# Company Site Re-crawl Queue Design

## Background

Users observed that some companies have more positions on their own career sites than currently captured by existing sources.

Current crawler flow:
- Existing sources: Tata + Haitou
- Trigger modes: manual (`/api/crawl/trigger`) and scheduler
- Limitation: no user-driven company-level website re-crawl queue

User-confirmed requirements:
- User can click a company-level action to request "re-crawl full jobs"
- Target is the company's own career site (not only existing sources)
- Career URL is provided manually by user in UI
- Task executes on next crawl run (manual/scheduled), not immediately
- On failure, task remains recorded as failed for manual retry

## Goals

1. Add a durable "company site re-crawl" queue.
2. Allow queueing from both Jobs overview and CompanyExpand pages.
3. Process queued items at the beginning of next crawl run.
4. Keep failed tasks visible and retryable.
5. Keep existing Tata/Haitou crawl flow stable.

## Non-goals

- Not building full universal extraction for every possible career site in v1.
- Not auto-discovering company career URLs in v1 (manual input only).
- Not introducing destructive replacement of existing job records.

## Recommended Architecture (Approved)

Use "Queue + Adapters + Generic Fallback".

### 1) Persistent Queue Model

Add `company_recrawl_queue` table (SQLite), with fields:
- `id`
- `company`
- `department`
- `career_url`
- `status` (`pending`, `running`, `failed`, `completed`)
- `attempt_count`
- `last_error`
- `created_at`, `updated_at`, `finished_at`
- `next_run_only` (default true)

Constraints:
- Deduplicate active tasks by `(company, department, career_url, status in pending/running)`.

### 2) Frontend Entry Points

Add "重新爬取全量岗位" action in:
- Jobs overview (company row action)
- CompanyExpand page (header action)

Interaction:
- User clicks button
- Modal asks for `career_url`
- Submit creates queue item (`pending`)

### 3) Crawl Orchestration Integration

On each crawl run (manual or scheduler):
1. Run `process_company_recrawl_queue()` first
2. Process all `pending` items (or bounded batch)
3. Continue existing Tata + Haitou flow unchanged

Queue task lifecycle:
- `pending` -> `running` -> `completed`
- `pending` -> `running` -> `failed` (with `last_error`)

### 4) Adapter Strategy

For company site crawling:
- Adapter layer for known ATS patterns (e.g., common job-list APIs/templates)
- Generic fallback extractor for unknown structures (best-effort list/detail extraction)

Result mapping:
- Save into existing `jobs` table
- `source` tagged as `company_site:<domain>`
- `job_id` generated via stable hash from key URL/title signals

## Data Flow

1. User queues company site task from UI.
2. Queue item persisted as `pending`.
3. Next crawl trigger starts:
   - consume queue (company site recrawl)
   - then run normal Tata/Haitou crawl
4. Parsed jobs are upserted into `jobs`.
5. Queue item marked `completed` or `failed`.
6. Failed item can be retried from UI/API.

## API Design (v1)

- `POST /api/recrawl-queue`
  - body: `company`, `department`, `career_url`
  - effect: create `pending` task

- `GET /api/recrawl-queue`
  - query: optional `status`
  - effect: list queue tasks for UI

- `PUT /api/recrawl-queue/{id}/retry`
  - effect: `failed` -> `pending`, clear error

- `DELETE /api/recrawl-queue/{id}` (optional)
  - effect: remove stale task

## Error Handling

- Network failures: short retries (request-level), then task `failed`.
- Parser failures: task `failed` with concise `last_error`.
- Timeout guard per company task to avoid blocking entire crawl.
- If one company task fails, continue with remaining queue tasks.
- Existing Tata/Haitou flow should still execute.

## Security and Safety

- Validate URL schema (`http`/`https`) before queueing.
- Limit crawl scope to provided domain and job pages.
- Do not execute submission workflows.

## Testing and Acceptance

### Backend

- Queue CRUD and status transitions
- Deduplication behavior
- `process_company_recrawl_queue()` lifecycle
- Failure keeps task as `failed`

### Frontend

- Jobs + CompanyExpand button visibility and modal behavior
- Queue submit success/failure feedback
- Retry action updates status correctly

### End-to-end

- Queue task appears as `pending`
- Next crawl run consumes task
- Result status becomes `completed` or `failed`
- Existing source crawls still run in same trigger

## Complexity Assessment

- Overall: medium-high complexity
- Main challenge: heterogeneous company website structures
- Mitigation: phased adapter strategy + fallback parser + explicit failure status

## Rollout Plan

1. Build queue model/API + UI queue action
2. Integrate queue processing in crawl orchestration
3. Add adapter/fallback crawler implementation
4. Add retry and monitoring UX
