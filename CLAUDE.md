# CLAUDE.md

Guidance for Claude Code working in this repo.

## What this project is

**JobRadar** — campus-recruitment tracking tool for the Chinese job market. Three runtimes:

| Runtime | Root | Port | Purpose |
|---|---|---|---|
| Backend API | `backend/` | 8000 (dev) / 8002 (resume-copilot docker) | FastAPI + SQLite, all data logic |
| Frontend (job browser) | `frontend/` | 5173 | Vite + React, job search/scoring/intel UI |
| Resume Copilot Web | `resume-copilot-web/` | 3001 | Next.js, resume upload → parse → recommend / interview |

The frontend and resume-copilot-web are separate apps that both proxy `/api/*` to the same backend. Never served together in dev.

---

## Commands

### Backend
```bash
cd backend && pip install -r requirements.txt
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Tests
cd backend && PYTHONPATH=. .venv/bin/pytest tests/
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_sites_router.py -x
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_sites_router.py::test_name -x
```

### Frontend (Vite + React job browser)
```bash
cd frontend && npm install
npm run dev      # port 5173
npm run lint
npm run build    # tsc + vite build
npm test         # vitest
```

### Resume Copilot Web (Next.js)
```bash
cd resume-copilot-web && npm install
npm run dev      # port 3001
npm run lint     # must pass with 0 errors before shipping
npm run build    # next build
```

### Docker (backend + frontend together)
```bash
docker compose up --build   # backend → :8001, frontend → :5173
```

---

## Architecture

### Backend (`backend/app/`)

**Entry point** — `main.py` lifespan: create tables → `ensure_compatible_schema()` (legacy DDL patcher) → `alembic upgrade head` → seed YAML configs → `ensure_demo_session(db)` → start APScheduler (3 daily jobs, see Sites monitor below + hourly guest cleanup).

**Routers** (`app/routers/`): `jobs`, `tracks`, `scoring`, `exclude`, `crawl`, `export`, `scheduler`, `system_config`, `company_recrawl`, `job_intel`, `resume_copilot`, `interview`, `sites`, `coverage`, `review_queue`, `system_health`, `teacher_entry`.

**Database** — SQLite at `backend/data/jobradar.db`. WAL + `busy_timeout=5000` set via SQLAlchemy `@event.listens_for(engine, 'connect')`. Models in `app/models.py`. Schema evolves via Alembic (`backend/alembic/versions/`); legacy `app/services/schema_patch.py` still runs at startup as a safety net. To add a migration: `cd backend && PYTHONPATH=. .venv/bin/alembic revision --autogenerate -m "<name>"`.

**Resume Copilot pipeline** (`app/services/resume_copilot/`):
- `workflow.py` — two async-safe workflows (`run_resume_parse_workflow`, `run_resume_generate_workflow`) dispatched via FastAPI `BackgroundTasks`; each opens its own `SessionLocal`.
- `parser.py` / `ingest.py` — LLM-extract structured profile from PDF text (heuristic fallback on HTTP error). `extract_resume_text_with_page_count(bytes) -> (text, page_count)` is the canonical PDF helper; `POST /sessions` returns `page_count` + `file_size_bytes` so the upload UI shows real numbers.
- `recommendation.py` — pre-filters jobs by preferences/track, scores via `compute_rule_score`, optional `JobIntelSnapshot` boost (14-day TTL), LLM reranks top-N.
- `quick_enrichment.py` — parallel web search + page extraction for top-N via `ThreadPoolExecutor`. Trace events collected thread-locally and replayed on main thread (avoids concurrent SQLite writes).
- `feedback.py` — LLM resume diagnostics + rewrite suggestions.
- `agent/` — ReAct loop powering the "代理思考中" trace. `tools.py`: 4 callables (`search_candidates`, `inspect_jobs`, `get_company_intel`, `search_web`). `core.py`: adds `finalize` + `BUDGET_EXHAUSTED` short-circuit (driven by `budget.py`).
- `direction_analysis.py` — LLM produces 3-tier labels (强匹配 / 可迁移 / 有差距); `tier_label` enum enforced, falls back to `'强匹配'` on parse failure.
- `chat.py` — `/chat` turn handler. **Rewrite contract is strict**: `rewrite_options` length must be 2 and both options share `field_path`, `target_title`, `original` (two writeups for the *same* spot). `field_path` is dot-notation (e.g. `internships.0.bullets`); `_traverse_and_set` applies the chosen option via `POST /chat/apply-rewrite`.
- `demo_session.py` — `DEMO_SESSION_ID = 1` + `ensure_demo_session(db)`. Seeds a fully-prepared shared session with `user_key='__demo__'`, status `completed`, pre-computed recommendations + direction analysis + 3 chat messages. Lifespan force-updates `user_key='__demo__'` on every startup so the read-only guard catches the row.

