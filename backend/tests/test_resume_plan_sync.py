"""Unit tests for plan_sync — projecting FINALIZED plan items back into
the confirmed-profile payload."""
from __future__ import annotations

from app.schemas_resume_copilot import (
    ResumeEducationItem,
    ResumeInternshipItem,
    ResumeProfilePayload,
    ResumeProjectItem,
)
from app.services.resume_copilot.plan import (
    Draft,
    ItemKind,
    ItemStatus,
    PlanItem,
    PlanState,
)
from app.services.resume_copilot.plan_sync import (
    newly_finalized_item_ids,
    sync_plan_to_profile,
)


def _final(kind: ItemKind, text: str, *, parent_id: str | None = None, order: int = 0, item_id: str | None = None) -> PlanItem:
    item = PlanItem(
        kind=kind,
        title=f"{kind.value}-{order}",
        parent_id=parent_id,
        order=order,
        status=ItemStatus.FINALIZED,
        draft=Draft(text=text),
    )
    if item_id:
        item.id = item_id
    return item


def _pending_parent(kind: ItemKind, *, order: int = 0, item_id: str | None = None) -> PlanItem:
    item = PlanItem(kind=kind, title=f"{kind.value}-{order}", order=order)
    if item_id:
        item.id = item_id
    return item


# ─── self_intro ─────────────────────────────────────────────────────────────

def test_self_intro_finalized_overwrites_summary():
    plan = PlanState(items=[_final(ItemKind.SELF_INTRO, "数据分析方向，互联网赛道")])
    profile = ResumeProfilePayload(candidate_summary="(旧版)")
    out = sync_plan_to_profile(plan, profile)
    assert out.candidate_summary == "数据分析方向，互联网赛道"


def test_self_intro_pending_leaves_summary_alone():
    plan = PlanState(items=[_pending_parent(ItemKind.SELF_INTRO)])
    profile = ResumeProfilePayload(candidate_summary="(旧版保留)")
    out = sync_plan_to_profile(plan, profile)
    assert out.candidate_summary == "(旧版保留)"


# ─── education ──────────────────────────────────────────────────────────────

def test_education_finalized_writes_highlights_wrapped():
    plan = PlanState(items=[
        _final(ItemKind.EDUCATION, "GPA 3.9 / 副修计算机", order=0),
        _final(ItemKind.EDUCATION, "海外交换 UCSD", order=1),
    ])
    profile = ResumeProfilePayload(education=[
        ResumeEducationItem(school="上交大", highlights=["旧"]),
        ResumeEducationItem(school="UCSD-exchange", highlights=[]),
    ])
    out = sync_plan_to_profile(plan, profile)
    assert out.education[0].highlights == ["GPA 3.9 / 副修计算机"]
    assert out.education[1].highlights == ["海外交换 UCSD"]


# ─── internship + project (children-driven) ─────────────────────────────────

def test_internship_collects_finalized_children_in_order():
    parent_id = "intern-0"
    plan = PlanState(items=[
        _pending_parent(ItemKind.INTERNSHIP, order=0, item_id=parent_id),
        _final(ItemKind.INTERNSHIP, "做了 A/B 测试，提升 CTR 3%", parent_id=parent_id, order=1),
        _final(ItemKind.INTERNSHIP, "搭了 SQL 看板，沉淀 12 张报表", parent_id=parent_id, order=2),
    ])
    profile = ResumeProfilePayload(internships=[
        ResumeInternshipItem(company="字节", role="数据实习", bullets=["旧版 bullet"]),
    ])
    out = sync_plan_to_profile(plan, profile)
    assert out.internships[0].bullets == [
        "做了 A/B 测试，提升 CTR 3%",
        "搭了 SQL 看板，沉淀 12 张报表",
    ]


def test_internship_partial_finalized_children_only_includes_finalized():
    parent_id = "intern-0"
    final_child = _final(ItemKind.INTERNSHIP, "已写", parent_id=parent_id, order=1)
    pending_child = _pending_parent(ItemKind.INTERNSHIP, order=2)
    pending_child.parent_id = parent_id
    plan = PlanState(items=[
        _pending_parent(ItemKind.INTERNSHIP, order=0, item_id=parent_id),
        final_child,
        pending_child,
    ])
    profile = ResumeProfilePayload(internships=[
        ResumeInternshipItem(company="字节", bullets=["旧"]),
    ])
    out = sync_plan_to_profile(plan, profile)
    assert out.internships[0].bullets == ["已写"]


