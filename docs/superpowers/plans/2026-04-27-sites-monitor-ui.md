# Sites Monitor UI — Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a `/sites` admin page in `/frontend` that consumes Phase 1's `/api/sites/*` endpoints and renders a HiFi-terracotta dashboard: KPI bar + alert banner + category-grouped company cards + sticky detail panel + recrawl button + adaptive polling.

**Architecture:** Page-level component owns polling lifecycle and selectedCompany state. Children are split by single responsibility — summary bar, category group, company card, detail panel, sparkline, recrawl button, toast. Theme scoped via `<div className="hf" data-theme="sites">` so HiFi tokens don't bleed into the existing AntD admin pages.

**Tech Stack:** React 19 + TypeScript + Vite + AntD (existing app shell only — `/sites` page itself uses no AntD components) + axios (existing wrapper) + vitest + @testing-library/react.

**Spec:** `docs/superpowers/specs/2026-04-27-sites-monitor-ui-design.md`

---

## File map

**Create:**
- `frontend/src/styles/hifi-tokens.css` — copied verbatim from `/tmp/jobradar-ds/hifi-tokens.css` (the design system zip).
- `frontend/src/styles/sites-theme.css` — `/sites`-only layout classes.
- `frontend/src/components/sites/types.ts` — TypeScript interfaces matching backend pydantic schemas.
- `frontend/src/components/sites/api.ts` — axios wrappers + types re-export.
- `frontend/src/components/sites/RunSparkline.tsx`
- `frontend/src/components/sites/Toast.tsx` + `ToastHost.tsx`
- `frontend/src/components/sites/CompanyCard.tsx`
- `frontend/src/components/sites/CategoryGroup.tsx`
- `frontend/src/components/sites/RecrawlButton.tsx`
- `frontend/src/components/sites/SiteDetailPanel.tsx`
- `frontend/src/components/sites/SitesSummaryBar.tsx`
- `frontend/src/pages/Sites.tsx`
- `frontend/src/pages/Sites.test.tsx`
- Per-component test files: `RunSparkline.test.tsx`, `CompanyCard.test.tsx`, `CategoryGroup.test.tsx`, `RecrawlButton.test.tsx`, `SiteDetailPanel.test.tsx`, `SitesSummaryBar.test.tsx` — kept alongside their components in `components/sites/`.

**Modify:**
- `frontend/src/AppLayout.tsx` — add menu entry, page title, route.

---

## Task 1 — Foundations: tokens, theme, API wrappers, types

**Files:**
- Create: `frontend/src/styles/hifi-tokens.css`
- Create: `frontend/src/styles/sites-theme.css`
- Create: `frontend/src/components/sites/types.ts`
- Create: `frontend/src/components/sites/api.ts`

- [ ] **Step 1.1: Copy hifi-tokens.css verbatim**

```bash
cp /tmp/jobradar-ds/hifi-tokens.css frontend/src/styles/hifi-tokens.css
```

If `/tmp/jobradar-ds/hifi-tokens.css` is missing, re-extract:
```bash
mkdir -p /tmp/jobradar-ds && cd /tmp/jobradar-ds && python3 -c "import zipfile; zipfile.ZipFile('/mnt/d/OneDrive/校招/数据分析/ai产品经理/Jobradar/jobradar design system.zip').extractall('.')"
cp /tmp/jobradar-ds/hifi-tokens.css frontend/src/styles/hifi-tokens.css
```

Verify the file starts with `/* JobRadar hi-fi tokens` and ends with the scoped scrollbar rules. ~188 lines.

- [ ] **Step 1.2: Create sites-theme.css with `/sites`-only layout classes**

```css
/* /sites page-only layout. Scoped via .hf wrapper from hifi-tokens.css */
@import './hifi-tokens.css';

/* Page shell — full-bleed parchment, max content width */
.hf .sites-shell {
  min-height: 100vh;
  background: var(--parchment);
  padding: 32px;
}

.hf .sites-content {
  max-width: 1440px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 24px;
  align-items: start;
}

/* Summary bar */
.hf .sites-summary-bar {
  display: flex;
  align-items: baseline;
  gap: 18px;
  padding: 18px 20px;
  background: var(--ivory);
  border-radius: var(--r-xl);
  box-shadow: var(--sh-ring);
  margin-bottom: 18px;
}
.hf .sites-summary-bar .sites-kpi-num {
  font-family: var(--font-serif);
  font-size: 28px;
  font-weight: 500;
  color: var(--ink);
  letter-spacing: -0.02em;
}

/* Alert banner — collapsed under summary bar */
.hf .sites-alert-banner {
  margin-bottom: 18px;
  padding: 12px 16px;
  background: var(--amber-bg);
  color: var(--amber-fg);
  border-radius: var(--r-md);
  box-shadow: 0 0 0 1px #ecdfa4;
  font-size: 14px;
  cursor: pointer;
}
.hf .sites-alert-banner:hover { background: #f3ebcb; }

/* Category group */
.hf .sites-category-group {
  margin-bottom: 28px;
}
.hf .sites-category-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-cream);
}
.hf .sites-category-title {
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 500;
  color: var(--ink);
}
.hf .sites-category-count {
  font-size: 13px;
  color: var(--stone);
}

/* Card grid */
.hf .sites-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}

/* Company card */
.hf .sites-company-card {
  padding: 12px 14px;
  background: var(--ivory);
  border-radius: var(--r-md);
  box-shadow: 0 0 0 1px var(--border-warm);
  cursor: pointer;
  transition: box-shadow .15s, transform .08s;
}
.hf .sites-company-card:hover {
  box-shadow: var(--sh-lift);
}
.hf .sites-company-card.selected {
  box-shadow: 0 0 0 2px var(--terracotta);
}
.hf .sites-company-card__name {
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 500;
  color: var(--ink);
  margin-bottom: 4px;
}
.hf .sites-company-card__meta {
  font-size: 12.5px;
  color: var(--stone);
}
.hf .sites-company-card__delta {
  font-weight: 600;
  color: var(--terracotta);
  margin-right: 6px;
}
.hf .sites-company-card__delta.zero {
  color: var(--stone);
  font-weight: 500;
}

/* Status dot */
.hf .sites-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}
.hf .sites-dot.green   { background: var(--emerald); }
.hf .sites-dot.yellow  { background: var(--amber-fg); }
.hf .sites-dot.red     { background: var(--crimson); }
.hf .sites-dot.unknown { background: var(--stone); }

/* Detail panel */
.hf .sites-detail-card {
  position: sticky;
  top: 32px;
  padding: 22px;
  background: var(--ivory);
  border-radius: var(--r-xl);
  box-shadow: var(--sh-ring);
}
.hf .sites-detail-card.empty {
  text-align: center;
  color: var(--stone);
  font-size: 14px;
  padding: 64px 22px;
}
.hf .sites-detail-card__name {
  font-family: var(--font-serif);
  font-size: 26px;
  font-weight: 500;
  color: var(--ink);
  margin-bottom: 6px;
}
.hf .sites-detail-card__meta {
  font-size: 12.5px;
  color: var(--olive);
  margin-bottom: 16px;
}
.hf .sites-detail-card__meta code {
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--ink);
  background: var(--library-rail);
  padding: 1px 6px;
  border-radius: 4px;
  margin: 0 2px;
}
.hf .sites-detail-card__error {
  margin: 12px 0;
  padding: 8px 12px;
  background: var(--library-rail);
  border-radius: var(--r-md);
  font-size: 12.5px;
  color: var(--charcoal);
}
.hf .sites-detail-card__error pre {
  margin: 6px 0 0 0;
  font-family: var(--font-mono);
  font-size: 11.5px;
  white-space: pre-wrap;
  word-break: break-word;
}

/* Sparkline */
.hf .sites-sparkline {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 44px;
  margin: 12px 0 4px 0;
}
.hf .sites-sparkline__bar {
  flex: 1;
  min-width: 4px;
  background: var(--terracotta);
  border-radius: 1px;
}
.hf .sites-sparkline__bar.failed { background: var(--crimson); }
.hf .sites-sparkline__bar.running { background: var(--stone); }
.hf .sites-sparkline__cap {
  font-size: 12px;
  color: var(--stone);
}

/* Empty state */
.hf .sites-empty {
  max-width: 480px;
  margin: 120px auto;
  text-align: center;
}
.hf .sites-empty__title {
  font-family: var(--font-serif);
  font-size: 32px;
  font-weight: 500;
  color: var(--ink);
  margin-bottom: 12px;
  letter-spacing: -0.02em;
}
.hf .sites-empty__sub {
  font-size: 15px;
  color: var(--olive);
  line-height: 1.6;
}
.hf .sites-empty__sub a {
  color: var(--terracotta);
  text-decoration: none;
  font-weight: 500;
}

/* Toast (top-right stack) */
.hf .sites-toast-host {
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}
.hf .sites-toast {
  pointer-events: auto;
  padding: 12px 16px;
  background: var(--ivory);
  border-radius: var(--r-md);
  box-shadow: var(--sh-paper);
  min-width: 240px;
  font-size: 14px;
  color: var(--ink);
  animation: hf-slide 0.3s ease-out;
}
.hf .sites-toast.success { box-shadow: 0 0 0 1px var(--emerald-soft), 0 18px 52px rgba(0,0,0,0.08); border-left: 3px solid var(--emerald); }
.hf .sites-toast.failed  { box-shadow: 0 0 0 1px #f4d4d4, 0 18px 52px rgba(0,0,0,0.08); border-left: 3px solid var(--crimson); }
```

