"""Tests for resume copilot plan-mode data model + state machine."""
from __future__ import annotations

import pytest

from app.services.resume_copilot.plan import (
    AgentAction,
    Evidence,
    EvidenceAuditFailed,
    EvidenceTag,
    IllegalTransition,
    ItemKind,
    ItemStatus,
    PlanItem,
    PlanState,
    PlanStatus,
    StaleVersion,
    apply_action,
    audit_draft,
    init_plan_from_template,
)


# ─── init_plan_from_template ────────────────────────────────────────────────

def test_template_with_no_experiences():
    plan = init_plan_from_template({"internship": 0, "project": 0, "education": 0})
    titles = [it.title for it in plan.items]
    # self_intro + skill always present (count=1)
    assert "self_intro" in titles
    assert "skill" in titles
    # award skipped because count_if_present and parsed=0
    assert "award" not in titles
    assert plan.status == PlanStatus.AWAITING_PLAN_APPROVAL
    assert plan.version == 1


def test_template_expands_bullets_per_experience():
    plan = init_plan_from_template({
        "internship": 2,
        "project": 3,
        "education": 1,
        "campus_activity": 1,
        "award": 2,
    })
    # 2 internship parents + 6 bullets
    intern_items = [it for it in plan.items if it.kind == ItemKind.INTERNSHIP]
    assert len([it for it in intern_items if it.parent_id is None]) == 2
    assert len([it for it in intern_items if it.parent_id is not None]) == 6
    # 3 project parents + 6 bullets
    project_items = [it for it in plan.items if it.kind == ItemKind.PROJECT]
    assert len([it for it in project_items if it.parent_id is None]) == 3
    assert len([it for it in project_items if it.parent_id is not None]) == 6
    # award is single-item (count_if_present=True, bullets_per=0)
    award_items = [it for it in plan.items if it.kind == ItemKind.AWARD]
    assert len(award_items) == 1


def test_template_orders_are_sequential_and_unique():
    plan = init_plan_from_template({"internship": 2, "project": 1})
    orders = [it.order for it in plan.items]
    assert orders == sorted(orders)
    assert len(set(orders)) == len(orders)


def test_template_child_items_reference_existing_parent():
    plan = init_plan_from_template({"internship": 1})
    parent_ids = {it.id for it in plan.items if it.parent_id is None}
    for child in plan.items:
        if child.parent_id is not None:
            assert child.parent_id in parent_ids


# ─── State machine: legal transitions ──────────────────────────────────────

def _single_item_plan(status: ItemStatus = ItemStatus.PENDING, evidence=None) -> PlanState:
    item = PlanItem(
        kind=ItemKind.INTERNSHIP,
        title="test bullet",
        status=status,
        evidence=evidence or [],
    )
    return PlanState(version=1, items=[item])


def test_ask_transitions_pending_to_clarifying():
    plan = _single_item_plan()
    item_id = plan.items[0].id
    action = AgentAction(action="ask", item_id=item_id, payload={"question_text": "数据量？"})
    new_plan = apply_action(plan, action)
    assert new_plan.items[0].status == ItemStatus.CLARIFYING
    assert len(new_plan.items[0].open_questions) == 1
    assert new_plan.items[0].open_questions[0].text == "数据量？"
    assert new_plan.status == PlanStatus.CLARIFYING
    assert new_plan.current_item_id == item_id
    assert new_plan.version == 2


def test_ready_to_write_skips_clarify_when_evidence_rich():
    plan = _single_item_plan()
    item_id = plan.items[0].id
    action = AgentAction(action="ready_to_write", item_id=item_id)
    new_plan = apply_action(plan, action)
    assert new_plan.items[0].status == ItemStatus.READY_TO_WRITE


def test_finalize_requires_awaiting_review():
    plan = _single_item_plan(status=ItemStatus.AWAITING_REVIEW)
    item_id = plan.items[0].id
    action = AgentAction(action="finalize", item_id=item_id)
    new_plan = apply_action(plan, action)
    assert new_plan.items[0].status == ItemStatus.FINALIZED


def test_drop_from_clarifying():
    plan = _single_item_plan(status=ItemStatus.CLARIFYING)
    item_id = plan.items[0].id
    action = AgentAction(action="drop", item_id=item_id, payload={"reason": "用户说不写"})
    new_plan = apply_action(plan, action)
    assert new_plan.items[0].status == ItemStatus.DROPPED


def test_finalized_can_go_back_to_clarifying():
    plan = _single_item_plan(status=ItemStatus.FINALIZED)
    item_id = plan.items[0].id
    action = AgentAction(action="ask", item_id=item_id, payload={"question_text": "想再补一个细节"})
    new_plan = apply_action(plan, action)
    assert new_plan.items[0].status == ItemStatus.CLARIFYING


