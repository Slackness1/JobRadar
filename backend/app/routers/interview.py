import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session, sessionmaker

from app.database import SessionLocal, get_db
from app.models import (
    InterviewIntelKeyword,
    InterviewIntelPost,
    InterviewAudioArtifact,
    InterviewRealtimeSession,
    InterviewReport,
    InterviewTurn,
)
from app.services.interview.llm import stream_interview_turn
from app.services.interview.orchestrator import process_turn_synchronous
from app.services.interview.report import generate_interview_report
from app.services.interview.voice.asr import AsrUnavailable, run_asr_session
from app.services.interview.voice.avatar import AvatarUnavailable, create_avatar_session
from app.services.interview.voice.tts import TTS_SAMPLE_RATE, TTSUnavailable, synthesize

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/interview', tags=['interview'])


def _require_audio_user_key(user_key: str) -> None:
    if not user_key.strip():
        raise HTTPException(status_code=401, detail='AUDIO_ARTIFACT_IDENTITY_REQUIRED')


def _load_latest_profile_for_user(db: Session, user_key: str) -> dict | None:
    """Look up the most recent confirmed resume profile for a user_key.

    Used by /report to power the fab-number guard in generate_interview_report —
    candidate's transcript numbers are cross-checked against this profile.
    Returns None when user has no resume copilot session (guest / cold start);
    the guard then no-ops without crashing.
    """
    if not user_key:
        return None
    try:
        from app.models import ResumeConfirmedProfile, ResumeCopilotSession
        sess = (
            db.query(ResumeCopilotSession)
            .filter(ResumeCopilotSession.user_key == user_key)
            .order_by(ResumeCopilotSession.updated_at.desc())
            .first()
        )
        if not sess:
            return None
        cp = (
            db.query(ResumeConfirmedProfile)
            .filter(ResumeConfirmedProfile.session_id == sess.id)
            .first()
        )
        if not cp or not cp.profile_json:
            return None
        return json.loads(str(cp.profile_json))
    except Exception as exc:
        logger.warning('load_latest_profile_for_user failed for %s: %s', user_key, exc)
        return None


class InterviewMessage(BaseModel):
    role: str
    content: str


class AsrSegment(BaseModel):
    """One final ASR segment.

    Timing is optional because some provider final events do not include it.
    When absent, downstream timing metrics intentionally stay null rather than
    using a synthetic zero-length segment.
    """

    start_s: float | None = None
    end_s: float | None = None
    text: str

    @model_validator(mode='after')
    def validate_timing_pair(self):
        if (self.start_s is None) != (self.end_s is None):
            raise ValueError('start_s and end_s must be provided together')
        if self.start_s is not None and self.end_s is not None:
            if self.start_s < 0 or self.end_s < self.start_s:
                raise ValueError('ASR segment timing must be non-negative and monotonic')
        return self


class AsrTranscript(BaseModel):
    audio_duration_s: float = Field(default=0.0, ge=0)
    segments: list[AsrSegment] = Field(default_factory=list)


class InterviewTurnIn(BaseModel):
    target_job: str
    session_id: str = ''  # frontend UUID
    messages: list[InterviewMessage]
    asr_transcript: AsrTranscript | None = None  # most-recent voice answer
    jd_content: str | None = None  # 可选 — 来自岗位 JD，用于定制考察重点


class InterviewReportIn(BaseModel):
    target_job: str
    session_id: str = ''
    messages: list[InterviewMessage]
    duration_seconds: int = 0
    jd_content: str | None = None


class InterviewRealtimeSessionIn(BaseModel):
    session_id: str = Field(min_length=8, max_length=80)
    target_job: str = Field(min_length=1, max_length=160)
    jd_content: str = Field(default='', max_length=12000)
    turn_mode: Literal['manual', 'automatic'] = 'manual'


