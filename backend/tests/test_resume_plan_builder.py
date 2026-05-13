"""Tests for the plan-mode agent builder (LLM caller injected, no network)."""
from __future__ import annotations

import json

import pytest

from app.schemas_resume_copilot import ResumeProfilePayload
from app.services.resume_copilot.agent.builder import (
    NoMoreItems,
    _pick_next_item,
    propose_next_action,
)
from app.services.resume_copilot.plan import (
    Evidence,
    EvidenceTag,
    ItemKind,
    ItemStatus,
    PlanItem,
    PlanState,
    PlanStatus,
)


def _plan_with_items(items: list[PlanItem]) -> PlanState:
    return PlanState(
        version=1,
        status=PlanStatus.CLARIFYING,
        items=items,
    )


def _profile() -> ResumeProfilePayload:
    return ResumeProfilePayload(candidate_summary="本科生，找数据分析")


# ─── _pick_next_item ────────────────────────────────────────────────────────

def test_picker_honors_target_item_id():
    a = PlanItem(kind=ItemKind.INTERNSHIP, title="a", order=0, status=ItemStatus.PENDING)
    b = PlanItem(kind=ItemKind.PROJECT, title="b", order=1, status=ItemStatus.PENDING)
    plan = _plan_with_items([a, b])
    picked = _pick_next_item(plan, target_item_id=b.id)
    assert picked is b


def test_picker_skips_finalized_and_dropped():
    a = PlanItem(kind=ItemKind.INTERNSHIP, title="a", order=0, status=ItemStatus.FINALIZED)
    b = PlanItem(kind=ItemKind.PROJECT, title="b", order=1, status=ItemStatus.DROPPED)
    c = PlanItem(kind=ItemKind.SKILL, title="c", order=2, status=ItemStatus.PENDING)
    plan = _plan_with_items([a, b, c])
    picked = _pick_next_item(plan, target_item_id=None)
    assert picked is c


def test_picker_prefers_clarifying_over_pending():
    p = PlanItem(kind=ItemKind.INTERNSHIP, title="pending", order=0, status=ItemStatus.PENDING)
    c = PlanItem(kind=ItemKind.PROJECT, title="clarifying", order=1, status=ItemStatus.CLARIFYING)
    plan = _plan_with_items([p, c])
    picked = _pick_next_item(plan, target_item_id=None)
    assert picked is c


def test_picker_honors_current_item_id_first():
    a = PlanItem(kind=ItemKind.INTERNSHIP, title="a", order=0, status=ItemStatus.CLARIFYING)
    b = PlanItem(kind=ItemKind.PROJECT, title="b", order=1, status=ItemStatus.CLARIFYING)
    plan = PlanState(version=1, status=PlanStatus.CLARIFYING, items=[a, b], current_item_id=b.id)
    picked = _pick_next_item(plan, target_item_id=None)
    assert picked is b


def test_picker_returns_none_when_all_terminal():
    a = PlanItem(kind=ItemKind.INTERNSHIP, title="a", order=0, status=ItemStatus.FINALIZED)
    b = PlanItem(kind=ItemKind.PROJECT, title="b", order=1, status=ItemStatus.DROPPED)
    plan = _plan_with_items([a, b])
    assert _pick_next_item(plan, target_item_id=None) is None


# ─── propose_next_action ────────────────────────────────────────────────────

def _fake_caller(response: dict | str):
    """Make an llm_caller that returns the given JSON (as dict or raw string)."""
    raw = response if isinstance(response, str) else json.dumps(response)

    def _call(_messages):
        return raw

    return _call


def test_propose_returns_valid_ask_action():
    item = PlanItem(kind=ItemKind.INTERNSHIP, title="x", order=0, status=ItemStatus.PENDING)
    plan = _plan_with_items([item])
    fake = _fake_caller({
        "action": "ask",
        "item_id": item.id,
        "payload": {"question_text": "数据规模是多少?"},
    })
    action = propose_next_action(
        profile=_profile(), preferences=None, plan=plan,
        user_message="字节实习做了 A/B 测试",
        llm_caller=fake,
    )
    assert action.action == "ask"
    assert action.item_id == item.id
    assert action.payload["question_text"] == "数据规模是多少?"


def test_propose_returns_write_action():
    ev = Evidence(source="user_clarification", text="处理 30 万行")
    item = PlanItem(
        kind=ItemKind.INTERNSHIP, title="x", order=0,
        status=ItemStatus.READY_TO_WRITE, evidence=[ev],
    )
    plan = _plan_with_items([item])
    fake = _fake_caller({
        "action": "write",
        "item_id": item.id,
        "payload": {
            "draft_text": "处理 30 万行用户数据",
            "used_evidence_ids": [ev.id],
        },
    })
    action = propose_next_action(
        profile=_profile(), preferences=None, plan=plan,
        user_message="可以写了",
        llm_caller=fake,
    )
    assert action.action == "write"
    assert action.payload["used_evidence_ids"] == [ev.id]


def test_propose_injects_item_id_when_missing():
    """LLM sometimes omits item_id when it's obvious — we fill it from the picker."""
    item = PlanItem(kind=ItemKind.PROJECT, title="x", order=0, status=ItemStatus.PENDING)
    plan = _plan_with_items([item])
    fake = _fake_caller({"action": "ask", "payload": {"question_text": "?"}})
    action = propose_next_action(
        profile=_profile(), preferences=None, plan=plan,
        user_message="x", llm_caller=fake,
    )
    assert action.item_id == item.id


def test_propose_retries_on_malformed_json():
    """First call returns garbage; second call returns valid JSON."""
    item = PlanItem(kind=ItemKind.PROJECT, title="x", order=0, status=ItemStatus.PENDING)
    plan = _plan_with_items([item])

    calls = []

    def _flaky(messages):
        calls.append(messages)
        if len(calls) == 1:
            return "not valid json at all"
        return json.dumps({"action": "ask", "item_id": item.id, "payload": {"question_text": "ok"}})

    action = propose_next_action(
        profile=_profile(), preferences=None, plan=plan,
        user_message="x", llm_caller=_flaky,
    )
    assert action.action == "ask"
    assert len(calls) == 2


def test_propose_falls_back_to_generic_ask_when_retries_exhausted():
    item = PlanItem(kind=ItemKind.PROJECT, title="x", order=0, status=ItemStatus.PENDING)
    plan = _plan_with_items([item])

    def _always_broken(_messages):
        return "not json"

    action = propose_next_action(
        profile=_profile(), preferences=None, plan=plan,
        user_message="x", llm_caller=_always_broken,
    )
    assert action.action == "ask"
    assert action.item_id == item.id


def test_propose_falls_back_when_caller_throws():
    item = PlanItem(kind=ItemKind.PROJECT, title="x", order=0, status=ItemStatus.PENDING)
    plan = _plan_with_items([item])

    def _explode(_messages):
        raise RuntimeError("network down")

    action = propose_next_action(
        profile=_profile(), preferences=None, plan=plan,
        user_message="x", llm_caller=_explode,
    )
    assert action.action == "ask"


def test_propose_raises_no_more_items_when_plan_terminal():
    a = PlanItem(kind=ItemKind.INTERNSHIP, title="a", order=0, status=ItemStatus.FINALIZED)
    plan = _plan_with_items([a])
    with pytest.raises(NoMoreItems):
        propose_next_action(
            profile=_profile(), preferences=None, plan=plan,
            user_message="anything", llm_caller=_fake_caller({"action": "ask"}),
        )