# ─── State machine: illegal transitions ────────────────────────────────────

def test_pending_to_finalized_directly_is_rejected():
    plan = _single_item_plan(status=ItemStatus.PENDING)
    item_id = plan.items[0].id
    action = AgentAction(action="finalize", item_id=item_id)
    with pytest.raises(IllegalTransition):
        apply_action(plan, action)


def test_dropped_is_terminal_no_resurrection():
    plan = _single_item_plan(status=ItemStatus.DROPPED)
    item_id = plan.items[0].id
    for kind in ("ask", "ready_to_write", "write", "finalize"):
        with pytest.raises(IllegalTransition):
            apply_action(plan, AgentAction(action=kind, item_id=item_id, payload={"question_text": "x", "draft_text": "y"}))


def test_unknown_item_id_raises():
    plan = _single_item_plan()
    with pytest.raises(IllegalTransition):
        apply_action(plan, AgentAction(action="ask", item_id="nonexistent", payload={"question_text": "?"}))


# ─── Concurrency ───────────────────────────────────────────────────────────

def test_stale_version_rejected():
    plan = _single_item_plan()
    item_id = plan.items[0].id
    action = AgentAction(action="ready_to_write", item_id=item_id)
    with pytest.raises(StaleVersion):
        apply_action(plan, action, expected_version=999)


def test_version_increments_on_every_action():
    plan = _single_item_plan()
    item_id = plan.items[0].id
    p1 = apply_action(plan, AgentAction(action="ready_to_write", item_id=item_id))
    assert p1.version == plan.version + 1
    # use an evidence-free, number-free, vague draft so audit returns only
    # non-blocking flags and the write is accepted
    p2 = apply_action(p1, AgentAction(
        action="write",
        item_id=item_id,
        payload={"draft_text": "完成了一项工作", "used_evidence_ids": []},
    ))
    assert p2.version == p1.version + 1


# ─── Pure-function discipline ──────────────────────────────────────────────

def test_apply_action_does_not_mutate_input():
    plan = _single_item_plan()
    item_id = plan.items[0].id
    snapshot_status = plan.items[0].status
    snapshot_version = plan.version
    apply_action(plan, AgentAction(action="ask", item_id=item_id, payload={"question_text": "?"}))
    assert plan.items[0].status == snapshot_status
    assert plan.version == snapshot_version


# ─── Evidence audit: blocking flags ────────────────────────────────────────

def _evidence(text: str, tags=None) -> Evidence:
    return Evidence(source="user_clarification", text=text, tags=tags or [])


def test_audit_passes_when_numbers_in_evidence():
    ev = [_evidence("处理了 30 万行数据，留存提升 1.2%")]
    flags = audit_draft("处理 30 万行数据，留存提升 1.2%", ev)
    blocking = [f for f in flags if f.blocking]
    assert blocking == []


def test_audit_flags_overclaim_when_number_not_in_evidence():
    ev = [_evidence("处理了一些数据")]
    flags = audit_draft("处理了 30 万行数据", ev)
    overclaims = [f for f in flags if f.kind == "overclaim"]
    assert len(overclaims) == 1
    assert overclaims[0].blocking


def test_audit_passes_overclaim_via_metric_tag():
    ev = [Evidence(
        source="user_clarification",
        text="处理了一批数据，规模在百万级",
        tags=[EvidenceTag(type="metric", value="30万", raw="百万级")],
    )]
    flags = audit_draft("处理 30万 行数据", ev)
    blocking = [f for f in flags if f.kind == "overclaim"]
    assert blocking == []


def test_audit_flags_leadership_without_verb_subject_self():
    ev = [_evidence("和组里同学一起做了项目")]
    flags = audit_draft("带领 3 人完成项目", ev)
    leadership = [f for f in flags if f.kind == "leadership_unverified"]
    assert len(leadership) == 1
    assert leadership[0].blocking


def test_audit_passes_leadership_with_verb_subject_tag():
    ev = [Evidence(
        source="user_clarification",
        text="3 人小组，我是组长",
        tags=[
            EvidenceTag(type="verb_subject", value="self", raw="我"),
            EvidenceTag(type="scope", value="3人", raw="3 人小组"),
        ],
    )]
    flags = audit_draft("带领 3 人完成项目", ev)
    assert not any(f.kind == "leadership_unverified" for f in flags)


