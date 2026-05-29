# GPT 5.5 Pro — Phase G Call 1 输入包: Taxonomy 重设计 + Pass 2 prompt 重写

**生成日期**: 2026-05-29
**Call 编号**: 1 / 10 (10 calls 总预算)

## 背景

JobRadar Phase G 推荐链路 v2: 把岗位库 (4 万帖, T10 quality_label 过滤后剩 ~9k 候选) 跑
Multi-pass C sub_cat 分类 (Pass 1 选 7 大类, Pass 2 选具体 sub_cat + 3 维 industry/tier/secondary)。

**T13 200 帖人工 review 准确率 76.4%, 未达 90% 验收线**。6 类错误模式集中在: 机构销售/DCM
/AI 边界/FOF·中后台·投后/金融科技·量化·AI量化 互相串台 — spec-level 缺口 + Pass 2 prompt 边界
规则不够精细。

**你的任务**: 一次性给我 (a) Taxonomy 增删调整 (b) 新 Pass 2 prompt (c) 哪些 KB 需重做
(d) Pass 1 是否需改 (e) 实施 checklist。我后续按你的建议执行。

---

## Part 1 — 现 29 sub_cat 全景 (按 7 strategy 分组)

### Strategy: 基本面权益 (5 sub_cat)

#### `公募基金中后台` (low)
- **industry**: 金融, 不动产/基础设施 | **tier**: 一线公募, 中型公募, 头部券商资管
- **typical_companies (top5)**: 南方基金⭐, 易方达基金⭐, 嘉实基金⭐, 景顺长城基金, 国泰海通证券资管
- **hard_req (top3)**:
  - 研究生及以上学历在校生,经济/金融/财务等相关专业优先
  - 实习期 3 个月以上,长期实习优先;每周到岗 3 天起
  - 通过基金从业资格,熟练掌握 Wind / Office 等工具

#### `公募指数研究员` (medium)
- **industry**: TMT, 消费, 金融, 医药, 周期, REITs | **tier**: 一线公募, 二线公募, 外资行, 保险资管, 银行理财
- **typical_companies (top5)**: 易方达基金⭐, 华夏基金⭐, 南方基金⭐, 中金基金, 摩根资产管理
- **hard_req (top3)**:
  - 理工科/金融/数学/统计硕士优先,Python/SAS/Matlab + Wind/Bloomberg 数据库熟练,能跑因子回测
  - 能讲清楚指数编制原理:市值/等权重/Smart Beta 加权差异,样本空间与调整频率对指数表现影响
  - 理解指数基金/ETF/指数增强三者运作区别,会算跟踪误差,熟悉申赎清单与成分股事件处理

#### `公募权益研究员` (medium)
- **industry**: 消费, TMT, 医药, 周期, 金融 | **tier**: 一线公募, 二线公募, 头部保险资管
- **typical_companies (top5)**: 华夏基金⭐, 易方达基金⭐, 工银瑞信基金, 嘉实基金⭐, 汇添富基金
- **hard_req (top3)**:
  - 国内外重点高校硕士及以上,金融/经济/会计/理工科背景优先,留学生与境内研究生均可投递
  - 至少一份公募/券商研究所/保险资管投研实习,优先覆盖单一行业组(消费/TMT/医药)
  - 简历必须有至少 1 份独立完成的个股深度报告,标的市值 200 亿以上,能讲清楚选股逻辑与跟踪

#### `行业研究员·TMT-医药-周期` (medium)
- **industry**: TMT, 医药, 周期, 新能源, 消费电子 | **tier**: 一线公募, 二线公募, 头部险资资管
- **typical_companies (top5)**: 华夏基金⭐, 易方达基金, Point72, Millennium, Citadel
- **hard_req (top3)**:
  - 数学/金融/统计学等理工或量化背景,本科以上,研究生学历日趋成为门槛
  - 至少1段二级买方或卖方行研实习,能讲清研究框架与研究流程
  - 熟练 Wind/Bloomberg,具备建模与数据库维护能力

#### `行业研究员·消费` (high)
- **industry**: 食品饮料, 商贸零售, 新消费, 美妆医美, 餐饮社服 | **tier**: 一线公募, 中型券商研究所, 消费基金/产投
- **typical_companies (top5)**: 兴业证券⭐, 华创证券⭐, 天风证券⭐, 开源证券, 中泰证券
- **hard_req (top3)**:
  - 国内外重点院校硕士在读,2027 年及以后毕业;消费/食品/财经背景或 CPA 通过者优先
  - 至少 1 段消费行研实习(券商食品饮料/商社组优先),周 4 天起、累计 3-4 个月以上
  - Wind/Excel/财务建模熟练,能独立完成数据整理 + 行业动态跟踪 + 深度报告撰写

### Strategy: 量化 (5 sub_cat)

#### `AI 量化工程师` (low)
- **industry**: AI 应用层, AI 基础设施 | **tier**: 头部量化私募, 大模型独角兽
- **typical_companies (top5)**: 鸣石基金⭐, 明汯投资⭐, 幻方量化⭐, DeepSeek⭐, 九坤投资⭐
- **hard_req (top3)**:
  - 海内外名校硕/博,数学/统计/物理/计算机等理工科背景,扎实数理与编程功底
  - 精通深度学习框架(PyTorch/TensorFlow)+ 大规模模型训练经验,熟练 Python/C++
  - 掌握深度学习/机器学习/凸优化/线性代数,能做数学推导 + 代码实现 + 理论理解

