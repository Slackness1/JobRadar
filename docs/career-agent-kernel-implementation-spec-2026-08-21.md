# JobRadar Career Agent Kernel 改装实施 Spec

- 状态：Draft，待实施评审
- 日期：2026-08-21
- 产品范围：岗位推荐、Resume Copilot、模拟面试、统一记忆
- 主要读者：FDE / 技术产品经理、后端、前端、AI 工程师
- 前置依赖：Realtime Voice Agent Draft PR #6
- 核心决策：**统一 Runtime 基础设施，不统一业务 Loop**

## 0. 怎么阅读这份 Spec

这不是一份“未来架构愿景”，而是一份可以直接拆 PR、分配开发和验收的实施合同。

不同角色可以重点阅读：

| 角色 | 建议先看 |
|---|---|
| FDE / 技术产品经理 | 1、3、8、9、10、11、16 |
| 后端工程师 | 5、6、7、8、9、14、15、16 |
| AI 工程师 | 6.2、6.3、7.3、7.4、9、10 |
| 前端工程师 | 3.2、8.1、9.7、10.1、11 |
| 测试 / 验收 | 8.7、9.8、10.5、13、15 |

文档里的类名和字段名是逻辑契约。实施时允许调整命名，但不能改变字段语义和验收标准。

## 1. 一句话结论

JobRadar 不应该被重构成一个“小号 Claude Code / Codex / DSH”，也不应该把三个业务模块塞进一个万能 ReAct Loop。

我们要新增的是一个**小而稳定的 Career Agent Kernel**，统一解决：

- Run / Session / Turn / Step / Command / Event 协议；
- 幂等、状态版本、重试、取消和崩溃恢复；
- 上下文编译、来源追踪、敏感信息和 Token 预算；
- Capability 的类型校验、权限、超时和审计；
- 真实事件、用户进度、开发者 Trace 和离线评测；
- 记忆候选项治理和 Career Pack 版本固定。

但三条业务链继续保留不同执行范式：

| 业务链 | 执行范式 | 业务自己负责什么 |
|---|---|---|
| 岗位推荐 | 默认规则召回/排序快路；需要深度研究时才运行受预算约束的 research loop | 候选池、硬条件、排序、推荐证据和岗位决策 |
| Resume Copilot | 用户驱动的有限状态机，一轮只产生一个结构化动作 | Evidence 收集、状态转换、防编造、草稿确认 |
| 模拟面试 | 结构化双工 Turn Loop + 异步分析流水线 | 问题、追问策略、评分、报告语义 |

最终原则：

> Kernel 负责“可靠地运行”；Workflow 负责“做什么求职判断”；Capability 可以替换；身份、隐私、幂等和审计永远属于特权核心。

## 2. 为什么现在要改

JobRadar 已经有三套能工作的领域系统，缺的不是“再做一个 Agent”，而是统一的运行可靠性。

### 2.1 代码中已经确认的缺口

| 缺口 | 当前真实行为 | 用户或业务风险 |
|---|---|---|
| 面试 Turn 幂等 | 从数据库最后一题推算下一个 `turn_index`，没有 `(session_id, turn_index)` 唯一约束 | 重试、重连或并发请求可能推进两次 |
| LiveKit 服务身份 | Voice Worker 调 `/api/interview/turn` 时提交裸 `X-Resume-User-Key` | 服务调用没有和 room、context、session、user 做签名绑定 |
| 面试延迟耦合 | 评分、参考答案和语音指标并行后仍整体等待，再决定下一题 | 非关键分析拖慢实时对话 |
| 推荐 Trace | 部分展示内容来自模型生成的 `reasoning_display` | 展示的“过程”可能和真实工具行为不一致 |
| Agent 预算 | 主要统计成功 Tool Call，没有完整约束模型 Step、失败次数、Token、费用 | 坏循环可能持续消耗时间和费用 |
| Context 拼装 | Provider 主要返回匿名字符串，可选失败通常直接跳过 | 无法统一审计来源、敏感度、新鲜度和截断原因 |
| Memory 提升 | 长期记忆本身较完整，但模型推断和已确认事实之间仍缺一层统一 Staging | 一次推断可能过早影响跨会话个性化 |

### 2.2 必须保留的现有资产

- 岗位候选池由确定性流程产生，最终 `job_id` 受候选池约束；
- Resume Plan Mode 的状态机和 Evidence 防编造规则；
- LiveKit Media Runtime 与 Interview Orchestrator 的边界；
- Voice Facts V2 的 `source / definition / quality / basis` 契约；
- `account_memory` 的 Schema、去重、来源、确认、supersession 和 archive；
- 现有业务表继续保存用户可见的最终状态；
- 文本模式、旧语音模式和确定性推荐 fallback。

本项目采用**渐进式包裹和接管**，不做大爆炸重写。

## 3. 产品结果

### 3.1 北极星体验

用户从“选岗位”进入“改简历”，再进入“针对这个岗位模拟面试”时，系统不能丢失事实依据，也不能让不同模块各自猜一个用户画像。

系统必须做到：

1. **可靠继续**：刷新、断网和重试不会重复生成题目或重复产生副作用。
2. **实时响应**：下一题不等待完整评分和报告生成。
3. **结论有证据**：推荐、改写和面试建议可以回到 JD、简历事实、用户偏好或具体 Turn。
4. **进度真实**：UI 展示系统实际做过什么，不展示模型编写的伪思考过程。
5. **个性化可治理**：推断记忆可确认、可纠正、可撤销、可删除。
6. **运行可复现**：知道一次结果使用了哪个 Workflow、模型、Prompt、Provider、Rubric 和 Career Pack 版本。

### 3.2 三次产品交付

| 交付 | 用户拿到的功能 | 技术核心 |
|---|---|---|
| Release 1：面试可靠性 | 重试不重复问题、下一题更快、报告异步补齐、明确降级、Voice Worker 身份可信 | Command、幂等、版本、Service Grant、Fast/Slow Lane、Outbox |
| Release 2：可解释 Runtime | 真实进度时间线、推荐证据抽屉、稳定 fallback 原因、开发者 Run Inspector | Run/Step/Event、Context Compiler、Typed Capability、Verify |
| Release 3：跨流程候选人画像 | 可审阅证据、待确认推断、三模块共享事实、领域版本固定 | Memory Claim Staging、Evidence 引用、Career Pack |

### 3.3 不做什么

