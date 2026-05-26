import json
import re
from typing import Any, Protocol
from urllib.error import HTTPError
from urllib.error import URLError
from urllib import request

from app.schemas_resume_copilot import (
    ResumeEducationItem,
    ResumeInternshipItem,
    ResumeProfilePayload,
    ResumeProjectItem,
    ResumeSkillsPayload,
)
from app.services.resume_copilot.llm import build_resume_llm_client
from app.services.taxonomy import canonicalize_track


EMAIL_PATTERN = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
PHONE_PATTERN = re.compile(
    r'(?<!\d)(?:\+?\d{1,3}[\s-]?)?(?:1[3-9]\d[\s-]?\d{4}[\s-]?\d{4}|\d{3}[-\s]\d{3,4}[-\s]\d{4})(?!\d)'
)
URL_PATTERN = re.compile(
    r'(?:(?:https?://)?(?:www\.)?)'
    r'(?:github\.com/[A-Za-z0-9_.-]+|linkedin\.com/in/[A-Za-z0-9_.-]+|[A-Za-z0-9.-]+\.[A-Za-z]{2,}/[^\s，,；;|]+)'
)
# 2026-05-22 #114 Phase 2: 支持英文日期格式。原来只匹配 "2024.09 – 2025.12",
# 现在还匹配:
#   "Sep 2024 – Dec 2025" / "September 2024 – Present" / "09/2024 – 12/2025" /
#   "2020 – 2024" (年-年 — 学校经历常用) / "Sep 2024 – Present"
# 注意: 年份限 1900-2099, 不然 "Annual budget 1000 - 2000" 这种 salary range 会
# 被当成 date range, _split_section_entries 误判 entry 边界。
_MONTH_NAME = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*'
_YEAR = r'(?:19|20)\d{2}'        # 1900-2099, 拦 salary/budget false positive
_DATE_ALTS: tuple[str, ...] = (
    rf'{_YEAR}[./-]\d{{1,2}}',       # 2024.09 / 2024-09 / 2024/09
    rf'\d{{1,2}}[./-]{_YEAR}',       # 09/2024
    rf'{_MONTH_NAME}\.?\s+{_YEAR}',  # Sep 2024 / September 2024
    _YEAR,                            # 2024 (孤立年, 学校多年区间用)
)
_DATE_TOKEN = '(?:' + '|'.join(_DATE_ALTS) + ')'
_DATE_END_TOKEN = '(?:' + '|'.join(('至今', 'present', 'now', 'current') + _DATE_ALTS) + ')'
DATE_RANGE_PATTERN = re.compile(
    rf'(?P<start>{_DATE_TOKEN})\s*[–—\-~]\s*(?P<end>{_DATE_END_TOKEN})',
    re.IGNORECASE,
)
BULLET_PREFIX_PATTERN = re.compile(r'^[•·●▪■*-]\s*')
# 2026-05-21: 删了独字母 'C' / 'Go' — 这俩太短, substring match 会在
# "CICC" / "consumer" / "google" / "going" 里全命中, 让每份简历凭空多出
# "C" / "Go" 两个根本不在简历里的技能 (4/8 persona 实测中招)。
# 同时大幅扩充 ML / 金融数据 / 量化 词库 — Worker C 发现 P7/P8 的
# LightGBM / XGBoost / LSTM / Transformer / GraphSAGE 等头部差异化技能
# 全被丢, 这些是 SAIF "深度 > 广度" persona 的命门。
KNOWN_TECH_SKILLS = [
    # languages — 删 'C' / 'Go' (false-positive 高);保留多字母明确的
    'Python', 'Java', 'C++', 'C#', 'Rust', 'JavaScript', 'TypeScript', 'SQL',
    'R语言', 'MATLAB', 'Scala', 'Kotlin', 'Swift', 'PHP', 'Ruby',
    # web
    'React', 'Vue', 'Angular', 'Node.js', 'FastAPI', 'Django', 'Flask', 'Spring',
    # storage
    'MySQL', 'PostgreSQL', 'Redis', 'MongoDB', 'Elasticsearch', 'ClickHouse',
    # infra
    'Docker', 'Kubernetes', 'Airflow', 'Spark', 'Flink', 'Kafka', 'Hadoop', 'Hive',
    # ml frameworks
    'TensorFlow', 'PyTorch', 'scikit-learn', 'XGBoost', 'LightGBM', 'CatBoost',
    'Keras', 'JAX', 'Hugging Face', 'Transformers',
    # ml/dl 概念
    'LSTM', 'Transformer', 'GRU', 'CNN', 'RNN', 'BERT', 'GPT', 'Attention',
    'GraphSAGE', 'GAT', 'GCN', 'DGL', '强化学习',
    '机器学习', '深度学习', '时间序列', '时序模型', '神经网络', '集成学习',
    # 金融 / 量化 specifics
    'Wind', 'Bloomberg', 'Choice', 'iFinD', 'Tushare', 'AKShare',
    'DCF', 'LBO', 'IRR', 'NPV', 'WACC', 'CAPM', 'M&A',
    'Alpha', 'Beta', 'Sharpe', 'Black-Scholes',
    'PVSyst', 'AutoCAD',
    # data
    '数据分析', '数据治理', '爬虫', '后端', '前端', '算法',
]
ROLE_KEYWORDS = [
    'Backend Engineer', 'Frontend Engineer', 'Full Stack Engineer', 'Data Analyst',
    'Data Engineer', 'Machine Learning Engineer', 'Product Manager', 'Operations',
    '后端开发', '前端开发', '全栈开发', '数据分析', '数据工程', '算法工程师', '产品经理', '运营',
]
# 2026-05-22 Round 3 (#114 Phase 2 hardening): TRACK_KEYWORDS 大改
#
# 之前 P1 + AI/金融/PE 短 token 用纯 substring 在简历里到处误命中(`AI` 撞
# `Airflow` / `SAIF` 里的 `ai`,`金融` 撞 `SAIF 投资分析协会`,`PE` 撞
# `PE/EV-EBITDA`)。把 top-3 cap 吃光,真正长 keyword 排在后面被截掉 — 8/8
# SAIF persona heuristic 全部跑错(详见 docs/eval-cn-vs-en-parsing-2026-05-22.md)。
#
# 修法:
#   1. 删 `'AI'` / `'金融'` — 零选择性。中文金融简历里几乎 100% 含 '金融'。
#   2. 短 token 走 `_skill_in()` word-boundary(同 KNOWN_TECH_SKILLS 路径),
#      `'PE'` / `'VC'` / `'IBD'` / `'S&T'` 不会撞 `PE/EV-EBITDA` / `Type`。
#   3. 补 EN gap: Mutual Fund / Buy-side / Long-only / Management Trainee /
#      Corporate Banking / Power Market / Energy / Solar / PV — 配 alias 在
#      `taxonomy/canonical.py`。
#
# 命中顺序: 高精度长 keyword 先 — 先 hit 的优先占满 top-3。
TRACK_KEYWORDS = [
    # —— EN finance — 高精度长 keyword (top-3 优先吃这些) ——
    'Investment Banking', 'Equity Research', 'Sell-side Research',
    'Buy-side Research', 'Buy Side Research',
    'Private Equity', 'Venture Capital', 'Asset Management',
    'Hedge Fund', 'Mutual Fund', 'Long-only', 'Long Only', 'Buy-side', 'Buy Side',
    'Sales and Trading', 'Quantitative',
    'Management Consulting', 'Strategy Consulting',
    'Corporate Banking', 'Management Trainee', 'Banking Trainee', 'HQ Trainee',
    'FinTech',
    'Power Market', 'Energy Trading', 'Commodity', 'Commodities', 'Energy',
    # —— EN finance — 短 acronym (word-boundary 必须) ——
    'IBD', 'PE', 'VC', 'S&T', 'Quant', 'Consulting', 'Solar', 'PV',
    # —— CN finance signals (2026-05-23 重新分组到新 13 canonical) ——
    # canonicalize_track() 用 longest-match-wins, 这里只是给 _token_in_text 拿
    # raw keyword 在简历文本里 substring 命中, 命中后再 canonicalize 归正确赛道。
    '投行', '投资银行', 'IBD',                                  # 投行·并购·资本市场
    'PE/VC',                                                    # 一级股权·PE/VC
    '公募', '资管', '行研', '基金研究',                          # 公募/资管·投研
    '私募', '对冲基金',                                          # 私募·基本面
    '卖方', '研究所', '券商研究',                                # 卖方研究
    'FICC', '销售交易', '衍生品',                                # S&T·FICC·衍生品
    '量化', '高频',                                              # 量化
    '总行', '管培', '股份行', '城商', '综合金融',                # 银行·总行核心
    '监管', '证监', '央行', '体制内',                            # 监管·体制内
    '金融科技', '互金',                                          # 金融科技
    '麦肯锡', '贝恩', 'BCG', '咨询',                             # 咨询·MBB+Tier2
    '战略', '战投',                                              # 企业战略·管培·实业金融
    '大宗', '能源', '石油', '电力', '电价',                      # 大宗·能源
    '互联网',
    'Internet',  # FE generic 兜底
]


