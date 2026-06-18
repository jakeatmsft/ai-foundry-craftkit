from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)


def main(argv: Sequence[str] | None = None) -> int:
    from src.voice_live_app.assistant import BasicVoiceAssistant, build_credential, check_audio_devices
    from src.voice_live_app.config import parse_args

    args = parse_args(argv)
    configure_logging(args.verbose)

    try:
        settings = args.to_settings()
        settings.validate()
        check_audio_devices(require_input=settings.use_microphone)
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        return 1
    except RuntimeError as exc:
        print(f"Audio system error: {exc}")
        return 1

    assistant = BasicVoiceAssistant(
        endpoint=settings.endpoint,
        credential=build_credential(settings),
        model=settings.model,
        voice=settings.voice,
        instructions=settings.instructions,
        api_version=settings.api_version,
        input_wav=Path(settings.input_wav).resolve() if settings.input_wav else None,
        use_microphone=settings.use_microphone,
        chunk_ms=settings.chunk_ms,
        sleep_between_chunks_ms=settings.sleep_between_chunks_ms,
    )

    print("Basic Voice Assistant with Azure VoiceLive SDK")
    print("=" * 50)

    try:
        asyncio.run(assistant.start())
    except KeyboardInterrupt:
        print("\nVoice assistant shut down.")
        return 0
    except Exception as exc:  # pragma: no cover - depends on external service
        print(f"Fatal error: {exc}")
        return 1

    return 0


def configure_logging(verbose: bool) -> None:
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(exist_ok=True)

    from datetime import datetime

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        filename=log_dir / f"{timestamp}_voicelive.log",
        filemode="w",
        format="%(asctime)s:%(name)s:%(levelname)s:%(message)s",
        level=level,
    )


if __name__ == "__main__":
    raise SystemExit(main())
