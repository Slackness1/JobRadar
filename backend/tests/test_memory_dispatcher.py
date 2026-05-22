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


# ─── Plan 1 (2026-05-20): resume-edit ↔ memory sync ──────────────────────────

import json as _json
from app.services.memory.api_helpers import (
    diff_changed_field_paths,
    mark_memory_needs_resync,
)


def _factory_plan1():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_diff_changed_field_paths_detects_edits_and_inserts_and_summary():
    old = {
        "candidate_summary": "aa",
        "internships": [
            {"bullets": ["第一条", "第二条"]},
            {"bullets": ["公司2-b1"]},
        ],
        "projects": [],
        "education": [{"highlights": ["edu-hi-1"]}],
    }
    new = {
        "candidate_summary": "aa  ",  # whitespace-only → not changed
        "internships": [
            {"bullets": ["第一条 修改", "第二条"]},  # b0 changed
            {"bullets": ["公司2-b1", "新增 b2"]},     # b1 added
        ],
        "projects": [],
        "education": [{"highlights": ["edu-hi-1 修订"]}],  # changed
    }
    out = diff_changed_field_paths(old, new)
    assert "internships.0.bullets.0" in out
    assert "internships.1.bullets.1" in out
    assert "education.0.highlights.0" in out
    assert "candidate_summary" not in out  # whitespace ignored
    assert "internships.0.bullets.1" not in out  # unchanged


def test_diff_changed_field_paths_handles_none_and_empty_profiles():
    assert diff_changed_field_paths(None, {}) == []
    assert diff_changed_field_paths({}, None) == []
    assert diff_changed_field_paths(None, None) == []


@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_mark_memory_needs_resync_flags_matching_rows_only():
    db = _factory_plan1()()
    # Row A: linked to bullets.0 → should flip
    rowA = AccountMemory(
        user_key="alice", category="experience", summary="A",
        summary_hash="hA", payload_json="{}",
        linked_field_paths=_json.dumps(["internships.0.bullets.0"]),
    )
    # Row B: linked to bullets.5 → should NOT flip
    rowB = AccountMemory(
        user_key="alice", category="experience", summary="B",
        summary_hash="hB", payload_json="{}",
        linked_field_paths=_json.dumps(["internships.0.bullets.5"]),
    )
    # Row C: orphan (no links) → should NOT flip
    rowC = AccountMemory(
        user_key="alice", category="preference", summary="C",
        summary_hash="hC", payload_json="{}",
        linked_field_paths="[]",
    )
    db.add_all([rowA, rowB, rowC])
    db.commit()

    touched = mark_memory_needs_resync(
        db, user_key="alice",
        changed_field_paths=["internships.0.bullets.0"],
    )
    assert touched == 1
    db.refresh(rowA); db.refresh(rowB); db.refresh(rowC)
    assert rowA.needs_resync is True
    assert rowB.needs_resync is False
    assert rowC.needs_resync is False


@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_mark_memory_needs_resync_reserved_user_keys_are_noop():
    db = _factory_plan1()()
    for key in ("", "__demo__", "__guest__"):
        out = mark_memory_needs_resync(
            db, user_key=key,
            changed_field_paths=["internships.0.bullets.0"],
        )
        assert out == 0


@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_write_memory_persists_linked_field_paths():
    from app.services.memory.dispatcher import write_memory
    db = _factory_plan1()()
    outcome = write_memory(
        db, user_key="alice", category="preference",
        summary="想去上海", payload={"dimension": "city", "value": "上海"},
        source_module="test",
        linked_field_paths=["internships.0.bullets.2"],
    )
    assert outcome.action == "inserted"
    assert outcome.row is not None
    linked = _json.loads(str(outcome.row.linked_field_paths or "[]"))
    assert linked == ["internships.0.bullets.2"]


# ─── Plan ② parser_seed (2026-05-21) ─────────────────────────────────────────

from unittest.mock import patch as _patch_seed
from app.services.resume_copilot.memory.seeding import seed_memory_from_profile


@_patch_seed("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_seed_memory_from_profile_one_row_per_experience():
    """2026-05-21 v2: one archive card per internship / project, not per
    bullet. All the bullets of that experience live in behavioral_hook +
    linked_field_paths.
    """
    db = _factory_plan1()()
    profile = {
        "internships": [
            {"company": "中信证券", "role": "行研助理",
             "bullets": ["跟踪 5 只半导体股票", "撰写 3 篇深度报告"]},
            {"company": "易方达", "role": "研究助理",
             "bullets": ["白酒板块覆盖"]},
        ],
        "projects": [
            {"name": "市场量化", "bullets": ["搭建因子模型"]},
        ],
    }
    out = seed_memory_from_profile(
        db, user_key="seedtest", session_id=999,
        profile=profile, active_track="二级买方·基本面",
    )
    # 2 internships + 1 project = 3 archive cards, not per-bullet 4
    assert out["inserted"] == 3
    rows = db.query(AccountMemory).filter_by(user_key="seedtest").all()
    assert len(rows) == 3
    # First internship: 2 bullets → 2 linked_field_paths
    ints_zhongxin = next(r for r in rows if "中信证券" in r.summary)
    linked = _json.loads(str(ints_zhongxin.linked_field_paths or "[]"))
    assert linked == ["internships.0.bullets.0", "internships.0.bullets.1"]
    # behavioral_hook in payload contains both bullet lines
    payload = _json.loads(str(ints_zhongxin.payload_json))
    assert "跟踪 5 只半导体股票" in payload["behavioral_hook"]
    assert "撰写 3 篇深度报告" in payload["behavioral_hook"]
    for r in rows:
        assert r.category == "experience"
        assert r.source_module == "parser_seed"
        assert r.linked_track == "二级买方·基本面"
        assert r.user_confirmed is False


@_patch_seed("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_seed_memory_from_profile_idempotent_on_reupload():
    db = _factory_plan1()()
    profile = {
        "internships": [
            {"company": "X", "role": "Y", "bullets": ["aa", "bb"]},
        ],
        "projects": [],
    }
    out1 = seed_memory_from_profile(db, user_key="u1", session_id=1, profile=profile)
    assert out1["inserted"] == 1  # one card per internship
    out2 = seed_memory_from_profile(db, user_key="u1", session_id=1, profile=profile)
    assert out2["inserted"] == 0
    assert out2["refreshed"] == 1  # dedup hit on the single card
    rows = db.query(AccountMemory).filter_by(user_key="u1").count()
    assert rows == 1


@_patch_seed("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
def test_seed_memory_from_profile_reserved_keys_noop():
    db = _factory_plan1()()
    profile = {
        "internships": [{"bullets": ["aa"]}],
        "projects": [],
    }
    for k in ("", "__demo__", "__guest__"):
        out = seed_memory_from_profile(db, user_key=k, session_id=1, profile=profile)
        assert out["inserted"] == 0
