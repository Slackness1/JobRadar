"""Low-level retrieval helpers for podcast knowledge.

Wraps `services.podcasts.retrieve.search` with use-case-specific defaults
(types / confidence / formatting). Pure functions — no provider abstraction
here, that lives in `provider.py`.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.podcasts import retrieve


def fetch_for_chat(
    db: Session,
    user_question: str,
    *,
    sectors: list[str] | None = None,
    roles: list[str] | None = None,
    k: int = 3,
) -> list[dict]:
    """Resume copilot chat: balanced types, fall back to pure semantic if filter empties."""
    if not (user_question or "").strip():
        return []
    try:
        results = retrieve.search(
            db,
            query=user_question,
            sector=sectors or None,
            role=roles or None,
            min_confidence="med",
            limit=k,
        )
        if not results and (sectors or roles):
            results = retrieve.search(
                db,
                query=user_question,
                min_confidence="med",
                limit=k,
            )
        return results
    except Exception:
        return []


def fetch_for_job(
    db: Session,
    *,
    company: str,
    job_title: str,
    track_label: str = "",
    k: int = 2,
) -> list[dict]:
    """Per-job context inside recommendation rerank.

    Pure semantic search (job-company names rarely match canonical dict).
    Restricted to role_insight / company_anecdote / industry_trend
    (interview_qa + resume_tip belong to other consumers).
    """
    query_parts = [p for p in [company, job_title, track_label, "岗位职责 求职建议"] if p]
    if not query_parts:
        return []
    try:
        return retrieve.search(
            db,
            query=" ".join(query_parts),
            types=["role_insight", "company_anecdote", "industry_trend"],
            min_confidence="med",
            limit=k,
        )
    except Exception:
        return []


def fetch_for_interview(
    db: Session,
    *,
    target_job: str,
    purpose: str = "questions",  # "questions" or "scoring"
    k: int = 5,
) -> list[dict]:
    """Mock interview question generation or report scoring.

    questions: prioritize interview_qa + role_insight (real exam questions + 岗位认知)
    scoring:   prioritize role_insight + resume_tip + industry_trend
    """
    if not (target_job or "").strip():
        return []
    types = (
        ["interview_qa", "role_insight"]
        if purpose == "questions"
        else ["role_insight", "resume_tip", "industry_trend"]
    )
    try:
        return retrieve.search(
            db,
            query=target_job,
            types=types,
            min_confidence="med",
            limit=k,
        )
    except Exception:
        return []


def format_block(insights: list[dict], *, header: str) -> str:
    """Compact prompt-ready block with citation footer per line."""
    if not insights:
        return ""
    lines = [f"[{header}]"]
    for r in insights:
        src = r.get("source") or {}
        cite = f"《{src.get('show', '?')} · {(src.get('title') or '?')[:40]}》"
        speaker = {"guest": "嘉宾", "host": "主持人", "unknown": "?"}.get(
            r.get("speaker", ""), r.get("speaker", "?")
        )
        lines.append(f"- {r['content']} —— {speaker}观点（{cite}）")
    return "\n".join(lines)


def format_per_job_block(by_job_id: dict[str, list[dict]]) -> str:
    """Compact per-job block for recommendation rerank prompt."""
    if not by_job_id:
        return ""
    lines = ["[每个岗位附带的播客洞察 — 用来辅助 final_score / strengths / risks 的判断]"]
    for job_id, insights in by_job_id.items():
        if not insights:
            continue
        lines.append(f"\njob_id={job_id}:")
        for r in insights:
            src = r.get("source") or {}
            cite = f"《{src.get('show', '?')} · {(src.get('title') or '?')[:30]}》"
            lines.append(f"  · {r['content'][:140]} ({cite})")
    return "\n".join(lines)
