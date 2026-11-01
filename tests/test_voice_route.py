import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as app_module
from src.voice_pipeline import MAX_AUDIO_BYTES


def valid_wav_bytes() -> bytes:
    # Minimal WAV-shaped test payload; the route signature check is exercised,
    # while the mocked VoicePipeline avoids sending test bytes to live Gnani.
    return b"RIFF" + (36).to_bytes(4, "little") + b"WAVE" + b"fmt " + b"\x00" * 24


@pytest.fixture
def client():
    return TestClient(app_module.app)


def install_pipeline_stub(monkeypatch, tmp_path, result=None, error=None):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    monkeypatch.setattr(app_module, "OUTPUT_DIR", output_dir)
    observed = {}
    class StubPipeline:
        def __init__(self, agent, settings):
            if error:
                raise error
        def process_file(self, audio_path, out_dir, session_id):
            observed["path"] = Path(audio_path)
            observed["bytes"] = Path(audio_path).read_bytes()
            observed["session_id"] = session_id
            if result is None:
                return {"status": "success", "transcription": "hello", "response_text": "Hi there",
                        "decision": "answer", "retrieved_sources": [], "tool_calls": [],
                        "output_audio_filename": "stub_reply.wav"}
            return result
    monkeypatch.setattr(app_module, "VoicePipeline", StubPipeline)
    return observed, output_dir


def test_voice_route_accepts_valid_wav_and_cleans_temporary_file(client, monkeypatch, tmp_path):
    observed, out_dir = install_pipeline_stub(monkeypatch, tmp_path)
    (out_dir / "stub_reply.wav").write_bytes(valid_wav_bytes())
    response = client.post("/api/voice", data={"session_id": "browser-session_1"},
                           files={"audio": ("recording.wav", valid_wav_bytes(), "audio/wav")})
    assert response.status_code == 200
    body = response.json()
    assert body["transcription"] == "hello" and body["response"] == "Hi there"
    assert body["audio_url"] == "/outputs/stub_reply.wav"
    assert observed["bytes"] == valid_wav_bytes()
    assert observed["session_id"] == "browser-session_1"
    assert not observed["path"].exists()


def test_voice_route_rejects_empty_audio(client, monkeypatch, tmp_path):
    install_pipeline_stub(monkeypatch, tmp_path)
    response = client.post("/api/voice", data={"session_id": "s1"},
                           files={"audio": ("empty.wav", b"", "audio/wav")})
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_voice_route_rejects_unsupported_extension(client, monkeypatch, tmp_path):
    install_pipeline_stub(monkeypatch, tmp_path)
    response = client.post("/api/voice", data={"session_id": "s1"},
                           files={"audio": ("recording.webm", b"webm", "audio/webm")})
    assert response.status_code == 400
    assert "unsupported audio format" in response.json()["detail"].lower()


def test_voice_route_rejects_content_type_mismatch(client, monkeypatch, tmp_path):
    install_pipeline_stub(monkeypatch, tmp_path)
    response = client.post("/api/voice", data={"session_id": "s1"},
                           files={"audio": ("recording.wav", valid_wav_bytes(), "text/plain")})
    assert response.status_code == 415
    assert "content type" in response.json()["detail"].lower()


def test_voice_route_rejects_invalid_audio_signature(client, monkeypatch, tmp_path):
    install_pipeline_stub(monkeypatch, tmp_path)
    response = client.post("/api/voice", data={"session_id": "s1"},
                           files={"audio": ("recording.wav", b"not really a wav file", "audio/wav")})
    assert response.status_code == 415
    assert "valid audio" in response.json()["detail"].lower()


def test_voice_route_rejects_oversized_audio(client, monkeypatch, tmp_path):
    install_pipeline_stub(monkeypatch, tmp_path)
    oversized = b"RIFF" + (36).to_bytes(4, "little") + b"WAVE" + b"\x00" * MAX_AUDIO_BYTES
    response = client.post("/api/voice", data={"session_id": "s1"},
                           files={"audio": ("recording.wav", oversized, "audio/wav")})
    assert response.status_code == 413


def test_voice_route_rejects_empty_session_id(client, monkeypatch, tmp_path):
    install_pipeline_stub(monkeypatch, tmp_path)
    response = client.post("/api/voice", data={"session_id": ""},
                           files={"audio": ("recording.wav", valid_wav_bytes(), "audio/wav")})
    assert response.status_code == 400


def test_voice_route_does_not_claim_success_if_output_audio_missing(client, monkeypatch, tmp_path):
    result = {"status": "success", "transcription": "hello", "response_text": "Hi",
              "decision": "answer", "retrieved_sources": [], "tool_calls": [],
              "output_audio_filename": "missing.wav"}
    install_pipeline_stub(monkeypatch, tmp_path, result=result)
    response = client.post("/api/voice", data={"session_id": "s1"},
                           files={"audio": ("recording.wav", valid_wav_bytes(), "audio/wav")})
    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "invalid_tts_output"


def test_voice_route_sanitizes_pipeline_setup_error(client, monkeypatch, tmp_path):
    install_pipeline_stub(monkeypatch, tmp_path, error=RuntimeError("sensitive provider detail"))
    response = client.post("/api/voice", data={"session_id": "s1"},
                           files={"audio": ("recording.wav", valid_wav_bytes(), "audio/wav")})
    assert response.status_code == 502
    assert "sensitive provider detail" not in response.text
