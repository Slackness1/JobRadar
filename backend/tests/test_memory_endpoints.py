"""End-to-end tests for the memory CRUD endpoints.

Covers:
- POST  /sessions/{id}/memory               — create (Phase 0)
- GET   /sessions/{id}/memory               — list grouped by category (Phase 0)
- PATCH /sessions/{id}/memory/{entry_id}    — A-3 简: edit summary + payload
- DELETE /sessions/{id}/memory/{entry_id}   — A-3 简: soft-delete (is_archived)

Guards exercised:
- demo session (user_key == '__demo__') → 403 on PATCH/DELETE
- cross-session/cross-user_key id-guess → 404 (never leak existence)
- empty body / bad payload schema       → 422
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import AccountMemory, ResumeCopilotSession


def _build_client(user_key: str = 'real_user_alpha'):
    """Fresh in-memory DB + FastAPI app wired to the memory router.

    Returns (client, session_factory, helper_for_seed_session).
    """
    from app.routers import resume_copilot

    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    app = FastAPI()
    app.include_router(resume_copilot.router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    client.headers.update({'X-Resume-User-Key': user_key})
    return client, TestingSessionLocal


def _seed_session(SessionLocal, user_key: str) -> int:
    db = SessionLocal()
    s = ResumeCopilotSession(file_name='cv.pdf', user_key=user_key, status='completed')
    db.add(s)
    db.commit()
    db.refresh(s)
    sid = int(s.id)
    db.close()
    return sid


def _create_entry(client, session_id: int, **overrides) -> dict:
    """Helper: POST one preference row (simplest payload to construct)."""
    body = {
        'category': 'preference',
        'summary': '只想去上海',
        'payload': {'dimension': 'city', 'value': '上海'},
        'confidence': 0.95,
        'raw_excerpt': '我只想去上海',
    }
    body.update(overrides)
    r = client.post(f'/api/resume-copilot/sessions/{session_id}/memory', json=body)
    assert r.status_code == 201, r.text
    return r.json()


# ════════════════════════════════════════════════════════════════════════════
# POST + GET (Phase 0 sanity — needed as setup for PATCH/DELETE)
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _enable_memory_flag(monkeypatch):
    """Phase 0 flipped UNIFIED_MEMORY_ENABLED ON by default, but dispatcher
    captures it at module-import time — patch the *bound* name so tests are
    independent of the env at the host's import time."""
    monkeypatch.setattr('app.services.memory.dispatcher.UNIFIED_MEMORY_ENABLED', True)


def test_post_then_get_round_trip():
    client, SessionLocal = _build_client()
    sid = _seed_session(SessionLocal, 'real_user_alpha')

    entry = _create_entry(client, sid)
    assert entry['category'] == 'preference'
    assert entry['payload'] == {'dimension': 'city', 'value': '上海'}
    assert entry['is_archived'] is False

    r = client.get(f'/api/resume-copilot/sessions/{sid}/memory')
    assert r.status_code == 200
    data = r.json()
    prefs = data['entries']['preference']
    assert len(prefs) == 1
    assert prefs[0]['id'] == entry['id']


# ════════════════════════════════════════════════════════════════════════════
# PATCH happy path (A-3 简)
# ════════════════════════════════════════════════════════════════════════════


def test_patch_updates_summary_only():
    client, SessionLocal = _build_client()
    sid = _seed_session(SessionLocal, 'real_user_alpha')
    entry = _create_entry(client, sid)

    r = client.patch(
        f'/api/resume-copilot/sessions/{sid}/memory/{entry["id"]}',
        json={'summary': '只想去北上深'},
    )
    assert r.status_code == 200, r.text
    patched = r.json()
    assert patched['summary'] == '只想去北上深'
    # payload untouched
    assert patched['payload'] == {'dimension': 'city', 'value': '上海'}

    # GET reflects the update
    listed = client.get(f'/api/resume-copilot/sessions/{sid}/memory').json()
    prefs = listed['entries']['preference']
    assert len(prefs) == 1
    assert prefs[0]['summary'] == '只想去北上深'


def test_patch_updates_payload_only():
    client, SessionLocal = _build_client()
    sid = _seed_session(SessionLocal, 'real_user_alpha')
    entry = _create_entry(client, sid)

    r = client.patch(
        f'/api/resume-copilot/sessions/{sid}/memory/{entry["id"]}',
        json={'payload': {'dimension': 'city', 'value': '深圳'}},
    )
    assert r.status_code == 200, r.text
    patched = r.json()
    assert patched['payload'] == {'dimension': 'city', 'value': '深圳'}
    # summary untouched
    assert patched['summary'] == '只想去上海'


def test_patch_updates_both():
    client, SessionLocal = _build_client()
    sid = _seed_session(SessionLocal, 'real_user_alpha')
    entry = _create_entry(client, sid)

    r = client.patch(
        f'/api/resume-copilot/sessions/{sid}/memory/{entry["id"]}',
        json={
            'summary': '想去深圳',
            'payload': {'dimension': 'city', 'value': '深圳'},
        },
    )
    assert r.status_code == 200, r.text
    patched = r.json()
    assert patched['summary'] == '想去深圳'
    assert patched['payload']['value'] == '深圳'


# ════════════════════════════════════════════════════════════════════════════
# PATCH guards (422 / 403 / 404)
# ════════════════════════════════════════════════════════════════════════════


def test_patch_empty_body_returns_422():
    client, SessionLocal = _build_client()
    sid = _seed_session(SessionLocal, 'real_user_alpha')
    entry = _create_entry(client, sid)

    r = client.patch(
        f'/api/resume-copilot/sessions/{sid}/memory/{entry["id"]}',
        json={},
    )
    assert r.status_code == 422


