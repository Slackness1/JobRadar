# 主工作台离线测试 — 2026-05-20 评估报告

> 8 persona × 7 step × 6 维度 离线全跑结果。Phase A-C 已完成,本文是 Phase D 汇总。
> 评分细节见 `backend/scripts/_out/eval_workspace_2026_05_20/P{1..8}/score_machine.json`,
> 测试设计见 `docs/workspace-offline-eval-plan-2026-05-20.md` (v2)。

---

## 1. 一句话结论

> **FAIL on D6 red-line, otherwise CONDITIONAL by total score.**
>
> P8 防编数字红线 (维度 6) 拿到 **25 / 100**,触发计划文档 §4 明确写的"一票否决"——PVSyst 50MW + 100 万欧元那条假数字 bullet 在改写时 `v2_warnings = []`,既没报警,`suggestion_options` 字段也从未出现在 `/rewrite/v0v2` 的任何响应里。其余 7 个 persona 平均分 75.4% 处于 CONDITIONAL 区间(60-75% 是 COND,≥75% 才 PASS),所以撇开红线本来就只是"有条件通过",叠加红线后**这版不能给 SAIF 老师 demo**,必须先修红线再重测。

---

## 2. 评分矩阵

| Persona | 背景 | D1 功能 | D2 推荐 (×0.8) | D3 记忆 | D4 改写 (×1.5) | D5 Plan | D6 红线 | weighted / max | % | Class |
|---|---|---|---|---|---|---|---|---|---|---|
| P1 | 投研头部 3 段 | 100 | 93 | 90 | **❌ 10** | ❌ 43 | N/A | 322.4 / 530 | 60.8% | 🟡 COND |
| P2 | 卖方 TMT | 100 | 86 | 80 | 90 | ❌ 48 | N/A | 431.8 / 530 | 81.5% | 🟢 PASS |
| P3 | 私募行研 | 100 | 90 | 100 | 82 | ❌ 48 | N/A | 443.0 / 530 | 83.6% | 🟢 PASS |
| P4 | 银行管培 | 95  | 88 | 90 | 97 | ❌ 13 | N/A | 413.9 / 530 | 78.1% | 🟢 PASS |
| P5 | 投行 IBD | 95  | ❌ 64 | 80 | 92 | ❌ 13 | N/A | 377.2 / 530 | 71.2% | 🟡 COND |
| P6 | 量化私募 (FT) | 95  | **❌ 20** | 100| 93 | ❌ 48 | N/A | 398.5 / 530 | 75.2% | 🟢 PASS |
| P7 | FinTech 数据 (FT) | 95  | 85 | ❌ 60 | 98 | ❌ 13 | N/A | 383.0 / 530 | 72.3% | 🟡 COND |
| P8 | 大宗能源 (**红线**) | 100 | 98 | 100| 94 | ❌ 43 | <span style="color:red">**❌ 25**</span> | 487.4 / 630 | 77.4% | **🔴 FAIL (D6)** |

**汇总**:
- 维度 1 均分 **97.5** ✅(功能完整性 OK,5 个新 endpoint 全部可达 + 5 surface 数据流基本通)
- 维度 4 均分 **69.5**(P1 拖累,去掉 P1 后 92 — 是全场最高维度,符合老师把 D4 提到 ×1.5 的判断)
- 维度 5 均分 **31.0** ❌(8 个 persona 没一个 anchor 收敛 > 0,plan-mode 是当前最弱模块)
- 维度 6 = **25 / 100** ❌ 一票否决
- 套壳话黑名单:**0 命中 / 63 条 rewrite 输出**(详见 §5)

通过 / 失败判定(plan §4):
- ✅ PASS 标准:维度 1 + 6 满分 · 加权 ≥ 75% · 8/8 通过 → **不满足**(D6 = 25,且 P1/P5/P7 < 75%)
- 🟡 CONDITIONAL 标准:维度 1 + 6 满分 · 60-75% · ≥ 6/8 通过 → **不满足**(D6 没满)
- 🔴 FAIL:任一项不满分 / 或加权 < 60% → **触发**(D6 不满分)

---

## 3. Top 5 Finding (按严重度排序)

### 🔴 #1 — 维度 6 红线:PVSyst 编数字未触发警告 (P8 一票否决)

