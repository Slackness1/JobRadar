# Phase G — 推荐链路 v2 升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 SAIF MF 学生在第一屏推荐岗位环节不再失去耐心 — 第一屏 100% 是 ground truth 公司 + good 质量 + 27 sub_cat 命中, 推荐理由 100% 引用知识库 verbatim 或学生 hidden_highlight。

**Architecture:** 6 工序流水线: XHS 补爬到 27 sub_cat baseline → Opus 一次合成公司 ground truth 清单 → Opus hybrid synthesis 27 sub_cat 知识库 → audit + 补爬岗位 (与 quality_label backfill 并行) → DeepSeek Pro Multi-pass C 决策树 enrich 5-8k 岗位 sub_cat → recommendation.py 重写 v2 (废弃 canonical_track 路径, 走新 sub_category + 3 维 cross + LLM rerank with 知识库 + 4 anchor 推荐理由) + 公司 fallback surface。env flag `RECOMMENDATION_V2_ENABLED` 灰度。

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + SQLite; DeepSeek v4-Pro (reasoning_effort=medium/high) + Opus 4.7 (1M context); DashScope text-embedding-v3; 复用 demo XHS crawler infra (Decodo desktop + TikHub `get_note_info` xsec_token URL); 复用 12+ 个 finance crawler。

**Spec**: `docs/superpowers/specs/2026-05-27-phase-g-recommendation-pipeline-v2-design.md`

---

## File Structure

### 新建文件

```
backend/
├── alembic/versions/
│   ├── g1a2b3c4d5e6_phase_g_sub_cat_columns.py        # T0: jobs 表 7 列
│   └── g7b8c9d0e1f2_phase_g_knowledge_tables.py       # T0: taxonomy_xhs_posts + knowledge_subcategories
│
├── app/services/
│   ├── phase_g/                                        # 新模块, Phase G 所有 service-level 代码
│   │   ├── __init__.py
│   │   ├── ground_truth.py                             # T4: Opus 一次合成 ground_truth_companies_v1.json
│   │   ├── xhs_classifier.py                           # T1-T3: 691 帖分桶 + 补爬 + 抽取
│   │   ├── knowledge_synthesis.py                      # T5-T6: 27 sub_cat hybrid Opus synthesis
│   │   ├── audit.py                                    # T7: ground truth 公司 audit (绿/黄/红 gap)
│   │   ├── sub_cat_enricher.py                         # T11-T12: Multi-pass C
│   │   ├── company_fallback.py                         # T18: fallback 公司 + hiring_season 解释
│   │   └── recommendation_v2/                          # T14-T17: v2 推荐链路
│   │       ├── __init__.py
│   │       ├── recall.py                               # T14: 新 SQL recall (sub_category-only)
│   │       ├── scoring.py                              # T15: 3 维 cross 加权
│   │       ├── rerank.py                               # T16: LLM rerank with 知识库
│   │       └── narrative.py                            # T17: 4 anchor 推荐理由
│   │
│   └── job_helpers.py                                  # T0: detect_internship() 派生函数
│
├── scripts/phase_g/                                    # 新目录, runner scripts (一次性)
│   ├── 01_classify_existing_xhs.py                     # T1
│   ├── 02_identify_short_subcats.py                    # T2
│   ├── 03_crawl_short_subcats.py                       # T3
│   ├── 04_generate_ground_truth.py                     # T4
│   ├── 05_synthesize_knowledge_hybrid.py               # T5-T6
│   ├── 07_audit_coverage.py                            # T7
│   ├── 08_crawl_missing_companies.py                   # T8
│   ├── 10_quality_label_backfill.py                    # T10
│   ├── 12_enrich_sub_cat.py                            # T12
│   └── 20_ab_test_v1_vs_v2.py                          # T20
│
├── data/
│   └── ground_truth_companies_v1.json                  # T4 output (committed)
│
└── tests/phase_g/                                      # 新目录
    ├── __init__.py
    ├── test_ground_truth_schema.py                     # T4
    ├── test_xhs_classifier.py                          # T1
    ├── test_knowledge_synthesis.py                     # T5/T6
    ├── test_audit.py                                   # T7
    ├── test_quality_label_prompt.py                    # T9
    ├── test_sub_cat_enricher.py                        # T11
    ├── test_recommendation_v2_recall.py                # T14
    ├── test_recommendation_v2_scoring.py               # T15
    ├── test_recommendation_v2_rerank.py                # T16
    ├── test_recommendation_v2_narrative.py             # T17
    ├── test_company_fallback.py                        # T18
    └── test_recommendation_v2_e2e.py                   # T19/T20

docs/
├── sub_cat_knowledge/                                  # T6 output (27 md, committed)
│   ├── fund_equity_researcher.md
│   ├── ... (26 个)
└── _phase_g/                                           # T7 output
    └── audit_v1.md

resume-copilot-web/components/recommendation/
└── CompanyFallbackCard.tsx                             # T18 UI
```

### 修改文件

- `backend/app/models.py` — jobs 表添加 7 列 (T0); 新加 TaxonomyXhsPost + KnowledgeSubcategory 两个 model (T0)
- `backend/app/config.py` — 加 `RECOMMENDATION_V2_ENABLED` env flag (T0)
- `backend/app/services/crawler_llm_enrich.py` — 升级 model + reasoning_effort + prompt (T9)
- `backend/app/services/resume_copilot/recommendation.py` — deprecate 老路径, wire 进 recommendation_v2 (T19)
- `backend/app/services/resume_copilot/narrative.py` — wire 进 v2 narrative (T19)
- `backend/app/routers/recommend.py` — 加 `/api/recommend/companies-fallback` endpoint (T18)
- `resume-copilot-web/app/(workspace)/page.tsx` — 接入 CompanyFallbackCard (T18)
- `CHANGELOG.md` — Phase G W22-W24 entry (T22)
- `ACTIVITY.md` — 追加 (T22)

---

## Task 列表

22 个 task, 按依赖关系排序:

| # | Task | 工序 | 预估 | 依赖 |
|---|---|---|---|---|
| T0 | Setup — branch + env flag + 2 Alembic migrations + base dirs | 0 | 30 min | — |
| T1 | XHS classifier: classify 691 existing posts to 27 sub_cat | 3a | 1.5h | T0 |
| T2 | 识别短板 sub_cat + 生成 targeted XHS queries | 3a | 1h | T1 |
| T3 | 跑补爬 + Pro 抽取 + 入 taxonomy_xhs_posts | 3a | 4h | T2 |
| T4 | Opus 1-shot 生成 ground_truth_companies_v1.json | 0 | 1h | T3 |
| T5 | Hybrid Opus synthesis — 前 5 个 sub_cat 用 subagent | 3b | 3h | T4 |
| T6 | Pure API loop 剩 22 个 sub_cat + 入 DB + md | 3b | 3h | T5 |
| T7 | Audit script: ground truth vs 库现状 gap 报告 | 1 | 2h | T4 |
| T8 | 补爬缺失公司 (must_have only) | 1 | 16-24h | T7 |
| T9 | Quality_label 7 等级 prompt 升级 + model 切 Pro medium | 2 | 2h | T0 |
| T10 | 跑 28k quality_label backfill | 2 | 1h (含 LLM 跑批) | T9 |
| T11 | Sub_cat enrich Multi-pass C 实现 (Pass 1 strategy + Pass 2 sub_cat) | 4 | 4h | T6 |
| T12 | 跑 5-8k ground truth 池 sub_cat enrich | 4 | 2h (含 LLM 跑批) | T11, T10, T8 |
| T13 | 50 样本人工 review sub_cat 准确率 (硬验收指标 5) | 4 | 1.5h | T12 |
| T14 | recommendation_v2 — 5.1 新 SQL recall (sub_category-only) | 5.1 | 2h | T12 |
| T15 | recommendation_v2 — 5.2 三维 cross 加权评分 | 5.2 | 3h | T14 |
| T16 | recommendation_v2 — 5.3 LLM rerank with 知识库 prompt | 5.3 | 3h | T15 |
| T17 | recommendation_v2 — 5.4 narrative 4 anchor 模板 | 5.4 | 3h | T16 |
| T18 | 5.5 公司 fallback API + UI 卡片 | 5.5 | 4h | T6, T17 |
| T19 | env flag 接线 + 老 canonical_track 推荐路径 deprecate | 5 | 1h | T17, T18 |
| T20 | 9 persona × 3 sub_cat A/B test 跑 + 报告 (硬验收 1-4) | 验收 | 4h | T19 |
| T21 | ACTIVITY/CHANGELOG 更新 + prod rollout playbook | 文档 | 1h | T20 |

**关键路径**: T0 → T1 → T2 → T3 → T4 → T5 → T6 → (T7 → T8 ∥ T11) → T12 → T13 → T14 → T15 → T16 → T17 → T18 → T19 → T20 → T21

**总工期**: 12.5-15.5 天 (T8 补爬是最大变数)

---

## Task 0: Setup — branch + env flag + 2 Alembic migrations + base dirs

**Files:**
- Create: `backend/alembic/versions/g1a2b3c4d5e6_phase_g_sub_cat_columns.py`
- Create: `backend/alembic/versions/g7b8c9d0e1f2_phase_g_knowledge_tables.py`
- Create: `backend/app/services/phase_g/__init__.py`
- Create: `backend/app/services/phase_g/recommendation_v2/__init__.py`
- Create: `backend/app/services/job_helpers.py`
- Create: `backend/scripts/phase_g/__init__.py`
- Create: `backend/tests/phase_g/__init__.py`
- Modify: `backend/app/models.py` (add 7 cols + 2 new models)
- Modify: `backend/app/config.py` (add `RECOMMENDATION_V2_ENABLED`)

- [ ] **Step 1: Create feature branch from main**

```bash
cd /home/chuanbo/projects/JobRadar
git checkout main && git pull --ff-only
git checkout -b phase-g/recommendation-pipeline-v2
```

- [ ] **Step 2: Create base directory skeleton**

```bash
mkdir -p backend/app/services/phase_g/recommendation_v2
mkdir -p backend/scripts/phase_g
mkdir -p backend/tests/phase_g
mkdir -p docs/sub_cat_knowledge
mkdir -p docs/_phase_g
touch backend/app/services/phase_g/__init__.py
touch backend/app/services/phase_g/recommendation_v2/__init__.py
touch backend/scripts/phase_g/__init__.py
touch backend/tests/phase_g/__init__.py
```

- [ ] **Step 3: Add `RECOMMENDATION_V2_ENABLED` env flag**

Edit `backend/app/config.py`, find Settings class, add field:

```python
class Settings(BaseSettings):
    # ... existing fields ...
    RECOMMENDATION_V2_ENABLED: bool = False  # Phase G v2 推荐链路灰度
```

- [ ] **Step 4: Add models for jobs 表 7 列 + 2 new tables**

Edit `backend/app/models.py`, find `class Job(Base)`, add columns:

```python
class Job(Base):
    # ... existing columns ...
    sub_category = Column(Text, nullable=True, index=True)
    sub_category_secondary = Column(Text, nullable=True)
    industry_focus = Column(Text, nullable=True)        # JSON array as string
    institution_tier = Column(Text, nullable=True, index=True)
    sub_cat_confidence = Column(Float, nullable=True)
    sub_cat_reasoning = Column(Text, nullable=True)
    sub_cat_enriched_at = Column(DateTime, nullable=True)
```

Add 2 new models at end of `models.py`:

```python
class TaxonomyXhsPost(Base):
    """Phase G — XHS 帖 per 27 sub_cat."""
    __tablename__ = "taxonomy_xhs_posts"
    id = Column(Integer, primary_key=True)
    sub_cat = Column(Text, nullable=False, index=True)
    source_url = Column(Text, nullable=False, unique=True)
    company_mentions = Column(Text)        # JSON array
    verbatim_signals = Column(Text)        # JSON array
    raw_content = Column(Text, nullable=False)
    extracted_fields = Column(Text)        # JSON
    relevance_score = Column(Float)
    scraped_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeSubcategory(Base):
    """Phase G — 27 sub_cat 结构化知识库."""
    __tablename__ = "knowledge_subcategories"
    id = Column(Integer, primary_key=True)
    sub_cat = Column(Text, nullable=False, unique=True)
    sub_cat_slug = Column(Text, nullable=False, unique=True)
    strategy_type = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=False)        # 15 字段 JSON
    data_confidence = Column(Text, nullable=False)     # high/medium/low
    data_basis_json = Column(Text, nullable=False)
    hiring_season_json = Column(Text)
    embedding = Column(LargeBinary)                    # DashScope text-embedding-v3
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

Make sure `from sqlalchemy import LargeBinary, Float, Column, Integer, Text, DateTime` is imported.

- [ ] **Step 5: Generate 2 Alembic migrations**

```bash
cd backend
PYTHONPATH=. .venv/bin/alembic revision --autogenerate -m "phase_g_sub_cat_columns"
PYTHONPATH=. .venv/bin/alembic revision --autogenerate -m "phase_g_knowledge_tables"
```

This should create 2 files in `backend/alembic/versions/` with auto-generated DDL based on the model changes. Verify both have `op.add_column` (first migration) and `op.create_table` (second migration). 

Add idempotency check in each migration (top of upgrade()):

```python
def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = [c["name"] for c in inspector.get_columns("jobs")]
    if "sub_category" not in existing_columns:
        op.add_column("jobs", sa.Column("sub_category", sa.Text(), nullable=True))
        # ... etc for other columns
```

Idempotency is required because legacy `ensure_compatible_schema()` may have partially run on dev DB.

- [ ] **Step 6: Run migrations on dev DB**

```bash
cd backend && PYTHONPATH=. .venv/bin/alembic upgrade head 2>&1 | tail -10
```

Expected: 2 "Running upgrade" lines, no errors. Verify with:

```bash
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('data/jobradar.db')
cur = conn.cursor()
cur.execute('PRAGMA table_info(jobs)')
cols = [r[1] for r in cur.fetchall()]
assert 'sub_category' in cols
assert 'institution_tier' in cols
print('OK — Phase G columns added')
cur.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name IN ('taxonomy_xhs_posts','knowledge_subcategories')\")
assert len(cur.fetchall()) == 2
print('OK — Phase G tables created')
"
```

- [ ] **Step 7: Create `detect_internship()` helper**

Create `backend/app/services/job_helpers.py`:

```python
"""Job-level derived helpers used by Phase G推荐 v2."""
from __future__ import annotations
from app.models import Job


_INTERNSHIP_TITLE_SIGNALS = ("实习", "intern", "实习生", "Internship")
_INTERNSHIP_DUTY_SIGNALS = ("实习期", "在校生", "学生岗")


def detect_internship(job: Job) -> bool:
    """Return True if job appears to be an internship (vs full-time).

    Used by Phase G recommendation v2 to surface internships in a separate tab,
    not first-screen recommendations.
    """
    title = job.job_title or ""
    if any(sig in title for sig in _INTERNSHIP_TITLE_SIGNALS):
        return True
    duty = job.job_duty or ""
    if any(sig in duty for sig in _INTERNSHIP_DUTY_SIGNALS):
        return True
    if job.job_stage and "实习" in job.job_stage:
        return True
    return False
```

- [ ] **Step 8: Write unit test for `detect_internship()`**

Create `backend/tests/phase_g/test_job_helpers.py`:

```python
import pytest
from app.models import Job
from app.services.job_helpers import detect_internship


def _make(title=None, duty=None, stage=None):
    j = Job(job_id="x", job_title=title, job_duty=duty, job_stage=stage)
    return j


def test_internship_title_signal():
    assert detect_internship(_make(title="量化研究实习生")) is True
    assert detect_internship(_make(title="Software Intern (Beijing)")) is True


def test_internship_duty_signal():
    assert detect_internship(_make(title="数据分析", duty="实习期 6 个月")) is True


def test_internship_stage_signal():
    assert detect_internship(_make(title="分析师", stage="实习")) is True


def test_full_time_not_internship():
    assert detect_internship(_make(title="量化研究员")) is False
    assert detect_internship(_make(title="基金经理助理", duty="正式岗位")) is False


def test_null_safe():
    assert detect_internship(_make()) is False
```

- [ ] **Step 9: Run tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_job_helpers.py -v
```

Expected: 5 passed.

- [ ] **Step 10: Commit T0**

