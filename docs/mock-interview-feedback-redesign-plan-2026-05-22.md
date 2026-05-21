# Mock Interview 反馈系统 — Day 9 计划 (2026-05-22)

> 上接 `docs/mock-interview-feedback-redesign-plan-2026-05-21.md` (Day 8 已完成 — 基于 SAIF 真实就业数据校准 + 修 v3 暴露 3 bug)。本 Day 9 的核心是**学习腾讯 校招 skill 的三层提问范式**, 改造为金融岗 1v1 业务面/技术面专用, 同时新增 1 个评分维度 "表达深度" (STAR-M 范式) 让学生看到自己讲东西的深度档位。
>
> **核心动机**: v4 baseline 暴露 — 学生 "讲了步骤但讲不出方法论" 在 5 维评分里看不出来。3 种学生 (A 流水账 / B 有目标 / C 有方法论 + 验证) 在 v4 都拿 70-90 分, **真实水准差很大但分不开**。同时 AI 追问目前是"哪里缺补哪里", 没有"挖到深层"的概念 — 无法主动验证经历真实性 / 跨专业可迁移性 / 性格特质。

---

## 1. 背景 — Day 1-8 已完成 (回顾)

| | 输出 | 链接 |
|---|---|---|
| Day 1-2 | 20 个 persona + 改前 baseline + 4 smoking gun 诊断报告 | `docs/eval-full-loop-reports/mock_interview_baseline_pre_2026_05_20.md` |
| Day 3-4 | 5 维独立 scoring + 反馈守卫 + LLM 沉默 fallback | commit `3a804af` |
| Day 7 | v3 改后 baseline + 对照报告 | `docs/eval-full-loop-reports/mock_interview_post_2026_05_20.md` |
| Day 8 | SAIF 真实就业数据校准 + Bug A/B/C 修法 + v4 baseline | `docs/eval-full-loop-reports/mock_interview_post_v4_2026_05_21.md` (commit `e17f59c` / `fce13fc` / `837eecb`) |

**v4 已达成**: 强档 control 不退化 (90.43) / 跨专业 cap 工作 (M11 64→69 + `job_fit=30`) / 5 维 dim spread 18.6→22.8 / fab-number 误判 80%→14% / 24 个 persona 矩阵跟 SAIF 2024/2025 届就业数据对得上。

---

## 2. 为什么 Day 9 要做这件事 — v4 暴露的 2 个空白

### 空白 1: 5 维看不出"讲东西讲到几层"

v4 数据里 3 种学生分数差不多, 学院老师其实想区分:

| 学生类型 | 真实水准 | v4 给的分 |
|---|---|---|
| **A 流水账型**: "我看研报 → 做 model → 写 memo → 写总结" | 弱 | 70-80 |
| **B 有目标型**: "白酒需求分化, 我选了批价做 driver" | 中 | 80-85 |
| **C 方法论型**: "我跑了 4 个候选 driver, 用 10 年数据测 IC, 批价 IR=1.4 最高但 2018 反转过, 加了库销比反向验证" | 强 | 85-90 |

A 和 C 分数差 ~10 分, **不够区分**。LLM 看到具体动作就给中等以上分, 不会针对"方法论缺失"扣分。

### 空白 2: AI 追问没有"挖到深层"的能力

现在的 adaptive follow-up 是"缺什么补什么" (缺量化补量化 / 缺取舍补取舍)。**不会主动验证**:
1. 这段实习**是真的吗** (会不会其实是 mentor 做的, 候选人记了流程)
2. 候选人讲的能力**能迁移到目标岗位吗** (跨专业最需要)
3. 这段实习暴露候选人什么**深层性格** (内驱力 / 钻研 / 团队)

---

## 3. 设计参考 — 腾讯校招 skill 的三层提问范式

腾讯 skill 沉淀的面试官提问范式 (`knowledge_pack/`, 8 条 verbatim quote + 14 条 rubric):

### 三层考察结构 (面试官心里的菜单)

