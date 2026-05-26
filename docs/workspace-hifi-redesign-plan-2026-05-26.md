# Resume Copilot HiFi 三页一比一复刻 — 实施计划

> **作者:** Claude (resume-copilot session,2026-05-26)
> **设计源:** Claude Design 导出 bundle(3 个 HTML + 16 个 JSX) — Resume Copilot HiFi.html / Confirm Profile.html / Resume Sessions.html
> **目标:** 工作台 + 解析确认页 + 多简历管理页,样式 + 动画 + 交互 1:1 复刻设计,后端契约不动。
> **分支流程:** 全部 commit 进 `resume-copilot` 分支 → push origin → 跟 `网站设计-devvpstmux` orchestrator 协调 merge main → deploy(不直接 push main)。

---

## 0. 现状对齐结论

### 0.1 后端无改动需求 ✅

后端 router 现有 endpoint 全部覆盖三页需求:

| 设计需要 | 现有 endpoint | 状态 |
|---|---|---|
| 工作台拉取会话 | `GET /sessions/{sid}` | ✅ |
| 多会话列表 | `GET /sessions` | ✅(line 142) |
| 切换/新建会话 | `POST /sessions` + `DELETE /sessions/{sid}` | ✅ |
| 解析确认提交 | `PUT /sessions/{sid}/confirmed-profile` + `PUT /sessions/{sid}/preferences` | ✅ |
| 平台聚合推荐 | `GET /sessions/{sid}/recommendations/platforms` | ✅ |
| LLM 个性化叙事 | `GET /sessions/{sid}/recommendations/{job_id}/narrative` | ✅ |
| 同辈情报卡 | `/api/intel/company-card`(独立 router) | ✅ |
| Rewrite 警告 | `chat.py::generate_rewrite_v0_v2` + `_detect_fabricated_numbers` | ✅(警告必须显式露出 — 别剥) |

### 0.2 前端 token / 字体已对齐 ✅

`resume-copilot-web/components/hifi/hifi-tokens.css` 是设计 `hifi-tokens.css` 的**严格超集**(2026-05-20 已合并过)。所有 `--terracotta-*` / `--parchment` / `--ink-*` / `--font-serif` / `hf-btn` / `hf-pill` / `hf-card` 类都 ready。

### 0.3 已知差距 ❌

| 维度 | 现状 | 差距 |
|---|---|---|
| **5 个 rc-\* 动画** | `workspace-theme.css` 4205 行全用自有 `workspace-hifi-*` 命名,**`rc-*` 命名一个都没引** | 必须新增:`rc-orb`(LLM 球心跳)/ `rc-pulsering`(Coach 节点扩散环)/ `rc-dot`(思考省略号)/ `rc-drawer-in`(IntelDrawer 滑入)/ `rc-fade-in`(modal/menu) |
| **TopBar** | `TopTrackBar.tsx` 50 行简单赛道 + 分数 | 需扩到 logo 面包屑 + Session 切换下拉 + Coach mode 徽章 + 赛道 chip + 计数 + 用户头像 |
| **RailHeader** | 已有 3 tab + LeftRecommendRail | tab 选中态、count pill 颜色、过滤行布局需对齐设计 |
| **IntelDrawer 420px 右栏** | `RecommendCardIntelSection.tsx` 内嵌在卡片里的简版,无 tab | 重做为独立 420px 右栏抽屉,4 tab(原话 hero + 待遇 + 要求 + 面试题)替换 RightResumePane |
| **Coach Pane** | `PlanPanel.tsx` 现有 STAR 流,但未走 Coach 视觉 | CoachPane 套壳/复用 PlanPanel,加 ribbon + STAR stepper + 同辈情报 hero quote + footer 3 胶囊 |
| **Rewrite Pane** | 现有 v0/v2 流跑在 chat bubble 里 | 中栏 takeover,3 候选卡 + 数字 mark 高亮 + 守卫面板 |
| **Confirm Profile 整页** | `WorkspaceConfirmGuide` 是浮层 | 新建 `/resume-copilot/confirm` 整页,3 个内容卡 + 城市 chip |
| **Sessions 整页** | 不存在 | 新建 `/resume-copilot/sessions`,thumbnail + 4 维统计 + 上传卡 |

---

## 1. 样式 + 动画对齐审计(P0 前置)

### 1.1 必须引入的 5 个 `rc-*` 关键帧

