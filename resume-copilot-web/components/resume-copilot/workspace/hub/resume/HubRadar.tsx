'use client';

export interface RadarDatum { k: string; v: number; fin?: boolean }

/** 8 维雷达 — 移植自 hub-prototype hub-views.jsx::HubRadar。金融维(fin)土红加粗。 */
export function HubRadar({ size = 172, data, max = 100 }: { size?: number; data: RadarDatum[]; max?: number }) {
  const cx = size / 2, cy = size / 2, R = size * 0.38, n = data.length;
  const ang = (i: number) => (Math.PI * 2 * i) / n - Math.PI / 2;
  const pt = (i: number, r: number): [number, number] => [cx + Math.cos(ang(i)) * r, cy + Math.sin(ang(i)) * r];
  const poly = (r: number) => data.map((_, i) => pt(i, R * r).join(',')).join(' ');
  const valPoly = data.map((d, i) => pt(i, R * (d.v / max)).join(',')).join(' ');
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ overflow: 'visible' }}>
      {[0.25, 0.5, 0.75, 1].map((r, i) => (
        <polygon key={i} points={poly(r)} fill="none" stroke={i === 3 ? 'var(--border-strong)' : 'var(--border-warm)'} strokeWidth="1" />
      ))}
      {data.map((_, i) => { const [x, y] = pt(i, R); return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke="var(--border-warm)" strokeWidth="1" />; })}
      <polygon points={valPoly} fill="var(--terracotta)" fillOpacity="0.13" stroke="var(--terracotta)" strokeWidth="1.6" strokeLinejoin="round" />
      {data.map((d, i) => { const [x, y] = pt(i, R * (d.v / max)); return <circle key={i} cx={x} cy={y} r="2.6" fill="var(--terracotta-strong)" />; })}
      {data.map((d, i) => {
        const [x, y] = pt(i, R + 15);
        const anchor = Math.abs(x - cx) < 6 ? 'middle' : x > cx ? 'start' : 'end';
        return (
          <text key={i} x={x} y={y} textAnchor={anchor} dominantBaseline="middle"
            style={{ font: `${d.fin ? 700 : 500} 9.5px var(--font-sans)`, fill: d.fin ? 'var(--terracotta-strong)' : 'var(--olive)' }}>{d.k}</text>
        );
      })}
    </svg>
  );
}
