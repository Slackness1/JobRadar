# GPT 5.5 Pro — Phase G Call 2: 重做 🔴 sub_cat KB — AI算法业务

**生成日期**: 2026-05-29
**Call 编号**: 2 / 10
**优先理由**: user audit: meta 缺失 (company_mentions=?), 公司表全 0 XHS 提及却 medium confidence 加多个 must_have

## 你 (GPT 5.5 Pro) 的任务

重做 `AI算法业务` 这一张知识库 (sub_cat KB)。输出 15 字段新 KB JSON, 直接替换
现 knowledge_subcategories 表 sub_cat='AI算法业务' 行的 payload_json。

**严格按 Part 5 输出 schema 给, 不写总结性废话**。

---

## Part 1 — Call 1 已给的回炉指南

- 现 KB 主要问题: meta/source 不足，业务算法与 LLM post-train、Agent、AI infra、前端开发混淆。
- 应改的关键字段: typical_companies 保留字节、阿里、美团、小红书、蚂蚁等有搜推广告/风控/数据挖掘业务算法的实体，并补 company×sub_cat 证据。
- 应改的关键字段: hard_req 聚焦搜索/推荐/广告/排序/召回/CTR/CVR/风控/特征工程/模型上线/A-B/在线指标。
- 应改的关键字段: pitfalls 增加"大模型训练/对齐 ≠ 业务算法""Agent/RAG ≠ 业务算法""前端/全栈开发 ≠ 业务算法""ML engine infra ≠ 业务算法"。
- 应补的证据来源: 大厂业务算法官方 JD、算法实习招聘页、XHS 同岗位面经；common_knowledge 必须写清"该公司有对应业务算法团队"的理由。
- 重做后 confidence 期望: medium-high。
- 实施: Opus subagent 整节回炉；Pass 2 AI 五子赛道规则同步上线。

---

## Part 2 — 现 KB payload (你要替换的对象)

**data_confidence**: medium
**data_basis**: {'post_count': 18, 'saif_record_count': 0, 'ground_truth_count': 8, 'high_relevance_posts': 7, 'notes': '互联网大厂 must_have 8 家全覆盖；金融科技 AI 应用方向（华泰/中金/中邮资管/九坤）作为延伸路径补充；缺乏 SAIF MF 学生直接 case，置信度 medium'}

