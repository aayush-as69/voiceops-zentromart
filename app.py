"""FastAPI web application for the VoiceOps 2026 ZentroMart agent."""
from __future__ import annotations
import logging
import tempfile
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from src.agent import SupportAgent
from src.config import Settings
from src.logging_config import configure_logging
from src.voice_pipeline import VoicePipeline, SUPPORTED_AUDIO_EXTENSIONS, MAX_AUDIO_BYTES

settings = Settings.from_env()
configure_logging(settings)
logger = logging.getLogger(__name__)
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
Path("storage").mkdir(parents=True, exist_ok=True)
agent = SupportAgent(settings)

app = FastAPI(title="ZentroMart AI Voice Support Agent", version="1.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    session_id: str = Field(min_length=1, max_length=100)

AUDIO_MIME_TYPES = {
    ".wav": {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"},
    ".mp3": {"audio/mpeg", "audio/mp3", "audio/x-mpeg"},
    ".flac": {"audio/flac", "audio/x-flac"},
    ".m4a": {"audio/mp4", "audio/x-m4a", "audio/m4a", "video/mp4"},
    ".ogg": {"audio/ogg", "application/ogg"},
}
GENERIC_MIME_TYPES = {"", "application/octet-stream", "binary/octet-stream"}

def _audio_signature_matches(suffix: str, contents: bytes) -> bool:
    """Check a lightweight container signature before passing bytes to an SDK."""
    if suffix == ".wav":
        return len(contents) >= 12 and contents[:4] in {b"RIFF", b"RF64"} and contents[8:12] == b"WAVE"
    if suffix == ".flac":
        return contents.startswith(b"fLaC")
    if suffix == ".ogg":
        return contents.startswith(b"OggS")
    if suffix == ".m4a":
        return len(contents) >= 12 and contents[4:8] == b"ftyp"
    if suffix == ".mp3":
        if contents.startswith(b"ID3"):
            return True
        return any(
            contents[index] == 0xFF and (contents[index + 1] & 0xE0) == 0xE0
            for index in range(min(16, max(0, len(contents) - 1)))
        )
    return False

@app.get("/", response_class=HTMLResponse)
def home():
    return FileResponse("templates/index.html")

@app.get("/health")
def health():
    return {
        "status": "ok",
        "dataset_configured": bool(agent.tools and agent.rag),
        "llm_configured": bool(settings.llm_api_key and settings.llm_model),
        "gnani_configured": bool(settings.gnani_api_key),
        "speech_provider": "Gnani.ai only",
        "reference_date": "2026-10-20",
    }

@app.post("/api/chat")
def chat(payload: ChatRequest):
    response = agent.respond(payload.message, payload.session_id)
    if not response.ok:
        status = 503 if response.error in {"llm_not_configured", "dataset_not_configured", "rag_unavailable"} else 502
        raise HTTPException(status_code=status, detail={
            "message": response.response,
            "error": response.error,
            "decision": response.decision,
            "sources": response.sources,
            "tool_calls": response.tool_calls,
        })
    return {
        "response": response.response,
        "decision": response.decision,
        "sources": response.sources,
        "tool_calls": response.tool_calls,
    }

@app.post("/api/voice")
def voice(audio: UploadFile = File(...), session_id: str = Form("")):
    suffix = Path(audio.filename or "audio.wav").suffix.lower()
    if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported audio format. Allowed: {', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))}")
    mime = (audio.content_type or "").split(";", 1)[0].strip().lower()
    if mime not in GENERIC_MIME_TYPES and mime not in AUDIO_MIME_TYPES[suffix]:
        raise HTTPException(status_code=415, detail="The audio content type does not match the file extension.")
    if not session_id or not session_id.strip() or len(session_id) > 100:
        raise HTTPException(status_code=400, detail="A valid session_id is required.")
    contents = audio.file.read(MAX_AUDIO_BYTES + 1)
    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded audio file is empty.")
    if len(contents) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio must be 10 MB or smaller.")
    if not _audio_signature_matches(suffix, contents):
        raise HTTPException(status_code=415, detail="The uploaded file does not appear to be valid audio in the declared format.")

    safe_session = "".join(ch for ch in session_id if ch.isalnum() or ch in "-_")[:60] or "session"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="zentromart_", suffix=suffix, delete=False) as tmp:
            tmp.write(contents)
            temp_path = Path(tmp.name)
        pipeline = VoicePipeline(agent, settings)
        result = pipeline.process_file(temp_path, OUTPUT_DIR, session_id=safe_session)
    except Exception as exc:
        logger.warning("Voice route failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=502, detail={
            "message": "Audio processing could not be completed. Check the service configuration and retry.",
            "error": type(exc).__name__,
        }) from None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    if not isinstance(result, dict) or result.get("status") != "success":
        detail = {
            "message": "Audio processing did not complete successfully. Check API configuration and retry.",
            "error": (result.get("error") or result.get("agent_error") or "voice_processing_failed") if isinstance(result, dict) else "voice_processing_failed",
        }
        if isinstance(result, dict) and result.get("transcription"):
            detail["transcription"] = result["transcription"]
        if isinstance(result, dict) and result.get("response_text"):
            detail["response"] = result["response_text"]
        raise HTTPException(status_code=502, detail=detail)
    output_name = Path(str(result.get("output_audio_filename") or "")).name
    output_path = (OUTPUT_DIR / output_name).resolve()
    if not output_name or output_path.parent != OUTPUT_DIR.resolve() or not output_path.is_file() or output_path.stat().st_size == 0:
        logger.warning("Voice pipeline reported success without a valid audio output")
        raise HTTPException(status_code=502, detail={
            "message": "The support response was generated, but the spoken audio could not be verified. Please retry.",
            "error": "invalid_tts_output",
            "transcription": result.get("transcription"),
            "response": result.get("response_text"),
        })
    return {
        "transcription": result.get("transcription") or "",
        "response": result.get("response_text") or "",
        "decision": result.get("decision", "answer"),
        "sources": result.get("retrieved_sources", []),
        "tool_calls": result.get("tool_calls", []),
        "audio_url": f"/outputs/{output_name}",
    }

@app.post("/api/reset")
def reset(payload: dict):
    session_id = str(payload.get("session_id", ""))[:100]
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    agent.conversations.reset(session_id)
    return {"reset": True}
