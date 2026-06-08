# 统一对话 Hub 外壳 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把分散的求职模块收敛成一个对话 Hub 外壳:左可收起侧边栏 + 中对话主轴 + 右"会变形画布槽";点模块=激活、打一句话=激发跑技能、落结果卡、点开才进视图。本期落 **前端外壳 + 职位推荐 + 梯队骨架 + 个人档案 + 简历优化接口位 + 模拟面试全屏入口**。

**Architecture:** 新建 `HubShell`(不就地改 `RecommendWorkspaceShell`,避免破坏现有 `/recommend` 与并行会话),挂在新路由 `app/hub/page.tsx`(`/hub?session=N`)。复用现有对话栈(`Composer`/`Turn`/`TraceCard`/`MemoryToast`)、feed(`RecommendFeedPane`/`JobCard`)、骨架(`RecommendSkeletonPane`+`PlatformTierGroup`)、档案数据(`getStudentKbIndex`/`confirm`/`archive`)与 `api.ts` 全部现成接口。**新组件**:`DeepThinkCard`(两段式思考卡)、`HubSidebar`、`CanvasSlot`、`HubLanding`、`HubProfileView`、`ResumeSlotPlaceholder`。**后端不动**(本期三拍板:简历优化归 resume-copilot 分支、思考卡接真浅层、会话拆分延后)。

**Tech Stack:** Next.js 16 App Router · React 19 · TypeScript · 现有 `.hf` 赭红 token(`hifi-tokens.css`)+ 新 `hub-theme.css`(`[data-theme="hub"]`)。设计对照:`docs/superpowers/specs/hub-prototype-2026-06-09/`(原型 jsx)+ `docs/superpowers/specs/2026-06-07-unified-conversational-hub-shell-design.md`(spec)。

**铁律(贯穿所有任务):**
- 每个任务结束 `cd resume-copilot-web && npm run lint && npm run build` 必须 **0 error** 才算完成。
- **绝不**改 `RecommendWorkspaceShell.tsx` / `/recommend` 路由(留作回退路径,Hub 验收通过后再议下线)。
- 思考卡 **只有一个**思考动效、**无** border-beam、**无**彩色小标(记忆用单色图标)。
- 学生卡面 **无黑话**:只显示 岗位匹配 / 匹配 94 / 深度匹配 96 / 深挖这个岗 / 讲讲这家;`Base/Enhanced/used_ai/Pro精排` 一律不上卡面。
- 复用组件时**按真实 props 调**(见下 §符号速查),不照抄原型的 window.* 全局写法。

---

## 符号速查(来自真实代码 map,实现时按这个,别按原型全局变量)

- 路由:`app/recommend/page.tsx` → `RecommendPageInner` 解析 `?session=N`、回退列 session→DEMO_SESSION_ID。**新 Hub 照这个模式**。
- 对话消息联合类型(`RecommendChatPane.tsx`):`{kind:'turn',who,text} | {kind:'trace',trace} | {kind:'memory',text} | {kind:'intel',text}`。**Hub 要扩两种**:`{kind:'skillrun',module} | {kind:'result',module,data}`。
- `Composer`(`chat/Composer.tsx`):`{ chips: {key,label}[], placeholder, disabled?, onSend(text) }`。
- `Turn`:`{ who:'me'|'ai', children }`。`TraceCard`:`{ trace:{intent,query_delta,remember_note} }`。`MemoryToast`:`{ text }`。`ThinkingCard`:无 props(含 border-beam — Hub **不用**它,用 DeepThinkCard)。
- feed:`RecommendFeedPane`:`{ sessionId, workingQuery, feed, setFeed, setWorkingQuery, onHighlightCompany(company), onIntel(company) }`。`JobCard`:`{ item, rank, deepening, onDeepen(jobId), onIntel(company), onHighlightCompany(item) }`。item 有 `job_id/job_title/company/location/base_score/enhanced_score/used_ai/in_skeleton/anchors`。
- 骨架:`RecommendSkeletonPane`:`{ sessionId, highlightCompany?, reloadKey?, onOpenIntel?(company,{n_insights?}) }`。**回流对话靠 `onOpenIntel`**。
- api(`components/resume-copilot/api.ts`):`postRecommendChat(sessionId,message): RecommendTurnResponse{intent,reply,feed,working_query,trace,remembered}` · `postRecommendDeepen(sessionId,jobIds): {items}` · `getPlatformsByTier(sessionId,subCat?,mode?)` · `getWorkingQuery` · `updateWorkingQuery` · `getStudentKbIndex(includeArchived?)` · `listStudentExperiences` · `confirmStudentExperience(id)` · `archiveStudentExperience(id)` · `deleteStudentExperience(id)`。
- 类型(`components/resume-copilot/types.ts`):`WorkingQuery{seed_sub_cats,sub_cats,companies,locations,exclude,sort,only,note}` · `RecommendTurnResponse` · `RecommendFeedItem`。
- 档案:`ArchivePanel`(`workspace/archive/ArchivePanel.tsx`)+ `ArchiveEntryCard`;数据 `MemoryEntry{id,category,summary,confidence,user_confirmed,is_archived,...}`。Hub 档案视图复用其数据/动作,呈现层重做(B 分层)。
- token:`components/hifi/hifi-tokens.css`(`.hf`:`--parchment #f5f4ed`/`--ivory #faf9f5`/`--terracotta #c96442`/`--terracotta-wash`/`--font-serif Fraunces`/`--font-sans Inter`)。
- 面试:`app/interview/[sessionId]/page.tsx`(`/interview/123`)。Hub 跳转用 `router.push('/interview/'+sessionId)`,回程 `/hub?session=N`。

