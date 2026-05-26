"""Tests for the plan-mode turn orchestrator (DB + injected LLM)."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    ResumeCopilotMessage,
    ResumeCopilotSession,
    ResumeParsedProfile,
)
from app.services.resume_copilot.agent.builder import NoMoreItems
from app.services.resume_copilot.plan import (
    Evidence,
    ItemKind,
    ItemStatus,
    PlanItem,
    PlanState,
    PlanStatus,
)
from app.services.resume_copilot.plan_turn import run_plan_turn


@pytest.fixture
def db_with_session():
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    s = ResumeCopilotSession(
        file_name='x.pdf',
        name='alice',
        user_key='alice',
        status='awaiting_user_confirmation',
        extracted_text='',
    )
    db.add(s)
    db.flush()
    profile_payload = {
        'basic_info': {'name': 'Alice'},
        'internships': [{'company': 'ByteDance', 'role': 'DA Intern'}],
        'projects': [],
        'education': [],
        'awards': [],
        'skills': {'technical': []},
    }
    db.add(ResumeParsedProfile(
        session_id=s.id,
        profile_json=json.dumps(profile_payload),
    ))
    db.flush()

    # build a minimal plan with one pending item + one item awaiting clarify
    item_pending = PlanItem(
        kind=ItemKind.INTERNSHIP, title='intern bullet 1',
        order=0, status=ItemStatus.PENDING,
    )
    plan = PlanState(
        version=2,
        status=PlanStatus.CLARIFYING,
        items=[item_pending],
    )
    s.plan_json = plan.model_dump_json()
    s.plan_status = plan.status.value
    db.commit()

    yield db, s.id, item_pending.id
    db.close()


def _fake_caller(response: dict):
    def _call(_messages):
        return json.dumps(response)
    return _call


def _fake_sequence(responses):
    calls = []

    def _call(messages):
        calls.append(messages)
        response = responses[len(calls) - 1]
        if callable(response):
            response = response(messages)
        return json.dumps(response)

    _call.calls = calls
    return _call


def test_run_plan_turn_persists_user_message(db_with_session):
    db, sid, item_id = db_with_session
    fake = _fake_caller({
        "action": "ask",
        "item_id": item_id,
        "payload": {"question_text": "数据量?"},
    })
    run_plan_turn(db, sid, "字节实习", llm_caller=fake)
    msgs = db.query(ResumeCopilotMessage).filter_by(session_id=sid).order_by(ResumeCopilotMessage.id).all()
    assert len(msgs) == 2
    assert msgs[0].role == 'user'
    assert msgs[0].content == '字节实习'
    assert msgs[1].role == 'assistant'
    assert '数据量' in msgs[1].content


def test_run_plan_turn_records_user_answer_as_evidence(db_with_session):
    db, sid, item_id = db_with_session
    fake = _fake_caller({
        "action": "ask",
        "item_id": item_id,
        "payload": {"question_text": "结果是什么?"},
    })
    new_plan, _ = run_plan_turn(db, sid, "我用 Excel 做了模型核查，输出估值表", llm_caller=fake)
    item = new_plan.items[0]
    user_evidence = [ev for ev in item.evidence if ev.source == 'user_clarification']
    assert len(user_evidence) == 1
    assert user_evidence[0].citation_msg_id is not None
    assert {tag.type for tag in user_evidence[0].tags} >= {'verb_subject', 'tool'}


def test_run_plan_turn_auto_writes_after_ready_to_write(db_with_session):
    db, sid, item_id = db_with_session

    # #2 (2026-05-21): min-turn floor 要求 item 至少 2 条 user_clarification
    # evidence 才允许 inline ready_to_write→write 自动写草稿。 给这个 item 预先
    # 挂一条 evidence (模拟"已经聊过一轮"), 让这一回合的答复触发 inline write。
    from app.services.resume_copilot.plan import (
        Evidence as _Evidence, PlanState as _PlanState
    )
    s = db.query(ResumeCopilotSession).filter_by(id=sid).first()
    _plan_state = _PlanState.model_validate_json(s.plan_json)
    _plan_state.items[0].evidence.append(_Evidence(
        source='user_clarification',
        text='上次我说过用了 Excel 跑了一遍数据',
        tags=[],
    ))
    s.plan_json = _plan_state.model_dump_json()
    db.commit()

    def write_from_current_item(messages):
        prompt = json.loads(messages[-1]["content"])
        evidence_ids = [ev["id"] for ev in prompt["current_item"]["evidence"]]
        return {
            "action": "write",
            "item_id": item_id,
            "payload": {
                "draft_text": "使用 Excel 完成模型核查并输出估值表",
                "used_evidence_ids": evidence_ids,
            },
        }

    fake = _fake_sequence([
        {"action": "ready_to_write", "item_id": item_id, "payload": {}},
        write_from_current_item,
    ])
    new_plan, action = run_plan_turn(
        db, sid, "我用 Excel 做了模型核查，输出估值表", llm_caller=fake,
    )
    assert action.action == "write"
    assert new_plan.items[0].status == ItemStatus.AWAITING_REVIEW
    assert new_plan.items[0].draft is not None
    assert new_plan.items[0].draft.text == "使用 Excel 完成模型核查并输出估值表"

    msgs = db.query(ResumeCopilotMessage).filter_by(session_id=sid).order_by(ResumeCopilotMessage.id).all()
    assert len(msgs) == 2
    assert msgs[-1].role == 'assistant'
    # R2 polish (2026-05-21): message rewriten to "我按现在的 evidence 写了一版给你看"
    # so student sees the 2-step finalize ritual more clearly. Still asserts the
    # draft text shows up + finalize prompt is present.
    assert '写了一版' in msgs[-1].content
    assert '使用 Excel 完成模型核查并输出估值表' in msgs[-1].content
    assert '入档' in msgs[-1].content
    assert '再聊几轮' in msgs[-1].content


def test_run_plan_turn_applies_action_and_bumps_version(db_with_session):
    db, sid, item_id = db_with_session
    fake = _fake_caller({
        "action": "ask",
        "item_id": item_id,
        "payload": {"question_text": "q"},
    })
    new_plan, action = run_plan_turn(db, sid, "msg", llm_caller=fake)
    assert action.action == "ask"
    assert new_plan.version == 3  # was 2, +1 for the ask
    assert new_plan.items[0].status == ItemStatus.CLARIFYING


def test_run_plan_turn_converts_failing_write_into_followup_ask(db_with_session):
    db, sid, item_id = db_with_session
    # advance the item to ready_to_write first
    s = db.query(ResumeCopilotSession).filter_by(id=sid).first()
    plan = PlanState.model_validate_json(s.plan_json)
    plan.items[0].status = ItemStatus.READY_TO_WRITE
    s.plan_json = plan.model_dump_json()
    db.commit()

    # LLM returns a write with a hallucinated number
    fake = _fake_caller({
        "action": "write",
        "item_id": item_id,
        "payload": {"draft_text": "处理 999 万行数据", "used_evidence_ids": []},
    })
    new_plan, action = run_plan_turn(db, sid, "go", llm_caller=fake)
    # the orchestrator must NOT propagate the audit error; instead it converts
    # to an ask so the user is asked for the missing source
    assert action.action == "ask"
    # M1 (2026-05-21): tag 名 ("overclaim" / "tech_unverified") 必须被翻成
    # 自然中文 — 之前直接拼 tag 字符串到学生眼前 (Worker B 实测)。
    qt = action.payload.get("question_text", "")
    assert "overclaim" not in qt, f'raw tag leak: {qt}'
    assert "tech_unverified" not in qt, f'raw tag leak: {qt}'
    assert "动词太强" in qt or "具体负责" in qt or "确认一下" in qt, f'unexpected qt: {qt}'
    assert new_plan.items[0].status == ItemStatus.CLARIFYING


def test_run_plan_turn_raises_no_more_items_when_terminal(db_with_session):
    db, sid, _ = db_with_session
    s = db.query(ResumeCopilotSession).filter_by(id=sid).first()
    plan = PlanState.model_validate_json(s.plan_json)
    plan.items[0].status = ItemStatus.FINALIZED
    s.plan_json = plan.model_dump_json()
    db.commit()

    fake = _fake_caller({"action": "ask", "payload": {"question_text": "x"}})
    with pytest.raises(NoMoreItems):
        run_plan_turn(db, sid, "anything", llm_caller=fake)


def test_run_plan_turn_raises_when_no_plan(db_with_session):
    db, sid, _ = db_with_session
    s = db.query(ResumeCopilotSession).filter_by(id=sid).first()
    s.plan_json = None
    db.commit()

    fake = _fake_caller({"action": "ask"})
    with pytest.raises(ValueError):
        run_plan_turn(db, sid, "x", llm_caller=fake)


def test_run_plan_turn_uses_target_item_id(db_with_session):
    db, sid, item_id = db_with_session
    # add a second item; ask LLM to act on the second one explicitly
    s = db.query(ResumeCopilotSession).filter_by(id=sid).first()
    plan = PlanState.model_validate_json(s.plan_json)
    second = PlanItem(
        kind=ItemKind.PROJECT, title='proj bullet', order=1, status=ItemStatus.PENDING,
    )
    plan.items.append(second)
    s.plan_json = plan.model_dump_json()
    db.commit()

    fake = _fake_caller({
        "action": "ask",
        "item_id": second.id,
        "payload": {"question_text": "项目细节"},
    })
    new_plan, action = run_plan_turn(
        db, sid, "聊聊项目", target_item_id=second.id, llm_caller=fake,
    )
    assert action.item_id == second.id
    target = next(it for it in new_plan.items if it.id == second.id)
    assert target.status == ItemStatus.CLARIFYING
