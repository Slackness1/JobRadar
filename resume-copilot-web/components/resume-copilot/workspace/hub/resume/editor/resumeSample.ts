/**
 * 简历文档数据模型 + 5 套模板注册表 + 示例 profile。
 * 数据形态移植自设计源 简历模板.html 的 PROFILE / TEMPLATES。
 * 编辑器目前为目测壳态,用此示例数据驱动渲染;接真实 session profile 时
 * 只需把 ResumeProfile 映射好喂给 <ResumeDoc>。
 */

export type ResumeSection =
  | { id: string; label: string; type: 'timeline'; items: TimelineItem[] }
  | { id: string; label: string; type: 'paragraphs'; items: string[] }
  | { id: string; label: string; type: 'skills' }
  | { id: string; label: string; type: 'tags'; items: string[] };

export interface TimelineItem {
  org: string;
  date: string;
  location?: string;
  sub?: string;
  course?: string;
  desc?: string;
  bullets?: string[];
}

export interface ResumeProfile {
  name: string;
  email: string;
  skillsText: string;
  sections: ResumeSection[];
}

/** 模板 id → 渲染信息。id 与设计源一致;name/struct 对齐编辑器中文命名。 */
export interface ResumeTemplate {
  id: string;
  name: string;
  struct: string;
  cls: string;
}

/** 「布局」tab 排版状态。四个值均为 0..1 滑块刻度。 */
export interface LayoutState {
  font: number; // 字号
  line: number; // 行高
  margin: number; // 页边距
  gap: number; // 模块间距
}

export const DEFAULT_LAYOUT: LayoutState = { font: 0.5, line: 0.62, margin: 0.4, gap: 0.55 };

/** 把 0..1 滑块刻度映射成简历文档可用的 CSS 变量(覆盖 resume-doc.css 默认)。 */
export function layoutToVars(l: LayoutState): Record<string, string> {
  return {
    '--doc-fs': `${(11.5 + l.font * 3).toFixed(2)}px`,
    '--doc-line': (1.3 + l.line * 0.6).toFixed(3),
    '--doc-pad': `${Math.round(30 + l.margin * 45)}px`,
    '--sec-gap': `${Math.round(8 + l.gap * 20)}px`,
  };
}

export const TEMPLATES: ResumeTemplate[] = [
  { id: 'classic', name: '素白单栏', struct: '单栏', cls: 't-classic' },
  { id: 'sidebar', name: '蓝栏双侧', struct: '双栏', cls: 't-sidebar' },
  { id: 'darkhdr', name: '深首横幅', struct: '单栏', cls: 't-darkhdr' },
  { id: 'tealcurve', name: '墨绿弧顶', struct: '单栏', cls: 't-tealcurve' },
  { id: 'cyanblock', name: '浅青色块', struct: '单栏', cls: 't-cyanblock' },
];

