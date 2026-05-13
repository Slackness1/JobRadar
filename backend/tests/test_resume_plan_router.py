"""Integration tests for the plan-mode router endpoints.

Spins up a FastAPI TestClient against an in-memory SQLite, seeds a
ResumeCopilotSession + parsed profile, then exercises:

- POST /plan/start — bootstrap from template
- GET  /plan — read current state
- POST /plan/approve — awaiting_plan_approval → clarifying
- POST /plan/actions — apply AgentAction (ask / write / replan / ...)
- error codes: 404 / 409 / 422
"""
from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import ResumeCopilotSession, ResumeParsedProfile
from app.routers.resume_copilot import router


@pytest.fixture
def client_with_session():
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def _override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)

    # seed: a session belonging to user 'alice' with a parsed profile
    db = SessionLocal()
    try:
        session_obj = ResumeCopilotSession(
            file_name='alice.pdf',
            name='alice',
            user_key='alice',
            status='awaiting_user_confirmation',
            extracted_text='',
            plan_status='idle',
        )
        db.add(session_obj)
        db.flush()
        profile_payload = {
            'basic_info': {'name': 'Alice'},
            'education': [{'school': 'Tsinghua'}],
            'internships': [
                {'company': 'ByteDance', 'role': 'DA Intern'},
                {'company': 'Tencent', 'role': 'PM Intern'},
            ],
            'projects': [
                {'name': 'Project A'},
                {'name': 'Project B'},
            ],
            'awards': [],
            'skills': {'technical': ['Python']},
        }
        parsed = ResumeParsedProfile(
            session_id=session_obj.id,
            profile_json=json.dumps(profile_payload),
        )
        db.add(parsed)
        db.commit()
        session_id = session_obj.id
    finally:
        db.close()

    yield client, session_id, SessionLocal


HEADERS_ALICE = {'X-Resume-User-Key': 'alice'}
HEADERS_BOB = {'X-Resume-User-Key': 'bob'}


# ─── /plan/start ────────────────────────────────────────────────────────────

def test_plan_start_creates_plan_from_template(client_with_session):
    client, sid, _ = client_with_session
    r = client.post(f'/api/resume-copilot/sessions/{sid}/plan/start', headers=HEADERS_ALICE)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['status'] == 'awaiting_plan_approval'
    assert data['version'] == 1
    # template: 1 self_intro + 1 education + 2 internships*(1+3 bullets) + 2 projects*(1+2 bullets) + 1 skill = 1+1+8+6+1 = 17
    assert len(data['items']) == 17
    intern_items = [it for it in data['items'] if it['kind'] == 'internship']
    intern_parents = [it for it in intern_items if it['parent_id'] is None]
    intern_bullets = [it for it in intern_items if it['parent_id'] is not None]
    assert len(intern_parents) == 2
    assert len(intern_bullets) == 6  # 3 per parent


def test_plan_start_rejects_other_user(client_with_session):
    client, sid, _ = client_with_session
    r = client.post(f'/api/resume-copilot/sessions/{sid}/plan/start', headers=HEADERS_BOB)
    assert r.status_code == 403


def test_plan_start_404_on_unknown_session(client_with_session):
    client, _, _ = client_with_session
    r = client.post('/api/resume-copilot/sessions/999/plan/start', headers=HEADERS_ALICE)
    assert r.status_code == 404


def test_plan_start_conflicts_on_existing_plan(client_with_session):
    client, sid, _ = client_with_session
    client.post(f'/api/resume-copilot/sessions/{sid}/plan/start', headers=HEADERS_ALICE)
    r2 = client.post(f'/api/resume-copilot/sessions/{sid}/plan/start', headers=HEADERS_ALICE)
    assert r2.status_code == 409


# ─── /plan GET ──────────────────────────────────────────────────────────────

def test_plan_get_404_before_start(client_with_session):
    client, sid, _ = client_with_session
    r = client.get(f'/api/resume-copilot/sessions/{sid}/plan', headers=HEADERS_ALICE)
    assert r.status_code == 404


def test_plan_get_after_start(client_with_session):
    client, sid, _ = client_with_session
    client.post(f'/api/resume-copilot/sessions/{sid}/plan/start', headers=HEADERS_ALICE)
    r = client.get(f'/api/resume-copilot/sessions/{sid}/plan', headers=HEADERS_ALICE)
    assert r.status_code == 200
    assert r.json()['status'] == 'awaiting_plan_approval'


# ─── /plan/approve ──────────────────────────────────────────────────────────

def test_plan_approve_transitions_to_clarifying(client_with_session):
    client, sid, _ = client_with_session
    client.post(f'/api/resume-copilot/sessions/{sid}/plan/start', headers=HEADERS_ALICE)
    r = client.post(f'/api/resume-copilot/sessions/{sid}/plan/approve', headers=HEADERS_ALICE)
    assert r.status_code == 200
    assert r.json()['status'] == 'clarifying'
    assert r.json()['version'] == 2  # 1 from start + 1 from approve


def test_plan_approve_rejects_when_not_awaiting(client_with_session):
    client, sid, _ = client_with_session
    client.post(f'/api/resume-copilot/sessions/{sid}/plan/start', headers=HEADERS_ALICE)
    client.post(f'/api/resume-copilot/sessions/{sid}/plan/approve', headers=HEADERS_ALICE)
    r2 = client.post(f'/api/resume-copilot/sessions/{sid}/plan/approve', headers=HEADERS_ALICE)
    assert r2.status_code == 409


# ─── /plan/actions ──────────────────────────────────────────────────────────

