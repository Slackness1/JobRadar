"""Source quality tier mapping.

Classifies each job's `source` field into a quality tier so the UI can display
trust signals to SAIF students:

- tier_1 (官网直采): 来自我们直接对接的独立 ATS (mokahr/zhiye/hotjob/Wintalent/
  Workday/Greenhouse/Eightfold/citics-DOM 等),数据已经过 portal-side 校验,
  招聘方明确发布。这是「学生应该优先看的」信号源。
- tier_2 (聚合来源): 来自第三方聚合(Tata 旺神/应届生网/牛客)或历史 legacy
  快照。覆盖范围广(尤其公募/资管/理财子季节性强的赛道,Tata 91%+ 兜底),
  但数据时效性 + 字段准确度 弱于 tier_1。
- unknown: source 为空或不识别 — UI 默认不展示 trust 标。

设计选择: 不在 jobs 表加 source_tier 列(轻改动),纯运行时 map。如果后续要
按 tier 做 SQL filter(例如「只看 tier_1 岗位」),再加 column。
"""
from __future__ import annotations


# 我们直接对接的独立 ATS — source 前缀
# (每个 tier crawler / handler 自己定义 source 字符串)
_TIER_1_PREFIXES: tuple[str, ...] = (
    # 银行/国央企/保险/消费外企/外资行 portal 直采
    "bank_official",
    "insurance_official",
    "state_owned_official",
    "consumer_foreign_official",
    "foreign_ibs_official",
    "pe_vc_official",
    "internet_official",
    # 多 family 券商/公募/私募 (含 securities_zhiye / hedge_funds_moka_embedded / 等)
    "securities_",
    "funds_",
    "hedge_funds_",
    # 能源 (CLI tier crawler)
    "energy_",
)

# 显式 tier_2 source 名 (聚合源)
_TIER_2_SOURCES: frozenset[str] = frozenset({
    "tatawangshen",       # Tata 旺神
    "haitou_xyzp",        # 应届生海投
    "haitou_securities",  # 应届生海投券商专用
    "teacher_entry",      # 老师录入手工导入 — 也算"聚合"
})

# Legacy snapshot 来源(早期手工导入 / 老 crawler 存档)
_TIER_LEGACY_PREFIXES: tuple[str, ...] = (
    "legacy",
    "bank-legacy",
    "job-crawler-legacy",
    "job-crawler-jobcrawler",
)


def source_tier(source: str | None) -> str:
    """Return one of {tier_1, tier_2, unknown}."""
    if not source:
        return "unknown"
    if source in _TIER_2_SOURCES:
        return "tier_2"
    for p in _TIER_LEGACY_PREFIXES:
        if source.startswith(p):
            return "tier_2"
    for p in _TIER_1_PREFIXES:
        if source.startswith(p):
            return "tier_1"
    return "unknown"


def source_quality_label(source: str | None) -> str:
    """Human-readable label for UI."""
    t = source_tier(source)
    return {
        "tier_1": "官网直采",
        "tier_2": "聚合来源",
        "unknown": "未分类",
    }[t]


def tier_breakdown(sources: list[str]) -> dict[str, int]:
    """Count rows by tier. Input: list of source strings. Output: {tier: count}."""
    out = {"tier_1": 0, "tier_2": 0, "unknown": 0}
    for s in sources:
        out[source_tier(s)] += 1
    return out
