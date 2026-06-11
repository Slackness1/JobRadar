# Fix-2a — 工作台 8 项交互补完 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resume Copilot 工作台 8 项漏接的交互全部接通,SAIF 学生主路径每个按钮真生效。

**Architecture:** 纯前端改动(0 backend)。WorkspaceShell 已有 `setCoachContext` / `onExport` 等基础 state 和 callback,本 plan 主要是把"按钮 onClick"接到现有 callback 上。3 个 Coach 入口(Chat toggle / Composer pill / ChatEmpty 卡)共享一个新统一 `handleEnterCoach` callback。

**Tech Stack:** Next.js 16 / React 19 / TypeScript / Tailwind-less HiFi token CSS

---

## File Structure

本 plan 涉及文件(没有新建文件,全部 modify):

| 文件 | 任务 | 责任 |
|---|---|---|
| `resume-copilot-web/components/resume-copilot/workspace/resume/ResumePreview.tsx` | T1, T2 | 拿掉"对比上一版"按钮 + 接通"导出 PDF" |
| `resume-copilot-web/components/resume-copilot/workspace/SessionMenu.tsx` | T3 | onSwitch / onNew 接 router.push |
| `resume-copilot-web/components/resume-copilot/workspace/WorkspaceShell.tsx` | T3, T4, T5, T6 | 新增 `handleEnterCoach` callback + 透传 |
| `resume-copilot-web/components/resume-copilot/workspace/MiddleChatPane.tsx` | T4 | Chat 顶 toggle + Composer Coach pill → onEnterCoach |
| `resume-copilot-web/components/resume-copilot/workspace/chat/ChatEmpty.tsx` | T4 | "针对一家公司定制" 引导卡 → onEnterCoach |
| `resume-copilot-web/components/resume-copilot/workspace/intel/IntelDrawer.tsx` | T5 | "让我练 →" 接 onMock(seedQuestion) |
| `resume-copilot-web/components/resume-copilot/workspace/rewrite/RewritePane.tsx` | T6 | "再改一版" 接 onRegenerate |

---

### Task 1: 拿掉 Resume "对比上一版" 按钮

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/workspace/resume/ResumePreview.tsx`

- [ ] **Step 1: Locate the 对比上一版 button**

Run: `grep -n "对比上一版" resume-copilot-web/components/resume-copilot/workspace/resume/ResumePreview.tsx`
Expected: 1-2 matches with button JSX.

- [ ] **Step 2: Delete the button JSX + related click handler / state if any**

Edit the file — remove the `<button>` element with "对比上一版" + any `onClick` handler / `useState` it depends on(若有独立 state)。

- [ ] **Step 3: Verify lint + build**

```bash
cd /home/chuanbo/projects/JobRadar/.worktrees/resume-copilot/resume-copilot-web
npm run lint 2>&1 | tail -5
npm run build 2>&1 | tail -5
```

Expected: 0 errors. Build pass.

- [ ] **Step 4: Browser smoke test**

刷新工作台,看右栏简历预览顶部 toolbar — **"对比上一版"按钮应该消失**。

- [ ] **Step 5: Commit**

```bash
cd /home/chuanbo/projects/JobRadar/.worktrees/resume-copilot
git add resume-copilot-web/components/resume-copilot/workspace/resume/ResumePreview.tsx
git commit -m "$(cat <<'EOF'
fix(resume-preview): 拿掉「对比上一版」按钮 — Fix-2a #1

设计有这个按钮但真做需要版本对比后端 endpoint(超 demo 工期),
按用户决策直接拿掉,等 backlog 再补.
EOF
)"
```

---

### Task 2: 接通 Resume "导出 PDF" 按钮

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/workspace/resume/ResumePreview.tsx`

- [ ] **Step 1: 确认现有 onExport prop 链路**

Run: `grep -n "onExport\|export" resume-copilot-web/components/resume-copilot/workspace/RightResumePane.tsx | head -10`
Expected: 看到 `onExport?: () => void` 在 props,且已透传给 ResumePreview。

如果 RightResumePane 没透传给 ResumePreview,需要补 `onExport={onExport}`。

- [ ] **Step 2: 在 ResumePreview 接 "导出 PDF" 按钮的 onClick**

Read `ResumePreview.tsx`,找 "导出 PDF" 按钮,加 `onClick={onExport}` + `disabled={isExporting || !canExport}`。

- [ ] **Step 3: 确认 props 透传链路完整**

WorkspaceShell → RightResumePane → ResumePreview 都要传 `onExport / isExporting / canExport`。如果缺一环,补上。

- [ ] **Step 4: Verify lint + build**

