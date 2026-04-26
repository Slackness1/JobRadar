# Nowcoder Interview Intel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a nightly Nowcoder 面经 pre-crawl + summarize pipeline that injects 17 chip-keyword intel into the AI interviewer's system prompt; silently degrades to current behavior on any failure.

**Architecture:** Two new SQLite tables (`interview_intel_keywords`, `interview_intel_posts`) + 5 new modules under `backend/app/services/interview/nowcoder/` (scraper, summarizer, refresh_job, intel_provider) + 1 yaml config + 1 cron-registered APScheduler job at 09:00 Asia/Shanghai. Single injection point in `build_interview_system_prompt()`.

**Tech Stack:** FastAPI, SQLAlchemy (SQLite WAL), APScheduler, urllib (no Playwright), PyYAML, deepseek-v4-flash.

**Spec:** `docs/superpowers/specs/2026-04-27-nowcoder-interview-intel-design.md`

**Repo conventions** (from CLAUDE.md):
- Tests live in `backend/tests/test_<topic>.py`, no fixtures dir
- Run tests: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_<file>.py -x`
- Schema evolution via `app/services/schema_patch.ensure_compatible_schema()`
- No comments unless WHY is non-obvious; no docstrings just because

---

## File Structure

| Path | Purpose | Created/Modified |
|---|---|---|
| `backend/app/models.py` | Add `InterviewIntelKeyword` + `InterviewIntelPost` | Modified |
| `backend/app/services/schema_patch.py` | Add CREATE TABLE for the two new tables | Modified |
| `backend/app/services/interview/nowcoder/__init__.py` | Marker | Created |
| `backend/app/services/interview/nowcoder/keywords.yaml` | 17 chip → search-query mapping | Created |
| `backend/app/services/interview/nowcoder/scraper.py` | `search()` + `fetch_post()` | Created |
| `backend/app/services/interview/nowcoder/summarizer.py` | `summarize_keyword()` | Created |
| `backend/app/services/interview/nowcoder/intel_provider.py` | `get_intel_for_target_job()` | Created |
| `backend/app/services/interview/nowcoder/refresh_job.py` | `run_refresh()` orchestrator + `get_last_refresh_status()` | Created |
| `backend/app/services/interview/llm.py` | Inject intel into `build_interview_system_prompt()` | Modified |
| `backend/app/services/scheduler_service.py` | Register `nowcoder_intel_refresh` cron job | Modified |
| `backend/app/schemas.py` | Extend `SchedulerConfigOut` with `nowcoder_intel_refresh` field | Modified |
| `backend/tests/test_nowcoder_scraper.py` | scraper unit tests + 1 integration | Created |
| `backend/tests/test_nowcoder_summarizer.py` | summarizer unit tests | Created |
| `backend/tests/test_nowcoder_intel_provider.py` | intel_provider unit tests | Created |
| `backend/tests/test_nowcoder_refresh_job.py` | refresh_job orchestrator unit tests | Created |
| `backend/tests/test_interview_service.py` | Extend with intel-injection tests | Modified |

**Why this layout**: keeping all five new files under one `nowcoder/` subpackage keeps the blast radius isolated — anyone can `rm -rf backend/app/services/interview/nowcoder/` and revert the feature without touching anything else (other than the yaml + the two callsites in `llm.py` and `scheduler_service.py`).

---

## Task 1: Schema (models + schema_patch)

**Files:**
- Modify: `backend/app/models.py` (append at end of file)
- Modify: `backend/app/services/schema_patch.py` (append inside `ensure_compatible_schema`)

- [ ] **Step 1: Append models to `backend/app/models.py`**

Add at the end of the file:

```python
class InterviewIntelKeyword(Base):
    __tablename__ = "interview_intel_keywords"

    keyword = Column(Text, primary_key=True)
    summary_md = Column(Text, default="")
    source_count = Column(Integer, default=0)
    generated_at = Column(DateTime, nullable=True)
    last_error = Column(Text, default="")


class InterviewIntelPost(Base):
    __tablename__ = "interview_intel_posts"

    pid = Column(Text, primary_key=True)
    keyword = Column(Text, primary_key=True, index=True)
    title = Column(Text, default="")
    company = Column(Text, default="")
    interview_date = Column(Text, default="")
    position = Column(Text, default="")
    questions_text = Column(Text, default="")
    fetched_at = Column(DateTime, default=datetime.utcnow)
    parse_status = Column(Text, default="ok")
```

- [ ] **Step 2: Append CREATE TABLE blocks to `ensure_compatible_schema`**

Add **inside** the `with engine.begin() as conn:` block in `backend/app/services/schema_patch.py` (append after the existing logic, before the closing of the `with` block):

```python
        kw_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='interview_intel_keywords'")
        ).fetchone()
        if not kw_exists:
            conn.execute(text(
                """
                CREATE TABLE interview_intel_keywords (
                    keyword TEXT PRIMARY KEY,
                    summary_md TEXT DEFAULT '',
                    source_count INTEGER DEFAULT 0,
                    generated_at DATETIME,
                    last_error TEXT DEFAULT ''
                )
                """
            ))

        post_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='interview_intel_posts'")
        ).fetchone()
        if not post_exists:
            conn.execute(text(
                """
                CREATE TABLE interview_intel_posts (
                    pid TEXT NOT NULL,
                    keyword TEXT NOT NULL,
                    title TEXT DEFAULT '',
                    company TEXT DEFAULT '',
                    interview_date TEXT DEFAULT '',
                    position TEXT DEFAULT '',
                    questions_text TEXT DEFAULT '',
                    fetched_at DATETIME,
                    parse_status TEXT DEFAULT 'ok',
                    PRIMARY KEY (pid, keyword)
                )
                """
            ))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_iip_keyword ON interview_intel_posts(keyword)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_iip_fetched ON interview_intel_posts(fetched_at)"))
