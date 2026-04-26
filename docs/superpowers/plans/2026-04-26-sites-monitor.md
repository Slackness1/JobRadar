# Sites Monitor — Phase 1 (Backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-company crawl logging + 4 read/write endpoints under `/api/sites/*` so an operator can answer "did 腾讯's scraper run today, did it work, can I retry it" without running SQL by hand.

**Architecture:** New `company_crawl_logs` SQLite table populated by a context manager wrapped around every per-company crawl call across 6 orchestrator modules. Four FastAPI endpoints expose summary, list, run history, and per-company recrawl. A `COMPANY_CRAWLERS` registry maps company names to thin recrawl shims that reuse existing leaf scrapers.

**Tech Stack:** FastAPI · SQLAlchemy · pytest · pydantic v2. UI is Phase 2 — not in scope.

**Spec:** `docs/superpowers/specs/2026-04-26-sites-monitor-design.md`

---

## File map

**Create:**
- `backend/app/services/company_crawl_logger.py` — context manager.
- `backend/app/services/sites_alert.py` — pure `alert_level()` function.
- `backend/app/services/company_crawler_registry.py` — `COMPANY_CRAWLERS` dict.
- `backend/app/schemas_sites.py` — pydantic response models.
- `backend/app/routers/sites.py` — 4 endpoints.
- `backend/tests/test_company_crawl_logger.py`
- `backend/tests/test_sites_alert.py`
- `backend/tests/test_sites_router.py`

**Modify:**
- `backend/app/models.py:418` — append `CompanyCrawlLog` model.
- `backend/app/services/schema_patch.py` — add `CREATE TABLE IF NOT EXISTS company_crawl_logs` + 3 indexes.
- `backend/app/services/internet_crawler.py:513` — wrap `for target in targets:` body.
- `backend/app/services/state_owned_crawler.py` — wrap analogous loop.
- `backend/app/services/securities_crawler.py` — wrap analogous loops (3: zhiye / hotjob / moka_embedded).
- `backend/app/services/consumer_foreign_crawler.py` — wrap analogous loop.
- `backend/app/services/energy_crawler.py` — wrap analogous loops (6 sub-sources).
- `backend/app/main.py:97` — register `sites.router`.
- `backend/app/routers/__init__.py` — re-export `sites`.

---

## Task 1 — `CompanyCrawlLog` model + migration

**Files:**
- Modify: `backend/app/models.py` (append after line 418)
- Modify: `backend/app/services/schema_patch.py` (append in `ensure_compatible_schema`)

- [ ] **Step 1.1: Append SQLAlchemy model**

Append to `backend/app/models.py`:

```python
class CompanyCrawlLog(Base):
    __tablename__ = "company_crawl_logs"

    id = Column(Integer, primary_key=True)
    source = Column(Text, nullable=False, index=True)
    company = Column(Text, nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    status = Column(Text, nullable=False, default="running")
    fetched_count = Column(Integer, nullable=False, default=0)
    new_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=False, default="")
    parent_log_id = Column(Integer, nullable=True, index=True)
    duration_ms = Column(Integer, nullable=False, default=0)
```

- [ ] **Step 1.2: Add DDL to schema_patch**

In `backend/app/services/schema_patch.py`, inside `ensure_compatible_schema`, after the `company_recrawl_queue` block, add:

```python
        ccl_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='company_crawl_logs'")
        ).fetchone()
        if not ccl_exists:
            conn.execute(text(
                """
                CREATE TABLE company_crawl_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    company TEXT NOT NULL,
                    started_at DATETIME NOT NULL,
                    finished_at DATETIME,
                    status TEXT NOT NULL,
                    fetched_count INTEGER NOT NULL DEFAULT 0,
                    new_count INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT NOT NULL DEFAULT '',
                    parent_log_id INTEGER,
                    duration_ms INTEGER NOT NULL DEFAULT 0
                )
                """
            ))
            conn.execute(text("CREATE INDEX idx_ccl_company_started ON company_crawl_logs(company, started_at DESC)"))
            conn.execute(text("CREATE INDEX idx_ccl_source_started  ON company_crawl_logs(source, started_at DESC)"))
            conn.execute(text("CREATE INDEX idx_ccl_parent          ON company_crawl_logs(parent_log_id)"))
```

- [ ] **Step 1.3: Smoke-test schema creation**

Run: `cd backend && PYTHONPATH=. .venv/bin/python -c "from app.database import engine; from app.services.schema_patch import ensure_compatible_schema; ensure_compatible_schema(engine); print('ok')"`
Expected: `ok` printed; no exception.

Then verify table:
`cd backend && PYTHONPATH=. .venv/bin/python -c "from app.database import engine; from sqlalchemy import text; print(engine.connect().execute(text('PRAGMA table_info(company_crawl_logs)')).fetchall())"`
Expected: 11 column rows.

- [ ] **Step 1.4: Commit**

```bash
git add backend/app/models.py backend/app/services/schema_patch.py
git commit -m "feat(sites): add company_crawl_logs table + model

Per-company run records to support /api/sites monitor.
Schema patch creates table + 3 indexes idempotently."
```

---

