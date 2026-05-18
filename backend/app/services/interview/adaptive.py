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


# 与前端 ProgressRail 对齐的 6 个主题点位。**改这里的话前端会自动跟上**
# （前端通过 /api/interview/skeleton 拉取），不要再在 ProgressRail.tsx 里
# 写死。新增/重排时务必保持顺序一致 — turn_index 直接对应 index。
SKELETON_TOPIC_LABELS: list[str] = [
    "自我介绍与来意",
    "主导过的核心项目",
    "关键技术 / 业务取舍",
    "在不确定下的决策",
    "为什么是这家公司",
    "反问环节",
]

# Per-chip mandatory question skeletons. Ordered: turn N pulls index N,
# and turn N 的主题 = SKELETON_TOPIC_LABELS[N]。
# Chip names mirror those in nowcoder/keywords.yaml. "default" is the
# fallback when chip isn't in the dict.
SKELETON_QUESTIONS: dict[str, list[str]] = {
    "default": [
        # 0 自我介绍与来意
        "请用 1-2 分钟做个自我介绍，最后落到为什么你和这个岗位匹配。",
        # 1 主导过的核心项目（项目深挖）
        "讲一段你最近主导的项目：客户/团队的痛点是什么，你的目标是什么，你用了什么方法。",
        # 2 关键技术 / 业务取舍
        "在那个项目里有没有一个关键的技术或业务取舍？为什么这么选，代价是什么？",
        # 3 在不确定下的决策
        "讲一次你在信息不完整或目标不清晰的情况下，是怎么做决策推动事情往前走的。",
        # 4 为什么是这家公司
        "为什么选这家公司？最近你关注到他们的哪个业务/项目/动态？",
        # 5 反问环节
        "你想反过来问我们什么？无论是这个岗位、团队还是业务方向。",
    ],
    "数据分析师": [
        "请用 1-2 分钟做个自我介绍，最后落到你为什么适合做数据分析。",
        "讲一个你做过的数据分析项目：业务方的痛点是什么，你做了什么，最后用什么指标证明带来了价值。",
        "在那个项目里你做过最关键的技术或业务取舍是什么？（比如：选指标 / 选实验方法 / 选模型）",
        "如果业务方提了一个数据上不太能验证的需求，你会怎么推动？",
        "为什么选这家公司？他们最近有哪个数据驱动的业务/产品让你觉得有意思？",
        "你想反过来问面试官什么？",
    ],
    "产品经理": [
        "请做个简短的自我介绍，最后落到你为什么选产品方向。",
        "讲一个你主导过的产品功能：用户痛点是什么，你的目标是什么，你怎么推动上线。",
        "那个功能里有没有一个关键取舍？比如做不做某个功能、上不上某条业务线，代价是什么？",
        "讲一次你在数据 / 资源不充分的不确定环境下，怎么决策要不要做某件事的经历。",
        "为什么选这家公司？他们最近的哪个产品让你觉得'这个 PM 真懂'？",
        "你想反过来问面试官什么？",
    ],
    "前端开发": [
        "请用 1-2 分钟做个自我介绍，最后落到你为什么适合做前端。",
        "讲一个你做过最有难度的前端项目：解决的痛点是什么，技术挑战是什么。",
        "在那个项目里你做过的关键技术取舍是什么？（架构 / 性能 / 框架选型 / 状态管理）",
        "讲一次产品 / 设计输入不清晰的不确定情境下，你是怎么决策并推进开发的。",
        "为什么选这家公司？他们最近的哪个工程实践或产品让你觉得有意思？",
        "你想反过来问面试官什么？",
    ],
    "后端开发": [
        "请用 1-2 分钟做个自我介绍，最后落到你为什么适合做后端。",
        "讲一个你做过的后端项目：业务痛点是什么，你的目标是什么，你用了什么架构和技术。",
        "在那个项目里你做过的关键技术取舍是什么？（架构 / 一致性 / 并发 / 选型）",
        "讲一次你在系统出现非预期问题时是怎么定位和决策的。",
        "为什么选这家公司？他们最近的哪个工程实践或业务让你觉得有挑战？",
        "你想反过来问面试官什么？",
    ],
}

GENERIC_FALLBACK_QUESTION = "请详细讲讲你最近完成的项目里，你最自豪的一个细节。"


