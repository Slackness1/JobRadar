'use client';
import { useState } from 'react';
import type { JSX } from 'react';

const TEMPLATES: [string, number][] = [
  ['素白单栏', 0],
  ['蓝栏双侧', 1],
  ['深首横幅', 2],
  ['墨绿弧顶', 3],
  ['浅青色块', 4],
];

/** 模板 mini-card 缩略图 — 移植自 hub-prototype LeftTemplate.mini。 */
function mini(i: number): JSX.Element {
  if (i === 1) {
    return (
      <div style={{ display: 'flex', gap: 4, height: '100%' }}>
        <div style={{ width: '34%', background: 'var(--ring-warm)', borderRadius: 2 }} />
        <div style={{ flex: 1 }}>
          {[88, 70, 80, 64, 76].map((w, k) => (
            <div key={k} style={{ width: `${w}%`, height: 3, background: 'var(--border-warm)', borderRadius: 2, marginBottom: 4 }} />
          ))}
        </div>
      </div>
    );
  }
  if (i === 2) {
    return (
      <div style={{ height: '100%' }}>
        <div style={{ height: 16, background: 'var(--ink-soft)', borderRadius: 2, marginBottom: 6 }} />
        {[100, 84, 92, 60].map((w, k) => (
          <div key={k} style={{ width: `${w}%`, height: 3, background: 'var(--border-warm)', borderRadius: 2, marginBottom: 4 }} />
        ))}
      </div>
    );
  }
  if (i === 3) {
    return (
      <div style={{ height: '100%' }}>
        <div style={{ height: 18, background: 'var(--ring-warm)', borderRadius: '0 0 16px 16px', marginBottom: 6 }} />
        {[100, 84, 92, 56].map((w, k) => (
          <div key={k} style={{ width: `${w}%`, height: 3, background: 'var(--border-warm)', borderRadius: 2, marginBottom: 4 }} />
        ))}
      </div>
    );
  }
  if (i === 4) {
    return (
      <div style={{ height: '100%' }}>
        <div
          style={{
            height: 8,
            width: '52%',
            background: 'var(--terracotta-wash)',
            borderRadius: 2,
            marginBottom: 6,
            boxShadow: '0 0 0 1px #eccfb6',
          }}
        />
        {[100, 84, 92, 58].map((w, k) => (
          <div key={k} style={{ width: `${w}%`, height: 3, background: 'var(--border-warm)', borderRadius: 2, marginBottom: 4 }} />
        ))}
      </div>
    );
  }
  return (
    <div style={{ height: '100%' }}>
      <div style={{ width: '44%', height: 6, background: 'var(--ink-soft)', borderRadius: 2, marginBottom: 4 }} />
      <div style={{ height: 1, background: 'var(--ring-warm)', margin: '3px 0 6px' }} />
      {[100, 84, 92, 60].map((w, k) => (
        <div key={k} style={{ width: `${w}%`, height: 3, background: 'var(--border-warm)', borderRadius: 2, marginBottom: 4 }} />
      ))}
    </div>
  );
}

/** 左栏「模板」tab — 5 个模板 mini-card 选择。 */
export function LeftTemplate() {
  const [sel, setSel] = useState(0);
  return (
    <div style={{ overflow: 'auto', padding: '4px 2px 0' }}>
      <span className="hf-pill" style={{ height: 24, marginBottom: 12 }}>
        5 个模板 · 默认素白单栏(纯净无色)
      </span>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 12 }}>
        {TEMPLATES.map(([t, i]) => (
          <button
            key={i}
            onClick={() => setSel(i)}
            style={{
              textAlign: 'left',
              borderRadius: 10,
              padding: 7,
              cursor: 'pointer',
              background: sel === i ? 'var(--terracotta-wash)' : 'var(--ivory)',
              boxShadow: sel === i ? '0 0 0 1.5px var(--terracotta)' : '0 0 0 1px var(--border-warm)',
            }}
          >
            <div
              style={{
                height: 86,
                borderRadius: 5,
                background: '#fff',
                boxShadow: '0 0 0 1px var(--border-warm)',
                padding: 7,
                marginBottom: 7,
                overflow: 'hidden',
              }}
            >
              {mini(i)}
            </div>
            <div
              style={{
                font: `${sel === i ? 600 : 500} 11px var(--font-sans)`,
                color: sel === i ? 'var(--terracotta-strong)' : 'var(--olive)',
                textAlign: 'center',
              }}
            >
              {t}
            </div>
          </button>
        ))}
        <div
          style={{
            borderRadius: 10,
            boxShadow: '0 0 0 1px var(--border-strong)',
            borderStyle: 'dashed',
            display: 'grid',
            placeItems: 'center',
            font: '500 10.5px/1.4 var(--font-sans)',
            color: 'var(--stone)',
            textAlign: 'center',
            padding: 6,
          }}
        >
          全无照片 · 金融极简
        </div>
      </div>
    </div>
  );
}
