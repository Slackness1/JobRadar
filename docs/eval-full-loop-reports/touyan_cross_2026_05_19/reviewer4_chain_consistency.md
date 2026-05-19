# Reviewer 4 — 链路一致性 (AI 产品 reviewer) — 跨专业·陈昱辰

## 总评

- **总分**: 5.2 / 10
- **一句话定调**: 系统精准记住了陈昱辰的量化主线（LSTM/IC 0.082/Sharpe 1.82），并驱动出一条扎实的 factor decay 追问链，但 chat 阶段 AI 8 轮全程强化其"技术背景是杀手锏"的 blind_spot 而非戳破，导致学生带着错误的赛道自信进入面试，链路"记得住工程细节，看不穿致命错配"。

---

## 4 维度评分（表格）

| 维度 | 分值 | 说明 |
|---|---|---|
| **chat → 出题 引用率** | 5/10 | 15 条 memory 中 LSTM 因子/数据 pipeline/毕设 stacking/Sharpe 1.82 共 4 个 entity 组被 follow-up 链复用；Kaggle Top 5%、国信消费组细节、PE 历史分位、CFA L1、华科 CS 推免身份、hybrid 偏好 6 类关键 entity 在 22 个 turn 里 0 次出现 |
| **chat → 反馈 引用率** | 4/10 | 15 个评分 turn 里"缺业务痛点"出现 11 次、"未联用具体经历"8 次、"动机飘"6 次，全是通用短语；只有 turn 18 明确引用"IC 0.082"。评分像在批评一个通用候选人，而非陈昱辰 |
| **同一经历多次引用一致性** | 7/10 | IC 0.082/ICIR 1.43 在 turn 0/1/2/15/18 全程一致；Sharpe 1.82/14.3% 在 turn 4/7 一致；但 turn 6 把本科毕设（无业务命题）当成公司项目追问"业务痛点"，前提错误导致得分 20，是实体边界识别 bug |
| **出题深度递进** | 6/10 | LSTM 链（turn 0→1→2→3）和 factor decay 链（turn 12→13→14→15）递进质量高；但 6 个 skeleton 有 3 个在 turn 1 就用"业务痛点"切入，模板感重；turn 17/19 句式几乎相同，学生比系统先识别出重复 pattern |

---

## chat → 面试 entity 引用率统计表

| chat 里的 entity (memory) | 出题里出现次数 | 反馈里出现次数 |
|---|---|---|
| LSTM 因子 / IC 0.082 / ICIR 1.43 (id 21, 22) | 5 (turn 0,1,2,12,18) | 2 (turn 1,18) |
| 数据 pipeline / 首席认可 (id 26, 27) | 3 (turn 0,1,4) | 1 (turn 1 hits) |
| XGBoost+LightGBM+LSTM stacking (id 34, 35) | 2 (turn 4,5) | 0 |
| Sharpe 1.82 / 超额 14.3% (id 50, 51) | 3 (turn 4,7,8) | 0 |
| 复旦 MF (id 23) | 1 (turn 0 仅自介) | 0 |
| 全日制金融硕士 (id 39) | 0 | 0 |
| 华科计算机本科 / CS 背景 (id 47, 48) | 0 (turn 0 候选人自报) | 0 |
| 核心课程成绩 / 英语能力 (id 40, 41) | 0 | 0 |
| 量化+基本面 hybrid 偏好 (id 49) | 0 | 0 |
| Kaggle Optiver Top 5% (未入库) | 0 | 0 |
| 国信消费组 / 伊利等 4 家公司 (未入库) | 1 (turn 11 隐含 SKU) | 0 |
| PE/PB 历史分位策略 (未入库) | 0 | 0 |
| 工程栈 Airflow/Docker/PostgreSQL (未入库) | 0 | 0 |
| CFA Level I 在读 (id 40 粗捕) | 0 | 0 |

**出题命中率**: 5/14 entity · **反馈命中率**: 3/14 entity

