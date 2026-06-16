# 岗位推荐 2.0 实施计划（可追踪 + 会轮换的岗位流）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给岗位推荐加一层"岗位级状态（看过/收藏想投/已投递/不合适）+ 会轮换的分页下发 + 我的岗位汇总 tab + 卡上显式日期"，让学生持续用得下去。

**Architecture:** 后端新增一张按 `(user_key, job_id)` 唯一的 `resume_job_user_state` 表承载岗位状态；推荐生成时持久化更深的有序候选池（`pool_json`），下发与"换一批"从池里排除已看过/已屏蔽再取下一页并自动标记看过；新增 `/jobs/{job_id}/state`、`/sessions/{id}/recommendations/next-batch`、`/my-jobs` 三个端点；前端推荐卡加三态按钮 + 显式日期，feed 加"换一批"，工作台加"我的岗位"tab。整套行为挂 `RECOMMENDATION_ROTATION_ENABLED` flag，默认关 = 与现状字节级一致。

**Tech Stack:** FastAPI + SQLAlchemy + SQLite(WAL) + Alembic（后端）；Next.js 16 App Router + React 19 + HiFi 设计系统（`.hf` scope，terracotta/parchment/Fraunces）（前端）。LLM 文本走 OpenCode DeepSeek。

**关键既有事实（实现前必读）**
- `user_key` 派生为 `"u_%d" % users.id`，但它**是** `resume_copilot_sessions` / `account_memory` 的列；新表也存这个字符串。会话对象上直接 `session_obj.user_key`。
- 唯一的现有岗位级状态是"拒绝"：`ResumeCopilotSession.rejected_job_ids_json`（会话级）+ reject 端点写 `account_memory.preference`。本期**保留**该端点，内部双写到新表的 `dismissed`，并一次性回填存量。
- 推荐结果存 `ResumeRecommendationRun.recommendations_json`（每会话唯一一条 run）。当前只存最终下发的 ≤20 条。
- 岗位日期：`jobs.publish_date`（真实发布时间，可空）优先，回落 `jobs.scraped_at`（收录时间）。
- demo 会话只读：每个写端点必须 `_assert_not_demo(session_obj)`；归属校验 `_assert_session_owner(session_obj, x_resume_user_key)`。
- 后端 schema 改动只走 Alembic；新迁移用 `inspector` 做幂等检查。SQLite 多个 head，迁移的 `down_revision` 用 `alembic heads` 当前结果，勿硬编。
- 端点测试范式（无 conftest）：内存 SQLite + `Base.metadata.create_all` + `app.dependency_overrides[get_db]`，见 `tests/test_recommend_reject.py`。

---

## File Structure

**后端（新建）**
- `backend/app/services/resume_copilot/job_state.py` — 岗位状态领域逻辑（纯函数 + DB upsert：标记看过 / 设置显式状态 / 查询集合 / 我的岗位分组）。单一职责，不含 HTTP / LLM。
- `backend/app/services/resume_copilot/rotation.py` — 轮换分页：从 `pool_json` 排除 seen/dismissed 取下一页、回收兜底。纯函数为主（输入池 + 排除集 → 页），DB 侧薄包装。
- `backend/alembic/versions/<rev>_job_user_state_and_pool.py` — 建 `resume_job_user_state` 表 + 给 `resume_recommendation_runs` 加 `pool_json` 列。
- `backend/scripts/_tmp_backfill_dismissed_from_rejected.py` — 一次性把存量 `rejected_job_ids_json` 回填到新表 `dismissed`（幂等）。
- 测试：`backend/tests/test_job_user_state.py` / `test_recommendation_rotation.py` / `test_my_jobs_endpoint.py` / `test_job_state_endpoint.py`。

**后端（修改）**
- `backend/app/models.py` — 加 `JobUserState` 模型 + `ResumeRecommendationRun.pool_json` 列。
- `backend/app/config.py` — 加 `RECOMMENDATION_ROTATION_ENABLED` / `ROTATION_PAGE_SIZE` / `ROTATION_POOL_SIZE`。
- `backend/app/schemas_resume_copilot.py` — `JobStateIn/Out`、`MyJobItem`、`MyJobsOut`、`ResumeRecommendationItem` 加 `posted_at`/`posted_is_publish`。
- `backend/app/routers/resume_copilot.py` — 加三端点；GET recommendations + reject 端点接状态层；下发时附日期。
- `backend/app/services/resume_copilot/workflow.py` — 生成完成时持久化 `pool_json` + 播种首页 + 标记看过（flag 开时）。

**前端（修改/新建）**
- `resume-copilot-web/components/resume-copilot/api.ts` — `markJobState` / `getMyJobs` / `nextRecommendBatch`。
- `resume-copilot-web/components/resume-copilot/types.ts` — `JobState` / `MyJobsResult` / item 加 `posted_at`。
- `resume-copilot-web/components/resume-copilot/workspace/recommend/RecommendCard.tsx` — 三态按钮 + 显式日期。
- `resume-copilot-web/components/resume-copilot/workspace/MyJobsPanel.tsx`（新）— 我的岗位 tab 视图（按 mockup）。
- feed 容器（`LeftRecommendRail.tsx` / `RecommendWorkspaceShell.tsx`）— "换一批"按钮 + 接 tab。

---

## Phase 0 — 数据与开关（后端地基）

### Task 1: `JobUserState` 模型 + `pool_json` 列 + flag

**Files:**
- Modify: `backend/app/models.py`（在 `ResumeRecommendationRun` 定义附近 + 文件末尾加新模型）
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_job_user_state.py`

- [ ] **Step 1: 写失败测试 — 模型可建表 + 唯一约束**

```python
# backend/tests/test_job_user_state.py
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import JobUserState


def _mk_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_unique_user_job():
    db = _mk_session()
    db.add(JobUserState(user_key="u_5", job_id="j1", state="seen"))
    db.commit()
    db.add(JobUserState(user_key="u_5", job_id="j1", state="saved"))
    with pytest.raises(IntegrityError):
        db.commit()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_job_user_state.py::test_unique_user_job -x`
Expected: FAIL — `ImportError: cannot import name 'JobUserState'`

- [ ] **Step 3: 加模型 + 列**

在 `backend/app/models.py` 文件末尾（其它模型之后）加：

```python
class JobUserState(Base):
    """岗位级用户状态 — 按 (user_key, job_id) 唯一，跟随用户跨会话。

    state ∈ {seen, saved, applied, dismissed}：
      - seen 隐式（下发即标记），用于轮换排除；
      - saved/applied/dismissed 显式且互斥（同一岗同一时刻只一个）。
    本期纯做追踪展示，不回流推荐算法（见设计稿 2026-06-16 §七.4）。
    """

    __tablename__ = "resume_job_user_state"
    __table_args__ = (
        UniqueConstraint("user_key", "job_id", name="uq_job_user_state_user_job"),
    )

    id = Column(Integer, primary_key=True)
    user_key = Column(Text, nullable=False, index=True)
    job_id = Column(Text, nullable=False, index=True)
    state = Column(Text, nullable=False, default="seen")
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    state_updated_at = Column(DateTime, default=datetime.utcnow)
    source_session_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
