from app.services.intel.positioning import build_positioning


def test_full_positioning():
    job = {"company": "华泰证券", "job_title": "固定收益部 信用研究岗",
           "department": "固定收益部", "sub_category": "信用研究员",
           "institution_tier": "头部券商研究所"}
    p = build_positioning(job)
    assert p["sub_category"] == "信用研究员"
    assert p["tier"] == "头部券商研究所"
    assert "固收" in p["track_line"] or "固定收益" in p["track_line"]
    assert p["one_liner"]  # 非空一句话


def test_missing_subcat_graceful():
    job = {"company": "X", "job_title": "Y", "department": "", "sub_category": None, "institution_tier": None}
    p = build_positioning(job)
    assert p["sub_category"] is None
    assert p["one_liner"]  # 仍给兜底文案
