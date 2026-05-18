"""把 crawler 的 source 标识映射到 8 大 canonical finance track。

Phase B (2026-05-16): 99113 行 Job 里只有 0% 跑过 LLM enrich(track_predicted
留空),但每行都有 source。复用 Phase F 已经在 coverage_truth.yaml 里钉好的
canonical_tracks 映射,把 source 反推到 canonical,实现 backfill + 新增行
自动打标。

设计原则:
- **只接受 1:1 source → canonical**。1:N (e.g. hedge_funds = [量化, 二级买方·基本面])
  歧义太大,让下游 LLM 或 job_title 信号决定,这里返 None。
- **job_title 优先,source 兜底**。canonicalize_track(job_title) 命中(e.g.
  title 含"量化"/"PE")就直接用,跳过 source 推断 —— job-level 信号比
  source-level 准。
- **load-on-import**。模块 import 时从 coverage_truth.yaml 算一次 dict,不
  做 lazy / cache,因 yaml 改动总要重启进程。
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


def canonicalize_job(source: str, job_title: str) -> Optional[str]:
    """优先用 job_title 推断 canonical;不行的话退到 source 映射;再不行返 None。

    顺序合理性:job_title 是岗位级信号("量化研究员"明确是 量化 track);
    source 是平台级信号(只在 1:1 mapping 时可信)。两边都没命中就 None,
    交给下游 LLM rerank 或人工 review_queue。
    """
    if job_title:
        canon = canonicalize_track(job_title)
        # canonicalize_track 没命中时返原字符串,得校验
        if canon and canon != job_title:
            return canon

    if source:
        return SOURCE_TO_CANONICAL.get(source.strip())

    return None
