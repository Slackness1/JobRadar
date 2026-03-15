from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, field_validator


# ---- Job Intel Tasks ----

class JobIntelTaskOut(BaseModel):
    id: int
    job_id: int
    trigger_mode: str
    search_level: str
    platform_scope_json: str
    query_bundle_json: str
    status: str
    result_count: int
    error_message: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class JobIntelSearchRequest(BaseModel):
    trigger_mode: Literal["manual", "auto_follow", "refresh"] = "manual"
    platforms: list[str] = ["xiaohongshu", "maimai", "nowcoder", "boss", "zhihu"]
    force: bool = False


class JobIntelRefreshRequest(BaseModel):
    force: bool = False


# ---- Job Intel Records ----

class JobIntelRecordOut(BaseModel):
    id: int
    job_id: int
    task_id: Optional[int] = None
    platform: str
    content_type: str
    platform_item_id: str
    title: str
    author_name: str
    author_meta_json: str
    url: str
    publish_time: Optional[datetime] = None
    raw_text: str
    cleaned_text: str
    summary: str
    keywords_json: str
    tags_json: str
    metrics_json: str
    entities_json: str
    relevance_score: float
    confidence_score: float
    sentiment: str
    data_version: str
    fetched_at: Optional[datetime] = None
    parsed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class JobIntelCommentOut(BaseModel):
    id: int
    intel_record_id: int
    platform_comment_id: str
    parent_comment_id: str
    author_name: str
    content: str
    like_count: int
    publish_time: Optional[datetime] = None
    relevance_score: float
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# ---- Job Intel Snapshots ----

class JobIntelSnapshotOut(BaseModel):
    id: int
    job_id: int
    snapshot_type: str
    summary_text: str
    evidence_count: int
    source_platforms_json: str
    confidence_score: float
    generated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# ---- Job Intel Summary ----

class JobIntelSummaryOut(BaseModel):
    job_id: int
    latest_task_id: Optional[int] = None
    latest_task_status: Optional[str] = None
    records_count: int
    snapshots: list[JobIntelSnapshotOut]
    model_config = {"from_attributes": True}


# ---- Platform Status ----

class JobIntelPlatformStatusOut(BaseModel):
    platform: str
    status: str
    last_login_at: Optional[datetime] = None
    last_error: str
    model_config = {"from_attributes": True}


# ---- Common Responses ----

class JobIntelTaskCreatedOut(BaseModel):
    task_id: int
    status: str
    query_bundle: dict


class JobIntelRecordsListOut(BaseModel):
    items: list[JobIntelRecordOut]
    total: int
    page: int
    page_size: int
    has_more: bool
    model_config = {"from_attributes": True}
