import RecrawlButton from './RecrawlButton';
import RunSparkline from './RunSparkline';
import type { SiteRecrawlOut, SiteRow, SiteRun } from './types';

interface SiteDetailPanelProps {
  row: SiteRow | null;
  runs: SiteRun[];
  inFlight: boolean;
  onRecrawlSubmit: (company: string, result: SiteRecrawlOut | null) => void;
}

export default function SiteDetailPanel({ row, runs, inFlight, onRecrawlSubmit }: SiteDetailPanelProps) {
  if (!row) {
    return (
      <aside className="sites-detail-card empty">
        ← 点左侧任意公司查看详情
      </aside>
    );
  }

  const lastRun = runs[0];
  const showError = lastRun && lastRun.status === 'failed' && lastRun.error_message;

  return (
    <aside className="sites-detail-card">
      <div className="sites-detail-card__name">
        <span className={`sites-dot ${row.alert_level}`} />
        {row.company}
      </div>
      <div className="sites-detail-card__meta">
        <code>{row.source}</code>
      </div>

      <RunSparkline runs={runs} />

      {showError ? (
        <details className="sites-detail-card__error">
          <summary>最近一次错误</summary>
          <pre>{lastRun.error_message}</pre>
        </details>
      ) : null}

      <div style={{ marginTop: 16 }}>
        <RecrawlButton company={row.company} inFlight={inFlight} onSubmit={onRecrawlSubmit} />
      </div>
    </aside>
  );
}
