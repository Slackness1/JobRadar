# Phase G — Ground Truth 119 公司 × 全部证据 dump

**生成日期**: 2026-05-28
**总公司数**: 119 (去重)
**总 ground_truth 行**: 236 (公司 × sub_cat 笛卡尔)

**用途**: 学院老师审 ground truth 来源, 验 must_have 标记是否有真实数据支撑。

**Source 标签解释**:
- `saif:YYYY` — 来自 SAIF MF 年度就业报告 (YYYY 年, 该公司在校友流向里出现)
- `xhs:sub_cat:N` — 来自 N 个 XHS 经验帖在该 sub_cat 池里提到此公司
- `demo_v1` — 来自 Phase F demo 评测固定下来的 5 persona 推荐池
- `taxonomy_doc` — 来自 27/29 canonical sub_cat 设计文档的「典型机构」列表
- `common_knowledge:理由` — 来自 LLM 行业常识 (e.g. 高瓴是头部 PE 是公知事实, 但无具体 XHS 帖)

---

## 速查索引 (按 must_have 数 + sub_cat 数排序)

| # | 公司 | tier | must_have sub_cat 数 | 总 sub_cat 数 | 证据来源 |
|---|---|---|---|---|---|
| 1 | 易方达基金 | 一线公募 | 9 | 9 | common_knowledge:头部公募; common_knowledge:头部公募固收; demo_v1; saif:2024; saif:2025; t |
| 2 | 中信证券 | 头部券商研究所 | 8 | 8 | common_knowledge:头部券商; common_knowledge:头部券商自营; common_knowledge:头部券商衍生品; saif:2 |
| 3 | 中金公司 | 头部券商研究所 | 7 | 8 | common_knowledge:头部券商; common_knowledge:头部券商自营; demo_v1; saif:2025; taxonomy_doc |
| 4 | 国泰海通证券 | 头部券商研究所 | 5 | 7 | common_knowledge:头部券商; common_knowledge:头部券商衍生品; saif:2024; taxonomy_doc; xhs:卖方 |
| 5 | 南方基金 | 一线公募 | 5 | 6 | common_knowledge:头部公募; saif:2024; taxonomy_doc; xhs:公募指数研究员:2; xhs:自营FOF:2 |
| 6 | 九坤投资 | 头部量化私募 | 5 | 5 | common_knowledge:头部量化私募; demo_v1; saif:2025; taxonomy_doc; xhs:量化研究员·高频:6 |
| 7 | 华夏基金 | 一线公募 | 5 | 5 | common_knowledge:头部公募; demo_v1; saif:2024; saif:2025; taxonomy_doc; xhs:公募指数研究员: |
| 8 | 字节跳动 | 互联网大厂 | 5 | 5 | common_knowledge:大厂AI; demo_v1; taxonomy_doc; xhs:AI PM:16 |
| 9 | 华泰证券 | 头部券商研究所 | 4 | 6 | common_knowledge:头部券商衍生品; demo_v1; taxonomy_doc; xhs:利率宏观策略:2; xhs:卖方研究员·宏观策略:1; |
| 10 | 嘉实基金 | 一线公募 | 4 | 4 | common_knowledge:头部公募; saif:2025; taxonomy_doc |
| 11 | 明汯投资 | 头部量化私募 | 4 | 4 | common_knowledge:头部量化私募; taxonomy_doc; xhs:量化研究员·高频:1 |
| 12 | 腾讯 | 互联网大厂 | 4 | 4 | demo_v1; xhs:AI PM:3; xhs:多模态推理优化:14 |
| 13 | 鸣石基金 | 头部量化私募 | 4 | 4 | common_knowledge:头部量化私募; taxonomy_doc |
| 14 | 幻方量化 | 头部量化私募 | 3 | 5 | common_knowledge:头部量化私募; taxonomy_doc; xhs:量化研究员·高频:8 |
| 15 | 阿里巴巴 | 互联网大厂 | 3 | 5 | demo_v1; taxonomy_doc; xhs:AI PM:1; xhs:多模态推理优化:1 |
| 16 | 中信建投证券 | 头部券商研究所 | 3 | 4 | common_knowledge:头部券商; common_knowledge:头部券商衍生品; demo_v1; saif:2024; taxonomy_do |
| 17 | 招商证券 | 中型券商研究所 | 3 | 4 | common_knowledge:头部券商; common_knowledge:头部券商衍生品; taxonomy_doc; xhs:卖方研究员·消费医药周期: |
| 18 | 中欧基金 | 一线公募 | 3 | 3 | common_knowledge:头部公募; xhs:财富管理FOF:1 |
| 19 | 平安资产管理 | 保险资管 | 3 | 3 | saif:2024; taxonomy_doc; xhs:利率宏观策略:1 |
| 20 | 招商基金 | 一线公募 | 2 | 5 | common_knowledge:头部公募; taxonomy_doc |
| 21 | 灵均投资 | 头部量化私募 | 2 | 4 | common_knowledge:头部量化私募; demo_v1; taxonomy_doc |
| 22 | 百度 | 互联网大厂 | 2 | 4 | demo_v1; xhs:AI PM:2; xhs:多模态推理优化:2 |
| 23 | 衍复投资 | 头部量化私募 | 2 | 4 | common_knowledge:头部量化私募; taxonomy_doc |
| 24 | DeepSeek | 大模型独角兽 | 2 | 3 | demo_v1; taxonomy_doc; xhs:多模态推理优化:1 |
| 25 | 富国基金 | 一线公募 | 2 | 3 | demo_v1; saif:2025; taxonomy_doc; xhs:财富管理FOF:1 |
| 26 | 工银瑞信基金 | 二线公募 | 2 | 3 | saif:2024; saif:2025; taxonomy_doc |
| 27 | 广发基金 | 一线公募 | 2 | 3 | common_knowledge:头部公募; saif:2024 |
| 28 | 美团 | 互联网大厂 | 2 | 3 | demo_v1; taxonomy_doc; xhs:AI PM:2 |
| 29 | 蚂蚁集团 | 互联网大厂 | 2 | 3 | demo_v1; taxonomy_doc |
| 30 | Citadel | 外资行 | 2 | 2 | common_knowledge:头部对冲基金; taxonomy_doc |
| 31 | 小红书 | 互联网大厂 | 2 | 2 | demo_v1; taxonomy_doc |
| 32 | 平安银行 | 银行系资管 | 2 | 2 | taxonomy_doc; xhs:财富管理FOF:1 |
| 33 | 招商银行 | 银行系资管 | 2 | 2 | taxonomy_doc; xhs:自营FOF:2; xhs:财富管理FOF:1 |
| 34 | 天风证券 | 中型券商研究所 | 1 | 4 | xhs:卖方研究员·宏观策略:1; xhs:卖方研究员·消费医药周期:6; xhs:行业研究员·消费:3 |
| 35 | AI 应用初创 (头部创业) | AI 初创 | 1 | 2 | demo_v1; taxonomy_doc |
| 36 | 宽德投资 | 中型量化私募 | 1 | 2 | taxonomy_doc; xhs:量化研究员·高频:2 |
| 37 | 广发证券 | 中型券商研究所 | 1 | 2 | common_knowledge:头部券商衍生品; taxonomy_doc; xhs:卖方研究员·消费医药周期:11 |
| 38 | Jane Street | 衍生品做市商 | 1 | 1 | common_knowledge:头部做市商; taxonomy_doc |
| 39 | Millennium | 外资行 | 1 | 1 | common_knowledge:头部对冲基金 |
| 40 | Morgan Stanley | 外资行 | 1 | 1 | common_knowledge:头部外资投行; saif:2025 |
| 41 | Optiver | 衍生品做市商 | 1 | 1 | taxonomy_doc; xhs:量化研究员·高频:15 |
| 42 | Point72 | 外资行 | 1 | 1 | saif:2025; taxonomy_doc |
| 43 | 中信保诚基金 | 二线公募 | 1 | 1 | xhs:自营FOF:2 |
| 44 | 中再资产 | 保险资管 | 1 | 1 | demo_v1; taxonomy_doc |
| 45 | 中诚信国际 | 信用评级机构 | 1 | 1 | common_knowledge:头部信用评级 |
| 46 | 信银理财 | 理财子 | 1 | 1 | demo_v1; taxonomy_doc |
| 47 | 兴业证券 | 中型券商研究所 | 1 | 1 | xhs:行业研究员·消费:5 |
| 48 | 华为 | 互联网大厂 | 1 | 1 | taxonomy_doc |
| 49 | 华创证券 | 中型券商研究所 | 1 | 1 | xhs:行业研究员·消费:3 |
| 50 | 华泰联合证券 | 头部券商研究所 | 1 | 1 | common_knowledge:头部投行; taxonomy_doc |
| 51 | 商汤科技 | AI 初创 | 1 | 1 | taxonomy_doc; xhs:多模态推理优化:8 |
| 52 | 国寿投资 | 保险资管 | 1 | 1 | saif:2025 |
| 53 | 大公国际 | 信用评级机构 | 1 | 1 | common_knowledge:头部信用评级 |
| 54 | 平安证券 | 中型券商 | 1 | 1 | taxonomy_doc |
| 55 | 弘毅投资 | 头部PE | 1 | 1 | saif:2025; taxonomy_doc |
| 56 | 德弘资本 | 头部PE | 1 | 1 | saif:2025; taxonomy_doc |
| 57 | 晨壹基金 | 头部PE | 1 | 1 | saif:2025; taxonomy_doc |
| 58 | 永赢基金 | 二线公募 | 1 | 1 | saif:2024; taxonomy_doc |
| 59 | 申万宏源证券 | 中型券商研究所 | 1 | 1 | saif:2024; taxonomy_doc; xhs:卖方研究员·宏观策略:12 |
| 60 | 米哈游 | 互联网大厂 | 1 | 1 | taxonomy_doc |
| 61 | 红杉中国 | 头部VC | 1 | 1 | common_knowledge:头部VC |
| 62 | 联合资信 | 信用评级机构 | 1 | 1 | common_knowledge:头部信用评级 |
| 63 | 融通基金 | 二线公募 | 1 | 1 | taxonomy_doc |
| 64 | 贝莱德 | 外资行 | 1 | 1 | xhs:利率宏观策略:2 |
| 65 | 量派投资 | 中型量化私募 | 1 | 1 | taxonomy_doc |
| 66 | 高瓴资本 | 头部PE | 1 | 1 | demo_v1; saif:2025; taxonomy_doc |
| 67 | 高盛 | 外资行 | 1 | 1 | common_knowledge:头部外资投行 |
| 68 | 兴证全球基金 | 一线公募 | 0 | 2 | common_knowledge:头部公募; saif:2024 |
| 69 | 汇添富基金 | 一线公募 | 0 | 2 | common_knowledge:头部公募; taxonomy_doc |
| 70 | Bank of America | 外资行 | 0 | 1 | saif:2025 |
| 71 | DRW | 衍生品做市商 | 0 | 1 | xhs:量化研究员·高频:2 |
| 72 | IMC | 衍生品做市商 | 0 | 1 | xhs:量化研究员·高频:2 |
| 73 | MiniMax | 大模型独角兽 | 0 | 1 | taxonomy_doc |
| 74 | NVIDIA | 外资行 | 0 | 1 | xhs:多模态推理优化:2 |
| 75 | SIG | 衍生品做市商 | 0 | 1 | xhs:量化研究员·高频:2 |
| 76 | Tower Research | 衍生品做市商 | 0 | 1 | taxonomy_doc |
| 77 | Two Sigma | 外资行 | 0 | 1 | common_knowledge:头部对冲基金 |
| 78 | 世纪前沿 | 中型量化私募 | 0 | 1 | saif:2025 |
| 79 | 东吴证券 | 中型券商研究所 | 0 | 1 | xhs:卖方研究员·消费医药周期:4 |
| 80 | 中国国际金融 | 头部券商研究所 | 0 | 1 | common_knowledge:头部券商 |
| 81 | 中国银河证券 | 中型券商研究所 | 0 | 1 | saif:2024; xhs:卖方研究员·宏观策略:1 |
| 82 | 中国银行 | 银行系资管 | 0 | 1 | xhs:财富管理FOF:1 |
| 83 | 中投公司 | 头部PE | 0 | 1 | saif:2025; taxonomy_doc |
| 84 | 中泰证券 | 中型券商研究所 | 0 | 1 | xhs:行业研究员·消费:2 |
| 85 | 中金基金 | 二线公募 | 0 | 1 | xhs:公募指数研究员:2 |
| 86 | 中银证券 | 中型券商研究所 | 0 | 1 | xhs:卖方研究员·宏观策略:1 |
| 87 | 乾象投资 | 中型量化私募 | 0 | 1 | saif:2025 |
| 88 | 云锋基金 | 头部PE | 0 | 1 | saif:2024 |
| 89 | 京东 | 互联网大厂 | 0 | 1 | common_knowledge:头部电商 |
| 90 | 佳期投资 | 中型量化私募 | 0 | 1 | saif:2024 |
| 91 | 光大永明资产 | 保险资管 | 0 | 1 | taxonomy_doc |
| 92 | 光大证券 | 中型券商研究所 | 0 | 1 | xhs:自营FOF:1 |
| 93 | 兴业银行 | 银行系资管 | 0 | 1 | common_knowledge:头部银行金融市场部 |
| 94 | 凯雷投资 | 头部PE | 0 | 1 | saif:2025 |
| 95 | 华富基金 | 二线公募 | 0 | 1 | taxonomy_doc |
| 96 | 华平投资 | 头部PE | 0 | 1 | saif:2025 |
| 97 | 华泰资产 | 保险资管 | 0 | 1 | xhs:利率宏观策略:1 |
| 98 | 博时基金 | 二线公募 | 0 | 1 | common_knowledge:头部公募 |
| 99 | 因诺资产 | 中型量化私募 | 0 | 1 | saif:2024 |
| 100 | 国信证券 | 中型券商研究所 | 0 | 1 | taxonomy_doc |
| 101 | 国泰基金 | 二线公募 | 0 | 1 | saif:2024 |
| 102 | 国金证券 | 中型券商研究所 | 0 | 1 | xhs:卖方研究员·消费医药周期:3 |
| 103 | 小米 | 互联网大厂 | 0 | 1 | taxonomy_doc |
| 104 | 建设银行 | 银行系资管 | 0 | 1 | xhs:财富管理FOF:1 |
| 105 | 开源证券 | 中型券商研究所 | 0 | 1 | xhs:行业研究员·消费:2 |
| 106 | 拼多多 | 互联网大厂 | 0 | 1 | common_knowledge:头部电商 |
| 107 | 摩根大通 | 外资行 | 0 | 1 | xhs:利率宏观策略:1 |
| 108 | 摩根资产管理 | 外资行 | 0 | 1 | xhs:公募指数研究员:1 |
| 109 | 智谱AI | 大模型独角兽 | 0 | 1 | taxonomy_doc |
| 110 | 月之暗面 | 大模型独角兽 | 0 | 1 | taxonomy_doc |
| 111 | 汇丰晋信基金 | 二线公募 | 0 | 1 | saif:2024 |
| 112 | 淡马锡 | 头部PE | 0 | 1 | saif:2025; taxonomy_doc |
| 113 | 瑞银证券 | 外资行 | 0 | 1 | common_knowledge:头部外资投行 |
| 114 | 网易 | 互联网大厂 | 0 | 1 | xhs:AI PM:1 |
| 115 | 银华基金 | 二线公募 | 0 | 1 | common_knowledge:头部公募 |
| 116 | 锐天投资 | 中型量化私募 | 0 | 1 | saif:2025 |
| 117 | 高瓴量化 | 头部主观私募 | 0 | 1 | common_knowledge:头部主观私募 |
| 118 | 鹏华基金 | 二线公募 | 0 | 1 | saif:2024 |
| 119 | 黑翼资产 | 中型量化私募 | 0 | 1 | xhs:量化研究员·高频:2 |

---

## 每家公司详细证据

### 1. 易方达基金

- **tier**: 一线公募
- **must_have in**: 公募权益研究员, 行业研究员·消费, 公募指数研究员, 公募基金中后台, 信用研究员, 固收+多资产, 利率宏观策略, 资管FOF, 财富管理FOF (9 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: TMT, 医药, 城投, 消费, 金融
- **source 标签**: common_knowledge:头部公募, common_knowledge:头部公募固收, demo_v1, saif:2024, saif:2025, taxonomy_doc, xhs:公募指数研究员:10, xhs:财富管理FOF:1
- **notes**:
  - [公募权益研究员] 全市场公募 AUM 第一,权益条线核心
  - [行业研究员·消费] 易方达消费组业内标杆
  - [公募指数研究员] 宽基 ETF 强,XHS 指数赛道 mention 最多
  - [公募基金中后台] 按行业共识,中后台规模大
  - [信用研究员] 按行业共识,公募固收信用组
  - [固收+多资产] 按行业共识,固收+规模大
  - [利率宏观策略] 按行业共识,公募固收利率组
  - [资管FOF] FOF 公募头部
  - [财富管理FOF] 投顾业务发展中

#### SAIF 校友流向证据 (2 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 易方达基金管理有限公司 | 行业研究员 | 2 | 公募基金 |
| 2025 | 易方达基金管理有限公司 | 行业研究员 | 1 | 公募基金 |

#### XHS 帖证据 (32 条)

**[信用研究员]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/69a8107c000000001](https://www.xiaohongshu.com/discovery/item/69a8107c000000001a0256c1?xsec_token=YBKa6dGSqoDQiE-oV489_9WKftQkmztfGn52RVw7CycAU%3D&xsec_source=app_share)

> 帖内提到的公司: 富国基金, 易方达, 华夏

> **内容快照**:
> 
> 富国基金信用研究员面试包含10道问题，涉及城投债评级上调、信用下沉策略、地产债暴跌、行业规避、审计师变更、信用与权益研究方法论差异、流动性枯竭、公司对比、AI替代、发行人暗示美化评级等场景，并带有追问。
> 
> 信用研究员岗位需要处理评级与风险判断冲突、信用下沉策略、流动性危机、与投资经理沟通、职业道德困境等。
> 
> 富国基金信用研究岗位面试题涉及与易方达、华夏的对比，以及保险资管挖角场景。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 1. 如果某城投债评级上调，但你觉得风险加大，信谁？...10. 如果某发行人暗示'适当美化评级可以合作'，怎么处理？
> - 信用研究员面试真题拆解分析
> - 怎么看富国信用和易方达、华夏的差距？

**[量化研究员·中频]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a0f1f52000000003](https://www.xiaohongshu.com/discovery/item/6a0f1f52000000003700d9ab?xsec_token=YBN2X1RuqB4DDPgcukhFoKeu5T216dC63UAnGIN3ep7CQ%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达基金, 南方基金, 汇添富基金, 华夏基金, 华泰证券, 中信证券

> **内容快照**:
> 
> 易方达基金投研岗笔试挂，行测+英语，70+分数没过，说明投研量化竞争激烈。
> 
> 南方基金指数研究员一面为无领导小组讨论，题目方向未知导致挂。
> 
> 招卡数据分析一面为对抗小游戏，形式有趣。
> 
> yn资产量化研究员期权方向进展到二面hr面，有希望。
> 
> wy资产量化研究员笔试通过但后续流程未定。
> 
> mx投资量化研究员笔试后无消息。
> 
> 作者背景：华五金工本+金融硕，偏量化/研究赛道，3段相关实习（某百亿私募+三中一华投研）。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 易方达基金 投研岗（4.18笔试挂 行测+英语） 70+分数也没过，只能说投研量化太卷了
> - 南方基金 指数研究员（4.29笔试 行测 5.10一面挂）一面无领导小组题目问了完全不知道的方向，遂阵亡
> - 招卡 数据分析（5.17笔试 行测+英语+性格测试+雷霆服从性测试题目 5.18一面）一面是对抗小游戏挺有意思

**[信用研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/699b00c1000000000](https://www.xiaohongshu.com/discovery/item/699b00c1000000000e03f406?xsec_token=YByUaNWdGqni4CccoDmetp9jnkQ79jyEQvtPsYLCsbMVQ%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达基金, 招商银行

> **内容快照**:
> 
> 易方达基金资管投研部门内部竞争激烈，工作强度大，建议谨慎考虑。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 炸了！pa资管投研，竟是这种“卷王”局？内行人做二级固收研究的应该都知道哈哈，内部惨不忍睹，去的话谨慎之～

**[公募基金中后台]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69030995000000000](https://www.xiaohongshu.com/discovery/item/690309950000000007035e51?xsec_token=YB7KmP1aA7MWpAsvmlr-5vKCC2_wHJtpJClFV8BTDdHlQ%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达

> **内容快照**:
> 
> 易方达FOF岗位面试流程：仅一轮面试，面试官为部门负责人，问题包括自我介绍、职业规划、实习课题、沟通能力、地点接受度、保研选择、成绩、暑期return offer、爱好和书籍。通过后需实习两周并答辩，可能还有后续面试。
> 
> 易方达FOF岗位竞争激烈，学生被调剂到中后台。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 流程是自我介绍...反问环节...通过反问得知只有这一轮面试，通过的话要去实习两周，实习答辩之后可能还会有面试！
> - 本来投的是FOF，可惜竞争太激烈给我调剂到中后台去了

**[公募指数研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/67fdf1e2000000000](https://www.xiaohongshu.com/discovery/item/67fdf1e2000000000903976e?xsec_token=YBb0C75mEAOOs50gHFP0g0mDTOabaMQQL8N8lvLgVCYsw%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达

> **内容快照**:
> 
> 易方达指数投资面试流程包括自我介绍、简历行业分析、研究框架、对指数投资的看法、岗位偏好、暑期留用和offer情况、对dirty work的看法等。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 面试流程: 1.自我介绍 2.针对简历中的一个行业做一个简单分析。 3.针对简历中的一份报告，分享一下研究框架和逻辑 4.你对指数投资的看法以及日常生活中是否有指数投资的经历 5.你在过去实习岗位中选择一个岗位，你最喜欢从事什么工作。如果没有的话,你未来希望从事什么工作。 6.暑期留用和目前的offer情况。 7.你对dirty的工作怎么看待？ 8.反问环节

**[公募指数研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a07675d000000021](https://www.xiaohongshu.com/discovery/item/6a07675d000000021000993a?xsec_token=YBCjY5EHPGdGqerro_MisSOSCFQkAIIYO-NrPE8hKk52U%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达

> **内容快照**:
> 
> 易方达暑期实习留用率非常低且实习时间短
> 
> 易方达暑期实习offer，面临线下实习与远程、时间冲突的抉择

> **verbatim 锚点 (T1/T3 抽取)**:
> - 听说留用率非常低而且实习时间实在有点短
> - 收到了易方达暑期实习offer，但是线下给的三个时间段有两个时间人还在国外只能远程，第三个时间段又跟另外一个实习时间撞了

_(+26 条更多帖未展示, 同 sub_cat)_

---

### 2. 中信证券

- **tier**: 头部券商研究所
- **must_have in**: 固收交易员, 卖方研究员·TMT, 卖方研究员·消费医药周期, 卖方研究员·宏观策略, 买方 Quant, 投行 IBD, 自营FOF, 结构化产品衍生品 (8 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: TMT, 医药, 周期, 消费, 金融
- **source 标签**: common_knowledge:头部券商, common_knowledge:头部券商自营, common_knowledge:头部券商衍生品, saif:2025, taxonomy_doc, xhs:卖方研究员·宏观策略:2, xhs:卖方研究员·消费医药周期:10, xhs:自营FOF:2
- **notes**:
  - [固收交易员] FICC 自营交易头部
  - [卖方研究员·TMT] 全市场卖方第一
  - [卖方研究员·消费医药周期] 全行业覆盖
  - [卖方研究员·宏观策略] 全市场宏观首席
  - [买方 Quant] 按行业共识,头部券商自营 Quant
  - [投行 IBD] 按行业共识,A 股 IPO 第一
  - [自营FOF] 券商自营 FOF 头部
  - [结构化产品衍生品] 按行业共识,衍生品做市头部

#### SAIF 校友流向证据 (3 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 中信建投证券股份有限公司 | 卖方分析师 | 1 | 券商研究所 |
| 2025 | 中信证券股份有限公司 | 卖方分析师 | 1 | 券商研究所 |
| 2025 | 中信里昂 | 卖方分析师 | 1 | 券商研究所 |

#### XHS 帖证据 (28 条)

**[买方 Quant]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/695940c8000000001](https://www.xiaohongshu.com/discovery/item/695940c8000000001e03a19c?xsec_token=YBrJ_goExM-LGFpD_KXswc_GrNMq5jKropLNK56upboAU%3D&xsec_source=app_share)

> 帖内提到的公司: 高盛, 摩根士丹利, 中金, 中信里昂, 幻方, 灵均

> **内容快照**:
> 
> 大湾区量化岗位分为卖方Quant（投行）和买方Quant（基金/私募），卖方Quant集中在香港，买方Quant在深圳更活跃。
> 
> 香港的卖方Quant主要集中在国际投行（高盛、摩根士丹利等）和中资投行国际子公司（中金、中信里昂），深圳的卖方机会在国内券商的金融工程/量化自营部门。
> 
> 深圳的买方Quant核心是顶尖量化私募（幻方、灵均等），香港的买方Quant包括全球顶级对冲基金和自营交易公司（Citadel, Two Sigma, Optiver等）。
> 
> 深圳的量化岗位面试必考对国内金融数据源（Wind, Tushare, JoinQuant）和A股交易规则的熟悉度。
> 
> 香港的量化岗位面试对期权定价、随机微积分等理论要求更深。
> 
> 深圳偏好国内顶尖理工院校（清北复交、浙大、中科大等）的硕士/博士，海外名校需对国内市场有理解；香港偏好全球顶级名校（美英顶尖高校、新加坡两所、港三所），专业排名比学校综合排名更重要。
> 
> 纯金融背景竞争力弱，数学、物理、计算机、电子工程等硬核专业是绝对主流。
> 
> 大湾区量化岗位技能要求：Python、SQL、Linux是基础；深圳需精通C++，香港需英语工作能力和kdb+/q等工具。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 在大湾区，两者的重心和机会有显著差异：1. 卖方Quant（以投行为主）：香港是绝对中心...2. 买方Quant（以基金/私募为主）：深圳是核心战场...
> - 国际投行（高盛、摩根士丹利等）及中资投行的国际子公司（中金、中信里昂等）的量化团队主要聚集于香港。
> - 深圳是核心战场：聚集了全国最顶尖、最活跃的量化私募（幻方、灵均等）...香港是国际桥头堡：云集了全球顶级对冲基金和自营交易公司（Citadel, Two Sigma, Optiver等）

**[公募权益研究员]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/69b01b10000000000](https://www.xiaohongshu.com/discovery/item/69b01b10000000000601f681?xsec_token=YB3mubOgxaYuySVOQc18ibYOSsyNMwYBOBRr4DQeL0kMQ%3D&xsec_source=app_share)

> 帖内提到的公司: 工银瑞信, 中信建投基金, 嘉实基金, 天弘基金, 华夏基金

> **内容快照**:
> 
> 公募基金面试通过推票（基本面分析）、近期行情判断（策略框架）、关键行业事件（行业趋势洞察力）、市场风险溢价（宏观分析能力）这四类问题判断候选人综合潜力。
> 
> 公募基金实习阶段通过观察日常工作习惯、课题沟通能力、任务完成程度、工作自驱力判断实习生。
> 
> 公募基金答辩考察候选者能否将研究转化为包含价格与时点的具体观点。
> 
> 公募基金高管面通过观察候选人与上位者的沟通姿态及回答内容，检验职业兴趣和组织稳定度。
> 
> 作者秋招投递了多家公募基金，包括某top3公募（暑期投研）、工银瑞信（拿到pass卡后放弃）、中信建投基金（暑期后放弃）、嘉实基金（简历挂）、天弘基金（面试挂）、华夏基金（简历挂）。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 面试阶段，通过推票（基本面分析）、近期行情判断（策略框架）、关键行业事件（行业趋势洞察力）、市场风险溢价（宏观分析能力）这四类问题能准确判断候选人的综合潜力、职业兴趣、时间投入。
> - 实习中，通过观察日常工作习惯、课题沟通能力、任务完成程度、工作自驱力增加对实习生的深层次判断。
> - 答辩中，通过考察短时间内的输出情况，衡量候选者能否将研究转化为包含价格与时点的具体观点，完成对业务能力的下半场判断。

**[公募权益研究员]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/66c008ec000000000](https://www.xiaohongshu.com/discovery/item/66c008ec00000000050217fb?xsec_token=YBT3yCxG5zxXVT6aBR0cxLsJN2mHc47OD-PlizX-VAnA0%3D&xsec_source=app_share)

> 帖内提到的公司: 农总, 箭头研究所, 中信自营部, top公募, 工银理财

> **内容快照**:
> 
> 买方投研发展路径基本上是在各个买方（公募、私募、保险、券商资管）之间跳，很少有人愿意再回卖方。
> 
> 如果想进入权益投研，简历上必须至少有一份独立完成的个股深度报告，该个股最好200亿市值以上，对该报告有非常深入的研究基础。
> 
> 如果想进入银行管培，在校成绩要好一些，有银行实习最佳，若没有银行实习，校内优秀获奖比赛成果和银行有关联度最好（比如绿色金融、普惠金融、信贷投放研究）。
> 
> 如果想进入理财子，固收、宏观的投研实习经历最佳，对宏观有自己的看法和见解，对金融课本知识掌握扎实。
> 
> 公募投研行业前景和股市强相关，纵向和21年之前相比黯淡，但横向和其他行业相比仍具备较高吸引力。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 买方投研发展路径基本上是在各个买方（公募、私募、保险、券商资管）之间跳，基本上进入买方后很少有人原因再回卖方
> - 如果想进入权益投研：简历上必须至少有一份独立完成的个股深度报告，该个股最好200亿市值以上，对该报告有非常深入的研究基础
> - 如果想进入银行管培：在校成绩要好一些，有银行实习最佳，若没有银行实习，校内优秀获奖比赛成果和银行有关联度最好（比如绿色金融、普惠金融、信贷投放研究）

**[卖方研究员·消费医药周期]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/69f0aa2a000000001](https://www.xiaohongshu.com/discovery/item/69f0aa2a000000001f00110b?xsec_token=YBM4eHPfnRLI_HE6okUGLLCLVqw1NH4xXpzkkb0_R63A8%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, CITIC

> **内容快照**:
> 
> 中信证券暑期实习IB hc保守预计100+，对学历包容，双非本或qs200也有机会进入头部券商。
> 
> 固收业务分为研究、销售与交易，销售主要做债券销售，交易细分做市、自营、资金，研究涉及信评。
> 
> 资管业务助理分为机构销售、研究和交易，研究岗位有机会转投资助理。
> 
> 股衍业务助理分为量化研究和衍生品交易，建议有编程和数据分析背景的同学投递。
> 
> 机构业务助理包含公募、私募、同业等细分方向，面试时各业务线领导参与，表现好的会电话沟通。

> **verbatim 锚点 (T1/T3 抽取)**:
> - CITIC应该是前十券商里面对于学历最包容的，暑期IB hc保守预计100+。
> - 固收业务：分为研究、销售与交易。销售主要是债券销售...交易的话估计里面会细分做市交易、自营交易、资金交易等岗位，研究业务则涉及如信评等方向。
> - 资管业务助理：分为机构销售、研究和交易。研究岗位是对应券商里面资管二级研究...后续会有机会转投资助理。

**[固收+多资产]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a03466a000000000](https://www.xiaohongshu.com/discovery/item/6a03466a000000000702f4c4?xsec_token=YBHOt7zneE8YP4HgVHcNE3uPkUsDCRauMCju0BEuxouic%3D&xsec_source=app_share)

> 帖内提到的公司: yfd, 德邦, 上银, 中银理财, 中邮理财, 信银理财

> **内容快照**:
> 
> 固收赛道相比权益bar略低，但近年越来越卷。
> 
> 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向。
> 
> 实习经历垂直会有一定优势，多段转债量化经历有助于秋招。
> 
> 暑期实习面试中，公募、理财子、券商、私募等均有面试经历，部分挂掉。
> 
> 多数市场化机构在暑期确定名额后秋招不开放。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 固收赛道相比权益bar略低，但是近年越来越卷
> - 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向
> - 实习经历垂直会有一定优势，猜测秋招发面是因为有多段转债量化经历

**[量化研究员·中频]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a0f1f52000000003](https://www.xiaohongshu.com/discovery/item/6a0f1f52000000003700d9ab?xsec_token=YBN2X1RuqB4DDPgcukhFoKeu5T216dC63UAnGIN3ep7CQ%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达基金, 南方基金, 汇添富基金, 华夏基金, 华泰证券, 中信证券

> **内容快照**:
> 
> 易方达基金投研岗笔试挂，行测+英语，70+分数没过，说明投研量化竞争激烈。
> 
> 南方基金指数研究员一面为无领导小组讨论，题目方向未知导致挂。
> 
> 招卡数据分析一面为对抗小游戏，形式有趣。
> 
> yn资产量化研究员期权方向进展到二面hr面，有希望。
> 
> wy资产量化研究员笔试通过但后续流程未定。
> 
> mx投资量化研究员笔试后无消息。
> 
> 作者背景：华五金工本+金融硕，偏量化/研究赛道，3段相关实习（某百亿私募+三中一华投研）。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 易方达基金 投研岗（4.18笔试挂 行测+英语） 70+分数也没过，只能说投研量化太卷了
> - 南方基金 指数研究员（4.29笔试 行测 5.10一面挂）一面无领导小组题目问了完全不知道的方向，遂阵亡
> - 招卡 数据分析（5.17笔试 行测+英语+性格测试+雷霆服从性测试题目 5.18一面）一面是对抗小游戏挺有意思

_(+22 条更多帖未展示, 同 sub_cat)_

---

### 3. 中金公司

- **tier**: 头部券商研究所
- **must_have in**: 利率宏观策略, 卖方研究员·TMT, 卖方研究员·消费医药周期, 卖方研究员·宏观策略, 买方 Quant, 投行 IBD, 结构化产品衍生品 (7 sub_cat)
- **非 must_have (备选) in**: 固收交易员 (1)
- **industry_focus**: TMT, 医药, 消费, 金融
- **source 标签**: common_knowledge:头部券商, common_knowledge:头部券商自营, demo_v1, saif:2025, taxonomy_doc, xhs:卖方研究员·宏观策略:12, xhs:卖方研究员·消费医药周期:4
- **notes**:
  - [固收交易员] 按行业共识
  - [利率宏观策略] 宏观利率研究领军
  - [卖方研究员·TMT] TMT 研究领军
  - [卖方研究员·消费医药周期] 三中一华之一
  - [卖方研究员·宏观策略] 宏观研究领军
  - [买方 Quant] 按行业共识
  - [投行 IBD] 投行业务头部
  - [结构化产品衍生品] 场外衍生品头部

#### XHS 帖证据 (22 条)

**[AI算法业务]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68e12963000000000](https://www.xiaohongshu.com/discovery/item/68e12963000000000400602e?xsec_token=YBoMACpj-L2xybKn7Neuw7-fKkHjNSchL1W07QkUdUvsg%3D&xsec_source=app_share)

> 帖内提到的公司: 中金公司

> **内容快照**:
> 
> 中金金融科技校招面试包括技术面和综合面，技术面涉及A股预测项目的特征工程、随机森林调优、SQL优化、LSTM与ARIMA对比、大规模数据处理等；综合面考察对中金财富管理科技应用、合规效率、机构客户系统等的理解。
> 
> 中金公司金融科技岗面试重视技术落地和业务理解，面试官会问及公司近期科技动态。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 首轮技术面超硬核！被问到A股预测项目的特征工程...二轮综合面更考对公司的理解～被问中金财富管理科技应用...
> - 面试下来感觉中金很看重技术落地和业务理解，宝子们准备时记得多研究公司近期科技动态！

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6809fc99000000001](https://www.xiaohongshu.com/discovery/item/6809fc99000000001c012d5d?xsec_token=YBy6ik79QacPrso0wuHhq2KUUt4upEGUn0CLkZVFRJol4%3D&xsec_source=app_share)

> 帖内提到的公司: 中金公司

> **内容快照**:
> 
> 中金公司设有软件与计算机行业研究团队，属于卖方研究岗位。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 中金公司软件与计算机行业研究团队

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/65dfd9e0000000000](https://www.xiaohongshu.com/discovery/item/65dfd9e00000000001028dcf?xsec_token=YBKkpkcD8lOiSfBRj5IdfiwuYXCMl1mMVcKVypmjqP8zA%3D&xsec_source=app_share)

> 帖内提到的公司: 中金公司

> **内容快照**:
> 
> 中金公司电子组实习机会

> **verbatim 锚点 (T1/T3 抽取)**:
> - #中金电子组

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6995c7c0000000000](https://www.xiaohongshu.com/discovery/item/6995c7c0000000000a0312a0?xsec_token=YBXWiIfnSsvy-8_tzsC6ksG7jxx6bUXQqIru356c4X2-o%3D&xsec_source=app_share)

> 帖内提到的公司: 中金公司

> **内容快照**:
> 
> 中金公司研究员助理面试包含推票、卖方与买方差异、内幕信息处理、深度报告数据获取、应对质疑、行业分析框架、知识积累方法、职业发展准备、公司护城河、报告总结等10个问题。
> 
> 研究员助理岗位属于卖方研究，面试考察推票、行业分析、沟通能力等。
> 
> 中金公司研究部是国内最大的卖方机构。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 1. 请向我推荐一只你看好的股票，并给出三个买入理由（5分钟推票）。2. 卖方研究员和买方研究员的工作核心差异是什么？你更倾向哪个？3. 如果上市公司董秘是你的朋友，你如何处理内幕信息红线？4. 撰写深度报告时，数据来源有限、行业信息不透明，你如何突破？5. 基金经理对你的研究成果提出尖锐质疑，认为你的逻辑有漏洞，你如何应对？6. 请拆解一家消费电子公司的核心竞争力框架。7. 你平时如何积累行业知识？请分享你的信息源和研究方法论。8. 随着职级提升，研究员的精力从“写报告”转向“与投资人沟通”，你对此有何准备？9. 中金研究部是国内最大的卖方机构，你认为它最大的护城河是什么？10. 请用一句话总结你过去实习中写出最好的一篇报告的核心结论。
> - 研究员助理
> - 中金研究部是国内最大的卖方机构

**[卖方研究员·宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69453317000000001](https://www.xiaohongshu.com/discovery/item/69453317000000001b031612?xsec_token=YB24FEpLWuRSTny4nYlb92ndJY24vA_NFM6LihhAUGUUU%3D&xsec_source=app_share)

> 帖内提到的公司: 中金公司

> **内容快照**:
> 
> 中金宏观研究岗面试题，涵盖宏观经济核心矛盾、政策预判、CPI预测、社融分析、数据库使用、央行报告、卖方vs买方研究、信息渠道、职业动机、学习计划等10个问题。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 中金｜宏观研究岗
1. 请简要阐述你对当前中国宏观经济核心矛盾的理解，并对未来一个季度的政策方向做出预判。
2. 如果让你分析“美国经济走势对中国资本市场的影响路径”，你会构建一个怎样的分析框架？
3. 在预测CPI（居民消费价格指数）时，除了翘尾因素，你会重点关注哪些领先或同步指标？请说明理由。◦ 追问：如果实际公布的CPI数据持续大幅偏离市场预期及你的预测，你的复盘和调整分析模型的思路是什么？
4. 你如何理解“社融”数据？它在宏观经济分析中的重要意义是什么？
5. 宏观研究经常需要处理大量数据。你熟练使用哪些数据库（如Wind、CEIC）或计量软件（如Stata、Python）？请简述一个你用其完成分析的小例子。
6. 请用英文简要概括一份你近期阅读的央行货币政策报告（如中国央行或美联储）的核心观点。
7. 卖方宏观研究与买方宏观研究在驱动因素和工作目标上有何不同？你更倾向于哪一种？
8. 你平时主要通过哪些渠道获取和筛选高质量的宏观经济信息与研究观点？
9. 为什么选择宏观研究这个领域？它最吸引你的智力挑战是什么？
10. 作为校招生，你计划如何快速构建起系统的宏观分析能力？

**[卖方研究员·宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69ea2bc2000000001](https://www.xiaohongshu.com/discovery/item/69ea2bc20000000019025c00?xsec_token=YBLcpQ5Ti2EtlH-rkQpUshPH4nebXp24mzuLESjOX8p6s%3D&xsec_source=app_share)

> 帖内提到的公司: 中金公司

> **内容快照**:
> 
> 中金公司研究部宏观研究助理面试问题包括：每天花多少时间阅读财经新闻和研报、毕业论文核心观点、如何持续学习、核心经济指标、社融结构变化、人民币汇率影响因素、通胀分析框架、宏观判断落地到大类资产配置、研究助理日常工作等。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 问题罗列
1. 你每天会花多少时间阅读财经新闻和研报？你主要通过哪些渠道获取信息？
2. 你的毕业论文主题是货币政策，能简单概括一下你的核心观点吗？
3. 卖方研究的工作需要持续输出，压力不小，你如何确保自己能够持续学习，跟上市场变化？
4. 在分析当前国内经济形势时，除了GDP增速，你认为还有哪几个核心指标是必须关注的？
5. 如何理解“社融”数据的结构变化？比如企业中长贷和居民中长贷的增减分别反映了什么？
6. 在研判人民币汇率走势时，国内基本面因素和海外因素（如美联储政策），哪个影响权重更大？
7. 如果让你写一篇关于“通胀”的专题报告，你的常规分析框架会包括哪几个部分？
8. 如何将宏观判断落地到对大类资产配置的具体建议上？比如，如果你看多经济复苏，会建议超配哪些资产？
9. 研究助理的日常工作主要包括哪些？是否有机会在资深分析师的指导下独立撰写报告片段？

_(+16 条更多帖未展示, 同 sub_cat)_

---

### 4. 国泰海通证券

- **tier**: 头部券商研究所
- **must_have in**: 固收交易员, 卖方研究员·TMT, 卖方研究员·宏观策略, 资管FOF, 结构化产品衍生品 (5 sub_cat)
- **非 must_have (备选) in**: 卖方研究员·消费医药周期, 投行 IBD (2)
- **industry_focus**: TMT, 周期, 消费, 金融
- **source 标签**: common_knowledge:头部券商, common_knowledge:头部券商衍生品, saif:2024, taxonomy_doc, xhs:卖方研究员·宏观策略:8, xhs:卖方研究员·消费医药周期:4
- **notes**:
  - [固收交易员] 按行业共识
  - [卖方研究员·TMT] TMT 研究全覆盖
  - [卖方研究员·消费医药周期] 国泰君安+海通合并体
  - [卖方研究员·宏观策略] 宏观研究头部
  - [投行 IBD] 按行业共识
  - [资管FOF] 券商资管 FOF 头部
  - [结构化产品衍生品] 按行业共识

#### XHS 帖证据 (19 条)

**[卖方研究员·宏观策略]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/69b90ca1000000002](https://www.xiaohongshu.com/discovery/item/69b90ca10000000023021f8d?xsec_token=YBYhJN9E0l4EYISbz8EyT45yhJlVJg1vFoGq71jBMKgl8%3D&xsec_source=app_share)

> 帖内提到的公司: 国泰海通, 国泰君安, 海通证券

> **内容快照**:
> 
> 国泰海通暑期实习岗位复杂，涵盖投行、权益研究、固收、机构销售等大类，其中固收销售交易HC最多。
> 
> 国泰君安和海通证券并购整合仍在进行，岗位分布复杂反映了权力重新分配。
> 
> 国泰海通暑期实习期6-10月，长达5个月，不利于海归学生，且投行HC不确定，成本高。
> 
> 国泰海通卡本科学历，对投行实习要求有所放宽。

> **verbatim 锚点 (T1/T3 抽取)**:
> - HC最多的，我认为是固收销售交易（销售交易）这个岗位。
> - 国泰君安和海通证券的并购整合和权力重新分配还在“持续进行”。
> - 今年的实习期是6-10月，可以说非常不利于海归同学们了。

**[公募基金中后台]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69bcd0e1000000001](https://www.xiaohongshu.com/discovery/item/69bcd0e1000000001a035c38?xsec_token=YBn8TO43p-qWCpgiMFhkVlLpWUOLIcupWnN8XtIXuDJBY%3D&xsec_source=app_share)

> 帖内提到的公司: 国泰海通证券资管

> **内容快照**:
> 
> REITs实习岗位职责包括存续期管理、投研体系搭建、项目尽调等
> 
> 国泰海通证券资管提供REITs实习岗位，要求4月中下旬到岗，每周至少3天，在岗3个月可开实习证明，有餐补无工资

> **verbatim 锚点 (T1/T3 抽取)**:
> - 协助基金经理开展REITs存续期全流程管理，包括底层基础设施资产运营监控、合规信息披露支持、投资者关系辅助等；参与REITs投研体系搭建，涵盖行业政策解读、底层资产市场动态分析、估值模型数据校验与参数优化、投研报告撰写等；辅助完成项目尽调资料整理、运营数据可视化呈现、投决会议材料汇编等支持性工作。
> - 4月中下旬到岗，每周至少 3 天，在岗时间3个月开具实习证明。实习生提供每日餐补，无工资补贴

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0ffa47000000003](https://www.xiaohongshu.com/discovery/item/6a0ffa470000000035023ff5?xsec_token=YBW5wlEnp0s0ohdjGrzIcUZSwEuW2KOf2ZdepxHsfM_U4%3D&xsec_source=app_share)

> 帖内提到的公司: 国泰海通

> **内容快照**:
> 
> 国泰海通TMT行研实习岗位职责包括数据库更新、会议纪要、协助研究员完成课题研究和报告写作等。
> 
> 国泰海通是一家头部券商，提供TMT行业研究实习岗位。
> 
> 任职要求包括国内外重点高校本科/硕士在读，TMT相关背景优先，具备金融知识基础和行研实习经历优先。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 定期数据库更新，会议纪要整理；参与投研工作，按照要求完成信息的搜索、整理及分析等任务；协助研究员完成相关行业及公司的课题研究项目，及研究报告写作；掌握行业研究方法后，实习一定时间后可尝试独立攥写研报。
> - 国泰海通TMT行研实习
> - 国内外重点高校本科、硕士在读，专业不限，但具有TMT等相关背景优先，通信、电子、物理、AI等专业的同学优先；具备一定的金融知识基础，有行研实习经历的同学优先。

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a034ce9000000003](https://www.xiaohongshu.com/discovery/item/6a034ce9000000003701f79c?xsec_token=YBiorUJgroJaDhf9F0epy4RzLo8wRybNzyR_-Iqve3CMI%3D&xsec_source=app_share)

> 帖内提到的公司: 国泰海通

> **内容快照**:
> 
> 国泰海通招聘TMT行研实习生，要求实习期不少于3个月，每周4天以上，工作内容包括数据库更新、会议纪要、信息搜集、协助报告等。
> 
> 国泰海通是一家券商，提供行研实习岗位。
> 
> 该岗位聚焦TMT行业，偏好有TMT背景（通信、电子、物理、AI等专业）的学生。
> 
> 加分项包括TMT背景、行研实习经历、金融知识基础。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 国泰海通 TMT行研实习生
> - 国泰海通
> - TMT背景（通信、电子、物理、AI等专业）

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a02b1fc000000003](https://www.xiaohongshu.com/discovery/item/6a02b1fc00000000360304f2?xsec_token=YB9UsTpUMt8TpAjXfIui9LxS4hRlTfcO__0ZhRoYDAkIo%3D&xsec_source=app_share)

> 帖内提到的公司: 国泰海通

> **内容快照**:
> 
> 国泰海通招聘TMT行业研究实习生，要求一周4天以上，实习期不少于3个月，工作内容包括数据库更新、会议纪要、协助研究等，有独立撰写研报机会。
> 
> 国泰海通提供行研实习岗位，支持官邮背调，线下实习可出具实习证明。
> 
> 实习要求包括思维敏锐、数据搜集处理能力、共情能力和积极性、能承受压力接受加班，具有TMT背景优先。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 国泰海通 · TMT行研实习生
> - 支持官邮背调，线下实习可出具实习证明
> - 思维敏锐清晰，具有良好的数据搜集和处理能力

**[卖方研究员·宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a155ee5000000000](https://www.xiaohongshu.com/discovery/item/6a155ee500000000060370b4?xsec_token=YBm3Y5JyYOl3pHQpV1WJCxNhn46VW7xOTfxjgM4W9Vr_U%3D&xsec_source=app_share)

> 帖内提到的公司: 国泰海通

> **内容快照**:
> 
> 国泰海通2026年Q1股权主承销规模94.2亿元同比+528.8%，IPO主承销19家募资45亿元；债券主承销规模3770亿元同比+55.8%排名行业第二；IPO储备项目16家排名行业第一
> 
> 投行研究分析助理、资本市场策略支持、大客户服务协调员、债务融资研究分析员、投行业务数据分析员等实习岗位，base上海、北京、深圳，可部分远程，6月入职
> 
> 要求头部高校金融/经济/会计/法学，有投行或律所实习经验优先，熟练使用Wind、PPT和Excel，对资本市场与企业融资策略有热情，实习3个月起，每周4天+

> **verbatim 锚点 (T1/T3 抽取)**:
> - 2026年Q1公司股权主承销规模94.2亿元同比+528.8%，IPO主承销19家募资45亿元；债券主承销规模3770亿元同比+55.8%排名行业第二；IPO储备项目16家排名行业第一
> - 实习岗位：投行研究分析助理、资本市场策略支持、大客户服务协调员、债务融资研究分析员、投行业务数据分析员
> - 要求：头部高校金融/经济/会计/法学，有投行或律所实习经验优先，熟练使用Wind、PPT和Excel，对资本市场与企业融资策略有热情，实习3个月起，每周4天+

_(+13 条更多帖未展示, 同 sub_cat)_

---

### 5. 南方基金

- **tier**: 一线公募
- **must_have in**: 公募权益研究员, 公募指数研究员, 公募基金中后台, 资管FOF, 自营FOF (5 sub_cat)
- **非 must_have (备选) in**: 固收+多资产 (1)
- **industry_focus**: 周期, 消费, 金融
- **source 标签**: common_knowledge:头部公募, saif:2024, taxonomy_doc, xhs:公募指数研究员:2, xhs:自营FOF:2
- **notes**:
  - [公募权益研究员] 老牌一线公募,中后台招聘量近年抬升
  - [公募指数研究员] ETF 老牌玩家
  - [公募基金中后台] 中后台风控/产品近年扩招
  - [固收+多资产] 按行业共识
  - [资管FOF] 按行业共识
  - [自营FOF] 公募自营 FOF

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 南方基金管理股份有限公司 | 行业研究员 | 1 | 公募基金 |

#### XHS 帖证据 (14 条)

**[行业研究员·消费]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/67e3d5db000000001](https://www.xiaohongshu.com/discovery/item/67e3d5db000000001d01ceac?xsec_token=YB8O0M4reImwTRSyyEvQ9eFgk8SX0hzbL5BmAoxqEf41w%3D&xsec_source=app_share)

> 帖内提到的公司: 南方基金

> **内容快照**:
> 
> 公募投研和交易岗位竞争激烈，大部分申请者都是炮灰，建议基于实习经历选岗。
> 
> 渠道/机构销售岗位HC充足，适合不想面客但想进公募的同学。
> 
> 中后台岗位如风险监控、基金会计等HC有限，但适合够不着投研又不想做销售的同学。
> 
> 基金投顾和理财专员岗位，作者持负面态度。
> 
> 南方基金招聘分布显示公募基金各条线岗位情况。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 大部分申请公募投研&交易的，都是炮灰，年年如此
> - 渠道/机构销售，咱不说这个岗位的好，至少HC还是公募里面很充足的
> - 风险监控岗有3个HC、基金会计+登记结算有3个HC，算的上是‘够不着投研+交易’+‘不想去市场+销售’情况下的合适选择了

**[量化研究员·中频]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a0f1f52000000003](https://www.xiaohongshu.com/discovery/item/6a0f1f52000000003700d9ab?xsec_token=YBN2X1RuqB4DDPgcukhFoKeu5T216dC63UAnGIN3ep7CQ%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达基金, 南方基金, 汇添富基金, 华夏基金, 华泰证券, 中信证券

> **内容快照**:
> 
> 易方达基金投研岗笔试挂，行测+英语，70+分数没过，说明投研量化竞争激烈。
> 
> 南方基金指数研究员一面为无领导小组讨论，题目方向未知导致挂。
> 
> 招卡数据分析一面为对抗小游戏，形式有趣。
> 
> yn资产量化研究员期权方向进展到二面hr面，有希望。
> 
> wy资产量化研究员笔试通过但后续流程未定。
> 
> mx投资量化研究员笔试后无消息。
> 
> 作者背景：华五金工本+金融硕，偏量化/研究赛道，3段相关实习（某百亿私募+三中一华投研）。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 易方达基金 投研岗（4.18笔试挂 行测+英语） 70+分数也没过，只能说投研量化太卷了
> - 南方基金 指数研究员（4.29笔试 行测 5.10一面挂）一面无领导小组题目问了完全不知道的方向，遂阵亡
> - 招卡 数据分析（5.17笔试 行测+英语+性格测试+雷霆服从性测试题目 5.18一面）一面是对抗小游戏挺有意思

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[公募基金中后台]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6683d1fc000000001](https://www.xiaohongshu.com/discovery/item/6683d1fc000000001c026f13?xsec_token=YBKVEpQ0tlhLw8Gyv652cvW9O1sdD3chwnXPSHCkc7fH0%3D&xsec_source=app_share)

> 帖内提到的公司: 南方基金

> **内容快照**:
> 
> 南方基金暑期实习面试包括HR+技术一面和二面，一面问Java基础（继承多态、抽象类接口、垃圾回收），二面问自我介绍、优势、职业规划等。
> 
> 南方基金提供暑期实习offer，时间线从4月投递到6月初OC。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 1、HR+技术 一面：（1）自我介绍？（2）为什么选择南方基金？（3）为什么不投互联网要投基金？（4）Base地？（5）收到了哪些offer？（6）Java里的继承和多态怎样理解？（7）Java的抽象类和接口怎样理解？（8）Java的垃圾回收机制介绍一下？2、二面 10min左右（1）自我介绍（2）你的优势？（3）职业规划？（4）能来实习的时间？（5）反问面试官。
> - 喜报｜南方基金暑期实习offer面经➕时间线

**[公募基金中后台]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/698bfcc7000000001](https://www.xiaohongshu.com/discovery/item/698bfcc7000000001a02afd2?xsec_token=YBYqlx4jX6sBjOie-hszNtW37QqvFLSTxQZeyYgOHH6cY%3D&xsec_source=app_share)

> 帖内提到的公司: 南方基金

> **内容快照**:
> 
> 南方基金投资实习岗位要求研究生及以上学历，经济、金融、财务等相关专业优先，有券商投行、研究所、基金等经验优先，实习期3个月以上，通过基金从业资格和熟练掌握Wind等工具优先。
> 
> 南方基金提供公募基金机构业务投研实习，工作内容包括协助日常工作、参与产品材料制作与更新、产品研究、行业研究等。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 研究生及以上学历在校生：经济、金融、财务等相关专业优先，有券商投行、研究所、基金等经验优先考虑；实习期3个月以上，长期实习优先，尽快到岗；能够熟练使用office等办公软件；认真细致，学习能力强；通过基金从业资格以及熟练掌握Wind等工具优先
> - 协助日常工作；参与产品材料制作与更新，包括数据分析、材料撰写等；协助开展产品研究、行业研究；完成部门交办的其他工作

**[公募基金中后台]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/682558f8000000002](https://www.xiaohongshu.com/discovery/item/682558f8000000002301f165?xsec_token=YBiVXmuq5NjEOn9ToYKnWdSDL37zEcM2W-uy1oRleMyk0%3D&xsec_source=app_share)

> 帖内提到的公司: 南方基金

> **内容快照**:
> 
> 南方基金暑期实习一面为混岗群面，包括自我介绍、抢答、无领导小组讨论和反问环节，氛围轻松，HR专业。
> 
> 面试流程：1分钟自我介绍（姓名、本硕院校专业、籍贯、生日、投递岗位及原因优势、推荐一本书），抢答行为问题和专业名词解释，10分钟无领导小组讨论（近期热点话题），最后反问互动。
> 
> 面试官比较在意gap情况，有正当理由即可。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 总体氛围超nice，是一次很愉快的面试。HR很专业，控场能力强，而且很认真的对待每一个候选人，有时候会开开玩笑，超级无敌大好评！
> - 1⃣️第一部分自我介绍1min（姓名，本硕院校+专业，籍贯，生日，投递的岗位以及原因优势，最后介绍一本你喜欢的书）
2⃣️第二部分抢答（一些行为问题+通俗解释专业名词，只要有同学想回答就都给了机会）
3⃣️第三部分无领导小组讨论10min，每个组最后选出1个主要汇报人（2min），1个副汇报人（补充发言，1min）。题目是一些近期热点话题，专业难度不大，题目还挺有意思的。
4⃣️第四部分反问互动。
> - 感觉面试官会比较在意gap情况，有正当理由即可。

_(+8 条更多帖未展示, 同 sub_cat)_

---

### 6. 九坤投资

- **tier**: 头部量化私募
- **must_have in**: 量化研究员·中频, 量化研究员·高频, 量化开发QD, AI 量化工程师, 量化因子工程师 (5 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: AI 应用层
- **source 标签**: common_knowledge:头部量化私募, demo_v1, saif:2025, taxonomy_doc, xhs:量化研究员·高频:6
- **notes**:
  - [量化研究员·中频] 中频+QD 双线
  - [量化研究员·高频] 国内高频/QD 双强
  - [量化开发QD] QD 主战场之一
  - [AI 量化工程师] 按行业共识,AI 量化方向投入大
  - [量化因子工程师] 因子库规模大

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2025 | 九坤投资 | 量化研究员 | 1 | 量化私募 |

#### XHS 帖证据 (35 条)

**[量化因子工程师]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a0c2659000000003](https://www.xiaohongshu.com/discovery/item/6a0c2659000000003501c0b8?xsec_token=YBWo3_04eqG7GfzDfPD8xw2IDqvAm1GxyL7BT86NKKem8%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 衍复, 灵均, 世纪前沿

> **内容快照**:
> 
> 幻方、九坤、明汯、衍复是量化“四大天王”出海主力，规模700-800亿，香港办公室持续扩招，提供签证担保和外派补贴。
> 
> 灵均2025年以73.51%收益斩获百亿量化业绩冠军，世纪前沿规模跃升至500-600亿，两家香港团队扩张期，对因子挖掘、建模能力强的同学友好。
> 
> 黑翼2025年新获香港9号牌，量派2024年拿下4+9号双牌照，规模突破300亿，入行门槛相对友好。
> 
> 港圈量化求职门槛：名校硕博，数理/计算机/金工背景优先，英文流利是标配。
> 
> 港圈量化优势：行业顶薪+外派补贴+签证担保，国际化投研平台，职业天花板更高。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 幻方 / 九坤 / 明汯 / 衍复：量化“四大天王”出海主力，规模普遍在700-800亿区间...香港办公室持续扩招。提供签证担保和外派补贴
> - 灵均 / 世纪前沿：2025年灵均以73.51%收益斩获百亿量化业绩冠军...世纪前沿规模跃升至500-600亿...两家香港团队均处于扩张期，对因子挖掘、建模能力强的同学非常友好
> - 黑翼 / 量派：黑翼2025年新获香港9号牌...量派2024年拿下4+9号双牌照，2025年规模已突破300亿...入行门槛相对友好

**[AI算法业务]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a143c4d000000000](https://www.xiaohongshu.com/discovery/item/6a143c4d0000000007027cd5?xsec_token=YBOEKqVMqnM_AnNg9CQJFPJZDV7wsSn7MZe4ICqcWEths%3D&xsec_source=app_share)

> 帖内提到的公司: 九坤投资, 至知创新研究院

> **内容快照**:
> 
> 九坤投资旗下至知创新研究院招聘大模型相关岗位，包括算法、工程、产品等方向，加班少，福利好。
> 
> 急招岗位涵盖k8s集群开发、高级运维、C++、数据抓取、数据仓库、量化风险、策略组合管理、行情系统开发、测试开发、agent算法、多模态算法、后端开发、产品经理、AI算法研究员、数据采集、大模型数据策略产品、高级前端、软件采购经理、linux系统开发、高级AI算法、大模型算法研究员等社招岗位，以及算法研究员、模型组合策略管理、风控开发、agent算法、多模态算法、C++、产品经理等实习岗位。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 九坤投资大模型团队扩张，多岗位急招
> - 社招：k8s集群开发专家，高级运维开发，C++，资深数据抓取，高级数据仓库，量化风险，策略组合管理，行情系统开发，测试开发，agent算法，多模态算法专家，后端开发，产品经理，ai算法研究员，数据采集，大模型数据策略产品（对话、创作、医疗），高级前端，高级数据仓库，软件采购经理，linux系统开发，高级ai算法，大模型算法研究员等
实习生：算法研究员，模型组合策略管理，风控开发，agent算法，多模态算法，c++，产品经理等

**[LLM算法post-train]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6900bdaa000000020](https://www.xiaohongshu.com/discovery/item/6900bdaa000000020400bf5a?xsec_token=YBm0oxtHuNRSzuRSEHQ4dsil6z37TMXjGMA0D62V639k4%3D&xsec_source=app_share)

> 帖内提到的公司: 九坤

> **内容快照**:
> 
> 九坤举办线下活动，有AI Lab负责人Dai老师参与交流。
> 
> 学生获得九坤实习offer，岗位是LLM（非量化）。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 跟AI Lab的负责人Dai老师深入交流了一波，从量化、职业规划聊到“认知”，茅塞顿开。
> - 暑期虽然拿了九坤的实习offer（去做LLM，非量化hh）但最后没能成行

**[LLM算法post-train]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69a1b45c000000021](https://www.xiaohongshu.com/discovery/item/69a1b45c000000021b014a3e?xsec_token=YBXSBkrR9hK2aB7N7vy-p-NNjtpaMzZCC0P_pq5sN0J2U%3D&xsec_source=app_share)

> 帖内提到的公司: 九坤投资

> **内容快照**:
> 
> 九坤投资正在招聘大模型算法研究员和量化实现工程师，属于量化私募领域。
> 
> 岗位包括大模型算法研究员（大模型方向）和量化实现工程师（IT方向）。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 九坤投资｜年后第一波热推岗位来袭
> - 大模型算法研究员--大模型方向 量化实现工程师--IT方向

**[PE投后VC行研]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d1b0d0000000001](https://www.xiaohongshu.com/discovery/item/69d1b0d0000000001e00c10c?xsec_token=YBFvgNWcd5CAjkvK1cQKq3vBazPpoWOANjPHw97n3e-xw%3D&xsec_source=app_share)

> 帖内提到的公司: 九坤投资

> **内容快照**:
> 
> 九坤投资创投实习生岗位职责包括行业研究、项目筛选、尽职调查、投资分析和投后管理，要求金融、经济、商业管理或相关专业，有转正机会。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 作为投资方向实习生，你将加入我们的投资团队，参与到投资项目的全流程中，包括市场研究、项目筛选、尽职调查、投资分析和投后管理。

**[PE投后VC行研]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6842ada4000000002](https://www.xiaohongshu.com/discovery/item/6842ada40000000023016755?xsec_token=YB6-GFpLmdf_dDJyVnSfhzJISq9em5Whffu3sGKYAMc8I%3D&xsec_source=app_share)

> 帖内提到的公司: 九坤创投

> **内容快照**:
> 
> 九坤创投是九坤投资旗下的创投平台，学生询问实习体验，暗示其作为实习平台的价值。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 有没有在九坤创投实习的朋友[害羞R][害羞R][害羞R]值不值得去呀[吧唧R][吧唧R]

_(+29 条更多帖未展示, 同 sub_cat)_

---

### 7. 华夏基金

- **tier**: 一线公募
- **must_have in**: 公募权益研究员, 行业研究员·TMT-医药-周期, 公募指数研究员, 公募基金中后台, 固收+多资产 (5 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: TMT, 医药, 消费, 金融
- **source 标签**: common_knowledge:头部公募, demo_v1, saif:2024, saif:2025, taxonomy_doc, xhs:公募指数研究员:3
- **notes**:
  - [公募权益研究员] 多赛道大平台,XHS mention 第二高
  - [行业研究员·TMT-医药-周期] 行业首席齐全
  - [公募指数研究员] ETF 市场份额第一
  - [公募基金中后台] 产品/风控/合规岗大量
  - [固收+多资产] 按行业共识

#### SAIF 校友流向证据 (2 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 华夏基金管理有限公司 | 行业研究员 | 1 | 公募基金 |
| 2025 | 华夏基金管理有限公司 | 行业研究员 | 1 | 公募基金 |

#### XHS 帖证据 (20 条)

**[信用研究员]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/69a8107c000000001](https://www.xiaohongshu.com/discovery/item/69a8107c000000001a0256c1?xsec_token=YBKa6dGSqoDQiE-oV489_9WKftQkmztfGn52RVw7CycAU%3D&xsec_source=app_share)

> 帖内提到的公司: 富国基金, 易方达, 华夏

> **内容快照**:
> 
> 富国基金信用研究员面试包含10道问题，涉及城投债评级上调、信用下沉策略、地产债暴跌、行业规避、审计师变更、信用与权益研究方法论差异、流动性枯竭、公司对比、AI替代、发行人暗示美化评级等场景，并带有追问。
> 
> 信用研究员岗位需要处理评级与风险判断冲突、信用下沉策略、流动性危机、与投资经理沟通、职业道德困境等。
> 
> 富国基金信用研究岗位面试题涉及与易方达、华夏的对比，以及保险资管挖角场景。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 1. 如果某城投债评级上调，但你觉得风险加大，信谁？...10. 如果某发行人暗示'适当美化评级可以合作'，怎么处理？
> - 信用研究员面试真题拆解分析
> - 怎么看富国信用和易方达、华夏的差距？

**[公募权益研究员]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/69b01b10000000000](https://www.xiaohongshu.com/discovery/item/69b01b10000000000601f681?xsec_token=YB3mubOgxaYuySVOQc18ibYOSsyNMwYBOBRr4DQeL0kMQ%3D&xsec_source=app_share)

> 帖内提到的公司: 工银瑞信, 中信建投基金, 嘉实基金, 天弘基金, 华夏基金

> **内容快照**:
> 
> 公募基金面试通过推票（基本面分析）、近期行情判断（策略框架）、关键行业事件（行业趋势洞察力）、市场风险溢价（宏观分析能力）这四类问题判断候选人综合潜力。
> 
> 公募基金实习阶段通过观察日常工作习惯、课题沟通能力、任务完成程度、工作自驱力判断实习生。
> 
> 公募基金答辩考察候选者能否将研究转化为包含价格与时点的具体观点。
> 
> 公募基金高管面通过观察候选人与上位者的沟通姿态及回答内容，检验职业兴趣和组织稳定度。
> 
> 作者秋招投递了多家公募基金，包括某top3公募（暑期投研）、工银瑞信（拿到pass卡后放弃）、中信建投基金（暑期后放弃）、嘉实基金（简历挂）、天弘基金（面试挂）、华夏基金（简历挂）。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 面试阶段，通过推票（基本面分析）、近期行情判断（策略框架）、关键行业事件（行业趋势洞察力）、市场风险溢价（宏观分析能力）这四类问题能准确判断候选人的综合潜力、职业兴趣、时间投入。
> - 实习中，通过观察日常工作习惯、课题沟通能力、任务完成程度、工作自驱力增加对实习生的深层次判断。
> - 答辩中，通过考察短时间内的输出情况，衡量候选者能否将研究转化为包含价格与时点的具体观点，完成对业务能力的下半场判断。

**[量化研究员·中频]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a0f1f52000000003](https://www.xiaohongshu.com/discovery/item/6a0f1f52000000003700d9ab?xsec_token=YBN2X1RuqB4DDPgcukhFoKeu5T216dC63UAnGIN3ep7CQ%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达基金, 南方基金, 汇添富基金, 华夏基金, 华泰证券, 中信证券

> **内容快照**:
> 
> 易方达基金投研岗笔试挂，行测+英语，70+分数没过，说明投研量化竞争激烈。
> 
> 南方基金指数研究员一面为无领导小组讨论，题目方向未知导致挂。
> 
> 招卡数据分析一面为对抗小游戏，形式有趣。
> 
> yn资产量化研究员期权方向进展到二面hr面，有希望。
> 
> wy资产量化研究员笔试通过但后续流程未定。
> 
> mx投资量化研究员笔试后无消息。
> 
> 作者背景：华五金工本+金融硕，偏量化/研究赛道，3段相关实习（某百亿私募+三中一华投研）。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 易方达基金 投研岗（4.18笔试挂 行测+英语） 70+分数也没过，只能说投研量化太卷了
> - 南方基金 指数研究员（4.29笔试 行测 5.10一面挂）一面无领导小组题目问了完全不知道的方向，遂阵亡
> - 招卡 数据分析（5.17笔试 行测+英语+性格测试+雷霆服从性测试题目 5.18一面）一面是对抗小游戏挺有意思

**[PE投后VC行研]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68c3ef80000000001](https://www.xiaohongshu.com/discovery/item/68c3ef80000000001d01281d?xsec_token=YB2AEXN7bWLB4e--Xh8k7ngG1NGrmImThn9I9ofGE0yFM%3D&xsec_source=app_share)

> 帖内提到的公司: 华夏基金

> **内容快照**:
> 
> 华夏基金招聘股权投资投研实习生，要求硕士及以上学历，对一级市场投资有兴趣，实习至少6个月。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 华夏基金 - 股权投资 - 投研实习生招聘

**[公募指数研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a037357000000023](https://www.xiaohongshu.com/discovery/item/6a0373570000000237014125?xsec_token=YBmtjboflUVBOAT3_5rMgI82wKMzw_G5cBWKuc4BFQc0g%3D&xsec_source=app_share)

> 帖内提到的公司: 华夏基金

> **内容快照**:
> 
> 量化岗面试的本质是考察从数据到决策的闭环思维，面试官看重对Smart Beta和因子择时的实战理解，以及过拟合和样本外稳定性的考量。
> 
> 面试中高频问题包括：指数增强与主动量化的区别、跟踪误差控制、因子IC和IR、多因子模型构建、Barra模型风险归因、红利低波指数编制方案等。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 量化岗面试的本质是“从数据到决策的闭环思维”——你能不能在压力下快速识别策略的边界和风险，这才是关键。
> - 1、简单说说你之前在指数研究或量化实习里做过什么？有没有参与过指数成分股调整或Smart Beta策略开发？2、你怎么理解指数增强？跟主动量化相比，核心区别在哪？3、跟踪误差是怎么定义的？你一般怎么控制它？4、说说因子IC和IR的概念？5、你构建过多因子模型吗？6、如果让你设计一个红利低波指数的编制方案，你会考虑哪些因子和加权方式？

**[公募指数研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a1163d5000000003](https://www.xiaohongshu.com/discovery/item/6a1163d5000000003701f9e9?xsec_token=YB-ytYsXaETuxWOMalLnmNS1SieO69lxemP-6F61KY6SY%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达基金, 华夏基金, 南方基金, 中金基金

> **内容快照**:
> 
> 公募REITs迎来指数化时代，易方达、华夏、南方、中金四家基金公司同步申报中证REITs全收益指数基金。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 当公募REITs迎来指数化时代

_(+14 条更多帖未展示, 同 sub_cat)_

---

### 8. 字节跳动

- **tier**: 互联网大厂
- **must_have in**: LLM算法post-train, Agent工程师, 多模态推理优化, AI PM, AI算法业务 (5 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: AI 基础设施, AI 应用层
- **source 标签**: common_knowledge:大厂AI, demo_v1, taxonomy_doc, xhs:AI PM:16
- **notes**:
  - [LLM算法post-train] 豆包 post-train 团队大
  - [Agent工程师] Coze + 豆包 Agent
  - [多模态推理优化] 豆包多模态团队
  - [AI PM] XHS AI PM 第一,16 次
  - [AI算法业务] 抖音推荐算法

#### XHS 帖证据 (23 条)

**[AI PM]** (relevance=0.85) — [https://www.xiaohongshu.com/discovery/item/67ebc3e1000000001](https://www.xiaohongshu.com/discovery/item/67ebc3e1000000001c01f1b7?xsec_token=YBWa4KeVAPAIULbEbAZXtohEB7fLDgjNIzRKmbx1Mtf7g%3D&xsec_source=app_share)

> 帖内提到的公司: 字节跳动, 百度

> **内容快照**:
> 
> 字节面试偏好有owner意识的人，独立拆解问题；熟悉AI产品体验，对趋势有自己见解；能结合体验反馈提出能落地的优化建议。
> 
> AI岗重点问题包括：如何验证功能的效果？用户反馈生成的信息过时，怎么处理？形容自己适合这个岗位的特质？
> 
> 从百度实习到拿下字节豆包AI产品经理岗位。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 字节面试偏好：喜欢有owner意识的人，独立拆解问题；熟悉AI产品体验，对趋势有自己见解（错也没啥）；能结合体验反馈提出能落地的优化建议。
> - AI岗重点问题（建议准备）：如何验证功能的效果？用户反馈生成的信息过时，怎么处理？形容自己适合这个岗位的特质？
> - 从百度实习到拿下字节豆包

**[AI PM]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a034f9d000000000](https://www.xiaohongshu.com/discovery/item/6a034f9d000000000603551e?xsec_token=YBlluoNSTOyvYktIZZFtTURGBTornU2LjPXvOn9tJInqc%3D&xsec_source=app_share)

> 帖内提到的公司: 字节跳动

> **内容快照**:
> 
> 面试官希望候选人有C端经验，但作者过往全是商业化广告经验，无C端经验。
> 
> AI产品经理岗位面试主要围绕产品体验、数据引导、业务价值、实习经历等展开。
> 
> 字节跳动Byteintern项目主动捞人面试AI产品经理岗位。
> 
> 面试官在反问环节给出了培养C端用户sense的建议，并举例说明产品布局和手势设计。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 反问对候选人的预期，结果依旧是希望有C端经验[捂脸R]，恰好过往0个C端经验，全是做商业化广告[失望R]
> - 1️⃣你觉得当前这个产品体验完之后，有哪些地方符合预期，哪些不符合预期...2️⃣通过数据发现用户打开该app后，不知道该如何使用...3️⃣你觉得【灵感】tab在app内承载什么业务价值...4️⃣请介绍一下快手的实习经历...5️⃣这段经历中最大的困难和最让你有成就感的事是什么...6️⃣非业务问题...
> - 没投递该岗，被主动捞的。

**[AI PM]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a11010f000000003](https://www.xiaohongshu.com/discovery/item/6a11010f0000000035028495?xsec_token=YBOoV-Er_cJP2jEogZtajMG3Tje7RhtPqfxa9rj-WUjVE%3D&xsec_source=app_share)

> 帖内提到的公司: 字节跳动

> **内容快照**:
> 
> AI产品经理需要具备工作流拆解能力，能够将复杂任务抽象为可复用的节点库和决策树。
> 
> 字节跳动的工作流优化方向PM具备强大的系统设计能力。
> 
> AI产品经理需要掌握工作流拆解工具和思维模型，如n8n、Zapier、ProcessOn等。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 他把自己经手和研究过的所有工作流项目，都抽象成可复用的节点库、衔接模板和决策树，形成了庞大的产品工作流武器库。
> - 团队新来的AI pm，之前在大厂专攻工作流优化方向。
> - 跟踪前沿：n8n、Zapier、Microsoft Power Automate官方博客 看最新节点设计

**[AI PM]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69e5edfd000000002](https://www.xiaohongshu.com/discovery/item/69e5edfd000000002003aece?xsec_token=YBLMt3ip4-vz5aVXhqvEQ-_U-B6ipwVu1hY0T8uvNLpI8%3D&xsec_source=app_share)

> 帖内提到的公司: 字节跳动

> **内容快照**:
> 
> 面试官从数据归因、产研协作、AI产品数据流向、技术架构等方面进行了深入拷问，展示了技术PM面试的典型问题。
> 
> 产品经理需要具备数据驱动思维、理解C/S架构、前端与后端通信、本地存储与云端数据库等知识。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 碰到技术出身的pm面试官真是好一场酣畅淋漓的拷打qwq
> - 需要搞懂C/S架构，弄清前端是怎么通过请求API接口拿到后端JSON数据的，理清本地存储和云端数据库（MySQL/Redis）的调用边界。

**[AI PM]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/690040a7000000000](https://www.xiaohongshu.com/discovery/item/690040a700000000050390d1?xsec_token=YBopIfnmfPr8iCeuGIfygVQ861mAvi7-Tc7Yof9naKKmw%3D&xsec_source=app_share)

> 帖内提到的公司: 字节跳动

> **内容快照**:
> 
> 字节AI数据平台产品运营面试包括自我介绍、提问和反问三部分，面试官关注候选人上一段AI PM经历中解决的问题和贡献，以及如何推动项目、排优先级、处理跨部门冲突等。
> 
> 面试官询问了英文场景题：当业务部门提出紧急需求但研发和产品团队无人力时，作为运营如何处理。
> 
> 面试官还问了数据权限问题：员工自己可以赋予文档权限会出现什么问题，作为产品如何解决。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 面试分三部分，1自我介绍，希望听到你上一段ai pm的解决的问题和困难，contribution 2提问 3反问
> - 英文：when business unit has given you an urgent requirement but the R&D team and product management team said they don't have more manpower and what would you do as an operation?
> - 数据权限问题：员工自己可以赋予文档的权限，会出现什么问题？你作为产品，怎么解决？

**[AI PM]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69f9eb1b000000002](https://www.xiaohongshu.com/discovery/item/69f9eb1b00000000200392d6?xsec_token=YBBgMKelGpOJtEkcG45mbb_zlQchjxpI_-zYrpb-HHIpU%3D&xsec_source=app_share)

> 帖内提到的公司: 字节跳动

> **内容快照**:
> 
> AI产品经理的技术门槛被提前了，需要懂大模型、知识库问答、Agent、工作流等基础概念。
> 
> 字节跳动明星AI产品的校招PM JD要求技术基础。
> 
> 非计算机专业学生可通过做AI项目实践来证明能力，如课程资料问答助手、简历修改小助手等。
> 
> AI产品经理岗位对技术理解要求提升，但传统产品基本功仍然重要。

> **verbatim 锚点 (T1/T3 抽取)**:
> - AI产品经理的技术门槛被提前了。...你要知道大模型、知识库问答、Agent、工作流、模型效果这些词大概是什么意思。
> - 我分析了字节几个明星AI产品的校招生JD
> - 非计算机专业...关键是证明你愿意学、学得快、能做出东西。...可以从身边场景开始，比如课程资料问答助手、简历修改小助手、论文阅读笔记助手、校园活动信息整理工具。

_(+17 条更多帖未展示, 同 sub_cat)_

---

### 9. 华泰证券

- **tier**: 头部券商研究所
- **must_have in**: 利率宏观策略, 卖方研究员·消费医药周期, 卖方研究员·宏观策略, 结构化产品衍生品 (4 sub_cat)
- **非 must_have (备选) in**: 卖方研究员·TMT, 自营FOF (2)
- **industry_focus**: TMT, 医药, 消费, 金融
- **source 标签**: common_knowledge:头部券商衍生品, demo_v1, taxonomy_doc, xhs:利率宏观策略:2, xhs:卖方研究员·宏观策略:1, xhs:卖方研究员·消费医药周期:4, xhs:自营FOF:1
- **notes**:
  - [利率宏观策略] 利率债首席强
  - [卖方研究员·TMT] TMT 横跨多赛道
  - [卖方研究员·消费医药周期] 消费医药全覆盖
  - [卖方研究员·宏观策略] 宏观+大类资产配置
  - [自营FOF] 券商自营
  - [结构化产品衍生品] 按行业共识

#### XHS 帖证据 (29 条)

**[资管FOF]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/66d3db2c000000001](https://www.xiaohongshu.com/discovery/item/66d3db2c000000001d03972a?xsec_token=YBy75m-S6rLH1bZeeEs-JRHEDf8yT1GtJnWLk-VglRc9Y%3D&xsec_source=app_share)

> 帖内提到的公司: 苏银理财, 江苏银行, 宁银理财, 华泰证券, 南银理财

> **内容快照**:
> 
> 苏银理财是江苏银行的理财子公司，2023年规模翻倍，待遇在江浙地区属于头部，债券投资经理据传能开到60个。
> 
> 面试流程：南京线下，一面群面（自我介绍+评委提问），二面分三场，部分同学加董事长面。一面中评委对量化fof策略衍生品方向的同学更感兴趣。
> 
> 理财子投研岗更偏好量化fof策略等适合理财子资产配置特点的岗位，而非纯权益或纯信用。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 苏银理财在2023年规模翻了接近一倍，虽然待遇不及同城南银理财和华泰证券，在江浙一带仍是二级研究领域的头部之选。待遇上据传债券投资经理能开到60个。
> - 一面是群面，每个人自我介绍，评委以研总、销售总和研究员为主，会针对少数几个感兴趣的人提问（基本是理财子实习过/量化fof策略衍生品这些方向的）。
> - 研总直说更偏好量化fof策略这些，对纯权益没啥需求。从今年开的岗位来看也得到了验证，相较纯权益和纯信用，显著更偏好策略fof这些更适合理财子资产配置特点的岗位。

**[量化研究员·中频]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a0f1f52000000003](https://www.xiaohongshu.com/discovery/item/6a0f1f52000000003700d9ab?xsec_token=YBN2X1RuqB4DDPgcukhFoKeu5T216dC63UAnGIN3ep7CQ%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达基金, 南方基金, 汇添富基金, 华夏基金, 华泰证券, 中信证券

> **内容快照**:
> 
> 易方达基金投研岗笔试挂，行测+英语，70+分数没过，说明投研量化竞争激烈。
> 
> 南方基金指数研究员一面为无领导小组讨论，题目方向未知导致挂。
> 
> 招卡数据分析一面为对抗小游戏，形式有趣。
> 
> yn资产量化研究员期权方向进展到二面hr面，有希望。
> 
> wy资产量化研究员笔试通过但后续流程未定。
> 
> mx投资量化研究员笔试后无消息。
> 
> 作者背景：华五金工本+金融硕，偏量化/研究赛道，3段相关实习（某百亿私募+三中一华投研）。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 易方达基金 投研岗（4.18笔试挂 行测+英语） 70+分数也没过，只能说投研量化太卷了
> - 南方基金 指数研究员（4.29笔试 行测 5.10一面挂）一面无领导小组题目问了完全不知道的方向，遂阵亡
> - 招卡 数据分析（5.17笔试 行测+英语+性格测试+雷霆服从性测试题目 5.18一面）一面是对抗小游戏挺有意思

**[AI 量化工程师]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/698f41fb000000000](https://www.xiaohongshu.com/discovery/item/698f41fb000000000a028ea7?xsec_token=YBfaOPkjFA_lzkwp3ZyjgHU8AeRhp_D9J1quG_pQE5GTM%3D&xsec_source=app_share)

> 帖内提到的公司: 华泰证券

> **内容快照**:
> 
> 华泰证券Fintech专项面试题包含量化交易、AI应用、手撕代码等，涉及深度学习在量化交易中的局限和过拟合问题。
> 
> 华泰证券设有Fintech专项岗位，强调科技驱动，关注数字化产品如涨乐财富通、行知、机构服务。
> 
> 金融科技岗需要同时对接业务、产品、开发，向不懂技术的业务同事解释技术边界。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 深度学习在量化交易中的应用有哪些局限？你怎么解决过拟合问题？
> - 华泰强调'科技驱动'，你关注过华泰的哪些数字化产品或技术成果？
> - 金融科技岗往往需要同时对接业务、产品、开发，你如何向不懂技术的业务同事解释技术边界？

**[AI算法业务]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/689476a3000000000](https://www.xiaohongshu.com/discovery/item/689476a3000000000500889c?xsec_token=YBSuiLLlWmnNdbQJeMT5agM073YWl8XSUcTFYUmj9oo5U%3D&xsec_source=app_share)

> 帖内提到的公司: 华泰证券

> **内容快照**:
> 
> 华泰证券Fintech数分一面面试问题包括自我介绍、简历提问、统计知识（第一类错误和第二类错误、ANOVA、t检验）、Python（滚动平均）、SQL（连接、having）、业务分析（用户活跃度下降原因）、对金融机构数字化工作的了解等。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 1.自我介绍 2.对简历中感兴趣的地方提问 3.第一类错误和第二类错误 4.ANOVA怎么分析，F统计量怎么构建 5.如何检验两组学生成绩是否有差异 6.t统计量一般用在哪 7.Python：如何计算七天滚动平均股价 8.SQL：说一下不同连接方式 9.SQL：having怎么用 10.发现涨乐财富通用户月活跃度下降，怎么分析 11.你认为金融机构有哪些工作可以进行数字化的 12.除了研究所，对金融机构其他行业有了解吗

**[AI算法业务]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/695d1eb7000000000](https://www.xiaohongshu.com/discovery/item/695d1eb7000000000a03c76d?xsec_token=YBrmTdVctPPyl7QovJaKaV_d7-SJ7pUrrFnv6XbaJQrSw%3D&xsec_source=app_share)

> 帖内提到的公司: 华泰证券

> **内容快照**:
> 
> 华泰证券金融科技AI算法工程师面试题目，涵盖BERT模型优化、实体识别、智能投顾推荐模型、知识图谱构建、边缘部署等。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 华泰证券｜金融科技｜AI算法工程师面经🔥

**[AI算法业务]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0f0a69000000003](https://www.xiaohongshu.com/discovery/item/6a0f0a69000000003700e3ef?xsec_token=YBXGkaz5NY9trOpaKRilNLhSjDer5GGcPcyYeefv5QQGc%3D&xsec_source=app_share)

> 帖内提到的公司: 华泰证券

> **内容快照**:
> 
> 华泰证券推出AI专项人才储备计划，面向全球本硕博，提供现金奖励和校招终面直通机会，涉及Agent、RAG、智能投研、大模型等前沿课题。
> 
> 竞赛流程包括报名、线上笔试、线下面试（报销差旅）、实习考察和课题答辩，优胜奖和入围奖均可直通校招终面。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 华泰证券 AI专项人才储备计划
> - 优胜奖（2万元奖金+直通校招终面）、入围奖（1万元奖金+直通校招终面）

_(+23 条更多帖未展示, 同 sub_cat)_

---

### 10. 嘉实基金

- **tier**: 一线公募
- **must_have in**: 公募权益研究员, 行业研究员·消费, 公募指数研究员, 公募基金中后台 (4 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: TMT, 消费, 金融
- **source 标签**: common_knowledge:头部公募, saif:2025, taxonomy_doc
- **notes**:
  - [公募权益研究员] 权益+消费组传统强项
  - [行业研究员·消费] 消费白酒/CXO 调研深
  - [公募指数研究员] 按行业共识,指数基金重要参与方
  - [公募基金中后台] 按行业共识

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2025 | 嘉实基金管理有限公司 | 行业研究员 | 1 | 公募基金 |

#### XHS 帖证据 (4 条)

**[公募基金中后台]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/69fd52e9000000001](https://www.xiaohongshu.com/discovery/item/69fd52e9000000001f003428?xsec_token=YBMr_thyXngm8ptqzFbVrNffoOvo0uEZPmz9__XqZxGVg%3D&xsec_source=app_share)

> 帖内提到的公司: 嘉实基金

> **内容快照**:
> 
> 嘉实基金面试中面试官深挖实习经历，特别是AI战略项目，追问成果如何落地，强调要准备好交付物。
> 
> 面试官询问基金会计与普通会计的区别，学生回答基金会计以产品为核算主体算净值，企业会计看整体利润。
> 
> 面试官问及基金运营变化少是否会无聊，学生回答“宁慢勿错，返工成本更高”，强调责任心。
> 
> 嘉实基金是公募基金，学生认为比券商更稳定，路径更清晰。
> 
> 学生有事务所、券商投行、四大咨询、财务审计和嘉实实习经历，以及“互联网+”省金和市调大赛国三。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 面试官追问“成果怎么落地的？”——大家准备类似项目一定要想清楚交付物是什么！
> - 基金会计是以“产品”为核算主体，算净值；企业会计看整体利润。
> - 宁慢勿错，返工成本更高

**[公募权益研究员]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/69b01b10000000000](https://www.xiaohongshu.com/discovery/item/69b01b10000000000601f681?xsec_token=YB3mubOgxaYuySVOQc18ibYOSsyNMwYBOBRr4DQeL0kMQ%3D&xsec_source=app_share)

> 帖内提到的公司: 工银瑞信, 中信建投基金, 嘉实基金, 天弘基金, 华夏基金

> **内容快照**:
> 
> 公募基金面试通过推票（基本面分析）、近期行情判断（策略框架）、关键行业事件（行业趋势洞察力）、市场风险溢价（宏观分析能力）这四类问题判断候选人综合潜力。
> 
> 公募基金实习阶段通过观察日常工作习惯、课题沟通能力、任务完成程度、工作自驱力判断实习生。
> 
> 公募基金答辩考察候选者能否将研究转化为包含价格与时点的具体观点。
> 
> 公募基金高管面通过观察候选人与上位者的沟通姿态及回答内容，检验职业兴趣和组织稳定度。
> 
> 作者秋招投递了多家公募基金，包括某top3公募（暑期投研）、工银瑞信（拿到pass卡后放弃）、中信建投基金（暑期后放弃）、嘉实基金（简历挂）、天弘基金（面试挂）、华夏基金（简历挂）。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 面试阶段，通过推票（基本面分析）、近期行情判断（策略框架）、关键行业事件（行业趋势洞察力）、市场风险溢价（宏观分析能力）这四类问题能准确判断候选人的综合潜力、职业兴趣、时间投入。
> - 实习中，通过观察日常工作习惯、课题沟通能力、任务完成程度、工作自驱力增加对实习生的深层次判断。
> - 答辩中，通过考察短时间内的输出情况，衡量候选者能否将研究转化为包含价格与时点的具体观点，完成对业务能力的下半场判断。

**[固收+多资产]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a1412f6000000003](https://www.xiaohongshu.com/discovery/item/6a1412f60000000035026264?xsec_token=YBvwRkObOi4aSrmUEd6aEB7by_6ktiqvnNF4WYNWt7fSU%3D&xsec_source=app_share)

> 帖内提到的公司: 嘉实资本

> **内容快照**:
> 
> 嘉实资本招聘另类固收+实习生，要求具备固收知识框架，理解久期、收益率曲线等概念。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 具备基础的固收知识框架：理解久期、收益率曲线等基本概念

**[行业研究员·消费]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68523924000000002](https://www.xiaohongshu.com/discovery/item/685239240000000022028983?xsec_token=YB1tOVHt4MrRCgE3YRmfKUfzkX4Zhwklu8QU9qotk8kHY%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达, 华夏, 博时, 国泰, 汇添富, 南方

> **内容快照**:
> 
> 易方达、华夏是头部公募，整体待遇好，科技岗位应届生薪资尤其高。
> 
> 博时、国泰、汇添富、南方类似公务员氛围。
> 
> 银行系公募（招商、中银、工银）薪资相对固化，待遇提升空间有限，但工作相对安逸。
> 
> 永赢、嘉实、鹏华待遇不错，但工作强度卷王级别。
> 
> 兴全待遇不错，人少资源多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 易方达、华夏：头部中的头部，整体待遇不会太差，据说科技岗位应届生薪资对比其他应届会尤其高一些
> - 博时、国泰、汇添富、南方：据说类似公务员氛围浓厚
> - 银行系包括（招商、中银、工银等）薪资相对固化，待遇可提升空间对比其他就不太行了，安逸也是相对的吧

---

### 11. 明汯投资

- **tier**: 头部量化私募
- **must_have in**: 量化研究员·中频, 量化开发QD, AI 量化工程师, 量化因子工程师 (4 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: AI 应用层
- **source 标签**: common_knowledge:头部量化私募, taxonomy_doc, xhs:量化研究员·高频:1
- **notes**:
  - [量化研究员·中频] 百亿量化老牌
  - [量化开发QD] C++ 系统开发
  - [AI 量化工程师] 按行业共识
  - [量化因子工程师] 因子工程主战场

#### XHS 帖证据 (19 条)

**[量化因子工程师]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a0c2659000000003](https://www.xiaohongshu.com/discovery/item/6a0c2659000000003501c0b8?xsec_token=YBWo3_04eqG7GfzDfPD8xw2IDqvAm1GxyL7BT86NKKem8%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 衍复, 灵均, 世纪前沿

> **内容快照**:
> 
> 幻方、九坤、明汯、衍复是量化“四大天王”出海主力，规模700-800亿，香港办公室持续扩招，提供签证担保和外派补贴。
> 
> 灵均2025年以73.51%收益斩获百亿量化业绩冠军，世纪前沿规模跃升至500-600亿，两家香港团队扩张期，对因子挖掘、建模能力强的同学友好。
> 
> 黑翼2025年新获香港9号牌，量派2024年拿下4+9号双牌照，规模突破300亿，入行门槛相对友好。
> 
> 港圈量化求职门槛：名校硕博，数理/计算机/金工背景优先，英文流利是标配。
> 
> 港圈量化优势：行业顶薪+外派补贴+签证担保，国际化投研平台，职业天花板更高。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 幻方 / 九坤 / 明汯 / 衍复：量化“四大天王”出海主力，规模普遍在700-800亿区间...香港办公室持续扩招。提供签证担保和外派补贴
> - 灵均 / 世纪前沿：2025年灵均以73.51%收益斩获百亿量化业绩冠军...世纪前沿规模跃升至500-600亿...两家香港团队均处于扩张期，对因子挖掘、建模能力强的同学非常友好
> - 黑翼 / 量派：黑翼2025年新获香港9号牌...量派2024年拿下4+9号双牌照，2025年规模已突破300亿...入行门槛相对友好

**[AI 量化工程师]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69881a22000000000](https://www.xiaohongshu.com/discovery/item/69881a220000000009038dd9?xsec_token=YBZKMi6mNP8rkkAMkJaSGdrwiU8D253dPqKAbEemyh7o4%3D&xsec_source=app_share)

> 帖内提到的公司: 明汯投资

> **内容快照**:
> 
> 明汯投资是一家头部量化私募，管理规模超500亿元，招聘量化研究、量化开发、AI算法研究、AI基础架构开发等实习生岗位，薪资800-1500元/天。
> 
> 量化研究实习生、量化开发实习生、AI算法研究实习生、AI基础架构开发实习生，均为量化相关岗位，可转正。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 明汯投资于2014年在上海成立，借助强大的数据挖掘、统计分析和技术研发能力，构建了覆盖全周期、多策略、多品种的量化资产管理平台。公司管理规模位居行业前列，并成为国内较早一批管理规模突破500亿元的量化私募管理人。
> - 量化研究实习生、量化开发实习生、AI算法研究实习生、AI基础架构开发实习生（4各岗位均可转正！）

**[AI 量化工程师]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69bcd95c000000001](https://www.xiaohongshu.com/discovery/item/69bcd95c000000001a037fb1?xsec_token=YBmWuq3vGdmXfbEZuwBird_rJddJs6so8GHFXZ1jVi31s%3D&xsec_source=app_share)

> 帖内提到的公司: 明汯投资

> **内容快照**:
> 
> 明汯投资是国内量化头部机构，2014年成立，投研团队超100人，核心团队来自海外顶尖对冲基金，策略以量价因子和机器学习为核心。
> 
> 量化投资行业，明汯2025年全线产品业绩突出，500指增超额20.09%，量化多头胜率91.67%，多策略对冲胜率100%。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 2014年成立，华尔街大佬裘慧明博士创立，妥妥的量化圈资深玩家！投研团队超100人，还有纽约团队协同，偏数据和机器学习，全球视野拉满
> - 2025年全线产品业绩直接拉满，顶级管理规模稳轻松拿捏，极端行情下超额依旧能打

**[AI 量化工程师]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0dd22b000000003](https://www.xiaohongshu.com/discovery/item/6a0dd22b000000003700e861?xsec_token=YBm4Y5lD0UeO4fv4xPCt09ZzZHE6ETWMcmH7G7sBIEw0Y%3D&xsec_source=app_share)

> 帖内提到的公司: 明汯

> **内容快照**:
> 
> 明汯是国内最早把深度学习（AI）大规模应用于量化交易的机构之一，策略迭代周期被压缩到极致，用海量GPU挖掘非线性规律。
> 
> 量化私募行业强调数据挖掘和算法，更像人工智能科技公司。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 明汯是国内最早把深度学习（AI）大规模应用于量化交易的机构之一。他们不满足于传统的线性模型，而是用海量GPU去挖掘海量数据中的非线性规律。
> - 这种对数据挖掘的偏执，让他们更像是一家披着私募外壳的人工智能科技公司。

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a08269a000000003](https://www.xiaohongshu.com/discovery/item/6a08269a000000003803740b?xsec_token=YBg-qzj9nuc27NM7UiNCrdMe8mhPU84fAi2YVlMCQUvgI%3D&xsec_source=app_share)

> 帖内提到的公司: 明汯, 衍复, 灵均, 九坤

> **内容快照**:
> 
> 用户询问量化私募哪个好，提及明汯、衍复、灵均、九坤等头部量化私募。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 量化私募哪个好？

_(+13 条更多帖未展示, 同 sub_cat)_

---

### 12. 腾讯

- **tier**: 互联网大厂
- **must_have in**: LLM算法post-train, Agent工程师, 多模态推理优化, AI PM (4 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: AI 基础设施, AI 应用层
- **source 标签**: demo_v1, xhs:AI PM:3, xhs:多模态推理优化:14
- **notes**:
  - [LLM算法post-train] 混元大模型
  - [Agent工程师] 元宝/微信 Agent
  - [多模态推理优化] XHS 多模态 mention 第一
  - [AI PM] 元宝/混元 PM

#### XHS 帖证据 (24 条)

**[多模态推理优化]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/69f2aec7000000001](https://www.xiaohongshu.com/discovery/item/69f2aec7000000001e00f159?xsec_token=YB9cakfPZQAKbBRDQPm_FHgujSHc3NtQN-od-sT3r-hvE%3D&xsec_source=app_share)

> 帖内提到的公司: 腾讯

> **内容快照**:
> 
> 腾讯基座大模型算法面试涉及多模态数据处理、数据集构建、强化训练等，最终挂了，部门更偏向数据驱动而非方法驱动。
> 
> 腾讯基座大模型算法岗位要求多模态数据处理、大规模数据处理、强化训练经验。
> 
> 腾讯基座大模型算法部门更偏向数据驱动而非方法驱动，招聘要求高（青云级别）。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 腾讯基座大模型算法凉经-还是得练
> - 腾讯基座大模型算法
> - 大概只收青云，整个部门更像数据驱动而不是方法驱动

**[AI PM]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a080031000000003](https://www.xiaohongshu.com/discovery/item/6a0800310000000035025bda?xsec_token=YBHpO6TxgKQiQyngY28wFBJcaEpoZPIMzApQWCPTGDSj4%3D&xsec_source=app_share)

> 帖内提到的公司: 腾讯, 字节

> **内容快照**:
> 
> 腾讯AI产品经理（2-5年经验）月薪35K-55K+，全年16-18薪，总包约70W-100W。
> 
> 腾讯AI产品面试不深挖Transformer推导，但要求清晰回答AI能力上限、出错情况、兜底方案；必须掌握监督/无监督/强化学习适用场景、模型幻觉成因与mitigation（如RAG、提示词约束）、SFT与RLHF成本对比。
> 
> 腾讯AI产品面试会追问成本问题：调用混元API vs 自建小模型 vs 规则，哪个划算？需要量化延迟、吞吐、单次调用成本、bad case人工审核成本。
> 
> 腾讯AI产品面试要求PRD包含准确率目标（如95%）、人工兜底链路、bad case闭环流程、ROI测算。
> 
> 腾讯AI产品面试会考察数据验证能力：模型迭代后准确率从92%提到94%，但延迟增加200ms，用户留存怎么变？需要权衡效果、体验、成本。
> 
> 腾讯AI产品面试会深挖如何让算法团队优先解决你的bad case，考察跨部门协同能力。
> 
> 腾讯内部AI项目常被挑战：“不用AI能不能做？”需要回答为什么非用AI不可，规则引擎哪里不够。
> 
> 腾讯AI产品核心逻辑：AI不是功能，是解决用户问题的手段。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 腾讯AI产品（2-5年经验）月薪35K-55K+是主流，全年16-18薪，总包约70W-100W。
> - 腾讯面试不深挖Transformer推导，但要求你清晰回答：这个AI能力上限在哪？会出什么错？怎么兜底？必须掌握：监督/无监督/强化学习的适用场景区别、模型幻觉的成因与 mitigation（如RAG、提示词约束）、SFT与RLHF的成本对比。
> - 你会被追问：“调用混元API vs 自建小模型 vs 规则，哪个划算？”答不出延迟、吞吐、单次调用成本、bad case人工审核成本的量化对比，直接扣分。

**[AI PM]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a13ae5a000000003](https://www.xiaohongshu.com/discovery/item/6a13ae5a0000000036030597?xsec_token=YB37OyhD0Jekrxv5MFZwIhyjS8W5MAw2RgfWP2EoDZTq8%3D&xsec_source=app_share)

> 帖内提到的公司: 腾讯

> **内容快照**:
> 
> AI产品经理需要具备需求分析能力，使用四层漏斗框架过滤伪需求、定义真问题、权衡方案、预演成功与风险。
> 
> 腾讯的AI产品总监展示了需求分析的方法论，强调从模糊需求中抽取出核心问题。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 在腾讯做AI需求必用的四层漏斗框架：第一层：伪需求过滤...第二层：真问题定义与量化...第三层：方案权衡与设计...第四层：成功预演与风险备案...
> - 我们组空降了一位腾讯来的AI产品总监。首次需求评审会上，就让我们见识了什么叫降维打击

**[AI PM]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68e0078c000000000](https://www.xiaohongshu.com/discovery/item/68e0078c00000000030367f3?xsec_token=YB4kCMNLlBhyABM5NAl5IKzZkXEa1HRdkAodl_g-8ZBy4%3D&xsec_source=app_share)

> 帖内提到的公司: 腾讯, 阿里

> **内容快照**:
> 
> 用户询问腾讯、阿里等大厂对AI产品经理的偏好，表明自己9本海硕背景，担心不被接受。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 到底喜欢什么样的ai产品经理啊 现在腾讯 阿里等大厂的ai产品到底喜欢什么样的人啊！想去大厂，9本海硕能接受不，太难了

**[PE投后VC行研]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/67c9867a000000001](https://www.xiaohongshu.com/discovery/item/67c9867a000000001201db42?xsec_token=YBFDYLgynpticLgEssNPPvOocryLGEO-mvax9hbjIGL7Y%3D&xsec_source=app_share)

> 帖内提到的公司: 腾讯

> **内容快照**:
> 
> 面试官关注实习总结的takeaway，会不断追问，对具体做的事情不太关心。
> 
> 面试中问到三个优点和三个缺点，缺点需要既真诚又无伤大雅。
> 
> 投资拉美市场高科技产业的分析框架：先定义高科技，看宏观指标（GDP增速、通胀）、人口年龄结构、基础设施建设、政策不确定性。
> 
> 如何找到当地VC机构对接：查股权结构、找出海投资咨询公司、行业报告、参加峰会。
> 
> 实习生受限于合规不会上项目，更多是提供宏观分析、市场分析等support。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 面试官对于每段实习做的具体事情不太关心，只关注总结的takeaway，会不断追问
> - 有点怪的点是要说的缺点有点多（？），一时想不出那么多既真诚又无伤大雅的缺点
> - 先clarify具体高科技的定义，涵盖哪些产业？之后看宏观指标，例如GDP增速、通货膨胀等等...然后高科技产业年轻人消费接受度更高更快...然后是基础建设...最后指出宏观政策的不确定性，尤其是关税

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

_(+18 条更多帖未展示, 同 sub_cat)_

---

### 13. 鸣石基金

- **tier**: 头部量化私募
- **must_have in**: 量化研究员·中频, 量化开发QD, AI 量化工程师, 量化因子工程师 (4 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: AI 应用层
- **source 标签**: common_knowledge:头部量化私募, taxonomy_doc
- **notes**:
  - [量化研究员·中频] 百亿量化,AI 量化方向激进
  - [量化开发QD] QD 招聘强
  - [AI 量化工程师] AI 量化博士 70-100W·20薪
  - [量化因子工程师] 按行业共识

#### XHS 帖证据 (15 条)

**[AI 量化工程师]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6979e092000000000](https://www.xiaohongshu.com/discovery/item/6979e092000000000e00ecd4?xsec_token=YBcuSm_5RG5FDUoAFBOZevRYeSV5FHW4EUxezGcMitvXE%3D&xsec_source=app_share)

> 帖内提到的公司: 鸣石基金

> **内容快照**:
> 
> 鸣石基金是头部量化私募，成立于2010年，管理规模超百亿，拥有AI实验室和超算中心。
> 
> 校招岗位包括量化因子工程师、AI量化工程师、Quantitative Research、量化开发工程师等，面向2026届全职和2027届实习。
> 
> 建议在简历中突出算法、数据建模、编程（C++/Python）相关项目或竞赛经历。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 鸣石基金成立于2010年（中国量化元年），深耕量化领域15年，资产管理规模于2020年突破100亿。公司旗下设有人工智能实验室“创世纪AI实验室（G-LAB）”，专注于全流程量化策略研发与AI金融应用创新，并自建超算中心“星座计划”。
> - 研究员序列（全职/实习）：量化因子工程师、AI量化工程师、Quantitative Research（Monetization & Optimization）；工程师序列（全职）：量化开发工程师（C++）。
> - 超算资源与AI实验室是核心优势，建议在简历中突出相关项目或竞赛经历。

**[AI 量化工程师]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/697ad578000000002](https://www.xiaohongshu.com/discovery/item/697ad5780000000022008b8e?xsec_token=YBiTjobqQtNzS5sd65hi876EvZwgdl9_ojIPAmOYYUKsw%3D&xsec_source=app_share)

> 帖内提到的公司: 鸣石基金

> **内容快照**:
> 
> 鸣石基金成立于2010年，是中国量化“元老级”玩家，2020年资产管理规模破百亿，旗下有创世纪AI实验室和自建超算中心“星座计划”。
> 
> 招聘岗位包括量化因子工程师、AI量化工程师（全职&暑期实习）和量化开发工程师（全职）。
> 
> 招聘流程为简历投递→初步沟通→线上笔试→2-3轮面试→发放OFFER，招满即止。
> 
> 面向海内外名校硕士/博士，理工类相关专业，要求扎实的数理、编程功底，对量化金融有强烈兴趣。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 成立于2010中国量化元年｜2020年资产管理规模破百亿
旗下 创世纪AI实验室（G-LAB） 赋能全流程策略研发
自建超算中心 “星座计划”（一期仙女座、二期英仙座）
> - 🔬 研究员序列（全职 & 暑期实习）
量化因子工程师
AI量化工程师（MONETIZATION & OPTIMIZATION）
💻 工程师序列（全职）
量化开发工程师（C++）
> - STEP 1 简历投递 → STEP 2 初步沟通 → STEP 3 线上笔试
→ STEP 4 2-3轮面试 → STEP 5 发放OFFER
⏰ 招满即止，建议尽早锁定席位

**[AI 量化工程师]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a06c29c000000000](https://www.xiaohongshu.com/discovery/item/6a06c29c0000000007020b39?xsec_token=YB4QBS1qgXQ-bzMzodScIaKdb7i_8y3G690JNEsYkchBI%3D&xsec_source=app_share)

> 帖内提到的公司: 鸣石基金

> **内容快照**:
> 
> 鸣石基金是一家400亿+规模的量化大厂，拥有自己的AI超算中心，近两年多个策略表现良好。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 400亿+规模量化大厂鸣石 调研交流～这两年几个策略都做得蛮好的[赞R] 还有自己的AI超算中心～

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69e6c71d000000001](https://www.xiaohongshu.com/discovery/item/69e6c71d000000001b021709?xsec_token=YBwm9CSQ__MViaGJoNmUtuSz9NFZXVP3A4Y0kfaeEuuSc%3D&xsec_source=app_share)

> 帖内提到的公司: 鸣石投资

> **内容快照**:
> 
> 鸣石投资成立于2010年，截至2026年4月规模350亿+，采用流水线制策略开发，人工为主+机器挖掘因子，有效因子超3万个。
> 
> 袁宇为总经理&策略负责人，沃顿商学院金融学博士，师承Fama-French三因子模型；王晓晗为投资经理，上海交通大学金融学博士。
> 
> 鸣石投资策略线包括空气指增、择时对冲、股指多空、量化对冲、季季红等，覆盖多种量化策略。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 公司：成立于2010年12月9日，2015年10亿；19年70亿并推出高频日内策略；20年破百亿；22年仙女座一期超算启用；23年上线低波动ETF策略、部署“英仙座二期”超算；24年上线股指套利策略。截至26年4月规模350亿+
> - 袁宇，总经理&策略负责人。沃顿商学院金融学博士，曾任沃顿商学院、上海高级金融学院教授，师承Fama-French三因子模型，2010年回国创立鸣石。目前亲自分管投研和市场。王晓晗，投资经理。上海交通大学金融学博士，2010年加入，负责风控模型与投资策略研究
> - 产品线：1）空气指增：代表产品鸣石未来新元量化选股1号C期...2）择时对冲：代表产品鸣石锐驰七号...3）股指多空：鸣石春天七号A...4）量化对冲：代表产品鸣石同心6号（中波）...5）季季红：代表产品鸣石对冲均衡3号量化

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68b6b196000000001](https://www.xiaohongshu.com/discovery/item/68b6b196000000001d020055?xsec_token=YBH0L0Ajxri4Res_FhZmYthCIcjO_Hi_B3hDutLAMRHoA%3D&xsec_source=app_share)

> 帖内提到的公司: 鸣石基金

> **内容快照**:
> 
> 鸣石基金是一家量化私募，提供投研实习机会。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 每天认识一个私募：鸣石基金

_(+9 条更多帖未展示, 同 sub_cat)_

---

### 14. 幻方量化

- **tier**: 头部量化私募
- **must_have in**: 量化研究员·中频, 量化研究员·高频, AI 量化工程师 (3 sub_cat)
- **非 must_have (备选) in**: 量化开发QD, 量化因子工程师 (2)
- **industry_focus**: AI 应用层
- **source 标签**: common_knowledge:头部量化私募, taxonomy_doc, xhs:量化研究员·高频:8
- **notes**:
  - [量化研究员·中频] DeepSeek 母公司,XHS mention 高
  - [量化研究员·高频] 国内高频强
  - [量化开发QD] 按行业共识
  - [AI 量化工程师] AI 量化先驱
  - [量化因子工程师] 按行业共识

#### XHS 帖证据 (15 条)

**[AI 量化工程师]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69a792eb000000002](https://www.xiaohongshu.com/discovery/item/69a792eb0000000022030502?xsec_token=YBs-4avNvayEyYORKHdX6UCHlKAuhJEeb1GFsp674-Hnw%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方量化

> **内容快照**:
> 
> 幻方量化是国内AI量化投资的领军者，管理规模超600亿，以深度学习为核心打造智能投研体系。
> 
> 幻方量化招聘AI研究员（大模型方向），年薪80-300万，要求PhD，NLP/CV/强化学习背景，顶会论文。
> 
> 幻方量化招聘量化研究员（股票Alpha），年薪60-200万，要求名校硕博，数学/统计/物理，竞赛获奖优先。
> 
> 幻方量化招聘高性能计算工程师，年薪50-150万，要求精通C++/CUDA，熟悉GPU并行计算。
> 
> 幻方量化招聘深度学习工程师，年薪60-180万，要求PyTorch/TensorFlow，大规模模型训练经验。
> 
> 校招DDL为rolling basis，建议尽早投递。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 幻方量化是国内AI量化投资的领军者，管理规模超600亿，以深度学习为核心，打造智能投研体系
> - AI研究员（大模型方向）💰 年薪80-300万 ✅ 要求：PhD，NLP/CV/强化学习背景，顶会论文
> - 量化研究员（股票Alpha）💰 年薪60-200万 ✅ 要求：名校硕博，数学/统计/物理，竞赛获奖优先

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/67ade79e000000001](https://www.xiaohongshu.com/discovery/item/67ade79e000000001902cae8?xsec_token=YBddWlTPnbIIPy55VycqNjT7dXxCOvBpZiPYNR30O6dKg%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方量化

> **内容快照**:
> 
> 幻方量化被描述为国运级重器，薪资超高，要求不明。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 这不一眼幻方吗 国运级重器，好强的偷感。啥要求也没有，只有超高薪资！牛！！！

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/679eb939000000002](https://www.xiaohongshu.com/discovery/item/679eb9390000000029025246?xsec_token=YBun9ptKp4gbmWTca1y6Q-4SgI77uN5heD_y4GKcRosc8%3D&xsec_source=app_share)

> 帖内提到的公司: 明汯投资, 灵均投资, 幻方量化, 九坤投资

> **内容快照**:
> 
> 中国量化私募四大天王包括明汯投资、灵均投资、幻方量化和九坤投资，在量化投资领域表现突出，管理规模较大，市场影响力较高。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 四大天王：包括明汯投资、灵均投资、幻方量化和九坤投资。这四家公司在量化投资领域表现突出，管理规模较大，市场影响力较高。

**[量化开发QD]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0d8637000000003](https://www.xiaohongshu.com/discovery/item/6a0d863700000000360025d1?xsec_token=YBm4Y5lD0UeO4fv4xPCt09Z1TPG5yS2AJULzN6ntDpeJY%3D&xsec_source=app_share)

> 帖内提到的公司: 顶级外资, 幻方量化, Jane Street, HRT

> **内容快照**:
> 
> 顶级外资急招junior C++开发，base香港，年薪200万，面向26年应届生或3年以内经验者。
> 
> 帖子提及幻方量化、Jane Street、HRT等量化公司，暗示这些公司正在招聘或有关注度。

> **verbatim 锚点 (T1/T3 抽取)**:
> - junior C++速来 26年应届C++ 顶级外资急招 200w base hk 3年以内的都可以聊
> - 幻方量化 janestreet面经 HRT面试

**[量化开发QD]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0e7e22000000000](https://www.xiaohongshu.com/discovery/item/6a0e7e220000000006023f8d?xsec_token=YBdg-UXLPVmfa2DBA3Md0i0McWmXr37DTYnIhXnM2JzK0%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方量化

> **内容快照**:
> 
> 幻方量化招聘量化开发工程师，要求顶尖院校计算机相关专业本科或以上，代码工程能力强，有竞赛获奖经历和科技/量化行业实习经历加分。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 幻方量化招量化开发工程师
要求顶尖院校计算机相关专业本科或以上的，代码工程能力强，有竞赛获奖经历和科技/量化行业实习经历加分。

**[量化研究员·中频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/679f9b01000000001](https://www.xiaohongshu.com/discovery/item/679f9b01000000001801b010?xsec_token=YB6v3yizhmiGCAtB5_x-e_myeRXKxjJVZlmmt1XfJmN0k%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方量化

> **内容快照**:
> 
> 幻方量化应届生研究员年薪可达百万
> 
> 量化研究岗位竞争激烈，最终能拿到offer的应届生本科多为清北
> 
> 幻方量化招聘时偏好有特殊兴趣爱好和经历的应届生，并相信刚毕业的人更有自信

> **verbatim 锚点 (T1/T3 抽取)**:
> - boss直聘上经验不限的研究员岗位，年薪已经百万了
> - 最终能接到offer的，一届研究生同学里面也屈指可数，他们基本上本科也是清北的
> - 他们在招人的时候会特意选有特殊兴趣爱好和经历的人，而且他们相信刚毕业的人更有自信

_(+9 条更多帖未展示, 同 sub_cat)_

---

### 15. 阿里巴巴

- **tier**: 互联网大厂
- **must_have in**: LLM算法post-train, AI PM, AI算法业务 (3 sub_cat)
- **非 must_have (备选) in**: Agent工程师, 多模态推理优化 (2)
- **industry_focus**: AI 基础设施, AI 应用层
- **source 标签**: demo_v1, taxonomy_doc, xhs:AI PM:1, xhs:多模态推理优化:1
- **notes**:
  - [LLM算法post-train] 通义千问团队
  - [Agent工程师] 通义 Agent
  - [多模态推理优化] 通义多模态
  - [AI PM] 通义 + 业务 AI PM
  - [AI算法业务] 淘天广告/推荐算法

#### XHS 帖证据 (4 条)

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[多模态推理优化]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69fec4c0000000003](https://www.xiaohongshu.com/discovery/item/69fec4c00000000037037dbe?xsec_token=YBmlLg2uWh_lvMnSZxDHuZ2V4OgGCX8r6chmzqpEoIeMU%3D&xsec_source=app_share)

> 帖内提到的公司: 腾讯, 字节跳动, 阿里巴巴, 美团, 拼多多, 百度

> **内容快照**:
> 
> 腾讯研发实习生薪资从7500涨至13000（含2000房补），涨幅超50%
> 
> 大厂集体上调实习生薪资，AI人才争夺激烈
> 
> 腾讯顶尖人才通过'青云计划'薪酬上不封顶，日薪可达5500元
> 
> 互联网行业重心转向AI，技术岗实习生迎来春天

> **verbatim 锚点 (T1/T3 抽取)**:
> - 去年月薪7500。今年直接干到13000（含2000房补）。一年涨了50%。
> - 大厂集体砸钱，本质是盯上了'AI原生代'
> - 顶尖人才通过'青云计划'：薪酬上不封顶。日薪可达5500元。

**[AI算法业务]** (relevance=0.20) — [https://www.xiaohongshu.com/discovery/item/6a040768000000003](https://www.xiaohongshu.com/discovery/item/6a040768000000003700e572?xsec_token=YBaeb85LThEO4PNqrTgJEF2fOALDIOuV3cFZRGi4gkQSY%3D&xsec_source=app_share)

> 帖内提到的公司: 阿里巴巴

> **内容快照**:
> 
> AI应用研发岗位要求综合能力：工程开发、AI工具熟练度、新技术敏感度。
> 
> AI应用研发面试可能考察对AI工具和模型的使用熟练度，以及新技术调研能力。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 这个方向对个人的要求会更综合。既要有工程开发能力，也要对AI工具和模型使用足够熟练，知道怎么和大模型交互、怎么设计prompt、怎么拆任务、怎么控制输出质量，还要保持对新技术的敏感度和学习速度。
> - 在真正动手之前，需要先去看业界最新的东西，分析它的创新点、不足，以及能不能和当前业务场景结合。

**[LLM算法post-train]** (relevance=0.20) — [https://www.xiaohongshu.com/discovery/item/6a0adad3000000003](https://www.xiaohongshu.com/discovery/item/6a0adad3000000003502dcfc?xsec_token=YBKCYOCzN__YUYgBbao898wxjgQXKkPesg1fnBZU7aKA8%3D&xsec_source=app_share)

> 帖内提到的公司: 阿里巴巴

> **内容快照**:
> 
> 阿里巴巴 ATH-MaaS AI应用团队招聘27届校招和实习，岗位为大模型算法工程师，工作地点杭州。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 阿里巴巴 ATH-MaaS AI应用团队 正式开启27届校招 & 实习招聘！

---

### 16. 中信建投证券

- **tier**: 头部券商研究所
- **must_have in**: 固收交易员, 卖方研究员·TMT, 结构化产品衍生品 (3 sub_cat)
- **非 must_have (备选) in**: 投行 IBD (1)
- **industry_focus**: TMT, 金融
- **source 标签**: common_knowledge:头部券商, common_knowledge:头部券商衍生品, demo_v1, saif:2024, taxonomy_doc
- **notes**:
  - [固收交易员] 按行业共识,自营 FICC 头部
  - [卖方研究员·TMT] 半导体/计算机首席强
  - [投行 IBD] 按行业共识
  - [结构化产品衍生品] 按行业共识

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 中信建投证券股份有限公司 | 卖方分析师 | 1 | 券商研究所 |

#### XHS 帖证据 (8 条)

**[公募权益研究员]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/69b01b10000000000](https://www.xiaohongshu.com/discovery/item/69b01b10000000000601f681?xsec_token=YB3mubOgxaYuySVOQc18ibYOSsyNMwYBOBRr4DQeL0kMQ%3D&xsec_source=app_share)

> 帖内提到的公司: 工银瑞信, 中信建投基金, 嘉实基金, 天弘基金, 华夏基金

> **内容快照**:
> 
> 公募基金面试通过推票（基本面分析）、近期行情判断（策略框架）、关键行业事件（行业趋势洞察力）、市场风险溢价（宏观分析能力）这四类问题判断候选人综合潜力。
> 
> 公募基金实习阶段通过观察日常工作习惯、课题沟通能力、任务完成程度、工作自驱力判断实习生。
> 
> 公募基金答辩考察候选者能否将研究转化为包含价格与时点的具体观点。
> 
> 公募基金高管面通过观察候选人与上位者的沟通姿态及回答内容，检验职业兴趣和组织稳定度。
> 
> 作者秋招投递了多家公募基金，包括某top3公募（暑期投研）、工银瑞信（拿到pass卡后放弃）、中信建投基金（暑期后放弃）、嘉实基金（简历挂）、天弘基金（面试挂）、华夏基金（简历挂）。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 面试阶段，通过推票（基本面分析）、近期行情判断（策略框架）、关键行业事件（行业趋势洞察力）、市场风险溢价（宏观分析能力）这四类问题能准确判断候选人的综合潜力、职业兴趣、时间投入。
> - 实习中，通过观察日常工作习惯、课题沟通能力、任务完成程度、工作自驱力增加对实习生的深层次判断。
> - 答辩中，通过考察短时间内的输出情况，衡量候选者能否将研究转化为包含价格与时点的具体观点，完成对业务能力的下半场判断。

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69f2f5a2000000003](https://www.xiaohongshu.com/discovery/item/69f2f5a20000000036018768?xsec_token=YB6XyL7qK0wnMKAufhmdA46EbHqgjR2g4Ec8azVEuM1cw%3D&xsec_source=app_share)

> 帖内提到的公司: 中信建投, 国泰海通, 招商证券, 中信证券

> **内容快照**:
> 
> 中信建投、国泰海通、招商证券的暑期实习于4月30日截止，中信证券总部暑期实习已开放。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 中信建投、国泰海通、招商证券均4月30日（今日）截止⚡中信证券总部暑期实习也已开放，及时投递

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a004d91000000003](https://www.xiaohongshu.com/discovery/item/6a004d910000000036000bfe?xsec_token=YBYM1cUi6i2AdR2d2EYp7gyzNSgGWMnMTf2wxGS2XvQqk%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 中金公司, 华泰证券, 中信建投证券, 国泰海通证券, 招商证券

> **内容快照**:
> 
> 投行招聘中，除了中金公司，大部分券商强调实习留用，面试越来越水，更看重实战能力。
> 
> 26年投行招聘仍是招聘大年，腰腿部券商提供更多机会，学历门槛下探。
> 
> 列举了15家开放投行暑期实习的券商和14家开放春季招聘的券商，其中4家同时开放。
> 
> 本科学历背景普通但实战能力突出的候选人，在26年拿到投行机会的可能性提升。
> 
> 投行面试越来越水，技术面试在绝大部分券商涉及不到。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 除了中金公司以外，其他大部分券商都强调“实习留用”...投行的面试越来越水了。
> - 26年仍会是投行的招聘大年...腰腿部券商投行给了大家更多的“选择权”...学历相对没那么优秀，26年有更多的加入投行的机会和可能性。
> - 至少包括15家：中信证券、中金公司、华泰证券...至少包括14家：招商证券、国联民生证券...同时开放暑期实习和春季招聘的投行，包括4家：招商证券、国联民生证券、东吴证券、西部证券。

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000](https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000702ace7?xsec_token=YB9MVh1sELWdJvRY7-4rURZo9qtVNwXXJJLAGIjlCzytE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 中金公司, 华泰证券, 中信建投证券, 申万宏源

> **内容快照**:
> 
> 中信证券多项业务指标连年夺魁，是券商中的'神'级公司。
> 
> 国泰海通由国开君安和海通证券合成，资本实力跃居行业榜首。
> 
> 中金公司是首家中外合资投行，投行业务标杆。
> 
> 华泰证券是金融科技+财富管理领域的标杆。
> 
> 中信建投证券降薪严重，与前三个相比掉队。
> 
> 2025年证券行业呈现'强者恒强'的马太效应，头部券商占据大部分市场份额。
> 
> 头部券商总部前台岗求职难度不输国有总行，建议根据学历背景和实习相关性合理选择。
> 
> 随着大A慢牛市场，证券公司实习机会增多，26届应把握机会。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 中信证券可以单独开一个'神'级，多项业务指标连年夺魁
> - 国泰海通由国开君安和海通证券合成而成的新龙头，资本实力跃居行业榜首
> - 中金公司，首家中外合资投行，投行业务标杆

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a00852d000000000](https://www.xiaohongshu.com/discovery/item/6a00852d0000000008002bb5?xsec_token=YBYM1cUi6i2AdR2d2EYp7gy0jrM93HeTyqyT4_9HsqWHE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 华泰证券, 中金证券, 中信建投, 招商证券

> **内容快照**:
> 
> 券商分为五个梯队，第一梯队包括中信证券、国泰海通、华泰证券、中金证券、中信建投等，平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> 
> 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> 
> 第一梯队偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历更加分。
> 
> 第三梯队门槛相对灵活，海外院校、转专业同学都有机会，关键是简历里要体现对金融行业的理解。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> - 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> - 通常更偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历会更加分。

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a140c94000000003](https://www.xiaohongshu.com/discovery/item/6a140c94000000003600064e?xsec_token=YBRzo-hNT4ZPXDcS5fA1AgySh-BmLbwiGc15KMU19Gu-o%3D&xsec_source=app_share)

> 帖内提到的公司: 广发证券, 广发基金, 中金公司, 华泰证券, 国泰海通, 中信建投

> **内容快照**:
> 
> 广发证券暑期实习采用定向招聘，不在官网发布，仅通过特定学校Career office用邮件接收申请。
> 
> 广发证券去年秋招高管面有“一票否决权”，看重学校背景（两财一贸不如西交/哈工大）、生源（留学生不如内地生）、专业（经管不如理工）、科研成果、大赛成果和AI大模型能力，而金融实习积累不那么重要。
> 
> 投行岗位选岗建议：投行/卖方研究/机构销售/股权投资业务“4选3”；股票研究：卖方研究+机构销售+股权投资业务；固收研究&交易：卖方研究+投资研究（FICC）+金融产品研究。
> 
> 广发证券招聘存在割裂：业务部门需要经管背景和实习经验，高管却偏好理工和AI能力，导致拿到大厂产品经理或中金/华泰投行offer的同学可能无法通过广发高管面。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 所谓的定向招聘，就是自己的官网不写暑期实习，没有投递窗口。结果在特定学校的Career office发放暑期实习的投递信息，而且是用E-mail接受大家的申请和投递。
> - 但是能否留用，主要取决于高管面的“一票否决权”，你的学校背景（例如两财一贸不如西交/哈工大，留学生不如内地生）、专业背景（经管＜＜＜理工）、科研成果和大赛成果、AI 大模型的能力，这些才是高管比较看重的能力。而至于你之前在金融方向的实习积累，没有那么重要。
> - 做投行的同学，考虑投行/卖方研究/机构销售/股权投资业务的“4选3”的组合。做股票研究的同学，考虑卖方研究+机构销售+股权投资业务的组合。做固收研究&交易的同学，考虑卖方研究+投资研究（FICC）+金融产品研究的组合。

_(+2 条更多帖未展示, 同 sub_cat)_

---

### 17. 招商证券

- **tier**: 中型券商研究所
- **must_have in**: 固收交易员, 卖方研究员·TMT, 卖方研究员·消费医药周期 (3 sub_cat)
- **非 must_have (备选) in**: 结构化产品衍生品 (1)
- **industry_focus**: TMT, 医药, 消费, 金融
- **source 标签**: common_knowledge:头部券商, common_knowledge:头部券商衍生品, taxonomy_doc, xhs:卖方研究员·消费医药周期:13
- **notes**:
  - [固收交易员] 按行业共识,自营固收强
  - [卖方研究员·TMT] 通信/电子强
  - [卖方研究员·消费医药周期] XHS 消费医药周期第一
  - [结构化产品衍生品] 按行业共识

#### XHS 帖证据 (21 条)

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[信用研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/699b00c1000000000](https://www.xiaohongshu.com/discovery/item/699b00c1000000000e03f406?xsec_token=YByUaNWdGqni4CccoDmetp9jnkQ79jyEQvtPsYLCsbMVQ%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达基金, 招商银行

> **内容快照**:
> 
> 易方达基金资管投研部门内部竞争激烈，工作强度大，建议谨慎考虑。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 炸了！pa资管投研，竟是这种“卷王”局？内行人做二级固收研究的应该都知道哈哈，内部惨不忍睹，去的话谨慎之～

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69bbb886000000002](https://www.xiaohongshu.com/discovery/item/69bbb886000000002b00dc0f?xsec_token=YBY-rrGTG456s3Kutg82G2iAMfesSM55ZOeJkEKPkgzAA%3D&xsec_source=app_share)

> 帖内提到的公司: 三中一华, 广发证券, 招商证券, 国信证券

> **内容快照**:
> 
> 学生背景211本+中9硕，实习经历包括一段颈部券商股承做和两段TMT行研（新财富），未来可能路径为行研、投行、PE/VC。
> 
> 学生获得四个top15券商的实习offer：三中一华债、广发机械/通信（新财富）、招商TMT、国信债。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 🏠211本+中9硕，实习经历，一段颈部券商股承做，两段TMT行研（新财富）。未来的发展路径没有想好，可能是行研、投行、PE/VC。
> - 手上的实习offer（全是top15券商）1️⃣三中一华 债 2️⃣广 机械/通信（新财富）3️⃣招 TMT 4️⃣国x 债

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a01eb1c000000000](https://www.xiaohongshu.com/discovery/item/6a01eb1c00000000060338be?xsec_token=YB_i_kGzuCXcaFW9dZg1ZTISu9Q8tnbXtneZpnnB4vq6M%3D&xsec_source=app_share)

> 帖内提到的公司: 招商证券

> **内容快照**:
> 
> 招商证券2026实习生招聘已开启

> **verbatim 锚点 (T1/T3 抽取)**:
> - 招商证券2026实习生招聘已开启

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69205644000000001](https://www.xiaohongshu.com/discovery/item/69205644000000001f00b280?xsec_token=YB_DHH46EccpDnafKb5wDAjbvxYtYyKvfxi_ehR5s45OQ%3D&xsec_source=app_share)

> 帖内提到的公司: 招商证券

> **内容快照**:
> 
> 招商证券投行实习留用率不确定，HR说实习1-2个月出结果，但有人实习一年。
> 
> 投行实习要求全职（5天/周），但作者只能抽3天，且12月初要上课，时间冲突。

> **verbatim 锚点 (T1/T3 抽取)**:
> - hr说实习1-2月出结果但红薯上刷到有人实习一年
> - 全职实习是不是指五天/周关键我只能抽三天，出差我这也很难办十二月初得上课

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6981f15c000000002](https://www.xiaohongshu.com/discovery/item/6981f15c00000000220080c6?xsec_token=YB36fp58VMA4y3yTxPK9RvWAg0VsVvBz1EByjqK8CUfgY%3D&xsec_source=app_share)

> 帖内提到的公司: 招商证券

> **内容快照**:
> 
> 招商证券投行部实习岗位，涉及量化建模和固收领域，适合金融、经济、会计等商科背景学生。
> 
> 招商证券是中国领先的上市券商，拥有全牌照业务体系。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 招商证券·投行部实习｜2-3个月，开启你的金融职场高起点！
> - 招商证券——中国领先的上市券商，承载百年招商局的深厚底蕴。

_(+15 条更多帖未展示, 同 sub_cat)_

---

### 18. 中欧基金

- **tier**: 一线公募
- **must_have in**: 行业研究员·TMT-医药-周期, 资管FOF, 财富管理FOF (3 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: TMT, 医药, 金融
- **source 标签**: common_knowledge:头部公募, xhs:财富管理FOF:1
- **notes**:
  - [行业研究员·TMT-医药-周期] 按行业共识,医药主动权益强
  - [资管FOF] 按行业共识,FOF 产品线齐
  - [财富管理FOF] FOF 投顾产品

#### XHS 帖证据 (4 条)

**[自营FOF]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6890067f000000000](https://www.xiaohongshu.com/discovery/item/6890067f0000000003031ea8?xsec_token=YBmCA1AtoFdnPTCngthUM3rB8t5ZksJM979ASjR1w7C5Y%3D&xsec_source=app_share)

> 帖内提到的公司: 兴全基金, 易方达基金, 中欧基金, 大成基金, 华夏基金, 南方基金

> **内容快照**:
> 
> FOF基金行业人才流失严重，薪资不够吸引人，很多优秀的基金经理都跑去保险、私募了。
> 
> 兴全FOF的林国怀从2020年开始重仓刘旭，2024年却全部清仓了，可能是考虑到刘旭管理规模已达475亿。
> 
> 兴证全球已经把'FOF投资部'改名为'多元资产配置部'，信号很明显。
> 
> 华夏郑鹏管理华夏海外聚享，业绩堪称完美，但已离职。
> 
> 南方恽雷理论功底深厚，核心理念是寻找长期优秀的Beta + 股债负相关性。
> 
> 中泰唐军建立了中泰时钟资产配置体系，长期持有黄金ETF。
> 
> 今年FOF新发规模已达308.42亿，超过去年全年的123.67亿，招商银行大力推广'TREE长盈计划'。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 人才流失严重：薪资不够吸引人，很多优秀的基金经理都跑去保险、私募了
> - 兴全FOF的林国怀从2020年开始重仓刘旭，2024年却全部清仓了！可能是考虑到刘旭管理规模已达475亿，太大了...
> - 兴证全球已经把'FOF投资部'改名为'多元资产配置部'，信号很明显！

**[财富管理FOF]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69b7adf5000000001](https://www.xiaohongshu.com/discovery/item/69b7adf5000000001d01e2cb?xsec_token=YBUbBPgCnu6HsJND6ndu6QErhvAcLeTam3vb19cHq1TBk%3D&xsec_source=app_share)

> 帖内提到的公司: 富国基金, 中欧基金, 易方达基金, 广发基金, 博时基金, 交银施罗德基金

> **内容快照**:
> 
> FOF（基金中的基金）近期在公募市场热度上升，发行数量和规模大幅增长，银行渠道推动明显，产品设计以短持有期、偏债混合策略为主。
> 
> FOF总规模突破3000亿，头部公司如富国、中欧、易方达、广发规模超200亿，但行业格局未固化。
> 
> FOF热度背后原因包括存款利率下行、市场波动大、银行渠道转型、产品设计适配等。
> 
> FOF行业趋势：从选基转向配置，产品形态纳入黄金ETF、REITs、QDII等，与养老联动。

> **verbatim 锚点 (T1/T3 抽取)**:
> - FOF（基金中的基金）突然成了公募市场的热门话题。截至3月14日，今年全市场已经有40只FOF成立，合计募了619.73亿元。跟去年一季度比，数量增加了233%，规模增长了361%。
> - 截至3月14日，FOF总规模突破3000亿。84家公募有布局，但头部还没固化：规模最大的管理人约245亿，规模超100亿的只有11家。第一梯队：富国、中欧、易方达、广发都超200亿。
> - 一是存款利率下行，叠加市场波动大，个人做择时、选基金的难度在增加。FOF的逻辑是通过专业选基+多资产配置，降低单一资产的波动。二是银行渠道从'卖产品'转向'卖配置方案'。三是产品设计的适配。

**[资管FOF]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68076825000000001](https://www.xiaohongshu.com/discovery/item/68076825000000001a0066db?xsec_token=YB99eH8k09Rv7rNLHjW60O0BTN6QzTKurNuAdNZ06-eic%3D&xsec_source=app_share)

> 帖内提到的公司: 交银施罗德基金, 兴证全球基金, 民生加银基金, 汇添富基金, 南方基金, 浦银安盛基金

> **内容快照**:
> 
> FOF行业规模从2021年的2253亿降至2024年底的1442亿，降幅36%，多家公司规模大幅缩水。
> 
> 交银施罗德基金FOF团队仅剩2名基金经理，规模排名从第一跌至第七。
> 
> 兴证全球基金FOF团队以林国怀为带头人，成员背景多元，包括互联网大厂和海外金融背景。
> 
> 易方达基金FOF团队由汪玲牵头，成员如刘淑霞有券商资管FOF业务负责人经验。
> 
> 中欧基金FOF团队由桑磊牵头，成员有险资投资管理经验。
> 
> 华夏基金FOF团队汇聚了许利民、廉赵峰、李晓易、卢少强等精兵强将。
> 
> 工银瑞信FOF团队赵志源接替蒋华安成为FOF投资部总经理并进入投委会，陈涵任研究副总监。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 截至2024年底，共有87家基金公司管理着511只FOF产品，资产净值规模合计1442亿元，相比2021年的2253亿降幅36%。
> - 交银施罗德FOF团队则仅见2人：刘兵，经济学博士，2016年加入交银施罗德基金；刘迪，金融工程与投资管理博士，2015年加入交银施罗德基金。
> - 兴证全球基金以公司总经理助理、FOF投资与金融工程部总监、养老金管理部总监林国怀为带头人，团队成员既有来自互联网大厂的成员，也有来自海外金融从业背景的成员。

**[量化研究员·中频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69ef06c9000000001](https://www.xiaohongshu.com/discovery/item/69ef06c9000000001f00683d?xsec_token=YBBFKhGPbgnOn2OGWLk_gXAX5sUP_42Hkr932PR2n-43I%3D&xsec_source=app_share)

> 帖内提到的公司: 洛书投资, Deutsche Börse Group, BlackRock, Wolverine Trading, MSCIInc., Man Group

> **内容快照**:
> 
> 列举了2026年大量量化相关的校招和实习机会，包括国内外多家知名机构。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 洛书投资2026 Graduate program...AlphaGrep 2026暑期实习

---

### 19. 平安资产管理

- **tier**: 保险资管
- **must_have in**: 信用研究员, 固收+多资产, 利率宏观策略 (3 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: 城投, 金融
- **source 标签**: saif:2024, taxonomy_doc, xhs:利率宏观策略:1
- **notes**:
  - [信用研究员] 保险资管 AUM 头部
  - [固收+多资产] 保险资管固收+核心
  - [利率宏观策略] 保险资管利率配置

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 平安资产管理有限责任公司 | 行业研究员 | 1 | 保险资管 |

#### XHS 帖证据 (12 条)

**[固收+多资产]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a03466a000000000](https://www.xiaohongshu.com/discovery/item/6a03466a000000000702f4c4?xsec_token=YBHOt7zneE8YP4HgVHcNE3uPkUsDCRauMCju0BEuxouic%3D&xsec_source=app_share)

> 帖内提到的公司: yfd, 德邦, 上银, 中银理财, 中邮理财, 信银理财

> **内容快照**:
> 
> 固收赛道相比权益bar略低，但近年越来越卷。
> 
> 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向。
> 
> 实习经历垂直会有一定优势，多段转债量化经历有助于秋招。
> 
> 暑期实习面试中，公募、理财子、券商、私募等均有面试经历，部分挂掉。
> 
> 多数市场化机构在暑期确定名额后秋招不开放。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 固收赛道相比权益bar略低，但是近年越来越卷
> - 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向
> - 实习经历垂直会有一定优势，猜测秋招发面是因为有多段转债量化经历

**[公募基金中后台]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0b1435000000003](https://www.xiaohongshu.com/discovery/item/6a0b14350000000035033c92?xsec_token=YBjJDvW9ftzu9in_HYy8Pxxg20_Kg7r5OsrRXUwVlafdo%3D&xsec_source=app_share)

> 帖内提到的公司: 国联民生, 南方基金, 东吴证券, 景顺长城, 平安证券, 平安理财

> **内容快照**:
> 
> 用户已面试国联民生中台岗、南方基金群面、东吴证券债承、景顺长城中台岗，并完成平安证券、平安理财、民生银行、东方财富证券的测评。
> 
> 用户投递了多家金融机构的暑期实习，包括券商、基金、银行理财子等。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 已面试：1、国联民生中台岗 2、南方基金群面 3、东吴证券债承 4、景顺长城中台岗 已测评：1、平安证券、平安理财 2、民生银行 3、东方财富证券
> - 国联民生中台岗、南方基金群面、东吴证券债承、景顺长城中台岗、平安证券、平安理财、民生银行、东方财富证券

**[利率宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/65d82a21000000000](https://www.xiaohongshu.com/discovery/item/65d82a21000000000b01727e?xsec_token=YBERA2NT_0W6NUgMTa_0vN0YwyvwgVf9e05xmaQ_CvrGo%3D&xsec_source=app_share)

> 帖内提到的公司: 国利, 平安, 国际, BGC, 信唐, 上田

> **内容快照**:
> 
> 货币中介门槛相对其他金融机构友好，但内卷严重，学历层次增高。
> 
> 面试货币中介需要了解所报价品种的市场概况、基础设施、参与机构，以及岗位日常和所需能力。
> 
> 国利是货币中介中最强的，平安、国际也比较猛，BGC次之，信唐不容小觑，上田是后起之秀。
> 
> 货币中介主要报价品种包括利率、信用、货币、存单、借贷、利率互换等，地方债逐渐独立成台。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 现在内卷比较严重，货币中介小伙伴们的学历层次也逐渐增高，不乏海内外名校硕士。但门槛总体还是没有其他金融机构要求那么严格，社招和校招对专业和学历还算友好。
> - 了解清楚自己面试台子所报价品种的市场概况，基础设施，参与机构；了解对应岗位每天的日常；了解该岗位需要什么能力，自己有什么特质与之匹配。
> - 国利最强，平安、国际也比较猛，BGC次之，信唐也不容小觑，在某些品种的报价表现上毫不逊色。上田作为后起之秀，社招了很多以前同行的经纪人，报价水平也一样专业。

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/669c8650000000000](https://www.xiaohongshu.com/discovery/item/669c8650000000000a02755d?xsec_token=YByIede-U9SUzZKRbL5ECpeyVlBMGy40PZrIh0A64Tocg%3D&xsec_source=app_share)

> 帖内提到的公司: 国元证券, 平安证券, 民生证券

> **内容快照**:
> 
> 卖方首席的职业路径可以从双非院校起步，通过努力逐步晋升，二级研究提供凭借个人能力走出来的机会。
> 
> 民生证券海外首席易老师，从国元证券到平安证券再到民生证券，专注于传媒互联网、消费等方向。
> 
> 二级研究行业为小镇做题家提供凭借个人能力走出来的机会，晋升不只看关系。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 双非院校走出来的卖方首席，勤奋&实力
> - 2020年初离开国元进入平安，一直从事传媒互联网、消费等方向的研究...2023年7月进入民生证券
> - 二级研究至少还给你一个凭借个人能力走出来的机会，这也是吸引一代又一代小镇做题家奋不顾身扎进来的原因之一。

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a004d91000000003](https://www.xiaohongshu.com/discovery/item/6a004d910000000036000bfe?xsec_token=YBYM1cUi6i2AdR2d2EYp7gyzNSgGWMnMTf2wxGS2XvQqk%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 中金公司, 华泰证券, 中信建投证券, 国泰海通证券, 招商证券

> **内容快照**:
> 
> 投行招聘中，除了中金公司，大部分券商强调实习留用，面试越来越水，更看重实战能力。
> 
> 26年投行招聘仍是招聘大年，腰腿部券商提供更多机会，学历门槛下探。
> 
> 列举了15家开放投行暑期实习的券商和14家开放春季招聘的券商，其中4家同时开放。
> 
> 本科学历背景普通但实战能力突出的候选人，在26年拿到投行机会的可能性提升。
> 
> 投行面试越来越水，技术面试在绝大部分券商涉及不到。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 除了中金公司以外，其他大部分券商都强调“实习留用”...投行的面试越来越水了。
> - 26年仍会是投行的招聘大年...腰腿部券商投行给了大家更多的“选择权”...学历相对没那么优秀，26年有更多的加入投行的机会和可能性。
> - 至少包括15家：中信证券、中金公司、华泰证券...至少包括14家：招商证券、国联民生证券...同时开放暑期实习和春季招聘的投行，包括4家：招商证券、国联民生证券、东吴证券、西部证券。

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000](https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000702ace7?xsec_token=YB9MVh1sELWdJvRY7-4rURZo9qtVNwXXJJLAGIjlCzytE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 中金公司, 华泰证券, 中信建投证券, 申万宏源

> **内容快照**:
> 
> 中信证券多项业务指标连年夺魁，是券商中的'神'级公司。
> 
> 国泰海通由国开君安和海通证券合成，资本实力跃居行业榜首。
> 
> 中金公司是首家中外合资投行，投行业务标杆。
> 
> 华泰证券是金融科技+财富管理领域的标杆。
> 
> 中信建投证券降薪严重，与前三个相比掉队。
> 
> 2025年证券行业呈现'强者恒强'的马太效应，头部券商占据大部分市场份额。
> 
> 头部券商总部前台岗求职难度不输国有总行，建议根据学历背景和实习相关性合理选择。
> 
> 随着大A慢牛市场，证券公司实习机会增多，26届应把握机会。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 中信证券可以单独开一个'神'级，多项业务指标连年夺魁
> - 国泰海通由国开君安和海通证券合成而成的新龙头，资本实力跃居行业榜首
> - 中金公司，首家中外合资投行，投行业务标杆

_(+6 条更多帖未展示, 同 sub_cat)_

---

### 20. 招商基金

- **tier**: 一线公募
- **must_have in**: 行业研究员·消费, 行业研究员·TMT-医药-周期 (2 sub_cat)
- **非 must_have (备选) in**: 公募基金中后台, 固收+多资产, 资管FOF (3)
- **industry_focus**: TMT, 周期, 消费, 金融
- **source 标签**: common_knowledge:头部公募, taxonomy_doc
- **notes**:
  - [行业研究员·消费] 按行业共识,消费行业研究员强
  - [行业研究员·TMT-医药-周期] 按行业共识
  - [公募基金中后台] 按行业共识
  - [固收+多资产] 按行业共识
  - [资管FOF] 按行业共识

#### XHS 帖证据 (21 条)

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[信用研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/699b00c1000000000](https://www.xiaohongshu.com/discovery/item/699b00c1000000000e03f406?xsec_token=YByUaNWdGqni4CccoDmetp9jnkQ79jyEQvtPsYLCsbMVQ%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达基金, 招商银行

> **内容快照**:
> 
> 易方达基金资管投研部门内部竞争激烈，工作强度大，建议谨慎考虑。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 炸了！pa资管投研，竟是这种“卷王”局？内行人做二级固收研究的应该都知道哈哈，内部惨不忍睹，去的话谨慎之～

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69bbb886000000002](https://www.xiaohongshu.com/discovery/item/69bbb886000000002b00dc0f?xsec_token=YBY-rrGTG456s3Kutg82G2iAMfesSM55ZOeJkEKPkgzAA%3D&xsec_source=app_share)

> 帖内提到的公司: 三中一华, 广发证券, 招商证券, 国信证券

> **内容快照**:
> 
> 学生背景211本+中9硕，实习经历包括一段颈部券商股承做和两段TMT行研（新财富），未来可能路径为行研、投行、PE/VC。
> 
> 学生获得四个top15券商的实习offer：三中一华债、广发机械/通信（新财富）、招商TMT、国信债。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 🏠211本+中9硕，实习经历，一段颈部券商股承做，两段TMT行研（新财富）。未来的发展路径没有想好，可能是行研、投行、PE/VC。
> - 手上的实习offer（全是top15券商）1️⃣三中一华 债 2️⃣广 机械/通信（新财富）3️⃣招 TMT 4️⃣国x 债

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a01eb1c000000000](https://www.xiaohongshu.com/discovery/item/6a01eb1c00000000060338be?xsec_token=YB_i_kGzuCXcaFW9dZg1ZTISu9Q8tnbXtneZpnnB4vq6M%3D&xsec_source=app_share)

> 帖内提到的公司: 招商证券

> **内容快照**:
> 
> 招商证券2026实习生招聘已开启

> **verbatim 锚点 (T1/T3 抽取)**:
> - 招商证券2026实习生招聘已开启

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69205644000000001](https://www.xiaohongshu.com/discovery/item/69205644000000001f00b280?xsec_token=YB_DHH46EccpDnafKb5wDAjbvxYtYyKvfxi_ehR5s45OQ%3D&xsec_source=app_share)

> 帖内提到的公司: 招商证券

> **内容快照**:
> 
> 招商证券投行实习留用率不确定，HR说实习1-2个月出结果，但有人实习一年。
> 
> 投行实习要求全职（5天/周），但作者只能抽3天，且12月初要上课，时间冲突。

> **verbatim 锚点 (T1/T3 抽取)**:
> - hr说实习1-2月出结果但红薯上刷到有人实习一年
> - 全职实习是不是指五天/周关键我只能抽三天，出差我这也很难办十二月初得上课

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6981f15c000000002](https://www.xiaohongshu.com/discovery/item/6981f15c00000000220080c6?xsec_token=YB36fp58VMA4y3yTxPK9RvWAg0VsVvBz1EByjqK8CUfgY%3D&xsec_source=app_share)

> 帖内提到的公司: 招商证券

> **内容快照**:
> 
> 招商证券投行部实习岗位，涉及量化建模和固收领域，适合金融、经济、会计等商科背景学生。
> 
> 招商证券是中国领先的上市券商，拥有全牌照业务体系。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 招商证券·投行部实习｜2-3个月，开启你的金融职场高起点！
> - 招商证券——中国领先的上市券商，承载百年招商局的深厚底蕴。

_(+15 条更多帖未展示, 同 sub_cat)_

---

### 21. 灵均投资

- **tier**: 头部量化私募
- **must_have in**: 量化研究员·中频, 量化因子工程师 (2 sub_cat)
- **非 must_have (备选) in**: 量化开发QD, AI 量化工程师 (2)
- **industry_focus**: AI 应用层
- **source 标签**: common_knowledge:头部量化私募, demo_v1, taxonomy_doc
- **notes**:
  - [量化研究员·中频] XHS 30 mention 量化第一
  - [量化开发QD] 按行业共识
  - [AI 量化工程师] 按行业共识
  - [量化因子工程师] 按行业共识

#### XHS 帖证据 (21 条)

**[买方 Quant]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/695940c8000000001](https://www.xiaohongshu.com/discovery/item/695940c8000000001e03a19c?xsec_token=YBrJ_goExM-LGFpD_KXswc_GrNMq5jKropLNK56upboAU%3D&xsec_source=app_share)

> 帖内提到的公司: 高盛, 摩根士丹利, 中金, 中信里昂, 幻方, 灵均

> **内容快照**:
> 
> 大湾区量化岗位分为卖方Quant（投行）和买方Quant（基金/私募），卖方Quant集中在香港，买方Quant在深圳更活跃。
> 
> 香港的卖方Quant主要集中在国际投行（高盛、摩根士丹利等）和中资投行国际子公司（中金、中信里昂），深圳的卖方机会在国内券商的金融工程/量化自营部门。
> 
> 深圳的买方Quant核心是顶尖量化私募（幻方、灵均等），香港的买方Quant包括全球顶级对冲基金和自营交易公司（Citadel, Two Sigma, Optiver等）。
> 
> 深圳的量化岗位面试必考对国内金融数据源（Wind, Tushare, JoinQuant）和A股交易规则的熟悉度。
> 
> 香港的量化岗位面试对期权定价、随机微积分等理论要求更深。
> 
> 深圳偏好国内顶尖理工院校（清北复交、浙大、中科大等）的硕士/博士，海外名校需对国内市场有理解；香港偏好全球顶级名校（美英顶尖高校、新加坡两所、港三所），专业排名比学校综合排名更重要。
> 
> 纯金融背景竞争力弱，数学、物理、计算机、电子工程等硬核专业是绝对主流。
> 
> 大湾区量化岗位技能要求：Python、SQL、Linux是基础；深圳需精通C++，香港需英语工作能力和kdb+/q等工具。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 在大湾区，两者的重心和机会有显著差异：1. 卖方Quant（以投行为主）：香港是绝对中心...2. 买方Quant（以基金/私募为主）：深圳是核心战场...
> - 国际投行（高盛、摩根士丹利等）及中资投行的国际子公司（中金、中信里昂等）的量化团队主要聚集于香港。
> - 深圳是核心战场：聚集了全国最顶尖、最活跃的量化私募（幻方、灵均等）...香港是国际桥头堡：云集了全球顶级对冲基金和自营交易公司（Citadel, Two Sigma, Optiver等）

**[量化因子工程师]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a0c2659000000003](https://www.xiaohongshu.com/discovery/item/6a0c2659000000003501c0b8?xsec_token=YBWo3_04eqG7GfzDfPD8xw2IDqvAm1GxyL7BT86NKKem8%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 衍复, 灵均, 世纪前沿

> **内容快照**:
> 
> 幻方、九坤、明汯、衍复是量化“四大天王”出海主力，规模700-800亿，香港办公室持续扩招，提供签证担保和外派补贴。
> 
> 灵均2025年以73.51%收益斩获百亿量化业绩冠军，世纪前沿规模跃升至500-600亿，两家香港团队扩张期，对因子挖掘、建模能力强的同学友好。
> 
> 黑翼2025年新获香港9号牌，量派2024年拿下4+9号双牌照，规模突破300亿，入行门槛相对友好。
> 
> 港圈量化求职门槛：名校硕博，数理/计算机/金工背景优先，英文流利是标配。
> 
> 港圈量化优势：行业顶薪+外派补贴+签证担保，国际化投研平台，职业天花板更高。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 幻方 / 九坤 / 明汯 / 衍复：量化“四大天王”出海主力，规模普遍在700-800亿区间...香港办公室持续扩招。提供签证担保和外派补贴
> - 灵均 / 世纪前沿：2025年灵均以73.51%收益斩获百亿量化业绩冠军...世纪前沿规模跃升至500-600亿...两家香港团队均处于扩张期，对因子挖掘、建模能力强的同学非常友好
> - 黑翼 / 量派：黑翼2025年新获香港9号牌...量派2024年拿下4+9号双牌照，2025年规模已突破300亿...入行门槛相对友好

**[AI 量化工程师]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69a96d04000000001](https://www.xiaohongshu.com/discovery/item/69a96d04000000001b01f77e?xsec_token=YBcOPiNC4aAN4ur27YciyEOyKrlisBl3bOyLSGWFFisKk%3D&xsec_source=app_share)

> 帖内提到的公司: 灵均投资

> **内容快照**:
> 
> 灵均投资是一家成立于2014年的百亿量化私募，专注AI量化，管理规模100亿+，核心团队包括闫彦、马志宇等行业大牛。
> 
> 灵均投资热招岗位包括AI量化研究员、量化开发工程师、指数增强研究员、量化交易员，均在北京。
> 
> 灵均投资招聘流程为：简历投递 → 笔试 → 2-3轮面试 → Offer。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 成立于2014年6月，10年量化老牌私募；管理规模100亿+，量化投资领先者；核心团队：闫彦、马志宇等行业大牛
> - 热招岗位【AI量化研究员】北京...【量化开发工程师】北京...【指数增强研究员】北京...【量化交易员】北京
> - 流程：简历投递 → 笔试 → 2-3轮面试 → Offer

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a08269a000000003](https://www.xiaohongshu.com/discovery/item/6a08269a000000003803740b?xsec_token=YBg-qzj9nuc27NM7UiNCrdMe8mhPU84fAi2YVlMCQUvgI%3D&xsec_source=app_share)

> 帖内提到的公司: 明汯, 衍复, 灵均, 九坤

> **内容快照**:
> 
> 用户询问量化私募哪个好，提及明汯、衍复、灵均、九坤等头部量化私募。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 量化私募哪个好？

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/679eb939000000002](https://www.xiaohongshu.com/discovery/item/679eb9390000000029025246?xsec_token=YBun9ptKp4gbmWTca1y6Q-4SgI77uN5heD_y4GKcRosc8%3D&xsec_source=app_share)

> 帖内提到的公司: 明汯投资, 灵均投资, 幻方量化, 九坤投资

> **内容快照**:
> 
> 中国量化私募四大天王包括明汯投资、灵均投资、幻方量化和九坤投资，在量化投资领域表现突出，管理规模较大，市场影响力较高。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 四大天王：包括明汯投资、灵均投资、幻方量化和九坤投资。这四家公司在量化投资领域表现突出，管理规模较大，市场影响力较高。

_(+15 条更多帖未展示, 同 sub_cat)_

---

### 22. 百度

- **tier**: 互联网大厂
- **must_have in**: 多模态推理优化, AI PM (2 sub_cat)
- **非 must_have (备选) in**: LLM算法post-train, Agent工程师 (2)
- **industry_focus**: AI 基础设施, AI 应用层
- **source 标签**: demo_v1, xhs:AI PM:2, xhs:多模态推理优化:2
- **notes**:
  - [LLM算法post-train] 文心 post-train
  - [Agent工程师] 搜索 Agent 化
  - [多模态推理优化] 文心多模态
  - [AI PM] 文心一言 PM

#### XHS 帖证据 (7 条)

**[AI PM]** (relevance=0.85) — [https://www.xiaohongshu.com/discovery/item/67ebc3e1000000001](https://www.xiaohongshu.com/discovery/item/67ebc3e1000000001c01f1b7?xsec_token=YBWa4KeVAPAIULbEbAZXtohEB7fLDgjNIzRKmbx1Mtf7g%3D&xsec_source=app_share)

> 帖内提到的公司: 字节跳动, 百度

> **内容快照**:
> 
> 字节面试偏好有owner意识的人，独立拆解问题；熟悉AI产品体验，对趋势有自己见解；能结合体验反馈提出能落地的优化建议。
> 
> AI岗重点问题包括：如何验证功能的效果？用户反馈生成的信息过时，怎么处理？形容自己适合这个岗位的特质？
> 
> 从百度实习到拿下字节豆包AI产品经理岗位。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 字节面试偏好：喜欢有owner意识的人，独立拆解问题；熟悉AI产品体验，对趋势有自己见解（错也没啥）；能结合体验反馈提出能落地的优化建议。
> - AI岗重点问题（建议准备）：如何验证功能的效果？用户反馈生成的信息过时，怎么处理？形容自己适合这个岗位的特质？
> - 从百度实习到拿下字节豆包

**[AI PM]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/672380e3000000001](https://www.xiaohongshu.com/discovery/item/672380e3000000001b02d194?xsec_token=YB3KRHR2f34C3CWoQq_65XYJcRSoUFj_OyhXLP3T34UAU%3D&xsec_source=app_share)

> 帖内提到的公司: 度厂（百度）, 百度

> **内容快照**:
> 
> AI策略PM实习生主要做用户日志数据标注和评估、信息资料整理汇总等dirty work，尚未接触核心PM业务如提需或内审。
> 
> 百度（度厂）的AI策略PM实习岗位，实习生可能面临dirty work较多的情况。

> **verbatim 锚点 (T1/T3 抽取)**:
> - AI策略PM实习（打算做一段长期实习），来了一个月一直还在看用户日志数据标注和评估，或者各类信息资料整理汇总的dirty work。组里面这个专项也就我一个实习生，和其他实习生交流发现很多都已经接触提需或参与内审。感觉自己没有接触到PM主要业务板块
> - 来度厂实习一个月了......AI策略PM实习

**[多模态推理优化]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a05e199000000000](https://www.xiaohongshu.com/discovery/item/6a05e199000000000603777c?xsec_token=YBSoRGoLnXgYWkamAVP-9gF7DimedlFbioD1lHciA1bc4%3D&xsec_source=app_share)

> 帖内提到的公司: OpenAI, Anthropic, Google, xAI, 阿里, DeepSeek

> **内容快照**:
> 
> 2026年4月全球大模型公司能力梯队全景图，T1到T5，涵盖OpenAI、Anthropic、Google、xAI、阿里、DeepSeek、Meta、智谱AI等公司。
> 
> T1梯队估值到1万亿级别，工业级Agent闭环、GPQA推理准确率超94%、代码生成率超85%。
> 
> T2梯队多模态与逻辑推理、代码生成率TOP 5、开源生态标杆。
> 
> T3梯队垂直行业分析、端侧部署、行业级多模态。
> 
> T4梯队政企流式推理、私有化部署、端云协同。
> 
> T5梯队细分场景、端侧部署、开源社区。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 2026年4月全球大模型公司能力梯队全景图，T1到T5，密密麻麻几十家公司。
> - 估值到1万亿级别，工业级Agent闭环、GPQA推理准确率超94%、代码生成率超85%。
> - 多模态与逻辑推理、代码生成率TOP 5、开源生态标杆。

**[多模态推理优化]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69fec4c0000000003](https://www.xiaohongshu.com/discovery/item/69fec4c00000000037037dbe?xsec_token=YBmlLg2uWh_lvMnSZxDHuZ2V4OgGCX8r6chmzqpEoIeMU%3D&xsec_source=app_share)

> 帖内提到的公司: 腾讯, 字节跳动, 阿里巴巴, 美团, 拼多多, 百度

> **内容快照**:
> 
> 腾讯研发实习生薪资从7500涨至13000（含2000房补），涨幅超50%
> 
> 大厂集体上调实习生薪资，AI人才争夺激烈
> 
> 腾讯顶尖人才通过'青云计划'薪酬上不封顶，日薪可达5500元
> 
> 互联网行业重心转向AI，技术岗实习生迎来春天

> **verbatim 锚点 (T1/T3 抽取)**:
> - 去年月薪7500。今年直接干到13000（含2000房补）。一年涨了50%。
> - 大厂集体砸钱，本质是盯上了'AI原生代'
> - 顶尖人才通过'青云计划'：薪酬上不封顶。日薪可达5500元。

**[Agent工程师]** (relevance=0.30) — [https://www.xiaohongshu.com/discovery/item/697c4ad2000000000](https://www.xiaohongshu.com/discovery/item/697c4ad2000000000c0353d8?xsec_token=YBuDmvXxcuij8fN_uhBQhpPbLvlTR2wGDSZoypG9xxuXM%3D&xsec_source=app_share)

> 帖内提到的公司: 阿里淘天, 美团, 百度, 小米, 米哈游, taptap

> **内容快照**:
> 
> 面试中大部分还是围绕项目进行深挖提问，以及相关的八股，能和面试官聊起来一般就问题不大，手撕也不是很难，面试官也会提示。
> 
> 0论文0实习，华五本硕，27届，第一段日常实习入职阿里淘天ai agent岗。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 面试中大部分还是围绕项目进行深挖提问，以及相关的八股，能和面试官聊起来一般就问题不大，手撕也不是很难，面试官也会提示。
> - bg 27届华五本硕 0论文0实习 第一段日常入职阿里淘天ai agent岗

**[AI PM]** (relevance=0.20) — [https://www.xiaohongshu.com/discovery/item/69faec5a000000003](https://www.xiaohongshu.com/discovery/item/69faec5a000000003701da73?xsec_token=YBDAgLlNz5bP_tL8wNE3k6Yzb6XSsm3Jp9QwF14uo4zzc%3D&xsec_source=app_share)

> 帖内提到的公司: 百度

> **内容快照**:
> 
> 百度招聘AI产品经理实习生（视觉方向），要求有AI相关项目或实习经历，熟练使用AI coding软件，有一定代码能力。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 【AI产品经理实习生（视觉方向）】协同推进百度AI视觉能力的迭代优化

_(+1 条更多帖未展示, 同 sub_cat)_

---

### 23. 衍复投资

- **tier**: 头部量化私募
- **must_have in**: 量化研究员·中频, 量化因子工程师 (2 sub_cat)
- **非 must_have (备选) in**: 量化开发QD, AI 量化工程师 (2)
- **industry_focus**: AI 应用层
- **source 标签**: common_knowledge:头部量化私募, taxonomy_doc
- **notes**:
  - [量化研究员·中频] 百亿量化老牌
  - [量化开发QD] 按行业共识
  - [AI 量化工程师] 按行业共识
  - [量化因子工程师] 因子工程岗位多

#### XHS 帖证据 (9 条)

**[量化因子工程师]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a0c2659000000003](https://www.xiaohongshu.com/discovery/item/6a0c2659000000003501c0b8?xsec_token=YBWo3_04eqG7GfzDfPD8xw2IDqvAm1GxyL7BT86NKKem8%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 衍复, 灵均, 世纪前沿

> **内容快照**:
> 
> 幻方、九坤、明汯、衍复是量化“四大天王”出海主力，规模700-800亿，香港办公室持续扩招，提供签证担保和外派补贴。
> 
> 灵均2025年以73.51%收益斩获百亿量化业绩冠军，世纪前沿规模跃升至500-600亿，两家香港团队扩张期，对因子挖掘、建模能力强的同学友好。
> 
> 黑翼2025年新获香港9号牌，量派2024年拿下4+9号双牌照，规模突破300亿，入行门槛相对友好。
> 
> 港圈量化求职门槛：名校硕博，数理/计算机/金工背景优先，英文流利是标配。
> 
> 港圈量化优势：行业顶薪+外派补贴+签证担保，国际化投研平台，职业天花板更高。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 幻方 / 九坤 / 明汯 / 衍复：量化“四大天王”出海主力，规模普遍在700-800亿区间...香港办公室持续扩招。提供签证担保和外派补贴
> - 灵均 / 世纪前沿：2025年灵均以73.51%收益斩获百亿量化业绩冠军...世纪前沿规模跃升至500-600亿...两家香港团队均处于扩张期，对因子挖掘、建模能力强的同学非常友好
> - 黑翼 / 量派：黑翼2025年新获香港9号牌...量派2024年拿下4+9号双牌照，2025年规模已突破300亿...入行门槛相对友好

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a08269a000000003](https://www.xiaohongshu.com/discovery/item/6a08269a000000003803740b?xsec_token=YBg-qzj9nuc27NM7UiNCrdMe8mhPU84fAi2YVlMCQUvgI%3D&xsec_source=app_share)

> 帖内提到的公司: 明汯, 衍复, 灵均, 九坤

> **内容快照**:
> 
> 用户询问量化私募哪个好，提及明汯、衍复、灵均、九坤等头部量化私募。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 量化私募哪个好？

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69f55dc6000000003](https://www.xiaohongshu.com/discovery/item/69f55dc60000000036030768?xsec_token=YBO_g5dxVwlm0aWR4QVRvbiiuom_DAIHrelvWhT7f_Ats%3D&xsec_source=app_share)

> 帖内提到的公司: 明汯投资, 平方和, 顽岩, 黑翼, 衍复, 龙旗

> **内容快照**:
> 
> 2026年4月百亿量化私募备案数据：明汯投资断层领先，4月备案42只，前4个月合计131只，已占去年全年84%。平方和、顽岩、黑翼、衍复等备案量也较高，而宽德、世纪前沿、九坤节奏放缓。新晋百亿私募包括远澜、子午、量道、凯读、鲁民投、知行通达。
> 
> 明汯投资备案节奏激进，渠道承接能力强，对发行窗口积极。
> 
> 宽德、世纪前沿、九坤备案节奏明显放缓，可能更重视容量管理。
> 
> 量化私募规模扩大后，超额收益能否持续是关键问题。
> 
> 新百亿私募出现，量化行业并非头部固化，中腰部仍有上升机会。
> 
> 百亿只是入场券，规模扩大后超额、波动、持有人体验才是真正考验。
> 
> 备案数量可作为观察管理人战略动作的窗口，但不能直接作为选基依据。
> 
> 量化私募竞争最终比拼的是规模变大后仍能做出超额收益。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 2026年4月，百亿量化私募备案数据更新。从YTD数据看，明汯投资仍然断层领先。1月至4月，明汯合计备案131只。其中4月单月备案42只。对比2025年全年156只，明汯前4个月已经完成去年全年约84%的备案量。
> - 这个节奏非常激进。4月的数据说明，它不是短期冲刺，而是在持续加速。背后至少说明两点：渠道承接能力强，管理人对当前发行窗口较为积极。
> - 相比之下，宽德4月备案7只，世纪前沿9只，九坤6只，节奏明显放缓。这不一定说明谁更好，而是说明不同管理人的阶段选择不同。有些机构选择趁市场回暖快速扩张，有些机构更重视容量管理。

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69a0230c000000001](https://www.xiaohongshu.com/discovery/item/69a0230c0000000015032f97?xsec_token=YB2-5hof2I4lVqzOjbMiX6hoxj_8LrGZHtD57Jbms0X6k%3D&xsec_source=app_share)

> 帖内提到的公司: 宽德, 磐松, 衍复, 九坤, 平方和, 顽岩

> **内容快照**:
> 
> 磐松工作环境三年前听说很压抑，现在情况未知。
> 
> 鸣石QR岗位要求博士或计算方向，普通背景难以达到。
> 
> 顽岩QR岗位简历秒拒，竞争激烈。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 磐松现在工作环境怎么样，大概三年前听朋友说很压抑，不知道现在情况如何……
> - 鸣石也有开放的岗位，但JD写明了需要博士或者偏计算的方向，达不到要求。
> - 顽岩也有QR，不过被简历秒拒了。

**[量化开发QD]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/66e2bb15000000002](https://www.xiaohongshu.com/discovery/item/66e2bb1500000000250322d3?xsec_token=YBnUU1iN8f18KnFA1mf0_tLlYuoedHIA9wQDivkysZeaw%3D&xsec_source=app_share)

> 帖内提到的公司: 九坤, 灵均, 明汯, optiver, 天演, 衍复

> **内容快照**:
> 
> 量化私募头部+一线公司包括九坤、灵均、明汯、optiver、天演、衍复、因诺、卓识、洛书等，招聘岗位涵盖C++交易系统开发、策略实现、python系统开发、数据开发、QD、量化研究员（机器学习、深度学习、NLP等）、测试开发，薪酬100w-300w，975节奏。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 量化私募岗位招聘薪酬100w-300w，975节奏

_(+3 条更多帖未展示, 同 sub_cat)_

---

### 24. DeepSeek

- **tier**: 大模型独角兽
- **must_have in**: AI 量化工程师, LLM算法post-train (2 sub_cat)
- **非 must_have (备选) in**: 多模态推理优化 (1)
- **industry_focus**: AI 基础设施
- **source 标签**: demo_v1, taxonomy_doc, xhs:多模态推理优化:1
- **notes**:
  - [AI 量化工程师] 量化条线源自幻方
  - [LLM算法post-train] post-train 行业标杆
  - [多模态推理优化] 推理优化标杆

#### XHS 帖证据 (6 条)

**[Agent工程师]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0bd38b000000000](https://www.xiaohongshu.com/discovery/item/6a0bd38b0000000006021ec6?xsec_token=YBYKS_RIPZhm2MRIQ9dm8Ymfwyag8lMl8Aqz6D4K1OxCs%3D&xsec_source=app_share)

> 帖内提到的公司: DeepSeek

> **内容快照**:
> 
> DeepSeek 是幻方量化孵化的 AGI 公司，2023 年创立，北京/杭州双总部，员工超 300 人，学术氛围浓厚。
> 
> 核心岗位包括深度学习研究员、Agent 算法、核心系统研发、大模型全栈，以及数据策略、产品、运营等。
> 
> 要求 2026-2027 届海外本科及以上学历，CS/AI/数学优先，接受 0 经验应届生但有实习经验和项目成果更优，偏好学术能力强的技术人才。
> 
> 待遇：硕士总包 49-70 万/年，算法岗 50-80K×14 薪，顶尖人才可达百万，股权激励+项目奖金，六险一金+住房补贴+餐补交通补。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 幻方量化孵化的 AGI 领军企业，2023 年创立，开源 DeepSeek-V4 等大模型，数学 / 编程 / 推理能力全球顶尖，北京 / 杭州双总部，员工超 300 人，学术氛围浓厚。
> - 核心招深度学习研究员 / Agent 算法 / 核心系统研发 / 大模型全栈，还有数据策略 / 产品 / 运营，覆盖 7 大职位类 50 + 岗位
> - 要求：2026-2027届海外本科及以上学历，CS/AI/ 数学优先，接受 0 经验应届生但有实习经验和项目成果更优有优势，偏好学术能力强的技术人才

**[多模态推理优化]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a05e199000000000](https://www.xiaohongshu.com/discovery/item/6a05e199000000000603777c?xsec_token=YBSoRGoLnXgYWkamAVP-9gF7DimedlFbioD1lHciA1bc4%3D&xsec_source=app_share)

> 帖内提到的公司: OpenAI, Anthropic, Google, xAI, 阿里, DeepSeek

> **内容快照**:
> 
> 2026年4月全球大模型公司能力梯队全景图，T1到T5，涵盖OpenAI、Anthropic、Google、xAI、阿里、DeepSeek、Meta、智谱AI等公司。
> 
> T1梯队估值到1万亿级别，工业级Agent闭环、GPQA推理准确率超94%、代码生成率超85%。
> 
> T2梯队多模态与逻辑推理、代码生成率TOP 5、开源生态标杆。
> 
> T3梯队垂直行业分析、端侧部署、行业级多模态。
> 
> T4梯队政企流式推理、私有化部署、端云协同。
> 
> T5梯队细分场景、端侧部署、开源社区。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 2026年4月全球大模型公司能力梯队全景图，T1到T5，密密麻麻几十家公司。
> - 估值到1万亿级别，工业级Agent闭环、GPQA推理准确率超94%、代码生成率超85%。
> - 多模态与逻辑推理、代码生成率TOP 5、开源生态标杆。

**[量化研究员·高频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68209b0c000000000](https://www.xiaohongshu.com/discovery/item/68209b0c000000000c03b96a?xsec_token=YBkBiUxr1vgmuF9SZyZnmQfkUrtE4P5n8gWgDeTynkmkg%3D&xsec_source=app_share)

> 帖内提到的公司: 正定私募, 幻方, DeepSeek, 黑翼, 九坤

> **内容快照**:
> 
> 量化开发实习生每天800-1600元，深度学习研究员基础包60-90k*14
> 
> 某顶级大模型公司开出130-260k*24薪，疑似DeepSeek
> 
> 量化策略在A股市场表现优于主观多头，百亿私募近半年业绩排名前10均为量化机构
> 
> 量化交易依赖高成交量，924之后市场成交量显著上升，适合量化做出超额

> **verbatim 锚点 (T1/T3 抽取)**:
> - 正定私募给量化开发实习生每天800-1600，幻方给深度学习研究员的基础包是60-90k*14
> - 某神秘的“顶级大模型公司”开出130-260k*24薪...（有人说是deepseek）
> - 从私募排排网最新公布的【百亿私募近半年业绩排名】来看，量化已经全面碾压了主观！收溢前10的公司都是量化机构

**[量化研究员·高频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6965096a000000000](https://www.xiaohongshu.com/discovery/item/6965096a000000000e00c8d9?xsec_token=YBxXGBFQGjE4OD8HZhu2pFW9lFIerhI5KZppQPLSblogc%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方量化, 宁波灵均, DeepSeek

> **内容快照**:
> 
> 幻方量化2025年实现平均回报56.6%，管理规模约700亿人民币，营收推测超7亿美元。
> 
> 中国量化基金平均回报率30.5%，是全球同类基金平均回报的两倍以上。
> 
> DeepSeek利用幻方量化的利润支持研发，形成“二级市场利润——顶级算力供给”内循环。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 幻方量化（High-Flyer）旗下基金在2025年实现了平均回报56.6%
> - 同期中国量化基金平均回报率为30.5%，是全球同类基金平均回报的两倍以上
> - 幻方的巨额利润直接充当了DeepSeek的军火库

**[量化研究员·高频]** (relevance=0.30) — [https://www.xiaohongshu.com/discovery/item/69f2fc31000000001](https://www.xiaohongshu.com/discovery/item/69f2fc31000000001a035b1c?xsec_token=YBzgay49aBCOWB8ud1795byeetEiHNNNO77cdZ73Piz2o%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方量化, DeepSeek

> **内容快照**:
> 
> 幻方量化管理规模超700亿，DeepSeek估值超万亿。他用“量化养AI”，走出了一条谁都没走过的路
> 
> 中国AI不可能永远停留在跟从阶段

> **verbatim 锚点 (T1/T3 抽取)**:
> - 幻方量化管理规模超700亿，DeepSeek估值超万亿。他用“量化养AI”，走出了一条谁都没走过的路
> - 中国AI不可能永远停留在跟从阶段

**[Agent工程师]** (relevance=0.20) — [https://www.xiaohongshu.com/discovery/item/6a0e7290000000003](https://www.xiaohongshu.com/discovery/item/6a0e72900000000036032d7b?xsec_token=YB86Pau54mbQHq-ixshhOwAbmJZADr3ipvmS_d9dkP9ZI%3D&xsec_source=app_share)

> 帖内提到的公司: DeepSeek

> **内容快照**:
> 
> DeepSeek正在招聘Agent Harness研发工程师和产品经理，表明其正式进入Agent产品化领域。
> 
> Agent赛道竞争加剧，DeepSeek对标Claude Code、Codex、Cursor等产品。

> **verbatim 锚点 (T1/T3 抽取)**:
> - DeepSeek挂出了两个新岗位，一个Agent Harness研发工程师，一个Agent Harness产品经理
> - 要求里直接点名了一串竞品：Claude Code、Codex、Cursor、Manus、OpenClaw

---

### 25. 富国基金

- **tier**: 一线公募
- **must_have in**: 公募权益研究员, 公募基金中后台 (2 sub_cat)
- **非 must_have (备选) in**: 财富管理FOF (1)
- **industry_focus**: 医药, 消费, 金融
- **source 标签**: demo_v1, saif:2025, taxonomy_doc, xhs:财富管理FOF:1
- **notes**:
  - [公募权益研究员] 应届招聘强信号,起薪 17-28 万
  - [公募基金中后台] 产品风控简历数超投研类
  - [财富管理FOF] 投顾产品线

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2025 | 富国基金管理有限公司 | 行业研究员 | 1 | 公募基金 |

#### XHS 帖证据 (2 条)

**[信用研究员]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/69a8107c000000001](https://www.xiaohongshu.com/discovery/item/69a8107c000000001a0256c1?xsec_token=YBKa6dGSqoDQiE-oV489_9WKftQkmztfGn52RVw7CycAU%3D&xsec_source=app_share)

> 帖内提到的公司: 富国基金, 易方达, 华夏

> **内容快照**:
> 
> 富国基金信用研究员面试包含10道问题，涉及城投债评级上调、信用下沉策略、地产债暴跌、行业规避、审计师变更、信用与权益研究方法论差异、流动性枯竭、公司对比、AI替代、发行人暗示美化评级等场景，并带有追问。
> 
> 信用研究员岗位需要处理评级与风险判断冲突、信用下沉策略、流动性危机、与投资经理沟通、职业道德困境等。
> 
> 富国基金信用研究岗位面试题涉及与易方达、华夏的对比，以及保险资管挖角场景。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 1. 如果某城投债评级上调，但你觉得风险加大，信谁？...10. 如果某发行人暗示'适当美化评级可以合作'，怎么处理？
> - 信用研究员面试真题拆解分析
> - 怎么看富国信用和易方达、华夏的差距？

**[财富管理FOF]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69b7adf5000000001](https://www.xiaohongshu.com/discovery/item/69b7adf5000000001d01e2cb?xsec_token=YBUbBPgCnu6HsJND6ndu6QErhvAcLeTam3vb19cHq1TBk%3D&xsec_source=app_share)

> 帖内提到的公司: 富国基金, 中欧基金, 易方达基金, 广发基金, 博时基金, 交银施罗德基金

> **内容快照**:
> 
> FOF（基金中的基金）近期在公募市场热度上升，发行数量和规模大幅增长，银行渠道推动明显，产品设计以短持有期、偏债混合策略为主。
> 
> FOF总规模突破3000亿，头部公司如富国、中欧、易方达、广发规模超200亿，但行业格局未固化。
> 
> FOF热度背后原因包括存款利率下行、市场波动大、银行渠道转型、产品设计适配等。
> 
> FOF行业趋势：从选基转向配置，产品形态纳入黄金ETF、REITs、QDII等，与养老联动。

> **verbatim 锚点 (T1/T3 抽取)**:
> - FOF（基金中的基金）突然成了公募市场的热门话题。截至3月14日，今年全市场已经有40只FOF成立，合计募了619.73亿元。跟去年一季度比，数量增加了233%，规模增长了361%。
> - 截至3月14日，FOF总规模突破3000亿。84家公募有布局，但头部还没固化：规模最大的管理人约245亿，规模超100亿的只有11家。第一梯队：富国、中欧、易方达、广发都超200亿。
> - 一是存款利率下行，叠加市场波动大，个人做择时、选基金的难度在增加。FOF的逻辑是通过专业选基+多资产配置，降低单一资产的波动。二是银行渠道从'卖产品'转向'卖配置方案'。三是产品设计的适配。

---

### 26. 工银瑞信基金

- **tier**: 二线公募
- **must_have in**: 行业研究员·TMT-医药-周期, 公募指数研究员 (2 sub_cat)
- **非 must_have (备选) in**: 公募权益研究员 (1)
- **industry_focus**: TMT, 周期
- **source 标签**: saif:2024, saif:2025, taxonomy_doc
- **notes**:
  - [公募权益研究员] 银行系公募,行业首席强
  - [行业研究员·TMT-医药-周期] TMT/周期产业链覆盖
  - [公募指数研究员] 银行系 ETF 强

#### SAIF 校友流向证据 (2 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 工银瑞信基金管理有限公司 | 行业研究员 | 1 | 公募基金 |
| 2025 | 工银瑞信基金管理有限公司 | 行业研究员 | 1 | 公募基金 |

#### XHS 帖证据 (4 条)

**[公募权益研究员]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/69b01b10000000000](https://www.xiaohongshu.com/discovery/item/69b01b10000000000601f681?xsec_token=YB3mubOgxaYuySVOQc18ibYOSsyNMwYBOBRr4DQeL0kMQ%3D&xsec_source=app_share)

> 帖内提到的公司: 工银瑞信, 中信建投基金, 嘉实基金, 天弘基金, 华夏基金

> **内容快照**:
> 
> 公募基金面试通过推票（基本面分析）、近期行情判断（策略框架）、关键行业事件（行业趋势洞察力）、市场风险溢价（宏观分析能力）这四类问题判断候选人综合潜力。
> 
> 公募基金实习阶段通过观察日常工作习惯、课题沟通能力、任务完成程度、工作自驱力判断实习生。
> 
> 公募基金答辩考察候选者能否将研究转化为包含价格与时点的具体观点。
> 
> 公募基金高管面通过观察候选人与上位者的沟通姿态及回答内容，检验职业兴趣和组织稳定度。
> 
> 作者秋招投递了多家公募基金，包括某top3公募（暑期投研）、工银瑞信（拿到pass卡后放弃）、中信建投基金（暑期后放弃）、嘉实基金（简历挂）、天弘基金（面试挂）、华夏基金（简历挂）。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 面试阶段，通过推票（基本面分析）、近期行情判断（策略框架）、关键行业事件（行业趋势洞察力）、市场风险溢价（宏观分析能力）这四类问题能准确判断候选人的综合潜力、职业兴趣、时间投入。
> - 实习中，通过观察日常工作习惯、课题沟通能力、任务完成程度、工作自驱力增加对实习生的深层次判断。
> - 答辩中，通过考察短时间内的输出情况，衡量候选者能否将研究转化为包含价格与时点的具体观点，完成对业务能力的下半场判断。

**[利率宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0eccec000000003](https://www.xiaohongshu.com/discovery/item/6a0eccec000000003501dc63?xsec_token=YB22ackc46J7CVQ3eyo-O2yb4R7YNtXOUggzr-SLogjLs%3D&xsec_source=app_share)

> 帖内提到的公司: 工银瑞信

> **内容快照**:
> 
> 工银瑞信宏观利率面试考察思维深度，要求候选人能讲清楚从carry思维到久期管理的切换逻辑，以及如何用边际思维判断利率拐点。
> 
> 面试官关注候选人如何将央行政策、资金面扰动和机构行为串成逻辑链，而非单纯堆数据。
> 
> 特殊情境下（如窄幅震荡市）策略框架需自洽，底层逻辑闭环是通关密码。
> 
> 列举了工银瑞信宏观利率面试的高频问题，包括久期、收益率曲线、凸性、货币政策、通胀预期、信用利差、回购交易等。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 从 carry思维 到 久期管理 的切换逻辑，面试官要的不是你背结论，而是看你能不能把“预期差”讲清楚。
> - 核心难点 在于怎么把央行政策、资金面扰动和机构行为串成一条逻辑链。很多人只会堆数据，但面试官想听的是你如何用“边际思维”去判断拐点
> - 特殊情境 下比如窄幅震荡市，你的策略框架得能自洽。所以，工银瑞信这种级别的面试，套路反而是次要的， 底层逻辑的闭环 才是通关密码。

**[行业研究员·消费]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68523924000000002](https://www.xiaohongshu.com/discovery/item/685239240000000022028983?xsec_token=YB1tOVHt4MrRCgE3YRmfKUfzkX4Zhwklu8QU9qotk8kHY%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达, 华夏, 博时, 国泰, 汇添富, 南方

> **内容快照**:
> 
> 易方达、华夏是头部公募，整体待遇好，科技岗位应届生薪资尤其高。
> 
> 博时、国泰、汇添富、南方类似公务员氛围。
> 
> 银行系公募（招商、中银、工银）薪资相对固化，待遇提升空间有限，但工作相对安逸。
> 
> 永赢、嘉实、鹏华待遇不错，但工作强度卷王级别。
> 
> 兴全待遇不错，人少资源多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 易方达、华夏：头部中的头部，整体待遇不会太差，据说科技岗位应届生薪资对比其他应届会尤其高一些
> - 博时、国泰、汇添富、南方：据说类似公务员氛围浓厚
> - 银行系包括（招商、中银、工银等）薪资相对固化，待遇可提升空间对比其他就不太行了，安逸也是相对的吧

**[资管FOF]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68076825000000001](https://www.xiaohongshu.com/discovery/item/68076825000000001a0066db?xsec_token=YB99eH8k09Rv7rNLHjW60O0BTN6QzTKurNuAdNZ06-eic%3D&xsec_source=app_share)

> 帖内提到的公司: 交银施罗德基金, 兴证全球基金, 民生加银基金, 汇添富基金, 南方基金, 浦银安盛基金

> **内容快照**:
> 
> FOF行业规模从2021年的2253亿降至2024年底的1442亿，降幅36%，多家公司规模大幅缩水。
> 
> 交银施罗德基金FOF团队仅剩2名基金经理，规模排名从第一跌至第七。
> 
> 兴证全球基金FOF团队以林国怀为带头人，成员背景多元，包括互联网大厂和海外金融背景。
> 
> 易方达基金FOF团队由汪玲牵头，成员如刘淑霞有券商资管FOF业务负责人经验。
> 
> 中欧基金FOF团队由桑磊牵头，成员有险资投资管理经验。
> 
> 华夏基金FOF团队汇聚了许利民、廉赵峰、李晓易、卢少强等精兵强将。
> 
> 工银瑞信FOF团队赵志源接替蒋华安成为FOF投资部总经理并进入投委会，陈涵任研究副总监。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 截至2024年底，共有87家基金公司管理着511只FOF产品，资产净值规模合计1442亿元，相比2021年的2253亿降幅36%。
> - 交银施罗德FOF团队则仅见2人：刘兵，经济学博士，2016年加入交银施罗德基金；刘迪，金融工程与投资管理博士，2015年加入交银施罗德基金。
> - 兴证全球基金以公司总经理助理、FOF投资与金融工程部总监、养老金管理部总监林国怀为带头人，团队成员既有来自互联网大厂的成员，也有来自海外金融从业背景的成员。

---

### 27. 广发基金

- **tier**: 一线公募
- **must_have in**: 公募权益研究员, 固收+多资产 (2 sub_cat)
- **非 must_have (备选) in**: 公募基金中后台 (1)
- **industry_focus**: TMT, 周期, 消费, 金融
- **source 标签**: common_knowledge:头部公募, saif:2024
- **notes**:
  - [公募权益研究员] 按行业共识,公募 AUM top 5
  - [公募基金中后台] 按行业共识
  - [固收+多资产] 按行业共识

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 广发基金管理有限公司 | 行业研究员 | 1 | 公募基金 |

#### XHS 帖证据 (18 条)

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[信用研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69ca9946000000001](https://www.xiaohongshu.com/discovery/item/69ca9946000000001b00076b?xsec_token=YBLMCeCSnGE4YGO-OsDjX8sNGlfn7z3BDpFmaRlwFA3Wo%3D&xsec_source=app_share)

> 帖内提到的公司: 广发基金

> **内容快照**:
> 
> 广发基金固收研究员面试题目汇总，涵盖固收研究兴趣、宏观利率分析、信用风险分析、可转债、久期等核心问题。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 广发基金｜固收研究员面经汇总🔥

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69bbb886000000002](https://www.xiaohongshu.com/discovery/item/69bbb886000000002b00dc0f?xsec_token=YBY-rrGTG456s3Kutg82G2iAMfesSM55ZOeJkEKPkgzAA%3D&xsec_source=app_share)

> 帖内提到的公司: 三中一华, 广发证券, 招商证券, 国信证券

> **内容快照**:
> 
> 学生背景211本+中9硕，实习经历包括一段颈部券商股承做和两段TMT行研（新财富），未来可能路径为行研、投行、PE/VC。
> 
> 学生获得四个top15券商的实习offer：三中一华债、广发机械/通信（新财富）、招商TMT、国信债。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 🏠211本+中9硕，实习经历，一段颈部券商股承做，两段TMT行研（新财富）。未来的发展路径没有想好，可能是行研、投行、PE/VC。
> - 手上的实习offer（全是top15券商）1️⃣三中一华 债 2️⃣广 机械/通信（新财富）3️⃣招 TMT 4️⃣国x 债

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000](https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000702ace7?xsec_token=YB9MVh1sELWdJvRY7-4rURZo9qtVNwXXJJLAGIjlCzytE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 中金公司, 华泰证券, 中信建投证券, 申万宏源

> **内容快照**:
> 
> 中信证券多项业务指标连年夺魁，是券商中的'神'级公司。
> 
> 国泰海通由国开君安和海通证券合成，资本实力跃居行业榜首。
> 
> 中金公司是首家中外合资投行，投行业务标杆。
> 
> 华泰证券是金融科技+财富管理领域的标杆。
> 
> 中信建投证券降薪严重，与前三个相比掉队。
> 
> 2025年证券行业呈现'强者恒强'的马太效应，头部券商占据大部分市场份额。
> 
> 头部券商总部前台岗求职难度不输国有总行，建议根据学历背景和实习相关性合理选择。
> 
> 随着大A慢牛市场，证券公司实习机会增多，26届应把握机会。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 中信证券可以单独开一个'神'级，多项业务指标连年夺魁
> - 国泰海通由国开君安和海通证券合成而成的新龙头，资本实力跃居行业榜首
> - 中金公司，首家中外合资投行，投行业务标杆

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a00852d000000000](https://www.xiaohongshu.com/discovery/item/6a00852d0000000008002bb5?xsec_token=YBYM1cUi6i2AdR2d2EYp7gy0jrM93HeTyqyT4_9HsqWHE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 华泰证券, 中金证券, 中信建投, 招商证券

> **内容快照**:
> 
> 券商分为五个梯队，第一梯队包括中信证券、国泰海通、华泰证券、中金证券、中信建投等，平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> 
> 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> 
> 第一梯队偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历更加分。
> 
> 第三梯队门槛相对灵活，海外院校、转专业同学都有机会，关键是简历里要体现对金融行业的理解。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> - 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> - 通常更偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历会更加分。

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69c4038e000000002](https://www.xiaohongshu.com/discovery/item/69c4038e00000000230125c5?xsec_token=YB0UsFJCDs7aM6X-Lq9bShYk2aYkjgRrrPBlPYUFvugTk%3D&xsec_source=app_share)

> 帖内提到的公司: 广发证券

> **内容快照**:
> 
> 广发证券行业研究员面试问题汇总，包括如何应对不熟悉的任务、优点、人际关系、行业分析报告、政策变化分析、数据质量、核心工作、定性定量分析、报告组织等。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 广发证券｜行业研究员面经汇总🔥

_(+12 条更多帖未展示, 同 sub_cat)_

---

### 28. 美团

- **tier**: 互联网大厂
- **must_have in**: AI PM, AI算法业务 (2 sub_cat)
- **非 must_have (备选) in**: Agent工程师 (1)
- **industry_focus**: AI 应用层
- **source 标签**: demo_v1, taxonomy_doc, xhs:AI PM:2
- **notes**:
  - [Agent工程师] 本地生活 Agent
  - [AI PM] 本地生活 AI 应用 PM
  - [AI算法业务] 外卖/到店推荐算法

#### XHS 帖证据 (8 条)

**[AI PM]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68a5770b000000001](https://www.xiaohongshu.com/discovery/item/68a5770b000000001b032042?xsec_token=YBMn-3vXRkAwKVWQG-g_6rmGDJaKO4_2jclTetcReqh8o%3D&xsec_source=app_share)

> 帖内提到的公司: 字节跳动, 网易, 美团, 抖音

> **内容快照**:
> 
> AI PM 求职时，大厂和小公司各有优劣：大厂资源多但创新受限，小公司在应用层机会更大。
> 
> AI 应用层机会在垂直细分领域，小而美的公司能更灵活地落地。
> 
> 大厂 PM 岗位流动性下降，招聘需求减少，竞争激烈。
> 
> 与字节 PM 学长 coffee chat 后，作者不再执念大厂，更看重创新和 AI 落地空间。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 小公司在应用层的机会反而更大。大厂体量大了，幻觉问题、安全合规问题，都会让产品变得“重”，交互上趋于保守。
> - 这些极其精细化、垂直化的AI应用，会被无数“小而美”的公司吃下来。
> - 业务增长放缓，没有那么多新坑了，招聘需求也就少了。

**[AI PM]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69f3a24f000000002](https://www.xiaohongshu.com/discovery/item/69f3a24f0000000023015de3?xsec_token=YB-AiMO2H5GuGCVoejEnwU3sdVSSVKzKs5Tjsbi993k9E%3D&xsec_source=app_share)

> 帖内提到的公司: 美团, 阿里云, 联想

> **内容快照**:
> 
> AI产品实习面试更看重产品思维、问题理解和将技术转化为产品的能力，而非纯技术深度。
> 
> 美团面试节奏快，偏数据+业务逻辑，深挖个人项目；阿里云更偏AI产品逻辑+用户链路+技术方法；联想偏AI应用+场景落地。
> 
> 零实习背景可通过个人项目（如vibecoding快速完成）弥补，项目经验在面试中很加分。
> 
> AI产品岗面试中，技术考察并不深奥，更注重对AI应用场景的理解和表达能力。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 面试官更看：你怎么理解问题，有没有产品思维，能不能把技术讲成产品
> - 美团：偏数据+业务逻辑，深挖个人项目；阿里云：更偏AI产品逻辑+用户链路+需要懂更多技术方法；联想：偏AI应用+场景落地
> - vibecoding两天就能完成一个个人项目 很容易但是简历很加分

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[公募权益研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a154d91000000000](https://www.xiaohongshu.com/discovery/item/6a154d91000000000702163f?xsec_token=YBtykXCAFyiHSXD_GpX4xfBCEPl85Qoq2k5vZtdH2VHjI%3D&xsec_source=app_share)

> 帖内提到的公司: 泰康资产, 景顺长城, 中投, 社保基金, 外管局外汇中心, 易方达基金

> **内容快照**:
> 
> 泰康资产和景顺长城正在面试辅导，涉及投研岗位。
> 
> 辅导的offer覆盖一级投资（含PE及PERE）、战投、产投、二级投研、投行、银行、理财子、金融央国企等。
> 
> 辅导过腾投、GIC、易方达基金、华夏基金、泰康资产、bb行、中金、华泰、中投、中信集团管培、社保基金、外管局外汇中心、国寿投资、建总、工总、农发总、新华社、强势部委等top全职offer。
> 
> 背景一般甚至有明显bug的也能辅导上岸top全职offer，例如两财一贸tier拿下大买投研，本科top10之外硕士QS100-200拿下头部保险资管投研，非top4本硕上岸头部一级投资岗等。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 泰康资产+景顺长城面试辅导
> - 自己投递的offer覆盖一级投资（含pe及pere）/战投产投/二级投研/投行/银行/理财子/金融央国企/垄断型央企/部委/另类的all rounder实力
> - 辅导腾投/GIC/易方达基金/华夏基金/泰康资产/bb行/中金/华泰/中投/中信集团管培/社保基金/外管局外汇中心/国寿投资/建总/工总/农发总/新华社/强势部委等top全职offer的实力

**[多模态推理优化]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69fec4c0000000003](https://www.xiaohongshu.com/discovery/item/69fec4c00000000037037dbe?xsec_token=YBmlLg2uWh_lvMnSZxDHuZ2V4OgGCX8r6chmzqpEoIeMU%3D&xsec_source=app_share)

> 帖内提到的公司: 腾讯, 字节跳动, 阿里巴巴, 美团, 拼多多, 百度

> **内容快照**:
> 
> 腾讯研发实习生薪资从7500涨至13000（含2000房补），涨幅超50%
> 
> 大厂集体上调实习生薪资，AI人才争夺激烈
> 
> 腾讯顶尖人才通过'青云计划'薪酬上不封顶，日薪可达5500元
> 
> 互联网行业重心转向AI，技术岗实习生迎来春天

> **verbatim 锚点 (T1/T3 抽取)**:
> - 去年月薪7500。今年直接干到13000（含2000房补）。一年涨了50%。
> - 大厂集体砸钱，本质是盯上了'AI原生代'
> - 顶尖人才通过'青云计划'：薪酬上不封顶。日薪可达5500元。

**[行业研究员·消费]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/696729d4000000000](https://www.xiaohongshu.com/discovery/item/696729d4000000000903bdc5?xsec_token=YBAMDdm3wuYKXWaq7X1DYHPlgHF8WY8vP6bJfSg7d7BFA%3D&xsec_source=app_share)

> 帖内提到的公司: 美团

> **内容快照**:
> 
> 美团到餐商业分析师补贴政策方向面试题：包括补贴战略目标、预算分配方案论证、活动诊断、补贴定义、羊毛党识别、竞争策略、补贴方式对比、监控看板设计。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 1️⃣对于美团到餐这样一个成熟的业务，为什么还需要持续、大规模地投入补贴？补贴的核心战略目标是什么？...8️⃣如果让你来为补贴策略团队，设计一个核心的日常数据监控看板，你会放入哪5个最关键的指标？

_(+2 条更多帖未展示, 同 sub_cat)_

---

### 29. 蚂蚁集团

- **tier**: 互联网大厂
- **must_have in**: LLM算法post-train, Agent工程师 (2 sub_cat)
- **非 must_have (备选) in**: AI PM (1)
- **industry_focus**: AI 应用层, 金融
- **source 标签**: demo_v1, taxonomy_doc
- **notes**:
  - [LLM算法post-train] 金融 AI post-train
  - [Agent工程师] 百宝箱 Agent 平台
  - [AI PM] 百宝箱 PM

#### XHS 帖证据 (1 条)

**[LLM算法post-train]** (relevance=0.20) — [https://www.xiaohongshu.com/discovery/item/6a0eb099000000003](https://www.xiaohongshu.com/discovery/item/6a0eb0990000000035031525?xsec_token=YB86Pau54mbQHq-ixshhOwATT7wD2xuYDeKCXhQECFgwY%3D&xsec_source=app_share)

> 帖内提到的公司: 蚂蚁集团

> **内容快照**:
> 
> 蚂蚁集团百灵大模型北京office急缺intern和校招，接受无经验，有mentor带教。
> 
> 岗位方向包括AI大模型算法、软件开发、产品运营、前后端开发。
> 
> 优先计算机、数学、统计、软工、AI、电子信息等专业，25-29届本科及以上留学生。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 蚂蚁集团百灵大模型北京office真的在急缺人，intern和校招都有hc，对留学生很友好。
> - AI大模型算法、软件开发、产品运营、前后端开发（少量）
> - 计算机、数学、统计、软工、AI、电子信息这类专业会更优先一些。

---

### 30. Citadel

- **tier**: 外资行
- **must_have in**: 量化研究员·高频, 买方 Quant (2 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: —
- **source 标签**: common_knowledge:头部对冲基金, taxonomy_doc
- **notes**:
  - [量化研究员·高频] 按行业共识,Citadel Securities 高频
  - [买方 Quant] 按行业共识

#### XHS 帖证据 (9 条)

**[买方 Quant]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/695940c8000000001](https://www.xiaohongshu.com/discovery/item/695940c8000000001e03a19c?xsec_token=YBrJ_goExM-LGFpD_KXswc_GrNMq5jKropLNK56upboAU%3D&xsec_source=app_share)

> 帖内提到的公司: 高盛, 摩根士丹利, 中金, 中信里昂, 幻方, 灵均

> **内容快照**:
> 
> 大湾区量化岗位分为卖方Quant（投行）和买方Quant（基金/私募），卖方Quant集中在香港，买方Quant在深圳更活跃。
> 
> 香港的卖方Quant主要集中在国际投行（高盛、摩根士丹利等）和中资投行国际子公司（中金、中信里昂），深圳的卖方机会在国内券商的金融工程/量化自营部门。
> 
> 深圳的买方Quant核心是顶尖量化私募（幻方、灵均等），香港的买方Quant包括全球顶级对冲基金和自营交易公司（Citadel, Two Sigma, Optiver等）。
> 
> 深圳的量化岗位面试必考对国内金融数据源（Wind, Tushare, JoinQuant）和A股交易规则的熟悉度。
> 
> 香港的量化岗位面试对期权定价、随机微积分等理论要求更深。
> 
> 深圳偏好国内顶尖理工院校（清北复交、浙大、中科大等）的硕士/博士，海外名校需对国内市场有理解；香港偏好全球顶级名校（美英顶尖高校、新加坡两所、港三所），专业排名比学校综合排名更重要。
> 
> 纯金融背景竞争力弱，数学、物理、计算机、电子工程等硬核专业是绝对主流。
> 
> 大湾区量化岗位技能要求：Python、SQL、Linux是基础；深圳需精通C++，香港需英语工作能力和kdb+/q等工具。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 在大湾区，两者的重心和机会有显著差异：1. 卖方Quant（以投行为主）：香港是绝对中心...2. 买方Quant（以基金/私募为主）：深圳是核心战场...
> - 国际投行（高盛、摩根士丹利等）及中资投行的国际子公司（中金、中信里昂等）的量化团队主要聚集于香港。
> - 深圳是核心战场：聚集了全国最顶尖、最活跃的量化私募（幻方、灵均等）...香港是国际桥头堡：云集了全球顶级对冲基金和自营交易公司（Citadel, Two Sigma, Optiver等）

**[量化研究员·高频]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/68af99f5000000001](https://www.xiaohongshu.com/discovery/item/68af99f5000000001d0394d1?xsec_token=YBMDFvAjSpbmV4GsOnphQWMFHXTSkeRFuR29faZgPTTsU%3D&xsec_source=app_share)

> 帖内提到的公司: Optiver, Citadel Securities

> **内容快照**:
> 
> Optiver qr第一轮面试包括三个场景（硬币、扑克牌、骰子）的betting game，面试官会追问问题，风险偏好低可能影响结果。
> 
> Cit Sec qt第一轮面试包括简历问题和两个case：一个是抽牌比大小并计算fair price，另一个是三个城市人口的market making游戏。

> **verbatim 锚点 (T1/T3 抽取)**:
> - Optiver qr的第一轮和qt一样，还是那个三个场景（硬币 扑克牌 骰子）的betting game，这次面试官是个从nsfz毕业的老中，整体流程还是和网上看到差不多，先简单问问简历，然后就是玩游戏。但我不知道为什么，这次被面试官评价我的风险偏好比较低
> - Cit Sec第一轮面试官是个hypsm毕业的亚女，总体来说人还是挺好的（毕竟从结果来看没挂我），但是不知道为什么本来预计45min的面试，硬生生面了70min啊。一开始她关于我简历上她感兴趣的部分问了几个问题（没有bq），然后就是两个case，一个是两个人玩抽牌（数字）的游戏比大小，然后我可以（may）选择重新抽一次，有三个不同的情形（关于对面的数）然后分别计算fair price。另一个是对于三个城市人口的market making，分别给出spread为10% 20% 30%（自己决定分别给哪个城市）的bid and offer，然后她会分别选择buy or sell，然后我根据结果再次重新给出那六个价格，以此类推玩了几轮，期间也有一些追问

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/696e0157000000000](https://www.xiaohongshu.com/discovery/item/696e0157000000000b00aa49?xsec_token=YBLzx7ZossRnL_aAxZjlYx2SzHExIvcl7Ifjrej0KQEMY%3D&xsec_source=app_share)

> 帖内提到的公司: Jane Street, HRT, Optiver, Virtu, DRW, Tower Research

> **内容快照**:
> 
> Quant公司可按交易频率和团队结构分为四类：高频协作（如Jane Street, HRT, Optiver）、高频个体化（如Virtu, DRW, Tower Research）、低频协作（如RenTec, QRT）、低频个体化（如Millennium, Citadel, BAM）。
> 
> 不同分类对应不同技能树：高频公司注重编程、算法设计、系统架构和低延迟优化，C++和硬件知识关键；低频公司更看重统计建模、机器学习和基本面分析，Python和R常用。
> 
> 团队文化影响技能：协作型需要善于沟通和团队合作；个体型要求高度自驱和独立解决问题能力。
> 
> Quant公司分类包括高频做市商、自营交易公司、系统化对冲基金、多策略对冲基金等。
> 
> 学员拿到Brevan Howard、Optiver的Quant Trading Offer，以及JPM、Citi、高盛的Quant岗。

> **verbatim 锚点 (T1/T3 抽取)**:
> - Jane Street、HRT、Optiver属于高频协作类...Virtu、DRW、Tower Research则是高频但更个体化...RenTec、QRT这类是协作式系统化投资...Millennium、Citadel的pod结构或BAM这类，是低频且高度siloed
> - 高频公司，技能重点在编程、算法设计、系统架构和低延迟优化，C++和硬件知识往往是关键。低频公司则更看重统计建模、机器学习和基本面分析能力，Python和R用得多
> - 协作型需要你善于沟通和团队合作...个体型则要求高度自驱和独立解决问题能力

**[行业研究员·TMT-医药-周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69bebcfd000000001](https://www.xiaohongshu.com/discovery/item/69bebcfd000000001a033461?xsec_token=YB9Iqi9eyKW3iHkWzWOke-qr5Z3tZK0qSa1zem4AN7Zxg%3D&xsec_source=app_share)

> 帖内提到的公司: Point72, Citadel

> **内容快照**:
> 
> 二级买方行研助手使用AI Agent提效，核心工作包括报告解析、宏观交叉验证、历史可比事件分析。
> 
> 半导体行业更新报告处理中，AI Agent可自动提取供应链变化、财务指标和趋势描述。
> 
> 面试中可能被问及如何利用AI工具提升行研效率，以及AI与人类判断的边界。

> **verbatim 锚点 (T1/T3 抽取)**:
> - Cursor让二级买方行研助手提效落地
> - 处理半导体行业更新报告时，我直接把AI Agent当成了核心行研助手
> - AI不取代人的最终判断——它擅长模式匹配和数据梳理，但宏观语境和突发事件解读仍需研究员经验把关

**[行业研究员·TMT-医药-周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69f4b12d000000001](https://www.xiaohongshu.com/discovery/item/69f4b12d000000001e00e3ff?xsec_token=YBmSakPnFEHN3Znl_nYcnGtSPqtLgDNxAwtXMcedWxamE%3D&xsec_source=app_share)

> 帖内提到的公司: Point72, Millennium, Citadel

> **内容快照**:
> 
> 二级行研研究员开始更多研究互联网产品，以更好理解价值创造源头。
> 
> PM和买方研究员转向研究互联网产品。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 研究员不再把精力完全all in传统的二级权益，而是开始更多地转身去研究和拥抱互联网产品。
> - 不少PM和买方研究员不再把精力完全all in传统的二级权益，而是开始更多地转身去研究和拥抱互联网产品。

**[行业研究员·TMT-医药-周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/696b5eb6000000021](https://www.xiaohongshu.com/discovery/item/696b5eb6000000021a0242d5?xsec_token=YBFVdwr1N5lDt73WdLpOM_jSvqAS4T6GFB9bmeARGwc2c%3D&xsec_source=app_share)

> 帖内提到的公司: Point72, Millennium, Citadel, 宁德时代, 台积电

> **内容快照**:
> 
> 对冲基金买方研究员岗位需要构建系统化的基本面研究框架，而非盲目追热点。
> 
> 面试中展示对具体公司（如宁德时代）的深入分析能力，包括上游原材料依赖和下游需求弹性。
> 
> EV行业当前市场焦点在电池供应链，半导体周期分析需考虑产能利用率和地缘风险。
> 
> Point72、Millennium、Citadel是知名的对冲基金，招聘买方研究员。
> 
> 简历中应突出系统化基本面研究能力和对具体行业的深入理解。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 关键在于构建系统化的基本面研究框架，而非盲目追热点。
> - 深入拆解其上游原材料依赖和下游需求弹性。
> - 现在市场焦点在电池供应链上，像宁德时代这样的公司...分析台积电时，要从产能利用率到地缘风险的逻辑链。

_(+3 条更多帖未展示, 同 sub_cat)_

---

### 31. 小红书

- **tier**: 互联网大厂
- **must_have in**: Agent工程师, AI算法业务 (2 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: AI 应用层
- **source 标签**: demo_v1, taxonomy_doc
- **notes**:
  - [Agent工程师] 内容 Agent
  - [AI算法业务] 内容推荐/搜索算法

#### XHS 帖证据 (1 条)

**[AI PM]** (relevance=0.20) — [https://www.xiaohongshu.com/discovery/item/69de2d59000000002](https://www.xiaohongshu.com/discovery/item/69de2d5900000000230168ca?xsec_token=YBLGT4q0rGwVOwcnwEkfrWQHbMZ0nsvlYMj0YxBK5jv5o%3D&xsec_source=app_share)

> 帖内提到的公司: 小红书

> **内容快照**:
> 
> 小红书面经，AI产品经理岗位，面试强度高，使用录音转文字工具

> **verbatim 锚点 (T1/T3 抽取)**:
> - 小红书面的是AI与数据方向

---

### 32. 平安银行

- **tier**: 银行系资管
- **must_have in**: 自营FOF, 财富管理FOF (2 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: 金融
- **source 标签**: taxonomy_doc, xhs:财富管理FOF:1
- **notes**:
  - [自营FOF] 银行自营 FOF
  - [财富管理FOF] 财富线 + 自营双线

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 平安资产管理有限责任公司 | 行业研究员 | 1 | 保险资管 |

#### XHS 帖证据 (12 条)

**[固收+多资产]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a03466a000000000](https://www.xiaohongshu.com/discovery/item/6a03466a000000000702f4c4?xsec_token=YBHOt7zneE8YP4HgVHcNE3uPkUsDCRauMCju0BEuxouic%3D&xsec_source=app_share)

> 帖内提到的公司: yfd, 德邦, 上银, 中银理财, 中邮理财, 信银理财

> **内容快照**:
> 
> 固收赛道相比权益bar略低，但近年越来越卷。
> 
> 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向。
> 
> 实习经历垂直会有一定优势，多段转债量化经历有助于秋招。
> 
> 暑期实习面试中，公募、理财子、券商、私募等均有面试经历，部分挂掉。
> 
> 多数市场化机构在暑期确定名额后秋招不开放。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 固收赛道相比权益bar略低，但是近年越来越卷
> - 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向
> - 实习经历垂直会有一定优势，猜测秋招发面是因为有多段转债量化经历

**[公募基金中后台]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0b1435000000003](https://www.xiaohongshu.com/discovery/item/6a0b14350000000035033c92?xsec_token=YBjJDvW9ftzu9in_HYy8Pxxg20_Kg7r5OsrRXUwVlafdo%3D&xsec_source=app_share)

> 帖内提到的公司: 国联民生, 南方基金, 东吴证券, 景顺长城, 平安证券, 平安理财

> **内容快照**:
> 
> 用户已面试国联民生中台岗、南方基金群面、东吴证券债承、景顺长城中台岗，并完成平安证券、平安理财、民生银行、东方财富证券的测评。
> 
> 用户投递了多家金融机构的暑期实习，包括券商、基金、银行理财子等。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 已面试：1、国联民生中台岗 2、南方基金群面 3、东吴证券债承 4、景顺长城中台岗 已测评：1、平安证券、平安理财 2、民生银行 3、东方财富证券
> - 国联民生中台岗、南方基金群面、东吴证券债承、景顺长城中台岗、平安证券、平安理财、民生银行、东方财富证券

**[利率宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/65d82a21000000000](https://www.xiaohongshu.com/discovery/item/65d82a21000000000b01727e?xsec_token=YBERA2NT_0W6NUgMTa_0vN0YwyvwgVf9e05xmaQ_CvrGo%3D&xsec_source=app_share)

> 帖内提到的公司: 国利, 平安, 国际, BGC, 信唐, 上田

> **内容快照**:
> 
> 货币中介门槛相对其他金融机构友好，但内卷严重，学历层次增高。
> 
> 面试货币中介需要了解所报价品种的市场概况、基础设施、参与机构，以及岗位日常和所需能力。
> 
> 国利是货币中介中最强的，平安、国际也比较猛，BGC次之，信唐不容小觑，上田是后起之秀。
> 
> 货币中介主要报价品种包括利率、信用、货币、存单、借贷、利率互换等，地方债逐渐独立成台。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 现在内卷比较严重，货币中介小伙伴们的学历层次也逐渐增高，不乏海内外名校硕士。但门槛总体还是没有其他金融机构要求那么严格，社招和校招对专业和学历还算友好。
> - 了解清楚自己面试台子所报价品种的市场概况，基础设施，参与机构；了解对应岗位每天的日常；了解该岗位需要什么能力，自己有什么特质与之匹配。
> - 国利最强，平安、国际也比较猛，BGC次之，信唐也不容小觑，在某些品种的报价表现上毫不逊色。上田作为后起之秀，社招了很多以前同行的经纪人，报价水平也一样专业。

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/669c8650000000000](https://www.xiaohongshu.com/discovery/item/669c8650000000000a02755d?xsec_token=YByIede-U9SUzZKRbL5ECpeyVlBMGy40PZrIh0A64Tocg%3D&xsec_source=app_share)

> 帖内提到的公司: 国元证券, 平安证券, 民生证券

> **内容快照**:
> 
> 卖方首席的职业路径可以从双非院校起步，通过努力逐步晋升，二级研究提供凭借个人能力走出来的机会。
> 
> 民生证券海外首席易老师，从国元证券到平安证券再到民生证券，专注于传媒互联网、消费等方向。
> 
> 二级研究行业为小镇做题家提供凭借个人能力走出来的机会，晋升不只看关系。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 双非院校走出来的卖方首席，勤奋&实力
> - 2020年初离开国元进入平安，一直从事传媒互联网、消费等方向的研究...2023年7月进入民生证券
> - 二级研究至少还给你一个凭借个人能力走出来的机会，这也是吸引一代又一代小镇做题家奋不顾身扎进来的原因之一。

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a004d91000000003](https://www.xiaohongshu.com/discovery/item/6a004d910000000036000bfe?xsec_token=YBYM1cUi6i2AdR2d2EYp7gyzNSgGWMnMTf2wxGS2XvQqk%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 中金公司, 华泰证券, 中信建投证券, 国泰海通证券, 招商证券

> **内容快照**:
> 
> 投行招聘中，除了中金公司，大部分券商强调实习留用，面试越来越水，更看重实战能力。
> 
> 26年投行招聘仍是招聘大年，腰腿部券商提供更多机会，学历门槛下探。
> 
> 列举了15家开放投行暑期实习的券商和14家开放春季招聘的券商，其中4家同时开放。
> 
> 本科学历背景普通但实战能力突出的候选人，在26年拿到投行机会的可能性提升。
> 
> 投行面试越来越水，技术面试在绝大部分券商涉及不到。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 除了中金公司以外，其他大部分券商都强调“实习留用”...投行的面试越来越水了。
> - 26年仍会是投行的招聘大年...腰腿部券商投行给了大家更多的“选择权”...学历相对没那么优秀，26年有更多的加入投行的机会和可能性。
> - 至少包括15家：中信证券、中金公司、华泰证券...至少包括14家：招商证券、国联民生证券...同时开放暑期实习和春季招聘的投行，包括4家：招商证券、国联民生证券、东吴证券、西部证券。

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000](https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000702ace7?xsec_token=YB9MVh1sELWdJvRY7-4rURZo9qtVNwXXJJLAGIjlCzytE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 中金公司, 华泰证券, 中信建投证券, 申万宏源

> **内容快照**:
> 
> 中信证券多项业务指标连年夺魁，是券商中的'神'级公司。
> 
> 国泰海通由国开君安和海通证券合成，资本实力跃居行业榜首。
> 
> 中金公司是首家中外合资投行，投行业务标杆。
> 
> 华泰证券是金融科技+财富管理领域的标杆。
> 
> 中信建投证券降薪严重，与前三个相比掉队。
> 
> 2025年证券行业呈现'强者恒强'的马太效应，头部券商占据大部分市场份额。
> 
> 头部券商总部前台岗求职难度不输国有总行，建议根据学历背景和实习相关性合理选择。
> 
> 随着大A慢牛市场，证券公司实习机会增多，26届应把握机会。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 中信证券可以单独开一个'神'级，多项业务指标连年夺魁
> - 国泰海通由国开君安和海通证券合成而成的新龙头，资本实力跃居行业榜首
> - 中金公司，首家中外合资投行，投行业务标杆

_(+6 条更多帖未展示, 同 sub_cat)_

---

### 33. 招商银行

- **tier**: 银行系资管
- **must_have in**: 自营FOF, 财富管理FOF (2 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: 金融
- **source 标签**: taxonomy_doc, xhs:自营FOF:2, xhs:财富管理FOF:1
- **notes**:
  - [自营FOF] 零售之王自营
  - [财富管理FOF] 财富管理龙头

#### XHS 帖证据 (21 条)

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[信用研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/699b00c1000000000](https://www.xiaohongshu.com/discovery/item/699b00c1000000000e03f406?xsec_token=YByUaNWdGqni4CccoDmetp9jnkQ79jyEQvtPsYLCsbMVQ%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达基金, 招商银行

> **内容快照**:
> 
> 易方达基金资管投研部门内部竞争激烈，工作强度大，建议谨慎考虑。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 炸了！pa资管投研，竟是这种“卷王”局？内行人做二级固收研究的应该都知道哈哈，内部惨不忍睹，去的话谨慎之～

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69bbb886000000002](https://www.xiaohongshu.com/discovery/item/69bbb886000000002b00dc0f?xsec_token=YBY-rrGTG456s3Kutg82G2iAMfesSM55ZOeJkEKPkgzAA%3D&xsec_source=app_share)

> 帖内提到的公司: 三中一华, 广发证券, 招商证券, 国信证券

> **内容快照**:
> 
> 学生背景211本+中9硕，实习经历包括一段颈部券商股承做和两段TMT行研（新财富），未来可能路径为行研、投行、PE/VC。
> 
> 学生获得四个top15券商的实习offer：三中一华债、广发机械/通信（新财富）、招商TMT、国信债。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 🏠211本+中9硕，实习经历，一段颈部券商股承做，两段TMT行研（新财富）。未来的发展路径没有想好，可能是行研、投行、PE/VC。
> - 手上的实习offer（全是top15券商）1️⃣三中一华 债 2️⃣广 机械/通信（新财富）3️⃣招 TMT 4️⃣国x 债

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a01eb1c000000000](https://www.xiaohongshu.com/discovery/item/6a01eb1c00000000060338be?xsec_token=YB_i_kGzuCXcaFW9dZg1ZTISu9Q8tnbXtneZpnnB4vq6M%3D&xsec_source=app_share)

> 帖内提到的公司: 招商证券

> **内容快照**:
> 
> 招商证券2026实习生招聘已开启

> **verbatim 锚点 (T1/T3 抽取)**:
> - 招商证券2026实习生招聘已开启

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69205644000000001](https://www.xiaohongshu.com/discovery/item/69205644000000001f00b280?xsec_token=YB_DHH46EccpDnafKb5wDAjbvxYtYyKvfxi_ehR5s45OQ%3D&xsec_source=app_share)

> 帖内提到的公司: 招商证券

> **内容快照**:
> 
> 招商证券投行实习留用率不确定，HR说实习1-2个月出结果，但有人实习一年。
> 
> 投行实习要求全职（5天/周），但作者只能抽3天，且12月初要上课，时间冲突。

> **verbatim 锚点 (T1/T3 抽取)**:
> - hr说实习1-2月出结果但红薯上刷到有人实习一年
> - 全职实习是不是指五天/周关键我只能抽三天，出差我这也很难办十二月初得上课

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6981f15c000000002](https://www.xiaohongshu.com/discovery/item/6981f15c00000000220080c6?xsec_token=YB36fp58VMA4y3yTxPK9RvWAg0VsVvBz1EByjqK8CUfgY%3D&xsec_source=app_share)

> 帖内提到的公司: 招商证券

> **内容快照**:
> 
> 招商证券投行部实习岗位，涉及量化建模和固收领域，适合金融、经济、会计等商科背景学生。
> 
> 招商证券是中国领先的上市券商，拥有全牌照业务体系。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 招商证券·投行部实习｜2-3个月，开启你的金融职场高起点！
> - 招商证券——中国领先的上市券商，承载百年招商局的深厚底蕴。

_(+15 条更多帖未展示, 同 sub_cat)_

---

### 34. 天风证券

- **tier**: 中型券商研究所
- **must_have in**: 行业研究员·消费 (1 sub_cat)
- **非 must_have (备选) in**: 卖方研究员·TMT, 卖方研究员·消费医药周期, 卖方研究员·宏观策略 (3)
- **industry_focus**: TMT, 消费
- **source 标签**: xhs:卖方研究员·宏观策略:1, xhs:卖方研究员·消费医药周期:6, xhs:行业研究员·消费:3
- **notes**:
  - [行业研究员·消费] 消费/医药双覆盖
  - [卖方研究员·TMT] 中型卖方 TMT
  - [卖方研究员·消费医药周期] 中型消费组
  - [卖方研究员·宏观策略] 中型卖方宏观

#### XHS 帖证据 (12 条)

**[利率宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/695a6268000000001](https://www.xiaohongshu.com/discovery/item/695a6268000000001d0382b1?xsec_token=YBd3iF8SWE-vvJspWYIM6IuHuIRxeOnYa2EbGAT8SnR28%3D&xsec_source=app_share)

> 帖内提到的公司: 天风证券

> **内容快照**:
> 
> 天风证券固收组宏观利率实习岗位

> **verbatim 锚点 (T1/T3 抽取)**:
> - 天风证券固收组宏观利率实习

**[利率宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69e60c71000000001](https://www.xiaohongshu.com/discovery/item/69e60c71000000001a036863?xsec_token=YBgxfelF6pOvvQ3lvrOeuANLCOt7CLJSMTLB_Vd8Bcm4E%3D&xsec_source=app_share)

> 帖内提到的公司: 光大, 天风, 东财, 国金, 浙商, 东北

> **内容快照**:
> 
> 学生目标岗位为券商自营部门的偏债或宏观方向，关注校招画像、待遇和发展情况。
> 
> 学生提及的中型券商自营部门包括光大、天风、东财、国金、浙商、东北等。
> 
> 学生询问校招是否是好选择以及进入机会。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 目标偏债或者宏观的二级（了解到一些新增的集中在资产配置方向）
> - 包括不限于如光大，天风，东财，国金，浙商，东北等券商的自营部门
> - 校招是好的选择吗，有机会进吗？

**[卖方研究员·宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/687b719c000000001](https://www.xiaohongshu.com/discovery/item/687b719c000000001c032ee7?xsec_token=YBLNgyTOisyoCtcxpkArfGUhAr2MEYTPMZ0Xpi-4Fbo1Y%3D&xsec_source=app_share)

> 帖内提到的公司: 天风证券, 中银证券

> **内容快照**:
> 
> 天风证券研究所策略组和中银证券策略组都是卖方研究岗位，但中银证券提供实习证明和薪资，天风证券则没有。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 天风证券研究所策略组（🈚️实习证明）和中银证券（有实习证明和薪资）选哪个！

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68f4c8d8000000000](https://www.xiaohongshu.com/discovery/item/68f4c8d800000000040017e5?xsec_token=YBmXcSVJ86pPYesi1tI_rsuyQ2Bq0taMjeBSnk7v1_S-c%3D&xsec_source=app_share)

> 帖内提到的公司: 天风证券

> **内容快照**:
> 
> 天风证券医药组招聘实习生，参与政策研究、行业分析，表现优异者有留用机会。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 天风证券医药组招聘实习生，参与政策研究、行业分析，表现优异者有留用机会。

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d9c047000000001](https://www.xiaohongshu.com/discovery/item/69d9c047000000001a027a0c?xsec_token=YB7Q31IQ164rsrhwt_j0SxEzhu5jSAgwYPlkP5l1lRvWE%3D&xsec_source=app_share)

> 帖内提到的公司: 天风证券

> **内容快照**:
> 
> 天风证券化工行研团队人员可能有变动

> **verbatim 锚点 (T1/T3 抽取)**:
> - 这是半年多以前的数据了，不知道人员有没有变动？

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d38b09000000001](https://www.xiaohongshu.com/discovery/item/69d38b09000000001a02d342?xsec_token=YBdwqzxPKVOip082MIT5rOsRq4HGUd7QEADHwXlgWTo3A%3D&xsec_source=app_share)

> 帖内提到的公司: 天风证券

> **内容快照**:
> 
> 天风证券研究所招聘有色实习生，走正式人事流程，可线上或线下，长期表现优异可参与留用答辩。

> **verbatim 锚点 (T1/T3 抽取)**:
> - base 上海 天风证券研究所 有色实习生

_(+6 条更多帖未展示, 同 sub_cat)_

---

### 35. AI 应用初创 (头部创业)

- **tier**: AI 初创
- **must_have in**: Agent工程师 (1 sub_cat)
- **非 must_have (备选) in**: AI PM (1)
- **industry_focus**: AI 应用层
- **source 标签**: demo_v1, taxonomy_doc
- **notes**:
  - [Agent工程师] Agent 创业团队聚集地
  - [AI PM] 0-1 PM 经验机会多

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 36. 宽德投资

- **tier**: 中型量化私募
- **must_have in**: 量化开发QD (1 sub_cat)
- **非 must_have (备选) in**: 量化因子工程师 (1)
- **industry_focus**: —
- **source 标签**: taxonomy_doc, xhs:量化研究员·高频:2
- **notes**:
  - [量化开发QD] C++/Linux 系统强
  - [量化因子工程师] 因子+QD 双线

#### XHS 帖证据 (8 条)

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69f55dc6000000003](https://www.xiaohongshu.com/discovery/item/69f55dc60000000036030768?xsec_token=YBO_g5dxVwlm0aWR4QVRvbiiuom_DAIHrelvWhT7f_Ats%3D&xsec_source=app_share)

> 帖内提到的公司: 明汯投资, 平方和, 顽岩, 黑翼, 衍复, 龙旗

> **内容快照**:
> 
> 2026年4月百亿量化私募备案数据：明汯投资断层领先，4月备案42只，前4个月合计131只，已占去年全年84%。平方和、顽岩、黑翼、衍复等备案量也较高，而宽德、世纪前沿、九坤节奏放缓。新晋百亿私募包括远澜、子午、量道、凯读、鲁民投、知行通达。
> 
> 明汯投资备案节奏激进，渠道承接能力强，对发行窗口积极。
> 
> 宽德、世纪前沿、九坤备案节奏明显放缓，可能更重视容量管理。
> 
> 量化私募规模扩大后，超额收益能否持续是关键问题。
> 
> 新百亿私募出现，量化行业并非头部固化，中腰部仍有上升机会。
> 
> 百亿只是入场券，规模扩大后超额、波动、持有人体验才是真正考验。
> 
> 备案数量可作为观察管理人战略动作的窗口，但不能直接作为选基依据。
> 
> 量化私募竞争最终比拼的是规模变大后仍能做出超额收益。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 2026年4月，百亿量化私募备案数据更新。从YTD数据看，明汯投资仍然断层领先。1月至4月，明汯合计备案131只。其中4月单月备案42只。对比2025年全年156只，明汯前4个月已经完成去年全年约84%的备案量。
> - 这个节奏非常激进。4月的数据说明，它不是短期冲刺，而是在持续加速。背后至少说明两点：渠道承接能力强，管理人对当前发行窗口较为积极。
> - 相比之下，宽德4月备案7只，世纪前沿9只，九坤6只，节奏明显放缓。这不一定说明谁更好，而是说明不同管理人的阶段选择不同。有些机构选择趁市场回暖快速扩张，有些机构更重视容量管理。

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69a0230c000000001](https://www.xiaohongshu.com/discovery/item/69a0230c0000000015032f97?xsec_token=YB2-5hof2I4lVqzOjbMiX6hoxj_8LrGZHtD57Jbms0X6k%3D&xsec_source=app_share)

> 帖内提到的公司: 宽德, 磐松, 衍复, 九坤, 平方和, 顽岩

> **内容快照**:
> 
> 磐松工作环境三年前听说很压抑，现在情况未知。
> 
> 鸣石QR岗位要求博士或计算方向，普通背景难以达到。
> 
> 顽岩QR岗位简历秒拒，竞争激烈。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 磐松现在工作环境怎么样，大概三年前听朋友说很压抑，不知道现在情况如何……
> - 鸣石也有开放的岗位，但JD写明了需要博士或者偏计算的方向，达不到要求。
> - 顽岩也有QR，不过被简历秒拒了。

**[财富管理FOF]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69736654000000000](https://www.xiaohongshu.com/discovery/item/69736654000000000a03e9cf?xsec_token=YBEzMvYRc_dlXgG3WLgWfvLLtIq2W8dxPyZhiShbMapEQ%3D&xsec_source=app_share)

> 帖内提到的公司: 宽德投资, 复胜资产, 平安CTA

> **内容快照**:
> 
> 用户赎回宽德A500指增，原因是超额收益差，仅覆盖业绩计提，认为1000指增fof更优。
> 
> 宽德投资的A500指增产品超额表现不佳，用户考虑赎回。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 超额做的太拉垮了，做的超额只能覆盖他们的业绩计提。还是之前的1000指增fof香
> - 要把去年年初投的宽德A500指增赎回了，原因是超额做的太拉垮了

**[量化研究员·中频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6693f635000000020](https://www.xiaohongshu.com/discovery/item/6693f635000000020302f1e9?xsec_token=YB3Cr21n9BvyMDlGOPs0CzXZPFZLj9QODs7UwIRknhhiI%3D&xsec_source=app_share)

> 帖内提到的公司: 宽德, 九坤, IDEA, 天王星

> **内容快照**:
> 
> 宽德面试中，面试官因学生未听完分享会而情绪变化，导致面试表现不佳。
> 
> 九坤面试中，学生因思维定势未准备coding环节，导致写题表现差。
> 
> IDEA公司无面试直接发拒信，学生感到莫名其妙。
> 
> 天王星面试后未主动通知结果，学生打电话询问才得知未通过，猜测与高考排名有关。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 二面面试官上来问我：之前的分享会听完感觉咋样？我老老实实回答说有事情没听完。说完隐约感觉到面试官情绪稍微降了那么一点点，他说：没事，那我们问几个问题吧。得，把我问的一塌糊涂，最后直接红温。
> - 因为之前面试都没有出现过coding环节，我当时思维定势，天真地认为量化面试环节不会写题，结果听到这句话我脑袋短路，直接来了一句：“啊，还要写题吗？”不出意外，题写的一塌糊涂。
> - 我至今不知道啥时候投的他们家，boss直聘上完全没搜到投递记录，直到某天上午上班，打开邮件，发现了他们家发来的拒信，莫名其妙地被拒，元气满满的上午直接被终结。

**[量化研究员·高频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/694dfad5000000002](https://www.xiaohongshu.com/discovery/item/694dfad50000000022032080?xsec_token=YBcHIqfNaLBVDhXCU8c_xcywRuE30yKwo_JDQ4QwekE5I%3D&xsec_source=app_share)

> 帖内提到的公司: 明汯投资, 幻方量化, 衍复投资, 九坤投资, 宽德投资, 世纪前沿

> **内容快照**:
> 
> 2025年量化策略业绩全面回暖，头部机构规模洗牌，明汯、幻方、衍复、九坤等有望重返千亿俱乐部。
> 
> 明汯投资今年备案最多，多个渠道积极推产品，可能很快突破千亿。
> 
> 幻方量化2021年曾主动控盘建议客户赎回，之后靠业绩驱动规模自然回升。
> 
> 衍复投资今年年中暂停新申购，多个策略年内第二次分红，主动控制规模扩张节奏。
> 
> 九坤投资产品发行细水长流，规模稳步爬升，属于长跑型选手。
> 
> 宽德投资上半年募资凶猛，下半年明显刹车，预计短期内规模变化不大。
> 
> 世纪前沿、诚奇、黑翼三家今年发力明显，备案和募资都在前列。
> 
> 2025年量化圈关键词是“卷”，靠规模喊口号的草莽时代结束，现在比的是策略迭代速度和算力竞赛。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 2025年余额仅剩最后3个交易日！复盘这一年，绝对是量化策略的当打之年。业绩全面回暖，头部机构赚得盆满钵满，百亿量化阵营也在加速扩容。
> - 明汯：今年的备案王！多个渠道都在积极推其产品，势头非常猛，可能很快再次捅破1000亿这层窗户纸。
> - 幻方：2021年曾主动控盘甚至建议客户赎回，随后依靠业绩驱动规模自然回升，实力不允许低调。

_(+2 条更多帖未展示, 同 sub_cat)_

---

### 37. 广发证券

- **tier**: 中型券商研究所
- **must_have in**: 卖方研究员·消费医药周期 (1 sub_cat)
- **非 must_have (备选) in**: 结构化产品衍生品 (1)
- **industry_focus**: 医药, 消费, 金融
- **source 标签**: common_knowledge:头部券商衍生品, taxonomy_doc, xhs:卖方研究员·消费医药周期:11
- **notes**:
  - [卖方研究员·消费医药周期] 消费医药行业首席多
  - [结构化产品衍生品] 按行业共识

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 广发基金管理有限公司 | 行业研究员 | 1 | 公募基金 |

#### XHS 帖证据 (18 条)

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[信用研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69ca9946000000001](https://www.xiaohongshu.com/discovery/item/69ca9946000000001b00076b?xsec_token=YBLMCeCSnGE4YGO-OsDjX8sNGlfn7z3BDpFmaRlwFA3Wo%3D&xsec_source=app_share)

> 帖内提到的公司: 广发基金

> **内容快照**:
> 
> 广发基金固收研究员面试题目汇总，涵盖固收研究兴趣、宏观利率分析、信用风险分析、可转债、久期等核心问题。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 广发基金｜固收研究员面经汇总🔥

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69bbb886000000002](https://www.xiaohongshu.com/discovery/item/69bbb886000000002b00dc0f?xsec_token=YBY-rrGTG456s3Kutg82G2iAMfesSM55ZOeJkEKPkgzAA%3D&xsec_source=app_share)

> 帖内提到的公司: 三中一华, 广发证券, 招商证券, 国信证券

> **内容快照**:
> 
> 学生背景211本+中9硕，实习经历包括一段颈部券商股承做和两段TMT行研（新财富），未来可能路径为行研、投行、PE/VC。
> 
> 学生获得四个top15券商的实习offer：三中一华债、广发机械/通信（新财富）、招商TMT、国信债。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 🏠211本+中9硕，实习经历，一段颈部券商股承做，两段TMT行研（新财富）。未来的发展路径没有想好，可能是行研、投行、PE/VC。
> - 手上的实习offer（全是top15券商）1️⃣三中一华 债 2️⃣广 机械/通信（新财富）3️⃣招 TMT 4️⃣国x 债

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000](https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000702ace7?xsec_token=YB9MVh1sELWdJvRY7-4rURZo9qtVNwXXJJLAGIjlCzytE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 中金公司, 华泰证券, 中信建投证券, 申万宏源

> **内容快照**:
> 
> 中信证券多项业务指标连年夺魁，是券商中的'神'级公司。
> 
> 国泰海通由国开君安和海通证券合成，资本实力跃居行业榜首。
> 
> 中金公司是首家中外合资投行，投行业务标杆。
> 
> 华泰证券是金融科技+财富管理领域的标杆。
> 
> 中信建投证券降薪严重，与前三个相比掉队。
> 
> 2025年证券行业呈现'强者恒强'的马太效应，头部券商占据大部分市场份额。
> 
> 头部券商总部前台岗求职难度不输国有总行，建议根据学历背景和实习相关性合理选择。
> 
> 随着大A慢牛市场，证券公司实习机会增多，26届应把握机会。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 中信证券可以单独开一个'神'级，多项业务指标连年夺魁
> - 国泰海通由国开君安和海通证券合成而成的新龙头，资本实力跃居行业榜首
> - 中金公司，首家中外合资投行，投行业务标杆

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a00852d000000000](https://www.xiaohongshu.com/discovery/item/6a00852d0000000008002bb5?xsec_token=YBYM1cUi6i2AdR2d2EYp7gy0jrM93HeTyqyT4_9HsqWHE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 华泰证券, 中金证券, 中信建投, 招商证券

> **内容快照**:
> 
> 券商分为五个梯队，第一梯队包括中信证券、国泰海通、华泰证券、中金证券、中信建投等，平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> 
> 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> 
> 第一梯队偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历更加分。
> 
> 第三梯队门槛相对灵活，海外院校、转专业同学都有机会，关键是简历里要体现对金融行业的理解。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> - 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> - 通常更偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历会更加分。

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69c4038e000000002](https://www.xiaohongshu.com/discovery/item/69c4038e00000000230125c5?xsec_token=YB0UsFJCDs7aM6X-Lq9bShYk2aYkjgRrrPBlPYUFvugTk%3D&xsec_source=app_share)

> 帖内提到的公司: 广发证券

> **内容快照**:
> 
> 广发证券行业研究员面试问题汇总，包括如何应对不熟悉的任务、优点、人际关系、行业分析报告、政策变化分析、数据质量、核心工作、定性定量分析、报告组织等。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 广发证券｜行业研究员面经汇总🔥

_(+12 条更多帖未展示, 同 sub_cat)_

---

### 38. Jane Street

- **tier**: 衍生品做市商
- **must_have in**: 量化研究员·高频 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: —
- **source 标签**: common_knowledge:头部做市商, taxonomy_doc
- **notes**:
  - [量化研究员·高频] 按行业共识,顶尖做市商

#### XHS 帖证据 (5 条)

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/696e0157000000000](https://www.xiaohongshu.com/discovery/item/696e0157000000000b00aa49?xsec_token=YBLzx7ZossRnL_aAxZjlYx2SzHExIvcl7Ifjrej0KQEMY%3D&xsec_source=app_share)

> 帖内提到的公司: Jane Street, HRT, Optiver, Virtu, DRW, Tower Research

> **内容快照**:
> 
> Quant公司可按交易频率和团队结构分为四类：高频协作（如Jane Street, HRT, Optiver）、高频个体化（如Virtu, DRW, Tower Research）、低频协作（如RenTec, QRT）、低频个体化（如Millennium, Citadel, BAM）。
> 
> 不同分类对应不同技能树：高频公司注重编程、算法设计、系统架构和低延迟优化，C++和硬件知识关键；低频公司更看重统计建模、机器学习和基本面分析，Python和R常用。
> 
> 团队文化影响技能：协作型需要善于沟通和团队合作；个体型要求高度自驱和独立解决问题能力。
> 
> Quant公司分类包括高频做市商、自营交易公司、系统化对冲基金、多策略对冲基金等。
> 
> 学员拿到Brevan Howard、Optiver的Quant Trading Offer，以及JPM、Citi、高盛的Quant岗。

> **verbatim 锚点 (T1/T3 抽取)**:
> - Jane Street、HRT、Optiver属于高频协作类...Virtu、DRW、Tower Research则是高频但更个体化...RenTec、QRT这类是协作式系统化投资...Millennium、Citadel的pod结构或BAM这类，是低频且高度siloed
> - 高频公司，技能重点在编程、算法设计、系统架构和低延迟优化，C++和硬件知识往往是关键。低频公司则更看重统计建模、机器学习和基本面分析能力，Python和R用得多
> - 协作型需要你善于沟通和团队合作...个体型则要求高度自驱和独立解决问题能力

**[量化开发QD]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0d8637000000003](https://www.xiaohongshu.com/discovery/item/6a0d863700000000360025d1?xsec_token=YBm4Y5lD0UeO4fv4xPCt09Z1TPG5yS2AJULzN6ntDpeJY%3D&xsec_source=app_share)

> 帖内提到的公司: 顶级外资, 幻方量化, Jane Street, HRT

> **内容快照**:
> 
> 顶级外资急招junior C++开发，base香港，年薪200万，面向26年应届生或3年以内经验者。
> 
> 帖子提及幻方量化、Jane Street、HRT等量化公司，暗示这些公司正在招聘或有关注度。

> **verbatim 锚点 (T1/T3 抽取)**:
> - junior C++速来 26年应届C++ 顶级外资急招 200w base hk 3年以内的都可以聊
> - 幻方量化 janestreet面经 HRT面试

**[量化研究员·中频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69ef06c9000000001](https://www.xiaohongshu.com/discovery/item/69ef06c9000000001f00683d?xsec_token=YBBFKhGPbgnOn2OGWLk_gXAX5sUP_42Hkr932PR2n-43I%3D&xsec_source=app_share)

> 帖内提到的公司: 洛书投资, Deutsche Börse Group, BlackRock, Wolverine Trading, MSCIInc., Man Group

> **内容快照**:
> 
> 列举了2026年大量量化相关的校招和实习机会，包括国内外多家知名机构。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 洛书投资2026 Graduate program...AlphaGrep 2026暑期实习

**[量化研究员·高频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a15a138000000003](https://www.xiaohongshu.com/discovery/item/6a15a138000000003501dd25?xsec_token=YBJXceSEhkLQc7puTGKMxN_p_R9jpYHzgNTvXgnWHFQ5c%3D&xsec_source=app_share)

> 帖内提到的公司: Citadel, Jane Street, Two Sigma, Optiver, IMC, SIG

> **内容快照**:
> 
> 量化行业机构梯队分为顶级买方（Citadel、Jane Street、Two Sigma）、一线做市商（Optiver、IMC等）、知名对冲基金（Balyasny、Bridgewater等）、成长型量化机构（DRW、Schonfeld等）、卖方&资管（高盛、BlackRock等）和加密量化（Jump Crypto等）。
> 
> 初级岗位薪资参考：顶级买方entry级可达$300k+，不同机构薪资差异大。
> 
> 不同梯队机构考察重点不同：顶级买方和做市商更看重算法题、数学推导和工程实现；资管岗更偏向因子建模和业务理解。
> 
> 低年级可以参加IMC、Optiver的交易赛积累项目经历。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 买方（God Tier）以 Citadel、Jane Street、Two Sigma 为代表...一线做市商包括 Optiver、IMC、SIG、HRT、Jump Trading 等...知名对冲基金比如 Balyasny、Bridgewater、D.E. Shaw 等...成长型量化机构以 DRW、Schonfeld、Tower Research 为代表...卖方 & 资管量化岗投行（高盛、摩根士丹利、小摩等）和资管巨头（BlackRock、Vanguard、State Street 等）...加密量化赛道还有 Jump Crypto、Wintermute、GSR 等
> - Citadel 的 entry 级岗位可达 $300k+
> - 顶级买方和做市商更看重算法题、数学推导和工程实现，资管岗则更偏向因子建模和业务理解。

**[量化研究员·高频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6998178d000000001](https://www.xiaohongshu.com/discovery/item/6998178d000000001b01c657?xsec_token=YBnXGurgnhzx1ZjoGk3kx0DTtzMdldvpTmQNedODjmG5c%3D&xsec_source=app_share)

> 帖内提到的公司: Jane Street, Optiver, HRT, Citadel

> **内容快照**:
> 
> 面试官更想听的是你能不能抓到Alpha、懂不懂市场信号，而不是死磕数学题。
> 
> Quant/HFT岗位需要实操逻辑，包括市场微结构、流动性、价格动力学等。
> 
> Jane Street、Optiver、HRT、Citadel是顶级量化公司，面试准备可参考相关书籍。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 面试官更想听的是：你能不能抓到Alpha？你懂不懂市场信号？
> - 从Math转Trading，最缺的其实是那一套“实操逻辑”
> - 如果你正在备战Jane Street、Optiver或者HRT的面试，甚至只是想参加Citadel的Discover Day

---

### 39. Millennium

- **tier**: 外资行
- **must_have in**: 买方 Quant (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: —
- **source 标签**: common_knowledge:头部对冲基金
- **notes**:
  - [买方 Quant] 按行业共识,多策略对冲基金

#### XHS 帖证据 (3 条)

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/696e0157000000000](https://www.xiaohongshu.com/discovery/item/696e0157000000000b00aa49?xsec_token=YBLzx7ZossRnL_aAxZjlYx2SzHExIvcl7Ifjrej0KQEMY%3D&xsec_source=app_share)

> 帖内提到的公司: Jane Street, HRT, Optiver, Virtu, DRW, Tower Research

> **内容快照**:
> 
> Quant公司可按交易频率和团队结构分为四类：高频协作（如Jane Street, HRT, Optiver）、高频个体化（如Virtu, DRW, Tower Research）、低频协作（如RenTec, QRT）、低频个体化（如Millennium, Citadel, BAM）。
> 
> 不同分类对应不同技能树：高频公司注重编程、算法设计、系统架构和低延迟优化，C++和硬件知识关键；低频公司更看重统计建模、机器学习和基本面分析，Python和R常用。
> 
> 团队文化影响技能：协作型需要善于沟通和团队合作；个体型要求高度自驱和独立解决问题能力。
> 
> Quant公司分类包括高频做市商、自营交易公司、系统化对冲基金、多策略对冲基金等。
> 
> 学员拿到Brevan Howard、Optiver的Quant Trading Offer，以及JPM、Citi、高盛的Quant岗。

> **verbatim 锚点 (T1/T3 抽取)**:
> - Jane Street、HRT、Optiver属于高频协作类...Virtu、DRW、Tower Research则是高频但更个体化...RenTec、QRT这类是协作式系统化投资...Millennium、Citadel的pod结构或BAM这类，是低频且高度siloed
> - 高频公司，技能重点在编程、算法设计、系统架构和低延迟优化，C++和硬件知识往往是关键。低频公司则更看重统计建模、机器学习和基本面分析能力，Python和R用得多
> - 协作型需要你善于沟通和团队合作...个体型则要求高度自驱和独立解决问题能力

**[行业研究员·TMT-医药-周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69f4b12d000000001](https://www.xiaohongshu.com/discovery/item/69f4b12d000000001e00e3ff?xsec_token=YBmSakPnFEHN3Znl_nYcnGtSPqtLgDNxAwtXMcedWxamE%3D&xsec_source=app_share)

> 帖内提到的公司: Point72, Millennium, Citadel

> **内容快照**:
> 
> 二级行研研究员开始更多研究互联网产品，以更好理解价值创造源头。
> 
> PM和买方研究员转向研究互联网产品。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 研究员不再把精力完全all in传统的二级权益，而是开始更多地转身去研究和拥抱互联网产品。
> - 不少PM和买方研究员不再把精力完全all in传统的二级权益，而是开始更多地转身去研究和拥抱互联网产品。

**[行业研究员·TMT-医药-周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/696b5eb6000000021](https://www.xiaohongshu.com/discovery/item/696b5eb6000000021a0242d5?xsec_token=YBFVdwr1N5lDt73WdLpOM_jSvqAS4T6GFB9bmeARGwc2c%3D&xsec_source=app_share)

> 帖内提到的公司: Point72, Millennium, Citadel, 宁德时代, 台积电

> **内容快照**:
> 
> 对冲基金买方研究员岗位需要构建系统化的基本面研究框架，而非盲目追热点。
> 
> 面试中展示对具体公司（如宁德时代）的深入分析能力，包括上游原材料依赖和下游需求弹性。
> 
> EV行业当前市场焦点在电池供应链，半导体周期分析需考虑产能利用率和地缘风险。
> 
> Point72、Millennium、Citadel是知名的对冲基金，招聘买方研究员。
> 
> 简历中应突出系统化基本面研究能力和对具体行业的深入理解。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 关键在于构建系统化的基本面研究框架，而非盲目追热点。
> - 深入拆解其上游原材料依赖和下游需求弹性。
> - 现在市场焦点在电池供应链上，像宁德时代这样的公司...分析台积电时，要从产能利用率到地缘风险的逻辑链。

---

### 40. Morgan Stanley

- **tier**: 外资行
- **must_have in**: 投行 IBD (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: 金融
- **source 标签**: common_knowledge:头部外资投行, saif:2025
- **notes**:
  - [投行 IBD] SAIF 2025 命中

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2025 | Morgan Stanley | 行业研究员 | 1 | 私募 |

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 41. Optiver

- **tier**: 衍生品做市商
- **must_have in**: 量化研究员·高频 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: —
- **source 标签**: taxonomy_doc, xhs:量化研究员·高频:15
- **notes**:
  - [量化研究员·高频] XHS mention 第一,做市商

#### XHS 帖证据 (18 条)

**[买方 Quant]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/695940c8000000001](https://www.xiaohongshu.com/discovery/item/695940c8000000001e03a19c?xsec_token=YBrJ_goExM-LGFpD_KXswc_GrNMq5jKropLNK56upboAU%3D&xsec_source=app_share)

> 帖内提到的公司: 高盛, 摩根士丹利, 中金, 中信里昂, 幻方, 灵均

> **内容快照**:
> 
> 大湾区量化岗位分为卖方Quant（投行）和买方Quant（基金/私募），卖方Quant集中在香港，买方Quant在深圳更活跃。
> 
> 香港的卖方Quant主要集中在国际投行（高盛、摩根士丹利等）和中资投行国际子公司（中金、中信里昂），深圳的卖方机会在国内券商的金融工程/量化自营部门。
> 
> 深圳的买方Quant核心是顶尖量化私募（幻方、灵均等），香港的买方Quant包括全球顶级对冲基金和自营交易公司（Citadel, Two Sigma, Optiver等）。
> 
> 深圳的量化岗位面试必考对国内金融数据源（Wind, Tushare, JoinQuant）和A股交易规则的熟悉度。
> 
> 香港的量化岗位面试对期权定价、随机微积分等理论要求更深。
> 
> 深圳偏好国内顶尖理工院校（清北复交、浙大、中科大等）的硕士/博士，海外名校需对国内市场有理解；香港偏好全球顶级名校（美英顶尖高校、新加坡两所、港三所），专业排名比学校综合排名更重要。
> 
> 纯金融背景竞争力弱，数学、物理、计算机、电子工程等硬核专业是绝对主流。
> 
> 大湾区量化岗位技能要求：Python、SQL、Linux是基础；深圳需精通C++，香港需英语工作能力和kdb+/q等工具。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 在大湾区，两者的重心和机会有显著差异：1. 卖方Quant（以投行为主）：香港是绝对中心...2. 买方Quant（以基金/私募为主）：深圳是核心战场...
> - 国际投行（高盛、摩根士丹利等）及中资投行的国际子公司（中金、中信里昂等）的量化团队主要聚集于香港。
> - 深圳是核心战场：聚集了全国最顶尖、最活跃的量化私募（幻方、灵均等）...香港是国际桥头堡：云集了全球顶级对冲基金和自营交易公司（Citadel, Two Sigma, Optiver等）

**[量化研究员·高频]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/68af99f5000000001](https://www.xiaohongshu.com/discovery/item/68af99f5000000001d0394d1?xsec_token=YBMDFvAjSpbmV4GsOnphQWMFHXTSkeRFuR29faZgPTTsU%3D&xsec_source=app_share)

> 帖内提到的公司: Optiver, Citadel Securities

> **内容快照**:
> 
> Optiver qr第一轮面试包括三个场景（硬币、扑克牌、骰子）的betting game，面试官会追问问题，风险偏好低可能影响结果。
> 
> Cit Sec qt第一轮面试包括简历问题和两个case：一个是抽牌比大小并计算fair price，另一个是三个城市人口的market making游戏。

> **verbatim 锚点 (T1/T3 抽取)**:
> - Optiver qr的第一轮和qt一样，还是那个三个场景（硬币 扑克牌 骰子）的betting game，这次面试官是个从nsfz毕业的老中，整体流程还是和网上看到差不多，先简单问问简历，然后就是玩游戏。但我不知道为什么，这次被面试官评价我的风险偏好比较低
> - Cit Sec第一轮面试官是个hypsm毕业的亚女，总体来说人还是挺好的（毕竟从结果来看没挂我），但是不知道为什么本来预计45min的面试，硬生生面了70min啊。一开始她关于我简历上她感兴趣的部分问了几个问题（没有bq），然后就是两个case，一个是两个人玩抽牌（数字）的游戏比大小，然后我可以（may）选择重新抽一次，有三个不同的情形（关于对面的数）然后分别计算fair price。另一个是对于三个城市人口的market making，分别给出spread为10% 20% 30%（自己决定分别给哪个城市）的bid and offer，然后她会分别选择buy or sell，然后我根据结果再次重新给出那六个价格，以此类推玩了几轮，期间也有一些追问

**[量化研究员·高频]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6880a9d5000000001](https://www.xiaohongshu.com/discovery/item/6880a9d50000000010011ba0?xsec_token=YBd9faHjVDkkQSHFf23cH7LLya_pA4wf0Drwhyk37lwAc%3D&xsec_source=app_share)

> 帖内提到的公司: Optiver, DRW, SIG, Akuna Capital

> **内容快照**:
> 
> 面试中考察了期货次高频策略的基本概念，包括tick size、换月逻辑、期货贴水、CTAs以及基差波动对alpha decay的影响。
> 
> Quant Trading Intern岗位需要熟悉期货次高频策略，包括midprice做市、库存控制、延迟执行下的报价优化。
> 
> Optiver、DRW、SIG、Akuna等HFT/Quant firm对期货次高频策略有较高要求。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 不知道tick size、换月逻辑、期货贴水、CTAs这些基本概念
> - Quant Trading Intern
> - Optiver / DRW / SIG / Akuna 这一类 firm

**[量化研究员·高频]** (relevance=0.85) — [https://www.xiaohongshu.com/discovery/item/69b21ae9000000001](https://www.xiaohongshu.com/discovery/item/69b21ae9000000001503b124?xsec_token=YBDzyndl-7rtYoDrF75nRMUowhtWMtTfFZ9P8gXLTeufI%3D&xsec_source=app_share)

> 帖内提到的公司: Optiver

> **内容快照**:
> 
> Optiver QT实习面试注重交易直觉、市场做市逻辑、认知能力和反应速度，而非单纯数学能力。
> 
> Zap-n-Spark测试考察认知能力和反应速度，无法靠背题通过。
> 
> 面试中市场做空逻辑环节要求快速决策，即使算错也要根据新信息调整模型。
> 
> 准备时应多刷Brainteasers并思考博弈论在实际交易中的应用。
> 
> 对高频交易的热情和不满足的精神是通关核心。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 其实人家更想要的是那种有Trading Instinct的人。说白了你得表现得像个真正的Trader，对PnL有执念但又能冷静控制Risk。
> - 首先就是那个著名的Zap-n-Spark测试，那个真的不是靠背题能过的，纯看你的Cognitive Ability和Reaction能力。
> - 面试官会给你一个很Random的场景，让你去估一个数并给出Bid和Ask的Range。这种时候千万别犹豫太久，你要表现得非常Decisive。其实如果你算错了也没关系，关键是你能不能在新的Information进来后快速Adjust你的Model。

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/696e0157000000000](https://www.xiaohongshu.com/discovery/item/696e0157000000000b00aa49?xsec_token=YBLzx7ZossRnL_aAxZjlYx2SzHExIvcl7Ifjrej0KQEMY%3D&xsec_source=app_share)

> 帖内提到的公司: Jane Street, HRT, Optiver, Virtu, DRW, Tower Research

> **内容快照**:
> 
> Quant公司可按交易频率和团队结构分为四类：高频协作（如Jane Street, HRT, Optiver）、高频个体化（如Virtu, DRW, Tower Research）、低频协作（如RenTec, QRT）、低频个体化（如Millennium, Citadel, BAM）。
> 
> 不同分类对应不同技能树：高频公司注重编程、算法设计、系统架构和低延迟优化，C++和硬件知识关键；低频公司更看重统计建模、机器学习和基本面分析，Python和R常用。
> 
> 团队文化影响技能：协作型需要善于沟通和团队合作；个体型要求高度自驱和独立解决问题能力。
> 
> Quant公司分类包括高频做市商、自营交易公司、系统化对冲基金、多策略对冲基金等。
> 
> 学员拿到Brevan Howard、Optiver的Quant Trading Offer，以及JPM、Citi、高盛的Quant岗。

> **verbatim 锚点 (T1/T3 抽取)**:
> - Jane Street、HRT、Optiver属于高频协作类...Virtu、DRW、Tower Research则是高频但更个体化...RenTec、QRT这类是协作式系统化投资...Millennium、Citadel的pod结构或BAM这类，是低频且高度siloed
> - 高频公司，技能重点在编程、算法设计、系统架构和低延迟优化，C++和硬件知识往往是关键。低频公司则更看重统计建模、机器学习和基本面分析能力，Python和R用得多
> - 协作型需要你善于沟通和团队合作...个体型则要求高度自驱和独立解决问题能力

**[量化研究员·高频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6866cc88000000000](https://www.xiaohongshu.com/discovery/item/6866cc88000000000b02fd89?xsec_token=YB7QZEOEpAkjIJBGOT7jCTKs5KiTePXhr_Ckm0Uts_8wQ%3D&xsec_source=app_share)

> 帖内提到的公司: Optiver

> **内容快照**:
> 
> Optiver是一家总部位于荷兰阿姆斯特丹的高频交易公司和做市商，拥有37年历史，全球超过1600名员工。
> 
> 2026 Optiver量化实习项目，要求2026年冬季或2028年春季毕业的STEM专业留学生，具备熟练使用编程语言的能力，无需相关经验。

> **verbatim 锚点 (T1/T3 抽取)**:
> - Optiver是一家总部位于荷兰阿姆斯特丹的高频交易公司和做市商，拥有着37年的历史，是全球建立时间最长的做市商之一，在世界各地有超过1600名员工。
> - 2026年冬季或2028年春季毕业的STEM专业留学生，要具备熟练使用编程语言的能力，无需相关经验！

_(+12 条更多帖未展示, 同 sub_cat)_

---

### 42. Point72

- **tier**: 外资行
- **must_have in**: 买方 Quant (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: —
- **source 标签**: saif:2025, taxonomy_doc
- **notes**:
  - [买方 Quant] 顶尖对冲基金

#### XHS 帖证据 (3 条)

**[行业研究员·TMT-医药-周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69bebcfd000000001](https://www.xiaohongshu.com/discovery/item/69bebcfd000000001a033461?xsec_token=YB9Iqi9eyKW3iHkWzWOke-qr5Z3tZK0qSa1zem4AN7Zxg%3D&xsec_source=app_share)

> 帖内提到的公司: Point72, Citadel

> **内容快照**:
> 
> 二级买方行研助手使用AI Agent提效，核心工作包括报告解析、宏观交叉验证、历史可比事件分析。
> 
> 半导体行业更新报告处理中，AI Agent可自动提取供应链变化、财务指标和趋势描述。
> 
> 面试中可能被问及如何利用AI工具提升行研效率，以及AI与人类判断的边界。

> **verbatim 锚点 (T1/T3 抽取)**:
> - Cursor让二级买方行研助手提效落地
> - 处理半导体行业更新报告时，我直接把AI Agent当成了核心行研助手
> - AI不取代人的最终判断——它擅长模式匹配和数据梳理，但宏观语境和突发事件解读仍需研究员经验把关

**[行业研究员·TMT-医药-周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69f4b12d000000001](https://www.xiaohongshu.com/discovery/item/69f4b12d000000001e00e3ff?xsec_token=YBmSakPnFEHN3Znl_nYcnGtSPqtLgDNxAwtXMcedWxamE%3D&xsec_source=app_share)

> 帖内提到的公司: Point72, Millennium, Citadel

> **内容快照**:
> 
> 二级行研研究员开始更多研究互联网产品，以更好理解价值创造源头。
> 
> PM和买方研究员转向研究互联网产品。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 研究员不再把精力完全all in传统的二级权益，而是开始更多地转身去研究和拥抱互联网产品。
> - 不少PM和买方研究员不再把精力完全all in传统的二级权益，而是开始更多地转身去研究和拥抱互联网产品。

**[行业研究员·TMT-医药-周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/696b5eb6000000021](https://www.xiaohongshu.com/discovery/item/696b5eb6000000021a0242d5?xsec_token=YBFVdwr1N5lDt73WdLpOM_jSvqAS4T6GFB9bmeARGwc2c%3D&xsec_source=app_share)

> 帖内提到的公司: Point72, Millennium, Citadel, 宁德时代, 台积电

> **内容快照**:
> 
> 对冲基金买方研究员岗位需要构建系统化的基本面研究框架，而非盲目追热点。
> 
> 面试中展示对具体公司（如宁德时代）的深入分析能力，包括上游原材料依赖和下游需求弹性。
> 
> EV行业当前市场焦点在电池供应链，半导体周期分析需考虑产能利用率和地缘风险。
> 
> Point72、Millennium、Citadel是知名的对冲基金，招聘买方研究员。
> 
> 简历中应突出系统化基本面研究能力和对具体行业的深入理解。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 关键在于构建系统化的基本面研究框架，而非盲目追热点。
> - 深入拆解其上游原材料依赖和下游需求弹性。
> - 现在市场焦点在电池供应链上，像宁德时代这样的公司...分析台积电时，要从产能利用率到地缘风险的逻辑链。

---

### 43. 中信保诚基金

- **tier**: 二线公募
- **must_have in**: 自营FOF (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: 金融
- **source 标签**: xhs:自营FOF:2
- **notes**:
  - [自营FOF] XHS 自营 FOF 2 次

#### XHS 帖证据 (2 条)

**[自营FOF]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a16aebf000000000](https://www.xiaohongshu.com/discovery/item/6a16aebf0000000008033edb?xsec_token=YBS-3qfPPzk2XzB_nFC2X8B_GfxRuKiVJdX_IdrYXLGgA%3D&xsec_source=app_share)

> 帖内提到的公司: 中信保诚基金

> **内容快照**:
> 
> ETF工具是FOF增强的核心抓手

> **verbatim 锚点 (T1/T3 抽取)**:
> - ETF工具：FOF增强的核心抓手

**[自营FOF]** (relevance=0.30) — [https://www.xiaohongshu.com/discovery/item/6a16a614000000003](https://www.xiaohongshu.com/discovery/item/6a16a61400000000360331d3?xsec_token=YB_a2p3MOsb9Jnd74YYidgBWT7oku88re-gY_OjP_m8D8%3D&xsec_source=app_share)

> 帖内提到的公司: 中信保诚基金

> **内容快照**:
> 
> FOF增强策略利用ETF低成本、流动性好的特点，在行业和策略之间灵活轮动，拓宽固收+组合收益来源，并有助于回撤管理。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 借助ETF低成本、流动性较好的特点，FOF增强策略可以在行业和策略之间进行灵活轮动，力争拓宽组合收益来源；同时，高流动性工具也有助于组合进行更及时的回撤管理。

---

### 44. 中再资产

- **tier**: 保险资管
- **must_have in**: 信用研究员 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: 城投, 金融
- **source 标签**: demo_v1, taxonomy_doc
- **notes**:
  - [信用研究员] 保险资管头部信用研究

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 45. 中诚信国际

- **tier**: 信用评级机构
- **must_have in**: 信用研究员 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: 城投, 金融
- **source 标签**: common_knowledge:头部信用评级
- **notes**:
  - [信用研究员] 按行业共识,国内头部信评

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 46. 信银理财

- **tier**: 理财子
- **must_have in**: 财富管理FOF (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: 金融
- **source 标签**: demo_v1, taxonomy_doc
- **notes**:
  - [财富管理FOF] 中信银行理财子

#### XHS 帖证据 (3 条)

**[固收+多资产]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a03466a000000000](https://www.xiaohongshu.com/discovery/item/6a03466a000000000702f4c4?xsec_token=YBHOt7zneE8YP4HgVHcNE3uPkUsDCRauMCju0BEuxouic%3D&xsec_source=app_share)

> 帖内提到的公司: yfd, 德邦, 上银, 中银理财, 中邮理财, 信银理财

> **内容快照**:
> 
> 固收赛道相比权益bar略低，但近年越来越卷。
> 
> 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向。
> 
> 实习经历垂直会有一定优势，多段转债量化经历有助于秋招。
> 
> 暑期实习面试中，公募、理财子、券商、私募等均有面试经历，部分挂掉。
> 
> 多数市场化机构在暑期确定名额后秋招不开放。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 固收赛道相比权益bar略低，但是近年越来越卷
> - 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向
> - 实习经历垂直会有一定优势，猜测秋招发面是因为有多段转债量化经历

**[固收+多资产]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0c10b1000000000](https://www.xiaohongshu.com/discovery/item/6a0c10b10000000006023dcb?xsec_token=YBWgce1sGsRBZ29D4SlbHerLIa1Scw8HEBqQ62pYxmGkY%3D&xsec_source=app_share)

> 帖内提到的公司: 信银理财

> **内容快照**:
> 
> 信银理财是中信银行全资子公司，提供2027届暑期实习，表现优秀可直通校招终面。
> 
> 投资研究实习生岗位涉及固收+、多资产、量化等资管研究。
> 
> 实习优秀者直通2027校招终面。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 中信银行全资子公司「信银理财」2027 届暑期实习（青萍计划）正式启动！表现优秀直接直通校招终面
> - 职责：固收 +、多资产、量化等资管研究
> - 福利：实习优秀者直通 2027 校招终面

**[行业研究员·消费]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a14565a000000003](https://www.xiaohongshu.com/discovery/item/6a14565a00000000350383e5?xsec_token=YBLKFZuwW0WB2iPpVVndbomZ74PxOYJQApUUJr_go6WKM%3D&xsec_source=app_share)

> 帖内提到的公司: 信银理财, 另一家头部股份行理财子

> **内容快照**:
> 
> 信银理财暑期实习有三个方向：金融算法及AI研发、投资研究、投资交易。其中金融算法及AI研发方向工作内容对标头部股份行理财子，但平台稍窄；投资研究方向hc少，门槛高；投资交易方向对实习卡得不严，看重理工科思维和python。
> 
> 面试流程包括笔试（心理测试+行测+专业知识约80题）、线上无领导群面（约1h，排序题）、终面（上海线下，单面+第二次笔试，含手撕代码）。
> 
> 信银理财是中信的理财子，存在感低但专业性和待遇不错，暑期实习只base上海，卡专业，对金融经管不友好，金科、金工、计算机和各理工类可直接冲。实习结束后答辩考察优秀可秋招直通终面。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 金融算法及AI研发方向的工作内容可以对标另一家头部股份行理财子的对应岗位...投资研究方向hc并不多的缘故，对标中上二级买投研的门槛...投资交易方向可能是大部分人投递的方向，因为按照往年的标准，这个方向不会对过往实习卡的太多
> - 笔试：心理测试40题+行测+专业知识约80题...线上无领导群面：约1h，10人左右...终面：一般是上海线下，单面+第二次笔试，其中单面是半结构简历面...后续笔试比较难，时间2h，会有金融专业题和分析题以及手撕代码
> - 中信的理财子，总是存在感有点低，但实际上专业性和待遇都还不错的一家...只base上海，没有北京的，卡专业...对only金融经管并不友好，金科、金工、计算机和各理工类可以直接冲...实习结束后答辩考察优秀可以秋招直通终面

---

### 47. 兴业证券

- **tier**: 中型券商研究所
- **must_have in**: 行业研究员·消费 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: 消费
- **source 标签**: xhs:行业研究员·消费:5
- **notes**:
  - [行业研究员·消费] XHS mention 第一,消费研究突出

#### XHS 帖证据 (11 条)

**[投行 IBD]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/69ce44cc000000001](https://www.xiaohongshu.com/discovery/item/69ce44cc000000001d01f7ed?xsec_token=YBIR2Y3LBhuk-vRmL2g0YltYiXkuB0U2Z6pD9wk7QrRGg%3D&xsec_source=app_share)

> 帖内提到的公司: 兴业证券, 兴证资管, 兴全基金

> **内容快照**:
> 
> 兴业证券最赚钱的业务是自营投资和资产管理，投行和研究所相对不赚钱。
> 
> 兴业证券投行岗位包括投行业务助理、债券承做助理、资产证券化承做助理、承销发行助理。
> 
> 兴业证券自营部门推荐证券投资部-行业研究助理和债券与衍生产品业务部-研究助理。
> 
> 兴证资管核心岗位是研究助理，涵盖权益、量化、FOF和衍生品方向。
> 
> 兴业证券投行对本科学历门槛可放松至末9及同Level学校。
> 
> 兴业证券股权业务体量在券商中排名10-20名。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 最赚钱的，当属自营投资和资产管理。而大家最为熟悉的投资银行和研究所属于兴业“最不赚钱”的业务。
> - 投行业务助理、债券承做助理、资产证券化承做助理、承销发行助理，一共4个岗位。
> - 首推证券投资部-行业研究助理和债券与衍生产品业务部-研究助理。

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68ae4ff7000000001](https://www.xiaohongshu.com/discovery/item/68ae4ff7000000001c0106a0?xsec_token=YBaXH2avCjRyk_t-gCh8k1VODrk8SJBm7HhZK9xfJZgO0%3D&xsec_source=app_share)

> 帖内提到的公司: 兴业证券

> **内容快照**:
> 
> 兴业证券海外研究TMT团队提供线上实习机会。
> 
> 该实习岗位属于卖方研究，覆盖TMT行业。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 线上实习|兴业证券海外研究TMT团队实习
> - 海外研究TMT团队

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a004d91000000003](https://www.xiaohongshu.com/discovery/item/6a004d910000000036000bfe?xsec_token=YBYM1cUi6i2AdR2d2EYp7gyzNSgGWMnMTf2wxGS2XvQqk%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 中金公司, 华泰证券, 中信建投证券, 国泰海通证券, 招商证券

> **内容快照**:
> 
> 投行招聘中，除了中金公司，大部分券商强调实习留用，面试越来越水，更看重实战能力。
> 
> 26年投行招聘仍是招聘大年，腰腿部券商提供更多机会，学历门槛下探。
> 
> 列举了15家开放投行暑期实习的券商和14家开放春季招聘的券商，其中4家同时开放。
> 
> 本科学历背景普通但实战能力突出的候选人，在26年拿到投行机会的可能性提升。
> 
> 投行面试越来越水，技术面试在绝大部分券商涉及不到。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 除了中金公司以外，其他大部分券商都强调“实习留用”...投行的面试越来越水了。
> - 26年仍会是投行的招聘大年...腰腿部券商投行给了大家更多的“选择权”...学历相对没那么优秀，26年有更多的加入投行的机会和可能性。
> - 至少包括15家：中信证券、中金公司、华泰证券...至少包括14家：招商证券、国联民生证券...同时开放暑期实习和春季招聘的投行，包括4家：招商证券、国联民生证券、东吴证券、西部证券。

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000](https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000702ace7?xsec_token=YB9MVh1sELWdJvRY7-4rURZo9qtVNwXXJJLAGIjlCzytE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 中金公司, 华泰证券, 中信建投证券, 申万宏源

> **内容快照**:
> 
> 中信证券多项业务指标连年夺魁，是券商中的'神'级公司。
> 
> 国泰海通由国开君安和海通证券合成，资本实力跃居行业榜首。
> 
> 中金公司是首家中外合资投行，投行业务标杆。
> 
> 华泰证券是金融科技+财富管理领域的标杆。
> 
> 中信建投证券降薪严重，与前三个相比掉队。
> 
> 2025年证券行业呈现'强者恒强'的马太效应，头部券商占据大部分市场份额。
> 
> 头部券商总部前台岗求职难度不输国有总行，建议根据学历背景和实习相关性合理选择。
> 
> 随着大A慢牛市场，证券公司实习机会增多，26届应把握机会。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 中信证券可以单独开一个'神'级，多项业务指标连年夺魁
> - 国泰海通由国开君安和海通证券合成而成的新龙头，资本实力跃居行业榜首
> - 中金公司，首家中外合资投行，投行业务标杆

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a00852d000000000](https://www.xiaohongshu.com/discovery/item/6a00852d0000000008002bb5?xsec_token=YBYM1cUi6i2AdR2d2EYp7gy0jrM93HeTyqyT4_9HsqWHE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 华泰证券, 中金证券, 中信建投, 招商证券

> **内容快照**:
> 
> 券商分为五个梯队，第一梯队包括中信证券、国泰海通、华泰证券、中金证券、中信建投等，平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> 
> 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> 
> 第一梯队偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历更加分。
> 
> 第三梯队门槛相对灵活，海外院校、转专业同学都有机会，关键是简历里要体现对金融行业的理解。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> - 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> - 通常更偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历会更加分。

**[投行 IBD]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69e9e830000000002](https://www.xiaohongshu.com/discovery/item/69e9e8300000000020007004?xsec_token=YBc11JooR0NZ98F21otDUFVYPtpfcbAB15sOU99-7Wv0g%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 中金公司, 华泰证券, 国泰海通, 中信建投, 申万宏源

> **内容快照**:
> 
> 国内券商存在明显的等级鄙视链，夯梯队（三中一华+国君海通）为投行天花板，项目资源多、薪资顶流，但门槛极高，要求清北复交+海外名校硕及头部实习经历。
> 
> 应届生求职建议包括：能冲夯梯队和顶级梯队直接冲；想回老家发展的优先看本地龙头券商；实习比空学历重要；不要死磕投行，研究所、财富管理、金融科技竞争小且发展空间不差。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 中信证券、中金公司、华泰证券、国泰海通、中信建投...项目资源多到做不完，薪资顶流，应届生base普遍20w+...门槛也真的🐮：清北复交+海外名校硕是基本盘
> - 能冲夯梯队+顶级梯队直接冲...想回老家发展的，优先看人上人里的本地龙头券商...实习＞空学历！...别死磕投行，研究所、财富管理、金融科技竞争小很多

_(+5 条更多帖未展示, 同 sub_cat)_

---

### 48. 华为

- **tier**: 互联网大厂
- **must_have in**: 多模态推理优化 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: AI 基础设施
- **source 标签**: taxonomy_doc
- **notes**:
  - [多模态推理优化] 盘古多模态

#### XHS 帖证据 (3 条)

**[固收+多资产]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a03466a000000000](https://www.xiaohongshu.com/discovery/item/6a03466a000000000702f4c4?xsec_token=YBHOt7zneE8YP4HgVHcNE3uPkUsDCRauMCju0BEuxouic%3D&xsec_source=app_share)

> 帖内提到的公司: yfd, 德邦, 上银, 中银理财, 中邮理财, 信银理财

> **内容快照**:
> 
> 固收赛道相比权益bar略低，但近年越来越卷。
> 
> 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向。
> 
> 实习经历垂直会有一定优势，多段转债量化经历有助于秋招。
> 
> 暑期实习面试中，公募、理财子、券商、私募等均有面试经历，部分挂掉。
> 
> 多数市场化机构在暑期确定名额后秋招不开放。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 固收赛道相比权益bar略低，但是近年越来越卷
> - 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向
> - 实习经历垂直会有一定优势，猜测秋招发面是因为有多段转债量化经历

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a003f80000000000](https://www.xiaohongshu.com/discovery/item/6a003f80000000000702bc2b?xsec_token=YBsNhXOTI38nQHFtlKmC5ApMt9f4juTsqo5GeMEAeQ3po%3D&xsec_source=app_share)

> 帖内提到的公司: 华为, Shopee

> **内容快照**:
> 
> 华为财经暑期实习面试包含会计问题、简历深挖和BQ，涉及财务报表、CAS与IFRS对比、卖方研究经历、互联网实习细节等。
> 
> 学生有卖方研究经历，面试中详细拆分了robotaxi UE模型，并讨论了卖方分析师在AI时代的价值。
> 
> 华为财经面试官强调卖方需要深入的行业理解，认为护城河可以抵御AI冲击。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 一面（会计问题+简历深挖）...二面（简历深挖+反问）...三面（简历深挖+BQ+反问）
> - 让我详细拆分了robotaxi UE模型的收入、成本的细项以及核心假设
> - 他说卖方需要很深入的行业理解，如果能在这方面有比较深的护城河的话不一定会像你说的这样被削弱价值。

**[Agent工程师]** (relevance=0.20) — [https://www.xiaohongshu.com/discovery/item/6a084f3a000000003](https://www.xiaohongshu.com/discovery/item/6a084f3a0000000038021fc0?xsec_token=YBgjyFUu8A_-NKggKg_0wQluSSsIGSEp5TEona81KU7VM%3D&xsec_source=app_share)

> 帖内提到的公司: 华为

> **内容快照**:
> 
> 华为暑期实习AI应用岗位面试流程包括技术面和主管面，技术面主要围绕简历项目经历，涉及LSTM、RNN、CNN、Transformer等深度学习模型，以及Agent项目、RAG等。主管面侧重联培经历、项目困难、压力应对等。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 技术面（主要围绕简历中项目经历进行，问答40分钟，手撕20分钟）

---

### 49. 华创证券

- **tier**: 中型券商研究所
- **must_have in**: 行业研究员·消费 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: 消费
- **source 标签**: xhs:行业研究员·消费:3
- **notes**:
  - [行业研究员·消费] XHS 消费组 3 次

#### XHS 帖证据 (4 条)

**[固收+多资产]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a03466a000000000](https://www.xiaohongshu.com/discovery/item/6a03466a000000000702f4c4?xsec_token=YBHOt7zneE8YP4HgVHcNE3uPkUsDCRauMCju0BEuxouic%3D&xsec_source=app_share)

> 帖内提到的公司: yfd, 德邦, 上银, 中银理财, 中邮理财, 信银理财

> **内容快照**:
> 
> 固收赛道相比权益bar略低，但近年越来越卷。
> 
> 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向。
> 
> 实习经历垂直会有一定优势，多段转债量化经历有助于秋招。
> 
> 暑期实习面试中，公募、理财子、券商、私募等均有面试经历，部分挂掉。
> 
> 多数市场化机构在暑期确定名额后秋招不开放。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 固收赛道相比权益bar略低，但是近年越来越卷
> - 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向
> - 实习经历垂直会有一定优势，猜测秋招发面是因为有多段转债量化经历

**[行业研究员·消费]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a157c5e000000000](https://www.xiaohongshu.com/discovery/item/6a157c5e0000000008003cf1?xsec_token=YB2j-vEM_s-iA7wHniUS_bx3LCbOJ3-St_tnIbrNQct6s%3D&xsec_source=app_share)

> 帖内提到的公司: 华创证券

> **内容快照**:
> 
> 华创证券食品饮料团队招聘行业研究实习生，要求掌握wind、excel等技能，不强制专业背景，有消费品投研经验或财经/食品背景优先。
> 
> 华创证券研究所食品饮料团队多次获新财富第一名，累计七次，2023年荣获新财富白金分析师。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 华创食品饮料团队｜华创证券研究所（食品饮料团队）｜岗位：食品饮料行业研究实习生
> - 团队多次获新财富第一名，累计七次，2023年荣获新财富白金分析师

**[行业研究员·消费]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69a5346b000000001](https://www.xiaohongshu.com/discovery/item/69a5346b000000001b0157a5?xsec_token=YBVzbD5p7ZCMur-Jj1vUDWNgbQhyVytupoXv-lP9NV1Uc%3D&xsec_source=app_share)

> 帖内提到的公司: 华创证券

> **内容快照**:
> 
> 华创证券食品饮料团队招聘实习生，有明确留用机会，提供餐补和补贴。
> 
> 华创食品饮料团队多次获新财富第一名，2023年新财富白金分析师。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 表现优秀有【明确留用】机会
> - 累计七次新财富第一名，2023年荣获新财富白金分析师

**[行业研究员·消费]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a108f20000000003](https://www.xiaohongshu.com/discovery/item/6a108f20000000003501f7ab?xsec_token=YBgVepef6Q5-h3PAJO7pWd6aOs6xftUmCtGOKrrKpX1yY%3D&xsec_source=app_share)

> 帖内提到的公司: 华创证券

> **内容快照**:
> 
> 华创证券招聘食品饮料团队行研实习生，要求研究生在读或大四保研，掌握wind、excel等技能，有消费品投研经验或财经、食品类专业背景优先。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 华创-招食品饮料团队行研实习生

---

### 50. 华泰联合证券

- **tier**: 头部券商研究所
- **must_have in**: 投行 IBD (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: 金融
- **source 标签**: common_knowledge:头部投行, taxonomy_doc
- **notes**:
  - [投行 IBD] 按行业共识,华泰投行子

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 51. 商汤科技

- **tier**: AI 初创
- **must_have in**: 多模态推理优化 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: AI 基础设施
- **source 标签**: taxonomy_doc, xhs:多模态推理优化:8
- **notes**:
  - [多模态推理优化] CV 多模态老牌

#### XHS 帖证据 (7 条)

**[多模态推理优化]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/69aaa2c8000000001](https://www.xiaohongshu.com/discovery/item/69aaa2c8000000001a0276c9?xsec_token=YB89oWI3TeIYbXgAuOCOVtr0Pa0pW6h8MKtSIZrodgypU%3D&xsec_source=app_share)

> 帖内提到的公司: 商汤科技

> **内容快照**:
> 
> 商汤科技多模态大模型组招聘实习生，要求研二、代码扎实、长期实习，涉及多模态大模型和Agent研发。
> 
> 商汤科技多模态大模型组提供全流程训练、评测、Agent前沿探索等核心工作，有转正机会。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 商汤科技多模态大模型组长期招实习生
> - 表现优秀者有转正/Return Offer 机会

**[多模态推理优化]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69c349c0000000002](https://www.xiaohongshu.com/discovery/item/69c349c0000000002102e9b5?xsec_token=YBbyzdjv92jWUBwQCLa3NAxCsNzgPhEUUPXODTsDJmnDM%3D&xsec_source=app_share)

> 帖内提到的公司: 商汤科技

> **内容快照**:
> 
> 商汤科技研究院多模态大模型岗位面试问题包括：自我介绍、项目介绍、PPO原理、DPO训练问题、奖励模型训练与结构、生成式奖励模型优缺点、轻量模型替代奖励模型、MOE架构、专家负载均衡、DeepSpeed三个阶段原理、Zero3 OOM调整、编程思维题（打怪兽最少经验值）。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 1.自我介绍 2.介绍项目 3.ppo原理 4.dpo训练出现的问题 5.奖励模型怎么训练，结构是怎么样的 6.生成式的奖励模型了解吗，他和普通奖励模型的优缺点分别是什么 7.能不能用预训练的轻量的大模型来替代奖励模型，分别的优缺点 8.介绍MOE架构 9.moe架构训练通常容易产生什么问题 10.什么方法解决专家负载均衡的问题 11.deepseed的三个阶段原理，如果用了zero3还是OOM应该调整那些参数 12.编程思维题，有n只怪兽和初始验值，打怪兽会消耗一定的经验值，同时打死怪兽又会获得一定的经验值，问如果随机开始打怪兽，能够消灭所有怪兽所需要的最少经验值说思路

**[多模态推理优化]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69317cfc000000001](https://www.xiaohongshu.com/discovery/item/69317cfc000000001e035a58?xsec_token=YBkK_n4ryEY1DI26ro9fj-D5k2bYS7FjlaQNc4UdCSOLc%3D&xsec_source=app_share)

> 帖内提到的公司: 商汤科技

> **内容快照**:
> 
> 商汤多模态算法实习生面试围绕项目提问，没有太多八股，从一面到收到offer历时14天。
> 
> 商汤科技面试流程较快，面试官友好。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 面试官都很nice，两面围绕项目来问，没太拷打八股，从一面到收到offer历时14天
> - 商汤万岁～

**[多模态推理优化]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68446b3a000000002](https://www.xiaohongshu.com/discovery/item/68446b3a000000002202cdf6?xsec_token=YBhLGYkbIUykdw_lDD1t4e0S9I9Gi6XkSP4T--Cy3NRl8%3D&xsec_source=app_share)

> 帖内提到的公司: 商汤科技

> **内容快照**:
> 
> 商汤科技多模态大模型算法实习岗位，研一学生，强调选择比努力重要。
> 
> 多模态大模型是AI应用方向的热门赛道。

> **verbatim 锚点 (T1/T3 抽取)**:
> - Sensetime 上海｜商汤多模态大模型算法实习
> - 多模态大模型

**[多模态推理优化]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/684da64d000000001](https://www.xiaohongshu.com/discovery/item/684da64d0000000012000d75?xsec_token=YBYLFbTBbl4leyYa-Ia_jvYUnp378d2X0dXPYgFs3eA5E%3D&xsec_source=app_share)

> 帖内提到的公司: 商汤科技

> **内容快照**:
> 
> 商汤多模态大模型二面面试内容包括项目介绍、QFormer/QLlama中间件作用、神经网络训练推理差异、PyTorch实现层冻结、手撕岛屿数量。
> 
> 商汤多模态基座模型组实习岗位，已获得offer但拒掉。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 1.介绍项目，反问和拷打 2.讨论QFormer or QLlama等中间件的作用 3.神经网络中有哪些结构在训练和推理有比较大的差别（以图像识别为例，batchnorm差异会比较大） 4.在训练大模型时，用pytorch如何实现某些层freeze 5.手撕岛屿数量（dfs）
> - 商汤维护多模态基座模型的组。

**[多模态推理优化]** (relevance=0.30) — [https://www.xiaohongshu.com/discovery/item/6a0f08fa000000000](https://www.xiaohongshu.com/discovery/item/6a0f08fa0000000008027c99?xsec_token=YB4MPHIDtCnwPJUdLrr50OEpWNTmZJdYvu-ToRZGY3I3o%3D&xsec_source=app_share)

> 帖内提到的公司: 商汤科技

> **内容快照**:
> 
> 商汤发布轻量化多模态智能体模型，并开放免费调用额度，可能对AI求职者提供工具或学习资源。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 商汤科技，推出新一代轻量化多模态智能体模型商汤日日新 SenseNova 6.7 Flash-Lite。同时，SenseNova Token Plan 限时免费开放。

_(+1 条更多帖未展示, 同 sub_cat)_

---

### 52. 国寿投资

- **tier**: 保险资管
- **must_have in**: 固收+多资产 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: 金融
- **source 标签**: saif:2025
- **notes**:
  - [固收+多资产] SAIF 2025 命中

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2025 | 国寿投资保险资产管理有限公司 | 行业研究员 | 1 | 保险资管 |

#### XHS 帖证据 (2 条)

**[公募权益研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a154d91000000000](https://www.xiaohongshu.com/discovery/item/6a154d91000000000702163f?xsec_token=YBtykXCAFyiHSXD_GpX4xfBCEPl85Qoq2k5vZtdH2VHjI%3D&xsec_source=app_share)

> 帖内提到的公司: 泰康资产, 景顺长城, 中投, 社保基金, 外管局外汇中心, 易方达基金

> **内容快照**:
> 
> 泰康资产和景顺长城正在面试辅导，涉及投研岗位。
> 
> 辅导的offer覆盖一级投资（含PE及PERE）、战投、产投、二级投研、投行、银行、理财子、金融央国企等。
> 
> 辅导过腾投、GIC、易方达基金、华夏基金、泰康资产、bb行、中金、华泰、中投、中信集团管培、社保基金、外管局外汇中心、国寿投资、建总、工总、农发总、新华社、强势部委等top全职offer。
> 
> 背景一般甚至有明显bug的也能辅导上岸top全职offer，例如两财一贸tier拿下大买投研，本科top10之外硕士QS100-200拿下头部保险资管投研，非top4本硕上岸头部一级投资岗等。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 泰康资产+景顺长城面试辅导
> - 自己投递的offer覆盖一级投资（含pe及pere）/战投产投/二级投研/投行/银行/理财子/金融央国企/垄断型央企/部委/另类的all rounder实力
> - 辅导腾投/GIC/易方达基金/华夏基金/泰康资产/bb行/中金/华泰/中投/中信集团管培/社保基金/外管局外汇中心/国寿投资/建总/工总/农发总/新华社/强势部委等top全职offer的实力

**[固收+多资产]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6941241e000000001](https://www.xiaohongshu.com/discovery/item/6941241e000000001d03bb37?xsec_token=YBSeArbBOqqhQMs6u3xUZLLgmKZ6Ql4jjkJ5f6KMAMFu4%3D&xsec_source=app_share)

> 帖内提到的公司: 招银理财, 工银理财, 建信理财, 中信证券资管, 中金资管, 国寿资管

> **内容快照**:
> 
> 资管岗位起薪25-35w，3年追平投行，5-7年有机会过百，女生友好。
> 
> 央企财务公司应届可给到35w，工作稳定，没有裁员风险。
> 
> 金融基础设施起薪约25w，但未来薪资天花板比总行高，到点下班。
> 
> 今年是固收大年，三四月份提示过可以多准备固收方向。
> 
> 列举了多家资管、财务公司、金融基础设施的具体公司名称。
> 
> 资管分权益和固收两条线，固收门槛较低。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 资管起薪普遍在25-35w之间，虽然略低于头部投行，但基本上3年追平，天花板比投行更高，5-7年就有一定概率过百。不拼体力，吃能力和天赋，女生友好
> - 应届可以给到35w，工作围绕集团主业，不用在市场里搏杀，性价比极高
> - 起薪可能略低于总行，一般在25w左右，但未来薪资天花板是比总行还高的

---

### 53. 大公国际

- **tier**: 信用评级机构
- **must_have in**: 信用研究员 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: 城投
- **source 标签**: common_knowledge:头部信用评级
- **notes**:
  - [信用研究员] 按行业共识,信评三大之一

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 54. 平安证券

- **tier**: 中型券商
- **must_have in**: 固收交易员 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: 金融
- **source 标签**: taxonomy_doc
- **notes**:
  - [固收交易员] FICC 团队强

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 平安资产管理有限责任公司 | 行业研究员 | 1 | 保险资管 |

#### XHS 帖证据 (12 条)

**[固收+多资产]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a03466a000000000](https://www.xiaohongshu.com/discovery/item/6a03466a000000000702f4c4?xsec_token=YBHOt7zneE8YP4HgVHcNE3uPkUsDCRauMCju0BEuxouic%3D&xsec_source=app_share)

> 帖内提到的公司: yfd, 德邦, 上银, 中银理财, 中邮理财, 信银理财

> **内容快照**:
> 
> 固收赛道相比权益bar略低，但近年越来越卷。
> 
> 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向。
> 
> 实习经历垂直会有一定优势，多段转债量化经历有助于秋招。
> 
> 暑期实习面试中，公募、理财子、券商、私募等均有面试经历，部分挂掉。
> 
> 多数市场化机构在暑期确定名额后秋招不开放。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 固收赛道相比权益bar略低，但是近年越来越卷
> - 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向
> - 实习经历垂直会有一定优势，猜测秋招发面是因为有多段转债量化经历

**[公募基金中后台]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0b1435000000003](https://www.xiaohongshu.com/discovery/item/6a0b14350000000035033c92?xsec_token=YBjJDvW9ftzu9in_HYy8Pxxg20_Kg7r5OsrRXUwVlafdo%3D&xsec_source=app_share)

> 帖内提到的公司: 国联民生, 南方基金, 东吴证券, 景顺长城, 平安证券, 平安理财

> **内容快照**:
> 
> 用户已面试国联民生中台岗、南方基金群面、东吴证券债承、景顺长城中台岗，并完成平安证券、平安理财、民生银行、东方财富证券的测评。
> 
> 用户投递了多家金融机构的暑期实习，包括券商、基金、银行理财子等。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 已面试：1、国联民生中台岗 2、南方基金群面 3、东吴证券债承 4、景顺长城中台岗 已测评：1、平安证券、平安理财 2、民生银行 3、东方财富证券
> - 国联民生中台岗、南方基金群面、东吴证券债承、景顺长城中台岗、平安证券、平安理财、民生银行、东方财富证券

**[利率宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/65d82a21000000000](https://www.xiaohongshu.com/discovery/item/65d82a21000000000b01727e?xsec_token=YBERA2NT_0W6NUgMTa_0vN0YwyvwgVf9e05xmaQ_CvrGo%3D&xsec_source=app_share)

> 帖内提到的公司: 国利, 平安, 国际, BGC, 信唐, 上田

> **内容快照**:
> 
> 货币中介门槛相对其他金融机构友好，但内卷严重，学历层次增高。
> 
> 面试货币中介需要了解所报价品种的市场概况、基础设施、参与机构，以及岗位日常和所需能力。
> 
> 国利是货币中介中最强的，平安、国际也比较猛，BGC次之，信唐不容小觑，上田是后起之秀。
> 
> 货币中介主要报价品种包括利率、信用、货币、存单、借贷、利率互换等，地方债逐渐独立成台。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 现在内卷比较严重，货币中介小伙伴们的学历层次也逐渐增高，不乏海内外名校硕士。但门槛总体还是没有其他金融机构要求那么严格，社招和校招对专业和学历还算友好。
> - 了解清楚自己面试台子所报价品种的市场概况，基础设施，参与机构；了解对应岗位每天的日常；了解该岗位需要什么能力，自己有什么特质与之匹配。
> - 国利最强，平安、国际也比较猛，BGC次之，信唐也不容小觑，在某些品种的报价表现上毫不逊色。上田作为后起之秀，社招了很多以前同行的经纪人，报价水平也一样专业。

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/669c8650000000000](https://www.xiaohongshu.com/discovery/item/669c8650000000000a02755d?xsec_token=YByIede-U9SUzZKRbL5ECpeyVlBMGy40PZrIh0A64Tocg%3D&xsec_source=app_share)

> 帖内提到的公司: 国元证券, 平安证券, 民生证券

> **内容快照**:
> 
> 卖方首席的职业路径可以从双非院校起步，通过努力逐步晋升，二级研究提供凭借个人能力走出来的机会。
> 
> 民生证券海外首席易老师，从国元证券到平安证券再到民生证券，专注于传媒互联网、消费等方向。
> 
> 二级研究行业为小镇做题家提供凭借个人能力走出来的机会，晋升不只看关系。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 双非院校走出来的卖方首席，勤奋&实力
> - 2020年初离开国元进入平安，一直从事传媒互联网、消费等方向的研究...2023年7月进入民生证券
> - 二级研究至少还给你一个凭借个人能力走出来的机会，这也是吸引一代又一代小镇做题家奋不顾身扎进来的原因之一。

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a004d91000000003](https://www.xiaohongshu.com/discovery/item/6a004d910000000036000bfe?xsec_token=YBYM1cUi6i2AdR2d2EYp7gyzNSgGWMnMTf2wxGS2XvQqk%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 中金公司, 华泰证券, 中信建投证券, 国泰海通证券, 招商证券

> **内容快照**:
> 
> 投行招聘中，除了中金公司，大部分券商强调实习留用，面试越来越水，更看重实战能力。
> 
> 26年投行招聘仍是招聘大年，腰腿部券商提供更多机会，学历门槛下探。
> 
> 列举了15家开放投行暑期实习的券商和14家开放春季招聘的券商，其中4家同时开放。
> 
> 本科学历背景普通但实战能力突出的候选人，在26年拿到投行机会的可能性提升。
> 
> 投行面试越来越水，技术面试在绝大部分券商涉及不到。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 除了中金公司以外，其他大部分券商都强调“实习留用”...投行的面试越来越水了。
> - 26年仍会是投行的招聘大年...腰腿部券商投行给了大家更多的“选择权”...学历相对没那么优秀，26年有更多的加入投行的机会和可能性。
> - 至少包括15家：中信证券、中金公司、华泰证券...至少包括14家：招商证券、国联民生证券...同时开放暑期实习和春季招聘的投行，包括4家：招商证券、国联民生证券、东吴证券、西部证券。

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000](https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000702ace7?xsec_token=YB9MVh1sELWdJvRY7-4rURZo9qtVNwXXJJLAGIjlCzytE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 中金公司, 华泰证券, 中信建投证券, 申万宏源

> **内容快照**:
> 
> 中信证券多项业务指标连年夺魁，是券商中的'神'级公司。
> 
> 国泰海通由国开君安和海通证券合成，资本实力跃居行业榜首。
> 
> 中金公司是首家中外合资投行，投行业务标杆。
> 
> 华泰证券是金融科技+财富管理领域的标杆。
> 
> 中信建投证券降薪严重，与前三个相比掉队。
> 
> 2025年证券行业呈现'强者恒强'的马太效应，头部券商占据大部分市场份额。
> 
> 头部券商总部前台岗求职难度不输国有总行，建议根据学历背景和实习相关性合理选择。
> 
> 随着大A慢牛市场，证券公司实习机会增多，26届应把握机会。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 中信证券可以单独开一个'神'级，多项业务指标连年夺魁
> - 国泰海通由国开君安和海通证券合成而成的新龙头，资本实力跃居行业榜首
> - 中金公司，首家中外合资投行，投行业务标杆

_(+6 条更多帖未展示, 同 sub_cat)_

---

### 55. 弘毅投资

- **tier**: 头部PE
- **must_have in**: PE投后VC行研 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: 消费, 金融
- **source 标签**: saif:2025, taxonomy_doc
- **notes**:
  - [PE投后VC行研] 联想系 PE 头部

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2025 | 弘毅投资 | 行业研究员 | 1 | 私募 |

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 56. 德弘资本

- **tier**: 头部PE
- **must_have in**: PE投后VC行研 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: 医药, 消费
- **source 标签**: saif:2025, taxonomy_doc
- **notes**:
  - [PE投后VC行研] 前 KKR 大中华团队

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2025 | 德弘资本 | 行业研究员 | 1 | 私募 |

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 57. 晨壹基金

- **tier**: 头部PE
- **must_have in**: PE投后VC行研 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: TMT, 消费
- **source 标签**: saif:2025, taxonomy_doc
- **notes**:
  - [PE投后VC行研] 并购基金头部

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2025 | 晨壹基金 | 行业研究员 | 1 | 私募 |

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 58. 永赢基金

- **tier**: 二线公募
- **must_have in**: 行业研究员·TMT-医药-周期 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: TMT, 新能源
- **source 标签**: saif:2024, taxonomy_doc
- **notes**:
  - [行业研究员·TMT-医药-周期] TMT 高弹性产品强

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 永赢基金管理有限公司 | 行业研究员 | 1 | 公募基金 |

#### XHS 帖证据 (1 条)

**[行业研究员·消费]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68523924000000002](https://www.xiaohongshu.com/discovery/item/685239240000000022028983?xsec_token=YB1tOVHt4MrRCgE3YRmfKUfzkX4Zhwklu8QU9qotk8kHY%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达, 华夏, 博时, 国泰, 汇添富, 南方

> **内容快照**:
> 
> 易方达、华夏是头部公募，整体待遇好，科技岗位应届生薪资尤其高。
> 
> 博时、国泰、汇添富、南方类似公务员氛围。
> 
> 银行系公募（招商、中银、工银）薪资相对固化，待遇提升空间有限，但工作相对安逸。
> 
> 永赢、嘉实、鹏华待遇不错，但工作强度卷王级别。
> 
> 兴全待遇不错，人少资源多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 易方达、华夏：头部中的头部，整体待遇不会太差，据说科技岗位应届生薪资对比其他应届会尤其高一些
> - 博时、国泰、汇添富、南方：据说类似公务员氛围浓厚
> - 银行系包括（招商、中银、工银等）薪资相对固化，待遇可提升空间对比其他就不太行了，安逸也是相对的吧

---

### 59. 申万宏源证券

- **tier**: 中型券商研究所
- **must_have in**: 卖方研究员·宏观策略 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: —
- **source 标签**: saif:2024, taxonomy_doc, xhs:卖方研究员·宏观策略:12
- **notes**:
  - [卖方研究员·宏观策略] 宏观策略 XHS 第一

#### SAIF 校友流向证据 (2 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 申万宏源证券有限公司 | 卖方分析师 | 1 | 券商研究所 |
| 2024 | 申万宏源证券资产管理有限公司 | 行业研究员 | 1 | 券商资管 |

#### XHS 帖证据 (18 条)

**[公募权益研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69be9640000000002](https://www.xiaohongshu.com/discovery/item/69be96400000000022028f1b?xsec_token=YB2bfX8mNVINV1vrfl08zvNysm_uMZEg2GX7iWHkIYOdk%3D&xsec_source=app_share)

> 帖内提到的公司: 申万宏源证券

> **内容快照**:
> 
> 申万宏源证券资产管理部研究岗面试问题包括：为什么选择资管研究而非券商研究所、资管研究与卖方研究的区别、覆盖行业兴趣、消费品公司分析框架、估值方法（PE/PB/DCF）、管理层判断、财务报表可疑点调查、股票推荐风险提示、股票池构建、研究员与基金经理协作。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 1. 你为什么选择资管行业的研究岗，而不是券商研究所？
2. 资管研究更偏向于为投资决策服务，你觉得这和卖方研究有什么不同？
3. 你对自己覆盖的哪个行业比较有研究兴趣？为什么？
4. 如果让你深入研究一家消费品公司，你的分析框架会是怎样的？（从行业到公司）。
5. 如何给一家公司进行估值？在什么情况下会用PE，什么情况下用PB或DCF？
6. 你如何判断一个公司的管理层是否优秀？会关注哪些方面？
7. 如果发现一家公司的财务报表存在一些可疑的点（比如应收账款异常增长），你会如何进一步调查？
8. 在推荐一只股票时，除了上涨空间，你还会重点提示哪些风险？
9. 你平时如何构建和维护自己的股票池？
10. 资管部的研究员和基金经理是如何协作的？

**[卖方研究员·宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/693106d7000000021](https://www.xiaohongshu.com/discovery/item/693106d7000000021e006e21?xsec_token=YBkK_n4ryEY1DI26ro9fj-D7emPMwxa97ZlbsOONF14do%3D&xsec_source=app_share)

> 帖内提到的公司: 申万宏源

> **内容快照**:
> 
> 申万宏源A股策略实习生招聘，要求对基本面分析和A股主动投资有热情，硕士或以上在读，需上海线下实习。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 申万宏源A股策略-实习生招聘
十年xcf团队，希望招募对基本面分析和A股主动投资有热情的同学

**[卖方研究员·宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69304f9d000000001](https://www.xiaohongshu.com/discovery/item/69304f9d000000001f00e803?xsec_token=YBhEFQik3ewutfUMB2Eho2tvwWJCWowusqejbUrm_YOds%3D&xsec_source=app_share)

> 帖内提到的公司: 申万宏源

> **内容快照**:
> 
> 申万宏源A股策略实习生招聘，要求硕士或以上在读，需在上海线下实习，对基本面分析和A股主动投资有热情。
> 
> 申万宏源是知名券商，其A股策略团队为十年xcf团队，具有较强实力。
> 
> 策略研究接近投资，能体验实战性投资研究，对实习求职有帮助。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 申万宏源A股策略-实习生招聘十年xcf团队，希望招募对基本面分析和A股主动投资有热情的同学
> - 十年xcf团队
> - 策略是最接近投资的研究领域，你能体验到具备实战性、能落地的投资研究。

**[卖方研究员·宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d63549000000001](https://www.xiaohongshu.com/discovery/item/69d63549000000001a032a27?xsec_token=YBBdaIAOjeqRnXb4rRiMLRqqeuW8Twxq3LCxPRDroTnkg%3D&xsec_source=app_share)

> 帖内提到的公司: 申万宏源

> **内容快照**:
> 
> 申万宏源FICC事业部信用研究岗实习生招聘，要求重点高校财经专业，硕士或优秀大四，持有CPA优先，每周到岗4天，实习3个月以上，表现优秀可推荐2026年春季校招。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 申万宏源FICC事业部 信用研究岗 实习生招聘

**[卖方研究员·宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68ab4ea0000000021](https://www.xiaohongshu.com/discovery/item/68ab4ea0000000021c038fcd?xsec_token=YBlQrLFXlUGaGJROVQhe0eGDv242Id-CbspUp2Mq_ni_M%3D&xsec_source=app_share)

> 帖内提到的公司: 申万宏源

> **内容快照**:
> 
> 申万宏源行业工具书覆盖多个行业研究框架，适合金融求职者学习行业逻辑。
> 
> 该工具书对想进入投资/行研岗的学生有帮助，可作为面试准备材料。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 从宏观经济、金融地产，到化工、TMT、制造业…十几个行业的研究框架全涵盖！
> - 想进投资/行研岗？拿它当'面试武器'，面试官都得夸你专业！

**[卖方研究员·宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69fdb055000000003](https://www.xiaohongshu.com/discovery/item/69fdb055000000003501d5a2?xsec_token=YBMr_thyXngm8ptqzFbVrNfVWNp9PNOrnhdx9Y9BX5cfs%3D&xsec_source=app_share)

> 帖内提到的公司: 申万宏源

> **内容快照**:
> 
> 申万宏源暑期有两个大类资产配置岗位，用户询问区别。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 有大佬知道swhy暑期这两个岗位的区别嘛？上面都写的大类资产配置，两个岗位的工作内容和bar会有什么不同嘛

_(+12 条更多帖未展示, 同 sub_cat)_

---

### 60. 米哈游

- **tier**: 互联网大厂
- **must_have in**: AI算法业务 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: AI 应用层
- **source 标签**: taxonomy_doc
- **notes**:
  - [AI算法业务] 游戏 AI/推荐

#### XHS 帖证据 (2 条)

**[AI PM]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/67d3fc92000000001](https://www.xiaohongshu.com/discovery/item/67d3fc92000000001b03d178?xsec_token=YB-2gnomoe8TvlKQTiwhBaeU4sAqjnEAZwdGFOeT25N6g%3D&xsec_source=app_share)

> 帖内提到的公司: 米哈游

> **内容快照**:
> 
> AI agent产品经理需要技术理解、懂用户、商业化思维和风险意识。技术理解包括掌握大模型技术边界（如token限制和幻觉问题）和熟悉LangChain等开发工具；懂用户包括人机协作心理和对话设计策略；商业化思维包括算力成本控制和竞品对标；风险意识包括合规设计和失效预案。
> 
> 米哈游2025年校招有Agent产品经理/云技术产品经理岗位，主要负责云游戏运营相关的产品化建设和迭代。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 做AI agent所需要的能力模型是酱⬇️：技术理解：1️⃣掌握大模型技术边界，如：token限制和幻觉问题。2️⃣熟悉类似LangChain的开发工具，至少能和研发上桌讨论技术方案。懂用户：1️⃣人机协作心理：比如，拟人化程度接受度（情感型用户需要更高拟真度）。2️⃣对话设计的策略：信息密度、容错提示、个性化表达（如Z世代用户偏好emoji辅助沟通）。商业化思维：1️⃣算力成本控制：评估模型推理成本（如GPT-4每千 token 0.03美元）与商业回报的平衡点。2️⃣竞品对标：分析C端竞品（如ChatGPT、Claude）与B端竞品（如微软Copilot）。风险意识：1️⃣合规设计：内容安全（防止生成违法信息）、可解释性（医疗Agent需提供决策依据）。2️⃣失效预案：设置人工接管流程、fallback话术（如“这个问题我需要更多时间思考”）。
> - 这个岗位在内部既可以叫“Agent产品经理”也会叫“云技术产品经理”。是今年米哈游的校招岗位之一，主要负责云游戏运营相关的产品化建设和迭代

**[Agent工程师]** (relevance=0.30) — [https://www.xiaohongshu.com/discovery/item/697c4ad2000000000](https://www.xiaohongshu.com/discovery/item/697c4ad2000000000c0353d8?xsec_token=YBuDmvXxcuij8fN_uhBQhpPbLvlTR2wGDSZoypG9xxuXM%3D&xsec_source=app_share)

> 帖内提到的公司: 阿里淘天, 美团, 百度, 小米, 米哈游, taptap

> **内容快照**:
> 
> 面试中大部分还是围绕项目进行深挖提问，以及相关的八股，能和面试官聊起来一般就问题不大，手撕也不是很难，面试官也会提示。
> 
> 0论文0实习，华五本硕，27届，第一段日常实习入职阿里淘天ai agent岗。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 面试中大部分还是围绕项目进行深挖提问，以及相关的八股，能和面试官聊起来一般就问题不大，手撕也不是很难，面试官也会提示。
> - bg 27届华五本硕 0论文0实习 第一段日常入职阿里淘天ai agent岗

---

### 61. 红杉中国

- **tier**: 头部VC
- **must_have in**: PE投后VC行研 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: AI 应用层, TMT, 消费
- **source 标签**: common_knowledge:头部VC
- **notes**:
  - [PE投后VC行研] 按行业共识,VC 头部

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 62. 联合资信

- **tier**: 信用评级机构
- **must_have in**: 信用研究员 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: 城投, 金融
- **source 标签**: common_knowledge:头部信用评级
- **notes**:
  - [信用研究员] 按行业共识,头部信评

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 63. 融通基金

- **tier**: 二线公募
- **must_have in**: 资管FOF (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: 金融
- **source 标签**: taxonomy_doc
- **notes**:
  - [资管FOF] FOF 老牌玩家

#### XHS 帖证据 (1 条)

**[固收+多资产]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69f57a85000000002](https://www.xiaohongshu.com/discovery/item/69f57a850000000022025d27?xsec_token=YB5End22irg_cTWO62zbIg28WJPxxBjMfNYWtpC5cz-_U%3D&xsec_source=app_share)

> 帖内提到的公司: 融通基金

> **内容快照**:
> 
> 面试融通基金时，回答公司了解应具体到FOF先行者、多元资产配置、固收+和权益+战略等，而非泛泛而谈。
> 
> 市场波动时向客户解释产品表现应遵循流程：分析波动原因、对标同类、结合策略、展示长期业绩、提供应对策略、强调资产配置、持续跟进。
> 
> 投研岗位需要宏观经济周期判断、行业趋势分析、公司基本面研究、财务模型构建、风险收益量化评估、独立思考与逆向投资勇气等专业能力。
> 
> 投资观点与团队不一致时，应整理数据逻辑、在投研会上表达、倾听反馈、寻找共识、提出可验证指标、跟踪验证、总结经验。
> 
> 提高投研报告价值应锁定核心问题、深入一手调研、建立独特分析框架、形成清晰投资逻辑、提出具体标的与估值、设定触发条件与止损点、数据可视化。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 国内最早成立的基金管理公司之一→FOF先行者与多元资产配置专家→全方位投研体系与风控机制→主动管理能力见长→"固收+"和"权益+"战略布局→科技赋能的投资管理平台
> - 先分析具体波动原因与市场环境→对标同类产品相对表现→结合产品策略与风险收益特征解释→展示长期业绩与历史类似行情对比→提供专业判断与应对策略→强调资产配置重要性→持续跟进沟通安抚情绪
> - 宏观经济周期的判断能力、行业趋势与竞争格局分析能力、公司基本面深度研究能力、财务模型构建与估值能力、风险收益比的量化评估能力、独立思考与逆向投资的勇气

---

### 64. 贝莱德

- **tier**: 外资行
- **must_have in**: 利率宏观策略 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: 金融
- **source 标签**: xhs:利率宏观策略:2
- **notes**:
  - [利率宏观策略] 外资固收策略

#### XHS 帖证据 (2 条)

**[利率宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/692fd7e0000000001](https://www.xiaohongshu.com/discovery/item/692fd7e0000000001b021334?xsec_token=YBZvF1WHadYcBM7UdDHSlhOLcXb91OQdyECCpollRvJ5M%3D&xsec_source=app_share)

> 帖内提到的公司: 贝莱德

> **内容快照**:
> 
> 贝莱德2026年全球投资展望，核心判断包括短期宏观波动、中期AI持续亮点、长期资产定价体系重塑。
> 
> AI时代投资主线：算力×能力×电力，包括半导体、数据中心、电力系统。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 一、2026 核心判断
1. 短期：宏观更易波动
2. 中期：AI 是持续亮点，但节奏更温和
3. 长期：资产定价体系被重塑
> - AI 时代真正决定胜负的，是“算力 × 能力 × 电力”。

**[利率宏观策略]** (relevance=0.30) — [https://www.xiaohongshu.com/discovery/item/69329c12000000000](https://www.xiaohongshu.com/discovery/item/69329c12000000000d039884?xsec_token=YBgBjgzADyhN4b2tkRg5EIfoLRLu5K8Trh772BVt5qAJw%3D&xsec_source=app_share)

> 帖内提到的公司: 摩根大通, 贝莱德

> **内容快照**:
> 
> 摩根大通2026年全球投资展望，强调资产配置回到正确位置，债券要配但需聪明配，股票提高美国以外权重，AI投资主线从创新者向采用者扩散。
> 
> AI投资主线从创新者向采用者扩散，涉及工业、公用事业、医疗金融等行业。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 2026 资产配置：回到正确位置 (“Get Back Onside”)
> - AI 投资主线从“创新者”→“采用者”扩散

---

### 65. 量派投资

- **tier**: 中型量化私募
- **must_have in**: 量化开发QD (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: —
- **source 标签**: taxonomy_doc
- **notes**:
  - [量化开发QD] QD 高薪 25-40K·15薪

#### XHS 帖证据 (3 条)

**[量化因子工程师]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a0c2659000000003](https://www.xiaohongshu.com/discovery/item/6a0c2659000000003501c0b8?xsec_token=YBWo3_04eqG7GfzDfPD8xw2IDqvAm1GxyL7BT86NKKem8%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 衍复, 灵均, 世纪前沿

> **内容快照**:
> 
> 幻方、九坤、明汯、衍复是量化“四大天王”出海主力，规模700-800亿，香港办公室持续扩招，提供签证担保和外派补贴。
> 
> 灵均2025年以73.51%收益斩获百亿量化业绩冠军，世纪前沿规模跃升至500-600亿，两家香港团队扩张期，对因子挖掘、建模能力强的同学友好。
> 
> 黑翼2025年新获香港9号牌，量派2024年拿下4+9号双牌照，规模突破300亿，入行门槛相对友好。
> 
> 港圈量化求职门槛：名校硕博，数理/计算机/金工背景优先，英文流利是标配。
> 
> 港圈量化优势：行业顶薪+外派补贴+签证担保，国际化投研平台，职业天花板更高。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 幻方 / 九坤 / 明汯 / 衍复：量化“四大天王”出海主力，规模普遍在700-800亿区间...香港办公室持续扩招。提供签证担保和外派补贴
> - 灵均 / 世纪前沿：2025年灵均以73.51%收益斩获百亿量化业绩冠军...世纪前沿规模跃升至500-600亿...两家香港团队均处于扩张期，对因子挖掘、建模能力强的同学非常友好
> - 黑翼 / 量派：黑翼2025年新获香港9号牌...量派2024年拿下4+9号双牌照，2025年规模已突破300亿...入行门槛相对友好

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d521fa000000002](https://www.xiaohongshu.com/discovery/item/69d521fa000000002103bbb9?xsec_token=YB6sAJJmJihTG8Su1WQpcg-UJB_8yB1hfhb5O1gYnWiVU%3D&xsec_source=app_share)

> 帖内提到的公司: 量派投资

> **内容快照**:
> 
> 量派投资校招笔试分为Quant Test（策略岗）和Code Test（开发岗），核心考察数理、编程和金融量化能力，无统一教材，极度侧重实操与逻辑，不考英语。
> 
> 量派投资是一家顶级量化私募，校招笔试有明确的岗位区分和考察重点。
> 
> 备考计划建议：2周夯实数理基础与Python编程，刷LeetCode中等题；1-2周专项突破，策略岗练习因子挖掘与回测框架，开发岗强化数据结构和系统设计；最后1周全真模拟。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 量派投资作为量化私募（企业类型：其他/金融机构），其校招笔试核心是线上机考，时长90-120分钟，分岗位进行：Quant Test（策略岗）和Code Test（开发岗）。核心考察数理、编程和金融量化三大能力，无统一教材，极度侧重实操与逻辑，不考英语（信息明确）。
> - 想冲26量派投资校招的宝子们集合！面对这家顶级量化私募的笔试题库
> - 备考计划分三步走：第一步用2周夯实数理基础与Python编程，刷LeetCode中等题；第二步用1-2周专项突破，策略岗重点练习因子挖掘与回测框架，开发岗强化数据结构和系统设计题；最后1周全真模拟，严格计时完成各岗位珍题套卷，适应机考节奏。

**[量化开发QD]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0429bd000000003](https://www.xiaohongshu.com/discovery/item/6a0429bd0000000036031f02?xsec_token=YBDDr9lAXvwHkmg1OwIGLq7EkqBJrrqQBTnHUHfIBIKSk%3D&xsec_source=app_share)

> 帖内提到的公司: 九坤, 灵均, 凯丰, 量派投资

> **内容快照**:
> 
> 头部量化私募如九坤、灵均等广泛招聘量化交易开发工程师（C++）、量化策略研究员等岗位，聚焦股票、期货期权和CTA策略。
> 
> 头部量化私募采用利润分成模式，如九坤按投资团队业绩给予PNL分红，优秀策略人员年收入远超基本薪酬。
> 
> 国内头部量化薪酬已赶超国际，工程和研究岗位税前年薪通常50-100万人民币以上，核心人才收入可达数百万元级。
> 
> 量派投资2020年成立，2024年2月管理规模达180亿元，策略扩展至指数增强、中性、CTA、量化多头等领域。
> 
> 2024年初A股剧烈调整导致量化产品1月平均回撤约7.2%，部分百亿私募净值跌破预警线，规模、业绩与回撤的平衡三角考验风控。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 头部机构过去半年广泛招聘量化交易开发工程师（C++）、量化策略研究员和模型开发等核心岗位，聚焦股票、期货期权和CTA策略。
> - 部分公司采用利润分成模式：如九坤等按投资团队业绩给予PNL分红，使优秀策略人员年收入远超基本薪酬。
> - 国内头部量化薪酬已赶超国际：有创始人透露，过去2–3年他们给出的薪资高于美国顶尖公司。

---

### 66. 高瓴资本

- **tier**: 头部PE
- **must_have in**: PE投后VC行研 (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: TMT, 医药, 消费
- **source 标签**: demo_v1, saif:2025, taxonomy_doc
- **notes**:
  - [PE投后VC行研] 国内 PE 头部

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2025 | 高瓴资本 | 行业研究员 | 1 | 私募 |

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 67. 高盛

- **tier**: 外资行
- **must_have in**: 投行 IBD (1 sub_cat)
- **非 must_have (备选) in**: — (0)
- **industry_focus**: TMT, 金融
- **source 标签**: common_knowledge:头部外资投行
- **notes**:
  - [投行 IBD] 按行业共识,顶尖外资投行

#### XHS 帖证据 (3 条)

**[买方 Quant]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/695940c8000000001](https://www.xiaohongshu.com/discovery/item/695940c8000000001e03a19c?xsec_token=YBrJ_goExM-LGFpD_KXswc_GrNMq5jKropLNK56upboAU%3D&xsec_source=app_share)

> 帖内提到的公司: 高盛, 摩根士丹利, 中金, 中信里昂, 幻方, 灵均

> **内容快照**:
> 
> 大湾区量化岗位分为卖方Quant（投行）和买方Quant（基金/私募），卖方Quant集中在香港，买方Quant在深圳更活跃。
> 
> 香港的卖方Quant主要集中在国际投行（高盛、摩根士丹利等）和中资投行国际子公司（中金、中信里昂），深圳的卖方机会在国内券商的金融工程/量化自营部门。
> 
> 深圳的买方Quant核心是顶尖量化私募（幻方、灵均等），香港的买方Quant包括全球顶级对冲基金和自营交易公司（Citadel, Two Sigma, Optiver等）。
> 
> 深圳的量化岗位面试必考对国内金融数据源（Wind, Tushare, JoinQuant）和A股交易规则的熟悉度。
> 
> 香港的量化岗位面试对期权定价、随机微积分等理论要求更深。
> 
> 深圳偏好国内顶尖理工院校（清北复交、浙大、中科大等）的硕士/博士，海外名校需对国内市场有理解；香港偏好全球顶级名校（美英顶尖高校、新加坡两所、港三所），专业排名比学校综合排名更重要。
> 
> 纯金融背景竞争力弱，数学、物理、计算机、电子工程等硬核专业是绝对主流。
> 
> 大湾区量化岗位技能要求：Python、SQL、Linux是基础；深圳需精通C++，香港需英语工作能力和kdb+/q等工具。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 在大湾区，两者的重心和机会有显著差异：1. 卖方Quant（以投行为主）：香港是绝对中心...2. 买方Quant（以基金/私募为主）：深圳是核心战场...
> - 国际投行（高盛、摩根士丹利等）及中资投行的国际子公司（中金、中信里昂等）的量化团队主要聚集于香港。
> - 深圳是核心战场：聚集了全国最顶尖、最活跃的量化私募（幻方、灵均等）...香港是国际桥头堡：云集了全球顶级对冲基金和自营交易公司（Citadel, Two Sigma, Optiver等）

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/696e0157000000000](https://www.xiaohongshu.com/discovery/item/696e0157000000000b00aa49?xsec_token=YBLzx7ZossRnL_aAxZjlYx2SzHExIvcl7Ifjrej0KQEMY%3D&xsec_source=app_share)

> 帖内提到的公司: Jane Street, HRT, Optiver, Virtu, DRW, Tower Research

> **内容快照**:
> 
> Quant公司可按交易频率和团队结构分为四类：高频协作（如Jane Street, HRT, Optiver）、高频个体化（如Virtu, DRW, Tower Research）、低频协作（如RenTec, QRT）、低频个体化（如Millennium, Citadel, BAM）。
> 
> 不同分类对应不同技能树：高频公司注重编程、算法设计、系统架构和低延迟优化，C++和硬件知识关键；低频公司更看重统计建模、机器学习和基本面分析，Python和R常用。
> 
> 团队文化影响技能：协作型需要善于沟通和团队合作；个体型要求高度自驱和独立解决问题能力。
> 
> Quant公司分类包括高频做市商、自营交易公司、系统化对冲基金、多策略对冲基金等。
> 
> 学员拿到Brevan Howard、Optiver的Quant Trading Offer，以及JPM、Citi、高盛的Quant岗。

> **verbatim 锚点 (T1/T3 抽取)**:
> - Jane Street、HRT、Optiver属于高频协作类...Virtu、DRW、Tower Research则是高频但更个体化...RenTec、QRT这类是协作式系统化投资...Millennium、Citadel的pod结构或BAM这类，是低频且高度siloed
> - 高频公司，技能重点在编程、算法设计、系统架构和低延迟优化，C++和硬件知识往往是关键。低频公司则更看重统计建模、机器学习和基本面分析能力，Python和R用得多
> - 协作型需要你善于沟通和团队合作...个体型则要求高度自驱和独立解决问题能力

**[量化研究员·高频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a15a138000000003](https://www.xiaohongshu.com/discovery/item/6a15a138000000003501dd25?xsec_token=YBJXceSEhkLQc7puTGKMxN_p_R9jpYHzgNTvXgnWHFQ5c%3D&xsec_source=app_share)

> 帖内提到的公司: Citadel, Jane Street, Two Sigma, Optiver, IMC, SIG

> **内容快照**:
> 
> 量化行业机构梯队分为顶级买方（Citadel、Jane Street、Two Sigma）、一线做市商（Optiver、IMC等）、知名对冲基金（Balyasny、Bridgewater等）、成长型量化机构（DRW、Schonfeld等）、卖方&资管（高盛、BlackRock等）和加密量化（Jump Crypto等）。
> 
> 初级岗位薪资参考：顶级买方entry级可达$300k+，不同机构薪资差异大。
> 
> 不同梯队机构考察重点不同：顶级买方和做市商更看重算法题、数学推导和工程实现；资管岗更偏向因子建模和业务理解。
> 
> 低年级可以参加IMC、Optiver的交易赛积累项目经历。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 买方（God Tier）以 Citadel、Jane Street、Two Sigma 为代表...一线做市商包括 Optiver、IMC、SIG、HRT、Jump Trading 等...知名对冲基金比如 Balyasny、Bridgewater、D.E. Shaw 等...成长型量化机构以 DRW、Schonfeld、Tower Research 为代表...卖方 & 资管量化岗投行（高盛、摩根士丹利、小摩等）和资管巨头（BlackRock、Vanguard、State Street 等）...加密量化赛道还有 Jump Crypto、Wintermute、GSR 等
> - Citadel 的 entry 级岗位可达 $300k+
> - 顶级买方和做市商更看重算法题、数学推导和工程实现，资管岗则更偏向因子建模和业务理解。

---

### 68. 兴证全球基金

- **tier**: 一线公募
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 公募权益研究员, 资管FOF (2)
- **industry_focus**: 周期, 消费, 金融
- **source 标签**: common_knowledge:头部公募, saif:2024
- **notes**:
  - [公募权益研究员] SAIF 2024 行业研究员命中
  - [资管FOF] 按行业共识

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 兴证全球基金管理有限公司 | 行业研究员 | 1 | 公募基金 |

#### XHS 帖证据 (1 条)

**[资管FOF]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68076825000000001](https://www.xiaohongshu.com/discovery/item/68076825000000001a0066db?xsec_token=YB99eH8k09Rv7rNLHjW60O0BTN6QzTKurNuAdNZ06-eic%3D&xsec_source=app_share)

> 帖内提到的公司: 交银施罗德基金, 兴证全球基金, 民生加银基金, 汇添富基金, 南方基金, 浦银安盛基金

> **内容快照**:
> 
> FOF行业规模从2021年的2253亿降至2024年底的1442亿，降幅36%，多家公司规模大幅缩水。
> 
> 交银施罗德基金FOF团队仅剩2名基金经理，规模排名从第一跌至第七。
> 
> 兴证全球基金FOF团队以林国怀为带头人，成员背景多元，包括互联网大厂和海外金融背景。
> 
> 易方达基金FOF团队由汪玲牵头，成员如刘淑霞有券商资管FOF业务负责人经验。
> 
> 中欧基金FOF团队由桑磊牵头，成员有险资投资管理经验。
> 
> 华夏基金FOF团队汇聚了许利民、廉赵峰、李晓易、卢少强等精兵强将。
> 
> 工银瑞信FOF团队赵志源接替蒋华安成为FOF投资部总经理并进入投委会，陈涵任研究副总监。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 截至2024年底，共有87家基金公司管理着511只FOF产品，资产净值规模合计1442亿元，相比2021年的2253亿降幅36%。
> - 交银施罗德FOF团队则仅见2人：刘兵，经济学博士，2016年加入交银施罗德基金；刘迪，金融工程与投资管理博士，2015年加入交银施罗德基金。
> - 兴证全球基金以公司总经理助理、FOF投资与金融工程部总监、养老金管理部总监林国怀为带头人，团队成员既有来自互联网大厂的成员，也有来自海外金融从业背景的成员。

---

### 69. 汇添富基金

- **tier**: 一线公募
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 公募权益研究员, 公募基金中后台 (2)
- **industry_focus**: 医药, 消费, 金融
- **source 标签**: common_knowledge:头部公募, taxonomy_doc
- **notes**:
  - [公募权益研究员] 按行业共识,消费医药条线知名
  - [公募基金中后台] 按行业共识

#### XHS 帖证据 (5 条)

**[量化研究员·中频]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a0f1f52000000003](https://www.xiaohongshu.com/discovery/item/6a0f1f52000000003700d9ab?xsec_token=YBN2X1RuqB4DDPgcukhFoKeu5T216dC63UAnGIN3ep7CQ%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达基金, 南方基金, 汇添富基金, 华夏基金, 华泰证券, 中信证券

> **内容快照**:
> 
> 易方达基金投研岗笔试挂，行测+英语，70+分数没过，说明投研量化竞争激烈。
> 
> 南方基金指数研究员一面为无领导小组讨论，题目方向未知导致挂。
> 
> 招卡数据分析一面为对抗小游戏，形式有趣。
> 
> yn资产量化研究员期权方向进展到二面hr面，有希望。
> 
> wy资产量化研究员笔试通过但后续流程未定。
> 
> mx投资量化研究员笔试后无消息。
> 
> 作者背景：华五金工本+金融硕，偏量化/研究赛道，3段相关实习（某百亿私募+三中一华投研）。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 易方达基金 投研岗（4.18笔试挂 行测+英语） 70+分数也没过，只能说投研量化太卷了
> - 南方基金 指数研究员（4.29笔试 行测 5.10一面挂）一面无领导小组题目问了完全不知道的方向，遂阵亡
> - 招卡 数据分析（5.17笔试 行测+英语+性格测试+雷霆服从性测试题目 5.18一面）一面是对抗小游戏挺有意思

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[公募权益研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69cfc9fd000000002](https://www.xiaohongshu.com/discovery/item/69cfc9fd000000002301faf9?xsec_token=YBLFBOwwww_YoKS27jWCHctEONxIy8MkOa74dNilAm48s%3D&xsec_source=app_share)

> 帖内提到的公司: 汇添富基金

> **内容快照**:
> 
> 汇添富基金行业研究岗面试问题包括：为什么想做买方研究而非卖方、如何说服基金经理、草根调研方法、未盈利科技公司估值、持续跟踪股票、行业配置与个股选择、景气度与价值投资、当前看好细分行业、平衡深度与广度。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 1. 你为什么想加入公募基金做研究，而不是券商研究所？
2. 买方研究和卖方研究，你更倾向于哪一种，为什么？
3. 如果你看好的股票，基金经理并不认可，你会如何说服他？
4. 在研究一家消费类公司时，除了看财报，你会通过哪些“草根调研”来验证你的判断？
5. 如何给一家尚未盈利的科技公司进行估值？
6. 你有没有持续跟踪过一只股票，并定期记录你的观点和逻辑变化？
7. 在构建投资组合时，行业配置和个股选择，你觉得哪个更重要？
8. 你对“景气度投资”和“价值投资”这两种方法论有什么看法？
9. 当前市场下，你最看好哪个细分行业，逻辑是什么？
10. 在基金公司做研究，压力很大，你如何平衡深度和覆盖广度？

**[行业研究员·消费]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68523924000000002](https://www.xiaohongshu.com/discovery/item/685239240000000022028983?xsec_token=YB1tOVHt4MrRCgE3YRmfKUfzkX4Zhwklu8QU9qotk8kHY%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达, 华夏, 博时, 国泰, 汇添富, 南方

> **内容快照**:
> 
> 易方达、华夏是头部公募，整体待遇好，科技岗位应届生薪资尤其高。
> 
> 博时、国泰、汇添富、南方类似公务员氛围。
> 
> 银行系公募（招商、中银、工银）薪资相对固化，待遇提升空间有限，但工作相对安逸。
> 
> 永赢、嘉实、鹏华待遇不错，但工作强度卷王级别。
> 
> 兴全待遇不错，人少资源多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 易方达、华夏：头部中的头部，整体待遇不会太差，据说科技岗位应届生薪资对比其他应届会尤其高一些
> - 博时、国泰、汇添富、南方：据说类似公务员氛围浓厚
> - 银行系包括（招商、中银、工银等）薪资相对固化，待遇可提升空间对比其他就不太行了，安逸也是相对的吧

**[资管FOF]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68076825000000001](https://www.xiaohongshu.com/discovery/item/68076825000000001a0066db?xsec_token=YB99eH8k09Rv7rNLHjW60O0BTN6QzTKurNuAdNZ06-eic%3D&xsec_source=app_share)

> 帖内提到的公司: 交银施罗德基金, 兴证全球基金, 民生加银基金, 汇添富基金, 南方基金, 浦银安盛基金

> **内容快照**:
> 
> FOF行业规模从2021年的2253亿降至2024年底的1442亿，降幅36%，多家公司规模大幅缩水。
> 
> 交银施罗德基金FOF团队仅剩2名基金经理，规模排名从第一跌至第七。
> 
> 兴证全球基金FOF团队以林国怀为带头人，成员背景多元，包括互联网大厂和海外金融背景。
> 
> 易方达基金FOF团队由汪玲牵头，成员如刘淑霞有券商资管FOF业务负责人经验。
> 
> 中欧基金FOF团队由桑磊牵头，成员有险资投资管理经验。
> 
> 华夏基金FOF团队汇聚了许利民、廉赵峰、李晓易、卢少强等精兵强将。
> 
> 工银瑞信FOF团队赵志源接替蒋华安成为FOF投资部总经理并进入投委会，陈涵任研究副总监。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 截至2024年底，共有87家基金公司管理着511只FOF产品，资产净值规模合计1442亿元，相比2021年的2253亿降幅36%。
> - 交银施罗德FOF团队则仅见2人：刘兵，经济学博士，2016年加入交银施罗德基金；刘迪，金融工程与投资管理博士，2015年加入交银施罗德基金。
> - 兴证全球基金以公司总经理助理、FOF投资与金融工程部总监、养老金管理部总监林国怀为带头人，团队成员既有来自互联网大厂的成员，也有来自海外金融从业背景的成员。

---

### 70. Bank of America

- **tier**: 外资行
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 投行 IBD (1)
- **industry_focus**: 金融
- **source 标签**: saif:2025
- **notes**:
  - [投行 IBD] SAIF 2025 命中

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2025 | Bank of America | 行业研究员 | 1 | 私募 |

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 71. DRW

- **tier**: 衍生品做市商
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 量化研究员·高频 (1)
- **industry_focus**: —
- **source 标签**: xhs:量化研究员·高频:2
- **notes**:
  - [量化研究员·高频] 芝加哥做市商

#### XHS 帖证据 (4 条)

**[量化研究员·高频]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6880a9d5000000001](https://www.xiaohongshu.com/discovery/item/6880a9d50000000010011ba0?xsec_token=YBd9faHjVDkkQSHFf23cH7LLya_pA4wf0Drwhyk37lwAc%3D&xsec_source=app_share)

> 帖内提到的公司: Optiver, DRW, SIG, Akuna Capital

> **内容快照**:
> 
> 面试中考察了期货次高频策略的基本概念，包括tick size、换月逻辑、期货贴水、CTAs以及基差波动对alpha decay的影响。
> 
> Quant Trading Intern岗位需要熟悉期货次高频策略，包括midprice做市、库存控制、延迟执行下的报价优化。
> 
> Optiver、DRW、SIG、Akuna等HFT/Quant firm对期货次高频策略有较高要求。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 不知道tick size、换月逻辑、期货贴水、CTAs这些基本概念
> - Quant Trading Intern
> - Optiver / DRW / SIG / Akuna 这一类 firm

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/696e0157000000000](https://www.xiaohongshu.com/discovery/item/696e0157000000000b00aa49?xsec_token=YBLzx7ZossRnL_aAxZjlYx2SzHExIvcl7Ifjrej0KQEMY%3D&xsec_source=app_share)

> 帖内提到的公司: Jane Street, HRT, Optiver, Virtu, DRW, Tower Research

> **内容快照**:
> 
> Quant公司可按交易频率和团队结构分为四类：高频协作（如Jane Street, HRT, Optiver）、高频个体化（如Virtu, DRW, Tower Research）、低频协作（如RenTec, QRT）、低频个体化（如Millennium, Citadel, BAM）。
> 
> 不同分类对应不同技能树：高频公司注重编程、算法设计、系统架构和低延迟优化，C++和硬件知识关键；低频公司更看重统计建模、机器学习和基本面分析，Python和R常用。
> 
> 团队文化影响技能：协作型需要善于沟通和团队合作；个体型要求高度自驱和独立解决问题能力。
> 
> Quant公司分类包括高频做市商、自营交易公司、系统化对冲基金、多策略对冲基金等。
> 
> 学员拿到Brevan Howard、Optiver的Quant Trading Offer，以及JPM、Citi、高盛的Quant岗。

> **verbatim 锚点 (T1/T3 抽取)**:
> - Jane Street、HRT、Optiver属于高频协作类...Virtu、DRW、Tower Research则是高频但更个体化...RenTec、QRT这类是协作式系统化投资...Millennium、Citadel的pod结构或BAM这类，是低频且高度siloed
> - 高频公司，技能重点在编程、算法设计、系统架构和低延迟优化，C++和硬件知识往往是关键。低频公司则更看重统计建模、机器学习和基本面分析能力，Python和R用得多
> - 协作型需要你善于沟通和团队合作...个体型则要求高度自驱和独立解决问题能力

**[量化研究员·高频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a15a138000000003](https://www.xiaohongshu.com/discovery/item/6a15a138000000003501dd25?xsec_token=YBJXceSEhkLQc7puTGKMxN_p_R9jpYHzgNTvXgnWHFQ5c%3D&xsec_source=app_share)

> 帖内提到的公司: Citadel, Jane Street, Two Sigma, Optiver, IMC, SIG

> **内容快照**:
> 
> 量化行业机构梯队分为顶级买方（Citadel、Jane Street、Two Sigma）、一线做市商（Optiver、IMC等）、知名对冲基金（Balyasny、Bridgewater等）、成长型量化机构（DRW、Schonfeld等）、卖方&资管（高盛、BlackRock等）和加密量化（Jump Crypto等）。
> 
> 初级岗位薪资参考：顶级买方entry级可达$300k+，不同机构薪资差异大。
> 
> 不同梯队机构考察重点不同：顶级买方和做市商更看重算法题、数学推导和工程实现；资管岗更偏向因子建模和业务理解。
> 
> 低年级可以参加IMC、Optiver的交易赛积累项目经历。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 买方（God Tier）以 Citadel、Jane Street、Two Sigma 为代表...一线做市商包括 Optiver、IMC、SIG、HRT、Jump Trading 等...知名对冲基金比如 Balyasny、Bridgewater、D.E. Shaw 等...成长型量化机构以 DRW、Schonfeld、Tower Research 为代表...卖方 & 资管量化岗投行（高盛、摩根士丹利、小摩等）和资管巨头（BlackRock、Vanguard、State Street 等）...加密量化赛道还有 Jump Crypto、Wintermute、GSR 等
> - Citadel 的 entry 级岗位可达 $300k+
> - 顶级买方和做市商更看重算法题、数学推导和工程实现，资管岗则更偏向因子建模和业务理解。

---

### 72. IMC

- **tier**: 衍生品做市商
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 量化研究员·高频 (1)
- **industry_focus**: —
- **source 标签**: xhs:量化研究员·高频:2
- **notes**:
  - [量化研究员·高频] 荷兰做市商

#### XHS 帖证据 (2 条)

**[量化研究员·高频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68a1ec59000000001](https://www.xiaohongshu.com/discovery/item/68a1ec59000000001c03f9f8?xsec_token=YB5Ulu1WhUNtw4vWAtrIxUoOacwIr42grgPnEysfGZPCQ%3D&xsec_source=app_share)

> 帖内提到的公司: Optiver, IMC, AQR

> **内容快照**:
> 
> Optiver的Quantitative Trader Intern和Quantitative Research Intern岗位已开放2026年暑期实习申请。
> 
> Optiver的面试流程包括OA（80 in 8心算、Zap-N、NumberLogic、Beat the Odds）、HR面、技术面和BQ面，技术面涉及做市、费米问题和心算。
> 
> Optiver的期权做市是天花板级别，交易桌文化aggressive，喜欢self-driven、敢拍板的人。
> 
> Optiver给new grad QT的待遇约400k+（含signing）。

> **verbatim 锚点 (T1/T3 抽取)**:
> - Optiver 26 Summer ，给intern开8w刀！
> - 流程很套路：OA → HR → Tech → BQ，但每一步都掉血。
> - Optiver 的交易桌文化就是 aggressive，喜欢 self-driven、敢拍板的人。

**[量化研究员·高频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a15a138000000003](https://www.xiaohongshu.com/discovery/item/6a15a138000000003501dd25?xsec_token=YBJXceSEhkLQc7puTGKMxN_p_R9jpYHzgNTvXgnWHFQ5c%3D&xsec_source=app_share)

> 帖内提到的公司: Citadel, Jane Street, Two Sigma, Optiver, IMC, SIG

> **内容快照**:
> 
> 量化行业机构梯队分为顶级买方（Citadel、Jane Street、Two Sigma）、一线做市商（Optiver、IMC等）、知名对冲基金（Balyasny、Bridgewater等）、成长型量化机构（DRW、Schonfeld等）、卖方&资管（高盛、BlackRock等）和加密量化（Jump Crypto等）。
> 
> 初级岗位薪资参考：顶级买方entry级可达$300k+，不同机构薪资差异大。
> 
> 不同梯队机构考察重点不同：顶级买方和做市商更看重算法题、数学推导和工程实现；资管岗更偏向因子建模和业务理解。
> 
> 低年级可以参加IMC、Optiver的交易赛积累项目经历。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 买方（God Tier）以 Citadel、Jane Street、Two Sigma 为代表...一线做市商包括 Optiver、IMC、SIG、HRT、Jump Trading 等...知名对冲基金比如 Balyasny、Bridgewater、D.E. Shaw 等...成长型量化机构以 DRW、Schonfeld、Tower Research 为代表...卖方 & 资管量化岗投行（高盛、摩根士丹利、小摩等）和资管巨头（BlackRock、Vanguard、State Street 等）...加密量化赛道还有 Jump Crypto、Wintermute、GSR 等
> - Citadel 的 entry 级岗位可达 $300k+
> - 顶级买方和做市商更看重算法题、数学推导和工程实现，资管岗则更偏向因子建模和业务理解。

---

### 73. MiniMax

- **tier**: 大模型独角兽
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: LLM算法post-train (1)
- **industry_focus**: AI 基础设施
- **source 标签**: taxonomy_doc
- **notes**:
  - [LLM算法post-train] 海螺 AI

#### XHS 帖证据 (1 条)

**[多模态推理优化]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a05e199000000000](https://www.xiaohongshu.com/discovery/item/6a05e199000000000603777c?xsec_token=YBSoRGoLnXgYWkamAVP-9gF7DimedlFbioD1lHciA1bc4%3D&xsec_source=app_share)

> 帖内提到的公司: OpenAI, Anthropic, Google, xAI, 阿里, DeepSeek

> **内容快照**:
> 
> 2026年4月全球大模型公司能力梯队全景图，T1到T5，涵盖OpenAI、Anthropic、Google、xAI、阿里、DeepSeek、Meta、智谱AI等公司。
> 
> T1梯队估值到1万亿级别，工业级Agent闭环、GPQA推理准确率超94%、代码生成率超85%。
> 
> T2梯队多模态与逻辑推理、代码生成率TOP 5、开源生态标杆。
> 
> T3梯队垂直行业分析、端侧部署、行业级多模态。
> 
> T4梯队政企流式推理、私有化部署、端云协同。
> 
> T5梯队细分场景、端侧部署、开源社区。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 2026年4月全球大模型公司能力梯队全景图，T1到T5，密密麻麻几十家公司。
> - 估值到1万亿级别，工业级Agent闭环、GPQA推理准确率超94%、代码生成率超85%。
> - 多模态与逻辑推理、代码生成率TOP 5、开源生态标杆。

---

### 74. NVIDIA

- **tier**: 外资行
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 多模态推理优化 (1)
- **industry_focus**: AI 基础设施
- **source 标签**: xhs:多模态推理优化:2
- **notes**:
  - [多模态推理优化] 推理硬件+优化

#### XHS 帖证据 (2 条)

**[多模态推理优化]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69ac3800000000002](https://www.xiaohongshu.com/discovery/item/69ac38000000000028009bd0?xsec_token=YBmXj5XVFgYSMuAZl_eAeu_ZK990jFtbEDVgKQTgo2__w%3D&xsec_source=app_share)

> 帖内提到的公司: 阿里云, NVIDIA

> **内容快照**:
> 
> ECHO 是一种面向高并发低延迟推理的投机采样方法，在低负载下实现最高5.35倍加速，在高并发吞吐测试中全面领先。

> **verbatim 锚点 (T1/T3 抽取)**:
> - ECHO提出了一套非常聪明的全局弹性架构...实现了最高5.35倍的加速

**[多模态推理优化]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a05e199000000000](https://www.xiaohongshu.com/discovery/item/6a05e199000000000603777c?xsec_token=YBSoRGoLnXgYWkamAVP-9gF7DimedlFbioD1lHciA1bc4%3D&xsec_source=app_share)

> 帖内提到的公司: OpenAI, Anthropic, Google, xAI, 阿里, DeepSeek

> **内容快照**:
> 
> 2026年4月全球大模型公司能力梯队全景图，T1到T5，涵盖OpenAI、Anthropic、Google、xAI、阿里、DeepSeek、Meta、智谱AI等公司。
> 
> T1梯队估值到1万亿级别，工业级Agent闭环、GPQA推理准确率超94%、代码生成率超85%。
> 
> T2梯队多模态与逻辑推理、代码生成率TOP 5、开源生态标杆。
> 
> T3梯队垂直行业分析、端侧部署、行业级多模态。
> 
> T4梯队政企流式推理、私有化部署、端云协同。
> 
> T5梯队细分场景、端侧部署、开源社区。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 2026年4月全球大模型公司能力梯队全景图，T1到T5，密密麻麻几十家公司。
> - 估值到1万亿级别，工业级Agent闭环、GPQA推理准确率超94%、代码生成率超85%。
> - 多模态与逻辑推理、代码生成率TOP 5、开源生态标杆。

---

### 75. SIG

- **tier**: 衍生品做市商
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 量化研究员·高频 (1)
- **industry_focus**: —
- **source 标签**: xhs:量化研究员·高频:2
- **notes**:
  - [量化研究员·高频] 费城做市商

#### XHS 帖证据 (4 条)

**[量化研究员·高频]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6880a9d5000000001](https://www.xiaohongshu.com/discovery/item/6880a9d50000000010011ba0?xsec_token=YBd9faHjVDkkQSHFf23cH7LLya_pA4wf0Drwhyk37lwAc%3D&xsec_source=app_share)

> 帖内提到的公司: Optiver, DRW, SIG, Akuna Capital

> **内容快照**:
> 
> 面试中考察了期货次高频策略的基本概念，包括tick size、换月逻辑、期货贴水、CTAs以及基差波动对alpha decay的影响。
> 
> Quant Trading Intern岗位需要熟悉期货次高频策略，包括midprice做市、库存控制、延迟执行下的报价优化。
> 
> Optiver、DRW、SIG、Akuna等HFT/Quant firm对期货次高频策略有较高要求。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 不知道tick size、换月逻辑、期货贴水、CTAs这些基本概念
> - Quant Trading Intern
> - Optiver / DRW / SIG / Akuna 这一类 firm

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69ef9583000000002](https://www.xiaohongshu.com/discovery/item/69ef958300000000230171b5?xsec_token=YBvSJ4xTAUDH8nq-0EDamJZ2cujQOd4qXyynO4pi4U5f8%3D&xsec_source=app_share)

> 帖内提到的公司: 九坤投资, SIG, Susquehanna

> **内容快照**:
> 
> 九坤投资和SIG的量化项目体验令人印象深刻，但缺乏睡眠和通勤辛苦。
> 
> 九坤AI推理挑战赛进入决赛，但最终未获奖。
> 
> SIG的discovery program-trading活动用心，管理层、技术、HR从澳洲/美国飞来。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 在九坤量化&SIG的周日和周一，十分令人印象深刻的两天！（也是极速缺乏睡眠+沪深港通勤的两天）
> - 去九坤是因为在九坤AI推理挑战赛很幸运进入了决赛 喜提往返上海机票酒店&在Office的一天。虽然最后抱憾而归哈哈哈
> - 去SIG则是参加discovery program-trading。氛围好好，活动办的超用心！许多管理层 技术 以及HR 都是从澳洲/美国专门飞过来的

**[量化研究员·高频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a15a138000000003](https://www.xiaohongshu.com/discovery/item/6a15a138000000003501dd25?xsec_token=YBJXceSEhkLQc7puTGKMxN_p_R9jpYHzgNTvXgnWHFQ5c%3D&xsec_source=app_share)

> 帖内提到的公司: Citadel, Jane Street, Two Sigma, Optiver, IMC, SIG

> **内容快照**:
> 
> 量化行业机构梯队分为顶级买方（Citadel、Jane Street、Two Sigma）、一线做市商（Optiver、IMC等）、知名对冲基金（Balyasny、Bridgewater等）、成长型量化机构（DRW、Schonfeld等）、卖方&资管（高盛、BlackRock等）和加密量化（Jump Crypto等）。
> 
> 初级岗位薪资参考：顶级买方entry级可达$300k+，不同机构薪资差异大。
> 
> 不同梯队机构考察重点不同：顶级买方和做市商更看重算法题、数学推导和工程实现；资管岗更偏向因子建模和业务理解。
> 
> 低年级可以参加IMC、Optiver的交易赛积累项目经历。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 买方（God Tier）以 Citadel、Jane Street、Two Sigma 为代表...一线做市商包括 Optiver、IMC、SIG、HRT、Jump Trading 等...知名对冲基金比如 Balyasny、Bridgewater、D.E. Shaw 等...成长型量化机构以 DRW、Schonfeld、Tower Research 为代表...卖方 & 资管量化岗投行（高盛、摩根士丹利、小摩等）和资管巨头（BlackRock、Vanguard、State Street 等）...加密量化赛道还有 Jump Crypto、Wintermute、GSR 等
> - Citadel 的 entry 级岗位可达 $300k+
> - 顶级买方和做市商更看重算法题、数学推导和工程实现，资管岗则更偏向因子建模和业务理解。

---

### 76. Tower Research

- **tier**: 衍生品做市商
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 量化研究员·高频 (1)
- **industry_focus**: —
- **source 标签**: taxonomy_doc
- **notes**:
  - [量化研究员·高频] 纽约高频做市商

#### XHS 帖证据 (2 条)

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/696e0157000000000](https://www.xiaohongshu.com/discovery/item/696e0157000000000b00aa49?xsec_token=YBLzx7ZossRnL_aAxZjlYx2SzHExIvcl7Ifjrej0KQEMY%3D&xsec_source=app_share)

> 帖内提到的公司: Jane Street, HRT, Optiver, Virtu, DRW, Tower Research

> **内容快照**:
> 
> Quant公司可按交易频率和团队结构分为四类：高频协作（如Jane Street, HRT, Optiver）、高频个体化（如Virtu, DRW, Tower Research）、低频协作（如RenTec, QRT）、低频个体化（如Millennium, Citadel, BAM）。
> 
> 不同分类对应不同技能树：高频公司注重编程、算法设计、系统架构和低延迟优化，C++和硬件知识关键；低频公司更看重统计建模、机器学习和基本面分析，Python和R常用。
> 
> 团队文化影响技能：协作型需要善于沟通和团队合作；个体型要求高度自驱和独立解决问题能力。
> 
> Quant公司分类包括高频做市商、自营交易公司、系统化对冲基金、多策略对冲基金等。
> 
> 学员拿到Brevan Howard、Optiver的Quant Trading Offer，以及JPM、Citi、高盛的Quant岗。

> **verbatim 锚点 (T1/T3 抽取)**:
> - Jane Street、HRT、Optiver属于高频协作类...Virtu、DRW、Tower Research则是高频但更个体化...RenTec、QRT这类是协作式系统化投资...Millennium、Citadel的pod结构或BAM这类，是低频且高度siloed
> - 高频公司，技能重点在编程、算法设计、系统架构和低延迟优化，C++和硬件知识往往是关键。低频公司则更看重统计建模、机器学习和基本面分析能力，Python和R用得多
> - 协作型需要你善于沟通和团队合作...个体型则要求高度自驱和独立解决问题能力

**[量化研究员·高频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a15a138000000003](https://www.xiaohongshu.com/discovery/item/6a15a138000000003501dd25?xsec_token=YBJXceSEhkLQc7puTGKMxN_p_R9jpYHzgNTvXgnWHFQ5c%3D&xsec_source=app_share)

> 帖内提到的公司: Citadel, Jane Street, Two Sigma, Optiver, IMC, SIG

> **内容快照**:
> 
> 量化行业机构梯队分为顶级买方（Citadel、Jane Street、Two Sigma）、一线做市商（Optiver、IMC等）、知名对冲基金（Balyasny、Bridgewater等）、成长型量化机构（DRW、Schonfeld等）、卖方&资管（高盛、BlackRock等）和加密量化（Jump Crypto等）。
> 
> 初级岗位薪资参考：顶级买方entry级可达$300k+，不同机构薪资差异大。
> 
> 不同梯队机构考察重点不同：顶级买方和做市商更看重算法题、数学推导和工程实现；资管岗更偏向因子建模和业务理解。
> 
> 低年级可以参加IMC、Optiver的交易赛积累项目经历。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 买方（God Tier）以 Citadel、Jane Street、Two Sigma 为代表...一线做市商包括 Optiver、IMC、SIG、HRT、Jump Trading 等...知名对冲基金比如 Balyasny、Bridgewater、D.E. Shaw 等...成长型量化机构以 DRW、Schonfeld、Tower Research 为代表...卖方 & 资管量化岗投行（高盛、摩根士丹利、小摩等）和资管巨头（BlackRock、Vanguard、State Street 等）...加密量化赛道还有 Jump Crypto、Wintermute、GSR 等
> - Citadel 的 entry 级岗位可达 $300k+
> - 顶级买方和做市商更看重算法题、数学推导和工程实现，资管岗则更偏向因子建模和业务理解。

---

### 77. Two Sigma

- **tier**: 外资行
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 买方 Quant (1)
- **industry_focus**: —
- **source 标签**: common_knowledge:头部对冲基金
- **notes**:
  - [买方 Quant] 按行业共识

#### XHS 帖证据 (2 条)

**[买方 Quant]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/695940c8000000001](https://www.xiaohongshu.com/discovery/item/695940c8000000001e03a19c?xsec_token=YBrJ_goExM-LGFpD_KXswc_GrNMq5jKropLNK56upboAU%3D&xsec_source=app_share)

> 帖内提到的公司: 高盛, 摩根士丹利, 中金, 中信里昂, 幻方, 灵均

> **内容快照**:
> 
> 大湾区量化岗位分为卖方Quant（投行）和买方Quant（基金/私募），卖方Quant集中在香港，买方Quant在深圳更活跃。
> 
> 香港的卖方Quant主要集中在国际投行（高盛、摩根士丹利等）和中资投行国际子公司（中金、中信里昂），深圳的卖方机会在国内券商的金融工程/量化自营部门。
> 
> 深圳的买方Quant核心是顶尖量化私募（幻方、灵均等），香港的买方Quant包括全球顶级对冲基金和自营交易公司（Citadel, Two Sigma, Optiver等）。
> 
> 深圳的量化岗位面试必考对国内金融数据源（Wind, Tushare, JoinQuant）和A股交易规则的熟悉度。
> 
> 香港的量化岗位面试对期权定价、随机微积分等理论要求更深。
> 
> 深圳偏好国内顶尖理工院校（清北复交、浙大、中科大等）的硕士/博士，海外名校需对国内市场有理解；香港偏好全球顶级名校（美英顶尖高校、新加坡两所、港三所），专业排名比学校综合排名更重要。
> 
> 纯金融背景竞争力弱，数学、物理、计算机、电子工程等硬核专业是绝对主流。
> 
> 大湾区量化岗位技能要求：Python、SQL、Linux是基础；深圳需精通C++，香港需英语工作能力和kdb+/q等工具。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 在大湾区，两者的重心和机会有显著差异：1. 卖方Quant（以投行为主）：香港是绝对中心...2. 买方Quant（以基金/私募为主）：深圳是核心战场...
> - 国际投行（高盛、摩根士丹利等）及中资投行的国际子公司（中金、中信里昂等）的量化团队主要聚集于香港。
> - 深圳是核心战场：聚集了全国最顶尖、最活跃的量化私募（幻方、灵均等）...香港是国际桥头堡：云集了全球顶级对冲基金和自营交易公司（Citadel, Two Sigma, Optiver等）

**[量化研究员·高频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a15a138000000003](https://www.xiaohongshu.com/discovery/item/6a15a138000000003501dd25?xsec_token=YBJXceSEhkLQc7puTGKMxN_p_R9jpYHzgNTvXgnWHFQ5c%3D&xsec_source=app_share)

> 帖内提到的公司: Citadel, Jane Street, Two Sigma, Optiver, IMC, SIG

> **内容快照**:
> 
> 量化行业机构梯队分为顶级买方（Citadel、Jane Street、Two Sigma）、一线做市商（Optiver、IMC等）、知名对冲基金（Balyasny、Bridgewater等）、成长型量化机构（DRW、Schonfeld等）、卖方&资管（高盛、BlackRock等）和加密量化（Jump Crypto等）。
> 
> 初级岗位薪资参考：顶级买方entry级可达$300k+，不同机构薪资差异大。
> 
> 不同梯队机构考察重点不同：顶级买方和做市商更看重算法题、数学推导和工程实现；资管岗更偏向因子建模和业务理解。
> 
> 低年级可以参加IMC、Optiver的交易赛积累项目经历。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 买方（God Tier）以 Citadel、Jane Street、Two Sigma 为代表...一线做市商包括 Optiver、IMC、SIG、HRT、Jump Trading 等...知名对冲基金比如 Balyasny、Bridgewater、D.E. Shaw 等...成长型量化机构以 DRW、Schonfeld、Tower Research 为代表...卖方 & 资管量化岗投行（高盛、摩根士丹利、小摩等）和资管巨头（BlackRock、Vanguard、State Street 等）...加密量化赛道还有 Jump Crypto、Wintermute、GSR 等
> - Citadel 的 entry 级岗位可达 $300k+
> - 顶级买方和做市商更看重算法题、数学推导和工程实现，资管岗则更偏向因子建模和业务理解。

---

### 78. 世纪前沿

- **tier**: 中型量化私募
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 量化研究员·中频 (1)
- **industry_focus**: —
- **source 标签**: saif:2025
- **notes**:
  - [量化研究员·中频] SAIF 2025 量化命中

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2025 | 世纪前沿 | 量化研究员 | 1 | 量化私募 |

#### XHS 帖证据 (4 条)

**[量化因子工程师]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a0c2659000000003](https://www.xiaohongshu.com/discovery/item/6a0c2659000000003501c0b8?xsec_token=YBWo3_04eqG7GfzDfPD8xw2IDqvAm1GxyL7BT86NKKem8%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 衍复, 灵均, 世纪前沿

> **内容快照**:
> 
> 幻方、九坤、明汯、衍复是量化“四大天王”出海主力，规模700-800亿，香港办公室持续扩招，提供签证担保和外派补贴。
> 
> 灵均2025年以73.51%收益斩获百亿量化业绩冠军，世纪前沿规模跃升至500-600亿，两家香港团队扩张期，对因子挖掘、建模能力强的同学友好。
> 
> 黑翼2025年新获香港9号牌，量派2024年拿下4+9号双牌照，规模突破300亿，入行门槛相对友好。
> 
> 港圈量化求职门槛：名校硕博，数理/计算机/金工背景优先，英文流利是标配。
> 
> 港圈量化优势：行业顶薪+外派补贴+签证担保，国际化投研平台，职业天花板更高。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 幻方 / 九坤 / 明汯 / 衍复：量化“四大天王”出海主力，规模普遍在700-800亿区间...香港办公室持续扩招。提供签证担保和外派补贴
> - 灵均 / 世纪前沿：2025年灵均以73.51%收益斩获百亿量化业绩冠军...世纪前沿规模跃升至500-600亿...两家香港团队均处于扩张期，对因子挖掘、建模能力强的同学非常友好
> - 黑翼 / 量派：黑翼2025年新获香港9号牌...量派2024年拿下4+9号双牌照，2025年规模已突破300亿...入行门槛相对友好

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69f55dc6000000003](https://www.xiaohongshu.com/discovery/item/69f55dc60000000036030768?xsec_token=YBO_g5dxVwlm0aWR4QVRvbiiuom_DAIHrelvWhT7f_Ats%3D&xsec_source=app_share)

> 帖内提到的公司: 明汯投资, 平方和, 顽岩, 黑翼, 衍复, 龙旗

> **内容快照**:
> 
> 2026年4月百亿量化私募备案数据：明汯投资断层领先，4月备案42只，前4个月合计131只，已占去年全年84%。平方和、顽岩、黑翼、衍复等备案量也较高，而宽德、世纪前沿、九坤节奏放缓。新晋百亿私募包括远澜、子午、量道、凯读、鲁民投、知行通达。
> 
> 明汯投资备案节奏激进，渠道承接能力强，对发行窗口积极。
> 
> 宽德、世纪前沿、九坤备案节奏明显放缓，可能更重视容量管理。
> 
> 量化私募规模扩大后，超额收益能否持续是关键问题。
> 
> 新百亿私募出现，量化行业并非头部固化，中腰部仍有上升机会。
> 
> 百亿只是入场券，规模扩大后超额、波动、持有人体验才是真正考验。
> 
> 备案数量可作为观察管理人战略动作的窗口，但不能直接作为选基依据。
> 
> 量化私募竞争最终比拼的是规模变大后仍能做出超额收益。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 2026年4月，百亿量化私募备案数据更新。从YTD数据看，明汯投资仍然断层领先。1月至4月，明汯合计备案131只。其中4月单月备案42只。对比2025年全年156只，明汯前4个月已经完成去年全年约84%的备案量。
> - 这个节奏非常激进。4月的数据说明，它不是短期冲刺，而是在持续加速。背后至少说明两点：渠道承接能力强，管理人对当前发行窗口较为积极。
> - 相比之下，宽德4月备案7只，世纪前沿9只，九坤6只，节奏明显放缓。这不一定说明谁更好，而是说明不同管理人的阶段选择不同。有些机构选择趁市场回暖快速扩张，有些机构更重视容量管理。

**[量化研究员·高频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/694dfad5000000002](https://www.xiaohongshu.com/discovery/item/694dfad50000000022032080?xsec_token=YBcHIqfNaLBVDhXCU8c_xcywRuE30yKwo_JDQ4QwekE5I%3D&xsec_source=app_share)

> 帖内提到的公司: 明汯投资, 幻方量化, 衍复投资, 九坤投资, 宽德投资, 世纪前沿

> **内容快照**:
> 
> 2025年量化策略业绩全面回暖，头部机构规模洗牌，明汯、幻方、衍复、九坤等有望重返千亿俱乐部。
> 
> 明汯投资今年备案最多，多个渠道积极推产品，可能很快突破千亿。
> 
> 幻方量化2021年曾主动控盘建议客户赎回，之后靠业绩驱动规模自然回升。
> 
> 衍复投资今年年中暂停新申购，多个策略年内第二次分红，主动控制规模扩张节奏。
> 
> 九坤投资产品发行细水长流，规模稳步爬升，属于长跑型选手。
> 
> 宽德投资上半年募资凶猛，下半年明显刹车，预计短期内规模变化不大。
> 
> 世纪前沿、诚奇、黑翼三家今年发力明显，备案和募资都在前列。
> 
> 2025年量化圈关键词是“卷”，靠规模喊口号的草莽时代结束，现在比的是策略迭代速度和算力竞赛。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 2025年余额仅剩最后3个交易日！复盘这一年，绝对是量化策略的当打之年。业绩全面回暖，头部机构赚得盆满钵满，百亿量化阵营也在加速扩容。
> - 明汯：今年的备案王！多个渠道都在积极推其产品，势头非常猛，可能很快再次捅破1000亿这层窗户纸。
> - 幻方：2021年曾主动控盘甚至建议客户赎回，随后依靠业绩驱动规模自然回升，实力不允许低调。

---

### 79. 东吴证券

- **tier**: 中型券商研究所
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 卖方研究员·消费医药周期 (1)
- **industry_focus**: 医药, 消费
- **source 标签**: xhs:卖方研究员·消费医药周期:4
- **notes**:
  - [卖方研究员·消费医药周期] 中型卖方

#### XHS 帖证据 (6 条)

**[公募基金中后台]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0b1435000000003](https://www.xiaohongshu.com/discovery/item/6a0b14350000000035033c92?xsec_token=YBjJDvW9ftzu9in_HYy8Pxxg20_Kg7r5OsrRXUwVlafdo%3D&xsec_source=app_share)

> 帖内提到的公司: 国联民生, 南方基金, 东吴证券, 景顺长城, 平安证券, 平安理财

> **内容快照**:
> 
> 用户已面试国联民生中台岗、南方基金群面、东吴证券债承、景顺长城中台岗，并完成平安证券、平安理财、民生银行、东方财富证券的测评。
> 
> 用户投递了多家金融机构的暑期实习，包括券商、基金、银行理财子等。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 已面试：1、国联民生中台岗 2、南方基金群面 3、东吴证券债承 4、景顺长城中台岗 已测评：1、平安证券、平安理财 2、民生银行 3、东方财富证券
> - 国联民生中台岗、南方基金群面、东吴证券债承、景顺长城中台岗、平安证券、平安理财、民生银行、东方财富证券

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68c02652000000001](https://www.xiaohongshu.com/discovery/item/68c02652000000001b035d05?xsec_token=YBtkYOqLo7KO0p4UrxPMbxSLRrDlXVacMBHa-ODD0DWIc%3D&xsec_source=app_share)

> 帖内提到的公司: 东吴证券

> **内容快照**:
> 
> 东吴证券食品饮料组招聘实习生，正式实习/日常实习，周末需加班。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 上海/远程-东吴证券证券-食品饮料xcf 正式实习/日常 周末要加班

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a004d91000000003](https://www.xiaohongshu.com/discovery/item/6a004d910000000036000bfe?xsec_token=YBYM1cUi6i2AdR2d2EYp7gyzNSgGWMnMTf2wxGS2XvQqk%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 中金公司, 华泰证券, 中信建投证券, 国泰海通证券, 招商证券

> **内容快照**:
> 
> 投行招聘中，除了中金公司，大部分券商强调实习留用，面试越来越水，更看重实战能力。
> 
> 26年投行招聘仍是招聘大年，腰腿部券商提供更多机会，学历门槛下探。
> 
> 列举了15家开放投行暑期实习的券商和14家开放春季招聘的券商，其中4家同时开放。
> 
> 本科学历背景普通但实战能力突出的候选人，在26年拿到投行机会的可能性提升。
> 
> 投行面试越来越水，技术面试在绝大部分券商涉及不到。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 除了中金公司以外，其他大部分券商都强调“实习留用”...投行的面试越来越水了。
> - 26年仍会是投行的招聘大年...腰腿部券商投行给了大家更多的“选择权”...学历相对没那么优秀，26年有更多的加入投行的机会和可能性。
> - 至少包括15家：中信证券、中金公司、华泰证券...至少包括14家：招商证券、国联民生证券...同时开放暑期实习和春季招聘的投行，包括4家：招商证券、国联民生证券、东吴证券、西部证券。

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000](https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000702ace7?xsec_token=YB9MVh1sELWdJvRY7-4rURZo9qtVNwXXJJLAGIjlCzytE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 中金公司, 华泰证券, 中信建投证券, 申万宏源

> **内容快照**:
> 
> 中信证券多项业务指标连年夺魁，是券商中的'神'级公司。
> 
> 国泰海通由国开君安和海通证券合成，资本实力跃居行业榜首。
> 
> 中金公司是首家中外合资投行，投行业务标杆。
> 
> 华泰证券是金融科技+财富管理领域的标杆。
> 
> 中信建投证券降薪严重，与前三个相比掉队。
> 
> 2025年证券行业呈现'强者恒强'的马太效应，头部券商占据大部分市场份额。
> 
> 头部券商总部前台岗求职难度不输国有总行，建议根据学历背景和实习相关性合理选择。
> 
> 随着大A慢牛市场，证券公司实习机会增多，26届应把握机会。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 中信证券可以单独开一个'神'级，多项业务指标连年夺魁
> - 国泰海通由国开君安和海通证券合成而成的新龙头，资本实力跃居行业榜首
> - 中金公司，首家中外合资投行，投行业务标杆

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a00852d000000000](https://www.xiaohongshu.com/discovery/item/6a00852d0000000008002bb5?xsec_token=YBYM1cUi6i2AdR2d2EYp7gy0jrM93HeTyqyT4_9HsqWHE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 华泰证券, 中金证券, 中信建投, 招商证券

> **内容快照**:
> 
> 券商分为五个梯队，第一梯队包括中信证券、国泰海通、华泰证券、中金证券、中信建投等，平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> 
> 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> 
> 第一梯队偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历更加分。
> 
> 第三梯队门槛相对灵活，海外院校、转专业同学都有机会，关键是简历里要体现对金融行业的理解。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> - 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> - 通常更偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历会更加分。

**[行业研究员·消费]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a01b2b5000000003](https://www.xiaohongshu.com/discovery/item/6a01b2b50000000037034916?xsec_token=YBUPAYoqBEFYQ7pp_viS1Jf60hlFndL4XNFya8dAeFUxc%3D&xsec_source=app_share)

> 帖内提到的公司: 东吴证券

> **内容快照**:
> 
> 东吴证券研究所食品饮料团队招募实习生，要求985/211及海外知名院校硕士在读，2027届及往后毕业，有行研实习经历优先。
> 
> 东吴证券提供卖方研究实习岗位，覆盖食品饮料行业。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 东吴证券研究所食品饮料团队实习生招募
> - 东吴证券研究所食品饮料团队

---

### 80. 中国国际金融

- **tier**: 头部券商研究所
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 利率宏观策略 (1)
- **industry_focus**: 金融
- **source 标签**: common_knowledge:头部券商
- **notes**:
  - [利率宏观策略] 按行业共识,与中金公司同体系

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2025 | 中国国际金融股份有限公司 | 卖方分析师 | 1 | 券商研究所 |

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 81. 中国银河证券

- **tier**: 中型券商研究所
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 卖方研究员·宏观策略 (1)
- **industry_focus**: —
- **source 标签**: saif:2024, xhs:卖方研究员·宏观策略:1
- **notes**:
  - [卖方研究员·宏观策略] SAIF 2024 命中

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 中国银河证券股份有限公司 | 卖方分析师 | 1 | 券商研究所 |

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 82. 中国银行

- **tier**: 银行系资管
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 财富管理FOF (1)
- **industry_focus**: 金融
- **source 标签**: xhs:财富管理FOF:1
- **notes**:
  - [财富管理FOF] 国有大行财富

#### SAIF 校友流向证据 (3 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 中国银河证券股份有限公司 | 卖方分析师 | 1 | 券商研究所 |
| 2025 | 中国投资有限责任公司 | 行业研究员 | 1 | 私募 |
| 2025 | 中国国际金融股份有限公司 | 卖方分析师 | 1 | 券商研究所 |

#### XHS 帖证据 (4 条)

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[利率宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/65d1b8ba000000000](https://www.xiaohongshu.com/discovery/item/65d1b8ba0000000007004ffa?xsec_token=YB89jGF1lO7RYoY1dqv_1dX_n7IaKqIKa69o-pyhsGts0%3D&xsec_source=app_share)

> 帖内提到的公司: 郭磊宏观茶座, 一瑜中的, Kevin策略研究, 华泰证券固收研究, 郁言债市, 固收亮话

> **内容快照**:
> 
> 宏观/固收研究日常工作需要大量阅读，包括新闻、数据、机构报告和专家评论。
> 
> 卖方机构报告更新频繁，每天1-3篇，需要筛选有效信息。
> 
> 推荐了多个宏观/固收研究资源，包括卖方、买方、论坛和野生大佬。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 投研日常工作需要大量读东西，除了新闻和数据，机构报告还有各路大佬评论这些去哪看怎么看
> - 每个板块基本都有独立的号，并且大部分都是保持每天1-3篇的更新量
> - 下面盘一盘宏观/固收两个板块我日常都会看什么

**[固收+多资产]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69fc5941000000003](https://www.xiaohongshu.com/discovery/item/69fc59410000000035033df7?xsec_token=YBMVn1RFZuLCNCpexZRAr5gbS42XqSQYhg3TGyDSz5gCs%3D&xsec_source=app_share)

> 帖内提到的公司: 中国国新, 诚通基金, 上海国际集团, 北京金控集团, 浙江金控

> **内容快照**:
> 
> 国资PE专注于股权投资，地方金控提供多元化金融服务，两者业务互动频繁。
> 
> 券商自营信用债投资经理和资金交易员是前台中相对轻松的岗位。
> 
> 纯固收越来越难做，多资产、大类资产配置和固收量化是发展方向。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 国资pe是以股权投资业务为核心...地方金控是地方政府主导设立的综合性金融控股平台
> - 券商自营信用债投资经理...自营没有募资压力，信用债又不用总是交易
> - 纯固收越来越难做的背景下，多资产，大类资产配置和固收量化是这个细分领域的发展方向

**[财富管理FOF]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69b7adf5000000001](https://www.xiaohongshu.com/discovery/item/69b7adf5000000001d01e2cb?xsec_token=YBUbBPgCnu6HsJND6ndu6QErhvAcLeTam3vb19cHq1TBk%3D&xsec_source=app_share)

> 帖内提到的公司: 富国基金, 中欧基金, 易方达基金, 广发基金, 博时基金, 交银施罗德基金

> **内容快照**:
> 
> FOF（基金中的基金）近期在公募市场热度上升，发行数量和规模大幅增长，银行渠道推动明显，产品设计以短持有期、偏债混合策略为主。
> 
> FOF总规模突破3000亿，头部公司如富国、中欧、易方达、广发规模超200亿，但行业格局未固化。
> 
> FOF热度背后原因包括存款利率下行、市场波动大、银行渠道转型、产品设计适配等。
> 
> FOF行业趋势：从选基转向配置，产品形态纳入黄金ETF、REITs、QDII等，与养老联动。

> **verbatim 锚点 (T1/T3 抽取)**:
> - FOF（基金中的基金）突然成了公募市场的热门话题。截至3月14日，今年全市场已经有40只FOF成立，合计募了619.73亿元。跟去年一季度比，数量增加了233%，规模增长了361%。
> - 截至3月14日，FOF总规模突破3000亿。84家公募有布局，但头部还没固化：规模最大的管理人约245亿，规模超100亿的只有11家。第一梯队：富国、中欧、易方达、广发都超200亿。
> - 一是存款利率下行，叠加市场波动大，个人做择时、选基金的难度在增加。FOF的逻辑是通过专业选基+多资产配置，降低单一资产的波动。二是银行渠道从'卖产品'转向'卖配置方案'。三是产品设计的适配。

---

### 83. 中投公司

- **tier**: 头部PE
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: PE投后VC行研 (1)
- **industry_focus**: 金融
- **source 标签**: saif:2025, taxonomy_doc
- **notes**:
  - [PE投后VC行研] 主权基金

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 84. 中泰证券

- **tier**: 中型券商研究所
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 行业研究员·消费 (1)
- **industry_focus**: 消费
- **source 标签**: xhs:行业研究员·消费:2
- **notes**:
  - [行业研究员·消费] XHS 消费组 2 次

#### XHS 帖证据 (6 条)

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a004d91000000003](https://www.xiaohongshu.com/discovery/item/6a004d910000000036000bfe?xsec_token=YBYM1cUi6i2AdR2d2EYp7gyzNSgGWMnMTf2wxGS2XvQqk%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 中金公司, 华泰证券, 中信建投证券, 国泰海通证券, 招商证券

> **内容快照**:
> 
> 投行招聘中，除了中金公司，大部分券商强调实习留用，面试越来越水，更看重实战能力。
> 
> 26年投行招聘仍是招聘大年，腰腿部券商提供更多机会，学历门槛下探。
> 
> 列举了15家开放投行暑期实习的券商和14家开放春季招聘的券商，其中4家同时开放。
> 
> 本科学历背景普通但实战能力突出的候选人，在26年拿到投行机会的可能性提升。
> 
> 投行面试越来越水，技术面试在绝大部分券商涉及不到。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 除了中金公司以外，其他大部分券商都强调“实习留用”...投行的面试越来越水了。
> - 26年仍会是投行的招聘大年...腰腿部券商投行给了大家更多的“选择权”...学历相对没那么优秀，26年有更多的加入投行的机会和可能性。
> - 至少包括15家：中信证券、中金公司、华泰证券...至少包括14家：招商证券、国联民生证券...同时开放暑期实习和春季招聘的投行，包括4家：招商证券、国联民生证券、东吴证券、西部证券。

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a00852d000000000](https://www.xiaohongshu.com/discovery/item/6a00852d0000000008002bb5?xsec_token=YBYM1cUi6i2AdR2d2EYp7gy0jrM93HeTyqyT4_9HsqWHE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 华泰证券, 中金证券, 中信建投, 招商证券

> **内容快照**:
> 
> 券商分为五个梯队，第一梯队包括中信证券、国泰海通、华泰证券、中金证券、中信建投等，平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> 
> 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> 
> 第一梯队偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历更加分。
> 
> 第三梯队门槛相对灵活，海外院校、转专业同学都有机会，关键是简历里要体现对金融行业的理解。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> - 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> - 通常更偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历会更加分。

**[自营FOF]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6890067f000000000](https://www.xiaohongshu.com/discovery/item/6890067f0000000003031ea8?xsec_token=YBmCA1AtoFdnPTCngthUM3rB8t5ZksJM979ASjR1w7C5Y%3D&xsec_source=app_share)

> 帖内提到的公司: 兴全基金, 易方达基金, 中欧基金, 大成基金, 华夏基金, 南方基金

> **内容快照**:
> 
> FOF基金行业人才流失严重，薪资不够吸引人，很多优秀的基金经理都跑去保险、私募了。
> 
> 兴全FOF的林国怀从2020年开始重仓刘旭，2024年却全部清仓了，可能是考虑到刘旭管理规模已达475亿。
> 
> 兴证全球已经把'FOF投资部'改名为'多元资产配置部'，信号很明显。
> 
> 华夏郑鹏管理华夏海外聚享，业绩堪称完美，但已离职。
> 
> 南方恽雷理论功底深厚，核心理念是寻找长期优秀的Beta + 股债负相关性。
> 
> 中泰唐军建立了中泰时钟资产配置体系，长期持有黄金ETF。
> 
> 今年FOF新发规模已达308.42亿，超过去年全年的123.67亿，招商银行大力推广'TREE长盈计划'。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 人才流失严重：薪资不够吸引人，很多优秀的基金经理都跑去保险、私募了
> - 兴全FOF的林国怀从2020年开始重仓刘旭，2024年却全部清仓了！可能是考虑到刘旭管理规模已达475亿，太大了...
> - 兴证全球已经把'FOF投资部'改名为'多元资产配置部'，信号很明显！

**[自营FOF]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/694f3770000000002](https://www.xiaohongshu.com/discovery/item/694f377000000000210318a7?xsec_token=YBlKAv8wY0HALD2nXaWlzzSkmAyHKtqrYjKwISPIGRpac%3D&xsec_source=app_share)

> 帖内提到的公司: 南方基金, 中泰资管, 招商银行

> **内容快照**:
> 
> FOF规模较年初增加1041亿元，达到2373.05亿元，增幅高达78.15%，公募FOF业务呈现加速发展态势。
> 
> 南方基金夏莹莹管理的FOF产品南方合顺2024年至今涨幅达24.51%，黄金配置约10%，贡献约10%的净值。
> 
> 招商银行推出“Tree多元资产配置”计划，推动FOF发行。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 据Wind统计，FOF规模较年初增加1041亿元，达到2373.05亿元，增幅高达78.15%，公募FOF业务呈现加速发展态势。
> - 2024年至今该产品涨幅达24.51%，表现优异...黄金配置约10%，对产品净值的贡献同样在10%左右
> - 这些增量中，很大一部分受益于招商银行“Tree多元资产配置”计划的推动。

**[行业研究员·消费]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69e76415000000002](https://www.xiaohongshu.com/discovery/item/69e76415000000002102e478?xsec_token=YBgmoRk57qW1qcAJtiMgfWzzlKmt0B2qMDte0923sNd1A%3D&xsec_source=app_share)

> 帖内提到的公司: 中泰证券

> **内容快照**:
> 
> 中泰证券食品饮料组实习生招聘

> **verbatim 锚点 (T1/T3 抽取)**:
> - 上海实习丨中泰证券 食品饮料组实习生

**[行业研究员·消费]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69a6ff47000000002](https://www.xiaohongshu.com/discovery/item/69a6ff470000000028022aa5?xsec_token=YBx0Yp7YzYFQyTm91SyPc0ufSeLATnS9absRVH6qJG-uQ%3D&xsec_source=app_share)

> 帖内提到的公司: 中泰证券

> **内容快照**:
> 
> 中泰证券研究所食品饮料组招聘实习生，要求有行研基础、报告撰写经验，实习时间3个月以上，一周至少4天，可远程或线下。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 中泰证券研究所-食品饮料组-实习生

---

### 85. 中金基金

- **tier**: 二线公募
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 公募指数研究员 (1)
- **industry_focus**: 金融
- **source 标签**: xhs:公募指数研究员:2
- **notes**:
  - [公募指数研究员] XHS 指数 2 次

#### XHS 帖证据 (33 条)

**[买方 Quant]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/695940c8000000001](https://www.xiaohongshu.com/discovery/item/695940c8000000001e03a19c?xsec_token=YBrJ_goExM-LGFpD_KXswc_GrNMq5jKropLNK56upboAU%3D&xsec_source=app_share)

> 帖内提到的公司: 高盛, 摩根士丹利, 中金, 中信里昂, 幻方, 灵均

> **内容快照**:
> 
> 大湾区量化岗位分为卖方Quant（投行）和买方Quant（基金/私募），卖方Quant集中在香港，买方Quant在深圳更活跃。
> 
> 香港的卖方Quant主要集中在国际投行（高盛、摩根士丹利等）和中资投行国际子公司（中金、中信里昂），深圳的卖方机会在国内券商的金融工程/量化自营部门。
> 
> 深圳的买方Quant核心是顶尖量化私募（幻方、灵均等），香港的买方Quant包括全球顶级对冲基金和自营交易公司（Citadel, Two Sigma, Optiver等）。
> 
> 深圳的量化岗位面试必考对国内金融数据源（Wind, Tushare, JoinQuant）和A股交易规则的熟悉度。
> 
> 香港的量化岗位面试对期权定价、随机微积分等理论要求更深。
> 
> 深圳偏好国内顶尖理工院校（清北复交、浙大、中科大等）的硕士/博士，海外名校需对国内市场有理解；香港偏好全球顶级名校（美英顶尖高校、新加坡两所、港三所），专业排名比学校综合排名更重要。
> 
> 纯金融背景竞争力弱，数学、物理、计算机、电子工程等硬核专业是绝对主流。
> 
> 大湾区量化岗位技能要求：Python、SQL、Linux是基础；深圳需精通C++，香港需英语工作能力和kdb+/q等工具。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 在大湾区，两者的重心和机会有显著差异：1. 卖方Quant（以投行为主）：香港是绝对中心...2. 买方Quant（以基金/私募为主）：深圳是核心战场...
> - 国际投行（高盛、摩根士丹利等）及中资投行的国际子公司（中金、中信里昂等）的量化团队主要聚集于香港。
> - 深圳是核心战场：聚集了全国最顶尖、最活跃的量化私募（幻方、灵均等）...香港是国际桥头堡：云集了全球顶级对冲基金和自营交易公司（Citadel, Two Sigma, Optiver等）

**[资管FOF]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/68fb85c2000000000](https://www.xiaohongshu.com/discovery/item/68fb85c20000000004012878?xsec_token=YBpb-4slSnJFcvHP5-4vJ_c6vSHGKkRhYmI8b7PXoUkI8%3D&xsec_source=app_share)

> 帖内提到的公司: 中金

> **内容快照**:
> 
> 中金暑期FOF投研岗面试流程：第一轮群面实际为13人轮流单面，被问英文问题，二三面半小时以内，无tech问题。
> 
> 中金暑期实习offer后，表现好可能直接拿return，或秋招跳过笔试环节。实习薪资100元/天。
> 
> 中金FOF投研岗暑期实习，岗位为FOF投研。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一轮无效群面=13个人轮流单面（超绝狗屎运我还是第一个，说完太无聊跟朋友聊了一个多小时vx才开始群面讨论[微笑R]），除了被突然的一个英文问题打的措手不及之外，其他都还好，没有很tech，二三面基本都半小时以内
> - 电话offer：连着打了四个才接起来，是hr直接通知面试通过问是否有意愿接offer，实习100💰一天+附近餐厅优惠什么的，表现好可能直接拿return，或者秋招跳过笔试环节（听语气第二种居多）
> - 中金暑期fof投研岗（已offer）

**[AI算法业务]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68e12963000000000](https://www.xiaohongshu.com/discovery/item/68e12963000000000400602e?xsec_token=YBoMACpj-L2xybKn7Neuw7-fKkHjNSchL1W07QkUdUvsg%3D&xsec_source=app_share)

> 帖内提到的公司: 中金公司

> **内容快照**:
> 
> 中金金融科技校招面试包括技术面和综合面，技术面涉及A股预测项目的特征工程、随机森林调优、SQL优化、LSTM与ARIMA对比、大规模数据处理等；综合面考察对中金财富管理科技应用、合规效率、机构客户系统等的理解。
> 
> 中金公司金融科技岗面试重视技术落地和业务理解，面试官会问及公司近期科技动态。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 首轮技术面超硬核！被问到A股预测项目的特征工程...二轮综合面更考对公司的理解～被问中金财富管理科技应用...
> - 面试下来感觉中金很看重技术落地和业务理解，宝子们准备时记得多研究公司近期科技动态！

**[信用研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/66b0dab4000000002](https://www.xiaohongshu.com/discovery/item/66b0dab40000000025033160?xsec_token=YBWIG9AzV0kN4M-Y1opCW5ntSRX2D1bePJHQ7Q7gr_NJE%3D&xsec_source=app_share)

> 帖内提到的公司: 中金固定收益研究, YY, 光大固收

> **内容快照**:
> 
> 信用债投研需要从入门到进阶，进阶方向包括信用风险研究、底层逻辑构建、核心能力培养、资源利用和信用策略。
> 
> 信评岗位的核心能力包括行业分析能力、财务分析能力、市场敏感度、复盘和总结能力。
> 
> 推荐100个公众号用于行业分析框架构建、每日舆情跟踪、热点事件深度和方法类总结。
> 
> 信用策略包括票息策略、交易策略、杠杆策略、行业轮动策略、券种策略。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 信用分析进阶：但由于近年投研行业内卷程度提升、资产荒背景下的收益挖掘大背景下，信用债投研还需要在以下方面继续深耕
> - 核心能力。行业分析能力、财务分析能力、市场敏感度、复盘和总结能力
> - 100个公众号有助于行业分析框架的构建，比如中金固定收益研究《金融资产管理公司信用资质跟踪》、YY《煤炭企业我们关注什么》

**[公募指数研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a1163d5000000003](https://www.xiaohongshu.com/discovery/item/6a1163d5000000003701f9e9?xsec_token=YB-ytYsXaETuxWOMalLnmNS1SieO69lxemP-6F61KY6SY%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达基金, 华夏基金, 南方基金, 中金基金

> **内容快照**:
> 
> 公募REITs迎来指数化时代，易方达、华夏、南方、中金四家基金公司同步申报中证REITs全收益指数基金。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 当公募REITs迎来指数化时代

**[公募权益研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a154d91000000000](https://www.xiaohongshu.com/discovery/item/6a154d91000000000702163f?xsec_token=YBtykXCAFyiHSXD_GpX4xfBCEPl85Qoq2k5vZtdH2VHjI%3D&xsec_source=app_share)

> 帖内提到的公司: 泰康资产, 景顺长城, 中投, 社保基金, 外管局外汇中心, 易方达基金

> **内容快照**:
> 
> 泰康资产和景顺长城正在面试辅导，涉及投研岗位。
> 
> 辅导的offer覆盖一级投资（含PE及PERE）、战投、产投、二级投研、投行、银行、理财子、金融央国企等。
> 
> 辅导过腾投、GIC、易方达基金、华夏基金、泰康资产、bb行、中金、华泰、中投、中信集团管培、社保基金、外管局外汇中心、国寿投资、建总、工总、农发总、新华社、强势部委等top全职offer。
> 
> 背景一般甚至有明显bug的也能辅导上岸top全职offer，例如两财一贸tier拿下大买投研，本科top10之外硕士QS100-200拿下头部保险资管投研，非top4本硕上岸头部一级投资岗等。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 泰康资产+景顺长城面试辅导
> - 自己投递的offer覆盖一级投资（含pe及pere）/战投产投/二级投研/投行/银行/理财子/金融央国企/垄断型央企/部委/另类的all rounder实力
> - 辅导腾投/GIC/易方达基金/华夏基金/泰康资产/bb行/中金/华泰/中投/中信集团管培/社保基金/外管局外汇中心/国寿投资/建总/工总/农发总/新华社/强势部委等top全职offer的实力

_(+27 条更多帖未展示, 同 sub_cat)_

---

### 86. 中银证券

- **tier**: 中型券商研究所
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 卖方研究员·宏观策略 (1)
- **industry_focus**: —
- **source 标签**: xhs:卖方研究员·宏观策略:1
- **notes**:
  - [卖方研究员·宏观策略] 银行系券商

#### XHS 帖证据 (7 条)

**[信用研究员]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/65b112fa000000001](https://www.xiaohongshu.com/discovery/item/65b112fa000000001100b280?xsec_token=YBzU0cmu6QqVVwu4bJ9BXshq0B-bdwJ6C57ZTtl5A5qtI%3D&xsec_source=app_share)

> 帖内提到的公司: 北银理财, 宁银理财, 苏银理财, 杭银理财, 招银理财, 工银理财

> **内容快照**:
> 
> 北银理财是北京银行旗下的理财子公司，成立于2022年底，属于城商行理财子，投资研究条线下设研究部、固收部、权益部和另类，以及集中交易室。
> 
> 北银理财面试流程：第一轮伪群面，5人一组，HR问行为面和个人信息，统计意愿岗位；第二轮分两个会议室，一个3面试官+3面试者，另一个2面试官（1人力+1业务领导），博士似乎被放在一组。面试聚焦简历面，问理财子相关经历、研究能力、论文等。业务领导问实习经历、看的方向、部门配置、权益态度、投资标的、实习课题、近期观点、研究所实习行业，以及定岗倾向（固收），对美元固收兴趣，对新发产品了解。
> 
> 作者强调个人兴趣集中在投研，只考虑投研岗，并认为该offer是投研条线。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 北银理财成立时间太短，22年底，但北京银行作为top1城商行（经过评论区uu指正，江苏银行是第一，那就top2），实力还是在位的，目前投资研究条线下设部门主要是四个：研究部，固收部，权益部和另类，外加一个集中交易室。
> - 第一次面试就是伪群面，两个HR，一组5个人左右。相对来说没什么压力，主要是一些行为面或者个人信息了解，会统计每个人意愿岗位，比如投研交易，市场等。第二轮面试分两个会议室进行，一个会议室是三个面试官+三个面试者的搭配，另一个会议室是两个面试官：1人力+1业务领导。ps面试的时候发现似乎博士都被放在一组面试了。第二轮面试相对也聚焦在个人经历的简历面，如果有理财子相关会被问比较多，看评论区uu似乎也有问论文的，可能主要是考察下研究能力。面我的业务领导主要问题围绕我在另一家理财子的经历展开，包括但不限于看的方向，部门人员配置和权益的态度，部门主要投资的标的（不合规的没展开），问下我的实习的工作和课题和近期的观点+研究所实习的时候看的行业。再次问了，对定岗方向倾向，我答得固收，然后补充说了下对美元固收比较感兴趣，又问了下对他们最近新发的产品了解。
> - 面试的时候说了我的个人兴趣比较集中，只想在投研发展，不然不太考虑。因为其他家理财子定岗也只投递了投研岗，也拿到了其他offer，所以姑且厚颜认为这个上岸offer是投研条线。

**[固收+多资产]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a03466a000000000](https://www.xiaohongshu.com/discovery/item/6a03466a000000000702f4c4?xsec_token=YBHOt7zneE8YP4HgVHcNE3uPkUsDCRauMCju0BEuxouic%3D&xsec_source=app_share)

> 帖内提到的公司: yfd, 德邦, 上银, 中银理财, 中邮理财, 信银理财

> **内容快照**:
> 
> 固收赛道相比权益bar略低，但近年越来越卷。
> 
> 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向。
> 
> 实习经历垂直会有一定优势，多段转债量化经历有助于秋招。
> 
> 暑期实习面试中，公募、理财子、券商、私募等均有面试经历，部分挂掉。
> 
> 多数市场化机构在暑期确定名额后秋招不开放。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 固收赛道相比权益bar略低，但是近年越来越卷
> - 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向
> - 实习经历垂直会有一定优势，猜测秋招发面是因为有多段转债量化经历

**[卖方研究员·宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/687b719c000000001](https://www.xiaohongshu.com/discovery/item/687b719c000000001c032ee7?xsec_token=YBLNgyTOisyoCtcxpkArfGUhAr2MEYTPMZ0Xpi-4Fbo1Y%3D&xsec_source=app_share)

> 帖内提到的公司: 天风证券, 中银证券

> **内容快照**:
> 
> 天风证券研究所策略组和中银证券策略组都是卖方研究岗位，但中银证券提供实习证明和薪资，天风证券则没有。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 天风证券研究所策略组（🈚️实习证明）和中银证券（有实习证明和薪资）选哪个！

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a16bd94000000003](https://www.xiaohongshu.com/discovery/item/6a16bd940000000038037a0e?xsec_token=YBVIhZ7G2mEYP_wldrBEA3p5TbQC1oigNXxo4ieGmizEo%3D&xsec_source=app_share)

> 帖内提到的公司: 华西证券, 东北证券, 中银国际证券, 华通证券国际, 招商证券, 国融证券

> **内容快照**:
> 
> 券商行研实习岗位，2026暑期末班车，可内推。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 2026暑期行研末班车实习list

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a00852d000000000](https://www.xiaohongshu.com/discovery/item/6a00852d0000000008002bb5?xsec_token=YBYM1cUi6i2AdR2d2EYp7gy0jrM93HeTyqyT4_9HsqWHE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 华泰证券, 中金证券, 中信建投, 招商证券

> **内容快照**:
> 
> 券商分为五个梯队，第一梯队包括中信证券、国泰海通、华泰证券、中金证券、中信建投等，平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> 
> 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> 
> 第一梯队偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历更加分。
> 
> 第三梯队门槛相对灵活，海外院校、转专业同学都有机会，关键是简历里要体现对金融行业的理解。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> - 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> - 通常更偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历会更加分。

**[行业研究员·消费]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68523924000000002](https://www.xiaohongshu.com/discovery/item/685239240000000022028983?xsec_token=YB1tOVHt4MrRCgE3YRmfKUfzkX4Zhwklu8QU9qotk8kHY%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达, 华夏, 博时, 国泰, 汇添富, 南方

> **内容快照**:
> 
> 易方达、华夏是头部公募，整体待遇好，科技岗位应届生薪资尤其高。
> 
> 博时、国泰、汇添富、南方类似公务员氛围。
> 
> 银行系公募（招商、中银、工银）薪资相对固化，待遇提升空间有限，但工作相对安逸。
> 
> 永赢、嘉实、鹏华待遇不错，但工作强度卷王级别。
> 
> 兴全待遇不错，人少资源多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 易方达、华夏：头部中的头部，整体待遇不会太差，据说科技岗位应届生薪资对比其他应届会尤其高一些
> - 博时、国泰、汇添富、南方：据说类似公务员氛围浓厚
> - 银行系包括（招商、中银、工银等）薪资相对固化，待遇可提升空间对比其他就不太行了，安逸也是相对的吧

_(+1 条更多帖未展示, 同 sub_cat)_

---

### 87. 乾象投资

- **tier**: 中型量化私募
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 量化研究员·中频 (1)
- **industry_focus**: —
- **source 标签**: saif:2025
- **notes**:
  - [量化研究员·中频] SAIF 2025 量化命中

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2025 | 乾象投资 | 量化研究员 | 1 | 量化私募 |

#### XHS 帖证据 (1 条)

**[AI 量化工程师]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69be89d4000000002](https://www.xiaohongshu.com/discovery/item/69be89d4000000002301f58f?xsec_token=YBLYoT2jsBGiWMvHX8qxX6TN7lb7CF7ZBpEL7wjAoGAic%3D&xsec_source=app_share)

> 帖内提到的公司: 乾象投资

> **内容快照**:
> 
> 乾象投资在浙大进行春招，招聘量化实习生，涉及高性能计算和genai方向。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 给我司竖大拇哥 欢迎咨询🙋‍♀️ #量化实习生 #quant #乾象投资 #高性能计算 #genai

---

### 88. 云锋基金

- **tier**: 头部PE
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: PE投后VC行研 (1)
- **industry_focus**: TMT, 消费
- **source 标签**: saif:2024
- **notes**:
  - [PE投后VC行研] 阿里系 PE

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 云锋基金 | 行业研究员 | 1 | 私募 |

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 89. 京东

- **tier**: 互联网大厂
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: AI算法业务 (1)
- **industry_focus**: AI 应用层
- **source 标签**: common_knowledge:头部电商
- **notes**:
  - [AI算法业务] 按行业共识

#### XHS 帖证据 (1 条)

**[多模态推理优化]** (relevance=0.20) — [https://www.xiaohongshu.com/discovery/item/6a145205000000003](https://www.xiaohongshu.com/discovery/item/6a1452050000000038035693?xsec_token=YBO7mCyjNS18IDdy_G_dP8Vyw3rxTz1CVJf1CVFPuxXSw%3D&xsec_source=app_share)

> 帖内提到的公司: 京东

> **内容快照**:
> 
> 京东AI-Infra推理团队招聘实习生，方向为大模型推理加速/投机采样/Speculative Decoding，关注LLM Infra、推理加速、CUDA/并行计算、模型服务化。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 方向：大模型推理加速 / 投机采样 / Speculative Decoding

---

### 90. 佳期投资

- **tier**: 中型量化私募
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 量化因子工程师 (1)
- **industry_focus**: —
- **source 标签**: saif:2024
- **notes**:
  - [量化因子工程师] SAIF 2024 量化命中

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 佳期投资有限公司 | 量化研究员 | 1 | 量化私募 |

#### XHS 帖证据 (1 条)

**[量化研究员·高频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/694dfad5000000002](https://www.xiaohongshu.com/discovery/item/694dfad50000000022032080?xsec_token=YBcHIqfNaLBVDhXCU8c_xcywRuE30yKwo_JDQ4QwekE5I%3D&xsec_source=app_share)

> 帖内提到的公司: 明汯投资, 幻方量化, 衍复投资, 九坤投资, 宽德投资, 世纪前沿

> **内容快照**:
> 
> 2025年量化策略业绩全面回暖，头部机构规模洗牌，明汯、幻方、衍复、九坤等有望重返千亿俱乐部。
> 
> 明汯投资今年备案最多，多个渠道积极推产品，可能很快突破千亿。
> 
> 幻方量化2021年曾主动控盘建议客户赎回，之后靠业绩驱动规模自然回升。
> 
> 衍复投资今年年中暂停新申购，多个策略年内第二次分红，主动控制规模扩张节奏。
> 
> 九坤投资产品发行细水长流，规模稳步爬升，属于长跑型选手。
> 
> 宽德投资上半年募资凶猛，下半年明显刹车，预计短期内规模变化不大。
> 
> 世纪前沿、诚奇、黑翼三家今年发力明显，备案和募资都在前列。
> 
> 2025年量化圈关键词是“卷”，靠规模喊口号的草莽时代结束，现在比的是策略迭代速度和算力竞赛。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 2025年余额仅剩最后3个交易日！复盘这一年，绝对是量化策略的当打之年。业绩全面回暖，头部机构赚得盆满钵满，百亿量化阵营也在加速扩容。
> - 明汯：今年的备案王！多个渠道都在积极推其产品，势头非常猛，可能很快再次捅破1000亿这层窗户纸。
> - 幻方：2021年曾主动控盘甚至建议客户赎回，随后依靠业绩驱动规模自然回升，实力不允许低调。

---

### 91. 光大永明资产

- **tier**: 保险资管
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 信用研究员 (1)
- **industry_focus**: 城投
- **source 标签**: taxonomy_doc
- **notes**:
  - [信用研究员] 保险资管信评

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 92. 光大证券

- **tier**: 中型券商研究所
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 自营FOF (1)
- **industry_focus**: 金融
- **source 标签**: xhs:自营FOF:1
- **notes**:
  - [自营FOF] 券商自营

#### XHS 帖证据 (12 条)

**[信用研究员]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/65b112fa000000001](https://www.xiaohongshu.com/discovery/item/65b112fa000000001100b280?xsec_token=YBzU0cmu6QqVVwu4bJ9BXshq0B-bdwJ6C57ZTtl5A5qtI%3D&xsec_source=app_share)

> 帖内提到的公司: 北银理财, 宁银理财, 苏银理财, 杭银理财, 招银理财, 工银理财

> **内容快照**:
> 
> 北银理财是北京银行旗下的理财子公司，成立于2022年底，属于城商行理财子，投资研究条线下设研究部、固收部、权益部和另类，以及集中交易室。
> 
> 北银理财面试流程：第一轮伪群面，5人一组，HR问行为面和个人信息，统计意愿岗位；第二轮分两个会议室，一个3面试官+3面试者，另一个2面试官（1人力+1业务领导），博士似乎被放在一组。面试聚焦简历面，问理财子相关经历、研究能力、论文等。业务领导问实习经历、看的方向、部门配置、权益态度、投资标的、实习课题、近期观点、研究所实习行业，以及定岗倾向（固收），对美元固收兴趣，对新发产品了解。
> 
> 作者强调个人兴趣集中在投研，只考虑投研岗，并认为该offer是投研条线。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 北银理财成立时间太短，22年底，但北京银行作为top1城商行（经过评论区uu指正，江苏银行是第一，那就top2），实力还是在位的，目前投资研究条线下设部门主要是四个：研究部，固收部，权益部和另类，外加一个集中交易室。
> - 第一次面试就是伪群面，两个HR，一组5个人左右。相对来说没什么压力，主要是一些行为面或者个人信息了解，会统计每个人意愿岗位，比如投研交易，市场等。第二轮面试分两个会议室进行，一个会议室是三个面试官+三个面试者的搭配，另一个会议室是两个面试官：1人力+1业务领导。ps面试的时候发现似乎博士都被放在一组面试了。第二轮面试相对也聚焦在个人经历的简历面，如果有理财子相关会被问比较多，看评论区uu似乎也有问论文的，可能主要是考察下研究能力。面我的业务领导主要问题围绕我在另一家理财子的经历展开，包括但不限于看的方向，部门人员配置和权益的态度，部门主要投资的标的（不合规的没展开），问下我的实习的工作和课题和近期的观点+研究所实习的时候看的行业。再次问了，对定岗方向倾向，我答得固收，然后补充说了下对美元固收比较感兴趣，又问了下对他们最近新发的产品了解。
> - 面试的时候说了我的个人兴趣比较集中，只想在投研发展，不然不太考虑。因为其他家理财子定岗也只投递了投研岗，也拿到了其他offer，所以姑且厚颜认为这个上岸offer是投研条线。

**[公募权益研究员]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/673f35e2000000000](https://www.xiaohongshu.com/discovery/item/673f35e20000000008004421?xsec_token=YBh2z9gW9v0pp7-vcgozkTCOfiSAYt8Thh1xwcW0S6Sos%3D&xsec_source=app_share)

> 帖内提到的公司: 光大理财, 杭银理财, 公募基金, 券商资管

> **内容快照**:
> 
> 理财子面试风格与银行一脉相承，投研岗也需经历无领导小组讨论和行为面，与基金/资管围绕研究经历集中面试不同。
> 
> 理财子面试中，如果被问到的问题与自身研究经历相关性高、专业问题问得深，说明成功引起面试官兴趣，拿offer几率更高。
> 
> 理财子招聘模式与基金/资管不同，多为面试通过即拿offer，但今年也有要求实习留用的。
> 
> 理财子投研岗的市场认可度和薪资水平均不及公募基金，但工作强度明显占优，且固收研究受重视。
> 
> 理财子背靠银行，有渠道优势，旱涝保收；固收类产品多，固收研究很受重视。
> 
> 理财子投研岗对于想做二级的权益研究来说性价比高，固收方向尤其推荐。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 理财子是银行的下属子公司，面试风格跟银行一脉相承，即使我投的是投研岗，也照样得经历无领导小组讨论和行为面
> - 如果被问到的问题与自身研究经历相关性高、专业问题问得深，那么恭喜你，成功引起了面试官的兴趣
> - 理财子则是二级买中少有的面试通过即拿offer的机构（不过听说今年也有理财子要求实习留用了）

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[信用研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/66b0dab4000000002](https://www.xiaohongshu.com/discovery/item/66b0dab40000000025033160?xsec_token=YBWIG9AzV0kN4M-Y1opCW5ntSRX2D1bePJHQ7Q7gr_NJE%3D&xsec_source=app_share)

> 帖内提到的公司: 中金固定收益研究, YY, 光大固收

> **内容快照**:
> 
> 信用债投研需要从入门到进阶，进阶方向包括信用风险研究、底层逻辑构建、核心能力培养、资源利用和信用策略。
> 
> 信评岗位的核心能力包括行业分析能力、财务分析能力、市场敏感度、复盘和总结能力。
> 
> 推荐100个公众号用于行业分析框架构建、每日舆情跟踪、热点事件深度和方法类总结。
> 
> 信用策略包括票息策略、交易策略、杠杆策略、行业轮动策略、券种策略。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 信用分析进阶：但由于近年投研行业内卷程度提升、资产荒背景下的收益挖掘大背景下，信用债投研还需要在以下方面继续深耕
> - 核心能力。行业分析能力、财务分析能力、市场敏感度、复盘和总结能力
> - 100个公众号有助于行业分析框架的构建，比如中金固定收益研究《金融资产管理公司信用资质跟踪》、YY《煤炭企业我们关注什么》

**[利率宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69e60c71000000001](https://www.xiaohongshu.com/discovery/item/69e60c71000000001a036863?xsec_token=YBgxfelF6pOvvQ3lvrOeuANLCOt7CLJSMTLB_Vd8Bcm4E%3D&xsec_source=app_share)

> 帖内提到的公司: 光大, 天风, 东财, 国金, 浙商, 东北

> **内容快照**:
> 
> 学生目标岗位为券商自营部门的偏债或宏观方向，关注校招画像、待遇和发展情况。
> 
> 学生提及的中型券商自营部门包括光大、天风、东财、国金、浙商、东北等。
> 
> 学生询问校招是否是好选择以及进入机会。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 目标偏债或者宏观的二级（了解到一些新增的集中在资产配置方向）
> - 包括不限于如光大，天风，东财，国金，浙商，东北等券商的自营部门
> - 校招是好的选择吗，有机会进吗？

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000](https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000702ace7?xsec_token=YB9MVh1sELWdJvRY7-4rURZo9qtVNwXXJJLAGIjlCzytE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 中金公司, 华泰证券, 中信建投证券, 申万宏源

> **内容快照**:
> 
> 中信证券多项业务指标连年夺魁，是券商中的'神'级公司。
> 
> 国泰海通由国开君安和海通证券合成，资本实力跃居行业榜首。
> 
> 中金公司是首家中外合资投行，投行业务标杆。
> 
> 华泰证券是金融科技+财富管理领域的标杆。
> 
> 中信建投证券降薪严重，与前三个相比掉队。
> 
> 2025年证券行业呈现'强者恒强'的马太效应，头部券商占据大部分市场份额。
> 
> 头部券商总部前台岗求职难度不输国有总行，建议根据学历背景和实习相关性合理选择。
> 
> 随着大A慢牛市场，证券公司实习机会增多，26届应把握机会。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 中信证券可以单独开一个'神'级，多项业务指标连年夺魁
> - 国泰海通由国开君安和海通证券合成而成的新龙头，资本实力跃居行业榜首
> - 中金公司，首家中外合资投行，投行业务标杆

_(+6 条更多帖未展示, 同 sub_cat)_

---

### 93. 兴业银行

- **tier**: 银行系资管
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 固收交易员 (1)
- **industry_focus**: 金融
- **source 标签**: common_knowledge:头部银行金融市场部
- **notes**:
  - [固收交易员] 按行业共识,金融市场部交易强

#### XHS 帖证据 (11 条)

**[投行 IBD]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/69ce44cc000000001](https://www.xiaohongshu.com/discovery/item/69ce44cc000000001d01f7ed?xsec_token=YBIR2Y3LBhuk-vRmL2g0YltYiXkuB0U2Z6pD9wk7QrRGg%3D&xsec_source=app_share)

> 帖内提到的公司: 兴业证券, 兴证资管, 兴全基金

> **内容快照**:
> 
> 兴业证券最赚钱的业务是自营投资和资产管理，投行和研究所相对不赚钱。
> 
> 兴业证券投行岗位包括投行业务助理、债券承做助理、资产证券化承做助理、承销发行助理。
> 
> 兴业证券自营部门推荐证券投资部-行业研究助理和债券与衍生产品业务部-研究助理。
> 
> 兴证资管核心岗位是研究助理，涵盖权益、量化、FOF和衍生品方向。
> 
> 兴业证券投行对本科学历门槛可放松至末9及同Level学校。
> 
> 兴业证券股权业务体量在券商中排名10-20名。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 最赚钱的，当属自营投资和资产管理。而大家最为熟悉的投资银行和研究所属于兴业“最不赚钱”的业务。
> - 投行业务助理、债券承做助理、资产证券化承做助理、承销发行助理，一共4个岗位。
> - 首推证券投资部-行业研究助理和债券与衍生产品业务部-研究助理。

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68ae4ff7000000001](https://www.xiaohongshu.com/discovery/item/68ae4ff7000000001c0106a0?xsec_token=YBaXH2avCjRyk_t-gCh8k1VODrk8SJBm7HhZK9xfJZgO0%3D&xsec_source=app_share)

> 帖内提到的公司: 兴业证券

> **内容快照**:
> 
> 兴业证券海外研究TMT团队提供线上实习机会。
> 
> 该实习岗位属于卖方研究，覆盖TMT行业。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 线上实习|兴业证券海外研究TMT团队实习
> - 海外研究TMT团队

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a004d91000000003](https://www.xiaohongshu.com/discovery/item/6a004d910000000036000bfe?xsec_token=YBYM1cUi6i2AdR2d2EYp7gyzNSgGWMnMTf2wxGS2XvQqk%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 中金公司, 华泰证券, 中信建投证券, 国泰海通证券, 招商证券

> **内容快照**:
> 
> 投行招聘中，除了中金公司，大部分券商强调实习留用，面试越来越水，更看重实战能力。
> 
> 26年投行招聘仍是招聘大年，腰腿部券商提供更多机会，学历门槛下探。
> 
> 列举了15家开放投行暑期实习的券商和14家开放春季招聘的券商，其中4家同时开放。
> 
> 本科学历背景普通但实战能力突出的候选人，在26年拿到投行机会的可能性提升。
> 
> 投行面试越来越水，技术面试在绝大部分券商涉及不到。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 除了中金公司以外，其他大部分券商都强调“实习留用”...投行的面试越来越水了。
> - 26年仍会是投行的招聘大年...腰腿部券商投行给了大家更多的“选择权”...学历相对没那么优秀，26年有更多的加入投行的机会和可能性。
> - 至少包括15家：中信证券、中金公司、华泰证券...至少包括14家：招商证券、国联民生证券...同时开放暑期实习和春季招聘的投行，包括4家：招商证券、国联民生证券、东吴证券、西部证券。

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000](https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000702ace7?xsec_token=YB9MVh1sELWdJvRY7-4rURZo9qtVNwXXJJLAGIjlCzytE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 中金公司, 华泰证券, 中信建投证券, 申万宏源

> **内容快照**:
> 
> 中信证券多项业务指标连年夺魁，是券商中的'神'级公司。
> 
> 国泰海通由国开君安和海通证券合成，资本实力跃居行业榜首。
> 
> 中金公司是首家中外合资投行，投行业务标杆。
> 
> 华泰证券是金融科技+财富管理领域的标杆。
> 
> 中信建投证券降薪严重，与前三个相比掉队。
> 
> 2025年证券行业呈现'强者恒强'的马太效应，头部券商占据大部分市场份额。
> 
> 头部券商总部前台岗求职难度不输国有总行，建议根据学历背景和实习相关性合理选择。
> 
> 随着大A慢牛市场，证券公司实习机会增多，26届应把握机会。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 中信证券可以单独开一个'神'级，多项业务指标连年夺魁
> - 国泰海通由国开君安和海通证券合成而成的新龙头，资本实力跃居行业榜首
> - 中金公司，首家中外合资投行，投行业务标杆

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a00852d000000000](https://www.xiaohongshu.com/discovery/item/6a00852d0000000008002bb5?xsec_token=YBYM1cUi6i2AdR2d2EYp7gy0jrM93HeTyqyT4_9HsqWHE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 华泰证券, 中金证券, 中信建投, 招商证券

> **内容快照**:
> 
> 券商分为五个梯队，第一梯队包括中信证券、国泰海通、华泰证券、中金证券、中信建投等，平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> 
> 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> 
> 第一梯队偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历更加分。
> 
> 第三梯队门槛相对灵活，海外院校、转专业同学都有机会，关键是简历里要体现对金融行业的理解。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> - 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> - 通常更偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历会更加分。

**[投行 IBD]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69e9e830000000002](https://www.xiaohongshu.com/discovery/item/69e9e8300000000020007004?xsec_token=YBc11JooR0NZ98F21otDUFVYPtpfcbAB15sOU99-7Wv0g%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 中金公司, 华泰证券, 国泰海通, 中信建投, 申万宏源

> **内容快照**:
> 
> 国内券商存在明显的等级鄙视链，夯梯队（三中一华+国君海通）为投行天花板，项目资源多、薪资顶流，但门槛极高，要求清北复交+海外名校硕及头部实习经历。
> 
> 应届生求职建议包括：能冲夯梯队和顶级梯队直接冲；想回老家发展的优先看本地龙头券商；实习比空学历重要；不要死磕投行，研究所、财富管理、金融科技竞争小且发展空间不差。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 中信证券、中金公司、华泰证券、国泰海通、中信建投...项目资源多到做不完，薪资顶流，应届生base普遍20w+...门槛也真的🐮：清北复交+海外名校硕是基本盘
> - 能冲夯梯队+顶级梯队直接冲...想回老家发展的，优先看人上人里的本地龙头券商...实习＞空学历！...别死磕投行，研究所、财富管理、金融科技竞争小很多

_(+5 条更多帖未展示, 同 sub_cat)_

---

### 94. 凯雷投资

- **tier**: 头部PE
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: PE投后VC行研 (1)
- **industry_focus**: TMT, 消费
- **source 标签**: saif:2025
- **notes**:
  - [PE投后VC行研] 外资 PE

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2025 | 凯雷投资集团 | 行业研究员 | 1 | 私募 |

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 95. 华富基金

- **tier**: 二线公募
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 信用研究员 (1)
- **industry_focus**: 城投
- **source 标签**: taxonomy_doc
- **notes**:
  - [信用研究员] 公募固收信用

#### XHS 帖证据 (1 条)

**[信用研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69bd466d000000001](https://www.xiaohongshu.com/discovery/item/69bd466d000000001a0220cf?xsec_token=YBtYHnhwa3KBh9ber4X-aNuMy6sISaVh4neXgzH_59nR8%3D&xsec_source=app_share)

> 帖内提到的公司: 华富基金, 华富利得

> **内容快照**:
> 
> 华富基金2026年度日常实习生招募，包含固定收益投研、专户投研支持等岗位，要求经管/金工硕博背景，熟练使用Wind/Python。
> 
> 固定收益投研实习生主要职责为研报跟踪、数据处理，要求经管/金工硕博背景，熟练使用Wind/Python，有固收实习经验优先。
> 
> 专户投研支持实习生主要职责为FICC体系构建、专题研究，要求硕博学历，具备较强的数据抓取及分析能力。
> 
> 投资业务助理实习生（子公司华富利得）主要职责为投资辅助工作、尽调资料汇总、策略配置支持，要求数理功底扎实。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 华富基金2026年度日常实习生招募 - 上海
> - 固定收益投研实习生：主要职责：研报跟踪、数据处理；任职要求：经管/金工硕博背景，熟练使用Wind/Python，有固收实习经验可优先考虑
> - 专户投研支持实习生：主要职责：FICC体系构建、专题研究；任职要求：硕博学历，具备较强的数据抓取及分析能力

---

### 96. 华平投资

- **tier**: 头部PE
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: PE投后VC行研 (1)
- **industry_focus**: TMT, 消费
- **source 标签**: saif:2025
- **notes**:
  - [PE投后VC行研] 外资 PE

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2025 | 华平投资 | 行业研究员 | 1 | 私募 |

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 97. 华泰资产

- **tier**: 保险资管
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 利率宏观策略 (1)
- **industry_focus**: 金融
- **source 标签**: xhs:利率宏观策略:1
- **notes**:
  - [利率宏观策略] 保险资管

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 98. 博时基金

- **tier**: 二线公募
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 公募指数研究员 (1)
- **industry_focus**: 周期
- **source 标签**: common_knowledge:头部公募
- **notes**:
  - [公募指数研究员] 按行业共识

#### XHS 帖证据 (3 条)

**[行业研究员·消费]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68523924000000002](https://www.xiaohongshu.com/discovery/item/685239240000000022028983?xsec_token=YB1tOVHt4MrRCgE3YRmfKUfzkX4Zhwklu8QU9qotk8kHY%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达, 华夏, 博时, 国泰, 汇添富, 南方

> **内容快照**:
> 
> 易方达、华夏是头部公募，整体待遇好，科技岗位应届生薪资尤其高。
> 
> 博时、国泰、汇添富、南方类似公务员氛围。
> 
> 银行系公募（招商、中银、工银）薪资相对固化，待遇提升空间有限，但工作相对安逸。
> 
> 永赢、嘉实、鹏华待遇不错，但工作强度卷王级别。
> 
> 兴全待遇不错，人少资源多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 易方达、华夏：头部中的头部，整体待遇不会太差，据说科技岗位应届生薪资对比其他应届会尤其高一些
> - 博时、国泰、汇添富、南方：据说类似公务员氛围浓厚
> - 银行系包括（招商、中银、工银等）薪资相对固化，待遇可提升空间对比其他就不太行了，安逸也是相对的吧

**[财富管理FOF]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69b7adf5000000001](https://www.xiaohongshu.com/discovery/item/69b7adf5000000001d01e2cb?xsec_token=YBUbBPgCnu6HsJND6ndu6QErhvAcLeTam3vb19cHq1TBk%3D&xsec_source=app_share)

> 帖内提到的公司: 富国基金, 中欧基金, 易方达基金, 广发基金, 博时基金, 交银施罗德基金

> **内容快照**:
> 
> FOF（基金中的基金）近期在公募市场热度上升，发行数量和规模大幅增长，银行渠道推动明显，产品设计以短持有期、偏债混合策略为主。
> 
> FOF总规模突破3000亿，头部公司如富国、中欧、易方达、广发规模超200亿，但行业格局未固化。
> 
> FOF热度背后原因包括存款利率下行、市场波动大、银行渠道转型、产品设计适配等。
> 
> FOF行业趋势：从选基转向配置，产品形态纳入黄金ETF、REITs、QDII等，与养老联动。

> **verbatim 锚点 (T1/T3 抽取)**:
> - FOF（基金中的基金）突然成了公募市场的热门话题。截至3月14日，今年全市场已经有40只FOF成立，合计募了619.73亿元。跟去年一季度比，数量增加了233%，规模增长了361%。
> - 截至3月14日，FOF总规模突破3000亿。84家公募有布局，但头部还没固化：规模最大的管理人约245亿，规模超100亿的只有11家。第一梯队：富国、中欧、易方达、广发都超200亿。
> - 一是存款利率下行，叠加市场波动大，个人做择时、选基金的难度在增加。FOF的逻辑是通过专业选基+多资产配置，降低单一资产的波动。二是银行渠道从'卖产品'转向'卖配置方案'。三是产品设计的适配。

**[资管FOF]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68076825000000001](https://www.xiaohongshu.com/discovery/item/68076825000000001a0066db?xsec_token=YB99eH8k09Rv7rNLHjW60O0BTN6QzTKurNuAdNZ06-eic%3D&xsec_source=app_share)

> 帖内提到的公司: 交银施罗德基金, 兴证全球基金, 民生加银基金, 汇添富基金, 南方基金, 浦银安盛基金

> **内容快照**:
> 
> FOF行业规模从2021年的2253亿降至2024年底的1442亿，降幅36%，多家公司规模大幅缩水。
> 
> 交银施罗德基金FOF团队仅剩2名基金经理，规模排名从第一跌至第七。
> 
> 兴证全球基金FOF团队以林国怀为带头人，成员背景多元，包括互联网大厂和海外金融背景。
> 
> 易方达基金FOF团队由汪玲牵头，成员如刘淑霞有券商资管FOF业务负责人经验。
> 
> 中欧基金FOF团队由桑磊牵头，成员有险资投资管理经验。
> 
> 华夏基金FOF团队汇聚了许利民、廉赵峰、李晓易、卢少强等精兵强将。
> 
> 工银瑞信FOF团队赵志源接替蒋华安成为FOF投资部总经理并进入投委会，陈涵任研究副总监。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 截至2024年底，共有87家基金公司管理着511只FOF产品，资产净值规模合计1442亿元，相比2021年的2253亿降幅36%。
> - 交银施罗德FOF团队则仅见2人：刘兵，经济学博士，2016年加入交银施罗德基金；刘迪，金融工程与投资管理博士，2015年加入交银施罗德基金。
> - 兴证全球基金以公司总经理助理、FOF投资与金融工程部总监、养老金管理部总监林国怀为带头人，团队成员既有来自互联网大厂的成员，也有来自海外金融从业背景的成员。

---

### 99. 因诺资产

- **tier**: 中型量化私募
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 量化研究员·中频 (1)
- **industry_focus**: —
- **source 标签**: saif:2024
- **notes**:
  - [量化研究员·中频] SAIF 2024 量化命中

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 因诺资产管理有限公司 | 量化研究员 | 1 | 量化私募 |

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 100. 国信证券

- **tier**: 中型券商研究所
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 卖方研究员·TMT (1)
- **industry_focus**: TMT
- **source 标签**: taxonomy_doc
- **notes**:
  - [卖方研究员·TMT] TMT 中型卖方

#### XHS 帖证据 (5 条)

**[固收+多资产]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a03466a000000000](https://www.xiaohongshu.com/discovery/item/6a03466a000000000702f4c4?xsec_token=YBHOt7zneE8YP4HgVHcNE3uPkUsDCRauMCju0BEuxouic%3D&xsec_source=app_share)

> 帖内提到的公司: yfd, 德邦, 上银, 中银理财, 中邮理财, 信银理财

> **内容快照**:
> 
> 固收赛道相比权益bar略低，但近年越来越卷。
> 
> 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向。
> 
> 实习经历垂直会有一定优势，多段转债量化经历有助于秋招。
> 
> 暑期实习面试中，公募、理财子、券商、私募等均有面试经历，部分挂掉。
> 
> 多数市场化机构在暑期确定名额后秋招不开放。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 固收赛道相比权益bar略低，但是近年越来越卷
> - 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向
> - 实习经历垂直会有一定优势，猜测秋招发面是因为有多段转债量化经历

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69bbb886000000002](https://www.xiaohongshu.com/discovery/item/69bbb886000000002b00dc0f?xsec_token=YBY-rrGTG456s3Kutg82G2iAMfesSM55ZOeJkEKPkgzAA%3D&xsec_source=app_share)

> 帖内提到的公司: 三中一华, 广发证券, 招商证券, 国信证券

> **内容快照**:
> 
> 学生背景211本+中9硕，实习经历包括一段颈部券商股承做和两段TMT行研（新财富），未来可能路径为行研、投行、PE/VC。
> 
> 学生获得四个top15券商的实习offer：三中一华债、广发机械/通信（新财富）、招商TMT、国信债。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 🏠211本+中9硕，实习经历，一段颈部券商股承做，两段TMT行研（新财富）。未来的发展路径没有想好，可能是行研、投行、PE/VC。
> - 手上的实习offer（全是top15券商）1️⃣三中一华 债 2️⃣广 机械/通信（新财富）3️⃣招 TMT 4️⃣国x 债

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/670cedf9000000002](https://www.xiaohongshu.com/discovery/item/670cedf9000000002100b8f6?xsec_token=YBO19yrKkffSaVM7XfIJi0fFVjqF3UHWbgP-lQtppr1t0%3D&xsec_source=app_share)

> 帖内提到的公司: 国信互联网, 国信证券

> **内容快照**:
> 
> 卖方研究所互联网研究员岗位要求0-3年互联网、科技行业研究经验，强调深度研究、沟通能力和财务建模能力。
> 
> 国信证券（国信互联网）招聘卖方研究员，要求重点院校本硕，金融经济与科技背景均可。
> 
> 面试可能考察财务和搭建模型能力，以及文字和语言表达能力。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 0-3年内互联网、科技行业研究经验；踏实认真，勤奋细致，热爱深度研究，主观能动性强，对待工作有责任心。
> - 本硕为海内外重点院校毕业，金融经济与科技背景均可。
> - 可熟练使用办公与金融工作软件，财务和搭建模型能力扎实，文字和语言表达能力强。

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a00852d000000000](https://www.xiaohongshu.com/discovery/item/6a00852d0000000008002bb5?xsec_token=YBYM1cUi6i2AdR2d2EYp7gy0jrM93HeTyqyT4_9HsqWHE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 华泰证券, 中金证券, 中信建投, 招商证券

> **内容快照**:
> 
> 券商分为五个梯队，第一梯队包括中信证券、国泰海通、华泰证券、中金证券、中信建投等，平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> 
> 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> 
> 第一梯队偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历更加分。
> 
> 第三梯队门槛相对灵活，海外院校、转专业同学都有机会，关键是简历里要体现对金融行业的理解。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> - 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> - 通常更偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历会更加分。

**[投行 IBD]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69e9e830000000002](https://www.xiaohongshu.com/discovery/item/69e9e8300000000020007004?xsec_token=YBc11JooR0NZ98F21otDUFVYPtpfcbAB15sOU99-7Wv0g%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 中金公司, 华泰证券, 国泰海通, 中信建投, 申万宏源

> **内容快照**:
> 
> 国内券商存在明显的等级鄙视链，夯梯队（三中一华+国君海通）为投行天花板，项目资源多、薪资顶流，但门槛极高，要求清北复交+海外名校硕及头部实习经历。
> 
> 应届生求职建议包括：能冲夯梯队和顶级梯队直接冲；想回老家发展的优先看本地龙头券商；实习比空学历重要；不要死磕投行，研究所、财富管理、金融科技竞争小且发展空间不差。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 中信证券、中金公司、华泰证券、国泰海通、中信建投...项目资源多到做不完，薪资顶流，应届生base普遍20w+...门槛也真的🐮：清北复交+海外名校硕是基本盘
> - 能冲夯梯队+顶级梯队直接冲...想回老家发展的，优先看人上人里的本地龙头券商...实习＞空学历！...别死磕投行，研究所、财富管理、金融科技竞争小很多

---

### 101. 国泰基金

- **tier**: 二线公募
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 行业研究员·TMT-医药-周期 (1)
- **industry_focus**: TMT
- **source 标签**: saif:2024
- **notes**:
  - [行业研究员·TMT-医药-周期] SAIF 2024 命中

#### SAIF 校友流向证据 (2 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 国泰基金管理有限公司 | 行业研究员 | 1 | 公募基金 |
| 2024 | 国泰君安证券股份有限公司 | 卖方分析师 | 1 | 券商研究所 |

#### XHS 帖证据 (29 条)

**[卖方研究员·宏观策略]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/69b90ca1000000002](https://www.xiaohongshu.com/discovery/item/69b90ca10000000023021f8d?xsec_token=YBYhJN9E0l4EYISbz8EyT45yhJlVJg1vFoGq71jBMKgl8%3D&xsec_source=app_share)

> 帖内提到的公司: 国泰海通, 国泰君安, 海通证券

> **内容快照**:
> 
> 国泰海通暑期实习岗位复杂，涵盖投行、权益研究、固收、机构销售等大类，其中固收销售交易HC最多。
> 
> 国泰君安和海通证券并购整合仍在进行，岗位分布复杂反映了权力重新分配。
> 
> 国泰海通暑期实习期6-10月，长达5个月，不利于海归学生，且投行HC不确定，成本高。
> 
> 国泰海通卡本科学历，对投行实习要求有所放宽。

> **verbatim 锚点 (T1/T3 抽取)**:
> - HC最多的，我认为是固收销售交易（销售交易）这个岗位。
> - 国泰君安和海通证券的并购整合和权力重新分配还在“持续进行”。
> - 今年的实习期是6-10月，可以说非常不利于海归同学们了。

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

**[公募基金中后台]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69bcd0e1000000001](https://www.xiaohongshu.com/discovery/item/69bcd0e1000000001a035c38?xsec_token=YBn8TO43p-qWCpgiMFhkVlLpWUOLIcupWnN8XtIXuDJBY%3D&xsec_source=app_share)

> 帖内提到的公司: 国泰海通证券资管

> **内容快照**:
> 
> REITs实习岗位职责包括存续期管理、投研体系搭建、项目尽调等
> 
> 国泰海通证券资管提供REITs实习岗位，要求4月中下旬到岗，每周至少3天，在岗3个月可开实习证明，有餐补无工资

> **verbatim 锚点 (T1/T3 抽取)**:
> - 协助基金经理开展REITs存续期全流程管理，包括底层基础设施资产运营监控、合规信息披露支持、投资者关系辅助等；参与REITs投研体系搭建，涵盖行业政策解读、底层资产市场动态分析、估值模型数据校验与参数优化、投研报告撰写等；辅助完成项目尽调资料整理、运营数据可视化呈现、投决会议材料汇编等支持性工作。
> - 4月中下旬到岗，每周至少 3 天，在岗时间3个月开具实习证明。实习生提供每日餐补，无工资补贴

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0ffa47000000003](https://www.xiaohongshu.com/discovery/item/6a0ffa470000000035023ff5?xsec_token=YBW5wlEnp0s0ohdjGrzIcUZSwEuW2KOf2ZdepxHsfM_U4%3D&xsec_source=app_share)

> 帖内提到的公司: 国泰海通

> **内容快照**:
> 
> 国泰海通TMT行研实习岗位职责包括数据库更新、会议纪要、协助研究员完成课题研究和报告写作等。
> 
> 国泰海通是一家头部券商，提供TMT行业研究实习岗位。
> 
> 任职要求包括国内外重点高校本科/硕士在读，TMT相关背景优先，具备金融知识基础和行研实习经历优先。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 定期数据库更新，会议纪要整理；参与投研工作，按照要求完成信息的搜索、整理及分析等任务；协助研究员完成相关行业及公司的课题研究项目，及研究报告写作；掌握行业研究方法后，实习一定时间后可尝试独立攥写研报。
> - 国泰海通TMT行研实习
> - 国内外重点高校本科、硕士在读，专业不限，但具有TMT等相关背景优先，通信、电子、物理、AI等专业的同学优先；具备一定的金融知识基础，有行研实习经历的同学优先。

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a034ce9000000003](https://www.xiaohongshu.com/discovery/item/6a034ce9000000003701f79c?xsec_token=YBiorUJgroJaDhf9F0epy4RzLo8wRybNzyR_-Iqve3CMI%3D&xsec_source=app_share)

> 帖内提到的公司: 国泰海通

> **内容快照**:
> 
> 国泰海通招聘TMT行研实习生，要求实习期不少于3个月，每周4天以上，工作内容包括数据库更新、会议纪要、信息搜集、协助报告等。
> 
> 国泰海通是一家券商，提供行研实习岗位。
> 
> 该岗位聚焦TMT行业，偏好有TMT背景（通信、电子、物理、AI等专业）的学生。
> 
> 加分项包括TMT背景、行研实习经历、金融知识基础。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 国泰海通 TMT行研实习生
> - 国泰海通
> - TMT背景（通信、电子、物理、AI等专业）

**[卖方研究员·TMT]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a02b1fc000000003](https://www.xiaohongshu.com/discovery/item/6a02b1fc00000000360304f2?xsec_token=YB9UsTpUMt8TpAjXfIui9LxS4hRlTfcO__0ZhRoYDAkIo%3D&xsec_source=app_share)

> 帖内提到的公司: 国泰海通

> **内容快照**:
> 
> 国泰海通招聘TMT行业研究实习生，要求一周4天以上，实习期不少于3个月，工作内容包括数据库更新、会议纪要、协助研究等，有独立撰写研报机会。
> 
> 国泰海通提供行研实习岗位，支持官邮背调，线下实习可出具实习证明。
> 
> 实习要求包括思维敏锐、数据搜集处理能力、共情能力和积极性、能承受压力接受加班，具有TMT背景优先。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 国泰海通 · TMT行研实习生
> - 支持官邮背调，线下实习可出具实习证明
> - 思维敏锐清晰，具有良好的数据搜集和处理能力

_(+23 条更多帖未展示, 同 sub_cat)_

---

### 102. 国金证券

- **tier**: 中型券商研究所
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 卖方研究员·消费医药周期 (1)
- **industry_focus**: 消费
- **source 标签**: xhs:卖方研究员·消费医药周期:3
- **notes**:
  - [卖方研究员·消费医药周期] 中型卖方

#### XHS 帖证据 (6 条)

**[固收+多资产]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/6a03466a000000000](https://www.xiaohongshu.com/discovery/item/6a03466a000000000702f4c4?xsec_token=YBHOt7zneE8YP4HgVHcNE3uPkUsDCRauMCju0BEuxouic%3D&xsec_source=app_share)

> 帖内提到的公司: yfd, 德邦, 上银, 中银理财, 中邮理财, 信银理财

> **内容快照**:
> 
> 固收赛道相比权益bar略低，但近年越来越卷。
> 
> 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向。
> 
> 实习经历垂直会有一定优势，多段转债量化经历有助于秋招。
> 
> 暑期实习面试中，公募、理财子、券商、私募等均有面试经历，部分挂掉。
> 
> 多数市场化机构在暑期确定名额后秋招不开放。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 固收赛道相比权益bar略低，但是近年越来越卷
> - 低利率时代建议关注多资产、量化、转债、国债期货等固收+方向
> - 实习经历垂直会有一定优势，猜测秋招发面是因为有多段转债量化经历

**[利率宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/65d1b8ba000000000](https://www.xiaohongshu.com/discovery/item/65d1b8ba0000000007004ffa?xsec_token=YB89jGF1lO7RYoY1dqv_1dX_n7IaKqIKa69o-pyhsGts0%3D&xsec_source=app_share)

> 帖内提到的公司: 郭磊宏观茶座, 一瑜中的, Kevin策略研究, 华泰证券固收研究, 郁言债市, 固收亮话

> **内容快照**:
> 
> 宏观/固收研究日常工作需要大量阅读，包括新闻、数据、机构报告和专家评论。
> 
> 卖方机构报告更新频繁，每天1-3篇，需要筛选有效信息。
> 
> 推荐了多个宏观/固收研究资源，包括卖方、买方、论坛和野生大佬。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 投研日常工作需要大量读东西，除了新闻和数据，机构报告还有各路大佬评论这些去哪看怎么看
> - 每个板块基本都有独立的号，并且大部分都是保持每天1-3篇的更新量
> - 下面盘一盘宏观/固收两个板块我日常都会看什么

**[利率宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69e60c71000000001](https://www.xiaohongshu.com/discovery/item/69e60c71000000001a036863?xsec_token=YBgxfelF6pOvvQ3lvrOeuANLCOt7CLJSMTLB_Vd8Bcm4E%3D&xsec_source=app_share)

> 帖内提到的公司: 光大, 天风, 东财, 国金, 浙商, 东北

> **内容快照**:
> 
> 学生目标岗位为券商自营部门的偏债或宏观方向，关注校招画像、待遇和发展情况。
> 
> 学生提及的中型券商自营部门包括光大、天风、东财、国金、浙商、东北等。
> 
> 学生询问校招是否是好选择以及进入机会。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 目标偏债或者宏观的二级（了解到一些新增的集中在资产配置方向）
> - 包括不限于如光大，天风，东财，国金，浙商，东北等券商的自营部门
> - 校招是好的选择吗，有机会进吗？

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a004d91000000003](https://www.xiaohongshu.com/discovery/item/6a004d910000000036000bfe?xsec_token=YBYM1cUi6i2AdR2d2EYp7gyzNSgGWMnMTf2wxGS2XvQqk%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 中金公司, 华泰证券, 中信建投证券, 国泰海通证券, 招商证券

> **内容快照**:
> 
> 投行招聘中，除了中金公司，大部分券商强调实习留用，面试越来越水，更看重实战能力。
> 
> 26年投行招聘仍是招聘大年，腰腿部券商提供更多机会，学历门槛下探。
> 
> 列举了15家开放投行暑期实习的券商和14家开放春季招聘的券商，其中4家同时开放。
> 
> 本科学历背景普通但实战能力突出的候选人，在26年拿到投行机会的可能性提升。
> 
> 投行面试越来越水，技术面试在绝大部分券商涉及不到。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 除了中金公司以外，其他大部分券商都强调“实习留用”...投行的面试越来越水了。
> - 26年仍会是投行的招聘大年...腰腿部券商投行给了大家更多的“选择权”...学历相对没那么优秀，26年有更多的加入投行的机会和可能性。
> - 至少包括15家：中信证券、中金公司、华泰证券...至少包括14家：招商证券、国联民生证券...同时开放暑期实习和春季招聘的投行，包括4家：招商证券、国联民生证券、东吴证券、西部证券。

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000](https://www.xiaohongshu.com/discovery/item/6a0f1d3e000000000702ace7?xsec_token=YB9MVh1sELWdJvRY7-4rURZo9qtVNwXXJJLAGIjlCzytE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 中金公司, 华泰证券, 中信建投证券, 申万宏源

> **内容快照**:
> 
> 中信证券多项业务指标连年夺魁，是券商中的'神'级公司。
> 
> 国泰海通由国开君安和海通证券合成，资本实力跃居行业榜首。
> 
> 中金公司是首家中外合资投行，投行业务标杆。
> 
> 华泰证券是金融科技+财富管理领域的标杆。
> 
> 中信建投证券降薪严重，与前三个相比掉队。
> 
> 2025年证券行业呈现'强者恒强'的马太效应，头部券商占据大部分市场份额。
> 
> 头部券商总部前台岗求职难度不输国有总行，建议根据学历背景和实习相关性合理选择。
> 
> 随着大A慢牛市场，证券公司实习机会增多，26届应把握机会。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 中信证券可以单独开一个'神'级，多项业务指标连年夺魁
> - 国泰海通由国开君安和海通证券合成而成的新龙头，资本实力跃居行业榜首
> - 中金公司，首家中外合资投行，投行业务标杆

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a00852d000000000](https://www.xiaohongshu.com/discovery/item/6a00852d0000000008002bb5?xsec_token=YBYM1cUi6i2AdR2d2EYp7gy0jrM93HeTyqyT4_9HsqWHE%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 国泰海通, 华泰证券, 中金证券, 中信建投, 招商证券

> **内容快照**:
> 
> 券商分为五个梯队，第一梯队包括中信证券、国泰海通、华泰证券、中金证券、中信建投等，平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> 
> 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> 
> 第一梯队偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历更加分。
> 
> 第三梯队门槛相对灵活，海外院校、转专业同学都有机会，关键是简历里要体现对金融行业的理解。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 平台越头部，项目资源、客户质量、培训体系和简历认可度通常越强，但入职门槛也更高。
> - 券商求职不是只看公司名字，更要看岗位内容、业务条线和你的背景匹配度。
> - 通常更偏好985/211、海外名校、金融/经济/会计/理工复合背景，有头部券商、基金、咨询、四大实习经历会更加分。

---

### 103. 小米

- **tier**: 互联网大厂
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: AI算法业务 (1)
- **industry_focus**: AI 应用层
- **source 标签**: taxonomy_doc
- **notes**:
  - [AI算法业务] 推荐/广告算法

#### XHS 帖证据 (1 条)

**[Agent工程师]** (relevance=0.30) — [https://www.xiaohongshu.com/discovery/item/697c4ad2000000000](https://www.xiaohongshu.com/discovery/item/697c4ad2000000000c0353d8?xsec_token=YBuDmvXxcuij8fN_uhBQhpPbLvlTR2wGDSZoypG9xxuXM%3D&xsec_source=app_share)

> 帖内提到的公司: 阿里淘天, 美团, 百度, 小米, 米哈游, taptap

> **内容快照**:
> 
> 面试中大部分还是围绕项目进行深挖提问，以及相关的八股，能和面试官聊起来一般就问题不大，手撕也不是很难，面试官也会提示。
> 
> 0论文0实习，华五本硕，27届，第一段日常实习入职阿里淘天ai agent岗。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 面试中大部分还是围绕项目进行深挖提问，以及相关的八股，能和面试官聊起来一般就问题不大，手撕也不是很难，面试官也会提示。
> - bg 27届华五本硕 0论文0实习 第一段日常入职阿里淘天ai agent岗

---

### 104. 建设银行

- **tier**: 银行系资管
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 财富管理FOF (1)
- **industry_focus**: 金融
- **source 标签**: xhs:财富管理FOF:1
- **notes**:
  - [财富管理FOF] 国有大行财富

#### XHS 帖证据 (1 条)

**[财富管理FOF]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69b7adf5000000001](https://www.xiaohongshu.com/discovery/item/69b7adf5000000001d01e2cb?xsec_token=YBUbBPgCnu6HsJND6ndu6QErhvAcLeTam3vb19cHq1TBk%3D&xsec_source=app_share)

> 帖内提到的公司: 富国基金, 中欧基金, 易方达基金, 广发基金, 博时基金, 交银施罗德基金

> **内容快照**:
> 
> FOF（基金中的基金）近期在公募市场热度上升，发行数量和规模大幅增长，银行渠道推动明显，产品设计以短持有期、偏债混合策略为主。
> 
> FOF总规模突破3000亿，头部公司如富国、中欧、易方达、广发规模超200亿，但行业格局未固化。
> 
> FOF热度背后原因包括存款利率下行、市场波动大、银行渠道转型、产品设计适配等。
> 
> FOF行业趋势：从选基转向配置，产品形态纳入黄金ETF、REITs、QDII等，与养老联动。

> **verbatim 锚点 (T1/T3 抽取)**:
> - FOF（基金中的基金）突然成了公募市场的热门话题。截至3月14日，今年全市场已经有40只FOF成立，合计募了619.73亿元。跟去年一季度比，数量增加了233%，规模增长了361%。
> - 截至3月14日，FOF总规模突破3000亿。84家公募有布局，但头部还没固化：规模最大的管理人约245亿，规模超100亿的只有11家。第一梯队：富国、中欧、易方达、广发都超200亿。
> - 一是存款利率下行，叠加市场波动大，个人做择时、选基金的难度在增加。FOF的逻辑是通过专业选基+多资产配置，降低单一资产的波动。二是银行渠道从'卖产品'转向'卖配置方案'。三是产品设计的适配。

---

### 105. 开源证券

- **tier**: 中型券商研究所
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 行业研究员·消费 (1)
- **industry_focus**: 消费
- **source 标签**: xhs:行业研究员·消费:2
- **notes**:
  - [行业研究员·消费] XHS 消费组 2 次

#### XHS 帖证据 (4 条)

**[利率宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a168e08000000020](https://www.xiaohongshu.com/discovery/item/6a168e0800000002080390a6?xsec_token=YBDr8fia9AsTfKUqr5MRCUWIWxTYf32d5gC-uh2UwuAUs%3D&xsec_source=app_share)

> 帖内提到的公司: 港大开源版

> **内容快照**:
> 
> Vibe-Trading 是多智能体 AI 投研框架，具备宏观策略所需的核心要素，包括全市场覆盖、宏观数据接入、新闻/情绪分析、跨资产联动、自然语言到策略。
> 
> 该框架覆盖全球宏观与资产配置，涉及 A股/港美股/期货/外汇/加密货币，以及宏观经济分析、地缘政治事件驱动、跨资产配置等。

> **verbatim 锚点 (T1/T3 抽取)**:
> - Vibe-Trading（vibe-trading-ai）是多智能体 AI 投研框架，不是传统意义上的宏观对冲基金系统，但具备宏观策略所需的核心要素
> - 全球宏观与资产配置测试

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a004d91000000003](https://www.xiaohongshu.com/discovery/item/6a004d910000000036000bfe?xsec_token=YBYM1cUi6i2AdR2d2EYp7gyzNSgGWMnMTf2wxGS2XvQqk%3D&xsec_source=app_share)

> 帖内提到的公司: 中信证券, 中金公司, 华泰证券, 中信建投证券, 国泰海通证券, 招商证券

> **内容快照**:
> 
> 投行招聘中，除了中金公司，大部分券商强调实习留用，面试越来越水，更看重实战能力。
> 
> 26年投行招聘仍是招聘大年，腰腿部券商提供更多机会，学历门槛下探。
> 
> 列举了15家开放投行暑期实习的券商和14家开放春季招聘的券商，其中4家同时开放。
> 
> 本科学历背景普通但实战能力突出的候选人，在26年拿到投行机会的可能性提升。
> 
> 投行面试越来越水，技术面试在绝大部分券商涉及不到。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 除了中金公司以外，其他大部分券商都强调“实习留用”...投行的面试越来越水了。
> - 26年仍会是投行的招聘大年...腰腿部券商投行给了大家更多的“选择权”...学历相对没那么优秀，26年有更多的加入投行的机会和可能性。
> - 至少包括15家：中信证券、中金公司、华泰证券...至少包括14家：招商证券、国联民生证券...同时开放暑期实习和春季招聘的投行，包括4家：招商证券、国联民生证券、东吴证券、西部证券。

**[行业研究员·消费]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69ee3727000000003](https://www.xiaohongshu.com/discovery/item/69ee3727000000003601f863?xsec_token=YBwRvoe0f0Njvu562Ivw62eJYNVHGKIdspbvCA-fm4KDg%3D&xsec_source=app_share)

> 帖内提到的公司: 开源证券

> **内容快照**:
> 
> 开源证券研究所新消费-商社组招聘行业研究暑期实习生，研究方向包括黄金珠宝、化妆品、医美等，有留用机会。
> 
> 开源证券研究所新消费-商社组为2025证券时报（XCF）获奖团队。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 团队为2025证券时报（XCF）获奖团队。

**[行业研究员·消费]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a028a46000000000](https://www.xiaohongshu.com/discovery/item/6a028a460000000008033b54?xsec_token=YB-EPCkDMCoBUapj9HmnsbjLzSaSk0FUd1uSO12_i8gH0%3D&xsec_source=app_share)

> 帖内提到的公司: 开源证券

> **内容快照**:
> 
> 开源证券研究所新消费-商社组招聘暑期实习生，研究方向包括黄金珠宝、化妆品、医美、酒店餐饮、旅游景区、免税、互联网电商、超市零售等。
> 
> 开源证券研究所暑期实习生有留用名额，面向2027年6月以后毕业的硕士及以上在校生。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 开源证券研究所【新消费-商社组】行业研究暑期实习生
> - 暑期实习生（对应27年6月毕业）有留用名额。

---

### 106. 拼多多

- **tier**: 互联网大厂
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: AI算法业务 (1)
- **industry_focus**: AI 应用层
- **source 标签**: common_knowledge:头部电商
- **notes**:
  - [AI算法业务] 按行业共识,电商推荐算法

#### XHS 帖证据 (1 条)

**[多模态推理优化]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69fec4c0000000003](https://www.xiaohongshu.com/discovery/item/69fec4c00000000037037dbe?xsec_token=YBmlLg2uWh_lvMnSZxDHuZ2V4OgGCX8r6chmzqpEoIeMU%3D&xsec_source=app_share)

> 帖内提到的公司: 腾讯, 字节跳动, 阿里巴巴, 美团, 拼多多, 百度

> **内容快照**:
> 
> 腾讯研发实习生薪资从7500涨至13000（含2000房补），涨幅超50%
> 
> 大厂集体上调实习生薪资，AI人才争夺激烈
> 
> 腾讯顶尖人才通过'青云计划'薪酬上不封顶，日薪可达5500元
> 
> 互联网行业重心转向AI，技术岗实习生迎来春天

> **verbatim 锚点 (T1/T3 抽取)**:
> - 去年月薪7500。今年直接干到13000（含2000房补）。一年涨了50%。
> - 大厂集体砸钱，本质是盯上了'AI原生代'
> - 顶尖人才通过'青云计划'：薪酬上不封顶。日薪可达5500元。

---

### 107. 摩根大通

- **tier**: 外资行
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 利率宏观策略 (1)
- **industry_focus**: 金融
- **source 标签**: xhs:利率宏观策略:1
- **notes**:
  - [利率宏观策略] 外资行宏观利率

#### XHS 帖证据 (1 条)

**[利率宏观策略]** (relevance=0.30) — [https://www.xiaohongshu.com/discovery/item/69329c12000000000](https://www.xiaohongshu.com/discovery/item/69329c12000000000d039884?xsec_token=YBgBjgzADyhN4b2tkRg5EIfoLRLu5K8Trh772BVt5qAJw%3D&xsec_source=app_share)

> 帖内提到的公司: 摩根大通, 贝莱德

> **内容快照**:
> 
> 摩根大通2026年全球投资展望，强调资产配置回到正确位置，债券要配但需聪明配，股票提高美国以外权重，AI投资主线从创新者向采用者扩散。
> 
> AI投资主线从创新者向采用者扩散，涉及工业、公用事业、医疗金融等行业。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 2026 资产配置：回到正确位置 (“Get Back Onside”)
> - AI 投资主线从“创新者”→“采用者”扩散

---

### 108. 摩根资产管理

- **tier**: 外资行
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 公募指数研究员 (1)
- **industry_focus**: TMT
- **source 标签**: xhs:公募指数研究员:1
- **notes**:
  - [公募指数研究员] 外资指数产品

#### XHS 帖证据 (6 条)

**[买方 Quant]** (relevance=0.90) — [https://www.xiaohongshu.com/discovery/item/695940c8000000001](https://www.xiaohongshu.com/discovery/item/695940c8000000001e03a19c?xsec_token=YBrJ_goExM-LGFpD_KXswc_GrNMq5jKropLNK56upboAU%3D&xsec_source=app_share)

> 帖内提到的公司: 高盛, 摩根士丹利, 中金, 中信里昂, 幻方, 灵均

> **内容快照**:
> 
> 大湾区量化岗位分为卖方Quant（投行）和买方Quant（基金/私募），卖方Quant集中在香港，买方Quant在深圳更活跃。
> 
> 香港的卖方Quant主要集中在国际投行（高盛、摩根士丹利等）和中资投行国际子公司（中金、中信里昂），深圳的卖方机会在国内券商的金融工程/量化自营部门。
> 
> 深圳的买方Quant核心是顶尖量化私募（幻方、灵均等），香港的买方Quant包括全球顶级对冲基金和自营交易公司（Citadel, Two Sigma, Optiver等）。
> 
> 深圳的量化岗位面试必考对国内金融数据源（Wind, Tushare, JoinQuant）和A股交易规则的熟悉度。
> 
> 香港的量化岗位面试对期权定价、随机微积分等理论要求更深。
> 
> 深圳偏好国内顶尖理工院校（清北复交、浙大、中科大等）的硕士/博士，海外名校需对国内市场有理解；香港偏好全球顶级名校（美英顶尖高校、新加坡两所、港三所），专业排名比学校综合排名更重要。
> 
> 纯金融背景竞争力弱，数学、物理、计算机、电子工程等硬核专业是绝对主流。
> 
> 大湾区量化岗位技能要求：Python、SQL、Linux是基础；深圳需精通C++，香港需英语工作能力和kdb+/q等工具。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 在大湾区，两者的重心和机会有显著差异：1. 卖方Quant（以投行为主）：香港是绝对中心...2. 买方Quant（以基金/私募为主）：深圳是核心战场...
> - 国际投行（高盛、摩根士丹利等）及中资投行的国际子公司（中金、中信里昂等）的量化团队主要聚集于香港。
> - 深圳是核心战场：聚集了全国最顶尖、最活跃的量化私募（幻方、灵均等）...香港是国际桥头堡：云集了全球顶级对冲基金和自营交易公司（Citadel, Two Sigma, Optiver等）

**[公募指数研究员]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a06e576000000000](https://www.xiaohongshu.com/discovery/item/6a06e57600000000060203dd?xsec_token=YBG4oMV0GM4EvWWfreDkf8CNldd4GiWDoLVZq1kwR9yoQ%3D&xsec_source=app_share)

> 帖内提到的公司: 摩根资产管理, 摩根基金

> **内容快照**:
> 
> 公募基金产品经理需要基于行业趋势、客户需求、投研判断与监管导向等多重因素设计产品，而非简单追风口。
> 
> 公募基金行业管理规模持续增长、产品供给日益丰富。
> 
> 摩根资产管理资深产品经理刘楠在复旦大学分享公募基金产品发展趋势。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 基金产品的设计要基于行业趋势、客户需求、投研判断与监管导向等多重因素，远非“追风口”那么简单。
> - 公募基金行业管理规模持续增长、产品供给日益丰富
> - 摩根资产管理走进复旦大学管理学院，资深产品经理刘楠作为主讲嘉宾，分享了公募基金行业的发展现状与投资思考。

**[利率宏观策略]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68aadd77000000001](https://www.xiaohongshu.com/discovery/item/68aadd77000000001c03321a?xsec_token=YBGhbE1zi9BRM_QtzvKf4IPJ1Rq387AvBqXvWfFQ0HI98%3D&xsec_source=app_share)

> 帖内提到的公司: 摩根士丹利

> **内容快照**:
> 
> 作者在摩根士丹利伦敦办公室做宏观固收研究暑期实习，描述为'愚蠢热忱'，并表达了对这段经历的喜爱。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 伦敦大摩｜宏观固收研究暑期记忆｜愚蠢热忱

**[卖方研究员·消费医药周期]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6936a816000000001](https://www.xiaohongshu.com/discovery/item/6936a816000000001e013f4e?xsec_token=YBpCiQVBzdmjUenwrjY9Db287T6DF4auUUVmHa1Ksf51w%3D&xsec_source=app_share)

> 帖内提到的公司: 摩根士丹利

> **内容快照**:
> 
> 大摩闭门会讨论保险长期增长和超配中国平安，涉及保险行业投研观点。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 大摩闭门会｜保险长期增长和超配中国平安

**[量化研究员·高频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a15a138000000003](https://www.xiaohongshu.com/discovery/item/6a15a138000000003501dd25?xsec_token=YBJXceSEhkLQc7puTGKMxN_p_R9jpYHzgNTvXgnWHFQ5c%3D&xsec_source=app_share)

> 帖内提到的公司: Citadel, Jane Street, Two Sigma, Optiver, IMC, SIG

> **内容快照**:
> 
> 量化行业机构梯队分为顶级买方（Citadel、Jane Street、Two Sigma）、一线做市商（Optiver、IMC等）、知名对冲基金（Balyasny、Bridgewater等）、成长型量化机构（DRW、Schonfeld等）、卖方&资管（高盛、BlackRock等）和加密量化（Jump Crypto等）。
> 
> 初级岗位薪资参考：顶级买方entry级可达$300k+，不同机构薪资差异大。
> 
> 不同梯队机构考察重点不同：顶级买方和做市商更看重算法题、数学推导和工程实现；资管岗更偏向因子建模和业务理解。
> 
> 低年级可以参加IMC、Optiver的交易赛积累项目经历。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 买方（God Tier）以 Citadel、Jane Street、Two Sigma 为代表...一线做市商包括 Optiver、IMC、SIG、HRT、Jump Trading 等...知名对冲基金比如 Balyasny、Bridgewater、D.E. Shaw 等...成长型量化机构以 DRW、Schonfeld、Tower Research 为代表...卖方 & 资管量化岗投行（高盛、摩根士丹利、小摩等）和资管巨头（BlackRock、Vanguard、State Street 等）...加密量化赛道还有 Jump Crypto、Wintermute、GSR 等
> - Citadel 的 entry 级岗位可达 $300k+
> - 顶级买方和做市商更看重算法题、数学推导和工程实现，资管岗则更偏向因子建模和业务理解。

**[利率宏观策略]** (relevance=0.30) — [https://www.xiaohongshu.com/discovery/item/69329c12000000000](https://www.xiaohongshu.com/discovery/item/69329c12000000000d039884?xsec_token=YBgBjgzADyhN4b2tkRg5EIfoLRLu5K8Trh772BVt5qAJw%3D&xsec_source=app_share)

> 帖内提到的公司: 摩根大通, 贝莱德

> **内容快照**:
> 
> 摩根大通2026年全球投资展望，强调资产配置回到正确位置，债券要配但需聪明配，股票提高美国以外权重，AI投资主线从创新者向采用者扩散。
> 
> AI投资主线从创新者向采用者扩散，涉及工业、公用事业、医疗金融等行业。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 2026 资产配置：回到正确位置 (“Get Back Onside”)
> - AI 投资主线从“创新者”→“采用者”扩散

---

### 109. 智谱AI

- **tier**: 大模型独角兽
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: LLM算法post-train (1)
- **industry_focus**: AI 基础设施
- **source 标签**: taxonomy_doc
- **notes**:
  - [LLM算法post-train] GLM 大模型

#### XHS 帖证据 (1 条)

**[多模态推理优化]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/6a05e199000000000](https://www.xiaohongshu.com/discovery/item/6a05e199000000000603777c?xsec_token=YBSoRGoLnXgYWkamAVP-9gF7DimedlFbioD1lHciA1bc4%3D&xsec_source=app_share)

> 帖内提到的公司: OpenAI, Anthropic, Google, xAI, 阿里, DeepSeek

> **内容快照**:
> 
> 2026年4月全球大模型公司能力梯队全景图，T1到T5，涵盖OpenAI、Anthropic、Google、xAI、阿里、DeepSeek、Meta、智谱AI等公司。
> 
> T1梯队估值到1万亿级别，工业级Agent闭环、GPQA推理准确率超94%、代码生成率超85%。
> 
> T2梯队多模态与逻辑推理、代码生成率TOP 5、开源生态标杆。
> 
> T3梯队垂直行业分析、端侧部署、行业级多模态。
> 
> T4梯队政企流式推理、私有化部署、端云协同。
> 
> T5梯队细分场景、端侧部署、开源社区。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 2026年4月全球大模型公司能力梯队全景图，T1到T5，密密麻麻几十家公司。
> - 估值到1万亿级别，工业级Agent闭环、GPQA推理准确率超94%、代码生成率超85%。
> - 多模态与逻辑推理、代码生成率TOP 5、开源生态标杆。

---

### 110. 月之暗面

- **tier**: 大模型独角兽
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: LLM算法post-train (1)
- **industry_focus**: AI 基础设施
- **source 标签**: taxonomy_doc
- **notes**:
  - [LLM算法post-train] Kimi

#### XHS 帖证据 (1 条)

**[Agent工程师]** (relevance=0.20) — [https://www.xiaohongshu.com/discovery/item/69d87e16000000001](https://www.xiaohongshu.com/discovery/item/69d87e16000000001a0363ff?xsec_token=YBq5QfHxJDg9yBL3G5hdrsqmAWURNZ1FO7h8kRhM-wymY%3D&xsec_source=app_share)

> 帖内提到的公司: 月之暗面

> **内容快照**:
> 
> 月之暗面Kimi Harness Team正在招聘Agent Engineer，简历投递至luozheng@moonshot.ai

> **verbatim 锚点 (T1/T3 抽取)**:
> - Kimi Harness Team 持续招人，希望相信技术、习惯刨根问底的你加入我们！简历请发 luozheng@moonshot.ai

---

### 111. 汇丰晋信基金

- **tier**: 二线公募
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 行业研究员·TMT-医药-周期 (1)
- **industry_focus**: TMT, 周期
- **source 标签**: saif:2024
- **notes**:
  - [行业研究员·TMT-医药-周期] SAIF 2024 命中

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 汇丰晋信基金管理有限公司 | 行业研究员 | 1 | 公募基金 |

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 112. 淡马锡

- **tier**: 头部PE
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: PE投后VC行研 (1)
- **industry_focus**: TMT, 金融
- **source 标签**: saif:2025, taxonomy_doc
- **notes**:
  - [PE投后VC行研] 新加坡主权基金

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2025 | 淡马锡上海 | 行业研究员 | 1 | 私募 |

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 113. 瑞银证券

- **tier**: 外资行
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 投行 IBD (1)
- **industry_focus**: 金融
- **source 标签**: common_knowledge:头部外资投行
- **notes**:
  - [投行 IBD] 按行业共识

#### XHS 帖证据 (1 条)

**[卖方研究员·TMT]** (relevance=0.20) — [https://www.xiaohongshu.com/discovery/item/6a15930c000000003](https://www.xiaohongshu.com/discovery/item/6a15930c00000000370366f7?xsec_token=YBp6NuLTNeVKVJxfqEX3_W56DfH9XxSOdshS-lYD7wir0%3D&xsec_source=app_share)

> 帖内提到的公司: 瑞银

> **内容快照**:
> 
> 存储芯片市场从周期品转变为AI基础设施，HBM是增长斜率。
> 
> 全球存储芯片市场2025年约1713亿美元，2034年可能接近4480亿美元。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 存储以前是周期品，现在是AI基础设施的水电煤
> - 2025年大约1713亿美元，到2034年可能接近4480亿美元

---

### 114. 网易

- **tier**: 互联网大厂
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: AI PM (1)
- **industry_focus**: AI 应用层
- **source 标签**: xhs:AI PM:1
- **notes**:
  - [AI PM] 游戏 + AI PM

#### XHS 帖证据 (1 条)

**[AI PM]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68a5770b000000001](https://www.xiaohongshu.com/discovery/item/68a5770b000000001b032042?xsec_token=YBMn-3vXRkAwKVWQG-g_6rmGDJaKO4_2jclTetcReqh8o%3D&xsec_source=app_share)

> 帖内提到的公司: 字节跳动, 网易, 美团, 抖音

> **内容快照**:
> 
> AI PM 求职时，大厂和小公司各有优劣：大厂资源多但创新受限，小公司在应用层机会更大。
> 
> AI 应用层机会在垂直细分领域，小而美的公司能更灵活地落地。
> 
> 大厂 PM 岗位流动性下降，招聘需求减少，竞争激烈。
> 
> 与字节 PM 学长 coffee chat 后，作者不再执念大厂，更看重创新和 AI 落地空间。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 小公司在应用层的机会反而更大。大厂体量大了，幻觉问题、安全合规问题，都会让产品变得“重”，交互上趋于保守。
> - 这些极其精细化、垂直化的AI应用，会被无数“小而美”的公司吃下来。
> - 业务增长放缓，没有那么多新坑了，招聘需求也就少了。

---

### 115. 银华基金

- **tier**: 二线公募
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 行业研究员·TMT-医药-周期 (1)
- **industry_focus**: TMT, 医药
- **source 标签**: common_knowledge:头部公募
- **notes**:
  - [行业研究员·TMT-医药-周期] 按行业共识,医药条线知名

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 116. 锐天投资

- **tier**: 中型量化私募
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 量化研究员·中频 (1)
- **industry_focus**: —
- **source 标签**: saif:2025
- **notes**:
  - [量化研究员·中频] SAIF 2025 量化命中

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2025 | 锐天投资 | 量化研究员 | 1 | 量化私募 |

#### XHS 帖证据 (1 条)

**[买方 Quant]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/69d432b2000000002](https://www.xiaohongshu.com/discovery/item/69d432b200000000230165ba?xsec_token=YB8P2sbk6XOuWvtBsp0Qw4RFxCEDtP9oT_Q6sMVDVtcIA%3D&xsec_source=app_share)

> 帖内提到的公司: 幻方, 九坤, 明汯, 灵均, 衍复, 宽德

> **内容快照**:
> 
> 量化私募分为第一梯队（幻方、九坤等）和第二梯队（启林、鸣石等），第一梯队高薪技术强，第二梯队是上岸主力。
> 
> Trading Firm包括锐天、天演、宽投、SIG、DRW、Squarepoint，偏高频/microstructure，数学和coding要求更高。
> 
> 互联网量化岗位包括字节、腾讯、阿里达摩院、美团，适合ML/Data强的同学，但交易感弱一点。
> 
> 券商和公募只投量化/自营/衍生品岗位，包括中信、华泰、广发、招商、汇添富、南方、招商基金。
> 
> 期货公司包括东证期货和国泰君安期货。
> 
> 银行包括招商银行、兴银理财、光大。
> 
> 交易所/国家级机构包括上海证券交易所、深圳证券交易所、香港交易所、中国经济信息社、中国投融资担保股份有限公司、中国外汇交易中心。
> 
> 地点选择：上海是量化核心，北京偏研究型，深圳偏高频多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 第一梯队（冲就完了）幻方｜九坤｜明汯｜灵均｜衍复｜宽德 高薪+技术强+最核心去处 第二梯队（上岸主力）启林｜鸣石｜世纪前沿｜千象｜赫富｜致诚卓远 第一梯队没回，这一层最关键
> - 锐天｜天演｜宽投｜SIG｜DRW｜Squarepoint 更偏：* 高频 / microstructure * 数学+coding要求更高
> - 字节｜腾讯｜阿里达摩院｜美团 ML/Data强的可以冲（但交易感弱一点）

---

### 117. 高瓴量化

- **tier**: 头部主观私募
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 买方 Quant (1)
- **industry_focus**: —
- **source 标签**: common_knowledge:头部主观私募
- **notes**:
  - [买方 Quant] 按行业共识,高瓴量化条线

#### XHS 帖证据

(taxonomy_xhs_posts 表内未找到提及此公司的帖 — source 应该来自 saif / demo_v1 / taxonomy_doc / common_knowledge)

---

### 118. 鹏华基金

- **tier**: 二线公募
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 公募权益研究员 (1)
- **industry_focus**: TMT, 周期
- **source 标签**: saif:2024
- **notes**:
  - [公募权益研究员] SAIF 2024 流向

#### SAIF 校友流向证据 (1 条)

| year | SAIF 表内公司名 | role_type | count | industry |
|---|---|---|---|---|
| 2024 | 鹏华基金管理有限公司 | 行业研究员 | 1 | 公募基金 |

#### XHS 帖证据 (2 条)

**[行业研究员·消费]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68523924000000002](https://www.xiaohongshu.com/discovery/item/685239240000000022028983?xsec_token=YB1tOVHt4MrRCgE3YRmfKUfzkX4Zhwklu8QU9qotk8kHY%3D&xsec_source=app_share)

> 帖内提到的公司: 易方达, 华夏, 博时, 国泰, 汇添富, 南方

> **内容快照**:
> 
> 易方达、华夏是头部公募，整体待遇好，科技岗位应届生薪资尤其高。
> 
> 博时、国泰、汇添富、南方类似公务员氛围。
> 
> 银行系公募（招商、中银、工银）薪资相对固化，待遇提升空间有限，但工作相对安逸。
> 
> 永赢、嘉实、鹏华待遇不错，但工作强度卷王级别。
> 
> 兴全待遇不错，人少资源多。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 易方达、华夏：头部中的头部，整体待遇不会太差，据说科技岗位应届生薪资对比其他应届会尤其高一些
> - 博时、国泰、汇添富、南方：据说类似公务员氛围浓厚
> - 银行系包括（招商、中银、工银等）薪资相对固化，待遇可提升空间对比其他就不太行了，安逸也是相对的吧

**[资管FOF]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/68076825000000001](https://www.xiaohongshu.com/discovery/item/68076825000000001a0066db?xsec_token=YB99eH8k09Rv7rNLHjW60O0BTN6QzTKurNuAdNZ06-eic%3D&xsec_source=app_share)

> 帖内提到的公司: 交银施罗德基金, 兴证全球基金, 民生加银基金, 汇添富基金, 南方基金, 浦银安盛基金

> **内容快照**:
> 
> FOF行业规模从2021年的2253亿降至2024年底的1442亿，降幅36%，多家公司规模大幅缩水。
> 
> 交银施罗德基金FOF团队仅剩2名基金经理，规模排名从第一跌至第七。
> 
> 兴证全球基金FOF团队以林国怀为带头人，成员背景多元，包括互联网大厂和海外金融背景。
> 
> 易方达基金FOF团队由汪玲牵头，成员如刘淑霞有券商资管FOF业务负责人经验。
> 
> 中欧基金FOF团队由桑磊牵头，成员有险资投资管理经验。
> 
> 华夏基金FOF团队汇聚了许利民、廉赵峰、李晓易、卢少强等精兵强将。
> 
> 工银瑞信FOF团队赵志源接替蒋华安成为FOF投资部总经理并进入投委会，陈涵任研究副总监。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 截至2024年底，共有87家基金公司管理着511只FOF产品，资产净值规模合计1442亿元，相比2021年的2253亿降幅36%。
> - 交银施罗德FOF团队则仅见2人：刘兵，经济学博士，2016年加入交银施罗德基金；刘迪，金融工程与投资管理博士，2015年加入交银施罗德基金。
> - 兴证全球基金以公司总经理助理、FOF投资与金融工程部总监、养老金管理部总监林国怀为带头人，团队成员既有来自互联网大厂的成员，也有来自海外金融从业背景的成员。

---

### 119. 黑翼资产

- **tier**: 中型量化私募
- **must_have in**: — (0 sub_cat)
- **非 must_have (备选) in**: 量化研究员·高频 (1)
- **industry_focus**: —
- **source 标签**: xhs:量化研究员·高频:2
- **notes**:
  - [量化研究员·高频] XHS 高频 2 次

#### XHS 帖证据 (1 条)

**[量化研究员·高频]** (relevance=0.80) — [https://www.xiaohongshu.com/discovery/item/694dfad5000000002](https://www.xiaohongshu.com/discovery/item/694dfad50000000022032080?xsec_token=YBcHIqfNaLBVDhXCU8c_xcywRuE30yKwo_JDQ4QwekE5I%3D&xsec_source=app_share)

> 帖内提到的公司: 明汯投资, 幻方量化, 衍复投资, 九坤投资, 宽德投资, 世纪前沿

> **内容快照**:
> 
> 2025年量化策略业绩全面回暖，头部机构规模洗牌，明汯、幻方、衍复、九坤等有望重返千亿俱乐部。
> 
> 明汯投资今年备案最多，多个渠道积极推产品，可能很快突破千亿。
> 
> 幻方量化2021年曾主动控盘建议客户赎回，之后靠业绩驱动规模自然回升。
> 
> 衍复投资今年年中暂停新申购，多个策略年内第二次分红，主动控制规模扩张节奏。
> 
> 九坤投资产品发行细水长流，规模稳步爬升，属于长跑型选手。
> 
> 宽德投资上半年募资凶猛，下半年明显刹车，预计短期内规模变化不大。
> 
> 世纪前沿、诚奇、黑翼三家今年发力明显，备案和募资都在前列。
> 
> 2025年量化圈关键词是“卷”，靠规模喊口号的草莽时代结束，现在比的是策略迭代速度和算力竞赛。

> **verbatim 锚点 (T1/T3 抽取)**:
> - 2025年余额仅剩最后3个交易日！复盘这一年，绝对是量化策略的当打之年。业绩全面回暖，头部机构赚得盆满钵满，百亿量化阵营也在加速扩容。
> - 明汯：今年的备案王！多个渠道都在积极推其产品，势头非常猛，可能很快再次捅破1000亿这层窗户纸。
> - 幻方：2021年曾主动控盘甚至建议客户赎回，随后依靠业绩驱动规模自然回升，实力不允许低调。

---
