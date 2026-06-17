import json
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, UploadFile, status
from fastapi.responses import Response
from urllib.parse import quote
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    HubConversation,
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
    DeepOptimizeStartIn,
    DeepOptimizeWriteBackOut,
    DirectionTierResult,
    MemoryEntryCreateIn,
    MemoryEntryOut,
    MemoryEntryPatchIn,
    MemoryGroupedOut,
    PlanStartIn,
    PlanStateOut,
    JobStateIn,
    JobStateOut,
    MyJobItem,
    MyJobsCounts,
    MyJobsOut,
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
    ResumeJobModeOut,
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
    ScoreReportOut,
    ScoreRequestIn,
)
from pydantic import BaseModel
from app.services.resume_copilot import score_task as _score_task_mod
from app.services.resume_copilot import scoring as _scoring_mod
from app.services.resume_copilot import translator as translator_svc
from app.services.resume_copilot.scoring import derive_target_track, score_resume
from app.services.resume_copilot.demo_session import DEMO_SESSION_ID
from app.services.resume_copilot.ingest import ResumeUploadError, extract_resume_text_with_page_count, validate_pdf_upload
from app.services.resume_copilot.pdf_export import FontsNotInstalledError, render_resume_pdf
from app.services.resume_copilot.state import INFLIGHT_GUARD_SECONDS, RunStatus, SessionStatus
from app.services.resume_copilot.workflow import run_resume_generate_workflow, run_resume_parse_workflow
from app.config import RECOMMENDATION_V2_ENABLED
from app.services.llm_json import deepseek_json_fn

import logging

log = logging.getLogger(__name__)

router = APIRouter(prefix='/api/resume-copilot', tags=['resume-copilot'])


GUEST_SESSION_TTL = timedelta(hours=24)
USER_SESSION_TTL = timedelta(days=7)


def _load_profile_and_prefs(
    db: Session, session_id: int
) -> tuple[ResumeProfilePayload, ResumePreferencePayload | None]:
    """重建 session 的 profile (confirmed 优先, 否则 parsed) + preferences。"""
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
    profile = ResumeProfilePayload()
    if source:
        profile_json: Any = getattr(source, 'profile_json', '{}') or '{}'
        profile = ResumeProfilePayload.model_validate(json.loads(str(profile_json)))
    pref_row = (
        db.query(ResumePreferenceProfile)
        .filter(ResumePreferenceProfile.session_id == session_id)
        .first()
    )
    preferences = None
    if pref_row is not None:
        pref_json: Any = getattr(pref_row, 'preferences_json', '{}') or '{}'
        preferences = ResumePreferencePayload.model_validate(json.loads(str(pref_json)))
    return profile, preferences


def _platforms_preferred_sub_cats(db: Session, session_id: int) -> list[str]:
    """重建 profile + preferences → v2 目标 sub_cat 列表 (给平台栏公司兜底用)。"""
    profile, preferences = _load_profile_and_prefs(db, session_id)
    from app.services.resume_copilot.recommendation import _v2_extract_preferred_sub_cats
    return _v2_extract_preferred_sub_cats(profile, preferences)


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


def _json_list_or_empty(raw: Any) -> list[Any]:
    """Parse a JSON list field defensively for read-side availability checks."""
    try:
        parsed = json.loads(str(raw or '[]'))
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _recommendation_run_has_visible_items(run: ResumeRecommendationRun | None) -> bool:
    """A recommendation run is usable only when it has completed, visible items.

    Existence of the row is not enough: generate creates the row before work
    starts, and failed/stale runs may leave ``recommendations_json=[]``. Treating
    those as ready makes the frontend enter the platform skeleton view even
    though there is nothing to hydrate it with.
    """
    if run is None:
        return False
    if str(getattr(run, 'status', '') or '') != RunStatus.COMPLETED.value:
        return False
    return len(_json_list_or_empty(getattr(run, 'recommendations_json', '[]'))) > 0


def _recommendation_run_is_stale(run: ResumeRecommendationRun | None) -> bool:
    if run is None or str(getattr(run, 'status', '') or '') != RunStatus.RUNNING.value:
        return False
    last_heartbeat = getattr(run, 'updated_at', None) or getattr(run, 'created_at', None)
    if last_heartbeat is None:
        return False
    return datetime.utcnow() - last_heartbeat >= timedelta(seconds=INFLIGHT_GUARD_SECONDS)


def _build_session_out(session: ResumeCopilotSession) -> ResumeCopilotSessionOut:
    recommendation_run = getattr(session, 'recommendation_run', None)
    recommendation_is_stale = _recommendation_run_is_stale(recommendation_run)
    recommendation_status = str(getattr(session, 'recommendation_status', '') or '')
    feedback_status = str(getattr(session, 'feedback_status', '') or '')
    session_status = str(getattr(session, 'status', '') or '')
    if recommendation_is_stale:
        recommendation_status = RunStatus.FAILED.value
        if feedback_status == RunStatus.RUNNING.value:
            feedback_status = RunStatus.FAILED.value
        if session_status == SessionStatus.GENERATING_RECOMMENDATIONS.value:
            session_status = (
                SessionStatus.COMPLETED.value
                if session.confirmed_profile is not None or session.parsed_profile is not None
                else SessionStatus.FAILED.value
            )
    return ResumeCopilotSessionOut(
        id=int(getattr(session, 'id')),
        file_name=str(getattr(session, 'file_name', '') or ''),
        name=str(getattr(session, 'name', '') or ''),
        status=session_status,
        error_message=str(getattr(session, 'error_message', '') or ''),
        recommendation_status=recommendation_status,
        feedback_status=feedback_status,
        has_parsed_profile=session.parsed_profile is not None,
        has_confirmed_profile=session.confirmed_profile is not None,
        has_preferences=session.preference_profile is not None,
        has_recommendations=_recommendation_run_has_visible_items(recommendation_run),
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
        .options(
            joinedload(ResumeCopilotSession.recommendation_run),
            joinedload(ResumeCopilotSession.confirmed_profile),
            joinedload(ResumeCopilotSession.parsed_profile),
            joinedload(ResumeCopilotSession.preference_profile),
        )
        .filter(ResumeCopilotSession.user_key == x_resume_user_key)
        .order_by(ResumeCopilotSession.updated_at.desc())
        .limit(20)
        .all()
    )
    # 「聊过」= hub_conversations 表里有这份简历名下的对话(批量一查, 不逐行打 DB)
    conversed_ids: set[int] = set()
    if rows:
        conversed_ids = {
            int(sid)
            for (sid,) in db.query(HubConversation.session_id)
            .filter(HubConversation.session_id.in_([int(r.id) for r in rows]))
            .distinct()
        }
    return [
        ResumeCopilotSessionListItem(
            id=int(getattr(r, 'id')),
            file_name=str(getattr(r, 'file_name', '') or ''),
            name=str(getattr(r, 'name', '') or ''),
            status=str(getattr(r, 'status', '') or ''),
            has_recommendations=_recommendation_run_has_visible_items(r.recommendation_run),
            has_conversation=int(getattr(r, 'id')) in conversed_ids,
            is_archived=bool(getattr(r, 'is_archived', False) or False),
            created_at=getattr(r, 'created_at', None),
            updated_at=getattr(r, 'updated_at', None),
            **_session_card_summary(r),
        )
        for r in rows
    ]


