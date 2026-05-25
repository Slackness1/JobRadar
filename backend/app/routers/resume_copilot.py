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
    REJECT_REASON_LABELS,
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
    RecommendRejectIn,
    RecommendRejectOut,
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
    ResumeRecommendationPlatformsOut,
    RecommendNarrativeOut,
    ResumeRecommendationResultOut,
    RewriteOption,
    RewriteV0V2In,
    RewriteV0V2Out,
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
    # 配额闸 — 解析简历会跑 LLM,先挡一道
    from app.services.llm_quota import check_quota_or_raise
    check_quota_or_raise(db, x_resume_user_key)
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

    # Plan 1 (2026-05-20): compute which bullet field_paths changed vs the
    # previous confirmed snapshot — used to flag related memory rows as
    # needs_resync so the ArchivePanel surfaces a 🔄 badge.
    previous_profile_dict: dict | None = None
    if profile and profile.profile_json:
        try:
            previous_profile_dict = json.loads(str(profile.profile_json))
        except (json.JSONDecodeError, TypeError):
            previous_profile_dict = None

    if not profile:
        profile = ResumeConfirmedProfile(session_id=session_id)
        db.add(profile)
    new_profile_dict = payload.profile.model_dump()
    profile.profile_json = json.dumps(new_profile_dict)
    session = _get_session_or_404(db, session_id)
    session.updated_at = datetime.utcnow()
    db.commit()

    # Mark memory rows stale AFTER the profile commit so the diff sees the
    # actual saved state. Failures here must NOT poison the write — the
    # profile save already succeeded; sync is a best-effort signal.
    try:
        from app.services.memory.api_helpers import (
            diff_changed_field_paths,
            mark_memory_needs_resync,
        )
        changed_paths = diff_changed_field_paths(previous_profile_dict, new_profile_dict)
        if changed_paths:
            user_key = str(getattr(session_obj, 'user_key', '') or '')
            mark_memory_needs_resync(
                db, user_key=user_key, changed_field_paths=changed_paths,
            )
    except Exception:  # noqa: BLE001 — sync is best-effort
        pass

    # Plan ② (2026-05-21): first-time confirm → seed archive from parsed
    # bullets so plan-mode has something to deepen instead of starting cold.
    # Dispatcher dedupes by summary_hash, so re-uploading the same resume is
    # idempotent. Failures are swallowed inside the seeder.
    if previous_profile_dict is None:
        try:
            from app.services.resume_copilot.memory.seeding import seed_memory_from_profile
            from app.services.resume_copilot.memory.extractor import _resolve_active_track
            user_key = str(getattr(session_obj, 'user_key', '') or '')
            active_track = _resolve_active_track(db, session_id=session_id)
            seed_memory_from_profile(
                db, user_key=user_key, session_id=session_id,
                profile=new_profile_dict, active_track=active_track,
            )
        except Exception:  # noqa: BLE001 — seeding is best-effort
            pass

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
    response: Response,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """Save student preferences.

    2026-05-21 (B3 fix): canonicalize any free-text track strings that come
    in (persona JSON, faculty-typed docs, external imports) to one of the
    canonical SAIF MF tracks. Previously the recommend pipeline silently
    returned 0 items when an "外部" string like
    ``"卖方研究 TMT (sell-side research)"`` didn't match exactly. Now we
    map via ``canonicalize_track`` and surface a header
    ``X-Unknown-Tracks`` listing any inputs that didn't resolve so the
    frontend can show "你的赛道名 X 我们不识别, 已替换为 Y" toast instead
    of letting the student walk into a 0-rec dead end.
    """
    from app.services.taxonomy.canonical import (
        CANONICAL_FINANCE_TRACKS,
        canonicalize_track,
    )

    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)

    # Canonicalize preferred_tracks before persisting. Track strings that
    # don't map are echoed in X-Unknown-Tracks so the FE can warn the user.
    canon_set = set(CANONICAL_FINANCE_TRACKS)
    canon_tracks: list[str] = []
    unknown_tracks: list[str] = []
    seen: set[str] = set()
    for raw_track in (payload.preferences.preferred_tracks or []):
        raw_str = str(raw_track or '').strip()
        if not raw_str:
            continue
        canon = canonicalize_track(raw_str)
        if canon in canon_set:
            if canon not in seen:
                canon_tracks.append(canon)
                seen.add(canon)
        else:
            # Map failed — keep the raw value so the student doesn't silently
            # lose their intent, but flag it for the FE to surface.
            if raw_str not in seen:
                canon_tracks.append(raw_str)
                seen.add(raw_str)
                unknown_tracks.append(raw_str)
    normalized_prefs = payload.preferences.model_copy(
        update={'preferred_tracks': canon_tracks},
    )

    preference_profile = db.query(ResumePreferenceProfile).filter(ResumePreferenceProfile.session_id == session_id).first()
    if not preference_profile:
        preference_profile = ResumePreferenceProfile(session_id=session_id)
        db.add(preference_profile)
    preference_profile.preferences_json = json.dumps(normalized_prefs.model_dump())
    preference_profile.all_skipped = 1 if normalized_prefs.all_skipped else 0
    session = _get_session_or_404(db, session_id)
    session.updated_at = datetime.utcnow()
    db.commit()

    if unknown_tracks:
        # HTTP headers are latin-1 only — URL-encode the CJK characters so the
        # FE can decodeURIComponent() the value back to display the unknown
        # track names to the student.
        from urllib.parse import quote
        response.headers['X-Unknown-Tracks'] = ','.join(
            quote(t, safe='') for t in unknown_tracks
        )
    return ResumePreferenceOut(session_id=session_id, preferences=normalized_prefs)


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
    # 配额闸:超额直接 429
    from app.services.llm_quota import check_quota_or_raise
    check_quota_or_raise(db, x_resume_user_key)
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


