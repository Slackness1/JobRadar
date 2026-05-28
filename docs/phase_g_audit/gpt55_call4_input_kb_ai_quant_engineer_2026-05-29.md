# GPT 5.5 Pro — Phase G Call 4: 重做 🔴 sub_cat KB — AI 量化工程师

**生成日期**: 2026-05-29
**Call 编号**: 4 / 10
**优先理由**: user audit: DeepSeek/字节/美团等 AI 公司不能支撑 AI 量化, ground truth 3 个修正之一

## 你 (GPT 5.5 Pro) 的任务

重做 `AI 量化工程师` 这一张知识库 (sub_cat KB)。输出 15 字段新 KB JSON, 直接替换
现 knowledge_subcategories 表 sub_cat='AI 量化工程师' 行的 payload_json。

**严格按 Part 5 输出 schema 给, 不写总结性废话**。

---

## Part 1 — Call 1 已给的回炉指南

- 现 KB 主要问题: DeepSeek/大模型事实不能直接支撑"AI量化工程师"，公司名与岗位目标混用。
- 应改的关键字段: typical_companies 改为幻方/High-Flyer、鸣石、明汯、九坤、宽德等有量化投资链路的实体；DeepSeek 只保留在"High-Flyer/幻方关联说明"且不得单独当 must_have。
- 应改的关键字段: hard_req 必须同时包含 AI/ML/DL 技术 + alpha/因子/交易/组合/行情/order book/PnL 目标。
- 应改的关键字段: pitfalls 增加"AI公司/大模型岗位 ≠ AI量化""量化私募普通 ML infra ≠ AI量化"。
- 应补的证据来源: 官方 JD、量化私募 AI researcher/ML quant 岗、XHS 同 sub_cat 面经；common_knowledge 只能写"幻方/High-Flyer 属量化投资机构"及理由。
- 重做后 confidence 期望: medium；若补到 3+ 官方/JD 强证据，可升 high。
- 实施: Opus subagent 重做 KB + Pass 2 prompt 边界规则共同解决。

---

## Part 2 — 现 KB payload (你要替换的对象)

**data_confidence**: low
**data_basis**: {'post_count': 14, 'company_mention_count': 8, 'saif_alumni_count': 0, 'ground_truth_count': 7, 'notes': 'post=14 + saif=0,confidence 定 low;典型公司主要由 ground_truth must_have 撑起,XHS 印证鸣石/明汯/幻方/灵均/乾象/超量子,DeepSeek 和九坤未在 XHS 出现但属 must_have 必保留'}

