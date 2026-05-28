# GPT 5.5 Pro — Phase G Call 3: 重做 🔴 sub_cat KB — 自营FOF

**生成日期**: 2026-05-29
**Call 编号**: 3 / 10
**优先理由**: user audit: 公司表所有 XHS 提及都是 0, 却标 medium 并给出多个 must_have

## 你 (GPT 5.5 Pro) 的任务

重做 `自营FOF` 这一张知识库 (sub_cat KB)。输出 15 字段新 KB JSON, 直接替换
现 knowledge_subcategories 表 sub_cat='自营FOF' 行的 payload_json。

**严格按 Part 5 输出 schema 给, 不写总结性废话**。

---

## Part 1 — Call 1 已给的回炉指南

- 现 KB 主要问题: 公司表强证据不足，且与财富管理FOF、资管FOF、基金评价混淆。
- 应改的关键字段: typical_companies 只放能证明"自有资金/自营盘/机构自营配置"的券商、信托、保险、财务公司，不用泛银行/泛公募充数。
- 应改的关键字段: hard_req 增加 proprietary capital、自有资金配置、管理人尽调、FOF组合、底层基金筛选、投委会材料、绩效归因。
- 应改的关键字段: pitfalls 增加"私行客户投顾 ≠ 自营FOF""资管产品FOF ≠ 自营FOF""基金运营/产品助理 ≠ FOF"。
- 应补的证据来源: 自营投资/FOF投资官方 JD、校友/SAIF 来源、XHS 同 sub_cat；若 2 轮检索仍无强证据，降为 low 并减少 must_have。
- 重做后 confidence 期望: medium；证据不足则保持 low 但边界清晰。
- 实施: Opus subagent 重做；必要时把弱样本并入资管FOF/财富FOF而非强行保留。

---

## Part 2 — 现 KB payload (你要替换的对象)

**data_confidence**: medium
**data_basis**: {'post_count': 29, 'high_relevance_post_count': 23, 'company_mention_count': 38, 'ground_truth_count': 7, 'saif_alumni_count': 0, 'verbatim_quote_count': 6, 'notes': '29 帖 XHS + 7 条 ground truth 公司清单; 无 SAIF 校友直接流向数据, 故 confidence 维持 medium; 自营 / 资管 / 财富三分线 + 自营盘灵活要素的认知来自 2 条独立帖子交叉验证'}

