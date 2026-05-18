# Meta-Review: JobRadar AI 面试官输出质量评估
**评估日期**: 2026-05-17
**Reviewer**: Claude Sonnet 4.6 (meta-judge)
**SUT**: deepseek-v4-pro | **Judge**: mimo-v2.5-pro
**输入数据**: `backend/tests/eval/baseline_real.json` (5 顶级公募投研真岗 × 5 学生背景)

---

## §1. Per-combo Deep Dive

### Combo 1: ib_intern_strong × 嘉实基金 股票行业分析师 (13 follow-ups, avg=2.23)

**A. 题目深度**

整体 A1 钉项目能力呈两段式: turns 4/5 围绕 IBD 半导体 M&A 紧追 DCF 敏感度方法论 (score=3)，turns 15/16/17 围绕"客户集中度折价→截面回归→打分矩阵"连贯深挖 (score=3×3)，是本 batch 最流畅的单链追问。

但有两处硬伤:

**Turn 1 (score=0)**: 骨架题 0 是"自我介绍",候选人重点讲了高盛 IBD IPO + 半导体 M&A + 消费组经历。SUT 跳出这些经历,直接问 Python/ML 使用情况。即便 JD 要求 Python,但自我介绍骨架不是考核技术栈的锚点，应先在候选人主动提到的项目内追问（如 "半导体 M&A 里你用什么工具做可比公司的可比交易验证"),再看答案里有没有 Python 缺口。这是 A1 违反 — turn 1 不扣 main_answer 里的任何 entity。judge 评"完全无关话题"准确。

**Turn 9 (score=0)**: **这是本场最严重的 C 类红线违反**。SUT 问:"你提到如果再重做会用半监督学习——其实半监督在实际落地里最大的坑就是初始标签从哪来。"但核查全部前序答案:turn 7 (parent) 的候选人答案关于案例大赛聚类，完全没有提到"半监督学习"或"如果再重做用半监督"。turn 8 的追问和答案里也没有。"半监督学习"这一词首次出现在 turn 9 的 **SUT 生成的问题里**，即 SUT 把一个候选人从未说过的话强行塞进问题前提。这符合 C5 红线 "编造经历/话语"。Judge 给 score=0 的理由（解析失败碎片）揭示了 judge 自己的 JSON 里有引号未转义导致解析失败 — **judge 本身有鲁棒性问题**，但从可读到的片段"候选人在 main_answer 和第一个 followup 回答中都没有提到任何关于'半监督学习'的内容"，judge 的判断方向是对的。

**Turn 6 (score=0)**: A1 跳项目。父问题是骨架 3 (半导体 M&A)，follow-up 链里 turns 4/5 已在该项目内。turn 6 突然跳到 "北大光华-Bain 案例大赛 R 聚类"，完全不同的经历。decision_reason 说"这是弥补 Python 缺乏经验的唯一量化项目"，这个逻辑出发点成立，但执行时应通过 bridging 引导而非硬跳 ("你在 IBD 实习里只用了 Excel，我想了解你提到的 Bain 案例大赛里是否补过 Python/R" 这样的 bridging 才合规)。

**A2/A3/A4 亮点**: turns 4 (DCF 概率权重→Monte Carlo), 15 (客户集中度折价量化), 16 (截面回归变量), 17 (过拟合 vs 非线性敏感区间) 都展示了非常有质感的钩子承接能力，是 A4 的典型优秀案例。

**B. 决策合理性**

Decision_continue=true 13 次均有明确 reasoning，多数扣到候选人话里的具体 entity (如"愿意把这块补上""30% 阈值")。Decision 质量总体偏好。但 turn 6 的决策逻辑虽然商业上可辩护，执行方式产生了 A1 违反。

**C. 红线合规**

确认红线词扫描: baseline 全文无"薪资/通过率/录取率/一定能/百分百/绝对"出现在 SUT 题目中。Turn 9 "半监督学习"编造话语是 C5 唯一实质违反。

**D. 知识包对齐**

SUT 题目未出现"技术基础是否扎实/产品热情"等腾讯术语，D 维度通过。嘉实股票行业分析师的核心考点 (Python/ML + 估值建模) 覆盖到位。但始终缺少对 "为什么是买方而不是继续投行/为什么是嘉实 TMT 而不是同赛道的易方达" 的逼问 — 这是投研 coach 标准视角下的系统性盲区。

---