```

确认 `models.py` 顶部已 import `UniqueConstraint`（与其它 `Column`/`ForeignKey` 同来源 `from sqlalchemy import ...`）；若没有就加进去。

在 `ResumeRecommendationRun` 类里（`recommendations_json` 列旁）加：

```python
    # 推荐 2.0 轮换:完整有序候选池(item dict 列表 JSON)。recommendations_json 仍是
    # "当前下发页",pool_json 是可翻的全池。flag OFF 时不写,留 None=兼容旧行为。
    pool_json = Column(Text, nullable=True)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_job_user_state.py::test_unique_user_job -x`
Expected: PASS

- [ ] **Step 5: 加 flag**

在 `backend/app/config.py`（与其它 `RECOMMENDATION_*` flag 同段）加：

```python
# 推荐 2.0 — 岗位级状态 + 轮换。默认 OFF = 与现状字节级一致(单页下发,无状态层)。
RECOMMENDATION_ROTATION_ENABLED = os.getenv("RECOMMENDATION_ROTATION_ENABLED", "0") == "1"
ROTATION_PAGE_SIZE = int(os.getenv("ROTATION_PAGE_SIZE", "12"))   # 每页下发数
ROTATION_POOL_SIZE = int(os.getenv("ROTATION_POOL_SIZE", "100"))  # 持久化的候选池上限
```

确认 `config.py` 顶部已 `import os`。

- [ ] **Step 6: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/models.py backend/app/config.py backend/tests/test_job_user_state.py
git commit -m "feat(reco2): JobUserState 模型 + pool_json 列 + rotation flag"
```

---

### Task 2: Alembic 迁移（建表 + 加列，幂等）

**Files:**
- Create: `backend/alembic/versions/<rev>_job_user_state_and_pool.py`

- [ ] **Step 1: 取当前 head 作 down_revision**

Run: `cd backend && PYTHONPATH=. .venv/bin/alembic heads`
记下输出的 revision id（若有多个 head 先 `alembic merge` 不在本计划范围——取与本仓主线一致那个；dev 上通常单一 head）。把它填进下面的 `down_revision`。

- [ ] **Step 2: 写迁移文件**

```python
# backend/alembic/versions/jus20260616_job_user_state_and_pool.py
"""resume_job_user_state table + recommendation_runs.pool_json

Revision ID: jus20260616
Revises: <PASTE_CURRENT_HEAD>
Create Date: 2026-06-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "jus20260616"
down_revision: Union[str, Sequence[str], None] = "<PASTE_CURRENT_HEAD>"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    if "resume_job_user_state" not in insp.get_table_names():
        op.create_table(
            "resume_job_user_state",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_key", sa.Text(), nullable=False),
            sa.Column("job_id", sa.Text(), nullable=False),
            sa.Column("state", sa.Text(), nullable=False, server_default="seen"),
            sa.Column("first_seen_at", sa.DateTime(), nullable=True),
            sa.Column("state_updated_at", sa.DateTime(), nullable=True),
            sa.Column("source_session_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("user_key", "job_id", name="uq_job_user_state_user_job"),
        )
        op.create_index("ix_job_user_state_user_key", "resume_job_user_state", ["user_key"])
        op.create_index("ix_job_user_state_job_id", "resume_job_user_state", ["job_id"])
    cols = [c["name"] for c in insp.get_columns("resume_recommendation_runs")]
    if "pool_json" not in cols:
        op.add_column("resume_recommendation_runs", sa.Column("pool_json", sa.Text(), nullable=True))


def downgrade() -> None:
    pass
```

- [ ] **Step 3: 跑迁移到 dev DB**

Run: `cd backend && PYTHONPATH=. .venv/bin/alembic upgrade head`
Expected: 无报错；`Running upgrade ... -> jus20260616`

- [ ] **Step 4: 验证表存在**

Run: `cd backend && .venv/bin/python -c "import sqlite3;c=sqlite3.connect('data/jobradar.db');print('resume_job_user_state' in [r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")]);print('pool_json' in [r[1] for r in c.execute('PRAGMA table_info(resume_recommendation_runs)')])"`
Expected: `True` 和 `True`

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/jus20260616_job_user_state_and_pool.py
git commit -m "feat(reco2): alembic — resume_job_user_state + pool_json"
```

---

## Phase 1 — 状态领域逻辑 + 端点

### Task 3: `job_state.py` 领域逻辑

**Files:**
- Create: `backend/app/services/resume_copilot/job_state.py`
- Test: `backend/tests/test_job_user_state.py`（追加）

状态常量与函数契约（后续任务依赖这些名字）：
- `STATE_SEEN="seen"`, `STATE_SAVED="saved"`, `STATE_APPLIED="applied"`, `STATE_DISMISSED="dismissed"`
- `EXPLICIT_STATES = {STATE_SAVED, STATE_APPLIED, STATE_DISMISSED}`
- `mark_seen(db, user_key, job_ids, source_session_id=None) -> int`：对每个还没有任何状态行的 job_id 插一条 `seen`；已有行（不论什么状态）不动。返回新插入数。
- `set_explicit_state(db, user_key, job_id, state, source_session_id=None) -> JobUserState`：upsert 到显式状态（必须 ∈ EXPLICIT_STATES）。已有行就改 `state` + `state_updated_at`；没有就插。
- `clear_explicit_state(db, user_key, job_id) -> None`：把显式状态降回 `seen`（保留行，便于仍算"看过"）。
- `seen_or_dismissed_ids(db, user_key) -> set[str]`：轮换排除集（seen + saved + applied + dismissed 全算"出现过"；轮换要的是"没出现过的新岗"，所以排除集 = 所有有行的 job_id）。
- `states_map(db, user_key) -> dict[str, str]`：job_id → state。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_job_user_state.py` 追加：

```python
from app.services.resume_copilot import job_state as js


def test_mark_seen_idempotent_and_preserves_explicit():
    db = _mk_session()
    assert js.mark_seen(db, "u_5", ["a", "b"]) == 2
    # 再标记 a,c：a 已存在不动，c 新增 → 只 +1
    assert js.mark_seen(db, "u_5", ["a", "c"]) == 1
    # 把 a 设成 saved，再 mark_seen 不能把它打回 seen
    js.set_explicit_state(db, "u_5", "a", js.STATE_SAVED)
    js.mark_seen(db, "u_5", ["a"])
    assert js.states_map(db, "u_5")["a"] == "saved"


def test_set_explicit_mutual_exclusive_and_clear():
    db = _mk_session()
    js.set_explicit_state(db, "u_5", "a", js.STATE_SAVED)
    js.set_explicit_state(db, "u_5", "a", js.STATE_APPLIED)  # 切换，不新增行
    m = js.states_map(db, "u_5")
    assert m["a"] == "applied"
    js.clear_explicit_state(db, "u_5", "a")
    assert js.states_map(db, "u_5")["a"] == "seen"


def test_exclusion_set():
    db = _mk_session()
    js.mark_seen(db, "u_5", ["a", "b"])
    js.set_explicit_state(db, "u_5", "c", js.STATE_DISMISSED)
    assert js.seen_or_dismissed_ids(db, "u_5") == {"a", "b", "c"}


def test_set_explicit_rejects_bad_state():
    db = _mk_session()
    import pytest
    with pytest.raises(ValueError):
        js.set_explicit_state(db, "u_5", "a", "seen")  # seen 不是显式态
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_job_user_state.py -x`
Expected: FAIL — `ModuleNotFoundError: ...job_state`

- [ ] **Step 3: 写实现**

