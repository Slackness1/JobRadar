"""Verify Resume Copilot recommendation score fields are semantically distinct.

C3 cleanup: rule_score has been removed; only base_match_score, enhanced_score,
and final_score remain. Test asserts they CAN diverge.
"""

from app.schemas_resume_copilot import ResumeRecommendationItem


def test_recommendation_item_no_longer_has_rule_score():
    fields = ResumeRecommendationItem.model_fields
    assert 'rule_score' not in fields, (
        'rule_score was redundant with base_match_score (C3 cleanup). '
        'Remove all references and the field itself.'
    )
    assert 'base_match_score' in fields
    assert 'enhanced_score' in fields
    assert 'final_score' in fields


def test_recommendation_item_can_have_distinct_score_tiers():
    item = ResumeRecommendationItem(
        job_id='J1',
        company='Acme',
        job_title='SDE',
        location='Beijing',
        detail_url='',
        objective_score=20,
        preference_score=15,
        base_job_score=10,
        company_priority_score=5,
        base_match_score=50,
        enhanced_score=58,
        final_score=62,
    )
    assert item.base_match_score < item.enhanced_score < item.final_score