```json
{
  "sub_cat": "AI 量化工程师",
  "sub_cat_slug": "ai_quant_engineer",
  "strategy_type": "量化",
  "industry_focus_candidates": [
    "AI 应用层",
    "AI 基础设施"
  ],
  "institution_tier_candidates": [
    "头部量化私募",
    "大模型独角兽"
  ],
  "typical_companies": [
    {
      "name": "鸣石基金",
      "tier": "头部量化私募",
      "xhs_mention_count": 3,
      "is_saif_alumni_dest": false,
      "is_must_have": true
    },
    {
      "name": "明汯投资",
      "tier": "头部量化私募",
      "xhs_mention_count": 3,
      "is_saif_alumni_dest": false,
      "is_must_have": true
    },
    {
      "name": "幻方量化",
      "tier": "头部量化私募",
      "xhs_mention_count": 1,
      "is_saif_alumni_dest": false,
      "is_must_have": true
    },
    {
      "name": "DeepSeek",
      "tier": "大模型独角兽",
      "xhs_mention_count": 0,
      "is_saif_alumni_dest": false,
      "is_must_have": true
    },
    {
      "name": "九坤投资",
      "tier": "头部量化私募",
      "xhs_mention_count": 0,
      "is_saif_alumni_dest": false,
      "is_must_have": true
    },
    {
      "name": "灵均投资",
      "tier": "头部量化私募",
      "xhs_mention_count": 1,
      "is_saif_alumni_dest": false,
      "is_must_have": false
    },
    {
      "name": "衍复投资",
      "tier": "头部量化私募",
      "xhs_mention_count": 0,
      "is_saif_alumni_dest": false,
      "is_must_have": false
    },
    {
      "name": "乾象投资",
      "tier": "一线量化私募",
      "xhs_mention_count": 1,
      "is_saif_alumni_dest": false,
      "is_must_have": false
    },
    {
      "name": "超量子基金",
      "tier": "量化私募",
      "xhs_mention_count": 1,
      "is_saif_alumni_dest": false,
      "is_must_have": false
    }
  ],
  "hard_requirements": [
    "海内外名校硕/博,数学/统计/物理/计算机等理工科背景,扎实数理与编程功底",
    "精通深度学习框架(PyTorch/TensorFlow)+ 大规模模型训练经验,熟练 Python/C++",
    "掌握深度学习/机器学习/凸优化/线性代数,能做数学推导 + 代码实现 + 理论理解",
    "AI 研究员岗位通常要求 PhD,有 NLP/CV/强化学习背景或顶会论文",
    "高性能计算方向需精通 C++/CUDA,熟悉 GPU 并行计算"
  ],
  "soft_signals": [
    "对量化金融有强烈兴趣,逻辑严密、创新意识强、跨领域探索能力",
    "竞赛获奖(ACM/Kaggle/数学建模)经历对量化研究员岗位加分",
    "简历突出算法、数据建模、编程相关项目或竞赛经历,匹配 AI 实验室 / 超算资源",
    "理解深度学习在量化交易中的局限(过拟合、样本外失效)并有应对方法"
  ],
  "transfer_paths": [
    {
      "from": "互联网 AI 算法岗(NLP/CV/推荐)",
      "to": "AI 量化工程师",
      "difficulty": "medium",
      "notes": "DL/RL 技术栈通用,需补金融市场理解和因子工程经验;幻方/DeepSeek 路径已被验证"
    },
    {
      "from": "传统量化研究员(线性因子)",
      "to": "AI 量化工程师",
      "difficulty": "medium",
      "notes": "已有金融认知,补 PyTorch/Transformer/GPU 并行 + 大模型训练经验即可迁移"
    },
    {
      "from": "AI 学术 PhD(顶会论文)",
      "to": "AI 量化工程师",
      "difficulty": "low",
      "notes": "幻方等机构对 PhD 直招大模型方向,年薪 80-300 万,优先 NLP/CV/RL 背景"
    }
  ],
  "pitfalls": [
    "AI 挖出的因子常杂乱无章,缺乏可解释性,实盘落地比传统因子更难",
    "深度学习在量化交易中过拟合风险高,样本外表现易衰减,需严控正则与验证流程",
    "把岗位当成纯互联网 AI 跳板,不补金融市场微观结构,长期天花板低"
  ],
  "interview_style": "笔试侧重深度学习 + 机器学习 + 凸优化 + 线性代数,考察数学推导、代码实现和理论理解;面试常问深度学习在量化交易中的局限和过拟合解决方案,以及手撕代码题。整体流程为简历投递→初步沟通→线上笔试→2-3 轮面试→Offer,招满即止建议尽早投递。",
  "compensation_signal": "AI 研究员 80-300 万,量化研究员 60-200 万,深度学习/高性能计算工程师 50-180 万(头部私募口径)",
  "care
```

---

## Part 3 — 该 sub_cat 全部 XHS 原帖 (14 条, 按 relevance desc)

每条含 source_url + 内容快照 + verbatim 锚点 + 提到的公司。**新 KB 的 verbatim_quotes
字段必须从这些 XHS 帖里直接 substring 摘抄, 不能改写, source_url 必须真实存在于本列表。**

### Post 1 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/69be89d4000000002301f58f?xsec_token=YBLYoT2jsBGiWMvHX8qxX6TN7lb7CF7ZBpEL7wjAoGAic%3D&xsec_source=app_share
- **company_mentions**: 乾象投资
- **verbatim_signals (T1/T3 已抽取)**:
  - 给我司竖大拇哥 欢迎咨询🙋‍♀️ #量化实习生 #quant #乾象投资 #高性能计算 #genai
- **content snippet**:
  > 乾象投资在浙大进行春招，招聘量化实习生，涉及高性能计算和genai方向。

