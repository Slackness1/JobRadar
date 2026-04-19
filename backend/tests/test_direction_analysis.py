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