---

## 文件结构(本期新建/改动)

```
resume-copilot-web/
  app/hub/page.tsx                    新建 — /hub?session=N 路由 + Suspense + 解析 session
  app/hub/hub-page-inner.tsx          新建 — 解析 session(照 recommend-page-inner)→ <HubShell sessionId/>
  components/resume-copilot/workspace/hub/
    HubShell.tsx                      新建 — orchestrator:arm/fire 状态机 + msgs + 画布槽
    HubSidebar.tsx                    新建 — 侧边栏(导航5 + 新对话 + 简历切换器 + 历史 + 底部身份)
    DeepThinkCard.tsx                 新建 — 两段式思考卡(我的理解 + 思考过程,自动折叠)
    deep-think-meta.ts                新建 — 4 模块的 understand + 4 节点 + 工具名(静态文案 + 真数据注入点)
    CanvasSlot.tsx                    新建 — 会变形画布槽(feed/skeleton/profile/resume 切换 + 宽度)
    HubLanding.tsx                    新建 — 落地态(居中问候 + 打字机 composer + 入口卡 + SkillBar)
    HubProfileView.tsx                新建 — 个人档案 B 闭环(确认信息 + AI 推断待确认)
    ResumeSlotPlaceholder.tsx         新建 — 简历优化接口位占位卡
    SkillBar.tsx                      新建 — composer 上方 3 chip(职位推荐/梯队骨架/简历优化)
    hub-theme.css                     新建 — [data-theme="hub"] 局部样式(沿用 .hf token)
    hub-types.ts                      新建 — HubModule / HubMessage 联合类型 / DeepMeta 类型
  components/resume-copilot/workspace/recommend/PlatformTierGroup.tsx
                                      改 — onOpenIntel 已有;骨架卡"定制深挖"按钮 → 新增 onOpenCoach 回调(回流对话)
```

> 命名隔离:Hub 用 `[data-theme="hub"]`,wrapper `<div data-theme="hub" className="hf">`,与 recommend / interview / workspace 各自 scope 不渗透(CLAUDE.md 三套设计系统铁律)。

---

## Task 1: hub-types + 路由骨架(空壳能跑)

**Files:**
- Create: `resume-copilot-web/components/resume-copilot/workspace/hub/hub-types.ts`
- Create: `resume-copilot-web/components/resume-copilot/workspace/hub/HubShell.tsx`
- Create: `resume-copilot-web/components/resume-copilot/workspace/hub/hub-theme.css`
- Create: `resume-copilot-web/app/hub/page.tsx`
- Create: `resume-copilot-web/app/hub/hub-page-inner.tsx`

- [ ] **Step 1: 定义 hub-types.ts**

```typescript
import type { WorkingQuery, RecommendFeedItem, RecommendTrace } from '../../types';

export type HubModule = 'feed' | 'skeleton' | 'resume' | 'interview' | 'profile';

// 画布槽当前视图（profile 直接开，不跑技能）
export type HubSlot = 'none' | 'feed' | 'skeleton' | 'resume' | 'profile';

export interface ResultCardData {
  title: string;
  body: string;   // 允许内联 <b>，dangerouslySetInnerHTML 渲染
  cta: string;
}

export type HubMessage =
  | { id: string; kind: 'turn'; who: 'me' | 'ai'; html: string }
  | { id: string; kind: 'skillrun'; module: HubModule }
  | { id: string; kind: 'result'; module: HubModule; data: ResultCardData }
  | { id: string; kind: 'trace'; trace: RecommendTrace }
  | { id: string; kind: 'memory'; text: string }
  | { id: string; kind: 'intel'; text: string };

export type { WorkingQuery, RecommendFeedItem };
```

- [ ] **Step 2: 最小 HubShell（占位,后续任务填）**