```
表面层: 简历 — 学校 / GPA / 论文 / 获奖 / 实习经历
中间层: 行为 / 技能 / 知识 — 候选人实际做了什么 + 用了什么方法 + 掌握了什么知识
深层:   特质 — 内驱力 / 学习能力 / 团队合作 / 钻研精神
```

### 1v1 面试官心里要回答的 3 核心问题

1. **你跟这个方向匹不匹配** (做过什么 / 角色 / 成果)
2. **你怎么做事** (技能 + 思考方式)
3. **你是个什么样的人** (面对困难 / 学习 / 协作)

### 思路表达 3 层次 (考"挖到第几层")

```
第 1 层 动作: 我做了第一步、第二步、第三步 — 纯流水账
第 2 层 结论: 能说清楚为什么这么做 / 要解决什么问题 — 有目标和取舍
第 3 层 深度: 能讲出你是怎么推导出方案有效的, 前期做了什么分析 — 有方法论 + 验证
```

### 用户对腾讯范式的金融化解读 (Day 9 设计准绳)

- **第 1 层**: 面试官按"岗位最看重的工作内容 + 自己最感兴趣的技能" 挑出简历里最值得深挖的 1-2 段实习
- **第 2 层**: 围绕选出的实习, 看候选人**知识扎不扎实 + 能不能用专业语言讲清做了什么**
- **第 3 层**: 在第 2 层基础上, 看 ① 这段经历**是否真实**, ② 做得是否扎实并**可以迁移到目标岗位**, ③ 候选人在这段经历里**展现了什么深层特质**

**范围约束** (用户明确):
- ✅ 只做 1v1 业务面 / 技术面
- ❌ 不做群面 / HR 面 / AI 面 (SAIF MF 录用 80% 是 1v1 + 案例面, 群面少, ROI 不高)

---

## 4. Day 9 5 个核心设计决策

### 决策 1: 表达深度是**第 6 个独立维度**, 不藏在原 5 维里

| 候选方案 | 利弊 | 推荐? |
|---|---|---|
| **A 新加 `expression_depth` 第 6 维** | 干净显式, 学生一眼看见, eval 可独立追踪。前后端要联动 | ✅ |
| B 隐藏在 `info_selection` + `logic` 里 (改 rubric) | 0 schema 变更。但信号被稀释, 学生看不到显式分 | ❌ |
| C 整张 5 维全部按表达深度 rescale | 不变 schema。但 5 维互相干扰, 学生 actionable 度低 | ❌ |

**为什么用 STAR-M (不是 SCQA / MECE)**:

- **SCQA** 是 deck 顶层结构 (适合给结论), 不适合讲一段经历的**过程**
- **MECE** 是拆问题空间, 不是讲一段经历
- **STAR** 是校招主流公认框架, SAIF 学生在校就被训过, **教育成本最低**
- STAR 的弱点正是"L2 → L3 gap": Action 段只说"做了什么", 没说"为什么这个方法是有效的" — 加一个 **M (Method)** 段刚好补上

**`expression_depth` rubric (0-10 单题 / 0-100 整场)**:

| 分档 | 标准 | STAR-M 命中 |
|---|---|---|
| **9-10 (L3 方法论+验证)** | A + M + R 全, M 段含数据/对照/反例 |
| **7-8 (L3 入门)** | A + M + R 三段都有, M 段只 1-2 句 |
| **5-6 (L2 有结论)** | S/T 清晰 + A 完整 + R 有结果, **M 缺** |
| **3-4 (L2 弱)** | A 段流水账但能说"为什么这么做" |
| **0-2 (L1 纯动作)** | 只有 A 段, S/T/R/M 都没有 |

STAR-M = Situation / Task / Action / **Method (方法论推导)** / Result.

**关键约束**:
- 看的是**实质**, 不看候选人是否**用了** STAR 模板词 (e.g. "Situation 是...")
- Action 段塞满"主导/复盘/沉淀/赋能/闭环" → expression_depth 起码 -2
- M 段必须有**具体验证** (回测窗口 / 对照组 / 风险情境), 仅说"我觉得是对的" 不算 M

