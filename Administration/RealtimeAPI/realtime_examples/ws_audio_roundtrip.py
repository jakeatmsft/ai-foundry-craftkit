import argparse
import asyncio
import base64
import inspect
import json
import os
import re
import wave
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

import websockets
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

SCRIPT_PATH = Path(__file__).resolve()


def load_env_chain() -> None:
    current = SCRIPT_PATH.parent
    loaded: set[Path] = set()
    for parent in [current, *current.parents]:
        env_path = parent / ".env"
        if env_path.exists() and env_path not in loaded:
            load_dotenv(env_path, override=False)
            loaded.add(env_path)


load_env_chain()

PCM16_SAMPLE_RATE = 24_000
PCM16_SAMPLE_WIDTH = 2
PCM16_CHANNELS = 1
DEFAULT_CHUNK_MS = 100
DEFAULT_TIMEOUT_S = 60.0
DEFAULT_VOICE = "alloy"
DEFAULT_INSTRUCTIONS = (
    "Listen to the user's audio and respond naturally. "
    "Return both text and audio."
)


@dataclass
class CaptureState:
    input_transcript: str = ""
    response_text: str = ""
    response_audio_transcript: str = ""
    response_audio_bytes: bytearray = field(default_factory=bytearray)
    errors: list[dict[str, Any]] = field(default_factory=list)
    event_count: int = 0
    session_id: str | None = None


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    default_input = SCRIPT_PATH.with_name("tts_hello.wav")
    default_output = SCRIPT_PATH.with_name("outputs") / f"roundtrip-{utc_timestamp()}"

    parser = argparse.ArgumentParser(
        description="Send a WAV file to Azure OpenAI Realtime over WebSockets and save transcripts/audio."
    )
    parser.add_argument(
        "--input-wav",
        default=str(default_input),
        help="Path to a mono 24 kHz PCM16 WAV file.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(default_output),
        help="Directory where transcripts, audio, and event logs are written.",
    )
    parser.add_argument(
        "--deployment",
        default=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME") or os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        help="Azure OpenAI realtime deployment name. Defaults from .env.",
    )
    parser.add_argument(
        "--endpoint",
        default=os.getenv("AZURE_OPENAI_ENDPOINT"),
        help="Azure OpenAI endpoint, for example https://my-resource.openai.azure.com. Defaults from .env.",
    )
    parser.add_argument(
        "--api-mode",
        choices=("ga", "preview"),
        default=os.getenv("AZURE_OPENAI_REALTIME_API_MODE", "ga"),
        help="Use GA or preview WebSocket endpoint shape.",
    )
    parser.add_argument(
        "--api-version",
        default=os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview"),
        help="Preview API version. Ignored for GA mode.",
    )
    parser.add_argument(
        "--voice",
        default=os.getenv("AZURE_OPENAI_REALTIME_VOICE", DEFAULT_VOICE),
        help="Voice used for audio output.",
    )
    parser.add_argument(
        "--instructions",
        default=os.getenv("AZURE_OPENAI_REALTIME_INSTRUCTIONS", DEFAULT_INSTRUCTIONS),
        help="Session instructions.",
    )
    parser.add_argument(
        "--transcription-deployment",
        default=os.getenv("AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT_NAME"),
        help="Optional deployment used for input audio transcription.",
    )
    parser.add_argument(
        "--chunk-ms",
        type=int,
        default=DEFAULT_CHUNK_MS,
        help="Audio chunk size to send per append event.",
    )
    parser.add_argument(
        "--sleep-between-chunks-ms",
        type=int,
        default=0,
        help="Optional delay between audio chunks to mimic live streaming.",
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=DEFAULT_TIMEOUT_S,
        help="Timeout waiting for response.done.",
    )
    parser.add_argument(
        "--auth-mode",
        choices=("auto", "api_key", "entra"),
        default="entra",
        help="Authentication mode. Defaults to Entra ID via DefaultAzureCredential.",
    )
    return parser.parse_args()


