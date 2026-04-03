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
