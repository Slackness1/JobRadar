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
    fetchSitesDigest: vi.fn(),
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
  suggested_fix: '',
};

describe('Sites page', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    vi.clearAllMocks();
    vi.mocked(api.fetchSitesSummary).mockResolvedValue(mockResponse(baseSummary));
    vi.mocked(api.fetchSites).mockResolvedValue(mockResponse([tencentRow, aliRow, cicc]));
    vi.mocked(api.fetchSiteRuns).mockResolvedValue(mockResponse([baseRun]));
    vi.mocked(api.triggerSiteRecrawl).mockResolvedValue(mockResponse({ parent_log_id: 99, message: '已启动' }));
    vi.mocked(api.fetchSitesDigest).mockResolvedValue(mockResponse({ text: '', generated_at: null }));
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
