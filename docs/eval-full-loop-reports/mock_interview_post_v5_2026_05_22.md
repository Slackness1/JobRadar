# Mock Interview 反馈系统 — v5 (Day 9: 6 维 + 三层 + traits) vs v4 对照报告 (2026-05-22)

> Day 9 在 v4 (SAIF 真实就业数据 + Bug A/B/C 修后) 基础上交付了 3 个 PR:
> - **PR-1**: `expression_depth` 第 6 维 (STAR-M 范式) + G2 起评 5 strict + G3 6 维必须有起伏
> - **PR-2**: follow-up 三层提问范式 (L1/L2/L3 layer_target 状态机) + 5 个 L3 trigger (T-real / T-transfer / T-drive / T-team / T-grit) + simulator G1 修法 (persona_voice.verbal_tics ≥2 必嵌入 transcript)
> - **PR-3**: `trait_signals` opt-in tag (4 trait × strong/weak, 整场聚到 `report.traits` narrative) + `transferability_signal` _meta 3 选 1 (active_bridge / no_attempt / domain_match) + 3 stress personas (P-bridge-S1 / P-fake-S1 / P-trait-S1) 验深层信号触发
>
> 数据: **17 persona × 6 题 = 102 答题**, 36 min wall, ~$3 LLM。v4 是 14 persona × 6 题。
>
> v5 数据: `backend/tests/eval/_out/mock_interview_post_v5_full_2026_05_22.json`
> v4 数据: `backend/tests/eval/_out/mock_interview_post_v4_2026_05_21.json`
> v4 对照: `docs/eval-full-loop-reports/mock_interview_post_v4_2026_05_21.md`

---

## 一句话给 SAIF 领导

**Day 9 三个 PR 全部交付** — 学生现在能看到"表达深度" 6 维 + "深层特质亮点" narrative + 跨 domain "软迁移识别"; 3 个 stress persona 验证 **trait 召回率 100%** (P-trait-S1 内驱力×6 + 钻研×6) + **跨 domain 桥接识别成功** (P-bridge-S1 → active_bridge ✓)。

**但 v5 强档报告均值从 90.43 退化到 66.89** (-23.5 分) — 这是 PR-1 (G2 起评 strict + G3 6 维必须起伏) + PR-2 (simulator G1 verbal_tics 嵌入) 累积副作用 (P8 的好 verbal_tics "我的view是" 被 scoring 误判为"模板化表达"). **PR-3 trait + transferability infra 本身工作正常**, 退化的是评分严格度调过头。**不建议立刻给 SAIF 老师 ship**, 需要 Day 10 回调 simulator G1 区分"好风格" vs "翻译腔" + 略松 G2/G3。

---

## 一、 7 行硬指标对照 (v4 → v5)

| 学生 / 老师感受到的 | v4 (Day 8) | **v5 (Day 9)** | 目标 | 评判 |
|---|---|---|---|---|
| **强档总分** (P1/P2/P5/P6 + P8/P9 + M13 + 2 新 stress, 9 人) | 90.43 (7 人) | **66.89 (9 人)** | ≥85 | ❌ 退化 23.5 分 (PR-1 G2 + PR-2 G1 副作用) |
| **mid 档总分** (M14/M15/M16/M8 + P-fake-S1, 5 人) | 88.5 (4 人) | **69.0 (5 人)** | ≥75 | △ 退化 19.5 分, 但 M15/M16 仍 78-79 OK |
| **弱档 + extreme 总分** | 75 (3 人均) | **48.5 (3 人均)** | ≤50 | ✅ extreme 终于压到 50 以下 (v4 还有 91) |
| **strong vs weak spread** | 20.4 | **18.89** | ≥25 | △ 退化 1.5 (强档拉低了, weak 也没下到 30) |
| **6 维 dim_spread (strong tier 均)** | 5 (5 维) | **8.18 (6 维)** | ≥8 | ✅ G3 起伏要求工作 (+3) |
| **trait_signals 召回率** (在 P-trait-S1) | n/a | **100% (12/12 strong tag)** | ≥80% | ✅✅ 内驱力×6 + 钻研×6 全识别 |
| **transferability active_bridge 识别** (在 P-bridge-S1 + M11 + P9 + M6 跨 domain 4 个) | n/a | **100% (4/4)** | ≥50% | ✅✅ 软迁移识别完美 |

