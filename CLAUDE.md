# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**JobRadar** is a campus-recruitment tracking tool for the Chinese job market. It has three runtimes:

| Runtime | Root | Port | Purpose |
|---|---|---|---|
| Backend API | `backend/` | 8000 (dev) / 8002 (resume-copilot docker) | FastAPI + SQLite, all data logic |
| Frontend (job browser) | `frontend/` | 5173 | Vite + React, job search/scoring/intel UI |
| Resume Copilot Web | `resume-copilot-web/` | 3001 | Next.js, resume upload → parse → recommend flow |

The frontend and resume-copilot-web are separate apps that both proxy `/api/*` to the same backend. They are never served together in dev.

---

## Commands

### Backend
```bash
# Install deps (from repo root or backend/)
cd backend && pip install -r requirements.txt

# Run dev server (port 8000)
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run all tests
cd backend && PYTHONPATH=. .venv/bin/pytest tests/

# Run a single test file
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_sites_router.py -x

# Run a specific test
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

### Docker (both backend + frontend together)
```bash
docker compose up --build
# backend → :8001, frontend → :5173
```

---

## Architecture

### Backend (`backend/app/`)

**Entry point:** `main.py` — FastAPI app with a lifespan that: creates all tables, runs `ensure_compatible_schema()` (ad-hoc DDL patcher), seeds from YAML configs, calls `ensure_demo_session(db)` to (re)hydrate the shared demo session, and starts an APScheduler daily crawl at 08:00 Asia/Shanghai + an hourly guest-cleanup interval job.

**Routers:** `jobs`, `tracks`, `scoring`, `exclude`, `crawl`, `export`, `scheduler`, `system_config`, `company_recrawl`, `job_intel`, `resume_copilot`, `interview`, `sites`. Each router is a file under `app/routers/`.

**Database:** Single SQLite file at `backend/data/jobradar.db`. WAL mode and `busy_timeout=5000` are set via a SQLAlchemy `@event.listens_for(engine, 'connect')` hook. Models are in `app/models.py`. Schema evolution: starting 2026-04-28, new schema changes go through Alembic (`backend/alembic/versions/`); legacy `app/services/schema_patch.py` still runs at startup for safety during transition. To add a migration: `cd backend && PYTHONPATH=. .venv/bin/alembic revision --autogenerate -m "<name>"`, review the generated file, then `alembic upgrade head` (also runs automatically in lifespan). On a brand-new VPS DB, after first deploy run `cd /home/ubuntu/opencode-worktrees/jobrador-edit/backend && PYTHONPATH=. .venv/bin/alembic stamp head` once before any code that calls `alembic upgrade head`.

**Resume Copilot pipeline** (`app/services/resume_copilot/`):
- `workflow.py` — two async-safe workflows: `run_resume_parse_workflow` and `run_resume_generate_workflow`, both dispatched via FastAPI `BackgroundTasks`. Each opens its own `SessionLocal`.
- `parser.py` — calls an LLM to extract structured profile from raw PDF text; falls back to heuristic extraction on HTTP errors.
- `ingest.py` — `extract_resume_text_with_page_count(bytes) -> (text, page_count)` is the canonical PDF-extract helper; `extract_resume_text_from_pdf` is a thin wrapper kept for older call sites. `POST /sessions` returns `page_count` and `file_size_bytes` so the upload UI can show real numbers in its agent trace.
- `recommendation.py` — pre-filters jobs from DB by preferences/track, scores with `compute_rule_score`, optionally enriches with `JobIntelSnapshot` boosts (14-day TTL). LLM reranks top-N results.
- `quick_enrichment.py` — parallel web search + page extraction for top-N jobs using `ThreadPoolExecutor`. Trace events are collected in thread-local lists and replayed in the main thread to avoid concurrent SQLite writes.
- `feedback.py` — LLM-generated resume diagnostics and rewrite suggestions.
- `agent/` — ReAct loop powering "代理思考中" trace. `tools.py` exposes 4 callables (`search_candidates`, `inspect_jobs`, `get_company_intel`, `search_web`); `core.py` adds a `finalize` action and a `BUDGET_EXHAUSTED` short-circuit driven by `budget.py` (forces `finalize` when token/step budget is spent).
- `direction_analysis.py` — LLM produces 3-tier direction labels: 第1层 强匹配 / 第2层 可迁移 / 第3层 有差距. `tier_label` enum is enforced; falls back to `tier_label='强匹配'` on parse failure.
- `chat.py` — `/chat` turn handler. **Rewrite contract is strict**: when LLM returns `rewrite_options`, length must be 2 and both options must share the same `field_path`, `target_title`, and `original` (two alternative writeups for the *same* spot, not two different edits). `field_path` is dot-notation (e.g. `internships.0.bullets`); `_traverse_and_set` walks `ResumeConfirmedProfile.profile_json` to apply the chosen option via `POST /chat/apply-rewrite`.
- `demo_session.py` — `DEMO_SESSION_ID = 1` + `ensure_demo_session(db)`. Seeds a fully-prepared shared session (张三 / 上交大本科 / 互联网数据分析) with `user_key='__demo__'`, `is_guest=0`, status `completed`, and pre-computed recommendations + direction analysis + 3 chat messages. The lifespan calls this on every startup; existing demo rows are force-updated to ensure `user_key='__demo__'` is set (so the read-only guard catches them).

**Demo session read-only guard**: in `routers/resume_copilot.py`, `_assert_not_demo(session)` checks `session.user_key == '__demo__'` (not session_id, so tests using id=1 with a different user_key pass). It must be called **after** `_get_session_or_404` and is mounted on every write endpoint (PATCH/DELETE session, PUT confirmed-profile, PUT preferences, POST generate, POST chat, POST chat/apply-rewrite). All `GET` endpoints are unaffected.

**Mock Interview pipeline** (`app/services/interview/`):
- `llm.py` — `stream_interview_turn(target_job, messages)` yields raw SSE lines from the resume-copilot LLM (DeepSeek by default). Reuses `build_resume_llm_client()`. Per-read socket timeout is bumped to **120s** because reasoning models can pause >30s between tokens; the default 30s would abort streams mid-thought and leave the UI stuck in "思考中".
- `report.py` — generates the post-interview report (overall score + per-dimension scores + recommendations) by re-prompting the same LLM with the full transcript.
- `voice/tts.py` — dispatches by `config.DASHSCOPE_TTS_MODEL`: `qwen3-tts-*` uses HTTP REST (POST → OSS WAV URL → stream bytes); `cosyvoice-*` uses WebSocket duplex (run-task → continue-task with text → finish-task → binary frames). Both return `Iterator[bytes]` so callers don't care. Default voice is `longyingtian` ("温柔甜美女", CosyVoice v2). Voice list at `https://help.aliyun.com/zh/model-studio/cosyvoice-voice-list`.
- `voice/asr.py` — `run_asr_session(audio_frames, send_event)` proxies a Paraformer-realtime-v2 WebSocket session. Receives PCM16 16kHz mono frames from the browser via `/api/interview/asr` WS, forwards to DashScope, emits `{type: started/partial/final/completed/error}` events back to the client.
- `voice/avatar.py` — Aliyun Lingmou (灵眸) digital-human session creator. **Currently unused at runtime** — `POST /api/interview/avatar/session` is wired up but the design has moved to a static portrait + AI orb. Kept in the codebase for reference / future integration. Uses Aliyun **V3 signature** (ACS3-HMAC-SHA256, header-based) on the **ROA-style** path `POST /openapi/chat/init/{projectId}?platform=Web&instanceId=...`. The `platform` value MUST be `Web`, not `webSDK`. The `id` is the avatar project ID (a `path` param), not body. See SDK reference: `alibabacloud-lingmou20250527`.