def test_audit_flags_tech_unverified():
    ev = [_evidence("用 Python 做数据分析")]
    flags = audit_draft("用 Python 和 Spark 做大数据 ETL", ev)
    tech_flags = [f for f in flags if f.kind == "tech_unverified"]
    assert len(tech_flags) == 1
    assert "Spark" in tech_flags[0].detail


def test_audit_passes_tech_via_tag():
    ev = [Evidence(
        source="user_clarification",
        text="做了一些大数据处理 ETL",
        tags=[
            EvidenceTag(type="tech", value="Spark", raw="大数据处理"),
        ],
    )]
    flags = audit_draft("用 Spark 做 ETL", ev)
    # both Spark (via tag) and ETL (via evidence text) should pass
    assert not any(f.kind == "tech_unverified" for f in flags)


# ─── Evidence audit: non-blocking flags ────────────────────────────────────

def test_audit_warns_missing_metric_non_blocking():
    ev = [_evidence("做了一些事")]
    flags = audit_draft("做了一些事情", ev)
    missing = [f for f in flags if f.kind == "missing_metric"]
    assert len(missing) == 1
    assert missing[0].blocking is False


def test_audit_warns_vague_verb_non_blocking():
    ev = [_evidence("参加了团队")]
    flags = audit_draft("参与了一个 5 人小组", ev)
    vague = [f for f in flags if f.kind == "vague_verb"]
    assert len(vague) == 1
    assert vague[0].blocking is False


# ─── Write action — full audit gate integration ────────────────────────────

def test_write_with_blocking_audit_fails_and_does_not_mutate():
    plan = _single_item_plan(status=ItemStatus.READY_TO_WRITE)
    item_id = plan.items[0].id
    action = AgentAction(
        action="write",
        item_id=item_id,
        payload={"draft_text": "处理了 999 万行数据", "used_evidence_ids": []},
    )
    with pytest.raises(EvidenceAuditFailed):
        apply_action(plan, action)
    # plan unchanged
    assert plan.items[0].status == ItemStatus.READY_TO_WRITE
    assert plan.items[0].draft is None


def test_write_with_audit_pass_lands_in_awaiting_review():
    ev = Evidence(
        source="user_clarification",
        text="处理 30 万行数据，留存 +1.5%",
    )
    plan = _single_item_plan(status=ItemStatus.READY_TO_WRITE, evidence=[ev])
    item_id = plan.items[0].id
    action = AgentAction(
        action="write",
        item_id=item_id,
        payload={
            "draft_text": "处理 30 万行数据，留存提升 1.5%",
            "used_evidence_ids": [ev.id],
        },
    )
    new_plan = apply_action(plan, action)
    assert new_plan.items[0].status == ItemStatus.AWAITING_REVIEW
    assert new_plan.items[0].draft is not None
    assert new_plan.items[0].draft.text == "处理 30 万行数据，留存提升 1.5%"


def test_write_can_re_run_from_awaiting_review_for_regenerate():
    ev = Evidence(source="user_clarification", text="30 万行数据 1.5% 提升")
    plan = _single_item_plan(status=ItemStatus.AWAITING_REVIEW, evidence=[ev])
    item_id = plan.items[0].id
    action = AgentAction(
        action="write",
        item_id=item_id,
        payload={
            "draft_text": "重写后版本 30 万行 1.5%",
            "used_evidence_ids": [ev.id],
        },
    )
    new_plan = apply_action(plan, action)
    assert new_plan.items[0].draft.text == "重写后版本 30 万行 1.5%"


# ─── Replan ────────────────────────────────────────────────────────────────

def test_replan_adds_and_removes_items():
    plan = _single_item_plan()
    old_id = plan.items[0].id
    new_item = PlanItem(kind=ItemKind.PROJECT, title="新增的项目", order=1)
    action = AgentAction(
        action="replan",
        payload={
            "added": [new_item.model_dump()],
            "removed_ids": [old_id],
            "reason": "学生说那条要删，加这条",
        },
    )
    new_plan = apply_action(plan, action)
    assert len(new_plan.items) == 1
    assert new_plan.items[0].title == "新增的项目"
    assert new_plan.replan_count == 1


def test_replan_reorders_items():
    plan = init_plan_from_template({"internship": 0, "project": 0})
    # template gave us self_intro + skill at minimum
    assert len(plan.items) >= 2
    ids = [it.id for it in plan.items]
    reversed_ids = list(reversed(ids))
    action = AgentAction(
        action="replan",
        payload={"reordered_ids": reversed_ids, "reason": "调整顺序"},
    )
    new_plan = apply_action(plan, action)
    new_ids = [it.id for it in new_plan.items]
    assert new_ids == reversed_ids