- 不建立全局万能 ReAct Loop；
- 不做 Multi-Agent Swarm 或多个 Agent 开会；
- 不把现有业务状态全部改成 Event Sourcing；
- 不展示或持久化隐藏 Chain-of-Thought；
- 不加载模型临时生成的 Python 到生产进程；
- 当前不优先建设 Shell / OS Sandbox；
- 本轮不做自动投递、自动发邮件和自动操作 ATS；
- 不为 Memory 引入图数据库；
- 不把 Auth、隐私、幂等、状态版本做成 Plugin；
- 不把当前 Voice Agent Draft PR 继续扩大成全项目重构。

## 4. 核心术语

| 术语 | 定义 |
|---|---|
| Run | 一次有明确开始和终止状态的业务执行，如一次推荐生成或一场面试 |
| Session | 用户可见的长期容器，可以包含多个 Run 或 Turn |
| Turn | 对话工作流中的一次用户输入和系统响应 |
| Step | Run 中一个可观测的运行步骤 |
| Command | 要求改变业务状态的请求，必须支持鉴权和幂等 |
| Proposal | 无副作用的候选决策，可以被丢弃或重新计算 |
| Commit | 唯一允许产生权威业务副作用的动作 |
| Effect | Commit 后需要异步或外部执行的工作 |
| Capability | 有类型契约的能力，如搜岗位、读 JD、LLM、STT、TTS |
| ContextBlock | 带来源、优先级、敏感度和新鲜度的上下文块 |
| ContextSnapshot | 某次模型请求最终实际选中的 ContextBlock 清单和版本 |
| Domain Event | `AnswerCommitted` 等业务事实 |
| Runtime Event | `CapabilityCompleted` 等运行事实 |
| Projection | 现有业务表中用户可见的当前状态 |

## 5. 目标架构

```text
Web / SSE / LiveKit / Scheduler / Admin
                    |
                 Command
                    v
+--------------------------------------------------------+
| Career Agent Kernel                                    |
|                                                        |
| Protocol / IDs       Command / Idempotency / Version   |
| Workflow Runtime     Retry / Cancel / Recover          |
| Policy / Approval    Context Compiler                  |
| Capability Executor  Event / Trace Recorder            |
| Model / Cost Budget  Memory Claim API                  |
+------------------------+-------------------------------+
                         |
          +--------------+---------------+
          |              |               |
          v              v               v
    岗位推荐          Resume Copilot      模拟面试
 pipeline/research      状态机            双工 Turn Loop
          |              |               |
          +--------------+---------------+
                         |
                         v
岗位库 / ATS / RAG / LLM / STT / TTS / Memory / Evaluator
                         |
                         v
现有业务 Projection + Event Log + Outbox + Async Worker
```

### 5.1 Kernel 的特权边界

Kernel 负责：

- 解析可信 Actor，阻止跨用户访问；
- Command 去重、输入哈希和乐观版本控制；
- Capability 权限检查和外部 Effect 审批；
- 必须执行的 Policy 和 fail-closed 行为；
- Event Schema、版本固定和敏感 Payload 引用；
- Outbox、Lease、Retry、Cancel 和终态。

Kernel 不负责：

- 决定推荐哪个岗位；
- 决定某个回答是否值得追问；
- 判断某条简历 Evidence 是否够写 Bullet；
- 保存领域 Rubric、问题模板和推荐权重。

### 5.2 代码目录

共享代码目标目录：

```text
backend/app/services/career_kernel/
  protocols.py
  commands.py
  events.py
  outbox.py
  policy.py
  budgets.py
  context/
    models.py
    compiler.py
  capabilities/
    spec.py
    registry.py
    executor.py
  memory/
    claims.py
    consolidation.py
  packs/
    manifest.py
    registry.py
```

目录是目标边界，不要求 PR A 一次性创建所有空模块。只有第一个真实消费者出现时才新增对应模块。

Domain Adapter 继续放在现有 `interview`、`resume_copilot`、`recommendation_v2` 中。共享 Kernel 不得反向 import 具体业务实现。

## 6. 跨业务功能需求

### 6.1 Run 与 Command

- `KERNEL-RUN-01`：每次新 Workflow 执行都有稳定 `run_id`。
- `KERNEL-RUN-02`：每个改变状态的请求都有稳定 `command_id`。
- `KERNEL-RUN-03`：已完成 Command 被重放时返回第一次的相同结果。
- `KERNEL-RUN-04`：同一个 `command_id` 携带不同输入时返回 `IDEMPOTENCY_KEY_REUSED`。
- `KERNEL-RUN-05`：依赖当前状态的 Command 必须带 `expected_version`。
- `KERNEL-RUN-06`：版本过期时返回当前权威状态，不产生新副作用。
- `KERNEL-RUN-07`：Cancel 能传播到尚未执行的 Step 和 Effect；Provider 支持时继续传播到底层调用。
- `KERNEL-RUN-08`：进程崩溃后，Lease 到期的 Command / Effect 能被新 Worker 恢复。
- `KERNEL-RUN-09`：Command 的终态只能是 `completed / failed / cancelled`，不能永久停在 `running`。

### 6.2 Context 与 Policy

- `KERNEL-CTX-01`：Provider 返回 `ContextBlock`，不再只返回匿名 Prompt 字符串。
- `KERNEL-CTX-02`：每次模型调用都记录 `context_snapshot_id`。
- `KERNEL-CTX-03`：Context Compiler 在请求模型前执行 Purpose Token Budget。
- `KERNEL-CTX-04`：根据 Policy 删除、脱敏或引用敏感内容。
- `KERNEL-CTX-05`：Required Block 失败时阻止请求；Optional Block 失败时显式降级。
- `KERNEL-CTX-06`：被截断或未选中的 Block 必须记录确定性原因。
- `KERNEL-CTX-07`：上下文按 `stable_prefix / run_snapshot / turn_dynamic` 三层编译，变化频率更低的内容必须排在更前面。
- `KERNEL-CTX-08`：Stable Prefix 的工具顺序、Block 顺序和序列化结果必须确定，禁止时间戳、剩余预算、无序 JSON 等请求级变量进入该前缀。
- `KERNEL-CTX-09`：Run Snapshot 在 Run 开始时固定画像、JD、Career Pack 和 Rubric 版本；中途修改必须生成新 Revision 和 Hash，不能静默漂移。
- `KERNEL-CTX-10`：Turn Dynamic 只携带当前业务状态、检索证据、工具结果、对话摘要和用户输入，不向模型暴露工作目录、Git、主机或数据库结构等无关基础设施环境。
- `KERNEL-CTX-11`：仓库级 `CLAUDE.md / AGENTS.md` 只服务开发 Agent，不得直接作为面向求职用户的 Runtime Prompt 来源。
- `KERNEL-POL-01`：安全、身份、Consent 和外部动作审批不属于 best-effort Provider。
- `KERNEL-POL-02`：Policy 执行失败时 fail closed。

