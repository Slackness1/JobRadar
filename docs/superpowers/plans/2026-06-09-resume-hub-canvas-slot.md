# 简历优化接进 Hub 画布槽 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement task-by-task. Steps use checkbox (`- [ ]`).

**Goal:** 把简历优化的「打分报告侧面板」+「全屏编辑器」做出来,塞进网站设计 orchestrator 留的 Hub 画布槽接口位(`CanvasSlot` 的 `active==='resume'` 分支),照原型 `hub-views.jsx::ResumeView` / `hub-editor*.jsx` 逐字段还原。

**Architecture:** 自包含 React 组件,挂载契约 = orchestrator 传 `{ sessionId, onExpandEditor, onClose }`。打分报告是侧面板(宽 ~500),编辑器是它右上角「展开编辑器」进的全屏 overlay(**自管 `editorOpen` 态**)。进入路径铁律:先打分报告 → 再展开编辑器,不跳过打分。复用已建后端(score / deep-optimize / plan-turn / apply-rewrite)。设计系统用 `.hf` 赭红 token(`components/hifi/hifi-tokens.css` 已含全部所需 token + `hf-btn/hf-pill/hf-overline`)。

**Tech Stack:** Next.js 16 App Router + React + TS;`.hf` 设计系统;后端 FastAPI 现有端点。前端无单测惯例 → 每任务验收 = `npm run lint`(0 error)+ `npm run build` + 对照原型人工目测(独立 mount 页)。

**关键事实(已核实,别重查):**
- `resume-copilot-web/components/resume-copilot/api.ts` 已有 `scoreResume(sessionId, targetTrack)` + `requestJson`(自动注入 `X-Resume-User-Key`)+ `ScoreReportData`/`ScoreSectionGap`/`ScoreDimension` 类型。**缺** `deepOptimizeStart` / `planTurn` / `applyRewrite` 封装。
- `hifi-tokens.css` 已含原型用到的全部 token(--terracotta/-strong/-wash、--ivory、--parchment、--olive、--stone、--border-warm/-strong、--library-rail、--sh-ring、--ink、--font-mono/-sans)+ `.hf-btn`(变体 ghost/primary/sand/dark/sm)/`.hf-pill`(变体 terra)/`.hf-overline`。**直接用,别重造 token。**
- 原型源:`git show hub-shell-frontend:docs/superpowers/specs/hub-prototype-2026-06-09/hub/hub-views.jsx`(ResumeView 行 396–464 / HubRadar 行 346–365 / ResumeA4)。编辑器:同分支 `hub/hub-editor.jsx` + `hub/hub-editor-ai.jsx`(Phase 2 开始时读)。
- 后端端点(都带 owner + `_assert_not_demo`):`POST /api/resume-copilot/sessions/{id}/score`、`POST .../deep-optimize/start`(入参 `{section,label,gaps,detail,target_track}`)、`POST .../plan/turn`、`POST .../chat/apply-rewrite`。
- `CanvasSlot.tsx` orchestrator 还没提交 → Phase 1 用独立 mount 页目测;真正塞进 CanvasSlot 在 orchestrator 冻结接口后做(Task 1.7 产出可交付的 panel 组件 + 契约)。

**目录约定(handoff 要求,别污染 hub 根):** 全部新组件放 `resume-copilot-web/components/resume-copilot/workspace/hub/resume/`。

---

## Phase 0:分支 + 目录

### Task 0:建分支 + 子目录

**Files:** 无代码,仅 git + mkdir

- [ ] **Step 1: 从 resume-copilot 建分支**
```bash
cd /home/chuanbo/projects/JobRadar/.worktrees/resume-copilot
git checkout -b hub-resume-optimize
git branch --show-current   # 期望 hub-resume-optimize
```

- [ ] **Step 2: 建组件子目录**
```bash
mkdir -p resume-copilot-web/components/resume-copilot/workspace/hub/resume
```

- [ ] **Step 3: Commit 占位(.gitkeep 不需要,跳过;下个 Task 直接产文件)**

---

## Phase 1:打分报告侧面板(主交付)

