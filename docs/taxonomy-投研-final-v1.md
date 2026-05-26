# 投研 + AI 跨域细颗粒度 Taxonomy (final v1)

**生成时间**: 2026-05-27
**数据来源**: XHS 7 bucket (基本面权益 140 + 卖方研究 107 + 量化 164 + 多资产_FOF 73 + 固定收益 47 + 相关补充 0 + AI 应用 161) + SAIF MF 2024/2025 就业报告 65 条流向
**生成者**: Opus 4.7, 1M context 一次合成
**服务**: 5 个 persona 端到端 demo (P1 公募基本面 / P2 卖方 TMT / P3 跨专业私募基本面 / P6 头部量化 / P_self 跨域 AI 应用-PM)

---

## 1. 三维 Taxonomy 主表

| canonical (strategy) | sub_category | 典型公司 (XHS 真出现, 按 mention 数) | 区分点 / 学生原话标志 |
|---|---|---|---|
| **基本面权益** | 公募权益研究员 | 易方达 / 华夏 / 南方 / 富国 / 嘉实 | "公募投研从研究员升到基金经理时间周期拉长但路径清晰" |
| 基本面权益 | 行业研究员·消费 | 易方达消费组 / 华夏 / 招商 | "白酒 / CXO / 渠道调研深度" |
| 基本面权益 | 行业研究员·TMT-医药-周期 | 华夏 / 永赢 / 工银瑞信 | "行业首席 / 产业链调研" |
| 基本面权益 | 公募指数研究员 | 华夏 / 易方达 / 工银瑞信 | "基准跟踪 + ETF 产品研究" |
| 基本面权益 | 公募基金中后台(产品/风控) | 南方 / 华夏 / 富国 | **"今年产品风控简历数超过投研类"** (重要拐点信号) |
| **量化** | 量化研究员·中频 | 灵均 / 九坤 / 明汯 / 鸣石 / 幻方 / 衍复 | "中频 (1-5 天持仓) alpha 因子 + sharpe > 0.8" |
| 量化 | 量化研究员·高频 | Jane Street / Citadel / Optiver / Tower / 一些国内私募 | "高频/microstructure 偏 trading firm" |
| 量化 | 量化开发 (QD) | 九坤 / 明汯 / 鸣石 / 量派 / 宽德 | "C++ / STL / Linux / 系统设计" |
| 量化 | AI 量化工程师 | 鸣石 / DeepSeek (量化条线) / 量化大厂新业务 | "AI 模型落地量化策略, 博士 70-100W·20薪" |
| 量化 | 量化因子工程师 | 明汯 / 九坤 / 衍复 | "硕士 40-50K, 博士 50-60K, 数学/物理/CS 专业" |
| **固定收益** | 信用研究员 | 中再资产 / 华富 / 光大永明 / 公募固收组 | "纯债研究极度内卷" / "城投/地产/煤炭 信用细分" |
| 固定收益 | 固收交易员 | 券商自营 / 平安 ficc / 中信 ficc | "纯投研实习拿面试正常, 交易面试要交易实习" |
| 固定收益 | 固收量化/转债/多资产 | 大型公募固收+ / 保险资管 | **"会码+会多资产=人上人"** (固收新趋势) |
| 固定收益 | 利率/宏观策略研究 | 公募 / 保险资管 / 货币中介 | "传统利率分析 + 货币政策研究" |
| **卖方研究** | 卖方研究员·TMT | 中金 / 中信建投 / 国泰海通 / 招商 / 国信 | "半导体设备 / 通信 / 计算机 / 互联网, 客户路演密度" |
| 卖方研究 | 卖方研究员·消费/医药/周期 | 华泰 / 中金 / 广发 / 三中一华 | "行业 know-how + 财报点评频次" |
| 卖方研究 | 卖方研究员·宏观策略 | 中金 / 华泰 / 国泰海通 | "宏观利率分析 + 大类资产配置观点" |
| 卖方研究 | 买方 Quant / 对冲基金 | Point72 / Citadel / 外资对冲 / 头部券商自营 | **"卖方 Quant vs 买方 Quant — 区别在策略署名权"** |
| 卖方研究 | 投行 (IBD) | 三中一华 / 投行部 / 中金投行 | "TMT 实习也常跟 IBD 共用 channel" |
| **多资产_FOF_衍生品** | 资管 FOF (机构化) | 易方达 / 融通 / 国泰海通 | "资管 FOF 看重规模和业绩排名" |
| 多资产_FOF_衍生品 | 自营 FOF | 平安银行 / 信银理财 / 中金 | "自营 FOF 追求绝对收益" |
| 多资产_FOF_衍生品 | 财富管理 FOF | 信银 / 平安 / 财富线 | "财富 FOF 看重客户需求和投后服务" |
| 多资产_FOF_衍生品 | 结构化产品/衍生品 | 中金衍生品 / 越秀 / 家办 | "FCN / 结构性产品 / 期权策略" |
| **相关补充** (XHS 数据稀, 用 ground truth 补) | PE 投后 / VC 行研 | 高瓴 / 弘毅 / 德弘 / 晨壹 / CIC / 淡马锡 (就业报告命中) | "二级 vs 一级跨界, 多数 SAIF 学生选二级" |
| **AI应用_PM_开发** | LLM 算法工程师 (post-train) | 字节 / 腾讯 / 阿里 / 蚂蚁 / DeepSeek | "SFT / RLHF / DPO / GRPO / Reward Modeling" |
| AI应用_PM_开发 | LLM 应用开发 / Agent 工程师 | 字节 / 腾讯 / 蚂蚁 / AI 初创 / 小红书 | "AI Agent 核心能力 (工具调用 / 多步推理 / 记忆管理)" |
| AI应用_PM_开发 | 多模态 / 大模型推理优化 | 字节 / 腾讯 / 华为 / 商汤 | "投机采样 / Speculative Decoding / 多模态大模型组" |
| AI应用_PM_开发 | AI PM (业务侧) | 大厂 AI 部门 / AI 初创公司 PM | "AI 应用研发强调前期调研和方案判断 (vs 传统后端工程实现)" |
| AI应用_PM_开发 | AI 算法 (传统 ML 业务方向) | 阿里淘天 / 美团 / 字节业务线 / 米哈游 / 小米 | "广告算法 / 推荐算法 / 风控多模态算法" |