### 6.3 Capability

- `KERNEL-CAP-01`：Capability 有 Pydantic Input / Output Schema。
- `KERNEL-CAP-02`：Capability 声明 Side Effect、Permission、Timeout、Idempotency、Sensitivity 和 Version。
- `KERNEL-CAP-03`：参数错误返回 Typed Observation，不把手写 `_normalize_tool_args` 当作主要契约。
- `KERNEL-CAP-04`：模型 Step、失败 Step、Tool Call、Token、Cost 和 Deadline 都进入 Budget。
- `KERNEL-CAP-05`：外部副作用必须有稳定 `effect_id` 和 Approval Policy。
- `KERNEL-CAP-06`：Unknown Tool 和 Invalid Output 都消耗 Step Budget。

### 6.4 Event 与透明进度

- `KERNEL-EVT-01`：Event 只追加，在事件发生处打 `occurred_at`。
- `KERNEL-EVT-02`：Domain Event、Runtime Event 和 Metric 采用不同 Event Type。
- `KERNEL-EVT-03`：用户进度由事实 Event Reducer 生成。
- `KERNEL-EVT-04`：不保存或展示隐藏推理和完整敏感 Prompt。
- `KERNEL-EVT-05`：每次 Fallback 记录触发原因、采用方案和用户影响。
- `KERNEL-EVT-06`：当前业务表继续作为权威 Projection，本项目不做全量 Event Replay。

### 6.5 Memory

- `KERNEL-MEM-01`：模型推断出的长期记忆先写 Staged Claim。
- `KERNEL-MEM-02`：Staged Claim 必须保存 Evidence 和 Extractor Version。
- `KERNEL-MEM-03`：冲突 Claim 不得静默覆盖 Active Memory。
- `KERNEL-MEM-04`：未确认的模型推断不能覆盖用户确认的事实。
- `KERNEL-MEM-05`：用户可以查看、确认、修改、归档和删除 Claim。
- `KERNEL-MEM-06`：一次面试得分、一次停顿或未校准的人格推断不能成为永久事实。

## 7. 核心协议

### 7.1 CommandEnvelope

```python
class CommandEnvelope(BaseModel):
    command_id: UUID
    run_id: UUID
    workflow: Literal["recommendation", "resume", "interview"]
    command_type: str
    actor_type: Literal["user", "service", "worker", "admin"]
    actor_id: str
    session_id: str | None = None
    turn_id: UUID | None = None
    expected_version: int | None = None
    source: Literal["web", "livekit", "retry", "worker", "scheduler"]
    occurred_at: datetime
    payload: dict
```

`command_id` 表示“一次业务意图”。网络重试必须复用同一个 ID，不能每次生成新 ID。

输入哈希规则：

```text
删除 occurred_at、trace header 等非业务字段
-> JSON key 排序
-> 字符串按 UTF-8 编码
-> 对稳定业务字段做 SHA-256
```

同一个 `command_id` 的 Hash 不同，直接拒绝。

### 7.2 AgentEvent

```python
class AgentEvent(BaseModel):
    event_id: UUID
    run_id: UUID
    workflow: str
    session_id: str | None
    turn_id: UUID | None
    step_id: UUID | None
    parent_step_id: UUID | None
    event_type: str
    schema_version: str
    status: str
    occurred_at: datetime
    duration_ms: int | None
    actor: str
    capability: str | None
    context_snapshot_id: UUID | None
    input_ref: str | None
    output_ref: str | None
    attempt: int
    fallback_reason: str | None
    user_visible: bool
    sensitivity: list[str]
    payload: dict
```

Event 只存紧凑事实。Raw Audio、完整简历、完整 Prompt 和大型 Tool Result 只能存访问受控的引用，不能复制到 Event Log。

### 7.3 ContextBlock 与 ContextSnapshot

```python
class EvidenceRef(BaseModel):
    source_type: str
    source_id: str
    excerpt: str | None = None
    field_path: str | None = None


class ContextBlock(BaseModel):
    block_id: UUID
    provider: str
    provider_version: str
    purpose: str
    layer: Literal["stable_prefix", "run_snapshot", "turn_dynamic"]
    cache_scope: Literal["global", "workflow", "run", "none"]
    content: str
    content_hash: str
    priority: int
    estimated_tokens: int
    evidence_refs: list[EvidenceRef]
    why_selected: str
    freshness_at: datetime | None
    expires_at: datetime | None
    sensitivity: list[str]
    required: bool
    dedup_key: str


class ContextSnapshot(BaseModel):
    snapshot_id: UUID
    run_id: UUID
    run_revision: int
    purpose: str
    token_budget: int
    ordered_block_ids: list[UUID]
    omitted: list[dict]
    provider_versions: dict[str, str]
    stable_prefix_hash: str
    run_snapshot_hash: str
    snapshot_hash: str
```

#### 7.3.1 Context 生命周期与缓存边界

JobRadar 借鉴 Coding Agent 的“稳定前缀在前、变化后缀在后”，但不照搬代码仓库环境。Runtime Context 固定编译为：

| 层 | 内容 | 典型生命周期 | 缓存策略 |
|---|---|---|---|
| `stable_prefix` | Kernel 行为边界、Workflow 合同、Capability Schema、输出协议 | 随发布版本变化 | 跨 Run 或同 Workflow 复用 |
| `run_snapshot` | 用户确认画像、目标岗位、规范化 JD、Career Pack、Rubric | 一次 Run 内冻结 | 按 `run_id + revision` 复用 |
| `turn_dynamic` | 当前输入、对话摘要、实时检索、Memory 召回、工具结果、预算和状态 | 每轮变化 | 不进入稳定前缀 |

逻辑 Prompt 顺序：

```text
Stable Tool Definitions
-> Kernel Policy / Workflow Contract / Output Schema
--- stable cache boundary ---
-> Profile / JD / Career Pack / Rubric Run Snapshot
--- run cache boundary ---
-> Conversation Summary / Retrieved Evidence / Tool Observation
-> Current Workflow State / Current User Input
```

`run_snapshot` 从平台视角属于动态用户数据，但在单次 Run 内必须字节稳定。用户更换 JD、修改关键画像或切换目标方向时创建新 Revision；后续 Step 只能引用新 Revision，已完成 Step 保留原 Snapshot 以便复现。

Prompt Asset 采用版本化、可编译的资源，不使用一个巨大的项目级 Markdown 作为运行时事实源：

