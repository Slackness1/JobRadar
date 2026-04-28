"""Tests for Resume Copilot session retention cleanup."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ResumeCopilotSession
from app.services.resume_copilot.retention import cleanup_expired_sessions


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


def test_cleanup_deletes_only_expired_sessions(db):
    now = datetime.utcnow()
    db.add(ResumeCopilotSession(
        name='expired-1', user_key='u1', is_guest=0,
        status='completed', expires_at=now - timedelta(hours=1),
    ))
    db.add(ResumeCopilotSession(
        name='live-1', user_key='u1', is_guest=0,
        status='completed', expires_at=now + timedelta(days=3),
    ))
    db.add(ResumeCopilotSession(
        name='no-expiry', user_key='u1', is_guest=0,
        status='completed', expires_at=None,
    ))
    db.commit()

    deleted = cleanup_expired_sessions(db)

    assert deleted == 1
    remaining_names = {s.name for s in db.query(ResumeCopilotSession).all()}
    assert remaining_names == {'live-1', 'no-expiry'}


def test_cleanup_skips_demo_session(db):
    now = datetime.utcnow()
    db.add(ResumeCopilotSession(
        name='demo', user_key='__demo__', is_guest=0,
        status='completed', expires_at=now - timedelta(hours=1),
    ))
    db.commit()

    deleted = cleanup_expired_sessions(db)

    assert deleted == 0
    assert db.query(ResumeCopilotSession).count() == 1
