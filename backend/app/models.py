from datetime import datetime
from sqlalchemy import Boolean, Column, Integer, Text, Float, DateTime, ForeignKey, UniqueConstraint, LargeBinary, event, func
from sqlalchemy.orm import relationship
from app.database import Base


class JobIntelTask(Base):
    __tablename__ = "job_intel_tasks"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    trigger_mode = Column(Text, default="manual")
    search_level = Column(Text, default="strict")
    platform_scope_json = Column(Text, default="[]")
    query_bundle_json = Column(Text, default="{}")
    status = Column(Text, default="queued")
    result_count = Column(Integer, default=0)
    error_message = Column(Text, default="")
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", foreign_keys=[job_id])


class JobIntelRecord(Base):
    __tablename__ = "job_intel_records"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("job_intel_tasks.id", ondelete="SET NULL"))
    platform = Column(Text, default="")
    content_type = Column(Text, default="")
    platform_item_id = Column(Text, default="")
    title = Column(Text, default="")
    author_name = Column(Text, default="")
    author_meta_json = Column(Text, default="{}")
    url = Column(Text, default="")
    publish_time = Column(DateTime, nullable=True)
    raw_text = Column(Text, default="")
    cleaned_text = Column(Text, default="")
    summary = Column(Text, default="")
    keywords_json = Column(Text, default="[]")
    tags_json = Column(Text, default="[]")
    metrics_json = Column(Text, default="{}")
    entities_json = Column(Text, default="{}")
    relevance_score = Column(Float, default=0)
    confidence_score = Column(Float, default=0)
    sentiment = Column(Text, default="")
    data_version = Column(Text, default="v1")
    fetched_at = Column(DateTime, default=datetime.utcnow)
    parsed_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class JobIntelComment(Base):
    __tablename__ = "job_intel_comments"

    id = Column(Integer, primary_key=True)
    intel_record_id = Column(Integer, ForeignKey("job_intel_records.id", ondelete="CASCADE"), nullable=False, index=True)
    platform_comment_id = Column(Text, default="")
    parent_comment_id = Column(Text, default="")
    author_name = Column(Text, default="")
    content = Column(Text, default="")
    like_count = Column(Integer, default=0)
    publish_time = Column(DateTime, nullable=True)
    relevance_score = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ResumeCopilotSession(Base):
    __tablename__ = "resume_copilot_sessions"

    id = Column(Integer, primary_key=True)
    file_name = Column(Text, default="")
    name = Column(Text, default="")
    user_key = Column(Text, default="", index=True)
    status = Column(Text, default="uploaded", index=True)
    extracted_text = Column(Text, default="")
    error_message = Column(Text, default="")
    recommendation_status = Column(Text, default="pending")
    feedback_status = Column(Text, default="pending")
    is_guest = Column(Integer, default=0, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    plan_json = Column(Text, nullable=True)
    plan_status = Column(Text, default="idle", index=True)
    # BE-3 of main-workspace-redesign-2026-05-20 (D-2 / D-3 / D-5):
    # rejected_job_ids_json — session-scoped list of job_ids the user has
    # ✗-rejected from recommendations; filtered out on every regenerate.
    # last_recommend_trigger_at — used by should_debounce_recommend() to
    # collapse rapid back-to-back regenerate triggers.
    rejected_job_ids_json = Column(Text, default="[]", nullable=True)
    last_recommend_trigger_at = Column(DateTime, nullable=True)
    # P0a (resume-copilot-redesign-2026-05-26): soft-archive flag — sessions
    # the user keeps but no longer actively edits. Surfaced to Sessions page so
    # active / archived can be split into filter tabs without DELETE'ing rows.
    # Defaults to False; default index keeps GET /sessions filter cheap.
    is_archived = Column(Boolean, default=False, nullable=False, server_default='0', index=True)

    parsed_profile = relationship(
        "ResumeParsedProfile",
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
    )
    confirmed_profile = relationship(
        "ResumeConfirmedProfile",
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
    )
    preference_profile = relationship(
        "ResumePreferenceProfile",
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
    )
    recommendation_run = relationship(
        "ResumeRecommendationRun",
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
    )
    feedback_run = relationship(
        "ResumeFeedbackRun",
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
    )
    direction_analysis_run = relationship(
        "ResumeDirectionAnalysisRun",
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
    )
    chat_messages = relationship(
        "ResumeCopilotMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ResumeCopilotMessage.created_at",
    )


class ResumeParsedProfile(Base):
    __tablename__ = "resume_parsed_profiles"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("resume_copilot_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    profile_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ResumeCopilotSession", back_populates="parsed_profile")


class ResumeConfirmedProfile(Base):
    __tablename__ = "resume_confirmed_profiles"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("resume_copilot_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    profile_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ResumeCopilotSession", back_populates="confirmed_profile")


class ResumePreferenceProfile(Base):
    __tablename__ = "resume_preference_profiles"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("resume_copilot_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    preferences_json = Column(Text, default="{}")
    all_skipped = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ResumeCopilotSession", back_populates="preference_profile")


class ResumeRecommendationRun(Base):
    __tablename__ = "resume_recommendation_runs"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("resume_copilot_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    status = Column(Text, default="pending")
    error_message = Column(Text, default="")
    used_ai = Column(Integer, default=0)
    fallback_reason = Column(Text, default="")
    agent_trace_json = Column(Text, default="[]")
    recommendations_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ResumeCopilotSession", back_populates="recommendation_run")


class ResumeFeedbackRun(Base):
    __tablename__ = "resume_feedback_runs"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("resume_copilot_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    status = Column(Text, default="pending")
    error_message = Column(Text, default="")
    diagnostics_json = Column(Text, default="[]")
    rewrite_examples_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ResumeCopilotSession", back_populates="feedback_run")


class ResumeDirectionAnalysisRun(Base):
    __tablename__ = "resume_direction_analysis_runs"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("resume_copilot_sessions.id", ondelete="CASCADE"), nullable=False, unique=True)
    status = Column(Text, default="pending")
    error_message = Column(Text, default="")
    directions_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ResumeCopilotSession", back_populates="direction_analysis_run")


class ResumeCopilotMessage(Base):
    __tablename__ = "resume_copilot_messages"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("resume_copilot_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(Text, default="user")      # system | user | assistant
    content = Column(Text, default="")
    rewrite_options_json = Column(Text, nullable=True)   # JSON list[RewriteOption] or null
    applied_option_id = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ResumeCopilotSession", back_populates="chat_messages")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    job_id = Column(Text, unique=True, nullable=False, index=True)
    source = Column(Text, default="tatawangshen")
    company = Column(Text, default="")
    company_type_industry = Column(Text, default="")
    company_tags = Column(Text, default="")
    department = Column(Text, default="")
    job_title = Column(Text, default="")
    location = Column(Text, default="")
    major_req = Column(Text, default="")
    job_req = Column(Text, default="")
    job_duty = Column(Text, default="")
    application_status = Column(Text, default="待申请")
    job_stage = Column(Text, default="campus")
    source_config_id = Column(Text, default="")
    publish_date = Column(DateTime, nullable=True)
    deadline = Column(DateTime, nullable=True)
    detail_url = Column(Text, default="")
    scraped_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    track_predicted = Column(Text, nullable=False, default="")
    quality_label = Column(Text, nullable=False, default="")
    # Phase B (2026-05-16): canonicalize_job(source, job_title) 的结果,
    # 自动通过 before_insert/before_update event listener (database.py 里挂)
    # 写入。None = 1:N 歧义 source 且 job_title 无信号,留给下游 LLM rerank。
    # 与 track_predicted (LLM 自由文本) 平级,canonical_track 是 enum-constrained。
    canonical_track = Column(Text, nullable=True, index=True)
    # v2 (2026-05-24): 10 → 13 canon 重构时备份的老 canonical_track 值, 给
    # backfill 脚本拆 ambiguous 池 (二级买方/卖方·S&T/一级市场/战略咨询) 当 hint。
    # 只在 alembic f1a8e3c7b2d5_canonical_track_v2_rename 设值, 之后只读不动。
    canonical_track_pre_v2 = Column(Text, nullable=True)
    # L3 (2026-05-22): detail_url HEAD 探活结果。NULL=未探过, alive/dead/uncertain。
    # cron 每天 10:00 跑 link_prober 更新; 推荐 SQL 排除 link_status='dead'。
    link_status = Column(Text, nullable=True, index=True)
    link_checked_at = Column(DateTime, nullable=True)
    # Phase G (2026-05-27): 27 sub_category × 3-dim taxonomy 字段。
    # sub_category / sub_cat_* 由 T1 分类器写入; institution_tier 由 T2 写入。
    # 推荐 v2 链路通过 RECOMMENDATION_V2_ENABLED 灰度切换。
    sub_category = Column(Text, nullable=True, index=True)
    sub_category_secondary = Column(Text, nullable=True)
    industry_focus = Column(Text, nullable=True)        # JSON array as string
    institution_tier = Column(Text, nullable=True, index=True)
    sub_cat_confidence = Column(Float, nullable=True)
    sub_cat_reasoning = Column(Text, nullable=True)
    sub_cat_enriched_at = Column(DateTime, nullable=True)

    scores = relationship("JobScore", back_populates="job", cascade="all, delete-orphan")


# Phase B (2026-05-16): 自动派生 canonical_track。
# 挂 model 上而不是 20+ 个 Job() 调用点 — 改一处生效,新增 crawler 不会漏。
# 已经显式设过的不覆盖(尊重 caller 意图,e.g. review_queue 改 track,或
# backfill 直接赋值)。import taxonomy 在函数里做,避免循环 import / 启动开销。
@event.listens_for(Job, 'before_insert')
@event.listens_for(Job, 'before_update')
def _populate_job_canonical_track(_mapper, _conn, target: 'Job') -> None:
    if getattr(target, 'canonical_track', None):
        return
    from app.services.taxonomy import canonicalize_job
    target.canonical_track = canonicalize_job(
        getattr(target, 'source', '') or '',
        getattr(target, 'job_title', '') or '',
    )


class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True)
    key = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    weight = Column(Float, default=1.0)
    min_score = Column(Integer, default=10)
    sort_order = Column(Integer, default=0)
    # Phase F (2026-05-16): 映射到 app.services.taxonomy 的 canonical key。
    # nullable — Track 是 keyword tier-scoring 的桶,不一定能对应到 8 canonical
    # 任一项 (e.g. other_foreign 太杂)。空 = 不归属。
    canonical_track = Column(Text, nullable=True)

    groups = relationship("KeywordGroup", back_populates="track", cascade="all, delete-orphan",
                          order_by="KeywordGroup.sort_order")
    scores = relationship("JobScore", back_populates="track", cascade="all, delete-orphan")


class KeywordGroup(Base):
    __tablename__ = "keyword_groups"

    id = Column(Integer, primary_key=True)
    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False)
    group_name = Column(Text, nullable=False)
    sort_order = Column(Integer, default=0)

    track = relationship("Track", back_populates="groups")
    keywords = relationship("Keyword", back_populates="group", cascade="all, delete-orphan")


class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("keyword_groups.id", ondelete="CASCADE"), nullable=False)
    word = Column(Text, nullable=False)

    group = relationship("KeywordGroup", back_populates="keywords")


class ScoringConfig(Base):
    __tablename__ = "scoring_config"

    id = Column(Integer, primary_key=True)
    config_json = Column(Text, nullable=False, default="{}")
    updated_at = Column(DateTime, default=datetime.utcnow)


class ExcludeRule(Base):
    __tablename__ = "exclude_rules"

    id = Column(Integer, primary_key=True)
    category = Column(Text, nullable=False)
    keyword = Column(Text, nullable=False)


class JobScore(Base):
    __tablename__ = "job_scores"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False)
    score = Column(Integer, default=0)
    matched_keywords = Column(Text, default="[]")
    scored_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="scores")
    track = relationship("Track", back_populates="scores")

    __table_args__ = (
        UniqueConstraint("job_id", "track_id", name="uq_job_track"),
    )