@dataclass(slots=True)
class NextQuestion:
    question: str
    source: str  # 'skeleton' | 'follow_up' | 'fallback' | 'end'


class _LLMClient(Protocol):
    def chat_text(self, system: str, user: str, **kwargs) -> object: ...


def _skeleton_for(chip: str) -> list[str]:
    return SKELETON_QUESTIONS.get(chip) or SKELETON_QUESTIONS["default"]


_JD_PROMPT_TRUNCATE = 1500


def _build_followup_user_payload(
    target_job: str,
    chip_summary: str,
    weakness: WeaknessProfile,
    asked_questions: list[str],
    jd_content: str = "",
    current_main_question: str = "",
    current_main_answer: str = "",
    recalled_experiences: list[dict] | None = None,
) -> str:
    payload: dict = {
        "target_job": target_job,
        "chip_summary": chip_summary,
        "weakness_profile": {
            "avg_score": weakness.avg_score,
            "weak_topics": weakness.weak_topics,
            "strong_topics": weakness.strong_topics,
        },
        "asked_questions": asked_questions,
    }
    # When drilling, explicitly tell the LLM what we're drilling INTO so it
    # doesn't jump to another resume entry. Bad case found in mock: follow-up
    # for an electricity-price project asked about a banking project instead.
    if current_main_question:
        payload["drilling_into"] = {
            "main_question": current_main_question,
            "candidate_answer": current_main_answer[:1500],
            "instruction": (
                "你必须围绕 candidate_answer 里**这个具体项目/经历**追问，"
                "绝对不要跳到候选人简历里的另一段经历。如果答案缺客户痛点，"
                "追问这个项目的客户/团队痛点；如果缺量化结果，追问这个项目"
                "的业务影响指标；如果缺取舍，追问这个项目里的关键决策。"
            ),
        }
    if jd_content and jd_content.strip():
        payload["jd_content"] = jd_content.strip()[:_JD_PROMPT_TRUNCATE]
    if recalled_experiences:
        payload["recalled_experiences"] = {
            "items": recalled_experiences,
            "instruction": (
                "以上是该候选人过往会话里登记过的真实经历摘要。可以**引用其中一段**作为"
                "follow-up 的切入口（例如：'你之前提到过 X 项目，能不能聊一下当时的 Y'），"
                "但绝不要照抄 raw_excerpt 原话。如果没有合适的钩子，就忽略这个字段。"
            ),
        }
    return json.dumps(payload, ensure_ascii=False)


def generate_followup_question(
    target_job: str,
    chip_summary: str,
    weakness: WeaknessProfile,
    asked_questions: list[str],
    llm: _LLMClient,
    jd_content: str = "",
    current_main_question: str = "",
    current_main_answer: str = "",
    recalled_experiences: list[dict] | None = None,
) -> NextQuestion:
    """Force-ask a follow-up sub-question via LLM, regardless of skeleton state.

    Used when the orchestrator decides to drill deeper on the current main question
    instead of advancing to the next skeleton item.

    `current_main_question` + `current_main_answer` 钉死 LLM 在当前正在深挖的
    项目上 — 没有这两个字段时 LLM 容易跳到候选人简历里的另一段经历。
    """
    user_payload = _build_followup_user_payload(
        target_job, chip_summary, weakness, asked_questions, jd_content,
        current_main_question=current_main_question,
        current_main_answer=current_main_answer,
        recalled_experiences=recalled_experiences,
    )

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
    jd_content: str = "",
) -> NextQuestion:
    """Choose the next question. turn_index is 0-based."""
    skeleton = _skeleton_for(chip)
    if turn_index < len(skeleton):
        return NextQuestion(question=skeleton[turn_index], source="skeleton")

    user_payload = _build_followup_user_payload(
        target_job, chip_summary, weakness, asked_questions, jd_content,
    )

    try:
        raw = llm.chat_text(system=FOLLOW_UP_SYSTEM, user=user_payload)
    except Exception as exc:
        logger.warning("adaptive follow-up LLM failed: %s", exc)
        return NextQuestion(question=GENERIC_FALLBACK_QUESTION, source="fallback")

    if not isinstance(raw, str) or not raw.strip():
        return NextQuestion(question=GENERIC_FALLBACK_QUESTION, source="fallback")

    return NextQuestion(question=raw.strip(), source="follow_up")
