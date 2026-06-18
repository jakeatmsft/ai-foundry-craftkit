# Voice Live Quickstart Sample

This folder now contains a small Python sample app based on the "Create a Voice Live real-time voice agent" quickstart. It opens a Voice Live session against a Microsoft Foundry model, sends `tts_hello.wav` to the service by default, and plays the assistant audio response through your default speaker device. You can switch back to live microphone input with a flag.

## Article Summary

The article's core point is that Voice Live can be used directly with a model instead of a portal-managed agent. That makes setup lighter when you want to control prompts, voice, and session behavior per run. The quickstart flow is:

1. Install `azure-ai-voicelive[aiohttp]`, `pyaudio`, `python-dotenv`, and `azure-identity`.
2. Put endpoint, model, API version, and optional API key in `.env`.
3. Authenticate with either Microsoft Entra ID (`az login`) or an API key.
4. Open a Voice Live connection, update the session, stream PCM16 microphone audio, and play PCM16 assistant audio back locally.

## Files

- `voice-live-quickstart.py`: thin entry point so the run command matches the article.
- `src/main.py`: loads `.env`, parses arguments, validates only the audio devices the selected mode needs, and starts the app.
- `src/voice_live_app/config.py`: CLI and environment configuration.
- `src/voice_live_app/audio.py`: microphone capture and speaker playback using PyAudio.
- `src/voice_live_app/assistant.py`: Voice Live session setup and event loop.
- `tests/test_config.py`: lightweight unit tests for config parsing.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` with your resource values:

```dotenv
AZURE_VOICELIVE_ENDPOINT=https://your-resource.services.ai.azure.com/
AZURE_VOICELIVE_MODEL=gpt-realtime
AZURE_VOICELIVE_API_VERSION=2026-04-10
AZURE_VOICELIVE_API_KEY=
AZURE_VOICELIVE_VOICE=en-US-Ava:DragonHDLatestNeural
AZURE_VOICELIVE_INSTRUCTIONS=You are a helpful voice assistant. Keep replies concise.
AZURE_VOICELIVE_INPUT_WAV=tts_hello.wav
```

## Run

Use Azure CLI / Entra ID with the bundled `tts_hello.wav` input:

```bash
az login
python voice-live-quickstart.py --use-token-credential
```

Use live microphone input instead:

```bash
python voice-live-quickstart.py --use-token-credential --use-microphone
```

Use a different WAV file:

```bash
python voice-live-quickstart.py --use-token-credential --input-wav /path/to/file.wav
```

Use an API key:

```bash
python voice-live-quickstart.py --api-key "$AZURE_VOICELIVE_API_KEY"
```

Verbose logging:

```bash
python voice-live-quickstart.py --use-token-credential --verbose
```

The app writes session logs to `logs/<timestamp>_voicelive.log`.

## Test

```bash
python -m unittest discover -s tests
```

## Notes

- `AZURE_VOICELIVE_API_VERSION` is accepted in the config and passed to the SDK only when the installed SDK exposes an `api_version` argument on `connect()`.
- Default file mode requires only an output device. Microphone mode requires both input and output devices.
- WAV input must be mono, 24 kHz, 16-bit PCM. `tts_hello.wav` in this folder already matches that format.
- Follow-up for a productionized version: add `ruff`, `black`, and `mypy` config once this sample is folded into a maintained package or CI workflow.
