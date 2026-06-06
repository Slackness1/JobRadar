"""统一决策事件埋点 (decision_events) — 写入函数 + 聚合查询的单测。

设计契约 (见 app/services/telemetry/decision_events.py):
  - record_event 永不 raise (best-effort), 失败返回 False
  - 自开短生命周期 session, 不碰调用方事务
  - event_counts 一句聚合, 回答"哪个分支真在触发"
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import DecisionEvent
from app.services.telemetry import event_counts, record_event


def _factory(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'tele.db'}")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)


def test_record_event_writes_row(tmp_path):
    Sess = _factory(tmp_path)
    ok = record_event(
        "recall_thin",
        session_id=42,
        purpose="recommendation",
        hit=True,
        detail={"count": 3},
        session_factory=Sess,
    )
    assert ok is True
    s = Sess()
    try:
        rows = s.query(DecisionEvent).all()
        assert len(rows) == 1
        assert rows[0].event_name == "recall_thin"
        assert rows[0].session_id == 42
        assert rows[0].purpose == "recommendation"
        assert rows[0].hit is True
        assert '"count": 3' in rows[0].detail_json
    finally:
        s.close()


def test_record_event_never_raises_on_bad_factory():
    """factory 抛错 → 不传播, 返回 False (埋点失败绝不拖垮主流程)."""
    def boom():
        raise RuntimeError("db down")

    assert record_event("x", session_factory=boom) is False


def test_event_counts_aggregates(tmp_path):
    Sess = _factory(tmp_path)
    record_event("canonicalize_unmapped", session_factory=Sess)
    record_event("canonicalize_unmapped", session_factory=Sess)
    record_event("recall_empty", session_factory=Sess)
    counts = event_counts(session_factory=Sess)
    assert counts["canonicalize_unmapped"] == 2
    assert counts["recall_empty"] == 1
