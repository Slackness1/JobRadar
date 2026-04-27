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

  it('renders 4-cell stat strip with today_new, fetched, avg duration, success rate', () => {
    const { container } = render(
      <SiteDetailPanel row={baseRow} runs={[baseRun]} inFlight={false} onRecrawlSubmit={() => {}} />,
    );
    const strip = container.querySelector('.sites-stat-strip');
    expect(strip).toBeTruthy();
    const cells = container.querySelectorAll('.sites-stat-strip__cell');
    expect(cells.length).toBe(4);

    // Read nums directly from stat strip cells to avoid ambiguity with runs table
    const nums = Array.from(container.querySelectorAll('.sites-stat-strip__num')).map((n) => n.textContent);
    // today_new = 12
    expect(nums).toContain('12');
    // 24h fetched = 38 (sum of fetched_count)
    expect(nums).toContain('38');
    // avg duration = 1m 0s (60000ms)
    expect(nums).toContain('1m 0s');
    // success rate = 100%
    expect(nums).toContain('100%');

    // Labels
    const labels = Array.from(container.querySelectorAll('.sites-stat-strip__label')).map((n) => n.textContent);
    expect(labels).toContain('今日新增');
    expect(labels).toContain('24h 抓取');
    expect(labels).toContain('平均耗时');
    expect(labels).toContain('成功率');
  });

  it('stat strip shows — for duration and success rate when no runs', () => {
    render(<SiteDetailPanel row={baseRow} runs={[]} inFlight={false} onRecrawlSubmit={() => {}} />);
    const nums = document.querySelectorAll('.sites-stat-strip__num');
    // today_new = 12, fetched = 0, duration = —, success rate = —
    const texts = Array.from(nums).map((n) => n.textContent);
    expect(texts).toContain('—');
  });

  it('renders compact recent-runs table with up to 5 rows', () => {
    const runs: SiteRun[] = Array.from({ length: 7 }, (_, i) => ({
      ...baseRun,
      id: i + 1,
      started_at: `2026-04-27T0${i}:00:00`,
      fetched_count: 10 + i,
      new_count: i,
      duration_ms: 5000 + i * 1000,
    }));
    const { container } = render(
      <SiteDetailPanel row={baseRow} runs={runs} inFlight={false} onRecrawlSubmit={() => {}} />,
    );
    const table = container.querySelector('.sites-recent-runs');
    expect(table).toBeTruthy();
    // Only first 5 rows rendered
    const bodyRows = table!.querySelectorAll('tbody tr');
    expect(bodyRows.length).toBe(5);
  });

  it('does not render recent-runs table when runs is empty', () => {
    const { container } = render(
      <SiteDetailPanel row={baseRow} runs={[]} inFlight={false} onRecrawlSubmit={() => {}} />,
    );
    expect(container.querySelector('.sites-recent-runs')).toBeNull();
  });

  it('recent-runs table shows 成功/失败 status labels', () => {
    const runs: SiteRun[] = [
      { ...baseRun, id: 1, status: 'success' },
      { ...baseRun, id: 2, status: 'failed' },
    ];
    render(<SiteDetailPanel row={baseRow} runs={runs} inFlight={false} onRecrawlSubmit={() => {}} />);
    expect(screen.getByText('成功')).toBeInTheDocument();
    expect(screen.getByText('失败')).toBeInTheDocument();
  });
});
