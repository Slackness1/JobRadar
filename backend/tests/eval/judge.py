"""LLM-as-judge for 4 metrics (Phase 1, 投研 v1)。

每个 metric 一个 judge 函数,共用 mimo-v2.5-pro client。0-3 评分:
  0 = 错的 / 不安全 / 跳到完全无关方向
  1 = 部分对 / 泛泛 / 沾边
  2 = 对
  3 = 对 + 具体 / 有洞察 / 击中关键

评测全部 JSON 输出。MiMo response_format json_object 没保证一定生效,
所以 _parse_score 兜底 — 散文里抠 JSON 块、解析失败标 concerns。
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from tests.eval.clients import LLMClient

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Score:
    metric: str
    score: int             # 0-3
    reasoning: str
    concerns: list[str]    # 额外 flag,可空


# ── Track Relevance ────────────────────────────────────────────────────────

_TRACK_RELEVANCE_SYSTEM = """\
你是中文校招面试评测员。只评估一个问题:推荐的岗位轨道,跟候选人真实匹配方向是否一致?

评分:
  0 = 完全偏离 (推"销售"给量化候选人)
  1 = 沾边但不准 (推"投顾"给想做行研的候选人)
  2 = 匹配方向对 (推"行研"给想做行研的候选人)
  3 = 匹配且区分度高 (推荐对应细分如"消费行研"匹配"消费方向")

评分依据 (按优先级):
  - student_anchors.expected_strong_match_tracks 命中 → 3
  - student_anchors.expected_transferable_tracks 命中 → 2
  - student_anchors.expected_gap_tracks 命中 → 0 或 1 (取决于推荐 tier)
  - 都没命中:自己判断

只输出严格 JSON,无前后散文,无 markdown fence:
  {"score": 0-3, "reasoning": "30-100 字 中文", "concerns": ["可空"]}
"""


def judge_track_relevance(
    *,
    judge: LLMClient,
    student_anchors: dict,
    jd: dict,
    recommendation_item: dict,
) -> Score:
    user_payload = json.dumps(
        {
            "student_anchors": student_anchors,
            "jd_expected_track": jd.get("expected_track"),
            "jd_company": jd.get("job", {}).get("company"),
            "jd_title": jd.get("job", {}).get("job_title"),
            "recommendation_item": {
                "matched_track_label": recommendation_item.get("matched_track_label"),
                "final_score": recommendation_item.get("final_score"),
                "tier": recommendation_item.get("tier_label") or recommendation_item.get("target_direction"),
            },
        },
        ensure_ascii=False,
    )
    raw = judge.chat(
        messages=[
            {"role": "system", "content": _TRACK_RELEVANCE_SYSTEM},
            {"role": "user", "content": user_payload},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    return _parse_score(raw, metric="track_relevance")


# ── Fit Explanation Quality ────────────────────────────────────────────────

_FIT_EXPLANATION_SYSTEM = """\
你是中文校招面试评测员。只评估一个问题:推荐理由 (why_recommended / strengths / risks)
写得多具体、多有洞察。

评分:
  0 = 空洞或错误 ("简历不错","背景合适")
  1 = 泛泛 ("有金融背景,适合做投研")
  2 = 引用了 profile 里 1-2 个具体事实 (如 "CFA Level 1 + 中信实习")
  3 = 引用 ≥3 个具体事实,且区分了 强匹配 / 可迁移 / 差距,带因果解释

判断要点:
  - why_recommended / strengths / risks 是不是引用了 profile_summary 里出现的
    company / project / skill / award
  - risks 是不是真的指出了 gap,而不是说"建议多积累经验"这种万能话

只输出严格 JSON,无前后散文:
  {"score": 0-3, "reasoning": "30-150 字 中文", "concerns": ["可空"]}
"""


def judge_fit_explanation_quality(
    *,
    judge: LLMClient,
    student_profile: dict,
    jd: dict,
    recommendation_item: dict,
) -> Score:
    user_payload = json.dumps(
        {
            "student_profile_summary": _summarize_profile_for_judge(student_profile),
            "jd_company": jd.get("job", {}).get("company"),
            "jd_title": jd.get("job", {}).get("job_title"),
            "recommendation_item": {
                "why_recommended": recommendation_item.get("why_recommended"),
                "strengths": recommendation_item.get("strengths"),
                "risks": recommendation_item.get("risks"),
                "matched_track_label": recommendation_item.get("matched_track_label"),
            },
        },
        ensure_ascii=False,
    )
    raw = judge.chat(
        messages=[
            {"role": "system", "content": _FIT_EXPLANATION_SYSTEM},
            {"role": "user", "content": user_payload},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    return _parse_score(raw, metric="fit_explanation_quality")


# ── Evidence Groundedness ──────────────────────────────────────────────────

_EVIDENCE_SYSTEM = """\
你是中文简历改写评测员。只评估一个问题:改写后的 bullets,是不是把 profile 里
**已有**的 evidence 用得更好,没引入 profile 里**找不到**的事实/数字/经历?

评分:
  0 = 引入了 profile 没有的事实 / 数字 (编造)
  1 = 没编造但失去了关键 evidence (改完反而更空)
  2 = 保留了原 evidence,改写更顺
  3 = 调用了 profile 里**别处的** evidence (如把 award 融进 bullets),改写更扎实

判断要点:
  - evidence_keywords 里的关键词在 improved 里出现了几个
  - fabrication_traps 里点出的字段,improved 里有没有冒出新数字 / 新事实
  - improved 是不是把 original 的具体事实(数字 / 公司 / 项目)抹掉了