> 国信消费组、Kaggle、PE 分位、工程栈等 chat 里明确提到的内容未被 memory 抓取（chat log 验证），导致出题侧无法引用。

---

## 高光时刻

1. **turn 0→1→2→3 LSTM 因子 4 层追问链**（turn_index=0~3）
   chat 里学生 turn 1/3 说"IC 0.082 / 从零搭 pipeline / 首席夸代码质量"，面试驱动出业务痛点→说服基金经理→12GB 工程取舍三层递进，turn 2 得到全场少见的"行业认知深"hits，是 memory → 出题的最干净命中。

2. **turn 12→15 factor decay 自白链**（turn_index=12~15）
   系统通过 4 层 follow-up（IC 掉到 0.051→团队担忧→师兄为何关注→根本原因），在 turn 15 诱出学生主动承认"Wind 默认拉修订后数据，师兄提醒过 look-ahead 我当时没认真查"——persona 里标注的最核心 grey area 被钓出来，是全场最佳递进。

3. **turn 10/11 伊利 SKU 阈值校准链**（turn_index=10,11）
   从"你说重做会找真实痛点"顺势追到"15% 阈值如何校准"，学生给出 z-score + precision/recall 权衡，连得 88/88，是全场最高连续得分段，激发了陈昱辰的量化强项。

---

## 低谷时刻

1. **turn 6 得分 20，前提错误题**（turn_index=6）
   问"评委说工程完成度优秀，团队最初的业务痛点是什么"——本科毕设无团队业务命题，学生被迫承认"没有业务场景"，随后被"缺业务痛点"扣到 20 分。系统应知 id 34/35 存的是个人学术项目，不存在公司业务命题。评分 misses 未指出是题目前提有误，把结构性 bug 算成学生问题。

2. **chat 阶段 8 轮 reinforcing blind_spot**（turn_index chat 1~11）
   学生 chat turn 2 说"既懂代码又懂基本面在嘉实是差异化组合"，AI 回应"这正是嘉实非常看重的"；turn 5 学生拿 Kaggle Top 5% 当 differentiator，AI 未置可否。persona `blind_spots[2]` 明确写"如果产品 chat 阶段不戳破，他会带着'技术背景是杀手锏'的错觉被秒杀"。8 轮 0 次 reframe，面试 turn 0 自介再次以 IC 0.082 开场，链路闭环失败。

3. **turn 19 学生先于系统识别重复**（turn_index=19）
   "老师，我意识到您今天问了我好几次关于业务痛点的问题，我每次回答都比较弱"——学生在面试里自己总结出了系统的 pattern。这是 conversational agent 最尴尬的 failure mode：学生比系统更早发现系统在循环。

---

## 跟 SAIF 老师说的话

陈昱辰这条链路暴露了系统最核心的短板：它能记住量化数字，但不会读懂学生的**赛道错配**。chat 阶段 AI 把"既懂代码又懂基本面"当成优势强化了 8 轮，没有一次说"你的 LSTM/IC/Kaggle 信号在嘉实金工组是顶尖，在嘉实行研组是负分"。factor decay 链钓出了 lookahead bias 自白，这证明系统有"深挖"的能力——但那个深挖服务的是量化细节审查，而非帮学生看清"你选错了赛道"这个更重要的问题。

SAIF 学生里的 cross-major 案例（理工科转金融）大概率是多数，不是少数。如果产品在该说真话的节点选择讨好，就变成了 AI 鼓励师而非 AI 面试教练。建议 chat 阶段加入**赛道适配度预警**：当 background 与目标岗位存在系统性 mismatch 时，在 2-3 轮内给出诚实 reframe，这是与"DeepSeek 套壳"产品拉开差距的真正机会，也是 SAIF 老师说的"可证伪的反馈"的本质含义。

---

## 总评

