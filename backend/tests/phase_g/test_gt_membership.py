from app.services.phase_g.tier_fit.platform_skeleton import gt_companies_for_sub_cat


def test_returns_gt_companies_for_known_subcat():
    names = gt_companies_for_sub_cat("公募权益研究员")
    # _norm_company is identity for these names (no suffix stripped)
    assert "鹏华基金" in names
    assert "中欧基金" in names


def test_unknown_subcat_returns_empty():
    assert gt_companies_for_sub_cat("不存在的赛道xyz") == set()