### Post 2 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/698f41fb000000000a028ea7?xsec_token=YBfaOPkjFA_lzkwp3ZyjgHU8AeRhp_D9J1quG_pQE5GTM%3D&xsec_source=app_share
- **company_mentions**: 华泰证券
- **verbatim_signals (T1/T3 已抽取)**:
  - 深度学习在量化交易中的应用有哪些局限？你怎么解决过拟合问题？
  - 华泰强调'科技驱动'，你关注过华泰的哪些数字化产品或技术成果？
  - 金融科技岗往往需要同时对接业务、产品、开发，你如何向不懂技术的业务同事解释技术边界？
- **content snippet**:
  > 华泰证券Fintech专项面试题包含量化交易、AI应用、手撕代码等，涉及深度学习在量化交易中的局限和过拟合问题。

华泰证券设有Fintech专项岗位，强调科技驱动，关注数字化产品如涨乐财富通、行知、机构服务。

金融科技岗需要同时对接业务、产品、开发，向不懂技术的业务同事解释技术边界。

### Post 3 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/69e6e286000000001d01dfbe?xsec_token=YBHtF66gwvv-BMd_KnQgiUefKOBGhXrYZQSgt-1Ih46sQ%3D&xsec_source=app_share
- **company_mentions**: 超量子基金
- **verbatim_signals (T1/T3 已抽取)**:
  - 超量子基金2026春招私募量化笔试题...考察：深度学习+机器学习+凸优化+线性代数...核心能力：数学推导 + 代码实现 + 理论理解
- **content snippet**:
  > 超量子基金2026春招量化笔试包含深度学习、机器学习、凸优化、线性代数，考察数学推导、代码实现和理论理解。

### Post 4 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/69a792eb0000000022030502?xsec_token=YBs-4avNvayEyYORKHdX6UCHlKAuhJEeb1GFsp674-Hnw%3D&xsec_source=app_share
- **company_mentions**: 幻方量化
- **verbatim_signals (T1/T3 已抽取)**:
  - 幻方量化是国内AI量化投资的领军者，管理规模超600亿，以深度学习为核心，打造智能投研体系
  - AI研究员（大模型方向）💰 年薪80-300万 ✅ 要求：PhD，NLP/CV/强化学习背景，顶会论文
  - 量化研究员（股票Alpha）💰 年薪60-200万 ✅ 要求：名校硕博，数学/统计/物理，竞赛获奖优先
  - 高性能计算工程师 💰 年薪50-150万 ✅ 要求：精通C++/CUDA，熟悉GPU并行计算
  - 深度学习工程师 💰 年薪60-180万 ✅ 要求：PyTorch/TensorFlow，大规模模型训练经验
- **content snippet**:
  > 幻方量化是国内AI量化投资的领军者，管理规模超600亿，以深度学习为核心打造智能投研体系。

幻方量化招聘AI研究员（大模型方向），年薪80-300万，要求PhD，NLP/CV/强化学习背景，顶会论文。

幻方量化招聘量化研究员（股票Alpha），年薪60-200万，要求名校硕博，数学/统计/物理，竞赛获奖优先。

幻方量化招聘高性能计算工程师，年薪50-150万，要求精通C++/CUDA，熟悉GPU并行计算。

幻方量化招聘深度学习工程师，年薪60-180万，要求PyTorch/TensorFlow，大规模模型训练经验。

校招DDL为rolling basis，建议尽早投递。

### Post 5 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/69881a220000000009038dd9?xsec_token=YBZKMi6mNP8rkkAMkJaSGdrwiU8D253dPqKAbEemyh7o4%3D&xsec_source=app_share
- **company_mentions**: 明汯投资
- **verbatim_signals (T1/T3 已抽取)**:
  - 明汯投资于2014年在上海成立，借助强大的数据挖掘、统计分析和技术研发能力，构建了覆盖全周期、多策略、多品种的量化资产管理平台。公司管理规模位居行业前列，并成为国内较早一批管理规模突破500亿元的量化私募管理人。
  - 量化研究实习生、量化开发实习生、AI算法研究实习生、AI基础架构开发实习生（4各岗位均可转正！）
- **content snippet**:
  > 明汯投资是一家头部量化私募，管理规模超500亿元，招聘量化研究、量化开发、AI算法研究、AI基础架构开发等实习生岗位，薪资800-1500元/天。

量化研究实习生、量化开发实习生、AI算法研究实习生、AI基础架构开发实习生，均为量化相关岗位，可转正。

