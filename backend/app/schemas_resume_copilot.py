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
    # 2026-05-22 P3: 推断学生目标 office 区域,值域 {'hk','sg','mainland','global'}
    # 用于 confirm 页 pre-fill location chip + 推荐时优先该区域岗位
    inferred_offices: list[str] = []


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
    # P0a (resume-copilot-redesign-2026-05-26): soft-archive flag — Sessions
    # page splits 使用中 / 归档 / 全部 tabs from this. Defaults False for
    # backwards compatibility with any client that ignored the field.
    is_archived: bool = False
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
    # 2026-05-20: 实习 / 校招 分流。frontend 据此 split into 两个 tab。
    is_internship: bool = False
    # 2026-05-25 Phase 6-mvp: 行业子方向 chip (TMT/消费/医药/...) — 0-2 个,
    # keyword-based 推断,纯展示用,不入排序。
    industry_tags: list[str] = []


class ResumeRecommendationResultOut(BaseModel):
    session_id: int
    status: str
    items: list[ResumeRecommendationItem] = []
    agent_trace: list[ResumeAgentTraceItem] = []
    used_ai: bool = False
    fallback_reason: str = ''
    error_message: str = ''


class RecommendNarrativeOut(BaseModel):
    """Phase 7 (2026-05-25) — 推荐卡个性化叙事。

    Phase 8 (2026-05-25) — 加 narrative_short 字段,给平台 tab mini job 行用。
    长短两版同一 LLM call 一并生成,共享缓存。
    """
    narrative: str = ''
    narrative_short: str = ''
    action_tip: str = ''
    evidence_refs: list[str] = []
    generated_at: str = ''
    from_cache: bool = False
    status: str = ''


class ResumeRecommendationPlatformJobBrief(BaseModel):
    """Per-platform 卡片 expand 后显示的岗位摘要。完整字段走原 items endpoint。"""
    job_id: str
    job_title: str
    final_score: int
    priority_letter: str = ''
    tier_label: str = ''
    is_internship: bool = False
    location: str = ''
    detail_url: str = ''
    industry_tags: list[str] = []  # 2026-05-25 Phase 6-mvp


class ResumeRecommendationPlatform(BaseModel):
    """聚合后的"平台卡片" — Phase 3 (2026-05-24) 主响应单元。

    rule:
      - 同 company 下所有 jobs 聚合到一张 PlatformCard
      - platform_score = jobs 里最高 final_score (排序用)
      - priority_letter / tier_label = 取最佳 (A > B > C > D, 强匹配 > 可迁移 > 有差距)
      - top_jobs 按 final_score 取 top 3 (实习+校招 混合), all_job_ids 保留全部
      - n_xhs_insights 来自 XHS 知识库 company_target 命中数 — 0 也展示但不挂 chip
    """
    company: str
    company_priority_label: str = ''
    company_priority_tier: str = ''
    platform_score: int = 0
    n_jobs: int = 0
    n_campus: int = 0
    n_internship: int = 0
    n_xhs_insights: int = 0
    track_match_kind: str = ''
    priority_letter: str = ''
    tier_label: str = ''
    matched_track_label: str = ''
    top_jobs: list[ResumeRecommendationPlatformJobBrief] = []
    all_job_ids: list[str] = []


class ResumeRecommendationPlatformsOut(BaseModel):
    session_id: int
    status: str = ''
    platforms: list[ResumeRecommendationPlatform] = []
    n_total_jobs: int = 0
    used_ai: bool = False
    fallback_reason: str = ''


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
    # Optional non-blocking hint shown under the v2 box when memory is empty
    # but a profile-bullet rewrite is still possible (Fix #2): e.g.
    # "📝 你还没在 plan-mode 聊过这段经历,改写仅基于简历表层。"
    soft_hint: str = ''
    # 2026-05-22 #114 Phase 1: 港新学生的英文 bullet。当 profile.inferred_offices
    # 含 hk 或 sg 时,LLM 会同时输出英文版,前端在中文 v2 旁边展示「EN」切换。
    # 其它学生默认为空,前端 UI 不渲染英文块。
    en_text: str = ''


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
    # Plan ② Job plan-mode (2026-05-21): when the student is in chat after
    # clicking "🎯 针对这家定制" on a recommend card, the frontend tags this
    # turn with the job_id so memory extracted from this turn is bound to
    # the job (linked_job_id) — not just the active track.
    active_job_id: str = ''


class ApplyRewriteIn(BaseModel):
    message_id: int
    option_id: str


class ApplyRewriteOut(BaseModel):
    profile: 'ResumeProfilePayload'
    applied: bool = True


# ─── Plan-mode I/O ──────────────────────────────────────────────────────────

class PlanStartIn(BaseModel):
    """Body for POST /sessions/{id}/plan/start.

    2026-05-21: ``focus_kind`` + ``focus_id`` are wired through end-to-end so
    when the student picks a specific 实习 / 项目 in PlanFocusPicker, the BE
    sets ``current_item_id`` to the matching plan item (instead of always
    anchoring to the first one — old behaviour confused students who picked
    "中金 IBD" and saw the AI grill them about "高盛 GBM").

    - ``focus_kind`` currently always ``"experience"``; reserved for future
      kinds like "skill_claim" / "education".
    - ``focus_id``: ``account_memory.id`` (memory entry id) — BE resolves to
      a plan item via ``linked_field_paths`` (e.g. ``"internships.2.bullets.0"``
      → 3rd internship's plan item). If unresolvable, BE falls back to the
      first parent-level item silently.
    """
    focus_kind: str | None = None
    focus_id: int | None = None


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
    # Plan 1 (2026-05-20): resume-edit ↔ memory sync. UI uses these to
    # render the 🔄 "内容已变,建议重聊" badge and to route the student to
    # plan-mode focused on the right bullet.
    linked_field_paths: list[str] = []
    needs_resync: bool = False
    # Plan ② (2026-05-20): which 赛道 was active when this memory was captured.
    # Empty string = general / cross-track. UI shows a tag on the card.
    linked_track: str = ''
    # Plan ② Job plan-mode (2026-05-21): job_id this memory was captured
    # while customising for. Empty = general / track-level.
    linked_job_id: str = ''


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


# ===== 简历多维度打分 (B1) =====


class DimensionScore(BaseModel):
    key: str                       # logic|star|readability|completeness|expression|quantification|track_fit|defensibility
    name: str                      # 中文显示名
    score: int                     # 0-100 现状分
    ceiling: int                   # 0-100 «补齐真实证据后可达» 上限(>= score)
    reason: str = ''               # 一句话诊断


class SectionGap(BaseModel):
    section: str                   # 经历定位,如 "internships.0" / "projects.1"
    label: str = ''                # 该段显示名(公司/项目名),给前端列表用
    gaps: list[str] = []           # 该段的主要缺口(短句)


class ScoreReportOut(BaseModel):
    session_id: int
    target_track: str              # canonical 赛道(打分所对齐的目标)
    overall_current: int           # 现状总分 0-100
    overall_potential_low: int     # 潜力区间下界
    overall_potential_high: int    # 潜力区间上界
    dimensions: list[DimensionScore] = []
    section_gaps: list[SectionGap] = []
    used_ai: bool = False


class ScoreRequestIn(BaseModel):
    target_track: str = ''         # 空 = 后端自动推导
