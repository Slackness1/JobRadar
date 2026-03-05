# JobRadar Web App Design

## Overview

Local web application to replace the existing CLI workflow for daily job scraping, filtering, scoring, and export from tatawangshen.com. Single-user, single-process architecture with FastAPI backend and React frontend.

## Goals

- One-click daily job crawling with auto-login via Playwright
- Multi-track keyword+weight scoring with visual editing in browser
- Filterable/sortable job table with expandable details
- Export filtered results to CSV/Excel/JSON
- Scheduled daily crawling via APScheduler
- Replace all existing CLI scripts (`auto_login_scraper.py`, `filter_jobs_v2.py`, `generate_report.py`)

## Architecture

```
React (Vite + Ant Design 5)
    |
    v  REST API (axios, Vite proxy in dev)
FastAPI
    +-- /api/jobs        -> job list/search/filter/detail/stats
    +-- /api/tracks      -> track CRUD + keyword groups
    +-- /api/keywords    -> keyword CRUD
    +-- /api/scoring     -> scoring config + rescore trigger
    +-- /api/exclude     -> exclude rules CRUD
    +-- /api/crawl       -> trigger crawl / status / logs
    +-- /api/scheduler   -> view/update cron config
    +-- /api/export      -> CSV / Excel / JSON export
    |
    +-- APScheduler (embedded, daily cron)
    +-- SQLite (jobradar.db)
    +-- Playwright (headless crawling)
```

Single process. Crawl tasks run in background threads via `asyncio.to_thread`. Dev mode: Vite dev server + FastAPI on separate ports with Vite proxy. Production: build React static files, FastAPI serves them.

## Data Model

### jobs

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | auto |
| job_id | TEXT UNIQUE | platform-side ID, dedup key |
| source | TEXT | "tatawangshen" (extensible) |
| company | TEXT | |
| company_type_industry | TEXT | |
| company_tags | TEXT | |
| department | TEXT | |
| job_title | TEXT | |
| location | TEXT | |
| major_req | TEXT | |
| job_req | TEXT | |
| job_duty | TEXT | |
| publish_date | DATETIME | |
| deadline | DATETIME | |
| detail_url | TEXT | |
| scraped_at | DATETIME | |
| created_at | DATETIME | |

### tracks

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| key | TEXT UNIQUE | "data_analysis" |
| name | TEXT | "数据分析/挖掘" |
| weight | REAL | 1.0 |
| min_score | INTEGER | 15 |
| sort_order | INTEGER | |

### keyword_groups

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| track_id | INTEGER FK | |
| group_name | TEXT | "core", "algorithm_ml" |
| sort_order | INTEGER | |

### keywords

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| group_id | INTEGER FK | |
| word | TEXT | "数据分析" |

### scoring_config

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| config_json | TEXT | JSON blob for scoring weights, thresholds, company tiers, etc. |
| updated_at | DATETIME | |

### exclude_rules

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| category | TEXT | "sales", "design" |
| keyword | TEXT | "销售代表" |

### job_scores

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| job_id | INTEGER FK | references jobs.id |
| track_id | INTEGER FK | references tracks.id |
| score | INTEGER | |
| matched_keywords | TEXT | JSON array |
| scored_at | DATETIME | |

### crawl_logs

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| source | TEXT | |
| started_at | DATETIME | |
| finished_at | DATETIME | |
| status | TEXT | "running" / "success" / "failed" |
| new_count | INTEGER | |
| total_count | INTEGER | |
| error_message | TEXT | |

## API Routes

### Jobs
- `GET /api/jobs` - paginated list with search, track filter, min_score, days, sort
- `GET /api/jobs/{id}` - single job detail
- `GET /api/jobs/stats` - counts by track, total, today's new

### Tracks
- `GET /api/tracks` - all tracks with nested keyword groups and keywords
- `POST /api/tracks` - create track
- `PUT /api/tracks/{id}` - update track name/weight/min_score
- `DELETE /api/tracks/{id}` - delete track and cascade
- `POST /api/tracks/{id}/groups` - add keyword group
- `PUT /api/tracks/{id}/groups/{gid}` - update keyword group
- `DELETE /api/tracks/{id}/groups/{gid}` - delete keyword group

### Keywords
- `POST /api/keywords` - batch add keywords to a group
- `DELETE /api/keywords/{id}` - delete keyword
- `PUT /api/keywords/batch` - batch update

### Scoring
- `GET /api/scoring/config` - get scoring config JSON
- `PUT /api/scoring/config` - update scoring config
- `POST /api/scoring/rescore` - trigger full rescore (background task)

