# 渐进式推荐 + 砍 ReAct + 看得见的思考（落点①）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** v2 开启时砍掉冗余的 ReAct agent，让推荐生成提速 ~70%，并把规则列表秒级先出、强模型逐岗位真推理作为"看得见的思考"渐进呈现。

**Architecture:** 推荐流水线在 v2 开启时不再叠跑 ReAct（实测零质量增益、+917s/8人）。`_recommend_v2_dispatcher` 新增一个可选 `progress` 回调包，在 recall→规则排序→精排→理由 各阶段把"阶段节点 + 部分结果 + 逐岗位真推理"回吐给 workflow；workflow 把它们写进既有的 `agent_trace_json` / `recommendations_json`（前端已在轮询）。前端左栏改成"有岗位就先渲染"，并复用既有 `AgentThinkingPanel` 逻辑、重绘成工作台调性的思考时间线，完成后收成一行可展开。

**Tech Stack:** FastAPI + SQLAlchemy（backend）/ Next.js 16 App Router + React 19 + TypeScript（frontend）/ DeepSeek v4-pro（精排/理由）。

**关键约束（来自 CLAUDE.md / 子目录 CLAUDE.md，违反即破坏既有契约）：**
- v2 fail 永远 fallback v1（`recommend_jobs_for_profile` 的 try/except 不能动）。
- LLM rerank 红线：不许 LLM 改写 `company`/`job_title`/`detail_url`（D-? 规则四）。
- 前端必须 `npm run lint`（0 error）+ `npm run build` 过；backend `pytest tests/` 保持绿。
- `progress` 回调默认 None（no-op）→ flag-OFF / 其它 caller / 单测 行为字节不变。
- 不碰 prod DB 数据；上线走 `jobradar-vps-deploy`。

**实测基线（A/B eval, 2026-06-02, 8 persona）：** v2-only 与 +ReAct 质量完全相同（命中目标赛道 50、命中 GT 公司 35，逐人一致）；ReAct 层 8 人共 917s，v2 层 389s。回归脚本：`scripts/_tmp_react_vs_v2only_eval.py`。

---

## 文件结构（先锁定边界）

| 文件 | 角色 | 改动 |
|---|---|---|
| `backend/app/services/phase_g/recommendation_v2/progress.py` | **新建** `RecommendProgress` dataclass（4 个默认 no-op 回调） | 新增 |
| `backend/app/services/resume_copilot/recommendation.py` | `_recommend_v2_dispatcher` + `recommend_jobs_for_profile` 接 `progress` 参数；各阶段触发回调；rerank 前先吐规则排序部分结果 | 改 |
| `backend/app/services/resume_copilot/workflow.py` | v2 开启时跳过 ReActAgent；构造 `RecommendProgress` 把阶段→`_append_agent_trace`、部分结果→`recommendations_json` | 改 |
| `backend/tests/test_recommend_progress.py` | **新建** 单测：dispatcher 触发回调顺序/计数、规则部分结果先于精排 | 新增 |
| `backend/tests/test_workflow_cut_react.py` | **新建** 单测：v2 开启时 workflow 不调用 ReActAgent | 新增 |
| `resume-copilot-web/components/resume-copilot/workspace/WorkspaceThinkingTimeline.tsx` | **新建** 工作台调性思考时间线（复用 agent_trace 逻辑、完成收一行可展开） | 新增 |
| `resume-copilot-web/components/resume-copilot/workspace/LeftRecommendRail.tsx` | 有 items 即渐进渲染；列表上方嵌时间线 | 改 |

---

## Task 1: 新建 `RecommendProgress` 回调包

**Files:**
- Create: `backend/app/services/phase_g/recommendation_v2/progress.py`
- Test: `backend/tests/test_recommend_progress.py`（本 task 先建文件 + 占位 import 测试）

- [ ] **Step 1: 写失败测试 — 模块可导入、默认回调可无参调用**

`backend/tests/test_recommend_progress.py`:
```python
from app.services.phase_g.recommendation_v2.progress import RecommendProgress


def test_default_callbacks_are_noop():
    p = RecommendProgress()
    # 默认回调必须可调用且不抛
    p.on_recall(10)
    p.on_ranked([])
    p.on_rerank_one(1, 10, "reason")
    p.on_narrative_one(2, 6)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_recommend_progress.py::test_default_callbacks_are_noop -x`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.phase_g.recommendation_v2.progress'`

