from datetime import datetime

from pydantic import BaseModel, Field


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
    rule_score: int
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
