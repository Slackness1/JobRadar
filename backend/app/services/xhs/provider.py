"""XhsContextProvider — feeds XHS knowledge into LLM prompts.

Single class handles all 4 purposes via dispatch on req.purpose. Mirrors
PodcastContextProvider; the two are complementary:
- Podcast: long-form 嘉宾深度访谈, slow signals about career arcs / sector cycles
- XHS:    short-form 个人帖 + 评论, fresh signals about live interview rounds /
          实习日记 / specific company anecdote in current cycle
"""
from __future__ import annotations

from app.services.llm_context.base import (
    KNOWN_PURPOSES,
    PURPOSE_CHAT,
    PURPOSE_INTERVIEW_QUESTION,
    PURPOSE_INTERVIEW_SCORE,
    PURPOSE_RERANK_JOB,
    ContextRequest,
)
from app.services.xhs.context import (
    fetch_for_chat,
    fetch_for_interview,
    fetch_for_job,
    format_block,
)


class XhsContextProvider:
    name = "xhs"

    def applies_to(self, req: ContextRequest) -> bool:
        return req.purpose in KNOWN_PURPOSES

    def fetch(self, req: ContextRequest) -> str:
        if req.purpose == PURPOSE_CHAT:
            sectors = (req.preferences or {}).get("preferred_tracks") or None
            roles = (req.preferences or {}).get("preferred_roles") or None
            insights = fetch_for_chat(req.db, req.user_question, sectors=sectors, roles=roles, k=3)
            return format_block(insights, header="来自小红书的相关一手分享")

        if req.purpose == PURPOSE_RERANK_JOB:
            job = req.job or {}
            insights = fetch_for_job(
                req.db,
                company=str(job.get("company") or ""),
                job_title=str(job.get("title") or ""),
                track_label=str(job.get("track_label") or ""),
                k=2,
            )
            return format_block(insights, header="本岗位相关小红书一手信息")

        if req.purpose == PURPOSE_INTERVIEW_QUESTION:
            insights = fetch_for_interview(req.db, target_job=req.target_job, purpose="questions", k=4)
            block = format_block(insights, header="来自小红书的近期面试真题 / 岗位认知")
            if not block:
                return ""
            return (
                block
                + "\n\n（以上是真实候选人在近期校招/实习面试里遇到的，"
                "可作为出题角度，但**不要照搬原话**，要改写。）"
            )

        if req.purpose == PURPOSE_INTERVIEW_SCORE:
            insights = fetch_for_interview(req.db, target_job=req.target_job, purpose="scoring", k=3)
            block = format_block(insights, header="评分参照：来自小红书的'同期候选人' 表现 / 反例")
            if not block:
                return ""
            return (
                block
                + "\n\n请将以上作为同辈水平的参照（'对比同期候选人'）。"
                "highlights / improvements 可以引用，禁止编造。"
            )

        return ""
