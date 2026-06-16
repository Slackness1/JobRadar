# 深度优化「对话历史」分流 + 删除 设计

> 作者:网站设计线 · 2026-06-16 · 分支 `fix/deep-optimize-conversation-routing`(基线 origin/main `34284eb`)

## 目标(一句话)

修掉编辑器右栏「深度优化」对话历史的三个体验问题,并把「一段简历 = 一个对话」做成稳定模型:
1. 新建对话会沿用上一个对话的内容;
2. 同一账号攒出多段一模一样的对话历史;
3. 历史里无法删除误开的对话;
4. 不同段落(教育 / 某段实习)的深度优化没有分流到各自的对话。

## 范围

**纯前端**,3 个组件 + 对话持久化 blob 加字段。**不碰** `/plan/*` 共享端点、后端零改动。

涉及文件:
- `resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/EditorAIPanel.tsx`(对话路由 / per-conv seed 投递 / 删除 / 后端 plan 对齐协调)
- `resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/ChatThread.tsx`(收 per-conv seed、消费回调、激活时按 section 重对齐)
- `resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/HubHistoryPanel.tsx`(删除按钮 + 行内二次确认)
- `resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/versionTypes.ts`(可选:`Convo` 类型若集中在此则在此扩字段;当前 `Convo` 定义在 `EditorAIPanel.tsx`)

**不在本次范围:** 路线 2(后端 plan 改为每对话一份);自由问 tab(归简历推荐线);写回后前端 profile 不刷新这个独立断层(另案)。

## 根因(已定位)

- **问题①②同一个 bug:** `seed` / `pendingQuote` 是父级状态,被 `ChatThread` 消费后**从不清空**。点「+新建对话」→ 新空 tab 设为激活 → 它的 `ChatThread` 收到仍挂着的旧 `seed`(`seed={t.id===activeTabId ? seed : null}`)→ 非水合 tab(`hydrated.current=false`)seed 守卫不拦 → 又跑一遍 `deepOptimizeStart(旧seed)` → 长出相同开头;反复触发 → 被 `putEditorConversations` 落库 → 攒成多段重复(`EditorAIPanel.tsx:222`、`ChatThread.tsx:300-335`)。
- **问题③:** `closeTab` 只把对话移出打开 tab、留在历史;无「从历史删除」路径,`HubHistoryPanel` 也无删除回调(`EditorAIPanel.tsx:260`)。
- **问题④:** 缺口 CTA 只 `setSeed + setTab('deep')`,谁激活谁抢 seed;若激活 tab 已 `hydrated.current=true`,seed 守卫 `if (hydrated.current) return` 静默丢弃(`EditorAIPanel.tsx:111`、`ChatThread.tsx:303`)。

## 关键约束:后端 plan 是「每 session 一份」

`session.plan_json` 单份。`deep-optimize/start` 注释明写「覆盖现有 plan」并 `_save_plan`(`resume_copilot.py:913,949`);`/plan/turn`、`write-back` 都只认这单份(`resume_copilot.py:1823,955`)。前端多个对话 tab 共用同一后端 plan。

→ 本设计走**路线 1**:前端分流 + 进入对齐;后端零改动。代价:**同时挂两段未写回完的对话来回切,切回去的那段从首问重启**(顺序用法不触发)。用户已确认接受。

---

## 设计

### ① 数据模型:对话绑定段落

`Convo`(当前定义在 `EditorAIPanel.tsx:27`)增两个**持久化**字段:

```ts
interface Convo {
  id: number;
  messages: ChatMsg[];
  updatedAt: string;
  section?: string;   // 绑定的简历段路径,如 'internships.0' / 'education' / 'projects.1';undefined = 自由对话
  label?: string;     // 段落显示名,用于 tab 标题 / 历史标题 / 锁定段横幅
}
```

落库:`persistConvos` 的 body map 里加 `section` / `label`;水合 `getEditorConversations` 的 map 里读回(类型守卫:`typeof c.section === 'string' ? c.section : undefined`)。editor-conversations 后端透传,无 schema 改动。

`__meta__` 元记录不变。

### ② 缺口 / 引用 → 分流(治 ①②④)

**a. seed / pendingQuote 改为按对话 id 投递**

