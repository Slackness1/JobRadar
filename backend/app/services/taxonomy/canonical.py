"""8 canonical 金融赛道 + 别名映射。

详见 docs/finance-tracks-2026-overview.md。
"""
from __future__ import annotations


CANONICAL_FINANCE_TRACKS: tuple[str, ...] = (
    '二级买方·基本面',
    '量化',
    '一级市场',
    '卖方研究·S&T',
    '银行·总行核心',
    '监管·体制内',
    '金融科技',
    '金融咨询',
)


# 别名 → canonical 映射 (大小写 / 中英 / 常见变体)。
# 命中规则: alias 跟 input 任一方是另一方子串则匹配。
TRACK_ALIASES: dict[str, str] = {
    # 二级买方·基本面
    '公募': '二级买方·基本面',
    '公募基金': '二级买方·基本面',
    '公募基金/研究': '二级买方·基本面',
    '公募/研究': '二级买方·基本面',
    '主动基金': '二级买方·基本面',
    '私募': '二级买方·基本面',
    '阳光私募': '二级买方·基本面',
    '对冲基金': '二级买方·基本面',
    '二级市场买方': '二级买方·基本面',
    '基本面研究': '二级买方·基本面',
    '行业研究员': '二级买方·基本面',
    '行业研究': '二级买方·基本面',
    '银行理财子': '二级买方·基本面',
    '理财子': '二级买方·基本面',
    '保险资管': '二级买方·基本面',
    '资产管理': '二级买方·基本面',
    '信托': '二级买方·基本面',
    '信托公司': '二级买方·基本面',

    # 量化
    '量化': '量化',
    '量化研究': '量化',
    '量化私募': '量化',
    'quant': '量化',
    'quantitative': '量化',
    '做市': '量化',
    'market making': '量化',
    '高频交易': '量化',

    # 一级市场
    'pe': '一级市场',
    'vc': '一级市场',
    'ibd': '一级市场',
    '投行': '一级市场',
    '投资银行': '一级市场',
    'fa': '一级市场',
    '财务顾问': '一级市场',
    '一级 pe': '一级市场',
    '一级市场': '一级市场',
    'm&a': '一级市场',
    '兼并收购': '一级市场',
    '外资投行': '一级市场',

    # 卖方研究·S&T
    '卖方': '卖方研究·S&T',
    '卖方研究': '卖方研究·S&T',
    '券商研究所': '卖方研究·S&T',
    '研究所': '卖方研究·S&T',
    's&t': '卖方研究·S&T',
    '销售交易': '卖方研究·S&T',
    'sales and trading': '卖方研究·S&T',
    'ficc': '卖方研究·S&T',        # FICC desk 主要在 sell-side / 外资行 S&T,不是 banking

    # 银行·总行核心
    '银行': '银行·总行核心',
    '银行总行': '银行·总行核心',
    '总行': '银行·总行核心',
    '总行管培': '银行·总行核心',
    'fmt': '银行·总行核心',         # bank financial markets trainee
    '国有大行': '银行·总行核心',
    '股份制银行': '银行·总行核心',
    '城商行': '银行·总行核心',
    '城商': '银行·总行核心',
    '农商行': '银行·总行核心',
    '外资行': '银行·总行核心',
    '私行': '银行·总行核心',       # 私人银行,跟营业部理财顾问区分(那个是低质量,被红线兜)
    'pwm': '银行·总行核心',

    # 监管·体制内
    '监管': '监管·体制内',
    '证监会': '监管·体制内',
    '央行': '监管·体制内',
    '人民银行': '监管·体制内',
    '银保监': '监管·体制内',
    '金融监管局': '监管·体制内',
    '交易所': '监管·体制内',
    '上交所': '监管·体制内',
    '深交所': '监管·体制内',
    '国央企': '监管·体制内',
    '国企': '监管·体制内',
    '央企': '监管·体制内',
    '体制内': '监管·体制内',
    '国开': '监管·体制内',
    '中投': '监管·体制内',
    '社保理事会': '监管·体制内',

    # 金融科技
    '金融科技': '金融科技',
    'fintech': '金融科技',
    '金科': '金融科技',        # 学生口语缩写
    '互金': '金融科技',
    '互联网金融': '金融科技',
    '蚂蚁': '金融科技',
    '微众': '金融科技',
    '京东数科': '金融科技',
    '京东金融': '金融科技',
    '度小满': '金融科技',
    '跨境支付': '金融科技',
    'wind': '金融科技',
    '同花顺': '金融科技',
    '东方财富': '金融科技',

    # 金融咨询
    '咨询': '金融咨询',
    'mbb': '金融咨询',
    '麦肯锡': '金融咨询',
    'bcg': '金融咨询',
    'bain': '金融咨询',
    '四大': '金融咨询',
    '审计': '金融咨询',
    '战略咨询': '金融咨询',
    '财务咨询': '金融咨询',
}


def canonicalize_track(label: str) -> str:
    """把任意 track 文本映射到 8 个 canonical 之一。映射不到就原样返回。

    映射规则:
      1. label 跟某 alias 完全相等(忽略大小写) → canon
      2. label 是某 alias 的子串,或 alias 是 label 的子串 → canon
      3. 都不命中 → 原样返回 label (不强制改)
    """
    if not label:
        return ''
    label_l = label.lower().strip()
    if not label_l:
        return ''
    # 1. exact match
    for alias, canon in TRACK_ALIASES.items():
        if alias.lower() == label_l:
            return canon
    # 2. substring (双向)
    for alias, canon in TRACK_ALIASES.items():
        a_l = alias.lower()
        if a_l in label_l or label_l in a_l:
            return canon
    return label