```

- [ ] **Step 3: Sanity check — start backend, verify tables exist**

```bash
cd /home/chuanbo/projects/JobRadar/backend
# Backend is already running on :8002 with --reload; the model + schema changes
# will trigger reload. If it doesn't, restart manually:
pkill -f "uvicorn app.main:app.*--port 8002" 2>/dev/null
PYTHONPATH=. /home/chuanbo/projects/JobRadar/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload &
sleep 4
sqlite3 data/jobradar.db ".schema interview_intel_keywords"
sqlite3 data/jobradar.db ".schema interview_intel_posts"
```

Expected: both `CREATE TABLE` statements print, no error.

- [ ] **Step 4: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/models.py backend/app/services/schema_patch.py
git commit -m "$(cat <<'EOF'
feat(interview): add InterviewIntelKeyword + InterviewIntelPost tables

Two-table store for nightly Nowcoder 面经 pre-crawl. Keyword row is the
chip-level summary; post rows are the underlying scraped 面经 entries
(composite PK pid+keyword to allow same post under multiple search terms).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Keywords YAML

**Files:**
- Create: `backend/app/services/interview/nowcoder/__init__.py` (empty)
- Create: `backend/app/services/interview/nowcoder/keywords.yaml`

- [ ] **Step 1: Create empty `__init__.py`**

```bash
mkdir -p /home/chuanbo/projects/JobRadar/backend/app/services/interview/nowcoder
touch /home/chuanbo/projects/JobRadar/backend/app/services/interview/nowcoder/__init__.py
```

- [ ] **Step 2: Create `keywords.yaml` with all 17 chips**

Path: `backend/app/services/interview/nowcoder/keywords.yaml`

```yaml
# chip 文本来自 resume-copilot-web/app/interview/page.tsx 的 PRESETS。
# query 是对应的牛客搜索词。可手动调整以提升召回质量。
- chip: "产品经理"
  query: "产品经理面经"
- chip: "数据分析师"
  query: "数据分析面经"
- chip: "前端开发"
  query: "前端开发面经"
- chip: "后端开发"
  query: "后端开发面经"
- chip: "算法工程师"
  query: "算法工程师面经"
- chip: "运营"
  query: "互联网运营面经"
- chip: "券商研究员"
  query: "券商研究员面经"
- chip: "投行分析师"
  query: "投行分析师面经"
- chip: "量化研究员"
  query: "量化研究员面经"
- chip: "风控分析师"
  query: "风控分析师面经"
- chip: "商业银行管培生"
  query: "商业银行管培生面经"
- chip: "MBB 战略咨询"
  query: "战略咨询面经"
- chip: "宝洁市场营销"
  query: "宝洁市场营销面经"
- chip: "联合利华管培生"
  query: "联合利华管培生面经"
- chip: "中金财富管理"
  query: "中金财富管理面经"
- chip: "中国银行总行"
  query: "中国银行总行面经"
```

- [ ] **Step 3: Verify yaml loads**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/python -c "
import yaml, pathlib
p = pathlib.Path('app/services/interview/nowcoder/keywords.yaml')
data = yaml.safe_load(p.read_text(encoding='utf-8'))
assert isinstance(data, list) and len(data) == 16, f'expected 16 entries, got {len(data) if data else 0}'
for entry in data:
    assert 'chip' in entry and 'query' in entry, entry
print(f'OK: {len(data)} keyword entries')
"
```

Expected: `OK: 16 keyword entries`

(Note: 16 because `MBB 战略咨询` is one of the咨询/快消/央企 chips; the design said "17 chips" loosely — the actual PRESETS count from `page.tsx` is **16**. This plan uses the actual count.)

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/interview/nowcoder/__init__.py backend/app/services/interview/nowcoder/keywords.yaml
git commit -m "$(cat <<'EOF'
feat(interview): nowcoder keyword config (16 chip → search query map)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Scraper

**Files:**
- Create: `backend/app/services/interview/nowcoder/scraper.py`
- Create: `backend/tests/test_nowcoder_scraper.py`
- Create: `backend/tests/fixtures_nowcoder/search_sample.html` (small HTML fixture)
- Create: `backend/tests/fixtures_nowcoder/post_sample.html` (small HTML fixture)

- [ ] **Step 1: Create the scraper test file (failing)**

Path: `backend/tests/test_nowcoder_scraper.py`

```python
import pathlib
from unittest.mock import patch

import pytest

from app.services.interview.nowcoder import scraper

FIXTURES = pathlib.Path(__file__).parent / "fixtures_nowcoder"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_search_extracts_post_metas():
    with patch.object(scraper, "_fetch", return_value=_read("search_sample.html")):
        results = scraper.search("数据分析面经", limit=5)
    assert len(results) >= 2
    pids = [r.pid for r in results]
    assert "873597725214789632" in pids
    titles = {r.pid: r.title for r in results}
    assert titles["873597725214789632"]


def test_search_dedupes_repeated_pids():
    with patch.object(scraper, "_fetch", return_value=_read("search_sample.html")):
        results = scraper.search("anything", limit=20)
    seen = set()
    for r in results:
        assert r.pid not in seen
        seen.add(r.pid)


def test_fetch_post_parses_emoji_template():
    with patch.object(scraper, "_fetch", return_value=_read("post_sample.html")):
        detail = scraper.fetch_post("873597725214789632")
    assert detail.company == "聚智"
    assert detail.interview_date == "26-4-14"
    assert detail.position == "开发实习生"
    assert "单例模式" in detail.questions_text
    assert detail.parse_status == "ok"


def test_fetch_post_returns_failed_on_no_meta():
    html_no_meta = "<html><head></head><body>no meta description here</body></html>"
    with patch.object(scraper, "_fetch", return_value=html_no_meta):
        detail = scraper.fetch_post("000")
    assert detail.parse_status == "failed"
    assert detail.questions_text == ""


@pytest.mark.integration
def test_search_real_nowcoder_smoke():
    """Hits real Nowcoder. Run manually: pytest -m integration."""
    results = scraper.search("数据分析面经", limit=3)
    assert len(results) >= 1
    assert all(r.pid.isdigit() for r in results)
```

- [ ] **Step 2: Create fixtures from POC verified data**

```bash
mkdir -p /home/chuanbo/projects/JobRadar/backend/tests/fixtures_nowcoder
```