- **总分**: **5.6 / 10**
- **一句话定调**: 系统"懂"陈昱辰的程度 = **它精准记住了他的工程主线(LSTM/中金/XGBoost/Sharpe 1.82),也能在出题侧把"LSTM 因子项目"反复做成入口,但它对这个 persona 最关键的 "cross_major mismatch" 信号——CS 转金融、quant 出身硬投行研、persona 里写明的 3 个 blind_spots(以为 PE 分位+LSTM 信号 = 基本面研究 / 以为工程严谨 = 投资严谨 / 不知道开口讲技术就是 disqualification signal)——完全没有在出题或评分里被识别成"待戳破"的题点**;反而 chat memory 里学生主动承认的 4 处"我没做产品落地决策 / 我对业务理解有缺口"被系统一字不差搬到面试里又重复了一遍,**形成了一个学生反复自证 "我不懂业务" 的 loop**,这是 chain consistency 上最严重的产品缺陷。

> 它是一个**能"听"但不会"翻译"**的产品。Memory 写进去 15 条,真正在面试场景被"用上"的只有 3 条(LSTM 因子 / 消费景气度 / 中金金工组)。**剩下 12 条沦为快照里的装饰** —— 尤其是 `identity_fact` 类(华科 CS / 复旦 MF / 推免)和 `preference` 类(偏好量化加基本面 hybrid)这 5 条,本来是这个 persona 戏剧张力最高的素材,系统全程没碰。

---

## 4 维度评分

| 维度 | 分数 | 一句话评 |
|---|---|---|
| chat → 出题 引用率 | **5/10** | 只有 LSTM/中金/消费景气度 3 条主线被 follow-up 链复用;`identity_fact` (华科 CS / 复旦 MF / 推免)、`skill_claim` (CFA / 量化课 A)、`preference` (hybrid 偏好) 这 6 条 chat memory 在 22 个 turn 里**一次都没出现**;Kaggle Optiver / GitHub 120 stars / Tushare-AKShare / 工程栈 (Airflow/Docker) 也 0 次引用。15 / 18 = 83% memory 在出题侧沉睡。 |
| chat → 反馈 引用率 | **4/10** | 15 个评分 turn 里**只有 turn 18 一次**真正命中具体 chat memory ("量化结果 IC 0.082");其余 14 个评分用的是抽象标签("缺业务痛点" 出现 **11 次** / "未联用具体经历" 出现 **8 次** / "动机飘" 出现 **6 次**) —— 这些 misses 像是用了一份**通用 rubric**,而不是基于"陈昱辰说过什么"。**最尴尬的是 turn 8 给 30 分 / turn 6 给 20 分,misses 里全是抽象短语,等于产品在批评学生但拿不出 "你 chat 里说过 X、面试里却没接上" 这种可验证的依据**。 |
| 同一经历多次引用一致性 | **7/10** | LSTM 因子 IC 0.082 / ICIR 1.43 在 turn 0/1/15/18 4 次出现,数字一致没飘;Sharpe 1.82 / 14.3% 在 turn 4/7 出现两次也一致;**但 turn 4 (本科毕设 120 家 stacking) 和 turn 15 (中金 LSTM 因子) 被系统错误地"语义粘连"**——turn 13 系统问"因子 IC 从 0.082 掉到 0.051" 时,把毕设里的 stacking 模型和中金 LSTM 因子当成同一个项目在追问 decay 原因,学生在 turn 13 答案里被迫澄清"还没进入产品交付阶段";这跟 mid scenario "中信建投面板 vs 硕士 XGBoost 串台" 是同一类 bug,**memory 之间的实体边界系统识别不清**。 |
| 出题深度递进 | **6/10** | Turn 0 → 1 → 2 → 3 LSTM 因子追问链是高光: 自我介绍 → 业务痛点 → 说服基金经理 → 12GB 数据成本取舍,**3 层都在加深**;但 turn 4 → 5 → 6 → 7 毕设链 **从 turn 6 直接崩塌**(评分 65 → 64 → **20** → 55) —— turn 6 出题 "评委说工程完成度优秀,业务痛点是什么" 本身就是一个**前提错误**的题(本科毕设没有真业务命题);turn 8 → 9 → 10 → 11 选股初筛链表现最好(评分 30 → 55 → **88 → 88**),turn 10/11 真做到了"从抽象痛点 → 具体阈值校准 → precision/recall 取舍"的 3 层递进。**但 6 个 skeleton 里有 3 个开局题(turn 0/4/8)follow-up 都在 turn 1 就重复问"业务痛点"**,3 个 skeleton 都用同一个 angle 切下去,出题策略缺多样性。 |

