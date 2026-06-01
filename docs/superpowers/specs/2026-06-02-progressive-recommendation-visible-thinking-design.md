# 渐进式推荐 + 看得见的思考 — 设计文档

> 日期：2026-06-02 · 会话：网站设计-devvpstmux · 模块：Resume Copilot 工作台（左栏推荐 + coach 对话）
> 状态：设计已与产品 owner 逐段确认，待 review → 转实施计划

## 1. 为什么做（背景与目标）

### 痛点
学生在工作台触发推荐生成后，**盯着一个不透明的转圈**等 1–2 分钟，期间什么都看不到；coach 改写/答疑也是发问后干等、一次性蹦出结果。体验上像"DeepSeek 套壳"——而 SAIF 学院**明确对套壳产品脱敏**，要的是"看得见的、可证伪的反馈"。

### 目标
把"等待"变成"看得见 AI 在为你动脑子"：
1. **推荐生成**：规则排序的岗位列表**秒级先出**，强模型的精排/理由**算好一条补一条**；同时一条**思考时间线**逐节点亮起，关键步骤**挂出强模型的真实推理**。
2. **对话 coach**：把 DeepSeek 强模型的**思考过程实时打字**给学生看（最终结构化建议想完整段落地）。

这两件事**本身就是产品差异化**（真推理 = 反套壳的硬货），不是装饰。

### 非目标（本期不做）
- 后端推荐生成的**深层提速**：rerank/narrative 的并行化、medium 档位、快速失败回落**已在上一轮完成**（H1–H3）。本期后端改动只新增"规则列表先落地 + 结构化进度节点"，不重做并行框架。
- 推荐结果本身的算法/打分口径不变。
- 语音、面试链路不动。

## 2. 总体架构：一个概念，两个落点

```
            ┌──────────────────── 看得见的思考（统一概念）────────────────────┐
            │                                                                  │
  落点①  推荐生成（渐进式 + 进度节点）            落点②  对话 coach（实时打字机）
  ─────────────────────────────────             ──────────────────────────────
  复用现有 1.6s 轮询                              新增 SSE 流式通道
  后端：规则列表先落地 + 结构化阶段节点            后端：流式推理 + 最终结构化结果两类事件
  关键节点挂强模型一句真推理                       前端：思考气泡实时打字、想完收起、正文整段
  岗位卡逐条升级（精排完一个覆盖一个）             默认思考时展开 / 完成自动收起
  完成后时间线收成一行"✓ 已完成·用时 Ns·可展开"
```

**共用手势**：思考过程默认可见，完成后**收起成一行、可展开复盘**（学生/老师事后可证伪）。两个落点**独立上线、独立验收**，①先②后——①复用现有底座、风险低，SAIF 演示先到位就已有"看得见在动脑子"的效果。

## 3. 现有可复用底座（核对过，非从零造）

| 底座 | 位置 | 现状 |
|---|---|---|
| 推荐运行过程日志 | `ResumeRecommendationRun.agent_trace_json` | 生成中**增量写入**；`_append_agent_trace()` 已在 workflow 内逐步调用 |
| 推荐部分结果 | `ResumeRecommendationRun.recommendations_json` | 跑到一半**先写一批**、`recommendation_status` 仍保持 `running` |
| 过程节点数据结构 | `ResumeAgentTraceItem` = `{agent, message, status, tool?, step_index?, result_summary?}` | 前端已有同名 type |
| 前端思考面板 | `AgentThinkingPanel`（`public-resume-copilot.tsx` ~L446） | 已渲染 agent_trace，含转圈→✓、工具图标、结果摘要、两种渲染模式 |
| 后端并行底座 | `rerank_top_n`（8 并发）/ narrative（6 并发）/ medium / `max_retries=0` | H1–H3 已完成 |
| coach 对话接口 | `POST /sessions/{id}/chat` → 单个 `ResumeCopilotMessageOut`，`chat.py` 有 `_try_parse_chat_json` | 一次性返回，**无流式、无 reasoning 接出** |
| 骨架接口 | `GET /sessions/{id}/platforms-by-tier` | 缓存优先，实测 **19ms** 返回 |

结论：落点①是"在已有底座上加三处"；落点②要新增流式通道。

## 4. 落点① 推荐渐进式 + 进度节点