**Interview router** (`app/routers/interview.py`) endpoints:
- `POST /api/interview/turn` — SSE stream of one assistant turn. Wraps the LLM stream in a try/except so transport-level errors surface as `data: {"error": "...", "type": "..."}` events instead of breaking the stream.
- `POST /api/interview/report` — synchronous; persists an `InterviewReport` row and returns the parsed report.
- `POST /api/interview/avatar/session` — Lingmou rtcParams (currently unused by frontend).
- `POST /api/interview/tts` — returns `audio/wav` stream.
- `WS   /api/interview/asr` — bi-directional: client sends PCM frames, server sends transcript events.
- `GET  /api/interview/reports` and `GET /api/interview/reports/{id}` — history + detail. Filtered by `X-Resume-User-Key`.

**Config** (`app/config.py`): reads `.env.local` from `backend/` then root, then OS env. Key groups:
- `RESUME_COPILOT_*` — LLM base URL, API key, model name, timeouts
- `TAVILY_API_KEY`, `FIRECRAWL_API_KEY`, `JINA_API_KEY`, `BRAVE_SEARCH_API_KEY` — enrichment search
- `TATA_USERNAME` / `TATA_PASSWORD` — crawler credentials
- `DASHSCOPE_API_KEY` + `DASHSCOPE_TTS_MODEL` (default `qwen3-tts-flash`, set to `cosyvoice-v2` for the longyingtian voice) + `DASHSCOPE_TTS_VOICE` (default `Chelsie`, set to `longyingtian`) + `DASHSCOPE_ASR_MODEL` (default `paraformer-realtime-v2`) — voice stack for the mock interview
- `ALIYUN_ACCESS_KEY_ID` + `ALIYUN_ACCESS_KEY_SECRET` + `AVATAR_PROJECT_ID` + `AVATAR_INSTANCE_ID` — Lingmou avatar credentials (currently dormant — see `voice/avatar.py`)
- `ALERT_STALE_DAYS` — sites-monitor staleness threshold (default 3 days)
- `CRAWLER_LLM_BASE_URL` / `CRAWLER_LLM_API_KEY` (fall back to RESUME_COPILOT_LLM_*) / `CRAWLER_LLM_FLASH_MODEL` / `CRAWLER_LLM_PRO_MODEL` / `CRAWLER_LLM_TIMEOUT_SECONDS` — DeepSeek V4 client config for crawler enrichment / diagnosis / digest. Three feature flags default OFF: `CRAWLER_LLM_ENRICH_ENABLED`, `CRAWLER_LLM_DIAGNOSE_ENABLED`, `CRAWLER_LLM_DIGEST_ENABLED`.

