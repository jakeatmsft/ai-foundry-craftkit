from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

DEFAULT_ENDPOINT = "https://your-resource-name.services.ai.azure.com/"
DEFAULT_MODEL = "gpt-realtime"
DEFAULT_API_VERSION = "2026-04-10"
DEFAULT_VOICE = "en-US-Ava:DragonHDLatestNeural"
DEFAULT_INPUT_WAV = str(Path(__file__).resolve().parents[2] / "tts_hello.wav")
DEFAULT_INSTRUCTIONS = (
    "You are a helpful AI assistant. Respond naturally and conversationally. "
    "Keep your responses concise but engaging."
)


@dataclass(slots=True)
class VoiceLiveSettings:
    endpoint: str
    model: str
    api_version: str
    voice: str
    instructions: str
    input_wav: str | None
    use_microphone: bool
    chunk_ms: int
    sleep_between_chunks_ms: int
    api_key: str | None
    use_token_credential: bool
    verbose: bool

    def validate(self) -> None:
        if not self.endpoint or self.endpoint == DEFAULT_ENDPOINT:
            raise ValueError("AZURE_VOICELIVE_ENDPOINT must be set to your Voice Live resource endpoint.")
        if not self.model:
            raise ValueError("AZURE_VOICELIVE_MODEL is required.")
        if not self.api_key and not self.use_token_credential:
            raise ValueError(
                "Provide --api-key, set AZURE_VOICELIVE_API_KEY, or pass --use-token-credential."
            )
        if not self.use_microphone:
            if not self.input_wav:
                raise ValueError("Provide --input-wav or pass --use-microphone.")
            if not Path(self.input_wav).is_file():
                raise ValueError(f"Input WAV file not found: {self.input_wav}")
        if self.chunk_ms <= 0:
            raise ValueError("--chunk-ms must be greater than 0.")
        if self.sleep_between_chunks_ms < 0:
            raise ValueError("--sleep-between-chunks-ms cannot be negative.")


class ParsedArguments(argparse.Namespace):
    endpoint: str
    model: str
    api_version: str
    voice: str
    instructions: str
    input_wav: str | None
    use_microphone: bool
    chunk_ms: int
    sleep_between_chunks_ms: int
    api_key: str | None
    use_token_credential: bool
    verbose: bool

    def to_settings(self) -> VoiceLiveSettings:
        return VoiceLiveSettings(
            endpoint=self.endpoint,
            model=self.model,
            api_version=self.api_version,
            voice=self.voice,
            instructions=self.instructions,
            input_wav=self.input_wav,
            use_microphone=self.use_microphone,
            chunk_ms=self.chunk_ms,
            sleep_between_chunks_ms=self.sleep_between_chunks_ms,
            api_key=self.api_key,
            use_token_credential=self.use_token_credential,
            verbose=self.verbose,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Basic Voice Assistant using Azure VoiceLive SDK",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.getenv("AZURE_VOICELIVE_API_KEY"),
        help="Azure VoiceLive API key. Defaults from AZURE_VOICELIVE_API_KEY.",
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default=os.getenv("AZURE_VOICELIVE_ENDPOINT", DEFAULT_ENDPOINT),
        help="Azure VoiceLive endpoint.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=os.getenv("AZURE_VOICELIVE_MODEL", DEFAULT_MODEL),
        help="VoiceLive model to use.",
    )
    parser.add_argument(
        "--api-version",
        type=str,
        default=os.getenv("AZURE_VOICELIVE_API_VERSION", DEFAULT_API_VERSION),
        help="VoiceLive API version to request when supported by the installed SDK.",
    )
    parser.add_argument(
        "--voice",
        type=str,
        default=os.getenv("AZURE_VOICELIVE_VOICE", DEFAULT_VOICE),
        help="Assistant voice. Example: alloy, echo, fable, en-US-Ava:DragonHDLatestNeural.",
    )
    parser.add_argument(
        "--instructions",
        type=str,
        default=os.getenv("AZURE_VOICELIVE_INSTRUCTIONS", DEFAULT_INSTRUCTIONS),
        help="System instructions for the AI assistant.",
    )
    parser.add_argument(
        "--input-wav",
        type=str,
        default=os.getenv("AZURE_VOICELIVE_INPUT_WAV", DEFAULT_INPUT_WAV),
        help="Path to a mono 24 kHz PCM16 WAV file. Defaults to tts_hello.wav in this sample folder.",
    )
    parser.add_argument(
        "--use-microphone",
        action="store_true",
        default=False,
        help="Use live microphone input instead of sending the default WAV file.",
    )
    parser.add_argument(
        "--chunk-ms",
        type=int,
        default=int(os.getenv("AZURE_VOICELIVE_CHUNK_MS", "100")),
        help="Chunk size, in milliseconds, when streaming WAV input.",
    )
    parser.add_argument(
        "--sleep-between-chunks-ms",
        type=int,
        default=int(os.getenv("AZURE_VOICELIVE_SLEEP_BETWEEN_CHUNKS_MS", "0")),
        help="Optional delay between WAV chunks to mimic live streaming.",
    )
    parser.add_argument(
        "--use-token-credential",
        action="store_true",
        default=False,
        help="Use AzureCliCredential instead of an API key.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose logging.",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> ParsedArguments:
    return build_parser().parse_args(argv, namespace=ParsedArguments())
