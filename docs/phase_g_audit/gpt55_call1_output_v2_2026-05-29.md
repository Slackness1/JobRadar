# GPT 5.5 Pro Call 1 输出 — Phase G v2 Taxonomy + Pass 2 prompt + 9 红 KB 回炉 + 数据 schema + 实施 checklist

**Call 编号**: 1 / 10
**生成日期**: 2026-05-29
**对齐基础**: T13 200 帖 review (76.4%) + user 119 公司 ground_truth audit (78.5%) + 29 sub_cat KB audit (3 绿 17 黄 9 红)

---

## A. 新 Pass 2 prompt 全文

你是中国金融+AI 校招岗位 sub_cat 精细分类器。给你一个岗位 JD + 该 strategy_type 大类下的全部 sub_cat 知识库，选出最匹配的 1 个主 sub_cat + 可选 1 个 secondary，并输出可被程序直接解析的 JSON。

Strategy type: {strategy_type}

候选 sub_cats（含硬门槛 / 工作样态 / 典型公司 / 候选 industry_focus / institution_tier）:
{candidates_text}

总判定原则：
1. 先看 JD 的岗位标题、团队名、工作动词、交付物、硬技能要求，再看公司名；不得只因公司是典型公司就高置信归类。
2. 主 sub_cat 必须来自候选列表；secondary 也必须来自候选列表或为 null。
3. 如果 JD 明显命中某个边界规则，但候选列表没有对应 sub_cat，只能在候选列表中选"最不坏"的近邻，并把 confidence ≤ 0.45、evidence_path="low_signal"，reasoning 必须写明"候选缺失/弱匹配"。
4. 如果 JD 是销售、运营、产品支持、承做、发行、客户覆盖、前端/全栈开发、金融科技平台等非投研/非交易岗位，不得因为出现"研究/交易/量化/AI/基金/固收"等词而误归到研究员、交易员或 FOF 投资。
5. confidence 规则：
   - hard_jd: JD 中有明确标题/团队/工作内容/硬技能 2 项以上直接支持所选 sub_cat，confidence 可为 0.75-0.95。
   - boundary_inferred: JD 信号明确但文本短，主要依靠标题/团队/边界排除判断，confidence 0.55-0.75。
   - low_signal: JD 只有公司名、泛化岗位名、AI/量化/金融泛词，或候选列表缺少正确类，confidence ≤ 0.55。
6. reasoning ≤ 80 字，只写"选择证据 + 排除的主要混淆项"，不要写长推理。

六类强边界规则：

一、机构销售 / Sales / Sales Trading / 销售支持 ≠ 卖方研究员 / 固收交易员 / 利率宏观 / 信用研究
- 命中关键词：机构销售、销售助理、客户经理、客户组、公募客户、保险客户、华北/华东/华南客户组、股销、股票销售、全球利率销售、全球信用销售、Rates Sales、Credit Sales、Sales、Sales Assistant、Client Coverage、客户服务、销售材料、路演支持、投资者覆盖、交易对手覆盖。
- 若工作内容是服务机构客户、客户沟通、路演安排、销售材料、产品推介、交易询价协调，优先选"机构销售·销售支持"（若在候选中）。
- 不选卖方研究员：除非 JD 明确写独立写研报、行业跟踪、盈利预测、模型搭建、路演观点输出。
- 不选固收交易员：除非 JD 明确写现券/回购/资金交易、报价执行、头寸管理、风险限额、P&L。
- 不选利率宏观/信用研究：除非 JD 明确写宏观利率报告、信用主体研究、评级框架、投资建议。
- "Trading Intern" 只有在出现订单执行、报价、做市、头寸、对冲、交易系统时才归交易；若核心是客户覆盖/销售支持，则归机构销售。

