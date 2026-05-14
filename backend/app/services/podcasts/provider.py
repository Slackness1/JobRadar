"""ContextProvider that feeds podcast knowledge into LLM prompts.

Single class handles all 4 purposes via dispatch on req.purpose.
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
from app.services.podcasts.context import (
    fetch_for_chat,
    fetch_for_interview,
    fetch_for_job,
    format_block,
)


class PodcastContextProvider:
    name = "podcast"

    def applies_to(self, req: ContextRequest) -> bool:
        return req.purpose in KNOWN_PURPOSES

    def fetch(self, req: ContextRequest) -> str:
        if req.purpose == PURPOSE_CHAT:
            sectors = (req.preferences or {}).get("preferred_tracks") or None
            roles = (req.preferences or {}).get("preferred_roles") or None
            insights = fetch_for_chat(req.db, req.user_question, sectors=sectors, roles=roles, k=3)
            return format_block(insights, header="来自播客知识库的相关洞察")

        if req.purpose == PURPOSE_RERANK_JOB:
            job = req.job or {}
            insights = fetch_for_job(
                req.db,
                company=str(job.get("company") or ""),
                job_title=str(job.get("title") or ""),
                track_label=str(job.get("track_label") or ""),
                k=2,
            )
            return format_block(insights, header="本岗位相关播客洞察")

        if req.purpose == PURPOSE_INTERVIEW_QUESTION:
            insights = fetch_for_interview(req.db, target_job=req.target_job, purpose="questions", k=5)
            block = format_block(insights, header="来自金融播客的真实面试经验 + 岗位认知")
            if not block:
                return ""
            return (
                block
                + "\n\n（以上是真实从业者讨论过的考察点，可作为出题角度，但**不要照搬原话**，"
                "要改写成自己的提问方式。）"
            )

        if req.purpose == PURPOSE_INTERVIEW_SCORE:
            insights = fetch_for_interview(req.db, target_job=req.target_job, purpose="scoring", k=4)
            block = format_block(insights, header="评分参照：来自金融播客的'优秀候选人'参考标准")
            if not block:
                return ""
            return (
                block
                + "\n\n请将以上洞察作为打分参照（'对标真实从业者认为的好'），"
                "highlights 与 improvements 字段可以引用洞察里的判断作为依据，但禁止编造。"
            )

        return ""
