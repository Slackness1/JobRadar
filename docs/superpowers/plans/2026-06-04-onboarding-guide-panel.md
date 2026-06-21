# 新手「一图看懂」向导面板 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 SAIF 学生加一个「四步看懂」向导面板(网页搭、HiFi 陶土调性、弹窗形式),首登自动弹一次 + 常驻「怎么用」入口,降低第一次上手的摩擦。

**Architecture:** 纯前端,无后端 / 无数据库。内容数据单一来源(`guide-content.ts`)→ 展示组件 `GuidePanel` → 自定义遮罩 `GuideModal`。"已看过"状态存浏览器 `localStorage`。两处宿主(hero 顶栏 + 选简历页顶栏)各挂一个「怎么用」入口;选简历页额外在首登未看过时自动弹。先产出一个自包含 HTML 预览丢 `jobradar-sync` 供本人直接打开确认观感,再落成组件集成。

**Tech Stack:** Next.js 16 App Router + React 19 + TypeScript;现有 HiFi 设计系统(`.hf` scope,陶土 `#c96442` / parchment `#f5f4ed`);`localStorage`。**本仓 `resume-copilot-web` 无单测框架**——验收 = `npm run lint`(0 error)+ `npm run build`(过)+ 手动走查,与既有前端任务一致。

**关键约定(铁律):**
- 新代码全部 scope 在 `.hf` 下,类名前缀 `og-`,**绝不**让样式外溢到 `/interview/*` / workspace / admin。
- 提交只 `git add` 明确列出的文件,**绝不** `git add -A` / `git add .`。
- 不动数据库、不加后端端点、不改 hero 既有登录门逻辑(`handleCTA`)。
- commit message 末尾加 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。

---

## File Structure(先锁定分解)

**新建:**
- `resume-copilot-web/components/onboarding/guide-content.ts` — 内容唯一来源:四步数据 + 标题 + 按钮文案。
- `resume-copilot-web/components/onboarding/guide-seen.ts` — `localStorage` 读写助手(`hasSeenGuide` / `markGuideSeen`),纯函数无 hook。
- `resume-copilot-web/components/onboarding/onboarding-guide.css` — `.hf .og-*` 样式。
- `resume-copilot-web/components/onboarding/GuidePanel.tsx` — 四步主线展示 + hover 展开 + 底部 CTA(纯展示,props 驱动)。
- `resume-copilot-web/components/onboarding/GuideModal.tsx` — 自定义全屏遮罩,包 `GuidePanel`。
- `jobradar-sync/onboarding-guide-preview.html` — 自包含静态预览(Task 1 先交付,供本人浏览器打开)。

**修改:**
- `resume-copilot-web/components/hifi/hifi-hero.tsx` — 顶栏加「怎么用」入口 + 渲染 `GuideModal`。
- `resume-copilot-web/components/resume-copilot/sessions/SessionsPanel.tsx` — 顶栏加「怎么用」入口 + 首登自动弹 + 渲染 `GuideModal`。

---

## Task 0: Worktree + 分支(基于已部署的 origin/main)

**目的:** 把向导建在当前线上基线(`ce13abb`)之上,完工后能干净快进部署,不混入 dev 上其它 WIP。

- [ ] **Step 1: 拉取最新 origin/main 并建 worktree**

Run:
```bash
cd /home/chuanbo/projects/JobRadar
git fetch origin main -q
git worktree add -b feat/onboarding-guide /tmp/jr-onboarding-guide origin/main
```
Expected: `Preparing worktree (new branch 'feat/onboarding-guide')`,HEAD 落在 `ce13abb`。

- [ ] **Step 2: 接上 node_modules(供 lint/build)**

Run:
```bash
ln -sfn /home/chuanbo/projects/JobRadar/resume-copilot-web/node_modules /tmp/jr-onboarding-guide/resume-copilot-web/node_modules
git -C /tmp/jr-onboarding-guide log --oneline -1
```
Expected: 软链建好;HEAD 显示 `ce13abb feat(hifi): hero 去 demo 入口 …`。

- [ ] **Step 3: 确认基线 lint 干净(基准线)**

