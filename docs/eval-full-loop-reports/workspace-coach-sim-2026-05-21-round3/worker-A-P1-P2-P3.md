# Round 3 Worker A — P1 P2 P3 (run 2026-05-21)

Backend: `http://127.0.0.1:8000` (healthy, dev VPS host=lavm-wlcndo6anm). Raw API responses in `/tmp/sim_worker_a_r3/`.

Sessions / user-keys (rand suffix `2de5414d`):
- P1 → session 112, `sim_P1_20260521r3_2de5414d` (中信证券 internship as focus)
- P2 → session 113, `sim_P2_20260521r3_2de5414d` (CICC TMT internship as focus)
- P3 → session 114, `sim_P3_20260521r3_2de5414d` (国海富兰克林 internship as focus)

## Batch-3 fix verification matrix

| Fix | P1 | P2 | P3 | Notes |
|---|---|---|---|---|
| #4 access log visible | ✓ | ✓ | ✓ | `[INFO|WARN] METHOD path → status (Xms)` format present for every request. Sample: `[INFO] POST /api/resume-copilot/sessions/112/plan/turn → 200 (9196ms)` / `[WARN] POST /api/resume-copilot/sessions/112/generate → 409 (16ms)` — note WARN auto-fires on 4xx. |
| #1 parser bullet count match | ✓ | ✓ | ✓ | P1 persona 4/5/4 → parsed 4/5/4. P2 persona 4/4 → parsed 4/4. P3 persona 4/4 → parsed 4/4. Persona's loose "做了一些数据整理和报告维护工作" bullet (P1 intern[0] b[3]) preserved as its own atom — round 1 Worker C's specific complaint resolved. |
| #3 X-Unknown-Tracks header | n/a | ✓ | n/a | PUT `["卖方研究 TMT (sell-side research)","this-is-bogus-track-xyz"]` → response header `x-unknown-tracks: this-is-bogus-track-xyz`. Chinese variant `["…","明显假的赛道名XYZ"]` → `x-unknown-tracks: %E6%98%8E%E6%98%BE%E5%81%87%E7%9A%84%E8%B5%9B%E9%81%93%E5%90%8DXYZ` (URL-encoded). Clean PUT (no bogus) → no header. Persisted track for `"卖方研究 TMT (sell-side research)"` canonicalized to `"卖方研究·S&T"`. |
| #2 coach min-turn floor | ✓ | ✓ | ✓ | Turn 1 with dense single-message evidence on all 3 personas → `status=clarifying`, `draft=None`, generated 1 `open_questions` entry (= ask). No draft/awaiting_review until turn 2+. P1 turn 2 with second evidence → flipped to `awaiting_review` with draft. P2/P3 stayed in `clarifying` at turn 2 (also acceptable, errs on more cautious). Critical check ("第 1 轮应该是 ask 不应是 write/awaiting_review") PASSED for all 3. |

### Evidence quick-lookup

**Fix #4 (access log) — `/tmp/backend_dev.log` excerpt:**
```
[INFO] POST /api/resume-copilot/sessions/112/plan/turn → 200 (2945ms)
[INFO] POST /api/resume-copilot/sessions/113/plan/start → 200 (33ms)
[INFO] PUT /api/resume-copilot/sessions/113/preferences → 200 (19ms)
[WARN] POST /api/resume-copilot/sessions/112/generate → 409 (16ms)
```

**Fix #1 (parser bullets) — `jq '[.profile.internships[] | {company, n: (.bullets|length)}]' /tmp/sim_worker_a_r3/P1_parsed.json`:**
```
P1 intern[0] 中信证券研究所 bullets=4 (persona 4)
P1 intern[1] 易方达基金     bullets=5 (persona 5)
P1 intern[2] 高瓴资本       bullets=4 (persona 4)
P2 intern[0] CICC研究部TMT  bullets=4 (persona 4)
P2 intern[1] 中信建投TMT    bullets=4 (persona 4)
P3 intern[0] 国海富兰克林   bullets=4 (persona 4)
P3 intern[1] 某中型私募    bullets=4 (persona 4)
```

