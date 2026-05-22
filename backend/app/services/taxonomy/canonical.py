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
    '管理咨询·MBB',     # 2026-05-21 renamed from 金融咨询 (语义更清晰)
    '战略咨询',          # 2026-05-21 拆出 (基于 SAIF 老师反馈 + 2025 MF 报告 McKinsey 等)
    '大宗·能源',         # 2026-05-21 加 (2025 MF: LDC / Cargill / 托克 / COSCO / 中石油 4-5 家)
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
    # 2026-05-21: 英文 alias — P3/P5 等学生 LLM 输出 "Asset Management" /
    # "Buy-side" / "Equity Long-Only" 等英文
    'asset management': '二级买方·基本面',
    'am': '二级买方·基本面',
    'buy-side': '二级买方·基本面',
    'buy side': '二级买方·基本面',
    'long-only': '二级买方·基本面',
    'long only': '二级买方·基本面',
    'mutual fund': '二级买方·基本面',
    'public fund': '二级买方·基本面',
    'hedge fund': '二级买方·基本面',  # 大部分 HF 算二级买方; 量化 HF 走 quant alias 优先
    'fund research': '二级买方·基本面',
    'fundamental research': '二级买方·基本面',
    'pm assistant': '二级买方·基本面',
    # 2026-05-21: LLM 偶尔在 inferred_tracks 里返"细分行业" (P1 实测返 '消费'
    # / '医药' / '行研') 而不是赛道名。 把主流行业默认 → 二级买方·基本面 (公募
    # 行研在 SAIF MF placement 里占 45%, 最高概率默认)。 学生可以在 confirm 页
    # 改成其它 chip; 总比一个 chip 都没预勾强。
    '行研': '二级买方·基本面',
    '行业研究': '二级买方·基本面',
    '消费': '二级买方·基本面',
    '医药': '二级买方·基本面',
    '医药生物': '二级买方·基本面',
    '生物医药': '二级买方·基本面',
    'tmt': '二级买方·基本面',
    'TMT': '二级买方·基本面',
    '科技': '二级买方·基本面',
    '半导体': '二级买方·基本面',
    '新能源': '二级买方·基本面',
    '能源材料': '二级买方·基本面',  # 跟 '大宗·能源' 区分: 这指股票研究, 不是商品
    '高端制造': '二级买方·基本面',
    '军工': '二级买方·基本面',
    '周期': '二级买方·基本面',

    # 量化
    '量化': '量化',
    '量化研究': '量化',
    '量化私募': '量化',
    '公募量化': '量化',          # P1 (2026-05-22): 修 P6 "公募量化部" — 拆 tie
    '量化对冲': '量化',
    '量化策略': '量化',
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
    # 2026-05-21: 英文 alias — LLM inferred_tracks 经常返英文 (P5 实测), 没
    # 这些 alias 学生 confirm 页一个 chip 都不会预勾, 又看不懂 "一级市场"
    # 就是 IBD, 最后乱选成 MBB / 国企。 命中 ≠ 选定, alias 让 canonicalize
    # 把英文译回中文 canonical。
    'investment banking': '一级市场',
    'investment bank': '一级市场',
    'i-bank': '一级市场',
    'i bank': '一级市场',
    'private equity': '一级市场',
    'venture capital': '一级市场',
    'pe fund': '一级市场',
    'vc fund': '一级市场',
    'leveraged finance': '一级市场',
    'lev fin': '一级市场',
    'ecm': '一级市场',        # equity capital markets
    'dcm': '一级市场',        # debt capital markets

    # 卖方研究·S&T
    '卖方': '卖方研究·S&T',
    '卖方研究': '卖方研究·S&T',
    '券商研究所': '卖方研究·S&T',
    '研究所': '卖方研究·S&T',
    's&t': '卖方研究·S&T',
    '销售交易': '卖方研究·S&T',
    'sales and trading': '卖方研究·S&T',
    'ficc': '卖方研究·S&T',        # FICC desk 主要在 sell-side / 外资行 S&T,不是 banking
    # 2026-05-21: 英文 alias 同 IBD 注释
    'sales & trading': '卖方研究·S&T',
    'global markets': '卖方研究·S&T',  # Goldman GBM = S&T 性质
    'gbm': '卖方研究·S&T',
    'equity research': '卖方研究·S&T',
    'sell-side': '卖方研究·S&T',
    'sell side': '卖方研究·S&T',
    'research analyst': '卖方研究·S&T',
    # P1 (2026-05-22): 修 P1/P2 "外资行研究部" — 不应被 '外资行' 抢去银行
    '外资行研究': '卖方研究·S&T',
    '外资研究部': '卖方研究·S&T',

    # 银行·总行核心
    '银行': '银行·总行核心',
    '银行总行': '银行·总行核心',
    '总行': '银行·总行核心',
    '总行管培': '银行·总行核心',
    '管培': '银行·总行核心',          # P1 (2026-05-22): 修 P4 "股份行管培" / "国有大行总行管培"
    '管培生': '银行·总行核心',
    '股份行': '银行·总行核心',        # P1 (2026-05-22): 修 P4 "股份行管培" — '股份制银行' 字符不同
    '综合金融': '银行·总行核心',      # P1 (2026-05-22): 修 P4 "券商综合金融" (默认银行,SAIF 学生口径)
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
    '金融科技子公司': '金融科技',  # P1 (2026-05-22): 修 P7 "银行金融科技子公司" — 应金科不应银行
    '金融科技部': '金融科技',      # P1 (2026-05-22): 修 P7 "券商金融科技部"
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

    # 管理咨询·MBB (2026-05-21 renamed from 金融咨询)
    'mbb': '管理咨询·MBB',
    '麦肯锡': '管理咨询·MBB',
    'mckinsey': '管理咨询·MBB',
    'bcg': '管理咨询·MBB',
    'bain': '管理咨询·MBB',
    '管理咨询': '管理咨询·MBB',
    '金融咨询': '管理咨询·MBB',  # backward-compat: 老 canonical 名作为 alias
    '四大': '管理咨询·MBB',
    '审计': '管理咨询·MBB',
    '财务咨询': '管理咨询·MBB',
    '战略咨询·金融': '管理咨询·MBB',

    # 战略咨询 (2026-05-21 拆出 — 老师 + 报告口径)
    '战略咨询': '战略咨询',
    '战略': '战略咨询',
    'strategy consulting': '战略咨询',
    'strategy': '战略咨询',
    '战略组': '战略咨询',  # McKinsey 战略组
    '战略部': '战略咨询',
    '公司战略': '战略咨询',
    '战略规划': '战略咨询',
    '通用咨询': '战略咨询',

    # 大宗·能源 (2026-05-21 新增 — 2025 MF 报告头部雇主)
    '大宗': '大宗·能源',
    '大宗商品': '大宗·能源',
    'commodity': '大宗·能源',
    'commodities': '大宗·能源',
    '能源': '大宗·能源',
    'energy': '大宗·能源',
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
    '远景动力': '大宗·能源',  # AESC
    'aesc': '大宗·能源',
    '远洋海运': '大宗·能源',
    'cosco': '大宗·能源',
    '航运': '大宗·能源',
}

