"""Environment-backed configuration. Secrets are never logged."""
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    dataset_dir: Path
    vector_store_path: Path
    llm_api_key: str
    llm_model: str
    llm_base_url: str | None
    gnani_api_key: str
    stt_language: str
    tts_language: str
    tts_model: str
    tts_voice: str
    log_level: str
    app_host: str
    app_port: int

    @classmethod
    def from_env(cls) -> "Settings":
        base_url = os.getenv("LLM_BASE_URL", "").strip() or None
        return cls(
            dataset_dir=Path(os.getenv("DATASET_DIR", "./dataset/Capstone_Project_Dataset_FTTT_2026")).expanduser(),
            vector_store_path=Path(os.getenv("VECTOR_STORE_PATH", "./storage/vector_index.joblib")).expanduser(),
            llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
            llm_model=os.getenv("LLM_MODEL", "gpt-4.1-mini").strip(),
            llm_base_url=base_url,
            gnani_api_key=os.getenv("GNANI_API_KEY", "").strip(),
            stt_language=os.getenv("GNANI_STT_LANGUAGE", "en-IN").strip(),
            tts_language=os.getenv("GNANI_TTS_LANGUAGE", "en-IN").strip(),
            tts_model=os.getenv("GNANI_TTS_MODEL", "timbre-v2.5").strip(),
            tts_voice=os.getenv("GNANI_TTS_VOICE", "Kaveri").strip(),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            app_host=os.getenv("APP_HOST", "127.0.0.1"),
            app_port=int(os.getenv("APP_PORT", "8000")),
        )

    def validate_dataset(self) -> Path:
        root = self.dataset_dir.resolve()
        required = [root / "kb", root / "data", root / "practice", root / "tools" / "tools.py"]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise FileNotFoundError(
                "Dataset directory is missing required challenge files: " + ", ".join(missing)
                + ". Extract Capstone_Project_Dataset_FTTT_2026.zip and set DATASET_DIR."
            )
        return root
