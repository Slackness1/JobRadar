import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';

vi.mock('./pages/Jobs', () => ({
  default: () => <div>Jobs page stub</div>,
}));

import AppRoutes from './AppRoutes';
import { writeMockSession } from './auth/mockSession';

describe('AppRoutes', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it('shows the login page for anonymous users visiting root', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: '登录 JobRadar' })).toBeInTheDocument();
  });

  it('shows the app shell when a preview session is saved', async () => {
    writeMockSession({
      username: 'preview-user',
      rememberMe: true,
      autoLogin: false,
    });

    render(
      <MemoryRouter initialEntries={['/']}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect((await screen.findAllByText('岗位总览')).length).toBeGreaterThan(0);
  });

  it('shows the app shell when a non-remembered preview session is saved in sessionStorage', async () => {
    window.sessionStorage.setItem('jobradar_mock_session', JSON.stringify({
      username: 'preview-user',
      rememberMe: false,
      autoLogin: false,
    }));

    render(
      <MemoryRouter initialEntries={['/']}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect((await screen.findAllByText('岗位总览')).length).toBeGreaterThan(0);
  });

  it('redirects authenticated users away from /login to the app shell', async () => {
    writeMockSession({
      username: 'preview-user',
      rememberMe: true,
      autoLogin: false,
    });

    render(
      <MemoryRouter initialEntries={['/login']}>
        <AppRoutes />
      </MemoryRouter>,
    );

    expect((await screen.findAllByText('岗位总览')).length).toBeGreaterThan(0);
    expect(screen.queryByRole('heading', { name: '登录 JobRadar' })).not.toBeInTheDocument();
  });
});
