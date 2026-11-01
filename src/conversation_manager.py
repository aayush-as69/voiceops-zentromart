"""In-memory, per-session conversation state. Do not persist verification secrets."""
from __future__ import annotations
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

@dataclass
class ConversationState:
    session_id: str
    history: list[dict[str, str]] = field(default_factory=list)
    introduced: bool = False
    pending_order_id: str | None = None
    verification_attempts: int = 0
    verified_order: dict[str, Any] | None = None
    pending_issue: str = ""
    last_intent: str = ""
    escalation_required: bool = False

class ConversationManager:
    def __init__(self):
        self._sessions: dict[str, ConversationState] = {}
        self._lock = RLock()

    def get(self, session_id: str) -> ConversationState:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = ConversationState(session_id=session_id)
            return self._sessions[session_id]

    def reset(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def add_turn(self, state: ConversationState, user: str, assistant: str) -> None:
        state.history.extend([{"role": "user", "content": user}, {"role": "assistant", "content": assistant}])
        # Bound memory per session while retaining enough context for follow-ups.
        if len(state.history) > 24:
            state.history = state.history[-24:]
