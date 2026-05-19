import json
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import (
    ResumeConfirmedProfile,
    ResumeCopilotSession,
    ResumeRecommendationRun,
    ResumeParsedProfile,
    ResumePreferenceProfile,
)
from app.schemas_resume_copilot import ResumeAgentTraceItem, ResumePreferencePayload, ResumeProfilePayload
from app.services.resume_copilot.parser import (
    ResumeParserProvider,
    build_heuristic_resume_profile,
    is_resume_parser_upstream_http_error,
    parse_resume_text_to_profile,
)
from app.services.resume_copilot.quick_enrichment import serialize_agent_trace
from app.services.resume_copilot.state import RunStatus, SessionStatus
from app.services.resume_copilot.agent.budget import AgentBudget
from app.services.resume_copilot.agent.core import ReActAgent
from app.services.resume_copilot.agent.tools import build_tools
from app.services.resume_copilot.recommendation import ResumeRecommendationProvider, recommend_jobs_for_profile

RESUME_RECOMMENDATION_LIMIT = 100
_AGENT_TRACE_CAP = 50

# Mirrors USER_SESSION_TTL from app.routers.resume_copilot — duplicated here
# to avoid a circular import. Keep in sync.
USER_SESSION_TTL = timedelta(days=7)


def _append_agent_trace(
    db,
    session_id: int,
    agent_trace: list[ResumeAgentTraceItem],
    agent: str = 'Agent',
    message: str = '',
    status: str = 'completed',
    tool: str = '',
    step_index: int = 0,
    result_summary: str = '',
) -> None:
    agent_trace.append(ResumeAgentTraceItem(
        agent=agent,
        message=message,
        status=status,
        tool=tool,
        step_index=step_index,
        result_summary=result_summary,
    ))
    if len(agent_trace) > _AGENT_TRACE_CAP:
        del agent_trace[: len(agent_trace) - _AGENT_TRACE_CAP]
    recommendation_run = db.query(ResumeRecommendationRun).filter(
        ResumeRecommendationRun.session_id == session_id
    ).first()
    if recommendation_run:
        recommendation_run.agent_trace_json = serialize_agent_trace(agent_trace)
        recommendation_run.updated_at = datetime.utcnow()  # heartbeat for inflight guard
        db.commit()


def run_resume_parse_workflow(
    session_id: int,
    session_factory=SessionLocal,
    provider: ResumeParserProvider | None = None,
) -> None:
    db = session_factory()
    session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
    if not session:
        db.close()
        raise ValueError(f'Resume copilot session {session_id} not found')

    # 设 ContextVar 让 LLM call 站点能记账。BackgroundTask 不继承 request 的 contextvar,
    # 所以在 task 入口显式 set,session.user_key 是注册时 plumb 进来的 stable key。
    from app.services.llm_quota import set_current_user_key, reset_current_user_key
    _quota_token = set_current_user_key(str(getattr(session, 'user_key', '') or ''))

    try:
        profile = parse_resume_text_to_profile(str(getattr(session, 'extracted_text', '') or ''), provider=provider)
        parsed_profile = db.query(ResumeParsedProfile).filter(ResumeParsedProfile.session_id == session_id).first()
        if not parsed_profile:
            parsed_profile = ResumeParsedProfile(session_id=session_id)
            db.add(parsed_profile)
        parsed_profile.profile_json = json.dumps(profile.model_dump())
        session.status = SessionStatus.AWAITING_USER_CONFIRMATION.value
        session.error_message = ''
        db.commit()
    except Exception as exc:
        if is_resume_parser_upstream_http_error(exc):
            db.rollback()
            session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
            parsed_profile = db.query(ResumeParsedProfile).filter(ResumeParsedProfile.session_id == session_id).first()
            if not parsed_profile:
                parsed_profile = ResumeParsedProfile(session_id=session_id)
                db.add(parsed_profile)
            fallback_profile = build_heuristic_resume_profile(str(getattr(session, 'extracted_text', '') or ''))
            parsed_profile.profile_json = json.dumps(fallback_profile.model_dump())
            session.status = SessionStatus.AWAITING_USER_CONFIRMATION.value
            session.error_message = ''
            db.commit()
            db.close()
            return
        db.rollback()
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
        parsed_profile = db.query(ResumeParsedProfile).filter(ResumeParsedProfile.session_id == session_id).first()
        if parsed_profile:
            db.delete(parsed_profile)
        session.status = SessionStatus.FAILED.value
        session.error_message = str(exc)
        db.commit()
    finally:
        db.close()
        reset_current_user_key(_quota_token)


