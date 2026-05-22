import json
import re
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
from app.services.resume_copilot.state import RunStatus, SessionStatus
from app.services.resume_copilot.agent.budget import AgentBudget
from app.services.resume_copilot.agent.core import ReActAgent
from app.services.resume_copilot.agent.tools import build_tools
from app.services.resume_copilot.recommendation import ResumeRecommendationProvider, recommend_jobs_for_profile

RESUME_RECOMMENDATION_LIMIT = 100


# B2 (2026-05-21): "蚂蚁集团" 和 "蚂蚁科技集团股份有限公司" 是同一家公司
# 两个法人名, 实测 P7 推荐 20 条全是这两家, 学生立刻判定坏掉。 这里做轻量
# 公司归一: 去掉法人后缀 + 常见 "集团 / 股份有限公司 / 控股 / SH / HK / Inc"
# 等去重 — 一律用清洗后的 token 作为 per-employer cap 的 key, 让真实多样性
# 出来。
_COMPANY_SUFFIX_STRIP = re.compile(
    r'('
    r'股份有限公司|有限责任公司|有限公司|控股集团|集团股份有限公司|'
    r'科技集团股份有限公司|科技集团有限公司|科技集团|集团|控股|'
    r'\(集团\)|（集团）|\(中国\)|（中国）|\(SH\)|\(HK\)|\(US\)|'
    r'Co\.,\s*Ltd\.?|Co\.\s*Ltd\.?|Limited|Ltd\.?|Inc\.?|Corp\.?|Group|Holdings?'
    r')$'
)


# R2-2 (2026-05-21) — 已知一对一 alias (公司常用名 → 归一 key)。 后缀剥
# 不掉的情况, 这里手工列。 例: "中金公司" 和 "中国国际金融股份有限公司"
# 是同一家。
_COMPANY_ALIAS: dict[str, str] = {
    '中金公司': 'cicc',
    '中国国际金融': 'cicc',
    '中国国际金融股份有限公司': 'cicc',
    'cicc': 'cicc',
    '工商银行': 'icbc',
    '中国工商银行': 'icbc',
    '建设银行': 'ccb',
    '中国建设银行': 'ccb',
    '中国银行': 'boc',
    '农业银行': 'abc',
    '中国农业银行': 'abc',
}


def _canonical_employer_key(company: str) -> str:
    """归一公司名 → 一个去重 key。 "蚂蚁集团" 和 "蚂蚁科技集团股份有限公司"
    应该归到同一个 key ("蚂蚁")。

    粗规则: trim 空白 → 反复剥常见法人后缀 → 查 alias → 小写化。 不做语义
    同义合并 (e.g. "Tencent" vs "腾讯" 仍算两家) — 那也走 alias 表。
    """
    s = (company or '').strip()
    if not s:
        return ''
    for _ in range(3):  # 最多剥 3 层后缀
        new = _COMPANY_SUFFIX_STRIP.sub('', s).strip()
        if new == s:
            break
        s = new
    s_low = s.lower()
    return _COMPANY_ALIAS.get(s_low, _COMPANY_ALIAS.get(s, s_low))


def _balance_two_streams(
    finalized,
    candidates,
    *,
    per_stream: int = 10,
    per_employer_cap: int = 3,
):
    """Ensure the React agent's output has up to ``per_stream`` items in each
    stream (校招 + 实习). The agent typically returns ~10 mixed; pad each
    side from ``candidates`` (rule-scored, sorted) so the workspace's two
    tabs both have content.

    Items already in ``finalized`` keep their LLM-enriched fields (strengths,
    risks, etc.); padding items come straight from rule scoring.

    B2 (2026-05-21): per_employer_cap (default 3) limits how many rows from
    the same canonical company (e.g. "蚂蚁" — both 蚂蚁集团 and
    蚂蚁科技集团股份有限公司 normalize to this) can appear in each stream.
    Prevents the P7-style "20 条全是蚂蚁" failure mode.
    """
    finalized_ids = {str(it.job_id) for it in finalized}
    fin_campus = [it for it in finalized if not it.is_internship]
    fin_intern = [it for it in finalized if it.is_internship]

    def _topup(target_list, want_intern):
        # 先按 employer key 给 finalized 部分做一次 cap (LLM 输出本身也可能
        # 集中, 不能只在 padding 时去重)
        employer_counts: dict[str, int] = {}
        capped: list = []
        for it in target_list:
            key = _canonical_employer_key(str(getattr(it, 'company', '') or ''))
            if key and employer_counts.get(key, 0) >= per_employer_cap:
                continue
            employer_counts[key] = employer_counts.get(key, 0) + 1
            capped.append(it)
        target_list = capped
        if len(target_list) >= per_stream:
            return target_list[:per_stream]
        for cand in candidates:
            if str(cand.job_id) in finalized_ids:
                continue
            if cand.is_internship is bool(want_intern):
                key = _canonical_employer_key(str(getattr(cand, 'company', '') or ''))
                if key and employer_counts.get(key, 0) >= per_employer_cap:
                    continue
                employer_counts[key] = employer_counts.get(key, 0) + 1
                target_list.append(cand)
                finalized_ids.add(str(cand.job_id))
                if len(target_list) >= per_stream:
                    break
        return target_list[:per_stream]

    campus = _topup(fin_campus, want_intern=False)
    intern = _topup(fin_intern, want_intern=True)
    return campus + intern
_AGENT_TRACE_CAP = 50


def serialize_agent_trace(items: list[ResumeAgentTraceItem]) -> str:
    """JSON-serialize agent trace list. Used to be in quick_enrichment.py;
    moved here in Phase 0 (D-4 snapshot system removal) since that module no
    longer exists."""
    return json.dumps([item.model_dump() for item in items], ensure_ascii=False)

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
        # BE-3 (D-2/D-3): exclude jobs the user has ✗-rejected this session
        rejected_job_ids: list[str] = []
        raw_rejected = getattr(session, 'rejected_job_ids_json', None)
        if raw_rejected:
            try:
                parsed = json.loads(str(raw_rejected) or '[]')
                if isinstance(parsed, list):
                    rejected_job_ids = [str(j) for j in parsed if str(j).strip()]
            except json.JSONDecodeError:
                rejected_job_ids = []
        # 2026-05-20: bump per-stream top_n to 30 so the React agent has
        # enough candidates to choose ~10 from, and so the post-finalize
        # `_balance_two_streams` topup has room to pad each stream to ~10.
        candidates, used_ai, fallback_reason = recommend_jobs_for_profile(
            db, profile, preferences,
            limit=RESUME_RECOMMENDATION_LIMIT,
            ai_provider=recommendation_provider,
            ai_top_n=0,
            rejected_job_ids=rejected_job_ids,
            top_n=30,
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
        # 2026-05-20: ensure each tab (校招 / 实习) has ~10 items. The React
        # agent's finalize typically returns ~10 mixed; pad each stream from
        # the upstream candidate pool so the UI's two tabs don't starve.
        recommendations = _balance_two_streams(recommendations, candidates, per_stream=10)
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
