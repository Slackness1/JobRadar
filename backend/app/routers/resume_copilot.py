import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, UploadFile, status
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
    ApplyRewriteIn,
    ApplyRewriteOut,
    ChatMessageIn,
    DirectionTierResult,
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
from app.services.resume_copilot.workflow import run_resume_generate_workflow, run_resume_parse_workflow

router = APIRouter(prefix='/api/resume-copilot', tags=['resume-copilot'])


def _assert_not_demo(session: ResumeCopilotSession) -> None:
    if str(getattr(session, 'user_key', '') or '') == '__demo__':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Demo session is read-only',
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

    session = ResumeCopilotSession(
        file_name=file.filename or '',
        user_key=x_resume_user_key,
        status='parsing_profile',
        extracted_text=extracted_text,
        is_guest=1 if x_guest.strip().lower() in {'1', 'true', 'yes'} else 0,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    background_tasks.add_task(run_resume_parse_workflow, int(getattr(session, 'id')))
    return ResumeCopilotSessionCreatedOut(
        session_id=int(getattr(session, 'id')),
        status='parsing_profile',
        page_count=page_count,
        file_size_bytes=len(file_bytes),
    )


@router.get('/sessions/{session_id}', response_model=ResumeCopilotSessionOut)
def get_resume_copilot_session(session_id: int, db: Session = Depends(get_db)):
    session = _get_session_eager(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f'Resume copilot session {session_id} not found')
    return _build_session_out(session)


@router.patch('/sessions/{session_id}', response_model=ResumeCopilotSessionOut)
def rename_resume_copilot_session(
    session_id: int,
    payload: ResumeCopilotRenameIn,
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)
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
def delete_resume_copilot_session(session_id: int, db: Session = Depends(get_db)):
    session = _get_session_or_404(db, session_id)
    _assert_not_demo(session)
    db.delete(session)
    db.commit()


@router.get('/sessions/{session_id}/parsed-profile', response_model=ResumeParsedProfileOut)
def get_resume_copilot_parsed_profile(session_id: int, db: Session = Depends(get_db)):
    _get_session_or_404(db, session_id)
    profile = db.query(ResumeParsedProfile).filter(ResumeParsedProfile.session_id == session_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail=f'Parsed profile for session {session_id} not found')
    profile_json: Any = getattr(profile, 'profile_json', '{}') or '{}'
    return ResumeParsedProfileOut(
        session_id=session_id,
        profile=ResumeProfilePayload.model_validate(json.loads(str(profile_json))),
    )


@router.get('/sessions/{session_id}/confirmed-profile', response_model=ResumeConfirmedProfileOut)
def get_resume_copilot_confirmed_profile(session_id: int, db: Session = Depends(get_db)):
    _get_session_or_404(db, session_id)
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
    db: Session = Depends(get_db),
):
    session_obj = _get_session_or_404(db, session_id)
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


@router.get('/sessions/{session_id}/preferences', response_model=ResumePreferenceOut)
def get_resume_copilot_preferences(session_id: int, db: Session = Depends(get_db)):
    _get_session_or_404(db, session_id)
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
    db: Session = Depends(get_db),
):
    session_obj = _get_session_or_404(db, session_id)
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
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)
    _assert_not_demo(session)
    confirmed_profile = db.query(ResumeConfirmedProfile).filter(ResumeConfirmedProfile.session_id == session_id).first()
    if not confirmed_profile:
        raise HTTPException(status_code=409, detail='CONFIRMED_PROFILE_REQUIRED')

    recommendation_run = db.query(ResumeRecommendationRun).filter(ResumeRecommendationRun.session_id == session_id).first()
    if not recommendation_run:
        recommendation_run = ResumeRecommendationRun(session_id=session_id)
        db.add(recommendation_run)

    direction_run = db.query(ResumeDirectionAnalysisRun).filter(
        ResumeDirectionAnalysisRun.session_id == session_id
    ).first()
    if not direction_run:
        direction_run = ResumeDirectionAnalysisRun(session_id=session_id)
        db.add(direction_run)

    recommendation_run.status = 'running'
    recommendation_run.error_message = ''
    recommendation_run.used_ai = 0
    recommendation_run.fallback_reason = ''
    recommendation_run.recommendations_json = '[]'
    direction_run.status = 'running'
    direction_run.error_message = ''
    direction_run.directions_json = '[]'
    session.status = 'generating_recommendations'
    session.recommendation_status = 'running'
    session.feedback_status = 'running'
    session.error_message = ''
    db.commit()
    background_tasks.add_task(run_resume_generate_workflow, int(session_id))

    return ResumeGenerateOut(session_id=session_id, status='running')


@router.get('/sessions/{session_id}/recommendations', response_model=ResumeRecommendationResultOut)
def get_resume_copilot_recommendations(session_id: int, db: Session = Depends(get_db)):
    _get_session_or_404(db, session_id)
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
def get_direction_analysis(session_id: int, db: Session = Depends(get_db)):
    _get_session_or_404(db, session_id)
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
def get_chat_messages(session_id: int, db: Session = Depends(get_db)):
    _get_session_or_404(db, session_id)
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
    db: Session = Depends(get_db),
):
    from app.services.resume_copilot.chat import generate_chat_turn

    session_obj = _get_session_or_404(db, session_id)
    _assert_not_demo(session_obj)
    direction_run = db.query(ResumeDirectionAnalysisRun).filter(
        ResumeDirectionAnalysisRun.session_id == session_id
    ).first()
    if not direction_run or str(getattr(direction_run, 'status', '')) != 'completed':
        raise HTTPException(status_code=409, detail='DIRECTION_ANALYSIS_NOT_READY')

    try:
        return generate_chat_turn(session_id, payload.content, db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post('/sessions/{session_id}/chat/apply-rewrite', response_model=ApplyRewriteOut)
def post_apply_rewrite(
    session_id: int,
    payload: ApplyRewriteIn,
    db: Session = Depends(get_db),
):
    from app.services.resume_copilot.chat import apply_rewrite

    session_obj = _get_session_or_404(db, session_id)
    _assert_not_demo(session_obj)
    try:
        updated_profile = apply_rewrite(
            session_id, payload.message_id, payload.option_id, db
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ApplyRewriteOut(profile=updated_profile, applied=True)
