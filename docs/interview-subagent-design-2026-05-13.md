# 设计文档:模拟面试 Subagent 化重构

**Date**: 2026-05-13
**Author**: Claude Code (claude-opus-4-7) + Slackness1
**Status**: 设计中,待 review 后实施
**估时**: 后端 ~600 行 + 50 行测试,2-3 天工程

---

## 1. 背景与动机

当前 `app/services/interview/llm.py::stream_interview_turn` 是一个**巨型单 LLM call**,
它的 system prompt 同时承担:

1. 理解 target_job 的 JD
2. 评估上一轮回答的 STAR 完整度 + 量化质量
3. 决定本轮是「追问上轮」还是「推进 rubric」
4. 按 Jerry rubric 维度选下一个问题
5. 生成自然语气的面试官话术

**问题**:
- **Prompt 膨胀**:JD-aware rubric(commit `83271ca`)进来之后,system prompt 已经 ~2500 token。
   每加一个 capability 都直接撑大主 prompt → 首字延迟变长 + 模型不容易"专注"
- **缺乏 KB 召回**:刚 Phase 1 落地的 `student_experiences` 表(commit 待提)只在沉淀端,
   面试端**没有任何主动召回**。理想场景"AI 帮学生想起合适经历"是这次重构的最大动力
- **不可观测**:rubric 打分逻辑混在 dialogue 生成里,**输出没有可结构化的中间产物**。
   报告生成时(`report.py`)只能再让 LLM 把 transcript 全过一遍——重复推理 + 风格漂移
- **难单元测试**:目前 interview 模块几乎没有 unit test,因为单 LLM 一把梭很难 mock 分支

## 2. 目标 / 非目标

### 目标

- **G1**:把 turn handler 拆成 3 个 subagent + 1 个 orchestrator,每个 subagent **prompt < 800 token**
- **G2**:**自动从 student_experiences 召回**当前问题相关的经历,作为 hint 注入主 prompt,
   让面试官的下一题能"引导学生讲出某条 KB 经历"
- **G3**:**结构化打分**——每轮 turn 产生持久化的 dimension score JSON,供报告生成端**直接复用**(不用再 LLM 二次推理 transcript)
- **G4**:**Feature flag + A/B**——`INTERVIEW_SUBAGENT_ENABLED` 默认 OFF;打开后**与现有 path 并存**,可 A/B 评估同一 user 两种实现的报告差异
- **G5**:不破坏现有 SSE 协议——前端代码零修改

### 非目标(本次不做)

- 不引入 mem0 / Letta 等第三方 agent framework
- 不动 ASR/TTS/avatar 任何一层
- 不动 `InterviewReport` 表 schema(只在 `score_json` 字段塞结构化得分)
- 不做面试中的"missed opportunity"提示——这是 Phase 3 的事(post-interview report 阶段)
- 不引入分布式 task queue(用 FastAPI BackgroundTasks 或同步 `asyncio.gather` 即可)

## 3. 架构总览

```
┌────────────────────────────────────────────────────────────────┐
│  POST /api/interview/turn   (SSE)                               │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Interviewer (orchestrator,非 LLM agent)                │   │
│  │  ─────────────────────────────────────────              │   │
│  │  接收: { target_job, messages[], user_key }              │   │
│  │                                                          │   │
│  │  ┌──────────────────────────────────────────────┐       │   │
│  │  │  Phase A: fan-out (asyncio.gather, parallel)  │       │   │
│  │  ├──────────────────────────────────────────────┤       │   │
│  │  │  ▢ AnswerScorer       (score 上轮回答)        │       │   │
│  │  │  ▢ ExperienceRecaller (从 KB 拉 top-3 经历)   │       │   │
│  │  │  ▢ FollowUpDecider    (决定 follow_up 或 next)│       │   │
│  │  └──────────────────────────────────────────────┘       │   │
│  │                                                          │   │
│  │  Phase B: 拼装 final prompt(瘦身后的主 prompt)         │   │
│  │  Phase C: 流式调用 main LLM → SSE 推回客户端              │   │
│  │  Phase D: 写 InterviewTurn 行(score_json + recall_used) │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

**关键点**:三个 subagent 都是**无副作用** subagent(read-only DB / 纯推理),完全符合
Claude Code 的"研究 task 并行,write 串行"原则。**写动作只发生在 Phase D**,在主进程串行写。

---

## 4. Subagent 接口规范

所有 subagent 共用一个返回信封——直接抄 Claude Code 的 `<task-notification>`:

```python
@dataclass
class SubagentResult:
    status: Literal["completed", "failed", "timeout"]
    subagent_type: str
    summary: dict                  # 结构化 — schema 因 type 而异
    duration_ms: int
    error_message: str = ""
    fallback_used: bool = False    # 是否用了 fallback 路径
