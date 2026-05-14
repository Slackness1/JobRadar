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
    """
    try:
        from app.services.podcasts.provider import PodcastContextProvider
        register(PodcastContextProvider())
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(f"PodcastContextProvider register failed: {exc}")

    # Future:
    # try:
    #     from app.services.memory.provider import StudentMemoryProvider
    #     register(StudentMemoryProvider())
    # except Exception: pass
    #
    # try:
    #     from app.services.knowledge_pack.tencent_provider import TencentTrackProvider
    #     register(TencentTrackProvider())
    # except Exception: pass


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
