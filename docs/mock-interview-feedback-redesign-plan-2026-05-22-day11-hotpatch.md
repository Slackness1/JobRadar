# Mock Interview 反馈系统 — Day 11 Hot-Patch 计划 (2026-05-22)

> 上接 `docs/mock-interview-feedback-redesign-plan-2026-05-22.md` (Day 9-10 完成 + v6 baseline ship 到 prod)。本 Day 11 是**生产回退式 hot-patch** — 独立审查 (worker A/B/C 三组人 + offline audit) 发现 v6 系统有 3 个 blocker + 5 个 major 都已经在生产, 必须先修再继续 SAIF 灰度。
>
> **核心动机**: 我 Day 10 给的 "P8 60→87 / P9 48→88 / strong mean 80.2" 是**单次随机**, 没跑 N=3 复测就 ship 了。独立审查 N=3-style 复测显示 **13/27 persona 跨 run drift ≥10 分**, 当前评分系统**根本不是稳定回归基线**。同时审查抓出 3 个具体严重 bug 我自己 (引入 PR 的人) 都没看到。本 Day 11 = 透明承认 + 修法 + 用更严的 N=3 验证。

---

## 1. Day 9-10 v6 系统的真实状态 (诚实回顾)

### 1.1 我之前汇报的指标

- Strong tier mean: 66.9 → **80.2** (+13.3)
- P8: 60 → 87, P9: 48 → 88, P-trait-S1: 72 → 88, P-bridge-S1: 55 → 78
- fab_numbers_detected: 76.5% → 0%
- 73 个 backend test 全过

### 1.2 这些指标"对"在哪、"错"在哪

| 指标 | 真实程度 | 备注 |
|---|---|---|
| 73 backend test 全过 | ✓ 真 | 单元测试覆盖的逻辑层正确 |
| fab_numbers_detected → 0% | ✓ 真 | Gap 4 anchor 工作了, 但**遮盖了一些真实编造**(simulator 写"4.2% alpha"也被白名单了) |
| strong mean 80.2 | △ **单次**, 重跑 ±10 | 没跑 N=3 — 这是核心方法学失误 |
| P8 87 / P9 88 | △ **单次**, P8 重跑可掉到 60 (fallback 命中), P9 重跑可掉到 57 (跨 simulator 漂移) | 不可重复 |
| 4 个 Gap 真的修了系统 | △ 部分 | turn-level 改了, 但**报告级**同一类 bug 没改透 |

### 1.3 我自我验证为什么没抓到

1. **没跑 N=3 重测** — 直接用单次 baseline 当 ship gate
2. **没验证 stress persona** — P-fake-S1 是我 Day 9 写的 ownership-fallback 红线压力测试 persona, ship 时只看了它 "比 v5 高" 没看 "和设计期待对得上"
3. **fallback 路径自己写的, 没自己 test** — Day 3 加的 `_build_fallback_report` 输出 6 维全 60 看起来"合理", 实际是产品上不能接受的"伪装成正常报告"
4. **pattern cap 修了 turn-level 没修 report-level** — Day 8 加报告级 pattern cap 时镜像了 turn-level 的"翻译腔"识别, 但白名单只在 turn-level prompt 加了, report-level 代码层 cap 还在乱开火

---

## 2. 独立审查证据 — 3 Blocker + 5 Major + 2 Minor

> 完整证据: `docs/eval-full-loop-reports/mock-interview-independent-review-2026-05-22/independent-summary.md` + worker A/B/C 各自 + offline audit + targeted-diff + full-rerun-diff。

### 🔴 Blocker

#### B1. `report_llm_silent` fallback 输出"伪装成正常"的 60 分

| | 现象 |
|---|---|
| **触发** | 报告 LLM 调用失败 → 走 `_build_fallback_report` 兜底 |
| **输出形态** | `overall_score=60` + `dimensions=[6 个全 60]` + `traits=null` + `transferability=null` + `_meta.fallback_reason='report_llm_silent'` |
| **问题** | 6 维全 60 跟"真的中等候选人 60 分"长得一模一样, 学生区分不出来"系统坏了"还是"我真 60" |
| **证据** | 1. targeted P8: baseline `87` → rerun `60`, 6 维全 60, transcript 实际是顶档<br>2. full M14: baseline `73` → rerun `60`, 同样模式 |
| **频率** | full 27 run 1 次 = 3.7%; targeted 11 run 1 次 = 9%. 给单个学生看 → blast radius 不可接受 |