`EditorAIPanel` 内新增两个 state(替代经 overlay 上提的全局 `seed` / `pendingQuote` 投递):
```ts
const [pendingSeedByConv, setPendingSeedByConv] = useState<Record<number, DeepOptimizeStartIn>>({});
const [pendingQuoteByConv, setPendingQuoteByConv] = useState<Record<number, PendingQuote>>({});
```
渲染时每个 `ChatThread` 只收**自己那份**:
```tsx
seed={pendingSeedByConv[t.id] ?? null}
pendingQuote={pendingQuoteByConv[t.id] ?? null}
```
`ChatThread` 消费(start 成功或失败收尾)后回调 `onSeedConsumed(convId)`;父组件从 map 删除该条 → seed 永不泄漏到其它 tab。pendingQuote 同理(消费点是用户发首句 start 时,见 `ChatThread.tsx:425`,改成回调父组件删 per-conv 项)。

> overlay 层原 `seed/setSeed/pendingQuote/setPendingQuote` props:外部(缺口 CTA 在 `EditorScoreReportThick.onOptimize` → `EditorAIPanel.handleOptimize`)与引用(`LeftEdit`/选行引用 → overlay `handleQuote` → 需改成调 `EditorAIPanel` 暴露的路由)。为收敛改动,路由逻辑全部落在 `EditorAIPanel`;overlay 把「引用某段」事件透传给 `EditorAIPanel`(新增 prop 回调或上提 ref)。实现细节在 plan 阶段定;契约是:**任何「优化某段 / 引用某段」都经统一 `routeToSection`**。

**b. 统一路由 `routeToSection`**

```ts
function routeToSection(section: string, label: string, payload: { seed?: DeepOptimizeStartIn; quote?: PendingQuote }): void {
  setTab('deep');
  const existing = convos.find((c) => c.section === section);
  if (existing) {
    openConvo(existing.id);                         // 切回 / 打开它的 tab
    if (existing.messages.length === 0) {           // 只有还空着才补 seed/quote,否则纯切换
      if (payload.seed) setPendingSeedByConv((m) => ({ ...m, [existing.id]: payload.seed! }));
      if (payload.quote) setPendingQuoteByConv((m) => ({ ...m, [existing.id]: payload.quote! }));
    }
    return;
  }
  // 新建绑定该段的对话
  const id = createSectionConvo(section, label);    // addTab 变体:fresh convo 带 section/label,设为激活
  if (payload.seed) setPendingSeedByConv((m) => ({ ...m, [id]: payload.seed! }));
  if (payload.quote) setPendingQuoteByConv((m) => ({ ...m, [id]: payload.quote! }));
}
```
- 缺口 CTA:`handleOptimize(gap, track)` → `routeToSection(gap.section, gap.label, { seed: { section, label, gaps, detail, target_track } })`。
- 引用此段 / 选行引用:`routeToSection(quote.section, quote.label, { quote })`(quote 在用户发首句时才 start,沿用现有 `ChatThread` 逻辑)。

`createSectionConvo` = 现 `addTab` 的变体:`fresh = { id, messages: [], updatedAt, section, label }`,其余(openTabIds 满 3 顶掉激活槽、设激活、persist)不变。

### ③「+」手动新对话 = 真·空白

`addTab`(手动「+」按钮)建 `{ id, messages: [], updatedAt }`(**无 section/seed**)。因 seed 不再全局残留(②a),新空白对话保证空。
- 若用户在空白对话里引用某段 → 走 `routeToSection`:
  - 该段**无对话** → 空白对话**认领**它(给它补 `section/label`,start);
  - 该段**已有对话** → 跳回已有那个(保持一段一对话不重复);空白对话留着,可删。

> 认领实现:`routeToSection` 在「无 existing」分支里,若**当前激活对话恰是空白无 section**,复用它而非再新建(避免空白 orphan 叠空白)。

### ④ 删除(历史里,二次确认)

- `HubHistoryPanel` 每个会话行右侧加 🗑 按钮 → 点一下行内切「确认删除? 删 / 取消」(组件内 local state `confirmingId`,不用 `window.confirm`,贴 HiFi)。点「删」→ `onDeleteConvo(id)`。
- `EditorAIPanel.deleteConvo(id)`:
  - 从 `convos` 移除;
  - 从 `openTabIds` 移除(若在);
  - 若是 `activeTabId` → 切到另一打开 tab(`nextOpen[last]`);
  - **永不删到 0**:若删后 convos 空 → 立即建一个空白对话(复用 `addTab` 逻辑);
  - 清掉该 id 的 `pendingSeedByConv`/`pendingQuoteByConv`;
  - `persistConvos(next, true)`。
