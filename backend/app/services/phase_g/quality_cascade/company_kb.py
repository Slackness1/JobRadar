"""GT 公司反向索引 + 轻量 KB block 生成(纯函数, 无网络)。

ground_truth_companies_v1.json 是按 sub_cat 分组的; 这里反向成
公司核心字号 → {tier, sub_cats}, 给 quality 判别器注入"每公司一行"背景:
把 flash 对金融公司"训练少→系统性误判"转成随机噪声, 投票/级联才有意义。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.services.phase_g.tier_fit.tier_ladder import _norm_company

# backend/ 根 → data/ground_truth_companies_v1.json
_DEFAULT_GT_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "ground_truth_companies_v1.json"
)
_MAX_SUBCATS_IN_BLOCK = 4


def load_gt_index(path: str | None = None) -> dict[str, dict]:
    """反向索引: 归一公司名 → {"tier": str, "sub_cats": [str, ...]}。

    同一公司在多个 sub_cat 下出现时合并典型赛道(去重保序), tier 取首个非空。
    """
    gt_path = Path(path) if path else _DEFAULT_GT_PATH
    raw = json.loads(gt_path.read_text(encoding="utf-8"))
    index: dict[str, dict] = {}
    for _sub_cat, entries in (raw.get("ground_truth") or {}).items():
        for e in entries or []:
            name = (e.get("name") or "").strip()
            if not name:
                continue
            key = _norm_company(name)
            slot = index.setdefault(key, {"tier": "", "sub_cats": []})
            if not slot["tier"] and e.get("tier"):
                slot["tier"] = str(e["tier"])
            for sc in e.get("primary_sub_cats") or []:
                if sc and sc not in slot["sub_cats"]:
                    slot["sub_cats"].append(sc)
    return index


@lru_cache(maxsize=1)
def _default_index() -> dict[str, dict]:
    return load_gt_index()


def build_company_kb_block(company: str, *, index: dict[str, dict] | None = None) -> str:
    """命中 GT 公司则返回一行背景, 否则空串。

    例: "【公司背景】易方达基金 — 梯队: 一线公募; 典型赛道: 公募权益研究员/公募指数研究员"
    """
    if not company or not company.strip():
        return ""
    idx = index if index is not None else _default_index()
    info = idx.get(_norm_company(company))
    if not info:
        return ""
    parts = []
    if info.get("tier"):
        parts.append(f"梯队: {info['tier']}")
    if info.get("sub_cats"):
        sub = "/".join(info["sub_cats"][:_MAX_SUBCATS_IN_BLOCK])
        parts.append(f"典型赛道: {sub}")
    if not parts:
        return ""
    norm = _norm_company(company)
    return f"【公司背景】{norm} — " + "; ".join(parts)
