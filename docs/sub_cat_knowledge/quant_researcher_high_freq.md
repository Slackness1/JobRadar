# 量化研究员·高频 — 知识库

**策略类型**: 量化
**数据置信度**: medium (post=64, company_mention=58, saif_alumni=0)
**行业方向候选**: 全市场（股票/期货/期权/ETF） / 衍生品做市 / 高频股票 / 商品/股指期货
**机构层级候选**: 衍生品做市商 / 头部量化私募 / 外资行（自营/做市部门）

## 典型公司

- **Optiver** — 衍生品做市商 (XHS 提及 16 次) ⭐
- **Jane Street** — 衍生品做市商 (XHS 提及 2 次) ⭐
- **Citadel** — 外资行 (XHS 提及 2 次) ⭐
- **幻方量化** — 头部量化私募 (XHS 提及 11 次) ⭐
- **九坤投资** — 头部量化私募 (XHS 提及 10 次) ⭐
- **Tower Research** — 衍生品做市商 (XHS 提及 1 次)
- **IMC** — 衍生品做市商 (XHS 提及 2 次)
- **DRW** — 衍生品做市商 (XHS 提及 2 次)
- **SIG** — 衍生品做市商 (XHS 提及 2 次)
- **HRT** — 衍生品做市商 (XHS 提及 2 次)
- **黑翼资产** — 头部量化私募 (XHS 提及 3 次)
- **宽德投资** — 头部量化私募 (XHS 提及 3 次)

## 硬门槛

- 数学/物理/CS/EE 硬核背景，研究生及以上学历优先，国际竞赛获奖（ACM-ICPC、NOI、IMO、Kaggle）是显性加分项
- C++ 低延迟工程能力（堆栈/缓存/数据结构性能优化），能落到 tick 级订单簿与做市报价系统
- 心算 + 概率题 + 博弈论快速反应（绿皮书刷 3 遍级别），面试现场承受连续追问与高压报价
- 理解 tick size、订单簿、队列位置、撮合规则、滑点与延迟分布，知道回测与实盘偏差的来源
- Python 数据处理与回测能力，熟悉 tick/逐笔成交数据的清洗、特征构建与时间戳对齐

## 加分项

- Trading Instinct：对 PnL 有执念但能冷静控盘 Risk，敢报价、敢调仓、敢承认错误
- self-driven + aggressive 的桌面文化，能在被追问时维持判断速度与解释清晰度
- 对低延迟和代码 impact 的真热情，而非用 Machine Learning 套话堆简历
- 扑克/电竞/竞赛背景常被视为博弈直觉与抗压能力的间接证据

## 转岗路径

- **互联网后台开发/搜推算法 → 量化开发（做市/低延迟方向）** (难度: medium) — C++ 与系统性能背景直接迁移；需补金融市场结构、tick 数据与撮合机制
- **CS/数学 PhD 应届 → 做市商 Quant Trader / Researcher** (难度: high) — 门槛在心算+博弈+概率题手感，需提前半年按 mental math / market making 路径练
- **量化研究员·中频（指增/CTA） → 量化研究员·高频** (难度: high) — 信号 horizon 与执行框架完全不同，需重学订单簿微结构与队列模型
- **卖方金工/资管量化 → 买方高频/做市** (难度: high) — 卖方因子建模思维偏长 horizon，高频更看工程速度与微观结构，常需从初级岗重新起步

## 风险/排雷

- 简历堆 Machine Learning / xgboost 等套话却答不出实操细节，Optiver 等已用 AI 简历扫描秒拒
- 不懂 tick size、换月逻辑、期货贴水、CTA 等基础概念就投高频 Quant Trading 实习
- 做高频回测时把价格触达当成交，忽略队列位置、延迟分布与对手盘节奏，导致成交率系统性高估

## 面试样态

做市商流程 OA → HR → Tech → BQ → 终面 Market Making 游戏，考心算、概率题、博弈直觉与高压报价；技术面深挖 C++ 与低延迟。国内头部私募清北简历通过率约 2%，看 Trading Instinct 与 PnL 执念。

