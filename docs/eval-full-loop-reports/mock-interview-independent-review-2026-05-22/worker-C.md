# Mock Interview Independent Review 2026-05-22 - Worker C

## Scope

- Worker: C
- Personas: `P-fake-S1`, `M6`, `M11`, `M12`, `M9`
- Baseline: `backend/tests/eval/_out/mock_interview_post_v6_full_2026_05_22.json`
- New raw output: `/tmp/mock_interview_worker_C_2026_05_22.json`
- Targeted command:

```bash
cd backend && PYTHONPATH=. .venv/bin/python tests/eval/run_mock_interview_baseline.py --personas-dirs tests/eval/personas/workspace_2026_05_20,tests/eval/personas/mock_interview_2026_05_20 --questions 6 --workers 1 --include-ids P-fake-S1,M6,M11,M12,M9 --out /tmp/mock_interview_worker_C_2026_05_22.json
```

Run completed and wrote `/tmp/mock_interview_worker_C_2026_05_22.json` with 5 personas.

## Executive Verdict

Recommend triggering a full 27-persona rerun, with special attention to fake/ownership personas and report fabrication suppression.

Reason: 4 of 5 personas behave acceptably or stricter than v6, but `P-fake-S1` is a severe regression: report overall jumps `59 -> 78`, all 6 dimensions increase, traits are inflated, and `fabrication_suppressed=True` coexists with a high final score and only mild ownership warning. This is exactly the fake/mentor-fallback failure mode this worker was assigned to catch.

## Score Deltas

| Persona | Tier / Risk | Baseline Overall | New Overall | Delta | Transferability |
| --- | --- | ---: | ---: | ---: | --- |
| `P-fake-S1` | fake / mentor fallback | 59 | 78 | +19 | `domain_match -> domain_match` |
| `M6` | weak / cross-major bridge | 53 | 42 | -11 | `active_bridge -> no_attempt` |
| `M11` | extreme / track mismatch | 60 | 42 | -18 | `active_bridge -> active_bridge` |
| `M12` | extreme / translation artifact | 51 | 48 | -3 | `domain_match -> domain_match` |
| `M9` | extreme / template STAR | 25 | 22 | -3 | `domain_match -> domain_match` |

## Six-Dimension Deltas

| Persona | job_fit | info_selection | logic | industry_sense | credibility | expression_depth |
| --- | --- | --- | --- | --- | --- | --- |
| `P-fake-S1` | `65 -> 75` (+10) | `45 -> 75` (+30) | `55 -> 80` (+25) | `60 -> 80` (+20) | `60 -> 75` (+15) | `70 -> 85` (+15) |
| `M6` | `62 -> 55` (-7) | `45 -> 30` (-15) | `55 -> 30` (-25) | `60 -> 55` (-5) | `42 -> 50` (+8) | `55 -> 30` (-25) |
| `M11` | `30 -> 30` (+0) | `52 -> 40` (-12) | `65 -> 30` (-35) | `70 -> 30` (-40) | `75 -> 80` (+5) | `70 -> 40` (-30) |
| `M12` | `78 -> 70` (-8) | `70 -> 65` (-5) | `30 -> 30` (+0) | `30 -> 30` (+0) | `72 -> 60` (-12) | `25 -> 30` (+5) |
| `M9` | `30 -> 35` (+5) | `30 -> 25` (-5) | `30 -> 25` (-5) | `20 -> 20` (+0) | `15 -> 15` (+0) | `25 -> 10` (-15) |

## Traits / Audit Deltas

| Persona | Traits Baseline | Traits New | Report Audit Delta |
| --- | --- | --- | --- |
| `P-fake-S1` | `钻研精神:2`, `内驱力:1` | `钻研精神:5`, `内驱力:3` | fabrication warnings `3 -> 5`, suppressed `False -> True`, report length `1010 -> 571` |
| `M6` | `钻研精神:3` | none | warnings `7 -> 4`, suppressed `True -> False`, transferability downgraded to `no_attempt` |
| `M11` | `钻研精神:5` | `内驱力:1` | warnings `3 -> 6`, suppressed `True -> False`, caps expanded to `logic/industry_sense/expression_depth/job_fit` |
| `M12` | `内驱力:1` | `内驱力:2`, `钻研精神:2` | warnings `5 -> 3`, suppressed stays `False`, same translation caps |
| `M9` | none | none | warnings `7 -> 6`, suppressed `False -> True`, report length `1423 -> 398` |

## Manual Text Review

### `P-fake-S1`

Fail / high-risk regression.