Run: `cd /tmp/jr-onboarding-guide/resume-copilot-web && npm run lint 2>&1 | tail -5`
Expected: `0 errors`(允许既有 2 个 `<img>` warning)。

> 之后所有 Task 都在 `/tmp/jr-onboarding-guide/resume-copilot-web` 内操作。

---

## Task 1: 内容数据 + 独立 HTML 预览(先交付给本人看)

**Files:**
- Create: `resume-copilot-web/components/onboarding/guide-content.ts`
- Create: `jobradar-sync/onboarding-guide-preview.html`(注意:写到 `/home/ubuntu/jobradar-sync/`,**不在** worktree 内)

- [ ] **Step 1: 写内容唯一来源 `guide-content.ts`**

Create `/tmp/jr-onboarding-guide/resume-copilot-web/components/onboarding/guide-content.ts`:
```ts
import type { ReactNode } from 'react';

import { I } from '@/components/hifi/hifi-primitives';

export interface GuideStep {
  no: number;
  icon: ReactNode;
  title: string;
  what: string;   // 做什么
  value: string;  // 对学生的价值
  detail: string; // hover / 点击展开的补充说明
}

export const GUIDE_TITLE = 'JobRadar 怎么用 · 四步看懂';
export const GUIDE_SUBTITLE = '第一次用?跟着这四步走一遍就懂了。';
export const GUIDE_CTA_LABEL = '立即开始 →';
export const GUIDE_DISMISS_LABEL = '不再提示';

export const GUIDE_STEPS: GuideStep[] = [
  {
    no: 1,
    icon: I.upload(20),
    title: '上传简历',
    what: '传一份简历(PDF / Word),AI 自动读出教育、实习、项目、技能。',
    value: '不用填表,传完就开始。',
    detail: '支持 PDF / Word;解析不全也能手动补,AI 不会编造你没写过的经历。',
  },
  {
    no: 2,
    icon: I.radar(20),
    title: '选赛道 + 细分方向',
    what: '挑想去的金融赛道,再勾二级细分方向(如"公募权益研究员"),AI 帮你预勾最像的。',
    value: '选得越准,后面推荐和打分越贴你。',
    detail: '细分方向会影响岗位推荐排序和简历打分口径;勾错了随时回来改。',
  },
  {
    no: 3,
    icon: I.sparkle(20),
    title: '进工作台(核心)',
    what: '左:梯队骨架(目标公司按稳/匹配/冲刺分档 + 情报)· 中:AI 简历助手(按目标岗诊断 + 改写,不编数字)· 右:简历预览。',
    value: '一屏看清"我能去哪 + 简历差在哪"。',
    detail: '梯队骨架给你目标公司的档次与在招;AI 助手只做诚实诊断,绝不替你编造数字刷分。',
  },
  {
    no: 4,
    icon: I.send(20),
    title: '模拟面试 + 反馈',
    what: '针对某个岗位做模拟面试,AI 逐轮追问 + 给反馈。',
    value: '面试前先练一遍,拿到具体可改点。',
    detail: '可语音可文字;结束后出一份逐维度打分 + 改进建议的面试报告。',
  },
];
```

- [ ] **Step 2: 写自包含 HTML 预览**

