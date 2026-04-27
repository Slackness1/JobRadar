import type { SiteRow } from './types';

interface CompanyCardProps {
  row: SiteRow;
  selected: boolean;
  onClick: (company: string) => void;
}

function formatRunTime(iso: string | null): string {
  if (!iso) return '从未运行';
  const d = new Date(iso);
  const now = new Date();
  const sameDay =
    d.getDate() === now.getDate() &&
    d.getMonth() === now.getMonth() &&
    d.getFullYear() === now.getFullYear();
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  if (sameDay) return `${hh}:${mm}`;
  const md = `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return `${md} ${hh}:${mm}`;
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
        {row.last_status === 'failed' && (
          <span style={{ color: 'var(--crimson)', marginRight: 4 }}>⚠</span>
        )}
        {formatRunTime(row.last_run_at)}
      </div>
    </div>
  );
}