# 咨询 (孤词) → 默认归"管理咨询·MBB" — 因 SAIF 学生口语 default,但跟
# canonicalize_track 的子串规则结合可能误触发("咨询" 是 "战略咨询" 子串)。
# 为了控制歧义,arrange order matters: 把"咨询"放最后,避免被前面具体词压住。
TRACK_ALIASES['咨询'] = '管理咨询·MBB'


def canonicalize_track(label: str) -> str:
    """把任意 track 文本映射到 10 个 canonical 之一。映射不到就原样返回。

    映射规则 (2026-05-22 P0 重写,longest-match-wins,修 P2/P6/P7 等
    复合短语被短 alias 劫持的 bug):
      1. exact match (忽略大小写) → canon
      2. 收集所有"alias ⊆ label"(forward)命中,**按 alias 长度 desc** 选最 specific —
         避免 '私募'(短)劫持 '量化私募'(长)→ 量化
      3. 没有 forward 命中时,fallback "label ⊆ alias"(reverse)— **按 alias
         长度 asc** 选最近似(避免用户输 '投' 被 'investment banking' 拐走)
      4. 都不命中 → 原样返回 label (不强制改)
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
    '投研': ('管理咨询·MBB', '银行·总行核心'),
    '研究': ('管理咨询·MBB', '战略咨询'),
    '买方': ('管理咨询·MBB', '银行·总行核心'),
    '卖方': ('银行·总行核心', '管理咨询·MBB'),
    '一级': ('管理咨询·MBB', '战略咨询', '银行·总行核心'),
    '二级': ('管理咨询·MBB',),
    '前台': ('管理咨询·MBB', '战略咨询', '银行·总行核心'),
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