```

### 4.1 `ExperienceRecaller`

**职责**:从 student_experiences 表里召回**与当前问题维度相关**的 top-N 经历,
返回给 Interviewer 作为 hint。

**输入**:
```python
@dataclass
class RecallerInput:
    user_key: str                       # 必填,非 __demo__/__guest__
    target_job: str
    current_topic_dimensions: list[str] # 主 agent 判断的下一题维度
    transcript_so_far: list[dict]       # 用于去重——已讲过的别再 surface
    max_results: int = 3
```

**算法**:
1. SQL 查 `StudentExperience` where `user_key=? AND category='experience' AND is_archived=False`
2. Python 端按 `star_dimensions JSON contains any of current_topic_dimensions` 过滤
3. 排序:`confidence × recency_decay × (use_count == 0 ? 1.5 : 1.0)`(没用过的优先)
4. **可选**小 LLM rerank(Flash,200 tokens):给 LLM 看 top-10 candidate 的 summary + behavioral_hook,选 top-3 最切题的

**输出 `summary`**:
```python
{
  "experiences": [
    {
      "id": 42,
      "summary": "三个月将次留率从 12% 提升至 16%",
      "behavioral_hook": "S=...|T=...|A=...|R=...",   # Interviewer 直接复用
      "dimensions": ["analytical_thinking", "ownership"],
      "age_days": 5,
      "confidence": 0.95,
      "raw_excerpt_snippet": "三个月里把次留率从 12% 提到 16%"
    }
  ],
  "kb_size": 12,
  "no_match_reason": null   # 或 "kb_empty" | "no_dimension_match" | "all_used"
}
```

**降级**:`user_key` 为 demo/guest/空 → 立即返回 `experiences: []`,不查库,
`no_match_reason: "unauthorized_or_demo"`。

**Token 预算**:
- 无 LLM rerank 版:0 token(纯 SQL)
- 含 LLM rerank 版:input ~600 / output ~150,Flash 单价约 $0.00006

### 4.2 `AnswerScorer`

**职责**:对学生**上一轮回答**做结构化 rubric 打分。

**输入**:
```python
@dataclass
class ScorerInput:
    question: str
    answer: str
    target_job: str
    rubric_focus: list[str]   # 本轮该问题预期考察的维度(由主 agent 给)
    jd_context_brief: str     # JD 关键诉求 (≤200 字摘要,主 agent 缓存)
```

**LLM 调用**:Flash,JSON mode,prompt ~400 token。

**输出 `summary`**:
```python
{
  "dimension_scores": {
    "analytical_thinking": 3,   # 1-5
    "communication": 4
  },
  "star_completeness": {
    "S": true,
    "T": true,
    "A": false,
    "R": false
  },
  "missing_signals": ["量化结果", "你具体做了什么"],
  "strong_signals": ["开场情境清晰"],
  "overall_pass": false        # 是否达到合格线(STAR 至少 3 项 OK)
}
```

**降级**:无回答(第一轮)→ 直接返回所有维度 `null`,不发 LLM call。

### 4.3 `FollowUpDecider`

**职责**:看 ScorerInput 的结果 + transcript 进度,**决定本轮策略**:
- `follow_up`:追问上轮(STAR 缺 A/R 时常见)
- `next_topic`:推进 rubric 下一维度
- `end_session`:transcript 已覆盖足够多维度 + 时长接近 25 分钟,该收尾了

**输入**:
```python
@dataclass
class DeciderInput:
    scorer_summary: dict           # AnswerScorer 输出
    rubric_progress: dict[str,int] # 每个 dimension 累计被 cover 几次
    turn_count: int
    elapsed_minutes: float
    target_total_minutes: int = 25
