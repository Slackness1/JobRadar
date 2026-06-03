'use client';

/**
 * 8 维雷达图 — React 版,逐行照搬设计稿 简历打分报告.html 的 drawRadar。
 * terracotta 主色,fin 维标签加粗变色。纯 SVG,无依赖。
 */

export interface RadarDim {
  k: string;        // 短标签
  v: number;        // 0-100
  fin?: boolean;    // 金融独有维(标签加粗变色)
}

const CX = 150;
const CY = 150;
const R = 96;

function angle(i: number, n: number): number {
  return (Math.PI * 2 * i) / n - Math.PI / 2;
}

function pt(i: number, n: number, r: number): [number, number] {
  const a = angle(i, n);
  return [CX + Math.cos(a) * r, CY + Math.sin(a) * r];
}

export function ScoreRadar({ data, size = 300 }: { data: RadarDim[]; size?: number }) {
  const n = data.length;
  const rings = [0.25, 0.5, 0.75, 1];
  const valuePts = data.map((d, i) => pt(i, n, R * (d.v / 100)).join(',')).join(' ');

  return (
    <svg width={size} height={size} viewBox="0 0 300 300" style={{ overflow: 'visible' }}>
      {/* rings */}
      {rings.map((r, idx) => (
        <polygon
          key={`ring-${idx}`}
          points={data.map((_, i) => pt(i, n, R * r).join(',')).join(' ')}
          fill="none"
          stroke={idx === rings.length - 1 ? '#d1cfc5' : '#e8e6dc'}
          strokeWidth={1}
        />
      ))}
      {/* spokes */}
      {data.map((_, i) => {
        const [x, y] = pt(i, n, R);
        return <line key={`spoke-${i}`} x1={CX} y1={CY} x2={x} y2={y} stroke="#e8e6dc" strokeWidth={1} />;
      })}
      {/* value polygon */}
      <polygon points={valuePts} fill="#c96442" fillOpacity={0.14} stroke="#c96442" strokeWidth={2} strokeLinejoin="round" />
      {/* value dots */}
      {data.map((d, i) => {
        const [x, y] = pt(i, n, R * (d.v / 100));
        return <circle key={`dot-${i}`} cx={x} cy={y} r={3} fill="#c96442" />;
      })}
      {/* labels */}
      {data.map((d, i) => {
        const [x, y] = pt(i, n, R + 20);
        const anchor = Math.abs(x - CX) < 8 ? 'middle' : x > CX ? 'start' : 'end';
        return (
          <text
            key={`label-${i}`}
            x={x}
            y={y}
            textAnchor={anchor}
            dominantBaseline="middle"
            fontFamily="'Inter','Noto Sans SC',sans-serif"
            fontSize={11}
            fontWeight={d.fin ? 600 : 500}
            fill={d.fin ? '#a84f34' : '#5e5d59'}
          >
            {d.k}
          </text>
        );
      })}
    </svg>
  );
}
