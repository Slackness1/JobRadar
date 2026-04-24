import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import Jobs from './Jobs';
import * as api from '../api';

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof import('../api')>('../api');
  return {
    ...actual,
    getJobs: vi.fn(),
    getJobsByCompany: vi.fn(),
    getJobStats: vi.fn(),
    getTracks: vi.fn(),
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

describe('Jobs', () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();

    vi.mocked(api.getJobs).mockResolvedValue(mockResponse({ items: [], total: 0 }));
    vi.mocked(api.getJobsByCompany).mockResolvedValue(mockResponse({ items: [], total: 0 }));
    vi.mocked(api.getJobStats).mockResolvedValue(mockResponse({ total_jobs: 0, today_new: 0, by_track: {}, by_stage: {} }));
    vi.mocked(api.getTracks).mockResolvedValue(mockResponse([]));
  });

  it('requests all jobs by default on first render', async () => {
    render(
      <MemoryRouter>
        <Jobs />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(api.getJobs).toHaveBeenCalled();
    });

    expect(api.getJobs).toHaveBeenCalledWith(
      expect.objectContaining({
        job_stage: 'all',
      }),
    );
  });

  it('uses job title search params when persisted search mode is 岗位', async () => {
    window.localStorage.setItem('jobradar.lastFilterState.v3', JSON.stringify({
      search: '抖音',
      searchMode: 'job',
    }));

    render(
      <MemoryRouter>
        <Jobs />
      </MemoryRouter>,
    );

    await waitFor(() => {
      const calls = vi.mocked(api.getJobs).mock.calls;
      expect(calls.at(-1)?.[0]).toEqual(expect.objectContaining({
        job_title_search: '抖音',
      }));
    });

    const latestParams = vi.mocked(api.getJobs).mock.calls.at(-1)?.[0] as Record<string, unknown>;
    expect(latestParams.company_search).toBeUndefined();
  });

  it('uses company search params when persisted search mode is 公司', async () => {
    window.localStorage.setItem('jobradar.lastFilterState.v3', JSON.stringify({
      search: '字节',
      searchMode: 'company',
    }));

    render(
      <MemoryRouter>
        <Jobs />
      </MemoryRouter>,
    );

    await waitFor(() => {
      const calls = vi.mocked(api.getJobs).mock.calls;
      expect(calls.at(-1)?.[0]).toEqual(expect.objectContaining({
        company_search: '字节',
      }));
    });

    const latestParams = vi.mocked(api.getJobs).mock.calls.at(-1)?.[0] as Record<string, unknown>;
    expect(latestParams.job_title_search).toBeUndefined();
  });
});