```json
{
  "sub_cat": "AI算法业务",
  "sub_cat_slug": "ai_algorithm_business",
  "strategy_type": "AI 应用_PM_开发",
  "industry_focus_candidates": [
    "AI 应用层",
    "互联网"
  ],
  "institution_tier_candidates": [
    "互联网大厂",
    "头部电商",
    "金融科技"
  ],
  "typical_companies": [
    {
      "name": "字节跳动",
      "tier": "互联网大厂",
      "is_must_have": true,
      "notes": "抖音/TikTok 推荐 + 广告算法"
    },
    {
      "name": "阿里巴巴",
      "tier": "互联网大厂",
      "is_must_have": true,
      "notes": "淘天搜推广 + 1688 业务算法"
    },
    {
      "name": "美团",
      "tier": "互联网大厂",
      "is_must_have": true,
      "notes": "外卖到店推荐 + 搜索"
    },
    {
      "name": "小红书",
      "tier": "互联网大厂",
      "is_must_have": true,
      "notes": "内容推荐 + 搜索算法"
    },
    {
      "name": "米哈游",
      "tier": "互联网大厂",
      "is_must_have": true,
      "notes": "游戏 AI + 推荐"
    },
    {
      "name": "拼多多",
      "tier": "互联网大厂",
      "is_must_have": false,
      "notes": "电商搜推 + 广告"
    },
    {
      "name": "京东",
      "tier": "互联网大厂",
      "is_must_have": false,
      "notes": "搜推 + 风控算法"
    },
    {
      "name": "腾讯",
      "tier": "互联网大厂",
      "is_must_have": false,
      "notes": "广告/视频号推荐 + AI 应用开发"
    },
    {
      "name": "快手",
      "tier": "互联网大厂",
      "is_must_have": false,
      "notes": "策略算法 + 短视频推荐"
    },
    {
      "name": "蚂蚁集团",
      "tier": "互联网大厂",
      "is_must_have": false,
      "notes": "风控算法 + AI 应用开发"
    },
    {
      "name": "小米",
      "tier": "互联网大厂",
      "is_must_have": false,
      "notes": "推荐 + 广告算法"
    }
  ],
  "hard_requirements": [
    "扎实的 ML/DL 基础：手撕 Transformer 注意力、LR/GBDT/Deep&Cross 等模型",
    "至少 1 段完整业务算法项目（搜推/广告/风控/特征工程），能讲清数据-模型-上线全链路",
    "Python + SQL 熟练；至少接触过 PyTorch/TF 训练 + A/B 实验框架",
    "项目经历 > 院校背景，垂直方向 ACM 类竞赛是加分项"
  ],
  "soft_signals": [
    "业务理解：能区分 CTR/CVR/GMV/留存 等指标在不同业务的优先级",
    "A/B 实验意识：知道指标拆解、显著性、长期收益 vs 短期收益的权衡",
    "对新技术保持敏感：LLM、生成式推荐、AI 搜的范式转变要有自己判断",
    "工程落地能力：特征工程 + 模型 + 上线推理三位一体，不只是调包"
  ],
  "transfer_paths": [
    {
      "from": "ACM/数模竞赛 + AI 课程项目",
      "to": "互联网大厂算法实习",
      "difficulty": "medium",
      "notes": "项目经历 + 垂直竞赛是核心门票，海投 BOSS/实习僧可破局"
    },
    {
      "from": "传统搜推业务算法",
      "to": "AI 搜/生成式推荐方向",
      "difficulty": "medium",
      "notes": "LLM 范式下旧框架价值衰减，需补 prompt + RAG + Agent"
    },
    {
      "from": "互联网业务算法",
      "to": "券商/资管金融科技 AI 应用",
      "difficulty": "low",
      "notes": "华泰/中金/中邮资管均新开 AI 应用方向，金融业务理解是新门槛"
    }
  ],
  "pitfalls": [
    "简历写'熟悉 RAG' 但只跑过 Langchain+向量库 demo，三面被拷问 prompt 设计/上下文拼接必穿帮",
    "只调包不懂模型原理：手撕注意力、特征工程细节是高频考点，背八股不够",
    "忽视 A/B 实验和指标拆解：业务算法岗最忌讳只讲 AUC 不讲线上收益"
  ],
  "interview_style": "技术面硬核，必撕 Transformer 注意力 + 手写代码，项目要追问到特征工程/模型选型/AB 实验细节；二面+综合面考业务理解（如中金会问公司近期科技动态、字节会拷问推荐场景）",
  "compensation_signal": "26 届大模型/算法岗薪资比 25 届涨约 50%，西二旗大厂 + 蚂蚁为头部档位",
  "career_trajectory": "实习→秋招转正进大厂算法组；2-3 年后或留互联网做高级算法，或转金融科技（券商/资管 AI 应用方向新开口子），LLM 浪潮下传统搜推面临 skill 化压力，需主动靠拢生成式推荐/AI 搜",
  "verbatim_quotes": [
    {
      "quote": "LLM席卷一切，旧范式故事不好讲，AI搜和生
```

---

## Part 3 — 该 sub_cat 全部 XHS 原帖 (18 条, 按 relevance desc)

每条含 source_url + 内容快照 + verbatim 锚点 + 提到的公司。**新 KB 的 verbatim_quotes
字段必须从这些 XHS 帖里直接 substring 摘抄, 不能改写, source_url 必须真实存在于本列表。**

### Post 1 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/69d36476000000001e00c089?xsec_token=YBFAF3ELSmto-2QMgBM2pJvYQHXuEdQIf0HLuqcCh_EWU%3D&xsec_source=app_share
- **company_mentions**: (无)
- **verbatim_signals (T1/T3 已抽取)**:
  - LLM席卷一切，旧范式故事不好讲，AI搜和生成式推荐一夜之间成了新宠儿。此外，更忧心的是skill化。同事、前任都能变成skill，我们自己未来也难逃同样的命运。
  - 搜推算法刚入门，却感到越来越慌。
  - LLM浪潮下，传统搜推乃至业务算法的出路在哪？还是直接离开互联网，投身热门地区垄断央国企/核心岗位公考选调？
- **content snippet**:
  > LLM浪潮下，传统搜推算法面临范式转变，AI搜和生成式推荐成为新方向，业务算法岗位可能被skill化取代。

搜推算法工程师入门后感到焦虑，担心业务算法岗位的未来。

学生寻求前辈对LLM浪潮下传统搜推算法出路的看法。

