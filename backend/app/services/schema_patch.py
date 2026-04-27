from sqlalchemy import text
from sqlalchemy.engine import Engine


def ensure_compatible_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(jobs)")).fetchall()
        columns = {row[1] for row in rows}

        if "job_stage" not in columns:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN job_stage TEXT DEFAULT 'campus'"))

        if "source_config_id" not in columns:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN source_config_id TEXT DEFAULT ''"))

        if "application_status" not in columns:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN application_status TEXT DEFAULT '待申请'"))

        queue_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='company_recrawl_queue'")
        ).fetchone()

        if not queue_exists:
            conn.execute(text(
                """
                CREATE TABLE company_recrawl_queue (
                    id INTEGER PRIMARY KEY,
                    company TEXT NOT NULL,
                    department TEXT DEFAULT '',
                    career_url TEXT NOT NULL,
                    source_domain TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    attempt_count INTEGER DEFAULT 0,
                    fetched_count INTEGER DEFAULT 0,
                    new_count INTEGER DEFAULT 0,
                    last_error TEXT DEFAULT '',
                    failure_reason TEXT DEFAULT '',
                    failure_reasons_json TEXT DEFAULT '[]',
                    last_detection_json TEXT DEFAULT '{}',
                    last_evidence_json TEXT DEFAULT '{}',
                    completeness_score FLOAT DEFAULT 0,
                    zero_result_type TEXT DEFAULT '',
                    fallback_action TEXT DEFAULT '',
                    priority INTEGER DEFAULT 0,
                    created_at DATETIME,
                    updated_at DATETIME,
                    finished_at DATETIME
                )
                """
            ))
        else:
            queue_rows = conn.execute(text("PRAGMA table_info(company_recrawl_queue)")).fetchall()
            queue_columns = {row[1] for row in queue_rows}

            if "source_domain" not in queue_columns:
                conn.execute(text("ALTER TABLE company_recrawl_queue ADD COLUMN source_domain TEXT DEFAULT ''"))
            if "fetched_count" not in queue_columns:
                conn.execute(text("ALTER TABLE company_recrawl_queue ADD COLUMN fetched_count INTEGER DEFAULT 0"))
            if "new_count" not in queue_columns:
                conn.execute(text("ALTER TABLE company_recrawl_queue ADD COLUMN new_count INTEGER DEFAULT 0"))

        crawl_log_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='crawl_logs'")
        ).fetchone()

        if crawl_log_exists:
            crawl_rows = conn.execute(text("PRAGMA table_info(crawl_logs)")).fetchall()
            crawl_columns = {row[1] for row in crawl_rows}

            crawl_additions = {
                "target_url": "ALTER TABLE crawl_logs ADD COLUMN target_url TEXT DEFAULT ''",
                "final_url": "ALTER TABLE crawl_logs ADD COLUMN final_url TEXT DEFAULT ''",
                "page_title": "ALTER TABLE crawl_logs ADD COLUMN page_title TEXT DEFAULT ''",
                "ats_family": "ALTER TABLE crawl_logs ADD COLUMN ats_family TEXT DEFAULT ''",
                "framework_family": "ALTER TABLE crawl_logs ADD COLUMN framework_family TEXT DEFAULT ''",
                "detection_flags_json": "ALTER TABLE crawl_logs ADD COLUMN detection_flags_json TEXT DEFAULT '{}'",
                "evidence_json": "ALTER TABLE crawl_logs ADD COLUMN evidence_json TEXT DEFAULT '{}'",
                "failure_reason": "ALTER TABLE crawl_logs ADD COLUMN failure_reason TEXT DEFAULT ''",
                "failure_reasons_json": "ALTER TABLE crawl_logs ADD COLUMN failure_reasons_json TEXT DEFAULT '[]'",
                "completeness_score": "ALTER TABLE crawl_logs ADD COLUMN completeness_score FLOAT DEFAULT 0",
                "zero_result_type": "ALTER TABLE crawl_logs ADD COLUMN zero_result_type TEXT DEFAULT ''",
                "fallback_action": "ALTER TABLE crawl_logs ADD COLUMN fallback_action TEXT DEFAULT ''",
                "detail_link_count": "ALTER TABLE crawl_logs ADD COLUMN detail_link_count INTEGER DEFAULT 0",
                "job_signal_count": "ALTER TABLE crawl_logs ADD COLUMN job_signal_count INTEGER DEFAULT 0",
                "page_claimed_count": "ALTER TABLE crawl_logs ADD COLUMN page_claimed_count INTEGER DEFAULT 0",
            }
            for column_name, ddl in crawl_additions.items():
                if column_name not in crawl_columns:
                    conn.execute(text(ddl))

        if not queue_exists:
            pass
        else:
            queue_rows = conn.execute(text("PRAGMA table_info(company_recrawl_queue)")).fetchall()
            queue_columns = {row[1] for row in queue_rows}

            if "source_domain" not in queue_columns:
                conn.execute(text("ALTER TABLE company_recrawl_queue ADD COLUMN source_domain TEXT DEFAULT ''"))
            if "fetched_count" not in queue_columns:
                conn.execute(text("ALTER TABLE company_recrawl_queue ADD COLUMN fetched_count INTEGER DEFAULT 0"))
            if "new_count" not in queue_columns:
                conn.execute(text("ALTER TABLE company_recrawl_queue ADD COLUMN new_count INTEGER DEFAULT 0"))
            if "failure_reason" not in queue_columns:
                conn.execute(text("ALTER TABLE company_recrawl_queue ADD COLUMN failure_reason TEXT DEFAULT ''"))
            if "failure_reasons_json" not in queue_columns:
                conn.execute(text("ALTER TABLE company_recrawl_queue ADD COLUMN failure_reasons_json TEXT DEFAULT '[]'"))
            if "last_detection_json" not in queue_columns:
                conn.execute(text("ALTER TABLE company_recrawl_queue ADD COLUMN last_detection_json TEXT DEFAULT '{}'"))
            if "last_evidence_json" not in queue_columns:
                conn.execute(text("ALTER TABLE company_recrawl_queue ADD COLUMN last_evidence_json TEXT DEFAULT '{}'"))
            if "completeness_score" not in queue_columns:
                conn.execute(text("ALTER TABLE company_recrawl_queue ADD COLUMN completeness_score FLOAT DEFAULT 0"))
            if "zero_result_type" not in queue_columns:
                conn.execute(text("ALTER TABLE company_recrawl_queue ADD COLUMN zero_result_type TEXT DEFAULT ''"))
            if "fallback_action" not in queue_columns:
                conn.execute(text("ALTER TABLE company_recrawl_queue ADD COLUMN fallback_action TEXT DEFAULT ''"))
            if "priority" not in queue_columns:
                conn.execute(text("ALTER TABLE company_recrawl_queue ADD COLUMN priority INTEGER DEFAULT 0"))

        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_company_recrawl_queue_company ON company_recrawl_queue (company)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_company_recrawl_queue_status ON company_recrawl_queue (status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_company_recrawl_queue_priority ON company_recrawl_queue (priority)"))

        resume_session_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='resume_copilot_sessions'")
        ).fetchone()
        if resume_session_exists:
            resume_rows = conn.execute(text("PRAGMA table_info(resume_copilot_sessions)")).fetchall()
            resume_columns = {row[1] for row in resume_rows}

            resume_session_additions = {
                "file_name": "ALTER TABLE resume_copilot_sessions ADD COLUMN file_name TEXT DEFAULT ''",
                "extracted_text": "ALTER TABLE resume_copilot_sessions ADD COLUMN extracted_text TEXT DEFAULT ''",
                "feedback_status": "ALTER TABLE resume_copilot_sessions ADD COLUMN feedback_status TEXT DEFAULT 'pending'",
                "finished_at": "ALTER TABLE resume_copilot_sessions ADD COLUMN finished_at DATETIME",
                "name": "ALTER TABLE resume_copilot_sessions ADD COLUMN name TEXT DEFAULT ''",
                "user_key": "ALTER TABLE resume_copilot_sessions ADD COLUMN user_key TEXT DEFAULT ''",
                "is_guest": "ALTER TABLE resume_copilot_sessions ADD COLUMN is_guest INTEGER DEFAULT 0",
            }
            for column_name, ddl in resume_session_additions.items():
                if column_name not in resume_columns:
                    conn.execute(text(ddl))

            refreshed_rows = conn.execute(text("PRAGMA table_info(resume_copilot_sessions)")).fetchall()
            refreshed_columns = {row[1] for row in refreshed_rows}
            if {"filename", "file_name"}.issubset(refreshed_columns):
                conn.execute(
                    text(
                        """
                        UPDATE resume_copilot_sessions
                        SET file_name = filename
                        WHERE COALESCE(file_name, '') = '' AND COALESCE(filename, '') != ''
                        """
                    )
                )
            if {"resume_text", "extracted_text"}.issubset(refreshed_columns):
                conn.execute(
                    text(
                        """
                        UPDATE resume_copilot_sessions
                        SET extracted_text = resume_text
                        WHERE COALESCE(extracted_text, '') = '' AND COALESCE(resume_text, '') != ''
                        """
                    )
                )

        recommendation_run_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='resume_recommendation_runs'")
        ).fetchone()
        if recommendation_run_exists:
            recommendation_rows = conn.execute(text("PRAGMA table_info(resume_recommendation_runs)")).fetchall()
            recommendation_columns = {row[1] for row in recommendation_rows}

            recommendation_additions = {
                "error_message": "ALTER TABLE resume_recommendation_runs ADD COLUMN error_message TEXT DEFAULT ''",
                "used_ai": "ALTER TABLE resume_recommendation_runs ADD COLUMN used_ai INTEGER DEFAULT 0",
                "fallback_reason": "ALTER TABLE resume_recommendation_runs ADD COLUMN fallback_reason TEXT DEFAULT ''",
                "agent_trace_json": "ALTER TABLE resume_recommendation_runs ADD COLUMN agent_trace_json TEXT DEFAULT '[]'",
                "recommendations_json": "ALTER TABLE resume_recommendation_runs ADD COLUMN recommendations_json TEXT DEFAULT '[]'",
            }
            for column_name, ddl in recommendation_additions.items():
                if column_name not in recommendation_columns:
                    conn.execute(text(ddl))

        direction_analysis_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='resume_direction_analysis_runs'")
        ).fetchone()
        if not direction_analysis_exists:
            conn.execute(text(
                """
                CREATE TABLE resume_direction_analysis_runs (
                    id INTEGER PRIMARY KEY,
                    session_id INTEGER NOT NULL UNIQUE REFERENCES resume_copilot_sessions(id) ON DELETE CASCADE,
                    status TEXT DEFAULT 'pending',
                    error_message TEXT DEFAULT '',
                    directions_json TEXT DEFAULT '[]',
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            ))

        messages_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='resume_copilot_messages'")
        ).fetchone()
        if not messages_exists:
            conn.execute(text(
                """
                CREATE TABLE resume_copilot_messages (
                    id INTEGER PRIMARY KEY,
                    session_id INTEGER NOT NULL REFERENCES resume_copilot_sessions(id) ON DELETE CASCADE,
                    role TEXT DEFAULT 'user',
                    content TEXT DEFAULT '',
                    rewrite_options_json TEXT,
                    applied_option_id TEXT,
                    created_at DATETIME
                )
                """
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_resume_copilot_messages_session_id ON resume_copilot_messages (session_id)"
            ))

        interview_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='interview_reports'")
        ).fetchone()
        if not interview_exists:
            conn.execute(text(
                """
                CREATE TABLE interview_reports (
                    id INTEGER PRIMARY KEY,
                    user_key TEXT NOT NULL,
                    target_job TEXT NOT NULL,
                    transcript_json TEXT DEFAULT '[]',
                    report_json TEXT DEFAULT '{}',
                    duration_seconds INTEGER DEFAULT 0,
                    is_guest INTEGER DEFAULT 0,
                    created_at DATETIME
                )
                """
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_interview_reports_user_key ON interview_reports (user_key)"
            ))
        else:
            interview_rows = conn.execute(text("PRAGMA table_info(interview_reports)")).fetchall()
            interview_columns = {row[1] for row in interview_rows}
            if "is_guest" not in interview_columns:
                conn.execute(text("ALTER TABLE interview_reports ADD COLUMN is_guest INTEGER DEFAULT 0"))

        kw_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='interview_intel_keywords'")
        ).fetchone()
        if not kw_exists:
            conn.execute(text(
                """
                CREATE TABLE interview_intel_keywords (
                    keyword TEXT PRIMARY KEY,
                    summary_md TEXT DEFAULT '',
                    source_count INTEGER DEFAULT 0,
                    generated_at DATETIME,
                    last_error TEXT DEFAULT ''
                )
                """
            ))

        post_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='interview_intel_posts'")
        ).fetchone()
        if not post_exists:
            conn.execute(text(
                """
                CREATE TABLE interview_intel_posts (
                    pid TEXT NOT NULL,
                    keyword TEXT NOT NULL,
                    title TEXT DEFAULT '',
                    company TEXT DEFAULT '',
                    interview_date TEXT DEFAULT '',
                    position TEXT DEFAULT '',
                    questions_text TEXT DEFAULT '',
                    fetched_at DATETIME,
                    parse_status TEXT DEFAULT 'ok',
                    quality_score INTEGER DEFAULT 2,
                    PRIMARY KEY (pid, keyword)
                )
                """
            ))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_iip_keyword ON interview_intel_posts(keyword)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_iip_fetched ON interview_intel_posts(fetched_at)"))
        else:
            post_rows = conn.execute(text("PRAGMA table_info(interview_intel_posts)")).fetchall()
            post_columns = {row[1] for row in post_rows}
            if "quality_score" not in post_columns:
                conn.execute(text("ALTER TABLE interview_intel_posts ADD COLUMN quality_score INTEGER DEFAULT 2"))

        # interview_turns — per-turn audit + scoring storage
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS interview_turns (
                id INTEGER PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_key TEXT DEFAULT '',
                turn_index INTEGER NOT NULL,
                target_job TEXT DEFAULT '',
                question TEXT DEFAULT '',
                user_answer TEXT DEFAULT '',
                asr_transcript TEXT DEFAULT '',
                voice_metrics TEXT,
                score_json TEXT,
                reference_answer TEXT DEFAULT '',
                question_source TEXT DEFAULT 'skeleton',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        ))
        # Drop legacy manual indexes; ensure ORM-named indexes exist (idempotent)
        conn.execute(text("DROP INDEX IF EXISTS idx_interview_turns_session"))
        conn.execute(text("DROP INDEX IF EXISTS idx_interview_turns_user"))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_interview_turns_session_id ON interview_turns(session_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_interview_turns_user_key ON interview_turns(user_key)"
        ))

        # interview_reports new columns — idempotent ALTER
        existing_report_cols = {
            row[1] for row in conn.execute(text("PRAGMA table_info(interview_reports)")).fetchall()
        }
        if "weakness_profile_json" not in existing_report_cols:
            conn.execute(text("ALTER TABLE interview_reports ADD COLUMN weakness_profile_json TEXT"))
        if "weekly_plan_md" not in existing_report_cols:
            conn.execute(text("ALTER TABLE interview_reports ADD COLUMN weekly_plan_md TEXT DEFAULT ''"))
        if "turn_count" not in existing_report_cols:
            conn.execute(text("ALTER TABLE interview_reports ADD COLUMN turn_count INTEGER DEFAULT 0"))

        ccl_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='company_crawl_logs'")
        ).fetchone()
        if not ccl_exists:
            conn.execute(text(
                """
                CREATE TABLE company_crawl_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    company TEXT NOT NULL,
                    started_at DATETIME NOT NULL,
                    finished_at DATETIME,
                    status TEXT NOT NULL,
                    fetched_count INTEGER NOT NULL DEFAULT 0,
                    new_count INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT NOT NULL DEFAULT '',
                    parent_log_id INTEGER,
                    duration_ms INTEGER NOT NULL DEFAULT 0
                )
                """
            ))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ccl_company_started ON company_crawl_logs(company, started_at DESC)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ccl_source_started  ON company_crawl_logs(source, started_at DESC)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ccl_parent          ON company_crawl_logs(parent_log_id)"))

        # Crawler LLM enrichment columns (LLM-1 foundation)
        ccl_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(company_crawl_logs)")).fetchall()}
        if "suggested_fix" not in ccl_cols:
            conn.execute(text("ALTER TABLE company_crawl_logs ADD COLUMN suggested_fix TEXT NOT NULL DEFAULT ''"))

        jobs_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(jobs)")).fetchall()}
        if "track_predicted" not in jobs_cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN track_predicted TEXT NOT NULL DEFAULT ''"))
        if "quality_label" not in jobs_cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN quality_label TEXT NOT NULL DEFAULT ''"))