```bash
cd /home/chuanbo/projects/JobRadar/.worktrees/resume-copilot/resume-copilot-web
npm run lint 2>&1 | tail -5
npm run build 2>&1 | tail -5
```

Expected: 0 errors.

- [ ] **Step 5: Browser test**

工作台右栏简历预览 → 点 "导出 PDF" → 浏览器下载 PDF。

- [ ] **Step 6: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/resume/ResumePreview.tsx
git commit -m "fix(resume-preview): 接通「导出 PDF」按钮 — Fix-2a #2

走现有 WorkspaceShell.onExport → /sessions/{sid}/export.pdf 链路.
disabled 当 !canExport(简历没解析完时灰显)或 isExporting(LOAD 中)."
```

---

### Task 3: TopBar SessionMenu — onSwitch + onNew 真生效

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/workspace/SessionMenu.tsx`

- [ ] **Step 1: 看现有 SessionMenu prop / state**

Run: `grep -n "onSwitch\|onNew\|router" resume-copilot-web/components/resume-copilot/workspace/SessionMenu.tsx`
Expected: 可能有 prop callback 但 router push 没接,或者点 session item 没 navigate。

- [ ] **Step 2: 在 SessionMenu 内部加 useRouter + 改 onClick**

Edit SessionMenu.tsx:
- import `useRouter` from `'next/navigation'`
- session list item onClick → `router.push(`/resume-copilot?sessionId=${s.id}`)` + `onClose()`
- "上传新简历 · 开始新会话" 按钮 onClick → `router.push('/upload')` + `onClose()`
- "管理全部简历 →" 按钮 onClick → `router.push('/resume-copilot/sessions')` + `onClose()`

- [ ] **Step 3: Verify lint + build**

```bash
cd /home/chuanbo/projects/JobRadar/.worktrees/resume-copilot/resume-copilot-web
npm run lint 2>&1 | tail -5
npm run build 2>&1 | tail -5
```

- [ ] **Step 4: Browser test**

工作台顶栏 → 点 session chip → 下拉菜单弹出 → 点别的 session → 跳 ?sessionId=N + 整页 reload + 工作台显示新 session 数据。
点"上传新简历" → 跳 /upload。
点"管理全部简历" → 跳 /resume-copilot/sessions。

- [ ] **Step 5: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/SessionMenu.tsx
git commit -m "fix(session-menu): onSwitch/onNew/manage-all 真 router.push — Fix-2a #3

之前 SessionMenu list item / 上传新简历 / 管理全部 三按钮的 onClick
都是 no-op. 接 useRouter,切 session 走 ?sessionId=N 整页 navigate
(决策 ⑦a — 不做原地 swap,避免 state 复杂)."
```

---

### Task 4: Coach 三入口聚合 — Chat toggle + Composer pill + ChatEmpty 卡

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/workspace/WorkspaceShell.tsx`(新 `handleEnterCoach` callback)
- Modify: `resume-copilot-web/components/resume-copilot/workspace/MiddleChatPane.tsx`(2 个入口透传 + onClick wire)
- Modify: `resume-copilot-web/components/resume-copilot/workspace/chat/ChatEmpty.tsx`(1 个入口透传 + onClick wire)

- [ ] **Step 1: 在 WorkspaceShell 新增 handleEnterCoach callback**

Edit `WorkspaceShell.tsx`,在 `handleCustomiseForJob` 之后(line ~243)加:

```tsx
/** Fix-2a #4 (2026-05-27): Chat header toggle / Composer pill / ChatEmpty
 *  引导卡 三个统一入口都用这个 callback。default coach context 决策见 spec §2.2. */
const handleEnterCoach = useCallback((companyOverride?: string) => {
  // 决策优先级:
  // 1. 传入的 company override(从 ChatEmpty 卡 / Chat toggle 等显式触发)
  // 2. activeJobContext 已有的公司
  // 3. recommendations.items[0].company
  // 4. 都没有 → toast 提示后不切
  const company =
    companyOverride
    || activeJobContext?.company
    || recommendations?.items?.[0]?.company
    || '';
  if (!company) {
    // 简化:console.warn,demo 时学生先选过公司就不会跑到这分支
    console.warn('Fix-2a #4: no company available, skip Coach switch');
    return;
  }
  setCoachContext({
    company,
    ch: company,
    pri: 'A',
  });
  setPlanFocusRequest({ focusKind: 'experience' });
}, [activeJobContext, recommendations]);
```

- [ ] **Step 2: 透传 handleEnterCoach 给 MiddleChatPane**

