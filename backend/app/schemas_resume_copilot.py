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
    plan_status: str = 'idle'
    has_plan: bool = False
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
    topic_key: str = ''
    # Phase 0 (D-4): snapshot/enrichment fields removed —
    # need_enrichment / enrichment_reason / topic_cache_status / topic_summary /
    # quick_enrichment_profile no longer part of the recommendation contract.
    used_ai: bool = False
    why_recommended: list[str] = []
    strengths: list[str] = []
    risks: list[str] = []
    target_direction: str = ''   # set by ReAct agent in finalize
    tier_label: str = ''         # '强匹配' | '可迁移' | '有差距' — 三档说理
    priority_letter: str = ''    # 'A' | 'B' | 'C' | 'D' — 投递分层 (rule 算)
    track_match_kind: str = ''   # 'hit'|'null_hit'|'transferable'|'ambiguous'|'mismatch'|'no_pref' (debug)


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
    warning: str = ''               # set by the fabrication guard when `improved` introduces
                                    # numeric values not present anywhere in the original profile
    audit_risks: list[dict] = []    # set by audit_draft 5-维 evidence gate;每项 {kind,detail,blocking}
    warning_severity: str = 'info'  # 'info' | 'warn' | 'severe' — UI 角标用

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


# ─── Rewrite v0/v2 (Phase 1 BE-2 — C-1 简) ─────────────────────────────────
#
# v0 = 学生当前简历原文 (echo, 不改)
# v2 = thesis-aware 改写 (基于 account_memory 注入学生独立判断 / 非共识 view)
# 没有 v1 STAR (C-1 简化决策, 见 docs/main-workspace-redesign-2026-05-20.md §0.6)


class RewriteWarningSuggestion(BaseModel):
    """One actionable choice attached to a rewrite warning (C-5)."""
    action: str        # 'fill_real' | 'delete_number' | 'vague'
    label: str         # 学生可见的中文按钮文案


class RewriteWarning(BaseModel):
    """Structured rewrite-warning. Today's only ``type`` is
    ``fabricated_number`` (C-5 red line). Schema is open for future kinds
    (overclaim / leadership_unverified etc.) without bumping the wire format.
    """
    type: str                        # 'fabricated_number' (for now)
    number: str = ''                 # the offending token, when type=fabricated_number
    suggestion_options: list[RewriteWarningSuggestion] = []
    detail: str = ''                 # optional free-text human description


class RewriteVersionV0(BaseModel):
    """v0 — 学生当前原文。Echo of the bullet, no AI rewrite."""
    text: str


class RewriteVersionV2(BaseModel):
    """v2 — thesis-aware 改写, 基于 account_memory entries 注入个人化判断 / 非共识 view.

    ``needs_plan_mode=True`` 表示 memory 拉不到相关 entries, 此时 ``text`` 是
    引导文案而非真实改写 — 学生应去 plan-mode 跟 AI 聊聊这段经历再回来。

    ``warnings`` 由 ``_detect_fabricated_numbers`` 填; 学生应用前必须看到 —
    CLAUDE.md 红线: AI 不可在 v2 里编造原简历没有的数字。
    """
    text: str
    needs_plan_mode: bool = False
    warnings: list[RewriteWarning] = []


class RewriteV0V2In(BaseModel):
    """Request body for POST /sessions/{id}/rewrite/v0v2 (C-1)."""
    bullet_text: str
    field_path: str
    target_job_description: str = ''
    target_title: str = ''
    section: str = ''


class RewriteV0V2Out(BaseModel):
    """Response shape for the C-1 simplified rewrite path: v0 + v2 only.

    ``field_path`` / ``target_title`` mirror ``RewriteOption`` so the same
    ``apply_rewrite`` traversal logic can later be reused (FE-3 wires up the
    apply button against this schema)."""
    field_path: str            # e.g. 'internships.0.bullets.0' or 'internships.0.bullets'
    section: str = ''          # 'internships' | 'projects' | 'candidate_summary'
    target_title: str = ''     # "字节跳动 · 产品实习生"
    v0: RewriteVersionV0
    v2: RewriteVersionV2
    rationale: str = ''        # why v2 is shaped this way — visible in the diff panel
    memory_refs: list[int] = []  # account_memory.id of injected entries (audit/debug)


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