```json
{
  "sub_cat": "自营FOF",
  "sub_cat_slug": "proprietary_fof",
  "strategy_type": "多资产_FOF_衍生品",
  "industry_focus_candidates": [
    "金融"
  ],
  "institution_tier_candidates": [
    "头部券商研究所",
    "中型券商研究所",
    "银行系资管",
    "一线公募",
    "二线公募",
    "保险资管",
    "信托自营"
  ],
  "typical_companies": [
    {
      "name": "中信证券",
      "tier": "头部券商研究所",
      "is_must_have": true,
      "notes": "券商自营 FOF 头部, 股衍 / 自营资管利润梯队顶端"
    },
    {
      "name": "中信建投",
      "tier": "头部券商研究所",
      "is_must_have": false,
      "notes": "XHS 出现 FOF 投资经理岗"
    },
    {
      "name": "华泰证券",
      "tier": "头部券商研究所",
      "is_must_have": false,
      "notes": "金融创新部场外衍生品 + 做市自营"
    },
    {
      "name": "光大证券",
      "tier": "中型券商研究所",
      "is_must_have": false,
      "notes": "金融创新部条线"
    },
    {
      "name": "招商银行",
      "tier": "银行系资管",
      "is_must_have": true,
      "notes": "TREE 多元资产配置计划推动 FOF 新发"
    },
    {
      "name": "平安银行",
      "tier": "银行系资管",
      "is_must_have": true,
      "notes": "银行自营 FOF"
    },
    {
      "name": "南方基金",
      "tier": "一线公募",
      "is_must_have": true,
      "notes": "南方合顺 FOF + 黄金配置约 10% 贡献净值"
    },
    {
      "name": "中信保诚基金",
      "tier": "二线公募",
      "is_must_have": true,
      "notes": "FOF 增强策略 + ETF 工具核心抓手"
    },
    {
      "name": "易方达基金",
      "tier": "一线公募",
      "is_must_have": false,
      "notes": "FOF 研究员面试真题来源"
    },
    {
      "name": "中泰资管",
      "tier": "中型券商研究所",
      "is_must_have": false,
      "notes": "中泰时钟资产配置 + 长期持仓黄金 ETF"
    }
  ],
  "hard_requirements": [
    "金融工程 / 数理 / 统计 / 经济金融硕士背景, 公募 / 券商 / 私募 FOF 或基金评价相关实习 2 段以上",
    "熟练 Python 做多资产回测 / 因子构建 / 基金画像, 能写 CTA + 宏观策略评价框架",
    "理解 FOF 与普通基金区别 + 利率下行周期资产配置 + 底层基金筛选指标, 能扛面试追问",
    "对绝对收益 / 回撤控制 / 多策略组合 (CTA + 中性 + 套利) 有方法论, 不只会卖 Beta"
  ],
  "soft_signals": [
    "全面能力都要合格, 但能把其中一项 (多资产配置 / 行业轮动 / 定量 / 定性) 做大做强当个人标签",
    "对自营机构资金的 FOF 思路 (稀缺额度 + 灵活要素 + 几亿大资金组合经验) 有认知, 能区别于资管 FOF",
    "抗压能力强 + 愿意被业绩 / 回撤指标硬控, 行情好钱多行情差没钱, 心态稳",
    "对决策流程 + 闭环交易 + 数据沉淀的差异化逻辑有理解, 不迷信新技术 / 新模型"
  ],
  "transfer_paths": [
    {
      "from": "公募 FOF 研究员",
      "to": "券商自营 FOF / 银行自营 FOF",
      "difficulty": "medium",
      "notes": "门槛更高 + pay 更低, 但有实盘和绝对收益经验后是顺向迁移"
    },
    {
      "from": "量化私募研究员 (CTA / 中性)",
      "to": "券商 / 信托自营 FOF 多策略组合",
      "difficulty": "medium",
      "notes": "自营盘看多策略组合, CTA + 套利背景稀缺"
    },
    {
      "from": "券商资管 FOF",
      "to": "自营 FOF",
      "difficulty": "easy",
      "notes": "同一家券商内部条线迁移, 资管做大锅饭, 自营更灵活"
    },
    {
      "from": "保险资管多资产",
      "to": "银行 / 券商自营 FOF",
      "difficulty": "easy",
      "notes": "保险大类资产配置经验直接对口自营 FOF 绝对收益目标"
    },
    {
      "from": "美元 FoF + coinvestment",
      "to": "境内自营 FOF / 直投 / IBD",
      "difficulty": "hard",
      "notes": "学习空间窄 + 离市场远, 转直投或 IBD 都要重新建网络"
    }
  ],
  "pitfalls": [
    "公募 FOF 受公募新规 + 产品硬伤拖累, 容易清盘, 晋升道路狭窄, 不要把它当稳定铁饭碗",
    "FOF 整体小众赛道, 人才流失到保险 / 私募, 兴证全球已把 FOF 投资部改名多元资产配置部",
    "自营 FOF 门槛高 pay 低, 想从基金投顾 / 美元 FoF 转过来要算清楚机会成本"

```

---

## Part 3 — 该 sub_cat 全部 XHS 原帖 (29 条, 按 relevance desc)

每条含 source_url + 内容快照 + verbatim 锚点 + 提到的公司。**新 KB 的 verbatim_quotes
字段必须从这些 XHS 帖里直接 substring 摘抄, 不能改写, source_url 必须真实存在于本列表。**

### Post 1 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/693e065c000000021e029e20?xsec_token=YBHnwsTf9MGpmgQdrtDV-hHE7Pu0hENRz2PrH5k4cqxXM%3D&xsec_source=app_share
- **company_mentions**: 券商资管部门, 各类金融机构自营资金, 金融机构自营
- **verbatim_signals (T1/T3 已抽取)**:
  - 券商资管部门的fof定制底层是较为死板的。一是大多只投向权益底层的私募...二是大锅饭...三是底层资产要素不灵活
  - 而各类金融机构自营资金的fof下投的思路：首先对管理几个亿大资金定制组合更有经验...其次...再次...最后...
- **content snippet**:
  > 券商资管部门的FOF定制存在底层死板、大锅饭、要素不灵活等问题

自营机构资金的FOF下投思路更优：投资经理经验丰富、有稀缺额度、能控制回撤、要素灵活