```tsx
'use client';
import './hub-theme.css';

export default function HubShell({ sessionId }: { sessionId: number }) {
  return (
    <div data-theme="hub" className="hf" style={{ height: '100vh', display: 'flex', overflow: 'hidden', background: 'var(--parchment)' }}>
      <div style={{ margin: 'auto', font: '500 18px var(--font-serif)', color: 'var(--ink)' }}>
        Hub 外壳 · session {sessionId}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: hub-theme.css 最小内容**

```css
[data-theme="hub"] { color: var(--ink); }
[data-theme="hub"] *::-webkit-scrollbar { width: 8px; height: 8px; }
[data-theme="hub"] *::-webkit-scrollbar-thumb { background: var(--ring-warm); border-radius: 8px; }
[data-theme="hub"] *::-webkit-scrollbar-track { background: transparent; }
```

- [ ] **Step 4: 路由 app/hub/page.tsx + hub-page-inner.tsx（照 app/recommend/page.tsx 模式）**

读 `app/recommend/page.tsx` 与 `app/recommend/recommend-page-inner.tsx` 作样板:`page.tsx` 包 `<Suspense>` → `HubPageInner`;`HubPageInner` 用 `useSearchParams()` 取 `?session=N`,缺失则回退(列 sessions → 第一个 → DEMO_SESSION_ID),拿到 `sessionId: number` 后 `<HubShell sessionId={sessionId} />`。**复用 recommend-page-inner 的 session 解析逻辑,不要重发明**。

- [ ] **Step 5: 验证 lint + build + 路由可达**

Run: `cd resume-copilot-web && npm run lint && npm run build`
Expected: 0 error。`/hub?session=1` 渲染 "Hub 外壳 · session 1"。

- [ ] **Step 6: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/hub/hub-types.ts \
        resume-copilot-web/components/resume-copilot/workspace/hub/HubShell.tsx \
        resume-copilot-web/components/resume-copilot/workspace/hub/hub-theme.css \
        resume-copilot-web/app/hub/page.tsx resume-copilot-web/app/hub/hub-page-inner.tsx
git commit -m "feat(hub): /hub 路由 + HubShell 空壳 + hub-types + hub-theme scope"
```

---

## Task 2: HubSidebar(导航 + 简历切换器 + 历史 + 底部身份)

**Files:**
- Create: `resume-copilot-web/components/resume-copilot/workspace/hub/HubSidebar.tsx`
- Modify: `resume-copilot-web/components/resume-copilot/workspace/hub/HubShell.tsx`

参照原型 `docs/superpowers/specs/hub-prototype-2026-06-09/hub/hub-views.jsx` 的 `HubSidebar`(行 73–151)。移植为 TSX:用真实图标(从 `components/hifi/` 现有 icon 或内联 SVG),token 用 `var(--...)`。

- [ ] **Step 1: HubSidebar 组件**

Props:
```typescript
interface HubSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  active: HubModule | null;      // 高亮项 = armed || (slot==='none'?null:slot)
  onNav: (key: HubModule) => void;
  onNew: () => void;
}
```
内容(照原型):
- 收起态(width 64):logo 点 + 新对话 + 5 个导航图标 + 底部头像。
- 展开态(width 252):品牌 + 收起钮 / 「新对话」(土红浅底,与选中 tab 同样式)/ 5 项导航(`职位推荐`/`梯队骨架`/`简历优化`/`模拟面试`(带跳转角标)/`个人档案`)/ 分隔 / 简历切换器(静态"简历·中文主版 · 切换简历(2)",**本期不接多简历后端,纯展示**)/ 历史记录(`历史记录·此简历下的会话`,静态 3 条 mock)/ 底部身份(头像"陈"+ "它记得你·点开看档案",点 → `onNav('profile')`)。
- 选中态:土红浅底 `var(--terracotta-wash)` + 左侧 2.5px 土红竖条 + `var(--terracotta-strong)` 图标。

> 历史记录 + 简历切换器本期是**静态展示**(后端会话拆分延后),只把"会话嵌简历下"的形态立出来。注释标 `// TODO(next): 接会话独立实体后端`。

- [ ] **Step 2: HubShell 接入 sidebar + collapsed 状态**

HubShell 加 `const [collapsed, setCollapsed] = useState(false)`;左侧渲染 `<HubSidebar collapsed active=... onNav onNew onToggle />`。`active`/`onNav`/`onNew` 先用占位:`onNav` 暂存 `console.log`,`onNew` 暂 no-op(Task 5 接真状态机)。

- [ ] **Step 3: 验证 lint + build**

Run: `cd resume-copilot-web && npm run lint && npm run build`
Expected: 0 error。侧边栏渲染、可收起、5 项导航显示。

- [ ] **Step 4: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/hub/HubSidebar.tsx \
        resume-copilot-web/components/resume-copilot/workspace/hub/HubShell.tsx
git commit -m "feat(hub): 可收起侧边栏(导航/简历切换器/历史/底部身份,会话静态占位)"
```

---

## Task 3: deep-think-meta.ts(4 模块思考文案 + 节点 + 工具)

**Files:**
- Create: `resume-copilot-web/components/resume-copilot/workspace/hub/deep-think-meta.ts`

照原型 `hub-deepthink.jsx` 的 `DEEP_META`(行 56–113)移植成强类型 TS。**这是静态文案底座**;真数据(我的理解的赛道/记忆、节点计数)在 Task 4 由 HubShell 注入覆盖。

- [ ] **Step 1: 类型 + 数据**

```typescript
export interface DeepNode {
  icon: string;            // Lucide 名,见 ICONS
  title: string;           // 4 字节点名
  tool: string;            // 工具名(lock_track / search_candidates ...)
  input: Record<string, string | string[]>;
  output: string;          // 完成态 output 文案(可被真计数覆盖)
  chips: string[];         // 完成态结果 chips
}
export interface DeepUnderstand {
  headline: string;        // 「我理解你要的是 —— <headline>」
  tracks: string[];        // 赛道 pill(真数据可覆盖)
  memory: string[];        // 记忆 pill(真数据可覆盖)
  reasoning: string;       // 打字机推理段
}
export interface DeepMeta { understand: DeepUnderstand; nodes: DeepNode[]; }