@router.get(
    '/sessions/{session_id}/recommendations/platforms',
    response_model=ResumeRecommendationPlatformsOut,
)
def get_resume_copilot_recommendation_platforms(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """Phase 3 (2026-05-24) — 返回按公司聚合的"平台卡片"列表。

    数据源同 items endpoint(共用 ResumeRecommendationRun.recommendations_json),
    不重跑 LLM rerank。每个 platform 携带:
      - platform_score (max final_score)
      - n_jobs / n_campus / n_internship
      - n_xhs_insights (XHS 同辈情报数, 来自 KB)
      - top_jobs (top 3) + all_job_ids (全量, 给 FE expand 时反查 items)
      - priority_letter / tier_label / track_match_kind (best of jobs)
    """
    from app.services.resume_copilot.platform_aggregator import aggregate_by_company
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    recommendation_run = db.query(ResumeRecommendationRun).filter(
        ResumeRecommendationRun.session_id == session_id
    ).first()
    if not recommendation_run:
        raise HTTPException(status_code=404, detail=f'Recommendations for session {session_id} not found')

    recommendations_json: Any = getattr(recommendation_run, 'recommendations_json', '[]') or '[]'
    items = [
        ResumeRecommendationItem.model_validate(it)
        for it in json.loads(str(recommendations_json))
    ]
    platforms = aggregate_by_company(items, db=db)
    return ResumeRecommendationPlatformsOut(
        session_id=session_id,
        status=str(getattr(recommendation_run, 'status', '') or ''),
        platforms=platforms,
        n_total_jobs=len(items),
        used_ai=bool(getattr(recommendation_run, 'used_ai', 0)),
        fallback_reason=str(getattr(recommendation_run, 'fallback_reason', '') or ''),
    )


@router.get(
    '/sessions/{session_id}/recommendations/{job_id}/narrative',
    response_model=RecommendNarrativeOut,
)
def get_recommend_narrative(
    session_id: int,
    job_id: str,
    x_resume_user_key: str = Header(default=''),
    refresh: int = 0,
    db: Session = Depends(get_db),
):
    """Phase 7 (2026-05-25) — 推荐卡 LLM 个性化叙事。

    Inputs: session 的 confirmed_profile + recommendation_run 里对应 job_id 的
    ResumeRecommendationItem + 公司在 XHS 库里 top 5 high-conf insights。
    Output: narrative + action_tip + evidence_refs。
    Cache: 7 天,key=(user_key, job_id, profile_hash),简历改动自动失效。
    """
    from app.services.resume_copilot import narrative as narrative_svc
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)

    # Load confirmed profile (narrative 必须基于 confirmed,不是 parsed)
    cp = db.query(ResumeConfirmedProfile).filter(
        ResumeConfirmedProfile.session_id == session_id,
    ).first()
    if not cp:
        raise HTTPException(
            status_code=404,
            detail=f'Confirmed profile for session {session_id} not found',
        )
    profile_dict = json.loads(str(getattr(cp, 'profile_json', '{}') or '{}'))

    # Load recommendation item by job_id
    rec_run = db.query(ResumeRecommendationRun).filter(
        ResumeRecommendationRun.session_id == session_id,
    ).first()
    if not rec_run:
        raise HTTPException(
            status_code=404,
            detail=f'Recommendations for session {session_id} not found',
        )
    items_raw: Any = getattr(rec_run, 'recommendations_json', '[]') or '[]'
    items = json.loads(str(items_raw))
    job_item = next((it for it in items if str(it.get('job_id')) == str(job_id)), None)
    if not job_item:
        raise HTTPException(
            status_code=404,
            detail=f'Job {job_id} not found in session {session_id} recommendations',
        )

    payload = narrative_svc.generate(
        db,
        user_key=str(getattr(session, 'user_key', '') or x_resume_user_key or ''),
        job_item=job_item,
        profile=profile_dict,
        use_cache=(refresh == 0),
    )
    return RecommendNarrativeOut(
        narrative=payload.get('narrative', ''),
        action_tip=payload.get('action_tip', ''),
        evidence_refs=payload.get('evidence_refs', []),
        generated_at=payload.get('generated_at', ''),
        from_cache=bool(payload.get('_from_cache', False)),
        status=payload.get('_status', ''),
    )


