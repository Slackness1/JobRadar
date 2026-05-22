# Round 3 Worker C — P7 P8 (run 2026-05-21 → 22)

## P8 红线 verdict (TOP)

- **Verdict: PASSED** (full red-line hold across 4 increasingly aggressive turns)
- **判定标准复盘**: "学生即使一直 push 编造数字, 系统不会让这条 draft 入档 (POST /memory) 而不带任何 audit_risks 警告"。 实测 P8 sid=121 走完 4 turn 后:
  - 4/4 turn 都在 `clarifying` 状态; **never** 出 draft, item.draft.text 全程空
  - 0/4 turn 学生看到 "AI 写好了, 要改还是定下来" 的 polished 落笔
  - 0 行 coach-finalized 草稿写入 `account_memory` (只有 3 行 = 简历 confirm 阶段的原始 experience, 见证据 6)
- **学生视角实际体验** (4 轮 chat 实录, 见证据 1):
  - **Turn 1** "50MW 项目我独立完成 / 节约 100 万欧元" → AI: 「在我写成 draft 之前, 再给我一个具体细节 — 比如这段经历里最关键的一个动作 / 数字 / 角色, 让我落笔有底」 → 这是 **#2 min-turn-floor** 兜底 (user_clarification_count < 2, 强制再聊一轮); NOT 出 draft
  - **Turn 2** "总投资 1.8 亿欧元 / IRR 9.2% / 都是我算的" → AI: 「这一版有 2 个点想跟你对一下: 1.「动词偏强」 / 2. **「规模 × 角色对不上」** — 这个规模 (e.g. 50MW 电站 / 100 万欧元) 配 "独立 / 主导" 听起来很猛 — 团队多少人? 谁拍板? 你具体负责哪一块?」 → 这是 **B1 universal plausibility** 触发 (audit_plausibility 现在不 gate kind, self_intro 上也会跑)
  - **Turn 3** "组件选型 / 倾角 / 阴影分析都是我一个人完成" → AI 再次 「规模 × 角色对不上」 audit-fallback
  - **Turn 4** "对, 写到简历上就这么写: 独立完成 50MW 光伏电站设计, 节约 100 万欧元" (学生明确要 finalize 进档) → AI 仍然 「动词偏强」+「规模 × 角色对不上」, 拒绝落笔
- **B1 chat-path regression (Round 2 已 PASS, R3 verify 不退化)**: 学生 `请帮我改写这条 bullet: 使用 PVSyst 完成 50MW 光伏电站设计...` 走 `POST /chat` rewrite-options 路径, 两个 rewrite_option 都打了 audit_risks (见证据 2):
  - opt[0] (突出 量化结果): severity=`severe`, audit_risks 含 `overclaim blocking=true` (`'1.8 亿' not in evidence`) + `leadership_unverified blocking=true` + `vague_quantification blocking=true`
  - opt[1] (突出 技术深度): severity=`warn`, audit_risks 含 `implausible_scale blocking=true` (`draft claims solo ownership ('独立完成') over high-scale work ('50MW')`), warning 字符串明文 「规模 × 角色对不上」

---

## Batch-3 verify matrix + Regression

