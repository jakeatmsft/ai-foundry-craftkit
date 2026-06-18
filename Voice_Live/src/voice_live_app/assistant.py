from __future__ import annotations

import asyncio
import inspect
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Union, cast

import pyaudio
from azure.core.credentials import AzureKeyCredential
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import AzureCliCredential
from azure.ai.voicelive.aio import connect
from azure.ai.voicelive.models import (
    AudioEchoCancellation,
    AudioNoiseReduction,
    AzureStandardVoice,
    InputAudioFormat,
    Modality,
    OutputAudioFormat,
    RequestSession,
    ServerEventType,
    ServerVad,
)

from src.voice_live_app.audio import AudioProcessor, stream_wav_audio
from src.voice_live_app.config import VoiceLiveSettings

if TYPE_CHECKING:
    from azure.ai.voicelive.aio import VoiceLiveConnection

logger = logging.getLogger(__name__)


def build_credential(settings: VoiceLiveSettings) -> Union[AzureKeyCredential, AsyncTokenCredential]:
    if settings.use_token_credential:
        logger.info("Using Azure CLI token credential")
        return AzureCliCredential()
    assert settings.api_key is not None, "API key must be present when token auth is disabled."
    logger.info("Using API key credential")
    return AzureKeyCredential(settings.api_key)


def check_audio_devices(*, require_input: bool) -> None:
    audio = None
    try:
        audio = pyaudio.PyAudio()
        input_devices = []
        if require_input:
            input_devices = [
                i
                for i in range(audio.get_device_count())
                if cast(int | float, audio.get_device_info_by_index(i).get("maxInputChannels", 0) or 0) > 0
            ]
        output_devices = [
            i
            for i in range(audio.get_device_count())
            if cast(int | float, audio.get_device_info_by_index(i).get("maxOutputChannels", 0) or 0) > 0
        ]
    except Exception as exc:  # pragma: no cover - depends on local audio stack
        raise RuntimeError(f"Audio system check failed: {exc}") from exc
    finally:
        try:
            audio.terminate()
        except Exception:
            pass

    if require_input and not input_devices:
        raise RuntimeError("No audio input devices found. Check your microphone.")
    if not output_devices:
        raise RuntimeError("No audio output devices found. Check your speakers.")