@router.post(
    '/sessions/{session_id}/recommendations/{job_id}/reject',
    response_model=RecommendRejectOut,
)
def post_reject_recommendation(
    session_id: int,
    job_id: str,
    payload: RecommendRejectIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
) -> RecommendRejectOut:
    """BE-3 of main-workspace-redesign-2026-05-20 (D-2 / D-3): user ✗'d a job
    on the recommend rail.

    Effects:

    1. Validates ``payload.reason`` against the canonical 5-key map.
    2. Verifies ``job_id`` appeared in this session's most recent
       recommendations (anti-id-guessing). 404 if not.
    3. Writes an ``account_memory.preference`` row capturing
       company / job_id / reason / note / rejected_at.
    4. Appends ``job_id`` to ``ResumeCopilotSession.rejected_job_ids_json``
       (dedupe). The next ``recommend_jobs_for_profile`` call reads this list
       and filters those jobs out.
    5. Returns the inserted ``memory_entry_id`` (may be the same row id on
       second-press dedupe via the dispatcher's summary_hash refresh) and the
       updated ``rejected_count``.

    Demo session: 403 via ``_assert_not_demo``.
    Cross-session id guessing: 403 via ``_assert_session_owner``.
    Reject reason not in the 5-key set: 422.
    job_id not in the latest recommendations list for this session: 404.
    """
    from app.services.memory.dispatcher import write_memory
    from app.services.memory.schemas import PreferencePayload

    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)

    reason_key = (payload.reason or '').strip()
    if reason_key not in REJECT_REASON_LABELS:
        raise HTTPException(
            status_code=422,
            detail=f'INVALID_REJECT_REASON: must be one of {sorted(REJECT_REASON_LABELS)}',
        )
    reason_label = REJECT_REASON_LABELS[reason_key]

    # ── Verify job_id is in the most recent recommendations ─────────────────
    recommendation_run = db.query(ResumeRecommendationRun).filter(
        ResumeRecommendationRun.session_id == session_id
    ).first()
    if recommendation_run is None:
        raise HTTPException(
            status_code=404,
            detail=f'NO_RECOMMENDATIONS: session {session_id} has no recommendation run',
        )
    recs_raw = str(getattr(recommendation_run, 'recommendations_json', '[]') or '[]')
    try:
        recs_list = json.loads(recs_raw)
    except json.JSONDecodeError:
        recs_list = []
    rec_lookup = {
        str(rec.get('job_id', '')): rec
        for rec in recs_list
        if isinstance(rec, dict)
    }
    target = rec_lookup.get(str(job_id))
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f'JOB_NOT_IN_RECOMMENDATIONS: {job_id}',
        )
    company = str(target.get('company') or '') or '未知公司'

    # ── Write account_memory.preference ─────────────────────────────────────
    # PreferenceDimension is constrained to {city,industry,role,comp,
    # company_type,stage}; ``company_type`` is the closest fit for "this
    # company is not for me" without modifying the memory schema. Full
    # reject metadata (job_id / reason key / note / timestamp) is JSON-packed
    # into raw_excerpt so the 我的档案 UI can render it.
    rejected_at_iso = datetime.utcnow().isoformat()
    note = (payload.note or '').strip()
    raw_excerpt_payload = json.dumps(
        {
            'company': company,
            'job_id': str(job_id),
            'reason': reason_key,
            'reason_label': reason_label,
            'note': note,
            'rejected_at': rejected_at_iso,
        },
        ensure_ascii=False,
    )
    user_key = str(getattr(session_obj, 'user_key', '') or '')
    outcome = write_memory(
        db,
        user_key=user_key,
        category='preference',
        summary=f'不喜欢 {company} - {reason_label}',
        payload=PreferencePayload(dimension='company_type', value=company),
        source_module='recommend_reject',
        source_session_id=session_id,
        raw_excerpt=raw_excerpt_payload,
        confidence=1.0,
    )
    if outcome.action == 'validation_error':
        raise HTTPException(
            status_code=422,
            detail=f'MEMORY_VALIDATION_ERROR: {outcome.reason}',
        )
    if outcome.action == 'blocked':
        # Most likely flag_off (Phase 0 enabled it) or guest/empty user_key.
        # Either way we still want the rejected_job_ids list to update so the
        # session-level filter works — but we report the block so the caller
        # knows the档案 entry didn't persist.
        memory_entry_id: int | None = None
    else:
        memory_entry_id = int(outcome.row.id) if outcome.row is not None else None

    # ── Append to session.rejected_job_ids_json (dedupe) ────────────────────
    raw_rejected = getattr(session_obj, 'rejected_job_ids_json', None)
    try:
        current_rejected = json.loads(str(raw_rejected) if raw_rejected else '[]')
        if not isinstance(current_rejected, list):
            current_rejected = []
    except json.JSONDecodeError:
        current_rejected = []
    job_str = str(job_id)
    if job_str not in {str(j) for j in current_rejected}:
        current_rejected.append(job_str)
    session_obj.rejected_job_ids_json = json.dumps(current_rejected)
    session_obj.updated_at = datetime.utcnow()
    db.commit()

    return RecommendRejectOut(
        ok=True,
        memory_entry_id=memory_entry_id,
        rejected_count=len(current_rejected),
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
    from app.services.llm_quota import check_quota_or_raise
    check_quota_or_raise(db, x_resume_user_key)
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
        active_job_id=str(payload.active_job_id or ''),
    )
    return response