#### `量化因子工程师` (medium)
- **industry**: 全市场股票, 中证500/1000指增, 商品/股指CTA, ETF/期权 | **tier**: 头部量化私募, 中型量化私募, 券商研究所金工组, 海外量化平台
- **typical_companies (top5)**: WorldQuant, 鸣石基金⭐, 灵均投资⭐, 幻方量化, 九坤投资⭐
- **hard_req (top3)**:
  - 数学/物理/计算机/金工硕博背景, 高数、线代、概率统计扎实, 加分项随机过程、凸优化
  - Python (numpy/pandas) 数据处理熟练, 能在 Pandas 中高效完成截面/时序运算
  - 熟悉因子投资理论 (Fama-French、Barra), 掌握 IC/IR、因子衰减、过拟合检验

#### `量化开发QD` (medium)
- **industry**: 低延迟交易系统, 回测框架, 数据平台, AI Infra/算子优化, 高频系统 | **tier**: 头部量化私募, 中型量化私募, 券商自营/金融科技, 外资量化做市商
- **typical_companies (top5)**: 九坤投资⭐, 明汯投资⭐, 鸣石基金⭐, 量派投资⭐, 宽德投资⭐
- **hard_req (top3)**:
  - 重点大学本硕应届理工科,计算机/软件工程相关,顶尖院校或 ACM/奥赛获奖者优先
  - 精通 C++ 或 Python,熟悉数据结构与算法,LeetCode 中等以上现场手撕代码
  - 熟悉 Linux 开发工具链、Git/Docker,理解多线程、网络编程与微服务容错

#### `量化研究员·高频` (medium)
- **industry**: 全市场（股票/期货/期权/ETF）, 衍生品做市, 高频股票, 商品/股指期货 | **tier**: 衍生品做市商, 头部量化私募, 外资行（自营/做市部门）
- **typical_companies (top5)**: Optiver⭐, Jane Street⭐, Citadel⭐, 幻方量化⭐, 九坤投资⭐
- **hard_req (top3)**:
  - 数学/物理/CS/EE 硬核背景，研究生及以上学历优先，国际竞赛获奖（ACM-ICPC、NOI、IMO、Kaggle）是显性加分项
  - C++ 低延迟工程能力（堆栈/缓存/数据结构性能优化），能落到 tick 级订单簿与做市报价系统
  - 心算 + 概率题 + 博弈论快速反应（绿皮书刷 3 遍级别），面试现场承受连续追问与高压报价

#### `量化研究员·中频` (medium)
- **industry**: 全市场选股, 股票多头, 市场中性, CTA期货, 另类数据 | **tier**: 头部量化私募, 中型量化私募, 公募量化部
- **typical_companies (top5)**: 灵均投资⭐, 明汯投资⭐, 幻方量化⭐, 九坤投资⭐, 鸣石基金⭐
- **hard_req (top3)**:
  - 985/211 或 QS50 院校,理工科/金融工程/数学/计算机硕士及以上,头部岗位明确偏好 PhD
  - 扎实的统计与概率基础,熟练 Python+numpy,头部量化普遍要 C++ 或工程化能力
  - 至少 1 段头部量化私募或公募量化部实习,做过完整因子挖掘/回测闭环

### Strategy: 固定收益 (4 sub_cat)

#### `信用研究员` (medium)
- **industry**: 城投, 金融, 地产, 产业债（钢铁/煤炭等周期）, 可转债（部分兼看） | **tier**: 信用评级机构, 公募基金固收信用研究, 保险资管信用研究, 银行理财子固收研究, 券商资管/自营/研究所固收信用
- **typical_companies (top5)**: 易方达基金⭐, 富国基金, 华夏基金, 广发基金, 华富基金⭐
- **hard_req (top3)**:
  - 硕士及以上学历，国内985/211或海外QS前50院校，金融/经济/统计/金工等专业优先
  - 熟练使用Wind/Python，具备数据处理、逻辑梳理与报告撰写能力
  - 需有公募/券商/保险资管/理财子等买方或卖方固收信用相关实习经历

#### `利率宏观策略` (medium)
- **industry**: 金融, 宏观, 固收 | **tier**: 头部券商研究所, 一线公募, 保险资管, 外资行/资管, 银行金市部, 货币中介
- **typical_companies (top5)**: 华泰证券⭐, 贝莱德⭐, 华泰资管, 摩根大通, 摩根士丹利
- **hard_req (top3)**:
  - 经济、金融、数理统计专业背景,熟练 Wind/Excel/Python,有固收宏观行研经历加分
  - 985/两财一贸/海外名校硕士,熟悉久期、收益率曲线、凸性、信用利差等固收核心概念
  - 能跟踪央行政策(MLF/OMO)、资金面、通胀(CPI/PPI)、PMI 等宏观指标并形成观点

