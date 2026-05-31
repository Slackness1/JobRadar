"""TDD: GET /api/resume-copilot/sessions/{id}/tier-fit 端点 + build_tier_fit 组装器。

LLM 调用通过 monkeypatch 替换成 fake，测试只验证组装路径 + API 形状，不花钱不依赖外部。
"""
import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.main import app

# ---------------------------------------------------------------------------
# Fake LLM — 返回符合 judge_tier_fit 输出契约的固定结果
# ---------------------------------------------------------------------------

def _fake_llm_fn(prompt: str) -> dict:
    return {
        "floor_band": "腰部",
        "match_band": "次头部",
        "stretch_band": "头部",
        "reasons": [
            {
                "text": "最高实习在次头部机构",
                "evidence": "头部要求顶级券商实习",
                "evidence_source": "gate",
            }
        ],
        "upgrade_hint": "补头部券商实习可冲头部",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _top_sub_cat_with_tier() -> str | None:
    """从 dev DB 取最热的有 institution_tier 的 sub_category，供测试参数化。"""
    try:
        c = sqlite3.connect("data/jobradar.db").cursor()
        row = c.execute(
            "SELECT sub_category FROM jobs "
            "WHERE sub_category IS NOT NULL AND institution_tier IS NOT NULL "
            "AND quality_label IN ('good','internship_only') "
            "GROUP BY sub_category ORDER BY COUNT(*) DESC LIMIT 1"
        ).fetchone()
        c.connection.close()
        return row[0] if row else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_tier_fit_endpoint_shape(monkeypatch):
    """端点返回正确 shape，ladder 有三档，fit 里 match_band 合法。"""
    # Monkeypatch deepseek_json_fn 让 build_tier_fit 不调真实 LLM
    import app.routers.resume_copilot as rc_router
    import app.services.phase_g.tier_fit.tier_fit as tier_fit_mod

    monkeypatch.setattr(tier_fit_mod, "deepseek_json_fn", _fake_llm_fn, raising=False)

    sub_cat = _top_sub_cat_with_tier()
    if not sub_cat:
        pytest.skip("dev DB 无 institution_tier 数据，跳过")

    client = TestClient(app)
    r = client.get(
        f"/api/resume-copilot/sessions/1/tier-fit",
        params={"sub_cat": sub_cat, "refresh": 1},  # refresh=1 跳过缓存
    )
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
    b = r.json()
    assert b["sub_cat"] == sub_cat, f"sub_cat mismatch: {b}"
    assert b["ladder"] is not None  # 可以为空列表（赛道无 tier 数据时）
    assert isinstance(b["ladder"], list)
    assert "fit" in b
    # fit 可能是 None (ladder 空时) 或 dict
    if b["ladder"] and b["fit"]:
        band_names = {x["band"] for x in b["ladder"]}
        assert b["fit"]["match_band"] in band_names, \
            f"match_band {b['fit']['match_band']!r} 不在 ladder 档 {band_names}"


def test_tier_fit_endpoint_no_sub_cat_returns_graceful(monkeypatch):
    """session 无 profile 时，不传 sub_cat 应返回 fit=None 而非 500。"""
    import app.services.phase_g.tier_fit.tier_fit as tier_fit_mod
    monkeypatch.setattr(tier_fit_mod, "deepseek_json_fn", _fake_llm_fn, raising=False)

    client = TestClient(app)
    # session 1 是 demo session，profile 可能有也可能无 preferred sub_cat
    r = client.get("/api/resume-copilot/sessions/1/tier-fit", params={"refresh": 1})
    assert r.status_code == 200
    b = r.json()
    assert "session_id" in b


def test_tier_fit_with_fake_llm_injected(monkeypatch):
    """通过 build_tier_fit 直接注入 fake llm_fn，验证组装逻辑不依赖真实 LLM。"""
    from app.database import SessionLocal
    from app.services.phase_g.tier_fit.tier_fit import build_tier_fit

    sub_cat = _top_sub_cat_with_tier()
    if not sub_cat:
        pytest.skip("dev DB 无 institution_tier 数据，跳过")

    db = SessionLocal()
    try:
        result = build_tier_fit(
            db, 1, sub_cat,
            llm_fn=_fake_llm_fn,
            use_cache=False,  # 不走缓存，每次新跑
        )
    finally:
        db.close()

    assert result["sub_cat"] == sub_cat
    assert isinstance(result["ladder"], list)
    assert result["fit"] is not None or result["ladder"] == []
    if result["fit"]:
        assert result["fit"]["match_band"] in ("头部", "次头部", "腰部")