### Post 2 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/67343f0e000000003c017576?xsec_token=YB0CZWBbnst8HscUtlaxkzdV5LPYTAkn_N9dgTpsRcKSg%3D&xsec_source=app_share
- **company_mentions**: 公募, 券商, 量化私募, 交易所, 券商自营
- **verbatim_signals (T1/T3 已抽取)**:
  - 量化相关的工作岗位：fof 风控 量化投研 衍生品
  - 优点：成长曲线陡峭，wlb，相对更好的薪资待遇 缺点：稳定性低，hc随机
  - 985理工本华五人金融硕，女，24届 实习机构有 公募、券商、私募 实习岗位有：fof、风控、量化研究、衍生品
- **content snippet**:
  > 量化相关岗位包括FOF、风控、量化研究、衍生品等

量化私募优点：成长曲线陡峭，wlb，相对更好的薪资待遇；缺点：稳定性低，hc随机

作者背景：985理工本华五人金融硕，实习经历包括公募、券商、私募，岗位有FOF、风控、量化研究、衍生品

### Post 3 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/69f9c6d10000000236017df1?xsec_token=YBjvkpfH4EZNDX1fdAwHaxzixUFX-KWA43iF9MiS7xpng%3D&xsec_source=app_share
- **company_mentions**: 华泰证券, 光大证券, 中信证券
- **verbatim_signals (T1/T3 已抽取)**:
  - 金融创新部主要负责以下4类业务：第一部分是场外衍生品...第二部分是结构化产品...第三部分是做市与自营...第四部分是境外业务
  - 如果要投交易，基本需要垂直实习or数理本科背景。如果是投sales...对销售的专业知识会更高一些
  - zx的股衍部门是除了投行以外人均创收最高的部门
  - 目前这个部门还是属于高增长、高壁垒、有一定红利的
- **content snippet**:
  > 券商金融创新部主要负责场外衍生品、结构化产品、做市与自营、境外业务四类业务

金融创新部对交易岗要求数理和编程能力高，需垂直实习或数理本科背景；销售岗需专业知识高

中信证券股权衍生品部门是除投行外人均创收最高的部门

金融创新部属于高增长、高壁垒、有一定红利的部门

### Post 4 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/6855401b000000002203dbb1?xsec_token=YBJwLSptFOnDfeWjwIQAC14BXIQyV9IYZKfiMYKfObQBY%3D&xsec_source=app_share
- **company_mentions**: (无)
- **verbatim_signals (T1/T3 已抽取)**:
  - 恭喜稳健策略FOF！
- **content snippet**:
  > FOF策略受到关注，尤其是稳健策略FOF

### Post 5 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/667edd8b000000021d01229d?xsec_token=YBWNmqW28S-03iE7cFg312dLQflsIoIGDQywWtz9VsVhQ%3D&xsec_source=app_share
- **company_mentions**: 券商资管, 券商
- **verbatim_signals (T1/T3 已抽取)**:
  - FOF是什么？ 主要工作内容在做什么
  - 对于很多朋友来说这是金融比较小众的赛道
- **content snippet**:
  > FOF是基金中的基金，主要工作包括基金筛选、资产配置、风险管理等。

FOF是金融行业比较小众的赛道。

### Post 6 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/6913e51f000000000500024f?xsec_token=YB7lRH1RMRMb_BmvNu2YSE8u6scv_qOBFm7u6uQU12rVY%3D&xsec_source=app_share
- **company_mentions**: 中金财富
- **verbatim_signals (T1/T3 已抽取)**:
  - 中金财富1200亿FOF规模驱动买方投顾新模式，从卖产品到定制方案，财富管理3.0模式成功转型
- **content snippet**:
  > 中金财富1200亿FOF规模驱动买方投顾新模式，从卖产品到定制方案，财富管理3.0模式成功转型。

### Post 7 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/69f3977c0000000237005dcf?xsec_token=YBR40-aaHbPXe8lvCXhHOoD2W5EN13b42cfznym836_B0%3D&xsec_source=app_share
- **company_mentions**: 券商, 公募基金
- **verbatim_signals (T1/T3 已抽取)**:
  - 前台：债券自营>资管>权益自营>衍生品自营>债券业务>投行和MA（股权）>机构业务>研究所>经纪业务=财富管理（两融）
  - 中台：风控>合规法律>托管
后台：财务>总办>董办>稽核审计>人力
  - 卖方永远没法和买方比
  - 券商做债总体比做股好，公募反过来
  - 中后台里越接近业务，越有发展空间