### Post 6 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/69bcd95c000000001a037fb1?xsec_token=YBmWuq3vGdmXfbEZuwBird_rJddJs6so8GHFXZ1jVi31s%3D&xsec_source=app_share
- **company_mentions**: 明汯投资
- **verbatim_signals (T1/T3 已抽取)**:
  - 2014年成立，华尔街大佬裘慧明博士创立，妥妥的量化圈资深玩家！投研团队超100人，还有纽约团队协同，偏数据和机器学习，全球视野拉满
  - 2025年全线产品业绩直接拉满，顶级管理规模稳轻松拿捏，极端行情下超额依旧能打
- **content snippet**:
  > 明汯投资是国内量化头部机构，2014年成立，投研团队超100人，核心团队来自海外顶尖对冲基金，策略以量价因子和机器学习为核心。

量化投资行业，明汯2025年全线产品业绩突出，500指增超额20.09%，量化多头胜率91.67%，多策略对冲胜率100%。

### Post 7 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/6a0dd22b000000003700e861?xsec_token=YBm4Y5lD0UeO4fv4xPCt09ZzZHE6ETWMcmH7G7sBIEw0Y%3D&xsec_source=app_share
- **company_mentions**: 明汯
- **verbatim_signals (T1/T3 已抽取)**:
  - 明汯是国内最早把深度学习（AI）大规模应用于量化交易的机构之一。他们不满足于传统的线性模型，而是用海量GPU去挖掘海量数据中的非线性规律。
  - 这种对数据挖掘的偏执，让他们更像是一家披着私募外壳的人工智能科技公司。
- **content snippet**:
  > 明汯是国内最早把深度学习（AI）大规模应用于量化交易的机构之一，策略迭代周期被压缩到极致，用海量GPU挖掘非线性规律。

量化私募行业强调数据挖掘和算法，更像人工智能科技公司。

### Post 8 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/69a96d04000000001b01f77e?xsec_token=YBcOPiNC4aAN4ur27YciyEOyKrlisBl3bOyLSGWFFisKk%3D&xsec_source=app_share
- **company_mentions**: 灵均投资
- **verbatim_signals (T1/T3 已抽取)**:
  - 成立于2014年6月，10年量化老牌私募；管理规模100亿+，量化投资领先者；核心团队：闫彦、马志宇等行业大牛
  - 热招岗位【AI量化研究员】北京...【量化开发工程师】北京...【指数增强研究员】北京...【量化交易员】北京
  - 流程：简历投递 → 笔试 → 2-3轮面试 → Offer
- **content snippet**:
  > 灵均投资是一家成立于2014年的百亿量化私募，专注AI量化，管理规模100亿+，核心团队包括闫彦、马志宇等行业大牛。

灵均投资热招岗位包括AI量化研究员、量化开发工程师、指数增强研究员、量化交易员，均在北京。

灵均投资招聘流程为：简历投递 → 笔试 → 2-3轮面试 → Offer。

### Post 9 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/6979e092000000000e00ecd4?xsec_token=YBcuSm_5RG5FDUoAFBOZevRYeSV5FHW4EUxezGcMitvXE%3D&xsec_source=app_share
- **company_mentions**: 鸣石基金
- **verbatim_signals (T1/T3 已抽取)**:
  - 鸣石基金成立于2010年（中国量化元年），深耕量化领域15年，资产管理规模于2020年突破100亿。公司旗下设有人工智能实验室“创世纪AI实验室（G-LAB）”，专注于全流程量化策略研发与AI金融应用创新，并自建超算中心“星座计划”。
  - 研究员序列（全职/实习）：量化因子工程师、AI量化工程师、Quantitative Research（Monetization & Optimization）；工程师序列（全职）：量化开发工程师（C++）。
  - 超算资源与AI实验室是核心优势，建议在简历中突出相关项目或竞赛经历。
- **content snippet**:
  > 鸣石基金是头部量化私募，成立于2010年，管理规模超百亿，拥有AI实验室和超算中心。

校招岗位包括量化因子工程师、AI量化工程师、Quantitative Research、量化开发工程师等，面向2026届全职和2027届实习。

建议在简历中突出算法、数据建模、编程（C++/Python）相关项目或竞赛经历。

