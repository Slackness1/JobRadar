// wf-kit.jsx — grayscale mid-fi wireframe primitives for JobRadar 简历编辑页 + AI 助手 v2
// All neutral. No brand color. Real Chinese copy. Exported to window.

const WF = {
  ink:   '#1c1917',
  ink2:  '#44403c',
  muted: '#78716c',
  faint: '#a8a29e',
  ghost: '#c9c5bf',
  line:  '#e7e5e4',
  line2: '#d6d3d1',
  fill:  '#f6f5f3',
  fill2: '#eeece8',
  paper: '#ffffff',
  dark:  '#3f3b36',     // "active/primary" stand-in (solid neutral)
  meta:  '#6b7c93',     // annotation ink (cool meta-gray, not brand)
  metaBg:'#eef1f4',
  sans:  '"Geist", -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif',
  mono:  '"Geist Mono", ui-monospace, "SFMono-Regular", monospace',
};

// ---- tiny building blocks ----------------------------------------------

// grey placeholder text line
function WLine({ w = '100%', h = 7, c = WF.line2, mb = 7, style }) {
  return <div style={{ width: w, height: h, background: c, borderRadius: 4, marginBottom: mb, ...style }} />;
}

// a run of placeholder lines
function WLines({ rows = 3, last = '64%', gap = 7, c = WF.line2, h = 7 }) {
  return (
    <div>
      {Array.from({ length: rows }).map((_, i) => (
        <WLine key={i} w={i === rows - 1 ? last : '100%'} h={h} c={c} mb={i === rows - 1 ? 0 : gap} />
      ))}
    </div>
  );
}

// section label / overline
function WTag({ children, style }) {
  return (
    <div style={{ font: `600 10px/1.3 ${WF.sans}`, letterSpacing: '0.12em', textTransform: 'uppercase',
      color: WF.faint, ...style }}>{children}</div>
  );
}

function WBtn({ children, solid, ghost, sm, style }) {
  const base = {
    display: 'inline-flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap',
    font: `${solid ? 600 : 500} ${sm ? 11 : 12}px/1 ${WF.sans}`,
    padding: sm ? '6px 10px' : '9px 14px', borderRadius: 9, cursor: 'default',
  };
  const skin = solid
    ? { background: WF.dark, color: '#fff', border: `1px solid ${WF.dark}` }
    : ghost
      ? { background: 'transparent', color: WF.ink2, border: `1px solid transparent` }
      : { background: WF.paper, color: WF.ink2, border: `1px solid ${WF.line2}` };
  return <span style={{ ...base, ...skin, ...style }}>{children}</span>;
}

function WChip({ children, active, style }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5, whiteSpace: 'nowrap',
      font: `500 11px/1 ${WF.sans}`, padding: '6px 11px', borderRadius: 999,
      color: active ? '#fff' : WF.ink2,
      background: active ? WF.dark : WF.paper,
      border: `1px solid ${active ? WF.dark : WF.line2}`, ...style,
    }}>{children}</span>
  );
}

// pill tabs (segmented)
function WTabs({ items, active = 0, style }) {
  return (
    <div style={{ display: 'inline-flex', gap: 3, padding: 3, background: WF.fill2,
      borderRadius: 11, border: `1px solid ${WF.line}`, ...style }}>
      {items.map((t, i) => (
        <span key={i} style={{
          font: `${i === active ? 600 : 500} 12px/1 ${WF.sans}`,
          padding: '7px 13px', borderRadius: 8,
          color: i === active ? WF.ink : WF.muted,
          background: i === active ? WF.paper : 'transparent',
          boxShadow: i === active ? '0 1px 2px rgba(0,0,0,.06)' : 'none',
        }}>{t}</span>
      ))}
    </div>
  );
}

// generic card
function WCard({ children, pad = 14, style }) {
  return (
    <div style={{ background: WF.paper, border: `1px solid ${WF.line}`, borderRadius: 14,
      padding: pad, ...style }}>{children}</div>
  );
}

