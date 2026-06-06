"""先验硬规则路由(纯函数, 无模型在环)。

只回答"这个岗 flash 大概率拿不准、要不要升级强模型", 不给最终 label。
规则源自 jobradar-enrich skill 沉淀的 flash 系统性误判类型。校准脚本
(26_divergence_map.py) 会用库里强模型 baseline 验证/修剪这张表。
"""
from __future__ import annotations

# "销售/客户经理"类: 难点是区分 A 机构销售(good) vs B/C 零售/渠道(support)。
_RETAIL_CHANNEL_KW = (
    "理财经理", "财富顾问", "私人财富", "个人客户经理", "营业部",
    "渠道经理", "代销", "持营", "零售客户",
)
# 泛销售标题(无机构信号时算难)
_GENERIC_SALES_KW = ("销售", "客户经理", "客户经理岗", "业务经理")
# JD 里出现这些 = 机构销售信号, 配 KB 后 flash 够用, 不必升级
_INSTITUTIONAL_SIGNAL_KW = (
    "机构客户", "机构销售", "机构业务", "路演", "策略会", "投研服务",
    "ficc", "qfii", "同业", "年金", "理财子", "资管机构", "corporate access",
)
# 中后台: 易被 flash 误判 support, 实为金融核心
_MIDDLE_BACK_OFFICE_KW = (
    "中台", "投资监督", "投资运营", "衍生品运营", "衍生品中台",
    "量化平台运营", "产品设计", "风险管理", "投资风险",
)
# 对公/零售银行条线歧义
_BANK_LINE_KW = ("对公", "零售条线", "对公条线", "公司金融")
# 外资量化/投行英文岗名(训练数据少, flash 易误判)
_FOREIGN_FIRMS = (
    "optiver", "point72", "citadel", "jane street", "two sigma", "jump trading",
    "goldman", "morgan stanley", "jp morgan", "j.p. morgan", "ubs", "barclays",
    "deutsche", "hsbc", "nomura",
)
_ENGLISH_ROLE_KW = ("trader", "quant", "researcher", "analyst", "developer", "engineer")


def _has(text: str, kws) -> bool:
    t = (text or "").lower()
    return any(k.lower() in t for k in kws)


def is_hard_pattern(
    *, company: str, title: str, duty: str, req: str
) -> tuple[bool, str | None]:
    """返回 (是否难, 命中规则名|None)。难 = 升级强模型。"""
    title = title or ""
    jd = f"{duty or ''}\n{req or ''}"

    # 1. 零售/渠道销售 → 难
    if _has(title, _RETAIL_CHANNEL_KW):
        return True, "retail_or_channel_sales"

    # 2. 泛销售/客户经理, 且 JD 无机构信号 → 难(分不清 A/B/C 层)
    if _has(title, _GENERIC_SALES_KW) and not _has(jd, _INSTITUTIONAL_SIGNAL_KW):
        return True, "retail_or_channel_sales"

    # 3. 中后台 → 难
    if _has(title, _MIDDLE_BACK_OFFICE_KW):
        return True, "middle_back_office"

    # 4. 对公/零售银行条线 → 难
    if _has(title, _BANK_LINE_KW):
        return True, "bank_line_ambiguity"

    # 5. 外资公司 + 英文岗名 → 难
    if _has(company, _FOREIGN_FIRMS) and _has(title, _ENGLISH_ROLE_KW):
        return True, "foreign_english_role"

    return False, None
