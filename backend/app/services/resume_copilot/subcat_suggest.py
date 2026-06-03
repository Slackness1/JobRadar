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
    """复用项目 Flash client 工厂; 预勾是简单分类, 用便宜的 flash 档即可。"""
    from app.services.crawler_llm import build_flash_client
    return build_flash_client()


def _model_name() -> str:
    from app.services.crawler_llm import flash_model_name
    return flash_model_name()


def suggest_sub_cats(resume_summary: str, candidate_sub_cats: list[str], *, client=None) -> list[str]:
    """返回候选子集(≤3), 失败兜底返回全部候选。"""
    cands = [c for c in (candidate_sub_cats or []) if c]
    if not cands:
        return []
    cli = client if client is not None else _build_client()
    try:
        resp = cli.chat.completions.create(
            model=_model_name(),
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


def build_sub_cat_options(resume_summary: str, tracks: list[str]) -> list[dict]:
    """给一组赛道, 返回每个赛道的 sub_cat 候选 + 预勾标记。

    预勾对所有赛道的 sub_cat 并集跑一次 LLM, 然后按赛道回填 suggested 标记。
    返回: [{"track": str, "sub_cats": [{"key": str, "suggested": bool}, ...]}]
    """
    from app.services.phase_g.track_subcat_map import CANONICAL_TRACK_TO_SUBCATS

    track_to_cands: dict[str, list[str]] = {}
    union: list[str] = []
    seen: set[str] = set()
    for t in tracks or []:
        cands = CANONICAL_TRACK_TO_SUBCATS.get((t or "").strip(), [])
        track_to_cands[t] = cands
        for c in cands:
            if c not in seen:
                seen.add(c); union.append(c)
    suggested = set(suggest_sub_cats(resume_summary, union)) if union else set()
    out: list[dict] = []
    for t in tracks or []:
        out.append({
            "track": t,
            "sub_cats": [{"key": c, "suggested": c in suggested} for c in track_to_cands.get(t, [])],
        })
    return out
