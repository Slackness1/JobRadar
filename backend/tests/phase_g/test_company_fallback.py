"""Phase G T18 — company_fallback 测试 (内存 SQLite + 假 ground_truth)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Job, KnowledgeSubcategory
from app.services.phase_g import company_fallback


@pytest.fixture
def db_factory(monkeypatch):
    """In-memory SQLite + 替换 SessionLocal."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    monkeypatch.setattr(company_fallback, "SessionLocal", SessionLocal)
    return SessionLocal


def _gt_payload(sub_cat: str, companies: list[dict]) -> dict:
    return {"ground_truth": {sub_cat: companies}}


def _seed_jobs(s, company: str, n_alive: int, n_intern: int = 0, days_ago: int = 1):
    for i in range(n_alive):
        s.add(Job(
            job_id=f"{company}-good-{i}",
            company=company,
            job_title="研究员",
            quality_label="good",
            scraped_at=datetime.utcnow() - timedelta(days=days_ago),
            link_status="alive",
        ))
    for i in range(n_intern):
        s.add(Job(
            job_id=f"{company}-intern-{i}",
            company=company,
            job_title="实习生",
            quality_label="internship_only",
            scraped_at=datetime.utcnow() - timedelta(days=days_ago),
            link_status="alive",
        ))


def test_fallback_returns_must_have_companies_with_zero_jobs(db_factory, monkeypatch, tmp_path):
    """Ground truth must_have 公司在库内 0 帖 → 进 fallback, 显示 '本季暂未开放'。"""
    gt_file = tmp_path / "gt.json"
    gt_file.write_text(json.dumps(_gt_payload("公募权益研究员", [
        {"name": "高瓴资本", "tier": "头部PE", "must_have": True},
        {"name": "嘉实基金", "tier": "一线公募", "must_have": True},
    ]), ensure_ascii=False))
    monkeypatch.setattr(company_fallback, "GROUND_TRUTH_FILE", gt_file)

    s = db_factory()
    # 嘉实基金 5 个活跃 (超 threshold), 高瓴 0 个
    _seed_jobs(s, "嘉实基金", n_alive=5)
    s.commit()

    out = company_fallback.get_fallback_companies("公募权益研究员")
    assert len(out) == 1
    assert out[0]["name"] == "高瓴资本"
    assert out[0]["status"] == "本季暂未开放新增岗位"
    assert out[0]["active_jobs"] == 0


def test_fallback_status_text_one_two_jobs(db_factory, monkeypatch, tmp_path):
    """1-2 个 alive 岗位的 status 文案对路: 全实习 / 混合。"""
    gt_file = tmp_path / "gt.json"
    gt_file.write_text(json.dumps(_gt_payload("X", [
        {"name": "A", "tier": "tier-A", "must_have": True},
        {"name": "B", "tier": "tier-B", "must_have": True},
    ]), ensure_ascii=False))
    monkeypatch.setattr(company_fallback, "GROUND_TRUTH_FILE", gt_file)

    s = db_factory()
    _seed_jobs(s, "A", n_alive=0, n_intern=2)   # 2 个全实习
    _seed_jobs(s, "B", n_alive=1, n_intern=1)   # 1 good + 1 intern = 2 alive 混合
    s.commit()

    out = company_fallback.get_fallback_companies("X")
    by_name = {o["name"]: o for o in out}
    assert by_name["A"]["status"] == "仅有 2 个实习岗"
    assert by_name["B"]["status"] == "本季仅 2 个开放岗位"


def test_fallback_skips_companies_with_3plus_jobs(db_factory, monkeypatch, tmp_path):
    """≥ threshold 个 alive 的公司不进 fallback (走主推荐链路)。"""
    gt_file = tmp_path / "gt.json"
    gt_file.write_text(json.dumps(_gt_payload("X", [
        {"name": "A", "tier": "x", "must_have": True},
        {"name": "B", "tier": "x", "must_have": True},
    ]), ensure_ascii=False))
    monkeypatch.setattr(company_fallback, "GROUND_TRUTH_FILE", gt_file)

    s = db_factory()
    _seed_jobs(s, "A", n_alive=5)  # 充足
    _seed_jobs(s, "B", n_alive=0)
    s.commit()

    out = company_fallback.get_fallback_companies("X")
    assert {o["name"] for o in out} == {"B"}


