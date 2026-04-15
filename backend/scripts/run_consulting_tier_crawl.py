#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from html import unescape
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal
from app.models import Job


CONFIG_PATH = BACKEND_DIR / "config" / "consulting_campus.yaml"
REPORT_DIR = BACKEND_DIR / "data" / "validation_reports"
DEFAULT_TIMEOUT = 20

JOB_KEYWORDS = [
    "job",
    "opening",
    "position",
    "vacancy",
    "requisition",
    "apply now",
    "consultant",
    "analyst",
    "associate",
    "intern",
    "graduate",
    "student",
    "校园",
    "校招",
    "岗位",
    "职位",
    "招聘",
]

TIER_BUCKETS = {
    "t1": {"Tier S"},
    "t2": {"Tier A", "Tier A-"},
    "t3": {"Tier B", "Tier B (Optional)"},
}

COMPANY_ALIASES: dict[str, list[str]] = {
    "McKinsey": ["McKinsey", "麦肯锡"],
    "BCG": ["BCG", "波士顿咨询"],
    "Bain": ["Bain", "贝恩"],
    "Oliver Wyman": ["Oliver Wyman", "奥纬"],
    "LEK": ["LEK"],
    "EY-Parthenon": ["EY-Parthenon", "Parthenon"],
    "Deloitte": ["Deloitte", "德勤"],
    "PwC": ["PwC", "普华永道"],
    "EY": ["EY", "安永"],
    "KPMG": ["KPMG", "毕马威"],
    "Accenture": ["Accenture", "埃森哲"],
    "IBM Consulting": ["IBM Consulting", "IBM"],
    "Capgemini Invent": ["Capgemini Invent", "凯捷"],
    "Protiviti": ["Protiviti"],
    "BearingPoint": ["BearingPoint", "毕博"],
    "ZS": ["ZS"],
    "OC&C": ["OC&C"],
    "BDA": ["BDA"],
    "A&M": ["A&M", "Alvarez", "Alvarez & Marsal"],
    "AlixPartners": ["AlixPartners", "Alix"],
    "FTI": ["FTI"],
    "Strategy&": ["Strategy&", "思略特"],
    "Roland Berger": ["Roland Berger", "罗兰贝格"],
    "Kearney": ["Kearney", "科尔尼"],
}


@dataclass
class ConsultingTarget:
    tier: str
    source_tier: str
    name: str
    career_url: str
    campus_url: str
    platform: str
    ats_family: str
    status: str
    notes: str


@dataclass
class ConsultingCrawlResult:
    tier: str
    source_tier: str
    name: str
    url: str
    status: str
    http_status: int | None = None
    final_url: str = ""
    title: str = ""
    ats_fingerprint: str = ""
    job_keyword_hits: int = 0
    detail_link_hits: int = 0
    json_job_hits: int = 0
    extracted_samples: list[str] | None = None
    db_job_count: int = 0
    error: str = ""


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _load_targets(selected_tiers: list[str]) -> list[ConsultingTarget]:
    payload = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    allowed_source_tiers = set()
    for tier in selected_tiers:
        allowed_source_tiers.update(TIER_BUCKETS.get(tier, set()))

    targets: list[ConsultingTarget] = []
    for company in payload.get("companies", []) or []:
        source_tier = _detect_source_tier(company)
        if source_tier not in allowed_source_tiers:
            continue
        bucket = _map_bucket(source_tier)
        targets.append(
            ConsultingTarget(
                tier=bucket,
                source_tier=source_tier,
                name=str(company.get("name", "")).strip(),
                career_url=str(company.get("career_url", "")).strip(),
                campus_url=str(company.get("campus_url", "")).strip(),
                platform=str(company.get("platform", "")).strip(),
                ats_family=str(company.get("ats_family", "")).strip(),
                status=str(company.get("status", "")).strip(),
                notes=str(company.get("notes", "")).strip(),
            )
        )
    return targets


def _detect_source_tier(company: dict[str, Any]) -> str:
    name = str(company.get("name", "")).strip()
    if name in {"McKinsey", "BCG", "Bain"}:
        return "Tier S"
    if name in {"Oliver Wyman", "LEK", "EY-Parthenon"}:
        return "Tier A"
    if name in {"Deloitte", "PwC", "EY", "KPMG", "Accenture", "IBM Consulting"}:
        return "Tier A-"
    if name in {"Capgemini Invent", "Protiviti", "BearingPoint", "ZS", "OC&C", "BDA"}:
        return "Tier B"
    if name in {"A&M", "AlixPartners", "FTI"}:
        return "Tier B (Optional)"
    if name in {"Strategy&", "Roland Berger", "Kearney"}:
        return "Tier A"
    return "Unknown"


def _map_bucket(source_tier: str) -> str:
    for tier, source_tiers in TIER_BUCKETS.items():
        if source_tier in source_tiers:
            return tier
    return "unknown"


def _pick_url(target: ConsultingTarget) -> str:
    return target.campus_url or target.career_url


def _detect_ats(html: str, url: str) -> str:
    checks = {
        "Greenhouse": ["greenhouse.io", "boards.greenhouse.io"],
        "Lever": ["lever.co"],
        "Workday": ["workday.com"],
        "SmartRecruiters": ["smartrecruiters.com"],
        "Taleo": ["taleo.net", "oracle.com/hcm"],
        "Moka": ["mokahr.com", "hotjob.cn"],
        "Phenom People": ["phenompeople.com"],
        "Eightfold": ["eightfold.ai"],
        "iCIMS": ["icims.com"],
        "Recsolu": ["recsolu.com"],
        "Next.js": ["/_next/static"],
    }
    merged = f"{url}\n{html}"
    for ats, patterns in checks.items():
        if any(pattern.lower() in merged.lower() for pattern in patterns):
            return ats
    return "custom"