# 伞概念 (umbrella) — 用户输入的 raw 偏好不一定是 8 canonical 之一,可能是
# "投研" / "买方" / "前台" 这种跨多个 canonical 的伞名。expand 到所有相关 canonical
# 让召回 / 错位判定能覆盖到。
_UMBRELLA_EXPANSION: dict[str, tuple[str, ...]] = {
    '投研': ('二级买方·基本面', '卖方研究·S&T', '一级市场', '量化'),
    '研究': ('二级买方·基本面', '卖方研究·S&T'),
    '买方': ('二级买方·基本面', '量化'),
    '卖方': ('卖方研究·S&T',),
    '一级': ('一级市场',),
    '二级': ('二级买方·基本面', '量化', '卖方研究·S&T'),
    '前台': ('二级买方·基本面', '卖方研究·S&T', '一级市场', '量化'),
}


# 跳板 / 可迁移赛道 — 不严格属于伞,但 SAIF 学生视角是合理的 lateral 跳点。
# e.g. MBB FS / 四大 FDD 通常 2-3 年后跳 PE;银行总行投行/FICC 跟一级/S&T 接近。
# 推荐这些岗位不算"硬错位",但 UI 应该角标"可迁移"。
TRANSFERABLE_FOR_UMBRELLA: dict[str, tuple[str, ...]] = {
    '投研': ('金融咨询', '银行·总行核心'),
    '研究': ('金融咨询',),
    '买方': ('金融咨询', '银行·总行核心'),
    '卖方': ('银行·总行核心', '金融咨询'),
    '一级': ('金融咨询', '银行·总行核心'),
    '二级': ('金融咨询',),
    '前台': ('金融咨询', '银行·总行核心'),
}


def expand_track_to_canonicals(label: str) -> list[str]:
    """用户 raw 偏好 → 一组 canonical track。

    顺序:伞展开 > exact alias > substring alias > 原样返回(空列表)。
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
    """用户 raw 偏好 → 一组可迁移 canonical。

    映射不到的 label 返空 list。
    """
    if not label:
        return []
    label_l = label.lower().strip()
    for umbrella, canons in TRANSFERABLE_FOR_UMBRELLA.items():
        if umbrella.lower() == label_l:
            return list(canons)
    return []


def aliases_for_canonical(canon: str) -> list[str]:
    """canonical → 所有映射到它的 alias 列表 (含自身)。

    用作: 严格 alias 匹配 (打分 / canonicalize)。
    """
    if not canon:
        return []
    out = [canon]
    out.extend(a for a, c in TRACK_ALIASES.items() if c == canon)
    return out


# 召回宽 keyword — 严格 alias (TRACK_ALIASES) 是长词("行业研究员"/"量化研究"),
# 但实际 NULL 库的 job_title 用的是 stem 词("证券投资研究员"/"量化策略研究员")。
# 这套 keyword 专门给 _filter_candidate_jobs 的 NULL fallback substring 用。
# 注意:这些 keyword 故意比 TRACK_ALIASES 宽,会带误召回 (e.g. "AI 算法研究员"),
# 但下游 _track_mismatch_penalty 会根据 canonical_track 真实归属再过滤一道,
# 不进入 top 推荐。
RECALL_HINTS_PER_CANONICAL: dict[str, tuple[str, ...]] = {
    '二级买方·基本面': (
        '研究员', '行业研究', '行研',
        '投资经理', '基金经理', '组合管理',
        '权益投资', '股票投资', '固收投资', '债券投资',
        '基本面', 'fof',
    ),
    '量化': (
        '量化', '高频', '做市', 'quant', 'trader',
        '策略研究', '算法交易',
    ),
    '一级市场': (
        '投行', '投资银行', 'ibd', 'analyst',
        '一级', 'm&a', '并购', '私募股权', '风险投资',
        '股权投资',
    ),
    '卖方研究·S&T': (
        '研究助理', '策略研究', '宏观研究', '固收研究',
        '总量研究', '行业分析', 's&t', '销售交易', '机构销售',
    ),
    '银行·总行核心': (
        '总行', '机构金融', '投行部', '资本市场部',
        '金融市场部', 'ficc', '管培', '管理培训生',
    ),
    '监管·体制内': (
        '监察', '监管', '审核', '业务岗',
    ),
    '金融科技': (
        '金融科技', 'fintech', '互金',
        '风控', '风险管理', '反欺诈',
    ),
    '金融咨询': (
        '咨询顾问', '咨询师', 'consultant',
        '尽职调查', '财务尽调', 'fdd',
        '审计师', '高级审计',
    ),
}


def recall_keywords_for_canonical(canon: str) -> list[str]:
    """canonical → 召回宽 keyword (含 strict aliases + recall hints)。

    用作: _filter_candidate_jobs 的 NULL fallback (job_title substring)。
    """
    if not canon:
        return []
    out = set(aliases_for_canonical(canon))
    out.update(RECALL_HINTS_PER_CANONICAL.get(canon, ()))
    # 去掉太短的 (< 3 字符) 避免误命中爆炸
    return [w for w in out if len(w) >= 3]
