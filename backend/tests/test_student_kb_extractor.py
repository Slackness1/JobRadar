"""Unit tests for the student KB extractor.

Focus on the guard logic (3-anchor rule, substring check, demo/guest skip,
reserved-key safety). LLM call is mocked at the OpenAI client boundary.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import ResumeCopilotSession, StudentExperience


@pytest.fixture
def db_factory():
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _make_llm_response(items: list[dict]) -> MagicMock:
    """Build a MagicMock that mimics openai client.chat.completions.create."""
    msg = MagicMock()
    msg.content = json.dumps({'items': items}, ensure_ascii=False)
    choice = MagicMock()
    choice.message = msg
    completion = MagicMock()
    completion.choices = [choice]
    return completion


def _make_session(db_factory, user_key: str) -> int:
    db = db_factory()
    s = ResumeCopilotSession(file_name='cv.pdf', user_key=user_key, status='completed')
    db.add(s)
    db.commit()
    db.refresh(s)
    sid = int(s.id)
    db.close()
    return sid


# ---------- pure extractor logic --------------------------------------------


VALID_CANDIDATE = {
    'name': '组织 50 人产品发布会',
    'summary': '大三组织 50 人跨部门产品发布会',
    'category': 'experience',
    'star_dimensions': ['leadership', 'cross_functional'],
    'behavioral_hook': 'S=校创社团跨5部门|T=两月内办首场|A=主导周例会+子组owner|R=出席率90%',
    'quantified': {'team_size': 50, 'duration_months': 2},
    'raw_excerpt': '我大三时组织过一次 50 人的产品发布会',
    'confidence': 0.95,
    'has_temporal_anchor': True,
    'has_concrete_action': True,
    'has_outcome': True,
}

VALID_SOURCE = '我大三时组织过一次 50 人的产品发布会,跨 5 个部门两个月内办完,出席率超过 90%。'


@patch('app.services.resume_copilot.memory.extractor._build_llm_client')
def test_valid_candidate_passes_all_gates(mock_client):
    from app.services.resume_copilot.memory.extractor import extract_from_text

    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([VALID_CANDIDATE])
    mock_client.return_value = fake

    candidates, rejections = extract_from_text(VALID_SOURCE)
    assert len(candidates) == 1
    assert rejections == []
    assert candidates[0].category == 'experience'
    assert 'leadership' in candidates[0].star_dimensions


@patch('app.services.resume_copilot.memory.extractor._build_llm_client')
def test_experience_missing_temporal_anchor_rejected(mock_client):
    from app.services.resume_copilot.memory.extractor import extract_from_text

    bad = {**VALID_CANDIDATE, 'has_temporal_anchor': False}
    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([bad])
    mock_client.return_value = fake

    candidates, rejections = extract_from_text(VALID_SOURCE)
    assert candidates == []
    assert rejections == ['missing_anchors']


@patch('app.services.resume_copilot.memory.extractor._build_llm_client')
def test_experience_missing_outcome_rejected(mock_client):
    from app.services.resume_copilot.memory.extractor import extract_from_text

    bad = {**VALID_CANDIDATE, 'has_outcome': False}
    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([bad])
    mock_client.return_value = fake

    candidates, rejections = extract_from_text(VALID_SOURCE)
    assert candidates == []
    assert 'missing_anchors' in rejections


@patch('app.services.resume_copilot.memory.extractor._build_llm_client')
def test_raw_excerpt_not_in_source_rejected(mock_client):
    """Anti-hallucination guard: LLM cannot invent quotes."""
    from app.services.resume_copilot.memory.extractor import extract_from_text

    bad = {**VALID_CANDIDATE, 'raw_excerpt': '我组织过 100 人的发布会'}  # not in source
    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([bad])
    mock_client.return_value = fake

    candidates, rejections = extract_from_text(VALID_SOURCE)
    assert candidates == []
    assert rejections == ['raw_excerpt_not_substring']


@patch('app.services.resume_copilot.memory.extractor._build_llm_client')
def test_invalid_star_dimension_rejected(mock_client):
    from app.services.resume_copilot.memory.extractor import extract_from_text

    bad = {**VALID_CANDIDATE, 'star_dimensions': ['not_a_real_dim']}
    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([bad])
    mock_client.return_value = fake

    candidates, rejections = extract_from_text(VALID_SOURCE)
    assert candidates == []
    assert any(r.startswith('invalid_dimensions') for r in rejections)


@patch('app.services.resume_copilot.memory.extractor._build_llm_client')
def test_non_experience_dimensions_stripped(mock_client):
    """skill_claim with star_dimensions should have them silently stripped, not rejected."""
    from app.services.resume_copilot.memory.extractor import extract_from_text

    weird = {
        **VALID_CANDIDATE,
        'category': 'skill_claim',
        'star_dimensions': ['leadership'],  # would normally fail validation, but stripped first
        'summary': '熟悉 Python',
        'raw_excerpt': '我大三时组织过一次',  # any substring of source
        'has_temporal_anchor': False,
        'has_concrete_action': False,
        'has_outcome': False,
    }
    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([weird])
    mock_client.return_value = fake

    candidates, rejections = extract_from_text(VALID_SOURCE)
    assert len(candidates) == 1
    # The dim list was stripped; no anchor rule for non-experience categories.
    assert candidates[0].star_dimensions == []


@patch('app.services.resume_copilot.memory.extractor._build_llm_client')
def test_empty_source_returns_empty(mock_client):
    from app.services.resume_copilot.memory.extractor import extract_from_text

    candidates, rejections = extract_from_text('')
    assert candidates == []
    assert rejections == ['empty_source']
    # LLM never called.
    mock_client.assert_not_called()


@patch('app.services.resume_copilot.memory.extractor._build_llm_client')
def test_llm_failure_returns_empty(mock_client):
    from app.services.resume_copilot.memory.extractor import extract_from_text

    fake = MagicMock()
    fake.chat.completions.create.side_effect = RuntimeError('network')
    mock_client.return_value = fake

    candidates, rejections = extract_from_text(VALID_SOURCE)
    assert candidates == []
    assert rejections == []  # No rejections because no items even arrived.


# ---------- DB integration (guards, dedup) ----------------------------------


@patch('app.services.resume_copilot.memory.extractor.STUDENT_KB_ENABLED', True)
@patch('app.services.resume_copilot.memory.extractor._build_llm_client')
def test_extract_for_chat_turn_skips_demo_user_key(mock_client, db_factory):
    from app.services.resume_copilot.memory.extractor import extract_for_chat_turn

    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([VALID_CANDIDATE])
    mock_client.return_value = fake

    sid = _make_session(db_factory, user_key='__demo__')
    db = db_factory()
    try:
        result = extract_for_chat_turn(db, session_id=sid, user_content=VALID_SOURCE)
        assert result['skipped_reason'] == 'reserved_user_key:__demo__'
        assert result['inserted'] == 0
        assert db.query(StudentExperience).count() == 0
    finally:
        db.close()
    # LLM should never have been called.
    fake.chat.completions.create.assert_not_called()


@patch('app.services.resume_copilot.memory.extractor.STUDENT_KB_ENABLED', True)
@patch('app.services.resume_copilot.memory.extractor._build_llm_client')
def test_extract_for_chat_turn_skips_guest_user_key(mock_client, db_factory):
    from app.services.resume_copilot.memory.extractor import extract_for_chat_turn

    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([VALID_CANDIDATE])
    mock_client.return_value = fake

    sid = _make_session(db_factory, user_key='__guest__')
    db = db_factory()
    try:
        result = extract_for_chat_turn(db, session_id=sid, user_content=VALID_SOURCE)
        assert 'reserved_user_key' in result['skipped_reason']
        assert db.query(StudentExperience).count() == 0
    finally:
        db.close()


@patch('app.services.resume_copilot.memory.extractor.STUDENT_KB_ENABLED', False)
@patch('app.services.resume_copilot.memory.extractor._build_llm_client')
def test_extract_for_chat_turn_skips_when_flag_off(mock_client, db_factory):
    from app.services.resume_copilot.memory.extractor import extract_for_chat_turn

    sid = _make_session(db_factory, user_key='real_user_123')
    db = db_factory()
    try:
        result = extract_for_chat_turn(db, session_id=sid, user_content=VALID_SOURCE)
        assert result['skipped_reason'] == 'flag_off'
    finally:
        db.close()
    mock_client.assert_not_called()


@patch('app.services.resume_copilot.memory.extractor.STUDENT_KB_ENABLED', True)
@patch('app.services.resume_copilot.memory.extractor._build_llm_client')
def test_extract_for_chat_turn_inserts_real_user(mock_client, db_factory):
    from app.services.resume_copilot.memory.extractor import extract_for_chat_turn

    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([VALID_CANDIDATE])
    mock_client.return_value = fake

    sid = _make_session(db_factory, user_key='real_user_123')
    db = db_factory()
    try:
        result = extract_for_chat_turn(db, session_id=sid, user_content=VALID_SOURCE)
        assert result['inserted'] == 1
        assert result['refreshed'] == 0
        rows = db.query(StudentExperience).filter(StudentExperience.user_key == 'real_user_123').all()
        assert len(rows) == 1
        assert rows[0].user_confirmed is True  # 0.95 >= AUTO_CONFIRM_THRESHOLD (0.92)
    finally:
        db.close()


@patch('app.services.resume_copilot.memory.extractor.STUDENT_KB_ENABLED', True)
@patch('app.services.resume_copilot.memory.extractor._build_llm_client')
def test_extract_for_chat_turn_dedup_refreshes(mock_client, db_factory):
    """Second extraction of the same summary should refresh, not duplicate."""
    from app.services.resume_copilot.memory.extractor import extract_for_chat_turn

    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([VALID_CANDIDATE])
    mock_client.return_value = fake

    sid = _make_session(db_factory, user_key='real_user_xyz')
    db = db_factory()
    try:
        first = extract_for_chat_turn(db, session_id=sid, user_content=VALID_SOURCE)
        assert first['inserted'] == 1
        second = extract_for_chat_turn(db, session_id=sid, user_content=VALID_SOURCE)
        assert second['inserted'] == 0
        assert second['refreshed'] == 1
        assert db.query(StudentExperience).count() == 1
    finally:
        db.close()


@patch('app.services.resume_copilot.memory.extractor.STUDENT_KB_ENABLED', True)
@patch('app.services.resume_copilot.memory.extractor._build_llm_client')
def test_low_confidence_stores_unconfirmed(mock_client, db_factory):
    from app.services.resume_copilot.memory.extractor import extract_for_chat_turn

    low = {**VALID_CANDIDATE, 'confidence': 0.6}
    fake = MagicMock()
    fake.chat.completions.create.return_value = _make_llm_response([low])
    mock_client.return_value = fake

    sid = _make_session(db_factory, user_key='real_user_low')
    db = db_factory()
    try:
        extract_for_chat_turn(db, session_id=sid, user_content=VALID_SOURCE)
        row = db.query(StudentExperience).filter(StudentExperience.user_key == 'real_user_low').one()
        assert row.user_confirmed is False
    finally:
        db.close()