```text
prompts/kernel/core.md
prompts/workflows/<workflow>.md
prompts/output_contracts/<contract>.yaml
career_packs/<pack>/<version>/manifest.yaml
career_packs/<pack>/<version>/rubric.md
```

Markdown 承载适合自然语言表达的行为说明；Manifest / Schema 承载版本、适用范围、依赖、优先级和 Hash。安全、权限、Consent、Tenant Guard 仍由代码执行，不能依赖模型遵守 Prompt。

`omitted` 至少包含 `block_id + reason`，原因枚举为：

```text
not_applicable
permission_denied
expired
duplicate
lower_priority
token_budget
provider_failed
policy_blocked
```

### 7.4 CapabilitySpec

```python
class CapabilitySpec(BaseModel):
    name: str
    version: str
    input_schema: str
    output_schema: str
    side_effect: Literal["none", "local", "external"]
    permissions: list[str]
    timeout_ms: int
    idempotent: bool
    sensitivity: list[str]
    retry_policy: str
```

统一执行顺序：

```text
Input Schema Validate
-> Authorization / Policy
-> Sensitive Data Transform
-> Timeout / Cancellation Setup
-> Execute
-> Output Schema Validate
-> Event / Cost Record
-> Summary + Payload Ref
```

### 7.5 Run Version Pins

每个 Run 保存：

```json
{
  "workflow_version": "interview/v2",
  "career_pack": "ai.engineering@1.0.0",
  "rubric_version": "backend-interview@3",
  "prompt_versions": {"followup": "v8", "scoring": "v6"},
  "model_profile": "interview-low-latency@2",
  "context_provider_versions": {"memory": "v2", "xhs": "v1"},
  "feature_flags": {"async_analysis": true}
}
```

版本更新只对新 Run 生效。进行到第三题的面试不能中途切换 Rubric 或 Career Pack。

### 7.6 统一错误码

| HTTP | Error Code | 行为 |
|---|---|---|
| 400 | `INVALID_COMMAND` | 请求不满足 Command 契约 |
| 401 | `INVALID_ACTOR_CREDENTIAL` | 用户 Token 或 Service Grant 无效 |
| 403 | `COMMAND_NOT_ALLOWED` | Actor 没有该 Capability / Command 权限 |
| 409 | `STALE_VERSION` | 返回当前 Version 和权威状态，不执行副作用 |
| 409 | `IDEMPOTENCY_KEY_REUSED` | 相同 ID 对应不同 Input Hash |
| 202 | `COMMAND_IN_PROGRESS` | 同一 Command 正由其他 Lease Owner 执行 |
| 422 | `CAPABILITY_INPUT_INVALID` | Tool 参数不满足 Schema |
| 503 | `REQUIRED_PROVIDER_UNAVAILABLE` | Required Provider 失败，不能静默降级 |

## 8. Release 1：面试可靠性

### 8.1 用户功能

Release 1 交付：

- 同一场面试在刷新、重连和重复提交后不会多出一题；
- 下一题不再等待完整评分、参考答案和 Voice Facts；
- 报告显示 `分析中 / 部分完成 / 已完成 / 部分降级`；
- 版本过期的前端恢复到服务器权威题目；
- LiveKit Worker 不能伪造其他用户身份；
- 实时链路失败时继续回落文本或旧语音路径。

### 8.2 Voice Worker Service Grant

LiveKit Worker 调后端时必须携带短期签名 Service Grant。

Grant Claims：

```text
sub           jobradar-voice-agent
context_id    <realtime context id>
session_id    <interview session id>
user_key      <resolved owner>
room_name     <livekit room>
permissions   [interview.turn.commit]
expires_at    <short TTL>
nonce         <unique value>
```

后端验证：

- 签名和有效期；
- Permission；
- `context_id` 仍有效且没有关闭；
- Room、Session、User 与数据库 Context 一致；
- Nonce 没有被撤销。

后端从 Grant 推导 `user_key`，忽略 Service Caller 自己提交的裸 User Key。浏览器继续使用 Bearer Token 和 `resolve_user_key`。

### 8.3 数据模型

#### `interview_session_states`

| 字段 | 契约 |
|---|---|
| `session_id` | 主键，兼容现有公开 Session ID |
| `user_key` | 已解析的 Owner |
| `run_id` | 稳定 Kernel Run ID；PR C 前先作为 Opaque UUID |
| `version` | 乐观状态版本，从 0 开始 |
| `status` | active / completing / completed / cancelled |
| `current_turn_index` | 当前权威可见题目 |
| `created_at / updated_at` | 生命周期时间 |

#### `interview_commands`

| 字段 | 契约 |
|---|---|
| `command_id` | 主键 |
| `session_id` | Aggregate ID |
| `command_type` | start_session / commit_answer / cancel_session |
| `expected_version` | Caller 看到的状态版本 |
| `input_hash` | 防止 Idempotency Key 被不同请求复用 |
| `status` | claimed / answer_committed / completed / failed / cancelled |
| `result_json` | 用于幂等重放的权威结果 |
| `lease_owner / lease_expires_at` | 崩溃恢复 |
| `error_code / error_message` | 终态错误 |
| 时间字段 | created / updated / completed |

#### `interview_turns` 增量字段和约束

- `turn_id TEXT NOT NULL UNIQUE`；
- `command_id TEXT NULL UNIQUE`；
- `analysis_status TEXT NOT NULL DEFAULT 'pending'`；
- `UNIQUE(session_id, turn_index)`；
- 保留当前整数 `id`，不破坏已有接口。

Migration 必须给历史行回填稳定 `turn_id`。加唯一约束前先生成重复报告；如历史数据存在相同 `(session_id, turn_index)`，导出审阅，禁止静默删除。

### 8.4 开场和提交回答 API

现有 `/api/interview/turn` 保留为兼容 Adapter，内部转发新的 Command Service。

首次开场必须走 `start_session` Command，不能只依赖“查不到 last_turn 就插第一题”。同一个开场 `command_id` 重试时返回同一题。

`commit_answer` 请求：

```json
{
  "command_id": "uuid",
  "session_id": "session-123",
  "expected_session_version": 4,
  "expected_turn_index": 2,
  "target_job": "AI Agent Engineer",
  "answer_text": "...",
  "asr_evidence": {},
  "context_id": "service-caller-only"
}
```

响应：

```json
{
  "command_id": "uuid",
  "run_id": "uuid",
  "session_version": 6,
  "answered_turn_id": "uuid",
  "next_turn": {
    "turn_id": "uuid",
    "turn_index": 3,
    "question": "...",
    "source": "followup"
  },
  "analysis_status": "pending",
  "replayed": false,
  "fallback": null
}
```

