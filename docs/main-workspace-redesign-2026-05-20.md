# 主工作台交互重构设计 — 2026-05-20

> Brainstorm 产物：31 个产品决策 + 工程任务拆分。
> 范围：Resume Copilot Web (`resume-copilot-web/`) 主工作台 `/resume-copilot` 路由 + 配套 backend API。
> 不在范围：admin frontend (`frontend/`)、爬虫、面试系统。
> 决策方法：用户主导 brainstorm，每一步问"学生看到什么 / 体感如何 / 代价是什么"，用户选定。

---

## 0. TL;DR

主工作台从当前"信息纵向堆叠 + 各模块孤岛"重构为：

- **三栏 sticky 布局** + 顶部赛道 bar，所有信息一屏可见
- **5 个子系统**围绕一份 `account_memory` 闭环：档案 / plan-mode / 推荐 / 改写 / 赛道
- **memory bug 修复** (打 flag + 暴露 API + UI 接通) 是闭环前置条件
- **snapshot 系统彻底删除** —— 维护成本/价值失衡，留 dormant 代码污染心智
- **改写引入 thesis layer** (v0 原文 / v1 STAR / v2 thesis-aware)，并守住"不编数字"红线

---

## 0.5 执行决策 & 策略（2026-05-20 晚定稿）

> 这一节是最终拍板的执行方案。后续 §1–§8 是 brainstorm 原始记录，保留作为决策溯源。

### 决策记录

1. **简化版 31 → 20 决策**：brainstorm 结束后用户担心 UI 太复杂会迷路，做了一轮删 / 简化讨论。20 个保留决策清单见 §0.6。

2. **布局走向：1B（坚持 brainstorm 单页闭环）**：HiFi 设计包（Claude Design handoff bundle）走的是多页结构（Workspace + Results 分两页）。用户最终决定**坚持 brainstorm 的单页三栏闭环**：所有 5 个 surface（推荐 / chat / 简历 / 档案 / 赛道）一屏可见。
   - 收益：E-4 即时柔和重排动画保留（采纳改写 → 左栏推荐当场动）、闭环视觉化
   - 代价：HiFi 的 Results 页设计不直接复用；推荐左栏需要新设计

3. **HiFi tokens 引入**：复用 HiFi 设计包里的 tokens + primitives（保证视觉一致性）。
   - **Tokens**：`/tmp/design-package/jobradar/project/hifi-tokens.css`（terracotta `#c96442` + parchment `#f5f4ed` + Fraunces + Inter）
   - **Primitives**：`/tmp/design-package/jobradar/project/hifi-primitives.jsx`（HFBtn / HFPill / HFLogo / icon set）
   - 移植路径：复制到 `resume-copilot-web/components/hifi/tokens.css` + `hifi/primitives.tsx`，原本 `components/hifi/hifi-tokens.css`（项目已有）合并

4. **执行方式：subagent 驱动 + git worktree 并行 + 全自动测试**：所有 P0/P1 任务通过 subagent 并行执行，主 agent 编排 + 集成测试 + 合并。

---

### 0.6 20 个保留决策清单（删 8 / 简 6 / 留 14）

**🔪 砍掉 8 个**（v1 不做）：
| 决策 | 砍的理由 |
|---|---|
| A-3 ⭐ 重要标记 | 学生第一周不知道哪条是杀手锏，用熟了再加 |
| A-8 chat inline ✗ 撤回 | 从档案删 1 步够用 |
| A-9 老数据全量 migration | 现 prod 数据基数小，晚做 |
| B-5 plan-mode 折叠成 chat 卡片 | 默认时间排序够用 |
| C-4 永久改写历史 | 简化为"撤回最近一次" |
| D-1 ⚠ actionable weak signal bullet | 只展示 3 条 ✓ 强匹配 |
| ~~E-4 柔和重排动画~~ | ⚠️ **1B 选择后这条保留**（多页时才砍） |
| ~~E-5 顶部赛道 sticky bar~~ | ⚠️ **1B 选择后这条保留**（多页时才砍） |

**净砍 6 个**（A-3 / A-8 / A-9 / B-5 / C-4 / D-1）。

