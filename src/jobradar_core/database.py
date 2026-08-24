from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from jobradar_core.models import MemoryRecord, RunEvent, RunSummary, utc_now_iso

SCHEMA_VERSION = 1


class LocalDatabase:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _migrate(self) -> None:
        with self.transaction() as connection:
            current = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if current > SCHEMA_VERSION:
                raise RuntimeError(
                    f"database schema {current} is newer than supported {SCHEMA_VERSION}"
                )
            if current < 1:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS jobs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id TEXT NOT NULL UNIQUE,
                        source TEXT NOT NULL,
                        company TEXT NOT NULL DEFAULT '',
                        title TEXT NOT NULL DEFAULT '',
                        location TEXT NOT NULL DEFAULT '',
                        track TEXT NOT NULL DEFAULT '',
                        job_type TEXT NOT NULL DEFAULT '',
                        description TEXT NOT NULL DEFAULT '',
                        requirements TEXT NOT NULL DEFAULT '',
                        url TEXT NOT NULL DEFAULT '',
                        publish_date TEXT NOT NULL DEFAULT '',
                        deadline TEXT NOT NULL DEFAULT '',
                        crawled_at TEXT NOT NULL DEFAULT '',
                        quality_label TEXT NOT NULL DEFAULT '',
                        link_status TEXT NOT NULL DEFAULT '',
                        search_text TEXT NOT NULL DEFAULT '',
                        updated_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
                    CREATE INDEX IF NOT EXISTS idx_jobs_location ON jobs(location);
                    CREATE INDEX IF NOT EXISTS idx_jobs_track ON jobs(track);
                    CREATE INDEX IF NOT EXISTS idx_jobs_publish_date ON jobs(publish_date);

                    CREATE VIRTUAL TABLE IF NOT EXISTS jobs_fts USING fts5(
                        title, company, description, requirements, track,
                        content='jobs', content_rowid='id', tokenize='unicode61'
                    );

                    CREATE TRIGGER IF NOT EXISTS jobs_ai AFTER INSERT ON jobs BEGIN
                        INSERT INTO jobs_fts(
                            rowid, title, company, description, requirements, track
                        )
                        VALUES (new.id, new.title, new.company, new.description,
                                new.requirements, new.track);
                    END;
                    CREATE TRIGGER IF NOT EXISTS jobs_ad AFTER DELETE ON jobs BEGIN
                        INSERT INTO jobs_fts(jobs_fts, rowid, title, company, description,
                                             requirements, track)
                        VALUES('delete', old.id, old.title, old.company, old.description,
                               old.requirements, old.track);
                    END;
                    CREATE TRIGGER IF NOT EXISTS jobs_au AFTER UPDATE ON jobs BEGIN
                        INSERT INTO jobs_fts(jobs_fts, rowid, title, company, description,
                                             requirements, track)
                        VALUES('delete', old.id, old.title, old.company, old.description,
                               old.requirements, old.track);
                        INSERT INTO jobs_fts(
                            rowid, title, company, description, requirements, track
                        )
                        VALUES (new.id, new.title, new.company, new.description,
                                new.requirements, new.track);
                    END;

                    CREATE TABLE IF NOT EXISTS job_user_state (
                        job_id TEXT PRIMARY KEY,
                        favorite INTEGER NOT NULL DEFAULT 0,
                        excluded INTEGER NOT NULL DEFAULT 0,
                        exclude_reason TEXT NOT NULL DEFAULT '',
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS resumes (
                        resume_id TEXT PRIMARY KEY,
                        original_name TEXT NOT NULL,
                        source_path TEXT NOT NULL,
                        source_hash TEXT NOT NULL UNIQUE,
                        text TEXT NOT NULL,
                        blocks_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS resume_versions (
                        version_id TEXT PRIMARY KEY,
                        resume_id TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        path TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        patches_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(resume_id) REFERENCES resumes(resume_id)
                    );

                    CREATE TABLE IF NOT EXISTS memory_records (
                        memory_id TEXT PRIMARY KEY,
                        scope TEXT NOT NULL,
                        level TEXT NOT NULL,
                        category TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        source_ref TEXT NOT NULL DEFAULT '',
                        user_confirmed INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL DEFAULT 'staged',
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_memory_scope_level
                        ON memory_records(scope, level, status);

                    CREATE TABLE IF NOT EXISTS runs (
                        run_id TEXT PRIMARY KEY,
                        workflow TEXT NOT NULL,
                        state TEXT NOT NULL,
                        status TEXT NOT NULL,
                        revision INTEGER NOT NULL DEFAULT 1,
                        snapshot_hash TEXT NOT NULL DEFAULT '',
                        manifest_json TEXT NOT NULL DEFAULT '{}',
                        output_json TEXT NOT NULL DEFAULT '{}',
                        error TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS run_events (
                        event_id TEXT PRIMARY KEY,
                        run_id TEXT NOT NULL,
                        step TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        occurred_at TEXT NOT NULL,
                        duration_ms INTEGER,
                        quality TEXT NOT NULL DEFAULT 'valid',
                        summary TEXT NOT NULL DEFAULT '',
                        error_code TEXT NOT NULL DEFAULT '',
                        FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                    );
                    CREATE INDEX IF NOT EXISTS idx_run_events_run_time
                        ON run_events(run_id, occurred_at);
                    """
                )
                connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    def create_run(self, workflow: str, snapshot_hash: str = "") -> str:
        run_id = uuid.uuid4().hex
        now = utc_now_iso()
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO runs
                   (run_id, workflow, state, status, snapshot_hash, created_at, updated_at)
                   VALUES (?, ?, 'intake', 'running', ?, ?, ?)""",
                (run_id, workflow, snapshot_hash, now, now),
            )
        return run_id

    def update_run(
        self,
        run_id: str,
        *,
        state: str | None = None,
        status: str | None = None,
        snapshot_hash: str | None = None,
        manifest: dict | None = None,
        output: dict | None = None,
        error: str | None = None,
    ) -> None:
        values: dict[str, object] = {"updated_at": utc_now_iso()}
        if state is not None:
            values["state"] = state
        if status is not None:
            values["status"] = status
        if snapshot_hash is not None:
            values["snapshot_hash"] = snapshot_hash
        if manifest is not None:
            values["manifest_json"] = json.dumps(manifest, ensure_ascii=False)
        if output is not None:
            values["output_json"] = json.dumps(output, ensure_ascii=False)
        if error is not None:
            values["error"] = error
        assignments = ", ".join(f"{key}=?" for key in values)
        with self.transaction() as connection:
            connection.execute(
                f"UPDATE runs SET {assignments} WHERE run_id=?",  # noqa: S608
                (*values.values(), run_id),
            )

    def add_event(
        self,
        run_id: str,
        step: str,
        event_type: str,
        *,
        summary: str = "",
        duration_ms: int | None = None,
        quality: str = "valid",
        error_code: str = "",
    ) -> str:
        event = RunEvent(
            event_id=uuid.uuid4().hex,
            run_id=run_id,
            step=step,
            event_type=event_type,
            summary=summary,
            duration_ms=duration_ms,
            quality=quality,
            error_code=error_code,
        )
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO run_events
                   (event_id, run_id, step, event_type, occurred_at, duration_ms,
                    quality, summary, error_code)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.event_id,
                    event.run_id,
                    event.step,
                    event.event_type,
                    event.occurred_at,
                    event.duration_ms,
                    event.quality,
                    event.summary,
                    event.error_code,
                ),
            )
        return event.event_id

    def list_runs(self, limit: int = 100) -> list[RunSummary]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT run_id, workflow, state, status, revision, snapshot_hash,
                          created_at, updated_at, error
                   FROM runs ORDER BY created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [RunSummary.model_validate(dict(row)) for row in rows]

    def add_memory(self, record: MemoryRecord) -> None:
        with self.transaction() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO memory_records
                   (memory_id, scope, level, category, summary, payload_json,
                    source_ref, user_confirmed, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.memory_id,
                    record.scope,
                    record.level,
                    record.category,
                    record.summary,
                    json.dumps(record.payload, ensure_ascii=False),
                    record.source_ref,
                    int(record.user_confirmed),
                    record.status,
                    utc_now_iso(),
                ),
            )

    def recall_memory(
        self,
        *,
        scopes: tuple[str, ...] = ("global", "resume"),
        max_level: str = "L3",
        query: str = "",
        limit: int = 30,
    ) -> list[MemoryRecord]:
        level_order = {"L0": 0, "L1": 1, "L2": 2, "L3": 3}
        allowed = [level for level, order in level_order.items() if order <= level_order[max_level]]
        scope_marks = ",".join("?" for _ in scopes)
        level_marks = ",".join("?" for _ in allowed)
        params: list[object] = [*scopes, *allowed]
        sql = f"""SELECT * FROM memory_records
                  WHERE scope IN ({scope_marks}) AND level IN ({level_marks})
                    AND status='active'"""
        if query.strip():
            sql += " AND (summary LIKE ? OR payload_json LIKE ?)"
            term = f"%{query.strip()}%"
            params.extend([term, term])
        sql += " ORDER BY level ASC, created_at DESC LIMIT ?"
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [
            MemoryRecord(
                memory_id=row["memory_id"],
                scope=row["scope"],
                level=row["level"],
                category=row["category"],
                summary=row["summary"],
                payload=json.loads(row["payload_json"]),
                source_ref=row["source_ref"],
                user_confirmed=bool(row["user_confirmed"]),
                status=row["status"],
            )
            for row in rows
        ]