export const DEEP_META: Record<'feed' | 'skeleton' | 'resume' | 'interview', DeepMeta> = {
  feed: { /* 照原型行 57–70 */ },
  skeleton: { /* 行 71–84 */ },
  resume: { /* 行 85–98 */ },
  interview: { /* 行 99–112 */ },
};
```
逐字段照原型填(`feed` 节点:锁定赛道/检索岗位/三维打分/排出推荐;工具:lock_track/search_candidates/score_jobs/finalize;等)。**4 个模块全填全**。

- [ ] **Step 2: 单色 Lucide 图标表(从原型 DT_ICONS 行 20–35 移植)**

导出 `ICONS: Record<string,string>`(SVG path 字符串)+ `DTIcon` 渲染辅助;后续 DeepThinkCard 用。**只单色**,无彩色填充(除圆心点)。

- [ ] **Step 3: 验证 lint + build(类型自洽即可)**

Run: `cd resume-copilot-web && npm run lint && npm run build`
Expected: 0 error。

- [ ] **Step 4: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/hub/deep-think-meta.ts
git commit -m "feat(hub): 深度思考卡 4 模块 meta(我的理解+4节点+工具,静态底座)"
```

---

## Task 4: DeepThinkCard(两段式思考卡 — 本期核心组件)

**Files:**
- Create: `resume-copilot-web/components/resume-copilot/workspace/hub/DeepThinkCard.tsx`

照原型 `hub-deepthink.jsx` 的 `DeepThinkCard`(行 169–258)+ `DTStep`(139–166)+ `DTToolBody`(116–136)移植成 TSX。**核心交付**。

- [ ] **Step 1: 组件 props + 阶段机**

```typescript
interface DeepThinkCardProps {
  module: 'feed' | 'skeleton' | 'resume' | 'interview';
  understandOverride?: Partial<DeepUnderstand>;  // HubShell 注入真赛道/记忆
  outputOverride?: Record<number, string>;       // 节点 index → 真计数 output(可选)
  onComplete: () => void;
}
```
三阶段 `phase: 'understand' | 'think' | 'done'`(照原型):
1. `understand`(~1.6s):顶 `我的理解` 小标(spinner→✓)+ headline + 赛道 pill + 记忆 pill(**单色时钟图标**)+ 打字机 reasoning。
2. `think`:逐节点亮(per≈760ms),`思考过程` 展开,连接线 + 圆点状态。
3. `done`:整卡**自动折叠**思考过程成一行 `✓ 思考过程 · N/N · 已完成 ▾`;触发 `onComplete()`。

- [ ] **Step 2: DTStep + DTToolBody(每步可展开 Input/Output + 工具名 + 结果 chips)**

照原型:running 步默认展开看 Input/Output;Output 在 done 用 `outputOverride[i] ?? node.output`(真计数优先)。完成态下方一行结果 chips。**无 border-beam,无彩色小标**。

- [ ] **Step 3: 注入真数据点(留接口,Task 5/6 填)**

`understandOverride` 合并进 `cfg.understand`(真赛道来自 workingQuery.seed_sub_cats、真记忆来自档案 index)。`outputOverride` 在 feed 跑完用 `feed.length`(如 `召回 N → 去重 N`)。本步先支持 override 形参,默认 undefined 时退回静态文案。

- [ ] **Step 4: 验证 lint + build + 计时手测**

Run: `cd resume-copilot-web && npm run lint && npm run build`
Expected: 0 error。临时在 /hub 挂一张 `<DeepThinkCard module="feed" onComplete={()=>{}}/>` 看动效:我的理解 → 4 节点 → 自动折叠,全程一个动效、无气泡、无环绕。手测完移除临时挂载。

- [ ] **Step 5: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/hub/DeepThinkCard.tsx
git commit -m "feat(hub): 深度思考卡 — 我的理解+思考过程两段式,自动折叠,单色无气泡"
```

---

## Task 5: HubShell 状态机(arm/fire 两步 + 对话主轴 + 落地态切换)

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/workspace/hub/HubShell.tsx`
- Create: `resume-copilot-web/components/resume-copilot/workspace/hub/SkillBar.tsx`
- Create: `resume-copilot-web/components/resume-copilot/workspace/hub/HubLanding.tsx`

照原型 `hub-app.jsx` 的 `HubApp`(行 318–531)+ `ChatAxis`(138–175)+ `SkillBar`(110–133)+ `LandingGreeting`(257–293)。

- [ ] **Step 1: SkillBar(composer 上方 3 chip)**

Props `{ active: HubModule|null, onPick(key) }`。3 chip:`职位推荐`/`梯队骨架`/`简历优化`,选中态土红实底。照原型行 110–133。

- [ ] **Step 2: HubLanding(落地态:居中问候 + 打字机 composer + 入口卡 + SkillBar)**

Props `{ selected: HubModule|null, onPick, onSend(text) }`。照原型 `LandingGreeting`:问候 `晚上好，陈思远。今天想看哪个方向？` + 打字机 input(轮转提示 `多来点固收`/`看看券商资管的梯队`…)+ SkillBar + 2 入口卡(职位推荐 / 简历优化)。打字机辅助 `useTypewriterHint`(原型行 179–204)一并移植。

- [ ] **Step 3: HubShell 核心状态 + arm/fire**