## Task 2 — `company_crawl_log` context manager (TDD)

**Files:**
- Create: `backend/app/services/company_crawl_logger.py`
- Create: `backend/tests/test_company_crawl_logger.py`

- [ ] **Step 2.1: Write failing tests**

Create `backend/tests/test_company_crawl_logger.py`:

```python
import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, CompanyCrawlLog
from app.services.company_crawl_logger import company_crawl_log


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_success_path_sets_status_and_counts(db):
    with company_crawl_log(db, source="internet_official", company="腾讯", parent_log_id=42) as log:
        log.fetched_count = 100
        log.new_count = 12

    rows = db.query(CompanyCrawlLog).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.status == "success"
    assert row.source == "internet_official"
    assert row.company == "腾讯"
    assert row.parent_log_id == 42
    assert row.fetched_count == 100
    assert row.new_count == 12
    assert row.finished_at is not None
    assert row.duration_ms >= 0
    assert row.error_message == ""


def test_exception_path_marks_failed_and_truncates(db):
    long_msg = "boom-" * 200  # 1000 chars

    with pytest.raises(RuntimeError):
        with company_crawl_log(db, source="securities_zhiye", company="中金公司", parent_log_id=None):
            raise RuntimeError(long_msg)

    row = db.query(CompanyCrawlLog).one()
    assert row.status == "failed"
    assert row.error_message.startswith("boom-")
    assert len(row.error_message) == 500
    assert row.finished_at is not None


def test_running_row_visible_before_block_exits(db):
    """During the with-block, status='running' is committed so external readers can see in-flight runs."""
    with company_crawl_log(db, source="internet_official", company="字节跳动", parent_log_id=None) as log:
        # Use a separate session to query — the row should already be committed
        from sqlalchemy.orm import sessionmaker
        OtherSession = sessionmaker(bind=db.bind)
        other = OtherSession()
        try:
            in_flight = other.query(CompanyCrawlLog).filter_by(company="字节跳动").one()
            assert in_flight.status == "running"
            assert in_flight.finished_at is None
        finally:
            other.close()
        log.fetched_count = 5
        log.new_count = 5
```

- [ ] **Step 2.2: Run tests to verify they fail**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_company_crawl_logger.py -v`
Expected: 3 failures with `ModuleNotFoundError: No module named 'app.services.company_crawl_logger'`.

- [ ] **Step 2.3: Implement the context manager**

Create `backend/app/services/company_crawl_logger.py`:

```python
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Optional

from sqlalchemy.orm import Session

from app.models import CompanyCrawlLog

_ERROR_TRUNCATE = 500


