# 深度优化「对话历史」分流 + 删除 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把编辑器右栏「深度优化」做成「一段简历 = 一个对话」的稳定模型,修掉新对话沿用旧内容 / 历史重复增生 / 不能删 / 不同段不分流四个问题。

**Architecture:** 纯前端。对话绑定 section;seed/pendingQuote 从全局改为按对话 id 投递且消费即清;统一 `routeToSection` 实现「该段已有对话→切回,没有→新建」;历史浮层加删除+行内二次确认;后端单 plan 用「进入 mismatch 段→重新开始」兜底(后端零改动)。

**Tech Stack:** Next.js 16 / React 19 / TypeScript。无前端单测框架——验收门槛 = `npm run lint` + `npm run build` 0 error + 手动验收清单。设计 spec:`docs/superpowers/specs/2026-06-16-deep-optimize-conversation-routing-design.md`。

**通用命令(每个任务收尾都跑):**
```bash
cd /home/chuanbo/projects/JobRadar/.worktrees/resume-copilot/resume-copilot-web
npm run lint    # 必须 0 error(2 个既有 <img> warning 可忽略)
npm run build   # 必须成功
```

---

## File Structure

| 文件 | 职责 | 本计划改什么 |
|---|---|---|
| `resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/EditorAIPanel.tsx` | 右栏外壳 + 对话编排 + 持久化 | Convo 加字段;per-conv seed/quote 投递;routeToSection;deleteConvo;后端 plan 对齐协调 |
| `.../editor/ChatThread.tsx` | 单个对话线程 | 收 per-conv seed/quote + 消费回调;onClaimPlan;激活时按 section 重对齐 |
| `.../editor/HubHistoryPanel.tsx` | 历史浮层 | 会话行加删除按钮 + 行内二次确认 |
| `.../editor/ResumeEditorOverlay.tsx` | 全屏壳 | 去掉死的 `seed` state,引用路径不变(仍 setPendingQuote) |

所有路径前缀 = `resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/`。

---

## Task 1: 对话绑定 section/label(数据模型 + 持久化)

**Files:**
- Modify: `EditorAIPanel.tsx`(`Convo` 接口 `:27`;`persistConvos` `:142`;水合 `useEffect` `:169`)

- [ ] **Step 1: 扩 `Convo` 接口**

`EditorAIPanel.tsx:27` 当前:
```ts
interface Convo {
  id: number;
  messages: ChatMsg[];
  updatedAt: string; // ISO;最近改动(历史按它倒序)
}
```
改为:
```ts
interface Convo {
  id: number;
  messages: ChatMsg[];
  updatedAt: string; // ISO;最近改动(历史按它倒序)
  section?: string;  // 绑定的简历段路径,如 'internships.0' / 'education';undefined = 自由对话
  label?: string;    // 段落显示名(tab 标题 / 历史标题 / 锁定段横幅)
}
```

- [ ] **Step 2: 落库带上 section/label**

`EditorAIPanel.tsx:150-155`(`persistConvos` 内 body map)当前:
```ts
const body: unknown[] = list.map((c, i) => ({
  id: c.id,
  messages: c.messages,
  updatedAt: c.updatedAt,
  title: deriveTitle(c.messages, i + 1),
}));
```
改为:
```ts
const body: unknown[] = list.map((c, i) => ({
  id: c.id,
  messages: c.messages,
  updatedAt: c.updatedAt,
  title: deriveTitle(c.messages, i + 1),
  section: c.section,
  label: c.label,
}));
```

- [ ] **Step 3: 水合读回 section/label**

`EditorAIPanel.tsx:180-186`(水合 `list` map)当前:
```ts
const list: Convo[] = raw
  .filter((c) => c && typeof c.id === 'number')
  .map((c) => ({
    id: c.id as number,
    messages: Array.isArray(c.messages) ? (c.messages as ChatMsg[]) : [],
    updatedAt: typeof c.updatedAt === 'string' ? c.updatedAt : new Date().toISOString(),
  }));
```
改为:
```ts
const list: Convo[] = raw
  .filter((c) => c && typeof c.id === 'number')
  .map((c) => ({
    id: c.id as number,
    messages: Array.isArray(c.messages) ? (c.messages as ChatMsg[]) : [],
    updatedAt: typeof c.updatedAt === 'string' ? c.updatedAt : new Date().toISOString(),
    section: typeof c.section === 'string' ? (c.section as string) : undefined,
    label: typeof c.label === 'string' ? (c.label as string) : undefined,
  }));
```