**🔧 简化 6 个**（功能保留但裁剪冗余）：
| 决策 | 简化方式 |
|---|---|
| A-2 entry 形态 | 摘要 + 一行原话（不拆 多字段） |
| A-4 智能 8 类抽取 | 简化为 3 类：经历 / 技能 / 偏好 |
| A-5 经历主其他次 | 简化为"经历放上面"（不折叠） |
| B-2 AI 推断梳理对象 | 直接列档案让学生选（砍 LLM 推断兜底）|
| C-1 三版改写 | 两版（v0 原文 + v2 thesis-aware），砍 v1 STAR |
| C-2 AI 卖点 batch | 学生 hover 选 1 条改（砍 batch N 条） |

**✅ 完整保留 14 个 + 简化保留 6 个 = 20 个最终决策**：

A-1 / A-2 简 / A-4 简 / A-5 简 / A-6 / A-7 / B-1 / B-3 / B-4 / C-1 简 / C-5 / C-6 / D-2 / D-3 / D-4 / D-5 / D-6 / E-1 / E-2 / E-3 / E-4 / E-5

（共 22 项但其中 E-4 + E-5 是 1B 决策后从"砍"反转为"留"，所以净 20 个核心动作）

---

### 0.7 Subagent 编排（Phase 0 → 4）

**Phase 0 — Foundation（1 个 subagent 顺序跑）** · 预计 0.5 天
- alembic migration: drop `JobIntelSnapshot` 表（D-4）
- 删 `quick_enrichment.py` + 清 `recommendation.py` 内 snapshot 逻辑 + 清 `workflow.py` enrich 阶段
- 打开 `UNIFIED_MEMORY_ENABLED` + `STUDENT_KB_ENABLED` flag
- 暴露 `GET/POST /api/resume-copilot/sessions/{id}/memory` endpoints
- legacy `student_experiences` → `account_memory` 一次性 backfill 脚本（A-9 虽然被砍但 backfill 1 次小工作量值得，避免 dev DB 上残留 legacy 数据）
- 验收：pytest 全绿 + curl 测 GET /memory 返回 schema 合理

**Phase 1 — Backend Parallel（3 subagent 并行 worktree）** · 预计 1.5 天
- **Subagent BE-1（memory backend）**：account_memory 抽取限制为 3 类（A-4 简）；新增 PATCH/DELETE entry endpoint（A-3 简，无 ⭐）
- **Subagent BE-2（rewrite + thesis）**：rewrite prompt 改成 v0/v2 两版输出（C-1 简）；接 `account_memory` 作为 input（thesis 来源）；保留 `_detect_fabricated_numbers` 红警告字段（C-5）
- **Subagent BE-3（recommend feedback）**：新 `POST /sessions/{id}/recommendations/{job_id}/reject` endpoint（D-2/D-3）；写回 `account_memory.preference`；推荐生成调用加 debounce 标记（D-5）；top10 + 50 分阈值（D-6）

**Phase 2 — Frontend Parallel（4 subagent 并行 worktree）** · 预计 3 天
- **Subagent FE-1（workspace shell + 三栏 + 赛道 bar + tokens 引入）**：
  - 把 HiFi `hifi-tokens.css` + `hifi-primitives.jsx` 移植到 `resume-copilot-web/components/hifi/`
  - 重构 `public-resume-copilot.tsx` 为 `<WorkspaceShell>` + `<TopTrackBar>` + 三栏子组件占位（E-1 / E-5）
- **Subagent FE-2（左栏推荐 + 反馈 + 动画）**：
  - `<RecommendRail>` 卡片可展开 + 两层分 + ✗反馈 inline 表单（E-2 / D-1 / D-2 / D-3）
  - FLIP 动画 1.5s 柔和重排（E-4 / D-5）
- **Subagent FE-3（右栏简历 + 改写 modal + inline diff + chat 出思考）**：
  - `<ResumePreview>` 右栏 + hover 出 ✏️ 改写按钮（C-6）
  - 改写时 chat 出思考 + 右栏 inline 显示 v0/v2 diff（E-3 / C-1）
  - 编造数字红警告（C-5）
- **Subagent FE-4（档案面板 + plan-mode UI）**：
  - 档案浮条 🟢 + 展开面板（A-1 / A-2 / A-5 / A-6 / A-7）
  - chat composer mode toggle `[💬 普通 │ 📌 plan-mode]`（B-1）
  - plan-mode 进入后 AI 列档案让学生选（B-2 简）
  - plan-mode 草稿 review 入档卡（B-3 / B-4）

