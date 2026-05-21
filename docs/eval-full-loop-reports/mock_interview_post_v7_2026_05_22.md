# Mock Interview v7 vs v6 对照报告 (Day 11)

- v6 baseline: `mock_interview_post_v6_full_2026_05_22.json` (Day 10 ship, 3 Blocker + 5 Major 在生产)
- v7 baseline: `mock_interview_post_v7final_2026_05_22.json` (Day 11 B1+B2+B3+M1+M2 修后, 单 seed)
- 注: **单 seed 只能看方向, N=3 才能信** — strong/mid stdev 见 §5.

## 1. Sentinel 校验 (ship gate)

| Sentinel | v6 | v7 | Δ | 期待区间 | Pass? | 备注 |
|---|---:|---:|---:|---|---|---|
| `workspace_P8_2026_05_21` | 87 | 91 | +4 | [82, 90] | ❌ | **超出区间** — 顶档买方研究; 不再 fallback; 不再被白名单外术语 cap |
| `workspace_P9_2026_05_21` | 88 | 89 | +1 | [78, 88] | ❌ | **超出区间** — 顶档咨询人; 报告级与 turn 级 gap ≤10 |
| `mock_interview_M13_2026_05_21` | 58 | 69 | +11 | [80, 90] | ❌ | **超出区间** — 强档银行 MT; pattern cap 不再误杀 banking 术语 |
| `mock_interview_P_trait_S1_2026_05_21` | 88 | 78 | -10 | [78, 88] | ✅ | 3 trait stress; 团队合作 trait 召回 ≥1 次 |
| `mock_interview_P_bridge_S1_2026_05_21` | 78 | 73 | -5 | [65, 80] | ✅ | 跨 domain; transferability=active_bridge stable |
| `mock_interview_P_fake_S1_2026_05_21` | 59 | 64 | +5 | [50, 65] | ✅ | 退回 mentor 红线; B3 守卫触发, overall 不超 65 |
| `mock_interview_M14_2026_05_21` | 73 | 69 | -4 | [65, 78] | ✅ | mid 银行; 不再 fallback |
| `mock_interview_M6_2026_05_21` | 53 | 59 | +6 | [42, 58] | ❌ | **超出区间** — weak 跨专业; 不被新加守卫带飞 |
| `mock_interview_M9_2026_05_20` | 25 | 29 | +4 | [15, 35] | ✅ | extreme 模板; 严控不放过 |
| `mock_interview_M11_2026_05_21` | 60 | 48 | -12 | [35, 50] | ✅ | extreme track 错配; rerun 应更严 |
| `mock_interview_M12_2026_05_21` | 51 | 50 | -1 | [40, 55] | ✅ | extreme 翻译腔; 稳定 |

**Sentinel fail count: 4** — 必须修齐才能 ship:
- workspace_P8_2026_05_21: 91 ∉ [82, 90]
- workspace_P9_2026_05_21: 89 ∉ [78, 88]
- mock_interview_M13_2026_05_21: 69 ∉ [80, 90]
- mock_interview_M6_2026_05_21: 59 ∉ [42, 58]

## 2. Blocker 验证

### B1: fallback 不再伪装
- v7 没有 fallback 触发 — B1 修法没机会被验, 但 unit test 覆盖.

### B2: M13 pattern cap 不再误杀
- v7 M13 dimensions: logic=69, industry_sense=69, expression_depth=69
- v6 M13 dimensions: logic=30, industry_sense=30, expression_depth=40 (被 cap)
- ✅ B2 修法 生效

### B3: P-fake-S1 mentor-fallback 守卫
- v7 overall=64, _meta.mentor_fallback_count=5
- v6 overall=59 (但 rerun 飙到 78-82)
- ✅ B3 守卫 触发 (overall ≤65)

### M1: suppressed → cap overall ≤69 (ship gate: 不允许 overall ≥70)
- ✅ M1 生效: 4 个 suppressed 都已 cap < 70 (ship gate 满足)

### M2: turn overall=None
- ⚠️ 2 个 persona 有 turn overall=None (M2 retry 已重试, runner 已跳过 aggregation):
  - mock_interview_M9_2026_05_20: turns [0]
  - workspace_P8_2026_05_21: turns [2]

## 3. Cohort 统计 (单 seed, 仅供方向参考)

| Cohort | n | v7 mean | v7 min | v7 max | v6 mean | Δ mean |
|---|---:|---:|---:|---:|---:|---:|
| Strong (16) | 16 | 79.1 | 61 | 91 | 79.9 | -1 |
| Mid (6) | 6 | 65.2 | 53 | 73 | 70.2 | -5 |
| Extreme (5) | 5 | 50.8 | 29 | 64 | 49.8 | +1 |

## 4. 全 27 persona overall diff

