/**
 * /coverage 公司星图 — Coverage_B from JobRadar Wireframes
 *
 * Every T1 company is rendered as a dot inside a track-cluster halo.
 *   active   → filled terracotta, size scales with 7-day job count
 *   deferred → open gray circle (工程不可行)
 *   missing  → dashed red circle with `?` (期望 active 但 7 天无数据)
 *
 * Hover a dot → right sidebar updates with company detail.
 */
import { useMemo, useState } from 'react';

interface CompanyEntry {
  name: string;
  status: 'active' | 'deferred' | 'missing' | 'seasonal';
  fetched_7d: number;
  deferred_reason?: string | null;
}
interface ExtraEntry { name: string; fetched_7d: number; }
interface TrackEnumerate {
  id: string; name: string; mode: 'enumerate';
  t1_total: number; active_count: number; deferred_count: number; missing_count: number;
  rate: number; companies: CompanyEntry[]; extras: ExtraEntry[];
}
interface TrackAbsolute {
  id: string; name: string; mode: 'absolute';
  active_company_count: number; active_total_fetched: number; note: string;
  active_companies: ExtraEntry[];
}
type Track = TrackEnumerate | TrackAbsolute;

// Hand-tuned cluster positions for 8 tracks on a 900×600 SVG canvas.
// SOE sits in the center (smaller halo, denser) per wireframe.
const CLUSTER_LAYOUT: Record<string, { cx: number; cy: number; r: number; short: string }> = {
  internet:         { cx: 200, cy: 175, r: 86, short: '互联网' },
  hedge_funds:      { cx: 360, cy:  70, r: 48, short: '私募' },
  securities:       { cx: 440, cy: 170, r: 78, short: '券商' },
  banks:            { cx: 650, cy: 175, r: 88, short: '银行' },
  foreign_ibs:      { cx: 840, cy: 100, r: 48, short: '外资行' },
  consumer_foreign: { cx: 770, cy: 400, r: 96, short: '消费外企' },
  funds:            { cx: 530, cy: 480, r: 76, short: '公募' },
  insurance:        { cx: 290, cy: 470, r: 60, short: '保险' },
  pe_vc:            { cx: 120, cy: 370, r: 72, short: 'PE/VC' },
  // SOE: bigger halo + capped to top-N (less trypophobic), placed in center
  state_owned:      { cx: 470, cy: 300, r: 70, short: '国央企' },
  // Phase 11: 资管 / 理财派生 — 当前活跃度低，安排小晕圈
  asset_mgmt:       { cx: 410, cy: 555, r: 36, short: '资管' },
};

// Cap SOE rendered dots — 50 in a small halo was a sea-of-dots; top-20 reads
// better and the sidebar already lists the rest.
const SOE_DOT_CAP = 20;

interface DotPoint {
  x: number; y: number; size: number;
  kind: 'active' | 'deferred' | 'missing' | 'soe';
  intensity: number;
  name: string;
  fetched_7d: number;
  deferred_reason?: string | null;
  trackId: string;
  trackName: string;
}

/** Golden-ratio spiral placement — deterministic, looks organic. */
function spiralPoints(n: number, cx: number, cy: number, r: number): { x: number; y: number }[] {
  const out: { x: number; y: number }[] = [];
  for (let i = 0; i < n; i++) {
    const angle = i * 137.5 * (Math.PI / 180);
    const rr = r * Math.sqrt((i + 0.5) / Math.max(1, n)) * 0.85;
    out.push({ x: cx + Math.cos(angle) * rr, y: cy + Math.sin(angle) * rr });
  }
  return out;
}

function sizeForActive(v: number): { size: number; intensity: number } {
  // log scale: 1 job ~ 4px, 6000 jobs ~ 12px
  const intensity = Math.min(1, Math.log(v + 1) / Math.log(6000));
  return { size: 4 + intensity * 8, intensity: 0.5 + intensity * 0.5 };
}

