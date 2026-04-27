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