来自设计 `Resume Copilot HiFi.html` 顶部 `<style>` + `hifi-ws-orb.jsx` + 各 ws 组件:

```css
/* LLM 球心跳 — HFOrb / HFThinkingTakeover 核心动画 */
@keyframes rc-orb {
  0%, 100% { transform: scale(1); filter: brightness(1); }
  50%      { transform: scale(1.045); filter: brightness(1.08); }
}

/* Coach 节点 + Orb L 外环扩散 */
@keyframes rc-pulsering {
  0%   { box-shadow: 0 0 0 0 rgba(201,100,66,0.32); }
  100% { box-shadow: 0 0 0 18px rgba(201,100,66,0); }
}

/* 思考省略号 */
@keyframes rc-dot {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.35; }
  40%           { transform: translateY(-4px); opacity: 1; }
}

/* IntelDrawer 从右滑入 */
@keyframes rc-drawer-in {
  from { transform: translateX(20px); opacity: 0; }
  to   { transform: translateX(0); opacity: 1; }
}

/* SessionMenu / TrackModal / Coach 切换 — 通用淡入 */
@keyframes rc-fade-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}
```

**落地位置:** `resume-copilot-web/components/hifi/hifi-tokens.css` 底部追加。理由:这套动画与 `.hf` 设计语义强绑定,放 token 文件比 workspace-theme.css 更合适,且工作台/确认页/sessions 三处都要用。

### 1.2 已具备(超集已 OK,无需动) ✅

`hifi-tokens.css` 现有 8 个 `hf-*` keyframes 全在:`hf-spin` / `hf-pulse` / `hf-bar` / `hf-ping`(rail header radar dot)/ `hf-ticker` / `hf-slide`(chat bubble fade in)/ `hf-blink`(inline cursor)/ `hf-logo-ping` / `hf-logo-core` / `hf-logo-sweep`。

`hf-slide` ↔ 设计的 `hf-slide` 同名同效,Chat bubble 复用现有即可。

### 1.3 组件级样式 diff 表

| 设计组件 | 设计 token / 关键样式 | 现有实现 | 动作 |
|---|---|---|---|
| **HFTopBar**(workspace) | `height: 52px` / `background: var(--ivory)` / `border-bottom: 1px solid var(--border-warm)` / `z-index: 50` | `workspace-hifi__top-bar`(在 workspace-theme.css 应已存在) | 替换内容,样式骨架沿用 |
| **Coach 模式徽章** | `background: var(--terracotta)` / `color: #fff` / `border-radius: 999px` / `box-shadow: 0 4px 12px rgba(201,100,66,0.28)` + 内嵌小 logo bubble | 不存在 | **新增 .workspace-hifi__coach-badge** |
| **Session menu 下拉** | 320px / `box-shadow: 0 16px 40px rgba(0,0,0,0.18), 0 0 0 1px var(--ring-warm)` / 当前项 `var(--terracotta-wash)` 背景 | 不存在 | **新增 SessionMenu.tsx + .workspace-hifi__session-menu** |
| **HFRailHeader** tab | 选中 `border-bottom: 2px solid var(--terracotta)` + count pill 选中变 terracotta 实心 | 已有 tab 切换,样式不一致 | 修 CSS 选中态 |
| **HFIntelDrawer** 顶 banner | `linear-gradient(180deg, #fff5ed 0%, var(--ivory) 100%)` + `border-bottom: 1px solid var(--border-warm)` | 不存在(内嵌简版) | **新建** |
| **HFQuote** hero 态 | `linear-gradient(180deg, #fff8ef 0%, #faf4e9 100%)` + `border-left: 4px solid var(--terracotta)` + "VERBATIM" 角标 + `font-family: var(--font-serif); font-style: italic; font-size: 16px` | 不存在 | **新建** |
| **HFQuote** 小卡 | `#fff` 背景 + `border-left: 3px solid var(--terracotta-wash)` + serif italic 13.5px | 不存在 | **新建** |
| **IntelTabs** | tab `padding: 10px 10px` + 选中下边 `2px solid var(--terracotta)` + count pill | 不存在 | **新建** |
| **HFCoach** header ribbon | `linear-gradient(135deg, var(--terracotta-wash) 0%, #fff5ed 100%)` + `border-bottom: 1.5px solid var(--terracotta)` + target icon 36px terracotta 方块 | PlanPanel 没有这层 | **新增 .workspace-hifi__coach-ribbon** |
| **HFStarStepper** | 30px 节点圆 + active 态 `2px solid var(--terracotta) + box-shadow: 0 0 0 4px rgba(201,100,66,0.14)` + `rc-pulsering` 动画环 | 不存在 | **新建** |
| **HFPhaseTrack** | `B-1...B-4` 4 个胶囊 + 连接线,active 节点 terracotta 实心 | 不存在 | **新建** |
| **HFRewriteOption** | `box-shadow: 0 0 0 1px var(--border-warm)`,selected 态 `0 0 0 2px var(--terracotta), 0 8px 24px rgba(201,100,66,0.10)` | 现有 v0/v2 bubble 形态不同 | **新建** |
| **数字 mark 高亮** | `<mark>` 加 `background: var(--terracotta-wash); color: var(--terracotta-strong); padding: 0 3px; border-radius: 3px; font-weight: 600` | 不存在 | **新建 util `renderTextWithNumbers()`** |
| **守卫面板** | `var(--ivory)` 卡片 + shield icon + 列已 substring 命中的数字 | 不存在 | **新建** |
| **HFTrackCard**(modal) | selected 态 `0 0 0 2px var(--terracotta), 0 8px 20px rgba(201,100,66,0.10)` + 38px 圆角方形 track icon | `TrackPickerModal.tsx` 应已有,样式可能差 | 对照 diff 调样式 |
| **HFConfirmPage** 摘要卡 | `padding: 6px 22px` + `background: #fdfbf3` + `grid 120px 1fr` 12px gap key-value 行 | 不存在 | **新建** |
| **HFSessionCard** thumbnail | `background: #fff; border-radius: 8px; padding: 14px` + 三段假 bullet `width` 用 `(j * 17 + 60) % 95 + 5` pattern | 不存在 | **新建** |
| **HFUploadCard** dashed | `box-shadow: 0 0 0 2px dashed var(--ring-warm)` + 45° 拖纹 `repeating-linear-gradient` | 不存在 | **新建** |

