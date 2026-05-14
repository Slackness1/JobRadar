"""Project FINALIZED plan items back into the confirmed-profile payload.

Plan-mode and the legacy recommendation flow are independent paths (see
CLAUDE.md). This module is the one-way bridge: every time a plan item
reaches FINALIZED, sync_plan_to_profile mirrors its content into
ResumeConfirmedProfile.profile_json so the next /generate run picks up
the better-written bullets.

Pure function: no DB, no LLM, no I/O. Caller persists the returned profile
and flips session.recommendations_stale = 1.

Mapping table (only FINALIZED items contribute; missing children leave
existing bullets untouched, "latest plan wins" without erasing):

  ItemKind         Profile field                     Strategy
  ---------------  --------------------------------  ----------------------
  SELF_INTRO       candidate_summary (str)           parent.draft.text replaces
  EDUCATION[i]     education[i].highlights (list)    [parent.draft.text]
  INTERNSHIP[i]    internships[i].bullets (list)     [child.draft.text...]
  PROJECT[i]       projects[i].bullets (list)        [child.draft.text...]

SKILL, AWARD, CAMPUS_ACTIVITY are intentionally skipped in v1 — their
plan shape (1 parent, free-text draft) doesn't fit cleanly into the
profile schema (skills is structured technical/tools/languages, awards
is a list with no clear "headline" semantic, campus_activity has no
profile field). Revisit when the plan template grows a clearer signal.
"""
from __future__ import annotations

from app.schemas_resume_copilot import ResumeProfilePayload
from app.services.resume_copilot.plan import ItemKind, ItemStatus, PlanItem, PlanState


def newly_finalized_item_ids(old: PlanState, new: PlanState) -> list[str]:
    """IDs of items that flipped to FINALIZED between two PlanState snapshots.

    Used by the router/turn layer to decide whether to re-sync the profile
    and flip ``ResumeCopilotSession.recommendations_stale``.
    """
    old_set = {it.id for it in old.items if it.status == ItemStatus.FINALIZED}
    new_set = {it.id for it in new.items if it.status == ItemStatus.FINALIZED}
    return sorted(new_set - old_set)


def sync_plan_to_profile(
    plan: PlanState,
    profile: ResumeProfilePayload,
) -> ResumeProfilePayload:
    out = profile.model_copy(deep=True)

    items_by_kind: dict[ItemKind, list[PlanItem]] = {}
    for item in plan.items:
        items_by_kind.setdefault(item.kind, []).append(item)

    _sync_self_intro(items_by_kind.get(ItemKind.SELF_INTRO, []), out)
    _sync_flat(items_by_kind.get(ItemKind.EDUCATION, []), out.education, 'highlights')
    _sync_with_children(items_by_kind.get(ItemKind.INTERNSHIP, []), out.internships, 'bullets')
    _sync_with_children(items_by_kind.get(ItemKind.PROJECT, []), out.projects, 'bullets')

    return out


def _sync_self_intro(items: list[PlanItem], profile: ResumeProfilePayload) -> None:
    parents = [it for it in items if it.parent_id is None]
    parents.sort(key=lambda it: it.order)
    for parent in parents:
        if parent.status == ItemStatus.FINALIZED and parent.draft:
            profile.candidate_summary = parent.draft.text
            return


def _sync_flat(items: list[PlanItem], target_list: list, field: str) -> None:
    """For kinds with `bullets_per=0`: parent itself holds draft text.
    Each parent maps to one entry's field, wrapped as a single-element list.
    """
    parents = sorted([it for it in items if it.parent_id is None], key=lambda it: it.order)
    for idx, parent in enumerate(parents):
        if idx >= len(target_list):
            break
        if parent.status != ItemStatus.FINALIZED or not parent.draft:
            continue
        setattr(target_list[idx], field, [parent.draft.text])


def _sync_with_children(items: list[PlanItem], target_list: list, field: str) -> None:
    """For kinds with `bullets_per>0`: children hold draft text, parent is
    structural. Collect FINALIZED children sorted by order; if any exist,
    they replace the target's bullet list.
    """
    parents = sorted([it for it in items if it.parent_id is None], key=lambda it: it.order)
    children_by_parent: dict[str, list[PlanItem]] = {}
    for it in items:
        if it.parent_id is not None:
            children_by_parent.setdefault(it.parent_id, []).append(it)

    for idx, parent in enumerate(parents):
        if idx >= len(target_list):
            break
        children = sorted(children_by_parent.get(parent.id, []), key=lambda c: c.order)
        finalized_text = [c.draft.text for c in children if c.status == ItemStatus.FINALIZED and c.draft]
        if finalized_text:
            setattr(target_list[idx], field, finalized_text)
