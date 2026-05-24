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

from sqlalchemy import func, or_

from app.database import get_db
from app.models import CompanyCrawlLog, Job


router = APIRouter(prefix="/api/coverage", tags=["coverage"])


def _query_active_by_company_keywords(
    db: Session,
    include: list[str],
    exclude: list[str],
    days: int = 7,
    title_keywords_include: list[str] | None = None,
    standalone_entity_keywords: list[str] | None = None,
) -> dict[str, int]:
    """For `derived_company` mode: pull from jobs table directly by company-name
    keyword, since these companies are surfaced through other crawlers (banks /
    insurers / etc) rather than having dedicated CompanyCrawlLog rows.

    Optional `title_keywords_include`: further AND-filter by job_title or
    department LIKE. Used for sub-direction tracks like "大行管培" where the
    parent crawler already collected the bank rows, and we just need to
    surface a subset.

    Optional `standalone_entity_keywords`: bypass the title-keyword filter
    when company itself contains one of these (e.g. "证券资产管理" — those
    rows are already-named subsidiary entities, their job_title rarely
    contains "资管" but they all qualify).

    Returns {company: count_in_window}.
    """
    if not include:
        return {}
    since = datetime.utcnow() - timedelta(days=days)
    filters = [Job.company.like(f"%{kw}%") for kw in include]
    age_filter = or_(Job.scraped_at >= since, Job.created_at >= since)
    q = db.query(Job.company).filter(or_(*filters), age_filter)
    if exclude:
        for kw in exclude:
            q = q.filter(~Job.company.like(f"%{kw}%"))
    if title_keywords_include:
        # title/dept filter — but allow standalone-entity bypass: if company name
        # itself looks like a subsidiary entity (含 "证券资产管理"/"理财有限" 等),
        # we skip the title check since title field won't carry "资管" keyword.
        title_filters: list = []
        for kw in title_keywords_include:
            title_filters.append(Job.job_title.like(f"%{kw}%"))
            title_filters.append(Job.department.like(f"%{kw}%"))
        if standalone_entity_keywords:
            for kw in standalone_entity_keywords:
                title_filters.append(Job.company.like(f"%{kw}%"))
        q = q.filter(or_(*title_filters))
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
    company_def: dict[str, Any],
    active_map: dict[str, int],
    db: Optional[Session] = None,
    since: Optional[datetime] = None,
) -> tuple[str, int, Optional[str]]:
    """Returns (status, fetched, matched_alias).

    Two layers of lookup:
    1. PRIMARY — `jobs_company_match` keyword list against `jobs.company` if
       provided. Used when a T1 entity hides inside a parent group portal
       (e.g. 平安证券 / 平安寿险 are crawled as 'company=平安集团 source=
       bank_official' in CompanyCrawlLog but the actual `Job` rows have
       `company='平安证券' / '平安寿险' / ...`).
    2. SECONDARY — `aliases` against CompanyCrawlLog `active_map`. This is
       the original behaviour for cleanly-separated crawl targets.
    """
    keywords = company_def.get("jobs_company_match") or []
    if keywords and db is not None and since is not None:
        filters = [Job.company.like(f"%{kw}%") for kw in keywords]
        # Same age filter as derived_company queries: scraped_at OR created_at
        # (legacy Tata rows often have NULL created_at — see P1-D fix).
        age_filter = or_(Job.scraped_at >= since, Job.created_at >= since)
        count = (
            db.query(func.count(Job.id))
            .filter(or_(*filters), age_filter)
            .scalar()
            or 0
        )
        if count > 0:
            return "active", int(count), keywords[0]

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
            title_include = track.get("title_keywords_include") or []
            standalone_entity = track.get("standalone_entity_keywords") or []
            # Default 30d for derived tracks: parent crawlers re-pull weekly
            # at best, and futures/trust seasonal cycles mean 7d misses 90% of
            # data. 30d strikes the right balance.
            window_days = int(track.get("window_days") or 30)
            active_map = _query_active_by_company_keywords(
                db, include, exclude, days=window_days,
                title_keywords_include=title_include or None,
                standalone_entity_keywords=standalone_entity or None,
            )
            tracks_out.append({
                "id": track["id"],
                "name": track["name"],
                "canonical_tracks": list(track.get("canonical_tracks") or []),
                "mode": "absolute",   # frontend renders identically to absolute
                "sources": [],
                "active_company_count": len(active_map),
                "active_total_fetched": sum(active_map.values()),
                "note": track.get("note", "").strip(),
                "active_companies": [
                    {"name": k, "fetched_7d": v}
                    for k, v in sorted(active_map.items(), key=lambda x: -x[1])[:60]
                ],
                "window_days": window_days,
            })
            continue

        sources = track.get("source_match") or []
        active_map = _query_active_by_source(db, sources)
        if mode == "absolute":
            tracks_out.append({
                "id": track["id"],
                "name": track["name"],
                "canonical_tracks": list(track.get("canonical_tracks") or []),
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
        # enumerate-mode jobs_company_match window. Default 60d (broader than
        # 7d active_map for CompanyCrawlLog) — covers full春招/秋招 cycle
        # and lets Tata-sourced T1 entities (大部分 t1 券商无独立 ATS) surface.
        # Per-track override via 'jobs_match_window_days' yaml field.
        since = datetime.utcnow() - timedelta(days=int(track.get("jobs_match_window_days") or 60))

        for c in track.get("t1_companies") or []:
            status, fetched, _alias = _resolve_status(c, active_map, db=db, since=since)
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
            "canonical_tracks": list(track.get("canonical_tracks") or []),
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
