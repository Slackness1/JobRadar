"""低质量岗位红线词 — 跟 canonical track 正交。

任何赛道都适用 — 命中即认为是销售/基层岗,降级到推荐底部 + UI warning。

详见 docs/finance-tracks-2026-overview.md "低质量岗位红线"段。
"""
from __future__ import annotations


# 红线 — 命中即认为是低质量岗位。
# 严格控制误杀: 只放置基本无歧义的销售/基层关键词。"客户经理" 单独不放(歧义太大,
# 可能是"机构客户经理" 或 "对公客户经理"); 但"远程/零售/网点/个人客户经理" 那种限定
# 词加进去就是基层零售岗。
LOW_QUALITY_ROLE_PATTERNS: tuple[str, ...] = (
    '柜员', '大堂经理', '柜面服务',
    '客户服务', '客服',
    '渠道销售', '渠道经理', '渠道岗',
    '营销岗', '营销专员', '财富营销', '零售营销',
    '保险代理', '寿险销售', '财险销售', '保险顾问', '代理人',
    '理财经理', '理财顾问',
    '财富顾问', '投资顾问',     # 营业部级别为主
    'FOF销售', '基金销售', '产品销售',
    '远程客户经理', '个人客户经理', '零售客户经理', '网点客户经理',
)

# 命中扣分,把 final_score 拉到推荐底部 (现网正常 SAIF 投研岗 final_score ~ 50-80)
LOW_QUALITY_PENALTY: int = 50


def is_low_quality_role(job_title: str) -> str | None:
    """返回命中的关键词, 没命中返 None。

    用 substring 直接匹配 — 没用 regex 因为模式都是普通中文短语。
    """
    if not job_title:
        return None
    for pat in LOW_QUALITY_ROLE_PATTERNS:
        if pat in job_title:
            return pat
    return None
