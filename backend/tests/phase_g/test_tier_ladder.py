import sqlite3
from app.database import SessionLocal
from app.services.phase_g.tier_fit.tier_ladder import band_of, build_tier_ladder

def test_band_of_keyword_rules():
    assert band_of("头部券商研究所(三中一华)") == "头部"
    assert band_of("头部券商研究所") == "头部"
    assert band_of("一线公募") == "头部"
    assert band_of("头部量化私募") == "头部"
    assert band_of("中型券商研究所") == "次头部"
    assert band_of("二线公募") == "次头部"
    assert band_of("中型量化私募") == "次头部"
    assert band_of("产业基金/国资基金") == "腰部"
    assert band_of(None) == "腰部"

def test_build_ladder_for_a_real_subcat_orders_bands():
    db = SessionLocal()
    try:
        c = sqlite3.connect("data/jobradar.db").cursor()
        sc = c.execute(
            "SELECT sub_category FROM jobs WHERE sub_category IS NOT NULL "
            "AND institution_tier IS NOT NULL AND quality_label IN('good','internship_only') "
            "GROUP BY sub_category ORDER BY COUNT(*) DESC LIMIT 1").fetchone()[0]
        ladder = build_tier_ladder(db, sc)
    finally:
        db.close()
    assert ladder
    ranks = [b["rank"] for b in ladder]
    assert ranks == sorted(ranks)
    for b in ladder:
        assert b["band"] in ("头部", "次头部", "腰部")
        assert b["companies"]
        assert b["n_jobs"] >= 1