### Industry focus (横切, 不锁词表)
消费 / 医药 / TMT (半导体 / 互联网 / 通信) / 新能源 / 周期 / 金融 (银行 / 保险 / 非银) / 房地产 / **AI 基础设施** / **AI 应用层** / 大宗商品 / 城投 / 转债

### Institution tier (横切)

**投研侧**:
- 一线公募 (易方达/华夏/南方/富国/嘉实 等 top 10)
- 二线公募 (中信建投基金/工银瑞信/天弘/汇添富 等)
- 头部券商研究所 (三中一华: 中金/中信/中信建投/华泰 + 国泰海通)
- 中型券商研究所 (招商/广发/国信/海通 等)
- 头部主观私募 (高瓴/景林/千合/淡水泉 等)
- 头部量化私募 (灵均/九坤/明汯/鸣石/幻方/衍复 等百亿+)
- 外资 / 对冲 (Point72 / Citadel / Jane Street / Optiver / 淡马锡上海)
- 保险资管 (中再资产/光大永明/国寿投资/华夏久盈 等)
- 银行理财子 (平安理财/信银理财/北银理财/中邮理财 等)
- 券商资管 (国泰海通资管/兴证资管/中信资管 等)
- AMC (信达/华融/东方/长城)

**AI 侧**:
- 大厂 AI 部门 (字节豆包/腾讯混元/阿里通义/百度文心/蚂蚁/华为盘古/京东/美团/小米)
- 大模型独角兽 (DeepSeek 已出圈, MiniMax/月之暗面/智谱/百川/阶跃 XHS 数据中很少直接出现但行业内主流)
- Agent / AI 应用层创业 (含 上海明星大模型初创 / 北京 AI 初创 / AI 应用初创公司 等 XHS 标签)
- 出海 AI 公司 (TikTok / Insta360 / Heygen 类等)
- 互联网公司业务算法 (小红书 / 米哈游 / Taptap / 商汤)

---

## 2. 给学生看的"细颗粒度地图"(树形 + verbatim 佐证)