### 4.1 学生眼里的分镜
```
t=0.x 秒   "已从你的赛道召回 N 个对口岗" —— 规则排序列表【立刻铺出来】
           卡片先有：公司·岗位·初步匹配分；理由位显"强模型精排中…"占位
t+         思考时间线逐节点亮起：
           ✓ 召回岗位池（公募权益研究员 · 命中 21）
           ✓ 三维匹配打分（赛道/梯队/经历）
           ⟳ 强模型精排  3/10 …       ← 计数实时跳
               └ 挂一句真推理："中信研究所实习直接对口头部公募推票能力要求"
           ⟳ 生成推荐理由 2/6 …
t+         岗位卡【逐条升级】：每精排完一个，重新排位 + 补上 4 段式理由
完成        时间线收起成一行"✓ 已完成 · 用时 38s · 点开看推理"，列表定稿
```

### 4.2 三处升级

**升级 A — 后端：规则排序结果提早落地**
- 现状：LLM 全跑完才写 `recommendations_json`。
- 改为：base 规则排序一拿到，**先写入** `recommendations_json`（每条带初步分、`reason` 留空占位标志），`recommendation_status='running'`；随后 rerank/narrative 每完成一条**覆盖更新**对应条目。
- 前端轮询本就会拿到部分结果——左栏要改成"有 items 就先渲染"（见升级 C）。

**升级 B — 后端：过程日志升级成结构化阶段节点**
- 沿用 `_append_agent_trace` + `ResumeAgentTraceItem`，发出固定阶段节点：
  - `recall`（召回，带命中数）
  - `score`（三维匹配打分）
  - `rerank`（强模型精排，`message` 带 `x/N` 进度，`result_summary` 挂**一句真推理**）
  - `narrative`（生成理由，带 `x/N`）
- **真推理来源**：从 `rerank_one` 的返回里接出一句话（精排理由的摘要），写进该节点 `result_summary`。当前 trace 没有这条，是本期要接的关键数据。
- 约束：保持 `_AGENT_TRACE_CAP`（不撑爆 JSON）；每条节点 `step_index` 单调递增，前端按 `step_index` 去重（已有逻辑）。

**升级 C — 前端：思考面板搬进左栏 + 工作台调性 + 列表渐进**
- 左栏当前在 `sessionReady` 之前只显示一个 spinner（`"正在结合你的赛道…生成第一批岗位"`）。改为：**只要 `recommendations.items` 非空就渲染列表**（含占位理由的卡片），上方嵌入思考时间线。
- 复用 `AgentThinkingPanel` 的**逻辑**（step 去重、running/completed、result_summary），但**重绘为 terracotta 工作台风格**（现面板是 slate/blue，落在别处）。放在左栏推荐列表上方。
- 完成后**收起成一行可展开**（本期已确认的手势）。

### 4.3 数据流（落点①）
```
确认偏好 → POST /generate (202, 后台任务)
后台 workflow:
  1. recall + 规则排序 → 立即写 recommendations_json(占位理由) + trace:recall✓/score✓
  2. rerank_top_n(并行) → 每完成一条:覆盖该条目 + trace:rerank(x/N, 一句真推理)
  3. narrative(并行)    → 每完成一条:补 reason + trace:narrative(x/N)
  4. 收尾 → status=completed
前端(复用现有 1.6s 轮询):
  每轮 GET /recommendations → 拿到部分 items + agent_trace
  → 列表渐进渲染 + 思考时间线推进；status=completed 时定稿、时间线收起
```

## 5. 落点② 对话 coach 实时打字机

### 5.1 体验
```
学生：帮我把这段实习改得更贴头部公募
coach ⟳ 正在思考…
      ┌ 💭 这段经历的关键是"推票逻辑"，头部公募面试重点考察行情判断…  ← reasoning 实时打字
      │    学生原文只写了数据处理，没体现观点输出，需要往…
      └ ✓ 想完了（点可收起这段思考）
      【改写建议正文】—— 严格结构化，等想完整段落地
```

### 5.2 关键约束（先说清的预期）
coach 最终答案是**严格结构化**的（改写分段、`_detect_fabricated_numbers()` 防编造数字契约不能破），结构化内容**不能**逐字拼显。因此：
- **思考过程（reasoning_content）实时打字** —— 这就是"看着它想"；
- **最终建议想完后整段渲染**（保持现有 JSON 契约与校验）。

