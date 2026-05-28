"""Phase G 工序 4 — Multi-pass C sub_cat enrichment with knowledge base RAG.

设计 (per spec Section 4 工序 4):
- Pass 1: 7 大类 strategy_type 分类 — 搜索空间小, 用 Flash 即可 (cost 优化, 2026-05-28)
- Pass 2: 在该 strategy 下 4-5 个 sub_cat + 知识库 hard_req/工作样态/典型公司 选最匹配
  → Pro reasoning_effort=high (核心判定, 保留)

Output dict (caller 写 DB):
  sub_category / sub_category_secondary / industry_focus (JSON array str) /
  institution_tier / sub_cat_confidence (geo mean of two pass) / sub_cat_reasoning
"""
from __future__ import annotations

import json
import logging
from typing import Any

import app.config  # noqa: F401

from app.database import SessionLocal
from app.models import Job, KnowledgeSubcategory
from app.services.crawler_llm import (
    build_flash_client,
    build_pro_client,
    flash_model_name,
    pro_model_name,
)
from app.services.phase_g.knowledge_synthesis import SUBCAT_TO_STRATEGY

log = logging.getLogger(__name__)

# 跟 knowledge_synthesis.py SUBCAT_TO_STRATEGY 字面对齐 — 注意 "AI 应用_PM_开发" 中间有空格
STRATEGY_TYPES: tuple[str, ...] = (
    "基本面权益",
    "量化",
    "固定收益",
    "卖方研究",
    "多资产_FOF_衍生品",
    "相关补充",
    "AI 应用_PM_开发",
)


PASS1_SYSTEM_PROMPT = """你是中国金融+AI 校招岗位分类器。给你一个岗位 JD,选出最匹配的 1 个 strategy_type 大类:

- 基本面权益: 公募 / 主观私募的权益研究员, 行业研究, 指数研究, 中后台
- 量化: 量化研究员 (中频/高频), 量化开发 QD, AI 量化, 因子工程师
- 固定收益: 信用研究, 固收交易, 固收+多资产, 利率宏观策略
- 卖方研究: 券商研究所卖方研究员, 投行 IBD, 买方 Quant
- 多资产_FOF_衍生品: 资管 FOF, 自营 FOF, 财富 FOF, 结构化衍生品
- 相关补充: PE 投后, VC 行研
- AI 应用_PM_开发: LLM 算法 (post-train), Agent 工程师, 多模态推理优化, AI PM, AI 算法业务

如果岗位明显不属于上述任何一类 (e.g. 银行总行综合管培、央企工程师、零售运营、教育/医疗
非投研岗),输出 strategy_type=null,confidence=0。

输出 JSON: {"strategy_type": "<7 大类名 或 null>", "confidence": <0-1>, "reasoning": "<≤60 字>"}"""


PASS2_SYSTEM_PROMPT_TEMPLATE = """你是中国金融+AI 校招岗位 sub_cat 分类器。给你一个岗位 JD + 该 strategy_type 大类下的全部 sub_cat 知识库,选出最匹配的 1 个 sub_cat (主) + 可选 1 个 secondary。

Strategy type: {strategy_type}

候选 sub_cats (含硬门槛 / 工作样态 / 典型公司 / 候选 industry_focus / institution_tier):
{candidates_text}

判定规则:
- 主 sub_cat: 岗位 JD 跟该 sub_cat 的硬门槛 + 工作样态匹配度最高的
- secondary: 仅当岗位明显跨 sub_cat 时填 (e.g. 中金 TMT 既卖方研究又跨买方 quant),否则填 null
- industry_focus: 从该 sub_cat 的 industry_focus_candidates 词表选 1-3 个最 fit 的
- institution_tier: 从该 sub_cat 的 institution_tier_candidates 词表选 1 个最 fit 的, 看公司名

输出 JSON:
{{
  "sub_category": "<sub_cat 名, 必须在 候选列表 内>",
  "sub_category_secondary": "<sub_cat 名 或 null>",
  "industry_focus": ["..."],
  "institution_tier": "...",
  "confidence": <0-1>,
  "reasoning": "<≤80 字, 说明判定理由>"
}}"""


def _build_job_user_msg(job_dict: dict[str, Any]) -> str:
    return (
        f"公司: {job_dict.get('company', '')}\n"
        f"标题: {job_dict.get('job_title', '')}\n"
        f"职责: {(job_dict.get('job_duty') or '')[:1500]}\n"
        f"要求: {(job_dict.get('job_req') or '')[:1500]}"
    )