**Sites monitor** (`app/routers/sites.py` + `app/services/{company_crawl_logger,sites_alert,company_crawler_registry}.py`):

> **Cron schedule**: three daily APScheduler jobs.
> - **08:00 Asia/Shanghai** — `_daily_crawl_job` calls `run_crawl()` (Tata API + Haitou + recrawl-queue). Fast, ~5 min.
> - **09:00 Asia/Shanghai** — `_daily_tier_crawl_job` runs the 4 tier orchestrators (internet / state_owned / securities / consumer_foreign) sequentially with error isolation per tier. Populates `company_crawl_logs`. Slow, ~30 min, Playwright-heavy. Each tier wrapped so one failure doesn't stop the others; a parent `CrawlLog` row with `source='tier-crawl'` aggregates the run.
> - **09:35 Asia/Shanghai** — `_daily_digest_job` runs LLM digest (V4-Flash) over today's `company_crawl_logs` rows. Gated by `CRAWLER_LLM_DIGEST_ENABLED`. Persisted to `system_config` row `key='sites_daily_digest'`, served via `GET /api/sites/digest`.

- New table `company_crawl_logs` — per-company run record, parent-linked to `crawl_logs.id` for the daily batch. `suggested_fix` column holds optional LLM-3 markdown diagnosis text.
- New columns on `jobs`: `track_predicted` (LLM-classified track) + `quality_label` (good/agency/spam/low_signal). Filled by `crawler_llm_enrich.enrich_jobs_parallel` when `CRAWLER_LLM_ENRICH_ENABLED=1`. Wired into all 4 tier crawlers' new-job batch.
- Context manager `company_crawl_log(db, source=, company=, parent_log_id=)` wraps each per-target call inside the orchestrators (`internet_crawler`, `state_owned_crawler`, `securities_crawler`, `consumer_foreign_crawler`). On exception: marks row `failed`, truncates `error_message` to 500 chars, schedules a daemon-thread LLM-3 diagnosis (V4-Pro) if `CRAWLER_LLM_DIAGNOSE_ENABLED=1`, re-raises. Body sets `log.fetched_count` / `log.new_count`.
- For orchestrators whose existing inner except SWALLOWS exceptions (state_owned, consumer_foreign, internet), the wrap uses a `target_exc` sentinel: inner except saves exc + still appends to results / rolls back; after the inner finally an `if target_exc is not None: raise target_exc` propagates so `company_crawl_log` marks row failed; an outer `try/except: pass` swallows for continue-on-error. Securities re-raises naturally — simple wrap.
- Energy and antgroup are explicitly **out of scope**: `energy_crawler.py` is a CLI-only standalone script not invoked by the daily cron. `crawl_antgroup` flows through `crawl_internet_targets` so it's covered transitively by the internet wrap.
- 5 endpoints under `/api/sites/*`: `GET /summary`, `GET /?source=`, `GET /{company}/runs?limit=`, `POST /{company}/recrawl`, `GET /digest`. Recrawl validates against `COMPANY_CRAWLERS` registry (16 internet t1 companies; 网易雷火 deliberately omitted because `build_internet_targets()` doesn't return targets for it), schedules a fresh `SessionLocal` background task, runs scoring on `new_count > 0` (scorer failure non-fatal — doesn't escalate to parent CrawlLog status), returns `{parent_log_id, message}`.
- Alert level rule (`alert_level(runs, now)`, pure): empty=`unknown`; last failed + prev failed=`red`; last failed alone=`yellow`; last success + no new in `ALERT_STALE_DAYS`=`yellow`; else `green`.
- `_shanghai_today_start()` returns Asia/Shanghai today 00:00 expressed as naive UTC. Fixed +08:00 offset (Asia/Shanghai never observes DST).
- `_build_site_rows` is N+1 by design: 2N+1 queries per `/api/sites` call. Acceptable at current scale (~30 companies, SQLite WAL); revisit if registry grows past ~50.
- **UI** (`/frontend/src/pages/Sites.tsx` + `components/sites/*` + `styles/{hifi-tokens,sites-theme}.css`): `/sites` route. HiFi terracotta scoped via `<div className="hf" data-theme="sites">` — does not bleed into other AntD admin pages. Adaptive polling (8s default, 2s while any recrawl is in flight). Source→group bucketing maps `internet_official` / `securities_*` / `state_owned_official` / `consumer_foreign_official` onto 4 visible categories (互联网官网 / 券商 / 国央企 / 消费外企). Components: `SitesSummaryBar` (KPI pills + alert banner), `CategoryGroup` → `CompanyCard`, `SiteDetailPanel` → `RunSparkline` + `RecrawlButton` + LLM-3 diagnosis block (`MarkdownLite` for `**bold**` / `` `code` `` / numbered lists), `ToastHost` for recrawl feedback. 41 vitest unit + integration tests, no Playwright e2e.

