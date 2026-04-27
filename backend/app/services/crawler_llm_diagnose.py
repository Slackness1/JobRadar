"""LLM-powered failure diagnosis for crawler_llm Pro tier.

When a company_crawl_logs row is marked failed, this module assembles
the error + recent successful runs + relevant source code into a prompt
and asks DeepSeek V4-Pro for a probable cause + suggested code change.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.services.crawler_llm import build_pro_client, pro_model_name

logger = logging.getLogger(__name__)

_MAX_CODE_CHARS = 8000
_MAX_ERROR_CHARS = 1200
_MAX_PROMPT_CHARS = 20000

_SYSTEM_PROMPT = """你是爬虫脚本调试助手。给定一次失败的爬取记录、近期成功爬取的对照数据、以及该公司爬虫函数的源码，给出最可能的失败原因和具体修改建议。

要求：
1. 用 markdown 格式，只包含两段：**可能原因** 和 **建议改动**。
2. 可能原因结合错误信息和"近期成功 vs 现在失败"的差异（比如以前能抓到 50 条现在 0 条 → 强烈暗示 selector / API 变了）。
3. 建议改动要落到具体行/常量/正则上，不要泛泛说"改一下 selector"。
4. 总长度控制在 300 字以内。
5. 不要复制源代码，不要套话，直奔结论。"""


def _build_user_prompt(
    company: str,
    source: str,
    error_message: str,
    recent_successes: list[dict],
    crawler_code: str,
) -> str:
    err = (error_message or "")[:_MAX_ERROR_CHARS]
    code = (crawler_code or "")[:_MAX_CODE_CHARS]
    history_lines = []
    for s in recent_successes[:5]:
        history_lines.append(
            f"- {s.get('started_at', '')}: fetched={s.get('fetched_count', 0)}, new={s.get('new_count', 0)}, duration={s.get('duration_ms', 0)}ms"
        )
    history = "\n".join(history_lines) if history_lines else "（无成功 run 历史）"

    prompt = f"""公司: {company}
来源: {source}

# 本次错误
{err}

# 近期成功 run（最多 5 次，越早越前）
{history}

# 爬虫函数源码片段（已截断）
```python
{code}
```

请输出 markdown 格式的诊断（可能原因 + 建议改动）。"""
    return prompt[:_MAX_PROMPT_CHARS]


def diagnose_failure(
    *,
    company: str,
    source: str,
    error_message: str,
    recent_successes: list[dict],
    crawler_code: str,
) -> Optional[str]:
    """One Pro call. Returns markdown string on success, None on any failure."""
    try:
        client = build_pro_client()
        resp = client.chat.completions.create(
            model=pro_model_name(),
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(
                    company, source, error_message, recent_successes, crawler_code
                )},
            ],
            temperature=0.2,
            max_tokens=400,
        )
    except Exception as exc:
        logger.debug("crawler_llm_diagnose.diagnose_failure failed: %s", exc)
        return None

    try:
        out = resp.choices[0].message.content or ""
    except (IndexError, AttributeError):
        return None

    out = out.strip()
    return out if out else None