# ─── Plan-mode I/O ──────────────────────────────────────────────────────────

class PlanStartIn(BaseModel):
    """Body for POST /sessions/{id}/plan/start. Currently empty — derived
    counts come from the persisted parsed profile. Reserved for future
    template overrides."""
    pass


class AgentActionIn(BaseModel):
    """Request body for POST /sessions/{id}/plan/actions.

    Mirrors ``AgentAction`` in services.resume_copilot.plan but is a separate
    type so the router layer can validate / version-check before crossing
    into the service module."""
    action: str
    item_id: str | None = None
    payload: dict = {}
    expected_version: int | None = None


class PlanStateOut(BaseModel):
    """Wire-level view of PlanState.

    The service-layer ``PlanState`` already serializes via Pydantic, but the
    router returns a dict directly (``state.model_dump(mode='json')``) so the
    router doesn't have to depend on the service module's enum classes."""
    version: int
    status: str
    current_item_id: str | None = None
    items: list[dict] = []
    replan_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ─── Memory API (Phase 0 P0-2) ──────────────────────────────────────────────

class MemoryEntryOut(BaseModel):
    """One ``account_memory`` row as returned by the memory endpoints.

    Payload shape varies per category — kept as a free-form dict here so the
    HTTP contract isn't tied to the 8 category-specific pydantic schemas
    (which live in ``app.services.memory.schemas``). Frontend can switch on
    ``category`` to render the right view."""
    id: int
    category: str
    summary: str
    payload: dict = {}
    confidence: float = 0.0
    user_confirmed: bool = False
    use_count: int = 0
    is_archived: bool = False
    superseded_by_id: int | None = None
    source_module: str = ''
    source_session_id: int | None = None
    raw_excerpt: str = ''
    captured_at: str | None = None
    last_verified_at: str | None = None
    last_used_at: str | None = None


class MemoryGroupedOut(BaseModel):
    """Response for ``GET /sessions/{id}/memory`` — entries grouped by the
    8 canonical categories. Each value is the list of non-archived rows for
    that category (most recently captured first)."""
    session_id: int
    user_key: str
    entries: dict[str, list[MemoryEntryOut]]


class MemoryEntryCreateIn(BaseModel):
    """Request body for ``POST /sessions/{id}/memory``.

    ``category`` must be one of the 8 canonical categories; ``payload`` is
    validated against the matching pydantic schema inside the dispatcher."""
    category: str
    summary: str
    payload: dict = {}
    raw_excerpt: str = ''
    confidence: float = 1.0


class MemoryEntryPatchIn(BaseModel):
    """Request body for ``PATCH /sessions/{id}/memory/{entry_id}``.

    A-3 简(main-workspace-redesign-2026-05-20 Phase 1 BE-1):学生只能改两个
    字段 —— ``summary`` (常驻索引短句) 和 ``payload`` (结构化字段)。
    其它字段(category / confidence / raw_excerpt …)由 writer 一次性写入,
    不允许学生修改 —— 改 category 会破坏 reader 的语义,改 raw_excerpt 会破坏
    anti-hallucination 审计链。

    两个字段均 optional;只提供哪个就改哪个,都不提供 → 422。"""

    summary: str | None = None
    payload: dict | None = None


# ─── Recommendation reject (BE-3, D-2 / D-3) ─────────────────────────────────

REJECT_REASON_LABELS: dict[str, str] = {
    'wrong_track': '赛道不对',
    'company_disliked': '公司不喜欢',
    'school_mismatch': '学校段位不匹配',
    'timing': '时间不合适',
    'other': '其他',
}


class RecommendRejectIn(BaseModel):
    """Request body for POST /sessions/{id}/recommendations/{job_id}/reject.

    ``reason`` must be one of ``REJECT_REASON_LABELS``. ``note`` is the
    optional free-text the user typed in the inline form (≤2000 chars).
    """
    reason: str
    note: str = ''


class RecommendRejectOut(BaseModel):
    """Response for the reject endpoint. ``memory_entry_id`` lets the frontend
    show "已记入档案: id=..." for testing/debugging; ``rejected_count`` is the
    session-scoped list length after dedupe so the UI can show a small badge."""
    ok: bool = True
    memory_entry_id: int | None = None
    rejected_count: int = 0