class CrawlLog(Base):
    __tablename__ = "crawl_logs"

    id = Column(Integer, primary_key=True)
    source = Column(Text, default="tatawangshen")
    target_url = Column(Text, default="")
    final_url = Column(Text, default="")
    page_title = Column(Text, default="")
    ats_family = Column(Text, default="")
    framework_family = Column(Text, default="")
    detection_flags_json = Column(Text, default="{}")
    evidence_json = Column(Text, default="{}")
    failure_reason = Column(Text, default="")
    failure_reasons_json = Column(Text, default="[]")
    completeness_score = Column(Float, default=0)
    zero_result_type = Column(Text, default="")
    fallback_action = Column(Text, default="")
    detail_link_count = Column(Integer, default=0)
    job_signal_count = Column(Integer, default=0)
    page_claimed_count = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    status = Column(Text, default="running")
    new_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    error_message = Column(Text, default="")


class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True)
    key = Column(Text, unique=True, nullable=False)
    value = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime, default=datetime.utcnow)


class CompanyRecrawlQueue(Base):
    __tablename__ = "company_recrawl_queue"

    id = Column(Integer, primary_key=True)
    company = Column(Text, nullable=False, index=True)
    department = Column(Text, default="")
    career_url = Column(Text, nullable=False)
    source_domain = Column(Text, default="")
    status = Column(Text, default="pending", index=True)
    attempt_count = Column(Integer, default=0)
    fetched_count = Column(Integer, default=0)
    new_count = Column(Integer, default=0)
    last_error = Column(Text, default="")
    failure_reason = Column(Text, default="")
    failure_reasons_json = Column(Text, default="[]")
    last_detection_json = Column(Text, default="{}")
    last_evidence_json = Column(Text, default="{}")
    completeness_score = Column(Float, default=0)
    zero_result_type = Column(Text, default="")
    fallback_action = Column(Text, default="")
    priority = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)