#### `固收+多资产` (low)
- **industry**: 金融, 宏观大类资产, 可转债, 国债期货, REITs | **tier**: 一线公募, 头部理财子, 保险资管, 券商资管, 央企财务公司, 金融基础设施
- **typical_companies (top5)**: 易方达基金⭐, 广发基金⭐, 华夏基金⭐, 平安资产管理⭐, 国寿投资⭐
- **hard_req (top3)**:
  - 具备固收基础知识框架:理解久期、收益率曲线、信用利差、可转债定价等核心概念,能在面试中讲清楚
  - 至少 1 段固收+ / 多资产 / 转债 / 量化方向的实习,垂直堆叠效果优于横跨多赛道
  - 掌握大类资产配置思维:能讨论股债跷跷板、加息周期下美股美债黄金比例调整、股债相关性转正后的策略

#### `固收交易员` (low)
- **industry**: 金融 | **tier**: 头部券商研究所, 中型券商, 一线公募, 银行理财子, 银行金融市场部, 券商资管, 信托, 货币中介
- **typical_companies (top5)**: 易方达基金, 中信证券⭐, 平安证券⭐, 中信建投证券⭐, 国泰海通证券⭐
- **hard_req (top3)**:
  - 至少一份固收方向实习 (券商自营/资管、公募固收交易台、银行理财子或银行金市部),否则简历被刷概率很大
  - 面试要求对岗位有具体认识,能讲清现券/回购/同业询价等交易流程,不能以"没做过所以不懂"为理由
  - 熟悉 Wind/彭博或内部交易系统,会跟踪 PMI/CPI 等宏观指标对债市的影响

### Strategy: 卖方研究 (5 sub_cat)

#### `买方 Quant` (medium)
- **industry**: 因子投资, 组合优化与风险归因, 衍生品定价与对冲, FOF/多策略配置, Smart Beta/ETF | **tier**: 顶尖外资对冲基金, 头部券商自营/资管量化, 头部公募量化部, 保险资管/银行理财子量化组, 头部主观私募量化条线
- **typical_companies (top5)**: Point72⭐, Citadel⭐, Millennium⭐, Two Sigma, AQR
- **hard_req (top3)**:
  - QS50/清北复交/中科大等顶级理工或金融工程硕士及以上,外资对冲基金普遍要 PhD
  - 扎实的概率统计、随机过程、衍生品定价(BS、希腊字母、波动率微笑)理论基础
  - 熟练 Python+SQL,会因子研究/回测框架,外资 HF 看 C++、kdb+/q,A股方向看 Wind/Tushare

#### `卖方研究员·TMT` (medium)
- **industry**: TMT, 半导体, 互联网, 电子, 通信 | **tier**: 头部券商研究所, 中型券商研究所, 外资投行研究部
- **typical_companies (top5)**: 中金公司⭐, 国泰海通证券⭐, 中信证券⭐, 中信建投证券⭐, 华泰证券
- **hard_req (top3)**:
  - 国内外重点高校本科/硕士在读,通信、电子、物理、AI等专业优先,纯文科背景基本不进面
  - 至少 1 段 TMT 行研实习,头部券商组别强烈偏好有新财富团队带教经历
  - 能现场出勤 3 个月以上、每周 4 天起,北京/上海线下是大组默认要求

#### `卖方研究员·宏观策略` (high)
- **industry**: 宏观经济, 大类资产配置, A股策略, 海外宏观, 货币与财政政策 | **tier**: 头部券商研究所, 中型券商研究所, 外资投行研究部
- **typical_companies (top5)**: 中金公司⭐, 国泰海通证券⭐, 申万宏源证券⭐, 中信证券⭐, 华泰证券⭐
- **hard_req (top3)**:
  - 国内外重点高校经济/金融/数量经济硕士在读为主,毕业论文与货币政策、宏观经济相关是显性加分
  - 至少 1 段券商宏观/策略组实习,头部所偏好十年 xcf 级团队或新财富宏观团队带教经历
  - 熟练使用 Wind/CEIC + Stata/Python,能独立完成 CPI、社融、汇率等数据的拉取与建模

#### `卖方研究员·消费医药周期` (high)
- **industry**: 食品饮料, 医药, 化工, 有色金属, 钢铁/煤炭/建材, 家电/纺服/轻工, 新能源汽车, ESG/碳中和 | **tier**: 头部券商研究所(三中一华), 中型券商研究所, 腰腿部券商研究所, 第三梯队及以下
- **typical_companies (top5)**: 招商证券⭐, 广发证券⭐, 中信证券⭐, 中金公司⭐, 华泰证券⭐
- **hard_req (top3)**:
  - 重点院校研究生(2027年及以后毕业)或优秀本科生,统计/金融/经济相关专业,复合背景优先
  - 掌握金融、财务基本知识,熟练使用Wind、Excel,实习期至少3个月
  - 具备行业分析框架能力:能从行业周期、竞争格局、关键驱动因素三维度搭建研究框架

