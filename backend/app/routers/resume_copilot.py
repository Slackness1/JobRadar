import json
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, UploadFile, status
from fastapi.responses import Response
from urllib.parse import quote
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    ResumeConfirmedProfile,
    ResumeCopilotSession,
    ResumeDirectionAnalysisRun,
    ResumeCopilotMessage,
    ResumeParsedProfile,
    ResumePreferenceProfile,
    ResumeRecommendationRun,
)
from app.schemas_resume_copilot import (
    AgentActionIn,
    ApplyRewriteIn,
    ApplyRewriteOut,
    ChatMessageIn,
    DirectionTierResult,
    MemoryEntryCreateIn,
    MemoryEntryOut,
    MemoryEntryPatchIn,
    MemoryGroupedOut,
    PlanStartIn,
    PlanStateOut,
    ResumeAgentTraceItem,
    ResumeConfirmedProfileIn,
    ResumeConfirmedProfileOut,
    ResumeCopilotMessageOut,
    ResumeCopilotRenameIn,
    ResumeCopilotSessionCreatedOut,
    ResumeCopilotSessionListItem,
    ResumeCopilotSessionOut,
    ResumeGenerateOut,
    ResumePreferenceIn,
    ResumePreferenceOut,
    ResumeProfilePayload,
    ResumeParsedProfileOut,
    ResumePreferencePayload,
    ResumeRecommendationItem,
    ResumeRecommendationResultOut,
    RewriteOption,
)
from app.services.resume_copilot.demo_session import DEMO_SESSION_ID
from app.services.resume_copilot.ingest import ResumeUploadError, extract_resume_text_with_page_count, validate_pdf_upload
from app.services.resume_copilot.pdf_export import FontsNotInstalledError, render_resume_pdf
from app.services.resume_copilot.state import INFLIGHT_GUARD_SECONDS, RunStatus, SessionStatus
from app.services.resume_copilot.workflow import run_resume_generate_workflow, run_resume_parse_workflow

router = APIRouter(prefix='/api/resume-copilot', tags=['resume-copilot'])


GUEST_SESSION_TTL = timedelta(hours=24)
USER_SESSION_TTL = timedelta(days=7)


def _assert_not_demo(session: ResumeCopilotSession) -> None:
    if str(getattr(session, 'user_key', '') or '') == '__demo__':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Demo session is read-only',
        )


def _assert_session_owner(session: ResumeCopilotSession, user_key: str) -> None:
    """Reject access unless caller's X-Resume-User-Key matches the session.

    Demo session (`user_key == '__demo__'`) is publicly readable; writes are
    blocked separately by `_assert_not_demo`. Sessions with empty `user_key`
    are legacy/orphan rows from before auth was enforced — they become
    inaccessible, which is the intended outcome.
    """
    session_key = str(getattr(session, 'user_key', '') or '')
    if session_key == '__demo__':
        return
    if not user_key or user_key != session_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='SESSION_FORBIDDEN',
        )


def _get_session_or_404(db: Session, session_id: int) -> ResumeCopilotSession:
    session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f'Resume copilot session {session_id} not found')
    return session


def _get_session_eager(db: Session, session_id: int) -> ResumeCopilotSession | None:
    return (
        db.query(ResumeCopilotSession)
        .options(
            joinedload(ResumeCopilotSession.parsed_profile),
            joinedload(ResumeCopilotSession.confirmed_profile),
            joinedload(ResumeCopilotSession.preference_profile),
            joinedload(ResumeCopilotSession.recommendation_run),
            joinedload(ResumeCopilotSession.feedback_run),
            joinedload(ResumeCopilotSession.direction_analysis_run),
        )
        .filter(ResumeCopilotSession.id == session_id)
        .first()
    )


