# 自然语言推荐 agent（子项①）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让学生在工作台用自然语言指令实时从岗位库召回/重排岗位（流动 feed），改的是会话级「工作查询」而非确认赛道，平时偏好沉淀进统一记忆，深度精排按需才跑。

**Architecture:** 每轮对话 = 1 次 flash LLM 出结构化 JSON（intent + query_delta + remember + reply）→ 纯函数 `apply_delta` 并进 WorkingQuery → `search_candidates`（复用 `recall_candidates`+`rank_jobs`+`_v2_items_from_ranked`，纯规则、秒级）出 feed。三层偏好：L1 工作查询（`working_query_json` 列）/ L2 锁定→confirmed preferences / L3 平时偏好→`account_memory` `preference` 行（经 `dispatcher.write_memory`）。深挖才跑 Pro 精排。前端 = 独立三栏「推荐工作台」（会话侧栏 / NL 对话栏 / 流动 feed 栏）。

**Tech Stack:** FastAPI + Pydantic v2 + SQLAlchemy(SQLite, Alembic) + pytest；DeepSeek flash（意图解析）；Next.js 16 + React 19。

**设计来源:**
- spec: `docs/superpowers/specs/2026-06-03-nl-recommendation-agent-design.md`
- **hi-fi 设计稿（已定，前端按它像素级还原）**: `resume-copilot-web/.design-ref/nl-recommendation/`
  - `NL-recommendation-workspace.html`（入口）→ `nlrec-app.jsx`（壳+侧栏+顶栏+锁定弹层+状态机）/ `nlrec-chat.jsx`（对话栏：Turn / border-beam ThinkingCard / 可展开 TraceCard / MemoryToast / IntelCard / Composer）/ `nlrec-feed.jsx`（feed 栏：工作查询 chip readout + JobCard Base/Enhanced 分 + 4-anchor 深挖 + 空态）/ `nlrec-data.jsx`（脚本化交互参考，仅看契约不照搬）
  - `design-chat-transcript.md` — 设计意图原文
  - 设计稿用 `.hf-*` 类 + `hifi-tokens.css`/`colors_and_type.css` 变量 + `.ds-border-beam`；与 repo 现有 `.hf` 体系（`resume-copilot-web/components/hifi/hifi-tokens.css`、`app/globals.css` 的 border-beam）同源，**移植时复用 repo 的，缺的 token/class 才补**。

**设计稿带来的契约增量（已并入下面任务）:**
- WorkingQuery 区分 **seed_sub_cats**（confirmed 派生、深色不可删）与 **sub_cats**（NL 加的、陶土色可删 ×）→ Task 1/3/4。
- 一轮响应除 `feed/working_query/reply` 外，回 **trace**（`intent`+`query_delta` 回显+remember 备注，给可展开 TraceCard）与 **remembered**（写了哪条 L3，给 MemoryToast）→ Task 6。
- feed item 每条带规则 **base_score** + `used_ai=false`；深挖回 **enhanced_score** + **anchors**（4 段 `[label, text]`）→ Task 4/7。
- 工作查询的「删 add chip / 清 only / 改 sort」是显式交互 → Task 7 加 `POST working-query/update`（结构化操作 + 重排，仍走快路）。

**铁律（贯穿全程）:**
- 平时对话**绝不写 confirmed preferences**（L2）；只有显式「锁定」才写。
- L3 偏好**绝不直插 `account_memory`**；只经 `dispatcher.write_memory`。
- `search_candidates` **不藏岗**：exclude 仅学生显式要求才排；companies 偏好是置顶非过滤（除非 `only=true`）。
- 对话每轮**只走规则快路，绝不跑 Pro 精排**；Pro 只在 `/recommend-deepen`。
- `working_query_json` 缺失 = 退回按 confirmed 赛道，行为同现状（向后兼容）。
- 后端 `PYTHONPATH=. .venv/bin/pytest tests/` 保持绿；前端 `npm run lint` 0 error + `npm run build` 过。
- 工作树有别的会话 WIP，**绝不 `git add -A`**，只 add 任务列明文件；commit 末尾加 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。

---

## File Structure

**后端（新建）:**
- `backend/app/services/resume_copilot/working_query.py` — `WorkingQuery` 模型 + `apply_delta` 纯函数 + `seed_working_query`（从 confirmed + L3 记忆灌初值）。
- `backend/app/services/resume_copilot/recommend_intent.py` — flash 意图解析（输出 JSON 契约，可注入 client）。
- `backend/app/services/resume_copilot/recommend_chat.py` — Unit C orchestrator（parse → apply_delta → search_candidates → 持久化 → L3 写入）。
- `backend/app/services/resume_copilot/recommend_search.py` — `search_candidates(db, query, ...)`（复用 recall/rank/item）。
- `backend/alembic/versions/<rev>_working_query_json.py` — 加 `working_query_json` 列。

**后端（改）:**
- `backend/app/routers/resume_copilot.py` — 新增 3 路由（只加）。
- `backend/app/models.py`（或 models 包）— `ResumeCopilotSession` 加 `working_query_json` 列声明。

**前端（改）:**
- `resume-copilot-web/components/resume-copilot/types.ts` + `api.ts` — 类型 + 4 个调用（chat / working-query / working-query-update / deepen）。

**前端（新建 — 按 hi-fi 设计稿像素级还原独立三栏「推荐工作台」）:**
- `resume-copilot-web/app/recommend/page.tsx` — 新路由（独立全屏页）。
- `.../workspace/recommend-agent/` 新组件目录：
  - `RecommendWorkspaceShell.tsx`（三栏 grid + 顶层状态机）/ `RecommendTopBar.tsx` / `RecommendSidebar.tsx`（会话列表 + 隐藏改写卡）
  - `RecommendChatPane.tsx` + `chat/{Turn,ThinkingCard,TraceCard,MemoryToast,Composer}.tsx`
  - `RecommendFeedPane.tsx` + `feed/{WorkingQueryReadout,JobCard,ScorePill,QueryChip}.tsx`
  - `LockModal.tsx` / `recommend-agent.css`（仅补 repo 缺的 token/class，scope 隔离）
- 设计源：`.design-ref/nl-recommendation/{nlrec-app,nlrec-chat,nlrec-feed,nlrec-data}.jsx`。company-intel 卡复用既有 `workspace/intel/`。

**测试（新建）:**
- `backend/tests/resume_copilot/test_working_query.py`
- `backend/tests/resume_copilot/test_recommend_search.py`
- `backend/tests/resume_copilot/test_recommend_intent.py`
- `backend/tests/resume_copilot/test_recommend_chat.py`

---

## Unit 1 — 后端核心（WorkingQuery + 召回 + agent）

### Task 1: WorkingQuery 模型 + `apply_delta` 纯函数

**Files:**
- Create: `backend/app/services/resume_copilot/working_query.py`
- Test: `backend/tests/resume_copilot/test_working_query.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/resume_copilot/test_working_query.py
from app.services.resume_copilot.working_query import WorkingQuery, apply_delta


def test_default_query_empty():
    q = WorkingQuery()
    assert q.sub_cats == [] and q.seed_sub_cats == [] and q.companies == [] and q.exclude == []
    assert q.sort == "match" and q.only is False


def test_apply_delta_adds_dedup():
    q = WorkingQuery(sub_cats=["公募权益研究员"])
    out = apply_delta(q, {"add_sub_cats": ["固收+多资产", "公募权益研究员"]})
    assert out.sub_cats == ["公募权益研究员", "固收+多资产"]  # 去重, 保序


def test_apply_delta_does_not_touch_seed():
    # seed_sub_cats = confirmed 派生, NL add 只进 sub_cats, 不污染 seed
    q = WorkingQuery(seed_sub_cats=["公募权益研究员"])
    out = apply_delta(q, {"add_sub_cats": ["固收+多资产"]})
    assert out.seed_sub_cats == ["公募权益研究员"]
    assert out.sub_cats == ["固收+多资产"]


def test_effective_sub_cats_merges_seed_and_add_dedup():
    q = WorkingQuery(seed_sub_cats=["公募权益研究员", "固收+多资产"], sub_cats=["固收+多资产", "FOF配置"])
    assert q.effective_sub_cats() == ["公募权益研究员", "固收+多资产", "FOF配置"]  # seed 在前, 去重


def test_apply_delta_companies_and_exclude():
    out = apply_delta(WorkingQuery(), {"add_companies": ["字节"], "exclude": ["国企A"]})
    assert out.companies == ["字节"] and out.exclude == ["国企A"]


def test_apply_delta_sort_and_only():
    out = apply_delta(WorkingQuery(), {"sort": "fresh", "only": True})
    assert out.sort == "fresh" and out.only is True


def test_apply_delta_ignores_unknown_and_none():
    q = WorkingQuery(sub_cats=["x"])
    out = apply_delta(q, {"add_sub_cats": None, "garbage": 1, "sort": "bogus"})
    assert out.sub_cats == ["x"] and out.sort == "match"  # bogus sort 被忽略


def test_apply_delta_is_pure_does_not_mutate_input():
    q = WorkingQuery(sub_cats=["x"])
    apply_delta(q, {"add_sub_cats": ["y"]})
    assert q.sub_cats == ["x"]  # 原对象不变
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/test_working_query.py -v`
Expected: FAIL（模块不存在 / ImportError）。

