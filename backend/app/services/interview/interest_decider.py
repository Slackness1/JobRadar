"""LLM-driven follow-up 决策。

替代旧的"prev_score.overall < 60 or misses >= 1"系统视角逻辑。这套维度按
**真实面试官**视角:

  1. 业务强相关吗 — 候选人讲的项目/行业/技术,跟 JD 业务方向是否对得上
  2. 候选人埋了钩子吗 — "我还做过 X 但没展开" / 提了新 entity 没深入
  3. 答案有可 follow-up 的具体细节吗 — 公司/数字/项目/决策点
  4. 不被"答案完整度/分数"这种系统指标干扰

orchestrator 在 hard rule(反问环节、上限、答案太短)放过之后才调这个。
失败时降级 = 不 follow-up(advance)。
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class InterestDecision:
    should_continue: bool
    target_dimension: str | None   # 如果 continue,想聚焦哪个维度
    reasoning: str


class _LLMClient(Protocol):
    def chat_text(self, system: str, user: str, **kwargs) -> object: ...


_INTEREST_SYSTEM = """\
你是中文校招面试官。看候选人在某个项目上的回答(主问题 + 已经追问的几轮),
判断"作为真实面试官,我现在想继续追问吗?"

判断维度(按真实面试官思维,**不要**被系统指标干扰):
  1. **业务强相关吗** — 候选人讲的项目/行业/技术,跟 JD 业务方向(target_job + chip_summary
     + jd_content) 直接对得上,或者跟团队最近在做的方向匹配。强匹配 → 想问细节。
  2. **候选人埋了钩子吗** — 答案里有"我还做过 X 但没展开" / "这套方法在 Y 场景也用过"
     / 提了新 entity (公司/项目/技术) 没深入。这是候选人主动给面试官开门,值得跟。
  3. **答案有可 follow-up 的具体细节** — 公司/数字/项目/决策点/取舍。如果是空泛话术
     ("取得了不错成果"),没东西可问 → advance。
  4. **不要**被分数/完整度这种系统指标干扰。一个完美回答更值得多追(榨更多信号);
     一个一般回答如果没有钩子,就该 advance。

输出严格 JSON,无前后散文,无 markdown fence:
  {"should_continue": true | false,
   "target_dimension": "想聚焦哪个维度(20-50字),不继续就 null",
   "reasoning": "30-100 字解释,引用候选人话里具体词或 JD 关键词"}
"""

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL | re.IGNORECASE)


def should_continue_followup(
    *,
    llm: _LLMClient,
    target_job: str,
    chip_summary: str,
    jd_content: str,
    main_question: str,
    main_answer: str,
    followup_chain: list[tuple[str, str]],
    recalled_experiences: list[dict] | None = None,
) -> InterestDecision:
    """问 LLM:作为面试官,这次回答是否值得继续追问?

    `followup_chain` 是已问 + 已答的 follow-up 历史 [(q, a), ...]。最后一个
    是刚刚答完的那一轮。
    """
    user_payload = json.dumps(
        {
            "target_job": target_job,
            "chip_summary": chip_summary,
            "jd_content": (jd_content or "")[:1500],   # 截断防 token 爆
            "main_question": main_question,
            "main_answer": main_answer[:2000],
            "followup_chain": [
                {"q": q, "a": (a or "")[:2000]}
                for q, a in followup_chain
            ],
            "recalled_experiences": recalled_experiences or [],
        },
        ensure_ascii=False,
    )

    try:
        raw = llm.chat_text(system=_INTEREST_SYSTEM, user=user_payload)
    except Exception as exc:
        logger.warning("interest_decider LLM 调失败,默认 advance: %s", exc)
        return InterestDecision(
            should_continue=False,
            target_dimension=None,
            reasoning=f"<LLM 失败 fallback: {type(exc).__name__}>",
        )

    if not isinstance(raw, str) or not raw.strip():
        return InterestDecision(
            should_continue=False,
            target_dimension=None,
            reasoning="<LLM 返回空>",
        )

    return _parse_decision(raw)


def _parse_decision(raw: str) -> InterestDecision:
    """从 LLM 输出里解析 InterestDecision。容忍 markdown fence + 散文裹的 JSON。"""
    raw = raw.strip()
    fenced = _FENCE_RE.match(raw)
    if fenced:
        raw = fenced.group(1).strip()

    decoder = json.JSONDecoder()
    data: dict | None = None
    idx = raw.find("{")
    if idx >= 0:
        try:
            data, _ = decoder.raw_decode(raw[idx:])
        except json.JSONDecodeError:
            data = None

    if not isinstance(data, dict):
        logger.warning("interest_decider 返回无法解析: %s", raw[:200])
        return InterestDecision(
            should_continue=False,
            target_dimension=None,
            reasoning=f"<解析失败: {raw[:80]}>",
        )

    should = bool(data.get("should_continue"))
    target = data.get("target_dimension")
    if target is not None and not isinstance(target, str):
        target = str(target)
    return InterestDecision(
        should_continue=should,
        target_dimension=target,
        reasoning=str(data.get("reasoning", "")).strip(),
    )