#### `投行 IBD` (low)
- **industry**: 金融, TMT, 消费, 医药, 先进制造 | **tier**: 头部券商研究所, 外资行, 中型券商研究所, 精品投行
- **typical_companies (top5)**: 中信证券⭐, 中金公司⭐, 华泰联合证券⭐, 中信建投证券, 国泰海通证券
- **hard_req (top3)**:
  - 清北复交 + 海外名校硕士本科基本盘,头部券商投行对学历挑剔,中型券商可放松至末 9 同 Level 学校
  - 至少 1 段头部券商或外资行 IBD 实习,中信、华泰 IBD 简历池每年挂海量,无实习直接挂
  - 扎实的财务建模 + DCF 估值 + 三张报表勾稽能力,面试现场给 financial statements 估 enterprise value

### Strategy: 多资产_FOF_衍生品 (4 sub_cat)

#### `结构化产品衍生品` (medium)
- **industry**: 场外衍生品OTC, 雪球收益凭证, FCN/ELN/Autocall, 利率衍生品IRD, 期权做市 | **tier**: 头部券商衍生品部, 中型券商场外业务部, 外资投行Global Markets, 私人银行PWM, 期货风险子公司, 资管衍生品中台
- **typical_companies (top5)**: 中金公司⭐, 中信证券⭐, 华泰证券⭐, 国泰海通证券⭐, 中信建投证券⭐
- **hard_req (top3)**:
  - 扎实掌握期权定价理论(BS/Heston),能手推 BS 公式与边界条件、给定参数算出 vanilla 期权价格
  - 熟悉 Greeks(Delta/Gamma/Vega/Theta/Rho)与 Delta 对冲机制,能解释做市商如何动态对冲
  - 理解波动率曲面与隐含波动率,能讲清楚 skew/term structure 在结构化产品定价中的作用

#### `自营FOF` (medium)
- **industry**: 金融 | **tier**: 头部券商研究所, 中型券商研究所, 银行系资管, 一线公募, 二线公募, 保险资管, 信托自营
- **typical_companies (top5)**: 中信证券⭐, 中信建投, 华泰证券, 光大证券, 招商银行⭐
- **hard_req (top3)**:
  - 金融工程 / 数理 / 统计 / 经济金融硕士背景, 公募 / 券商 / 私募 FOF 或基金评价相关实习 2 段以上
  - 熟练 Python 做多资产回测 / 因子构建 / 基金画像, 能写 CTA + 宏观策略评价框架
  - 理解 FOF 与普通基金区别 + 利率下行周期资产配置 + 底层基金筛选指标, 能扛面试追问

#### `财富管理FOF` (medium)
- **industry**: 金融, 财富管理, 高净值客户, 大类资产配置, 基金投顾, 养老金融 | **tier**: 银行私行, 理财子, 一线公募, 券商财富管理子, 三方财富, 家族办公室, 保险资管FOF
- **typical_companies (top5)**: 信银理财⭐, 招商银行⭐, 平安银行⭐, 中欧基金⭐, 易方达基金⭐
- **hard_req (top3)**:
  - 理解大类资产配置框架:股债跷跷板/股债相关性/黄金REITs配置,能讲清楚选基与配置的区别
  - 至少 1 段 FOF 研究 / 基金投顾 / 私行投顾 / 资产配置相关实习,纯权益/纯固收实习不够
  - 掌握基金经理研究方法:看持仓/换手/风格漂移/业绩归因,能写基金经理尽调报告

#### `资管FOF` (medium)
- **industry**: 金融 | **tier**: 一线公募, 二线公募, 头部券商资管, 保险资管, 银行理财子
- **typical_companies (top5)**: 易方达基金⭐, 南方基金⭐, 中欧基金⭐, 兴证全球基金⭐, 招商基金⭐
- **hard_req (top3)**:
  - 国内外重点高校硕士及以上,金融工程/金融/统计/数学背景优先,理财子等极度看重量化FOF背景
  - 至少一份资管FOF/基金研究/资产配置相关实习,理财子/公募/保险资管均可,实习期 4 个月以上
  - 具备公募基金尽调能力 + 量化择时/归因模型搭建编程能力(Python/R),能搭建评估监控体系

### Strategy: 相关补充 (1 sub_cat)

#### `PE投后VC行研` (low)
- **industry**: 消费, TMT, 医药, 硬科技, 新能源 | **tier**: 头部PE, 头部VC, 产业基金/国资基金, 保险资管另类投资部
- **typical_companies (top5)**: 九坤投资, 越秀产业基金, 华夏基金, 腾讯投资, 高瓴资本⭐
- **hard_req (top3)**:
  - 硕士在读且能保证 6 个月以上连续坐班实习(华夏基金股权投资等岗明确要求)
  - 已有 1 段 PE/VC/FA/卖方研究所/咨询实习,熟悉行业研究+尽调+投资分析+投后管理全流程
  - 熟练做财务建模与估值(DCF/可比/Paper LBO),头部 PE 要求 30 分钟白纸手算 LBO 模型

### Strategy: AI 应用_PM_开发 (5 sub_cat)