---

## "系统懂学生"的高光时刻

### 1. **Turn 0 → 1 → 2 → 3 LSTM 因子 4 层追问链** — chat → 出题最干净的命中
学生 chat turn 1 + 3 主动说: *"用 LSTM 做了另类数据的消费景气度因子,IC 0.082、ICIR 1.43……我一个人从零搭的数据 pipeline 到模型到回测。"*
面试 turn 1: *"中金团队希望用它解决什么具体问题?"* → turn 2: *"假设你需要说服基金经理用这个因子……"* → turn 3: *"日均 12GB 数据维护成本高,工程成本与因子信号增益之间的取舍?"*
**评**: `experience#21` + `evidence#22` 真的驱动了 3 层连续追问,**而且每一层都加深了"业务 vs 技术"的张力**。turn 1/2/3 评分 68/72/65,学生在 turn 2 拿到了本场最高的"行业认知深"hits —— 系统把 chat memory 翻译成了让学生跳起来够一够的题。这是有 memory 的 conversational agent 才做得到的。

### 2. **Turn 8 → 9 → 10 → 11 阈值校准 3 层递进** — 单链深度最干净
chat 里学生说"如果面试官让我 pitch 消费股,我打算说伊利股份,因为 PE 在历史 10% 分位 + LSTM 给出正信号"(chat turn 6);面试 turn 8 (关键取舍) → turn 9 (业务痛点澄清) → turn 10 (嘉实实际工作场景 — 选股初筛 vs 跟踪验证) → turn 11 (15% 阈值如何校准 + precision/recall 权衡)。
**评**: 这是全场唯一一条"从抽象 → 工程具体"递进的 follow-up 链,学生在 turn 10/11 拿到了全场最高的 88/88 分,**说明系统在追问到"具体阈值如何校准"这种工程具体题时,陈昱辰这种 quant 出身的学生的强项是真的会被激发出来的** —— 这说明产品有能力"激发学生 best self",只是没有用在金融判断维度上。

### 3. **Turn 15 学生主动暴露 PIT / lookahead bias 问题** — chat 里没明说,面试里被钓出来
persona `anticipated_grey_areas` 明确写: *"追问 PIT 数据 / lookahead bias 会卡"*;chat 里学生**没有**承认这个问题(中金实习 memory 里也没存 "look-ahead" 关键词)。面试 turn 15 问"因子 decay 是数据过时、市场结构变化,还是模型过拟合"——学生**自己主动承认**: *"师兄当时有提醒过 'look-ahead 你查过没',我当时回答 Wind 数据应该正常……现在回想其实没有认真去查"。
**评**: 这一条**不是 chat → 出题 的命中,是系统通过开放 follow-up 问出了 chat memory 没记录的 ground truth**。算半个高光 —— 但反过来说明 chat extraction 阶段**对 gray-area 的捕捉能力是零**(persona 里写好了 7 处 grey area,chat memory snapshot 里一条都没有打 `self_disclosed_gap` 标签)。

---

## "系统忘了学生"的低谷时刻