function buildDots(tracks: Track[]): DotPoint[] {
  const dots: DotPoint[] = [];
  for (const t of tracks) {
    const layout = CLUSTER_LAYOUT[t.id];
    if (!layout) continue;
    if (t.mode === 'absolute') {
      // SOE: render top-N active companies, sized by fetched_7d
      const companies = t.active_companies.slice(0, SOE_DOT_CAP);
      const pts = spiralPoints(companies.length, layout.cx, layout.cy, layout.r);
      companies.forEach((c, i) => {
        const { size, intensity } = sizeForActive(c.fetched_7d);
        dots.push({
          x: pts[i].x, y: pts[i].y,
          // Slightly larger dots now that there are fewer of them
          size: Math.max(4.5, size * 0.95), intensity, kind: 'soe',
          name: c.name, fetched_7d: c.fetched_7d,
          trackId: t.id, trackName: t.name,
        });
      });
      continue;
    }
    // enumerate
    // Sort: active by fetched desc → deferred → missing — visually puts the dense star in center
    const sorted = [...t.companies].sort((a, b) => {
      const order: Record<CompanyEntry['status'], number> =
        { active: 0, missing: 1, seasonal: 2, deferred: 3 };
      if (a.status !== b.status) return order[a.status] - order[b.status];
      return b.fetched_7d - a.fetched_7d;
    });
    const pts = spiralPoints(sorted.length, layout.cx, layout.cy, layout.r);
    sorted.forEach((c, i) => {
      if (c.status === 'active' || c.status === 'seasonal') {
        const { size, intensity } = sizeForActive(c.fetched_7d);
        dots.push({
          x: pts[i].x, y: pts[i].y, size, intensity, kind: 'active',
          name: c.name, fetched_7d: c.fetched_7d,
          trackId: t.id, trackName: t.name,
        });
      } else if (c.status === 'deferred') {
        dots.push({
          x: pts[i].x, y: pts[i].y, size: 4, intensity: 0, kind: 'deferred',
          name: c.name, fetched_7d: 0,
          deferred_reason: c.deferred_reason,
          trackId: t.id, trackName: t.name,
        });
      } else {
        dots.push({
          x: pts[i].x, y: pts[i].y, size: 5, intensity: 0, kind: 'missing',
          name: c.name, fetched_7d: 0,
          trackId: t.id, trackName: t.name,
        });
      }
    });
  }
  return dots;
}