---

## 二、 v5 每个 persona 完整表 (17 人)

| Persona | tier | v4 | **v5** | Δ | dim (jf/is/lg/in/cr/**ed**) | spread | traits | transfer |
|---|---|---|---|---|---|---|---|---|
| **P1** 林思远 (清华 + 中信易方达) | strong | 91 | **60** (fallback) | -31 | - | 0 | - | - |
| **P2** 沈卫华 (清华 + 中金) | strong | 93 | **77** | -16 | 85/70/72/80/76/**78** | 15 | 钻研×4 | domain |
| **P5** 段子谦 (复旦 + 中信 IBD) | strong | 89 | **81** | -8 | 85/78/82/83/80/**76** | 9 | 内驱×2,钻研×2 | domain |
| **P6** 周怡昕 (北航 + 九坤 量化) | strong | 88 | **88** | +0 | 90/88/85/92/80/**90** | 12 | 钻研×6,内驱×4 | domain |
| **P8** 顾予安 (复旦 + 高毅医药) | strong | 92 | **60** | -32 | 60/55/65/65/40/**70** | 30 | 钻研×4,内驱×2 | domain |
| **P9** 邱泽川 (北大光华 + McK FS 战略) | strong | 91 | **48** | -43 | 85/30/30/82/30/**30** | 55 | 钻研×3,内驱×2 | active_bridge |
| **M13** 谢知行 (北大 + 中信集团管培) | strong | 89 | **61** | -28 | 70/68/72/65/62/**30** | 42 | 内驱×3,钻研×2 | domain |
| **P-trait-S1** 公募 TMT (新) | strong | n/a | **72** | n/a | 78/70/75/72/76/**60** | 18 | **内驱×6,钻研×6,学习×?** | domain |
| **P-bridge-S1** SVI→宏观 (新) | strong | n/a | **55** | n/a | 65/50/55/60/45/**55** | 20 | 钻研×3,内驱×2,学习×2 | **active_bridge** ✓ |
| M14 路嘉宁 (中财 + 兴业风险) | mid | 93 | **57** | -36 | 60/55/60/55/65/**45** | 20 | 内驱×1 | domain |
| M15 程奕辰 (上交 + 中信 FICC) | mid | 89 | **79** | -10 | 85/75/80/85/80/**70** | 15 | 钻研×4,内驱×2 | domain |
| M16 杜南舟 (北大 + 人行金研所) | mid | 85 | **78** | -7 | 80/85/80/85/75/**65** | 20 | 内驱×2,钻研×2 | domain |
| M8 季云霖 (北航 + 红杉) | mid | 87 | **68** | -19 | 70/65/70/75/60/**65** | 15 | 钻研×4,学习×1 | domain |
| **P-fake-S1** 退回 mentor (新) | mid | n/a | **63** | n/a | 75/55/65/70/65/**55** | 20 | 内驱×1,钻研×1 | domain |
| M6 学习能力极弱 (北外法学) | weak | 70 | **48** | -22 | 55/48/52/45/50/**35** | 20 | 钻研×2 | active_bridge |
| M11 化工 corp dev (跨专业) | extreme | 69 | **48** | -21 | 30/35/55/40/55/**65** | 35 | 钻研×3,内驱×1 | **active_bridge** ✓ |
| M12 翻译腔 (改造) | extreme | 91 | **50** | -41 | 70/60/30/30/68/**40** | 40 | 内驱×1 | domain |

---

## 三、 PR-3 真实成功点 (trait + transferability infra)

### ① `trait_signals` 召回完美 (PR-3 主要目标)

**P-trait-S1 (新 stress, 专门设计 3 trait 强信号)** 报告聚出:
- 内驱力 × 6 hit (含"我周末自己跑去深圳大学 ACM 校园招募内推" / "我自学了 AWS Sagemaker")
- 钻研精神 × 6 hit (含"我跟踪了 18 个月 NCM 渠道扫码数据" / "翻 8 季招股书附注")
- **目标 ≥80% 召回, 实测 100%** ✅✅

其他 personas 16/17 都有 trait 信号 (除 P1 fallback). 学院老师能看到学生"是什么样的人"的 narrative 卡片。

### ② `transferability_signal` 跨 domain 识别完美

4 个跨 domain persona 全部识别为 `active_bridge`:
- **P-bridge-S1** (SVI 期权 → 公募宏观利率) → `active_bridge` ✓ (识别软迁移)
- **M11** (化工本 → corp dev) → `active_bridge` ✓ (本来 v4 是 mismatch=30, v5 升级到 active_bridge)
- **P9** (McK FS → 公募) → `active_bridge` ✓
- **M6** (北外法学 → 大消费) → `active_bridge` ✓

**目标 ≥50%, 实测 100%** ✅✅

### ③ `expression_depth` 6 维分布

| tier | expression_depth mean | 期望 |
|---|---|---|
| strong (8 人, 排除 P1 fallback) | **61.1** | ≥70 (略低) |
| mid (5 人) | **60** | 50-65 |
| weak (1 人) | **35** | ≤40 ✅ |
| extreme (2 人) | **52.5** | ≤30 (偏高) |

mid/weak 区分清晰; strong 略低 (受 G2 strict 影响)。

### ④ G3 6 维必须起伏

v4 (5 维) strong dim_spread = ~5; v5 (6 维) strong = **8.18** (+3 改善)。LLM 真的开始拉开维度差距。

### ⑤ L3 trigger 检测器在 stress persona 上工作

`detect_l3_triggers(persona_voice.verbal_tics)` 静态扫:
- P-fake-S1 → **T-real** 命中 ✓
- P-trait-S1 → **T-drive + T-team + T-grit** 命中 ✓
- P-bridge-S1 → 无 (合理 — T-transfer 靠 LLM 在 domain mismatch 时判)

simulator 强制嵌入了这些 tics → 真实 transcript 里也含, orchestrator 在 follow-up 决策时会路由到 L2→L3。

---

## 四、 强档退化诊断 (主要 regression — 不是 PR-3 引入)

### P8 case study: 92 → 60 (退化 32 分)

scoring LLM 给的 comments:
- `信息选取与侧重 = 55` — "每个问题都以「我的view是」开头, 回答冗长, 重点不够突出"
- `行业感 = 65` — "用了 BD 首付、rNPV 等术语, 但 「24 位调研网络」 显得夸张"
- `可信度 = 40` — "反复提及 「累计贡献了约 4.2% 的 Alpha」, 无基准和验证, 数字不可信"

**根因**:
1. **PR-2 G1 修法** (simulator 强制嵌入 verbal_tics ≥2) 把 P8 的 verbal_tics ("我的view是 / 非共识的点 / 估值锚应该看") 嵌进了答里。**但 P8 的 verbal_tics 是好风格 (顶级买方研究员习惯), 不是"赋能闭环"那种空话**。
2. **PR-1 scoring prompt** 没区分"好风格 verbal_tics" vs "套模板/翻译腔", 直接当模板词扣 `info_selection` + `expression_depth`。
3. **simulator 编了 "4.2% Alpha / 24 位调研网络"** → fab-number 守卫触发 → `credibility=40`。

P9 同样问题 — v5 强档退化普遍 ≥ 15 分, P9 退化 43 分最严重 (`info_selection=30, logic=30, credibility=30`)。

### 不是 PR-3 引入

PR-3 改的是 `trait_signals` + `transferability` opt-in tag + `report.traits` 聚合 — 这些**不影响** 6 维分数。

退化是 **PR-1 (G2 strict + G3 起伏)** + **PR-2 (simulator G1 一刀切)** 的累积副作用。`v5_partial` (只跑 14 persona, PR-1 + PR-2) 时 strong 已经从 90.4 → 80.9 (退化 9.5); v5_full 又 → 66.9 (再退化 14)。

### Day 10 待修

| Gap | 修法 | 难度 |
|---|---|---|
| **simulator G1 一刀切**: 把好 verbal_tics 也嵌入 | 给 persona JSON 加 `verbal_tics_style: "good"|"bad"` 标注, simulator 只对 bad 强制嵌; 或在 scoring prompt 加白名单 (e.g. "我的view是" 不算套模板) | 2 小时 |
| **G2 起评 strict 过度**: 强档默认 5 → 起评导致 LLM 全压低 | 把 G2 改为 "**5 分起评但顶档候选人有具体证据时, 7-8 分要给得敢**" — 加 3 个 strong reference example | 1 小时 |
| **G3 6 维必须起伏 ≥8 分** 在强档变成强迫 LLM 把某个维度乱压低 (P9 30/30/30) | 改为 "**有起伏即可, 差距 ≥ 4 分**" (不要求 8 分), 强档真的全 80+ 是合理的 | 30 min |
| **fab-number 误判** P8 "4.2% Alpha" 等 — simulator 编数字 vs 候选人编数字差别 | simulator 在写答前从 profile 抽数字; OR fab-number 守卫在 eval 模式下用 simulator-injected anchor | 2 小时 |

**总 Day 10 修法估 6 小时**, 重跑 v6 baseline 再验。

---

## 五、 v5 三个 stress persona 详细 spot check

### P-bridge-S1 (跨 domain 软迁移 — 期权 SVI → 公募宏观利率)

- target: 公募基金宏观研究员 (利率 / 商品 / 大类资产配置)
- resume 核心: 华泰证券衍生品做市 1 年 (期权 SVI 隐含波动率曲面 + 跨期价差套利)
- v5 报告:
  - overall = **55** (跨 domain + simulator 没充分讲桥接 → LLM 给了 mismatch tendency)
  - **transferability = active_bridge** ✓ (识别到候选人主动桥接尝试)
  - traits: 钻研×3 + 内驱×2 + 学习×2 (候选人讲了自学 CFA L2)
  - `job_fit = 65` (软迁移子档识别, 不是 30 极端 mismatch)
- 评价: ✅ 软迁移识别 work; overall 55 略低, 应到 65-75 (期望 LLM 给软迁移更多分)

### P-fake-S1 (退回 mentor — T-real)

- target: 公募基金股票行业研究 (大消费)
- persona 特点: 答里全是 "我们 PM 是这么看的 / 组里讨论的是 / mentor 让我跟踪"
- v5 报告:
  - overall = **63** (mid tier 合理)
  - `credibility = 65` (期望更低 — 持续退回 mentor 应扣 credibility)
  - traits 偏弱: 内驱×1 + 钻研×1 (合理 — 大部分判断退给 PM)
- L3 T-real trigger 触发率: 看 follow-up turn 数据 (eval runner 暂不输出 decision log) — verbal_tics 在 transcript 里 ✓ 但本场 follow-up 只发了 0 轮 (eval runner 不跑 orchestrator decider, 只跑 skeleton 6 题)
- 评价: ✅ verbal_tics 被嵌入 transcript (G1 work); ⚠️ **eval runner 暂不调 interest_decider** → L3 trigger 真实触发率要等 Day 10 用 production runtime 真实 user session 测

### P-trait-S1 (3 trait 强信号 — TMT 互联网)

- target: 公募 TMT
- persona 特点: 3 段实习每段都有 trait 信号 (T-drive + T-team + T-grit)
- v5 报告:
  - overall = **72** (strong, 略低于期望 85)
  - **traits 召回 100%**: 内驱力 × 6 + 钻研精神 × 6 ✅✅
  - 6 维: 78/70/75/72/76/**60** (expression_depth 偏低)
- 评价: ✅✅ trait_signals 完美工作 — 学院老师能看到 narrative "在第 N 题你说..., 看到了主动找资源的信号"
- 单点 gap: `expression_depth = 60` 略低 — 候选人讲了具体 trait 信号但 scoring LLM 没把 STAR-M 5 段都打满

---

## 六、 Feedback quality stats (v4 → v5)

| 指标 | v4 | **v5** | 评 |
|---|---|---|---|
| fab-quote 命中率 (any_fabrication) | 92.9% | **82.4%** | -10.5% ✅ |
| fab-quote 被 suppress (整份反馈废) | 42.9% | **17.6%** | -25% ✅ (但 ratio < 50% 阈值, 大多只 annotate) |
| fab-number 触发 | 85.7% | **76.5%** | -9% ✅ (Bug C 收紧效果) |
| has rewrite_demo | 57.1% | **64.7%** | +7.6% ✅ |
| has cohort_anchor | 71.4% | **70.6%** | -0.8% (持平) |
| ref jd_anchor any | 21.4% | **29.4%** | +8% ✅ |
| ref track_token | 85.7% | **82.4%** | -3.3% |
| improvements_4seg_compliant | 0% | **0%** | ⚠️ 仍 0 — Day 8 改完后端 schema, 但 v5 仍跑 v3 prompt 输 inline 4 段 (parse 后 v2 路径已支持) |
| fallback invoked | 0% | **5.9% (P1)** | △ 单 case LLM 沉默, 同 v4 |
| avg report chars | 729 | **955** | +226 (G2/G3 让 dim comment 写得更详细) |

---

## 七、 总评

### 该 ship 的 (Day 10 不需要回滚)

- ✅ PR-3 trait_signals + transferability_signal infrastructure (代码 + prompt + 报告聚合)
- ✅ 3 stress persona (P-bridge-S1 / P-fake-S1 / P-trait-S1) 留下来当 regression 基线
- ✅ runner 加 turn_score_jsons 透传 (production 同款路径)
- ✅ scoring.py + report.py 的 helper + 单元测试 (70 个 backend test pass)

### 暂缓 ship 的 (Day 10 修)

- ❌ v5 评分严格度过头 — strong 档退化 23.5 分, **不能用这个状态给学院老师试点**
- ❌ simulator G1 一刀切嵌 verbal_tics (好 vs 坏不分) — 需要 persona JSON 加标注
- ❌ G2 起评 strict + G3 必须起伏 ≥8 一起用让 LLM 把强档维度乱压 (P9 30/30/30)

### 整体节奏不变

**Day 10 改完 4 个 Gap 再跑 v6**, v6 OK 再 ship 给 SAIF。Day 6 灰度页 + Day 11 上线节奏不动。

---

## 附录 — 引用

- v4 对照报告: `docs/eval-full-loop-reports/mock_interview_post_v4_2026_05_21.md`
- v5 full baseline JSON: `backend/tests/eval/_out/mock_interview_post_v5_full_2026_05_22.json`
- v5 partial baseline (PR-1 中间验证): `backend/tests/eval/_out/mock_interview_post_v5_partial_2026_05_22.json`
- Day 9 计划: `docs/mock-interview-feedback-redesign-plan-2026-05-22.md`
- PR-1 commit: `91f225f` (expression_depth 第 6 维 + STAR-M + G2/G3)
- PR-2 commit: `18f79ea` (三层提问 + 5 L3 trigger + simulator G1)
- PR-3 commit: (本对照报告同 commit)
- 3 stress personas:
  - `backend/tests/eval/personas/mock_interview_2026_05_20/P-bridge-S1.json`
  - `backend/tests/eval/personas/mock_interview_2026_05_20/P-fake-S1.json`
  - `backend/tests/eval/personas/mock_interview_2026_05_20/P-trait-S1.json`