@router.post('/audio-artifacts', status_code=202)
async def create_interview_audio_artifact(
    session_id: str = Form(..., min_length=1, max_length=80),
    turn_index: int = Form(..., ge=0),
    consent_granted: bool = Form(False),
    consent_version: str = Form(..., max_length=80),
    transcript_text: str = Form(default='', max_length=12000),
    audio: UploadFile = File(...),
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """Persist one explicitly consented, turn-bound WAV for async analysis."""
    from app import config
    from app.services.interview.voice_intelligence import (
        CONSENT_VERSION,
        delete_audio_artifact,
        enqueue_audio_analysis,
        inspect_wav_bytes,
        new_artifact_id,
        persist_private_wav,
        serialize_audio_artifact,
        sha256_hex,
    )

    if not config.VOICE_INTELLIGENCE_ENABLED:
        raise HTTPException(status_code=503, detail='VOICE_INTELLIGENCE_DISABLED')
    _require_audio_user_key(x_resume_user_key)
    if not consent_granted or consent_version != CONSENT_VERSION:
        raise HTTPException(status_code=422, detail='EXPLICIT_AUDIO_CONSENT_REQUIRED')
    _assert_session_owner_or_403(db, session_id, x_resume_user_key)
    turn = db.query(InterviewTurn).filter_by(
        session_id=session_id, turn_index=turn_index
    ).one_or_none()
    if turn is None:
        raise HTTPException(status_code=404, detail='INTERVIEW_TURN_NOT_FOUND')

    max_bytes = max(1, config.VOICE_AUDIO_MAX_UPLOAD_MB) * 1024 * 1024
    data = await audio.read(max_bytes + 1)
    await audio.close()
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail='AUDIO_UPLOAD_TOO_LARGE')
    try:
        metadata = inspect_wav_bytes(data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # One live artifact per turn minimizes retained data and makes retries
    # deterministic. A replacement first removes the previous physical file.
    previous_rows = db.query(InterviewAudioArtifact).filter(
        InterviewAudioArtifact.session_id == session_id,
        InterviewAudioArtifact.turn_index == turn_index,
        InterviewAudioArtifact.user_key == x_resume_user_key,
        InterviewAudioArtifact.deleted_at.is_(None),
    ).all()
    for previous in previous_rows:
        delete_audio_artifact(previous, db, status='replaced')

    now = datetime.utcnow()
    artifact_id = new_artifact_id()
    path = persist_private_wav(artifact_id, data)
    row = InterviewAudioArtifact(
        id=artifact_id,
        session_id=session_id,
        turn_index=turn_index,
        user_key=x_resume_user_key,
        consent_version=consent_version,
        consented_at=now,
        content_type='audio/wav',
        storage_path=str(path),
        sha256=sha256_hex(data),
        byte_size=len(data),
        sample_rate=metadata.sample_rate,
        channels=metadata.channels,
        duration_seconds=metadata.duration_seconds,
        status='uploaded',
        expires_at=now + timedelta(days=max(1, config.VOICE_AUDIO_RETENTION_DAYS)),
        created_at=now,
        updated_at=now,
    )
    try:
        db.add(row)
        db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise

    task_session_factory = sessionmaker(bind=db.get_bind())
    enqueue_audio_analysis(
        artifact_id,
        task_session_factory,
        transcript_text.strip(),
    )
    return serialize_audio_artifact(row)


@router.get('/sessions/{session_id}/audio-artifacts')
def list_interview_audio_artifacts(
    session_id: str,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    from app.services.interview.voice_intelligence import serialize_audio_artifact

    _require_audio_user_key(x_resume_user_key)
    _assert_session_owner_or_403(db, session_id, x_resume_user_key)
    rows = db.query(InterviewAudioArtifact).filter(
        InterviewAudioArtifact.session_id == session_id,
        InterviewAudioArtifact.user_key == x_resume_user_key,
    ).order_by(InterviewAudioArtifact.created_at).all()
    return [serialize_audio_artifact(row) for row in rows]


@router.get('/audio-artifacts/{artifact_id}')
def get_interview_audio_artifact(
    artifact_id: str,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    from app.services.interview.voice_intelligence import serialize_audio_artifact

    _require_audio_user_key(x_resume_user_key)
    row = db.query(InterviewAudioArtifact).filter_by(id=artifact_id).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail='AUDIO_ARTIFACT_NOT_FOUND')
    if row.user_key != x_resume_user_key:
        raise HTTPException(status_code=403, detail='AUDIO_ARTIFACT_FORBIDDEN')
    return serialize_audio_artifact(row)


@router.get('/audio-artifacts/{artifact_id}/audio')
def replay_interview_audio_artifact(
    artifact_id: str,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    from app.services.interview.voice_intelligence import delete_audio_artifact

    _require_audio_user_key(x_resume_user_key)
    row = db.query(InterviewAudioArtifact).filter_by(id=artifact_id).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail='AUDIO_ARTIFACT_NOT_FOUND')
    if row.user_key != x_resume_user_key:
        raise HTTPException(status_code=403, detail='AUDIO_ARTIFACT_FORBIDDEN')
    if row.deleted_at is not None or not row.storage_path:
        raise HTTPException(status_code=410, detail='AUDIO_ARTIFACT_DELETED')
    if row.expires_at <= datetime.utcnow():
        delete_audio_artifact(row, db, status='expired')
        raise HTTPException(status_code=410, detail='AUDIO_ARTIFACT_EXPIRED')
    if not Path(row.storage_path).is_file():
        row.status = 'error'
        row.error_message = 'AUDIO_FILE_MISSING'
        db.commit()
        raise HTTPException(status_code=410, detail='AUDIO_ARTIFACT_MISSING')
    return FileResponse(
        row.storage_path,
        media_type='audio/wav',
        headers={'Cache-Control': 'private, no-store'},
    )


@router.delete('/audio-artifacts/{artifact_id}', status_code=204)
def delete_interview_audio_artifact(
    artifact_id: str,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    from app.services.interview.voice_intelligence import delete_audio_artifact

    _require_audio_user_key(x_resume_user_key)
    row = db.query(InterviewAudioArtifact).filter_by(id=artifact_id).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail='AUDIO_ARTIFACT_NOT_FOUND')
    if row.user_key != x_resume_user_key:
        raise HTTPException(status_code=403, detail='AUDIO_ARTIFACT_FORBIDDEN')
    if row.deleted_at is None:
        delete_audio_artifact(row, db)


@router.delete('/sessions/{session_id}/audio-artifacts', status_code=204)
def delete_session_audio_artifacts(
    session_id: str,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    from app.services.interview.voice_intelligence import delete_audio_artifact

    _require_audio_user_key(x_resume_user_key)
    _assert_session_owner_or_403(db, session_id, x_resume_user_key)
    rows = db.query(InterviewAudioArtifact).filter(
        InterviewAudioArtifact.session_id == session_id,
        InterviewAudioArtifact.user_key == x_resume_user_key,
        InterviewAudioArtifact.deleted_at.is_(None),
    ).all()
    for row in rows:
        delete_audio_artifact(row, db)


@router.post('/realtime/session')
def create_interview_realtime_session(
    body: InterviewRealtimeSessionIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """Issue a short-lived, room-scoped token and server-side agent context."""
    from app import config
    from app.services.interview.voice.livekit_session import (
        LiveKitVoiceUnavailable,
        issue_livekit_grant,
    )
    from app.services.llm_quota import check_quota_or_raise

    check_quota_or_raise(db, x_resume_user_key)
    _assert_session_owner_or_403(db, body.session_id, x_resume_user_key)

    now = datetime.utcnow()
    reusable_rows = (
        db.query(InterviewRealtimeSession)
        .filter(
            InterviewRealtimeSession.user_key == x_resume_user_key,
            InterviewRealtimeSession.session_id == body.session_id,
            InterviewRealtimeSession.status.in_(['issued', 'connected']),
            InterviewRealtimeSession.expires_at > now,
        )
        .all()
    )
    for existing in reusable_rows:
        existing.status = 'superseded'
        existing.closed_at = now

    active_count = (
        db.query(InterviewRealtimeSession)
        .filter(
            InterviewRealtimeSession.user_key == x_resume_user_key,
            InterviewRealtimeSession.status.in_(['issued', 'connected']),
            InterviewRealtimeSession.expires_at > now,
        )
        .count()
    )
    if active_count >= max(1, config.VOICE_LIVEKIT_MAX_ACTIVE_SESSIONS_PER_USER):
        db.rollback()
        raise HTTPException(status_code=429, detail='REALTIME_SESSION_LIMIT_REACHED')

    requested_automatic = body.turn_mode == 'automatic'
    turn_mode = (
        'automatic'
        if requested_automatic and config.VOICE_LIVEKIT_AUTOMATIC_TURNS_ENABLED
        else 'manual'
    )
    interruption_mode = (
        'adaptive'
        if config.VOICE_LIVEKIT_ADAPTIVE_INTERRUPTION_ENABLED
        else 'vad'
    )

    try:
        grant = issue_livekit_grant(
            session_id=body.session_id,
            user_key=x_resume_user_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LiveKitVoiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    context_ttl = max(
        config.VOICE_LIVEKIT_TOKEN_TTL_SECONDS,
        config.VOICE_LIVEKIT_CONTEXT_TTL_SECONDS,
    )
    context_expires_at = datetime.utcnow() + timedelta(seconds=context_ttl)
    row = InterviewRealtimeSession(
        context_id=grant.context_id,
        session_id=body.session_id,
        room_name=grant.room_name,
        participant_identity=grant.participant_identity,
        user_key=x_resume_user_key,
        target_job=body.target_job.strip(),
        jd_content=body.jd_content.strip(),
        turn_mode=turn_mode,
        interruption_mode=interruption_mode,
        status='issued',
        expires_at=context_expires_at,
    )
    db.add(row)
    db.commit()

    return {
        'url': config.LIVEKIT_URL,
        'token': grant.token,
        'room_name': grant.room_name,
        'participant_identity': grant.participant_identity,
        'expires_at': grant.expires_at.isoformat() + 'Z',
        'turn_mode': turn_mode,
        'automatic_turns_available': config.VOICE_LIVEKIT_AUTOMATIC_TURNS_ENABLED,
        'interruption_mode': interruption_mode,
    }


@router.post('/turn')
def interview_turn(
    body: InterviewTurnIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    from app.services.interview.adaptive import NextQuestion, pick_next_question
    from app.services.interview.weakness_profile import WeaknessProfile
    from app.services.llm_quota import check_quota_or_raise

    check_quota_or_raise(db, x_resume_user_key)
    chip = body.target_job  # 1:1 for now; later: derive from a chip lookup table
    chip_summary = _load_chip_summary(db, chip)
    jd_content = body.jd_content or ''

    # Determine turn index from existing rows
    last_turn = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.session_id == body.session_id)
        .order_by(InterviewTurn.turn_index.desc())
        .first()
    )

    is_first_turn = (last_turn is None) or not any(
        m.role == 'user' for m in body.messages
    )

    if is_first_turn:
        # Bootstrap: skeleton[0] picked offline (no LLM needed)
        next_q = pick_next_question(
            target_job=body.target_job,
            chip=chip,
            chip_summary=chip_summary,
            weakness=WeaknessProfile(),
            asked_questions=[],
            turn_index=0,
            llm=_NoopLLM(),  # never reached for skeleton index 0
            jd_content=jd_content,
        )
        next_turn_index = 0
        # Persist first turn row
        if last_turn is None:
            db.add(InterviewTurn(
                session_id=body.session_id,
                user_key=x_resume_user_key,
                turn_index=0,
                target_job=body.target_job,
                question=next_q.question,
                question_source=next_q.source,
            ))
            db.commit()
    else:
        prev_user_msg = next(
            (m for m in reversed(body.messages) if m.role == 'user'), None
        )
        prev_user_answer = prev_user_msg.content if prev_user_msg else ''
        prev_turn_index = int(last_turn.turn_index)
        next_turn_index = prev_turn_index + 1

        try:
            next_q = process_turn_synchronous(
                session_id=body.session_id,
                user_key=x_resume_user_key,
                target_job=body.target_job,
                chip=chip,
                chip_summary=chip_summary,
                prev_turn_index=prev_turn_index,
                prev_user_answer=prev_user_answer,
                prev_asr_transcript=(
                    body.asr_transcript.model_dump() if body.asr_transcript else {}
                ),
                next_turn_index=next_turn_index,
                session_factory=SessionLocal,
                jd_content=jd_content,
            )
        except Exception as exc:
            logger.exception('process_turn failed: %s', exc)
            next_q = NextQuestion(
                question='请深入讲讲你最近完成的项目里你最自豪的一个细节。',
                source='fallback',
            )

    def event_stream():
        # Stream the next question text as chunks (so existing TTS-progress logic works).
        # Yield as a single chunk so downstream SSE parsers can match substrings in delta.
        yield f'data: {json.dumps({"type":"chunk","delta":next_q.question}, ensure_ascii=False)}\n\n'
        yield (
            f'data: {json.dumps({"type":"turn_complete","turn_index":next_turn_index,"question":next_q.question}, ensure_ascii=False)}\n\n'
        )

    return StreamingResponse(
        event_stream(),
        media_type='text/event-stream',
        headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache'},
    )


class _NoopLLM:
    def chat_text(self, system, user, **_):
        raise RuntimeError('NoopLLM.chat_text should never be reached')
    def chat_json(self, system, user, **_):
        raise RuntimeError('NoopLLM.chat_json should never be reached')


def _load_chip_summary(db: Session, chip: str) -> str:
    """Load nowcoder chip summary by exact match. Empty string if not found."""
    row = (
        db.query(InterviewIntelKeyword)
        .filter(InterviewIntelKeyword.keyword == chip)
        .first()
    )
    return str(row.summary_md or '') if row else ''


@router.post('/report')
def interview_report(
    body: InterviewReportIn,
    x_resume_user_key: str = Header(default=''),
    x_guest: str = Header(default=''),
    db: Session = Depends(get_db),
):
    from app.services.interview.report import build_report_aggregate
    from app.services.interview.llm_helpers import build_interview_llm_client
    from app.services.llm_quota import check_quota_or_raise

    check_quota_or_raise(db, x_resume_user_key)
    messages = [{'role': m.role, 'content': m.content} for m in body.messages]
    profile = _load_latest_profile_for_user(db, x_resume_user_key)
    report = generate_interview_report(
        body.target_job, messages, db=db,
        session_id=getattr(body, 'session_id', '') or None,
        profile=profile,
    )

    # New: aggregate from interview_turns + weekly plan
    session_id = getattr(body, 'session_id', '') or ''
    if session_id:
        try:
            llm = build_interview_llm_client()
            aggregate = build_report_aggregate(session_id, body.target_job, db, llm)
        except Exception as exc:
            logger.warning('report aggregate failed: %s', exc)
            aggregate = {'turn_count': 0, 'weakness_profile': None, 'weekly_plan_md': ''}
    else:
        aggregate = {'turn_count': 0, 'weakness_profile': None, 'weekly_plan_md': ''}

    voice_observations = _build_voice_observations(db, session_id, x_resume_user_key)
    if voice_observations:
        # Keep measured voice facts separate from the LLM-generated content
        # score. Every observation points back to a turn and replay artifact.
        report['voice_observations'] = voice_observations

    row = InterviewReport(
        user_key=x_resume_user_key,
        target_job=body.target_job,
        transcript_json=json.dumps(messages, ensure_ascii=False),
        report_json=json.dumps(report, ensure_ascii=False),
        duration_seconds=body.duration_seconds,
        is_guest=1 if x_guest.strip().lower() in {'1', 'true', 'yes'} else 0,
        created_at=datetime.utcnow(),
        weakness_profile_json=json.dumps(aggregate['weakness_profile'], ensure_ascii=False) if aggregate['weakness_profile'] else None,
        weekly_plan_md=aggregate['weekly_plan_md'],
        turn_count=aggregate['turn_count'],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        'id': row.id,
        'report': report,
        'turn_count': row.turn_count,
        'weakness_profile': aggregate['weakness_profile'],
        'weekly_plan_md': row.weekly_plan_md,
    }


@router.post('/avatar/session')
def avatar_session():
    """Create a Lingmou digital-human session, return rtcParams for the frontend SDK."""
    try:
        rtc_params = create_avatar_session(platform='Web')
    except AvatarUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return rtc_params


@router.get('/skeleton')
def get_skeleton(chip: str = ''):
    """Return the planned topic labels + questions for a chip.

    Frontend ProgressRail calls this so its labels are always in sync with the
    backend skeleton — eliminates the previous bug where the rail showed
    '为什么是这家公司' but the backend was asking '团队冲突' starting at turn 4.
    """
    from app.services.interview.adaptive import SKELETON_QUESTIONS, SKELETON_TOPIC_LABELS
    skeleton = SKELETON_QUESTIONS.get(chip) or SKELETON_QUESTIONS['default']
    matched = chip in SKELETON_QUESTIONS
    return {
        'chip': chip,
        'matched': matched,
        'topic_labels': SKELETON_TOPIC_LABELS,
        'questions': skeleton,
    }


@router.get('/intel-status')
def intel_status(db: Session = Depends(get_db)):
    """Per-chip 面经 coverage status. Drives the count badges on the /interview
    setup page so users can see how much real data backs each chip."""
    from sqlalchemy import func
    keyword_rows = db.query(InterviewIntelKeyword).all()
    post_counts = dict(
        db.query(InterviewIntelPost.keyword, func.count())
        .filter(InterviewIntelPost.parse_status == "ok")
        .group_by(InterviewIntelPost.keyword)
        .all()
    )
    items = []
    for r in keyword_rows:
        items.append({
            'keyword': r.keyword,
            'source_count': r.source_count or 0,
            'post_count': post_counts.get(r.keyword, 0),
            'has_summary': bool((r.summary_md or '').strip()),
            'generated_at': r.generated_at.isoformat() if r.generated_at else None,
        })
    items.sort(key=lambda x: -x['source_count'])
    return {'items': items, 'total_chips_with_summary': sum(1 for i in items if i['has_summary'])}


@router.get('/reports')
def list_reports(
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    if not x_resume_user_key:
        return []
    rows = (
        db.query(InterviewReport)
        .filter(InterviewReport.user_key == x_resume_user_key)
        .order_by(InterviewReport.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            'id': r.id,
            'target_job': r.target_job,
            'duration_seconds': r.duration_seconds,
            'overall_score': json.loads(r.report_json or '{}').get('overall_score', 0),
            'created_at': r.created_at.isoformat() if r.created_at else '',
        }
        for r in rows
    ]


class TTSIn(BaseModel):
    text: str
    voice: str | None = None


@router.post('/tts')
def interview_tts(
    body: TTSIn,
    audio_format: Literal['wav', 'pcm'] = Query(default='wav', alias='format'),
):
    if not body.text.strip():
        raise HTTPException(status_code=400, detail='text is empty')
    try:
        stream = synthesize(
            body.text,
            voice=body.voice,
            audio_format=audio_format,
        )
    except TTSUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if audio_format == 'pcm':
        return StreamingResponse(
            stream,
            media_type=f'audio/pcm;rate={TTS_SAMPLE_RATE};channels=1',
            headers={
                'Cache-Control': 'no-store',
                'X-Audio-Sample-Rate': str(TTS_SAMPLE_RATE),
                'X-Audio-Sample-Format': 's16le',
                'X-Voice-Stream-Version': '1',
            },
        )
    return StreamingResponse(
        stream,
        media_type='audio/wav',
        headers={'Cache-Control': 'no-store'},
    )


@router.websocket('/asr')
async def interview_asr(ws: WebSocket):
    await ws.accept()
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    async def audio_frames():
        while True:
            frame = await audio_queue.get()
            if frame is None:
                break
            yield frame

    async def send_event(event: dict):
        try:
            await ws.send_text(json.dumps(event, ensure_ascii=False))
        except Exception:
            pass

    asr_task = asyncio.create_task(
        run_asr_session(audio_frames(), send_event)  # type: ignore[arg-type]
    )

    try:
        while True:
            msg = await ws.receive()
            if msg.get('type') == 'websocket.disconnect':
                break
            if 'bytes' in msg and msg['bytes']:
                await audio_queue.put(msg['bytes'])
            elif 'text' in msg and msg['text']:
                try:
                    cmd = json.loads(msg['text'])
                except json.JSONDecodeError:
                    continue
                if cmd.get('action') == 'stop':
                    break
    except WebSocketDisconnect:
        pass
    except AsrUnavailable as exc:
        await send_event({'type': 'error', 'message': str(exc)})
    except Exception as exc:
        logger.exception('asr websocket error: %s', exc)
        await send_event({'type': 'error', 'message': str(exc)})
    finally:
        await audio_queue.put(None)
        try:
            await asyncio.wait_for(asr_task, timeout=5)
        except (asyncio.TimeoutError, AsrUnavailable) as exc:
            if isinstance(exc, AsrUnavailable):
                await send_event({'type': 'error', 'message': str(exc)})
        except Exception as exc:
            logger.exception('asr task cleanup error: %s', exc)
        try:
            await ws.close()
        except Exception:
            pass


@router.get('/reports/{report_id}')
def get_report(
    report_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    row = db.query(InterviewReport).filter(InterviewReport.id == report_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='Report not found')
    if row.user_key != x_resume_user_key:
        raise HTTPException(status_code=403, detail='Forbidden')
    return {
        'id': row.id,
        'target_job': row.target_job,
        'transcript': json.loads(row.transcript_json or '[]'),
        'report': json.loads(row.report_json or '{}'),
        'duration_seconds': row.duration_seconds,
        'created_at': row.created_at.isoformat() if row.created_at else '',
        'turn_count': int(row.turn_count or 0),
        'weakness_profile': json.loads(row.weakness_profile_json) if row.weakness_profile_json else None,
        'weekly_plan_md': str(row.weekly_plan_md or ''),
    }


def _assert_session_owner_or_403(db: Session, session_id: str, user_key: str) -> None:
    """Reject if any turn for this session has a non-empty user_key that doesn't match.
    Empty user_key on existing turns → treated as legacy/orphan and accessible (Q5 hardening
    for accidentally created rows during dev). Demo sessions don't apply to interviews."""
    rows = (
        db.query(InterviewTurn.user_key)
        .filter(InterviewTurn.session_id == session_id)
        .distinct()
        .all()
    )
    for (existing_key,) in rows:
        existing = str(existing_key or '')
        if existing and existing != user_key:
            raise HTTPException(status_code=403, detail='SESSION_FORBIDDEN')


def _build_voice_observations(db: Session, session_id: str, user_key: str) -> list[dict]:
    if not session_id:
        return []
    from app.services.interview.voice_intelligence import serialize_audio_artifact

    rows = db.query(InterviewAudioArtifact).filter(
        InterviewAudioArtifact.session_id == session_id,
        InterviewAudioArtifact.user_key == user_key,
        InterviewAudioArtifact.deleted_at.is_(None),
    ).order_by(InterviewAudioArtifact.turn_index, InterviewAudioArtifact.created_at).all()
    latest_by_turn = {int(row.turn_index): row for row in rows}
    return [serialize_audio_artifact(latest_by_turn[index]) for index in sorted(latest_by_turn)]


@router.get('/sessions/{session_id}/turns')
def get_session_turns(
    session_id: str,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    _assert_session_owner_or_403(db, session_id, x_resume_user_key)
    rows = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.session_id == session_id)
        .order_by(InterviewTurn.turn_index)
        .all()
    )
    artifact_rows = db.query(InterviewAudioArtifact).filter(
        InterviewAudioArtifact.session_id == session_id,
        InterviewAudioArtifact.user_key == x_resume_user_key,
        InterviewAudioArtifact.deleted_at.is_(None),
    ).order_by(InterviewAudioArtifact.created_at).all()
    latest_artifact_by_turn = {int(row.turn_index): row for row in artifact_rows}
    from app.services.interview.voice_intelligence import serialize_audio_artifact
    out = []
    for r in rows:
        voice_metrics = json.loads(r.voice_metrics) if r.voice_metrics else None
        if isinstance(voice_metrics, dict):
            # Historical rows may contain the uncalibrated LLM confidence field.
            # Never expose it as a measured voice fact.
            voice_metrics.pop('confidence_score', None)
        artifact = latest_artifact_by_turn.get(int(r.turn_index))
        out.append({
            'turn_index': int(r.turn_index),
            'question': str(r.question or ''),
            'user_answer': str(r.user_answer or ''),
            'reference_answer': str(r.reference_answer or ''),
            'question_source': str(r.question_source or ''),
            'parent_turn_index': int(r.parent_turn_index) if r.parent_turn_index is not None else None,
            'score': json.loads(r.score_json) if r.score_json else None,
            'voice_metrics': voice_metrics,
            'voice_intelligence': serialize_audio_artifact(artifact) if artifact else None,
            'question_heard_text': str(r.question_heard_text or ''),
            'question_interrupted': bool(r.question_interrupted),
            'realtime_transport': str(r.realtime_transport or ''),
            'created_at': r.created_at.isoformat() if r.created_at else '',
        })
    return out


@router.get('/sessions/{session_id}/turns/latest-score')
def get_latest_score(
    session_id: str,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    _assert_session_owner_or_403(db, session_id, x_resume_user_key)
    row = (
        db.query(InterviewTurn)
        .filter(
            InterviewTurn.session_id == session_id,
            InterviewTurn.score_json.isnot(None),
        )
        .order_by(InterviewTurn.turn_index.desc())
        .first()
    )
    if row is None:
        return None
    try:
        score = json.loads(row.score_json or '{}')
    except json.JSONDecodeError:
        return None
    misses = score.get('misses') or []
    if misses:
        hint = f'📌 你这次没提到 {misses[0]}'
    else:
        hits = score.get('hits') or []
        hint = f'✓ 这道答得不错，命中了 {hits[0]}' if hits else '本题已评分'
    return {'turn_index': int(row.turn_index), 'hint': hint}