**Phase 3 — 集成 / 测试 / 合并（主 agent 串行）** · 预计 0.5 天
- 合并所有 worktree，解决 conflict（重点：`public-resume-copilot.tsx` 多人改）
- `cd backend && PYTHONPATH=. .venv/bin/pytest tests/` 全绿
- `cd resume-copilot-web && npm run lint && npm run build` 全绿
- 端到端 smoke：跑一遍 §5 验收 checklist 的 6 条

**Phase 4 — 部署 dev VPS（主 agent + jobradar-vps-deploy skill）** · 预计 0.5 天
- 走标准 dev VPS 部署流程（不动 prod）
- VPS 上手动跑一遍 §5 checklist 确认

**总工作量预估**：~6 天（subagent 并行执行能压缩到 ~1-2 天 wall time）

---

### 0.8 执行风险与决断

| 风险 | 应对 |
|---|---|
| 多 subagent 改 `public-resume-copilot.tsx` 同一文件 → 合并 conflict 难解 | FE-1 先单独跑（拆完文件 + 占位）；FE-2/3/4 在拆好的子组件上分别工作 |
| backend migration 错误 → dev DB 损坏 | Phase 0 单 subagent 串行 + 跑后立刻 pytest |
| HiFi tokens 跟项目现有 `components/hifi/hifi-tokens.css` 冲突 | FE-1 检查现有 token，merge 而非 overwrite |
| brainstorm 决策实施时发现矛盾 | 主 agent 暂停并向 user 上报，不擅自决策 |
| prod VPS 误操作 | Phase 4 显式只推 dev VPS；prod 必须 user 单独 confirm |

### 0.9 单 commit 策略

整个重构走**一个 feature branch**，每个 subagent 在自己的 worktree 完成后产出**一个有意义的 commit**（不是 squash）。最后 PR-style 提交合并到 main 时保留所有 commits 的历史，便于后续 git blame 追溯到具体 subagent 的工作。

---

## 1. 工作台一屏全景

```
┌────────────────────────────────────────────────────────────┐
│ 🎯 当前赛道: 公募行研·买方基本面 / 适配度 6.2/10 [换赛道]   │ ← 顶部 sticky bar (E-5)
├──────────┬─────────────────────────┬───────────────────────┤
│ 📋 推荐    │  💬 chat / plan-mode    │  📄 简历预览           │
│ 卡片列表  │   主区 (↕滚动)          │  (改写时 inline diff) │
│ ⌄展开看   │                          │                       │
│  • 三层分 │   AI 思考浮出 (E-3)      │  hover 出 ✏️ 改写按钮  │
│  • 为什么 │                          │                       │
│  • ✗反馈  │  ──────────────────    │  ──────────────────  │
│ (sticky)  │  [💬 普通│📌 plan-mode]│ 📌 我的档案 🟢 (3)    │
│           │  [输入框 sticky 底部]   │ (收起浮条 → 点开展开) │
└──────────┴─────────────────────────┴───────────────────────┘
            ↑                                  ↑
    chat 出思考 + 右栏 diff 同步         档案: 经历主 / 其他次
    采纳后左栏 1.5s 柔和重排 (E-4)        新条目 🟢 小绿点提示
```

**5 surface 共用一份 `account_memory`**：chat / plan-mode 写 + 改 + 推荐 + 档案 全部 read/write 这一份 SSoT。

---

## 2. 5 个子系统的产品决策

### A — 我的档案 (account_memory 落地)