def test_patch_empty_summary_returns_422():
    client, SessionLocal = _build_client()
    sid = _seed_session(SessionLocal, 'real_user_alpha')
    entry = _create_entry(client, sid)

    r = client.patch(
        f'/api/resume-copilot/sessions/{sid}/memory/{entry["id"]}',
        json={'summary': '   '},
    )
    assert r.status_code == 422


def test_patch_invalid_payload_schema_returns_422():
    """preference.dimension must be one of the literal enum values; otherwise
    pydantic rejects."""
    client, SessionLocal = _build_client()
    sid = _seed_session(SessionLocal, 'real_user_alpha')
    entry = _create_entry(client, sid)

    r = client.patch(
        f'/api/resume-copilot/sessions/{sid}/memory/{entry["id"]}',
        json={'payload': {'dimension': 'not_a_real_dim', 'value': 'x'}},
    )
    assert r.status_code == 422


def test_patch_demo_session_returns_403():
    client, SessionLocal = _build_client(user_key='__demo__')
    sid = _seed_session(SessionLocal, '__demo__')

    # We can't POST first (demo blocks writes), so seed the row directly.
    db = SessionLocal()
    row = AccountMemory(
        user_key='__demo__',
        category='preference',
        summary='demo entry',
        payload_json='{"dimension":"city","value":"上海"}',
        summary_hash='demohash_001',
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    rid = int(row.id)
    db.close()

    r = client.patch(
        f'/api/resume-copilot/sessions/{sid}/memory/{rid}',
        json={'summary': '改一下'},
    )
    assert r.status_code == 403


def test_patch_cross_user_entry_returns_404():
    """User B tries to PATCH user A's entry by id — must 404, not 403.
    Never confirm an entry exists if it belongs to someone else."""
    client_a, SessionLocal = _build_client(user_key='user_a')
    sid_a = _seed_session(SessionLocal, 'user_a')
    entry_a = _create_entry(client_a, sid_a)

    # Create a separate session owned by user_b on the SAME DB.
    db = SessionLocal()
    sb = ResumeCopilotSession(
        file_name='b.pdf', user_key='user_b', status='completed',
    )
    db.add(sb)
    db.commit()
    db.refresh(sb)
    sid_b = int(sb.id)
    db.close()

    # Build a second client with user_b's header pointing at the same app.
    client_a.headers.update({'X-Resume-User-Key': 'user_b'})
    r = client_a.patch(
        f'/api/resume-copilot/sessions/{sid_b}/memory/{entry_a["id"]}',
        json={'summary': '试图越权'},
    )
    assert r.status_code == 404


def test_patch_unknown_entry_id_returns_404():
    client, SessionLocal = _build_client()
    sid = _seed_session(SessionLocal, 'real_user_alpha')

    r = client.patch(
        f'/api/resume-copilot/sessions/{sid}/memory/99999',
        json={'summary': '不存在的'},
    )
    assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════════════
# DELETE
# ════════════════════════════════════════════════════════════════════════════


def test_delete_soft_archives_and_hides_from_get():
    client, SessionLocal = _build_client()
    sid = _seed_session(SessionLocal, 'real_user_alpha')
    entry = _create_entry(client, sid)

    r = client.delete(f'/api/resume-copilot/sessions/{sid}/memory/{entry["id"]}')
    assert r.status_code == 204

    # GET no longer returns it
    listed = client.get(f'/api/resume-copilot/sessions/{sid}/memory').json()
    assert listed['entries']['preference'] == []

    # …but the row still exists in DB with is_archived=True (soft-delete invariant)
    db = SessionLocal()
    row = db.query(AccountMemory).filter(AccountMemory.id == entry['id']).one()
    assert row.is_archived is True
    db.close()


def test_delete_is_idempotent():
    client, SessionLocal = _build_client()
    sid = _seed_session(SessionLocal, 'real_user_alpha')
    entry = _create_entry(client, sid)

    r1 = client.delete(f'/api/resume-copilot/sessions/{sid}/memory/{entry["id"]}')
    assert r1.status_code == 204
    r2 = client.delete(f'/api/resume-copilot/sessions/{sid}/memory/{entry["id"]}')
    assert r2.status_code == 204


def test_delete_demo_session_returns_403():
    client, SessionLocal = _build_client(user_key='__demo__')
    sid = _seed_session(SessionLocal, '__demo__')

    db = SessionLocal()
    row = AccountMemory(
        user_key='__demo__',
        category='preference',
        summary='demo entry',
        payload_json='{"dimension":"city","value":"上海"}',
        summary_hash='demohash_del_001',
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    rid = int(row.id)
    db.close()

    r = client.delete(f'/api/resume-copilot/sessions/{sid}/memory/{rid}')
    assert r.status_code == 403


def test_delete_cross_user_entry_returns_404():
    client_a, SessionLocal = _build_client(user_key='user_a')
    sid_a = _seed_session(SessionLocal, 'user_a')
    entry_a = _create_entry(client_a, sid_a)

    db = SessionLocal()
    sb = ResumeCopilotSession(
        file_name='b.pdf', user_key='user_b', status='completed',
    )
    db.add(sb)
    db.commit()
    db.refresh(sb)
    sid_b = int(sb.id)
    db.close()

    client_a.headers.update({'X-Resume-User-Key': 'user_b'})
    r = client_a.delete(
        f'/api/resume-copilot/sessions/{sid_b}/memory/{entry_a["id"]}',
    )
    assert r.status_code == 404


def test_delete_unknown_entry_id_returns_404():
    client, SessionLocal = _build_client()
    sid = _seed_session(SessionLocal, 'real_user_alpha')

    r = client.delete(f'/api/resume-copilot/sessions/{sid}/memory/99999')
    assert r.status_code == 404