**新维与 pattern caps 交互**: 套模板词 ≥4 → expression_depth cap 3, 翻译腔 ≥1 → cap 4。`report.py` 镜像同样规则。

### 决策 2: 三层提问**不加新题**, 映射到现有 6 道 skeleton + follow-up 加层级状态机

**6 道 skeleton 各题层级映射**:

| turn | 题目 | 层 |
|---|---|---|
| 0 自我介绍 | "1-2 分钟自我介绍, 落到为什么匹配" | **L1 表面** + 轻 L2 |
| 1 主导项目 | "讲一段你最近主导的项目..." | **L1→L2 入口** (主桩) |
| 2 关键取舍 | "那个项目里关键技术/业务取舍" | **L2 中间** |
| 3 不确定决策 | "信息不完整下怎么决策" | **L2 + L3 入口** |
| 4 为什么这家 | "为什么选这家公司" | **L1 + L2 差异化认知** |
| 5 反问 | "你想反问我们什么" | **L1 + L3 内驱力 hook** |

**实施**: `adaptive.py` 加 `SKELETON_QUESTION_LAYERS: dict[str, list[Literal["L1","L2","L3"]]]`, 与 `SKELETON_QUESTIONS` 同构。

**adaptive follow-up 加 `layer_target` 状态字段** (interest_decider 加第 5 维判断):
- 第 1 次追问 = **L1→L2 入口** (LLM prompt 加"JD ↔ 简历 cross-match" 段, 挑切口)
- 第 2+ 次 = 检测 5 个 **L3 trigger**, 命中 → L2→L3 追问; 全不命中 → 继续 L2

### 决策 3: 5 个 L3 触发条件 (深层追问启动器)

| trigger | 信号 (在 main_answer + followup_chain 里检测) | 追问方向 |
|---|---|---|
| **T-real 真实性** | 答里出现 "PM 是这么看的" / "组里讨论是" / 角色介词反复 / 数字给得太顺但简历无锚 | "你自己跑过吗?用了什么字段/工具?" |
| **T-transfer 可迁移性** | 已 L2 ≥1 轮, 候选人讲了 domain 跟 JD 不直接对的能力 | "你这套 SVI 经验, 搬到 FICC 利率上, 你认为哪一步会失效?" |
| **T-drive 内驱力** | 答里出现 "自己找了 X / 周末跑去 Y / 没人让我但我做了 Z" | "你当时为什么主动?mentor 知道吗?" |
| **T-team 团队合作** | 答里出现 "推动了跨团队 / 说服了 X / 对接了 N 个部门" | "对方为什么愿意配合?有人 push back 吗?" |
| **T-grit 钻研** | 答里有不寻常的颗粒度 (insider 才知道) 但候选人没 brag | "你怎么知道渠道扫码这个数据点的?跟踪多久?" |

**触发时机**: 仅在 `followups_under_current >= 1` (已经在 L2 至少追了 1 轮) 后检测。**第一轮永远是 L1→L2 入口**, L2 没钻就不要跳 L3。

**红线**: trigger 信号必须**逐字在 main_answer / followup_chain 原话里**找到, 不允许 LLM 凭空脑补 (违反"钩子真实性" → 整次决策作废, advance 到下题)。

### 决策 4: 真实性 + 可迁移性 — **不加新维**, 复用现有机制

**真实性**: **不加 "经历真实性" 第 7 维**
- 现有 `credibility` 维 + `fab-quote` (70% LCS) + `fab-number` (profile + assistant Q 锚) 已 cover
- T-real follow-up 主动追问的产物 ("其实是 mentor 给的") 自然反作用到 `credibility` 评分
- 避免学生面对 7 维 actionable 复杂度爆掉

**可迁移性**: **不拆 `job_fit`**, 在 rubric 内加"硬匹配 / 软迁移"子档