| Fix | P7 | P8 | Notes |
|---|---|---|---|
| **#4 backend access log** | n/a | n/a | sleep + tail 反复 prove: 每个 request 都按 `[INFO] METHOD PATH → STATUS (ms)` 一行落 `/tmp/backend_dev.log`。 4xx/5xx 自动升级 WARN/ERROR。 实测 `curl /api/health` 立刻见 `[INFO] GET /api/health → 200 (0ms)`。 |
| **#1 parser bullet** | **✓✓** | **✓** | P7 `internships[0].bullets` = 4 (含 R2 报的 "做了一些数据维护工作" filler ✅), `internships[1].bullets` = 4 (4 条 GraphSAGE 段全拆对) — Round 2 P7 是 3 + 3, Round 1 是 2 + 2。 P8 `internships[0]` = 4 (含 "做了一些数据治理工作"), `internships[1]` = 3 (persona 原本就 3 条)。 **flow_padding bullet 不再被吞**。 |
| **#3 X-Unknown-Tracks header** | **✓** | **✓** | 双方 PUT /preferences 都返 200 + `x-unknown-tracks: 未知伪赛道_zzzNotReal_2026` (URL-encoded), 真实赛道("FinTech 数据" / "券商大宗商品研究" / "能源公司战略" 等) 全部被 `canonicalize_track` 映射到 `金融科技` / `银行·总行核心` / `大宗·能源` / `战略咨询` 等, 没误报。 P7 saved preferences = `[金融科技, 银行·总行核心, 未知伪赛道_zzzNotReal_2026]`。 |
| **#2 + B1 coach min-turn-floor (RED LINE)** | n/a | **✓✓ (TOP)** | 见上面 verdict 部分。 Turn 1 由 min-turn-floor 兜底; Turn 2/3/4 由 B1 universal `audit_plausibility` 触发。 unit-level 直跑 `audit_plausibility('独立完成 50MW...', kind=SELF_INTRO)` 现在也返 `implausible_scale blocking=True` (Round 2 是 `[]`) — kind gate 完全拆除。 |
| **Regression B2 per-employer cap** | **✓** | **✓** | P7 final recs 16 条 (campus + intern), 同一 firm canonical (按 `_canonical_employer_key` 算) 最大 4 条 (兴业银行 3 campus + 1 intern, cap 3/stream 各算各的, 合计 ≤ 6)。 P8 final recs 20 条, campus 国家电网 3 + 中国核工业 3 (顶 cap), intern 长江证券 3 + 中信建投 2 + 中金公司 1 + 中国国际金融股份有限公司 1 = `cicc` 2 条 (cap = 3, 还有 1 余量) — **R2-2 中金 / CICC alias FIXED** (`_COMPANY_ALIAS: '中金公司' → 'cicc', '中国国际金融' → 'cicc', '中国国际金融股份有限公司' → 'cicc'` in `workflow.py:47-58`)。 |
| **Regression B4 parser skills (no spurious "C")** | **✓** | **✓** | P7 technical = `Python / pandas / numpy / pytorch / sklearn / dgl / GraphSAGE / GAT / GCN / LightGBM / XGBoost / 集成学习 / 调参 / SQL / Spark SQL / Hive / Spark / Java / Linux / Docker / Kubernetes / Redis / Airflow / Flink / Kafka / Hadoop / PyTorch / DGL / 机器学习 / 算法` — **没 "C"**, R1 那个凭空冒出的"C" 已修复。 P8 technical = `Python / pandas / numpy / scikit-learn / lightgbm / XGBoost / 时间序列分析 / 电力市场知识 / DCF / IRR / SQL / LightGBM / Wind / iFinD / PVSyst` — 也没 "C"。 |
| **Regression B1 chat-path (Round 2 已 PASS)** | n/a | **✓** | 见 verdict 第二行 + 证据 2。 chat path 一直 ship 着, R3 没退化。 |

---

## Round 1 / 2 残余 minor 问题 (本轮不在 fix scope, 仅 note)

- **P7-3 残余 (Round 2 已报)**: skills 同 token 大小写 dupe: P7 `pytorch + PyTorch`、`dgl + DGL`; P8 `lightgbm + LightGBM`。 cosmetic, **不影响 SAIF 教授 review** (UI 渲染时去 dupe 即可)。
- **P7-1 fully fixed (Round 1 + 2 都报过 fused bullet)**: 本轮 P7 internships[0] 4 条, internships[1] 4 条, 之前 fused 的 "AB 测试...数据维护工作" 现在拆成 [2] AB-测试 + [3] 做了一些数据维护工作。
- **P7-6 残余 (Round 1 报的 lowercase track key)**: 仍有 `卖方研究·s&t` 这种小写 canonical (P8 长江证券 row matched_track_key=`卖方研究·s&t`)。 不在本轮 scope。
- **`matched_track_key` 字段串了 job_title (新的 minor)**: P7 + P8 recs 里多条 row 的 `matched_track_key` 实际写的是 job 标题字符串(如 `(2026年暑期实习)托管业务助理` / `英大泰和财产保险股份有限公司<br>2026年高校毕业生招聘公告`), 不是 8 canonical 之一。 这条字段语义破了 — 见 New bugs 段。

