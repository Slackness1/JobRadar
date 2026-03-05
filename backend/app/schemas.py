from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, field_validator


# ---- Keywords ----
class KeywordOut(BaseModel):
    id: int
    word: str
    model_config = {"from_attributes": True}


class KeywordBatchIn(BaseModel):
    group_id: int
    words: list[str]


# ---- Keyword Groups ----
class KeywordGroupOut(BaseModel):
    id: int
    group_name: str
    sort_order: int
    keywords: list[KeywordOut] = []
    model_config = {"from_attributes": True}


class KeywordGroupIn(BaseModel):
    group_name: str
    sort_order: int = 0


# ---- Tracks ----
class TrackOut(BaseModel):
    id: int
    key: str
    name: str
    weight: float
    min_score: int
    sort_order: int
    groups: list[KeywordGroupOut] = []
    model_config = {"from_attributes": True}


class TrackIn(BaseModel):
    key: str
    name: str
    weight: float = 1.0
    min_score: int = 10
    sort_order: int = 0


class TrackUpdate(BaseModel):
    name: Optional[str] = None
    weight: Optional[float] = None
    min_score: Optional[int] = None
    sort_order: Optional[int] = None


class TrackImportGroupIn(BaseModel):
    group_name: str
    sort_order: int = 0
    keywords: list[str] = []


class TrackImportTrackIn(BaseModel):
    key: str
    name: str
    weight: float = 1.0
    min_score: int = 10
    sort_order: int = 0
    groups: list[TrackImportGroupIn] = []


class TrackImportIn(BaseModel):
    tracks: list[TrackImportTrackIn]


class TrackImportOut(BaseModel):
    replaced: bool
    track_count: int
    group_count: int
    keyword_count: int


# ---- Jobs ----
class JobScoreOut(BaseModel):
    track_id: int
    track_key: str = ""
    track_name: str = ""
    score: int
    matched_keywords: str
    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: int
    job_id: str
    source: str
    company: str
    company_type_industry: str
    company_tags: str
    department: str
    job_title: str
    location: str
    major_req: str
    job_req: str
    job_duty: str
    application_status: str = "待申请"
    job_stage: str = "campus"
    source_config_id: str = ""
    publish_date: Optional[datetime] = None
    deadline: Optional[datetime] = None
    detail_url: str
    scraped_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    total_score: int = 0
    scores: list[JobScoreOut] = []
    model_config = {"from_attributes": True}


class JobListOut(BaseModel):
    items: list[JobOut]
    total: int
    page: int
    page_size: int


ApplicationStatusType = Literal["待申请", "已申请", "已网测", "已面试"]


class JobApplicationStatusIn(BaseModel):
    application_status: ApplicationStatusType


class JobStatsOut(BaseModel):
    total_jobs: int
    today_new: int
    by_track: dict[str, int]
    by_stage: dict[str, int] = {}


# ---- Scoring Config ----
class ScoringConfigOut(BaseModel):
    id: int
    config_json: str
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class ScoringConfigIn(BaseModel):
    config_json: str


# ---- Exclude Rules ----
class ExcludeRuleOut(BaseModel):
    id: int
    category: str
    keyword: str
    model_config = {"from_attributes": True}


class ExcludeRuleIn(BaseModel):
    category: str
    keyword: str


# ---- Crawl ----
class CrawlLogOut(BaseModel):
    id: int
    source: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    status: str
    new_count: int
    total_count: int
    error_message: str
    model_config = {"from_attributes": True}


class CrawlStatusOut(BaseModel):
    is_running: bool
    current_log: Optional[CrawlLogOut] = None


class CrawlTriggerOut(BaseModel):
    log_id: int
    message: str


# ---- Scheduler ----
class SchedulerConfigOut(BaseModel):
    cron_expression: str
    next_run: Optional[str] = None
    is_active: bool


class SchedulerConfigIn(BaseModel):
    cron_expression: str


# ---- Company Recrawl Queue ----
RecrawlQueueStatusType = Literal["pending", "running", "failed", "completed"]


class CompanyRecrawlQueueCreateIn(BaseModel):
    company: str
    department: str = ""
    career_url: str

    @field_validator("company", "career_url")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("must not be empty")
        return text


class CompanyRecrawlQueueOut(BaseModel):
    id: int
    company: str
    department: str
    career_url: str
    source_domain: str = ""
    status: RecrawlQueueStatusType
    attempt_count: int
    fetched_count: int
    new_count: int
    last_error: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class CompanyRecrawlQueueListOut(BaseModel):
    items: list[CompanyRecrawlQueueOut]
    total: int


# ---- System Config ----
class SpringDisplayConfigOut(BaseModel):
    enabled: bool
    cutoff_date: str


class SpringDisplayConfigIn(BaseModel):
    enabled: bool
    cutoff_date: str = "2026-02-01"


# ---- Export ----
class ExportParams(BaseModel):
    search: str = ""
    tracks: list[str] = []
    min_score: int = 0
    days: int = 0
    job_stage: str = "all"
    fields: list[str] = []