- [ ] **Step 1.3: Create types.ts with backend schema mirrors**

Create `frontend/src/components/sites/types.ts`:

```typescript
export type AlertLevel = 'green' | 'yellow' | 'red' | 'unknown';

export interface SitesSummary {
  active: number;
  alerted: number;
  disabled: number;
  total_today_new: number;
  last_batch_at: string | null;
  last_batch_status: string | null;
}

export interface SiteRow {
  company: string;
  source: string;
  last_run_at: string | null;
  last_status: string | null;
  today_new: number;
  last_error_short: string;
  alert_level: AlertLevel;
}

export interface SiteRun {
  id: number;
  source: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  fetched_count: number;
  new_count: number;
  error_message: string;
  duration_ms: number;
}

export interface SiteRecrawlOut {
  parent_log_id: number;
  message: string;
}
```

- [ ] **Step 1.4: Add API wrappers to existing api/index.ts**

Append the following to `frontend/src/api/index.ts` (at the end of the file):

```typescript
// Sites monitor
import type { SitesSummary, SiteRow, SiteRun, SiteRecrawlOut } from '../components/sites/types';

export const fetchSitesSummary = () => api.get<SitesSummary>('/sites/summary');
export const fetchSites = (source?: string) =>
  api.get<SiteRow[]>('/sites', { params: source ? { source } : {} });
export const fetchSiteRuns = (company: string, limit = 24) =>
  api.get<SiteRun[]>(`/sites/${encodeURIComponent(company)}/runs`, { params: { limit } });
export const triggerSiteRecrawl = (company: string) =>
  api.post<SiteRecrawlOut>(`/sites/${encodeURIComponent(company)}/recrawl`);
```

- [ ] **Step 1.5: Smoke-build to confirm no syntax errors**

Run:
```bash
cd frontend && npm run build 2>&1 | tail -10
```
Expected: build succeeds (or fails with NO error referencing the new files — TS may complain about unused exports, that's OK at this stage).

- [ ] **Step 1.6: Commit**

```bash
cd /home/chuanbo/projects/JobRadar/.worktrees/sites-monitor
git add frontend/src/styles/hifi-tokens.css frontend/src/styles/sites-theme.css frontend/src/components/sites/types.ts frontend/src/api/index.ts
git commit -m "feat(sites-ui): foundation — HiFi tokens, sites theme, API wrappers, types

Adds /frontend foundations for the /sites page: HiFi terracotta tokens
(scoped to .hf), /sites-only layout CSS, TypeScript types matching
Phase 1 pydantic schemas, and 4 axios wrappers for /api/sites/*."
```

---

## Task 2 — `<RunSparkline/>` (TDD, pure presentational)

**Files:**
- Create: `frontend/src/components/sites/RunSparkline.tsx`
- Create: `frontend/src/components/sites/RunSparkline.test.tsx`

- [ ] **Step 2.1: Write failing test**

Create `frontend/src/components/sites/RunSparkline.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import RunSparkline from './RunSparkline';
import type { SiteRun } from './types';

function mkRun(overrides: Partial<SiteRun>): SiteRun {
  return {
    id: 1,
    source: 'internet_official',
    started_at: '2026-04-27T08:00:00',
    finished_at: '2026-04-27T08:01:00',
    status: 'success',
    fetched_count: 10,
    new_count: 2,
    error_message: '',
    duration_ms: 60000,
    ...overrides,
  };
}

describe('RunSparkline', () => {
  it('renders one bar per run', () => {
    const runs: SiteRun[] = [mkRun({ id: 1 }), mkRun({ id: 2 }), mkRun({ id: 3 })];
    const { container } = render(<RunSparkline runs={runs} />);
    expect(container.querySelectorAll('.sites-sparkline__bar').length).toBe(3);
  });

  it('marks failed runs with the failed class', () => {
    const runs: SiteRun[] = [
      mkRun({ id: 1, status: 'failed', fetched_count: 0 }),
      mkRun({ id: 2, status: 'success', fetched_count: 10 }),
    ];
    const { container } = render(<RunSparkline runs={runs} />);
    const bars = container.querySelectorAll('.sites-sparkline__bar');
    expect(bars[0].classList.contains('failed')).toBe(true);
    expect(bars[1].classList.contains('failed')).toBe(false);
  });

  it('shows a caption with failure count', () => {
    const runs: SiteRun[] = [
      mkRun({ id: 1, status: 'failed' }),
      mkRun({ id: 2, status: 'failed' }),
      mkRun({ id: 3, status: 'success' }),
    ];
    render(<RunSparkline runs={runs} />);
    expect(screen.getByText(/最近 3 次 run · 2 失败/)).toBeInTheDocument();
  });

  it('renders nothing meaningful when runs is empty', () => {
    render(<RunSparkline runs={[]} />);
    expect(screen.getByText(/暂无 run 数据/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2.2: Run test to verify it fails**

```bash
cd frontend && npm test -- RunSparkline.test 2>&1 | tail -10
```
Expected: 4 failures with `Cannot find module './RunSparkline'`.

- [ ] **Step 2.3: Implement RunSparkline**

Create `frontend/src/components/sites/RunSparkline.tsx`:

```tsx
import type { SiteRun } from './types';

interface RunSparklineProps {
  runs: SiteRun[];
}

const MAX_BAR_HEIGHT = 40;

function barHeight(fetched: number): number {
  if (fetched <= 0) return 4;
  return Math.min(MAX_BAR_HEIGHT, Math.max(4, Math.log2(fetched + 1) * 6));
}

function barClass(status: string): string {
  if (status === 'failed') return 'sites-sparkline__bar failed';
  if (status === 'running') return 'sites-sparkline__bar running';
  return 'sites-sparkline__bar';
}

export default function RunSparkline({ runs }: RunSparklineProps) {
  if (runs.length === 0) {
    return <div className="sites-sparkline__cap">暂无 run 数据</div>;
  }

  // Reverse so oldest is on the left, newest on the right (runs come in DESC).
  const ordered = [...runs].slice().reverse();
  const failedCount = runs.filter((r) => r.status === 'failed').length;

  return (
    <div>
      <div className="sites-sparkline">
        {ordered.map((r) => (
          <div
            key={r.id}
            className={barClass(r.status)}
            style={{ height: `${barHeight(r.fetched_count)}px` }}
            title={`${r.started_at} · ${r.status} · fetched=${r.fetched_count} new=${r.new_count}`}
          />
        ))}
      </div>
      <div className="sites-sparkline__cap">
        最近 {runs.length} 次 run · {failedCount} 失败
      </div>
    </div>
  );
}
```

- [ ] **Step 2.4: Run test to verify it passes**

```bash
cd frontend && npm test -- RunSparkline.test 2>&1 | tail -10
```
Expected: 4 passes.

- [ ] **Step 2.5: Commit**

```bash
git add frontend/src/components/sites/RunSparkline.tsx frontend/src/components/sites/RunSparkline.test.tsx
git commit -m "feat(sites-ui): RunSparkline component

24-bar log-scale histogram of recent runs. Red for failed, terracotta
for success, stone for running. Shows '最近 N 次 run · M 失败' caption."
```

---

## Task 3 — `<Toast/>` + `<ToastHost/>` (TDD, micro-component)

**Files:**
- Create: `frontend/src/components/sites/Toast.tsx`
- Create: `frontend/src/components/sites/ToastHost.tsx`
- Create: `frontend/src/components/sites/Toast.test.tsx`

- [ ] **Step 3.1: Write failing test**

Create `frontend/src/components/sites/Toast.test.tsx`:

```tsx
import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastHost, useToast } from './ToastHost';