Edit `WorkspaceShell.tsx` 渲染 MiddleChatPane 的地方,加 prop:

```tsx
<MiddleChatPane
  ...
  onEnterCoach={handleEnterCoach}
/>
```

- [ ] **Step 3: MiddleChatPane 加 onEnterCoach prop + 接 chat header toggle + composer Coach pill**

Edit `MiddleChatPane.tsx`:
- props interface 加 `onEnterCoach?: () => void;`
- 找 chat header 的 Chat/Coach toggle(`grep -n "Chat.*Coach\|toggle" MiddleChatPane.tsx`),给 Coach pill 的 onClick 接 `onEnterCoach?.()`
- 找 composer 底部 Coach pill / 工具栏(grep "coach.*pill\|composer"),onClick 接 `onEnterCoach?.()`
- 同时透 onEnterCoach 给 ChatEmpty:`<ChatEmpty onEnterCoach={onEnterCoach} .../>`

- [ ] **Step 4: ChatEmpty 卡 "针对一家公司定制" 接 onEnterCoach**

Edit `ChatEmpty.tsx`:
- 加 prop `onEnterCoach?: () => void;`
- 4 张卡之一 title 含"针对一家公司定制" / "Coach"的,onClick 改成 `onEnterCoach ? onEnterCoach() : onQuickPick(c.prompt)`(fallback 走原 quickPick)

- [ ] **Step 5: Verify lint + build**

```bash
cd /home/chuanbo/projects/JobRadar/.worktrees/resume-copilot/resume-copilot-web
npm run lint 2>&1 | tail -5
npm run build 2>&1 | tail -5
```

- [ ] **Step 6: Browser test — 3 个入口逐个验**

1. 工作台 → chat header 顶部 "Chat / Coach" toggle 点 Coach → 中栏切 CoachPane(看顶栏徽章 + ribbon)
2. 工作台 → 底部 composer 工具栏 "Coach" pill 点 → 同上
3. 工作台 → 没消息时空状态 4 卡 "针对一家公司定制" 点 → 同上

- [ ] **Step 7: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/WorkspaceShell.tsx \
        resume-copilot-web/components/resume-copilot/workspace/MiddleChatPane.tsx \
        resume-copilot-web/components/resume-copilot/workspace/chat/ChatEmpty.tsx
git commit -m "$(cat <<'EOF'
fix(coach-entries): 接通 Chat toggle / Composer pill / ChatEmpty 卡 三个 Coach 入口 — Fix-2a #4

之前只有公司卡「针对这家定制」+ IntelDrawer「用这些做 Coach 定制」两个
入口能切到 Coach. Chat 顶 toggle / 底 composer pill / ChatEmpty 引导卡
三个最直觉的入口全部 no-op — 学生没看到 Coach 模式.

WorkspaceShell 新增 handleEnterCoach 统一 callback(default coach context
3 步 fallback: override / activeJobContext / recommendations[0]),三个入口
共享.
EOF
)"
```

---

### Task 5: Intel "让我练 →" 切 Coach 带题

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/workspace/intel/IntelDrawer.tsx`(扩 onMock signature)
- Modify: `resume-copilot-web/components/resume-copilot/workspace/WorkspaceShell.tsx`(handleIntelMock 接 seedQuestion)
- Modify: `resume-copilot-web/components/resume-copilot/workspace/coach/CoachPane.tsx`(显示 seedQuestion banner — 可选)

- [ ] **Step 1: 找 IntelDrawer 面试题 tab 的 "让我练 →" 按钮**

Run: `grep -n "让我练\|onMock" resume-copilot-web/components/resume-copilot/workspace/intel/IntelDrawer.tsx`
Expected: 看到按钮 JSX + onMock prop 类型(目前是 `() => void`)。

- [ ] **Step 2: 扩 onMock signature + 接按钮 onClick**

Edit `IntelDrawer.tsx`:
- props 改 `onMock?: (seedQuestion?: string) => void;`
- 面试题 tab 每道题旁 "让我练 →" 按钮 onClick:`onClick={() => onMock?.(question.text)}`(传当前题文本)

- [ ] **Step 3: WorkspaceShell handleIntelMock 接 seedQuestion**

Edit `WorkspaceShell.tsx::handleIntelMock`,signature 改 `(seedQuestion?: string) => void`,把 seedQuestion 存进 coachContext 一个新字段:

```tsx
setCoachContext({
  company: intelOpenCompany,
  ch: intelOpenCompany,
  pri: intelOpenContext.priority ?? 'A',
  xhsCount: ...,
  // Fix-2a #5: 学生从 Intel 面试题旁 "让我练" 切过来,带这道题做 STAR context
  seedQuestion,
});
```