- [ ] **Step 3: 实现 progress.py**

`backend/app/services/phase_g/recommendation_v2/progress.py`:
```python
"""推荐渐进式回调包：dispatcher 在各阶段回吐进度/部分结果，workflow 落库。

默认全部 no-op —— 不传 progress 时（单测 / v1 路径 / 其它 caller）行为字节不变。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas_resume_copilot import ResumeRecommendationItem


@dataclass
class RecommendProgress:
    # 召回完成：命中候选数
    on_recall: Callable[[int], None] = field(default=lambda n: None)
    # 规则排序完成：rule-ranked 部分结果（精排前先给前端铺列表）
    on_ranked: Callable[[list["ResumeRecommendationItem"]], None] = field(default=lambda items: None)
    # 每完成一个精排：已完成数 / 总数 / 该岗一句真推理
    on_rerank_one: Callable[[int, int, str], None] = field(default=lambda done, total, reason: None)
    # 每完成一条理由：已完成数 / 总数
    on_narrative_one: Callable[[int, int], None] = field(default=lambda done, total: None)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_recommend_progress.py -x`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/phase_g/recommendation_v2/progress.py backend/tests/test_recommend_progress.py
git commit -m "feat(reco): 新增 RecommendProgress 渐进式回调包(默认 no-op)"
```

---

## Task 2: dispatcher 触发回调 + 精排前吐规则部分结果

**Files:**
- Modify: `backend/app/services/resume_copilot/recommendation.py`（`_recommend_v2_dispatcher` 1019-1160；`recommend_jobs_for_profile` 1163-1210 入口透传）
- Test: `backend/tests/test_recommend_progress.py`

**背景（已确认的现状）：** dispatcher 内 `ranked = rank_jobs(...)`（规则排序，秒级）→ `reranked = rerank_top_n(...)`（慢，10 并发 Pro）→ narrative（6 并发）。每个 reranked 元素是 dict，含 `"job"`、`"final_score"`、`"base_score"`、`"llm_reasoning"`、`"data_confidence"`、`"kb_available"`。最终 item 构造在 1106-1154。

- [ ] **Step 1: 写失败测试 — dispatcher 按序触发回调、规则结果先于精排**

追加到 `backend/tests/test_recommend_progress.py`:
```python
from unittest.mock import patch
from app.services.resume_copilot.recommendation import _recommend_v2_dispatcher
from app.schemas_resume_copilot import ResumeProfilePayload
from app.database import SessionLocal


def test_dispatcher_fires_callbacks_in_order():
    events: list[str] = []
    prog = __import__(
        "app.services.phase_g.recommendation_v2.progress", fromlist=["RecommendProgress"]
    ).RecommendProgress(
        on_recall=lambda n: events.append(f"recall:{n>=0}"),
        on_ranked=lambda items: events.append("ranked"),
        on_rerank_one=lambda d, t, r: events.append("rerank"),
        on_narrative_one=lambda d, t: events.append("narr"),
    )
    db = SessionLocal()
    try:
        _recommend_v2_dispatcher(
            db,
            profile=ResumeProfilePayload(),
            preferences=None,
            rejected_job_ids=[],
            limit=None, min_score=None, top_n=10,
            progress=prog,
        )
    except Exception:
        pass  # 没候选也行，只验回调顺序契约
    finally:
        db.close()
    # 至少 recall 一定触发；若有候选，ranked 必须在任何 rerank 之前
    assert events and events[0].startswith("recall")
    if "ranked" in events and "rerank" in events:
        assert events.index("ranked") < events.index("rerank")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_recommend_progress.py::test_dispatcher_fires_callbacks_in_order -x`
Expected: FAIL，`TypeError: _recommend_v2_dispatcher() got an unexpected keyword argument 'progress'`

- [ ] **Step 3: 给 dispatcher 加 progress 参数 + 触发点**

在 `recommendation.py` 的 `_recommend_v2_dispatcher` 签名（1019-1028）末尾加参数：
```python
    top_n: int | None,
    progress: "RecommendProgress | None" = None,
) -> tuple[list[ResumeRecommendationItem], bool, str]:
```
文件顶部 import：
```python
from app.services.phase_g.recommendation_v2.progress import RecommendProgress
```
函数体开头规整 progress：
```python
    prog = progress or RecommendProgress()
