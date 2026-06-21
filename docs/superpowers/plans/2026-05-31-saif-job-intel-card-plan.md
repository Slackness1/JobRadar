# SAIF 岗位情报卡 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给每个岗位生成一张固定维度情报卡 —— 定位（赛道/梯队/条线/一句话）+ 学生最关心的 3 维情报（门槛/薪酬/前景体验），每维带三维可信度徽章（信源分/亲历层级/交叉验证）+ verbatim 原话 + provenance。

**Architecture:** 后端纯函数层（信源分 scorer / 作者去重 / 定位拼装 / 徽章合成）+ 一个 LLM 维度归类抽取器（可注入、fixture 测试）+ 卡组装器（复用已有 `xhs/retrieve.py` 检索 + `intel/enrichment.py` 的 LLM/缓存模式）+ 新 API `/api/job-intel/card`。前端扩 `IntelDrawer.tsx`。零 LLM 的部分（信源分/徽章/定位/去重）先落地并测；LLM 维度抽取用 fixture 测机制，真跑走免费强模型/DeepSeek（余额）。

**Tech Stack:** FastAPI + SQLAlchemy + SQLite + Alembic；pytest；Next.js（前端）。所有 python 走 `PYTHONPATH=. .venv/bin/pytest`，工作目录 `backend/`。

**依据 spec：** `docs/superpowers/specs/2026-05-31-saif-job-intel-card-design.md`

---

## File Structure（先锁边界）

| 文件 | 职责 |
|---|---|
| `backend/app/services/intel/source_score.py`（新） | Layer-1 信源分纯函数：`compute_source_score(note_id, liked, comment, signal_score, author_name) -> float`；营销正则；平台权重 |
| `backend/app/services/intel/corroboration.py`（新） | Layer-3 作者感知交叉验证：`independent_cross(siblings) -> str`（verified/single），`siblings` 含 source 前缀 + author |
| `backend/app/services/intel/positioning.py`（新） | 定位拼装：`build_positioning(job) -> dict`（赛道/梯队/tier_label/track_line/one_liner），纯模板 + DB 读 |
| `backend/app/services/intel/badge.py`（新） | 三维合成：`synth_badge(source_score, content_tier, cross) -> int`（1/2/3） |
| `backend/app/services/intel/dimension_extract.py`（新） | LLM 维度归类 + 要点抽取：`extract_dimensions(insights, llm_fn) -> dict`（threshold/compensation/outlook，每点挂 insight_id）；`llm_fn` 可注入 |
| `backend/app/services/intel/job_card.py`（新） | 卡组装器：`build_job_card(db, job_id, *, use_cache=True, llm_fn=None) -> dict`；磁盘缓存（复用 enrichment 的缓存模式） |
| `backend/app/routers/intel_enrichment.py`（改） | 加 `GET /api/job-intel/card?job_id=&refresh=` |
| `backend/alembic/versions/<new>_add_source_score.py`（新） | `xhs_insights` 加 `source_score`(Float) + `source_platform`(Text) |
| `backend/scripts/intel_backfill_source_score.py`（新） | 给存量 insight 回填 source_score（纯数值） |
| `backend/tests/intel/test_*.py`（新） | 各纯函数 + 抽取器 fixture + 组装器 + API 测试 |
| `resume-copilot-web/components/resume-copilot/workspace/intel/IntelDrawer.tsx`（改） | 渲染定位段 + 3 维 + 徽章（复用已有 conflict 折叠面板） |

---

## Task 1: 信源分 scorer（Layer-1 纯函数）

**Files:**
- Create: `backend/app/services/intel/source_score.py`
- Test: `backend/tests/intel/test_source_score.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/intel/test_source_score.py
from app.services.intel.source_score import compute_source_score, platform_of

def test_platform_of_by_prefix():
    assert platform_of("zh_abc") == "zhihu"
    assert platform_of("xhs_abc") == "xhs"
    assert platform_of("xhsp_1") == "xhs"
    assert platform_of("bili_BV1") == "bilibili"
    assert platform_of("pod_x") == "podcast"

def test_high_engagement_zhihu_with_author_scores_mid_high():
    s = compute_source_score("zh_x", liked=200, comment=33, signal_score=200, author_name="王某")
    assert 0.45 <= s <= 0.85  # 知乎 ceiling 0.85，高赞有作者

def test_marketing_gate_tanks_score():
    s = compute_source_score("xhs_x", liked=500, comment=50, signal_score=500,
                             author_name="某机构", marketing_text="扫码进群领取资料")
    assert s <= 0.20

def test_empty_signals_floor():
    s = compute_source_score("xhsp_1", liked=0, comment=0, signal_score=0, author_name="")
    assert 0.0 <= s <= 0.15
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. .venv/bin/pytest tests/intel/test_source_score.py -v`
Expected: FAIL（`ModuleNotFoundError: app.services.intel.source_score`）

- [ ] **Step 3: 写实现**

