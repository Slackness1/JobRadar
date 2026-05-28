# GPT 5.5 Pro — Phase G Call 1 v2: Pass 2 prompt + Taxonomy + 9 红 KB 回炉

**生成日期**: 2026-05-29
**Call 编号**: 1 / 10 (10 calls 总预算)

## 背景

JobRadar Phase G v2 推荐链路: 4 万真实校招岗位 → Pass 1 (7 大类) + Pass 2 (29 sub_cat) + 三维 enrich → SQL recall + LLM rerank with 知识库 + 4-anchor narrative。

**Phase G 当前状态**: T0-T19 全 commit + T10/T12 跑批完成 (40k 帖 label 完成, 1795 帖 enriched)。

**两份 user audit 已完成**:
1. T13 200 帖 sub_cat 准确率 review — **76.4%** (未达 90% 验收线)
2. 119 公司 ground_truth audit — **78.5%** (含 common_knowledge), 53% 强证据
3. 29 sub_cat KB 综合可用准确率 — **72-78%** (3 绿 17 黄 9 红)

**你 (GPT 5.5 Pro) 的任务**: 不重做 audit (已完成), 只给 5 个可执行产出 — 新 Pass 2 prompt + Taxonomy delta + 9 红 KB 回炉指南 + 数据结构改造 + 实施 checklist。

---

## Part 1 — User Audit 摘要 (已知问题, 别重做)

### Ground truth audit (149 must_have 行)

**统计**: {'通过-强': 79, '通过-常识/中': 38, '弱支撑': 9, '需补标签': 9, '需修正': 3, '需补证据': 11}

**3 个明确修正 (必须 fix)**:
- ** × AI 量化工程师**: DeepSeek 的 LLM 事实强，但“AI量化工程师”只用“源自幻方”无法支撑；应改到幻方/High-Flyer，或补 DeepSeek 本身量化岗位证据。 | 原证据: taxonomy_doc; demo_v1
- ** × 量化研究员·高频**: 当前公司名和 source 是 Citadel 对冲基金，但 note 写 Citadel Securities 高频/做市；建议拆分/改名为 Citadel Securities。 | 原证据: 可见摘录同 sub_cat 1 条; common_knowledge 可支撑: 头部对冲基金; taxonomy_doc
- ** × Agent工程师**: 这不是具体公司，不能按“119家公司”口径验证；建议改为 persona/桶，不放 company ground truth。 | 原证据: taxonomy_doc; demo_v1

**8 条需补证据** (列出名单, 不是错但 source 字段不够硬):
  -  × 自营FOF
  -  × 财富管理FOF
  -  × 量化开发QD
  -  × 买方 Quant
  -  × 信用研究员
  -  × 财富管理FOF
  -  × 多模态推理优化
  -  × 固收交易员
  -  × AI算法业务
  -  × 资管FOF

**8 条需补 source 标签** (事实大概率对, 标签缺 common_knowledge):
  -  × LLM算法post-train
  -  × Agent工程师
  -  × LLM算法post-train
  -  × AI算法业务
  -  × AI算法业务
  -  × LLM算法post-train
  -  × Agent工程师
  -  × Agent工程师
  -  × AI算法业务

**7 条弱支撑** (大方向合理但具体 sub_cat 支撑不够硬):
  -  × 利率宏观策略
  -  × 结构化产品衍生品
  -  × 资管FOF
  -  × 固收+多资产
  -  × 信用研究员
  -  × LLM算法post-train
  -  × 公募基金中后台
  -  × 公募指数研究员
  -  × 固收+多资产

### Sub_cat 知识库 audit (29 sub_cat 综合可用 72-78%)

**🟢 可直接使用 (3 个)**: 行业研究员·消费, 卖方研究员·消费医药周期, LLM算法post-train

