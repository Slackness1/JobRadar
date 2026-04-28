"""Per-turn orchestrator.

`process_turn_synchronous` is the testable form: it runs scoring / reference /
voice metrics in parallel via ThreadPoolExecutor, blocks until all three
complete, then picks + persists the next question and returns it.

The streaming SSE wrapper in routers/interview.py wraps this — it kicks off
process_turn_synchronous, then streams the next question text back to the
client. Live polling (separate endpoint) reads the score row whenever it's
ready.

Each parallel task opens its own SessionLocal (Q5 hardening: never share a
db session across threads).
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Callable

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import InterviewTurn
from app.services.interview.adaptive import (
    NextQuestion,
    SKELETON_QUESTIONS,
    generate_followup_question,
    pick_next_question,
)
from app.services.interview.llm_helpers import InterviewLLMClient
from app.services.interview.reference_answer import generate_reference
from app.services.interview.scoring import ScoreResult, score_answer
from app.services.interview.voice_metrics import (
    VoiceMetrics,
    compute_voice_metrics,
    score_confidence_from_transcript,
)
from app.services.interview.weakness_profile import compute_weakness

logger = logging.getLogger(__name__)


def _score_task(
    session_factory: Callable[[], Session],
    session_id: str,
    turn_index: int,
    target_job: str,
    question: str,
    user_answer: str,
    chip_summary: str,
    llm: InterviewLLMClient,
) -> None:
    db = session_factory()
    try:
        result: ScoreResult = score_answer(
            target_job=target_job,
            question=question,
            user_answer=user_answer,
            chip_summary=chip_summary,
            llm=llm,
        )
        if result.overall is None and not result.hits and not result.misses:
            return  # leave score_json null
        row = db.query(InterviewTurn).filter_by(
            session_id=session_id, turn_index=turn_index,
        ).one_or_none()
        if row is not None:
            row.score_json = result.to_json()
            db.commit()
    except Exception as exc:
        logger.warning("score_task failed: %s", exc)
        db.rollback()
    finally:
        db.close()


def _reference_task(
    session_factory: Callable[[], Session],
    session_id: str,
    turn_index: int,
    target_job: str,
    question: str,
    chip_summary: str,
    candidate_summary: str,
    llm: InterviewLLMClient,
) -> None:
    db = session_factory()
    try:
        text = generate_reference(
            target_job=target_job,
            question=question,
            chip_summary=chip_summary,
            candidate_summary=candidate_summary,
            llm=llm,
        )
        if not text:
            return
        row = db.query(InterviewTurn).filter_by(
            session_id=session_id, turn_index=turn_index,
        ).one_or_none()
        if row is not None:
            row.reference_answer = text
            db.commit()
    except Exception as exc:
        logger.warning("reference_task failed: %s", exc)
        db.rollback()
    finally:
        db.close()


def _voice_task(
    session_factory: Callable[[], Session],
    session_id: str,
    turn_index: int,
    asr_transcript: dict,
    llm: InterviewLLMClient,
) -> None:
    db = session_factory()
    try:
        if not asr_transcript:
            return
        metrics = compute_voice_metrics(asr_transcript)
        # confidence sub-call (LLM); failure → leaves field null
        if metrics.wpm is not None:
            metrics.confidence_score = score_confidence_from_transcript(
                asr_transcript, metrics, llm=llm,
            )
        row = db.query(InterviewTurn).filter_by(
            session_id=session_id, turn_index=turn_index,
        ).one_or_none()
        if row is not None:
            row.voice_metrics = metrics.to_json()
            db.commit()
    except Exception as exc:
        logger.warning("voice_task failed: %s", exc)
        db.rollback()
    finally:
        db.close()


def process_turn_synchronous(
    session_id: str,
    user_key: str,
    target_job: str,
    chip: str,
    chip_summary: str,
    prev_turn_index: int,
    prev_user_answer: str,
    prev_asr_transcript: dict,
    next_turn_index: int,
    session_factory: Callable[[], Session] = SessionLocal,
    llm: InterviewLLMClient | None = None,
    candidate_summary: str = "",
) -> NextQuestion:
    """Process one full turn cycle.

    1. Save prev_user_answer + asr to the existing prev_turn_index row.
    2. Fan out 3 parallel tasks (score / reference / voice metrics).
    3. Wait for all 3 to complete.
    4. Compute weakness profile from all turns so far.
    5. Pick next question.
    6. Insert next_turn_index row with just the question.
    7. Return NextQuestion (caller streams to client).
    """
    if llm is None:
        from app.services.interview.llm_helpers import build_interview_llm_client
        llm = build_interview_llm_client()

    # Step 1: persist user answer to current turn row
    db = session_factory()
    try:
        prev_row = db.query(InterviewTurn).filter_by(
            session_id=session_id, turn_index=prev_turn_index,
        ).one_or_none()
        prev_question = ""
        if prev_row is not None:
            prev_row.user_answer = prev_user_answer
            import json as _json
            prev_row.asr_transcript = _json.dumps(prev_asr_transcript, ensure_ascii=False) if prev_asr_transcript else ""
            prev_question = str(prev_row.question or "")
            db.commit()
    finally:
        db.close()

    # Step 2-3: parallel fan-out
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [
            pool.submit(
                _score_task, session_factory, session_id, prev_turn_index,
                target_job, prev_question, prev_user_answer, chip_summary, llm,
            ),
            pool.submit(
                _reference_task, session_factory, session_id, prev_turn_index,
                target_job, prev_question, chip_summary, candidate_summary, llm,
            ),
            pool.submit(
                _voice_task, session_factory, session_id, prev_turn_index,
                prev_asr_transcript, llm,
            ),
        ]
        wait(futures, timeout=30)
        # Surface any unexpected exceptions to logs (not propagated)
        for f in futures:
            try:
                f.result(timeout=0.1)
            except Exception as exc:
                logger.warning("parallel turn task raised: %s", exc)

    # Step 4: weakness profile from all turns so far + decide branch
    db = session_factory()
    try:
        all_turns = (
            db.query(InterviewTurn)
            .filter(InterviewTurn.session_id == session_id)
            .order_by(InterviewTurn.turn_index)
            .all()
        )
        score_jsons = [t.score_json for t in all_turns]
        weakness = compute_weakness(score_jsons)
        asked = [str(t.question or "") for t in all_turns if t.question]

        # Identify the current main question (skeleton turn this thread belongs to).
        # The just-answered turn (prev_turn_index) is either skeleton itself or a follow-up.
        prev_turn = next((t for t in all_turns if t.turn_index == prev_turn_index), None)
        if prev_turn is None:
            current_main_index = None
        elif prev_turn.question_source == "skeleton":
            current_main_index = int(prev_turn.turn_index)
        else:
            current_main_index = (
                int(prev_turn.parent_turn_index)
                if prev_turn.parent_turn_index is not None
                else None
            )

        # How many follow-ups already exist under this main question.
        followups_under_current = sum(
            1 for t in all_turns
            if t.parent_turn_index is not None and int(t.parent_turn_index) == current_main_index
        )

        # How many skeleton turns asked so far → next skeleton index.
        skeleton_count = sum(1 for t in all_turns if t.question_source == "skeleton")
        skeleton_list = SKELETON_QUESTIONS.get(chip) or SKELETON_QUESTIONS["default"]

        # Latest score for the just-answered turn — used to decide drill vs advance.
        prev_score: dict | None = None
        if prev_turn is not None and prev_turn.score_json:
            try:
                import json as _json
                prev_score = _json.loads(prev_turn.score_json)
            except Exception:
                prev_score = None
    finally:
        db.close()

    # Step 5: decide follow-up vs advance vs final fallback
    should_follow_up = (
        current_main_index is not None
        and followups_under_current < 2
        and prev_score is not None
        and (
            (
                prev_score.get("overall") is not None
                and isinstance(prev_score["overall"], (int, float))
                and prev_score["overall"] < 60
            )
            or len(prev_score.get("misses") or []) >= 1
        )
    )

    parent_for_next: int | None = None
    if should_follow_up:
        next_q = generate_followup_question(
            target_job=target_job,
            chip_summary=chip_summary,
            weakness=weakness,
            asked_questions=asked,
            llm=llm,
        )
        parent_for_next = current_main_index
    elif skeleton_count < len(skeleton_list):
        # Advance to next planned main question.
        next_q = NextQuestion(question=skeleton_list[skeleton_count], source="skeleton")
        parent_for_next = None
    else:
        # All skeleton done and no drill triggered — keep going via follow-up so
        # the interview is unbounded; user ends manually.
        next_q = generate_followup_question(
            target_job=target_job,
            chip_summary=chip_summary,
            weakness=weakness,
            asked_questions=asked,
            llm=llm,
        )
        parent_for_next = current_main_index

    # Step 6: persist next turn row
    db = session_factory()
    try:
        existing = db.query(InterviewTurn).filter_by(
            session_id=session_id, turn_index=next_turn_index,
        ).one_or_none()
        if existing is None:
            db.add(InterviewTurn(
                session_id=session_id,
                user_key=user_key,
                turn_index=next_turn_index,
                target_job=target_job,
                question=next_q.question,
                question_source=next_q.source,
                parent_turn_index=parent_for_next,
            ))
            db.commit()
    finally:
        db.close()

    return next_q
