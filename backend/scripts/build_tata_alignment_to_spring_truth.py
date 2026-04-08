#!/usr/bin/env python3
import csv
import json
import sqlite3
from collections import Counter
from json import JSONDecodeError
from pathlib import Path

from app.services.company_truth_alignment import align_tata_company
from app.services.company_truth_merge import normalize_company_for_matching


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "backend" / "data" / "jobradar.db"
SPRING_TRUTH_PATH = PROJECT_ROOT / "data" / "exports" / "company_truth_spring_master.csv"
ALIAS_PATH = PROJECT_ROOT / "data" / "exports" / "legal_entity_alias_final_mapping_in_spring_truth.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "exports" / "tata_aligned_to_spring_truth.csv"
REPORT_PATH = PROJECT_ROOT / "data" / "exports" / "tata_alignment_report.txt"


def _safe_json_list(raw_value: str) -> list[str]:
    value = (raw_value or "").strip()
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except JSONDecodeError:
        return []
    return loaded if isinstance(loaded, list) else []


def load_spring_lookup() -> dict[str, object]:
    with open(SPRING_TRUTH_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    companies = {
        row["canonical_name"]: {
            "company_id": row["company_id"],
            "canonical_name": row["canonical_name"],
            "aliases": _safe_json_list(row.get("aliases_json", "[]")),
            "entity_members": _safe_json_list(row.get("entity_members_json", "[]")),
        }
        for row in rows
    }

    normalized_canonical = {}
    normalized_aliases = {}
    normalized_entity_members = {}
    for canonical_name, row in companies.items():
        normalized_canonical[normalize_company_for_matching(canonical_name)] = canonical_name
        for alias in row["aliases"]:
            normalized_aliases[normalize_company_for_matching(alias)] = canonical_name
        for member in row["entity_members"]:
            normalized_entity_members[normalize_company_for_matching(member)] = canonical_name

    return {
        "companies": companies,
        "normalized_canonical": normalized_canonical,
        "normalized_aliases": normalized_aliases,
        "normalized_entity_members": normalized_entity_members,
    }


def load_alias_lookup() -> dict[str, dict[str, str]]:
    with open(ALIAS_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return {
        row["tata_company"]: {
            "mapped_parent": row["mapped_parent"],
            "mapping_source": row["mapping_source"],
            "confidence": row["confidence"],
            "reason": row["reason"],
        }
        for row in rows
    }


def fetch_tata_jobs() -> list[sqlite3.Row]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE source='tatawangshen' ORDER BY company, id")
    rows = cur.fetchall()
    conn.close()
    return rows


def write_alignment_csv(rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "db_id",
        "job_id",
        "source",
        "company",
        "job_title",
        "location",
        "deadline",
        "detail_url",
        "matched",
        "matched_company_id",
        "matched_parent_name",
        "match_method",
        "alias_mapping_source",
        "alias_confidence",
        "alias_reason",
    ]
    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_report(rows: list[dict[str, str]]) -> None:
    total_jobs = len(rows)
    matched_jobs = sum(1 for row in rows if row["matched"] == "True")
    unmatched_jobs = total_jobs - matched_jobs

    companies = {}
    for row in rows:
        companies.setdefault(row["company"], {"jobs": 0, "matched": False})
        companies[row["company"]]["jobs"] += 1
        if row["matched"] == "True":
            companies[row["company"]]["matched"] = True

    total_companies = len(companies)
    matched_companies = sum(1 for item in companies.values() if item["matched"])
    unmatched_companies = total_companies - matched_companies

    method_counter = Counter(row["match_method"] for row in rows if row["matched"] == "True")
    top_unmatched = sorted(
        [(company, data["jobs"]) for company, data in companies.items() if not data["matched"]],
        key=lambda x: -x[1],
    )[:30]

    lines = [
        "TATA -> Spring Truth Alignment Report",
        "=" * 60,
        f"total_jobs: {total_jobs}",
        f"matched_jobs: {matched_jobs} ({matched_jobs / total_jobs * 100:.1f}%)",
        f"unmatched_jobs: {unmatched_jobs} ({unmatched_jobs / total_jobs * 100:.1f}%)",
        "",
        f"total_companies: {total_companies}",
        f"matched_companies: {matched_companies} ({matched_companies / total_companies * 100:.1f}%)",
        f"unmatched_companies: {unmatched_companies} ({unmatched_companies / total_companies * 100:.1f}%)",
        "",
        "match_method_breakdown:",
    ]
    for key, value in method_counter.items():
        lines.append(f"  {key}: {value}")
    lines.extend(["", "top_unmatched_companies:"])
    for company, jobs in top_unmatched:
        lines.append(f"  {company}: {jobs}")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    spring_lookup = load_spring_lookup()
    alias_lookup = load_alias_lookup()
    tata_jobs = fetch_tata_jobs()

    output_rows = []
    for job in tata_jobs:
        alignment = align_tata_company(job["company"], spring_lookup, alias_lookup)
        alias_meta = alias_lookup.get(job["company"], {})
        output_rows.append(
            {
                "db_id": job["id"],
                "job_id": job["job_id"],
                "source": job["source"],
                "company": job["company"],
                "job_title": job["job_title"] or "",
                "location": job["location"] or "",
                "deadline": job["deadline"] or "",
                "detail_url": job["detail_url"] or "",
                "matched": str(alignment["matched"]),
                "matched_company_id": alignment["matched_company_id"],
                "matched_parent_name": alignment["matched_parent_name"],
                "match_method": alignment["match_method"],
                "alias_mapping_source": alias_meta.get("mapping_source", ""),
                "alias_confidence": alias_meta.get("confidence", ""),
                "alias_reason": alias_meta.get("reason", ""),
            }
        )

    write_alignment_csv(output_rows)
    write_report(output_rows)

    matched_jobs = sum(1 for row in output_rows if row["matched"] == "True")
    matched_companies = len({row["company"] for row in output_rows if row["matched"] == "True"})
    total_companies = len({row["company"] for row in output_rows})

    print(f"output_csv: {OUTPUT_PATH}")
    print(f"output_report: {REPORT_PATH}")
    print(f"matched_jobs: {matched_jobs}/{len(output_rows)}")
    print(f"matched_companies: {matched_companies}/{total_companies}")


if __name__ == "__main__":
    main()