The persona is designed to look relevant but fall back to PM/mentor/team ownership. The new transcript still contains ownership caveats such as `我们PM的框架`, `组里的讨论是`, `我们PM那边提供`, `mentor让我跟踪`, `核心推票thesis还是跟PM过`, and `我们mentor觉得`. However, the simulator/report also converts the student into a much stronger independent owner with phrases like `不是谁给我的`, `我自己做了个横截面筛选`, `我自己跑得比较细`, and `这个选择是我自己从周跟踪频率里推的`.

The final report acknowledges the risk only mildly: it says the student should distinguish team framework from personal contribution, but still gives `overall=78`, `logic=80`, `industry_sense=80`, `expression_depth=85`, and inflates traits to `钻研精神:5` / `内驱力:3`. This is an over-lift of a fake/mentor-fallback case. It also has `fabrication_suppressed=True`, empty highlights/improvements, and still preserves very high dimensions, which is internally inconsistent.

### `M6`

Mostly acceptable strictness, with a metadata inconsistency.

The new result is stricter than baseline (`53 -> 42`). It does not let active bridge carry a weak candidate into a safe band. The report correctly flags missing financial modeling, no independent thesis, and legal/policy language substituting for research method.

Potential issue: transferability changes from `active_bridge` to `no_attempt`, even though the transcript repeatedly attempts a policy/legal bridge into public-fund research. The report itself says the student has a cross-disciplinary policy angle. This is not a harmful over-promotion, but the transferability label appears too harsh or inconsistent with the text.

### `M11`

Pass.

The new result fixes the baseline over-generosity (`60 -> 42`). `job_fit` remains capped at 30, and logic/industry_sense/expression_depth are also capped. The report directly states that financial analysis, valuation modeling, and transaction logic are nearly blank. `active_bridge` does not carry this extreme case into a safe band.

Minor issue: audit shows unsuppressed fabrication warnings (`3 -> 6`). Most are rewrite demos/action examples rather than final candidate praise, but exact invented claims such as being able to complete a simple DCF should be watched.

### `M12`

Pass.

The result is stable/slightly stricter (`51 -> 48`). The report correctly separates strong resume fit from bad oral expression: `job_fit=70`, but `logic=30`, `industry_sense=30`, and `expression_depth=30` are capped for translation/buzzword artifacts. This matches the persona intent that the resume is strong but the transcript should drive logic and industry-sense penalties.

Minor issue: traits increased from one signal to four total signals despite the persona being an expression-failure case. This does not appear to affect final scoring materially.

### `M9`

Pass with audit caveat.

The new result stays very low (`25 -> 22`) and does not get fooled by template language. Highlights/improvements are suppressed after fabricated quote detection, and the final report accurately says the candidate has slogans rather than facts, data, or verifiable research cases.

Audit caveat: `_pattern_caps_applied` is absent in the new output even though the case is the canonical template/buzzword violation. Scores are already low, so this is mostly metadata/report consistency rather than a scoring bug.

## Bugs / Risks

1. `P-fake-S1` fake ownership over-promotion.
   - Severity: high.
   - Evidence: overall `59 -> 78`; all 6 dimensions increase; traits inflate to `钻研精神:5` and `内驱力:3`.
   - Impact: mentor/PM fallback is under-penalized; fake/weak ownership is misread as strong independent research.

2. Fabrication suppression does not reliably constrain final scoring.
   - Severity: high for `P-fake-S1`, medium globally.
   - Evidence: `P-fake-S1` has `fabrication_suppressed=True`, empty highlights/improvements, and still gets `overall=78`.
   - Impact: a report can suppress unsafe text while leaving the numeric score overly positive.

3. Transferability label inconsistency on `M6`.
   - Severity: medium-low.
   - Evidence: `active_bridge -> no_attempt`, despite transcript/report discussing legal-policy-to-research bridging.
   - Impact: not an over-promotion, but metadata does not match text and may distort aggregate transferability analysis.

4. Report-audit fabrication warnings remain noisy.
   - Severity: medium.
   - Evidence: all 5 new reports have fabrication warnings; `M6` and `M11` are not suppressed despite exact invented rewrite-demo numbers/claims.
   - Impact: some warnings are rewrite examples rather than candidate claims, but the audit layer cannot clearly distinguish safe coaching examples from fabricated evidence.

## Full Rerun Recommendation

Yes, trigger a full 27-persona rerun, but treat `P-fake-S1` as a blocking sentinel. The full rerun should specifically track:

- fake/mentor fallback score drift,
- trait inflation on weak/fake personas,
- cases where `fabrication_suppressed=True` but final scores remain high,
- transferability label changes (`active_bridge`, `no_attempt`) against transcript evidence,
- missing `_pattern_caps_applied` metadata on template/buzzword cases.
