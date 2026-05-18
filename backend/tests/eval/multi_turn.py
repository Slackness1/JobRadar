"""Multi-turn 模拟面试 driver — Phase 1.5。

把整套 orchestrator 决策流跑一遍,测试 `interest_decider` 是不是真的会在合理的时机
advance / continue。

流程 (一个 student × 一个 chip):
  for each skeleton question (6 题):
     simulator 答题
     while 没到 cap 且 hard rule 都通过:
        interest_decider 判 continue / advance
        if continue:
           SUT 出 follow-up,simulator 答
           judge 评这个 follow-up 的质量
        else:
           break
     if 反问环节:
        end interview

判分:
  - 每个 follow-up turn → judge_multi_turn_followup_quality (0-3)
  - 整场 → 看 follow-up turn 数是否合理 + 反问环节是否正确收尾
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.interview.adaptive import SKELETON_QUESTIONS
from app.services.interview.interest_decider import should_continue_followup
from tests.eval.clients import LLMClient
from tests.eval.judge import Score, _parse_score
from tests.eval.simulator import simulate_candidate_answer

logger = logging.getLogger(__name__)


# Hard rule 阈值,跟 production orchestrator 对齐
_FOLLOWUP_CAP = 3
_TOO_SHORT_ANSWER_CHARS = 80


@dataclass(slots=True)
class TurnRecord:
    turn_index: int
    question: str
    question_source: str   # 'skeleton' | 'follow_up' | 'end'
    candidate_answer: str
    parent_main_index: int | None = None
    decision_continue: bool | None = None    # None = 未决策 (skeleton 出题之前)
    decision_reason: str = ""
    judge_score: int | None = None
    judge_reason: str = ""


@dataclass(slots=True)
class MultiTurnResult:
    student_id: str
    chip: str
    target_job: str
    turns: list[TurnRecord] = field(default_factory=list)

    @property
    def followup_turns(self) -> list[TurnRecord]:
        return [t for t in self.turns if t.question_source == "follow_up"]

    def to_dict(self) -> dict:
        return {
            "student_id": self.student_id,
            "chip": self.chip,
            "target_job": self.target_job,
            "n_turns": len(self.turns),
            "n_followups": len(self.followup_turns),
            "turns": [
                {
                    "idx": t.turn_index,
                    "source": t.question_source,
                    "question": t.question,
                    "answer": t.candidate_answer[:300],
                    "parent": t.parent_main_index,
                    "decision_continue": t.decision_continue,
                    "decision_reason": t.decision_reason[:200],
                    "judge_score": t.judge_score,
                    "judge_reason": t.judge_reason[:200],
                }
                for t in self.turns
            ],
        }


# ── interest_decider 适配器 ────────────────────────────────────────────────


class _DeciderAdapter:
    """Adapt eval LLMClient → interest_decider 的 _LLMClient Protocol。

    interest_decider 期望 `chat_text(system, user, **kwargs)` 返回字符串。
    eval LLMClient 是 `chat(messages, ...)` 接口。
    """

    def __init__(self, client: LLMClient):
        self._client = client

    def chat_text(self, system: str, user: str, **kwargs) -> str:
        return self._client.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=float(kwargs.get("temperature", 0.3)),
        )


# ── SUT: 生成 follow-up (multi-turn 版,接受 followup_chain) ─────────────────


_FOLLOWUP_GEN_SYSTEM = """\
你是 JobRadar 的中文校招模拟面试官。基于候选人当前讲的项目,提出**一个** follow-up 问题。

要求:
  1. 钉死在 main_question 描述的这个项目上,**绝对不要**跳到候选人简历另一段经历
  2. 追问候选人漏讲的关键维度(痛点 / 量化 / 取舍 / 风险),
     若 followup_chain 已经问过某维度,**不要**重复
  3. 一个问题,30-80 字,自然口语化
  4. 直接输出问题文本,不要 JSON,不要前后散文