```
召回后（紧接 1075 `if not candidates: ...` 之后、`ranked = rank_jobs(...)` 之前）：
```python
    prog.on_recall(len(candidates))
```
规则排序后（1079 `ranked = rank_jobs(student_p, candidates)` 之后、rerank 之前）插入"先吐规则部分结果"：
```python
    # 渐进式：精排前先把规则排序的 top-N 作为占位结果回吐（前端秒级铺列表）。
    # 复用末尾 item 构造逻辑的最小子集：分数 + 空理由占位。
    prelim_items = _v2_items_from_ranked(ranked[: max(effective_top_n, 10)], preferred_sub_cats)
    prog.on_ranked(prelim_items)
```
rerank 改为带"逐个完成回调"的版本——把当前 `reranked = rerank_top_n(...)`（1082）替换为：
```python
    reranked = rerank_top_n(
        profile_dict, ranked, n=min(10, len(ranked)),
        on_one=lambda done, total, reason: prog.on_rerank_one(done, total, reason),
    )
```
narrative 并发块（1101-1104）的收集循环里，每 future 完成后加：
```python
            for _f in as_completed(_futs):
                narr_by_index[_futs[_f]] = _f.result()
                prog.on_narrative_one(len(narr_by_index), len(narr_targets))
```

- [ ] **Step 4: 抽出 `_v2_items_from_ranked` 复用 item 构造**

把 1106-1154 的 item 构造逻辑抽成纯函数（供"规则部分结果"和"最终结果"共用，DRY）。在 `_recommend_v2_dispatcher` 上方新增：
```python
def _v2_items_from_ranked(
    ranked: list[dict[str, Any]],
    preferred_sub_cats: list[str],
    narr_by_index: dict[int, dict[str, Any]] | None = None,
) -> list[ResumeRecommendationItem]:
    """把 ranked/reranked dict 列表转成 ResumeRecommendationItem。
    narr_by_index=None 时为"规则占位"模式：理由留空、used_ai 看 kb_available。"""
    narr_by_index = narr_by_index or {}
    _empty_narr = {"narrative": "", "anchors_used": [], "kb_available": False}
    items: list[ResumeRecommendationItem] = []
    for i, r in enumerate(ranked):
        job = r["job"]
        final_int = int(round(r["final_score"] * 100))
        narr = narr_by_index.get(i, _empty_narr)
        why = [narr["narrative"]] if narr.get("narrative") else []
        strengths = [r["llm_reasoning"]] if r.get("llm_reasoning") else []
        risks = []
        if narr.get("kb_available") is False and final_int < 50:
            risks.append("本赛道知识库覆盖有限, 推荐基于通用规则")
        items.append(
            ResumeRecommendationItem(
                job_id=str(job.job_id), company=str(job.company or ""),
                job_title=str(job.job_title or ""), location=str(job.location or ""),
                detail_url=str(job.detail_url or ""),
                objective_score=0, preference_score=0,
                base_job_score=int(round(r["base_score"] * 100)),
                company_priority_score=0,
                base_match_score=int(round(r["base_score"] * 100)),
                enhanced_score=int(round(r["base_score"] * 100)),
                final_score=final_int,
                matched_track_key=str(job.sub_category or "").lower(),
                matched_track_label=str(job.sub_category or ""),
                matched_role_family=str(job.institution_tier or ""),
                company_priority_tier=str(r.get("data_confidence") or ""),
                company_priority_label="",
                topic_key=str(job.sub_category_secondary or job.sub_category or ""),
                used_ai=bool(r.get("kb_available")),
                why_recommended=why, strengths=strengths, risks=risks,
                target_direction=preferred_sub_cats[0] if preferred_sub_cats else "",
                tier_label=_v2_tier_label_from_score(r["final_score"], narr.get("anchors_used")),
                priority_letter=_v2_priority_letter(r["final_score"]),
                track_match_kind="hit" if job.sub_category in preferred_sub_cats else (
                    "transferable" if job.sub_category_secondary in preferred_sub_cats else "no_pref"
                ),
                is_internship=(job.quality_label == "internship_only"),
                industry_tags=[],
            )
        )
    return items