照原型 HubApp 的 state:`active(HubSlot)` / `armed(HubModule|null)` / `started(bool)` / `msgs(HubMessage[])` / `thinking` / `busy(ref)`。核心函数:
- `armModule(key)`:profile → 直接 `runSkill('profile')`;否则 toggle `armed`(再点取消)。
- `onSend(text)`:有 `armed` → 落学生发言 + `runSkill(armed)` + 清 armed;无 armed → NL 路由(Task 6)。
- `runSkill(key)`:profile 直接 push turn + 开 panel(不跑技能);否则 push `{kind:'turn',who:'ai',html:SAY[key]}` + push `{kind:'skillrun',module:key}`,`active='none'`(收回全宽看它想)。
- `onSkillComplete(key)`:push `{kind:'result',module:key,data:RESULT[key]}`。
- `openView(key)`:interview → `router.push('/interview/'+sessionId)`;否则 `setActive(key)`。
- `onNew()`:reset started/active/armed/msgs。
将原型 `SKILL_META.say` / `result()` 文案搬进 HubShell 顶部常量(`SAY`/`RESULT_FOR`)。

- [ ] **Step 4: ChatAxis(对话主轴渲染)**

中栏:landing 时渲染 `<HubLanding/>`(居中);started 后渲染 msgs(`turn`→`Turn`、`skillrun`→`DeepThinkCard`、`result`→ResultCard、`trace`→`TraceCard`、`memory`→`MemoryToast`、`intel`→ 复用 intel 渲染)+ `thinking && <DeepThinkCard?>`(注:thinking 走 Task 6 的 NL 微调,用现有 ThinkingCard 还是 DeepThink 看 Task 6)。底部 composer:armed 时上方浮"已激活「X」· 说一句就开始"提示 + SkillBar + `Composer`(真实 props `{chips,placeholder,onSend}`)。ResultCard 内联小组件(原型行 94–107):标题 + body + CTA 按钮(opened 显示"已打开·再看一次")。

- [ ] **Step 5: HubShell 布局三块拼齐**

`<HubSidebar/>` + `ChatAxis` + (`landing ? 空槽轨 EmptySlotRail : <CanvasSlot/>`)。CanvasSlot 先占位(Task 7 填真视图),先渲染一个空 div 占宽。`active`→sidebar 高亮联动。

- [ ] **Step 6: 验证 — 两步激活手测 + lint + build**

Run: `cd resume-copilot-web && npm run lint && npm run build`
Expected: 0 error。手测:进 `/hub?session=1` → 落地居中 → 点「职位推荐」chip 高亮 + 出"说一句就开始" → 打字 → 出思考卡 → 落结果卡;**点 chip 时右槽不动、什么没跑**。

- [ ] **Step 7: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/hub/HubShell.tsx \
        resume-copilot-web/components/resume-copilot/workspace/hub/SkillBar.tsx \
        resume-copilot-web/components/resume-copilot/workspace/hub/HubLanding.tsx
git commit -m "feat(hub): arm/fire 两步状态机 + 对话主轴 + 落地态 + 结果卡"
```

---

## Task 6: 接真后端 — 职位推荐技能跑通(我的理解/计数/feed 真数据)

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/workspace/hub/HubShell.tsx`

把 `feed` 模块的 `runSkill('feed')` 从纯动画接到真 `postRecommendChat`,并把真数据喂进思考卡 + 结果卡 + feed 槽。

- [ ] **Step 1: HubShell 加 sessionId 数据态**

HubShell 持有 `workingQuery: WorkingQuery|null` / `feed: RecommendFeedItem[]` / `deepening: string|null`。挂载时 `getWorkingQuery(sessionId)` 初始化 `workingQuery`(拿 seed_sub_cats 作"我的理解"的真赛道)。`getStudentKbIndex()` 拿记忆条目数/摘要作"记忆 pill"真数据(取 top 2–3 summary)。

- [ ] **Step 2: runSkill('feed') 真请求 + 动画并行**

`runSkill('feed')` 时:同时(a)push skillrun 卡播 4 节点动画,(b)`await postRecommendChat(sessionId, lastUserText)`。响应回来:`setFeed(resp.feed ?? [])`、`setWorkingQuery(resp.working_query)`。把 `understandOverride={tracks: resp.working_query.seed_sub_cats, memory: 记忆摘要}` 与 `outputOverride={1: '召回 '+feed.length+' → 去重 '+feed.length, 3:'第一版 Top 已就绪'}` 透给该 skillrun 卡(存进 message 对象)。动画与真请求**取较慢者**完成后再落结果卡(`onSkillComplete` 等 `postRecommendChat` resolve 且卡动画 done)。

> HubMessage 的 `skillrun` 项扩 `understandOverride?`/`outputOverride?` 字段承载真数据。

- [ ] **Step 3: NL 路由(无 armed 直接打字)**

`onSend` 无 armed:用关键词路由(原型 `fallback` 行 412–434):`梯队|骨架|档次` → skeleton;`简历|打分|优化` → resume;`面试|模拟` → interview;`推荐|岗位|职位|看看|来点` → feed;都不中 → 走 `postRecommendChat` 当微调(push trace + reply + 更新 feed/wq,照 RecommendWorkspaceShell 现有 handleSend 逻辑读一遍对齐)。

