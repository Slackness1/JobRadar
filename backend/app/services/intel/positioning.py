"""定位拼装：从 job 的 taxonomy 字段生成 赛道/梯队/粗条线/一句话。粗粒度（金融不细分部门）。"""
from __future__ import annotations
import re

# 粗条线：从 title/department 关键词抽（抽不到则省略）
_LINE_KW = [
    ("固定收益", "固收条线"), ("固收", "固收条线"), ("投行", "投行条线"),
    ("资产管理", "资管条线"), ("资管", "资管条线"), ("研究所", "卖方研究条线"),
    ("量化", "量化条线"), ("风险管理", "风险条线"), ("衍生品", "衍生品条线"),
    ("机构", "机构业务条线"),
]
# sub_cat → SAIF 出路定位（一句话用）
_OUTLET = {
    "信用研究员": "卖方/买方固收核心出路", "利率宏观策略": "固收宏观研究出路",
    "机构销售·销售支持": "卖方/资管机构条线核心出路", "投行 IBD": "一级市场核心出路",
    "财富管理FOF": "资管FOF出路", "风险管理·投资监督": "中后台投资监督出路",
    "银行总行综合管培": "银行总行管理序列出路",
}


def _track_line(title: str, dept: str) -> str:
    blob = (title or "") + " " + (dept or "")
    for kw, line in _LINE_KW:
        if kw in blob:
            return line
    return ""


def build_positioning(job: dict) -> dict:
    sub = job.get("sub_category")
    tier = job.get("institution_tier")
    line = _track_line(job.get("job_title", ""), job.get("department", ""))
    outlet = _OUTLET.get(sub or "", "金融核心赛道") if sub else "金融岗位"
    one = f"{tier or ''}{(' · ' if tier and sub else '')}{sub or ''}，{outlet}".strip("，· ")
    return {
        "sub_category": sub,
        "tier": tier,
        "tier_label": tier or "梯队待定",
        "track_line": line,
        "one_liner": one or "金融岗位",
    }
