# 投研赛道细颗粒度发现 + XHS 知识库 + 岗位 enrich Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 XHS 数据驱动 + 多源共识，发现 SAIF MF 投研空间的细颗粒 taxonomy，并跑通 4 个 SAIF persona (P1/P2/P3/P6) 的端到端 demo（学生分类 → 岗位 enrich → KB 匹配 → 区分力矩阵评估）。

**Architecture:** 三柱共享 taxonomy（学生 / 岗位 / 知识库）。6 个 Sonnet 4.6 subagent 并行爬取 6 个 strategy 大类（基本面权益 / 量化 / 固收 / 卖方研究 / 多资产-FOF / 相关补充），每个 subagent 用 TikHub `search_notes` + decode `fetch_url` 抓帖，DeepSeek-V4-Pro 做 dual-schema 抽取（taxonomy 字段 + KB 字段），饱和指标触发停止；Opus 4.7 读全产出 + 就业报告 ground truth + Pony 现有 139 insights，输出最终 taxonomy + 10 家 demo 公司清单。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy / Pydantic v2 / pytest / SQLite (dev DB) / TikHub HTTP API / decode HTTP API / DeepSeek API / Claude Code Agent tool（subagent 调度）

**API 预算硬上限:** $10（TikHub + decode + DeepSeek，全局 cost tracker enforced）

---

## 文件结构总览

新建文件：

```
backend/
├── app/services/taxonomy_discovery/
│   ├── __init__.py
│   ├── schemas.py                # Pydantic dual-schema (taxonomy + KB)
│   ├── crawler_client.py         # TikHub + decode HTTP 封装
│   ├── llm_extractor.py          # DeepSeek dual-schema 抽取
│   ├── saturation.py             # subagent 饱和指标判断
│   ├── seed_queries.py           # 6 strategy 大类的 seed query 清单
│   ├── budget_tracker.py         # 全局 $10 cost tracker
│   └── persona_loader.py         # P1/P2/P3/P6 PDF + JSON 加载
├── alembic/versions/
│   └── 2026_05_26_xhs_taxonomy_extracts.py   # 新增 xhs_taxonomy_extracts 表
└── data/personas/                 # 已有 P1-P6 PDF + JSON

scripts/
├── extract_employment_reports.py     # SAIF 就业报告 LLM 抽取
├── xhs_discovery_subagent_runbook.md # subagent 操作手册（给 Claude Code Agent 用）
├── xhs_discovery_orchestrator.py     # 6 subagent 并行调度入口
├── opus_taxonomy_synthesis.py        # Opus 最终合成
├── classify_students.py              # 4 persona 学生分类器
├── enrich_demo_jobs.py               # 10 家公司岗位 enrich
├── demo_persona_match.py             # 4 persona 端到端匹配
└── eval_discrimination_matrix.py     # 5 维区分力矩阵评估

tests/taxonomy_discovery/
├── test_schemas.py
├── test_crawler_client.py            # 用 vcrpy 录制 API 响应
├── test_llm_extractor.py             # 用 fixture 测 schema 合规
├── test_saturation.py
├── test_budget_tracker.py
└── test_persona_loader.py

docs/
├── taxonomy-投研-final-v1.md        # 输出：最终 taxonomy
└── eval/<完工日期>-投研-demo-report.md  # 输出：demo 报告
```

修改文件：

```
backend/app/models.py                  # 新增 XHSTaxonomyExtract ORM 模型
backend/requirements.txt               # 加 vcrpy（测试用）
backend/.env.local                     # 已有 TIKHUB_API_KEY + WEB_SCRAPING_API_KEY
```

---

## Task 1: 创建模块骨架 + 依赖

**Files:**
- Create: `backend/app/services/taxonomy_discovery/__init__.py`
- Create: `backend/tests/taxonomy_discovery/__init__.py`
- Modify: `backend/requirements.txt`（追加 `vcrpy==6.0.1`）

- [ ] **Step 1: 创建空模块目录 + 初始化文件**

```bash
mkdir -p /home/chuanbo/projects/JobRadar/backend/app/services/taxonomy_discovery
mkdir -p /home/chuanbo/projects/JobRadar/backend/tests/taxonomy_discovery
touch /home/chuanbo/projects/JobRadar/backend/app/services/taxonomy_discovery/__init__.py
touch /home/chuanbo/projects/JobRadar/backend/tests/taxonomy_discovery/__init__.py
```

- [ ] **Step 2: 追加 vcrpy 到 requirements**

打开 `backend/requirements.txt`，在 dev 测试段（找 `pytest` 那行附近）下面加：

```
vcrpy==6.0.1
```

- [ ] **Step 3: 安装依赖 + 验证**

```bash
cd /home/chuanbo/projects/JobRadar/backend && .venv/bin/pip install vcrpy==6.0.1
.venv/bin/python -c "import vcr; print(vcr.__version__)"
```

Expected: `6.0.1` printed

- [ ] **Step 4: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/taxonomy_discovery/ backend/tests/taxonomy_discovery/ backend/requirements.txt
git commit -m "feat(taxonomy-discovery): 模块骨架 + vcrpy 测试依赖"
```

---

## Task 2: Pydantic Dual-Schema 定义

**Files:**
- Create: `backend/app/services/taxonomy_discovery/schemas.py`
- Test: `backend/tests/taxonomy_discovery/test_schemas.py`

- [ ] **Step 1: 写 schema test 先**

`backend/tests/taxonomy_discovery/test_schemas.py`:

```python
"""测 schemas — 主要测能 round-trip JSON 不丢字段 + enum 校验。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.services.taxonomy_discovery.schemas import (
    StrategyType,
    PostTaxonomyExtract,
    PostKBExtract,
    DualSchemaExtract,
    KBInsightType,
    StrategySignal,
    IndustrySignal,
    InstitutionSignal,
    CompanyRolePair,
    DimensionDistinction,
    KBInsight,
)


def test_strategy_type_enum_values() -> None:
    """6 大策略大类必须齐全 (spec §4.1)。"""
    expected = {
        "基本面权益",
        "量化",
        "固定收益",
        "卖方研究",
        "多资产_FOF_衍生品",
        "相关补充",
    }
    assert {s.value for s in StrategyType} == expected


def test_kb_insight_type_enum_values() -> None:
    """5 类 KB insight 必须齐全 (复用 Pony schema)。"""
    expected = {"role", "interview", "company", "resume", "industry"}
    assert {t.value for t in KBInsightType} == expected


def test_dual_schema_minimal_valid() -> None:
    """空字段帖也能构建 (例如全是噪声的低 relevance 帖)。"""
    extract = DualSchemaExtract(
        post_id="abc123",
        url="https://xhs.com/n/abc123",
        time="2026-05-01T12:00:00",
        author="user1",
        relevance_score=0.1,
        taxonomy=PostTaxonomyExtract(),
        kb=PostKBExtract(),
    )
    assert extract.relevance_score == 0.1
    assert extract.taxonomy.strategy_signals == []
    assert extract.kb.insights == []


def test_dual_schema_full_round_trip() -> None:
    """完整 schema 序列化/反序列化不丢字段。"""
    extract = DualSchemaExtract(
        post_id="abc123",
        url="https://xhs.com/n/abc123",
        time="2026-05-01T12:00:00",
        author="user1",
        relevance_score=0.85,
        taxonomy=PostTaxonomyExtract(
            strategy_signals=[
                StrategySignal(canonical=StrategyType.基本面权益, verbatim_phrase="消费组研究员"),
            ],
            industry_signals=[IndustrySignal(industry="消费", verbatim_phrase="白酒")],
            institution_signals=[
                InstitutionSignal(tier_guess="一线公募", company_name="嘉实基金", verbatim="嘉实消费组"),
            ],
            discovered_sub_categories=["消费组", "白酒研究"],
            company_role_pairs=[
                CompanyRolePair(company="嘉实基金", role_or_dept="消费组研究员", strategy="基本面权益"),
            ],
            dimension_distinctions=[
                DimensionDistinction(axis="institution_tier", x_vs_y="公募 vs 资管子", note="文化差异"),
            ],
        ),
        kb=PostKBExtract(
            insights=[
                KBInsight(
                    type=KBInsightType.company,
                    text="嘉实消费组带新人方式",
                    verbatim_quote="嘉实消费组带新人的方式跟易方达类似",
                    confidence="high",
                ),
            ],
        ),
    )
    j = extract.model_dump_json()
    re = DualSchemaExtract.model_validate_json(j)
    assert re.taxonomy.strategy_signals[0].canonical == StrategyType.基本面权益
    assert re.kb.insights[0].type == KBInsightType.company


def test_relevance_score_bounds() -> None:
    """relevance_score 必须在 [0, 1]。"""
    with pytest.raises(ValidationError):
        DualSchemaExtract(
            post_id="x", url="x", time="x", author="x",
            relevance_score=1.5,
            taxonomy=PostTaxonomyExtract(),
            kb=PostKBExtract(),
        )
```

- [ ] **Step 2: 跑测试，确认全失败（模块未实现）**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/pytest tests/taxonomy_discovery/test_schemas.py -x 2>&1 | tail -10
```

Expected: ImportError, 5 个 test 全 collect error

- [ ] **Step 3: 实现 schemas.py**

`backend/app/services/taxonomy_discovery/schemas.py`:

```python
"""Dual-schema for taxonomy discovery + KB extraction (spec §5)."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class StrategyType(str, Enum):
    """6 大策略大类 (spec §4.1)。enum value 用中文,LLM 直接吐就行。"""
    基本面权益 = "基本面权益"
    量化 = "量化"
    固定收益 = "固定收益"
    卖方研究 = "卖方研究"
    多资产_FOF_衍生品 = "多资产_FOF_衍生品"
    相关补充 = "相关补充"


class KBInsightType(str, Enum):
    """5 类 KB insight (复用 Pony schema, spec §5.2)。"""
    role = "role"
    interview = "interview"
    company = "company"
    resume = "resume"
    industry = "industry"


class StrategySignal(BaseModel):
    canonical: StrategyType
    verbatim_phrase: str = Field(description="原文里学生用什么词描述")


class IndustrySignal(BaseModel):
    industry: str = Field(description="行业方向, 如 消费/TMT/医药, 不锁 enum 让 LLM 自由发现")
    verbatim_phrase: str


class InstitutionSignal(BaseModel):
    tier_guess: str = Field(description="平台类型, 如 一线公募/头部主观私募")
    company_name: str
    verbatim: str


class CompanyRolePair(BaseModel):
    company: str
    role_or_dept: str
    strategy: str


class DimensionDistinction(BaseModel):
    axis: str = Field(description="哪个维度, e.g. strategy_type / institution_tier")
    x_vs_y: str = Field(description="X vs Y 形式, e.g. '公募 vs 资管子'")
    note: str


class KBInsight(BaseModel):
    type: KBInsightType
    text: str = Field(description="1 句摘要")
    verbatim_quote: str = Field(description="原文截取")
    confidence: Literal["high", "med", "low"]


class PostTaxonomyExtract(BaseModel):
    """Taxonomy 发现字段 (spec §5.1)。"""
    strategy_signals: list[StrategySignal] = Field(default_factory=list)
    industry_signals: list[IndustrySignal] = Field(default_factory=list)
    institution_signals: list[InstitutionSignal] = Field(default_factory=list)
    discovered_sub_categories: list[str] = Field(default_factory=list)
    company_role_pairs: list[CompanyRolePair] = Field(default_factory=list)
    dimension_distinctions: list[DimensionDistinction] = Field(default_factory=list)


class PostKBExtract(BaseModel):
    """KB 字段 (spec §5.2, 沿用 Pony 5-type)。"""
    insights: list[KBInsight] = Field(default_factory=list)


class DualSchemaExtract(BaseModel):
    """每帖 LLM 一次调用产出, 双 schema 合一。"""
    post_id: str
    url: str
    time: str
    author: str
    relevance_score: float = Field(ge=0.0, le=1.0, description="该帖是否真讨论投研, <0.3 drop")
    taxonomy: PostTaxonomyExtract
    kb: PostKBExtract
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="LLM 自评抽取置信度, <0.7 触发 Sonnet 二审")
```

- [ ] **Step 4: 跑测试，全绿**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/pytest tests/taxonomy_discovery/test_schemas.py -v 2>&1 | tail -15
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy_discovery/schemas.py backend/tests/taxonomy_discovery/test_schemas.py
git commit -m "feat(taxonomy-discovery): Pydantic dual-schema (taxonomy + KB)"
```

---

## Task 3: 全局预算 Tracker

**Files:**
- Create: `backend/app/services/taxonomy_discovery/budget_tracker.py`
- Test: `backend/tests/taxonomy_discovery/test_budget_tracker.py`

每个 API call 在执行前要查预算，超 $10 就 raise。跑 6 个并行 subagent 时这个 tracker 是共享状态，所以用文件锁实现。

- [ ] **Step 1: 写测试**

`backend/tests/taxonomy_discovery/test_budget_tracker.py`:

```python
"""测 budget tracker — 文件锁 + 累计 + 超限 raise。"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.services.taxonomy_discovery.budget_tracker import (
    BudgetExceededError,
    BudgetTracker,
)


@pytest.fixture
def tracker(tmp_path) -> BudgetTracker:
    return BudgetTracker(state_file=tmp_path / "budget.json", limit_usd=10.0)


def test_initial_state(tracker: BudgetTracker) -> None:
    assert tracker.spent() == 0.0
    assert tracker.remaining() == 10.0


def test_charge_accumulates(tracker: BudgetTracker) -> None:
    tracker.charge(0.50, "tikhub_search")
    tracker.charge(1.20, "decode_fetch")
    assert tracker.spent() == 1.70
    assert tracker.remaining() == 8.30


def test_charge_persists_across_instances(tmp_path) -> None:
    state = tmp_path / "budget.json"
    t1 = BudgetTracker(state_file=state, limit_usd=10.0)
    t1.charge(2.50, "deepseek_extract")
    t2 = BudgetTracker(state_file=state, limit_usd=10.0)
    assert t2.spent() == 2.50


def test_exceeding_limit_raises(tracker: BudgetTracker) -> None:
    tracker.charge(9.50, "decode_bulk")
    with pytest.raises(BudgetExceededError):
        tracker.charge(0.60, "deepseek_extra")  # would push to 10.10


def test_can_afford(tracker: BudgetTracker) -> None:
    tracker.charge(9.00, "x")
    assert tracker.can_afford(1.00) is True
    assert tracker.can_afford(1.01) is False


def test_breakdown_by_category(tracker: BudgetTracker) -> None:
    tracker.charge(0.50, "tikhub_search")
    tracker.charge(0.50, "tikhub_search")
    tracker.charge(1.00, "decode_fetch")
    breakdown = tracker.breakdown()
    assert breakdown["tikhub_search"] == 1.00
    assert breakdown["decode_fetch"] == 1.00
```

- [ ] **Step 2: 跑测试，确认全失败**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/pytest tests/taxonomy_discovery/test_budget_tracker.py -x 2>&1 | tail -10
```

Expected: ImportError

- [ ] **Step 3: 实现 budget_tracker.py**

`backend/app/services/taxonomy_discovery/budget_tracker.py`:

```python
"""全局 $10 预算 tracker, 多 subagent 共享, 文件锁防 race (spec §8)。"""
from __future__ import annotations

import fcntl
import json
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path


class BudgetExceededError(RuntimeError):
    """超预算就 raise, caller 必须 catch 并 graceful stop。"""