**修法**: `_build_fallback_report` 改成不输出 `dimensions` 数组 (返 `[]`), 把 `overall_score` 设成 `null`, 前端检测到 `_meta.fallback_reason` 时显示 "反馈生成中断 — 已记录, 请稍后刷新" banner, **不显示分数, 不显示 6 维卡片**。

#### B2. 报告级 pattern cap 把强档误杀 (M13 案例)

| | 现象 |
|---|---|
| **触发** | M13 transcript 含 `task force / RFM / BCG / CRM / ID mapping` 等正常 banking/consulting 术语 |
| **当前行为** | `_apply_report_pattern_caps` 在报告层把 logic / industry_sense / expression_depth 强制 cap 到 30 (识别为"翻译腔") |
| **后果** | M13 baseline=58 (logic=30, industry_sense=30, expression_depth=40), 但 rerun 两次都是 88 — 同一 persona 同一题 |
| **诊断** | turn-level 我加了好风格 verbal_tics 白名单 (Day 10 Gap 2), 但 **report-level pattern cap 是代码层规则不读 prompt 白名单**, 还在按 v3 老逻辑 fire |

**修法**: `_apply_report_pattern_caps` 加白名单 dict — `{"task force", "RFM", "BCG", "CRM", "ID mapping", "KPI", "OKR", "BD", "PM", "GMV", "DAU", "MAU"}` 不算翻译腔。维持原 cap 行为只针对真套话 (`leveraged synergies / 端到端价值闭环 / 主导沉淀闭环`)。

#### B3. P-fake-S1 (退回 mentor 红线 persona) 被抬到 78-82

| | 现象 |
|---|---|
| **设计期待** | persona 专门模拟"学生退回 PM/mentor 观点", 期待评分 55-65 区 |
| **实际** | v6 baseline=59 ✓, targeted rerun=78 (+19), full rerun=**82** (+23) |
| **最离谱点** | full rerun `fabrication_suppressed=True` (报告层确实警觉了), 但数字分仍给 82, 6 维 `job_fit=85 / industry_sense=88 / credibility=82` 全顶档. transcript 满屏 "我们 PM 觉得 / 组里讨论的是 / mentor 让我跟踪" |
| **产品影响** | SAIF 试点核心承诺 = "AI 能识别退回 mentor", 现在直接被绕过. 老师看到这个学生会以为"AI 推荐 hire" |

**修法**: 加 `_detect_mentor_fallback(transcript) -> int` 在报告级守卫里 — 统计 `(我们|组里|mentor|PM|senior|老师)(的|让|跟|说|觉得|推|觉得|的看法|的框架|的观点)` 模式次数, ≥3 次 → 强制 cap:
- `overall ≤ 65`
- `credibility ≤ 50`
- 抑制 `内驱力 strong` trait (改成 `weak`)
- 报告级 highlights 加一条 "**注意**: 候选人多次引用 mentor / PM 框架, 自主独立思考的证据不足"

### 🟡 Major

| # | 问题 | 证据 | 修法 |
|---|---|---|---|
| M1 | `fabrication_suppressed=True` 时 numeric score 不受约束 | full 27 里 8 个 reports: suppressed=True AND overall ≥70 | suppressed=True → 强制 cap overall ≤60, 注明 `_meta.score_capped_for_fabrication=True` |
| M2 | turn scoring 偶发 `overall=None` | full 27 里 5 个 persona 至少 1 turn None, 上游聚合 NPE | `score_answer` LLM 失败时 retry 1 次; 仍失败则 raise 让 runner 显式跳过该 turn (不让 None 流入聚合) |
| M3 | P-trait-S1 始终漏 `团队合作` trait | baseline + targeted 都只召回 `内驱力 + 钻研精神`, 命中 2/3 = 66.7% | scoring prompt trait 段加 `团队合作` 具体范例 ("跨部门数据对齐 / 推动 X 团队 align" 这类) |
| M4 | report overall 与 turn mean gap 太宽 | strong cohort turn mean=69.59 vs report mean=80.33 | report prompt 加 "overall 与 turn 均值差距 > 8 分 必须给充分理由 (e.g. 反问环节加分)" |
| M5 | **v6 baseline 不稳定** — 13/27 persona rerun drift ≥10 | 当前 baseline 不是 regression gate | N=3 重测 + 用 mean ± stdev 当 baseline, drift gate 设 1 stdev |

### 🟢 Minor

