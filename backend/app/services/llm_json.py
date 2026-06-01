"""共享 DeepSeek JSON 适配器：prompt(str) -> dict。
- deepseek_json_fn：Pro + reasoning。用于 tier-fit 等"判断/挂出处"类(质量是命门)。
- flash_json_fn：Flash 无 reasoning。用于情报卡三维抽取等"信息抽取"类(实测快 7-8 倍、成本低 ~40 倍，
  抽取质量足够；2026-06-01 切换)。
两者失败（无余额/超时/非法 JSON）一律返回 {}，由调用方走兜底。可 monkeypatch _client / _flash_client 测试。"""
from __future__ import annotations

import json
import logging

log = logging.getLogger(__name__)


def _client():
    from app.services.crawler_llm import build_pro_client

    # 放宽超时：grounded 判定走 reasoning_effort=medium，Pro 偶尔 >30s（默认会超时回退兜底）。
    # 这些调用结果按公司/赛道缓存、非延迟敏感，给 90s 头寸减少首调超时退化。
    return build_pro_client(timeout=90)


def _flash_client():
    from app.services.crawler_llm import build_flash_client

    return build_flash_client()


def deepseek_json_fn(prompt: str, *, reasoning_effort: str = "medium") -> dict:
    try:
        from app.services.crawler_llm import pro_model_name

        resp = _client().chat.completions.create(
            model=pro_model_name(),
            messages=[{"role": "user", "content": prompt}],
            reasoning_effort=reasoning_effort,
            response_format={"type": "json_object"},
        )
        out = json.loads(resp.choices[0].message.content or "{}")
        return out if isinstance(out, dict) else {}
    except Exception as e:
        log.warning("deepseek_json_fn failed: %s", e)
        return {}


def flash_json_fn(prompt: str) -> dict:
    """Flash 抽取器（无 reasoning）。签名同 deepseek_json_fn，可互换注入 extract_dimensions。"""
    try:
        from app.services.crawler_llm import flash_model_name

        resp = _flash_client().chat.completions.create(
            model=flash_model_name(),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        out = json.loads(resp.choices[0].message.content or "{}")
        return out if isinstance(out, dict) else {}
    except Exception as e:
        log.warning("flash_json_fn failed: %s", e)
        return {}
