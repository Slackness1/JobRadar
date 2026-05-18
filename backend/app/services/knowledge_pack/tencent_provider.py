"""TencentTrackProvider — surfaces public-智库 rows for Tencent jobs.

Detection:
    1. Employer = Tencent if target_job (or req.job.company) contains
       '腾讯' / 'tencent' / 'Tencent' / 'TX' / 'tx'
    2. Track = first KnowledgeTrack whose alias appears in target_job /
       job title / job description.

Output block (when employer + track both matched):

    [tencent_track · 腾讯 <track 中文名> 视角]
    面试官原话（来自 <attribution>）：
      - "<verbatim 1>"
      - "<verbatim 2>"
    简历评分维度：
      - <dim>: high=<...> / low=<...>
      - ...
    面试评分维度（<stage>）：
      - <dim>: <hint>
    评分参考样例：
      - <example title>

Always read-only. Falls back gracefully (returns "") if no match.
"""
from __future__ import annotations

import json
import logging
from typing import Iterable

from app.models import (
    InterviewerQuote,
    KnowledgeTrack,
    TrackExampleBank,
    TrackInterviewRubric,
    TrackResumeRubric,
)
from app.services.llm_context.base import (
    KNOWN_PURPOSES,
    PURPOSE_INTERVIEW_QUESTION,
    PURPOSE_INTERVIEW_SCORE,
    ContextRequest,
)

logger = logging.getLogger(__name__)


_TENCENT_TOKENS = ("腾讯", "tencent", "Tencent", "TENCENT")
_EMPLOYER_KEY = "tencent"

_MAX_QUOTES = 2
_MAX_RESUME_DIMS = 4
_MAX_INTERVIEW_RUBRICS = 2
_MAX_EXAMPLES = 1


class TencentTrackProvider:
    name = "tencent_track"

    def applies_to(self, req: ContextRequest) -> bool:
        if req.purpose not in KNOWN_PURPOSES:
            return False
        return _looks_tencent(req)

    def fetch(self, req: ContextRequest) -> str:
        track_key = _detect_track(req)
        if not track_key:
            return ""

        track_row = (
            req.db.query(KnowledgeTrack)
            .filter(
                KnowledgeTrack.employer_key == _EMPLOYER_KEY,
                KnowledgeTrack.track_key == track_key,
            )
            .one_or_none()
        )
        track_label = (track_row.display_name if track_row else track_key) or track_key

        quotes = (
            req.db.query(InterviewerQuote)
            .filter(
                InterviewerQuote.employer_key == _EMPLOYER_KEY,
                InterviewerQuote.track_key.in_([track_key, "generic"]),
            )
            .limit(_MAX_QUOTES)
            .all()
        )
        resume_rubrics = (
            req.db.query(TrackResumeRubric)
            .filter(
                TrackResumeRubric.employer_key == _EMPLOYER_KEY,
                TrackResumeRubric.track_key == track_key,
            )
            .limit(_MAX_RESUME_DIMS)
            .all()
        )
        # For interview purposes, prefer 1v1_business + group; for chat / rerank,
        # any stage is acceptable.
        interview_query = req.db.query(TrackInterviewRubric).filter(
            TrackInterviewRubric.employer_key == _EMPLOYER_KEY,
            TrackInterviewRubric.track_key.in_([track_key, "generic"]),
        )
        if req.purpose in (PURPOSE_INTERVIEW_QUESTION, PURPOSE_INTERVIEW_SCORE):
            interview_query = interview_query.filter(
                TrackInterviewRubric.interview_stage.in_(["1v1_business", "group", "hr"])
            )
        interview_rubrics = interview_query.limit(_MAX_INTERVIEW_RUBRICS).all()
        examples = (
            req.db.query(TrackExampleBank)
            .filter(
                TrackExampleBank.employer_key == _EMPLOYER_KEY,
                TrackExampleBank.track_key.in_([track_key, "generic"]),
            )
            .limit(_MAX_EXAMPLES)
            .all()
        )

        if not (quotes or resume_rubrics or interview_rubrics or examples):
            return ""

        return _format_block(
            track_label=track_label,
            quotes=quotes,
            resume_rubrics=resume_rubrics,
            interview_rubrics=interview_rubrics,
            examples=examples,
        )