### Frontend (`frontend/src/`)

Vite + React 19 + React Router 7 + Ant Design 6. All API calls go through an Axios instance with `baseURL: '/api'`, proxied to the backend by Vite (`vite.config.ts`). Pages: `Jobs`, `JobIntel`, `Tracks`, `Scoring`, `Exclude`, `Crawl`, `Scheduler`, `Sites`, `Login`. There are no SSR concerns. The `/sites` page deliberately doesn't use AntD components — it's HiFi-styled (Fraunces serif, terracotta on parchment) — see "Sites monitor" subsection above.

### Resume Copilot Web (`resume-copilot-web/`)

Next.js 16 App Router + Tailwind CSS 4 + Ant Design 6. All API calls are proxied via `next.config.ts` rewrites: `/api/:path*` → `${RESUME_COPILOT_BACKEND_URL}/api/:path*` (default `http://127.0.0.1:8002`).

**Routes**:

| Path | Component | Notes |
|---|---|---|
| `/` | `<HFHero/>` from `components/hifi/hifi-hero.tsx` | Public marketing page (HiFi terracotta). CTAs `上传简历` / `看示例推荐` open `<GuestLoginModal/>` if not logged in. |
| `/upload` | `<HFUpload/>` from `components/hifi/hifi-upload.tsx` | Single-page upload + 3-stage real parse trace (read PDF → LLM extract → ready). Client-side guard: redirects to `/` if `!isGuestUser()`. |
| `/resume-copilot?sessionId=X` | `public-resume-copilot.tsx` | Workspace. `sessionId=1` shows `<DemoBanner/>` and disables chat composer + apply-rewrite buttons. |
| `/interview` | `app/interview/page.tsx` | Setup. High-frequency job chips (互联网 / 金融 / 咨询·快消·央企) + custom textarea. Single-click chip = fill, double-click = launch. Stores target job in `localStorage.interview.pending.{sessionId}` and routes to `/interview/{sessionId}/check`. |
| `/interview/[sessionId]/check` | `app/interview/[sessionId]/check/page.tsx` | Device check (mic / speaker / camera). 2-column hi-fi layout per `Mock Interview · Device Check.html` design — left: serif headline + 3 vertical check cards that auto-progress; right sticky aside: session info + camera preview + 开始模拟面试 button. Footer has 跳过检测 link. Real wiring: `useRecorder` (Paraformer ASR phrase test), `useTTSPlayer` (longyingtian sample for speaker), `getUserMedia` for camera. |
| `/interview/[sessionId]` | `app/interview/[sessionId]/page.tsx` | The interview itself. Immersive stage per `Mock Interview · AI Interviewer.html` design — top dark caption banner with **Border Beam** during thinking, center AI orb (terracotta sphere with breathe animation), left progress rail (6 questions), right self-view PiP, bottom mic input bar. **No static interviewer portrait** — the prior `interviewer.png` + `<AvatarView/>` flow was replaced by the orb. Voice mode: TTS-progress drives caption character reveal; push-to-talk via `Space`. Text mode: type answer + `Enter` to send. Mode switcher in top bar. |
| `/login` | **deleted** | Login is a modal, not a page. |

