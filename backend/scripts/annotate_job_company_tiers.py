#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.company_truth_merge import normalize_company_for_matching
from app.services.consumer_foreign_crawler import COMPANY_ALIASES as CONSUMER_ALIASES
from app.services.internet_crawler import COMPANY_ALIASES as INTERNET_ALIASES
from app.services.state_owned_crawler import SOE_GROUP_RULES


DB_PATH = BACKEND_DIR / "data" / "jobradar.db"
REPORT_DIR = BACKEND_DIR / "data" / "validation_reports"
INTERNET_CONFIG = BACKEND_DIR / "config" / "tiered_internet_companies.yaml"
CONSUMER_CONFIG = BACKEND_DIR / "config" / "tiered_consumer_companies.yaml"
CONSULTING_CONFIG = BACKEND_DIR / "config" / "consulting_campus.yaml"
SECURITIES_CONFIG = BACKEND_DIR / "config" / "securities_campus.yaml"
ENERGY_CONFIG = BACKEND_DIR / "config" / "energy_campus.yaml"
BANK_CONFIG = BACKEND_DIR / "app" / "services" / "bank_crawler" / "bank_sites.yaml"

INTERNET_TIER_LABELS = {
    "t1": "互联网-一线",
    "t2": "互联网-二线",
    "t3": "互联网-三线",
    "t4": "互联网-四线",
}

CONSUMER_TIER_LABELS = {
    "t0": "消费外企-T0",
    "t1": "消费外企-T1",
    "shanghai_picks": "消费外企-上海精选",
}

CONSULTING_TIER_LABELS = {
    "Tier S": "咨询-T1",
    "Tier A": "咨询-T2",
    "Tier A-": "咨询-T2",
    "Tier B": "咨询-T3",
    "Tier B (Optional)": "咨询-T3",
}

SOE_TIER_LABELS = {
    "tier1_grid_tobacco_energy": "国央企-第一梯队",
    "tier1_operator_core": "国央企-第一梯队",
    "tier1_oil_core": "国央企-第一梯队",
    "tier1_nuclear_hydro_energy": "国央企-第一梯队",
    "tier2_transport_construction": "国央企-第二梯队",
    "tier2_defense_research": "国央企-第二梯队",
}

BANK_TIER_LABELS = {
    "state_major": "银行-国有大行",
    "joint_stock": "银行-股份行",
    "city_commercial": "银行-优质城商行",
}

CONSULTING_ALIASES = {
    "McKinsey": ["McKinsey", "麦肯锡"],
    "BCG": ["BCG", "波士顿咨询"],
    "Bain": ["Bain", "贝恩"],
    "Oliver Wyman": ["Oliver Wyman", "奥纬"],
    "LEK": ["LEK"],
    "EY-Parthenon": ["EY-Parthenon", "Parthenon", "安永帕特农", "帕特农"],
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
    "FTI": ["FTI", "FTI Consulting"],
    "Strategy&": ["Strategy&", "思略特"],
    "Roland Berger": ["Roland Berger", "罗兰贝格"],
    "Kearney": ["Kearney", "科尔尼"],
}

BANK_RULE_SPECS = {
    "cmb": {
        "canonical_name": "招商银行",
        "bucket": "joint_stock",
        "aliases": ["招商银行", "招商银行股份有限公司", "招行", "cmb", "cmbchina"],
    },
    "spdb": {
        "canonical_name": "浦发银行",
        "bucket": "joint_stock",
        "aliases": ["浦发银行", "上海浦东发展银行", "上海浦东发展银行股份有限公司", "spdb"],
    },
    "icbc": {
        "canonical_name": "工商银行",
        "bucket": "state_major",
        "aliases": ["工商银行", "中国工商银行", "中国工商银行股份有限公司", "icbc"],
    },
    "ccb": {
        "canonical_name": "建设银行",
        "bucket": "state_major",
        "aliases": ["建设银行", "中国建设银行", "中国建设银行股份有限公司", "ccb"],
    },
    "nbc": {
        "canonical_name": "宁波银行",
        "bucket": "city_commercial",
        "aliases": ["宁波银行", "宁波银行股份有限公司", "nbcb"],
    },
    "jsbc": {
        "canonical_name": "江苏银行",
        "bucket": "city_commercial",
        "aliases": ["江苏银行", "江苏银行股份有限公司", "jsbchina"],
    },
}


@dataclass(frozen=True)
class TierRule:
    canonical_name: str
    label: str
    industry: str
    aliases: tuple[str, ...]
    excludes: tuple[str, ...] = ()
    extra_tags: tuple[str, ...] = ()


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _normalize_alias(value: str) -> str:
    return normalize_company_for_matching(str(value or ""))


def _split_tags(raw: str) -> list[str]:
    return [part.strip() for part in re.split(r"[|,;/]+", raw or "") if part.strip()]


