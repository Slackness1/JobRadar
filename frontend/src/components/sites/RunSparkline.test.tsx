import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import RunSparkline from './RunSparkline';
import type { SiteRun } from './types';

function mkRun(overrides: Partial<SiteRun>): SiteRun {
  return {
    id: 1,
    source: 'internet_official',
    started_at: '2026-04-27T08:00:00',
    finished_at: '2026-04-27T08:01:00',
    status: 'success',
    fetched_count: 10,
    new_count: 2,
    error_message: '',
    duration_ms: 60000,
    suggested_fix: '',
    ...overrides,
  };
}

describe('RunSparkline', () => {
  it('renders one bar per run', () => {
    const runs: SiteRun[] = [mkRun({ id: 1 }), mkRun({ id: 2 }), mkRun({ id: 3 })];
    const { container } = render(<RunSparkline runs={runs} />);
    expect(container.querySelectorAll('.sites-sparkline__bar').length).toBe(3);
  });

  it('marks failed runs with the failed class', () => {
    const runs: SiteRun[] = [
      mkRun({ id: 1, status: 'failed', fetched_count: 0 }),
      mkRun({ id: 2, status: 'success', fetched_count: 10 }),
    ];
    const { container } = render(<RunSparkline runs={runs} />);
    const bars = container.querySelectorAll('.sites-sparkline__bar');
    expect(bars[0].classList.contains('failed')).toBe(true);
    expect(bars[1].classList.contains('failed')).toBe(false);
  });

  it('shows a caption with failure count', () => {
    const runs: SiteRun[] = [
      mkRun({ id: 1, status: 'failed' }),
      mkRun({ id: 2, status: 'failed' }),
      mkRun({ id: 3, status: 'success' }),
    ];
    render(<RunSparkline runs={runs} />);
    expect(screen.getByText(/最近 3 次 run · 2 失败/)).toBeInTheDocument();
  });

  it('renders nothing meaningful when runs is empty', () => {
    render(<RunSparkline runs={[]} />);
    expect(screen.getByText(/暂无 run 数据/)).toBeInTheDocument();
  });
});