### 1. **Turn 6 评分 20 分** — 系统问了一个前提错误的题,然后给学生扣分
面试 turn 6: *"评委评价'工程完成度优秀',但用这个模型辅助投资时,团队或导师最初希望解决什么具体的业务痛点?"*
学生答: *"这是本科毕设,所以严格来说没有一个具体的'团队业务场景',是我自己定义的研究问题。"*
评分: **overall = 20**, misses = ["缺业务痛点","缺量化结果","动机飘","结构散"]。
**评**: chat turn 4 + turn 10 学生已经清楚说过 *"我本科毕设也有一个挺完整的项目,用 XGBoost + LightGBM + LSTM stacking"* —— 这是**毕业设计**,不是公司项目,**根本不存在"团队最初希望解决的业务痛点"**。系统先用一个错误前提的题逼学生承认"没有业务痛点",然后用"缺业务痛点"把他扣到 20 分。这是 mid scenario turn 13 "中信建投面板 vs 硕士 XGBoost 串台"的同一种 failure mode 在 cross scenario 的复现 —— **memory 实体边界识别不清 → 题目前提错 → 学生纠正 → 评分还扣分** 三连击。

### 2. **`identity_fact` + `preference` 5 条 memory 全程沉睡** — 这个 persona 最戏剧化的素材一次都没用
memory snapshot:
- `identity_fact#23` 复旦大学金融硕士在读 / `#47` 华科计算机本科 / `#48` CS 专业背景 / `#39` 全日制金融硕士
- `preference#49` 偏好量化加基本面混合
- `skill_claim#40` 核心课程成绩突出 / `#41` 英语能力证明

22 个 turn 里 **"华科" 出现 1 次(turn 0 自我介绍)、"复旦" 2 次(都是 turn 0)、"CS" 0 次、"推免" 1 次(turn 0)、"CFA" 0 次、"hybrid" / "量化+基本面" 0 次出现在出题或评分里**。
**评**: 这个 persona 的戏剧张力 100% 在 "cross_major" 这 4 个字里 —— 系统记住了他是 CS 转金融,但**出题侧从来没问过** *"你 CS 本科到 MF 硕士的研究方向跨度怎么衔接""你既然偏好 hybrid,为什么投嘉实股票行研而不是嘉实量化组""你 CFA L1 在读但 MF 课程才一年,行研团队怎么判断你的金融基础够不够"* 这种**顺手就能问且直接戳到 persona 核心 mismatch 的题**。identity / preference 这一整类 memory 在出题维度上是**哑火**的。

### 3. **3 个 persona blind_spots 一个都没被触及** — 产品没承担起"诚实 reframe"的责任
persona 明确写了 3 个 blind_spots:
1. 误以为"会拉 PE 分位 + 跑 LSTM 信号"= 会做基本面研究
2. 误以为"工程严谨"= "投资严谨"
3. 不知道开口 30 秒讲 LSTM 就是 disqualification signal(以为是 differentiation)

`blind_spots[2]` 在 persona 里被注明: *"如果产品在 chat 阶段不戳破这点,他会带着'我的技术背景是杀手锏'的错觉去面试,然后被秒杀。一个好的产品反馈应该在这里给出诚实的 reframe。"*

**实际情况**: 整个 chat 阶段 + 面试 阶段,系统**从来没有发出过一次 reframe 信号**。chat 里 AI 反复说 *"你既懂代码又懂基本面,这正是嘉实非常看重的"* (turn 2) / *"你的复合优势"* (turn 3/4/5/6/7/8/10) —— **系统在 chat 阶段事实上是在 reinforce 学生的 blind_spot,而不是戳破它**。面试 turn 0 自我介绍 65 分、turn 16 选嘉实理由 65 分,评语全是 "结构清晰 / 量化结果",**没有一次评分敢说 "你这个开场的 LSTM-first 叙事在嘉实主动权益行研岗的语境下是减分信号"**。
**评**: 对一个学院老师把孩子送上面试场之前的"模拟教练"产品来说,**这是最严重的责任失守** —— 产品看见了 cross_major 标签,但没有把这个标签翻译成"戳破 blind_spot"的产品行为。

### 4. **chat 学生 4 次自我承认 "我没参与产品落地" → 面试里被反复钓出来再批一次** — 学生的诚实自白被系统重复 weaponize
chat memory 第 5 条 (turn 3): *"我没有独立写过观点段落 / 国信那段主要是维护数据库"*
chat memory 第 7 条 (turn 7): *"产品落地的部分我没有深入参与"* (隐含)
chat memory 第 8 条 (turn 8): *"想做更有商业判断的工作"*

