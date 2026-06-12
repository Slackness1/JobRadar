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
def _load_brands() -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """返回有序品牌表 ((tier, brand, stems), ...)。

    JSON 2026-06-12 起为品牌分组结构 {tier: {品牌标准名: [词根...]}}; 词根 lower-case
    便于英文大小写无关匹配。顺序 = 匹配优先级: ai_special > tier1 > tier2。
    """
    try:
        raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return ()
    out: list[tuple[str, str, tuple[str, ...]]] = []
    for tier in ("ai_special", "tier1", "tier2"):
        brands = raw.get(tier) or {}
        if not isinstance(brands, dict):
            continue
        for brand, stems in brands.items():
            st = tuple(str(s).strip().lower() for s in (stems or []) if str(s).strip())
            if brand and st:
                out.append((tier, str(brand).strip(), st))
    return tuple(out)


def internet_brand_tier_of(company: str | None) -> tuple[str, str] | None:
    """公司名 → (品牌标准名, tier)。子串匹配, 未命中返回 None。

    品牌聚合的核心入口: '字节/抖音' 与 '字节跳动' 都归 ('字节跳动','tier1'),
    '阿里文娱' 与 '阿里巴巴文化娱乐有限公司' 都归 ('阿里巴巴','tier1') ——
    梯队骨架据此把同品牌的多个公司名变体合并成一张卡。
    """
    if not company:
        return None
    c = str(company).strip().lower()
    if not c:
        return None
    for tier, brand, stems in _load_brands():
        if any(stem in c for stem in stems):
            return (brand, tier)
    return None


def internet_tier_of(company: str | None) -> str | None:
    """公司名 → 'tier1' / 'tier2' / 'ai_special' / None(未命中)。子串匹配,
    ai_special 最先(AI 原生公司单列档, 不混入 T1/T2 —— 口径 2026-06-12)。"""
    hit = internet_brand_tier_of(company)
    return hit[1] if hit else None


def internet_brand_of(company: str | None) -> str | None:
    """公司名 → 品牌标准名(未命中返回 None)。"""
    hit = internet_brand_tier_of(company)
    return hit[0] if hit else None
