import json

from app import config
from app.database import SessionLocal
from app.models import (
    ResumeConfirmedProfile,
    ResumeCopilotSession,
    ResumeFeedbackRun,
    ResumeParsedProfile,
    ResumePreferenceProfile,
    ResumeRecommendationRun,
)
from app.schemas_resume_copilot import ResumeAgentTraceItem, ResumePreferencePayload, ResumeProfilePayload
from app.services.resume_copilot.feedback import ResumeFeedbackProvider, generate_feedback_for_profile
from app.services.resume_copilot.parser import (
    ResumeParserProvider,
    build_heuristic_resume_profile,
    is_resume_parser_upstream_http_error,
    parse_resume_text_to_profile,
)
from app.services.resume_copilot.quick_enrichment import serialize_agent_trace
from app.services.resume_copilot.agent.budget import AgentBudget
from app.services.resume_copilot.agent.core import ReActAgent
from app.services.resume_copilot.agent.tools import build_tools
from app.services.resume_copilot.recommendation import ResumeRecommendationProvider, recommend_jobs_for_profile

RESUME_RECOMMENDATION_LIMIT = 100


_AGENT_TRACE_CAP = 50


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

    try:
        profile = parse_resume_text_to_profile(str(getattr(session, 'extracted_text', '') or ''), provider=provider)
        parsed_profile = db.query(ResumeParsedProfile).filter(ResumeParsedProfile.session_id == session_id).first()
        if not parsed_profile:
            parsed_profile = ResumeParsedProfile(session_id=session_id)
            db.add(parsed_profile)
        parsed_profile.profile_json = json.dumps(profile.model_dump())
        session.status = 'awaiting_user_confirmation'
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
            session.status = 'awaiting_user_confirmation'
            session.error_message = ''
            db.commit()
            db.close()
            return
        db.rollback()
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
        parsed_profile = db.query(ResumeParsedProfile).filter(ResumeParsedProfile.session_id == session_id).first()
        if parsed_profile:
            db.delete(parsed_profile)
        session.status = 'failed'
        session.error_message = str(exc)
        db.commit()
    finally:
        db.close()


