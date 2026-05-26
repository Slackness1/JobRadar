"""6 大策略 seed query + 25 候选博主清单 (spec §4.2)。

候选博主清单从 docs/xhs-blogger-discovery-2026-05-23.md 的"25 个候选同行" section 来,
真正 deep crawl 之前 user 应再 review 一遍 (有人可能账号注销了)。
"""
from __future__ import annotations


_SEEDS: dict[str, list[str]] = {
    "基本面权益": [
        "公募基金 校招",
        "公募基金 实习 行业研究",
        "易方达 校招",
        "嘉实基金 消费组",
        "华夏基金 投研",
        "南方基金 实习",
        "保险资管 投研",
        "券商资管 校招",
        "银行理财子 投研",
        "基本面研究员 入门",
        "公募 vs 资管 选择",
        "SAIF MF 公募 实习",
    ],
    "量化": [
        "量化私募 校招",
        "幻方 校招",
        "九坤 实习",
        "明汯 投资",
        "灵均 量化研究员",
        "鸣石投资 校招",
        "多因子 因子开发",
        "高频策略 实习",
        "机器学习 量化",
        "alpha 因子",
        "量化交易员 vs 研究员",
        "公募量化 vs 私募量化",
    ],
    "固定收益": [
        "公募固收 校招",
        "银行理财子 固收",
        "保险资管 固收",
        "利率债 研究",
        "信用债 研究",
        "可转债 研究",
        "固收 投研 实习",
        "FICC 入门",
    ],
    "卖方研究": [
        "券商研究所 校招",
        "中信证券 研究所",
        "中金 研究 实习",
        "海通 行业研究",
        "招商证券 TMT",
        "卖方 行业研究员",
        "卖方 vs 买方 选择",
        "首席分析师 路径",
    ],
    "多资产_FOF_衍生品": [
        "FOF 投资 实习",
        "FOF 投资经理",
        "MOM 配置",
        "多资产 配置 校招",
        "衍生品 期权策略",
        "结构化产品",
    ],
    "相关补充": [
        "PE 投后 研究",
        "VC 行业研究",
        "量化 IT 校招",
        "量化 开发 实习",
        "金融科技 数据 算法",
    ],
    # 跨域: AI 应用 / 产品经理 / 大模型开发 (给 P_self 用)
    # seed 全部用 generic 求职词, 不带公司名 — 让 XHS 数据告诉我们头部公司是谁
    "AI应用_PM_开发": [
        "AI 实习",
        "大模型 实习",
        "大模型 校招",
        "AI 应用开发 实习",
        "AI 产品经理 校招",
        "AI 产品经理 实习",
        "LLM 工程师 实习",
        "Agent 工程师 校招",
        "RAG 工程师",
        "算法工程师 LLM",
        "GenAI 校招",
        "AI 求职",
    ],
}


# 25 候选博主 (Pony 报告 + Pony 自己) — uid 是 XHS 用户 ID, name 是博主名
# 真正 deep crawl 前 user 应再 review 这个 list (有人可能账号失效)
CANDIDATE_BLOGGERS: list[dict[str, str]] = [
    {"uid": "620f9d93000000002102508e", "name": "Pony说求职", "tier": "1", "topic": "金融求职全栈"},
    # TODO: user 提供完整 25 个清单时填充, 当前作为 placeholder.
    # 待 user 在 docs/xhs-blogger-discovery-2026-05-23.md 完整版的 §"25 个真同行候选" 段补全
    # 如果当前找不到 25 个, 也接受 1-N 的开端, subagent 跑起来后会再发现新博主
]


def seed_keywords_for_strategy(strategy: str) -> list[str]:
    if strategy not in _SEEDS:
        raise KeyError(f"未知 strategy: {strategy!r}")
    return list(_SEEDS[strategy])


def same_company_angles(company: str) -> list[str]:
    """同公司 5 视角 query (spec V3 vector)。"""
    return [
        f"{company} 面试",
        f"{company} 实习",
        f"{company} 入职",
        f"{company} 离职",
        f"{company} 真实",
    ]
