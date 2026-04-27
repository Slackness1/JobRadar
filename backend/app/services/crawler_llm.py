"""LLM client wrappers for crawler-side enrichment.

Two tiers:
- Flash: cheap (V4-Flash). Used for high-volume tasks: JD extraction, track classification, daily digest.
- Pro: stronger (V4-Pro). Used for low-volume reasoning: failure diagnosis.

Pricing reference (as of 2026-04-27, USD per 1M tokens):
  Flash:  cache-hit input $0.0028 / cache-miss input $0.14 / output $0.28
  Pro:    cache-hit input $0.0145 / cache-miss input $1.74 / output $3.48
          (with 75% off until 2026-05-05: $0.003625 / $0.435 / $0.87)
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from openai import OpenAI

from app.config import (
    CRAWLER_LLM_API_KEY,
    CRAWLER_LLM_BASE_URL,
    CRAWLER_LLM_FLASH_MODEL,
    CRAWLER_LLM_PRO_MODEL,
    CRAWLER_LLM_TIMEOUT_SECONDS,
)


# Pricing constants (USD per 1M tokens)
_FLASH_INPUT_HIT = 0.0028
_FLASH_INPUT_MISS = 0.14
_FLASH_OUTPUT = 0.28

_PRO_INPUT_HIT = 0.0145
_PRO_INPUT_MISS = 1.74
_PRO_OUTPUT = 3.48
_PRO_DISCOUNT_FACTOR = 0.25  # 75% off → 25% of original


def build_flash_client() -> OpenAI:
    return OpenAI(
        base_url=CRAWLER_LLM_BASE_URL,
        api_key=CRAWLER_LLM_API_KEY,
        timeout=CRAWLER_LLM_TIMEOUT_SECONDS,
    )


def build_pro_client() -> OpenAI:
    return OpenAI(
        base_url=CRAWLER_LLM_BASE_URL,
        api_key=CRAWLER_LLM_API_KEY,
        timeout=CRAWLER_LLM_TIMEOUT_SECONDS,
    )


def flash_model_name() -> str:
    return CRAWLER_LLM_FLASH_MODEL


def pro_model_name() -> str:
    return CRAWLER_LLM_PRO_MODEL


def estimate_cost_usd(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_hit: bool = False,
    discount: bool = False,
) -> float:
    """Estimate USD cost. `model` is 'flash' or 'pro'. `discount` applies the 75% off promo for pro."""
    if model == "flash":
        in_rate = _FLASH_INPUT_HIT if cache_hit else _FLASH_INPUT_MISS
        out_rate = _FLASH_OUTPUT
    elif model == "pro":
        in_rate = _PRO_INPUT_HIT if cache_hit else _PRO_INPUT_MISS
        out_rate = _PRO_OUTPUT
        if discount:
            in_rate *= _PRO_DISCOUNT_FACTOR
            out_rate *= _PRO_DISCOUNT_FACTOR
    else:
        raise ValueError(f"Unknown model tier: {model}")
    return (input_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate


_FENCED_JSON = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def safe_json_extract(raw: str) -> Optional[Any]:
    """Extract a JSON object/array from possibly-fenced or noisy LLM output."""
    if not raw:
        return None
    # Try direct parse first
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass
    # Try fenced code block
    m = _FENCED_JSON.search(raw)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try first {…} blob
    start = raw.find("{")
    end = raw.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass
    return None