### 1.4 现成可直接复用的现有组件

- `components/hifi/hifi-primitives.tsx` — `HFLogo` / `HFBtn` / `HFPill` / `I` icon set 全部已就位
- `components/resume-copilot/workspace/TrackPickerModal.tsx` — Track 选择 modal 已存在,P2 confirm 页直接复用
- `components/resume-copilot/workspace/recommend/PlatformCard.tsx` — 平台 tab 卡已实装,P0 只需小调
- `components/resume-copilot/workspace/recommend/RecommendNarrativeSection.tsx` — narrative ✦ 块复用
- `components/resume-copilot/workspace/RewriteContext.tsx` — 改写跨栏信号机制保留

---

## 2. P0 · 工作台核心(优先级 1,~2 工时)

**目标:** 工作台进入设计 1:1 样式,情报抽屉成王牌交互。

### 2.1 文件改动清单

| 文件 | 动作 | 估行 |
|---|---|---|
| `components/hifi/hifi-tokens.css` | **追加** 5 个 `rc-*` keyframes | +25 |
| `components/resume-copilot/workspace/TopTrackBar.tsx` | **重写**(50 → 180 行) | +130 |
| `components/resume-copilot/workspace/SessionMenu.tsx` | **新建** | +120 |
| `components/resume-copilot/workspace/LeftRecommendRail.tsx` | 改 tab + filter 样式 | ±30 |
| `components/resume-copilot/workspace/intel/IntelDrawer.tsx` | **新建** 主壳 | +200 |
| `components/resume-copilot/workspace/intel/IntelQuote.tsx` | **新建** hero + 小卡 | +60 |
| `components/resume-copilot/workspace/intel/IntelTabs.tsx` | **新建** | +50 |
| `components/resume-copilot/workspace/WorkspaceShell.tsx` | 增 `intelOpenId` state + 条件渲染 IntelDrawer 替换 RightResumePane | +30 |
| `components/resume-copilot/workspace/recommend/PlatformCard.tsx` | 展开态加"为你定制"高亮叙事盒 | +40 |
| `components/resume-copilot/workspace/recommend/RecommendCardIntelSection.tsx` | **删除**或改为只用于 fallback | -80 |
| `components/resume-copilot/workspace/workspace-theme.css` | 配套 css class | +150 |

