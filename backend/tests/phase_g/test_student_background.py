from app.services.phase_g.tier_fit.student_background import school_tier_of, extract_student_bg

def test_school_tier_buckets():
    assert school_tier_of("上海交通大学") == "清北复交"
    assert school_tier_of("清华大学") == "清北复交"
    assert school_tier_of("浙江大学") == "985"
    assert school_tier_of("苏州大学") == "211"
    assert school_tier_of("某二本学院") == "双非"
    assert school_tier_of("") == "未知"

def test_extract_bg_picks_best_internship_band():
    profile = {
        "education": [{"school": "上海交通大学", "degree": "硕士"}],
        "experiences": [
            {"company": "某城商行", "title": "柜员实习"},
            {"company": "中信证券", "title": "固收研究实习"},
        ],
    }
    bg = extract_student_bg(profile, {}, band_lookup=lambda c: {"中信证券": "头部"}.get(c, "腰部"))
    assert bg["school_level"] == "清北复交"
    assert bg["best_internship"]["company"] == "中信证券"
    assert bg["best_internship"]["band"] == "头部"

def test_extract_bg_graceful_when_empty():
    bg = extract_student_bg({"education": [], "experiences": []}, {}, band_lookup=lambda c: "腰部")
    assert bg["school_level"] == "未知"
    assert bg["best_internship"] is None