#### `AI PM` (medium)
- **industry**: AI 应用层, C 端工具, B 端效率工具, AI 创业出海, 教育/电商/游戏垂直 | **tier**: 互联网大厂, AI 初创, 外企科技公司
- **typical_companies (top5)**: 字节跳动⭐, 腾讯⭐, 美团⭐, 百度⭐, 阿里巴巴⭐
- **hard_req (top3)**:
  - 至少 1 段大厂或头部 AI 初创的 PM/策略实习,能讲清楚自己 owner 的功能、bad case 闭环、量化收益(转化率/留存/人天节省)
  - 跑通 1 个 LLM Agent demo:Coze/Dify/n8n/LangChain 任选,亲手搭过 RAG+工具调用+workflow,简历有可演示链接
  - 掌握大模型概念边界:Transformer 原理、SFT vs RLHF 成本差、模型幻觉成因与 mitigation(RAG/提示词/人工兜底)

#### `AI算法业务` (medium)
- **industry**: AI 应用层, 互联网 | **tier**: 互联网大厂, 头部电商, 金融科技
- **typical_companies (top5)**: 字节跳动⭐, 阿里巴巴⭐, 美团⭐, 小红书⭐, 米哈游⭐
- **hard_req (top3)**:
  - 扎实的 ML/DL 基础：手撕 Transformer 注意力、LR/GBDT/Deep&Cross 等模型
  - 至少 1 段完整业务算法项目（搜推/广告/风控/特征工程），能讲清数据-模型-上线全链路
  - Python + SQL 熟练；至少接触过 PyTorch/TF 训练 + A/B 实验框架

#### `Agent工程师` (medium)
- **industry**: AI 应用层, AI Infra / Harness, C 端 LLM 产品, B 端 Agent 平台, 代码智能体 / Coding Agent | **tier**: 互联网大厂, AI 初创 / 大模型公司, 央企 AI 国家队, 外企科技公司
- **typical_companies (top5)**: 字节跳动⭐, 腾讯⭐, 蚂蚁集团⭐, 小红书⭐, 阿里淘天⭐
- **hard_req (top3)**:
  - 至少 1 个亲手做的 AI Agent 项目,简历能挂 demo 链接,面试要求投屏演示
  - 掌握 Agent 核心范式:tool calling/多步推理/记忆管理/ReAct/Multi-Agent,熟主流框架
  - RAG 工程链路能讲透:文档切割、chunk、embedding 选型、向量库、token 超限

#### `LLM算法post-train` (medium)
- **industry**: AI 基础设施, AI 应用层, 互联网大厂自研模型, 金融 AI, 多模态/Agent | **tier**: 互联网大厂, 大模型独角兽, AI 初创, 国家队 AI Lab, 量化私募 AI Lab
- **typical_companies (top5)**: 字节跳动 (Seed/豆包)⭐, 腾讯 (混元/微信)⭐, 阿里巴巴 (通义/ATH-MaaS)⭐, 蚂蚁集团 (百灵大模型)⭐, DeepSeek⭐
- **hard_req (top3)**:
  - 熟练 Python + PyTorch,有训练/微调实操,能讲清 SFT/RLHF/DPO/PPO/GRPO/Reward Model 差异
  - 至少 1 段大厂或独角兽 post-train 实习,能讲透 owner 的数据飞轮、Reward Hacking、训练诊断
  - 顶会论文硬门槛:NeurIPS/ICLR/ACL/EMNLP 在投或接收,985/海外名校硕博为主

#### `多模态推理优化` (medium)
- **industry**: AI 基础设施, 多模态大模型, 推理引擎/Infra, 端侧/边缘部署, AIGC 应用 | **tier**: 互联网大厂, AI 初创, 大模型独角兽, 外企科技公司
- **typical_companies (top5)**: 腾讯⭐, 商汤科技⭐, 字节跳动⭐, 华为⭐, 百度⭐
- **hard_req (top3)**:
  - 懂多模态主流架构:CLIP 图文对齐、QFormer/QLlama 中间件作用、VLM 训练-推理差异(如 BatchNorm),能现场推导
  - 掌握推理加速主线:投机采样/Speculative Decoding、KV Cache、MoE 负载均衡、ZeRO3,能讲清 2-3x 加速来源
  - 至少 1 段大厂/AI 初创多模态算法实习,简历能讲清 owner 的训练/评测/推理优化模块,有量化指标(QPS/首 token 延迟/加速比)

---

## Part 2 — 现 Pass 1 + Pass 2 prompt 全文

### Pass 1 (7 大类分类, 默认 Flash)

```
你是中国金融+AI 校招岗位分类器。给你一个岗位 JD,选出最匹配的 1 个 strategy_type 大类:

- 基本面权益: 公募 / 主观私募的权益研究员, 行业研究, 指数研究, 中后台
- 量化: 量化研究员 (中频/高频), 量化开发 QD, AI 量化, 因子工程师
- 固定收益: 信用研究, 固收交易, 固收+多资产, 利率宏观策略
- 卖方研究: 券商研究所卖方研究员, 投行 IBD, 买方 Quant
- 多资产_FOF_衍生品: 资管 FOF, 自营 FOF, 财富 FOF, 结构化衍生品
- 相关补充: PE 投后, VC 行研
- AI 应用_PM_开发: LLM 算法 (post-train), Agent 工程师, 多模态推理优化, AI PM, AI 算法业务

如果岗位明显不属于上述任何一类 (e.g. 银行总行综合管培、央企工程师、零售运营、教育/医疗
非投研岗),输出 strategy_type=null,confidence=0。

输出 JSON: {"strategy_type": "<7 大类名 或 null>", "confidence": <0-1>, "reasoning": "<≤60 字>"}
```