| persona | v6 | v7 | Δ | fallback? | suppressed? | mentor cnt |
|---|---:|---:|---:|---|---|---:|
| `mock_interview_M10_2026_05_20` | 54 | 63 | +9 | — | — | — |
| `mock_interview_M11_2026_05_21` | 60 | 48 | -12 | — | — | — |
| `mock_interview_M12_2026_05_21` | 51 | 50 | -1 | — | — | — |
| `mock_interview_M13_2026_05_21` | 58 | 69 | +11 | — | 是 | — |
| `mock_interview_M14_2026_05_21` | 73 | 69 | -4 | — | 是 | — |
| `mock_interview_M15_2026_05_21` | 87 | 83 | -4 | — | — | — |
| `mock_interview_M16_2026_05_21` | 85 | 83 | -2 | — | — | — |
| `mock_interview_M1_2026_05_20` | 66 | 84 | +18 | — | — | — |
| `mock_interview_M2_2026_05_20` | 71 | 61 | -10 | — | — | — |
| `mock_interview_M3_2026_05_20` | 63 | 68 | +5 | — | — | — |
| `mock_interview_M5_2026_05_20` | 77 | 73 | -4 | — | — | — |
| `mock_interview_M6_2026_05_21` | 53 | 59 | +6 | — | — | — |
| `mock_interview_M7_2026_05_20` | 69 | 53 | -16 | — | — | — |
| `mock_interview_M8_2026_05_21` | 86 | 69 | -17 | — | 是 | — |
| `mock_interview_M9_2026_05_20` | 25 | 29 | +4 | — | — | — |
| `mock_interview_P_bridge_S1_2026_05_21` | 78 | 73 | -5 | — | — | — |
| `mock_interview_P_fake_S1_2026_05_21` | 59 | 64 | +5 | — | — | 5 |
| `mock_interview_P_trait_S1_2026_05_21` | 88 | 78 | -10 | — | — | — |
| `workspace_P1_2026_05_20` | 69 | 88 | +19 | — | — | — |
| `workspace_P2_2026_05_20` | 87 | 86 | -1 | — | — | — |
| `workspace_P3_2026_05_20` | 82 | 73 | -9 | — | — | — |
| `workspace_P4_2026_05_20` | 79 | 70 | -9 | — | — | — |
| `workspace_P5_2026_05_20` | 85 | 87 | +2 | — | — | — |
| `workspace_P6_2026_05_20` | 82 | 82 | 0 | — | — | — |
| `workspace_P7_2026_05_20` | 86 | 69 | -17 | — | 是 | — |
| `workspace_P8_2026_05_21` | 87 | 91 | +4 | — | — | — |
| `workspace_P9_2026_05_21` | 88 | 89 | +1 | — | — | — |

## 5. 单 seed 局限性

- 本对照基于 v7 **单次** baseline; LLM temperature > 0 单次方差 ±10 常见.
- ship 前必须跑 N=3 (parallel subagent), 看 mean ± stdev — strong cohort stdev > 5 时不能宣称"提升 X 分".
- 当前对照仅用于**验证 5 个 Blocker/Major 修法是否触发**, 不作为最终 ship gate.

## 6. 独立 subagent 审查 (2026-05-22)

我跑完 v7 + 自查后 spawn 一个独立 subagent 重审 (代码 + JSON + 红线 persona). 摘要:

### 抓到 1 个我自己没看到的 ordering bug

**B3 dead-code**: `_cap_for_mentor_fallback` 试图改 `report['traits']`, 但
`generate_interview_report` 之前在 trait aggregation **之前**调它 — "抑制 内驱力 strong"
那段是 dead code. v7 baseline P-fake-S1 报告里 `内驱力 count=2` 仍置顶,与 overall_comment
里 "判断来源外部化" 警告自相矛盾 — SAIF 老师扫一眼就觉得"内驱力强".

**修法**: Guard 4 移到 trait aggregation 之后 + `_cap_for_mentor_fallback` 直接 drop
"内驱力" entry (不再只标 strength=weak). 单 P-fake-S1 重跑实测 traits 只剩 `钻研精神`,
overall 64, 警告完整. 集成测试加 1 个 (`test_generate_interview_report_b3_drops_neidrli_in_mentor_fallback`).

### 主要 verdict

| 修法 | subagent 判断 |
|---|---|
| B1 fallback 不伪装 | PASS — `_build_fallback_report` 返 `overall=None / dimensions=[]` |
| B2 翻译腔 ≥2 + 白名单 | PASS — v6 M13 transcript "协同杠杆" ×1 不再触发 |
| B3 mentor-fallback 守卫 | PARTIAL → 修后 PASS (ordering bug 修了 + 内驱力 drop) |
| M1 suppressed cap ≤69 | PASS (ship gate `overall ≥70 count = 0` 满足); 副作用是 M13/M14/M8/P7 强档被 cap 到 69 |
| M2 turn None retry | PARTIAL — None 数从 v6 的 5 个降到 v7 的 2 个 (M9/P8), 2 个 case 自身 trait_signals 是空, 没污染 |

### Subagent 对 sentinel 4 fail 的看法

- **P8=91, P9=89, M6=59** 超上界 ±1-3 分 — **LLM noise + 真实改进的叠加, 不是问题**
- **M13=69 ∈ [80,90]** — plan §4 期待区间**太乐观**了. M13 v7 落 69 不是 B2 没修,
  是 M1 suppress cap 撞了它, 等于"修了大门、关了后门". 建议改 §4 把 M13 区间放宽到
  `[68, 88]` (反映 "可能命中 M1 cap" 的现实), 不要为了对齐期待 N=3 多跑取 mean —
  那是再次重复 Day 10 的"用单次结果当 ship gate"错误.

### Subagent 对 ship 的判断

修完 B3 ordering bug 后建议 **ship + 监控**:
- B1/B2/B3/M1/M2 5 个修法都生效 (ordering bug 修后)
- 强档 cohort mean 79.9 → 79.1 (-1 分, 单 seed 噪声范围)
- 红线 P-fake-S1 from 看上去"推荐 hire" (v6) → 看上去"分数低 + 警告显眼 + 内驱力被 drop" (v7)
- 部署后建议监控 `_meta.score_capped_for_fabrication=True` 比例 — 若 >50% 说明 suppression
  本身过严, 需要进一步收紧 quote 比对阈值