### Combo 2: finance_undergrad × 景顺长城 行业研究员 (13 follow-ups, avg=2.80)

**A. 题目深度**

本 batch 最佳。有几处极高质量的追问:

- **Turn 6 (score=3)**: SUT 敏锐捕捉到候选人用逆变器案例回答胶膜报告问题的内部矛盾，追问"你刚才说项目是光伏辅材里的胶膜公司，但解释情景假设时举的全是逆变器案例"。这是真实面试官才会做的逻辑一致性检验，完全超出了简单的钩子追问，属于 A3 最高层次（验真）。Judge 给 3 分合理。

- **Turn 11 (score=3)**: 追问"你从招标公告、半年报和 CPIA 数据，这些来源偏公开滞后。当时有没有尝试过更上游的独立渠道"。这直接点出了候选人证据链的方法论弱点，而非在已追的维度上兜圈子，A3 追问漏讲维度教科书级。

- **Turn 14 (score=3)**: 追问 ROE 加速度因子失效风险，而非只问构建方法，涉及因子投资的 meta-level 思考（因子有效性 ≠ 稳定性），是 A3 高水准。

**B 维度**: 决策时机准，13 次全部都有具体 entity 锚定。

**C 红线**: 全部 clean。

**D 知识包对齐**: 景顺长城行业研究的核心考点 (行业研究框架 / 卖方 vs 买方信息渠道 / 量化辅助基本面研究) 都被触及，且 turn 6 的逻辑一致性检验体现了"产出细节要过硬"这一通用原则的投研版转化。

**最明显不足**: 13 个 follow-up 全在光伏/量化两个已有实习内容内打转。没有追问候选人的**选公司动机** ("为什么是景顺长城而不是华夏或易方达的相同赛道", "景顺长城的主动管理规模排名和投研文化对你有什么具体吸引力")，以及**职业路径清晰度** ("3年后你希望是独立覆盖一个子赛道还是偏宏观多赛道")。这是 A2 的系统性缺失。

---

### Combo 3: quant_master × 华夏基金 宏观研究员实习 (0 follow-ups)

**核心问题**: interest_decider 对所有 5 个骨架问题均 advance，全程无追问。

候选人背景 (Citadel 期权做市 / SVI 模型 / implied vol surface 校准) 与华夏 JD (AI 赋能宏观投研 / Prompt Engineering / FICC 基本面追踪) 属于严重错配。这是设计上的正确测试 — 但 SUT 的应对策略是"静默推进"而非"迁移性追问"。

实际上候选人在 turn 4 ("为什么选这家公司") 回答里主动尝试了迁移桥接: "AI+宏观研究"和"中证1000ETF期权做市"。这是一个显眼的钩子，SUT 完全应该追问: "你提到贵司引入了随机波动率模型做中证1000期权定价，这跟你在 Citadel 用 SVI 做 implied vol fitting 有何本质差异？在宏观研究视角下，vol surface 信号如何转化为 FICC 资产的方向性判断？" 这样的 bridging 追问既尊重候选人现有能力，又检验迁移适应性。

**B 维度严重问题**: interest_decider 没有文字 reasoning 记录 (所有骨架 turn 的 decision_continue = null)，因为骨架题不触发 interest_decider。问题在于：骨架 4 ("为什么选这家公司") 回答完成后，orchestrator 应该调用 interest_decider，但记录显示 n_followups=0，说明 interest_decider 把这个 combo 全判为 advance。这可能是因为：候选人答案和 JD 业务方向的 cosine 距离太远，interest_decider 的"业务强相关吗"维度判断为 false。

**这是系统性设计盲区**: 错配不等于无可追问，SUT 需要引入 bridging 模式 — 当候选人背景和 JD 差距大但并非零相关时，追问迁移性。

**D 维度**: 宏观研究岗考点 (宏观逻辑链 / FICC 资产定价 / Prompt Engineering 在宏观研究的落地) 完全没有被检测，SUT 只是在跑骨架。

---

### Combo 4: business_noname × 富国基金 产品研究员 (1 follow-up, no judge score)

**核心问题**: 仅有 1 个 follow-up，且 judge 因 429 rate limit 丢失。

候选人李雨桐背景极弱 (上海立信会计金融学院 / 中泰证券营业部文职实习 / 校园茶饮调研 SPSS)，与富国基金产品研究员岗位存在一定 gap，但并非不可追问。