def normalize_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.exists():
        return path.resolve()

    win_match = re.match(r"^([A-Za-z]):[\\/](.*)$", path_text)
    if win_match:
        drive = win_match.group(1).lower()
        rest = win_match.group(2).replace("\\", "/")
        wsl_path = Path(f"/mnt/{drive}/{rest}")
        if wsl_path.exists():
            return wsl_path.resolve()

    return path.resolve()


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


def build_websocket_url(endpoint: str, deployment: str, api_mode: str, api_version: str) -> str:
    parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
    host = parsed.netloc or parsed.path
    if not host:
        raise ValueError("AZURE_OPENAI_ENDPOINT is required.")

    if api_mode == "ga":
        query = urlencode({"model": deployment})
        return f"wss://{host}/openai/v1/realtime?{query}"

    query = urlencode({"deployment": deployment, "api-version": api_version})
    return f"wss://{host}/openai/realtime?{query}"


def build_headers(auth_mode: str) -> dict[str, str]:
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    use_api_key = auth_mode == "api_key" or (auth_mode == "auto" and bool(api_key))

    if use_api_key:
        if not api_key:
            raise ValueError("AZURE_OPENAI_API_KEY is required for api_key auth mode.")
        return {"api-key": api_key}

    credential = DefaultAzureCredential()
    token = credential.get_token("https://cognitiveservices.azure.com/.default")
    return {"Authorization": f"Bearer {token.token}"}


def build_session_update(args: argparse.Namespace) -> dict[str, Any]:
    session: dict[str, Any] = {
        "modalities": ["text", "audio"],
        "voice": args.voice,
        "instructions": args.instructions,
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "turn_detection": None,
    }

    if args.transcription_deployment:
        session["input_audio_transcription"] = {"model": args.transcription_deployment}

    return {"type": "session.update", "session": session}


def build_response_create() -> dict[str, Any]:
    return {
        "type": "response.create",
        "response": {
            "modalities": ["text", "audio"],
        },
    }


def write_pcm16_wav(path: Path, pcm_bytes: bytes) -> None:
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(PCM16_CHANNELS)
        wav_file.setsampwidth(PCM16_SAMPLE_WIDTH)
        wav_file.setframerate(PCM16_SAMPLE_RATE)
        wav_file.writeframes(pcm_bytes)


def connect_kwargs(headers: dict[str, str]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"max_size": None}
    signature = inspect.signature(websockets.connect)
    if "additional_headers" in signature.parameters:
        kwargs["additional_headers"] = headers
    else:
        kwargs["extra_headers"] = headers
    return kwargs


async def send_event(ws: Any, event: dict[str, Any]) -> None:
    await ws.send(json.dumps(event))


async def append_audio(ws: Any, pcm_bytes: bytes, chunk_ms: int, sleep_ms: int) -> None:
    bytes_per_ms = PCM16_SAMPLE_RATE * PCM16_SAMPLE_WIDTH * PCM16_CHANNELS / 1000
    chunk_size = max(1, int(bytes_per_ms * chunk_ms))
    chunk_size -= chunk_size % PCM16_SAMPLE_WIDTH
    if chunk_size <= 0:
        chunk_size = PCM16_SAMPLE_WIDTH

    for offset in range(0, len(pcm_bytes), chunk_size):
        chunk = pcm_bytes[offset : offset + chunk_size]
        await send_event(
            ws,
            {
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(chunk).decode("ascii"),
            },
        )
        if sleep_ms > 0:
            await asyncio.sleep(sleep_ms / 1000)


def update_text(existing: str, delta: str) -> str:
    return f"{existing}{delta}"