- **m1**: `improvements_4seg_compliant_pct = 0` 但 `improvements_v2_compliance` 字段有 — audit 代码读了 stale field. 改 audit 读 `improvements_v2_compliance.rate` 字段
- **m2**: M6 transferability `active_bridge` → `no_attempt` 跨 run 跳变, transcript 没变. **暂不修** — 是 M5 (评分不稳定) 的派生, M5 修了这个自动好

---

## 3. Day 11 Hot-Patch 执行顺序 (按 ROI)

### Phase 1 — 阻塞性修法 (B1 + B2 + B3, ~6h)

| 任务 | 文件 | 改动 | 验证 |
|---|---|---|---|
| **B1 Fallback 不伪装** | `backend/app/services/interview/report.py` `_build_fallback_report` | 不输出 dimensions 数组 / overall=null / `_meta.fallback_reason` 保留 | 单元测试: fallback report 应该 `dimensions == []` AND `overall_score is None`. 前端配合 banner 在 task #142 灰度页一起做 |
| **B2 Pattern cap 白名单** | `backend/app/services/interview/report.py` `_apply_report_pattern_caps` | 加 banking/consulting 术语白名单 set, 命中白名单的 token 不进 cap 触发 count | 单元测试: M13 transcript 输入 → logic / industry_sense 不被 cap 到 30. Fixture 用 M13 实际 transcript |
| **B3 Mentor-fallback 守卫** | `backend/app/services/interview/report.py` 新加 `_detect_mentor_fallback(transcript) -> int` + `_cap_for_mentor_fallback(report, count)` | 在 Guard 段 (fab-number 守卫旁边) 加. ≥3 次 → cap overall ≤65, credibility ≤50, 抑制内驱力 strong | 单元测试: P-fake-S1 transcript fixture → cap 触发, overall ≤65 |

### Phase 2 — 一致性修法 (M1 + M2, ~2h)

| 任务 | 文件 | 改动 |
|---|---|---|
| **M1 Suppressed 时降分** | `report.py` Guard 1 段 | suppress 触发后追加 `_cap_overall(report, cap=60)` + `_meta.score_capped_for_fabrication=True` |
| **M2 Turn overall=None** | `backend/app/services/interview/scoring.py` `score_answer` + `tests/eval/run_mock_interview_baseline.py` | scoring 失败 retry 1 次; runner 不让 None 进 turn_score_jsons 列表 |

### Phase 3 — 验证 (~2h compute + 1h 写报告)

| 任务 | 步骤 |
|---|---|
| **N=3 重测** | `tests/eval/run_mock_interview_baseline.py` 加 `--seeds 3` flag 或外层 wrapper script. 跑 27 persona × 6 题 × 3 seed = ~3h 但可并行 |
| **方差统计** | per-persona mean ± stdev; 全部 stdev > 5 的 persona 标红 |
| **Sentinel 校验** | 11 sentinel persona 期待值 (见 §4) 全过才算 ship gate |

### Phase 4 — Ship (~1h)

| 任务 | 步骤 |
|---|---|
| **Commit + Deploy** | 用 `jobradar-vps-deploy` skill |
| **Smoke** | 5 标准 smoke (200/200/200/200/403) + 调一个 demo session 看 report fallback 路径不再返 60 |
| **Memory 更新** | `feedback_dev_constraints.md` 加一条: "ship eval-driven 改动前必须跑 N=3 看方差, 不能用单次 baseline 当 ship gate" |

---

## 4. Sentinel Persona 期待值表 (v7 ship gate)

每个 sentinel 跑 N=3 mean 必须落在期待区间, **任何一个 fail 都不 ship**。

| Sentinel | v6 单次 | **v7 期待 (N=3 mean)** | 检查点 |
|---|---|---|---|
| `P8` (顶档买方研究) | 87 (但 rerun fallback 到 60) | **82-90, stdev ≤ 5** | 不再触 fallback; 不再被白名单外术语 cap |
| `P9` (顶档咨询人) | 88 (rerun 漂到 57-83) | **78-88, stdev ≤ 5** | 报告级与 turn-level gap ≤ 10 |
| `M13` (强档 银行 MT) | 58 ❌ | **80-90, stdev ≤ 5** | pattern cap 不再误杀 banking 术语 |
| `P-trait-S1` (3 trait stress) | 88 | **78-88, stdev ≤ 5, 团队合作 trait 召回 ≥1 次** | M3 修后 trait 召回从 2/3 升 3/3 |
| `P-bridge-S1` (跨 domain) | 78 | **65-80, stdev ≤ 5, transferability=active_bridge stable** | M5 修后跨 run 不漂 |
| `P-fake-S1` (退回 mentor 红线) | 59 (rerun 飙到 82) ❌ | **50-65, ≤65 是硬上限** | B3 守卫触发, overall 不超 65 |
| `M14` (mid 银行) | 73 (rerun fallback 60) | **65-78** | 不再 fallback |
| `M6` (weak 跨专业) | 53 | **42-58, transferability 稳定** | 不被新加守卫带飞 |
| `M9` (extreme 模板) | 25 | **15-35** | 严控不放过 |
| `M11` (extreme track 错配) | 60 | **35-50** | rerun 应更严 |
| `M12` (extreme 翻译腔) | 51 | **40-55** | 稳定 |