### Task 1:API 封装补齐(deep-optimize / plan-turn / apply-rewrite)

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/api.ts`

- [ ] **Step 1: 看现有 scoreResume + requestJson 写法**
```bash
sed -n '155,230p' resume-copilot-web/components/resume-copilot/api.ts
```
Expected: 看到 `requestJson<T>` 注入 `X-Resume-User-Key`,`scoreResume` 用 `requestJson` POST。

- [ ] **Step 2: 加类型 + 三个封装(追加到 api.ts 末尾,scoreResume 之后)**
```typescript
// ── 深度优化(反问取证)──────────────────────────────────────────────
export interface DeepOptimizeStartIn {
  section: string;
  label: string;
  gaps: string[];
  detail: string;
  target_track: string;
}
// PlanState 出参结构宽松,前端只读 items/current_item_id/status
export interface PlanOpenQuestion { id: string; text: string; answered_at: string | null }
export interface PlanItem {
  id: string; kind: string; title: string; status: string;
  open_questions: PlanOpenQuestion[]; rationale?: string | null;
  draft?: { text: string } | null;
}
export interface PlanStateOut {
  status: string; current_item_id: string | null; items: PlanItem[]; version: number;
}

export function deepOptimizeStart(sessionId: number, body: DeepOptimizeStartIn): Promise<PlanStateOut> {
  return requestJson<PlanStateOut>(`/api/resume-copilot/sessions/${sessionId}/deep-optimize/start`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function planTurn(sessionId: number, message: string): Promise<PlanStateOut> {
  return requestJson<PlanStateOut>(`/api/resume-copilot/sessions/${sessionId}/plan/turn`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}

export interface ApplyRewriteResult {
  field_path: string;
  applied_text: string;
}
export function applyRewrite(sessionId: number, fieldPath: string, text: string): Promise<ApplyRewriteResult> {
  return requestJson<ApplyRewriteResult>(`/api/resume-copilot/sessions/${sessionId}/chat/apply-rewrite`, {
    method: 'POST',
    body: JSON.stringify({ field_path: fieldPath, text }),
  });
}
```

- [ ] **Step 3: 核对 plan/turn 与 apply-rewrite 真实入参**(避免出参/入参对不齐)
```bash
cd /home/chuanbo/projects/JobRadar/.worktrees/resume-copilot/backend
grep -n "class.*PlanTurnIn\|class ApplyRewriteIn\|post_plan_turn\|apply-rewrite" app/schemas_resume_copilot.py app/routers/resume_copilot.py | head
```
若入参字段名与 Step 2 不符(如 plan/turn 用 `user_message`、apply-rewrite 用别的键),按真实 schema 修正 Step 2 的 body 键名后再继续。

- [ ] **Step 4: lint**
```bash
cd resume-copilot-web && npm run lint 2>&1 | tail -3
```
Expected: 0 errors(api.ts 不应引入未用变量)。

- [ ] **Step 5: Commit**
```bash
git add resume-copilot-web/components/resume-copilot/api.ts
git commit -m "feat(hub-resume): api.ts 补 deep-optimize/plan-turn/apply-rewrite 封装"
```

---

### Task 2:HubRadar 组件(8 维雷达,逐字段照搬原型)

**Files:**
- Create: `resume-copilot-web/components/resume-copilot/workspace/hub/resume/HubRadar.tsx`

- [ ] **Step 1: 写组件(从原型 hub-views.jsx 行 346–365 移植为 TSX)**
```tsx
'use client';

export interface RadarDatum { k: string; v: number; fin?: boolean }

export function HubRadar({ size = 172, data, max = 100 }: { size?: number; data: RadarDatum[]; max?: number }) {
  const cx = size / 2, cy = size / 2, R = size * 0.38, n = data.length;
  const ang = (i: number) => (Math.PI * 2 * i) / n - Math.PI / 2;
  const pt = (i: number, r: number): [number, number] => [cx + Math.cos(ang(i)) * r, cy + Math.sin(ang(i)) * r];
  const poly = (r: number) => data.map((_, i) => pt(i, R * r).join(',')).join(' ');
  const valPoly = data.map((d, i) => pt(i, R * (d.v / max)).join(',')).join(' ');
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ overflow: 'visible' }}>
      {[0.25, 0.5, 0.75, 1].map((r, i) => (
        <polygon key={i} points={poly(r)} fill="none" stroke={i === 3 ? 'var(--border-strong)' : 'var(--border-warm)'} strokeWidth="1" />
      ))}
      {data.map((_, i) => { const [x, y] = pt(i, R); return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="var(--border-warm)" strokeWidth="1" />; })}
      <polygon points={valPoly} fill="var(--terracotta)" fillOpacity="0.13" stroke="var(--terracotta)" strokeWidth="1.6" strokeLinejoin="round" />
      {data.map((d, i) => { const [x, y] = pt(i, R * (d.v / max)); return <circle key={i} cx={x} cy={y} r="2.6" fill="var(--terracotta-strong)" />; })}
      {data.map((d, i) => {
        const [x, y] = pt(i, R + 15);
        const anchor = Math.abs(x - cx) < 6 ? 'middle' : x > cx ? 'start' : 'end';
        return (
          <text key={i} x={x} y={y} textAnchor={anchor} dominantBaseline="middle"
            style={{ font: `${d.fin ? 700 : 500} 9.5px var(--font-sans)`, fill: d.fin ? 'var(--terracotta-strong)' : 'var(--olive)' }}>{d.k}</text>
        );
      })}
    </svg>
  );
}
```

- [ ] **Step 2: lint + build**
```bash
cd resume-copilot-web && npm run lint 2>&1 | tail -3 && npm run build 2>&1 | tail -5
```
Expected: 0 errors, build 成功。

- [ ] **Step 3: Commit**
```bash
git add resume-copilot-web/components/resume-copilot/workspace/hub/resume/HubRadar.tsx
git commit -m "feat(hub-resume): HubRadar 8 维雷达(移植原型)"
```

---

### Task 3:ResumeA4 预览组件

**Files:**
- Create: `resume-copilot-web/components/resume-copilot/workspace/hub/resume/ResumeA4.tsx`

- [ ] **Step 1: 写组件(从原型 ResumeA4 移植;本期用占位灰条 + highlight 段,真实 profile 渲染留 Phase 2 编辑器)**
```tsx
'use client';
import type { CSSProperties } from 'react';

