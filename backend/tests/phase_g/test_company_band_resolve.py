"""TDD tests for resolve_company_band — 实习公司名归一化 + 档次识别。"""
from app.database import SessionLocal
from app.services.phase_g.tier_fit.tier_ladder import resolve_company_band, _norm_company


def test_norm_strips_dept_suffix():
    assert _norm_company("中信证券研究所·消费组").startswith("中信")
    assert "九坤" in _norm_company("九坤投资·中频策略组")


def test_norm_strips_full_legal_suffix():
    # 全称 + (CICC) 括号 → 核心字号
    norm = _norm_company("中国国际金融股份有限公司 (CICC) · 研究部 · TMT 组")
    assert "中国国际金融" in norm or "中金" in norm


def test_norm_strips_space_separated_dept():
    # 空格分隔部门后缀
    norm = _norm_company("易方达基金 · 消费 + 大健康组")
    assert "易方达" in norm


def test_top_institutions_resolve_to_head():
    db = SessionLocal()
    try:
        cases = [
            "中信证券研究所 · 消费组",
            "中国国际金融股份有限公司 (CICC) · 研究部 · TMT 组",
            "九坤投资 · 中频策略组",
            "易方达基金 · 消费 + 大健康组",
            "高瓴资本 · 二级研究部",
            "高盛 (Goldman Sachs) · Global Markets Division (GBM) · 暑期项目",
            "乾象投资 · alpha 因子组",
            "中信建投证券 · 研究发展部 · TMT 组",
        ]
        for c in cases:
            result = resolve_company_band(db, c)
            assert result == "头部", f"{c!r} 应识别为头部，实际={result!r}"
    finally:
        db.close()


def test_mid_tier_institution():
    db = SessionLocal()
    try:
        # 国海富兰克林 → 次头部或腰部（不是顶级，但不应误判成头部）
        result = resolve_company_band(db, "国海富兰克林基金 · 行业研究部")
        assert result in ("次头部", "腰部"), f"国海富兰克林 应为次头部/腰部，实际={result!r}"
    finally:
        db.close()


def test_unknown_company_is_waist():
    db = SessionLocal()
    try:
        assert resolve_company_band(db, "某不知名小公司XYZ") == "腰部"
    finally:
        db.close()