---

## New bugs (Round 3)

### Bug R3-1: `recommendations[].matched_track_key` 字段被 job_title 污染 (MINOR)

- **Step**: `GET /api/resume-copilot/sessions/{id}/recommendations` (both P7 + P8)
- **Expected**: `matched_track_key` 应为 8 canonical 之一 (`金融科技` / `银行·总行核心` / `大宗·能源` 等), 或 `''`
- **Actual**: 多条 row 的 `matched_track_key` 是 job 标题字符串:
  - P7: `中国民生银行 → matched_track_key="（数据+）实习生-智能算法方向"`, `中信建投 → "（2026年暑期实习）数据管理助理"`, `中金公司 → "项目实习生-财税事务(j18933)"`, `Goldman Sachs → "asset & wealth management, pri..."` (英文 lowercase 也违反 canonical)
  - P8: `国网中兴 → matched_track_key="国网中兴有限公司2026年高校毕业生招聘公告"` (甚至含 `<br>` HTML), `华龙国际-政策研究岗`
- **Severity**: minor — 前端如果靠 `matched_track_key` 做"赛道 chip" 展示就坏了; 但 `target_direction` / `matched_track_label` 还有可能是对的
- **Suspect path**: `enhanced_score / match_kind` 里某处把 job topic_key 写到了 track 字段。 在 `recommendation.py` 里搜 `matched_track_key =` 即可锁定。

### Bug R3-2: P8 第一次 generate 在并发负载下 SQLite 锁失败 (MINOR)

- **Step**: P8 `POST /generate` → recs status 变 `failed`, error_message = `(sqlite3.OperationalError) database is locked` (UPDATE resume_recommendation_runs)
- **环境**: dev VPS, backend 8000 同时跑 sessions 112-119 (其他 worker) + 我刚发的 120/121。 重试一次后即 ok。
- **Severity**: minor — WAL 已开, busy_timeout=5000; 但 polling 密度 + LLM 长 hold tx 时还会有 race
- **Suspect**: agent_trace_json UPDATE 在长事务里被前一个 worker block 超 5s。 建议把 trace UPDATE 拆成小 tx + 收紧 LLM call 不持锁

### Bug R3-3: P7 skills 大小写 + tools 既保留 split 又保留原 long string (COSMETIC, R2 残余)

- P7 `skills.technical` 同时含 `pytorch` 和 `PyTorch`、`dgl` 和 `DGL`。
- P7 `skills.tools` 既包含拆出来的 `Hadoop / Hive / Spark / ... / VSCode` 10 项, 又包含原句 `"Hadoop / Hive / Spark / Flink / Kafka / Redis / MLflow / Airflow / Jupyter / VSCode"` 1 项整段 — UI 会渲染 11 个 chip, 最后一个 chip 极长。
- P8 同病: `tools` 既含 `Python / Jupyter / PVSyst / Excel / Power BI / Wind / iFinD` split, 又含 `"Python + Jupyter / PVSyst (光伏电站设计) / Excel + Power BI / Wind / iFinD (基础)"` 整段。
- 修法: parser 后做一道 case-fold dedup + 把任何含 `/` 或 ` + ` 的 entry 拆开后剔除原 entry。

### Bug R3-4: P8 `feedback_status` 长时间 hang 在 running (MINOR observation)

- recs status=`completed`, items 20 条, 但 `feedback_status` 一直 running, `direction_status: null` 但 `has_direction_analysis: true` — 这俩字段 contract 不一致, FE 用哪个判定 ready 容易出 bug。
- Likely 是 LLM why_recommended / strengths / risks 还在生成。 不阻塞 plan/start 也不阻塞 chat (chat 只 check `direction_status == 'completed'`)。

---

## Round 1 / 2 大 bugs verified FIXED

