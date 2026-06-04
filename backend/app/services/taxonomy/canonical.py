"""13 canonical 金融赛道 + 别名映射。

2026-05-23 重写: 老 10 个 canon → 新 13 个。详见 DECISIONS.md。
拆 / 合 总结:
  - 二级买方·基本面 → 公募/资管·投研 + 私募·基本面 (拆)
  - 卖方研究·S&T → 卖方研究 + S&T·FICC·衍生品 (拆)
  - 一级市场 → 投行·并购·资本市场 + 一级股权·PE/VC (拆)
  - 银行·总行核心 (扩范围: 含政策行 / 外管 / 交易所 / 金融基础设施)
  - 监管·体制内 (缩范围: 只剩央行 / 证监会 / 银保监 / 国央企 / 主权基金)
  - 管理咨询·MBB + 战略咨询 → 咨询·MBB+Tier2 + 企业战略·管培·实业金融 (合再拆)
  - 量化 / 金融科技 / 大宗·能源 不动
"""
from __future__ import annotations


CANONICAL_FINANCE_TRACKS: tuple[str, ...] = (
    '公募/资管·投研',                # 公募 / 保险资管 / 券商资管 / 银行理财
    '私募·基本面',                    # 阳光私募 / 长短仓 / 行业研究私募
    '量化',
    '卖方研究',                       # 券商研究所 sell-side equity research
    'S&T·FICC·衍生品',               # sales & trading / FICC / global markets
    '投行·并购·资本市场',             # IBD / M&A / ECM / DCM
    '一级股权·PE/VC',                # PE / VC / buyout / growth / CVC
    '银行·总行核心',                  # 国大/股份/政策行/外管/交易所/金融基础设施
    '监管·体制内',                    # 央行/证监会/银保监/国央企/汇金/社保
    '金融科技',
    '咨询·MBB+Tier2',                # MBB + 罗兰贝格/Oliver Wyman/科尔尼/四大 FAS
    '企业战略·管培·实业金融',         # 互联网战略部 / 实业管培 / 实业金融 / 战投
    '大宗·能源',
)


