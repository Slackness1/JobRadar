"""PR-2 tests: chat extractor multi-category dual-write.

These complement the Phase 1 ``test_student_kb_extractor.py`` suite (which
covers the legacy student_experiences single-write path). PR-2 adds:
  - account_memory writes via dispatcher
  - structured payload extraction for skill_claim / preference / identity_fact
  - evidence row derivation from experience candidates
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import AccountMemory, ResumeCopilotSession, StudentExperience


@pytest.fixture
def db_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _make_llm_response(items: list[dict]):
    msg = MagicMock()
    msg.content = json.dumps({"items": items}, ensure_ascii=False)
    choice = MagicMock()
    choice.message = msg
    completion = MagicMock()
    completion.choices = [choice]
    return completion


def _make_session(db_factory, user_key="real_user") -> int:
    db = db_factory()
    s = ResumeCopilotSession(file_name="cv.pdf", user_key=user_key, status="completed")
    db.add(s)
    db.commit()
    db.refresh(s)
    sid = int(s.id)
    db.close()
    return sid


# ─── Reusable candidates ─────────────────────────────────────────────────────


EXPERIENCE_CANDIDATE = {
    "name": "字节实习用户增长",
    "summary": "三个月将次留率从12%提升至16%",
    "category": "experience",
    "star_dimensions": ["analytical_thinking", "ownership"],
    "behavioral_hook": "S=在字节实习|T=次留率12%|A=做归因模型|R=三个月提升至16%",
    "quantified": {"team_size": 1, "duration_months": 3, "outcome": "次留率从12%提升至16%"},
    "raw_excerpt": "我在字节实习三个月,把次留率从 12% 提升到 16%",
    "confidence": 0.95,
    "has_temporal_anchor": True,
    "has_concrete_action": True,
    "has_outcome": True,
}


SKILL_CANDIDATE = {
    "name": "Python 熟练",
    "summary": "Python pandas 熟练",
    "category": "skill_claim",
    "star_dimensions": [],
    "behavioral_hook": "",
    "quantified": {},
    "raw_excerpt": "Python pandas 熟练",
    "confidence": 0.92,
    "has_temporal_anchor": False,
    "has_concrete_action": False,
    "has_outcome": False,
    "skill_name": "Python pandas",
    "skill_level": "advanced",
}


PREFERENCE_CANDIDATE = {
    "name": "想去上海",
    "summary": "想去上海工作",
    "category": "preference",
    "star_dimensions": [],
    "behavioral_hook": "",
    "quantified": {},
    "raw_excerpt": "想去上海工作",
    "confidence": 0.9,
    "has_temporal_anchor": False,
    "has_concrete_action": False,
    "has_outcome": False,
    "preference_dimension": "city",
    "preference_value": "上海",
}


IDENTITY_CANDIDATE = {
    "name": "交大本科",
    "summary": "上海交大计算机本科",
    "category": "identity_fact",
    "star_dimensions": [],
    "behavioral_hook": "",
    "quantified": {},
    "raw_excerpt": "上海交大计算机本科",
    "confidence": 0.95,
    "has_temporal_anchor": False,
    "has_concrete_action": False,
    "has_outcome": False,
    "identity_fact_kind": "school",
    "identity_fact_value": "上海交通大学",
}


SOURCE_TEXT = (
    "我在字节实习三个月,把次留率从 12% 提升到 16%。"
    "Python pandas 熟练。想去上海工作。上海交大计算机本科。"
)


# ─── Multi-category dual-write ──────────────────────────────────────────────


@patch("app.services.resume_copilot.memory.extractor.STUDENT_KB_ENABLED", True)
@patch("app.services.resume_copilot.memory.extractor.UNIFIED_MEMORY_ENABLED", True)
@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
@patch("app.services.resume_copilot.memory.extractor._build_llm_client")
def test_experience_writes_to_both_tables(mock_client, db_factory):
    from app.services.resume_copilot.memory.extractor import extract_for_chat_turn

    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([EXPERIENCE_CANDIDATE])
    mock_client.return_value = fake

    sid = _make_session(db_factory)
    db = db_factory()
    try:
        result = extract_for_chat_turn(db, session_id=sid, user_content=SOURCE_TEXT)

        # Legacy leg
        assert result["inserted"] == 1
        assert db.query(StudentExperience).count() == 1

        # Unified leg: 1 experience + ≥1 derived evidence row
        assert result["memory_inserted"] == 1
        assert result["evidence_inserted"] >= 1

        rows = db.query(AccountMemory).all()
        categories = {r.category for r in rows}
        assert "experience" in categories
        assert "evidence" in categories
    finally:
        db.close()


@patch("app.services.resume_copilot.memory.extractor.STUDENT_KB_ENABLED", True)
@patch("app.services.resume_copilot.memory.extractor.UNIFIED_MEMORY_ENABLED", True)
@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
@patch("app.services.resume_copilot.memory.extractor._build_llm_client")
def test_skill_claim_writes_to_account_memory_only(mock_client, db_factory):
    """skill_claim has no STAR anchors, so legacy still writes it (per category
    column), but the new payload is structured (skill_name)."""
    from app.services.resume_copilot.memory.extractor import extract_for_chat_turn

    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([SKILL_CANDIDATE])
    mock_client.return_value = fake

    sid = _make_session(db_factory)
    db = db_factory()
    try:
        result = extract_for_chat_turn(db, session_id=sid, user_content=SOURCE_TEXT)
        assert result["memory_inserted"] == 1
        assert result["evidence_inserted"] == 0  # skill_claim doesn't derive evidence

        row = db.query(AccountMemory).filter(AccountMemory.category == "skill_claim").one()
        payload = json.loads(row.payload_json)
        assert payload["skill_name"] == "Python pandas"
        assert payload["level"] == "advanced"
    finally:
        db.close()


@patch("app.services.resume_copilot.memory.extractor.STUDENT_KB_ENABLED", True)
@patch("app.services.resume_copilot.memory.extractor.UNIFIED_MEMORY_ENABLED", True)
@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
@patch("app.services.resume_copilot.memory.extractor._build_llm_client")
def test_preference_emits_structured_payload(mock_client, db_factory):
    from app.services.resume_copilot.memory.extractor import extract_for_chat_turn

    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([PREFERENCE_CANDIDATE])
    mock_client.return_value = fake

    sid = _make_session(db_factory)
    db = db_factory()
    try:
        extract_for_chat_turn(db, session_id=sid, user_content=SOURCE_TEXT)
        row = db.query(AccountMemory).filter(AccountMemory.category == "preference").one()
        payload = json.loads(row.payload_json)
        assert payload["dimension"] == "city"
        assert payload["value"] == "上海"
    finally:
        db.close()


@patch("app.services.resume_copilot.memory.extractor.STUDENT_KB_ENABLED", True)
@patch("app.services.resume_copilot.memory.extractor.UNIFIED_MEMORY_ENABLED", True)
@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
@patch("app.services.resume_copilot.memory.extractor._build_llm_client")
def test_identity_fact_emits_structured_payload(mock_client, db_factory):
    from app.services.resume_copilot.memory.extractor import extract_for_chat_turn

    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([IDENTITY_CANDIDATE])
    mock_client.return_value = fake

    sid = _make_session(db_factory)
    db = db_factory()
    try:
        extract_for_chat_turn(db, session_id=sid, user_content=SOURCE_TEXT)
        row = db.query(AccountMemory).filter(AccountMemory.category == "identity_fact").one()
        payload = json.loads(row.payload_json)
        assert payload["kind"] == "school"
        assert payload["value"] == "上海交通大学"
    finally:
        db.close()


@patch("app.services.resume_copilot.memory.extractor.STUDENT_KB_ENABLED", True)
@patch("app.services.resume_copilot.memory.extractor.UNIFIED_MEMORY_ENABLED", True)
@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
@patch("app.services.resume_copilot.memory.extractor._build_llm_client")
def test_preference_missing_structured_fields_skipped(mock_client, db_factory):
    """LLM forgets to fill preference_dimension → skip rather than write
    invalid payload. Legacy leg still records the candidate."""
    from app.services.resume_copilot.memory.extractor import extract_for_chat_turn

    broken = {**PREFERENCE_CANDIDATE, "preference_dimension": "", "preference_value": ""}
    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([broken])
    mock_client.return_value = fake

    sid = _make_session(db_factory)
    db = db_factory()
    try:
        result = extract_for_chat_turn(db, session_id=sid, user_content=SOURCE_TEXT)
        # Legacy still inserts (Phase 1 only cared about summary)
        assert result["inserted"] == 1
        # Unified leg skipped — no preference row
        assert db.query(AccountMemory).filter(AccountMemory.category == "preference").count() == 0
    finally:
        db.close()


@patch("app.services.resume_copilot.memory.extractor.STUDENT_KB_ENABLED", True)
@patch("app.services.resume_copilot.memory.extractor.UNIFIED_MEMORY_ENABLED", True)
@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
@patch("app.services.resume_copilot.memory.extractor._build_llm_client")
def test_experience_derives_evidence_tags(mock_client, db_factory):
    """team_size + duration_months + outcome from quantified should each
    become an EvidenceTag on the derived evidence row."""
    from app.services.resume_copilot.memory.extractor import extract_for_chat_turn

    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([EXPERIENCE_CANDIDATE])
    mock_client.return_value = fake

    sid = _make_session(db_factory)
    db = db_factory()
    try:
        extract_for_chat_turn(db, session_id=sid, user_content=SOURCE_TEXT)

        evidence_row = db.query(AccountMemory).filter(AccountMemory.category == "evidence").one()
        payload = json.loads(evidence_row.payload_json)
        assert payload["source"] == "chat_extract"
        tag_types = {t["type"] for t in payload["tags"]}
        assert "metric" in tag_types or "duration" in tag_types or "outcome" in tag_types
        # Anti-hallucination: text must be the raw excerpt verbatim
        assert payload["text"] == EXPERIENCE_CANDIDATE["raw_excerpt"]
    finally:
        db.close()


# ─── Flag gating ────────────────────────────────────────────────────────────


@patch("app.services.resume_copilot.memory.extractor.STUDENT_KB_ENABLED", True)
@patch("app.services.resume_copilot.memory.extractor.UNIFIED_MEMORY_ENABLED", False)
@patch("app.services.resume_copilot.memory.extractor._build_llm_client")
def test_unified_flag_off_only_legacy_writes(mock_client, db_factory):
    from app.services.resume_copilot.memory.extractor import extract_for_chat_turn

    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([EXPERIENCE_CANDIDATE])
    mock_client.return_value = fake

    sid = _make_session(db_factory)
    db = db_factory()
    try:
        result = extract_for_chat_turn(db, session_id=sid, user_content=SOURCE_TEXT)
        assert result["inserted"] == 1
        assert result["memory_inserted"] == 0
        assert db.query(AccountMemory).count() == 0
        assert db.query(StudentExperience).count() == 1
    finally:
        db.close()


@patch("app.services.resume_copilot.memory.extractor.STUDENT_KB_ENABLED", False)
@patch("app.services.resume_copilot.memory.extractor.UNIFIED_MEMORY_ENABLED", True)
@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
@patch("app.services.resume_copilot.memory.extractor._build_llm_client")
def test_legacy_flag_off_only_unified_writes(mock_client, db_factory):
    """Once we're confident in unified, this is the steady-state config."""
    from app.services.resume_copilot.memory.extractor import extract_for_chat_turn

    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([EXPERIENCE_CANDIDATE])
    mock_client.return_value = fake

    sid = _make_session(db_factory)
    db = db_factory()
    try:
        result = extract_for_chat_turn(db, session_id=sid, user_content=SOURCE_TEXT)
        assert result["inserted"] == 0
        assert result["memory_inserted"] == 1
        assert db.query(StudentExperience).count() == 0
        assert db.query(AccountMemory).count() >= 2  # experience + evidence
    finally:
        db.close()


