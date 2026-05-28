"""Phase G recommendation v2 — read-only API endpoints (gated by RECOMMENDATION_V2_ENABLED).

当前只暴露 /api/recommend-v2/companies-fallback (T18 公司 fallback)。
后续 T19 wire 时把 recall + scoring + rerank + narrative 串成 /api/recommend-v2/score。
"""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query

from app.services.phase_g.company_fallback import get_fallback_companies

router = APIRouter(prefix="/api/recommend-v2", tags=["phase_g_recommend_v2"])


def _enabled() -> bool:
    return os.environ.get("RECOMMENDATION_V2_ENABLED", "0") in {"1", "true", "True"}


@router.get("/companies-fallback")
def companies_fallback(
    sub_cat: str = Query(..., description="目标 sub_cat 名 (必须在 ground_truth 里)"),
    max_companies: int = Query(default=5, ge=1, le=20),
    must_have_only: bool = Query(default=True),
):
    """返回某 sub_cat 的 must_have 头部公司 fallback 卡片数据。

    返回 [{name, tier, must_have, status, season, verbatim_hint, active_jobs}]
    UI 渲染逻辑见 t8-crawler-handoff doc, frontend 用 amber-themed 卡片。
    """
    if not _enabled():
        raise HTTPException(
            status_code=403,
            detail="RECOMMENDATION_V2_ENABLED=0 — Phase G v2 链路灰度未开",
        )
    items = get_fallback_companies(
        sub_cat=sub_cat,
        max_companies=max_companies,
        must_have_only=must_have_only,
    )
    return {
        "sub_cat": sub_cat,
        "fallback_companies": items,
        "count": len(items),
    }