class BasicVoiceAssistant:
    """Simple Voice Live assistant using direct model sessions."""

    def __init__(
        self,
        endpoint: str,
        credential: Union[AzureKeyCredential, AsyncTokenCredential],
        model: str,
        voice: str,
        instructions: str,
        api_version: str,
        input_wav: Path | None,
        use_microphone: bool,
        chunk_ms: int,
        sleep_between_chunks_ms: int,
    ) -> None:
        self.endpoint = endpoint
        self.credential = credential
        self.model = model
        self.voice = voice
        self.instructions = instructions
        self.api_version = api_version
        self.input_wav = input_wav
        self.use_microphone = use_microphone
        self.chunk_ms = chunk_ms
        self.sleep_between_chunks_ms = sleep_between_chunks_ms
        self.connection: VoiceLiveConnection | None = None
        self.audio_processor: AudioProcessor | None = None
        self._file_input_sent = False
        self._should_exit = False

    async def start(self) -> None:
        connect_kwargs = self._build_connect_kwargs()
        logger.info("Connecting to VoiceLive API with model %s", self.model)

        try:
            async with connect(**connect_kwargs) as connection:
                self.connection = connection
                self.audio_processor = AudioProcessor(connection)
                await self._setup_session()
                self.audio_processor.start_playback()

                print("\n" + "=" * 60)
                print("VOICE ASSISTANT READY")
                if self.use_microphone:
                    print("Start speaking to begin the conversation")
                else:
                    assert self.input_wav is not None
                    print(f"Sending WAV input: {self.input_wav.name}")
                print("Press Ctrl+C to exit")
                print("=" * 60 + "\n")

                await self._process_events()
        finally:
            if self.audio_processor:
                self.audio_processor.shutdown()

    async def _setup_session(self) -> None:
        logger.info("Setting up session")

        voice_config: Union[AzureStandardVoice, str]
        if "-" in self.voice:
            voice_config = AzureStandardVoice(name=self.voice)
        else:
            voice_config = self.voice

        session_kwargs: dict[str, object] = {
            "modalities": [Modality.TEXT, Modality.AUDIO],
            "instructions": self.instructions,
            "voice": voice_config,
            "input_audio_format": InputAudioFormat.PCM16,
            "output_audio_format": OutputAudioFormat.PCM16,
            "turn_detection": (
                ServerVad(
                    threshold=0.5,
                    prefix_padding_ms=400,
                    silence_duration_ms=500,
                )
                if self.use_microphone
                else None
            ),
        }

        if self.use_microphone:
            session_kwargs["input_audio_echo_cancellation"] = AudioEchoCancellation()
            session_kwargs["input_audio_noise_reduction"] = AudioNoiseReduction(
                type="azure_deep_noise_suppression",
            )

        session_config = RequestSession(**session_kwargs)

        assert self.connection is not None, "Connection must exist before session setup."
        await self.connection.session.update(session=session_config)
        logger.info("Session configuration sent")

    async def _process_events(self) -> None:
        assert self.connection is not None, "Connection must exist before processing events."
        async for event in self.connection:
            await self._handle_event(event)
            if self._should_exit:
                break

    async def _handle_event(self, event) -> None:
        logger.debug("Received event: %s", event.type)
        assert self.audio_processor is not None, "Audio processor must be initialized."

        if event.type == ServerEventType.SESSION_UPDATED:
            logger.info("Session ready: %s", event.session.id)
            if self.use_microphone:
                self.audio_processor.start_capture()
            elif not self._file_input_sent:
                self._file_input_sent = True
                await self._send_input_wav()
            return

        if event.type == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED:
            logger.info("User started speaking")
            print("Listening...")
            self.audio_processor.skip_pending_audio()
            return

        if event.type == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STOPPED:
            logger.info("User stopped speaking")
            print("Processing...")
            return

        if event.type == ServerEventType.RESPONSE_CREATED:
            logger.info("Assistant response created")
            return

        if event.type == ServerEventType.RESPONSE_AUDIO_DELTA:
            self.audio_processor.queue_audio(event.delta)
            return

        if event.type == ServerEventType.RESPONSE_AUDIO_DONE:
            logger.info("Assistant finished speaking")
            print("Ready for next input...")
            return

        if event.type == ServerEventType.RESPONSE_DONE:
            logger.info("Response complete")
            if not self.use_microphone:
                while not self.audio_processor.playback_queue.empty():
                    await asyncio.sleep(0.05)
                await asyncio.sleep(0.25)
                self._should_exit = True
            return

        if event.type == ServerEventType.ERROR:
            message = event.error.message
            if "Cancellation failed: no active response" not in message:
                logger.error("VoiceLive error: %s", message)
                print(f"Error: {message}")
            return

    def _build_connect_kwargs(self) -> dict[str, object]:
        kwargs: dict[str, object] = {
            "endpoint": self.endpoint,
            "credential": self.credential,
            "model": self.model,
        }

        try:
            signature = inspect.signature(connect)
        except (TypeError, ValueError):
            signature = None

        if signature and "api_version" in signature.parameters:
            kwargs["api_version"] = self.api_version

        return kwargs

    async def _send_input_wav(self) -> None:
        assert self.connection is not None, "Connection must exist before sending audio."
        assert self.input_wav is not None, "An input WAV path is required for file mode."

        logger.info("Streaming WAV input from %s", self.input_wav)
        print(f"Streaming WAV input from {self.input_wav.name}...")

        await stream_wav_audio(
            self.connection,
            self.input_wav,
            chunk_ms=self.chunk_ms,
            sleep_between_chunks_ms=self.sleep_between_chunks_ms,
        )
        await self._commit_input_audio_buffer()
        print("Processing...")
        await self._create_response()

    async def _commit_input_audio_buffer(self) -> None:
        assert self.connection is not None, "Connection must exist before committing audio."
        commit_method = getattr(self.connection.input_audio_buffer, "commit", None)
        if not callable(commit_method):
            raise RuntimeError("The installed VoiceLive SDK does not expose input_audio_buffer.commit().")
        result = commit_method()
        if inspect.isawaitable(result):
            await result

    async def _create_response(self) -> None:
        assert self.connection is not None, "Connection must exist before creating a response."

        for owner_name in ("response", "responses"):
            owner = getattr(self.connection, owner_name, None)
            create_method = getattr(owner, "create", None) if owner is not None else None
            if not callable(create_method):
                continue

            try:
                result = create_method()
            except TypeError:
                result = create_method(response={"modalities": ["text", "audio"]})

            if inspect.isawaitable(result):
                await result
            return

        raise RuntimeError("The installed VoiceLive SDK does not expose a response creation method.")
