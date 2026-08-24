# JobRadar Open-source TUI 实施 Spec

- 状态：Implemented Alpha（`v0.1.0-alpha`；许可证与公共数据源同步仍是 GA 前置项）
- 日期：2026-08-24
- 面向版本：`0.1.0-alpha`
- 产品边界：仅开放「岗位检索」与「简历优化」
- 关联设计：`career-agent-kernel-implementation-spec-2026-08-21.md`、`progressive-memory-disclosure-prd-2026-08-22.md`

## 1. 决策摘要

JobRadar 将提供一个**本地优先、可独立安装的终端产品**，让用户不部署完整 Web、管理端和面试服务，也能使用项目最成熟、最容易复用的两项能力：

1. 从本地岗位库检索、筛选、比较和收藏岗位；
2. 针对选定 JD 诊断简历，并以可审阅的 patch 形式生成优化建议。

第一版采用以下路线：

- TUI 使用 Python `Textual`，不另写 Go 业务层；
- 从现有 FastAPI 代码中抽取无 HTTP 依赖的 `career_core`；
- 本地 SQLite 承担岗位索引、用户状态、Run 和 Memory 的结构化存储；
- 简历原件、导出文件和 Run Manifest 保存在用户工作区；
- 岗位检索无需 LLM 即可工作，简历优化使用用户自己的 OpenAI-compatible 或 Ollama endpoint；
- Runtime 采用有限状态工作流和受预算约束的 Capability，不开放任意 shell、浏览器或文件系统代理；
- 系统包与用户数据物理分离，升级绝不能修改简历、画像、记忆、收藏或历史产物；
- 不发布生产岗位库、私有 XHS 语料、学生数据和音频，也不包含自动投递。

推荐命令形态：

```bash
uv tool install jobradar
jobradar init
jobradar doctor
jobradar tui
```

### 1.1 Alpha 实际交付

当前仓库已经落地：

- 根目录可安装 Python package 和 `jobradar` console script；
- `init`、`doctor`、`config`、`jobs`、`resume` 和 `tui` 命令；
- XDG / `JOBRADAR_HOME` 工作区与系统/用户数据物理隔离；
- SQLite WAL、FTS5、岗位导入、检索、排序、收藏和排除；
- PDF、DOCX、Markdown、TXT 简历解析与内容寻址原件存储；
- Stable Prefix、Run Snapshot、Turn Dynamic 和 L1/L3 Memory 实际调用；
- OpenAI-compatible/Ollama、远程模型显式授权和环境变量 Key；
- 证据化 Resume Patch、Blocked Gate、人工接受和新版本导出；
- Jobs、Resume、Runs、Settings 四页 Textual TUI；
- Docker、三版本 Python CI、离线 smoke test 和桌面/窄终端 Pilot 测试。

尚未落地：生产或公共 ATS 自动同步、PyPI 正式发布、L0 用户约束和 L2 经历的
自动抽取、历史 schema 跨版本迁移，以及根仓库许可证。它们继续按后文
Phase 0/4/5 推进，README 不把这些写成现成功能。

## 2. 为什么做这个版本

当前仓库是一个完整产品工程，包含 FastAPI、Next.js、管理端、爬虫调度、RAG、模拟面试和实时语音。它能展示系统深度，但外部用户为了体验岗位和简历能力，需要理解过多服务、环境变量和数据依赖。

开源 TUI 的目标不是复制完整线上产品，而是形成一个清晰的开源入口：

> 用户带着自己的简历和模型，在本地得到可追溯的岗位选择与简历优化；JobRadar 提供工作流、数据结构、检索方法和防编造边界。

这能同时解决三件事：

- 外部用户在 5 分钟内获得首个有效结果；
- Agent 工程师可以独立阅读和复用 Core，而不必先理解 Web 产品；
- 线上产品继续保留维护型数据基座、私有情报和实时面试等差异化能力。

## 3. 从 career-ops 借鉴什么

