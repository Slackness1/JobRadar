# Mock Interview Independent Review 2026-05-22

## Scope

本轮按“混合复测”执行：先审计 v6 baseline，再分组 targeted 复测 11 个高风险 persona，最后因 targeted 命中系统性问题而补跑完整 27 persona。

没有修改业务代码，没有 commit。所有新增内容仅限本报告目录。

## Data Integrity

- 飞书文件夹：`40_模拟面试`
- 飞书 v6 文件：`v6_baseline_27persona_完整对话+评分.json`
- 本地 v6 文件：`backend/tests/eval/_out/mock_interview_post_v6_full_2026_05_22.json`
- SHA256：`9c29b9cd37daadcbd84e45eda69ece72cdb0da0e058a5795236cf9d415c08eda`
- 结论：飞书和 repo 的 v6 baseline 是同一份。
- 工具备注：按计划未更新 `lark-cli`，保留 1.0.34，避免工具版本影响复现。

## Artifacts

- Offline audit: `offline-audit.md`, `offline-audit.json`
- Targeted diff: `targeted-diff.json`
- Full rerun diff: `full-rerun-diff.json`
- Worker reports: `worker-A.md`, `worker-B.md`, `worker-C.md`
- Raw targeted outputs:
  - `/tmp/mock_interview_worker_A_2026_05_22.json`
  - `/tmp/mock_interview_worker_B_2026_05_22.json`
  - `/tmp/mock_interview_worker_C_2026_05_22.json`
- Raw full output: `/tmp/mock_interview_independent_full_27_2026_05_22.json`

## Execution

Targeted 11 persona:

| Group | Personas | Result |
| --- | --- | --- |
| A | `P8`, `P9`, `P-bridge-S1` | Completed |
| B | `M13`, `M14`, `P-trait-S1` | Completed |
| C | `P-fake-S1`, `M6`, `M11`, `M12`, `M9` | Completed |

Full 27 persona rerun was triggered because targeted produced more than 2 systemic issues:

- 6 / 11 targeted samples had overall drift >= 10.
- `P8` hit `report_llm_silent` fallback on a strong transcript.
- `M13` moved `58 -> 88` with nearly unchanged turn mean, pointing to baseline scoring/post-processing mis-kill.
- `P-fake-S1` moved `59 -> 78` targeted and `59 -> 82` full, with fake/mentor fallback under-penalized.

Full run completed in 4196.3 seconds and wrote 27 persona.

## Offline Audit Findings

Offline audit of v6 baseline found 9 issues:

| Severity | Case | Finding |
| --- | --- | --- |
| Blocker | `mock_interview_M13_2026_05_21` | Strong persona scored 58, with `logic=30`, `industry_sense=30`, `expression_depth=40` despite positive comments. |
| Blocker | `workspace_P1_2026_05_20` | Strong persona below 70 in baseline. |
| Major | All | `fabrication_suppressed_pct=0.333`, high enough to require manual audit. |
| Major | All | `improvements_4seg_compliant_pct=0`, while many reports have v2-compliant improvements, suggesting audit metric mismatch or stale field. |
| Major | `mock_interview_M14_2026_05_21` | Trait recall empty in baseline. |
| Major | `workspace_P3_2026_05_20` | Overall 82 but one dimension collapsed to 30 with positive text. |
| Minor | All | `cohort_anchor` recall below target. |
| Minor | All | `rewrite_demo` recall below target. |

## Targeted Results

| Persona | Baseline | Targeted | Delta | Main Signal |
| --- | ---: | ---: | ---: | --- |
| `workspace_P8_2026_05_21` | 87 | 60 | -27 | Report fallback `report_llm_silent`; turn mean still 79.2. |
| `mock_interview_M13_2026_05_21` | 58 | 88 | +30 | Baseline cap/post-processing mis-kill. |
| `mock_interview_P_trait_S1_2026_05_21` | 88 | 72 | -16 | Trait stress case unstable; `团队合作` still missed. |
| `mock_interview_P_fake_S1_2026_05_21` | 59 | 78 | +19 | Fake/mentor fallback over-promoted. |
| `mock_interview_M11_2026_05_21` | 60 | 42 | -18 | New run stricter, acceptable. |
| `mock_interview_M6_2026_05_21` | 53 | 42 | -11 | New run stricter, but transferability changed to `no_attempt`. |
| `mock_interview_P_bridge_S1_2026_05_21` | 78 | 70 | -8 | Active bridge label stable; score drop explainable. |
| `workspace_P9_2026_05_21` | 88 | 83 | -5 | Report still high despite factual market-status error. |

## Full Rerun Results

Full run summary:

| Metric | Value |
| --- | ---: |
| Personas | 27 |
| Overall drift >= 10 | 13 |
| Strong below 70 | 2 |
| Turn `overall=None` | 5 |
| Report fallback | 1 |
| `fabrication_suppressed=True` and score >= 70 | 8 |
| Any fabrication warning | 96.3% |
| Fabrication suppressed | 40.7% |
| 4-seg compliant pct | 0.0% |

Notable full-run deltas:

| Persona | Baseline | Full | Delta | Note |
| --- | ---: | ---: | ---: | --- |
| `mock_interview_M13_2026_05_21` | 58 | 88 | +30 | Confirms baseline strong false negative. |
| `workspace_P5_2026_05_20` | 85 | 57 | -28 | Strong persona fell below 70; transcript turn mean was also weak, likely simulator drift plus cap. |
| `mock_interview_M16_2026_05_21` | 85 | 62 | -23 | Mid persona large drop; report suppressed unsafe feedback and lost useful sections. |
| `mock_interview_P_fake_S1_2026_05_21` | 59 | 82 | +23 | Confirms fake/mentor fallback over-promotion. |
| `mock_interview_P_bridge_S1_2026_05_21` | 78 | 61 | -17 | Strong cross-major bridge falls below 70 despite `active_bridge`. |
| `mock_interview_M14_2026_05_21` | 73 | 60 | -13 | Full run reproduced report fallback, all dimensions forced to 60. |
| `workspace_P8_2026_05_21` | 87 | 92 | +5 | P8 full recovered, supporting that targeted failure was fallback, not persona quality. |

## Blockers

### B1. Report fallback can overwrite a valid interview with unusable final scoring

Evidence:

- Targeted `workspace_P8_2026_05_21`: baseline `87`, targeted `60`, `fallback_reason=report_llm_silent`, all six dimensions forced to 60, traits and transferability lost.
- Full `mock_interview_M14_2026_05_21`: baseline `73`, full `60`, `fallback_reason=report_llm_silent`, all six dimensions forced to 60.

Impact:

学生会看到一份像“系统临时坏了”的反馈，但它仍然带着正式总分和维度分。这个会污染 demo，也会污染 baseline 指标。

### B2. Strong persona can be post-processed into false negative

Evidence:

- `mock_interview_M13_2026_05_21`: v6 baseline `58`, targeted `88`, full `88`.
- Baseline report text正向评价能力和行业内容，但 `logic=30`, `industry_sense=30`, `expression_depth=40`。
- Targeted and full both显示这不是 persona 标注错，也不是候选人真实表现差。

Likely cause:

Pattern cap around “翻译腔 / 英文管理黑话” over-applies to normal finance/consulting vocabulary or is applied inconsistently at report aggregation.

### B3. Fake / mentor fallback can be over-promoted into high score

Evidence:

- `mock_interview_P_fake_S1_2026_05_21`: baseline `59`, targeted `78`, full `82`.
- Full report still mentions `PM/mentor` ownership caveat, but gives `job_fit=85`, `industry_sense=88`, `credibility=82`, `overall=82`.
- Targeted run even had `fabrication_suppressed=True` while preserving high final score.

Impact:

这是最接近“学生把团队/导师贡献包装成自己独立研究”的红线场景。现在系统会温和提醒，但数字分和 traits 会把它抬成强候选人。

## Majors

### M1. Fabrication suppression does not constrain numeric score

Full run has 8 reports where `fabrication_suppressed=True` and final score is still >= 70. The text layer may suppress highlights/improvements, but numeric score remains high, causing “安全文案”和“高分判断”互相冲突。

### M2. Turn scoring sometimes returns `overall=None`

Full run has 5 personas with at least one turn `overall=None`:

- `mock_interview_M13_2026_05_21`
- `mock_interview_P_fake_S1_2026_05_21`
- `workspace_P6_2026_05_20`
- `mock_interview_M9_2026_05_20`
- `workspace_P2_2026_05_20`

This weakens report aggregation and makes score drift harder to interpret.

### M3. Trait recall is unstable

Evidence:

- `P-trait-S1` is designed to surface `内驱力`, `团队合作`, `钻研精神`; both baseline and targeted report-level traits miss `团队合作`.
- `M14` baseline had `traits=[]`; targeted recalled 2 traits; full fallback dropped traits entirely.

### M4. Report-vs-turn aggregation can be too wide

Examples:

- `P9` targeted turn mean was 69.0, report overall 83.
- Full `strong` cohort turn mean 69.59 but report overall mean 80.33.

Some gap is expected because final report has global context, but the current gap is wide enough to mask factual errors or weak turns.

### M5. Full run shows high instability versus v6 baseline

13 / 27 full rerun personas moved by >= 10 points. This is larger than acceptable if the baseline is meant to be a stable regression gate.

## Minors

### m1. 4-segment improvement audit metric is probably stale or mismatched

`improvements_4seg_compliant_pct` stays 0.0%, while many reports contain `improvements_v2_compliance` with compliant entries. This looks like the audit summary is not reading the newer structure.

### m2. Transferability labels can move despite similar text

Examples:

- Targeted `M6`: `active_bridge -> no_attempt`, though the transcript still attempts legal/policy-to-research bridging.
- Full `P_bridge_S1`: `active_bridge` remains stable, but score falls to 61.

## Recommendation

Do not treat v6 baseline as a clean release gate yet. The strongest blockers are not broad model quality; they are specific failure modes:

1. Report fallback should not emit authoritative-looking six-dimension scores.
2. Pattern caps need guardrails so normal finance/consulting terms do not collapse strong candidates.
3. Fake/mentor ownership should cap score and traits, not merely produce a mild warning.
4. Fabrication suppression should affect numeric scoring or mark the report as non-final.
5. The eval harness should fail or retry on `turn.overall=None` and `report_llm_silent` instead of silently aggregating.

Suggested next order:

1. Fix report fallback and `overall=None` handling first, because they pollute all metrics.
2. Add sentinel assertions for `M13`, `P_fake_S1`, `P8`, `M14`, and `P_trait_S1`.
3. Repair `improvements_4seg_compliant_pct` to read the current `improvements_v2` structure.
4. Re-run targeted sentinels before another full 27 run.
