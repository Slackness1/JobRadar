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
你是中文校招面试评测员。评估 SUT(JobRadar 推荐引擎)对一个 (候选人 × JD) 的轨道判断是否准确。

**关键原则**: SUT 自己会给 `tier_label` ('强匹配'/'可迁移'/'有差距') 和 `final_score` (0-100)。
判分**必须**综合看 SUT 推的 track + tier/score 是否自洽,而不是只看 track 命中哪个 anchor。

**13 个 canonical finance tracks** (2026-05-23 重构: 拆 二级买方/卖方·S&T/一级市场,
咨询合并再拆。跟 JobRadar app.services.taxonomy 对齐 — JD 带 `jd_canonical_track`):
  1. 公募/资管·投研          (公募 / 保险资管 / 券商资管 / 银行理财子)
  2. 私募·基本面             (阳光私募 / 长短仓 / 对冲基金基本面)
  3. 量化                    (头部私募 quant / 大基金量化部 / 外资 HF)
  4. 卖方研究                (券商研究所 sell-side equity research)
  5. S&T·FICC·衍生品         (Sales & Trading / FICC / Global Markets / 衍生品)
  6. 投行·并购·资本市场      (IBD / M&A / ECM / DCM)
  7. 一级股权·PE/VC          (PE / VC / Buyout / Growth / 产业基金 / CVC)
  8. 银行·总行核心            (国大/股份/政策行/外管/交易所/金融基础设施)
  9. 监管·体制内             (央行/证监会/银保监/国资委/中央汇金/社保)
 10. 金融科技                (蚂蚁/微众/京东数科/跨境支付)
 11. 咨询·MBB+Tier2          (MBB / 罗兰贝格 / Oliver Wyman / 科尔尼 / 四大 FAS)
 12. 企业战略·管培·实业金融  (互联网战略部 / 实业管培 / 集团投融资部 / 战投)
 13. 大宗·能源              (LDC / Cargill / 托克 / 中石油国际 / 远景动力)

SUT 推的 matched_track_label 若不在这 13 个里,通常说明 SUT 还在用 free-text(eg "公募基金/研究"
而不是 canonical "公募/资管·投研")。把这种当作"接近但未完全对齐"处理,不算 0 分。

评分:
  3 = 推到 expected_strong_match_tracks 且 tier='强匹配' (识别精准,SUT 自信且对)
  2 = 推到 expected_strong_match_tracks 但 tier='可迁移' (低估了)
       或 推到 expected_transferable_tracks 且 tier='可迁移' (中等,SUT 自洽)
  1 = 推到 expected_transferable_tracks 但 tier='有差距' (低估了)
       或 推到 expected_gap_tracks 但 tier='有差距' + final_score < 50 (SUT 自己承认 gap → 合理处理)
  0 = 推到 expected_gap_tracks 但 tier='强匹配' 或 final_score ≥ 60 (SUT 错认 gap 为强匹配 → 真 bug)
       或 推到完全无关方向 (不在 strong/transferable/gap 任何一个里)

**简单口诀**:
  - SUT 推 gap track + 自己说"有差距" → **1 分**(合理识别,production 会过滤掉低分)
  - SUT 推 gap track + 自信说"强匹配" → **0 分**(真 bug)
  - SUT 推 strong_match + 说"强匹配" → 3 分
  - SUT 推 strong_match + 谦虚说"可迁移" → 2 分(低估)

**JSON 转义硬约束**:reasoning 等字段内任何引文用中文方括号 「」 包,
**不要**在字段值里嵌套英文双引号 "" — 会破坏 JSON 解析。
例: ✅ "reasoning": "follow-up 击中候选人「DCF 概率权重」钩子"
    ❌ "reasoning": "follow-up 击中候选人"DCF 概率权重"钩子"

只输出严格 JSON,无前后散文,无 markdown fence:
  {"score": 0-3, "reasoning": "30-100 字 中文,**必须**提及 tier 和你的判断逻辑", "concerns": ["可空"]}
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
            "jd_canonical_track": jd.get("canonical_track"),   # Phase E: 8 canonical 显式 enum
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


# ── Feedback Specificity ───────────────────────────────────────────────────
# Phase C: 评估 InterviewReport 的 highlights/improvements 是否引用候选人原话
# + 是否给可执行 action。配合 prompts/scoring_system.md + report.py 的引用约束。