参考项目：[santifer/career-ops](https://github.com/santifer/career-ops)。

### 3.1 借鉴的产品原则

| 原则 | JobRadar 的采用方式 |
| --- | --- |
| Local-first | 默认不需要账号或 JobRadar 服务端，用户文件留在本机 |
| System / User Data Contract | 安装包和用户工作区物理分离；升级前自动备份与迁移检查 |
| Bring your own model | 支持 OpenAI-compatible endpoint 和 Ollama，不绑定单一厂商 |
| Human in the loop | Agent 只检索、比较和生成 patch；用户决定是否采纳 |
| Inspectable artifacts | 每次 Run 都有 Manifest、步骤事件、引用和最终产物 |
| One-command onboarding | `init` 创建工作区，`doctor` 一次检查所有依赖 |

### 3.2 不照搬的设计

| career-ops 路线 | JobRadar 不照搬的原因 | JobRadar 选择 |
| --- | --- | --- |
| 依赖 Claude Code/Codex 等 Coding Agent 作为运行时 | 求职用户不应先理解 coding CLI；不同 Agent 的权限和行为也不一致 | 自带受约束 Career Runtime，模型只是推理 Provider |
| Markdown 文件承载主要业务逻辑 | JobRadar 已有可测试的召回、评分、记忆和模型代码 | Prompt Asset 版本化，业务约束由 Python 执行 |
| 人类可读文件作为所有状态的唯一真相源 | 数万岗位的过滤、排序、去重和分页更适合结构化索引 | SQLite 是结构化状态源，原始文档和导出仍是用户文件 |
| 大量模式和全流程求职管理 | 第一版边界会失焦，增加维护与安全面 | 只做岗位检索和简历优化 |
| Agent 可直接操作工作目录 | 对非技术用户权限过大，也难以建立隐私边界 | Capability allowlist，只能访问工作区内声明的资源 |

## 4. 产品范围

### 4.1 Must Have

#### 岗位检索

- 关键词、公司、地点、岗位方向、学历、发布日期等组合筛选；
- 本地 SQLite FTS5 全文检索；
- 规则召回、质量先验、时效和用户偏好的可解释排序；
- 岗位详情、来源、抓取时间、原始链接和失效状态展示；
- 收藏、排除、加入简历优化；
- JSON、CSV 和 JobRadar SQLite 数据导入；
- 可选的公开来源同步 Adapter，默认遵循来源条款和速率限制；
- 搜索和查看岗位在无 LLM、无网络时仍可工作。

#### 简历优化

- 读取 PDF、DOCX、Markdown 和纯文本；
- 解析出经历、技能、教育和可引用的原文位置；
- 用户确认 Candidate Contract 后再进入生成；
- 选择本地岗位或粘贴 JD 作为目标；
- 展示匹配点、缺口、证据不足和关键词覆盖；
- 按 section/bullet 生成修改建议；
- 每个新增事实必须引用简历原文或已确认 Memory；
- 逐条接受、拒绝或编辑 patch；
- 永不覆盖原始简历，导出新的 Markdown 和结构化 JSON 版本；
- 输出清楚区分“措辞优化”“结构调整”和“需要用户补充事实”。

#### 共同能力

- 本地工作区初始化、升级和备份；
- Model Provider 配置与连通性检查；
- Run 时间线、取消、重试和明确降级；
- Stable Prefix、Run Snapshot、Turn Dynamic 三层 Context；
- L0-L3 渐进式 Memory 披露；
- 默认关闭遥测；日志不得记录简历全文、API Key 或完整 Prompt；
- 中英文终端正确显示，窄终端有可用的单栏降级布局。

### 4.2 明确不做

- 模拟面试、实时语音和 Voice Facts；
- 私有 XHS、播客或学生知识库分发；
- 自动点击投递、自动填写表单或批量海投；
- 登录、团队协作、多租户和云同步；
- 管理端、爬虫运维看板和完整调度平台；
- 任意 shell、任意浏览器和任意目录访问；
- 在 V1 建设通用热加载插件市场；
- 默认上传用户简历到 JobRadar 服务端。

## 5. 用户故事与成功路径

### 5.1 首次使用

```text
安装 → jobradar init → 选择工作区
→ 导入简历 → 选择模型或先跳过
→ 导入样例/本地岗位数据 → 进入 TUI
```

`init` 只收集完成首轮所需的信息，不要求用户一次填写完整画像。模型未配置时，岗位检索可继续使用，简历生成操作显示为 unavailable，并告诉用户缺少哪项配置。

### 5.2 岗位检索路径

```text
输入“上海 AI Agent 后端 校招”
→ Query Parser 生成结构化条件
→ SQL 硬过滤 + FTS 召回
→ 规则排序与原因生成
→ 用户查看 JD / 来源 / 风险
→ 收藏或发送到“简历优化”
```

模型只在用户主动选择“帮我进一步比较”时介入。基础搜索不让 LLM 决定岗位是否存在，也不允许它生成库外 `job_id`。

### 5.3 简历优化路径

```text
选择简历 + 目标 JD
→ 冻结 Run Snapshot
→ 找到 JD 要求与简历证据
→ 生成诊断
→ 针对单个 section/bullet 提议 patch
→ 用户逐条确认
→ 防编造 Verify
→ 导出新版本与变更说明
```

若模型建议了数字、技能、职责或结果，但 L2/L3 中找不到依据，该修改不能进入“可直接采纳”列表，只能进入“待补充事实”。

## 6. TUI 信息架构

### 6.1 全局结构

```text
┌ JobRadar ─ workspace ─ model status ─ run status ┐
│ Jobs │ Resume │ Runs │ Settings                  │
├───────────────────────────────────────────────────┤
│ 当前页面主区域                                    │
├───────────────────────────────────────────────────┤
│ command/help · progress · error/retry             │
└───────────────────────────────────────────────────┘
```

- `Jobs`：过滤条、结果表、详情和证据；
- `Resume`：原文结构、诊断、patch diff 和导出；
- `Runs`：步骤时间线、输入快照、Context Manifest、失败原因；
- `Settings`：模型、工作区、数据源和隐私选项。

键盘导航遵循终端常见约定，并为全部命令提供 command palette。图标只作辅助，所有状态必须有文本语义。

### 6.2 Jobs 页面

宽终端采用“结果表 + 详情”双栏，窄终端在列表和详情间切换。结果表固定显示：匹配度、公司、岗位、地点、发布日期、来源和状态。匹配度是规则特征摘要，不伪装成录用概率。

主要动作：

- 查看原始 JD 与来源；
- 收藏 / 取消收藏；
- 排除并记录原因；
- 比较所选岗位；
- 以该岗位优化简历。

### 6.3 Resume 页面

页面包含四种明确状态：

1. Source：只读原文和解析结果；
2. Diagnosis：JD 对应的证据、缺口和风险；
3. Patch：逐条 diff，支持接受、编辑和拒绝；
4. Export：版本名、格式、引用和变更摘要。

原文与建议不能混为同一可编辑文本，避免用户误把模型建议当作已有经历。

### 6.4 Run 可观测性

用户看到产品步骤，而不是模型内部思维：

```text
[done] 读取简历  0.4s
[done] 冻结目标 JD  0.1s
[done] 召回 7 条相关经历证据  0.2s
[running] 生成项目经历修改建议
[pending] 防编造检查
```

每步可展开查看：使用了哪些输入、调用了哪个 Capability、耗时、输出摘要、是否降级。不得展示或持久化隐藏 chain-of-thought。

## 7. 技术架构

### 7.1 总体结构

```text
Textual TUI
    │ commands / events
    ▼
Career Runtime
    ├── Workflow Engine
    ├── Context Compiler
    ├── Memory Resolver
    ├── Capability Registry
    ├── Policy / Approval
    └── Run Event Store
          │
          ▼
Career Core
    ├── jobs: import / normalize / retrieve / rank
    ├── resume: parse / diagnose / patch / verify
    └── contracts: models / ports / result envelopes
          │
          ▼
Adapters
    ├── SQLite / filesystem
    ├── OpenAI-compatible / Ollama
    ├── PDF / DOCX parser
    └── public job sources / local imports
```

FastAPI 和 TUI 都是 adapter。业务核心不得依赖 `Request`、`Depends`、Cookie、Next.js DTO 或全局 Web Session。

### 7.2 为什么选 Textual

| 方案 | 优点 | 代价 | 结论 |
| --- | --- | --- | --- |
| Go + Bubble Tea | 单二进制、终端体验成熟 | 需要重写 Python 召回、解析、Context 和 Memory，或额外启动 API | 暂不选 |
| Python + Rich 自绘循环 | 依赖少 | 状态管理、焦点、异步和测试需要自建 | 不选 |
| Python + Textual | 可直接复用 Python Core；有 DataTable、异步 Worker、CSS 和测试工具 | wheel 体积更大，冷启动略慢 | V1 选择 |
| 复用任意 Coding Agent CLI | 开发快、模型能力强 | 用户门槛、权限和行为不可控 | 可做可选 Skill，不做主运行时 |

目标是先验证两条垂直工作流，而不是为界面语言牺牲已有工程资产。若未来 Core API 稳定、确实需要单二进制，再做 Go thin client。

### 7.3 建议目录

```text
packages/
  jobradar-core/
    pyproject.toml
    src/jobradar_core/
      contracts/
      jobs/
      resume/
      context/
      memory/
      runtime/
      ports/
  jobradar-tui/
    pyproject.toml
    src/jobradar_tui/
      app.py
      screens/
      widgets/
      commands/
      adapters/
      theme.tcss
prompts/
  kernel/
  workflows/job_search/
  workflows/resume_optimize/
examples/
  jobs.sample.jsonl
  resume.sample.md
```

V1 可放在同一 monorepo，但 `jobradar-core` 必须能被单独安装和测试。Web 迁移时允许旧模块暂时调用 Core；Core 不能反向 import `backend.app.routers`。

## 8. 本地数据契约

### 8.1 物理隔离

系统代码由 `uv tool` / `pipx` 管理；用户数据使用 XDG 路径，默认如下：

```text
~/.config/jobradar/config.toml
~/.local/share/jobradar/
  jobradar.db
  workspace/
    profile.json
    resumes/original/
    resumes/versions/
    jobs/imports/
    exports/
    runs/<run_id>/manifest.json
    runs/<run_id>/events.jsonl
  backups/
~/.cache/jobradar/
```

用户可通过 `JOBRADAR_HOME` 改写根目录。所有文件访问先经过 `WorkspacePort` 做路径归一和根目录约束，拒绝 `..`、符号链接逃逸和工作区外写入。

### 8.2 真相源选择

- 简历原件：用户文件是真相源，只读保存；
- 简历优化版本：版本文件是真相源，SQLite 保存索引和元数据；
- 岗位：标准化 SQLite 表是真相源，导入原始文件保留 provenance；
- Memory、收藏、排除和 Run：SQLite 是结构化真相源；
- Run Manifest / events：每次完成后导出为可检查 JSON/JSONL；
- 搜索 FTS、embedding 和派生摘要：均可删除重建。

不照搬“所有状态都用 Markdown”，因为 JobRadar 的岗位数据量、过滤维度和迁移需求更适合数据库；但用户拥有可导出、可备份的数据副本。

### 8.3 升级规则

1. 安装包更新不得直接遍历或修改用户文档；
2. DB schema 迁移前创建带版本号的备份；
3. 迁移失败自动回滚并保留旧版本；
4. `jobradar doctor --data-contract` 检查路径、权限、schema 和备份；
5. CI 必须从至少两个历史 schema 升级并验证哈希不变的原始简历；
6. 模型 Provider、数据同步和遥测均不能在升级时自动启用。

## 9. Career Runtime

### 9.1 不做无边界 Agent Loop

两个工作流都有明确状态机：

```text
job_search:
  intake → normalize_query → retrieve → rank → inspect → shortlist → complete

resume_optimize:
  intake → parse → confirm_contract → bind_job → diagnose
  → propose_patch → user_review → verify → export → complete
```

模型不能自己发明新状态，也不能直接调用数据库或文件系统。Workflow 决定下一步允许哪些 Capability；每个调用有预算、超时、幂等键和结构化结果。

### 9.2 Capability 清单

| Capability | 类型 | 约束 |
| --- | --- | --- |
| `search_jobs` | 确定性 | 只读；返回真实 `job_id` 和 feature breakdown |
| `inspect_jobs` | 确定性 | 每次最多 10 个真实 `job_id` |
| `compare_jobs` | 模型可选 | 输入必须来自本 Run 的候选池 |
| `parse_resume` | 确定性/模型 | 文件必须在 workspace；保留原文定位 |
| `recall_candidate_memory` | 确定性 | 按 Purpose、Scope 和 L0-L3 上限披露 |
| `diagnose_resume` | 模型 | 只能引用 Run Snapshot 的 JD 和证据 |
| `propose_resume_patch` | 模型 | 输出结构化 patch，不直接写文件 |
| `verify_resume_patch` | 确定性 + 模型审计 | 无依据的新事实必须阻断或降级 |
| `export_resume_version` | 写操作 | 必须经过用户 approval，永不覆盖 original |

V1 不提供 `shell`、`browser`、`send_application` 或通用 `write_file`。

### 9.3 Run 与事件模型

```python
class Run:
    run_id: str
    workflow: str
    workflow_version: str
    state: str
    snapshot_hash: str
    status: str

class RunEvent:
    event_id: str
    run_id: str
    step: str
    event_type: str
    occurred_at: datetime
    duration_ms: int | None
    input_refs: list[str]
    output_refs: list[str]
    quality: str
    error_code: str | None
```

取消信号必须传到模型请求、解析 Worker 和导出任务。迟到结果通过 `run_id + revision + step_attempt` 围栏拒绝写入当前状态。

## 10. Context 与 Memory

### 10.1 三层 Context

#### Stable Prefix

- 求职事实不得编造；
- 来源、模型推断和用户事实的区分规则；
- 当前 workflow contract；
- Capability schema；
- 输出 schema、错误和降级协议；
- 引用与防编造规则。

该层随发布版本变化，不包含用户、时间戳、剩余预算或检索结果。

#### Run Snapshot

- 已确认 Candidate Contract；
- 当前简历版本和 hash；
- 目标 JD、`job_id` 和 hash；
- 搜索条件或本次优化目标；
- workflow、rubric 和 prompt asset 版本；
- 本 Run 已确认的关键决策。

Run 中修改简历或 JD 必须产生新 revision，不能静默漂移。

#### Turn Dynamic

- 当前用户命令；
- 当前状态和允许的 Capability；
- 最近对话摘要；
- 本轮检索结果和工具 Observation；
- 剩余预算、超时和错误信息；
- 本轮按需展开的 Memory Detail/Evidence。

### 10.2 L0-L3 渐进披露

| 层 | 内容 | 两个工作流中的用途 |
| --- | --- | --- |
| L0 Contract | 已确认目标、地点、岗位方向、硬限制和最低事实 | 搜索硬过滤；Run 初始化 |
| L1 Index | Memory 摘要、类别、状态、Record ID、是否有详情 | 判断要不要展开，不默认全部进模型 |
| L2 Detail | 经历、技能、偏好、STAR Hook、关联岗位和字段路径 | 排序解释、JD 对齐、改写选材 |
| L3 Evidence | 原文摘录、来源、简历字段位置、确认记录 | 防编造、patch 验证和用户解释 |

Memory 采用统一事实存储，通过 `scope` 区分 `global`、`job_search`、`resume` 和 `run`，不为每个页面复制一套数据库。模型产生的 Candidate Claim 先进入 staged 状态，本轮不能把它重新当成已确认事实；用户确认后才可进入 Active Memory。

### 10.3 Context Manifest

每次模型调用都记录不含正文的 Manifest：

```json
{
  "stable_prefix_hash": "...",
  "run_snapshot_hash": "...",
  "purpose": "resume.patch",
  "blocks": [
    {"type": "jd", "source_id": "job:123", "tokens": 830},
    {"type": "memory_l3", "source_id": "mem:42", "tokens": 120}
  ],
  "dropped": [{"source_id": "mem:18", "reason": "token_budget"}]
}
```

它回答“这次模型看到了什么来源和版本”，但不把用户隐私重复写进日志。

## 11. 岗位检索实现

### 11.1 数据导入接口

```python
class JobSourcePort(Protocol):
    source_id: str
    def sync(self, cursor: str | None) -> SyncBatch: ...

class JobImportPort(Protocol):
    def inspect(self, path: Path) -> ImportPlan: ...
    def commit(self, plan_id: str) -> ImportResult: ...
```

第一版内置：

- JSONL / JSON / CSV 导入；
- JobRadar SQLite 兼容导入；
- 一个公开 ATS fixture adapter 作为扩展示例；
- 样例岗位数据用于离线首跑。

生产库和受限语料不打包。公开来源同步必须显示来源、频率、上次成功时间和条款提示；遇到登录、验证码或封禁直接停止，不绕过限制。

### 11.2 检索与排序

V1 使用可解释的两阶段方式：

1. 硬过滤与召回：地点、阶段、方向、状态、日期 + FTS5；
2. 排序：文本相关度、方向匹配、地点偏好、时效、质量先验和用户状态。

每个结果返回：

```json
{
  "job_id": "...",
  "score": 0.82,
  "reasons": ["命中 AI Agent 后端方向", "地点符合上海偏好"],
  "risks": ["发布日期超过 30 天"],
  "features": {"text": 0.31, "track": 0.25, "location": 0.15}
}
```

`score` 只表示当前排序相关性，界面禁止写成“录用概率”或“成功率”。

### 11.3 与现有代码的关系

优先复用并迁移：

- `services/resume_copilot/recommend_search.py` 的纯规则召回和质量先验；
- `services/phase_g/recommendation_v2` 的 recall / scoring；
- `models.Job` 的标准字段和 taxonomy；
- 现有 `search_candidates`、`inspect_jobs` 的真实 ID 围栏。

需要拆除的耦合：SQLAlchemy Web Session、`app.config` 全局环境、前端 DTO、SAIF 专属策展常量和生产数据库假设。迁移时先写 characterization tests，保证同一 fixture 的 Top-K 和理由不发生无意变化。

## 12. 简历优化实现

### 12.1 事实模型

解析结果至少保存：

- section 和 bullet 的稳定 ID；
- 原文、页码/段落或字符范围；
- 公司、角色、时间、技能和结果；
- `source_hash`；
- 用户确认状态；
- 解析质量和缺失项。

PDF 不承诺字级坐标；能稳定提供页码和段落就不伪装成更高精度。

### 12.2 Patch 模型

```python
class ResumePatch:
    patch_id: str
    target_block_id: str
    operation: Literal["replace", "insert_after", "delete"]
    before: str
    after: str
    intent: Literal["wording", "structure", "fact_needed"]
    evidence_refs: list[str]
    risk_flags: list[str]
    status: Literal["proposed", "accepted", "edited", "rejected", "blocked"]
```

`fact_needed` 只能向用户提问，不可被一键接受。`wording` 和 `structure` 也必须经过 Verify，确认没有偷偷改变职责范围、技能熟练度、量化结果或时间关系。

### 12.3 复用与迁移

优先复用：

- `resume_copilot/parser.py` 的 PDF/DOCX 解析与 Provider 接口；
- `resume_copilot/chat.py` 的 rewrite option 和一键应用语义；
- `account_memory` 的 provenance、confirmation、supersession 和字段关联；
- `llm_context` Providers 的 purpose-aware 取数思想。

不直接搬运当前“各模块拼大 system prompt”的实现。TUI 首先落地 Context Compiler，再让 Web 逐步迁移到同一 Core。

## 13. 配置与模型

配置文件示例：

```toml
[workspace]
path = "~/.local/share/jobradar/workspace"

[model]
provider = "openai_compatible"
base_url = "http://127.0.0.1:11434/v1"
model = "qwen3:8b"
api_key_env = "JOBRADAR_LLM_API_KEY"
timeout_seconds = 60

[privacy]
telemetry = false
persist_prompt_bodies = false
allow_remote_model = false

[jobs]
max_results = 100
stale_after_days = 45
```

API Key 只从环境变量或系统 keyring 读取，不写入 `config.toml`。首次启用远程模型时显示：将发送哪些简历/JD 内容、发送给哪个 endpoint、是否继续。不同 endpoint 的 consent 分开记录。

`jobradar doctor` 检查：

- Python 与终端能力；
- 工作区权限和磁盘空间；
- SQLite FTS5；
- PDF/DOCX parser；
- 模型 endpoint 和结构化输出；
- schema 版本和备份；
- 可选数据源连通性。

## 14. 错误、降级与安全

### 14.1 降级原则

- LLM 不可用：岗位检索照常；简历页保留本地关键词覆盖和结构检查；
- PDF 解析失败：提示转 DOCX/Markdown，不吞掉原文件；
- 数据源同步失败：保留上次成功快照并标记 stale；
- FTS5 不可用：降级到字段过滤和受限 `LIKE`，明确性能下降；
- Memory 召回失败：使用 L0 + 当前简历，标记本次未使用长期记忆；
- 模型结构错误：一次 schema repair，仍失败则保存 Run 并允许重试；
- 导出失败：不改变已接受 patch 状态，允许单独重试导出。

### 14.2 安全边界

- 所有工具是 allowlist Capability；
- URL 只允许 `http/https`，阻断 `file://` 和内网地址抓取；
- 导入文件限制类型、大小和压缩展开量；
- Prompt 中的 JD、简历和岗位正文一律视为不可信数据，不可覆盖系统规则；
- 日志做字段级脱敏；
- 每次远程调用记录 endpoint、purpose、字节数和 consent，不记录 API Key；
- `jobradar export-data` 和 `jobradar delete-data` 提供完整的数据可携带与删除能力。

## 15. 开源与发布前置条件

当前 JobRadar 根仓库没有 `LICENSE`，因此严格来说还不能被外部合法地复制、修改和分发。公开 TUI GA 前必须完成：

1. 选择代码许可证，建议评估 Apache-2.0；
2. 岗位数据、样例数据和代码许可证分开声明；
3. 增加 `SECURITY.md`、`CONTRIBUTING.md` 和隐私说明；
4. 审计第三方 parser、模型 SDK、字体和样例数据许可证；
5. 清理生产域名、私有 endpoint、真实用户数据和密钥历史；
6. 明确产品只提供辅助决策，不承诺求职结果；
7. 对公开来源同步写明 ToS、robots、频率和退出机制。

许可证由项目所有者最终确认，实施阶段不能擅自替项目选择。

## 16. 非功能指标

| 指标 | Alpha 目标 |
| --- | --- |
| 安装到样例搜索 | 5 分钟内 |
| Warm startup | P95 < 2 秒 |
| 50k 岗位本地搜索 | P95 < 300 ms |
| TUI 键盘交互反馈 | P95 < 100 ms |
| Run step 可追踪率 | 100% |
| 原始简历被覆盖 | 0 次 |
| 库外 job_id 进入结果 | 0 次 |
| 无证据新增具体事实进入可采纳 patch | 0 次 |
| 无授权网络请求 | 0 次 |
| 升级后用户数据哈希变化 | 0 个 |

模型生成耗时由 endpoint 决定，不对第三方模型延迟做虚假 SLA；产品只统计自身排队、Context 构建和后处理耗时。

## 17. 实施阶段

### Phase 0：开源边界与可发布基线

交付：

- License 决策记录；
- `OPEN_SOURCE_BOUNDARY.md` 与 `DATA_CONTRACT.md`；
- 私有数据和密钥扫描；
- 样例简历、样例岗位与来源声明；
- CI 的 user-data / secret guard。

验收：干净 clone 不含生产 DB、XHS 私有语料、音频或真实简历；外部用户能明确知道什么可用、什么未开放。

### Phase 1：抽取 Career Core

交付：

- `jobradar-core` package；
- Job / Resume / Run / Context / Memory contracts；
- Repository、Workspace、LLM、Clock ports；
- 从现有召回和简历解析建立 characterization fixtures；
- Web adapter 暂时桥接 Core，避免双份逻辑。

验收：Core 单测不启动 FastAPI，不 import router，不需要生产 env；同一 fixture 的召回 Top-K、parser 和 patch contract 稳定。

### Phase 2：岗位检索 Vertical Slice

交付：

- `init`、`doctor` 和基础 TUI shell；
- Job importer、SQLite schema、FTS5；
- Jobs 页面、详情、收藏、排除；
- rule-based reasons 和搜索 Run trace；
- 样例数据的完全离线体验。

验收：无 API Key、断网条件下，从安装到完成搜索、查看详情和收藏全链路通过。

### Phase 3：简历优化 Vertical Slice

交付：

- PDF/DOCX/Markdown ingest；
- Candidate Contract 确认；
- 目标 JD 绑定和 Run Snapshot；
- diagnosis、patch review、Verify 和 Markdown/JSON export；
- 远程模型 consent 与 Ollama 示例配置。

验收：至少 20 组简历/JD fixture 跑通；所有具体新增事实有 Evidence Ref；原件哈希保持不变。

### Phase 4：Context、Memory 与可观测性

交付：

- Stable Prefix / Run Snapshot / Turn Dynamic Compiler；
- L0-L3 Memory Resolver；
- Context Manifest；
- Runs 页面、取消、重试、迟到结果围栏；
- token budget 和敏感字段日志检查。

验收：相同输入与版本生成相同 snapshot hash；用户能看到步骤和来源；不展示 chain-of-thought。

### Phase 5：打包、兼容与 Alpha 发布

交付：

- PyPI wheel 和 `uv tool` / `pipx` 安装说明；
- Linux、macOS、Windows CI；
- schema upgrade / rollback 测试；
- `jobradar export-data` / `delete-data`；
- README demo、真实终端录屏和故障排查文档；
- `v0.1.0-alpha` release notes。

验收：三平台 clean install；升级不改用户数据；README 中 5 分钟路径由新用户盲测通过。

## 18. 建议 PR 顺序

1. `docs(oss): define license, boundary and local data contract`
2. `refactor(core): add framework-independent contracts and ports`
3. `refactor(jobs): move deterministic recall behind JobRepository`
4. `feat(cli): add init and doctor commands`
5. `feat(tui): ship offline job search vertical slice`
6. `refactor(resume): move parser and evidence model into core`
7. `feat(resume): add grounded diagnosis and patch review`
8. `feat(context): compile stable, run and turn layers`
9. `feat(memory): add L0-L3 progressive disclosure`
10. `feat(runtime): expose run timeline, cancellation and fencing`
11. `chore(release): package, migrate, document and publish alpha`

每个 PR 必须保持 Web 产品可运行；禁止一边迁移、一边复制出第二套召回或 Memory 真相源。

## 19. 测试与验收矩阵

### 19.1 自动化

- Unit：query normalize、FTS、rank、patch verify、path sandbox、Context budget；
- Contract：OpenAI-compatible、Ollama、JobSource、Workspace、Repository；
- Golden：固定简历/JD 的 diagnosis 和 patch schema；
- Property：排序稳定性、库外 ID 拒绝、路径逃逸、原件不可写；
- Migration：历史 schema 到当前版本、失败回滚、用户文件 hash；
- TUI：Textual Pilot 测键盘、窄终端、取消、错误和离线状态；
- E2E：clean install → init → import → search → optimize → export；
- Security：secret scan、prompt injection fixture、恶意文档和 URL；
- Performance：50k/100k 岗位搜索与 TUI 滚动。

### 19.2 人工验收脚本

1. 在没有模型 Key 的新环境安装并完成岗位搜索；
2. 导入一份中文 PDF 简历并核对解析来源；
3. 连接 Ollama，针对样例 JD 生成修改；
4. 尝试采纳一个无依据数字，确认被阻断为 `fact_needed`；
5. 中途取消模型请求，确认没有迟到结果污染下一次 Run；
6. 升级版本，确认原始简历、收藏和 Memory 哈希不变；
7. 关闭网络后重新打开，确认历史结果和本地搜索可用；
8. 导出并删除全部本地数据，确认行为可解释且完整。

## 20. Definition of Done

`v0.1.0-alpha` 只有同时满足以下条件才算完成：

- 用户通过一个安装命令和一个初始化命令进入产品；
- 岗位检索无 LLM 可用，结果全部来自真实本地 `job_id`；
- 简历优化只产生可审阅 patch，原件永不覆盖；
- 每个可采纳的具体事实有证据；
- Context 三层和 Memory L0-L3 在真实调用中生效，不只存在于文档；
- Run 步骤、失败、降级、取消和引用可见；
- 用户数据与系统升级通过自动化契约隔离；
- 默认无遥测、无未授权联网、无自动投递；
- 根仓库具有明确许可证和数据边界；
- 三平台 clean install 与 E2E 验收通过。

## 21. 最终产品叙事

career-ops 证明了“求职 Agent 可以作为用户拥有的本地工作空间”这条交付路线。JobRadar 在此基础上进一步做三项取舍：

1. **不把 Coding Agent 当产品运行时**，而是提供安全、可测试的 Career Runtime；
2. **不把所有状态文件化**，而是让 SQLite 服务于大规模岗位检索，同时保留可导出的用户资产；
3. **不追求功能数量**，先把岗位检索与证据化简历优化做成两个完整、可信的工作流。

因此，这个 TUI 不是现有网页的终端皮肤，也不是缩小版 Claude Code。它是 JobRadar Agent 架构的第一个可独立分发宿主：数据在本地，步骤可观察，模型可替换，结果有证据，人保留最终决定权。
