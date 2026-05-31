"""LLM 把一个公司的 insights 归到 3 维 + 抽要点，每点回挂 insight_id。
llm_fn(prompt:str)->dict 可注入（测试传 fake；生产传 DeepSeek/强模型适配器）。"""
from __future__ import annotations
import copy
from typing import Callable

SYSTEM = """你是金融求职情报整理器。给你一个公司的若干条学生 UGC 洞察（每条带 insight_id）。
把它们整理成学生最关心的 3 个维度，每个维度的每个要点必须回挂支撑它的 insight_id（只能用给定的 id）：
- threshold（门槛）：hard[]（学历/实习/证书）、soft[]（面试官偏好/对口经历）、support_ids[]
- compensation（薪酬）：summary（一句话，含区间/奖金口径）、support_ids[]
- outlook（前景体验）：summary（推荐度/文化/压力/晋升）、support_ids[]
只依据给定洞察，不编造。输出严格 JSON：{"threshold":{...},"compensation":{...},"outlook":{...}}"""

_EMPTY = {
    "threshold": {"hard": [], "soft": [], "support_ids": []},
    "compensation": {"summary": None, "support_ids": []},
    "outlook": {"summary": None, "support_ids": []},
}


def build_prompt(company: str, insights: list[dict]) -> str:
    lines = [f"公司：{company}", "洞察："]
    for i in insights:
        lines.append(
            f'- [{i.get("insight_id")}] ({i.get("confidence")}) {i.get("content", "")[:200]}'
        )
    lines.append("\n请按 3 维（门槛/薪酬/前景）整理，每点回挂 insight_id。")
    return "\n".join(lines)


def extract_dimensions(
    insights: list[dict],
    *,
    company: str = "",
    llm_fn: Callable[[str], dict],
) -> dict:
    if not insights:
        return copy.deepcopy(_EMPTY)
    prompt = build_prompt(company, insights)
    try:
        out = llm_fn(SYSTEM + "\n\n" + prompt)
    except Exception:
        return copy.deepcopy(_EMPTY)
    # 防御：缺维度补空 + 过滤不在给定 id 集合内的 support_ids
    valid_ids = {i.get("insight_id") for i in insights}
    res = copy.deepcopy(_EMPTY)
    for dim in ("threshold", "compensation", "outlook"):
        d = (out or {}).get(dim) or {}
        d["support_ids"] = [x for x in (d.get("support_ids") or []) if x in valid_ids]
        res[dim] = {**_EMPTY[dim], **d}
    return res