_FEEDBACK_SPECIFICITY_SYSTEM = """\
你是资深的中文校招面试评估官,review 另一位评估官给候选人写的面试报告 (highlights +
improvements + overall_comment) 是否 specific。

**Specific 的定义** (按 Phase A 强化后的 prompt 标准):
  - highlights 每条必须用 「」 引用候选人答案里的**逐字片段** (eg 「用户增长 30% 但
    留存 8%」),让用户能 trace 到具体 turn
  - improvements 每条必须含 3 件事:(1) 引用问题位置 (eg "在第 3 题谈数据治理时")
    + (2) 用 「」 引候选人弱点原话 + (3) 给"可以这样改"的完整替换话术
  - overall_comment 至少 1 个具体优势引文 + 1 个具体短板

评分 (整份报告综合判,不是单条):
  0 = 全是空话, 0 个 「」 引文, improvements 是 "建议加强 X" 这种泛指
  1 = 偶尔有引文 (<30% 命中标准), improvements 大多是泛建议没具体话术
  2 = 多数 (50-80%) 条目有 「」 引文 + 具体话术, 个别空话
  3 = 几乎所有条目 (>80%) 都有「逐字引用」+ 具体可替换话术,且引文确实在 transcript 内可找到

**反 fabrication 检查 (任何一条违规 = 总分至多 1 分):**
  - 「」 引文必须能在 transcript 里**逐字找到**。如果引文是评估官杜撰的,降到 0-1 分。
  - 若 improvements 引文不存在,降 1 级。

**JSON 转义硬约束**:reasoning 等字段内任何引文用中文方括号 「」 包,
**不要**在字段值里嵌套英文双引号 "" — 会破坏 JSON 解析。
例: ✅ "reasoning": "follow-up 击中候选人「DCF 概率权重」钩子"
    ❌ "reasoning": "follow-up 击中候选人"DCF 概率权重"钩子"

只输出严格 JSON,无前后散文,无 markdown fence:
  {"score": 0-3,
   "reasoning": "100-200 字, 必须举 1-2 个具体 highlights/improvements 例子说明",
   "specific_count": <用引文的条目数>,
   "vague_count": <无引文/空话条目数>,
   "fabricated_quotes": [<列出 transcript 中不存在的引文,可空>],
   "concerns": ["全空话|多空话|有杜撰|引文跑偏" 等]}
"""


def judge_feedback_specificity(
    *,
    judge: LLMClient,
    transcript: list[dict],   # [{"role": "interviewer"|"candidate", "content": str}]
    report: dict,             # {"highlights": [...], "improvements": [...], "overall_comment": "..."}
) -> Score:
    """评估 report 是否引用候选人原话 + 给可执行 action。"""
    # transcript 可能很大 — 给 judge 一个紧凑版,标 turn 编号方便引文对照
    compact_transcript = []
    cand_turn = 0
    for m in transcript:
        role = m.get("role", "")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role in ("candidate", "user"):
            cand_turn += 1
            compact_transcript.append(f"[候选人 T{cand_turn}] {content[:600]}")
        elif role in ("interviewer", "assistant"):
            compact_transcript.append(f"[面试官] {content[:300]}")

    user_payload = json.dumps(
        {
            "transcript": "\n".join(compact_transcript),
            "report": {
                "highlights": report.get("highlights") or [],
                "improvements": report.get("improvements") or [],
                "overall_comment": report.get("overall_comment") or "",
            },
        },
        ensure_ascii=False,
    )
    raw = judge.chat(
        messages=[
            {"role": "system", "content": _FEEDBACK_SPECIFICITY_SYSTEM},
            {"role": "user", "content": user_payload},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    score = _parse_score(raw, metric="feedback_specificity")
    # 把额外字段 (specific_count / vague_count / fabricated_quotes) 塞 concerns
    # 方便 dump 到 baseline.json 不丢失
    try:
        extra = json.loads(raw.strip().split("```")[-1] if "```" in raw else raw)
        if isinstance(extra, dict):
            for key in ("specific_count", "vague_count", "fabricated_quotes"):
                v = extra.get(key)
                if v not in (None, [], ""):
                    score.concerns.append(f"{key}={v}")
    except Exception:
        pass
    return score


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
