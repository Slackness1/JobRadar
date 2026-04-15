# Login Page Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a polished internal-preview login page for JobRadar with account/password UI, mock session routing, and warm professional styling.

**Architecture:** Split the app into a public `/login` route and a gated app route, keep the login page self-contained, and use a tiny localStorage-backed mock session helper so the UI can support success/failure states before real auth exists. Add lightweight frontend test tooling first so the work can proceed with TDD instead of manual-only iteration.

**Tech Stack:** React 19, React Router 7, Ant Design 6, Vite 7, TypeScript, Vitest, React Testing Library

---

## Preflight

Use an isolated worktree before editing files.

```bash
git worktree add ~/.config/superpowers/worktrees/JobRadar/login-page-refresh -b feat/login-page-refresh
```

Work inside:

```bash
cd ~/.config/superpowers/worktrees/JobRadar/login-page-refresh
```

## File Structure

- Create: `frontend/src/AppRoutes.tsx`
  Routes the public login page and the authenticated app shell.
- Create: `frontend/src/AppLayout.tsx`
  Holds the current sider/header/main application layout so routing can split cleanly.
- Create: `frontend/src/auth/mockSession.ts`
  Stores and reads UI-only preview session state from `localStorage`.
- Create: `frontend/src/pages/Login.tsx`
  Owns the login page layout, form state, validation, loading, and inline error rendering.
- Create: `frontend/src/pages/Login.css`
  Holds page-specific warm split-layout styles.
- Create: `frontend/src/pages/Login.test.tsx`
  Covers login page content, validation, checkbox behavior, submit, and error state.
- Create: `frontend/src/AppRoutes.test.tsx`
  Covers redirect-to-login and authenticated route behavior.
- Create: `frontend/src/test/setup.ts`
  Loads `@testing-library/jest-dom` and cleanup hooks.
- Modify: `frontend/src/App.tsx`
  Reduce this file to the browser-router shell that renders `AppRoutes`.
- Modify: `frontend/package.json`
  Add test scripts and test dependencies.
- Modify: `frontend/vite.config.ts`
  Add Vitest config using `jsdom`.
- Modify: `frontend/tsconfig.app.json`
  Add test types for Vitest.
- Modify: `AGENTS.md`
  Document the new verified frontend test command.

## Task 1: Add Frontend Test Harness And Login Skeleton

**Files:**
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/src/pages/Login.test.tsx`
- Create: `frontend/src/pages/Login.tsx`
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/tsconfig.app.json`
- Modify: `AGENTS.md`

- [ ] **Step 1: Add test tooling and setup file**

Update `frontend/package.json` to add scripts and dependencies:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.9.1",
    "@testing-library/react": "^16.3.0",
    "@testing-library/user-event": "^14.6.1",
    "jsdom": "^27.0.1",
    "vitest": "^3.2.4"
  }
}
```

Update `frontend/vite.config.ts`:

```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: false,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    globals: true,
  },
});
```

Update `frontend/tsconfig.app.json`:

```json
{
  "compilerOptions": {
    "types": ["vite/client", "vitest/globals"]
  }
}
```

Create `frontend/src/test/setup.ts`:

```ts
import '@testing-library/jest-dom';
```

Update `AGENTS.md` frontend tests section to include:

```md
### Frontend Tests
- 单测：`cd frontend && npm run test -- --run`
- 单文件：`cd frontend && npm run test -- --run src/pages/Login.test.tsx`
```

- [ ] **Step 2: Write the first failing login-page render test**

Create `frontend/src/pages/Login.test.tsx`:

```tsx
import { MemoryRouter } from 'react-router-dom';
import { render, screen } from '@testing-library/react';

import Login from './Login';

describe('Login', () => {
  it('renders the login heading and core fields', () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: '登录 JobRadar' })).toBeInTheDocument();
    expect(screen.getByLabelText('账号')).toBeInTheDocument();
    expect(screen.getByLabelText('密码')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '登录' })).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run:

```bash
cd frontend && npm install && npm run test -- --run src/pages/Login.test.tsx
```

Expected: FAIL because `./Login` does not exist yet.

- [ ] **Step 4: Implement the minimal `Login` page skeleton**

Create `frontend/src/pages/Login.tsx`:

```tsx
import { Button, Checkbox, Form, Input, Typography } from 'antd';

const { Title, Paragraph } = Typography;

export default function Login() {
  return (
    <div>
      <Title level={2}>登录 JobRadar</Title>
      <Paragraph>使用内测账号继续访问岗位总览、申请流程看板与配置中心。</Paragraph>
      <Form layout="vertical">
        <Form.Item label="账号" name="username">
          <Input />
        </Form.Item>
        <Form.Item label="密码" name="password">
          <Input.Password />
        </Form.Item>
        <div>
          <Checkbox>记住我</Checkbox>
          <Checkbox>自动登录</Checkbox>
        </div>
        <Button type="primary" htmlType="submit">登录</Button>
      </Form>
    </div>
  );
}
```

- [ ] **Step 5: Re-run the test and commit the harness**

Run:

```bash
cd frontend && npm run test -- --run src/pages/Login.test.tsx
```

Expected: PASS.

Commit:

```bash
git add AGENTS.md frontend/package.json frontend/vite.config.ts frontend/tsconfig.app.json frontend/src/test/setup.ts frontend/src/pages/Login.tsx frontend/src/pages/Login.test.tsx package-lock.json
git commit -m "test(frontend): add login page test harness"
```

## Task 2: Add Mock Session Storage And Route Split

**Files:**
- Create: `frontend/src/AppRoutes.tsx`
- Create: `frontend/src/AppLayout.tsx`
- Create: `frontend/src/AppRoutes.test.tsx`
- Create: `frontend/src/auth/mockSession.ts`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write failing route tests for public and gated paths**

Create `frontend/src/AppRoutes.test.tsx`:

```tsx
import { MemoryRouter } from 'react-router-dom';
import { render, screen } from '@testing-library/react';

import AppRoutes from './AppRoutes';

describe('AppRoutes', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('redirects anonymous users from root to login', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: '登录 JobRadar' })).toBeInTheDocument();
  });

  it('shows the app shell when a preview session exists', () => {
    window.localStorage.setItem('jobradar_mock_session', JSON.stringify({
      username: 'tester',
      rememberMe: true,
      autoLogin: false,
    }));

    render(
      <MemoryRouter initialEntries={['/']}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(screen.getByText('岗位总览')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the route tests to verify they fail**

Run:

```bash
cd frontend && npm run test -- --run src/AppRoutes.test.tsx
```

Expected: FAIL because `AppRoutes` and mock session helpers do not exist yet.

- [ ] **Step 3: Implement mock session helper and route split**

Create `frontend/src/auth/mockSession.ts`:

```ts
export interface MockSession {
  username: string;
  rememberMe: boolean;
  autoLogin: boolean;
}

const STORAGE_KEY = 'jobradar_mock_session';

export function readMockSession(): MockSession | null {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw) as MockSession;
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function writeMockSession(session: MockSession) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearMockSession() {
  window.localStorage.removeItem(STORAGE_KEY);
}
```

Create `frontend/src/AppRoutes.tsx`:

```tsx
import { Navigate, Route, Routes } from 'react-router-dom';

import AppLayout from './AppLayout';
import Login from './pages/Login';
import { readMockSession } from './auth/mockSession';