### Exclude Rules
- `GET /api/exclude` - list all
- `POST /api/exclude` - add rule
- `DELETE /api/exclude/{id}` - delete rule

### Crawl
- `POST /api/crawl/trigger` - start crawl (background)
- `GET /api/crawl/status` - current crawl status
- `GET /api/crawl/logs` - crawl history

### Scheduler
- `GET /api/scheduler` - current schedule config
- `PUT /api/scheduler` - update cron expression

### Export
- `POST /api/export/csv` - export filtered jobs as CSV
- `POST /api/export/excel` - export as Excel
- `POST /api/export/json` - export as JSON

All export endpoints accept the same filter params as GET /api/jobs.

## Frontend Pages

### 1. Jobs Overview (main page)
- Top bar: search input, track dropdown, days dropdown, min score input, export button
- Stats cards: total jobs, today's new, per-track counts
- Ant Design Table: company, job_title, location, tracks, total_score, publish_date
- Row expand: full job detail, requirements, matched keywords
- Pagination

### 2. Track Config
- Collapsible panels for each track
- Editable fields: name, weight (slider/input), min_score
- Nested keyword groups with tag-style keyword display
- Add/remove keywords inline
- Add/remove groups
- Save button + rescore button

### 3. Exclude Rules
- Grouped by category (sales, design, etc.)
- Add/remove keywords per category
- Add/remove categories

### 4. Scoring Config
- Edit scoring weight sliders (keyword_match, track_fit, skill_relevance, etc.)
- Company tier editing (tier1/tier2/tier3 company lists)
- Threshold editing
- Rescore button

### 5. Crawl Management
- Trigger button with status indicator
- Progress display during crawl
- History table: time, status, new_count, total_count

### 6. Scheduler
- Current cron expression display
- Edit cron expression
- Next run time preview

## Tech Stack

### Backend
- Python 3.10+
- FastAPI
- SQLAlchemy 2.0 (sync, SQLite)
- APScheduler 3.x
- Playwright (crawling)
- openpyxl (Excel export)

### Frontend
- React 18
- TypeScript
- Vite
- Ant Design 5.x
- axios

## Migration from Existing System

- First startup: auto-import config.yaml into SQLite (tracks, keywords, scoring, exclude rules)
- Provide /api/import/csv endpoint to import existing jobs.csv
- Keep original scripts as reference, not actively used

## Data Flow

1. Crawl: Playwright login -> API pagination -> dedup by job_id -> insert to jobs table
2. Score: For each job, match against all tracks' keywords -> write job_scores
3. View: Frontend queries /api/jobs with filters -> backend joins jobs + job_scores
4. Export: Frontend sends filter params to /api/export -> backend generates file -> download



## Scoring Algorithm

### Formula

```
Single Track Score = Σ (matched keyword count × 2)
Total Score = Σ (track score × track weight)
```

### Scoring Flow

1. **Load Config**
   - Read global config from `scoring_config` table
   - Read track config from `tracks/keyword_groups/keywords` tables

2. **Exclude Filter**
   - Iterate `exclude_rules`, skip job if any keyword matches

3. **Keyword Matching** (per track)
   - Concatenate job text: `job_title + job_req + job_duty + major_req`
   - For each keyword group:
     - Expand synonyms (from `scoring_config.skill_synonyms`)
     - Match → record matched keywords

4. **Calculate Score**
   - `score = matched_count × 2`
   - If `score < track.min_score` → don't record this track score
   - Else → write to `job_scores` table

5. **Frontend Weighting**
   - `total_score = Σ (job_scores.score × tracks.weight)`

### Config Example

```json
{
  "scoring": {
    "keyword_match": 2,
    "recency_bonus_days": 3,
    "recency_multiplier": 1.2
  },
  "skill_synonyms": {
    "Python": {
      "canonical": "Python",
      "synonyms": ["python3", "py"]
    }
  }
}
```

## Deduplication Strategy

### Three-Layer Deduplication

| Layer | Timing | Mechanism | Performance |
|-------|--------|-----------|-------------|
| 1. URL | Pre-crawl | `source_url` UNIQUE constraint | < 1ms |
| 2. Business Key | Insert time | `job_id` UNIQUE constraint | < 1ms |
| 3. Content Hash | Optional | SHA256(normalized text) | ~50ms |

### Crawler Implementation

```python
# 1. Get job_id from API
job_id = record.get("position_id") or record.get("_id")

# 2. Check database
if db.query(Job).filter(Job.job_id == job_id).first():
    continue  # Skip duplicate

# 3. Insert
db.add(Job(job_id=job_id, ...))
```

