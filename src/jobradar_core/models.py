from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class JobRecord(BaseModel):
    job_id: str
    source: str = "local_import"
    company: str = ""
    title: str = ""
    location: str = ""
    track: str = ""
    job_type: str = "campus"
    description: str = ""
    requirements: str = ""
    url: str = ""
    publish_date: str = ""
    deadline: str = ""
    crawled_at: str = ""
    quality_label: str = ""
    link_status: str = ""


class JobSearchQuery(BaseModel):
    text: str = ""
    company: str = ""
    location: str = ""
    track: str = ""
    job_type: str = ""
    favorites_only: bool = False
    include_excluded: bool = False
    limit: int = Field(default=50, ge=1, le=200)


class JobSearchResult(BaseModel):
    job: JobRecord
    score: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    features: dict[str, float] = Field(default_factory=dict)
    favorite: bool = False
    excluded: bool = False


class ResumeBlock(BaseModel):
    block_id: str
    text: str
    source_ref: str
    order: int


class ResumeDocument(BaseModel):
    resume_id: str
    original_name: str
    source_path: str
    source_hash: str
    text: str
    blocks: list[ResumeBlock]
    created_at: str = Field(default_factory=utc_now_iso)


PatchIntent = Literal["wording", "structure", "fact_needed"]
PatchStatus = Literal["proposed", "accepted", "edited", "rejected", "blocked"]


class ResumePatch(BaseModel):
    patch_id: str
    target_block_id: str
    before: str
    after: str
    intent: PatchIntent = "wording"
    evidence_refs: list[str] = Field(default_factory=list)
    rationale: str = ""
    risk_flags: list[str] = Field(default_factory=list)
    status: PatchStatus = "proposed"


class ResumeDiagnosis(BaseModel):
    summary: str = ""
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)


class ResumeOptimization(BaseModel):
    run_id: str
    resume: ResumeDocument
    job_id: str = ""
    job_title: str = ""
    jd_hash: str
    diagnosis: ResumeDiagnosis
    patches: list[ResumePatch] = Field(default_factory=list)
    context_manifest: dict = Field(default_factory=dict)
    quality: Literal["valid", "degraded", "unavailable"] = "valid"
    message: str = ""


class RunSummary(BaseModel):
    run_id: str
    workflow: str
    state: str
    status: str
    revision: int = 1
    snapshot_hash: str = ""
    created_at: str
    updated_at: str
    error: str = ""


class RunEvent(BaseModel):
    event_id: str
    run_id: str
    step: str
    event_type: str
    occurred_at: str = Field(default_factory=utc_now_iso)
    duration_ms: int | None = None
    quality: str = "valid"
    summary: str = ""
    error_code: str = ""


class MemoryRecord(BaseModel):
    memory_id: str
    scope: Literal["global", "job_search", "resume", "run"]
    level: Literal["L0", "L1", "L2", "L3"]
    category: str
    summary: str
    payload: dict = Field(default_factory=dict)
    source_ref: str = ""
    user_confirmed: bool = False
    status: Literal["staged", "active", "archived"] = "staged"
