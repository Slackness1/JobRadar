"""Adaptive question selection.

First N turns: pop from a hand-curated skeleton dict (one ordered list per
chip). After skeleton runs out: ask the LLM to generate a follow-up using
the weakness profile. LLM failure → generic fallback.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Protocol

from app.services.interview.prompts import FOLLOW_UP_SYSTEM
from app.services.interview.weakness_profile import WeaknessProfile

logger = logging.getLogger(__name__)


# Per-chip mandatory question skeletons. Ordered: turn N pulls index N.
# Chip names mirror those in nowcoder/keywords.yaml. "default" is the
# fallback when chip isn't in the dict.
SKELETON_QUESTIONS: dict[str, list[str]] = {
    "default": [
        "请用 1-2 分钟做个自我介绍。",
        "讲一段你最近完成的项目，重点说说你做了什么、遇到的最大挑战是什么。",
        "在你做过的事情里，哪一件最能体现你这个岗位需要的能力？为什么？",
        "你为什么对这个岗位感兴趣？你期望从这份工作中学到什么？",
        "团队合作中，你印象最深的一次冲突或分歧是什么？怎么解决的？",
        "如果让你给过去一年的自己一个建议，你会说什么？",
    ],
    "数据分析师": [
        "请用 1-2 分钟做个自我介绍。",
        "讲一个你做过的数据分析项目，从问题定义到最终落地，你都做了什么？",
        "你怎么验证一个产品改动是真的带来了正面影响？",
        "讲一个你用 SQL 解决过的复杂问题。",
        "如果业务方提了一个看起来不靠谱的数据需求，你会怎么处理？",
        "你怎么看 AB 测试和因果推断的关系？",
    ],
    "产品经理": [
        "请做个简短的自我介绍，重点说说你为什么选产品方向。",
        "讲一个你主导过的产品功能，从需求到上线你做了什么？",
        "你怎么判断一个功能值不值得做？",
        "讲一次你和工程师/设计师产生分歧的经历。",
        "你最近用的产品里有哪一个让你觉得'这个 PM 真懂'？为什么？",
        "如果让你重做你简历里的某一段经历，你会怎么改？",
    ],
    "前端开发": [
        "请用 1-2 分钟做个自我介绍。",
        "讲一个你做过最有难度的前端项目，技术上的最大挑战是什么？",
        "你怎么处理大型应用的状态管理？",
        "讲一次你做的性能优化，怎么发现问题、怎么解决的？",
        "对 React 18 的并发特性你怎么看？",
        "你最近读的最有收获的前端文章 / 源码是什么？",
    ],
    "后端开发": [
        "请用 1-2 分钟做个自我介绍。",
        "讲一个你做过的后端项目，重点说说架构设计和技术选型。",
        "高并发场景下你最常遇到的问题是什么？怎么解决的？",
        "讲一次你做的数据库设计或优化。",
        "你怎么保证一个分布式系统的数据一致性？",
        "如果让你重新设计你简历里那个项目，你会怎么改？",
    ],
}

GENERIC_FALLBACK_QUESTION = "请详细讲讲你最近完成的项目里，你最自豪的一个细节。"


@dataclass(slots=True)
class NextQuestion:
    question: str
    source: str  # 'skeleton' | 'follow_up' | 'fallback'


class _LLMClient(Protocol):
    def chat_text(self, system: str, user: str, **kwargs) -> object: ...


def _skeleton_for(chip: str) -> list[str]:
    return SKELETON_QUESTIONS.get(chip) or SKELETON_QUESTIONS["default"]


def generate_followup_question(
    target_job: str,
    chip_summary: str,
    weakness: WeaknessProfile,
    asked_questions: list[str],
    llm: _LLMClient,
) -> NextQuestion:
    """Force-ask a follow-up sub-question via LLM, regardless of skeleton state.

    Used when the orchestrator decides to drill deeper on the current main question
    instead of advancing to the next skeleton item.
    """
    user_payload = json.dumps({
        "target_job": target_job,
        "chip_summary": chip_summary,
        "weakness_profile": {
            "avg_score": weakness.avg_score,
            "weak_topics": weakness.weak_topics,
            "strong_topics": weakness.strong_topics,
        },
        "asked_questions": asked_questions,
    }, ensure_ascii=False)

    try:
        raw = llm.chat_text(system=FOLLOW_UP_SYSTEM, user=user_payload)
    except Exception as exc:
        logger.warning("follow-up LLM failed: %s", exc)
        return NextQuestion(question=GENERIC_FALLBACK_QUESTION, source="fallback")

    if not isinstance(raw, str) or not raw.strip():
        return NextQuestion(question=GENERIC_FALLBACK_QUESTION, source="fallback")

    return NextQuestion(question=raw.strip(), source="follow_up")


def pick_next_question(
    target_job: str,
    chip: str,
    chip_summary: str,
    weakness: WeaknessProfile,
    asked_questions: list[str],
    turn_index: int,
    llm: _LLMClient,
) -> NextQuestion:
    """Choose the next question. turn_index is 0-based."""
    skeleton = _skeleton_for(chip)
    if turn_index < len(skeleton):
        return NextQuestion(question=skeleton[turn_index], source="skeleton")

    # After skeleton: ask LLM for a follow-up
    user_payload = json.dumps({
        "target_job": target_job,
        "chip_summary": chip_summary,
        "weakness_profile": {
            "avg_score": weakness.avg_score,
            "weak_topics": weakness.weak_topics,
            "strong_topics": weakness.strong_topics,
        },
        "asked_questions": asked_questions,
    }, ensure_ascii=False)

    try:
        raw = llm.chat_text(system=FOLLOW_UP_SYSTEM, user=user_payload)
    except Exception as exc:
        logger.warning("adaptive follow-up LLM failed: %s", exc)
        return NextQuestion(question=GENERIC_FALLBACK_QUESTION, source="fallback")

    if not isinstance(raw, str) or not raw.strip():
        return NextQuestion(question=GENERIC_FALLBACK_QUESTION, source="fallback")

    return NextQuestion(question=raw.strip(), source="follow_up")