export const SAMPLE_PROFILE: ResumeProfile = {
  name: '韩怀宇',
  email: 'han.huaiyu@saif.sjtu.edu.cn',
  skillsText:
    'Python（pandas/numpy/pytest/numba/cython）、C++（STL/模板元编程）、时序模型（LSTM/Transformer/GRU+Attention）、机器学习（LightGBM/XGBoost/神经网络）、高频数据处理（订单簿重构/tick级数据清洗）、回测框架开发、Linux、Git、Docker',
  sections: [
    {
      id: 'edu',
      label: '教育经历',
      type: 'timeline',
      items: [
        {
          org: '上海交通大学上海高级金融学院（SAIF）',
          date: '2025-09 - 2027-06',
          location: '上海',
          sub: '金融学-FinTech方向（MF-FT）·硕士',
          course: '主修课程：机器学习与金融实证A+、时间序列分析A+',
        },
        {
          org: '上海交通大学致远学院',
          date: '2021-09 - 2025-06',
          location: '上海',
          sub: '数学与应用数学+计算机科学·本科',
          course: '主修课程：机器学习与金融实证A+、时间序列分析A+',
        },
      ],
    },
    {
      id: 'str',
      label: '个人优势',
      type: 'paragraphs',
      items: [
        '数学与编程双引擎：上海交通大学数学与应用数学+计算机科学双学位，ACM-ICPC亚洲区域赛金牌，具备扎实的数理推导与高性能编程能力，能快速实现复杂算法与模型。',
        '高频量化实战经验：在九坤投资参与中频alpha因子开发，提交12个因子，入库4个（单因子Sharpe>0.8），熟悉因子开发全流程（数据清洗、特征工程、回测验证）；在乾象投资复现并改进4篇alpha因子学术论文，具备从论文到策略的转化能力。',
        '前沿技术储备：精通Python/C++，熟练使用PyTorch、LightGBM等工具，具备深度学习（LSTM/Transformer）在高频订单簿数据上的建模经验，能独立搭建回测框架与数据处理管道。',
        '目标明确：致力于加入头部量化私募（九坤、明汯、鸣石、Point72）担任量化研究员，中期目标成长为PM。当前正系统性补充跨资产与宏观视角，以完善策略框架。',
      ],
    },
    {
      id: 'intern',
      label: '实习经历',
      type: 'timeline',
      items: [
        {
          org: '九坤投资',
          date: '2024-06 - 2024-12',
          location: '北京',
          desc: '在资深研究员指导下，系统开发中频（1-5天持仓）alpha因子，覆盖数据清洗、特征工程、模型构建与回测验证全流程。共提交12个因子，其中4个入库（单因子Sharpe > 0.8），入库率33%。',
        },
      ],
    },
    {
      id: 'proj',
      label: '项目经历',
      type: 'timeline',
      items: [
        {
          org: '乾象投资·alpha因子组·量化实习生（寒假项目）',
          date: '2025-01 - 2025-04',
          location: '上海',
          bullets: [
            '复现并改进4篇alpha因子学术论文（Avramov、Lin、Frazzini等），针对信号处理与回测方法进行优化，输出4份详细复现报告',
            '提交并验证改进后因子的收益表现，单因子夏普比率较原始论文提升约15%',
          ],
        },
        {
          org: '深度学习在高频订单簿数据上的方向预测',
          date: '2024-09 - 2025-06',
          location: '上海',
          desc: '提取股指期货（IF/IC/IH）高频订单簿数据，基于LSTM+Transformer+注意力机制构建混合深度学习模型，预测5-30秒价格方向。',
          bullets: [
            '设计并实现多尺度特征提取模块，融合时序依赖与长程注意力，提升信号捕捉能力',
            '在实盘历史数据上回测，方向预测准确率达到58%以上，相比单一LSTM基线提升约4个百分点',
            '构建端到端数据处理与模型训练pipeline，支持批量回测与参数调优',
          ],
        },
        {
          org: 'ACM-ICPC区域赛金牌项目',
          date: '2022-01 - 2023-01',
          location: '上海',
          desc: '代表上海交通大学参加ACM-ICPC亚洲区域赛，作为图论与动态规划专题负责人，与团队协作获得金牌（前10%）。',
          bullets: [
            '负责图论与动态规划算法的策略制定与代码实现，在5小时内解决多道复杂算法题，涵盖最短路径、网络流、状态压缩DP等高难度题型',
            '通过高效算法设计与优化，显著提升解题速度与正确率，为团队稳定贡献关键分数',
          ],
        },
      ],
    },
    { id: 'skills', label: '掌握技能', type: 'skills' },
    { id: 'honor', label: '所获荣誉', type: 'tags', items: ['ACM-ICPC亚洲区域赛金牌'] },
  ],
};

/** 简历显示语言。 */
export type Lang = 'zh' | 'en';