```python
# backend/app/services/intel/source_score.py
"""Layer-1 信源分（弱版，零 LLM）。设计见 docs/source-credibility-layer1-design-2026-05-31.md。
当前仅用已有信号（liked/comment/signal_score/author + 营销闸）。收藏比/作者权威待补数据后并入。"""
from __future__ import annotations
import math, re

PLATFORM_VALUE = {"xhs": 1.0, "zhihu": 0.85, "bilibili": 0.85, "podcast": 0.5}
_MARKETING = re.compile(r"扫码|进群|我的课|训练营|资料领取|私信领|公总号|加我咨询|领取资料")

def platform_of(note_id: str) -> str:
    nid = note_id or ""
    if nid.startswith("zh_"): return "zhihu"
    if nid.startswith("xhsp_") or nid.startswith("xhs_"): return "xhs"
    if nid.startswith("bili_"): return "bilibili"
    if nid.startswith("pod_"): return "podcast"
    return "xhs"  # 默认按 UGC

def _norm(x: float, ref: float) -> float:
    x = max(0.0, float(x or 0))
    return min(1.0, math.log1p(x) / math.log1p(ref))

def compute_source_score(
    note_id: str, *, liked: float = 0, comment: float = 0,
    signal_score: float = 0, author_name: str = "", marketing_text: str = "",
) -> float:
    pv = PLATFORM_VALUE.get(platform_of(note_id), 0.85)
    signal_quality = (
        0.40 * _norm(liked, 1000)
        + 0.20 * _norm(comment, 300)
        + 0.25 * _norm(signal_score, 500)
        + 0.15 * (1.0 if (author_name or "").strip() else 0.0)
    )
    gate = 0.2 if _MARKETING.search(marketing_text or "") else 1.0
    return round(pv * signal_quality * gate, 3)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONPATH=. .venv/bin/pytest tests/intel/test_source_score.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: commit**

```bash
git add app/services/intel/source_score.py tests/intel/test_source_score.py
git commit -m "feat(intel): Layer-1 信源分 scorer（弱版，零LLM）"
```

---

## Task 2: source_score 列 + 回填脚本

**Files:**
- Create: `backend/alembic/versions/<rev>_add_source_score.py`
- Create: `backend/scripts/intel_backfill_source_score.py`
- Test: `backend/tests/intel/test_source_score_backfill.py`

- [ ] **Step 1: 写失败测试（回填把分写进列）**

```python
# backend/tests/intel/test_source_score_backfill.py
import sqlite3, subprocess, sys

def test_backfill_writes_scores(tmp_path):
    # 用真 dev DB 的只读校验：回填后 zh_/xhs_ insight 的 source_score 非空率 > 0.9
    db = "data/jobradar.db"
    c = sqlite3.connect(db).cursor()
    total = c.execute("SELECT COUNT(*) FROM xhs_insights").fetchone()[0]
    scored = c.execute("SELECT COUNT(*) FROM xhs_insights WHERE source_score IS NOT NULL").fetchone()[0]
    assert total > 0
    assert scored >= total * 0.9, f"only {scored}/{total} scored — 先跑 scripts/intel_backfill_source_score.py"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. .venv/bin/alembic upgrade head && PYTHONPATH=. .venv/bin/pytest tests/intel/test_source_score_backfill.py -v`
Expected: FAIL（`no such column: source_score` 或 scored=0）

- [ ] **Step 3: 写 migration + 回填脚本**

```python
# backend/alembic/versions/<rev>_add_source_score.py
"""add source_score + source_platform to xhs_insights"""
from alembic import op
import sqlalchemy as sa
revision = "<rev>"; down_revision = "<prev_head>"  # 用 alembic heads 查
branch_labels = None; depends_on = None

def upgrade():
    insp = sa.inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("xhs_insights")}
    if "source_score" not in cols:
        op.add_column("xhs_insights", sa.Column("source_score", sa.Float(), nullable=True))
    if "source_platform" not in cols:
        op.add_column("xhs_insights", sa.Column("source_platform", sa.Text(), nullable=True))

def downgrade():
    op.drop_column("xhs_insights", "source_platform")
    op.drop_column("xhs_insights", "source_score")
```

```python
# backend/scripts/intel_backfill_source_score.py
"""给存量 xhs_insights 回填 source_score + source_platform（纯数值，零 LLM）。幂等。"""
from __future__ import annotations
import app.config  # noqa
from app.database import SessionLocal
from app.models import XhsInsight, XhsNote
from app.services.intel.source_score import compute_source_score, platform_of

def main() -> int:
    db = SessionLocal()
    try:
        notes = {n.note_id: n for n in db.query(XhsNote).all()}
        n = 0
        for ins in db.query(XhsInsight).all():
            note = notes.get(ins.source_note_id)
            ins.source_platform = platform_of(ins.source_note_id)
            ins.source_score = compute_source_score(
                ins.source_note_id,
                liked=getattr(note, "liked_count", 0) or 0,
                comment=getattr(note, "comment_count", 0) or 0,
                signal_score=getattr(note, "signal_score", 0) or 0,
                author_name=getattr(note, "author_name", "") or "",
                marketing_text=(ins.content or "") + " " + (getattr(note, "title", "") or ""),
            )
            n += 1
            if n % 500 == 0:
                db.commit()
        db.commit()
        print(f"backfilled {n} insights")
        return 0
    finally:
        db.close()

