"""Gnani.ai-only text-to-speech adapter using explicit model/voice settings."""
from __future__ import annotations
import os
from pathlib import Path
from .config import Settings
from .gnani_stt import GnaniConfigurationError

class GnaniTTS:
    def __init__(self, settings: Settings | None = None, client=None):
        self.settings = settings or Settings.from_env()
        self._client = client

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.settings.gnani_api_key:
            raise GnaniConfigurationError("GNANI_API_KEY is required for live text-to-speech.")
        os.environ["GNANI_API_KEY"] = self.settings.gnani_api_key
        try:
            from gnani.tts import GnaniTTSClient
        except ImportError as exc:
            raise GnaniConfigurationError("Install the official Gnani SDK from requirements.txt.") from exc
        self._client = GnaniTTSClient(api_key=self.settings.gnani_api_key)
        return self._client

    def synthesize(self, text: str, output_path: Path) -> Path:
        if not (text or "").strip():
            raise ValueError("Text-to-speech input must not be empty.")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        audio = self._get_client().synthesize(
            text.strip(), voice=self.settings.tts_voice,
            model=self.settings.tts_model, language=self.settings.tts_language,
        )
        if hasattr(audio, "read"):
            audio = audio.read()
        if not isinstance(audio, (bytes, bytearray)) or len(audio) == 0:
            raise RuntimeError("Gnani TTS returned empty or unsupported audio data.")
        output_path.write_bytes(bytes(audio))
        if output_path.stat().st_size == 0:
            raise RuntimeError("Synthesized audio file was empty.")
        # WAV responses from the documented REST client should be RIFF/WAVE. Don't infer validity from extension alone.
        header = output_path.read_bytes()[:12]
        if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE":
            return output_path
        # SDK/API may evolve; preserve the bytes but fail validation explicitly if it isn't a recognized WAV payload.
        output_path.unlink(missing_ok=True)
        raise RuntimeError("Gnani TTS output was not a valid RIFF/WAVE file.")
