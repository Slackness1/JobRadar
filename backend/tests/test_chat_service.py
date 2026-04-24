import json
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    ResumeConfirmedProfile,
    ResumeCopilotMessage,
    ResumeCopilotSession,
)
from app.schemas_resume_copilot import (
    DirectionTierResult,
    ResumeProfilePayload,
    ResumeRecommendationItem,
    ResumeSkillsPayload,
)
from app.services.resume_copilot.chat import apply_rewrite, generate_chat_turn, initialize_chat


def _make_factory():
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _seed(db: Session, profile_dict: dict | None = None) -> int:
    session = ResumeCopilotSession(
        file_name='cv.pdf',
        status='completed',
        recommendation_status='completed',
        feedback_status='running',
        extracted_text='Jane',
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    if profile_dict is None:
        profile_dict = {
            'basic_info': {'name': 'Jane'},
            'education': [],
            'internships': [
                {
                    'company': 'Acme',
                    'role': 'Data Analyst',
                    'start_date': '2025-06',
                    'end_date': '2025-09',
                    'bullets': ['分析数据', '完成报告'],
                }
            ],
            'projects': [],
            'skills': {'technical': ['Python'], 'tools': [], 'languages': []},
            'languages': [],
            'awards': [],
            'candidate_summary': '',
            'inferred_roles': [],
            'inferred_tracks': [],
        }
    db.add(ResumeConfirmedProfile(
        session_id=session.id,
        profile_json=json.dumps(profile_dict),
    ))
    db.commit()
    return int(session.id)


def _make_direction_results():
    return [
        DirectionTierResult(
            direction='Backend Engineer', tier=1, tier_label='强匹配',
            strengths=['Python'], gaps=[], transferable_from=[],
        )
    ]


def _make_recs():
    return [
        ResumeRecommendationItem(
            job_id='job-1', company='Acme', job_title='后端', location='上海',
            objective_score=50, preference_score=30, base_job_score=40,
            company_priority_score=10, rule_score=130, final_score=130,
        )
    ]


def test_initialize_chat_creates_system_message():
    factory = _make_factory()
    db = factory()
    session_id = _seed(db)
    db.close()

    db = factory()
    initialize_chat(session_id, _make_direction_results(), _make_recs(), db)
    msgs = db.query(ResumeCopilotMessage).filter(
        ResumeCopilotMessage.session_id == session_id
    ).all()
    assert len(msgs) == 1
    assert msgs[0].role == 'system'
    assert len(msgs[0].content) > 10
    db.close()


def test_initialize_chat_idempotent_on_second_call():
    factory = _make_factory()
    db = factory()
    session_id = _seed(db)
    db.close()

    db = factory()
    initialize_chat(session_id, _make_direction_results(), _make_recs(), db)
    # Second call must not duplicate the system message
    initialize_chat(session_id, _make_direction_results(), _make_recs(), db)
    msgs = db.query(ResumeCopilotMessage).filter(
        ResumeCopilotMessage.session_id == session_id,
        ResumeCopilotMessage.role == 'system',
    ).all()
    assert len(msgs) == 1
    db.close()


class _StubChatLLMProvider:
    def generate_turn(self, messages_payload):
        return {
            'content': '这是建议',
            'rewrite_options': [
                {
                    'option_id': 'A',
                    'label': '方案A',
                    'section': 'internships',
                    'field_path': 'internships.0.bullets.0',
                    'original': '分析数据',
                    'improved': '独立完成数据分析，覆盖 100 个样本',
                    'rationale': '更具体',
                }
            ],
        }


def test_generate_chat_turn_stores_user_and_assistant_messages():
    factory = _make_factory()
    db = factory()
    session_id = _seed(db)
    db.close()

    db = factory()
    initialize_chat(session_id, _make_direction_results(), _make_recs(), db)
    db.close()

    db = factory()
    result = generate_chat_turn(
        session_id, '我做过估值模型', db,
        provider=_StubChatLLMProvider(),
    )
    msgs = db.query(ResumeCopilotMessage).filter(
        ResumeCopilotMessage.session_id == session_id
    ).all()
    assert len(msgs) == 3  # system + user + assistant
    assert result.role == 'assistant'
    assert result.content == '这是建议'
    assert result.rewrite_options is not None
    assert result.rewrite_options[0].option_id == 'A'
    db.close()


def test_apply_rewrite_patches_profile_field():
    factory = _make_factory()
    db = factory()
    session_id = _seed(db)
    db.close()

    # Set up an assistant message with a rewrite option
    db = factory()
    option_json = json.dumps([{
        'option_id': 'A',
        'label': '方案A',
        'section': 'internships',
        'field_path': 'internships.0.bullets.0',
        'original': '分析数据',
        'improved': '独立完成数据分析，覆盖 100 个样本',
        'rationale': '更具体',
    }])
    msg = ResumeCopilotMessage(
        session_id=session_id,
        role='assistant',
        content='建议',
        rewrite_options_json=option_json,
        applied_option_id=None,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    message_id = int(msg.id)
    db.close()

    db = factory()
    updated_profile = apply_rewrite(session_id, message_id, 'A', db)
    db.close()

    db = factory()
    confirmed = db.query(ResumeConfirmedProfile).filter(
        ResumeConfirmedProfile.session_id == session_id
    ).first()
    profile_dict = json.loads(confirmed.profile_json)
    assert profile_dict['internships'][0]['bullets'][0] == '独立完成数据分析，覆盖 100 个样本'
    msg_after = db.query(ResumeCopilotMessage).filter(
        ResumeCopilotMessage.id == message_id
    ).first()
    assert msg_after.applied_option_id == 'A'
    db.close()


def test_apply_rewrite_raises_on_invalid_field_path():
    factory = _make_factory()
    db = factory()
    session_id = _seed(db)
    option_json = json.dumps([{
        'option_id': 'A',
        'label': '方案A',
        'section': 'internships',
        'field_path': 'internships.99.bullets.0',  # index 99 doesn't exist
        'original': 'x',
        'improved': 'y',
        'rationale': 'z',
    }])
    msg = ResumeCopilotMessage(
        session_id=session_id,
        role='assistant',
        content='建议',
        rewrite_options_json=option_json,
        applied_option_id=None,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    message_id = int(msg.id)

    import pytest
    with pytest.raises(ValueError):
        apply_rewrite(session_id, message_id, 'A', db)
    db.close()
