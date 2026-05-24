"""Low-level XHS retrieval helpers — mirror podcasts.context for use in provider."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.xhs import retrieve


def fetch_for_chat(
    db: Session,
    user_question: str,
    *,
    sectors: list[str] | None = None,
    roles: list[str] | None = None,
    k: int = 3,
) -> list[dict]:
    """Resume copilot chat: balanced types from XHS, fall back to pure semantic if filter empties."""
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
            results = retrieve.search(db, query=user_question, min_confidence="med", limit=k)
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
    """Per-job XHS context — XHS shines on company anecdote / culture / actual interview rounds."""
    query_parts = [p for p in [company, job_title, track_label, "校招 实习 面试"] if p]
    if not query_parts:
        return []
    try:
        return retrieve.search(
            db,
            query=" ".join(query_parts),
            types=["company_anecdote", "role_insight", "industry_trend"],
            min_confidence="med",
            limit=k,
        )
    except Exception:
        return []


def fetch_for_interview(
    db: Session,
    *,
    target_job: str,
    purpose: str = "questions",
    k: int = 5,
) -> list[dict]:
    """Mock interview question gen or scoring — XHS interview_qa is gold for this."""
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
    speaker_map = {"author": "帖主", "commenter": "评论区", "unknown": "?"}
    for r in insights:
        src = r.get("source") or {}
        cite = f"《小红书 · {(src.get('title') or '?')[:30]}》"
        speaker = speaker_map.get(r.get("speaker", ""), r.get("speaker", "?"))
        lines.append(f"- {r['content']} —— {speaker}观点（{cite}）")
    return "\n".join(lines)