**Three design systems coexist** (kept strictly isolated):

- **Workspace** (`/resume-copilot`) — original sky-blue palette via `var(--primary)`, `var(--ink)`, `var(--muted)`, `var(--border)`, `var(--soft-blue)`. Defined in `app/globals.css`. The agent thinking panel uses `SPINNER_FRAMES = ['·', '✢', '✳', '✶', '✻', '✽']` at **120ms** ticks with staggered per-agent start offsets (0, 2, 4), matching Claude Code terminal style. Verb cycling is 2000/2300/2600ms per agent so they don't sync.
- **HiFi** (`/`, `/upload`, `<DemoBanner/>`) — Claude terracotta system: `--terracotta` `#c96442` on `--parchment` `#f5f4ed`, Fraunces serif for headings/numbers, Inter for body, JetBrains Mono for terminal-style traces. Tokens live in `components/hifi/hifi-tokens.css` and are **scoped to `.hf`** — every HiFi root element wraps in `<div className="hf">`. Page-level layout (`hf-hero-page__*`, `hf-upload-page__*`) is in `components/hifi/hifi-pages.css` with mobile breakpoints at 1024px (single-column) and 640px (compact). Both files are imported from `app/globals.css`. **Do not** add HiFi class names to workspace components, and do not redefine workspace tokens inside `.hf`.
- **Interview** (`/interview/*`) — same Claude terracotta palette as HiFi but **scoped to `[data-theme="interview"]`** instead of `.hf`. Tokens live in `app/interview/interview-theme.css`, applied by `app/interview/layout.tsx` which wraps all interview pages in `<div data-theme="interview">` and loads Google Fonts (Fraunces / Noto Serif SC / Inter / Noto Sans SC / JetBrains Mono). The layout overrides `--primary` / `--background` / `--paper` etc. inside the scope so any reused component reading those tokens automatically picks up the interview theme. **Border Beam** is the shared "AI thinking" treatment: `.border-beam` from `app/globals.css` (conic gradient + `@property --border-beam-angle` + mask-composite ring), with the interview theme overriding the gradient palette to terracotta + amber. Place it as the **last child** of any `position: relative` parent so it paints above siblings.