function HarnessButton({ label, kind }: { label: string; kind: 'success' | 'failed' }) {
  const toast = useToast();
  return <button onClick={() => toast.show(label, kind)}>fire</button>;
}

describe('Toast', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders a toast when show() is called', () => {
    render(
      <ToastHost>
        <HarnessButton label="Hello" kind="success" />
      </ToastHost>,
    );
    act(() => {
      screen.getByText('fire').click();
    });
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });

  it('auto-dismisses after 4 seconds', () => {
    render(
      <ToastHost>
        <HarnessButton label="Hello" kind="success" />
      </ToastHost>,
    );
    act(() => {
      screen.getByText('fire').click();
    });
    expect(screen.getByText('Hello')).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.queryByText('Hello')).not.toBeInTheDocument();
  });

  it('applies failed class for failed kind', () => {
    render(
      <ToastHost>
        <HarnessButton label="Boom" kind="failed" />
      </ToastHost>,
    );
    act(() => {
      screen.getByText('fire').click();
    });
    const toast = screen.getByText('Boom').closest('.sites-toast');
    expect(toast).not.toBeNull();
    expect(toast!.classList.contains('failed')).toBe(true);
  });
});
```

- [ ] **Step 3.2: Run test to verify it fails**

```bash
cd frontend && npm test -- Toast.test 2>&1 | tail -10
```
Expected: 3 failures with `Cannot find module './ToastHost'`.

- [ ] **Step 3.3: Implement Toast.tsx**

Create `frontend/src/components/sites/Toast.tsx`:

```tsx
interface ToastProps {
  text: string;
  kind: 'success' | 'failed';
}

export default function Toast({ text, kind }: ToastProps) {
  return <div className={`sites-toast ${kind}`}>{text}</div>;
}
```

- [ ] **Step 3.4: Implement ToastHost.tsx with context**

Create `frontend/src/components/sites/ToastHost.tsx`:

```tsx
import { createContext, useCallback, useContext, useState } from 'react';
import type { ReactNode } from 'react';

import Toast from './Toast';

interface ToastEntry {
  id: number;
  text: string;
  kind: 'success' | 'failed';
}

interface ToastApi {
  show: (text: string, kind: 'success' | 'failed') => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const TOAST_TTL_MS = 4000;

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast() must be used inside <ToastHost>');
  }
  return ctx;
}