def _merge_tags(existing: str, additions: list[str]) -> str:
    seen: set[str] = set()
    merged: list[str] = []
    for value in _split_tags(existing) + additions:
        lowered = value.strip().lower()
        if not value or lowered in seen:
            continue
        seen.add(lowered)
        merged.append(value.strip())
    return ", ".join(merged)


def _build_internet_rules() -> list[TierRule]:
    payload = _load_yaml(INTERNET_CONFIG)
    rules: list[TierRule] = []
    for tier, companies in payload.items():
        label = INTERNET_TIER_LABELS.get(str(tier))
        if not label:
            continue
        for company in companies or []:
            aliases = [company, *INTERNET_ALIASES.get(company, [])]
            rules.append(
                TierRule(
                    canonical_name=str(company),
                    label=label,
                    industry="互联网",
                    aliases=tuple(dict.fromkeys(alias for alias in aliases if alias)),
                )
            )
    return rules


def _build_consumer_rules() -> list[TierRule]:
    payload = _load_yaml(CONSUMER_CONFIG)
    rules: list[TierRule] = []
    for tier, companies in payload.items():
        label = CONSUMER_TIER_LABELS.get(str(tier))
        if not label:
            continue
        for company in companies or []:
            aliases = [company, *CONSUMER_ALIASES.get(company, [])]
            rules.append(
                TierRule(
                    canonical_name=str(company),
                    label=label,
                    industry="消费/外企",
                    aliases=tuple(dict.fromkeys(alias for alias in aliases if alias)),
                )
            )
    return rules


def _detect_consulting_source_tier(name: str) -> str:
    if name in {"McKinsey", "BCG", "Bain"}:
        return "Tier S"
    if name in {"Oliver Wyman", "LEK", "EY-Parthenon", "Strategy&", "Roland Berger", "Kearney"}:
        return "Tier A"
    if name in {"Deloitte", "PwC", "EY", "KPMG", "Accenture", "IBM Consulting"}:
        return "Tier A-"
    if name in {"Capgemini Invent", "Protiviti", "BearingPoint", "ZS", "OC&C", "BDA"}:
        return "Tier B"
    if name in {"A&M", "AlixPartners", "FTI"}:
        return "Tier B (Optional)"
    return ""


def _build_consulting_rules() -> list[TierRule]:
    payload = _load_yaml(CONSULTING_CONFIG)
    rules: list[TierRule] = []
    for row in payload.get("companies", []) or []:
        name = str(row.get("name", "")).strip()
        source_tier = _detect_consulting_source_tier(name)
        label = CONSULTING_TIER_LABELS.get(source_tier)
        if not name or not label:
            continue
        aliases = [name, *CONSULTING_ALIASES.get(name, [])]
        rules.append(
            TierRule(
                canonical_name=name,
                label=label,
                industry="咨询",
                aliases=tuple(dict.fromkeys(alias for alias in aliases if alias)),
            )
        )
    return rules


def _build_securities_rules() -> list[TierRule]:
    payload = _load_yaml(SECURITIES_CONFIG)
    rules: list[TierRule] = []
    for row in payload.get("sites", []) or []:
        name = str(row.get("name", "")).strip()
        category = str(row.get("category", "")).strip()
        if not name or not category:
            continue
        category_label = category.replace("券商", "").strip()
        label = f"券商-{category_label}" if category_label else "券商"
        rules.append(
            TierRule(
                canonical_name=name,
                label=label,
                industry="券商",
                aliases=(name,),
            )
        )
    return rules


def _build_energy_rules() -> list[TierRule]:
    payload = _load_yaml(ENERGY_CONFIG)
    rules: list[TierRule] = []
    for row in payload.get("sites", []) or []:
        name = str(row.get("name", "")).strip()
        category = str(row.get("category", "")).strip()
        if not name or not category:
            continue
        label = f"能源-{category}"
        rules.append(
            TierRule(
                canonical_name=name,
                label=label,
                industry="能源",
                aliases=(name,),
            )
        )
    return rules


def _build_bank_rules() -> list[TierRule]:
    payload = _load_yaml(BANK_CONFIG)
    rules: list[TierRule] = []
    for key, row in (payload.get("banks") or {}).items():
        spec = BANK_RULE_SPECS.get(str(key))
        if not spec:
            continue
        label = BANK_TIER_LABELS[spec["bucket"]]
        configured_name = str((row or {}).get("name", "")).strip()
        aliases = [configured_name, *spec["aliases"]]
        rules.append(
            TierRule(
                canonical_name=str(spec["canonical_name"]),
                label=label,
                industry="银行",
                aliases=tuple(dict.fromkeys(alias for alias in aliases if alias)),
            )
        )
    return rules


