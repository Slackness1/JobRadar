import type { SiteRow } from './types';

interface CompanyCardProps {
  row: SiteRow;
  selected: boolean;
  onClick: (company: string) => void;
}

function relativeTime(iso: string | null): string {
  if (!iso) return '从未运行';
  const t = new Date(iso).getTime();
  const now = Date.now();
  const diffMs = Math.max(0, now - t);
  const min = Math.floor(diffMs / 60000);
  if (min < 1) return '刚刚';
  if (min < 60) return `${min}m 前`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h 前`;
  const day = Math.floor(hr / 24);
  return `${day}d 前`;
}

export default function CompanyCard({ row, selected, onClick }: CompanyCardProps) {
  const cls = `sites-company-card${selected ? ' selected' : ''}`;
  const deltaCls = `sites-company-card__delta${row.today_new === 0 ? ' zero' : ''}`;
  return (
    <div className={cls} onClick={() => onClick(row.company)}>
      <div className="sites-company-card__name">
        <span className={`sites-dot ${row.alert_level}`} />
        {row.company}
      </div>
      <div className="sites-company-card__meta">
        <span className={deltaCls}>{row.today_new === 0 ? '·' : `+${row.today_new}`}</span>
        {relativeTime(row.last_run_at)}
      </div>
    </div>
  );
}