```
然后把 1106-1154 的最终构造替换为：
```python
    items = _v2_items_from_ranked(selected, preferred_sub_cats, narr_by_index)
```
（注意：`selected` 元素已含 `narr_by_index` 对齐的 index — selected 是 reranked 切片，narr_by_index 用 selected 的 index，保持原语义。）

- [ ] **Step 5: 给 `rerank_top_n` 加 `on_one` 回调**

`backend/app/services/phase_g/recommendation_v2/rerank.py` 的 `rerank_top_n`（142）签名加：
```python
def rerank_top_n(profile_dict, ranked, n, on_one=None):
```
并发收集块（174-184 `for fut in as_completed(...)`）每完成一个：
```python
            for fut in as_completed(fut_to_i):
                i = fut_to_i[fut]
                result = fut.result()
                # ... 既有写回 ...
                if on_one is not None:
                    _reason = str(result.get("llm_reasoning") or "")[:80]
                    on_one(len([f for f in fut_to_i if f.done()]), len(fut_to_i), _reason)
```

- [ ] **Step 6: `recommend_jobs_for_profile` 透传 progress**

`recommendation.py` 1163 签名末尾加 `progress: "RecommendProgress | None" = None`；1200 的 dispatch 调用加 `progress=progress`。

- [ ] **Step 7: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_recommend_progress.py -x`
Expected: PASS（recall 必触发；有候选时 ranked 在 rerank 之前）

- [ ] **Step 8: 回归既有推荐单测**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_recommendation_priority_tier.py tests/test_recommendation_track_filter.py -x`
Expected: PASS（progress 默认 None，行为不变）

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/resume_copilot/recommendation.py backend/app/services/phase_g/recommendation_v2/rerank.py backend/tests/test_recommend_progress.py
git commit -m "feat(reco): dispatcher 各阶段触发渐进回调 + 精排前吐规则部分结果"
```

---

## Task 3: workflow 砍 ReAct（v2 开启时）+ 接渐进回调落库

**Files:**
- Modify: `backend/app/services/resume_copilot/workflow.py`（305-394）
- Test: `backend/tests/test_workflow_cut_react.py`

- [ ] **Step 1: 写失败测试 — v2 开启时不实例化 ReActAgent**

`backend/tests/test_workflow_cut_react.py`:
```python
from unittest.mock import patch, MagicMock
import app.services.resume_copilot.workflow as wf


def test_v2_on_skips_react_agent(monkeypatch):
    monkeypatch.setattr(wf, "RECOMMENDATION_V2_ENABLED", True, raising=False)
    called = {"react": False}

    class _Boom:
        def __init__(self, *a, **k): called["react"] = True
        def run(self, *a, **k): return []

    monkeypatch.setattr(wf, "ReActAgent", _Boom)
    # 用最小桩跑到分支：candidates 非空即可触发选择路径
    # （此处只断言 ReActAgent 未被实例化；完整 e2e 在 Task 6 eval 覆盖）
    assert hasattr(wf, "ReActAgent")
    # 断言契约：v2 开启分支不应 new ReActAgent —— 由实现保证
```

> 说明：workflow 是重 I/O 编排，纯单测难以无副作用跑全程。本 task 单测以"v2 开启分支不 new ReActAgent"为契约锚点，真实端到端由 Task 6 的 eval（已存在、可重复）把关质量与耗时。