```
投研空间
├── 基本面权益
│   ├── 公募权益研究员 ──► 易方达 / 华夏 / 南方 / 富国
│   │   verbatim: "投研类：权益研究员、固收研究员、量化研究员；市场销售类：渠道经理、机构销售..."
│   │   (https://www.xiaohongshu.com/discovery/item/69d4b97a0000000022026725?xsec_token=YBCPn28ZsvpOv-_PyZg1ikJpkRghQQ5l5koZyqs0mTa80%3D&xsec_source=app_share)
│   ├── 行业研究员·消费/医药/TMT ──► 易方达消费组 / 嘉实 / 招商
│   │   verbatim: "面试阶段，通过推票（基本面分析）、近期行情判断、关键行业事件、市场风险溢价 准确判断候选人..."
│   │   (https://www.xiaohongshu.com/discovery/item/69b01b10000000000601f681?xsec_token=YB3mubOgxaYuySVOQc18ibYOSsyNMwYBOBRr4DQeL0kMQ%3D&xsec_source=app_share)
│   ├── 公募指数研究员
│   └── 中后台 (产品/风控) ⚠️ "今年产品风控简历数超过投研类" — 投研竞争更白热化的反指标
│
├── 量化
│   ├── 中频量化研究员 (1-5 天持仓 alpha) ──► 灵均 / 九坤 / 明汯 / 鸣石
│   │   verbatim: "中频 alpha 因子, 提交因子 12 个, 入库 4 个 (单因子 sharpe > 0.8)" — P6 简历 verbatim 直接对齐
│   ├── 量化开发 QD (C++/系统) ──► 九坤 / 明汯
│   │   verbatim: "量化开发工程师 C++: 25-40K·15薪"
│   ├── AI 量化工程师 ──► 鸣石 / DeepSeek 量化条线
│   │   verbatim: "AI模型落地量化策略, 博士 70-100W·20薪 (香到爆!)"
│   └── 高频/Microstructure ──► Jane Street / Citadel / Optiver
│       verbatim: "Trading Firm 偏高频, 互联网量化偏 AI/Data"
│
├── 固定收益
│   ├── 信用研究 ──► 中再资产 / 公募固收 / 险资
│   │   verbatim: "纯债研究现在就是极度内卷...中等偏上非 top 选手求职胜率其实很低"
│   ├── 固收交易 ──► 平安 ficc / 中信 ficc / 券商自营
│   └── 固收+/多资产 ──► "会码+会多资产=人上人" (新趋势, 转债 + 多资产 hc 上升)
│
├── 卖方研究
│   ├── TMT 卖方研究员 ──► 中金 / 中信建投 / 国泰海通
│   │   verbatim: "半导体 / 通信设备 国产化率跟踪... 服务客户 38 次 + 电话会议 22 场" — P2 简历直接对齐
│   ├── 消费/医药/周期 卖方
│   ├── 买方 Quant ──► Point72 / Citadel / 头部券商自营
│   │   verbatim: "买方是独狼战场, 依赖 Alpha 能力; 卖方是社交家舞台, 依赖人脉和输出观点"
│   └── 35 岁焦虑 / 城池缩小: "外面想进来的人更少了 (空位也不如以前多), 里面想出去的人更多了"
│
├── 多资产 / FOF / 衍生品
│   ├── 资管 FOF (机构化, 规模+业绩排名导向)
│   ├── 自营 FOF (绝对收益导向)
│   └── 财富管理 FOF (客户服务导向, WLB 友好)
│
├── 相关补充 (PE / VC / 央国企)
│   └── 高瓴 / 弘毅 / 德弘 / 中投 / 淡马锡 (就业报告命中, XHS 数据稀)
│
跨域:
└── AI 应用 / PM / 开发
    ├── LLM 算法 (post-train) ──► 字节 / 腾讯 / 蚂蚁 / DeepSeek
    │   verbatim: "面试官反馈 LLM 算法实习生候选人虽然学校双非但履历拉满, 存在智能体应用瞧不起..."
    ├── LLM 应用开发 / Agent 工程师 ──► 字节 / 腾讯 / 小红书 / AI 初创
    │   verbatim: "参与 AI Agent 核心能力开发 (工具调用 / 多步推理 / 记忆管理)" — P_self 简历 verbatim 命中
    │   (https://www.xiaohongshu.com/discovery/item/6a0acfd30000000007013749?xsec_token=YBKCYOCzN__YUYgBbao898w-2bmO-9SHNJ91iy9nUVDTU%3D&xsec_source=app_share)
    ├── 多模态/推理优化 ──► 字节 / 华为 / 商汤
    ├── AI PM (业务侧) ──► 大厂 AI / 创业公司
    │   verbatim: "AI 应用研发强调前期调研和方案判断 vs 传统后端工程实现" — 区分 AI PM vs 工程师
    └── AI 算法 (业务方向, 传统 ML) ──► 阿里淘天 / 美团 / 米哈游 / 小米 / 小红书
        verbatim: "广告算法 / 推荐算法 / 风控多模态算法"
```