const grayLine = (w: number | string, mb = 6) => (
  <div style={{ width: w, height: 4.5, background: 'var(--border-warm)', borderRadius: 3, marginBottom: mb }} />
);

export function ResumeA4({ highlight = false, name = '陈一帆' }: { highlight?: boolean; name?: string }) {
  const secs = ['教育经历', '实习经历', '项目经历', '掌握技能'];
  const wrap: CSSProperties = {
    background: '#fff', width: 322, padding: '24px 28px', boxSizing: 'border-box', borderRadius: 4,
    margin: '0 auto', boxShadow: '0 0 0 1px var(--border-warm), 0 12px 32px rgba(0,0,0,0.09)',
  };
  return (
    <div style={wrap}>
      <div style={{ borderBottom: '2px solid var(--ink)', paddingBottom: 10, marginBottom: 12 }}>
        <div style={{ font: '600 18px/1 var(--font-sans)', color: 'var(--ink)', marginBottom: 8 }}>{name}</div>
        <div style={{ display: 'flex', gap: 12 }}>{grayLine(58, 0)}{grayLine(72, 0)}{grayLine(46, 0)}</div>
      </div>
      {secs.map((s, i) => {
        const lit = highlight && i === 1;
        return (
          <div key={i} style={{
            background: lit ? 'var(--terracotta-wash)' : 'transparent', borderRadius: lit ? 7 : 0,
            margin: lit ? '0 -10px 14px' : '0 0 14px', padding: lit ? '8px 10px' : 0,
            boxShadow: lit ? '0 0 0 1.5px var(--terracotta)' : 'none',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <span style={{ font: '600 11px/1 var(--font-sans)', color: 'var(--ink-soft)', letterSpacing: '0.04em' }}>{s}</span>
              {lit && <span style={{ font: '600 9px var(--font-sans)', color: '#fff', background: 'var(--terracotta)', borderRadius: 999, padding: '2px 8px', marginLeft: 'auto' }}>AI 刚写回</span>}
            </div>
            {lit
              ? <div style={{ font: '400 10px/1.6 var(--font-sans)', color: 'var(--ink-soft)' }}>搭建覆盖 <b>40+ 量价因子</b>的回测框架(<b>2021–2023</b>),将单因子筛选由手动改为一键批量,显著缩短迭代周期。</div>
              : [...Array(i === 3 ? 2 : 3)].map((_, j, a) => grayLine(j === a.length - 1 ? (i === 2 ? '74%' : '56%') : '100%', 5))}
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: 核对 `--ink-soft` 是否存在**
```bash
grep -c -- "--ink-soft:" resume-copilot-web/components/hifi/hifi-tokens.css
```
若为 0,把上面 `var(--ink-soft)` 全替换为 `var(--olive)`。

- [ ] **Step 3: lint + build**(命令同 Task 2 Step 2)Expected: 0 errors。

- [ ] **Step 4: Commit**
```bash
git add resume-copilot-web/components/resume-copilot/workspace/hub/resume/ResumeA4.tsx
git commit -m "feat(hub-resume): ResumeA4 预览(移植原型占位版)"
```

---

### Task 4:ResumeScorePanel(画布槽侧面板主组件)

**Files:**
- Create: `resume-copilot-web/components/resume-copilot/workspace/hub/resume/ResumeScorePanel.tsx`

契约 props = `{ sessionId, onExpandEditor, onClose }`(handoff §画布槽接口契约)。内部:segmented(打分报告/简历预览)+ 打分态(目标赛道 pill / 现状分 + 潜力区间 / HubRadar / 逐段缺口卡 CTA)+ 预览态(A4 工具条 + ResumeA4)。数据走 `scoreResume(sessionId)`;mock 模式渲染原型样例。

- [ ] **Step 1: 写组件**
```tsx
'use client';
import { useEffect, useState } from 'react';
import { HubRadar, type RadarDatum } from './HubRadar';
import { ResumeA4 } from './ResumeA4';
import { scoreResume, type ScoreReportData } from '../../../api';

export interface ResumeScorePanelProps {
  sessionId: number;
  onExpandEditor: () => void;
  onClose?: () => void;
  /** 无 session 时渲染原型样例,供独立目测 */
  mock?: boolean;
}

// 8 维 → 雷达短标签 + 金融维标记(对齐原型 R_RADAR 顺序)
const RADAR_META: { key: string; k: string; fin?: boolean }[] = [
  { key: 'logic', k: '逻辑' }, { key: 'star', k: 'STAR' }, { key: 'readability', k: '可读' },
  { key: 'completeness', k: '完整' }, { key: 'expression', k: '表达' }, { key: 'quantification', k: '量化' },
  { key: 'track_fit', k: '匹配度', fin: true }, { key: 'defensibility', k: '佐证', fin: true },
];

const MOCK: ScoreReportData = {
  session_id: 0, target_track: '量化私募 · 研究', overall_current: 72,
  overall_potential_low: 80, overall_potential_high: 85, summary: '',
  dimensions: [
    { key: 'logic', name: '逻辑清晰', score: 78, ceiling: 86, reason: '' },
    { key: 'star', name: 'STAR 应用', score: 58, ceiling: 84, reason: '' },
    { key: 'readability', name: '内容可读', score: 84, ceiling: 88, reason: '' },
    { key: 'completeness', name: '内容完整', score: 70, ceiling: 80, reason: '' },
    { key: 'expression', name: '专业表达', score: 80, ceiling: 86, reason: '' },
    { key: 'quantification', name: '成果量化', score: 52, ceiling: 82, reason: '' },
    { key: 'track_fit', name: '赛道匹配度', score: 64, ceiling: 82, reason: '' },
    { key: 'defensibility', name: '佐证充分度', score: 55, ceiling: 80, reason: '' },
  ],
  section_gaps: [
    { section: 'internships.0', label: '九坤投资 · 量化研究实习', gaps: ['STAR 缺 Result', '佐证不足'], detail: '' },
    { section: 'projects.1', label: '校园量化策略项目', gaps: ['成果无量化锚点'], detail: '' },
  ],
  used_ai: false,
};

export function ResumeScorePanel({ sessionId, onExpandEditor, onClose, mock = false }: ResumeScorePanelProps) {
  const [view, setView] = useState<'score' | 'preview'>('score');
  const [report, setReport] = useState<ScoreReportData | null>(mock ? MOCK : null);
  const [loading, setLoading] = useState(!mock);
  const [error, setError] = useState('');

  useEffect(() => {
    if (mock || !sessionId) return;
    let alive = true;
    scoreResume(sessionId)
      .then((r) => { if (alive) { setReport(r); setError(''); } })
      .catch((e) => { if (alive) setError(e instanceof Error ? e.message : '打分失败'); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [mock, sessionId]);

  const radarData: RadarDatum[] = report
    ? RADAR_META.map((m) => ({ k: m.k, fin: m.fin, v: report.dimensions.find((d) => d.key === m.key)?.score ?? 0 }))
    : [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      {/* chrome */}
      <div style={{ padding: '13px 16px 0', background: 'var(--ivory)', borderBottom: '1px solid var(--border)', flex: 'none' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ font: '600 14px var(--font-sans)', color: 'var(--ink)' }}>简历优化</div>
            <div style={{ font: '400 11px var(--font-sans)', color: 'var(--stone)', marginTop: 1 }}>诚实打分 + 深度优化 · 写回实时刷新</div>
          </div>
          <button className="hf-btn ghost sm" style={{ gap: 6 }} onClick={onExpandEditor}>展开编辑器</button>
          {onClose && <button className="hf-btn ghost sm" onClick={onClose} aria-label="关闭">✕</button>}
        </div>
        <div style={{ display: 'flex', gap: 3, padding: 3, background: 'var(--library-rail)', borderRadius: 11, boxShadow: '0 0 0 1px var(--border-warm)', margin: '12px 0 13px' }}>
          {([['score', '打分报告'], ['preview', '简历预览']] as const).map(([k, t]) => (
            <button key={k} onClick={() => setView(k)} style={{
              flex: 1, textAlign: 'center', cursor: 'pointer', border: 'none',
              font: `${view === k ? 600 : 500} 12.5px var(--font-sans)`, padding: '7px 0', borderRadius: 8,
              color: view === k ? 'var(--ink)' : 'var(--olive)', background: view === k ? 'var(--ivory)' : 'transparent',
              boxShadow: view === k ? '0 0 0 1px var(--border-strong), 0 1px 2px rgba(0,0,0,0.04)' : 'none',
            }}>{t}</button>
          ))}
        </div>
      </div>

      {loading && <div style={{ padding: 40, color: 'var(--stone)', font: '400 13px var(--font-sans)' }}>打分中…</div>}
      {error && <div style={{ padding: 40, color: 'var(--terracotta-strong)', font: '400 13px var(--font-sans)' }}>打分失败:{error}</div>}

      {report && view === 'score' && (
        <div style={{ flex: 1, overflow: 'auto', padding: 16, background: 'var(--parchment)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <span className="hf-overline" style={{ fontSize: 9.5 }}>目标赛道</span>
            <span className="hf-pill terra" style={{ height: 26 }}>{report.target_track || '未定'} ▾</span>
            <span style={{ marginLeft: 'auto', font: '500 11px var(--font-sans)', color: 'var(--stone)' }}>切换重打分</span>
          </div>
          <div style={{ display: 'flex', gap: 14, alignItems: 'center', marginBottom: 16 }}>
            <div style={{ flex: 'none', textAlign: 'center' }}>
              <div style={{ font: '500 46px/0.9 var(--font-mono)', color: 'var(--ink)' }}>{report.overall_current}</div>
              <div style={{ font: '500 11px var(--font-sans)', color: 'var(--olive)', marginTop: 4 }}>现状分</div>
              <div className="hf-pill" style={{ height: 24, marginTop: 9, fontFamily: 'var(--font-mono)' }}>潜力 {report.overall_potential_low}–{report.overall_potential_high}</div>
            </div>
            <div style={{ flex: 1, background: 'var(--ivory)', borderRadius: 14, boxShadow: 'var(--sh-ring)', display: 'flex', justifyContent: 'center', padding: 8 }}>
              <HubRadar size={172} data={radarData} />
            </div>
          </div>
          <div className="hf-overline" style={{ marginBottom: 10 }}>逐段缺口 · 深度优化入口</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
            {report.section_gaps.map((g, i) => (
              <div key={i} style={{ borderRadius: 13, padding: '12px 13px', background: 'var(--ivory)', boxShadow: 'var(--sh-ring)' }}>
                <div style={{ font: '600 12.5px var(--font-sans)', color: 'var(--ink)', marginBottom: 8 }}>{g.label}</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
                  {g.gaps.map((t, j) => <span key={j} className="hf-pill" style={{ height: 22, fontSize: 10.5, whiteSpace: 'nowrap' }}>{t}</span>)}
                </div>
                <button className="hf-btn sand sm" style={{ height: 30 }} onClick={onExpandEditor}>去深度优化这段 →</button>
              </div>
            ))}
          </div>
          <div style={{ font: '400 10.5px/1.5 var(--font-sans)', color: 'var(--stone)', textAlign: 'center', marginTop: 12 }}>只诊断、不改写 · 提分靠深度优化反问取证</div>
        </div>
      )}

      {report && view === 'preview' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--parchment)' }}>
          <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)', background: 'var(--ivory)', display: 'flex', alignItems: 'center', gap: 7, flex: 'none' }}>
            <span className="hf-pill" style={{ height: 26, fontFamily: 'var(--font-mono)' }}>1 页</span>
            <span className="hf-pill" style={{ height: 26 }}>模板 · 经典单栏 ▾</span>
            <button className="hf-btn dark sm" style={{ marginLeft: 'auto', height: 28 }} onClick={onExpandEditor}>下载 PDF</button>
          </div>
          <div style={{ flex: 1, overflow: 'auto', padding: '18px 0', display: 'flex', justifyContent: 'center' }}>
            <ResumeA4 highlight />
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 注意点** — 逐段缺口 CTA 暂统一触发 `onExpandEditor`(编辑器里才有深度优化反问);Phase 2 改为「带 gap seed 进编辑器深度优化 chip」。原型里"正在深度优化"高亮态属 Phase 2,本期不做。

- [ ] **Step 3: lint + build**(命令同前)Expected: 0 errors。

- [ ] **Step 4: Commit**
```bash
git add resume-copilot-web/components/resume-copilot/workspace/hub/resume/ResumeScorePanel.tsx
git commit -m "feat(hub-resume): ResumeScorePanel 打分报告侧面板(契约 props + 实时打分 + 预览)"
```

---

### Task 5:独立目测页(CanvasSlot 未就绪前的对照入口)

**Files:**
- Create: `resume-copilot-web/app/resume-copilot/hub-score/page.tsx`

- [ ] **Step 1: 写页面(Suspense + ?mock=1 / ?session=)**
```tsx
'use client';
import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { ResumeScorePanel } from '../../../components/resume-copilot/workspace/hub/resume/ResumeScorePanel';

function Inner() {
  const params = useSearchParams();
  const mock = params.get('mock') === '1';
  const sessionId = Number(params.get('session') || '0');
  const [editorMsg, setEditorMsg] = useState('');
  if (!mock && !sessionId) return <div style={{ padding: 40 }}>缺少 ?session=&lt;id&gt; 或 ?mock=1</div>;
  return (
    <div className="hf" data-theme="hub" style={{ minHeight: '100vh', background: 'var(--parchment)', display: 'flex', justifyContent: 'flex-end' }}>
      <div style={{ width: 500, height: '100vh', background: 'var(--ivory)', boxShadow: '-8px 0 24px rgba(0,0,0,0.06)' }}>
        <ResumeScorePanel sessionId={sessionId} mock={mock}
          onExpandEditor={() => setEditorMsg('（展开编辑器 → Phase 2 全屏 overlay）')}
          onClose={() => setEditorMsg('（关闭面板）')} />
      </div>
      {editorMsg && <div style={{ position: 'fixed', left: 16, bottom: 16, font: '400 12px var(--font-sans)', color: 'var(--stone)' }}>{editorMsg}</div>}
    </div>
  );
}
export default function Page() {
  return <Suspense fallback={<div style={{ padding: 40 }}>加载中…</div>}><Inner /></Suspense>;
}
```

- [ ] **Step 2: lint + build**(命令同前)Expected: 0 errors。

- [ ] **Step 3: 人工目测** — `cd resume-copilot-web && npm run dev`,开 `http://localhost:3001/resume-copilot/hub-score?mock=1`,对照原型 ResumeView:目标赛道 pill / 现状 72 / 潜力 80–85 / 8 维雷达(匹配度+佐证 土红加粗)/ 逐段缺口卡 + CTA / segmented 切「简历预览」看 A4。**用户确认后再提交。**

- [ ] **Step 4: Commit**
```bash
git add resume-copilot-web/app/resume-copilot/hub-score/page.tsx
git commit -m "feat(hub-resume): 打分面板独立目测页 /resume-copilot/hub-score"
```

---

### Task 6:回归 + 交付契约给 orchestrator

- [ ] **Step 1: 全量 lint + build**
```bash
cd resume-copilot-web && npm run lint 2>&1 | tail -3 && npm run build 2>&1 | tail -8
```
Expected: 0 errors,build 成功。

- [ ] **Step 2: 写一行交付说明给 orchestrator**(同步回 sync,告诉它 `ResumeScorePanel` 已就绪 + 契约 props,等它冻结 `CanvasSlot` 接口我来塞 / 它来 import)。文件:`docs/superpowers/handoffs/2026-06-09-resume-panel-ready.md`,内容含组件路径 + props 签名 + 目测页 URL。

- [ ] **Step 3: Commit + sync**
```bash
git add docs/superpowers/handoffs/2026-06-09-resume-panel-ready.md
git commit -m "docs(hub-resume): 打分面板就绪 + 契约回交 orchestrator"
cp docs/superpowers/handoffs/2026-06-09-resume-panel-ready.md /home/ubuntu/jobradar-sync/
```

---

## Phase 2:全屏编辑器 overlay(outline — 落地前先读 hub-editor*.jsx)

> Phase 1 落地 + 用户目测通过后,再把这段拆成 bite-sized。先读原型:
> `git show hub-shell-frontend:docs/superpowers/specs/hub-prototype-2026-06-09/hub/hub-editor.jsx`
> `git show hub-shell-frontend:docs/superpowers/specs/hub-prototype-2026-06-09/hub/hub-editor-ai.jsx`

预计任务:
- **E1 ResumeEditorOverlay 外壳** — 自管 `editorOpen` 态(`ResumeScorePanel` 的 `onExpandEditor` → 由父挂 overlay,或面板内自挂);全屏顶栏 + 三栏骨架(左 模板/编辑/布局 tab · 中 WYSIWYG A4 · 右 AI 助手)。
- **E2 左栏三 tab** — 模板缩略图 / 分模块就地编辑(每 bullet「引用此段」)/ 布局滑块 + 显隐。
- **E3 中栏 WYSIWYG** — 单源 `renderResumeHTML()` + `<iframe srcDoc>`;导出 `POST /export-pdf`(Track A,可能跨期)。
- **E4 右栏 AI 助手三能力** — ① 打分报告(复用 ResumeScorePanel 内容)② 深度优化(流式反问**无选择框** → `deepOptimizeStart` 播种 + `planTurn` 续问 + `applyRewrite` 写回 → 中栏高亮"AI 刚写回")③ 自由问。
- **E5 gap→深度优化串联** — 打分逐段缺口 CTA 带 `{section,label,gaps,detail,target_track}` seed 进右栏深度优化 chip。
- **E6 回归 + lint/build + 目测全链路**(打分→点缺口→反问→改写→预览刷新)。

---

## Self-Review

**1. Spec/handoff 覆盖:**
- 画布槽契约 props `{sessionId,onExpandEditor,onClose}` → Task 4 ✅
- 进入路径"先打分→展开编辑器" → 面板有「展开编辑器」按钮触发 onExpandEditor,编辑器是 Phase 2 overlay ✅
- 打分报告字段(目标赛道 pill/现状/潜力/8 维雷达/逐段缺口/segmented A4)→ Task 2/3/4 逐字段 ✅
- 「佐证充分度」命名 + 金融维土红 → RADAR_META fin 标记 + HubRadar fin 配色 ✅
- `.hf` 赭红 token + 不带天蓝 → 全用 var(--terracotta…)/hf-* ✅
- API 封装补齐 → Task 1 ✅
- 编辑器自管 overlay + 单开分支 → Task 0 分支 + Phase 2 E1 ✅
- 深度优化反问取证/编数字红线 → 后端已建(Task 1-4 of deep-optimize-b2);前端 Phase 2 E4
- 无黑话上卡面 → 卡面只中文维度名 ✅(used_ai 不显示)

**2. Placeholder 扫描:** Phase 1 全部带完整 TSX;Phase 2 标注 outline + 明确"落地前读原型再拆",非伪代码占位。

**3. 类型一致:** `ScoreReportData`/`ScoreSectionGap`/`ScoreDimension` 复用 api.ts 现有类型;`PlanStateOut`/`DeepOptimizeStartIn` Task 1 定义,Phase 2 E4 使用 — 一致。

**4. 待 orchestrator 回的依赖:** ① `CanvasSlot.tsx` 冻结后真正挂载(Task 6 交付契约)② 若它扩了 hifi-tokens.css 以我为冲突基准 ③ 后端 plan/turn + apply-rewrite 真实入参(Task 1 Step 3 现场核对)。