二、债券发行 / DCM / ABS / REITs 承做 ≠ 固收交易员 / 信用研究员 / 固收+多资产 / 投行 IBD
- 命中关键词：债权资本市场、DCM、债券承做、债券承销、债券发行、发行执行、发行上市、ABS、资产证券化、REITs、类 REITs、存续管理、募集说明书、申报材料、反馈回复、尽调底稿、评级沟通、交易所/协会报送、簿记建档。
- 若工作内容是一级市场发行、承做承销、材料制作、项目执行、ABS/REITs 存续管理，优先选"债券承做DCM·ABS/REITs"（若在候选中）。
- 不选固收交易员：二级市场交易岗必须有买卖报价、现券/回购、资金交易、头寸、交易台。
- 不选信用研究员：信用研究必须以主体/债项研究、评级、信用利差、违约风险、投资建议为核心，而不是发行材料执行。
- 不选固收+多资产：固收+必须有组合投资、转债/债券/权益/大类资产配置、久期/仓位/策略研究。
- 只有 IPO、再融资、并购、股权资本市场、招股书、上市辅导等股权投行业务，才选"投行 IBD"；债券/ABS/REITs 优先 DCM/ABS 类。

三、公募权益研究 ≠ 泛行业研究 / 卖方研究 / 宏观研究
- 公募基金公司、基金管理公司、基金经理助理、权益投资部、研究部、行业研究员、助理研究员、资深研究员，且工作服务投资组合/基金经理/持仓决策，优先选"公募权益研究员"。
- 即使标题是"机械/非银/TMT/医药/周期行业研究员"，只要公司是公募基金且职责是买方投资研究，也优先公募权益研究员；不要误选"行业研究员·TMT-医药-周期"。
- "行业研究员·TMT-医药-周期"用于非公募买方/主观私募/产业基金/泛买方行业研究；不得覆盖券商研究所卖方，也不得覆盖公募权益研究。
- 券商研究所、研究助理、新财富团队、行业组、对外研报、客户路演，优先选对应"卖方研究员·TMT / 消费医药周期 / 宏观策略"。
- 国内宏观、海外宏观、市场策略、利率策略、大类资产策略，若是公募/资管买方投研，可选"利率宏观策略"；若是券商研究所对外研报，选"卖方研究员·宏观策略"；不要选公募权益研究员。
- 金融工程组/量化及 ESG 组在券商研究所通常是卖方金工/金融工程研究，不是买方 Quant，除非 JD 明确写自营投资、组合交易、alpha 研究。

四、AI 五子赛道边界：AI PM / AI算法业务 / Agent工程师 / LLM算法post-train / 多模态推理优化 / AI应用开发工程师
- AI PM：关键词是产品经理、策略产品、需求分析、PRD、用户增长、功能 owner、业务指标、A/B 实验、bad case、产品迭代；不以模型训练为主。风控策略产品、AI战略/产品策略若无算法训练，可归 AI PM。
- AI算法业务：关键词是搜推广告、搜索、推荐、排序、召回、CTR/CVR、风控、反欺诈、数据挖掘、特征工程、业务模型上线、A/B 实验、在线指标。它是业务算法，不是大模型 post-train。
- Agent工程师：关键词是 Agent、RAG、tool calling、workflow、ReAct、多步推理、记忆、插件、Multi-Agent、Dify/Coze/LangChain、工具调用链路。只有"Agent算法/Agent平台/Agent应用编排"才优先 Agent。
- LLM算法post-train：关键词是 SFT、RLHF、DPO、PPO、GRPO、Reward Model、偏好数据、指令微调、对齐、训练诊断、数据飞轮、Reward Hacking、模型评测/训练闭环。只有"大模型/LLM/Seed"字样但无训练/对齐信号，不得高置信归 post-train。
- 多模态推理优化：关键词是 VLM、多模态、图文/视频/语音/OCR、CLIP、Q-Former、推理加速、KV Cache、Speculative Decoding、TensorRT、vLLM、量化压缩、模型 serving、端侧部署、QPS/延迟。普通机器学习引擎、前端开发、业务算法不得归此类。
- AI应用开发工程师：关键词是前端、后端、全栈、客户端、服务端、工程开发、业务系统、AI应用落地、页面/接口/工程架构。若只是把 AI 能力接入业务产品，不做模型训练/Agent核心编排，优先选 AI应用开发工程师。
- "机器学习引擎/ML Infra/性能工程"若没有多模态或推理优化信号，不得归多模态；若发生在量化交易系统且有行情/回测/订单/交易链路，才可归量化开发QD。