- **content snippet**:
  > 券商前台部门收入排名：债券自营>资管>权益自营>衍生品自营>债券业务>投行和MA（股权）>机构业务>研究所>经纪业务=财富管理（两融）

券商中后台部门收入排名：风控>合规法律>托管>财务>总办>董办>稽核审计>人力

卖方永远没法和买方比

券商做债总体比做股好，公募反过来

中后台里越接近业务，越有发展空间

券商收入决定于能创造多少利润，前台部门中自营资管和股债发行承销收入最高

研究所经常在成本部门和微薄盈利的部门间徘徊，收入依赖佣金派点

机构业务/销售交易开始向国外S&T发展，收入多元化

经纪业务和两融营收高但和个人无关，奖金平均水平

### Post 8 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/682003950000000012004c92?xsec_token=YBkBiUxr1vgmuF9SZyZnmQfptiD4XG8_w4tf7Vm6RVfyo%3D&xsec_source=app_share
- **company_mentions**: 券商
- **verbatim_signals (T1/T3 已抽取)**:
  - 底层无外乎股债商三个大类品种。差异化来自于：1.券商基于那么多年交易的数据沉淀和经验积累，供养出的决策模型...2.决策流程的严谨...3.底层交易基本上也都是在券商平台，形成闭环
  - 新技术没有做出来是硬科技，做出来了就是制造业，三家公司做了就是产能过剩。所以新技术并不能起成为企业的差异化竞争优势，而且把新技术融入到你的决策流程和客户经营场景中，总结出你独特的业务链条，才是差异化。
- **content snippet**:
  > 券商做FOF的差异化不在于底层策略，而在于投研能力、决策流程和闭环交易。

新技术不能成为企业的差异化竞争优势，融入决策流程和客户经营场景才是差异化。

### Post 9 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/6953425e000000021f00f294?xsec_token=YBESGoHrR-DEWyhY3gl_h-odUMoA32f3tSS_3t9Wc1e1k%3D&xsec_source=app_share
- **company_mentions**: 知名券商
- **verbatim_signals (T1/T3 已抽取)**:
  - 知名券商-FOF研究员-上海
- **content snippet**:
  > 知名券商招聘FOF研究员，要求2-4年FOF研究、基金评价或策略开发经验，尤其对CTA和宏观策略有深刻理解，需熟练掌握Python等编程语言。

### Post 10 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/6890067f0000000003031ea8?xsec_token=YBmCA1AtoFdnPTCngthUM3rB8t5ZksJM979ASjR1w7C5Y%3D&xsec_source=app_share
- **company_mentions**: 兴全基金, 易方达基金, 中欧基金, 大成基金, 华夏基金, 南方基金, 中泰证券, 招商银行
- **verbatim_signals (T1/T3 已抽取)**:
  - 人才流失严重：薪资不够吸引人，很多优秀的基金经理都跑去保险、私募了
  - 兴全FOF的林国怀从2020年开始重仓刘旭，2024年却全部清仓了！可能是考虑到刘旭管理规模已达475亿，太大了...
  - 兴证全球已经把'FOF投资部'改名为'多元资产配置部'，信号很明显！
  - 华夏郑鹏（已离职）管理华夏海外聚享，业绩堪称完美
  - 南方恽雷理论功底深厚，定期报告写得最有深度，核心理念：寻找长期优秀的Beta + 股债负相关性
- **content snippet**:
  > FOF基金行业人才流失严重，薪资不够吸引人，很多优秀的基金经理都跑去保险、私募了。

兴全FOF的林国怀从2020年开始重仓刘旭，2024年却全部清仓了，可能是考虑到刘旭管理规模已达475亿。

兴证全球已经把'FOF投资部'改名为'多元资产配置部'，信号很明显。

华夏郑鹏管理华夏海外聚享，业绩堪称完美，但已离职。

南方恽雷理论功底深厚，核心理念是寻找长期优秀的Beta + 股债负相关性。

中泰唐军建立了中泰时钟资产配置体系，长期持有黄金ETF。

今年FOF新发规模已达308.42亿，超过去年全年的123.67亿，招商银行大力推广'TREE长盈计划'。