- [ ] **Step 4: lint + build**

Run(通用命令)。Expected:0 error,build 成功。section/label 是可选字段,旧对话水合为 undefined,向后兼容。

- [ ] **Step 5: Commit**
```bash
cd /home/chuanbo/projects/JobRadar/.worktrees/resume-copilot
git add resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/EditorAIPanel.tsx
git commit -m "feat(hub-resume): 深度优化对话绑定 section/label(持久化)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 2: per-conv seed/quote 投递 + 消费即清(治①②)

这是根治「新对话沿用旧内容 / 重复增生」的核心:seed/quote 不再全局,改为按对话 id 投递,ChatThread 消费后回调父组件删除。

**Files:**
- Modify: `EditorAIPanel.tsx`(新增 per-conv map state;ChatThread 渲染传参 `:560-571`)
- Modify: `ChatThread.tsx`(新增 `onSeedConsumed`/`onQuoteConsumed` props;消费点回调)

- [ ] **Step 1: EditorAIPanel 新增 per-conv 投递 state**

在 `EditorAIPanel.tsx` 的 `useState` 区(`:125-131` 附近,`hydratedConvos` 之后)加:
```ts
// seed/quote 按对话 id 投递(替代全局「谁激活谁抢」)。ChatThread 消费后回调删除该条,
// 保证 seed 永不泄漏到下一个新建/切换的 tab —— 根治「新对话沿用旧内容 / 重复增生」。
const [pendingSeedByConv, setPendingSeedByConv] = useState<Record<number, DeepOptimizeStartIn>>({});
const [pendingQuoteByConv, setPendingQuoteByConv] = useState<Record<number, PendingQuote>>({});
```
确保 `PendingQuote` 已 import(`EditorAIPanel.tsx:10-17` 的 api import 块当前已含 `DeepOptimizeStartIn` / `PendingQuote`,无需改)。

- [ ] **Step 2: 加消费回调**

在 `EditorAIPanel.tsx` 的 `handleTabMsgs`(`:276`)附近加两个 useCallback:
```ts
// ChatThread 消费完它那份 seed → 删除,避免重复 start / 泄漏到其它 tab。
const consumeSeed = useCallback((convId: number) => {
  setPendingSeedByConv((m) => {
    if (!(convId in m)) return m;
    const next = { ...m };
    delete next[convId];
    return next;
  });
}, []);
const consumeQuote = useCallback((convId: number) => {
  setPendingQuoteByConv((m) => {
    if (!(convId in m)) return m;
    const next = { ...m };
    delete next[convId];
    return next;
  });
}, []);
```

- [ ] **Step 3: ChatThread 渲染改成传 per-conv seed/quote + 消费回调**

`EditorAIPanel.tsx:550-573`(`openConvos.map` 渲染 ChatThread)当前关键行:
```tsx
<ChatThread
  sessionId={sessionId}
  mode="deep"
  seed={t.id === activeTabId ? seed : null}
  pendingQuote={t.id === activeTabId ? pendingQuote : null}
  setPendingQuote={setPendingQuote}
  onWriteBack={onWriteBack}
  mock={mock}
  initialMsgs={t.messages}
  onMsgsChange={(msgs) => handleTabMsgs(t.id, msgs)}
/>
```
改为:
```tsx
<ChatThread
  sessionId={sessionId}
  mode="deep"
  seed={pendingSeedByConv[t.id] ?? null}
  pendingQuote={pendingQuoteByConv[t.id] ?? null}
  onSeedConsumed={() => consumeSeed(t.id)}
  onQuoteConsumed={() => consumeQuote(t.id)}
  onWriteBack={onWriteBack}
  mock={mock}
  initialMsgs={t.messages}
  onMsgsChange={(msgs) => handleTabMsgs(t.id, msgs)}
