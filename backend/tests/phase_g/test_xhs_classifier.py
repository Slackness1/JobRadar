"""Unit tests for xhs_classifier (all LLM calls mocked)."""
from unittest.mock import MagicMock
import json

from app.services.phase_g.xhs_classifier import (
    classify_post,
    classify_batch,
    _SUB_CATS_27,
    _build_content,
)


def _mock_llm_response(payload: dict):
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = json.dumps(payload)
    return mock_resp


def test_classify_post_returns_structured():
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_llm_response({
        "primary_sub_cat": "量化研究员·中频",
        "primary_confidence": 0.92,
        "secondary_sub_cat": None,
        "secondary_confidence": 0,
        "rationale": "明确提到中频 alpha 因子 + sharpe",
    })
    out = classify_post(client, "讨论中频量化 alpha 因子 sharpe > 0.8")
    assert out.primary_sub_cat == "量化研究员·中频"
    assert out.primary_confidence == 0.92
    assert out.secondary_sub_cat is None


def test_classify_batch_filters_low_confidence():
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        _mock_llm_response({
            "primary_sub_cat": "量化研究员·中频", "primary_confidence": 0.92,
            "secondary_sub_cat": None, "secondary_confidence": 0, "rationale": "x",
        }),
        _mock_llm_response({
            "primary_sub_cat": "公募权益研究员", "primary_confidence": 0.5,  # below threshold
            "secondary_sub_cat": None, "secondary_confidence": 0, "rationale": "y",
        }),
    ]
    # Use kb format (Phase F data shape) so _build_content can extract content
    posts = [
        {"kb": {"insights": [{"type": "role", "text": "量化", "verbatim_quote": "量化alpha", "confidence": "high"}]}, "post_id": "a"},
        {"kb": {"insights": [{"type": "role", "text": "公募", "verbatim_quote": "公募基金", "confidence": "high"}]}, "post_id": "b"},
    ]
    out = classify_batch(client, posts, threshold=0.7)
    assert len(out) == 1
    assert out[0]["post_id"] == "a"


def test_sub_cats_27_count():
    # Constant contains 29 items (plan naming predates final count)
    assert len(_SUB_CATS_27) == 29
    assert len(set(_SUB_CATS_27)) == 29  # all unique


def test_build_content_parses_python_repr_kb():
    post = {"kb": "{'insights': [{'type': 'role', 'text': 'a', 'verbatim_quote': 'b', 'confidence': 'high'}]}"}
    out = _build_content(post)
    assert "b" in out  # verbatim_quote
    # text == 'a' should also be included (different from verbatim_quote)
    assert "a" in out


def test_build_content_handles_malformed_kb():
    assert _build_content({"kb": "not valid python"}) == ""
    assert _build_content({}) == ""
    assert _build_content({"kb": None}) == ""
