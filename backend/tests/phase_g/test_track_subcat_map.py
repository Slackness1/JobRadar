"""测 13 赛道→sub_cat 映射表 + _v2_extract_preferred_sub_cats 的选择优先逻辑。"""
from app.schemas_resume_copilot import ResumeProfilePayload, ResumePreferencePayload
from app.services.phase_g.knowledge_synthesis import SUBCAT_TO_STRATEGY
from app.services.phase_g.track_subcat_map import (
    CANONICAL_TRACK_TO_SUBCATS,
    subcats_for_tracks,
)
from app.services.taxonomy.canonical import CANONICAL_FINANCE_TRACKS
from app.services.resume_copilot.recommendation import _v2_extract_preferred_sub_cats


def test_table_keys_align_with_canonical_tracks():
    assert set(CANONICAL_TRACK_TO_SUBCATS) == set(CANONICAL_FINANCE_TRACKS)


def test_table_subcats_all_valid():
    valid = set(SUBCAT_TO_STRATEGY)
    for track, scs in CANONICAL_TRACK_TO_SUBCATS.items():
        for sc in scs:
            assert sc in valid, f"{track} 映射到未知 sub_cat {sc}"


def test_subcats_for_tracks_dedup_and_order():
    out = subcats_for_tracks(["量化"])
    assert "量化研究员·中频" in out and "买方 Quant" in out
    # 两个赛道有重叠 sub_cat 时去重
    out2 = subcats_for_tracks(["公募/资管·投研", "私募·基本面"])
    assert len(out2) == len(set(out2))


def test_uncovered_track_returns_empty():
    # 监管/咨询/大宗 是覆盖缺口
    assert subcats_for_tracks(["监管·体制内"]) == []


def test_explicit_choice_overrides_resume():
    """学生简历是卖方研究, 但显式选了量化 → 必须按量化推 (选择优先)。"""
    profile = ResumeProfilePayload(inferred_tracks=["头部券商研究所 TMT", "卖方研究"])
    prefs = ResumePreferencePayload(preferred_tracks=["量化"])
    out = _v2_extract_preferred_sub_cats(profile, prefs)
    assert "量化研究员·中频" in out
    # 不应混入卖方 sub_cat
    assert "卖方研究员·TMT" not in out


def test_no_choice_falls_back_to_resume():
    """没显式选 → 用简历 inferred_tracks 映射。"""
    profile = ResumeProfilePayload(inferred_tracks=["卖方研究"])
    prefs = ResumePreferencePayload(preferred_tracks=[])
    out = _v2_extract_preferred_sub_cats(profile, prefs)
    assert "卖方研究员·TMT" in out


def test_uncovered_explicit_choice_does_not_revert_to_resume():
    """选了覆盖缺口赛道 → 返空 (走通用召回), 不退回简历。"""
    profile = ResumeProfilePayload(inferred_tracks=["卖方研究"])
    prefs = ResumePreferencePayload(preferred_tracks=["监管·体制内"])
    assert _v2_extract_preferred_sub_cats(profile, prefs) == []
