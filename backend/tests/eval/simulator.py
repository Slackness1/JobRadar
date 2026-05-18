"""候选人模拟器 — 多轮 role-play。

给 simulator LLM 一个 student profile + chip,让它假装是这个学生答 SUT 的提问。
跑完一完整面试 (6-turn skeleton + 0-N follow-up),返回 transcript。

约束:
  - simulator 必须严格基于 profile 答题,**不能编造** profile 里没有的事实/数字/经历
  - 每轮答案 100-400 字,跟真人面试节奏一致
  - 答到第 6 轮 (反问环节) 就停 — SUT 自己 follow-up 要不要再深挖一轮 evaluator 决定
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from tests.eval.clients import LLMClient

logger = logging.getLogger(__name__)


_SIMULATOR_SYSTEM = """\
你扮演一名中文校招面试候选人。你只能基于"my_profile"里写的真实事实回答问题,
**绝对不能编造** profile 里没有的公司、项目、数字、技能、奖项、经历。

回答规则:
  1. 第一人称、对话风格、长度 100-400 字
  2. 引用 profile 里具体公司 / 项目 / 数字 / 技能,不要泛泛
  3. 如果面试官问的方向 profile 没有相关经历,坦率说"这块我没有直接经验,但我做过 X"
  4. 不要堆形容词(如"专业、敬业、努力")— 用事实代替
  5. 不输出任何 meta 信息(不要说"作为候选人,我会..."),直接进入第一人称
"""


@dataclass(slots=True)
class SimulatedTurn:
    role: str           # "assistant" (面试官) | "user" (候选人)
    content: str
    is_followup: bool = False    # SUT 标记此 turn 为 follow-up 而非 skeleton
    parent_turn_index: int | None = None


@dataclass(slots=True)
class SimulatedSession:
    student_id: str
    chip: str
    turns: list[SimulatedTurn] = field(default_factory=list)

    def transcript_for_judge(self) -> list[dict]:
        return [{"role": t.role, "content": t.content} for t in self.turns]


def simulate_candidate_answer(
    *,
    simulator: LLMClient,
    student_profile: dict,
    interviewer_question: str,
    prior_transcript: list[dict],
) -> str:
    """让 simulator 给一道面试官问题生成候选人式回答。"""
    user_payload = json.dumps(
        {
            "my_profile": _profile_for_simulator(student_profile),
            "prior_transcript": prior_transcript,
            "interviewer_question": interviewer_question,
        },
        ensure_ascii=False,
    )
    answer = simulator.chat(
        messages=[
            {"role": "system", "content": _SIMULATOR_SYSTEM},
            {"role": "user", "content": user_payload},
        ],
        temperature=0.7,   # 答题口语化,稍高 temperature
    )
    return answer.strip()


def _profile_for_simulator(profile: dict) -> dict:
    """喂给 simulator 的 profile 视图 — 比 judge 看的还要全,因为 simulator 要引用细节。"""
    return {
        "name": (profile.get("basic_info") or {}).get("name"),
        "headline": (profile.get("basic_info") or {}).get("headline"),
        "candidate_summary": profile.get("candidate_summary"),
        "education": profile.get("education", []),
        "internships": profile.get("internships", []),
        "projects": profile.get("projects", []),
        "skills": profile.get("skills", {}),
        "awards": profile.get("awards", []),
    }
