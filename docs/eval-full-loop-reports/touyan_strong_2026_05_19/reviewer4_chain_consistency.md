# Reviewer 4 — 链路一致性评估 · 顾承翊(strong)

> 视角:AI 产品 reviewer。**判系统"懂"这个学生的程度** — chat 阶段说过的事,在面试出题与反馈里有没有被真正用上、且口径一致。

---

## 总评

**总分:62 / 100(及格偏下,链路有断点但底子比 mid 强)**

一句定调:**"系统消化了 chat 里的'明面经历',但完全没消化'真实空洞'— 出题命中了 50% 的简历关键词,反馈却 0 引用 chat 私密信号(古井贡 mentor 分歧、非共识 thesis 仅是 mentor 选题、保守 hedge 倾向),把一个'笔头一流但 conviction 借来的'强学生当成了普通强学生在测,SAIF 老师会觉得'还是没问到根上'。"**

---

## 4 维度评分表

| 维度 | 评分 | 关键证据 |
|---|---|---|
| 1. chat → 出题 引用率 | **55 / 100** | 19 条 memory 中 8 条在出题里被显式触发(42%);白酒/CXO/VECM/古井贡省外/嘉实持仓全中,但 4 篇报告 conviction、茅台金融属性非共识、高瓴珀莱雅 vs 贝泰妮、CFA/GPA、草根调研方法论被 chat 强调却**完全没出题** |
| 2. chat → 反馈 引用率 | **40 / 100** | 21 个 score 块共出现 ~95 个 hits/misses/bonuses tag,其中**仅 1 个**显式引用 chat 内容("结合草根调研经验"on turn 10),其余全是抽象框架词(结构清晰/颗粒度恰当/痛点明确);persona 真实空洞(汾酒 conviction 是 mentor 给的 / 周期阅历单薄)从未被反馈点破 |
| 3. 多次引用一致性 | **78 / 100** | 易方达 4 个白酒标的(茅台/汾酒/古井贡/泸州老窖+五粮液)跨 7 个 turn 反复出现,公司名 / 数字(78% / 0.62 / 0.58 / 8 季度对 6)在 chat 与面试中完全一致,无人格漂移;但**学生自己**对"4 篇报告 own 程度"的口径在 chat turn 3("全程是我own的")与面试 turn 8(承认五粮液/泸州只是跟踪型)之间出现温和漂移,反馈侧 0 捕捉 |
| 4. 出题深度递进 | **70 / 100** | 3 条 follow-up 链有明显递进:CXO 链(BD 痛点 → 200 家映射手工/NLP 取舍 → 效率量化数据)/ VECM 链(模型选型 → 数据口径痛点 → 资金成本因子回测 → 一批价价差锚)/ 古井贡链(hedge 取舍 → 研究瓶颈 → 负向验证回测);但**深到第 3-4 跳就开始原地踏步**,turn 17/18 问"持仓权重相关系数"被学生坦白没做后,turn 19 又退回讲案例,没继续向 conviction 根因深挖 |

**4 维加权平均: (55 + 40 + 78 + 70) / 4 = 60.75,定 62 分**

---

## chat → 面试 entity 引用率统计表

> 19 条 memory 逐条核对:在 22 turn 面试 question / reference_answer / score.hits/misses 中是否出现。

| # | category | summary | 在**出题**中? | 在**反馈**中? |
|---|---|---|---|---|
| 24 | experience | 8个月易方达白酒5家覆盖 | √ (q0/q4/q19,贯穿) | × (反馈未引用) |
| 28 | experience | 全程own从数据采集到建模 | × (出题侧没问"哪段是你 own 的") | × |
| 30 | experience | 数据被3位基金经理引用 | × (没出题追问这3位 PM 反馈) | × |
| 32 | experience | Python+Airflow CXO 体系沿用 | √ (q1 直接复用) | × |
| 42 | experience | VAR+VECM 8 季度对 6 | √ (q5 / q7 都问到模型) | × (78% 没在反馈里被质疑样本期) |
| 45 | experience | 高瓴港股美妆个护渠道效率 | × (**完全没出题**) | × |
| 52 | experience | 易方达白酒调研流程获组长好评 | × (q10 自然带出但题面没引用) | × |
| 25 | evidence | 易方达 8 个月 5 家白酒 | √ | × |
| 29 | evidence | 4 篇报告全程 own | × | × |
| 31 | evidence | 3 位基金经理引用 | × | × |
| 33 | evidence | CXO leading indicator 体系 | √ (q1/q2/q3) | × |
| 43 | evidence | VAR+VECM 联立模型 10年月度 | √ (q5/q6/q7) | × |
| 46 | evidence | 珀莱雅 vs 贝泰妮 GMV 交叉 | × (高瓴整段没出题) | × |
| 53 | evidence | 草根调研方法论(经销商-终端-卖方) | × (q10 学生主动带出,非问出来) | √ (turn 10 bonus "结合草根调研经验") |
| 36 | identity_fact | 复旦经济 GPA 3.91 排名第3 | × | × |
| 37 | identity_fact | 推免北大光华 | × (q0 自介带出) | × |
| 38 | skill_claim | CFA L2 通过 备考 L3 | × (**完全没出题**) | × |
| 44 | skill_claim | Bloomberg BQL 6个月 | × (**完全没出题**) | × |
| 54 | preference | 茅台批价韧性=金融属性 非共识 thesis | × (chat turn 12 主动抛非共识观点,面试**完全没追**) | × |

