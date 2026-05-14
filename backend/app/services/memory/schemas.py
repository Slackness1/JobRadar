"""Pydantic payload schemas — one per ``account_memory.category``.

The dispatcher validates ``payload_json`` against the matching schema **before**
writing. Adding a new category = adding a payload class + registering it in
``CATEGORY_TO_SCHEMA`` — no DB migration required.

Categories(8 total):

| category          | payload class            | who writes it                       |
|-------------------|--------------------------|-------------------------------------|
| evidence          | EvidencePayload          | parser + chat extractor + plan      |
| experience        | ExperiencePayload        | chat extractor                      |
| skill_claim       | SkillClaimPayload        | chat extractor + parser             |
| preference        | PreferencePayload        | chat extractor + preferences panel  |
| identity_fact     | IdentityFactPayload      | parser + chat extractor             |
| goal              | GoalPayload              | plan clarifying / chat              |
| commitment        | CommitmentPayload        | plan finalize (only)                |
| weakness_signal   | WeaknessSignalPayload    | interview report                    |
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Type

from pydantic import BaseModel, Field, field_validator


# ─── Shared sub-models ────────────────────────────────────────────────────────

EvidenceTagType = Literal[
    "metric", "tech", "role", "scope", "duration", "outcome", "tool", "verb_subject",
]


class EvidenceTag(BaseModel):
    """Inline tag attached to an Evidence row. Mirrors plan.py::EvidenceTag so
    a plan PlanItem.evidence[].tags can be persisted into account_memory rows
    without lossy conversion."""

    type: EvidenceTagType
    value: str
    raw: str = ""


# Fixed ontology of behavioral STAR dimensions. Interview question generator
# joins on these. Adding one MUST also update interview rubric prompts.
ALLOWED_STAR_DIMENSIONS = (
    "leadership",
    "teamwork",
    "conflict_resolution",
    "initiative",
    "deadline_pressure",
    "ambiguity",
    "cross_functional",
    "failure_recovery",
    "planning",
    "analytical_thinking",
    "creativity",
    "communication",
    "stakeholder_mgmt",
    "ownership",
)


# ─── Category payloads ────────────────────────────────────────────────────────


class EvidencePayload(BaseModel):
    """Bullet-grained citable fact — source of truth for Plan Mode drafts.

    One Evidence ≈ one defendable claim about the user, with tags identifying
    what *kind* of claim it is (metric/tech/role/etc.) and a citation back to
    its source.
    """

    text: str                          # "次留率从 12% 提到 16%"
    tags: list[EvidenceTag] = Field(default_factory=list)
    source: Literal["parsed_resume", "user_clarification", "uploaded_doc", "chat_extract"]
    related_role: str | None = None    # "字节 / 产品实习生"

    @field_validator("text")
    @classmethod
    def _text_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Evidence.text must be non-empty")
        return v.strip()[:500]


class ExperiencePayload(BaseModel):
    """STAR-narratable retelling of a multi-evidence experience.

    Used by interview ExperienceRecaller. A single experience may cite many
    Evidence rows (via ``evidence_ids``), e.g. "次留率 12→16%" + "三个月" +
    "字节用户增长团队" all support the same STAR story.
    """

    behavioral_hook: str               # "S=...|T=...|A=...|R=..." — reusable verbatim
    star_dimensions: list[str] = Field(default_factory=list)
    quantified: dict = Field(default_factory=dict)  # {team_size, duration_months, outcome, ...}
    evidence_ids: list[int] = Field(default_factory=list)

    @field_validator("star_dimensions")
    @classmethod
    def _validate_dimensions(cls, dims: list[str]) -> list[str]:
        invalid = [d for d in dims if d not in ALLOWED_STAR_DIMENSIONS]
        if invalid:
            raise ValueError(
                f"Unknown star_dimensions: {invalid}. "
                f"Allowed: {ALLOWED_STAR_DIMENSIONS}"
            )
        return dims


class SkillClaimPayload(BaseModel):
    """User claims a skill. Optional supporting evidence_ids.

    Note: a skill_claim with no evidence is acceptable (the user just said
    they know X). Interview & plan should treat unsupported skill_claims as
    weaker signal than evidence-backed ones.
    """

    skill_name: str
    level: Literal["basic", "intermediate", "advanced", "expert"] | None = None
    evidence_ids: list[int] = Field(default_factory=list)

    @field_validator("skill_name")
    @classmethod
    def _skill_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("skill_name must be non-empty")
        return v.strip()[:120]


PreferenceDimension = Literal[
    "city", "industry", "role", "comp", "company_type", "stage",
]


class PreferencePayload(BaseModel):
    """User's job-search preferences. ``dimension`` is the axis, ``value`` the choice.

    Newer preferences supersede older ones via ``superseded_by_id`` on the
    parent AccountMemory row — the dispatcher handles that when caller passes
    ``supersede_existing=True``.
    """

    dimension: PreferenceDimension
    value: str

    @field_validator("value")
    @classmethod
    def _value_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("preference.value must be non-empty")
        return v.strip()[:200]


IdentityFactKind = Literal[
    "school", "major", "degree", "graduation_year", "program",
]


class IdentityFactPayload(BaseModel):
    """Static-ish facts about the user's background. Like preference, can be
    superseded (rare: user transfers schools) but normally stable."""

    kind: IdentityFactKind
    value: str

    @field_validator("value")
    @classmethod
    def _value_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("identity_fact.value must be non-empty")
        return v.strip()[:200]


class GoalPayload(BaseModel):
    """The user's stated career goal. Read by plan generation + interview JD
    framing. Multiple active goals are allowed (e.g. "买方量化研究员" AND
    "卖方研究助理" as fallback)."""

    target_role: str
    deadline: str | None = None        # "2026 秋招" — free-text, not parsed
    status: Literal["active", "paused", "achieved", "abandoned"] = "active"


class CommitmentPayload(BaseModel):
    """A concrete action the user has committed to.

    Written **only** by plan finalize — see design doc §10 Q4 for why we don't
    extract commitments from chat. ``linked_plan_item_id`` is the source
    PlanItem.id from the session-scoped plan_json.
    """

    description: str
    deadline: datetime | None = None
    linked_plan_item_id: str | None = None
    status: Literal["pending", "done", "abandoned"] = "pending"

    @field_validator("description")
    @classmethod
    def _description_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("commitment.description must be non-empty")
        return v.strip()[:500]


class WeaknessSignalPayload(BaseModel):
    """A mock-interview-detected weakness in a STAR dimension.

    Severity gradations let downstream surfaces (next interview, plan replan)
    prioritise. ``source_interview_id`` ties back to InterviewReport.id for
    audit / drill-down.
    """

    dimension: str                     # not constrained to STAR; can be skill-specific
    severity: Literal["minor", "moderate", "major"]
    source_interview_id: int
    suggested_practice: str | None = None


# ─── Category → payload class registry ────────────────────────────────────────

CATEGORY_TO_SCHEMA: dict[str, Type[BaseModel]] = {
    "evidence": EvidencePayload,
    "experience": ExperiencePayload,
    "skill_claim": SkillClaimPayload,
    "preference": PreferencePayload,
    "identity_fact": IdentityFactPayload,
    "goal": GoalPayload,
    "commitment": CommitmentPayload,
    "weakness_signal": WeaknessSignalPayload,
}


def validate_payload(category: str, payload_data: dict | BaseModel) -> BaseModel:
    """Validate a payload dict against its category's pydantic schema.

    Raises ValueError for unknown category or schema violation. Returns the
    parsed pydantic model instance — caller can ``.model_dump_json()`` to get
    the canonical serialization for DB storage.
    """
    schema_cls = CATEGORY_TO_SCHEMA.get(category)
    if schema_cls is None:
        raise ValueError(
            f"Unknown account_memory category: {category!r}. "
            f"Allowed: {sorted(CATEGORY_TO_SCHEMA)}"
        )
    if isinstance(payload_data, schema_cls):
        return payload_data
    if isinstance(payload_data, BaseModel):
        raise ValueError(
            f"Payload type mismatch for category {category!r}: "
            f"got {type(payload_data).__name__}, expected {schema_cls.__name__}"
        )
    return schema_cls.model_validate(payload_data)


__all__ = [
    "EvidenceTag",
    "ALLOWED_STAR_DIMENSIONS",
    "EvidencePayload",
    "ExperiencePayload",
    "SkillClaimPayload",
    "PreferencePayload",
    "IdentityFactPayload",
    "GoalPayload",
    "CommitmentPayload",
    "WeaknessSignalPayload",
    "CATEGORY_TO_SCHEMA",
    "validate_payload",
]
