"""Phase G T18 — 公司 fallback 卡片数据源。

需求: 某 sub_cat 的 must_have 头部公司, 当本季 active 岗位 < 3 时, 屏幕上不能让学生
觉得"我们没覆盖这家"。fallback 卡片告诉学生:
- 公司名 + tier
- 本季招聘动态 (active jobs 数 + 状态文案)
- KB hiring_season + verbatim 一条 (如果有)

后端只暴露数据, UI 由 frontend 渲染。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import or_

from app.database import SessionLocal
from app.models import Job, KnowledgeSubcategory

log = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[3]
GROUND_TRUTH_FILE = BACKEND_ROOT / "data" / "ground_truth_companies_v1.json"


def _ground_truth_for_subcat(sub_cat: str) -> list[dict[str, Any]]:
    if not GROUND_TRUTH_FILE.exists():
        return []
    try:
        gt = json.loads(GROUND_TRUTH_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.warning("ground_truth_companies_v1.json JSON parse fail")
        return []
    return gt.get("ground_truth", {}).get(sub_cat, [])


def _count_active_jobs(company_name: str, days: int = 30) -> tuple[int, int]:
    """Return (alive_total, internship_only_subset). substring match on company."""
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        base = db.query(Job).filter(
            Job.company.like(f"%{company_name}%"),
            Job.scraped_at > cutoff,
            (Job.link_status == "alive") | (Job.link_status.is_(None)),
            Job.quality_label.in_(["good", "internship_only"]),
        )
        alive = base.count()
        intern = base.filter(Job.quality_label == "internship_only").count()
        return alive, intern
    finally:
        db.close()


def _status_text(alive: int, intern: int) -> str:
    if alive == 0:
        return "本季暂未开放新增岗位"
    if 1 <= alive <= 2:
        if intern == alive:
            return f"仅有 {alive} 个实习岗"
        return f"本季仅 {alive} 个开放岗位"
    # >= 3 不应进 fallback (有充足岗位, 走主推荐链路)
    return f"本季 {alive} 个开放岗位"


def _kb_payload(sub_cat: str) -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        row = db.query(KnowledgeSubcategory).filter_by(sub_cat=sub_cat).first()
        if not row:
            return None
        try:
            return json.loads(row.payload_json)
        except json.JSONDecodeError:
            return None
    finally:
        db.close()


def _verbatim_for_company(
    payload: dict[str, Any] | None, company_name: str
) -> dict[str, Any] | None:
    """如果 KB verbatim 提到过该公司, 返回第一条; 否则 None。

    匹配宽松: ground truth "易方达基金" vs verbatim 写 "易方达" 也算 — 用
    company 全名 + 前缀 (剥 基金/证券/银行/资管 等后缀的 brand 部分)。
    """
    if not payload or not company_name:
        return None
    # brand prefix: 剥常见行业后缀后剩下的 (≥ 2 字才有意义)
    brand = company_name
    for suffix in ("基金", "证券", "银行", "信托", "保险", "资管", "投资", "资产管理"):
        if brand.endswith(suffix) and len(brand) > len(suffix):
            brand = brand[: -len(suffix)]
            break
    candidates = {company_name}
    if brand and len(brand) >= 2:
        candidates.add(brand)
    for q in payload.get("verbatim_quotes") or []:
        text = q.get("quote") or ""
        if any(c in text for c in candidates):
            return {"quote": text, "source_url": q.get("source_url") or ""}
    return None


def _season_text(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""
    hs = payload.get("hiring_season") or {}
    spring = (hs.get("spring") or "").strip()
    fall = (hs.get("fall") or "").strip()
    peak = hs.get("peak_month") or []
    parts: list[str] = []
    if spring:
        parts.append(f"春招: {spring}")
    if fall:
        parts.append(f"秋招: {fall}")
    if peak:
        parts.append(f"高峰月: {', '.join(str(m) for m in peak)}")
    return " · ".join(parts)


def get_fallback_companies(
    sub_cat: str,
    *,
    max_companies: int = 5,
    must_have_only: bool = True,
    threshold: int = 3,
) -> list[dict[str, Any]]:
    """返回该 sub_cat 的 fallback 公司列表 (active < threshold 才入 fallback)。

    Args:
        sub_cat: 目标 sub_cat 名 (必须在 ground_truth 里)
        max_companies: 最多返回数
        must_have_only: 仅返回 ground_truth.must_have=true 的公司 (默认 True)
        threshold: alive < threshold 才进 fallback (default 3, 即活跃岗 ≥3 走主推荐)

    Returns:
        [{name, tier, status, season, verbatim_hint, active_jobs, must_have}]
    """
    candidates = _ground_truth_for_subcat(sub_cat)
    if not candidates:
        return []
    if must_have_only:
        candidates = [c for c in candidates if c.get("must_have")]

    payload = _kb_payload(sub_cat)
    season = _season_text(payload)

    out: list[dict[str, Any]] = []
    for c in candidates:
        name = c.get("name") or ""
        if not name:
            continue
        alive, intern = _count_active_jobs(name)
        if alive >= threshold:
            continue  # 活跃岗位充足 → 不需要 fallback 卡片
        out.append({
            "name": name,
            "tier": c.get("tier"),
            "must_have": bool(c.get("must_have")),
            "status": _status_text(alive, intern),
            "season": season,
            "verbatim_hint": _verbatim_for_company(payload, name),
            "active_jobs": alive,
        })
        if len(out) >= max_companies:
            break
    return out
