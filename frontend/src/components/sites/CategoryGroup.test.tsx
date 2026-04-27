import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import CategoryGroup from './CategoryGroup';
import type { SiteRow } from './types';

const baseRow: SiteRow = {
  company: '',
  source: 'internet_official',
  last_run_at: null,
  last_status: 'success',
  today_new: 0,
  last_error_short: '',
  alert_level: 'green',
};

describe('CategoryGroup', () => {
  it('renders category title and count', () => {
    const rows: SiteRow[] = [
      { ...baseRow, company: '腾讯' },
      { ...baseRow, company: '阿里巴巴' },
    ];
    render(<CategoryGroup label="互联网官网" rows={rows} selectedCompany={null} onSelect={() => {}} />);
    expect(screen.getByText('互联网官网')).toBeInTheDocument();
    expect(screen.getByText('(2)')).toBeInTheDocument();
  });

  it('renders one CompanyCard per row', () => {
    const rows: SiteRow[] = [
      { ...baseRow, company: '腾讯' },
      { ...baseRow, company: '阿里巴巴' },
      { ...baseRow, company: '字节跳动' },
    ];
    const { container } = render(
      <CategoryGroup label="互联网官网" rows={rows} selectedCompany={null} onSelect={() => {}} />,
    );
    expect(container.querySelectorAll('.sites-company-card').length).toBe(3);
  });

  it('marks the selected card as selected', () => {
    const rows: SiteRow[] = [
      { ...baseRow, company: '腾讯' },
      { ...baseRow, company: '阿里巴巴' },
    ];
    const { container } = render(
      <CategoryGroup label="互联网官网" rows={rows} selectedCompany="阿里巴巴" onSelect={() => {}} />,
    );
    const selected = container.querySelectorAll('.sites-company-card.selected');
    expect(selected.length).toBe(1);
    expect(selected[0].textContent).toContain('阿里巴巴');
  });
});
