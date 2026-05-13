"""Plan-mode state + state-machine for Resume Copilot.

Models the Claude-Code-style "one tool call per turn" approach to resume
building:

- Plan is a list of items (one per bullet / block).
- Items move through a strict state machine; transitions are validated by
  ``apply_action`` and illegal jumps raise ``IllegalTransition``.
- Drafts must pass ``audit_draft`` against attached evidence — a blocking
  risk flag rejects the write at the data layer, structurally preventing
  hallucinations (numbers / tech / leadership claims must be traceable
  to evidence text or tags).
- Initial plan is built from a fixed YAML template + parsed-resume counts,
  not an LLM call — deterministic, cheap, zero-hallucination.

This module is pure data + pure functions. No DB, no LLM, no I/O.
Wire-up to ``ResumeCopilotSession.plan_json`` happens in the router /
workflow layer.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ─── Enums ──────────────────────────────────────────────────────────────────

class PlanStatus(str, Enum):
    IDLE = "idle"
    DRAFTING_PLAN = "drafting_plan"
    AWAITING_PLAN_APPROVAL = "awaiting_plan_approval"
    CLARIFYING = "clarifying"
    REVIEWING = "reviewing"
    DONE = "done"
    PAUSED = "paused"


class ItemStatus(str, Enum):
    PENDING = "pending"
    CLARIFYING = "clarifying"
    READY_TO_WRITE = "ready_to_write"
    DRAFTING = "drafting"
    AWAITING_REVIEW = "awaiting_review"
    FINALIZED = "finalized"
    DROPPED = "dropped"
    BLOCKED = "blocked"


class ItemKind(str, Enum):
    SELF_INTRO = "self_intro"
    EDUCATION = "education"
    INTERNSHIP = "internship"
    PROJECT = "project"
    CAMPUS_ACTIVITY = "campus_activity"
    SKILL = "skill"
    AWARD = "award"


EvidenceTagType = Literal[
    "metric", "tech", "role", "scope", "duration",
    "outcome", "tool", "verb_subject",
]


# ─── Evidence ───────────────────────────────────────────────────────────────

class EvidenceTag(BaseModel):
    type: EvidenceTagType
    value: str
    raw: str


class Evidence(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: Literal["parsed_resume", "user_clarification", "uploaded_doc"]
    text: str
    tags: list[EvidenceTag] = Field(default_factory=list)
    citation_msg_id: str | None = None
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─── Risk flags ─────────────────────────────────────────────────────────────

RiskKind = Literal[
    "overclaim", "missing_metric", "vague_verb",
    "tech_unverified", "leadership_unverified",
]


class RiskFlag(BaseModel):
    kind: RiskKind
    detail: str
    blocking: bool = True


# ─── Draft + Questions ──────────────────────────────────────────────────────

class Draft(BaseModel):
    text: str
    used_evidence_ids: list[str] = Field(default_factory=list)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OpenQuestion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    asked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    answered_at: datetime | None = None
    answer_msg_id: str | None = None


# ─── Plan item + state ──────────────────────────────────────────────────────

class PlanItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kind: ItemKind
    title: str
    parent_id: str | None = None
    order: int = 0
    status: ItemStatus = ItemStatus.PENDING
    evidence: list[Evidence] = Field(default_factory=list)
    draft: Draft | None = None
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    rationale: str | None = None
    last_transition_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlanState(BaseModel):
    version: int = 0
    status: PlanStatus = PlanStatus.IDLE
    current_item_id: str | None = None
    items: list[PlanItem] = Field(default_factory=list)
    replan_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─── Agent action (one per LLM turn) ────────────────────────────────────────

ActionKind = Literal[
    "ask", "write", "drop", "replan",
    "ready_to_write", "finalize", "block",
]


class AskActionPayload(BaseModel):
    question_text: str


class WriteActionPayload(BaseModel):
    draft_text: str
    used_evidence_ids: list[str] = Field(default_factory=list)


class DropActionPayload(BaseModel):
    reason: str = ""


class ReplanActionPayload(BaseModel):
    added: list[PlanItem] = Field(default_factory=list)
    removed_ids: list[str] = Field(default_factory=list)
    reordered_ids: list[str] | None = None
    reason: str = ""


class BlockActionPayload(BaseModel):
    reason: str = ""


class AgentAction(BaseModel):
    action: ActionKind
    item_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


# ─── Exceptions ─────────────────────────────────────────────────────────────

class IllegalTransition(Exception):
    pass


class StaleVersion(Exception):
    pass


class EvidenceAuditFailed(Exception):
    def __init__(self, flags: list[RiskFlag]) -> None:
        self.flags = flags
        kinds = [f.kind for f in flags]
        super().__init__(f"Evidence audit failed: {kinds}")


# ─── Allowed item transitions ───────────────────────────────────────────────

ITEM_TRANSITIONS: dict[ItemStatus, set[ItemStatus]] = {
    ItemStatus.PENDING: {
        ItemStatus.CLARIFYING, ItemStatus.READY_TO_WRITE,
        ItemStatus.DROPPED, ItemStatus.BLOCKED,
    },
    ItemStatus.CLARIFYING: {
        ItemStatus.CLARIFYING, ItemStatus.READY_TO_WRITE,
        ItemStatus.DROPPED, ItemStatus.BLOCKED,
    },
    ItemStatus.READY_TO_WRITE: {
        ItemStatus.AWAITING_REVIEW,
        ItemStatus.CLARIFYING, ItemStatus.DROPPED,
    },
    ItemStatus.DRAFTING: {ItemStatus.AWAITING_REVIEW},
    ItemStatus.AWAITING_REVIEW: {
        ItemStatus.FINALIZED, ItemStatus.AWAITING_REVIEW,
        ItemStatus.CLARIFYING, ItemStatus.DROPPED,
    },
    ItemStatus.FINALIZED: {ItemStatus.CLARIFYING},
    ItemStatus.DROPPED: set(),
    ItemStatus.BLOCKED: {ItemStatus.CLARIFYING, ItemStatus.DROPPED},
}


# ─── Evidence audit ─────────────────────────────────────────────────────────

_NUMERIC_RE = re.compile(r'\d+(?:\.\d+)?\s*[万亿千百%]?')
_LEADERSHIP_TOKENS = ("带领", "主导", "负责", "管理")
_VAGUE_VERBS = ("参与", "协助", "帮助")
_TECH_CANDIDATE_RE = re.compile(r'\b[A-Z][a-zA-Z0-9+#]{1,}\b')


def audit_draft(draft_text: str, evidence: list[Evidence]) -> list[RiskFlag]:
    """Run the evidence-gate audit.

    Returns a list of risk flags. Blocking flags (kind=overclaim/leadership/
    tech_unverified) cause ``apply_action(write)`` to raise
    ``EvidenceAuditFailed``. Non-blocking flags (missing_metric/vague_verb)
    are attached to the draft for UI display but don't reject the write.
    """
    flags: list[RiskFlag] = []

    tag_metrics = {t.value for ev in evidence for t in ev.tags if t.type == "metric"}
    tag_techs = {t.value for ev in evidence for t in ev.tags if t.type == "tech"}
    verb_subjects = {t.value for ev in evidence for t in ev.tags if t.type == "verb_subject"}
    all_text = " ".join(ev.text for ev in evidence)

    for m in _NUMERIC_RE.finditer(draft_text):
        num = m.group().strip()
        if num in {"1", "1%", "2", "3"}:
            continue
        if num in all_text or num in tag_metrics:
            continue
        flags.append(RiskFlag(
            kind="overclaim",
            detail=f"draft contains {num!r} not in evidence",
            blocking=True,
        ))
        break

    for tok in _LEADERSHIP_TOKENS:
        if tok in draft_text and "self" not in verb_subjects:
            flags.append(RiskFlag(
                kind="leadership_unverified",
                detail=f"draft uses {tok!r} but no verb_subject=self in evidence",
                blocking=True,
            ))
            break

    for tech in _TECH_CANDIDATE_RE.findall(draft_text):
        if tech in tag_techs or tech in all_text:
            continue
        flags.append(RiskFlag(
            kind="tech_unverified",
            detail=f"draft mentions {tech!r} not in evidence",
            blocking=True,
        ))
        break

    if not _NUMERIC_RE.search(draft_text):
        flags.append(RiskFlag(
            kind="missing_metric",
            detail="bullet has no quantification",
            blocking=False,
        ))

    for v in _VAGUE_VERBS:
        if v in draft_text:
            flags.append(RiskFlag(
                kind="vague_verb",
                detail=f"draft uses vague verb {v!r}",
                blocking=False,
            ))
            break

    return flags


# ─── Init plan from fixed template ──────────────────────────────────────────

PLAN_TEMPLATE_DEFAULT: dict[str, dict[str, Any]] = {
    "self_intro":      {"count": 1,            "bullets_per": 0},
    "education":       {"count_from_parsed": True, "bullets_per": 0},
    "internship":      {"count_from_parsed": True, "bullets_per": 3},
    "project":         {"count_from_parsed": True, "bullets_per": 2},
    "campus_activity": {"count_from_parsed": True, "bullets_per": 2},
    "skill":           {"count": 1,            "bullets_per": 0},
    "award":           {"count_if_present": True, "bullets_per": 0},
}


def init_plan_from_template(
    parsed_counts: dict[str, int],
    template: dict[str, dict[str, Any]] | None = None,
) -> PlanState:
    """Build the initial plan deterministically.

    ``parsed_counts`` is a mapping of ItemKind value → count from the parsed
    profile, e.g. ``{"internship": 2, "project": 3, "education": 1}``.

    The returned PlanState has ``status=AWAITING_PLAN_APPROVAL`` — UI should
    surface it for user review/edit before transitioning into CLARIFYING.
    """
    template = template or PLAN_TEMPLATE_DEFAULT
    items: list[PlanItem] = []
    order = 0

    for kind_str, rule in template.items():
        try:
            kind = ItemKind(kind_str)
        except ValueError:
            continue

        if "count" in rule:
            count = int(rule["count"])
        elif rule.get("count_from_parsed"):
            count = int(parsed_counts.get(kind_str, 0))
        elif rule.get("count_if_present"):
            count = 1 if int(parsed_counts.get(kind_str, 0)) > 0 else 0
        else:
            count = 0

        bullets_per = int(rule.get("bullets_per", 0))

        for i in range(count):
            title_root = kind_str if count == 1 else f"{kind_str} #{i + 1}"
            parent = PlanItem(kind=kind, title=title_root, order=order)
            items.append(parent)
            order += 1
            for j in range(bullets_per):
                items.append(PlanItem(
                    kind=kind,
                    title=f"{title_root} - bullet #{j + 1}",
                    parent_id=parent.id,
                    order=order,
                ))
                order += 1

    return PlanState(
        version=1,
        status=PlanStatus.AWAITING_PLAN_APPROVAL,
        items=items,
    )


# ─── apply_action — the single mutation entrypoint ──────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _find_item(plan: PlanState, item_id: str | None) -> PlanItem:
    if item_id is None:
        raise IllegalTransition("action requires item_id")
    for it in plan.items:
        if it.id == item_id:
            return it
    raise IllegalTransition(f"item {item_id!r} not found")


def _check_transition(item: PlanItem, target: ItemStatus) -> None:
    allowed = ITEM_TRANSITIONS.get(item.status, set())
    if target not in allowed:
        raise IllegalTransition(
            f"item {item.id}: {item.status.value} → {target.value} not allowed"
        )


def apply_action(
    plan: PlanState,
    action: AgentAction,
    expected_version: int | None = None,
) -> PlanState:
    """Apply one AgentAction and return the new PlanState.

    Pure function — does not mutate the input ``plan``. Concurrency control
    is via ``expected_version``: if the client posts with a stale version,
    raises ``StaleVersion`` so the caller can 409 + return current state.
    """
    if expected_version is not None and plan.version != expected_version:
        raise StaleVersion(f"expected v{expected_version}, got v{plan.version}")

    new_plan = plan.model_copy(deep=True)

    if action.action == "ask":
        item = _find_item(new_plan, action.item_id)
        _check_transition(item, ItemStatus.CLARIFYING)
        payload = AskActionPayload.model_validate(action.payload)
        item.open_questions.append(OpenQuestion(text=payload.question_text))
        item.status = ItemStatus.CLARIFYING
        item.last_transition_at = _now()
        new_plan.current_item_id = item.id
        new_plan.status = PlanStatus.CLARIFYING

    elif action.action == "ready_to_write":
        item = _find_item(new_plan, action.item_id)
        _check_transition(item, ItemStatus.READY_TO_WRITE)
        item.status = ItemStatus.READY_TO_WRITE
        item.last_transition_at = _now()

    elif action.action == "write":
        item = _find_item(new_plan, action.item_id)
        _check_transition(item, ItemStatus.AWAITING_REVIEW)
        payload = WriteActionPayload.model_validate(action.payload)
        used_ev = [ev for ev in item.evidence if ev.id in payload.used_evidence_ids]
        flags = audit_draft(payload.draft_text, used_ev)
        blocking = [f for f in flags if f.blocking]
        if blocking:
            raise EvidenceAuditFailed(blocking)
        item.draft = Draft(
            text=payload.draft_text,
            used_evidence_ids=payload.used_evidence_ids,
            risk_flags=flags,
        )
        item.status = ItemStatus.AWAITING_REVIEW
        item.last_transition_at = _now()

    elif action.action == "finalize":
        item = _find_item(new_plan, action.item_id)
        _check_transition(item, ItemStatus.FINALIZED)
        item.status = ItemStatus.FINALIZED
        item.last_transition_at = _now()

    elif action.action == "drop":
        item = _find_item(new_plan, action.item_id)
        _check_transition(item, ItemStatus.DROPPED)
        item.status = ItemStatus.DROPPED
        item.last_transition_at = _now()

    elif action.action == "block":
        item = _find_item(new_plan, action.item_id)
        _check_transition(item, ItemStatus.BLOCKED)
        item.status = ItemStatus.BLOCKED
        item.last_transition_at = _now()

    elif action.action == "replan":
        payload = ReplanActionPayload.model_validate(action.payload)
        removed = set(payload.removed_ids)
        new_plan.items = [it for it in new_plan.items if it.id not in removed]
        new_plan.items.extend(payload.added)
        if payload.reordered_ids is not None:
            by_id = {it.id: it for it in new_plan.items}
            reordered: list[PlanItem] = []
            for i, item_id in enumerate(payload.reordered_ids):
                it = by_id.get(item_id)
                if it is not None:
                    it.order = i
                    reordered.append(it)
            tail_offset = len(reordered)
            tail = [it for it in new_plan.items if it.id not in set(payload.reordered_ids)]
            for j, it in enumerate(tail):
                it.order = tail_offset + j
            new_plan.items = reordered + tail
        new_plan.replan_count += 1

    else:
        raise IllegalTransition(f"unknown action {action.action!r}")

    new_plan.version += 1
    new_plan.updated_at = _now()
    return new_plan