// dashed annotation callout (light, meta-gray)
function WNote({ children, style }) {
  return (
    <div style={{
      font: `500 11px/1.5 ${WF.sans}`, color: WF.meta, background: WF.metaBg,
      border: `1px dashed ${WF.meta}`, borderRadius: 9, padding: '7px 10px',
      maxWidth: 230, ...style,
    }}>
      <span style={{ fontWeight: 700, marginRight: 4 }}>※</span>{children}
    </div>
  );
}

// avatar dot
function WDot({ s = 26, label = '', style }) {
  return (
    <div style={{ width: s, height: s, borderRadius: 999, background: WF.dark, color: '#fff',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      font: `600 ${s * 0.42}px ${WF.sans}`, flex: 'none', ...style }}>{label}</div>
  );
}

// horizontal scored bar (dimension meter)
function WMeter({ label, score, of = 100, note }) {
  const pct = Math.round((score / of) * 100);
  return (
    <div style={{ marginBottom: 11 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 5 }}>
        <span style={{ font: `500 12px/1 ${WF.sans}`, color: WF.ink2 }}>{label}</span>
        <span style={{ font: `600 12px ${WF.mono}`, color: WF.ink }}>{score}<span style={{ color: WF.faint, fontWeight: 400 }}>/{of}</span></span>
      </div>
      <div style={{ height: 6, borderRadius: 999, background: WF.fill2, overflow: 'hidden' }}>
        <div style={{ width: pct + '%', height: '100%', background: pct >= 80 ? WF.ink2 : pct >= 60 ? WF.muted : WF.faint, borderRadius: 999 }} />
      </div>
      {note && <div style={{ font: `400 10.5px/1.4 ${WF.sans}`, color: WF.faint, marginTop: 4 }}>{note}</div>}
    </div>
  );
}

// ---- 8-dim radar chart (SVG) -------------------------------------------
function WRadar({ size = 220, data, max = 100 }) {
  const cx = size / 2, cy = size / 2, R = size * 0.40;
  const n = data.length;
  const ang = (i) => (Math.PI * 2 * i) / n - Math.PI / 2;
  const pt = (i, r) => [cx + Math.cos(ang(i)) * r, cy + Math.sin(ang(i)) * r];
  const rings = [0.25, 0.5, 0.75, 1];
  const poly = (r) => data.map((_, i) => pt(i, R * r).join(',')).join(' ');
  const valPoly = data.map((d, i) => pt(i, R * (d.v / max)).join(',')).join(' ');
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ overflow: 'visible' }}>
      {rings.map((r, i) => (
        <polygon key={i} points={poly(r)} fill="none" stroke={i === rings.length - 1 ? WF.line2 : WF.line} strokeWidth="1" />
      ))}
      {data.map((_, i) => {
        const [x, y] = pt(i, R);
        return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke={WF.line} strokeWidth="1" />;
      })}
      <polygon points={valPoly} fill={WF.ink2} fillOpacity="0.12" stroke={WF.ink2} strokeWidth="1.5" strokeLinejoin="round" />
      {data.map((d, i) => {
        const [x, y] = pt(i, R * (d.v / max));
        return <circle key={i} cx={x} cy={y} r="2.6" fill={WF.ink} />;
      })}
      {data.map((d, i) => {
        const [x, y] = pt(i, R + 16);
        const anchor = Math.abs(x - cx) < 6 ? 'middle' : x > cx ? 'start' : 'end';
        return (
          <text key={i} x={x} y={y} textAnchor={anchor} dominantBaseline="middle"
            style={{ font: `500 10px ${WF.sans}`, fill: d.fin ? WF.ink : WF.muted, fontWeight: d.fin ? 700 : 500 }}>
            {d.k}
          </text>
        );
      })}
    </svg>
  );
}

Object.assign(window, { WF, WLine, WLines, WTag, WBtn, WChip, WTabs, WCard, WNote, WDot, WMeter, WRadar });
