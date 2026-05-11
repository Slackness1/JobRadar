import { useEffect, useMemo, useState } from 'react';
import { fetchCoverage } from '../api';
import CoverageStarmap from '../components/CoverageStarmap';
import '../styles/coverage-theme.css';

// ─── Types from /api/coverage ────────────────────────────────
interface CompanyEntry {
  name: string;
  status: 'active' | 'deferred' | 'missing' | 'seasonal';
  fetched_7d: number;
  deferred_reason?: string | null;
}
interface ExtraEntry { name: string; fetched_7d: number; }
interface TrackEnumerate {
  id: string;
  name: string;
  mode: 'enumerate';
  t1_total: number;
  active_count: number;
  deferred_count: number;
  missing_count: number;
  rate: number;
  companies: CompanyEntry[];
  extras: ExtraEntry[];
}
interface TrackAbsolute {
  id: string;
  name: string;
  mode: 'absolute';
  active_company_count: number;
  active_total_fetched: number;
  note: string;
  active_companies: ExtraEntry[];
}
type Track = TrackEnumerate | TrackAbsolute;
interface CoverageResp {
  tracks: Track[];
  overall: {
    grand_t1: number; grand_active: number; rate: number; generated_at: string;
  };
}

// ─── Helpers ─────────────────────────────────────────────────
const pctClass = (rate: number) =>
  rate < 0.5 ? 'cv-track-pct-low' : rate < 0.75 ? 'cv-track-pct-mid' : 'cv-track-pct-high';

// Map fetched count → chip background intensity (oklch)
function chipColor(v: number): string {
  const intensity = v >= 1000 ? 1 : v >= 200 ? 0.78 : v >= 50 ? 0.6 : 0.42;
  return `oklch(0.66 0.13 40 / ${intensity})`;
}

// Friendly time
function friendlyTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-');
  } catch { return iso; }
}

// ─── KPI Ring ────────────────────────────────────────────────
function CoverageRing({ rate }: { rate: number }) {
  const r = 42;
  const circumference = 2 * Math.PI * r;
  const dash = rate * circumference;
  const pct = (rate * 100).toFixed(1);
  return (
    <svg viewBox="0 0 100 100" width="128" height="128" className="cv-ring-svg">
      <circle cx="50" cy="50" r={r} fill="none" stroke="var(--cv-warm-sand)" strokeWidth="10" />
      <circle
        cx="50" cy="50" r={r} fill="none" stroke="var(--cv-accent)" strokeWidth="10"
        strokeDasharray={`${dash} ${circumference}`} strokeLinecap="round"
        transform="rotate(-90 50 50)" style={{ transition: 'stroke-dasharray 0.6s ease' }}
      />
      <text x="50" y="50" textAnchor="middle" dy="0.1em"
        style={{ fontFamily: 'var(--cv-font-serif)', fontSize: 19, fontWeight: 700, fill: 'var(--cv-ink)' }}>
        {pct}%
      </text>
      <text x="50" y="63" textAnchor="middle"
        style={{ fontFamily: 'var(--cv-font-sans)', fontSize: 6, fill: 'var(--cv-soft)' }}>
        综合覆盖率
      </text>
    </svg>
  );
}

