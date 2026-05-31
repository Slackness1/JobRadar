from app.services.intel.dimension_extract import extract_dimensions, build_prompt


def _fake_llm(prompt: str) -> dict:
    return {
        "threshold": {"hard": ["985/海硕"], "soft": ["看重信用框架"], "support_ids": ["zh_a_i0"]},
        "compensation": {"summary": "25-30k×16薪", "support_ids": ["xhs_b_i0"]},
        "outlook": {"summary": "多数推荐", "support_ids": ["xhs_b_i0"]},
    }


def test_extract_returns_three_dims_with_support_ids():
    insights = [
        {"insight_id": "zh_a_i0", "content": "门槛高 985", "source_quote": "...", "confidence": "high"},
        {"insight_id": "xhs_b_i0", "content": "base 28", "source_quote": "...", "confidence": "med"},
    ]
    out = extract_dimensions(insights, llm_fn=_fake_llm)
    assert set(out.keys()) == {"threshold", "compensation", "outlook"}
    assert out["threshold"]["support_ids"] == ["zh_a_i0"]


def test_build_prompt_includes_insight_ids():
    insights = [{"insight_id": "zh_a_i0", "content": "x", "source_quote": "q", "confidence": "high"}]
    p = build_prompt("华泰证券", insights)
    assert "zh_a_i0" in p and "门槛" in p


def test_company_flows_into_prompt_via_extract(monkeypatch):
    captured = {}

    def spy_llm(prompt):
        captured["p"] = prompt
        return {
            "threshold": {"hard": [], "soft": [], "support_ids": []},
            "compensation": {"summary": None, "support_ids": []},
            "outlook": {"summary": None, "support_ids": []},
        }

    extract_dimensions(
        [{"insight_id": "zh_a_i0", "content": "x", "confidence": "high"}],
        llm_fn=spy_llm,
        company="华泰证券",
    )
    assert "华泰证券" in captured["p"]