def run_resume_generate_workflow(
    session_id: int,
    session_factory=SessionLocal,
    recommendation_provider: ResumeRecommendationProvider | None = None,
    feedback_provider: ResumeFeedbackProvider | None = None,
) -> None:
    db = session_factory()
    session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
    if not session:
        db.close()
        raise ValueError(f'Resume copilot session {session_id} not found')

    recommendation_run = db.query(ResumeRecommendationRun).filter(ResumeRecommendationRun.session_id == session_id).first()
    if not recommendation_run:
        recommendation_run = ResumeRecommendationRun(session_id=session_id)
        db.add(recommendation_run)

    feedback_run = db.query(ResumeFeedbackRun).filter(ResumeFeedbackRun.session_id == session_id).first()
    if not feedback_run:
        feedback_run = ResumeFeedbackRun(session_id=session_id)
        db.add(feedback_run)
    recommendation_run.status = 'running'
    recommendation_run.error_message = ''
    recommendation_run.used_ai = 0
    recommendation_run.fallback_reason = ''
    recommendation_run.agent_trace_json = '[]'
    recommendation_run.recommendations_json = '[]'
    feedback_run.status = 'running'
    feedback_run.error_message = ''
    feedback_run.diagnostics_json = '[]'
    feedback_run.rewrite_examples_json = '[]'
    session.status = 'generating_recommendations'
    session.recommendation_status = 'running'
    session.feedback_status = 'running'
    session.error_message = ''
    db.commit()
    agent_trace: list[ResumeAgentTraceItem] = []

    try:
        confirmed_profile = db.query(ResumeConfirmedProfile).filter(ResumeConfirmedProfile.session_id == session_id).first()
        if not confirmed_profile:
            raise ValueError('CONFIRMED_PROFILE_REQUIRED')
        preference_profile = db.query(ResumePreferenceProfile).filter(ResumePreferenceProfile.session_id == session_id).first()
        profile = ResumeProfilePayload.model_validate(json.loads(str(confirmed_profile.profile_json or '{}')))
        preferences = None
        if preference_profile:
            preferences = ResumePreferencePayload.model_validate(json.loads(str(preference_profile.preferences_json or '{}')))
            preferences.all_skipped = bool(preference_profile.all_skipped)

        _append_agent_trace(db, session_id, agent_trace, 'Agent', '规则引擎召回中，正在计算基础匹配分…', 'running')
        candidates, used_ai, fallback_reason = recommend_jobs_for_profile(
            db,
            profile,
            preferences,
            limit=RESUME_RECOMMENDATION_LIMIT,
            ai_provider=recommendation_provider,
            ai_top_n=0,
        )
        _append_agent_trace(db, session_id, agent_trace, 'Agent', f'规则初筛完成，召回 {len(candidates)} 个候选岗位。', 'completed')

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
        )
        recommendation_run = db.query(ResumeRecommendationRun).filter(ResumeRecommendationRun.session_id == session_id).first()
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
        recommendation_run.status = 'completed'
        recommendation_run.error_message = ''
        recommendation_run.used_ai = 1 if any(getattr(item, 'used_ai', False) for item in recommendations) else 0
        recommendation_run.fallback_reason = ''
        recommendation_run.agent_trace_json = serialize_agent_trace(agent_trace)
        recommendation_run.recommendations_json = json.dumps([item.model_dump() for item in recommendations])
        session.recommendation_status = 'completed'
        session.status = 'generating_recommendations'
        db.commit()
    except Exception as exc:
        db.rollback()
        recommendation_run = db.query(ResumeRecommendationRun).filter(ResumeRecommendationRun.session_id == session_id).first()
        feedback_run = db.query(ResumeFeedbackRun).filter(ResumeFeedbackRun.session_id == session_id).first()
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
        recommendation_run.status = 'failed'
        recommendation_run.error_message = str(exc)
        recommendation_run.used_ai = 0
        recommendation_run.fallback_reason = ''
        recommendation_run.agent_trace_json = serialize_agent_trace(agent_trace + [ResumeAgentTraceItem(agent='Agent 1', message=str(exc), status='failed')])
        recommendation_run.recommendations_json = '[]'
        feedback_run.status = 'failed'
        feedback_run.error_message = 'RECOMMENDATION_FAILED'
        feedback_run.diagnostics_json = '[]'
        feedback_run.rewrite_examples_json = '[]'
        session.status = 'failed'
        session.error_message = str(exc)
        session.recommendation_status = 'failed'
        session.feedback_status = 'failed'
        db.commit()
        db.close()
        return

    try:
        diagnostics, rewrite_examples = generate_feedback_for_profile(
            profile,
            preferences,
            recommendations[:5],
            provider=feedback_provider,
        )
        feedback_run = db.query(ResumeFeedbackRun).filter(ResumeFeedbackRun.session_id == session_id).first()
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
        feedback_run.status = 'completed'
        feedback_run.error_message = ''
        feedback_run.diagnostics_json = json.dumps([item.model_dump() for item in diagnostics])
        feedback_run.rewrite_examples_json = json.dumps([item.model_dump() for item in rewrite_examples])
        session.feedback_status = 'completed'
        session.status = 'completed'
        session.error_message = ''
        db.commit()
    except Exception as exc:
        db.rollback()
        feedback_run = db.query(ResumeFeedbackRun).filter(ResumeFeedbackRun.session_id == session_id).first()
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
        feedback_run.status = 'failed'
        feedback_run.error_message = str(exc)
        feedback_run.diagnostics_json = '[]'
        feedback_run.rewrite_examples_json = '[]'
        session.feedback_status = 'failed'
        session.status = 'completed'
        session.error_message = ''
        db.commit()
    finally:
        db.close()
