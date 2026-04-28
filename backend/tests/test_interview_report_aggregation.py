import json
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import InterviewTurn
from app.services.interview.report import build_report_aggregate


def _make_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _seed_turns(SessionLocal, session_id, user_key, count=3):
    db = SessionLocal()
    for i in range(count):
        db.add(InterviewTurn(
            session_id=session_id,
            user_key=user_key,
            turn_index=i,
            target_job="数据分析师",
            question=f"Q{i}",
            user_answer=f"A{i}",
            score_json=json.dumps({
                "overall": 60 + i * 10,
                "hits": ["量化"] if i > 0 else [],
                "misses": ["STAR 结构"],
                "bonuses": [],
            }),
        ))
    db.commit()
    db.close()


def test_build_report_aggregate_includes_turn_count_and_weakness_profile():
    SessionLocal = _make_db()
    _seed_turns(SessionLocal, "s1", "u1", count=3)

    llm = MagicMock()
    llm.chat_text.return_value = "你的整体表现尚可，**主要短板**是 STAR 结构。建议..."

    db = SessionLocal()
    try:
        result = build_report_aggregate(
            session_id="s1",
            target_job="数据分析师",
            db=db,
            llm=llm,
        )
    finally:
        db.close()

    assert result["turn_count"] == 3
    assert result["weakness_profile"]["avg_score"] == 70  # avg(60, 70, 80)
    assert "STAR 结构" in result["weakness_profile"]["weak_topics"]
    assert "STAR" in result["weekly_plan_md"]


def test_weekly_plan_falls_back_when_llm_fails():
    SessionLocal = _make_db()
    _seed_turns(SessionLocal, "s2", "u1", count=2)

    llm = MagicMock()
    llm.chat_text.side_effect = RuntimeError("network down")

    db = SessionLocal()
    try:
        result = build_report_aggregate(
            session_id="s2", target_job="x", db=db, llm=llm,
        )
    finally:
        db.close()

    assert result["weekly_plan_md"]  # non-empty (generic fallback)
    assert "建议" in result["weekly_plan_md"]


def test_build_report_aggregate_empty_session_returns_zeros():
    SessionLocal = _make_db()
    db = SessionLocal()
    try:
        result = build_report_aggregate(
            session_id="empty", target_job="x", db=db, llm=MagicMock(),
        )
    finally:
        db.close()
    assert result["turn_count"] == 0
    assert result["weakness_profile"]["avg_score"] is None
