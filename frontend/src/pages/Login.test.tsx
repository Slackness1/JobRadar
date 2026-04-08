import { act, render, screen, waitFor } from '@testing-library/react';
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
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: '登录 JobRadar' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '更快发现值得投递的岗位' })).toBeInTheDocument();
    expect(screen.getByText('聚合、筛选、评分与跟踪，集中管理你的求职信息流。')).toBeInTheDocument();
    expect(screen.getByText('多来源岗位聚合，减少重复搜岗')).toBeInTheDocument();
    expect(screen.getByText('统一筛选与评分，快速定位优先机会')).toBeInTheDocument();
    expect(screen.getByText('申请流程可追踪，避免信息散落')).toBeInTheDocument();
    expect(screen.getByText('0 家公司')).toBeInTheDocument();
    expect(screen.getByText('0 更新')).toBeInTheDocument();
    expect(screen.getByText('登录后继续访问岗位总览、申请流程看板与配置中心。')).toBeInTheDocument();
    expect(screen.queryByText('Private Preview')).not.toBeInTheDocument();
    expect(screen.queryByText('当前为内测版本，仅限已开通账号的成员访问。')).not.toBeInTheDocument();
    expect(screen.queryByText('如需开通，请联系管理员。')).not.toBeInTheDocument();
    expect(screen.getByLabelText('账号')).toBeInTheDocument();
    expect(screen.getByLabelText('密码')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: '记住我' })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: '自动登录' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '登录' })).toBeInTheDocument();
  });

  it('animates company coverage to 3486 and keeps incrementing updates after reaching 1087', async () => {
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
    expect(screen.getByText('1087 更新')).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(screen.getByText('1088 更新')).toBeInTheDocument();
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
