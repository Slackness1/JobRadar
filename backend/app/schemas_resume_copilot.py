from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ResumeEducationItem(BaseModel):
    school: str = ''
    degree: str = ''
    major: str = ''
    start_date: str = ''
    end_date: str = ''
    highlights: list[str] = []


class ResumeInternshipItem(BaseModel):
    company: str = ''
    role: str = ''
    start_date: str = ''
    end_date: str = ''
    bullets: list[str] = []


class ResumeProjectItem(BaseModel):
    name: str = ''
    role: str = ''
    tech_stack: list[str] = []
    bullets: list[str] = []


class ResumeSkillsPayload(BaseModel):
    technical: list[str] = []
    tools: list[str] = []
    languages: list[str] = []


class ResumeProfilePayload(BaseModel):
    basic_info: dict[str, str] = {}
    education: list[ResumeEducationItem] = []
    internships: list[ResumeInternshipItem] = []
    projects: list[ResumeProjectItem] = []
    skills: ResumeSkillsPayload = Field(default_factory=ResumeSkillsPayload)
    languages: list[str] = []
    awards: list[str] = []
    candidate_summary: str = ''
    inferred_roles: list[str] = []
    inferred_tracks: list[str] = []


class DirectionTierResult(BaseModel):
    direction: str
    tier: int  # 1, 2, or 3
    tier_label: str  # "强匹配" | "可迁移" | "有差距"
    strengths: list[str] = []
    gaps: list[str] = []
    transferable_from: list[str] = []


class ResumePreferencePayload(BaseModel):
    preferred_tracks: list[str] = []
    preferred_locations: list[str] = []
    preferred_roles: list[str] = []
    preferred_company_types: list[str] = []
    accept_relocation: bool = False
    accept_internship: bool = False
    campus_only: bool = False
    social_ok: bool = False
    preference_notes: str = ''
    all_skipped: bool = False


class ResumeParsedProfileOut(BaseModel):
    session_id: int
    profile: ResumeProfilePayload


class ResumeConfirmedProfileIn(BaseModel):
    profile: ResumeProfilePayload


class ResumeConfirmedProfileOut(BaseModel):
    session_id: int
    profile: ResumeProfilePayload


class ResumePreferenceIn(BaseModel):
    preferences: ResumePreferencePayload


class ResumePreferenceOut(BaseModel):
    session_id: int
    preferences: ResumePreferencePayload


class ResumeCopilotSessionCreatedOut(BaseModel):
    session_id: int
    status: str
    page_count: int = 0
    file_size_bytes: int = 0


class ResumeCopilotSessionOut(BaseModel):
    id: int
    file_name: str
    name: str = ''
    status: str
    error_message: str
    recommendation_status: str
    feedback_status: str
    has_parsed_profile: bool
    has_confirmed_profile: bool
    has_preferences: bool
    has_recommendations: bool
    has_feedback: bool
    has_direction_analysis: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = {'from_attributes': True}


class ResumeCopilotSessionListItem(BaseModel):
    id: int
    file_name: str
    name: str = ''
    status: str
    has_recommendations: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {'from_attributes': True}


class ResumeCopilotRenameIn(BaseModel):
    name: str


class ResumeGenerateOut(BaseModel):
    session_id: int
    status: str


class ResumeQuickEnrichmentSource(BaseModel):
    title: str = ''
    url: str = ''
    snippet: str = ''


class ResumeQuickEnrichmentProfile(BaseModel):
    summary: str = ''
    likely_orientation: str = ''
    likely_department: str = ''
    target_track_fit: str = ''
    uncertainty_points: list[str] = []
    search_queries: list[str] = []
    sources: list[ResumeQuickEnrichmentSource] = []


class ResumeAgentTraceItem(BaseModel):
    agent: str
    message: str
    status: str = 'completed'
    tool: str = ''
    step_index: int = 0
    result_summary: str = ''


class ResumeRecommendationItem(BaseModel):
    job_id: str
    company: str
    job_title: str
    location: str
    detail_url: str = ''
    objective_score: int
    preference_score: int
    base_job_score: int
    company_priority_score: int = 0
    base_match_score: int = 0
    enhanced_score: int = 0
    final_score: int
    matched_track_key: str = ''
    matched_track_label: str = ''
    matched_role_family: str = ''
    company_priority_tier: str = ''
    company_priority_label: str = ''
    need_enrichment: bool = False
    enrichment_reason: str = ''
    topic_key: str = ''
    topic_cache_status: str = 'not_needed'
    topic_summary: str = ''
    quick_enrichment_profile: ResumeQuickEnrichmentProfile = Field(default_factory=ResumeQuickEnrichmentProfile)
    used_ai: bool = False
    why_recommended: list[str] = []
    strengths: list[str] = []
    risks: list[str] = []
    target_direction: str = ''   # set by ReAct agent in finalize


class ResumeRecommendationResultOut(BaseModel):
    session_id: int
    status: str
    items: list[ResumeRecommendationItem] = []
    agent_trace: list[ResumeAgentTraceItem] = []
    used_ai: bool = False
    fallback_reason: str = ''
    error_message: str = ''


class ResumeFeedbackDiagnosticItem(BaseModel):
    title: str
    description: str


class ResumeFeedbackRewriteExample(BaseModel):
    section: str
    original: str
    improved: str
    rationale: str


class ResumeFeedbackResultOut(BaseModel):
    session_id: int
    status: str
    error_message: str = ''
    diagnostics: list[ResumeFeedbackDiagnosticItem] = []
    rewrite_examples: list[ResumeFeedbackRewriteExample] = []


class RewriteOption(BaseModel):
    option_id: str                  # "A" | "B"
    label: str
    section: str                    # "internships" | "projects" | "candidate_summary"
    field_path: str                 # dot-notation, points to a bullets list or text field.
                                    # Options A and B for the same turn MUST share this path.
    target_title: str = ''          # e.g. "字节跳动 · 产品实习生" — shown on the card
    original: list[str] = []        # all bullets of the targeted block
    improved: list[str] = []        # rewritten bullets for the same block
    rationale: str = ''

    @field_validator('original', 'improved', mode='before')
    @classmethod
    def _coerce_bullets(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, list):
            return [str(v) for v in value]
        return [str(value)]


class ResumeCopilotMessageOut(BaseModel):
    id: int
    role: str           # "system" | "user" | "assistant"
    content: str
    rewrite_options: list[RewriteOption] | None = None
    applied_option_id: str | None = None
    created_at: datetime | None = None


class ChatMessageIn(BaseModel):
    content: str


class ApplyRewriteIn(BaseModel):
    message_id: int
    option_id: str


class ApplyRewriteOut(BaseModel):
    profile: 'ResumeProfilePayload'
    applied: bool = True