def test_internship_no_finalized_children_keeps_old_bullets():
    parent_id = "intern-0"
    plan = PlanState(items=[
        _pending_parent(ItemKind.INTERNSHIP, order=0, item_id=parent_id),
    ])
    profile = ResumeProfilePayload(internships=[
        ResumeInternshipItem(company="字节", bullets=["旧 bullet 1", "旧 bullet 2"]),
    ])
    out = sync_plan_to_profile(plan, profile)
    assert out.internships[0].bullets == ["旧 bullet 1", "旧 bullet 2"]


def test_more_plan_parents_than_profile_entries_is_safe():
    """Plan has 2 internship parents but profile only 1 — extra parents drop silently."""
    p0, p1 = "intern-0", "intern-1"
    plan = PlanState(items=[
        _pending_parent(ItemKind.INTERNSHIP, order=0, item_id=p0),
        _final(ItemKind.INTERNSHIP, "first-bullet", parent_id=p0, order=1),
        _pending_parent(ItemKind.INTERNSHIP, order=2, item_id=p1),
        _final(ItemKind.INTERNSHIP, "orphan-bullet", parent_id=p1, order=3),
    ])
    profile = ResumeProfilePayload(internships=[
        ResumeInternshipItem(company="字节"),
    ])
    out = sync_plan_to_profile(plan, profile)
    assert len(out.internships) == 1
    assert out.internships[0].bullets == ["first-bullet"]


def test_project_children_path_works_same_as_internship():
    parent_id = "proj-0"
    plan = PlanState(items=[
        _pending_parent(ItemKind.PROJECT, order=0, item_id=parent_id),
        _final(ItemKind.PROJECT, "用 PyTorch 训练 BERT 文本分类", parent_id=parent_id, order=1),
    ])
    profile = ResumeProfilePayload(projects=[
        ResumeProjectItem(name="毕设", bullets=[]),
    ])
    out = sync_plan_to_profile(plan, profile)
    assert out.projects[0].bullets == ["用 PyTorch 训练 BERT 文本分类"]


# ─── skipped kinds (skill / award / campus_activity) ────────────────────────

def test_skill_and_award_finalized_do_not_modify_profile():
    plan = PlanState(items=[
        _final(ItemKind.SKILL, "Python / SQL / Tableau"),
        _final(ItemKind.AWARD, "校长奖学金"),
        _final(ItemKind.CAMPUS_ACTIVITY, "学生会主席"),
    ])
    profile = ResumeProfilePayload(awards=["旧奖项"])
    out = sync_plan_to_profile(plan, profile)
    assert out.awards == ["旧奖项"]


# ─── invariants ─────────────────────────────────────────────────────────────

def test_idempotent():
    parent_id = "intern-0"
    plan = PlanState(items=[
        _pending_parent(ItemKind.INTERNSHIP, order=0, item_id=parent_id),
        _final(ItemKind.INTERNSHIP, "稳定输出", parent_id=parent_id, order=1),
    ])
    profile = ResumeProfilePayload(internships=[ResumeInternshipItem(company="x")])
    once = sync_plan_to_profile(plan, profile)
    twice = sync_plan_to_profile(plan, once)
    assert once.model_dump() == twice.model_dump()


def test_does_not_mutate_input_profile():
    plan = PlanState(items=[_final(ItemKind.SELF_INTRO, "新")])
    profile = ResumeProfilePayload(candidate_summary="原")
    _ = sync_plan_to_profile(plan, profile)
    assert profile.candidate_summary == "原"


# ─── newly_finalized_item_ids ───────────────────────────────────────────────

def test_newly_finalized_returns_only_new_finalized():
    a = PlanItem(kind=ItemKind.SELF_INTRO, title="x", status=ItemStatus.PENDING)
    b = PlanItem(kind=ItemKind.SELF_INTRO, title="y", status=ItemStatus.AWAITING_REVIEW)
    c = PlanItem(kind=ItemKind.SELF_INTRO, title="z", status=ItemStatus.FINALIZED)
    old = PlanState(items=[a, b, c])

    a2 = a.model_copy(update={'status': ItemStatus.FINALIZED})
    b2 = b.model_copy()  # unchanged
    c2 = c.model_copy()  # already finalized
    new = PlanState(items=[a2, b2, c2])

    assert newly_finalized_item_ids(old, new) == [a.id]


def test_newly_finalized_empty_when_nothing_changed():
    items = [PlanItem(kind=ItemKind.SELF_INTRO, title="x", status=ItemStatus.FINALIZED, draft=Draft(text="t"))]
    plan = PlanState(items=items)
    assert newly_finalized_item_ids(plan, plan) == []
