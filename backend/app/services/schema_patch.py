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

        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_company_recrawl_queue_company ON company_recrawl_queue (company)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_company_recrawl_queue_status ON company_recrawl_queue (status)"))