| # | 决策 | 学生体感 |
|---|---|---|
| A-1 | AI chat 回话末尾标「📝 已记入档案：X」+ 侧边"我的档案"面板**常驻**；新增条目在档案条上显示 🟢 小绿点（不再用"高亮闪整面板"） | 一眼可见 AI 记住了，不打扰聊天 |
| A-2 | entry 默认显示**摘要短句**，点开展开看结构化字段（动作/技术/数据/结果）+ 原话出处 | 扫读快，验证细节随时点开 |
| A-3 | 学生能**删** + **编辑字段** + **标 ⭐ 重要** | 完全掌控；⭐ 解锁下游优先用 |
| A-4 | AI **智能判断 8 类**（经历 / 技能 / 偏好 / 身份事实 / evidence / goal / commitment / weakness_signal），属于就抽 | 8 类信号都能记，偶尔抽错由 A-3 兜底 |
| A-5 | 面板内组织：**经历主、其他次**（经历区默认展开，技能/偏好/身份折叠在下） | 经历最显眼，其他类不丢失 |
| A-6 | 排序：⭐ 置顶 + 其余时间倒序 | 学生标的重要在最上 + 默认看新的 |
| A-7 | 第一次进档案，AI 用 parse 出的简历**自动填充**为初始条目 + 底部引导「让 AI 跟你聊聊每段经历」按钮（→ 触发 plan-mode） | 不空白 + 有动力深化，**B 的入口** |
| A-8 | chat 里「已记入」提示**旁边带 ✗ inline 撤回按钮** | 抽错当场否决，1 步操作 |
| A-9 | 老学生 legacy `student_experiences` 表里的内容**全量自动迁移**到新 `account_memory` | 升级无断层，老用户体感连续 |

---

### B — Plan-mode (chat 输入框 mode toggle)

| # | 决策 | 学生体感 |
|---|---|---|
| B-1 | chat 输入框上方**加 mode toggle**：`[💬 普通 │ 📌 plan-mode]`，像 Claude / Codex 那种切换风格 | 单一入口，发现成本零；不需要散落多处的按钮 |
| B-2 | 学生切到 📌 时 AI 第一反应：**优先从 chat 上下文推断**梳理哪段经历；推断不出**兜底列档案 entry 让学生选** | 智能 + 兜底，体验丝滑 |
| B-3 | plan-mode 结束方式：**AI 判断够了主动 wrap-up**（4 个 anchor 都补齐就收）+ **学生可随时切回普通提前停** | AI 智能收尾 + 学生兜底掌控 |
| B-4 | 结束后产出：AI 给「📝 加厚后的草稿」卡片，**学生 review → 确认入档**（不直接覆盖） | 1 条主条目入档，5 轮对话作为"原话出处"挂在条目下；档案不爆 |
| B-5 | plan-mode 的 5 轮对话**在 chat 历史折叠成单卡片**：「📌 梳理了：电价管道项目（5 轮）」点开看完整对话 | chat 历史清爽，梳理记录易找 |

---

### C — 简历改写 + thesis layer

| # | 决策 | 学生体感 |
|---|---|---|
| C-1 | 三版改写：**v0 原文** / **v1 合规化 STAR** / **v2 thesis-aware**（加你的独立判断 / 非共识 view）；v2 生成不出（无 memory 信号）时**显式提示**学生用 plan-mode 跟 AI 聊聊这段经历 | 学生看到「模板 → 个人化」演进 + 自然引导 B |
| C-2 | AI 改写粒度：**先用行业深度经验判断学生最佳卖点**（不是按 JD 字面匹配），**batch 推 2-3 条**改写建议（硬上限 3 条） | AI 从"字面匹配工"变成"卖点鉴赏家" |
| C-3 | 判断"最佳卖点"的信号：**赛道知识 base + 学生 ⭐ 加权（+30%）** | 主动判断 + 尊重学生意图，cover 新老用户 |
| C-4 | 学生采纳一版后：**立即更新简历 + 永久改写历史**（Git-like，每条 bullet 的 v0/v1/v2 + 历次采纳记录全留，可回退任意版本） | 即时 + 完整可追溯 + 成长可视化 |
| C-5 | AI 想编数字时（`_detect_fabricated_numbers` 命中）：**生成 v2 含该数字** + **红色警告** + 3 条出路（填实数 / 删数 / 接受模糊版）。AI **不可让步** —— 红线 | SAIF 死线守住 + 学生主动收集真实数据 |
| C-6 | 改写入口：**推荐卡（针对岗位） + 右栏简历 hover（通用打磨） + 档案 entry（→ 写成 bullet）** | **B → C 闭环打通**（plan-mode 加厚的经历可直接转 bullet） |

---

### D — 推荐 + 反馈回路