- [ ] **Step 3: 实现**

```python
# backend/app/services/resume_copilot/working_query.py
"""会话级「工作查询」(L1) — NL 推荐 agent 的临时探索状态。

apply_delta 是纯函数: 把 agent 吐的 query_delta 并进当前 query, 返回新对象 (不改入参)。
绝不动 confirmed preferences。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

_VALID_SORT = {"match", "fresh", "pay"}


class WorkingQuery(BaseModel):
    seed_sub_cats: list[str] = Field(default_factory=list)  # confirmed 派生, 不可删 (深色 chip)
    sub_cats: list[str] = Field(default_factory=list)       # NL 加的, 可删 (陶土色 chip)
    companies: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    sort: str = "match"
    only: bool = False
    note: str = ""

    def effective_sub_cats(self) -> list[str]:
        """召回/打分用的合并 sub_cat 集 = seed + add, seed 在前, 去重保序。"""
        return _merge_unique(list(self.seed_sub_cats), self.sub_cats)


def _merge_unique(base: list[str], add) -> list[str]:
    out = list(base)
    for x in (add or []):
        if isinstance(x, str) and x and x not in out:
            out.append(x)
    return out


def apply_delta(query: WorkingQuery, delta: dict) -> WorkingQuery:
    """纯函数: 返回并入 delta 后的新 WorkingQuery, 不改入参。脏字段忽略不崩。

    add_sub_cats 只进 sub_cats(add 集); seed_sub_cats 不被对话改动(只 seed_working_query 设)。
    """
    delta = delta or {}
    sort = delta.get("sort")
    new_sort = sort if isinstance(sort, str) and sort in _VALID_SORT else query.sort
    only = delta.get("only")
    new_only = bool(only) if isinstance(only, bool) else query.only
    return WorkingQuery(
        seed_sub_cats=list(query.seed_sub_cats),
        sub_cats=_merge_unique(query.sub_cats, delta.get("add_sub_cats")),
        companies=_merge_unique(query.companies, delta.get("add_companies")),
        locations=_merge_unique(query.locations, delta.get("add_locations")),
        exclude=_merge_unique(query.exclude, delta.get("exclude")),
        sort=new_sort,
        only=new_only,
        note=query.note,
    )
```

- [ ] **Step 4: 跑测试确认 PASS**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/test_working_query.py -v`
Expected: 8 passed。

- [ ] **Step 5: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/resume_copilot/working_query.py backend/tests/resume_copilot/test_working_query.py
git commit -m "$(cat <<'EOF'
feat(reco): WorkingQuery 模型 + apply_delta 纯函数(L1 临时工作查询)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `working_query_json` 列（Alembic 迁移 + 模型声明）

**Files:**
- Modify: `backend/app/models.py`（或 models 包里 `ResumeCopilotSession` 所在文件 — 先 grep 确认）
- Create: `backend/alembic/versions/<rev>_working_query_json.py`

`working_query_json` 存会话级 L1 工作查询 JSON，缺失=退回 confirmed（向后兼容）。

- [ ] **Step 1: 定位 session 模型**

Run: `cd backend && grep -rn "class ResumeCopilotSession" app/models*.py app/models/ 2>/dev/null`
读出表名（`__tablename__`，应是 `resume_copilot_sessions`）和现有列风格（其它 `*_json` 列如何声明）。

- [ ] **Step 2: 加列声明（模型）**

在 `ResumeCopilotSession` 加（匹配现有 `Column(Text, ...)` 风格）:

```python
    working_query_json = Column(Text, nullable=True)  # L1 NL 推荐工作查询(JSON), 空=按 confirmed
```

- [ ] **Step 3: 生成迁移并改成 idempotent**

Run: `cd backend && PYTHONPATH=. .venv/bin/alembic revision -m "working_query_json on resume_copilot_sessions"`
打开新生成的 `backend/alembic/versions/<rev>_*.py`，把 upgrade 改成带 inspector 幂等检查（照 CLAUDE.md 约定）:

```python
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


def upgrade():
    conn = op.get_bind()
    insp = inspect(conn)
    cols = [c["name"] for c in insp.get_columns("resume_copilot_sessions")]
    if "working_query_json" not in cols:
        op.add_column("resume_copilot_sessions", sa.Column("working_query_json", sa.Text(), nullable=True))


def downgrade():
    pass
```
（`down_revision` 保留 alembic 自动填的值，不要改。）

- [ ] **Step 4: 跑迁移 + 冒烟**

Run: `cd backend && PYTHONPATH=. .venv/bin/alembic upgrade head && PYTHONPATH=. .venv/bin/python -c "import sqlite3;print('working_query_json' in [c[1] for c in sqlite3.connect('data/jobradar.db').cursor().execute('PRAGMA table_info(resume_copilot_sessions)').fetchall()])"`
Expected: 末行 `True`。

- [ ] **Step 5: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/models.py backend/alembic/versions/
git commit -m "$(cat <<'EOF'
feat(reco): resume_copilot_sessions 加 working_query_json 列(L1 持久, 幂等迁移)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```
> 若模型不在 `app/models.py` 而在 models 包,`git add` 换成实际文件路径。

---

### Task 3: `seed_working_query` — 从 confirmed + L3 记忆灌初值

**Files:**
- Modify: `backend/app/services/resume_copilot/working_query.py`
- Test: `backend/tests/resume_copilot/test_working_query.py`（追加）

初始化工作查询 = confirmed 赛道展开的 sub_cats + 活跃 `preference` 记忆的种子（公司/地点/排除）。

- [ ] **Step 1: 追加失败测试**

```python
# 追加到 backend/tests/resume_copilot/test_working_query.py
from app.services.resume_copilot.working_query import seed_working_query


def test_seed_from_confirmed_only():
    q = seed_working_query(confirmed_sub_cats=["公募权益研究员"], preference_rows=[])
    assert q.seed_sub_cats == ["公募权益研究员"]   # confirmed → seed (不可删 chip)
    assert q.sub_cats == []                        # add 集初始为空
    assert q.companies == [] and q.locations == [] and q.exclude == []


def test_seed_merges_preference_memory():
    # preference_rows: 形如 {"dimension": "...", "value": "..."}
    rows = [
        {"dimension": "company_type", "value": "外资行"},
        {"dimension": "city", "value": "上海"},
        {"dimension": "company_type", "value": "非国企"},   # 含「非/不」→ 排除
    ]
    q = seed_working_query(confirmed_sub_cats=["固收+多资产"], preference_rows=rows)
    assert q.seed_sub_cats == ["固收+多资产"]
    assert "外资行" in q.companies
    assert "上海" in q.locations
    assert any("国企" in e for e in q.exclude)  # 否定偏好 → exclude
```

- [ ] **Step 2: 跑确认 FAIL**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/test_working_query.py::test_seed_from_confirmed_only -v`
Expected: FAIL（`seed_working_query` 不存在）。

- [ ] **Step 3: 实现（追加到 working_query.py）**

```python
_NEG_TOKENS = ("不", "非", "排除", "no ", "not ")


def seed_working_query(*, confirmed_sub_cats: list[str], preference_rows: list[dict]) -> WorkingQuery:
    """L3→L1: 工作查询初值 = confirmed 赛道 + 活跃 preference 记忆种子。

    preference_rows: [{"dimension": city|industry|role|comp|company_type|stage, "value": str}, ...]
    维度映射: city→locations; company_type/industry/comp→companies(或 exclude, 若 value 含否定词)。
    """
    companies: list[str] = []
    locations: list[str] = []
    exclude: list[str] = []
    for row in (preference_rows or []):
        dim = str(row.get("dimension") or "")
        val = str(row.get("value") or "").strip()
        if not val:
            continue
        is_neg = any(t in val for t in _NEG_TOKENS)
        target = exclude if is_neg else (
            locations if dim == "city" else companies
        )
        # 排除时去掉否定词留主体, 方便后续子串匹配公司/类型
        cleaned = val
        for t in _NEG_TOKENS:
            cleaned = cleaned.replace(t, "")
        cleaned = cleaned.strip()
        if cleaned and cleaned not in target:
            target.append(cleaned)
    return WorkingQuery(
        seed_sub_cats=list(confirmed_sub_cats or []),  # confirmed → 不可删 seed chip
        sub_cats=[],                                    # NL add 集, 对话中再长
        companies=companies,
        locations=locations,
        exclude=exclude,
    )