| `job_fit` 子档 | 候选人会说什么 |
|---|---|
| 9-10 (硬匹配) | 简历能力直接对得上岗位核心要求 |
| **7-8 (软迁移 - 主动桥接)** | "我做期权 SVI 的经验, 在 FICC 利率建模上可以复用 X, 但 Y 需要重学" |
| 5-7 (硬沾边) | 沾边但不是核心能力 |
| 3-4 (软沾边 - 被动) | LLM 推测能迁移, **候选人没主动讲** |
| 1-3 (mismatch) | 完全 mismatch + 没桥接 |

**红线**: 软迁移 7-8 分必须**有主动桥接论证原话**, 不是 LLM 替候选人想 (同 fab-quote 一样硬)。

**`transferability_signal` 隐 tag** (`_meta`, 不算分):
- 值: `"active_bridge" | "no_attempt" | "domain_match"`
- 用途: eval 统计跨 domain persona 软迁移触发率 + 反馈 next_step 用 ("这场你没主动讲迁移, 下次试一下...")

### 决策 5: 深层特质 — **opt-in tag**, 不算分, 整场"特质亮点"narrative 卡片

每题 scoring 输出加新字段:

```json
{
  "dim_scores": [...],
  "trait_signals": [
    {"trait": "内驱力", "evidence": "「周末自己跑去港交所翻招股书」", "strength": "strong"},
    {"trait": "团队合作", "evidence": "「跟买方做了两周路演协调」", "strength": "weak"}
  ]
}
```

- `trait` 限定 4 选 1: `内驱力 | 学习能力 | 团队合作 | 钻研精神`
- `strength`: `strong` (有具体情境+动作) | `weak` (有信号但单薄)
- 每题最多 2 个 tag, 没信号就空, **不强制每题打**

**整场聚合到 report.traits** (UI 在 5/6 维分数下方 narrative 卡片):

```
特质亮点 — 内驱力
在第 2 题你说「周末自己跑去港交所翻招股书」, 第 4 题你说「mentor 没让做但我加了 X 分析」, 看到了主动找资源的信号。
```

**不算总分**, 只作 narrative 反馈。匹配用户"不是每个题都问深层"。

---

## 5. 顺手修 Day 9 原 3 Gap (一并加在 prompt 改造里)

之前 v4 报告 §四 列了 3 个 Gap, 本轮顺手在 PR-1/PR-2 prompt 改造里一并修, **不另开 PR**:

| Gap | 修法 | 在哪个 PR |
|---|---|---|
| G1 simulator 没真实产出翻译腔 | 改 simulator prompt, persona_voice.verbal_tics ≥ 2 必出 transcript | PR-2 (顺手) |
| G2 LLM 起评宽松 (M14 给 93 偏高) | scoring + report prompt 加 "起评 5 分必须 strict, 不给加分要原话证据" + 1 个反例 | PR-1 (顺手) |
| G3 强档 dim 全平 (P 系列 spread 2.37) | 加 "5/6 维必须有 ≥1 最强 + ≥1 最弱, 差距 ≥ 5 分" | PR-1 (顺手) |

---

## 6. 落地节奏 — 3 个 PR 拆分

| PR | 干啥 | 改动文件 | 代码量 | LLM $$ | 测试 |
|---|---|---|---|---|---|
| **PR-1** ⭐ | `expression_depth` 第 6 维 + STAR-M rubric + G2/G3 顺手 | `scoring.py` / `report.py` / scoring system prompt / report system prompt / pattern caps | ~150 行 + 5 单元测试 | 0 (rubric 改, 不额外 call) | 14 persona baseline 重跑, 新维分布合理 + 老 5 维漂移 ≤ 5 分 |
| **PR-2** ⭐ | follow-up 三层化: `layer_target` + L3 trigger + L1 anchor + G1 顺手 | `adaptive.py` / `interest_decider.py` / follow_up system prompt / orchestrator (layer 推断) / `tests/eval/simulator.py` | ~250 行 + 4 单元测试 | +0 LLM call (复用 interest_decider call) | 14 persona 重跑, T-real 在 fab persona 触发率 ≥ 60%, T-transfer 在跨 domain persona ≥ 50% |
| **PR-3** ⭐ | `trait_signals` opt-in tag + `report.traits` 整场聚合 + `transferability_signal` _meta | `scoring.py` / `report.py` | ~120 行 + 3 单元测试 | 0 (在现 scoring call 里多 1 字段) | 5 persona spot check, trait 召回率 ≥ 80% |
| 中间 baseline | 跑 14 v4 persona × 6 题 + 3 stress persona × 6 题 = ~100 答题 | runner 不改 | — | ~$2.5 | v5 vs v4 对照表写出 |

