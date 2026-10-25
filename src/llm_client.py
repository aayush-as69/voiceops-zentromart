"""Small OpenAI-compatible chat client with explicit missing-credential failures."""
from __future__ import annotations
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

class ChatClient:
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
        kwargs = {"api_key": self.settings.llm_api_key}
        if self.settings.llm_base_url:
            kwargs["base_url"] = self.settings.llm_base_url
        self._client = OpenAI(**kwargs)
        return self._client

    def complete(self, *, system: str, user: str, temperature: float = 0.0) -> LLMResult:
        client = self._get_client()
        try:
            result = client.chat.completions.create(
                model=self.settings.llm_model,
                temperature=temperature,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            )
        except Exception as exc:
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