五、FOF 三类 / 基金产品 / 基金运营 / 中后台 / 投后边界
- 自营FOF：资金属性是券商/信托/机构自有资金或自营盘，工作是底层基金筛选、管理人尽调、资产配置、组合跟踪、投资委员会材料；不得把财富投顾或资管产品 FOF 归入自营。
- 资管FOF：资金属性是公募、理财子、保险资管、券商资管等资管产品，工作是 FOF/MOM 产品投研、基金经理研究、组合构建、归因、量化择时。
- 财富管理FOF：客户属性是私行、财富管理、基金投顾、高净值客户、家办、养老投顾，工作是客户组合建议、基金投顾策略、投顾支持、适当性和配置方案。
- 基金产品运营·中后台：关键词是基金运营、产品助理、产品支持、产品团队、产品基础设施、估值清算、TA、登记、份额、申赎、运营报表、产品材料、产品生命周期、存续管理、系统/数据维护。只要没有底层基金投资研究/管理人尽调，不得归 FOF 投资。
- 公募基金中后台：公募内部运营、合规、风控、运营管理、渠道/产品支持、数据维护等非投研岗位；不得把公募权益研究员、基金经理助理、FOF研究员归入中后台。
- PE投后VC行研：必须有 PE/VC/股权投资/投后管理/投资尽调/IC memo/项目 sourcing/行业 mapping/被投企业经营分析。企业战略研究、互联网战略、无人机战略、纯行业研究不得归 PE投后VC行研。

六、金融科技 / 量化 / AI量化边界
- AI 量化工程师：必须同时出现"AI/ML/DL/大模型/深度学习"等技术信号 + "量化投资/alpha/因子/交易/组合/行情/order book/收益预测/策略研究"等投资交易目标。公司是 DeepSeek、字节、美团等 AI 公司本身不能支撑 AI 量化；DeepSeek 只有在岗位明确隶属 High-Flyer/幻方量化或金融交易目标时才可归 AI量化。
- 量化因子工程师：因子挖掘、alpha、IC/IR、Barra、回测、截面/时序、股票/CTA/指增策略；不包含客户研究、ESG数据整理、金融科技产品。
- 量化研究员·中频/高频：必须有策略研究、收益预测、盘口/订单簿、做市、高频交易、统计套利、实盘/仿真回测；高频更强调 tick、低延迟、盘口、做市、博弈。
- 量化开发QD：必须有交易系统、回测框架、行情数据、订单路由、低延迟、C++、Linux、分布式数据平台，且服务量化交易链路。普通 AI/ML infra、前端/后端工程不得仅因公司是量化私募而归 QD。
- 金融科技·量化平台：关键词是金融科技、数字金融、客户研究、量化平台、金融工程工具、ESG量化、风险模型、投研平台、机构客户分析、数据产品；没有 alpha/PnL/交易目标时，不得归量化因子或买方 Quant。
- 买方 Quant/海外 HF 类只在 JD 明确是投资分析、量化策略、衍生品定价、组合优化、风险归因且由买方投资机构招聘时使用；券商研究所金融工程组不是买方 Quant。
- 公司名或部门名中有"量化/AI/金融科技"但职责是销售、产品、平台、客户、ESG、运营，必须按职责归类，并下调 confidence。