**汇总:**
- 出题命中: 8 / 19 = **42.1%**
- 反馈命中: 1 / 19 = **5.3%**
- 整体链路命中: 8 / 19 = **42.1%**(以"任一阶段命中"算)

**最致命的 3 条漏出:**
1. **memory#54 茅台金融属性非共识 thesis** — 学生在 chat turn 12 主动抛出 high-conviction 非共识观点,这是 persona blind_spots 第 1 条("把能漂亮表达误认为拥有")最适合 probe 的入口,面试**整场 0 追问**
2. **memory#45/46 高瓴 + 珀莱雅 vs 贝泰妮** — Tier-1 实习 label,persona true_background 明确说这是"亮丽 label",面试**完全跳过**
3. **memory#38 CFA L3 备考 + 44 Bloomberg BQL** — 硬核 credential,可作为 anchor 验证学生说话真实性,面试**没问**

---

## 高光时刻

1. **CXO follow-up 链 (turn 1→2→3)** — 系统抓住"BD 公告 + Clinical Trials"这个独特性,连追三层(痛点 → 自动化 vs 手工取舍 → 效率量化),turn 2 的"NLP 自动化 vs 手工 200 家映射"是整场最锋利的一刀,逼出学生 35% NER 错误率 + 手工 sense-making 副产品的真实思考
2. **VECM 链 turn 5 → 7 的资金成本因子追问** — 系统从模型选型→因子有效性逼着学生交出 69%→78% 这个**论文里没披露的数字**,并触发学生自己说出"置信区间应该加显眼标注"的元反思,这是反馈里**唯一一次**学生显式承认"我的论文有 caveat"
3. **古井贡 hedge 链 turn 12→13→14** — 系统问到"为什么选两情景而不强推",学生在 turn 13 出现 persona 预设的 2-3 秒停顿("……我先 organize 一下我的 thinking"),坦白说出"我对古井贡的理解比 mentor 浅,在内心里没把握",这是整场**最接近 persona 真实空洞的瞬间**

## 低谷时刻

1. **turn 4 与 turn 10 chat memory_validation rejection** — 两条 raw_excerpt_not_substring 错误,意味着系统在 chat 阶段就**漏存了**学生主动抛出的"古井贡非共识 + 茅台金融属性"两个最珍贵的非共识观点 evidence;直接导致后续 interview context registry 没法把这两条作为 anchor 给出题侧,**断链发生在第一公里**
2. **turn 17 持仓权重相关系数追问** — 系统问得很专业(用持仓权重变化和批价指数做相关),但学生坦白"没做过、样本量太小、定性描述",反馈给 55 分扣"未调用熟练统计工具" — 但**没有任何反馈引用 memory#42 学生明明会 VAR/VECM**,这本来应该是"你会 VECM 怎么不会做相关回归"的尖锐反差点
3. **turn 19 案例追问退化** — 系统问"提前发信号 + 后续验证",学生讲了一个完美 hedge 答案(分歧不大、mentor 更审慎),反馈给 72 分扣"回应对象偏差",**但完全没意识到这就是 persona 预设的"汾酒 2025 Q1 短期看错"那种边角微调** — blind_spot 第 1 条原文已预言,系统毫无觉察
4. **保险类 score 标签** — 21 个 turn 中有 13 个 turn 的 hits 含"结构清晰",**完全没区分**这究竟是优势还是 sell-side 训练副产物;persona 明确说她结构化是 IBD/sell-side 训练产物,反过来是 conviction 不足的 proxy,系统把 proxy 当优点反复奖励

---

## 跟 SAIF 老师说的话

老师,这个学生属于"流程一流 / conviction 借来"的 strong 候选,简历层面 perfect match。我们这次跑下来的链路一致性结论是:

**系统识别得出她是谁(出题贴着白酒/CXO/VECM/古井贡),但没识别出她差在哪。** 19 条 chat memory 里只有 8 条在出题里被用上,反馈里只有 1 条被显式引用;她在 chat 阶段主动抛出的两个"非共识 thesis"信号(茅台批价金融属性 / 古井贡省外节奏)**因为 evidence 抽取失败 + provider 没回灌**,面试里 0 追问 — 而 persona 预设这恰恰是她最该被压力测试的地方。

**最该补的两件事:**
1. **修 chat-side evidence 抽取的 raw_excerpt 匹配 bug**(turn 4/10 两次 rejection),否则 student 主动抛出的"非共识/反 mentor"信号永远进不了 context registry
2. **scoring rubric 引入"chat-anchored probe"维度** — 反馈侧不能只打"结构清晰/颗粒度恰当"这种与学生无关的抽象标签,必须显式 cite 学生 chat/简历说过的某条事实,否则学生答完仍然不知道"我哪里被看穿了"

底层判断:**这个学生在嘉实真实一面会过、二面被首席凉的概率约 60%**,我们当前的 mock interview 给她打 76 分基本是"对应届筛简历的口径"友善了 — SAIF 想要的"到位反馈"还差至少一层:**让系统在 chat 阶段就主动 probe conviction、把"你 own 过的反 mentor 观点"作为强制 anchor 写进 memory,再灌进 interview**。这条链路打通之前,strong scenario 的差异化反馈跟 mid 没有本质区别。

---

**文件:** `/home/chuanbo/projects/JobRadar/docs/eval-full-loop-reports/touyan_strong_2026_05_19/reviewer4_chain_consistency.md`