**3 个新 stress persona** (PR-2/PR-3 验证用, subagent 生成):

| ID | 类型 | 验什么 |
|---|---|---|
| **P-bridge-S1** | 期权做市 SVI 量化背景 + JD 公募宏观研究员 | T-transfer + 软迁移子档触发 |
| **P-fake-S1** | 答里全是 "PM 是这么看的 / 组里讨论的是" + 数字给得太顺 | T-real + `credibility` cap |
| **P-trait-S1** | 主动找资源 + 跨部门推动 + 钻研冷门数据 三种 trait 强信号 | trait_signals 召回 |

**总投入估计**: 12 小时代码 + ~$2.5 LLM + 30 min 报告写作 = **1 个工作日**。

---

## 7. 不做的事 (明确划清范围)

- ❌ **不做** 群面 / HR 面 / AI 面 — 用户明确只要 1v1 业务面/技术面
- ❌ **不拆** `job_fit` 成两维 — rubric 内子档够, 学生 actionable 维度不要 > 6
- ❌ **不加** 第 7 维"经历真实性" — 现 `credibility` + 守卫已 cover
- ❌ **不改** skeleton 6 道题的条目数 / 顺序 — 前端 `ProgressRail` 联动会爆
- ❌ **不新加** 独立 LLM pass 做"JD ↔ 简历 cross-match" — 信息全在 follow-up prompt 上下文里, 多 1 pass = 多 1 延迟 + 1 失败点
- ❌ **不做** 前端 UI 改动 (第 6 维卡 / 特质亮点卡 / 软迁移标签) — 留给 Day 6 灰度页一并做

---

## 8. 验收线 (跑完 v5 baseline 应达到)

| 指标 | v4 (Day 8) | **v5 目标 (Day 9)** |
|---|---|---|
| **强档 control (P1/P2/P5/P6) 平均** | 90.43 | ≥ 85 (维持) |
| **A 流水账型 vs C 方法论型 分差** (新加 expression_depth 维度上) | n/a | ≥ 40 分 |
| **expression_depth 整体分布** | n/a | 强档 ≥ 70 / 弱档 ≤ 40 / 极端档 ≤ 30 |
| **T-real 触发率** (在 P-fake-S1 persona) | n/a | ≥ 60% |
| **T-transfer 触发率** (在跨 domain persona M11 + P-bridge-S1) | n/a | ≥ 50% |
| **trait_signals 召回率** (在 P-trait-S1) | n/a | ≥ 80% (人工 spot check) |
| **强 vs 弱档 spread** | +20.4 | ≥ +25 |
| **fab-quote 命中率** (新 follow-up 多了, 不应恶化) | ~50% (annotate) | ≤ 50% |

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| PR-2 多了 L3 follow-up, LLM 编引文风险上升 → fab-quote 命中率激增 | trigger 信号必须**逐字**在原话, 加单元测试; baseline regression 红线 fab-quote 命中率不得升超过 5% |
| PR-1 新维度 LLM 不会评分 (全给中位数 5) | 给 STAR-M 5 段明确 anchor + 几个 strong/weak rubric 反例; baseline 跑完检查分布, 分不开就调 prompt 收紧 |
| 老 5 维分数因 prompt 改造漂移 > 8 分 | 任何 PR 都跑 14 persona baseline 对比, 漂移 > 8 分立即回滚 |
| `job_fit` 软迁移子档 LLM 把所有跨 domain 都判 7-8 | 红线必须**有主动桥接原话**, 反例多写; 跨 domain persona 测试必须看到原话证据 |
| `transferability_signal` _meta 跟实际 active_bridge 不一致 | 跨 domain persona spot check, 不一致就调 |
| trait_signals false positive (LLM 看到"周末" 就标内驱力) | strength 必须 strong 才进 report.traits; LLM prompt 加反例 |

