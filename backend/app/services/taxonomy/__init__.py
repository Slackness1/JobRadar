"""项目级金融赛道 taxonomy — 8 个 canonical track 跟 docs/finance-tracks-2026-overview.md
对齐, 给整个项目 (recommendation / parser / preferences / interview / eval) 共用。

设计原则:
  - **8 个 canonical** 不轻易增 (再多打散下游 eval coverage)
  - **alias** 自由扩 (反映用户实际用语)
  - **低质量红线** 跟 canonical 正交,适用于任何赛道
  - 后续 phase D-0 会把 knowledge field (典型雇主/STAR/follow-up 模板) 装进来
  - 后续可能搬到 tracks.yaml,但目前 Python 常量也够用

public API:
  - CANONICAL_FINANCE_TRACKS — tuple[str, ...] of 8
  - canonicalize_track(label) -> str — 别名映射,映射不到返原值
  - expand_track_to_canonicals(label) -> list[str] — 用户 raw 偏好 → 一组 canonical
  - transferable_for(label) -> list[str] — 用户 raw 偏好 → 可迁移 canonical (跳板)
  - aliases_for_canonical(canon) -> list[str] — canonical → 所有 alias (含自身)
  - is_low_quality_role(job_title) -> str | None — 红线检测,返命中 pattern 或 None
  - LOW_QUALITY_ROLE_PATTERNS — tuple[str, ...] (public for testing)
  - LOW_QUALITY_PENALTY — int (推荐 final_score 扣分量)
  - is_ambiguous_source(source) -> bool — 1:N source 不当作错位
"""
from app.services.taxonomy.canonical import (
    CANONICAL_FINANCE_TRACKS,
    RECALL_HINTS_PER_CANONICAL,
    TRANSFERABLE_FOR_UMBRELLA,
    aliases_for_canonical,
    canonicalize_track,
    expand_track_to_canonicals,
    recall_keywords_for_canonical,
    transferable_for,
)
from app.services.taxonomy.quality import (
    LOW_QUALITY_PENALTY,
    LOW_QUALITY_ROLE_PATTERNS,
    is_low_quality_role,
)
from app.services.taxonomy.source_map import (
    AMBIGUOUS_SOURCES,
    SOURCE_TO_CANONICAL,
    canonicalize_job,
    is_ambiguous_source,
)

__all__ = [
    'CANONICAL_FINANCE_TRACKS',
    'TRANSFERABLE_FOR_UMBRELLA',
    'RECALL_HINTS_PER_CANONICAL',
    'canonicalize_track',
    'expand_track_to_canonicals',
    'transferable_for',
    'aliases_for_canonical',
    'recall_keywords_for_canonical',
    'LOW_QUALITY_ROLE_PATTERNS',
    'LOW_QUALITY_PENALTY',
    'is_low_quality_role',
    'SOURCE_TO_CANONICAL',
    'AMBIGUOUS_SOURCES',
    'canonicalize_job',
    'is_ambiguous_source',
]