- [ ] **Step 4: 结果卡 body 用真计数**

`RESULT_FOR.feed` 文案插入真 `workingQuery.seed_sub_cats.join('·')` + `feed.length`(如"按 投研·券商资管 评估 N 个、匹配 N 个")。

- [ ] **Step 5: 验证 — 真推荐端到端**

确保 dev 后端 :8000 起且 `RECOMMENDATION_V2_ENABLED` 状态已知(若 v2 慢见 plan tranquil-prancing-tiger;本任务**不依赖** v2,postRecommendChat 走现有链路)。手测:`/hub?session=<真实有 confirmed 的 session>` → 推荐 → 思考卡"我的理解"显示真赛道 + 真记忆摘要 → 结果卡显示真岗位数。
Run: `cd resume-copilot-web && npm run lint && npm run build` → 0 error。

- [ ] **Step 6: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/hub/HubShell.tsx
git commit -m "feat(hub): 职位推荐技能接真 postRecommendChat — 我的理解/计数/feed 真数据"
```

---

## Task 7: CanvasSlot + 岗位匹配面板(feed 视图接通)

**Files:**
- Create: `resume-copilot-web/components/resume-copilot/workspace/hub/CanvasSlot.tsx`
- Modify: `resume-copilot-web/components/resume-copilot/workspace/hub/HubShell.tsx`

- [ ] **Step 1: CanvasSlot 容器**

Props `{ active: HubSlot, feedProps, skelProps, profileProps, onClose }`。照原型 `CanvasSlot`(行 232–243):宽度随模块(feed 448 / skeleton 436 / resume 500 / profile 460);`active==='none'` 返回 null。每个视图左边框 + parchment 底。本任务先接 `feed`。

- [ ] **Step 2: 岗位匹配面板 = 复用 RecommendFeedPane**

`active==='feed'` 渲染 `<RecommendFeedPane sessionId={sessionId} workingQuery={workingQuery} feed={feed} setFeed={setFeed} setWorkingQuery={setWorkingQuery} onHighlightCompany={...} onIntel={onIntelToChat} />` + 顶部一个 close 钮(`onClose → setActive('none')`)。**深挖(深度匹配)沿用 RecommendFeedPane 内置 onDeepen → postRecommendDeepen**,无需重写。

- [ ] **Step 3: openView('feed') 接通**

结果卡 CTA「查看岗位」→ `openView('feed')` → `setActive('feed')` → 面板滑出。关掉 → 全宽对话。

- [ ] **Step 4: 验证 — 点开看岗位 + 深挖**

手测:推荐 → 结果卡「查看岗位」→ 右侧岗位匹配面板滑出,真岗位卡;点单卡「深挖这个岗」→ 深度匹配分 + 4 锚点理由填上;关掉回全宽。卡面无 `Base/Enhanced/Pro精排` 黑话(核对 JobCard 文案,若现状露黑话,在此任务顺手改成"匹配/深度匹配/深挖这个岗")。
Run: `npm run lint && npm run build` → 0 error。

- [ ] **Step 5: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/hub/CanvasSlot.tsx \
        resume-copilot-web/components/resume-copilot/workspace/hub/HubShell.tsx
git commit -m "feat(hub): 画布槽 + 岗位匹配面板(复用 FeedPane,点开才出,无黑话)"
```

---

## Task 8: 梯队骨架视图 + 情报/定制回流对话

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/workspace/hub/CanvasSlot.tsx`
- Modify: `resume-copilot-web/components/resume-copilot/workspace/hub/HubShell.tsx`
- Modify: `resume-copilot-web/components/resume-copilot/workspace/recommend/PlatformTierGroup.tsx`

- [ ] **Step 1: CanvasSlot 接 skeleton = 复用 RecommendSkeletonPane**

`active==='skeleton'` 渲染 `<RecommendSkeletonPane sessionId={sessionId} highlightCompany={highlightCompany} onOpenIntel={skelIntel} />` + close 钮。**用真实 RecommendSkeletonPane,不是原型 HFTierGroup**(原型 HFTierGroup ≈ 它,但真实组件已接 getPlatformsByTier)。

- [ ] **Step 2: skelIntel 回流对话**

HubShell 加 `skelIntel(company, ctx)`:push `{kind:'turn',who:'me',html:'讲讲'+company}` → setThinking → 之后 push trace + `{kind:'turn',who:'ai',...}` + `{kind:'intel',...}`(照原型 `skelIntel` 行 474–490,情报无数据则诚实"暂无结构化情报·不编")。接到 `RecommendSkeletonPane` 的 `onOpenIntel`。

- [ ] **Step 3: PlatformTierGroup 加"定制深挖"回调 → 回流**

`PlatformTierGroup` 现有 `onOpenIntel`;**新增可选 `onOpenCoach?(company)`**,在公司卡加"定制深挖"按钮(只在有该回调时显示,不破坏 RecommendWorkspaceShell 现有调用——它不传 onOpenCoach 就不显示)。HubShell 的 `skelCoach(company)`:push me turn + ai turn"要不要现在开一场针对它的模拟面试"(照原型 `skelCoach` 行 491–501)。`RecommendSkeletonPane` 透传新 `onOpenCoach` 到 `PlatformTierGroup`(也加可选 prop,默认不传不显示)。

- [ ] **Step 4: 验证 — 骨架点开 + 回流**

手测:点「梯队骨架」激活 → 打字 → 思考卡(拉取公司/梯队分档/背景定档/铺出全景)→ 结果卡 →「查看全景」→ 骨架面板;点公司卡"讲讲这家" → 对话主轴出情报卡;"定制深挖" → AI 提议模拟面试。RecommendWorkspaceShell `/recommend` 仍正常(onOpenCoach 未传 → 无新按钮 → 无回归)。
Run: `npm run lint && npm run build` → 0 error。

- [ ] **Step 5: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/hub/CanvasSlot.tsx \
        resume-copilot-web/components/resume-copilot/workspace/hub/HubShell.tsx \
        resume-copilot-web/components/resume-copilot/workspace/recommend/PlatformTierGroup.tsx
git commit -m "feat(hub): 梯队骨架视图复用骨架 Pane + 情报/定制回流对话主轴"
```

