"""Unit tests for account_memory payload schemas.

Each category has its own validator constraints; we test the boundary cases
since these schemas are the integrity contract between modules.
"""
import pytest
from pydantic import ValidationError

from app.services.memory.schemas import (
    CATEGORY_TO_SCHEMA,
    CommitmentPayload,
    EvidencePayload,
    EvidenceTag,
    ExperiencePayload,
    GoalPayload,
    IdentityFactPayload,
    PreferencePayload,
    SkillClaimPayload,
    WeaknessSignalPayload,
    validate_payload,
)


# ─── EvidencePayload ─────────────────────────────────────────────────────────


def test_evidence_minimum_valid():
    p = EvidencePayload(text="次留率从 12% 提升到 16%", source="parsed_resume")
    assert p.text == "次留率从 12% 提升到 16%"
    assert p.tags == []
    assert p.related_role is None


def test_evidence_with_tags():
    p = EvidencePayload(
        text="DAU 提升 8%",
        source="chat_extract",
        tags=[
            EvidenceTag(type="metric", value="DAU", raw="DAU 提升 8%"),
            EvidenceTag(type="outcome", value="+8%", raw="提升 8%"),
        ],
    )
    assert len(p.tags) == 2
    assert p.tags[0].type == "metric"


def test_evidence_empty_text_rejected():
    with pytest.raises(ValidationError):
        EvidencePayload(text="   ", source="parsed_resume")


def test_evidence_unknown_source_rejected():
    with pytest.raises(ValidationError):
        EvidencePayload(text="x", source="random_source")


def test_evidence_text_truncated():
    long_text = "a" * 1000
    p = EvidencePayload(text=long_text, source="chat_extract")
    assert len(p.text) == 500


# ─── ExperiencePayload ───────────────────────────────────────────────────────


def test_experience_basic():
    p = ExperiencePayload(
        behavioral_hook="S=...|T=...|A=...|R=...",
        star_dimensions=["leadership", "teamwork"],
        quantified={"team_size": 50},
        evidence_ids=[1, 2, 3],
    )
    assert p.star_dimensions == ["leadership", "teamwork"]


def test_experience_unknown_dimension_rejected():
    with pytest.raises(ValidationError):
        ExperiencePayload(
            behavioral_hook="x",
            star_dimensions=["not_a_real_dim"],
        )


def test_experience_empty_dimensions_allowed():
    # Empty dims is OK at the schema level — caller logic decides whether
    # an experience without dimensions is useful.
    p = ExperiencePayload(behavioral_hook="x", star_dimensions=[])
    assert p.star_dimensions == []


# ─── SkillClaimPayload ───────────────────────────────────────────────────────


def test_skill_claim_minimum():
    p = SkillClaimPayload(skill_name="Python pandas")
    assert p.level is None
    assert p.evidence_ids == []


def test_skill_claim_with_level():
    p = SkillClaimPayload(skill_name="SQL", level="advanced", evidence_ids=[42])
    assert p.level == "advanced"


def test_skill_claim_unknown_level_rejected():
    with pytest.raises(ValidationError):
        SkillClaimPayload(skill_name="Python", level="superhuman")


def test_skill_claim_empty_name_rejected():
    with pytest.raises(ValidationError):
        SkillClaimPayload(skill_name=" ")


# ─── PreferencePayload ───────────────────────────────────────────────────────


def test_preference_basic():
    p = PreferencePayload(dimension="city", value="上海")
    assert p.dimension == "city"


def test_preference_unknown_dimension_rejected():
    with pytest.raises(ValidationError):
        PreferencePayload(dimension="zodiac_sign", value="Aries")


def test_preference_empty_value_rejected():
    with pytest.raises(ValidationError):
        PreferencePayload(dimension="city", value="")


# ─── IdentityFactPayload ─────────────────────────────────────────────────────


def test_identity_basic():
    p = IdentityFactPayload(kind="school", value="上海交通大学")
    assert p.value == "上海交通大学"


def test_identity_unknown_kind_rejected():
    with pytest.raises(ValidationError):
        IdentityFactPayload(kind="favorite_color", value="blue")


# ─── GoalPayload ─────────────────────────────────────────────────────────────


def test_goal_basic():
    g = GoalPayload(target_role="买方量化研究员", deadline="2026 秋招")
    assert g.status == "active"


def test_goal_unknown_status_rejected():
    with pytest.raises(ValidationError):
        GoalPayload(target_role="x", status="unknown_thing")


# ─── CommitmentPayload ───────────────────────────────────────────────────────


def test_commitment_basic():
    c = CommitmentPayload(description="完成 字节实习段的简历改写")
    assert c.status == "pending"
    assert c.linked_plan_item_id is None


def test_commitment_empty_description_rejected():
    with pytest.raises(ValidationError):
        CommitmentPayload(description="   ")


def test_commitment_with_plan_link():
    c = CommitmentPayload(
        description="改写 internships.0.bullets",
        linked_plan_item_id="abc-123",
        status="done",
    )
    assert c.linked_plan_item_id == "abc-123"


# ─── WeaknessSignalPayload ───────────────────────────────────────────────────


def test_weakness_basic():
    w = WeaknessSignalPayload(
        dimension="analytical_thinking",
        severity="moderate",
        source_interview_id=7,
    )
    assert w.suggested_practice is None


def test_weakness_unknown_severity_rejected():
    with pytest.raises(ValidationError):
        WeaknessSignalPayload(
            dimension="x", severity="catastrophic", source_interview_id=1
        )


# ─── Registry + dispatcher entry validate_payload ───────────────────────────


def test_registry_has_all_eight_categories():
    expected = {
        "evidence", "experience", "skill_claim", "preference",
        "identity_fact", "goal", "commitment", "weakness_signal",
    }
    assert set(CATEGORY_TO_SCHEMA.keys()) == expected


def test_validate_payload_dispatches_to_right_schema():
    out = validate_payload("preference", {"dimension": "city", "value": "上海"})
    assert isinstance(out, PreferencePayload)


def test_validate_payload_unknown_category_raises():
    with pytest.raises(ValueError) as exc:
        validate_payload("not_a_category", {})
    assert "Unknown account_memory category" in str(exc.value)


def test_validate_payload_passes_through_model_instance():
    p = GoalPayload(target_role="PM")
    out = validate_payload("goal", p)
    assert out is p  # identity, no copy


def test_validate_payload_rejects_wrong_model_type():
    p = GoalPayload(target_role="PM")
    with pytest.raises(ValueError) as exc:
        validate_payload("preference", p)
    assert "Payload type mismatch" in str(exc.value)
