from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src.voice_live_app.config import (
    DEFAULT_API_VERSION,
    DEFAULT_ENDPOINT,
    DEFAULT_INPUT_WAV,
    DEFAULT_MODEL,
    DEFAULT_VOICE,
    parse_args,
)


class ConfigTests(unittest.TestCase):
    def test_parse_args_uses_environment_defaults(self) -> None:
        with patch.dict(
            os.environ,
            {
                "AZURE_VOICELIVE_ENDPOINT": "https://example.services.ai.azure.com/",
                "AZURE_VOICELIVE_MODEL": "gpt-realtime-mini",
                "AZURE_VOICELIVE_API_VERSION": "2026-04-10",
                "AZURE_VOICELIVE_VOICE": "alloy",
                "AZURE_VOICELIVE_API_KEY": "test-key",
            },
            clear=False,
        ):
            args = parse_args([])

        self.assertEqual(args.endpoint, "https://example.services.ai.azure.com/")
        self.assertEqual(args.model, "gpt-realtime-mini")
        self.assertEqual(args.api_version, "2026-04-10")
        self.assertEqual(args.voice, "alloy")
        self.assertEqual(args.api_key, "test-key")

    def test_parse_args_falls_back_to_code_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            args = parse_args([])

        self.assertEqual(args.endpoint, DEFAULT_ENDPOINT)
        self.assertEqual(args.model, DEFAULT_MODEL)
        self.assertEqual(args.api_version, DEFAULT_API_VERSION)
        self.assertEqual(args.voice, DEFAULT_VOICE)
        self.assertEqual(args.input_wav, DEFAULT_INPUT_WAV)

    def test_settings_validation_requires_auth_or_token(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            args = parse_args(
                [
                    "--endpoint",
                    "https://example.services.ai.azure.com/",
                ]
            )

        with self.assertRaisesRegex(ValueError, "Provide --api-key"):
            args.to_settings().validate()

    def test_settings_validation_accepts_token_auth(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            args = parse_args(
                [
                    "--endpoint",
                    "https://example.services.ai.azure.com/",
                    "--use-token-credential",
                ]
            )

        args.to_settings().validate()

    def test_settings_validation_accepts_default_wav_input(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            args = parse_args(
                [
                    "--endpoint",
                    "https://example.services.ai.azure.com/",
                    "--use-token-credential",
                ]
            )

        settings = args.to_settings()
        self.assertFalse(settings.use_microphone)
        self.assertTrue(os.path.isfile(settings.input_wav))

    def test_settings_validation_skips_wav_requirement_for_microphone_mode(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            args = parse_args(
                [
                    "--endpoint",
                    "https://example.services.ai.azure.com/",
                    "--use-token-credential",
                    "--use-microphone",
                    "--input-wav",
                    "/does/not/exist.wav",
                ]
            )

        args.to_settings().validate()


if __name__ == "__main__":
    unittest.main()