Create `/home/ubuntu/jobradar-sync/onboarding-guide-preview.html`(本人可直接双击在浏览器打开;内联样式,无需起服务;文案与 `guide-content.ts` 一致):
```html
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>JobRadar 新手向导 · 预览</title>
<style>
  :root {
    --terracotta:#c96442; --terracotta-strong:#b04f30; --terracotta-wash:#f7e9e2;
    --parchment:#f5f4ed; --ivory:#fffdf8; --ink:#2b2620; --ink-soft:#6f675b;
    --stone:#8a8175; --border-cream:#e7e0d3;
  }
  * { box-sizing:border-box; }
  body { margin:0; background:rgba(40,30,24,0.46); font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
         min-height:100vh; display:flex; align-items:center; justify-content:center; padding:24px; }
  .og-modal { position:relative; width:min(720px,100%); max-height:92vh; overflow-y:auto;
              background:var(--parchment); border-radius:20px; box-shadow:0 24px 60px rgba(0,0,0,0.28);
              padding:32px 32px 24px; }
  .og-close { position:absolute; top:16px; right:16px; width:30px; height:30px; border-radius:15px; border:none;
              cursor:pointer; background:var(--ivory); box-shadow:0 0 0 1px var(--border-cream); color:var(--stone);
              font-size:16px; line-height:1; }
  .og-title { font-family:Georgia,"Songti SC",serif; font-size:24px; color:var(--ink); margin:0 0 4px; }
  .og-sub { font-size:13px; color:var(--ink-soft); margin:0 0 22px; }
  .og-steps { display:flex; flex-direction:column; gap:12px; }
  .og-step { display:flex; gap:14px; padding:14px 16px; border-radius:14px; background:var(--ivory);
             box-shadow:0 0 0 1px var(--border-cream); transition:box-shadow .15s ease, transform .15s ease; cursor:default; }
  .og-step:hover { box-shadow:0 0 0 1.5px var(--terracotta); transform:translateY(-1px); }
  .og-step:hover .og-detail { display:block; }
  .og-ico { flex-shrink:0; width:38px; height:38px; border-radius:10px; display:inline-flex; align-items:center;
            justify-content:center; background:var(--terracotta-wash); color:var(--terracotta); font-size:18px; }
  .og-no { font-family:Georgia,serif; font-size:12px; color:var(--terracotta); font-weight:700; letter-spacing:.08em; }
  .og-st { font-size:15px; font-weight:600; color:var(--ink); margin:2px 0; }
  .og-what { font-size:13px; color:var(--ink-soft); line-height:1.55; }
  .og-val { font-size:12.5px; color:var(--terracotta-strong); margin-top:4px; }
  .og-detail { display:none; margin-top:8px; padding-top:8px; border-top:1px dashed var(--border-cream);
               font-size:12.5px; color:var(--ink-soft); line-height:1.5; }
  .og-foot { display:flex; align-items:center; gap:16px; margin-top:22px; }
  .og-cta { background:var(--terracotta); color:#fff; border:none; border-radius:10px; padding:11px 22px;
            font-size:15px; cursor:pointer; }
  .og-dismiss { margin-left:auto; font-size:12.5px; color:var(--stone); background:none; border:none;
                cursor:pointer; text-decoration:underline; }
</style>
</head>
<body>
  <div class="og-modal">
    <button class="og-close">✕</button>
    <h2 class="og-title">JobRadar 怎么用 · 四步看懂</h2>
    <p class="og-sub">第一次用?跟着这四步走一遍就懂了。</p>
    <div class="og-steps">
      <div class="og-step"><div class="og-ico">⤴</div><div>
        <div class="og-no">STEP 1</div><div class="og-st">上传简历</div>
        <div class="og-what">传一份简历(PDF / Word),AI 自动读出教育、实习、项目、技能。</div>
        <div class="og-val">不用填表,传完就开始。</div>
        <div class="og-detail">支持 PDF / Word;解析不全也能手动补,AI 不会编造你没写过的经历。</div></div></div>
      <div class="og-step"><div class="og-ico">◎</div><div>
        <div class="og-no">STEP 2</div><div class="og-st">选赛道 + 细分方向</div>
        <div class="og-what">挑想去的金融赛道,再勾二级细分方向(如"公募权益研究员"),AI 帮你预勾最像的。</div>
        <div class="og-val">选得越准,后面推荐和打分越贴你。</div>
        <div class="og-detail">细分方向会影响岗位推荐排序和简历打分口径;勾错了随时回来改。</div></div></div>
      <div class="og-step"><div class="og-ico">✦</div><div>
        <div class="og-no">STEP 3</div><div class="og-st">进工作台(核心)</div>
        <div class="og-what">左:梯队骨架(目标公司按稳/匹配/冲刺分档 + 情报)· 中:AI 简历助手(按目标岗诊断 + 改写,不编数字)· 右:简历预览。</div>
        <div class="og-val">一屏看清"我能去哪 + 简历差在哪"。</div>
        <div class="og-detail">梯队骨架给你目标公司的档次与在招;AI 助手只做诚实诊断,绝不替你编造数字刷分。</div></div></div>
      <div class="og-step"><div class="og-ico">➤</div><div>
        <div class="og-no">STEP 4</div><div class="og-st">模拟面试 + 反馈</div>
        <div class="og-what">针对某个岗位做模拟面试,AI 逐轮追问 + 给反馈。</div>
        <div class="og-val">面试前先练一遍,拿到具体可改点。</div>
        <div class="og-detail">可语音可文字;结束后出一份逐维度打分 + 改进建议的面试报告。</div></div></div>
    </div>
    <div class="og-foot">
      <button class="og-cta">立即开始 →</button>
      <button class="og-dismiss">不再提示</button>
    </div>
  </div>
</body>
</html>
```

