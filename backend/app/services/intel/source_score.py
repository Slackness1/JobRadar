"""Layer-1 信源分（弱版，零 LLM）。设计见 docs/source-credibility-layer1-design-2026-05-31.md。
当前仅用已有信号（liked/comment/signal_score/author + 营销闸）。收藏比/作者权威待补数据后并入。"""
from __future__ import annotations
import math, re

PLATFORM_VALUE = {"xhs": 1.0, "zhihu": 0.85, "bilibili": 0.85, "podcast": 0.5}
_MARKETING = re.compile(r"扫码|进群|我的课|训练营|资料领取|私信领|公总号|加我咨询|领取资料")

def platform_of(note_id: str) -> str:
    nid = note_id or ""
    if nid.startswith("zh_"): return "zhihu"
    if nid.startswith("xhsp_") or nid.startswith("xhs_"): return "xhs"
    if nid.startswith("bili_"): return "bilibili"
    if nid.startswith("pod_"): return "podcast"
    return "xhs"  # 默认按 UGC

def _norm(x: float, ref: float) -> float:
    x = max(0.0, float(x or 0))
    return min(1.0, math.log1p(x) / math.log1p(ref))

def compute_source_score(
    note_id: str, *, liked: float = 0, comment: float = 0,
    signal_score: float = 0, author_name: str = "", marketing_text: str = "",
) -> float:
    pv = PLATFORM_VALUE.get(platform_of(note_id), 0.85)
    signal_quality = (
        0.40 * _norm(liked, 1000)
        + 0.20 * _norm(comment, 300)
        + 0.25 * _norm(signal_score, 500)
        + 0.15 * (1.0 if (author_name or "").strip() else 0.0)
    )
    gate = 0.2 if _MARKETING.search(marketing_text or "") else 1.0
    return round(pv * signal_quality * gate, 3)