### Post 11 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/6942b810000000000d0374be?xsec_token=YBP0nienGdvpm09oz90sesSUzSwpPByvolyOicDy9CvG0%3D&xsec_source=app_share
- **company_mentions**: (无)
- **verbatim_signals (T1/T3 已抽取)**:
  - 科技成长是几乎所有保险资管都看好方向；高股息/红利板块也获得一致青睐；消费板块则遭冷遇
  - 某保险资管直言今年是“拔估值年份”，A股从去年九月到现在估值修复已接近完成；明年市场行情将更多取决于基本面
  - 某光资产也持类似观点，26 年看好与🇺🇸AI 趋势联动的国内相关产业标的
  - 出海方向也被重点安利，认为化工、有色金属、机械设备、新能源等领域具备全球竞争优势出海企业存在投资机会
  - 认为市场成交和波动率维持高位，量化策略超额收益仍可期待
- **content snippet**:
  > 保险资管普遍看好科技成长（AI、高端制造、创新药、机器人）和高股息/红利板块（能源、运营商、银行、保险），不看好消费板块。

某保险资管认为今年是“拔估值年份”，A股估值修复已接近完成，明年市场将更多取决于基本面。

某光资产看好与AI趋势联动的国内相关产业标的。

出海方向被重点安利，化工、有色金属、机械设备、新能源等领域具备全球竞争优势的出海企业存在投资机会。

量化策略超额收益仍可期待，因为市场成交和波动率维持高位。

债券市场预计窄区间震荡，建议短久期高评级信用债为主。

转债估值较高，需警惕调整风险；黄金长期配置价值仍存在。

### Post 12 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/694f377000000000210318a7?xsec_token=YBlKAv8wY0HALD2nXaWlzzSkmAyHKtqrYjKwISPIGRpac%3D&xsec_source=app_share
- **company_mentions**: 南方基金, 中泰资管, 招商银行
- **verbatim_signals (T1/T3 已抽取)**:
  - 据Wind统计，FOF规模较年初增加1041亿元，达到2373.05亿元，增幅高达78.15%，公募FOF业务呈现加速发展态势。
  - 2024年至今该产品涨幅达24.51%，表现优异...黄金配置约10%，对产品净值的贡献同样在10%左右
  - 这些增量中，很大一部分受益于招商银行“Tree多元资产配置”计划的推动。
- **content snippet**:
  > FOF规模较年初增加1041亿元，达到2373.05亿元，增幅高达78.15%，公募FOF业务呈现加速发展态势。

南方基金夏莹莹管理的FOF产品南方合顺2024年至今涨幅达24.51%，黄金配置约10%，贡献约10%的净值。

招商银行推出“Tree多元资产配置”计划，推动FOF发行。

### Post 13 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/6899609f000000002501a862?xsec_token=YBFJhgnYjdzWzAgC04xCLoHx-eTjo18_nbpH7Ae2jp93E%3D&xsec_source=app_share
- **company_mentions**: 公募, 公募基金
- **verbatim_signals (T1/T3 已抽取)**:
  - 受限于产品自身硬伤限制，市场吸引力不够，叠加如今公募新规的施行，整体上，岗位稳定不够，产品容易面临清盘风险，晋升道路狭窄且充满不确定性。
- **content snippet**:
  > 公募FOF受限于产品自身硬伤，市场吸引力不够，叠加公募新规，岗位稳定不够，产品容易清盘，晋升道路狭窄且充满不确定性。

### Post 14 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/66810504000000021c03d3c9?xsec_token=YBqK5jnKPXduLaptP992q2CzlfIeViMOhl1jLZrGIBoIg%3D&xsec_source=app_share
- **company_mentions**: 基金公司, 券商, 银行理财子
- **verbatim_signals (T1/T3 已抽取)**:
  - 自营FOF最追求绝对收益，资管FOF最看重规模和业绩排名，财富FOF最看重客户需求和投后服务
  - 应届生/新人更适合资管FOF、财富FOF；有实盘经验及投资追求去自营FOF
  - 追求Work life balance更适合去财富管理FOF，偏中后台，工作以研究分析为主，当然pay也就一般。有抗压能力、愿意学习成长以后致力于投资的去资管和自营FOF，行情好钱多行情差没钱
- **content snippet**:
  > FOF岗位分为资管FOF、自营FOF和财富管理FOF，各自侧重点不同：自营FOF追求绝对收益，资管FOF看重规模和业绩排名，财富FOF看重客户需求和投后服务。

应届生/新人更适合资管FOF和财富FOF，有实盘经验及投资追求的去自营FOF。

追求工作生活平衡适合财富管理FOF，偏中后台；愿意学习成长致力于投资的去资管和自营FOF。