- [ ] **Step 3: 校验 + 提交**

Run:
```bash
cd /tmp/jr-onboarding-guide/resume-copilot-web && npm run lint 2>&1 | tail -5
ls -la /home/ubuntu/jobradar-sync/onboarding-guide-preview.html
```
Expected: lint `0 errors`(content 文件能编译);预览文件存在。

```bash
cd /tmp/jr-onboarding-guide
git add resume-copilot-web/components/onboarding/guide-content.ts
git commit -m "$(printf 'feat(onboarding): 向导四步内容数据 + 独立 HTML 预览\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

> **CHECKPOINT:** 此处交付物是 `jobradar-sync/onboarding-guide-preview.html`,本人打开看观感/文案。继续后续 Task 不阻塞,但若本人要求改文案,改 `guide-content.ts` + 该 HTML 两处同步。

---

## Task 2: localStorage "已看过" 助手

**Files:**
- Create: `resume-copilot-web/components/onboarding/guide-seen.ts`

- [ ] **Step 1: 写助手**

Create `/tmp/jr-onboarding-guide/resume-copilot-web/components/onboarding/guide-seen.ts`:
```ts
// 向导"已看过"状态 — 浏览器本地,不动数据库。
// key 带版本号:日后面板大改可 bump 到 V2 重新对所有人弹一次。
const GUIDE_SEEN_KEY = 'jobradar.onboarding.guideSeenV1';

export function hasSeenGuide(): boolean {
  if (typeof window === 'undefined') return true; // SSR: 视为已看过, 不自动弹
  return window.localStorage.getItem(GUIDE_SEEN_KEY) === '1';
}

export function markGuideSeen(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(GUIDE_SEEN_KEY, '1');
}
```

- [ ] **Step 2: 校验 + 提交**

Run: `cd /tmp/jr-onboarding-guide/resume-copilot-web && npm run lint 2>&1 | tail -5`
Expected: `0 errors`。

```bash
cd /tmp/jr-onboarding-guide
git add resume-copilot-web/components/onboarding/guide-seen.ts
git commit -m "$(printf 'feat(onboarding): localStorage 已看过状态助手\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task 3: 样式 + GuidePanel(四步主线展示)

**Files:**
- Create: `resume-copilot-web/components/onboarding/onboarding-guide.css`
- Create: `resume-copilot-web/components/onboarding/GuidePanel.tsx`

- [ ] **Step 1: 写样式 `onboarding-guide.css`**