**🟡 可用但需脚注 (17 个)**: 公募指数研究员 / 公募权益研究员 / 行业研究员·TMT-医药-周期 / 量化因子工程师 / 量化开发QD / 量化研究员·高频 / 量化研究员·中频 / 信用研究员 / 利率宏观策略 / 买方 Quant / 卖方研究员·TMT / 卖方研究员·宏观策略 / 财富管理FOF / 资管FOF / AI PM / Agent工程师 / 多模态推理优化

**🔴 必须回炉 (9 个)**: AI 量化工程师, 公募基金中后台, 固收+多资产, 固收交易员, 投行 IBD, 结构化产品衍生品, 自营FOF, PE投后VC行研, AI算法业务

### User 列的 8 大优先修问题 (你直接照办)

1. **0 XHS 提及 + must_have 公司加脚注**: 拆 `XHS_supported` vs `industry_common_sense_added`
2. **修 meta vs 公司表口径**: 至少 7 个 sub_cat 的 `company_mentions` 跟公司表 XHS 提及数合计冲突 (AI 量化 / 卖方宏观 / AI PM / Agent / LLM post-train / 多模态推理优化 / AI算法业务)
3. **AI算法业务整节回炉**: meta 缺失, 公司表全 0 提及, 应降 low 或补新证据
4. **自营FOF整节回炉**: 公司表全 0 提及, 应降 low 或补 JD/校友
5. **薪酬信号改写**: 区分「个案信号」「市场传闻」「官方约束」, 不写整体行业薪资
6. **XHS 摘录 ≠ 结论**: e.g. Optiver「ML 秒拒」是单帖夸张, 不应升级为正式 pitfall
7. **大类混杂 sub_cat 拆细**: 买方 Quant / TMT-医药-周期 / 固收+多资产 / FOF 三类 / PE投后VC行研
8. **招聘节奏只在官方/半官方来源时写死**: 易方达 4 月网申有 XHS+招聘页对得上, 其它 sub_cat 改成「行业经验窗口」

---

## Part 2 — T13 200 帖 review 76.4% — 6 类错误 + 43 ✗ 样本

### 6 类错误模式 (reviewer 手工归类)

```
- 机构销售/销售支持被误归为研究员或交易员：#9、#28、#42、#74、#135、#139、#172、#178、#196、#200。
- 债券发行、DCM、ABS/REITs承做与固收交易/信用研究混淆：#18、#65、#99、#100、#133、#176。
- 公募权益研究与泛行业研究、宏观研究混淆：#26、#51、#72、#119、#170。
- AI/LLM应用、Agent、post-train、Infra边界混淆：#47、#61、#110、#113、#125、#130、#157、#162、#166。
- FOF、基金产品、基金运营/中后台和投后/FOF投资混淆：#1、#35、#46、#121、#184、#189。
- 金融科技/量化/AI量化边界混淆：#80、#104、#129、#145。
```

### 43 个 ✗ 错判样本 (LLM 标错, reviewer 已给正确 sub_cat)

**✗ #9. 国金证券 — 机执委\-公募华南\-机构销售助理（2027届暑期）\(J16504\)** | LLM 标 `卖方研究员·宏观策略` (conf 0\.75)
  - reviewer 备注: ?

**✗ #10. 东吴证券 — 研究所 研究助理（金融工程）\(J11644\)** | LLM 标 `买方 Quant` (conf 0\.84)
  - reviewer 备注: ?

**✗ #18. 国金证券 — 资管\-ABS后台助理实习生（日常实习）\(J16553\)** | LLM 标 `固收\+多资产` (conf 0\.73)
  - reviewer 备注: ?

**✗ #21. 国金证券 — 公司直属\-产品经理实习生\(J16366\)** | LLM 标 `公募基金中后台` (conf 0\.60)
  - reviewer 备注: ?

**✗ #22. 国金证券 — 研究所\-非银组\-研究助理（2026年春招）\(J16410\)** | LLM 标 `卖方研究员·消费医药周期` (conf 0\.55)
  - reviewer 备注: ?

