# Mock Interview Independent Review - Worker B

Scope: M13, M14, P-trait-S1 only. No business code changes. No commit.

Raw output path: `/tmp/mock_interview_worker_B_2026_05_22.json`

Command run:

```bash
cd backend && PYTHONPATH=. .venv/bin/python tests/eval/run_mock_interview_baseline.py --personas-dirs tests/eval/personas/workspace_2026_05_20,tests/eval/personas/mock_interview_2026_05_20 --questions 6 --workers 1 --include-ids M13,M14,P-trait-S1 --out /tmp/mock_interview_worker_B_2026_05_22.json
```

## Summary verdict

Recommendation: trigger full 27 persona rerun after triaging the two high-signal issues below. If no code/config fix is planned first, a full rerun is still useful to quantify blast radius, but the rerun will likely reproduce noisy failures.

Main findings:

- M13 strong-tier score 58 is not a persona labeling issue. The transcript is strong and aligned. The v6 low report score is best classified as scoring/post-processing mis-kill, especially the pattern cap on `logic`, `industry_sense`, and `expression_depth`.
- M14 v6 `traits=[]` is a mild trait aggregation/recall instability. The candidate is mid-tier and not trait-heavy, but the transcript contains enough evidence for at least weak/moderate diligence/learning signals. New run surfaced 2 report traits.
- P-trait-S1 is not fully stable. Both baseline and new report-level traits miss the expected `团队合作` trait, and the new run generated an empty answer for turn 0. Trait-category recall remains 2/3, below the persona note expectation of >=80%.

## Persona comparisons

### M13

Persona: `mock_interview_M13_2026_05_21`  
Tier/config: strong, top joint-stock bank HQ MT / large SOE group strategy MT.

| Metric | v6 baseline | new targeted | delta |
|---|---:|---:|---:|
| report overall | 58 | 88 | +30 |
| turn overall mean | 71.3 | 71.0 | -0.3 |
| job_fit | 85 | 85 | 0 |
| info_selection | 80 | 85 | +5 |
| logic | 30 | 88 | +58 |
| industry_sense | 30 | 90 | +60 |
| credibility | 85 | 88 | +3 |
| expression_depth | 40 | 90 | +50 |
| report trait total | 4 | 3 | -1 |
| transferability | domain_match | domain_match | same |

Report audit:

| Audit field | v6 baseline | new targeted |
|---|---:|---:|
| len_chars | 1547 | 1156 |
| ref_jd_anchor_count | 1 | 1 |
| ref_jd_anchor_pct | 0.125 | 0.125 |
| ref_track_token | true | true |
| has_rewrite_demo | false | true |
| has_cohort_anchor | false | true |
| fabrication_warnings | 7 | 5 |
| fabrication_suppressed | false | false |
| fabricated_numbers | 0 | 0 |

Manual transcript/report audit:

- v6 and new turn-level means are almost identical, but report overall moved from 58 to 88. That points away from candidate quality and toward report-level aggregation/cap behavior.
- v6 dimensions are internally contradictory: comments praise strong business alignment and concrete industry detail, while `logic=30`, `industry_sense=30`, `expression_depth=40` were capped by "翻译腔/英文管理黑话".
- The M13 transcript contains normal finance/consulting vocabulary such as `task force`, `RFM`, `BCG`, `CRM`, `ID mapping`, but the substance is concrete: 5 subsidiaries, 28-page whitepaper, 38% overlap, <5% referral, BCG LTV segmentation, target-bank green finance/county-market synergy.
- New run still has repetitive phrases, but not low-quality content. Score 88 is more consistent with strong-tier persona and transcript.

Conclusion: M13 is a scoring/post-processing bug, not persona mislabeling and not a genuinely poor candidate performance. The likely bug is over-aggressive or unstable pattern cap application at report aggregation time.

### M14

Persona: `mock_interview_M14_2026_05_21`  
Tier/config: mid, mid joint-stock bank HQ MT / city commercial bank HQ MT.

| Metric | v6 baseline | new targeted | delta |
|---|---:|---:|---:|
| report overall | 73 | 69 | -4 |
| turn overall mean | 57.2 | 62.7 | +5.5 |
| job_fit | 70 | 70 | 0 |
| info_selection | 72 | 65 | -7 |
| logic | 75 | 75 | 0 |
| industry_sense | 78 | 65 | -13 |
| credibility | 75 | 70 | -5 |
| expression_depth | 68 | 70 | +2 |
| report trait total | 0 | 2 | +2 |
| transferability | domain_match | domain_match | same |

Report audit:

| Audit field | v6 baseline | new targeted |
|---|---:|---:|
| len_chars | 923 | 1384 |
| ref_jd_anchor_count | 3 | 2 |
| ref_jd_anchor_pct | 0.375 | 0.25 |
| ref_track_token | true | true |
| has_rewrite_demo | false | true |
| has_cohort_anchor | false | false |
| fabrication_warnings | 6 | 5 |
| fabrication_suppressed | true | false |
| fabricated_numbers | 0 | 0 |

Manual transcript/report audit:

- v6 report-level `traits=[]`, but v6 turn scoring did detect two weak `钻研精神` signals.
- New run report aggregated `学习能力=1` and `钻研精神=1`, with evidence such as calling 5 branches to confirm 36 loans and course/thesis alignment.
- This persona is not designed as a strong trait persona; it is a mid bank-risk profile with careful but not exceptional signals. A zero-trait report is therefore not catastrophic, but it is unstable relative to turn-level evidence.
- New report quality is better: `has_rewrite_demo` changed false to true and `fabrication_suppressed` changed true to false.

Conclusion: M14 traits=0 is likely a mild report-level aggregation/threshold miss rather than a major recall failure. It should be tracked, but I would not trigger a full rerun for M14 alone.

### P-trait-S1

Persona: `mock_interview_P_trait_S1_2026_05_21`  
Tier/config: strong trait stress case for public-fund TMT research. Persona notes expect strong signals for `内驱力`, `团队合作`, and `钻研精神`, with trait recall >=80%.

| Metric | v6 baseline | new targeted | delta |
|---|---:|---:|---:|
| report overall | 88 | 72 | -16 |
| turn overall mean | 61.3 | 65.8 | +4.5 |
| job_fit | 85 | 75 | -10 |
| info_selection | 88 | 55 | -33 |
| logic | 85 | 75 | -10 |
| industry_sense | 90 | 80 | -10 |
| credibility | 92 | 70 | -22 |
| expression_depth | 88 | 80 | -8 |
| report trait total | 8 | 6 | -2 |
| transferability | domain_match | domain_match | same |

Report audit:

| Audit field | v6 baseline | new targeted |
|---|---:|---:|
| len_chars | 1009 | 1164 |
| ref_jd_anchor_count | 0 | 0 |
| ref_jd_anchor_pct | 0.0 | 0.0 |
| ref_track_token | true | true |
| has_rewrite_demo | true | true |
| has_cohort_anchor | true | true |
| fabrication_warnings | 4 | 3 |
| fabrication_suppressed | false | false |
| fabricated_numbers | 0 | 0 |

Manual transcript/report audit:

- New run turn 0 generated an empty answer (`len=0`) and still assigned overall 50. This is a generation/eval stability bug.
- Both baseline and new report-level traits only include `内驱力` and `钻研精神`. The expected `团队合作` signal from 易方达 cross-team data alignment / product-team persuasion is not surfaced in report traits.
- New turn 4 contains a clear teamwork/collaboration answer: pushing quant IT and industry research to align GMV/DAU/MAU/user-duration definitions across 12 companies via 4 cross-group meetings. It still did not produce a `团队合作` trait signal.
- New answer to "推一只 A 股" still recommends 网易云音乐, a Hong Kong stock connect name. The report correctly flags instruction mismatch, but this also depresses overall stability.

Conclusion: P-trait-S1 is not stable enough. Trait recall is effectively 2/3 categories in both runs, below the persona's stated target. The missing `团队合作` recall is the main product bug; the empty turn 0 answer is a separate runner/generator stability bug.

## Bugs / risks to file

1. M13 report-level pattern cap over-applies to normal finance/consulting English terms and can collapse strong candidates from high 80s to 58 despite similar turn means.
2. P-trait-S1 can produce an empty answer for turn 0 while still receiving a nonzero score.
3. P-trait-S1 report trait aggregation misses the explicit `团队合作` category even when transcript contains cross-team alignment evidence.
4. M14 report trait aggregation is unstable: v6 turn-level weak signals did not aggregate, while targeted run aggregated 2 traits.
5. `report_audit.improvements_4seg_total` remains null even when `improvements_v2` entries are structurally present. This makes the audit summary's 4-segment compliance hard to interpret.

## Full rerun recommendation

Yes, trigger a full 27 persona rerun, ideally after triaging the M13 cap and P-trait generation/trait-recall issues. Reasons:

- M13 is a severe false negative on a strong persona: +30 report-overall swing with nearly unchanged turn mean.
- P-trait-S1 fails the explicit trait stress objective in both runs by missing `团队合作`.
- The new P-trait run produced an empty answer, so runner/generator stability needs blast-radius measurement.
- M14 shows lower-severity trait aggregation instability that may affect other mid personas.
