# OpenClaw → OpenCode 架构迁移设计

## 目标

将项目上下文包从 OpenClaw multi-agent 架构迁移到 OpenCode 单会话架构。保留业务知识，删除 OpenClaw 特有的 agent 调度概念，将所有上下文文件整合到 worktree 项目内部。

## 背景

当前状态：
- `/home/ubuntu/.config/opencode/project-a-context/` 存放从 OpenClaw 迁出的结构化上下文包（boundary/ memory/ skills/ playbooks/ config/ services/ docs/ data-model/ scripts/）
- `/home/ubuntu/opencode-worktrees/jobrador-edit/` 是实际的 JobRadar 项目代码
- 上下文包包含 OpenClaw 特有的 SOUL/IDENTITY/HEARTBEAT/memory 等机制，不适用于 OpenCode
- 项目已有 `config.yaml`(628行)、`docs/site_playbooks/`、`docs/plans/` 等

## 文件处置

### 删除（OpenClaw 特有）

| 文件 | 原因 |
|------|------|
| `boundary/SOUL.md` | AI 灵魂定义，OpenCode 不需要 |
| `boundary/IDENTITY.md` | Agent 身份定义，OpenCode 不需要 |
| `boundary/HEARTBEAT.md` | 心跳机制，OpenCode 不需要 |
| `boundary/USER.md` | 用户定义，不适用 |
| `boundary/PATHS.md` | OpenClaw workspace 路径，需重写 |
| `boundary/workspace_structure.md` | OpenClaw workspace 结构，需重写 |
| `boundary/config.yaml` | 业务配置已存在于项目根目录 config.yaml |
| `skills/SKILL.md` | 合并到 AGENTS.md 后删除 |
| 整个 `boundary/` 目录 | 清空后删除 |

### 迁移到项目内

| 源 | 目标 | 处理方式 |
|----|------|---------|
| `boundary/AGENTS.md` + `skills/SKILL.md` | 根目录 `AGENTS.md` | 清理 OpenClaw 调度概念，保留爬虫规则和工作流，合并 skill 内容 |
| `boundary/TOOLS.md` | `docs/tools-and-paths.md` | 更新路径为实际项目路径 |
| `boundary/MEMORY.md` | `docs/decisions.md` | 保留关键长期决策记录 |
| `playbooks/` (10文件) | `docs/playbooks/` | 直接复制（项目内已有 `docs/site_playbooks/`，需去重） |
| `memory/` (14文件) | `docs/memory/` | 精简保留关键日志 |
| `config/` (9文件) | `docs/config-reference/` | 作为配置参考保留 |
| `docs/plans/` | 合并到 `docs/plans/` | 去重合并 |
| `docs/CRAWL_PLAN.md` 等 | `docs/` | 去重合并 |

### 不迁移（项目已有或仅作参考）

| 源 | 原因 |
|----|------|
| `services/` (89文件) | 项目已有 `backend/app/services/`，上下文包的 services 作为参考 |
| `data-model/` (4文件) | 项目已有 `backend/app/models/` |
| `scripts/` (36文件) | 项目已有 `scripts/` |
| `README.md` + `MANIFEST.txt` | 上下文包元数据 |

## AGENTS.md 内容设计

### 保留内容

1. **爬虫核心原则**：合法边界、优先官方站、优先结构化数据、尊重反爬
2. **提取优先级**：Public API > Embedded payload > Stable HTML > Playwright
3. **ATS 家族识别 + adapter 模式**：Greenhouse/Lever/Workday/Moka/北森等
4. **分层探测（Layer 0-4）**：静态探测 → API → 轻量交互 → 重型抓取 → 保底
5. **六步标准爬取流程**：探测 → API → 混合模式 → 页面高召回 → 结果校验 → 失败归因
6. **真假 0 判断 + completeness score**：confirmed zero vs suspect zero
7. **轻量证据收集 + 标准失败标签**：11 种 FailureReason 枚举
8. **文档更新规则**：站点经验 → playbooks，高层说明 → docs
9. **Source of truth 优先级**：后端模型 > crawler 代码 > config > docs > 记忆
10. **站点 playbooks 索引**：指向 docs/playbooks/

### 删除内容

- OpenClaw agent 调度概念（main / project-a / project-b）
- Executor contract
- bank_queue.json 队列调度规则
- 飞书触发识别规则
- Skill 安全审查流程
- 多层模型架构（GLM-4.7 / Sonnet / GPT-5）
- memory 写入规则
- cron 调度规则
- 咨询公司飞书多维表格查询规则（保留为业务参考但不作为 agent 触发规则）
- 路径规则（迁移到 docs/tools-and-paths.md）

## 迁移后结构

```
jobrador-edit/
├── AGENTS.md                         # 项目规则
├── README.md                         # 已有
├── config.yaml                       # 已有
├── backend/
├── frontend/
├── docs/
│   ├── playbooks/                    # 站点攻略（从 playbooks/ 迁入，去重已有 site_playbooks）
│   ├── memory/                       # 精简运行日志
│   ├── decisions.md                  # 长期决策记录
│   ├── tools-and-paths.md            # 工具和路径约定
│   ├── config-reference/             # 配置参考
│   ├── plans/                        # 已有 + 合并
│   ├── site_playbooks/               # 已有，与 playbooks 去重
│   ├── CRAWL_PLAN.md                 # 已有
│   ├── JOB_INTEL_SYSTEM_DESIGN.md    # 已有
│   └── PROGRESS.md                   # 已有
├── scripts/
├── tools/
└── .opencode/
```

## 实施步骤

1. 创建目录结构（docs/playbooks/ docs/memory/ docs/config-reference/）
2. 编写新 AGENTS.md（从 boundary/AGENTS.md + skills/SKILL.md 合并）
3. 迁移 TOOLS.md → docs/tools-and-paths.md（更新路径）
4. 迁移 MEMORY.md → docs/decisions.md（精简决策记录）
5. 迁移 playbooks/ → docs/playbooks/（与已有 site_playbooks/ 去重）
6. 迁移 memory/ → docs/memory/（精简保留）
7. 迁移 config/ → docs/config-reference/
8. 合并 docs/plans/ 中的差异文件
9. 清理上下文包目录（.project-a-context/ 和 project-a-context）
10. 更新 OPENCODE_START.md 反映新结构

## 验证

- `git status` 确认所有文件变更
- 阅读 AGENTS.md 确认无 OpenClaw 概念残留
- 确认 docs/ 下无重复文件
- 确认项目可正常运行（前后端不受影响）