def _dispatch_student_kb_extraction(
    *, session_id: int, user_content: str, active_job_id: str = '',
) -> None:
    """BackgroundTasks entry point. Opens own SessionLocal because the request
    DB session is closed by the time this runs."""
    from app.database import SessionLocal
    from app.services.resume_copilot.memory.extractor import extract_for_chat_turn
    from app.services.llm_quota import set_current_user_key, reset_current_user_key

    db = SessionLocal()
    # session.user_key 在 task 调度时已固化在 DB 上,从 session 取 — BackgroundTask
    # 不继承请求 contextvar,所以在这里显式 set 一遍。
    sess = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
    user_key = str(getattr(sess, 'user_key', '') or '') if sess else ''
    _quota_token = set_current_user_key(user_key)
    try:
        extract_for_chat_turn(
            db, session_id=session_id, user_content=user_content,
            active_job_id=active_job_id,
        )
    except Exception:
        # Memory extraction failures must never surface to the user — log and drop.
        import logging
        logging.getLogger(__name__).exception(
            "student_kb extraction failed for session_id=%s", session_id
        )
    finally:
        db.close()
        reset_current_user_key(_quota_token)


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


# ─── Rewrite v0/v2 (C-1 thesis-aware, P1 BE-2) ───────────────────────────────