```python
# backend/app/services/resume_copilot/job_state.py
"""岗位级用户状态领域逻辑(推荐 2.0)。

纯 DB upsert + 集合查询,不含 HTTP / LLM。每个调用方自己持有 Session。
state 互斥规则与设计稿 2026-06-16 §3.1 一致。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import JobUserState

STATE_SEEN = "seen"
STATE_SAVED = "saved"
STATE_APPLIED = "applied"
STATE_DISMISSED = "dismissed"
EXPLICIT_STATES = {STATE_SAVED, STATE_APPLIED, STATE_DISMISSED}
ALL_STATES = EXPLICIT_STATES | {STATE_SEEN}


def _rows(db: Session, user_key: str):
    return db.query(JobUserState).filter(JobUserState.user_key == user_key)


def states_map(db: Session, user_key: str) -> dict[str, str]:
    return {r.job_id: r.state for r in _rows(db, user_key)}


def seen_or_dismissed_ids(db: Session, user_key: str) -> set[str]:
    """轮换排除集 = 该用户已有任何状态行的全部 job_id(出现过即不再算"新")。"""
    return {r.job_id for r in _rows(db, user_key)}


def mark_seen(db: Session, user_key: str, job_ids, source_session_id=None) -> int:
    """对没有任何状态行的 job_id 插 seen;已有行(任何状态)保持不动。返回新增数。"""
    if not user_key or not job_ids:
        return 0
    existing = {r.job_id for r in _rows(db, user_key).filter(JobUserState.job_id.in_(list(job_ids)))}
    now = datetime.utcnow()
    n = 0
    for jid in job_ids:
        jid = str(jid)
        if jid in existing:
            continue
        db.add(JobUserState(
            user_key=user_key, job_id=jid, state=STATE_SEEN,
            first_seen_at=now, state_updated_at=now, source_session_id=source_session_id,
            created_at=now, updated_at=now,
        ))
        existing.add(jid)
        n += 1
    db.commit()
    return n


def set_explicit_state(db: Session, user_key: str, job_id: str, state: str, source_session_id=None) -> JobUserState:
    if state not in EXPLICIT_STATES:
        raise ValueError(f"state must be one of {sorted(EXPLICIT_STATES)}, got {state!r}")
    job_id = str(job_id)
    now = datetime.utcnow()
    row = _rows(db, user_key).filter(JobUserState.job_id == job_id).first()
    if row is None:
        row = JobUserState(
            user_key=user_key, job_id=job_id, state=state,
            first_seen_at=now, source_session_id=source_session_id, created_at=now,
        )
        db.add(row)
    else:
        row.state = state
    row.state_updated_at = now
    row.updated_at = now
    db.commit()
    db.refresh(row)
    return row


def clear_explicit_state(db: Session, user_key: str, job_id: str) -> None:
    """显式状态降回 seen(保留行 → 仍算看过)。无行则无操作。"""
    row = _rows(db, user_key).filter(JobUserState.job_id == str(job_id)).first()
    if row is None:
        return
    row.state = STATE_SEEN
    row.state_updated_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    db.commit()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_job_user_state.py -x`
Expected: PASS（4 个用例全绿）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/resume_copilot/job_state.py backend/tests/test_job_user_state.py
git commit -m "feat(reco2): job_state 领域逻辑(标记看过/三态互斥/排除集)"
```

---

### Task 4: `POST /jobs/{job_id}/state` 端点 + schema

**Files:**
- Modify: `backend/app/schemas_resume_copilot.py`
- Modify: `backend/app/routers/resume_copilot.py`
- Test: `backend/tests/test_job_state_endpoint.py`

端点契约：`POST /api/resume-copilot/sessions/{session_id}/jobs/{job_id}/state`，body `{"state": "saved"}`（`saved|applied|dismissed`，或 `""` 表示清除回 seen）。挂在 session 下以复用归属/ demo 校验。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_job_state_endpoint.py
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import ResumeCopilotSession
from app.services.resume_copilot import job_state as js


def _client():
    from app.routers import resume_copilot
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sl = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    app = FastAPI()
    app.include_router(resume_copilot.router)
    def _ov():
        db = sl()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = _ov
    return TestClient(app), sl


def _seed_session(sl, user_key="u_9", demo=False):
    db = sl()
    s = ResumeCopilotSession(user_key="__demo__" if demo else user_key, name="t")
    db.add(s); db.commit(); db.refresh(s)
    sid = s.id
    db.close()
    return sid


def test_set_and_clear_state():
    client, sl = _client()
    sid = _seed_session(sl)
    r = client.post(f"/sessions/{sid}/jobs/j1/state", json={"state": "saved"},
                    headers={"X-Resume-User-Key": "u_9"})
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "saved"
    db = sl(); assert js.states_map(db, "u_9")["j1"] == "saved"; db.close()
    # clear
    r2 = client.post(f"/sessions/{sid}/jobs/j1/state", json={"state": ""},
                     headers={"X-Resume-User-Key": "u_9"})
    assert r2.status_code == 200
    db = sl(); assert js.states_map(db, "u_9")["j1"] == "seen"; db.close()


def test_demo_session_forbidden():
    client, sl = _client()
    sid = _seed_session(sl, demo=True)
    r = client.post(f"/sessions/{sid}/jobs/j1/state", json={"state": "saved"},
                    headers={"X-Resume-User-Key": "__demo__"})
    assert r.status_code == 403


def test_bad_state_422():
    client, sl = _client()
    sid = _seed_session(sl)
    r = client.post(f"/sessions/{sid}/jobs/j1/state", json={"state": "loved"},
                    headers={"X-Resume-User-Key": "u_9"})
    assert r.status_code == 422
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_job_state_endpoint.py -x`
Expected: FAIL — 404（端点不存在）

- [ ] **Step 3: 加 schema**

在 `backend/app/schemas_resume_copilot.py`（reject schema 附近）加：

```python
class JobStateIn(BaseModel):
    # "" = 清除(降回 seen);否则必须是 saved/applied/dismissed
    state: str = ""


class JobStateOut(BaseModel):
    ok: bool
    job_id: str
    state: str  # 当前生效状态(清除后为 "seen")
```

- [ ] **Step 4: 加端点**

在 `backend/app/routers/resume_copilot.py`（reject 端点附近）加。确认文件顶部已 import `JobStateIn, JobStateOut`（加到现有 `from app.schemas_resume_copilot import (...)` 块）。

```python
@router.post('/sessions/{session_id}/jobs/{job_id}/state', response_model=JobStateOut)
def post_job_state(
    session_id: int,
    job_id: str,
    payload: JobStateIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
) -> JobStateOut:
    """推荐 2.0:设置/清除某岗位的显式状态(收藏想投/已投递/不合适)。

    state="" → 清除回 seen。state ∈ {saved,applied,dismissed} → upsert。
    纯追踪,不回流推荐算法(设计稿 2026-06-16 §七.4)。
    """
    from app.services.resume_copilot import job_state as js

    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)

    user_key = str(getattr(session_obj, 'user_key', '') or '')
    state = (payload.state or '').strip()
    if state == '':
        js.clear_explicit_state(db, user_key, job_id)
        return JobStateOut(ok=True, job_id=str(job_id), state=js.STATE_SEEN)
    if state not in js.EXPLICIT_STATES:
        raise HTTPException(status_code=422, detail=f'INVALID_STATE: {state}')
    row = js.set_explicit_state(db, user_key, job_id, state, source_session_id=session_id)
    return JobStateOut(ok=True, job_id=str(job_id), state=row.state)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_job_state_endpoint.py -x`