# 别名 → canonical 映射。命中规则:longest-match-wins(详见 canonicalize_track)。
# 包含老 canon 名作为 backward-compat alias,让 LLM rerank prompt / 测试 fixture /
# 历史代码里残留的老名字也会被正确归位。
TRACK_ALIASES: dict[str, str] = {
    # ===== 公募/资管·投研 =====
    '公募': '公募/资管·投研',
    '公募基金': '公募/资管·投研',
    '公募基金/研究': '公募/资管·投研',
    '公募/研究': '公募/资管·投研',
    '主动基金': '公募/资管·投研',
    '银行理财子': '公募/资管·投研',
    '理财子': '公募/资管·投研',
    '保险资管': '公募/资管·投研',
    '券商资管': '公募/资管·投研',
    '资产管理': '公募/资管·投研',
    '资管': '公募/资管·投研',
    '信托': '公募/资管·投研',
    '信托公司': '公募/资管·投研',
    'asset management': '公募/资管·投研',
    'am': '公募/资管·投研',
    'mutual fund': '公募/资管·投研',
    'public fund': '公募/资管·投研',
    'long-only': '公募/资管·投研',
    'long only': '公募/资管·投研',
    'fund research': '公募/资管·投研',
    'fundamental research': '公募/资管·投研',
    'pm assistant': '公募/资管·投研',
    'buy-side': '公募/资管·投研',
    'buy side': '公募/资管·投研',
    'buy-side research': '公募/资管·投研',
    'buy side research': '公募/资管·投研',
    # 子行业 → 默认归公募/资管行研 (SAIF placement 公募行研最大头)
    '行研': '公募/资管·投研',
    '行业研究': '公募/资管·投研',
    '行业研究员': '公募/资管·投研',
    '基本面研究': '公募/资管·投研',
    '消费': '公募/资管·投研',
    '医药': '公募/资管·投研',
    '医药生物': '公募/资管·投研',
    '生物医药': '公募/资管·投研',
    'tmt': '公募/资管·投研',
    'TMT': '公募/资管·投研',
    '科技': '公募/资管·投研',
    '半导体': '公募/资管·投研',
    '新能源': '公募/资管·投研',
    '能源材料': '公募/资管·投研',
    '高端制造': '公募/资管·投研',
    '军工': '公募/资管·投研',
    '周期': '公募/资管·投研',
    '二级市场买方': '公募/资管·投研',
    # 信用研究 / 财务分析 路径 — 财务管理本/会计背景学生转投研的现实切入点
    # (信用研究 / IPO 跟踪 / 财务建模比纯权益投研更易拿)。归买方投研篮子,
    # 与 公募/资管·投研 的 '信用研究员' / '固收+多资产' sub_cat 一致。
    '信用研究': '公募/资管·投研',
    '信用研究员': '公募/资管·投研',
    '信用债研究': '公募/资管·投研',
    '信用债': '公募/资管·投研',
    '财务分析': '公募/资管·投研',
    '财务建模': '公募/资管·投研',
    # backward-compat 老 canon 名
    '二级买方·基本面': '公募/资管·投研',

    # ===== 私募·基本面 =====
    '私募': '私募·基本面',
    '阳光私募': '私募·基本面',
    '私募基金': '私募·基本面',
    '私募证券': '私募·基本面',
    '私募研究': '私募·基本面',
    '私募研究员': '私募·基本面',
    '对冲基金': '私募·基本面',
    'hedge fund': '私募·基本面',
    'long-short': '私募·基本面',
    'long/short': '私募·基本面',
    'long short': '私募·基本面',
    '长短仓': '私募·基本面',
    '基本面私募': '私募·基本面',

    # ===== 量化 =====
    '量化': '量化',
    '量化研究': '量化',
    '量化私募': '量化',
    '公募量化': '量化',
    '量化对冲': '量化',
    '量化策略': '量化',
    'quant': '量化',
    'quantitative': '量化',
    'quant research': '量化',
    'quant researcher': '量化',
    '做市': '量化',
    'market making': '量化',
    '高频交易': '量化',
    '中高频': '量化',
    '因子研究': '量化',
    'alpha research': '量化',

    # ===== 卖方研究 =====
    '卖方': '卖方研究',
    '卖方研究': '卖方研究',
    '券商研究所': '卖方研究',
    '研究所': '卖方研究',
    '行业首席': '卖方研究',
    '首席助理': '卖方研究',
    'equity research': '卖方研究',
    'sell-side': '卖方研究',
    'sell side': '卖方研究',
    'sell-side research': '卖方研究',
    'sell side research': '卖方研究',
    'research analyst': '卖方研究',
    'research associate': '卖方研究',
    '外资行研究': '卖方研究',
    '外资研究部': '卖方研究',
    '新财富': '卖方研究',
    # backward-compat 老 canon 名
    '卖方研究·S&T': '卖方研究',

    # ===== S&T·FICC·衍生品 =====
    's&t': 'S&T·FICC·衍生品',
    'S&T': 'S&T·FICC·衍生品',
    '销售交易': 'S&T·FICC·衍生品',
    'sales and trading': 'S&T·FICC·衍生品',
    'sales & trading': 'S&T·FICC·衍生品',
    'ficc': 'S&T·FICC·衍生品',
    'FICC': 'S&T·FICC·衍生品',
    'global markets': 'S&T·FICC·衍生品',
    'gbm': 'S&T·FICC·衍生品',
    'GBM': 'S&T·FICC·衍生品',
    '机构销售': 'S&T·FICC·衍生品',
    '债券交易': 'S&T·FICC·衍生品',
    '外汇交易': 'S&T·FICC·衍生品',
    '衍生品': 'S&T·FICC·衍生品',
    '衍生品销售': 'S&T·FICC·衍生品',
    '结构化产品': 'S&T·FICC·衍生品',
    'structuring': 'S&T·FICC·衍生品',
    'fixed income': 'S&T·FICC·衍生品',
    'rates trader': 'S&T·FICC·衍生品',
    'fx trader': 'S&T·FICC·衍生品',

    # ===== 投行·并购·资本市场 =====
    'ibd': '投行·并购·资本市场',
    'IBD': '投行·并购·资本市场',
    '投行': '投行·并购·资本市场',
    '投资银行': '投行·并购·资本市场',
    '投行部': '投行·并购·资本市场',
    'fa': '投行·并购·资本市场',
    '财务顾问': '投行·并购·资本市场',
    'm&a': '投行·并购·资本市场',
    'M&A': '投行·并购·资本市场',
    '兼并收购': '投行·并购·资本市场',
    '并购': '投行·并购·资本市场',
    '外资投行': '投行·并购·资本市场',
    'investment banking': '投行·并购·资本市场',
    'investment bank': '投行·并购·资本市场',
    'i-bank': '投行·并购·资本市场',
    'i bank': '投行·并购·资本市场',
    'leveraged finance': '投行·并购·资本市场',
    'lev fin': '投行·并购·资本市场',
    'ecm': '投行·并购·资本市场',
    'ECM': '投行·并购·资本市场',
    'equity capital markets': '投行·并购·资本市场',
    'dcm': '投行·并购·资本市场',
    'DCM': '投行·并购·资本市场',
    'debt capital markets': '投行·并购·资本市场',
    'capital markets': '投行·并购·资本市场',
    '资本市场部': '投行·并购·资本市场',
    'ipo': '投行·并购·资本市场',
    'IPO': '投行·并购·资本市场',
    # backward-compat 老 canon 名
    '一级市场': '投行·并购·资本市场',

    # ===== 一级股权·PE/VC =====
    'pe': '一级股权·PE/VC',
    'PE': '一级股权·PE/VC',
    'vc': '一级股权·PE/VC',
    'VC': '一级股权·PE/VC',
    'private equity': '一级股权·PE/VC',
    'venture capital': '一级股权·PE/VC',
    'pe fund': '一级股权·PE/VC',
    'vc fund': '一级股权·PE/VC',
    'pe/vc': '一级股权·PE/VC',
    'PE/VC': '一级股权·PE/VC',
    '一级 pe': '一级股权·PE/VC',
    'buyout': '一级股权·PE/VC',
    'growth equity': '一级股权·PE/VC',
    'growth fund': '一级股权·PE/VC',
    '股权投资': '一级股权·PE/VC',
    '私募股权': '一级股权·PE/VC',
    '风险投资': '一级股权·PE/VC',
    '产业基金': '一级股权·PE/VC',
    '战略投资': '一级股权·PE/VC',
    'cvc': '一级股权·PE/VC',
    'CVC': '一级股权·PE/VC',
    'corporate venture': '一级股权·PE/VC',

    # ===== 银行·总行核心 (扩范围: 政策行 + 外管 + 交易所 + 金融基础设施) =====
    '银行': '银行·总行核心',
    '银行总行': '银行·总行核心',
    '总行': '银行·总行核心',
    '总行管培': '银行·总行核心',
    '管培': '银行·总行核心',
    '管培生': '银行·总行核心',
    '股份行': '银行·总行核心',
    '股份制银行': '银行·总行核心',
    '综合金融': '银行·总行核心',
    'fmt': '银行·总行核心',
    '国有大行': '银行·总行核心',
    '城商行': '银行·总行核心',
    '城商': '银行·总行核心',
    '农商行': '银行·总行核心',
    '外资行': '银行·总行核心',
    '私行': '银行·总行核心',
    'pwm': '银行·总行核心',
    'corporate banking': '银行·总行核心',
    'management trainee': '银行·总行核心',
    'banking trainee': '银行·总行核心',
    'hq trainee': '银行·总行核心',
    # 政策行 / 外管 / 交易所 / 金融基础设施 (Q1 共识: 从监管搬过来)
    '政策行': '银行·总行核心',
    '国开行': '银行·总行核心',
    '国开': '银行·总行核心',
    '进出口银行': '银行·总行核心',
    '农发行': '银行·总行核心',
    '外管局': '银行·总行核心',
    '国家外汇管理局': '银行·总行核心',
    '中央外汇业务中心': '银行·总行核心',
    '外汇交易中心': '银行·总行核心',
    '交易所': '银行·总行核心',
    '上交所': '银行·总行核心',
    '深交所': '银行·总行核心',
    '北交所': '银行·总行核心',
    '中证登': '银行·总行核心',
    '上清所': '银行·总行核心',
    '金融基础设施': '银行·总行核心',

    # ===== 监管·体制内 (缩范围) =====
    '监管': '监管·体制内',
    '证监会': '监管·体制内',
    '央行': '监管·体制内',
    '人民银行': '监管·体制内',
    '银保监': '监管·体制内',
    '金融监管局': '监管·体制内',
    '国家金融监管': '监管·体制内',
    '国央企': '监管·体制内',
    '国企': '监管·体制内',
    '央企': '监管·体制内',
    '体制内': '监管·体制内',
    '考公': '监管·体制内',
    '公务员': '监管·体制内',
    '中投': '监管·体制内',
    '中投公司': '监管·体制内',
    '中央汇金': '监管·体制内',
    '社保理事会': '监管·体制内',
    '社保基金': '监管·体制内',
    '主权基金': '监管·体制内',
    '国资委': '监管·体制内',
    '国务院国资委': '监管·体制内',

    # ===== 金融科技 =====
    '金融科技': '金融科技',
    '金融科技子公司': '金融科技',
    '金融科技部': '金融科技',
    'fintech': '金融科技',
    'FinTech': '金融科技',
    '金科': '金融科技',
    '互金': '金融科技',
    '互联网金融': '金融科技',
    '蚂蚁': '金融科技',
    '微众': '金融科技',
    '京东数科': '金融科技',
    '京东金融': '金融科技',
    '度小满': '金融科技',
    '跨境支付': '金融科技',
    'wind': '金融科技',
    'Wind': '金融科技',
    '同花顺': '金融科技',
    '东方财富': '金融科技',
    '反欺诈': '金融科技',
    '风控建模': '金融科技',
    '智能投顾': '金融科技',

    # ===== 咨询·MBB+Tier2 =====
    'mbb': '咨询·MBB+Tier2',
    'MBB': '咨询·MBB+Tier2',
    '麦肯锡': '咨询·MBB+Tier2',
    'mckinsey': '咨询·MBB+Tier2',
    'McKinsey': '咨询·MBB+Tier2',
    'bcg': '咨询·MBB+Tier2',
    'BCG': '咨询·MBB+Tier2',
    'boston consulting': '咨询·MBB+Tier2',
    'bain': '咨询·MBB+Tier2',
    'Bain': '咨询·MBB+Tier2',
    '管理咨询': '咨询·MBB+Tier2',
    '金融咨询': '咨询·MBB+Tier2',
    '战略咨询': '咨询·MBB+Tier2',
    'strategy consulting': '咨询·MBB+Tier2',
    '罗兰贝格': '咨询·MBB+Tier2',
    'roland berger': '咨询·MBB+Tier2',
    'oliver wyman': '咨询·MBB+Tier2',
    '科尔尼': '咨询·MBB+Tier2',
    'kearney': '咨询·MBB+Tier2',
    'lek': '咨询·MBB+Tier2',
    'l.e.k.': '咨询·MBB+Tier2',
    '四大': '咨询·MBB+Tier2',
    '审计': '咨询·MBB+Tier2',
    '财务咨询': '咨询·MBB+Tier2',
    'fdd': '咨询·MBB+Tier2',
    'cdd': '咨询·MBB+Tier2',
    'tier 2 consulting': '咨询·MBB+Tier2',
    'tier-2 consulting': '咨询·MBB+Tier2',
    '战略咨询·金融': '咨询·MBB+Tier2',
    'business analyst': '咨询·MBB+Tier2',
    # backward-compat 老 canon 名
    '管理咨询·MBB': '咨询·MBB+Tier2',

    # ===== 企业战略·管培·实业金融 =====
    '企业战略': '企业战略·管培·实业金融',
    '战略': '企业战略·管培·实业金融',
    '战略组': '企业战略·管培·实业金融',
    '战略部': '企业战略·管培·实业金融',
    '战略发展': '企业战略·管培·实业金融',
    '战略规划': '企业战略·管培·实业金融',
    '战略与投资': '企业战略·管培·实业金融',
    '战投': '企业战略·管培·实业金融',
    '公司战略': '企业战略·管培·实业金融',
    'strategy': '企业战略·管培·实业金融',
    'corp dev': '企业战略·管培·实业金融',
    'corporate development': '企业战略·管培·实业金融',
    'corporate strategy': '企业战略·管培·实业金融',
    '实业管培': '企业战略·管培·实业金融',
    '实业金融': '企业战略·管培·实业金融',
    '产业金融': '企业战略·管培·实业金融',
    '产业战略': '企业战略·管培·实业金融',
    '通用咨询': '企业战略·管培·实业金融',
    '互联网战略': '企业战略·管培·实业金融',
    '阿里战略': '企业战略·管培·实业金融',
    '美团战略': '企业战略·管培·实业金融',
    '字节战略': '企业战略·管培·实业金融',
    '腾讯战略': '企业战略·管培·实业金融',

    # ===== 大宗·能源 =====
    '大宗': '大宗·能源',
    '大宗商品': '大宗·能源',
    'commodity': '大宗·能源',
    'commodities': '大宗·能源',
    '能源': '大宗·能源',
    'energy': '大宗·能源',
    'energy trading': '大宗·能源',
    'power market': '大宗·能源',
    'electricity': '大宗·能源',
    'solar': '大宗·能源',
    'pv': '大宗·能源',
    '石油': '大宗·能源',
    '石化': '大宗·能源',
    '中石油': '大宗·能源',
    '中石化': '大宗·能源',
    '路易达孚': '大宗·能源',
    'ldc': '大宗·能源',
    '嘉吉': '大宗·能源',
    'cargill': '大宗·能源',
    '托克': '大宗·能源',
    'trafigura': '大宗·能源',
    '嘉能可': '大宗·能源',
    'glencore': '大宗·能源',
    'cofco': '大宗·能源',
    '中粮国际': '大宗·能源',
    '远景动力': '大宗·能源',
    'aesc': '大宗·能源',
    '远洋海运': '大宗·能源',
    'cosco': '大宗·能源',
    '航运': '大宗·能源',
    '矿业': '大宗·能源',
    '原油': '大宗·能源',
    '化工': '大宗·能源',
    '燃料油': '大宗·能源',
    '电力': '大宗·能源',
    '电价': '大宗·能源',
    # 注: '电网' 故意不加 — 国家电网/南方电网更近 SOE 司库/资金 (监管·体制内),
    # 不是能源 trading desk。
}