**✗ #26. 鹏华基金 — 基金经理助理/资深研究员** | LLM 标 `行业研究员·TMT\-医药\-周期` (conf 0\.95)
  - reviewer 备注: ?

**✗ #28. 国金证券 — 机执委\-公募/保险华北\-机构销售助理（2027届暑期）\(J16506\)** | LLM 标 `卖方研究员·宏观策略` (conf 0\.73)
  - reviewer 备注: ?

**✗ #35. 中金公司 — 项目实习生\-基金运营\(J18291\)** | LLM 标 `PE投后VC行研` (conf 0\.46)
  - reviewer 备注: ?

**✗ #42. 中金公司 — 项目实习生\-全球利率销售团队跨境销售组\(J19308\)** | LLM 标 `利率宏观策略` (conf 0\.87)
  - reviewer 备注: ?

**✗ #44. 国金证券 — 研究所\-2027届暑期实习生（金融工程组）\(J16498\)** | LLM 标 `买方 Quant` (conf 0\.76)
  - reviewer 备注: ?

**✗ #46. 国金证券 — 资管\-ABS存续管理实习生（日常实习）\(J16401\)** | LLM 标 `信用研究员` (conf 0\.65)
  - reviewer 备注: ?

**✗ #51. 国泰基金 — 机械行业研究员** | LLM 标 `行业研究员·TMT\-医药\-周期` (conf 0\.95)
  - reviewer 备注: ?

**✗ #61. 字节跳动 — 前端开发实习生（AI娱乐方向）\-猫箱** | LLM 标 `Agent工程师` (conf 0\.73)
  - reviewer 备注: ?

**✗ #65. 平安证券 — 债权资本市场实习生** | LLM 标 `固收交易员` (conf 0\.69)
  - reviewer 备注: ?

**✗ #72. 招商基金 — 研究员（国内宏观）** | LLM 标 `公募权益研究员` (conf 0\.87)
  - reviewer 备注: ?

**✗ #74. 中金公司 — 项目实习生\-全球利率销售团队华东销售组\(J19364\)** | LLM 标 `固收交易员` (conf 0\.84)
  - reviewer 备注: ?

**✗ #75. 字节跳动 — AI战略实习生\-火山引擎** | LLM 标 `卖方研究员·TMT` (conf 0\.55)
  - reviewer 备注: ?

**✗ #80. 国金证券 — 公司总部\-金融量化博士实习生（客户研究方向）\(J16516\)** | LLM 标 `量化因子工程师` (conf 0\.90)
  - reviewer 备注: ?

**✗ #89. 国金证券 — 公司直属\-金融创新部\-场外衍生品产品运维岗（2027届暑期）\(J16465\)** | LLM 标 `结构化产品衍生品` (conf 0\.90)
  - reviewer 备注: ?

**✗ #99. 国信证券 — 发行执行岗实习生\(J13915\)** | LLM 标 `固收交易员` (conf 0\.75)
  - reviewer 备注: ?

**✗ #100. 国信证券 — 债券承做实习生\(J12351\)** | LLM 标 `信用研究员` (conf 0\.52)
  - reviewer 备注: ?

**✗ #104. 中金公司 — 项目实习生\-量化及ESG组\-ESG方向\(J19343\)** | LLM 标 `卖方研究员·消费医药周期` (conf 0\.79)
  - reviewer 备注: ?

**✗ #110. 美团 — 机器学习引擎项目实习生** | LLM 标 `多模态推理优化` (conf 0\.87)
  - reviewer 备注: ?

**✗ #113. 蚂蚁集团 — 【Plan A】财富AI Lab\-大模型Agent算法（实习）** | LLM 标 `LLM算法post\-train` (conf 0\.92)
  - reviewer 备注: ?

**✗ #119. 招商基金 — 研究员（海外宏观）** | LLM 标 `公募权益研究员` (conf 0\.90)
  - reviewer 备注: ?