### Post 2 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/689476a3000000000500889c?xsec_token=YBSuiLLlWmnNdbQJeMT5agM073YWl8XSUcTFYUmj9oo5U%3D&xsec_source=app_share
- **company_mentions**: 华泰证券
- **verbatim_signals (T1/T3 已抽取)**:
  - 1.自我介绍 2.对简历中感兴趣的地方提问 3.第一类错误和第二类错误 4.ANOVA怎么分析，F统计量怎么构建 5.如何检验两组学生成绩是否有差异 6.t统计量一般用在哪 7.Python：如何计算七天滚动平均股价 8.SQL：说一下不同连接方式 9.SQL：having怎么用 10.发现涨乐财富通用户月活跃度下降，怎么分析 11.你认为金融机构有哪些工作可以进行数字化的 12.除了研究所，对金融机构其他行业有了解吗
- **content snippet**:
  > 华泰证券Fintech数分一面面试问题包括自我介绍、简历提问、统计知识（第一类错误和第二类错误、ANOVA、t检验）、Python（滚动平均）、SQL（连接、having）、业务分析（用户活跃度下降原因）、对金融机构数字化工作的了解等。

### Post 3 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/695d1eb7000000000a03c76d?xsec_token=YBrmTdVctPPyl7QovJaKaV_d7-SJ7pUrrFnv6XbaJQrSw%3D&xsec_source=app_share
- **company_mentions**: 华泰证券
- **verbatim_signals (T1/T3 已抽取)**:
  - 华泰证券｜金融科技｜AI算法工程师面经🔥
- **content snippet**:
  > 华泰证券金融科技AI算法工程师面试题目，涵盖BERT模型优化、实体识别、智能投顾推荐模型、知识图谱构建、边缘部署等。

### Post 4 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/68e12963000000000400602e?xsec_token=YBoMACpj-L2xybKn7Neuw7-fKkHjNSchL1W07QkUdUvsg%3D&xsec_source=app_share
- **company_mentions**: 中金公司
- **verbatim_signals (T1/T3 已抽取)**:
  - 首轮技术面超硬核！被问到A股预测项目的特征工程...二轮综合面更考对公司的理解～被问中金财富管理科技应用...
  - 面试下来感觉中金很看重技术落地和业务理解，宝子们准备时记得多研究公司近期科技动态！
- **content snippet**:
  > 中金金融科技校招面试包括技术面和综合面，技术面涉及A股预测项目的特征工程、随机森林调优、SQL优化、LSTM与ARIMA对比、大规模数据处理等；综合面考察对中金财富管理科技应用、合规效率、机构客户系统等的理解。

中金公司金融科技岗面试重视技术落地和业务理解，面试官会问及公司近期科技动态。

### Post 5 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/6a0f0a69000000003700e3ef?xsec_token=YBXGkaz5NY9trOpaKRilNLhSjDer5GGcPcyYeefv5QQGc%3D&xsec_source=app_share
- **company_mentions**: 华泰证券
- **verbatim_signals (T1/T3 已抽取)**:
  - 华泰证券 AI专项人才储备计划
  - 优胜奖（2万元奖金+直通校招终面）、入围奖（1万元奖金+直通校招终面）
- **content snippet**:
  > 华泰证券推出AI专项人才储备计划，面向全球本硕博，提供现金奖励和校招终面直通机会，涉及Agent、RAG、智能投研、大模型等前沿课题。

竞赛流程包括报名、线上笔试、线下面试（报销差旅）、实习考察和课题答辩，优胜奖和入围奖均可直通校招终面。

### Post 6 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/6a0c2405000000003501f2a5?xsec_token=YBHTwzjyF1UZIUPZ7Ro0P7Yi3IKdVDiI9rl5X3CLCRg1k%3D&xsec_source=app_share
- **company_mentions**: 华泰证券
- **verbatim_signals (T1/T3 已抽取)**:
  - 求问华泰证券金科专场校招笔试考啥呀 难度如何 报的是算法工程师岗
- **content snippet**:
  > 华泰证券金科专场校招笔试，算法工程师岗，询问考试内容和难度。