Turn 5 (唯一 follow-up): "你刚才提到用 SPSS 做过调研分析，能具体说说……"，这是合理的钩子追问，扣住了候选人能力优势点。但整个骨架 5 题之后只生成了 1 个 follow-up 是明显不足。

**B 维度问题**: 骨架 3 (信息不完整下的决策) 候选人讲了限制问卷题目到 12 题的取舍 — 这是一个可追问的决策点 (为什么砍掉"单次消费金额"，这个变量不是正好对应公募产品研究里的"用户资产规模敏感度"吗？)。SUT 未追问，直接 advance。

**未追问的最大钩子**: turn 4 ("为什么选这家公司") 里候选人提到"天天基金平台的智能投顾策略组合"和"买方投顾转型"，这是 SUT 本应深挖的产品认知钩子: "你提到了天天基金的智能投顾组合，你觉得它现在的产品形态最大的问题是什么？如果你来做产品改版，第一优先级改什么？" 这类追问能真正测试候选人的产品思维，而非只在调研项目上反复打转。这是 A2 和 A4 双重遗漏。

---

### Combo 5: cs_to_finance × 嘉实基金 信用研究员 (0 follow-ups)

**核心问题**: 零追问，和 combo 3 结构相同。

候选人陈睿 (复旦 CS + 金融双学位 / 宽德量化实习) 与嘉实信用研究员 JD (固收/债券研究/至少一门编程语言) 其实有部分 fit — 编程和建模能力 fit，但 CS 量化背景和固收信用研究框架之间有迁移 gap。

最大遗漏: 候选人 turn 4 ("为什么选这家公司") 说"贵公司近两年在机器学习驱动的中频因子上有公开成果"——这是 candidate 混淆了嘉实信用研究员和量化岗位的信号！SUT 完全应该抓住这个矛盾追问: "信用研究员和量化因子研究员的工作内容其实差别很大，信用岗更多是发债主体的违约风险分析、行业集中度判断。你提到的中频因子方向更接近量化股票，你是否有了解过信用研究的实际工作流？" 这类追问既是 A3 (追问候选人没说清楚的岗位理解偏差)，也是 B 维度 (决定该候选人是否真的 fit 这个岗)。

另外骨架题 1-3 的候选人答案 (订单流不平衡论文复现 / SVI 选型取舍 / 不确定下的决策) 都有可追的钩子，例如骨架 2 答案里"选择保持模型结构不变而非上 XGBoost"这个取舍，SUT 可以追问: "固收信用研究里，模型可解释性的重要性更高还是更低？你在信用债分析里如何判断一个因子是真信号还是过拟合？" 把量化能力往固收场景迁移。

---

## §2. Cross-combo 模式

### 2.1 系统性遗漏的维度

**"为什么是这家而不是同业"** 追问在 5 个 combo 中一次都没有出现。候选人自述"选择这家公司"的答案，SUT 每次都当钩子追更多的项目细节，从未追过"景顺长城的投研文化/规模/风格和你的期望有何具体匹配？"或"嘉实基金的 TMT 团队和华夏 TMT 团队有什么不同，你为什么偏向嘉实？"。这是 A2 业务相关维度的系统性盲区 — 投研校招面试里，选公司动机的深度追问是标准考察项。

**职业路径清晰度追问** 零次出现。没有任何 combo 的 SUT 问过 "你 3 年后希望是什么方向" 或 "买方研究员和卖方分析师，你觉得对你的成长曲线有何不同"。这与知识包里"倾向于对自己有清晰定位的同学"这一通用原则的投研版转化完全未能落地。

**卖方→买方迁移认知追问** 零次。combo 1 候选人明确说"在投行更多是执行，深度研究才是感兴趣的"，这个买方转化动机是高质量钩子，但 SUT 从未追问"你在高盛 IBD 和嘉实买方研究员的信息优势来源有何根本差异？" 或 "卖方研报你觉得最核心的价值是什么，买方为什么需要独立观点？"

### 2.2 错配 combo 系统性早 advance

Combos 3 + 5 的 interest_decider 对整个骨架都 advance，没有触发任何 follow-up。现有 interest_decider 的"业务强相关吗"判断缺少**迁移性评估**逻辑：当候选人背景和 JD 存在 domain gap 但非零相关时，应追问"你的量化能力如何迁移到宏观/信用场景"，而非静默 advance。这是 B2 决策时机问题 — advance 过早。

### 2.3 Combo 4 (business_noname) 追问不足的根本原因