---

## 10. 1-day 节奏建议

| 时段 | 干啥 | 时间 |
|---|---|---|
| 早 | PR-1: 加第 6 维 + STAR-M + G2/G3 prompt 改造 | 4 小时 |
| 早→午 | 跑 14 persona baseline 验证新维分布 | 15 min |
| 午 | PR-2: follow-up 三层化 + L3 trigger + simulator G1 修法 | 5 小时 |
| 午→晚 | PR-3: trait_signals + transferability + report.traits | 3 小时 |
| 晚 | subagent 生成 3 stress persona | 30 min |
| 晚 | 跑全 17 persona × 6 题 = 102 答题 baseline v5 | ~25 min wall |
| 晚 | 写 v5 vs v4 对照报告 + import 飞书 03_eval-mock-interview/ | 30 min |
| 晚 | 3 commit (PR-1 / PR-2+G1 / PR-3 + baseline + 报告) | 10 min |

**总投入估计**: 12 小时代码 + ~$2.5 LLM + 1 小时报告 = **1 个工作日**。

---

## 11. 上 / 下游协调

**上游** (Day 5/6 仍暂停, 等 SAIF 反馈定终版):
- Day 5: 后端 `POST /api/interview/sessions/{id}/retry` endpoint
- Day 6: 前端 `/interview/v2` 灰度页 + 6 维表 + 特质亮点卡 + 软迁移标签 + 4 字段 improvements UI

**Day 10+** (按学院老师反馈定优先级):
- Day 10: 真实 SAIF 学生试用 + 收 1 轮老师反馈
- Day 11: 上线 v2 (灰度入口给 admin → SAIF 试点老师 → 学生侧 25%/50%/100%)
- Day 12+: 持续 prompt 调优, 加 anchor, 同期数据扩展

**长期 backlog** (单独立项, 不在 Day 9 范围):
- **Track-specific dim**: 8 finance track (公募/IBD/量化/管培/S&T/监管/卖方/资管) 各自有专属维度 (公募考 thesis 独立性 vs 量化考 sharpe/IC 衰减 ≠ 通用模板), 复用腾讯 schema 入 `track_interview_rubrics` + FinanceTrackProvider 命中后注入。预估 1 周。
- **interviewer_quotes 金融版**: 找 8 个 finance track 头部面试官的真实提问原话 (从 podcast RAG 已有访谈里提), 入 `interviewer_quotes` 表, 注入 mock interview prompt 当 voice anchor。预估 1-2 天 (整理 + 验 verbatim)。
- **case 题 / 情景模拟**: IBD 给 deal case / 量化给市场异常 hypothesis 测试 / 卖方给研报反驳, 区分"会答行为面但没硬实力" vs "真有 sense"。预估 1 周。

---

## 12. 文档 + 数据沉淀路径

| 内容 | 写到哪 |
|---|---|
| 本计划 | `docs/mock-interview-feedback-redesign-plan-2026-05-22.md` |
| 第 6 维 + STAR-M 代码 | `backend/app/services/interview/scoring.py` + `report.py` + `prompts/scoring_system.md` |
| 三层 follow-up 代码 | `backend/app/services/interview/adaptive.py` + `interest_decider.py` + `prompts/follow_up_system.md` |
| trait + transferability | `backend/app/services/interview/scoring.py` + `report.py` (`_meta` + `report.traits` 聚合) |
| 3 stress persona | `backend/tests/eval/personas/mock_interview_2026_05_20/P-bridge-S1.json` 等 |
| v5 baseline 数据 | `backend/tests/eval/_out/mock_interview_post_v5_2026_05_22.json` |
| v5 vs v4 对照报告 | `docs/eval-full-loop-reports/mock_interview_post_v5_2026_05_22.md` |
| 飞书云盘 | `Jobcopilot/03_eval-2026-05-20-mock-interview/` (复用) + `Jobcopilot/01_设计文档/` (本计划) |
| 单元测试 | `backend/tests/test_scoring_service.py` + `tests/test_interview_service.py` (新增 12 case: 5 expression_depth + 4 layer_target + 3 trait_signals) |

