from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_template_exposes_accessible_microphone_controls_and_preview():
    html = (ROOT / 'templates' / 'index.html').read_text(encoding='utf-8')
    for token in ('id="recordButton"', 'id="stopButton"', 'id="sendRecordingButton"',
                  'id="discardRecordingButton"', 'id="recordingPreview"',
                  'id="recordingTimer"', 'id="voiceStatus"', 'aria-live="polite"'):
        assert token in html


def test_browser_recorder_uses_real_capture_and_builds_wav_not_a_renamed_webm():
    js = (ROOT / 'static' / 'app.js').read_text(encoding='utf-8')
    assert 'navigator.mediaDevices.getUserMedia' in js
    assert 'new MediaRecorder' in js
    assert 'encodeWavMono16' in js
    assert "type: 'audio/wav'" in js
    assert "form.append('audio', file, file.name" in js
    assert 'stop()' in js and 'getTracks()' in js