Path: `backend/tests/fixtures_nowcoder/search_sample.html` (minimal HTML containing 3 search-result links — this is what the SSR returns)

```html
<!DOCTYPE html>
<html><head><title>搜索结果</title></head>
<body>
<a href="/discuss/873597725214789632?sourceSSR=search" target="_blank" class="tw-cursor-pointer po" data-v-71d992d0>面经</a>
<a href="/discuss/353158311207968768?sourceSSR=search" target="_blank" class="tw-cursor-pointer po" data-v-71d992d0>思特奇数据分析面经</a>
<a href="/discuss/353154603472592896?sourceSSR=search" target="_blank" class="tw-cursor-pointer po" data-v-71d992d0>Vivo数据分析面经</a>
<a href="/discuss/873597725214789632?sourceSSR=search" target="_blank">duplicate-link-same-pid</a>
</body></html>
```

Path: `backend/tests/fixtures_nowcoder/post_sample.html`

```html
<!DOCTYPE html>
<html><head>
<title>面经_牛客网</title>
<meta name="description" content="📍面试公司：聚智🕐面试时间：26-4-14💻面试岗位：开发实习生❓面试问题：介绍单例模式String，StringBuilder和StringBuffer 的区别redis的哨兵机制_牛客网_牛客在手,offer不愁"/>
</head><body></body></html>
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/pytest tests/test_nowcoder_scraper.py -x 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'app.services.interview.nowcoder.scraper'`

- [ ] **Step 4: Implement scraper**

Path: `backend/app/services/interview/nowcoder/scraper.py`

```python
import html
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
_HEADERS = {"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9"}
_SEARCH_URL = "https://www.nowcoder.com/search/all?query={q}&type=all"
_POST_URL = "https://www.nowcoder.com/discuss/{pid}"
_TIMEOUT_SECONDS = 20

_SEARCH_LINK_RE = re.compile(
    r'href="/discuss/(\d+)\?sourceSSR=search"[^>]*>([^<]+)<'
)
_META_DESC_RE = re.compile(r'<meta name="description" content="([^"]+)"')


@dataclass(slots=True, frozen=True)
class PostMeta:
    pid: str
    title: str


@dataclass(slots=True)
class PostDetail:
    pid: str
    company: str
    interview_date: str
    position: str
    questions_text: str
    parse_status: str  # "ok" | "partial" | "failed"


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as r:
        return r.read().decode("utf-8", errors="replace")


def search(query: str, limit: int = 10) -> list[PostMeta]:
    url = _SEARCH_URL.format(q=urllib.parse.quote(query))
    htm = _fetch(url)
    out: list[PostMeta] = []
    seen: set[str] = set()
    for m in _SEARCH_LINK_RE.finditer(htm):
        pid, title = m.group(1), m.group(2).strip()
        if pid in seen:
            continue
        seen.add(pid)
        out.append(PostMeta(pid=pid, title=title))
        if len(out) >= limit:
            break
    return out


def fetch_post(pid: str) -> PostDetail:
    url = _POST_URL.format(pid=pid)
    htm = _fetch(url)
    desc_m = _META_DESC_RE.search(htm)
    if not desc_m:
        return PostDetail(pid=pid, company="", interview_date="", position="", questions_text="", parse_status="failed")
    desc = html.unescape(desc_m.group(1))
    desc = re.split(r'_牛客网_', desc, maxsplit=1)[0]

    fields = {"company": "", "interview_date": "", "position": "", "questions_text": ""}
    label_map = [
        ("📍面试公司", "company"),
        ("🕐面试时间", "interview_date"),
        ("💻面试岗位", "position"),
        ("❓面试问题", "questions_text"),
        ("面试公司", "company"),
        ("面试时间", "interview_date"),
        ("面试岗位", "position"),
        ("面试问题", "questions_text"),
    ]
    boundary = r'(?=📍|🕐|💻|❓|面试公司|面试时间|面试岗位|面试问题|$)'
    for label, key in label_map:
        if fields[key]:
            continue
        pat = rf'{re.escape(label)}[：: ]\s*(.+?){boundary}'
        m = re.search(pat, desc)
        if m:
            fields[key] = m.group(1).strip()

    have_any = any(fields.values())
    have_questions = bool(fields["questions_text"])
    if not have_any:
        status = "failed"
    elif not have_questions:
        status = "partial"
    else:
        status = "ok"
    return PostDetail(pid=pid, parse_status=status, **fields)
```

- [ ] **Step 5: Verify unit tests pass**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/pytest tests/test_nowcoder_scraper.py -x -m "not integration" 2>&1 | tail -10
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/interview/nowcoder/scraper.py backend/tests/test_nowcoder_scraper.py backend/tests/fixtures_nowcoder/
git commit -m "$(cat <<'EOF'
feat(interview): nowcoder scraper (search + post detail via meta tag)

Pure stdlib, no playwright. Parses the SSR meta description for the
emoji-template fields (company / date / position / questions). Returns
parse_status so callers can route partial/failed posts.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Summarizer

**Files:**
- Create: `backend/app/services/interview/nowcoder/summarizer.py`
- Create: `backend/tests/test_nowcoder_summarizer.py`

- [ ] **Step 1: Write failing tests**

Path: `backend/tests/test_nowcoder_summarizer.py`

```python
from unittest.mock import patch

from app.services.interview.nowcoder import summarizer
from app.services.interview.nowcoder.scraper import PostDetail


def _post(company="字节", date="26-4-14", pos="数据分析", qs="拆解DAU下降5%; A/B样本量计算") -> PostDetail:
    return PostDetail(pid="x", company=company, interview_date=date, position=pos, questions_text=qs, parse_status="ok")


def test_summarize_returns_empty_when_no_posts():
    assert summarizer.summarize_keyword("产品经理", []) == ""


def test_summarize_calls_llm_with_compact_input():
    posts = [_post(), _post(company="美团", qs="评估新功能成功标准; 留存归因")]
    with patch.object(summarizer, "_call_llm", return_value="## 高频考察方向\n- 指标拆解\n- A/B 实验") as mock:
        out = summarizer.summarize_keyword("数据分析师", posts)
    assert "高频考察方向" in out
    sent_prompt = mock.call_args.args[0]
    assert "数据分析师" in sent_prompt
    assert "字节" in sent_prompt and "美团" in sent_prompt


def test_summarize_returns_empty_on_llm_failure():
    posts = [_post()]
    with patch.object(summarizer, "_call_llm", side_effect=RuntimeError("upstream down")):
        out = summarizer.summarize_keyword("产品经理", posts)
    assert out == ""


def test_summarize_caps_post_count():
    posts = [_post(qs=f"问题{i}") for i in range(50)]
    with patch.object(summarizer, "_call_llm", return_value="ok") as mock:
        summarizer.summarize_keyword("k", posts)
    sent_prompt = mock.call_args.args[0]
    # Should not include all 50; we cap input to keep prompt small
    assert sent_prompt.count("问题") <= 20
```

