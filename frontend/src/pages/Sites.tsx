import { useEffect, useMemo, useRef, useState } from 'react';

import { fetchSiteRuns, fetchSites, fetchSitesSummary } from '../api';
import CategoryGroup from '../components/sites/CategoryGroup';
import SiteDetailPanel from '../components/sites/SiteDetailPanel';
import SitesSummaryBar from '../components/sites/SitesSummaryBar';
import { ToastHost, useToast } from '../components/sites/ToastHost';
import type { SiteRecrawlOut, SiteRow, SiteRun, SitesSummary } from '../components/sites/types';

import '../styles/sites-theme.css';

const POLL_DEFAULT_MS = 8000;
const POLL_FAST_MS = 2000;

const SOURCE_GROUPS: Array<{ label: string; sources: string[] }> = [
  { label: '互联网官网', sources: ['internet_official'] },
  { label: '券商', sources: ['securities_zhiye', 'securities_zhiye_legacy', 'securities_hotjob', 'securities_moka_embedded'] },
  { label: '国央企', sources: ['state_owned_official'] },
  { label: '消费外企', sources: ['consumer_foreign_official'] },
];

function groupKeyForSource(source: string): string {
  for (const g of SOURCE_GROUPS) {
    if (g.sources.includes(source)) return g.label;
  }
  return source;
}

function SitesInner() {
  const [summary, setSummary] = useState<SitesSummary | null>(null);
  const [rows, setRows] = useState<SiteRow[] | null>(null);
  const [selectedCompany, setSelectedCompany] = useState<string | null>(null);
  const [runs, setRuns] = useState<SiteRun[]>([]);
  const [recrawlInFlight, setRecrawlInFlight] = useState<Record<string, number>>({});
  const intervalRef = useRef<number | null>(null);
  const toast = useToast();

  const refresh = async (currentSelected: string | null) => {
    try {
      const [s, r] = await Promise.all([fetchSitesSummary(), fetchSites()]);
      setSummary(s.data);
      setRows(r.data);
      if (currentSelected) {
        const runsRes = await fetchSiteRuns(currentSelected, 24);
        setRuns(runsRes.data);
      }
    } catch {
      // Silent for v1
    }
  };

  useEffect(() => {
    refresh(selectedCompany);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const cadence = Object.keys(recrawlInFlight).length > 0 ? POLL_FAST_MS : POLL_DEFAULT_MS;
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current);
    }
    intervalRef.current = window.setInterval(() => {
      refresh(selectedCompany);
    }, cadence);
    return () => {
      if (intervalRef.current !== null) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recrawlInFlight, selectedCompany]);

  useEffect(() => {
    if (!selectedCompany) {
      setRuns([]);
      return;
    }
    fetchSiteRuns(selectedCompany, 24).then((res) => setRuns(res.data)).catch(() => {});
  }, [selectedCompany]);

  useEffect(() => {
    if (!selectedCompany || Object.keys(recrawlInFlight).length === 0) return;
    const submitMs = recrawlInFlight[selectedCompany];
    if (!submitMs) return;
    const completed = runs.find(
      (r) => new Date(r.started_at).getTime() > submitMs && (r.status === 'success' || r.status === 'failed'),
    );
    if (completed) {
      toast.show(
        `${selectedCompany} 重跑${completed.status === 'success' ? '成功' : '失败'}`,
        completed.status === 'success' ? 'success' : 'failed',
      );
      setRecrawlInFlight((prev) => {
        const next = { ...prev };
        delete next[selectedCompany];
        return next;
      });
    }
  }, [runs, selectedCompany, recrawlInFlight, toast]);

  const handleRecrawlSubmit = (company: string, result: SiteRecrawlOut | null) => {
    if (result === null) {
      toast.show(`${company} 重跑提交失败`, 'failed');
      return;
    }
    setRecrawlInFlight((prev) => ({ ...prev, [company]: Date.now() }));
    toast.show(`${company} 重跑已启动`, 'success');
  };

  const groupedRows = useMemo(() => {
    if (!rows) return [];
    const buckets = new Map<string, SiteRow[]>();
    for (const row of rows) {
      const key = groupKeyForSource(row.source);
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key)!.push(row);
    }
    return SOURCE_GROUPS
      .filter((g) => buckets.has(g.label))
      .map((g) => ({ label: g.label, rows: buckets.get(g.label)! }))
      .concat(
        Array.from(buckets.entries())
          .filter(([k]) => !SOURCE_GROUPS.some((g) => g.label === k))
          .map(([label, rs]) => ({ label, rows: rs })),
      );
  }, [rows]);

  const isEmpty =
    summary !== null && rows !== null && rows.length === 0 && summary.total_today_new === 0;

  if (isEmpty) {
    return (
      <div className="hf" data-theme="sites">
        <div className="sites-shell">
          <div className="sites-empty">
            <h1 className="sites-empty__title">等首次跑完再回来看</h1>
            <p className="sites-empty__sub">
              明天 09:00 自动跑全量 tier crawl，
              或现在去 <a href="/crawl">触发爬取</a> 手动跑一次。
            </p>
          </div>
        </div>
      </div>
    );
  }

  const selectedRow = rows?.find((r) => r.company === selectedCompany) ?? null;
  const selectedInFlight = selectedCompany ? Boolean(recrawlInFlight[selectedCompany]) : false;

  return (
    <div className="hf" data-theme="sites">
      <div className="sites-shell">
        {summary ? (
          <SitesSummaryBar summary={summary} rows={rows ?? []} onJumpToCompany={setSelectedCompany} />
        ) : null}
        <div className="sites-content">
          <div>
            {groupedRows.map((g) => (
              <CategoryGroup
                key={g.label}
                label={g.label}
                rows={g.rows}
                selectedCompany={selectedCompany}
                onSelect={setSelectedCompany}
              />
            ))}
          </div>
          <SiteDetailPanel
            row={selectedRow}
            runs={runs}
            inFlight={selectedInFlight}
            onRecrawlSubmit={handleRecrawlSubmit}
          />
        </div>
      </div>
    </div>
  );
}

export default function Sites() {
  return (
    <ToastHost>
      <SitesInner />
    </ToastHost>
  );
}