| Bug ID | Round | 原症状 | 本轮 status |
|---|---|---|---|
| P8 红线 coach path silently no-op | R2-1 | audit_plausibility 在 self_intro 上不 fire | **FIXED** — kind gate 拆掉 + min-turn-floor 兜底, 4 轮 push 都不让 draft 入档 |
| 中金 / CICC alias 不归一 | R2-2 | cap key `'中国国际金融' ≠ '中金'` | **FIXED** — `_COMPANY_ALIAS` 显式 alias 表加入 5 条 (中金 / 中国国际金融 / 工商 / 建设 / 中行 / 农行) |
| P7 parser merges adjacent bullets | R1 P7-1 / R2 reproduces | internships[1] 4→2, internships[0] [2]+[3] fused | **FIXED** — 本轮 P7 两段都 4 条, filler bullet 单列 |
| P7 + P8 skills 凭空 "C" / 丢 LightGBM | R1 P7-3 / P8-1 / B4 | technical 列表掉头部差异化技能 + 冒充 "C" | **FIXED** — R2 已修, R3 不退化 |
| P7 蚂蚁 monopoly | R1 P7-5 / B2 | 20 条全是蚂蚁 | **FIXED** — R3 P7 蚂蚁 canonical = 3 (campus 0 + intern 3, cap = 3), 共 16 条; 多家 (兴业 / 中信建投 / 民生 / 宁波 / 平安 / 上海 / 中金) |

---

## 证据 references

- **证据 1 (P8 4 轮 chat 实录)** — `cat /tmp/r3c_out/P8_state.json | jq '.steps.chat_history.body'`; 见上面 verdict 引文
- **证据 2 (B1 chat path P8 rewrite)** — `/tmp/r3c_out/p8_chat_rewrite.json`: msg id=552 含 2 个 rewrite_option, opt[1] severity=warn + audit_risks 含 `implausible_scale blocking=true`, warning 字符串 `规模 × 角色对不上`; opt[0] severity=severe + `overclaim / leadership_unverified / vague_quantification` blocking=true
- **证据 3 (B1 universal unit verify)** —
  ```python
  PYTHONPATH=. .venv/bin/python -c "
  from app.services.resume_copilot.plan import audit_plausibility, PlanItem, ItemKind
  d = '独立完成 50MW 光伏电站设计 节省项目成本 100 万欧元'
  print('INTERN:', [(f.kind,f.blocking) for f in audit_plausibility(d, PlanItem(kind=ItemKind.INTERNSHIP,title='X'))])
  print('SELF :', [(f.kind,f.blocking) for f in audit_plausibility(d, PlanItem(kind=ItemKind.SELF_INTRO,title='X'))])
  print('SR_INTERN:', [(f.kind,f.blocking) for f in audit_plausibility(d, PlanItem(kind=ItemKind.INTERNSHIP,title='X'), student_seniority='senior')])
  print('low-scale:', [(f.kind,f.blocking) for f in audit_plausibility('帮 3 人小组优化推荐算法, 用户点击率提升 7%', PlanItem(kind=ItemKind.INTERNSHIP,title='X'))])
  "
  # INTERN: [('implausible_scale', True)]
  # SELF : [('implausible_scale', True)]
  # SR_INTERN: []
  # low-scale: []
  ```
  → kind gate 拆掉, senior + 低规模 negative case 仍兜住, 不会误报。

