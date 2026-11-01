from types import SimpleNamespace

import pytest

from src.config import Settings
from src.llm_client import ChatClient


class RateLimitError(Exception):
    status_code = 429


class BadRequestError(Exception):
    status_code = 400


def _ok(text="hello"):
    msg = SimpleNamespace(content=text)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None)


class FakeClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **_):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _client(fake, monkeypatch):
    monkeypatch.setattr("src.llm_client.time.sleep", lambda _s: None)
    return ChatClient(Settings.from_env(), client=fake)


def test_transient_rate_limit_is_retried(monkeypatch):
    fake = FakeClient([RateLimitError("429"), RateLimitError("429"), _ok("done")])
    assert _client(fake, monkeypatch).complete(system="s", user="u").text == "done"
    assert fake.calls == 3


def test_non_transient_error_is_not_retried(monkeypatch):
    fake = FakeClient([BadRequestError("bad")])
    with pytest.raises(RuntimeError, match="LLM request failed"):
        _client(fake, monkeypatch).complete(system="s", user="u")
    assert fake.calls == 1


def test_gives_up_after_max_attempts(monkeypatch):
    fake = FakeClient([RateLimitError("429")] * ChatClient.MAX_ATTEMPTS)
    with pytest.raises(RuntimeError):
        _client(fake, monkeypatch).complete(system="s", user="u")
    assert fake.calls == ChatClient.MAX_ATTEMPTS