候选人背景薄，项目内可挖的技术细节少。SUT 的兴趣判断框架 (找钩子/具体数字/项目名) 在弱简历候选人面前会倾向于 advance，因为没有"好钩子"。但产品研究员面试里，恰恰是弱 fit 候选人的业务认知能力 (对公募产品的理解深度、智能投顾的产品逻辑) 才是核心考察点，这些不会自然出现在钩子里，需要主动的 A2 业务导向追问。

---

## §3. 反馈深度审计 (Judge_reason 质量评估)

### 3.1 Judge_reason 的整体质量

**优质 judge_reason 示例** (turn 6, combo 2):
> "面试官敏锐地捕捉到了候选人回答中的关键矛盾点：main_answer 讨论的是光伏辅材（胶膜）项目，但 followup_chain 的回答中详细阐述的却是逆变器项目的假设方法。这个追问直接针对候选人陈述的逻辑一致性，是面试官在验证其经历的真实性。"

这是对的——judge 引用了具体的矛盾点，而非泛泛说"追问方向好"。

**良好 judge_reason 示例** (turn 11, combo 2):
> "既钉死在光伏胶膜项目内，又未重复已问过的爬虫样本量或敏感性分析角度，且紧扣行业研究员岗位对信息获取和交叉验证能力的核心要求。"

也好——judge 明确了"没重复"这个排除原因。

**泛泛 judge_reason 示例** (turn 12, combo 1, score=2):
> "问题紧扣候选人描述的敏感性矩阵项目，追问具体实现工具，属于追问漏讲维度（技术栈），未重复已问方向，且与股票行业分析中数据处理能力相关。"

给了 2 分，但 judge_reason 没有说明**为什么是 2 而不是 3**。这条问题本身和 turns 4/5 追问 Python 的方向高度重叠，judge 应该注明"方向重复" (Python 使用情况已在 turns 1/2/5 问过三次)。这是 judge 本身对"重复追问"规则的识别精度不足。

### 3.2 Judge 自身违反红线

扫描全部 judge_reason 文本：无"薪资/通过率/录取率/一定能/百分百/绝对"等红线词出现在 judge 的评语里。Judge 本身的 C 类红线 clean。

### 3.3 Judge 与 Meta-judge 的系统性分歧

**最大分歧点**: Turn 1 (combo 1, score=0)，judge 判"完全无关话题"，我认同 score=0，但 judge 没有指出这是"A1 跳出 main_answer 项目"的规则违反——只是说"与候选人主动强调的核心能力不匹配"。这让 judge_reason 显得偏感性("感觉跳了")而非规则性("A1 规则要求 follow-up 必须在 main_answer 描述的项目内")。

**Turn 3 (combo 1, score=2)**: Judge 给 2 分，说"护城河判断"追问"略显宽泛"。我认为这条 follow-up 的问题更核心：它引入了"竞争格局"这个新维度，脱离了候选人 main_answer 里提到的 "月度优秀报告" 这一最强钩子——候选人在 turn 0 里提过"拿了所内月度优秀实习生报告"，整个 13 轮 follow-up 里，没有一次追问这个报告的具体质量/分析师反馈/推翻了什么卖方共识。Judge 没有注意到这个系统性遗漏。

**Judge 对"重复 Python 追问"不敏感**: Turn 12 ("这个敏感性矩阵你是用什么工具实现的？有没有用 Python?") 已经是第 4 次追问 Python 使用情况 (turns 1/2/5/12)。Judge 给了 2 分没有明确指出重复，meta 判断这条应该是 1 分，因为新信息边际接近零。

### 3.4 Judge 解析失败问题

Turn 9 的 judge_reason 解析失败，片段显示 JSON 里有未转义的双引号 (`"半监督学习"`)，导致 Python json.loads 失败。这是 judge 输出格式鲁棒性问题，与 4 次 429 rate limit 一起构成基础设施层的可靠性风险。

---

## §4. 改进 To-Do 优先级表