### 5.3 改造
1. **后端新增流式接口**（如 `POST /sessions/{id}/chat/stream`，SSE / `text/event-stream`），事件两类：
   - `reasoning`：`{delta}` 推理增量
   - `answer`：`{message: ResumeCopilotMessageOut}` 最终结构化结果（沿用现有解析 + 防编造校验）
   - 失败/超时 → `error` 事件，前端回落到现有一次性接口。
2. **保留** 现有 `POST /chat` 一次性接口（兜底 + `apply-rewrite` 不需流式）。
3. **前端**：聊天消息渲染"思考气泡（实时打字，**默认展开**，想完**自动收起**可再展开）+ 正文"。用 fetch streaming / EventSource 消费。
4. **依赖确认**：coach 必须走会吐 `reasoning_content` 的**强模型（reasoner）**；线上 nginx 对该路由**关闭 proxy 缓冲**（否则字会一坨一坨而非流出）。

## 6. 组件边界一览

| 单元 | 职责 | 依赖 | 接口 |
|---|---|---|---|
| `workflow.py`（改） | 规则结果提早写库 + 发结构化阶段节点 | `_append_agent_trace`、rerank/narrative 返回 | 写 `recommendations_json` / `agent_trace_json` |
| `rerank_one`（小改） | 返回里多带"一句话精排理由"供节点摘要 | — | 返回结构 +1 字段 |
| 左栏 `LeftRecommendRail`（改） | items 非空即渐进渲染 + 内嵌思考时间线 | 现有轮询数据 | props 不变 |
| `WorkspaceThinkingTimeline`（新，前端） | 工作台调性的思考时间线（复用 AgentThinkingPanel 逻辑） | `agent_trace` | `{trace, running}` |
| `chat_stream` 路由（新，后端） | SSE 流式：reasoning 增量 + 最终结果 | reasoner、`chat.py` 解析与防编造 | `POST /chat/stream` |
| 聊天消息组件（改，前端） | 思考气泡实时打字 + 折叠 + 正文 | 流式消费 | — |

## 7. 错误处理
- **落点①**：任一 LLM 节点失败 → 该岗位回落规则分/占位理由（已有快速失败回落），节点标 `failed` 但**不阻断**整条流水线；列表照常定稿。轮询拿不到结果 → 维持现有"give up"兜底。
- **落点②**：流断/超时/模型不吐 reasoning → 发 `error` 事件，前端**自动回落**到一次性 `POST /chat`，学生只是"看不到打字"，答案照常出。结构化解析失败/检出编造数字 → 沿用现有 warning 暴露，不剥离。

## 8. 测试 / 验收
- **落点①**
  - 单测：workflow 在 rerank 前写出含占位理由的部分结果；trace 节点 `step_index` 单调、`rerank` 节点带非空 `result_summary`。
  - 端到端：触发一次生成，**确认规则列表 < 3s 出现**，时间线逐节点推进，岗位卡逐条补上理由，完成收起一行。
  - 回归：`pytest tests/phase_g/` 绿；前端 `lint` 0 error + `build` 通过。
- **落点②**
  - 端到端：发一条改写请求，**思考气泡实时逐行打字**，想完收起、正文整段且通过防编造校验。
  - 回落：模拟流断 → 自动走一次性接口、答案仍出。
  - 部署：nginx 该路由关缓冲后，curl 流式接口可见**分块 flush**（非一次性）。

## 9. 上线顺序
1. 落点①（后端两改 + 前端左栏渐进 + 时间线组件）→ dev 验收 → 部署（仅前端 + 后端，**不碰 DB 数据**，走 `jobradar-vps-deploy`）。
2. 落点②（SSE 接口 + 前端流式 + nginx 关缓冲）→ dev 验收 → 部署。

## 10. 待确认/风险
- coach 当前实际走的模型是否已是 reasoner（出 `reasoning_content`）——实施第一步先确认，否则落点②要先切模型。
- SSE 经 SSH 隧道在 dev 调试可能不稳；dev 用生产构建 + 直连 :3001 验证，线上以 nginx 关缓冲为准。
- `agent_trace_json` 体积：阶段节点 + 每条精排一句推理，需确认不超 `_AGENT_TRACE_CAP`，必要时只保留最近 N 条 + 汇总。
