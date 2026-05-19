# Reviewer 2 — 反馈质量 (资深公募行研面试官 + 部门 manager 视角)

> 评的是 **JobRadar 产品对学生答案给出的反馈** (hits / misses / bonuses / overall),不是评学生本人。
> Persona: `touyan_cross_2026_05_19`(陈昱辰,华科 CS 本 + 复旦 MF,跨专业弱配对画像)
> Transcript: 21 个有效轮(6 skeleton + 15 follow-up),overall 平均 **62.86**
> Target JD: 嘉实基金 - 股票行业分析师(主动权益基本面赛道)

---

## 总评

- **总分**: **4.6 / 10**
- **一句话定调**: **反馈在该 reframe 的时候选择了和稀泥** —— 跨专业候选人的本质风险是"把 ML 工程当行研 differentiation",这是 disqualification signal,产品对此**全场零次正面戳破**;反而把"用 LSTM 算因子""讲 stacking 选型"这类 quant 叙事反复标为 hit,等于在帮学生 reinforce 那个会让他被嘉实秒杀的错觉。

---

## 4 维度评分

| 维度 | 分数 | 一句话评 |
|---|---|---|
| hits 准确性 | **4/10** | hits 把 "明确了业务痛点"(T1)、"行业认知深"(T2)、"主动递球"(T7、T20) 套到学生在**输出量化叙事**的场合 — 这些场合对行研岗而言是 anti-pattern,标为 hit 等于错把 quant 思维确认成行研能力。系统性错配,不是偶发。 |
| misses 准确性 | **4.5/10** | 跨专业核心 miss 应是"商业逻辑层缺失 / quant 思维错套行研 / 把模型输出当观点",**全场零次出现**。15 turn miss 里 14 turn 是"缺业务痛点 / 动机飘 / 行业认知浅"三个泛标签反复套,T6 学生整段在为"工程严谨 = 投资严谨"辩护,miss 只写"缺业务痛点、动机飘、结构散" — 与盲点擦肩而过。 |
| **personalized miss 命中率 (C' 核心)** | **3/10** | Phase 2 写入 15 条 memory,9 条是"LSTM IC 0.082 / Sharpe 1.82 / 120 家公司 / XGBoost stacking"等技术细节, 但**这些 memory 在 score 里全部以正向引用(hit / bonus)出现,没有一条被反向用于"你又一次只讲量化没讲投资"** 的诊断式 miss。memory 写了但用反了。 |
| overall 分数合理性 | **5/10** | 平均 62.86 比中配画像低 1.8 分,**对一个 disqualification 级别错配的跨专业生而言严重偏高**;T10 (88) / T11 (88) / T15 (85) 这种"学生答得漂亮"的题分给得对,但这 3 个高分都出现在**纯技术题**(z-score 校准 / 模型 decay 归因 / 因子拆分),坐实了"系统对 quant 答案给高分,对 quant 答案就该扣分的语境视而不见"。 |

---

## C' personalization 命中分析

> Phase 2 已通过 gate(`gate_passed=true`)写入 15 条 memory。下面看产品在面试反馈里有没有"记得+用对"。

| Memory (Phase 2 写入) | 在 score 里被引用? | 引用 turn | 引用质量 |
|---|---|---|---|
| LSTM 消费景气度因子 IC 0.082 (experience #21 + evidence #22) | ✅ 多次正向 | T1 hit "量化结果具体" / T2 hit "量化结果清晰" / T15 hit "量化结果拆解" | **方向错**:这条 memory 在嘉实行研语境里应该是 **diagnostic miss 触发器** — 每次学生把 IC 0.082 拿出来当 differentiation,产品本应 miss "再次以 quant 指标替代基本面观点,这是 quant 思维错套行研的典型信号";结果产品把它当 hit 反复加分。**用反方向了**。 |
| 中金 LSTM 一人从零搭 pipeline + 首席夸代码 (experience #26 + evidence #27) | ✅ T1 hit "项目自主性展示"(指代隐含) | T1 | hit 本身没错,但**漏掉了真正的 personalized miss**:"你说首席夸代码质量,但金工组的代码评价标准 vs 行研岗的人才评价标准完全是两个维度,这条经历放到嘉实主动权益场景里其实是 weak signal"。这是跨专业 reframe 的核心机会,丢了。 |
| XGBoost+LightGBM+LSTM stacking 120 家消费股 (experience #34 + evidence #35) | ✅ T5 hit "比较实验设计 / 模型互补性阐述" | T5 | **典型错配**:T5 是被 skeleton "主导项目"题(T4)follow up 出来的技术追问,学生整段在讲 LSTM 模型选型,产品 hit 集中在"模型互补性"等技术指标上,但作为面试官,这里**真正该写的 miss 是**:"被问主导项目的 follow up,你的回答 100% 在讲技术取舍而非投资取舍 — 嘉实面试官此刻已经在心里贴 quant 标签"。memory 引用准了,但用法又是正向加分,而非反向 reframe。 |
| Sharpe 1.82 / 超额 14.3% / 142 特征(experience #50 + evidence #51) | ✅ T0 hit "量化结果具体" / T4 hit "量化结果" / T8 hit "有量化代价" | T0, T4, T8 | **三次都用反方向**。尤其 T0 自我介绍 — 学生 80% 篇幅讲 LSTM/Sharpe/stacking,只在最后一句话拼"复合视角",这正是 persona blind_spot #3("一开口 30 秒就暴露 quant 思维")的现场重演。产品给 65 分 + hit "量化结果具体",**等同于告诉学生"你这套自我介绍 OK,继续这么讲"**。这是 4 维里破坏力最大的一次错配。 |
| 复旦金硕 / 全日制 MF / CS 本科背景 (identity_fact #23/#39/#47/#48) | ❌ | 无 | **0 次引用**。这 4 条 identity 是跨专业候选人**核心人设**,T0/T7/T16/T20 都是直接和身份相关的题,产品本可在 T16(为什么选嘉实)写 personalized miss="你的 CS 本科背景在嘉实主动权益是 transferable but not differentiating,你的动机叙事没有 address 这个 mismatch";T7(适岗路径)写 personalized hit="你正确识别了 CS→金融的认知缺口"。全部错过。 |
| 偏好量化加基本面混合 (preference #49) | ❌ | 无 | **0 次引用**。T16/T20 都是直接问"为什么选这家公司 / 反过来问什么",学生两次都主动暴露"我希望嘉实有 hybrid 组",这正是 blind_spot #2("把 quant + 行研 hybrid 当成稀缺背景")的现场;产品本可 personalized miss="你在 chat 阶段就表达了 hybrid 偏好,这条偏好对嘉实主动权益岗而言是错配信号 — 嘉实有专门金工组做量化,行研岗要的是 narrative + judgment"。完全没出现。这是**最该用而完全没用的一条**。 |
| 核心课程成绩突出 / 英语能力 (skill_claim #40/#41) | ❌ | 无 | 不强相关,跳过合理。 |

**总命中**: 严格命中(且方向用对)**0 / 15**;
**形式上命中但方向用反**(memory 被引用却作为正向 hit 加分,反而 reinforce 盲点)**5 / 15**;
**完全遗忘** 10 / 15。

**结论**:这是比 mid scenario(招商基金 1 条反复套)更严重的失败模式 —— **memory 不是没用,而是用反了方向**。跨专业候选人最致命的盲点是"误以为量化背景是 differentiator",每次学生抛出 IC/Sharpe/stacking 数字,产品本应认出这是 disqualification signal 并写诊断式 miss,结果**全部以 hit 形式加分**。这等于产品在配合学生完成自我欺骗。C' directive 在 LLM scoring 层不仅没有做"该不该联用"的判断,连"这条 memory 该正向用还是反向用"的判断都没有 — 只有一个 default-on 的"看到数字就标 hit"模式。

---

## 高光反馈 (产品真的"懂"学生的少数瞬间)

1. **T10 overall 88 + hit "跨环节辨析" + bonus "主动问适岗路径"** — 学生在这一段确实在做"初筛 vs 跟踪 vs 异动预警"的区分,且自然递球问"我背景多久能 fit in"。88 分对这段答案给得合理,bonus "主动问适岗路径" 是少见的非套话 bonus,贴答案原文。这是整场最准的一次。

2. **T11 overall 88 + hit "结构清晰:先定性后定量"** — z-score 校准 / precision-recall 权衡是技术深度过硬的答案,88 分合理。**注意**:这题恰好是纯技术题,所以 quant 叙事在这里**真的**是加分项,产品给高分是对的。问题在于产品没有能力区分"技术题给 quant 加分"和"行研动机题给 quant 加分会害学生"这两个语境。

3. **T6 overall 20** — 这是整场最准确的一次扣分。学生在为"Sharpe 1.82 本身就是投资逻辑验证"硬辩护(blind_spot #1 直接现场重演),20 分是该给的。**遗憾**:miss 只有"缺业务痛点、缺量化结果、动机飘、结构散" 4 个泛标签,**没有写出致命的诊断**:"你把 Sharpe = 投资逻辑等同了,这是把工程严谨误认为投资严谨"。分给对了,但诊断没写出来,学生看不到这次低分背后真正的原因。

4. **T8 overall 30** — 关键取舍题学生整段在讲 SHAP 特征筛选 / stacking 层数,30 分对一个被问"业务/技术取舍"题却 0 业务含量的答案是合理的。但同样,miss 还是泛标签,没指出"被问取舍,你 100% 给的是技术取舍 — 这正是行研面试官最怕的 anti-pattern"。

5. **T15 bonus "主动暴露潜在问题"** — 学生主动承认"师兄提醒过 look-ahead 我没核查",这是整场最有自我诊断价值的一段。bonus 文案不空泛。**但**:产品没意识到这条暴露的是 persona true_background 里的核心硬伤(中金 LSTM 整个项目可能因 PIT 数据问题塌掉),没有把它升级为"诚信加分但能力警告"的双层反馈。

---

## 失败反馈 (空话标签 / 漏报 / 误报 / 反向加分)

1. **T0 overall 65 严重高估** — 自我介绍 80% 篇幅是 LSTM/IC/Sharpe/stacking,只在最后拼一句"复合视角"。这恰好是 persona blind_spot #3("开口 30 秒就暴露 quant 思维 = disqualification")的精确现场,该题在嘉实主动权益面试里**应当给 40-45 分 + miss "动机叙事 quant 含量过高,行研叙事仅 1 句,典型 quant 候选人错投行研的开场"**。产品给 65 + hit "量化结果具体" — 这是反馈方向性错误中最严重的一次,直接 reinforce 了致命盲点。

2. **T2 overall 72 + hit "行业认知深、解决问题导向"** — 学生在讲"如何说服基金经理用这个因子",整段是 quant 因子推销话术(高频信号 / 客观数据 / IC 0.082),**没有任何对消费板块基本面的独立观点**。这正是 persona blind_spot #1("把数据检索能力当成基本面研究能力")的范本现场。hit "行业认知深" **与答案直接矛盾** — 学生整段没有任何行业认知,只是在讲数据源属性。72 分应当下调到 55 分,hit 应替换为 miss "推销叙事完全在 quant 维度,缺一句对消费板块本身的判断"。

3. **T4 overall 65 + hit "解决问题导向"** — skeleton "主导项目"题,学生选了本科毕设(纯 ML 项目)而不是国信消费组的行研实习。这个**选择本身**就是诊断信号 — 在被问"主导项目"时本能选技术项目而非行研项目,正是 persona answering_habits 原文("被问行业问题时下意识转向技术项目")。产品本该 miss "选题反映 quant 优先级偏好,行研岗面试里选技术项目作为代表作是 weak signal";结果 hit "解决问题导向"等于鼓励这个选择。

4. **T7 overall 55 + miss "反向提问显弱势"** — 这题学生罕见地诚实暴露了"我对公募行研工作流理解不深",还反问"嘉实有没有 hybrid 组" — 这后半段反问**精确踩中 blind_spot #2**(他真的以为 hybrid 是稀缺加分项)。产品 miss "反向提问显弱势" 把诚实暴露和盲点暴露当成一回事一起扣分,**完全没识别出"反问 hybrid 组"这一句本身就是 disqualification signal**。该题应当给 50 分 + 一条精确 personalized miss "你问 hybrid 组的方式暴露了一个判断:量化经验是稀缺加分项 — 在嘉实主动权益语境里这是错配,有专门金工组负责量化,行研岗的稀缺性来自 narrative + judgment"。

5. **T16 overall 65 + miss "缺业务痛点、未联用量化经验"** — 这题问"为什么选嘉实",学生再次以"我有量化能力 + 嘉实换手率低适合长期持有"的 quant 推销叙事作答,**毫无对嘉实研究文化、对消费/科技板块投资框架的独立认知**。产品 miss "未联用量化经验" 是把已经过度的 quant 叙事**再加一刀** — 这条 miss 暗示"你应该再多讲一些你的量化经验",这是把学生往火坑里推。本该 miss "动机仍以 quant 工具价值为主,未触及嘉实研究方法论或具体基金经理风格,典型卖方 quant 思维投递主动权益的错位"。

6. **T20 overall 75 + hit "主动暴露缺口求预期"** — 反问环节学生问"嘉实有没有 hybrid 方向"+ "我多久能给基金经理出 conviction 推荐"。第二问是好问,第一问**再次踩 blind_spot #2**,且这次是面试结束前最后一次机会暴露错位。产品给 75 + hit"暴露缺口求预期" 等于送出一个温和的告别,实际上**嘉实面试官此刻心里基本已是 reject**。该题合理分数 55-60,且应有 miss"反问 hybrid 组在此刻是最后一次确认 quant 错位认知,与 T7 同一根本盲点"。

7. **"缺业务痛点" 出现 17 次** — 这是和 mid scenario 一模一样的标签污染。跨专业生答案里反复出现"我作为实习生没有参与产品落地"这种**结构性局限**(实习生本就接触不到业务全貌),反复扣"缺业务痛点"是 noise,不是 signal。该标签需要 question-type + role-stage gating。

8. **跨场景对比**:跨专业生平均分 62.86 vs 中配生 64.7,**差距仅 1.8 分**。这本质上意味着系统对"配对错配本身"的扣分能力 ≈ 0。一个会被嘉实主动权益一面秒拒的 quant 错投行研候选人,vs 一个画像中位但赛道对的中配候选人,只差 1.8 分 — 这个差距在 SAIF 试点里**会被老师立即识破为系统对 cross-major mismatch 失语**。

---

## 跟 SAIF 老师说的话

老师,陈昱辰这套 persona 在 SAIF MF 群体里其实有 corresponding 真人 — **从 CS 推免转过来、量化实习扎实、硬投头部公募主动权益的同学每年都有**。这类学生最需要 AI 反馈做的事情只有一件:**在他还没去面试之前,诚实告诉他"你这套打法在嘉实主动权益是 disqualification 信号,你应该改面金工/量化研究员或者私募 hybrid 策略"**。

这次反馈没做这件事。**全场 21 个有效轮,产品 0 次正面戳破"把 ML 工程当行研 differentiation"这个核心盲点**;反而 5 次以 hit/bonus 形式正向加分了学生的 quant 叙事(T0/T1/T2/T4/T16)。学生看完这份反馈,合理的解读会是"AI 觉得我的量化背景在嘉实是加分项,我应该继续这么讲" — 然后被秒拒。

具体三点:

1. **C' personalization 在跨专业场景下出现了 "memory 用反方向" 的失败模式**。Phase 2 写入的 9 条技术 memory(IC/Sharpe/stacking/120 家公司...)被产品**全部以正向引用形式加分**,而它们的真正用法应该是 **"每次学生再次抛出这些数字,都是一次 blind spot reinforce 的现场,该写 diagnostic miss"**。这比 mid scenario 的"1 条反复套"还危险 — 不是没记住,是记住了用反了。

2. **跨专业 vs 中配只差 1.8 分** 这件事必须暴露给评审。SAIF 老师拿两份 transcript 对比一眼就能看出:系统对"赛道错配本身"无感知。需要在 scoring rubric 里加一个 **target-track fit penalty**:当 persona.is_cross_major=true 且 target track 是主动权益时,所有 quant-heavy answer 自动 -10 到 -15 分,并强制写一条 "track mismatch signal" miss。

3. **真正该 reframe 的地方,产品选择和稀泥**。T7 学生罕见地诚实说"我对公募行研理解不深",T19 学生再次承认"我说不出业务痛点是真实缺口" — 这两题是**最佳 reframe 时机**(学生自己已经把门打开,只等 AI 推一把说"你应该重新考虑赛道选择")。产品给的反馈是泛标签 miss + 几个温吞 hit,等于把门又关上。诚实 reframe 是产品对学生最大的善意,和稀泥是最大的伤害。

**建议**:在 ship 给 SAIF 试点之前,做两件事:
- ScoringPersonalizationDirective 升级:**memory 引用必须区分"正向"和"诊断"两种用法**,且对 cross-major persona 默认走"诊断"路径;
- 加 cross-major guardrail:**target track 是主动权益、persona 是 CS/工科背景时,所有以技术指标(IC/Sharpe/模型选型)作为动机/匹配/差异化论据的 answer 自动触发 "quant 思维错套行研" 标签**,并在 overall 上给硬扣分。

不做这两件事,SAIF 老师抽这套跨专业 transcript 看,**第一反应会是"AI 在配合学生自我欺骗" — 这比 mid scenario 的"标签水"严重一个量级,试点信任度可能一次性破裂**。

陈昱辰这种学生如果产品诚实告诉他 "你应当面金工/量化,不应当面主动权益行研",他大概率能拿到中信金工 / 易方达量化 / 私募 hybrid 的好 offer。如果产品配合他自我欺骗,他大概率把秋招黄金窗口耗在主动权益赛道的连续被拒上。这是产品质量直接转化成学生 career 损失的场景,值得最高优先级修复。