def _build_state_owned_rules() -> list[TierRule]:
    rules: list[TierRule] = []
    for row in SOE_GROUP_RULES:
        tier = str(row.get("tier", "")).strip()
        group = str(row.get("group", "")).strip()
        label = SOE_TIER_LABELS.get(tier)
        if not label:
            continue
        aliases = [group, *(row.get("include") or [])]
        excludes = tuple(str(value) for value in (row.get("exclude") or []) if value)
        rules.append(
            TierRule(
                canonical_name=group,
                label=label,
                industry="国央企",
                aliases=tuple(dict.fromkeys(alias for alias in aliases if alias)),
                excludes=excludes,
                extra_tags=(f"国央企-{group}",),
            )
        )
    return rules


def build_rules() -> list[TierRule]:
    groups = [
        _build_internet_rules(),
        _build_consumer_rules(),
        _build_consulting_rules(),
        _build_bank_rules(),
        _build_securities_rules(),
        _build_energy_rules(),
        _build_state_owned_rules(),
    ]
    rules: list[TierRule] = []
    for items in groups:
        rules.extend(items)
    return rules


def _best_rule_for_company(company: str, rules: list[TierRule]) -> TierRule | None:
    raw = (company or "").strip()
    if not raw:
        return None
    normalized = _normalize_alias(raw)
    lowered = raw.lower()
    best_rule: TierRule | None = None
    best_score = -1

    for rule in rules:
        if any(exclude.lower() in lowered for exclude in rule.excludes):
            continue
        for alias in rule.aliases:
            alias_norm = _normalize_alias(alias)
            if not alias_norm:
                continue
            if alias_norm not in normalized:
                continue
            score = len(alias_norm)
            if normalized == alias_norm:
                score += 100
            if score > best_score:
                best_score = score
                best_rule = rule
    return best_rule


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Annotate jobs in jobradar.db with company tier labels.")
    parser.add_argument("--db-path", default=str(DB_PATH), help="Path to SQLite database")
    parser.add_argument("--dry-run", action="store_true", help="Preview updates without writing DB")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup before writing")
    return parser.parse_args()


def _create_backup(db_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.name}.before_tier_annotation_{timestamp}.bak")
    shutil.copy2(db_path, backup_path)
    return backup_path


def main() -> None:
    args = parse_args()
    db_path = Path(args.db_path).resolve()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rules = build_rules()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    companies = [row["company"] for row in cur.execute("select distinct company from jobs where company <> '' order by company")]
    company_matches: dict[str, TierRule] = {}
    label_counter: Counter[str] = Counter()
    industry_counter: Counter[str] = Counter()
    company_samples: dict[str, list[str]] = {}

    for company in companies:
        rule = _best_rule_for_company(company, rules)
        if rule is None:
            continue
        company_matches[company] = rule
        label_counter[rule.label] += 1
        industry_counter[rule.industry] += 1
        company_samples.setdefault(rule.label, []).append(company)

    rows = list(
        cur.execute(
            "select id, company, company_type_industry, company_tags from jobs order by id"
        )
    )

    updates: list[tuple[str, str, int]] = []
    updated_jobs = 0
    jobs_by_label: Counter[str] = Counter()
    jobs_by_industry: Counter[str] = Counter()

    for row in rows:
        rule = company_matches.get(row["company"])
        if rule is None:
            continue
        additions = [rule.label, *list(rule.extra_tags)]
        new_tags = _merge_tags(row["company_tags"] or "", additions)
        new_industry = row["company_type_industry"] or rule.industry
        if new_tags == (row["company_tags"] or "") and new_industry == (row["company_type_industry"] or ""):
            continue
        updates.append((new_industry, new_tags, row["id"]))
        updated_jobs += 1
        jobs_by_label[rule.label] += 1
        jobs_by_industry[rule.industry] += 1

    backup_path = None
    if not args.dry_run:
        if not args.no_backup:
            backup_path = _create_backup(db_path)
        cur.executemany(
            "update jobs set company_type_industry = ?, company_tags = ? where id = ?",
            updates,
        )
        conn.commit()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"job_company_tier_annotation_{timestamp}.json"
    report = {
        "generated_at": datetime.now().isoformat(),
        "db_path": str(db_path),
        "dry_run": args.dry_run,
        "backup_path": str(backup_path) if backup_path else "",
        "rule_count": len(rules),
        "matched_company_count": len(company_matches),
        "updated_job_count": updated_jobs,
        "matched_companies_by_label": dict(label_counter.most_common()),
        "updated_jobs_by_label": dict(jobs_by_label.most_common()),
        "updated_jobs_by_industry": dict(jobs_by_industry.most_common()),
        "sample_companies_by_label": {
            label: sorted(samples)[:20] for label, samples in sorted(company_samples.items())
        },
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"db_path={db_path}")
    print(f"dry_run={args.dry_run}")
    if backup_path:
        print(f"backup_path={backup_path}")
    print(f"matched_company_count={len(company_matches)}")
    print(f"updated_job_count={updated_jobs}")
    print(f"report_path={report_path}")
    print("top_labels=")
    for label, count in jobs_by_label.most_common(20):
        print(f"  {label}: {count}")

    conn.close()


if __name__ == "__main__":
    main()