- tab 上「右键关闭」(只收起、留历史)保留不变。

### ⑤ 后端单 plan 对齐(路线 1 兜底)

- `EditorAIPanel` 持 `backendPlanSectionRef = useRef<string | null>(null)`(哪段当前占着后端 plan)。
- `ChatThread` 每次 `deepOptimizeStart` 成功后回调 `onClaimPlan(section)` → 父组件写 ref。
- 给每个 `ChatThread` 传 `active: boolean`(= `t.id === activeTabId`)与 `isPlanOwner: boolean`(= `conv.section != null && conv.section === backendPlanSectionRef.current`)。
- `ChatThread`:`useEffect([active])` → 若 `active && section && msgs.length > 0 && !isPlanOwner` → **重新开始这段**:按本对话的 seed(从 section/label/已存 gap 上下文重建一个 `DeepOptimizeStartIn`)调 `deepOptimizeStart`,**消息重置为新首问**,顶部追加一句系统提示「已重新开始这段优化(后端一次只跟一段)」。重启后 `onClaimPlan(section)`。
  - 重建 seed 的入参:section/label 来自 convo;gaps/detail/target_track 在首次 start 时存进 convo(扩 `Convo` 可选 `lastSeed?: DeepOptimizeStartIn`,**仅内存**不必持久化;若重载后丢失则用 `{ section, label, gaps: [], detail: '', target_track }` 兜底重启)。
- 顺序用法(改完一段写回再下一段)永不触发;只有来回切两段未写回完的对话才重启 —— 已确认的可接受限制。

---

## 数据流(改后)

```
[打分缺口「去深度优化这段」]                      [左栏/简历「引用此段」]
        │ handleOptimize(gap,track)                       │ handleQuote(quote)
        └──────────────┬──────────────────────────────────┘
                       ▼
              routeToSection(section,label,{seed|quote})
                       │
        ┌──────────────┴───────────────┐
   该段已有对话?                      没有
   openConvo(existing)          createSectionConvo → 新 tab
   (空才补 seed/quote)          挂 pendingSeed/Quote[newId]
                       │
                       ▼
            ChatThread(收自己那份 seed/quote)
              start 成功 → onSeedConsumed(id) 删 per-conv 项
                        → onClaimPlan(section) 写 backendPlanSectionRef
              激活且 section≠owner 且有消息 → 重新开始这段
```

## 边界 / 错误处理

- **start 失败:** `ChatThread` 仍调 `onSeedConsumed(id)`(避免卡住),thread 内显示失败气泡;用户可重试(seed 已消费 → 重试走 `pendingQuote`/手动)。沿用现有失败兜底文案。
- **demo / 只读 403:** `persistConvos` 已 catch 静默;删除/路由在内存照常生效。
- **水合并发:** `hydratedConvos.current` 守卫保留;路由/删除只在水合后写库(`persistConvos` 内已有 `if (!hydratedConvos.current) return`)。
- **section 缺失的老对话:** 水合回来 `section=undefined` 的历史对话视为自由对话,不参与 reuse 匹配,不触发 plan 对齐重启(`msgs.length>0 && !isPlanOwner` 中 `section` 为空则跳过)。向后兼容。
- **永不 0 对话:** 删除/关闭都保证至少留一个对话(空白)。

## 测试

前端无单测框架强约束,验证以 `npm run lint` + `npm run build` 0 error 为门槛 + 手动验收清单:
1. 缺口 A → 对话 1;缺口 B → 对话 2(不同 tab,内容不串)。
2. 缺口 A 再点 → 跳回对话 1(不新建、不重复)。
3. 点「+」→ 真空白对话(无上一段内容)。
4. 历史里删除一个对话 → 二次确认 → 删除后不再出现;删到最后留一个空白。
5. 顺序:优化 A 写回 → 优化 B,全程后端 plan 正确,无重启提示。
6. 来回切两段未写回完的 A/B:切回的那段出现「已重新开始这段优化」并从首问重启(符合预期限制)。
7. 刷新页面:对话 + section 绑定 + 打开态恢复;无重复增生。