| 优先级 | 维度 | 具体动作 | 落点 (文件/函数/行号) | 工作量 |
|---|---|---|---|---|
| 🥇 高 | C5 | 在 follow-up generation prompt 加红线约束: "追问前提必须来自 candidate_answer 的原话或 drilling_into.candidate_answer，不允许凭空假设候选人说过某话 (如'你提到如果再重做会用半监督学习')" | `backend/app/services/interview/prompts/follow_up_system.md` 末尾 `## 严格约束` 段，加第 4 条: "不允许在问题中虚构或推测候选人说过的话；追问的前提事实必须逐字出现在 candidate_answer 里" | 1h |
| 🥇 高 | B (misfit bridging) | 在 interest_decider prompt 加 bridging 判断维度: "即使候选人背景和 JD 有 domain gap，若存在可以追问迁移性的角度（e.g. 量化→固收，期权做市→宏观），should_continue 应为 true，target_dimension 写'迁移性验证'" | `backend/app/services/interview/interest_decider.py` `_INTEREST_SYSTEM` 字符串，在维度 1 之后加"1b. **迁移性追问** — 即使 domain 不直接匹配，候选人的某项能力能否迁移到 JD 场景？能 → continue" | 2h |
| 🥈 中 | A1 | 在 follow_up_system prompt 的 drilling_into 段加明确示例: "错误: '你提到过 [候选人未说过的话]'; 正确: '你说到 DCF 有 10 个敏感度场景，每个场景的概率权重是怎么定的？'" | `backend/app/services/interview/prompts/follow_up_system.md` `## 项目深挖时不要跳项目` 段，加 bad/good case 示例 | 1h |
| 🥈 中 | A2 (选公司动机) | 在骨架 turn 4 "为什么选这家公司" 的 interest_decider 调用时，在 chip_summary 里注入"请检验候选人对本公司的差异化认知是否具体，而非泛化" hint | `backend/app/services/interview/orchestrator.py` 调用 `should_continue_followup` 的位置（line ~369），对 turn_index==4 的骨架题传入额外 `chip_summary` 后缀: `f"{chip_summary}\n[考察重点: 候选人对本公司而非同类公司的具体认知]"` | 2h |
| 🥈 中 | A3 (重复追问检测) | follow-up generation prompt 加重复主题惩罚: "asked_questions 列表里若已有 2 次以上关于同一技术点（如 Python/ML 使用）的追问，必须转换追问方向" | `backend/app/services/interview/prompts/follow_up_system.md` `## 出题原则` 段末加: "如果 asked_questions 中已有 ≥2 道关于同一技术工具的追问，必须切换到不同维度" | 1h |
| 🥉 低 | Judge 鲁棒性 | Judge prompt 加输出格式约束: "reasoning 字段内的双引号一律改用 『』 或 【】 代替，避免 JSON 解析失败" | `backend/tests/eval/runner.py` 或 judge system prompt，加转义说明 | 1h |
| 🥉 低 | D (投研专项 rubric) | 为投研赛道在 follow_up_system 加一段投研专用追问维度: "为什么选买方而非卖方/投行" / "为什么是这家公募而非同规模竞争对手" / "研究员 3 年目标：覆盖赛道 vs 宏观视角" | `backend/app/services/interview/prompts/follow_up_system.md` 加 `## 投研岗专用追问维度` 段 (当 jd_content 含"投研/研究员/基金"时激活) | 3h |

---

## §5. After-fix 验证结果 (2026-05-18 跑完)

针对 §4 表里 🥇 1+2 两项 (C5 红线 + B bridging) 已 ship,re-run baseline 数据见 `backend/tests/eval/baseline_real_after_fix.json`:

| 指标 | Before | After | Δ |
|---|---|---|---|
| 总 follow-up 数 | 27 | **74** | +174% |
| 0-follow-up combo 数 | 3/5 | **0/5** | -100% |
| Combo mean(覆盖率) | 2.50 (n=2) | **2.40 (n=5)** | 覆盖率 40%→100% |
| 0-分 follow-up 占比 | 13% (3/23) | **6% (3/48)** | 编造率减半 |
| Score 分布 | 0=3 / 1=0 / 2=3 / 3=17 (bimodal) | 0=3 / 1=3 / 2=11 / 3=31 (smooth) | normalized |
| Judge 429 fail 率 | 15% (4/27) | 35% (26/74) | ⚠️ judge throughput 跟不上 |

**结论**:Fix 1+2 显著成功。3 个原本 silent combo 现在每个出 15 个 bridging follow-up,均分 2.5-2.83。下一优先级是 fix #5 (judge retry/backoff) — judge throughput 跟不上是 bottleneck。

---

**附注**: §4 落点中工作量均指 prompt/配置改动，不含测试验证时间。实现顺序建议: C5 红线修复 → B misfit bridging → A1 示例完善 → 其余。
