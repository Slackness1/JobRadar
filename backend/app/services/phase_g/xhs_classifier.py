"""Multi-label classifier: XHS post -> 27 sub_cat (Phase G 3a step 1)."""
from __future__ import annotations
import ast
import json
import os
from dataclasses import dataclass
from typing import Iterable

import app.config  # noqa: F401  # triggers .env.local load into os.environ
from openai import OpenAI


_SUB_CATS_27 = [
    # 基本面权益
    "公募权益研究员", "行业研究员·消费", "行业研究员·TMT-医药-周期",
    "公募指数研究员", "公募基金中后台",
    # 量化
    "量化研究员·中频", "量化研究员·高频", "量化开发QD",
    "AI 量化工程师", "量化因子工程师",
    # 固定收益
    "信用研究员", "固收交易员", "固收+多资产", "利率宏观策略",
    # 卖方研究
    "卖方研究员·TMT", "卖方研究员·消费医药周期", "卖方研究员·宏观策略",
    "买方 Quant", "投行 IBD",
    # 多资产_FOF_衍生品
    "资管FOF", "自营FOF", "财富管理FOF", "结构化产品衍生品",
    # 相关补充
    "PE投后VC行研",
    # AI 应用_PM_开发
    "LLM算法post-train", "Agent工程师", "多模态推理优化", "AI PM", "AI算法业务",
]


@dataclass
class XhsClassification:
    primary_sub_cat: str | None
    primary_confidence: float
    secondary_sub_cat: str | None
    secondary_confidence: float
    rationale: str


_SYSTEM_PROMPT = """你是中国金融 + AI 校招赛道分类专家. 给一篇小红书帖, 判定属于以下 27 个细分赛道中的哪 1-2 个 (multi-label).

27 个 sub_cat:
{subcats}

输出 JSON, 严格 schema:
{{
  "primary_sub_cat": "<27 个之一 或 null>",
  "primary_confidence": <0-1 浮点>,
  "secondary_sub_cat": "<27 个之一 或 null (只标 1 个不要凑数)>",
  "secondary_confidence": <0-1>,
  "rationale": "<≤80 字, 说明你为什么这么标>"
}}

规则:
- 帖子明显不属于上述任何赛道, primary_sub_cat 输出 null, confidence 0
- 帖子只对应 1 个赛道, secondary_sub_cat 输出 null
- 不要凑两个 sub_cat
- confidence 是你对自己判断的把握, 不是帖子内容质量
"""


def _build_system_prompt() -> str:
    return _SYSTEM_PROMPT.format(subcats="\n".join(f"- {s}" for s in _SUB_CATS_27))


def _build_content(post: dict) -> str:
    """Extract post content from kb.insights field (Phase F data format).

    The kb field is stored as a Python-repr string OR as a parsed dict.
    Falls back gracefully on malformed or missing data.
    """
    kb_raw = post.get("kb")
    if kb_raw is None:
        return ""
    # Handle both already-parsed dict (json.loads already did it) and string repr
    if isinstance(kb_raw, dict):
        kb = kb_raw
    elif isinstance(kb_raw, str):
        try:
            kb = ast.literal_eval(kb_raw)
        except (SyntaxError, ValueError):
            return ""
    else:
        return ""
    if not isinstance(kb, dict):
        return ""
    insights = kb.get("insights", [])
    if not isinstance(insights, list):
        return ""
    parts = []
    for ins in insights:
        if isinstance(ins, dict):
            q = ins.get("verbatim_quote") or ""
            t = ins.get("text") or ""
            if q:
                parts.append(q)
            if t and t != q:
                parts.append(t)
    return "\n\n".join(parts).strip()


# Canonical-name aliases — LLM occasionally emits whitespace/punctuation variants
# despite the prompt's canonical list. Map them back so downstream filters match.
_SUB_CAT_ALIASES = {
    "买方Quant": "买方 Quant",
    "AI量化工程师": "AI 量化工程师",
    "AIPM": "AI PM",
}


def _snap_to_canonical(name: str | None) -> str | None:
    if name is None:
        return None
    if name in _SUB_CATS_27:
        return name
    if name in _SUB_CAT_ALIASES:
        return _SUB_CAT_ALIASES[name]
    return None  # unknown name — treat as no-match


def classify_post(client: OpenAI, post_content: str, model: str = "deepseek-v4-pro") -> XhsClassification:
    """Single-post classification via DeepSeek Pro (reasoning_effort=medium).

    Returns an empty XhsClassification on LLM/parse failure so the batch loop
    can keep going instead of crashing on a single bad response.
    """
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _build_system_prompt()},
                {"role": "user", "content": f"帖子内容:\n\n{post_content[:3000]}"},
            ],
            extra_body={"reasoning_effort": "medium"},
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        content = resp.choices[0].message.content or ""
        raw = json.loads(content) if content.strip() else {}
    except (json.JSONDecodeError, Exception):
        raw = {}
    return XhsClassification(
        primary_sub_cat=_snap_to_canonical(raw.get("primary_sub_cat")),
        primary_confidence=float(raw.get("primary_confidence") or 0),
        secondary_sub_cat=_snap_to_canonical(raw.get("secondary_sub_cat")),
        secondary_confidence=float(raw.get("secondary_confidence") or 0),
        rationale=raw.get("rationale", ""),
    )


def classify_batch(
    client: OpenAI,
    posts: Iterable[dict],
    threshold: float = 0.7,
    model: str = "deepseek-v4-pro",
) -> list[dict]:
    """Classify a batch of posts. Returns posts with `classification` field added.

    Uses _build_content() to extract text from kb.insights (Phase F data format).
    Filters: only includes classifications with primary_confidence >= threshold.
    """
    out = []
    for post in posts:
        content = _build_content(post)
        if not content.strip():
            continue
        c = classify_post(client, content, model=model)
        if c.primary_confidence < threshold or c.primary_sub_cat is None:
            continue
        post_copy = dict(post)
        post_copy["classification"] = {
            "primary_sub_cat": c.primary_sub_cat,
            "primary_confidence": c.primary_confidence,
            "secondary_sub_cat": c.secondary_sub_cat if c.secondary_confidence >= threshold else None,
            "secondary_confidence": c.secondary_confidence,
            "rationale": c.rationale,
        }
        out.append(post_copy)
    return out


def _get_client() -> OpenAI:
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("RESUME_COPILOT_LLM_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set")
    base_url = os.environ.get("RESUME_COPILOT_LLM_BASE_URL", "https://api.deepseek.com/v1")
    return OpenAI(api_key=api_key, base_url=base_url)
