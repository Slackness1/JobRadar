from datetime import datetime
from typing import Any


PREFER_NEW_IF_OLD_EMPTY = {
    "source",
    "company",
    "company_type_industry",
    "company_tags",
    "department",
    "job_title",
    "location",
    "major_req",
    "job_req",
    "job_duty",
    "source_config_id",
    "detail_url",
}

DIRECT_FIELDS = {
    "application_status",
    "publish_date",
    "deadline",
    "scraped_at",
    "job_stage",
}


def _is_empty(value: Any) -> bool:
    return value is None or value == ""


def merge_job_fields(existing: Any, mapped: dict) -> bool:
    """Merge new crawler fields into an existing Job row.

    Rules:
    - preserve user/application state when present
    - fill blank textual fields from new payload
    - refresh timestamps/dates if new value is available
    Returns True if any field changed.
    """
    changed = False

    for field in PREFER_NEW_IF_OLD_EMPTY:
        new_value = mapped.get(field)
        if _is_empty(new_value):
            continue
        old_value = getattr(existing, field, None)
        if _is_empty(old_value):
            setattr(existing, field, new_value)
            changed = True

    for field in DIRECT_FIELDS:
        if field not in mapped:
            continue
        new_value = mapped.get(field)
        if _is_empty(new_value):
            continue
        old_value = getattr(existing, field, None)
        if old_value != new_value:
            setattr(existing, field, new_value)
            changed = True

    # Always keep created_at stable; never overwrite it.
    if getattr(existing, "scraped_at", None) is None and mapped.get("scraped_at"):
        setattr(existing, "scraped_at", mapped["scraped_at"])
        changed = True

    # Normalize naive datetimes if needed.
    for field in ("publish_date", "deadline", "scraped_at"):
        value = getattr(existing, field, None)
        if isinstance(value, datetime):
            continue

    return changed
