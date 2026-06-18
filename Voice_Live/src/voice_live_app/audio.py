from __future__ import annotations

import asyncio
import base64
import logging
import queue
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pyaudio

logger = logging.getLogger(__name__)

PCM16_SAMPLE_RATE = 24000
PCM16_SAMPLE_WIDTH = 2
PCM16_CHANNELS = 1


class AudioProcessor:
    """Handle microphone capture and speaker playback."""

    @dataclass(slots=True)
    class AudioPlaybackPacket:
        seq_num: int
        data: Optional[bytes]

    def __init__(self, connection) -> None:
        self.connection = connection
        self.audio = pyaudio.PyAudio()
        self.format = pyaudio.paInt16
        self.channels = PCM16_CHANNELS
        self.rate = PCM16_SAMPLE_RATE
        self.chunk_size = 1200
        self.input_stream = None
        self.output_stream = None
        self.playback_queue: queue.Queue[AudioProcessor.AudioPlaybackPacket] = queue.Queue()
        self.playback_base = 0
        self.next_seq_num = 0
        self.loop: asyncio.AbstractEventLoop | None = None
        logger.info("Audio processor initialized with 24 kHz PCM16 mono audio")

    def start_capture(self) -> None:
        def capture_callback(in_data, _frame_count, _time_info, _status_flags):
            assert self.loop is not None, "Event loop must be available before capture starts."
            audio_base64 = base64.b64encode(in_data).decode("utf-8")
            asyncio.run_coroutine_threadsafe(
                self.connection.input_audio_buffer.append(audio=audio_base64),
                self.loop,
            )
            return (None, pyaudio.paContinue)

        if self.input_stream:
            return

        self.loop = asyncio.get_running_loop()
        self.input_stream = self.audio.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            stream_callback=capture_callback,
        )
        logger.info("Started audio capture")

    def start_playback(self) -> None:
        if self.output_stream:
            return

        remaining = bytes()

        def playback_callback(_in_data, frame_count, _time_info, _status_flags):
            nonlocal remaining
            frame_bytes = frame_count * pyaudio.get_sample_size(pyaudio.paInt16)
            output = remaining[:frame_bytes]
            remaining = remaining[frame_bytes:]

            while len(output) < frame_bytes:
                try:
                    packet = self.playback_queue.get_nowait()
                except queue.Empty:
                    output += bytes(frame_bytes - len(output))
                    continue

                if packet.data is None:
                    logger.info("Reached end of playback queue")
                    break

                if packet.seq_num < self.playback_base:
                    remaining = bytes()
                    continue

                needed = frame_bytes - len(output)
                output += packet.data[:needed]
                remaining = packet.data[needed:]

            if len(output) >= frame_bytes:
                return (output, pyaudio.paContinue)
            return (output, pyaudio.paComplete)

        self.output_stream = self.audio.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            output=True,
            frames_per_buffer=self.chunk_size,
            stream_callback=playback_callback,
        )
        logger.info("Audio playback system ready")

    def queue_audio(self, audio_data: Optional[bytes]) -> None:
        self.playback_queue.put(
            AudioProcessor.AudioPlaybackPacket(
                seq_num=self._get_and_increase_seq_num(),
                data=audio_data,
            )
        )

    def skip_pending_audio(self) -> None:
        self.playback_base = self._get_and_increase_seq_num()

    def shutdown(self) -> None:
        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
            self.input_stream = None
            logger.info("Stopped audio capture")

        if self.output_stream:
            self.skip_pending_audio()
            self.queue_audio(None)
            self.output_stream.stop_stream()
            self.output_stream.close()
            self.output_stream = None
            logger.info("Stopped audio playback")

        self.audio.terminate()
        logger.info("Audio processor cleaned up")

    def _get_and_increase_seq_num(self) -> int:
        seq_num = self.next_seq_num
        self.next_seq_num += 1
        return seq_num


def require_wav_format(audio_path: Path) -> bytes:
    with wave.open(str(audio_path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_rate = wav_file.getframerate()
        sample_width = wav_file.getsampwidth()
        frames = wav_file.getnframes()

        if channels != PCM16_CHANNELS:
            raise ValueError(f"{audio_path} must be mono; got {channels} channels.")
        if sample_rate != PCM16_SAMPLE_RATE:
            raise ValueError(f"{audio_path} must be 24 kHz; got {sample_rate} Hz.")
        if sample_width != PCM16_SAMPLE_WIDTH:
            raise ValueError(f"{audio_path} must be 16-bit PCM; got {sample_width * 8}-bit.")
        if frames <= 0:
            raise ValueError(f"{audio_path} does not contain any audio frames.")

        return wav_file.readframes(frames)


async def stream_wav_audio(
    connection,
    audio_path: Path,
    chunk_ms: int,
    sleep_between_chunks_ms: int,
) -> None:
    pcm_bytes = require_wav_format(audio_path)
    bytes_per_ms = PCM16_SAMPLE_RATE * PCM16_SAMPLE_WIDTH * PCM16_CHANNELS / 1000
    chunk_size = max(PCM16_SAMPLE_WIDTH, int(bytes_per_ms * chunk_ms))
    chunk_size -= chunk_size % PCM16_SAMPLE_WIDTH
    if chunk_size <= 0:
        chunk_size = PCM16_SAMPLE_WIDTH

    for offset in range(0, len(pcm_bytes), chunk_size):
        chunk = pcm_bytes[offset : offset + chunk_size]
        await connection.input_audio_buffer.append(
            audio=base64.b64encode(chunk).decode("ascii"),
        )
        if sleep_between_chunks_ms > 0:
            await asyncio.sleep(sleep_between_chunks_ms / 1000)