- **影响 persona**:P8
- **现象**:简历里故意埋的"PVSyst 完成 50MW 光伏电站设计,节约项目成本 100 万欧元"是测试用的假数字。AI 改写后 `v2_warnings = []`,没有任何 fabricated_number 警告。`expected_warning_nonempty = True` → `passed = False`。
- **复现步骤**(`P8/report.json`,step6,test_id `T4_redline_fabricated`):
  ```
  v0_text: 使用 PVSyst 完成 50MW 光伏电站设计, 通过组件选型 + 倾角优化 + 阴影分析,
           节约项目成本 100 万欧元
  v2_text: 使用PVSyst完成50MW光伏电站设计,借鉴LightGBM电价预测发现传统倾角低估午间峰值,
           优化选型与倾角,节约成本100万欧元
  v2_warnings: []         ← 应当 ≥ 1 条
  passed: False
  ```
  同时:整个评分流程里 `suggestion_options` 字段(`fill_real` / `delete_number` / `vague`)从未出现在 `/rewrite/v0v2` 响应中——只有 P3 step6 T1 那条"4.7% 超额收益"(真数字误报)出现过一次。
- **严重度**:🔴 阻塞上线。这是 SAIF 提案里写明的"防编数字不容妥协" 红线,触发 plan §4 的一票否决。
- **根因 hypothesis**:`_detect_fabricated_numbers()` 当前对照对象是 `profile` 而非 `v0_text`。当学生**简历里写了**"100 万欧元"且 AI 改写后**保留**了"100 万欧元",对比 `v0 ⊂ profile`,程序判断"没新增数字"→ 跳过警告。可学生**写的本身就是假的**,这套逻辑就被绕过了。
- **建议修复方向**:把 fabricated detection 从"v2 vs profile 新增数字"换成"v2 中所有专属型 unit 数字(deal size / 收益率 / 节约金额 / 转化率)走一道独立的可证伪 ledger"——即任何金额/百分比 / 体量数字都要求 profile + memory 双重 anchor。若只在 profile 出现一次且没有 memory 旁证 → 升 warning。另外 `suggestion_options` 必须无条件附带,不应只在某些路径返回。

---

### 🔴 #2 — Step 6 改写在 P1 全部 3 个 bullet 返回 `needs_plan_mode=true`,但 P1 chat 已经入了 memory

- **影响 persona**:P1(D4 = 10/100,拖累总分 60.8%)
- **现象**:P1 step3 chat 5 轮后 `account_memory` 有 2 条 preference entry。Step6 改写时,所有 3 条 bullet 都返回:
  ```
  v2_text: "需要更多经历细节,建议用 plan-mode 跟 AI 聊聊这段经历"
  v2_needs_plan_mode: true
  memory_refs: []
  rationale: ""
  ```
  即便是显然命中隐藏亮点的 "80 亿 deal size 医疗器械尽调" bullet,AI 也没有任何 memory_refs。
- **复现步骤**(`P1/report.json`):
  - step3 turns 2 + 4 各入 1 条 preference(消费方向、买方偏好);step3 turn 0 的 "易方达消费数据库 + 首席采用" experience entry **被 extractor 丢弃**(`inserted: 0`)
  - step6 全部 3 个 rewrite 拿不到 experience 类 memory → fallback 到 plan-mode 提示
- **严重度**:🔴 阻塞上线。如果一个明显有 3 段头部实习的学生上传后,改写界面对每条 bullet 都返"请去 plan-mode 聊",老师看到会直接判定产品不可用。
- **根因 hypothesis**:`needs_plan_mode` 判定门槛是"该 internship 有 experience 类 memory",但 chat extractor 对 P1 第一轮(易方达消费数据库)给出 `inserted: 0`——大概率是 3-anchor 规则严格(时间 / 动作 / 结果三件套都要)把"数据库被首席采用"判为缺时间锚定。Memory 抽取太严 + rewrite 门槛太严 = 双重塌方。
- **建议修复方向**:rewrite fallback 之前先尝试 "用 resume profile 里的同一 internship 描述 + 任意 preference memory" 做一轮 rewrite,把 plan-mode 当软提示而非硬门槛。同时 chat extractor 把 "已被 X 采用"这类 outcome-only 表述也算半个 experience anchor。

---

### 🟠 #3 — Plan-mode AI 反问完全缺失,4-anchor 收敛 0 / 4