| # | 决策 | 学生体感 |
|---|---|---|
| D-1 | "为什么推" 卡片 = **3-5 条 bullet**（✓ 强匹配 + ⚠ 弱信号 actionable）+ **底部 ✗ 反馈按钮** | 扫读 + actionable + 反馈入口在场 |
| D-2 | ✗ 按下后：**inline 弹原因选项卡**（不是这个赛道 / 公司不喜欢 / 学校段位 / 时间不合适 / 其他）+ **自由备注框** | 主路径快 + 想多说可写 |
| D-3 | 反馈后下次进工作台：**第一次进时 banner 一行**「👍 已记你不喜欢 X，已排除」 + **档案多一条 preference 条目**（持久） | 即时可见 + 长期可管 |
| D-4 | **snapshot 系统彻底删除**（前端 + 后端 + DB 表 + `quick_enrichment.py` + `recommendation.py` 内 snapshot boost 逻辑全删） | 推荐变两层（规则 / LLM 共识）+ 维护成本归零 |
| D-5 | 重大动作（采纳改写 / 标 ⭐ / 删档案 / plan-mode finalize / ✗ 拒绝 / 换赛道）**触发推荐重排**，**1.5s debounce 合并连续动作** | 即时反馈 + 不嘈杂 |
| D-6 | 推荐数量 = **top 10 + 最低 50 分门槛**；冷门赛道空缺时**诚实显示"暂无更多优质推荐"**（不硬凑） | 数量稳 + 质量稳 + 不糊弄 |

---

### E — 工作台三栏布局

| # | 决策 | 学生体感 |
|---|---|---|
| E-1 | 三栏：**左推荐 / 中 chat / 右简历**；档案作**收起浮条**挂在右栏底部，🟢 小绿点提示有更新 | 信息分布清晰 + 档案不挤右栏仍能被瞄到 |
| E-2 | 左栏推荐 = **卡片可展开**（默认 β 中等密度，点开看三层分独立 + 完整"为什么推" + ✗ 反馈按钮）；**同一时间只允许 1 张展开**（点新的旧的自动收） | 默认轻量、想看细节随时点开；D 阶段可解释性直接落地 | 
| E-3 | 改写发生时：**chat 区出 AI 思考** + **右栏 inline diff 同步**（v0/v1/v2 三段 in-place） | 左眼读思考 / 右眼看变化，所见即所得 |
| E-4 | 学生采纳改写后：**左栏推荐 1.5s 柔和动画重排**（卡片"飞"到新位置） | 学生眼睁睁看到自己的改写产生效果，闭环视觉化 |
| E-5 | **顶部 sticky bar 全宽一条**「🎯 当前赛道: X / 适配度 N/10 [换赛道]」 | 赛道意识贯穿整个工作流 |

⚠ E-2 由 D-4 触发**修正**：三层分（规则 / 情报 / 最终）→ **两层分**（规则 / LLM 共识）。前端组件设计据此调整。

---

## 3. 4-surface 闭环 — `account_memory` 是粘合剂

```
                ┌──────────────────────┐
                │  Resume 上传 + Parse  │
                └──────────┬───────────┘
                           ↓
                ┌──────────────────────┐
                │  confirmed_profile    │ ← 静态,parse 出的
                └──────────────────────┘
                           ↓ (A-7 自动填充)
       ┌──────────────────────────────────────────┐
       │             主工作台 (5 surface)          │
       ├──────────────────────────────────────────┤
       │ ① Chat                 写 ✓  读 ✓        │ ←──┐
       │ ② Plan-mode (B)        写 ✓  读 ✓        │    │
       │ ③ Recommendation (D)   写 ✓  读 ✓        │    │  account_memory
       │ ④ Rewrite (C)          写 ✓  读 ✓        │ ←──┤  (SSoT)
       │ ⑤ 我的档案 (A)         读+编辑 ✓         │ ←──┘
       └──────────────────────────────────────────┘
                           ↕
                ┌──────────────────────┐
                │  account_memory       │
                │  (8 categories + ⭐)  │
                └──────────┬───────────┘
                           ↓
                ┌──────────────────────┐
                │  Mock Interview       │ ← 验证 + 再生 memory
                └──────────────────────┘
                           ↓
                       (回流到 memory)
```

**对比当前 silo 状态**：
- Chat 写但 UI 不显示 → 学生不知道写了什么 ← **A 修复**
- Plan-mode 写但 UI 没入口 → 学生不知道有这个功能 ← **B 修复**
- Recommendation 不写 memory → 学生反馈没回流 ← **D 修复**
- Rewrite 只读 confirmed_profile，不读 memory → 改写跟 chat 最新细节脱节 ← **C 修复**

---

## 4. 工程任务拆分

### P0 — 闭环前置（必须先 ship，否则后续都是空架子）