"""


def _sut_generate_followup_multi_turn(
    sut: LLMClient,
    *,
    target_job: str,
    chip_summary: str,
    main_question: str,
    main_answer: str,
    followup_chain: list[tuple[str, str]],
    jd_content: str = "",
    target_dimension: str | None = None,
) -> str:
    user = json.dumps(
        {
            "target_job": target_job,
            "chip_summary": chip_summary,
            "main_question": main_question,
            "main_answer": main_answer,
            "followup_chain": [{"q": q, "a": a} for q, a in followup_chain],
            "jd_content": (jd_content or "")[:1500],
            "interest_decider_target_dimension": target_dimension,
        },
        ensure_ascii=False,
    )
    raw = sut.chat(
        messages=[
            {"role": "system", "content": _FOLLOWUP_GEN_SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.5,
    )
    return raw.strip()


# ── Judge: multi-turn follow-up 质量 (无预设 expected_targets) ─────────────


_MULTI_TURN_JUDGE_SYSTEM = """\
你是资深面试官,评估另一位面试官的 follow-up 问题质量。**没有**预设的 expected_targets,
你要自己判断。

评估维度 (按真实面试官思维):
  1. **钉死项目** — follow-up 是否扎在 main_answer 描述的项目里? 跳到候选人简历另一段
     经历 / 完全无关话题 → 0 分。
  2. **不重复** — 之前 followup_chain 里已经问过的角度,这个 follow-up 不能重复。
  3. **追问漏讲维度** — 候选人答案里没讲清楚的痛点 / 量化 / 取舍 / 决策点。
  4. **业务相关** — 跟 target_job / chip_summary 的业务方向有关。

评分:
  0 = 跳到候选人另一段经历 / 完全无关 / 反问候选人 "你为什么问这个"
  1 = 在项目内但太泛 ("还有什么补充","你觉得呢") 或 重复了已问过的方向
  2 = 在项目内,追问了具体维度
  3 = 在项目内,追问了候选人主动埋的钩子(answer 里出现的 entity 或承接 followup_chain
      建立的脉络) 或 业务关键洞察

只输出严格 JSON,无前后散文,无 markdown fence:
  {"score": 0-3, "reasoning": "30-150 字", "concerns": ["跳跃|泛泛|重复|偏题" 等]}