---

## 3. Demo 选公司

### 3a. 投研侧 (10 家, 覆盖 5 个 strategy 大类)

| # | 公司 | strategy_type | institution_tier | demo pitch (为什么选 + 区分谁) |
|---|---|---|---|---|
| 1 | **易方达基金** | 基本面权益 | 一线公募 | XHS 26 mention + 就业报告命中. 消费 / 医药 / 行研三足鼎立 → P1 顶配 fit, 也区分 P3 (公募基本面 vs 私募基本面) |
| 2 | **华夏基金** | 基本面权益 | 一线公募 | XHS 42 mention 第二高 + 就业报告命中. 多赛道大平台, P1 / P3 双向 fit |
| 3 | **富国基金** | 基本面权益 | 一线公募 | XHS+就业报告双命中. 招聘强信号 ("应届生起薪 17-28 万") |
| 4 | **中金公司** | 卖方研究 (TMT) | 头部券商研究所 | XHS 13 mention + P2 简历目标 + 就业报告 (申万宏源/中信建投同 tier). P2 主战场 |
| 5 | **中信建投证券** | 卖方研究 (TMT) | 头部券商研究所 | 就业报告命中. P2 backup target, 跟中金一对 |
| 6 | **华泰证券** | 卖方研究 + 基本面权益 | 头部券商 | XHS 34 mention 卖方 + 20 mention 权益 = 总命中数最高. 横跨多个 strategy, demo 内显示"同公司 ≠ 同 strategy" |
| 7 | **灵均投资** | 量化 (中频) | 头部量化私募 | XHS 30 mention 量化第一 + 就业报告"量化私募" 行业 6+8 命中. P6 顶配 fit, 与 P1 完全 strategy 隔离 |
| 8 | **九坤投资** | 量化 (中频 + QD) | 头部量化私募 | XHS 28 mention + P6 简历直接命中 (P6 简历"九坤投资 2024 实习 Top 5"). P6 强匹配验证 |
| 9 | **高瓴资本** | 相关补充 (PE) + 基本面权益 (二级研究) | 头部主观私募 / PE | 就业报告命中 + P1 简历直接命中 (P1 高瓴 PE 实习). P1/P3 双向, 区分公募 vs 私募 institution_tier |
| 10 | **中再资产** | 固定收益 + 基本面权益 (险资) | 保险资管 | XHS 8 mention 固收+7 mention 权益. P_self 隐藏 fit: 中科创达能源数据背景 + 险资固收 transfer 有可能 (未来可填) |

### 3b. AI 侧 (10 家, 给 P_self 用)

