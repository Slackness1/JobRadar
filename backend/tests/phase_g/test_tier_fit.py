from app.services.phase_g.tier_fit.tier_fit import judge_tier_fit, build_prompt

_LADDER = [
    {"band": "头部", "rank": 1, "native_labels": ["头部券商研究所"], "companies": ["中信证券","华泰证券"], "n_jobs": 50},
    {"band": "次头部", "rank": 2, "native_labels": ["中型券商研究所"], "companies": ["东吴证券"], "n_jobs": 20},
    {"band": "腰部", "rank": 3, "native_labels": ["信用评级机构"], "companies": ["中诚信国际"], "n_jobs": 8},
]
_KNOW = {"gate_evidence": "头部投研简历池每年挂海量，无顶级券商实习直接挂",
         "must_have": {"头部": ["985/海硕", "头部券商实习"]},
         "intel_quotes": [{"text": "中信固收实习是硬通货", "evidence_source": "intel_ugc"}]}
_BG = {"school_level": "清北复交", "best_internship": {"company": "东吴证券", "band": "次头部"}}

def _fake_llm(prompt: str) -> dict:
    return {"floor_band": "腰部", "match_band": "次头部", "stretch_band": "头部",
            "reasons": [{"text": "你最高实习在中型券商", "evidence": "头部投研简历池每年挂海量，无顶级券商实习直接挂", "evidence_source": "gate"}],
            "upgrade_hint": "补一段头部券商实习可上探头部"}

def test_judge_returns_three_bands_and_filters_bad_evidence():
    out = judge_tier_fit(_BG, "信用研究员", _LADDER, _KNOW, llm_fn=_fake_llm)
    assert out["match_band"] == "次头部"
    assert out["floor_band"] == "腰部" and out["stretch_band"] == "头部"
    assert out["reasons"] and out["reasons"][0]["evidence_source"] == "gate"
    assert out["data_confidence"] in ("strong", "thin")

def test_judge_filters_illegal_evidence_source_and_band():
    def bad_llm(p):
        return {"floor_band": "火星", "match_band": "次头部", "stretch_band": "头部",
                "reasons": [{"text": "瞎编", "evidence": "x", "evidence_source": "made_up"},
                            {"text": "对的", "evidence": "y", "evidence_source": "gate"}],
                "upgrade_hint": ""}
    out = judge_tier_fit(_BG, "信用研究员", _LADDER, _KNOW, llm_fn=bad_llm)
    assert out["floor_band"] in ("头部","次头部","腰部")  # 火星被替换
    assert all(r["evidence_source"] in ("gate","gt_must_have","intel_ugc") for r in out["reasons"])
    assert len(out["reasons"]) == 1  # made_up 被过滤

def test_judge_falls_back_on_llm_failure():
    def boom(p): raise RuntimeError("x")
    out = judge_tier_fit(_BG, "信用研究员", _LADDER, _KNOW, llm_fn=boom)
    assert out["match_band"] == "次头部"  # 用 best_internship.band 兜底
    assert "reasons" in out

def test_build_prompt_includes_ladder_and_knowledge():
    p = build_prompt(_BG, "信用研究员", _LADDER, _KNOW)
    assert "信用研究员" in p and "头部" in p and "中信证券" in p
    assert "头部投研简历池" in p