CoachContext type interface 加 `seedQuestion?: string;` (in `CoachPane.tsx`).

- [ ] **Step 4: CoachPane 顶部显示 seedQuestion banner(可选)**

Edit `CoachPane.tsx`,如果 `coach.seedQuestion` 非空,在 ribbon header 下方加一行小提示:

```tsx
{coach.seedQuestion ? (
  <div className="workspace-hifi__coach-seed-question">
    <span className="hf-overline">练习题</span>
    <span>「{coach.seedQuestion}」</span>
  </div>
) : null}
```

(CSS 暂用 inline style 或加一个简短 class 进 workspace-theme.css,~10 行。)

- [ ] **Step 5: Verify lint + build**

```bash
cd /home/chuanbo/projects/JobRadar/.worktrees/resume-copilot/resume-copilot-web
npm run lint 2>&1 | tail -5
npm run build 2>&1 | tail -5
```

- [ ] **Step 6: Browser test**

公司卡 → 小红书 badge → IntelDrawer → "面试题" tab → 某道题旁 "让我练 →" → 中栏切 Coach + ribbon 下方显"练习题:「这道题」"。

- [ ] **Step 7: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/intel/IntelDrawer.tsx \
        resume-copilot-web/components/resume-copilot/workspace/WorkspaceShell.tsx \
        resume-copilot-web/components/resume-copilot/workspace/coach/CoachPane.tsx \
        resume-copilot-web/components/resume-copilot/workspace/workspace-theme.css
git commit -m "fix(intel-coach-bridge): Intel「让我练 →」切 Coach 带题 — Fix-2a #5

onMock signature 扩 (seedQuestion?: string), IntelDrawer 面试题 tab 每道
题点「让我练」传题文; WorkspaceShell.handleIntelMock 存进 coachContext.
seedQuestion, CoachPane ribbon 下方显小卡片提示学生要练哪道题."
```

---

### Task 6: Rewrite "再改一版" 重新生成 v0/v2

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/workspace/rewrite/RewritePane.tsx`
- Modify: `resume-copilot-web/components/resume-copilot/workspace/WorkspaceShell.tsx`(handleRewriteRegenerate)

- [ ] **Step 1: 看 RewritePane "再改一版" 按钮 + 现有 onRegenerate 接口**

Run: `grep -n "再改一版\|再来\|onRegenerate" resume-copilot-web/components/resume-copilot/workspace/rewrite/RewritePane.tsx`
Expected: 按钮 JSX + props onRegenerate(可能已经声明但 disabled / 没 wire)。

- [ ] **Step 2: 看 v0v2 API call 现有位置**

Run: `grep -n "postRewriteV0V2\|generate_rewrite" resume-copilot-web/components/resume-copilot/workspace/RightResumePane.tsx | head -5`
Expected: RightResumePane 调用 postRewriteV0V2 的位置(P1 已写)。

- [ ] **Step 3: WorkspaceShell 加 handleRewriteRegenerate**

Edit `WorkspaceShell.tsx`,在 handleMiddleRewriteResult 附近加:

```tsx
const handleRewriteRegenerate = useCallback(async () => {
  if (!rewriteBulletContext || !session) return;
  // 重新调 postRewriteV0V2 用相同 bullet context + 同 session
  // 复用 RightResumePane 的 rewrite 链路 — 把 trigger 暴露给中栏
  // 简化:用 ref + custom event 让 RightResumePane 重新触发
  setRewriteResult(null);  // clear current,触发 RewritePane loading
  // 调 api 拿新一轮 v0/v2
  try {
    const result = await postRewriteV0V2({
      session_id: session.id,
      bullet_id: rewriteBulletContext.bulletId,
      original_text: rewriteBulletContext.originalText,
      section_title: rewriteBulletContext.sectionTitle,
    });
    setRewriteResult(result);
  } catch (e) {
    console.error('Rewrite regenerate failed:', e);
  }
}, [rewriteBulletContext, session]);
```

(注意:`postRewriteV0V2` 签名要跟现有 `RightResumePane` 调用的一致 — 先 grep verify。)

- [ ] **Step 4: 透传给 RewritePane**

```tsx
<RewritePane
  ...
  onRegenerate={handleRewriteRegenerate}
/>
```

- [ ] **Step 5: RewritePane 接 onClick + disabled 态**

Edit `RewritePane.tsx`,"再改一版" 按钮:
- `disabled={!onRegenerate || isRegenerating}`
- `onClick={() => { setIsRegenerating(true); onRegenerate?.(); }}`
- 内部 useState `isRegenerating`,根据 props.rewriteResult 变化 setIsRegenerating(false)