# 咨询孤词 → 默认归"咨询·MBB+Tier2" (SAIF 学生口语 default)。
# longest-match 保护: '战略咨询' (4字) > '咨询' (2字), 不冲突。
TRACK_ALIASES['咨询'] = '咨询·MBB+Tier2'


# 明确量化信号词 (小写匹配) — 出现即判定为量化意图, 不被 私募/对冲基金 组织词抢走。
# 只收无歧义的量化词; 不含 "策略"/"trader" 等可能属 S&T/其它前台的泛词。
_QUANT_SIGNAL_TOKENS: tuple[str, ...] = (
    '量化', 'quant', 'quantitative', 'alpha', '因子', '高频', '中高频',
    '做市', 'market making',
)


def canonicalize_track(label: str) -> str:
    """把任意 track 文本映射到 13 个 canonical 之一。映射不到就原样返回。

    映射规则 (longest-match-wins):
      1. exact match (忽略大小写) → canon
      2. 收集所有"alias ⊆ label"(forward)命中,按 alias 长度 desc 选最 specific
      3. 没有 forward 命中时,fallback "label ⊆ alias"(reverse),按 alias 长度 asc
      4. 都不命中 → 原样返回 label (不强制改)
    """
    if not label:
        return ''
    label_l = label.lower().strip()
    if not label_l:
        return ''
    # 0. 量化信号优先 — "对冲基金"/"私募" 是组织词, 既可量化也可基本面;
    #    一旦出现明确量化词 (量化/quant/alpha/因子/高频/做市), 学生意图就是量化,
    #    必须压过同长的组织词, 否则 longest-match 平局会按 alias 顺序错落到 私募·基本面。
    #    边界: 不含量化词的 "对冲基金" 单独出现仍走下方常规映射 (→ 私募·基本面)。
    for q in _QUANT_SIGNAL_TOKENS:
        if q in label_l:
            return '量化'
    # 1. exact match
    for alias, canon in TRACK_ALIASES.items():
        if alias.lower() == label_l:
            return canon
    # 2 / 3. forward (alias ⊆ label) vs reverse (label ⊆ alias)
    forward_hits: list[tuple[int, str]] = []
    reverse_hits: list[tuple[int, str]] = []
    for alias, canon in TRACK_ALIASES.items():
        a_l = alias.lower()
        if a_l in label_l:
            forward_hits.append((len(a_l), canon))
        elif label_l in a_l:
            reverse_hits.append((len(a_l), canon))
    if forward_hits:
        forward_hits.sort(key=lambda x: -x[0])
        return forward_hits[0][1]
    if reverse_hits:
        reverse_hits.sort(key=lambda x: x[0])
        return reverse_hits[0][1]
    return label