industry_focus 判定：
- 从所选 sub_cat 的 industry_focus_candidates 词表中选 1-3 个最 fit 的。
- 若 JD 只给公司/部门，没有行业方向，选该 sub_cat 最通用的 1 个，并把 evidence_path 设为 boundary_inferred 或 low_signal。

institution_tier 判定：
- 从所选 sub_cat 的 institution_tier_candidates 词表中选 1 个最 fit 的。
- 优先按公司实体和部门判断；不得把母公司、子公司、合并后公司、同前缀公司混用。
- Citadel 与 Citadel Securities 必须拆开；中金公司/中金基金/中金财富，中信证券/中信建投/中信银行，国泰君安/海通/国泰海通/国泰基金，平安证券/平安银行/平安资管必须按精确实体判断。

输出要求：
- 只输出一个 JSON object，不要 markdown，不要解释。
- sub_category 必须在候选列表内；sub_category_secondary 必须在候选列表内或为 null。
- evidence_path 只能是 "hard_jd" / "boundary_inferred" / "low_signal" 三者之一。
- confidence 是 0-1 小数。
- reasoning ≤ 80 字。

输出 JSON schema：
{{
  "sub_category": "<sub_cat 名，必须在候选列表内>",
  "sub_category_secondary": "<sub_cat 名 或 null>",
  "industry_focus": ["..."],
  "institution_tier": "...",
  "confidence": <0-1>,
  "evidence_path": "hard_jd | boundary_inferred | low_signal",
  "reasoning": "<≤80字，写选择证据 + 排除主要混淆项>"
}}

---

## B. Taxonomy 增删表

### 新增 sub_cat (净 +5, 29 → 34)

| 新 sub_cat | 隶属 strategy | 跟现有 sub_cat 区分 | typical_companies 5 个 |
|---|---|---|---|
| 机构销售·销售支持 | 卖方研究 | 边界 = 服务机构客户、销售材料、路演支持、客户覆盖、交易询价协调；不是写研报的卖方研究员，不是管头寸/P&L/报价执行的交易员 | 中金公司, 国金证券, 中信证券, 华泰证券, 国泰海通证券 |
| 债券承做DCM·ABS/REITs | 固定收益 | 边界 = 一级市场债券/ABS/REITs 发行承做、材料制作、报送、簿记、存续管理；不是二级交易，不是信用研究，不是固收+组合投资 | 中信证券, 中金公司, 平安证券, 国金证券, 国信证券 |
| 基金产品运营·中后台 | 多资产_FOF_衍生品 | 边界 = 基金产品、运营、估值清算、TA、产品基础设施、申赎/登记/存续/产品材料；不是 FOF 投研，不是公募权益研究，不是 PE/VC 投后 | 中金公司, 鹏华基金, 易方达基金, 招商银行, 中欧基金 |
| AI应用开发工程师 | AI 应用_PM_开发 | 边界 = 前端/后端/全栈/客户端/服务端开发，把 AI 能力工程化接入业务；不是 Agent 核心编排，不是 post-train，不是业务算法训练 | 字节跳动, 美团, 腾讯, 阿里巴巴, 小红书 |
| 金融科技·量化平台 | 量化 | 边界 = 金融科技、量化平台、客户研究、ESG量化、数字金融、风险/投研数据产品；没有 alpha/PnL/交易目标时不归量化因子、买方 Quant、AI量化 | 国金证券, 中金公司, 蚂蚁集团, 招商银行, 国信证券 |

### 删除 / 合并 sub_cat

