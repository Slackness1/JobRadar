import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vi } from 'vitest';

import Login from './Login';
import * as mockSession from '../auth/mockSession';

describe('Login', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('renders the login heading and core fields', () => {
    const { container } = render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    const tickerTrack = container.querySelector('.login-page__ticker-track');

    expect(tickerTrack).toHaveStyle({ animationDuration: '42s' });
    expect(tickerTrack).toHaveStyle({ animationPlayState: 'running' });

    expect(screen.getByRole('heading', { name: '登录 JobRadar' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '更快发现值得投递的岗位' })).toBeInTheDocument();
    expect(screen.getByText('重点岗位速览')).toBeInTheDocument();
    expect(screen.getAllByText('阿里巴巴 · 后端开发工程师 · 杭州').length).toBeGreaterThan(0);
    expect(screen.getAllByText('腾讯 · 产品经理 · 深圳').length).toBeGreaterThan(0);
    expect(screen.getAllByText('字节跳动 · 算法工程师 · 北京').length).toBeGreaterThan(0);
    expect(screen.getAllByText('中金公司 · 研究助理 · 上海').length).toBeGreaterThan(0);
    expect(screen.getAllByText('中信证券 · 投行项目助理 · 北京').length).toBeGreaterThan(0);
    expect(screen.getAllByText('中信建投 · 行业研究岗 · 上海').length).toBeGreaterThan(0);
    expect(screen.getAllByText('华泰证券 · 量化分析岗 · 上海').length).toBeGreaterThan(0);
    expect(screen.getAllByText('招商银行 · 数据分析岗 · 深圳').length).toBeGreaterThan(0);
    expect(screen.getAllByText('工商银行 · 金融科技岗 · 北京').length).toBeGreaterThan(0);
    expect(screen.getAllByText('建设银行 · 数据治理岗 · 北京').length).toBeGreaterThan(0);
    expect(screen.getAllByText('中国银行 · 风险管理岗 · 上海').length).toBeGreaterThan(0);
    expect(screen.getAllByText('农业银行 · 软件开发岗 · 杭州').length).toBeGreaterThan(0);
    expect(screen.getAllByText('国家电网 · 信息技术岗 · 南京').length).toBeGreaterThan(0);
    expect(screen.getAllByText('国家电投 · 数字化运营岗 · 北京').length).toBeGreaterThan(0);
    expect(screen.getByText('面向高校就业与职业发展场景，聚合互联网、券商、央国企、银行等重点平台岗位，强调覆盖、筛选与更新时效。')).toBeInTheDocument();
    expect(screen.getByText('重点公司持续覆盖，岗位入口统一归集')).toBeInTheDocument();
    expect(screen.getByText('春招开放信息与岗位动态快速更新')).toBeInTheDocument();
    expect(screen.getByText('更适合学校老师与学生一眼扫清核心信息')).toBeInTheDocument();
    expect(screen.getByText('0 家公司')).toBeInTheDocument();
    expect(screen.getByText('0 日更新')).toBeInTheDocument();
    expect(screen.getByText('登录后继续访问岗位总览、申请流程看板与配置中心。')).toBeInTheDocument();
    expect(screen.getByText('持续追踪岗位动态、目标公司与申请进展。')).toBeInTheDocument();
    expect(screen.getByText('让求职信息流保持更新与可执行。')).toBeInTheDocument();
    expect(screen.queryByText('Private Preview')).not.toBeInTheDocument();
    expect(screen.queryByText('当前为内测版本，仅限已开通账号的成员访问。')).not.toBeInTheDocument();
    expect(screen.queryByText('如需开通，请联系管理员。')).not.toBeInTheDocument();
    expect(screen.getByLabelText('账号')).toBeInTheDocument();
    expect(screen.getByLabelText('密码')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: '记住我' })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: '自动登录' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '登录' })).toBeInTheDocument();
  });

  it('pauses the ticker animation on hover and resumes on mouse leave', () => {
    const { container } = render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    const ticker = screen.getByLabelText('重点岗位速览');
    const tickerTrack = container.querySelector('.login-page__ticker-track');

    expect(tickerTrack).toHaveStyle({ animationPlayState: 'running' });

    fireEvent.mouseEnter(ticker);
    expect(tickerTrack).toHaveStyle({ animationPlayState: 'paused' });

    fireEvent.mouseLeave(ticker);
    expect(tickerTrack).toHaveStyle({ animationPlayState: 'running' });
  });

  it('animates company coverage to 3486 and keeps incrementing daily updates after reaching 1087', async () => {
    vi.useFakeTimers();

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2400);
    });

    expect(screen.getByText('3486 家公司')).toBeInTheDocument();
    expect(screen.getByText('1087 日更新')).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(screen.getByText('1088 日更新')).toBeInTheDocument();
  });

  it('shows required field messages when submitting empty credentials', async () => {
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

  it('submits boolean checkbox values and navigates to root on success', async () => {
    const user = userEvent.setup();
    const submitSpy = vi.spyOn(mockSession, 'submitPreviewLogin').mockResolvedValue(undefined);

    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<div>Jobs page stub</div>} />
        </Routes>
      </MemoryRouter>,
    );

    await user.type(screen.getByLabelText('账号'), 'preview-user');
    await user.type(screen.getByLabelText('密码'), 'preview-password');
    await user.click(screen.getByRole('checkbox', { name: '记住我' }));
    await user.click(screen.getByRole('checkbox', { name: '自动登录' }));
    await user.click(screen.getByRole('button', { name: '登录' }));

    await waitFor(() => {
      expect(submitSpy).toHaveBeenCalledWith({
        username: 'preview-user',
        password: 'preview-password',
        rememberMe: true,
        autoLogin: true,
      });
    });

    expect(await screen.findByText('Jobs page stub')).toBeInTheDocument();
  });

  it('shows an inline error when preview login rejects with invalid credentials', async () => {
    const user = userEvent.setup();
    vi.spyOn(mockSession, 'submitPreviewLogin').mockRejectedValue(new Error('INVALID_CREDENTIALS'));

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    await user.type(screen.getByLabelText('账号'), 'preview-user');
    await user.type(screen.getByLabelText('密码'), 'wrong-password');
    await user.click(screen.getByRole('button', { name: '登录' }));

    expect(await screen.findByText('账号或密码错误，请重试')).toBeInTheDocument();
  });

  it('shows a generic error when preview login fails unexpectedly', async () => {
    const user = userEvent.setup();
    vi.spyOn(mockSession, 'submitPreviewLogin').mockRejectedValue(new Error('NETWORK_ERROR'));

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    await user.type(screen.getByLabelText('账号'), 'preview-user');
    await user.type(screen.getByLabelText('密码'), 'preview-password');
    await user.click(screen.getByRole('button', { name: '登录' }));

    expect(await screen.findByText('登录失败，请稍后重试')).toBeInTheDocument();
    expect(screen.queryByText('账号或密码错误，请重试')).not.toBeInTheDocument();
  });
});