**✗ #121. 鹏华基金 — 产品助理** | LLM 标 `资管FOF` (conf 0\.77)
  - reviewer 备注: ?

**✗ #130. 字节跳动 — 机器学习算法实习生\-Seed** | LLM 标 `AI 量化工程师` (conf 0\.52)
  - reviewer 备注: ?

**✗ #133. 国信证券 — 发行上市岗实习生\(J12113\)** | LLM 标 `固收交易员` (conf 0\.67)
  - reviewer 备注: ?

**✗ #135. 中金公司 — 项目实习生\- 华北区销售/销售助理** | LLM 标 `卖方研究员·TMT` (conf 0\.65)
  - reviewer 备注: ?

**✗ #139. 中金公司 — Project Intern\-Rates Sales\(J19309\)** | LLM 标 `利率宏观策略` (conf 0\.90)
  - reviewer 备注: ?

**✗ #145. 衍复投资 — 机器学习工程师（infra方向）** | LLM 标 `量化开发QD` (conf 0\.92)
  - reviewer 备注: ?

**✗ #169. 国信证券 — 碳金融研究岗实习生\(J13932\)** | LLM 标 `结构化产品衍生品` (conf 0\.52)
  - reviewer 备注: ?

**✗ #170. 鹏华基金 — 助理研究员** | LLM 标 `行业研究员·TMT\-医药\-周期` (conf 0\.95)
  - reviewer 备注: ?

**✗ #172. 中金公司 — 项目实习生\-全球信用销售团队\-华南客户组\(J19359\)** | LLM 标 `信用研究员` (conf 0\.73)
  - reviewer 备注: ?

**✗ #176. 鹏华基金 — 基金经理/投资经理** | LLM 标 `固收\+多资产` (conf 0\.82)
  - reviewer 备注: ?

**✗ #178. 国金证券 — 股销\-国际业务部\-机构销售助理（2026届春招）\(J16428\)** | LLM 标 `卖方研究员·宏观策略` (conf 0\.75)
  - reviewer 备注: ?

**✗ #183. 国信证券 — 机构业务岗\(J13836\)** | LLM 标 `买方 Quant` (conf 0\.57)
  - reviewer 备注: ?

**✗ #184. 中金公司 — 项目实习生\-财富管理部总行支持岗\(J18737\)** | LLM 标 `公募基金中后台` (conf 0\.73)
  - reviewer 备注: ?

**✗ #186. 美团 — 无人机\-战略研究专家** | LLM 标 `PE投后VC行研` (conf 0\.60)
  - reviewer 备注: ?

**✗ #189. 中金公司 — 项目实习生\-产品团队基础设施组\(J19277\)** | LLM 标 `财富管理FOF` (conf 0\.65)
  - reviewer 备注: ?

**✗ #192. Point72 — 2027 Point72 Academy Investment Analyst** | LLM 标 `量化研究员·中频` (conf 0\.46)
  - reviewer 备注: ?

**✗ #196. 中金公司 — 项目实习生\-全球信用销售团队华北客户组\(J12665\)** | LLM 标 `固收交易员` (conf 0\.70)
  - reviewer 备注: ?

**✗ #200. 中金公司 — Trading Intern\(J19190\)** | LLM 标 `买方 Quant` (conf 0\.55)
  - reviewer 备注: ?

---

## Part 3 — 现 Pass 1 + Pass 2 prompt 全文

### Pass 1 (7 大类, 默认 Flash)

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

## Part 4 — 29 sub_cat 当前状态全景

### 29 sub_cat 当前 status (User audit 评级)