Create `/tmp/jr-onboarding-guide/resume-copilot-web/components/onboarding/onboarding-guide.css`(全部 scope `.hf`,token 带 fallback 兜底):
```css
/* Onboarding「一图看懂」向导 — 全部 scope 在 .hf 下, 类名前缀 og- */
.hf .og-overlay {
  position: fixed; inset: 0; z-index: 1000;
  display: flex; align-items: center; justify-content: center; padding: 24px;
  background: rgba(40, 30, 24, 0.46); backdrop-filter: blur(2px);
  animation: og-fade 0.18s ease;
}
@keyframes og-fade { from { opacity: 0; } to { opacity: 1; } }
.hf .og-modal {
  position: relative; width: min(720px, 100%); max-height: 88vh; overflow-y: auto;
  background: var(--parchment, #f5f4ed); border-radius: 20px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.28); padding: 32px 32px 24px;
}
.hf .og-close {
  position: absolute; top: 16px; right: 16px; width: 30px; height: 30px; border-radius: 15px;
  border: none; cursor: pointer; background: var(--ivory, #fffdf8);
  box-shadow: 0 0 0 1px var(--border-cream, #e7e0d3); color: var(--stone, #8a8175);
  display: inline-flex; align-items: center; justify-content: center;
}
.hf .og-title { font-family: var(--font-serif, Georgia, serif); font-size: 24px; color: var(--ink, #2b2620); margin: 0 0 4px; }
.hf .og-sub { font-size: 13px; color: var(--ink-soft, #6f675b); margin: 0 0 22px; }
.hf .og-steps { display: flex; flex-direction: column; gap: 12px; }
.hf .og-step {
  display: flex; gap: 14px; padding: 14px 16px; border-radius: 14px;
  background: var(--ivory, #fffdf8); box-shadow: 0 0 0 1px var(--border-cream, #e7e0d3);
  cursor: default; transition: box-shadow 0.15s ease, transform 0.15s ease;
}
.hf .og-step:hover { box-shadow: 0 0 0 1.5px var(--terracotta, #c96442); transform: translateY(-1px); }
.hf .og-step__icon {
  flex-shrink: 0; width: 38px; height: 38px; border-radius: 10px;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--terracotta-wash, #f7e9e2); color: var(--terracotta, #c96442);
}
.hf .og-step__no { font-family: var(--font-serif, Georgia, serif); font-size: 12px; color: var(--terracotta, #c96442); font-weight: 700; letter-spacing: 0.08em; }
.hf .og-step__title { font-size: 15px; font-weight: 600; color: var(--ink, #2b2620); margin: 2px 0; }
.hf .og-step__what { font-size: 13px; color: var(--ink-soft, #6f675b); line-height: 1.55; }
.hf .og-step__value { font-size: 12.5px; color: var(--terracotta-strong, #b04f30); margin-top: 4px; }
.hf .og-step__detail { margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--border-cream, #e7e0d3); font-size: 12.5px; color: var(--ink-soft, #6f675b); line-height: 1.5; }
.hf .og-foot { display: flex; align-items: center; gap: 16px; margin-top: 22px; }
.hf .og-dismiss { margin-left: auto; font-size: 12.5px; color: var(--stone, #8a8175); background: none; border: none; cursor: pointer; text-decoration: underline; }
@media (max-width: 560px) {
  .hf .og-modal { padding: 22px 18px 18px; }
  .hf .og-title { font-size: 20px; }
}
```

- [ ] **Step 2: 写 `GuidePanel.tsx`**

Create `/tmp/jr-onboarding-guide/resume-copilot-web/components/onboarding/GuidePanel.tsx`:
```tsx
'use client';

import { useState } from 'react';

import { HFBtn } from '@/components/hifi/hifi-primitives';
import {
  GUIDE_CTA_LABEL,
  GUIDE_DISMISS_LABEL,
  GUIDE_STEPS,
  GUIDE_SUBTITLE,
  GUIDE_TITLE,
} from './guide-content';
import './onboarding-guide.css';

interface GuidePanelProps {
  onStart: () => void;
  onDismiss: () => void;
}

export function GuidePanel({ onStart, onDismiss }: GuidePanelProps) {
  const [openStep, setOpenStep] = useState<number | null>(null);
  return (
    <div className="og-panel">
      <h2 className="og-title">{GUIDE_TITLE}</h2>
      <p className="og-sub">{GUIDE_SUBTITLE}</p>
      <div className="og-steps">
        {GUIDE_STEPS.map((step) => (
          <div
            key={step.no}
            className="og-step"
            onMouseEnter={() => setOpenStep(step.no)}
            onMouseLeave={() => setOpenStep((s) => (s === step.no ? null : s))}
            onClick={() => setOpenStep((s) => (s === step.no ? null : step.no))}
          >
            <span className="og-step__icon">{step.icon}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="og-step__no">STEP {step.no}</div>
              <div className="og-step__title">{step.title}</div>
              <div className="og-step__what">{step.what}</div>
              <div className="og-step__value">{step.value}</div>
              {openStep === step.no ? <div className="og-step__detail">{step.detail}</div> : null}
            </div>
          </div>
        ))}
      </div>
      <div className="og-foot">
        <HFBtn variant="primary" size="lg" onClick={onStart}>
          {GUIDE_CTA_LABEL}
        </HFBtn>
        <button type="button" className="og-dismiss" onClick={onDismiss}>
          {GUIDE_DISMISS_LABEL}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 校验 + 提交**

Run: `cd /tmp/jr-onboarding-guide/resume-copilot-web && npm run lint 2>&1 | tail -5`
Expected: `0 errors`。

```bash
cd /tmp/jr-onboarding-guide
git add resume-copilot-web/components/onboarding/onboarding-guide.css resume-copilot-web/components/onboarding/GuidePanel.tsx
git commit -m "$(printf 'feat(onboarding): GuidePanel 四步主线展示 + hover 展开 + 样式\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task 4: GuideModal(自定义遮罩)+ 首次 build 把关

