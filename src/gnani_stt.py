"""Gnani.ai-only speech-to-text adapter."""
from __future__ import annotations
import os
from pathlib import Path
from .config import Settings

class GnaniConfigurationError(RuntimeError):
    pass

class GnaniSTT:
    def __init__(self, settings: Settings | None = None, client=None):
        self.settings = settings or Settings.from_env()
        self._client = client

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.settings.gnani_api_key:
            raise GnaniConfigurationError("GNANI_API_KEY is required for live speech-to-text.")
        os.environ["GNANI_API_KEY"] = self.settings.gnani_api_key
        try:
            from gnani.stt import GnaniSTTClient
        except ImportError as exc:
            raise GnaniConfigurationError("Install the official Gnani SDK from requirements.txt.") from exc
        self._client = GnaniSTTClient(api_key=self.settings.gnani_api_key)
        return self._client

    def transcribe(self, audio_path: Path) -> str:
        audio_path = Path(audio_path)
        if not audio_path.is_file() or audio_path.stat().st_size == 0:
            raise ValueError("Audio file is missing or empty.")
        result = self._get_client().transcribe(str(audio_path), language_code=self.settings.stt_language)
        if isinstance(result, dict):
            transcript = result.get("transcript") or result.get("text") or ""
        else:
            transcript = getattr(result, "transcript", "") or ""
        return str(transcript).strip()