# 2026-05-22 P3: 推断学生目标 office 区域 — 用于 confirm 页 pre-fill location chip
# + 推荐时优先该区域岗位。值域固定 4 个: hk / sg / mainland / global
OFFICE_VALUES: set[str] = {'hk', 'sg', 'mainland', 'global'}

# 港新外资 IB / 咨询学生最强信号: 港校 + HK 实习。匹配为小写子串。
HK_HEURISTIC_KEYWORDS: tuple[str, ...] = (
    'hkust', '港科大', '香港科技大学',
    'cuhk', '港中文', '香港中文大学', '中大商学院',
    'hku', '港大', '香港大学',
    'hkbu', '香港浸会',
    'cityu hk', '香港城市大学',
    'hong kong', '香港',
    # 外资 IB / consulting 港岗实习强信号
    'goldman sachs hong kong', 'gs hk', 'morgan stanley hk', 'jpm hk',
    'ubs hk', 'credit suisse hk',
    'hk office', 'based in hong kong',
)

SG_HEURISTIC_KEYWORDS: tuple[str, ...] = (
    'nus', '新加坡国立',
    'ntu', '南洋理工',
    'smu', '新加坡管理大学',
    'singapore', '新加坡',
    'goldman sachs singapore', 'gs sg', 'jpm sg', 'ms singapore',
    'sg office', 'based in singapore',
)

# 中国大陆 — 用作明确的中国院校信号(避免英文简历空 inferred_offices)
MAINLAND_HEURISTIC_KEYWORDS: tuple[str, ...] = (
    '清华', 'tsinghua', '北京大学', 'peking university',
    '复旦', 'fudan', '上海交通大学', 'sjtu', '上海交大',
    '中国人民大学', '人大', '浙江大学', '浙大', 'zhejiang university',
    '南京大学', '中山大学',
    'saif', '高级金融学院',
    'cicc', '中金', '中信证券', '中信建投', '招商证券', '招行',
)


def _is_english_dominant_resume(resume_text: str) -> bool:
    """简历主体是否英文。判断依据:中文字符占英文字符比 < 0.3 视为英文简历。"""
    chinese_chars = sum(1 for c in resume_text if '一' <= c <= '鿿')
    english_chars = sum(1 for c in resume_text if c.isascii() and c.isalpha())
    if english_chars == 0:
        return False
    return chinese_chars / max(english_chars, 1) < 0.3


def _token_in_text(token: str, lowered_text: str) -> bool:
    """Word-boundary-aware substring check for short ASCII tokens.

    短 ASCII token (< 6 字符,e.g. 'PE' / 'VC' / 'AI' / 'ntu') 不能用纯
    substring — 会撞 'PE/EV-EBITDA' / 'intuition' / 'SAIF' 里的 'ai'。长
    token (Equity Research / Hedge Fund) 直接 substring 即可。

    CJK token (含中文字符) 永远走纯 substring — 中文是字符级,没有词边界
    概念,而且 `'管'.isalnum()` 返 True 会让 word boundary check 永假
    (eval 2026-05-22 Round 3: '管培' 在 '招行总行管培' 里被 isalnum 拦)。
    """
    s = token.lower()
    if not s:
        return False
    # CJK 或长 token → 纯 substring。
    has_cjk = any('一' <= c <= '鿿' for c in s)
    if has_cjk or len(s) >= 6:
        return s in lowered_text
    # 短 ASCII token → word boundary check
    idx = 0
    while True:
        pos = lowered_text.find(s, idx)
        if pos < 0:
            return False
        left_ok = pos == 0 or not lowered_text[pos - 1].isalnum()
        right_end = pos + len(s)
        right_ok = right_end == len(lowered_text) or not lowered_text[right_end].isalnum()
        if left_ok and right_ok:
            return True
        idx = pos + 1


