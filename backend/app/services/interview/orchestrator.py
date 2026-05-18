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
from app.services.interview.subagents.recaller import (
    ExperienceRecaller,
    RecallerInput,
)
from app.services.interview.interest_decider import should_continue_followup
from app.services.interview.llm_helpers import InterviewLLMClient
from app.services.interview.reference_answer import generate_reference
from app.services.interview.scoring import ScoreResult, score_answer
from app.services.interview.voice_metrics import (
    VoiceMetrics,
    compute_voice_metrics,
    score_confidence_from_transcript,
)
from app.services.interview.weakness_profile import compute_weakness


# 反问环节后礼貌收尾文案 — orchestrator 在 reverse Q 答完之后返回这条,
# 不再 LLM 生成 follow-up
_END_OF_INTERVIEW_MESSAGE = "本次面试到这里告一段落,谢谢你今天的分享。如果还有想补充的可以再聊几句,否则可以结束。"

# Hard-rule 阈值
_FOLLOWUP_CAP = 3                  # 单 main 下最多 N 个 follow-up (旧版写死 2)
_TOO_SHORT_ANSWER_CHARS = 80       # 答案少于 N 字直接 advance,没东西可问

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


def _recall_experiences(
    session_factory: Callable[[], Session],
    user_key: str,
    target_job: str,
    transcript: list[dict],
    max_results: int = 3,
) -> list[dict]:
    """Run ExperienceRecaller synchronously and return its experiences list.

    The Recaller is async-shaped (asyncio.to_thread internally) but does pure
    SQL/Python work — we drive it from the sync orchestrator via asyncio.run.
    Failures are non-fatal: returns [] so the follow-up branch falls through
    to its existing behavior without recalled hints.
    """
    import asyncio
    if not (user_key or "").strip():
        return []
    db = session_factory()
    try:
        try:
            result = asyncio.run(
                ExperienceRecaller().invoke(RecallerInput(
                    db=db,
                    user_key=user_key,
                    target_job=target_job,
                    transcript_so_far=transcript,
                    max_results=max_results,
                ))
            )
        except Exception as exc:
            logger.warning("ExperienceRecaller invoke failed: %s", exc)
            return []
        if not result.is_usable:
            return []
        return list(result.summary.get("experiences") or [])
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
    jd_content: str = "",
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

    # Step 5: decide follow-up vs advance vs end-of-interview
    #
    # Hybrid:
    #   1. Hard rules (no LLM,毫秒级): 反问环节 / 上限 / 答案太短 → advance
    #   2. Soft rule (LLM interest_decider): 真实面试官视角判 "还想继续追问吗"
    #
    # 失败时(LLM 错误 / 解析失败) 默认 advance — 不连续追问总比追错好。
    should_follow_up = False
    interest_target_dimension: str | None = None

    # 是不是反问环节(skeleton 最后一题)
    is_reverse_question_phase = False
    if current_main_index is not None:
        main_turn_obj = next(
            (t for t in (
                # 重新开 session 拿 all_turns 太重,直接用 prev_turn 推断:
                # current_main_index 要么 == prev_turn_index (skeleton),
                # 要么 prev_turn 是它的 child (follow-up)
                [prev_turn] if prev_turn is not None else []
            ) if t and int(getattr(t, 'turn_index', -1)) == current_main_index),
            None,
        )
        if main_turn_obj is not None and getattr(main_turn_obj, 'question_source', None) == "skeleton":
            # 它在 skeleton 列表里的位置 = 它前面有几个 skeleton turn
            skeleton_position = sum(
                1 for t in all_turns
                if t.question_source == "skeleton" and t.turn_index < current_main_index
            )
            is_reverse_question_phase = skeleton_position == len(skeleton_list) - 1

    answer_too_short = len((prev_user_answer or "").strip()) < _TOO_SHORT_ANSWER_CHARS
    followup_cap_reached = followups_under_current >= _FOLLOWUP_CAP

    if is_reverse_question_phase:
        logger.info("hard rule: 反问环节,跳过 follow-up")
    elif followup_cap_reached:
        logger.info("hard rule: 已追 %d 次 (cap=%d),advance", followups_under_current, _FOLLOWUP_CAP)
    elif answer_too_short:
        logger.info("hard rule: 答案 %d 字 (<%d),advance", len(prev_user_answer or ''), _TOO_SHORT_ANSWER_CHARS)
    elif current_main_index is None:
        # 未识别到 main → 安全 advance
        logger.info("无 current_main_index,advance")
    else:
        # Soft rule: 让 LLM 像面试官一样判断
        main_turn = next((t for t in all_turns if t.turn_index == current_main_index), None)
        main_question = str(main_turn.question or "") if main_turn else ""
        main_answer = str(main_turn.user_answer or "") if main_turn else ""
        # 已问 + 已答的 follow-up 链 (parent == current_main_index 的 turn,按 turn_index 排序)
        followup_chain = [
            (str(t.question or ""), str(t.user_answer or ""))
            for t in sorted(
                [t for t in all_turns
                 if t.parent_turn_index is not None
                 and int(t.parent_turn_index) == current_main_index],
                key=lambda x: x.turn_index,
            )
        ]
        decision = should_continue_followup(
            llm=llm,
            target_job=target_job,
            chip_summary=chip_summary,
            jd_content=jd_content,
            main_question=main_question,
            main_answer=main_answer,
            followup_chain=followup_chain,
        )
        should_follow_up = decision.should_continue
        interest_target_dimension = decision.target_dimension
        logger.info(
            "interest_decider: continue=%s target=%r reasoning=%s",
            decision.should_continue, decision.target_dimension, decision.reasoning[:120],
        )

    parent_for_next: int | None = None
    if should_follow_up:
        # Recall experiences from account_memory before generating follow-up so
        # the LLM can ground sub-questions in real candidate history.
        transcript = [
            {"role": "assistant", "content": str(t.question or "")}
            for t in all_turns if t.question
        ] + [
            {"role": "user", "content": str(t.user_answer or "")}
            for t in all_turns if t.user_answer
        ]
        recalled = _recall_experiences(
            session_factory, user_key, target_job, transcript,
        )
        next_q = generate_followup_question(
            target_job=target_job,
            chip_summary=chip_summary,
            weakness=weakness,
            asked_questions=asked,
            llm=llm,
            jd_content=jd_content,
            current_main_question=prev_question if current_main_index is not None else "",
            current_main_answer=prev_user_answer if current_main_index is not None else "",
            recalled_experiences=recalled,
        )
        parent_for_next = current_main_index
    elif skeleton_count < len(skeleton_list):
        # Advance to next planned main question.
        next_q = NextQuestion(question=skeleton_list[skeleton_count], source="skeleton")
        parent_for_next = None
    else:
        # 全部 skeleton 跑完(含反问环节已答)→ 礼貌收尾,不再硬生成 follow-up。
        # 旧版在这里 LLM 生成无界 follow-up,会出现"反问环节面试官还反问候选人"的怪
        # 行为(eval baseline 抓到的真 bug)。前端可以用 source="end" 来收 UI。
        next_q = NextQuestion(question=_END_OF_INTERVIEW_MESSAGE, source="end")
        parent_for_next = None

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