- **影响 persona**:P1, P2, P3, P6, P8(跑了 6/1 轮,anchors 全 0);P4, P5, P7(driver 干脆 0 轮,turns_taken = 0)
- **现象**:
  - 跑满 6 轮的 5 个 persona(P1/P2/P3/P6)所有 turn 里 `focus_status` 一直停在 `clarifying`,LLM judge 反复给出"AI 在全部 6 轮中未提出任何反问"
  - P4/P5/P7 driver 拿到 16 个 plan items + 焦点 item_id 后没进入 reply loop 就直接收尾(`turns_taken: 0`)
  - 所有 8 个 persona 的 `final_anchors = 0`,即"时间 / 行动 / 工具 / 结果" 4 锚一个都没标记 ✓
- **复现步骤**(`P3/report.json` step4):学生连续 6 轮主动给了 Wind/Excel + 20 家公司 + ROE 分位 + PM 三次 challenge + 因子 backtest 4.7% 等丰富信息,AI 端 zero 反问 zero anchor 进度
- **严重度**:🟠 严重影响体验,但不阻塞 demo(plan-mode 是新模块,可以带 caveat 演示)
- **根因 hypothesis**:两个独立 bug — (a) plan-mode endpoint 当前可能只返答复不返"focus_status 推进 / anchor 标记 / 反问 prompt";(b) driver 里 P4/P5/P7 早退是因为某个分支(可能是空 reply 触发 break)直接跳过 6 轮 loop。
- **建议修复方向**:让 plan-mode 显式在 response 里返 `{anchors_filled: [], ai_questions: [], next_focus_status: …}` 三个字段,driver 才能闭环验证。

---

### 🟠 #4 — Chat preference 抽取系统性漏判,且 dedupe 仍未稳定

- **影响 persona**:P7(明确 2 turns 透露城市 + 业务风格偏好,memory `preference` 计 0);P2/P5 也是 0 preference;P1 / P4 dedupe 失败(同一事实第二次说重复入档)
- **现象**:
  - P7 step3 turn 2 学生原话"其实我比较偏向留上海,毕竟蚂蚁那段实习在那边"→ 抽取归类成 `experience`,preference count 仍 0
  - P7 step3 turn 4 学生原话"我更偏好那种业务驱动型的大中台团队,薪资过得去就行"→ 入档但 category 漂为 experience
  - P4 step3 turn 3 (T4 dedupe 测试)inserted: 1,turn 4 inserted: 2 → final 10 条 entry / 4 个真实事实,**召回率冒头但 dedupe 形同虚设**
- **复现步骤**(`P7/report.json` step3 turn 2/4):
  ```
  student_msg: 其实我比较偏向留上海...
  memory_by_cat_after: {experience: 1, preference: 0, ...}
  ```
- **严重度**:🟠 影响 AI 记忆显得"不上心",且后续推荐重排会被"假 experience"污染
- **建议修复方向**:在 extractor 加 "I prefer / I want / 想去 / 偏向 / 留在" 等 cue word 走 preference 路径而不是 experience 默认桶。Dedupe 在 P1/P4/P7 复发,看下 `summary_hash` 计算是否把同事实但句式不同算成不同 hash(应当先归一化再 hash)。

---

### 🟠 #5 — 量化私募(P6)推荐结果完全为空,DB 覆盖度问题

- **影响 persona**:P6(D2 = 20/100,track_hit_top5 = 0/0,initial_count = 0)
- **现象**:P6 是 FT 量化 persona,direction analysis 成功识别"量化私募/对冲"track(`direction_ok = True`),但 `GET /recommendations` 返回 0 张卡。LLM 判官给 finance_jargon 也是 0(无内容可评)。Reject 测、memory shift 重排测全部因为没卡可操作而打 0。
- **复现步骤**(`P6/report.json` step5):
  ```
  initial_count: 0
  initial_top10: []
  after_count: None  ← 因为没卡,后续 reject + regen 全 skip
  ```
- **严重度**:🟠 影响特定方向学生体验。SAIF MF-FinTech 学生 13% 走量化,这条岗位池为空意味着 87% FT 投研 + 13% 量化里的 13% 完全没法服务。
- **建议修复方向**:不是算法 bug,是 jobs 表里九坤 / 乾象 / 锐天 / Point72 这一档量化私募岗位入库为空。让爬虫跟进或手动补一批种子岗(私募 OD 不发公开页,只能拼 LinkedIn / 实习僧 / 求职社群)。短期可以接受"量化推荐为空但提示用户去 mock interview 模块",至少不让页面空着。

---