### Post 7 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/6a15741e00000000070278b8?xsec_token=YBtykXCAFyiHSXD_GpX4xfBFke_35ll-7M1DTKg6YcoIw%3D&xsec_source=app_share
- **company_mentions**: 中邮资管, 中邮保险, 中邮消费金融
- **verbatim_signals (T1/T3 已抽取)**:
  - 中邮资管，做机构资金的投资管理，不用对接个人客户，工作体面又稳定。六险二金、免费食堂、带薪年假。我带过的学生里秋招留用率能到60%以上。
  - 今年新开了AI应用方向，很多人还不知道，现在冲就是捡漏哈。
  - 很多人对保险有误解，觉得就是卖保险，大错特错！总部岗全是中台后台，根本不是干销售哈。
  - 实习考核优秀直接解锁2027届校招终面，不用再挤秋招独木桥。
  - 中邮消费金融，持牌消金公司头部，总部在广州，背靠邮储银行，资金成本低、业务稳定，是金融科技和消费金融赛道不错的跳板。
- **content snippet**:
  > 中邮资管是央企资管，做机构资金投资，工作体面稳定，秋招留用率60%以上。

中邮资管新开AI应用方向岗位，适合计算机+金融复合背景，竞争小。

中邮保险总部岗位不是销售，而是精算、核保、市场等中后台岗。

中邮消费金融实习考核优秀可直接解锁2027届校招终面。

中邮消费金融是持牌消金头部，背靠邮储银行，是金融科技和消费金融赛道的跳板。

### Post 8 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/6a143c4d0000000007027cd5?xsec_token=YBOEKqVMqnM_AnNg9CQJFPJZDV7wsSn7MZe4ICqcWEths%3D&xsec_source=app_share
- **company_mentions**: 九坤投资, 至知创新研究院
- **verbatim_signals (T1/T3 已抽取)**:
  - 九坤投资大模型团队扩张，多岗位急招
  - 社招：k8s集群开发专家，高级运维开发，C++，资深数据抓取，高级数据仓库，量化风险，策略组合管理，行情系统开发，测试开发，agent算法，多模态算法专家，后端开发，产品经理，ai算法研究员，数据采集，大模型数据策略产品（对话、创作、医疗），高级前端，高级数据仓库，软件采购经理，linux系统开发，高级ai算法，大模型算法研究员等
实习生：算法研究员，模型组合策略管理，风控开发，agent算法，多模态算法，c++，产品经理等
- **content snippet**:
  > 九坤投资旗下至知创新研究院招聘大模型相关岗位，包括算法、工程、产品等方向，加班少，福利好。

急招岗位涵盖k8s集群开发、高级运维、C++、数据抓取、数据仓库、量化风险、策略组合管理、行情系统开发、测试开发、agent算法、多模态算法、后端开发、产品经理、AI算法研究员、数据采集、大模型数据策略产品、高级前端、软件采购经理、linux系统开发、高级AI算法、大模型算法研究员等社招岗位，以及算法研究员、模型组合策略管理、风控开发、agent算法、多模态算法、C++、产品经理等实习岗位。

### Post 9 (relevance=0.30)
- **URL**: https://www.xiaohongshu.com/discovery/item/69ce943e000000001b002ef9?xsec_token=YBFDVxut9k2kFvxOZuK-Zfw7gmtcLoWUMPv5-VzW3HOLk%3D&xsec_source=app_share
- **company_mentions**: 券商
- **verbatim_signals (T1/T3 已抽取)**:
  - 都是券商总部，前者偏前台研发管培在前台金融科技组AI应用开发相关，后者就在后台信息科技总部后台开发组，名义是算法岗其实也是AI应用开发相关。
  - 前者偏前台研发管培在前台金融科技组AI应用开发相关，后者就在后台信息科技总部后台开发组
- **content snippet**:
  > 券商总部IT岗位，前台金融科技组和后台信息科技总部，均为AI应用开发方向。

前台研发管培和后台开发组，前者偏前台，后者偏后台。

### Post 10 (relevance=0.20)
- **URL**: https://www.xiaohongshu.com/discovery/item/68a28fb5000000001c006aff?xsec_token=YBrHCC6EfzHTPhS33o6AIf_IQGg73eBFFmOo_HaXxf__k%3D&xsec_source=app_share
- **company_mentions**: (无)
- **verbatim_signals (T1/T3 已抽取)**:
  - 简历中项目经历>院校背景（门槛）>垂直相关的竞赛（ACM之类）>专业排名、国奖、英语（锦上添花）>不够垂直的竞赛（比如美赛O奖）
  - 面试的时候能讲清楚细节和项目框架和一些设计上的idea，所以面试官的评价还挺高的
  - boss直聘/实习僧别管三七二十一海投（我就是这样）
  - ai+垂直领域应用开发的项目