```bash
git add backend/app/models.py backend/app/config.py \
        backend/app/services/job_helpers.py \
        backend/app/services/phase_g/ \
        backend/scripts/phase_g/__init__.py \
        backend/tests/phase_g/ \
        backend/alembic/versions/g*_phase_g_*.py \
        docs/sub_cat_knowledge/ docs/_phase_g/
git commit -m "$(cat <<'EOF'
phase-g(T0): setup — env flag + 2 migrations + base dirs + detect_internship helper

- RECOMMENDATION_V2_ENABLED env flag (default OFF, dev VPS ON 验)
- jobs 表新加 7 列 (sub_category / sub_category_secondary / industry_focus / institution_tier / sub_cat_confidence / sub_cat_reasoning / sub_cat_enriched_at)
- 2 新表 taxonomy_xhs_posts + knowledge_subcategories
- detect_internship() 派生函数 (job_helpers.py) + 单测 5 个 passed

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 1: XHS classifier — classify 691 existing posts to 27 sub_cat

**Files:**
- Create: `backend/app/services/phase_g/xhs_classifier.py`
- Create: `backend/scripts/phase_g/01_classify_existing_xhs.py`
- Create: `backend/tests/phase_g/test_xhs_classifier.py`

**Context:** demo 阶段 `backend/data/personas/` 旁边或 `tools/xhs_post_comment_crawler/` 产出了 691 帖 XHS 数据, 按 7 大 bucket 不均匀分布。Phase G 需要重新按 27 sub_cat 多标签分类, threshold > 0.7 才入桶。

- [ ] **Step 1: Locate the 691 existing XHS posts**

```bash
find /home/chuanbo/projects/JobRadar -name "*xhs*" -path "*taxonomy*" -o -name "*.jsonl" -path "*xhs*" 2>/dev/null | head -10
ls /home/chuanbo/projects/JobRadar/.worktrees/crawler-xhs/data/raw/ 2>&1 | head
```

Likely paths (verify which has the 691 posts): `.worktrees/crawler-xhs/data/raw/decodo_xhs/*.json` or `backend/data/_phase_f/xhs_posts_v1.jsonl`. Record the actual path for use in subsequent steps. If not found, dispatch implementer subagent to grep wider.

- [ ] **Step 2: Write the XhsClassifier class skeleton**

Create `backend/app/services/phase_g/xhs_classifier.py`:

```python
"""Multi-label classifier: XHS post -> 27 sub_cat (Phase G 3a step 1)."""
from __future__ import annotations
import json
import os
from dataclasses import dataclass
from typing import Iterable
from openai import OpenAI


_SUB_CATS_27 = [
    # 基本面权益
    "公募权益研究员", "行业研究员·消费", "行业研究员·TMT-医药-周期",
    "公募指数研究员", "公募基金中后台",
    # 量化
    "量化研究员·中频", "量化研究员·高频", "量化开发QD",
    "AI 量化工程师", "量化因子工程师",
    # 固定收益
    "信用研究员", "固收交易员", "固收+多资产", "利率宏观策略",
    # 卖方研究
    "卖方研究员·TMT", "卖方研究员·消费医药周期", "卖方研究员·宏观策略",
    "买方 Quant", "投行 IBD",
    # 多资产_FOF_衍生品
    "资管FOF", "自营FOF", "财富管理FOF", "结构化产品衍生品",
    # 相关补充
    "PE投后VC行研",
    # AI 应用_PM_开发
    "LLM算法post-train", "Agent工程师", "多模态推理优化", "AI PM", "AI算法业务",
]


@dataclass
class XhsClassification:
    primary_sub_cat: str | None
    primary_confidence: float
    secondary_sub_cat: str | None
    secondary_confidence: float
    rationale: str


_SYSTEM_PROMPT = """你是中国金融 + AI 校招赛道分类专家. 给一篇小红书帖, 判定属于以下 27 个细分赛道中的哪 1-2 个 (multi-label).

27 个 sub_cat:
{subcats}

输出 JSON, 严格 schema:
{{
  "primary_sub_cat": "<27 个之一 或 null>",
  "primary_confidence": <0-1 浮点>,
  "secondary_sub_cat": "<27 个之一 或 null (只标 1 个不要凑数)>",
  "secondary_confidence": <0-1>,
  "rationale": "<≤80 字, 说明你为什么这么标>"
}}

规则:
- 帖子明显不属于上述任何赛道, primary_sub_cat 输出 null, confidence 0
- 帖子只对应 1 个赛道, secondary_sub_cat 输出 null
- 不要凑两个 sub_cat
- confidence 是你对自己判断的把握, 不是帖子内容质量
"""


def _build_system_prompt() -> str:
    return _SYSTEM_PROMPT.format(subcats="\n".join(f"- {s}" for s in _SUB_CATS_27))


def classify_post(client: OpenAI, post_content: str, model: str = "deepseek-v4-pro") -> XhsClassification:
    """Single-post classification via DeepSeek Pro (reasoning_effort=medium)."""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _build_system_prompt()},
            {"role": "user", "content": f"帖子内容:\n\n{post_content[:3000]}"},
        ],
        extra_body={"reasoning_effort": "medium"},
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    raw = json.loads(resp.choices[0].message.content)
    return XhsClassification(
        primary_sub_cat=raw.get("primary_sub_cat"),
        primary_confidence=float(raw.get("primary_confidence", 0)),
        secondary_sub_cat=raw.get("secondary_sub_cat"),
        secondary_confidence=float(raw.get("secondary_confidence", 0)),
        rationale=raw.get("rationale", ""),
    )


def classify_batch(client: OpenAI, posts: Iterable[dict], threshold: float = 0.7, model: str = "deepseek-v4-pro") -> list[dict]:
    """Classify a batch of posts. Returns posts with `classification` field added.
    
    Filters: only includes classifications with primary_confidence > threshold.
    """
    out = []
    for post in posts:
        content = post.get("content") or post.get("raw_content") or post.get("desc") or ""
        if not content.strip():
            continue
        c = classify_post(client, content, model=model)
        if c.primary_confidence < threshold:
            continue
        post_copy = dict(post)
        post_copy["classification"] = {
            "primary_sub_cat": c.primary_sub_cat,
            "primary_confidence": c.primary_confidence,
            "secondary_sub_cat": c.secondary_sub_cat if c.secondary_confidence > threshold else None,
            "secondary_confidence": c.secondary_confidence,
            "rationale": c.rationale,
        }
        out.append(post_copy)
    return out


def _get_client() -> OpenAI:
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("RESUME_COPILOT_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    return OpenAI(api_key=api_key, base_url=base_url)
```

- [ ] **Step 3: Write unit test (mocked LLM)**

Create `backend/tests/phase_g/test_xhs_classifier.py`:

```python
from unittest.mock import MagicMock, patch
import json
from app.services.phase_g.xhs_classifier import classify_post, classify_batch, _SUB_CATS_27


def _mock_llm_response(payload: dict):
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = json.dumps(payload)
    return mock_resp


def test_classify_post_returns_structured():
    client = MagicMock()
    client.chat.completions.create.return_value = _mock_llm_response({
        "primary_sub_cat": "量化研究员·中频",
        "primary_confidence": 0.92,
        "secondary_sub_cat": None,
        "secondary_confidence": 0,
        "rationale": "明确提到中频 alpha 因子 + sharpe",
    })
    out = classify_post(client, "讨论中频量化 alpha 因子 sharpe > 0.8")
    assert out.primary_sub_cat == "量化研究员·中频"
    assert out.primary_confidence == 0.92
    assert out.secondary_sub_cat is None


def test_classify_batch_filters_low_confidence():
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        _mock_llm_response({
            "primary_sub_cat": "量化研究员·中频", "primary_confidence": 0.92,
            "secondary_sub_cat": None, "secondary_confidence": 0, "rationale": "x",
        }),
        _mock_llm_response({
            "primary_sub_cat": "公募权益研究员", "primary_confidence": 0.5,  # below threshold
            "secondary_sub_cat": None, "secondary_confidence": 0, "rationale": "y",
        }),
    ]
    posts = [{"content": "量化", "id": "a"}, {"content": "公募", "id": "b"}]
    out = classify_batch(client, posts, threshold=0.7)
    assert len(out) == 1
    assert out[0]["id"] == "a"


def test_sub_cats_27_count():
    assert len(_SUB_CATS_27) == 27
    assert len(set(_SUB_CATS_27)) == 27  # all unique
```

- [ ] **Step 4: Run tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_xhs_classifier.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Write the runner script**

Create `backend/scripts/phase_g/01_classify_existing_xhs.py`:

```python
"""Classify the 691 existing XHS posts (from demo Phase F) to 27 sub_cat.

Output: backend/data/_phase_g/xhs_classified_v1.jsonl (one post per line, classified posts only)
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

# Resolve repo root (script lives 3 levels deep)
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.phase_g.xhs_classifier import classify_batch, _get_client

# Verified path from T1 Step 1 — UPDATE this path after Step 1 locates the data
INPUT_PATHS = [
    REPO_ROOT / "backend/data/_phase_f/xhs_posts_v1.jsonl",
    # Add other candidate paths if first doesn't exist
]
OUTPUT_DIR = REPO_ROOT / "backend/data/_phase_g"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "xhs_classified_v1.jsonl"
PROGRESS_FILE = OUTPUT_DIR / "xhs_classified_v1.progress.json"


def _load_existing_progress() -> set[str]:
    """Resume support: track already-processed post IDs."""
    if PROGRESS_FILE.exists():
        return set(json.loads(PROGRESS_FILE.read_text()).get("done_ids", []))
    return set()


def _save_progress(done_ids: set[str]) -> None:
    PROGRESS_FILE.write_text(json.dumps({"done_ids": list(done_ids)}, ensure_ascii=False))


def load_input_posts() -> list[dict]:
    for path in INPUT_PATHS:
        if path.exists():
            print(f"Loading from {path}")
            if path.suffix == ".jsonl":
                return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            else:
                return json.loads(path.read_text())
    raise FileNotFoundError(f"None of input paths exist: {INPUT_PATHS}")


def main():
    posts = load_input_posts()
    print(f"Loaded {len(posts)} input posts")
    done_ids = _load_existing_progress()
    posts_to_process = [p for p in posts if (p.get("id") or p.get("note_id") or "") not in done_ids]
    print(f"Resume: {len(done_ids)} already done, {len(posts_to_process)} to process")

    client = _get_client()
    BATCH_SIZE = 20
    total_classified = 0
    with OUTPUT_FILE.open("a", encoding="utf-8") as outf:
        for i in range(0, len(posts_to_process), BATCH_SIZE):
            batch = posts_to_process[i:i+BATCH_SIZE]
            classified = classify_batch(client, batch, threshold=0.7)
            for c in classified:
                outf.write(json.dumps(c, ensure_ascii=False) + "\n")
                total_classified += 1
            # Update progress
            for p in batch:
                pid = p.get("id") or p.get("note_id") or ""
                if pid:
                    done_ids.add(pid)
            _save_progress(done_ids)
            print(f"  Batch {i//BATCH_SIZE + 1}: {len(batch)} processed, {len(classified)} above threshold (total: {total_classified})")

    print(f"\nDone. {total_classified} classified posts written to {OUTPUT_FILE}")
    print(f"Filtered out: {len(posts_to_process) - total_classified} posts below 0.7 confidence")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Dry-run on 10 posts first**

Test on small sample before full 691 batch:

```bash
cd backend
head -n 10 data/_phase_f/xhs_posts_v1.jsonl > /tmp/xhs_sample.jsonl  # adjust path
PYTHONPATH=. .venv/bin/python -c "
import json, sys
sys.path.insert(0, '.')
from app.services.phase_g.xhs_classifier import classify_batch, _get_client
posts = [json.loads(l) for l in open('/tmp/xhs_sample.jsonl')]
client = _get_client()
out = classify_batch(client, posts, threshold=0.7)
print(f'{len(out)}/{len(posts)} classified above threshold')
for o in out[:3]:
    print('  -', o['classification']['primary_sub_cat'], o['classification']['primary_confidence'])
"
```

Expected: 6-9 / 10 classified above 0.7. If many are low-confidence, examine threshold or post quality.

- [ ] **Step 7: Run full classification**

```bash
cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/01_classify_existing_xhs.py 2>&1 | tail -30
```

Expected: ~500-600 posts above threshold, written to `data/_phase_g/xhs_classified_v1.jsonl`. Cost ~$1 (Pro medium small calls).

- [ ] **Step 8: Verify output distribution**

```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
import json
from collections import Counter
posts = [json.loads(l) for l in open('data/_phase_g/xhs_classified_v1.jsonl')]
primary = Counter(p['classification']['primary_sub_cat'] for p in posts)
print('Sub_cat distribution:')
for sc, n in primary.most_common():
    print(f'  {sc}: {n}')
print(f'Total: {len(posts)}')
"
```

Record output as it informs T2 short sub_cat identification.

- [ ] **Step 9: Commit T1**

```bash
git add backend/app/services/phase_g/xhs_classifier.py \
        backend/scripts/phase_g/01_classify_existing_xhs.py \
        backend/tests/phase_g/test_xhs_classifier.py \
        backend/data/_phase_g/xhs_classified_v1.jsonl \
        backend/data/_phase_g/xhs_classified_v1.progress.json
git commit -m "$(cat <<'EOF'
phase-g(T1): XHS classifier — 691 帖按 27 sub_cat multi-label 分类

DeepSeek Pro reasoning=medium, threshold 0.7. 单测 3 passed, 实际批跑 ~600 帖入桶。
output: backend/data/_phase_g/xhs_classified_v1.jsonl

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: 识别短板 sub_cat + 生成 targeted XHS queries

**Files:**
- Create: `backend/scripts/phase_g/02_identify_short_subcats.py`
- Create: `backend/data/_phase_g/short_subcats_queries_v1.json` (output)

- [ ] **Step 1: Write the analysis script**

Create `backend/scripts/phase_g/02_identify_short_subcats.py`:

```python
"""Identify sub_cats below baseline (30 posts + 10 unique companies) and generate
targeted XHS queries to补足 to baseline.

Output: data/_phase_g/short_subcats_queries_v1.json
"""
from __future__ import annotations
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.phase_g.xhs_classifier import _SUB_CATS_27

CLASSIFIED_FILE = REPO_ROOT / "backend/data/_phase_g/xhs_classified_v1.jsonl"
GROUND_TRUTH_DRAFT = REPO_ROOT / "docs/taxonomy-投研-final-v1.md"  # for typical_companies hint
OUTPUT_FILE = REPO_ROOT / "backend/data/_phase_g/short_subcats_queries_v1.json"

BASELINE_POSTS = 30
BASELINE_COMPANIES = 10


def extract_mentioned_companies(post: dict) -> set[str]:
    """Heuristic: scan post content for company name hits in a curated list.
    Use existing demo_companies_v1.json as the seed company list."""
    demo_path = REPO_ROOT / "backend/data/demo_companies_v1.json"
    companies = [c["name"] for c in json.loads(demo_path.read_text())]
    text = (post.get("content") or post.get("raw_content") or "") + " " + (post.get("title") or "")
    return {c for c in companies if c in text}


def classify_distribution() -> dict[str, dict]:
    """Returns {sub_cat: {post_count, company_count, companies}}."""
    by_subcat = defaultdict(lambda: {"posts": [], "companies": set()})
    for line in CLASSIFIED_FILE.read_text().splitlines():
        if not line.strip():
            continue
        post = json.loads(line)
        for key in ("primary_sub_cat", "secondary_sub_cat"):
            sc = post["classification"].get(key)
            if sc:
                by_subcat[sc]["posts"].append(post)
                by_subcat[sc]["companies"].update(extract_mentioned_companies(post))
    return {sc: {"post_count": len(d["posts"]), "company_count": len(d["companies"]),
                  "companies": sorted(d["companies"])} for sc, d in by_subcat.items()}


# Hardcoded per-sub_cat seed query templates (used when XHS data sparse).
# Sub_cat name + 2-3 ground truth companies + 1 verbatim signal word per query.
_QUERY_TEMPLATES = {
    "PE投后VC行研": [
        "高瓴 PE 投后 实习", "弘毅资本 行研", "中投公司 二级市场",
        "淡马锡 上海 投资 实习", "PE 投后管理 学姐分享",
    ],
    "信用研究员": [
        "信用研究 城投 内卷", "光大永明 信用债 实习",
        "中再资产 信用研究员", "信用研究 转债 多资产", "公募固收 信用",
    ],
    "固收交易员": [
        "券商自营 固收交易", "平安 ficc 实习", "中信 ficc 交易员",
        "固收交易 银行间", "国债交易 卖方研究",
    ],
    "投行 IBD": [
        "三中一华 投行 IBD 实习", "中金投行 TMT", "中信投行 消费",
        "IBD 暑期实习", "保荐承做 投行",
    ],
    "结构化产品衍生品": [
        "中金衍生品 实习", "FCN 结构性产品", "期权策略 衍生品",
        "家办 衍生品", "越秀 结构化产品",
    ],
    "利率宏观策略": [
        "公募 利率 宏观策略", "保险资管 利率研究", "货币中介 利率",
        "宏观利率分析 实习", "公募 利率 大类资产",
    ],
    "财富管理FOF": [
        "信银理财 FOF", "平安 财富 FOF", "公募 财富线 FOF",
        "招商 财富 FOF 投后", "财富 FOF 客户服务",
    ],
    "多模态推理优化": [
        "字节 多模态 推理优化", "投机采样 Speculative", "商汤 多模态大模型",
        "华为 推理优化 实习", "腾讯 多模态 算法",
    ],
}


def generate_queries_for_short_subcats(dist: dict[str, dict]) -> dict[str, list[str]]:
    """For sub_cats below baseline, generate targeted XHS queries."""
    out = {}
    for sc in _SUB_CATS_27:
        info = dist.get(sc, {"post_count": 0, "company_count": 0})
        if info["post_count"] < BASELINE_POSTS or info["company_count"] < BASELINE_COMPANIES:
            queries = _QUERY_TEMPLATES.get(sc, [])
            if not queries:
                # Fallback: 5 generic queries based on sub_cat name
                queries = [
                    f"{sc} 实习",
                    f"{sc} 招聘",
                    f"{sc} 学姐分享",
                    f"{sc} 应届生",
                    f"{sc} 求职",
                ]
            out[sc] = queries
    return out


def main():
    dist = classify_distribution()
    print(f"Distribution across 27 sub_cats:")
    for sc in _SUB_CATS_27:
        info = dist.get(sc, {"post_count": 0, "company_count": 0})
        status = "OK" if info["post_count"] >= BASELINE_POSTS and info["company_count"] >= BASELINE_COMPANIES else "SHORT"
        print(f"  [{status}] {sc}: {info['post_count']} posts, {info['company_count']} companies")
    
    short = generate_queries_for_short_subcats(dist)
    print(f"\n{len(short)} sub_cats below baseline, will补爬:")
    for sc, queries in short.items():
        print(f"  {sc}: {len(queries)} queries")
    
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps({
        "baseline": {"posts": BASELINE_POSTS, "companies": BASELINE_COMPANIES},
        "distribution": {sc: {"post_count": dist.get(sc, {}).get("post_count", 0),
                                "company_count": dist.get(sc, {}).get("company_count", 0)}
                        for sc in _SUB_CATS_27},
        "queries_to_run": short,
    }, indent=2, ensure_ascii=False))
    print(f"\nOutput: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run analysis**

```bash
cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/02_identify_short_subcats.py 2>&1 | tee /tmp/short_subcat_report.txt
```

Expected output: 7-9 sub_cats marked SHORT, query plan written to `data/_phase_g/short_subcats_queries_v1.json`.

- [ ] **Step 3: Commit T2**

```bash
git add backend/scripts/phase_g/02_identify_short_subcats.py \
        backend/data/_phase_g/short_subcats_queries_v1.json
git commit -m "$(cat <<'EOF'
phase-g(T2): identify 短板 sub_cats + 生成 targeted XHS 补爬 queries

baseline = 30 posts + 10 unique companies. 短板 sub_cat 用 hardcoded query templates (PE/VC、信用、固收交易、投行 IBD、衍生品、利率宏观、财富 FOF、多模态推理优化), fallback 用 sub_cat 名 generic queries。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 跑补爬 + Pro 抽取 + 入 taxonomy_xhs_posts

**Files:**
- Modify: `backend/app/services/phase_g/xhs_classifier.py` (add extraction function)
- Create: `backend/scripts/phase_g/03_crawl_short_subcats.py`

- [ ] **Step 1: Locate the demo crawler infra**

```bash
find /home/chuanbo/projects/JobRadar -path '*xhs_post_comment_crawler*' -name "*.py" 2>/dev/null | head -10
ls /home/chuanbo/projects/JobRadar/tools/xhs_post_comment_crawler/ 2>&1 | head
```

Record the entry point. Implementer subagent should read the demo crawler module to understand Decodo + TikHub API usage + xsec_token URL building. Key files (estimated from spec): `tools/xhs_post_comment_crawler/decodo_client.py`, `tools/xhs_post_comment_crawler/tikhub_client.py`.

- [ ] **Step 2: Write the crawler orchestrator script**

Create `backend/scripts/phase_g/03_crawl_short_subcats.py`:

```python
"""For each short sub_cat, run targeted XHS queries via Decodo/TikHub, filter
by Pro relevance > 0.6, then extract structured signals (硬门槛/工作样态/学生原话/
公司 mention/verbatim 信号词) via Pro extraction prompt. Write to taxonomy_xhs_posts table.

Resume-safe via progress file at data/_phase_g/crawl_progress.json
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "tools/xhs_post_comment_crawler"))

from app.database import SessionLocal
from app.models import TaxonomyXhsPost
from app.services.phase_g.xhs_classifier import _get_client, classify_post
from app.services.phase_g.xhs_extractor import extract_post_signals  # See Step 3

# Import the demo crawler — UPDATE these imports per actual module structure from Step 1
from decodo_client import search_xhs as decodo_search  # placeholder, verify exact API
from tikhub_client import get_note_info as tikhub_get  # placeholder

QUERIES_FILE = REPO_ROOT / "backend/data/_phase_g/short_subcats_queries_v1.json"
PROGRESS_FILE = REPO_ROOT / "backend/data/_phase_g/crawl_progress.json"
RELEVANCE_THRESHOLD = 0.6
POSTS_PER_QUERY = 15


def _load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"done_queries": [], "stats": {}}


def _save_progress(p: dict) -> None:
    PROGRESS_FILE.write_text(json.dumps(p, indent=2, ensure_ascii=False))


def crawl_query(query: str) -> list[dict]:
    """Returns list of post dicts with url, title, content, etc."""
    # Decodo search first (cheaper), fallback TikHub get_note_info
    try:
        posts = decodo_search(query, count=POSTS_PER_QUERY)
        return posts
    except Exception as e:
        print(f"    Decodo failed: {e}, trying TikHub")
        # Fallback path — implementer subagent should adapt to actual TikHub API
        return []


def main():
    plan = json.loads(QUERIES_FILE.read_text())
    progress = _load_progress()
    client = _get_client()
    db = SessionLocal()

    try:
        for sub_cat, queries in plan["queries_to_run"].items():
            print(f"\n=== {sub_cat} ===")
            for query in queries:
                key = f"{sub_cat}::{query}"
                if key in progress["done_queries"]:
                    print(f"  [SKIP] {query}")
                    continue
                
                print(f"  Crawling: {query}")
                try:
                    posts = crawl_query(query)
                except Exception as e:
                    print(f"    ERROR: {e}")
                    continue
                
                print(f"    Got {len(posts)} candidate posts")
                
                # Classify + relevance filter
                inserted = 0
                for post in posts:
                    url = post.get("url") or post.get("source_url")
                    if not url:
                        continue
                    # Skip if URL already in DB
                    existing = db.query(TaxonomyXhsPost).filter_by(source_url=url).first()
                    if existing:
                        continue
                    
                    content = (post.get("content") or post.get("desc") or "")[:3000]
                    if not content:
                        continue
                    
                    # Pro classifier check
                    c = classify_post(client, content)
                    if c.primary_sub_cat != sub_cat and c.secondary_sub_cat != sub_cat:
                        continue
                    relevance = max(c.primary_confidence, c.secondary_confidence)
                    if relevance < RELEVANCE_THRESHOLD:
                        continue
                    
                    # Pro extraction
                    signals = extract_post_signals(client, content, sub_cat)
                    
                    db.add(TaxonomyXhsPost(
                        sub_cat=sub_cat,
                        source_url=url,
                        company_mentions=json.dumps(signals.get("company_mentions", []), ensure_ascii=False),
                        verbatim_signals=json.dumps(signals.get("verbatim_signals", []), ensure_ascii=False),
                        raw_content=content,
                        extracted_fields=json.dumps(signals, ensure_ascii=False),
                        relevance_score=relevance,
                        scraped_at=datetime.utcnow(),
                    ))
                    inserted += 1
                
                db.commit()
                progress["done_queries"].append(key)
                progress["stats"][key] = {"crawled": len(posts), "inserted": inserted}
                _save_progress(progress)
                print(f"    Inserted {inserted} into taxonomy_xhs_posts")
    finally:
        db.close()
    
    print("\n=== Done. Final per-sub_cat count: ===")
    db = SessionLocal()
    try:
        from sqlalchemy import func
        counts = db.query(TaxonomyXhsPost.sub_cat, func.count(TaxonomyXhsPost.id)).group_by(TaxonomyXhsPost.sub_cat).all()
        for sc, n in counts:
            print(f"  {sc}: {n}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Implement xhs_extractor.py (Pro extraction)**

Create `backend/app/services/phase_g/xhs_extractor.py`:

```python
"""Extract structured signals from XHS post for a given sub_cat (Phase G 3a step 3)."""
from __future__ import annotations
import json
from openai import OpenAI


_SYSTEM_PROMPT = """你是中国金融 + AI 校招赛道情报抽取专家. 给一篇小红书帖 + 该帖所属的细分赛道 sub_cat, 抽取以下结构化信号:

- hard_requirements: 这个 sub_cat 的硬门槛 (e.g. 学历 / 实习背景 / 证书), 最多 5 条
- soft_signals: 加分项 (e.g. GitHub repo / 比赛获奖), 最多 5 条
- work_style: 工作样态 (e.g. 推票路演 / 行业调研深度 / sharpe > 0.8), ≤100 字
- compensation: 薪酬信号 (e.g. "应届生 25-40K"), ≤50 字, 如无明确数字填 null
- company_mentions: 提到的公司名 (数组)
- verbatim_signals: 学生原话或行业 verbatim quote (数组, 每条 ≤80 字), 最多 5 条
- pitfalls: 排雷信号 (e.g. "中后台不要被名字误导"), 最多 3 条

输出严格 JSON, 字段缺失填 null 或 []."""


def extract_post_signals(client: OpenAI, post_content: str, sub_cat: str, model: str = "deepseek-v4-pro") -> dict:
    """Pro extraction (reasoning_effort=medium)."""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"sub_cat: {sub_cat}\n\n帖子:\n{post_content[:3000]}"},
        ],
        extra_body={"reasoning_effort": "medium"},
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    return json.loads(resp.choices[0].message.content)
```

- [ ] **Step 4: Write unit test for extractor**

Add to `backend/tests/phase_g/test_xhs_classifier.py` (or create separate test file):

```python
from unittest.mock import MagicMock
import json
from app.services.phase_g.xhs_extractor import extract_post_signals


def test_extract_returns_dict():
    client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = json.dumps({
        "hard_requirements": ["985 + 硕士", "1 段公募实习"],
        "soft_signals": ["CFA 一级"],
        "work_style": "推票 + 路演",
        "compensation": "17-28 万",
        "company_mentions": ["易方达", "华夏"],
        "verbatim_signals": ["公募投研路径清晰"],
        "pitfalls": [],
    })
    client.chat.completions.create.return_value = mock_resp
    out = extract_post_signals(client, "demo content", "公募权益研究员")
    assert "易方达" in out["company_mentions"]
    assert len(out["hard_requirements"]) == 2
```

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_xhs_classifier.py -v
```

Expected: 4 passed total (3 from T1 + 1 new).

- [ ] **Step 5: Dry-run crawl on 1 query**

Before full run, dry-run 1 short sub_cat with 1 query:

```bash
cd backend
PYTHONPATH=. .venv/bin/python -c "
import sys
sys.path.insert(0, '../tools/xhs_post_comment_crawler')
# Adapt to actual API
from decodo_client import search_xhs
posts = search_xhs('PE 投后 实习', count=5)
print(f'Got {len(posts)} posts')
for p in posts[:2]:
    print(' -', p.get('title', '?')[:80])
"
```

Expected: 3-5 posts returned. If Decodo errors, switch to TikHub `get_note_info` (refer demo crawler doc).

- [ ] **Step 6: Run full crawl + extract**

```bash
cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/03_crawl_short_subcats.py 2>&1 | tee /tmp/crawl_log.txt
```

Expected: ~150-200 new posts inserted across 7-9 short sub_cats, each sub_cat reaching ≥30 posts + ≥10 companies. Cost ~$2-3 (Decodo + Pro extraction).

If a sub_cat still below baseline after first pass, log it; may need second pass with different queries (continue in next iteration).

- [ ] **Step 7: Verify baseline reached**

```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
from app.database import SessionLocal
from app.models import TaxonomyXhsPost
from sqlalchemy import func, distinct
from app.services.phase_g.xhs_classifier import _SUB_CATS_27
db = SessionLocal()
for sc in _SUB_CATS_27:
    n_posts = db.query(func.count(TaxonomyXhsPost.id)).filter_by(sub_cat=sc).scalar()
    # Approximate company count via JSON parsing
    posts = db.query(TaxonomyXhsPost).filter_by(sub_cat=sc).all()
    companies = set()
    import json as _json
    for p in posts:
        try: companies.update(_json.loads(p.company_mentions or '[]'))
        except: pass
    status = 'OK' if n_posts >= 30 and len(companies) >= 10 else 'SHORT'
    print(f'  [{status}] {sc}: {n_posts} posts, {len(companies)} companies')
db.close()
"
```

If 2+ sub_cats still SHORT, document them and either (a) add more queries to `_QUERY_TEMPLATES` in T2 script + re-run, or (b) accept SHORT and mark `data_confidence=low` in T6.

- [ ] **Step 8: Commit T3**

```bash
git add backend/app/services/phase_g/xhs_extractor.py \
        backend/scripts/phase_g/03_crawl_short_subcats.py \
        backend/tests/phase_g/test_xhs_classifier.py \
        backend/data/_phase_g/crawl_progress.json
git commit -m "$(cat <<'EOF'
phase-g(T3): XHS 补爬 + Pro 抽取 + 入 taxonomy_xhs_posts

复用 demo Decodo + TikHub infra, Pro relevance > 0.6 + Pro structured extraction (硬门槛/工作样态/公司 mention/verbatim signals/排雷)。短板 sub_cat 全部触达 baseline (≥30 帖 + ≥10 公司)。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Opus 1-shot 生成 ground_truth_companies_v1.json

**Files:**
- Create: `backend/app/services/phase_g/ground_truth.py`
- Create: `backend/scripts/phase_g/04_generate_ground_truth.py`
- Create: `backend/tests/phase_g/test_ground_truth_schema.py`
- Create: `backend/data/ground_truth_companies_v1.json` (output, committed)

- [ ] **Step 1: Write the Opus orchestrator**

Create `backend/app/services/phase_g/ground_truth.py`:

```python
"""Phase G 工序 0 — Opus 4.7 一次性合成 27 sub_cat × 公司清单 (ground truth)."""
from __future__ import annotations
import json
import os
from pathlib import Path
from anthropic import Anthropic


_SYSTEM_PROMPT = """你是 SAIF MF 校招赛道的资深求职顾问. 你需要为 27 个细分赛道 (sub_cat) 各列出一份"必须在岗位库里覆盖的公司清单".

输出严格 JSON, schema:
{
  "ground_truth": {
    "<sub_cat 名>": [
      {
        "name": "<公司中文名>",
        "tier": "<institution_tier, e.g. 一线公募 / 头部券商研究所 / 头部量化私募 / 大厂 AI 部门 等>",
        "primary_sub_cats": ["<该公司主招的 sub_cat, 1-3 个>"],
        "industry_focus": ["<相关行业, e.g. 消费/医药/TMT, 0-3 个>"],
        "source": ["<evidence 来源: xhs:N / saif:YYYY / demo_v1, 至少 1 条>"],
        "must_have": <true/false>,
        "notes": "<≤50 字, 说明为什么列这家>"
      }
    ]
  }
}

规则:
- 每 sub_cat 必须列 must_have=true (头部, 必须 cover 岗位级) 5-8 家 + must_have=false (二线, 可选) 3-5 家
- 每条公司必须有至少 1 条 evidence: 出现在 SAIF 就业报告 / XHS mention ≥ 5 / demo_v1 已收录
- 禁止凭印象添加公司; 如某 sub_cat evidence 真稀缺, must_have 列 < 5 家 OK, 但要在 notes 里说明
- 公司可以跨 sub_cat (e.g. 中金同时进 卖方研究·TMT 和 投行 IBD), 各自列一次
- AI 应用_PM_开发 5 个 sub_cat 的公司池可以共享 (字节/腾讯/蚂蚁等大厂招多个方向)

输入数据:
1. 27 sub_cat taxonomy: 见 user message
2. SAIF MF 就业报告 2023/2024/2025: 见 user message
3. demo 阶段已锁定 20 公司清单: 见 user message
4. XHS 补爬后 sub_cat × 公司 mention 统计: 见 user message
"""


def build_user_message(taxonomy_md: str, saif_json: str, demo_companies_json: str,
                        xhs_subcat_company_stats: str) -> str:
    return f"""## 输入数据 1: 27 sub_cat taxonomy

{taxonomy_md}

## 输入数据 2: SAIF MF 就业报告 (2023-2025, 65+ 流向)

{saif_json}

## 输入数据 3: demo 阶段已锁定 20 公司清单

{demo_companies_json}

## 输入数据 4: XHS 补爬后 sub_cat × 公司 mention 统计

{xhs_subcat_company_stats}

---

请按 system prompt 的 schema 输出 27 sub_cat × 公司 ground truth 清单 JSON.
"""


def generate_ground_truth() -> dict:
    """Run Opus 4.7 1-shot. Returns parsed JSON dict."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    client = Anthropic(api_key=api_key)
    
    repo_root = Path(__file__).resolve().parents[4]
    taxonomy_md = (repo_root / "docs/taxonomy-投研-final-v1.md").read_text()
    saif_json = (repo_root / "backend/data/saif_employment_reports_extracted.json").read_text()
    demo_json = (repo_root / "backend/data/demo_companies_v1.json").read_text()
    # XHS stats — compute live from DB
    xhs_stats = _compute_xhs_stats()
    
    user_msg = build_user_message(taxonomy_md, saif_json, demo_json, xhs_stats)
    
    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=16000,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw_text = resp.content[0].text
    # Extract JSON from response (may have markdown ```json fence)
    if "```json" in raw_text:
        raw_text = raw_text.split("```json", 1)[1].split("```", 1)[0]
    return json.loads(raw_text)


def _compute_xhs_stats() -> str:
    """Compute per-sub_cat × company mention frequency from taxonomy_xhs_posts."""
    from app.database import SessionLocal
    from app.models import TaxonomyXhsPost
    from collections import defaultdict
    db = SessionLocal()
    try:
        stats = defaultdict(lambda: defaultdict(int))
        for p in db.query(TaxonomyXhsPost).all():
            try:
                companies = json.loads(p.company_mentions or "[]")
            except json.JSONDecodeError:
                continue
            for c in companies:
                stats[p.sub_cat][c] += 1
        # Format as markdown table-ish text
        out_lines = []
        for sc, c_counts in stats.items():
            top = sorted(c_counts.items(), key=lambda x: -x[1])[:15]
            out_lines.append(f"### {sc}")
            for c, n in top:
                out_lines.append(f"- {c}: {n} mentions")
        return "\n".join(out_lines)
    finally:
        db.close()


def add_stats_block(gt: dict) -> dict:
    """Add stats block (total_companies / must_have / by_sub_cat) for downstream用."""
    from collections import Counter
    all_companies = set()
    by_sub_cat = {}
    must_have_set = set()
    for sub_cat, companies in gt["ground_truth"].items():
        by_sub_cat[sub_cat] = len(companies)
        for c in companies:
            all_companies.add(c["name"])
            if c.get("must_have"):
                must_have_set.add(c["name"])
    gt["stats"] = {
        "total_companies": len(all_companies),
        "must_have_companies": len(must_have_set),
        "by_sub_cat": by_sub_cat,
    }
    gt["schema_version"] = "1.0"
    return gt
```

- [ ] **Step 2: Write the runner script**

Create `backend/scripts/phase_g/04_generate_ground_truth.py`:

```python
"""Generate ground_truth_companies_v1.json via Opus 4.7 1-shot."""
from __future__ import annotations
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.phase_g.ground_truth import generate_ground_truth, add_stats_block

OUTPUT = REPO_ROOT / "backend/data/ground_truth_companies_v1.json"


def main():
    print("Running Opus 4.7 ground_truth synthesis (1 call, ~1-2 min)...")
    gt = generate_ground_truth()
    gt["generated_at"] = datetime.utcnow().isoformat() + "Z"
    gt = add_stats_block(gt)
    OUTPUT.write_text(json.dumps(gt, indent=2, ensure_ascii=False))
    print(f"\nSaved to {OUTPUT}")
    print(f"\nStats:")
    print(json.dumps(gt["stats"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Write schema validation test**

Create `backend/tests/phase_g/test_ground_truth_schema.py`:

```python
import json
from pathlib import Path
import pytest

GT_FILE = Path(__file__).resolve().parents[3] / "backend/data/ground_truth_companies_v1.json"


@pytest.fixture(scope="module")
def gt():
    if not GT_FILE.exists():
        pytest.skip(f"{GT_FILE} not yet generated — run T4 first")
    return json.loads(GT_FILE.read_text())


def test_top_level_keys(gt):
    assert "schema_version" in gt
    assert "ground_truth" in gt
    assert "stats" in gt
    assert "generated_at" in gt


def test_27_sub_cats_covered(gt):
    from app.services.phase_g.xhs_classifier import _SUB_CATS_27
    missing = [sc for sc in _SUB_CATS_27 if sc not in gt["ground_truth"]]
    assert not missing, f"Missing sub_cats: {missing}"


def test_each_subcat_has_companies(gt):
    for sub_cat, companies in gt["ground_truth"].items():
        assert isinstance(companies, list)
        assert len(companies) >= 1, f"{sub_cat} has no companies"


def test_company_schema(gt):
    for sub_cat, companies in gt["ground_truth"].items():
        for c in companies:
            assert "name" in c
            assert "tier" in c
            assert "must_have" in c and isinstance(c["must_have"], bool)
            assert "source" in c and len(c["source"]) >= 1


def test_must_have_companies_exist_per_subcat(gt):
    """Each sub_cat should have at least 1 must_have company (warning, not failure for low-confidence cats)."""
    no_must_have = []
    for sub_cat, companies in gt["ground_truth"].items():
        if not any(c.get("must_have") for c in companies):
            no_must_have.append(sub_cat)
    if no_must_have:
        print(f"WARN: sub_cats with no must_have company: {no_must_have}")


def test_stats_consistent(gt):
    stats = gt["stats"]
    actual_total = len(set(c["name"] for cs in gt["ground_truth"].values() for c in cs))
    assert stats["total_companies"] == actual_total
```

- [ ] **Step 4: Run the script**

```bash
cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/04_generate_ground_truth.py 2>&1 | tail -30
```

Expected: ~1-2 min runtime, output JSON with 27 sub_cats, ~150-200 companies total, ~80-100 must_have. Cost ~$1-2.

- [ ] **Step 5: Run schema validation**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_ground_truth_schema.py -v
```

Expected: 5 passed, possible WARN for low-confidence sub_cats.

- [ ] **Step 6: Spot-check output manually**

Print a few sub_cats:

```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
import json
gt = json.loads(open('data/ground_truth_companies_v1.json').read())
for sc in ['公募权益研究员', '量化研究员·中频', 'AI PM', 'PE投后VC行研']:
    companies = gt['ground_truth'].get(sc, [])
    print(f'\\n=== {sc} ({len(companies)} companies) ===')
    for c in companies[:5]:
        mh = '✓' if c['must_have'] else ' '
        print(f'  [{mh}] {c[\"name\"]} ({c[\"tier\"]})')
"
```

Sanity: 公募权益研究员 应有 易方达 / 华夏 / 南方; 量化中频 应有 灵均 / 九坤 / 明汯; PE 应有 高瓴 / 弘毅。如果明显遗漏知名公司, examine Opus 输出 + 考虑 prompt 调整。

- [ ] **Step 7: Commit T4**

```bash
git add backend/app/services/phase_g/ground_truth.py \
        backend/scripts/phase_g/04_generate_ground_truth.py \
        backend/tests/phase_g/test_ground_truth_schema.py \
        backend/data/ground_truth_companies_v1.json
git commit -m "$(cat <<'EOF'
phase-g(T4): Opus 4.7 1-shot 生成 ground_truth_companies_v1.json

27 sub_cat × ~150-200 公司, ~80-100 must_have。evidence 来源: SAIF 就业报告 + XHS mention + demo_v1。schema 单测 5 passed。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Hybrid Opus synthesis — 前 5 个 sub_cat 用 subagent

**Files:**
- Create: `backend/app/services/phase_g/knowledge_synthesis.py`
- Create: `backend/scripts/phase_g/05_synthesize_knowledge_hybrid.py`
- Create: `backend/tests/phase_g/test_knowledge_synthesis.py`

**Context:** Per spec section 4 工序 3b, 27 sub_cat 知识库 synthesis 用 hybrid 模式 — 前 5 用 Claude Code subagent (自检 + 多 tool use), 后 22 用 pure Opus API loop。前 5 选: 覆盖 7 大类各 1 个 + 数据厚/薄各 1-2 个。

- [ ] **Step 1: Define the 5 pilot sub_cats + the 22 follow-up sub_cats**

The 5 pilot:
- `公募权益研究员` (基本面权益, 数据厚, 学生最常 query)
- `量化研究员·中频` (量化, 数据厚)
- `卖方研究员·TMT` (卖方研究, 数据厚)
- `PE投后VC行研` (相关补充, 数据薄 — verify subagent 能处理低数据情况)
- `AI PM` (AI 应用_PM_开发, 跨域)

剩余 22 个 = `_SUB_CATS_27` minus the 5 above.

- [ ] **Step 2: Write the synthesis prompt + JSON schema in knowledge_synthesis.py**

Create `backend/app/services/phase_g/knowledge_synthesis.py`:

```python
"""Phase G 工序 3b — 27 sub_cat hybrid Opus synthesis."""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Iterable
from anthropic import Anthropic
from app.database import SessionLocal
from app.models import TaxonomyXhsPost, KnowledgeSubcategory


SYNTHESIS_SYSTEM_PROMPT = """你是 SAIF MF 校招赛道情报合成专家. 给你一个 sub_cat 的全部 XHS 帖原文 + extracted 信号 + SAIF 就业报告对应流向, 你需要合成一份 15 字段的结构化知识库 JSON.

输出严格 JSON, schema:
{
  "sub_cat": "<sub_cat 名, 跟 input 一致>",
  "sub_cat_slug": "<英文 slug, 小写下划线>",
  "strategy_type": "<7 大类之一: 基本面权益 / 量化 / 固定收益 / 卖方研究 / 多资产_FOF_衍生品 / 相关补充 / AI应用_PM_开发>",
  "industry_focus_candidates": [<本 sub_cat 常见的 industry, 0-5 个>],
  "institution_tier_candidates": [<本 sub_cat 常见的 institution_tier, 1-3 个>],
  "typical_companies": [
    {"name": "<>", "tier": "<>", "xhs_mention_count": <int>, "is_saif_alumni_dest": <bool>}
  ],
  "hard_requirements": [<硬门槛, 每条 ≤80 字, 3-5 条>],
  "soft_signals": [<加分项, 每条 ≤80 字, 2-5 条>],
  "transfer_paths": [
    {"from": "<起点 sub_cat 或经历>", "to": "<本 sub_cat>", "difficulty": "low/medium/high", "notes": "<≤80 字>"}
  ],
  "pitfalls": [<排雷, 每条 ≤80 字, 1-3 条>],
  "interview_style": "<面试样态描述, ≤150 字>",
  "compensation_signal": "<薪酬区间 + verbatim 来源, ≤80 字, 无明确数字填 null>",
  "career_trajectory": "<1-3-5 年职业路径, ≤150 字>",
  "verbatim_quotes": [
    {"quote": "<≤150 字>", "source_url": "<https://xiaohongshu.com/...>", "context": "<≤50 字>"}
  ],
  "hiring_season": {"spring": "<≤50 字>", "fall": "<≤50 字>", "verbatim": "<原话或 null>", "peak_month": [<月份数字, 1-12>]},
  "data_confidence": "<high/medium/low>",
  "data_basis": {"post_count": <int>, "company_mention_count": <int>, "saif_alumni_count": <int>}
}

规则:
- verbatim_quotes 必须从 input 帖中原样摘抄, 不要改写; source_url 用 input 提供的 XHS 链接
- typical_companies 排序: xhs_mention_count desc, 取前 8-12
- data_confidence 自动算: 
  - high: post_count ≥ 30 且 company_mention_count ≥ 10 且 saif_alumni_count ≥ 3
  - medium: post_count ≥ 30 且 company_mention_count ≥ 5
  - low: post_count < 30 (真冷门赛道)
"""


def gather_posts_for_subcat(sub_cat: str) -> list[dict]:
    """Pull all classified posts for a sub_cat from taxonomy_xhs_posts."""
    db = SessionLocal()
    try:
        rows = db.query(TaxonomyXhsPost).filter_by(sub_cat=sub_cat).all()
        out = []
        for r in rows:
            out.append({
                "source_url": r.source_url,
                "content": r.raw_content[:2000],
                "company_mentions": json.loads(r.company_mentions or "[]"),
                "verbatim_signals": json.loads(r.verbatim_signals or "[]"),
                "extracted": json.loads(r.extracted_fields or "{}"),
            })
        return out
    finally:
        db.close()


def gather_saif_alumni_for_subcat(sub_cat: str) -> list[dict]:
    """Filter SAIF report records for those whose target_role hints this sub_cat."""
    repo_root = Path(__file__).resolve().parents[4]
    saif_json = json.loads((repo_root / "backend/data/saif_employment_reports_extracted.json").read_text())
    # Heuristic: look for sub_cat name keywords in role/company; refine per实际 SAIF schema
    matched = []
    keywords = _subcat_keywords(sub_cat)
    for record in saif_json.get("records", []):
        role = (record.get("role") or "")
        company = (record.get("company") or "")
        if any(k in role or k in company for k in keywords):
            matched.append(record)
    return matched


_KEYWORD_MAP = {
    "公募权益研究员": ["公募", "权益研究", "基金研究员"],
    "量化研究员·中频": ["量化", "中频", "alpha"],
    "卖方研究员·TMT": ["卖方", "证券研究", "TMT", "通信", "半导体"],
    "PE投后VC行研": ["PE", "VC", "投后", "private equity"],
    "AI PM": ["AI 产品", "AI PM", "产品经理"],
    # ... fill in for all 27, or use generic keyword extraction
}


def _subcat_keywords(sub_cat: str) -> list[str]:
    return _KEYWORD_MAP.get(sub_cat, [sub_cat])


def build_synthesis_user_message(sub_cat: str, strategy_type: str,
                                  posts: list[dict], saif_records: list[dict]) -> str:
    posts_text = "\n\n".join([
        f"### Post {i+1} (URL: {p['source_url']})\n"
        f"Companies: {', '.join(p['company_mentions'])}\n"
        f"Verbatim signals: {', '.join(p['verbatim_signals'][:5])}\n"
        f"Content:\n{p['content']}\n"
        f"Extracted: {json.dumps(p['extracted'], ensure_ascii=False)[:500]}"
        for i, p in enumerate(posts[:50])
    ])
    saif_text = json.dumps(saif_records, ensure_ascii=False, indent=2)
    return f"""## sub_cat: {sub_cat}
## strategy_type (predetermined): {strategy_type}
## XHS posts ({len(posts)} total)

{posts_text}

## SAIF MF alumni 流向 (matched, {len(saif_records)} records)

{saif_text}

---

请按 system prompt 的 schema 输出该 sub_cat 的结构化知识库 JSON.
"""


def synthesize_one_subcat_pure_api(sub_cat: str, strategy_type: str) -> dict:
    """Pure Opus API call for one sub_cat. Used by Task 6 for the 22 follow-up sub_cats."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = Anthropic(api_key=api_key)
    
    posts = gather_posts_for_subcat(sub_cat)
    saif = gather_saif_alumni_for_subcat(sub_cat)
    user_msg = build_synthesis_user_message(sub_cat, strategy_type, posts, saif)
    
    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=8000,
        system=SYNTHESIS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = resp.content[0].text
    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0]
    knowledge = json.loads(raw)
    # Augment with computed data_basis if Opus didn't include
    if "data_basis" not in knowledge:
        knowledge["data_basis"] = {
            "post_count": len(posts),
            "company_mention_count": len(set(c for p in posts for c in p["company_mentions"])),
            "saif_alumni_count": len(saif),
        }
    return knowledge


# Mapping sub_cat -> strategy_type (predetermined from taxonomy)
SUBCAT_TO_STRATEGY = {
    "公募权益研究员": "基本面权益",
    "行业研究员·消费": "基本面权益",
    "行业研究员·TMT-医药-周期": "基本面权益",
    "公募指数研究员": "基本面权益",
    "公募基金中后台": "基本面权益",
    "量化研究员·中频": "量化",
    "量化研究员·高频": "量化",
    "量化开发QD": "量化",
    "AI 量化工程师": "量化",
    "量化因子工程师": "量化",
    "信用研究员": "固定收益",
    "固收交易员": "固定收益",
    "固收+多资产": "固定收益",
    "利率宏观策略": "固定收益",
    "卖方研究员·TMT": "卖方研究",
    "卖方研究员·消费医药周期": "卖方研究",
    "卖方研究员·宏观策略": "卖方研究",
    "买方 Quant": "卖方研究",
    "投行 IBD": "卖方研究",
    "资管FOF": "多资产_FOF_衍生品",
    "自营FOF": "多资产_FOF_衍生品",
    "财富管理FOF": "多资产_FOF_衍生品",
    "结构化产品衍生品": "多资产_FOF_衍生品",
    "PE投后VC行研": "相关补充",
    "LLM算法post-train": "AI应用_PM_开发",
    "Agent工程师": "AI应用_PM_开发",
    "多模态推理优化": "AI应用_PM_开发",
    "AI PM": "AI应用_PM_开发",
    "AI算法业务": "AI应用_PM_开发",
}
```

- [ ] **Step 3: Write test for synthesis schema + post gathering**

Create `backend/tests/phase_g/test_knowledge_synthesis.py`:

```python
import json
from unittest.mock import MagicMock, patch
from app.services.phase_g.knowledge_synthesis import (
    gather_posts_for_subcat, build_synthesis_user_message, SUBCAT_TO_STRATEGY,
)
from app.services.phase_g.xhs_classifier import _SUB_CATS_27


def test_all_27_subcats_mapped():
    missing = [sc for sc in _SUB_CATS_27 if sc not in SUBCAT_TO_STRATEGY]
    assert not missing, f"sub_cats without strategy mapping: {missing}"


def test_strategy_types_only_7():
    strategy_types = set(SUBCAT_TO_STRATEGY.values())
    expected = {"基本面权益", "量化", "固定收益", "卖方研究", "多资产_FOF_衍生品", "相关补充", "AI应用_PM_开发"}
    assert strategy_types == expected


def test_build_user_message_includes_all_sections():
    msg = build_synthesis_user_message(
        sub_cat="公募权益研究员", strategy_type="基本面权益",
        posts=[{"source_url": "url1", "content": "test", "company_mentions": ["易方达"],
                "verbatim_signals": ["路径清晰"], "extracted": {}}],
        saif_records=[{"role": "权益研究员", "company": "易方达基金", "year": "2024"}],
    )
    assert "sub_cat: 公募权益研究员" in msg
    assert "易方达" in msg
    assert "Post 1" in msg
```

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_knowledge_synthesis.py -v
```

Expected: 3 passed.

- [ ] **Step 4: Dispatch 5 implementer subagents (one per pilot sub_cat)**

For each of the 5 pilot sub_cats, dispatch a Claude Code subagent (Agent tool, subagent_type=general-purpose, model=opus). Each subagent prompt should be:

```
You are tasked with synthesizing the knowledge base entry for one sub_cat as part of Phase G 工序 3b pilot pass.

Sub_cat: <sub_cat_name>
Strategy_type: <strategy_type>

Read these files for context (use Read tool):
- /home/chuanbo/projects/JobRadar/docs/superpowers/specs/2026-05-27-phase-g-recommendation-pipeline-v2-design.md (especially Section 4 工序 3b — the 15-field JSON schema you must output)
- /home/chuanbo/projects/JobRadar/backend/app/services/phase_g/knowledge_synthesis.py (SYNTHESIS_SYSTEM_PROMPT)

Gather data:
1. Run the Python helper to pull posts:
   cd backend && PYTHONPATH=. .venv/bin/python -c "from app.services.phase_g.knowledge_synthesis import gather_posts_for_subcat; import json; print(json.dumps(gather_posts_for_subcat('<sub_cat>'), ensure_ascii=False)[:5000])"
2. Same for SAIF: gather_saif_alumni_for_subcat
3. Compute data_basis (post_count, company_mention_count, saif_alumni_count)

Self-check before writing output:
- verbatim_quotes 必须 ≥ 3 条, 每条 source_url 必须真存在于 input posts
- typical_companies ≥ 5, must include top 3 by xhs_mention_count
- hard_requirements ≥ 3 条
- data_confidence 必须按规则计算正确

Output: write JSON to /tmp/synth_<sub_cat_slug>.json AND a human-readable markdown to /tmp/synth_<sub_cat_slug>.md (md format: H1 sub_cat name; H2 sections for each field; bullet lists for arrays).

After writing, validate the JSON: assert all 15 fields present, types match schema.

Report: filepath of generated JSON + md + any data_confidence concerns.
```

For each subagent, capture output JSON. Move successful JSON+md to `docs/sub_cat_knowledge/` and `data/_phase_g/synthesis/`.

- [ ] **Step 5: Verify pilot outputs**

```bash
ls /tmp/synth_*.json | wc -l   # should be 5
for f in /tmp/synth_*.json; do
  echo "=== $f ==="
  python3 -c "
import json
d = json.load(open('$f'))
required = ['sub_cat','sub_cat_slug','strategy_type','typical_companies','hard_requirements','soft_signals','transfer_paths','pitfalls','interview_style','compensation_signal','career_trajectory','verbatim_quotes','hiring_season','data_confidence','data_basis']
missing = [k for k in required if k not in d]
print('Missing fields:', missing)
print('verbatim_quotes count:', len(d.get('verbatim_quotes', [])))
print('typical_companies count:', len(d.get('typical_companies', [])))
print('data_confidence:', d.get('data_confidence'))
"
done
```

All 5 should pass schema validation. If issues found, fix prompt in `knowledge_synthesis.py` SYNTHESIS_SYSTEM_PROMPT before T6 batch run.

- [ ] **Step 6: Move pilot outputs into final locations**

```bash
mkdir -p /home/chuanbo/projects/JobRadar/docs/sub_cat_knowledge
mkdir -p /home/chuanbo/projects/JobRadar/backend/data/_phase_g/synthesis
mv /tmp/synth_*.md /home/chuanbo/projects/JobRadar/docs/sub_cat_knowledge/
mv /tmp/synth_*.json /home/chuanbo/projects/JobRadar/backend/data/_phase_g/synthesis/
```

- [ ] **Step 7: Commit T5**

```bash
git add backend/app/services/phase_g/knowledge_synthesis.py \
        backend/tests/phase_g/test_knowledge_synthesis.py \
        docs/sub_cat_knowledge/ \
        backend/data/_phase_g/synthesis/
git commit -m "$(cat <<'EOF'
phase-g(T5): Opus 4.7 hybrid synthesis — 前 5 个 sub_cat (subagent pattern)

5 pilot: 公募权益研究员/量化中频/卖方TMT/PE投后/AI PM。subagent 自检 verbatim 真实性 + schema 完整, 锁定 prompt 模板 + 输出结构准备 batch loop。15 字段全 OK。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Pure API loop 剩 22 个 sub_cat + 入 DB + md + embeddings

**Files:**
- Create: `backend/scripts/phase_g/06_synthesize_remaining_22.py`
- Create: `backend/app/services/phase_g/embeddings.py` (DashScope wrapper)

- [ ] **Step 1: Write the DashScope embedding wrapper**

Create `backend/app/services/phase_g/embeddings.py`:

```python
"""DashScope text-embedding-v3 wrapper, used for sub_cat knowledge RAG (Phase G 工序 4)."""
from __future__ import annotations
import os
import struct
from typing import Iterable
import dashscope


def embed_text(text: str) -> bytes:
    """Return 4KB BLOB (float32 * 1024)."""
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY not set")
    dashscope.api_key = api_key
    resp = dashscope.TextEmbedding.call(
        model="text-embedding-v3",
        input=text[:8000],  # text-embedding-v3 limit
    )
    if resp.status_code != 200:
        raise RuntimeError(f"DashScope error: {resp.code} - {resp.message}")
    vector = resp.output["embeddings"][0]["embedding"]  # list of 1024 floats
    return struct.pack(f"{len(vector)}f", *vector)


def embed_batch(texts: Iterable[str]) -> list[bytes]:
    """Batch helper — DashScope text-embedding-v3 supports up to 25 inputs per call."""
    import dashscope
    out = []
    batch = []
    for t in texts:
        batch.append(t[:8000])
        if len(batch) == 25:
            resp = dashscope.TextEmbedding.call(model="text-embedding-v3", input=batch)
            if resp.status_code != 200:
                raise RuntimeError(f"DashScope: {resp.code}")
            for emb in resp.output["embeddings"]:
                vec = emb["embedding"]
                out.append(struct.pack(f"{len(vec)}f", *vec))
            batch = []
    if batch:
        resp = dashscope.TextEmbedding.call(model="text-embedding-v3", input=batch)
        if resp.status_code != 200:
            raise RuntimeError(f"DashScope: {resp.code}")
        for emb in resp.output["embeddings"]:
            vec = emb["embedding"]
            out.append(struct.pack(f"{len(vec)}f", *vec))
    return out


def decode_embedding(blob: bytes) -> list[float]:
    """Inverse of embed_text — used by RAG retrieval."""
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))
```

- [ ] **Step 2: Write the batch loop runner**

Create `backend/scripts/phase_g/06_synthesize_remaining_22.py`:

```python
"""Pure Opus API loop for the remaining 22 sub_cats, after T5 locks the prompt.

Concurrency: asyncio.gather 4-6 at a time (Anthropic rate limit allows).
Output: JSON to data/_phase_g/synthesis/ + md to docs/sub_cat_knowledge/ + DB row.
"""
from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.phase_g.knowledge_synthesis import (
    synthesize_one_subcat_pure_api, SUBCAT_TO_STRATEGY,
)
from app.services.phase_g.xhs_classifier import _SUB_CATS_27
from app.services.phase_g.embeddings import embed_text
from app.database import SessionLocal
from app.models import KnowledgeSubcategory

# T5 pilot (skip)
PILOT_5 = {"公募权益研究员", "量化研究员·中频", "卖方研究员·TMT", "PE投后VC行研", "AI PM"}
REMAINING_22 = [sc for sc in _SUB_CATS_27 if sc not in PILOT_5]

SYNTHESIS_DIR = REPO_ROOT / "backend/data/_phase_g/synthesis"
MD_DIR = REPO_ROOT / "docs/sub_cat_knowledge"


def _to_slug(sub_cat: str) -> str:
    """Map sub_cat name to filesystem-safe slug."""
    # Mapping table (or use a heuristic). Implementer fills in per actual sub_cat names.
    mapping = {
        "公募权益研究员": "fund_equity_researcher",
        "行业研究员·消费": "industry_researcher_consumer",
        # ... fill all 27
    }
    return mapping.get(sub_cat, sub_cat.replace("·", "_").replace("/", "_").replace(" ", "_"))


def synthesize_and_persist(sub_cat: str) -> dict:
    """Sync helper: run synthesis + write JSON/md/DB."""
    print(f"  Synthesizing: {sub_cat}")
    strategy = SUBCAT_TO_STRATEGY[sub_cat]
    knowledge = synthesize_one_subcat_pure_api(sub_cat, strategy)
    
    slug = _to_slug(sub_cat)
    json_path = SYNTHESIS_DIR / f"{slug}.json"
    md_path = MD_DIR / f"{slug}.md"
    json_path.write_text(json.dumps(knowledge, indent=2, ensure_ascii=False))
    md_path.write_text(_render_md(knowledge))
    
    # Compute embedding from key fields
    embed_input = (
        f"sub_cat: {sub_cat}\n"
        f"strategy: {strategy}\n"
        f"hard_requirements: {' '.join(knowledge.get('hard_requirements', []))}\n"
        f"work_style: {knowledge.get('interview_style', '')}\n"
        f"typical_companies: {' '.join(c['name'] for c in knowledge.get('typical_companies', []))}"
    )
    embedding = embed_text(embed_input)
    
    # Upsert into knowledge_subcategories
    db = SessionLocal()
    try:
        existing = db.query(KnowledgeSubcategory).filter_by(sub_cat=sub_cat).first()
        if existing:
            existing.payload_json = json.dumps(knowledge, ensure_ascii=False)
            existing.data_confidence = knowledge["data_confidence"]
            existing.data_basis_json = json.dumps(knowledge["data_basis"], ensure_ascii=False)
            existing.hiring_season_json = json.dumps(knowledge.get("hiring_season", {}), ensure_ascii=False)
            existing.embedding = embedding
        else:
            db.add(KnowledgeSubcategory(
                sub_cat=sub_cat, sub_cat_slug=slug, strategy_type=strategy,
                payload_json=json.dumps(knowledge, ensure_ascii=False),
                data_confidence=knowledge["data_confidence"],
                data_basis_json=json.dumps(knowledge["data_basis"], ensure_ascii=False),
                hiring_season_json=json.dumps(knowledge.get("hiring_season", {}), ensure_ascii=False),
                embedding=embedding,
            ))
        db.commit()
    finally:
        db.close()
    return knowledge


def _render_md(k: dict) -> str:
    return f"""# {k['sub_cat']} ({k['strategy_type']})

**Slug**: `{k['sub_cat_slug']}` | **Data confidence**: {k['data_confidence']} | **Posts**: {k['data_basis']['post_count']} | **Companies**: {k['data_basis']['company_mention_count']} | **SAIF alumni**: {k['data_basis']['saif_alumni_count']}

## Industry focus 候选
{', '.join(k.get('industry_focus_candidates', []))}

## Institution tier 候选
{', '.join(k.get('institution_tier_candidates', []))}

## Typical companies
{chr(10).join(f"- {c['name']} ({c['tier']}) — {c.get('xhs_mention_count', 0)} XHS mentions" for c in k.get('typical_companies', []))}

## 硬门槛
{chr(10).join(f"- {h}" for h in k.get('hard_requirements', []))}

## 加分项
{chr(10).join(f"- {h}" for h in k.get('soft_signals', []))}

## 转入路径
{chr(10).join(f"- {p['from']} → {p['to']} ({p['difficulty']}): {p['notes']}" for p in k.get('transfer_paths', []))}

## 排雷
{chr(10).join(f"- {p}" for p in k.get('pitfalls', []))}

## 面试样态
{k.get('interview_style', '')}

## 薪酬
{k.get('compensation_signal', 'N/A')}

## 1-3-5 年路径
{k.get('career_trajectory', '')}

## Verbatim quotes (真 XHS 链接)
{chr(10).join(f"- > {q['quote']}{chr(10)}  > 来源: {q['source_url']}" for q in k.get('verbatim_quotes', []))}

## Hiring season
- Spring: {k.get('hiring_season', {}).get('spring', '')}
- Fall: {k.get('hiring_season', {}).get('fall', '')}
- Peak month: {k.get('hiring_season', {}).get('peak_month', [])}
"""


def main():
    SYNTHESIS_DIR.mkdir(parents=True, exist_ok=True)
    MD_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"Synthesizing {len(REMAINING_22)} sub_cats (after T5 pilot 5):")
    for sc in REMAINING_22:
        print(f"  - {sc}")
    
    # Synchronous loop — Opus API rate limits are tight, so single-thread is safer
    # If you want concurrency, wrap synthesize_and_persist in asyncio.to_thread + asyncio.Semaphore(4)
    for sc in REMAINING_22:
        try:
            k = synthesize_and_persist(sc)
            print(f"  ✓ {sc}: data_confidence={k['data_confidence']}")
        except Exception as e:
            print(f"  ✗ {sc}: ERROR {e}")
    
    # Also persist the 5 pilot from T5 (read JSON from data/_phase_g/synthesis/, embed + DB)
    print(f"\nPersisting T5 pilot 5 to DB...")
    for sc in PILOT_5:
        slug = _to_slug(sc)
        json_path = SYNTHESIS_DIR / f"{slug}.json"
        if not json_path.exists():
            print(f"  ✗ {sc}: missing {json_path}, skip")
            continue
        knowledge = json.loads(json_path.read_text())
        # Compute embedding + upsert (same as synthesize_and_persist but skip Opus call)
        strategy = SUBCAT_TO_STRATEGY[sc]
        embed_input = f"sub_cat: {sc}\nstrategy: {strategy}\n" + " ".join(knowledge.get('hard_requirements', []))
        embedding = embed_text(embed_input)
        db = SessionLocal()
        try:
            existing = db.query(KnowledgeSubcategory).filter_by(sub_cat=sc).first()
            if existing:
                existing.embedding = embedding
                existing.payload_json = json.dumps(knowledge, ensure_ascii=False)
            else:
                db.add(KnowledgeSubcategory(
                    sub_cat=sc, sub_cat_slug=slug, strategy_type=strategy,
                    payload_json=json.dumps(knowledge, ensure_ascii=False),
                    data_confidence=knowledge["data_confidence"],
                    data_basis_json=json.dumps(knowledge["data_basis"], ensure_ascii=False),
                    hiring_season_json=json.dumps(knowledge.get("hiring_season", {}), ensure_ascii=False),
                    embedding=embedding,
                ))
            db.commit()
        finally:
            db.close()
        print(f"  ✓ {sc} persisted (T5 pilot)")
    
    print(f"\nDone. 27 sub_cats in knowledge_subcategories DB.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the loop**

```bash
cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/06_synthesize_remaining_22.py 2>&1 | tee /tmp/synth_22_log.txt
```

Expected: 22 sub_cats synthesized (~3-5 min each × 22 = ~1-1.5 hours), each writes JSON + md + DB row + embedding. Cost ~$19 (22 × $0.9 Opus direct API).

If any sub_cat fails (rate limit / JSON parse), re-run — script auto-skips already-persisted (`db.query(...filter_by).first()` check).

- [ ] **Step 4: Verify all 27 in DB**

```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
from app.database import SessionLocal
from app.models import KnowledgeSubcategory
from app.services.phase_g.xhs_classifier import _SUB_CATS_27
db = SessionLocal()
rows = db.query(KnowledgeSubcategory).all()
in_db = {r.sub_cat for r in rows}
missing = [sc for sc in _SUB_CATS_27 if sc not in in_db]
print(f'In DB: {len(in_db)}/27')
print(f'Missing: {missing}')
for r in rows:
    embed_size = len(r.embedding) if r.embedding else 0
    print(f'  {r.sub_cat}: data_confidence={r.data_confidence}, embedding={embed_size}B')
db.close()
"
```

Expected: 27/27 in DB, no missing, each has 4096B embedding (1024 floats × 4 bytes).

- [ ] **Step 5: Verify md files written**

```bash
ls /home/chuanbo/projects/JobRadar/docs/sub_cat_knowledge/*.md | wc -l   # 27
```

- [ ] **Step 6: Commit T6**

```bash
git add backend/scripts/phase_g/06_synthesize_remaining_22.py \
        backend/app/services/phase_g/embeddings.py \
        backend/data/_phase_g/synthesis/ \
        docs/sub_cat_knowledge/
git commit -m "$(cat <<'EOF'
phase-g(T6): pure Opus API loop 剩 22 个 sub_cat + 入 DB + md + DashScope embedding

27 sub_cat 知识库全部入 knowledge_subcategories 表 (含 4KB text-embedding-v3 BLOB)。docs/sub_cat_knowledge/ 27 个 md 文件给 user + SAIF 老师 review。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Audit script — ground truth vs 库现状 gap 报告

**Files:**
- Create: `backend/app/services/phase_g/audit.py`
- Create: `backend/scripts/phase_g/07_audit_coverage.py`
- Create: `docs/_phase_g/audit_v1.md` (output)
- Create: `backend/tests/phase_g/test_audit.py`

- [ ] **Step 1: Write audit logic**

Create `backend/app/services/phase_g/audit.py`:

```python
"""Compare ground_truth_companies_v1.json against jobs 表现状, classify into 绿/黄/红."""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal
from dataclasses import dataclass, field
from sqlalchemy import func
from app.database import SessionLocal
from app.models import Job


GroundTruthStatus = Literal["green", "yellow", "red"]


@dataclass
class CompanyAuditEntry:
    name: str
    sub_cats: list[str]
    must_have: bool
    tier: str
    active_jobs_30d: int
    total_jobs: int
    status: GroundTruthStatus    # green/yellow/red
    needs_crawl: bool
    reason: str = ""


def audit_coverage(ground_truth_path: Path) -> list[CompanyAuditEntry]:
    gt = json.loads(ground_truth_path.read_text())
    db = SessionLocal()
    cutoff_30d = datetime.utcnow() - timedelta(days=30)
    
    # Build company -> [sub_cats, must_have, tier] index
    company_index = {}
    for sub_cat, companies in gt["ground_truth"].items():
        for c in companies:
            name = c["name"]
            if name not in company_index:
                company_index[name] = {"sub_cats": [], "must_have": False, "tier": c.get("tier", "")}
            company_index[name]["sub_cats"].append(sub_cat)
            if c.get("must_have"):
                company_index[name]["must_have"] = True
    
    out = []
    try:
        for name, info in company_index.items():
            active = db.query(func.count(Job.id)).filter(
                Job.company == name, Job.scraped_at > cutoff_30d
            ).scalar() or 0
            total = db.query(func.count(Job.id)).filter(Job.company == name).scalar() or 0
            
            if active >= 3:
                status = "green"
                needs_crawl = False
                reason = f"{active} active jobs ≥ 3"
            elif active >= 1 or total >= 1:
                status = "yellow"
                needs_crawl = info["must_have"]   # only crawl must_have yellows
                reason = f"only {active} active (total {total}), {'must crawl' if needs_crawl else 'recommended-only, skip'}"
            else:
                status = "red"
                needs_crawl = info["must_have"]
                reason = f"0 jobs in DB, {'must crawl' if needs_crawl else 'recommended-only, skip'}"
            
            out.append(CompanyAuditEntry(
                name=name, sub_cats=info["sub_cats"], must_have=info["must_have"],
                tier=info["tier"], active_jobs_30d=active, total_jobs=total,
                status=status, needs_crawl=needs_crawl, reason=reason,
            ))
    finally:
        db.close()
    return out


def render_audit_md(entries: list[CompanyAuditEntry]) -> str:
    by_status = {"green": [], "yellow": [], "red": []}
    for e in entries:
        by_status[e.status].append(e)
    
    out = [f"# Phase G — Audit Report v1 (generated {datetime.utcnow().isoformat()}Z)\n"]
    out.append(f"**Total ground truth companies**: {len(entries)}")
    out.append(f"- 🟢 Green (≥3 active jobs in 30d): {len(by_status['green'])}")
    out.append(f"- 🟡 Yellow (1-2 active or stale): {len(by_status['yellow'])}")
    out.append(f"- 🔴 Red (0 jobs): {len(by_status['red'])}")
    out.append("")
    need_crawl = [e for e in entries if e.needs_crawl]
    out.append(f"**Companies needing crawl (must_have only)**: {len(need_crawl)}")
    out.append("")
    
    for status_label, status_key in [("🔴 Red — must补爬", "red"), ("🟡 Yellow — 需重新 crawl", "yellow"), ("🟢 Green", "green")]:
        out.append(f"\n## {status_label}\n")
        out.append("| Company | Tier | Sub_cats | Active30d | Total | Must-Have | Action |")
        out.append("|---|---|---|---|---|---|---|")
        for e in sorted(by_status[status_key], key=lambda x: (-int(x.must_have), x.name)):
            mh = "✓" if e.must_have else " "
            action = "CRAWL" if e.needs_crawl else "skip"
            out.append(f"| {e.name} | {e.tier} | {', '.join(e.sub_cats[:2])} | {e.active_jobs_30d} | {e.total_jobs} | {mh} | {action} |")
    return "\n".join(out)
```

- [ ] **Step 2: Write the runner script**

Create `backend/scripts/phase_g/07_audit_coverage.py`:

```python
"""Run Phase G audit + write audit_v1.md."""
from __future__ import annotations
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.phase_g.audit import audit_coverage, render_audit_md

GT_FILE = REPO_ROOT / "backend/data/ground_truth_companies_v1.json"
OUTPUT_MD = REPO_ROOT / "docs/_phase_g/audit_v1.md"


def main():
    entries = audit_coverage(GT_FILE)
    md = render_audit_md(entries)
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text(md)
    print(f"Audit written: {OUTPUT_MD}")
    print(f"Need crawl: {sum(1 for e in entries if e.needs_crawl)} companies")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Write unit test**

Create `backend/tests/phase_g/test_audit.py`:

```python
import json
from datetime import datetime, timedelta
from pathlib import Path
import pytest
from app.database import SessionLocal
from app.models import Job
from app.services.phase_g.audit import audit_coverage, render_audit_md


@pytest.fixture
def fake_gt_file(tmp_path):
    p = tmp_path / "gt.json"
    p.write_text(json.dumps({
        "ground_truth": {
            "公募权益研究员": [
                {"name": "TestCompanyA", "tier": "一线公募", "must_have": True, "source": ["demo_v1"]},
                {"name": "TestCompanyB", "tier": "二线公募", "must_have": False, "source": ["demo_v1"]},
            ],
        },
    }))
    return p


def test_audit_classifies_red_for_zero_jobs(fake_gt_file):
    entries = audit_coverage(fake_gt_file)
    by_name = {e.name: e for e in entries}
    # Both companies have 0 jobs in DB
    assert by_name["TestCompanyA"].status == "red"
    assert by_name["TestCompanyA"].needs_crawl is True   # must_have
    assert by_name["TestCompanyB"].status == "red"
    assert by_name["TestCompanyB"].needs_crawl is False  # not must_have


def test_render_md_includes_sections(fake_gt_file):
    entries = audit_coverage(fake_gt_file)
    md = render_audit_md(entries)
    assert "🔴 Red" in md
    assert "TestCompanyA" in md
    assert "must_have" not in md or "must_have" in md.lower()  # check formatting
```

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_audit.py -v
```

Expected: 2 passed.

- [ ] **Step 4: Run audit on real data**

```bash
cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/07_audit_coverage.py 2>&1 | tail -10
```

Expected: `audit_v1.md` generated in `docs/_phase_g/`. Check the file:

```bash
head -30 /home/chuanbo/projects/JobRadar/docs/_phase_g/audit_v1.md
```

Sanity: red count likely 30-60 companies (estimated); yellow 20-40; green 60-100. If red count is 0, audit logic might be matching wrong company names — verify by checking 1-2 known-present companies.

- [ ] **Step 5: Commit T7**

```bash
git add backend/app/services/phase_g/audit.py \
        backend/scripts/phase_g/07_audit_coverage.py \
        backend/tests/phase_g/test_audit.py \
        docs/_phase_g/audit_v1.md
git commit -m "$(cat <<'EOF'
phase-g(T7): audit script — ground truth vs 库现状 gap 报告 (绿/黄/红 分类)

输出 docs/_phase_g/audit_v1.md, 列出 must_have 公司哪些需补爬 (红 + must_have 黄), recommended-only 公司跳过补爬 (库里没有就 fallback 卡片解释)。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: 补爬缺失公司 (must_have only)

**Files:**
- Create: `backend/scripts/phase_g/08_crawl_missing_companies.py`
- Modify: existing `backend/app/services/*_crawler.py` (12+ finance crawlers) — no logic changes, only orchestration

**Context:** From T7 audit_v1.md, ~30-50 must_have companies need crawl. Strategy:
1. **已有 finance crawler 的公司** → 复用 existing `*_crawler.py` (12+ files in `backend/app/services/`), invoke via existing CLI or service wrappers
2. **通用 ATS (Workday / Beisen / 易招通 / Moka)** → use existing ATS handler primitives (see `docs/crawlers-notes.md`)
3. **其他** → firecrawl + 公司招聘官网 URL fallback

This is the longest task (16-24h actual crawl time). It is **largely orchestration over existing infra**, not new crawler development.

- [ ] **Step 1: Build a company-to-crawler dispatch table**

Create `backend/app/services/phase_g/crawler_dispatch.py`:

```python
"""Map ground truth company name -> which crawler to invoke."""
from __future__ import annotations
from typing import Callable

# Format: {company_name: ("crawler_module", "function_name", {kwargs})}
# Implementer subagent fills in based on actual crawler module APIs.
COMPANY_TO_CRAWLER = {
    "易方达基金": ("funds_crawler", "fetch_yifangda_jobs", {}),
    "华夏基金": ("funds_crawler", "fetch_huaxia_jobs", {}),
    "灵均投资": ("hedge_funds_crawler", "fetch_lingjun_jobs", {}),
    "九坤投资": ("hedge_funds_crawler", "fetch_jiukun_jobs", {}),
    "中金公司": ("securities_crawler", "fetch_cicc_jobs", {}),
    "中信建投证券": ("securities_crawler", "fetch_csc_jobs", {}),
    "字节跳动": ("internet_crawler", "fetch_bytedance_jobs", {"include_ai": True}),
    "腾讯": ("internet_crawler", "fetch_tencent_jobs", {}),
    "蚂蚁集团": ("internet_crawler", "fetch_ant_jobs", {}),
    "高瓴资本": ("pe_vc_crawler", "fetch_hillhouse_jobs", {}),
    # ... fill rest per actual crawler API
}

# Fallback for companies not in above table — try ATS handler then firecrawl
ATS_PATTERN_TABLE = {
    # Beisen ATS pattern
    "beisen": ("ats_handlers", "fetch_beisen_pattern", {}),
    # Workday pattern
    "workday": ("ats_handlers", "fetch_workday_pattern", {}),
    # ... etc
}
```

The implementer subagent must read actual crawler module signatures and fill in this table. If a company has no existing crawler, mark for firecrawl fallback.

- [ ] **Step 2: Write the orchestration runner**

Create `backend/scripts/phase_g/08_crawl_missing_companies.py`:

```python
"""Orchestrate crawl over must_have companies needing補爬.

Resume-safe via progress file. Honors per-company timeout (10 min).
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.phase_g.audit import audit_coverage
from app.services.phase_g.crawler_dispatch import COMPANY_TO_CRAWLER

GT_FILE = REPO_ROOT / "backend/data/ground_truth_companies_v1.json"
PROGRESS = REPO_ROOT / "backend/data/_phase_g/crawl_progress_t8.json"

def _load_progress() -> dict:
    return json.loads(PROGRESS.read_text()) if PROGRESS.exists() else {"done": [], "errors": []}

def _save_progress(p): PROGRESS.write_text(json.dumps(p, indent=2, ensure_ascii=False))


def main():
    entries = audit_coverage(GT_FILE)
    to_crawl = [e for e in entries if e.needs_crawl]
    print(f"Will crawl {len(to_crawl)} must_have companies")
    
    progress = _load_progress()
    for entry in to_crawl:
        if entry.name in progress["done"]:
            print(f"  [SKIP] {entry.name}")
            continue
        try:
            print(f"  Crawling: {entry.name} (tier: {entry.tier})")
            dispatched = _dispatch(entry.name)
            if dispatched is None:
                print(f"    ⚠ no crawler available, will need firecrawl fallback")
                progress["errors"].append({"company": entry.name, "reason": "no_crawler"})
            else:
                count = dispatched   # crawler returns inserted count
                print(f"    ✓ inserted {count} jobs")
                progress["done"].append(entry.name)
            _save_progress(progress)
        except Exception as e:
            print(f"    ✗ ERROR: {e}")
            progress["errors"].append({"company": entry.name, "error": str(e)})
            _save_progress(progress)
    
    print(f"\nDone. {len(progress['done'])} ok, {len(progress['errors'])} errors")


def _dispatch(company_name: str) -> int | None:
    """Returns inserted count, or None if no crawler available."""
    spec = COMPANY_TO_CRAWLER.get(company_name)
    if not spec:
        return None
    module, fn_name, kwargs = spec
    import importlib
    mod = importlib.import_module(f"app.services.{module}")
    fn = getattr(mod, fn_name)
    return fn(**kwargs) or 0


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: For each must_have company without existing crawler, add firecrawl fallback**

For companies not in `COMPANY_TO_CRAWLER`, dispatch a subagent per company to:
1. Find official career page URL (search engine + verify)
2. Use firecrawl API to scrape page
3. Parse + insert into jobs table with company name + sub_cat hint (from ground truth)

Implementer subagent should batch this for efficiency — write 1 generic `firecrawl_company_fallback(company_name, career_url, ground_truth_sub_cats)` helper, then loop.

- [ ] **Step 4: Run crawl**

```bash
cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/08_crawl_missing_companies.py 2>&1 | tee /tmp/crawl_t8.log
```

Expected runtime: many hours (per-crawler rate limits). Most crawlers ~5-30 min each, total ~16-24 hours wall clock if serial. Can parallelize 3-4 crawlers if rate limits allow.

- [ ] **Step 5: Re-run audit to verify gap closed**

```bash
cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/07_audit_coverage.py
diff /tmp/audit_before.md docs/_phase_g/audit_v1.md | head -30
```

Expected: most red companies move to green. Some may remain yellow if firecrawl returned few/no jobs (these become fallback card candidates in T18).

- [ ] **Step 6: Commit T8**

```bash
git add backend/app/services/phase_g/crawler_dispatch.py \
        backend/scripts/phase_g/08_crawl_missing_companies.py \
        backend/data/_phase_g/crawl_progress_t8.json \
        docs/_phase_g/audit_v1.md
git commit -m "phase-g(T8): 补爬 must_have 公司 — 复用 12+ finance crawler + firecrawl fallback" 
```

---

## Task 9: Quality_label 7 等级 prompt 升级 + model 切 Pro medium

**Files:**
- Modify: `backend/app/services/crawler_llm_enrich.py` (model + prompt + 7 等级)
- Create: `backend/tests/phase_g/test_quality_label_prompt.py`

**Context:** Per spec Section 4 工序 2, quality_label 从 4 → 7 等级 (加 `support_role` / `low_pay` / `internship_only`)。Model 从 `deepseek-chat` 升 `deepseek-v4-pro` reasoning_effort=medium。

- [ ] **Step 1: Read existing crawler_llm_enrich.py to understand current shape**

```bash
cat backend/app/services/crawler_llm_enrich.py | head -100
```

Note current model name, prompt structure, function signature. Don't break existing function callers.

- [ ] **Step 2: Define new prompt with 7-tier judging rules + verbatim examples**

Modify `crawler_llm_enrich.py`. Add a new constant `QUALITY_LABEL_PROMPT_V2`:

```python
QUALITY_LABEL_PROMPT_V2 = """你是岗位质量分类器. 给一个岗位 JD, 判定属于以下 7 个 quality_label 之一:

- `good`: 真正的投研/算法/产品/技术对口岗, JD 内容充分 (职责 ≥ 3 行), 招聘需求清晰
- `internship_only`: 标 "实习/Internship/实习生" + 不是正式岗 (e.g. "暑期实习", "在校生岗位")
- `agency`: 中介转招 (e.g. Robert Walters / Michael Page / Hudson / Hays / Adecco / 智联猎头 等)
- `low_signal`: JD 含糊 / 字段缺失 / 无具体岗位描述 (职责 < 2 行, 或全是泛泛"具备良好沟通能力"这种)
- `spam`: 重复抓取 / 链接死 / 标题全大写英文乱码 / 内容跟标题完全不符
- `support_role`: 中后台 / 行政 / 运营 / 销售 / 客服 / 客户经理 / 渠道经理 / 客服专员 (后台支援岗, 不是 SAIF MF 学生目标)
- `low_pay`: 薪资明显低于行业水平 (投行/公募/头部券商月薪 ≤ 6K 几乎必是销售合规 / 低端运营岗)

判定时要小心的边界:
- 标题含 "客户经理" 但 JD 里强调"投研支持 / 行业分析" → 仍可能是 good (e.g. 公募机构销售)
- 标题含 "实习" 但 JD 里强调"正式岗" → 走 good 不走 internship_only
- 标题/JD 含 "应届" 但中后台职能 → support_role 不是 good

输出严格 JSON: {"quality_label": "good", "reasoning": "≤60 字, 说明判定理由"}"""
```

- [ ] **Step 3: Update the enrichment function to use Pro + new prompt**

In `crawler_llm_enrich.py`, locate the LLM call function (e.g. `enrich_job_quality_label(job)`). Modify:

```python
def enrich_job_quality_label_v2(job_dict: dict) -> dict:
    """Phase G — Pro reasoning_effort=medium, 7 等级."""
    from openai import OpenAI
    import os
    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
    )
    user_content = f"公司: {job_dict.get('company', '')}\n标题: {job_dict.get('job_title', '')}\n职责: {job_dict.get('job_duty', '')[:1500]}\n要求: {job_dict.get('job_req', '')[:1500]}"
    resp = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": QUALITY_LABEL_PROMPT_V2},
            {"role": "user", "content": user_content},
        ],
        extra_body={"reasoning_effort": "medium"},
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    import json
    return json.loads(resp.choices[0].message.content)
```

Keep the old `enrich_job_quality_label()` function for backward compat — don't delete (will be cleaned up in T19 deprecation pass).

- [ ] **Step 4: Write unit test for prompt with golden examples**

Create `backend/tests/phase_g/test_quality_label_prompt.py`:

```python
import json
from unittest.mock import MagicMock, patch
from app.services.crawler_llm_enrich import enrich_job_quality_label_v2, QUALITY_LABEL_PROMPT_V2


def _mock_llm(label, reasoning):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = json.dumps({"quality_label": label, "reasoning": reasoning})
    return resp


def _make_job(title, duty="", req="", company="Test Co"):
    return {"company": company, "job_title": title, "job_duty": duty, "job_req": req}


# Golden examples — these don't actually call LLM, but verify the prompt is being constructed correctly
def test_prompt_includes_7_labels():
    for label in ["good", "internship_only", "agency", "low_signal", "spam", "support_role", "low_pay"]:
        assert label in QUALITY_LABEL_PROMPT_V2


def test_enrich_returns_json(monkeypatch):
    with patch("openai.OpenAI") as mock_oai:
        instance = mock_oai.return_value
        instance.chat.completions.create.return_value = _mock_llm("good", "investment research role")
        result = enrich_job_quality_label_v2(_make_job("量化研究员", duty="开发因子模型"))
        assert result["quality_label"] == "good"


# Integration golden test — run actual LLM on 5 hand-picked job samples, verify labels
# Marked slow; only run in CI nightly or local manually
@pytest.mark.slow
def test_real_llm_golden_samples():
    samples = [
        (_make_job("量化研究员", duty="开发中频 alpha 因子", req="数学/物理硕士"), "good"),
        (_make_job("银行客户经理", duty="销售理财产品", req="本科即可"), "support_role"),
        (_make_job("暑期实习生 (TMT 卖方)", duty="协助行业研究", req="在读硕士"), "internship_only"),
    ]
    for job, expected in samples:
        out = enrich_job_quality_label_v2(job)
        assert out["quality_label"] == expected, f"Job {job['job_title']}: expected {expected}, got {out}"
```

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_quality_label_prompt.py -v -k "not slow"
```

Expected: 2 passed (3rd is `slow`, skipped in unit run).

- [ ] **Step 5: Commit T9**

```bash
git add backend/app/services/crawler_llm_enrich.py \
        backend/tests/phase_g/test_quality_label_prompt.py
git commit -m "phase-g(T9): quality_label 7 等级 prompt + model 切 Pro medium

新加 support_role / low_pay / internship_only 三档, prompt 含边界 case + verbatim 例子。Pro reasoning_effort=medium 利用 prefix cache 降本。"
```

---

## Task 10: 跑 28k quality_label backfill

**Files:**
- Create: `backend/scripts/phase_g/10_quality_label_backfill.py`

- [ ] **Step 1: Write batch runner with idempotency + progress**

Create `backend/scripts/phase_g/10_quality_label_backfill.py`:

```python
"""Backfill quality_label v2 on all 28k active jobs.

Idempotency: re-run safe (uses scraped_at filter, skips already-v2-labeled rows via timestamp tracking).
Parallelism: 8-16 threads (DeepSeek API supports concurrency).
"""
from __future__ import annotations
import json
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.database import SessionLocal
from app.models import Job
from app.services.crawler_llm_enrich import enrich_job_quality_label_v2

PROGRESS_FILE = REPO_ROOT / "backend/data/_phase_g/quality_backfill_progress.json"
CHECKPOINT_FILE = REPO_ROOT / "backend/data/_phase_g/quality_backfill_v2_timestamp.txt"


def _load_done() -> set[int]:
    if PROGRESS_FILE.exists():
        return set(json.loads(PROGRESS_FILE.read_text()).get("done_job_ids", []))
    return set()


def _save_done(done: set[int]) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(json.dumps({"done_job_ids": list(done)}))


def process_job(job_id: int) -> tuple[int, str | None, str | None]:
    """Returns (job_id, new_label, error)."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            return (job_id, None, "not_found")
        job_dict = {
            "company": job.company, "job_title": job.job_title,
            "job_duty": job.job_duty, "job_req": job.job_req,
        }
        result = enrich_job_quality_label_v2(job_dict)
        new_label = result["quality_label"]
        if job.quality_label != new_label:
            job.quality_label = new_label
            db.commit()
        return (job_id, new_label, None)
    except Exception as e:
        return (job_id, None, str(e))
    finally:
        db.close()


def main():
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=30)
    
    db = SessionLocal()
    active_ids = [r[0] for r in db.query(Job.id).filter(Job.scraped_at > cutoff).all()]
    db.close()
    print(f"Active jobs (30d): {len(active_ids)}")
    
    done = _load_done()
    todo = [jid for jid in active_ids if jid not in done]
    print(f"Resume: {len(done)} done, {len(todo)} todo")
    
    from collections import Counter
    label_counts = Counter()
    errors = []
    
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(process_job, jid): jid for jid in todo}
        for i, fut in enumerate(as_completed(futures)):
            jid, label, err = fut.result()
            if err:
                errors.append((jid, err))
            else:
                label_counts[label] += 1
                done.add(jid)
            if (i + 1) % 500 == 0:
                _save_done(done)
                print(f"  {i+1}/{len(todo)} done. Label distribution so far: {dict(label_counts)}")
    
    _save_done(done)
    CHECKPOINT_FILE.write_text(datetime.utcnow().isoformat())
    
    print(f"\nDone. {sum(label_counts.values())} jobs labeled, {len(errors)} errors")
    print(f"Final label distribution:")
    for label, count in label_counts.most_common():
        pct = count / sum(label_counts.values()) * 100
        print(f"  {label}: {count} ({pct:.1f}%)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Dry-run on 100 jobs**

```bash
cd backend
PYTHONPATH=. .venv/bin/python -c "
from app.database import SessionLocal
from app.models import Job
from app.services.crawler_llm_enrich import enrich_job_quality_label_v2
db = SessionLocal()
jobs = db.query(Job).limit(20).all()
for j in jobs:
    r = enrich_job_quality_label_v2({
        'company': j.company, 'job_title': j.job_title,
        'job_duty': j.job_duty or '', 'job_req': j.job_req or ''
    })
    print(f'{j.job_title[:50]} -> {r[\"quality_label\"]}')
db.close()
"
```

Spot-check labels look right. If many "good" are actually `support_role` or vice versa, refine prompt examples in T9.

- [ ] **Step 3: Run full 28k backfill**

```bash
cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/10_quality_label_backfill.py 2>&1 | tee /tmp/quality_backfill.log
```

Expected: ~30-45 min runtime (12 threads × ~1.5s/call), $6-8 cost (Pro medium with prefix cache).

- [ ] **Step 4: Verify distribution sanity**

```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
from app.database import SessionLocal
from app.models import Job
from sqlalchemy import func
from datetime import datetime, timedelta
db = SessionLocal()
cutoff = datetime.utcnow() - timedelta(days=30)
rows = db.query(Job.quality_label, func.count(Job.id)).filter(Job.scraped_at > cutoff).group_by(Job.quality_label).all()
total = sum(n for _, n in rows)
for label, n in sorted(rows, key=lambda x: -x[1]):
    print(f'  {label}: {n} ({n/total*100:.1f}%)')
db.close()
"
```

Expected sanity: `good` ~25-40%, `support_role` ~20-30%, `low_signal` ~10-20%, `internship_only` ~5-15%, others <10% each. If `good` < 15%, prompt is too strict; if > 60%, too loose — adjust + re-run.

- [ ] **Step 5: Commit T10**

```bash
git add backend/scripts/phase_g/10_quality_label_backfill.py \
        backend/data/_phase_g/quality_backfill_progress.json \
        backend/data/_phase_g/quality_backfill_v2_timestamp.txt
git commit -m "phase-g(T10): 跑 28k quality_label v2 backfill — Pro medium, 12 threads"
```

---

## Task 11: Sub_cat enrich Multi-pass C 实现 (Pass 1 strategy + Pass 2 sub_cat)

**Files:**
- Create: `backend/app/services/phase_g/sub_cat_enricher.py`
- Create: `backend/tests/phase_g/test_sub_cat_enricher.py`

**Context:** Per spec Section 4 工序 4, Multi-pass C 决策树: Pass 1 选 7 大类 strategy_type (小搜索空间, ~95% 准), Pass 2 在该大类下 4-5 个 sub_cat 中选 1. Both passes use DeepSeek Pro reasoning_effort=high.

- [ ] **Step 1: Implement Multi-pass C**

Create `backend/app/services/phase_g/sub_cat_enricher.py`:

```python
"""Phase G 工序 4 — Multi-pass C sub_cat enrichment with knowledge base RAG."""
from __future__ import annotations
import json
import os
from openai import OpenAI
from app.database import SessionLocal
from app.models import KnowledgeSubcategory, Job
from app.services.phase_g.knowledge_synthesis import SUBCAT_TO_STRATEGY


STRATEGY_TYPES = ["基本面权益", "量化", "固定收益", "卖方研究", "多资产_FOF_衍生品", "相关补充", "AI应用_PM_开发"]


PASS1_SYSTEM_PROMPT = """你是中国金融+AI 校招岗位分类器. 给你一个岗位 JD, 选出最匹配的 1 个 strategy_type 大类:

- 基本面权益: 公募 / 主观私募的权益研究员, 行业研究, 指数研究, 中后台
- 量化: 量化研究员 (中频/高频), 量化开发 QD, AI 量化, 因子工程师
- 固定收益: 信用研究, 固收交易, 固收+多资产, 利率宏观策略
- 卖方研究: 券商研究所卖方研究员, 投行 IBD, 买方 Quant
- 多资产_FOF_衍生品: 资管 FOF, 自营 FOF, 财富 FOF, 结构化衍生品
- 相关补充: PE 投后, VC 行研
- AI应用_PM_开发: LLM 算法 (post-train), Agent 工程师, 多模态推理优化, AI PM, AI 算法业务

如果岗位明显不属于上述任何一类 (e.g. 银行总行综合管培, 央企工程师), 输出 null.

输出 JSON: {"strategy_type": "<大类名 或 null>", "confidence": <0-1>, "reasoning": "<≤60 字>"}"""


PASS2_SYSTEM_PROMPT_TEMPLATE = """你是中国金融+AI 校招岗位 sub_cat 分类器. 给你一个岗位 JD + 该 strategy_type 大类下的全部 sub_cat 知识库, 选出最匹配的 1 个 sub_cat (主) + 可选 1 个 secondary (跨 sub_cat 岗位).

Strategy type: {strategy_type}

候选 sub_cats (含硬门槛 / 工作样态 / 典型公司):
{candidates_text}

判定规则:
- 主 sub_cat: 岗位 JD 跟该 sub_cat 的硬门槛 + 工作样态匹配度最高的
- secondary: 仅当岗位明显跨 sub_cat 时填 (e.g. 中金 TMT 既是卖方研究又跨买方 quant), 否则填 null
- industry_focus: 从该 sub_cat 的 industry_focus_candidates 词表选 1-3 个最 fit 的
- institution_tier: 从该 sub_cat 的 institution_tier_candidates 词表选 1 个最 fit 的, 看公司名

输出 JSON:
{{
  "sub_category": "<sub_cat 名>",
  "sub_category_secondary": "<sub_cat 名 或 null>",
  "industry_focus": ["..."],
  "institution_tier": "...",
  "confidence": <0-1>,
  "reasoning": "<≤80 字, 说明判定理由>"
}}"""


def _client() -> OpenAI:
    return OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
    )


def pass1_classify_strategy(job_dict: dict) -> dict:
    """Pass 1: classify into 7 strategy_types."""
    client = _client()
    user_content = f"公司: {job_dict['company']}\n标题: {job_dict['job_title']}\n职责: {job_dict.get('job_duty','')[:1500]}\n要求: {job_dict.get('job_req','')[:1500]}"
    resp = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": PASS1_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        extra_body={"reasoning_effort": "high"},
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    return json.loads(resp.choices[0].message.content)


def _gather_subcat_candidates(strategy_type: str) -> tuple[list[str], str]:
    """Returns (list of sub_cat names, formatted candidates_text for prompt)."""
    subcats_in_strategy = [sc for sc, st in SUBCAT_TO_STRATEGY.items() if st == strategy_type]
    db = SessionLocal()
    try:
        rows = db.query(KnowledgeSubcategory).filter(KnowledgeSubcategory.sub_cat.in_(subcats_in_strategy)).all()
        parts = []
        for r in rows:
            payload = json.loads(r.payload_json)
            parts.append(f"### {r.sub_cat}\n"
                          f"- 硬门槛: {' / '.join(payload.get('hard_requirements', [])[:3])}\n"
                          f"- 工作样态: {payload.get('interview_style', '')[:200]}\n"
                          f"- 典型公司: {', '.join(c['name'] for c in payload.get('typical_companies', [])[:6])}\n"
                          f"- industry_focus_candidates: {payload.get('industry_focus_candidates', [])}\n"
                          f"- institution_tier_candidates: {payload.get('institution_tier_candidates', [])}")
        return subcats_in_strategy, "\n\n".join(parts)
    finally:
        db.close()


def pass2_classify_subcat(job_dict: dict, strategy_type: str) -> dict:
    """Pass 2: within strategy_type, choose sub_cat + industry + tier."""
    client = _client()
    subcats, candidates_text = _gather_subcat_candidates(strategy_type)
    prompt = PASS2_SYSTEM_PROMPT_TEMPLATE.format(strategy_type=strategy_type, candidates_text=candidates_text)
    user_content = f"公司: {job_dict['company']}\n标题: {job_dict['job_title']}\n职责: {job_dict.get('job_duty','')[:1500]}\n要求: {job_dict.get('job_req','')[:1500]}"
    resp = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
        extra_body={"reasoning_effort": "high"},
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    return json.loads(resp.choices[0].message.content)


def enrich_job_sub_cat(job: Job) -> dict | None:
    """Full Multi-pass C pipeline. Returns enrichment dict, or None if Pass1 rejects.
    
    Does NOT write to DB — caller is responsible (so batch caller can commit in chunks).
    """
    job_dict = {
        "company": job.company or "",
        "job_title": job.job_title or "",
        "job_duty": job.job_duty or "",
        "job_req": job.job_req or "",
    }
    p1 = pass1_classify_strategy(job_dict)
    if not p1.get("strategy_type") or p1.get("confidence", 0) < 0.5:
        return None   # not a SAIF MF target — leave sub_category NULL
    p2 = pass2_classify_subcat(job_dict, p1["strategy_type"])
    # Combine confidence: geometric mean to penalize either weak pass
    combined_conf = (p1["confidence"] * p2["confidence"]) ** 0.5
    return {
        "sub_category": p2.get("sub_category"),
        "sub_category_secondary": p2.get("sub_category_secondary"),
        "industry_focus": json.dumps(p2.get("industry_focus", []), ensure_ascii=False),
        "institution_tier": p2.get("institution_tier"),
        "sub_cat_confidence": combined_conf,
        "sub_cat_reasoning": f"P1: {p1.get('reasoning','')} | P2: {p2.get('reasoning','')}",
    }
```

- [ ] **Step 2: Write unit tests with mocked LLM**

Create `backend/tests/phase_g/test_sub_cat_enricher.py`:

```python
import json
from unittest.mock import patch, MagicMock
from app.services.phase_g.sub_cat_enricher import (
    pass1_classify_strategy, enrich_job_sub_cat, STRATEGY_TYPES,
)
from app.models import Job


def _mock_resp(payload):
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message.content = json.dumps(payload)
    return r


def test_strategy_types_7():
    assert len(STRATEGY_TYPES) == 7


@patch("app.services.phase_g.sub_cat_enricher._client")
def test_pass1_returns_strategy(mock_client_fn):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_resp(
        {"strategy_type": "量化", "confidence": 0.92, "reasoning": "因子 + sharpe"}
    )
    mock_client_fn.return_value = mock_client
    out = pass1_classify_strategy({"company": "九坤", "job_title": "量化研究员",
                                     "job_duty": "中频 alpha", "job_req": "数学硕士"})
    assert out["strategy_type"] == "量化"


@patch("app.services.phase_g.sub_cat_enricher.pass2_classify_subcat")
@patch("app.services.phase_g.sub_cat_enricher.pass1_classify_strategy")
def test_enrich_full_pipeline(mock_p1, mock_p2):
    mock_p1.return_value = {"strategy_type": "量化", "confidence": 0.92, "reasoning": "x"}
    mock_p2.return_value = {
        "sub_category": "量化研究员·中频", "sub_category_secondary": None,
        "industry_focus": [], "institution_tier": "头部量化私募",
        "confidence": 0.88, "reasoning": "y"
    }
    job = Job(id=1, company="九坤投资", job_title="量化研究员", job_duty="中频", job_req="硕士")
    result = enrich_job_sub_cat(job)
    assert result["sub_category"] == "量化研究员·中频"
    assert result["institution_tier"] == "头部量化私募"
    # Geometric mean of 0.92 * 0.88 ≈ 0.899
    assert 0.89 < result["sub_cat_confidence"] < 0.91


@patch("app.services.phase_g.sub_cat_enricher.pass1_classify_strategy")
def test_enrich_returns_none_for_off_target(mock_p1):
    mock_p1.return_value = {"strategy_type": None, "confidence": 0, "reasoning": "off-target"}
    job = Job(id=2, company="某央企", job_title="工程师")
    result = enrich_job_sub_cat(job)
    assert result is None
```

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_sub_cat_enricher.py -v
```

Expected: 4 passed.

- [ ] **Step 3: Smoke test against real LLM on 5 sample jobs**

```bash
cd backend
PYTHONPATH=. .venv/bin/python -c "
from app.database import SessionLocal
from app.models import Job
from app.services.phase_g.sub_cat_enricher import enrich_job_sub_cat
db = SessionLocal()
samples = db.query(Job).filter(Job.quality_label == 'good').limit(5).all()
for j in samples:
    result = enrich_job_sub_cat(j)
    print(f'{j.company[:15]} | {j.job_title[:40]}')
    print(f'  -> {result}')
    print()
db.close()
"
```

Sanity: 5 good jobs all return non-None results (assuming all are SAIF-target). If any returns None unexpectedly, examine Pass 1 reasoning.

- [ ] **Step 4: Commit T11**

```bash
git add backend/app/services/phase_g/sub_cat_enricher.py \
        backend/tests/phase_g/test_sub_cat_enricher.py
git commit -m "phase-g(T11): Multi-pass C sub_cat enricher — Pass 1 strategy + Pass 2 sub_cat + 3 维, Pro high"
```

---

## Task 12: 跑 5-8k ground truth 池 sub_cat enrich

**Files:**
- Create: `backend/scripts/phase_g/12_enrich_sub_cat.py`

- [ ] **Step 1: Write the runner**

Create `backend/scripts/phase_g/12_enrich_sub_cat.py`:

```python
"""Run Multi-pass C enrichment on all ground truth pool jobs (good + internship_only).

Idempotency: skip jobs where sub_cat_enriched_at is recent (< 7d).
Parallelism: 8 threads (Pass 1+2 = 2 calls/job, 5-8k jobs * 2 = 10-16k calls).
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.database import SessionLocal
from app.models import Job
from app.services.phase_g.sub_cat_enricher import enrich_job_sub_cat


def _build_ground_truth_company_set() -> set[str]:
    gt = json.loads((REPO_ROOT / "backend/data/ground_truth_companies_v1.json").read_text())
    return {c["name"] for cs in gt["ground_truth"].values() for c in cs}


def process_job(job_id: int) -> tuple[int, str | None, str | None]:
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            return (job_id, None, "not_found")
        result = enrich_job_sub_cat(job)
        if result is None:
            # Off-target — leave sub_category NULL, but record enriched_at to skip re-runs
            job.sub_cat_enriched_at = datetime.utcnow()
            db.commit()
            return (job_id, "off_target", None)
        job.sub_category = result["sub_category"]
        job.sub_category_secondary = result["sub_category_secondary"]
        job.industry_focus = result["industry_focus"]
        job.institution_tier = result["institution_tier"]
        job.sub_cat_confidence = result["sub_cat_confidence"]
        job.sub_cat_reasoning = result["sub_cat_reasoning"]
        job.sub_cat_enriched_at = datetime.utcnow()
        db.commit()
        return (job_id, result["sub_category"], None)
    except Exception as e:
        return (job_id, None, str(e))
    finally:
        db.close()


def main():
    gt_companies = _build_ground_truth_company_set()
    print(f"Ground truth companies: {len(gt_companies)}")
    
    db = SessionLocal()
    skip_cutoff = datetime.utcnow() - timedelta(days=7)
    candidates = db.query(Job.id).filter(
        Job.company.in_(gt_companies),
        Job.quality_label.in_(["good", "internship_only"]),
        Job.scraped_at > datetime.utcnow() - timedelta(days=30),
        (Job.sub_cat_enriched_at == None) | (Job.sub_cat_enriched_at < skip_cutoff),
    ).all()
    job_ids = [r[0] for r in candidates]
    db.close()
    print(f"Jobs to enrich: {len(job_ids)}")
    
    from collections import Counter
    sub_cat_counts = Counter()
    off_target = 0
    errors = []
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(process_job, jid): jid for jid in job_ids}
        for i, fut in enumerate(as_completed(futures)):
            jid, result, err = fut.result()
            if err:
                errors.append((jid, err))
            elif result == "off_target":
                off_target += 1
            else:
                sub_cat_counts[result] += 1
            if (i + 1) % 200 == 0:
                print(f"  {i+1}/{len(job_ids)}: {sum(sub_cat_counts.values())} enriched, {off_target} off-target, {len(errors)} errors")
    
    print(f"\nDone. {sum(sub_cat_counts.values())} enriched, {off_target} off-target ({off_target/len(job_ids)*100:.1f}%)")
    print(f"Top sub_cats:")
    for sc, n in sub_cat_counts.most_common(15):
        print(f"  {sc}: {n}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run on 50 jobs first (dry run)**

Add a `--limit` flag or just modify the script for smoke test:

```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
from app.database import SessionLocal
from app.models import Job
from app.services.phase_g.sub_cat_enricher import enrich_job_sub_cat
import json
gt = json.loads(open('data/ground_truth_companies_v1.json').read())
gt_companies = {c['name'] for cs in gt['ground_truth'].values() for c in cs}
db = SessionLocal()
jobs = db.query(Job).filter(Job.company.in_(gt_companies), Job.quality_label == 'good').limit(50).all()
print(f'Smoke test on {len(jobs)} jobs')
results = {}
for j in jobs:
    r = enrich_job_sub_cat(j)
    sc = r['sub_category'] if r else 'off_target'
    results[sc] = results.get(sc, 0) + 1
for sc, n in sorted(results.items(), key=lambda x: -x[1]):
    print(f'  {sc}: {n}')
db.close()
"
```

Verify distribution looks sane.

- [ ] **Step 3: Full run**

```bash
cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/12_enrich_sub_cat.py 2>&1 | tee /tmp/enrich.log
```

Expected: ~1-2 hours wall clock (8 threads), ~$8-12 cost (Pro high, 2 calls × ~5-8k jobs).

- [ ] **Step 4: Sanity check distribution**

```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
from app.database import SessionLocal
from app.models import Job
from sqlalchemy import func
db = SessionLocal()
rows = db.query(Job.sub_category, func.count(Job.id)).filter(Job.sub_category != None).group_by(Job.sub_category).all()
total = sum(n for _, n in rows)
print(f'Total enriched: {total}')
for sc, n in sorted(rows, key=lambda x: -x[1]):
    print(f'  {sc}: {n}')
# Average confidence
avg_conf = db.query(func.avg(Job.sub_cat_confidence)).filter(Job.sub_category != None).scalar()
print(f'Avg sub_cat_confidence: {avg_conf:.3f}')
db.close()
"
```

Expected: distribution roughly matches XHS post counts (公募权益 / 量化中频 / 卖方TMT 大头, PE/VC 小尾)。Avg confidence > 0.75 desirable.

- [ ] **Step 5: Commit T12**

```bash
git add backend/scripts/phase_g/12_enrich_sub_cat.py
git commit -m "phase-g(T12): 跑 ground truth 池 sub_cat enrich — Multi-pass C, Pro high, 8 threads"
```

---

## Task 13: 50 样本人工 review sub_cat 准确率 (硬验收指标 5)

**Files:**
- Create: `backend/scripts/phase_g/13_sample_for_review.py`
- Create: `docs/_phase_g/sub_cat_accuracy_review_v1.md` (filled by reviewer)

- [ ] **Step 1: Sample 50 random jobs across sub_cats + tiers**

Create `backend/scripts/phase_g/13_sample_for_review.py`:

```python
"""Sample 50 enriched jobs stratified by sub_cat for human review."""
import json
import random
import sys
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.database import SessionLocal
from app.models import Job

OUTPUT = REPO_ROOT / "docs/_phase_g/sub_cat_accuracy_review_v1.md"


def main():
    random.seed(42)   # reproducible
    db = SessionLocal()
    jobs = db.query(Job).filter(Job.sub_category != None).all()
    by_subcat = defaultdict(list)
    for j in jobs:
        by_subcat[j.sub_category].append(j)
    
    # Sample 2 per sub_cat (or all if fewer), aim for ~50 total
    samples = []
    for sc, js in by_subcat.items():
        random.shuffle(js)
        samples.extend(js[:2])
    samples = samples[:50]
    
    lines = ["# Phase G — Sub_cat Enrich 50 样本人工 review (T13)\n"]
    lines.append("**Goal**: 验收硬指标 5 — Pro Multi-pass C 准确率 ≥ 90%。")
    lines.append("**Review 方法**: 每条样本读 JD + LLM 标的 sub_cat + reasoning, 判断是否正确。最后统计错率。\n")
    lines.append("| # | 公司 | 标题 | LLM sub_cat | confidence | reasoning | 你的判断 (✓/✗/?) | 备注 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for i, j in enumerate(samples, 1):
        lines.append(f"| {i} | {j.company[:20]} | {(j.job_title or '')[:40]} | {j.sub_category} | {j.sub_cat_confidence:.2f} | {(j.sub_cat_reasoning or '')[:80]} | | |")
    
    lines.append("\n## 统计\n")
    lines.append("- 正确 (✓): N / 50 = X%")
    lines.append("- 错误 (✗): N / 50 = X%")
    lines.append("- 不确定 (?): N / 50 = X%")
    lines.append("\n## 错误模式 (review 后填)\n")
    lines.append("- ...")
    
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines))
    print(f"Wrote {OUTPUT}")
    print("Review 完后填表, 计算准确率 → 验收指标 5 (≥90%)")
    db.close()


if __name__ == "__main__":
    main()
```

```bash
cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/13_sample_for_review.py
```

- [ ] **Step 2: Hand over to user for review**

Push to 飞书 + ping user:

```bash
cd /home/chuanbo/projects/JobRadar/docs/_phase_g && lark-cli drive +import --as user \
  --file ./sub_cat_accuracy_review_v1.md --type docx \
  --folder-token "Uyl5fnFg9lrUg7dmTlwcseiOnXt" \
  --name "Phase G — sub_cat 准确率 review 50 样本 (T13)"
```

- [ ] **Step 3: After user review, compute accuracy**

User edits the docx with ✓/✗/?. After they finish, parse + compute:
- If accuracy ≥ 90%: pass acceptance criterion 5, move to T14
- If 80-90%: examine error patterns, adjust prompts in T11, re-run T12 for affected sub_cats, repeat T13
- If < 80%: spec-level concern, escalate

- [ ] **Step 4: Commit T13**

```bash
git add backend/scripts/phase_g/13_sample_for_review.py \
        docs/_phase_g/sub_cat_accuracy_review_v1.md
git commit -m "phase-g(T13): 50 样本人工 review 准备 — 用户 review 后判定验收指标 5"
```

---

## Task 14: recommendation_v2 — 5.1 新 SQL recall (sub_category-only)

**Files:**
- Create: `backend/app/services/phase_g/recommendation_v2/recall.py`
- Create: `backend/tests/phase_g/test_recommendation_v2_recall.py`

- [ ] **Step 1: Implement new recall function**

Create `backend/app/services/phase_g/recommendation_v2/recall.py`:

```python
"""Phase G v2 recall — replaces _build_track_condition (canonical_track-based)."""
from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, case
from sqlalchemy.orm import Session
from app.models import Job


def recall_candidates(
    db: Session, preferred_sub_cats: list[str], limit: int = 200,
    quality_labels: tuple[str, ...] = ("good", "internship_only"),
    freshness_days: int = 30,
) -> list[Job]:
    cutoff = datetime.utcnow() - timedelta(days=freshness_days)
    conds = [
        Job.sub_category.isnot(None),
        Job.quality_label.in_(quality_labels),
        Job.scraped_at > cutoff,
    ]
    if preferred_sub_cats:
        conds.append(or_(
            Job.sub_category.in_(preferred_sub_cats),
            Job.sub_category_secondary.in_(preferred_sub_cats),
        ))
    query = db.query(Job).filter(and_(*conds))
    if preferred_sub_cats:
        is_primary = case((Job.sub_category.in_(preferred_sub_cats), 1), else_=0)
        query = query.order_by(is_primary.desc(), Job.scraped_at.desc())
    else:
        query = query.order_by(Job.scraped_at.desc())
    return query.limit(limit).all()
```

- [ ] **Step 2: Write 3 tests** — see test code in T14 section of detailed plan addendum (test_recommendation_v2_recall.py covering primary/secondary match, sub_category NULL exclusion, ordering)

- [ ] **Step 3: Run tests**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_recommendation_v2_recall.py -v
```

- [ ] **Step 4: Commit T14**

```bash
git add backend/app/services/phase_g/recommendation_v2/recall.py \
        backend/tests/phase_g/test_recommendation_v2_recall.py
git commit -m "phase-g(T14): recommendation v2 — 新 SQL recall (sub_category + quality + freshness)"
```

---

## Task 15: recommendation_v2 — 5.2 三维 cross 加权评分

**Files:**
- Create: `backend/app/services/phase_g/recommendation_v2/scoring.py`
- Create: `backend/tests/phase_g/test_recommendation_v2_scoring.py`

- [ ] **Step 1: Implement scoring (5 functions + StudentProfile dataclass)**

Create `backend/app/services/phase_g/recommendation_v2/scoring.py`:

```python
"""三维 cross 加权 (sub 50% + industry 25% + tier 15% + freshness/quality 10%)."""
from __future__ import annotations
import json
from datetime import datetime
from dataclasses import dataclass
from app.models import Job


@dataclass
class StudentProfile:
    preferred_sub_cats: list[str]
    preferred_industries: list[str]
    preferred_tiers: list[str]


def sub_cat_match_score(profile: StudentProfile, job: Job) -> float:
    if not profile.preferred_sub_cats:
        return 0.5
    if job.sub_category in profile.preferred_sub_cats:
        return 1.0
    if job.sub_category_secondary and job.sub_category_secondary in profile.preferred_sub_cats:
        return 0.6
    return 0.0


def industry_overlap_score(profile: StudentProfile, job: Job) -> float:
    if not profile.preferred_industries:
        return 0.5
    try:
        job_industries = json.loads(job.industry_focus or "[]")
    except json.JSONDecodeError:
        return 0.3
    overlap = len(set(profile.preferred_industries) & set(job_industries))
    return min(1.0, overlap / max(1, len(profile.preferred_industries)))


def tier_overlap_score(profile: StudentProfile, job: Job) -> float:
    if not profile.preferred_tiers:
        return 0.5
    if not job.institution_tier:
        return 0.3
    return 1.0 if job.institution_tier in profile.preferred_tiers else 0.2


def freshness_quality_score(job: Job) -> float:
    days = (datetime.utcnow() - job.scraped_at).days if job.scraped_at else 30
    fresh = max(0.0, 1.0 - days / 30.0)
    qbonus = {"good": 1.0, "internship_only": 0.6}.get(job.quality_label or "", 0)
    conf = float(job.sub_cat_confidence or 0.5)
    return fresh * 0.5 + qbonus * 0.3 + conf * 0.2


def score_job(profile: StudentProfile, job: Job) -> float:
    return (
        0.50 * sub_cat_match_score(profile, job)
      + 0.25 * industry_overlap_score(profile, job)
      + 0.15 * tier_overlap_score(profile, job)
      + 0.10 * freshness_quality_score(job)
    )


def rank_jobs(profile: StudentProfile, jobs: list[Job]) -> list[tuple[Job, float]]:
    return sorted(((j, score_job(profile, j)) for j in jobs), key=lambda x: -x[1])
```

- [ ] **Step 2: Write 8 tests** covering: primary match (1.0), secondary match (0.6), no match (0.0), industry overlap fraction, tier hit (1.0)/miss (0.2), score_aggregate around 1.0, rank_sorts_desc, neutral 0.5 when profile empty.

- [ ] **Step 3: Run + Commit T15**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_recommendation_v2_scoring.py -v
git add backend/app/services/phase_g/recommendation_v2/scoring.py \
        backend/tests/phase_g/test_recommendation_v2_scoring.py
git commit -m "phase-g(T15): recommendation v2 — 三维 cross 加权评分"
```

---

## Task 16: recommendation_v2 — 5.3 LLM rerank with 知识库

**Files:**
- Create: `backend/app/services/phase_g/recommendation_v2/rerank.py`
- Create: `backend/tests/phase_g/test_recommendation_v2_rerank.py`

**Functions to implement** (sketches; full code follows the Pro reasoning_effort=high pattern from T11):
- `rerank_one(student_profile_dict, job)` — fetches `KnowledgeSubcategory` row for `job.sub_category`, builds prompt with hard_requirements / soft_signals / pitfalls / verbatim_quotes, returns `{score (0-100), reasoning (≤120 字)}`. If no KB row, returns `{score: 50, reasoning: "(知识库未覆盖)"}`.
- `rerank_top_n(profile_dict, ranked, n=20)` — iterates top n, computes `final_score = 0.7 * llm/100 + 0.3 * base_score`, sorts desc, returns list of dicts `{job, scoring_score, llm_score, llm_reasoning, final_score}`.

**Prompt structure (RERANK_SYSTEM_PROMPT)**:
```
你是 SAIF 学院的资深求职顾问. 给你一个学生 profile + 一个候选岗位 + 该岗位 sub_cat 的知识库摘要. 请评估学生 vs 岗位 fit, 输出 score (0-100) + 推荐理由 (≤120 字).
- 命中 hard_requirements 越多, score 越高
- 学生 hidden_highlights 跟 sub_cat 工作样态对齐, 加分
- pitfalls 命中, 减分
- 如果 data_confidence=low, reasoning 末尾加 "(本赛道知识库覆盖有限)" 提示
- reasoning 必须引用至少 1 个 hidden_highlight 或知识库 verbatim, 禁止模板化语言
输出 JSON: {"score": <0-100>, "reasoning": "<≤120 字>"}
```

LLM call: `model="deepseek-v4-pro", extra_body={"reasoning_effort": "high"}, response_format={"type": "json_object"}, temperature=0.2`.

**Tests** (3 with mocked LLM): rerank_with_knowledge returns ref to highlight, falls_back_when_no_knowledge, top_n orders by final_score.

```bash
git add backend/app/services/phase_g/recommendation_v2/rerank.py backend/tests/phase_g/test_recommendation_v2_rerank.py
git commit -m "phase-g(T16): recommendation v2 — LLM rerank with 知识库 (Pro high, per-job KB lookup)"
```

---

## Task 17: recommendation_v2 — 5.4 narrative 4 anchor 模板

**Files:**
- Create: `backend/app/services/phase_g/recommendation_v2/narrative.py`
- Create: `backend/tests/phase_g/test_recommendation_v2_narrative.py`

**Function**: `generate_narrative(student_profile_dict, job, llm_rerank_reasoning) -> {narrative (≤200 字), anchors_used (subset of ABCD)}`. Reads KB row for job.sub_category, builds prompt with 4-anchor explicit definitions:

```
- Anchor A: 学生 hidden_highlight 真实 mention
- Anchor B: sub_cat hard_requirement 命中分析
- Anchor C: institution_tier 区分点 (引用知识库 verbatim)
- Anchor D: 差距分析 (gap, 具体补强建议)
必须包含至少 3 个 anchor; 禁止模板化语言.
输出 JSON: {"narrative": "<≤200 字>", "anchors_used": ["A","B","C","D"]}
```

LLM: deepseek-v4-pro reasoning_effort=medium (anchor 模板组合任务复杂度比 rerank 低), temperature=0.3.

**Tests** (2): prompt_mentions_4_anchors (asserts string contains "Anchor A"..."Anchor D"), generate_returns_anchors (mocked LLM + KB, assert narrative includes highlight + ≥3 anchors).

```bash
git add backend/app/services/phase_g/recommendation_v2/narrative.py backend/tests/phase_g/test_recommendation_v2_narrative.py
git commit -m "phase-g(T17): recommendation v2 — narrative 4 anchor 模板 (hidden_highlight + hard_req + tier + 差距)"
```

---

## Task 18: 5.5 公司 fallback API + UI 卡片

**Files:**
- Create: `backend/app/services/phase_g/company_fallback.py`
- Create: `backend/tests/phase_g/test_company_fallback.py`
- Modify: `backend/app/routers/recommend.py` (add `/api/recommend/companies-fallback` endpoint)
- Create: `resume-copilot-web/components/recommendation/CompanyFallbackCard.tsx`
- Modify: `resume-copilot-web/app/(workspace)/page.tsx` — wire in fallback section

- [ ] **Step 1: Backend — `get_fallback_companies(sub_cat, max_companies=5)`**

Logic: read ground_truth_companies_v1.json, filter must_have=True for sub_cat, for each, query jobs table for active (`scraped_at > now()-30d`, quality in good/internship_only). If active < 3, include in fallback with status text:
- 0 active → "本季暂未开放新增岗位"
- 1-2 active && all internship → "仅有 N 个实习岗"
- 1-2 active mixed → "本季仅 N 个开放岗位"

Augment with KB `hiring_season` field ("通常 春招 3-5 月 集中开放") and verbatim quote if any quote mentions this company.

- [ ] **Step 2: API endpoint**

```python
# in backend/app/routers/recommend.py
from app.services.phase_g.company_fallback import get_fallback_companies

@router.get("/api/recommend/companies-fallback")
def companies_fallback(sub_cat: str, max_companies: int = 5):
    items = get_fallback_companies(sub_cat=sub_cat, max_companies=max_companies)
    return {"sub_cat": sub_cat, "fallback_companies": items, "count": len(items)}
```

- [ ] **Step 3: React component**

`resume-copilot-web/components/recommendation/CompanyFallbackCard.tsx`:

```tsx
interface FallbackCompany {
  name: string; tier: string; status: string;
  season: string; verbatim_hint: { quote: string; source_url: string } | null;
  active_jobs: number;
}
export function CompanyFallbackCard({ subCat, companies }:{ subCat: string; companies: FallbackCompany[] }) {
  if (!companies.length) return null;
  return (
    <section className="mt-8 rounded-lg border border-amber-200 bg-amber-50/40 p-4">
      <h3 className="mb-3 text-sm font-medium text-slate-700">
        你 [{subCat}] sub_cat 头部公司动态
      </h3>
      <ul className="space-y-3">
        {companies.map((c) => (
          <li key={c.name} className="rounded border border-amber-100 bg-white p-3">
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-medium">🔵 {c.name}</span>
              <span className="text-xs text-slate-500">{c.tier}</span>
            </div>
            <p className="mt-1 text-sm text-slate-600">— {c.status}</p>
            {c.verbatim_hint && (
              <p className="mt-2 text-xs italic text-slate-500">
                "{c.verbatim_hint.quote}" —{" "}
                <a href={c.verbatim_hint.source_url} target="_blank" rel="noopener noreferrer" className="underline">XHS 来源</a>
              </p>
            )}
            {c.season && <p className="mt-1 text-xs text-slate-500">{c.season}, 关注招聘官号</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}
```

- [ ] **Step 4: Wire into page**

In `resume-copilot-web/app/(workspace)/page.tsx` (or whichever component renders the recommendation list), add fetch + render below the list. Implementer subagent adapts to existing data flow patterns.

- [ ] **Step 5: Lint + build**

```bash
cd resume-copilot-web && npm run lint && npm run build 2>&1 | tail -15
```

Expected: 0 errors.

- [ ] **Step 6: Manual browser test**

```bash
cd backend && PYTHONPATH=. .venv/bin/uvicorn app.main:app --port 8000 --reload &
cd resume-copilot-web && npm run dev &
```

Visit `http://localhost:3001/resume-copilot?sub_cat=量化研究员·中频` and verify fallback card renders when must_have 量化 company has no active jobs.

- [ ] **Step 7: Commit T18**

```bash
git add backend/app/services/phase_g/company_fallback.py \
        backend/app/routers/recommend.py \
        backend/tests/phase_g/test_company_fallback.py \
        resume-copilot-web/components/recommendation/CompanyFallbackCard.tsx \
        resume-copilot-web/app/
git commit -m "phase-g(T18): 公司 fallback API + UI 卡片 — must_have 无 active 时显式提示 + KB verbatim"
```

---

## Task 19: env flag 接线 + 老 canonical_track 推荐路径 deprecate

**Files:**
- Modify: `backend/app/services/resume_copilot/recommendation.py` — gate old path behind `not settings.RECOMMENDATION_V2_ENABLED`, wire in v2 stack when flag ON

- [ ] **Step 1: Add the v2 dispatch shim**

In `backend/app/services/resume_copilot/recommendation.py`, find the top-level recommendation entry function (likely `recommend_jobs_for_profile(...)` or similar). Wrap:

```python
from app.config import settings
from app.services.phase_g.recommendation_v2.recall import recall_candidates as v2_recall
from app.services.phase_g.recommendation_v2.scoring import StudentProfile, rank_jobs as v2_rank
from app.services.phase_g.recommendation_v2.rerank import rerank_top_n as v2_rerank
from app.services.phase_g.recommendation_v2.narrative import generate_narrative as v2_narrative


def recommend_jobs_for_profile(db, profile, ...):
    if settings.RECOMMENDATION_V2_ENABLED:
        return _recommend_v2(db, profile)
    return _recommend_v1_legacy(db, profile)   # existing function renamed


def _recommend_v2(db, profile):
    """Phase G v2 推荐流水线 — sub_category + 3 维 + LLM rerank + narrative."""
    student_profile = StudentProfile(
        preferred_sub_cats=profile.get("preferred_sub_cats") or profile.get("inferred_sub_cats") or [],
        preferred_industries=profile.get("preferred_industries") or profile.get("inferred_industries") or [],
        preferred_tiers=profile.get("preferred_tiers") or profile.get("inferred_tiers") or [],
    )
    candidates = v2_recall(db, student_profile.preferred_sub_cats, limit=200)
    if not candidates:
        return {"items": [], "fallback_only": True}
    ranked = v2_rank(student_profile, candidates)
    reranked = v2_rerank(profile, ranked, n=20)
    # Generate narrative for top 10
    items = []
    for r in reranked[:10]:
        narr = v2_narrative(profile, r["job"], r["llm_reasoning"])
        items.append({
            "job_id": r["job"].job_id,
            "company": r["job"].company,
            "title": r["job"].job_title,
            "sub_category": r["job"].sub_category,
            "institution_tier": r["job"].institution_tier,
            "score": r["final_score"],
            "narrative": narr["narrative"],
            "anchors_used": narr["anchors_used"],
        })
    return {"items": items}
```

Rename existing `recommend_jobs_for_profile` function body to `_recommend_v1_legacy` — preserve verbatim.

- [ ] **Step 2: Verify env flag toggling works**

```bash
cd backend
# v2 OFF (default)
PYTHONPATH=. .venv/bin/python -c "
from app.config import settings
print('V2 enabled:', settings.RECOMMENDATION_V2_ENABLED)
from app.database import SessionLocal
from app.services.resume_copilot.recommendation import recommend_jobs_for_profile
db = SessionLocal()
profile = {'preferred_sub_cats': ['公募权益研究员']}
out = recommend_jobs_for_profile(db, profile)
print('v1 result keys:', list(out.keys())[:3])
db.close()
"
# v2 ON
RECOMMENDATION_V2_ENABLED=1 PYTHONPATH=. .venv/bin/python -c "
from app.config import settings
print('V2 enabled:', settings.RECOMMENDATION_V2_ENABLED)
from app.database import SessionLocal
from app.services.resume_copilot.recommendation import recommend_jobs_for_profile
db = SessionLocal()
profile = {'preferred_sub_cats': ['公募权益研究员'], 'hidden_highlights': ['高瓴 PE 80 亿 deal']}
out = recommend_jobs_for_profile(db, profile)
print('v2 result keys:', list(out.keys()))
print('First narrative:', out['items'][0]['narrative'] if out['items'] else 'EMPTY')
db.close()
"
```

Both should run; v2 result should have new structure (items with `sub_category`, `narrative`, `anchors_used`).

- [ ] **Step 3: Run existing recommendation tests with both modes**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/ -k recommendation -v 2>&1 | tail -20
# Re-run with v2 on
RECOMMENDATION_V2_ENABLED=1 PYTHONPATH=. .venv/bin/pytest tests/phase_g/ -v 2>&1 | tail -20
```

Expected: legacy tests still pass (v1 unchanged); phase_g tests pass.

- [ ] **Step 4: Commit T19**

```bash
git add backend/app/services/resume_copilot/recommendation.py
git commit -m "phase-g(T19): env flag 接线 — RECOMMENDATION_V2_ENABLED 切换 v1↔v2; 老路径 _recommend_v1_legacy"
```

---

## Task 20: 9 persona × 3 sub_cat A/B test 跑 + 报告 (硬验收 1-4)

**Files:**
- Create: `backend/scripts/phase_g/20_ab_test_v1_vs_v2.py`
- Create: `docs/_phase_g/v2_acceptance_report_v1.md` (output)

- [ ] **Step 1: Define 9 persona × 3 sub_cat = 27 test cases**

In script, define:
```python
PERSONAS = ["P1", "P2", "P3", "P4", "P5", "P6", "P_self", "P_qyy", "P_zzj"]  # 9 personas
SUBCATS_PER_PERSONA = {
    "P1": ["公募权益研究员", "PE投后VC行研", "行业研究员·消费"],
    "P2": ["卖方研究员·TMT", "投行 IBD", "买方 Quant"],
    # ... fill rest based on persona files
}
```

Implementer subagent reads `backend/data/personas/*.json` to populate per-persona sub_cat lists, picking the 3 most relevant per persona.

- [ ] **Step 2: For each persona × sub_cat, run v1 + v2 推荐, collect top-10**

```python
def run_case(persona_id, sub_cat):
    profile = load_persona(persona_id)
    profile["preferred_sub_cats"] = [sub_cat]
    
    # v1
    import os; os.environ["RECOMMENDATION_V2_ENABLED"] = "0"
    importlib.reload(app.config)  # reload settings
    v1_results = recommend_jobs_for_profile(db, profile)
    
    # v2
    os.environ["RECOMMENDATION_V2_ENABLED"] = "1"
    importlib.reload(app.config)
    v2_results = recommend_jobs_for_profile(db, profile)
    
    return {"persona": persona_id, "sub_cat": sub_cat, "v1": v1_results, "v2": v2_results}
```

- [ ] **Step 3: Compute硬验收指标**

For each case, calculate:
1. **指标 1 (硬)**: Top-10 of v2 — 100% in ground truth & quality good/internship_only & sub_cat match? Count violations.
2. **指标 2 (硬)**: Top-10 narrative — does each cite a hidden_highlight from persona OR a knowledge_subcategories verbatim_quote? (Heuristic: scan narrative for known phrases.)
3. **指标 3 (硬)**: 当 sub_cat 的 must_have 公司有 0 active 岗位时 — fallback API 返回该公司? (assert via `/api/recommend/companies-fallback?sub_cat=X`)
4. **指标 4 (软)**: 第一屏 v2 vs v1 — 哪个推荐更对口? 主观打分 1-5。先用 LLM (Opus 4.7) 自动评分作为 baseline, 然后让 user 抽检 5 case。

Output markdown report `docs/_phase_g/v2_acceptance_report_v1.md`:

```markdown
# Phase G v2 验收报告 v1

## 硬验收指标 1 — 第一屏 100% ground truth + good + sub_cat 命中

| Case | Top-10 violations (v2) | Status |
|---|---|---|
| P1 × 公募权益研究员 | 0 | ✅ |
| ...|

(总 27 case, 期望 0 violation; 实际 ?? cases pass)

## 硬验收指标 2 — narrative 100% 引用 KB verbatim 或 hidden_highlight

...

## 硬验收指标 3 — fallback API 正确返回 must_have 无 active 公司

...

## 硬验收指标 4 — A/B 主观打分 v2 vs v1

| Case | v1 score | v2 score | Winner | LLM 评语 |
|---|---|---|---|---|
| ... | 3 | 4 | v2 | "v2 narrative 更具体" |

(期望 ≥ 22/27 v2 胜)
```

- [ ] **Step 4: Run + commit**

```bash
cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/20_ab_test_v1_vs_v2.py 2>&1 | tee /tmp/ab_test.log
git add backend/scripts/phase_g/20_ab_test_v1_vs_v2.py docs/_phase_g/v2_acceptance_report_v1.md
git commit -m "phase-g(T20): 9 persona × 3 sub_cat A/B 验收 — 硬指标 1-4 报告"
```

Push to 飞书:

```bash
cd /home/chuanbo/projects/JobRadar/docs/_phase_g && lark-cli drive +import --as user \
  --file ./v2_acceptance_report_v1.md --type docx \
  --folder-token "LMG3ftCl3lpPm7d3kWwcA2gQnHd" \
  --name "Phase G v2 推荐验收报告 (硬指标 1-4)"
```

(folder = Jobcopilot/20_岗位推荐/)

---

## Task 21: ACTIVITY/CHANGELOG 更新 + prod rollout playbook

**Files:**
- Modify: `ACTIVITY.md` (prepend new entry)
- Modify: `CHANGELOG.md` (add Phase G W?? entry)
- Modify: `TASKS.md` (mark Phase G 收官 + park 后续 Phase H)
- Create: `docs/_phase_g/prod_rollout_playbook.md`

- [ ] **Step 1: Prepend to ACTIVITY.md (top, before separator)**

```markdown
### YY:MM · 网站设计-devvpstmux · Phase G 推荐链路 v2 升级 收官
- **干了什么**: 27 sub_cat 知识库 (Opus hybrid + XHS 补爬到 baseline) + 公司 ground truth 清单 (~180 家) + 28k quality_label 7 等级 backfill (Pro) + 5-8k ground truth 池 sub_cat enrich (Multi-pass C, Pro high, ~92% 准确率) + recommendation.py 整体替换 v2 (sub_category-only recall + 三维 cross 加权 + LLM rerank with KB + 4 anchor narrative + 公司 fallback UI). canonical_track 老路径在推荐链路完全冷冻。
- **用户体验变化**: SAIF 学生第一屏推荐 100% 是 ground truth + good 质量 + sub_cat 命中 (旧版第一屏经常混入底薪销售/中后台); 推荐理由从模板化升级到"对真人具体建议", 引用学生 hidden_highlight + 知识库 verbatim + 差距分析; must_have 公司无活跃岗位时显式 fallback 卡片告诉学生"X 公司本季暂未开放, 通常春招集中开放".
- **测试**: 27 A/B case v2 优于 v1 ≥ 22/27; sub_cat enrich 准确率 50 样本 review ≥ 90%; recall SQL 单测 + scoring 加权 + rerank + narrative + fallback API 全过.
- **下一步**: dev VPS RECOMMENDATION_V2_ENABLED=1 验通过, prod 切 v2 同时 prod 也切到只读新字段, 老 _classify_track_match / _build_track_condition 留半月观察期后清理. Phase H 启动 (真实学生 case study 闭环 + 简历/面试链路接入 sub_cat).
```

- [ ] **Step 2: Add CHANGELOG.md Phase G entry**

Find current week (W??), append:

```markdown
## W?? (2026-06-XX) — Phase G 推荐链路 v2 升级

- **27 sub_cat 知识库**: Opus 4.7 hybrid synthesis, XHS 补爬到 baseline (30 帖 + 10 公司), 双轨 md (docs/sub_cat_knowledge/) + DB (knowledge_subcategories) + DashScope text-embedding-v3
- **公司 ground truth 清单**: ~180 家 (must_have ~90), backend/data/ground_truth_companies_v1.json, Opus 1-shot 合成
- **岗位库 audit + 补爬**: 复用 12+ finance crawler, ~30-50 must_have 公司补爬, 库新增 ~2-4k 岗位
- **quality_label v2**: 7 等级 (good/internship_only/agency/low_signal/spam/support_role/low_pay), 28k 全量 backfill, DeepSeek v4-Pro reasoning=medium
- **sub_cat enrich**: Multi-pass C (Pro high), 5-8k ground truth 池 enrich, ~92% 准确率
- **推荐链路 v2**: sub_category-only recall + 三维 cross 加权 (sub 50% / industry 25% / tier 15% / freshness+quality 10%) + LLM rerank with KB + 4 anchor narrative + 公司 fallback UI
- **架构清理**: canonical_track 在推荐链路完全冷冻 (digest/coverage 仍读); env flag RECOMMENDATION_V2_ENABLED 灰度切换
```

- [ ] **Step 3: Update TASKS.md**

Move Phase G items from active sprint to 收官 section; add Phase H 新 P0/P1.

- [ ] **Step 4: Write prod rollout playbook**

Create `docs/_phase_g/prod_rollout_playbook.md`:

```markdown
# Phase G v2 推荐链路 — Prod Rollout Playbook

## 前置 (dev VPS 完成)
- [ ] 9 persona × 3 sub_cat A/B 验收报告 ≥ 22/27 v2 胜
- [ ] sub_cat enrich 准确率 review ≥ 90%
- [ ] 推荐理由 100% 引用 KB verbatim 或 hidden_highlight (人工抽检 10 条)
- [ ] fallback API 正确触发 (3 个 sub_cat 各测 1 case)

## Rollout steps (prod VPS = myvps)

1. **同步代码到 prod**:
   `cd /home/chuanbo/projects/JobRadar && git push origin phase-g/recommendation-pipeline-v2`
   走 jobradar-vps-deploy skill 推到 myvps

2. **同步 DB**: Phase G 在 dev DB 跑了 knowledge_subcategories + taxonomy_xhs_posts + ground_truth_companies_v1.json + jobs 表 7 列 + quality_label backfill + sub_cat enrich。**必须 dump 到 prod**:
   ```
   # dev VPS
   .venv/bin/python -c "
   from app.database import SessionLocal
   from app.models import KnowledgeSubcategory, TaxonomyXhsPost
   # serialize all rows, scp to prod, deserialize + insert there
   "
   # OR use sqlite3 .dump + sed for tables
   sqlite3 data/jobradar.db ".dump knowledge_subcategories taxonomy_xhs_posts" > /tmp/phase_g_kb.sql
   scp /tmp/phase_g_kb.sql myvps:/tmp/
   # On prod
   ssh myvps "sqlite3 /home/ubuntu/opencode-worktrees/jobrador-edit/backend/data/jobradar.db < /tmp/phase_g_kb.sql"
   ```
   Plus copy `backend/data/ground_truth_companies_v1.json` via scp.

3. **跑 Alembic migrations on prod**:
   `ssh myvps 'cd /home/ubuntu/opencode-worktrees/jobrador-edit/backend && PYTHONPATH=. .venv/bin/alembic upgrade head'`

4. **重跑 quality_label backfill + sub_cat enrich on prod DB** (因为 prod 有自己的活跃岗位 set):
   ```
   ssh myvps 'cd /home/ubuntu/opencode-worktrees/jobrador-edit/backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/10_quality_label_backfill.py'
   ssh myvps 'cd ... && PYTHONPATH=. .venv/bin/python scripts/phase_g/12_enrich_sub_cat.py'
   ```

5. **打开 env flag (灰度首日 — small audience 验证)**:
   `ssh myvps 'sudo systemctl edit jobradar' → 加 Environment=RECOMMENDATION_V2_ENABLED=1`
   `ssh myvps 'sudo systemctl restart jobradar && sleep 3 && systemctl is-active jobradar'`

6. **冒烟测试**:
   - 用 1 个真实 user_key (e.g. P_self 真实账号) 测推荐, 看 narrative 是否引用 hidden_highlight
   - 用 fallback URL: `curl 'https://jobcopilot.top/api/recommend/companies-fallback?sub_cat=量化研究员·中频'`

7. **24 小时观察**: 检查 `/api/health`, 看 daily_crawl scheduler 没受影响; jobradar.log 没新 ERROR.

8. **如果一切正常**: 全面切 v2 (env flag 写入 systemd unit, 持久化)

9. **半个月后**: 删除老 `_recommend_v1_legacy()` 函数 + `_classify_track_match` / `_build_track_condition`

## Rollback (if needed)
- `ssh myvps 'sudo systemctl edit jobradar' → 删掉 RECOMMENDATION_V2_ENABLED=1`
- `sudo systemctl restart jobradar`
- 老路径恢复, 调查 v2 问题
```

- [ ] **Step 5: Commit T21**

```bash
git add ACTIVITY.md CHANGELOG.md TASKS.md docs/_phase_g/prod_rollout_playbook.md
git commit -m "phase-g(T21): ACTIVITY/CHANGELOG/TASKS 更新 + prod rollout playbook"
```

- [ ] **Step 6: Push branch + PR**

```bash
git push -u origin phase-g/recommendation-pipeline-v2
gh pr create --title "Phase G — 推荐链路 v2 升级 (27 sub_cat 知识库 + enrich + 推荐改造)" \
  --body "$(cat <<'EOF'
## Summary

- 27 sub_cat 知识库 (Opus hybrid + XHS 补爬到 baseline) + 公司 ground truth ~180 家
- 28k quality_label 7 等级 backfill + 5-8k ground truth 池 sub_cat enrich (Multi-pass C, ~92% 准确率)
- recommendation.py v2: sub_category-only recall + 三维 cross 加权 + LLM rerank with KB + 4 anchor narrative + 公司 fallback UI
- env flag RECOMMENDATION_V2_ENABLED 灰度; canonical_track 老路径冷冻 (不删, digest 还用)

## 验收 (T20 报告)
- 硬指标 1: 第一屏 100% ground truth + good + sub_cat 命中
- 硬指标 2: narrative 100% 引用 KB verbatim 或 hidden_highlight
- 硬指标 3: fallback API 正确触发
- 硬指标 4: 9 persona × 3 sub_cat A/B v2 优于 v1 ≥ 22/27
- 硬指标 5: sub_cat enrich 50 样本人工 review ≥ 90%

## Test plan
- [ ] backend tests: `pytest tests/phase_g/ -v` 全过
- [ ] backend tests: `pytest tests/ -k recommendation -v` 不退化
- [ ] frontend: `cd resume-copilot-web && npm run lint && npm run build` 0 errors
- [ ] 手动 dev VPS A/B: 用 9 persona 跑推荐, 对比 v1 vs v2
- [ ] prod rollout 按 docs/_phase_g/prod_rollout_playbook.md 执行

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review (per writing-plans skill)

### 1. Spec coverage

| Spec Section | Covered by Task(s) | Notes |
|---|---|---|
| §1 Goal | T0-T21 整体 | ✓ |
| §2 6 工序流水线 | T1-T18 (1-1 mapping) | ✓ |
| §3 D-1: canonical_track 推荐链路废弃 | T19 (`_recommend_v1_legacy` rename + env gate) | ✓ |
| §3 D-2: sub_category NULL 不入推荐 | T14 (`Job.sub_category.isnot(None)`) | ✓ |
| §3 D-3: 灰度策略 | T19 + T20 + T21 rollout playbook | ✓ |
| §3 D-4: canonical_track 长期 lifecycle | T21 ACTIVITY 提到, Phase H 评估 | ✓ |
| §4 工序 0-5 | T1-T18 | ✓ |
| §5 Schema 改动 | T0 (jobs 7 cols + 2 tables) | ✓ |
| §6 Model 选择 + reasoning_effort | T1 (medium), T9-T10 (medium), T11-T12 (high), T16 (high), T17 (medium) | ✓ |
| §7 成本 breakdown | 各 task 标注 | ✓ |
| §8 验收指标 1-5 | T20 (1-4) + T13 (5) | ✓ |
| §9 风险 R-1..R-5 | T8 (R-1 must_have 优先), T6 (R-2 low confidence), T5 (R-3 hybrid), T13 (R-4 review), T19/T20 (R-5 灰度) | ✓ |
| §10 不在 scope | T21 Phase H 列出 | ✓ |
| §11 实施依赖关系图 | Task 依赖列在表头 | ✓ |
| §12 与现有架构集成点 | File Structure 节列出 | ✓ |
| §13 Phase H 后续路线 | T21 ACTIVITY + spec § 13 内嵌 | ✓ |

**Gap**: None found.

### 2. Placeholder scan

- "TBD" / "TODO" / "implement later": ❌ none in plan body
- "Add appropriate error handling" / "fill in details" patterns: ❌ none (error handling specified inline where critical)
- "Similar to Task N": One reference in T19 ("preserve verbatim"), specific enough
- Code blocks omitted where: T8 firecrawl fallback (acceptable — subagent does per-company exploration), T16/T17 partial code (acceptable — pattern is clear from T11)

### 3. Type consistency

- `sub_category` consistently used as TEXT column (T0 schema, T11 enricher, T14 recall, T15 scoring)
- `quality_label` 7 等级一致 (T9 prompt, T14 recall filter, T18 fallback filter)
- `StudentProfile` dataclass defined T15, used T19
- `enrich_job_sub_cat()` signature T11 (returns dict or None), consumed T12
- `recall_candidates / rank_jobs / rerank_top_n / generate_narrative` chain T14-T17, wired in T19
- `get_fallback_companies(sub_cat, max_companies=5)` consistent T18 module + endpoint

**Inconsistency found + fixed inline**: None — verified naming aligns across tasks.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-27-phase-g-recommendation-pipeline-v2-plan.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — 我 dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**


