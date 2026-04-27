# Sites Monitor UI — Phase 2 Design Spec

**Date:** 2026-04-27
**Wireframe reference:** `JobRadar Wireframes.html` 第 07 节 · `wf-core.jsx` Core_B（站点节点视图）— 简化为分组卡片栅格而非 SVG hub graph
**Design system:** HiFi terracotta — `hifi-tokens.css` from `Jobradar design system.zip`
**Phase 1:** Backend complete on `feat/sites-monitor` branch (19 commits, 215 tests passing). API contract: 4 endpoints under `/api/sites/*`.
**Status:** Approved by user 2026-04-27

## Goal

Ship a `/sites` admin page in `/frontend` that lets the operator answer two questions every morning at a glance:

1. **"Did the crawlers run last night, and which companies got fresh data?"**
2. **"For the company I care about (e.g. 腾讯), is its scraper still working — and if not, can I retry it without re-running the whole batch?"**

Backed by Phase 1's `/api/sites/*` endpoints. Visual identity: HiFi terracotta — Fraunces serif headers, Inter body, JetBrains Mono code, parchment background, terracotta primary.

## Scope

In:
- New `/sites` route in `/frontend` (Vite + React + AntD app, port 5173).
- HiFi terracotta theme scoped to the new page only — does not affect existing `/crawl`, `/scheduler`, etc.
- 4 components consuming the existing API: summary bar, category-grouped company-card grid, detail panel, recrawl trigger.
- Adaptive polling (8s default; 2s after a recrawl is triggered until completion is detected).
- Empty state when the DB has no `company_crawl_logs` rows yet (fresh deploy).
- Top-of-page alert banner when ≥2 companies are alerted (yellow/red).
- Unit tests covering rendering / interaction / API contract.

