"""Unit tests for the unified account_memory dispatcher.

Focus on the contract guarantees:
- Flag-gated
- Demo/guest user_keys blocked
- Validation errors return outcome (don't raise to caller)
- Dedup via (user_key, category, normalized_summary) hash
- Archive respects user_key boundary
- Supersede links rows correctly
"""
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import AccountMemory
from app.services.memory.dispatcher import (
    archive_memory,
    compute_summary_hash,
    supersede_memory,
    write_memory,
)


@pytest.fixture
def db_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ─── Flag gate ───────────────────────────────────────────────────────────────


@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", False)
def test_flag_off_blocks_writes(db_factory):
    db = db_factory()
    try:
        outcome = write_memory(
            db,
            user_key="real_user",
            category="preference",
            summary="想去上海",
            payload={"dimension": "city", "value": "上海"},
            source_module="chat",
        )
        assert outcome.action == "blocked"
        assert outcome.reason == "flag_off"
        assert db.query(AccountMemory).count() == 0
    finally:
        db.close()


# ─── User-key gate ───────────────────────────────────────────────────────────


@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
@pytest.mark.parametrize("key,expected_reason_prefix", [
    ("__demo__", "reserved_user_key:__demo__"),
    ("__guest__", "reserved_user_key:__guest__"),
    ("", "reserved_user_key:<empty>"),
    ("   ", "reserved_user_key:<empty>"),  # whitespace stripped
])
def test_reserved_user_keys_blocked(db_factory, key, expected_reason_prefix):
    db = db_factory()
    try:
        outcome = write_memory(
            db,
            user_key=key,
            category="preference",
            summary="x",
            payload={"dimension": "city", "value": "上海"},
            source_module="chat",
        )
        assert outcome.action == "blocked"
        assert outcome.reason == expected_reason_prefix
        assert db.query(AccountMemory).count() == 0
    finally:
        db.close()


# ─── Payload validation ──────────────────────────────────────────────────────


@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_unknown_category_returns_validation_error(db_factory):
    db = db_factory()
    try:
        outcome = write_memory(
            db,
            user_key="alice",
            category="zodiac_sign",
            summary="Aries",
            payload={},
            source_module="chat",
        )
        assert outcome.action == "validation_error"
        assert "Unknown account_memory category" in outcome.reason
    finally:
        db.close()


@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_invalid_payload_returns_validation_error(db_factory):
    db = db_factory()
    try:
        outcome = write_memory(
            db,
            user_key="alice",
            category="experience",
            summary="bad experience",
            payload={
                "behavioral_hook": "x",
                "star_dimensions": ["not_a_real_dimension"],  # invalid
            },
            source_module="chat",
        )
        assert outcome.action == "validation_error"
        assert "star_dimensions" in outcome.reason or "Unknown" in outcome.reason
    finally:
        db.close()


@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_empty_summary_rejected(db_factory):
    db = db_factory()
    try:
        outcome = write_memory(
            db,
            user_key="alice",
            category="preference",
            summary="   ",
            payload={"dimension": "city", "value": "上海"},
            source_module="chat",
        )
        assert outcome.action == "validation_error"
        assert outcome.reason == "empty_summary"
    finally:
        db.close()


# ─── Insert + dedup ──────────────────────────────────────────────────────────


@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_insert_creates_row(db_factory):
    db = db_factory()
    try:
        outcome = write_memory(
            db,
            user_key="alice",
            category="preference",
            summary="想去上海",
            payload={"dimension": "city", "value": "上海"},
            source_module="chat",
            confidence=0.95,
        )
        assert outcome.action == "inserted"
        assert outcome.row is not None
        assert outcome.row.user_confirmed is True   # 0.95 >= 0.85 threshold

        rows = db.query(AccountMemory).all()
        assert len(rows) == 1
        assert rows[0].category == "preference"
        assert "上海" in rows[0].payload_json
    finally:
        db.close()


@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_dedup_refreshes_existing(db_factory):
    db = db_factory()
    try:
        first = write_memory(
            db,
            user_key="alice",
            category="preference",
            summary="想去上海",
            payload={"dimension": "city", "value": "上海"},
            source_module="chat",
        )
        assert first.action == "inserted"

        second = write_memory(
            db,
            user_key="alice",
            category="preference",
            summary="想去上海",   # same → dedup
            payload={"dimension": "city", "value": "上海"},
            source_module="chat",
        )
        assert second.action == "refreshed"
        assert db.query(AccountMemory).count() == 1
    finally:
        db.close()


@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_dedup_normalizes_whitespace_and_case(db_factory):
    db = db_factory()
    try:
        write_memory(
            db, user_key="alice", category="skill_claim",
            summary="Python  pandas", payload={"skill_name": "Python"},
            source_module="chat",
        )
        out = write_memory(
            db, user_key="alice", category="skill_claim",
            summary="python pandas",   # different case + spacing
            payload={"skill_name": "Python"}, source_module="chat",
        )
        assert out.action == "refreshed"
        assert db.query(AccountMemory).count() == 1
    finally:
        db.close()


@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_different_categories_no_collision(db_factory):
    """Same summary under different category should be different rows."""
    db = db_factory()
    try:
        a = write_memory(
            db, user_key="alice", category="skill_claim",
            summary="Python", payload={"skill_name": "Python"},
            source_module="chat",
        )
        b = write_memory(
            db, user_key="alice", category="identity_fact",
            summary="Python",
            payload={"kind": "major", "value": "Python 编程"},
            source_module="chat",
        )
        assert a.action == "inserted"
        assert b.action == "inserted"
        assert db.query(AccountMemory).count() == 2
    finally:
        db.close()