def run_resume_generate_workflow(
    session_id: int,
    session_factory=SessionLocal,
    recommendation_provider: ResumeRecommendationProvider | None = None,
    direction_provider=None,
) -> None:
    from app.models import ResumeDirectionAnalysisRun, ResumeCopilotMessage
    from app.services.resume_copilot.direction_analysis import generate_direction_analysis
    from app.services.resume_copilot.chat import initialize_chat

    db = session_factory()
    session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
    if not session:
        db.close()
        raise ValueError(f'Resume copilot session {session_id} not found')

    from app.services.llm_quota import set_current_user_key, reset_current_user_key
    _quota_token = set_current_user_key(str(getattr(session, 'user_key', '') or ''))

    recommendation_run = db.query(ResumeRecommendationRun).filter(
        ResumeRecommendationRun.session_id == session_id
    ).first()
    if not recommendation_run:
        recommendation_run = ResumeRecommendationRun(session_id=session_id)
        db.add(recommendation_run)

    # UNIQUE constraint: query-then-create, never bare db.add
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
    recommendation_run.agent_trace_json = '[]'
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
    agent_trace: list[ResumeAgentTraceItem] = []

    try:
        confirmed_profile = db.query(ResumeConfirmedProfile).filter(
            ResumeConfirmedProfile.session_id == session_id
        ).first()
        if not confirmed_profile:
            raise ValueError('CONFIRMED_PROFILE_REQUIRED')
        preference_profile = db.query(ResumePreferenceProfile).filter(
            ResumePreferenceProfile.session_id == session_id
        ).first()
        profile = ResumeProfilePayload.model_validate(
            json.loads(str(confirmed_profile.profile_json or '{}'))
        )
        preferences = None
        if preference_profile:
            preferences = ResumePreferencePayload.model_validate(
                json.loads(str(preference_profile.preferences_json or '{}'))
            )
            preferences.all_skipped = bool(preference_profile.all_skipped)

        # ── Step 1: Rule scoring ──────────────────────────────────────────
        _append_agent_trace(db, session_id, agent_trace, 'Agent',
                            '规则引擎召回中，正在计算基础匹配分…', 'running')
        candidates, used_ai, fallback_reason = recommend_jobs_for_profile(
            db, profile, preferences,
            limit=RESUME_RECOMMENDATION_LIMIT,
            ai_provider=recommendation_provider,
            ai_top_n=0,
        )
        _append_agent_trace(db, session_id, agent_trace, 'Agent',
                            f'规则初筛完成，召回 {len(candidates)} 个候选岗位。', 'completed')

        # Dual-track: persist preliminary results immediately
        recommendation_run.recommendations_json = json.dumps(
            [item.model_dump() for item in candidates[:15]]
        )
        recommendation_run.updated_at = datetime.utcnow()
        session.recommendation_status = RunStatus.RUNNING.value
        db.commit()

        # ── Step 2: Direction analysis ────────────────────────────────────
        direction_results = generate_direction_analysis(
            profile, preferences, provider=direction_provider
        )
        direction_run = db.query(ResumeDirectionAnalysisRun).filter(
            ResumeDirectionAnalysisRun.session_id == session_id
        ).first()
        if not direction_run:
            raise ValueError(f'direction_run for session {session_id} was deleted mid-flight')
        direction_run.status = RunStatus.COMPLETED.value
        direction_run.directions_json = json.dumps(
            [r.model_dump() for r in direction_results]
        )
        direction_run.updated_at = datetime.utcnow()
        db.commit()

        # ── Step 3: ReAct agent ───────────────────────────────────────────
        def agent_trace_recorder(**kwargs: object) -> None:
            _append_agent_trace(db, session_id, agent_trace, **kwargs)

        react_agent = ReActAgent(
            tools=build_tools(db, profile, preferences, candidates),
            budget=AgentBudget(),
        )
        recommendations = react_agent.run(
            profile=profile,
            preferences=preferences,
            candidates=candidates,
            trace_recorder=agent_trace_recorder,
            direction_results=direction_results,
        )
        recommendation_run = db.query(ResumeRecommendationRun).filter(
            ResumeRecommendationRun.session_id == session_id
        ).first()
        if not recommendation_run:
            raise ValueError(f'recommendation_run for session {session_id} was deleted mid-flight')
        session = db.query(ResumeCopilotSession).filter(
            ResumeCopilotSession.id == session_id
        ).first()
        recommendation_run.status = RunStatus.COMPLETED.value
        recommendation_run.error_message = ''
        recommendation_run.used_ai = 1
        recommendation_run.fallback_reason = fallback_reason
        recommendation_run.agent_trace_json = serialize_agent_trace(agent_trace)
        recommendation_run.recommendations_json = json.dumps(
            [item.model_dump() for item in recommendations]
        )
        recommendation_run.updated_at = datetime.utcnow()
        session.recommendation_status = RunStatus.COMPLETED.value
        session.status = SessionStatus.GENERATING_RECOMMENDATIONS.value
        db.commit()

        # ── Step 4: Initialize chat from direction analysis ───────────────
        initialize_chat(session_id, direction_results, recommendations, db)
        session = db.query(ResumeCopilotSession).filter(
            ResumeCopilotSession.id == session_id
        ).first()
        session.feedback_status = RunStatus.COMPLETED.value
        session.status = SessionStatus.COMPLETED.value
        session.expires_at = datetime.utcnow() + USER_SESSION_TTL
        session.error_message = ''
        db.commit()

    except Exception as exc:
        db.rollback()
        recommendation_run = db.query(ResumeRecommendationRun).filter(
            ResumeRecommendationRun.session_id == session_id
        ).first()
        direction_run = db.query(ResumeDirectionAnalysisRun).filter(
            ResumeDirectionAnalysisRun.session_id == session_id
        ).first()
        session = db.query(ResumeCopilotSession).filter(
            ResumeCopilotSession.id == session_id
        ).first()
        if recommendation_run:
            recommendation_run.status = RunStatus.FAILED.value
            recommendation_run.error_message = str(exc)
            recommendation_run.used_ai = 0
            recommendation_run.fallback_reason = ''
            recommendation_run.agent_trace_json = serialize_agent_trace(
                agent_trace + [ResumeAgentTraceItem(agent='Agent', message=str(exc), status='failed')]
            )
            recommendation_run.recommendations_json = '[]'
            recommendation_run.updated_at = datetime.utcnow()
        if direction_run:
            direction_run.status = RunStatus.FAILED.value
            direction_run.error_message = str(exc)
            direction_run.updated_at = datetime.utcnow()
        if session:
            session.status = SessionStatus.FAILED.value
            session.error_message = str(exc)
            session.recommendation_status = RunStatus.FAILED.value
            session.feedback_status = RunStatus.FAILED.value
        db.commit()
    finally:
        db.close()
        reset_current_user_key(_quota_token)