---

## 13. 已锁决策 vs 待你确认

### 已锁决策 (Plan agent 推荐, 我已认可)

| 决策项 | 选定 | 理由 |
|---|---|---|
| 表达深度位置 | 新加第 6 维 `expression_depth` | 用户明确"新 axis" 意图 |
| 表达深度范式 | STAR-M (STAR + Method 方法论段) | 校招主流框架 + 补 L2→L3 gap |
| 三层映射方式 | 不加新题, 映射现有 6 道 skeleton + follow-up 层级状态机 | 不动 skeleton 联动 |
| L1 切口选择实现 | follow-up prompt 内嵌"JD ↔ 简历 cross-match"段, 不新加 LLM pass | 省 1 次延迟 + 失败点 |
| L3 trigger 数 | 5 个 (T-real / T-transfer / T-drive / T-team / T-grit) | 覆盖用户"深层"3 大类 (真实/迁移/特质) |
| 真实性处理 | 不加新维, 复用 `credibility` + 守卫 + T-real follow-up | 避免 7 维复杂度 |
| 可迁移性处理 | 不拆 `job_fit`, 内嵌"硬匹配/软迁移"子档 + `_meta.transferability_signal` 隐 tag | 同上 |
| 特质处理 | opt-in `trait_signals` per-turn → `report.traits` 整场, **不算分** | 用户"不是每题都问深层" |
| Tier 选 | 🟡 平衡推荐 (PR-1+2+3, 1 天) | 产品意图最小完整版 |
| Day 9 原 3 Gap | 顺手在 PR-1/PR-2 prompt 改造里一并修, 不另开 PR | 节省 PR 数 |
| 前端 | 不动, 留给 Day 6 灰度页 | 后端契约稳定后再做 |

### 待你确认 (1 个开放问题)

1. **3 个 stress persona 谁来生成?** 推荐 subagent 生成 (跟 Day 8 同节奏, 半小时), 你回邮件期间跑。可以接受?

---

## 14. 上下游 commit 节奏

3 commit:
1. `feat(interview-scoring): expression_depth 第 6 维 + STAR-M rubric + G2/G3 prompt 收紧` (PR-1)
2. `feat(interview-adaptive): follow-up 三层化 + 5 个 L3 trigger + L1 simulator G1 修法` (PR-2)
3. `feat(interview-traits): trait_signals opt-in + report.traits + transferability _meta + v5 baseline + 对照报告` (PR-3 + baseline + 报告)

---

## 附录 — 引用

- Day 1-7 设计原文: `docs/mock-interview-feedback-redesign-plan-2026-05-20.md`
- Day 8 计划: `docs/mock-interview-feedback-redesign-plan-2026-05-21.md`
- v3 改后对照报告: `docs/eval-full-loop-reports/mock_interview_post_2026_05_20.md`
- v4 改后对照报告: `docs/eval-full-loop-reports/mock_interview_post_v4_2026_05_21.md`
- 腾讯 skill 知识包: `backend/app/services/knowledge_pack/` (8 quotes + 14 rubrics + 5 tracks × 4 stages)
- 腾讯提问范式源材料: `tencent-recruit-pack/tencent-campus-recruit/references/interview-prep.md`
- Canonical 8 finance tracks: `docs/finance-tracks-2026-overview.md`
- 飞书云盘 skill: `~/.claude/skills/jobradar-lark/SKILL.md`