- **content snippet**:
  > 简历中项目经历比院校背景更重要，垂直相关的竞赛也有帮助。

面试中能讲清楚项目细节和设计想法很重要，比学历背景更受认可。

找实习可以通过BOSS直聘、实习僧海投，或者校园论坛、学长学姐内推。

AI开发岗位实习，项目经历和垂直领域应用开发经验很重要。

### Post 11 (relevance=0.20)
- **URL**: https://www.xiaohongshu.com/discovery/item/69b58ca10000000023025027?xsec_token=YBGUOZ5HJwfioWSpudh2rh8bBTS5sqLxyA9HcPD5lTMoU%3D&xsec_source=app_share
- **company_mentions**: (无)
- **verbatim_signals (T1/T3 已抽取)**:
  - 从项目背景怎么说到数据怎么找，可以参考哪些开源代码，技术选型再到面试会被问的点再到每周规划！需要做哪些实验！
- **content snippet**:
  > 帖子提供了大模型面试准备指南，包括项目背景、数据来源、开源代码、技术选型、面试问题及每周规划。

### Post 12 (relevance=0.20)
- **URL**: https://www.xiaohongshu.com/discovery/item/69f5f1af000000002003bc23?xsec_token=YBqdEUaT64Pj7zYf8OFFeSqokh1yTA91gnwF28uDgLjTk%3D&xsec_source=app_share
- **company_mentions**: (无)
- **verbatim_signals (T1/T3 已抽取)**:
  - 26届大模型秋招岗位薪资过于吓人，普遍比25届涨了50%，吸引了大量非科班人员转行大模型。内心感觉这种行情只能持续2-3年，估计就会饱和
  - 花2周准备八股和简历，3周面试，最终拿到了西二旗大厂的算法实习生岗位，并在今年暑期中，拿下了蚂蚁oc
  - 花2周准备八股和简历
  - 西二旗大厂的算法实习生岗位，并在今年暑期中，拿下了蚂蚁oc
- **content snippet**:
  > 大模型岗位薪资涨幅大，吸引非科班转行，但行情可能仅持续2-3年

非科班转大模型准备两周八股和简历，三周面试，拿到西二旗大厂算法实习和蚂蚁oc

转大模型需要准备八股和简历

西二旗大厂和蚂蚁集团提供算法岗位

### Post 13 (relevance=0.20)
- **URL**: https://www.xiaohongshu.com/discovery/item/6a0348f2000000003701e7f5?xsec_token=YBiorUJgroJaDhf9F0epy4R6K-tSAPRnXCGWkrPPcd7WA%3D&xsec_source=app_share
- **company_mentions**: 腾讯
- **verbatim_signals (T1/T3 已抽取)**:
  - 5.14上午一面 5.14下午一面通过 5.18二面速通 5.18二面通过 等HR面 5.19收到HR面 5.21HR面结束，+🛰️ 5.21云证 5.21录用评估
- **content snippet**:
  > 腾讯AI应用开发实习面试流程包括一面、二面、HR面、云证、录用评估

### Post 14 (relevance=0.20)
- **URL**: https://www.xiaohongshu.com/discovery/item/6a040768000000003700e572?xsec_token=YBaeb85LThEO4PNqrTgJEF2fOALDIOuV3cFZRGi4gkQSY%3D&xsec_source=app_share
- **company_mentions**: 阿里巴巴
- **verbatim_signals (T1/T3 已抽取)**:
  - 这个方向对个人的要求会更综合。既要有工程开发能力，也要对AI工具和模型使用足够熟练，知道怎么和大模型交互、怎么设计prompt、怎么拆任务、怎么控制输出质量，还要保持对新技术的敏感度和学习速度。
  - 在真正动手之前，需要先去看业界最新的东西，分析它的创新点、不足，以及能不能和当前业务场景结合。
- **content snippet**:
  > AI应用研发岗位要求综合能力：工程开发、AI工具熟练度、新技术敏感度。

AI应用研发面试可能考察对AI工具和模型的使用熟练度，以及新技术调研能力。

### Post 15 (relevance=0.20)
- **URL**: https://www.xiaohongshu.com/discovery/item/69ec5aef00000000360315c0?xsec_token=YBUstzBp_IX-iFWOKcSC-mCQg3OJeDMl9XdAkBTal1ly8%3D&xsec_source=app_share
- **company_mentions**: (无)
- **verbatim_signals (T1/T3 已抽取)**:
  - 蚂蚁 AI 应用开发 一面