## 薪酬信号

Optiver new grad QT 总包 USD 400k+；Citadel entry $300k+；国内头部私募应届 base 15k 起谈。

## 职业路径

应届入做市商 Quant Trader/Researcher 或国内头部私募投研，3–5 年独立带策略/做市账户；优秀者晋升 Senior Trader / PM；少数自立工作室。圈子小、靠业绩说话，Tech 路径可在低延迟与 FPGA 方向长期深耕。

## 招聘节奏

- **春招**: 3–5 月做市商 FutureFocus / Discovery Day 集中开放
- **秋招**: 8–10 月 new grad 校招主战场，9 月笔试 + 10 月面试
- **高峰月**: 3, 8, 9, 10

## XHS 原文锚点 (verbatim)

> 他认为最决定胜负的是Market Making 游戏，不是团队合作，而是真人对抗博弈，每轮你要根据部分信息估算资产价格并报价交易，拼的就是心算+博弈直觉+抗压能力
>
> — [Optiver 终面 Market Making 游戏复盘](https://www.xiaohongshu.com/discovery/item/688e26510000000025024392?xsec_token=YBfA4ZabvT73hxjQCFYsiMcxfSGqg612t9IllGWkBDu8s%3D&xsec_source=app_share)

> 流程很套路：OA → HR → Tech → BQ，但每一步都掉血。
>
> — [Optiver 26 Summer intern 流程](https://www.xiaohongshu.com/discovery/item/68a1ec59000000001c03f9f8?xsec_token=YB5Ulu1WhUNtw4vWAtrIxUoOacwIr42grgPnEysfGZPCQ%3D&xsec_source=app_share)

> 今年新增AI简历扫描仪（出现"Machine Learning"秒拒）
>
> — [Optiver 反 ML 套话简历筛选](https://www.xiaohongshu.com/discovery/item/67bc15ad000000002a000486?xsec_token=YBGhkz5zbI1f__35ylC81X6THL2fjHAtmCtGz1G-zdtBQ%3D&xsec_source=app_share)

> 其实人家更想要的是那种有Trading Instinct的人。说白了你得表现得像个真正的Trader，对PnL有执念但又能冷静控制Risk。
>
> — [做市商面试官真实标准](https://www.xiaohongshu.com/discovery/item/69b21ae9000000001503b124?xsec_token=YBDzyndl-7rtYoDrF75nRMUowhtWMtTfFZ9P8gXLTeufI%3D&xsec_source=app_share)

> 买方（God Tier）以 Citadel、Jane Street、Two Sigma 为代表
>
> — [高频/买方 Quant 行业地图](https://www.xiaohongshu.com/discovery/item/6a15a138000000003501dd25?xsec_token=YBJXceSEhkLQc7puTGKMxN_p_R9jpYHzgNTvXgnWHFQ5c%3D&xsec_source=app_share)

> 不知道tick size、换月逻辑、期货贴水、CTAs这些基本概念
>
> — [Quant Trading Intern 常见 pitfall](https://www.xiaohongshu.com/discovery/item/6880a9d50000000010011ba0?xsec_token=YBd9faHjVDkkQSHFf23cH7LLya_pA4wf0Drwhyk37lwAc%3D&xsec_source=app_share)

> 即使有完整 tick 数据，回测仍可能与实盘偏差很大，因为 tick 只解决“看见价格”，不代表“能成交”。
>
> — [高频回测与实盘偏差核心坑](https://www.xiaohongshu.com/discovery/item/69de11af000000001a02582c?xsec_token=YBVkrEimBbRkXJ2qPZ5_N40-fOqoNmW6ojT4wd1gLx7WY%3D&xsec_source=app_share)

> 清北简历通过率仅2%，选拔标准严苛
>
> — [九坤投资简历筛选门槛](https://www.xiaohongshu.com/discovery/item/6964b6e2000000000a0316d5?xsec_token=YBU4z1Lpx2NFfDQ4Fl9SlINizOxUHfkD7ts9RekV9CPhU%3D&xsec_source=app_share)