### Post 15 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/69427259000000021e027bca?xsec_token=YBPCbg0ZeyVPclci2f1lLEatcLy-tFfZdE1cUQLarrLEo%3D&xsec_source=app_share
- **company_mentions**: (无)
- **verbatim_signals (T1/T3 已抽取)**:
  - FOF就是一个要求全面能力都要合格的这个一个职业，但是可以把其中一个能力做大做强，成为去自我营销的一个特点吧
  - 比如现在你想配置新能源，那你才会去筛选现在配置了新能源板块的主动基金或者被动基金，然后进一步去看这个基金经理是长期配置新能源还是行业轮动到新能源，是买新能源龙头还是买新能源小弟
- **content snippet**:
  > FOF岗位要求全面能力，包括多资产配置、行业轮动、定量分析、定性分析，但可以突出一个能力作为特色。

FOF选基金前需要先有基金画像，例如配置新能源板块时需筛选相关基金并分析基金经理风格。

### Post 16 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/68f5d3770000000003038fc1?xsec_token=YBo_FODNuCvfZ8VVMUXBjdv9KvxJ722ovoBrDdB5IY_KU%3D&xsec_source=app_share
- **company_mentions**: 招行
- **verbatim_signals (T1/T3 已抽取)**:
  - 做公募FOF的感觉价值感很弱，今年一个快死的赛道被招行类投顾模式救起来了，看上去规模是提高了，但从业的大家，还好吗？有没有被回撤指标硬控，黄金是不是买的太多了，追涨的科技回调时怎么办？其他家又发了新的，我的产品规模怎么办？
  - 研究员们还在调多资产回测模型吗，时序动量的模型在真正的cta面前拿的出手吗，选基还在回测根据几个因子构建模型看过往调仓超额收益和实际上只有标签细化但没有超额认知的基金调研报告吗？
- **content snippet**:
  > 公募FOF从业者感到价值感弱，被回撤指标硬控，面临追涨科技回调、规模压力等问题。

公募FOF行业面临价值困惑，研究员在调多资产回测模型，但模型在真正CTA面前可能拿不出手。

### Post 17 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/69248ad5000000001e009b1b?xsec_token=YBuTLszjR2QK9De-L9KBf4AWtoGb-PgSSTjK4yq-Mv64Y%3D&xsec_source=app_share
- **company_mentions**: 美元FoF
- **verbatim_signals (T1/T3 已抽取)**:
  - 毕业就在一家美元FoF一直做新兴市场的FoF+coinvestment...最近越来越burnout 觉得这工作能学到的东西太少了
  - 百亿美元的AUM但分给我们的盘子很小
  - 以前有bb ibd summer的经验 但太久不碰直投已经离市场越来越远了
- **content snippet**:
  > FoF岗位工作内容可能包括母基金投资和联合投资，但学习空间有限，容易burnout。

百亿美元AUM的美元FoF，但分给个人的盘子很小。

FoF从业者考虑出路，可能转向直投或IBD相关领域。

### Post 18 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/6969ad00000000021a02efc0?xsec_token=YBW1-V0j8rjVSmD_LlVJywDUDFwXhLCzlLuW3hXFswAjk%3D&xsec_source=app_share
- **company_mentions**: 基金投顾机构, 资管自营机构
- **verbatim_signals (T1/T3 已抽取)**:
  - 基金投顾业务在到处捞人，基金投顾投研岗虽然岗位名字奇奇怪怪，但是给的多...如果两年里做不起来基本上也是凉凉
  - 博主还是想走资管自营等机构道路，毕竟不想浪费了公募私募双修的背景，但给的确实又少很多，并且门槛也高不少
- **content snippet**:
  > 基金投顾业务在到处捞人，投研岗给得多，但发展前景堪忧，两年内做不起来可能凉凉。

博主有公募私募双修背景，想走资管自营道路，但门槛高且给得少。

### Post 19 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/68980ec30000000225016866?xsec_token=YBy-OWvN26uOjG9C0uWGj6yQMwz8i9v4FgwjaiGbnvC5k%3D&xsec_source=app_share
- **company_mentions**: (无)
- **verbatim_signals (T1/T3 已抽取)**:
  - 理财子也卷的很，一堆人在排队
- **content snippet**:
  > 理财子竞争激烈，求职者众多