```

**LLM 调用**:Flash,~200 token prompt,JSON mode。

**输出 `summary`**:
```python
{
  "decision": "follow_up",       # 或 "next_topic" | "end_session"
  "follow_up_probe": "你刚提到 mentor 评价不错,具体反馈了哪些点?",
  "next_topic_dimension": null,  # 仅 decision == "next_topic" 时填
  "rationale": "答案缺 A 和 R,建议追问 1 次"
}
```

**降级**:第一轮(无上轮回答)→ 跳过此 subagent,主 agent 默认选开场维度(`leadership` 或
JD-第一关键词)。

### 4.4 Subagent 基类与执行器

放在 `app/services/interview/subagents/base.py`:

```python
import asyncio, time, json, logging
from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import Generic, TypeVar

InT = TypeVar("InT")
OutT = TypeVar("OutT", bound=dict)

class Subagent(ABC, Generic[InT, OutT]):
    subagent_type: str = "<set in subclass>"
    timeout_seconds: int = 8

    @abstractmethod
    async def _run(self, payload: InT) -> OutT: ...

    async def invoke(self, payload: InT) -> SubagentResult:
        t0 = time.time()
        try:
            summary = await asyncio.wait_for(
                self._run(payload), timeout=self.timeout_seconds,
            )
            return SubagentResult(
                status="completed", subagent_type=self.subagent_type,
                summary=summary, duration_ms=int((time.time() - t0) * 1000),
            )
        except asyncio.TimeoutError:
            return SubagentResult(
                status="timeout", subagent_type=self.subagent_type,
                summary={}, duration_ms=self.timeout_seconds * 1000,
                error_message="timeout",
            )
        except Exception as exc:
            logging.getLogger(__name__).exception(
                "subagent %s failed", self.subagent_type
            )
            return SubagentResult(
                status="failed", subagent_type=self.subagent_type,
                summary={}, duration_ms=int((time.time() - t0) * 1000),
                error_message=str(exc)[:300],
            )
```

**所有失败都被 Subagent 基类吞掉**——上游不会因为某个 subagent 死掉而崩溃,
Interviewer 拿到 `status != "completed"` 时**走 fallback 路径**(等价于旧的单 LLM call)。

## 5. Interviewer 编排逻辑

`app/services/interview/orchestrator.py`(新文件)。

### 5.1 Turn 生命周期

```python
async def stream_interview_turn_v2(
    target_job: str,
    messages: list[dict],
    user_key: str,
    session_id: str,
) -> AsyncIterator[str]:
    # ── Phase 0: 提取上下文 ──────────────────────────────────────
    last_user_answer = _last_user_msg(messages)
    last_question = _last_assistant_msg(messages)
    is_first_turn = last_user_answer is None
    rubric_progress = _compute_rubric_progress(messages)
    elapsed_minutes = _elapsed_minutes(session_id)

    # ── Phase A: 主 agent 预测下一题维度(轻量决策,主进程内做)──
    next_topic_dimensions = _pick_next_dimensions(
        target_job, rubric_progress, is_first_turn,
    )

    # ── Phase B: fan-out subagents(并行)─────────────────────────
    tasks = [
        ExperienceRecaller().invoke(RecallerInput(
            user_key=user_key,
            target_job=target_job,
            current_topic_dimensions=next_topic_dimensions,
            transcript_so_far=messages,
        )),
    ]
    if not is_first_turn:
        tasks.append(AnswerScorer().invoke(ScorerInput(
            question=last_question, answer=last_user_answer,
            target_job=target_job, rubric_focus=next_topic_dimensions,
            jd_context_brief=_jd_brief_cache(target_job),
        )))
        # FollowUpDecider 依赖 Scorer 结果,所以稍后串行
    recaller_result, *maybe_scorer = await asyncio.gather(*tasks)
    scorer_result = maybe_scorer[0] if maybe_scorer else None

    decider_result = None
    if scorer_result and scorer_result.status == "completed":
        decider_result = await FollowUpDecider().invoke(DeciderInput(
            scorer_summary=scorer_result.summary,
            rubric_progress=rubric_progress,
            turn_count=len(messages) // 2,
            elapsed_minutes=elapsed_minutes,
        ))

    # ── Phase C: 构建主 LLM prompt(瘦身后)+ 流式输出 ───────────
    main_prompt = _build_main_prompt(
        target_job=target_job, messages=messages,
        recall=recaller_result, score=scorer_result, decision=decider_result,
        next_topic=next_topic_dimensions,
    )
    full_response = ""
    async for chunk in _stream_main_llm(main_prompt):
        full_response += chunk
        yield chunk

    # ── Phase D: 持久化(主进程串行)────────────────────────────
    _persist_turn(
        session_id=session_id, user_key=user_key,
        question=full_response, user_answer=last_user_answer or "",
        score_json=scorer_result.summary if scorer_result else None,
        recall_used_ids=[e["id"] for e in (recaller_result.summary.get("experiences") or [])],
        decider_summary=decider_result.summary if decider_result else None,
    )