def _build_session_out(session: ResumeCopilotSession) -> ResumeCopilotSessionOut:
    return ResumeCopilotSessionOut(
        id=int(getattr(session, 'id')),
        file_name=str(getattr(session, 'file_name', '') or ''),
        name=str(getattr(session, 'name', '') or ''),
        status=str(getattr(session, 'status', '') or ''),
        error_message=str(getattr(session, 'error_message', '') or ''),
        recommendation_status=str(getattr(session, 'recommendation_status', '') or ''),
        feedback_status=str(getattr(session, 'feedback_status', '') or ''),
        has_parsed_profile=session.parsed_profile is not None,
        has_confirmed_profile=session.confirmed_profile is not None,
        has_preferences=session.preference_profile is not None,
        has_recommendations=session.recommendation_run is not None,
        has_feedback=session.feedback_run is not None,
        has_direction_analysis=session.direction_analysis_run is not None,
        plan_status=str(getattr(session, 'plan_status', '') or 'idle'),
        has_plan=bool(getattr(session, 'plan_json', None)),
        created_at=getattr(session, 'created_at', None),
        updated_at=getattr(session, 'updated_at', None),
        finished_at=getattr(session, 'finished_at', None),
    )


@router.get('/sessions', response_model=list[ResumeCopilotSessionListItem])
def list_resume_copilot_sessions(
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    if not x_resume_user_key:
        return []
    rows = (
        db.query(ResumeCopilotSession)
        .options(joinedload(ResumeCopilotSession.recommendation_run))
        .filter(ResumeCopilotSession.user_key == x_resume_user_key)
        .order_by(ResumeCopilotSession.updated_at.desc())
        .limit(20)
        .all()
    )
    return [
        ResumeCopilotSessionListItem(
            id=int(getattr(r, 'id')),
            file_name=str(getattr(r, 'file_name', '') or ''),
            name=str(getattr(r, 'name', '') or ''),
            status=str(getattr(r, 'status', '') or ''),
            has_recommendations=r.recommendation_run is not None,
            created_at=getattr(r, 'created_at', None),
            updated_at=getattr(r, 'updated_at', None),
        )
        for r in rows
    ]


@router.post('/sessions', response_model=ResumeCopilotSessionCreatedOut, status_code=status.HTTP_202_ACCEPTED)
async def create_resume_copilot_session(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    x_resume_user_key: str = Header(default=''),
    x_guest: str = Header(default=''),
    db: Session = Depends(get_db),
):
    try:
        validate_pdf_upload(file.filename or '', file.content_type or '')
        file_bytes = await file.read()
        extracted_text, page_count = extract_resume_text_with_page_count(file_bytes)
    except ResumeUploadError as exc:
        raise HTTPException(status_code=400, detail=exc.code) from exc

    is_guest = 1 if x_guest.strip().lower() in {'1', 'true', 'yes'} else 0
    session = ResumeCopilotSession(
        file_name=file.filename or '',
        user_key=x_resume_user_key,
        status=SessionStatus.PARSING_PROFILE.value,
        extracted_text=extracted_text,
        is_guest=is_guest,
        expires_at=datetime.utcnow() + (GUEST_SESSION_TTL if is_guest else USER_SESSION_TTL),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    background_tasks.add_task(run_resume_parse_workflow, int(getattr(session, 'id')))
    return ResumeCopilotSessionCreatedOut(
        session_id=int(getattr(session, 'id')),
        status=SessionStatus.PARSING_PROFILE.value,
        page_count=page_count,
        file_size_bytes=len(file_bytes),
    )


@router.get('/sessions/{session_id}', response_model=ResumeCopilotSessionOut)
def get_resume_copilot_session(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    session = _get_session_eager(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f'Resume copilot session {session_id} not found')
    _assert_session_owner(session, x_resume_user_key)
    return _build_session_out(session)


@router.patch('/sessions/{session_id}', response_model=ResumeCopilotSessionOut)
def rename_resume_copilot_session(
    session_id: int,
    payload: ResumeCopilotRenameIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    _assert_not_demo(session)
    session.name = payload.name.strip()[:120]
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    eager = _get_session_eager(db, session_id)
    if not eager:
        raise HTTPException(status_code=404, detail=f'Resume copilot session {session_id} not found')
    return _build_session_out(eager)


@router.delete('/sessions/{session_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_resume_copilot_session(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    _assert_not_demo(session)
    db.delete(session)
    db.commit()


@router.get('/sessions/{session_id}/parsed-profile', response_model=ResumeParsedProfileOut)
def get_resume_copilot_parsed_profile(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    profile = db.query(ResumeParsedProfile).filter(ResumeParsedProfile.session_id == session_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail=f'Parsed profile for session {session_id} not found')
    profile_json: Any = getattr(profile, 'profile_json', '{}') or '{}'
    return ResumeParsedProfileOut(
        session_id=session_id,
        profile=ResumeProfilePayload.model_validate(json.loads(str(profile_json))),
    )


@router.get('/sessions/{session_id}/confirmed-profile', response_model=ResumeConfirmedProfileOut)
def get_resume_copilot_confirmed_profile(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    profile = db.query(ResumeConfirmedProfile).filter(ResumeConfirmedProfile.session_id == session_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail=f'Confirmed profile for session {session_id} not found')
    profile_json: Any = getattr(profile, 'profile_json', '{}') or '{}'
    return ResumeConfirmedProfileOut(
        session_id=session_id,
        profile=ResumeProfilePayload.model_validate(json.loads(str(profile_json))),
    )


@router.put('/sessions/{session_id}/confirmed-profile', response_model=ResumeConfirmedProfileOut)
def put_resume_copilot_confirmed_profile(
    session_id: int,
    payload: ResumeConfirmedProfileIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)
    profile = db.query(ResumeConfirmedProfile).filter(ResumeConfirmedProfile.session_id == session_id).first()
    if not profile:
        profile = ResumeConfirmedProfile(session_id=session_id)
        db.add(profile)
    profile.profile_json = json.dumps(payload.profile.model_dump())
    session = _get_session_or_404(db, session_id)
    session.updated_at = datetime.utcnow()
    db.commit()
    return ResumeConfirmedProfileOut(session_id=session_id, profile=payload.profile)


@router.get('/sessions/{session_id}/export.pdf')
def export_resume_pdf(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)

    confirmed = (
        db.query(ResumeConfirmedProfile)
        .filter(ResumeConfirmedProfile.session_id == session_id)
        .first()
    )
    parsed = (
        db.query(ResumeParsedProfile)
        .filter(ResumeParsedProfile.session_id == session_id)
        .first()
    )
    source = confirmed or parsed
    if not source:
        raise HTTPException(status_code=404, detail='No resume profile available to export')

    profile_json: Any = getattr(source, 'profile_json', '{}') or '{}'
    profile = ResumeProfilePayload.model_validate(json.loads(str(profile_json)))

    try:
        pdf_bytes = render_resume_pdf(profile)
    except FontsNotInstalledError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    name = (profile.basic_info or {}).get('name', '').strip() or '简历'
    filename = f'{name}-简历-{datetime.utcnow().strftime("%Y%m%d")}.pdf'
    content_disposition = (
        f"attachment; filename=resume.pdf; filename*=UTF-8''{quote(filename)}"
    )
    return Response(
        content=pdf_bytes,
        media_type='application/pdf',
        headers={'Content-Disposition': content_disposition},
    )


@router.get('/sessions/{session_id}/preferences', response_model=ResumePreferenceOut)
def get_resume_copilot_preferences(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    preference_profile = db.query(ResumePreferenceProfile).filter(ResumePreferenceProfile.session_id == session_id).first()
    if not preference_profile:
        raise HTTPException(status_code=404, detail=f'Preferences for session {session_id} not found')
    preferences_json: Any = getattr(preference_profile, 'preferences_json', '{}') or '{}'
    preferences = ResumePreferencePayload.model_validate(json.loads(str(preferences_json)))
    preferences.all_skipped = bool(getattr(preference_profile, 'all_skipped', 0))
    return ResumePreferenceOut(session_id=session_id, preferences=preferences)


@router.put('/sessions/{session_id}/preferences', response_model=ResumePreferenceOut)
def put_resume_copilot_preferences(
    session_id: int,
    payload: ResumePreferenceIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)
    preference_profile = db.query(ResumePreferenceProfile).filter(ResumePreferenceProfile.session_id == session_id).first()
    if not preference_profile:
        preference_profile = ResumePreferenceProfile(session_id=session_id)
        db.add(preference_profile)
    preference_profile.preferences_json = json.dumps(payload.preferences.model_dump())
    preference_profile.all_skipped = 1 if payload.preferences.all_skipped else 0
    session = _get_session_or_404(db, session_id)
    session.updated_at = datetime.utcnow()
    db.commit()
    return ResumePreferenceOut(session_id=session_id, preferences=payload.preferences)


@router.post(
    '/sessions/{session_id}/generate',
    response_model=ResumeGenerateOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_resume_recommendations(
    session_id: int,
    background_tasks: BackgroundTasks,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    _assert_not_demo(session)
    confirmed_profile = db.query(ResumeConfirmedProfile).filter(ResumeConfirmedProfile.session_id == session_id).first()
    if not confirmed_profile:
        raise HTTPException(status_code=409, detail='CONFIRMED_PROFILE_REQUIRED')

    recommendation_run = db.query(ResumeRecommendationRun).filter(ResumeRecommendationRun.session_id == session_id).first()
    if recommendation_run is not None and str(recommendation_run.status) == RunStatus.RUNNING.value:
        last_heartbeat = getattr(recommendation_run, 'updated_at', None) or getattr(recommendation_run, 'created_at', None)
        if last_heartbeat is not None and datetime.utcnow() - last_heartbeat < timedelta(seconds=INFLIGHT_GUARD_SECONDS):
            raise HTTPException(status_code=409, detail='GENERATE_ALREADY_RUNNING')
        # Stale worker — fall through and let the new run take over.

    if not recommendation_run:
        recommendation_run = ResumeRecommendationRun(session_id=session_id)
        db.add(recommendation_run)

    direction_run = db.query(ResumeDirectionAnalysisRun).filter(
        ResumeDirectionAnalysisRun.session_id == session_id
    ).first()
    if not direction_run:
        direction_run = ResumeDirectionAnalysisRun(session_id=session_id)
        db.add(direction_run)

    recommendation_run.status = RunStatus.RUNNING.value
    recommendation_run.error_message = ''
    recommendation_run.used_ai = 0
    recommendation_run.fallback_reason = ''
    recommendation_run.recommendations_json = '[]'
    recommendation_run.updated_at = datetime.utcnow()
    direction_run.status = RunStatus.RUNNING.value
    direction_run.error_message = ''
    direction_run.directions_json = '[]'
    direction_run.updated_at = datetime.utcnow()
    session.status = SessionStatus.GENERATING_RECOMMENDATIONS.value
    session.recommendation_status = RunStatus.RUNNING.value
    session.feedback_status = RunStatus.RUNNING.value
    session.error_message = ''
    db.commit()
    background_tasks.add_task(run_resume_generate_workflow, int(session_id))

    return ResumeGenerateOut(session_id=session_id, status=RunStatus.RUNNING.value)


@router.get('/sessions/{session_id}/recommendations', response_model=ResumeRecommendationResultOut)
def get_resume_copilot_recommendations(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    recommendation_run = db.query(ResumeRecommendationRun).filter(ResumeRecommendationRun.session_id == session_id).first()
    if not recommendation_run:
        raise HTTPException(status_code=404, detail=f'Recommendations for session {session_id} not found')
    recommendations_json: Any = getattr(recommendation_run, 'recommendations_json', '[]') or '[]'
    return ResumeRecommendationResultOut(
        session_id=session_id,
        status=str(getattr(recommendation_run, 'status', '') or ''),
        agent_trace=[ResumeAgentTraceItem.model_validate(item) for item in json.loads(str(getattr(recommendation_run, 'agent_trace_json', '[]') or '[]'))],
        used_ai=bool(getattr(recommendation_run, 'used_ai', 0)),
        fallback_reason=str(getattr(recommendation_run, 'fallback_reason', '') or ''),
        error_message=str(getattr(recommendation_run, 'error_message', '') or ''),
        items=[ResumeRecommendationItem.model_validate(item) for item in json.loads(str(recommendations_json))],
    )


@router.get('/sessions/{session_id}/direction-analysis', response_model=list[DirectionTierResult])
def get_direction_analysis(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    direction_run = db.query(ResumeDirectionAnalysisRun).filter(
        ResumeDirectionAnalysisRun.session_id == session_id
    ).first()
    if not direction_run or direction_run.status != 'completed':
        return []
    directions_json = getattr(direction_run, 'directions_json', '[]') or '[]'
    return [
        DirectionTierResult.model_validate(item)
        for item in json.loads(str(directions_json))
    ]


@router.get('/sessions/{session_id}/chat', response_model=list[ResumeCopilotMessageOut])
def get_chat_messages(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    msgs = (
        db.query(ResumeCopilotMessage)
        .filter(ResumeCopilotMessage.session_id == session_id)
        .order_by(ResumeCopilotMessage.created_at)
        .all()
    )
    return [
        ResumeCopilotMessageOut(
            id=int(msg.id),
            role=str(msg.role),
            content=str(msg.content or ''),
            rewrite_options=(
                [RewriteOption.model_validate(o)
                 for o in json.loads(str(msg.rewrite_options_json))]
                if msg.rewrite_options_json else None
            ),
            applied_option_id=msg.applied_option_id,
            created_at=msg.created_at,
        )
        for msg in msgs
    ]


@router.post('/sessions/{session_id}/chat', response_model=ResumeCopilotMessageOut)
def post_chat_message(
    session_id: int,
    payload: ChatMessageIn,
    background_tasks: BackgroundTasks,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    from app.services.resume_copilot.chat import generate_chat_turn

    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)
    direction_run = db.query(ResumeDirectionAnalysisRun).filter(
        ResumeDirectionAnalysisRun.session_id == session_id
    ).first()
    if not direction_run or str(getattr(direction_run, 'status', '')) != 'completed':
        raise HTTPException(status_code=409, detail='DIRECTION_ANALYSIS_NOT_READY')

    try:
        response = generate_chat_turn(session_id, payload.content, db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Student KB passive capture — flag-gated, guest/demo-skipped inside the task.
    # Runs after response returns so chat latency is unaffected.
    background_tasks.add_task(
        _dispatch_student_kb_extraction,
        session_id=session_id,
        user_content=payload.content,
    )
    return response


def _dispatch_student_kb_extraction(*, session_id: int, user_content: str) -> None:
    """BackgroundTasks entry point. Opens own SessionLocal because the request
    DB session is closed by the time this runs."""
    from app.database import SessionLocal
    from app.services.resume_copilot.memory.extractor import extract_for_chat_turn

    db = SessionLocal()
    try:
        extract_for_chat_turn(db, session_id=session_id, user_content=user_content)
    except Exception:
        # Memory extraction failures must never surface to the user — log and drop.
        import logging
        logging.getLogger(__name__).exception(
            "student_kb extraction failed for session_id=%s", session_id
        )
    finally:
        db.close()


@router.post('/sessions/{session_id}/chat/apply-rewrite', response_model=ApplyRewriteOut)
def post_apply_rewrite(
    session_id: int,
    payload: ApplyRewriteIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    from app.services.resume_copilot.chat import apply_rewrite

    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)
    try:
        updated_profile = apply_rewrite(
            session_id, payload.message_id, payload.option_id, db
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ApplyRewriteOut(profile=updated_profile, applied=True)


# ─── Plan-mode endpoints ────────────────────────────────────────────────────

def _load_plan(session: ResumeCopilotSession):
    from app.services.resume_copilot.plan import PlanState
    raw = getattr(session, 'plan_json', None)
    if not raw:
        return None
    return PlanState.model_validate_json(raw)


def _save_plan(session: ResumeCopilotSession, plan) -> None:
    session.plan_json = plan.model_dump_json()
    session.plan_status = plan.status.value


def _parsed_counts_from_profile(session: ResumeCopilotSession) -> dict[str, int]:
    """Derive ItemKind-keyed counts from the parsed profile JSON.

    Falls back to zeros if parse is missing — template still produces
    self_intro + skill items, so the plan is usable even on a near-empty
    upload."""
    if session.parsed_profile is None:
        return {}
    try:
        data = json.loads(session.parsed_profile.profile_json or '{}')
    except json.JSONDecodeError:
        return {}
    return {
        'education':       len(data.get('education', []) or []),
        'internship':      len(data.get('internships', []) or []),
        'project':         len(data.get('projects', []) or []),
        'campus_activity': 0,  # not in current profile schema; LLM tag pass will fill later
        'award':           len(data.get('awards', []) or []),
    }


@router.post('/sessions/{session_id}/plan/start', response_model=PlanStateOut)
def post_plan_start(
    session_id: int,
    _: PlanStartIn = PlanStartIn(),
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """Bootstrap the plan from the fixed template + parsed counts.

    Returns 409 if a plan already exists (clients should call GET first).
    Lands the session in ``plan_status=awaiting_plan_approval`` — user
    reviews/edits, then calls /plan/approve to enter the clarify loop."""
    from app.services.resume_copilot.plan import init_plan_from_template
    from app.services.resume_copilot.tag_extractor import attach_parsed_evidence

    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)

    if getattr(session_obj, 'plan_json', None):
        raise HTTPException(
            status_code=409,
            detail='PLAN_ALREADY_EXISTS — call GET /plan or DELETE first',
        )

    counts = _parsed_counts_from_profile(session_obj)
    plan = init_plan_from_template(counts)

    parsed_dict: dict = {}
    if session_obj.parsed_profile is not None:
        try:
            parsed_dict = json.loads(session_obj.parsed_profile.profile_json or '{}')
        except json.JSONDecodeError:
            parsed_dict = {}
    if parsed_dict:
        plan = attach_parsed_evidence(plan, parsed_dict)

    _save_plan(session_obj, plan)
    db.commit()
    db.refresh(session_obj)
    return PlanStateOut(**plan.model_dump(mode='json'))


@router.get('/sessions/{session_id}/plan', response_model=PlanStateOut)
def get_plan(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    plan = _load_plan(session_obj)
    if plan is None:
        raise HTTPException(status_code=404, detail='NO_PLAN — call POST /plan/start first')
    return PlanStateOut(**plan.model_dump(mode='json'))


@router.post('/sessions/{session_id}/plan/approve', response_model=PlanStateOut)
def post_plan_approve(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """Transition awaiting_plan_approval → clarifying. After this the agent
    loop is allowed to call /plan/actions to drive the conversation."""
    from app.services.resume_copilot.plan import PlanStatus

    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)

    plan = _load_plan(session_obj)
    if plan is None:
        raise HTTPException(status_code=404, detail='NO_PLAN')
    if plan.status != PlanStatus.AWAITING_PLAN_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f'PLAN_NOT_AWAITING_APPROVAL (current: {plan.status.value})',
        )
    plan.status = PlanStatus.CLARIFYING
    plan.version += 1
    _save_plan(session_obj, plan)
    db.commit()
    db.refresh(session_obj)
    return PlanStateOut(**plan.model_dump(mode='json'))


@router.post('/sessions/{session_id}/plan/turn', response_model=PlanStateOut)
def post_plan_turn(
    session_id: int,
    payload: ChatMessageIn,
    target_item_id: str | None = None,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """One LLM-driven plan-mode turn.

    Persists the user's chat message, asks the agent for one AgentAction,
    applies it (auto-converting failed writes into clarifying asks), and
    returns the new PlanState. The chat message log doubles as a
    conversation rail; the plan_json remains the source of truth."""
    from app.services.resume_copilot.agent.builder import NoMoreItems
    from app.services.resume_copilot.plan_turn import run_plan_turn

    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)

    if not getattr(session_obj, 'plan_json', None):
        raise HTTPException(status_code=404, detail='NO_PLAN — call POST /plan/start first')

    try:
        new_plan, _action = run_plan_turn(
            db=db,
            session_id=session_id,
            user_message=payload.content,
            target_item_id=target_item_id,
        )
    except NoMoreItems as exc:
        raise HTTPException(status_code=409, detail=f'PLAN_TERMINAL: {exc}') from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return PlanStateOut(**new_plan.model_dump(mode='json'))


@router.post('/sessions/{session_id}/plan/actions', response_model=PlanStateOut)
def post_plan_action(
    session_id: int,
    payload: AgentActionIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """Apply one AgentAction. Single mutation entrypoint for plan-mode.

    409 on stale version, 422 on illegal transition or audit failure."""
    from app.services.resume_copilot.plan import (
        AgentAction,
        EvidenceAuditFailed,
        IllegalTransition,
        StaleVersion,
        apply_action,
    )

    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)

    plan = _load_plan(session_obj)
    if plan is None:
        raise HTTPException(status_code=404, detail='NO_PLAN')

    try:
        action = AgentAction.model_validate(
            {'action': payload.action, 'item_id': payload.item_id, 'payload': payload.payload}
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f'INVALID_ACTION: {exc}') from exc

    try:
        new_plan = apply_action(plan, action, expected_version=payload.expected_version)
    except StaleVersion as exc:
        raise HTTPException(status_code=409, detail=f'STALE_VERSION: {exc}') from exc
    except IllegalTransition as exc:
        raise HTTPException(status_code=422, detail=f'ILLEGAL_TRANSITION: {exc}') from exc
    except EvidenceAuditFailed as exc:
        raise HTTPException(
            status_code=422,
            detail={
                'code': 'EVIDENCE_AUDIT_FAILED',
                'flags': [f.model_dump() for f in exc.flags],
            },
        ) from exc

    _save_plan(session_obj, new_plan)
    db.commit()
    db.refresh(session_obj)
    return PlanStateOut(**new_plan.model_dump(mode='json'))


# ── Memory endpoints ────────────────────────────────────────────────────────
# Phase 0 (P0-2 of main-workspace-redesign-2026-05-20). Surfaces
# account_memory rows grouped by the 8 canonical categories so the UI's
# 我的档案 panel (A-1 / A-2 / A-5) can render them, and lets authenticated
# users add an entry manually (later: edit / archive in P1).


@router.get(
    '/sessions/{session_id}/memory',
    response_model=MemoryGroupedOut,
)
def get_session_memory(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
) -> MemoryGroupedOut:
    """Return all non-archived ``account_memory`` rows for this session's
    owner, grouped by the 8 canonical categories.

    Demo session (``user_key == '__demo__'``) is publicly readable per the
    project convention but always yields empty buckets — demo/guest keys are
    multi-tenant and we refuse to write or surface memory there.
    """
    from app.services.memory.api_helpers import (
        MEMORY_CATEGORIES,
        list_entries_by_category,
    )

    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)

    grouped = list_entries_by_category(
        db,
        user_key=str(getattr(session_obj, 'user_key', '') or ''),
        include_archived=False,
    )
    # Cast each entry through MemoryEntryOut so the response schema validates.
    grouped_typed: dict[str, list[MemoryEntryOut]] = {
        cat: [MemoryEntryOut.model_validate(e) for e in grouped.get(cat, [])]
        for cat in MEMORY_CATEGORIES
    }
    return MemoryGroupedOut(
        session_id=session_id,
        user_key=str(getattr(session_obj, 'user_key', '') or ''),
        entries=grouped_typed,
    )


@router.post(
    '/sessions/{session_id}/memory',
    response_model=MemoryEntryOut,
    status_code=status.HTTP_201_CREATED,
)
def post_session_memory(
    session_id: int,
    payload: MemoryEntryCreateIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
) -> MemoryEntryOut:
    """Manually insert a row into ``account_memory`` for this session's
    owner. Demo session is blocked by ``_assert_not_demo``; guest sessions
    are blocked inside the dispatcher (reserved user_key)."""
    from app.services.memory.api_helpers import serialize_entry
    from app.services.memory.dispatcher import write_memory

    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)

    user_key = str(getattr(session_obj, 'user_key', '') or '')
    outcome = write_memory(
        db,
        user_key=user_key,
        category=payload.category,
        summary=payload.summary,
        payload=payload.payload,
        source_module='manual_api',
        source_session_id=session_id,
        raw_excerpt=payload.raw_excerpt,
        confidence=float(payload.confidence),
    )
    if outcome.action == 'validation_error':
        raise HTTPException(
            status_code=422,
            detail=f'MEMORY_VALIDATION_ERROR: {outcome.reason}',
        )
    if outcome.action == 'blocked':
        # Most likely flag_off (shouldn't happen post-Phase 0) or a reserved
        # user_key (guest/empty). Return 403 with the dispatcher's reason so
        # callers can tell apart "not authed" from "memory subsystem down".
        raise HTTPException(
            status_code=403,
            detail=f'MEMORY_BLOCKED: {outcome.reason}',
        )
    if outcome.row is None:
        raise HTTPException(
            status_code=500,
            detail='MEMORY_WRITE_NO_ROW',
        )
    return MemoryEntryOut.model_validate(serialize_entry(outcome.row))


# Phase 1 (BE-1 of main-workspace-redesign-2026-05-20). A-3 简: 学生可以
# 编辑 + 删除 自己 account_memory 中的条目 —— 不带 ⭐ 重要标记, 不带永久改写
# 历史。修改限于 summary + payload; 删除走软删 (is_archived=True) 保留审计。


def _get_memory_entry_for_session(
    db: Session,
    *,
    session: ResumeCopilotSession,
    entry_id: int,
):
    """Fetch one ``AccountMemory`` row that belongs to ``session``'s owner.

    Returns the ``AccountMemory`` row or raises 404. The 404 message is
    intentionally identical for "entry doesn't exist" and "entry exists but
    belongs to another user_key" — never leak existence of other users' rows.
    """
    from app.models import AccountMemory

    session_user_key = str(getattr(session, 'user_key', '') or '')
    row = (
        db.query(AccountMemory)
        .filter(
            AccountMemory.id == entry_id,
            AccountMemory.user_key == session_user_key,
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f'MEMORY_ENTRY_NOT_FOUND:{entry_id}',
        )
    return row


@router.patch(
    '/sessions/{session_id}/memory/{entry_id}',
    response_model=MemoryEntryOut,
)
def patch_session_memory_entry(
    session_id: int,
    entry_id: int,
    body: MemoryEntryPatchIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
) -> MemoryEntryOut:
    """Edit one memory entry. A-3 简: only ``summary`` / ``payload`` mutable.

    Guards (in order):
      - 404 if session unknown
      - 403 if X-Resume-User-Key doesn't match session owner
      - 403 if demo session (read-only by convention)
      - 404 if entry id doesn't exist OR belongs to another user_key
      - 422 if patched payload fails category-schema validation
      - 422 if both summary and payload are None (no-op)
    """
    from app.services.memory.api_helpers import serialize_entry
    from app.services.memory.schemas import validate_payload

    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)

    if body.summary is None and body.payload is None:
        raise HTTPException(
            status_code=422,
            detail='MEMORY_PATCH_EMPTY: at least one of summary / payload required',
        )

    row = _get_memory_entry_for_session(db, session=session_obj, entry_id=entry_id)

    # ── summary update ─────────────────────────────────────────────────────
    if body.summary is not None:
        cleaned = body.summary.strip()
        if not cleaned:
            raise HTTPException(
                status_code=422,
                detail='MEMORY_PATCH_EMPTY_SUMMARY',
            )
        if len(cleaned) > 200:
            cleaned = cleaned[:200]
        row.summary = cleaned

    # ── payload update (validated against category schema) ────────────────
    if body.payload is not None:
        category = str(row.category or '')
        try:
            validated = validate_payload(category, body.payload)
        except (ValueError, Exception) as exc:  # noqa: BLE001 — pydantic + ValueError both possible
            raise HTTPException(
                status_code=422,
                detail=f'MEMORY_PATCH_INVALID_PAYLOAD: {str(exc)[:300]}',
            )
        row.payload_json = validated.model_dump_json()

    # AccountMemory has no `updated_at` column — bump ``last_verified_at``
    # which carries the "I touched this row" semantic for read-side ordering.
    row.last_verified_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return MemoryEntryOut.model_validate(serialize_entry(row))


@router.delete(
    '/sessions/{session_id}/memory/{entry_id}',
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_session_memory_entry(
    session_id: int,
    entry_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
) -> Response:
    """Soft-delete a memory entry (``is_archived=True``).

    We never hard-delete — audit trail + Plan-Mode citations may reference
    the row id. Subsequent GET /memory filters archived rows out by default,
    so from the UI's perspective it disappears immediately.
    """
    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)

    row = _get_memory_entry_for_session(db, session=session_obj, entry_id=entry_id)

    # Idempotent: re-archiving an archived row is a no-op, still 204.
    if not bool(getattr(row, 'is_archived', False)):
        row.is_archived = True
        row.last_verified_at = datetime.utcnow()
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