@contextmanager
def company_crawl_log(
    db: Session,
    *,
    source: str,
    company: str,
    parent_log_id: Optional[int],
) -> Iterator[CompanyCrawlLog]:
    log = CompanyCrawlLog(
        source=source,
        company=company,
        parent_log_id=parent_log_id,
        started_at=datetime.utcnow(),
        status="running",
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    start = time.monotonic()
    try:
        yield log
        log.status = "success"
    except Exception as exc:
        log.status = "failed"
        log.error_message = str(exc)[:_ERROR_TRUNCATE]
        raise
    finally:
        log.finished_at = datetime.utcnow()
        log.duration_ms = int((time.monotonic() - start) * 1000)
        db.commit()
```

- [ ] **Step 2.4: Run tests to verify they pass**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_company_crawl_logger.py -v`
Expected: 3 passes.

- [ ] **Step 2.5: Commit**

```bash
git add backend/app/services/company_crawl_logger.py backend/tests/test_company_crawl_logger.py
git commit -m "feat(sites): company_crawl_log context manager

Wraps per-company crawl calls and commits a CompanyCrawlLog row
with status=running before the block, then success/failed with
duration_ms after. Error messages truncated to 500 chars."
```

---

## Task 3 — `alert_level` pure function (TDD)

**Files:**
- Create: `backend/app/services/sites_alert.py`
- Create: `backend/tests/test_sites_alert.py`

- [ ] **Step 3.1: Write failing tests**

Create `backend/tests/test_sites_alert.py`:

```python
from datetime import datetime, timedelta

from app.services.sites_alert import alert_level


def _run(started_at, status, new_count=0):
    class R: pass
    r = R()
    r.started_at = started_at
    r.status = status
    r.new_count = new_count
    return r


NOW = datetime(2026, 4, 26, 12, 0, 0)


def test_unknown_when_no_runs():
    assert alert_level([], NOW) == "unknown"


def test_green_when_recent_success_with_new_jobs():
    runs = [_run(NOW - timedelta(hours=4), "success", new_count=10)]
    assert alert_level(runs, NOW) == "green"


def test_yellow_on_single_failure():
    runs = [
        _run(NOW - timedelta(hours=4), "failed"),
        _run(NOW - timedelta(days=1), "success", new_count=5),
    ]
    assert alert_level(runs, NOW) == "yellow"


def test_red_on_two_consecutive_failures():
    runs = [
        _run(NOW - timedelta(hours=4), "failed"),
        _run(NOW - timedelta(days=1), "failed"),
        _run(NOW - timedelta(days=2), "success", new_count=5),
    ]
    assert alert_level(runs, NOW) == "red"


def test_yellow_when_success_but_no_new_jobs_in_3_days():
    runs = [
        _run(NOW - timedelta(hours=4), "success", new_count=0),
        _run(NOW - timedelta(days=1), "success", new_count=0),
        _run(NOW - timedelta(days=4), "success", new_count=2),
    ]
    assert alert_level(runs, NOW) == "yellow"


def test_green_when_success_and_recent_new_jobs():
    runs = [
        _run(NOW - timedelta(hours=4), "success", new_count=0),
        _run(NOW - timedelta(days=1), "success", new_count=3),
    ]
    assert alert_level(runs, NOW) == "green"
```

- [ ] **Step 3.2: Run tests to verify they fail**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_sites_alert.py -v`
Expected: 6 failures with `ModuleNotFoundError`.

- [ ] **Step 3.3: Implement `alert_level`**

Create `backend/app/services/sites_alert.py`:

```python
from datetime import datetime, timedelta
from typing import Iterable, Literal

AlertLevel = Literal["green", "yellow", "red", "unknown"]
ALERT_STALE_DAYS = 3


def alert_level(runs: list, now: datetime) -> AlertLevel:
    """Compute alert level from runs sorted by started_at DESC.

    runs: objects with .started_at, .status, .new_count attributes.
    """
    if not runs:
        return "unknown"

    last = runs[0]
    if last.status == "failed":
        if len(runs) >= 2 and runs[1].status == "failed":
            return "red"
        return "yellow"

    # last is 'success'
    new_run_dates = [r.started_at for r in runs if r.new_count > 0]
    if not new_run_dates:
        last_new = now - timedelta(days=999)
    else:
        last_new = max(new_run_dates)

    if (now - last_new).days >= ALERT_STALE_DAYS:
        return "yellow"
    return "green"
```

- [ ] **Step 3.4: Run tests to verify they pass**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_sites_alert.py -v`
Expected: 6 passes.

- [ ] **Step 3.5: Commit**

```bash
git add backend/app/services/sites_alert.py backend/tests/test_sites_alert.py
git commit -m "feat(sites): alert_level rule

green/yellow/red/unknown based on last 2 runs + 3-day staleness.
Pure function, no DB dependency."
```

---

## Task 4 — Wrap `internet_crawler.crawl_internet_targets` per-target loop

**Files:**
- Modify: `backend/app/services/internet_crawler.py:513` — body of `for target in targets:`
- The wrap is purely additive: existing logic preserved, surrounded by `with company_crawl_log(...) as log:`.

- [ ] **Step 4.1: Read current loop body to understand fetched_count / new_count semantics**

Run: `cd backend && PYTHONPATH=. .venv/bin/sed -n '513,610p' app/services/internet_crawler.py`

Confirm: existing code already accumulates `fetched_count` and `new_count` as locals. Wrap point is from `for target in targets:` to just after the per-target processing block (before next iteration).

- [ ] **Step 4.2: Add import**

At the top of `backend/app/services/internet_crawler.py`, add:

```python
from app.services.company_crawl_logger import company_crawl_log
```

- [ ] **Step 4.3: Modify signature to accept `parent_log_id`**

Change function signature at line 487 of `backend/app/services/internet_crawler.py`:

```python
def crawl_internet_targets(
    db: Session,
    targets: list[InternetCrawlTarget],
    dry_run: bool = False,
    max_pages: Optional[int] = None,
    parent_log_id: Optional[int] = None,
) -> list[InternetCrawlResult]:
```

- [ ] **Step 4.4: Wrap loop body**

Inside the `for target in targets:` block, wrap the body. Replace:

```python
                for target in targets:
                    fn = _select_crawler(target.company, target.url)
                    if fn is None:
                        results.append(InternetCrawlResult(...))
                        continue

                    context, page = legacy.new_page(browser)
                    try:
                        # ... existing body that computes fetched_count, new_count ...
                    finally:
                        context.close()
```

with:

```python
                for target in targets:
                    fn = _select_crawler(target.company, target.url)
                    if fn is None:
                        results.append(InternetCrawlResult(...))
                        continue

                    with company_crawl_log(
                        db,
                        source=target.source or "internet_official",
                        company=target.company,
                        parent_log_id=parent_log_id,
                    ) as log:
                        context, page = legacy.new_page(browser)
                        try:
                            # ... existing body unchanged ...
                            log.fetched_count = fetched_count
                            log.new_count = new_count
                        finally:
                            context.close()
```

The body's local `fetched_count` / `new_count` variables get assigned onto the log object right before the inner `finally` runs. Important: do NOT remove the existing variables; keep them and copy into the log.

- [ ] **Step 4.5: Update caller(s) to pass `parent_log_id`**

Find callers:

Run: `cd backend && PYTHONPATH=. grep -rn "crawl_internet_targets(" app/ scripts/ --include='*.py'`

For each caller in `app/services/crawler.py` (the `run_crawl` orchestrator) and `scripts/run_internet_tier_crawl.py`, pass `parent_log_id=log.id` where `log` is the parent `CrawlLog` (in `crawler.py`'s `run_crawl`) or `parent_log_id=None` (in scripts that don't have a parent log).

In `backend/app/services/crawler.py`'s `run_crawl`, locate the call to `crawl_internet_targets(...)` and add `parent_log_id=log.id` (where `log` is the existing parent `CrawlLog` instance for the multi-source batch).

- [ ] **Step 4.6: Smoke test**

Run: `cd backend && PYTHONPATH=. .venv/bin/python -c "from app.services.internet_crawler import crawl_internet_targets; print('import ok')"`
Expected: `import ok`.

Run unit-suite to make sure nothing else broke:
`cd backend && PYTHONPATH=. .venv/bin/pytest tests/ --ignore=tests/test_resume_copilot_service.py -x`
Expected: all green (no per-company-crawl integration test yet).

- [ ] **Step 4.7: Commit**

```bash
git add backend/app/services/internet_crawler.py backend/app/services/crawler.py
git commit -m "feat(sites): instrument internet_crawler per-target loop

Each iteration over InternetCrawlTarget now writes one
company_crawl_logs row via the company_crawl_log context manager.
parent_log_id wired from run_crawl's CrawlLog."
```

---

## Task 5 — Wrap remaining orchestrators (state_owned / securities / consumer_foreign / energy / antgroup)

**Files:**
- Modify: `backend/app/services/state_owned_crawler.py`
- Modify: `backend/app/services/securities_crawler.py`
- Modify: `backend/app/services/consumer_foreign_crawler.py`
- Modify: `backend/app/services/energy_crawler.py`

For each orchestrator below, the change is identical in shape: identify the `for target in targets:` loop, add `from app.services.company_crawl_logger import company_crawl_log` at top, add `parent_log_id: Optional[int] = None` to the public function signature, wrap the per-target body in `with company_crawl_log(db, source=<source-string>, company=target.company, parent_log_id=parent_log_id) as log:` and assign `log.fetched_count` / `log.new_count` before the with-block exits.

- [ ] **Step 5.1: state_owned_crawler**

Run: `cd backend && PYTHONPATH=. grep -n "^def crawl_\|^def _crawl_\|for target\|target.source" app/services/state_owned_crawler.py | head -30`

Identify the orchestrator function (likely `crawl_state_owned_targets`). Apply the same pattern as Task 4: import, add `parent_log_id` parameter, wrap loop body.

`source` argument value: `target.source` if the target dataclass has it, otherwise `"state_owned_official"`.

- [ ] **Step 5.2: securities_crawler**

Same as 5.1, but securities has 3 sub-sources (`securities_zhiye`, `securities_hotjob`, `securities_moka_embedded`). If the orchestrator has 3 separate loops or one parameterized loop, wrap each.

- [ ] **Step 5.3: consumer_foreign_crawler**

Same pattern. Source: `"consumer_foreign_official"`.

- [ ] **Step 5.4: energy_crawler**

Energy has 6 sub-sources (`energy_hotjob`, `energy_csisolar`, `energy_moka`, `energy_moka_embedded`, `energy_zhiye`, `energy_51job_campus`). Wrap each loop with the appropriate source string.

- [ ] **Step 5.5: antgroup_api**

Run: `cd backend && PYTHONPATH=. grep -rn "antgroup_api" app/services/ --include='*.py'` — find where the API source is invoked.

Wrap the call with `source="antgroup_api"`, `company="蚂蚁集团"`. If the call already runs inside `crawl_internet_targets` (via legacy `_crawl_antgroup_one_type`), it's already covered by Task 4 and this step is a no-op — verify and skip.

- [ ] **Step 5.6: Update callers**

For each modified orchestrator, find callers via `grep -rn "<function_name>(" app/ scripts/` and pass `parent_log_id=log.id` from `run_crawl`.

- [ ] **Step 5.7: Sanity import + test pass**

Run: `cd backend && PYTHONPATH=. .venv/bin/python -c "
from app.services.state_owned_crawler import *
from app.services.securities_crawler import *
from app.services.consumer_foreign_crawler import *
from app.services.energy_crawler import *
print('imports ok')
"`
Expected: `imports ok`.

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/ --ignore=tests/test_resume_copilot_service.py -x`
Expected: all green.

- [ ] **Step 5.8: Commit**

```bash
git add backend/app/services/state_owned_crawler.py backend/app/services/securities_crawler.py backend/app/services/consumer_foreign_crawler.py backend/app/services/energy_crawler.py backend/app/services/crawler.py
git commit -m "feat(sites): instrument remaining orchestrators

state_owned, securities (3 sub-sources), consumer_foreign,
energy (6 sub-sources) now write per-company log rows.
antgroup_api covered transitively via internet_crawler."
```

---

## Task 6 — `COMPANY_CRAWLERS` registry + recrawl shims

**Files:**
- Create: `backend/app/services/company_crawler_registry.py`
- Create: `backend/tests/test_company_crawler_registry.py`

- [ ] **Step 6.1: Write failing test**

Create `backend/tests/test_company_crawler_registry.py`:

```python
from app.services.company_crawler_registry import COMPANY_CRAWLERS, recrawl_company


def test_registry_has_internet_t1_companies():
    expected = {
        "腾讯", "阿里巴巴", "蚂蚁集团", "字节跳动", "美团",
        "京东", "快手", "拼多多", "百度", "网易",
        "哔哩哔哩", "米哈游", "携程", "得物",
    }
    missing = expected - set(COMPANY_CRAWLERS.keys())
    assert not missing, f"missing companies in registry: {missing}"


def test_registry_callables_have_correct_signature():
    import inspect
    for company, fn in COMPANY_CRAWLERS.items():
        sig = inspect.signature(fn)
        params = list(sig.parameters.keys())
        assert params[:2] == ["db", "parent_log_id"], (
            f"{company}: expected (db, parent_log_id, ...), got {params}"
        )


def test_recrawl_unknown_company_raises_keyerror():
    import pytest
    with pytest.raises(KeyError):
        recrawl_company(db=None, company="不存在公司", parent_log_id=None)
```

- [ ] **Step 6.2: Run tests to verify they fail**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_company_crawler_registry.py -v`
Expected: 3 failures (`ModuleNotFoundError`).

- [ ] **Step 6.3: Implement registry**

Create `backend/app/services/company_crawler_registry.py`:

```python
"""Per-company recrawl entry points.

Used by POST /api/sites/{company}/recrawl to invoke a single company's
scraper without going through the full multi-source batch.

Each callable takes (db, parent_log_id) and DELEGATES to the existing
orchestrator (e.g. crawl_internet_targets), filtering its target list
to just the requested company. The orchestrator already wraps each
target in a `with company_crawl_log(...)` block (Tasks 4/5), so the
shim does NOT add another wrap — that would double-count rows.
"""
from typing import Callable, Optional

from sqlalchemy.orm import Session


CompanyCrawler = Callable[[Session, Optional[int]], None]


def _shim_internet(company: str, source: str = "internet_official") -> CompanyCrawler:
    """Build a recrawl shim for a single internet_official target.

    NOTE: confirm the actual discovery function name first — run
    `grep -n "^def discover\|^def _build_internet_targets\|^def load_internet_targets" backend/app/services/internet_crawler.py`
    and substitute below. Common candidates: `discover_internet_targets`,
    `build_internet_targets`, `load_internet_targets`.
    """
    def _run(db: Session, parent_log_id: Optional[int]) -> None:
        from app.services.internet_crawler import (
            crawl_internet_targets,
            discover_internet_targets,  # ← rename if grep reveals a different symbol
        )
        targets = [t for t in discover_internet_targets() if t.company == company]
        if not targets:
            raise RuntimeError(f"no targets configured for {company}")
        # crawl_internet_targets already wraps each target in company_crawl_log
        crawl_internet_targets(db, targets, parent_log_id=parent_log_id)
    return _run


def _shim_state_owned(company: str) -> CompanyCrawler:
    def _run(db: Session, parent_log_id: Optional[int]) -> None:
        from app.services.state_owned_crawler import (
            crawl_state_owned_targets,
            discover_state_owned_targets,
        )
        targets = [t for t in discover_state_owned_targets() if t.company == company]
        if not targets:
            raise RuntimeError(f"no state-owned targets for {company}")
        crawl_state_owned_targets(db, targets, parent_log_id=parent_log_id)
    return _run


# Internet (16)
COMPANY_CRAWLERS: dict[str, CompanyCrawler] = {
    "腾讯":       _shim_internet("腾讯"),
    "阿里巴巴":   _shim_internet("阿里巴巴"),
    "蚂蚁集团":   _shim_internet("蚂蚁集团"),
    "字节跳动":   _shim_internet("字节跳动"),
    "美团":       _shim_internet("美团"),
    "京东":       _shim_internet("京东"),
    "快手":       _shim_internet("快手"),
    "拼多多":     _shim_internet("拼多多"),
    "百度":       _shim_internet("百度"),
    "网易":       _shim_internet("网易"),
    "网易雷火":   _shim_internet("网易雷火"),
    "哔哩哔哩":   _shim_internet("哔哩哔哩"),
    "米哈游":     _shim_internet("米哈游"),
    "携程":       _shim_internet("携程"),
    "得物":       _shim_internet("得物"),
    "BOSS直聘":   _shim_internet("BOSS直聘"),
}

# Add other clusters by introspecting the discover_* functions of each orchestrator.
# For Phase 1 the internet_official subset is sufficient — it's the highest-traffic cluster
# and the one the user named explicitly. Other clusters can be added in a follow-up patch
# once their `discover_*` functions are confirmed (Step 6.4).


def recrawl_company(db: Session, company: str, parent_log_id: Optional[int]) -> None:
    if company not in COMPANY_CRAWLERS:
        raise KeyError(company)
    COMPANY_CRAWLERS[company](db, parent_log_id)
```

- [ ] **Step 6.4: Extend registry to other clusters**

Run: `cd backend && PYTHONPATH=. grep -n "^def discover_\|^def _discover_" app/services/state_owned_crawler.py app/services/securities_crawler.py app/services/consumer_foreign_crawler.py app/services/energy_crawler.py`

For each cluster that exposes a `discover_*_targets()` function, add a `_shim_<cluster>(company)` factory in `company_crawler_registry.py` analogous to `_shim_state_owned`, then extend `COMPANY_CRAWLERS` with that cluster's companies. Drive the company list from `discover_<cluster>_targets()` at module import:

```python
from app.services.state_owned_crawler import discover_state_owned_targets
for t in discover_state_owned_targets():
    COMPANY_CRAWLERS.setdefault(t.company, _shim_state_owned(t.company))
```

(Repeat for securities / consumer_foreign / energy.)

If a cluster does not expose a `discover_*` (lookup fails), defer it — leave a comment and note in CLAUDE.md.

- [ ] **Step 6.5: Run tests to verify they pass**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_company_crawler_registry.py -v`
Expected: 3 passes.

- [ ] **Step 6.6: Commit**

```bash
git add backend/app/services/company_crawler_registry.py backend/tests/test_company_crawler_registry.py
git commit -m "feat(sites): COMPANY_CRAWLERS registry + recrawl_company

Maps company name → callable that invokes that company's scraper
via the existing orchestrator (which already wraps in
company_crawl_log). Internet t1 (16) covered explicitly; other
clusters pulled from each orchestrator's discover_* function."
```

---

## Task 7 — `/api/sites` router + Pydantic schemas + tests + main.py wiring

**Files:**
- Create: `backend/app/schemas_sites.py`
- Create: `backend/app/routers/sites.py`
- Modify: `backend/app/routers/__init__.py`
- Modify: `backend/app/main.py:97`
- Create: `backend/tests/test_sites_router.py`

- [ ] **Step 7.1: Pydantic schemas**

Create `backend/app/schemas_sites.py`:

```python
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


AlertLevel = Literal["green", "yellow", "red", "unknown"]


class SitesSummaryOut(BaseModel):
    active: int
    alerted: int
    disabled: int
    total_today_new: int
    last_batch_at: Optional[datetime]
    last_batch_status: Optional[str]


class SiteRowOut(BaseModel):
    company: str
    source: str
    last_run_at: Optional[datetime]
    last_status: Optional[str]
    today_new: int
    last_error_short: str
    alert_level: AlertLevel


class SiteRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    fetched_count: int
    new_count: int
    error_message: str
    duration_ms: int


class SiteRecrawlOut(BaseModel):
    parent_log_id: int
    message: str
```

- [ ] **Step 7.2: Write router tests**

Create `backend/tests/test_sites_router.py`:

```python
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app
from app.models import Base, CompanyCrawlLog, CrawlLog


@pytest.fixture
def client():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c, Session
    app.dependency_overrides.clear()


def _seed(session, **kw):
    row = CompanyCrawlLog(
        source=kw.get("source", "internet_official"),
        company=kw["company"],
        started_at=kw["started_at"],
        finished_at=kw.get("finished_at", kw["started_at"] + timedelta(seconds=5)),
        status=kw.get("status", "success"),
        fetched_count=kw.get("fetched_count", 10),
        new_count=kw.get("new_count", 2),
        error_message=kw.get("error_message", ""),
        parent_log_id=kw.get("parent_log_id"),
        duration_ms=kw.get("duration_ms", 5000),
    )
    session.add(row)
    session.commit()
    return row


def test_summary_counts_active_and_alerted(client):
    c, Session = client
    db = Session()
    now = datetime.utcnow()
    _seed(db, company="腾讯", started_at=now - timedelta(hours=2), status="success", new_count=5)
    _seed(db, company="阿里巴巴", started_at=now - timedelta(hours=2), status="failed", new_count=0)
    _seed(db, company="阿里巴巴", started_at=now - timedelta(days=1), status="failed", new_count=0)
    _seed(db, company="字节跳动", started_at=now - timedelta(hours=2), status="success", new_count=20)
    db.close()

    res = c.get("/api/sites/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["active"] == 2          # 腾讯 + 字节跳动
    assert body["alerted"] == 1         # 阿里巴巴 red
    assert body["total_today_new"] >= 25


def test_list_returns_one_row_per_company(client):
    c, Session = client
    db = Session()
    now = datetime.utcnow()
    _seed(db, company="腾讯", started_at=now - timedelta(hours=2), new_count=5)
    _seed(db, company="腾讯", started_at=now - timedelta(days=1), new_count=3)
    _seed(db, company="阿里巴巴", started_at=now - timedelta(hours=1), new_count=2)
    db.close()

    res = c.get("/api/sites")
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 2
    companies = {r["company"] for r in rows}
    assert companies == {"腾讯", "阿里巴巴"}
    tencent = next(r for r in rows if r["company"] == "腾讯")
    assert tencent["alert_level"] == "green"


def test_list_filters_by_source(client):
    c, Session = client
    db = Session()
    now = datetime.utcnow()
    _seed(db, source="internet_official", company="腾讯", started_at=now)
    _seed(db, source="state_owned_official", company="中电科技", started_at=now)
    db.close()

    res = c.get("/api/sites?source=state_owned_official")
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["company"] == "中电科技"


def test_runs_endpoint_returns_recent_history(client):
    c, Session = client
    db = Session()
    now = datetime.utcnow()
    for i in range(5):
        _seed(db, company="腾讯", started_at=now - timedelta(hours=i))
    db.close()

    res = c.get("/api/sites/腾讯/runs?limit=3")
    assert res.status_code == 200
    runs = res.json()
    assert len(runs) == 3
    # newest first
    started_times = [r["started_at"] for r in runs]
    assert started_times == sorted(started_times, reverse=True)


def test_recrawl_unknown_company_returns_400(client):
    c, _ = client
    res = c.post("/api/sites/不存在的公司/recrawl")
    assert res.status_code == 400
```

- [ ] **Step 7.3: Implement the router**

Create `backend/app/routers/sites.py`:

```python
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import CompanyCrawlLog, CrawlLog
from app.schemas_sites import (
    SiteRecrawlOut,
    SiteRowOut,
    SiteRunOut,
    SitesSummaryOut,
)
from app.services.company_crawler_registry import COMPANY_CRAWLERS, recrawl_company
from app.services.scorer import score_all_jobs
from app.services.sites_alert import alert_level


router = APIRouter(prefix="/api/sites", tags=["sites"])


def _shanghai_today_start() -> datetime:
    """Return today 00:00 Asia/Shanghai expressed as naive UTC."""
    sh = timezone(timedelta(hours=8))
    now_sh = datetime.now(sh)
    today_sh = now_sh.replace(hour=0, minute=0, second=0, microsecond=0)
    return today_sh.astimezone(timezone.utc).replace(tzinfo=None)


def _build_site_rows(db: Session, source_filter: Optional[str]) -> list[SiteRowOut]:
    q = db.query(
        CompanyCrawlLog.company,
        CompanyCrawlLog.source,
    )
    if source_filter:
        q = q.filter(CompanyCrawlLog.source == source_filter)
    pairs = q.distinct().all()

    today_start = _shanghai_today_start()
    rows: list[SiteRowOut] = []
    now = datetime.utcnow()
    for company, source in pairs:
        runs = (
            db.query(CompanyCrawlLog)
            .filter(CompanyCrawlLog.company == company, CompanyCrawlLog.source == source)
            .order_by(CompanyCrawlLog.started_at.desc())
            .limit(10)
            .all()
        )
        today_new = (
            db.query(func.coalesce(func.sum(CompanyCrawlLog.new_count), 0))
            .filter(
                CompanyCrawlLog.company == company,
                CompanyCrawlLog.source == source,
                CompanyCrawlLog.started_at >= today_start,
            )
            .scalar()
        )
        last = runs[0] if runs else None
        rows.append(SiteRowOut(
            company=company,
            source=source,
            last_run_at=last.started_at if last else None,
            last_status=last.status if last else None,
            today_new=int(today_new or 0),
            last_error_short=(last.error_message[:120] if last and last.error_message else ""),
            alert_level=alert_level(runs, now),
        ))
    return rows


@router.get("/summary", response_model=SitesSummaryOut)
def get_summary(db: Session = Depends(get_db)) -> SitesSummaryOut:
    rows = _build_site_rows(db, None)
    active = sum(1 for r in rows if r.alert_level == "green")
    alerted = sum(1 for r in rows if r.alert_level in ("yellow", "red"))
    disabled = max(0, len(COMPANY_CRAWLERS) - {r.company for r in rows}.__len__())
    total_today_new = sum(r.today_new for r in rows)

    last_batch = (
        db.query(CrawlLog)
        .order_by(CrawlLog.id.desc())
        .first()
    )
    return SitesSummaryOut(
        active=active,
        alerted=alerted,
        disabled=disabled,
        total_today_new=total_today_new,
        last_batch_at=last_batch.started_at if last_batch else None,
        last_batch_status=last_batch.status if last_batch else None,
    )


@router.get("", response_model=list[SiteRowOut])
def list_sites(
    source: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> list[SiteRowOut]:
    return _build_site_rows(db, source)


@router.get("/{company}/runs", response_model=list[SiteRunOut])
def get_company_runs(
    company: str,
    limit: int = Query(24, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[SiteRunOut]:
    runs = (
        db.query(CompanyCrawlLog)
        .filter(CompanyCrawlLog.company == company)
        .order_by(CompanyCrawlLog.started_at.desc())
        .limit(limit)
        .all()
    )
    return [SiteRunOut.model_validate(r) for r in runs]


def _run_recrawl_in_background(company: str, parent_log_id: int) -> None:
    db = SessionLocal()
    try:
        recrawl_company(db=db, company=company, parent_log_id=parent_log_id)
        new_total = (
            db.query(func.coalesce(func.sum(CompanyCrawlLog.new_count), 0))
            .filter(CompanyCrawlLog.parent_log_id == parent_log_id)
            .scalar()
        )
        if int(new_total or 0) > 0:
            score_all_jobs(db)
        parent = db.query(CrawlLog).filter(CrawlLog.id == parent_log_id).first()
        if parent is not None:
            parent.status = "success"
            parent.finished_at = datetime.utcnow()
            parent.new_count = int(new_total or 0)
            db.commit()
    except Exception as exc:
        parent = db.query(CrawlLog).filter(CrawlLog.id == parent_log_id).first()
        if parent is not None:
            parent.status = "failed"
            parent.finished_at = datetime.utcnow()
            parent.error_message = str(exc)[:500]
            db.commit()
    finally:
        db.close()


@router.post("/{company}/recrawl", response_model=SiteRecrawlOut)
def recrawl_company_endpoint(
    company: str,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> SiteRecrawlOut:
    if company not in COMPANY_CRAWLERS:
        raise HTTPException(status_code=400, detail=f"未配置 {company} 的爬虫")

    parent = CrawlLog(
        source=f"recrawl:{company}",
        started_at=datetime.utcnow(),
        status="running",
    )
    db.add(parent)
    db.commit()
    db.refresh(parent)

    background.add_task(_run_recrawl_in_background, company, parent.id)
    return SiteRecrawlOut(parent_log_id=parent.id, message="已启动")
```

- [ ] **Step 7.4: Wire router into main.py**

Edit `backend/app/routers/__init__.py` to re-export `sites`:

```python
# Append:
from . import sites  # noqa: F401
```

Edit `backend/app/main.py` line 97 area — add after `interview`:

```python
app.include_router(sites.router)
```

And add `sites` to the import at line 15.

- [ ] **Step 7.5: Run tests**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_sites_router.py -v`
Expected: 5 passes.

- [ ] **Step 7.6: Manual smoke test against running server**

In one terminal: `cd backend && PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

In another:
```bash
curl http://127.0.0.1:8000/api/sites/summary | python3 -m json.tool
curl http://127.0.0.1:8000/api/sites | python3 -m json.tool | head -40
curl 'http://127.0.0.1:8000/api/sites/腾讯/runs?limit=3' | python3 -m json.tool
curl -X POST http://127.0.0.1:8000/api/sites/腾讯/recrawl
curl -X POST http://127.0.0.1:8000/api/sites/不存在/recrawl  # expect 400
```

Expected: first 3 calls return JSON without 500. Recrawl returns `{parent_log_id, message}`. Unknown company returns 400.

- [ ] **Step 7.7: Commit**

```bash
git add backend/app/schemas_sites.py backend/app/routers/sites.py backend/app/routers/__init__.py backend/app/main.py backend/tests/test_sites_router.py
git commit -m "feat(sites): /api/sites router with 4 endpoints

GET /summary, GET /, GET /{company}/runs, POST /{company}/recrawl.
Recrawl invokes COMPANY_CRAWLERS via FastAPI BackgroundTasks and
re-runs scoring if new_count > 0."
```

---

## Final verification

- [ ] **Run full backend test suite**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/ --ignore=tests/test_resume_copilot_service.py -x
```
Expected: all green.

- [ ] **Trigger a full crawl and verify per-company logs populate**

In a separate terminal with the dev server running:
```bash
curl -X POST http://127.0.0.1:8000/api/crawl/trigger
```

Wait for it to finish (poll `/api/crawl/status`). Then:
```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
import sqlite3
con = sqlite3.connect('data/jobradar.db')
print(con.execute(\"SELECT company, source, status, new_count FROM company_crawl_logs WHERE date(started_at) = date('now') ORDER BY started_at DESC LIMIT 30\").fetchall())
"
```
Expected: ≥10 rows from today, mix of `internet_official` / `state_owned_official` / `securities_*` / `consumer_foreign_official` / `energy_*`.

- [ ] **Update CLAUDE.md**

Append a "Sites monitor" subsection to `CLAUDE.md` documenting:
- New `company_crawl_logs` table.
- 4 endpoints under `/api/sites`.
- `COMPANY_CRAWLERS` registry — when adding a new company crawler, add an entry here too.
- 蚂蚁集团 special case: covered by `_crawl_antgroup_one_type` running twice (campus_graduates + campus_interns) inside `_crawl_internet_targets`; logged as one row per type.

- [ ] **Final commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): document sites monitor backend"
```

---

## Notes for the implementer

- **Wrap-point pattern** is identical across all 5 orchestrator modules (Tasks 4 and 5). If the existing loop body lifts `fetched_count` / `new_count` into local variables (it does in `internet_crawler`; verify others), the wrap is purely additive.
- **Do not** wrap inside `legacy_crawlers/crawler.py`'s individual `crawl_<company>` functions — those are leaf scrapers called by orchestrators. Wrap at the orchestrator level only, otherwise rows double up.
- **Errors propagating up** — the context manager re-raises after recording, so the existing `try/except` around each per-target call (in the orchestrator) still catches and continues to the next target. Confirm by reading the existing `except` clause around line 530 of `internet_crawler.py`.
- **Recrawl runs synchronously inside BackgroundTasks**, which means concurrent recrawls of different companies can run if FastAPI serves them on different worker threads. SQLite's WAL + busy_timeout handles this. If you observe "database is locked" in logs, file a follow-up — Phase 1 doesn't add a lock.
- **Don't add a UI** in this phase. Phase 2 spec covers it once the design system arrives.