**Shared HiFi primitives** (`components/hifi/hifi-primitives.tsx`): `HFLogo`, `HFBtn` (primary/ghost/sand/dark/link × sm/md/lg), `HFPill` (default/amber/terra/emerald/dark), `HFTicker`, `useCountUp(target, duration)`, `useLiveCount(target, duration)` (count-up then slow live tick), and an icon set under `I.{arrowRight, upload, file, check, sparkle, ...}`.

**Auth state**: `isGuestUser()` reads `sessionStorage.jobradar.resumeCopilot.isGuest`. `markAsGuest()` sets it after `<GuestLoginModal/>` validates `guest1` / `123456`. `requestJson` in `api.ts` injects `X-Guest: 1` when this flag is set, which causes the backend to mark new sessions as `is_guest=1` (subject to 2-hour cleanup).

**Demo session constant**: `DEMO_SESSION_ID = 1` is exported from `components/resume-copilot/api.ts` and consumed by both Hero (CTA destination), Upload (`使用示例简历` button), and the workspace (`<DemoBanner/>` mount + write-disable).

Workspace key file: `components/resume-copilot/public-resume-copilot.tsx` (~1990 lines) — the entire resume copilot UI: upload → parse progress → profile editor → preference picker → recommendation cards + chat rail. It polls the backend at 1.6s intervals while `sessionIsActive(session)` is true.

### Session state machine (resume copilot)

`ResumeCopilotSession.status` transitions:
```
uploading → parsing → awaiting_user_confirmation → generating_recommendations → completed
                                                 ↘ failed
```
`recommendation_status` and `direction_status` are independent sub-statuses (`running | completed | failed`). The router derives `has_parsed_profile / has_confirmed_profile / has_recommendations / has_feedback` via `joinedload` (single JOIN query — see `_get_session_eager` in `routers/resume_copilot.py`).

**Chat rail** (feature/big-wip-20260315): Each session has a `/chat` endpoint returning `CopilotMessage[]`. Chat turns call `generate_chat_turn` in `services/resume_copilot/chat.py`, which has access to the full recommendation + direction analysis context. Rewrite suggestions can be applied via `POST /chat/apply-rewrite`.

### Root-level scripts (`scripts/`)

Standalone scripts for job filtering, reporting, and crawling — **not** part of the FastAPI app. Run from the repo root with `python scripts/<name>.py`.

Key files:
- `config.yaml` — track/keyword/scoring rules consumed by `filter_jobs_v2.py`
- `filter_jobs.py` / `filter_jobs_v2.py` — filter job CSVs by track rules
- `auto_login_scraper.py` — Playwright-based Tata Wangshen login + scrape
- `tata_jobs_export.py` — export Tata VIP job table to CSV
- `generate_report.py` — generate Markdown job recommendation report
- `jobradar-docker-*.sh` — Docker lifecycle helpers

