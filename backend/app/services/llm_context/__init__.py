"""Pluggable context-injection layer for LLM prompts.

When several knowledge sources (podcast / tencent skill / student memory / future)
all want to enrich the same LLM call (resume chat / job rerank / interview question
/ interview report), they each become a ContextProvider and register here.

Strangler-fig with existing block builders: gateway code calls fetch_blocks(req)
**alongside** existing hardcoded blocks (e.g. _build_jerry_style_block,
_build_jd_focus_block, _build_track_qa_block in interview/llm.py). New sources
go through this registry; old hardcoded blocks stay until someone wants to
migrate them. No big-bang refactor.

Usage:
    from app.services.llm_context import ContextRequest, fetch_blocks

    req = ContextRequest(purpose="chat", db=db, user_question=msg, profile=p)
    extras = fetch_blocks(req)
    # then concatenate alongside existing hardcoded blocks

Adding a new feature (memory / tencent / etc.):
    1. Implement a class with .name, .applies_to(req), .fetch(req) -> str
    2. Register it inside bootstrap() below
"""
from app.services.llm_context.base import ContextProvider, ContextRequest
from app.services.llm_context.registry import (
    fetch_blocks,
    fetch_blocks_for_jobs,
    format_per_job_aggregated,
    register,
    registered_names,
)


def bootstrap() -> None:
    """Register all enabled providers. Called once from app.main lifespan startup.

    Each provider import + register is independent — failing to register one
    must not block the others. New features add their registration here.

    Registration order is meaningful: SensitiveTopicProvider runs first because
    a hit triggers early-terminate and skips the rest (薪酬/通过率/offer 承诺
    must not get factual context piled on top of the safe template).
    """
    import logging
    log = logging.getLogger(__name__)

    # 1. Sensitive-topic guardrail FIRST (early-terminate on chat hits).
    try:
        from app.services.knowledge_pack.sensitive_provider import SensitiveTopicProvider
        register(SensitiveTopicProvider())
    except Exception as exc:
        log.warning(f"SensitiveTopicProvider register failed: {exc}")

    # 2. Public 智库 (Tencent) — track-perspective rubrics + verbatim quotes.
    try:
        from app.services.knowledge_pack.tencent_provider import TencentTrackProvider
        register(TencentTrackProvider())
    except Exception as exc:
        log.warning(f"TencentTrackProvider register failed: {exc}")

    # 3. Per-student private memory — read-side of unified-memory store.
    try:
        from app.services.memory.provider import StudentMemoryProvider
        register(StudentMemoryProvider())
    except Exception as exc:
        log.warning(f"StudentMemoryProvider register failed: {exc}")

    # 4. Podcast RAG (existing).
    try:
        from app.services.podcasts.provider import PodcastContextProvider
        register(PodcastContextProvider())
    except Exception as exc:
        log.warning(f"PodcastContextProvider register failed: {exc}")

    # 5. XHS RAG (2026-05-19) — 小红书帖子+评论 一手分享, 互补于 podcast 的深度访谈。
    try:
        from app.services.xhs.provider import XhsContextProvider
        register(XhsContextProvider())
    except Exception as exc:
        log.warning(f"XhsContextProvider register failed: {exc}")

    # 6. Track knowledge (Phase D, 2026-05-16) — 8 canonical 的 employers /
    #    signals / STAR / follow-up 模板。tracks.yaml 在 taxonomy module 里。
    try:
        from app.services.taxonomy.provider import TrackKnowledgeProvider
        register(TrackKnowledgeProvider())
    except Exception as exc:
        log.warning(f"TrackKnowledgeProvider register failed: {exc}")

    # 7. 互联网/AI 简历方法论 (2026-06-12) — 蒸馏自腾讯校招 skill 的 resume-guide,
    #    赛道门控: 学生选了互联网/AI 才在简历改写对话里注入面试官视角的优秀简历标准。
    try:
        from app.services.resume_copilot.internet_resume_provider import InternetResumeProvider
        register(InternetResumeProvider())
    except Exception as exc:
        log.warning(f"InternetResumeProvider register failed: {exc}")


__all__ = [
    "ContextProvider",
    "ContextRequest",
    "bootstrap",
    "fetch_blocks",
    "fetch_blocks_for_jobs",
    "format_per_job_aggregated",
    "register",
    "registered_names",
]