```

### 5.2 主 LLM Prompt 瘦身后样板

```
你是一个面试官。Target job: {target_job}。
当前 rubric 进度: {rubric_progress_compact}。

[私有 hint - 不要直接念出来]
本轮维度: {next_topic_dimensions}
学生 KB 召回(可在问题里引导他讲这些经历):
{recall.experiences | top-2, summary + behavioral_hook only}
上轮回答评分: STAR={star_completeness}, 缺={missing_signals}
策略: {decider.decision} ({decider.rationale})

[输出]
- 如果策略 == follow_up,问 {decider.follow_up_probe} 的同主题但更具体
- 如果策略 == next_topic,以自然语气开启 {next_topic_dimensions[0]}
- 如果策略 == end_session,做一段 ≤150 字的总结 + 谢谢
- 风格:大方,会用 "嗯/我看到/能多讲讲" 这种衔接,但不要油腻
```

**对比旧版**:旧 prompt 2500 token,新主 prompt **≤ 800 token**(rubric 全文 + JD 全文 + 评分逻辑全搬走了)。

## 6. 数据模型变更

### 6.1 既有表 `interview_turns`(无 schema 变更)

`score_json` 列已存在,本次只是开始**真正填充结构化内容**:
```json
{
  "scorer": {... AnswerScorer.summary ...},
  "decider": {... FollowUpDecider.summary ...},
  "recall_used_ids": [42, 87],
  "subagent_telemetry": {
    "recaller": {"duration_ms": 240, "status": "completed"},
    "scorer":   {"duration_ms": 1200, "status": "completed"},
    "decider":  {"duration_ms": 800, "status": "completed"}
  }
}
```

### 6.2 既有表 `student_experiences`(本次只读)

- `last_used_at` + `use_count` 在 Phase D 持久化时同步更新
   (对每个 `recall_used_ids` 中的 id)
- 用于 KB 面板「这条经历被引用过 3 次,最近一次 2 天前」

### 6.3 不动 `interview_reports`

报告生成端(`report.py`)在 Phase 2 时改为**直接读 `interview_turns.score_json`** 而不是重跑
LLM。本次仅写入,**不动读取端**。

## 7. Feature Flag 与并存策略

### 7.1 Flag 设计

`backend/app/config.py`:
```python
INTERVIEW_SUBAGENT_ENABLED = os.environ.get("INTERVIEW_SUBAGENT_ENABLED", "0") in {"1","true","True"}
INTERVIEW_SUBAGENT_TIMEOUT_SECONDS = _get_int_env("INTERVIEW_SUBAGENT_TIMEOUT_SECONDS", 8)
INTERVIEW_SUBAGENT_RECALLER_USE_LLM = os.environ.get("INTERVIEW_SUBAGENT_RECALLER_USE_LLM", "1") in {"1","true","True"}
```

### 7.2 Router 切换

`backend/app/routers/interview.py`,`POST /api/interview/turn`:

```python
if INTERVIEW_SUBAGENT_ENABLED:
    from app.services.interview.orchestrator import stream_interview_turn_v2
    stream = stream_interview_turn_v2(target_job, messages, user_key, session_id)
else:
    from app.services.interview.llm import stream_interview_turn
    stream = stream_interview_turn(target_job, messages)   # old path