function RequirePreviewSession({ children }: { children: JSX.Element }) {
  return readMockSession() ? children : <Navigate to="/login" replace />;
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="*" element={<RequirePreviewSession><AppLayout /></RequirePreviewSession>} />
    </Routes>
  );
}
```

Create `frontend/src/AppLayout.tsx` by moving the current routed layout out of `App.tsx`:

```tsx
import { useState } from 'react';
import { Link, Route, Routes, useLocation } from 'react-router-dom';
import { Layout, Menu, theme } from 'antd';
import {
  UnorderedListOutlined,
  SettingOutlined,
  StopOutlined,
  BarChartOutlined,
  BugOutlined,
  ClockCircleOutlined,
  TeamOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';

import Jobs from './pages/Jobs';
import JobIntel from './pages/JobIntel';
import Tracks from './pages/Tracks';
import Scoring from './pages/Scoring';
import Exclude from './pages/Exclude';
import Crawl from './pages/Crawl';
import Scheduler from './pages/Scheduler';
import CompanyExpand from './pages/CompanyExpand';

const { Sider, Content, Header } = Layout;

const menuItems = [
  { key: '/', icon: <UnorderedListOutlined />, label: <Link to="/">岗位总览</Link> },
  { key: '/applied-flow', icon: <CheckCircleOutlined />, label: <Link to="/applied-flow">申请流程看板</Link> },
  { key: '/company-expand', icon: <TeamOutlined />, label: <Link to="/company-expand">公司展开</Link> },
  { key: '/tracks', icon: <SettingOutlined />, label: <Link to="/tracks">赛道配置</Link> },
  { key: '/exclude', icon: <StopOutlined />, label: <Link to="/exclude">排除规则</Link> },
  { key: '/scoring', icon: <BarChartOutlined />, label: <Link to="/scoring">评分设置</Link> },
  { key: '/crawl', icon: <BugOutlined />, label: <Link to="/crawl">爬取管理</Link> },
  { key: '/scheduler', icon: <ClockCircleOutlined />, label: <Link to="/scheduler">定时任务</Link> },
];

const PAGE_TITLES: Record<string, string> = {
  '/': '岗位总览',
  '/applied-flow': '申请流程看板',
  '/company-expand': '公司展开',
  '/tracks': '赛道配置',
  '/exclude': '排除规则',
  '/scoring': '评分设置',
  '/crawl': '爬取管理',
  '/scheduler': '定时任务',
};

export default function AppLayout() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const { token: { colorBgContainer, borderRadiusLG } } = theme.useToken();

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed} style={{ overflow: 'auto', height: '100vh', position: 'sticky', top: 0, left: 0 }}>
        <div style={{ color: '#fff', textAlign: 'center', padding: '16px 0', fontSize: collapsed ? 16 : 20, fontWeight: 'bold', letterSpacing: 1, borderBottom: '1px solid rgba(255,255,255,0.1)', marginBottom: 8 }}>
          {collapsed ? 'JR' : 'JobRadar'}
        </div>
        <Menu theme="dark" selectedKeys={[location.pathname]} items={menuItems} mode="inline" />
      </Sider>
      <Layout>
        <Header style={{ background: colorBgContainer, padding: '0 24px', fontSize: 18, fontWeight: 600, borderBottom: '1px solid #f0f0f0', display: 'flex', alignItems: 'center' }}>
          {PAGE_TITLES[location.pathname] || 'JobRadar'}
        </Header>
        <Content style={{ margin: 16, padding: 20, background: colorBgContainer, borderRadius: borderRadiusLG, minHeight: 280 }}>
          <Routes>
            <Route path="/" element={<Jobs />} />
            <Route path="/applied-flow" element={<Jobs />} />
            <Route path="/company-expand" element={<CompanyExpand />} />
            <Route path="/job-intel/:jobId" element={<JobIntel />} />
            <Route path="/tracks" element={<Tracks />} />
            <Route path="/scoring" element={<Scoring />} />
            <Route path="/exclude" element={<Exclude />} />
            <Route path="/crawl" element={<Crawl />} />
            <Route path="/scheduler" element={<Scheduler />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}
```

Refactor `frontend/src/App.tsx` so it becomes the router shell only:

```tsx
import { BrowserRouter } from 'react-router-dom';

import AppRoutes from './AppRoutes';

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
```

- [ ] **Step 4: Re-run the tests to verify the route gate passes**

Run:

```bash
cd frontend && npm run test -- --run src/AppRoutes.test.tsx src/pages/Login.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit the route split**

```bash
git add frontend/src/App.tsx frontend/src/AppRoutes.tsx frontend/src/AppRoutes.test.tsx frontend/src/auth/mockSession.ts
git commit -m "feat(frontend): add preview login route gate"
```

## Task 3: Implement Form State, Validation, Loading, And Inline Error Handling

**Files:**
- Modify: `frontend/src/pages/Login.tsx`
- Modify: `frontend/src/pages/Login.test.tsx`
- Modify: `frontend/src/auth/mockSession.ts`

- [ ] **Step 1: Write failing behavior tests for validation, checkbox state, success, and failure**

Expand `frontend/src/pages/Login.test.tsx`:

```tsx
import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vi } from 'vitest';

import Login from './Login';
import * as mockSession from '../auth/mockSession';

it('validates required fields before submit', async () => {
  const user = userEvent.setup();

  render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>,
  );

  await user.click(screen.getByRole('button', { name: '登录' }));

  expect(await screen.findByText('请输入账号')).toBeInTheDocument();
  expect(await screen.findByText('请输入密码')).toBeInTheDocument();
});

it('submits checkbox state and navigates on success', async () => {
  const user = userEvent.setup();
  const submitSpy = vi.spyOn(mockSession, 'submitPreviewLogin').mockResolvedValueOnce();

  render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<div>home</div>} />
      </Routes>
    </MemoryRouter>,
  );

  await user.type(screen.getByLabelText('账号'), 'tester');
  await user.type(screen.getByLabelText('密码'), 'secret');
  await user.click(screen.getByRole('checkbox', { name: '记住我' }));
  await user.click(screen.getByRole('checkbox', { name: '自动登录' }));
  await user.click(screen.getByRole('button', { name: '登录' }));

  await waitFor(() => {
    expect(submitSpy).toHaveBeenCalledWith({
      username: 'tester',
      password: 'secret',
      rememberMe: true,
      autoLogin: true,
    });
  });

  expect(await screen.findByText('home')).toBeInTheDocument();
});

it('shows inline error text when submit fails', async () => {
  const user = userEvent.setup();
  vi.spyOn(mockSession, 'submitPreviewLogin').mockRejectedValueOnce(new Error('INVALID_CREDENTIALS'));

  render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>,
  );

  await user.type(screen.getByLabelText('账号'), 'tester');
  await user.type(screen.getByLabelText('密码'), 'bad');
  await user.click(screen.getByRole('button', { name: '登录' }));

  expect(await screen.findByText('账号或密码错误，请重试')).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the page tests to verify they fail**

Run:

```bash
cd frontend && npm run test -- --run src/pages/Login.test.tsx
```

Expected: FAIL because `submitPreviewLogin`, validation, navigation, and inline error handling do not exist yet.

- [ ] **Step 3: Implement the minimal behavior in `mockSession.ts` and `Login.tsx`**

Extend `frontend/src/auth/mockSession.ts`:

```ts
export interface PreviewLoginInput {
  username: string;
  password: string;
  rememberMe: boolean;
  autoLogin: boolean;
}

export async function submitPreviewLogin(input: PreviewLoginInput) {
  await new Promise(resolve => window.setTimeout(resolve, 400));
  writeMockSession({
    username: input.username,
    rememberMe: input.rememberMe,
    autoLogin: input.autoLogin,
  });
}
```

Update `frontend/src/pages/Login.tsx`:

```tsx
import { Alert, Button, Checkbox, Form, Input, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';

import { submitPreviewLogin } from '../auth/mockSession';

interface LoginFormValues {
  username: string;
  password: string;
  rememberMe?: boolean;
  autoLogin?: boolean;
}

export default function Login() {
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleFinish = async (values: LoginFormValues) => {
    setSubmitting(true);
    setSubmitError(null);

    try {
      await submitPreviewLogin({
        username: values.username,
        password: values.password,
        rememberMe: Boolean(values.rememberMe),
        autoLogin: Boolean(values.autoLogin),
      });
      navigate('/');
    } catch {
      setSubmitError('账号或密码错误，请重试');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Form layout="vertical" onFinish={handleFinish} initialValues={{ rememberMe: false, autoLogin: false }}>
      {submitError ? <Alert type="error" message={submitError} showIcon /> : null}
      <Form.Item label="账号" name="username" rules={[{ required: true, message: '请输入账号' }]}>
        <Input autoComplete="username" />
      </Form.Item>
      <Form.Item label="密码" name="password" rules={[{ required: true, message: '请输入密码' }]}>
        <Input.Password autoComplete="current-password" />
      </Form.Item>
      <div className="login-page__checkboxRow">
        <Form.Item name="rememberMe" valuePropName="checked" noStyle>
          <Checkbox>记住我</Checkbox>
        </Form.Item>
        <Form.Item name="autoLogin" valuePropName="checked" noStyle>
          <Checkbox>自动登录</Checkbox>
        </Form.Item>
      </div>
      <Button type="primary" htmlType="submit" loading={submitting}>
        {submitting ? '登录中...' : '登录'}
      </Button>
    </Form>
  );
}
```

- [ ] **Step 4: Re-run the behavior tests and lint**

Run:

```bash
cd frontend && npm run test -- --run src/pages/Login.test.tsx src/AppRoutes.test.tsx && npm run lint
```

Expected: PASS.

- [ ] **Step 5: Commit the form behavior**

```bash
git add frontend/src/pages/Login.tsx frontend/src/pages/Login.test.tsx frontend/src/auth/mockSession.ts
git commit -m "feat(frontend): add preview login form behavior"
```

## Task 4: Apply The Approved Warm Split Layout And Final Verification

**Files:**
- Create: `frontend/src/pages/Login.css`
- Modify: `frontend/src/pages/Login.tsx`
- Modify: `frontend/src/pages/Login.test.tsx`

- [ ] **Step 1: Write failing content tests for the approved messaging and page structure**

Add these assertions to `frontend/src/pages/Login.test.tsx`:

```tsx
it('renders the approved product-value content', () => {
  render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>,
  );

  expect(screen.getByText('Private Preview')).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: '更快发现值得投递的岗位' })).toBeInTheDocument();
  expect(screen.getByText('聚合、筛选、评分与跟踪，集中管理你的求职信息流。')).toBeInTheDocument();
  expect(screen.getByText('多来源岗位聚合，减少重复搜岗')).toBeInTheDocument();
  expect(screen.getByText('统一筛选与评分，快速定位优先机会')).toBeInTheDocument();
  expect(screen.getByText('申请流程可追踪，避免信息散落')).toBeInTheDocument();
  expect(screen.getByText('74k+ 岗位数据池')).toBeInTheDocument();
  expect(screen.getByText('55k+ TATA 覆盖')).toBeInTheDocument();
  expect(screen.getByText('当前为内测版本，仅限已开通账号的成员访问。')).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd frontend && npm run test -- --run src/pages/Login.test.tsx
