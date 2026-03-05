# Haitou + Spring Filter + Track Paste Import Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate Haitou campus scraping into the existing crawl pipeline, store full data in backend, enforce a global default-on spring display filter from 2026-02-01 for all sources, and add JSON paste full-overwrite import for track configuration.

**Architecture:** Keep a unified `jobs` table with source tagging (`tatawangshen` + `haitou_xyzp`), orchestrate dual-source crawl from one trigger, and apply the spring cutoff at query-time via a persisted global toggle. Add a strict JSON config import endpoint that validates and atomically replaces tracks/groups/keywords and linked scoring settings.

**Tech Stack:** FastAPI, SQLAlchemy, APScheduler, requests/BeautifulSoup (or lxml) for scraping, React + Ant Design frontend, pytest for backend tests.

---

### Task 1: Add global system config for spring-display toggle

**Files:**
- Create: `backend/app/services/system_config.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_system_config.py`

**Step 1: Write the failing test**

```python
def test_default_spring_filter_is_enabled(client):
    r = client.get('/api/system-config/spring-display')
    assert r.status_code == 200
    assert r.json()['enabled'] is True
    assert r.json()['cutoff_date'] == '2026-02-01'
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_system_config.py::test_default_spring_filter_is_enabled -v`
Expected: FAIL with missing route/service/model.

**Step 3: Write minimal implementation**

```python
# models.py
class SystemConfig(Base):
    __tablename__ = 'system_config'
    id = Column(Integer, primary_key=True)
    key = Column(Text, unique=True, nullable=False)
    value = Column(Text, nullable=False, default='')
    updated_at = Column(DateTime, default=datetime.utcnow)

# system_config.py
SPRING_KEY = 'spring_display_filter'
DEFAULT = {'enabled': True, 'cutoff_date': '2026-02-01'}
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_system_config.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/models.py backend/app/schemas.py backend/app/services/system_config.py backend/app/main.py backend/tests/test_system_config.py
git commit -m "feat: add persisted spring display system config"
```

### Task 2: Expose system-config API and wire Exclude page toggle

**Files:**
- Create: `backend/app/routers/system_config.py`
- Modify: `backend/app/main.py`
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/pages/Exclude.tsx`
- Test: `backend/tests/test_system_config_api.py`

**Step 1: Write the failing test**

```python
def test_update_spring_filter_toggle(client):
    r = client.put('/api/system-config/spring-display', json={'enabled': False})
    assert r.status_code == 200
    assert r.json()['enabled'] is False
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_system_config_api.py::test_update_spring_filter_toggle -v`
Expected: FAIL with 404 or schema error.

**Step 3: Write minimal implementation**

```python
@router.get('/spring-display')
def get_spring_display(...):
    return service.get_spring_display_config(db)

@router.put('/spring-display')
def set_spring_display(payload: SpringDisplayConfigIn, ...):
    return service.set_spring_display_config(db, payload)
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_system_config_api.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/routers/system_config.py backend/app/main.py frontend/src/api/index.ts frontend/src/pages/Exclude.tsx backend/tests/test_system_config_api.py
git commit -m "feat: add spring display toggle API and exclude page switch"
```

### Task 3: Apply global spring filter to jobs/stats/company-expand/export

**Files:**
- Modify: `backend/app/routers/jobs.py`
- Modify: `backend/app/services/exporter.py`
- Modify: `backend/app/routers/export.py`
- Modify: `backend/app/services/system_config.py`
- Test: `backend/tests/test_spring_filter_queries.py`

**Step 1: Write the failing test**

```python
def test_jobs_list_hides_pre_cutoff_when_enabled(client, seed_jobs):
    r = client.get('/api/jobs/?page=1&page_size=50')
    ids = {x['job_id'] for x in r.json()['items']}
    assert 'pre_cutoff_job' not in ids
    assert 'post_cutoff_job' in ids
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_spring_filter_queries.py::test_jobs_list_hides_pre_cutoff_when_enabled -v`
Expected: FAIL because old jobs still returned.

**Step 3: Write minimal implementation**

```python
cfg = get_spring_display_config(db)
if cfg.enabled:
    cutoff = parse_bj_midnight(cfg.cutoff_date)
    query = query.filter(Job.publish_date >= cutoff)
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_spring_filter_queries.py -v`
Expected: PASS for list/stats/company-expand/export.

**Step 5: Commit**

```bash
git add backend/app/routers/jobs.py backend/app/services/exporter.py backend/app/routers/export.py backend/app/services/system_config.py backend/tests/test_spring_filter_queries.py
git commit -m "feat: enforce global spring cutoff on display and export APIs"
```

### Task 4: Implement Haitou scraper parser (list + detail)

**Files:**
- Create: `backend/app/services/haitou_crawler.py`
- Create: `backend/app/services/haitou_parser.py`
- Test: `backend/tests/test_haitou_parser.py`
- Test fixtures: `backend/tests/fixtures/haitou_list.html`, `backend/tests/fixtures/haitou_detail.html`

**Step 1: Write the failing test**

```python
def test_parse_haitou_detail_extracts_job_fields(detail_html):
    data = parse_detail(detail_html, 'https://xyzp.haitou.cc/article/3494119.html')
    assert data['company']
    assert data['job_title']
    assert data['job_req']
    assert data['publish_date'] is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_haitou_parser.py::test_parse_haitou_detail_extracts_job_fields -v`
Expected: FAIL with missing parser.

**Step 3: Write minimal implementation**

```python
def parse_list(html: str) -> list[str]:
    return sorted(set(article_urls))