SSE Adapter 可以把该对象作为 `turn_complete` 事件发送；Command Service 本身不能依赖 SSE。

### 8.5 Propose / Commit

禁止在数据库事务中等待 LLM。

```text
1. 鉴权并校验 Command / Input Hash。
2. Transaction A：
   - Claim Command；
   - 校验 expected_version 和 expected_turn_index；
   - Commit 当前回答；
   - Session Version +1；
   - 写入 Slow Lane Outbox Effects；
   - Command -> answer_committed。
3. 事务外：
   - 生成轻量 TurnSignal；
   - Interview Policy Propose 下一题；
   - 超过 Deadline 使用确定性 Fallback。
4. Transaction B：
   - 校验回答提交后的 Session Version；
   - 插入唯一的下一题；
   - Session Version +1；
   - 保存 Result，Command -> completed。
5. 返回权威结果；重复 Command 返回同一 Result。
```

如果 Transaction B 遇到版本冲突，丢弃 Proposal，读取已经提交的权威下一题，不能再插入一题。

`session_version` 表示权威 Projection 的状态转换次数，不表示 Command 数量。因此一次 `commit_answer` 正常可以从 Version 4 变为 Version 6：Version 5 代表回答已 Commit，Version 6 代表下一题已 Commit。

### 8.6 Fast Lane / Slow Lane

#### Fast Lane

```text
Answer Commit
-> TurnSignal
-> Follow-up / Advance / End Proposal
-> Version-checked Next Question Commit
-> Response / TTS
```

```python
class TurnSignal(BaseModel):
    answer_complete: bool
    needs_clarification: bool
    missing_dimensions: list[str]
    followup_reason_code: str | None
    quality: Literal["valid", "degraded", "unavailable"]
```

Fast Lane 先跑硬规则，再调用低延迟模型。超时、无效 JSON 或 Provider 错误时走确定性 Advance / Fallback，并记录 `FallbackActivated`。

#### Slow Lane

Outbox Effects：

- 完整多维评分；
- Reference Answer；
- Voice Facts 和授权 Audio Analysis；
- Report Aggregate；
- Staged Memory Extraction；
- 单独校准后才允许加入的纵向能力估计。

初始 Retry Policy：

```text
max_attempts: 3
backoff: 2s, 10s, 60s
lease: 90s
terminal: degraded + analysis_failures
late_result_fence: turn_id + effect_id + analyzer_version
```

使用带数据库 Lease 的独立 Worker 入口。不能依赖 API 进程内单例 Scheduler，因为未来多副本会重复执行。

Release 1 的支持档位仍是**单节点 SQLite + 独立 Worker Process**，本阶段不宣称多节点分布式执行。需要横向扩展 API / Worker 前，必须先把 Command、Outbox 和 Event Store 迁到支持多写者的数据库；Domain Contract 和 Idempotency Key 保持不变。

### 8.7 Release 1 验收

功能和正确性：

- 同一个 `start_session command_id` 重放 100 次只产生一条第一题；
- 同一个 `commit_answer command_id` 并发重放 100 次只产生一次回答推进和一条下一题；
- 两个不同 Command 使用相同 Expected Version 时，一个成功，一个返回 `STALE_VERSION`；
- 相同 Command ID 携带不同 Input Hash 时被拒绝；
- Process 在 Transaction A 后崩溃，重试后能继续完成同一 Command；
- 伪造、过期、错误 Room 和错误 Context 的 Service Grant 全部被拒绝；
- 下一题路径不等待完整 Score、Reference Answer 或 Voice Facts；
- Fallback Question 和 Reason 落库，不只存在 SSE Response；
- UI 能区分 pending / partial / complete / degraded；
- Legacy Text / Voice Path 在 Feature Flag 关闭时仍可用。

初始性能目标，不包含 TTS 播放：

- Answer Commit DB Path p95 < 150 ms；
- Answer Commit 到 Next Question Decision p95 < 3 s；
- 95% Slow Lane Effect 在 60 s 内进入终态；
- Retry / Reconnect 语料中的 Duplicate Visible Turn Rate = 0。

## 9. Release 2：可解释 Runtime

### 9.1 用户功能

用户得到真实的工作进度和证据解释。开发者得到一个 Run Inspector，能够回答：

- 哪些 Context 被选中和丢弃；
- 调用了哪些 Capability；
- 使用了什么版本、Timeout、Retry 和 Fallback；
- 最终结论依赖了什么 Evidence；
- 延迟、Token 和费用花在哪里。

### 9.2 Sidecar 数据表

#### `agent_runs`

`run_id`、workflow、user/session、status、state_version、version_pins_json、budget_json、started/completed、cancel、terminal_error。

#### `agent_steps`

`step_id`、run/parent、step_type、capability、status、attempt、started/completed、context_snapshot_id、input/output_ref、fallback、cost/usage。

#### `agent_events`

Append-only `AgentEvent`。按 run、session、turn、event_type、occurred_at 建索引，只保存紧凑 Payload。

#### `context_snapshots`

Purpose、Token Budget、Selected / Omitted Manifest、Provider Version、Snapshot Hash、Created At。敏感正文仍留在权限受控的数据源中。

#### `agent_effects_outbox`

Effect ID、Run/Step、Effect Type、Idempotency Key、Payload、Status、Attempts、Available At、Lease、Result Ref、Error 和时间字段。

PR B 先为面试创建这张表；PR C 将它纳入正式 Kernel Sidecar，而不是新建第二张队列表。

### 9.3 Event 接入顺序

1. Interview Command 和 Slow Lane 原生写 Kernel Event。
2. Recommendation 同时写现有 `agent_trace_json` 和 Kernel Event。
3. Event Reducer 生成现有 Trace API Shape。
4. Parity Test 通过后，Kernel Event 成为 Trace 来源；旧 JSON 保留一个 Release 作为 Projection。
5. Resume Plan Mode 接入 Run / Step Event，但不修改业务状态机。

本阶段不通过 Event Replay 重建业务状态。

### 9.4 Context Compiler

旧 Provider 逐个适配：

```text
现有 fetch() 结果
-> Adapter 生成 ContextBlock
-> Shadow Context Snapshot
-> 对比旧 Prompt 和新 Manifest
-> 按 Purpose 灰度切换
```

Purpose 接入顺序：

1. Recommendation 的 JD / Company Context；
2. Interview Question Context；
3. Resume Bullet Rewrite Context；
4. Report 和长文本 Summary。

Compiler 固定阶段：