/** 英文示例简历 — 与 SAMPLE_PROFILE 结构/section id 严格对齐,仅文本/日期为英文。 */
export const SAMPLE_PROFILE_EN: ResumeProfile = {
  name: 'Huaiyu Han',
  email: 'han.huaiyu@saif.sjtu.edu.cn',
  skillsText:
    'Python (pandas/numpy/pytest/numba/cython), C++ (STL/template metaprogramming), time-series models (LSTM/Transformer/GRU+Attention), machine learning (LightGBM/XGBoost/neural nets), high-frequency data processing (order-book reconstruction/tick-level cleaning), backtesting framework development, Linux, Git, Docker',
  sections: [
    {
      id: 'edu',
      label: 'Education',
      type: 'timeline',
      items: [
        {
          org: 'Shanghai Advanced Institute of Finance (SAIF), SJTU',
          date: 'Sep 2025 – Jun 2027',
          location: 'Shanghai',
          sub: 'M.F. in Finance, FinTech track (MF-FT)',
          course: 'Selected courses: Machine Learning & Empirical Finance (A+), Time Series Analysis (A+)',
        },
        {
          org: 'Zhiyuan College, Shanghai Jiao Tong University',
          date: 'Sep 2021 – Jun 2025',
          location: 'Shanghai',
          sub: 'B.S. in Mathematics & Applied Mathematics + Computer Science',
          course: 'Selected courses: Machine Learning & Empirical Finance (A+), Time Series Analysis (A+)',
        },
      ],
    },
    {
      id: 'str',
      label: 'Summary',
      type: 'paragraphs',
      items: [
        'Dual math & engineering foundation: B.S. in Mathematics & Applied Mathematics + Computer Science at SJTU, ACM-ICPC Asia Regional gold medalist; strong mathematical derivation and high-performance programming, able to implement complex algorithms and models quickly.',
        'Hands-on quant experience: at Ubiquant, developed mid-frequency alpha factors, submitting 12 factors with 4 accepted into the library (single-factor Sharpe > 0.8); at Zhixuan Investment, reproduced and improved 4 alpha-factor papers, demonstrating paper-to-strategy capability.',
        'Frontier technical stack: proficient in Python/C++, fluent with PyTorch and LightGBM; deep-learning (LSTM/Transformer) modeling experience on high-frequency order-book data; able to build backtesting frameworks and data pipelines independently.',
        'Clear goal: aiming to join a top quant fund (Ubiquant, Minghong, Mingshi, Point72) as a Quantitative Researcher, with a mid-term goal of becoming a PM; currently broadening cross-asset and macro perspectives to complete the strategy framework.',
      ],
    },
    {
      id: 'intern',
      label: 'Work Experience',
      type: 'timeline',
      items: [
        {
          org: 'Ubiquant',
          date: 'Jun 2024 – Dec 2024',
          location: 'Beijing',
          desc: 'Under senior researcher guidance, systematically developed mid-frequency (1–5 day holding) alpha factors across the full pipeline of data cleaning, feature engineering, model construction, and backtest validation. Submitted 12 factors, 4 accepted into the library (single-factor Sharpe > 0.8), a 33% acceptance rate.',
        },
      ],
    },
    {
      id: 'proj',
      label: 'Projects',
      type: 'timeline',
      items: [
        {
          org: 'Zhixuan Investment · Alpha Factor Group · Quant Intern (winter project)',
          date: 'Jan 2025 – Apr 2025',
          location: 'Shanghai',
          bullets: [
            'Reproduced and improved 4 alpha-factor papers (Avramov, Lin, Frazzini, et al.), optimizing signal processing and backtest methodology, and produced 4 detailed reproduction reports',
            'Submitted and validated the improved factors; single-factor Sharpe ratio improved ~15% over the original papers',
          ],
        },
        {
          org: 'Deep Learning for Direction Prediction on High-Frequency Order-Book Data',
          date: 'Sep 2024 – Jun 2025',
          location: 'Shanghai',
          desc: 'Extracted high-frequency order-book data of index futures (IF/IC/IH) and built a hybrid LSTM+Transformer+attention deep-learning model to predict 5–30 second price direction.',
          bullets: [
            'Designed and implemented a multi-scale feature-extraction module fusing temporal dependency and long-range attention to improve signal capture',
            'Backtested on live historical data with directional accuracy above 58%, ~4 percentage points over a single-LSTM baseline',
            'Built an end-to-end data-processing and model-training pipeline supporting batch backtesting and hyperparameter tuning',
          ],
        },
        {
          org: 'ACM-ICPC Regional Gold Medal Project',
          date: 'Jan 2022 – Jan 2023',
          location: 'Shanghai',
          desc: 'Represented SJTU at the ACM-ICPC Asia Regional Contest as the graph-theory and dynamic-programming lead, winning gold (top 10%) with the team.',
          bullets: [
            'Led strategy and implementation for graph and DP algorithms, solving multiple hard problems within 5 hours spanning shortest paths, network flow, and bitmask DP',
            'Improved solving speed and accuracy through efficient algorithm design, consistently contributing key points for the team',
          ],
        },
      ],
    },
    { id: 'skills', label: 'Skills', type: 'skills' },
    { id: 'honor', label: 'Honors & Awards', type: 'tags', items: ['ACM-ICPC Asia Regional Gold Medal'] },
  ],
};