**估计净增:** ~700 行(含 css)

### 2.2 实施步骤

1. **rc-\* 动画引入**(hifi-tokens.css)— 1 commit
2. **TopBar 重做** + SessionMenu 新建 — 1 commit
3. **IntelDrawer 三件套**(主壳 + Quote + Tabs)+ WorkspaceShell wire-up — 1 commit
4. **PlatformCard 展开态调整** + RecommendCardIntelSection 退役 — 1 commit
5. **RailHeader 样式 polish** — 1 commit

### 2.3 验收

- `npm run lint` 0 errors;`npm run build` 通过
- 浏览器 demo session:
  - TopBar 4 个区域可见 + SessionMenu 下拉能开能关
  - 点小红书角标 → IntelDrawer 从右滑入(`rc-drawer-in` 动画) + 4 tab 全部数据 + 没数据公司显 `📭 同辈情报暂未覆盖`
  - 平台 tab 卡片展开 → "为你定制" terracotta-wash 盒子 + mini-job 列表 + narrative
  - Chat / 改写流程不破坏
- 三套设计系统隔离不破:Workspace token 不渗 HiFi/Interview

---

## 3. P1 · Coach + Rewrite 中栏 takeover(优先级 2,~2 工时)

**目标:** chat / coach / rewrite 三态切换的中栏,完整对齐设计。

### 3.1 文件改动清单

| 文件 | 动作 | 估行 |
|---|---|---|
| `components/resume-copilot/workspace/coach/CoachPane.tsx` | **新建** 主壳 | +250 |
| `components/resume-copilot/workspace/coach/CoachRibbon.tsx` | **新建** | +60 |
| `components/resume-copilot/workspace/coach/StarStepper.tsx` | **新建** | +80 |
| `components/resume-copilot/workspace/coach/PhaseTrack.tsx` | **新建** | +50 |
| `components/resume-copilot/workspace/rewrite/RewritePane.tsx` | **新建** 主壳 | +180 |
| `components/resume-copilot/workspace/rewrite/RewriteOption.tsx` | **新建** | +100 |
| `components/resume-copilot/workspace/rewrite/FabricationGuardPanel.tsx` | **新建**(对接 `_detect_fabricated_numbers`) | +60 |
| `components/resume-copilot/workspace/MiddleChatPane.tsx` | 加 coach/rewrite 模式条件渲染 | +30 |
| `components/resume-copilot/workspace/chat/ChatEmpty.tsx` | **新建** 4 引导卡 | +80 |
| `components/resume-copilot/workspace/RewriteContext.tsx` | 加 `rewriteBulletId` + `coachCompanyId` state | +20 |
| `workspace-theme.css` | 配套 css | +200 |

**估计净增:** ~1100 行(原 800 估计偏低 — 加上 CSS 和 wire-up 在 1k 上下)

### 3.2 后端复用契约

- **CoachPane** 不重写后端,wrap 现有 `plan_turn.py` 走 `activeJobContext` — 现工作台 WorkspaceShell.tsx 已经传 `activeJobContext` 到 MiddleChatPane,改造把它转换为 coachCompanyId
- **RewritePane** 走现有 `generate_rewrite_v0_v2` endpoint;3 候选其实是 v0 + v2 共 2 个 + 可加 v3 占位(或维持 2 个,设计 3 候选只是 mock 数据)— **跟用户确认是否上 v3**
- **守卫面板** 直接读 `RewriteWarning.fabricated_numbers` + `RewriteWarning.audit_risks` — 现已存在,不剥即可
- **Coach 同辈情报引用** — 从 `intel.quotes` 取最后一段 verbatim quote(per design),其它阶段切换可循环不同 quote

### 3.3 实施步骤

1. **CoachPane + 3 子组件** + WorkspaceShell wire-up — 1 commit
2. **RewritePane + 守卫面板** + RewriteContext 扩 — 1 commit
3. **Chat 空状态 4 引导卡** — 1 commit
4. **样式 polish + lint** — 1 commit

### 3.4 验收

- 点公司卡 "针对这家定制" → CoachPane takeover + STAR stepper 显示 + ribbon 公司信息正确
- STAR 4 步切换流畅,active 节点 `rc-pulsering` 扩散环
- 点 resume bullet 上的 edit → RewritePane takeover,2-3 候选有数字高亮 + 守卫面板列已命中数字
- 故意触发 fabrication(LLM 改写编了简历没的数字)→ 守卫面板红框警告显式显示
- "回 Chat" 按钮回到 chat 模式