| sub_cat | strategy | conf | enriched 数 | User 评级 |
|---|---|---|---|---|
| AI PM | AI 应用_PM_开发 | medium | 322 | 🟡 可用但需脚注 |
| AI算法业务 | AI 应用_PM_开发 | medium | 299 | 🔴 回炉 |
| Agent工程师 | AI 应用_PM_开发 | medium | 259 | 🟡 可用但需脚注 |
| LLM算法post-train | AI 应用_PM_开发 | medium | 316 | 🟢 可用 |
| 多模态推理优化 | AI 应用_PM_开发 | medium | 247 | 🟡 可用但需脚注 |
| 买方 Quant | 卖方研究 | medium | 5 | 🟡 可用但需脚注 |
| 卖方研究员·TMT | 卖方研究 | medium | 14 | 🟡 可用但需脚注 |
| 卖方研究员·宏观策略 | 卖方研究 | high | 23 | 🟡 可用但需脚注 |
| 卖方研究员·消费医药周期 | 卖方研究 | high | 37 | 🟢 可用 |
| 投行 IBD | 卖方研究 | low | 70 | 🔴 回炉 |
| 信用研究员 | 固定收益 | medium | 11 | 🟡 可用但需脚注 |
| 利率宏观策略 | 固定收益 | medium | 10 | 🟡 可用但需脚注 |
| 固收+多资产 | 固定收益 | low | 10 | 🔴 回炉 |
| 固收交易员 | 固定收益 | low | 24 | 🔴 回炉 |
| 公募基金中后台 | 基本面权益 | low | 14 | 🔴 回炉 |
| 公募指数研究员 | 基本面权益 | medium | 1 | 🟡 可用但需脚注 |
| 公募权益研究员 | 基本面权益 | medium | 10 | 🟡 可用但需脚注 |
| 行业研究员·TMT-医药-周期 | 基本面权益 | medium | 8 | 🟡 可用但需脚注 |
| 行业研究员·消费 | 基本面权益 | high | 1 | 🟢 可用 |
| 结构化产品衍生品 | 多资产_FOF_衍生品 | medium | 14 | 🔴 回炉 |
| 自营FOF | 多资产_FOF_衍生品 | medium | 3 | 🔴 回炉 |
| 财富管理FOF | 多资产_FOF_衍生品 | medium | 5 | 🟡 可用但需脚注 |
| 资管FOF | 多资产_FOF_衍生品 | medium | 6 | 🟡 可用但需脚注 |
| PE投后VC行研 | 相关补充 | low | 26 | 🔴 回炉 |
| AI 量化工程师 | 量化 | low | 9 | 🔴 回炉 |
| 量化因子工程师 | 量化 | medium | 19 | 🟡 可用但需脚注 |
| 量化开发QD | 量化 | medium | 16 | 🟡 可用但需脚注 |
| 量化研究员·中频 | 量化 | medium | 12 | 🟡 可用但需脚注 |
| 量化研究员·高频 | 量化 | medium | 4 | 🟡 可用但需脚注 |

---

## Part 5 — 你 (GPT 5.5 Pro) 必须输出的 5 个产出

**严格按以下 A-E 五段输出, 不写总结性废话, 不重复 user audit 内容, 直接给可执行内容**。

### A. 新 Pass 2 prompt 全文 (核心交付物)

新 Pass 2 prompt 必须解 T13 反映的 6 类边界混淆 (机构销售/DCM/AI 5 子赛道/FOF 三类/金融科技·量化·AI量化/泛行业 vs 公募权益)。直接给可 copy 的完整 prompt, 含:
1. 系统指令 + 候选 sub_cat 占位符 `{candidates_text}` (跟现版兼容)
2. **6 类边界规则** (每条形如 「机构销售/Sales Trading ≠ 卖方研究员 — 销售岗带'机构销售/客户经理'关键字 + 服务机构客户买卖股票/债券, 卖方研究员是写研报跑路演」)
3. 输出 JSON schema 新增 `evidence_path` 字段 (`hard_jd` / `boundary_inferred` / `low_signal`) 表明判断置信来源
4. 输出仍含 `sub_category`, `sub_category_secondary`, `industry_focus`, `institution_tier`, `confidence`, `reasoning`