### Post 10 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/697ad5780000000022008b8e?xsec_token=YBiTjobqQtNzS5sd65hi876EvZwgdl9_ojIPAmOYYUKsw%3D&xsec_source=app_share
- **company_mentions**: 鸣石基金
- **verbatim_signals (T1/T3 已抽取)**:
  - 成立于2010中国量化元年｜2020年资产管理规模破百亿
旗下 创世纪AI实验室（G-LAB） 赋能全流程策略研发
自建超算中心 “星座计划”（一期仙女座、二期英仙座）
  - 🔬 研究员序列（全职 & 暑期实习）
量化因子工程师
AI量化工程师（MONETIZATION & OPTIMIZATION）
💻 工程师序列（全职）
量化开发工程师（C++）
  - STEP 1 简历投递 → STEP 2 初步沟通 → STEP 3 线上笔试
→ STEP 4 2-3轮面试 → STEP 5 发放OFFER
⏰ 招满即止，建议尽早锁定席位
  - 学历背景：海内外名校 硕士/博士，理工类相关专业
硬核技能：扎实的数理、编程功底，对量化金融有强烈兴趣
思维特质：逻辑严密、创新意识强、具备跨领域探索能力
- **content snippet**:
  > 鸣石基金成立于2010年，是中国量化“元老级”玩家，2020年资产管理规模破百亿，旗下有创世纪AI实验室和自建超算中心“星座计划”。

招聘岗位包括量化因子工程师、AI量化工程师（全职&暑期实习）和量化开发工程师（全职）。

招聘流程为简历投递→初步沟通→线上笔试→2-3轮面试→发放OFFER，招满即止。

面向海内外名校硕士/博士，理工类相关专业，要求扎实的数理、编程功底，对量化金融有强烈兴趣。

### Post 11 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/6a06c29c0000000007020b39?xsec_token=YB4QBS1qgXQ-bzMzodScIaKdb7i_8y3G690JNEsYkchBI%3D&xsec_source=app_share
- **company_mentions**: 鸣石基金
- **verbatim_signals (T1/T3 已抽取)**:
  - 400亿+规模量化大厂鸣石 调研交流～这两年几个策略都做得蛮好的[赞R] 还有自己的AI超算中心～
- **content snippet**:
  > 鸣石基金是一家400亿+规模的量化大厂，拥有自己的AI超算中心，近两年多个策略表现良好。

### Post 12 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/6a0bd5bf00000000080304f9?xsec_token=YBPCtCgFFhYVnxVIKu8MByAmj1iJSLzH-IxOX8TR3qVRg%3D&xsec_source=app_share
- **company_mentions**: (无)
- **verbatim_signals (T1/T3 已抽取)**:
  - 真的有人用ai完成过一整套可实盘的量化策略吗？我咋感觉ai挖出来的因子乱七八糟的，用ai做策略比自己做还麻烦
- **content snippet**:
  > 用户质疑AI挖掘因子的有效性，认为AI挖出的因子杂乱，用AI做策略比自己做还麻烦。

### Post 13 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/68a0b696000000001d013725?xsec_token=YB6mnGsgMwmQFJ2yh0vfw8V3A_Z9NNYJGocDnvQq8KUu4%3D&xsec_source=app_share
- **company_mentions**: (无)
- **verbatim_signals (T1/T3 已抽取)**:
  - 如果你想用机器学习来预测股票收益，就一定要读一读Gu, Kelley, and Xiu (2020)。这是一篇里程碑之作
  - 最优模型：3层神经网络 → 个股预测月均R²=0.40% | 标普500择时夏普率=0.77
- **content snippet**:
  > 机器学习在量化投资中的应用，特别是预测股票收益的论文讨论

讨论了机器学习模型在金融预测中的性能排序，神经网络最优，传统OLS失效

### Post 14 (relevance=0.30)
- **URL**: https://www.xiaohongshu.com/discovery/item/68e657470000000007036958?xsec_token=YBPgs5oGucpNyKWQOWHc9YTgFrFYLXL5yRrZkFteAAuZk%3D&xsec_source=app_share
- **company_mentions**: (无)
- **verbatim_signals (T1/T3 已抽取)**:
  - 从零学量化第一天，装好了qlib，让claude 帮我梳理了学习路线