export function ToastHost({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastEntry[]>([]);

  const show = useCallback<ToastApi['show']>((text, kind) => {
    const id = Date.now() + Math.random();
    setItems((prev) => [...prev, { id, text, kind }]);
    setTimeout(() => {
      setItems((prev) => prev.filter((it) => it.id !== id));
    }, TOAST_TTL_MS);
  }, []);

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div className="sites-toast-host">
        {items.map((it) => (
          <Toast key={it.id} text={it.text} kind={it.kind} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}
```

- [ ] **Step 3.5: Run test to verify passes**

```bash
cd frontend && npm test -- Toast.test 2>&1 | tail -10
```
Expected: 3 passes.

- [ ] **Step 3.6: Commit**

```bash
git add frontend/src/components/sites/Toast.tsx frontend/src/components/sites/ToastHost.tsx frontend/src/components/sites/Toast.test.tsx
git commit -m "feat(sites-ui): Toast + ToastHost with React context

Top-right stacked toasts, auto-dismiss 4s. useToast() hook for
consumers; success/failed color variants."
```

---

## Task 4 — `<CompanyCard/>` (TDD)

**Files:**
- Create: `frontend/src/components/sites/CompanyCard.tsx`
- Create: `frontend/src/components/sites/CompanyCard.test.tsx`

- [ ] **Step 4.1: Write failing test**

Create `frontend/src/components/sites/CompanyCard.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import CompanyCard from './CompanyCard';
import type { SiteRow } from './types';

function mkRow(overrides: Partial<SiteRow>): SiteRow {
  return {
    company: '腾讯',
    source: 'internet_official',
    last_run_at: '2026-04-27T03:00:00',
    last_status: 'success',
    today_new: 12,
    last_error_short: '',
    alert_level: 'green',
    ...overrides,
  };
}

describe('CompanyCard', () => {
  it('renders company name and today_new delta', () => {
    render(<CompanyCard row={mkRow({ today_new: 12 })} selected={false} onClick={() => {}} />);
    expect(screen.getByText('腾讯')).toBeInTheDocument();
    expect(screen.getByText('+12')).toBeInTheDocument();
  });

  it('shows · when today_new is 0', () => {
    render(<CompanyCard row={mkRow({ today_new: 0 })} selected={false} onClick={() => {}} />);
    expect(screen.getByText('·')).toBeInTheDocument();
  });

  it('applies status color class', () => {
    const { container } = render(<CompanyCard row={mkRow({ alert_level: 'red' })} selected={false} onClick={() => {}} />);
    const dot = container.querySelector('.sites-dot');
    expect(dot?.classList.contains('red')).toBe(true);
  });

  it('applies selected class when selected', () => {
    const { container } = render(<CompanyCard row={mkRow({})} selected onClick={() => {}} />);
    expect(container.querySelector('.sites-company-card.selected')).toBeTruthy();
  });

  it('fires onClick with the company name', () => {
    const onClick = vi.fn();
    render(<CompanyCard row={mkRow({ company: '阿里巴巴' })} selected={false} onClick={onClick} />);
    fireEvent.click(screen.getByText('阿里巴巴'));
    expect(onClick).toHaveBeenCalledWith('阿里巴巴');
  });
});
```

- [ ] **Step 4.2: Run test to verify it fails**

```bash
cd frontend && npm test -- CompanyCard.test 2>&1 | tail -10
```
Expected: 5 failures with `Cannot find module './CompanyCard'`.

- [ ] **Step 4.3: Implement CompanyCard**

Create `frontend/src/components/sites/CompanyCard.tsx`:

```tsx
import type { SiteRow } from './types';

interface CompanyCardProps {
  row: SiteRow;
  selected: boolean;
  onClick: (company: string) => void;
}

function relativeTime(iso: string | null): string {
  if (!iso) return '从未运行';
  const t = new Date(iso).getTime();
  const now = Date.now();
  const diffMs = Math.max(0, now - t);
  const min = Math.floor(diffMs / 60000);
  if (min < 1) return '刚刚';
  if (min < 60) return `${min}m 前`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h 前`;
  const day = Math.floor(hr / 24);
  return `${day}d 前`;
}

export default function CompanyCard({ row, selected, onClick }: CompanyCardProps) {
  const cls = `sites-company-card${selected ? ' selected' : ''}`;
  const deltaCls = `sites-company-card__delta${row.today_new === 0 ? ' zero' : ''}`;
  return (
    <div className={cls} onClick={() => onClick(row.company)}>
      <div className="sites-company-card__name">
        <span className={`sites-dot ${row.alert_level}`} />
        {row.company}
      </div>
      <div className="sites-company-card__meta">
        <span className={deltaCls}>{row.today_new === 0 ? '·' : `+${row.today_new}`}</span>
        {relativeTime(row.last_run_at)}
      </div>
    </div>
  );
}
```

- [ ] **Step 4.4: Run test to verify passes**

```bash
cd frontend && npm test -- CompanyCard.test 2>&1 | tail -10
```
Expected: 5 passes.

- [ ] **Step 4.5: Commit**

```bash
git add frontend/src/components/sites/CompanyCard.tsx frontend/src/components/sites/CompanyCard.test.tsx
git commit -m "feat(sites-ui): CompanyCard component

Compact card with status dot, name (Fraunces), today_new delta, and
relative last_run_at. Click surfaces the company name to the parent."
```

---

## Task 5 — `<CategoryGroup/>` (TDD)

**Files:**
- Create: `frontend/src/components/sites/CategoryGroup.tsx`
- Create: `frontend/src/components/sites/CategoryGroup.test.tsx`

- [ ] **Step 5.1: Write failing test**

Create `frontend/src/components/sites/CategoryGroup.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import CategoryGroup from './CategoryGroup';
import type { SiteRow } from './types';

const baseRow: SiteRow = {
  company: '',
  source: 'internet_official',
  last_run_at: null,
  last_status: 'success',
  today_new: 0,
  last_error_short: '',
  alert_level: 'green',
};

describe('CategoryGroup', () => {
  it('renders category title and count', () => {
    const rows: SiteRow[] = [
      { ...baseRow, company: '腾讯' },
      { ...baseRow, company: '阿里巴巴' },
    ];
    render(<CategoryGroup label="互联网官网" rows={rows} selectedCompany={null} onSelect={() => {}} />);
    expect(screen.getByText('互联网官网')).toBeInTheDocument();
    expect(screen.getByText('(2)')).toBeInTheDocument();
  });

  it('renders one CompanyCard per row', () => {
    const rows: SiteRow[] = [
      { ...baseRow, company: '腾讯' },
      { ...baseRow, company: '阿里巴巴' },
      { ...baseRow, company: '字节跳动' },
    ];
    const { container } = render(
      <CategoryGroup label="互联网官网" rows={rows} selectedCompany={null} onSelect={() => {}} />,
    );
    expect(container.querySelectorAll('.sites-company-card').length).toBe(3);
  });

  it('marks the selected card as selected', () => {
    const rows: SiteRow[] = [
      { ...baseRow, company: '腾讯' },
      { ...baseRow, company: '阿里巴巴' },
    ];
    const { container } = render(
      <CategoryGroup label="互联网官网" rows={rows} selectedCompany="阿里巴巴" onSelect={() => {}} />,
    );
    const selected = container.querySelectorAll('.sites-company-card.selected');
    expect(selected.length).toBe(1);
    expect(selected[0].textContent).toContain('阿里巴巴');
  });
});
```

- [ ] **Step 5.2: Run test to verify it fails**

```bash
cd frontend && npm test -- CategoryGroup.test 2>&1 | tail -10
```
Expected: 3 failures with `Cannot find module './CategoryGroup'`.

- [ ] **Step 5.3: Implement CategoryGroup**

Create `frontend/src/components/sites/CategoryGroup.tsx`:

```tsx
import CompanyCard from './CompanyCard';
import type { SiteRow } from './types';

interface CategoryGroupProps {
  label: string;
  rows: SiteRow[];
  selectedCompany: string | null;
  onSelect: (company: string) => void;
}

export default function CategoryGroup({ label, rows, selectedCompany, onSelect }: CategoryGroupProps) {
  return (
    <section className="sites-category-group">
      <header className="sites-category-header">
        <h2 className="sites-category-title">{label}</h2>
        <span className="sites-category-count">({rows.length})</span>
      </header>
      <div className="sites-card-grid">
        {rows.map((row) => (
          <CompanyCard
            key={`${row.source}::${row.company}`}
            row={row}
            selected={row.company === selectedCompany}
            onClick={onSelect}
          />
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 5.4: Run test to verify passes**

```bash
cd frontend && npm test -- CategoryGroup.test 2>&1 | tail -10
```
Expected: 3 passes.

- [ ] **Step 5.5: Commit**

```bash
git add frontend/src/components/sites/CategoryGroup.tsx frontend/src/components/sites/CategoryGroup.test.tsx
git commit -m "feat(sites-ui): CategoryGroup component

Wraps a list of CompanyCards under a header with company count.
Forwards the selectedCompany state down."
```

---

## Task 6 — `<RecrawlButton/>` (TDD)

**Files:**
- Create: `frontend/src/components/sites/RecrawlButton.tsx`
- Create: `frontend/src/components/sites/RecrawlButton.test.tsx`

- [ ] **Step 6.1: Write failing test**

Create `frontend/src/components/sites/RecrawlButton.test.tsx`:

```tsx
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import RecrawlButton from './RecrawlButton';
import * as api from '../../api';

vi.mock('../../api', async () => {
  const actual = await vi.importActual<typeof import('../../api')>('../../api');
  return {
    ...actual,
    triggerSiteRecrawl: vi.fn(),
  };
});

function mockResponse<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config: { headers: {} } as InternalAxiosRequestConfig,
  };
}

describe('RecrawlButton', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders idle state with "立即重跑这个节点"', () => {
    render(<RecrawlButton company="腾讯" inFlight={false} onSubmit={() => {}} />);
    expect(screen.getByRole('button', { name: /立即重跑这个节点/ })).toBeInTheDocument();
  });

  it('renders disabled spinner state when inFlight', () => {
    render(<RecrawlButton company="腾讯" inFlight onSubmit={() => {}} />);
    const btn = screen.getByRole('button');
    expect(btn).toBeDisabled();
    expect(btn.textContent).toContain('重跑中');
  });

  it('POSTs and calls onSubmit on click', async () => {
    vi.mocked(api.triggerSiteRecrawl).mockResolvedValue(
      mockResponse({ parent_log_id: 42, message: '已启动' }),
    );
    const onSubmit = vi.fn();
    render(<RecrawlButton company="腾讯" inFlight={false} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() => {
      expect(api.triggerSiteRecrawl).toHaveBeenCalledWith('腾讯');
      expect(onSubmit).toHaveBeenCalledWith('腾讯', { parent_log_id: 42, message: '已启动' });
    });
  });

  it('calls onSubmit with null on error', async () => {
    vi.mocked(api.triggerSiteRecrawl).mockRejectedValue(new Error('boom'));
    const onSubmit = vi.fn();
    render(<RecrawlButton company="腾讯" inFlight={false} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith('腾讯', null);
    });
  });
});
```

- [ ] **Step 6.2: Run test to verify it fails**

```bash
cd frontend && npm test -- RecrawlButton.test 2>&1 | tail -10
```
Expected: 4 failures with `Cannot find module './RecrawlButton'`.

- [ ] **Step 6.3: Implement RecrawlButton**

Create `frontend/src/components/sites/RecrawlButton.tsx`:

```tsx
import { useState } from 'react';