### Post 20 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/68bbdba2000000001c00545a?xsec_token=YBgbIorudrQRiOedhfupr1IZ8bTArX7XFw_WN_Y5Q6EaA%3D&xsec_source=app_share
- **company_mentions**: 易方达
- **verbatim_signals (T1/T3 已抽取)**:
  - 1. 请解释FOF（基金中基金）与普通基金的主要区别... 2. 假设当前处于利率下行周期... 3. 作为FOF研究员，你会通过哪些核心指标筛选和评估底层基金... 3-追问1：如果两只底层基金的历史业绩相近... 3-追问2：在筛选底层基金时，若某基金的“历史业绩优异”但“未来市场环境可能不利于其风格发挥”...
- **content snippet**:
  > 易方达FOF研究员面试真题，包括FOF与普通基金区别、利率下行周期策略、底层基金筛选指标、风格选择、历史业绩与未来展望矛盾处理。

### Post 21 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/69f9c6d1000000003601f8cb?xsec_token=YBnFa4xApobQBvp3vnnCnlVta8-eZcO29PttI6v4ycj_8%3D&xsec_source=app_share
- **company_mentions**: 华泰, 光大, 中信, 中信证券
- **verbatim_signals (T1/T3 已抽取)**:
  - 金融创新部是以股权和指数衍生品为核心标的...需要了解一般的金融创新业务部主要负责以下4类业务...如果要投交易，基本需要垂直实习or数理本科背景。如果是投sales，虽然不一定要硬性要求垂直实习，但不像别的部门销售主要考行为面，这个岗位对销售的专业知识会更高一些。
  - zx的股衍部门是除了投行以外人均创收最高的部门。
  - 目前这个部门还是属于高增长、高壁垒、有一定红利的
- **content snippet**:
  > 券商金融创新部主要业务包括场外衍生品、结构化产品、做市与自营、境外业务，其中交易岗对数理和编程能力要求高，销售岗对专业知识要求高。

中信证券股权衍生品部门是除投行外人均创收最高的部门之一。

券商金融创新部属于高增长、高壁垒、有一定红利的部门。

### Post 22 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/6a16aebf0000000008033edb?xsec_token=YBS-3qfPPzk2XzB_nFC2X8B_GfxRuKiVJdX_IdrYXLGgA%3D&xsec_source=app_share
- **company_mentions**: 中信保诚基金
- **verbatim_signals (T1/T3 已抽取)**:
  - ETF工具：FOF增强的核心抓手
- **content snippet**:
  > ETF工具是FOF增强的核心抓手

### Post 23 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/67d5da23000000000302ab72?xsec_token=YBkPBybGVkO9YazAoHHi9pM9vdTYXpqg8vXaOYI_N9H0c%3D&xsec_source=app_share
- **company_mentions**: 中信建投
- **verbatim_signals (T1/T3 已抽取)**:
  - 中信建投fof投资经理怎么样
- **content snippet**:
  > 中信建投FOF投资经理岗位，主要职能是FOF投资管理，待遇和上升空间需了解。

### Post 24 (relevance=0.80)
- **URL**: https://www.xiaohongshu.com/discovery/item/69d4b71d000000002101239e?xsec_token=YBXTQkhcnvpkVGQk-5X32kwt7EVY6MCz-yqxNJt6iIGQo%3D&xsec_source=app_share
- **company_mentions**: 金融公司自有母基金
- **verbatim_signals (T1/T3 已抽取)**:
  - 找CTA策略产品经理！！！金融公司自有母基金要发fof，我去哪里找私募市场经理呀！求推！自有大资金，求深圳本地的私募公司，手里家办客户想投cta策略的
- **content snippet**:
  > 用户正在寻找CTA策略产品经理职位，同时需要对接私募市场经理，涉及FOF发行和家办客户投资CTA策略。

### Post 25 (relevance=0.40)
- **URL**: https://www.xiaohongshu.com/discovery/item/67f71a34000000021d02dde9?xsec_token=YBT1jdDtYTnZ7552a7-qdfO7IqVFdz1NO951E2r-qV0Lg%3D&xsec_source=app_share
- **company_mentions**: 公募基金
- **verbatim_signals (T1/T3 已抽取)**:
  - 大环境、金融、FOF，各维度都肉眼可见的变cha了
  - 老本行基本没有什么新增的岗位需求，大家都可以说只是苟住而已
  - 要换乘的话，是all in考公，还是转型教培呢
