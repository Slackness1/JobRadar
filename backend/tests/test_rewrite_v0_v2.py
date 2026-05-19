"""Tests for the v0/v2 thesis-aware rewrite path (Phase 1 BE-2, C-1 简 + C-5).

Covers:
  - propose_rewrite_v0_v2 returns v0 echo + v2 LLM rewrite
  - empty account_memory → v2.needs_plan_mode=True (LLM NOT called)
  - fabricated number in v2 → warnings array with 3 suggestion_options
  - relevant_memory_for_bullet fuzzy match scores correctly
  - Schema RewriteV0V2Out shape sanity
"""
from __future__ import annotations

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    AccountMemory,
    ResumeConfirmedProfile,
    ResumeCopilotSession,
)
from app.schemas_resume_copilot import (
    RewriteV0V2Out,
    RewriteVersionV2,
    RewriteWarning,
)
from app.services.memory.api_helpers import relevant_memory_for_bullet
from app.services.resume_copilot.chat import (
    _build_fabrication_warnings,
    _detect_fabricated_numbers_in_text,
    _format_memory_block,
    propose_rewrite_v0_v2,
)


# ─── Fixtures / helpers ──────────────────────────────────────────────────────


def _make_factory():
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _seed_session(db: Session, *, user_key: str = 'student-uk-1') -> int:
    session = ResumeCopilotSession(
        file_name='cv.pdf',
        user_key=user_key,
        status='completed',
        recommendation_status='completed',
        feedback_status='running',
        extracted_text='',
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    profile = {
        'basic_info': {'name': 'Wang'},
        'education': [{
            'school': '上海交大高金 SAIF',
            'degree': '金融硕士',
            'major': '金融硕士',
            'highlights': [],
        }],
        'internships': [{
            'company': '中信证券',
            'role': '行研助理',
            'bullets': [
                '跟踪 5 只半导体股票,撰写 3 篇深度报告',
            ],
        }],
        'projects': [],
        'skills': {'technical': ['Python'], 'tools': [], 'languages': []},
        'languages': [],
        'awards': [],
        'candidate_summary': '',
        'inferred_roles': [],
        'inferred_tracks': [],
    }
    db.add(ResumeConfirmedProfile(
        session_id=session.id,
        profile_json=json.dumps(profile),
    ))
    db.commit()
    return int(session.id)


def _seed_memory(
    db: Session,
    *,
    user_key: str,
    summary: str,
    category: str = 'experience',
    raw_excerpt: str = '',
    payload: dict | None = None,
) -> int:
    """Insert AccountMemory bypassing dispatcher flag gate (tests don't depend on flag)."""
    import hashlib
    digest = hashlib.sha256(f"{user_key}::{category}::{summary}".encode()).hexdigest()[:24]
    row = AccountMemory(
        user_key=user_key,
        category=category,
        summary=summary,
        summary_hash=digest,
        payload_json=json.dumps(payload or {'behavioral_hook': summary}),
        source_module='test',
        raw_excerpt=raw_excerpt,
        confidence=0.9,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return int(row.id)


# ─── Stub LLM providers ──────────────────────────────────────────────────────


class _StubV2Provider:
    """LLM stub that returns a thesis-aware rewrite."""
    def __init__(self, text: str = '', rationale: str = ''):
        self.text = text or '跟踪 5 只半导体股票时, 发现头部 IDM 在车规 MCU 切换上的 lead time 被市场低估, 据此给 leader 提出反共识 buy 建议'
        self.rationale = rationale or '基于 memory 里关于半导体调研的具体细节, 注入非共识 view'
        self.called_with: list = []

    def generate_v2(self, messages_payload: list[dict]) -> dict:
        self.called_with.append(messages_payload)
        return {'text': self.text, 'rationale': self.rationale}


class _NeverCalledProvider:
    """LLM stub that fails the test if called — for empty-memory short-circuit."""
    def __init__(self):
        self.called = False

    def generate_v2(self, messages_payload: list[dict]) -> dict:
        self.called = True
        raise AssertionError('LLM should not be called when memory is empty')


# ─── Tests: relevant_memory_for_bullet ───────────────────────────────────────


def test_relevant_memory_for_bullet_matches_overlapping_summary():
    factory = _make_factory()
    db = factory()
    _seed_memory(
        db, user_key='uk-1',
        summary='在中信证券跟踪半导体行业, 重点是 IDM 车规 MCU',
        raw_excerpt='跟了三个月半导体,发现车规 MCU lead time 很有 alpha',
    )
    _seed_memory(
        db, user_key='uk-1',
        summary='完全不相关的咖啡店打工经历',
    )
    matches = relevant_memory_for_bullet(
        db, user_key='uk-1',
        bullet_text='跟踪 5 只半导体股票,撰写 3 篇深度报告',
        k=3,
    )
    db.close()
    assert len(matches) >= 1
    # 半导体 entry must rank first
    assert '半导体' in matches[0]['summary']
    assert matches[0]['match_score'] > 0


def test_relevant_memory_for_bullet_skips_reserved_user_keys():
    factory = _make_factory()
    db = factory()
    matches_demo = relevant_memory_for_bullet(
        db, user_key='__demo__', bullet_text='any bullet', k=3,
    )
    matches_guest = relevant_memory_for_bullet(
        db, user_key='__guest__', bullet_text='any bullet', k=3,
    )
    matches_empty = relevant_memory_for_bullet(
        db, user_key='', bullet_text='any bullet', k=3,
    )
    db.close()
    assert matches_demo == []
    assert matches_guest == []
    assert matches_empty == []


def test_relevant_memory_for_bullet_returns_empty_when_no_match():
    factory = _make_factory()
    db = factory()
    _seed_memory(db, user_key='uk-1', summary='烘焙咖啡冲煮拉花')
    matches = relevant_memory_for_bullet(
        db, user_key='uk-1',
        bullet_text='搭建因子模型计算 IR',
        k=3,
    )
    db.close()
    assert matches == []


def test_relevant_memory_for_bullet_excludes_other_categories():
    factory = _make_factory()
    db = factory()
    _seed_memory(
        db, user_key='uk-1',
        summary='偏好上海 / 公募行研',
        category='preference',
        payload={'dimension': 'industry', 'value': '公募行研'},
    )
    matches = relevant_memory_for_bullet(
        db, user_key='uk-1',
        bullet_text='公募行研实习, 上海',
        k=3,
    )
    db.close()
    # preference category should NOT be returned (only experience + skill_claim)
    assert matches == []


# ─── Tests: propose_rewrite_v0_v2 ────────────────────────────────────────────


def test_propose_rewrite_v0_v2_happy_path_returns_v0_and_v2():
    factory = _make_factory()
    db = factory()
    session_id = _seed_session(db, user_key='uk-1')
    _seed_memory(
        db, user_key='uk-1',
        summary='半导体行研, IDM 车规 MCU 调研, 上海 SAIF',
        raw_excerpt='跟了三个月半导体, 发现车规 MCU lead time 很有 alpha',
    )
    provider = _StubV2Provider()
    out = propose_rewrite_v0_v2(
        session_id=session_id,
        bullet_text='跟踪 5 只半导体股票,撰写 3 篇深度报告',
        field_path='internships.0.bullets.0',
        db=db,
        target_job_description='公募行研 半导体 买方',
        target_title='中信证券 · 行研助理',
        section='internships',
        provider=provider,
    )
    db.close()

    assert isinstance(out, RewriteV0V2Out)
    assert out.v0.text == '跟踪 5 只半导体股票,撰写 3 篇深度报告'
    assert out.v2.text == provider.text
    assert out.v2.needs_plan_mode is False
    assert out.v2.warnings == []   # the stub used only anchor numbers (5 / 3) so no fabrication
    assert out.rationale != ''
    assert len(out.memory_refs) == 1
    # LLM was called
    assert len(provider.called_with) == 1


def test_propose_rewrite_v0_v2_empty_memory_returns_needs_plan_mode_without_calling_llm():
    factory = _make_factory()
    db = factory()
    session_id = _seed_session(db, user_key='uk-empty')
    # NO memory rows for this user
    provider = _NeverCalledProvider()
    out = propose_rewrite_v0_v2(
        session_id=session_id,
        bullet_text='跟踪 5 只半导体股票,撰写 3 篇深度报告',
        field_path='internships.0.bullets.0',
        db=db,
        provider=provider,
    )
    db.close()

    assert out.v0.text == '跟踪 5 只半导体股票,撰写 3 篇深度报告'
    assert out.v2.needs_plan_mode is True
    assert '需要更多经历细节' in out.v2.text
    assert out.v2.warnings == []
    assert out.memory_refs == []
    assert provider.called is False


def test_propose_rewrite_v0_v2_fabricated_number_emits_warning_with_3_suggestions():
    factory = _make_factory()
    db = factory()
    session_id = _seed_session(db, user_key='uk-fab')
    _seed_memory(
        db, user_key='uk-fab',
        summary='半导体行研, 写过深度报告, 上海',
        raw_excerpt='我跟了几个月半导体, 写了一些报告',
    )
    # LLM hallucinates "30 只" + "15 篇" — these numbers are NOT in the profile
    # (profile has "5 只" and "3 篇" only).
    provider = _StubV2Provider(
        text='跟踪 30 只半导体股票, 撰写 15 篇深度报告, 据此提出反共识 buy 建议',
        rationale='注入非共识 view',
    )
    out = propose_rewrite_v0_v2(
        session_id=session_id,
        bullet_text='跟踪 5 只半导体股票,撰写 3 篇深度报告',
        field_path='internships.0.bullets.0',
        db=db,
        provider=provider,
    )
    db.close()

    assert out.v2.needs_plan_mode is False
    # Both 30 and 15 should be flagged
    flagged_numbers = {w.number for w in out.v2.warnings}
    assert '30' in flagged_numbers
    assert '15' in flagged_numbers
    # Each warning has the canonical 3 suggestion options
    for w in out.v2.warnings:
        assert w.type == 'fabricated_number'
        actions = {s.action for s in w.suggestion_options}
        assert actions == {'fill_real', 'delete_number', 'vague'}
        assert len(w.suggestion_options) == 3
        labels = {s.label for s in w.suggestion_options}
        assert '填实数' in labels
        assert '删数' in labels


def test_propose_rewrite_v0_v2_does_not_strip_warnings_when_present():
    """CLAUDE.md red line: never suppress fabrication warnings."""
    factory = _make_factory()
    db = factory()
    session_id = _seed_session(db, user_key='uk-noStrip')
    _seed_memory(
        db, user_key='uk-noStrip',
        summary='半导体行研深度报告',
    )
    provider = _StubV2Provider(text='跟 99 只股票, 写 88 篇报告')
    out = propose_rewrite_v0_v2(
        session_id=session_id,
        bullet_text='跟踪 5 只半导体股票,撰写 3 篇深度报告',
        field_path='internships.0.bullets.0',
        db=db,
        provider=provider,
    )
    db.close()
    # warnings MUST be present, non-empty
    assert out.v2.warnings, 'fabrication warnings must surface'
    assert len(out.v2.warnings) == 2  # 99 + 88
    # And the offending text is NOT scrubbed from v2.text
    assert '99' in out.v2.text
    assert '88' in out.v2.text


# ─── Tests: low-level helpers ────────────────────────────────────────────────


def test_detect_fabricated_numbers_in_text():
    anchor = {'5', '3', '20%'}
    out = _detect_fabricated_numbers_in_text(
        '跟踪 5 只, 写 3 篇, IR 提升 30%', anchor,
    )
    # 30% is not in anchor — should be flagged
    assert '30%' in out
    assert '5' not in out
    assert '3' not in out


def test_build_fabrication_warnings_empty_profile_skips():
    # No anchor numbers in profile → can't decide → no warning (avoid false positive)
    warnings = _build_fabrication_warnings('跟踪 99 只股票', {})
    assert warnings == []


def test_build_fabrication_warnings_with_anchor():
    profile = {
        'internships': [{
            'company': 'X', 'role': 'Y',
            'bullets': ['跟踪 5 只股票'],
        }],
        'projects': [],
    }
    warnings = _build_fabrication_warnings('跟踪 99 只股票', profile)
    assert len(warnings) == 1
    assert warnings[0].number == '99'
    assert len(warnings[0].suggestion_options) == 3


def test_format_memory_block_includes_category_and_raw_excerpt():
    entries = [
        {
            'category': 'experience',
            'summary': '半导体行研深度报告',
            'raw_excerpt': '跟了三个月半导体, 觉得车规 MCU 有 alpha',
        },
    ]
    block = _format_memory_block(entries)
    assert 'student_memory' in block
    assert 'experience' in block
    assert '半导体行研' in block
    assert '车规 MCU' in block


def test_format_memory_block_empty_returns_empty_string():
    assert _format_memory_block([]) == ''


# ─── Schema sanity ───────────────────────────────────────────────────────────


def test_rewrite_v0_v2_out_schema_roundtrip():
    out = RewriteV0V2Out(
        field_path='internships.0.bullets.0',
        section='internships',
        target_title='X · Y',
        v0={'text': '原文'},
        v2=RewriteVersionV2(
            text='改写后',
            needs_plan_mode=False,
            warnings=[
                RewriteWarning(
                    type='fabricated_number',
                    number='30%',
                    suggestion_options=[
                        {'action': 'fill_real', 'label': '填实数'},
                        {'action': 'delete_number', 'label': '删数'},
                        {'action': 'vague', 'label': '接受模糊版本'},
                    ],
                ),
            ],
        ),
        rationale='because',
        memory_refs=[1, 2, 3],
    )
    dumped = out.model_dump()
    assert dumped['v0']['text'] == '原文'
    assert dumped['v2']['warnings'][0]['number'] == '30%'
    assert len(dumped['v2']['warnings'][0]['suggestion_options']) == 3
    # Round-trip
    reloaded = RewriteV0V2Out.model_validate(dumped)
    assert reloaded.v2.warnings[0].suggestion_options[0].action == 'fill_real'