Expected: PASS（3 用例）

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas_resume_copilot.py backend/app/routers/resume_copilot.py backend/tests/test_job_state_endpoint.py
git commit -m "feat(reco2): POST /jobs/{id}/state 端点(三态+清除,demo 403)"
```

---

### Task 5: reject 端点双写 + 存量回填脚本

**Files:**
- Modify: `backend/app/routers/resume_copilot.py`（reject 端点尾部）
- Create: `backend/scripts/_tmp_backfill_dismissed_from_rejected.py`
- Test: `backend/tests/test_recommend_reject.py`（追加一个断言）

- [ ] **Step 1: 写失败测试 — reject 同时写 dismissed**

在 `backend/tests/test_recommend_reject.py` 找到 happy-path 测试函数，在它断言 `rejected_count` 之后追加（沿用该测试已造好的 `client`/`sl`/`session_id`/`job_id`/user_key 变量名；若变量名不同按文件实际改）：

```python
    # 推荐 2.0:reject 应同时把该岗写进 resume_job_user_state=dismissed
    from app.services.resume_copilot import job_state as js
    _db = sl()
    assert js.states_map(_db, user_key).get(job_id) == "dismissed"
    _db.close()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_recommend_reject.py -x -k happy or true`
（用该文件 happy-path 用例名）Expected: FAIL — `dismissed` 未写

- [ ] **Step 3: reject 端点尾部双写**

在 `post_reject_recommendation` 的 `db.commit()`（追加 rejected_job_ids 之后那个）**之前**插入：

```python
    # 推荐 2.0:同源写新状态表(dismissed),便于"我的岗位"聚合 + 轮换排除。
    # 不改既有 account_memory / rejected_job_ids_json 行为。
    try:
        from app.services.resume_copilot import job_state as js
        if user_key:
            js.set_explicit_state(db, user_key, str(job_id), js.STATE_DISMISSED, source_session_id=session_id)
    except Exception:
        pass  # 双写失败不阻断既有拒绝流
```

> 注：`set_explicit_state` 内部自带 `db.commit()`，与端点末尾的 commit 不冲突。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_recommend_reject.py -x`
Expected: PASS（含新断言；原有用例不退）

- [ ] **Step 5: 写回填脚本**

```python
# backend/scripts/_tmp_backfill_dismissed_from_rejected.py
"""一次性:把存量 ResumeCopilotSession.rejected_job_ids_json 回填到
resume_job_user_state(state=dismissed)。幂等(set_explicit_state upsert)。"""
import json
import sys

sys.path.insert(0, ".")
from app.database import SessionLocal
from app.models import ResumeCopilotSession
from app.services.resume_copilot import job_state as js

db = SessionLocal()
n_sessions = n_jobs = 0
for s in db.query(ResumeCopilotSession).all():
    uk = str(getattr(s, "user_key", "") or "")
    if not uk or uk in ("__demo__", "__guest__"):
        continue
    try:
        ids = json.loads(str(getattr(s, "rejected_job_ids_json", "[]") or "[]"))
    except json.JSONDecodeError:
        ids = []
    if not ids:
        continue
    n_sessions += 1
    for jid in ids:
        js.set_explicit_state(db, uk, str(jid), js.STATE_DISMISSED, source_session_id=s.id)
        n_jobs += 1
print(f"✅ 回填 {n_jobs} 条 dismissed,涉及 {n_sessions} 个会话")
db.close()
```

- [ ] **Step 6: 跑回填(dev DB) + 验证**

Run: `cd backend && PYTHONPATH=. .venv/bin/python scripts/_tmp_backfill_dismissed_from_rejected.py`
Expected: 打印 `✅ 回填 N 条 dismissed ...`

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/resume_copilot.py backend/tests/test_recommend_reject.py backend/scripts/_tmp_backfill_dismissed_from_rejected.py
git commit -m "feat(reco2): reject 双写 dismissed + 存量回填脚本"
```

---

### Task 6: `GET /my-jobs` 端点

**Files:**
- Modify: `backend/app/schemas_resume_copilot.py`
- Modify: `backend/app/services/resume_copilot/job_state.py`（加分组聚合）
- Modify: `backend/app/routers/resume_copilot.py`
- Test: `backend/tests/test_my_jobs_endpoint.py`

端点：`GET /api/resume-copilot/my-jobs`（按 `X-Resume-User-Key` 取该用户全部显式状态，join `jobs` 取展示字段）。返回 saved/applied/dismissed 三组 + 计数。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_my_jobs_endpoint.py
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Job
from app.services.resume_copilot import job_state as js


def _client():
    from app.routers import resume_copilot
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sl = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    app = FastAPI(); app.include_router(resume_copilot.router)
    def _ov():
        db = sl()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = _ov
    return TestClient(app), sl


def test_my_jobs_grouped():
    client, sl = _client()
    db = sl()
    db.add(Job(job_id="j1", company="中金", job_title="量化研究员", location="上海", detail_url="http://x/1"))
    db.add(Job(job_id="j2", company="幻方", job_title="策略实习", location="杭州", detail_url="http://x/2"))
    db.commit()
    js.set_explicit_state(db, "u_9", "j1", js.STATE_SAVED)
    js.set_explicit_state(db, "u_9", "j2", js.STATE_APPLIED)
    js.mark_seen(db, "u_9", ["j3"])  # 纯 seen 不进任何组
    db.close()

    r = client.get("/my-jobs", headers={"X-Resume-User-Key": "u_9"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["counts"] == {"saved": 1, "applied": 1, "dismissed": 0}
    assert body["saved"][0]["company"] == "中金"
    assert body["applied"][0]["job_id"] == "j2"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_my_jobs_endpoint.py -x`
Expected: FAIL — 404

- [ ] **Step 3: 加聚合函数到 job_state.py**

```python
def my_jobs_grouped(db: Session, user_key: str) -> dict:
    """按显式状态分组,join jobs 取展示字段。seen 不进任何组。

    返回 {saved:[...], applied:[...], dismissed:[...], counts:{...}}。
    每个 item:{job_id, company, job_title, location, detail_url, publish_date, scraped_at}。
    """
    from app.models import Job  # 局部 import 避免循环

    rows = [r for r in _rows(db, user_key) if r.state in EXPLICIT_STATES]
    job_ids = [r.job_id for r in rows]
    jobs = {j.job_id: j for j in db.query(Job).filter(Job.job_id.in_(job_ids))} if job_ids else {}
    groups: dict[str, list] = {STATE_SAVED: [], STATE_APPLIED: [], STATE_DISMISSED: []}
    # 按 state_updated_at 倒序(最近操作在前)
    for r in sorted(rows, key=lambda x: (x.state_updated_at or x.created_at), reverse=True):
        j = jobs.get(r.job_id)
        groups[r.state].append({
            "job_id": r.job_id,
            "company": getattr(j, "company", "") or "",
            "job_title": getattr(j, "job_title", "") or "",
            "location": getattr(j, "location", "") or "",
            "detail_url": getattr(j, "detail_url", "") or "",
            "publish_date": (j.publish_date.isoformat() if j and j.publish_date else ""),
            "scraped_at": (j.scraped_at.isoformat() if j and j.scraped_at else ""),
        })
    return {
        **groups,
        "counts": {k: len(v) for k, v in groups.items()},
    }
```

- [ ] **Step 4: 加 schema**

在 `backend/app/schemas_resume_copilot.py` 加：

```python
class MyJobItem(BaseModel):
    job_id: str
    company: str = ''
    job_title: str = ''
    location: str = ''
    detail_url: str = ''
    publish_date: str = ''
    scraped_at: str = ''


class MyJobsCounts(BaseModel):
    saved: int = 0
    applied: int = 0
    dismissed: int = 0


class MyJobsOut(BaseModel):
    saved: list[MyJobItem] = []
    applied: list[MyJobItem] = []
    dismissed: list[MyJobItem] = []
    counts: MyJobsCounts
```

- [ ] **Step 5: 加端点**

确认 router 顶部 import `MyJobsOut`。加：

