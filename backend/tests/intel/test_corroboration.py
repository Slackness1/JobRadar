from app.services.intel.corroboration import independent_cross

def test_two_sources_two_authors_is_verified():
    sibs = [{"note_id": "zh_a", "author": "王"}, {"note_id": "xhs_b", "author": "李"}]
    assert independent_cross(sibs) == "verified"

def test_same_author_across_sources_not_verified():
    sibs = [{"note_id": "zh_a", "author": "王"}, {"note_id": "xhs_b", "author": "王"}]
    assert independent_cross(sibs) == "single"

def test_two_authors_same_source_not_verified():
    sibs = [{"note_id": "xhs_a", "author": "王"}, {"note_id": "xhs_b", "author": "李"}]
    assert independent_cross(sibs) == "single"  # 同平台不算跨源

def test_missing_author_counts_as_distinct_only_if_distinct_note():
    sibs = [{"note_id": "zh_a", "author": ""}, {"note_id": "xhs_b", "author": ""}]
    assert independent_cross(sibs) == "single"  # 都缺作者 → 无法确认非同人 → 不升 verified