```

### 7.3 灰度路径

| 阶段 | 配置 | 验证 |
|---|---|---|
| Stage 0 | flag=0,代码全部合并 | 老 path 行为 0 变化(回归测试) |
| Stage 1 | 本地 flag=1 跑 5 次完整面试 | 看 transcript 质量 + score_json 是否合理 |
| Stage 2 | VPS 上为单个测试 user(user_key 白名单)开启 | A/B 看主观体验差异 |
| Stage 3 | 全量开 flag=1 | 监控 `interview_turns.score_json` 写入率 + subagent timeout 率 |
| Stage 4 | 一周后老 path 删除 | 不再回退 |

### 7.4 回滚

任何阶段发现问题,**关 flag 即回到老 path**(同 process 内,无需 restart;
但保守起见每次切都 restart 一次 jobradar 保 cache 干净)。

## 8. 测试策略

### 8.1 Subagent 单测

**`tests/test_subagent_experience_recaller.py`**:
- 空 KB → `no_match_reason="kb_empty"`
- demo/guest user_key → `unauthorized_or_demo`,**不查 DB**
- 维度匹配 0 个 → `no_match_reason="no_dimension_match"`
- 多条候选 → 排序对(confidence > age > use_count)
- LLM rerank fail → fallback 到无 rerank 路径

**`tests/test_subagent_answer_scorer.py`**:
- mock LLM 返回不同 STAR 完整度 → output 结构正确
- LLM timeout → `status="timeout"`,主流不挂
- 上轮无回答 → 不发 LLM call

**`tests/test_subagent_follow_up_decider.py`**:
- scorer 全合格 + 维度多 → `decision=next_topic`
- scorer 缺 A/R → `decision=follow_up`
- elapsed > 22 min + 维度 cover ≥ 4 → `decision=end_session`

### 8.2 Orchestrator 集成测试

**`tests/test_interview_orchestrator.py`**:
- 第一轮(无 prev answer)→ scorer/decider 都跳过,recaller 仍跑
- KB 召回成功 → 主 prompt 包含 recall hint
- 任一 subagent timeout → 主流仍能 stream 出回答
- Phase D 写 `interview_turns` 行,`score_json` schema 正确

### 8.3 黄金文件 (golden) 测试

固定 transcript + 固定 `user_key` 的 KB 状态,跑一遍 v2 流水线,
snapshot 主 prompt 内容。后续 prompt 调整时**对比 diff**,
意外 regression 立刻可见。

### 8.4 现有 SSE 协议回归

外部前端代码**不能感知**这次重构。验证:
- `POST /api/interview/turn` 返回相同 `text/event-stream` content-type
- 同样的 `data: {...}` 行,同样的 `[DONE]` 收尾
- 错误事件 `{"error": "...", "type": "..."}` 兼容

## 9. 失败模式 / 风险

| 风险 | 应对 |
|---|---|
| **3 个 subagent 并行 → 总 API 调用 ×4**(原本 1 次现在 4 次) | (a) 2 个用 Flash 单价低;(b) 并行 → 总时延不变;(c) 主 LLM 因为 prompt 更短反而 quicker first-token |
| **KB 召回扰乱面试节奏**(强行让学生讲某条经历) | 主 prompt 严格写"hint 不要直接念",且 recall summary 只塞 2 条最相关。学生答非所问时,主 LLM 仍能正常推进 |
| **某个 subagent 长期 fail** | timeout=8s 兜底,fallback 到旧 path 中对应行为(scorer 不跑就 None,decider 不跑就默认 next_topic) |
| **score_json 字段写错 schema** | pydantic `ScoreSnapshot` model 校验后再 dump 入库 |
| **A/B 阶段同一 user 两种实现下 KB use_count 双写** | 老 path 不写 `last_used_at`(因为它不召回);只有 v2 path 写。无冲突 |
| **学生 KB 为空时 recall 返回 0 条** | `no_match_reason=kb_empty` → 主 prompt 显式知道、不浪费 token 加 hint section |
| **LLM Flash 偶尔不返回合法 JSON** | 每个 subagent `safe_json_extract` + schema 校验 → 校验失败=fallback;复用 crawler_llm 已有的 `safe_json_extract` |

## 10. Open Questions

1. **要不要持久化 subagent 的中间 prompt + 完整 LLM response?**
   - 利:debug 神器,可视化 agent 思考过程
   - 弊:DB 膨胀,每天 ~1000 turns × 4 subagent × 数 KB = 4MB / 天
   - **倾向**:打 telemetry flag `INTERVIEW_SUBAGENT_TRACE_ENABLED`,默认 off,出问题时开

2. **Recaller 要不要带 LLM rerank?**
   - 不带:0 LLM cost,但维度匹配粒度只到"是否 contains dimension X"
   - 带:能选 top-3 真正语义切题的,但每 turn +1 LLM call
   - **倾向**:首版 ship 不带,A/B 时 flag-on rerank 对比效果

3. **`AnswerScorer` 的 rubric 来源?**
   - 选项 A:hardcoded 在 prompt 里(目前 Jerry rubric 就是这样)
   - 选项 B:每 target_job 跑一次 JD analysis,缓存 rubric 到 `system_config` 表
   - **倾向**:选 A 先 ship,选 B 是单独的 Phase 3(JD-derived custom rubric)

4. **`FollowUpDecider` 能否合并进 `AnswerScorer`?**
   - 都是 ~200 token prompt,逻辑相关
   - 合并优点:1 个 LLM call 替代 2 个
   - 合并缺点:scorer 失败时连决策都没了,不能独立 fallback
   - **倾向**:**首版分开 ship**(独立 fallback 价值大于省一次调用)。后续可考虑合并

5. **demo session(id=1)在 v2 下怎么表现?**
   - demo 的 `user_key="__demo__"` → Recaller 直接返回空
   - Demo flow 必须保持现有"3 段预录"行为
   - **倾向**:flag-on 时,demo session 强制走 v1 老 path,避免动 demo 数据

## 11. 实施计划(分 4 个 PR)

### PR-1:基础设施 + ExperienceRecaller(~250 行)

- `app/services/interview/subagents/base.py` — Subagent 基类 + SubagentResult
- `app/services/interview/subagents/recaller.py` — 实现
- 单测 + flag-OFF 时零行为变化的回归测试
- **此 PR 不动 router,不开 flag**,纯增量代码

### PR-2:AnswerScorer + FollowUpDecider(~200 行)

- `app/services/interview/subagents/scorer.py`
- `app/services/interview/subagents/decider.py`
- 各自单测
- **仍不动 router**

### PR-3:Orchestrator + flag 切换(~250 行)

- `app/services/interview/orchestrator.py` — `stream_interview_turn_v2`
- `app/routers/interview.py` — flag-branch
- 集成测试 + golden file
- flag default OFF
- **此 PR 之后 ship 到 prod,但 flag 不开**

### PR-4:打开 flag + 监控(~50 行 + 文档)

- 私有 user_key 白名单灰度
- `system-health` panel 加 subagent telemetry 卡片(可选)
- 跑 1 周观测,然后全量开

---

## Appendix A:与 Phase 2/3 student_kb 的关系

| Phase | 状态 | 与本设计的关系 |
|---|---|---|
| Phase 1 | ✅ 已部署(flag OFF) | 沉淀端 — chat → extractor → student_experiences |
| **Phase 2** | **本设计文档** | **召回端 — interview 主动从 KB 拉经历** |
| Phase 3 | TODO | 复盘端 — post-interview "你应该提 X 经历" |

本设计**只引入读路径**,不动 Phase 1 的写路径。Phase 1 + Phase 2 各自可独立 flag。

## Appendix B:与 Claude Code 的设计差异

| Claude Code 原模式 | 本项目调整 | 原因 |
|---|---|---|
| `AgentTool.call(subagent_type, prompt)` | 直接 Python class instantiate + `await invoke()` | 我们不需要"agent 可以自主决定调用 subagent"——orchestrator 永远是固定流程 |
| `<task-notification>` XML 信封 | `SubagentResult` dataclass | 内部传递,无需文本协议 |
| `coordinator/` 系统 prompt 强制并行 | `asyncio.gather` | 不需要协调 agent,固定 fan-out |
| Tool 强制注入(`SendMessageTool` 等) | 每个 subagent 显式声明工具 | subagent 之间不通信,只回 orchestrator |
| 父 agent 继承 rendered bytes | 不继承——每个 subagent 自己 build prompt | 因为我们的 subagent 不是"复制父 LLM 的视角",而是"专项工人" |

**核心理念保留**:并行 research、独立 context、结构化 return、orchestrator 收摘要后再决策。