async def receive_events(
    ws: Any,
    output_dir: Path,
    state: CaptureState,
    response_done: asyncio.Event,
) -> None:
    events_path = output_dir / "events.jsonl"
    with events_path.open("w", encoding="utf-8") as events_file:
        async for message in ws:
            if not isinstance(message, str):
                continue

            event = json.loads(message)
            state.event_count += 1
            event_type = event.get("type", "")
            events_file.write(json.dumps(event, ensure_ascii=False) + "\n")
            events_file.flush()

            if event_type == "session.created":
                session = event.get("session") or {}
                if isinstance(session, dict):
                    state.session_id = session.get("id")
            elif event_type == "conversation.item.input_audio_transcription.completed":
                transcript = event.get("transcript", "")
                if transcript:
                    state.input_transcript = transcript
            elif event_type in {"response.text.delta", "response.output_text.delta"}:
                state.response_text = update_text(state.response_text, event.get("delta", ""))
            elif event_type in {"response.text.done", "response.output_text.done"}:
                state.response_text = event.get("text") or state.response_text
            elif event_type in {"response.audio_transcript.delta", "response.output_audio_transcript.delta"}:
                state.response_audio_transcript = update_text(
                    state.response_audio_transcript,
                    event.get("delta", ""),
                )
            elif event_type in {"response.audio_transcript.done", "response.output_audio_transcript.done"}:
                state.response_audio_transcript = (
                    event.get("transcript") or state.response_audio_transcript
                )
            elif event_type in {"response.audio.delta", "response.output_audio.delta"}:
                delta = event.get("delta")
                if delta:
                    state.response_audio_bytes.extend(base64.b64decode(delta))
            elif event_type == "error":
                state.errors.append(event)
            elif event_type == "response.done":
                response_done.set()
                break


async def run_roundtrip(args: argparse.Namespace) -> Path:
    if not args.endpoint:
        raise ValueError("AZURE_OPENAI_ENDPOINT or --endpoint is required.")
    if not args.deployment:
        raise ValueError(
            "AZURE_OPENAI_DEPLOYMENT or AZURE_OPENAI_DEPLOYMENT_NAME or --deployment is required."
        )

    input_wav = normalize_path(args.input_wav)
    output_dir = normalize_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pcm_bytes = require_wav_format(input_wav)
    ws_url = build_websocket_url(args.endpoint, args.deployment, args.api_mode, args.api_version)
    headers = build_headers(args.auth_mode)

    state = CaptureState()
    response_done = asyncio.Event()

    async with websockets.connect(ws_url, **connect_kwargs(headers)) as ws:
        receiver = asyncio.create_task(receive_events(ws, output_dir, state, response_done))

        await send_event(ws, build_session_update(args))
        await append_audio(ws, pcm_bytes, args.chunk_ms, args.sleep_between_chunks_ms)
        await send_event(ws, {"type": "input_audio_buffer.commit"})
        await send_event(ws, build_response_create())

        try:
            await asyncio.wait_for(response_done.wait(), timeout=args.timeout_s)
        finally:
            receiver.cancel()
            try:
                await receiver
            except asyncio.CancelledError:
                pass

    write_outputs(output_dir, input_wav, args, state)
    return output_dir


def write_outputs(
    output_dir: Path,
    input_wav: Path,
    args: argparse.Namespace,
    state: CaptureState,
) -> None:
    (output_dir / "input_transcript.txt").write_text(state.input_transcript, encoding="utf-8")
    (output_dir / "response_text.txt").write_text(state.response_text, encoding="utf-8")
    (output_dir / "response_audio_transcript.txt").write_text(
        state.response_audio_transcript,
        encoding="utf-8",
    )

    if state.response_audio_bytes:
        write_pcm16_wav(output_dir / "response_audio.wav", bytes(state.response_audio_bytes))

    summary = {
        "input_wav": str(input_wav),
        "output_dir": str(output_dir),
        "endpoint": args.endpoint,
        "deployment": args.deployment,
        "api_mode": args.api_mode,
        "session_id": state.session_id,
        "event_count": state.event_count,
        "response_audio_bytes": len(state.response_audio_bytes),
        "errors": state.errors,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    output_dir = asyncio.run(run_roundtrip(args))
    print(f"Saved outputs to {output_dir}")


if __name__ == "__main__":
    main()