if __name__ == "__main__":
    raise SystemExit(main())
```

同时给 model 加列（`backend/app/models.py` 的 `XhsInsight`）：
```python
    source_score = Column(Float, nullable=True)
    source_platform = Column(Text, nullable=True)
```

- [ ] **Step 4: 跑 migration + 回填 + 测试**

Run:
```bash
PYTHONPATH=. .venv/bin/alembic upgrade head
PYTHONPATH=. .venv/bin/python scripts/intel_backfill_source_score.py
PYTHONPATH=. .venv/bin/pytest tests/intel/test_source_score_backfill.py -v
```
Expected: 回填打印 `backfilled <N>`；测试 PASS。

- [ ] **Step 5: commit**

```bash
git add alembic/versions/*add_source_score.py scripts/intel_backfill_source_score.py app/models.py tests/intel/test_source_score_backfill.py
git commit -m "feat(intel): xhs_insights 加 source_score/source_platform 列 + 回填脚本"
```

---

## Task 3: 作者感知交叉验证（Layer-3 纯函数）

**Files:**
- Create: `backend/app/services/intel/corroboration.py`
- Test: `backend/tests/intel/test_corroboration.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/intel/test_corroboration.py
from app.services.intel.corroboration import independent_cross

def test_two_sources_two_authors_is_verified():
    sibs = [{"note_id": "zh_a", "author": "王"}, {"note_id": "xhs_b", "author": "李"}]
    assert independent_cross(sibs) == "verified"

def test_same_author_across_sources_not_verified():
    sibs = [{"note_id": "zh_a", "author": "王"}, {"note_id": "xhs_b", "author": "王"}]
    assert independent_cross(sibs) == "single"

def test_two_authors_same_source_not_verified():
    sibs = [{"note_id": "xhs_a", "author": "王"}, {"note_id": "xhs_b", "author": "李"}]
    assert independent_cross(sibs) == "single"  # 同平台不算跨源

def test_missing_author_counts_as_distinct_only_if_distinct_note():
    sibs = [{"note_id": "zh_a", "author": ""}, {"note_id": "xhs_b", "author": ""}]
    assert independent_cross(sibs) == "single"  # 都缺作者 → 无法确认非同人 → 不升 verified
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. .venv/bin/pytest tests/intel/test_corroboration.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写实现**

```python
# backend/app/services/intel/corroboration.py
"""Layer-3 交叉验证：不同信源 + 不同作者 才算 verified（author_id 缺失，用 author_name 近似）。"""
from __future__ import annotations
from app.services.intel.source_score import platform_of

def independent_cross(siblings: list[dict]) -> str:
    """siblings: [{"note_id":..., "author":...}, ...]（含自身）。
    返回 'verified' 当 ≥2 不同平台 且 ≥2 个非空且互异的作者；否则 'single'。"""
    platforms = {platform_of(s.get("note_id", "")) for s in siblings}
    authors = {(s.get("author") or "").strip() for s in siblings if (s.get("author") or "").strip()}
    if len(platforms) >= 2 and len(authors) >= 2:
        return "verified"
    return "single"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONPATH=. .venv/bin/pytest tests/intel/test_corroboration.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: commit**

```bash
git add app/services/intel/corroboration.py tests/intel/test_corroboration.py
git commit -m "feat(intel): 作者感知交叉验证（不同信源+不同人才 verified）"
```

---

## Task 4: 定位拼装（赛道/梯队/条线/一句话）

**Files:**
- Create: `backend/app/services/intel/positioning.py`
- Test: `backend/tests/intel/test_positioning.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/intel/test_positioning.py
from app.services.intel.positioning import build_positioning

def test_full_positioning():
    job = {"company": "华泰证券", "job_title": "固定收益部 信用研究岗",
           "department": "固定收益部", "sub_category": "信用研究员",
           "institution_tier": "头部券商研究所"}
    p = build_positioning(job)
    assert p["sub_category"] == "信用研究员"
    assert p["tier"] == "头部券商研究所"
    assert "固收" in p["track_line"] or "固定收益" in p["track_line"]
    assert p["one_liner"]  # 非空一句话

def test_missing_subcat_graceful():
    job = {"company": "X", "job_title": "Y", "department": "", "sub_category": None, "institution_tier": None}
    p = build_positioning(job)
    assert p["sub_category"] is None
    assert p["one_liner"]  # 仍给兜底文案
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. .venv/bin/pytest tests/intel/test_positioning.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写实现**

```python
# backend/app/services/intel/positioning.py
"""定位拼装：从 job 的 taxonomy 字段生成 赛道/梯队/粗条线/一句话。粗粒度（金融不细分部门）。"""
from __future__ import annotations
import re

# 粗条线：从 title/department 关键词抽（抽不到则省略）
_LINE_KW = [
    ("固定收益", "固收条线"), ("固收", "固收条线"), ("投行", "投行条线"),
    ("资产管理", "资管条线"), ("资管", "资管条线"), ("研究所", "卖方研究条线"),
    ("量化", "量化条线"), ("风险管理", "风险条线"), ("衍生品", "衍生品条线"),
    ("机构", "机构业务条线"),
]
# sub_cat → SAIF 出路定位（一句话用）
_OUTLET = {
    "信用研究员": "卖方/买方固收核心出路", "利率宏观策略": "固收宏观研究出路",
    "机构销售·销售支持": "卖方/资管机构条线核心出路", "投行 IBD": "一级市场核心出路",
    "财富管理FOF": "资管FOF出路", "风险管理·投资监督": "中后台投资监督出路",
    "银行总行综合管培": "银行总行管理序列出路",
}

def _track_line(title: str, dept: str) -> str:
    blob = (title or "") + " " + (dept or "")
    for kw, line in _LINE_KW:
        if kw in blob:
            return line
    return ""

def build_positioning(job: dict) -> dict:
    sub = job.get("sub_category")
    tier = job.get("institution_tier")
    line = _track_line(job.get("job_title", ""), job.get("department", ""))
    outlet = _OUTLET.get(sub or "", "金融核心赛道") if sub else "金融岗位"
    one = f"{tier or ''}{(' · ' if tier and sub else '')}{sub or ''}，{outlet}".strip("，· ")
    return {
        "sub_category": sub,
        "tier": tier,
        "tier_label": tier or "梯队待定",
        "track_line": line,
        "one_liner": one or "金融岗位",
    }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONPATH=. .venv/bin/pytest tests/intel/test_positioning.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: commit**

```bash
git add app/services/intel/positioning.py tests/intel/test_positioning.py
git commit -m "feat(intel): 岗位定位拼装（赛道/梯队/粗条线/一句话）"
```

---

## Task 5: 徽章合成（三维 → ★）

**Files:**
- Create: `backend/app/services/intel/badge.py`
- Test: `backend/tests/intel/test_badge.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/intel/test_badge.py
from app.services.intel.badge import synth_badge

def test_verified_is_three_stars():
    assert synth_badge(source_score=0.3, content_tier="low", cross="verified") == 3

def test_single_high_or_strong_is_two():
    assert synth_badge(source_score=0.7, content_tier="med", cross="single") == 2
    assert synth_badge(source_score=0.3, content_tier="high", cross="single") == 2

def test_single_weak_is_one():
    assert synth_badge(source_score=0.3, content_tier="low", cross="single") == 1

def test_n_three_rescues_to_two():
    assert synth_badge(source_score=0.3, content_tier="med", cross="single", n=3) == 2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. .venv/bin/pytest tests/intel/test_badge.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写实现**

```python
# backend/app/services/intel/badge.py
"""三维合成 → 徽章 ★数。原则：交叉验证 > 亲历层级 > 单条信源分。"""
from __future__ import annotations

def synth_badge(*, source_score: float, content_tier: str, cross: str, n: int = 1) -> int:
    if cross == "verified":
        return 3
    if content_tier == "high" or (n or 1) >= 3 or (source_score or 0) >= 0.6:
        return 2
    return 1
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONPATH=. .venv/bin/pytest tests/intel/test_badge.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: commit**

```bash
git add app/services/intel/badge.py tests/intel/test_badge.py
git commit -m "feat(intel): 三维可信度 → 徽章合成"
```

---

## Task 6: LLM 维度归类 + 要点抽取（可注入，fixture 测）

**Files:**
- Create: `backend/app/services/intel/dimension_extract.py`
- Test: `backend/tests/intel/test_dimension_extract.py`

- [ ] **Step 1: 写失败测试（注入 fake llm_fn，不调真 LLM）**

```python
# backend/tests/intel/test_dimension_extract.py
from app.services.intel.dimension_extract import extract_dimensions, build_prompt

def _fake_llm(prompt: str) -> dict:
    # 模拟强模型按契约返回
    return {
        "threshold": {"hard": ["985/海硕"], "soft": ["看重信用框架"], "support_ids": ["zh_a_i0"]},
        "compensation": {"summary": "25-30k×16薪", "support_ids": ["xhs_b_i0"]},
        "outlook": {"summary": "多数推荐", "support_ids": ["xhs_b_i0"]},
    }

def test_extract_returns_three_dims_with_support_ids():
    insights = [
        {"insight_id": "zh_a_i0", "content": "门槛高 985", "source_quote": "...", "confidence": "high"},
        {"insight_id": "xhs_b_i0", "content": "base 28", "source_quote": "...", "confidence": "med"},
    ]
    out = extract_dimensions(insights, llm_fn=_fake_llm)
    assert set(out.keys()) == {"threshold", "compensation", "outlook"}
    assert out["threshold"]["support_ids"] == ["zh_a_i0"]

def test_build_prompt_includes_insight_ids():
    insights = [{"insight_id": "zh_a_i0", "content": "x", "source_quote": "q", "confidence": "high"}]
    p = build_prompt("华泰证券", insights)
    assert "zh_a_i0" in p and "门槛" in p
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. .venv/bin/pytest tests/intel/test_dimension_extract.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写实现**

```python
# backend/app/services/intel/dimension_extract.py
"""LLM 把一个公司的 insights 归到 3 维 + 抽要点，每点回挂 insight_id。
llm_fn(prompt:str)->dict 可注入（测试传 fake；生产传 DeepSeek/强模型适配器）。"""
from __future__ import annotations
import json
from typing import Callable

SYSTEM = """你是金融求职情报整理器。给你一个公司的若干条学生 UGC 洞察（每条带 insight_id）。
把它们整理成学生最关心的 3 个维度，每个维度的每个要点必须回挂支撑它的 insight_id（只能用给定的 id）：
- threshold（门槛）：hard[]（学历/实习/证书）、soft[]（面试官偏好/对口经历）、support_ids[]
- compensation（薪酬）：summary（一句话，含区间/奖金口径）、support_ids[]
- outlook（前景体验）：summary（推荐度/文化/压力/晋升）、support_ids[]
只依据给定洞察，不编造。输出严格 JSON：{"threshold":{...},"compensation":{...},"outlook":{...}}"""

def build_prompt(company: str, insights: list[dict]) -> str:
    lines = [f"公司：{company}", "洞察："]
    for i in insights:
        lines.append(f'- [{i.get("insight_id")}] ({i.get("confidence")}) {i.get("content","")[:200]}')
    lines.append("\n请按 3 维（门槛/薪酬/前景）整理，每点回挂 insight_id。")
    return "\n".join(lines)

_EMPTY = {"threshold": {"hard": [], "soft": [], "support_ids": []},
          "compensation": {"summary": None, "support_ids": []},
          "outlook": {"summary": None, "support_ids": []}}

def extract_dimensions(insights: list[dict], *, llm_fn: Callable[[str], dict]) -> dict:
    if not insights:
        return dict(_EMPTY)
    prompt = build_prompt("", insights)  # company 由 caller 带进 prompt 头亦可
    try:
        out = llm_fn(SYSTEM + "\n\n" + prompt)
    except Exception:
        return dict(_EMPTY)
    # 防御：缺维度补空 + 过滤非法 support_ids
    valid_ids = {i.get("insight_id") for i in insights}
    res = dict(_EMPTY)
    for dim in ("threshold", "compensation", "outlook"):
        d = (out or {}).get(dim) or {}
        d["support_ids"] = [x for x in (d.get("support_ids") or []) if x in valid_ids]
        res[dim] = {**_EMPTY[dim], **d}
    return res
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONPATH=. .venv/bin/pytest tests/intel/test_dimension_extract.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: commit**

```bash
git add app/services/intel/dimension_extract.py tests/intel/test_dimension_extract.py
git commit -m "feat(intel): LLM 维度归类+要点抽取（可注入llm_fn，每点挂insight_id）"
```

---

## Task 7: 卡组装器（job_id → 完整卡）

**Files:**
- Create: `backend/app/services/intel/job_card.py`
- Test: `backend/tests/intel/test_job_card.py`

- [ ] **Step 1: 写失败测试（注入 fake llm，用真 dev DB 取一个有 UGC 的公司岗）**

```python
# backend/tests/intel/test_job_card.py
import sqlite3
from app.database import SessionLocal
from app.services.intel.job_card import build_job_card

def _fake_llm(prompt: str) -> dict:
    return {"threshold": {"hard": ["x"], "soft": [], "support_ids": []},
            "compensation": {"summary": "s", "support_ids": []},
            "outlook": {"summary": "o", "support_ids": []}}

def _a_finance_job_id() -> int:
    c = sqlite3.connect("data/jobradar.db").cursor()
    # 一个有 sub_category 的金融岗（华泰/中信等，库里有 UGC）
    r = c.execute("SELECT id FROM jobs WHERE sub_category IS NOT NULL AND company LIKE '%证券%' LIMIT 1").fetchone()
    return r[0]

def test_card_has_positioning_and_three_dims():
    db = SessionLocal()
    try:
        card = build_job_card(db, _a_finance_job_id(), use_cache=False, llm_fn=_fake_llm)
    finally:
        db.close()
    assert card["positioning"]["one_liner"]
    assert set(card["intel"].keys()) == {"threshold", "compensation", "outlook"}
    # 每维带 badge
    for dim in card["intel"].values():
        assert "badge" in dim and dim["badge"] in (1, 2, 3)
    assert card["provenance"]["label"]

def test_no_ugc_job_graceful():
    db = SessionLocal()
    try:
        # 一个几乎肯定无 UGC 的冷门公司岗
        c = sqlite3.connect("data/jobradar.db").cursor()
        rid = c.execute("SELECT id FROM jobs WHERE sub_category IS NOT NULL LIMIT 1 OFFSET 5000").fetchone()
        card = build_job_card(db, rid[0], use_cache=False, llm_fn=_fake_llm)
    finally:
        db.close()
    assert card["positioning"]  # 定位段照常
    assert "intel" in card       # 不报错
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. .venv/bin/pytest tests/intel/test_job_card.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写实现**

```python
# backend/app/services/intel/job_card.py
"""卡组装器：job_id → 定位 + 3 维情报（带三维可信度徽章）+ provenance。
复用 xhs/retrieve.search 取该公司 UGC；维度抽取走 dimension_extract（LLM 可注入）。磁盘缓存。"""
from __future__ import annotations
import hashlib, json, os
from typing import Callable, Optional
from sqlalchemy.orm import Session
from app.models import Job
from app.services.xhs import retrieve
from app.services.intel import positioning as _pos
from app.services.intel.dimension_extract import extract_dimensions
from app.services.intel.badge import synth_badge
from app.services.intel.corroboration import independent_cross

_CACHE_DIR = os.path.join("data", "_intel_cache", "job_cards")

def _cache_path(job_id: int) -> str:
    os.makedirs(_CACHE_DIR, exist_ok=True)
    return os.path.join(_CACHE_DIR, f"{job_id}.json")

def _tier_from_insights(dim_ids: list[str], by_id: dict) -> dict:
    """对一个维度的支撑 insight 算三维可信度。"""
    if not dim_ids:
        return {"source_score": 0.0, "content_tier": "low", "cross": "single", "badge": 1, "n": 0}
    rows = [by_id[i] for i in dim_ids if i in by_id]
    if not rows:
        return {"source_score": 0.0, "content_tier": "low", "cross": "single", "badge": 1, "n": 0}
    avg_src = round(sum((r.get("source_score") or 0.0) for r in rows) / len(rows), 3)
    best_tier = "high" if any(r.get("confidence") == "high" for r in rows) else (
        "med" if any(r.get("confidence") == "med" for r in rows) else "low")
    # 交叉验证：把这些 insight 的 siblings（含自身）喂作者去重
    sibs = [{"note_id": r.get("insight_id", ""), "author": (r.get("source") or {}).get("author", "")} for r in rows]
    cross = independent_cross(sibs)
    badge = synth_badge(source_score=avg_src, content_tier=best_tier, cross=cross, n=len(rows))
    return {"source_score": avg_src, "content_tier": best_tier, "cross": cross, "badge": badge, "n": len(rows)}

def build_job_card(db: Session, job_id: int, *, use_cache: bool = True,
                   llm_fn: Optional[Callable[[str], dict]] = None) -> dict:
    if use_cache and os.path.exists(_cache_path(job_id)):
        with open(_cache_path(job_id), encoding="utf-8") as f:
            return json.load(f)

    job = db.query(Job).filter_by(id=job_id).first()
    if not job:
        return {"job_id": job_id, "_status": "not_found"}
    job_d = {"company": job.company, "job_title": job.job_title, "department": job.department,
             "sub_category": job.sub_category, "institution_tier": job.institution_tier}
    pos = _pos.build_positioning(job_d)

    insights = retrieve.search(db, company=[job.company or ""], limit=20)
    by_id = {i["insight_id"]: i for i in insights}

    if llm_fn is None:
        from app.services.intel.dimension_extract import _EMPTY  # 无 LLM → 空情报，定位照出
        dims = dict(_EMPTY)
    else:
        dims = extract_dimensions(insights, llm_fn=llm_fn)

    intel = {}
    for name in ("threshold", "compensation", "outlook"):
        d = dims[name]
        conf = _tier_from_insights(d.get("support_ids") or [], by_id)
        quotes = [{"text": by_id[i].get("source_quote", ""),
                   "source": (by_id[i].get("source") or {}).get("platform", ""),
                   "author": (by_id[i].get("source") or {}).get("author", "")}
                  for i in (d.get("support_ids") or [])[:2] if i in by_id]
        intel[name] = {**{k: v for k, v in d.items() if k != "support_ids"}, **conf, "quotes": quotes}

    sources = sorted({(i.get("source") or {}).get("platform", "") for i in insights} - {""})
    card = {
        "job_id": job_id, "company": job.company, "role_title": job.job_title,
        "positioning": pos, "intel": intel,
        "provenance": {"label": "学生 UGC 参考 · 非官方", "n_insights": len(insights), "sources": sources},
    }
    if use_cache:
        with open(_cache_path(job_id), "w", encoding="utf-8") as f:
            json.dump(card, f, ensure_ascii=False)
    return card
```

> 注：`retrieve.search` 返回的 dict `source` 里是否含 `platform`，实现时核对 `xhs/retrieve.py:232` 的 source 结构；缺则用 `source_score.platform_of(insight_id)` 推。

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONPATH=. .venv/bin/pytest tests/intel/test_job_card.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: commit**

```bash
git add app/services/intel/job_card.py tests/intel/test_job_card.py
git commit -m "feat(intel): 岗位情报卡组装器（定位+3维+三维可信度+provenance）"
```

---

## Task 8: API 端点 `/api/job-intel/card`

**Files:**
- Modify: `backend/app/routers/intel_enrichment.py`（加 endpoint）
- Test: `backend/tests/intel/test_job_card_api.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/intel/test_job_card_api.py
import sqlite3
from fastapi.testclient import TestClient
from app.main import app

def test_card_endpoint_returns_positioning():
    c = sqlite3.connect("data/jobradar.db").cursor()
    jid = c.execute("SELECT id FROM jobs WHERE sub_category IS NOT NULL LIMIT 1").fetchone()[0]
    client = TestClient(app)
    r = client.get(f"/api/job-intel/card?job_id={jid}")
    assert r.status_code == 200
    body = r.json()
    assert body["positioning"]["one_liner"]
    assert set(body["intel"].keys()) == {"threshold", "compensation", "outlook"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. .venv/bin/pytest tests/intel/test_job_card_api.py -v`
Expected: FAIL（404）

- [ ] **Step 3: 加 endpoint（在 `intel_enrichment.py`）**

```python
# 在 app/routers/intel_enrichment.py 顶部 import
from app.services.intel.job_card import build_job_card

# 加路由（与现有 /company-card 同 router 前缀；前缀见文件顶部 APIRouter 定义）
@router.get("/job-intel/card")
def job_intel_card(job_id: int, refresh: int = 0, db: Session = Depends(get_db)) -> dict:
    # demo 阶段 llm_fn=None → 定位照出、情报段为空骨架；接强模型/DeepSeek 后传入 llm_fn
    return build_job_card(db, job_id, use_cache=(refresh == 0), llm_fn=None)
```
> 核对该文件的 `APIRouter(prefix=...)`：若前缀已是 `/api/intel`，把路由写成 `@router.get("/../job-intel/card")` 不优雅 —— 改为在 `app/main.py` 用现有 intel router 或新挂一个 `APIRouter(prefix="/api/job-intel")`。实现时择一，保证最终路径是 `/api/job-intel/card`。

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONPATH=. .venv/bin/pytest tests/intel/test_job_card_api.py -v`
Expected: PASS

- [ ] **Step 5: 全量后端测试保持绿 + commit**

```bash
PYTHONPATH=. .venv/bin/pytest tests/intel/ -q
git add app/routers/intel_enrichment.py app/main.py tests/intel/test_job_card_api.py
git commit -m "feat(intel): GET /api/job-intel/card 端点"
```

---

## Task 9: 前端 IntelDrawer 渲染定位 + 3 维 + 徽章

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/workspace/intel/IntelDrawer.tsx`
- Modify: `resume-copilot-web/lib/api.ts`（加 `getJobIntelCard(jobId)` + `JobIntelCard` 类型）

- [ ] **Step 1: 加 API 封装 + 类型**

```ts
// resume-copilot-web/lib/api.ts
export interface JobIntelCard {
  job_id: number; company: string; role_title: string;
  positioning: { sub_category: string|null; tier: string|null; tier_label: string; track_line: string; one_liner: string };
  intel: Record<'threshold'|'compensation'|'outlook', {
    hard?: string[]; soft?: string[]; summary?: string|null;
    badge: 1|2|3; cross: 'verified'|'single'|'conflicting'; n: number;
    quotes: { text: string; source: string; author: string }[];
  }>;
  provenance: { label: string; n_insights: number; sources: string[] };
}
export async function getJobIntelCard(jobId: number): Promise<JobIntelCard> {
  const r = await fetch(`/api/job-intel/card?job_id=${jobId}`);
  if (!r.ok) throw new Error(`card ${r.status}`);
  return r.json();
}
```

- [ ] **Step 2: 在 IntelDrawer 渲染（复用已有 conflict 折叠面板 + 徽章 CSS）**

在 `IntelDrawer.tsx` 加一段渲染（定位四行 + 三维卡块）：
```tsx
// 定位段
<div className="workspace-hifi__intel-positioning">
  <div>赛道：{card.positioning.sub_category ?? '—'}</div>
  <div>梯队：{card.positioning.tier_label}</div>
  {card.positioning.track_line && <div>条线：{card.positioning.track_line}</div>}
  <div className="workspace-hifi__intel-oneliner">{card.positioning.one_liner}</div>
</div>
// 三维
{(['threshold','compensation','outlook'] as const).map((dim) => {
  const d = card.intel[dim];
  const label = {threshold:'门槛', compensation:'薪酬待遇', outlook:'前景·体验'}[dim];
  return (
    <section key={dim} className="workspace-hifi__intel-dim">
      <header>{label} <span>{'★'.repeat(d.badge)}{'☆'.repeat(3-d.badge)}</span>
        {d.cross==='verified' && <em> ✓{d.n}源印证(不同人)</em>}
        {d.cross==='conflicting' && <em className="conflict"> ⚠ 有分歧</em>}</header>
      {dim==='threshold' ? (<>
        {!!d.hard?.length && <div>硬：{d.hard.join(' · ')}</div>}
        {!!d.soft?.length && <div>软：{d.soft.join(' · ')}</div>}
      </>) : <div>{d.summary ?? '暂无足够 UGC 情报'}</div>}
      {d.quotes.map((q,i)=>(<blockquote key={i}>「{q.text}」—{q.source}</blockquote>))}
    </section>
  );
})}
<footer className="workspace-hifi__intel-prov">{card.provenance.n_insights} 条 UGC · {card.provenance.sources.join('+')} · 学生参考非官方</footer>
```
（沿用 `IntelDrawer` 现有 `[data-theme]`/`.workspace-hifi__` scope；徽章/分歧色板复用 `workspace-theme.css` 既有 `.workspace-hifi__intel-conf-badge*`。）

- [ ] **Step 3: lint + build 必过**

Run:
```bash
cd resume-copilot-web && npm run lint && npm run build
```
Expected: 0 errors，build 成功。

- [ ] **Step 4: commit**

```bash
git add resume-copilot-web/lib/api.ts resume-copilot-web/components/resume-copilot/workspace/intel/IntelDrawer.tsx
git commit -m "feat(resume-copilot-web): 岗位情报卡 — 定位+3维+三维可信度徽章渲染"
```

---

## Task 10: 端到端冒烟（demo 验收）

**Files:** 无新增（手动 + 一个冒烟脚本可选）

- [ ] **Step 1: 起 backend，取一个 GT 金融岗，curl `/api/job-intel/card`**

Run:
```bash
PYTHONPATH=. .venv/bin/uvicorn app.main:app --port 8000 &
JID=$(PYTHONPATH=. .venv/bin/python -c "import sqlite3;print(sqlite3.connect('data/jobradar.db').cursor().execute(\"SELECT id FROM jobs WHERE sub_category IS NOT NULL AND company LIKE '%证券%' LIMIT 1\").fetchone()[0])")
curl -s "http://127.0.0.1:8000/api/job-intel/card?job_id=$JID" | python3 -m json.tool | head -40
```
Expected：返回 positioning 四项齐 + intel 三维（demo 阶段 llm_fn=None → 情报段为空骨架，定位齐）。

- [ ] **Step 2: 接 LLM 真跑一张卡（强模型/DeepSeek 余额后）**

把 `job_card.build_job_card` 的 `llm_fn` 接到 DeepSeek（复用 `enrichment._call_llm` 的封装，签名适配成 `(prompt)->dict`）或免费强模型适配器，对同一个 job 重跑 `refresh=1`，确认 3 维有真要点 + 每点挂的 insight_id 命中、quote 是 verbatim。

- [ ] **Step 3: 验收清单核对（spec §10）**

- [ ] 定位 4 项齐；3 维至少 1 维有 UGC 情报；每维带 badge + ≥1 verbatim 原话
- [ ] 找到一例 verified ★★★（不同信源不同人）+ 一例单源 ★
- [ ] 一例 ⚠ 分歧
- [ ] 无 UGC 岗：定位照出、情报段优雅空、不报错
- [ ] 原话 substring 命中原 insight；provenance 标 UGC

- [ ] **Step 4: 追加 ACTIVITY.md + commit**

```bash
git add ACTIVITY.md
git commit -m "docs: SAIF 岗位情报卡 demo 端到端跑通"
```

---

## Self-Review（对照 spec）

- **Spec §3 schema** → Task 7/8 的 card dict 覆盖 positioning + intel(3维) + provenance。✅
- **Spec §4 三维可信度** → Task 1(A 信源分)/Task 3(C 交叉验证作者去重)/Task 5(合成 badge)，content_tier(B)复用 insight.confidence。✅
- **Spec §5 填充管道** → Task 6(LLM 维度抽取)+Task 7(组装，复用 retrieve.search)。✅
- **Spec §6 平台权重** → Task 1 PLATFORM_VALUE（xhs 1.0 / zhihu·bili 0.85 / podcast 0.5）。✅
- **Spec §7 定位** → Task 4。✅
- **Spec §8 前端** → Task 9。✅
- **Spec §9 YAGNI**：未补拉 author 权威/收藏（Task 1 弱版只用现有信号，注释记账）；author_id 缺用 name 近似（Task 3 注释）。✅
- **Spec §10 验收** → Task 10。✅
- **类型一致性**：`build_job_card`/`extract_dimensions`/`synth_badge`/`independent_cross`/`compute_source_score`/`build_positioning` 签名在各 task 间一致。✅
- **LLM 不卡 DeepSeek 余额**：所有机制 task 用 fixture/None llm_fn 可建可测；真 LLM 仅 Task 10 Step 2（可延后）。✅

**已知开放项（实现时核对，非占位）**：`retrieve.search` 返回 dict 的 `source` 子结构是否含 `platform`/`author`（核对 `xhs/retrieve.py:220-236`，缺则用 `platform_of` 推 + note.author_name）；新 router 前缀挂法（Task 8 Step 3 二选一保证最终路径 `/api/job-intel/card`）。