---

## 4. P2 · Confirm Profile + Resume Sessions 两页(优先级 3,~1.5 工时)

**目标:** 解析确认页 + 多简历管理页整页新建。

### 4.1 前置数据验证(开干前先跑)

| 需验证 | 怎么验 | 备用方案 |
|---|---|---|
| `target_cities` 字段是否在 `ResumePreferencePayload` | `grep "cities" backend/app/schemas_resume_copilot.py` | 没有就加 alembic migration(`backend/alembic/versions/<name>_add_target_cities.py`) |
| Session list 是否含 stats(companies / jobs / intel / rewrites count) | 看 `ResumeCopilotSessionListItem` schema | 没有就在 list endpoint 加聚合查询 |
| Session `is_archived` 字段 | 看 model | 没有就加(P2 sessions 页有归档 filter) |

### 4.2 文件改动清单

| 文件 | 动作 | 估行 |
|---|---|---|
| `app/resume-copilot/confirm/page.tsx` | **新建** route | +30 |
| `components/resume-copilot/confirm/ConfirmProfilePanel.tsx` | **新建** 主壳 | +120 |
| `components/resume-copilot/confirm/ResumeSummaryCard.tsx` | **新建** | +60 |
| `components/resume-copilot/confirm/TrackBlock.tsx` | **新建**(复用 TrackPickerModal) | +50 |
| `components/resume-copilot/confirm/CityBlock.tsx` | **新建** | +50 |
| `app/resume-copilot/sessions/page.tsx` | **新建** route | +30 |
| `components/resume-copilot/sessions/SessionsPanel.tsx` | **新建** 主壳 | +150 |
| `components/resume-copilot/sessions/SessionCard.tsx` | **新建** | +120 |
| `components/resume-copilot/sessions/ResumeThumb.tsx` | **新建** | +70 |
| `components/resume-copilot/sessions/UploadCard.tsx` | **新建** | +60 |
| `components/resume-copilot/sessions/SessionsToolbar.tsx` | **新建** filter + sort | +80 |
| 退役 `WorkspaceConfirmGuide.tsx` | **删除**(替换为 redirect) | -100 |
| `WorkspaceShell.tsx` | `needsConfirm` 改成 `router.push('/resume-copilot/confirm?session_id=N')` | +5 |
| 新 CSS files | 整页样式 | +250 |

**估计净增:** ~900 行

### 4.3 实施步骤

1. **后端前置验证** — 1 commit(若需要 migration)
2. **Confirm 页** 5 个子组件 + route — 1 commit
3. **Sessions 页** 5 个子组件 + route — 1 commit
4. **退役 WorkspaceConfirmGuide + redirect 改造** — 1 commit
5. **样式 polish** — 1 commit

### 4.4 验收

- 上传简历后:`/upload` → 后端 parse → 跳 `/resume-copilot/confirm?session_id=N` → 看摘要 + 选赛道 + 选城市 → "确认" → 跳工作台开始生成推荐
- 工作台 TopBar SessionMenu 底部"管理全部" → `/resume-copilot/sessions` → 列出全部 session + thumbnail + 4 维统计 + 切换/上传
- 空状态(无 session)显引导

---

## 5. 跨 PR 注意事项

### 5.1 红线(不可破)

1. **`_assert_not_demo` 守卫** — demo session 所有写入端点保留
2. **`_detect_fabricated_numbers` warning 显式露出** — RewritePane 必须显示,不能剥
3. **Knowledge pack verbatim quote 不改写** — IntelDrawer "原话" tab 直显原文,不二次包装/总结
4. **`account_memory` 写入路径唯一** — 不在新组件里直插 row,继续走 `BackgroundTasks` → `extract_for_chat_turn` → `_persist_to_account_memory`
5. **三套设计系统隔离** —
   - Workspace 新组件全部进 `.workspace-hifi` scope
   - 新页面整页 `.hf` scope
   - 不渗到 `/`、`/upload`、`/interview/*`

### 5.2 每 PR done 前必跑

```bash
cd resume-copilot-web && npm run lint && npm run build
cd backend && PYTHONPATH=. .venv/bin/pytest tests/ -x  # 若改后端
```

