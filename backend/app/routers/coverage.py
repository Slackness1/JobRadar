"""Top-platform coverage dashboard router.

Reads backend/config/coverage_truth.yaml (declared T1 list per track + DEFERRED
reasons) and joins with company_crawl_logs (last 7 days, fetched_count > 0) to
compute per-track coverage rate + per-T1 status.

Status values:
    active   — T1 公司在最近 7 天爬到了 ≥1 岗位
    seasonal — engine 已知通但当前空（暂无）
    deferred — 工程不可行，docstring 标 deferred_reason
    missing  — 期望 active 但 7 天无数据（潜在 alert）
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import yaml
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from sqlalchemy import or_

from app.database import get_db
from app.models import CompanyCrawlLog, Job


router = APIRouter(prefix="/api/coverage", tags=["coverage"])


def _query_active_by_company_keywords(
    db: Session, include: list[str], exclude: list[str], days: int = 7
) -> dict[str, int]:
    """For `derived_company` mode: pull from jobs table directly by company-name
    keyword, since these companies are surfaced through other crawlers (banks /
    insurers / etc) rather than having dedicated CompanyCrawlLog rows.
    Returns {company: count_in_window}.
    """
    if not include:
        return {}
    since = datetime.utcnow() - timedelta(days=days)
    filters = [Job.company.like(f"%{kw}%") for kw in include]
    q = db.query(Job.company).filter(or_(*filters), Job.created_at >= since)
    if exclude:
        for kw in exclude:
            q = q.filter(~Job.company.like(f"%{kw}%"))
    out: dict[str, int] = {}
    for (company,) in q.all():
        if not company:
            continue
        out[company] = out.get(company, 0) + 1
    return out


_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "coverage_truth.yaml"
)


def _load_truth() -> dict:
    return yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}


def _query_active_by_source(
    db: Session, sources: list[str], days: int = 7
) -> dict[str, int]:
    """Return {company: max_fetched_count_in_window} for the given sources."""
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(
            CompanyCrawlLog.company,
            CompanyCrawlLog.fetched_count,
        )
        .filter(
            CompanyCrawlLog.source.in_(sources),
            CompanyCrawlLog.started_at >= since,
            CompanyCrawlLog.fetched_count != None,  # noqa: E711
            CompanyCrawlLog.fetched_count > 0,
        )
        .all()
    )
    out: dict[str, int] = {}
    for company, fetched in rows:
        if not company:
            continue
        prev = out.get(company, 0)
        if (fetched or 0) > prev:
            out[company] = int(fetched or 0)
    return out


def _resolve_status(
    company_def: dict[str, Any], active_map: dict[str, int]
) -> tuple[str, int, Optional[str]]:
    """Returns (status, fetched_max, matched_alias)."""
    aliases = company_def.get("aliases") or [company_def["name"]]
    matched_alias: Optional[str] = None
    fetched_max = 0
    for alias in aliases:
        if alias in active_map:
            matched_alias = alias
            fetched_max = max(fetched_max, active_map[alias])
    deferred = company_def.get("deferred_reason")
    if matched_alias:
        return "active", fetched_max, matched_alias
    if deferred:
        return "deferred", 0, None
    return "missing", 0, None


@router.get("")
def get_coverage(db: Session = Depends(get_db)) -> dict:
    truth = _load_truth()
    tracks_in = truth.get("tracks") or []
    tracks_out: list[dict] = []

    grand_t1 = 0
    grand_active = 0

    for track in tracks_in:
        mode = track.get("mode", "enumerate")

        if mode == "derived_company":
            include = track.get("company_keywords_include") or []
            exclude = track.get("company_keywords_exclude") or []
            active_map = _query_active_by_company_keywords(db, include, exclude)
            tracks_out.append({
                "id": track["id"],
                "name": track["name"],
                "mode": "absolute",   # frontend renders identically to absolute
                "sources": [],
                "active_company_count": len(active_map),
                "active_total_fetched": sum(active_map.values()),
                "note": track.get("note", "").strip(),
                "active_companies": [
                    {"name": k, "fetched_7d": v}
                    for k, v in sorted(active_map.items(), key=lambda x: -x[1])[:60]
                ],
            })
            continue

        sources = track.get("source_match") or []
        active_map = _query_active_by_source(db, sources)
        if mode == "absolute":
            tracks_out.append({
                "id": track["id"],
                "name": track["name"],
                "mode": "absolute",
                "sources": sources,
                "active_company_count": len(active_map),
                "active_total_fetched": sum(active_map.values()),
                "note": track.get("note", "").strip(),
                "active_companies": [
                    {"name": k, "fetched_7d": v}
                    for k, v in sorted(
                        active_map.items(), key=lambda x: -x[1]
                    )[:50]  # 只取 top-50 给前端
                ],
            })
            continue

        # enumerate mode
        companies_out: list[dict] = []
        active_count = 0
        deferred_count = 0
        missing_count = 0

        for c in track.get("t1_companies") or []:
            status, fetched, _alias = _resolve_status(c, active_map)
            if status == "active":
                active_count += 1
            elif status == "deferred":
                deferred_count += 1
            else:
                missing_count += 1
            companies_out.append({
                "name": c["name"],
                "status": status,
                "fetched_7d": fetched,
                "deferred_reason": c.get("deferred_reason"),
            })

        # Surface 7-day active companies that ARE NOT in our T1 list — these
        # are extras the user might want to know about.
        t1_alias_set: set[str] = set()
        for c in track.get("t1_companies") or []:
            for a in (c.get("aliases") or [c["name"]]):
                t1_alias_set.add(a)
        extras = [
            {"name": k, "fetched_7d": v}
            for k, v in sorted(active_map.items(), key=lambda x: -x[1])
            if k not in t1_alias_set
        ][:30]

        t1_total = len(track.get("t1_companies") or [])
        rate = (active_count / t1_total) if t1_total else 0.0
        grand_t1 += t1_total
        grand_active += active_count

        tracks_out.append({
            "id": track["id"],
            "name": track["name"],
            "mode": "enumerate",
            "sources": sources,
            "t1_total": t1_total,
            "active_count": active_count,
            "deferred_count": deferred_count,
            "missing_count": missing_count,
            "rate": round(rate, 4),
            "companies": companies_out,
            "extras": extras,
        })

    overall = {
        "grand_t1": grand_t1,
        "grand_active": grand_active,
        "rate": round(grand_active / grand_t1, 4) if grand_t1 else 0.0,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }

    return {"tracks": tracks_out, "overall": overall}