---

## Task 9: 个人档案 B 闭环视图(复用现有 KB 数据/动作,呈现层重做)

**Files:**
- Create: `resume-copilot-web/components/resume-copilot/workspace/hub/HubProfileView.tsx`
- Modify: `resume-copilot-web/components/resume-copilot/workspace/hub/CanvasSlot.tsx`
- Modify: `resume-copilot-web/components/resume-copilot/workspace/hub/HubShell.tsx`

照原型 `hub-views.jsx` 的 `ProfileView`(行 272–312)+ `InferredCard`(236–270),但**数据接真**:确认信息来自 prefs/confirmed,AI 推断来自 `listStudentExperiences({confirmedOnly:false})` 里 `user_confirmed===false` 的条目。

- [ ] **Step 1: HubProfileView 组件**

两层:
- **确认信息**(权威):从现有偏好/confirmed 字段读(目标赛道 `seed_sub_cats`、城市、求职阶段/毕业、投递类型)。本期若部分字段拿不到,静态兜底 + `// TODO 接 prefs`。
- **AI 推断·待确认**:`listStudentExperiences({confirmedOnly:false, includeArchived:false})` 过滤 `user_confirmed===false` → `InferredCard`(claim=summary,from=raw_excerpt,conf=confidence)。**弱点信号类(weakness_signal)绝不展示**(过滤 category)。
动作:「确认·升为确认信息」→ `confirmStudentExperience(id)`;「否掉」→ `archiveStudentExperience(id)`。乐观更新 UI(confirmed/rejected 态,照原型 InferredCard)。

- [ ] **Step 2: CanvasSlot + HubShell 接 profile**

CanvasSlot `active==='profile'` → `<HubProfileView sessionId onClose />`。`runSkill('profile')`/`armModule('profile')` → push 一句 AI 话(`PROFILE_SAY`)+ `setActive('profile')`,**不跑技能卡、不落结果卡**(spec 例外)。底部头像 + 侧边栏档案项都走这条。

- [ ] **Step 3: 验证 — 档案 B 闭环**

手测:点底部头像 → 档案面板**直接开**(无思考卡);看到"确认信息"+"AI 推断待确认"两层;点「确认」→ 条目升格;点「否掉」→ 划掉。弱点信号不出现。
Run: `npm run lint && npm run build` → 0 error。

- [ ] **Step 4: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/hub/HubProfileView.tsx \
        resume-copilot-web/components/resume-copilot/workspace/hub/CanvasSlot.tsx \
        resume-copilot-web/components/resume-copilot/workspace/hub/HubShell.tsx
git commit -m "feat(hub): 个人档案 B 闭环视图(真 KB 数据,确认/否掉,直接开不跑技能)"
```

---

## Task 10: 简历优化接口位 + 模拟面试全屏入口

**Files:**
- Create: `resume-copilot-web/components/resume-copilot/workspace/hub/ResumeSlotPlaceholder.tsx`
- Modify: `resume-copilot-web/components/resume-copilot/workspace/hub/CanvasSlot.tsx`
- Modify: `resume-copilot-web/components/resume-copilot/workspace/hub/HubShell.tsx`

- [ ] **Step 1: ResumeSlotPlaceholder(接口位占位卡)**

照原型 `ResumePlaceholderView`(行 317–331):虚线文件图标 + "简历优化在 resume-copilot 分支 · 日后它的视图(打分/深度优化)直接塞进同一个槽,不动外壳" + 一个"等 HiFi · 可见不可用" pill。**本期就是占位**(本期三拍板①)。CanvasSlot `active==='resume'` 渲染它 + close 钮。

- [ ] **Step 2: 简历优化技能流走通到占位**

`runSkill('resume')`:正常跑思考卡(解析简历/诚实打分/定位缺口/给出建议 动画)→ 结果卡(`简历打分完成 · 现状 72…〔查看打分报告〕`)→ 点开 `setActive('resume')` → 占位卡。**进入路径同构,只是终点是接口位**(spec §二)。

- [ ] **Step 3: 模拟面试全屏入口**

`openView('interview')` → `router.push('/interview/'+sessionId)`(真路由 `app/interview/[sessionId]`)。结果卡 CTA「进入面试」触发。返回 Hub:`/interview` 页内"返回"按 push `/hub?session='+sessionId`(若 interview 页改动超范围,本期仅保证从 Hub 能跳进;回程按钮留 TODO 注释,不强求改 interview 页)。