export default function CoverageStarmap({ tracks, overallRate }: { tracks: Track[]; overallRate: number }) {
  const dots = useMemo(() => buildDots(tracks), [tracks]);
  const [hoverId, setHoverId] = useState<string | null>(null);

  const hovered = useMemo(() => {
    if (!hoverId) return null;
    return dots.find(d => `${d.trackId}-${d.name}` === hoverId) || null;
  }, [hoverId, dots]);

  // Pull out PE/VC missing companies for the "短板高亮" sidebar block
  const pevc = tracks.find((t): t is TrackEnumerate => t.id === 'pe_vc' && t.mode === 'enumerate');
  const pevcMissing = pevc?.companies.filter(c => c.status === 'missing') || [];

  // Deferred list across all tracks
  const deferredAll: { name: string; reason: string; trackName: string }[] = [];
  for (const t of tracks) {
    if (t.mode !== 'enumerate') continue;
    for (const c of t.companies) {
      if (c.status === 'deferred') {
        deferredAll.push({
          name: c.name,
          reason: c.deferred_reason || '工程不可行',
          trackName: t.name,
        });
      }
    }
  }

  // Layout-only summary numbers
  const totalActive = dots.filter(d => d.kind === 'active' || d.kind === 'soe').length;
  const totalMissing = dots.filter(d => d.kind === 'missing').length;
  const totalDeferred = dots.filter(d => d.kind === 'deferred').length;

  return (
    <div className="cv-starmap">
      <div className="cv-starmap-legend">
        <span className="cv-sm-legend-item"><span className="cv-sm-legend-dot is-active" />活跃 ({totalActive})</span>
        <span className="cv-sm-legend-item"><span className="cv-sm-legend-dot is-deferred" />缓议 ({totalDeferred})</span>
        <span className="cv-sm-legend-item"><span className="cv-sm-legend-dot is-missing" />缺失 ({totalMissing})</span>
        <span className="cv-sm-legend-item cv-sm-legend-soe">国央企 (绝对数 · 内圈)</span>
        <span style={{ marginLeft: 'auto', color: 'var(--cv-soft)', fontSize: 12 }}>
          点大小 = 7 天岗位数（对数） · 悬停查看详情
        </span>
      </div>

      <div className="cv-starmap-stage">
        <div className="cv-starmap-headline">
          <div className="cv-starmap-headline-num">{(overallRate * 100).toFixed(1)}%</div>
          <div className="cv-starmap-headline-sub">
            综合覆盖率 · {totalActive} 颗活跃星 · 黑洞 {totalMissing} 处 · 缓议 {totalDeferred}
          </div>
        </div>

        <div className="cv-starmap-canvas-wrap">
          <svg viewBox="0 0 900 600" className="cv-starmap-canvas">
            <defs>
              <pattern id="cv-sm-grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(20,20,19,0.05)" strokeWidth="0.5" />
              </pattern>
              <radialGradient id="cv-sm-halo" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="rgba(201,100,66,0.10)" />
                <stop offset="100%" stopColor="rgba(201,100,66,0.0)" />
              </radialGradient>
              {/* SOE halo — same terracotta family as other tracks; the
                  dashed stroke + "N 家活跃" label do the absolute-mode
                  signalling, color doesn't need to. */}
              <radialGradient id="cv-sm-halo-soe" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="rgba(201,100,66,0.12)" />
                <stop offset="100%" stopColor="rgba(201,100,66,0.0)" />
              </radialGradient>
            </defs>

            <rect width="900" height="600" fill="url(#cv-sm-grid)" />

            {/* Cluster halos */}
            {tracks.map(t => {
              const layout = CLUSTER_LAYOUT[t.id];
              if (!layout) return null;
              const isSoe = t.id === 'state_owned';
              return (
                <g key={`halo-${t.id}`}>
                  <circle cx={layout.cx} cy={layout.cy} r={layout.r}
                          fill={isSoe ? 'url(#cv-sm-halo-soe)' : 'url(#cv-sm-halo)'}
                          stroke="rgba(201,100,66,0.28)"
                          strokeWidth="0.8"
                          strokeDasharray={isSoe ? '3 3' : ''} />
                </g>
              );
            })}

            {/* Cluster labels */}
            {tracks.map(t => {
              const layout = CLUSTER_LAYOUT[t.id];
              if (!layout) return null;
              const ratio = t.mode === 'enumerate'
                ? `${t.active_count}/${t.t1_total} · ${Math.round(t.rate * 100)}%`
                : `${t.active_company_count} 家活跃`;
              return (
                <g key={`label-${t.id}`}>
                  <text x={layout.cx} y={layout.cy - layout.r - 8} textAnchor="middle"
                        fontFamily="var(--cv-font-serif)" fontSize="14" fontWeight="600"
                        fill="var(--cv-ink)">
                    {layout.short}
                  </text>
                  <text x={layout.cx} y={layout.cy - layout.r + 6} textAnchor="middle"
                        fontFamily="var(--cv-font-mono)" fontSize="9.5"
                        fill="var(--cv-soft)">
                    {ratio}
                  </text>
                </g>
              );
            })}

            {/* Dots */}
            {dots.map(d => {
              const id = `${d.trackId}-${d.name}`;
              const isHover = hoverId === id;
              const baseFill = (d.kind === 'active' || d.kind === 'soe')
                ? `oklch(0.65 0.13 40 / ${d.intensity})`
                : 'transparent';

              if (d.kind === 'active' || d.kind === 'soe') {
                return (
                  <g key={id}
                     onMouseEnter={() => setHoverId(id)}
                     onMouseLeave={() => setHoverId(null)}
                     style={{ cursor: 'pointer' }}>
                    <circle cx={d.x} cy={d.y} r={d.size + (isHover ? 2 : 0)}
                            fill={baseFill}
                            stroke={isHover ? 'var(--cv-ink)' : 'transparent'}
                            strokeWidth={isHover ? 1 : 0} />
                  </g>
                );
              }
              if (d.kind === 'deferred') {
                return (
                  <g key={id}
                     onMouseEnter={() => setHoverId(id)}
                     onMouseLeave={() => setHoverId(null)}
                     style={{ cursor: 'pointer' }}>
                    <circle cx={d.x} cy={d.y} r={4 + (isHover ? 1.5 : 0)}
                            fill="transparent"
                            stroke={isHover ? 'var(--cv-ink)' : 'var(--cv-soft)'}
                            strokeWidth="1" />
                  </g>
                );
              }
              // missing
              return (
                <g key={id}
                   onMouseEnter={() => setHoverId(id)}
                   onMouseLeave={() => setHoverId(null)}
                   style={{ cursor: 'pointer' }}>
                  <circle cx={d.x} cy={d.y} r={5 + (isHover ? 1.5 : 0)}
                          fill="transparent" stroke="#b53333"
                          strokeWidth="1" strokeDasharray="2 2" />
                  <text x={d.x} y={d.y + 2} textAnchor="middle"
                        fontSize="6" fill="#b53333"
                        style={{ pointerEvents: 'none' }}>?</text>
                </g>
              );
            })}

            {/* Hover ring + leader line */}
            {hovered && (
              <g>
                <circle cx={hovered.x} cy={hovered.y} r={hovered.size + 6}
                        fill="none" stroke="var(--cv-accent)" strokeWidth="1.2"
                        strokeDasharray="3 2" />
              </g>
            )}
          </svg>

          {/* Hover tooltip (HTML overlay for crisp typography) */}
          {hovered && (
            <div className="cv-sm-tooltip"
                 style={{
                   left: `${(hovered.x / 900) * 100}%`,
                   top: `${(hovered.y / 600) * 100}%`,
                 }}>
              <div className="cv-sm-tooltip-title">{hovered.name}</div>
              <div className="cv-sm-tooltip-meta">{hovered.trackName}</div>
              {hovered.kind === 'active' || hovered.kind === 'soe' ? (
                <div className="cv-sm-tooltip-stat">
                  <span className="cv-sm-tooltip-num">{hovered.fetched_7d.toLocaleString()}</span>
                  <span className="cv-sm-tooltip-num-meta">7 天岗位数</span>
                </div>
              ) : hovered.kind === 'deferred' ? (
                <div className="cv-sm-tooltip-deferred">
                  缓议 · {hovered.deferred_reason || '工程不可行'}
                </div>
              ) : (
                <div className="cv-sm-tooltip-missing">
                  应有但 7 天无数据 — 可能要修爬虫
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Sidebar */}
      <aside className="cv-starmap-aside">
        {hovered ? (
          <div className="cv-card">
            <div className="cv-sm-aside-eyebrow">悬停 · {hovered.trackName}</div>
            <div className="cv-sm-aside-name">{hovered.name}</div>
            <div className="cv-sm-aside-status">
              {hovered.kind === 'active' || hovered.kind === 'soe' ? '活跃 ●' :
               hovered.kind === 'deferred' ? '缓议 ○' : '缺失 ?'}
            </div>
            {hovered.kind === 'active' || hovered.kind === 'soe' ? (
              <>
                <div className="cv-sm-aside-num">{hovered.fetched_7d.toLocaleString()}</div>
                <div className="cv-sm-aside-num-meta">7 天岗位数</div>
              </>
            ) : hovered.kind === 'deferred' ? (
              <div className="cv-sm-aside-reason">{hovered.deferred_reason || '工程不可行'}</div>
            ) : (
              <div className="cv-sm-aside-reason">期望 active 但 7 天无数据 — 检查爬虫</div>
            )}
          </div>
        ) : (
          <div className="cv-card cv-card-thin">
            <div className="cv-sm-aside-eyebrow">悬停说明</div>
            <div className="cv-sm-aside-empty">
              悬停画布里的星点，看公司 7 天岗位数 / 缓议原因 / 缺失诊断。
            </div>
          </div>
        )}

        {pevcMissing.length > 0 && (
          <div className="cv-card cv-card-thin">
            <div className="cv-sm-aside-eyebrow" style={{ color: 'var(--cv-crimson)' }}>
              🔻 短板高亮 · {pevc?.name}
            </div>
            <div style={{ fontSize: 12, color: 'var(--cv-soft)', marginBottom: 6 }}>
              {pevc?.t1_total} 家头部 · 仅 {pevc?.active_count} 家活跃
            </div>
            <div className="cv-sm-aside-chips">
              {pevcMissing.map(c => (
                <span key={c.name} className="cv-chip cv-chip-missing">? {c.name}</span>
              ))}
            </div>
          </div>
        )}

        {deferredAll.length > 0 && (
          <div className="cv-card cv-card-thin">
            <div className="cv-sm-aside-eyebrow">⚙ 缓议公司 ({deferredAll.length})</div>
            {deferredAll.slice(0, 8).map(d => (
              <div key={`${d.trackName}-${d.name}`} className="cv-sm-deferred-row">
                <span className="cv-sm-deferred-name">{d.name}</span>
                <span className="cv-sm-deferred-reason">{d.reason}</span>
              </div>
            ))}
            {deferredAll.length > 8 && (
              <div style={{ fontSize: 11, color: 'var(--cv-accent)', marginTop: 6 }}>
                + {deferredAll.length - 8} 家
              </div>
            )}
          </div>
        )}
      </aside>
    </div>
  );
}
