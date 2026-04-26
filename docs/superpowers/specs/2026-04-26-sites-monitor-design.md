# Sites Monitor — Design Spec

**Date:** 2026-04-26
**Wireframe reference:** `JobRadar Wireframes.html` 第 07 节 · `wf-core.jsx` Core_B（站点节点视图）
**Status:** Approved by user 2026-04-26 (visual layer deferred to Phase 2 design system)

## Goal

Give the operator a single page to answer two questions every morning:

1. **"Did the crawlers run last night, and which companies got fresh data?"**
2. **"For the company I care about (e.g. 腾讯), is its scraper script still working — and if not, can I retry it without re-running the whole batch?"**

Today the only signal is `MAX(jobs.scraped_at) WHERE company='腾讯'`, which can't tell "脚本跑了 0 条" from "脚本崩了". This spec adds per-company crawl logging and a `/sites` admin page that exposes it.

## Scope (Phase 1 — backend)

In:
- New `company_crawl_logs` table with per-company run records.
- Instrument every per-company crawl call (互联网 / 国央企 / 券商 / 消费外企 / 能源 / 蚂蚁 API — about 6–8 wrap points) with a context manager that writes a row.
- 4 endpoints under `/api/sites/*`.
- A registry of `company → callable` so a single company can be re-crawled without going through the full batch.

Out (Phase 2):
- The `/sites` page UI. Visuals deferred until the user provides a design system. Page will follow Core_B layout (hub + category cards + right detail panel) once design tokens are in.
- Disable/enable a company at runtime (was Q2.c — explicitly skipped).
- In-UI editing of crawler parameters (was Q2.d — skipped, YAML stays the source of truth).

## Decisions log (from brainstorming)

| Q | Decision | Why |
|---|---|---|
| Q1 | **B** — per-company `crawl_logs` rows | Need to distinguish "script ran, 0 results" from "script crashed". Lightweight A loses that. |
| Q2 | **a + b + e** — read-only monitor + single-company recrawl + anomaly banner | Covers 90% of "今天还正常吗 / 不正常先重试一次" workflow. |
| Q3 | **ii** — internet_official + state_owned_official + consumer_foreign_official + securities_* + energy_* + antgroup_api | All "official-website / JS-rendered" sources have the same failure mode. tatawangshen / haitou / legacy CSVs use a different signal (login/import/file), shown only as source-summary cards on the page header. |
| Q4 | **A** — new dedicated route `/sites` | Monitoring (daily glance) and ops (manual trigger) are different workflows; combining them in `/crawl` adds tab-switching friction. |
| Q5 | Deferred — design system pending | UI written in Phase 2 once tokens are provided. |
| Q6 | Route name `/sites` | Matches Core_B's "站点节点视图" semantics. |

## Architecture

```
                 ┌─────────────────────────────────────────────────┐
                 │  Cron @ 08:00 (existing)  →  run_crawl(db)      │
                 │     ├─ creates parent crawl_logs row            │
                 │     └─ for each per-company call:               │
                 │         with company_crawl_log(db,              │
                 │              source, company, parent_log_id):   │
                 │             _crawl_<company>(...)               │
                 │             # body sets log.fetched_count       │
                 │             # body sets log.new_count           │
                 └─────────────────────────────────────────────────┘
                                    │
                                    ▼
                 ┌────────────────────────────┐
                 │  company_crawl_logs (new)  │
                 └────────────────────────────┘
                                    │
                ┌───────────────────┼───────────────────┐
                ▼                   ▼                   ▼
   /api/sites/summary       /api/sites           /api/sites/{c}/runs
   (top KPI)                (list + alert)       (24h sparkline)

                 ┌────────────────────────────┐
                 │  POST /api/sites/{c}/      │
                 │       recrawl              │
                 │     ├─ resolve via         │
                 │     │  COMPANY_CRAWLERS    │
                 │     ├─ BackgroundTasks     │
                 │     ├─ wraps in            │
                 │     │  company_crawl_log   │
                 │     └─ runs scorer if      │
                 │        new_count > 0       │
                 └────────────────────────────┘
```

## Components

### 1. Data model — `company_crawl_logs`

```sql
CREATE TABLE company_crawl_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT    NOT NULL,
    company         TEXT    NOT NULL,
    started_at      DATETIME NOT NULL,
    finished_at     DATETIME,
    status          TEXT    NOT NULL,   -- 'running' | 'success' | 'failed'
    fetched_count   INTEGER NOT NULL DEFAULT 0,
    new_count       INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT    NOT NULL DEFAULT '',
    parent_log_id   INTEGER,            -- FK → crawl_logs.id (logical, not enforced)
    duration_ms     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_ccl_company_started ON company_crawl_logs(company, started_at DESC);
CREATE INDEX idx_ccl_source_started  ON company_crawl_logs(source,  started_at DESC);
CREATE INDEX idx_ccl_parent          ON company_crawl_logs(parent_log_id);
```