| 现 sub_cat | 操作 | 理由 |
|---|---|---|
| AI 应用初创（头部创业） | 从 company ground_truth / must_have 公司表移除，改放 persona_bucket / institution_tier 桶 | 不是具体公司，不能按 119 公司 ground_truth 口径验证 |
| 买方 Quant | 不删除；从"卖方研究"迁移到"量化"，重命名为"海外买方量化/衍生品研究" | 当前 strategy 归属错位，容易把券商金工、机构业务、Trading Intern 误判为买方 Quant |
| 公募基金中后台 | 不删除；收窄为"公募管理人内部运营/合规/风控/运营支持" | 基金产品/运营/产品基础设施交给新增"基金产品运营·中后台"，避免和 FOF、产品助理混淆 |
| 自营FOF / 财富管理FOF / 资管FOF | 不合并；增加资金属性 discriminator | 三者不是同义词：自营=机构自有资金，财富=客户投顾，资管=产品组合投研 |
| 行业研究员·TMT-医药-周期 | 不删除；重命名为"非公募买方行业研究员·TMT医药周期" | 公募公司行业研究应归"公募权益研究员"，券商研究所应归卖方研究 |
| PE投后VC行研 | 不删除；重命名为"PEVC投资研究·投后支持" | 排除企业战略、互联网战略、纯行业研究，保留股权投资/投后/尽调场景 |

### 拆分 / 重命名 sub_cat

| 现 sub_cat | 操作 | 拆成 / 改成 N 个 |
|---|---|---|
| 固收+多资产 | 收窄 + 新增 DCM 类分流 | 保留"固收投资研究·转债/多资产" 1 个；新增"债券承做DCM·ABS/REITs" 1 个 |
| FOF 三类 | 不新增，增加三类判定字段 | 自营FOF / 财富管理FOF / 资管FOF 仍为 3 个，但新增 capital_owner_type 内部字段：proprietary / wealth_client / asset_management_product |
| AI 应用_PM_开发 现 5 类 | 新增工程落地类 | 现 5 类 + "AI应用开发工程师" = 6 个，防止前端/全栈/应用开发误入 Agent/post-train |
| 量化类 | 新增非 alpha 平台类 | 现 5 类 + "金融科技·量化平台"，防止客户研究/ESG/数字金融误入量化因子或 AI量化 |
| 卖方研究 | 新增销售支持类 | 现卖方研究员/IBD/买方 Quant 迁移后，新增"机构销售·销售支持"，处理销售/客户覆盖样本 |

---

## C. 9 个 🔴 sub_cat 回炉指南

### AI 量化工程师
- 现 KB 主要问题: DeepSeek/大模型事实不能直接支撑"AI量化工程师"，公司名与岗位目标混用。
- 应改的关键字段: typical_companies 改为幻方/High-Flyer、鸣石、明汯、九坤、宽德等有量化投资链路的实体；DeepSeek 只保留在"High-Flyer/幻方关联说明"且不得单独当 must_have。
- 应改的关键字段: hard_req 必须同时包含 AI/ML/DL 技术 + alpha/因子/交易/组合/行情/order book/PnL 目标。
- 应改的关键字段: pitfalls 增加"AI公司/大模型岗位 ≠ AI量化""量化私募普通 ML infra ≠ AI量化"。
- 应补的证据来源: 官方 JD、量化私募 AI researcher/ML quant 岗、XHS 同 sub_cat 面经；common_knowledge 只能写"幻方/High-Flyer 属量化投资机构"及理由。
- 重做后 confidence 期望: medium；若补到 3+ 官方/JD 强证据，可升 high。
- 实施: Opus subagent 重做 KB + Pass 2 prompt 边界规则共同解决。

### 公募基金中后台
- 现 KB 主要问题: 把公募内部运营、产品支持、基金产品运营、FOF、权益研究混在一起，弱支撑较多。
- 应改的关键字段: typical_companies 保留易方达、南方、嘉实、华夏、鹏华等公募管理人；不要混入券商财富/产品基础设施作为 must_have。
- 应改的关键字段: hard_req 改为基金运营、估值清算、TA、合规风控、运营报表、基金从业、Wind/Office/运营系统。
- 应改的关键字段: pitfalls 增加"基金经理助理/行业研究员 ≠ 中后台""FOF研究 ≠ 中后台""券商/财富产品运营优先基金产品运营·中后台"。
- 应补的证据来源: 公募官网/校招 JD、基金运营/TA/合规风控实习 JD、XHS 同岗位面经。
- 重做后 confidence 期望: medium。
- 实施: Opus subagent 重做；新增"基金产品运营·中后台"承接非公募/产品基础设施样本。