| 任务 | 范围 | 估时 |
|---|---|---|
| **P0-1** 打开 `UNIFIED_MEMORY_ENABLED` + `STUDENT_KB_ENABLED` flag，确认 chat 抽取真的在写 `account_memory` | `backend/app/config.py` + 验证 `extractor.py` 触发路径 | 1h |
| **P0-2** 新增 `GET /api/resume-copilot/sessions/{id}/memory` endpoint，按 8 类分组返回 entry | `backend/app/routers/resume_copilot.py` + 新 service | 半天 |
| **P0-3** legacy `student_experiences` → `account_memory` 一次性 backfill migration（A-9） | Alembic migration + 数据脚本 | 半天 |
| **P0-4** "我的档案"侧边面板（A-1/A-2/A-3/A-5/A-6/A-7/A-8）—— 替换现有 `student-kb-drawer.tsx` | `resume-copilot-web/components/resume-copilot/` 新增 `archive-panel.tsx` + 拆 9 个子组件 | 1.5 天 |
| **P0-5** plan-mode mode toggle（B-1） + 接通 `/sessions/{id}/plan/*` 三个 endpoint | 改 chat 输入框组件 + 新 mode-toggle 子组件 | 1 天 |
| **P0-6** plan-mode 完整流程（B-2/B-3/B-4/B-5） | 后端 `plan.py` 已有，主要补前端 wrap-up + 草稿 review + chat 折叠卡片 | 1.5 天 |
| **P0-7** snapshot 系统彻底删除（D-4） | drop `JobIntelSnapshot` + 删 `quick_enrichment.py` + 清 `recommendation.py` 的 snapshot 逻辑 + 清 `workflow.py` 的 enrich 阶段 | 半天 |

**P0 工程总量**：约 **5.5 天**。完成后学生第一次能感受到 "AI 真记住了 / plan-mode 真能用"。

---

### P1 — 核心闭环（让 5 surface 真正打通）

| 任务 | 范围 | 估时 |
|---|---|---|
| **P1-1** 工作台三栏布局重构（E-1）+ 顶部赛道 sticky bar（E-5，仅占位版本） | `public-resume-copilot.tsx` 大幅重构 → 拆分到 `<WorkspaceShell>` + 三栏子组件 | 2 天 |
| **P1-2** 推荐卡片可展开 + 两层分 + "为什么推" + ✗ 反馈（E-2 + D-1） | 新 `<RecommendCard>` 组件，**只展示两层分**（snapshot 删除后） | 1 天 |
| **P1-3** ✗ 反馈 inline 表单 + banner + 写回 `account_memory.preference`（D-2/D-3） | 前端 inline 卡 + 新 `POST /sessions/{id}/recommendations/{job_id}/reject` endpoint | 1 天 |
| **P1-4** 改写引入 thesis layer：v0/v1/v2 三版生成（C-1） | 重写 `chat.py` 里 rewrite prompt + 输出结构 | 1 天 |
| **P1-5** AI 卖点判断 + batch 推 N 条改写（C-2/C-3） | 新 `recommend_rewrite_targets()` service，赛道知识 + ⭐ 加权 | 1 天 |
| **P1-6** chat 出思考 + 右栏 inline diff 同步（E-3）+ 改写后柔和重排（E-4） | 前端 framer-motion / FLIP 动画 + diff 组件 | 1.5 天 |
| **P1-7** 改写采纳 + 永久改写历史（C-4） | 新 `bullet_revisions` 表 + Alembic + 前端历史折叠区 | 1 天 |
| **P1-8** 编造数字红色警告（C-5）—— 复用现有 `_detect_fabricated_numbers`，前端展示 + 3 个出路按钮 | 前端组件 + 写回 v2 时的 markup | 半天 |
| **P1-9** 改写三入口（C-6）：推荐卡 + 简历 hover + 档案 entry → bullet | 三处按钮 + 入口收敛到同一 rewrite service | 半天 |
| **P1-10** 推荐重排 debounce + top10 + 50 分门槛（D-5/D-6） | 后端排序 + 阈值 + 前端 debounce | 半天 |

**P1 工程总量**：约 **10 天**。完成后整个 5 surface 闭环跑通。

---

### P2 — Polish + 完善