def test_fallback_must_have_only_filter(db_factory, monkeypatch, tmp_path):
    """must_have_only=True 时跳过 must_have=False 的。"""
    gt_file = tmp_path / "gt.json"
    gt_file.write_text(json.dumps(_gt_payload("X", [
        {"name": "A", "tier": "x", "must_have": True},
        {"name": "B", "tier": "x", "must_have": False},
    ]), ensure_ascii=False))
    monkeypatch.setattr(company_fallback, "GROUND_TRUTH_FILE", gt_file)

    s = db_factory()
    s.commit()  # 都 0 帖

    out_strict = company_fallback.get_fallback_companies("X", must_have_only=True)
    assert {o["name"] for o in out_strict} == {"A"}
    out_all = company_fallback.get_fallback_companies("X", must_have_only=False)
    assert {o["name"] for o in out_all} == {"A", "B"}


def test_fallback_uses_kb_season_and_verbatim(db_factory, monkeypatch, tmp_path):
    """KB hiring_season 拼成 season 文案; verbatim 提到公司名 → verbatim_hint 填上。"""
    gt_file = tmp_path / "gt.json"
    gt_file.write_text(json.dumps(_gt_payload("公募权益研究员", [
        {"name": "易方达基金", "tier": "一线公募", "must_have": True},
    ]), ensure_ascii=False))
    monkeypatch.setattr(company_fallback, "GROUND_TRUTH_FILE", gt_file)

    s = db_factory()
    s.add(KnowledgeSubcategory(
        sub_cat="公募权益研究员",
        sub_cat_slug="public_equity_researcher",
        strategy_type="基本面权益",
        data_confidence="medium",
        data_basis_json="{}",
        payload_json=json.dumps({
            "hiring_season": {
                "spring": "3-5 月暑期",
                "fall": "9-11 月秋招",
                "peak_month": [3, 4, 9],
            },
            "verbatim_quotes": [
                {"quote": "易方达 25 暑期实习 1.2w/月", "source_url": "https://xhs.example/q1"},
                {"quote": "不相关 quote", "source_url": "https://xhs.example/q2"},
            ],
        }, ensure_ascii=False),
    ))
    s.commit()

    out = company_fallback.get_fallback_companies("公募权益研究员")
    assert len(out) == 1
    o = out[0]
    assert "春招: 3-5 月暑期" in o["season"]
    assert "高峰月: 3, 4, 9" in o["season"]
    assert o["verbatim_hint"]["quote"] == "易方达 25 暑期实习 1.2w/月"
    assert o["verbatim_hint"]["source_url"] == "https://xhs.example/q1"


def test_fallback_no_ground_truth_returns_empty(monkeypatch, tmp_path):
    """该 sub_cat 在 ground_truth 里完全没条目 → 空 list。"""
    gt_file = tmp_path / "gt.json"
    gt_file.write_text(json.dumps({"ground_truth": {}}, ensure_ascii=False))
    monkeypatch.setattr(company_fallback, "GROUND_TRUTH_FILE", gt_file)
    assert company_fallback.get_fallback_companies("不存在的赛道") == []


def test_fallback_respects_max_companies(db_factory, monkeypatch, tmp_path):
    """max_companies 限流。"""
    gt_file = tmp_path / "gt.json"
    gt_file.write_text(json.dumps(_gt_payload("X", [
        {"name": f"co_{i}", "tier": "x", "must_have": True} for i in range(10)
    ]), ensure_ascii=False))
    monkeypatch.setattr(company_fallback, "GROUND_TRUTH_FILE", gt_file)

    s = db_factory()
    s.commit()  # 全 0 帖, 全部进 fallback

    out = company_fallback.get_fallback_companies("X", max_companies=3)
    assert len(out) == 3