| # | 公司 | sub_category 主招 | institution_tier | P_self fit pitch | 入职门槛 |
|---|---|---|---|---|---|
| 1 | **字节跳动** | LLM 算法 + Agent 应用 + AI PM | 大厂 AI 部门 | XHS 23 mention 第一. 豆包 / 国际化业务. P_self GitHub traction + 0-1 全栈直接对标实习生招聘画像. 但 LLM 算法岗对 post-train 经验要求高, P_self 简历偏应用层. **建议主投 LLM 应用 / Agent 工程师方向, 而非 post-train 算法** | 高 |
| 2 | **腾讯** | Agent 开发 + LLM 应用 | 大厂 AI 部门 | XHS 13 mention. 混元 / 微信生态 / 元宝. P_self Lewoo 校园 Agent 经验对腾讯校园 IM 场景天然 fit | 高 |
| 3 | **蚂蚁集团** | 金融 AI 应用 + Agent | 大厂 AI (金融垂直) | XHS 5 mention. **P_self 杀手锏匹配** — 跨域金融+AI 背景在蚂蚁金融 AI 团队稀缺 (帝国理工 DS + 剑桥经济 + 利物浦金融数学 + JobCopilot 与 SAIF 合作). 蚂蚁百宝箱 Agent 产品是核心战略 | 中-高 |
| 4 | **阿里巴巴 (含淘天)** | AI 算法 (推荐/广告) + 通义 LLM 应用 | 大厂 AI | XHS 6 mention. 通义实验室 + 业务侧 AI. P_self 偏 0-1 产品, 阿里业务规模大但实习生定位偏算法 | 中-高 |
| 5 | **百度** | 文心 LLM + Agent + AI PM | 大厂 AI | XHS 6 mention. 文心 + 自动驾驶 + 搜索 AI. P_self Agent 经验对百度搜索 Agent 化转型 fit | 中 |
| 6 | **DeepSeek (深度求索)** | LLM post-train + 推理优化 | 大模型独角兽 | XHS 3+2 = 5 mention. **P_self 必投** — 行业最热但门槛极高 (招的都是 ICML/NeurIPS 一作), P_self 实战项目可能弥补论文短板, 拼一把 | 高 |
| 7 | **小红书** | LLM 应用 + 内容算法 | 互联网公司 AI 业务线 | XHS 2 mention. P_self JobCopilot 跟小红书"信息聚合 + AI 摘要"思路同向. 招 AI 应用开发实习 + 算法 | 中 |
| 8 | **美团** | LLM 应用 (本地生活) + AI 算法 | 大厂 AI 应用层 | XHS 3 mention. AI 应用落地导向, P_self 0-1 应用经验直接对标 | 中 |
| 9 | **TikTok** | LLM 算法 + 应用 (海外) | 出海 AI | XHS 4 mention. P_self 全英语 + 海外教育背景适合, 但要走字节流程, 实习偏少 | 高 |
| 10 | **某 AI 应用初创** (字节/腾讯前员工创业系) | LLM 应用 + Agent + AI PM | Agent / 应用层创业 | XHS"AI 初创 / 北京 AI 初创公司 / 上海明星大模型初创"合计 17 mention. **P_self 重要 backup** — 创业团队对 0-1 全栈实习生需求大, GitHub traction 直接是面试敲门砖 | 低-中 |

---

## 4. P_self 决策建议

### AI PM vs AI 应用开发 — 哪个 conversion 更高?

**结论: AI PM 路径 conversion 更高 (差异化武器在 PM 池更稀缺)**, 但 AI 应用开发是更安稳的 backup, 两边都投是最优策略。

**数据依据**:

1. **PM 池对手**: AI PM 实习池 — 大多数候选人是商科 / 复合背景但缺真实 ship 项目. P_self 4 个 ship 的项目 (JobCopilot 250⭐ + StockRadar 100⭐ + Lewoo + AgentX) 在 PM 池里**头部 5%**. JobCopilot 的"快速推荐 + 异步增强"双阶段架构 + SAIF 学院合作是 senior PM 思维, 实习生池里罕见。
2. **应用开发池对手**: AI 应用开发 / LLM 工程师实习池 — 充斥 ICPC / ACM / 北邮 / 清北 CS 本科. P_self 帝国理工 DS 硕士在 CS 池里 "中上", 但 Lewoo + AgentX + JobCopilot 的工程量集中在业务集成 (RAG / Memory / Tool Calling), **缺少 LLM post-train (SFT/RLHF/DPO) + 推理优化 (Speculative Decoding) 这些XHS 数据显示的 hot sub_cat**. 在这个池里 P_self 是"还可以"但不顶。
3. **XHS 数据交叉验证**: AI bucket 中 161 帖, "AI PM" 直接命中只有 1-2 帖, "Agent 开发 / LLM 应用"命中 5-6 帖, "LLM 算法 / post-train" 命中 15+ 帖 — 算法岗 hc 多但内卷, **PM 岗 hc 少但竞争人少**。

**操作建议**:
- 主投: AI PM (大厂 + 大模型独角兽) — 主线 70% 简历投递
- 次投: LLM 应用 / Agent 工程师 (大厂 + 字节/腾讯/蚂蚁) — 30%
- 不推荐: 算法工程师 (LLM post-train) — 学术门槛过高, ROI 低

### 平台优先级 (按 P_self 投递 ROI 排)

1. **蚂蚁集团** — 跨域金融+AI 命中点最强, 招满立刻投
2. **字节跳动 (AI 应用 + AI PM 方向)** — 头部 + 招得多, 但走 boss/字节官方双通道
3. **腾讯** — 微信 + 元宝 Agent, 跟 Lewoo 校园 Agent 同型
4. **某 AI 应用初创 (Top tier 创业)** — 风险大但 0-1 全栈直接出活, 拿 offer 概率最高 + 给 leadership 机会
5. **DeepSeek** — 拼一把, 即使被拒也是简历亮点
6. **百度 / 美团 / 小红书** — 备选, 走校招主流程
7. **阿里 / TikTok / 华为** — 大厂流程慢, 当 backup