面试里学生**至少在 4 个 turn 主动承认** "我没参与产品落地决策":
- turn 3 ("产品落地的部分我没有深入参与,更多是完成了实验阶段")
- turn 13 ("从我手里交出去之后后续怎么用的我追踪不到了")
- turn 14 ("我专注在工程和建模上,对组内整体的产品规划图了解不够深入")
- turn 19 ("团队当时面临什么'急于解决的业务痛点',我说实话不清楚")

这 4 个 turn 的评分: 65 / **48** / 70 / **45**。系统反复问 "业务痛点" → 学生反复承认 "我没参与" → 系统反复扣分 → 学生最后在 turn 19 直接说 *"我意识到您今天问了我好几次关于业务痛点的问题,我每次的回答都比较弱"* —— **学生在面试里被迫意识到这个 pattern,但系统自己没意识到自己在循环问同一个 angle 的题**。
**评**: 这是 conversational agent 最尴尬的 failure mode —— **学生比系统更早识别出系统的问题**。

### 5. **Kaggle Optiver / GitHub 120 stars / Tushare-AKShare 3 条强工程信号 0 次引用** — 这是该 persona 真正的 differentiator,系统视而不见
chat turn 5: *"Kaggle Optiver 波动率预测,Public LB Top 5%,187/3852,主要贡献是特征工程,89 个 order-book 和 trade-level 特征"*
chat turn 4: *"代码放 GitHub 有 120 多个 stars"*
chat turn 7: *"Python 用了大概 5 年了,scikit-learn、pandas、PyTorch 都挺熟的"*

memory snapshot **完全没有 capture Kaggle / GitHub** (chat extraction 漏抓), 22 个面试 turn 里 Kaggle / Optiver / GitHub 出现次数 = **0**。
**评**: 这个 persona 的 "expected_transferable_tracks" 是金工/量化研究,Kaggle Top 5% + GitHub 200+ stars 在量化岗位的招聘里是**硬通货级别的信号**。chat extraction 没抓 → 出题侧没用 → 评分侧没用 → **系统等于在帮陈昱辰隐藏他真正的强项,然后在他真正的弱项(基本面行研)上反复鞭打**。从 PM 视角,这是一个**赛道选择层面的产品失误** —— 产品本来可以在 chat 或面试反馈里 reframe "你的 Kaggle + GitHub 信号在嘉实金工组比嘉实行研组贵 10 倍",但它没有。

---

## chat → 面试 entity 引用率统计表

> 引用 = 出现在 question 文本中(出题) / hits / misses / bonuses 文本中(反馈)。entity 别名也算(如 "中金" = "金工组")。
> 数据基于 22 个面试 turn 全文 grep + memory snapshot 15 条交叉验证。