**Files:**
- Create: `resume-copilot-web/components/onboarding/GuideModal.tsx`

- [ ] **Step 1: 写 `GuideModal.tsx`**

Create `/tmp/jr-onboarding-guide/resume-copilot-web/components/onboarding/GuideModal.tsx`:
```tsx
'use client';

import type { ReactNode } from 'react';

import { I } from '@/components/hifi/hifi-primitives';

interface GuideModalProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

export function GuideModal({ open, onClose, children }: GuideModalProps) {
  if (!open) return null;
  return (
    <div className="hf og-overlay" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="og-modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="og-close" aria-label="关闭" onClick={onClose}>
          {I.close(16)}
        </button>
        {children}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 全量 build 把关(组件全齐,确认无类型错误)**

Run: `cd /tmp/jr-onboarding-guide/resume-copilot-web && npm run lint 2>&1 | tail -5 && npm run build 2>&1 | tail -15`
Expected: lint `0 errors`;build 成功(出现 Route 列表,无 `Failed to compile`)。

- [ ] **Step 3: 提交**

```bash
cd /tmp/jr-onboarding-guide
git add resume-copilot-web/components/onboarding/GuideModal.tsx
git commit -m "$(printf 'feat(onboarding): GuideModal 自定义遮罩 (.hf scope)\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task 5: Hero 顶栏接入「怎么用」入口

**Files:**
- Modify: `resume-copilot-web/components/hifi/hifi-hero.tsx`

> 背景:hero 顶栏在 `HFHero()` 内,结构为 `<div className="hf-hero-page__nav"><HFLogo /><div ...>{loggedIn ? <UserBadge/> : <登录按钮>}</div></div>`。hero 的「怎么用」是**手动打开**,关闭**不**写 `markGuideSeen`(首登自动弹只由选简历页负责,避免未登录访客在 hero 看过就压掉学生的首登弹窗)。

- [ ] **Step 1: 加 import**

在 `import { AuthModal } from './auth-modal';` 之后加:
```tsx
import { GuideModal } from '@/components/onboarding/GuideModal';
import { GuidePanel } from '@/components/onboarding/GuidePanel';
```

- [ ] **Step 2: 加 state**

在 `const [loggedIn, setLoggedIn] = useState(false);` 之后加:
```tsx
  const [guideOpen, setGuideOpen] = useState(false);
```

- [ ] **Step 3: 顶栏加「怎么用」按钮**

把顶栏右侧那块:
```tsx
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {loggedIn ? (
```
改成(在条件块前插入「怎么用」按钮):
```tsx
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <HFBtn variant="link" size="sm" icon={I.book(14)} onClick={() => setGuideOpen(true)}>
            怎么用
          </HFBtn>
          {loggedIn ? (
```

- [ ] **Step 4: 渲染 GuideModal**

