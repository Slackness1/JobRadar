"""把池里 ~63 种 institution_tier 字符串归一成 头部/次头部/腰部 三档 + 建赛道阶梯。
band_of 用关键词规则 + 少量 override（这张表是命门，建完人工校）。纯函数，零 LLM。"""
from __future__ import annotations
from sqlalchemy import text
from sqlalchemy.orm import Session

_BAND_RANK = {"头部": 1, "次头部": 2, "腰部": 3}
_HEAD_KW = ("头部", "一线", "三中一华", "外资", "做市商", "顶级")
_MID_KW = ("中型", "二线", "股份行", "腰部券商", "中腰部")
_OVERRIDE = {
    "头部券商资管": "头部", "头部PE": "头部", "头部VC": "头部",
    "银行私行": "次头部", "理财子": "次头部", "券商资管": "次头部",
    "产业基金/国资基金": "腰部", "信用评级机构": "次头部",
}

def band_of(institution_tier: str | None) -> str:
    t = (institution_tier or "").strip()
    if not t:
        return "腰部"
    if t in _OVERRIDE:
        return _OVERRIDE[t]
    if any(k in t for k in _HEAD_KW):
        return "头部"
    if any(k in t for k in _MID_KW):
        return "次头部"
    return "腰部"

def build_tier_ladder(db: Session, sub_cat: str) -> list[dict]:
    rows = db.execute(text(
        "SELECT institution_tier, company, COUNT(*) n FROM jobs "
        "WHERE sub_category = :sc AND quality_label IN ('good','internship_only') "
        "AND institution_tier IS NOT NULL AND institution_tier != '' "
        "GROUP BY institution_tier, company"), {"sc": sub_cat}).fetchall()
    bands: dict[str, dict] = {}
    for tier, company, n in rows:
        band = band_of(tier)
        b = bands.setdefault(band, {"band": band, "rank": _BAND_RANK[band],
                                    "native_labels": set(), "companies": [], "n_jobs": 0})
        b["native_labels"].add(tier)
        if company and company not in b["companies"]:
            b["companies"].append(company)
        b["n_jobs"] += n
    out = sorted(bands.values(), key=lambda b: b["rank"])
    for b in out:
        b["native_labels"] = sorted(b["native_labels"])
        b["companies"] = b["companies"][:8]
    return out