/>
```
注意:删掉了 `setPendingQuote={setPendingQuote}`(ChatThread 不再直接清父级全局,改回调 `onQuoteConsumed`)。

- [ ] **Step 4: ChatThread props 加消费回调,去掉 setPendingQuote**

`ChatThread.tsx:197-213`(`ChatThreadProps`)当前含 `setPendingQuote?: (q: PendingQuote | null) => void;`。改为:
```ts
export interface ChatThreadProps {
  sessionId: number;
  mode: 'deep' | 'free';
  /** 深度优化:从打分缺口播种的首问入参(本对话专属)。null = 没 seed。 */
  seed?: DeepOptimizeStartIn | null;
  /** 「待引用」低调引子(本对话专属);发送时才据此启动。 */
  pendingQuote?: PendingQuote | null;
  /** seed 已消费(start 收尾)→ 通知父组件删除该对话的 pendingSeed。 */
  onSeedConsumed?: () => void;
  /** pendingQuote 已消费(发首句 start 收尾)→ 通知父组件删除该对话的 pendingQuote。 */
  onQuoteConsumed?: () => void;
  /** 写回成功 → 通知父组件把对应段映射成 A4 lit。 */
  onWriteBack?: (section: string) => void;
  /** 无真实 session 时渲染样例对话(离线目测)。 */
  mock?: boolean;
  /** 挂载时一次性水合该 tab 的历史消息。 */
  initialMsgs?: ChatMsg[];
  /** 消息变动时回调(父组件 debounce 落库)。 */
  onMsgsChange?: (msgs: ChatMsg[]) => void;
}
```
对应解构(`ChatThread.tsx:240-250`)把 `setPendingQuote` 替换为 `onSeedConsumed`、`onQuoteConsumed`:
```ts
export function ChatThread({
  sessionId,
  mode,
  seed = null,
  pendingQuote = null,
  onSeedConsumed,
  onQuoteConsumed,
  onWriteBack,
  mock = false,
  initialMsgs,
  onMsgsChange,
}: ChatThreadProps): JSX.Element {
```

- [ ] **Step 5: seed 自动起头的收尾调 onSeedConsumed**

`ChatThread.tsx:327-329`(seed useEffect 的 `.finally`)当前:
```ts
.finally(() => {
  if (alive) setThinking(false);
});
```
改为:
```ts
.finally(() => {
  if (alive) setThinking(false);
  onSeedConsumed?.(); // seed 已消费,父组件删除该对话的 pendingSeed
});
```

- [ ] **Step 6: 引用 start 的消费点改回调**

`ChatThread.tsx:420-451`(`if (!started.current && pendingQuote)` 块)当前内部有 `setPendingQuote?.(null);`(约 `:425`)。删掉那一行,改为在 `.finally` 里调 `onQuoteConsumed?.()`。该块改为:
```ts
if (!started.current && pendingQuote) {
  const q = pendingQuote;
  started.current = true;
  setFocusLabel(q.label);
  setTargetTrack(q.target_track || TARGET_TRACK_FALLBACK);
  const startBody: DeepOptimizeStartIn = {
    section: q.section,
    label: q.label,
    gaps: [],
    detail: `引用片段:\n${q.text}\n\n我的诉求:${v}`,
    target_track: q.target_track || TARGET_TRACK_FALLBACK,
  };
  setThinking(true);
  deepOptimizeStart(sessionId, startBody)
    .then((p) => {
      plan.current = p;
      applyPlanToMsgs(p, true);
    })
    .catch((e) => {
      started.current = false; // 启动失败允许重试
      setMsgs((m) => [
        ...m,
        { kind: 'text', who: 'ai', html: `启动深度优化失败:${e instanceof Error ? e.message : '未知错误'}` },
      ]);
    })
    .finally(() => {
      setThinking(false);
      busy.current = false;
      onQuoteConsumed?.(); // pendingQuote 已消费
    });
  return;
}
```
(其余 `撤掉引用` 按钮在 `:650` 调 `setPendingQuote?.(null)` —— 改为 `onQuoteConsumed?.()`。)

- [ ] **Step 7: lint + build**

Run(通用命令)。Expected:0 error。`setPendingQuote` 在 ChatThread 内的全部引用都已替换为 `onQuoteConsumed`(grep 确认无残留):
```bash
grep -n "setPendingQuote" resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/ChatThread.tsx
```
Expected:无输出。

- [ ] **Step 8: 手动验收**

启动 dev(若未起):`cd resume-copilot-web && npm run dev`(:3001)。开真实 session 编辑器 → 打分缺口点「去深度优化这段」起一段对话 → 点 tab 条「+」新建对话 → **新对话应为空白,不再自动长出上一段的开头**。

- [ ] **Step 9: Commit**
```bash
cd /home/chuanbo/projects/JobRadar/.worktrees/resume-copilot
git add resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/EditorAIPanel.tsx resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/ChatThread.tsx
git commit -m "fix(hub-resume): 深度优化 seed/引用 改按对话投递+消费即清(根治新对话沿用旧内容/重复增生)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 3: routeToSection 分流(治④,一段一对话·复用)

把「优化某段 / 引用某段」统一收口到 `routeToSection`:该段已有对话→切回,没有→新建并 seed。

**Files:**
- Modify: `EditorAIPanel.tsx`(`createSectionConvo` 助手;`routeToSection`;`handleOptimize` 改写;watch overlay `pendingQuote` prop;blank 认领)
- Modify: `ResumeEditorOverlay.tsx`(去掉死的 `seed` state + EditorAIPanel 的 `seed`/`setSeed` 传参)

- [ ] **Step 1: 加 `createSectionConvo` 助手**

`EditorAIPanel.tsx` 的 `addTab`(`:222`)后面加一个变体(建带 section/label 的新对话,返回新 id):
```ts
// 新建一个绑定指定 section 的对话(addTab 变体)。返回新对话 id。
// 满 3 个打开 tab 时顶掉当前激活槽位(被顶会话留在历史)。
const createSectionConvo = useCallback((section: string, label: string): number => {
  const id = nextId.current++;
  const fresh: Convo = { id, messages: [], updatedAt: new Date().toISOString(), section, label };
  setConvos((cs) => {
    const next = [...cs, fresh];
    setOpenTabIds((ot) => {
      const nextOpen =
        ot.length < MAX_OPEN_EDITOR_TABS ? [...ot, id] : ot.map((x) => (x === openRef.current.activeTabId ? id : x));
      openRef.current = { openTabIds: nextOpen, activeTabId: id };
      return nextOpen;
    });
    setActiveTabId(id);
    persistConvos(next, true);
    return next;
  });
  return id;
}, [persistConvos]);
```

- [ ] **Step 2: 加 `routeToSection`**

紧接 `createSectionConvo` 后:
```ts
// 「优化某段 / 引用某段」统一入口:该段已有对话→切回(空才补 seed/quote);没有→新建。
// 例外:当前激活对话恰是「空白无 section」→ 复用它认领该段(避免空白 orphan)。
const routeToSection = useCallback(
  (section: string, label: string, payload: { seed?: DeepOptimizeStartIn; quote?: PendingQuote }): void => {
    setTab('deep');
    const existing = convos.find((c) => c.section === section);
    if (existing) {
      openConvo(existing.id);
      if (existing.messages.length === 0) {
        if (payload.seed) setPendingSeedByConv((m) => ({ ...m, [existing.id]: payload.seed! }));
        if (payload.quote) setPendingQuoteByConv((m) => ({ ...m, [existing.id]: payload.quote! }));
      }
      return;
    }
    // 空白激活对话(无 section、无消息)→ 认领该段,而不是再叠一个空白。
    const activeBlank = convos.find(
      (c) => c.id === openRef.current.activeTabId && !c.section && c.messages.length === 0,
    );
    let targetId: number;
    if (activeBlank) {
      targetId = activeBlank.id;
      setConvos((cs) => {
        const next = cs.map((c) => (c.id === activeBlank.id ? { ...c, section, label } : c));
        persistConvos(next, true);
        return next;
      });
    } else {
      targetId = createSectionConvo(section, label);
    }
    if (payload.seed) setPendingSeedByConv((m) => ({ ...m, [targetId]: payload.seed! }));
    if (payload.quote) setPendingQuoteByConv((m) => ({ ...m, [targetId]: payload.quote! }));
  },
  [convos, openConvo, createSectionConvo, persistConvos, setTab],
);
```

- [ ] **Step 3: `handleOptimize` 改成走 routeToSection**

`EditorAIPanel.tsx:111-120`(`handleOptimize`)当前:
```ts
function handleOptimize(gap: ScoreSectionGap, track: string): void {
  setSeed({
    section: gap.section,
    label: gap.label,
    gaps: gap.gaps,
    detail: gap.detail,
    target_track: track,
  });
  setTab('deep');
}
```
改为:
```ts
function handleOptimize(gap: ScoreSectionGap, track: string): void {
  routeToSection(gap.section, gap.label, {
    seed: {
      section: gap.section,
      label: gap.label,
      gaps: gap.gaps,
      detail: gap.detail,
      target_track: track,
    },
  });
}
```

- [ ] **Step 4: 监听 overlay 传进来的 pendingQuote → 路由 + 清空**

引用(`引用此段`/选行引用)仍由 overlay 的 `handleQuote` 设置 `pendingQuote` prop。在 EditorAIPanel 里把它路由到对应 section 对话,然后清空 overlay 的 pendingQuote。在 `useEffect` 区(`openRef` effect `:136` 之后)加:
```ts
// overlay 传进来的「引用某段」一次性请求 → 路由到该段对话(复用/新建)→ 清空 overlay 全局。
useEffect(() => {
  if (!pendingQuote) return;
  routeToSection(pendingQuote.section, pendingQuote.label || pendingQuote.section, { quote: pendingQuote });
  setPendingQuote(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [pendingQuote]);
```
(`pendingQuote` / `setPendingQuote` 仍是 EditorAIPanel 的 props,本任务保留;`seed`/`setSeed` props 移除,见 Step 5-6。)

- [ ] **Step 5: 移除 EditorAIPanel 的 `seed`/`setSeed` props**

`EditorAIPanel.tsx:59-86`(`EditorAIPanelProps`)删掉:
```ts
  seed: DeepOptimizeStartIn | null;
  setSeed: (s: DeepOptimizeStartIn | null) => void;
```
解构(`:89-109`)同步删 `seed`,`setSeed`。`handleOptimize` 已不用 `setSeed`(Step 3)。tab 红点提示 `:450` 当前 `(seed || pendingQuote)` 改为只看 `pendingQuote` 与 per-conv 是否有待投递:
```tsx
{k === 'deep' && (pendingQuote || Object.keys(pendingSeedByConv).length > 0) && !on && (
  <span style={{ width: 5, height: 5, borderRadius: 999, background: 'var(--terracotta)' }} />
)}
```

- [ ] **Step 6: overlay 去掉死的 `seed` state + 传参**

`ResumeEditorOverlay.tsx:154` 删 `const [seed, setSeed] = useState<DeepOptimizeStartIn | null>(null);`。
`ResumeEditorOverlay.tsx:756-763`(`<EditorAIPanel .../>` 传参)删掉 `seed={seed}` 和 `setSeed={setSeed}` 两行。其余(`pendingQuote`/`setPendingQuote`/`tab`/`setTab`)保留。
若 `DeepOptimizeStartIn` 在 overlay 已无其它引用,删掉它的 import(grep 确认):
```bash
grep -n "DeepOptimizeStartIn" resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/ResumeEditorOverlay.tsx
```
仅剩 import 行则删除该 import 名。

- [ ] **Step 7: lint + build**

Run(通用命令)。Expected:0 error。grep 确认 overlay 不再有 `seed` state:
```bash
grep -nE "\bseed\b|setSeed" resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/ResumeEditorOverlay.tsx
```
Expected:无输出(只剩 `seedInitial` 这类无关命名,确认不是 state)。

- [ ] **Step 8: 手动验收**

编辑器里:① 打分点缺口 A 段「去深度优化这段」→ 对话 1;切回打分点缺口 B 段 →**对话 2(新 tab,内容不串)**。② 再点缺口 A →**跳回对话 1,不新建、不重复**。③ 左栏「引用此段」教育 → 进教育对话;再引用同段 → 跳回同一对话。

- [ ] **Step 9: Commit**
```bash
cd /home/chuanbo/projects/JobRadar/.worktrees/resume-copilot
git add resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/EditorAIPanel.tsx resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/ResumeEditorOverlay.tsx
git commit -m "feat(hub-resume): 深度优化按段分流 routeToSection(一段一对话·已有则复用)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 4: 删除对话(历史浮层 + 行内二次确认)

**Files:**
- Modify: `HubHistoryPanel.tsx`(`onDeleteConvo` prop;会话行加 🗑 + 行内确认 state)
- Modify: `EditorAIPanel.tsx`(`deleteConvo`;传 `onDeleteConvo`)

- [ ] **Step 1: HubHistoryPanel 加 prop + 行内确认 state**

`HubHistoryPanel.tsx:48-64`(`HubHistoryPanelProps`)加:
```ts
  /** 删除一段会话(从历史移除)。 */
  onDeleteConvo?: (id: number) => void;
```
解构(`:69-79`)加 `onDeleteConvo,`。组件内 state 区(`:82-84`)加:
```ts
const [confirmingDelete, setConfirmingDelete] = useState<number | null>(null);
```
并 import `Trash2`:`HubHistoryPanel.tsx:6-14` 的 lucide import 加 `Trash2`。

- [ ] **Step 2: 会话行加删除按钮 + 行内确认**

`HubHistoryPanel.tsx:232-310`(`convos.map` 的会话 `<button>` 行)。问题:当前整行是一个 `<button>`,内部不能再嵌 `<button>`。改成外层 `<div role="button">` + 右侧操作区。把外层 `<button key={c.id} onClick=...>` 改为 `<div key={c.id}>` 容器,内部「主体点击区」用 `<button>`,右侧加删除区。最小改法:把整行外层换成 `<div>`,主体保持可点(onClick 切对话),末尾追加删除控件:

在该行 `</button>`(`:308`)之前、`{on && (...ArrowRight...)}` 之后,插入删除控件;并把最外层 `<button>` 换成 `<div style={{...同样的容器样式..., display:'flex'}}>`,把原 `onClick`(切对话)移到包裹标题的内层可点区。为降低风险,采用如下结构替换整段 `convos.map((c) => {...})`:
```tsx
: convos.map((c) => {
    const on = pickConvo === c.id;
    const confirming = confirmingDelete === c.id;
    return (
      <div
        key={c.id}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          padding: '2px 2px 2px 0',
          borderRadius: 11,
          marginBottom: 2,
          background: on ? 'var(--terracotta-wash)' : 'transparent',
          boxShadow: on ? '0 0 0 1px #eccfb6' : 'none',
        }}
      >
        <button
          onClick={() => {
            setPickConvo(c.id);
            onOpenConvo?.(c.id);
          }}
          style={{
            flex: 1,
            minWidth: 0,
            textAlign: 'left',
            display: 'flex',
            alignItems: 'center',
            gap: 11,
            padding: '10px 11px',
            borderRadius: 11,
            cursor: 'pointer',
            border: 'none',
            background: 'transparent',
          }}
        >
          <span
            style={{
              flex: 'none',
              width: 30,
              height: 30,
              borderRadius: 9,
              display: 'grid',
              placeItems: 'center',
              color: on ? 'var(--terracotta-strong)' : 'var(--stone)',
              background: on ? 'var(--ivory)' : 'var(--library-rail)',
              boxShadow: on ? '0 0 0 1px #eccfb6' : '0 0 0 1px var(--border-warm)',
            }}
          >
            <MessageSquare size={15} />
          </span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                font: `${on ? 600 : 500} 13px var(--font-sans)`,
                color: on ? 'var(--ink)' : 'var(--ink-soft)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {c.title}
            </div>
            <div style={{ font: '400 11px var(--font-mono)', color: 'var(--stone)', marginTop: 2 }}>
              {c.date}
              {c.active ? (
                <span style={{ fontFamily: 'var(--font-sans)', color: 'var(--terracotta-strong)' }}>
                  {' · 当前会话'}
                </span>
              ) : c.open ? (
                <span style={{ fontFamily: 'var(--font-sans)', color: 'var(--olive)' }}>{' · 已在标签'}</span>
              ) : null}
            </div>
          </div>
        </button>
        {confirming ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 'none', paddingRight: 6 }}>
            <button
              onClick={() => {
                onDeleteConvo?.(c.id);
                setConfirmingDelete(null);
              }}
              className="hf-btn primary sm"
              style={{ height: 26, padding: '0 9px', fontSize: 11 }}
            >
              删
            </button>
            <button
              onClick={() => setConfirmingDelete(null)}
              className="hf-btn ghost sm"
              style={{ height: 26, padding: '0 9px', fontSize: 11 }}
            >
              取消
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirmingDelete(c.id)}
            title="删除这段对话"
            aria-label="删除对话"
            style={{
              flex: 'none',
              width: 28,
              height: 28,
              marginRight: 6,
              borderRadius: 8,
              display: 'grid',
              placeItems: 'center',
              cursor: 'pointer',
              border: 'none',
              color: 'var(--stone)',
              background: 'transparent',
            }}
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>
    );
  })
