# Haitou Integration + Spring Display Filter + Track Paste Import Design

## Context

- Existing system already crawls Tata and stores jobs in unified table `jobs`.
- User needs a second source: `https://xyzp.haitou.cc/zxxz/` (no login), where complete requirement text is in detail pages.
- User requires storing all scraped data in backend, but frontend should default to displaying only jobs from Beijing-time `2026-02-01 00:00:00` onward.
- User also requires:
  - A global display toggle in Exclude page for the spring filter.
  - Track config paste import (JSON), with full overwrite semantics.

## Goals

1. Add Haitou source crawler and integrate into existing crawl trigger flow.
2. Keep full raw job dataset in database.
3. Enforce display-layer filtering by configurable switch (default ON), applying to all sources.
4. Support JSON paste import to fully replace track/weight/keyword config.

## Non-Goals

- No change to scoring algorithm logic itself.
- No multi-format import for track config in first version (JSON only).
- No deletion of historical data before `2026-02-01`.

## Proposed Architecture

### 1) Unified Dual-Source Crawl Orchestration

- Extend crawl trigger pipeline (`/api/crawl/trigger` and scheduler job):
  - Step A: run existing Tata crawler.
  - Step B: run new Haitou crawler.
- Use one aggregated crawl log for user-facing status, with per-source sub-metrics attached to error message/metadata.

### 2) Haitou Crawler Strategy

- Entry: list pages under `https://xyzp.haitou.cc/zxxz/` and pagination endpoints.
- Collect article/detail URLs (`/article/<id>.html`).
- Open each detail page to extract:
  - company name
  - job title(s)
  - location
  - publish/apply window
  - job requirement/duty text
  - detail URL
- Normalize into existing `Job` schema:
  - `source = "haitou_xyzp"`
  - `job_id = stable hash(source + detail_url + job_title)`
  - `publish_date`: parse from apply window start; fallback to scraped time with inferred flag behavior (implementation detail)

### 3) Display Filter as Configurable Policy

- Add system config item: `spring_2026_filter_enabled` (default `true`).
- Filter rule when enabled:
  - only return jobs where `publish_date >= 2026-02-01 00:00:00` in Asia/Shanghai interpretation.
- Apply rule consistently to:
  - `/api/jobs`
  - `/api/jobs/stats`
  - `/api/jobs/company-expand`
  - export endpoints (recommended to avoid user confusion)
- Database remains full-fidelity; this is query-time filtering.

### 4) Exclude Page Toggle

- Add a switch card in `Exclude` page for spring filter policy.
- Load initial state from backend.
- Persist user changes via dedicated config API.
- UI default ON and deterministic startup behavior.

### 5) Track Paste Import (JSON, Full Overwrite)

- Add paste area + import button in Track config page.
- JSON schema includes tracks, groups, keywords, weight/min_score/sort_order.
- Backend validates payload then performs transactional full replace:
  - delete existing tracks/groups/keywords
  - recreate from payload
  - optionally update scoring config weights alignment
- Return applied counts and validation errors.

## Data Flow

1. User clicks crawl trigger.
2. Backend runs Tata then Haitou crawler.
3. New jobs are upserted into `jobs` with source distinction.
4. Scoring runs on newly inserted jobs.
5. Frontend job list requests hit API.
6. API checks spring filter config; if enabled, apply 2026-02-01 threshold.
7. User can toggle filter in Exclude page; subsequent requests reflect new state.

## Error Handling

- Haitou page-level failures are non-fatal; continue with other pages/details.
- Repeated request failures use bounded retry + backoff.
- Parse failure captures URL + reason for diagnostics.
- Track paste import uses strict validation and transaction rollback on any fatal issue.

## Testing Strategy

### Backend

- Unit tests:
  - Haitou list/detail parser fixtures.
  - publish date parsing from apply window text.
  - display filter enabled/disabled behavior in list/stats/company-expand.
  - track JSON validation and overwrite transaction behavior.
- Integration tests:
  - crawl trigger runs dual-source flow.
  - dedupe behavior for repeated crawl.

### Frontend

- Exclude page toggle load/save behavior.
- Jobs page default view with filter ON.
- Track paste import success/error UX.

### End-to-End

- Run crawl once, confirm DB includes pre-threshold data.
- Confirm frontend default hides pre-threshold data.
- Toggle OFF and confirm full dataset appears.

## Risks and Mitigations

- Haitou DOM changes: isolate selectors and keep parser fallback strategy.
- Date text variability: multi-pattern parser with monitored fallback counts.
- Full overwrite misuse: require explicit confirm action in UI before submit.

## Acceptance Criteria

1. Crawl trigger ingests both Tata and Haitou jobs.
2. DB stores complete data (no hard deletion by date).
3. Frontend default shows only jobs from `2026-02-01` onward for all sources.
4. Exclude page switch controls this behavior globally.
5. Track JSON paste import fully replaces existing track config in one operation.
