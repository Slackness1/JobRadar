# Company Site Re-crawl Queue Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a durable company-site re-crawl queue so users can submit a company career URL from Jobs/CompanyExpand, then have the next crawl run process that company site before normal Tata/Haitou crawling.

**Architecture:** Implement a dedicated `company_recrawl_queue` table with status lifecycle (`pending/running/failed/completed`), expose queue APIs, add frontend queue actions, and integrate queue consumption into `run_crawl()`. Use adapter-based extraction for known ATS patterns and generic fallback parsing for unknown structures, while preserving existing multi-source crawl flow.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite schema patching, requests/Playwright-compatible crawling, React + Ant Design.

---

### Task 1: Add Queue Data Model and Schema Compatibility

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/services/schema_patch.py`
- Test: `backend/tests/test_company_recrawl_schema.py`

**Step 1: Write the failing test**

```python
def test_schema_patch_adds_company_recrawl_queue_table():
    # Arrange in-memory sqlite engine
    # Act: call ensure_compatible_schema(engine)
    # Assert: sqlite_master contains company_recrawl_queue table
    # Assert: required columns exist (company, department, career_url, status, attempt_count)
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_company_recrawl_schema.py::test_schema_patch_adds_company_recrawl_queue_table -v`
Expected: FAIL because table/model does not exist.

**Step 3: Write minimal implementation**

```python
class CompanyRecrawlQueue(Base):
    __tablename__ = "company_recrawl_queue"
    id = Column(Integer, primary_key=True)
    company = Column(Text, nullable=False, index=True)
    department = Column(Text, default="")
    career_url = Column(Text, nullable=False)
    status = Column(Text, default="pending")
    attempt_count = Column(Integer, default=0)
    last_error = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
```

Also create table in `ensure_compatible_schema()` if missing.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_company_recrawl_schema.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/models.py backend/app/services/schema_patch.py backend/tests/test_company_recrawl_schema.py
git commit -m "feat: add company recrawl queue model and schema patch"
```

### Task 2: Implement Queue Service and API Endpoints

**Files:**
- Create: `backend/app/services/company_recrawl_queue.py`
- Create: `backend/app/routers/company_recrawl.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_company_recrawl_api.py`

**Step 1: Write the failing test**

```python
def test_create_list_retry_company_recrawl_queue(client):
    create = client.post('/api/recrawl-queue', json={
        'company': 'Acme', 'department': 'Campus', 'career_url': 'https://careers.acme.com/jobs'
    })
    assert create.status_code == 200

    lst = client.get('/api/recrawl-queue?status=pending')
    assert lst.status_code == 200
    assert len(lst.json()['items']) == 1

    retry = client.put(f"/api/recrawl-queue/{create.json()['id']}/retry")
    assert retry.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_company_recrawl_api.py::test_create_list_retry_company_recrawl_queue -v`
Expected: FAIL with 404/missing schemas.

**Step 3: Write minimal implementation**

```python
# router endpoints
POST /api/recrawl-queue
GET /api/recrawl-queue
PUT /api/recrawl-queue/{id}/retry
DELETE /api/recrawl-queue/{id}

# service rules
- dedupe active pending/running by (company, department, career_url)
- retry sets failed->pending and clears last_error
```

Add Pydantic schemas for in/out payloads.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_company_recrawl_api.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/company_recrawl_queue.py backend/app/routers/company_recrawl.py backend/app/schemas.py backend/app/main.py backend/tests/test_company_recrawl_api.py
git commit -m "feat: add company recrawl queue APIs and service"
```

### Task 3: Add Frontend Queue Actions in Jobs and CompanyExpand

**Files:**
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/pages/Jobs.tsx`
- Modify: `frontend/src/pages/CompanyExpand.tsx`
- Test: `frontend/src/pages/__tests__/companyRecrawlActions.test.tsx`

**Step 1: Write the failing test**

```tsx
it('submits recrawl request from company expand modal', async () => {
  // render CompanyExpand with company+department
  // click "重新爬取全量岗位"
  // enter URL and submit
  // assert API called with company/department/career_url
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- companyRecrawlActions.test.tsx`
Expected: FAIL because action/modal/API method missing.

**Step 3: Write minimal implementation**

```tsx
export const addCompanyRecrawlTask = (payload) => api.post('/recrawl-queue', payload);

// Jobs + CompanyExpand
- add button: "重新爬取全量岗位"
- add modal with career_url input
- submit calls addCompanyRecrawlTask({ company, department, career_url })
- show success/error message
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- companyRecrawlActions.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/api/index.ts frontend/src/pages/Jobs.tsx frontend/src/pages/CompanyExpand.tsx frontend/src/pages/__tests__/companyRecrawlActions.test.tsx
git commit -m "feat: add company recrawl queue actions in jobs pages"
```

