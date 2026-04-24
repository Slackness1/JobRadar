from __future__ import annotations

import re


def normalize_company(value: str) -> str:
    text = (value or "").strip()
    text = re.sub(r"（[^）]*岗[^）]*）$", "", text)
    text = re.sub(r"\([^)]*岗[^)]*\)$", "", text)
    return text.strip()


def normalize_job_title(value: str) -> str:
    text = (value or "").strip()
    text = re.sub(r"（[^）]*）$", "", text)
    text = re.sub(r"\([^)]*\)$", "", text)
    return re.sub(r"\s+", "", text)


def normalize_location(value: str) -> str:
    parts = [part.strip() for part in re.split(r"[,，]", value or "") if part.strip()]
    unique_parts = list(dict.fromkeys(parts))
    return ",".join(sorted(unique_parts, key=lambda x: x.encode("gbk", errors="ignore")))


def _richness(record: dict) -> int:
    fields = [
        record.get("detail_url", ""),
        record.get("job_req", ""),
        record.get("job_duty", ""),
        record.get("major_req", ""),
        record.get("company_type_industry", ""),
    ]
    return sum(len(str(v).strip()) for v in fields)


def dedupe_records(records: list[dict]) -> list[dict]:
    best_by_key: dict[tuple[str, str, str], dict] = {}
    for record in records:
        company = normalize_company(str(record.get("company", "")))
        job_title = normalize_job_title(str(record.get("job_title", "")))
        location = normalize_location(str(record.get("location", "")))
        key = (company, job_title, location)

        existing = best_by_key.get(key)
        if existing is None or _richness(record) > _richness(existing):
            merged = dict(record)
            merged["company"] = company
            merged["job_title"] = job_title
            merged["location"] = location
            best_by_key[key] = merged

    return list(best_by_key.values())
