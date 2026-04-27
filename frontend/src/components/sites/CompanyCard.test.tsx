import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import CompanyCard from './CompanyCard';
import type { SiteRow } from './types';

function mkRow(overrides: Partial<SiteRow>): SiteRow {
  return {
    company: '腾讯',
    source: 'internet_official',
    last_run_at: '2026-04-27T03:00:00',
    last_status: 'success',
    today_new: 12,
    last_error_short: '',
    alert_level: 'green',
    ...overrides,
  };
}

describe('CompanyCard', () => {
  it('renders company name and today_new delta', () => {
    render(<CompanyCard row={mkRow({ today_new: 12 })} selected={false} onClick={() => {}} />);
    expect(screen.getByText('腾讯')).toBeInTheDocument();
    expect(screen.getByText('+12')).toBeInTheDocument();
  });

  it('shows · when today_new is 0', () => {
    render(<CompanyCard row={mkRow({ today_new: 0 })} selected={false} onClick={() => {}} />);
    expect(screen.getByText('·')).toBeInTheDocument();
  });

  it('applies status color class', () => {
    const { container } = render(<CompanyCard row={mkRow({ alert_level: 'red' })} selected={false} onClick={() => {}} />);
    const dot = container.querySelector('.sites-dot');
    expect(dot?.classList.contains('red')).toBe(true);
  });

  it('applies selected class when selected', () => {
    const { container } = render(<CompanyCard row={mkRow({})} selected onClick={() => {}} />);
    expect(container.querySelector('.sites-company-card.selected')).toBeTruthy();
  });

  it('fires onClick with the company name', () => {
    const onClick = vi.fn();
    render(<CompanyCard row={mkRow({ company: '阿里巴巴' })} selected={false} onClick={onClick} />);
    fireEvent.click(screen.getByText('阿里巴巴'));
    expect(onClick).toHaveBeenCalledWith('阿里巴巴');
  });
});