### Pass 2 (sub_cat 精细分类, Pro reasoning_effort=high)

```
你是中国金融+AI 校招岗位 sub_cat 分类器。给你一个岗位 JD + 该 strategy_type 大类下的全部 sub_cat 知识库,选出最匹配的 1 个 sub_cat (主) + 可选 1 个 secondary。

Strategy type: {strategy_type}

候选 sub_cats (含硬门槛 / 工作样态 / 典型公司 / 候选 industry_focus / institution_tier):
{candidates_text}

判定规则:
- 主 sub_cat: 岗位 JD 跟该 sub_cat 的硬门槛 + 工作样态匹配度最高的
- secondary: 仅当岗位明显跨 sub_cat 时填 (e.g. 中金 TMT 既卖方研究又跨买方 quant),否则填 null
- industry_focus: 从该 sub_cat 的 industry_focus_candidates 词表选 1-3 个最 fit 的
- institution_tier: 从该 sub_cat 的 institution_tier_candidates 词表选 1 个最 fit 的, 看公司名

输出 JSON:
{{
  "sub_category": "<sub_cat 名, 必须在 候选列表 内>",
  "sub_category_secondary": "<sub_cat 名 或 null>",
  "industry_focus": ["..."],
  "institution_tier": "...",
  "confidence": <0-1>,
  "reasoning": "<≤80 字, 说明判定理由>"
}}
```

---

## Part 3 — T13 review 结果 + 错误样本

**总数**: 200 样本
**通过准确率**: 139 ✓ / (139 ✓ + 43 ✗) = **76.4%** (未达 90% 验收线, 低于 80% spec-level threshold)

### 6 类错误模式归纳 (reviewer 手工归类)

```
- 机构销售/销售支持被误归为研究员或交易员：#9、#28、#42、#74、#135、#139、#172、#178、#196、#200。
- 债券发行、DCM、ABS/REITs承做与固收交易/信用研究混淆：#18、#65、#99、#100、#133、#176。
- 公募权益研究与泛行业研究、宏观研究混淆：#26、#51、#72、#119、#170。
- AI/LLM应用、Agent、post-train、Infra边界混淆：#47、#61、#110、#113、#125、#130、#157、#162、#166。
- FOF、基金产品、基金运营/中后台和投后/FOF投资混淆：#1、#35、#46、#121、#184、#189。
- 金融科技/量化/AI量化边界混淆：#80、#104、#129、#145。
```

### 43 个 ✗ 错判样本 (LLM 标错)

下面每条含: 公司 + 标题 + LLM 误判 sub_cat + LLM reasoning + JD 摘录 + reviewer 备注 (备注里有正确 sub_cat)。