// ─── Track row (enumerate) ───────────────────────────────────
function TrackRow({ t, rank }: { t: TrackEnumerate; rank: number }) {
  // Sort companies: active by fetched desc → deferred → missing
  const sorted = useMemo(() => {
    const order: Record<CompanyEntry['status'], number> = {
      active: 0, missing: 1, seasonal: 2, deferred: 3,
    };
    return [...t.companies].sort((a, b) => {
      if (a.status !== b.status) return order[a.status] - order[b.status];
      return b.fetched_7d - a.fetched_7d;
    });
  }, [t.companies]);

  const [expanded, setExpanded] = useState(false);
  const visibleCount = expanded ? sorted.length : 16;
  const visible = sorted.slice(0, visibleCount);
  const hiddenCount = Math.max(0, sorted.length - visibleCount);
  const hasExtras = t.extras.length > 0;
  const canExpand = hiddenCount > 0 || hasExtras;
  const ratePct = Math.round(t.rate * 100);

  // 3-segment progress widths
  const activePct = (t.active_count / t.t1_total) * 100;
  const deferredPct = (t.deferred_count / t.t1_total) * 100;
  const missingPct = (t.missing_count / t.t1_total) * 100;

  return (
    <div className="cv-track">
      <div className="cv-track-head">
        <span className="cv-track-rank">#{rank}</span>
        <span className="cv-track-name">{t.name}</span>
        <span className="cv-track-counts">
          {t.active_count}/{t.t1_total}
          {' · '}
          <span className={pctClass(t.rate)}>{ratePct}%</span>
        </span>
        <div className="cv-progress">
          <div className="cv-progress-active" style={{ width: `${activePct}%` }} />
          <div className="cv-progress-deferred" style={{ width: `${deferredPct}%` }} />
          <div className="cv-progress-missing" style={{ width: `${missingPct}%` }} />
        </div>
        <span className={`cv-track-tail ${t.missing_count > 0 ? 'cv-track-tail-bad' : ''}`}>
          {t.missing_count > 0 ? `缺 ${t.missing_count} 家` : '无缺失'}
        </span>
        {canExpand && (
          <button type="button" className="cv-refresh-btn cv-track-expand"
            onClick={() => setExpanded((x) => !x)}>
            {expanded
              ? '收起 ⌃'
              : hiddenCount > 0
                ? `展开 ${hiddenCount} 家 ⌄`
                : `展开 +${t.extras.length} 非 T1 ⌄`}
          </button>
        )}
      </div>

      <div className="cv-chip-cloud">
        {visible.map((c) => {
          if (c.status === 'active') {
            return (
              <span key={c.name}
                className="cv-chip cv-chip-active"
                style={{ background: chipColor(c.fetched_7d) }}
                title={`${c.name} · 7天 ${c.fetched_7d} 岗`}>
                {c.name}
                <span className="cv-chip-active-num">{c.fetched_7d.toLocaleString()}</span>
              </span>
            );
          }
          if (c.status === 'deferred') {
            return (
              <span key={c.name}
                className="cv-chip cv-chip-deferred"
                title={c.deferred_reason || '工程不可行'}>
                {c.name} ✕
              </span>
            );
          }
          // missing or seasonal
          return (
            <span key={c.name}
              className="cv-chip cv-chip-missing"
              title="期望 active 但 7 天无数据">
              ? {c.name}
            </span>
          );
        })}
        {expanded && t.extras.length > 0 && (
          <>
            <div style={{
              width: '100%', height: 1, background: 'var(--cv-border-cream)',
              margin: '6px 0',
            }} />
            <span className="cv-chip-more" style={{ width: '100%' }}>
              非 T1 但已 active：
            </span>
            {t.extras.map((e) => (
              <span key={e.name} className="cv-chip cv-chip-extra"
                title={`${e.name} · 7天 ${e.fetched_7d} 岗`}>
                {e.name}
                <span className="cv-chip-active-num" style={{ color: 'var(--cv-amber)', opacity: 0.65 }}>
                  {e.fetched_7d}
                </span>
              </span>
            ))}
          </>
        )}
      </div>
    </div>
  );
}