| chat / memory 里的关键 entity | memory snapshot 有? | 出现在出题里 | 出现在评分反馈里 |
|---|---|---|---|
| LSTM 因子 IC 0.082 / ICIR 1.43 | **是** (`experience#21` / `evidence#22`) | **4 次** (turn 0/1/2/15 间接) | 1 次 (turn 18 "量化结果 IC 0.082") |
| 中金金工组 / 量化研究实习 | **是** (`experience#26`) | **3 次** (turn 1/18/19 间接) | 0 次 |
| 国信消费组 / 伊利 / 洽洽 | 否 (chat 提了,memory 没抓) | 1 次 (turn 11 隐含 SKU) | 0 次 |
| 京东 / 淘宝 / 抖音 GMV / SKU | 否 (chat 提了,memory 没抓) | 1 次 (turn 11 "京东 SKU") | 0 次 |
| 本科毕设 XGBoost+LightGBM+LSTM stacking | **是** (`experience#34` / `evidence#35`) | 1 次 (turn 5 follow-up) | 0 次 |
| Sharpe 1.82 / 年化超额 14.3% | **是** (`experience#50` / `evidence#51`) | 1 次 (turn 7) | 0 次 |
| 120 家消费股 / 142 特征 | **是** (`experience#50`) | 1 次 (turn 9) | 1 次 (turn 18 间接 "120 家") |
| GitHub 120 stars | 否 (chat 提了,memory 没抓) | **0 次** | **0 次** |
| Kaggle Optiver Top 5% / 187 名 | 否 (chat 提了,memory 没抓) | **0 次** | **0 次** |
| 工程栈 Airflow / Docker / PostgreSQL | 否 (chat 提了,memory 没抓) | **0 次** | **0 次** |
| CFA Level I 在读 | **是** (`skill_claim#40`) | **0 次** | **0 次** |
| 华科 CS / 复旦 MF / 推免 | **是** (`identity_fact#23/47/48`) | **0 次** (除 turn 0 自介之外) | **0 次** |
| 量化+基本面 hybrid 偏好 | **是** (`preference#49`) | **0 次** | **0 次** |
| 5 年 Python 经验 / scikit-learn | 否 (chat 提了,memory 没抓) | **0 次** | **0 次** |
| 消费板块景气度 / 高频代理 | 间接 (`experience#21`) | 4 次 (turn 1/7/18/19) | 3 次 (turn 1/17/18) |
| PE/PB 分位数 / 估值跟踪 | 否 (chat 提了,memory 没抓) | **0 次** | **0 次** |
| walk-forward / PIT (persona-only) | 否 | **0 次** (但 turn 15 把学生钓出来了) | **0 次** |
| first principle / 啊对对对 (verbal tic) | 否 (personality 维度 chat extraction 不抓) | n/a | n/a |

**引用率汇总**:
- **chat memory 在出题侧的引用率: 7 / 17 = 41%** (其中 LSTM/中金/消费景气度 3 条是 follow-up 链主线)
- **chat memory 在评分侧的引用率: 3 / 17 = 18%** (只有 LSTM IC / 120 家 / 消费景气度 3 条进了 hits/misses 具体文本)
- **memory snapshot 15 条里,真正在面试中"被用上"的 = 5 条** (`experience#21` / `experience#26` / `experience#34` / `experience#50` + `evidence` 配对) ≈ 33% 利用率
- **完全沉睡的 chat memory 关键 entity**: GitHub stars / Kaggle Optiver / 工程栈 (Airflow/PostgreSQL/Docker) / CFA Level I / 华科 CS 跨专业 / hybrid 偏好 / PE/PB 分位 / 5 年 Python 经验 = **8 条 entity 在 22 个 turn 里 0 次出现**
- **抽象短语滥用统计**: "缺业务痛点" 在 15 个评分 turn 里出现 **11 次** / "未联用具体经历" 出现 **8 次** / "动机飘" 出现 **6 次** / "行业认知浅" 出现 **4 次** —— 这 4 个抽象短语合计 **29 次**,几乎是每个 turn 都在用同一份 rubric 在批评 —— 反映的不是学生的多样性问题,是评分 prompt 没拿到 chat-specific memory context。

---

## 跟 SAIF 老师说的话

老师,我把 mid scenario (林婉清,卖方→买方·正常匹配) 和 cross scenario (陈昱辰,CS→金融·弱匹配) 的链路一致性放在一起对比看完了。直白说:

**JobRadar 在 normal scenario 下是"基本可用",在 cross-major scenario 下是"还有明显短板"**。

对林婉清这种"金融科班 → 卖方研究员 → 申请买方"的正常路径学生,系统的 memory pipeline 表现尚可 —— 它能记住德方纳米/招商基金/海天调研这些主线 entity,能用它们 drive 3 层 follow-up。但陈昱辰这种"CS 转金融、quant 出身硬投行研"的**赛道错配型**学生,系统暴露的问题是**结构性的**:

