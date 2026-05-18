"""Unit tests for ExperienceRecaller.

Uses ``asyncio.run`` rather than pytest-asyncio (prod venv lacks the plugin).

Covers all five paths a recall can take + the demo/guest gate. Tests use
a real in-memory SQLite + seeded AccountMemory rows — the recaller is
SQL-heavy and Python-light, so mocking SQLAlchemy would obscure the
contract more than it would simplify.
"""
import asyncio
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import AccountMemory
from app.services.interview.subagents.recaller import (
    ExperienceRecaller,
    RecallerInput,
)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def db_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _seed_experience(
    factory,
    *,
    user_key="alice",
    summary="大三组织 50 人产品发布会",
    dimensions=("leadership", "cross_functional"),
    behavioral_hook="S=大三|T=跨5部门|A=主导|R=出席率90%",
    raw_excerpt="我大三组织过 50 人发布会",
    confidence=0.95,
    captured_offset_days=0,
    use_count=0,
    is_archived=False,
    superseded_by_id=None,
    category="experience",
):
    db = factory()
    payload = {
        "behavioral_hook": behavioral_hook,
        "star_dimensions": list(dimensions),
        "quantified": {},
        "evidence_ids": [],
    }
    row = AccountMemory(
        user_key=user_key,
        category=category,
        summary=summary,
        payload_json=json.dumps(payload, ensure_ascii=False),
        summary_hash=f"h_{abs(hash((user_key, summary, captured_offset_days))) % 10**12}",
        raw_excerpt=raw_excerpt,
        confidence=confidence,
        use_count=use_count,
        is_archived=is_archived,
        superseded_by_id=superseded_by_id,
        captured_at=datetime.utcnow() - timedelta(days=captured_offset_days),
        last_verified_at=datetime.utcnow(),
        source_module="chat",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    rid = int(row.id)
    db.close()
    return rid


# ─── User-key gate ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("reserved_key", ["__demo__", "__guest__", "", "   "])
def test_reserved_user_keys_blocked(db_factory, reserved_key):
    db = db_factory()
    try:
        result = _run(
            ExperienceRecaller().invoke(
                RecallerInput(
                    db=db,
                    user_key=reserved_key,
                    current_topic_dimensions=["leadership"],
                )
            )
        )
    finally:
        db.close()

    assert result.status == "completed"  # gate is a "no match", not a failure
    assert result.summary["no_match_reason"] == "unauthorized_or_demo"
    assert result.summary["experiences"] == []
    assert result.summary["kb_size"] == 0


# ─── kb_empty path ───────────────────────────────────────────────────────────


def test_empty_kb_returns_kb_empty(db_factory):
    db = db_factory()
    try:
        result = _run(
            ExperienceRecaller().invoke(
                RecallerInput(
                    db=db,
                    user_key="alice",
                    current_topic_dimensions=["leadership"],
                )
            )
        )
    finally:
        db.close()
    assert result.summary["no_match_reason"] == "kb_empty"
    assert result.summary["kb_size"] == 0


# ─── no_dimension_match path ─────────────────────────────────────────────────


def test_no_dimension_match(db_factory):
    _seed_experience(db_factory, dimensions=["teamwork", "planning"])
    db = db_factory()
    try:
        result = _run(
            ExperienceRecaller().invoke(
                RecallerInput(
                    db=db,
                    user_key="alice",
                    current_topic_dimensions=["failure_recovery"],
                )
            )
        )
    finally:
        db.close()
    assert result.summary["no_match_reason"] == "no_dimension_match"
    assert result.summary["kb_size"] == 1
    assert result.summary["experiences"] == []


# ─── transcript dedup → all_used ─────────────────────────────────────────────


def test_already_in_transcript_skipped(db_factory):
    raw = "我大三时组织过 50 人发布会,出席率超 90%"
    _seed_experience(
        db_factory,
        dimensions=["leadership"],
        raw_excerpt=raw,
    )
    transcript = [
        {"role": "user", "content": f"嗯, {raw} ,那次挺有挑战的"},
    ]
    db = db_factory()
    try:
        result = _run(
            ExperienceRecaller().invoke(
                RecallerInput(
                    db=db,
                    user_key="alice",
                    current_topic_dimensions=["leadership"],
                    transcript_so_far=transcript,
                )
            )
        )
    finally:
        db.close()
    assert result.summary["no_match_reason"] == "all_used"


# ─── Happy path: matched experience surfaced ─────────────────────────────────


def test_match_returns_shaped_experience(db_factory):
    _seed_experience(
        db_factory,
        summary="大三组织 50 人发布会",
        dimensions=["leadership", "cross_functional"],
        behavioral_hook="S=校创社团|T=2月内|A=划分子组|R=出席率90%",
        confidence=0.92,
    )
    db = db_factory()
    try:
        result = _run(
            ExperienceRecaller().invoke(
                RecallerInput(
                    db=db,
                    user_key="alice",
                    current_topic_dimensions=["leadership"],
                )
            )
        )
    finally:
        db.close()

    assert result.summary["no_match_reason"] is None
    assert len(result.summary["experiences"]) == 1
    exp = result.summary["experiences"][0]
    assert exp["summary"] == "大三组织 50 人发布会"
    assert "leadership" in exp["dimensions"]
    assert "cross_functional" in exp["dimensions"]
    assert exp["behavioral_hook"].startswith("S=")
    assert exp["confidence"] == 0.92
    assert exp["age_days"] == 0


# ─── Archived rows excluded ──────────────────────────────────────────────────


def test_archived_row_excluded(db_factory):
    _seed_experience(db_factory, dimensions=["leadership"], is_archived=True)
    db = db_factory()
    try:
        result = _run(
            ExperienceRecaller().invoke(
                RecallerInput(
                    db=db,
                    user_key="alice",
                    current_topic_dimensions=["leadership"],
                )
            )
        )
    finally:
        db.close()
    assert result.summary["kb_size"] == 0
    assert result.summary["no_match_reason"] == "kb_empty"


# ─── Superseded rows excluded ────────────────────────────────────────────────


def test_superseded_row_excluded(db_factory):
    old_id = _seed_experience(
        db_factory,
        summary="老想法 (superseded)",
        dimensions=["leadership"],
        raw_excerpt="raw old",
    )
    new_id = _seed_experience(
        db_factory,
        summary="新想法",
        dimensions=["leadership"],
        raw_excerpt="raw new",
    )
    db = db_factory()
    try:
        old_row = db.query(AccountMemory).filter(AccountMemory.id == old_id).one()
        old_row.superseded_by_id = new_id
        db.commit()
    finally:
        db.close()

    db2 = db_factory()
    try:
        result = _run(
            ExperienceRecaller().invoke(
                RecallerInput(
                    db=db2,
                    user_key="alice",
                    current_topic_dimensions=["leadership"],
                )
            )
        )
    finally:
        db2.close()
    summaries = [e["summary"] for e in result.summary["experiences"]]
    assert "老想法 (superseded)" not in summaries
    assert "新想法" in summaries


# ─── Top-N truncation ────────────────────────────────────────────────────────


def test_top_n_truncation_respects_max_results(db_factory):
    for i in range(5):
        _seed_experience(
            db_factory,
            summary=f"exp {i}",
            dimensions=["leadership"],
            raw_excerpt=f"raw {i}",
            confidence=0.9,
        )
    db = db_factory()
    try:
        result = _run(
            ExperienceRecaller().invoke(
                RecallerInput(
                    db=db,
                    user_key="alice",
                    current_topic_dimensions=["leadership"],
                    max_results=2,
                )
            )
        )
    finally:
        db.close()
    assert len(result.summary["experiences"]) == 2
    assert result.summary["kb_size"] == 5


# ─── Sorting: confidence × recency × unused bonus ────────────────────────────


def test_recency_weights_newer_higher(db_factory):
    """All else equal, the newer experience should come first."""
    _seed_experience(
        db_factory,
        summary="老的(180 天前)",
        dimensions=["leadership"],
        raw_excerpt="raw old",
        confidence=0.9,
        captured_offset_days=180,
    )
    _seed_experience(
        db_factory,
        summary="新的(今天)",
        dimensions=["leadership"],
        raw_excerpt="raw new",
        confidence=0.9,
        captured_offset_days=0,
    )
    db = db_factory()
    try:
        result = _run(
            ExperienceRecaller().invoke(
                RecallerInput(
                    db=db,
                    user_key="alice",
                    current_topic_dimensions=["leadership"],
                )
            )
        )
    finally:
        db.close()
    summaries = [e["summary"] for e in result.summary["experiences"]]
    assert summaries[0] == "新的(今天)"


def test_unused_bonus_favors_never_surfaced(db_factory):
    """Two equally-recent equally-confident rows; the unused one wins."""
    _seed_experience(
        db_factory,
        summary="已用过 3 次",
        dimensions=["leadership"],
        raw_excerpt="raw used",
        confidence=0.9,
        use_count=3,
    )
    _seed_experience(
        db_factory,
        summary="从未用过",
        dimensions=["leadership"],
        raw_excerpt="raw unused",
        confidence=0.9,
        use_count=0,
    )
    db = db_factory()
    try:
        result = _run(
            ExperienceRecaller().invoke(
                RecallerInput(
                    db=db,
                    user_key="alice",
                    current_topic_dimensions=["leadership"],
                )
            )
        )
    finally:
        db.close()
    summaries = [e["summary"] for e in result.summary["experiences"]]
    assert summaries[0] == "从未用过"


# ─── Cross-user isolation ────────────────────────────────────────────────────


def test_other_users_experiences_excluded(db_factory):
    _seed_experience(
        db_factory, user_key="alice",
        summary="alice 的经历", dimensions=["leadership"],
        raw_excerpt="alice raw",
    )
    _seed_experience(
        db_factory, user_key="bob",
        summary="bob 的经历", dimensions=["leadership"],
        raw_excerpt="bob raw",
    )
    db = db_factory()
    try:
        result = _run(
            ExperienceRecaller().invoke(
                RecallerInput(
                    db=db,
                    user_key="alice",
                    current_topic_dimensions=["leadership"],
                )
            )
        )
    finally:
        db.close()
    assert result.summary["kb_size"] == 1
    assert result.summary["experiences"][0]["summary"] == "alice 的经历"


# ─── Non-experience categories filtered out ──────────────────────────────────


def test_non_experience_categories_filtered(db_factory):
    """skill_claim / preference rows should never leak into recall."""
    _seed_experience(
        db_factory,
        summary="实际经历", dimensions=["leadership"],
        category="experience",
    )
    _seed_experience(
        db_factory,
        summary="一项技能", dimensions=[],
        category="skill_claim",
    )
    db = db_factory()
    try:
        result = _run(
            ExperienceRecaller().invoke(
                RecallerInput(
                    db=db,
                    user_key="alice",
                    current_topic_dimensions=["leadership"],
                )
            )
        )
    finally:
        db.close()
    assert result.summary["kb_size"] == 1  # only experience counted
    summaries = [e["summary"] for e in result.summary["experiences"]]
    assert summaries == ["实际经历"]