@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_different_users_no_collision(db_factory):
    db = db_factory()
    try:
        write_memory(
            db, user_key="alice", category="preference",
            summary="想去上海",
            payload={"dimension": "city", "value": "上海"},
            source_module="chat",
        )
        write_memory(
            db, user_key="bob", category="preference",
            summary="想去上海",
            payload={"dimension": "city", "value": "上海"},
            source_module="chat",
        )
        assert db.query(AccountMemory).count() == 2
    finally:
        db.close()


@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_low_confidence_stays_unconfirmed(db_factory):
    db = db_factory()
    try:
        out = write_memory(
            db, user_key="alice", category="preference",
            summary="想去上海",
            payload={"dimension": "city", "value": "上海"},
            source_module="chat",
            confidence=0.5,
        )
        assert out.action == "inserted"
        assert out.row.user_confirmed is False
    finally:
        db.close()


@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_archived_row_not_unarchived_by_refresh(db_factory):
    """Once user archives a fact, re-extraction must respect that. We don't
    silently un-archive — caller needs to take explicit action."""
    db = db_factory()
    try:
        out = write_memory(
            db, user_key="alice", category="preference",
            summary="想去上海",
            payload={"dimension": "city", "value": "上海"},
            source_module="chat",
        )
        archive_memory(db, memory_id=out.row.id, user_key="alice")

        out2 = write_memory(
            db, user_key="alice", category="preference",
            summary="想去上海",
            payload={"dimension": "city", "value": "上海"},
            source_module="chat",
        )
        # Hit dedup path, didn't insert again — but row stays archived
        assert out2.action == "refreshed"
        db.refresh(out2.row)
        assert bool(out2.row.is_archived) is True
    finally:
        db.close()


# ─── Archive ─────────────────────────────────────────────────────────────────


@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_archive_sets_flag(db_factory):
    db = db_factory()
    try:
        out = write_memory(
            db, user_key="alice", category="preference",
            summary="x", payload={"dimension": "city", "value": "上海"},
            source_module="chat",
        )
        assert archive_memory(db, memory_id=out.row.id, user_key="alice") is True
        db.refresh(out.row)
        assert bool(out.row.is_archived) is True
    finally:
        db.close()


@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_archive_rejects_wrong_user(db_factory):
    db = db_factory()
    try:
        out = write_memory(
            db, user_key="alice", category="preference",
            summary="x", payload={"dimension": "city", "value": "上海"},
            source_module="chat",
        )
        # bob tries to archive alice's row
        assert archive_memory(db, memory_id=out.row.id, user_key="bob") is False
        db.refresh(out.row)
        assert bool(out.row.is_archived) is False
    finally:
        db.close()


def test_archive_nonexistent_returns_false(db_factory):
    db = db_factory()
    try:
        assert archive_memory(db, memory_id=99999, user_key="alice") is False
    finally:
        db.close()


# ─── Supersede ───────────────────────────────────────────────────────────────


@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_supersede_links_old_to_new(db_factory):
    """Classic case: user changes preference. Old row stays for audit, gets
    superseded_by_id pointing at the new row."""
    db = db_factory()
    try:
        old = write_memory(
            db, user_key="alice", category="preference",
            summary="想做研发",
            payload={"dimension": "role", "value": "研发"},
            source_module="chat",
        )
        new = write_memory(
            db, user_key="alice", category="preference",
            summary="想做产品",
            payload={"dimension": "role", "value": "产品"},
            source_module="chat",
        )
        assert supersede_memory(db, old_id=old.row.id, new_outcome=new) is True

        db.refresh(old.row)
        assert old.row.superseded_by_id == new.row.id
    finally:
        db.close()


@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_supersede_refused_when_new_is_refresh(db_factory):
    db = db_factory()
    try:
        old = write_memory(
            db, user_key="alice", category="preference",
            summary="想去上海",
            payload={"dimension": "city", "value": "上海"},
            source_module="chat",
        )
        new = write_memory(   # same summary → refreshed, not inserted
            db, user_key="alice", category="preference",
            summary="想去上海",
            payload={"dimension": "city", "value": "上海"},
            source_module="chat",
        )
        assert new.action == "refreshed"
        # Nothing to supersede TO — function refuses, leaves DB intact
        assert supersede_memory(db, old_id=old.row.id, new_outcome=new) is False
        db.refresh(old.row)
        assert old.row.superseded_by_id is None
    finally:
        db.close()


# ─── compute_summary_hash purity ────────────────────────────────────────────


def test_hash_stable_across_calls():
    a = compute_summary_hash("alice", "preference", "想去  上海")
    b = compute_summary_hash("alice", "preference", "想去 上海")  # different spacing
    c = compute_summary_hash("alice", "preference", "想去上海")     # no spacing
    # Whitespace collapsed but not stripped from inside characters
    assert a == b   # multi-space → single-space match
    # "想去 上海" (single space) vs "想去上海" (no space) — single-space wins after collapse
    # so they should be different
    assert b != c


def test_hash_different_users_different_hashes():
    a = compute_summary_hash("alice", "preference", "x")
    b = compute_summary_hash("bob", "preference", "x")
    assert a != b


def test_hash_different_categories_different_hashes():
    a = compute_summary_hash("alice", "preference", "x")
    b = compute_summary_hash("alice", "skill_claim", "x")
    assert a != b