### Task 4: Build Company-Site Crawler Adapter + Fallback Service

**Files:**
- Create: `backend/app/services/company_site_recrawl.py`
- Test: `backend/tests/test_company_site_recrawl.py`
- Test fixtures: `backend/tests/fixtures/company_site_*.html`

**Step 1: Write the failing test**

```python
def test_extract_jobs_with_adapter_or_fallback():
    html = load_fixture('company_site_unknown_template.html')
    jobs = extract_company_jobs(url='https://careers.acme.com/jobs', html=html)
    assert len(jobs) > 0
    assert jobs[0]['job_title']
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_company_site_recrawl.py::test_extract_jobs_with_adapter_or_fallback -v`
Expected: FAIL because service does not exist.

**Step 3: Write minimal implementation**

```python
def crawl_company_site_task(task) -> tuple[list[dict], str]:
    # detect adapter by domain/signature
    # known adapter -> parse
    # else generic fallback parser
    # return normalized job records
```

Normalization should map to existing `jobs` schema and set `source=company_site:<domain>`.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_company_site_recrawl.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/company_site_recrawl.py backend/tests/test_company_site_recrawl.py backend/tests/fixtures/company_site_*.html
git commit -m "feat: add company site recrawl parser with adapter fallback"
```

### Task 5: Integrate Queue Processing into Main Crawl Pipeline

**Files:**
- Modify: `backend/app/services/crawler.py`
- Modify: `backend/app/routers/crawl.py`
- Modify: `backend/app/services/scheduler_service.py`
- Test: `backend/tests/test_run_crawl_queue_integration.py`

**Step 1: Write the failing test**

```python
def test_run_crawl_processes_pending_company_recrawls_before_sources(monkeypatch):
    order = []
    monkeypatch.setattr('app.services.crawler.process_company_recrawl_queue', lambda *a, **k: order.append('queue'))
    monkeypatch.setattr('app.services.crawler.run_haitou_crawl', lambda *a, **k: (0, 0))
    # execute run_crawl(...)
    assert order[0] == 'queue'
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_run_crawl_queue_integration.py::test_run_crawl_processes_pending_company_recrawls_before_sources -v`
Expected: FAIL because queue step not integrated.

**Step 3: Write minimal implementation**

```python
def run_crawl(...):
    queue_new, queue_total = process_company_recrawl_queue(db, existing_jobs)
    # then existing Tata + Haitou flow
```

Ensure failures mark queue item `failed` and preserve error info.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_run_crawl_queue_integration.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/crawler.py backend/app/routers/crawl.py backend/app/services/scheduler_service.py backend/tests/test_run_crawl_queue_integration.py
git commit -m "feat: process company recrawl queue in crawl pipeline"
```

### Task 6: Add Queue Status/Retry UI and Startup Recovery

**Files:**
- Modify: `frontend/src/pages/Crawl.tsx`
- Modify: `frontend/src/api/index.ts`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_company_recrawl_startup_recovery.py`

**Step 1: Write the failing test**

```python
def test_startup_recovers_running_queue_items(db_session):
    # insert queue item with status='running'
    # call startup recovery hook
    # assert status becomes 'failed' (or pending, per design)
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_company_recrawl_startup_recovery.py::test_startup_recovers_running_queue_items -v`
Expected: FAIL because recovery logic missing.

**Step 3: Write minimal implementation**

```python
# main.py startup
- recover stale queue items left in running state
- set to failed with interruption reason

# Crawl.tsx
- display recrawl queue list/status
- add retry button for failed items
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_company_recrawl_startup_recovery.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/main.py frontend/src/pages/Crawl.tsx frontend/src/api/index.ts backend/tests/test_company_recrawl_startup_recovery.py
git commit -m "feat: add recrawl queue status UI and startup recovery"
```

### Task 7: End-to-End Verification and Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/plans/2026-03-05-company-site-recrawl-design.md` (if needed for final clarifications)

**Step 1: Add user-facing docs**

Document:
- How to queue a company recrawl URL
- Queue lifecycle statuses
- Retry behavior for failed tasks

**Step 2: Run full verification**

Run:
- `pytest backend/tests -v`
- `python -m compileall backend/app -q`
- `npm --prefix frontend run build`
- `docker compose -p jobscraper up -d --force-recreate backend frontend`
- API smoke checks for `/api/recrawl-queue` and `/api/crawl/trigger`

Expected:
- All tests pass
- Build passes
- Queue flow works: create pending -> next crawl consumes -> completed/failed

**Step 3: Commit docs and final adjustments**

```bash
git add README.md docs/plans/2026-03-05-company-site-recrawl-design.md
git commit -m "docs: add company site recrawl queue usage and lifecycle"
```
