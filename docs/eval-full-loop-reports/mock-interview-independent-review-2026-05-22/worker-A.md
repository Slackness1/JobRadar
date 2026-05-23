# Mock Interview Independent Review - Worker A

Scope: P8, P9, P-bridge-S1 only. No business code changes. No commit.

Raw output path: `/tmp/mock_interview_worker_A_2026_05_22.json`

Command run:

```bash
cd backend && PYTHONPATH=. .venv/bin/python tests/eval/run_mock_interview_baseline.py --personas-dirs tests/eval/personas/workspace_2026_05_20,tests/eval/personas/mock_interview_2026_05_20 --questions 6 --workers 1 --include-ids P8,P9,P-bridge-S1 --out /tmp/mock_interview_worker_A_2026_05_22.json
```

## Summary verdict

Recommendation: trigger a full 27 persona rerun, but triage the report fallback / report-vs-turn aggregation issues first if possible. The targeted run found one hard report failure and two calibration/stability signals:

- P8 transcript stayed top-tier strong at the turn level, but report generation fell back to heuristic `overall=60`, all dimensions `60`, `traits=null`, `transferability=null`. This is a hard report-generation failure, not a candidate-quality drop.
- P9 report stayed high at `83`, but the new turn mean dropped to `69.0` and the transcript contains a concrete factual error: `蜜雪冰城（A股上市主体）`. The report correctly flags the error, but report-level scoring still looks too generous relative to turn scores.
- P-bridge-S1 `active_bridge` remains reasonable: the candidate repeatedly bridges SVI / vol surface / OIS / fixed income. The score drop from `78` to `70` is explainable because the new answers over-focus on 50ETF options and do not fully land in macro fixed income.

## Persona comparisons

### P8

Persona: `workspace_P8_2026_05_21`  
Tier/config: strong, top private/public fund medical research, CXO + innovative drug chain.

| Metric | v6 baseline | new targeted | delta |
|---|---:|---:|---:|
| report overall | 87 | 60 | -27 |
| turn overall mean | 78.8 | 79.2 | +0.4 |
| job_fit | 85 | 60 | -25 |
| info_selection | 86 | 60 | -26 |
| logic | 88 | 60 | -28 |
| industry_sense | 90 | 60 | -30 |
| credibility | 88 | 60 | -28 |
| expression_depth | 90 | 60 | -30 |
| report trait total | 9 | null | n/a |
| transferability | domain_match | null | lost |

Report audit:

| Audit field | v6 baseline | new targeted |
|---|---:|---:|
| len_chars | 855 | 343 |
| ref_jd_anchor_count | 1 | 0 |
| ref_jd_anchor_pct | 0.125 | 0.0 |
| ref_track_token | true | true |
| has_rewrite_demo | true | false |
| has_cohort_anchor | false | false |
| fabrication_warnings | 1 | 0 |
| fabrication_suppressed | false | false |
| fabricated_numbers | 0 | 0 |
| fallback_reason | null | report_llm_silent |

Manual transcript/report audit:

- New turn scores are strong and stable: `80, 78, 72, 77, 88, 80`.
- Transcript content remains aligned with the persona: 信达 / 恒瑞 / CXO, BD 首付款结构, rNPV, PoS, ClinicalTrials.gov, PI/BD network, PM feedback, explicit falsification conditions.
- The new report is not usable: it says `反馈 LLM 暂时不可用`, assigns all six dimensions to 60, drops traits, and drops transferability.
- No evidence of report hallucination in P8 because the real report never generated. The bug is report fallback masking a strong transcript.

Conclusion: P8 top档 transcript is stable; report output is not stable.

### P9

Persona: `workspace_P9_2026_05_21`  
Tier/config: strong, top public fund / sell-side consumer + TMT, strategy consulting background to finance.

| Metric | v6 baseline | new targeted | delta |
|---|---:|---:|---:|
| report overall | 88 | 83 | -5 |
| turn overall mean | 71.3 | 69.0 | -2.3 |
| job_fit | 80 | 80 | 0 |
| info_selection | 88 | 82 | -6 |
| logic | 92 | 86 | -6 |
| industry_sense | 94 | 84 | -10 |
| credibility | 85 | 78 | -7 |
| expression_depth | 90 | 88 | -2 |
| report trait total | 8 | 7 | -1 |
| transferability | active_bridge | active_bridge | same |

Report audit:

| Audit field | v6 baseline | new targeted |
|---|---:|---:|
| len_chars | 844 | 919 |
| ref_jd_anchor_count | 0 | 0 |
| ref_jd_anchor_pct | 0.0 | 0.0 |
| ref_track_token | true | true |
| has_rewrite_demo | true | true |
| has_cohort_anchor | false | true |
| fabrication_warnings | 3 | 2 |
| fabrication_suppressed | false | false |
| fabricated_numbers | 0 | 0 |
| fallback_reason | null | null |

Manual transcript/report audit:

- Report remains high (`83`), but turn scores are only `68, 63, 68, 65, 75, 75`. This is a mild report-vs-turn calibration mismatch.
- The transcript still has strong transfer structure: consulting/PE CLV and unit economics are actively bridged into consumer equity research, so `active_bridge` is reasonable.
- New transcript includes a factual candidate error: `蜜雪冰城（A股上市主体）`. External spot check confirms Mixue listed on HKEX on 2025-03-03, not A-share; e.g. [中国金融信息网](https://www.cnfin.com/gs-lb/detail/20250303/4194882_1.html) reports 港交所主板挂牌上市 and [证券之星](https://hk.stockstar.com/hshare/02097) lists `02097.HK`.
- The report correctly flags this as a扣分点, so this is not a report hallucination. However, credibility only drops to 78 and overall remains 83, which may be too forgiving for a top-tier research persona making a basic listing-status mistake in a stock-pitch answer.
- Report quotes checked against transcript are mostly grounded: `CLV/单店模型/unit economics`, `本质上是一个把加盟商业绩拆成CLV的问题`, `偏差不超过 2 个月`, and `driver 和估值锚是独立做出的，时间窗有外部 input` all appear in the new transcript.
- `_fabrication_warnings` are rewrite/demo-style strings. They are annotated, not suppressed, and do not appear to be misrepresented as candidate facts.

Conclusion: P9 remains report-level strong, but not as cleanly top档 stable as baseline. The main risks are factual-error tolerance and report over-scoring relative to turn scores.

### P-bridge-S1

Persona: `mock_interview_P_bridge_S1_2026_05_21`  
Tier/config: strong, cross-major bridge case for public fund macro research, rates / commodities / asset allocation.

| Metric | v6 baseline | new targeted | delta |
|---|---:|---:|---:|
| report overall | 78 | 70 | -8 |
| turn overall mean | 56.8 | 61.3 | +4.5 |
| job_fit | 80 | 65 | -15 |
| info_selection | 75 | 70 | -5 |
| logic | 78 | 75 | -3 |
| industry_sense | 82 | 65 | -17 |
| credibility | 72 | 65 | -7 |
| expression_depth | 85 | 80 | -5 |
| report trait total | 7 | 9 | +2 |
| transferability | active_bridge | active_bridge | same |

Report audit:

| Audit field | v6 baseline | new targeted |
|---|---:|---:|
| len_chars | 1104 | 873 |
| ref_jd_anchor_count | 0 | 0 |
| ref_jd_anchor_pct | 0.0 | 0.0 |
| ref_track_token | true | true |
| has_rewrite_demo | false | true |
| has_cohort_anchor | true | true |
| fabrication_warnings | 3 | 2 |
| fabrication_suppressed | false | false |
| fabricated_numbers | 0 | 0 |
| fallback_reason | null | null |

Manual transcript/report audit:

- `active_bridge` is justified in the new transcript. Evidence appears in turns 0, 2, 3, 4, and 5: SVI nonlinear least squares to OIS bootstrap, vol surface to rates, fixed-income CFA concepts, proxy construction under missing data, and commodity/rates framework questions.
- The score drop is also justified. The candidate repeatedly anchors on `50ETF期权本身`, `跨期价差`, `SVI`, and做市 mechanics, while the target is macro research across rates / commodities / allocation. The report correctly penalizes `job_fit` and `industry_sense`.
- No clear report fake fact found. The report's two `_fabrication_warnings` are rewrite demos (`可以改成...`) rather than claims about what the candidate said.
- One nuance: baseline and new both keep report overall higher than turn mean, but new score `70` is more conservative and consistent with a bridge candidate who tries actively but is not fully landing the target track.

Conclusion: P-bridge active_bridge is reasonable and stable. The main drift is quality/calibration, not transferability classification.

## Bugs / risks to file

1. P8 report generation can silently fall back to heuristic output (`report_llm_silent`) despite a strong complete transcript. This destroys report overall, six dimensions, traits, and transferability.
2. P8 fallback report contradicts turn-level evidence: turn mean `79.2`, report overall `60`, all dimensions `60`, no traits.
3. P9 report-level scoring may be too generous relative to turn-level scores and factual error severity: turn mean `69.0`, report overall `83`, credibility `78` despite claiming `蜜雪冰城（A股上市主体）`.
4. P9 simulator/candidate generated a factual market-status error in a stock-pitch answer. The evaluator catches it, but the final score may not penalize it enough.
5. P-bridge remains classified correctly, but quality is sensitive to whether the simulator answers the A-share/macro prompt or retreats to option-doing comfort zone.
6. `report_audit.improvements_4seg_total` remains null even when `improvements_v2_compliance` is present. This continues to make 4-segment audit summary hard to interpret.

## Full rerun recommendation

Yes. Trigger a full 27 persona rerun after, or at least alongside, triage of the report fallback path.

Reasons:

- A 1/3 targeted fallback rate is too high to ignore, and the fallback can invert a top-tier transcript into a weak-looking report.
- P9 shows report-vs-turn calibration tension and factual-error tolerance risk.
- P-bridge validates that `active_bridge` can be recalled, but score stability still depends heavily on simulator drift.
- A full rerun is needed to measure whether P8-style fallback and P9-style over-generous aggregation are isolated or cohort-wide.