### Data exports (`data/exports/`)

56 MB of denormalized company/job truth-layer CSVs built by the tier-annotation pipeline:
- `company_truth_spring_master.csv` — canonical company list with tier labels
- `job_truth_spring_master.csv` — canonical job list with company linkage
- `tata_aligned_to_spring_truth.csv` — Tata export aligned to truth layer
- `legal_entity_alias_*.csv` — entity resolution candidates/overrides

### Backend data scripts (`backend/scripts/`)

Periodic scripts for crawling company tier lists (consulting, internet, state-owned, securities, consumer-foreign), building the `company_truth_layer`, aligning TATA export sheets, and annotating job rows with company tiers. Run directly as `python backend/scripts/<script>.py` from the repo root.

### Mock interview module (`app/routers/interview.py` + `resume-copilot-web/app/interview/`)

Frontend pages live under `resume-copilot-web/app/interview/[sessionId]/`. Entry from a recommendation card creates a session, then user goes through device check → chat → report. Theme styles in `app/interview/interview-theme.css`; shared bits in `components/interview/primitives.tsx`.

Backend voice stack (Aliyun NLS was replaced — see commits `4615a9e` / `7d2f8d2`):

- **ASR**: DashScope `paraformer-realtime-v2` (WebSocket proxy through `/api/interview/asr`)
- **TTS**: DashScope `cosyvoice-v2` with voice `longyingtian` (default; falls back to `qwen3-tts-flash` HTTP path if model name is `qwen3-tts-*`). Streamed back as `audio/wav`.
- **Digital-human avatar**: 阿里灵眸 (`POST /api/interview/avatar/session`) is wired but **not rendered** — the design replaced the live video avatar with a static-orb stage. Code retained in `voice/avatar.py` for future re-enablement.

Frontend deps notable for the interview pages: `lucide-react` for the icon set used by both the device check and interviewer pages.

### Crawler 诊断方法论（避免 "工程不可行" 误判）

2026-05-09 LVMH 反例：Phase 5 当时定为"Chromium HTTP/2 fingerprint 被 CDN 拒，需换 Firefox/curl_cffi 工程不可行"。后来 subagent 用 `curl_cffi.requests.get(impersonate='chrome120')` **一次过 200 / 1.38MB HTML**，证伪了 fingerprint 假说。**真因**是 LVMH 的 Prismic CMS 主动没配 job feed (`offersUrl: "$undefined"` for all locales)——是上游内容侧空，不是反爬。

**规则**：在给某家 crawler 标 "工程不可行 / 反爬不可绕" 之前，**至少 1 个备选引擎实测**：
- `curl_cffi.requests` with `impersonate='chrome120' / 'safari17_2'` （TLS+H2 fingerprint 模拟）
- Playwright Firefox（`playwright install firefox` + `p.firefox.launch()`），fingerprint 跟 Chromium 完全不同
- 直 `requests` + 仿真 headers（特别是 `Sec-Fetch-{Site,Mode,Dest,User}` —— Akamai 类常因为缺这几个 403）
- 看 RSC payload / window.__NEXT_DATA__ / data.js 等 SSR 数据源（很多 SPA 真数据不在 DOM）

如果 ≥2 个备选都拿不到，再标"工程不可行"。否则要分清：(a) 上游真空 vs (b) 反爬不可绕 vs (c) 选择器/接口漂——三种处理方式不同。

### Internet crawler coverage notes (`app/services/legacy_crawlers/crawler.py`)

The t1 internet portals each have a quirk worth knowing before touching them:

- **字节跳动**: portal pagination (jobs.bytedance.com/campus/position) hits an anti-scrape ceiling around 5,590 entries (~559 pages). `targets.yaml` sets `max_pages: 800` and the crawler resets the session every 150 pages to bust pagination cache. Reaching the full ~7,800 entries would require reverse-engineering the `_signature` JS — not worth the maintenance cost; Tata source covers the tail.
- **阿里巴巴**: `_crawl_campus_talent_alibaba()` uses XSRF-TOKEN cookie + REST POST. The `batchId=100000540002` in `targets.yaml` is hardcoded per hiring season — needs manual update each new batch.
- **蚂蚁集团**: `_crawl_antgroup_one_type` runs two passes (`campus_graduates` + `campus_interns`) because the portal segregates them.
- **腾讯**: `join.qq.com` is dead (kept commented out in `targets.yaml`); only `careers.tencent.com` works. `merge_job_fields` upsert previously didn't update the `source` column — `crawl_internet_targets()` now force-promotes source when an internet_official fetch matches a non-internet_official DB row.
- **`max_pages` propagation**: The `InternetCrawlTarget` dataclass carries `max_pages` from `targets.yaml` through `_add_candidate()` to per-company crawl functions. Without this, yaml-configured caps were silently ignored.

---

## Production deployment (VPS)

The project runs on the user's VPS (`myvps`, 122.51.18.237) under systemd as the long-lived daily runtime. Connection setup lives in the `wsl2-ssh-to-vps` skill (cipher pinning works around WSL2's MTU bug).

- **Timezone**: VPS clock = **CST (Asia/Shanghai = 北京时间 / UTC+8)**. User is also in 北京时间. SQLite stores `started_at`/`finished_at` in **naive UTC** (default). When querying use `datetime(started_at, 'localtime')` to get 北京时间. Don't manually subtract 8h — `'localtime'` 已经做对。APScheduler cron 表达式按 CST 解读（`0 9 * * *` = 北京时间 09:00）。
- **Service**: `/etc/systemd/system/jobradar.service` on VPS — `sudo systemctl {status,restart,start,stop} jobradar`
- **Working dir**: `/home/ubuntu/opencode-worktrees/jobrador-edit/backend` on `main` branch
- **Bind**: uvicorn on `127.0.0.1:8000` only (no external exposure, no nginx)
- **Scheduler**: APScheduler `daily_crawl` fires at `0 8 * * *` Asia/Shanghai. Verify with `curl http://127.0.0.1:8000/api/scheduler` on the VPS.
- **Env**: systemd `EnvironmentFile=/home/ubuntu/opencode-worktrees/jobrador-edit/.env` — keeps `TATA_USERNAME` / `TATA_PASSWORD` in one place. Plus `Environment=PYTHONUNBUFFERED=1` (lifespan print 要进 journal) + `Environment=OPENSSL_CONF=/etc/ssl/openssl-legacy.cnf` (legacy TLS 银行/政府站需要 unsafe legacy renegotiation)。
- **Logs**: `sudo journalctl -u jobradar --since "08:00"`

Code that affects scheduler / lifespan / startup must be tested against this systemd unit. The VPS runs `main`, so cherry-pick crawler fixes from feature branches to `main` and push before expecting them to take effect there. When GitHub→VPS network is flaky, transfer commits via `git bundle` + `scp` instead of relying on `git fetch` from the VPS.

### Weekly DB backup (WSL-side pull)

- **Script**: `~/bin/backup_jobradar_db.sh` on the user's WSL machine
- **Cron**: `0 3 * * 0` (Sunday 03:00 local) — WSL must be running at that time
- **Snapshots**: `~/backups/jobradar/jobradar.<UTC-stamp>.db`, rotated to keep the 8 most recent
- **Mechanism**: sqlite3 `.backup` API on the VPS for WAL-safe consistent snapshot, then gzip + rsync with 5-retry backoff (WSL2 ↔ VPS link is flaky for >1MB transfers)

---

## Environment setup

Create `backend/.env.local` with at minimum:
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

For the resume-copilot-web, set `RESUME_COPILOT_BACKEND_URL` in `resume-copilot-web/.env.local` if the backend runs on a port other than 8002.