```

- [ ] **Step 3: EditorAIPanel 加 `deleteConvo` + 传 prop**

`EditorAIPanel.tsx` 的 `closeTab`(`:260`)后面加:
```ts
// 从历史彻底删除一段会话:移出 convos + 打开集合;激活则切到其它打开 tab;永不删到 0。
const deleteConvo = useCallback((id: number) => {
  setConvos((cs) => {
    const remaining = cs.filter((c) => c.id !== id);
    // 同步打开集合 / 激活态。
    setOpenTabIds((ot) => {
      let nextOpen = ot.filter((x) => x !== id);
      let nextActive = openRef.current.activeTabId === id ? nextOpen[nextOpen.length - 1] : openRef.current.activeTabId;
      // 删光了 → 立刻补一个空白对话(永不 0)。
      if (remaining.length === 0) {
        const fresh: Convo = { id: nextId.current++, messages: [], updatedAt: new Date().toISOString() };
        remaining.push(fresh);
        nextOpen = [fresh.id];
        nextActive = fresh.id;
      } else if (nextOpen.length === 0) {
        nextOpen = [remaining[remaining.length - 1].id];
        nextActive = nextOpen[0];
      }
      openRef.current = { openTabIds: nextOpen, activeTabId: nextActive };
      setActiveTabId(nextActive);
      return nextOpen;
    });
    persistConvos(remaining, true);
    return remaining;
  });
  // 清掉该对话的待投递项。
  consumeSeed(id);
  consumeQuote(id);
}, [persistConvos, consumeSeed, consumeQuote]);
```

- [ ] **Step 4: 把 onDeleteConvo 接到 HubHistoryPanel**

`EditorAIPanel.tsx:393-417`(`<HubHistoryPanel .../>`)加一行 prop:
```tsx
onDeleteConvo={deleteConvo}
```

- [ ] **Step 5: lint + build**

Run(通用命令)。Expected:0 error。

- [ ] **Step 6: 手动验收**

编辑器 → 历史记录浮层 → 会话历史段:每行有 🗑 → 点一下变「删 / 取消」→ 点「删」对话消失;删到只剩一个、再删 → 自动留一个空白对话(不报错、不空白崩)。

- [ ] **Step 7: Commit**
```bash
cd /home/chuanbo/projects/JobRadar/.worktrees/resume-copilot
git add resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/EditorAIPanel.tsx resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/HubHistoryPanel.tsx
git commit -m "feat(hub-resume): 深度优化历史可删除对话(行内二次确认·永不删到0)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 5: 后端单 plan 对齐(进入 mismatch 段→重新开始)