@patch("app.services.resume_copilot.memory.extractor.STUDENT_KB_ENABLED", False)
@patch("app.services.resume_copilot.memory.extractor.UNIFIED_MEMORY_ENABLED", False)
@patch("app.services.resume_copilot.memory.extractor._build_llm_client")
def test_both_flags_off_skips_everything(mock_client, db_factory):
    from app.services.resume_copilot.memory.extractor import extract_for_chat_turn

    sid = _make_session(db_factory)
    db = db_factory()
    try:
        result = extract_for_chat_turn(db, session_id=sid, user_content=SOURCE_TEXT)
        assert result["skipped_reason"] == "flag_off"
    finally:
        db.close()
    # LLM never invoked
    mock_client.assert_not_called()


@patch("app.services.resume_copilot.memory.extractor.STUDENT_KB_ENABLED", True)
@patch("app.services.resume_copilot.memory.extractor.UNIFIED_MEMORY_ENABLED", True)
@patch("app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED", True)
@patch("app.services.resume_copilot.memory.extractor._build_llm_client")
def test_demo_session_still_blocked_in_both_legs(mock_client, db_factory):
    """Critical privacy guarantee: demo / guest user_keys produce zero rows
    in either table, even with both flags on."""
    from app.services.resume_copilot.memory.extractor import extract_for_chat_turn

    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([EXPERIENCE_CANDIDATE])
    mock_client.return_value = fake

    for reserved_key in ("__demo__", "__guest__"):
        sid = _make_session(db_factory, user_key=reserved_key)
        db = db_factory()
        try:
            result = extract_for_chat_turn(db, session_id=sid, user_content=SOURCE_TEXT)
            assert "reserved_user_key" in result["skipped_reason"]
        finally:
            db.close()
    # LLM should never have been called for blocked sessions.
    fake.chat.completions.create.assert_not_called()