```

Expected: FAIL because the skeleton page does not yet render the approved left-side structure or final copy.

- [ ] **Step 3: Implement the final split layout and CSS**

Create `frontend/src/pages/Login.css`:

```css
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  background: linear-gradient(135deg, #fffaf1 0%, #fff2d8 48%, #fff7ef 100%);
}

.login-page__hero {
  padding: 56px 64px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 18px;
}

.login-page__badge {
  width: fit-content;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  color: #b45309;
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.login-page__cardWrap {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}

.login-page__card {
  width: 100%;
  max-width: 360px;
  border-radius: 22px;
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.12);
}

.login-page__checkboxRow {
  display: flex;
  gap: 16px;
}

@media (max-width: 900px) {
  .login-page {
    grid-template-columns: 1fr;
  }

  .login-page__hero {
    padding: 32px 20px 12px;
  }

  .login-page__checkboxRow {
    flex-direction: column;
    gap: 8px;
  }
}
```

Update `frontend/src/pages/Login.tsx` to use the approved content and class structure:

```tsx
import './Login.css';

<div className="login-page">
  <section className="login-page__hero">
    <div className="login-page__badge">Private Preview</div>
    <h1>更快发现值得投递的岗位</h1>
    <p>聚合、筛选、评分与跟踪，集中管理你的求职信息流。</p>
    <ul>
      <li>多来源岗位聚合，减少重复搜岗</li>
      <li>统一筛选与评分，快速定位优先机会</li>
      <li>申请流程可追踪，避免信息散落</li>
    </ul>
    <div>
      <div>74k+ 岗位数据池</div>
      <div>55k+ TATA 覆盖</div>
    </div>
  </section>

  <section className="login-page__cardWrap">
    <Card className="login-page__card">
      <Title level={2}>登录 JobRadar</Title>
      <Paragraph>使用内测账号继续访问岗位总览、申请流程看板与配置中心。</Paragraph>
      <div className="login-page__checkboxRow">
        <Form.Item name="rememberMe" valuePropName="checked" noStyle>
          <Checkbox>记住我</Checkbox>
        </Form.Item>
        <Form.Item name="autoLogin" valuePropName="checked" noStyle>
          <Checkbox>自动登录</Checkbox>
        </Form.Item>
      </div>
      <Button type="primary" htmlType="submit" size="large" style={{ background: '#2563eb' }}>
        登录
      </Button>
      <div className="login-page__footerNote">当前为内测版本，仅限已开通账号的成员访问。</div>
      <div className="login-page__footerHelp">如需开通，请联系管理员。</div>
    </Card>
  </section>
</div>
```

- [ ] **Step 4: Run the full verification suite**

Run:

```bash
cd frontend && npm run test -- --run && npm run lint && npm run build
```

Expected: all commands PASS.

Also run a quick manual browser check:

```bash
cd frontend && npm run dev
```

Verify manually:

- `/login` shows the warm split layout
- empty submit shows required-field messages
- toggling `记住我` and `自动登录` works
- successful submit routes into the main app
- mobile responsive mode stacks the layout cleanly

- [ ] **Step 5: Commit the final UI**

```bash
git add frontend/src/pages/Login.tsx frontend/src/pages/Login.css frontend/src/pages/Login.test.tsx frontend/src/App.tsx frontend/src/AppRoutes.tsx frontend/src/AppRoutes.test.tsx frontend/src/auth/mockSession.ts
git commit -m "feat(frontend): redesign login page for internal preview"
```