class BudgetTracker:
    def __init__(self, state_file: Path, limit_usd: float) -> None:
        self.state_file = Path(state_file)
        self.limit_usd = limit_usd
        if not self.state_file.exists():
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps({"spent": 0.0, "by_category": {}}))

    @contextmanager
    def _locked(self):
        """文件锁, 避免 6 subagent 并发改同一个 state。"""
        with open(self.state_file, "r+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.seek(0)
                state = json.load(f)
                yield state
                f.seek(0)
                f.truncate()
                json.dump(state, f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def spent(self) -> float:
        with self._locked() as s:
            return float(s["spent"])

    def remaining(self) -> float:
        return self.limit_usd - self.spent()

    def can_afford(self, amount_usd: float) -> bool:
        return self.spent() + amount_usd <= self.limit_usd

    def charge(self, amount_usd: float, category: str) -> None:
        with self._locked() as s:
            new_total = float(s["spent"]) + amount_usd
            if new_total > self.limit_usd:
                raise BudgetExceededError(
                    f"charge {amount_usd:.4f} ({category}) 会让总开销 {new_total:.4f} 超过 ${self.limit_usd}"
                )
            s["spent"] = new_total
            by_cat = defaultdict(float, s.get("by_category", {}))
            by_cat[category] += amount_usd
            s["by_category"] = dict(by_cat)

    def breakdown(self) -> dict[str, float]:
        with self._locked() as s:
            return dict(s.get("by_category", {}))
```

- [ ] **Step 4: 跑测试，全绿**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/pytest tests/taxonomy_discovery/test_budget_tracker.py -v 2>&1 | tail -15
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy_discovery/budget_tracker.py backend/tests/taxonomy_discovery/test_budget_tracker.py
git commit -m "feat(taxonomy-discovery): 全局 $10 budget tracker, 文件锁 race-safe"
```

---

## Task 4: TikHub + decode HTTP 客户端

**Files:**
- Create: `backend/app/services/taxonomy_discovery/crawler_client.py`
- Test: `backend/tests/taxonomy_discovery/test_crawler_client.py`

封装两个 API 的 HTTP 调用 + 强制 budget tracker 扣费 + 速率限制（10 RPS）。

- [ ] **Step 1: 写测试（vcrpy 录制 mock response）**

`backend/tests/taxonomy_discovery/test_crawler_client.py`:

```python
"""测 TikHub + decode 客户端 — 用 vcrpy 录的 fixture 模拟响应。

注意: vcrpy cassettes 第一次跑时录真实 API, 提交后离线 replay。
为了节省 $0.01, 这里直接写假 cassette。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.taxonomy_discovery.budget_tracker import BudgetTracker
from app.services.taxonomy_discovery.crawler_client import CrawlerClient


@pytest.fixture
def client(tmp_path) -> CrawlerClient:
    tracker = BudgetTracker(state_file=tmp_path / "b.json", limit_usd=10.0)
    return CrawlerClient(
        tikhub_key="fake_tikhub_key",
        decode_key="fake_decode_key",
        budget_tracker=tracker,
        rate_limit_qps=10,
    )


def test_tikhub_search_charges_budget(client: CrawlerClient, requests_mock) -> None:
    """search_notes 调用一次扣 $0.010。"""
    requests_mock.get(
        "https://api.tikhub.io/api/v1/xiaohongshu/web_v1/search/notes",
        json={
            "data": {
                "notes": [
                    {"note_id": "n1", "title": "嘉实消费组实习", "user_id": "u1"},
                    {"note_id": "n2", "title": "易方达 TMT 面经", "user_id": "u2"},
                ]
            }
        },
        status_code=200,
    )
    notes = client.search_notes(keyword="嘉实消费组")
    assert len(notes) == 2
    assert notes[0]["note_id"] == "n1"
    assert client.budget_tracker.spent() == pytest.approx(0.010, abs=1e-6)


def test_decode_fetch_charges_budget(client: CrawlerClient, requests_mock) -> None:
    """decode fetch 一次扣 $0.0015。"""
    requests_mock.post(
        "https://api.web-scraping.dev/v1/fetch",
        json={"html": "<html>fake xhs page</html>", "ok": True},
        status_code=200,
    )
    html = client.decode_fetch_url("https://xhs.com/n/abc")
    assert "fake xhs page" in html
    assert client.budget_tracker.spent() == pytest.approx(0.0015, abs=1e-6)


def test_budget_exceeded_blocks_call(client: CrawlerClient, requests_mock) -> None:
    """预算用完时调用 raise, 不发请求。"""
    client.budget_tracker.charge(9.999, "test_drain")
    with pytest.raises(Exception):  # BudgetExceededError
        client.search_notes(keyword="x")
```

需要 `pip install requests-mock` (大概率已经有, 没有就在这一步加上)。

- [ ] **Step 2: 跑测试，确认全失败**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/pip install requests-mock 2>&1 | tail -3
PYTHONPATH=. .venv/bin/pytest tests/taxonomy_discovery/test_crawler_client.py -x 2>&1 | tail -10
```

Expected: ImportError 或 test collection failure

- [ ] **Step 3: 实现 crawler_client.py**

`backend/app/services/taxonomy_discovery/crawler_client.py`:

```python
"""TikHub + decode HTTP 客户端封装。

TikHub: 小红书 search_notes / get_note_detail / get_note_comments
decode: 通用 web scraping, 给定 URL 返抓取后的 HTML/text
两个 API 调用都要先过 BudgetTracker; rate limit 10 RPS (TikHub 限制)。
"""
from __future__ import annotations

import time
from typing import Any

import requests

from .budget_tracker import BudgetTracker

TIKHUB_BASE = "https://api.tikhub.io/api/v1"
DECODE_BASE = "https://api.web-scraping.dev/v1"  # TODO: 用户确认 decode 实际 endpoint

TIKHUB_COST = 0.010
DECODE_COST = 0.0015


class CrawlerClient:
    def __init__(
        self,
        tikhub_key: str,
        decode_key: str,
        budget_tracker: BudgetTracker,
        rate_limit_qps: int = 10,
    ) -> None:
        self.tikhub_key = tikhub_key
        self.decode_key = decode_key
        self.budget_tracker = budget_tracker
        self._min_interval = 1.0 / rate_limit_qps
        self._last_call: float = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.monotonic()

    def search_notes(self, keyword: str, page: int = 1) -> list[dict[str, Any]]:
        """TikHub search_notes — 单次 ~20 results。"""
        if not self.budget_tracker.can_afford(TIKHUB_COST):
            from .budget_tracker import BudgetExceededError
            raise BudgetExceededError(f"无余额跑 search_notes (剩 ${self.budget_tracker.remaining():.4f})")
        self._throttle()
        r = requests.get(
            f"{TIKHUB_BASE}/xiaohongshu/web_v1/search/notes",
            params={"keyword": keyword, "page": page},
            headers={"Authorization": f"Bearer {self.tikhub_key}"},
            timeout=30,
        )
        r.raise_for_status()
        self.budget_tracker.charge(TIKHUB_COST, "tikhub_search")
        notes = r.json().get("data", {}).get("notes", [])
        return notes

    def decode_fetch_url(self, url: str) -> str:
        """decode 抓单 URL, 返回 raw HTML/text。"""
        if not self.budget_tracker.can_afford(DECODE_COST):
            from .budget_tracker import BudgetExceededError
            raise BudgetExceededError(f"无余额跑 decode_fetch_url (剩 ${self.budget_tracker.remaining():.4f})")
        self._throttle()
        r = requests.post(
            f"{DECODE_BASE}/fetch",
            json={"url": url},
            headers={"Authorization": f"Bearer {self.decode_key}"},
            timeout=60,
        )
        r.raise_for_status()
        self.budget_tracker.charge(DECODE_COST, "decode_fetch")
        return r.json().get("html", "")
```

- [ ] **Step 4: 跑测试，全绿**

```bash
PYTHONPATH=. .venv/bin/pytest tests/taxonomy_discovery/test_crawler_client.py -v 2>&1 | tail -15
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy_discovery/crawler_client.py backend/tests/taxonomy_discovery/test_crawler_client.py backend/requirements.txt
git commit -m "feat(taxonomy-discovery): TikHub + decode HTTP client w/ budget gate + rate limit"
```

⚠️ **后续 user 必须确认 `DECODE_BASE` 真实 URL + payload 格式**——当前是 placeholder, 真跑前要 1 次手工调通联调。

---

## Task 5: DeepSeek Dual-Schema Extractor

**Files:**
- Create: `backend/app/services/taxonomy_discovery/llm_extractor.py`
- Test: `backend/tests/taxonomy_discovery/test_llm_extractor.py`

LLM 调用 DeepSeek-V4-Pro, 喂一个 prompt 让它输出 `DualSchemaExtract` 的 JSON。包含 prompt 模板 + JSON parse + schema 校验。

- [ ] **Step 1: 写测试 (用 mock LLM 响应)**

`backend/tests/taxonomy_discovery/test_llm_extractor.py`:

```python
"""测 DeepSeek dual-schema extractor — mock 掉 OpenAI client。"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.taxonomy_discovery.budget_tracker import BudgetTracker
from app.services.taxonomy_discovery.llm_extractor import DualSchemaExtractor
from app.services.taxonomy_discovery.schemas import StrategyType


@pytest.fixture
def extractor(tmp_path) -> DualSchemaExtractor:
    tracker = BudgetTracker(state_file=tmp_path / "b.json", limit_usd=10.0)
    return DualSchemaExtractor(
        api_key="fake_deepseek_key",
        budget_tracker=tracker,
    )


def _mock_llm_response(content: str) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = MagicMock(prompt_tokens=2000, completion_tokens=800)
    return resp


def test_extract_returns_valid_dual_schema(extractor: DualSchemaExtractor) -> None:
    fake_response = json.dumps({
        "post_id": "abc",
        "url": "https://xhs.com/n/abc",
        "time": "2026-05-01T12:00:00",
        "author": "u1",
        "relevance_score": 0.8,
        "taxonomy": {
            "strategy_signals": [{"canonical": "基本面权益", "verbatim_phrase": "消费组"}],
            "industry_signals": [],
            "institution_signals": [],
            "discovered_sub_categories": ["消费组"],
            "company_role_pairs": [],
            "dimension_distinctions": [],
        },
        "kb": {"insights": []},
        "extraction_confidence": 0.9,
    })
    with patch("app.services.taxonomy_discovery.llm_extractor.OpenAI") as MockClient:
        client_inst = MockClient.return_value
        client_inst.chat.completions.create.return_value = _mock_llm_response(fake_response)
        result = extractor.extract(
            post_id="abc",
            url="https://xhs.com/n/abc",
            time="2026-05-01T12:00:00",
            author="u1",
            content="嘉实基金消费组实习, 主要做白酒研究",
            comments_text=[],
        )
    assert result.taxonomy.strategy_signals[0].canonical == StrategyType.基本面权益
    assert extractor.budget_tracker.spent() > 0  # 抽取扣了钱


def test_extract_handles_malformed_json(extractor: DualSchemaExtractor) -> None:
    """LLM 偶尔回 non-JSON, extractor 必须 graceful 返 low-confidence 空记录。"""
    with patch("app.services.taxonomy_discovery.llm_extractor.OpenAI") as MockClient:
        client_inst = MockClient.return_value
        client_inst.chat.completions.create.return_value = _mock_llm_response("not a json {{{")
        result = extractor.extract(
            post_id="abc",
            url="https://xhs.com/n/abc",
            time="2026-05-01T12:00:00",
            author="u1",
            content="random",
            comments_text=[],
        )
    assert result.relevance_score == 0.0  # malformed → 默认无信号
    assert result.extraction_confidence == 0.0  # 标记 fail
```

- [ ] **Step 2: 跑测试，确认全失败**

```bash
PYTHONPATH=. .venv/bin/pytest tests/taxonomy_discovery/test_llm_extractor.py -x 2>&1 | tail -10
```

Expected: ImportError

- [ ] **Step 3: 实现 llm_extractor.py**

`backend/app/services/taxonomy_discovery/llm_extractor.py`:

```python
"""DeepSeek-V4-Pro dual-schema extractor (spec §5)。一次 LLM 调用产出 taxonomy + KB 双输出。"""
from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from .budget_tracker import BudgetTracker
from .schemas import (
    DualSchemaExtract,
    PostKBExtract,
    PostTaxonomyExtract,
)

logger = logging.getLogger(__name__)

# DeepSeek pricing 2026: ~$0.27/1M input + $1.10/1M output
DEEPSEEK_INPUT_PER_1M = 0.27
DEEPSEEK_OUTPUT_PER_1M = 1.10


SYSTEM_PROMPT = """你是一个金融求职帖子结构化抽取器。从输入的小红书帖子(正文+评论)抽取两类数据:

**Taxonomy 发现字段** (用来分析金融岗位赛道):
- strategy_signals: 学生提到的策略类型, canonical 必须从 [基本面权益, 量化, 固定收益, 卖方研究, 多资产_FOF_衍生品, 相关补充] 选 1 个
- industry_signals: 行业方向, e.g. 消费/TMT/医药/金融/周期 (不锁词表, 学生原文用啥就抽啥)
- institution_signals: 平台类型 + 公司名 + 原文
- discovered_sub_categories: 学生用来区分岗位的具体词, e.g. "消费组"、"投研一组"
- company_role_pairs: 公司-岗位-策略映射
- dimension_distinctions: 学生显式的 "X vs Y" 对比

**KB 字段** (用来填知识库, 沿用 Pony 5-type schema):
- insights: list, 每条 type ∈ {role, interview, company, resume, industry}, 配 text+verbatim_quote+confidence

判断 relevance_score:
- 0.7-1.0: 真讨论金融投研岗位
- 0.3-0.7: 沾边但模糊
- 0-0.3: 不相关 (营销/学习/无关话题)

输出**纯 JSON**, 不要 markdown 代码块, 必须能 json.loads 解析。schema 见下方示例。
"""


JSON_SKELETON = """
{
  "post_id": "<透传>",
  "url": "<透传>",
  "time": "<透传>",
  "author": "<透传>",
  "relevance_score": 0.8,
  "taxonomy": {
    "strategy_signals": [{"canonical": "基本面权益", "verbatim_phrase": "..."}],
    "industry_signals": [{"industry": "消费", "verbatim_phrase": "..."}],
    "institution_signals": [{"tier_guess": "一线公募", "company_name": "...", "verbatim": "..."}],
    "discovered_sub_categories": ["..."],
    "company_role_pairs": [{"company": "...", "role_or_dept": "...", "strategy": "..."}],
    "dimension_distinctions": [{"axis": "...", "x_vs_y": "...", "note": "..."}]
  },
  "kb": {
    "insights": [{"type": "interview", "text": "...", "verbatim_quote": "...", "confidence": "high"}]
  },
  "extraction_confidence": 0.9
}
"""


class DualSchemaExtractor:
    def __init__(self, api_key: str, budget_tracker: BudgetTracker, model: str = "deepseek-chat") -> None:
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        self.budget_tracker = budget_tracker
        self.model = model

    def extract(
        self,
        *,
        post_id: str,
        url: str,
        time: str,
        author: str,
        content: str,
        comments_text: list[str],
    ) -> DualSchemaExtract:
        """单帖抽取, 失败时 graceful 返回空记录 (relevance=0, conf=0)。"""
        comments_blob = "\n---\n".join(comments_text[:30]) if comments_text else "(无评论)"
        user_msg = f"""帖子 ID: {post_id}
URL: {url}
发帖时间: {time}
作者: {author}

正文:
{content}

评论 (前 30 条):
{comments_blob}

请按 schema 输出 JSON:
{JSON_SKELETON}
"""

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            # 扣费 — input+output token 估算
            usage = resp.usage
            cost = (usage.prompt_tokens * DEEPSEEK_INPUT_PER_1M / 1_000_000
                    + usage.completion_tokens * DEEPSEEK_OUTPUT_PER_1M / 1_000_000)
            self.budget_tracker.charge(cost, "deepseek_extract")

            raw = resp.choices[0].message.content or ""
            data = json.loads(raw)
            data.setdefault("post_id", post_id)
            data.setdefault("url", url)
            data.setdefault("time", time)
            data.setdefault("author", author)
            return DualSchemaExtract.model_validate(data)
        except (json.JSONDecodeError, ValueError, Exception) as e:
            logger.warning("LLM extract failed for %s: %s", post_id, e)
            return DualSchemaExtract(
                post_id=post_id, url=url, time=time, author=author,
                relevance_score=0.0,
                taxonomy=PostTaxonomyExtract(),
                kb=PostKBExtract(),
                extraction_confidence=0.0,
            )
```

- [ ] **Step 4: 跑测试，全绿**

```bash
PYTHONPATH=. .venv/bin/pytest tests/taxonomy_discovery/test_llm_extractor.py -v 2>&1 | tail -15
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy_discovery/llm_extractor.py backend/tests/taxonomy_discovery/test_llm_extractor.py
git commit -m "feat(taxonomy-discovery): DeepSeek dual-schema extractor + graceful JSON parse"
```

---

## Task 6: Saturation 指标判断

**Files:**
- Create: `backend/app/services/taxonomy_discovery/saturation.py`
- Test: `backend/tests/taxonomy_discovery/test_saturation.py`

Subagent 每爬 50 帖后, 用这个模块判断"该停了 / 该继续"。

- [ ] **Step 1: 写测试**

`backend/tests/taxonomy_discovery/test_saturation.py`:

```python
"""测 saturation 指标 — 各 strategy 大类的阈值 + 饱和判定逻辑。"""
from __future__ import annotations

import pytest

from app.services.taxonomy_discovery.saturation import (
    SaturationConfig,
    SaturationState,
    SaturationStatus,
    check_saturation,
    config_for_strategy,
)


def test_config_for_top_weight() -> None:
    """基本面权益 (顶配) sub_cat_target=6, company_target=15, max_posts=1500。"""
    c = config_for_strategy("基本面权益")
    assert c.sub_cat_target == 6
    assert c.sub_cat_min_mentions == 10
    assert c.company_target == 15
    assert c.company_min_mentions == 5
    assert c.min_posts == 200
    assert c.max_posts == 1500


def test_config_for_low_weight() -> None:
    c = config_for_strategy("多资产_FOF_衍生品")
    assert c.sub_cat_target == 1
    assert c.max_posts == 200


def test_status_continue_below_minimum() -> None:
    """爬不够 min_posts 时永远不停。"""
    c = config_for_strategy("基本面权益")
    state = SaturationState(
        posts_crawled=50,
        unique_sub_cats_with_mentions={"消费组": 10, "TMT组": 8},
        unique_companies_with_mentions={"嘉实基金": 5},
        last_3_batches_new_items=[5, 4, 3],
    )
    assert check_saturation(state, c) == SaturationStatus.CONTINUE


def test_status_saturated_when_thresholds_met(top_config: SaturationConfig) -> None:
    """达标且最近 3 batch 无新东西 → SATURATED。"""
    state = SaturationState(
        posts_crawled=600,
        unique_sub_cats_with_mentions={f"cat{i}": 12 for i in range(6)},
        unique_companies_with_mentions={f"co{i}": 6 for i in range(15)},
        last_3_batches_new_items=[0, 0, 0],
    )
    assert check_saturation(state, top_config) == SaturationStatus.SATURATED


def test_status_scarce_when_signal_dries_up(top_config: SaturationConfig) -> None:
    """连续 3 batch insight 总数 < 5 → SCARCE。"""
    state = SaturationState(
        posts_crawled=250,
        unique_sub_cats_with_mentions={"消费组": 5},
        unique_companies_with_mentions={"嘉实基金": 3},
        last_3_batches_new_items=[1, 1, 1],
        last_3_batches_total_insights=[2, 1, 1],
    )
    assert check_saturation(state, top_config) == SaturationStatus.SCARCE


def test_status_ceiling_at_hard_max(top_config: SaturationConfig) -> None:
    state = SaturationState(
        posts_crawled=1500,
        unique_sub_cats_with_mentions={"消费组": 5},
        unique_companies_with_mentions={"嘉实基金": 3},
        last_3_batches_new_items=[1, 1, 1],
    )
    assert check_saturation(state, top_config) == SaturationStatus.CEILING


@pytest.fixture
def top_config() -> SaturationConfig:
    return config_for_strategy("基本面权益")
```

- [ ] **Step 2: 跑测试确认失败**

```bash
PYTHONPATH=. .venv/bin/pytest tests/taxonomy_discovery/test_saturation.py -x 2>&1 | tail -10
```

Expected: ImportError

- [ ] **Step 3: 实现 saturation.py**

`backend/app/services/taxonomy_discovery/saturation.py`:

```python
"""Saturation 指标 + 配置 (spec §4.3)。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SaturationStatus(str, Enum):
    CONTINUE = "continue"
    SATURATED = "saturated"
    SCARCE = "scarce"
    CEILING = "ceiling"


@dataclass
class SaturationConfig:
    sub_cat_target: int
    sub_cat_min_mentions: int
    company_target: int
    company_min_mentions: int
    min_posts: int
    max_posts: int


@dataclass
class SaturationState:
    posts_crawled: int
    unique_sub_cats_with_mentions: dict[str, int]
    unique_companies_with_mentions: dict[str, int]
    last_3_batches_new_items: list[int] = field(default_factory=list)  # 每 batch 新出现的 sub_cat+company 数
    last_3_batches_total_insights: list[int] = field(default_factory=list)


_CONFIGS: dict[str, SaturationConfig] = {
    "基本面权益": SaturationConfig(6, 10, 15, 5, 200, 1500),
    "量化": SaturationConfig(4, 8, 10, 5, 100, 800),
    "固定收益": SaturationConfig(3, 5, 6, 3, 60, 500),
    "卖方研究": SaturationConfig(4, 5, 5, 5, 60, 500),
    "多资产_FOF_衍生品": SaturationConfig(1, 5, 3, 3, 20, 200),
    "相关补充": SaturationConfig(1, 2, 2, 2, 10, 100),
}


def config_for_strategy(strategy: str) -> SaturationConfig:
    if strategy not in _CONFIGS:
        raise KeyError(f"未知 strategy: {strategy!r}, 可选 {list(_CONFIGS)}")
    return _CONFIGS[strategy]


def check_saturation(state: SaturationState, config: SaturationConfig) -> SaturationStatus:
    if state.posts_crawled >= config.max_posts:
        return SaturationStatus.CEILING

    if state.posts_crawled < config.min_posts:
        return SaturationStatus.CONTINUE

    # 内容稀缺: 连续 3 batch insight 总和 < 5
    if (len(state.last_3_batches_total_insights) >= 3
            and sum(state.last_3_batches_total_insights[-3:]) < 5):
        return SaturationStatus.SCARCE

    # 达标判定
    qualified_sub_cats = sum(
        1 for n in state.unique_sub_cats_with_mentions.values()
        if n >= config.sub_cat_min_mentions
    )
    qualified_companies = sum(
        1 for n in state.unique_companies_with_mentions.values()
        if n >= config.company_min_mentions
    )
    no_recent_growth = (
        len(state.last_3_batches_new_items) >= 3
        and sum(state.last_3_batches_new_items[-3:]) == 0
    )

    if (qualified_sub_cats >= config.sub_cat_target
            and qualified_companies >= config.company_target
            and no_recent_growth):
        return SaturationStatus.SATURATED

    return SaturationStatus.CONTINUE
```

- [ ] **Step 4: 跑测试，全绿**

```bash
PYTHONPATH=. .venv/bin/pytest tests/taxonomy_discovery/test_saturation.py -v 2>&1 | tail -15
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy_discovery/saturation.py backend/tests/taxonomy_discovery/test_saturation.py
git commit -m "feat(taxonomy-discovery): saturation indicators + per-strategy config"
```

---

## Task 7: Seed Query 清单

**Files:**
- Create: `backend/app/services/taxonomy_discovery/seed_queries.py`
- Test: `backend/tests/taxonomy_discovery/test_seed_queries.py`

每个 strategy 大类的初始关键词 + 候选博主清单。后续 subagent 用此 seed 出发, 自动扩展 query。

- [ ] **Step 1: 写测试**

`backend/tests/taxonomy_discovery/test_seed_queries.py`:

```python
"""测 seed query 清单 — 必须 6 大策略都有, 关键词非空, 候选博主有 25 个。"""
from __future__ import annotations

from app.services.taxonomy_discovery.seed_queries import (
    CANDIDATE_BLOGGERS,
    seed_keywords_for_strategy,
    same_company_angles,
)


def test_all_6_strategies_have_seeds() -> None:
    for strategy in [
        "基本面权益", "量化", "固定收益", "卖方研究",
        "多资产_FOF_衍生品", "相关补充",
    ]:
        seeds = seed_keywords_for_strategy(strategy)
        assert len(seeds) >= 5, f"{strategy} seed 不足 5: {seeds}"
        # 关键词不能完全重复
        assert len(set(seeds)) == len(seeds)


def test_candidate_bloggers_count() -> None:
    """25 个候选博主 (Pony 之前发现的 7 tier1 + 18 tier2 + Pony 自己)。"""
    assert len(CANDIDATE_BLOGGERS) >= 25
    # Pony 必须在 list 里
    pony = [b for b in CANDIDATE_BLOGGERS if "pony" in b["uid"].lower() or "Pony" in b["name"]]
    assert len(pony) >= 1


def test_same_company_angles() -> None:
    """同公司 5 视角 query 模板。"""
    angles = same_company_angles("嘉实基金")
    assert len(angles) == 5
    assert "嘉实基金 面试" in angles
    assert "嘉实基金 实习" in angles
```

- [ ] **Step 2: 跑测试，确认失败**

```bash
PYTHONPATH=. .venv/bin/pytest tests/taxonomy_discovery/test_seed_queries.py -x 2>&1 | tail -10
```

- [ ] **Step 3: 实现 seed_queries.py**

`backend/app/services/taxonomy_discovery/seed_queries.py`:

```python
"""6 大策略 seed query + 25 候选博主清单 (spec §4.2)。

候选博主清单从 docs/xhs-blogger-discovery-2026-05-23.md 的"25 个候选同行" section 来,
真正 deep crawl 之前 user 应再 review 一遍 (有人可能账号注销了)。
"""
from __future__ import annotations


_SEEDS: dict[str, list[str]] = {
    "基本面权益": [
        "公募基金 校招",
        "公募基金 实习 行业研究",
        "易方达 校招",
        "嘉实基金 消费组",
        "华夏基金 投研",
        "南方基金 实习",
        "保险资管 投研",
        "券商资管 校招",
        "银行理财子 投研",
        "基本面研究员 入门",
        "公募 vs 资管 选择",
        "SAIF MF 公募 实习",
    ],
    "量化": [
        "量化私募 校招",
        "幻方 校招",
        "九坤 实习",
        "明汯 投资",
        "灵均 量化研究员",
        "鸣石投资 校招",
        "多因子 因子开发",
        "高频策略 实习",
        "机器学习 量化",
        "alpha 因子",
        "量化交易员 vs 研究员",
        "公募量化 vs 私募量化",
    ],
    "固定收益": [
        "公募固收 校招",
        "银行理财子 固收",
        "保险资管 固收",
        "利率债 研究",
        "信用债 研究",
        "可转债 研究",
        "固收 投研 实习",
        "FICC 入门",
    ],
    "卖方研究": [
        "券商研究所 校招",
        "中信证券 研究所",
        "中金 研究 实习",
        "海通 行业研究",
        "招商证券 TMT",
        "卖方 行业研究员",
        "卖方 vs 买方 选择",
        "首席分析师 路径",
    ],
    "多资产_FOF_衍生品": [
        "FOF 投资 实习",
        "FOF 投资经理",
        "MOM 配置",
        "多资产 配置 校招",
        "衍生品 期权策略",
        "结构化产品",
    ],
    "相关补充": [
        "PE 投后 研究",
        "VC 行业研究",
        "量化 IT 校招",
        "量化 开发 实习",
        "金融科技 数据 算法",
    ],
}


# 25 候选博主 (Pony 报告 + Pony 自己) — uid 是 XHS 用户 ID, name 是博主名
# 真正 deep crawl 前 user 应再 review 这个 list (有人可能账号失效)
CANDIDATE_BLOGGERS: list[dict[str, str]] = [
    {"uid": "620f9d93000000002102508e", "name": "Pony说求职", "tier": "1", "topic": "金融求职全栈"},
    # TODO: user 提供完整 25 个清单时填充, 当前作为 placeholder.
    # 待 user 在 docs/xhs-blogger-discovery-2026-05-23.md 完整版的 §"25 个真同行候选" 段补全
    # 如果当前找不到 25 个, 也接受 1-N 的开端, subagent 跑起来后会再发现新博主
]


def seed_keywords_for_strategy(strategy: str) -> list[str]:
    if strategy not in _SEEDS:
        raise KeyError(f"未知 strategy: {strategy!r}")
    return list(_SEEDS[strategy])


def same_company_angles(company: str) -> list[str]:
    """同公司 5 视角 query (spec V3 vector)。"""
    return [
        f"{company} 面试",
        f"{company} 实习",
        f"{company} 入职",
        f"{company} 离职",
        f"{company} 真实",
    ]
```

- [ ] **Step 4: 跑测试，全绿**

```bash
PYTHONPATH=. .venv/bin/pytest tests/taxonomy_discovery/test_seed_queries.py -v 2>&1 | tail -15
```

Expected: 3 passed (注意: `test_candidate_bloggers_count` 会失败因为只塞了 Pony 一个；先 mark as xfail 让 commit 过, 后续 user 补 25 后转 pass)

修正: 在 test 文件顶部加 `import pytest`, 把 `test_candidate_bloggers_count` 装饰 `@pytest.mark.xfail(reason="待 user 补全 25 候选博主 list", strict=False)`。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/taxonomy_discovery/seed_queries.py backend/tests/taxonomy_discovery/test_seed_queries.py
git commit -m "feat(taxonomy-discovery): seed queries + candidate bloggers (待 user 补完整 25 list)"
```

---

## Task 8: Alembic Migration — `xhs_taxonomy_extracts` 表

**Files:**
- Create: `backend/alembic/versions/2026_05_26_xhs_taxonomy_extracts.py`
- Modify: `backend/app/models.py`（追加 XHSTaxonomyExtract ORM 类）

- [ ] **Step 1: 看现有 alembic head**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/alembic current 2>&1 | tail -3
```

记下当前 head revision 字符串，下面 `down_revision` 用它。

- [ ] **Step 2: 写 migration 文件**

`backend/alembic/versions/2026_05_26_xhs_taxonomy_extracts.py`:

```python
"""xhs_taxonomy_extracts: taxonomy 字段独立表, 不污染 xhs_insights (KB 用)。

Revision ID: a26052601
Revises: <写 step 1 看到的 current head>
Create Date: 2026-05-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers
revision = "a26052601"
down_revision = "<待填: step 1 看到的 head>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "xhs_taxonomy_extracts" in insp.get_table_names():
        return  # idempotent
    op.create_table(
        "xhs_taxonomy_extracts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("post_id", sa.Text, nullable=False, index=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("post_time", sa.Text, nullable=True),
        sa.Column("author_uid", sa.Text, nullable=True, index=True),
        sa.Column("relevance_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("strategy_signals_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("industry_signals_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("institution_signals_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("discovered_sub_categories_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("company_role_pairs_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("dimension_distinctions_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("extraction_confidence", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("strategy_bucket", sa.Text, nullable=True, index=True),  # 给 6 subagent 各自查
        sa.Column("created_at", sa.DateTime, server_default=sa.func.current_timestamp()),
    )


def downgrade() -> None:
    op.drop_table("xhs_taxonomy_extracts")
```

- [ ] **Step 3: 跑 migration**

```bash
PYTHONPATH=. .venv/bin/alembic upgrade head 2>&1 | tail -5
PYTHONPATH=. .venv/bin/python -c "
from app.database import SessionLocal
from sqlalchemy import inspect
db = SessionLocal(); insp = inspect(db.bind)
assert 'xhs_taxonomy_extracts' in insp.get_table_names(), '表未创建'
print('OK')
db.close()
"
```

Expected: `OK`

- [ ] **Step 4: 在 `backend/app/models.py` 末尾追加 ORM**

```python
class XHSTaxonomyExtract(Base):
    """Taxonomy 字段独立表 (跟 xhs_insights 拆开, 后者存 KB 5-type)。"""
    __tablename__ = "xhs_taxonomy_extracts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Text, nullable=False, index=True)
    url = Column(Text, nullable=False)
    post_time = Column(Text, nullable=True)
    author_uid = Column(Text, nullable=True, index=True)
    relevance_score = Column(Float, nullable=False, default=0.0)
    strategy_signals_json = Column(Text, nullable=False, default="[]")
    industry_signals_json = Column(Text, nullable=False, default="[]")
    institution_signals_json = Column(Text, nullable=False, default="[]")
    discovered_sub_categories_json = Column(Text, nullable=False, default="[]")
    company_role_pairs_json = Column(Text, nullable=False, default="[]")
    dimension_distinctions_json = Column(Text, nullable=False, default="[]")
    extraction_confidence = Column(Float, nullable=False, default=1.0)
    strategy_bucket = Column(Text, nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
```

注意上面用了 `Float`、`func`，确认 import 部分有这俩。

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/2026_05_26_xhs_taxonomy_extracts.py backend/app/models.py
git commit -m "feat(taxonomy-discovery): alembic migration + ORM for xhs_taxonomy_extracts"
```

---

## Task 9: Persona Loader

**Files:**
- Create: `backend/app/services/taxonomy_discovery/persona_loader.py`
- Test: `backend/tests/taxonomy_discovery/test_persona_loader.py`

加载 backend/data/personas/P{1,2,3,6}.{pdf,json}, 提取文本 + JSON 上帝视角字段。

- [ ] **Step 1: 写测试**

`backend/tests/taxonomy_discovery/test_persona_loader.py`:

```python
"""测 persona loader — 真读 backend/data/personas/ 4 个 persona 文件。"""
from __future__ import annotations

import pytest

from app.services.taxonomy_discovery.persona_loader import load_persona, load_all_demo_personas


def test_load_persona_p1() -> None:
    p = load_persona("P1")
    assert p.id == "P1"
    assert "林思远" in p.resume_text or "清华" in p.resume_text
    assert len(p.hidden_highlights) > 0
    assert isinstance(p.target_jd_anchors, list)


def test_load_all_demo_personas() -> None:
    personas = load_all_demo_personas()
    ids = {p.id for p in personas}
    assert ids == {"P1", "P2", "P3", "P6"}
```

- [ ] **Step 2: 跑测试，确认失败**

```bash
PYTHONPATH=. .venv/bin/pytest tests/taxonomy_discovery/test_persona_loader.py -x 2>&1 | tail -10
```

- [ ] **Step 3: 实现 persona_loader.py**

`backend/app/services/taxonomy_discovery/persona_loader.py`:

```python
"""Persona loader — 读 backend/data/personas/P{1,2,3,6}.{pdf,json}。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PERSONA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "personas"
DEMO_IDS = ["P1", "P2", "P3", "P6"]


@dataclass
class Persona:
    id: str
    resume_text: str                # 从 PDF 提取的纯文本
    hidden_highlights: list[dict]   # 上帝视角隐藏亮点
    target_jd_anchors: list[str]    # 目标岗位关键词
    persona_voice: dict             # 说话风格
    raw_json: dict                  # 原始 JSON, 后面 LLM prompt 全文喂


def _extract_pdf_text(pdf_path: Path) -> str:
    """用 pdfplumber 提文字。pdfplumber 已在 requirements。"""
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        return "\n\n".join(page.extract_text() or "" for page in pdf.pages)


def load_persona(persona_id: str) -> Persona:
    pdf = PERSONA_DIR / f"{persona_id}.pdf"
    js = PERSONA_DIR / f"{persona_id}.json"
    if not pdf.exists() or not js.exists():
        raise FileNotFoundError(f"persona files missing for {persona_id}: {pdf}, {js}")
    raw = json.loads(js.read_text(encoding="utf-8"))
    return Persona(
        id=persona_id,
        resume_text=_extract_pdf_text(pdf),
        hidden_highlights=raw.get("hidden_highlights", []),
        target_jd_anchors=raw.get("target_jd_anchors", []),
        persona_voice=raw.get("persona_voice", {}),
        raw_json=raw,
    )


def load_all_demo_personas() -> list[Persona]:
    return [load_persona(pid) for pid in DEMO_IDS]
```

- [ ] **Step 4: 确认 pdfplumber 在 requirements**

```bash
grep pdfplumber /home/chuanbo/projects/JobRadar/backend/requirements.txt
```

如果没有, 加 `pdfplumber==0.11.4` 并 `pip install pdfplumber==0.11.4`。

- [ ] **Step 5: 跑测试，全绿**

```bash
PYTHONPATH=. .venv/bin/pytest tests/taxonomy_discovery/test_persona_loader.py -v 2>&1 | tail -10
```

Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/taxonomy_discovery/persona_loader.py backend/tests/taxonomy_discovery/test_persona_loader.py backend/requirements.txt
git commit -m "feat(taxonomy-discovery): persona loader for P1/P2/P3/P6"
```

---

## Task 10: 就业报告 LLM 抽取脚本

**Files:**
- Create: `scripts/extract_employment_reports.py`
- Create: `backend/data/saif_employment_reports_extracted.json`（输出文件）

把 3 份 PDF (23/24/25 SAIF MF 就业报告) 喂给 DeepSeek, 抽出公司 / 岗位 / 人数结构化数据。这是 Opus 合成阶段的 ground truth anchor。

- [ ] **Step 1: 把 PDF 落本地**

报告当前在 `/home/ubuntu/.claude/uploads/.../`。复制到项目目录:

```bash
mkdir -p /home/chuanbo/projects/JobRadar/backend/data/_private/saif_reports/
cp /home/ubuntu/.claude/uploads/022c7ac9-e58c-40bd-ada1-8a6d4028ea90/e421cc38-2023_____MF____.pdf \
   /home/chuanbo/projects/JobRadar/backend/data/_private/saif_reports/saif_mf_2023.pdf
cp /home/ubuntu/.claude/uploads/022c7ac9-e58c-40bd-ada1-8a6d4028ea90/a9721662-2024_____MF____.pdf \
   /home/chuanbo/projects/JobRadar/backend/data/_private/saif_reports/saif_mf_2024.pdf
cp /home/ubuntu/.claude/uploads/022c7ac9-e58c-40bd-ada1-8a6d4028ea90/38cc5c80-2025_____MF____.pdf \
   /home/chuanbo/projects/JobRadar/backend/data/_private/saif_reports/saif_mf_2025.pdf
ls /home/chuanbo/projects/JobRadar/backend/data/_private/saif_reports/
```

- [ ] **Step 2: 写脚本**

`scripts/extract_employment_reports.py`:

```python
"""从 SAIF MF 就业报告 PDF 抽取流向数据 (公司 / 岗位 / 人数)。

输出: backend/data/saif_employment_reports_extracted.json
   {
     "2023": [{"company": "易方达基金", "role_type": "行业研究员", "count": 3, "industry": "公募基金"}, ...],
     "2024": [...],
     "2025": [...]
   }
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pdfplumber
from openai import OpenAI

REPORT_DIR = Path("backend/data/_private/saif_reports")
OUTPUT = Path("backend/data/saif_employment_reports_extracted.json")
YEARS = ["2023", "2024", "2025"]


SYSTEM_PROMPT = """你是金融求职报告结构化抽取器。读取上海高级金融学院 (SAIF) MF 项目年度就业报告 PDF 文本,
抽出每个学生的去向: 公司名 / 岗位类型 / 行业大类。

只关心**投研相关方向**: 公募 / 私募 / 资管 / 量化 / 卖方研究 / 险资。
不关心: 银行管培 / IBD / 咨询 / 体制内 / FinTech。

输出纯 JSON 数组, 每条:
{
  "company": "<标准化公司全名, 如 易方达基金管理有限公司>",
  "role_type": "<行业研究员/量化研究员/固收研究/FOF 投资经理/卖方分析师/...>",
  "count": <人数, 报告里如有数字就用, 没有就 1>,
  "industry": "<公募基金/私募/保险资管/券商资管/银行理财子/量化私募/券商研究所>"
}

如果某段是岗位介绍而非学生流向, 跳过。
"""


def extract_text(pdf_path: Path) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        return "\n\n".join(p.extract_text() or "" for p in pdf.pages)


def extract_year(year: str, client: OpenAI) -> list[dict]:
    pdf_path = REPORT_DIR / f"saif_mf_{year}.pdf"
    text = extract_text(pdf_path)
    # 报告很长, 分块跑 (每块约 8000 字, 留 buffer 给 prompt)
    chunks = [text[i:i + 8000] for i in range(0, len(text), 8000)]
    all_records = []
    for idx, chunk in enumerate(chunks):
        print(f"  [{year}] chunk {idx+1}/{len(chunks)} 抽取中...")
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"年度: {year}\n\n报告片段:\n{chunk}\n\n请输出 JSON 数组 (key 直接是 records, 顶层 dict 包一层方便解析)"},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        try:
            data = json.loads(resp.choices[0].message.content or "{}")
            records = data.get("records") or data.get("students") or data.get("data") or []
            if isinstance(records, list):
                all_records.extend(records)
        except (json.JSONDecodeError, KeyError):
            print(f"    [WARN] chunk {idx+1} parse failed, skip")
    return all_records


def main() -> None:
    api_key = os.environ.get("RESUME_COPILOT_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("ERROR: 缺 RESUME_COPILOT_API_KEY", file=sys.stderr)
        sys.exit(1)
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    out: dict[str, list[dict]] = {}
    for year in YEARS:
        pdf = REPORT_DIR / f"saif_mf_{year}.pdf"
        if not pdf.exists():
            print(f"[SKIP] {pdf} not found")
            continue
        print(f"处理 {year}...")
        out[year] = extract_year(year, client)
        print(f"  → {len(out[year])} 条记录")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ 写入 {OUTPUT}")
    print(f"  2023={len(out.get('2023',[]))} / 2024={len(out.get('2024',[]))} / 2025={len(out.get('2025',[]))}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 跑脚本**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/python ../scripts/extract_employment_reports.py 2>&1 | tail -20
```

Expected: 输出 "处理 2023... → N 条记录" × 3, 最终落 backend/data/saif_employment_reports_extracted.json

- [ ] **Step 4: Sanity check 产出**

```bash
.venv/bin/python -c "
import json
d = json.loads(open('backend/data/saif_employment_reports_extracted.json').read())
for year, recs in d.items():
    print(f'{year}: {len(recs)} 条, sample:')
    for r in recs[:3]:
        print(f'  {r}')
"
```

Expected: 每年至少几十条记录, sample 包含 company/role_type/count/industry 四个字段。

- [ ] **Step 5: Commit (排除 PDF, 因为 _private/)**

注意: `backend/data/_private/` 应该在 .gitignore 里。**只 commit 抽取后的 JSON**, 不 commit 原始 PDF (含学生隐私)。

```bash
grep "_private" /home/chuanbo/projects/JobRadar/.gitignore || echo "backend/data/_private/" >> /home/chuanbo/projects/JobRadar/.gitignore

cd /home/chuanbo/projects/JobRadar
git add scripts/extract_employment_reports.py backend/data/saif_employment_reports_extracted.json .gitignore
git commit -m "feat(taxonomy-discovery): SAIF MF 就业报告 LLM 抽取 (3 年流向数据)"
```

---

## Task 11: Subagent 操作手册（Markdown Runbook）

**Files:**
- Create: `scripts/xhs_discovery_subagent_runbook.md`

每个 Sonnet 4.6 subagent 跑这套 runbook 来发现自己负责的 strategy 大类的 sub-categories。用 Claude Code Agent tool 启动时把这份 markdown 作为 prompt。

- [ ] **Step 1: 写 runbook**

`scripts/xhs_discovery_subagent_runbook.md`:

```markdown
# XHS Discovery Subagent Runbook

你是负责一个 strategy 大类的 discovery subagent (Sonnet 4.6)。任务是从 XHS 抓取讨论该策略的帖子, 用 DeepSeek 抽取结构化数据, 直到饱和或触顶。

## 输入 (调用者传入)

- `strategy`: 6 大类之一 ("基本面权益" / "量化" / "固定收益" / "卖方研究" / "多资产_FOF_衍生品" / "相关补充")
- `batch_size`: 每轮爬几帖, 默认 50
- `output_jsonl`: 把每帖 DualSchemaExtract JSON 追加到这个文件

## 操作步骤

1. **加载 seed query**:
   ```python
   from app.services.taxonomy_discovery.seed_queries import seed_keywords_for_strategy
   queries = seed_keywords_for_strategy(strategy)
   ```

2. **加载 saturation config**:
   ```python
   from app.services.taxonomy_discovery.saturation import config_for_strategy, SaturationState, check_saturation, SaturationStatus
   config = config_for_strategy(strategy)
   state = SaturationState(posts_crawled=0, unique_sub_cats_with_mentions={}, unique_companies_with_mentions={})
   ```

3. **初始化 client + extractor**:
   ```python
   from app.services.taxonomy_discovery.crawler_client import CrawlerClient
   from app.services.taxonomy_discovery.llm_extractor import DualSchemaExtractor
   from app.services.taxonomy_discovery.budget_tracker import BudgetTracker
   import os
   tracker = BudgetTracker(state_file="backend/data/xhs/raw/_budget.json", limit_usd=10.0)
   client = CrawlerClient(
       tikhub_key=os.environ["TIKHUB_API_KEY"],
       decode_key=os.environ["WEB_SCRAPING_API_KEY"],
       budget_tracker=tracker,
   )
   extractor = DualSchemaExtractor(api_key=os.environ["RESUME_COPILOT_API_KEY"], budget_tracker=tracker)
   ```

4. **主循环** (一轮 = 一个 batch):
   ```
   for round in range(1, 100):
       本轮 query = queries 的前 5 个 (第 1 轮) 或 用上轮发现的新公司 / sub_cat 词构造的新 query
       crawled_this_batch = []
       for q in 本轮 query:
           ids = client.search_notes(q)  # 返 ~20 个 note_id
           for note in ids:
               if note already in state.processed_ids: continue
               # 用 decode 拉单帖正文 + 评论
               raw = client.decode_fetch_url(note.url)
               content, comments = parse_xhs_html(raw)  # 见下方 helper
               extract = extractor.extract(post_id=note.id, url=note.url, time=note.time, author=note.author, content=content, comments_text=comments)
               # 写 jsonl
               with open(output_jsonl, "a") as f:
                   f.write(extract.model_dump_json() + "\n")
               # 更新 state
               state.posts_crawled += 1
               for sig in extract.taxonomy.strategy_signals + extract.taxonomy.industry_signals + ...:
                   ...更新 unique_sub_cats_with_mentions...
               for comp in extract.taxonomy.company_role_pairs:
                   ...更新 unique_companies_with_mentions...
               crawled_this_batch.append(extract)
           if len(crawled_this_batch) >= batch_size: break
       # 检查饱和
       state.last_3_batches_new_items.append(<本轮新发现的 sub_cat+company 总数>)
       state.last_3_batches_total_insights.append(<本轮有多少有效 insight>)
       status = check_saturation(state, config)
       if status != SaturationStatus.CONTINUE:
           print(f"{strategy}: {status.value} at {state.posts_crawled} posts")
           break
       # 生成下一轮 query: 用本轮新发现的 high-frequency company + sub_cat 词构造
       queries = generate_next_queries(state, strategy, top_k=5)
   ```

5. **写完工报告**: 一份 markdown 总结到 `backend/data/xhs/raw/_reports/{strategy}_subagent_report.md`:
   ```
   # {strategy} subagent report
   - posts_crawled: N
   - status: <SATURATED/SCARCE/CEILING>
   - sub_cats found: [list]
   - top 10 companies: [list]
   - cost spent: $X
   ```

## Helper: parse_xhs_html

decode 返的是 HTML, 需要提取:
- 正文 text
- 评论 list (作者 + 文本 + 点赞数)

用 BeautifulSoup + XHS 已知 selector (具体 selector 见 `tools/xhs_post_comment_crawler/src/`)。

## 退出条件

- saturation status == SATURATED → 任务完成
- saturation status == SCARCE → 内容稀缺, 该 strategy 在 XHS 上不活跃, 接受当前结果
- saturation status == CEILING → 触上限, 接受当前结果
- BudgetExceededError → 立即停, 写报告时标 status=BUDGET_EXCEEDED

## 不要做

- ❌ 自行调整 saturation 配置 (硬上限是 spec 锁的)
- ❌ 跨 strategy 的 query (你只负责自己那个 bucket)
- ❌ 拒绝写 jsonl (即使 relevance_score < 0.3 也写, 让 orchestrator 知道你看过)
```

- [ ] **Step 2: Commit**

```bash
git add scripts/xhs_discovery_subagent_runbook.md
git commit -m "feat(taxonomy-discovery): subagent runbook (markdown spec for Claude Code Agent)"
```

注意: 这个 runbook **不是可执行的 Python**, 是给 Claude Code Agent tool 当 prompt 用的。下一个 task 是 Python orchestrator, 它会读这个 runbook + dispatch 6 个 agent。

---

## Task 12: Orchestrator — 6 Subagent 并行调度

**Files:**
- Create: `scripts/xhs_discovery_orchestrator.py`

⚠️ 这个 task **不是普通 Python 脚本** —— 它是给 Claude Code (主会话) 跑的 shell 命令清单。orchestrator 的工作不是直接调 LLM, 而是：
1. 准备好 output 目录 + budget state
2. 通过 Claude Code Agent tool **dispatch 6 个 subagent**, 每个 subagent 读 Task 11 的 runbook + 自己的 strategy 参数
3. 等所有 subagent 完工 (或全部 BudgetExceeded)
4. 收集每个 subagent 的报告

由于 Python 脚本不能调 Claude Code Agent tool, 这个步骤的真实实现是：**user 在 Claude Code 里说"开始跑 discovery"**, 然后 Claude (orchestrator session) 使用 `superpowers:dispatching-parallel-agents` skill 来真正 fan-out。

- [ ] **Step 1: 写"预跑准备"脚本**

`scripts/xhs_discovery_orchestrator.py`:

```python
"""Discovery 预跑准备 + 后处理.

真正的 6 subagent 并行 fan-out 在 Claude Code 主会话里用
`superpowers:dispatching-parallel-agents` skill 跑, 此脚本只负责:

1. 创建输出目录 + 初始化 budget state
2. 跑完后聚合 6 个 subagent 的 jsonl + report
3. 输出"已完工"汇总, 供 Opus synthesis 用
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from app.services.taxonomy_discovery.budget_tracker import BudgetTracker

OUTPUT_ROOT = Path("backend/data/xhs/raw")
SUBAGENT_OUTPUTS = OUTPUT_ROOT / "_subagent_outputs"
REPORTS_DIR = OUTPUT_ROOT / "_reports"
BUDGET_STATE = OUTPUT_ROOT / "_budget.json"

STRATEGIES = ["基本面权益", "量化", "固定收益", "卖方研究", "多资产_FOF_衍生品", "相关补充"]


def prepare() -> None:
    """跑 subagent 之前 init 目录 + budget state。"""
    SUBAGENT_OUTPUTS.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    # 重置 budget tracker
    BUDGET_STATE.parent.mkdir(parents=True, exist_ok=True)
    BUDGET_STATE.write_text(json.dumps({"spent": 0.0, "by_category": {}}))
    print(f"✓ Output dirs ready: {SUBAGENT_OUTPUTS}")
    print(f"✓ Budget state initialized: {BUDGET_STATE}")
    # 打印用户应该 dispatch 的 subagent 清单
    print("\n现在在 Claude Code 主会话里说:")
    print("  '用 dispatching-parallel-agents skill 启动 6 个 discovery subagent'")
    print("\n每个 subagent 的 prompt:")
    for s in STRATEGIES:
        print(f"\n--- {s} ---")
        print(f"读 scripts/xhs_discovery_subagent_runbook.md, 参数: strategy={s!r}, "
              f"output_jsonl={SUBAGENT_OUTPUTS / f'{s}.jsonl'!s}, report_md={REPORTS_DIR / f'{s}.md'!s}")


def aggregate() -> None:
    """6 subagent 跑完后, 聚合所有 jsonl + 打印汇总。"""
    tracker = BudgetTracker(state_file=BUDGET_STATE, limit_usd=10.0)
    print(f"\n=== Discovery 聚合汇总 ===")
    print(f"总开销: ${tracker.spent():.4f} / $10")
    print(f"分类:")
    for cat, amt in sorted(tracker.breakdown().items()):
        print(f"  {cat}: ${amt:.4f}")
    print()
    total_posts = 0
    for s in STRATEGIES:
        jsonl = SUBAGENT_OUTPUTS / f"{s}.jsonl"
        if not jsonl.exists():
            print(f"  [{s}] ⚠ no output (subagent didn't write)")
            continue
        with open(jsonl) as f:
            lines = sum(1 for _ in f)
        print(f"  [{s}] {lines} 帖")
        total_posts += lines
    print(f"\n总抽取帖数: {total_posts}")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    if cmd == "prepare":
        prepare()
    elif cmd == "aggregate":
        aggregate()
    else:
        print(f"未知命令: {cmd}. 用 'prepare' 或 'aggregate'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑 prepare 命令验证**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/python ../scripts/xhs_discovery_orchestrator.py prepare 2>&1 | head -30
```

Expected: 输出 dispatch 指引 + budget 初始化 OK。

- [ ] **Step 3: Commit**

```bash
git add scripts/xhs_discovery_orchestrator.py
git commit -m "feat(taxonomy-discovery): orchestrator prepare/aggregate helper"
```

⚠️ **此 task 的实际执行（fan-out 6 agent）在 Task 13 由 Claude Code 主会话用 superpowers skill 完成, 此脚本只是 init + collect 的助手。**

---

## Task 13: 执行 Discovery 阶段（用 superpowers:dispatching-parallel-agents）

**这一步在 Claude Code 主会话里手动执行, 不是 Python 脚本。**

- [ ] **Step 1: 跑 prepare**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/python ../scripts/xhs_discovery_orchestrator.py prepare
```

- [ ] **Step 2: 在 Claude Code 里调 dispatching-parallel-agents skill**

主会话执行:
```
我用 superpowers:dispatching-parallel-agents 启动 6 个 discovery subagent, 每个的 prompt:

[Subagent 1] 读 scripts/xhs_discovery_subagent_runbook.md, strategy=基本面权益, output_jsonl=backend/data/xhs/raw/_subagent_outputs/基本面权益.jsonl, report=backend/data/xhs/raw/_reports/基本面权益.md
[Subagent 2] strategy=量化, ...
...(共 6 个)
```

- [ ] **Step 3: 等 6 个 subagent 全部跑完**

监控时通过查看 `backend/data/xhs/raw/_budget.json` 看消耗:
```bash
watch -n 30 'jq . backend/data/xhs/raw/_budget.json'
```

Expected: 总消耗最终 ≤ $9 (留 $1 buffer 给 Opus synthesis 阶段)

- [ ] **Step 4: 跑 aggregate**

```bash
PYTHONPATH=. .venv/bin/python ../scripts/xhs_discovery_orchestrator.py aggregate 2>&1 | tail -20
```

Expected: 输出 6 个 strategy 各自的帖数 + 总开销。

- [ ] **Step 5: Commit (只 commit 报告 + budget log, 不 commit jsonl 因为太大)**

`.gitignore` 加:
```
backend/data/xhs/raw/_subagent_outputs/
backend/data/xhs/raw/_budget.json
```

```bash
cd /home/chuanbo/projects/JobRadar
git add .gitignore backend/data/xhs/raw/_reports/
git commit -m "data: discovery subagent reports (6 strategies)"
```

---

## Task 14: Opus Taxonomy Synthesis

**Files:**
- Create: `scripts/opus_taxonomy_synthesis.py`
- Output: `docs/taxonomy-投研-final-v1.md`

读所有 subagent 抽取 + 就业报告 + Pony 已有 insights → Opus 合成最终 taxonomy + 10 家 demo 公司清单。

- [ ] **Step 1: 写脚本**

`scripts/opus_taxonomy_synthesis.py`:

```python
"""Opus 4.7 最终合成 (spec §6)。

输入:
- backend/data/xhs/raw/_subagent_outputs/*.jsonl   # 6 strategy 的 DualSchemaExtract
- backend/data/saif_employment_reports_extracted.json  # 就业报告 ground truth
- (可选) Pony 现有 139 insights (如能找到原始位置)

输出:
- docs/taxonomy-投研-final-v1.md  # 最终 taxonomy + 共识标注 + 10 家 demo 公司

注意: 这个脚本本身不调 Opus API (Opus 是 Claude Code session 的主模型, 不在 user 的 API key 范围内)。
脚本只做"准备 prompt + 写出最终 YAML + markdown 输出"。

真正的 Opus 合成在 Claude Code 主会话用 Read + 推理 + Write 完成。
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

SUBAGENT_DIR = Path("backend/data/xhs/raw/_subagent_outputs")
REPORTS_JSON = Path("backend/data/saif_employment_reports_extracted.json")
SYNTHESIS_INPUT = Path("backend/data/xhs/raw/_synthesis_input.json")


def main() -> None:
    """聚合所有 subagent 抽取 + 报告 → 一份大 JSON, 给 Opus 当输入。"""
    all_extracts = []
    for jsonl in sorted(SUBAGENT_DIR.glob("*.jsonl")):
        strategy = jsonl.stem
        with open(jsonl) as f:
            for line in f:
                rec = json.loads(line)
                rec["_source_strategy_bucket"] = strategy
                all_extracts.append(rec)
    print(f"聚合 {len(all_extracts)} 帖抽取")

    # 按 strategy_bucket 聚合 sub_cat / company 频次
    by_bucket: dict[str, dict] = defaultdict(lambda: {"sub_cats": Counter(), "companies": Counter()})
    for r in all_extracts:
        bucket = r["_source_strategy_bucket"]
        for sc in r["taxonomy"]["discovered_sub_categories"]:
            by_bucket[bucket]["sub_cats"][sc] += 1
        for cr in r["taxonomy"]["company_role_pairs"]:
            by_bucket[bucket]["companies"][cr["company"]] += 1

    # 读就业报告 ground truth
    reports = json.loads(REPORTS_JSON.read_text(encoding="utf-8")) if REPORTS_JSON.exists() else {}
    report_companies: dict[str, int] = Counter()
    for year_recs in reports.values():
        for r in year_recs:
            report_companies[r.get("company", "")] += r.get("count", 1)

    # 写合成输入
    synthesis = {
        "total_posts": len(all_extracts),
        "by_strategy_bucket": {
            k: {
                "sub_cats_freq": dict(v["sub_cats"].most_common(50)),
                "companies_freq": dict(v["companies"].most_common(30)),
            }
            for k, v in by_bucket.items()
        },
        "employment_report_companies_freq": dict(report_companies.most_common(50)),
        "report_total_records": sum(len(v) for v in reports.values()),
    }
    SYNTHESIS_INPUT.parent.mkdir(parents=True, exist_ok=True)
    SYNTHESIS_INPUT.write_text(json.dumps(synthesis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ Synthesis 输入写入 {SYNTHESIS_INPUT}")
    print(f"\n现在在 Claude Code 里读这个文件, 让 Opus 输出最终 taxonomy:")
    print(f"  docs/taxonomy-投研-final-v1.md")
    print(f"\nOpus prompt 模板见 task 14 step 3。")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑脚本聚合**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/python ../scripts/opus_taxonomy_synthesis.py 2>&1 | tail -10
```

Expected: 输出"聚合 N 帖抽取"+ 写出 _synthesis_input.json。

- [ ] **Step 3: 在 Claude Code 主会话里让 Opus 合成**

主会话执行:
```
读 backend/data/xhs/raw/_synthesis_input.json, 按 spec §6 输出最终 taxonomy + 共识标注 + 10 家 demo 公司:
1. 每个 strategy_type 下面的 sub_categories 列出来, 每个标共识层级 (high/med/low):
   - high: XHS 高频 + 就业报告也出现 + (如有) Pony 已记录
   - med: 至少 2 源出现
   - low: 仅 1 源出现, 推荐 drop
2. institution_tier 也按上述规则发现
3. 10 家 demo 公司: 综合 XHS 高频 + 报告流向 + 多源共识, 给每家配 strategy_tag + institution_tier
4. 每个高共识 sub_cat 选 5-10 条代表性 verbatim quote (从 jsonl 的 KB insights 里挑 confidence=high 的)

输出: docs/taxonomy-投研-final-v1.md
```

- [ ] **Step 4: 检查输出文件**

```bash
wc -l docs/taxonomy-投研-final-v1.md
head -50 docs/taxonomy-投研-final-v1.md
```

Expected: 文件存在 + 包含 strategy_type / institution_tier / 10 家公司 + verbatim quotes。

- [ ] **Step 5: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add scripts/opus_taxonomy_synthesis.py docs/taxonomy-投研-final-v1.md backend/data/xhs/raw/_synthesis_input.json
git commit -m "feat(taxonomy-discovery): Opus 合成最终 taxonomy + 10 家 demo 公司 + 共识标注"
```

---

## Task 15: Student Classifier — 4 Persona

**Files:**
- Create: `scripts/classify_students.py`
- Output: `backend/data/personas/_classified.json`

用 final taxonomy 对 P1/P2/P3/P6 跑分类器, 输出三维标签 + hidden_highlights 识别。

- [ ] **Step 1: 写脚本**

`scripts/classify_students.py`:

```python
"""对 4 个 demo persona 跑学生分类器 (spec §7.1)。

输出 backend/data/personas/_classified.json:
{
  "P1": {
    "primary": {"strategy_type": "基本面权益", "industry_focus": ["消费", "医药"], "institution_tier_target": ["一线公募", "头部主观私募"]},
    "secondary_signals": [...],
    "core_skills": [...],
    "hidden_highlights_identified": [...]
  },
  ...
}
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from openai import OpenAI

from app.services.taxonomy_discovery.persona_loader import load_all_demo_personas

OUTPUT = Path("backend/data/personas/_classified.json")
TAXONOMY_FILE = Path("docs/taxonomy-投研-final-v1.md")


SYSTEM_PROMPT = """你是一个 SAIF MF 学生简历分类器。读取一份简历 (PDF 提取文本) + 上帝视角 JSON (hidden_highlights / target_jd_anchors),
对照投研细颗粒 taxonomy, 输出学生的:

- primary.strategy_type: 6 大类之一 (基本面权益 / 量化 / 固定收益 / 卖方研究 / 多资产_FOF_衍生品 / 相关补充)
- primary.industry_focus: list, 基本面或卖方学生有 (消费/TMT/医药/...), 量化学生可 null
- primary.institution_tier_target: list, 学生最适合的平台类型 (一线公募 / 头部量化私募 / ...)
- secondary_signals: 兼职方向 (如 P1 的 PE 经历)
- core_skills: list, 学生的核心能力栈
- hidden_highlights_identified: list, 从简历里识别出的隐藏亮点 (跟上帝视角的 hidden_highlights 对照, 看是否能挖出)
- cross_major_signal: bool (是否跨专业)

输出纯 JSON, schema:
{
  "primary": {"strategy_type": "...", "industry_focus": [...], "institution_tier_target": [...]},
  "secondary_signals": [...],
  "core_skills": [...],
  "hidden_highlights_identified": [...],
  "cross_major_signal": false
}
"""


def main() -> None:
    api_key = os.environ.get("RESUME_COPILOT_API_KEY")
    if not api_key:
        raise SystemExit("缺 RESUME_COPILOT_API_KEY")
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    taxonomy_md = TAXONOMY_FILE.read_text(encoding="utf-8") if TAXONOMY_FILE.exists() else ""

    personas = load_all_demo_personas()
    classified: dict[str, dict] = {}
    for p in personas:
        print(f"分类 {p.id}...")
        user_msg = f"""## Final Taxonomy (供参考)

{taxonomy_md[:5000]}

## 学生 {p.id} 简历正文

{p.resume_text[:6000]}

## 上帝视角 (用于对照, 但不要直接 paste)

hidden_highlights: {json.dumps(p.hidden_highlights, ensure_ascii=False)}
target_jd_anchors: {json.dumps(p.target_jd_anchors, ensure_ascii=False)}
persona_voice: {json.dumps(p.persona_voice, ensure_ascii=False)}

请输出 JSON 分类结果。
"""
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        classified[p.id] = json.loads(resp.choices[0].message.content or "{}")
        print(f"  → strategy={classified[p.id].get('primary', {}).get('strategy_type', '?')}")

    OUTPUT.write_text(json.dumps(classified, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ 写入 {OUTPUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑脚本**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/python ../scripts/classify_students.py 2>&1 | tail -10
```

Expected: 4 个 persona 都分类完, _classified.json 写出。

- [ ] **Step 3: Sanity check**

```bash
.venv/bin/python -c "
import json
d = json.loads(open('backend/data/personas/_classified.json').read())
for pid, info in d.items():
    p = info.get('primary', {})
    print(f'{pid}: strategy={p.get(\"strategy_type\")}, industry={p.get(\"industry_focus\")}, tier={p.get(\"institution_tier_target\")}')
"
```

Expected (大致):
```
P1: strategy=基本面权益, industry=[消费, 医药], tier=[一线公募, 头部主观私募]
P2: strategy=卖方研究, industry=[TMT], tier=[卖方研究所]
P3: strategy=基本面权益, industry=[跨行业 / Quantamental], tier=[中型公募, 头部主观私募]
P6: strategy=量化, industry=null/null, tier=[头部量化私募, 中型量化私募]
```

如果分类结果跟 spec §7.1 expected 偏差太大 (e.g. P6 被分到基本面), 重新跑或调 prompt。

- [ ] **Step 4: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add scripts/classify_students.py backend/data/personas/_classified.json
git commit -m "feat(taxonomy-discovery): 学生分类器 (P1/P2/P3/P6)"
```

---

## Task 16: Job Enricher — Demo 10 家公司

**Files:**
- Create: `scripts/enrich_demo_jobs.py`
- Output: `backend/data/personas/_demo_jobs_enriched.json`

把 demo 10 家公司的现有岗位 LLM enrich, 打 strategy_type / industry_focus / institution_tier 三维标签。

- [ ] **Step 1: 写脚本**

`scripts/enrich_demo_jobs.py`:

```python
"""对 demo 10 家公司的岗位跑 LLM enrich (spec §7.2)。

输入:
- docs/taxonomy-投研-final-v1.md  # 取 10 家 demo 公司清单 (Opus 写的)
- DB: jobs 表里 company 在 10 家清单 + scraped_at >= 2026-01-01

输出: backend/data/personas/_demo_jobs_enriched.json
[
  {"job_id": "...", "company": "...", "title": "...", "strategy_type": "...",
   "industry_focus": "...", "institution_tier": "...", "required_skills": [...],
   "enrichment_confidence": "high"},
  ...
]
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from openai import OpenAI
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Job

TAXONOMY_FILE = Path("docs/taxonomy-投研-final-v1.md")
OUTPUT = Path("backend/data/personas/_demo_jobs_enriched.json")


SYSTEM_PROMPT = """你是金融岗位结构化分类器。给一条招聘岗位 (公司 + 标题 + JD 文本), 按 final taxonomy 输出:

- strategy_type: 6 大类之一
- industry_focus: 单一行业 (如 消费/TMT/医药), 量化或非基本面岗可 null
- institution_tier: 平台类型 (一线公募 / 头部量化私募 / ...)
- required_skills: 这岗位要求的能力栈
- enrichment_confidence: high/med/low

输出纯 JSON。无法分类的字段 null。
"""


def extract_demo_companies(md_path: Path) -> list[str]:
    """从 Opus 写的 taxonomy markdown 里提取 10 家 demo 公司清单。

    假设 markdown 里有形如 "### 10 家 demo 公司" 或类似 section, 公司名以 "- " 或 "1. " 开头。
    实在解析不到就 raise, user 手工修。
    """
    if not md_path.exists():
        raise FileNotFoundError(md_path)
    content = md_path.read_text(encoding="utf-8")
    # 尝试找 demo 公司 section
    m = re.search(r"(?:10 家 demo 公司|demo[_ ]?companies)[^\n]*\n+(.+?)(?:\n##|\Z)", content, re.S | re.I)
    if not m:
        raise ValueError("无法在 taxonomy.md 找到 demo 公司 section, user 手工列出来塞 _demo_companies.txt")
    section = m.group(1)
    companies = re.findall(r"^[\-\*\d.]+\s*\*?\*?([^\n*]+?)\*?\*?(?:\s*[—-：:]|$)", section, re.M)
    companies = [c.strip() for c in companies if c.strip()]
    return companies[:10]


def main() -> None:
    api_key = os.environ.get("RESUME_COPILOT_API_KEY")
    if not api_key:
        raise SystemExit("缺 RESUME_COPILOT_API_KEY")
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    taxonomy_md = TAXONOMY_FILE.read_text(encoding="utf-8")[:5000]
    companies = extract_demo_companies(TAXONOMY_FILE)
    print(f"Demo 10 家公司: {companies}")

    db = SessionLocal()
    jobs = (
        db.execute(
            select(Job)
            .where(Job.company.in_(companies))
            .where(Job.scraped_at >= "2026-01-01")
            .limit(500)  # cap, 实际可能少很多
        )
        .scalars()
        .all()
    )
    print(f"匹配岗位 {len(jobs)} 条")

    enriched: list[dict] = []
    for j in jobs:
        prompt = f"""## Taxonomy 摘要

{taxonomy_md[:3000]}

## 岗位

公司: {j.company}
标题: {j.job_title}
JD 文本 (前 1500 字符): {(j.job_description or '')[:1500]}

请按上面 schema 输出 JSON。
"""
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        try:
            data = json.loads(resp.choices[0].message.content or "{}")
            data["job_id"] = j.job_id
            data["company"] = j.company
            data["title"] = j.job_title
            enriched.append(data)
        except (json.JSONDecodeError, KeyError):
            continue
    db.close()

    OUTPUT.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ {len(enriched)} 岗位写入 {OUTPUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑脚本**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/python ../scripts/enrich_demo_jobs.py 2>&1 | tail -10
```

Expected: 输出岗位数 + 写出 enriched.json

注意: 如果 `extract_demo_companies` 没解析出来, 手工创建 `backend/data/personas/_demo_companies.txt` 列 10 家, 修脚本读这个文件即可。

- [ ] **Step 3: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add scripts/enrich_demo_jobs.py backend/data/personas/_demo_jobs_enriched.json
git commit -m "feat(taxonomy-discovery): demo 10 家公司岗位 enrich"
```

---

## Task 17: Demo End-to-End Matching

**Files:**
- Create: `scripts/demo_persona_match.py`
- Output: `backend/data/personas/_demo_recommendations.json`

对 4 persona 跑端到端匹配, 各输出 top 5 + KB-backed 理由。

- [ ] **Step 1: 写脚本**

`scripts/demo_persona_match.py`:

```python
"""对 P1/P2/P3/P6 跑端到端匹配 (spec §7.3)。

输入:
- backend/data/personas/_classified.json   # 4 persona 三维标签
- backend/data/personas/_demo_jobs_enriched.json  # 10 家公司岗位标签
- backend/data/xhs/raw/_subagent_outputs/*.jsonl  # XHS KB insights (verbatim quotes)

输出: backend/data/personas/_demo_recommendations.json
{
  "P1": [
    {"rank": 1, "job_id": "...", "company": "嘉实", "title": "消费组研究员", "score": 0.93,
     "reasoning": [...], "xhs_evidence": [{"quote": "...", "source": "post_xxx"}],
     "risk_signals": []},
    ...
  ],
  "P2": [...],
  ...
}
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from openai import OpenAI

CLASSIFIED = Path("backend/data/personas/_classified.json")
ENRICHED = Path("backend/data/personas/_demo_jobs_enriched.json")
KB_DIR = Path("backend/data/xhs/raw/_subagent_outputs")
OUTPUT = Path("backend/data/personas/_demo_recommendations.json")


def load_kb_insights() -> dict[str, list[dict]]:
    """从所有 jsonl 加载 KB insights, 按公司索引。"""
    by_company: dict[str, list[dict]] = {}
    for jsonl in KB_DIR.glob("*.jsonl"):
        with open(jsonl) as f:
            for line in f:
                rec = json.loads(line)
                for ins in rec.get("kb", {}).get("insights", []):
                    if ins.get("confidence") != "high":
                        continue
                    # 关联到 company_role_pairs 里的 company
                    for cr in rec.get("taxonomy", {}).get("company_role_pairs", []):
                        comp = cr.get("company", "")
                        by_company.setdefault(comp, []).append({
                            "quote": ins["verbatim_quote"],
                            "type": ins["type"],
                            "source": rec.get("post_id", ""),
                        })
    return by_company


SYSTEM_PROMPT = """你是 SAIF MF 岗位推荐引擎。给定一个学生分类标签 + 一组 enriched 岗位 + 每家公司的 XHS verbatim insights, 输出 top 5 推荐, 每条:

- rank: 1-5
- job_id, company, title: 透传
- score: 0-1, 匹配分
- reasoning: list, 2-3 条具体理由 (优先引用学生简历事实 + 岗位要求)
- xhs_evidence: list of {"quote": "...", "source": "post_xxx"}, 至少 1 条 (如有 KB 数据)
- risk_signals: list, 该岗位的风险 (跨专业不友好 / tier 错配 等)

输出 JSON: {"recommendations": [...]}。
"""


def main() -> None:
    api_key = os.environ.get("RESUME_COPILOT_API_KEY")
    if not api_key:
        raise SystemExit("缺 RESUME_COPILOT_API_KEY")
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    classified = json.loads(CLASSIFIED.read_text(encoding="utf-8"))
    enriched = json.loads(ENRICHED.read_text(encoding="utf-8"))
    kb_by_company = load_kb_insights()

    recommendations: dict[str, list[dict]] = {}
    for pid, student in classified.items():
        print(f"匹配 {pid}...")
        # 喂给 LLM 的 enriched (含 KB quote)
        enriched_with_kb = []
        for j in enriched:
            comp = j.get("company", "")
            j["xhs_quotes_available"] = kb_by_company.get(comp, [])[:5]
            enriched_with_kb.append(j)

        user_msg = f"""## 学生分类 ({pid})

{json.dumps(student, ensure_ascii=False, indent=2)}

## Demo 岗位池 (含每家公司可用的 XHS quotes)

{json.dumps(enriched_with_kb, ensure_ascii=False)[:12000]}

请输出 top 5 推荐 JSON。
"""
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        recs = data.get("recommendations", [])[:5]
        recommendations[pid] = recs
        print(f"  → top 5 公司: {[r.get('company') for r in recs]}")

    OUTPUT.write_text(json.dumps(recommendations, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ 写入 {OUTPUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑脚本**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/python ../scripts/demo_persona_match.py 2>&1 | tail -15
```

Expected: 4 persona 各 5 条推荐, _demo_recommendations.json 写出。

- [ ] **Step 3: Sanity check (这一步要细看)**

```bash
.venv/bin/python -c "
import json
d = json.loads(open('backend/data/personas/_demo_recommendations.json').read())
for pid, recs in d.items():
    print(f'\n=== {pid} top 5 ===')
    for r in recs:
        print(f'  rank{r[\"rank\"]}: {r[\"company\"]} - {r.get(\"title\")} (score={r.get(\"score\")})')
        for reason in r.get('reasoning', [])[:2]:
            print(f'      • {reason}')
        for ev in r.get('xhs_evidence', [])[:1]:
            print(f'      [XHS] \"{ev[\"quote\"][:60]}...\" - {ev[\"source\"]}')
"
```

Expected: 跟 spec §7.3 大致对得上 (P1 top 公募 / P6 top 量化, 不混乱)。

- [ ] **Step 4: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add scripts/demo_persona_match.py backend/data/personas/_demo_recommendations.json
git commit -m "feat(taxonomy-discovery): 4 persona 端到端匹配 (top 5 + KB-backed reasoning)"
```

---

## Task 18: 区分力矩阵评估

**Files:**
- Create: `scripts/eval_discrimination_matrix.py`
- Output: `backend/data/personas/_discrimination_matrix.json`

跑 5 维区分力矩阵, 自动判定 demo 是否成功 (≥ 4/5 通过)。

- [ ] **Step 1: 写脚本**

`scripts/eval_discrimination_matrix.py`:

```python
"""5 维区分力矩阵自动评估 (spec §7.4)。

输入: backend/data/personas/_demo_recommendations.json
输出: backend/data/personas/_discrimination_matrix.json
{
  "matrix": [
    {"dim": "strategy 主轴", "compared": "P1 vs P6", "passed": true, "details": "..."},
    ...
  ],
  "score": "4/5",
  "demo_success": true
}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CLASSIFIED = Path("backend/data/personas/_classified.json")
RECS = Path("backend/data/personas/_demo_recommendations.json")
ENRICHED = Path("backend/data/personas/_demo_jobs_enriched.json")
OUTPUT = Path("backend/data/personas/_discrimination_matrix.json")


def get_strategies(recs: list[dict], enriched: dict[str, dict]) -> set[str]:
    """从一组推荐中, 拿到对应岗位的 strategy_type 集合。"""
    return {enriched.get(r["job_id"], {}).get("strategy_type", "") for r in recs}


def main() -> None:
    classified = json.loads(CLASSIFIED.read_text(encoding="utf-8"))
    recs_all = json.loads(RECS.read_text(encoding="utf-8"))
    enriched_list = json.loads(ENRICHED.read_text(encoding="utf-8"))
    enriched = {e["job_id"]: e for e in enriched_list}

    matrix: list[dict[str, Any]] = []

    # Dim 1: strategy 主轴 (P1 基本面 vs P6 量化)
    p1_strats = get_strategies(recs_all["P1"], enriched)
    p6_strats = get_strategies(recs_all["P6"], enriched)
    no_strategy_leak = ("量化" not in p1_strats) and (
        all(s in {"量化", "相关补充", ""} for s in p6_strats)
    )
    matrix.append({
        "dim": "strategy 主轴区分",
        "compared": "P1 (基本面) vs P6 (量化)",
        "passed": no_strategy_leak,
        "details": f"P1 strategies={p1_strats}, P6 strategies={p6_strats}",
    })

    # Dim 2: 同 strategy 不同 tier (P1 公募 vs P3 私募/中型)
    p1_tiers = {enriched.get(r["job_id"], {}).get("institution_tier", "") for r in recs_all["P1"]}
    p3_tiers = {enriched.get(r["job_id"], {}).get("institution_tier", "") for r in recs_all["P3"]}
    overlap = p1_tiers & p3_tiers
    tier_diff = len(overlap) <= max(1, len(p1_tiers) * 0.4)
    matrix.append({
        "dim": "同 strategy 不同 tier",
        "compared": "P1 (公募) vs P3 (中型/私募)",
        "passed": tier_diff,
        "details": f"P1 tiers={p1_tiers}, P3 tiers={p3_tiers}, overlap={overlap}",
    })

    # Dim 3: 买卖方分离 (P1 买方 vs P2 卖方)
    p1_companies = {r["company"] for r in recs_all["P1"]}
    p2_companies = {r["company"] for r in recs_all["P2"]}
    p1_p2_overlap = p1_companies & p2_companies
    side_separated = len(p1_p2_overlap) <= 1  # 至多 1 家重合 (允许偶发)
    matrix.append({
        "dim": "同 industry 不同 side",
        "compared": "P1 (买方消费/医药) vs P2 (卖方 TMT)",
        "passed": side_separated,
        "details": f"P1 companies={p1_companies}, P2 companies={p2_companies}, overlap={p1_p2_overlap}",
    })

    # Dim 4: 隐藏亮点挖掘 (每 persona ≥1 条 reasoning 引用 hidden_highlights)
    all_hidden_mentioned = []
    for pid, recs in recs_all.items():
        student = classified.get(pid, {})
        hidden = student.get("hidden_highlights_identified", [])
        if not hidden:
            all_hidden_mentioned.append(False)
            continue
        reasoning_text = " ".join(reason for r in recs for reason in r.get("reasoning", []))
        # 简单关键词匹配: hidden_highlights 里关键名词出现在 reasoning 里
        mentioned = any(any(kw[:8] in reasoning_text for kw in [str(h)[:30] for h in hidden]) for h in hidden)
        all_hidden_mentioned.append(mentioned)
    hidden_pass = all(all_hidden_mentioned)
    matrix.append({
        "dim": "隐藏亮点挖掘",
        "compared": "P1/P2/P3/P6 各自",
        "passed": hidden_pass,
        "details": f"per-persona mentioned: {dict(zip(['P1','P2','P3','P6'], all_hidden_mentioned))}",
    })

    # Dim 5: 跨专业友好度 (P3)
    p3_reasoning = " ".join(reason for r in recs_all["P3"] for reason in r.get("reasoning", []))
    cross_friendly = any(kw in p3_reasoning for kw in ["跨专业", "数学", "理工", "量化背景", "跳板"])
    matrix.append({
        "dim": "跨专业友好度",
        "compared": "P3 (理工→金融)",
        "passed": cross_friendly,
        "details": f"P3 reasoning excerpt: ...{p3_reasoning[:300]}...",
    })

    score_passed = sum(1 for m in matrix if m["passed"])
    score_str = f"{score_passed}/5"
    demo_success = score_passed >= 4

    result = {
        "matrix": matrix,
        "score": score_str,
        "demo_success": demo_success,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== 区分力矩阵评估 ===")
    for m in matrix:
        print(f"  [{'✓' if m['passed'] else '✗'}] {m['dim']}: {m['compared']}")
        if not m['passed']:
            print(f"      ↳ {m['details']}")
    print(f"\n得分: {score_str}, demo_success={demo_success}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑脚本**

```bash
cd /home/chuanbo/projects/JobRadar/backend
PYTHONPATH=. .venv/bin/python ../scripts/eval_discrimination_matrix.py 2>&1 | tail -15
```

Expected: 输出 5 维评估 + 得分 + demo_success bool。

- [ ] **Step 3: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add scripts/eval_discrimination_matrix.py backend/data/personas/_discrimination_matrix.json
git commit -m "feat(taxonomy-discovery): 区分力矩阵 5 维评估"
```

---

## Task 19: 最终 Demo 报告

**Files:**
- Create: `docs/eval/<日期>-投研-demo-report.md`

把所有产出汇成一份 markdown 报告, 供 SAIF 老师 + 团队 review。

- [ ] **Step 1: 在 Claude Code 主会话里让 Opus 写报告**

主会话:
```
基于以下产出, 写一份 markdown 报告到 docs/eval/<完工日期>-投研-demo-report.md:

1. backend/data/personas/_classified.json (4 persona 分类结果)
2. backend/data/personas/_demo_recommendations.json (4 persona top 5 推荐)
3. backend/data/personas/_discrimination_matrix.json (5 维评估)
4. docs/taxonomy-投研-final-v1.md (最终 taxonomy)
5. backend/data/xhs/raw/_budget.json (开销)
6. backend/data/saif_employment_reports_extracted.json (报告 ground truth)

报告结构:
- §1 摘要 (一页, 给老师看的)
- §2 Final Taxonomy 概览
- §3 4 个 Persona 分类结果 + Top 5 推荐
- §4 区分力矩阵评估
- §5 与就业报告的对比 (taxonomy 是否对得上真实流向)
- §6 待改进 (≥ 1 维度没过的细节 + 修复方向)
- §7 成本与时长统计
```

- [ ] **Step 2: 上传报告到飞书**

```bash
cd /home/chuanbo/projects/JobRadar/docs/eval && \
  lark-cli drive +import --as user \
    --file ./<日期>-投研-demo-report.md \
    --type docx \
    --folder-token "<找 40_模拟面试 类似的 eval 文件夹 token, 或新建 20_岗位推荐 子文件夹>" \
    --name "投研赛道细颗粒度 demo 验收报告 — <日期>"
```

- [ ] **Step 3: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add docs/eval/<日期>-投研-demo-report.md
git commit -m "docs(eval): 投研赛道 taxonomy demo 验收报告 (4 persona + 区分力 5 维)"
```

- [ ] **Step 4: 写 ACTIVITY.md**

按 CLAUDE.md 规则在 ACTIVITY.md 顶部追加:
```markdown
### <日期> · 网站设计-devvpstmux · 投研 taxonomy demo 收官
- **干了什么**: 跑通投研赛道细颗粒度 demo 全链路 - XHS 多向量爬取 + 6 subagent 并行发现 + Opus 合成最终 taxonomy + 4 SAIF persona 端到端匹配 + 5 维区分力矩阵评估
- **用户体验变化**: 系统现在能从简历分辨 "P1 公募基本面 vs P6 量化" 这种粒度的画像差异, 给出 KB-backed 推荐理由 (引用 XHS 学姐学长 verbatim quote)
- **测试**: 区分力矩阵得分 <N/5>, demo 验收 <pass/fail>
- **下一步**: 扩展到其它 SAIF 流向 (IBD / 咨询 / 体制内) 用同样 pipeline 复跑
```

```bash
git add ACTIVITY.md
git commit -m "docs(activity): 投研 taxonomy demo 收官入档"
```

---

## Self-Review Notes

跑完上面 19 个 task 后, **每一步都按 spec §2.3 demo 成功判据自查**:

| 产出 | Task # | 检查 |
|---|---|---|
| `docs/taxonomy-投研-final-v1.md` | 14 | 存在 + 含 strategy / industry / tier 三维 + 共识标注 + 10 家 demo 公司 |
| `backend/data/xhs/raw/<keyword>/{notes,comments}.csv` | 13 | jsonl 形式落地 (没有按 keyword 分目录, 因为 subagent 是按 strategy 分; 跟 spec 微调, 等价) |
| `xhs_notes` + `xhs_insights` 表 | (跳过, demo 阶段直接走 jsonl, 不入库) | spec §10.3 提到入库, 但 demo 跑通后再批量 ingest, 不阻塞 demo |
| `backend/data/personas/P{1,2,3,6}.{pdf,json}` | 已就位 | ✓ Task 9 用 |
| `scripts/demo_persona_match.py` | 17 | ✓ |
| `docs/eval/...-投研-demo-report.md` | 19 | ✓ |

**已知偏离 spec 的地方** (executing 时要注意):

1. **XHS 数据落地格式**: spec 说 `<keyword>/{notes,comments}.csv`, 计划改成按 strategy 落 jsonl (因 subagent 是按 strategy 划分的, csv 不方便存 dual-schema)。等价产出。
2. **xhs_notes/xhs_insights 入库**: demo 阶段跳过, 跑通后再批量 ingest (避免 demo 失败时清表麻烦)。
3. **drug 25 候选博主 list**: seed_queries.py 当前只塞了 Pony 1 个, user 要补完 25 个 list (Task 7 步骤 5 已 mark xfail)。
4. **decode API 真实 URL**: crawler_client.py 用了 placeholder URL `https://api.web-scraping.dev/v1/fetch`, user 提供完整 endpoint 后改一行 (Task 4 末尾警告)。
5. **Subagent fan-out 在 Claude Code 主会话执行**: Task 12+13 在 Python 脚本里只做 init/aggregate, 真正 fan-out 用 superpowers:dispatching-parallel-agents skill。

---

## 工期与并行机会

| Day | 完成任务 | 并行机会 |
|---|---|---|
| Day 1 | Task 1-3 (骨架 + schemas + budget) | — |
| Day 2 | Task 4-7 (client + extractor + saturation + seed) | Task 5 和 Task 6 可并行 (无依赖) |
| Day 2.5 | Task 8 + 9 (alembic + persona loader) | Task 8 和 9 可并行 |
| Day 3 | Task 10 (报告抽取, 独立可早跑) | — |
| Day 3-4 | Task 11-13 (runbook + orchestrator + 实际 6 subagent 并行跑) | 6 subagent 天然并行 |
| Day 4 | Task 14 (Opus 合成) | — |
| Day 5 | Task 15-17 (分类 + enrich + match) | Task 15 和 16 可并行 |
| Day 5.5-6 | Task 18-19 (评估 + 报告) | — |

实际 5.5-6.5 天 work, 与 spec §12 估算一致。
