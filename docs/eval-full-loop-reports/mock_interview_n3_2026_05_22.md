# Mock Interview v7 N=3 重测聚合 (2026-05-22)

- 3 次独立全量 baseline (27 persona × 6 题 × 3 seed) — 用 LLM temperature 默认值, 不固定 seed
- runs: `v7final`, `v7_run2`, `v7_run3`

## 1. Sentinel 稳定性 (ship gate: mean ∈ 期待区间 AND stdev ≤ 5)

| Sentinel | v6 单次 | N=3 mean | stdev | min | max | 期待区间 | Pass? | 备注 |
|---|---:|---:|---:|---:|---:|---|---|---|
| `workspace_P8_2026_05_21` | 87 | 88.3 | 2.5 | 86 | 91 | [82, 90] | ✅ | 顶档买方研究 |
| `workspace_P9_2026_05_21` | 88 | 79.0 | 14.1 | 69 | 89 | [78, 88] | ❌ | 顶档咨询人 |
| `mock_interview_M13_2026_05_21` | 58 | 75.3 | 11.0 | 69 | 88 | [68, 88] | ❌ | 强档银行 MT (期待区间放宽: M1 cap=69 上界存在) |
| `mock_interview_P_trait_S1_2026_05_21` | 88 | 78.0 | 9.0 | 69 | 87 | [78, 88] | ❌ | 3 trait stress |
| `mock_interview_P_bridge_S1_2026_05_21` | 78 | 75.0 | 7.2 | 69 | 83 | [65, 80] | ❌ | 跨 domain |
| `mock_interview_P_fake_S1_2026_05_21` | 59 | 63.7 | 9.5 | 54 | 73 | [50, 65] | ❌ | 退回 mentor 红线 (B3 hard cap) |
| `mock_interview_M14_2026_05_21` | 73 | 72.0 | 4.4 | 69 | 77 | [65, 78] | ✅ | mid 银行 |
| `mock_interview_M6_2026_05_21` | 53 | 52.3 | 5.9 | 48 | 59 | [42, 60] | ❌ | weak 跨专业 (放宽 +2 反映 LLM 噪声) |
| `mock_interview_M9_2026_05_20` | 25 | 25.7 | 3.1 | 23 | 29 | [15, 35] | ✅ | extreme 模板 |
| `mock_interview_M11_2026_05_21` | 60 | 56.0 | 7.2 | 48 | 62 | [35, 55] | ❌ | extreme track 错配 (放宽 +5) |
| `mock_interview_M12_2026_05_21` | 51 | 47.7 | 4.0 | 43 | 50 | [40, 55] | ✅ | extreme 翻译腔 |

**Sentinel fails: 7**
- workspace_P9_2026_05_21: stdev 14.1 > 5
- mock_interview_M13_2026_05_21: stdev 11.0 > 5
- mock_interview_P_trait_S1_2026_05_21: stdev 9.0 > 5
- mock_interview_P_bridge_S1_2026_05_21: stdev 7.2 > 5
- mock_interview_P_fake_S1_2026_05_21: stdev 9.5 > 5; max 73 > hard cap 65
- mock_interview_M6_2026_05_21: stdev 5.9 > 5
- mock_interview_M11_2026_05_21: mean 56.0 ∉ [35, 55]; stdev 7.2 > 5

## 2. 全 27 persona N=3 overall 分布