---

## 5. 我会做的方法学改进 (Memory 永久)

### M-1: ship 前必须 N=3 复测
**为什么**: LLM 评分天然有方差 (temperature > 0), 单次 baseline ±10 噪声常见. 用单次结果当 regression gate = 自我欺骗.
**怎么应用**: 任何 eval-driven 系统改动 ship 前跑 N=3 (并行), mean ± stdev 报上来, **stdev > 5 时不报"提升 X 分"只报"未发现稳定提升"**.

### M-2: stress persona 必须用"期待区间"判, 不是 "比上一次高"
**为什么**: P-fake-S1 设计就是要保持低分 — v5=59 → v6=82 算 ship 是把负向退化当正向改进了.
**怎么应用**: 每个 stress persona 在 plan 里写明期待区间 (e.g. P-fake-S1 ∈ [50, 65]). v6 报告时同时核对"绝对值对不对", 不只看相对变化.

### M-3: 自己写的 fallback 路径必须自己 test
**为什么**: `_build_fallback_report` Day 3 加的, 跑了 4 个礼拜没人触发, 触发时输出"伪装成正常的 60 分" — 产品级 bug.
**怎么应用**: 任何错误兜底/fallback 路径必须有单元测试用 mock LLM 失败触发, 验证输出 shape 不会"看起来正常"误导调用方.

### M-4: 报告级 vs turn-level 是两套代码, 改一处必查另一处
**为什么**: turn-level 加好风格白名单, report-level pattern cap 没改 → M13 误杀.
**怎么应用**: 每次改 `scoring.py` 同时检查 `report.py` 是否有同名/同类逻辑, 同步改.

---

## 6. 时间线

| 阶段 | 任务 | 工时 |
|---|---|---|
| **Phase 1** | B1 + B2 + B3 三个 blocker 修法 + 单元测试 | 6h |
| **Phase 2** | M1 + M2 两个 major 修法 + 单元测试 | 2h |
| **Phase 3** | N=3 重测 + sentinel 验证 + 写 v7 对照报告 | 4h (含 ~3h compute) |
| **Phase 4** | Commit + Deploy + smoke | 1h |
| **总计** | | **~13h (1.5 工作日)** |

**Day 6 灰度页 + Day 5 retry endpoint 顺序往后挪一天**, Day 11 完成且 v7 ship 后再接。

---

## 7. ship gate

满足**所有**才 ship 给 SAIF:

- [ ] B1 fallback 不再输出 6 维全 60 (单元测试 + 1 个实跑 fallback case)
- [ ] B2 M13 sentinel N=3 mean ∈ [80, 90]
- [ ] B3 P-fake-S1 sentinel N=3 mean ≤ 65 且 max ≤ 70
- [ ] M1 N=3 里 `(suppressed=True AND overall ≥70)` count = 0
- [ ] M2 N=3 里 turn `overall=None` 数 = 0
- [ ] 11 个 sentinel persona N=3 mean **全部**落在 §4 期待区间
- [ ] strong cohort N=3 stdev ≤ 5 (现 ≥10)
- [ ] 73 backend test + 新 Day 11 单元测试 全过
- [ ] 5 项 prod smoke 全 pass

任何一个 fail → 回到对应 task 修, 不绕过.

---

## 附录

- 独立审查全部产出: `docs/eval-full-loop-reports/mock-interview-independent-review-2026-05-22/`
- v6 baseline (single seed, 不稳定): `backend/tests/eval/_out/mock_interview_post_v6_full_2026_05_22.json`
- Full rerun raw (worker triggered): `/tmp/mock_interview_independent_full_27_2026_05_22.json`
- 我自己 Day 10 给的 v6 对照报告 (现已知含 single-seed 单次随机问题): `docs/eval-full-loop-reports/mock_interview_post_v6_2026_05_22.md`
- 现 prod commit: `0e13e50` (v6, 含 3 Blocker + 5 Major)
- Day 11 修法目标 commit: `vX (待生成)`
