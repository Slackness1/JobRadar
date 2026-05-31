"""共享 DeepSeek JSON 适配器：prompt(str) -> dict。情报卡维度抽取 + tier-fit 判定共用。
失败（无余额/超时/非法 JSON）一律返回 {}，由调用方走兜底。可 monkeypatch _client 测试。"""
from __future__ import annotations

import json
import logging

log = logging.getLogger(__name__)


def _client():
    from app.services.crawler_llm import build_pro_client

    # 放宽超时：grounded 判定走 reasoning_effort=medium，Pro 偶尔 >30s（默认会超时回退兜底）。
    # 这些调用结果按公司/赛道缓存、非延迟敏感，给 90s 头寸减少首调超时退化。
    return build_pro_client(timeout=90)


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