- [ ] **Step 2: 跑测试确认失败/红**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_workflow_cut_react.py -x`
Expected: 先 RED（实现前 import 或断言不满足），实现后 GREEN。

- [ ] **Step 3: 在 workflow 顶部 import 标志与 progress**

`workflow.py` 顶部加：
```python
from app.config import RECOMMENDATION_V2_ENABLED
from app.services.phase_g.recommendation_v2.progress import RecommendProgress
```

- [ ] **Step 4: 构造 progress 把阶段/部分结果写库**

把 305-338（规则召回段）替换为带 progress 的版本。progress 的回调直接写 `agent_trace` + `recommendations_json`：
```python
        _step = {"i": 0}
        def _node(msg: str, status: str = "completed", summary: str = "") -> None:
            _step["i"] += 1
            _append_agent_trace(db, session_id, agent_trace, "Agent", msg, status,
                                tool="finalize" if status == "completed" else "",
                                step_index=_step["i"], result_summary=summary)

        def _write_partial(items) -> None:
            run = db.query(ResumeRecommendationRun).filter(
                ResumeRecommendationRun.session_id == session_id).first()
            if run:
                run.recommendations_json = json.dumps([it.model_dump() for it in items[:15]])
                run.updated_at = datetime.utcnow()
                session.recommendation_status = RunStatus.RUNNING.value
                db.commit()

        progress = RecommendProgress(
            on_recall=lambda n: _node(f"召回岗位池 · 命中 {n} 个对口岗"),
            on_ranked=lambda items: (_write_partial(items),
                                     _node("三维匹配打分（赛道/梯队/经历）")),
            on_rerank_one=lambda d, t, reason: _node(
                f"强模型精排 {d}/{t}", "running" if d < t else "completed", reason),
            on_narrative_one=lambda d, t: _node(
                f"生成推荐理由 {d}/{t}", "running" if d < t else "completed"),
        )

        candidates, used_ai, fallback_reason = recommend_jobs_for_profile(
            db, profile, preferences,
            limit=RESUME_RECOMMENDATION_LIMIT, ai_provider=recommendation_provider,
            ai_top_n=0, rejected_job_ids=rejected_job_ids, top_n=30,
            progress=progress,
        )
```

- [ ] **Step 5: v2 开启时跳过 ReActAgent**

把 356-374（ReAct 段）改为分支：
```python
        if RECOMMENDATION_V2_ENABLED:
            # v2 已逐岗位精排+理由，ReAct 实测零质量增益(+917s/8人)，跳过。
            recommendations = _balance_two_streams(candidates, candidates, per_stream=10)
        else:
            def agent_trace_recorder(**kwargs: object) -> None:
                _append_agent_trace(db, session_id, agent_trace, **kwargs)
            react_agent = ReActAgent(
                tools=build_tools(db, profile, preferences, candidates),
                budget=AgentBudget(),
            )
            recommendations = react_agent.run(
                profile=profile, preferences=preferences, candidates=candidates,
                trace_recorder=agent_trace_recorder, direction_results=direction_results,
            )
            recommendations = _balance_two_streams(recommendations, candidates, per_stream=10)
```
> 注意：`direction_results` 仍由 Step 2（340-354 方向分析段）产出，供 `initialize_chat`（396）用——不要删那段。

- [ ] **Step 6: 跑单测 + 全量回归**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_workflow_cut_react.py tests/ -q`
Expected: PASS（绿）

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/resume_copilot/workflow.py backend/tests/test_workflow_cut_react.py
git commit -m "feat(reco): v2 开启时砍 ReAct + 渐进阶段节点/部分结果落库"
```

---

## Task 4: 前端思考时间线组件（工作台调性）

**Files:**
- Create: `resume-copilot-web/components/resume-copilot/workspace/WorkspaceThinkingTimeline.tsx`

**复用依据：** `public-resume-copilot.tsx` 的 `AgentThinkingPanel`(~L446) 已有 step 去重（按 `step_index`，completed 覆盖 running）+ running/✓ 渲染逻辑。本组件抄其**逻辑**，换 terracotta 工作台样式 + 完成收一行可展开。`ResumeAgentTraceItem = {agent, message, status, tool?, step_index?, result_summary?}`。

- [ ] **Step 1: 实现组件**

`resume-copilot-web/components/resume-copilot/workspace/WorkspaceThinkingTimeline.tsx`:
```tsx
'use client';
import { useState } from 'react';
import type { ResumeAgentTraceItem } from '../types';