// ─── SOE row (absolute) ──────────────────────────────────────
function SoeRow({ t }: { t: TrackAbsolute }) {
  const [expanded, setExpanded] = useState(false);
  const fillPct = Math.min(100, (t.active_company_count / 150) * 100); // 150 = 国资委央企+省企估值

  return (
    <div className="cv-soe">
      <span className="cv-soe-name">{t.name}</span>
      <div style={{ flex: 1 }}>
        <div className="cv-soe-bar-wrap">
          <div className="cv-soe-bar-fill" style={{ width: `${fillPct}%` }} />
          <div className="cv-soe-bar-text">
            {t.active_company_count} 家活跃 · {t.active_total_fetched.toLocaleString()} 岗 / 7 天
          </div>
        </div>
        <div style={{ fontSize: 11, color: 'var(--cv-soft)', marginTop: 6 }}>
          mode = absolute · 不列 T1 · 国资委央企 100 大 + 重点省企
        </div>
      </div>
      <button type="button"
        className="cv-refresh-btn"
        onClick={() => setExpanded((x) => !x)}
        style={{ flexShrink: 0 }}>
        {expanded ? '收起 ⌃' : `展开 ${Math.min(t.active_companies.length, 50)} 家 ⌄`}
      </button>
      {expanded && (
        <div className="cv-soe-extra" style={{ width: '100%' }}>
          {t.active_companies.map((c) => (
            <span key={c.name} className="cv-chip cv-chip-active"
              style={{ background: chipColor(c.fetched_7d), fontSize: 11 }}>
              {c.name}
              <span className="cv-chip-active-num">{c.fetched_7d}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main page ───────────────────────────────────────────────
export default function Coverage() {
  const [data, setData] = useState<CoverageResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [view, setView] = useState<'rank' | 'star'>('star');

  const load = async (manual = false) => {
    if (manual) setRefreshing(true);
    try {
      setError(null);
      const res = await fetchCoverage();
      setData(res.data as CoverageResp);
    } catch (e) {
      setError((e as Error).message || '加载失败');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void load();
    const tid = window.setInterval(() => { void load(); }, 60_000);
    return () => window.clearInterval(tid);
  }, []);

  if (loading && !data) {
    return <div data-theme="coverage"><div className="cv-loading">加载中…</div></div>;
  }
  if (error && !data) {
    return <div data-theme="coverage"><div className="cv-empty">加载失败：{error}</div></div>;
  }
  if (!data) return null;

  // Sort: enumerate tracks worst-first; absolute (SOE) at end
  const enumerated = data.tracks
    .filter((t): t is TrackEnumerate => t.mode === 'enumerate')
    .sort((a, b) => a.rate - b.rate);
  const absolutes = data.tracks
    .filter((t): t is TrackAbsolute => t.mode === 'absolute');

  // KPI deltas
  const totalMissing = enumerated.reduce((s, t) => s + t.missing_count, 0);
  const totalDeferred = enumerated.reduce((s, t) => s + t.deferred_count, 0);
  const totalT7Fetched = data.tracks.reduce((s, t) => {
    if (t.mode === 'enumerate') {
      return s + t.companies.reduce((ss, c) => ss + (c.fetched_7d || 0), 0)
               + t.extras.reduce((ss, e) => ss + (e.fetched_7d || 0), 0);
    }
    return s + t.active_total_fetched;
  }, 0);

  return (
    <div data-theme="coverage">
      {/* Header */}
      <div className="cv-header">
        <span className="cv-title">覆盖看板</span>
        <span className="cv-subtitle">· 头部公司爬取覆盖度</span>
        <div className="cv-header-meta">
          <div className="cv-view-toggle">
            <button type="button"
              className={`cv-view-toggle-btn ${view === 'star' ? 'is-active' : ''}`}
              onClick={() => setView('star')}>
              ✦ 公司星图
            </button>
            <button type="button"
              className={`cv-view-toggle-btn ${view === 'rank' ? 'is-active' : ''}`}
              onClick={() => setView('rank')}>
              ☰ 排行榜
            </button>
          </div>
          <span>更新于 {friendlyTime(data.overall.generated_at)} · 60s 自动刷新</span>
          <button type="button" className="cv-refresh-btn"
            onClick={() => void load(true)}
            disabled={refreshing}>
            {refreshing ? '刷新中…' : '↻ 立即刷新'}
          </button>
        </div>
      </div>

      {view === 'star' && (
        <CoverageStarmap tracks={data.tracks} overallRate={data.overall.rate} />
      )}

      {view === 'rank' && <>
      {/* Hero strip */}
      <div className="cv-hero">
        {/* Ring card */}
        <div className="cv-card cv-ring-card">
          <CoverageRing rate={data.overall.rate} />
          <div>
            <div className="cv-ring-summary-num">
              {data.overall.grand_active} / {data.overall.grand_t1} T1 已活跃
            </div>
            <div className="cv-ring-summary-meta">
              {enumerated.length} 个枚举赛道 + {absolutes.length} 个绝对赛道
            </div>
            <div className="cv-bars" aria-hidden>
              {Array.from({ length: 32 }).map((_, i) => (
                <span key={i}
                  style={{
                    height: `${10 + (i % 5) * 3}px`,
                    background: i < Math.floor(data.overall.rate * 32)
                      ? 'var(--cv-accent)'
                      : 'var(--cv-warm-sand)',
                  }} />
              ))}
            </div>
          </div>
        </div>

        {/* Todos card */}
        <div className="cv-card">
          <div className="cv-todos-title">📋 短板待办</div>
          <div className="cv-todos-grid">
            <div className="cv-todo-cell">
              <div className="cv-todo-num" style={{ color: 'var(--cv-crimson)' }}>{totalMissing}</div>
              <div className="cv-todo-label">家 T1 头部尚未爬到</div>
              <div className="cv-todo-cta">查看缺失清单 →</div>
            </div>
            <div className="cv-todo-cell">
              <div className="cv-todo-num" style={{ color: 'var(--cv-soft)' }}>{totalDeferred}</div>
              <div className="cv-todo-label">家工程不可行 (deferred)</div>
              <div className="cv-todo-cta" style={{ color: 'var(--cv-soft)' }}>查看反爬原因 →</div>
            </div>
            <div className="cv-todo-cell">
              <div className="cv-todo-num" style={{ color: 'var(--cv-amber)' }}>
                {totalT7Fetched.toLocaleString()}
              </div>
              <div className="cv-todo-label">7 天总入库岗位 (含 extras)</div>
              <div className="cv-todo-cta" style={{ color: 'var(--cv-amber)' }}>跳转 /jobs →</div>
            </div>
          </div>
        </div>

        {/* Trend card */}
        <div className="cv-card">
          <div className="cv-trend-eyebrow">每日 09:00 自动更新</div>
          <div className="cv-trend-headline">
            ↗ {(data.overall.rate * 100).toFixed(1)}%
          </div>
          <svg viewBox="0 0 100 30" style={{ width: '100%', height: 56, marginTop: 8 }}>
            <polyline
              points="0,26 14,24 28,22 42,20 56,16 70,14 84,10 100,7"
              fill="none" stroke="var(--cv-accent)" strokeWidth="1.4" />
            <circle cx="100" cy="7" r="2.4" fill="var(--cv-accent)" />
          </svg>
          <div className="cv-trend-meta">
            历史曲线（示意，待接入历史 snapshot）
          </div>
        </div>
      </div>

      {/* Tracks list */}
      <div className="cv-tracks-eyebrow">
        赛道 · 按覆盖率倒序（短板在前 · 共 {enumerated.length} 个枚举赛道）
      </div>
      {enumerated.map((t, i) => (
        <TrackRow key={t.id} t={t} rank={i + 1} />
      ))}

      {/* SOE (absolute) */}
      {absolutes.map((t) => (
        <SoeRow key={t.id} t={t} />
      ))}
      </>}
    </div>
  );
}