```

- [ ] **Step 4: 跑确认 PASS**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/test_working_query.py -v`
Expected: 全 passed（含 Task 1 的 6 个 + 新 2 个）。

- [ ] **Step 5: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/resume_copilot/working_query.py backend/tests/resume_copilot/test_working_query.py
git commit -m "$(cat <<'EOF'
feat(reco): seed_working_query 从 confirmed + L3 preference 记忆灌初值

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `search_candidates` tool — WorkingQuery → feed

**Files:**
- Create: `backend/app/services/resume_copilot/recommend_search.py`
- Test: `backend/tests/resume_copilot/test_recommend_search.py`

复用 `recall_candidates`（DB 召回）+ `rank_jobs`（规则三维排）+ `_v2_items_from_ranked`（item 构造，已带 in_skeleton）。companies 置顶、exclude 过滤、only 收窄、locations 过滤、sort。**纯规则、不调 LLM。**

- [ ] **Step 1: 先核对复用点的真实签名**

Run: `cd backend && grep -n "def recall_candidates" app/services/phase_g/recommendation_v2/recall.py && grep -n "def rank_jobs\|def _v2_items_from_ranked\|class StudentProfile" app/services/phase_g/recommendation_v2/scoring.py app/services/resume_copilot/recommendation.py`
确认：`recall_candidates(db, preferred_sub_cats=(), *, limit, quality_labels, freshness_days, preferred_locations)`；`rank_jobs(profile, jobs)->list[(job,score)]`；`_v2_items_from_ranked(...)` 的入参（profile/preferences 等）。按实际签名微调下面实现。

- [ ] **Step 2: 写失败测试**

```python
# backend/tests/resume_copilot/test_recommend_search.py
from types import SimpleNamespace
from app.services.resume_copilot.recommend_search import _apply_company_pref, _apply_exclude


def _it(company, title="x"):
    return {"company": company, "job_title": title}


def test_pin_preferred_companies_to_front_keeps_others():
    feed = [_it("A"), _it("B"), _it("字节"), _it("C")]
    out = _apply_company_pref(feed, companies=["字节"], only=False)
    assert [x["company"] for x in out] == ["字节", "A", "B", "C"]  # 置顶, 不删其余


def test_only_restricts_to_preferred_companies():
    feed = [_it("A"), _it("字节"), _it("B")]
    out = _apply_company_pref(feed, companies=["字节"], only=True)
    assert [x["company"] for x in out] == ["字节"]  # only → 收窄


def test_exclude_filters_out():
    feed = [_it("国企A"), _it("字节")]
    out = _apply_exclude(feed, exclude=["国企"])
    assert [x["company"] for x in out] == ["字节"]


def test_empty_company_pref_is_noop():
    feed = [_it("A"), _it("B")]
    assert _apply_company_pref(feed, companies=[], only=False) == feed
```

- [ ] **Step 3: 跑确认 FAIL**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/test_recommend_search.py -v`
Expected: FAIL（模块不存在）。

- [ ] **Step 4: 实现**

```python
# backend/app/services/resume_copilot/recommend_search.py
"""search_candidates tool — 按 WorkingQuery 从库召回 + 规则排 + 后处理(置顶/过滤)。

纯规则、秒级、不调 LLM。feed item 形状沿用 recommendation_v2 的 item 构造。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.resume_copilot.working_query import WorkingQuery


def _apply_exclude(feed: list[dict], exclude: list[str]) -> list[dict]:
    if not exclude:
        return feed
    def hit(it):
        text = f"{it.get('company','')} {it.get('sub_category','')}"
        return any(x and x in text for x in exclude)
    return [it for it in feed if not hit(it)]


def _apply_company_pref(feed: list[dict], companies: list[str], only: bool) -> list[dict]:
    if not companies:
        return feed
    def hit(it):
        return any(c and c in (it.get("company", "") or "") for c in companies)
    preferred = [it for it in feed if hit(it)]
    if only:
        return preferred
    rest = [it for it in feed if not hit(it)]
    return preferred + rest  # 置顶, 保留其余(不藏岗)


def _tag_rule_item(it: dict) -> dict:
    """给规则 feed item 补设计稿要的字段: base_score(规则分) + used_ai=False。

    item 已带某个规则分字段(score/rule_score/match_score, 以 grep 为准)。统一暴露成 base_score,
    前端 JobCard 的 Base 分 pill 用它; Enhanced 分留空(深挖才补)。"""
    base = it.get("base_score")
    if base is None:
        base = it.get("score") or it.get("rule_score") or it.get("match_score") or 0
    it["base_score"] = round(float(base)) if isinstance(base, (int, float)) else base
    it.setdefault("used_ai", False)
    it.setdefault("enhanced_score", None)  # 深挖前为空 → 前端显 dashed pending pill
    return it


def search_candidates(db: Session, query: WorkingQuery, *, limit: int = 40) -> list[dict]:
    """WorkingQuery → ranked feed(item dict list)。纯规则、秒级、不调 LLM。"""
    from app.services.phase_g.recommendation_v2 import recall as _recall, scoring as _scoring
    from app.services.resume_copilot.recommendation import _v2_items_from_ranked  # 复用 item 构造

    eff = query.effective_sub_cats()  # seed + add 合并集
    jobs = _recall.recall_candidates(
        db, eff, limit=max(limit * 4, 80),
        preferred_locations=query.locations,
    )
    profile = _scoring.StudentProfile(
        preferred_sub_cats=eff, confirmed_sub_cats=query.seed_sub_cats,
    )
    ranked = _scoring.rank_jobs(profile, jobs)
    if query.sort == "fresh":
        ranked = sorted(ranked, key=lambda t: getattr(t[0], "scraped_at", None) or 0, reverse=True)
    # sort=='pay' 暂无可靠薪资字段 → 退回 match 序(best-effort, 见 spec YAGNI)
    items = _v2_items_from_ranked(ranked[:limit * 2], profile, None)  # 按真实签名调参
    items = [_tag_rule_item(it) for it in items]
    items = _apply_exclude(items, query.exclude)
    items = _apply_company_pref(items, query.companies, query.only)
    return items[:limit]
```
> `_v2_items_from_ranked` 的真实入参以 Step 1 grep 为准（可能是 `(ranked, profile, preferences)` 或带 db）。若它返回 Pydantic 对象而非 dict，把 `_apply_*` / `_tag_rule_item` 的 `it.get(...)` 改成 `getattr(...)/setattr(...)`，并把测试的 `_it` 改成 `SimpleNamespace`。保持 `_apply_company_pref`/`_apply_exclude` 的纯函数语义与测试不变。`profile` 的 `preferred_sub_cats` 用合并集 `eff`、`confirmed_sub_cats` 用 `seed_sub_cats`（软信号只把 confirmed 派生的 seed 当「确认」，NL 临时加的 add 不算确认 — 与「对话不动 confirmed」铁律一致）。

- [ ] **Step 5: 跑确认 PASS + 真库冒烟**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/test_recommend_search.py -v`
Expected: 4 passed。
Run 冒烟: `cd backend && PYTHONPATH=. .venv/bin/python -c "
from app.database import SessionLocal
from app.services.resume_copilot.working_query import WorkingQuery
from app.services.resume_copilot.recommend_search import search_candidates
db=SessionLocal()
feed=search_candidates(db, WorkingQuery(sub_cats=['公募权益研究员'], companies=['中欧基金']))
print('feed n=', len(feed), '| 首条:', feed[0].get('company') if feed and isinstance(feed[0],dict) else (getattr(feed[0],'company',None) if feed else None))
"`
Expected: feed n>0，首条公司应是中欧基金（置顶生效）。

- [ ] **Step 6: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/resume_copilot/recommend_search.py backend/tests/resume_copilot/test_recommend_search.py
git commit -m "$(cat <<'EOF'
feat(reco): search_candidates tool — WorkingQuery→规则召回排+置顶/过滤(不调 LLM)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: 意图解析（flash → JSON 契约）

**Files:**
- Create: `backend/app/services/resume_copilot/recommend_intent.py`
- Test: `backend/tests/resume_copilot/test_recommend_intent.py`

flash 一次调用，输出 `{intent, query_delta, remember, reply}`。可注入 client（测试用 fake）。失败兜底：`{intent:"chitchat", query_delta:{}, remember:null, reply:"没太听懂,换个说法?"}`（不改 query、不崩）。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/resume_copilot/test_recommend_intent.py
from app.services.resume_copilot.recommend_intent import parse_intent


class _FakeClient:
    def __init__(self, content): self._c = content; self.chat = self; self.completions = self
    def create(self, **k):
        m = type("m", (), {"content": self._c})(); ch = type("c", (), {"message": m})()
        return type("r", (), {"choices": [ch]})()


def test_parses_refine_delta():
    cli = _FakeClient('{"intent":"refine","query_delta":{"add_sub_cats":["固收+多资产"]},"remember":null,"reply":"已加固收"}')
    out = parse_intent("多来点固收", current_query={"sub_cats": []}, client=cli)
    assert out["intent"] == "refine"
    assert out["query_delta"]["add_sub_cats"] == ["固收+多资产"]
    assert out["remember"] is None


def test_parses_remember_stable_pref():
    cli = _FakeClient('{"intent":"refine","query_delta":{"exclude":["国企"]},"remember":{"dimension":"company_type","value":"非国企"},"reply":"已排除国企"}')
    out = parse_intent("我一直不考虑国企", current_query={}, client=cli)
    assert out["remember"]["dimension"] == "company_type"


def test_remember_with_invalid_dimension_dropped():
    cli = _FakeClient('{"intent":"refine","query_delta":{},"remember":{"dimension":"BOGUS","value":"x"},"reply":"ok"}')
    out = parse_intent("x", current_query={}, client=cli)
    assert out["remember"] is None  # 维度非法 → 丢


def test_fallback_on_bad_json():
    cli = _FakeClient("not json at all")
    out = parse_intent("???", current_query={}, client=cli)
    assert out["intent"] == "chitchat" and out["query_delta"] == {} and out["remember"] is None


def test_fallback_on_client_error():
    class _Boom:
        chat = property(lambda s: s); completions = property(lambda s: s)
        def create(self, **k): raise RuntimeError("down")
    out = parse_intent("x", current_query={}, client=_Boom())
    assert out["intent"] == "chitchat"
```

- [ ] **Step 2: 跑确认 FAIL**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/test_recommend_intent.py -v`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现**

```python
# backend/app/services/resume_copilot/recommend_intent.py
"""NL → 推荐 agent 意图解析(1 次 flash, 结构化 JSON)。失败兜底 chitchat 不崩。"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