在 `<AuthModal ... />`(`onSuccess={onLoginSuccess}` 那个)之后、组件最外层 `</div>` 之前加:
```tsx
      <GuideModal open={guideOpen} onClose={() => setGuideOpen(false)}>
        <GuidePanel
          onStart={() => {
            setGuideOpen(false);
            handleCTA('/upload');
          }}
          onDismiss={() => setGuideOpen(false)}
        />
      </GuideModal>
```
> `onStart` 复用 hero 既有 `handleCTA('/upload')` —— 未登录会先弹登录门,登录门逻辑不变。

- [ ] **Step 5: 校验 + 提交**

Run: `cd /tmp/jr-onboarding-guide/resume-copilot-web && npm run lint 2>&1 | tail -5`
Expected: `0 errors`(`HFBtn` / `I` hero 已 import,无新增未用变量)。

```bash
cd /tmp/jr-onboarding-guide
git add resume-copilot-web/components/hifi/hifi-hero.tsx
git commit -m "$(printf 'feat(onboarding): hero 顶栏「怎么用」入口接 GuideModal\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task 6: 选简历页接入(常驻入口 + 首登自动弹)

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/sessions/SessionsPanel.tsx`

> 背景:`SessionsPanel()` 渲染 `.hf .rc-sessions`,顶部 topbar 含 `HFLogo` 与用户头像。它已 import `{ HFBtn, HFLogo, I }`。这里既加常驻「怎么用」入口,又在首登未看过时自动弹;关闭/开始/不再提示都写 `markGuideSeen`。

- [ ] **Step 1: 加 import**

在现有 `import { HFBtn, HFLogo, I } from '@/components/hifi/hifi-primitives';` 之后加:
```tsx
import { GuideModal } from '@/components/onboarding/GuideModal';
import { GuidePanel } from '@/components/onboarding/GuidePanel';
import { hasSeenGuide, markGuideSeen } from '@/components/onboarding/guide-seen';
```

- [ ] **Step 2: 加 state + 首登自动弹 effect**

在 `SessionsPanel()` 内、`const router = useRouter();` 附近的 state 区加:
```tsx
  const [guideOpen, setGuideOpen] = useState(false);
```
在组件已有的 `useEffect` 区(挂载初始化那些)旁,新增一个只跑一次的 effect:
```tsx
  useEffect(() => {
    if (!hasSeenGuide()) {
      setGuideOpen(true);
    }
  }, []);
```
> ESLint 若提示 deps,这个 effect 故意空依赖(只在挂载判一次);如报错按既有文件里其它空依赖 effect 的写法对齐(必要时同样加 `// eslint-disable-next-line react-hooks/exhaustive-deps` 或项目惯用注释)。

- [ ] **Step 3: 定义关闭处理 + 渲染 GuideModal**

在组件内定义(放在 return 之前的 handler 区):
```tsx
  const closeGuide = () => {
    markGuideSeen();
    setGuideOpen(false);
  };
  const startFromGuide = () => {
    markGuideSeen();
    setGuideOpen(false);
    router.push('/upload');
  };
```
在 `SessionsPanel` 返回 JSX 的**最外层容器末尾**(`.hf .rc-sessions` 根 `</div>` 之前)加:
```tsx
      <GuideModal open={guideOpen} onClose={closeGuide}>
        <GuidePanel onStart={startFromGuide} onDismiss={closeGuide} />
      </GuideModal>
```

- [ ] **Step 4: topbar 加常驻「怎么用」入口**

在 topbar 里(`HFLogo` 与用户头像所在那行的右侧区域)加一个按钮,点击手动打开(不预先 mark,关闭时才 mark):
```tsx
            <HFBtn variant="link" size="sm" icon={I.book(14)} onClick={() => setGuideOpen(true)}>
              怎么用
            </HFBtn>
```
> 放在用户头像/返回工作台按钮同一个 flex 容器内即可;`HFBtn` / `I` 文件已 import。

- [ ] **Step 5: 校验 + build + 提交**

Run: `cd /tmp/jr-onboarding-guide/resume-copilot-web && npm run lint 2>&1 | tail -5 && npm run build 2>&1 | tail -12`
Expected: lint `0 errors`;build 成功。

