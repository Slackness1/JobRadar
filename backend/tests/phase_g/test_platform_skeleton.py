"""TDD tests for platform_skeleton.build_platform_skeleton."""
import sqlite3

import pytest
from app.database import SessionLocal
from app.services.phase_g.tier_fit.platform_skeleton import build_platform_skeleton


def test_skeleton_groups_gt_companies_by_band():
    db = SessionLocal()
    try:
        # 信用研究员 GT 有公司, 应有 skeleton
        sk = build_platform_skeleton(db, "信用研究员", match_band="次头部")
        assert sk["has_skeleton"] is True
        assert sk["tiers"]
        for t in sk["tiers"]:
            assert t["band"] in ("头部", "次头部", "腰部")
            assert t["companies"]
            for c in t["companies"]:
                assert "name" in c and "has_live" in c and "n_insights" in c
        # match_band 那档 role=match
        match_tiers = [t for t in sk["tiers"] if t["role"] == "match"]
        assert any(t["band"] == "次头部" for t in match_tiers)
    finally:
        db.close()


def test_no_gt_subcat_degrades():
    db = SessionLocal()
    try:
        sk = build_platform_skeleton(db, "机构销售·销售支持")  # GT 无此键
        assert sk["has_skeleton"] is False
        assert sk["tiers"] == []
    finally:
        db.close()


def test_skeleton_has_correct_structure():
    """验证返回结构字段完整性。"""
    db = SessionLocal()
    try:
        sk = build_platform_skeleton(db, "公募权益研究员", match_band="头部")
        assert "sub_cat" in sk
        assert "has_skeleton" in sk
        assert "tiers" in sk
        if sk["has_skeleton"]:
            for t in sk["tiers"]:
                assert "tier" in t
                assert "band" in t
                assert "role" in t
                assert "label" in t
                assert "companies" in t
                for c in t["companies"]:
                    assert "name" in c
                    assert "has_live" in c
                    assert "n_live" in c
                    assert "n_insights" in c
                    assert "jobs" in c
    finally:
        db.close()


def test_match_band_param_overrides_default_role():
    """传了 match_band='头部' 时，头部档的 role 应该是 match。"""
    db = SessionLocal()
    try:
        sk = build_platform_skeleton(db, "投行 IBD", match_band="头部")
        if sk["has_skeleton"] and sk["tiers"]:
            head_tiers = [t for t in sk["tiers"] if t["band"] == "头部"]
            if head_tiers:
                assert head_tiers[0]["role"] == "match"
    finally:
        db.close()


def test_companies_sorted_live_first():
    """有在招对口岗的公司应排在同梯队无在招岗公司前面。"""
    db = SessionLocal()
    try:
        sk = build_platform_skeleton(db, "公募权益研究员")
        if not sk["has_skeleton"]:
            return
        for t in sk["tiers"]:
            companies = t["companies"]
            if len(companies) < 2:
                continue
            # 找第一个 has_live=False 的位置
            first_no_live = next(
                (i for i, c in enumerate(companies) if not c["has_live"]), None
            )
            if first_no_live is None:
                continue
            # 该位置之后不应再出现 has_live=True
            for c in companies[first_no_live:]:
                assert not c["has_live"], (
                    f"has_live=True 公司 {c['name']} 出现在无在招岗公司之后"
                )
    finally:
        db.close()