# 伞概念 (umbrella) — 学生 raw 偏好不一定是 13 canonical 之一,可能是
# "投研" / "买方" / "前台" 跨多个 canonical 的伞名。expand 到所有相关 canonical。
_UMBRELLA_EXPANSION: dict[str, tuple[str, ...]] = {
    '投研': (
        '公募/资管·投研', '私募·基本面', '卖方研究', '量化',
        '投行·并购·资本市场', '一级股权·PE/VC',
    ),
    '研究': ('公募/资管·投研', '私募·基本面', '卖方研究'),
    '买方': ('公募/资管·投研', '私募·基本面', '量化'),
    '卖方': ('卖方研究', 'S&T·FICC·衍生品'),
    '一级': ('投行·并购·资本市场', '一级股权·PE/VC'),
    '二级': (
        '公募/资管·投研', '私募·基本面', '量化',
        '卖方研究', 'S&T·FICC·衍生品',
    ),
    '前台': (
        '公募/资管·投研', '私募·基本面', '卖方研究', 'S&T·FICC·衍生品',
        '投行·并购·资本市场', '一级股权·PE/VC', '量化',
    ),
}


# 跳板 / 可迁移赛道 — SAIF 学生视角的合理 lateral 跳点。
# e.g. MBB FS / 四大 FDD 通常 2-3 年后跳 PE;银行总行投行/FICC 跟一级 / S&T 接近。
TRANSFERABLE_FOR_UMBRELLA: dict[str, tuple[str, ...]] = {
    '投研': ('咨询·MBB+Tier2', '银行·总行核心'),
    '研究': ('咨询·MBB+Tier2', '企业战略·管培·实业金融'),
    '买方': ('咨询·MBB+Tier2', '银行·总行核心'),
    '卖方': ('银行·总行核心', '咨询·MBB+Tier2'),
    '一级': ('咨询·MBB+Tier2', '企业战略·管培·实业金融', '银行·总行核心'),
    '二级': ('咨询·MBB+Tier2',),
    '前台': ('咨询·MBB+Tier2', '企业战略·管培·实业金融', '银行·总行核心'),
}


