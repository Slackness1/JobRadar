"""LLM-driven rubric scoring for one interview answer.

The scoring rubric comes from the chip's nowcoder summary (passed in as
chip_summary). Q5-pattern hardening: any failure (network, malformed JSON,
non-dict response, missing fields) returns ScoreResult.empty() rather than
raising — the orchestrator never gets a 500 from this module.

Optional ContextProvider integration: when ``db`` is passed, score_answer
runs the LLM-Context Registry (purpose=INTERVIEW_SCORE) and appends the
returned blocks + a personalization directive to SCORING_SYSTEM, so the
LLM can produce student-specific feedback (e.g. "未联用 [中金白酒实习]")
instead of generic 6 维 misses. db=None preserves byte-identical behavior
for existing call sites + tests.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Protocol

from app.services.interview.prompts import (
    SCORING_PERSONALIZATION_DIRECTIVE,
    SCORING_SYSTEM,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class _LLMClient(Protocol):
    def chat_json(self, system: str, user: str, **kwargs) -> object: ...


@dataclass(slots=True)
class ScoreResult:
    overall: int | None = None
    hits: list[str] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)
    bonuses: list[str] = field(default_factory=list)
    # 2026-05-20: 5 维独立打分 (job_fit / info_selection / logic /
    # industry_sense / credibility), 0-10 分 + evidence + reason。
    # 旧调用方不传 → None, 完全向后兼容。
    dim_scores: list[dict] | None = None

    @classmethod
    def empty(cls) -> "ScoreResult":
        return cls()

    def to_json(self) -> str:
        out = {
            "overall": self.overall,
            "hits": self.hits,
            "misses": self.misses,
            "bonuses": self.bonuses,
        }
        if self.dim_scores is not None:
            out["dim_scores"] = self.dim_scores
        return json.dumps(out, ensure_ascii=False)


# 5 维 id → 中文 name 表 (与 SCORING_SYSTEM / report.py 对齐)
DIM_ID_TO_NAME: dict[str, str] = {
    "job_fit": "岗位能力匹配度",
    "info_selection": "信息选取与侧重",
    "logic": "逻辑性",
    "industry_sense": "行业感",
    "credibility": "可信度",
}


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


def _clamp_dim_score(value) -> int | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(10, n))


def _coerce_dim_scores(value) -> list[dict] | None:
    """Parse the 5-dim list. Drop bad entries; keep partial if at least 1 valid.

    Returns None when LLM didn't produce dim_scores (legacy path / failure) so
    that old callers that only look at overall/hits/misses stay byte-identical.
    """
    if not isinstance(value, list):
        return None
    out: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        dim_id = item.get("id")
        if not isinstance(dim_id, str) or dim_id not in DIM_ID_TO_NAME:
            continue
        score = _clamp_dim_score(item.get("score"))
        if score is None:
            continue
        out.append({
            "id": dim_id,
            "name": DIM_ID_TO_NAME[dim_id],
            "score": score,
            "evidence": _string_list(item.get("evidence"), cap=4),
            "reason": (item.get("reason") or "").strip()[:300],
        })
    return out or None


def _build_system_prompt(
    db: "Optional[Session]",
    target_job: str,
    user_key: str,
    profile: Optional[dict],
    preferences: Optional[dict],
) -> str:
    """SCORING_SYSTEM + optional context blocks + personalization directive.

    db=None → returns SCORING_SYSTEM unchanged (test/legacy path).
    Provider failures are logged inside fetch_blocks and swallowed; we get
    back fewer blocks but never raise.
    """
    if db is None:
        return SCORING_SYSTEM

    from app.services.llm_context import fetch_blocks
    from app.services.llm_context.base import PURPOSE_INTERVIEW_SCORE, ContextRequest

    req = ContextRequest(
        purpose=PURPOSE_INTERVIEW_SCORE,
        db=db,
        target_job=target_job,
        user_key=user_key or "",
        profile=profile,
        preferences=preferences,
    )
    try:
        blocks = fetch_blocks(req)
    except Exception as exc:
        logger.warning("fetch_blocks for scoring failed: %s", exc)
        blocks = []

    if not blocks:
        return SCORING_SYSTEM
    return (
        SCORING_SYSTEM
        + "\n\n## 额外上下文 (来自智库 / 学生记忆)\n\n"
        + "\n\n".join(blocks)
        + "\n\n"
        + SCORING_PERSONALIZATION_DIRECTIVE
    )


def score_answer(
    target_job: str,
    question: str,
    user_answer: str,
    chip_summary: str,
    llm: _LLMClient,
    *,
    db: "Optional[Session]" = None,
    user_key: str = "",
    profile: Optional[dict] = None,
    preferences: Optional[dict] = None,
) -> ScoreResult:
    """Score one user answer against the rubric. Never raises.

    db (kw-only, optional): when provided, enables ContextProvider injection
    + personalization directive — see module docstring. Existing callers
    that omit it get byte-identical behavior to the pre-Phase-D path.
    """
    user_payload = json.dumps({
        "target_job": target_job,
        "question": question,
        "user_answer": user_answer,
        "chip_summary": chip_summary,
    }, ensure_ascii=False)

    system_prompt = _build_system_prompt(db, target_job, user_key, profile, preferences)

    try:
        raw = llm.chat_json(system=system_prompt, user=user_payload)
    except Exception as exc:
        logger.warning("scoring LLM call failed: %s", exc)
        return ScoreResult.empty()

    if not isinstance(raw, dict):
        logger.warning("scoring LLM returned non-dict (%s)", type(raw).__name__)
        return ScoreResult.empty()

    dim_scores = _coerce_dim_scores(raw.get("dim_scores"))
    overall = _clamp_overall(raw.get("overall"))
    # 如果 LLM 给了 dim_scores 但 overall 缺失/不合法, 用 mean(dim) * 10 兜底
    if overall is None and dim_scores:
        overall = round(sum(d["score"] for d in dim_scores) * 10 / len(dim_scores))

    return ScoreResult(
        overall=overall,
        hits=_string_list(raw.get("hits"), cap=5),
        misses=_string_list(raw.get("misses"), cap=4),
        bonuses=_string_list(raw.get("bonuses"), cap=3),
        dim_scores=dim_scores,
    )
