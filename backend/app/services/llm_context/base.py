"""ContextRequest + ContextProvider Protocol.

Single dataclass carries everything a provider could possibly need; each provider
picks what it cares about and ignores the rest.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy.orm import Session


PURPOSE_CHAT = "chat"                          # resume copilot chat turn
PURPOSE_RERANK_JOB = "rerank_job"              # per-job context inside recommendation rerank
PURPOSE_INTERVIEW_QUESTION = "interview_question"   # mock interview question generation
PURPOSE_INTERVIEW_SCORE = "interview_score"    # mock interview report scoring

KNOWN_PURPOSES = {
    PURPOSE_CHAT,
    PURPOSE_RERANK_JOB,
    PURPOSE_INTERVIEW_QUESTION,
    PURPOSE_INTERVIEW_SCORE,
}


@dataclass
class ContextRequest:
    """Generic context bag passed to providers.

    Most fields are optional — each gateway populates only what it has, and
    providers MUST tolerate missing fields rather than crashing.
    """
    purpose: str
    db: Session
    user_question: str = ""
    target_job: str = ""
    user_key: str = ""              # for student-memory providers (account_memory.user_key)
    profile: dict | None = None
    preferences: dict | None = None
    # For per-job (PURPOSE_RERANK_JOB):
    job: dict | None = None
    # Escape hatch for future feature-specific data (memory ids, skill flags…).
    extras: dict[str, Any] = field(default_factory=dict)


class ContextProvider(Protocol):
    """Interface every knowledge source implements.

    name: stable identifier used for logging and ENV-flag toggling.
    applies_to: cheap pre-check (no I/O); returns False to skip silently.
    fetch: do the actual retrieval + formatting; return "" to contribute nothing.
    Failures inside fetch are caught by the registry — never bubble up.
    """

    name: str

    def applies_to(self, req: ContextRequest) -> bool: ...

    def fetch(self, req: ContextRequest) -> str: ...