### 固收+多资产
- 现 KB 主要问题: 过度吸收 DCM、固收交易、FOF、宏观策略，正例边界不够窄。
- 应改的关键字段: typical_companies 按公募固收+、理财子、保险资管、券商资管的投资/研究团队重列。
- 应改的关键字段: hard_req 必须含固收投资框架、转债、久期、收益率曲线、股债配置、组合/仓位/风险预算、多资产策略。
- 应改的关键字段: pitfalls 增加"债券发行承做/ABS/REITs ≠ 固收+""二级交易台 ≠ 固收+""FOF基金筛选 ≠ 固收+"。
- 应补的证据来源: 固收+基金/多资产投资研究官方 JD、理财子/保险资管资产配置 JD、XHS 同 sub_cat。
- 重做后 confidence 期望: medium。
- 实施: Opus subagent 重做 + 新增 DCM sub_cat 分流。

### 固收交易员
- 现 KB 主要问题: 把利率/信用销售、债券发行、机构客户支持误吸收为交易员。
- 应改的关键字段: typical_companies 按券商自营/资管交易台、公募固收交易台、银行金市部、理财子交易岗重列。
- 应改的关键字段: hard_req 必须出现现券/回购/资金/报价/询价/订单执行/头寸/风控/P&L/交易系统。
- 应改的关键字段: pitfalls 增加"Rates Sales/Credit Sales ≠ 固收交易""DCM/债券承做 ≠ 固收交易""信用研究 ≠ 交易"。
- 应补的证据来源: 固收交易实习 JD、银行金市/券商交易台官方 JD、交易台面经。
- 重做后 confidence 期望: medium-high。
- 实施: Opus subagent 重做；Pass 2 对销售/DCM 强制排除。

### 投行 IBD
- 现 KB 主要问题: 与卖方研究、债券发行/DCM、发行上市泛岗、资本市场岗混淆。
- 应改的关键字段: typical_companies 保留中信证券、中金公司、华泰联合、中信建投、国泰海通，并区分 IBD/ECM/DCM/研究所。
- 应改的关键字段: hard_req 聚焦 IPO、再融资、并购、财务顾问、尽调、招股书、DCF/三表/可比公司、pitchbook。
- 应改的关键字段: pitfalls 增加"债券承做/ABS/REITs 优先 DCM""券商研究所研究助理 ≠ IBD""发行销售/机构业务 ≠ IBD"。
- 应补的证据来源: 券商投行部/华泰联合/中金 IBD 官方 JD、SAIF/校招帖、同 sub_cat 面经。
- 重做后 confidence 期望: high。
- 实施: Opus subagent 重做；DCM 新类分流后回归测试。

### 结构化产品衍生品
- 现 KB 主要问题: 前台结构化/衍生品定价与产品运维、碳金融、财富产品支持混在一起。
- 应改的关键字段: typical_companies 保留中金、中信、华泰、国泰海通、中信建投等 OTC/全球市场/衍生品部门；产品运维不得作为 must_have。
- 应改的关键字段: hard_req 必须含期权定价、Greeks、波动率曲面、雪球/FCN/ELN/Autocall、OTC、对冲、结构设计。
- 应改的关键字段: pitfalls 增加"场外衍生品产品运维 ≠ 结构化前台""碳金融研究 ≠ 衍生品""财富产品支持 ≠ 结构化定价"。
- 应补的证据来源: 全球市场/场外衍生品/结构化产品官方 JD、衍生品做市/structuring 面经。
- 重做后 confidence 期望: medium-high。
- 实施: Opus subagent 重做；产品运维样本转入"基金产品运营·中后台"或低置信。

