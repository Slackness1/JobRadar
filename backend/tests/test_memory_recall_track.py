"""B1 记忆召回 — 赛道上下文加权 (账号级事实按当前简历目标排序)。"""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AccountMemory
from app.services.memory.api_helpers import relevant_memory_for_bullet


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _mk(db, user_key, summary, summary_hash, linked_track='', conf=0.9):
    row = AccountMemory(
        user_key=user_key, category='experience', summary=summary,
        raw_excerpt=summary, payload_json='{}', summary_hash=summary_hash,
        confidence=conf, captured_at=datetime.utcnow(), use_count=0,
        is_archived=False, linked_track=linked_track,
    )
    db.add(row)
    db.commit()
    return row


def test_matching_track_ranks_higher(db_session):
    uk = 'u_9001'
    # 两行对 bullet 的字面 overlap 接近,只差 linked_track
    _mk(db_session, uk, '量化因子开发 回测 alpha', 'h1', linked_track='')
    _mk(db_session, uk, '量化因子开发 回测 alpha', 'h2', linked_track='量化')
    out = relevant_memory_for_bullet(
        db_session, user_key=uk, bullet_text='量化因子开发 回测 alpha',
        k=2, target_track='量化',
    )
    assert out[0]['linked_track'] == '量化'   # 赛道匹配的排第一


def test_no_target_track_is_backward_compatible(db_session):
    uk = 'u_9002'
    _mk(db_session, uk, '量化因子开发 回测 alpha', 'h3', linked_track='量化')
    out = relevant_memory_for_bullet(
        db_session, user_key=uk, bullet_text='量化因子开发 回测 alpha', k=2,
    )
    assert len(out) >= 1   # 不传 target_track 行为不变,正常召回
