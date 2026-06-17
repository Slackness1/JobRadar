"""简历打分 rubric 内容 (B0 起步版)。

8 个固定维度 (6 表层 + 2 金融独有) + 13 canonical 赛道的校准说明。
评判标准按目标赛道校准 —— 同一条 bullet,投研 vs IB 标准不同。
``build_rubric_prompt_block`` 额外叠加 ``track_resume_rubrics`` 表里该赛道
已 ingest 的行 (腾讯批次为主;金融赛道多为空,空则只用静态校准)。

硬原则:rubric 只用来«评判»,不指导改写,更不暗示补数字。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import TrackResumeRubric


# 8 个固定维度。high_signal / low_signal 给 LLM 当锚点。
DIMENSIONS: list[dict] = [
    {
        'key': 'logic', 'name': '逻辑清晰',
        'high_signal': '模块层次分明,每段经历主线清楚,先因后果',
        'low_signal': '流水账、要点堆砌、前后无主线',
    },
    {
        'key': 'star', 'name': 'STAR 应用',
        'high_signal': '情境-任务-行动-结果四要素齐,尤其有可核实的 Result',
        'low_signal': '只写做了什么,缺背景、缺结果',
    },
    {
        'key': 'readability', 'name': '内容可读',
        'high_signal': '句式干净、术语统一、长度克制',
        'low_signal': '口语化、冗长、标点混乱',
    },
    {
        'key': 'completeness', 'name': '内容完整',
        # 注:打分前 redact_profile_for_llm 会抹掉电话/邮箱等联系方式(隐私),
        # 评审根本看不到联系方式 → 这里**不得**把"缺联系方式"当低分信号,
        # 否则对每份简历恒误报(轮次9 实测 profile 实有 phone+email 仍被扣"缺联系方式")。
        'high_signal': '教育/经历/技能要素齐全,时间线完整,关键信息不缺',
        'low_signal': '缺时间线、经历只有标题没内容、关键段落留空',
    },
    {
        'key': 'expression', 'name': '专业表达',
        'high_signal': '用目标赛道的专业术语准确描述工作',
        'low_signal': '外行话、泛泛而谈、术语用错',
    },
    {
        'key': 'quantification', 'name': '成果量化',
        'high_signal': '用真实数字/范围/频次量化产出 (规模、提升、覆盖)',
        'low_signal': '全是定性描述,无任何量化锚点',
    },
    # ===== 金融独有 2 维 =====
    {
        'key': 'track_fit', 'name': '赛道匹配度',
        'high_signal': '经历与目标赛道高度对口,核心能力命中赛道要求',
        'low_signal': '经历偏离目标赛道,关键能力缺位',
    },
    {
        'key': 'defensibility', 'name': '佐证充分度',
        'high_signal': '每条声明都有足够支撑——角色边界清楚、数字有机制/出处、技能有项目佐证,经得起追问',
        'low_signal': '声明缺支撑——夸大角色(协助写成主导)、数字来路不明、技能无项目可证,一追就露',
    },
]


# 13 canonical 赛道校准:每个赛道«尤其看重什么»+«常见踩坑»。
# key 必须 ∈ CANONICAL_FINANCE_TRACKS。
TRACK_CALIBRATION: dict[str, str] = {
    '公募/资管·投研': '看重买方研究逻辑、个股/行业深度、独立判断与非共识观点;忌堆量、忌纯卖方腔。',
    '私募·基本面': '看重产业链理解、深度调研、绝对收益视角;忌空泛覆盖、忌只跟卖方。',
    '量化': '看重因子开发全流程、IC/Sharpe/回测口径、工程能力(数据清洗/特征/回测框架);忌只报漂亮数字无方法、忌口径不清。',
    '卖方研究': '看重覆盖深度、报告/路演产出、产业链景气度跟踪;忌只列动作无观点。',
    'S&T·FICC·衍生品': '看重市场敏感度、产品理解(利率/汇率/信用/衍生品)、风险与定价直觉;忌纯学术。',
    '投行·并购·资本市场': '看重交易经验、财务建模/估值、尽调与底稿、信息披露;忌夸大独立完成。',
    '一级股权·PE/VC': '看重行业判断、投资逻辑、尽调与投后、deal sourcing;忌只做执行无判断。',
    '银行·总行核心': '看重对公/风险/资负/政策理解、合规严谨;忌零售柜面化表达。',
    '监管·体制内': '看重政策理解、宏观与体制视角、严谨稳健、文字功底;忌浮夸。',
    '金融科技': '看重技术+金融复合、产品/数据/工程落地、业务价值;忌纯技术堆砌。',
    '咨询·MBB+Tier2': '看重结构化思维、假设驱动、量化论证、客户沟通;忌无框架。',
    '企业战略·管培·实业金融': '看重战略思维、跨部门协作、商业 sense、落地执行;忌空谈。',
    '大宗·能源': '看重产业链/供需基本面、价格驱动、跨资产视角;忌脱离实业。',
}


def _track_rubric_rows(db: Session, track_key: str) -> list[TrackResumeRubric]:
    if not track_key:
        return []
    return (
        db.query(TrackResumeRubric)
        .filter(TrackResumeRubric.track_key == track_key)
        .all()
    )


def build_rubric_prompt_block(target_track: str, db: Session) -> str:
    """渲染 8 维定义 + 该赛道校准 (+ track_resume_rubrics 已有行)。"""
    lines: list[str] = ['【评分维度 (0-100,各维独立打分)】']
    for d in DIMENSIONS:
        lines.append(
            f"- {d['name']} ({d['key']}): 高分=({d['high_signal']});低分=({d['low_signal']})"
        )

    calib = TRACK_CALIBRATION.get(target_track, '')
    if calib:
        lines.append(f'\n【目标赛道校准 · {target_track}】\n{calib}')

    rows = _track_rubric_rows(db, target_track)
    if rows:
        lines.append(f'\n【{target_track} 已沉淀的细化标尺】')
        for r in rows:
            dim = str(r.dimension or '').strip()
            hi = str(r.high_signal or '').strip()
            lo = str(r.low_signal or '').strip()
            if dim:
                lines.append(f'- {dim}: 高={hi};低={lo}')

    return '\n'.join(lines)
