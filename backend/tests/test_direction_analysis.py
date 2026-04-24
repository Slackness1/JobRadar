from app.schemas_resume_copilot import (
    DirectionTierResult,
    RewriteOption,
    ResumeCopilotMessageOut,
    ChatMessageIn,
    ApplyRewriteIn,
    ResumeRecommendationItem,
)
from datetime import datetime


def test_direction_tier_result_schema():
    r = DirectionTierResult(
        direction='投研',
        tier=2,
        tier_label='可迁移',
        strengths=['数据分析经历'],
        gaps=['缺少金融实习'],
        transferable_from=['数据分析实习可往投研方向靠'],
    )
    assert r.tier == 2
    assert r.direction == '投研'


def test_rewrite_option_schema():
    o = RewriteOption(
        option_id='A',
        label='方案A — 突出量化成果',
        section='internships',
        field_path='internships.0.bullets.2',
        original='参与数据分析项目',
        improved='独立搭建 DCF 估值模型，覆盖 3 家上市公司',
        rationale='添加具体成果',
    )
    assert o.field_path == 'internships.0.bullets.2'


def test_copilot_message_out_schema():
    msg = ResumeCopilotMessageOut(
        id=1,
        role='assistant',
        content='建议如下',
        rewrite_options=None,
        applied_option_id=None,
        created_at=datetime(2026, 4, 20),
    )
    assert msg.role == 'assistant'


def test_chat_message_in_schema():
    msg = ChatMessageIn(content='我做过估值模型')
    assert msg.content == '我做过估值模型'


def test_apply_rewrite_in_schema():
    req = ApplyRewriteIn(message_id=5, option_id='A')
    assert req.option_id == 'A'


def test_recommendation_item_has_target_direction():
    item = ResumeRecommendationItem(
        job_id='job-1', company='ABC', job_title='后端', location='上海',
        objective_score=50, preference_score=30, base_job_score=40,
        company_priority_score=10, rule_score=130, final_score=130,
        target_direction='互联网后端',
    )
    assert item.target_direction == '互联网后端'


from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base
from app.models import ResumeDirectionAnalysisRun, ResumeCopilotMessage
from app.services.schema_patch import ensure_compatible_schema


def _make_engine():
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    ensure_compatible_schema(engine)
    return engine


def test_direction_analysis_run_table_exists():
    engine = _make_engine()
    inspector = inspect(engine)
    assert 'resume_direction_analysis_runs' in inspector.get_table_names()
    columns = {c['name'] for c in inspector.get_columns('resume_direction_analysis_runs')}
    assert {'id', 'session_id', 'status', 'directions_json', 'error_message', 'created_at'}.issubset(columns)


def test_copilot_message_table_exists():
    engine = _make_engine()
    inspector = inspect(engine)
    assert 'resume_copilot_messages' in inspector.get_table_names()
    columns = {c['name'] for c in inspector.get_columns('resume_copilot_messages')}
    assert {'id', 'session_id', 'role', 'content', 'rewrite_options_json', 'applied_option_id', 'created_at'}.issubset(columns)


from app.schemas_resume_copilot import (
    ResumeProfilePayload,
    ResumePreferencePayload,
    ResumeSkillsPayload,
)
from app.services.resume_copilot.direction_analysis import generate_direction_analysis


def _build_profile():
    return ResumeProfilePayload(
        basic_info={'name': 'Jane'},
        education=[],
        internships=[],
        projects=[],
        skills=ResumeSkillsPayload(technical=['Python'], tools=[], languages=[]),
        languages=[],
        awards=[],
        candidate_summary='Data-focused student',
        inferred_roles=['Data Analyst'],
        inferred_tracks=['Internet'],
    )


def _build_preferences(roles=None, tracks=None):
    return ResumePreferencePayload(
        preferred_roles=roles or ['Backend Engineer'],
        preferred_tracks=tracks or ['Internet'],
        preferred_locations=['Shanghai'],
        preferred_company_types=[],
        accept_relocation=False,
        accept_internship=False,
        campus_only=False,
        social_ok=False,
        preference_notes='',
        all_skipped=False,
    )


class _StubDirectionProvider:
    def analyze_directions(self, profile, preferences, directions):
        return [
            {
                'direction': d,
                'tier': 1 if d == 'Backend Engineer' else 2,
                'tier_label': '强匹配' if d == 'Backend Engineer' else '可迁移',
                'strengths': ['Python skills'],
                'gaps': [] if d == 'Backend Engineer' else ['missing finance experience'],
                'transferable_from': [] if d == 'Backend Engineer' else ['data analysis transferable'],
            }
            for d in directions
        ]


class _FailingDirectionProvider:
    def analyze_directions(self, profile, preferences, directions):
        raise RuntimeError('LLM unavailable')


def test_generate_direction_analysis_returns_tier_results():
    results = generate_direction_analysis(
        _build_profile(),
        _build_preferences(roles=['Backend Engineer', '投研']),
        provider=_StubDirectionProvider(),
    )
    assert len(results) >= 2
    assert all(isinstance(r, DirectionTierResult) for r in results)
    be = next(r for r in results if r.direction == 'Backend Engineer')
    assert be.tier == 1
    assert be.tier_label == '强匹配'


def test_generate_direction_analysis_falls_back_on_llm_failure():
    results = generate_direction_analysis(
        _build_profile(),
        _build_preferences(roles=['Backend Engineer']),
        provider=_FailingDirectionProvider(),
    )
    # Should return fallback tier=1 for each direction, not raise
    assert len(results) >= 1
    assert all(r.tier == 1 for r in results)


def test_generate_direction_analysis_uses_inferred_when_preferences_all_skipped():
    prefs = _build_preferences()
    prefs.all_skipped = True
    results = generate_direction_analysis(
        _build_profile(),
        prefs,
        provider=_StubDirectionProvider(),
    )
    # Falls back to inferred_roles + inferred_tracks from profile
    assert len(results) >= 1


from app.services.resume_copilot.agent.prompt import build_system_prompt
from app.services.resume_copilot.agent.budget import AgentBudget


def test_build_system_prompt_includes_direction_tiers_when_provided():
    profile = _build_profile()
    preferences = _build_preferences()
    direction_results = [
        DirectionTierResult(direction='Backend Engineer', tier=1, tier_label='强匹配',
                            strengths=['Python'], gaps=[], transferable_from=[]),
        DirectionTierResult(direction='投研', tier=2, tier_label='可迁移',
                            strengths=[], gaps=['缺少金融经历'], transferable_from=['数据分析可迁移']),
    ]
    prompt = build_system_prompt(profile, preferences, [], AgentBudget(), direction_results=direction_results)
    assert 'Backend Engineer' in prompt
    assert '强匹配' in prompt
    assert '投研' in prompt
    assert '可迁移' in prompt


def test_build_system_prompt_no_direction_section_when_none():
    profile = _build_profile()
    preferences = _build_preferences()
    prompt = build_system_prompt(profile, preferences, [], AgentBudget(), direction_results=None)
    assert 'Direction Tiers' not in prompt
    assert '方向层级分析' not in prompt