```python
@router.get('/my-jobs', response_model=MyJobsOut)
def get_my_jobs(
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
) -> MyJobsOut:
    """推荐 2.0:按 user_key 聚合该用户标记过的岗位(收藏想投/已投递/不合适)。"""
    from app.services.resume_copilot import job_state as js
    user_key = (x_resume_user_key or '').strip()
    if not user_key:
        return MyJobsOut(counts=MyJobsCounts())
    grouped = js.my_jobs_grouped(db, user_key)
    return MyJobsOut(**grouped)
```

确认顶部也 import 了 `MyJobsCounts`。

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_my_jobs_endpoint.py -x`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas_resume_copilot.py backend/app/services/resume_copilot/job_state.py backend/app/routers/resume_copilot.py backend/tests/test_my_jobs_endpoint.py
git commit -m "feat(reco2): GET /my-jobs 分组聚合端点"
```

---

## Phase 2 — 轮换下发

### Task 7: 轮换分页纯函数 `rotation.py`

**Files:**
- Create: `backend/app/services/resume_copilot/rotation.py`
- Test: `backend/tests/test_recommendation_rotation.py`

`next_page(pool, exclude_ids, page_size) -> (page, recycled)`：
- pool = item dict 列表（有序）。先取 `job_id ∉ exclude_ids` 的前 `page_size` 条 → `(page, recycled=False)`。
- 若一条未看过的都没有（全看过）→ 回收：从 pool 里取**在 exclude_ids 内**的前 `page_size` 条（保持池序）→ `(page, recycled=True)`。
- pool 为空 → `([], False)`。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_recommendation_rotation.py
from app.services.resume_copilot.rotation import next_page


def _pool(n):
    return [{"job_id": f"j{i}"} for i in range(n)]


def test_first_page_excludes_seen():
    page, recycled = next_page(_pool(5), exclude_ids={"j0", "j1"}, page_size=2)
    assert [p["job_id"] for p in page] == ["j2", "j3"]
    assert recycled is False


def test_recycle_when_all_seen():
    page, recycled = next_page(_pool(3), exclude_ids={"j0", "j1", "j2"}, page_size=2)
    assert [p["job_id"] for p in page] == ["j0", "j1"]
    assert recycled is True


def test_empty_pool():
    assert next_page([], exclude_ids=set(), page_size=5) == ([], False)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_recommendation_rotation.py -x`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 写实现**

```python
# backend/app/services/resume_copilot/rotation.py
"""推荐 2.0 轮换分页 — 纯函数(无 DB)。

从有序候选池排除"已看过/已屏蔽"取下一页;全看过则回收最旧(池序)兜底。
"""
from __future__ import annotations


def next_page(pool: list[dict], exclude_ids: set[str], page_size: int):
    """返回 (page, recycled)。

    page: 下一批 item dict(≤page_size)。
    recycled: True 表示池里已无未看过的,这页是回收的旧岗(前端据此提示)。
    """
    if not pool:
        return [], False
    fresh = [it for it in pool if str(it.get("job_id", "")) not in exclude_ids]
    if fresh:
        return fresh[:page_size], False
    return pool[:page_size], True
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_recommendation_rotation.py -x`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/resume_copilot/rotation.py backend/tests/test_recommendation_rotation.py
git commit -m "feat(reco2): rotation.next_page 纯函数(排除已看过+回收兜底)"
```

---

### Task 8: 生成时持久化 pool + 播种首页（workflow）

**Files:**
- Modify: `backend/app/services/resume_copilot/workflow.py`（`run_resume_generate_workflow` 写 `recommendations_json` 处附近）
- Test: 复用现有 workflow 测试 + 手动 dev 验证（workflow 跑真 LLM，难单测，故以 flag-off 不变 + flag-on dev 冒烟为准）

逻辑（flag 开时）：在把最终 items 写进 `recommendation_run.recommendations_json` 的地方，改为：
1. 拿到"更深的有序池"——优先用 dispatcher 已算出的更长有序候选（若只拿得到最终 20 条，则池=这 20 条，MVP 可接受，后续 Task 可加深）；截断到 `ROTATION_POOL_SIZE`。
2. 写 `recommendation_run.pool_json = json.dumps(pool)`。
3. 首页 = `rotation.next_page(pool, exclude_ids=已看过, page_size=ROTATION_PAGE_SIZE)`；`recommendations_json = json.dumps(first_page)`。
4. `job_state.mark_seen(db, user_key, [首页 job_id...], session_id)`。

- [ ] **Step 1: 定位写入点**

Run: `cd backend && grep -n "recommendations_json" app/services/resume_copilot/workflow.py`
找到给 `recommendation_run.recommendations_json` 赋最终结果的那一行（记下行号）。

- [ ] **Step 2: 在该写入点替换为 flag 分支**

把"直接写 recommendations_json = 全部 items"改成（`items` 为该处已算好的最终推荐 dict 列表；`session` / `db` / `recommendation_run` 为该作用域已有对象）：

```python
        from app import config as _cfg
        if getattr(_cfg, 'RECOMMENDATION_ROTATION_ENABLED', False):
            from app.services.resume_copilot import job_state as _js
            from app.services.resume_copilot.rotation import next_page as _next_page
            _user_key = str(getattr(session, 'user_key', '') or '')
            _pool = items[: _cfg.ROTATION_POOL_SIZE]
            recommendation_run.pool_json = json.dumps(_pool, ensure_ascii=False)
            _exclude = _js.seen_or_dismissed_ids(db, _user_key) if _user_key else set()
            _page, _ = _next_page(_pool, _exclude, _cfg.ROTATION_PAGE_SIZE)
            recommendation_run.recommendations_json = json.dumps(_page, ensure_ascii=False)
            if _user_key and _page:
                _js.mark_seen(db, _user_key, [str(p.get('job_id', '')) for p in _page], session.id)
        else:
            recommendation_run.recommendations_json = json.dumps(items, ensure_ascii=False)
```

> 若原代码用的不是 `json.dumps(items, ...)` 而是别的序列化（如 `[it.model_dump() for it in ...]`），保持 else 分支与原逻辑**逐字一致**，只在 if 分支里用同样的序列化产物作 `_pool`/`items`。

- [ ] **Step 3: flag-off 回归(不变)**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_resume_recommendation_service.py tests/test_recommend_progress.py -x`
Expected: PASS（flag 默认 off，行为不变）

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/resume_copilot/workflow.py
git commit -m "feat(reco2): workflow 持久化 pool_json + 播种首页 + 标记看过(flag-gated)"
```

---

### Task 9: `next-batch` 端点 + GET 附日期

**Files:**
- Modify: `backend/app/schemas_resume_copilot.py`（item 加日期字段）
- Modify: `backend/app/routers/resume_copilot.py`（新端点 + GET 附日期）
- Test: `backend/tests/test_recommendation_rotation.py`（追加端点级用例）

- [ ] **Step 1: item 加日期字段**

在 `ResumeRecommendationItem`（`schemas_resume_copilot.py:205+`）加：

```python
    # 推荐 2.0:显式日期。posted_at = publish_date(优先) 或 scraped_at 的 ISO 串;
    # posted_is_publish=True 表示是真实发布日(文案"发布于"),否则收录日("收录于")。
    posted_at: str = ''
    posted_is_publish: bool = False
```

- [ ] **Step 2: 写失败测试（端点级）**

在 `backend/tests/test_recommendation_rotation.py` 追加：