def _infer_offices_from_resume_text(resume_text: str) -> list[str]:
    """Heuristic 推断学生目标 office 区域,返 {hk, sg, mainland, global} 子集。

    设计原则(2026-05-22 P3):
      - **没信号就空,不强制 fallback 到 mainland** — 尊重学生空意图
      - **多信号都输出** — 简历同时有清华本科 + Goldman HK 实习 → ['hk', 'mainland']
      - 英文简历主体 + 无明确港新本科 → 加 'global'(可能在求海外 mobility)
      - 'hk'/'sg' 一旦命中,'mainland' 才会跟着出现(意图明显偏港新,弱化 mainland default)
    """
    if not resume_text:
        return []
    text_l = resume_text.lower()
    # 短 token (ntu / nus / hku / smu / sjtu / pwm) 必须走 word-boundary,
    # 否则 'ntu' 撞 'intuition' / 'continuation' (eval 2026-05-22 P3 假阳)。
    hk_hit = any(_token_in_text(kw, text_l) for kw in HK_HEURISTIC_KEYWORDS)
    sg_hit = any(_token_in_text(kw, text_l) for kw in SG_HEURISTIC_KEYWORDS)
    mainland_hit = any(_token_in_text(kw, text_l) for kw in MAINLAND_HEURISTIC_KEYWORDS)
    english_dom = _is_english_dominant_resume(resume_text)

    offices: list[str] = []
    if hk_hit:
        offices.append('hk')
    if sg_hit:
        offices.append('sg')
    if mainland_hit:
        offices.append('mainland')
    # 英文简历但没明确港新院校信号 — 标 global(可能外资 mobility 求职)
    if english_dom and not (hk_hit or sg_hit):
        if 'global' not in offices:
            offices.append('global')
    return offices


def _normalize_offices(value: Any) -> list[str]:
    """清洗 LLM / 用户输入,只保留合法 4 值(hk / sg / mainland / global)。"""
    if not value:
        return []
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        s = str(item).strip().lower()
        # 兼容常见别名
        if s in {'hong kong', '香港', 'hongkong'}:
            s = 'hk'
        elif s in {'singapore', '新加坡'}:
            s = 'sg'
        elif s in {'cn', 'china', '中国', '大陆', 'mainland china'}:
            s = 'mainland'
        elif s in {'overseas', 'international', '海外'}:
            s = 'global'
        if s in OFFICE_VALUES and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _canonicalize_track_list(values: list[str]) -> list[str]:
    """Phase C (2026-05-16): 把 inferred_tracks 里的 free-text 跑 canonicalize_track
    映到 8 canonical(无 mapping 的保留原值,e.g. '互联网' / 'AI' 不属 8 canonical
    但也别丢)。Dedupe 保序。
    """
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        if not v:
            continue
        canon = canonicalize_track(v) or v
        if canon and canon not in seen:
            seen.add(canon)
            out.append(canon)
    return out
# 2026-05-22 #114 Phase 2: SECTION_ALIASES 同时收中英两套 heading。匹配走
# _normalize_section_heading() 做 lowercase + 去 trailing colon, 所以这里写一种
# 形式即可(无需把 EDUCATION / Education / education 重复列)。
SECTION_ALIASES = {
    'summary': {
        '个人介绍', '个人简介', '自我介绍', '自我评价',
        'profile', 'summary', 'professional summary', 'personal summary',
        'about', 'about me', 'objective',
    },
    'education': {
        '教育背景', '教育经历', '教育',
        'education', 'educational background', 'academic background',
        'academic qualifications', 'academics',
    },
    'internships': {
        '实习经历', '工作经历', '职业经历', '实习/工作经历',
        'experience', 'work experience', 'professional experience',
        'internship', 'internships', 'internship experience',
        'employment', 'employment history', 'career',
    },
    'projects': {
        '项目经历', '项目经验', '项目与论文', '项目/论文', '科研项目',
        'projects', 'project experience', 'selected projects',
        'research', 'research projects', 'research experience',
        'publications',
    },
    'skills': {
        '技能与资质', '技能', '专业技能', '技能证书',
        'skills', 'technical skills', 'core skills', 'skills & certifications',
        'certifications', 'languages & tools', 'tools',
    },
}
SECTION_HEADING_ALIASES = {alias for aliases in SECTION_ALIASES.values() for alias in aliases}


def _normalize_section_heading(line: str) -> str:
    """Return a folded form of `line` suitable for SECTION_ALIASES lookup.

    Lowercases, strips trailing colon (en/cn variants) and surrounding
    whitespace so English headings like ``Education:`` / ``EDUCATION`` /
    ``Education`` all collapse to ``education``. Chinese headings unchanged
    (lowercase is a no-op for CJK)."""
    s = (line or '').strip()
    if not s:
        return ''
    # strip trailing : / : / ; / 。 etc.
    s = re.sub(r'[\s:：;；。．\.]+$', '', s)
    return s.lower()
BASIC_INFO_KEY_ALIASES = {
    '姓名': 'name',
    'name': 'name',
    'full_name': 'name',
    'full name': 'name',
    '邮箱': 'email',
    '电子邮箱': 'email',
    'email': 'email',
    'email_address': 'email',
    'email address': 'email',
    '电话': 'phone',
    '手机号': 'phone',
    '手机': 'phone',
    'phone': 'phone',
    'mobile': 'phone',
    'tel': 'phone',
    'github': 'github',
    'github_url': 'github',
    'github url': 'github',
    'git hub': 'github',
    '领英': 'linkedin',
    'linkedin': 'linkedin',
    'linkedin_url': 'linkedin',
    'linkedin url': 'linkedin',
    '个人主页': 'website',
    '个人网站': 'website',
    '作品集': 'website',
    'website': 'website',
    'portfolio': 'website',
    '所在地': 'location',
    '地址': 'location',
    'location': 'location',
    'target_role': 'headline',
    'target role': 'headline',
    'headline': 'headline',
    'title': 'headline',
}
SUMMARY_FACT_KEYWORDS = {
    '教育背景',
    '教育经历',
    '实习经历',
    '工作经历',
    '项目经历',
    '项目经验',
    '专业技能',
    '技能与资质',
    '大学',
    '学院',
    '硕士',
    '本科',
    '博士',
    '学士',
    '专业',
    'GPA',
}


class ResumeParserProvider(Protocol):
    def parse_resume_text(self, resume_text: str) -> Any: ...