# ── detection helpers ──────────────────────────────────────────────────────


def _looks_tencent(req: ContextRequest) -> bool:
    candidates: list[str] = []
    if req.target_job:
        candidates.append(req.target_job)
    if req.job:
        for k in ("company", "title", "company_name"):
            v = req.job.get(k) if isinstance(req.job, dict) else None
            if v:
                candidates.append(str(v))
    if req.user_question:
        candidates.append(req.user_question)
    if not candidates:
        return False
    blob = " ".join(candidates).lower()
    return any(t.lower() in blob for t in _TENCENT_TOKENS)


def _detect_track(req: ContextRequest) -> str:
    """Return the first matching track_key, or '' if no track is identifiable.

    Walks all KnowledgeTrack rows for tencent and matches by alias substring.
    Cheap (5 rows seeded) — no need to cache.
    """
    blob_parts: list[str] = []
    if req.target_job:
        blob_parts.append(req.target_job)
    if req.job:
        for k in ("title", "jd_summary", "description"):
            v = req.job.get(k) if isinstance(req.job, dict) else None
            if v:
                blob_parts.append(str(v))
    if req.user_question:
        blob_parts.append(req.user_question)
    blob = " ".join(blob_parts).lower()
    if not blob:
        return ""

    rows = (
        req.db.query(KnowledgeTrack)
        .filter(KnowledgeTrack.employer_key == _EMPLOYER_KEY)
        .all()
    )
    # Prefer specific tracks over the 'generic' fallback.
    for r in rows:
        if r.track_key == "generic":
            continue
        aliases = _safe_loads_list(r.aliases_json)
        # match against display_name + aliases + the key itself
        tokens = [t.lower() for t in (aliases + [r.track_key, r.display_name or ""]) if t]
        if any(tok and tok in blob for tok in tokens):
            return r.track_key
    return ""


def _safe_loads_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        out = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [str(x) for x in out] if isinstance(out, list) else []


# ── formatting ─────────────────────────────────────────────────────────────


def _format_block(
    *,
    track_label: str,
    quotes: Iterable[InterviewerQuote],
    resume_rubrics: Iterable[TrackResumeRubric],
    interview_rubrics: Iterable[TrackInterviewRubric],
    examples: Iterable[TrackExampleBank],
) -> str:
    lines: list[str] = [f"[tencent_track · 腾讯 {track_label} 视角]"]

    quote_lines = []
    for q in quotes:
        attr = (q.attribution or "面试官").strip()
        quote_lines.append(f"  - 「{attr}」: \"{q.quote_verbatim.strip()}\"")
    if quote_lines:
        lines.append("面试官原话（verbatim，禁止改写引用）：")
        lines.extend(quote_lines)

    resume_lines = []
    for r in resume_rubrics:
        dim = (r.dimension or "").strip()
        if not dim:
            continue
        high = (r.high_signal or "").strip()
        low = (r.low_signal or "").strip()
        resume_lines.append(f"  - {dim}: 高分=\"{high}\" / 低分=\"{low}\"")
    if resume_lines:
        lines.append("简历评分维度：")
        lines.extend(resume_lines)

    interview_lines = []
    for r in interview_rubrics:
        stage = (r.interview_stage or "general").strip()
        rubric = (r.rubric_md or "").strip().replace("\n", " ")
        if not rubric:
            continue
        interview_lines.append(f"  - [{stage}] {rubric[:200]}")
    if interview_lines:
        lines.append("面试评分维度：")
        lines.extend(interview_lines)

    example_lines = []
    for e in examples:
        title = (e.title or e.example_type or "").strip()
        commentary = (e.commentary or "").strip()
        if title:
            example_lines.append(f"  - {title}: {commentary[:200]}" if commentary else f"  - {title}")
    if example_lines:
        lines.append("评分参考样例：")
        lines.extend(example_lines)

    return "\n".join(lines)


__all__ = ["TencentTrackProvider"]
