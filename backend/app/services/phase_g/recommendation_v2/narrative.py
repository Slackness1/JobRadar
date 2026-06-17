"""Phase G v2 — 4 anchor 推荐叙事生成 (Pro reasoning_effort=medium)。

4 个 anchor 必须 ≥3 个被引用:
- Anchor A: 学生 hidden_highlight 真实 mention
- Anchor B: sub_cat hard_requirement 命中分析
- Anchor C: institution_tier 区分点 (引用知识库 verbatim)
- Anchor D: 差距分析 (gap, 具体补强建议)

输出 narrative 长度 ≤200 字; 引用知识库 verbatim 时不能改写。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.database import SessionLocal
from app.models import Job, KnowledgeSubcategory
from app.services.crawler_llm import build_interactive_client, interactive_model_name

log = logging.getLogger(__name__)


NARRATIVE_SYSTEM_PROMPT = """你是 SAIF 学院的资深求职顾问。给你一个学生 profile + 一个候选岗位 + 该岗位 sub_cat 的知识库摘要 + LLM rerank 给的 score & reasoning。请用 4 个 anchor 写推荐理由。

4 个 anchor (至少写 3 个, 每个 anchor 必须是**彼此不同、独立成段**的一句话, 严禁把同一句话复制到多个 anchor):
- Anchor A (赛道契合): 学生 hidden_highlight 真实 mention (e.g. "你独立做的 200 亿市值消费股深度报告")
- Anchor B (平台梯队): institution_tier 区分点 (e.g. "一线公募 vs 二线公募的留用差异" 必须引用知识库 verbatim 原文)
- Anchor C (岗位画像): sub_cat hard_requirement 命中分析 (e.g. "本岗硬门槛是 1 段公募投研实习, 你已有")
- Anchor D (不确定点): 差距分析 (gap, 具体补强建议; e.g. "你缺一次推票面练习, 用易方达内推+模拟面试补")

输出 JSON:
{
  "anchors": [
    {"key": "A", "text": "<赛道契合, ≤60 字, 第二人称'你'>"},
    {"key": "B", "text": "<平台梯队, ≤60 字, 与其它 anchor 内容不重复>"},
    {"key": "C", "text": "<岗位画像, ≤60 字>"},
    {"key": "D", "text": "<不确定点, ≤60 字>"}
  ],
  "narrative": "<把上面 anchor 串成一段 ≤200 字综合理由, 用于列表摘要>"
}
铁律: anchors 数组里每条 text 必须讲不同的事; 不准重复、不准复制粘贴同一句话。无法支撑的 anchor 直接省略该条, 不要为了凑数复制。"""


def _gather_kb_payload(sub_cat: str) -> dict[str, Any] | None:
    if not sub_cat:
        return None
    db = SessionLocal()
    try:
        row = db.query(KnowledgeSubcategory).filter_by(sub_cat=sub_cat).first()
        if not row:
            return None
        try:
            payload = json.loads(row.payload_json)
        except json.JSONDecodeError:
            return None
        payload["_data_confidence"] = row.data_confidence
        return payload
    finally:
        db.close()


def _build_user_msg(
    student_profile: dict[str, Any],
    job: Job,
    kb: dict[str, Any],
    llm_rerank: dict[str, Any] | None,
) -> str:
    parts: list[str] = []
    parts.append("## 学生")
    parts.append(f"name: {student_profile.get('name', '?')}")
    if student_profile.get("background"):
        parts.append(f"背景: {student_profile['background']}")
    highlights = student_profile.get("hidden_highlights") or []
    parts.append(f"hidden_highlights ({len(highlights)} 条):")
    for h in highlights:
        parts.append(f"  - {h}")
    parts.append("")
    parts.append("## 候选岗位")
    parts.append(f"公司: {job.company}")
    parts.append(f"标题: {job.job_title}")
    parts.append(f"sub_category: {job.sub_category}")
    parts.append(f"institution_tier: {job.institution_tier or '未知'}")
    parts.append("")
    parts.append("## 知识库摘要 (Anchor B/C 来源)")
    hard = (kb.get("hard_requirements") or [])[:4]
    parts.append("hard_requirements:")
    for h in hard:
        parts.append(f"  - {h}")
    tier_candidates = kb.get("institution_tier_candidates") or []
    parts.append(f"institution_tier_candidates: {tier_candidates}")
    verbatim = (kb.get("verbatim_quotes") or [])[:3]
    parts.append("verbatim_quotes (Anchor C 必须引用其中一条原文):")
    for v in verbatim:
        parts.append(f"  - {v.get('quote', '')}")
    pitfalls = (kb.get("pitfalls") or [])[:2]
    parts.append("pitfalls (Anchor D 差距 / 风险参考):")
    for p in pitfalls:
        parts.append(f"  - {p}")
    parts.append("")
    parts.append(f"## LLM rerank 给的 score & reasoning (作为 narrative 立意参考)")
    if llm_rerank:
        parts.append(f"score: {llm_rerank.get('score')}")
        parts.append(f"reasoning: {llm_rerank.get('reasoning')}")
    else:
        parts.append("(无 rerank 信息)")
    return "\n".join(parts)


def generate_narrative(
    student_profile: dict[str, Any],
    job: Job,
    *,
    llm_rerank: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """生成 4-anchor 推荐 narrative。无 KB 时返 placeholder, 不调 LLM。"""
    kb = _gather_kb_payload(job.sub_category or "")
    if kb is None:
        return {
            "narrative": "(本赛道知识库覆盖有限, 暂无个性化推荐理由)",
            "anchors_used": [],
            "kb_available": False,
        }
    # 2026-06-15: 交互链路改走官方 DeepSeek(中转并发限流太重),非推理模型不传 reasoning_effort。
    client = build_interactive_client(max_retries=1, timeout=60)
    user_msg = _build_user_msg(student_profile, job, kb, llm_rerank)
    resp = client.chat.completions.create(
        model=interactive_model_name(),
        messages=[
            {"role": "system", "content": NARRATIVE_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    parsed = json.loads(resp.choices[0].message.content or "{}")
    # 新 schema: anchors = [{key, text}, ...], 每条 text 必须不同。
    anchor_points: list[dict[str, str]] = []
    seen_texts: set[str] = set()
    raw_anchors = parsed.get("anchors")
    if isinstance(raw_anchors, list):
        for a in raw_anchors:
            if not isinstance(a, dict):
                continue
            key = str(a.get("key") or "").strip().upper()
            text = str(a.get("text") or "").strip()
            if key not in {"A", "B", "C", "D"} or not text:
                continue
            # 去重: 同一段文字只保留第一次出现, 杜绝"三条一样"
            norm = text.replace(" ", "")
            if norm in seen_texts:
                continue
            seen_texts.add(norm)
            anchor_points.append({"key": key, "text": text[:120]})
    # narrative 综合摘要; 旧 schema 兜底(没 narrative 时用 anchor 串接)
    narrative = str(parsed.get("narrative") or "")[:240]
    if not narrative and anchor_points:
        narrative = " ".join(p["text"] for p in anchor_points)[:240]
    anchors_used = [p["key"] for p in anchor_points]
    return {
        "narrative": narrative,
        "anchors_used": anchors_used,
        "anchor_points": anchor_points,
        "kb_available": True,
        "data_confidence": kb.get("_data_confidence"),
    }