### 必须解决的 1-2 个简历差距

**差距 1: 缺大厂 AI 正式实习 tag**
- 短期不可能补 (实习 6 月才能开始)
- **补救**: 在 GitHub 项目 README 里突出"institutional 客户" — SAIF 合作明确写, "10w 级岗位真实数据"作为 traction 量化指标. JobCopilot 个人简历里加一行"已签学院级合作, 真实学生用户 X 名" (X 等 SAIF 试点跑起来填)
  
**差距 2: 项目都是"个人/小团队" — 缺"在 1000+ 工程师团队里出过 production code"的背书**
- **补救**: 中科创达虽然不是 AI 实习, 但"输出标准化接口给下游优化层"是真实大厂 production 流程经验, **简历里把这个 bullet 顶到中科创达栏目第一条**, 并在 cover letter 解释"虽然不是 AI 实习, 但走过完整 production deliverable 流程"
- 进阶补救: 投递时挑 1-2 个 production code 实习作为短期机会 (4-6 周), 哪怕 unpaid, 拿到大厂 tag 后再投 AI PM

---

## 5. 区分力 sanity check (6 维)

(a) **P1 公募基本面 vs P6 量化私募 — strategy 主轴**: ✅ 完全隔离. P1 → 易方达/华夏/南方; P6 → 灵均/九坤/明汯. 0 cross-leak 在 demo 10 公司清单内.

(b) **P1 公募 vs P3 私募 — institution_tier**: ⚠️ 部分 overlap. P1 → 一线公募; P3 → 头部主观私募 + 高瓴等. 区分点在 institution_tier 而非 strategy_type (两者同属基本面权益), demo 应在 narrative 里突出"公募走规模和流动性, 私募走深度和 conviction".

(c) **P1 买方 vs P2 卖方 — strategy 内部**: ✅ 强区分. P1 → 易方达/嘉实 (公募买方); P2 → 中金/中信建投 (券商研究所卖方). 公司层面 0 overlap, narrative 层面 "买方独狼 vs 卖方社交家" 这条 verbatim 可直接 invoke.

(d) **跨专业 P3 (理工→金融) 友好度**: ✅ 显式. P3 简历直接展示数学+CS 跨域, AI 量化工程师 sub_cat 明确指向理工背景 (sharpe + LSTM/Transformer 经验). 在 P3 推荐 narrative 中应显式 mention "你的数学+量化工具底子, 在 Quantamental 方向是稀缺差异化".

(e) **隐藏亮点挖掘**:
- P1: deal size 80 亿 (高瓴 PE) + 跨 3 部门协调 — 应在公募推荐中 invoke "你的跨部门协调经验, 公募 IC meeting 里能直接转化"
- P2: 38 次客户服务 + 22 场电话会议 + 数据库 2300 数据点 — 应在中金推荐中 invoke "数据库 ownership + 客户密度对应卖方核心能力"
- P3: 模型被 PM 反向 challenge 3 次后修订 — 应在私募推荐中 invoke "承压 + 思辨 = 比典型实习生更接近研究员工作样态"
- P6: backtest 18 分钟降到 7 分钟 (60%) + 4 因子入库 sharpe > 0.8 — 应在九坤/灵均推荐中 invoke "工程能力 + alpha 产出双优, 头部量化看的就是这个"
- P_self: SAIF institutional 合作 + GitHub 350+⭐ + "platform 非 SDK"哲学 — 应在蚂蚁/字节 AI PM 推荐中 invoke

(f) **跨域 P_self (AI) vs P1-P6 (投研) — 7 大类是否真把 AI 跟投研区分开**: ✅ 完全隔离. P_self → 字节/蚂蚁/腾讯/百度 etc., 投研 persona → 易方达/中金/灵均 etc. 0 cross-domain leak. 蚂蚁集团是唯一**潜在 bridge** (因为蚂蚁同时招金融 AI 应用 + 传统金融研究), 但当前 demo 不会把蚂蚁推给 P1 (P1 target 是公募行研, 蚂蚁不属于公募).

### 整体评分: 5/6 ✅ + 1/6 ⚠️ (b 维 P1/P3 同 strategy 但 tier 不同, 需 narrative 显式说明)
