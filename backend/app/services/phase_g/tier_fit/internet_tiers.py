"""互联网/AI/游戏赛道重点公司分档查询。

动机: GT 名单(`ground_truth_companies_v1.json`)是金融导向(SAIF), 互联网 sub_cat 桶里
GT 集为空 → 桶内只剩新鲜度区分, 大厂被随机新岗盖过。enrich 打的 institution_tier
自由文本能做粗退路, 但有噪声(银泰百货被标"互联网大厂"会错误浮顶; 国金证券/平安证券被
误标"互联网大厂"混进互联网桶)。

这里用一份**策展品牌词根名单**(`data/internet_company_tiers.json`)做更准的档次先验:
- 子串匹配(不是精确集合): 库里公司名常带地区/子公司前缀('百度在线网络技术（北京）有限公司'
  / '深圳市腾讯计算机系统'), 精确匹配大面积漏配; 词根命中即可。
- 天然挡噪声: 国金证券/银泰百货 不含互联网词根 → 不命中, 不再被误标 tier 抬分。
- tier1 优先于 tier2, 先命中先归档。

只读名单, 进程内 lru_cache; 改 JSON 后重启刷新。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parents[4] / "data" / "internet_company_tiers.json"


@lru_cache(maxsize=1)
def _load_stems() -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """返回 (tier1_stems, tier2_stems, ai_special_stems), lower-case 便于英文词根
    大小写无关匹配。"""
    try:
        raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return ((), (), ())
    t1 = tuple(str(s).strip().lower() for s in raw.get("tier1", []) if str(s).strip())
    t2 = tuple(str(s).strip().lower() for s in raw.get("tier2", []) if str(s).strip())
    ai = tuple(str(s).strip().lower() for s in raw.get("ai_special", []) if str(s).strip())
    return (t1, t2, ai)


def internet_tier_of(company: str | None) -> str | None:
    """公司名 → 'tier1' / 'tier2' / 'ai_special' / None(未命中)。子串匹配,
    ai_special 最先(AI 原生公司单列档, 不混入 T1/T2 —— 口径 2026-06-12)。"""
    if not company:
        return None
    c = str(company).strip().lower()
    if not c:
        return None
    t1, t2, ai = _load_stems()
    if any(stem in c for stem in ai):
        return "ai_special"
    if any(stem in c for stem in t1):
        return "tier1"
    if any(stem in c for stem in t2):
        return "tier2"
    return None