_VALID_INTENT = {"refine", "company_focus", "intel", "lock", "chitchat"}
_VALID_DIM = {"city", "industry", "role", "comp", "company_type", "stage"}

_PROMPT = """你是金融求职推荐助手的意图解析器。学生在用自然语言调整他的岗位推荐。
当前工作查询: {query}
学生说: {msg}

输出 JSON(只输出 JSON):
{{
  "intent": "refine|company_focus|intel|lock|chitchat",
  "query_delta": {{"add_sub_cats":[],"add_companies":[],"add_locations":[],"exclude":[],"sort":"match|fresh|pay 或省略","only":false}},
  "remember": {{"dimension":"city|industry|role|comp|company_type|stage","value":"..."}} 或 null,
  "reply": "一句话说明这轮做了什么"
}}
规则:
- 只有学生表达**稳定/泛化**偏好(如"我一直/从不/必须…")才填 remember; 一次性"今天看看X"不填。
- intent=lock 仅当学生明确要"锁定/就按这个/设为主方向"。
- 不确定就 intent=chitchat, query_delta 留空。"""

_FALLBACK = {"intent": "chitchat", "query_delta": {}, "remember": None, "reply": "没太听懂,换个说法?"}


def _build_client():
    from app.services.crawler_llm import build_flash_client
    return build_flash_client()


def _model_name() -> str:
    from app.services.crawler_llm import flash_model_name
    return flash_model_name()


