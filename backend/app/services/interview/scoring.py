"""LLM-driven rubric scoring for one interview answer.

The scoring rubric comes from the chip's nowcoder summary (passed in as
chip_summary). Q5-pattern hardening: any failure (network, malformed JSON,
non-dict response, missing fields) returns ScoreResult.empty() rather than
raising — the orchestrator never gets a 500 from this module.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Protocol

from app.services.interview.prompts import SCORING_SYSTEM

logger = logging.getLogger(__name__)


class _LLMClient(Protocol):
    def chat_json(self, system: str, user: str, **kwargs) -> object: ...


@dataclass(slots=True)
class ScoreResult:
    overall: int | None = None
    hits: list[str] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)
    bonuses: list[str] = field(default_factory=list)

    @classmethod
    def empty(cls) -> "ScoreResult":
        return cls()

    def to_json(self) -> str:
        return json.dumps({
            "overall": self.overall,
            "hits": self.hits,
            "misses": self.misses,
            "bonuses": self.bonuses,
        }, ensure_ascii=False)


def _string_list(value, cap: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out[:cap]


def _clamp_overall(value) -> int | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(100, n))


def score_answer(
    target_job: str,
    question: str,
    user_answer: str,
    chip_summary: str,
    llm: _LLMClient,
) -> ScoreResult:
    """Score one user answer against the rubric. Never raises."""
    user_payload = json.dumps({
        "target_job": target_job,
        "question": question,
        "user_answer": user_answer,
        "chip_summary": chip_summary,
    }, ensure_ascii=False)

    try:
        raw = llm.chat_json(system=SCORING_SYSTEM, user=user_payload)
    except Exception as exc:
        logger.warning("scoring LLM call failed: %s", exc)
        return ScoreResult.empty()

    if not isinstance(raw, dict):
        logger.warning("scoring LLM returned non-dict (%s)", type(raw).__name__)
        return ScoreResult.empty()

    return ScoreResult(
        overall=_clamp_overall(raw.get("overall")),
        hits=_string_list(raw.get("hits"), cap=5),
        misses=_string_list(raw.get("misses"), cap=4),
        bonuses=_string_list(raw.get("bonuses"), cap=3),
    )