```python
import json as _json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.models import ResumeCopilotSession, ResumeRecommendationRun, Job
from app.services.resume_copilot import job_state as js


def _client():
    from app.routers import resume_copilot
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    sl = sessionmaker(bind=eng); Base.metadata.create_all(bind=eng)
    app = FastAPI(); app.include_router(resume_copilot.router)
    def _ov():
        db = sl()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = _ov
    return TestClient(app), sl


def test_next_batch_advances_and_marks_seen(monkeypatch):
    from app import config
    monkeypatch.setattr(config, "RECOMMENDATION_ROTATION_ENABLED", True)
    monkeypatch.setattr(config, "ROTATION_PAGE_SIZE", 2)
    client, sl = _client()
    db = sl()
    s = ResumeCopilotSession(user_key="u_9", name="t"); db.add(s); db.commit(); db.refresh(s)
    sid = s.id
    pool = [{"job_id": f"j{i}", "company": "C", "job_title": "T", "location": "",
             "detail_url": "", "objective_score": 0, "preference_score": 0,
             "base_job_score": 0, "company_priority_score": 0, "final_score": 50} for i in range(5)]
    db.add(ResumeRecommendationRun(session_id=sid, status="completed",
                                   recommendations_json="[]", pool_json=_json.dumps(pool)))
    db.commit(); db.close()

    r = client.post(f"/sessions/{sid}/recommendations/next-batch", headers={"X-Resume-User-Key": "u_9"})
    assert r.status_code == 200, r.text
    ids1 = [it["job_id"] for it in r.json()["items"]]
    assert ids1 == ["j0", "j1"]
    r2 = client.post(f"/sessions/{sid}/recommendations/next-batch", headers={"X-Resume-User-Key": "u_9"})
    ids2 = [it["job_id"] for it in r2.json()["items"]]
    assert ids2 == ["j2", "j3"]  # 不重叠,推进了
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_recommendation_rotation.py::test_next_batch_advances_and_marks_seen -x`
Expected: FAIL — 404

- [ ] **Step 4: 写日期附着 helper + next-batch 端点 + GET 接日期**

在 `backend/app/routers/resume_copilot.py` 加 helper（放在 reject 端点附近）：

```python
def _attach_posted_dates(db: Session, items: list) -> None:
    """给 ResumeRecommendationItem 列表填 posted_at / posted_is_publish(就地)。"""
    from app.models import Job
    ids = [str(getattr(it, 'job_id', '') or '') for it in items]
    if not ids:
        return
    jobs = {j.job_id: j for j in db.query(Job).filter(Job.job_id.in_(ids))}
    for it in items:
        j = jobs.get(str(getattr(it, 'job_id', '') or ''))
        if not j:
            continue
        if getattr(j, 'publish_date', None):
            it.posted_at = j.publish_date.isoformat()
            it.posted_is_publish = True
        elif getattr(j, 'scraped_at', None):
            it.posted_at = j.scraped_at.isoformat()
            it.posted_is_publish = False
```

next-batch 端点：

```python
@router.post('/sessions/{session_id}/recommendations/next-batch',
             response_model=ResumeRecommendationResultOut)
def post_recommendations_next_batch(
    session_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
) -> ResumeRecommendationResultOut:
    """推荐 2.0「换一批」:从 pool_json 排除已看过/已屏蔽取下一页,设为当前页并标记看过。"""
    from app.services.resume_copilot import job_state as js
    from app.services.resume_copilot.rotation import next_page
    from app import config

    session_obj = _get_session_or_404(db, session_id)
    _assert_session_owner(session_obj, x_resume_user_key)
    _assert_not_demo(session_obj)

    run = db.query(ResumeRecommendationRun).filter(
        ResumeRecommendationRun.session_id == session_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f'NO_RECOMMENDATIONS: {session_id}')
    try:
        pool = json.loads(str(getattr(run, 'pool_json', '[]') or '[]'))
    except json.JSONDecodeError:
        pool = []
    user_key = str(getattr(session_obj, 'user_key', '') or '')
    exclude = js.seen_or_dismissed_ids(db, user_key) if user_key else set()
    page, recycled = next_page(pool, exclude, config.ROTATION_PAGE_SIZE)
    run.recommendations_json = json.dumps(page, ensure_ascii=False)
    run.updated_at = datetime.utcnow()
    db.commit()
    if user_key and page:
        js.mark_seen(db, user_key, [str(p.get('job_id', '')) for p in page], session_id)

    items = [ResumeRecommendationItem.model_validate(it) for it in page]
    _attach_posted_dates(db, items)
    return ResumeRecommendationResultOut(
        session_id=session_id,
        status=str(getattr(run, 'status', '') or ''),
        agent_trace=[],
        used_ai=bool(getattr(run, 'used_ai', 0)),
        fallback_reason=('recycled' if recycled else ''),
        error_message='',
        items=items,
    )
```

在 GET `get_resume_copilot_recommendations` 的 `items=[...]` 构造后、return 之前，给 items 附日期。把 return 改成先建 items 变量：

```python
    items = [ResumeRecommendationItem.model_validate(item) for item in json.loads(str(recommendations_json))]
    _attach_posted_dates(db, items)
    return ResumeRecommendationResultOut(
        session_id=session_id,
        status=str(getattr(recommendation_run, 'status', '') or ''),
        agent_trace=[ResumeAgentTraceItem.model_validate(item) for item in json.loads(str(getattr(recommendation_run, 'agent_trace_json', '[]') or '[]'))],
        used_ai=bool(getattr(recommendation_run, 'used_ai', 0)),
        fallback_reason=str(getattr(recommendation_run, 'fallback_reason', '') or ''),
        error_message=str(getattr(recommendation_run, 'error_message', '') or ''),
        items=items,
    )
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_recommendation_rotation.py -x`
Expected: PASS（含 next-batch 推进用例）

- [ ] **Step 6: 全后端回归**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/ -q`
Expected: 全绿（无新失败）

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas_resume_copilot.py backend/app/routers/resume_copilot.py backend/tests/test_recommendation_rotation.py
git commit -m "feat(reco2): next-batch 端点 + 推荐 item 附显式日期"
```

---

## Phase 3 — 前端

> 前端三套设计系统严格隔离。本期所有新 UI 在 hub/recommend 工作台内，**沿用 `.hf` HiFi 作用域**（terracotta/parchment/Fraunces），class 用现成 `hf-btn`/`hf-pill`/`hf-card`。视觉对照 `docs/superpowers/specs/2026-06-16-my-jobs-mockup.html`。每个前端任务结束都要 `npm run lint`（0 error）+ `npm run build` 通过。

### Task 10: 前端 api + types

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/types.ts`
- Modify: `resume-copilot-web/components/resume-copilot/api.ts`

- [ ] **Step 1: 加类型**

在 `types.ts` 加（与现有 `RecommendItem` 类型同处；字段名对齐后端）：

```typescript
export type JobState = 'seen' | 'saved' | 'applied' | 'dismissed';

export interface MyJobItem {
  job_id: string;
  company: string;
  job_title: string;
  location: string;
  detail_url: string;
  publish_date: string;
  scraped_at: string;
}

export interface MyJobsResult {
  saved: MyJobItem[];
  applied: MyJobItem[];
  dismissed: MyJobItem[];
  counts: { saved: number; applied: number; dismissed: number };
}
```

并在现有推荐 item 接口（`RecommendItem` 或等价，types.ts 里描述 `ResumeRecommendationItem` 的那个）补两字段：

```typescript
  posted_at?: string;
  posted_is_publish?: boolean;
```

- [ ] **Step 2: 加 api 函数**

在 `api.ts`（沿用文件内既有 `request<T>()`/带 `X-Resume-User-Key` 的封装；参照 `scoreResume` 等现有函数的写法）加：

```typescript
export function markJobState(sessionId: number, jobId: string, state: '' | JobState) {
  return request<{ ok: boolean; job_id: string; state: string }>(
    `/sessions/${sessionId}/jobs/${encodeURIComponent(jobId)}/state`,
    { method: 'POST', body: JSON.stringify({ state }) },
  );
}

