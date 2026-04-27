import type { SiteRow, SitesSummary } from './types';

interface SitesSummaryBarProps {
  summary: SitesSummary;
  rows: SiteRow[];
  onJumpToCompany: (company: string) => void;
}

function formatRunTime(iso: string | null): string {
  if (!iso) return '—';
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

function statusLabel(s: string | null): string {
  if (s === 'success') return '成功';
  if (s === 'failed') return '失败';
  if (s === 'running') return '运行中';
  if (!s) return '—';
  return s;
}

export default function SitesSummaryBar({ summary, rows, onJumpToCompany }: SitesSummaryBarProps) {
  const redRows = rows.filter((r) => r.alert_level === 'red');
  const showBanner = summary.alerted >= 2 && redRows.length > 0;

  const bannerNames = rows
    .filter((r) => r.alert_level === 'red' || r.alert_level === 'yellow')
    .slice(0, 3)
    .map((r) => r.company)
    .join('、');

  const handleBannerClick = () => {
    if (redRows.length > 0) {
      onJumpToCompany(redRows[0].company);
    }
  };

  const totalRows = rows.length;
  const failedToday = rows.filter((r) => r.last_status === 'failed').length;

  const subLine = summary.last_batch_at
    ? `上次跑批 ${formatRunTime(summary.last_batch_at)} · ${statusLabel(summary.last_batch_status)} · ${totalRows} 家公司 · ${failedToday} 失败`
    : '上次跑批 — 暂无运行';

  return (
    <>
      <div className="sites-summary-bar">
        <span className="hf-pill emerald">
          <span className="sites-dot green" />
          运行中 <strong style={{ marginLeft: 4 }}>{summary.active}</strong>
        </span>
        <span className="hf-pill amber">
          ⚠ 报警 <strong style={{ marginLeft: 4 }}>{summary.alerted}</strong>
        </span>
        <span className="hf-pill">
          <span className="sites-dot unknown" />
          停用 <strong style={{ marginLeft: 4 }}>{summary.disabled}</strong>
        </span>
        <span style={{ flex: 1 }} />
        <span className="hf-cap" style={{ marginRight: 8 }}>今日新增</span>
        <span className="sites-kpi-num">{summary.total_today_new}</span>
        <div className="sites-summary-bar__sub">{subLine}</div>
      </div>

      {showBanner ? (
        <div className="sites-alert-banner" onClick={handleBannerClick}>
          ⚠ 今日 {summary.alerted} 家爬虫疑似失效（{bannerNames}）— 点这里查看
        </div>
      ) : null}
    </>
  );
}