### 自营FOF
- 现 KB 主要问题: 公司表强证据不足，且与财富管理FOF、资管FOF、基金评价混淆。
- 应改的关键字段: typical_companies 只放能证明"自有资金/自营盘/机构自营配置"的券商、信托、保险、财务公司，不用泛银行/泛公募充数。
- 应改的关键字段: hard_req 增加 proprietary capital、自有资金配置、管理人尽调、FOF组合、底层基金筛选、投委会材料、绩效归因。
- 应改的关键字段: pitfalls 增加"私行客户投顾 ≠ 自营FOF""资管产品FOF ≠ 自营FOF""基金运营/产品助理 ≠ FOF"。
- 应补的证据来源: 自营投资/FOF投资官方 JD、校友/SAIF 来源、XHS 同 sub_cat；若 2 轮检索仍无强证据，降为 low 并减少 must_have。
- 重做后 confidence 期望: medium；证据不足则保持 low 但边界清晰。
- 实施: Opus subagent 重做；必要时把弱样本并入资管FOF/财富FOF而非强行保留。

### PE投后VC行研
- 现 KB 主要问题: 把量化私募、公募股权、企业战略、互联网战略研究混入 PE/VC 投资研究。
- 应改的关键字段: typical_companies 改为高瓴、红杉中国、IDG资本、腾讯投资、越秀产业基金等股权投资实体；移除无 PE/VC 证据的九坤/泛公募。
- 应改的关键字段: hard_req 聚焦行业 mapping、项目 sourcing、投资尽调、IC memo、财务建模、估值、投后经营分析、被投企业支持。
- 应改的关键字段: pitfalls 增加"企业战略/无人机战略/互联网战略 ≠ PEVC""卖方行业研究 ≠ PEVC""公募权益研究 ≠ PEVC"。
- 应补的证据来源: PE/VC/产业基金官方实习 JD、投后管理 JD、FA/投资分析 JD、XHS 同类面经。
- 重做后 confidence 期望: medium。
- 实施: Opus subagent 重做；Pass 2 对企业战略类降 low_signal 或排除。

### AI算法业务
- 现 KB 主要问题: meta/source 不足，业务算法与 LLM post-train、Agent、AI infra、前端开发混淆。
- 应改的关键字段: typical_companies 保留字节、阿里、美团、小红书、蚂蚁等有搜推广告/风控/数据挖掘业务算法的实体，并补 company×sub_cat 证据。
- 应改的关键字段: hard_req 聚焦搜索/推荐/广告/排序/召回/CTR/CVR/风控/特征工程/模型上线/A-B/在线指标。
- 应改的关键字段: pitfalls 增加"大模型训练/对齐 ≠ 业务算法""Agent/RAG ≠ 业务算法""前端/全栈开发 ≠ 业务算法""ML engine infra ≠ 业务算法"。
- 应补的证据来源: 大厂业务算法官方 JD、算法实习招聘页、XHS 同岗位面经；common_knowledge 必须写清"该公司有对应业务算法团队"的理由。
- 重做后 confidence 期望: medium-high。
- 实施: Opus subagent 整节回炉；Pass 2 AI 五子赛道规则同步上线。

---

## D. 数据结构改造方案 (6 段 JSON schema)

[完整 6 段 JSON schema — ground_truth_companies_v2 / common_knowledge 示例 / evidence_strength_rules / company_alias_v2 / company_ground_truth_rule + persona_bucket_v1 / entity_disambiguation_rules — 见 user 原 Call 1 输出, 入库时 parse 用]

---

## E. 实施 checklist (18 步)

[18 步 step-by-step — 见 user 原 Call 1 输出, 实施按这个跑]

---

**Call 1 状态**: ✅ 已 parse + 入库 (本文件 + Pass 2 prompt 替换待 step 3 实施)。
**预算消耗**: 1 / 10 calls