```text
Resolve Versioned Stable Assets
-> Freeze / Load Run Snapshot
-> Collect Turn-dynamic Blocks
-> Policy / Ownership Filter
-> Purpose Filter
-> Deduplicate
-> Freshness Check
-> Priority / Relevance Score
-> Token Allocation
-> Truncate / Approved Summarize
-> Snapshot / Hash
-> Prompt Render
```

Compiler 输出至少包含 `stable_prefix_hash / run_snapshot_hash / snapshot_hash`。同一 Workflow Version 的 Stable Prefix 必须保持固定顺序和规范化序列化；不得因为当前时间、Provider 返回顺序、工具剩余次数或字典 Key 顺序发生无意义 Cache Miss。

模型 Adapter 负责将两个逻辑缓存边界映射到具体供应商能力；不支持显式 Cache Breakpoint 的模型仍使用相同的前缀顺序，以获得供应商自动前缀缓存或降低后续迁移成本。

`SensitiveTopicProvider` 的安全职责迁到 Required Policy。XHS、Podcast、Company Intel 等可选 Provider 失败时记录显式降级。

### 9.5 Typed Capability

第一批迁移推荐工具：

- `search_candidates`；
- `inspect_jobs`；
- `get_company_intel`。

模型输出改为：

```json
{
  "action": "inspect_jobs",
  "args": {"job_ids": ["job-1", "job-2"]},
  "decision_summary": "核对岗位职责与申请条件"
}
```

不再请求 `thought`。`decision_summary` 只是可选的人类可读意图，真实 Event 才是事实来源。

Budget 维度：

```text
max_model_steps
max_tool_calls
max_failed_steps
max_prompt_tokens
max_completion_tokens
max_cost
deadline
```

每次模型请求都消耗 Model Step，包括无效 JSON、Unknown Tool 和 Tool Input Validation Failure。

### 9.6 Deterministic Verify

推荐 Finalize 前由代码检查：

- `job_id` 是否属于原 Candidate Pool；
- Job 是否 Active，必要时 Canonical URL 是否有效；
- 地点、用工类型、毕业时间和显式 Exclusion 是否满足；
- 是否重复；
- 单公司 Cap 是否满足；
- 展示的事实理由是否带 `EvidenceRef`；
- 数量是否超过上限。

Verify 先在 Warn-only Shadow Mode 运行。离线语料确认没有错误硬拦截后再 Blocking。

### 9.7 用户和开发者界面

#### 用户进度

由 Event Reducer 生成：

```text
从 124 个岗位中召回 30 个
按地点和岗位类型筛选到 18 个
读取了 6 个岗位的完整 JD
核对了 4 家公司的公开信息
验证岗位状态后输出 8 个推荐
```

#### Recommendation Evidence Drawer

每个结果展示：

- JD Requirement 和来源；
- 对应的 Resume Evidence 或 User Preference；
- 通过的 Hard Constraints；
- Risk、Missing Information 和 Freshness；
- Score / Career Pack Version。

#### Developer Run Inspector

只读且受权限控制：

- Run / Step Timeline；
- Context Block Manifest 和 Omission Reason；
- Model / Capability Version；
- 脱敏 Arguments 和 Output Ref；
- Retry、Cancel、Fallback、Latency、Token、Cost。

### 9.8 Release 2 验收

- 100% Completed Recommendation Run 有 Run Start 和 Terminal Event；
- 100% 展示的推荐事实有 Evidence Ref，无法取证的内容标注为模型建议；
- Blocking 上线后 Candidate Pool、Duplicate、Hard Constraint Violation = 0；
- 每次模型请求都有 Context Snapshot、Model Profile 和 Budget Record；
- Optional Provider 失败产生 Degraded Event 和可用 Fallback；
- Required Policy 失败阻止执行；
- Student API、Event、Log、UI 中没有隐藏 Chain-of-Thought；
- Shadow 迁移期间推荐质量保持在已约定离线评测容差内。

## 10. Release 3：跨流程候选人画像

### 10.1 用户功能

用户得到一个候选人证据中心：

- 已确认身份和求职偏好；
- 带原文来源的经历 Evidence；
- 等待确认的模型推断；
- 面试产生的练习信号；
- 修改、冲突、替代和删除历史；
- 某条事实曾被哪些推荐、简历或面试使用。

三个 Workflow 使用同一份治理后的事实，但每个 Purpose 通过自己的 Context Snapshot 读取。

### 10.2 Memory Claim Staging

新增 `memory_claim_candidates`，不直接让所有现有 Memory Reader 理解 Staged Row。

字段：

```text
claim_id
user_key
category
summary
payload_json
claim_status: staged | accepted | rejected | conflicted | expired
assertion_type: user_asserted | extracted | inferred
source_module / source_session_id / source_message_id
evidence_refs_json / raw_excerpt
confidence
verification_method
consent_scope / sensitivity
model_version / extractor_version
valid_from / valid_to
conflicts_with_json
created_at / reviewed_at
```

Consolidation Flow：

```text
Transcript / Resume Change / Artifact
-> Extract Candidate Claims
-> Schema / Evidence Validate
-> Deduplicate
-> Conflict / Supersession Detect
-> Propose Accept / Conflict
-> User or Policy Review
-> Promote via existing memory.dispatcher
```

Promotion 必须继续走现有 Dispatcher，保留 Schema、Dedup、Supersession、Archive 和 Tenant Guard。

### 10.3 Memory Retrieval

Memory 召回不再主要依赖 least-used 轮换，改为 Purpose-aware Score：

```text
Task Relevance
* Evidence Reliability
* User Confirmation Weight
* Freshness
* Active Job / Track Alignment
* Non-redundancy
```

最终仍转换为 `ContextBlock`，Memory 不得绕过 Context Compiler。

### 10.4 Career Pack

Career Pack 是版本化领域配置，不是任意可执行 Plugin。

第一批：

- `finance.general@1.0.0`：复用现有金融 Taxonomy、Rubric 和 Knowledge；
- `ai.engineering@1.0.0`：复用 AI Agent / Backend 岗位资料。

Manifest：

```yaml
id: ai.engineering
version: 1.0.0
api_version: career-pack/v1
question_blueprints: []
scoring_dimensions: []
evidence_requirements: []
resume_rubrics: []
company_taxonomy: []
knowledge_providers: []
language_policy: zh-CN
report_sections: []
evaluator_fixtures: []
```

Pack 注册前校验 Manifest 和引用资源。Run 开始时固定一个版本，中途不 Hot Reload。

### 10.5 Release 3 验收