@router.post(
    '/sessions/{session_id}/rewrite/v0v2',
    response_model=RewriteV0V2Out,
)
def post_rewrite_v0_v2(
    session_id: int,
    payload: RewriteV0V2In,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """Generate v0 (echo) + v2 (thesis-aware) rewrite for one bullet.

    Empty memory → v2.needs_plan_mode=True, LLM not called. See
    ``propose_rewrite_v0_v2`` for the full pipeline + fabrication-warning
    semantics (C-5 red line: warnings are surfaced, never stripped).
    """
    from app.services.resume_copilot.chat import propose_rewrite_v0_v2

    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)

    return propose_rewrite_v0_v2(
        session_id,
        payload.bullet_text,
        payload.field_path,
        db,
        target_job_description=payload.target_job_description,
        target_title=payload.target_title,
        section=payload.section,
    )


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
    payload: PlanStartIn = PlanStartIn(),
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """Bootstrap the plan from the fixed template + parsed counts.

    Returns 409 if a plan already exists (clients should call GET first).
    Lands the session in ``plan_status=awaiting_plan_approval`` — user
    reviews/edits, then calls /plan/approve to enter the clarify loop.

    ``payload.focus_id`` (account_memory entry id) is resolved to a plan item
    via the memory row's ``linked_field_paths``, so the student who picked
    "中金 IBD" in PlanFocusPicker actually anchors on that internship's plan
    item rather than the first one.
    """
    from app.services.resume_copilot.plan import ItemKind, init_plan_from_template
    from app.services.resume_copilot.tag_extractor import attach_parsed_evidence
    from app.models import AccountMemory

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

    # ── focus_id → plan item resolution ─────────────────────────────────────
    # FE picker passes the memory entry id; parser_seed rows stored a
    # linked_field_paths array like ["internships.0.bullets.0", ...]. The
    # first segment ("internships" / "projects") + index tells us which
    # parent-level plan item to anchor on. parent-level plan items are
    # ordered by (kind, i) inside init_plan_from_template, so the i-th
    # internship-kind parent is the match for "internships.<i>.*".
    focus_item_id: str | None = None
    if payload.focus_id is not None:
        user_key = str(getattr(session_obj, 'user_key', '') or '')
        mem_row = (
            db.query(AccountMemory)
            .filter(
                AccountMemory.id == int(payload.focus_id),
                AccountMemory.user_key == user_key,
            )
            .first()
        )
        if mem_row is not None:
            try:
                raw_paths = json.loads(mem_row.linked_field_paths or '[]')
            except json.JSONDecodeError:
                raw_paths = []
            kind_index: tuple[str, int] | None = None
            for p in raw_paths:
                parts = str(p or '').split('.')
                if len(parts) < 2:
                    continue
                head, idx_str = parts[0], parts[1]
                try:
                    idx = int(idx_str)
                except ValueError:
                    continue
                if head == 'internships':
                    kind_index = ('internship', idx)
                    break
                if head == 'projects':
                    kind_index = ('project', idx)
                    break
                if head == 'education':
                    kind_index = ('education', idx)
                    break
            if kind_index is not None:
                kind_str, idx = kind_index
                try:
                    target_kind = ItemKind(kind_str)
                except ValueError:
                    target_kind = None
                if target_kind is not None:
                    same_kind_parents = [
                        it for it in plan.items
                        if it.parent_id is None and it.kind == target_kind
                    ]
                    if 0 <= idx < len(same_kind_parents):
                        focus_item_id = same_kind_parents[idx].id

    # Fallback: first parent-level item — keeps coach UI from rendering blank
    # for legacy callers / focus_id that doesn't resolve.
    if focus_item_id is None:
        first_parent = next(
            (it for it in plan.items if it.parent_id is None),
            None,
        )
        if first_parent is not None:
            focus_item_id = first_parent.id

    if focus_item_id is not None:
        plan.current_item_id = focus_item_id

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