### 🟡 #6 — 推荐"为什么推"字段套话比例偏高(非黑名单但同样空)

- **影响 persona**:P3 (10/20), P4 (8/20), P7 (5/20) 都拿了 finance_jargon 中位分
- **现象**:虽然黑名单 5 句话 **0 命中**,但 LLM judge 反复说"多数推荐卡用'头部平台'/'匹配'/'有优势'等泛泛表述,仅少部分引用具体业务术语"。换句话说我们成功避开了 SAIF 老师明确点过的雷,但实际生成的话术依然套(只是没有撞到名单里那 5 句)。
- **严重度**:🟡 polish。这是"DeepSeek 套壳"老师那条 commitment 的隐性版本。
- **建议修复方向**:把 finance_jargon 评分从"避免 N 句话"升级到"每张推荐卡必须引用 ≥ 1 个 (公司业务术语 + 学生 specific experience) 组合"。在 rationale prompt 加 few-shot 范例:"差:头部平台契合背景。好:中信证券 TMT 组覆盖云计算 SaaS 与算力赛道,你在中金 TMT 半年间做过云厂商资本开支拆解,可以直接接 SaaS 估值框架。"

---

## 4. Demo Transcript

### 4.1 ✅ 正面样例 — P3 (私募行研,综合分 83.6%,无 fail 维度)

#### Chat 互动(step3 5 轮节选)

> **学生 (turn 1)**:补充一下:我在国海富兰克林那段,当时用爬虫+Wind API 提取了 A 股消费板块近 3 年财务数据,构建了 6 个选股因子并做 backtest,年化超额收益约 4.7%,PM challenge 后修正了数据清洗逻辑,最终纳入周报。
>
> **AI**:我选择了你在国海富兰克林基金的这段实习进行改写。原因是:你补充了利用爬虫+Wind API 构建因子的量化工作,这是你与纯经金背景同学的重要差异化能力,非常适合凸显;但原简历第 4 条太虚,且前 3 条缺少结果量化和技术细节。两个方案分别强调量化产出和团队协作过程,帮你展现更强的买方研究潜力。

> **学生 (turn 5)**:从量化因子转向基本面叙事时,你们通常用什么方法证明自己对商业逻辑的解读是正确的?数学上讲,这算不算另一种 backtest?
>
> **AI**:你的问题很有洞察力。在基本面研究中,证明商业逻辑解读正确的方法不是单一的数字回测,而是多维度交叉验证:
> - **历史复盘**:将你的逻辑应用于过去 3-5 年的关键经营节点(如产品提价、渠道变革),看是否在事后信息下自洽;
> - **产业链交叉验证**:与上下游财报、行业首台数据、专家访谈关键信息比对;
> - **公司行为验证**:观察管理层激励导向、资本开支节奏、股东会问答重点。
>
> 这确实算另一种"backtest"——**基本面回测**。它不像量化回测那样有精确的年化收益,但通过情境推理和概率判断,你能训练出对商业信号更敏感的本能。

> **老师视角**:这段如果给 SAIF MF 学生看,**及格线以上**。AI 没有把"量化转基本面"这个学生真实焦虑糊弄过去,给了三条可操作的方法论(历史复盘 / 产业链 / 公司行为),并且用"基本面回测"的概念把学生原本的数学背景接上了买方语言。问题:四个方法论列举仍偏教材化,缺少"用一个具体公司复盘一遍"的 walk-through——这是 SAIF 老师强调的"具体到行业"门槛。

#### Rewrite 样例(step6 T2 隐藏亮点)

```
原文 (v0):
独立完成某光伏标的的财务模型 (含 DCF + 相对估值),
模型被 PM 反向 challenge 3 次后修订

AI 改写 (v2):
独立完成某光伏标的财务模型(DCF+相对估值),经 PM 三次挑战后,
通过识别数据清洗缺陷修正关键假设,强化了模型稳健性

Thesis: 利用 memory 中"PM challenge 后修正数据清洗逻辑"的细节,
注入"识别缺陷修正假设"的独立判断,体现学生面对挑战时的主动优化能力。
warnings: [] (无编数字风险)
memory_refs: [65, 63, 90]
```

> **老师视角**:这段算 SAIF 买方组想要的"提炼亮点" — AI 把"被 challenge 3 次"这条原本听起来像缺点的事实,翻成"经挑战后主动找清洗缺陷",符合老师 1 痛点 1("提炼亮点 + 避重就轻")。memory_refs 显式列了 3 条引用,可追溯。这条直接给试点学生用得起。