def _start_and_approve(client, sid) -> dict:
    client.post(f'/api/resume-copilot/sessions/{sid}/plan/start', headers=HEADERS_ALICE)
    r = client.post(f'/api/resume-copilot/sessions/{sid}/plan/approve', headers=HEADERS_ALICE)
    return r.json()


def test_action_ask_moves_item_to_clarifying(client_with_session):
    client, sid, _ = client_with_session
    plan = _start_and_approve(client, sid)
    bullet = next(it for it in plan['items']
                  if it['kind'] == 'internship' and it['parent_id'] is not None)
    r = client.post(
        f'/api/resume-copilot/sessions/{sid}/plan/actions',
        json={
            'action': 'ask',
            'item_id': bullet['id'],
            'payload': {'question_text': 'A/B 测试结果是多少?'},
            'expected_version': plan['version'],
        },
        headers=HEADERS_ALICE,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    target = next(it for it in data['items'] if it['id'] == bullet['id'])
    assert target['status'] == 'clarifying'
    assert len(target['open_questions']) == 1


def test_action_with_stale_version_returns_409(client_with_session):
    client, sid, _ = client_with_session
    plan = _start_and_approve(client, sid)
    bullet = next(it for it in plan['items'] if it['parent_id'] is not None)
    r = client.post(
        f'/api/resume-copilot/sessions/{sid}/plan/actions',
        json={
            'action': 'ask', 'item_id': bullet['id'],
            'payload': {'question_text': 'x'},
            'expected_version': 99,
        },
        headers=HEADERS_ALICE,
    )
    assert r.status_code == 409


def test_action_illegal_transition_returns_422(client_with_session):
    client, sid, _ = client_with_session
    plan = _start_and_approve(client, sid)
    item = plan['items'][0]
    # pending → finalized is illegal
    r = client.post(
        f'/api/resume-copilot/sessions/{sid}/plan/actions',
        json={'action': 'finalize', 'item_id': item['id'], 'payload': {}},
        headers=HEADERS_ALICE,
    )
    assert r.status_code == 422
    assert 'ILLEGAL_TRANSITION' in r.json()['detail']


def test_action_write_with_overclaim_returns_422_audit_payload(client_with_session):
    client, sid, _ = client_with_session
    plan = _start_and_approve(client, sid)
    item = plan['items'][0]
    # first move to ready_to_write
    client.post(
        f'/api/resume-copilot/sessions/{sid}/plan/actions',
        json={'action': 'ready_to_write', 'item_id': item['id'], 'payload': {}},
        headers=HEADERS_ALICE,
    )
    # now attempt a write with a number not in any evidence
    r = client.post(
        f'/api/resume-copilot/sessions/{sid}/plan/actions',
        json={
            'action': 'write',
            'item_id': item['id'],
            'payload': {'draft_text': '处理 999 万行数据', 'used_evidence_ids': []},
        },
        headers=HEADERS_ALICE,
    )
    assert r.status_code == 422
    body = r.json()['detail']
    assert body['code'] == 'EVIDENCE_AUDIT_FAILED'
    assert any(f['kind'] == 'overclaim' for f in body['flags'])


# ─── Persistence sanity ────────────────────────────────────────────────────

# ─── /plan/turn ─────────────────────────────────────────────────────────────

def test_plan_turn_invokes_agent_and_persists_messages(client_with_session, monkeypatch):
    client, sid, SessionLocal = client_with_session
    _start_and_approve(client, sid)

    fake_caller_calls = []

    def fake_caller(messages):
        fake_caller_calls.append(messages)
        return json.dumps({
            'action': 'ask',
            'payload': {'question_text': '你的具体角色是什么?'},
        })

    monkeypatch.setattr(
        'app.services.resume_copilot.agent.builder._default_caller',
        fake_caller,
    )

    r = client.post(
        f'/api/resume-copilot/sessions/{sid}/plan/turn',
        json={'content': '聊聊我在字节的实习'},
        headers=HEADERS_ALICE,
    )
    assert r.status_code == 200, r.text
    # plan should have advanced (one item now in clarifying)
    plan = r.json()
    assert plan['status'] == 'clarifying'
    assert any(it['status'] == 'clarifying' and it['open_questions']
               for it in plan['items'])
    # chat persisted user + assistant
    db = SessionLocal()
    try:
        from app.models import ResumeCopilotMessage
        msgs = db.query(ResumeCopilotMessage).filter_by(session_id=sid).all()
        roles = [m.role for m in msgs]
        assert 'user' in roles and 'assistant' in roles
    finally:
        db.close()
    assert len(fake_caller_calls) == 1


def test_plan_turn_404_when_no_plan(client_with_session):
    client, sid, _ = client_with_session
    r = client.post(
        f'/api/resume-copilot/sessions/{sid}/plan/turn',
        json={'content': 'x'},
        headers=HEADERS_ALICE,
    )
    assert r.status_code == 404


def test_plan_status_column_reflects_state(client_with_session):
    client, sid, SessionLocal = client_with_session
    client.post(f'/api/resume-copilot/sessions/{sid}/plan/start', headers=HEADERS_ALICE)
    db = SessionLocal()
    try:
        s = db.query(ResumeCopilotSession).filter_by(id=sid).first()
        assert s.plan_status == 'awaiting_plan_approval'
        assert s.plan_json is not None
    finally:
        db.close()
    client.post(f'/api/resume-copilot/sessions/{sid}/plan/approve', headers=HEADERS_ALICE)
    db = SessionLocal()
    try:
        s = db.query(ResumeCopilotSession).filter_by(id=sid).first()
        assert s.plan_status == 'clarifying'
    finally:
        db.close()
