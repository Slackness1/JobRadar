"""SensitiveTopicProvider — early-terminate guardrail for chat turns.

Scans the user's question against the sensitive_topics table's
typical_phrasings_json patterns. On a hit:

- severity='block'  : returns (response_template, terminate=True) — skill rules
                      forbid further data injection (薪酬 / 通过率 / offer 承诺)
- severity='warn'   : returns (response_template, terminate=True) — same
                      hard-stop because mixing other sources with these
                      templates dilutes the guardrail
- severity='soften' : returns (rule reminder, terminate=False) — output-shape
                      hint only; other providers still allowed to add context

Detection is keyword-based with simple Chinese-friendly tokenization
(strip punctuation, substring match). Aggressive on purpose — false
positives only mean we serve the safe template instead of an LLM answer,
which is the desired conservative bias.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Iterable

from app.models import SensitiveTopic
from app.services.llm_context.base import PURPOSE_CHAT, ContextRequest

logger = logging.getLogger(__name__)


_EMPLOYER_KEY = "tencent"

# Punctuation-strip pattern for cheap normalization. Keep CJK + ASCII alnum.
_PUNCT_RE = re.compile(r"[^\w一-鿿]+")


class SensitiveTopicProvider:
    name = "sensitive_topic"

    def applies_to(self, req: ContextRequest) -> bool:
        if req.purpose != PURPOSE_CHAT:
            return False
        return bool((req.user_question or "").strip())

    def fetch(self, req: ContextRequest) -> tuple[str, bool] | str:
        question = _normalize(req.user_question or "")
        if not question:
            return ""

        rows = (
            req.db.query(SensitiveTopic)
            .filter(SensitiveTopic.employer_key == _EMPLOYER_KEY)
            .all()
        )
        hit = _first_match(question, rows)
        if hit is None:
            return ""

        topic, matched_phrase = hit
        block = _format_block(topic, matched_phrase)
        # block + warn both early-terminate; soften lets others continue.
        terminate = topic.severity in ("block", "warn")
        if terminate:
            logger.info(
                "sensitive_topic hit: topic=%s severity=%s matched=%r",
                topic.topic_key, topic.severity, matched_phrase[:40],
            )
        return block, terminate


# ── helpers ────────────────────────────────────────────────────────────────


def _normalize(s: str) -> str:
    """Lowercase + strip punctuation. Keeps CJK characters intact."""
    return _PUNCT_RE.sub("", s.lower())


def _first_match(
    normalized_question: str,
    rows: Iterable[SensitiveTopic],
) -> tuple[SensitiveTopic, str] | None:
    """Return the first (topic, matched_phrase) where normalized
    typical_phrasing is a substring of the normalized question.

    Iteration order is DB row order (insertion order). Topics seeded with
    severity='block' come first chronologically because the LLM extractor
    walks the markdown top-down (薪酬 → 通过率 → ...).
    """
    for topic in rows:
        phrases = _safe_loads_list(topic.typical_phrasings_json)
        for raw_phrase in phrases:
            phrase = _normalize(raw_phrase)
            if not phrase or len(phrase) < 3:
                continue
            if phrase in normalized_question:
                return topic, raw_phrase
            # Also try a coarser check: any 4-char window of the phrase appears.
            # Useful when student paraphrases ("通过率怎么样" matches a phrasing
            # listed as "XX 岗位通过率是多少？").
            if _window_match(phrase, normalized_question, window=4):
                return topic, raw_phrase
    return None


def _window_match(needle: str, haystack: str, *, window: int) -> bool:
    if len(needle) < window:
        return False
    for i in range(len(needle) - window + 1):
        if needle[i: i + window] in haystack:
            return True
    return False


def _safe_loads_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        out = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [str(x) for x in out] if isinstance(out, list) else []


def _format_block(topic: SensitiveTopic, matched_phrase: str) -> str:
    name = (topic.display_name or topic.topic_key or "").strip()
    template = (topic.response_template or "").strip()
    severity = (topic.severity or "block").strip()

    lines = [
        f"[sensitive_topic · 命中：{name}（severity={severity}）]",
        f"识别到的措辞：「{matched_phrase}」",
    ]
    if severity in ("block", "warn"):
        lines.append("⚠️ 必须严格使用以下回答模板，不得叠加其他建议或信息：")
    else:
        lines.append("回答时请遵循下面的措辞约束：")
    if template:
        lines.append("")
        lines.append(template)
    return "\n".join(lines)


__all__ = ["SensitiveTopicProvider"]