- [ ] **Step 6: Verify lint + build**

```bash
cd /home/chuanbo/projects/JobRadar/.worktrees/resume-copilot/resume-copilot-web
npm run lint 2>&1 | tail -5
npm run build 2>&1 | tail -5
```

- [ ] **Step 7: Browser test**

简历右栏 → bullet 上 ✏️ 编辑 → 中栏切 RewritePane → 看到 v0/v2 候选 → 点"再改一版" → loading → 看到新一轮 v0/v2(可能跟之前类似但 LLM 应该有变化)。

- [ ] **Step 8: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/rewrite/RewritePane.tsx \
        resume-copilot-web/components/resume-copilot/workspace/WorkspaceShell.tsx
git commit -m "fix(rewrite): 「再改一版」按钮真重新生成 v0/v2 — Fix-2a #6

WorkspaceShell.handleRewriteRegenerate 调 postRewriteV0V2 拿新一轮候选,
覆盖 rewriteResult state, RewritePane disabled 期间显 loading."
```

---

### Task 7: Final push + 端到端验收

- [ ] **Step 1: 最后跑一遍 lint + build**

```bash
cd /home/chuanbo/projects/JobRadar/.worktrees/resume-copilot/resume-copilot-web
npm run lint 2>&1 | tail -5
npm run build 2>&1 | tail -5
```

Expected: 0 errors. 全部 routes 编译成功。

- [ ] **Step 2: 用户跑 Fix-2a 验收清单 8 项(spec §2.3)**

```
[ ] 2a-1: IntelDrawer 面试题 tab,点 Q1 旁 "让我练 →" → 中栏切 Coach + ribbon 下方显这道题
[ ] 2a-2: RewritePane 点 "再改一版" → loading + 2 候选刷新
[ ] 2a-3: 右栏简历顶部 "导出 PDF" → 浏览器下载 PDF
[ ] 2a-4: 右栏简历顶部 "对比上一版" 按钮已消失
[ ] 2a-5: TopBar 头像 chip → 下拉 → 点别的 session / 上传新简历 / 管理全部 全部生效
[ ] 2a-6: chat 顶部 Chat/Coach toggle 点 Coach → 切 Coach
[ ] 2a-7: chat composer 底部 Coach pill 点 → 切 Coach
[ ] 2a-8: chat 空状态卡 "针对一家公司定制" → 切 Coach
```

- [ ] **Step 3: Push origin**

```bash
cd /home/chuanbo/projects/JobRadar/.worktrees/resume-copilot
git push origin resume-copilot 2>&1 | tail -5
```

- [ ] **Step 4: 更新 task status**

mark task #103 (Fix-2a) → completed; task #104 (Fix-2b) → in_progress(下一阶段)。

---

## Self-Review

**Spec coverage:** spec §2 列了 8 项 Fix-2a,本 plan 拆成 6 个 implementation task(T1-T6) + Task 7 final 验收。覆盖:
- T1 = 2a-4 拿掉按钮 ✅
- T2 = 2a-3 导出 PDF ✅
- T3 = 2a-5 SessionMenu ✅
- T4 = 2a-6 + 2a-7 + 2a-8 三个 Coach 入口 ✅
- T5 = 2a-1 让我练 ✅
- T6 = 2a-2 再改一版 ✅
- 全覆盖。

**Placeholder scan:** 检查"TBD / TODO / 适当处理 / similar to":
- T6 Step 5 "RewritePane 接 onClick + disabled 态" — 给了完整代码片段 ✅
- T5 Step 4 "CoachPane 顶部显示 seedQuestion banner(可选)" — "可选"是合法的 scope 决策,不是 placeholder
- 无 TBD / TODO 字样。

**Type consistency:**
- `CoachContext` 加 `seedQuestion?: string` 字段 — Task 5 Step 3 标注要在 CoachPane.tsx 改 interface ✅
- `onMock` signature `(seedQuestion?: string) => void` — Task 5 Step 2(IntelDrawer 改 type)+ Step 3(WorkspaceShell 接收)一致 ✅
- `onEnterCoach?: () => void` — Task 4 Step 1(WorkspaceShell 定义)+ Step 3(MiddleChatPane prop)+ Step 4(ChatEmpty prop)一致 ✅

**Risk:**
- T6 `postRewriteV0V2` 签名需要 grep 验证(plan Step 3 already 标注了)— 若 signature 不一致需要在实施时调整
- T5 seedQuestion CSS 是新增的,会加几行进 workspace-theme.css

OK,plan 可执行。
