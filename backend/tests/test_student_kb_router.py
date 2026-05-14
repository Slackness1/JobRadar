"""API tests for /api/student-kb router."""
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import StudentExperience


@pytest.fixture
def client():
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def _override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app), factory
    app.dependency_overrides.clear()


def _seed_experience(factory, *, user_key='alice', summary='大三组织 50 人产品发布会',
                     dimensions=None, confirmed=False, archived=False, category='experience'):
    if dimensions is None:
        dimensions = ['leadership', 'cross_functional']
    db = factory()
    row = StudentExperience(
        user_key=user_key,
        source_session_id=None,
        name=summary[:20],
        summary=summary,
        summary_hash=f'h_{abs(hash((user_key, summary))) % 10**12}',
        category=category,
        star_dimensions_json=json.dumps(dimensions, ensure_ascii=False),
        behavioral_hook='S=...|T=...|A=...|R=...',
        quantified_json=json.dumps({'team_size': 50}, ensure_ascii=False),
        raw_excerpt='我大三时组织过一次 50 人',
        confidence=0.7,
        user_confirmed=confirmed,
        has_temporal_anchor=True,
        has_concrete_action=True,
        has_outcome=True,
        captured_at=datetime.utcnow(),
        last_verified_at=datetime.utcnow(),
        is_archived=archived,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    rid = int(row.id)
    db.close()
    return rid


def test_index_requires_auth(client):
    c, _ = client
    r = c.get('/api/student-kb/index')
    assert r.status_code == 401


def test_index_rejects_demo_user_key(client):
    c, _ = client
    r = c.get('/api/student-kb/index', headers={'X-Resume-User-Key': '__demo__'})
    assert r.status_code == 401


def test_index_rejects_guest_user_key(client):
    c, _ = client
    r = c.get('/api/student-kb/index', headers={'X-Resume-User-Key': '__guest__'})
    assert r.status_code == 401


def test_index_returns_only_own_rows(client):
    c, factory = client
    _seed_experience(factory, user_key='alice', summary='alice item')
    _seed_experience(factory, user_key='bob', summary='bob item')

    r = c.get('/api/student-kb/index', headers={'X-Resume-User-Key': 'alice'})
    assert r.status_code == 200
    data = r.json()
    assert data['total'] == 1
    assert data['items'][0]['summary'] == 'alice item'
    assert data['pending_confirm_count'] == 1


def test_index_hides_archived_by_default(client):
    c, factory = client
    _seed_experience(factory, user_key='alice', summary='active item')
    _seed_experience(factory, user_key='alice', summary='archived item', archived=True)

    r = c.get('/api/student-kb/index', headers={'X-Resume-User-Key': 'alice'})
    assert r.status_code == 200
    summaries = [it['summary'] for it in r.json()['items']]
    assert summaries == ['active item']

    r2 = c.get(
        '/api/student-kb/index?include_archived=true',
        headers={'X-Resume-User-Key': 'alice'},
    )
    assert r2.status_code == 200
    assert len(r2.json()['items']) == 2


def test_list_filter_by_dimension(client):
    c, factory = client
    _seed_experience(factory, user_key='alice', summary='lead item', dimensions=['leadership'])
    _seed_experience(factory, user_key='alice', summary='team item', dimensions=['teamwork'])

    r = c.get(
        '/api/student-kb/experiences?dimension=leadership',
        headers={'X-Resume-User-Key': 'alice'},
    )
    assert r.status_code == 200
    items = r.json()['items']
    assert len(items) == 1
    assert items[0]['summary'] == 'lead item'


def test_list_filter_by_category(client):
    c, factory = client
    _seed_experience(factory, user_key='alice', summary='exp', category='experience')
    _seed_experience(factory, user_key='alice', summary='pref', category='preference', dimensions=[])

    r = c.get(
        '/api/student-kb/experiences?category=preference',
        headers={'X-Resume-User-Key': 'alice'},
    )
    assert r.status_code == 200
    assert len(r.json()['items']) == 1
    assert r.json()['items'][0]['summary'] == 'pref'


def test_confirm_flips_user_confirmed(client):
    c, factory = client
    exp_id = _seed_experience(factory, user_key='alice')

    r = c.post(
        f'/api/student-kb/experiences/{exp_id}/confirm',
        headers={'X-Resume-User-Key': 'alice'},
    )
    assert r.status_code == 200
    assert r.json()['user_confirmed'] is True


def test_cannot_confirm_others_experience(client):
    c, factory = client
    bob_id = _seed_experience(factory, user_key='bob')

    r = c.post(
        f'/api/student-kb/experiences/{bob_id}/confirm',
        headers={'X-Resume-User-Key': 'alice'},
    )
    assert r.status_code == 403


def test_patch_edits_fields(client):
    c, factory = client
    exp_id = _seed_experience(factory, user_key='alice')

    r = c.patch(
        f'/api/student-kb/experiences/{exp_id}',
        json={'summary': '改后的摘要', 'star_dimensions': ['planning', 'initiative']},
        headers={'X-Resume-User-Key': 'alice'},
    )
    assert r.status_code == 200
    out = r.json()
    assert out['summary'] == '改后的摘要'
    assert sorted(out['star_dimensions']) == ['initiative', 'planning']
    # patch should auto-confirm.
    assert out['user_confirmed'] is True


def test_archive_hides_from_index(client):
    c, factory = client
    exp_id = _seed_experience(factory, user_key='alice')

    r = c.post(
        f'/api/student-kb/experiences/{exp_id}/archive',
        headers={'X-Resume-User-Key': 'alice'},
    )
    assert r.status_code == 200
    assert r.json()['is_archived'] is True

    idx = c.get('/api/student-kb/index', headers={'X-Resume-User-Key': 'alice'})
    assert idx.json()['total'] == 0


def test_delete_removes_row(client):
    c, factory = client
    exp_id = _seed_experience(factory, user_key='alice')

    r = c.delete(
        f'/api/student-kb/experiences/{exp_id}',
        headers={'X-Resume-User-Key': 'alice'},
    )
    assert r.status_code == 204

    idx = c.get('/api/student-kb/index', headers={'X-Resume-User-Key': 'alice'})
    assert idx.json()['total'] == 0
