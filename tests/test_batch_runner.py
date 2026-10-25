import json
import sys
from pathlib import Path

import run


def test_missing_configuration_writes_a_failure_record_for_every_audio(tmp_path, monkeypatch):
    audio_dir = tmp_path / "audio"
    out_dir = tmp_path / "out"
    audio_dir.mkdir()
    (audio_dir / "call_01.wav").write_bytes(b"not-real-audio-but-a-discovered-input")
    (audio_dir / "readme.txt").write_text("unsupported", encoding="utf-8")
    monkeypatch.setenv("DATASET_DIR", str(tmp_path / "missing-dataset"))
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GNANI_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["run.py", "--input-dir", str(audio_dir), "--output-dir", str(out_dir)])

    code = run.main()

    assert code == 2
    summary = json.loads((out_dir / "batch_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "blocked_missing_configuration"
    assert summary["inputs_discovered"] == 1
    assert summary["failed"] == 1
    assert summary["ignored_unsupported_files"] == ["readme.txt"]
    assert len(summary["results"]) == 1
    record = json.loads((out_dir / "call_01_result.json").read_text(encoding="utf-8"))
    assert record["input_filename"] == "call_01.wav"
    assert record["status"] == "blocked_missing_configuration"
    assert record["transcription"] is None
    assert record["output_audio_filename"] is None


def test_empty_audio_directory_does_not_report_success(tmp_path, monkeypatch):
    audio_dir = tmp_path / "audio"
    out_dir = tmp_path / "out"
    audio_dir.mkdir()
    monkeypatch.setattr(sys, "argv", ["run.py", "--input-dir", str(audio_dir), "--output-dir", str(out_dir)])

    code = run.main()

    assert code == 2
    summary = json.loads((out_dir / "batch_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "no_supported_inputs"
    assert summary["succeeded"] == 0