`parent_log_id` references the existing `crawl_logs` row representing the umbrella batch (the daily 08:00 multi-source run). Not declared as a SQL FK to avoid coupling DDL — schema_patch.py adds the table; FK enforcement is done at app layer.

`error_message` truncated to 500 chars in the context manager.

The existing `crawl_logs` table is not changed. Per-batch records continue to be written there.

### 2. Crawler instrumentation — `app/services/company_crawl_logger.py`

```python
from contextlib import contextmanager
from datetime import datetime, timezone
import time

@contextmanager
def company_crawl_log(db, *, source: str, company: str, parent_log_id: int | None):
    log = CompanyCrawlLog(
        source=source,
        company=company,
        parent_log_id=parent_log_id,
        started_at=datetime.now(timezone.utc),
        status='running',
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    start = time.monotonic()
    try:
        yield log
        log.status = 'success'
    except Exception as exc:
        log.status = 'failed'
        log.error_message = str(exc)[:500]
        raise
    finally:
        log.finished_at = datetime.now(timezone.utc)
        log.duration_ms = int((time.monotonic() - start) * 1000)
        db.commit()
```

Body sets `log.fetched_count` and `log.new_count` directly on the yielded log object. Existing per-company crawl functions already compute new-vs-existing counts when they call `merge_job_fields` — those values get assigned in the with-block.

### 3. Wrap points

In `app/services/legacy_crawlers/crawler.py`:

| Source | Wrap point |
|---|---|
| `internet_official` | `_crawl_internet_targets` — wrap each iteration of `targets`, with `company=target.company` |
| `state_owned_official` | `_crawl_state_owned_official_targets` — same loop pattern |
| `consumer_foreign_official` | `_crawl_consumer_foreign_official` |
| `securities_zhiye` | `_crawl_securities_zhiye_targets` |
| `securities_hotjob` | `_crawl_securities_hotjob_targets` |
| `securities_moka_embedded` | `_crawl_securities_moka_embedded_targets` |
| `energy_hotjob` / `energy_csisolar` / `energy_moka` / `energy_moka_embedded` / `energy_zhiye` / `energy_51job_campus` | each respective `_crawl_*_targets` |
| `antgroup_api` | `_crawl_antgroup_api` (one entry, company=蚂蚁集团) |

Each wrap is purely additive — the with-block surrounds the existing call without modifying business logic.

### 4. API — 4 endpoints under `/api/sites/*`

#### `GET /api/sites/summary`

```json
{
  "active": 38,                       // alert_level='green' count
  "alerted": 2,                       // alert_level in ('yellow','red') count
  "disabled": 0,                      // companies present in COMPANY_CRAWLERS registry but with no run rows
  "total_today_new": 142,             // SUM(new_count) WHERE started_at >= today_00:00 Asia/Shanghai
  "last_batch_at": "2026-04-26T00:00:12+08:00",
  "last_batch_status": "success"
}
```

#### `GET /api/sites?source=internet_official`

Returns one row per (source, company) with the latest run state:

```json
[{
  "company": "腾讯",
  "source": "internet_official",
  "last_run_at": "2026-04-26T08:14:22+08:00",
  "last_status": "success",
  "today_new": 12,
  "last_error_short": "",
  "alert_level": "green"
}]
```

`source` query param optional; when omitted, returns all sources.

#### `GET /api/sites/{company}/runs?limit=24`

Returns the last N runs for the company across all its sources. Used for the 24h sparkline in Core_B's right panel.

```json
[{
  "id": 4521,
  "source": "internet_official",
  "started_at": "...",
  "finished_at": "...",
  "status": "success",
  "fetched_count": 38,
  "new_count": 12,
  "error_message": "",
  "duration_ms": 8421
}]
```

#### `POST /api/sites/{company}/recrawl`

Body: empty.

Behavior:
1. Look up `company` in `COMPANY_CRAWLERS` registry. If absent → 400.
2. Create a parent `crawl_logs` row with `source=f"recrawl:{company}"`, status=`running`.
3. Schedule `BackgroundTasks` task that:
   - Opens a fresh `SessionLocal()`.
   - Wraps registry callable in `company_crawl_log`.
   - On success and `new_count > 0`, calls `score_all_jobs(db)`.
   - Updates the parent `crawl_logs` row finish state.
4. Returns `{ "parent_log_id": int, "message": "已启动" }`.

Frontend polls `/api/sites/{company}/runs?limit=1` to see the result.

### 5. `COMPANY_CRAWLERS` registry — `app/services/company_crawler_registry.py`