**Fix #3 (header):**
- `/tmp/sim_worker_a_r3/P2_prefs_full.txt` → header `x-unknown-tracks: this-is-bogus-track-xyz`
- `/tmp/sim_worker_a_r3/P2_prefs_zh_bogus.txt` → header URL-encoded `%E6%98%8E%E6%98%BE%E5%81%87%E7%9A%84%E8%B5%9B%E9%81%93%E5%90%8DXYZ`
- `/tmp/sim_worker_a_r3/P2_prefs_clean.txt` → no header

**Fix #2 (min-turn floor):**
- `/tmp/sim_worker_a_r3/P1_turn1.json` — `status=clarifying`, `draft=None`, 1 open_question
- `/tmp/sim_worker_a_r3/P1_turn2.json` — `status=awaiting_review`, draft populated (after second evidence)
- `/tmp/sim_worker_a_r3/P2_turn1.json` / `P3_turn1.json` — both `status=clarifying`, `draft=None`, open_question generated

## Round 1/2 regression spot-check

- **B4 parser skills**: all 3 PASS, real technical terms preserved, no phantom `"C"`:
  - P1 technical: `['财务三张表勾稽与质量分析','DCF','DDM','相对估值','SOTP','单店模型','Python','pandas','numpy','scikit-learn','Airflow','SQL','PostgreSQL','SQLite','时间序列计量','VAR','VECM','协整检验','Bloomberg','Wind','Choice','Tushare','AKShare']`
  - P2 technical: `['Python','pandas','matplotlib','SQL','Wind API','Wind','Bloomberg','Choice','DCF']`
  - P3 technical: `['Python','pandas','numpy','pytorch','scikit-learn','LSTM','Transformer','GRU','财务三张表','DCF','相对估值','SQL','PostgreSQL','PyTorch','时序模型','Wind','Tushare','AKShare']`
  - `jq '.profile.skills.technical | any(. == "C")'` → false on all 3.
- **B3 canonicalize**: P2 sent `"卖方研究 TMT (sell-side research)"` → BE persisted `["卖方研究·S&T"]`. P1 sent `"二级买方·基本面 (公募行研)"` → `["二级买方·基本面"]`. P3 sent `"私募 / 资管基本面研究"` → `["二级买方·基本面"]`. All canonical, no zero-recs dead-end.
- **M1 中文 tag**: `grep -oE 'tech_unverified|overclaim|implausible_scale|vague_verb'` across all 6 turn JSONs → 0 hits. All open_questions / clarify text is fluent Chinese (e.g. P3 turn 1: `"你在这个项目中的具体角色是什么？...另外，预测装机量的效果如何，有没有具体的评估指标（如RMSE、MAPE）或业务影响？"`).

## Summary
- Total new bugs: **1** (a regression on R1 P3-3 — basic_info literal `"None"` re-surfaced for P3)
- Batch-3 fixes verified PASS: **4 / 4**
- Regressions on prior fixes: **yes — 1** (P3-3 re-broke)

## New bugs (only NEW)

### Bug R3-1: P3 `basic_info.{phone,github,linkedin,website}` regressed to literal string `"None"` [MINOR — regression of R1 P3-3]
- Persona: P3 only (P1 + P2 cleanly omit these keys)
- Step: 3 (parsed-profile)
- Endpoint: `GET /api/resume-copilot/sessions/114/parsed-profile`
- Expected (per Round 2 verified fix): missing contact fields should be omitted from `basic_info`, OR the value should be `null`. Round 2's worker-A report explicitly logged: "P3 `basic_info` has only `name/email/location/headline` keys — no phone/github/linkedin/website fields at all (cleanly omitted)."
- Actual (Round 3):
  ```json
  {
    "name": "陈昊",
    "email": "chen.hao.math@saif.sjtu.edu.cn",
    "phone": "None",
    "github": "None",
    "linkedin": "None",
    "website": "None",
    "location": "上海",
    "headline": "上交数学本 + SAIF MF / 跨专业转金融 / 目标私募基本面研究"
  }
  ```