Out (later phases or out-of-scope):
- SVG hub graph (Core_B's decorative center). Deliberately omitted — see Q2 in brainstorming.
- Per-company enable/disable controls.
- In-UI editing of crawler parameters (`targets.yaml` etc).
- Slack/email/IM alert fan-out — only on-page banner.
- Mobile breakpoints. Desktop-first; admin tooling.
- Internationalization beyond Chinese.

## Decisions log (from brainstorming)

| Q | Decision | Why |
|---|---|---|
| Q1 | **A** — full HiFi treatment scoped via `[data-theme="sites"]` class on `<div className="hf">` wrapper, no AntD components inside the new page | Matches the design system the user explicitly provided; keeps other admin pages clean |
| Q2 | **B** — category-grouped card grid, not SVG hub graph | Density-first ops view beats sales/demo flair for daily-use tools |
| (implicit) | Polling 8s default, 2s after recrawl click | 1.6s is for live workflows; admin dashboard is glance-not-watch |
| (implicit) | Detail panel content: header + tier/source/YAML id + 24-bar history sparkline + collapsed error + recrawl button | Mirrors Core_B's detail panel structure exactly, just rebuilt in HiFi style |

## Architecture

```
                ┌──────────────────────────────────────────┐
                │  <Sites/> (page)                         │
                │  └─ <div className="hf" data-theme=...>  │
                │     ├─ <SitesSummaryBar/>                │
                │     │  └─ status pills + alert banner    │
                │     ├─ <main 2-col layout>               │
                │     │  ├─ <CategoryGroup source=...>     │
                │     │  │   └─ <CompanyCard/> × N        │
                │     │  └─ <SiteDetailPanel company=...>  │
                │     │       ├─ <RunSparkline runs=...>   │
                │     │       └─ <RecrawlButton .../>      │
                │     └─ ...                               │
                └──────────────────────────────────────────┘
                              │       ▲
                              │ polls │
                              ▼       │
                ┌──────────────────────────────────────────┐
                │  /frontend/src/components/sites/api.ts   │
                │  (axios wrappers)                        │
                └──────────────────────────────────────────┘
                              │       ▲
                              │       │
                              ▼       │
                ┌──────────────────────────────────────────┐
                │  Backend /api/sites/* (Phase 1)          │
                │  GET /summary                            │
                │  GET /?source=                           │
                │  GET /{company}/runs?limit=              │
                │  POST /{company}/recrawl                 │
                └──────────────────────────────────────────┘
```

## Components

### 1. `<Sites/>` page — `/frontend/src/pages/Sites.tsx`

Top-level component. Owns the polling lifecycle (8s default; 2s when any recrawl is in flight). Holds:
- `summary: SitesSummaryOut | null` — from `GET /api/sites/summary`.
- `rows: SiteRowOut[] | null` — from `GET /api/sites`.
- `selectedCompany: string | null` — UI state for the right-side detail panel.
- `runs: SiteRunOut[] | null` — from `GET /api/sites/{company}/runs?limit=24`, refetched when `selectedCompany` changes.
- `recrawlInFlight: Set<string>` — companies currently being recrawled (drives the "switch to 2s polling" + button-disabled state).

Wraps body in `<div className="hf" data-theme="sites">`. The `hf` class loads tokens; `data-theme="sites"` is reserved for any `/sites`-only overrides (none today; future-proofing).

Routing: register in `frontend/src/App.tsx` alongside other admin pages — `<Route path="/sites" element={<Sites/>}/>`. Add nav-bar entry "站点节点视图".

### 2. `<SitesSummaryBar/>` — `components/sites/SitesSummaryBar.tsx`

Top strip with three pill counters and an optional alert banner.

```
┌─────────────────────────────────────────────────────────────┐
│ ●运行中 38   ⚠报警 2   ○停用 0     ⊕今日新增 142            │
│  emerald      amber     stone           Fraunces 大字       │
└─────────────────────────────────────────────────────────────┘
```

If `summary.alerted >= 2` AND at least one row has `alert_level==='red'`:
```
┌─────────────────────────────────────────────────────────────┐
│ amber-bg | 今日 N 家爬虫疑似失效（腾讯、中金）— 点这里查看 │
└─────────────────────────────────────────────────────────────┘
```
Click → sets `selectedCompany` to first red row's company.

### 3. `<CategoryGroup/>` — `components/sites/CategoryGroup.tsx`

One container per `source`. Header shows source label translated to human-friendly Chinese:

| Source | Label |
|---|---|
| `internet_official` | 互联网官网 |
| `state_owned_official` | 国央企 |
| `securities_zhiye` / `_hotjob` / `_moka_embedded` / `_zhiye_legacy` | 券商 |
| `consumer_foreign_official` | 消费外企 |

Body: CSS grid of `<CompanyCard/>` elements, ~6 per row at desktop width, gap 12px.

Securities sub-sources collapse into a single "券商" group in the UI (split by sub-source within the group is unnecessary noise).

### 4. `<CompanyCard/>` — `components/sites/CompanyCard.tsx`

Compact card: company name + status dot + today_new + relative last_run_at.

```
┌──────────────┐
│ ● 腾讯        │  ← status dot color from alert_level
│ Fraunces 17px │
│ +12  ·  5h前 │  ← Inter, today_new (terracotta if >0, stone if 0), relative time
└──────────────┘
```

Background `var(--ivory)`, border `box-shadow: 0 0 0 1px var(--border-warm)`, hover lifts to `var(--sh-lift)`. Selected state: `box-shadow: 0 0 0 2px var(--terracotta)`.

Click → sets `selectedCompany` in parent state.

### 5. `<SiteDetailPanel/>` — `components/sites/SiteDetailPanel.tsx`

Right column (~360px wide), sticky. Sections from top to bottom:

1. **Header**: status dot + company name (Fraunces 22px) + tier pill (if known).
2. **Meta**: `source` (mono pill) · YAML id (mono with squiggle underline) · last_run_at relative.
3. **Sparkline**: `<RunSparkline runs={runs}/>` — 24 vertical bars, height = log-scaled `fetched_count`, red=failed, terracotta=success, stone=running.
4. **Error message** (if last run has one): `<details><summary>最近一次错误</summary><pre className="hf-mono-sm">{error_message}</pre></details>`
5. **Recrawl action**: `<RecrawlButton company={company} onSubmitted={...}/>` — terracotta primary, full-width, label "立即重跑这个节点"; disabled with spinner during in-flight recrawl.

When `selectedCompany` is null: show empty placeholder "← 点左侧任意公司查看详情".

### 6. `<RunSparkline/>` — `components/sites/RunSparkline.tsx`

Pure SVG. Props: `runs: SiteRunOut[]` (sorted DESC). Renders up to 24 bars left-to-right (oldest left, newest right).

Bar height = `Math.max(4, Math.log2(fetched_count + 1) * 6)` capped at 40px.
Bar color: `failed → var(--crimson)`, `running → var(--stone)`, `success → var(--terracotta)`.

Below the bars: a 12px caption "最近 24 次 run · X 失败" — Caveat font, stone color (closest match to wireframe note vibe; if Caveat isn't loaded fall back to Inter italic).

### 7. `<RecrawlButton/>` — `components/sites/RecrawlButton.tsx`

```
[ 立即重跑这个节点 ]   → idle, terracotta primary
[ ○ 重跑中…         ]   → submitted, disabled, spinner
```

Click handler:
1. POST `/api/sites/{company}/recrawl`.
2. On 200: parent updates `recrawlInFlight.add(company)`, polling cadence drops to 2s.
3. Watch the `runs` data: when a new `SiteRunOut` row appears for this company with `status === 'success' | 'failed'` AND `started_at > submitTime`, declare done. Toast (top-right, terracotta on success / crimson on failure) + remove from `recrawlInFlight`.
4. On 400/500: error toast.

Toast component: lightweight, no dependency. Auto-dismiss after 4s. Position fixed top-right.

### 8. `api.ts` — `components/sites/api.ts`

Re-uses the project's existing axios instance from `src/api.ts`. Exports typed wrappers:

```typescript
import api from '../../api';

export interface SitesSummary { active, alerted, disabled, total_today_new, last_batch_at, last_batch_status }
export interface SiteRow     { company, source, last_run_at, last_status, today_new, last_error_short, alert_level }
export interface SiteRun     { id, source, started_at, finished_at, status, fetched_count, new_count, error_message, duration_ms }

export const fetchSummary = () => api.get<SitesSummary>('/sites/summary');
export const fetchSites   = (source?: string) => api.get<SiteRow[]>('/sites', { params: source ? { source } : {} });
export const fetchRuns    = (company: string, limit = 24) => api.get<SiteRun[]>(`/sites/${encodeURIComponent(company)}/runs`, { params: { limit } });
export const triggerRecrawl = (company: string) => api.post<{ parent_log_id: number; message: string }>(`/sites/${encodeURIComponent(company)}/recrawl`);
```

## Styling

`/frontend/src/styles/sites-theme.css`:
- Imports `./hifi-tokens.css` (the file copied verbatim from the design-system zip into `frontend/src/styles/hifi-tokens.css`).
- Adds `/sites` page-only layout classes:
  - `.sites-shell` — main 2-col grid (1fr 360px), gap 24px, max-width 1440px, padding 32px.
  - `.sites-summary-bar` — flex row of pills + Fraunces today_new number.
  - `.sites-category-group` — vertical stack with header.
  - `.sites-card-grid` — `display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px;`.
  - `.sites-detail-card` — sticky 360px panel.

Imported once from `Sites.tsx`. Scoped via `.hf` (already in `hifi-tokens.css`) so styles don't leak.

## Polling state machine

```
Initial render
  └─ fetch summary + sites → display
  └─ start interval @ 8s
  
On user click recrawl:
  └─ POST /recrawl
  └─ recrawlInFlight.add(company)
  └─ if interval was 8s → cancel, restart @ 2s

On poll tick:
  └─ fetch summary + sites
  └─ if selectedCompany set → also fetch /runs?limit=24
  └─ for each company in recrawlInFlight:
        if a fresh run row exists with started_at > submitTime AND status in (success, failed):
          recrawlInFlight.delete(company)
          show toast
  └─ if recrawlInFlight is empty AND interval is 2s → restart @ 8s

On unmount:
  └─ cancel interval
```

`submitTime` per recrawl is stored in a Map alongside `recrawlInFlight` so the watch is per-company.

## Empty state

When `summary` has `total_today_new === 0` AND `rows.length === 0`:

Full-page message instead of the 2-col layout:

```
┌────────────────────────────────────────────┐
│                                            │
│       [logo]                               │
│                                            │
│       等首次跑完再回来看  (Fraunces 32px)   │
│                                            │
│       明天 09:00 自动跑全量 tier crawl，    │
│       或现在去 [触发爬取] 手动跑一次。       │
│                                            │
└────────────────────────────────────────────┘
```

The `[触发爬取]` link goes to `/crawl` (existing AntD page with manual trigger button).

## Testing

`/frontend/src/pages/Sites.test.tsx` (vitest + React Testing Library):

1. **renders summary + groups + cards** — mock `/sites/summary` returning sample data, mock `/sites` returning 4 rows across 2 sources; assert 2 `CategoryGroup` headers ("互联网官网" + "券商"), 4 `CompanyCard` instances, status dot colors match alert_level.

2. **click card opens detail panel** — click second card, assert `SiteDetailPanel` shows that company's name, assert `/sites/腾讯/runs?limit=24` was called.

3. **recrawl button POSTs and disables** — click recrawl, assert POST `/sites/{company}/recrawl` called, button shows spinner + disabled.

4. **alert banner shows when alerted ≥ 2 and any red** — mock summary `{alerted: 2}`, mock rows with one `alert_level: 'red'`; assert banner renders + clicking it sets selected company to the red one.

5. **empty state** — mock both endpoints to return zeros / empty array; assert "等首次跑完" message renders.

No Playwright e2e — same discipline as Phase 1.

## File layout

```
frontend/src/
├── pages/
│   ├── Sites.tsx                          # NEW — page-level component
│   └── Sites.test.tsx                     # NEW — vitest unit tests
├── components/sites/                      # NEW
│   ├── SitesSummaryBar.tsx
│   ├── CategoryGroup.tsx
│   ├── CompanyCard.tsx
│   ├── SiteDetailPanel.tsx
│   ├── RunSparkline.tsx
│   ├── RecrawlButton.tsx
│   ├── Toast.tsx                          # tiny, no deps
│   └── api.ts                             # axios wrappers + types
├── styles/
│   ├── hifi-tokens.css                    # NEW — copied verbatim from design-system zip
│   └── sites-theme.css                    # NEW — page-only layout classes
└── App.tsx                                # MODIFY — add <Route path="/sites" .../> + nav entry
```

Modify (1 file):
- `frontend/src/App.tsx` — add route + nav menu entry.

Create (10 files): listed above.

## Verification

- `cd frontend && npm run lint` passes 0 errors.
- `cd frontend && npm test` passes including 5 new tests.
- `cd frontend && npm run build` succeeds (tsc + vite).
- Manual: open `http://localhost:5173/sites` against a backend with seeded `company_crawl_logs` rows. Verify:
  - 2-3 CategoryGroups render.
  - Cards show correct status dots.
  - Click card → detail panel appears with sparkline.
  - Click recrawl on a known-good company (e.g. 腾讯) → toast appears, polling speeds up, eventually a new run row shows in the sparkline.
  - With backend stopped, the page should show stale data + an unobtrusive failure indicator (one Phase 1 coverage gap that Phase 2 inherits — see Q6 of the original review plan; not addressed here).

## Items explicitly out of scope

- **No retry banner on backend down** — the original review plan flagged this (Q6). It's a polling resilience issue independent of the new page; stays out of Phase 2.
- **No source filtering controls in UI** — the API supports `?source=`, but Phase 2 always fetches all sources. Adding a filter dropdown is YAGNI for now.
- **No pagination on company cards** — even with 30+ companies the grid scrolls naturally; no need for paging.
- **No SSE / WebSocket** — polling only. Recrawl completion detection is poll-based, not push-based.
- **No mobile layout** — desktop only. The sticky 360px detail panel doesn't make sense on phone.
