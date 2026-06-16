from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import JobUserState


def _mk_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_unique_user_job():
    db = _mk_session()
    db.add(JobUserState(user_key="u_5", job_id="j1", state="seen"))
    db.commit()
    db.add(JobUserState(user_key="u_5", job_id="j1", state="saved"))
    with pytest.raises(IntegrityError):
        db.commit()