- [ ] **Step 2: Run tests, expect import error**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/pytest tests/test_nowcoder_summarizer.py -x 2>&1 | tail -5
```

Expected: ModuleNotFoundError on `summarizer`.

- [ ] **Step 3: Implement summarizer**

Path: `backend/app/services/interview/nowcoder/summarizer.py`

```python
import json
from urllib import request as urllib_request

from app.services.interview.nowcoder.scraper import PostDetail
from app.services.resume_copilot.llm import build_resume_llm_client

_MAX_POSTS = 15
_PROMPT_TEMPLATE = """你是一个面试情报分析助手。下面是从公开面经中收集的真实面试题样本。请提炼出最近这个岗位的高频考察方向，输出 ≤400 字 markdown，结构如下：

## 高频考察方向
- 方向 A：一句话概括 + 哪几家公司在考
- 方向 B：...
- 方向 C：...（最多 5 个方向）

要求：
1. 不要直接复述原题
2. 把同类问题合并成一个方向
3. 优先列举出现频次高的方向

岗位：{keyword}

公开面经样本（{count} 条）：
{posts_block}
"""


def _format_posts(posts: list[PostDetail]) -> str:
    lines = []
    for i, p in enumerate(posts, 1):
        company = p.company or "未注明"
        date = p.interview_date or ""
        position = p.position or ""
        head = f"[{i}] {company} · {position} · {date}".strip(" ·")
        lines.append(head)
        if p.questions_text:
            lines.append(f"  问题: {p.questions_text[:300]}")
    return "\n".join(lines)


