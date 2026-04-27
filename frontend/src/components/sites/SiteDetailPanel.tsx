import RecrawlButton from './RecrawlButton';
import RunSparkline from './RunSparkline';
import type { SiteRecrawlOut, SiteRow, SiteRun } from './types';

interface SiteDetailPanelProps {
  row: SiteRow | null;
  runs: SiteRun[];
  inFlight: boolean;
  onRecrawlSubmit: (company: string, result: SiteRecrawlOut | null) => void;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${s % 60}s`;
}

function formatRunTime(iso: string): string {
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

function statusLabel(s: string): string {
  if (s === 'success') return '成功';
  if (s === 'failed') return '失败';
  if (s === 'running') return '运行中';
  return s;
}

function statusDotClass(s: string): string {
  if (s === 'success') return 'green';
  if (s === 'failed') return 'red';
  return 'unknown';
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

  // Stat strip calculations
  const totalFetched = runs.reduce((acc, r) => acc + r.fetched_count, 0);
  const successCount = runs.filter((r) => r.status === 'success').length;
  const avgDurationMs = runs.length
    ? Math.round(runs.reduce((acc, r) => acc + r.duration_ms, 0) / runs.length)
    : 0;
  const successRate = runs.length ? `${Math.round((100 * successCount) / runs.length)}%` : '—';

  const recentRuns = runs.slice(0, 5);

  return (
    <aside className="sites-detail-card">
      <div className="sites-detail-card__name">
        <span className={`sites-dot ${row.alert_level}`} />
        {row.company}
      </div>
      <div className="sites-detail-card__meta">
        <code>{row.source}</code>
      </div>

      {/* 4-cell stat strip */}
      <div className="sites-stat-strip">
        <div className="sites-stat-strip__cell">
          <span className="sites-stat-strip__num">{row.today_new}</span>
          <span className="sites-stat-strip__label">今日新增</span>
        </div>
        <div className="sites-stat-strip__cell">
          <span className="sites-stat-strip__num">{totalFetched}</span>
          <span className="sites-stat-strip__label">24h 抓取</span>
        </div>
        <div className="sites-stat-strip__cell">
          <span className="sites-stat-strip__num">{runs.length ? formatDuration(avgDurationMs) : '—'}</span>
          <span className="sites-stat-strip__label">平均耗时</span>
        </div>
        <div className="sites-stat-strip__cell">
          <span className="sites-stat-strip__num">{successRate}</span>
          <span className="sites-stat-strip__label">成功率</span>
        </div>
      </div>

      <RunSparkline runs={runs} />

      {/* Recent 5 runs table */}
      {recentRuns.length > 0 && (
        <table className="sites-recent-runs">
          <thead>
            <tr>
              <th>时间</th>
              <th>状态</th>
              <th className="num">抓取</th>
              <th className="num">新增</th>
              <th className="num">耗时</th>
            </tr>
          </thead>
          <tbody>
            {recentRuns.map((r) => (
              <tr key={r.id}>
                <td>{formatRunTime(r.started_at)}</td>
                <td className="status">
                  <span className={`sites-dot ${statusDotClass(r.status)}`} />
                  {statusLabel(r.status)}
                </td>
                <td className="num">{r.fetched_count}</td>
                <td className="num">{r.new_count}</td>
                <td className="num">{formatDuration(r.duration_ms)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {showError ? (
        <details className="sites-detail-card__error">
          <summary>最近一次错误</summary>
          <pre>{lastRun.error_message}</pre>
        </details>
      ) : null}

      {lastRun && lastRun.suggested_fix ? (
        <div className="sites-detail-card__diagnosis">
          <div className="sites-detail-card__diagnosis-label">🔧 LLM 诊断建议</div>
          <div className="sites-detail-card__diagnosis-body">{lastRun.suggested_fix}</div>
        </div>
      ) : null}

      <div style={{ marginTop: 16 }}>
        <RecrawlButton company={row.company} inFlight={inFlight} onSubmit={onRecrawlSubmit} />
      </div>
    </aside>
  );
}
