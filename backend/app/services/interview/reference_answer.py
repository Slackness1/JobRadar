"""Generate a 3-5 sentence model answer ("如果是面霸会怎么答") for one interview question.

LLM is allowed to use chip_summary and candidate_summary as context but is
instructed (in the prompt) to NOT fabricate concrete numbers or specific
projects. Failure returns empty string — UI hides the section.
"""
from __future__ import annotations

import json
import logging
from typing import Protocol

from app.services.interview.prompts import REFERENCE_SYSTEM

logger = logging.getLogger(__name__)


class _LLMClient(Protocol):
    def chat_text(self, system: str, user: str, **kwargs) -> object: ...


def generate_reference(
    target_job: str,
    question: str,
    chip_summary: str,
    candidate_summary: str,
    llm: _LLMClient,
) -> str:
    """Return the reference answer paragraph, or empty string on any failure."""
    user_payload = json.dumps({
        "target_job": target_job,
        "question": question,
        "chip_summary": chip_summary,
        "candidate_summary": candidate_summary,
    }, ensure_ascii=False)

    try:
        raw = llm.chat_text(system=REFERENCE_SYSTEM, user=user_payload)
    except Exception as exc:
        logger.warning("reference LLM call failed: %s", exc)
        return ""

    if not isinstance(raw, str):
        return ""
    return raw.strip()