def parse_detail(html: str, url: str) -> dict:
    return {
        'job_id': md5(...),
        'source': 'haitou_xyzp',
        'company': company,
        'job_title': title,
        'location': location,
        'job_req': req,
        'job_duty': duty,
        'publish_date': start_date,
        'detail_url': url,
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_haitou_parser.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/haitou_crawler.py backend/app/services/haitou_parser.py backend/tests/test_haitou_parser.py backend/tests/fixtures/haitou_list.html backend/tests/fixtures/haitou_detail.html
git commit -m "feat: add haitou parser and crawler primitives"
```

### Task 5: Integrate Haitou crawler into crawl trigger and scheduler

**Files:**
- Modify: `backend/app/services/crawler.py`
- Modify: `backend/app/routers/crawl.py`
- Modify: `backend/app/services/scheduler_service.py`
- Modify: `backend/app/schemas.py`
- Test: `backend/tests/test_crawl_orchestration.py`

**Step 1: Write the failing test**

```python
def test_trigger_crawl_runs_tata_then_haitou(monkeypatch, client):
    order = []
    monkeypatch.setattr('app.services.crawler.run_tata_crawl', lambda *a, **k: order.append('tata'))
    monkeypatch.setattr('app.services.crawler.run_haitou_crawl', lambda *a, **k: order.append('haitou'))
    client.post('/api/crawl/trigger')
    assert order == ['tata', 'haitou']
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_crawl_orchestration.py::test_trigger_crawl_runs_tata_then_haitou -v`
Expected: FAIL with missing orchestration split.

**Step 3: Write minimal implementation**

```python
def run_crawl(...):
    tata_log = run_tata_crawl(...)
    haitou_log = run_haitou_crawl(...)
    return merge_logs(tata_log, haitou_log)
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_crawl_orchestration.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/services/crawler.py backend/app/routers/crawl.py backend/app/services/scheduler_service.py backend/app/schemas.py backend/tests/test_crawl_orchestration.py
git commit -m "feat: orchestrate tata and haitou in unified crawl flow"
```

### Task 6: Add track JSON paste import API with full overwrite

**Files:**
- Modify: `backend/app/routers/tracks.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/app/services/track_importer.py`
- Test: `backend/tests/test_track_json_import.py`

**Step 1: Write the failing test**

```python
def test_track_json_import_full_overwrite(client, seed_tracks):
    payload = {"tracks": [{"key": "new_track", "name": "New", "weight": 1.2, "min_score": 10, "groups": [{"group_name": "g1", "keywords": ["a", "b"]}]}]}
    r = client.post('/api/tracks/import-json', json=payload)
    assert r.status_code == 200
    assert r.json()['replaced'] is True
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_track_json_import.py::test_track_json_import_full_overwrite -v`
Expected: FAIL with missing endpoint.

**Step 3: Write minimal implementation**

```python
def import_tracks_json_full_replace(db, payload):
    validate(payload)
    with db.begin_nested():
        delete_all_tracks_graph(db)
        recreate_tracks_graph(db, payload)
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_track_json_import.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/routers/tracks.py backend/app/schemas.py backend/app/services/track_importer.py backend/tests/test_track_json_import.py
git commit -m "feat: support JSON paste full-overwrite track import"
```

### Task 7: Add frontend paste-import UX in Tracks page

**Files:**
- Modify: `frontend/src/pages/Tracks.tsx`
- Modify: `frontend/src/api/index.ts`
- Test (optional UI): `frontend/src/pages/__tests__/Tracks.import.test.tsx`

**Step 1: Write the failing test**

```tsx
it('submits JSON payload to import endpoint', async () => {
  // render Tracks page, paste JSON, click import, assert API called
});
```

**Step 2: Run test to verify it fails**

Run: `npm --prefix frontend run test -- Tracks.import.test.tsx`
Expected: FAIL because UI/handler absent.

**Step 3: Write minimal implementation**

```tsx
<TextArea value={jsonText} onChange={...} />
<Button onClick={handleImport}>粘贴导入(JSON)</Button>
```

**Step 4: Run test to verify it passes**

Run: `npm --prefix frontend run test -- Tracks.import.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/pages/Tracks.tsx frontend/src/api/index.ts frontend/src/pages/__tests__/Tracks.import.test.tsx
git commit -m "feat: add JSON paste import UI for track full overwrite"
```

### Task 8: Verify and document operations

**Files:**
- Modify: `README.md`
- Modify: `.env.example` (or `.env` template docs)
- Test: N/A (verification commands)

**Step 1: Add docs for new settings/endpoints**

```md
- HAITOU crawl source
- spring display toggle behavior
- track JSON import schema example
```

**Step 2: Run full verification**

Run:
- `pytest backend/tests -v`
- `python -m compileall backend/app -q`
- `npm --prefix frontend run build`
- `docker compose -p jobscraper restart backend frontend`

Expected:
- tests pass
- no compile errors
- frontend build succeeds
- APIs respond 200

**Step 3: Commit docs and verification fixes**

```bash
git add README.md .env.example
git commit -m "docs: describe haitou source spring filter and track json import"
```