### Dedup Key Priority

1. `position_id` (from API)
2. `_id` (from API)
3. MD5(company + job_title + location) (fallback)

## Frontend Interaction Flow

### Page Structure

```
/jobs          → Job list (filter/sort/expand)
/tracks        → Track config (keyword editing)
/exclude       → Exclude rules
/scoring       → Scoring weight config
/crawl         → Crawl management (trigger/status)
/scheduler     → Scheduled task config
```

### Jobs Main Page

```
┌─────────────────────────────────────────────────┐
│ [Search] [Track Dropdown] [Days] [Min Score] [Export▼]
├─────────────────────────────────────────────────┤
│ Stats: Total 36,000 | Today 120                 │
│        Data Analysis: 450 | Research: 380 | ... │
├─────────────────────────────────────────────────┤
│ Table:                                          │
│ Company | Job | Location | Tracks | Score | Date│
│ ────────────────────────────────────────────── │
│ Tencent | Data Analyst | Shenzhen | DA,Research | 42│
│   └─ Expand: Requirements/Duty/Matched Keywords│
│                                                 │
│ Pagination: 1 2 3 ... 1800                     │
└─────────────────────────────────────────────────┘
```

### Tracks Config Page

```
┌─────────────────────────────────────────────────┐
│ ▼ Data Analysis [weight: 1.0] [min_score: 15]  │
│   ├─ Core Keywords [Edit]                       │
│   │   Data Analysis, Data Mining, SQL, Python  │
│   ├─ Algorithm/ML [Edit]                        │
│   │   Machine Learning, Deep Learning          │
│   └─ [+ Add Keyword Group]                      │
│                                                 │
│ [+ Add Track] [Rescore] [Save]                 │
└─────────────────────────────────────────────────┘
```

## Export Functionality

### Export Formats

| Format | Use Case | Implementation |
|--------|----------|----------------|
| CSV | Data analysis/backup | `csv.DictWriter` (fast) |
| Excel | Final reports | `xlsxwriter` (styled) |
| JSON | API integration | `json.dumps` (structured) |

### Default Export Fields

```python
DEFAULT_FIELDS = [
    "job_id", "company", "company_type_industry", "department",
    "job_title", "location", "major_req", "publish_date",
    "detail_url", "total_score", "matched_tracks"
]
```

### Export Flow

1. User sets filters (search/track/score/days)
2. Click [Export▼] → Select format
3. Backend queries → Generates file → Returns download
4. Browser downloads: `jobs_2026-03-03.xlsx`

## Scheduled Tasks & Error Handling

### APScheduler Configuration

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        daily_crawl,
        'cron',
        hour=6,
        minute=0,
        id='daily_crawl'
    )
    scheduler.start()
    yield
    scheduler.shutdown()
```

### Error Handling

| Scenario | Handling |
|----------|----------|
| Crawl failure | Write to `crawl_logs` (status='failed', error_message) |
| Scoring error | Catch exception → Skip job → Log |
| API timeout | Retry 3x → Exponential backoff → Log failure |
| Token expired | Re-login via Playwright → Retry |

### Log Structure

```
crawl_logs table:
- id, source, started_at, finished_at
- status: running/success/failed
- new_count, total_count, error_message
```

## Implementation Priority

### Phase 1: Core Backend (1-2 days)
1. FastAPI + SQLAlchemy + SQLite
2. Jobs/Tracks/Keywords models
3. Scorer service (migrate `filter_jobs_v2.py`)
4. Jobs API (list/detail/stats)

### Phase 2: Crawler Integration (1 day)
1. Crawler service (migrate `auto_login_scraper.py`)
2. Crawl API (trigger/status/logs)
3. APScheduler integration

### Phase 3: Frontend (2-3 days)
1. React + Vite + Ant Design
2. Jobs main page (table/filter/expand)
3. Tracks config page
4. Export functionality

### Phase 4: Polish (1 day)
1. Scoring config page
2. Exclude rules page
3. Scheduler config
4. Error handling optimization

## Migration Path from Existing Scripts

| Existing Script | Migrate To |
|-----------------|------------|
| `auto_login_scraper.py` | `backend/app/services/crawler.py` |
| `filter_jobs_v2.py` | `backend/app/services/scorer.py` |
| `config.yaml` | Import to SQLite on first startup |
| `jobs.csv` | `/api/import/csv` endpoint (one-time) |
| `filtered_jobs.csv` | No longer needed, frontend queries in real-time |