"""把 crawler 的 source 标识映射到 13 大 canonical finance track。

Phase B (2026-05-16): 99113 行 Job 里只有 0% 跑过 LLM enrich(track_predicted
留空),但每行都有 source。复用 Phase F 已经在 coverage_truth.yaml 里钉好的
canonical_tracks 映射,把 source 反推到 canonical,实现 backfill + 新增行
自动打标。

设计原则:
- **只接受 1:1 source → canonical**。1:N (e.g. hedge_funds = [量化, 私募·基本面])
  歧义太大,让下游 LLM 或 job_title 信号决定,这里返 None。
- **job_title 优先,source 兜底**。canonicalize_track(job_title) 命中(e.g.
  title 含"量化"/"PE")就直接用,跳过 source 推断 —— job-level 信号比
  source-level 准。
- **load-on-import**。模块 import 时从 coverage_truth.yaml 算一次 dict,不
  做 lazy / cache,因 yaml 改动总要重启进程。
- **source-aware title 二级路由 (D-16, 2026-05-17)**: 1:N source 上同一 alias 在
  不同上下文 canonical 不同(典型:`研究员` 在 securities 是 sell-side =
  卖方研究·S&T,但 canonical.TRACK_ALIASES 把它通用映射到 二级买方·基本面)。
  `_SOURCE_AWARE_TITLE_OVERRIDES` 给特定 source prefix 写二级规则,优先级
  最高 — 不动 D-15 "1:N source 留 NULL" 的设计,只在 title 信号清晰时切回。
- **is_ambiguous_source (2026-05-18)**: D-18 召回 mismatch penalty 需要识别
  1:N source 的 NULL,跳过错位罚分,改成"信号不足" risk note。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from app.services.taxonomy.canonical import canonicalize_track


_COVERAGE_YAML = (
    Path(__file__).resolve().parents[3] / "config" / "coverage_truth.yaml"
)


def _build_source_to_canonical() -> dict[str, str]:
    """从 coverage_truth.yaml 提取 1:1 source → canonical 映射。

    1:N source(歧义)跳过,let downstream 决定。
    """
    truth = yaml.safe_load(_COVERAGE_YAML.read_text(encoding="utf-8")) or {}
    out: dict[str, str] = {}
    for t in truth.get("tracks") or []:
        canonical_tracks = t.get("canonical_tracks") or []
        if len(canonical_tracks) != 1:
            continue  # 1:N 或 0:N 跳过
        canon = canonical_tracks[0]
        for src in (t.get("source_match") or []):
            out[src] = canon
    return out


def _build_ambiguous_sources() -> set[str]:
    """从 coverage_truth.yaml 提取 1:N source 集合 — 故意留 NULL 的来源。

    D-15: 这类 source 的 Job 行 canonical_track 是 NULL 不是因为 backfill 漏了,
    而是源头本身赛道不明 (e.g. hedge_funds_hotjob 可能买方也可能量化)。
    下游 mismatch penalty 看到这类 source 应该跳过,不当作错位。
    """
    truth = yaml.safe_load(_COVERAGE_YAML.read_text(encoding="utf-8")) or {}
    out: set[str] = set()
    for t in truth.get("tracks") or []:
        canonical_tracks = t.get("canonical_tracks") or []
        if len(canonical_tracks) <= 1:
            continue  # 0:N (没映射) 或 1:1 跳过, 只收 1:N
        for src in (t.get("source_match") or []):
            out.add(src)
    return out


# Module-level constants; rebuilt only on process restart (matches yaml lifecycle)
SOURCE_TO_CANONICAL: dict[str, str] = _build_source_to_canonical()
AMBIGUOUS_SOURCES: frozenset[str] = frozenset(_build_ambiguous_sources())


def is_ambiguous_source(source: str) -> bool:
    """该 source 在 coverage_truth.yaml 里被定义成 1:N (canonical_tracks 多个)?

    True = 信号不足而非错位,mismatch penalty 应跳过。
    """
    if not source:
        return False
    return source.strip() in AMBIGUOUS_SOURCES


# Source-aware title 二级路由:对 1:N source(securities / hedge_funds)上
# 在 source 上下文里语义有偏的 title,直接路由到正确 canonical。
#
# 规则:外层 key 是 source prefix(用 startswith 匹配);内层是 title 子串
# → canonical 字典,**外层第一个匹配的 prefix + title 子串胜出**。
#
# 关键场景:
# - 券商的 "研究员 / 行业研究 / 金融工程 / 策略分析" 是 sell-side(卖方研究·S&T),
#   而 canonical.TRACK_ALIASES 把它通用映到 公募/资管·投研(买方研究)。
# - 券商的 "投行业务 / 资本市场" 偶尔在 alias 漏掉的子部门,这里兜一下。
_SOURCE_AWARE_TITLE_OVERRIDES: list[tuple[str, dict[str, str]]] = [
    (
        "securities_",
        {
            "研究员":      "卖方研究",
            "行业研究":    "卖方研究",
            "金融工程":    "卖方研究",
            "策略分析":    "卖方研究",
            "宏观研究":    "卖方研究",
            "固收研究":    "卖方研究",
            "权益研究":    "卖方研究",
            "债券分析":    "卖方研究",
            "股票分析":    "卖方研究",
            "策略研究":    "卖方研究",
            "信用研究":    "卖方研究",
            # IBD/M&A/资本市场 — 即便 alias 已覆盖 'ibd'/'投行',这里再兜一层
            "投行业务":    "投行·并购·资本市场",
            "并购重组":    "投行·并购·资本市场",
            "资本市场":    "投行·并购·资本市场",
            "ECM":         "投行·并购·资本市场",
            "DCM":         "投行·并购·资本市场",
            # 金融科技:券商科技子公司岗,通用 alias 漏抓
            "开发工程师":  "金融科技",
            "算法工程师":  "金融科技",
            "AI工程师":    "金融科技",
            "数据工程师":  "金融科技",
            "测试工程师":  "金融科技",
        },
    ),
]


def canonicalize_job(source: str, job_title: str) -> Optional[str]:
    """优先用 source-aware title 二级路由;再退 job_title alias;再退 source 映射;
    再不行返 None。

    顺序合理性:source-aware override 解决 1:N source 上 title 语义偏移;
    job_title 是岗位级信号;source 是平台级信号(只在 1:1 mapping 时可信)。
    都没命中就 None,交给下游 LLM rerank 或人工 review_queue。
    """
    src = (source or "").strip()
    title = job_title or ""

    # 1. source-aware title 二级路由 (highest priority for 1:N sources)
    if src and title:
        for prefix, overrides in _SOURCE_AWARE_TITLE_OVERRIDES:
            if src.startswith(prefix):
                for needle, canon in overrides.items():
                    if needle in title:
                        return canon
                break  # 同 prefix 只匹配一组,不跨 prefix

    # 2. 通用 title alias
    if title:
        canon = canonicalize_track(title)
        # canonicalize_track 没命中时返原字符串,得校验
        if canon and canon != title:
            return canon

    # 3. source 兜底 (只在 1:1 mapping 时可信)
    if src:
        return SOURCE_TO_CANONICAL.get(src)

    return None
