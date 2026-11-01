"""Small OpenAI-compatible chat client with explicit missing-credential failures."""
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Any
from .config import Settings

class LLMConfigurationError(RuntimeError):
    pass

@dataclass
class LLMResult:
    text: str
    model: str
    usage: dict[str, Any] | None = None

_RETRYABLE_NAMES = ("ratelimit", "apiconnection", "apitimeout", "internalserver", "timeout", "connectionerror")


def _is_transient(exc: BaseException) -> bool:
    """True for rate limits, timeouts, connection problems and 5xx errors worth retrying."""
    node, seen = exc, set()
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        if any(marker in type(node).__name__.casefold() for marker in _RETRYABLE_NAMES):
            return True
        status = getattr(node, "status_code", None)
        try:
            status = int(status) if status is not None else None
        except (TypeError, ValueError):
            status = None
        if status in (408, 409, 425, 429) or (status is not None and 500 <= status <= 599):
            return True
        node = node.__cause__ or node.__context__
    return False


class ChatClient:
    # Live demos and batch runs hit provider rate limits; retry briefly instead of failing the turn.
    MAX_ATTEMPTS = 4
    BASE_DELAY = 1.5
    REQUEST_TIMEOUT = 45.0

    def __init__(self, settings: Settings | None = None, client: Any = None):
        self.settings = settings or Settings.from_env()
        self._client = client

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.settings.llm_api_key:
            raise LLMConfigurationError(
                "LLM is not configured. Set LLM_API_KEY and LLM_MODEL in your environment. "
                "No generated answer has been produced."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMConfigurationError("Install the 'openai' package from requirements.txt.") from exc
        kwargs = {"api_key": self.settings.llm_api_key, "timeout": self.REQUEST_TIMEOUT, "max_retries": 0}
        if self.settings.llm_base_url:
            kwargs["base_url"] = self.settings.llm_base_url
        self._client = OpenAI(**kwargs)
        return self._client

    def complete(self, *, system: str, user: str, temperature: float = 0.0) -> LLMResult:
        client = self._get_client()
        result = None
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                result = client.chat.completions.create(
                    model=self.settings.llm_model,
                    temperature=temperature,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                )
                break
            except Exception as exc:
                if attempt < self.MAX_ATTEMPTS and _is_transient(exc):
                    time.sleep(self.BASE_DELAY * (2 ** (attempt - 1)))
                    continue
                # Upstream exception details may contain request metadata; keep user-facing errors generic.
                raise RuntimeError(f"LLM request failed ({type(exc).__name__}). Check provider configuration and connectivity.") from exc
        text = (result.choices[0].message.content or "").strip()
        usage_obj = getattr(result, "usage", None)
        usage = None
        if usage_obj:
            usage = {
                "prompt_tokens": getattr(usage_obj, "prompt_tokens", None),
                "completion_tokens": getattr(usage_obj, "completion_tokens", None),
                "total_tokens": getattr(usage_obj, "total_tokens", None),
            }
        return LLMResult(text=text, model=self.settings.llm_model, usage=usage)