def _session_card_summary(r: ResumeCopilotSession) -> dict[str, Any]:
    """会话列表卡片摘要 (赛道 / 公司数 / 岗位数 / Top公司 / 缩略图段落)。

    全程 try/except 兜底 — 任何一段解析失败都退回默认空值, 绝不让列表 500。
    数据全来自已 joinedload 的关系, 不额外打 DB。
    """
    out: dict[str, Any] = {
        'track': '', 'n_companies': 0, 'n_jobs': 0,
        'top_companies': [], 'thumb_name': '', 'thumb_sections': [],
    }
    # 已选赛道
    try:
        pp = getattr(r, 'preference_profile', None)
        if pp and getattr(pp, 'preferences_json', None):
            tracks = (json.loads(pp.preferences_json) or {}).get('preferred_tracks') or []
            if tracks:
                out['track'] = str(tracks[0])
    except Exception:
        pass
    # 简历缩略图 (确认版优先于解析版)
    try:
        prof_row = getattr(r, 'confirmed_profile', None) or getattr(r, 'parsed_profile', None)
        if prof_row and getattr(prof_row, 'profile_json', None):
            prof = json.loads(prof_row.profile_json) or {}
            bi = prof.get('basic_info') or {}
            out['thumb_name'] = str(bi.get('name') or bi.get('full_name') or '')
            secs: list[dict[str, Any]] = []
            interns = prof.get('internships') or []
            if interns:
                nb = sum(len(i.get('bullets') or []) for i in interns) or len(interns)
                secs.append({'label': '实习经历', 'bullets': max(1, min(nb, 5))})
            edu = prof.get('education') or []
            if edu:
                secs.append({'label': '教育背景', 'bullets': max(1, min(len(edu), 3))})
            skills = prof.get('skills') or {}
            n_skill = (
                len((skills.get('technical') or []) + (skills.get('tools') or []))
                if isinstance(skills, dict) else 0
            )
            if n_skill:
                secs.append({'label': '技能', 'bullets': max(1, min(n_skill // 3 or 1, 3))})
            out['thumb_sections'] = secs
    except Exception:
        pass
    # 推荐统计 (公司数 / 岗位数 / Top公司)
    try:
        rr = getattr(r, 'recommendation_run', None)
        raw = getattr(rr, 'recommendations_json', None) if rr else None
        items = json.loads(raw) if raw else []
        if isinstance(items, list) and items:
            out['n_jobs'] = len(items)
            companies: list[str] = []
            for it in items:
                c = str((it or {}).get('company') or '').strip()
                if c and c not in companies:
                    companies.append(c)
            out['n_companies'] = len(companies)
            out['top_companies'] = companies[:4]
    except Exception:
        pass
    return out


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


# 每账号"在使用中"(非归档)简历上限。归档的不算占额 — 想试新赛道归档一份即可腾位。
MAX_ACTIVE_SESSIONS = 3


def _active_session_count(db: Session, user_key: str) -> int:
    return (
        db.query(ResumeCopilotSession)
        .filter(
            ResumeCopilotSession.user_key == user_key,
            ResumeCopilotSession.is_archived.is_(False),
        )
        .count()
    )


@router.post(
    '/sessions/{session_id}/duplicate',
    response_model=ResumeCopilotSessionListItem,
    status_code=status.HTTP_201_CREATED,
)
def duplicate_resume_copilot_session(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """复制一份会话: 克隆 解析简历 / 确认简历 / 偏好 / 推荐快照 到新会话(名字加 '· 副本')。

    记忆(account_memory)目前是账号级共享, 不随复制搬;会话级记忆改造后再让复制
    一并搬该会话的记忆行。受 MAX_ACTIVE_SESSIONS 在用上限约束。
    """
    src = _get_session_or_404(db, session_id)
    _assert_session_owner(src, x_resume_user_key)
    key = (x_resume_user_key or '').strip()
    if not key:
        raise HTTPException(status_code=400, detail='缺少用户标识, 无法复制')
    if _active_session_count(db, key) >= MAX_ACTIVE_SESSIONS:
        raise HTTPException(
            status_code=409,
            detail=f'在使用中的简历已达上限 {MAX_ACTIVE_SESSIONS} 份, 请先删除或归档一份再复制',
        )

    base_name = (
        str(getattr(src, 'name', '') or getattr(src, 'file_name', '') or f'会话 #{session_id}').strip()
    )
    dup = ResumeCopilotSession(
        file_name=str(getattr(src, 'file_name', '') or ''),
        name=f'{base_name} · 副本',
        user_key=key,
        status=str(getattr(src, 'status', 'uploaded') or 'uploaded'),
        extracted_text=str(getattr(src, 'extracted_text', '') or ''),
        recommendation_status=str(getattr(src, 'recommendation_status', 'pending') or 'pending'),
        is_guest=int(getattr(src, 'is_guest', 0) or 0),
        rejected_job_ids_json=str(getattr(src, 'rejected_job_ids_json', '[]') or '[]'),
        is_archived=False,
    )
    db.add(dup)
    db.flush()  # 拿到 dup.id

    if src.parsed_profile is not None:
        db.add(ResumeParsedProfile(session_id=dup.id, profile_json=src.parsed_profile.profile_json))
    if src.confirmed_profile is not None:
        db.add(ResumeConfirmedProfile(session_id=dup.id, profile_json=src.confirmed_profile.profile_json))
    if src.preference_profile is not None:
        db.add(ResumePreferenceProfile(
            session_id=dup.id, preferences_json=src.preference_profile.preferences_json,
        ))
    if src.recommendation_run is not None:
        rr = src.recommendation_run
        db.add(ResumeRecommendationRun(
            session_id=dup.id,
            recommendations_json=getattr(rr, 'recommendations_json', '[]'),
            agent_trace_json=getattr(rr, 'agent_trace_json', '[]'),
            status=getattr(rr, 'status', ''),
            used_ai=getattr(rr, 'used_ai', 0),
            fallback_reason=getattr(rr, 'fallback_reason', ''),
            error_message=getattr(rr, 'error_message', ''),
        ))
    db.commit()
    db.refresh(dup)
    return ResumeCopilotSessionListItem(
        id=int(dup.id),
        file_name=str(dup.file_name or ''),
        name=str(dup.name or ''),
        status=str(dup.status or ''),
        has_recommendations=_recommendation_run_has_visible_items(dup.recommendation_run),
        is_archived=False,
        created_at=dup.created_at,
        updated_at=dup.updated_at,
        **_session_card_summary(dup),
    )


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


def _load_score_inputs(
    db: Session, session_id: int, raw_target: str
) -> tuple[ResumeProfilePayload, ResumePreferencePayload | None, str]:
    """同步 /score 与后台 /score/start 共用的画像 + 偏好 + 目标赛道装载。"""
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
        raise HTTPException(status_code=404, detail='No resume profile available to score')

    profile = ResumeProfilePayload.model_validate(json.loads(str(source.profile_json or '{}')))

    preferences = None
    pref_row = (
        db.query(ResumePreferenceProfile)
        .filter(ResumePreferenceProfile.session_id == session_id)
        .first()
    )
    if pref_row is not None:
        preferences = ResumePreferencePayload.model_validate(
            json.loads(str(getattr(pref_row, 'preferences_json', '{}') or '{}'))
        )
        preferences.all_skipped = bool(getattr(pref_row, 'all_skipped', 0))

    target = (raw_target or '').strip() or derive_target_track(profile, preferences)
    return profile, preferences, target


@router.post('/sessions/{session_id}/score', response_model=ScoreReportOut)
def score_resume_session(
    session_id: int,
    body: ScoreRequestIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """多维度诚实打分 (B1)。只读,不写库 — demo 简历也可打分。

    同步阻塞版, 留作兼容; Hub 走 /score/start + /score/status 任务制。
    """
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    profile, preferences, target = _load_score_inputs(db, session_id, body.target_track)

    # 模块级 provider 钩子,测试可 monkeypatch _scoring_mod.OpenAICompatibleResumeScorer。
    provider = _scoring_mod.OpenAICompatibleResumeScorer()
    report = score_resume(db, profile, target, preferences=preferences, provider=provider)

    return ScoreReportOut(
        session_id=session_id,
        target_track=report.target_track,
        overall_current=report.overall_current,
        overall_potential_low=report.overall_potential_low,
        overall_potential_high=report.overall_potential_high,
        summary=report.summary,
        dimensions=report.dimensions,
        section_gaps=report.section_gaps,
        used_ai=report.used_ai,
    )


class ScoreStartIn(BaseModel):
    target_track: str = ''
    # force=True 重打(用户明确再要一次); 默认复用 running/done 任务, 一次交互只打一遍 LLM。
    force: bool = False
    # 可选: 直接打这份简历(编辑器「重新打分」打的是当前版本的简历快照, 而非库里 confirmed)。
    # 空=按库里 confirmed/parsed。给了 profile 时一般同时 force=True, 才不会复用旧缓存。
    profile: dict[str, Any] | None = None


@router.post('/sessions/{session_id}/score/start', status_code=status.HTTP_202_ACCEPTED)
def start_score_task(
    session_id: int,
    body: ScoreStartIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """启动后台打分任务(立即返回)。

    打分在服务端线程跑 —— 学生切对话/跳页都不中断(Hub「后台继续跑」的根);
    浏览器不再被 90s 长请求占连接池(修「返回工作台点不动」)。只读不写库,
    demo 简历也可打。body.profile 给了就打这份(编辑器版本快照), 否则按库里画像。
    """
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    profile, preferences, target = _load_score_inputs(db, session_id, body.target_track)
    if body.profile is not None:
        # 编辑器「重新打分」: 打当前版本的简历快照(可能与库里 confirmed 不同)。
        profile = ResumeProfilePayload.model_validate(body.profile)
        target = (body.target_track or '').strip() or derive_target_track(profile, preferences)
    snap = _score_task_mod.start_score_task(
        session_id, profile, target, preferences, force=bool(body.force)
    )
    return {"session_id": session_id, **{k: v for k, v in snap.items() if k != 'report'}}


@router.get('/sessions/{session_id}/score/status')
def get_score_task_status(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """轮询打分任务真实进度。status: none|running|done|failed; stage: prepare|llm|parse|done。

    done 时带完整报告(服务端缓存)— 对话结果卡 / 报告面板 / 编辑页共用同一份,
    不再各打一遍 LLM、也不再互相对不上(修「对话出了报告, 面板还在打分中」)。
    """
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    return {"session_id": session_id, **_score_task_mod.get_task_snapshot(session_id)}


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
    # Phase G G2-B — 学生没显式设阶段时, 从简历毕业时间智能预填 (不落库, 确认页选择器拿来当默认选中)
    if not (preferences.job_stage or '').strip():
        try:
            profile, _ = _load_profile_and_prefs(db, session_id)
            from app.services.phase_g.recommendation_v2.job_mode import (
                STAGE_UNKNOWN,
                infer_stage_from_education,
            )
            edu = [e.model_dump() for e in (profile.education or [])]
            guess = infer_stage_from_education(edu)
            if guess != STAGE_UNKNOWN:
                preferences.job_stage = guess
        except Exception:
            log.exception('job_stage prefill failed for session %s', session_id)
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
    # EXTRA_SELECTABLE_TRACKS = 非金融但可选(互联网/AI), 放行不弹"不识别"提示。
    from app.services.phase_g.track_subcat_map import EXTRA_SELECTABLE_TRACKS
    canon_set = set(CANONICAL_FINANCE_TRACKS) | set(EXTRA_SELECTABLE_TRACKS)
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


@router.post('/sessions/{session_id}/deep-optimize/start', response_model=PlanStateOut)
def post_deep_optimize_start(
    session_id: int,
    payload: DeepOptimizeStartIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """从打分逐段缺口进入深度优化:播种聚焦该段的单 item plan(覆盖现有 plan),
    返回 PlanStateOut(首问已对齐目标 subcat)。后续反问走现成 /plan/turn,
    改写写回走现成 /chat/apply-rewrite。写接口 → owner + not_demo 守卫。"""
    from app.services.resume_copilot.deep_optimize import (
        section_source_texts,
        seed_plan_from_gap,
    )

    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)

    # 该段简历原文入证据池(STRONG)——否则审计铁律会逼学生把简历重新口述一遍。
    source_texts: list[str] = []
    confirmed = session_obj.confirmed_profile
    parsed = session_obj.parsed_profile
    raw = ''
    if confirmed is not None and (confirmed.profile_json or '').strip():
        raw = confirmed.profile_json
    elif parsed is not None:
        raw = parsed.profile_json or ''
    if raw.strip():
        try:
            seed_profile = ResumeProfilePayload.model_validate(json.loads(raw))
            source_texts = section_source_texts(seed_profile, payload.section)
        except (ValueError, TypeError):
            source_texts = []

    plan = seed_plan_from_gap(
        section=payload.section,
        label=payload.label,
        gap_tags=payload.gaps,
        gap_detail=payload.detail,
        target_track=payload.target_track,
        source_texts=source_texts,
    )
    _save_plan(session_obj, plan)
    session_obj.updated_at = datetime.utcnow()
    db.commit()
    return PlanStateOut(**plan.model_dump(mode='json'))


@router.post('/sessions/{session_id}/deep-optimize/write-back', response_model=DeepOptimizeWriteBackOut)
def post_deep_optimize_write_back(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """深度优化写回:把当前 item 的 finalized draft 写进 confirmed profile 对应段落,
    返回更新后的 profile(前端据 section 高亮"AI 刚写回")。写接口 → owner + not_demo。"""
    from app.services.resume_copilot.deep_optimize import write_back_current_draft

    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)

    plan = _load_plan(session_obj)
    if plan is None:
        raise HTTPException(status_code=404, detail='NO_PLAN — 先 POST /deep-optimize/start')

    confirmed = session_obj.confirmed_profile
    parsed = session_obj.parsed_profile
    raw = ''
    if confirmed is not None and (confirmed.profile_json or '').strip():
        raw = confirmed.profile_json
    elif parsed is not None:
        raw = parsed.profile_json or ''
    profile = ResumeProfilePayload.model_validate(json.loads(raw or '{}'))

    try:
        new_plan, updated, section = write_back_current_draft(plan, profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if confirmed is None:
        confirmed = ResumeConfirmedProfile(session_id=session_id)
        db.add(confirmed)
    confirmed.profile_json = updated.model_dump_json()
    _save_plan(session_obj, new_plan)
    session_obj.updated_at = datetime.utcnow()
    db.commit()
    return DeepOptimizeWriteBackOut(profile=updated, section=section, applied=True)


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
    from app.services.resume_copilot.platform_aggregator import (
        aggregate_by_company,
        merge_fallback_companies,
    )
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

    # Phase G G2-C (2026-05-29): v2 开启时, 秋招前岗位稀, 把目标赛道的 must_have
    # 头部公司补进"平台"栏 (live 卡没覆盖到的), 让公司推荐这栏在岗位少时也丰满。
    if RECOMMENDATION_V2_ENABLED:
        try:
            preferred_sub_cats = _platforms_preferred_sub_cats(db, session_id)
            if preferred_sub_cats:
                _n_before = len(platforms)
                platforms = merge_fallback_companies(platforms, preferred_sub_cats)
                # 公司兜底触发埋点 — 补进了几家 = live 岗对这些 sub_cat 的覆盖缺口大小。
                _n_added = len(platforms) - _n_before
                if _n_added > 0:
                    from app.services.telemetry import record_event

                    record_event(
                        'company_fallback', session_id=session_id,
                        purpose='platforms',
                        detail={'added': _n_added, 'sub_cats': list(preferred_sub_cats)[:10]},
                    )
        except Exception:
            log.exception('merge_fallback_companies failed for session %s', session_id)

    return ResumeRecommendationPlatformsOut(
        session_id=session_id,
        status=str(getattr(recommendation_run, 'status', '') or ''),
        platforms=platforms,
        n_total_jobs=len(items),
        used_ai=bool(getattr(recommendation_run, 'used_ai', 0)),
        fallback_reason=str(getattr(recommendation_run, 'fallback_reason', '') or ''),
    )


@router.get('/sessions/{session_id}/job-mode', response_model=ResumeJobModeOut)
def get_resume_copilot_job_mode(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """Phase G G2-D — 求职模式判定 (实习/全职/both) + 默认 tab + 解释 banner。

    时点(学生阶段) × 主目标赛道门槛 × 经历匹配 → 模式。阶段优先用偏好里显式设的,
    否则从简历毕业时间推 (stage_inferred=True 提示前端这是猜的、可改)。
    """
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)

    from app.services.phase_g.recommendation_v2.job_mode import (
        STAGE_UNKNOWN,
        effective_job_stage,
        normalize_stage,
        resolve_job_mode,
        stage_label,
    )
    from app.services.resume_copilot.recommendation import _v2_extract_preferred_sub_cats

    profile, preferences = _load_profile_and_prefs(db, session_id)
    stage = effective_job_stage(preferences, profile)
    explicit = bool(preferences and normalize_stage(getattr(preferences, 'job_stage', '') or '') != STAGE_UNKNOWN)

    preferred = _v2_extract_preferred_sub_cats(profile, preferences)
    primary = preferred[0] if preferred else ''

    # 经历匹配: 从已生成的推荐 items 里取主目标赛道的 track_match_kind, 取不到默认 transferable
    match_kind = 'transferable'
    run = db.query(ResumeRecommendationRun).filter(
        ResumeRecommendationRun.session_id == session_id
    ).first()
    if run and getattr(run, 'recommendations_json', None):
        try:
            raw_items = json.loads(str(run.recommendations_json))
            top_for_primary = next(
                (it for it in raw_items if it.get('matched_track_label') == primary), None
            )
            chosen = top_for_primary or (raw_items[0] if raw_items else None)
            if chosen and chosen.get('track_match_kind'):
                match_kind = str(chosen['track_match_kind'])
        except Exception:
            pass

    jm = resolve_job_mode(stage, primary or '该赛道', match_kind)
    return ResumeJobModeOut(
        session_id=session_id,
        stage=jm.stage,
        stage_label=stage_label(jm.stage),
        stage_inferred=not explicit,
        primary_sub_cat=primary,
        mode=jm.mode,
        mode_label=jm.mode_label,
        default_tab=jm.default_tab,
        advice_text=jm.advice_text,
        advice_evidence=jm.advice_evidence,
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
        narrative_short=payload.get('narrative_short', ''),
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

    # 推荐 2.0:同源写新状态表(dismissed),便于"我的岗位"聚合 + 轮换排除。
    # 不改既有 account_memory / rejected_job_ids_json 行为。
    try:
        from app.services.resume_copilot import job_state as js
        if user_key:
            js.set_explicit_state(db, user_key, str(job_id), js.STATE_DISMISSED, source_session_id=session_id)
    except Exception:
        pass  # 双写失败不阻断既有拒绝流

    db.commit()

    return RecommendRejectOut(
        ok=True,
        memory_entry_id=memory_entry_id,
        rejected_count=len(current_rejected),
    )


@router.post('/sessions/{session_id}/jobs/{job_id}/state', response_model=JobStateOut)
def post_job_state(
    session_id: int,
    job_id: str,
    payload: JobStateIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
) -> JobStateOut:
    """推荐 2.0:设置/清除某岗位的显式状态(收藏想投/已投递/不合适)。

    state="" → 清除回 seen。state ∈ {saved,applied,dismissed} → upsert。
    纯追踪,不回流推荐算法(设计稿 2026-06-16 §七.4)。
    """
    from app.services.resume_copilot import job_state as js

    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)

    user_key = str(getattr(session_obj, 'user_key', '') or '')
    state = (payload.state or '').strip()
    if state == '':
        js.clear_explicit_state(db, user_key, job_id)
        return JobStateOut(ok=True, job_id=str(job_id), state=js.STATE_SEEN)
    if state not in js.EXPLICIT_STATES:
        raise HTTPException(status_code=422, detail=f'INVALID_STATE: {state}')
    row = js.set_explicit_state(db, user_key, job_id, state, source_session_id=session_id)
    return JobStateOut(ok=True, job_id=str(job_id), state=row.state)


@router.get('/my-jobs', response_model=MyJobsOut)
def get_my_jobs(
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
) -> MyJobsOut:
    """推荐 2.0:按 user_key 聚合该用户标记过的岗位(收藏想投/已投递/不合适)。"""
    from app.services.resume_copilot import job_state as js
    user_key = (x_resume_user_key or '').strip()
    if not user_key:
        return MyJobsOut(counts=MyJobsCounts())
    grouped = js.my_jobs_grouped(db, user_key)
    return MyJobsOut(**grouped)


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


@router.get('/sessions/{session_id}/tier-fit')
def get_resume_copilot_tier_fit(
    session_id: int,
    sub_cat: str | None = None,
    refresh: int = 0,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
) -> dict:
    """返回学生对指定赛道的档次定位（稳/匹配/冲刺三档 + 理由）。

    sub_cat 不传时自动从 session profile/preferences 推断第一个偏好赛道。
    refresh=1 强制跳过磁盘缓存重跑 LLM。
    """
    import threading
    from app.services.phase_g.tier_fit.tier_fit import build_tier_fit, _read_cache
    from app.services.phase_g.tier_fit.tier_ladder import build_tier_ladder
    from app.services.resume_copilot.recommendation import _v2_extract_preferred_sub_cats

    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)

    profile, prefs = _load_profile_and_prefs(db, session_id)

    if not sub_cat:
        subs = _v2_extract_preferred_sub_cats(profile, prefs)
        sub_cat = subs[0] if subs else None

    if not sub_cat:
        return {"session_id": session_id, "sub_cat": None, "ladder": [], "fit": None}

    # 缓存命中(或 refresh)→ 正常返回。
    if refresh != 0:
        return build_tier_fit(
            db, session_id, sub_cat, profile=profile, prefs=prefs,
            llm_fn=deepseek_json_fn, use_cache=False,
        )
    cached = _read_cache(session_id, sub_cat)
    if cached is not None:
        return cached

    # 缓存未命中：tier-fit 判定要跑 Pro reasoning(~112s)，**绝不同步阻塞前端**。
    # 立即返回 pending(带 ladder 让前端先画梯队，fit=null 暂不高亮)，后台线程算好写缓存，
    # 前端下次拉(或换赛道)即命中。
    def _bg_compute():
        from app.database import SessionLocal as _SL
        _db = _SL()
        try:
            build_tier_fit(_db, session_id, sub_cat, profile=profile, prefs=prefs,
                           llm_fn=deepseek_json_fn, use_cache=True)
        except Exception:
            pass
        finally:
            _db.close()
    threading.Thread(target=_bg_compute, daemon=True).start()
    ladder = build_tier_ladder(db, sub_cat)
    return {"session_id": session_id, "sub_cat": sub_cat,
            "ladder": ladder, "fit": None, "status": "computing"}


@router.get('/sessions/{session_id}/platforms-by-tier')
def get_platforms_by_tier(
    session_id: int,
    sub_cat: str | None = None,
    mode: str | None = None,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
) -> dict:
    """返回指定赛道的梯队骨架：GT 重点公司按头部/次头部/腰部分档，
    叠加"是否有在招对口岗 + 在招岗数 + 同辈情报条数"。

    GT 公司即使暂无在招对口岗也会展示，确保骨架完整。
    sub_cat 不传时自动从 session 推断第一个偏好赛道。
    """
    from app.services.phase_g.tier_fit.platform_skeleton import build_platform_skeleton
    from app.services.phase_g.tier_fit.tier_fit import build_tier_fit
    from app.services.resume_copilot.recommendation import _v2_extract_preferred_sub_cats

    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)

    profile, prefs = _load_profile_and_prefs(db, session_id)

    if not sub_cat:
        subs = _v2_extract_preferred_sub_cats(profile, prefs)
        sub_cat = subs[0] if subs else None

    if not sub_cat:
        return {"session_id": session_id, "sub_cat": None, "has_skeleton": False, "tiers": []}

    # match_band 只用来高亮哪一档。**只读 tier-fit 磁盘缓存**，绝不现场触发 LLM —
    # build_tier_fit 缓存未命中会跑 Pro reasoning(~112s)，会卡死骨架渲染(实测 9min)。
    # 缓存没命中就先不高亮，骨架毫秒级照出；高亮由前端用它已有的 tier-fit 结果补。
    from app.services.phase_g.tier_fit.tier_fit import _read_cache
    match_band: str | None = None
    try:
        cached = _read_cache(session_id, sub_cat)
        if cached:
            match_band = (cached.get("fit") or {}).get("match_band")
    except Exception:
        pass  # match_band 可空，不影响骨架展示

    # mode='intern' (学生主推实习/暑期) → 骨架在招岗实习优先,不被校招挤出 LIMIT 5。
    skeleton = build_platform_skeleton(
        db, sub_cat, match_band=match_band, prefer_internship=(mode == 'intern'),
    )
    skeleton["session_id"] = session_id
    return skeleton


@router.get('/sessions/{session_id}/company-track-jobs')
def get_company_track_jobs(
    session_id: int,
    company: str,
    sub_cat: str | None = None,
    mode: str | None = None,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
) -> dict:
    """梯队骨架:某公司在「当前赛道」的全部在招对口岗(解除骨架预览的 5 条上限)。"""
    from app.services.phase_g.tier_fit.platform_skeleton import _fetch_live_jobs
    from app.services.resume_copilot.recommendation import _v2_extract_preferred_sub_cats

    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)

    if not sub_cat:
        profile, prefs = _load_profile_and_prefs(db, session_id)
        subs = _v2_extract_preferred_sub_cats(profile, prefs)
        sub_cat = subs[0] if subs else None
    if not company or not sub_cat:
        return {"session_id": session_id, "company": company, "sub_cat": sub_cat, "n": 0, "jobs": []}

    jobs = _fetch_live_jobs(db, company, sub_cat, prefer_internship=(mode == 'intern'), limit=100)
    return {"session_id": session_id, "company": company, "sub_cat": sub_cat, "n": len(jobs), "jobs": jobs}


@router.get('/sessions/{session_id}/company-intel')
def get_company_intel(
    session_id: int,
    company: str,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
) -> dict:
    """「讲讲这家」:实时按公司名查 XHS 同辈情报(不依赖骨架预先算的计数,跨赛道也准)。

    诚实铁律:只回真实抽取的洞察(content/quote),没有就 n=0 留白,绝不编造门槛/待遇。
    """
    from app.services.xhs import retrieve

    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)

    name = (company or '').strip()
    if not name:
        return {"company": name, "n": 0, "insights": []}
    try:
        rows = retrieve.search(db, company=[name], limit=6)
    except Exception:
        logger.exception('company-intel search failed for %s', name)
        rows = []
    insights = [
        {
            "type": str(r.get("primary_type", "") or ""),
            "content": str(r.get("content", "") or ""),
            "quote": str(r.get("source_quote", "") or ""),
            "speaker": str(r.get("speaker", "") or ""),
            "confidence": str(r.get("confidence", "") or ""),
        }
        for r in (rows or [])
        if str(r.get("content", "") or "").strip()
    ]
    return {"company": name, "n": len(insights), "insights": insights}


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


class SubCatSuggestionsIn(_BaseModel):
    tracks: list[str] = []


@router.post('/sessions/{session_id}/sub-cat-suggestions')
def sub_cat_suggestions(
    session_id: int,
    payload: SubCatSuggestionsIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
) -> dict:
    """确认页两级勾选: 展开 tracks → sub_cats + LLM 预勾标记。只读, 不写 DB。"""
    from app.services.resume_copilot.subcat_suggest import build_sub_cat_options

    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)

    # Build resume summary: confirmed profile first, fall back to parsed.
    summary = ""
    try:
        prof_row = getattr(session, 'confirmed_profile', None) or getattr(session, 'parsed_profile', None)
        if prof_row is None:
            # lazy-load via direct query if relationship not loaded
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
            prof_row = confirmed or parsed
        if prof_row is not None:
            profile_json: Any = getattr(prof_row, 'profile_json', '{}') or '{}'
            prof = json.loads(str(profile_json))
            summary = str(prof.get('candidate_summary', '') or '')
    except Exception:
        log.warning("sub_cat_suggestions: failed to extract profile summary", exc_info=True)

    return {"options": build_sub_cat_options(summary, payload.tracks)}


# ---------------------------------------------------------------------------
# NL 推荐 agent 端点 (2026-06-04) — recommend-chat / working-query / deepen
#   快路(chat/working-query/update): 纯规则 + flash 意图解析, 绝不调 Pro。
#   慢路(deepen): 唯一允许跑 Pro 精排 + 4-anchor 理由的端点。
# ---------------------------------------------------------------------------


class RecommendChatIn(_BaseModel):
    message: str = ''


class RecommendDeepenIn(_BaseModel):
    job_ids: list[str] = []


class WorkingQueryUpdateIn(_BaseModel):
    remove_sub_cat: str | None = None
    clear_only: bool = False
    sort: str | None = None
    reseed: bool = False


@router.post('/sessions/{session_id}/recommend-chat')
def recommend_chat(
    session_id: int,
    payload: RecommendChatIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """NL 推荐 agent 一轮: 自然语言 → 工作查询重排 → 流动 feed (快路, 不调 Pro)。"""
    from app.services.resume_copilot.recommend_chat import run_recommend_turn

    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    _assert_not_demo(session)  # 写 working_query_json → 是写操作
    out = run_recommend_turn(db=db, session=session, message=payload.message)
    db.commit()
    return out


@router.get('/sessions/{session_id}/working-query')
def get_working_query(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """读当前工作查询; 为空则按 confirmed + L3 记忆 seed 并落库 (seed 即写, 守 demo)。"""
    from app.services.resume_copilot.recommend_chat import seed_query_for_session

    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    raw = getattr(session, 'working_query_json', None)
    if raw:
        try:
            return {"working_query": json.loads(raw)}
        except Exception:
            pass
    # 落库 seed → 写操作, demo 只读时只返不落库。
    q = seed_query_for_session(db, session)
    if str(getattr(session, 'user_key', '') or '') != '__demo__':
        session.working_query_json = json.dumps(q.model_dump(), ensure_ascii=False)
        db.commit()
    return {"working_query": q.model_dump()}


# ── 简历编辑器草稿(跨设备持久化)— editor_draft_json 列 ────────────────────────
# 编辑器改的是渲染模型 zh + 模板/布局/隐藏项, confirmed-profile 装不下这套。落库后
# 换设备/换浏览器也能恢复上次编辑。前端仍用 localStorage 当即时缓存, 这里是真源。

class EditorDraftIn(_BaseModel):
    draft: dict[str, Any]


@router.get('/sessions/{session_id}/editor-draft')
def get_editor_draft(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """读简历编辑器草稿(渲染模型 + 模板/布局/隐藏)。无草稿返回 null。"""
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    raw = getattr(session, 'editor_draft_json', None)
    if raw:
        try:
            return {"draft": json.loads(raw)}
        except Exception:
            pass
    return {"draft": None}


@router.put('/sessions/{session_id}/editor-draft')
def put_editor_draft(
    session_id: int,
    payload: EditorDraftIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """落简历编辑器草稿(跨设备恢复)。owner 守卫 + demo 只读守卫。"""
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    _assert_not_demo(session)
    session.editor_draft_json = json.dumps(payload.draft, ensure_ascii=False)
    session.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


# ── 简历版本存档 + 编辑器深度优化对话(统一 Hub 编辑器改版)─────────────────────
# 简历版本: 显式点保存才记一版, 每版 = 简历快照 + 该版打分报告(可空)。切版本载入该版
# 简历, 报告跟着切; 重新打分把报告归档进当前版。整组数组按 blob 存取(同 editor-draft 模式)。
# 编辑器对话: 编辑器内深度优化最多 3 个 tab, 各自独立消息, 也按 blob 存取。

class _VersionsIn(_BaseModel):
    versions: list[dict[str, Any]]


class _EditorConvosIn(_BaseModel):
    conversations: list[dict[str, Any]]


@router.get('/sessions/{session_id}/resume-versions')
def get_resume_versions(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """读简历版本存档数组(每版 = 简历快照 + 该版打分报告)。无存档返回 []。"""
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    raw = getattr(session, 'resume_versions_json', None)
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return {"versions": data}
        except Exception:
            pass
    return {"versions": []}


@router.put('/sessions/{session_id}/resume-versions')
def put_resume_versions(
    session_id: int,
    payload: _VersionsIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """整组落简历版本存档。owner 守卫 + demo 只读守卫。"""
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    _assert_not_demo(session)
    session.resume_versions_json = json.dumps(payload.versions, ensure_ascii=False)
    session.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.get('/sessions/{session_id}/editor-conversations')
def get_editor_conversations(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """读编辑器深度优化对话数组(最多 3 个 tab)。无对话返回 []。"""
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    raw = getattr(session, 'editor_conversations_json', None)
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return {"conversations": data}
        except Exception:
            pass
    return {"conversations": []}


@router.put('/sessions/{session_id}/editor-conversations')
def put_editor_conversations(
    session_id: int,
    payload: _EditorConvosIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """整组落编辑器深度优化对话。owner 守卫 + demo 只读守卫。"""
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    _assert_not_demo(session)
    session.editor_conversations_json = json.dumps(payload.conversations, ensure_ascii=False)
    session.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


# ── 统一 Hub 对话(多对话: 简历是 base, 一份简历下可开多个对话)──────────────────
# 取代旧单槽 hub_conversation_json(一份简历只装得下一段对话 → 「新对话」清空复用,
# 再聊就覆盖掉旧对话)。现在: 新对话=插新行(旧对话原样保留), 每个对话有自己的
# id / 标题(前端取首句) / 时间; 侧栏历史按当前简历列它名下的对话。
# 消息体仍是 turn/result/trace/memory/intel 有序数组(滤掉 skillrun 思考表演)。

class HubConversationCreateIn(_BaseModel):
    title: str = ""
    messages: list[dict[str, Any]]


class HubConversationUpdateIn(_BaseModel):
    messages: list[dict[str, Any]]
    title: str | None = None


def _conv_or_404(db: Session, session_id: int, conv_id: int) -> HubConversation:
    conv = (
        db.query(HubConversation)
        .filter(HubConversation.id == conv_id, HubConversation.session_id == session_id)
        .first()
    )
    if conv is None:
        raise HTTPException(status_code=404, detail='Conversation not found')
    return conv


@router.get('/sessions/{session_id}/hub-conversations')
def list_hub_conversations(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """这份简历名下的对话列表(新→旧)。侧栏「历史对话」与进场取最新对话都用它。"""
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    rows = (
        db.query(HubConversation)
        .filter(HubConversation.session_id == session_id)
        .order_by(HubConversation.updated_at.desc(), HubConversation.id.desc())
        .all()
    )
    out = []
    for r in rows:
        try:
            n = len(json.loads(r.messages_json or '[]'))
        except Exception:
            n = 0
        out.append(
            {
                "id": int(r.id),
                "title": str(r.title or ''),
                "updated_at": r.updated_at,
                "message_count": n,
            }
        )
    return {"conversations": out}


@router.post('/sessions/{session_id}/hub-conversations')
def create_hub_conversation(
    session_id: int,
    payload: HubConversationCreateIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """在这份简历下开一个新对话(旧对话不动)。owner + demo 只读守卫。"""
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    _assert_not_demo(session)
    now = datetime.utcnow()
    conv = HubConversation(
        session_id=session_id,
        title=(payload.title or '').strip()[:48] or '对话',
        messages_json=json.dumps(payload.messages, ensure_ascii=False),
        created_at=now,
        updated_at=now,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return {"id": int(conv.id), "title": str(conv.title or '')}


@router.get('/sessions/{session_id}/hub-conversations/{conv_id}')
def get_hub_conversation_detail(
    session_id: int,
    conv_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """读某个对话的消息流(切回来重放)。"""
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    conv = _conv_or_404(db, session_id, conv_id)
    try:
        messages = json.loads(conv.messages_json or '[]')
    except Exception:
        messages = []
    return {"id": int(conv.id), "title": str(conv.title or ''), "messages": messages}


@router.put('/sessions/{session_id}/hub-conversations/{conv_id}')
def update_hub_conversation(
    session_id: int,
    conv_id: int,
    payload: HubConversationUpdateIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """追加式落库某个对话(每轮对话后即时调, 不再防抖丢存)。owner + demo 守卫。"""
    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    _assert_not_demo(session)
    conv = _conv_or_404(db, session_id, conv_id)
    conv.messages_json = json.dumps(payload.messages, ensure_ascii=False)
    if payload.title is not None and payload.title.strip():
        conv.title = payload.title.strip()[:48]
    conv.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post('/sessions/{session_id}/recommend-deepen')
def recommend_deepen(
    session_id: int,
    payload: RecommendDeepenIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """慢路: 对指定岗位跑 Pro 精排 + 4-anchor 理由 (复用 recommendation_v2 慢路)。"""
    from app.services.resume_copilot.recommend_deepen import deepen_jobs

    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    return {"items": deepen_jobs(db, session, payload.job_ids)}


@router.post('/sessions/{session_id}/working-query/update')
def update_working_query(
    session_id: int,
    payload: WorkingQueryUpdateIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    """结构化操作工作查询(删 add chip / 清 only / 改 sort / 切赛道 reseed) + 重排 (快路, 不调 LLM)。"""
    from app.services.resume_copilot.recommend_chat import seed_query_for_session
    from app.services.resume_copilot.recommend_search import search_candidates
    from app.services.resume_copilot.working_query import WorkingQuery

    session = _get_session_or_404(db, session_id)
    _assert_session_owner(session, x_resume_user_key)
    if payload.reseed:
        # reseed = 按画像种子重查在招岗, 本质纯读; demo 只读会话也放行,
        # 但不落库 (working_query_json 不写) — 守住 demo read-only 铁律。
        q = seed_query_for_session(db, session)
        if str(getattr(session, 'user_key', '') or '') != '__demo__':
            session.working_query_json = json.dumps(q.model_dump(), ensure_ascii=False)
            db.commit()
        return {"working_query": q.model_dump(), "feed": search_candidates(db, q)}
    _assert_not_demo(session)  # 落库 working_query_json → 是写操作
    raw = getattr(session, 'working_query_json', None)
    q = WorkingQuery(**json.loads(raw)) if raw else WorkingQuery()
    if payload.remove_sub_cat:
        # 只删 add 集 (sub_cats), 永不动 seed_sub_cats (confirmed 派生)。
        q = q.model_copy(update={"sub_cats": [s for s in q.sub_cats if s != payload.remove_sub_cat]})
    if payload.clear_only:
        q = q.model_copy(update={"only": False})
    if payload.sort in ("match", "fresh", "pay"):
        q = q.model_copy(update={"sort": payload.sort})
    session.working_query_json = json.dumps(q.model_dump(), ensure_ascii=False)
    db.commit()
    return {"working_query": q.model_dump(), "feed": search_candidates(db, q)}
# ── Translate profile endpoint (B4) ─────────────────────────────────────────

class TranslateProfileIn(BaseModel):
    profile: dict[str, Any]
    target: str = 'en'


@router.post('/translate-profile')
def translate_profile_endpoint(body: TranslateProfileIn) -> dict:
    if body.target != 'en':
        return {'profile': body.profile, 'warnings': []}
    return translator_svc.translate_profile(body.profile)
