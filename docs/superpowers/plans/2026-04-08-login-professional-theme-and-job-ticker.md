# Login Professional Theme And Job Ticker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-theme the login page into a more professional, education-oriented style and add a top scrolling featured-jobs ticker using static exemplar jobs.

**Architecture:** Keep the implementation inside the existing `Login` page so routing and mock-auth behavior remain unchanged. Add a small static featured-jobs dataset plus a ticker UI at the top of the page, then update styles and text content to the approved deep-blue professional direction while preserving the existing animated coverage counters.

**Tech Stack:** React 19, TypeScript, Ant Design 6, CSS, Vitest, React Testing Library

---

## File Structure

- Modify: `frontend/src/pages/Login.tsx`
  Add static featured jobs, render the top ticker, update text content, and preserve login/counter behavior.
- Modify: `frontend/src/pages/Login.css`
  Re-theme the page to the approved deep-blue professional style and add ticker animation/layout styles.
- Modify: `frontend/src/pages/Login.test.tsx`
  Lock the new copy and ticker content with tests.

## Task 1: Lock The New Login Content And Ticker In Tests

**Files:**
- Modify: `frontend/src/pages/Login.test.tsx`

- [ ] **Step 1: Add failing assertions for the new approved content**

Update `frontend/src/pages/Login.test.tsx` so the render test expects:

```tsx
expect(screen.getByText('重点岗位速览')).toBeInTheDocument();
expect(screen.getByText('字节跳动 · 算法工程师 · 北京')).toBeInTheDocument();
expect(screen.getByText('中金公司 · 研究助理 · 上海')).toBeInTheDocument();
expect(screen.getByText('国家电网 · 信息技术岗 · 南京')).toBeInTheDocument();
expect(screen.getByText('招商银行 · 数据分析岗 · 深圳')).toBeInTheDocument();
expect(screen.getByText('面向高校就业与职业发展场景，聚合互联网、券商、央国企、银行等重点平台岗位，强调覆盖、筛选与更新时效。')).toBeInTheDocument();
expect(screen.getByText('重点公司持续覆盖，岗位入口统一归集')).toBeInTheDocument();
expect(screen.getByText('春招开放信息与岗位动态快速更新')).toBeInTheDocument();
expect(screen.getByText('更适合学校老师与学生一眼扫清核心信息')).toBeInTheDocument();
expect(screen.getByText('登录后继续访问岗位总览、申请流程看板与配置中心。')).toBeInTheDocument();
expect(screen.getByText('持续追踪岗位动态、目标公司与申请进展。')).toBeInTheDocument();
expect(screen.getByText('让求职信息流保持更新与可执行。')).toBeInTheDocument();
```

- [ ] **Step 2: Run the page test to verify red state**

Run:

```bash
cd frontend && npm run test -- --run src/pages/Login.test.tsx
```

Expected: FAIL because the current page still uses the old wording and has no top ticker.

- [ ] **Step 3: Keep the animation test expectations intact**

Retain the existing expectations that verify:

```tsx
expect(screen.getByText('3486 家公司')).toBeInTheDocument();
expect(screen.getByText('1087 更新')).toBeInTheDocument();
expect(screen.getByText('1088 更新')).toBeInTheDocument();
```

This ensures the redesign does not remove the approved metric animation behavior.

## Task 2: Render The Featured Jobs Ticker And New Hero Content

**Files:**
- Modify: `frontend/src/pages/Login.tsx`
- Test: `frontend/src/pages/Login.test.tsx`

- [ ] **Step 1: Add a small static featured jobs dataset**

Inside `frontend/src/pages/Login.tsx`, add a typed constant near the top:

```tsx
interface FeaturedJob {
  company: string;
  title: string;
  location: string;
  track: string;
}

const FEATURED_JOBS: FeaturedJob[] = [
  { company: '字节跳动', title: '算法工程师', location: '北京', track: '互联网' },
  { company: '中金公司', title: '研究助理', location: '上海', track: '券商' },
  { company: '国家电网', title: '信息技术岗', location: '南京', track: '央国企' },
  { company: '招商银行', title: '数据分析岗', location: '深圳', track: '银行' },
];
```

- [ ] **Step 2: Render the top ticker above the current shell**

Add this block inside the page root, before `login-page__shell`:

```tsx
<section className="login-page__ticker" aria-label="重点岗位速览">
  <div className="login-page__ticker-track">
    <span className="login-page__ticker-badge">重点岗位速览</span>
    {[...FEATURED_JOBS, ...FEATURED_JOBS].map((job, index) => (
      <span className="login-page__ticker-item" key={`${job.company}-${job.title}-${index}`}>
        <strong>{job.track}</strong>
        <span>{`${job.company} · ${job.title} · ${job.location}`}</span>
      </span>
    ))}
  </div>
</section>
```

- [ ] **Step 3: Update the left-side content to the approved copy**

Replace the existing description and value points with:

```tsx
<Paragraph className="login-page__description">
  面向高校就业与职业发展场景，聚合互联网、券商、央国企、银行等重点平台岗位，强调覆盖、筛选与更新时效。
</Paragraph>

<ul className="login-page__value-list">
  <li className="login-page__value-item">
    <span className="login-page__value-dot" aria-hidden="true" />
    <span>重点公司持续覆盖，岗位入口统一归集</span>
  </li>
  <li className="login-page__value-item">
    <span className="login-page__value-dot" aria-hidden="true" />
    <span>春招开放信息与岗位动态快速更新</span>
  </li>
  <li className="login-page__value-item">
    <span className="login-page__value-dot" aria-hidden="true" />
    <span>更适合学校老师与学生一眼扫清核心信息</span>
  </li>
</ul>
```

- [ ] **Step 4: Run the page test to verify green state**

Run:

```bash
cd frontend && npm run test -- --run src/pages/Login.test.tsx
```

Expected: PASS.

## Task 3: Apply The Professional Theme Styling

**Files:**
- Modify: `frontend/src/pages/Login.css`
- Test: `frontend/src/pages/Login.test.tsx`

- [ ] **Step 1: Re-theme the page around deep blue and structured density**

Update the main page styles so they follow these rules:

```css
.login-page {
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(37, 99, 235, 0.16), transparent 28%),
    linear-gradient(180deg, #eef4ff 0%, #f7f9fc 30%, #f4f6f9 100%);
  color: #0f172a;
}

.login-page__shell {
  max-width: 1220px;
  padding: 28px 24px 48px;
  grid-template-columns: minmax(0, 1.18fr) minmax(360px, 430px);
  gap: 32px;
  align-items: start;
}

.login-page__title.ant-typography {
  margin-top: 8px;
  font-size: clamp(2.5rem, 4vw, 3.8rem);
  line-height: 1.12;
  color: #0f172a;
}

.login-page__description.ant-typography {
  margin-bottom: 24px;
  color: #475569;
  font-size: 17px;
}
```

- [ ] **Step 2: Add ticker animation and item styling**

Add styles like these to `frontend/src/pages/Login.css`:

```css
.login-page__ticker {
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(10px);
}

.login-page__ticker-track {
  width: max-content;
  min-width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 24px;
  animation: login-ticker-scroll 28s linear infinite;
}

.login-page__ticker-badge {
  flex: none;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(29, 78, 216, 0.08);
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
}

.login-page__ticker-item {
  flex: none;
  display: inline-flex;
  gap: 8px;
  align-items: center;
  padding: 7px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.18);
  color: #334155;
  font-size: 13px;
}

.login-page__ticker-item strong {
  color: #0f172a;
}

@keyframes login-ticker-scroll {
  from { transform: translateX(0); }
  to { transform: translateX(-50%); }
}
```

- [ ] **Step 3: Tighten card, stats, and density to fit the approved style**

Adjust the existing classes so the page reads more like a professional platform:

```css
.login-page__stat {
  padding: 18px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
}

.login-page__panel {
  padding: 30px;
  border: 1px solid rgba(255, 255, 255, 0.92);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 24px 50px rgba(15, 23, 42, 0.1);
}

.login-page__submit.ant-btn {
  width: 100%;
  height: 46px;
  font-weight: 600;
  background: linear-gradient(135deg, #1d4ed8, #3730a3);
}
```

- [ ] **Step 4: Verify tests, lint, and build**

Run:

```bash
cd frontend && npm run test -- --run && npx eslint src/pages/Login.tsx src/pages/Login.css src/pages/Login.test.tsx && npm run build
```

Expected:
- tests PASS
- eslint PASS for the touched login files
- build PASS