```python
from typing import Callable
from sqlalchemy.orm import Session

CompanyCrawler = Callable[[Session, int], None]
# signature: (db, parent_log_id) -> None
# implementation responsibility: open `with company_crawl_log(db, source=..., company=..., parent_log_id=parent_log_id) as log:` and run

COMPANY_CRAWLERS: dict[str, CompanyCrawler] = {
    '腾讯':     _recrawl_tencent,
    '阿里巴巴': _recrawl_alibaba,
    '蚂蚁集团': _recrawl_antgroup,
    '字节跳动': _recrawl_bytedance,
    '美团':     _recrawl_meituan,
    '京东':     _recrawl_jd,
    '快手':     _recrawl_kuaishou,
    '拼多多':   _recrawl_pdd,
    # ... rest of internet_official 16
    '中金公司': _recrawl_cicc,
    '中信建投': _recrawl_csc,
    # ... securities / state_owned / consumer_foreign / energy
}
```

Each `_recrawl_*` is a thin shim called only by `POST /api/sites/{company}/recrawl`. It opens its own `with company_crawl_log(...)` block and invokes the existing per-company crawl function inside.

The daily-batch path is independent: `_crawl_internet_targets` (and the other batch loops in §3) opens `with company_crawl_log(...)` inline around each iteration. So a per-company log row gets one writer at a time — either the batch loop (during cron) or the shim (during `/recrawl`), never both.

For 蚂蚁集团 specifically, the shim runs both `campus_graduates` and `campus_interns` in sequence — it logs as one run (single `company_crawl_logs` row). Captured in CLAUDE.md.

### 6. Alert level rule

```python
def alert_level(runs: list[CompanyCrawlLog], now: datetime) -> Literal['green','yellow','red','unknown']:
    if not runs:
        return 'unknown'                      # never ran or no entry in registry
    last = runs[0]
    if last.status == 'failed':
        if len(runs) >= 2 and runs[1].status == 'failed':
            return 'red'                      # 2 consecutive failures → script likely broken
        return 'yellow'                       # one-off failure
    # last is 'success'
    days_since_new = (now - max((r.started_at for r in runs if r.new_count > 0), default=now - timedelta(days=999))).days
    if days_since_new >= ALERT_STALE_DAYS:
        return 'yellow'                       # script runs but yields nothing
    return 'green'
```

`ALERT_STALE_DAYS = 3`, lifted to `app.config` so it can be tuned without a redeploy.

## Migration

`schema_patch.py` adds:
- `CREATE TABLE IF NOT EXISTS company_crawl_logs ...`
- 3 indexes via `CREATE INDEX IF NOT EXISTS ...`

No backfill — historical runs are not retro-attributed (we don't have per-company breakdown for old `crawl_logs` rows). The first run after deploy starts populating.

## Testing

Unit tests under `backend/tests/`:

- `test_company_crawl_logger.py` — context manager: success path, exception path (verifies status, finish_at, error_message truncation, duration_ms).
- `test_alert_level.py` — table-driven cases for green / yellow / red / unknown.
- `test_sites_router.py` — 4 endpoints with seeded `company_crawl_logs` fixtures, including:
  - `summary` with mixed alert levels.
  - `list` filtered by source.
  - `recrawl` validates registry lookup and 400 on unknown company.

Integration: smoke test that runs `_crawl_internet_targets` against a mocked HTTP layer and asserts one `company_crawl_logs` row per `InternetCrawlTarget`.

## Verification

- After deploy, the next 08:00 cron should populate one `company_crawl_logs` row per per-company call. `SELECT company, COUNT(*) FROM company_crawl_logs WHERE date(started_at) = date('now') GROUP BY company` should return ~16 互联网 + ~9 央国企 + ~N 券商 + … rows.
- `curl http://127.0.0.1:8000/api/sites/summary` returns a JSON dict with non-zero `active`.
- `curl -X POST http://127.0.0.1:8000/api/sites/腾讯/recrawl` returns 200 within 200ms; subsequent `GET /api/sites/腾讯/runs?limit=1` shows a fresh run.
- Trigger a deliberate failure (e.g. monkey-patch `_crawl_tencent_careers` to raise) and verify `alert_level=red` after 2 consecutive failures.

## Phase 2 placeholder

The `/sites` page UI will be built in a separate spec/plan once the design system is provided. The endpoints in this spec are the contract — UI consumes them as-is. Layout intent: Core_B (hub + category cards + right detail panel + recrawl button + 24h sparkline + top alert banner driven by `summary.alerted`).

## Items explicitly out of scope

- No automated alert fan-out (Slack/email/IM). Page UI banner only — deferred per Q2.
- No edit-in-UI for YAML crawler config. YAML stays the source of truth.
- No rate-limiting on `POST /recrawl`. Single operator, internal admin; trivially abusable but irrelevant given user count = 1.
- No retention policy on `company_crawl_logs`. Will be added in a later spec if rows grow >1M (current order-of-magnitude estimate: ~40 rows/day → 14k/year).
