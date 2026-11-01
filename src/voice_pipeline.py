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

_SECTION_REF = re.compile(r"\s*\((?:per |policy |see )?[A-Z]{2,5}[-]\d+(?:\.\d+)?\)|\s+per\s+[A-Z]{2,5}-\d+(?:\.\d+)?", re.IGNORECASE)
SPOKEN_MAX_CHARS = 420


def speakable_text(text: str, max_chars: int = SPOKEN_MAX_CHARS) -> str:
    """Turn a written reply into something short and natural to hear.

    Written answers contain markdown tables, bullets, bold marks and policy codes that a voice
    would read out loud ("asterisk asterisk", "pipe"). Strip those, flatten table rows to
    "name: value", and keep roughly the first few sentences. The full text is still returned
    in the result JSON and shown on screen.
    """
    text = (text or "").replace("\u2011", "-").replace("\u2010", "-")
    lines, rows = [], [ln.strip() for ln in text.splitlines()]
    i = 0
    while i < len(rows):
        row = rows[i]
        if row.startswith("|"):
            block = []
            while i < len(rows) and rows[i].startswith("|"):
                block.append(rows[i]); i += 1
            if len(block) > 1 and re.fullmatch(r"[|\s:\-]+", block[1]):
                block = block[2:]  # drop header and separator
            for item in block:
                if re.fullmatch(r"[|\s:\-]+", item):
                    continue
                cells = [c.strip() for c in item.strip("|").split("|") if c.strip()]
                if cells:
                    lines.append(("T", ": ".join(cells[:2])))
            continue
        row = re.sub(r"^(?:#+\s*|[*\-•]\s+|\d+[.)]\s+)", "", row)
        row = re.sub(r"[*_`]+", "", row)
        if row:
            lines.append(("P", row))
        i += 1
    def render(items):
        parts = []
        for line in items:
            line = _SECTION_REF.sub("", line).strip(" -–—")
            if line:
                parts.append(line if line[-1] in ".!?:" else line + ".")
        out = re.sub(r"\s+", " ", " ".join(parts)).replace(":.", ".").strip()
        return re.sub(r"([.!?])\s+[\u2013\u2014-]\s+", r"\1 ", out)

    spoken = render([t for _, t in lines])
    if len(spoken) <= max_chars:
        return spoken
    # Too long: a half-read table sounds like the whole answer, so drop table rows entirely.
    spoken = render([t for kind, t in lines if kind == "P"])
    if len(spoken) <= max_chars:
        return spoken + " I can share more detail if you would like."
    cut = spoken[:max_chars]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    cut = cut[:end + 1] if end > 80 else cut.rsplit(" ", 1)[0] + "."
    return cut + " I can share more detail if you would like."


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
            spoken = speakable_text(reply) or reply
            result["spoken_text"] = spoken
            self.tts.synthesize(spoken, audio_out)
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