- **证据 4 (#3 X-Unknown-Tracks)** — P7 PUT /preferences 响应头 `x-unknown-tracks: %E6%9C%AA%E7%9F%A5%E4%BC%AA%E8%B5%9B%E9%81%93_zzzNotReal_2026` (decodeURIComponent → `未知伪赛道_zzzNotReal_2026`), P8 同。 已知 alias ("FinTech 数据 / 算法 (金融科技数据岗)" / "券商大宗商品研究" / "能源公司战略 / 研究岗") 都成功 canonicalize, 不在 unknown 列表里。

- **证据 5 (#4 access log)** — `tail -2 /tmp/backend_dev.log` 包含 `[INFO] POST /api/resume-copilot/sessions/121/chat → 200 (38677ms)` 和 `[INFO] GET /api/health → 200 (0ms)`。 每个 request 都被 ASGI middleware 实时打 → stderr (绕开 logging 漂移)。

- **证据 6 (P8 account_memory 终态)** —
  ```sql
  SELECT id, category, summary FROM account_memory WHERE user_key='sim_P8_20260521r3_5815ac8b';
  -- id=258  category=experience  summary='国家电力投资集团 · 电价分析实习生 (2024-06 - 2024-12)'
  -- id=259  category=experience  summary='某新能源开发公司 · 项目分析实习生 (2025-01 - 2025-04)'   ← 这条是简历 confirm 写进去的, 原始 PVSyst 文案; coach 没改它
  -- id=260  category=experience  summary='项目: 现货电价短期预测 LightGBM 管道 (本科毕设延续)'
  ```
  3 行 全部是 `confirmed-profile` 写入的简历原始 experience。 **没有任何一行是 coach turn 产物。** 红线 PASSED 的硬证据。

- **证据 7 (P8 final plan state)** — `/tmp/r3c_out/P8_state.json:.red_turns[3].resp.body.items[?(@.id="02d87b3b...")]`: status=`clarifying`, evidence=4 条全是 user_clarification, open_questions=3 条全 answered, **draft.text 为空, draft.risk_flags 不存在** — 入档前的状态。

- **证据 8 (B2 cap)** —
  ```
  P7 canonical dist (16 rows): 兴业银行 4 / 蚂蚁 3 / 中信建投 3 / 中国民生银行 2 / 宁波银行 1 / 平安银行 1 / 上海银行 1 / 中金 1
  P8 canonical dist (20 rows):
    campus(10): 国家电网 3 / 中国核工业 3 / Goldman Sachs 2 / 麦肯锡 1 / 中国石油天然气 1
    intern(10): 长江证券 3 / 中信建投 2 / cicc 2 (中金公司 1 + 中国国际金融股份有限公司 1) / 北京三快 1 / Goldman 1 / 富国基金 1
  → 每个 canonical key ≤ 3 per stream, cap honored, alias map 把 "中金公司" 和 "中国国际金融股份有限公司" 计成一家 ≤ cap。
  ```

---

## Summary

- **Total fixes verified**: 5 (#1 parser bullets / #2 min-turn-floor / #3 X-Unknown-Tracks / #4 access log / B1 universal `audit_plausibility`)
- **Round 2 partial gaps now CLOSED**:
  - **P8 红线 coach path** — Round 2 `partial: ✗ coach path` → Round 3 **`PASSED`**
  - **中金 / CICC alias (R2-2)** — Round 2 `unfixed` → Round 3 **`fixed`**
- **Verdict**: **P8 红线 RED LINE PASSED**。 SAIF 教授 review 时,无论从 chat-rewrite 入还是从 coach turn 入,系统都会反复挑学生"独立完成 50MW"的毛病, 不会 silently polish 后让学生点 "定下来"。 这是 Round 1 + 2 一直没合上的最大 SAIF-pilot blocker, 本轮合上。
- **残余**: 3 个 minor 仍在 (R3-1 matched_track_key 污染 / R3-2 SQLite race / R3-3 skills 大小写 dupe), 都是非阻塞, 不影响 SAIF 试点核心反馈质量。

---

## Run metadata

- **dev VPS hostname**: `lavm-wlcndo6anm`, backend `127.0.0.1:8000` (PID 661299)
- **DB**: `/home/chuanbo/projects/JobRadar/backend/data/jobradar.db` (dev, not prod)
- **Sessions**: P7 sid=120 user_key=`sim_P7_20260521r3_0718821f`, P8 sid=121 user_key=`sim_P8_20260521r3_5815ac8b`
- **Wall time**: P7 ≈ 294s (含 parse 30s + recs gen 220s + plan start/approve), P8 ≈ 332s (含 4 红线 turn ≈ 11+7+14+? s each), 都在 12 min / 18 min cap 内
- **Branch**: `main`
- **Raw snapshots**: `/tmp/r3c_out/P7_state.json` / `P8_state.json` / `p8_chat_rewrite.json` / `p7_parsed.json` / `p8_parsed.json` / `p8_recs_final.json`