- **content snippet**:
  > 蚂蚁AI应用开发一面面经分享

### Post 16 (relevance=0.20)
- **URL**: https://www.xiaohongshu.com/discovery/item/685becf3000000001703532d?xsec_token=YBBaV-j0Krd76FE_g7dBz9QLzJo_nfUsCKFUjueAa0Z_I%3D&xsec_source=app_share
- **company_mentions**: (无)
- **verbatim_signals (T1/T3 已抽取)**:
  - 面试过不少人,说自己熟悉 RAG ,结果一问都穿帮。通常RAG都只碰到过前半段，Langchain上个向量库，把chunk和embedding丢进去跑个检索。实际上什么都没掌握。RAG的后半段还多了 prompt 设计、上下文拼接、生成模型行为控制这几个大坑。
  - 听劝，别在简历里继续写熟悉RAG了，穿帮！
- **content snippet**:
  > 面试中常见候选人声称熟悉RAG但实际掌握不足，仅涉及前半段（Langchain+向量库+chunk+embedding），缺乏对后半段（prompt设计、上下文拼接、生成模型行为控制）的理解。

建议不要在简历中写“熟悉RAG”以免面试穿帮，因为很多候选人只了解表面。

### Post 17 (relevance=0.20)
- **URL**: https://www.xiaohongshu.com/discovery/item/691ed918000000001e016825?xsec_token=YBinvhimoo7yxCfJ8IHNOZQ48pGDFZuHQ_0an_yXdaSrc%3D&xsec_source=app_share
- **company_mentions**: (无)
- **verbatim_signals (T1/T3 已抽取)**:
  - 字节三面被问的RAG知识，面完直被夸
- **content snippet**:
  > 字节面试考察RAG知识，包括定义、原理、流程、架构、进阶、评估和前景。

### Post 18 (relevance=0.20)
- **URL**: https://www.xiaohongshu.com/discovery/item/687df509000000001c035d6b?xsec_token=YBdOfmTMvQaptXHKNr1_co4eBYJnhgRc6gcKoPGuR-c3Q%3D&xsec_source=app_share
- **company_mentions**: 快手
- **verbatim_signals (T1/T3 已抽取)**:
  - 面试官都非常标准的理工男生，强逻辑思维，手子技术尊的很牛，小趴菜被狠狠拷打，感觉还是自己基础不扎实，手撕也不够顺，没有把握好机会，面试结束狂补了transformer的八股和代码，注意力机制真的高频考点！
- **content snippet**:
  > 快手策略算法实习面试经历，面试官注重逻辑思维，手撕代码和transformer注意力机制是高频考点。

---

## Part 4 — User audit 关于该 sub_cat 的 must_have 公司评级 (5 行)

| 公司 | tier | status | audit_reason | note |
|---|---|---|---|---|
|  | 互联网大厂 | 通过-常识/中 | common_knowledge 可支撑: 大厂AI; taxonomy_doc; demo_v1 | 抖音推荐算法 |
|  | 互联网大厂 | 需补标签 | 事实大概率对，但 source 缺 common_knowledge:大厂AI/电商推荐广告算法，taxonomy/demo 不是独立证据。 | 原证据: 可见摘录同 sub_cat 1 条; taxonomy_doc; demo_v1 | 淘天广告/推荐算法 |
|  | 互联网大厂 | 需补标签 | 事实大概率对，但 source 的 XHS 只支撑 AI PM；算法业务应补 common_knowledge 或岗位证据。 | 原证据: taxonomy_doc; demo_v1 | 外卖/到店推荐算法 |
|  | 互联网大厂 | 需补标签 | 事实可能成立，但目前只有 demo/taxonomy；建议补推荐/搜索算法岗位证据。 | 原证据: taxonomy_doc; demo_v1 | 内容推荐/搜索算法 |
|  | 互联网大厂 | 需补证据 | 只有 taxonomy_doc；游戏AI/推荐逻辑成立但无直接证据。 | 原证据: taxonomy_doc | 游戏 AI/推荐 |

---

## Part 6 — 你必须输出的 15 字段 KB JSON

**严格按以下 schema 输出, 直接给可 parse 的 JSON, 不写解释**:

```json
{
  "sub_cat": "AI算法业务",
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