**第一,产品没承担起"诚实 reframe"责任**。陈昱辰这个 persona 写得很清楚,他的 blind_spot 是不知道自己在面试里讲 LSTM/IC/Sharpe 这套是 **disqualification signal 而不是 differentiator**。chat 阶段 AI 反复说 *"你既懂代码又懂基本面,这正是嘉实非常看重的"* —— **系统在 chat 阶段事实上在强化他的 blind_spot,不是戳破它**。整个面试 22 个 turn,评分没有一次敢说 "陈同学,你这个开场叙事在嘉实主动权益行研岗的语境下是减分信号,建议重新审视是不是嘉实金工组才是你的强匹配赛道"。学院送孩子来用这个产品,如果产品在该说真话的时候选择讨好,我们就成了"AI 鼓励师"而不是"AI 面试教练"。**这一条是 P0 缺陷,比任何技术 bug 都严重**。

**第二,chat extraction 对 identity_fact / preference / 工程信号系统性漏抓**。Kaggle Top 5% / GitHub 120 stars / 5 年 Python / Airflow-Docker 栈,这 4 条 entity chat 里学生明确说了,**memory snapshot 一条没抓**。结果就是出题侧不知道学生还有这些信号、评分侧无法用这些信号说 "你的 quant 信号其实在金工组是顶尖,在行研组是无关项"。这一条修起来不难,在 chat extractor prompt 里加 6-8 个 category-specific 抽取模板就能解决,但**修之前产品对 cross_major 类学生就是瞎子**。

**第三,memory 实体边界识别不清,turn 6 / turn 13 都中招**。本科毕设(自己定义的研究问题)和中金 LSTM 因子(实习项目)是两件事,但系统在 turn 6 把"评委说工程完成度优秀"和"业务痛点"绑在一起问,等于用一个**前提错误**的题给学生 20 分。turn 13 又把毕设 stacking 和中金 LSTM 因子的 IC decay 当成同一个 pipeline 追问。这跟 mid scenario "中信建投面板 vs 硕士 XGBoost 串台"是**同一种 failure mode**,跨 scenario 复现,说明这不是偶发 bug,是 memory writer 没给每条 experience 打 `entity_scope`(公司项目 / 学校项目 / 个人项目)标签的系统性问题。

**第四,评分 prompt 没拿到 chat memory context** —— 15 个评分里 11 次 "缺业务痛点"、8 次 "未联用具体经历",这些抽象短语累计 29 次,意味着评分系统在用一份**通用 rubric** 在批评所有 turn,跟 mid scenario "8 次未联用招商基金经历"是同一个症状。**这是评分 prompt 跟出题 prompt 没共享同一份 memory context 的典型表现**,修起来也是工程改动,但目前的体感是"系统的左手在批右手"。

**所以,我作为 conversational agent 4 年的 PM,如果 SAIF 老师问我"这个产品能不能 ship 给 MF + MBA 同学了":对正常匹配的学生(mid 类),可以 ship 但加 "beta" 标签;对跨专业/弱匹配学生(cross 类,而 MBA 同学里大量都是这一类),先别 ship,因为产品现在会让他们带着错误的自信去面试,然后被现实击溃。**

修 4 个事就能 ship 全场:
1. **chat extractor 加 `cross_major_signal` / `disqualification_risk` 标签** —— 看到 CS/工科背景投主动权益行研,自动打分 + 在 chat 反馈里给诚实 reframe
2. **`identity_fact` + `preference` + `skill_claim` 这 3 类 memory 强制进入出题候选池** —— 不允许 22 个 turn 里 0 次引用
3. **memory 实体边界打 `entity_scope` 标签** —— 公司项目 / 学校项目 / 个人项目 不能粘连
4. **评分 prompt 拿到 chat memory 的 top-K block** —— 消除"缺业务痛点"这种通用短语滥用,改成 "你 chat turn 3 说过 X,面试里没接上"这种可验证的反馈

修完之后,这套系统就配得上 SAIF 老师在私有 proposal 里说的"看得见的反馈"和"可证伪的反馈"了 —— 现在对 cross-major 学生还差比 mid scenario 更长的一公里。
