"""岗位情报卡组装器：job_id → 定位 + 3 维情报（带三维可信度徽章）+ provenance。

复用 xhs/retrieve.search 取该公司 UGC；维度抽取走 dimension_extract（LLM 可注入）。
磁盘缓存两层：
  - job_cards/   按 job_id 缓存整张卡（不变）
  - company_dims/ 按公司名 hash 缓存 LLM 抽取结果（同公司多 job 只跑一次 LLM）
测试时传 use_cache=False 不写盘。
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.models import Job, XhsInsight
from app.services.xhs import retrieve
from app.services.intel import positioning as _pos
from app.services.intel.source_score import platform_of
from app.services.intel.dimension_extract import extract_dimensions, _EMPTY
from app.services.intel.badge import synth_badge
from app.services.intel.corroboration import independent_cross

# 绝对化路径（对齐 enrichment.py 的 parents[3]=backend/），不依赖运行时 CWD。
_CACHE_DIR = str(Path(__file__).resolve().parents[3] / "data" / "_intel_cache" / "job_cards")
_COMPANY_CACHE_DIR = str(Path(__file__).resolve().parents[3] / "data" / "_intel_cache" / "company_dims")


def _cache_path(job_id: int) -> str:
    return os.path.join(_CACHE_DIR, f"{job_id}.json")


def _company_cache_path(company: str) -> str:
    key = hashlib.md5(company.encode()).hexdigest()
    return os.path.join(_COMPANY_CACHE_DIR, f"{key}.json")


def _company_dims(
    company: str,
    insights: list,
    *,
    llm_fn: Optional[Callable[[str], dict]],
    use_cache: bool,
) -> dict:
    """按公司名缓存 LLM 维度抽取结果，同公司多 job 只跑一次 LLM。

    - 命中公司缓存 → 直接返回（不调 llm_fn）
    - llm_fn 为 None → 返回空骨架（不写缓存）
    - llm_fn 非 None → extract_dimensions 并写公司缓存
    """
    cache_path = _company_cache_path(company)

    if use_cache and os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)

    if llm_fn is None:
        return copy.deepcopy(_EMPTY)

    dims = extract_dimensions(insights, llm_fn=llm_fn, company=company)

    if use_cache:
        os.makedirs(_COMPANY_CACHE_DIR, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(dims, f, ensure_ascii=False)

    return dims


def _tier_from_insights(dim_ids: list, by_id: dict) -> dict:
    """用该维度引用的 insight_ids 算 source_score / content_tier / cross / badge。"""
    rows = [by_id[i] for i in (dim_ids or []) if i in by_id]
    if not rows:
        return {
            "source_score": 0.0,
            "content_tier": "low",
            "cross": "single",
            "badge": 1,
            "n": 0,
        }
    avg_src = round(
        sum((r.get("source_score") or 0.0) for r in rows) / len(rows), 3
    )
    best_tier = (
        "high"
        if any(r.get("confidence") == "high" for r in rows)
        else (
            "med"
            if any(r.get("confidence") == "med" for r in rows)
            else "low"
        )
    )
    sibs = [
        {
            "note_id": r.get("insight_id", ""),
            "author": (r.get("source") or {}).get("author", ""),
        }
        for r in rows
    ]
    cross = independent_cross(sibs)
    badge = synth_badge(
        source_score=avg_src, content_tier=best_tier, cross=cross, n=len(rows)
    )
    return {
        "source_score": avg_src,
        "content_tier": best_tier,
        "cross": cross,
        "badge": badge,
        "n": len(rows),
    }


def build_job_card(
    db: Session,
    job_id: int,
    *,
    use_cache: bool = True,
    llm_fn: Optional[Callable[[str], dict]] = None,
) -> dict:
    """组装一张岗位情报卡。

    Args:
        db: SQLAlchemy session（调用方负责关闭）。
        job_id: jobs 表主键。
        use_cache: 是否读写磁盘缓存（测试时传 False）。
        llm_fn: prompt(str) -> dict，可注入 fake 或真实 LLM。
                传 None 时跳过 LLM 抽取，intel 三维全部返回空骨架。

    Returns:
        结构化 dict，包含 positioning / intel / provenance 三块。
    """
    if use_cache and os.path.exists(_cache_path(job_id)):
        with open(_cache_path(job_id), encoding="utf-8") as f:
            return json.load(f)

    job = db.query(Job).filter_by(id=job_id).first()
    if not job:
        return {"job_id": job_id, "_status": "not_found"}

    job_d = {
        "company": job.company,
        "job_title": job.job_title,
        "department": job.department,
        "sub_category": job.sub_category,
        "institution_tier": job.institution_tier,
    }
    pos = _pos.build_positioning(job_d)

    # ---- 取 UGC insights（按公司名检索）----
    # company 参数接受 list[str]，真实签名已确认
    insights = retrieve.search(db, company=[job.company or ""], limit=20)

    # ---- 关键修正①：retrieve.search 不返回 source_score，回 DB 批量补查并 attach ----
    ids = [i["insight_id"] for i in insights]
    if ids:
        score_map = {
            iid: sc
            for iid, sc in db.query(
                XhsInsight.insight_id, XhsInsight.source_score
            )
            .filter(XhsInsight.insight_id.in_(ids))
            .all()
        }
        for ins in insights:
            ins["source_score"] = score_map.get(ins["insight_id"]) or 0.0

    by_id = {i["insight_id"]: i for i in insights}

    # ---- LLM 维度抽取（按公司缓存，可注入 fake）----
    dims = _company_dims(
        job.company or "",
        insights,
        llm_fn=llm_fn,
        use_cache=use_cache,
    )

    # ---- 每维度组装：可信度层 + 引文摘要 ----
    intel: dict = {}
    for name in ("threshold", "compensation", "outlook"):
        d = dims[name]
        conf = _tier_from_insights(d.get("support_ids") or [], by_id)
        quotes = [
            {
                "text": by_id[i].get("source_quote", ""),
                # 关键修正②：source 子结构无 platform 键，用 platform_of(insight_id) 推导
                "source": platform_of(i),
                "author": (by_id[i].get("source") or {}).get("author", ""),
            }
            for i in (d.get("support_ids") or [])[:2]
            if i in by_id
        ]
        intel[name] = {
            **{k: v for k, v in d.items() if k != "support_ids"},
            **conf,
            "quotes": quotes,
        }

    # ---- provenance ----
    sources = sorted({platform_of(i["insight_id"]) for i in insights})
    card = {
        "job_id": job_id,
        "company": job.company,
        "role_title": job.job_title,
        "positioning": pos,
        "intel": intel,
        "provenance": {
            "label": "学生 UGC 参考 · 非官方",
            "n_insights": len(insights),
            "sources": sources,
        },
    }

    if use_cache:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        with open(_cache_path(job_id), "w", encoding="utf-8") as f:
            json.dump(card, f, ensure_ascii=False)

    return card