后端只有一份 `session.plan_json`。保证「当前在操作的对话」始终拥有后端 plan;切回一段 section≠当前 plan 的对话时重新开始它。

**Files:**
- Modify: `EditorAIPanel.tsx`(`backendPlanSectionRef`;给 ChatThread 传 `active`/`isPlanOwner`/`onClaimPlan`)
- Modify: `ChatThread.tsx`(start 后 `onClaimPlan`;`active` 变激活且 mismatch → 重启)

- [ ] **Step 1: EditorAIPanel 记录后端 plan 归属 + 传参**

`EditorAIPanel.tsx` state/ref 区加:
```ts
// 后端只有一份 plan_json;记当前占用它的 section。任何对话 start 成功后认领。
const backendPlanSectionRef = useRef<string | null>(null);
```
ChatThread 渲染(Task 2 Step 3 改过的那段)再加三个 prop:
```tsx
  active={t.id === activeTabId}
  isPlanOwner={!!t.section && t.section === backendPlanSectionRef.current}
  onClaimPlan={(section) => {
    backendPlanSectionRef.current = section;
  }}
```

- [ ] **Step 2: ChatThread props 加 active/isPlanOwner/onClaimPlan**

`ChatThread.tsx` 的 `ChatThreadProps`(Task 2 Step 4 改过)再加:
```ts
  /** 本对话绑定的 section(用于后端单 plan 对齐;自由对话为 undefined)。 */
  section?: string;
  /** 本对话是否为当前激活 tab。 */
  active?: boolean;
  /** 本对话是否当前拥有后端 plan(section === backendPlanSection)。 */
  isPlanOwner?: boolean;
  /** start 成功认领后端 plan → 通知父组件记录归属 section。 */
  onClaimPlan?: (section: string) => void;
```
解构加 `section`, `active = false`, `isPlanOwner = false`, `onClaimPlan`。
渲染传参(EditorAIPanel)再加 `section={t.section}`。