- 未确认 Inferred Claim 自动提升为 Confirmed Fact 的数量为 0；
- Preference / Identity 冲突必须进入显式解决；
- 用户确认事实不能被更低信任度推断覆盖；
- 每条提升后的 Memory 都保留 Source Evidence 和 Extractor Version；
- 用户可以 Confirm、Correct、Archive、Delete；
- 三个 Workflow 各完成至少一个 Purpose-specific Memory 使用案例；
- 两个 Career Pack 都通过 Schema Validation 和 Evaluator Fixtures；
- Completed Run 可以还原 Pack / Provider Version Manifest。

## 11. UI 状态契约

### 11.1 Interview

| State | UI 行为 |
|---|---|
| pending | 下一题可继续，报告显示分析中 |
| partial | 已有事实可展示，缺失部分有明确占位 |
| complete | 预期分析全部完成 |
| degraded | 回答已保存，展示失败 Part 和 Retry 结果 |
| cancelled | 不再产生新分析，已 Commit 内容按 Retention Policy 保留 |

UI 不允许永久 Spinner。每个 Pending 状态必须有 Retry、Terminal 或明确刷新策略。

### 11.2 Recommendation

稳定用户进度阶段：

```text
recall -> hard_filter -> inspect -> compare -> verify -> finalize
```

每个 Step 支持 `pending / running / completed / degraded / failed / cancelled`。动态计数更新同一个 Step，不为每个 Tick 追加 Trace 行。

### 11.3 Memory

默认低打扰：高可信 User-asserted Fact 可以轻量确认；冲突和敏感推断必须显式 Review；设置页支持完整查看和删除。

## 12. 安全、隐私与 Domain Sandbox

| 动作 | 默认 Policy |
|---|---|
| 搜岗位、读取公开 JD | 当前 Run 内允许 |
| 读取简历和 Memory | 仅当前用户 + 当前 Purpose |
| 生成推荐或草稿 | 允许，结果是 Proposal |
| 保存推断型长期记忆 | Staged，不自动 Confirm |
| 修改正式简历 | 用户触发、可撤销 |
| 保留面试音频 | 显式 Consent、私有目录、短 TTL |
| 投递岗位或联系招聘者 | 本轮 Out of Scope，未来必须确认 |
| 删除用户数据 | 强确认 + 可审计 Effect |
| 执行第三方代码 | Application Process 内禁止 |

Shadow ASR、第二家模型和未来外部集成要单独声明数据发送范围，不能复用模糊 Consent。

## 13. 可观测性与 SLO

| Metric | 用途 |
|---|---|
| Duplicate Turn Rate | Retry / Reconnect 正确性 |
| Command Replay / Conflict Count | 幂等和版本行为 |
| Answer Commit / Next Question Latency | Fast Lane 健康度 |
| Outbox Queue Age / Terminal Rate | Slow Lane 健康度 |
| Capability Latency / Error / Fallback | Provider 健康度 |
| Model Step / Token / Cost per Run | Budget 控制 |
| Context Selected / Omitted Tokens | Compiler 行为 |
| Evidence Coverage Rate | 推荐解释可信度 |
| Memory Staged / Accepted / Conflicted | 个性化治理 |

`occurred_at` 在事件发生位置打戳；`created_at` 只用于分析 Event 写入和 Queue Delay。

告警针对用户影响：Stuck Command、Outbox Queue Age、Unique Constraint Violation、Fallback Rate、Policy Failure、Latency SLO。

## 14. 灰度、迁移与回滚

### 14.1 Feature Flags

```text
INTERVIEW_COMMAND_V2_ENABLED
INTERVIEW_ASYNC_ANALYSIS_ENABLED
CAREER_KERNEL_EVENTS_ENABLED
CONTEXT_COMPILER_ENABLED
TYPED_CAPABILITY_RUNTIME_ENABLED
RECOMMENDATION_VERIFY_BLOCKING_ENABLED
MEMORY_CLAIM_STAGING_ENABLED
CAREER_PACKS_ENABLED
```

Feature Flag 在 Run Start 时固定。

### 14.2 Rollout

1. 增加 Schema 和 Dual-write Event，不改变用户行为。
2. Internal / Dev Session 开启 Interview Command V2。
3. 通过 Duplicate、Crash Recovery 和 Service Grant Security Test。
4. 开启 Async Analysis，保留同步 Fallback。
5. Event Reducer 与旧 Recommendation Trace 做 Shadow Parity。
6. Context Compiler 只生成 Shadow Manifest，不改变 Prompt。
7. 按 Purpose 逐个切换 Compiled Context。
8. Recommendation Verify 先 Warn-only，Review 后 Blocking。
9. Memory Claim 先 Staging 不消费，Review UI 上线后再允许 Promotion。
10. 两个 Career Pack 通过 Fixture 后才开启。

### 14.3 Rollback

- 只对新 Run 关闭新 Feature；
- 已开始 Run 按固定版本完成；
- Command、Event 和 Outbox 数据保留用于审计；
- Legacy `/turn`、旧 Trace Projection 和旧 Context Path 至少保留一个完整 Release；
- 不通过删除已 Commit Turn 或 Memory 历史实现回滚。

## 15. 测试与验收

### 15.1 测试层

| 测试层 | 必须覆盖 |
|---|---|
| Unit | State Transition、Hash、Budget、Compiler Selection、Verifier Rules |
| Database | Unique Constraint、Version Conflict、Outbox Lease、Migration / Backfill |
| Concurrency | Duplicate Command、Competing Command、Lease Expiry、Late Result Fence |
| Security | Cross-user、Forged Grant、Expired Grant、Consent、Retention |
| Contract | Capability Input/Output、Event Schema、Context Snapshot |
| Integration | Interview Fast/Slow Lane、Event Reducer、Memory Promotion |
| Offline Eval | Recommendation Quality、Context Parity、Evidence Coverage、Pack Fixture |
| UI | Reconnect Recovery、Pending/Degraded、Factual Progress、Memory Review |
| Live Acceptance | 真实 LiveKit Room 和 Provider Latency，和 Deterministic CI 分开 |

### 15.2 Release Gates

#### Gate A：确定性正确性

- Focused Backend / Frontend Tests Pass；
- Alembic Single Head；
- Duplicate / Stale Command Tests Pass；
- Cross-user 和 Service Grant Security Pass；
- Student Payload 不包含隐藏 Chain-of-Thought。
- Full-suite 与干净 `main` 做失败清单对照，不新增 Branch-specific Failure；不能把主分支已有失败描述成新功能已全库通过。

#### Gate B：Shadow Parity

