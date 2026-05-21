"""LLM-driven rubric scoring for one interview answer.

The scoring rubric comes from the chip's nowcoder summary (passed in as
chip_summary). Q5-pattern hardening: any failure (network, malformed JSON,
non-dict response, missing fields) returns ScoreResult.empty() rather than
raising — the orchestrator never gets a 500 from this module.

Optional ContextProvider integration: when ``db`` is passed, score_answer
runs the LLM-Context Registry (purpose=INTERVIEW_SCORE) and appends the
returned blocks + a personalization directive to SCORING_SYSTEM, so the
LLM can produce student-specific feedback (e.g. "未联用 [中金白酒实习]")
instead of generic 6 维 misses. db=None preserves byte-identical behavior
for existing call sites + tests.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Protocol

from app.services.interview.prompts import (
    SCORING_PERSONALIZATION_DIRECTIVE,
    SCORING_SYSTEM,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class _LLMClient(Protocol):
    def chat_json(self, system: str, user: str, **kwargs) -> object: ...


@dataclass(slots=True)
class ScoreResult:
    overall: int | None = None
    hits: list[str] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)
    bonuses: list[str] = field(default_factory=list)
    # 2026-05-20: 5 维独立打分 (job_fit / info_selection / logic /
    # industry_sense / credibility), 0-10 分 + evidence + reason。
    # 2026-05-22 PR-1: 加 expression_depth 第 6 维 (STAR-M)。
    # 旧调用方不传 → None, 完全向后兼容。
    dim_scores: list[dict] | None = None
    # 2026-05-22 PR-3: opt-in trait_signals (4 trait × strong/weak) + 钩子原话.
    # 每题最多 2 个 tag, 没信号就空 list, **不算总分**, 只给 report.traits narrative
    # 聚合用. None = LLM 没产 (向后兼容)。
    trait_signals: list[dict] | None = None
    # 2026-05-22 PR-3: transferability_signal _meta tag, 3 选 1:
    # "active_bridge" — 候选人主动讲了"X 能搬到 Y, Z 需重学"
    # "no_attempt" — domain mismatch 但候选人没主动桥接
    # "domain_match" — domain 直接对得上, 不存在迁移问题
    # None = LLM 没产或非跨 domain 题, 不算分。
    transferability_signal: str | None = None

    @classmethod
    def empty(cls) -> "ScoreResult":
        return cls()

    def to_json(self) -> str:
        out = {
            "overall": self.overall,
            "hits": self.hits,
            "misses": self.misses,
            "bonuses": self.bonuses,
        }
        if self.dim_scores is not None:
            out["dim_scores"] = self.dim_scores
        if self.trait_signals is not None:
            out["trait_signals"] = self.trait_signals
        if self.transferability_signal is not None:
            out["transferability_signal"] = self.transferability_signal
        return json.dumps(out, ensure_ascii=False)


# 6 维 id → 中文 name 表 (与 SCORING_SYSTEM / report.py 对齐)
# 2026-05-22 Day 9 PR-1: 新加 expression_depth 第 6 维 (STAR-M 范式),
# 区分 A 流水账型 / B 有目标型 / C 方法论型 学生的表达深度档位。
DIM_ID_TO_NAME: dict[str, str] = {
    "job_fit": "岗位能力匹配度",
    "info_selection": "信息选取与侧重",
    "logic": "逻辑性",
    "industry_sense": "行业感",
    "credibility": "可信度",
    "expression_depth": "表达深度",
}


def _string_list(value, cap: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out[:cap]


def _clamp_overall(value) -> int | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(100, n))


def _clamp_dim_score(value) -> int | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(10, n))


# 2026-05-22 PR-3: 4 trait + 2 strength 白名单 (与 prompt 对齐)
_TRAIT_NAMES: frozenset[str] = frozenset({"内驱力", "学习能力", "团队合作", "钻研精神"})
_TRAIT_STRENGTHS: frozenset[str] = frozenset({"strong", "weak"})
# transferability_signal 3 选 1 + None
_TRANSFERABILITY_VALUES: frozenset[str] = frozenset({"active_bridge", "no_attempt", "domain_match"})


def _coerce_trait_signals(value) -> list[dict] | None:
    """Parse trait_signals list. 每题最多 2 个 valid tag, drop 非白名单 trait/strength。
    None 表示 LLM 没产 (向后兼容); 空 list 表示 LLM 显式说"这题没特质信号"。
    """
    if not isinstance(value, list):
        return None
    out: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        trait = item.get("trait")
        if not isinstance(trait, str) or trait not in _TRAIT_NAMES:
            continue
        strength = item.get("strength")
        if not isinstance(strength, str) or strength not in _TRAIT_STRENGTHS:
            continue
        evidence = item.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            continue
        out.append({
            "trait": trait,
            "strength": strength,
            "evidence": evidence.strip()[:200],
        })
        if len(out) >= 2:   # 每题最多 2 个 tag (cap, 防 LLM 输出爆)
            break
    return out


def _coerce_transferability(value) -> str | None:
    """Validate transferability_signal — 必须 3 个白名单之一 or None。"""
    if not isinstance(value, str):
        return None
    if value not in _TRANSFERABILITY_VALUES:
        return None
    return value


def _coerce_dim_scores(value) -> list[dict] | None:
    """Parse the 5-dim list. Drop bad entries; keep partial if at least 1 valid.

    Returns None when LLM didn't produce dim_scores (legacy path / failure) so
    that old callers that only look at overall/hits/misses stay byte-identical.
    """
    if not isinstance(value, list):
        return None
    out: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        dim_id = item.get("id")
        if not isinstance(dim_id, str) or dim_id not in DIM_ID_TO_NAME:
            continue
        score = _clamp_dim_score(item.get("score"))
        if score is None:
            continue
        out.append({
            "id": dim_id,
            "name": DIM_ID_TO_NAME[dim_id],
            "score": score,
            "evidence": _string_list(item.get("evidence"), cap=4),
            "reason": (item.get("reason") or "").strip()[:300],
        })
    return out or None


def _build_system_prompt(
    db: "Optional[Session]",
    target_job: str,
    user_key: str,
    profile: Optional[dict],
    preferences: Optional[dict],
) -> str:
    """SCORING_SYSTEM + optional context blocks + personalization directive.

    db=None → returns SCORING_SYSTEM unchanged (test/legacy path).
    Provider failures are logged inside fetch_blocks and swallowed; we get
    back fewer blocks but never raise.
    """
    if db is None:
        return SCORING_SYSTEM

    from app.services.llm_context import fetch_blocks
    from app.services.llm_context.base import PURPOSE_INTERVIEW_SCORE, ContextRequest

    req = ContextRequest(
        purpose=PURPOSE_INTERVIEW_SCORE,
        db=db,
        target_job=target_job,
        user_key=user_key or "",
        profile=profile,
        preferences=preferences,
    )
    try:
        blocks = fetch_blocks(req)
    except Exception as exc:
        logger.warning("fetch_blocks for scoring failed: %s", exc)
        blocks = []

    if not blocks:
        return SCORING_SYSTEM
    return (
        SCORING_SYSTEM
        + "\n\n## 额外上下文 (来自智库 / 学生记忆)\n\n"
        + "\n\n".join(blocks)
        + "\n\n"
        + SCORING_PERSONALIZATION_DIRECTIVE
    )


def score_answer(
    target_job: str,
    question: str,
    user_answer: str,
    chip_summary: str,
    llm: _LLMClient,
    *,
    db: "Optional[Session]" = None,
    user_key: str = "",
    profile: Optional[dict] = None,
    preferences: Optional[dict] = None,
) -> ScoreResult:
    """Score one user answer against the rubric. Never raises.

    db (kw-only, optional): when provided, enables ContextProvider injection
    + personalization directive — see module docstring. Existing callers
    that omit it get byte-identical behavior to the pre-Phase-D path.
    """
    user_payload = json.dumps({
        "target_job": target_job,
        "question": question,
        "user_answer": user_answer,
        "chip_summary": chip_summary,
    }, ensure_ascii=False)

    system_prompt = _build_system_prompt(db, target_job, user_key, profile, preferences)

    # Day 11 M2: LLM 调用失败时 retry 1 次. Why: full 27 baseline 5 个 persona
    # 有 turn `overall=None`, 上游 trait/report 聚合受污染. retry 一次能消大部分
    # transient 失败 (rate limit / 5xx / timeout). 再失败仍返 empty, runner 自己跳.
    try:
        raw = llm.chat_json(system=system_prompt, user=user_payload)
    except Exception as exc:
        logger.warning("scoring LLM call failed, retrying once: %s", exc)
        try:
            raw = llm.chat_json(system=system_prompt, user=user_payload)
        except Exception as exc2:
            logger.warning("scoring LLM retry also failed: %s", exc2)
            return ScoreResult.empty()

    if not isinstance(raw, dict):
        logger.warning("scoring LLM returned non-dict (%s)", type(raw).__name__)
        return ScoreResult.empty()

    dim_scores = _coerce_dim_scores(raw.get("dim_scores"))

    # 2026-05-21 Day 8 Bug A: 模板词 / 翻译腔 / 跨专业 mismatch 后处理 cap
    # baseline v3 抓到 LLM 倾向给鼓励分 (M9 套模板=80, M12 翻译腔=87), 不敢扣低分。
    # 在 LLM 评分基础上, 检测候选人答里有没有套模板/翻译腔/跨专业 mismatch 信号,
    # 命中 → 该维度 cap ≤ 3. 不重生成, 只 cap 上限。
    if dim_scores:
        dim_scores = _apply_pattern_caps(dim_scores, user_answer, target_job)

    overall = _clamp_overall(raw.get("overall"))
    # 如果 LLM 给了 dim_scores 但 overall 缺失/不合法 (或 pattern cap 改了 dim),
    # 重算 overall = mean(dim) * 10
    if dim_scores and (overall is None or _need_recompute_overall(raw.get("overall"), dim_scores)):
        overall = round(sum(d["score"] for d in dim_scores) * 10 / len(dim_scores))

    return ScoreResult(
        overall=overall,
        hits=_string_list(raw.get("hits"), cap=5),
        misses=_string_list(raw.get("misses"), cap=4),
        bonuses=_string_list(raw.get("bonuses"), cap=3),
        dim_scores=dim_scores,
        trait_signals=_coerce_trait_signals(raw.get("trait_signals")),
        transferability_signal=_coerce_transferability(raw.get("transferability_signal")),
    )


def _need_recompute_overall(raw_overall, dim_scores) -> bool:
    """LLM overall vs 5-dim mean × 10 偏离 > 15 分 → cap 把 dim 改了, 应重算 overall。"""
    try:
        raw_int = int(raw_overall)
        computed = round(sum(d["score"] for d in dim_scores) * 10 / len(dim_scores))
        return abs(raw_int - computed) > 15
    except (TypeError, ValueError):
        return True


# 12 个套模板词 — baseline M9 抓到的 "主导/复盘/沉淀/赋能/闭环/抓手/打法/心智"
# + 业界扩展。命中 ≥ 3 个 → info_selection / logic 维度 cap ≤ 3
_TEMPLATE_WORDS = (
    '主导', '复盘', '沉淀', '赋能', '闭环', '抓手', '打法', '心智',
    '链路', '范式', '矩阵化', '颗粒度',
)

# 8 个翻译腔短语 — baseline M12 抓到的 "leveraged synergies / 端到端价值闭环"
# + 业界扩展。命中 ≥ 1 个 → logic / industry_sense 维度 cap ≤ 3
_TRANSLATION_PHRASES = (
    'leveraged', 'synergy', 'synergies', 'end-to-end', 'value-driven',
    'spearheaded', 'stakeholder alignment', 'cross-functional',
    '端到端价值闭环', '颠覆性洞察', '协同杠杆', '价值驱动赋能',
    '利益相关方对齐', '跨职能协同',
)

# 跨专业工程/化学/物理术语 — 命中 ≥ 5 个 + target 含"金融/投研/投行/资管"等
# → job_fit 强制 ≤ 3 (baseline M11 化工本投公募大消费 case)
_ENG_TERMS = (
    'Ni', 'Al2O3', 'MDI', 'DCS', 'TPR', 'XRD', 'BET', 'CO2', '催化剂',
    '中试', '装置', '反应釜', '吸附', '裂解', '甲烷化', '脱硫', '蒸馏',
    '焊接', '冲压', '热处理', '齿轮', '减速器', '伺服', 'PLC',
    '电池', '电芯',  # 注意: 电池可能命中真实新能源研究, 加权时考虑
)
_FINANCE_TARGETS = (
    '金融', '投研', '行研', '投行', 'IBD', '资管', '公募', '私募', '券商',
    '基金', '研究员', '行业研究', '战略投资', '战略发展',
    # 2026-05-21 Day 8 baseline v4 抓到 — corp dev / M&A / 战略发展部 也算金融岗,
    # 否则化工本想转 corp dev 的跨专业 mismatch 不会触发 job_fit cap
    'corp dev', 'M&A', 'MA', '战略', 'strategy', '产业基金',
)


def _apply_pattern_caps(dim_scores: list[dict], user_answer: str, target_job: str) -> list[dict]:
    """Post-LLM cap based on regex pattern hits in user_answer.

    Returns new dim_scores list with cap applied (cap = min(orig, 3)).
    LLM 评分高但候选人答里满是模板词 / 翻译腔 / 跨专业 → 强制压低对应维度。
    """
    if not user_answer:
        return dim_scores

    template_hits = sum(1 for w in _TEMPLATE_WORDS if w in user_answer)
    translation_hits = sum(1 for p in _TRANSLATION_PHRASES if p.lower() in user_answer.lower())
    eng_hits = sum(1 for t in _ENG_TERMS if t in user_answer)
    target_is_finance = any(t in (target_job or '') for t in _FINANCE_TARGETS)

    caps: dict[str, int] = {}
    # 2026-05-21 Day 8 baseline v4 调阈值 — 原 ≥ 3 误伤金融研报正常用词:
    # P8 (strong 公募行研) 真实 thesis 答里也用 '主导/复盘/闭环' = 3 命中, 被误 cap.
    # baseline v3 M9 (真套模板) = 6 命中, P1 strong = 2, P5 strong = 1 → 阈值 ≥4 完美区分.
    # 2026-05-22 Day 9 PR-1: 套模板 / 翻译腔 都同时 cap expression_depth — 套模板词代表
    # 候选人答非"具体动作 + 方法论推导", 表达深度也要压下来。
    if template_hits >= 4:
        caps['info_selection'] = 3
        caps['logic'] = 3
        caps['expression_depth'] = 3
    if translation_hits >= 1:
        caps['logic'] = min(caps.get('logic', 10), 3)
        caps['industry_sense'] = 3
        caps['expression_depth'] = min(caps.get('expression_depth', 10), 4)
    if eng_hits >= 5 and target_is_finance:
        caps['job_fit'] = 3

    if not caps:
        return dim_scores

    out = []
    for d in dim_scores:
        new_d = dict(d)
        cap = caps.get(d.get('id'))
        if cap is not None and d.get('score', 10) > cap:
            new_d['score'] = cap
            existing_reason = (d.get('reason') or '').strip()
            reason_addon = ''
            if d['id'] == 'expression_depth' and template_hits >= 4:
                reason_addon = f' [⚠️ 后处理 cap ≤{cap}: 答题含 {template_hits} 个套模板词, STAR-M 的 Action 段被模板词占满]'
            elif d['id'] == 'expression_depth' and translation_hits >= 1:
                reason_addon = f' [⚠️ 后处理 cap ≤{cap}: 答题含翻译腔, 表达深度被英文管理黑话替代]'
            elif d['id'] in ('info_selection', 'logic') and template_hits >= 3:
                reason_addon = f' [⚠️ 后处理 cap ≤{cap}: 答题含 {template_hits} 个套模板词]'
            elif d['id'] in ('logic', 'industry_sense') and translation_hits >= 1:
                reason_addon = f' [⚠️ 后处理 cap ≤{cap}: 答题含翻译腔/英文管理黑话]'
            elif d['id'] == 'job_fit' and eng_hits >= 5:
                reason_addon = f' [⚠️ 后处理 cap ≤{cap}: 答题 {eng_hits} 个工程术语 + target 是金融, 无转译]'
            new_d['reason'] = (existing_reason + reason_addon).strip()
        out.append(new_d)
    return out
