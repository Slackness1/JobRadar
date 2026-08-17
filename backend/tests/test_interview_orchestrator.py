import json
from unittest.mock import MagicMock

from app.models import InterviewTurn
from app.services.interview.orchestrator import process_turn_synchronous
from tests._threadsafe_db import make_threadsafe_sessionmaker


def _make_db():
    return make_threadsafe_sessionmaker("jobradar-orch-test-")


def _stub_llm():
    llm = MagicMock()
    llm.chat_json.return_value = {"overall": 70, "hits": ["a"], "misses": ["b"], "bonuses": []}
    llm.chat_text.return_value = "示例答案段落"
    return llm


def test_process_turn_inserts_user_answer_into_existing_turn_row():
    SessionLocal = _make_db()
    db = SessionLocal()
    db.add(InterviewTurn(
        session_id="s1", user_key="u1", turn_index=0, target_job="x",
        question="Q0", question_source="skeleton",
    ))
    db.commit()
    db.close()

    process_turn_synchronous(
        session_id="s1",
        user_key="u1",
        target_job="x",
        chip="default",
        chip_summary="...",
        prev_turn_index=0,
        prev_user_answer="A0",
        prev_asr_transcript={},
        next_turn_index=1,
        session_factory=SessionLocal,
        llm=_stub_llm(),
    )

    db = SessionLocal()
    try:
        turn0 = db.query(InterviewTurn).filter_by(session_id="s1", turn_index=0).one()
        assert turn0.user_answer == "A0"
        # Background tasks completed synchronously (process_turn_synchronous uses
        # an in-process pool that we wait on)
        assert turn0.score_json is not None
        score = json.loads(turn0.score_json)
        assert score["overall"] == 70
        assert turn0.reference_answer == "示例答案段落"
    finally:
        db.close()


def test_process_turn_inserts_next_question_row():
    SessionLocal = _make_db()
    db = SessionLocal()
    db.add(InterviewTurn(
        session_id="s2", user_key="u1", turn_index=0, target_job="x",
        question="Q0", question_source="skeleton",
    ))
    db.commit()
    db.close()

    next_q = process_turn_synchronous(
        session_id="s2", user_key="u1", target_job="x",
        chip="default", chip_summary="...",
        prev_turn_index=0, prev_user_answer="A0", prev_asr_transcript={},
        next_turn_index=1,
        session_factory=SessionLocal, llm=_stub_llm(),
    )

    db = SessionLocal()
    try:
        turn1 = db.query(InterviewTurn).filter_by(session_id="s2", turn_index=1).one()
        assert turn1.question == next_q.question
        assert turn1.user_answer == ""
    finally:
        db.close()


def test_process_turn_writes_voice_metrics_when_asr_available():
    SessionLocal = _make_db()
    db = SessionLocal()
    db.add(InterviewTurn(
        session_id="s3", user_key="u1", turn_index=0, target_job="x",
        question="Q0",
    ))
    db.commit()
    db.close()

    asr = {
        "audio_duration_s": 10.0,
        "segments": [{"start_s": 0.5, "end_s": 9.0, "text": "嗯 我做过一个项目 那个 主要是用户增长"}],
    }
    process_turn_synchronous(
        session_id="s3", user_key="u1", target_job="x",
        chip="default", chip_summary="...",
        prev_turn_index=0, prev_user_answer="ans",
        prev_asr_transcript=asr,
        next_turn_index=1,
        session_factory=SessionLocal, llm=_stub_llm(),
    )

    db = SessionLocal()
    try:
        turn0 = db.query(InterviewTurn).filter_by(session_id="s3", turn_index=0).one()
        assert turn0.voice_metrics is not None
        vm = json.loads(turn0.voice_metrics)
        assert vm["filler_rate"] is not None
    finally:
        db.close()


def test_process_turn_skips_voice_metrics_when_no_asr():
    SessionLocal = _make_db()
    db = SessionLocal()
    db.add(InterviewTurn(session_id="s4", user_key="u1", turn_index=0, target_job="x", question="Q0"))
    db.commit()
    db.close()

    process_turn_synchronous(
        session_id="s4", user_key="u1", target_job="x",
        chip="default", chip_summary="...",
        prev_turn_index=0, prev_user_answer="text mode answer",
        prev_asr_transcript={},  # text mode
        next_turn_index=1,
        session_factory=SessionLocal, llm=_stub_llm(),
    )

    db = SessionLocal()
    try:
        turn0 = db.query(InterviewTurn).filter_by(session_id="s4", turn_index=0).one()
        # voice_metrics may be null OR a metrics dict with all-None deterministic fields;
        # accept either as "no signal"
        if turn0.voice_metrics:
            vm = json.loads(turn0.voice_metrics)
            assert vm["wpm"] is None or vm["wpm"] == 0
    finally:
        db.close()


def test_process_turn_does_not_raise_on_llm_failure():
    SessionLocal = _make_db()
    db = SessionLocal()
    db.add(InterviewTurn(session_id="s5", user_key="u1", turn_index=0, target_job="x", question="Q0"))
    db.commit()
    db.close()

    bad_llm = MagicMock()
    bad_llm.chat_json.side_effect = RuntimeError("down")
    bad_llm.chat_text.side_effect = RuntimeError("down")

    # Must not raise
    process_turn_synchronous(
        session_id="s5", user_key="u1", target_job="x",
        chip="default", chip_summary="...",
        prev_turn_index=0, prev_user_answer="ans", prev_asr_transcript={},
        next_turn_index=1,
        session_factory=SessionLocal, llm=bad_llm,
    )

    db = SessionLocal()
    try:
        turn0 = db.query(InterviewTurn).filter_by(session_id="s5", turn_index=0).one()
        assert turn0.score_json is None or json.loads(turn0.score_json)["overall"] is None
        assert turn0.reference_answer == ""
    finally:
        db.close()
