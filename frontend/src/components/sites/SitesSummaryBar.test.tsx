import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import SitesSummaryBar from './SitesSummaryBar';
import type { SiteRow, SitesSummary } from './types';

const baseSummary: SitesSummary = {
  active: 38,
  alerted: 0,
  disabled: 0,
  total_today_new: 142,
  last_batch_at: '2026-04-27T01:00:00',
  last_batch_status: 'success',
};

const baseRow: SiteRow = {
  company: '',
  source: 'internet_official',
  last_run_at: null,
  last_status: 'success',
  today_new: 0,
  last_error_short: '',
  alert_level: 'green',
};

describe('SitesSummaryBar', () => {
  it('renders the three KPI counters and total_today_new', () => {
    render(<SitesSummaryBar summary={baseSummary} rows={[]} onJumpToCompany={() => {}} />);
    expect(screen.getByText(/运行中/)).toBeInTheDocument();
    expect(screen.getByText('38')).toBeInTheDocument();
    expect(screen.getByText(/今日新增/)).toBeInTheDocument();
    expect(screen.getByText('142')).toBeInTheDocument();
  });

  it('does not render the alert banner when alerted < 2', () => {
    const summary = { ...baseSummary, alerted: 1 };
    const { container } = render(<SitesSummaryBar summary={summary} rows={[]} onJumpToCompany={() => {}} />);
    expect(container.querySelector('.sites-alert-banner')).toBeNull();
  });

  it('does not render the alert banner when no row is red', () => {
    const summary = { ...baseSummary, alerted: 3 };
    const rows: SiteRow[] = [
      { ...baseRow, company: 'a', alert_level: 'yellow' },
      { ...baseRow, company: 'b', alert_level: 'yellow' },
      { ...baseRow, company: 'c', alert_level: 'yellow' },
    ];
    const { container } = render(<SitesSummaryBar summary={summary} rows={rows} onJumpToCompany={() => {}} />);
    expect(container.querySelector('.sites-alert-banner')).toBeNull();
  });

  it('renders the alert banner when alerted >= 2 and at least one row is red', () => {
    const summary = { ...baseSummary, alerted: 2 };
    const rows: SiteRow[] = [
      { ...baseRow, company: '腾讯', alert_level: 'red' },
      { ...baseRow, company: '中金公司', alert_level: 'yellow' },
    ];
    render(<SitesSummaryBar summary={summary} rows={rows} onJumpToCompany={() => {}} />);
    expect(screen.getByText(/今日 2 家爬虫疑似失效/)).toBeInTheDocument();
    expect(screen.getByText(/腾讯/)).toBeInTheDocument();
  });

  it('clicking the alert banner jumps to the first red company', () => {
    const summary = { ...baseSummary, alerted: 2 };
    const rows: SiteRow[] = [
      { ...baseRow, company: '中金公司', alert_level: 'yellow' },
      { ...baseRow, company: '腾讯', alert_level: 'red' },
      { ...baseRow, company: '阿里巴巴', alert_level: 'red' },
    ];
    const onJump = vi.fn();
    const { container } = render(<SitesSummaryBar summary={summary} rows={rows} onJumpToCompany={onJump} />);
    const banner = container.querySelector('.sites-alert-banner') as HTMLElement;
    expect(banner).toBeTruthy();
    fireEvent.click(banner);
    expect(onJump).toHaveBeenCalledWith('腾讯');
  });
});
