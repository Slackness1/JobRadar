import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import SiteDetailPanel from './SiteDetailPanel';
import type { SiteRow, SiteRun } from './types';

vi.mock('../../api', async () => {
  const actual = await vi.importActual<typeof import('../../api')>('../../api');
  return {
    ...actual,
    triggerSiteRecrawl: vi.fn(),
  };
});

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
