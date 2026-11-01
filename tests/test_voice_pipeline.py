import json
from dataclasses import replace
from pathlib import Path

from src.config import Settings
from src.voice_pipeline import VoicePipeline
from src.agent import AgentResponse


def _settings():
    return replace(Settings.from_env(), gnani_api_key='test-only', llm_api_key='test-only')


def _input_file(tmp_path, suffix='.wav'):
    path = tmp_path / f'customer{suffix}'
    path.write_bytes(b'RIFF' + (36).to_bytes(4, 'little') + b'WAVE' + b'\x00' * 24)
    return path


class FakeSTT:
    def __init__(self, transcript='Where is my order?', error=None):
        self.transcript, self.error, self.calls = transcript, error, 0
    def transcribe(self, path):
        self.calls += 1
        if self.error: raise self.error
        return self.transcript


class FakeTTS:
    def __init__(self, error=None, audio=None):
        self.error, self.audio, self.calls, self.texts = error, audio, 0, []
    def synthesize(self, text, output_path):
        self.calls += 1; self.texts.append(text)
        if self.error: raise self.error
        data = self.audio or (b'RIFF' + (36).to_bytes(4, 'little') + b'WAVE' + b'\x00' * 24)
        Path(output_path).write_bytes(data)
        return Path(output_path)


class FakeAgent:
    def __init__(self, response=None):
        self.response = response or AgentResponse('Your order is being checked.', decision='answer')
        self.calls = []
    def respond(self, message, session_id='default'):
        self.calls.append((message, session_id))
        return self.response


def test_voice_pipeline_runs_stt_agent_tts_and_writes_actual_wav_and_manifest(tmp_path):
    audio = _input_file(tmp_path)
    out_dir = tmp_path / 'out'
    stt, tts, agent = FakeSTT(), FakeTTS(), FakeAgent()
    result = VoicePipeline(agent, _settings(), stt=stt, tts=tts).process_file(audio, out_dir, 'session-1')
    assert result['status'] == 'success'
    assert result['transcription'] == 'Where is my order?'
    assert result['response_text'] == 'Your order is being checked.'
    assert stt.calls == 1 and len(agent.calls) == 1 and tts.calls == 1
    generated = out_dir / result['output_audio_filename']
    assert generated.is_file() and generated.read_bytes()[:12][0:4] == b'RIFF'
    manifest = json.loads((out_dir / result['result_json_filename']).read_text(encoding='utf-8'))
    assert manifest['status'] == 'success' and manifest['output_audio_filename'] == generated.name


def test_voice_pipeline_empty_transcript_asks_repeat_and_never_calls_agent(tmp_path):
    audio = _input_file(tmp_path); out_dir = tmp_path / 'out'
    stt, tts, agent = FakeSTT(transcript=''), FakeTTS(), FakeAgent()
    result = VoicePipeline(agent, _settings(), stt=stt, tts=tts).process_file(audio, out_dir, 'session-2')
    assert result['status'] == 'success'
    assert result['transcription'] == ''
    assert 'repeat' in result['response_text'].lower()
    assert agent.calls == [] and tts.calls == 1


def test_voice_pipeline_stt_failure_does_not_claim_success_or_call_tts(tmp_path):
    audio = _input_file(tmp_path); out_dir = tmp_path / 'out'
    stt, tts, agent = FakeSTT(error=RuntimeError('private provider detail')), FakeTTS(), FakeAgent()
    result = VoicePipeline(agent, _settings(), stt=stt, tts=tts).process_file(audio, out_dir, 'session-3')
    assert result['status'] == 'failed'
    assert result['output_audio_filename'] is None
    assert tts.calls == 0 and agent.calls == []
    assert 'private provider detail' not in json.dumps(result)


def test_voice_pipeline_tts_failure_does_not_claim_success(tmp_path):
    audio = _input_file(tmp_path); out_dir = tmp_path / 'out'
    stt, tts, agent = FakeSTT(), FakeTTS(error=RuntimeError('secret provider response')), FakeAgent()
    result = VoicePipeline(agent, _settings(), stt=stt, tts=tts).process_file(audio, out_dir, 'session-4')
    assert result['status'] == 'failed'
    assert result['output_audio_filename'] is None
    assert not list(out_dir.glob('*_reply.wav'))
    assert 'secret provider response' not in json.dumps(result)


def test_voice_pipeline_agent_error_is_reported_as_partial_failure(tmp_path):
    audio = _input_file(tmp_path); out_dir = tmp_path / 'out'
    stt, tts = FakeSTT(), FakeTTS()
    agent = FakeAgent(AgentResponse('Service temporarily unavailable.', decision='error', ok=False, error='llm_error'))
    result = VoicePipeline(agent, _settings(), stt=stt, tts=tts).process_file(audio, out_dir, 'session-5')
    assert result['status'] == 'partial_failure'
    assert result['agent_error'] == 'llm_error'
    assert tts.calls == 1 and result['output_audio_filename']


def test_voice_pipeline_rejects_unsupported_extension(tmp_path):
    audio = _input_file(tmp_path, '.webm'); out_dir = tmp_path / 'out'
    stt, tts, agent = FakeSTT(), FakeTTS(), FakeAgent()
    result = VoicePipeline(agent, _settings(), stt=stt, tts=tts).process_file(audio, out_dir, 'session-6')
    assert result['status'] == 'failed'
    assert stt.calls == 0 and tts.calls == 0 and agent.calls == []