| persona | run1 | run2 | run3 | mean | stdev | range |
|---|---:|---:|---:|---:|---:|---:|
| `mock_interview_M10_2026_05_20` | 63 | 48 | 44 | 51.7 | 10.0 ⚠️ | 19 |
| `mock_interview_M11_2026_05_21` | 48 | 58 | 62 | 56.0 | 7.2 ⚠️ | 14 |
| `mock_interview_M12_2026_05_21` | 50 | 43 | 50 | 47.7 | 4.0 | 7 |
| `mock_interview_M13_2026_05_21` | 69 | 69 | 88 | 75.3 | 11.0 ⚠️ | 19 |
| `mock_interview_M14_2026_05_21` | 69 | 77 | 70 | 72.0 | 4.4 | 8 |
| `mock_interview_M15_2026_05_21` | 83 | 88 | 69 | 80.0 | 9.8 ⚠️ | 19 |
| `mock_interview_M16_2026_05_21` | 83 | 81 | 69 | 77.7 | 7.6 ⚠️ | 14 |
| `mock_interview_M1_2026_05_20` | 84 | 70 | 69 | 74.3 | 8.4 ⚠️ | 15 |
| `mock_interview_M2_2026_05_20` | 61 | 77 | 74 | 70.7 | 8.5 ⚠️ | 16 |
| `mock_interview_M3_2026_05_20` | 68 | 76 | 73 | 72.3 | 4.0 | 8 |
| `mock_interview_M5_2026_05_20` | 73 | 71 | 88 | 77.3 | 9.3 ⚠️ | 17 |
| `mock_interview_M6_2026_05_21` | 59 | 50 | 48 | 52.3 | 5.9 ⚠️ | 11 |
| `mock_interview_M7_2026_05_20` | 53 | 63 | 70 | 62.0 | 8.5 ⚠️ | 17 |
| `mock_interview_M8_2026_05_21` | 69 | 69 | 84 | 74.0 | 8.7 ⚠️ | 15 |
| `mock_interview_M9_2026_05_20` | 29 | 25 | 23 | 25.7 | 3.1 | 6 |
| `mock_interview_P_bridge_S1_2026_05_21` | 73 | 83 | 69 | 75.0 | 7.2 ⚠️ | 14 |
| `mock_interview_P_fake_S1_2026_05_21` | 64 | 54 | 73 | 63.7 | 9.5 ⚠️ | 19 |
| `mock_interview_P_trait_S1_2026_05_21` | 78 | 69 | 87 | 78.0 | 9.0 ⚠️ | 18 |
| `workspace_P1_2026_05_20` | 88 | 85 | 88 | 87.0 | 1.7 | 3 |
| `workspace_P2_2026_05_20` | 86 | 90 | 69 | 81.7 | 11.2 ⚠️ | 21 |
| `workspace_P3_2026_05_20` | 73 | 88 | 69 | 76.7 | 10.0 ⚠️ | 19 |
| `workspace_P4_2026_05_20` | 70 | 69 | 66 | 68.3 | 2.1 | 4 |
| `workspace_P5_2026_05_20` | 87 | 89 | 82 | 86.0 | 3.6 | 7 |
| `workspace_P6_2026_05_20` | 82 | 84 | 85 | 83.7 | 1.5 | 3 |
| `workspace_P7_2026_05_20` | 69 | 69 | 79 | 72.3 | 5.8 ⚠️ | 10 |
| `workspace_P8_2026_05_21` | 91 | 88 | 86 | 88.3 | 2.5 | 5 |
| `workspace_P9_2026_05_21` | 89 | None | 69 | 79.0 | 14.1 ⚠️ | 20 |

## 3. 整体方差 (ship gate)

- 27 persona 平均 stdev: **6.99** (max: 14.1)
- stdev > 5 的 persona 数: **18 / 27**
- 强档 cohort mean: **78.4**, 跨 persona stdev: 5.8

**Ship gate 解读**:
- N=3 平均 stdev ≤ 3 → 系统**稳定** (单 seed 可信)
- 3 < stdev ≤ 5 → 有噪声但可接受 (sentinel 用 mean 判别即可)
- stdev > 5 → **不稳定** (单 seed 不可信, 必须 N=3 取 mean)

## 4. M1 cap 触发 N=3 一致性 (产品监控)

| persona | run1 cap | run2 cap | run3 cap | 一致? |
|---|---|---|---|---|
| `mock_interview_M10_2026_05_20` | — | — | cap | ⚠️ |
| `mock_interview_M12_2026_05_21` | — | — | cap | ⚠️ |
| `mock_interview_M13_2026_05_21` | cap | cap | — | ⚠️ |
| `mock_interview_M14_2026_05_21` | cap | — | — | ⚠️ |
| `mock_interview_M15_2026_05_21` | — | — | cap | ⚠️ |
| `mock_interview_M16_2026_05_21` | — | — | cap | ⚠️ |
| `mock_interview_M1_2026_05_20` | — | — | cap | ⚠️ |
| `mock_interview_M6_2026_05_21` | — | — | cap | ⚠️ |
| `mock_interview_M8_2026_05_21` | cap | cap | — | ⚠️ |
| `mock_interview_M9_2026_05_20` | — | cap | — | ⚠️ |
| `mock_interview_P_trait_S1_2026_05_21` | — | cap | — | ⚠️ |
| `workspace_P2_2026_05_20` | — | — | cap | ⚠️ |
| `workspace_P3_2026_05_20` | — | — | cap | ⚠️ |
| `workspace_P4_2026_05_20` | — | cap | cap | ⚠️ |
| `workspace_P7_2026_05_20` | cap | cap | — | ⚠️ |
| `workspace_P9_2026_05_21` | — | — | cap | ⚠️ |

- M1 cap 总触发次数 (27 persona × 3 run = 81 reports): **20** (24.7%)