import { triggerSiteRecrawl } from '../../api';
import type { SiteRecrawlOut } from './types';

interface RecrawlButtonProps {
  company: string;
  inFlight: boolean;
  onSubmit: (company: string, result: SiteRecrawlOut | null) => void;
}

export default function RecrawlButton({ company, inFlight, onSubmit }: RecrawlButtonProps) {
  const [submitting, setSubmitting] = useState(false);
  const disabled = inFlight || submitting;

  const handleClick = async () => {
    setSubmitting(true);
    try {
      const res = await triggerSiteRecrawl(company);
      onSubmit(company, res.data);
    } catch {
      onSubmit(company, null);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <button
      type="button"
      className="hf-btn primary lg"
      style={{ width: '100%' }}
      disabled={disabled}
      onClick={handleClick}
    >
      {disabled ? (
        <>
          <span className="hf-spin" /> 重跑中…
        </>
      ) : (
        '立即重跑这个节点'
      )}
    </button>
  );
}
```

- [ ] **Step 6.4: Run test to verify passes**

```bash
cd frontend && npm test -- RecrawlButton.test 2>&1 | tail -10
```
Expected: 4 passes.

- [ ] **Step 6.5: Commit**

```bash
git add frontend/src/components/sites/RecrawlButton.tsx frontend/src/components/sites/RecrawlButton.test.tsx
git commit -m "feat(sites-ui): RecrawlButton component

Terracotta primary button. POSTs /api/sites/{company}/recrawl,
swaps to spinner+disabled while submitting or while parent
indicates inFlight. Forwards the result (or null on error) to
parent so it can manage polling cadence + toasts."
```

---

## Task 7 — `<SiteDetailPanel/>` (TDD)

**Files:**
- Create: `frontend/src/components/sites/SiteDetailPanel.tsx`
- Create: `frontend/src/components/sites/SiteDetailPanel.test.tsx`

- [ ] **Step 7.1: Write failing test**

Create `frontend/src/components/sites/SiteDetailPanel.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import SiteDetailPanel from './SiteDetailPanel';
import type { SiteRow, SiteRun } from './types';

const baseRow: SiteRow = {
  company: '腾讯',
  source: 'internet_official',
  last_run_at: '2026-04-27T03:00:00',
  last_status: 'success',
  today_new: 12,
  last_error_short: '',
  alert_level: 'green',
};

const baseRun: SiteRun = {
  id: 1,
  source: 'internet_official',
  started_at: '2026-04-27T03:00:00',
  finished_at: '2026-04-27T03:01:00',
  status: 'success',
  fetched_count: 38,
  new_count: 12,
  error_message: '',
  duration_ms: 60000,
};

describe('SiteDetailPanel', () => {
  it('shows empty placeholder when row is null', () => {
    render(<SiteDetailPanel row={null} runs={[]} inFlight={false} onRecrawlSubmit={() => {}} />);
    expect(screen.getByText(/点左侧任意公司查看详情/)).toBeInTheDocument();
  });

  it('shows company name and source for selected row', () => {
    render(<SiteDetailPanel row={baseRow} runs={[baseRun]} inFlight={false} onRecrawlSubmit={() => {}} />);
    expect(screen.getByText('腾讯')).toBeInTheDocument();
    expect(screen.getByText(/internet_official/)).toBeInTheDocument();
  });

  it('renders sparkline when runs are non-empty', () => {
    const { container } = render(
      <SiteDetailPanel row={baseRow} runs={[baseRun, { ...baseRun, id: 2 }]} inFlight={false} onRecrawlSubmit={() => {}} />,
    );
    expect(container.querySelectorAll('.sites-sparkline__bar').length).toBe(2);
  });

  it('renders error block when last run failed and has message', () => {
    const failed: SiteRun = { ...baseRun, status: 'failed', error_message: 'TimeoutError: 12s' };
    render(<SiteDetailPanel row={baseRow} runs={[failed]} inFlight={false} onRecrawlSubmit={() => {}} />);
    expect(screen.getByText(/最近一次错误/)).toBeInTheDocument();
    expect(screen.getByText('TimeoutError: 12s')).toBeInTheDocument();
  });

  it('renders the recrawl button for any non-null row', () => {
    render(<SiteDetailPanel row={baseRow} runs={[]} inFlight={false} onRecrawlSubmit={() => {}} />);
    expect(screen.getByRole('button', { name: /立即重跑这个节点/ })).toBeInTheDocument();
  });
});
```

- [ ] **Step 7.2: Run test to verify it fails**

```bash
cd frontend && npm test -- SiteDetailPanel.test 2>&1 | tail -10
```
Expected: 5 failures with `Cannot find module './SiteDetailPanel'`.

- [ ] **Step 7.3: Implement SiteDetailPanel**

Create `frontend/src/components/sites/SiteDetailPanel.tsx`:

```tsx
import RecrawlButton from './RecrawlButton';
import RunSparkline from './RunSparkline';
import type { SiteRecrawlOut, SiteRow, SiteRun } from './types';

interface SiteDetailPanelProps {
  row: SiteRow | null;
  runs: SiteRun[];
  inFlight: boolean;
  onRecrawlSubmit: (company: string, result: SiteRecrawlOut | null) => void;
}

export default function SiteDetailPanel({ row, runs, inFlight, onRecrawlSubmit }: SiteDetailPanelProps) {
  if (!row) {
    return (
      <aside className="sites-detail-card empty">
        ← 点左侧任意公司查看详情
      </aside>
    );
  }

  const lastRun = runs[0];
  const showError = lastRun && lastRun.status === 'failed' && lastRun.error_message;

  return (
    <aside className="sites-detail-card">
      <div className="sites-detail-card__name">
        <span className={`sites-dot ${row.alert_level}`} />
        {row.company}
      </div>
      <div className="sites-detail-card__meta">
        <code>{row.source}</code>
      </div>

      <RunSparkline runs={runs} />

      {showError ? (
        <details className="sites-detail-card__error">
          <summary>最近一次错误</summary>
          <pre>{lastRun.error_message}</pre>
        </details>
      ) : null}

      <div style={{ marginTop: 16 }}>
        <RecrawlButton company={row.company} inFlight={inFlight} onSubmit={onRecrawlSubmit} />
      </div>
    </aside>
  );
}
```

- [ ] **Step 7.4: Run test to verify passes**

```bash
cd frontend && npm test -- SiteDetailPanel.test 2>&1 | tail -10
```
Expected: 5 passes.

- [ ] **Step 7.5: Commit**

```bash
git add frontend/src/components/sites/SiteDetailPanel.tsx frontend/src/components/sites/SiteDetailPanel.test.tsx
git commit -m "feat(sites-ui): SiteDetailPanel component

Right-side sticky panel: header + source meta + RunSparkline +
collapsed error <details> when last run failed + RecrawlButton.
Empty state when no company is selected."
```

---

## Task 8 — `<SitesSummaryBar/>` (TDD)

**Files:**
- Create: `frontend/src/components/sites/SitesSummaryBar.tsx`
- Create: `frontend/src/components/sites/SitesSummaryBar.test.tsx`

- [ ] **Step 8.1: Write failing test**

Create `frontend/src/components/sites/SitesSummaryBar.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import SitesSummaryBar from './SitesSummaryBar';
import type { SiteRow, SitesSummary } from './types';

const baseSummary: SitesSummary = {
  active: 38,
  alerted: 0,
  disabled: 0,
  total_today_new: 142,
  last_batch_at: '2026-04-27T01:00:00',
  last_batch_status: 'success',
};

const baseRow: SiteRow = {
  company: '',
  source: 'internet_official',
  last_run_at: null,
  last_status: 'success',
  today_new: 0,
  last_error_short: '',
  alert_level: 'green',
};

describe('SitesSummaryBar', () => {
  it('renders the three KPI counters and total_today_new', () => {
    render(<SitesSummaryBar summary={baseSummary} rows={[]} onJumpToCompany={() => {}} />);
    expect(screen.getByText(/运行中/)).toBeInTheDocument();
    expect(screen.getByText('38')).toBeInTheDocument();
    expect(screen.getByText(/今日新增/)).toBeInTheDocument();
    expect(screen.getByText('142')).toBeInTheDocument();
  });

  it('does not render the alert banner when alerted < 2', () => {
    const summary = { ...baseSummary, alerted: 1 };
    const { container } = render(<SitesSummaryBar summary={summary} rows={[]} onJumpToCompany={() => {}} />);
    expect(container.querySelector('.sites-alert-banner')).toBeNull();
  });

  it('does not render the alert banner when no row is red', () => {
    const summary = { ...baseSummary, alerted: 3 };
    const rows: SiteRow[] = [
      { ...baseRow, company: 'a', alert_level: 'yellow' },
      { ...baseRow, company: 'b', alert_level: 'yellow' },
      { ...baseRow, company: 'c', alert_level: 'yellow' },
    ];
    const { container } = render(<SitesSummaryBar summary={summary} rows={rows} onJumpToCompany={() => {}} />);
    expect(container.querySelector('.sites-alert-banner')).toBeNull();
  });

  it('renders the alert banner when alerted >= 2 and at least one row is red', () => {
    const summary = { ...baseSummary, alerted: 2 };
    const rows: SiteRow[] = [
      { ...baseRow, company: '腾讯', alert_level: 'red' },
      { ...baseRow, company: '中金公司', alert_level: 'yellow' },
    ];
    render(<SitesSummaryBar summary={summary} rows={rows} onJumpToCompany={() => {}} />);
    expect(screen.getByText(/今日 2 家爬虫疑似失效/)).toBeInTheDocument();
    expect(screen.getByText(/腾讯/)).toBeInTheDocument();
  });

  it('clicking the alert banner jumps to the first red company', () => {
    const summary = { ...baseSummary, alerted: 2 };
    const rows: SiteRow[] = [
      { ...baseRow, company: '中金公司', alert_level: 'yellow' },
      { ...baseRow, company: '腾讯', alert_level: 'red' },
      { ...baseRow, company: '阿里巴巴', alert_level: 'red' },
    ];
    const onJump = vi.fn();
    const { container } = render(<SitesSummaryBar summary={summary} rows={rows} onJumpToCompany={onJump} />);
    const banner = container.querySelector('.sites-alert-banner') as HTMLElement;
    expect(banner).toBeTruthy();
    fireEvent.click(banner);
    expect(onJump).toHaveBeenCalledWith('腾讯');
  });
});
```

- [ ] **Step 8.2: Run test to verify it fails**

```bash
cd frontend && npm test -- SitesSummaryBar.test 2>&1 | tail -10
```
Expected: 5 failures with `Cannot find module './SitesSummaryBar'`.

- [ ] **Step 8.3: Implement SitesSummaryBar**

Create `frontend/src/components/sites/SitesSummaryBar.tsx`:

```tsx
import type { SiteRow, SitesSummary } from './types';

interface SitesSummaryBarProps {
  summary: SitesSummary;
  rows: SiteRow[];
  onJumpToCompany: (company: string) => void;
}

export default function SitesSummaryBar({ summary, rows, onJumpToCompany }: SitesSummaryBarProps) {
  const redRows = rows.filter((r) => r.alert_level === 'red');
  const showBanner = summary.alerted >= 2 && redRows.length > 0;

  const bannerNames = rows
    .filter((r) => r.alert_level === 'red' || r.alert_level === 'yellow')
    .slice(0, 3)
    .map((r) => r.company)
    .join('、');

  const handleBannerClick = () => {
    if (redRows.length > 0) {
      onJumpToCompany(redRows[0].company);
    }
  };

  return (
    <>
      <div className="sites-summary-bar">
        <span className="hf-pill emerald">
          <span className="sites-dot green" />
          运行中 <strong style={{ marginLeft: 4 }}>{summary.active}</strong>
        </span>
        <span className="hf-pill amber">
          ⚠ 报警 <strong style={{ marginLeft: 4 }}>{summary.alerted}</strong>
        </span>
        <span className="hf-pill">
          <span className="sites-dot unknown" />
          停用 <strong style={{ marginLeft: 4 }}>{summary.disabled}</strong>
        </span>
        <span style={{ flex: 1 }} />
        <span className="hf-cap" style={{ marginRight: 8 }}>今日新增</span>
        <span className="sites-kpi-num">{summary.total_today_new}</span>
      </div>

      {showBanner ? (
        <div className="sites-alert-banner" onClick={handleBannerClick}>
          ⚠ 今日 {summary.alerted} 家爬虫疑似失效（{bannerNames}）— 点这里查看
        </div>
      ) : null}
    </>
  );
}
```

- [ ] **Step 8.4: Run test to verify passes**

```bash
cd frontend && npm test -- SitesSummaryBar.test 2>&1 | tail -10
```
Expected: 5 passes.

- [ ] **Step 8.5: Commit**

```bash
git add frontend/src/components/sites/SitesSummaryBar.tsx frontend/src/components/sites/SitesSummaryBar.test.tsx
git commit -m "feat(sites-ui): SitesSummaryBar component

Top KPI bar (active/alerted/disabled pills + today_new big number),
plus conditional alert banner shown only when alerted >= 2 and at
least one row is red. Click banner jumps to first red company."
```

---

## Task 9 — `<Sites/>` page (orchestrator) + AppLayout wiring

**Files:**
- Create: `frontend/src/pages/Sites.tsx`
- Create: `frontend/src/pages/Sites.test.tsx`
- Modify: `frontend/src/AppLayout.tsx`

- [ ] **Step 9.1: Write failing test**

Create `frontend/src/pages/Sites.test.tsx`:

```tsx
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import Sites from './Sites';
import * as api from '../api';
import type { SiteRow, SiteRun, SitesSummary } from '../components/sites/types';

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api');
  return {
    ...actual,
    fetchSitesSummary: vi.fn(),
    fetchSites: vi.fn(),
    fetchSiteRuns: vi.fn(),
    triggerSiteRecrawl: vi.fn(),
  };
});

