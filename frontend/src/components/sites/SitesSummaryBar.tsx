import type { SiteRow, SitesSummary } from './types';

interface SitesSummaryBarProps {
  summary: SitesSummary;
  rows: SiteRow[];
  onJumpToCompany: (company: string) => void;
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
      </div>

      {showBanner ? (
        <div className="sites-alert-banner" onClick={handleBannerClick}>
          ⚠ 今日 {summary.alerted} 家爬虫疑似失效（{bannerNames}）— 点这里查看
        </div>
      ) : null}
    </>
  );
}