def _count_job_keyword_hits(text: str) -> int:
    lowered = text.lower()
    return sum(1 for keyword in JOB_KEYWORDS if keyword.lower() in lowered)


def _count_detail_links(html: str) -> int:
    patterns = [
        r'href="[^"]*job[^"]*"',
        r'href="[^"]*opening[^"]*"',
        r'href="[^"]*position[^"]*"',
        r'href="[^"]*vacancy[^"]*"',
        r'href="[^"]*requisition[^"]*"',
        r'href="[^"]*career[^"]*"',
    ]
    return sum(len(re.findall(pattern, html, flags=re.IGNORECASE)) for pattern in patterns)


def _extract_json_job_hits(html: str) -> int:
    hits = 0
    for raw_json in re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        try:
            payload = json.loads(unescape(raw_json).strip())
        except Exception:
            continue
        if isinstance(payload, dict) and payload.get("@type") == "JobPosting":
            hits += 1
        elif isinstance(payload, list):
            hits += sum(1 for item in payload if isinstance(item, dict) and item.get("@type") == "JobPosting")
    return hits


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return " ".join(unescape(match.group(1)).split())


def _extract_dom_samples(html: str) -> list[str]:
    samples: list[str] = []
    for match in re.findall(r"<a[^>]*>(.*?)</a>", html, flags=re.IGNORECASE | re.DOTALL):
        text = " ".join(re.sub(r"<[^>]+>", " ", unescape(match)).split())
        if 8 < len(text) < 120 and any(token in text.lower() for token in ["consultant", "analyst", "associate", "intern", "graduate"]):
            samples.append(text[:120])
            if len(samples) >= 10:
                break
    return samples[:10]


def _count_existing_jobs(name: str, db) -> int:
    aliases = COMPANY_ALIASES.get(name, [name])
    total = 0
    for alias in aliases:
        pattern = f"%{alias}%"
        total += db.query(Job).filter(
            (Job.company.like(pattern)) | (Job.department.like(pattern)) | (Job.job_title.like(pattern))
        ).count()
    return total


def crawl_target(target: ConsultingTarget, db) -> ConsultingCrawlResult:
    url = _pick_url(target)
    result = ConsultingCrawlResult(
        tier=target.tier,
        source_tier=target.source_tier,
        name=target.name,
        url=url,
        status="failed",
        db_job_count=_count_existing_jobs(target.name, db),
    )

    if not url:
        result.error = "No campus_url/career_url configured"
        return result

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=DEFAULT_TIMEOUT,
            allow_redirects=True,
        )
    except Exception as exc:
        result.error = str(exc)
        return result

    result.http_status = response.status_code
    result.final_url = response.url
    if response.status_code != 200:
        result.error = f"HTTP_{response.status_code}"
        return result

    html = response.text
    result.title = _extract_title(html)
    result.ats_fingerprint = _detect_ats(html, response.url)
    result.job_keyword_hits = _count_job_keyword_hits(html)
    result.detail_link_hits = _count_detail_links(html)
    result.json_job_hits = _extract_json_job_hits(html)
    result.extracted_samples = _extract_dom_samples(html)

    if result.json_job_hits > 0 or (result.extracted_samples and len(result.extracted_samples) > 0):
        result.status = "success"
        return result

    if result.job_keyword_hits > 0 or result.detail_link_hits > 0:
        result.status = "suspect_zero"
    else:
        result.status = "confirmed_zero"
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl consulting T1-T3 targets from consulting_campus.yaml")
    parser.add_argument("--tiers", default="t1,t2,t3", help="Comma-separated tiers, default: t1,t2,t3")
    parser.add_argument("--include-companies", default="", help="Comma-separated company names to include")
    parser.add_argument("--output-prefix", default="", help="Optional output filename prefix")
    return parser.parse_args()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "tier",
        "source_tier",
        "name",
        "url",
        "status",
        "http_status",
        "final_url",
        "title",
        "ats_fingerprint",
        "job_keyword_hits",
        "detail_link_hits",
        "json_job_hits",
        "db_job_count",
        "error",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def main() -> None:
    args = parse_args()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    tiers = _split_csv(args.tiers) or ["t1", "t2", "t3"]
    include_companies = set(_split_csv(args.include_companies))
    targets = _load_targets(tiers)
    if include_companies:
        targets = [item for item in targets if item.name in include_companies]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = args.output_prefix or f"consulting_tier_crawl_{timestamp}"
    report_json = REPORT_DIR / f"{prefix}_results.json"
    report_csv = REPORT_DIR / f"{prefix}_results.csv"

    print(f"targets={len(targets)}")
    for target in targets:
        print(f"[{target.tier}/{target.source_tier}] {target.name} | {_pick_url(target)}")

    db = SessionLocal()
    try:
        results = [crawl_target(target, db) for target in targets]
    finally:
        db.close()

    summary = {
        "target_count": len(results),
        "by_status": dict(Counter(item.status for item in results)),
        "by_tier": {
            tier: dict(Counter(item.status for item in results if item.tier == tier))
            for tier in ["t1", "t2", "t3"]
        },
        "db_jobs_total": sum(item.db_job_count for item in results),
    }
    payload = {
        "generated_at": datetime.now().isoformat(),
        "tiers": tiers,
        "include_companies": sorted(include_companies),
        "summary": summary,
        "results": [asdict(item) for item in results],
    }
    _write_json(report_json, payload)
    _write_csv(report_csv, [asdict(item) for item in results])

    print(f"results_json={report_json}")
    print(f"results_csv={report_csv}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
