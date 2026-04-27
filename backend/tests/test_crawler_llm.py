import pytest
from unittest.mock import patch, MagicMock

from app.services.crawler_llm import (
    build_flash_client,
    build_pro_client,
    estimate_cost_usd,
    safe_json_extract,
)


def test_build_flash_client_returns_openai_client():
    client = build_flash_client()
    assert client is not None
    # Just verify it has chat.completions structure
    assert hasattr(client, "chat")


def test_build_pro_client_returns_openai_client():
    client = build_pro_client()
    assert client is not None
    assert hasattr(client, "chat")


def test_estimate_cost_usd_flash_pricing():
    # 1M input cache miss + 1M output ≈ $0.14 + $0.28 = $0.42
    cost = estimate_cost_usd(model="flash", input_tokens=1_000_000, output_tokens=1_000_000, cache_hit=False)
    assert 0.40 <= cost <= 0.45  # tolerate small rounding


def test_estimate_cost_usd_flash_cache_hit():
    # 1M input cache hit + 1M output ≈ $0.0028 + $0.28 = $0.283
    cost = estimate_cost_usd(model="flash", input_tokens=1_000_000, output_tokens=1_000_000, cache_hit=True)
    assert 0.28 <= cost <= 0.29


def test_estimate_cost_usd_pro_with_75pct_discount():
    # 1M input + 1M output at discounted price = $0.435 + $0.87 = $1.305
    cost = estimate_cost_usd(model="pro", input_tokens=1_000_000, output_tokens=1_000_000, cache_hit=False, discount=True)
    assert 1.28 <= cost <= 1.35


def test_safe_json_extract_handles_clean_json():
    out = safe_json_extract('{"track": "AI产品", "quality": "good"}')
    assert out == {"track": "AI产品", "quality": "good"}


def test_safe_json_extract_handles_fenced_markdown():
    raw = '```json\n{"track": "AI产品"}\n```'
    out = safe_json_extract(raw)
    assert out == {"track": "AI产品"}


def test_safe_json_extract_returns_none_on_garbage():
    assert safe_json_extract("not json at all") is None