| 任务 | 范围 |
|---|---|
| **P2-1** 赛道适配度算法（顶部 sticky bar 的 "6.2/10"）+ 整体改写建议 | 新 algorithm，需先定义赛道-bullet 对齐度评分 |
| **P2-2** AI 卖点判断算法精细化 + 跨岗位改写复用（同赛道相似公司可复用 v2） | 现 batch 改写每次重算，P2 加 cache |
| **P2-3** 改写后 PDF 重导 / 一键下载最新简历 | 复用现有 PDF service |
| **P2-4** 隐性反馈信号（学生扫过没点开是不是算 weak preference） | 前端埋点 + 后端权重 |
| **P2-5** 响应式：1280 以下窄屏怎么塌（推荐栏折叠成顶部抽屉？） | 响应式 layout |

---

## 5. 上线后验收 checklist

每个 P0 / P1 任务的"完成"标准：

- [ ] **A 验收**：在 chat 输入「我做过 X」→ AI 回话末尾出现「📝 已记入档案：X」→ 右栏档案面板 +1 + 🟢 小绿点 → 点开看到结构化条目 + 原话 → 能删 / 编辑 / 标 ⭐
- [ ] **B 验收**：chat 输入框切到 📌 plan-mode → AI 主动开问 → 聊 4-5 轮 → AI wrap-up 给草稿 → 学生 review 入档 → chat 历史里看到折叠卡片
- [ ] **C 验收**：点推荐卡「针对这家改写」→ chat 浮出思考 + 右栏 inline diff 出 v0/v1/v2 → 采纳 v2 → 左栏推荐 1.5s 柔和重排 → 改写历史能看到这次记录
- [ ] **D 验收**：点 ✗ 反馈 → 选原因 + 备注 → 推荐列表移除 → 第二天进工作台看到 banner + 档案多 preference 条目
- [ ] **E 验收**：三栏 sticky 在 1440 屏正常 → 顶部赛道 bar 全宽常驻 → 档案收起浮条点开正常展开
- [ ] **闭环验收**：用 plan-mode 加厚一段电价经历 → 从档案点「→ 写成 bullet」→ AI 自动生成 v0/v1/v2 → 采纳后推荐序号变化

---

## 6. 不在范围 / 留作未来 (Open questions)

这些 brainstorm 时没问到 / 不影响 P0+P1 ship 的决策，留待实施时根据情况判断：

- **AI 改写时 input/memory selection 策略**：是用全部 memory、top-K relevance、还是只跟当前 bullet 相关的？
- **跨岗位改写复用**：学生针对易方达改的 v2，投广发时复用还是重新生成？
- **改写后 PDF 重导**：学生改完几条 bullet 后是手动点"下载新 PDF"还是自动重导？
- **隐性反馈信号**：学生扫过推荐没点开算不算 weak preference？
- **三栏宽度比例 + 响应式**：1440 / 1920 比例分别多少？1280 以下怎么塌？
- **小绿点的精确清除规则**：点开档案就清？看完那条就清？
- **改写历史的 UX 深度**：是简单列表 vs 时间轴 vs Git-style commit graph？

---

## 7. 实施时的硬约束（CLAUDE.md 已有，重申）

- **新 schema 改动只走 Alembic**：`bullet_revisions` 表、`account_memory` 索引等新增必走 alembic
- **SQLite WAL + busy_timeout 不要绕开**：`backend/app/database.py` 的 connect hook 不动
- **Demo session read-only**：所有新 write endpoint 必须挂 `_assert_not_demo(session)` 守卫
- **每个并行任务自己开 `SessionLocal`**：不跨线程共享
- **DEV VPS DB 改动不会自动同步 prod**：P0-3 backfill migration 在 prod 上线时要单独走 deploy 流程
- **改写不能编数字**（C-5 红线）：`_detect_fabricated_numbers` 不能剥掉，红色警告必须明显

---

## 8. Brainstorm 来源记录

- 入口：2026-05-19 用户提出"主工作台交互逻辑优化"
- 调查：发现 2 个真 bug —— memory 写入但 UI 不展示、plan-mode 实现完整但工作台无入口
- 流程：用户主导，按"领导汇报"视角问每一步交付物/体感/代价
- 决策数：31 个（A 9 + B 5 + C 6 + D 6 + E 5）
- 决策记录：本文档 §2 五张表

未在本文档列出的中间讨论过程，见原始对话 transcript。