export function nextRecommendBatch(sessionId: number) {
  return request<ResumeRecommendationResult>(
    `/sessions/${sessionId}/recommendations/next-batch`,
    { method: 'POST' },
  );
}

export function getMyJobs() {
  return request<MyJobsResult>(`/my-jobs`, { method: 'GET' });
}
```

> `request`/`ResumeRecommendationResult` 用 api.ts 内已有的封装名与返回类型名（打开文件确认实际名称，如不是 `request` 而是内部 `apiFetch`/某 helper，则照用）。新类型从 `./types` import。

- [ ] **Step 3: 类型检查**

Run: `cd resume-copilot-web && npx tsc --noEmit 2>&1 | head -20`
Expected: 无与本改动相关的新报错

- [ ] **Step 4: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/types.ts resume-copilot-web/components/resume-copilot/api.ts
git commit -m "feat(reco2-fe): api + types — markJobState/nextRecommendBatch/getMyJobs + 日期字段"
```

---

### Task 11: RecommendCard 三态按钮 + 显式日期

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/workspace/recommend/RecommendCard.tsx`
- Modify: 父组件（`LeftRecommendRail.tsx` 或 `RecommendNarrativeSection.tsx`，传入 `onSetState` + 当前 state）

- [ ] **Step 1: 加日期格式化工具**

在 RecommendCard.tsx 顶部（组件外）加：

```typescript
function formatPosted(postedAt?: string, isPublish?: boolean): string {
  if (!postedAt) return '';
  const d = new Date(postedAt);
  if (Number.isNaN(d.getTime())) return '';
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  const rel = days <= 0 ? '今天' : days === 1 ? '昨天' : `${days} 天前`;
  const md = `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return `${isPublish ? '发布于' : '收录于'} ${md}（${rel}）`;
}
```

- [ ] **Step 2: 在卡片元信息行渲染日期**

在卡片公司/地点那一行（收起态可见处）追加日期 span（沿用现有 `.hf-cap`/`workspace-hifi__rec-card-*` class 风格）：

```tsx
{item.posted_at && (
  <span className="workspace-hifi__rec-card-date">{formatPosted(item.posted_at, item.posted_is_publish)}</span>
)}
```

- [ ] **Step 3: 加三态按钮区**

扩展组件 props（接口加）：

```tsx
  currentState?: JobState;                         // 该岗当前状态
  onSetState?: (state: '' | JobState) => Promise<void>;  // 设置/清除
```

在现有动作区（`!rejectOpen` 分支里、reject 按钮旁）加三个按钮；"不合适"沿用现有 reject 流（点开 `RecommendRejectForm`），新增"收藏想投""已投递"两个直切：

```tsx
<button
  className={`hf-btn sm ${item ? '' : ''} ${(currentState === 'saved') ? 'primary' : 'ghost'}`}
  onClick={() => onSetState?.(currentState === 'saved' ? '' : 'saved')}
>★ {currentState === 'saved' ? '已收藏' : '收藏想投'}</button>
<button
  className={`hf-btn sm ${currentState === 'applied' ? 'primary' : 'sand'}`}
  onClick={() => onSetState?.(currentState === 'applied' ? '' : 'applied')}
>{currentState === 'applied' ? '已投递 ✓' : '标记已投递'}</button>
```

- [ ] **Step 4: 父组件接线**

在父组件（渲染 RecommendCard 的地方）：
- 维护一个 `Record<string, JobState>` 状态映射（首屏可空，乐观更新）；
- 传 `currentState={states[item.job_id]}`；
- 传 `onSetState={async (s) => { await markJobState(sessionId, item.job_id, s); setStates(prev => ({...prev, [item.job_id]: s === '' ? 'seen' : s})); }}`。

- [ ] **Step 5: lint + build**

Run: `cd resume-copilot-web && npm run lint && npm run build 2>&1 | tail -15`
Expected: lint 0 error；build 成功

- [ ] **Step 6: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/recommend/RecommendCard.tsx resume-copilot-web/components/resume-copilot/workspace/LeftRecommendRail.tsx
git commit -m "feat(reco2-fe): 推荐卡三态按钮 + 显式日期"
```

---

### Task 12: feed "换一批" 按钮

**Files:**
- Modify: feed 容器（`LeftRecommendRail.tsx` 或 `RecommendWorkspaceShell.tsx` 右栏 feed 底部）

- [ ] **Step 1: 加换一批按钮 + 处理**

在 feed 列表底部加：

```tsx
<div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, marginTop: 16 }}>
  <button className="hf-btn sand" disabled={loadingBatch} onClick={handleNextBatch}>
    {loadingBatch ? '换一批中…' : recycled ? '重看之前看过的岗位' : '换一批'}
  </button>
  <span className="hf-cap">看过的岗位会自动记下，下次优先给你没看过的</span>
</div>
```

处理函数（组件内）：

```tsx
const [loadingBatch, setLoadingBatch] = useState(false);
const [recycled, setRecycled] = useState(false);
async function handleNextBatch() {
  setLoadingBatch(true);
  try {
    const res = await nextRecommendBatch(sessionId);
    setItems(res.items);                       // 用各 feed 现有的 items setter
    setRecycled(res.fallback_reason === 'recycled');
  } finally {
    setLoadingBatch(false);
  }
}
```

> `setItems` 用该 feed 组件已有的推荐列表状态 setter（打开文件确认实际名）。

- [ ] **Step 2: lint + build**

Run: `cd resume-copilot-web && npm run lint && npm run build 2>&1 | tail -15`
Expected: 0 error + build 成功

- [ ] **Step 3: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/LeftRecommendRail.tsx
git commit -m "feat(reco2-fe): feed 换一批按钮(含池见底回收文案)"
```

---

### Task 13: "我的岗位" tab

**Files:**
- Create: `resume-copilot-web/components/resume-copilot/workspace/MyJobsPanel.tsx`
- Modify: 工作台壳（顶栏加 tab + 路由/视图切换；`HubShell.tsx` 或 `RecommendWorkspaceShell.tsx`）

- [ ] **Step 1: 写 MyJobsPanel 组件**

```tsx
// resume-copilot-web/components/resume-copilot/workspace/MyJobsPanel.tsx
'use client';
import { useEffect, useState } from 'react';
import { getMyJobs, markJobState } from '../api';
import type { MyJobItem, MyJobsResult, JobState } from '../types';

function postedLabel(it: MyJobItem): string {
  const raw = it.publish_date || it.scraped_at;
  if (!raw) return '';
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return '';
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  const rel = days <= 0 ? '今天' : days === 1 ? '昨天' : `${days} 天前`;
  const md = `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return `${it.publish_date ? '发布于' : '收录于'} ${md}（${rel}）`;
}

function logoText(company: string): string {
  return (company || '').slice(0, 2);   // 图标最多取前 2 字
}

type Tab = 'saved' | 'applied' | 'dismissed';

