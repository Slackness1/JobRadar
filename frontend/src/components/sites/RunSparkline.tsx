import type { SiteRun } from './types';

interface RunSparklineProps {
  runs: SiteRun[];
}

const MAX_BAR_HEIGHT = 40;

function barHeight(fetched: number): number {
  if (fetched <= 0) return 4;
  return Math.min(MAX_BAR_HEIGHT, Math.max(4, Math.log2(fetched + 1) * 6));
}

function barClass(status: string): string {
  if (status === 'failed') return 'sites-sparkline__bar failed';
  if (status === 'running') return 'sites-sparkline__bar running';
  return 'sites-sparkline__bar';
}

export default function RunSparkline({ runs }: RunSparklineProps) {
  if (runs.length === 0) {
    return <div className="sites-sparkline__cap">暂无 run 数据</div>;
  }

  // Render runs in the order provided (caller passes oldest-first for left-to-right display).
  const ordered = runs;
  const failedCount = runs.filter((r) => r.status === 'failed').length;

  return (
    <div>
      <div className="sites-sparkline">
        {ordered.map((r) => (
          <div
            key={r.id}
            className={barClass(r.status)}
            style={{ height: `${barHeight(r.fetched_count)}px` }}
            title={`${r.started_at} · ${r.status} · fetched=${r.fetched_count} new=${r.new_count}`}
          />
        ))}
      </div>
      <div className="sites-sparkline__cap">
        最近 {runs.length} 次 run · {failedCount} 失败
      </div>
    </div>
  );
}