- **content snippet**:
  > 金融行业整体下行，FOF岗位需求减少，从业者面临裁员风险。

FOF研究员岗位在公募基金中曾蒸蒸日上，但如今新增岗位需求很少。

公募基金行业面临裁员，从业者考虑转行考公或教培。

### Post 26 (relevance=0.30)
- **URL**: https://www.xiaohongshu.com/discovery/item/68a7d17a000000021d000e27?xsec_token=YBZJgp_qiU6zgKNHQdBFEKVZZ3WBnGbkbTekn6YlDfL1E%3D&xsec_source=app_share
- **company_mentions**: 券商
- **verbatim_signals (T1/T3 已抽取)**:
- **content snippet**:
  > (无文本快照)

### Post 27 (relevance=0.30)
- **URL**: https://www.xiaohongshu.com/discovery/item/6a16a61400000000360331d3?xsec_token=YB_a2p3MOsb9Jnd74YYidgBWT7oku88re-gY_OjP_m8D8%3D&xsec_source=app_share
- **company_mentions**: 中信保诚基金
- **verbatim_signals (T1/T3 已抽取)**:
  - 借助ETF低成本、流动性较好的特点，FOF增强策略可以在行业和策略之间进行灵活轮动，力争拓宽组合收益来源；同时，高流动性工具也有助于组合进行更及时的回撤管理。
- **content snippet**:
  > FOF增强策略利用ETF低成本、流动性好的特点，在行业和策略之间灵活轮动，拓宽固收+组合收益来源，并有助于回撤管理。

### Post 28 (relevance=0.30)
- **URL**: https://www.xiaohongshu.com/discovery/item/69b28557000000000800d75f?xsec_token=YB3Co1CYcrkvfl7UOGWawHlvWVWKexhQ46lPvvPpXO7gI%3D&xsec_source=app_share
- **company_mentions**: 未具名私募管理人
- **verbatim_signals (T1/T3 已抽取)**:
  - 做私募 FOF 配置，选对管理人远比盲目看产品重要！
  - 选私募 FOF 管理人，核心看这 4 点
- **content snippet**:
  > 私募FOF配置的核心在于选对管理人，需关注团队稳定性、投研体系、策略分散性和风控严谨性。

FOF管理人筛选的四个维度：团队硬实力、投研体系、策略逻辑、风控与筛选。

### Post 29 (relevance=0.30)
- **URL**: https://www.xiaohongshu.com/discovery/item/68a7f9ff000000021d022ebb?xsec_token=YBXeYIYO4rkaKjUOzBQlJeiCeZkFtU7RpgoRFDB2A8kTo%3D&xsec_source=app_share
- **company_mentions**: (无)
- **verbatim_signals (T1/T3 已抽取)**:
  - 我们是站在你身边的‘独立观察者’，而不是单一机构的‘产品推荐者’。
  - 七年资管顾问，见过市场热络时的忙碌，也经历过行情冷清时的沉淀。
- **content snippet**:
  > 作者自称是香港的资管顾问，强调独立顾问与单一机构产品推荐者的区别。

资管行业在香港的工作日常，包括市场分析、客户信任等。

---

## Part 4 — User audit 关于该 sub_cat 的 must_have 公司评级 (5 行)

| 公司 | tier | status | audit_reason | note |
|---|---|---|---|---|
|  | 头部券商研究所 | 通过-强 | 同 sub_cat XHS 标签 2 条; common_knowledge 可支撑: 头部券商自营; taxonomy_doc | 券商自营 FOF 头部 |
|  | 一线公募 | 通过-强 | 同 sub_cat XHS 标签 2 条; taxonomy_doc | 公募自营 FOF |
|  | 银行系资管 | 需补证据 | XHS 标签只支撑财富管理FOF；“银行自营FOF”目前只有 taxonomy_doc，需补银行自营/资管部 FOF 证据。 | 原证据: taxonomy_doc | 银行自营 FOF |
|  | 银行系资管 | 通过-强 | 同 sub_cat XHS 标签 2 条; taxonomy_doc | 零售之王自营 |
|  | 二线公募 | 通过-强 | 同 sub_cat XHS 标签 2 条; 可见摘录同 sub_cat 2 条 | XHS 自营 FOF 2 次 |

---

## Part 6 — 你必须输出的 15 字段 KB JSON

**严格按以下 schema 输出, 直接给可 parse 的 JSON, 不写解释**:

```json
{
  "sub_cat": "自营FOF",
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