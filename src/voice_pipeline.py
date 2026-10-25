"""End-to-end audio -> Gnani STT -> same support agent -> Gnani TTS pipeline."""
from __future__ import annotations
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any
from .agent import SupportAgent
from .config import Settings
from .gnani_stt import GnaniSTT
from .gnani_tts import GnaniTTS

logger = logging.getLogger(__name__)
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".ogg"}
MAX_AUDIO_BYTES = 10 * 1024 * 1024

class VoicePipeline:
    def __init__(self, agent: SupportAgent, settings: Settings | None = None, stt=None, tts=None):
        self.agent = agent
        self.settings = settings or Settings.from_env()
        self.stt = stt or GnaniSTT(self.settings)
        self.tts = tts or GnaniTTS(self.settings)

    def process_file(self, audio_path: Path, output_dir: Path, session_id: str) -> dict[str, Any]:
        audio_path = Path(audio_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        result: dict[str, Any] = {
            "input_filename": audio_path.name, "transcription": None, "response_text": None,
            "retrieved_sources": [], "tool_calls": [], "output_audio_filename": None,
            "status": "failed", "error": None,
        }
        try:
            if audio_path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
                raise ValueError(f"Unsupported audio format {audio_path.suffix or '(no extension)'}.")
            if not audio_path.is_file():
                raise FileNotFoundError("Input audio file does not exist.")
            if audio_path.stat().st_size == 0:
                raise ValueError("Input audio file is empty.")
            if audio_path.stat().st_size > MAX_AUDIO_BYTES:
                raise ValueError("Input audio exceeds the 10 MB SDK batch/REST file limit.")
            transcript = self.stt.transcribe(audio_path)
            result["transcription"] = transcript
            if not transcript:
                reply = "Sorry, I didn't catch that. Could you please repeat your question?"
                sources, tool_calls, decision = [], [], "clarify"
            else:
                agent_response = self.agent.respond(transcript, session_id=session_id)
                result["agent_ok"] = agent_response.ok
                result["agent_error"] = agent_response.error
                reply = agent_response.response
                sources = agent_response.sources
                tool_calls = agent_response.tool_calls
                decision = agent_response.decision
                if not agent_response.ok:
                    result["error"] = agent_response.error or "agent_failed"
            result["response_text"] = reply
            result["retrieved_sources"] = sources
            result["tool_calls"] = tool_calls
            result["decision"] = decision
            stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", audio_path.stem)[:80] or "audio"
            audio_out = output_dir / f"{stem}_{uuid.uuid4().hex[:8]}_reply.wav"
            self.tts.synthesize(reply, audio_out)
            result["output_audio_filename"] = audio_out.name
            result["status"] = "success" if not result.get("error") else "partial_failure"
        except Exception as exc:
            logger.warning("Audio file processing failed for %s (%s)", audio_path.name, type(exc).__name__)
            result["error"] = result.get("error") or f"{type(exc).__name__}: processing failed; check configuration and sanitized logs"
            # Do not synthesize a fallback via another provider. Keep the failed input in the manifest.
        result_path = output_dir / f"{re.sub(r'[^A-Za-z0-9_.-]+', '_', audio_path.stem)[:80] or 'audio'}_result.json"
        result["result_json_filename"] = result_path.name
        result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        return result
