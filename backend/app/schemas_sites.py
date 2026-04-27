from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


AlertLevel = Literal["green", "yellow", "red", "unknown"]


class SitesSummaryOut(BaseModel):
    active: int
    alerted: int
    disabled: int
    total_today_new: int
    last_batch_at: Optional[datetime]
    last_batch_status: Optional[str]
    today_enriched_count: int = 0
    today_jobs_total: int = 0


class SiteRowOut(BaseModel):
    company: str
    source: str
    last_run_at: Optional[datetime]
    last_status: Optional[str]
    today_new: int
    last_error_short: str
    alert_level: AlertLevel


class SiteRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    fetched_count: int
    new_count: int
    error_message: str
    duration_ms: int
    suggested_fix: str = ""


class SiteRecrawlOut(BaseModel):
    parent_log_id: int
    message: str


class SitesDigestOut(BaseModel):
    text: str
    generated_at: Optional[datetime]