def expand_track_to_canonicals(label: str) -> list[str]:
    """学生 raw 偏好 → 一组 canonical track。

    顺序:伞展开 > exact alias > substring alias > 原样返回 (空列表)。
    """
    if not label:
        return []
    label_l = label.lower().strip()
    if not label_l:
        return []
    # 1. 伞概念优先 (1→N 映射)
    for umbrella, canons in _UMBRELLA_EXPANSION.items():
        if umbrella.lower() == label_l:
            return list(canons)
    # 2. canonical 自身
    for canon in CANONICAL_FINANCE_TRACKS:
        if canon.lower() == label_l:
            return [canon]
    # 3. alias 映射 (单 canonical)
    canon = canonicalize_track(label)
    if canon in CANONICAL_FINANCE_TRACKS:
        return [canon]
    return []


def transferable_for(label: str) -> list[str]:
    """学生 raw 偏好 → 一组可迁移 canonical。映射不到的 label 返空 list。"""
    if not label:
        return []
    label_l = label.lower().strip()
    for umbrella, canons in TRANSFERABLE_FOR_UMBRELLA.items():
        if umbrella.lower() == label_l:
            return list(canons)
    return []


def aliases_for_canonical(canon: str) -> list[str]:
    """canonical → 所有映射到它的 alias 列表 (含自身)。"""
    if not canon:
        return []
    out = [canon]
    out.extend(a for a, c in TRACK_ALIASES.items() if c == canon)
    return out