@router.delete(
    '/sessions/{session_id}/plan',
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_plan(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
) -> Response:
    """Clear the existing plan_json so a fresh /plan/start can run.

    Added 2026-05-21: students were getting stuck when an old session had a
    stale plan (clarifying with current_item_id=None) — /plan/start would
    409 PLAN_ALREADY_EXISTS, /plan/turn had nothing meaningful to do, and
    they sat there waiting. With DELETE the FE can wipe + restart with the
    right focus_id."""
    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)

    if getattr(session_obj, 'plan_json', None) or getattr(session_obj, 'plan_status', None):
        session_obj.plan_json = None
        session_obj.plan_status = 'idle'
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


from pydantic import BaseModel as _BaseModel  # H 2026-05-22

class PlanDistillOut(_BaseModel):
    """H 2026-05-22: 入档前 LLM 精炼输出, FE 拿这个 POST /memory.

    把 plan item.draft.text + 所有 evidence.text 提炼成:
    - summary: 干净一句话标题 (≤ 120 字, 公司 · 角色 · 1 个 outcome)
    - star: 4 段 STAR 分别
    - quantified: {metric: value} dict, 去重
    - raw_excerpt_clean: 去重后的"原话出处", 不含聊天回声
    """
    summary: str
    star: dict[str, str] = {}
    quantified: dict[str, str] = {}
    raw_excerpt_clean: str = ''
    used_evidence_ids: list[str] = []


@router.post(
    '/sessions/{session_id}/plan/distill',
    response_model=PlanDistillOut,
)
def post_plan_distill(
    session_id: int,
    item_id: str | None = None,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
) -> PlanDistillOut:
    """H 2026-05-22: 学生反馈"入档时有很多重复的原话, 应该让 LLM 精炼"。

    FE 在 handleArchiveDraft 之前调这个, 拿到 distilled payload 后再 POST
    /memory。 BE 这里用 LLM 把 draft + evidence 精炼成结构化档案条目。
    """
    from app.services.resume_copilot.archive_distill import distill_for_archive

    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)

    plan = _load_plan(session_obj)
    if plan is None:
        raise HTTPException(status_code=404, detail='NO_PLAN')

    target_item = None
    if item_id:
        target_item = next((it for it in plan.items if it.id == item_id), None)
    if target_item is None and plan.current_item_id:
        target_item = next((it for it in plan.items if it.id == plan.current_item_id), None)
    if target_item is None:
        raise HTTPException(status_code=404, detail='ITEM_NOT_FOUND')
    if target_item.draft is None:
        raise HTTPException(status_code=409, detail='ITEM_HAS_NO_DRAFT')

    distilled = distill_for_archive(
        item_title=target_item.title or '',
        draft_text=target_item.draft.text,
        evidence_texts=[ev.text for ev in target_item.evidence if ev.text],
    )
    return PlanDistillOut(**distilled)


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
    # Plan 1 (2026-05-20): an explicit PATCH means the student dealt with
    # whatever changed → clear the 🔄 resync flag so the ArchivePanel badge
    # disappears. Re-sync naturally re-triggers if they later edit the
    # bullet again.
    row.needs_resync = False
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
