from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import JobUserState
from app.services.resume_copilot import job_state as js


def _mk_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_unique_user_job():
    db = _mk_session()
    db.add(JobUserState(user_key="u_5", job_id="j1", state="seen"))
    db.commit()
    db.add(JobUserState(user_key="u_5", job_id="j1", state="saved"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_mark_seen_idempotent_and_preserves_explicit():
    db = _mk_session()
    assert js.mark_seen(db, "u_5", ["a", "b"]) == 2
    assert js.mark_seen(db, "u_5", ["a", "c"]) == 1
    js.set_explicit_state(db, "u_5", "a", js.STATE_SAVED)
    js.mark_seen(db, "u_5", ["a"])
    assert js.states_map(db, "u_5")["a"] == "saved"


def test_set_explicit_mutual_exclusive_and_clear():
    db = _mk_session()
    js.set_explicit_state(db, "u_5", "a", js.STATE_SAVED)
    js.set_explicit_state(db, "u_5", "a", js.STATE_APPLIED)
    m = js.states_map(db, "u_5")
    assert m["a"] == "applied"
    js.clear_explicit_state(db, "u_5", "a")
    assert js.states_map(db, "u_5")["a"] == "seen"


def test_exclusion_set():
    db = _mk_session()
    js.mark_seen(db, "u_5", ["a", "b"])
    js.set_explicit_state(db, "u_5", "c", js.STATE_DISMISSED)
    assert js.seen_or_dismissed_ids(db, "u_5") == {"a", "b", "c"}


def test_set_explicit_rejects_bad_state():
    db = _mk_session()
    with pytest.raises(ValueError):
        js.set_explicit_state(db, "u_5", "a", "seen")
