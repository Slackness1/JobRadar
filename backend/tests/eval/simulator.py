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

## persona_voice (Day 9 PR-2 G1 + Day 10 Gap 1 — 区分 good / bad 口头习惯)

如果输入里有 `persona_voice.verbal_tics` 字段, 这是该 persona 的**习惯口头禅 / 表达风格**.

### `verbal_tics_style = "good"` (顶档投研 / 理工硬核风格 — 不要强嵌)

如 `"我的 view 是 ..."` / `"非共识的点在于 ..."` / `"sample 是 X 到 Y"` / `"我做过 backtest"`
之类**真投研 / 真量化口头禅**. 这种是顶档候选人**自然的语言风格**, 不算套话:
  - 自然提及即可, **不强制每题嵌入** — 该用就用, 不该用就别硬塞
  - 一题最多挂 1 次, 避免把好风格用成"行话堆叠"被 evaluator 误判成模板词
  - 答的内容仍然主要服务"具体动作 + 数据 + 结论", 不要为了凑口头禅而虚化具体内容

### `verbal_tics_style = "bad"` / `"mixed"` / 未指定 (默认行为 — 强制嵌入)

`"主导 / 沉淀 / 闭环 / 端到端价值闭环 / leveraged synergies"` 之类**套模板 / 翻译腔**.
这种是 evaluator 要抓的"行话堆叠"问题, **不嵌入 = 测不出来**:
  - `verbal_tics` 有 ≥ 2 项 → 这一题至少**自然嵌入 1 项**到答里 (用法不要突兀, 但要露)
  - `verbal_tics` 有 ≥ 4 项 → 这一题至少嵌入 2 项
  - 不要把所有 tics 在一题里堆完 — 在 6 题里**均匀分布**, 让面试官能感受到这个候选人
    讲话**就是这种风格**, 而不是偶尔说了句行话
  - 例: persona_voice.verbal_tics = ["leveraged synergies", "端到端价值闭环",
    "spearheaded", "stakeholder alignment"] →
    答里自然出现: "我当时 spearheaded 了这个项目, 跟 BD / 风控 / 产品 align expectations..."

## persona_voice.communication_style + under_pressure

如果有 `persona_voice.communication_style` (e.g. "话多 / 简练 / 满嘴黑话"), 让答的风格
跟它对得上. 如果有 `persona_voice.under_pressure` (e.g. "被追问就开始结巴"), 在 follow-up
里表现出来。
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
    persona_voice: dict | None = None,
) -> str:
    """让 simulator 给一道面试官问题生成候选人式回答。

    `persona_voice` (Day 9 PR-2 G1 修法): {communication_style, verbal_tics,
    typical_message_length, under_pressure}. verbal_tics ≥ 2 时 prompt 强制嵌入,
    让 evaluator 真实测到候选人的翻译腔 / 套话风格。
    """
    payload: dict = {
        "my_profile": _profile_for_simulator(student_profile),
        "prior_transcript": prior_transcript,
        "interviewer_question": interviewer_question,
    }
    if persona_voice:
        payload["persona_voice"] = _persona_voice_for_simulator(persona_voice)
    user_payload = json.dumps(payload, ensure_ascii=False)
    answer = simulator.chat(
        messages=[
            {"role": "system", "content": _SIMULATOR_SYSTEM},
            {"role": "user", "content": user_payload},
        ],
        temperature=0.7,   # 答题口语化,稍高 temperature
    )
    return answer.strip()


def _persona_voice_for_simulator(pv: dict) -> dict:
    """喂给 simulator 的 persona_voice 视图. 留 5 个核心字段 (含 Day 10 Gap 1 的
    `verbal_tics_style`), 不喂 meta。"""
    return {
        "communication_style": pv.get("communication_style"),
        "verbal_tics": pv.get("verbal_tics") or [],
        "verbal_tics_style": pv.get("verbal_tics_style"),
        "typical_message_length": pv.get("typical_message_length"),
        "under_pressure": pv.get("under_pressure"),
    }


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