- Event Reducer 和旧 Trace 的 Terminal Status 一致；
- Context Compiler Shadow Manifest 在批准的 Token / Source Diff 内；
- Recommendation Verify False Positive 完成 Review；
- Slow Lane Completeness 不低于同步 Baseline。

#### Gate C：真实交互

- 真实 LiveKit Room 的 Retry / Reconnect 不产生 Duplicate Turn；
- Fast Lane 和 TTS Handoff 达到支持网络档位；
- Worker Restart 能恢复 Pending Analysis；
- Text Fallback 可用。

#### Gate D：产品评审

- 用户能理解 Pending / Degraded；
- Evidence Drawer 能回答“为什么”，不暴露内部推理；
- Memory Review 不出现惊讶型自动事实；
- Domain Owner 批准两个 Career Pack Fixture。

## 16. PR 实施顺序

### PR A：Interview Command Correctness

交付：

- Session State、Command Table、Stable Turn ID、Unique Constraint；
- `start_session / commit_answer / cancel_session`；
- Command Claim / Replay / Version Service；
- Browser Auth 和 LiveKit Service Auth 分离；
- Signed Service Grant；
- Persisted Fallback 和 Correlation ID；
- Concurrency / Security Tests。

DoD：Duplicate 和 Stale Request 不能创建第二个 Turn，Legacy Path 可用。

### PR B：Fast Lane / Slow Lane

交付：

- `TurnSignal` 和 Pure Proposal Boundary；
- Two-transaction Propose / Commit；
- Generic Outbox 和 Dedicated Worker；
- Score / Reference / Voice / Report Effects；
- Pending / Partial / Degraded Report State；
- Retry、Lease、Late Result Fence、Crash Recovery Tests。

DoD：Next Question Path 不再等待完整分析。

### PR C：Run / Step / Event Sidecar

交付：

- Kernel Protocol Package；
- Run / Step / Event / Snapshot / Outbox Models；
- Interview Native Events；
- Recommendation Trace Dual-write / Reducer；
- Read-only Developer Run Endpoint。

DoD：不改变现有业务结果，但能通过 Run Timeline 定位一次失败。

### PR D：Context Compiler

交付：

- `ContextBlock / EvidenceRef / ContextSnapshot`；
- Provider Adapter 和 Deterministic Compiler；
- Required Policy Engine；
- Shadow Manifest Comparison；
- Recommendation / Interview 各一个 Purpose Cutover。

DoD：每个迁移后的模型请求都有可审计、受预算控制的 Snapshot。

### PR E：Typed Capability / Verify

交付：

- Capability Registry / Executor；
- 三个 Typed Recommendation Tools；
- Expanded Budget；
- 删除 `thought` Contract；
- Deterministic Recommendation Verify；
- Factual User Progress Reducer。

DoD：Recommendation Tool Use 有 Schema、有 Budget、有确定性 Verify。

### PR F：Memory Claim Governance

交付：

- Staged Claim Table / Extractor Contract；
- Consolidation / Conflict Worker；
- 通过 Existing Dispatcher Promotion；
- Review / Confirm / Reject / Archive UI；
- Purpose-aware Retrieval Score。

DoD：Inferred Claim 不能静默成为 Confirmed Durable Memory。

### PR G：Career Pack V1

至少有两个真实 Consumer 后才做：

- Manifest / Registry；
- Finance / AI Engineering Pack；
- Run Version Pin；
- Pack Validation / Evaluator Fixture。

DoD：同一 Workflow 不改 Kernel Code 就能使用两个 Pack，每个 Run 固定精确版本。

### 16.1 文件影响矩阵

| PR | 新建文件重点 | 修改文件重点 |
|---|---|---|
| A | `career_kernel/protocols.py`、`career_kernel/commands.py`、`interview/commands.py`、`interview/service_grant.py`、Migration、Command/Security Tests | `models.py`、`routers/interview.py`、`voice/livekit_agent.py`、前端 Interview API/State |
| B | `career_kernel/outbox.py`、Worker Entry、`interview/turn_policy.py`、Outbox Migration、Recovery Tests | `interview/orchestrator.py`、Report API/Types、Interview/Report UI |
| C | `career_kernel/events.py`、Event Reducer、Run Inspector Router、Sidecar Migration | Recommendation Workflow、现有 Trace Serializer、Interview Event Writer |
| D | `career_kernel/context/models.py`、`compiler.py`、`policy.py`、Shadow Diff Tests | `llm_context/base.py`、`registry.py`、首批 Recommendation/Interview Consumer |
| E | `career_kernel/capabilities/*`、`budgets.py`、Recommendation Verifier | `resume_copilot/agent/core.py`、`budget.py`、`tools.py`、Progress UI/API |
| F | `career_kernel/memory/*`、Claim Migration、Consolidation Worker、Memory Review UI | Existing Memory Dispatcher/Provider、各 Workflow Extractor |
| G | `career_kernel/packs/*`、两套 Manifest/Fixture | Interview/Resume/Recommendation 的 Pack Adapter、Run Version Pins |

## 17. 工作量和职责

单个主开发者 + Coding Agent 的粗略工作量，不含等待真人和真实 Provider 验收：

| Package | PR | 预估 |
|---|---|---|
| Interview Reliability | A-B | 7-10 个开发日 |
| Explainable Runtime | C-E | 8-12 个开发日 |
| Candidate Profile | F-G | 10-15 个开发日 |

| 领域 | Accountable Role |
|---|---|
| 产品行为和验收 | FDE / 技术产品 Owner |
| Kernel Contract / Migration | Backend Owner |
| Interview Policy / Voice Gate | Interview / Voice Owner |
| Recommendation Verify / Evidence | Recommendation Owner |
| Context / Memory Governance | AI Platform Owner |
| Progress / Report / Review UI | Frontend Owner |
| Security / Privacy Gate | Backend Owner + Product Approval |

## 18. 最终实施原则

1. 包裹已经工作的 Workflow，不重写成一个 Loop。
2. 增加 Autonomy 前，先保证 State-changing Command 幂等。
3. Proposal 无副作用，Commit 必须带版本检查。
4. 实时响应和异步分析走两条 Lane。
5. Event 记录事实，不记录模型表演出来的思考。
6. Context 是编译后、带版本的 Artifact，不是随手拼接的字符串。
7. Capability 是 Typed Service，不是任意 Python Plugin。
8. 推断型 Memory 先 Staging，必须保留 Evidence、Consent 和纠错路径。
9. Workflow、Rubric、Prompt、Model、Provider 和 Career Pack 对 Run 固定版本。
10. 这次改造是否成功，最终看用户感知的可靠性、响应速度、证据质量和交付效率，而不是架构看起来多像通用 Coding Agent。