def pass1_classify_strategy(
    job_dict: dict[str, Any], *, use_flash: bool = True,
) -> dict[str, Any]:
    """Pass 1: 7 大类分类。

    use_flash=True (默认) — 用 Flash non-thinking, 7-way 分类够用且省钱 ($0.0003 vs Pro $0.0014/call)。
    use_flash=False — Pro reasoning_effort=high, 复杂 case (e.g. 战略管培 vs 投行 IBD 边界) 时切回。
    """
    if use_flash:
        client = build_flash_client()
        resp = client.chat.completions.create(
            model=flash_model_name(),
            messages=[
                {"role": "system", "content": PASS1_SYSTEM_PROMPT},
                {"role": "user", "content": _build_job_user_msg(job_dict)},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
    else:
        client = build_pro_client()
        resp = client.chat.completions.create(
            model=pro_model_name(),
            messages=[
                {"role": "system", "content": PASS1_SYSTEM_PROMPT},
                {"role": "user", "content": _build_job_user_msg(job_dict)},
            ],
            extra_body={"reasoning_effort": "high"},
            response_format={"type": "json_object"},
            temperature=0.1,
        )
    parsed = json.loads(resp.choices[0].message.content or "{}")
    st = parsed.get("strategy_type")
    if st is not None and st not in STRATEGY_TYPES:
        # LLM 偶尔会瞎写, 当 null 处理
        log.debug("pass1 unknown strategy %r → treat as null", st)
        st = None
        parsed["confidence"] = 0
    parsed["strategy_type"] = st
    try:
        parsed["confidence"] = float(parsed.get("confidence") or 0)
    except (TypeError, ValueError):
        parsed["confidence"] = 0
    return parsed


def _gather_subcat_candidates(strategy_type: str) -> tuple[list[str], str]:
    """从 knowledge_subcategories 表拉本 strategy 下的所有 sub_cat 候选文本。"""
    subcats_in_strategy = [
        sc for sc, st in SUBCAT_TO_STRATEGY.items() if st == strategy_type
    ]
    db = SessionLocal()
    try:
        rows = (
            db.query(KnowledgeSubcategory)
            .filter(KnowledgeSubcategory.sub_cat.in_(subcats_in_strategy))
            .all()
        )
        parts: list[str] = []
        for r in rows:
            try:
                payload = json.loads(r.payload_json)
            except json.JSONDecodeError:
                continue
            companies = [c.get("name", "") for c in payload.get("typical_companies") or []][:6]
            parts.append(
                f"### {r.sub_cat}\n"
                f"- 硬门槛: {' / '.join((payload.get('hard_requirements') or [])[:3])}\n"
                f"- 工作样态: {(payload.get('interview_style') or '')[:200]}\n"
                f"- 典型公司: {', '.join(companies)}\n"
                f"- industry_focus_candidates: {payload.get('industry_focus_candidates') or []}\n"
                f"- institution_tier_candidates: {payload.get('institution_tier_candidates') or []}"
            )
        return subcats_in_strategy, "\n\n".join(parts) or "(知识库空)"
    finally:
        db.close()


def pass2_classify_subcat(
    job_dict: dict[str, Any], strategy_type: str
) -> dict[str, Any]:
    """Pass 2: 在该 strategy 下选 sub_cat + industry + tier。"""
    client = build_pro_client()
    subcats, candidates_text = _gather_subcat_candidates(strategy_type)
    prompt = PASS2_SYSTEM_PROMPT_TEMPLATE.format(
        strategy_type=strategy_type, candidates_text=candidates_text
    )
    resp = client.chat.completions.create(
        model=pro_model_name(),
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": _build_job_user_msg(job_dict)},
        ],
        extra_body={"reasoning_effort": "high"},
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    parsed = json.loads(resp.choices[0].message.content or "{}")
    chosen = parsed.get("sub_category")
    if chosen and chosen not in subcats:
        # LLM 写了不存在的 sub_cat 名 → 兜底 None (caller 跳过)
        log.debug(
            "pass2 returned unknown sub_cat %r for strategy %r; valid: %s",
            chosen, strategy_type, subcats,
        )
        parsed["sub_category"] = None
        parsed["confidence"] = 0
    try:
        parsed["confidence"] = float(parsed.get("confidence") or 0)
    except (TypeError, ValueError):
        parsed["confidence"] = 0
    return parsed


def enrich_job_sub_cat(job: Job) -> dict[str, Any] | None:
    """Full Multi-pass C pipeline. Returns enrichment dict or None.

    Caller writes the result into Job 字段 (sub_category / sub_category_secondary /
    industry_focus / institution_tier / sub_cat_confidence / sub_cat_reasoning /
    sub_cat_enriched_at)。
    """
    job_dict = {
        "company": job.company or "",
        "job_title": job.job_title or "",
        "job_duty": job.job_duty or "",
        "job_req": job.job_req or "",
    }
    p1 = pass1_classify_strategy(job_dict)
    if not p1.get("strategy_type") or p1.get("confidence", 0) < 0.5:
        return None
    p2 = pass2_classify_subcat(job_dict, p1["strategy_type"])
    if not p2.get("sub_category") or p2.get("confidence", 0) < 0.3:
        return None
    combined = (p1["confidence"] * p2["confidence"]) ** 0.5
    return {
        "sub_category": p2["sub_category"],
        "sub_category_secondary": p2.get("sub_category_secondary"),
        "industry_focus": json.dumps(
            p2.get("industry_focus") or [], ensure_ascii=False
        ),
        "institution_tier": p2.get("institution_tier"),
        "sub_cat_confidence": combined,
        "sub_cat_reasoning": (
            f"P1[{p1['strategy_type']}, {p1.get('confidence', 0):.2f}]: "
            f"{p1.get('reasoning', '')[:60]} | "
            f"P2: {p2.get('reasoning', '')[:80]}"
        )[:300],
    }
