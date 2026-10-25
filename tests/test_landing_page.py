from pathlib import Path

from fastapi.testclient import TestClient

import app as app_module

ROOT = Path(__file__).resolve().parents[1]


def test_home_renders_landing_page_and_preserves_support_workspace():
    response = TestClient(app_module.app).get("/")
    assert response.status_code == 200
    html = response.text
    for required_id in (
        'id="landingPage"',
        'id="supportApp"',
        'id="startVoiceButton"',
        'id="startChatButton"',
        'id="recordButton"',
        'id="chatForm"',
    ):
        assert required_id in html
    assert 'id="supportApp" hidden' in html


def test_landing_page_ctas_open_existing_chat_and_voice_workspace():
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    assert "startVoiceButton" in js and "enterSupport('voice')" in js
    assert "startChatButton" in js and "enterSupport('chat')" in js
    assert "landing-page" in css
    assert "@media(max-width:680px)" in css