class OpenAICompatibleResumeParserProvider:
    def __init__(self, client=None) -> None:
        from app import config
        self.client = client or build_resume_llm_client(
            model=config.RESUME_PARSER_MODEL,
        )

    def parse_resume_text(self, resume_text: str) -> Any:
        # Phase 2 (2026-05-24): pro + reasoning_effort=high。简历上传是 SAIF 演示
        # 第一个 LLM 入口,质量决定后面所有下游。学生愿意等 60-90s 换一份准的解析。
        # max_tokens 升到 16000 留 thinking + 长简历 (50+ bullets) 头空。
        payload = {
            'model': self.client.model,
            'response_format': {'type': 'json_object'},
            'reasoning_effort': 'high',
            'max_tokens': 16000,
            'stream': True,
            'stream_options': {'include_usage': True},
            'messages': [
                {
                    'role': 'system',
                    'content': (
                        'Extract the resume into JSON with keys: basic_info, education, '
                        'internships, projects, skills, languages, awards, '
                        'candidate_summary, inferred_roles, inferred_tracks, '
                        'inferred_offices.\n'
                        # 2026-05-22 #114 Phase 2: 简历语言可能中/英任意一种,
                        # 或中英混合 (大陆 SAIF 学生申港新外资经常有英文 bullet)。
                        # LLM 必须按原文语言 extract,不要翻译。中文 bullet 保留中文,
                        # 英文 bullet 保留英文,bullets 数组里允许同时存在两种语言。
                        'The resume may be written in Chinese, English, or a mix. '
                        'Extract every field verbatim in the original language — '
                        'NEVER translate. A bullets[] entry may be Chinese or English; '
                        'keep it as written.\n'
                        # 2026-05-22 P3: inferred_offices 推断学生目标 office 区域,值域固定
                        # 4 个: "hk" / "sg" / "mainland" / "global"。多信号都输出(e.g.
                        # 清华本 + Goldman HK 实习 → ["hk", "mainland"])。
                        # 判断依据(综合权重):
                        #   - 港校 (HKUST/CUHK/HKU/港中文/港大) → "hk"
                        #   - 新校 (NUS/NTU/SMU) → "sg"
                        #   - 港 office 实习 (Goldman HK / GS HK / JPM HK / 等) → "hk"
                        #   - 新 office 实习 (GS SG / JPM SG 等) → "sg"
                        #   - 清华 / 北大 / 复旦 / 上交 / SAIF / 内资 IB 实习 → "mainland"
                        #   - 简历主体英文 + 多国经历 + 无明确港新院校 → "global"
                        # 没明确信号就空数组 [] — 不要强制 fallback 到 mainland。
                        'For inferred_offices: detect the student\'s target office region(s) '
                        'from their resume. Output a JSON array containing any subset of '
                        '["hk", "sg", "mainland", "global"]. Multiple signals → multiple items. '
                        'No clear signal → empty array [].\n'
                        'Put contact facts only in basic_info using normalized keys '
                        'name, email, phone, github, linkedin, website, location, headline.\n'
                        'For every education item output all of: school, degree, major, '
                        'start_date, end_date, highlights (list of bullet strings such as '
                        'core courses / GPA / honours). Do not leave school or dates blank '
                        'when the resume text contains them.\n'
                        'For every internship item output all of: company, role, start_date, '
                        'end_date, bullets (list of strings — copy each bullet from the resume '
                        'verbatim, preserve every one of them, do not summarize, do not merge, '
                        'do not cap the count).\n'
                        # #1 (2026-05-21): SAIF P7 实测 LLM 把 "AB 测试 …" 和
                        # "做了一些数据维护工作" 两个独立 bullet 合并成一条,  下游
                        # 改写测试整个失效。 用 - / • / ● / ▪ / * 或换行后的首字符
                        # 作为 bullet 边界, 即使一条只有 5 个字也独立出条目。
                        'Bullet boundary rule (STRICT): in the source text, each line that '
                        'starts with `-` / `•` / `●` / `▪` / `*` / a number prefix `1.`/`(1)`, '
                        'OR each blank-line-separated paragraph inside the bullets region, '
                        'is one logical bullet. NEVER concatenate two source lines into one '
                        'bullets[] entry even if the second is short ("做了一些 X" 也独立成条). '
                        'NEVER drop a short bullet because it looks like padding.\n'
                        'For every project item output all of: name, role, tech_stack (list), '
                        'bullets (list of strings — copy each bullet from the resume verbatim, '
                        'preserve every one of them, do not summarize, do not merge, do not cap '
                        'the count).\n'
                        # 2026-05-21: SAIF persona eval 发现 LLM 经常把头部技能词
                        # (LightGBM / XGBoost / LSTM / Transformer / GraphSAGE 等)
                        # summarize 成 "Python / SQL", 摧毁学生差异化。这条 prompt
                        # 是 non-negotiable。Round 2 收紧: 单 term 不带描述。
                        'For skills.technical / skills.tools: copy EVERY technical term '
                        'verbatim from the resume\'s skill section. Do NOT collapse 类别 '
                        '("机器学习") to omit the specific tools beneath it. Each item is '
                        'a single skill name (e.g. "LightGBM", "XGBoost", "LSTM", '
                        '"Transformer", "时间序列分析"). Do not add skills that are not '
                        'mentioned in the source text — no defaults, no inferences. '
                        'skills.tools must be a LIST of strings, never a single concatenated '
                        'string.\n'
                        # Round 2 (2026-05-21): LLM 把 "Python (3 年实战经验)" 拆出来
                        # 放成两个 skill ("Python" 和 "3 年实战经验"), FE 渲染"技能:
                        # 3 年实战经验" 像废话。明确禁止带描述/年限/级别。
                        'Each skill item MUST be a single noun (e.g. "Python", "Wind") — '
                        'NOT a phrase with year ("3 年实战经验"), level ("高级用法"), '
                        'context ("窗口函数"), or count. Strip parentheses content. '
                        'If the resume says "Python (3 年实战经验, 熟练 pandas/numpy)", '
                        'output ["Python", "pandas", "numpy"] — NEVER include "3 年实战经验" '
                        'or "熟练 pandas/numpy".\n'
                        'Dates should be in the resume original format (e.g. "2024.09 – 2025.12").\n'
                        'Do not put education, contact details, dates, projects, skills, '
                        'or work-history facts into candidate_summary. candidate_summary '
                        'should only contain an explicit personal introduction or self-evaluation; '
                        'leave it empty if the resume does not have one.'
                    ),
                },
                {'role': 'user', 'content': resume_text},
            ],
        }
        req = request.Request(
            self.client.chat_completions_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {self.client.api_key}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        # Streaming mode: accumulate SSE chunks so each recv() arrives quickly,
        # avoiding long silent-wait timeouts on large JSON outputs.
        chunks: list[str] = []
        usage_obj: dict | None = None
        with request.urlopen(req, timeout=self.client.timeout_seconds) as response:
            for raw_line in response:
                line = raw_line.decode('utf-8').strip()
                if not line.startswith('data:'):
                    continue
                data = line[len('data:'):].strip()
                if data == '[DONE]':
                    break
                try:
                    event = json.loads(data)
                    if isinstance(event.get('usage'), dict):
                        usage_obj = event['usage']  # final chunk carries usage
                    choices = event.get('choices') or []
                    if choices:
                        delta = choices[0].get('delta', {})
                        token = delta.get('content') or ''
                        if token:
                            chunks.append(token)
                except (KeyError, json.JSONDecodeError):
                    continue
        if usage_obj:
            try:
                from app.services.llm_quota import record_usage_from_response_for_current
                record_usage_from_response_for_current('resume_parse', {'usage': usage_obj})
            except Exception:
                pass
        content = ''.join(chunks)
        return json.loads(content)


def is_resume_parser_upstream_http_error(exc: Exception) -> bool:
    if isinstance(exc, HTTPError):
        return True
    if isinstance(exc, URLError):
        reason = getattr(exc, 'reason', None)
        return isinstance(reason, TimeoutError) or 'timed out' in str(reason).lower()
    if isinstance(exc, ValueError) and 'RESUME_COPILOT_LLM_API_KEY is not configured' in str(exc):
        return True
    return isinstance(exc, TimeoutError)


def _clean_line(value: str) -> str:
    return re.sub(r'\s+', ' ', BULLET_PREFIX_PATTERN.sub('', value or '')).strip()


def _normalize_line_preserve_bullet(value: str) -> str:
    return re.sub(r'\s+', ' ', value or '').strip()


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        result.append(cleaned)
        seen.add(cleaned)
    return result


def _split_text_items(value: str) -> list[str]:
    items: list[str] = []
    buffer: list[str] = []
    depth = 0

    for char in value:
        if char in '([{（':
            depth += 1
        elif char in ')]}）' and depth > 0:
            depth -= 1

        if depth == 0 and char in '\n,;；、':
            item = _clean_line(''.join(buffer))
            if item:
                items.append(item)
            buffer = []
            continue

        buffer.append(char)

    tail = _clean_line(''.join(buffer))
    if tail:
        items.append(tail)
    return items


# R2-3 (2026-05-21): LLM 给 skills.technical 时偶尔会塞 "3 年实战经验" / "熟练
# 窗口函数" 这类描述短语。 prompt 已经收紧, 这里再做一道后处理:
#   - 剥括号内容: "Python (3 年)" → "Python"
#   - 丢弃含数字 + 年/年限/月/经验/级 的整条
#   - 丢弃以"熟练 / 精通 / 掌握 / 了解 / 使用"开头的描述句
#   - 丢弃超过 25 字符的(技能名几乎不会这么长)
_SKILL_PAREN_RE = re.compile(r'[\(（].*?[\)）]')
# 描述性后缀 (年限 / 级 / 熟练度 / 用法 / 应用 / 实战) — 出现这些就剥掉对应段
_SKILL_DESCRIPTOR_SUFFIX_RE = re.compile(
    r'\s*(?:'
    r'\d+\s*(?:年|月|周|个月|年限|年实战|年经验)|'
    r'(?:高级|初级|中级)\s*用法|'
    r'(?:实战|经验|用法|应用|基础|入门|进阶|熟练度)'
    r')\s*.*$'
)
# 描述句开头 — "熟练 X" / "精通 X" 整条丢
_SKILL_DESCRIPTOR_PREFIX_RE = re.compile(r'^(?:熟练|精通|掌握|了解|使用|掌握)')


def _clean_skill_items(items: list[str]) -> list[str]:
    """R3-3 (2026-05-21): + case-insensitive dedup — "pytorch" 和 "PyTorch"
    应该合并 (保留首次出现的 casing); 同时把 tools 的 long string + split parts
    并存的情况通过 split + dedup 自然解决。
    """
    out: list[str] = []
    seen_lower: set[str] = set()
    for raw in items:
        s = _SKILL_PAREN_RE.sub('', raw or '').strip()
        if not s:
            continue
        # 先按 + / / 、 , 拆成 sub-parts,  再逐个 validate (顺序很重要 —
        # 整条 "Bloomberg + Wind + Choice 高级用法" 整体长度超 25 会被误丢)
        for part in re.split(r'[+/、,，]\s*', s):
            part = part.strip()
            # 剥尾巴的描述后缀 ("Choice 高级用法" → "Choice")
            part = _SKILL_DESCRIPTOR_SUFFIX_RE.sub('', part).strip()
            if not part or len(part) > 25:
                continue
            if _SKILL_DESCRIPTOR_PREFIX_RE.match(part):
                continue
            key = part.lower()
            if key in seen_lower:
                continue
            seen_lower.add(key)
            out.append(part)
    return out


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _dedupe_preserve_order(_split_text_items(value))
    if not isinstance(value, list):
        return []

    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            cleaned = _clean_line(item)
            if cleaned:
                result.append(cleaned)
            continue
        if isinstance(item, dict):
            language = _clean_line(str(item.get('language', '') or item.get('name', '')))
            proficiency = _clean_line(str(item.get('proficiency', '') or item.get('level', '')))
            if language and proficiency:
                result.append(f'{language} ({proficiency})')
            elif language:
                result.append(language)
            else:
                flattened = ' '.join(_clean_line(str(part)) for part in item.values() if _clean_line(str(part)))
                if flattened:
                    result.append(flattened)
    return _dedupe_preserve_order(result)


# R3 (2026-05-21): LLM 在缺字段时偶尔返回字符串 "None" / "null" / "N/A" 而不是
# omit 这个 key, 下游 UI 会渲染 "电话: None" 这种废话。 这里统一过滤。
_BASIC_INFO_NULLISH = {'none', 'null', 'n/a', 'na', '-', '—', '无', '不详', '未提供'}


def _normalize_basic_info(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, raw_value in value.items():
        cleaned_key = str(key).strip()
        normalized_key = BASIC_INFO_KEY_ALIASES.get(cleaned_key, BASIC_INFO_KEY_ALIASES.get(cleaned_key.lower(), cleaned_key))
        cleaned_value = _clean_line(str(raw_value))
        # R3 过滤 "None" 类 nullish value, 不写入 dict
        if cleaned_value.lower() in _BASIC_INFO_NULLISH:
            continue
        if normalized_key and cleaned_value:
            normalized[normalized_key] = cleaned_value
    return normalized


def _normalize_contact_url(value: str) -> str:
    cleaned = _clean_line(value).strip('.,;；，')
    return re.sub(r'^https?://', '', cleaned)


def _extract_contact_info(resume_text: str) -> dict[str, str]:
    contact: dict[str, str] = {}

    email_match = EMAIL_PATTERN.search(resume_text)
    if email_match:
        contact['email'] = email_match.group(0)

    phone_match = PHONE_PATTERN.search(resume_text)
    if phone_match:
        contact['phone'] = _clean_line(phone_match.group(0))

    for match in URL_PATTERN.finditer(resume_text):
        url = _normalize_contact_url(match.group(0))
        lowered = url.lower()
        if 'github.com/' in lowered and 'github' not in contact:
            contact['github'] = url
        elif 'linkedin.com/in/' in lowered and 'linkedin' not in contact:
            contact['linkedin'] = url
        elif 'website' not in contact:
            contact['website'] = url

    return contact


def _is_structured_fact_fragment(value: str) -> bool:
    cleaned = _clean_line(value)
    if not cleaned:
        return True
    if cleaned in SECTION_HEADING_ALIASES:
        return True
    if EMAIL_PATTERN.search(cleaned) or PHONE_PATTERN.search(cleaned) or URL_PATTERN.search(cleaned):
        return True
    if DATE_RANGE_PATTERN.search(cleaned):
        return True
    return any(keyword in cleaned for keyword in SUMMARY_FACT_KEYWORDS)


def _sanitize_candidate_summary(value: str) -> str:
    cleaned = _clean_line(value)
    if not cleaned:
        return ''

    fragments = [_clean_line(part) for part in re.split(r'[\n|]+', value) if _clean_line(part)]
    if not fragments:
        return ''

    kept = [fragment for fragment in fragments if not _is_structured_fact_fragment(fragment)]
    return '；'.join(kept)[:500]


def _candidate_summary_or_empty(value: str, basic_info: dict[str, str]) -> str:
    summary = _sanitize_candidate_summary(value)
    if summary and summary == basic_info.get('name', ''):
        return ''
    return summary


def _extract_sections(resume_text: str) -> dict[str, list[str]]:
    sections = {key: [] for key in SECTION_ALIASES}
    current_section: str | None = None

    # Pre-fold SECTION_ALIASES once so each line check is a set lookup.
    folded: dict[str, str] = {}
    for section_name, aliases in SECTION_ALIASES.items():
        for alias in aliases:
            folded[_normalize_section_heading(alias)] = section_name

    for raw_line in resume_text.splitlines():
        line = _clean_line(raw_line)
        if not line:
            continue

        norm = _normalize_section_heading(line)
        matched_section = folded.get(norm)

        if matched_section is not None:
            current_section = matched_section
            continue

        if current_section is not None:
            sections[current_section].append(_normalize_line_preserve_bullet(raw_line))

    return sections


def _is_bulleted_line(value: str) -> bool:
    return BULLET_PREFIX_PATTERN.match(value.strip()) is not None


def _looks_like_labeled_bullet(value: str) -> bool:
    cleaned = _clean_line(value)
    colon_positions = [index for index in (cleaned.find('：'), cleaned.find(':')) if index >= 0]
    if not colon_positions:
        return False
    first_colon = min(colon_positions)
    return 1 <= first_colon <= 28


def _merge_detail_lines(lines: list[str]) -> list[str]:
    merged: list[tuple[str, bool]] = []

    for line in lines:
        cleaned = _clean_line(line)
        if not cleaned:
            continue

        is_bulleted = _is_bulleted_line(line)
        starts_new_labeled_item = _looks_like_labeled_bullet(cleaned)

        if not merged or is_bulleted or starts_new_labeled_item:
            merged.append((cleaned, is_bulleted or starts_new_labeled_item))
            continue

        previous, previous_is_item = merged[-1]
        if previous_is_item:
            merged[-1] = (f'{previous}{cleaned}', previous_is_item)
            continue

        merged.append((cleaned, False))

    return [text for text, _is_item in merged]


def _split_section_entries(lines: list[str]) -> list[tuple[str, list[str]]]:
    entries: list[tuple[str, list[str]]] = []
    current_header = ''
    current_details: list[str] = []

    for line in lines:
        if DATE_RANGE_PATTERN.search(line):
            if current_header:
                entries.append((current_header, current_details))
            current_header = line
            current_details = []
            continue

        if current_header:
            current_details.append(line)

    if current_header:
        entries.append((current_header, current_details))

    return entries


def _split_header_parts(value: str) -> list[str]:
    cleaned = re.sub(r'\s{2,}', ' | ', value).strip()
    if '|' in cleaned:
        return [part.strip() for part in cleaned.split('|') if part.strip()]
    return [part.strip() for part in cleaned.split() if part.strip()]


def _extract_date_range(value: str) -> tuple[str, str, str]:
    match = DATE_RANGE_PATTERN.search(value)
    if not match:
        return value.strip(), '', ''
    start_date = match.group('start')
    end_date = match.group('end')
    prefix = value[:match.start()].strip()
    return prefix, start_date, end_date


def _parse_education_section(lines: list[str]) -> list[ResumeEducationItem]:
    items: list[ResumeEducationItem] = []
    for line in lines:
        prefix, start_date, end_date = _extract_date_range(line)
        if not prefix:
            continue
        parts = _split_header_parts(prefix)
        if not parts:
            continue

        school = parts[0]
        remainder = ' '.join(parts[1:]).strip()
        degree = ''
        major = ''
        for candidate in ('博士', '硕士', '学士'):
            if candidate in remainder:
                degree = candidate
                major = remainder.replace(candidate, '').strip()
                break
        if not degree and remainder:
            degree = remainder

        items.append(
            ResumeEducationItem(
                school=school,
                degree=degree,
                major=major,
                start_date=start_date,
                end_date=end_date,
                highlights=[],
            )
        )
    return items


def _parse_internship_header(prefix: str) -> tuple[str, str]:
    parts = _split_header_parts(prefix)
    if len(parts) >= 3:
        return parts[0], ' '.join(parts[1:])
    if len(parts) == 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return parts[0], ''
    return '', ''


def _parse_internship_section(lines: list[str]) -> list[ResumeInternshipItem]:
    items: list[ResumeInternshipItem] = []
    for header, details in _split_section_entries(lines):
        prefix, start_date, end_date = _extract_date_range(header)
        company, role = _parse_internship_header(prefix)
        if not company:
            continue
        items.append(
            ResumeInternshipItem(
                company=company,
                role=role,
                start_date=start_date,
                end_date=end_date,
                bullets=_merge_detail_lines(details),
            )
        )
    return items


def _parse_project_section(lines: list[str]) -> list[ResumeProjectItem]:
    items: list[ResumeProjectItem] = []
    for header, details in _split_section_entries(lines):
        prefix, _start_date, _end_date = _extract_date_range(header)
        parts = _split_header_parts(prefix)
        if not parts:
            continue
        if len(parts) >= 2:
            name = ' '.join(parts[:-1])
            role = parts[-1]
        else:
            name = parts[0]
            role = ''
        items.append(
            ResumeProjectItem(
                name=name,
                role=role,
                tech_stack=[],
                bullets=_merge_detail_lines(details),
            )
        )
    return items


def _parse_skills_section(lines: list[str]) -> tuple[list[str], list[str], list[str]]:
    technical: list[str] = []
    tools: list[str] = []
    languages: list[str] = []

    for line in lines:
        normalized = line.replace('：', ':')
        if ':' not in normalized:
            continue
        label, values = normalized.split(':', 1)
        parsed_values = _normalize_string_list(values)
        if '编程语言' in label:
            technical.extend(parsed_values)
        elif '软件工具' in label or '工具' in label:
            tools.extend(parsed_values)
        elif label.strip() == '语言' or '语言' in label:
            languages.extend(parsed_values)

    return (
        _dedupe_preserve_order(technical),
        _dedupe_preserve_order(tools),
        _dedupe_preserve_order(languages),
    )


def _normalize_education_items(value: Any) -> list[ResumeEducationItem]:
    if not isinstance(value, list):
        return []
    items: list[ResumeEducationItem] = []
    for raw_item in value:
        if isinstance(raw_item, str):
            items.append(ResumeEducationItem(school=_clean_line(raw_item)))
            continue
        if not isinstance(raw_item, dict):
            continue
        items.append(
            ResumeEducationItem(
                school=_clean_line(str(raw_item.get('school', ''))),
                degree=_clean_line(str(raw_item.get('degree', ''))),
                major=_clean_line(str(raw_item.get('major', ''))),
                start_date=_clean_line(str(raw_item.get('start_date', ''))),
                end_date=_clean_line(str(raw_item.get('end_date', ''))),
                highlights=_normalize_string_list(raw_item.get('highlights', [])),
            )
        )
    return [item for item in items if item.school or item.degree or item.major]


def _normalize_internship_items(value: Any) -> list[ResumeInternshipItem]:
    if not isinstance(value, list):
        return []
    items: list[ResumeInternshipItem] = []
    for raw_item in value:
        if isinstance(raw_item, str):
            items.append(ResumeInternshipItem(company=_clean_line(raw_item)))
            continue
        if not isinstance(raw_item, dict):
            continue
        items.append(
            ResumeInternshipItem(
                company=_clean_line(str(raw_item.get('company', ''))),
                role=_clean_line(str(raw_item.get('role', ''))),
                start_date=_clean_line(str(raw_item.get('start_date', ''))),
                end_date=_clean_line(str(raw_item.get('end_date', ''))),
                # #1 (2026-05-21): LLM 输出 bullets 已经按"逻辑条目"分好,
                # 不再走 _merge_detail_lines (那个原本是给 heuristic 路径用
                # 修 PDF 行 wrap 的, 在 LLM 输出上会反方向 glue 把"做了一些
                # 数据维护工作"粘到前一条 "AB 测试..." 上 — Worker C P7-1)。
                bullets=_normalize_string_list(raw_item.get('bullets', [])),
            )
        )
    return [item for item in items if item.company or item.role or item.bullets]


def _normalize_project_items(value: Any) -> list[ResumeProjectItem]:
    if not isinstance(value, list):
        return []
    items: list[ResumeProjectItem] = []
    for raw_item in value:
        if isinstance(raw_item, str):
            items.append(ResumeProjectItem(name=_clean_line(raw_item)))
            continue
        if not isinstance(raw_item, dict):
            continue
        items.append(
            ResumeProjectItem(
                name=_clean_line(str(raw_item.get('name', ''))),
                role=_clean_line(str(raw_item.get('role', ''))),
                tech_stack=_normalize_string_list(raw_item.get('tech_stack', [])),
                # #1 (2026-05-21): 同 internship, 不再 merge LLM 已分好的 bullets
                bullets=_normalize_string_list(raw_item.get('bullets', [])),
            )
        )
    return [item for item in items if item.name or item.role or item.bullets]


def _fill_education_from_heuristic(
    llm_items: list[ResumeEducationItem],
    heuristic_items: list[ResumeEducationItem],
) -> list[ResumeEducationItem]:
    if not llm_items:
        return heuristic_items
    filled: list[ResumeEducationItem] = []
    for index, item in enumerate(llm_items):
        fallback = heuristic_items[index] if index < len(heuristic_items) else None
        filled.append(
            ResumeEducationItem(
                school=item.school or (fallback.school if fallback else ''),
                degree=item.degree or (fallback.degree if fallback else ''),
                major=item.major or (fallback.major if fallback else ''),
                start_date=item.start_date or (fallback.start_date if fallback else ''),
                end_date=item.end_date or (fallback.end_date if fallback else ''),
                highlights=item.highlights or (fallback.highlights if fallback else []),
            )
        )
    return filled


def _fill_internships_from_heuristic(
    llm_items: list[ResumeInternshipItem],
    heuristic_items: list[ResumeInternshipItem],
) -> list[ResumeInternshipItem]:
    if not llm_items:
        return heuristic_items
    filled: list[ResumeInternshipItem] = []
    for index, item in enumerate(llm_items):
        fallback = heuristic_items[index] if index < len(heuristic_items) else None
        filled.append(
            ResumeInternshipItem(
                company=item.company or (fallback.company if fallback else ''),
                role=item.role or (fallback.role if fallback else ''),
                start_date=item.start_date or (fallback.start_date if fallback else ''),
                end_date=item.end_date or (fallback.end_date if fallback else ''),
                bullets=item.bullets or (fallback.bullets if fallback else []),
            )
        )
    return filled


def _fill_projects_from_heuristic(
    llm_items: list[ResumeProjectItem],
    heuristic_items: list[ResumeProjectItem],
) -> list[ResumeProjectItem]:
    if not llm_items:
        return heuristic_items
    filled: list[ResumeProjectItem] = []
    for index, item in enumerate(llm_items):
        fallback = heuristic_items[index] if index < len(heuristic_items) else None
        filled.append(
            ResumeProjectItem(
                name=item.name or (fallback.name if fallback else ''),
                role=item.role or (fallback.role if fallback else ''),
                tech_stack=item.tech_stack or (fallback.tech_stack if fallback else []),
                bullets=item.bullets or (fallback.bullets if fallback else []),
            )
        )
    return filled


def _merge_profile_with_heuristics(raw_profile: Any, heuristic_profile: ResumeProfilePayload) -> ResumeProfilePayload:
    raw_dict = raw_profile if isinstance(raw_profile, dict) else {}
    skills_dict = raw_dict.get('skills', {}) if isinstance(raw_dict.get('skills', {}), dict) else {}
    basic_info = {
        **heuristic_profile.basic_info,
        **_normalize_basic_info(raw_dict.get('basic_info', {})),
    }

    technical = _clean_skill_items(_normalize_string_list(skills_dict.get('technical', [])))
    tools = _clean_skill_items(_normalize_string_list(skills_dict.get('tools', [])))
    skill_languages = _normalize_string_list(skills_dict.get('languages', []))
    languages = _normalize_string_list(raw_dict.get('languages', []))

    profile = ResumeProfilePayload(
        basic_info=basic_info,
        education=_fill_education_from_heuristic(
            _normalize_education_items(raw_dict.get('education', [])),
            heuristic_profile.education,
        ),
        internships=_fill_internships_from_heuristic(
            _normalize_internship_items(raw_dict.get('internships', [])),
            heuristic_profile.internships,
        ),
        projects=_fill_projects_from_heuristic(
            _normalize_project_items(raw_dict.get('projects', [])),
            heuristic_profile.projects,
        ),
        # 2026-05-21: skills 三栏改成 LLM ∪ heuristic 并集而不是"LLM or heuristic"。
        # 原来 LLM 给 ["Python","SQL"] 就直接覆盖, heuristic 通过 KNOWN_TECH_SKILLS
        # 在简历里实锤找到的 LightGBM/XGBoost/LSTM 等被丢。 现在两边各自的 hits 都
        # 保留, dedupe 保序 (LLM 优先, heuristic 补全)。
        skills=ResumeSkillsPayload(
            technical=_dedupe_preserve_order(
                list(technical) + list(heuristic_profile.skills.technical)
            ),
            tools=_dedupe_preserve_order(
                list(tools) + list(heuristic_profile.skills.tools)
            ),
            languages=_dedupe_preserve_order(
                list(skill_languages) + list(heuristic_profile.skills.languages)
            ),
        ),
        languages=languages or heuristic_profile.languages,
        awards=_normalize_string_list(raw_dict.get('awards', [])) or heuristic_profile.awards,
        candidate_summary=_candidate_summary_or_empty(str(raw_dict.get('candidate_summary', '') or ''), basic_info)
        or heuristic_profile.candidate_summary,
        inferred_roles=_normalize_string_list(raw_dict.get('inferred_roles', [])) or heuristic_profile.inferred_roles,
        inferred_tracks=_canonicalize_track_list(
            _normalize_string_list(raw_dict.get('inferred_tracks', [])) or heuristic_profile.inferred_tracks
        ),
        # 2026-05-22 P3: LLM inferred_offices 优先(LLM 能识别 Objective 段 / 隐含
        # 偏好), heuristic 兜底(LLM 漏掉 / 不输出此字段时不要丢)。 取并集 dedupe。
        inferred_offices=_dedupe_preserve_order(
            _normalize_offices(raw_dict.get('inferred_offices', []))
            + heuristic_profile.inferred_offices
        ),
    )
    return profile


def build_heuristic_resume_profile(resume_text: str) -> ResumeProfilePayload:
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    contact_info = _extract_contact_info(resume_text)
    sections = _extract_sections(resume_text)

    name = ''
    for line in lines[:8]:
        cleaned_line = _clean_line(line)
        if (
            EMAIL_PATTERN.search(cleaned_line)
            or PHONE_PATTERN.search(cleaned_line)
            or URL_PATTERN.search(cleaned_line)
            or cleaned_line in SECTION_HEADING_ALIASES
        ):
            continue
        if len(line) <= 40:
            name = line
            break

    lowered_text = resume_text.lower()
    technical_skills = [skill for skill in KNOWN_TECH_SKILLS if _token_in_text(skill, lowered_text)]
    inferred_roles = _dedupe_preserve_order(
        [role for role in ROLE_KEYWORDS if _token_in_text(role, lowered_text)]
    )[:3]
    # 2026-05-22 Round 3: TRACK_KEYWORDS 走 word-boundary, 不再让 'PE' 撞
    # 'PE/EV-EBITDA', 'VC' 撞 'GraphSAGE'(GAT、GCN 在 KNOWN_TECH 里已隔离)等。
    inferred_tracks = _canonicalize_track_list(
        _dedupe_preserve_order(
            [track for track in TRACK_KEYWORDS if _token_in_text(track, lowered_text)]
        )[:3]
    )

    summary = _sanitize_candidate_summary('\n'.join(sections['summary']))
    technical_from_section, tools_from_section, languages = _parse_skills_section(sections['skills'])

    return ResumeProfilePayload(
        basic_info={
            'name': name,
            **contact_info,
        },
        education=_parse_education_section(sections['education']),
        internships=_parse_internship_section(sections['internships']),
        projects=_parse_project_section(sections['projects']),
        skills=ResumeSkillsPayload(
            technical=_dedupe_preserve_order(technical_skills + technical_from_section),
            tools=tools_from_section,
            languages=languages,
        ),
        languages=languages,
        candidate_summary=summary,
        inferred_roles=inferred_roles,
        inferred_tracks=inferred_tracks,
        # 2026-05-22 P3: heuristic 也填 inferred_offices(纯 keyword 匹配, LLM 挂时兜底)
        inferred_offices=_infer_offices_from_resume_text(resume_text),
    )


def build_resume_parser_provider() -> ResumeParserProvider:
    from app import config
    client = build_resume_llm_client(model=config.RESUME_PARSER_MODEL)
    if not client.api_key:
        raise ValueError('RESUME_COPILOT_LLM_API_KEY is not configured')
    return OpenAICompatibleResumeParserProvider(client=client)


def parse_resume_text_to_profile(
    resume_text: str,
    provider: ResumeParserProvider | None = None,
) -> ResumeProfilePayload:
    parser_provider = provider or build_resume_parser_provider()
    raw_profile = parser_provider.parse_resume_text(resume_text)
    if isinstance(raw_profile, str):
        raw_profile = json.loads(raw_profile)
    heuristic_profile = build_heuristic_resume_profile(resume_text)
    return _merge_profile_with_heuristics(raw_profile, heuristic_profile)