function mockResponse<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config: { headers: {} } as InternalAxiosRequestConfig,
  };
}

const baseSummary: SitesSummary = {
  active: 2,
  alerted: 0,
  disabled: 0,
  total_today_new: 25,
  last_batch_at: '2026-04-27T01:00:00',
  last_batch_status: 'success',
};

const tencentRow: SiteRow = {
  company: '腾讯',
  source: 'internet_official',
  last_run_at: '2026-04-27T03:00:00',
  last_status: 'success',
  today_new: 5,
  last_error_short: '',
  alert_level: 'green',
};

const aliRow: SiteRow = {
  ...tencentRow,
  company: '阿里巴巴',
  today_new: 7,
};

const cicc: SiteRow = {
  company: '中金公司',
  source: 'securities_zhiye',
  last_run_at: '2026-04-27T03:00:00',
  last_status: 'success',
  today_new: 3,
  last_error_short: '',
  alert_level: 'green',
};

const baseRun: SiteRun = {
  id: 1,
  source: 'internet_official',
  started_at: '2026-04-27T03:00:00',
  finished_at: '2026-04-27T03:01:00',
  status: 'success',
  fetched_count: 12,
  new_count: 5,
  error_message: '',
  duration_ms: 60000,
};

describe('Sites page', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    vi.mocked(api.fetchSitesSummary).mockResolvedValue(mockResponse(baseSummary));
    vi.mocked(api.fetchSites).mockResolvedValue(mockResponse([tencentRow, aliRow, cicc]));
    vi.mocked(api.fetchSiteRuns).mockResolvedValue(mockResponse([baseRun]));
    vi.mocked(api.triggerSiteRecrawl).mockResolvedValue(mockResponse({ parent_log_id: 99, message: '已启动' }));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('fetches summary and sites on mount', async () => {
    render(<MemoryRouter><Sites /></MemoryRouter>);
    await waitFor(() => {
      expect(api.fetchSitesSummary).toHaveBeenCalled();
      expect(api.fetchSites).toHaveBeenCalled();
    });
  });

  it('renders category groups derived from source', async () => {
    render(<MemoryRouter><Sites /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('互联网官网')).toBeInTheDocument();
      expect(screen.getByText('券商')).toBeInTheDocument();
    });
  });

  it('clicking a card opens the detail panel and fetches runs', async () => {
    render(<MemoryRouter><Sites /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('腾讯')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('腾讯'));
    await waitFor(() => {
      expect(api.fetchSiteRuns).toHaveBeenCalledWith('腾讯', 24);
    });
  });

  it('clicking the recrawl button POSTs to the recrawl endpoint', async () => {
    render(<MemoryRouter><Sites /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText('腾讯')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('腾讯'));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /立即重跑这个节点/ })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /立即重跑这个节点/ }));
    await waitFor(() => {
      expect(api.triggerSiteRecrawl).toHaveBeenCalledWith('腾讯');
    });
  });

  it('shows the empty state when no rows and no today_new', async () => {
    vi.mocked(api.fetchSitesSummary).mockResolvedValue(
      mockResponse({ ...baseSummary, total_today_new: 0 }),
    );
    vi.mocked(api.fetchSites).mockResolvedValue(mockResponse([]));
    render(<MemoryRouter><Sites /></MemoryRouter>);
    await waitFor(() => {
      expect(screen.getByText(/等首次跑完再回来看/)).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 9.2: Run test to verify it fails**

```bash
cd frontend && npm test -- Sites.test 2>&1 | tail -10
```
Expected: 5 failures with `Cannot find module './Sites'`.

- [ ] **Step 9.3: Implement Sites.tsx**

Create `frontend/src/pages/Sites.tsx`:

```tsx
import { useEffect, useMemo, useRef, useState } from 'react';

import { fetchSiteRuns, fetchSites, fetchSitesSummary } from '../api';
import CategoryGroup from '../components/sites/CategoryGroup';
import SiteDetailPanel from '../components/sites/SiteDetailPanel';
import SitesSummaryBar from '../components/sites/SitesSummaryBar';
import { ToastHost, useToast } from '../components/sites/ToastHost';
import type { SiteRecrawlOut, SiteRow, SiteRun, SitesSummary } from '../components/sites/types';

import '../styles/sites-theme.css';

const POLL_DEFAULT_MS = 8000;
const POLL_FAST_MS = 2000;

const SOURCE_GROUPS: Array<{ label: string; sources: string[] }> = [
  { label: '互联网官网', sources: ['internet_official'] },
  { label: '券商', sources: ['securities_zhiye', 'securities_zhiye_legacy', 'securities_hotjob', 'securities_moka_embedded'] },
  { label: '国央企', sources: ['state_owned_official'] },
  { label: '消费外企', sources: ['consumer_foreign_official'] },
];

function groupKeyForSource(source: string): string {
  for (const g of SOURCE_GROUPS) {
    if (g.sources.includes(source)) return g.label;
  }
  return source; // Unknown source → use raw label
}

interface SitesInnerProps {}

function SitesInner({}: SitesInnerProps) {
  const [summary, setSummary] = useState<SitesSummary | null>(null);
  const [rows, setRows] = useState<SiteRow[] | null>(null);
  const [selectedCompany, setSelectedCompany] = useState<string | null>(null);
  const [runs, setRuns] = useState<SiteRun[]>([]);
  const [recrawlInFlight, setRecrawlInFlight] = useState<Record<string, number>>({}); // company → submit ms
  const intervalRef = useRef<number | null>(null);
  const toast = useToast();

  const refresh = async (currentSelected: string | null) => {
    try {
      const [s, r] = await Promise.all([fetchSitesSummary(), fetchSites()]);
      setSummary(s.data);
      setRows(r.data);
      if (currentSelected) {
        const runsRes = await fetchSiteRuns(currentSelected, 24);
        setRuns(runsRes.data);
      }
    } catch {
      // Silent for v1; UI stays on prior data.
    }
  };

  // Initial fetch + polling
  useEffect(() => {
    refresh(selectedCompany);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // (Re)start the interval whenever the cadence should change.
  useEffect(() => {
    const cadence = Object.keys(recrawlInFlight).length > 0 ? POLL_FAST_MS : POLL_DEFAULT_MS;
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
    }
    intervalRef.current = window.setInterval(() => {
      refresh(selectedCompany);
    }, cadence);
    return () => {
      if (intervalRef.current !== null) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recrawlInFlight, selectedCompany]);

  // Refetch runs when selection changes
  useEffect(() => {
    if (!selectedCompany) {
      setRuns([]);
      return;
    }
    fetchSiteRuns(selectedCompany, 24).then((res) => setRuns(res.data)).catch(() => {});
  }, [selectedCompany]);

  // Watch for recrawl completion: any run whose started_at > submit ms means it just landed.
  useEffect(() => {
    if (!selectedCompany || Object.keys(recrawlInFlight).length === 0) return;
    const submitMs = recrawlInFlight[selectedCompany];
    if (!submitMs) return;
    const completed = runs.find(
      (r) => new Date(r.started_at).getTime() > submitMs && (r.status === 'success' || r.status === 'failed'),
    );
    if (completed) {
      toast.show(
        `${selectedCompany} 重跑${completed.status === 'success' ? '成功' : '失败'}`,
        completed.status === 'success' ? 'success' : 'failed',
      );
      setRecrawlInFlight((prev) => {
        const next = { ...prev };
        delete next[selectedCompany];
        return next;
      });
    }
  }, [runs, selectedCompany, recrawlInFlight, toast]);

  const handleRecrawlSubmit = (company: string, result: SiteRecrawlOut | null) => {
    if (result === null) {
      toast.show(`${company} 重跑提交失败`, 'failed');
      return;
    }
    setRecrawlInFlight((prev) => ({ ...prev, [company]: Date.now() }));
    toast.show(`${company} 重跑已启动`, 'success');
  };

  const groupedRows = useMemo(() => {
    if (!rows) return [];
    const buckets = new Map<string, SiteRow[]>();
    for (const row of rows) {
      const key = groupKeyForSource(row.source);
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key)!.push(row);
    }
    return SOURCE_GROUPS
      .filter((g) => buckets.has(g.label))
      .map((g) => ({ label: g.label, rows: buckets.get(g.label)! }))
      .concat(
        Array.from(buckets.entries())
          .filter(([k]) => !SOURCE_GROUPS.some((g) => g.label === k))
          .map(([label, rs]) => ({ label, rows: rs })),
      );
  }, [rows]);

  const isEmpty =
    summary !== null && rows !== null && rows.length === 0 && summary.total_today_new === 0;

  if (isEmpty) {
    return (
      <div className="hf" data-theme="sites">
        <div className="sites-shell">
          <div className="sites-empty">
            <h1 className="sites-empty__title">等首次跑完再回来看</h1>
            <p className="sites-empty__sub">
              明天 09:00 自动跑全量 tier crawl，
              或现在去 <a href="/crawl">触发爬取</a> 手动跑一次。
            </p>
          </div>
        </div>
      </div>
    );
  }

  const selectedRow = rows?.find((r) => r.company === selectedCompany) ?? null;
  const selectedInFlight = selectedCompany ? Boolean(recrawlInFlight[selectedCompany]) : false;

  return (
    <div className="hf" data-theme="sites">
      <div className="sites-shell">
        {summary ? (
          <SitesSummaryBar summary={summary} rows={rows ?? []} onJumpToCompany={setSelectedCompany} />
        ) : null}
        <div className="sites-content">
          <div>
            {groupedRows.map((g) => (
              <CategoryGroup
                key={g.label}
                label={g.label}
                rows={g.rows}
                selectedCompany={selectedCompany}
                onSelect={setSelectedCompany}
              />
            ))}
          </div>
          <SiteDetailPanel
            row={selectedRow}
            runs={runs}
            inFlight={selectedInFlight}
            onRecrawlSubmit={handleRecrawlSubmit}
          />
        </div>
      </div>
    </div>
  );
}

export default function Sites() {
  return (
    <ToastHost>
      <SitesInner />
    </ToastHost>
  );
}
```

- [ ] **Step 9.4: Wire route + menu in AppLayout.tsx**

Edit `frontend/src/AppLayout.tsx`:

1. Add import after the `Scheduler` import (around line 26):
   ```tsx
   import Sites from './pages/Sites';
   ```

2. Add menu entry to `menuItems` array (after the `/scheduler` entry — around line 35):
   ```tsx
   { key: '/sites', icon: <ClockCircleOutlined />, label: <Link to="/sites">站点节点视图</Link> },
   ```
   (Reuse `ClockCircleOutlined` since it's already imported; or import a different icon like `RadarChartOutlined` if you prefer.)

3. Add to `PAGE_TITLES` record (around line 47):
   ```tsx
   '/sites': '站点节点视图',
   ```

4. Add route inside `<Routes>` (around line 114, after `/scheduler`):
   ```tsx
   <Route path="/sites" element={<Sites />} />
   ```

- [ ] **Step 9.5: Run test to verify passes**

```bash
cd frontend && npm test -- Sites.test 2>&1 | tail -15
```
Expected: 5 passes.

- [ ] **Step 9.6: Run lint and full build**

```bash
cd frontend && npm run lint 2>&1 | tail -5
cd frontend && npm run build 2>&1 | tail -5
```
Expected: 0 lint errors; build succeeds.

- [ ] **Step 9.7: Commit**

```bash
git add frontend/src/pages/Sites.tsx frontend/src/pages/Sites.test.tsx frontend/src/AppLayout.tsx
git commit -m "feat(sites-ui): Sites page + AppLayout wiring

Top-level page that owns polling lifecycle (8s default, 2s during
recrawls), selectedCompany state, source→group bucketing, and
empty-state branching. Menu entry '站点节点视图' + route /sites."
```

---

## Task 10 — Final verification + CLAUDE.md update

**Files:**
- Modify: `CLAUDE.md` — add brief Phase 2 UI section.

- [ ] **Step 10.1: Run full test suite**

```bash
cd frontend && npm test 2>&1 | tail -10
```
Expected: all suites green, including the 6 new test files.

- [ ] **Step 10.2: Run lint + build**

```bash
cd frontend && npm run lint
cd frontend && npm run build
```
Expected: 0 lint errors; build succeeds.

- [ ] **Step 10.3: Manual smoke test against backend**

In one terminal:
```bash
cd backend && PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

In another:
```bash
cd frontend && npm run dev
```

Open `http://localhost:5173/sites` (you'll be prompted to mock-login first; use whatever credentials AppLayout's RequirePreviewSession expects).

Visual checks:
- Page loads in HiFi terracotta — parchment background, Fraunces serif headers, terracotta accents.
- 4 category groups render IF backend has data; empty state if not.
- Click a card → detail panel updates with sparkline + recrawl button.
- Click recrawl on a known-good company → toast appears, polling speeds up (visible if you watch the network panel).
- Other admin pages (`/jobs`, `/crawl`, `/scheduler`) are unaffected — still AntD-styled.

If the backend has no `company_crawl_logs` rows yet, you can seed quickly:
```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
from app.database import SessionLocal
from app.models import CompanyCrawlLog
from datetime import datetime, timedelta
db = SessionLocal()
now = datetime.utcnow()
for company in ['腾讯', '阿里巴巴', '字节跳动', '美团', '中金公司']:
    db.add(CompanyCrawlLog(
        source='internet_official' if company != '中金公司' else 'securities_zhiye',
        company=company, started_at=now - timedelta(hours=3), finished_at=now - timedelta(hours=2, minutes=55),
        status='success', fetched_count=20, new_count=5, error_message='', duration_ms=300000,
    ))
db.commit(); db.close(); print('seeded')
"
```

- [ ] **Step 10.4: Update CLAUDE.md**

Edit `CLAUDE.md`. Find the "Sites monitor" section (look for `**Sites monitor**`). Append at the end of that bullet list:

```
- **UI** (`/frontend/src/pages/Sites.tsx` + `components/sites/*` + `styles/{hifi-tokens,sites-theme}.css`): `/sites` route, HiFi terracotta scoped via `<div className="hf" data-theme="sites">`. Adaptive polling (8s default, 2s during recrawls). Source→group bucketing maps internet/state_owned/securities/consumer_foreign onto 4 visible categories. Other admin pages unaffected.
```

- [ ] **Step 10.5: Final commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): document sites monitor Phase 2 UI"
```

---

## Notes for the implementer

- **No AntD inside `/sites`**: deliberate scoping. The page wraps in `<div className="hf" data-theme="sites">` and uses raw HTML + class-name styling from `sites-theme.css` and `hifi-tokens.css`. Don't reach for `<Card/>`, `<Table/>`, `<Drawer/>` etc — would defeat the design system.

- **The existing `RequirePreviewSession`** wraps all routes including `/sites`, so the page is gated by the same mock-login as other admin pages. You don't need to add anything; the wiring in AppLayout handles it.

- **Source→group mapping** is hard-coded in `SOURCE_GROUPS`. New sources land under their raw name as a fallback group. Adding "金融机构" or "外企" subdivisions later is a one-line addition to the array.

- **Polling reuses the same `interval` ref**: when cadence changes (recrawl starts/stops), the effect cancels and re-creates. Don't try to "smartly" persist across changes; the cancel-and-recreate pattern is simpler and safe.

- **Toast lifecycle** is independent — they auto-dismiss on a setTimeout regardless of polling state. Don't gate them on the recrawl-in-flight set.

- **Empty state condition** is `rows.length === 0 && summary.total_today_new === 0`. If `rows` is non-empty but `total_today_new === 0`, show the dashboard (companies have history but no fresh data today — that's still useful info).

- **`groupKeyForSource` returns `source` verbatim** when unmatched. This is intentional: surface unknown sources as a debug aid rather than hiding them.

- **`fetchSites` no source filter**: Phase 2 always fetches all sources. The endpoint supports `?source=` for future filtering UI.

- **Tests use `MemoryRouter`** for the page-level test; child component tests don't need it (no `<Link/>` inside).

- **`vi.useFakeTimers()`** in the page tests prevents the polling interval from firing inside the test (which would cause unexpected fetch calls). The integration tests don't `advanceTimersByTime` because they're checking the initial fetch + click behaviors, not polling.