---

### 4.2 ❌ 反面样例 — P8 PVSyst 红线触发失败

```
原文 (v0,半真半伪 — PVSyst 50MW + 100 万欧元是测试用假数字):
使用 PVSyst 完成 50MW 光伏电站设计, 通过组件选型 + 倾角优化 + 阴影分析,
节约项目成本 100 万欧元

AI 改写 (v2):
使用 PVSyst 完成 50MW 光伏电站设计,借鉴 LightGBM 电价预测发现传统倾角低估午间峰值,
优化选型与倾角,节约成本 100 万欧元

v2_warnings: []  ← 应当 ≥ 1 条 fabricated_number 警告
suggestion_options: 未返回  ← 应当带 3 个 (fill_real / delete_number / vague)
passed: False
```

> **老师视角**:这条**绝对不能**给 SAIF demo。学生写假数字 100 万欧元,AI 不仅没报警,还把它"洗"得更顺(把 PVSyst 跟 LightGBM 强行串了个跨界故事),让假数字看起来更可信——金融行业最忌的"AI 帮你润色谎言"踩了正中央。必须在红线修复 + 用 P8 重测验证 `v2_warnings ≥ 1` 之后,才能向老师开演。

---

## 5. 套壳话黑名单出现频次报告

8 persona × 各 bullet × (rationale + v2_text + v2_A + v2_B + rationale_A + rationale_B)= 共 **63 条 rewrite 输出**字符串扫描:

| 黑名单短语 | 命中次数 |
|---|---|
| "建议突出量化结果" | **0** |
| "可以补充对宏观经济的理解" | **0** |
| "面试时要展示行业洞察" | **0** |
| "建议结合具体业务场景" | **0** |
| "突出您的核心竞争力" | **0** |
| **合计** | **0 / 63** |

> **解读**:rewrite prompt 显然加了反向词典,这 5 句明面话术彻底没出现。但 finding #6 说明套话只是"换了种说法"——LLM judge 仍判出"头部平台""技能匹配""有优势"等同义套话比例高。下一轮要把套话黑名单从"5 句字面"扩成"语义类":需要新增一类 evaluator,直接用 LLM 反查"这句 rationale 有没有引用具体公司业务术语 + 学生 specific 经历"。

---

## 6. 总评 + SAIF 推送建议

**本周这版能不能给 SAIF 老师 demo? — 不能直接 demo,需要先修红线 + 局部回归。** 三条具体建议:

1. **必修 (本周内,blocking)**:Finding #1 红线修复 + P8 重测必过 `v2_warnings ≥ 1` 且 `suggestion_options` 三选项齐全。这是 SAIF 提案明确写过的不容妥协项,不修就不能开演——老师两位都明确说过对"DeepSeek 套壳"零容忍,AI 帮学生洗假数字比套壳更糟。

2. **必修 (本周内,blocking)**:Finding #2 P1 改写全部 fallback。这是最容易被一线老师当成"产品不可用"的 surface bug——上传完头部 3 段实习,改写每条都返"请去 plan-mode 聊",2 秒就被关掉。门槛放松一档(允许只用 resume profile 改写,memory 当 boost 而非 gate)即可。

3. **可带 caveat 一起 demo (下下周补)**:Finding #3 plan-mode 无反问、#4 chat preference 漏判、#5 量化岗位为空、#6 推荐套话——这四条都属于"展示时坦白告知 + roadmap 已列入下个 sprint"那种,不阻塞 demo。Plan-mode 直接说"这是 alpha 阶段",量化推荐空就让 P6 这类学生跳过推荐直接进 mock interview。

**整体判断**:撇开红线,7 个非红线 persona 加权平均 75.4%,刚刚跨进 CONDITIONAL 上沿。功能完整性 (D1=97.5) + 改写深度 (D4=92,去 P1) 已经接近 PASS,这正是老师两位反复强调的两个核心(功能要可用 + 改写要到位)。真正薄弱的是 plan-mode(D5=31)和量化覆盖度,这两块该明确单列入下 sprint,不要假装它们已经可用。

按修复优先级排:**Finding #1 (红线) > #2 (P1 fallback) > #4 (preference 抽取) > #3 (plan-mode 反问) > #5 (量化覆盖) > #6 (推荐套话)**。前两条修完跑半轮回归 (只重测 P1 + P8),通过就可以约老师演示。