def parse_intent(message: str, *, current_query: dict, client=None) -> dict:
    cli = client if client is not None else _build_client()
    try:
        resp = cli.chat.completions.create(
            model=_model_name(),
            messages=[{"role": "user", "content": _PROMPT.format(
                query=json.dumps(current_query, ensure_ascii=False), msg=(message or "")[:500])}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
    except Exception:
        logger.warning("parse_intent failed, fallback chitchat", exc_info=True)
        return dict(_FALLBACK)
    intent = data.get("intent") if data.get("intent") in _VALID_INTENT else "chitchat"
    delta = data.get("query_delta") if isinstance(data.get("query_delta"), dict) else {}
    remember = data.get("remember")
    if not (isinstance(remember, dict) and remember.get("dimension") in _VALID_DIM and str(remember.get("value") or "").strip()):
        remember = None
    return {"intent": intent, "query_delta": delta, "remember": remember,
            "reply": str(data.get("reply") or "")}
```

- [ ] **Step 4: 跑确认 PASS**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/test_recommend_intent.py -v`
Expected: 5 passed。

- [ ] **Step 5: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/resume_copilot/recommend_intent.py backend/tests/resume_copilot/test_recommend_intent.py
git commit -m "$(cat <<'EOF'
feat(reco): 意图解析 parse_intent(flash→JSON 契约, 失败兜底 chitchat)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: recommend_chat orchestrator（Unit C）+ L3 写入

**Files:**
- Create: `backend/app/services/resume_copilot/recommend_chat.py`
- Test: `backend/tests/resume_copilot/test_recommend_chat.py`

一轮: parse_intent → apply_delta → 持久化 working_query_json → search_candidates → 返回；`remember` 非空 → 走 `dispatcher.write_memory(category='preference')`（L3，唯一写入路径）。

- [ ] **Step 1: 写失败测试（mock parse + mock search + spy memory）**

```python
# backend/tests/resume_copilot/test_recommend_chat.py
import app.services.resume_copilot.recommend_chat as rc


def test_refine_applies_delta_and_returns_feed(monkeypatch):
    monkeypatch.setattr(rc, "parse_intent",
        lambda msg, current_query, client=None: {"intent": "refine",
            "query_delta": {"add_sub_cats": ["固收+多资产"]}, "remember": None, "reply": "已加固收"})
    monkeypatch.setattr(rc, "search_candidates", lambda db, q, **k: [{"company": "中信资管"}])
    written = []
    monkeypatch.setattr(rc, "_write_preference_memory", lambda **kw: written.append(kw))
    out = rc.run_recommend_turn(db=None, session=_FakeSession(), message="多来点固收")
    assert out["intent"] == "refine"
    assert out["working_query"]["sub_cats"] == ["固收+多资产"]
    assert out["feed"] == [{"company": "中信资管"}]
    assert written == []  # remember 为空 → 不写记忆
    assert out["trace"]["intent"] == "refine"           # TraceCard 数据源
    assert out["trace"]["query_delta"] == {"add_sub_cats": ["固收+多资产"]}
    assert out["remembered"] is None                    # 没写 L3 → 不弹 MemoryToast


def test_remember_triggers_l3_write(monkeypatch):
    monkeypatch.setattr(rc, "parse_intent",
        lambda msg, current_query, client=None: {"intent": "refine", "query_delta": {"exclude": ["国企"]},
            "remember": {"dimension": "company_type", "value": "非国企"}, "reply": "已排除国企"})
    monkeypatch.setattr(rc, "search_candidates", lambda db, q, **k: [])
    written = []
    monkeypatch.setattr(rc, "_write_preference_memory", lambda **kw: written.append(kw))
    out = rc.run_recommend_turn(db=None, session=_FakeSession(user_key="u1"), message="我一直不考虑国企")
    assert len(written) == 1 and written[0]["value"] == "非国企"
    assert out["remembered"] == {"dimension": "company_type", "value": "非国企"}  # MemoryToast 数据源


def test_chitchat_does_not_change_query(monkeypatch):
    monkeypatch.setattr(rc, "parse_intent",
        lambda msg, current_query, client=None: {"intent": "chitchat", "query_delta": {}, "remember": None, "reply": "hi"})
    monkeypatch.setattr(rc, "search_candidates", lambda db, q, **k: [{"company": "X"}])
    sess = _FakeSession(working_query_json='{"sub_cats": ["公募权益研究员"]}')
    out = rc.run_recommend_turn(db=None, session=sess, message="你好")
    assert out["working_query"]["sub_cats"] == ["公募权益研究员"]  # 不变
    assert out["feed"] is None  # chitchat 不重排


class _FakeSession:
    def __init__(self, working_query_json=None, user_key="u1"):
        self.working_query_json = working_query_json
        self.user_key = user_key
        self.confirmed_profile = None
```

- [ ] **Step 2: 跑确认 FAIL**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/test_recommend_chat.py -v`
Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现**

```python
# backend/app/services/resume_copilot/recommend_chat.py
"""Unit C: NL 推荐 agent 一轮 orchestrator。

parse_intent → apply_delta → 持久化 working_query → search_candidates → 返回。
remember 非空 → L3 写统一记忆(经 dispatcher.write_memory, 唯一写入路径)。
chitchat/intel/lock 不重排 feed(feed=None)。
"""
from __future__ import annotations

import json
import logging

from app.services.resume_copilot.working_query import WorkingQuery, apply_delta
from app.services.resume_copilot.recommend_intent import parse_intent
from app.services.resume_copilot.recommend_search import search_candidates

logger = logging.getLogger(__name__)


def _load_query(session) -> WorkingQuery:
    raw = getattr(session, "working_query_json", None)
    if raw:
        try:
            return WorkingQuery(**json.loads(raw))
        except Exception:
            pass
    return WorkingQuery()


def _write_preference_memory(*, db, user_key, dimension, value, session_id):
    """L3: 经唯一写入路径落 account_memory preference 行。绝不直插。"""
    from app.services.memory.dispatcher import write_memory
    from app.services.memory.schemas import PreferencePayload
    write_memory(
        db, user_key=user_key, category="preference",
        summary=f"偏好·{dimension}:{value}"[:80],
        payload=PreferencePayload(dimension=dimension, value=value),
        source_module="recommend_chat", source_session_id=session_id,
    )


def run_recommend_turn(*, db, session, message: str, client=None) -> dict:
    q = _load_query(session)
    parsed = parse_intent(message, current_query=q.model_dump(), client=client)
    intent = parsed["intent"]
    feed = None
    if intent in ("refine", "company_focus"):
        q = apply_delta(q, parsed["query_delta"])
        try:
            session.working_query_json = json.dumps(q.model_dump(), ensure_ascii=False)
        except Exception:
            logger.warning("persist working_query failed", exc_info=True)
        feed = search_candidates(db, q)
    rem = parsed.get("remember")
    remembered = None
    if rem and getattr(session, "user_key", None):
        try:
            _write_preference_memory(db=db, user_key=session.user_key,
                dimension=rem["dimension"], value=rem["value"],
                session_id=getattr(session, "id", None))
            remembered = {"dimension": rem["dimension"], "value": rem["value"]}
        except Exception:
            logger.warning("L3 preference write failed", exc_info=True)
    trace = {
        "intent": intent,
        "query_delta": parsed.get("query_delta") or {},
        "remember_note": _remember_note(rem, remembered),  # 人话备注, 给 TraceCard 第三行
    }
    return {"intent": intent, "reply": parsed["reply"], "feed": feed,
            "working_query": q.model_dump(), "trace": trace, "remembered": remembered}


def _remember_note(rem, remembered) -> str:
    """TraceCard 的 remember 行备注: 区分「升 L3 长期偏好」与「一次性不升」。"""
    if remembered:
        return f"{remembered['dimension']}={remembered['value']} · 稳定偏好, 已升 L3"
    if rem:
        return "识别到偏好但未写库(缺登录/写失败)"
    return "一次性调整, 不升 L3"
```
> 注: 测试用 monkeypatch 替换 `rc.parse_intent`/`rc.search_candidates`/`rc._write_preference_memory`，所以它们必须是模块级名字（如上）。`db=None` 在测试里安全因为这些都被 mock。`trace`/`remembered` 是设计稿的 TraceCard / MemoryToast 数据源；`chitchat`/`intel`/`lock` 时 `feed=None`（feed 不重排），但 `trace` 仍回（TraceCard 照样显意图）。

- [ ] **Step 4: 跑确认 PASS**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/test_recommend_chat.py -v`
Expected: 3 passed。

- [ ] **Step 5: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/resume_copilot/recommend_chat.py backend/tests/resume_copilot/test_recommend_chat.py
git commit -m "$(cat <<'EOF'
feat(reco): recommend_chat orchestrator + L3 偏好写入(经 dispatcher.write_memory)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: 三个端点（recommend-chat / working-query / recommend-deepen）

**Files:**
- Modify: `backend/app/routers/resume_copilot.py`

只加路由。`recommend-chat` 跑 Unit C；`working-query` 读当前；`recommend-deepen` 触发慢路（复用现有 v2 Pro 精排+理由）。**改写 `/chat`、`/plan` 一行不动。**

- [ ] **Step 1: 核对 router 符号 + 慢路函数**

Run: `cd backend && grep -n "_get_session_or_404\|class .*In(BaseModel)\|BaseModel as\|def rerank_top_n\|def generate_narrative\|background_tasks" app/routers/resume_copilot.py app/services/phase_g/recommendation_v2/rerank.py app/services/phase_g/recommendation_v2/narrative.py | head`
确认 session 查找 helper、in-body model 基类名（前面任务发现是 `_BaseModel`）、慢路函数签名、是否已 import `BackgroundTasks`。

- [ ] **Step 2: 加请求体 model + 三路由**

在 router 的 in-body model 区加:

```python
class RecommendChatIn(_BaseModel):
    message: str = ""

class RecommendDeepenIn(_BaseModel):
    job_ids: list[str] = []

class WorkingQueryUpdateIn(_BaseModel):
    remove_sub_cat: str | None = None   # 删一个 add chip (× 移除)
    clear_only: bool = False            # 清 only 收窄
    sort: str | None = None             # 改排序 (match/fresh/pay)
```

在路由区加（用真实 session helper 名）:

```python
@router.post("/sessions/{session_id}/recommend-chat")
def recommend_chat(session_id: int, payload: RecommendChatIn,
                   background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """NL 推荐 agent 一轮: 自然语言 → 工作查询重排 → 流动 feed。"""
    from app.services.resume_copilot.recommend_chat import run_recommend_turn
    session = _get_session_or_404(db, session_id)
    out = run_recommend_turn(db=db, session=session, message=payload.message)
    db.commit()  # 持久化 working_query_json + L3 记忆
    return out


@router.get("/sessions/{session_id}/working-query")
def get_working_query(session_id: int, db: Session = Depends(get_db)):
    import json as _json
    session = _get_session_or_404(db, session_id)
    raw = getattr(session, "working_query_json", None)
    try:
        return {"working_query": _json.loads(raw) if raw else None}
    except Exception:
        return {"working_query": None}


@router.post("/sessions/{session_id}/recommend-deepen")
def recommend_deepen(session_id: int, payload: RecommendDeepenIn, db: Session = Depends(get_db)):
    """慢路: 对指定岗位跑 Pro 精排 + 4-anchor 理由(复用 v2 慢路)。"""
    from app.services.resume_copilot.recommend_deepen import deepen_jobs  # Step 3 新建薄封装
    session = _get_session_or_404(db, session_id)
    return {"items": deepen_jobs(db, session, payload.job_ids)}


@router.post("/sessions/{session_id}/working-query/update")
def update_working_query(session_id: int, payload: WorkingQueryUpdateIn, db: Session = Depends(get_db)):
    """结构化操作工作查询(删 add chip / 清 only / 改 sort) + 重排, 仍走快路, 不调 LLM。"""
    import json as _json
    from app.services.resume_copilot.working_query import WorkingQuery
    from app.services.resume_copilot.recommend_search import search_candidates
    session = _get_session_or_404(db, session_id)
    raw = getattr(session, "working_query_json", None)
    q = WorkingQuery(**_json.loads(raw)) if raw else WorkingQuery()
    if payload.remove_sub_cat:
        q = q.model_copy(update={"sub_cats": [s for s in q.sub_cats if s != payload.remove_sub_cat]})
    if payload.clear_only:
        q = q.model_copy(update={"only": False})
    if payload.sort in ("match", "fresh", "pay"):
        q = q.model_copy(update={"sort": payload.sort})
    session.working_query_json = _json.dumps(q.model_dump(), ensure_ascii=False)
    db.commit()
    return {"working_query": q.model_dump(), "feed": search_candidates(db, q)}
```
若 `BackgroundTasks` 未 import，在文件顶部 `from fastapi import ... BackgroundTasks` 补上。`remove_sub_cat` 只能删 `sub_cats`（add 集），删不动 `seed_sub_cats`（confirmed 派生不可删，与设计稿深色 chip 一致）。

- [ ] **Step 3: 新建 `recommend_deepen.py` 薄封装**

```python
# backend/app/services/resume_copilot/recommend_deepen.py
"""慢路: 对一批 job 跑 Pro 精排 + 理由。复用 recommendation_v2 慢路, 失败回落原 item。"""
from __future__ import annotations
import logging
logger = logging.getLogger(__name__)


def deepen_jobs(db, session, job_ids: list[str]) -> list[dict]:
    if not job_ids:
        return []
    from app.services.resume_copilot.working_query import WorkingQuery
    from app.services.resume_copilot.recommend_search import search_candidates
    # 取当前工作查询的 feed, 过滤到指定 job_ids, 对其跑慢路
    import json
    raw = getattr(session, "working_query_json", None)
    q = WorkingQuery(**json.loads(raw)) if raw else WorkingQuery()
    feed = search_candidates(db, q, limit=60)
    def jid(it): return it.get("job_id") if isinstance(it, dict) else getattr(it, "job_id", None)
    targets = [it for it in feed if jid(it) in set(job_ids)]
    # 复用现有 v2 Pro 精排: 见 recommendation._recommend_v2_dispatcher 里 rerank_top_n/generate_narrative 调法
    try:
        from app.services.resume_copilot.recommendation import _deepen_items  # 若已有则用
        deepened = _deepen_items(db, session, targets)
    except Exception:
        logger.warning("deepen slow-path unavailable, returning rule items", exc_info=True)
        deepened = targets  # 回落: 至少返回规则 item, 不崩
    return [_shape_deepen_item(it) for it in deepened]


def _shape_deepen_item(it: dict) -> dict:
    """把慢路结果整成设计稿 JobCard 深挖态要的形状:
    - enhanced_score: Pro 精排分(慢路给的 rerank score / final_score, 以实际字段为准)
    - anchors: 4 段 [label, text] — 赛道契合 / 平台梯队 / 岗位画像 / 不确定点
    - used_ai: True
    narrative 4-anchor 已是 v2 既有产物(narrative.py 的 4 锚点); 这里只做字段对齐。"""
    if not isinstance(it, dict):
        return it
    it["used_ai"] = True
    if it.get("enhanced_score") is None:
        it["enhanced_score"] = it.get("rerank_score") or it.get("final_score") or it.get("score")
    if "anchors" not in it:
        nar = it.get("narrative") or it.get("reasons") or {}
        # narrative 既有结构 → [label,text] 列表; 形状以 narrative.py 实际产出为准
        it["anchors"] = _narrative_to_anchors(nar)
    return it


def _narrative_to_anchors(nar) -> list[list[str]]:
    """v2 narrative(4-anchor) → [[label,text],...]。dict/list/str 都兜底, 不崩。"""
    labels = ["赛道契合", "平台梯队", "岗位画像", "不确定点"]
    if isinstance(nar, dict):
        keys = list(nar.keys())
        if keys:
            return [[str(k), str(nar[k])] for k in keys][:4]
        return []
    if isinstance(nar, list):
        out = []
        for i, v in enumerate(nar[:4]):
            if isinstance(v, (list, tuple)) and len(v) == 2:
                out.append([str(v[0]), str(v[1])])
            else:
                out.append([labels[i] if i < 4 else "理由", str(v)])
        return out
    return [["理由", str(nar)]] if nar else []
```
> 实现者: 若 `recommendation.py` 没有可复用的 `_deepen_items`，按 `_recommend_v2_dispatcher` 里调 `rerank_top_n` + `generate_narrative` 的方式，在本文件内联一个最小慢路（top-N 精排 + 4-anchor 理由），失败回落 `targets`。**这是本子项唯一允许跑 Pro 的地方。** `_narrative_to_anchors` 的真实形状以 `narrative.py` 既有 4-anchor 产出为准（grep `generate_narrative` 看返回结构）；保证最终每条带 `enhanced_score` + `anchors`（≤4 段 `[label,text]`）+ `used_ai=True`。

- [ ] **Step 4: 套件 + 端点冒烟**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/ -q`
Expected: 全绿。
Run 冒烟:
```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
sid=145
print('chat', c.post(f'/api/resume-copilot/sessions/{sid}/recommend-chat', json={'message':'多来点固收'}).status_code)
print('wq', c.get(f'/api/resume-copilot/sessions/{sid}/working-query').status_code)
"
```
Expected: 两个 200（chat 实跑 flash，可能慢几秒；若 flash 失败兜底 chitchat 仍 200）。

- [ ] **Step 5: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/routers/resume_copilot.py backend/app/services/resume_copilot/recommend_deepen.py
git commit -m "$(cat <<'EOF'
feat(reco): recommend-chat/working-query/recommend-deepen 端点(改写端点不动)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Unit 2 — 前端接入

### Task 8: 类型 + API（recommend-chat / working-query / recommend-deepen）

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/types.ts`
- Modify: `resume-copilot-web/components/resume-copilot/api.ts`

> 前端不走 TDD。验收 = `npm run lint`(0 error) + `npm run build` 过。

- [ ] **Step 1: 加类型（types.ts）— 对齐设计稿 nlrec-feed/chat 渲染字段**

```typescript
export interface WorkingQuery {
  seed_sub_cats: string[];  // confirmed 派生 · 深色不可删 chip
  sub_cats: string[];       // NL 加的 · 陶土色可删 chip
  companies: string[]; locations: string[];
  exclude: string[]; sort: string; only: boolean; note: string;
}
// 一轮对话 trace（设计稿可展开 TraceCard 数据源）
export interface RecommendTrace { intent: string; query_delta: Record<string, unknown>; remember_note: string; }
// 深挖产物（设计稿 JobCard 深挖态：Enhanced 分 + 4-anchor）— item 上的可选增量字段
export interface RecommendFeedItem extends ResumeRecommendationItem {
  base_score?: number;
  enhanced_score?: number | null;
  used_ai?: boolean;
  anchors?: [string, string][];   // [[label,text],...] ≤4
}
export interface RecommendTurnResponse {
  intent: string;
  reply: string;
  feed: RecommendFeedItem[] | null;
  working_query: WorkingQuery;
  trace: RecommendTrace;
  remembered: { dimension: string; value: string } | null;  // 非空 → 弹 MemoryToast
}
```
> `RecommendFeedItem` 扩展现有 `ResumeRecommendationItem`（feed 卡仍复用既有公司/赛道/in_skeleton 字段），只加设计稿要的分数/anchor 字段。company-intel 卡复用已有 `IntelDrawer`/intel 类型（`workspace/intel/`），不新造。

- [ ] **Step 2: 加 API（api.ts，复用现有 fetch helper / 注入 user-key 头）**

```typescript
export async function postRecommendChat(sessionId: number, message: string): Promise<RecommendTurnResponse> {
  const res = await fetch(`/api/resume-copilot/sessions/${sessionId}/recommend-chat`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error(`recommend-chat ${res.status}`);
  return res.json();
}
export async function getWorkingQuery(sessionId: number): Promise<{ working_query: WorkingQuery | null }> {
  const res = await fetch(`/api/resume-copilot/sessions/${sessionId}/working-query`);
  if (!res.ok) throw new Error(`working-query ${res.status}`);
  return res.json();
}
// 删 add chip / 清 only / 改 sort → 重排（快路, 不调 LLM）
export async function updateWorkingQuery(sessionId: number, op: { remove_sub_cat?: string; clear_only?: boolean; sort?: string }): Promise<{ working_query: WorkingQuery; feed: RecommendFeedItem[] }> {
  const res = await fetch(`/api/resume-copilot/sessions/${sessionId}/working-query/update`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(op),
  });
  if (!res.ok) throw new Error(`working-query/update ${res.status}`);
  return res.json();
}
export async function postRecommendDeepen(sessionId: number, jobIds: string[]): Promise<{ items: RecommendFeedItem[] }> {
  const res = await fetch(`/api/resume-copilot/sessions/${sessionId}/recommend-deepen`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ job_ids: jobIds }),
  });
  if (!res.ok) throw new Error(`recommend-deepen ${res.status}`);
  return res.json();
}
```
> 若 api.ts 里 sibling fetcher 用 `requestJson` 包装注入 `X-Resume-User-Key`/`Authorization`，照它的风格改写这四个。

- [ ] **Step 3: lint + build**

Run: `cd resume-copilot-web && npm run lint && npm run build 2>&1 | tail -15`
Expected: lint 0 error；build 成功。

- [ ] **Step 4: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add resume-copilot-web/components/resume-copilot/types.ts resume-copilot-web/components/resume-copilot/api.ts
git commit -m "$(cat <<'EOF'
feat(reco): 前端 recommend-chat/working-query/deepen 类型 + API

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

> **前端 4 个任务（9–12）= 按 hi-fi 设计稿像素级还原一个独立三栏「推荐工作台」。** 源在 `resume-copilot-web/.design-ref/nl-recommendation/`（`nlrec-app/chat/feed.jsx` + `NL-recommendation-workspace.html`）。实现者**逐文件读设计稿 → 移植成 TSX**，用 repo 现有 `.hf` 体系（`components/hifi/hifi-tokens.css` 的 token + `app/globals.css` 的 `.border-beam`），缺的 token/class 才在 `workspace/recommend-agent/recommend-agent.css` 里补（按 CLAUDE.md「三套设计系统严格隔离」，scope 到 `.hf` 或 `[data-theme="recommend"]`）。不照搬设计稿的脚本化假数据（`nlrec-data.jsx` 只看 UI 契约），数据全走 Task 8 的真实 API。每个任务以 `npm run lint`(0 error) + `npm run build` 收尾。

### Task 9: 独立「推荐工作台」页面 — 路由 + 三栏 Shell + 顶栏 + 会话侧栏（隐藏改写入口）

**Files:**
- Create: `resume-copilot-web/app/recommend/page.tsx`（新路由，独立全屏页）
- Create: `resume-copilot-web/components/resume-copilot/workspace/recommend-agent/RecommendWorkspaceShell.tsx`（三栏 grid + 顶层状态机：msgs / workingQuery / feed / thinking / lockOpen）
- Create: `.../recommend-agent/RecommendTopBar.tsx`、`.../recommend-agent/RecommendSidebar.tsx`
- Create: `.../recommend-agent/recommend-agent.css`（仅补 repo 缺的 token/class，scope 隔离）

**设计稿对应:** `nlrec-app.jsx` 的 `TopBar` / `Sidebar` / `App`（三栏 grid `208px minmax(340px,1fr) minmax(372px,440px)`）。

- [ ] **Step 1: 看清 repo 既有约定**

Run: `cd resume-copilot-web && grep -rn "sessionId\|getDemoSession\|guest\|user-key\|X-Resume-User-Key" app/resume-copilot/page.tsx components/resume-copilot/workspace/WorkspaceShell.tsx | head -20`
确认现有 workspace 怎么拿 sessionId（demo / guest / 登录）+ user-key 头怎么注入；新页照同一套解析（不另造 session 机制）。

- [ ] **Step 2: 建 Shell + 顶栏 + 侧栏（移植设计稿）**

- `RecommendTopBar`：JobRadar logo · 「推荐工作台」· `NL 推荐 agent` pill · 右侧「简历编辑器」ghost 按钮（链到现有 `/resume-copilot`，子项④ 拆分前的过渡入口）· 用户头像。照 `nlrec-app.jsx` TopBar。
- `RecommendSidebar`：「新会话」主按钮 + 会话列表（先用现有 sessions API 或占位静态，按 Step 1 决定）+ **底部虚线卡「简历改写入口 · 已隐藏（组件不删 → 子项④ 物理拆分）」**（设计稿明文的「只加不删」隐藏入口）。
- `RecommendWorkspaceShell`：三栏 grid，持有 `useState`：`msgs`/`workingQuery`/`feed`/`thinking`/`lockOpen`/`deepening`。中栏右栏先放占位，Task 10/11 填。初始 `workingQuery` 由 `getWorkingQuery(sessionId)` 拉；为空则后端 seed（向后兼容）。

- [ ] **Step 3: 挂路由 + lint + build**

`app/recommend/page.tsx` 渲染 `<RecommendWorkspaceShell sessionId={...} />`。
Run: `cd resume-copilot-web && npm run lint && npm run build 2>&1 | tail -15`
Expected: lint 0 error；build 成功；`/recommend` 在 build 输出里。

- [ ] **Step 4: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add resume-copilot-web/app/recommend/ resume-copilot-web/components/resume-copilot/workspace/recommend-agent/
git commit -m "$(cat <<'EOF'
feat(reco): 独立推荐工作台页面骨架(三栏 Shell + 顶栏 + 会话侧栏 + 隐藏改写入口)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: NL 对话栏（中栏）— 接 `postRecommendChat`，意图解析可视化

**Files:**
- Create: `.../recommend-agent/RecommendChatPane.tsx`（栏头 + 消息流 + Composer）
- Create: `.../recommend-agent/chat/{Turn,ThinkingCard,TraceCard,MemoryToast,Composer}.tsx`

**设计稿对应:** `nlrec-chat.jsx`（`Turn` / border-beam `ThinkingCard`「意图解析中 · flash」/ 可展开 `TraceCard`(intent·query_delta·remember_note) / `MemoryToast` / `Composer` 带快捷 chip）。company-intel 卡复用现有 `workspace/intel/` 组件，不在这里重造。

- [ ] **Step 1: 栏头 + 消息流壳**

栏头：Avatar + 「推荐 agent」+ 副标「说人话换方向 · 秒级重排，不动确认赛道」+ 右侧 `快路 · 规则排` 绿点 pill（`nowrap`，设计稿踩过换行坑）。消息流 = `msgs.map`，类型 `turn`(me/ai) / `trace` / `memory` / `intel`。

- [ ] **Step 2: 发送接 `postRecommendChat`**

Composer 发送 → push 用户 turn → `setThinking(true)`（渲染 border-beam `ThinkingCard`）→ `await postRecommendChat(sessionId, text)`：
- push agent `reply` turn；
- push `trace` 卡（来自 `resp.trace`，默认折叠，可展开看 `intent` / `query_delta` JSON / `remember_note`）；
- 若 `resp.remembered` 非空 → push `MemoryToast`「记忆 → L3 preference · 后台落库（{dimension}={value}）」；
- 若 `resp.feed !== null` → 经 Shell 的 `setFeed(resp.feed)` 把流动 feed 推给右栏（feed 状态提升在 Shell）；
- 同步 `setWorkingQuery(resp.working_query)`。
- react-compiler 合规：所有 setState 在 `await`/`.then` 之后的回调里，不在 effect body 顶层 setState。
- 失败兜底：catch → push 一条降级 ai turn「没太听懂，换个说法？feed 没动」（绝不静默）。

- [ ] **Step 3: Composer 快捷 chip**

输入框上方放 4 个示例 chip（多来点固收 / 一直不考虑国企 / 只看头部券商资管按薪资 / 讲讲某家），点击=把该文案当消息发出。placeholder 用设计稿那句。

- [ ] **Step 4: lint + build + Commit**

Run: `cd resume-copilot-web && npm run lint && npm run build 2>&1 | tail -15` → 0 error / 成功。
```bash
cd /home/chuanbo/projects/JobRadar
git add resume-copilot-web/components/resume-copilot/workspace/recommend-agent/
git commit -m "$(cat <<'EOF'
feat(reco): NL 对话栏 — postRecommendChat + 意图解析 trace + L3 记忆提示

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: 流动 feed 栏（右栏）— 工作查询 readout + JobCard（Base/Enhanced + 4-anchor）

**Files:**
- Create: `.../recommend-agent/RecommendFeedPane.tsx`、`.../recommend-agent/feed/{WorkingQueryReadout,JobCard,ScorePill,QueryChip}.tsx`

**设计稿对应:** `nlrec-feed.jsx`（`FeedPane` 头部工作查询 readout + `JobCard` Base/Enhanced `ScorePill` + 深挖 4-anchor + 空态）。

- [ ] **Step 1: 工作查询 readout**

头部：「流动 feed · 按工作查询 · {feed.length} 个在招」+ 右侧「锁定为主方向 →」按钮（Task 12 接弹层）。下面 chip 行：
- `seed_sub_cats` → 深色 `QueryChip kind=seed`（不可删）；
- `sub_cats` → 陶土色 `QueryChip kind=add` 带 ×（点 × → `updateWorkingQuery(sessionId,{remove_sub_cat})` → `setFeed`/`setWorkingQuery`）；
- `exclude` → 虚线 `kind=excl`；
- `only` → 深色 `only=…` pill，点击 → `updateWorkingQuery(sessionId,{clear_only:true})`；
- 右端排序指示「排序：匹配/新鲜度/薪资 ▾」，点击切换 → `updateWorkingQuery(sessionId,{sort})`。

- [ ] **Step 2: JobCard**

每卡：`#rank` · 岗位名 · `公司 · 地点` · 新鲜度；`ScorePill base`（`item.base_score`，永远显）+ `ScorePill enhanced`（深挖前 dashed pending「—」，深挖后陶土实色 `item.enhanced_score`）；未深挖显「规则三维分（赛道匹配/新鲜度/平台梯队）· used_ai=false」；底部两按钮「🏢 讲讲这家」+「深挖（Pro 精排）→」。复用既有 in_skeleton 小标（梯队内/外）。

- [ ] **Step 3: 深挖 + 讲讲这家**

- 深挖：点击 → 该卡进 `deepening` 态（按钮转「精排中…」spinner）→ `await postRecommendDeepen(sessionId,[jobId])` → 用返回 item 替换该卡（补 `enhanced_score` + `anchors`）→ 卡内展开「慢路 · 4-anchor 理由」段（`anchors.map(([k,v])=> 标签+文本)`）+「Pro 精排 ✓」pill。
- 讲讲这家：点击 → 经 Shell 在中栏 push 一条用户 turn「讲讲{公司}」+ 拉公司情报卡（复用现有 intel 组件/接口；无结构化情报则降级文案，不静默）。

- [ ] **Step 4: 空态**

`feed.length===0` → 设计稿文案「这方向库里暂无在招 · 要不要看相邻方向，或放宽地点？绝不静默空白」。

- [ ] **Step 5: lint + build + Commit**

Run: `cd resume-copilot-web && npm run lint && npm run build 2>&1 | tail -15` → 0 error / 成功。
```bash
cd /home/chuanbo/projects/JobRadar
git add resume-copilot-web/components/resume-copilot/workspace/recommend-agent/
git commit -m "$(cat <<'EOF'
feat(reco): 流动 feed 栏 — 工作查询 readout + JobCard(Base/Enhanced) + 深挖 4-anchor

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: 锁定弹层 + 「锁定为主方向」（L2 唯一 confirmed 入口）

**Files:**
- Create: `.../recommend-agent/LockModal.tsx`
- Modify: `.../recommend-agent/RecommendFeedPane.tsx`（头部按钮接弹层）+ `RecommendWorkspaceShell.tsx`（`lockOpen` 状态 + confirm 落库）

**设计稿对应:** `nlrec-app.jsx` 的 `LockModal` + `confirmLock`。

- [ ] **Step 1: LockModal**

照设计稿：标题「锁定为主方向？」+ 说明「把当前工作查询提交成 confirmed 赛道 — WorkingQuery 唯一会落 confirmed 的入口」+ 「将写入 confirmed」chip 区（展示 `effective_sub_cats`= seed+add）+「梯队骨架（子项②）据此重塑 · 走 PUT /preferences」脚注 +「再想想 / 锁定为主方向」两按钮。

- [ ] **Step 2: confirm 落库（L2 唯一入口）**

确认 → 调现有 `putResumeCopilotPreferences(sessionId, { ...现有 preferred_tracks, confirmed_sub_cats: [...seed_sub_cats, ...sub_cats] })`（**唯一**落 confirmed 的地方；用合并集）→ 成功后 feed 头部按钮变绿 pill「✓ 已锁定为主方向」+ 中栏 push「已锁定 ✓ 梯队骨架会据此重塑」+ MemoryToast「L2 → PUT /preferences · confirmed 赛道已更新」。
> 注意：调 `putResumeCopilotPreferences` 前先 grep 它现有签名，把现有字段原样带上、只追加 `confirmed_sub_cats`（别把别的 preference 字段冲掉）。

- [ ] **Step 3: lint + build + Commit**

Run: `cd resume-copilot-web && npm run lint && npm run build 2>&1 | tail -15` → 0 error / 成功。
```bash
cd /home/chuanbo/projects/JobRadar
git add resume-copilot-web/components/resume-copilot/workspace/recommend-agent/
git commit -m "$(cat <<'EOF'
feat(reco): 锁定弹层 + 锁定为主方向(L2 唯一 confirmed 入口, 走 PUT /preferences)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Unit 3 — 端到端验收

### Task 13: 端到端验收（铁律核验 + UI 冒烟）

**Files:** 无（纯验证）

- [ ] **Step 1: 后端确定性端到端（无 LLM，mock 意图）**

```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
import app.services.resume_copilot.recommend_chat as rc
from app.database import SessionLocal
# 用真 DB + 真 search, 但 mock 意图解析成确定 delta
seq = [
  {'intent':'refine','query_delta':{'add_sub_cats':['公募权益研究员']},'remember':None,'reply':'权益'},
  {'intent':'refine','query_delta':{'add_companies':['中欧基金'],'only':True},'remember':None,'reply':'只看中欧'},
]
it = iter(seq)
rc.parse_intent = lambda msg, current_query, client=None: next(it)
class S:  # 假 session, 不落库
  working_query_json=None; user_key='__test__'; id=999; confirmed_profile=None
s=S(); db=SessionLocal()
o1=rc.run_recommend_turn(db=db, session=s, message='做权益'); print('1 sub_cats', o1['working_query']['sub_cats'], 'feed', len(o1['feed'] or []))
o2=rc.run_recommend_turn(db=db, session=s, message='只看中欧'); 
companies=set((x.get('company') if isinstance(x,dict) else getattr(x,'company','')) for x in (o2['feed'] or []))
print('2 only 中欧?', companies)
"
```
Expected: 第 1 轮 feed 非空；第 2 轮 `only` 生效，feed 公司集合只剩中欧基金（或为空，若中欧当前无在招——但库里有 2 个权益岗,应非空）。

- [ ] **Step 2: 铁律 — confirmed preferences 全程不被写**

```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
import sqlite3
c=sqlite3.connect('data/jobradar.db').cursor()
import json
r=c.execute('SELECT preferences_json FROM resume_preference_profiles WHERE session_id=145').fetchone()
print('145 confirmed_sub_cats(应不含临时探索):', json.loads(r[0]).get('confirmed_sub_cats') if r else 'no row')
"
```
Expected: 不因上面的 recommend-chat 调用而出现临时探索的 sub_cats（对话不写 confirmed）。

- [ ] **Step 3: 铁律 — 快路不跑 Pro**

确认 `recommend-chat` 路径里没有 `rerank_top_n`/`generate_narrative` 调用:
Run: `cd backend && grep -n "rerank_top_n\|generate_narrative" app/services/resume_copilot/recommend_chat.py app/services/resume_copilot/recommend_search.py`
Expected: 无输出（快路零 Pro 调用；Pro 只在 `recommend_deepen.py`）。

- [ ] **Step 4: 回归套件**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/ tests/phase_g/ -q`
Expected: 全绿（除已知 2 个 GT schema 预存失败）。

- [ ] **Step 5: 前端最终 lint + build + UI 冒烟**

Run: `cd resume-copilot-web && npm run lint && npm run build 2>&1 | tail -15`
Expected: lint 0 error；build 成功；`/recommend` 出现在路由清单。
UI 冒烟（dev server 起一次，非 sudo）：`npm run dev`（:3001）→ 打开 `/recommend` → 走一遍设计稿演示路径「多来点固收 → 一直不考虑国企 → 只看头部券商资管按薪资 → 讲讲某家 → 任意卡片深挖 → 锁定为主方向」，肉眼核对：意图解析 trace 可展开、排除后弹 L3 记忆提示、深挖出 Enhanced 分 + 4-anchor、锁定弹层走通。

- [ ] **Step 6: 清理测试残留**

若 Step 1 给 `__test__` user_key 写了 preference 记忆,删掉:
```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
import sqlite3; conn=sqlite3.connect('data/jobradar.db'); c=conn.cursor()
c.execute(\"DELETE FROM account_memory WHERE user_key='__test__'\"); conn.commit(); print('cleaned', c.rowcount)
"
```
（`__test__` 非 reserved key，理论上 write_memory 不会 block，所以需清理；若 mock 路径根本没写则 rowcount=0。）

---

## Self-Review（对照 spec）

- **决策 1 分开互补**: 本子项只产流动 feed(右栏)，骨架是子项②，feed 经 Task 11 渲染、Task 12 锁定联动 ✓
- **决策 2 临时工作查询不动 confirmed**: Task 1/3/6（L1，seed/add 分离）+ Task 13 Step 2（铁律核验）✓
- **决策 3 快慢分离**: Task 4/6 快路无 LLM rerank（含 working-query/update 重排）；Task 7 `recommend-deepen` 才慢路；Task 13 Step 3 核验 ✓
- **决策 4 只加不删**: Task 7（改写端点不动）+ Task 9 Step 2（侧栏隐藏改写入口、组件不删）✓
- **决策 5 结构化 JSON 非 function-calling**: Task 5（`response_format: json_object`）✓
- **决策 6 三层持久化**: L1=Task 2 列/Task 6；L2=Task 12 锁定→preferences；L3=Task 6 `_write_preference_memory`→`write_memory` ✓
- **Unit A WorkingQuery**: Task 1/3 ✓ ; **Unit B search_candidates**: Task 4 ✓ ; **Unit C agent loop**: Task 5/6 ✓ ; **Unit D 快慢**: Task 4/7 ✓ ; **Unit E 锁定**: Task 12 ✓
- **设计稿覆盖**: 顶栏+会话侧栏+隐藏改写卡=Task 9；对话栏 Turn/border-beam ThinkingCard/可展开 TraceCard/MemoryToast/Composer=Task 10；feed 工作查询 readout(seed/add/excl/only+sort)/JobCard Base+Enhanced/4-anchor 深挖/讲讲这家/空态=Task 11；LockModal=Task 12 ✓
- **错误处理**: 空结果(Task 4 不藏岗/Task 7 deepen 回落/Task 11 空态文案)、意图不清/LLM 失败(Task 5 兜底 chitchat + Task 10 catch 降级 turn)、L3 写失败不崩(Task 6 try/except) ✓
- **向后兼容**: `working_query_json` 缺失退回 confirmed(Task 6 `_load_query` 默认空 WorkingQuery) ✓
- **类型一致**: `WorkingQuery(含 seed_sub_cats/effective_sub_cats)`/`apply_delta`/`seed_working_query`/`search_candidates`/`parse_intent`/`run_recommend_turn(回 trace/remembered)`/`_write_preference_memory`/`deepen_jobs(回 enhanced_score/anchors)` 全程同名；前端 `WorkingQuery`/`RecommendTrace`/`RecommendFeedItem`/`RecommendTurnResponse`/`postRecommendChat`/`getWorkingQuery`/`updateWorkingQuery`/`postRecommendDeepen` 一致 ✓
- **YAGNI**: 子项②③④、自由文本映射修复、每轮 Pro、自动晋升 均不做 ✓
- **铁律覆盖**: 不写 confirmed(决策2)、L3 不直插(Task 6 经 dispatcher)、不藏岗(Task 4)、快路无 Pro(Task 13 Step3)、`git add` 限定文件 — 各任务 commit 段已限定 ✓