- [ ] **Step 3: start 成功 → onClaimPlan**

`ChatThread.tsx` 两处 `deepOptimizeStart(...).then((p) => {...})`(seed 自动起头 `:314`、引用起头 Task2-Step6 块)在 `applyPlanToMsgs(p, true)` 之后各加一行:
```ts
if (seed?.section) onClaimPlan?.(seed.section);   // seed 路径
```
引用路径用 `onClaimPlan?.(q.section)`。续轮 `planTurn` 不改归属(它操作的就是当前 plan)。

- [ ] **Step 4: 激活且 mismatch → 重新开始这段**

`ChatThread.tsx` 加一个 ref 存「本对话最后一次 seed」(供重启重建入参):
```ts
const lastSeed = useRef<DeepOptimizeStartIn | null>(seed);
```
在 seed useEffect 里(消费 seed 时)同步 `lastSeed.current = seed;`。
新增一个 useEffect(放在 seed useEffect 之后):
```ts
// 后端单 plan 对齐:本对话变激活、有 section、已有消息、但当前不持有后端 plan
// → 它的后端进度已被别的段覆盖,重新开始这段(消息重置为新首问)。
useEffect(() => {
  if (mock || mode !== 'deep') return;
  if (!active || !section || isPlanOwner) return;
  if (msgs.length === 0) return; // 空对话由 seed/quote 正常起头,不在此处理
  let alive = true;
  const body: DeepOptimizeStartIn = lastSeed.current ?? {
    section,
    label: focusLabel || section,
    gaps: [],
    detail: '',
    target_track: targetTrack,
  };
  setMsgs([
    { kind: 'text', who: 'ai', html: '已重新开始这段优化(后端一次只跟一段)。' },
  ]);
  setThinking(true);
  started.current = true;
  deepOptimizeStart(sessionId, body)
    .then((p) => {
      if (!alive) return;
      plan.current = p;
      applyPlanToMsgs(p, true);
      onClaimPlan?.(section);
    })
    .catch((e) => {
      if (!alive) return;
      setMsgs((m) => [...m, { kind: 'text', who: 'ai', html: `重新开始失败:${e instanceof Error ? e.message : '未知错误'}` }]);
    })
    .finally(() => {
      if (alive) setThinking(false);
    });
  return () => {
    alive = false;
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [active, isPlanOwner, section]);
```