"""


def _judge_multi_turn_followup(
    judge: LLMClient,
    *,
    target_job: str,
    chip_summary: str,
    main_question: str,
    main_answer: str,
    followup_chain: list[tuple[str, str]],   # 已问 + 已答 (不含正在评估的)
    generated_followup: str,
) -> Score:
    user_payload = json.dumps(
        {
            "target_job": target_job,
            "chip_summary": chip_summary,
            "main_question": main_question,
            "main_answer": main_answer[:1500],
            "followup_chain": [{"q": q, "a": (a or "")[:600]} for q, a in followup_chain],
            "generated_followup": generated_followup,
        },
        ensure_ascii=False,
    )
    raw = judge.chat(
        messages=[
            {"role": "system", "content": _MULTI_TURN_JUDGE_SYSTEM},
            {"role": "user", "content": user_payload},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    return _parse_score(raw, metric="multi_turn_followup")


# ── Driver ─────────────────────────────────────────────────────────────────


def simulate_full_interview(
    *,
    sut: LLMClient,
    simulator: LLMClient,
    judge: LLMClient,
    student: dict,             # 完整 fixture (含 .id, .profile)
    chip: str,
    chip_summary: str,
    target_job: str,
    jd_content: str = "",
) -> MultiTurnResult:
    """跑完整套 skeleton + 各 follow-up 决策。返回 turn-by-turn 记录。

    - SUT 出 skeleton 的固定文案 (复用 SKELETON_QUESTIONS)
    - SUT 用 _sut_generate_followup_multi_turn 出 follow-up
    - Simulator 答题
    - interest_decider 决定 continue / advance
    - judge 评每个 follow-up
    - 反问环节 hard rule 收尾
    """
    skeleton_list = SKELETON_QUESTIONS.get(chip) or SKELETON_QUESTIONS["default"]
    decider_llm = _DeciderAdapter(sut)

    result = MultiTurnResult(
        student_id=str(student.get("id", "?")),
        chip=chip,
        target_job=target_job,
    )
    turn_idx = 0

    for skel_idx, skel_question in enumerate(skeleton_list):
        is_reverse = skel_idx == len(skeleton_list) - 1
        # 出 skeleton 题 + simulator 答
        prior_transcript = [
            {"role": "assistant" if t.question else "user",
             "content": t.question or t.candidate_answer}
            for t in result.turns
        ]
        skel_answer = simulate_candidate_answer(
            simulator=simulator,
            student_profile=student["profile"],
            interviewer_question=skel_question,
            prior_transcript=prior_transcript,
        )
        main_idx = turn_idx
        result.turns.append(TurnRecord(
            turn_index=turn_idx,
            question=skel_question,
            question_source="skeleton",
            candidate_answer=skel_answer,
        ))
        turn_idx += 1

        if is_reverse:
            # Hard rule: 反问环节 → 强制收尾
            result.turns.append(TurnRecord(
                turn_index=turn_idx,
                question="[interview ended after reverse question]",
                question_source="end",
                candidate_answer="",
                parent_main_index=main_idx,
                decision_continue=False,
                decision_reason="hard rule: reverse question phase → 收尾",
            ))
            turn_idx += 1
            break

        # 进入 follow-up 循环
        followup_chain: list[tuple[str, str]] = []
        for _ in range(_FOLLOWUP_CAP):
            last_answer = followup_chain[-1][1] if followup_chain else skel_answer
            # Hard rule: 答案太短
            if len((last_answer or "").strip()) < _TOO_SHORT_ANSWER_CHARS:
                logger.info("hard rule: 答案 < %d 字,advance (skel=%d)", _TOO_SHORT_ANSWER_CHARS, skel_idx)
                break

            # Soft: interest_decider
            try:
                decision = should_continue_followup(
                    llm=decider_llm,
                    target_job=target_job,
                    chip_summary=chip_summary,
                    jd_content=jd_content,
                    main_question=skel_question,
                    main_answer=skel_answer,
                    followup_chain=followup_chain,
                )
            except Exception as exc:
                logger.warning("interest_decider 失败,advance: %s", exc)
                break

            if not decision.should_continue:
                logger.info("interest_decider: advance · %s", decision.reasoning[:120])
                break

            # SUT 生成 follow-up
            try:
                followup_q = _sut_generate_followup_multi_turn(
                    sut,
                    target_job=target_job,
                    chip_summary=chip_summary,
                    main_question=skel_question,
                    main_answer=skel_answer,
                    followup_chain=followup_chain,
                    jd_content=jd_content,
                    target_dimension=decision.target_dimension,
                )
            except Exception as exc:
                logger.warning("SUT follow-up 生成失败,advance: %s", exc)
                break

            # Simulator 答
            updated_transcript = [
                {"role": "assistant" if t.question else "user",
                 "content": t.question or t.candidate_answer}
                for t in result.turns
            ] + [{"role": "assistant", "content": followup_q}]
            followup_a = simulate_candidate_answer(
                simulator=simulator,
                student_profile=student["profile"],
                interviewer_question=followup_q,
                prior_transcript=updated_transcript,
            )

            # Judge 这个 follow-up
            try:
                score = _judge_multi_turn_followup(
                    judge,
                    target_job=target_job,
                    chip_summary=chip_summary,
                    main_question=skel_question,
                    main_answer=skel_answer,
                    followup_chain=followup_chain,
                    generated_followup=followup_q,
                )
                judge_score = score.score
                judge_reason = score.reasoning
            except Exception as exc:
                logger.warning("judge 失败: %s", exc)
                judge_score = None
                judge_reason = f"<judge error: {exc}>"

            result.turns.append(TurnRecord(
                turn_index=turn_idx,
                question=followup_q,
                question_source="follow_up",
                candidate_answer=followup_a,
                parent_main_index=main_idx,
                decision_continue=True,
                decision_reason=decision.reasoning,
                judge_score=judge_score,
                judge_reason=judge_reason,
            ))
            turn_idx += 1

            # 加入 chain 给下一轮 interest_decider 用
            followup_chain.append((followup_q, followup_a))

    return result
