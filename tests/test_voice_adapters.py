from dataclasses import replace
from pathlib import Path
from src.config import Settings
from src.gnani_stt import GnaniSTT
from src.gnani_tts import GnaniTTS

class STTClient:
    def transcribe(self, path, language_code): return {'transcript':'What is the return window?'}
class TTSClient:
    def synthesize(self, text, voice, model, language): return b'RIFF'+(40).to_bytes(4,'little')+b'WAVE'+b'\x00'*24

def test_stt_and_tts_adapters_with_mocks(tmp_path):
    settings=replace(Settings.from_env(),gnani_api_key='test-only')
    audio=tmp_path/'input.wav';audio.write_bytes(b'fake input')
    assert GnaniSTT(settings,STTClient()).transcribe(audio)=='What is the return window?'
    out=GnaniTTS(settings,TTSClient()).synthesize('Hello there',tmp_path/'reply.wav')
    assert out.exists() and out.stat().st_size>0