**Demo session read-only guard** — `_assert_not_demo(session)` in `routers/resume_copilot.py` checks `session.user_key == '__demo__'` (not session_id, so tests using id=1 with a different user_key pass). Mounted on every write endpoint (PATCH/DELETE session, PUT confirmed-profile, PUT preferences, POST generate, POST chat, POST chat/apply-rewrite, POST plan/*). Must be called **after** `_get_session_or_404`. All `GET` endpoints unaffected.

**Plan-mode resume building** (2026-05-13, `app/services/resume_copilot/{plan,plan_turn,plan_sync,tag_extractor}.py` + `agent/builder.py`):

A second, independent path parallel to `parse → confirm → generate_recommendations`. Plan-mode tackles *resume writing* — one bullet at a time, evidence-gated, structurally reverse-hallucinated. Two URLs/UIs stay separate, but a **one-way bridge** mirrors finalized plan content back into `ResumeConfirmedProfile.profile_json` so the next `/generate` picks up the better-written bullets. Migrations: `0003_session_plan_json` (plan_json + plan_status), `0004_recommendations_stale` (stale flag).

- `plan.py` — pure data + state machine, no DB no LLM. `PlanStatus` × `ItemStatus` enums + transition table + `apply_action`. `audit_draft` is the reverse-hallucination gate: any concrete number / tech stack / leadership verb in a draft must trace back to an `EvidenceTag` (`metric` / `tech` / `scope` / `role` / `verb_subject`); blocking flags reject the write at the data layer.
- `tag_extractor.py` — regex extraction of evidence tags, feeds `audit_draft`.
- `agent/builder.py` — one LLM call → one `AgentAction` (5 actions: `ask` / `ready_to_write` / `write` / `drop` / `block`). Pydantic-validated, 1 retry on `ValidationError` then falls back to `ask`. Audit failure inside `write` is auto-converted to `ask` so users never see the audit exception.
- `plan_turn.py` — turn handler wiring `agent/builder` → `apply_action` → persist. Initial plan built deterministically from a YAML template + `parsed_counts` (零 LLM 零 hallucination).
- `plan_sync.py` — one-way bridge into legacy recommendation flow. After every `apply_action` that newly transitions any item to `FINALIZED`, both call sites (`run_plan_turn` and the raw `/plan/actions` endpoint via `_maybe_sync_plan_to_profile` helper) call `sync_plan_to_profile(plan, profile) -> profile`. Mapping: SELF_INTRO → `candidate_summary`, EDUCATION[i] → `education[i].highlights`, INTERNSHIP[i]/PROJECT[i] → `internships[i]/projects[i].bullets` (collected from FINALIZED children sorted by `order`). SKILL/AWARD/CAMPUS_ACTIVITY skipped in v1 (profile schema mismatch). Side effects: writes `ResumeConfirmedProfile.profile_json` + flips `session.recommendations_stale = 1`. `/generate` clears the flag. Workspace shows a yellow banner; the "重新推荐" button calls `regenerateFromSyncedProfile` (skips `putConfirmedProfile` to avoid clobbering synced bullets with React's parsed-profile state).
- **Routes**: `POST/GET /sessions/{id}/plan/start|""|approve|turn|actions` — all gated by owner check + demo guard.
- **Tests**: 90 tests across `test_resume_plan{,_builder,_router,_turn,_sync}.py`; tag extractor lives in `test_resume_tag_extractor.py`. `backend/scripts/smoke_plan_turn.py` is a real-LLM smoke (DeepSeek).

**Mock Interview pipeline** (`app/services/interview/`, `app/routers/interview.py`):
- **LLM** — `llm.py:stream_interview_turn` yields raw SSE lines from the resume-copilot LLM (DeepSeek). Per-read socket timeout bumped to **120s** (reasoning models can pause >30s; default 30s aborts mid-thought and freezes UI in "思考中").
- **Reports** — `report.py` generates the post-interview report (overall + per-dimension scores + recommendations) by re-prompting with full transcript.
- **Voice stack** (DashScope, replaced Aliyun NLS in commits `4615a9e` / `7d2f8d2`):
  - **TTS** (`voice/tts.py`) — dispatches by `DASHSCOPE_TTS_MODEL`: `qwen3-tts-*` uses HTTP REST (POST → OSS WAV URL → stream); `cosyvoice-*` uses WebSocket duplex. Default voice `longyingtian` ("温柔甜美女", CosyVoice v2). Voice list: <https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list>.
  - **ASR** (`voice/asr.py`) — `paraformer-realtime-v2` proxied through `/api/interview/asr` WebSocket; client sends PCM16 16kHz mono frames.
  - **Avatar** (`voice/avatar.py`) — Aliyun Lingmou (灵眸) wired (`POST /api/interview/avatar/session`) but **not rendered** — the design uses a static AI orb instead. Code retained for re-enablement. Uses Aliyun **V3 signature** (ACS3-HMAC-SHA256, header-based) on `POST /openapi/chat/init/{projectId}?platform=Web&instanceId=...`. `platform` MUST be `Web` (not `webSDK`); `id` is path-param.
- **Endpoints**: `POST /turn` (SSE, error events wrap transport failures as `data: {"error": ..., "type": ...}`), `POST /report`, `POST /tts`, `WS /asr`, `POST /avatar/session` (dormant), `GET /reports[/{id}]` (filtered by `X-Resume-User-Key`).

**Config** (`app/config.py`) — reads `.env.local` from `backend/`, then root, then OS env. Key groups:
- `RESUME_COPILOT_*` — LLM base URL, key, model, timeouts.
- `TAVILY_API_KEY`, `FIRECRAWL_API_KEY`, `JINA_API_KEY`, `BRAVE_SEARCH_API_KEY` — enrichment search.
- `TATA_USERNAME` / `TATA_PASSWORD` — crawler credentials.
- `DASHSCOPE_API_KEY` + `DASHSCOPE_TTS_MODEL` + `DASHSCOPE_TTS_VOICE` + `DASHSCOPE_ASR_MODEL` — voice stack (defaults in `## Environment setup` template below).
- `ALIYUN_ACCESS_KEY_ID/SECRET` + `AVATAR_PROJECT_ID` + `AVATAR_INSTANCE_ID` — Lingmou (currently dormant).
- `ALERT_STALE_DAYS` — sites-monitor staleness threshold (default 3 days).
- `CRAWLER_LLM_*` — DeepSeek V4 client (FLASH_MODEL / PRO_MODEL / TIMEOUT_SECONDS) for crawler enrich/diagnose/digest. Three feature flags default OFF: `CRAWLER_LLM_{ENRICH,DIAGNOSE,DIGEST}_ENABLED`.

**Sites monitor** (`app/routers/sites.py` + `app/services/{company_crawl_logger,sites_alert,company_crawler_registry}.py`):

> **Cron schedule** — three daily APScheduler jobs (CST):
> - **08:00** — `_daily_crawl_job` runs `run_crawl()` (Tata + Haitou + recrawl-queue). ~5 min.
> - **09:00** — `_daily_tier_crawl_job` runs the tier orchestrators sequentially with per-block error isolation. ~30-40 min, Playwright-heavy. Parent `CrawlLog row.source='tier-crawl'` aggregates the run. **10 blocks (Phase order)**: `internet → state_owned → securities → consumer_foreign → insurance (P6) → funds (P6) → pe_vc (P7) → hedge_funds (P9) → foreign_ibs (P10) → consumer_foreign_workday (P13, 阿斯利康)`. foreign_ibs alone ~4.5 min (Citi+MS via Workday `searchText` filter).
> - **09:35** — `_daily_digest_job` runs LLM digest (V4-Flash) over today's `company_crawl_logs`; gated by `CRAWLER_LLM_DIGEST_ENABLED`. Persisted to `system_config[key='sites_daily_digest']`, served via `GET /api/sites/digest`.

- Table `company_crawl_logs` — per-company run record, parent-linked to `crawl_logs.id`. `suggested_fix` column holds optional LLM-3 markdown diagnosis.
- New `jobs` columns: `track_predicted` (LLM-classified) + `quality_label` (good/agency/spam/low_signal). Filled by `crawler_llm_enrich.enrich_jobs_parallel` when `CRAWLER_LLM_ENRICH_ENABLED=1`.
- `company_crawl_log(db, source=, company=, parent_log_id=)` context manager wraps each per-target call. On exception: marks row `failed`, truncates `error_message` to 500 chars, optionally schedules daemon-thread LLM-3 diagnosis (V4-Pro, gated by `CRAWLER_LLM_DIAGNOSE_ENABLED`), re-raises. For orchestrators whose inner except swallows exceptions (state_owned / consumer_foreign / internet), the wrap uses a `target_exc` sentinel to re-raise across the swallow boundary.
- Out of scope: `energy_crawler.py` is CLI-only (not in cron). `crawl_antgroup` flows through `crawl_internet_targets` so it's covered transitively.
- 5 endpoints under `/api/sites/*`: `GET /summary`, `GET /?source=`, `GET /{company}/runs?limit=`, `POST /{company}/recrawl`, `GET /digest`. Recrawl validates against `COMPANY_CRAWLERS` registry (16 internet t1 companies; 网易雷火 omitted because `build_internet_targets()` doesn't return targets for it), schedules a fresh `SessionLocal` background task. Scoring on `new_count > 0` is non-fatal.
- `alert_level(runs, now)` (pure): empty=`unknown`; last+prev failed=`red`; last failed alone=`yellow`; last success + no new in `ALERT_STALE_DAYS`=`yellow`; else `green`.
- `_shanghai_today_start()` returns Asia/Shanghai today 00:00 as naive UTC. Fixed +08:00 offset (no DST).
- `_build_site_rows` is N+1 by design (~2N+1 queries per `/api/sites` call). Acceptable at ~30 companies; revisit past ~50.
- **UI** (`frontend/src/pages/Sites.tsx` + `components/sites/*` + `styles/{hifi-tokens,sites-theme}.css`): scoped via `<div className="hf" data-theme="sites">`. Adaptive polling (8s default, 2s during recrawl). Source→group bucketing onto 4 visible categories (互联网官网 / 券商 / 国央企 / 消费外企). 41 vitest unit + integration tests. **`/sites` is no longer in the sidebar** (replaced by `/system-health` which embeds the company table) — route + endpoints stay live for direct linking.

**Coverage dashboard** (`app/routers/coverage.py` + `frontend/src/pages/Coverage.tsx` + `components/CoverageStarmap.tsx`): `/coverage` route. Reads `backend/config/coverage_truth.yaml` (truth table of T1 companies per track) and joins with `company_crawl_logs` last-N-day data. **13 tracks**: internet / banks (T0+T1) / insurance / securities T1 / 公募基金 / PE/VC / 消费外企 / 国央企 / hedge_funds / foreign_ibs / asset_mgmt / trust / futures.

Three track modes:
- `enumerate` — explicit T1 list with `aliases` + `deferred_reason`. Active = company in `company_crawl_logs` with `fetched_count > 0` in last 7 days.
- `absolute` — no T1 list, top-N actives. Used by 国央企 (~119 firms).
- `derived_company` — query `jobs` directly by company-name keyword (e.g. `LIKE '%理财%'`). Used by 资管 / 信托 / 期货 — those subsidiaries get captured by parent group portals. `window_days` default 30 (lag tolerance).

**`jobs_company_match` second-level lookup** (2026-05-12) — for `enumerate` entries where one parent portal multiplexes subsidiaries (e.g. 平安集团 portal 一锅烩 829 jobs / `source=bank_official`, but `jobs.company` is split into 平安寿险 / 产险 / 证券 / 银行 / 人寿). `_resolve_status` first tries `jobs_company_match` keyword list against `jobs` (7-day window); on miss falls back to `company_crawl_logs`. Result: 银行 / 保险 / 券商 3 个赛道同时算出平安子实体的真实 active 数。

Frontend has two views via header pill: **公司星图** (default, `CoverageStarmap.tsx` — SVG 900×600, golden-ratio spiral dot placement, hand-tuned `CLUSTER_LAYOUT` per track) and **排行榜** (3-segment progress bar). `/api/coverage` reads yaml at request time — new tracks land instantly on yaml edit, no migration.

**Admin pages — Review queue + System health** (`app/routers/{review_queue,system_health}.py` + `frontend/src/pages/{ReviewQueue,SystemHealth}.tsx`):

- `/review-queue` surfaces jobs the crawler LLM left ambiguous (`quality_label IN ('', 'low_signal')` OR `track_predicted == ''`) in the last 30 days. `track_predicted` is re-bucketed into 3 coarse columns (FinTech / 纯金融 / 其他) for kanban view via `_bucket()` mapping. Endpoints: `GET /api/review-queue`, `POST /api/review-queue/{id}/{approve|reject|retrack}`, `POST /api/review-queue/batch`. Retrack writes one of 8 keys: internet/banks/securities/funds/pe_vc/insurance/state_owned/consumer_foreign/FinTech.

  **Teacher OCR bridge** (2026-05-12) — same page also shows `JobDraft` rows from the `/teacher` quick-entry flow (链接 / OCR / 文本三模). `GET /api/review-queue` returns `teacher_drafts[]` + `teacher_pending_total`; UI adds `✏️ 教师录入 N` tab. Proxy endpoints `POST /api/review-queue/teacher-drafts/{id}/{approve|reject}` call `teacher_entry._promote_draft_to_job` + `scorer.score_all_jobs` in-process. On approve: `jobs.source='teacher_entry'`, `quality_label='good'`, drops straight into the recommendation pool. Proxy is unauthenticated (same-origin/same-process); the underlying `/api/teacher-entry/admin/*` still requires admin token for cross-origin callers.

- `/system-health` **absorbs `/sites`** — service-status tiles (uvicorn / SQLite / APScheduler / 爬虫节点 / Resume Copilot / Sentry placeholder) on top of the embedded per-company crawler table. Auto-refresh 30s. `GET /api/system-health` returns `{headline, services, scheduler, sites, events}`; events stream mixes recent CompanyCrawlLog failures (last 7d) + CrawlLog batch finishes.

Both pages use per-page HiFi terracotta theme files scoped via `[data-theme="<page>"]` to prevent bleed into AntD pages.

### Frontend (`frontend/src/`)

Vite + React 19 + React Router 7 + Ant Design 6. Axios `baseURL: '/api'`, proxied by Vite to backend. Pages: `Jobs`, `JobIntel`, `Tracks`, `Scoring`, `Exclude`, `Crawl`, `Scheduler`, `Sites`, `Coverage`, `ReviewQueue`, `SystemHealth`, `CompanyExpand`, `Login`. The HiFi-styled pages (`/sites`, `/coverage`, `/review-queue`, `/system-health`) skip AntD components and use scoped `[data-theme="<page>"]` CSS files (Fraunces serif on terracotta parchment).

### Resume Copilot Web (`resume-copilot-web/`)

Next.js 16 App Router + Tailwind 4 + Ant Design 6. API proxied via `next.config.ts` rewrites: `/api/:path*` → `${RESUME_COPILOT_BACKEND_URL}/api/:path*` (default `http://127.0.0.1:8002`).

**Routes**:

| Path | Component | Notes |
|---|---|---|
| `/` | `<HFHero/>` | Public marketing page (HiFi). CTAs open `<GuestLoginModal/>`. |
| `/upload` | `<HFUpload/>` | Single-page upload + 3-stage real parse trace. Redirects to `/` if `!isGuestUser()`. |
| `/resume-copilot?sessionId=X` | `public-resume-copilot.tsx` | Workspace (legacy recommendation flow). `sessionId=1` shows `<DemoBanner/>` + disables write actions. Yellow `recommendations_stale` banner appears when Plan-mode synced new bullets. |
| `/resume-copilot/plan?sessionId=X` | `plan/page.tsx` → `PlanPanel.tsx` | Plan-mode resume builder (2026-05-13). Item tree (left) + selected-item chat + draft preview (right). Independent from `/resume-copilot`; finalized items sync back via `plan_sync`. |
| `/interview` | `app/interview/page.tsx` | Setup. Job chips (互联网 / 金融 / 咨询·快消·央企). Single-click chip = fill, double-click = launch. Stores target in `localStorage.interview.pending.{sessionId}`, routes to `/interview/{sessionId}/check`. |
| `/interview/[sessionId]/check` | `check/page.tsx` | Device check: mic (Paraformer phrase test) / speaker (longyingtian sample) / camera (`getUserMedia`). Auto-progressing 3-card layout. |
| `/interview/[sessionId]` | `[sessionId]/page.tsx` | Immersive stage: dark caption banner with **Border Beam** during thinking + center AI orb (terracotta sphere) + left progress rail + right self-view PiP + bottom mic input. Voice mode: TTS-progress drives caption reveal, push-to-talk via `Space`. Text mode: `Enter` to send. |
| `/login` | _deleted_ | Login is a modal, not a page. |

**Three design systems coexist** (kept strictly isolated):

- **Workspace** (`/resume-copilot`) — sky-blue palette via `var(--primary/ink/muted/border/soft-blue)` in `app/globals.css`. Agent thinking panel uses `SPINNER_FRAMES = ['·','✢','✳','✶','✻','✽']` at 120ms with staggered offsets (0/2/4) and verb-cycle 2000/2300/2600ms.
- **HiFi** (`/`, `/upload`, `<DemoBanner/>`) — Claude terracotta `#c96442` on parchment `#f5f4ed`, Fraunces serif. Tokens in `components/hifi/hifi-tokens.css`, **scoped to `.hf`**. Page layout in `hifi-pages.css` with breakpoints at 1024px / 640px.
- **Interview** (`/interview/*`) — same terracotta palette but **scoped to `[data-theme="interview"]`**, applied by `app/interview/layout.tsx`. Tokens in `app/interview/interview-theme.css`. **Border Beam** is the shared "AI thinking" treatment — `.border-beam` from `app/globals.css` (conic gradient + `@property --border-beam-angle`); place as **last child** of any `position:relative` parent so it paints above siblings.

Do not cross-pollute: no HiFi class names in workspace components; no workspace tokens redefined inside `.hf`.

**Shared HiFi primitives** (`components/hifi/hifi-primitives.tsx`): `HFLogo`, `HFBtn` (primary/ghost/sand/dark/link × sm/md/lg), `HFPill` (default/amber/terra/emerald/dark), `HFTicker`, `useCountUp`, `useLiveCount`, icon set under `I.{arrowRight, upload, file, check, sparkle, ...}`.

**Auth state** — `isGuestUser()` reads `sessionStorage.jobradar.resumeCopilot.isGuest`. `markAsGuest()` sets it after `<GuestLoginModal/>` validates `guest1` / `123456`. `requestJson` injects `X-Guest: 1` so backend marks new sessions `is_guest=1` (subject to 2-hour cleanup).

**Demo session constant** — `DEMO_SESSION_ID = 1` exported from `components/resume-copilot/api.ts`, consumed by Hero (CTA), Upload (`使用示例简历` button), workspace (`<DemoBanner/>` + write-disable).

Workspace key file: `components/resume-copilot/public-resume-copilot.tsx` (~2000 lines) — full workspace UI. Polls backend at 1.6s while `sessionIsActive(session)`.

### Session state machine (resume copilot)

```
uploading → parsing → awaiting_user_confirmation → generating_recommendations → completed
                                                ↘ failed
```
`recommendation_status` and `feedback_status` are independent sub-statuses (`running | completed | failed`). The router derives `has_*` flags via `joinedload` (single JOIN — see `_get_session_eager`).

**Chat rail**: each session has `/chat` returning `CopilotMessage[]`. Chat turns call `generate_chat_turn` in `services/resume_copilot/chat.py` (full recommendation + direction analysis context). Rewrites apply via `POST /chat/apply-rewrite`.

### Scripts

- **Root `scripts/`** — standalone (NOT part of the FastAPI app). `config.yaml` (track/keyword rules), `filter_jobs_v2.py`, `auto_login_scraper.py` (Playwright Tata login), `tata_jobs_export.py`, `generate_report.py`, `jobradar-docker-*.sh`.
- **Backend `backend/scripts/`** — periodic crawlers for company tier lists (consulting / internet / state-owned / securities / consumer-foreign), build `company_truth_layer`, align Tata sheets, annotate jobs with company tiers. Run `python backend/scripts/<script>.py` from repo root.

### Crawler 诊断方法论

Before labeling a crawler "工程不可行 / 反爬不可绕", **test at least one alternative engine**:
- `curl_cffi.requests` with `impersonate='chrome120' / 'safari17_2'` (TLS+H2 fingerprint)
- Playwright Firefox (different fingerprint than Chromium)
- Plain `requests` + `Sec-Fetch-{Site,Mode,Dest,User}` headers (Akamai 403 commonly fixed by these)
- Inspect RSC payload / `window.__NEXT_DATA__` / data.js (many SPAs hide truth in SSR data, not DOM)

Reach ≥2 dead-ends before declaring infeasible. Distinguish: (a) upstream真空 / (b) 反爬不可绕 / (c) 选择器漂. **Reference incident**: 2026-05-09 LVMH was wrongly flagged as "Chromium fingerprint blocked" — `curl_cffi(impersonate='chrome120')` returned 200 immediately; real cause was the Prismic CMS having `offersUrl: "$undefined"` for all locales (upstream真空, not anti-scrape).

### Internet crawler portal quirks (`app/services/legacy_crawlers/crawler.py`)

- **字节跳动**: portal pagination caps ~5,590 entries (~559 pages). `targets.yaml` sets `max_pages: 800` and the crawler resets session every 150 pages to bust cache. Reaching ~7,800 would need reverse-engineering the `_signature` JS — not worth it; Tata source covers the tail.
- **阿里巴巴**: `_crawl_campus_talent_alibaba()` uses XSRF-TOKEN cookie + REST POST. `batchId=100000540002` in `targets.yaml` is hardcoded **per hiring season** — needs manual update each batch.
- **蚂蚁集团**: `_crawl_antgroup_one_type` runs two passes (`campus_graduates` + `campus_interns`) because the portal segregates them.
- **腾讯**: `join.qq.com` is dead (commented out); only `careers.tencent.com` works. `crawl_internet_targets()` force-promotes `source` when an internet_official fetch matches a non-internet_official DB row (`merge_job_fields` upsert previously didn't update `source`).
- **`max_pages` propagation** — `InternetCrawlTarget` carries `max_pages` from `targets.yaml` through `_add_candidate()` to per-company crawl functions. Without this the yaml caps were silently ignored.

### Finance tier crawlers (`app/services/{insurance,bank,securities,funds,pe_vc,hedge_funds,foreign_ibs}_tier_crawler.py`)

Each tier crawler: load yaml → dispatch to an `ats_family` handler primitive → wrap each company call in `company_crawl_log(source=...)` → stamp records with track-specific `source` prefix (so `/sites` + `/coverage` bucket them).

**Handler primitives** (shared, live in `securities_crawler.py` + `funds_crawler.py`):
- `crawl_zhiye_target` — Beisen zhiye-campus JSON API at `<host>/api/Jobad/GetJobAdPageList`. Used by 中国人寿 / 人保 / 太平 / 衍复 / many securities.
- `crawl_zhiye_beisen_cms_target` — Beisen zhiye-CMS HTML scrape. Used by 大成/chinaamc/hftfund/ccbfund/gtfund.
- `crawl_moka_embedded_target` — Moka campus board, parses `<input id="init-data">` JSON from `app.mokahr.com/campus_apply/<tenant>/<board>`. Used by 九坤 / 幻方 (board 4604, `/apply/` variant) / 海通证券 / many internet firms.
- `crawl_hotjob_target` — `wecruit.hotjob.cn/wecruit/positionInfo/listPosition/<suite>` POST form. Used by many banks.
- `crawl_wintalent_sc_target` — `sc.hotjob.cn/wt/<COID>/...` self-host Wintalent. Used by 兴证全球 / 高毅 / 博时.

**Workday CXS** — separate impl in `pe_vc_tier_crawler._fetch_workday` (黑石) and `foreign_ibs_tier_crawler._fetch_workday_filtered` (uses `searchText` server-side to avoid paginating 2000 global jobs). Workday hard-caps `limit≤20` (25+ → 400). Many tenants (Goldman/JPM/UBS/HSBC) return 422 to minimal payloads even with searchText+facets — likely need per-tenant prep.

**Source prefix convention** — each tier crawler stamps records with track-prefix variant for `/sites` bucketing:
- `insurance_official` / `bank_official` / `state_owned_official` / `consumer_foreign_official` — single-source per track
- `securities_{zhiye,zhiye_legacy,moka_embedded,hotjob}` — multi-source 券商
- `funds_{hotjob,zhiye,moka_embedded,zhiye_beisen_cms,wintalent_sc}` — multi-source 公募
- `hedge_funds_*`, `pe_vc_official`, `foreign_ibs_official` — see Phase 7/9/10

`coverage_truth.yaml`'s `source_match` lists per track must match these prefixes — adding a new finance source means updating both crawler AND yaml in one commit.

---

## Production deployment (VPS)

Runs on user's VPS (`myvps`, 122.51.18.237) under systemd. SSH setup in the `wsl2-ssh-to-vps` skill (cipher pinning around WSL2 MTU bug).

- **Timezone**: VPS = CST (Asia/Shanghai = UTC+8). SQLite stores `started_at`/`finished_at` in **naive UTC**; query with `datetime(started_at, 'localtime')` to get 北京时间 (don't manually subtract 8h). APScheduler cron expressions are interpreted in CST (`0 9 * * *` = 北京时间 09:00).
- **Service**: `/etc/systemd/system/jobradar.service` — `sudo systemctl {status,restart,start,stop} jobradar`.
- **Working dir**: `/home/ubuntu/opencode-worktrees/jobrador-edit/backend` on `main` branch. Bind: uvicorn `127.0.0.1:8000` only (no external exposure).
- **Scheduler**: APScheduler `daily_crawl` fires `0 8 * * *` Asia/Shanghai. Verify with `curl http://127.0.0.1:8000/api/scheduler` on VPS.
- **Env**: `EnvironmentFile=/home/ubuntu/opencode-worktrees/jobrador-edit/.env` + `Environment=PYTHONUNBUFFERED=1` (lifespan print → journal) + `Environment=OPENSSL_CONF=/etc/ssl/openssl-legacy.cnf` (legacy TLS for bank/government sites needing unsafe legacy renegotiation).
- **Logs**: `sudo journalctl -u jobradar --since "08:00"`.
- **Brand-new VPS DB only**: after first deploy run `cd /home/ubuntu/opencode-worktrees/jobrador-edit/backend && PYTHONPATH=. .venv/bin/alembic stamp head` once before code calls `alembic upgrade head`.

The VPS runs `main`, so cherry-pick crawler fixes from feature branches to `main` and push before expecting effect there. When GitHub→VPS network is flaky, transfer commits via `git bundle` + `scp` instead of `git fetch`.

### Weekly DB backup (WSL-side pull)

- **Script**: `~/bin/backup_jobradar_db.sh` on user's WSL machine.
- **Cron**: `0 3 * * 0` (Sunday 03:00 local) — WSL must be running.
- **Snapshots**: `~/backups/jobradar/jobradar.<UTC-stamp>.db`, rotated to keep 8 most recent.
- **Mechanism**: sqlite3 `.backup` API on VPS for WAL-safe snapshot, then gzip + rsync with 5-retry backoff (WSL2 ↔ VPS is flaky for >1MB).

---

## Environment setup

`backend/.env.local` minimum:
```
RESUME_COPILOT_BASE_URL=https://api.deepseek.com/v1
RESUME_COPILOT_API_KEY=sk-...
RESUME_COPILOT_MODEL_NAME=deepseek-chat
TAVILY_API_KEY=tvly-...
FIRECRAWL_API_KEY=fc-...

# Mock-interview voice stack (DashScope / 阿里云百炼)
DASHSCOPE_API_KEY=sk-...
DASHSCOPE_TTS_MODEL=cosyvoice-v2
DASHSCOPE_TTS_VOICE=longyingtian
DASHSCOPE_ASR_MODEL=paraformer-realtime-v2
```

For resume-copilot-web, set `RESUME_COPILOT_BACKEND_URL` in `resume-copilot-web/.env.local` if backend runs on a port other than 8002.
