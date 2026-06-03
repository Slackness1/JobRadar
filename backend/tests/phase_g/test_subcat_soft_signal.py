from types import SimpleNamespace
from app.services.phase_g.recommendation_v2.scoring import (
    StudentProfile, sub_cat_match_score,
)


def _job(primary, secondary=None):
    return SimpleNamespace(sub_category=primary, sub_category_secondary=secondary)


PREFERRED = ["公募权益研究员", "固收+多资产", "资管FOF"]


def test_no_confirmed_falls_back_to_preferred_behaviour():
    p = StudentProfile(preferred_sub_cats=PREFERRED)
    assert sub_cat_match_score(p, _job("公募权益研究员")) == 1.0
    assert sub_cat_match_score(p, _job("固收+多资产")) == 1.0
    assert sub_cat_match_score(p, _job("量化研究员")) == 0.0


def test_confirmed_hit_scores_full():
    p = StudentProfile(preferred_sub_cats=PREFERRED, confirmed_sub_cats=["公募权益研究员"])
    assert sub_cat_match_score(p, _job("公募权益研究员")) == 1.0


def test_in_track_but_unconfirmed_is_demoted_not_zero():
    p = StudentProfile(preferred_sub_cats=PREFERRED, confirmed_sub_cats=["公募权益研究员"])
    assert sub_cat_match_score(p, _job("固收+多资产")) == 0.5


def test_secondary_confirmed_match():
    p = StudentProfile(preferred_sub_cats=PREFERRED, confirmed_sub_cats=["资管FOF"])
    assert sub_cat_match_score(p, _job("公募权益研究员", secondary="资管FOF")) == 0.6


def test_out_of_track_still_zero():
    p = StudentProfile(preferred_sub_cats=PREFERRED, confirmed_sub_cats=["公募权益研究员"])
    assert sub_cat_match_score(p, _job("券商IT运维")) == 0.0