- [ ] **Step 5: lint + build**

Run(通用命令)。Expected:0 error。

- [ ] **Step 6: 手动验收**

① 顺序流:优化教育→写回→优化实习,全程无「已重新开始」提示、后端不报错。② 来回切:开教育对话(几轮不写回)→ 开实习对话(几轮)→ 切回教育 tab → 出现「已重新开始这段优化」并从首问重启(符合 spec 接受的限制)。③ 自由对话(无 section)切来切去不触发重启。

- [ ] **Step 7: Commit**
```bash
cd /home/chuanbo/projects/JobRadar/.worktrees/resume-copilot
git add resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/EditorAIPanel.tsx resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/ChatThread.tsx
git commit -m "feat(hub-resume): 深度优化后端单plan对齐(切回mismatch段重启·后端零改动)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## 最终验收清单(全部任务后)

按 spec「测试」节逐条过一遍:
1. 缺口 A → 对话 1;缺口 B → 对话 2,内容不串。
2. 缺口 A 再点 → 跳回对话 1,不新建不重复。
3. 「+」→ 真空白对话(无上一段内容)。
4. 历史删除 → 二次确认 → 删除后不再出现;删到最后留一个空白。
5. 顺序优化(写回后下一段)后端 plan 正确,无重启提示。
6. 来回切两段未写回完的对话:切回的从首问重启 +「已重新开始」提示。
7. 刷新页面:对话 + section 绑定 + 打开态恢复,无重复增生。

最后 `npm run lint && npm run build` 全绿,交 orchestrator merge(不直接 push origin/main)。