浏览器手测 demo session + 1 个真账号 golden path:上传 → confirm → workspace → 点 intel → coach → rewrite → 导出。

### 5.3 分支 + 部署流程

每个 PR:
1. commit 到 `resume-copilot` 分支
2. `git push origin resume-copilot`
3. 跟 `网站设计-devvpstmux` orchestrator 协调 merge `resume-copilot` → `main`
4. merge 进 main 后 → 用 `jobradar-vps-deploy` skill 部署到 prod
5. **不直接 push main / 不绕过 orchestrator**;紧急 hotfix 先问用户

---

## 6. 风险 / 未决问题

| # | 问题 | 影响 | 解法 |
|---|---|---|---|
| 1 | RewritePane 候选数量(设计 3,后端实际 v0/v2 = 2) | P1 视觉 vs 后端契约 | **跟用户确认**:维持 2 候选 + 用一个 v3 placeholder slot,或者升 backend 出 3 候选 |
| 2 | Coach Pane 与现有 `PlanPanel` 关系 | P1 实现选择 | 倾向 wrap 而非重写,降低 regression 风险 |
| 3 | `target_cities` schema 字段 | P2 confirm 页 | 开 P2 前先 grep 验,缺则加 alembic |
| 4 | Sessions list stats 聚合 | P2 sessions 卡片 4 维统计 | 验 `ResumeCopilotSessionListItem` 是否含 stats;缺则扩 endpoint |
| 5 | Session `is_archived` | P2 filter tab | 同 #4 验,缺则 column 加 + migration |
| 6 | TopBar SessionMenu 切换语义 | P0 实施细节 | 看 `useResumeCopilotSession` hook 切换是 router.push 还是 setState,对齐 |
| 7 | IntelDrawer 替换 vs 并列 RightResumePane | P0 设计意图分歧 | **跟用户确认**:设计是替换;但 simultaneous 操作(改 resume 同时看情报)会冲突 |
| 8 | dev 上 narrative cache / intel cache 都缺(prod 写过 dev 没) | P0 demo 路径可能看不到 narrative / intel | 不挡正常开发(用户说"未来再说"),实施 P0 时本地手 pre-bake 即可 |

---

## 7. 任务跟踪

本计划对应 TaskList:

- #100 P0 前置 — 引入 rc-* 动画 + style audit
- #97  P0 — TopBar + RailHeader + IntelDrawer 重做
- #98  P1 — Coach Pane + Rewrite Pane 中栏 takeover
- #99  P2 — Confirm Profile 页 + Resume Sessions 页

依赖:#100 → #97 → #98 → #99(每个 P 进 in_progress 时再细化子任务)

---

## 8. 验收 checklist 总览

**P0 done 条件:**
- [ ] `rc-orb` / `rc-pulsering` / `rc-dot` / `rc-drawer-in` / `rc-fade-in` 5 个动画引入并生效
- [ ] TopBar 4 区显示(logo/breadcrumb + Coach 徽章 + 赛道 chip + 头像)
- [ ] SessionMenu 下拉切换可用(切换调用现有 sessions endpoint)
- [ ] IntelDrawer 420px 右栏从右滑入,4 tab 数据全
- [ ] 空数据公司显 `📭 同辈情报暂未覆盖`
- [ ] PlatformCard 展开"为你定制"高亮盒生效
- [ ] `npm run lint && npm run build` 0 error

**P1 done 条件:**
- [ ] CoachPane 完整渲染 ribbon + STAR stepper(active 节点 rc-pulsering 动画)
- [ ] 同辈情报引用块顶部显示 verbatim quote
- [ ] RewritePane 中栏 takeover,2-3 候选 + 数字高亮 + 守卫面板
- [ ] 故意编造数字测试 → 守卫面板红框警告
- [ ] Chat 空状态 4 引导卡

**P2 done 条件:**
- [ ] `/resume-copilot/confirm?session_id=N` 整页可访问
- [ ] 提交后跳工作台 + 后端 confirmed_profile 写入
- [ ] `/resume-copilot/sessions` 整页可访问,列出会话 + thumbnail + 4 维统计 + 上传卡
- [ ] WorkspaceConfirmGuide 浮层退役
- [ ] 三个新页面 metadata title + favicon 正确(`Resume Copilot · 解析确认` / `· 我的简历会话`)
