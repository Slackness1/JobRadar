"""A SQLite test engine that behaves like production for multi-threaded code.

Most tests use an in-memory engine with StaticPool, which hands the *same* DBAPI
connection to every session. That is fine for single-threaded request tests, but
this codebase has code paths where a request thread and a background worker touch
the same row concurrently (the per-turn analysis fan-out, the audio analysis
daemons). Sharing one connection makes their transactions interleave, so rows
intermittently read back as missing — failures that cannot happen against the
real WAL database, where every session gets its own connection.

Use this helper in any test that exercises those threads.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base


def make_threadsafe_sessionmaker(prefix: str = "jobradar-test-"):
    """File-backed engine: one connection per session, WAL, busy timeout."""
    tmp_dir = tempfile.mkdtemp(prefix=prefix)
    engine = create_engine(
        f"sqlite:///{Path(tmp_dir) / 'test.db'}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - setup
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
