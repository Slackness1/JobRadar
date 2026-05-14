"""Pluggable context-injection layer for LLM prompts.

When several "knowledge sources" all want to enrich the same LLM call (resume
chat / job rerank / interview question / interview report), they each become a
ContextProvider and register here. The gateway code calls fetch_blocks(req)
once and concatenates whatever applicable providers return.

Usage:
    from app.services.llm_context import ContextRequest, fetch_blocks

    req = ContextRequest(purpose="chat", db=db, user_question=msg, profile=p)
    blocks = fetch_blocks(req)
    system_prompt = base + "\\n\\n" + "\\n\\n".join(blocks)

Adding a new feature (memory / skills / etc.):
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

    Add new providers here as features land. Each call is independent — failing
    to register one provider must not block the others.
    """
    try:
        from app.services.podcasts.provider import PodcastContextProvider
        register(PodcastContextProvider())
    except Exception:
        # A missing/broken provider must never block app boot.
        pass

    # Future:
    # try:
    #     from app.services.memory.provider import StudentMemoryProvider
    #     register(StudentMemoryProvider())
    # except Exception:
    #     pass
    #
    # try:
    #     from app.services.skills.provider import TrackStandardsProvider
    #     register(TrackStandardsProvider())
    # except Exception:
    #     pass


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