```
<新 Pass 2 prompt 全文 — 直接 copy-paste 替代 PASS2_SYSTEM_PROMPT_TEMPLATE>
```

### B. Taxonomy 增删表 (基于 user audit + T13)

**新增 sub_cat** (按 T13 / user audit 隐含需要):
| 新 sub_cat | 隶属 strategy | 跟现有哪个 sub_cat 区分 | typical_companies 5 个 |
|---|---|---|---|
| <name> | <7 大类之一> | 边界 = ... | A, B, C, D, E |

**删除/合并 sub_cat**:
| 现 sub_cat | 操作 | 理由 |
|---|---|---|
| AI 应用初创 (头部创业) | 移除 (放 persona 桶) | user audit 确认: 不是具体公司 |

**拆分/重命名 sub_cat** (基于 user audit 8.7 大类混杂):
| 现 sub_cat | 操作 | 拆成 N 个 |
|---|---|---|

**约束**:
- 净新增 ≤ 5 个 (29 → 最多 34)
- 不动 7 大 strategy_type
- 拆分时给清楚的边界规则

### C. 9 个 🔴 sub_cat 回炉指南 (每个 5-10 行)

对每个 🔴 sub_cat, 按以下结构输出:

```
## <sub_cat>
- 现 KB 主要问题: <user audit 已列, 你简要复述 1 句>
- 应改的关键字段: <typical_companies 怎么改 / hard_req 怎么改 / pitfalls 怎么改>
- 应补的证据来源: <补 SAIF / common_knowledge: 理由 / XHS 同 sub_cat>
- 重做后 confidence 期望: <high / medium / low>
- 实施: <Opus subagent 重做 还是 Pass 2 prompt 边界规则解决 还是 删除>
```

9 个 🔴 sub_cat: AI 量化工程师, 公募基金中后台, 固收+多资产, 固收交易员, 投行 IBD, 结构化产品衍生品, 自营FOF, PE投后VC行研, AI算法业务

### D. 数据结构改造方案 (基于 user audit 8.4 修复规则)

User audit 已指出 6 个数据结构问题, 给具体的落地改造方案:

1. **source 从公司级下沉到 company×sub_cat 级**: 给 ground_truth_companies_v1.json 新 schema (含 evidence_per_sub_cat 字段)
2. **common_knowledge 必须显式写理由**: 给 5-10 个示例 (e.g. `common_knowledge:腾讯混元/大厂AI`)
3. **taxonomy_doc/demo_v1 算弱证据**: 单独不能支撑 must_have, 给判定规则
4. **alias 表**: 哪些公司名不能前缀匹配 (中信/中金/中国/国泰/平安), 给 alias 映射 JSON 草稿
5. **公司 vs 类型桶分开**: 给「公司 ground truth」和「persona/桶」两套 schema 边界
6. **拆分易混公司**: 给 Citadel vs Citadel Securities / 国泰君安 vs 海通 vs 国泰海通 等具体拆法

### E. 实施 checklist (我按这个跑)

给 step-by-step 可执行清单 (我后续按这个跑 T11-T13 重做)。每步注明:
- 谁做 (Opus subagent / DeepSeek / 你 GPT 5.5 Pro / 我手工)
- 输入 / 输出
- 验收标准
- 预计 token / 时间

重做完成定义: T13 准确率 ≥ 90% + 9 红 sub_cat 全升 🟡/🟢 + ground_truth 强证据率 ≥ 70%。

---

## 输入约束

- **不重做** user 已做的 audit (T13 200 帖 / 119 公司 / 29 sub_cat 评级)
- **不写**总结性废话 (e.g. 「整体可用 / 需要优化」) — user audit 已涵盖
- **直接给可 copy / 可执行的具体内容**
- Pass 2 prompt 必须中文 (跟现 prompt 一致), 含「{candidates_text}」字面占位符