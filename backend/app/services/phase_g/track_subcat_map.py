"""13 canonical 赛道 → 33 sub_cat 显式映射 (Phase G, 2026-05-29)。

为什么不用子串匹配:
  旧 _v2_extract_preferred_sub_cats 把赛道名跟 33 个 sub_cat 名做 substring
  匹配 — "公募权益研究员" 这种无分隔符复合词永远命中不到, 还会误抓 "买方 Quant"
  (因 "买方" 命中)。persona 评测显示 P1/P3/P9 头部覆盖只有 0.4-0.5。
  改成显式对照表后, 学生选的赛道能精确映射到该赛道的 sub_cat。

覆盖缺口 (留空, 走通用召回):
  监管·体制内 / 咨询·MBB+Tier2 / 企业战略·管培·实业金融 / 大宗·能源 —
  33-sub_cat 体系偏投研 + AI, 这 4 个赛道暂无对应 sub_cat。后续要么补 sub_cat,
  要么这些赛道走 v1 canonical 路径。

key 必须严格等于 backend/app/services/taxonomy/canonical.py 的 CANONICAL_FINANCE_TRACKS;
value 必须严格等于 knowledge_synthesis.SUBCAT_TO_STRATEGY 的键。改前两边对齐。
"""
from __future__ import annotations

CANONICAL_TRACK_TO_SUBCATS: dict[str, list[str]] = {
    "公募/资管·投研": [
        # 前台投研/资管核心。**不含**公募基金中后台 / 基金产品运营·中后台 —— 那是
        # 中后台运营,把它们当"投研强匹配"会给投研学生推基金会计/估值清算(2026-06-02 修)。
        "公募权益研究员",
        "行业研究员·消费",
        "行业研究员·TMT-医药-周期",
        "公募指数研究员",
        "信用研究员",
        "固收+多资产",
        "利率宏观策略",
        "资管FOF",
        "财富管理FOF",
    ],
    "私募·基本面": [
        "公募权益研究员",
        "行业研究员·消费",
        "行业研究员·TMT-医药-周期",
        "自营FOF",
    ],
    "量化": [
        "量化研究员·中频",
        "量化研究员·高频",
        "量化因子工程师",
        "量化开发QD",
        "AI 量化工程师",
        "买方 Quant",
    ],
    "卖方研究": [
        "卖方研究员·TMT",
        "卖方研究员·消费医药周期",
        "卖方研究员·宏观策略",
    ],
    "S&T·FICC·衍生品": [
        "固收交易员",
        "利率宏观策略",
        "结构化产品衍生品",
        "机构销售·销售支持",
        "债券承做DCM·ABS/REITs",
    ],
    "投行·并购·资本市场": [
        "投行 IBD",
        "债券承做DCM·ABS/REITs",
    ],
    "一级股权·PE/VC": [
        "PE投后VC行研",
    ],
    "银行·总行核心": [
        "信用研究员",
        "基金产品运营·中后台",
    ],
    "监管·体制内": [],
    "金融科技": [
        # 2026-06-12: 旧 "AI PM"/"Agent工程师" 已被强模型重分类拆成下面的 AI 桶,
        # 这里换成新桶(含最对口的"金融科技/支付/风控产品经理")。纯互联网产品桶
        # (用户增长/商业化/策略数据/ToB PM) 暂不挂赛道, 走 NL 或显式勾选召回,
        # 待 11×55 重构补出独立"互联网泛科技"赛道再正式纳入。
        "金融科技/支付/风控产品经理",
        "金融科技·量化平台",
        "AI产品经理",
        "Agent/工作流产品经理",
        "AI产品工程师/Product Engineer",
        "LLM/RAG应用工程师",
        "Agent平台工程师",
        "AI算法业务",
        "LLM算法post-train",
        "多模态推理优化",
    ],
    "咨询·MBB+Tier2": [],
    "企业战略·管培·实业金融": [],
    "大宗·能源": [],
}


def subcats_for_tracks(tracks: list[str]) -> list[str]:
    """给一组 canonical 赛道, 返回去重保序的 sub_cat 列表。未知赛道忽略。"""
    out: list[str] = []
    seen: set[str] = set()
    for t in tracks or []:
        for sc in CANONICAL_TRACK_TO_SUBCATS.get((t or "").strip(), []):
            if sc not in seen:
                seen.add(sc)
                out.append(sc)
    return out