- Reproduction: `jq '.profile.basic_info' /tmp/sim_worker_a_r3/P3_parsed.json`
- Note: This is the exact R1 P3-3 bug "literal None" that R2 confirmed fixed. Either the parser fix regressed between R2 and R3, or it was always non-deterministic and R2 just got lucky. FE will render "联系方式: None" or "GitHub: None" on the confirm chip.
- Severity: MINOR. Cosmetic but visible in the confirm-resume UI; the kind of "AI 套壳" detail SAIF graders specifically watch for.

## Round 1/2 bugs that still REPRO (carried forward — not in batch-3 fix list, just noted)

- **Bug P1-1 (parser company suffix)** — still partial. P1 internships still come back as `"中信证券研究所"`, `"易方达基金"`, `"高瓴资本"` with the `· 消费组` / `· 消费+大健康组` / `· 二级研究部` suffix relocated to the `role` field (`"消费组 · 研究助理实习生"`). Not strictly broken — the info is preserved, just moved. Worth a UX call: company chip will read "中信证券研究所" instead of "中信证券研究所 · 消费组".
- **Bug R2-3 (skills.tools slash-joined dump)** — still partial. Tools list now atomizes Bloomberg / Wind / Choice / Tushare / AKShare etc. cleanly, but on P1 + P2 + P3 the original slash-joined string also persists as a trailing entry, e.g.
  - P1: `"Bloomberg Terminal / Wind 资讯 (高级函数 + Wind API) / Choice 金融终端 / Tushare / AKShare / Tableau /"` (note trailing `/`)
  - P2: `"Bloomberg Terminal / Wind 资讯 / Choice 金融终端 / Excel/PPT 专家级"`
  - P3: `"Wind 资讯 / Tushare / AKShare / Jupyter Notebook (日常使用) / Excel/PPT"`
  - FE renders both: 工具栏会出现"Bloomberg Terminal"独立 chip + 一条长 slash chip. R2 bug R2-3 partially fixed, not closed.
- **R2-1 / P1-4 (current_item_id snaps to self_intro on finalize)** — not verified this round (we never reached a finalize on internship since cursor was at self_intro). Not in the batch-3 fix list. Carry forward.
- **R2-2 (matched_track_label echoes pref)** — not re-verified this round (recommendations need confirmed-profile, skipped per 12-min budget). Not in the batch-3 fix list. Carry forward.

## Spot-check evidence files (for QA replay)

```
/tmp/sim_worker_a_r3/
├── P1_session.json / P1_sid.txt        # session 112
├── P1_parsed.json                       # fix #1: bullets 4/5/4 match persona
├── P1_prefs.txt                         # B3: "二级买方·基本面 (公募行研)" → "二级买方·基本面"
├── P1_plan_start.json                   # status=awaiting_plan_approval
├── P1_plan_approve.json / approve2.json # status=clarifying
├── P1_plan_now.json                     # post-approve current_item self_intro
├── P1_turn1.json                        # fix #2: clarifying, draft=None, 1 open_q
├── P1_turn2.json                        # fix #2 progression: awaiting_review w/ draft after 2 evidence
├── P2_session.json / P2_sid.txt         # session 113
├── P2_parsed.json                       # fix #1: bullets 4/4 match
├── P2_prefs_full.txt                    # fix #3: x-unknown-tracks header (ASCII bogus)
├── P2_prefs_clean.txt                   # fix #3: no header on clean
├── P2_prefs_zh_bogus.txt                # fix #3: URL-encoded Chinese bogus
├── P2_plan_start.json / approve.json
├── P2_turn1.json / turn2.json           # fix #2: clarifying on both, no draft
├── P3_session.json / P3_sid.txt         # session 114
├── P3_parsed.json                       # fix #1 PASS; R3-1 regression on basic_info
├── P3_prefs.txt                         # B3: "私募 / 资管基本面研究" → "二级买方·基本面"
├── P3_plan_start.json / approve.json
└── P3_turn1.json / turn2.json           # fix #2: clarifying on both
```
