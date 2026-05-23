# Mock Interview Independent Review — Offline v6 Audit

Source: `/home/ubuntu/projects/JobRadar/backend/tests/eval/_out/mock_interview_post_v6_full_2026_05_22.json`

## Summary

- Personas: 27
- Issues: 9 (blocker=3, major=4, minor=2)
- Strong mean: 80.22
- Extreme mean: 47.5

## Issues

- **BLOCKER** `mock_interview_M13_2026_05_21` — M13 strong misclassified low: M13 is marked strong but scored 58; must inspect transcript/report to decide if persona is mislabeled or scoring is over-penalizing.
- **BLOCKER** `mock_interview_M13_2026_05_21` — strong persona overall < 70: mock_interview_M13_2026_05_21 tier=strong but overall=58.
- **BLOCKER** `workspace_P1_2026_05_20` — strong persona overall < 70: workspace_P1_2026_05_20 tier=strong but overall=69.
- **MAJOR** `ALL` — fabrication_suppressed_pct high: fabrication_suppressed_pct=0.333 — inspect whether useful quote evidence is being suppressed too often.
- **MAJOR** `ALL` — improvements_4seg_compliant_pct is 0: All reports fail the expected 4-seg improvements audit; this is called out in v6 report as known unresolved.
- **MAJOR** `mock_interview_M14_2026_05_21` — trait recall missing on targeted persona: mock_interview_M14_2026_05_21 has 0 report.traits.
- **MAJOR** `workspace_P3_2026_05_20` — high overall with collapsed dimension: overall=82 but one dimension=30; may be a contradictory report.
- **MINOR** `ALL` — cohort anchor recall below 50%: has_cohort_anchor_pct=0.37
- **MINOR** `ALL` — rewrite demo recall below 60%: has_rewrite_demo_pct=0.519

## Persona Table

| persona | tier | overall | dim_avg | dim_min | dim_max | traits | transferability |
|---|---:|---:|---:|---:|---:|---:|---|
| mock_interview_M10_2026_05_20 | extreme | 54 | 53.8 | 38 | 75 | 1 | domain_match |
| mock_interview_M11_2026_05_21 | extreme | 60 | 60.3 | 30 | 75 | 1 | active_bridge |
| mock_interview_M12_2026_05_21 | extreme | 51 | 50.8 | 25 | 78 | 1 | domain_match |
| mock_interview_M13_2026_05_21 | strong | 58 | 58.3 | 30 | 85 | 2 | domain_match |
| mock_interview_M14_2026_05_21 | mid | 73 | 73.0 | 68 | 78 | 0 | domain_match |
| mock_interview_M15_2026_05_21 | mid | 87 | 87.7 | 84 | 92 | 2 | domain_match |
| mock_interview_M16_2026_05_21 | mid | 85 | 85.0 | 80 | 90 | 2 | domain_match |
| mock_interview_M1_2026_05_20 | mid | 66 | 65.5 | 50 | 75 | 2 | domain_match |
| mock_interview_M2_2026_05_20 | mid | 71 | 70.7 | 65 | 75 | 2 | domain_match |
| mock_interview_M3_2026_05_20 | mid | 63 | 61.7 | 55 | 65 | 2 | domain_match |
| mock_interview_M5_2026_05_20 | mid | 77 | 76.5 | 68 | 80 | 2 | domain_match |
| mock_interview_M6_2026_05_21 | weak | 53 | 53.2 | 42 | 62 | 1 | active_bridge |
| mock_interview_M7_2026_05_20 | mid | 69 | 68.7 | 65 | 72 | 2 | domain_match |
| mock_interview_M8_2026_05_21 | mid | 86 | 85.8 | 80 | 90 | 2 | domain_match |
| mock_interview_M9_2026_05_20 | extreme | 25 | 25.0 | 15 | 30 | 0 | domain_match |
| mock_interview_P_bridge_S1_2026_05_21 | strong | 78 | 78.7 | 72 | 85 | 2 | active_bridge |
| mock_interview_P_fake_S1_2026_05_21 | mid | 59 | 59.2 | 45 | 70 | 2 | domain_match |
| mock_interview_P_trait_S1_2026_05_21 | strong | 88 | 88.0 | 85 | 92 | 2 | domain_match |
| workspace_P1_2026_05_20 | strong | 69 | 68.8 | 65 | 73 | 3 | domain_match |
| workspace_P2_2026_05_20 | strong | 87 | 86.5 | 84 | 90 | 2 | domain_match |
| workspace_P3_2026_05_20 | mid | 82 | 72.7 | 30 | 90 | 3 | domain_match |
| workspace_P4_2026_05_20 | mid | 79 | 79.3 | 75 | 85 | 3 | domain_match |
| workspace_P5_2026_05_20 | strong | 85 | 85.0 | 82 | 87 | 2 | domain_match |
| workspace_P6_2026_05_20 | strong | 82 | 82.2 | 78 | 88 | 2 | domain_match |
| workspace_P7_2026_05_20 | mid | 86 | 86.3 | 80 | 90 | 2 | domain_match |
| workspace_P8_2026_05_21 | strong | 87 | 87.8 | 85 | 90 | 2 | domain_match |
| workspace_P9_2026_05_21 | strong | 88 | 88.2 | 80 | 94 | 2 | active_bridge |