export function MyJobsPanel({ sessionId }: { sessionId: number }) {
  const [data, setData] = useState<MyJobsResult | null>(null);
  const [tab, setTab] = useState<Tab>('saved');

  async function reload() { setData(await getMyJobs()); }
  useEffect(() => { reload(); }, []);

  async function setState(jobId: string, s: '' | JobState) {
    await markJobState(sessionId, jobId, s);
    await reload();
  }

  if (!data) return <div className="hf-cap" style={{ padding: 24 }}>加载中…</div>;
  const list = data[tab];

  return (
    <div className="hf" style={{ maxWidth: 980, margin: '0 auto', padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 6 }}>
        <h1 className="hf-serif" style={{ fontSize: 30 }}>我的岗位</h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <span className="hf-pill terra">想投 {data.counts.saved}</span>
          <span className="hf-pill emerald">已投递 {data.counts.applied}</span>
          <span className="hf-pill">已屏蔽 {data.counts.dismissed}</span>
        </div>
      </div>
      <p className="hf-body-sm" style={{ marginBottom: 18 }}>把感兴趣的岗位收起来、记下投递进度。这里只做记录，不会改变给你的推荐。</p>

      <div style={{ display: 'inline-flex', gap: 4, background: 'var(--library-rail)', padding: 3, borderRadius: 999, marginBottom: 18 }}>
        {(['saved', 'applied', 'dismissed'] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className="hf-btn sm" style={{ borderRadius: 999, background: tab === t ? 'var(--ivory)' : 'transparent', boxShadow: tab === t ? 'var(--sh-ring)' : 'none' }}>
            {t === 'saved' ? `收藏·想投 (${data.counts.saved})` : t === 'applied' ? `已投递 (${data.counts.applied})` : `已屏蔽 (${data.counts.dismissed})`}
          </button>
        ))}
      </div>

      <div className="hf-card lift">
        {list.length === 0 && <div className="hf-cap" style={{ padding: 24 }}>这一组还没有岗位。</div>}
        {list.map((it) => (
          <div key={it.job_id} style={{ display: 'flex', gap: 14, padding: '16px 18px', borderBottom: '1px solid var(--border-cream)' }}>
            <div style={{ width: 40, height: 40, borderRadius: 10, background: 'var(--terracotta)', color: 'var(--ivory)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--font-serif)', fontWeight: 600, flexShrink: 0 }}>{logoText(it.company)}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="hf-serif" style={{ fontSize: 16 }}>{it.job_title}</div>
              <div className="hf-cap" style={{ marginTop: 2 }}>{it.company} · {it.location} · {postedLabel(it)}</div>
              <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                {tab === 'saved' && <button className="hf-btn primary sm" onClick={() => setState(it.job_id, 'applied')}>标记已投递</button>}
                {tab !== 'dismissed' && <button className="hf-btn ghost sm" onClick={() => setState(it.job_id, '')}>移除</button>}
                {tab === 'dismissed' && <button className="hf-btn ghost sm" onClick={() => setState(it.job_id, '')}>撤回屏蔽</button>}
                {it.detail_url && <a className="hf-btn link sm" href={it.detail_url} target="_blank" rel="noreferrer" style={{ marginLeft: 'auto' }}>去投递 ↗</a>}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 工作台壳加 tab**

在工作台顶栏（现有 tab 组，HubShell/RecommendWorkspaceShell 内）加一个"我的岗位"tab；选中时渲染 `<MyJobsPanel sessionId={sessionId} />` 替代主内容区。沿用壳里已有的 tab 状态机（仿现有 tab 项写法，不新建路由）。

- [ ] **Step 3: lint + build**

Run: `cd resume-copilot-web && npm run lint && npm run build 2>&1 | tail -15`
Expected: 0 error + build 成功

- [ ] **Step 4: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/MyJobsPanel.tsx resume-copilot-web/components/resume-copilot/workspace/hub/HubShell.tsx
git commit -m "feat(reco2-fe): 我的岗位 tab(MyJobsPanel,按 HiFi 视觉稿)"
```

---

## Phase 4 — 验收

### Task 14: 端到端验收 + flag-off 回归 + ACTIVITY

**Files:**
- Modify: `ACTIVITY.md`

- [ ] **Step 1: 后端全绿**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/ -q`
Expected: 全绿

- [ ] **Step 2: flag-off 字节级不变核验**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_resume_recommendation_service.py tests/test_recommend_progress.py tests/test_recommend_reject.py -x`
Expected: PASS（默认 flag off，推荐与拒绝行为不变；reject 新断言因双写而过）

- [ ] **Step 3: 前端 lint + build**

Run: `cd resume-copilot-web && npm run lint && npm run build 2>&1 | tail -15`
Expected: 0 error + build 成功

- [ ] **Step 4: dev 端到端冒烟（flag 开）**

在 dev `backend/.env.local` 临时设 `RECOMMENDATION_ROTATION_ENABLED=1`，重启 :8000，对一个非 demo 会话：
- `POST /generate` → 轮询 `/recommendations` 到 done，确认 items 带 `posted_at`；
- `POST /recommendations/next-batch` → 返回与首页不重叠的下一批；
- `POST /jobs/{id}/state {"state":"saved"}` → `GET /my-jobs` 看到该岗在 saved 组；
- demo 会话对 state/next-batch 返回 403。

Run（示例）：
```bash
cd backend && curl -s -X POST localhost:8000/api/resume-copilot/sessions/<SID>/recommendations/next-batch -H "X-Resume-User-Key: u_<N>" | python -c "import sys,json;d=json.load(sys.stdin);print([i['job_id'] for i in d['items']])"
```
Expected: 打印一页 job_id；二次调用推进。

- [ ] **Step 5: 追加 ACTIVITY.md**

在 `ACTIVITY.md` 顶部加一条（5 行内，产品语言）：岗位推荐 2.0 上线骨架——学生现在能收藏/标记已投/屏蔽岗位、在"我的岗位"看投递进度、"换一批"持续看到没看过的新岗、卡上显式岗位日期；MVP 纯追踪不学习；行为挂 flag 默认关，灰度可开。测试：后端全绿 + 前端 lint/build 过 + dev 冒烟过。下一步：prod 灰度开 flag + 观察。

- [ ] **Step 6: Commit**

```bash
git add ACTIVITY.md
git commit -m "docs(activity): 岗位推荐 2.0 骨架交付(三态/我的岗位/换一批/日期)"
```

---

## Self-Review（计划 vs 设计稿）

**Spec 覆盖核对：**
- §3.1 状态层(表/互斥/dismissed 收编/唯一约束) → Task 1,2,3,5 ✅
- §3.2 轮换(深池持久化/排除已看过/换一批/回收兜底) → Task 7,8,9 ✅
- §3.3① 三态标记 + 显式日期 → Task 4,9,11 ✅
- §3.3② 换一批 → Task 12 ✅
- §3.3③ 我的岗位 tab + 图标≤2 字 → Task 6,13 ✅
- §四 API(state/next-batch/my-jobs/reject 保留双写) → Task 4,5,6,9 ✅
- §五 兼容(demo 403 / 存量回填 / flag 默认关) → Task 4,5,8,14 ✅
- §六 测试要点(互斥/唯一/分页/回收/双写/flag-off 回归) → Task 3,7,9,14 ✅
- §七.4 纯追踪不回流 → 本计划无任何"用状态改排序"的任务 ✅

**占位符扫描：** 无 TBD/TODO；`<PASTE_CURRENT_HEAD>` 是 Task 2 必须由实施者用 `alembic heads` 实际填的真实值，已在步骤里说明取法（非占位偷懒）。

**类型/命名一致性：** `JobUserState` / `resume_job_user_state` / state 常量 / `mark_seen` / `set_explicit_state` / `seen_or_dismissed_ids` / `my_jobs_grouped` / `next_page` / `pool_json` / `posted_at` / `markJobState` / `nextRecommendBatch` / `getMyJobs` 跨任务一致。

**已知务实取舍（实现时留意）：** Task 8 的"深池"MVP 先用 dispatcher 最终 items 作池（可能仍 ~20）；要真正用满 ~100 需后续让 dispatcher 暴露更长有序候选——已在设计稿 §八与本节标注，不阻塞骨架上线。
