"""确认页 LLM 预勾:给简历 + 赛道展开的 sub_cat 候选, 挑最像的 1-3 个默认勾选。

设计决策(2026-06-03):宁缺勿滥, 最多 3 个; 失败兜底返回全部候选(= 软信号关闭 = 现状)。
召回不依赖此结果, 所以失败只是少了智能预勾, 不阻塞确认页。
"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

_MAX_SUGGEST = 3

_PROMPT = """你是金融招聘顾问。下面是一个学生的简历摘要, 以及他选的求职赛道展开出的细分方向候选。
请只挑出**最直接对应**这份简历的细分方向, 最多 3 个。宁缺勿滥 —— 简历明确是权益就只挑权益,
不要把固收/FOF/量化等不相关方向也勾上。

简历摘要:
{resume}

候选细分方向(只能从这里选, 原样返回字符串):
{cands}

只输出 JSON: {{"suggested": ["方向1", "方向2"]}}"""


def _build_client():
    """复用项目里 Pro/Flash client 工厂; 预勾用便宜模型即可。"""
    from app.services.crawler_llm import build_pro_client
    return build_pro_client(max_retries=1, timeout=30)


def suggest_sub_cats(resume_summary: str, candidate_sub_cats: list[str], *, client=None) -> list[str]:
    """返回候选子集(≤3), 失败兜底返回全部候选。"""
    cands = [c for c in (candidate_sub_cats or []) if c]
    if not cands:
        return []
    cli = client if client is not None else _build_client()
    try:
        resp = cli.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": _PROMPT.format(
                resume=(resume_summary or "")[:1500],
                cands="\n".join(f"- {c}" for c in cands),
            )}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        raw = json.loads(content).get("suggested", [])
        cand_set = set(cands)
        picked = [s for s in raw if s in cand_set][:_MAX_SUGGEST]
        return picked or cands
    except Exception:
        logger.warning("suggest_sub_cats failed, fallback to all candidates", exc_info=True)
        return cands