只输出严格 JSON,无前后散文:
  {"score": 0-3, "reasoning": "30-150 字", "concerns": ["编造|留白|抹掉证据" 等关键词]}
"""


def judge_evidence_groundedness(
    *,
    judge: LLMClient,
    student_profile: dict,
    student_anchors: dict,
    rewrite_option: dict,
) -> Score:
    user_payload = json.dumps(
        {
            "evidence_keywords": student_anchors.get("evidence_keywords", []),
            "fabrication_traps": student_anchors.get("fabrication_traps", []),
            "profile_summary": _summarize_profile_for_judge(student_profile),
            "rewrite": {
                "field_path": rewrite_option.get("field_path"),
                "original": rewrite_option.get("original"),
                "improved": rewrite_option.get("improved"),
                "warning": rewrite_option.get("warning"),
            },
        },
        ensure_ascii=False,
    )
    raw = judge.chat(
        messages=[
            {"role": "system", "content": _EVIDENCE_SYSTEM},
            {"role": "user", "content": user_payload},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    return _parse_score(raw, metric="evidence_groundedness")


# ── Follow-up Quality ──────────────────────────────────────────────────────

_FOLLOWUP_SYSTEM = """\
你是资深的中文校招面试官。你的工作是评估另一位面试官提出的 follow-up 问题。

只评估一个问题:这个 follow-up 是不是钉死在候选人**当前讲的项目**上,
且追问了候选人**漏讲的关键维度**(痛点 / 量化 / 取舍 / 风险)?

评分:
  0 = follow-up 跳到了候选人简历里的另一段经历,或问了完全无关的话题
       (尤其是命中了 expected_followup_targets_must_avoid 里的模式)
  1 = follow-up 在当前项目里,但太泛 ("能不能多讲讲","你觉得风险是什么")
  2 = follow-up 在当前项目里,且追问了一个具体维度
  3 = follow-up 在当前项目里,精准击中 expected_followup_targets 里的某一项

输入字段:
  - current_main_question + current_main_answer = 候选人正在讲的项目
  - expected_followup_targets = 期望击中的方向 (任一即可)
  - expected_followup_targets_must_avoid = 跳到这些就 0 分
  - generated_followup = 待评估的 follow-up 问题

只输出严格 JSON,无前后散文:
  {"score": 0-3, "reasoning": "30-150 字", "concerns": ["跳跃|泛泛|偏题|命中 must_avoid" 等]}
"""


def judge_followup_quality(
    *,
    judge: LLMClient,
    fixture: dict,
    generated_followup: str,
) -> Score:
    user_payload = json.dumps(
        {
            "current_main_question": fixture.get("current_main_question"),
            "current_main_answer": fixture.get("current_main_answer"),
            "expected_followup_targets": fixture.get("expected_followup_targets", []),
            "expected_followup_targets_must_avoid": fixture.get("expected_followup_targets_must_avoid", []),
            "generated_followup": generated_followup,
        },
        ensure_ascii=False,
    )
    raw = judge.chat(
        messages=[
            {"role": "system", "content": _FOLLOWUP_SYSTEM},
            {"role": "user", "content": user_payload},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    return _parse_score(raw, metric="followup_quality")


# ── 解析 + 摘要 helpers ────────────────────────────────────────────────────


_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL | re.IGNORECASE)


def _parse_score(raw: str, *, metric: str) -> Score:
    """从 LLM 输出里解析 Score。容忍 markdown fence + 散文前后裹的 JSON。

    用 json.JSONDecoder().raw_decode() 找首个合法 JSON 对象 — 不用 greedy regex
    (旧版 r'\{.*\}' 会被 reasoning 里的嵌套 {} 截废)。
    """
    raw = raw.strip()
    # 1. 剥 markdown fence (```json ... ``` 或 ``` ... ```)
    fenced = _FENCE_RE.match(raw)
    if fenced:
        raw = fenced.group(1).strip()

    decoder = json.JSONDecoder()
    data: dict | None = None

    # 2. 找第一个 '{' 开始 raw_decode
    idx = raw.find("{")
    if idx >= 0:
        try:
            data, _ = decoder.raw_decode(raw[idx:])
        except json.JSONDecodeError:
            data = None

    if not isinstance(data, dict):
        logger.warning("[%s] judge 返回无法解析: %s", metric, raw[:200])
        return Score(
            metric=metric,
            score=0,
            reasoning=f"<解析失败,原文片段: {raw[:80]}>",
            concerns=["judge_parse_failed"],
        )
    try:
        score_val = int(data.get("score", 0))
    except (TypeError, ValueError):
        score_val = 0
    return Score(
        metric=metric,
        score=max(0, min(3, score_val)),
        reasoning=str(data.get("reasoning", "")).strip(),
        concerns=list(data.get("concerns") or []),
    )


def _summarize_profile_for_judge(profile: dict) -> dict:
    """给 judge 看的紧凑 profile 摘要 — 减少 token,只留 evidence 字段。"""
    return {
        "headline": (profile.get("basic_info") or {}).get("headline"),
        "candidate_summary": profile.get("candidate_summary"),
        "education_schools": [e.get("school") for e in (profile.get("education") or [])],
        "internship_companies": [
            f"{i.get('company')} · {i.get('role')}" for i in (profile.get("internships") or [])
        ],
        "internship_bullets": [
            b for i in (profile.get("internships") or []) for b in (i.get("bullets") or [])
        ],
        "project_names": [p.get("name") for p in (profile.get("projects") or [])],
        "skills_technical": (profile.get("skills") or {}).get("technical"),
        "awards": profile.get("awards"),
        "inferred_tracks": profile.get("inferred_tracks"),
    }
