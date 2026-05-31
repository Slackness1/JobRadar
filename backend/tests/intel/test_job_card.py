"""TDD 测试：岗位情报卡组装器 build_job_card"""
import sqlite3
from app.database import SessionLocal
from app.services.intel.job_card import build_job_card


def _fake_llm(prompt: str) -> dict:
    return {
        "threshold": {"hard": ["x"], "soft": [], "support_ids": []},
        "compensation": {"summary": "s", "support_ids": []},
        "outlook": {"summary": "o", "support_ids": []},
    }


def _a_finance_job_id() -> int:
    c = sqlite3.connect("data/jobradar.db").cursor()
    r = c.execute(
        "SELECT id FROM jobs WHERE sub_category IS NOT NULL AND company LIKE '%证券%' LIMIT 1"
    ).fetchone()
    assert r, "DB 中找不到证券公司岗位，请检查 data/jobradar.db"
    return r[0]


def _a_cold_job_id() -> int:
    """取一个有 sub_category 但大概率没有 UGC 的冷门岗（使用高偏移量）"""
    c = sqlite3.connect("data/jobradar.db").cursor()
    # total=2564，offset=2500 肯定存在且冷门
    r = c.execute(
        "SELECT id FROM jobs WHERE sub_category IS NOT NULL LIMIT 1 OFFSET 2500"
    ).fetchone()
    assert r, "DB 偏移量超出范围，请调小 OFFSET"
    return r[0]


def test_card_has_positioning_and_three_dims():
    db = SessionLocal()
    try:
        card = build_job_card(db, _a_finance_job_id(), use_cache=False, llm_fn=_fake_llm)
    finally:
        db.close()
    assert card["positioning"]["one_liner"]
    assert set(card["intel"].keys()) == {"threshold", "compensation", "outlook"}
    for dim in card["intel"].values():
        assert "badge" in dim and dim["badge"] in (1, 2, 3)
    assert card["provenance"]["label"]


def test_no_ugc_job_graceful():
    db = SessionLocal()
    try:
        card = build_job_card(db, _a_cold_job_id(), use_cache=False, llm_fn=_fake_llm)
    finally:
        db.close()
    assert card["positioning"]
    assert "intel" in card