```bash
cd /tmp/jr-onboarding-guide
git add resume-copilot-web/components/resume-copilot/sessions/SessionsPanel.tsx
git commit -m "$(printf 'feat(onboarding): 选简历页常驻「怎么用」入口 + 首登自动弹\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Task 7: 端到端走查 + 交付

**Files:** 无新增(验收 + 收尾)。

- [ ] **Step 1: 终态 lint + build**

Run: `cd /tmp/jr-onboarding-guide/resume-copilot-web && npm run lint 2>&1 | tail -5 && npm run build 2>&1 | tail -12`
Expected: lint `0 errors`;build 成功。

- [ ] **Step 2: 本地起 dev 手动走查(非 sudo,挑个空闲端口如 3005)**

Run(后台起): `cd /tmp/jr-onboarding-guide/resume-copilot-web && npm run dev -- -p 3005`
逐项核对(本人可经 SSH 隧道 `ssh -L 3005:127.0.0.1:3005 devvps` 看,或交付截图):
1. 浏览器控制台 `localStorage.removeItem('jobradar.onboarding.guideSeenV1')` → 登录落选简历页 → **自动弹一次**。
2. 关闭 / 勾「不再提示」/ 点「立即开始」→ 刷新 → **不再自动弹**。
3. 首页「怎么用」、选简历页「怎么用」→ 任何时候点都能打开。
4. 首页未登录也能点开「怎么用」。
5. 悬停某一步高亮 + 展开补充说明;窄屏(手机视宽)排版正常、四步可读。
6. 打开向导时 `/interview` 与 workspace 调色未被影响(`.hf` 隔离没漏)。

- [ ] **Step 3: 追加 ACTIVITY.md(产品语言一条)**

在 `/home/chuanbo/projects/JobRadar/ACTIVITY.md`(主仓)顶部 `## 2026-06-04` 下追加一条:做了什么(新手四步向导)/ 学生能看到什么 / 验证状态 / 下一步(部署待本人点头)。

- [ ] **Step 4: 交付汇报 + 等部署指令**

产品语言汇报;**部署到生产需本人显式点头**,走 `jobradar-vps-deploy`(`feat/onboarding-guide` 是基于 `origin/main` 的干净快进,前端重 build,只重启前端服务)。完工后清理 worktree:
```bash
rm -f /tmp/jr-onboarding-guide/resume-copilot-web/node_modules
cd /home/chuanbo/projects/JobRadar && git worktree remove /tmp/jr-onboarding-guide --force
```

---

## Self-Review(对照 spec 核对)

**Spec coverage:**
- §2 形态(网页面板 / 弹窗 / 首登自动弹+常驻入口 / HiFi / 不配截图)→ Task 1/3/4/5/6 全覆盖。
- §3 四步内容 → Task 1 `guide-content.ts` 逐字落地。
- §4 轻交互(hover 高亮 + 展开 + 移动端可点)→ Task 3 `GuidePanel`(onMouseEnter/Leave + onClick toggle)。
- §5 触发与状态(localStorage key、首登自动弹、关闭即标记、常驻入口、纯客户端)→ Task 2 + Task 6。
- §6 组件结构(GuidePanel / GuideModal / 状态助手 / 入口 / 自动弹接线,`.hf` 隔离)→ Task 2-6 一一对应。
- §7 验收(lint/build/六项手动走查/隔离)→ Task 7。
- §8 交付两段(独立 HTML 先行 + 落组件集成)→ Task 1(HTML)+ Task 3-6(组件)。
- §9 上线(纯前端、无迁移、只重启前端)→ Task 7 Step 4。

**Placeholder scan:** 无 TBD/TODO;每个代码步给了完整代码;命令带预期输出。

**Type consistency:** `GuideStep` 字段(no/icon/title/what/value/detail)在 `guide-content.ts` 定义,`GuidePanel` 全部按此读;`GuideModal` props(open/onClose/children)与 hero/sessions 调用一致;`hasSeenGuide` / `markGuideSeen` 命名两处调用一致;localStorage key `jobradar.onboarding.guideSeenV1` Task 2 定义、Task 7 走查复用同名。
