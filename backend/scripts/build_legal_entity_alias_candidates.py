#!/usr/bin/env python3
import csv
import json
import sqlite3
from pathlib import Path

from app.services.company_truth_merge import (
    find_rule_based_parent_candidates,
    infer_parent_company,
    normalize_company_for_matching,
    partition_alias_candidates,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "backend" / "data" / "jobradar.db"
SPRING_TRUTH_PATH = PROJECT_ROOT / "data" / "exports" / "company_truth_spring_master.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "exports" / "legal_entity_alias_candidates.csv"
HIGH_OUTPUT_PATH = PROJECT_ROOT / "data" / "exports" / "legal_entity_alias_high_confidence.csv"
REVIEW_OUTPUT_PATH = PROJECT_ROOT / "data" / "exports" / "legal_entity_alias_medium_confidence_review.csv"


def load_spring_truth_names() -> set[str]:
    with open(SPRING_TRUTH_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    names = set()
    for row in rows:
        names.add(row["canonical_name"])
        names.update(json.loads(row["aliases_json"]))
        names.update(json.loads(row["entity_members_json"]))
    return {name for name in names if name}


def load_tata_companies() -> list[tuple[str, int]]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT company, COUNT(*) FROM jobs WHERE source='tatawangshen' GROUP BY company ORDER BY COUNT(*) DESC"
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def build_candidates() -> list[dict[str, str]]:
    truth_names = load_spring_truth_names()
    truth_normalized = {normalize_company_for_matching(name) for name in truth_names}
    tata_companies = load_tata_companies()

    out = []
    for company, row_count in tata_companies:
        norm = normalize_company_for_matching(company)
        parent = infer_parent_company(norm)

        if company in truth_names or norm in truth_normalized or parent in truth_names or parent in truth_normalized:
            continue

        candidates = find_rule_based_parent_candidates(company, truth_names)
        if not candidates:
            continue

        top = candidates[0]
        out.append(
            {
                "tata_company": company,
                "tata_rows": str(row_count),
                "normalized_legal_name": norm,
                "inferred_parent_name": parent,
                "candidate_parent": top["candidate"],
                "candidate_reason": top["reason"],
                "confidence": top["confidence"],
                "candidate_count": str(len(candidates)),
                "candidate_list_json": json.dumps(candidates, ensure_ascii=False),
            }
        )

    return out


def main() -> None:
    candidates = build_candidates()
    candidates.sort(key=lambda row: (-int(row["tata_rows"]), row["tata_company"]))

    high_candidates, review_candidates = partition_alias_candidates(candidates)

    fieldnames = [
        "tata_company",
        "tata_rows",
        "normalized_legal_name",
        "inferred_parent_name",
        "candidate_parent",
        "candidate_reason",
        "confidence",
        "candidate_count",
        "candidate_list_json",
    ]

    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidates)

    with open(HIGH_OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(high_candidates)

    with open(REVIEW_OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(review_candidates)

    high = sum(1 for row in candidates if row["confidence"] == "high")
    medium = sum(1 for row in candidates if row["confidence"] == "medium")
    covered_rows = sum(int(row["tata_rows"]) for row in candidates)
    high_rows = sum(int(row["tata_rows"]) for row in high_candidates)
    review_rows = sum(int(row["tata_rows"]) for row in review_candidates)

    print(f"output: {OUTPUT_PATH}")
    print(f"candidates: {len(candidates)}")
    print(f"high_confidence: {high}")
    print(f"medium_confidence: {medium}")
    print(f"covered_tata_rows: {covered_rows}")
    print(f"high_output: {HIGH_OUTPUT_PATH} ({len(high_candidates)} rows, covered_tata_rows={high_rows})")
    print(f"review_output: {REVIEW_OUTPUT_PATH} ({len(review_candidates)} rows, covered_tata_rows={review_rows})")


if __name__ == "__main__":
    main()