class InterviewReport(Base):
    __tablename__ = 'interview_reports'

    id = Column(Integer, primary_key=True, index=True)
    user_key = Column(Text, nullable=False, index=True)
    target_job = Column(Text, nullable=False)
    transcript_json = Column(Text, default='[]')
    report_json = Column(Text, default='{}')
    duration_seconds = Column(Integer, default=0)
    is_guest = Column(Integer, default=0, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    weakness_profile_json = Column(Text, nullable=True)
    weekly_plan_md = Column(Text, default="")
    turn_count = Column(Integer, default=0)


class InterviewIntelKeyword(Base):
    __tablename__ = "interview_intel_keywords"

    keyword = Column(Text, primary_key=True)
    summary_md = Column(Text, default="")
    source_count = Column(Integer, default=0)
    generated_at = Column(DateTime, nullable=True)
    last_error = Column(Text, default="")
    posts_hash = Column(Text, default="")


class InterviewIntelPost(Base):
    __tablename__ = "interview_intel_posts"

    pid = Column(Text, primary_key=True)
    keyword = Column(Text, primary_key=True, index=True)
    title = Column(Text, default="")
    company = Column(Text, default="")
    interview_date = Column(Text, default="")
    position = Column(Text, default="")
    questions_text = Column(Text, default="")
    fetched_at = Column(DateTime, default=datetime.utcnow)
    parse_status = Column(Text, default="ok")
    quality_score = Column(Integer, default=2)


class CompanyCrawlLog(Base):
    __tablename__ = "company_crawl_logs"

    id = Column(Integer, primary_key=True)
    source = Column(Text, nullable=False, index=True)
    company = Column(Text, nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    status = Column(Text, nullable=False, default="running")
    fetched_count = Column(Integer, nullable=False, default=0)
    new_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=False, default="")
    parent_log_id = Column(Integer, nullable=True, index=True)
    duration_ms = Column(Integer, nullable=False, default=0)
    suggested_fix = Column(Text, nullable=False, default="")


class InterviewTurn(Base):
    __tablename__ = "interview_turns"

    id = Column(Integer, primary_key=True)
    session_id = Column(Text, nullable=False, index=True)
    user_key = Column(Text, default="", index=True)
    turn_index = Column(Integer, nullable=False)
    target_job = Column(Text, default="")
    question = Column(Text, default="")
    user_answer = Column(Text, default="")
    asr_transcript = Column(Text, default="")
    voice_metrics = Column(Text, nullable=True)
    score_json = Column(Text, nullable=True)
    reference_answer = Column(Text, default="")
    question_source = Column(Text, default="skeleton")
    parent_turn_index = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class StudentExperience(Base):
    """Cross-session personal knowledge base for one student (keyed on user_key).

    Schema aligned with Claude Code's memory file design — see CLAUDE.md "Student KB"
    section for rationale. Each row is one "experience" or related fact extracted
    from the resume-copilot chat rail and re-usable in mock interview prompts.
    """

    __tablename__ = "student_experiences"

    id = Column(Integer, primary_key=True)
    user_key = Column(Text, nullable=False, index=True)
    source_session_id = Column(
        Integer,
        ForeignKey("resume_copilot_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )

    name = Column(Text, default="")                    # ≤20 char human-readable
    summary = Column(Text, default="")                 # ≤30 char, lives in always-on index
    summary_hash = Column(Text, default="", index=True)  # dedup key
    category = Column(Text, default="experience")      # experience | skill_claim | preference | identity_fact
    star_dimensions_json = Column(Text, default="[]")  # JSON list[str], retrieval index for category=experience
    behavioral_hook = Column(Text, default="")         # STAR-structured template the interview LLM reuses verbatim
    quantified_json = Column(Text, default="{}")       # JSON dict (team_size, duration_months, outcome, ...)
    raw_excerpt = Column(Text, default="")             # original chat substring — anti-hallucination + audit trail
    confidence = Column(Float, default=0.0)            # LLM self-rated 0-1
    user_confirmed = Column(Boolean, default=False, index=True)

    # 3-anchor flags — for category='experience', all three must be True or the row is rejected at extraction time.
    has_temporal_anchor = Column(Boolean, default=False)
    has_concrete_action = Column(Boolean, default=False)
    has_outcome = Column(Boolean, default=False)

    # Time / staleness — mirrors Claude Code's "memory is N days old" injection.
    captured_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_verified_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    use_count = Column(Integer, default=0)

    # User-driven lifecycle
    is_archived = Column(Boolean, default=False)       # user marked outdated / superseded

    __table_args__ = (
        UniqueConstraint("user_key", "summary_hash", name="uq_student_experience_user_summary"),
    )


class AccountMemory(Base):
    """Unified account-scoped memory layer — single table, category-discriminated.

    Replaces piecemeal stores (student_experiences, plan_json-embedded Evidence)
    with one row-per-fact design. See docs/unified-memory-and-plan-mode-2026-05-13.md
    for full rationale and the 8 categories' payload schemas.

    Provenance is a first-class concept: every row remembers which module produced
    it (`source_module`), which session and which message inside that session
    (`source_session_id` / `source_message_id`), and the original raw text
    (`raw_excerpt`) for anti-hallucination audit. Mirrors Claude Code memory's
    `originSessionId` + verify-before-recommend pattern.
    """

    __tablename__ = "account_memory"

    id = Column(Integer, primary_key=True)

    # Identity + discriminator
    user_key = Column(Text, nullable=False, index=True)
    category = Column(Text, nullable=False, index=True)
    # one of: evidence | experience | skill_claim | preference |
    #         identity_fact | goal | commitment | weakness_signal

    # Content
    summary = Column(Text, default="")               # short, always-on index field
    payload_json = Column(Text, default="{}")        # category-specific (pydantic-validated)
    summary_hash = Column(Text, default="", index=True)  # dedup key

    # Provenance
    source_module = Column(Text, default="")         # chat | plan | parser | interview | manual
    source_session_id = Column(Integer, nullable=True)
    source_message_id = Column(Integer, nullable=True)
    raw_excerpt = Column(Text, default="")           # source citation, anti-hallucination anchor

    # Confidence + user-confirmation
    confidence = Column(Float, default=0.0)
    user_confirmed = Column(Boolean, default=False, index=True)

    # Lifecycle
    captured_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_verified_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    use_count = Column(Integer, default=0)

    # Evolution (versioning via supersession chain)
    superseded_by_id = Column(Integer, nullable=True)   # FK-shaped but not enforced (intra-table)
    is_archived = Column(Boolean, default=False, index=True)

    # Resume-edit sync (Plan 1, 2026-05-20).
    # `linked_field_paths` = JSON list[str] of resume bullet paths this row was
    # extracted from (e.g. ["internships.0.bullets.2"]). Empty list when memory
    # is general / not tied to a bullet (preference rows, identity_fact, etc.).
    # `needs_resync` set to True when user edits one of the linked bullets via
    # the right-pane edit toolbar — ArchivePanel renders a 🔄 badge.
    linked_field_paths = Column(Text, default="[]")
    needs_resync = Column(Boolean, default=False)
    # Plan ② (2026-05-20): canonical 赛道 name the student was working on
    # when this memory was captured. Lets ArchivePanel render a track tag on
    # the card + lets recall optionally filter by track. Empty string = not
    # tagged (general / cross-track memory, e.g. preference rows).
    linked_track = Column(Text, default="")
    # Plan ② Job plan-mode (2026-05-21): job_id this memory was captured
    # while customising for. Empty = general / track-level memory.
    # ArchivePanel can show a job tag; rewrite recall can boost memory for
    # the matching job.
    linked_job_id = Column(Text, default="")

    __table_args__ = (
        UniqueConstraint("user_key", "summary_hash", name="uq_account_memory_user_summary"),
    )


class JobDraft(Base):
    """Teacher quick-entry: one job draft (link / OCR / JD-text input → parsed → review queue)."""

    __tablename__ = "job_drafts"

    id = Column(Integer, primary_key=True)
    teacher_user_key = Column(Text, default="", index=True)
    teacher_name = Column(Text, default="")
    teacher_dept = Column(Text, default="")
    source_type = Column(Text, default="link")           # link | ocr | text
    source_payload = Column(Text, default="")             # raw URL / OCR text / pasted JD
    parse_confidence = Column(Float, default=0)           # 0–100
    parsed_title = Column(Text, default="")
    parsed_company = Column(Text, default="")
    parsed_location = Column(Text, default="")
    parsed_jd_summary = Column(Text, default="")
    parsed_deadline = Column(Text, default="")            # keep as text; varied formats
    parsed_salary = Column(Text, default="")
    parsed_detail_url = Column(Text, default="")
    track = Column(Text, default="other")                 # finance | fintech | other
    tags_json = Column(Text, default="[]")                # JSON list[str]
    teacher_note = Column(Text, default="")
    status = Column(Text, default="draft", index=True)    # draft | pending | approved | rejected
    reject_reason = Column(Text, default="")
    submitted_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class PodcastEpisode(Base):
    __tablename__ = "podcast_episodes"

    id = Column(Integer, primary_key=True)
    eid = Column(Text, unique=True, nullable=False, index=True)
    show = Column(Text, default="")
    title = Column(Text, default="")
    duration_sec = Column(Integer, default=0)
    topic_one_liner = Column(Text, default="")
    summary_500 = Column(Text, default="")
    audience = Column(Text, default="")
    guests_json = Column(Text, default="[]")
    hot_takes_json = Column(Text, default="[]")
    covers_role_json = Column(Text, default="[]")
    covers_company_json = Column(Text, default="[]")
    covers_sector_json = Column(Text, default="[]")
    embedding = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class PodcastInsight(Base):
    __tablename__ = "podcast_insights"

    id = Column(Integer, primary_key=True)
    insight_id = Column(Text, unique=True, nullable=False, index=True)
    source_eid = Column(Text, nullable=False, index=True)
    type_json = Column(Text, default="[]")
    primary_type = Column(Text, default="", index=True)
    role_target_json = Column(Text, default="[]")
    company_target_json = Column(Text, default="[]")
    sector_target_json = Column(Text, default="[]")
    content = Column(Text, nullable=False)
    source_quote = Column(Text, default="")
    speaker = Column(Text, default="unknown")
    confidence = Column(Text, default="med", index=True)
    corroboration_json = Column(Text, default="[]")
    embedding = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class XhsNote(Base):
    """XHS (小红书) post = source row for XhsInsight. Mirrors PodcastEpisode role."""

    __tablename__ = "xhs_notes"

    id = Column(Integer, primary_key=True)
    note_id = Column(Text, unique=True, nullable=False, index=True)
    title = Column(Text, default="")
    desc = Column(Text, default="")
    author_name = Column(Text, default="")
    author_id = Column(Text, default="")
    tags_json = Column(Text, default="[]")
    liked_count = Column(Integer, default=0)
    collected_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    signal_score = Column(Float, default=0.0)
    matched_keywords_json = Column(Text, default="[]")
    source_url = Column(Text, default="")
    time_iso = Column(Text, default="")
    embedding = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class XhsInsight(Base):
    """Typed insight extracted from an XHS note (post + top comments)."""

    __tablename__ = "xhs_insights"

    id = Column(Integer, primary_key=True)
    insight_id = Column(Text, unique=True, nullable=False, index=True)
    source_note_id = Column(Text, nullable=False, index=True)
    type_json = Column(Text, default="[]")
    primary_type = Column(Text, default="", index=True)
    role_target_json = Column(Text, default="[]")
    company_target_json = Column(Text, default="[]")
    sector_target_json = Column(Text, default="[]")
    content = Column(Text, nullable=False)
    source_quote = Column(Text, default="")
    speaker = Column(Text, default="unknown")  # author | commenter | unknown
    confidence = Column(Text, default="med", index=True)
    corroboration_json = Column(Text, default="[]")
    embedding = Column(LargeBinary, nullable=True)
    source_score = Column(Float, nullable=True)
    source_platform = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Knowledge pack — public 智库 layer (per-employer rubric/quote/example bank)
# Sourced from skill packs like tencent-recruit-pack/. Read by
# TencentTrackProvider / SensitiveTopicProvider via fetch_blocks().
# ---------------------------------------------------------------------------


class KnowledgeEmployer(Base):
    """Lookup row per public-knowledge owner. Use 'tencent' for tencent-recruit-pack
    and '__generic__' for cross-employer methodology (STAR, group-interview rubrics)."""

    __tablename__ = "knowledge_employers"

    id = Column(Integer, primary_key=True)
    employer_key = Column(Text, unique=True, nullable=False, index=True)
    display_name = Column(Text, default="")
    description = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeTrack(Base):
    """Per-employer track lookup (技术 / 产品 / 游戏 / 市场 ...)."""

    __tablename__ = "knowledge_tracks"

    id = Column(Integer, primary_key=True)
    employer_key = Column(Text, nullable=False, index=True)
    track_key = Column(Text, nullable=False, index=True)
    display_name = Column(Text, default="")
    aliases_json = Column(Text, default="[]")
    description = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("employer_key", "track_key", name="uq_knowledge_track"),
    )


class KnowledgeFile(Base):
    """Source-of-truth .md content. Hash-based dedup so re-ingest is idempotent."""

    __tablename__ = "knowledge_files"

    id = Column(Integer, primary_key=True)
    employer_key = Column(Text, nullable=False, index=True)
    file_path = Column(Text, nullable=False)
    content_md = Column(Text, default="")
    content_hash = Column(Text, default="", index=True)
    version = Column(Integer, default=1)
    ingested_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("employer_key", "file_path", name="uq_knowledge_file_path"),
    )


class TrackResumeRubric(Base):
    """Per-(employer, track) resume scoring dimension with high/low signals."""

    __tablename__ = "track_resume_rubrics"

    id = Column(Integer, primary_key=True)
    employer_key = Column(Text, nullable=False, index=True)
    track_key = Column(Text, nullable=False, index=True)
    dimension = Column(Text, default="")
    high_signal = Column(Text, default="")
    low_signal = Column(Text, default="")
    examples_json = Column(Text, default="[]")
    source_file = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class TrackInterviewRubric(Base):
    """Per-(employer, track, stage) interview rubric. group/1v1/hr/ai_screen.

    For 群面 (group), scoring_dimensions_json carries the dual-axis spec:
        {"speak_quality": [...], "collaboration": [...]}
    """

    __tablename__ = "track_interview_rubrics"

    id = Column(Integer, primary_key=True)
    employer_key = Column(Text, nullable=False, index=True)
    track_key = Column(Text, nullable=False, index=True)
    interview_stage = Column(Text, default="", index=True)
    scoring_dimensions_json = Column(Text, default="{}")
    rubric_md = Column(Text, default="")
    source_file = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class InterviewerQuote(Base):
    """VERBATIM quotes from real interviewers — paraphrasing forbidden.

    quote_verbatim must be a substring of the source file at ingest time;
    the ingest script drops candidates that fail substring verification.
    """

    __tablename__ = "interviewer_quotes"

    id = Column(Integer, primary_key=True)
    employer_key = Column(Text, nullable=False, index=True)
    track_key = Column(Text, default="", index=True)
    interview_stage = Column(Text, default="", index=True)
    quote_verbatim = Column(Text, nullable=False)
    attribution = Column(Text, default="")
    context_topic = Column(Text, default="")
    source_file = Column(Text, default="")
    source_excerpt = Column(Text, default="")
    quote_hash = Column(Text, default="", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("employer_key", "quote_hash", name="uq_interviewer_quote_hash"),
    )


class TrackExampleBank(Base):
    """good_answer / bad_answer / star_example / group_interview_full_run / ..."""

    __tablename__ = "track_example_bank"

    id = Column(Integer, primary_key=True)
    employer_key = Column(Text, nullable=False, index=True)
    track_key = Column(Text, default="", index=True)
    example_type = Column(Text, default="", index=True)
    title = Column(Text, default="")
    content_md = Column(Text, default="")
    rubric_score_json = Column(Text, default="{}")
    commentary = Column(Text, default="")
    source_file = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class OutputConstraint(Base):
    """Cross-cutting output rules. scope='global' applies to everything;
    'employer' / 'track' narrow it. SensitiveTopicProvider may early-terminate
    based on the highest-priority match."""

    __tablename__ = "output_constraints"

    id = Column(Integer, primary_key=True)
    scope = Column(Text, default="global", index=True)
    employer_key = Column(Text, default="", index=True)
    track_key = Column(Text, default="", index=True)
    rule = Column(Text, nullable=False)
    explanation = Column(Text, default="")
    softening_phrases_json = Column(Text, default="[]")
    forbidden_phrases_json = Column(Text, default="[]")
    priority = Column(Integer, default=50, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SensitiveTopic(Base):
    """8 categories per Tencent sensitive-topics.md. SensitiveTopicProvider
    matches user_question against typical_phrasings_json and, on hit,
    returns response_template + an early-terminate sentinel so other
    providers don't append further context."""

    __tablename__ = "sensitive_topics"

    id = Column(Integer, primary_key=True)
    employer_key = Column(Text, nullable=False, index=True)
    topic_key = Column(Text, nullable=False, index=True)
    display_name = Column(Text, default="")
    typical_phrasings_json = Column(Text, default="[]")
    response_template = Column(Text, default="")
    can_say_json = Column(Text, default="[]")
    cannot_say_json = Column(Text, default="[]")
    severity = Column(Text, default="block", index=True)
    source_file = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("employer_key", "topic_key", name="uq_sensitive_topic"),
    )


# ── 账号系统 (alpha-1 内测,邀请码 gated) ───────────────────────────────────


class InviteCode(Base):
    """邀请码。已用过的 code consumed_at != null。

    token_limit_total / token_limit_daily NULL = 不限。
    """

    __tablename__ = "invite_codes"

    id = Column(Integer, primary_key=True)
    code = Column(Text, nullable=False, unique=True, index=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    consumed_at = Column(DateTime, nullable=True, index=True)
    consumed_by_user_key = Column(Text, nullable=True)  # 不上 FK,跟 users 解耦
    expires_at = Column(DateTime, nullable=True, index=True)
    token_limit_total = Column(Integer, nullable=True)
    token_limit_daily = Column(Integer, nullable=True)


class LlmUsage(Base):
    """一行 = 一次 LLM 调用。给 token quota 用,也方便事后审计。"""

    __tablename__ = "llm_usage"

    id = Column(Integer, primary_key=True)
    user_key = Column(Text, nullable=False, index=True)
    feature = Column(Text, nullable=False)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    usage_date = Column(Text, nullable=False)  # 'YYYY-MM-DD' Asia/Shanghai
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class User(Base):
    """邮箱注册账号。email_verified_at != null 才能正常使用。"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(Text, nullable=False, unique=True, index=True)
    password_hash = Column(Text, nullable=False)
    invite_code_id = Column(Integer, ForeignKey("invite_codes.id"), nullable=True)
    email_verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)


class EmailVerification(Base):
    """6 位数字邮箱验证码,10 分钟有效。一个 user 多条历史记录(防 race)。"""

    __tablename__ = "email_verifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    code = Column(Text, nullable=False)
    purpose = Column(Text, default="register", index=True)  # register | reset_password | ...
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    verified_at = Column(DateTime, nullable=True)
    attempts = Column(Integer, default=0)


class UserSession(Base):
    """登录 session token。30 天有效。前端用 Bearer header 携带。"""

    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(Text, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True)
    ua = Column(Text, nullable=True)
    ip = Column(Text, nullable=True)


class XHSTaxonomyExtract(Base):
    """Taxonomy 字段独立表 (跟 xhs_insights 拆开, 后者存 KB 5-type)。"""
    __tablename__ = "xhs_taxonomy_extracts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Text, nullable=False, index=True)
    url = Column(Text, nullable=False)
    post_time = Column(Text, nullable=True)
    author_uid = Column(Text, nullable=True, index=True)
    relevance_score = Column(Float, nullable=False, default=0.0)
    strategy_signals_json = Column(Text, nullable=False, default="[]")
    industry_signals_json = Column(Text, nullable=False, default="[]")
    institution_signals_json = Column(Text, nullable=False, default="[]")
    discovered_sub_categories_json = Column(Text, nullable=False, default="[]")
    company_role_pairs_json = Column(Text, nullable=False, default="[]")
    dimension_distinctions_json = Column(Text, nullable=False, default="[]")
    extraction_confidence = Column(Float, nullable=False, default=1.0)
    strategy_bucket = Column(Text, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())


class TaxonomyXhsPost(Base):
    """Phase G — XHS 帖 per 27 sub_cat."""
    __tablename__ = "taxonomy_xhs_posts"
    id = Column(Integer, primary_key=True)
    sub_cat = Column(Text, nullable=False, index=True)
    source_url = Column(Text, nullable=False, unique=True)
    company_mentions = Column(Text)        # JSON array
    verbatim_signals = Column(Text)        # JSON array
    raw_content = Column(Text, nullable=False)
    extracted_fields = Column(Text)        # JSON
    relevance_score = Column(Float)
    scraped_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeSubcategory(Base):
    """Phase G — 27 sub_cat 结构化知识库."""
    __tablename__ = "knowledge_subcategories"
    id = Column(Integer, primary_key=True)
    sub_cat = Column(Text, nullable=False, unique=True)
    sub_cat_slug = Column(Text, nullable=False, unique=True)
    strategy_type = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=False)        # 15 字段 JSON
    data_confidence = Column(Text, nullable=False)     # high/medium/low
    data_basis_json = Column(Text, nullable=False)
    hiring_season_json = Column(Text)
    embedding = Column(LargeBinary)                    # DashScope text-embedding-v3
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