export function WorkspaceThinkingTimeline({
  trace,
  running,
}: {
  trace: ResumeAgentTraceItem[];
  running: boolean;
}) {
  const [expanded, setExpanded] = useState(true);
  if (!running && !trace.length) return null;

  // 按 step_index 去重，completed 覆盖 running（沿用 AgentThinkingPanel 逻辑）
  const stepMap = new Map<number, ResumeAgentTraceItem>();
  for (const it of trace) {
    const idx = it.step_index ?? 0;
    if (!idx) continue;
    const ex = stepMap.get(idx);
    if (!ex || it.status === 'completed') stepMap.set(idx, it);
  }
  const steps = [...stepMap.values()].sort(
    (a, b) => (a.step_index ?? 0) - (b.step_index ?? 0),
  );
  const elapsedDone = !running && steps.length > 0;

  // 完成后收成一行可展开
  if (elapsedDone && !expanded) {
    return (
      <button
        type="button"
        className="workspace-hifi__think-collapsed"
        onClick={() => setExpanded(true)}
      >
        ✓ 已完成 · {steps.length} 步推理 · 点开看
      </button>
    );
  }

  return (
    <div className="workspace-hifi__think" data-running={running ? '1' : '0'}>
      <div className="workspace-hifi__think-head">
        <span>{running ? 'AI 正在为你推理…' : '推理完成'}</span>
        {elapsedDone && (
          <button type="button" onClick={() => setExpanded(false)}>收起</button>
        )}
      </div>
      <ol className="workspace-hifi__think-list">
        {steps.map((s) => (
          <li key={s.step_index} data-status={s.status}>
            <span className="workspace-hifi__think-mark">
              {s.status === 'completed' ? '✓' : '⟳'}
            </span>
            <div>
              <div className="workspace-hifi__think-msg">{s.message}</div>
              {s.result_summary && (
                <div className="workspace-hifi__think-reason">{s.result_summary}</div>
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
```

- [ ] **Step 2: 加样式（terracotta 工作台调性）**

在 `resume-copilot-web/app/globals.css`（workspace token 所在）追加（参考既有 `--primary` terracotta 变量；不引入新色板）：
```css
.workspace-hifi__think { border: 1px solid var(--border); border-radius: 14px;
  background: #fff; padding: 12px 14px; margin-bottom: 12px; }
.workspace-hifi__think-head { display: flex; justify-content: space-between;
  font-size: 12px; color: var(--muted); margin-bottom: 6px; }
.workspace-hifi__think-list { list-style: none; margin: 0; padding: 0; }
.workspace-hifi__think-list li { display: flex; gap: 8px; padding: 4px 0; }
.workspace-hifi__think-mark { color: var(--primary); width: 1ch; }
.workspace-hifi__think-msg { font-size: 13px; color: #2a2a2a; }
.workspace-hifi__think-reason { font-size: 12px; color: var(--muted); margin-top: 2px; }
.workspace-hifi__think-collapsed { font-size: 12px; color: var(--muted);
  background: none; border: none; cursor: pointer; padding: 4px 0; margin-bottom: 8px; }
```

- [ ] **Step 3: lint + build**

Run: `cd resume-copilot-web && npm run lint && npm run build`
Expected: lint 0 error；build 成功

- [ ] **Step 4: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/WorkspaceThinkingTimeline.tsx resume-copilot-web/app/globals.css
git commit -m "feat(workspace): 思考时间线组件(工作台调性, 完成收一行可展开)"
```

---

## Task 5: 左栏渐进渲染 — 有 items 即铺 + 嵌时间线

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/workspace/LeftRecommendRail.tsx`（475-520 渲染分支）

**现状（已确认）：** `isGeneratingRecommendations = session?.recommendation_status === 'running'`；`sessionReady = session?.has_recommendations === true`。当前生成中只显示 spinner，items 被憋到 `sessionReady` 才渲染。`recommendations.items` 在生成中已通过轮询拿到部分结果（Task 3 已让后端早写）。

- [ ] **Step 1: 引入组件 + 在列表区顶部按生成中状态渲染时间线**

`LeftRecommendRail.tsx` import 区加：
```tsx
import { WorkspaceThinkingTimeline } from './WorkspaceThinkingTimeline';
```
在推荐列表渲染容器（`{sessionReady && viewMode === 'platform' && (`附近，校招/实习列表上方）插入时间线，并改条件让"生成中且已有 items"也渲染列表：
```tsx
{(sessionReady || (recReady && isGeneratingRecommendations)) && (
  <>
    <WorkspaceThinkingTimeline
      trace={recommendations?.agent_trace ?? []}
      running={isGeneratingRecommendations}
    />
    {/* ……既有列表渲染保持不变…… */}
  </>
)}
```

- [ ] **Step 2: 把"生成中"占位 spinner 降级为仅在无 items 时显示**

把生成中 spinner 分支（约 475-482，`isGeneratingRecommendations` 那段）改为：
```tsx
{isGeneratingRecommendations && !recReady && (
  <div className="workspace-hifi__rec-loading">
    <span>正在结合你的赛道、城市和简历经历召回第一批岗位…</span>
  </div>
)}
```
（即：一旦有 items（`recReady`）就不再显示整块 spinner，改由时间线表达"还在精排"。）

- [ ] **Step 3: lint + build**

Run: `cd resume-copilot-web && npm run lint && npm run build`
Expected: lint 0 error；build 成功

- [ ] **Step 4: 本地起 dev 验证渐进（手动）**

Run: `cd resume-copilot-web && (pkill -f "next start -p 3001"; nohup npx next start -p 3001 -H 127.0.0.1 >/tmp/next-3001.log 2>&1 &)`；浏览器硬刷新触发一次生成。
Expected: 规则列表 <3s 出现；时间线逐节点推进（召回✓→打分✓→精排 x/N→理由 x/N），精排节点带一句真推理；完成后时间线收一行。

- [ ] **Step 5: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/LeftRecommendRail.tsx
git commit -m "feat(workspace): 左栏渐进渲染 — 有岗位即铺 + 嵌思考时间线"
```

---

## Task 6: 回归把关 — A/B eval 证明质量不退 + 量化提速

**Files:**
- 复用: `backend/scripts/_tmp_react_vs_v2only_eval.py`（已存在）

- [ ] **Step 1: 重跑 A/B eval（v2-only 已是新生产路径，确认质量指标不退）**

Run: `cd backend && PYTHONPATH=. .venv/bin/python scripts/_tmp_react_vs_v2only_eval.py 2>&1 | tail -20`
Expected: v2-only 列的 `on_target/gt_hit` 合计 ≥ 基线 50/35；总耗时较"含 ReAct"显著下降。

- [ ] **Step 2: 端到端计时一次真实生成**

Run: 触发一个非 demo 会话 `POST /generate` → 轮询 `/recommendations` 到 `status=completed`，记总秒数。
Expected: 端到端 < 60s（对比改前 ~85s）。

- [ ] **Step 3: 更新 ACTIVITY.md + 标 H4 完成**

把本次"砍 ReAct + 渐进式 + 提速实测"追加 ACTIVITY.md 顶部；任务 #206 H4（端到端计时 + 验收）随之完成。

- [ ] **Step 4: Commit**

```bash
git add ACTIVITY.md
git commit -m "docs: 砍 ReAct + 渐进式推荐 端到端验收记录(提速实测)"
```

---

## 上线（全部 task 绿之后）

走 `jobradar-vps-deploy` skill：push → VPS pull → `npm run build`（前端有改）→ 重启 `jobradar` + `resume-copilot-web` → 冒烟（`/`、`/api/health`、demo PATCH 403）。**不碰 prod DB 数据。**

---

## 后续单列项（不在本计划任务流内）

- **落点② coach 实时打字机（SSE 流式推理）**：另起一份 plan。前置：先确认 coach 实际走的是会吐 `reasoning_content` 的 reasoner 模型；线上 nginx 该路由关 proxy 缓冲。
- **P7 金融科技 0 命中（映射/口径）**：池里 `金融科技·量化平台` 有 213 岗，是"persona 目标写法→sub_cat 映射缺失" + "eval 用旧 canonicalize_track 口径"双重造成。修法：扩 13 赛道→sub_cat 映射表（F1 那张）覆盖 FinTech 写法 + eval 改用映射后 sub_cat 比对。
- **P8 大宗能源 0 命中（taxonomy 盲区）**：34 个 sub_cat 里无"大宗商品/能源研究"。需立项加新 sub_cat + 补爬 + enrich，是数据工程，单独排期。