#### ✗ #9. 国金证券 — 机执委\-公募华南\-机构销售助理（2027届暑期）\(J16504\)
- **LLM 误判 sub_cat**: `卖方研究员·宏观策略` (conf=0\.75)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #10. 东吴证券 — 研究所 研究助理（金融工程）\(J11644\)
- **LLM 误判 sub_cat**: `买方 Quant` (conf=0\.84)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #18. 国金证券 — 资管\-ABS后台助理实习生（日常实习）\(J16553\)
- **LLM 误判 sub_cat**: `固收\+多资产` (conf=0\.73)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #21. 国金证券 — 公司直属\-产品经理实习生\(J16366\)
- **LLM 误判 sub_cat**: `公募基金中后台` (conf=0\.60)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #22. 国金证券 — 研究所\-非银组\-研究助理（2026年春招）\(J16410\)
- **LLM 误判 sub_cat**: `卖方研究员·消费医药周期` (conf=0\.55)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #26. 鹏华基金 — 基金经理助理/资深研究员
- **LLM 误判 sub_cat**: `行业研究员·TMT\-医药\-周期` (conf=0\.95)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #28. 国金证券 — 机执委\-公募/保险华北\-机构销售助理（2027届暑期）\(J16506\)
- **LLM 误判 sub_cat**: `卖方研究员·宏观策略` (conf=0\.73)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #35. 中金公司 — 项目实习生\-基金运营\(J18291\)
- **LLM 误判 sub_cat**: `PE投后VC行研` (conf=0\.46)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #42. 中金公司 — 项目实习生\-全球利率销售团队跨境销售组\(J19308\)
- **LLM 误判 sub_cat**: `利率宏观策略` (conf=0\.87)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #44. 国金证券 — 研究所\-2027届暑期实习生（金融工程组）\(J16498\)
- **LLM 误判 sub_cat**: `买方 Quant` (conf=0\.76)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #46. 国金证券 — 资管\-ABS存续管理实习生（日常实习）\(J16401\)
- **LLM 误判 sub_cat**: `信用研究员` (conf=0\.65)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #51. 国泰基金 — 机械行业研究员
- **LLM 误判 sub_cat**: `行业研究员·TMT\-医药\-周期` (conf=0\.95)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #61. 字节跳动 — 前端开发实习生（AI娱乐方向）\-猫箱
- **LLM 误判 sub_cat**: `Agent工程师` (conf=0\.73)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #65. 平安证券 — 债权资本市场实习生
- **LLM 误判 sub_cat**: `固收交易员` (conf=0\.69)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #72. 招商基金 — 研究员（国内宏观）
- **LLM 误判 sub_cat**: `公募权益研究员` (conf=0\.87)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #74. 中金公司 — 项目实习生\-全球利率销售团队华东销售组\(J19364\)
- **LLM 误判 sub_cat**: `固收交易员` (conf=0\.84)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #75. 字节跳动 — AI战略实习生\-火山引擎
- **LLM 误判 sub_cat**: `卖方研究员·TMT` (conf=0\.55)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #80. 国金证券 — 公司总部\-金融量化博士实习生（客户研究方向）\(J16516\)
- **LLM 误判 sub_cat**: `量化因子工程师` (conf=0\.90)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #89. 国金证券 — 公司直属\-金融创新部\-场外衍生品产品运维岗（2027届暑期）\(J16465\)
- **LLM 误判 sub_cat**: `结构化产品衍生品` (conf=0\.90)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #99. 国信证券 — 发行执行岗实习生\(J13915\)
- **LLM 误判 sub_cat**: `固收交易员` (conf=0\.75)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #100. 国信证券 — 债券承做实习生\(J12351\)
- **LLM 误判 sub_cat**: `信用研究员` (conf=0\.52)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #104. 中金公司 — 项目实习生\-量化及ESG组\-ESG方向\(J19343\)
- **LLM 误判 sub_cat**: `卖方研究员·消费医药周期` (conf=0\.79)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #110. 美团 — 机器学习引擎项目实习生
- **LLM 误判 sub_cat**: `多模态推理优化` (conf=0\.87)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #113. 蚂蚁集团 — 【Plan A】财富AI Lab\-大模型Agent算法（实习）
- **LLM 误判 sub_cat**: `LLM算法post\-train` (conf=0\.92)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #119. 招商基金 — 研究员（海外宏观）
- **LLM 误判 sub_cat**: `公募权益研究员` (conf=0\.90)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #121. 鹏华基金 — 产品助理
- **LLM 误判 sub_cat**: `资管FOF` (conf=0\.77)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #130. 字节跳动 — 机器学习算法实习生\-Seed
- **LLM 误判 sub_cat**: `AI 量化工程师` (conf=0\.52)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #133. 国信证券 — 发行上市岗实习生\(J12113\)
- **LLM 误判 sub_cat**: `固收交易员` (conf=0\.67)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #135. 中金公司 — 项目实习生\- 华北区销售/销售助理
- **LLM 误判 sub_cat**: `卖方研究员·TMT` (conf=0\.65)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #139. 中金公司 — Project Intern\-Rates Sales\(J19309\)
- **LLM 误判 sub_cat**: `利率宏观策略` (conf=0\.90)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #145. 衍复投资 — 机器学习工程师（infra方向）
- **LLM 误判 sub_cat**: `量化开发QD` (conf=0\.92)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #169. 国信证券 — 碳金融研究岗实习生\(J13932\)
- **LLM 误判 sub_cat**: `结构化产品衍生品` (conf=0\.52)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #170. 鹏华基金 — 助理研究员
- **LLM 误判 sub_cat**: `行业研究员·TMT\-医药\-周期` (conf=0\.95)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #172. 中金公司 — 项目实习生\-全球信用销售团队\-华南客户组\(J19359\)
- **LLM 误判 sub_cat**: `信用研究员` (conf=0\.73)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #176. 鹏华基金 — 基金经理/投资经理
- **LLM 误判 sub_cat**: `固收\+多资产` (conf=0\.82)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #178. 国金证券 — 股销\-国际业务部\-机构销售助理（2026届春招）\(J16428\)
- **LLM 误判 sub_cat**: `卖方研究员·宏观策略` (conf=0\.75)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #183. 国信证券 — 机构业务岗\(J13836\)
- **LLM 误判 sub_cat**: `买方 Quant` (conf=0\.57)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #184. 中金公司 — 项目实习生\-财富管理部总行支持岗\(J18737\)
- **LLM 误判 sub_cat**: `公募基金中后台` (conf=0\.73)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #186. 美团 — 无人机\-战略研究专家
- **LLM 误判 sub_cat**: `PE投后VC行研` (conf=0\.60)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #189. 中金公司 — 项目实习生\-产品团队基础设施组\(J19277\)
- **LLM 误判 sub_cat**: `财富管理FOF` (conf=0\.65)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #192. Point72 — 2027 Point72 Academy Investment Analyst
- **LLM 误判 sub_cat**: `量化研究员·中频` (conf=0\.46)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #196. 中金公司 — 项目实习生\-全球信用销售团队华北客户组\(J12665\)
- **LLM 误判 sub_cat**: `固收交易员` (conf=0\.70)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

#### ✗ #200. 中金公司 — Trading Intern\(J19190\)
- **LLM 误判 sub_cat**: `买方 Quant` (conf=0\.55)
- **LLM reasoning**: ?
- **reviewer 备注**: ?