# 召回宽 keyword — 严格 alias (TRACK_ALIASES) 是长词("行业研究员"/"量化研究"),
# 但 NULL 库的 job_title 用的是 stem 词("证券投资研究员"/"量化策略研究员")。
# 这套 keyword 给 _filter_candidate_jobs 的 NULL fallback substring 用。
# 会带误召回 (e.g. "AI 算法研究员"),但下游 _track_mismatch_penalty 二次校正,
# 不进入 top 推荐。
RECALL_HINTS_PER_CANONICAL: dict[str, tuple[str, ...]] = {
    '公募/资管·投研': (
        '研究员', '行业研究', '行研',
        '投资经理', '基金经理', '组合管理',
        '权益投资', '股票投资', '固收投资', '债券投资',
        '基本面', 'fof', '资管', '理财子', '保险资管', '券商资管',
    ),
    '私募·基本面': (
        '私募', '阳光私募', '对冲基金', '长短仓', '私募研究员',
        '深度研究', 'hedge',
    ),
    '量化': (
        '量化', '高频', '做市', 'quant', 'trader',
        '策略研究', '算法交易', '因子', 'alpha',
    ),
    '卖方研究': (
        '研究助理', '行业分析', '策略研究', '宏观研究',
        '固收研究', '总量研究', '研究所', '行业首席',
    ),
    'S&T·FICC·衍生品': (
        's&t', '销售交易', '机构销售', '债券交易',
        '衍生品', 'ficc', 'global markets', '外汇交易',
    ),
    '投行·并购·资本市场': (
        '投行', '投资银行', 'ibd', '并购', 'm&a', 'ipo',
        '资本市场', '财务顾问', '股权融资',
    ),
    '一级股权·PE/VC': (
        'pe', 'vc', '股权投资', '私募股权', '风险投资',
        '投资分析师', '战略投资', '产业基金',
    ),
    '银行·总行核心': (
        '总行', '机构金融', '投行部', '资本市场部',
        '金融市场部', 'ficc', '管培', '管理培训生',
        '同业', '外汇业务',
    ),
    '监管·体制内': (
        '监察', '监管', '审核', '业务岗', '政策研究', '体制内',
    ),
    '金融科技': (
        '金融科技', 'fintech', '互金',
        '风控', '风险管理', '反欺诈', '数据科学家', '风控建模',
    ),
    '咨询·MBB+Tier2': (
        '咨询顾问', '咨询师', 'consultant',
        '尽职调查', '财务尽调', 'fdd', 'cdd',
        '审计师', '高级审计', '战略咨询', 'associate',
    ),
    '企业战略·管培·实业金融': (
        '战略与投资', '战略发展', 'corp dev',
        '战略分析师', '商业分析师', '管培生', '战投',
        '战略部', '战略组',
    ),
    '大宗·能源': (
        '大宗', '能源', '商品研究', '化工', '电力',
        '航运', '燃料', '采购', '套保', '基差',
    ),
}


def recall_keywords_for_canonical(canon: str) -> list[str]:
    """canonical → 召回宽 keyword (含 strict aliases + recall hints)。
    给 _filter_candidate_jobs 的 NULL fallback (job_title substring) 用。
    """
    if not canon:
        return []
    out = set(aliases_for_canonical(canon))
    out.update(RECALL_HINTS_PER_CANONICAL.get(canon, ()))
    # 去掉太短的 (< 3 字符) 避免误命中爆炸
    return [w for w in out if len(w) >= 3]