def _call_llm(prompt: str) -> str:
    client = build_resume_llm_client()
    payload = {
        "model": client.model,
        "stream": False,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib_request.Request(
        client.chat_completions_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {client.api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=client.timeout_seconds) as r:
        body = json.loads(r.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def summarize_keyword(keyword: str, posts: list[PostDetail]) -> str:
    if not posts:
        return ""
    capped = posts[:_MAX_POSTS]
    prompt = _PROMPT_TEMPLATE.format(
        keyword=keyword,
        count=len(capped),
        posts_block=_format_posts(capped),
    )
    try:
        return _call_llm(prompt).strip()
    except Exception:
        return ""
```

- [ ] **Step 4: Verify tests pass**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/pytest tests/test_nowcoder_summarizer.py -x 2>&1 | tail -8
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/interview/nowcoder/summarizer.py backend/tests/test_nowcoder_summarizer.py
git commit -m "$(cat <<'EOF'
feat(interview): nowcoder summarizer (LLM compresses N posts → 400-char md)

Caps input at 15 posts and returns empty string on any LLM failure so
the orchestrator can store the raw posts even when summarization is
broken (next refresh will retry summarize without re-scraping).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Intel Provider

**Files:**
- Create: `backend/app/services/interview/nowcoder/intel_provider.py`
- Create: `backend/tests/test_nowcoder_intel_provider.py`

- [ ] **Step 1: Write failing tests**

Path: `backend/tests/test_nowcoder_intel_provider.py`

```python
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import InterviewIntelKeyword
from app.services.interview.nowcoder import intel_provider


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()


def _seed(db, keyword: str, summary: str, count: int = 5):
    db.add(InterviewIntelKeyword(
        keyword=keyword, summary_md=summary, source_count=count, generated_at=datetime.utcnow()
    ))
    db.commit()


def test_returns_none_when_no_keyword_table_rows(db):
    assert intel_provider.get_intel_for_target_job(db, "anything") is None


def test_exact_match(db):
    _seed(db, "产品经理", "## 高频\n- 用户增长")
    out = intel_provider.get_intel_for_target_job(db, "产品经理")
    assert out is not None
    assert "用户增长" in out.summary_md
    assert out.source_count == 5


def test_substring_match(db):
    _seed(db, "产品经理", "summary")
    out = intel_provider.get_intel_for_target_job(db, "字节跳动产品经理实习")
    assert out is not None and out.keyword == "产品经理"


def test_no_match_returns_none(db):
    _seed(db, "产品经理", "summary")
    assert intel_provider.get_intel_for_target_job(db, "宁德时代电芯研发") is None


def test_empty_summary_returns_none(db):
    _seed(db, "产品经理", "")
    assert intel_provider.get_intel_for_target_job(db, "产品经理") is None


def test_db_error_returns_none(db):
    db.close()  # subsequent queries fail
    assert intel_provider.get_intel_for_target_job(db, "产品经理") is None
```

- [ ] **Step 2: Run tests, expect import error**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/pytest tests/test_nowcoder_intel_provider.py -x 2>&1 | tail -5
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement intel_provider**

Path: `backend/app/services/interview/nowcoder/intel_provider.py`

```python
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models import InterviewIntelKeyword


@dataclass(slots=True, frozen=True)
class IntelView:
    keyword: str
    summary_md: str
    source_count: int


def get_intel_for_target_job(db: Session, target_job: str) -> Optional[IntelView]:
    if not target_job:
        return None
    target = target_job.strip()
    if not target:
        return None
    try:
        rows = db.query(InterviewIntelKeyword).all()
    except Exception:
        return None

    # Pass 1: exact match
    for row in rows:
        if row.keyword == target and (row.summary_md or "").strip():
            return IntelView(keyword=row.keyword, summary_md=row.summary_md, source_count=row.source_count or 0)

    # Pass 2: substring match (longest keyword wins)
    candidates = [row for row in rows if row.keyword and row.keyword in target and (row.summary_md or "").strip()]
    if not candidates:
        return None
    best = max(candidates, key=lambda r: len(r.keyword))
    return IntelView(keyword=best.keyword, summary_md=best.summary_md, source_count=best.source_count or 0)
```

- [ ] **Step 4: Verify tests pass**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/pytest tests/test_nowcoder_intel_provider.py -x 2>&1 | tail -10
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/interview/nowcoder/intel_provider.py backend/tests/test_nowcoder_intel_provider.py
git commit -m "$(cat <<'EOF'
feat(interview): nowcoder intel_provider (exact + substring keyword match)

Read-only DB lookup invoked from build_interview_system_prompt. Returns
None on any failure or when summary is empty so the prompt builder
silently degrades to base behavior.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Refresh Job Orchestrator

**Files:**
- Create: `backend/app/services/interview/nowcoder/refresh_job.py`
- Create: `backend/tests/test_nowcoder_refresh_job.py`

- [ ] **Step 1: Write failing tests**

Path: `backend/tests/test_nowcoder_refresh_job.py`

```python
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import InterviewIntelKeyword, InterviewIntelPost
from app.services.interview.nowcoder import refresh_job
from app.services.interview.nowcoder.scraper import PostDetail, PostMeta


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()


_KEYWORDS_STUB = [
    {"chip": "产品经理", "query": "产品经理面经"},
    {"chip": "数据分析师", "query": "数据分析面经"},
]


def _meta(pid):
    return PostMeta(pid=pid, title=f"title-{pid}")


def _detail(pid, status="ok"):
    return PostDetail(
        pid=pid, company="A", interview_date="26-4-14", position="P",
        questions_text="Q1; Q2", parse_status=status,
    )


def test_run_refresh_writes_keyword_and_posts(db):
    with (
        patch.object(refresh_job, "_load_keywords", return_value=_KEYWORDS_STUB),
        patch("app.services.interview.nowcoder.refresh_job.scraper.search",
              side_effect=lambda q, limit: [_meta("100"), _meta("200")]),
        patch("app.services.interview.nowcoder.refresh_job.scraper.fetch_post",
              side_effect=lambda pid: _detail(pid)),
        patch("app.services.interview.nowcoder.refresh_job.summarizer.summarize_keyword",
              return_value="## summary"),
        patch("app.services.interview.nowcoder.refresh_job.time.sleep", return_value=None),
    ):
        stats = refresh_job.run_refresh(db)

    assert stats.keywords_total == 2
    assert stats.keywords_ok == 2
    assert stats.posts_fetched == 4  # 2 chips × 2 posts
    assert db.query(InterviewIntelKeyword).count() == 2
    assert db.query(InterviewIntelPost).count() == 4


def test_run_refresh_skips_recently_fetched_posts(db):
    db.add(InterviewIntelPost(
        pid="100", keyword="产品经理", title="cached", fetched_at=datetime.utcnow() - timedelta(hours=2),
        parse_status="ok",
    ))
    db.commit()
    fetch_calls = []

    def fake_fetch(pid):
        fetch_calls.append(pid)
        return _detail(pid)

    with (
        patch.object(refresh_job, "_load_keywords", return_value=[_KEYWORDS_STUB[0]]),
        patch("app.services.interview.nowcoder.refresh_job.scraper.search",
              return_value=[_meta("100"), _meta("200")]),
        patch("app.services.interview.nowcoder.refresh_job.scraper.fetch_post", side_effect=fake_fetch),
        patch("app.services.interview.nowcoder.refresh_job.summarizer.summarize_keyword",
              return_value="x"),
        patch("app.services.interview.nowcoder.refresh_job.time.sleep", return_value=None),
    ):
        refresh_job.run_refresh(db)

    assert fetch_calls == ["200"]  # 100 was skipped (within 24h)


def test_run_refresh_keyword_failure_does_not_block_others(db):
    def search_side(query, limit):
        if "产品经理" in query:
            raise RuntimeError("network down")
        return [_meta("777")]

    with (
        patch.object(refresh_job, "_load_keywords", return_value=_KEYWORDS_STUB),
        patch("app.services.interview.nowcoder.refresh_job.scraper.search", side_effect=search_side),
        patch("app.services.interview.nowcoder.refresh_job.scraper.fetch_post", return_value=_detail("777")),
        patch("app.services.interview.nowcoder.refresh_job.summarizer.summarize_keyword", return_value="ok"),
        patch("app.services.interview.nowcoder.refresh_job.time.sleep", return_value=None),
    ):
        stats = refresh_job.run_refresh(db)

    assert stats.keywords_failed == 1
    assert stats.keywords_ok == 1
    rows = db.query(InterviewIntelKeyword).all()
    by_kw = {r.keyword: r for r in rows}
    assert by_kw["产品经理"].last_error
    assert by_kw["数据分析师"].summary_md == "ok"


def test_status_helpers_round_trip(db):
    refresh_job._record_status({"last_status": "ok", "keywords_total": 16})
    out = refresh_job.get_last_refresh_status()
    assert out["last_status"] == "ok"
    assert out["keywords_total"] == 16
```

- [ ] **Step 2: Run tests, expect failures**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/pytest tests/test_nowcoder_refresh_job.py -x 2>&1 | tail -5
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement refresh_job**

Path: `backend/app/services/interview/nowcoder/refresh_job.py`

```python
import json
import pathlib
import random
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Optional

import yaml
from sqlalchemy.orm import Session

from app.models import InterviewIntelKeyword, InterviewIntelPost
from app.services.interview.nowcoder import scraper, summarizer

_KEYWORDS_PATH = pathlib.Path(__file__).parent / "keywords.yaml"
_DEFAULT_LIMIT = 10
_FETCH_FRESH_HOURS = 24
_STATUS_LOCK = threading.Lock()
_STATUS: dict = {}


@dataclass(slots=True)
class RefreshStats:
    keywords_total: int = 0
    keywords_ok: int = 0
    keywords_failed: int = 0
    posts_fetched: int = 0
    last_error: str = ""


def _load_keywords() -> list[dict]:
    raw = _KEYWORDS_PATH.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or []
    return [d for d in data if isinstance(d, dict) and d.get("chip") and d.get("query")]


def _is_fresh(post: Optional[InterviewIntelPost]) -> bool:
    if post is None or post.fetched_at is None:
        return False
    return datetime.utcnow() - post.fetched_at < timedelta(hours=_FETCH_FRESH_HOURS)


def _upsert_post(db: Session, keyword: str, detail: scraper.PostDetail, title: str) -> None:
    row = db.query(InterviewIntelPost).filter_by(pid=detail.pid, keyword=keyword).one_or_none()
    if row is None:
        row = InterviewIntelPost(pid=detail.pid, keyword=keyword)
        db.add(row)
    row.title = title
    row.company = detail.company
    row.interview_date = detail.interview_date
    row.position = detail.position
    row.questions_text = detail.questions_text
    row.parse_status = detail.parse_status
    row.fetched_at = datetime.utcnow()


def _upsert_keyword(db: Session, keyword: str, summary: str, source_count: int, error: str = "") -> None:
    row = db.query(InterviewIntelKeyword).filter_by(keyword=keyword).one_or_none()
    if row is None:
        row = InterviewIntelKeyword(keyword=keyword)
        db.add(row)
    row.summary_md = summary
    row.source_count = source_count
    row.generated_at = datetime.utcnow()
    row.last_error = error


def _record_status(payload: dict) -> None:
    with _STATUS_LOCK:
        _STATUS.clear()
        _STATUS.update(payload)


def get_last_refresh_status() -> dict:
    with _STATUS_LOCK:
        return dict(_STATUS)


def _process_keyword(db: Session, chip: str, query: str, stats: RefreshStats) -> None:
    metas = scraper.search(query, limit=_DEFAULT_LIMIT)
    ok_posts: list[scraper.PostDetail] = []
    for meta in metas:
        existing = db.query(InterviewIntelPost).filter_by(pid=meta.pid, keyword=chip).one_or_none()
        if _is_fresh(existing):
            if existing.parse_status == "ok":
                ok_posts.append(scraper.PostDetail(
                    pid=existing.pid, company=existing.company, interview_date=existing.interview_date,
                    position=existing.position, questions_text=existing.questions_text, parse_status="ok",
                ))
            continue
        detail = scraper.fetch_post(meta.pid)
        _upsert_post(db, chip, detail, meta.title)
        if detail.parse_status == "ok":
            ok_posts.append(detail)
        stats.posts_fetched += 1
        time.sleep(random.uniform(0.4, 1.0))
    db.commit()

    summary = summarizer.summarize_keyword(chip, ok_posts) if ok_posts else ""
    _upsert_keyword(db, chip, summary, len(ok_posts))
    db.commit()


def run_refresh(db: Session) -> RefreshStats:
    stats = RefreshStats()
    started = datetime.utcnow()
    try:
        keywords = _load_keywords()
    except Exception as e:
        _record_status({"last_run": started.isoformat(), "last_status": "failed", "last_error": f"keywords yaml: {e}"})
        stats.last_error = str(e)
        return stats

    stats.keywords_total = len(keywords)
    for entry in keywords:
        chip = entry["chip"]
        query = entry["query"]
        try:
            _process_keyword(db, chip, query, stats)
            stats.keywords_ok += 1
        except Exception as e:
            stats.keywords_failed += 1
            try:
                _upsert_keyword(db, chip, "", 0, error=str(e)[:500])
                db.commit()
            except Exception:
                db.rollback()

    overall_status = "ok"
    if stats.keywords_failed and stats.keywords_failed == stats.keywords_total:
        overall_status = "failed"
    elif stats.keywords_failed:
        overall_status = "partial"

    _record_status({
        "last_run": started.isoformat() + "Z",
        "last_status": overall_status,
        "keywords_total": stats.keywords_total,
        "keywords_ok": stats.keywords_ok,
        "keywords_failed": stats.keywords_failed,
        "posts_fetched": stats.posts_fetched,
        "last_error": stats.last_error or None,
    })
    return stats
```

- [ ] **Step 4: Verify tests pass**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/pytest tests/test_nowcoder_refresh_job.py -x 2>&1 | tail -10
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/interview/nowcoder/refresh_job.py backend/tests/test_nowcoder_refresh_job.py
git commit -m "$(cat <<'EOF'
feat(interview): nowcoder nightly refresh orchestrator

Iterates 16 keyword entries; per-chip: search → 24h-dedup → fetch_post →
sleep 0.4-1s → summarize → upsert. Per-keyword failure isolated. Records
in-memory status for /api/scheduler exposure.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Inject into `build_interview_system_prompt`

**Files:**
- Modify: `backend/app/services/interview/llm.py`
- Modify: `backend/app/routers/interview.py` (call sites need to pass db)
- Modify: `backend/tests/test_interview_service.py` (add injection tests)

- [ ] **Step 1: Add failing tests to `backend/tests/test_interview_service.py`**

Append at the end of the file:

```python
from unittest.mock import patch
from app.services.interview.nowcoder.intel_provider import IntelView


def test_system_prompt_no_db_uses_base_only():
    prompt = build_interview_system_prompt("产品经理", db=None)
    assert "高频考察方向" not in prompt
    assert "产品经理" in prompt


def test_system_prompt_injects_intel_when_present():
    fake = IntelView(keyword="产品经理", summary_md="## 高频考察方向\n- 用户增长", source_count=8)
    with patch("app.services.interview.llm.intel_provider.get_intel_for_target_job", return_value=fake):
        prompt = build_interview_system_prompt("字节产品经理实习", db="dummy")
    assert "高频考察方向" in prompt
    assert "用户增长" in prompt
    assert "8 条" in prompt or "8条" in prompt


def test_system_prompt_no_intel_uses_base_only():
    with patch("app.services.interview.llm.intel_provider.get_intel_for_target_job", return_value=None):
        prompt = build_interview_system_prompt("宁德时代电芯研发", db="dummy")
    assert "高频考察方向" not in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/pytest tests/test_interview_service.py -x 2>&1 | tail -10
```

Expected: failures on the new tests (the function signature doesn't accept `db=`).

- [ ] **Step 3: Update `build_interview_system_prompt`**

Path: `backend/app/services/interview/llm.py`

Replace the existing `build_interview_system_prompt` and `stream_interview_turn` with this version (keeps the rest of the file unchanged):

```python
import json
from typing import Iterator, Optional
from urllib import request as urllib_request

from sqlalchemy.orm import Session

from app.services.interview.nowcoder import intel_provider
from app.services.resume_copilot.llm import build_resume_llm_client

INTERVIEW_END_MARKER = '[INTERVIEW_END]'

_TURN_LIMIT = 14


def build_interview_system_prompt(target_job: str, db: Optional[Session] = None) -> str:
    base = f"""你是一位专业的校招面试官，正在对一名应届生进行一对一面试。
目标岗位：{target_job}

## 面试规则
1. 前 3 轮出行为类问题（如"介绍一个你主导过的项目"、"描述一次你解决团队冲突的经历"）
2. 第 4 轮起穿插岗位专项问题，根据目标岗位选择技术或业务方向题
3. 根据候选人的回答决定：深挖追问 还是 切换下一题
4. 每次只问一个问题，语气专业但不刻板，不提前评价候选人表现
5. 累计对话达到 {_TURN_LIMIT} 轮后，给出一句简短的收尾语，并在消息末尾追加标记：{INTERVIEW_END_MARKER}
6. 如候选人主动说"结束面试"，立即收尾并追加 {INTERVIEW_END_MARKER}

## 开场
第一条消息：用一句话介绍自己的面试官身份，然后直接提出第一个行为类问题。"""

    if db is None:
        return base

    intel = intel_provider.get_intel_for_target_job(db, target_job)
    if intel is None or not intel.summary_md.strip():
        return base

    return (
        base
        + "\n\n## 最近公开面经的高频考察方向\n"
        + intel.summary_md.strip()
        + f"\n\n（以上方向参考了 {intel.source_count} 条来自牛客网的公开面经，作为出题灵感，不要直接复述原题。）"
    )


def stream_interview_turn(
    target_job: str, messages: list[dict], db: Optional[Session] = None
) -> Iterator[str]:
    client = build_resume_llm_client()
    payload = {
        'model': client.model,
        'stream': True,
        'messages': [
            {'role': 'system', 'content': build_interview_system_prompt(target_job, db=db)},
            *messages,
        ],
    }
    req = urllib_request.Request(
        client.chat_completions_url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {client.api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    stream_timeout = max(client.timeout_seconds, 120)
    with urllib_request.urlopen(req, timeout=stream_timeout) as response:
        for raw_line in response:
            line = raw_line.decode('utf-8').rstrip('\n')
            if line:
                yield line + '\n'
```

- [ ] **Step 4: Update the router callsite to pass `db`**

Find the place in `backend/app/routers/interview.py` that calls `stream_interview_turn(...)`. Locate it:

```bash
grep -n "stream_interview_turn" /home/chuanbo/projects/JobRadar/backend/app/routers/interview.py
```

The handler that calls it should already have a `db: Session = Depends(get_db)` parameter (standard FastAPI pattern). Pass `db` through:

```python
# Change call from:
stream_interview_turn(payload.target_job, payload.messages_dict)
# To:
stream_interview_turn(payload.target_job, payload.messages_dict, db=db)
```

If the handler does not yet take `db`, add it:

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from app.database import get_db

@router.post("/turn")
def post_turn(payload: ..., db: Session = Depends(get_db)):
    ...
    return StreamingResponse(stream_interview_turn(payload.target_job, payload.messages_dict, db=db), ...)
```

- [ ] **Step 5: Verify tests pass**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/pytest tests/test_interview_service.py -x 2>&1 | tail -10
```

Expected: all tests pass (existing 5 + 3 new).

- [ ] **Step 6: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/interview/llm.py backend/app/routers/interview.py backend/tests/test_interview_service.py
git commit -m "$(cat <<'EOF'
feat(interview): inject nowcoder intel into system prompt

build_interview_system_prompt(db=None) now optionally pulls a chip-level
summary via intel_provider and appends it to the base prompt. Falls back
silently when no db is passed or no matching keyword exists.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Register Scheduler Job

**Files:**
- Modify: `backend/app/services/scheduler_service.py`

- [ ] **Step 1: Add the new job and helper to `scheduler_service.py`**

Apply these specific edits to `backend/app/services/scheduler_service.py`:

Add to the imports block:

```python
from app.services.interview.nowcoder.refresh_job import (
    get_last_refresh_status as get_nowcoder_status,
    run_refresh as run_nowcoder_refresh,
)
```

Add two new constants alongside `JOB_ID`:

```python
NOWCODER_INTEL_JOB_ID = "nowcoder_intel_refresh"
NOWCODER_INTEL_CRON = "0 9 * * *"  # 09:00 Asia/Shanghai
```

Add a job function near `_daily_crawl_job`:

```python
def _nowcoder_intel_job():
    db = SessionLocal()
    try:
        run_nowcoder_refresh(db)
    except Exception as e:
        print(f"[NOWCODER INTEL ERROR] {e}")
    finally:
        db.close()
```

Inside `start_scheduler()`, add a third `add_job` call after the existing two:

```python
        scheduler.add_job(
            _nowcoder_intel_job,
            CronTrigger.from_crontab(NOWCODER_INTEL_CRON, timezone=SCHEDULER_TZ),
            id=NOWCODER_INTEL_JOB_ID,
            replace_existing=True,
        )
```

Extend `get_scheduler_info()` to include the new job's status. Replace the function body:

```python
def get_scheduler_info() -> dict:
    job = scheduler.get_job(JOB_ID)
    next_run = None
    if job is not None:
        next_run_time = getattr(job, "next_run_time", None)
        if next_run_time is not None:
            next_run = next_run_time.isoformat()

    nowcoder_job = scheduler.get_job(NOWCODER_INTEL_JOB_ID)
    nowcoder_next_run = None
    if nowcoder_job is not None:
        nrt = getattr(nowcoder_job, "next_run_time", None)
        if nrt is not None:
            nowcoder_next_run = nrt.isoformat()

    nowcoder_status = get_nowcoder_status()
    nowcoder_status["cron_expression"] = NOWCODER_INTEL_CRON
    nowcoder_status["next_run"] = nowcoder_next_run

    return {
        "cron_expression": _current_cron,
        "next_run": next_run,
        "is_active": scheduler.running,
        "nowcoder_intel_refresh": nowcoder_status,
    }
```

- [ ] **Step 2: Update `SchedulerConfigOut` to allow the new field**

Path: `backend/app/schemas.py`, replace the `SchedulerConfigOut` block:

```python
class SchedulerConfigOut(BaseModel):
    cron_expression: str
    next_run: Optional[str] = None
    is_active: bool
    nowcoder_intel_refresh: Optional[dict] = None
```

- [ ] **Step 3: Restart backend, hit endpoint to verify**

```bash
pkill -f "uvicorn app.main:app.*--port 8002" 2>/dev/null
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. /home/chuanbo/projects/JobRadar/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload &
sleep 5
curl -s http://127.0.0.1:8002/api/scheduler | python3 -m json.tool
```

Expected output includes:

```json
{
  "cron_expression": "0 8 * * *",
  "next_run": "...",
  "is_active": true,
  "nowcoder_intel_refresh": {
    "cron_expression": "0 9 * * *",
    "next_run": "..."
  }
}
```

`last_status` etc. will be missing until the first run completes — that's expected.

- [ ] **Step 4: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/scheduler_service.py backend/app/schemas.py
git commit -m "$(cat <<'EOF'
feat(scheduler): register nowcoder_intel_refresh cron at 09:00 Asia/Shanghai

Adds the third APScheduler job alongside daily_crawl and guest_cleanup.
Status surfaced through /api/scheduler so refresh health is visible by
curl on the VPS without a separate alerting channel.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Manual smoke test (real Nowcoder + LLM)

**Files:** none

- [ ] **Step 1: Trigger refresh manually for one keyword**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/python <<'PY'
from app.database import SessionLocal
from app.services.interview.nowcoder import refresh_job

db = SessionLocal()
# Patch the keyword loader to limit to 1 chip for speed
orig = refresh_job._load_keywords
refresh_job._load_keywords = lambda: [{"chip": "数据分析师", "query": "数据分析面经"}]
try:
    stats = refresh_job.run_refresh(db)
    print("STATS:", stats)
    print("STATUS:", refresh_job.get_last_refresh_status())
finally:
    refresh_job._load_keywords = orig
    db.close()
PY
```

Expected: `keywords_ok=1`, `posts_fetched >= 1`, `last_status='ok'`.

- [ ] **Step 2: Verify DB rows**

```bash
sqlite3 data/jobradar.db "SELECT keyword, source_count, length(summary_md), generated_at FROM interview_intel_keywords;"
sqlite3 data/jobradar.db "SELECT pid, keyword, parse_status, length(questions_text) FROM interview_intel_posts LIMIT 5;"
```

Expected: 1 keyword row with non-zero `source_count` and a multi-hundred-char `summary_md`; ≥1 post rows with `parse_status='ok'` and non-empty `questions_text`.

- [ ] **Step 3: Verify the prompt now contains the intel**

```bash
PYTHONPATH=. .venv/bin/python <<'PY'
from app.database import SessionLocal
from app.services.interview.llm import build_interview_system_prompt
db = SessionLocal()
print(build_interview_system_prompt("字节跳动数据分析师实习", db=db))
db.close()
PY
```

Expected: prompt ends with `## 最近公开面经的高频考察方向` block followed by the markdown summary and the "参考了 N 条" line.

- [ ] **Step 4: Verify integration test against real Nowcoder still passes**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/pytest tests/test_nowcoder_scraper.py -x -m integration 2>&1 | tail -5
```

Expected: 1 passed.

- [ ] **Step 5: Final cross-test (full suite minus the broken one)**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ --ignore=tests/test_resume_copilot_service.py -x -m "not integration" 2>&1 | tail -15
```

Expected: all green.

- [ ] **Step 6: Final commit (only if anything changed during smoke testing)**

If smoke testing surfaced fixes, commit them. Otherwise skip.

---

## Self-Review

I checked the spec against this plan. Coverage map:

| Spec section | Tasks |
|---|---|
| §1 chip set (16 entries) | Task 2 yaml |
| §Components (5 new files) | Tasks 3,4,5,6 + Task 7 callsite + Task 8 scheduler |
| §Data Model (2 tables, composite PK) | Task 1 |
| §Data Flow §3a nightly | Task 6 |
| §Data Flow §3b injection | Task 7 |
| §Error Handling table | Tasks 5,6,7 (intel returns None, refresh isolates per-chip failure, prompt builder degrades silently) |
| §Observability `/api/scheduler` | Task 8 |
| §Politeness (UA, sleep 0.4-1s) | Task 3 (`_HEADERS`) + Task 6 (`time.sleep(uniform(0.4,1.0))`) |
| §Testing matrix | Tasks 3,4,5,6,7 each include unit tests; integration test in Task 3 |

Ambiguity I resolved:
- Spec said "17 chips"; actual `PRESETS` count is 16 — yaml uses 16
- Spec didn't specify cron string for the scheduler job — used `0 9 * * *` (09:00 Asia/Shanghai, after `daily_crawl` at 08:00)
- Spec mentioned "重试 1 次（间隔 5s）" for 5xx — left this for now: the per-chip exception handler isolates failures already, and the cron next day is only 24h away. Adding retry adds complexity for a low-value gain. (Documented as future work below.)

Out of scope (kept for future):
- 5xx retry-once with backoff
- 429 global stop-24h flag (currently 429 just kills the per-chip request; nightly continues with other chips)
- Free textarea path
- Report-page source banner

These are all intentional simplifications; the spec's degradation path covers them by always falling back to base prompt.

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-27-nowcoder-interview-intel.md`.**