### 18 个 ? 边界样本 (reviewer 不确定)

下面每条简要列出, 帮 GPT 5.5 Pro 判断边界规则:

- **#1** 富国基金 | FOF研究员\-2027届暑期实习 → LLM 标 `财富管理FOF` | reviewer: ?
- **#3** 字节跳动 | 大模型应用全栈开发实习生\-巨量星图 → LLM 标 `Agent工程师` | reviewer: ?
- **#5** 美团 | Keeta风控策略产品\-实习岗 → LLM 标 `AI PM` | reviewer: ?
- **#20** 东吴证券 | 博士后创新实践基地 博士后研究员\(J11641\) → LLM 标 `量化研究员·中频` | reviewer: ?
- **#47** 美团 | 大模型数据工程师 → LLM 标 `LLM算法post\-train` | reviewer: ?
- **#50** 因诺资产 | 量化投资实习生\-暑期实习 → LLM 标 `量化因子工程师` | reviewer: ?
- **#57** 招商银行 | 数字金融实习生 → LLM 标 `AI算法业务` | reviewer: ?
- **#97** 鹏华基金 | 高级金融工程师 → LLM 标 `资管FOF` | reviewer: ?
- **#111** 蚂蚁集团 | 【转正实习】数据挖掘工程师 → LLM 标 `LLM算法post\-train` | reviewer: ?
- **#112** 字节跳动 | 大模型开发实习生\-TikTok → LLM 标 `LLM算法post\-train` | reviewer: ?
- **#125** 蚂蚁集团 | 产品实习生 → LLM 标 `AI PM` | reviewer: ?
- **#129** 宽德投资 | 机器学习性能工程师 → LLM 标 `量化开发QD` | reviewer: ?
- **#137** 富国基金 | 市场策略分析师\-2027届暑期实习 → LLM 标 `利率宏观策略` | reviewer: ?
- **#147** 中金公司 | 项目实习生\-非银金融及金融科技组\(J19279\) → LLM 标 `卖方研究员·TMT` | reviewer: ?
- **#153** 鹏华基金 | 助理研究员 → LLM 标 `公募权益研究员` | reviewer: ?
- **#157** 字节跳动 | 大模型算法实习生\-搜索 → LLM 标 `LLM算法post\-train` | reviewer: ?
- **#162** 字节跳动 | 算法实习生\-Dev AI → LLM 标 `Agent工程师` | reviewer: ?
- **#166** 字节跳动 | AI全栈开发实习生\-财经业务 → LLM 标 `Agent工程师` | reviewer: ?

---

## Part 4 — 你 (GPT 5.5 Pro) 要输出什么

请严格按以下结构输出。不要写总结性废话, 直接给可执行内容。

### A. Taxonomy 增删建议

新增 sub_cat (每个含: 名 / 隶属 strategy_type / 跟现有哪个 sub_cat 边界 / typical_companies 5 个示例):
- `<新 sub_cat 名>` → strategy=`<7 大类之一>` | 边界跟 `<现有 sub_cat>` 区别 = `<边界说明>` | typical: [5 公司]

删除/合并 sub_cat (如果有):
- `<现 sub_cat>` → 建议合并到 `<另一 sub_cat>` 因为 ...

保留但需调整描述/边界的 sub_cat (建议改 typical_companies 或 hard_req):
- `<sub_cat>` → 改 ...

### B. 新 Pass 2 prompt 全文

(直接给可 copy 的完整 prompt, 含: 系统指令 / 候选 sub_cat 占位符 / 边界规则 / 输出 JSON schema。重点解 T13 反映的 6 类边界混淆)

```
<新 Pass 2 prompt 全文>
```

### C. 哪些 sub_cat 知识库 (KB) 必须重做

按「重做收益从高到低」排序, 给前 3-5 个 sub_cat, 各说一句「为什么必须重做」(基于 T13 ✗ 集中的 sub_cat / 边界模糊点等):
1. `<sub_cat>` — 重做理由: ...
2. ...

### D. Pass 1 prompt 是否需要改

(简要 1-2 段。如果只需 Pass 2 改, 直接说「Pass 1 不改」; 如果新增 sub_cat 涉及新 strategy 大类, 给改动建议)

### E. 实施 checklist

(给我 step-by-step 操作清单, 我按这个跑 T11-T13 重做)

---

## 输入约束

- 新 sub_cat 增加上限 +5 个 (29 → 最多 34); 删除/合并 不限
- 不动 7 大 strategy_type (基本面权益/量化/固定收益/卖方研究/多资产_FOF_衍生品/相关补充/AI 应用_PM_开发)
- Pass 2 输出 schema 仍是 {sub_category, sub_category_secondary, industry_focus, institution_tier, confidence, reasoning}
- 中国校招语境, 不用国外 (FICC / IBD / S&T) 套现有 sub_cat (e.g. 「机构销售·S&T」 是新加)
- KB 重做意味着 我后续会让 Opus subagent 跑 (不消耗 GPT 5.5 Pro 额度), 你只要列出哪些 sub_cat 需重做即可