- **content snippet**:
  > 用户开始学习量化，使用Qlib框架，并计划安装Ubuntu系统。

---

## Part 4 — User audit 关于该 sub_cat 的 must_have 公司评级 (5 行)

| 公司 | tier | status | audit_reason | note |
|---|---|---|---|---|
|  | 头部量化私募 | 通过-强 | SAIF 角色匹配: 2025 九坤投资 量化研究员; common_knowledge 可支撑: 头部量化私募; taxonomy_doc; demo_v1 | 按行业共识,AI 量化方向投入大 |
|  | 头部量化私募 | 通过-强 | 可见摘录同 sub_cat 3 条; common_knowledge 可支撑: 头部量化私募; taxonomy_doc | 按行业共识 |
|  | 头部量化私募 | 通过-强 | 可见摘录同 sub_cat 3 条; common_knowledge 可支撑: 头部量化私募; taxonomy_doc | AI 量化博士 70-100W·20薪 |
|  | 头部量化私募 | 通过-强 | 可见摘录同 sub_cat 1 条; common_knowledge 可支撑: 头部量化私募; taxonomy_doc | AI 量化先驱 |
|  | 大模型独角兽 | 需修正 | DeepSeek 的 LLM 事实强，但“AI量化工程师”只用“源自幻方”无法支撑；应改到幻方/High-Flyer，或补 DeepSeek 本身量化岗位证据。 | 原证据: taxonomy_doc; demo_v1 | 量化条线源自幻方 |

---

## Part 6 — 你必须输出的 15 字段 KB JSON

**严格按以下 schema 输出, 直接给可 parse 的 JSON, 不写解释**:

```json
{
  "sub_cat": "AI 量化工程师",
  "sub_cat_slug": "<英文 slug>",
  "strategy_type": "<7 大类之一, 跟 Call 1 taxonomy_v2_1.json 对齐>",
  "industry_focus_candidates": [<0-5 个>],
  "institution_tier_candidates": [<1-3 个>],
  "typical_companies": [
    {"name": "...", "tier": "...", "xhs_mention_count": <int>, "is_saif_alumni_dest": <bool>, "is_must_have": <bool>}
  ],
  "hard_requirements": [<每条 ≤80 字, 3-5 条; 必须解 Part 5 误判>],
  "soft_signals": [<每条 ≤80 字, 2-5 条>],
  "transfer_paths": [{"from": "...", "to": "...", "difficulty": "low/medium/high", "notes": <≤80 字>}],
  "pitfalls": [<每条 ≤80 字; 必须含 user audit 8.5/8.6 提的边界>],
  "interview_style": "<≤150 字>",
  "compensation_signal": "<≤80 字 或 null — 必须区分「个案/官方约束/市场传闻」>",
  "career_trajectory": "<≤150 字>",
  "verbatim_quotes": [
    {"quote": "<≤150 字, 必须 substring 自 Part 3 XHS 帖>", "source_url": "<Part 3 真实 URL>", "context": "<≤50 字>"}
  ],
  "hiring_season": {"spring": <≤50 字>, "fall": <≤50 字>, "verbatim": <原话 或 null>, "peak_month": [int]},
  "data_confidence": "<high/medium/low>",
  "data_basis": {"post_count": <int>, "company_mention_count": <int>, "saif_alumni_count": <int>}
}
```

### 输入约束 (重要)

- typical_companies 严格按 Part 4 user audit 评级: 不要把 user audit 标「需修正/需补证据」的公司当 must_have
- typical_companies XHS 提及数必须从 Part 3 真实 XHS 帖 reverse-count (不能凭空写)
- verbatim_quotes 每条必须能在 Part 3 某帖的 content/verbatim_signals 里 substring 找到
- pitfalls 必须显式列 Part 5 反映的边界混淆 (e.g. "前端/全栈 AI 应用 ≠ XX")
- compensation_signal 区分 "个案信号/市场传闻/官方约束", 不要写整体行业薪资
- data_confidence 严格按 data_basis 规则: high (post≥30 + comp_mention≥10 + saif≥3) / medium (post≥15 + comp_mention≥5) / low (其余)
- 输出只一个 JSON object, 不要 markdown 代码块包裹, 不要 explanation