- [ ] **Step 4: 验证**

手测:点「简历优化」→ 激活 → 打字 → 思考卡 → 结果卡 →「查看打分报告」→ 占位卡(明示归 resume-copilot)。点「模拟面试」→ 激活 → 打字 → 结果卡「进入面试」→ 跳 `/interview/<sessionId>`。
Run: `npm run lint && npm run build` → 0 error。

- [ ] **Step 5: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/hub/ResumeSlotPlaceholder.tsx \
        resume-copilot-web/components/resume-copilot/workspace/hub/CanvasSlot.tsx \
        resume-copilot-web/components/resume-copilot/workspace/hub/HubShell.tsx
git commit -m "feat(hub): 简历优化接口位占位 + 模拟面试全屏跳转入口"
```

---

## Task 11: 落地漏斗 + 端到端验收 + 黑话清洗复核

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/workspace/hub/HubShell.tsx`(收尾)
- (可选)`resume-copilot-web/app/recommend/recommend-page-inner.tsx` 或落地页 — 加"进 Hub"入口

- [ ] **Step 1: 登录后落地 Hub(漏斗保留)**

确认 onboarding 不被破坏:上传 `/upload` → 确认 `/confirm` → **落 `/hub?session=N`**(把确认页完成后的跳转目标改指 `/hub`,或在落地页加显著"进 Hub"入口)。回访直接 `/hub`。**不删 `/upload` `/confirm` `/recommend`**(spec §十二:漏斗 + 日常编辑面,老页不丢)。具体跳转点读 confirm 页现有 redirect 一处改。

- [ ] **Step 2: 黑话全卡面复核(spec §十三)**

跑一遍 Hub 全流程,核对学生可见文案只剩:岗位匹配 / 匹配 94 / 深度匹配 96 / 深挖这个岗 / 讲讲这家。搜 Hub + 复用组件里有没有漏的 `Base分/Enhanced/used_ai/Pro精排/规则三维分`,有则改 tooltip 或删。

- [ ] **Step 3: 端到端验收清单(spec §十四 9 条逐条核)**

逐条手测并记录:① 两步激活(点 chip 不跑、打字才跑、点开才出面板)② 思考卡单动效/无气泡/自动折叠/真我的理解/无彩色小标 ③ 骨架点开 + 回流 ④ 面试全屏跳转 ⑤ 档案 B 闭环直接开 + 确认/否掉 ⑥ 简历接口位占位 ⑦ 一套赭红 + 侧边栏可收起 ⑧ 卡面无黑话 ⑨ lint+build 0 error。

- [ ] **Step 4: 最终 lint + build + 截图**

Run: `cd resume-copilot-web && npm run lint && npm run build`
Expected: 0 error。截 3–4 张关键态(落地 / 思考卡 / 岗位匹配面板 / 档案 B)存 sync 给用户看。

- [ ] **Step 5: Commit + ACTIVITY**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/hub/HubShell.tsx \
        resume-copilot-web/app/...   # 落地跳转改动的确切文件
git commit -m "feat(hub): 落地漏斗指向 Hub + 端到端验收 + 黑话复核"
```
往 `ACTIVITY.md` 顶部追加一条(产品语言:统一对话 Hub 外壳上线 dev,学生能看到什么变化,测试状态,下一步留给 resume-copilot 分支填简历优化)。

---

## Self-Review(写完计划回看 spec)

- **Spec §一外壳结构** → Task 1/2/5/7(侧边栏 + 主轴 + 画布槽)✓
- **§二 两步激活 + 思考卡两段式 + 4 模块节点 + 个人档案例外** → Task 3/4/5/9 ✓
- **§三 档案 B 闭环** → Task 9 ✓
- **§四 落地态 chip/入口卡** → Task 5 ✓
- **§五 复用清单(真实组件)** → 各 Task 按 §符号速查调真 props ✓
- **§五 骨架卡情报/定制回流** → Task 8 ✓
- **§六 单会话单记忆** → 沿用 sessionId 贯穿(Task 1+6)✓
- **§十一 会话拆分** → 本期延后,Task 2 静态占位 + TODO 注释 ✓(拍板③)
- **§十二 漏斗保留** → Task 11 ✓
- **§十三 黑话清洗** → Task 7 + Task 11 ✓
- **§十四 验收 9 条** → Task 11 逐条 ✓
- **简历优化 = 接口位** → Task 10 占位,不建内部 ✓(拍板①)
- **思考卡真浅层** → Task 6 注真我的理解/计数,工具明细静态 ✓(拍板②)

类型一致性:`HubModule`/`HubSlot`/`HubMessage`/`ResultCardData`/`DeepMeta`/`DeepUnderstand`/`DeepNode` 跨 Task 1/3/4/5 命名一致;复用组件 props 全部按真实 map(§符号速查)。

无占位红旗:每个 Task 的 Step 都给了具体组件/props/真接口名 + 验证命令。原型逐字段对照路径已标(`hub-deepthink.jsx` 行号等)。
