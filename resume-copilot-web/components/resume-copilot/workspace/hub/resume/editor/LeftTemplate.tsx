'use client';
import type { JSX } from 'react';
import { TEMPLATES } from './resumeSample';

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

export interface LeftTemplateProps {
  /** 当前选中模板 id。 */
  value: string;
  /** 切换模板 → 中栏实时换皮。 */
  onChange: (id: string) => void;
}

/** 左栏「模板」tab — 5 个模板 mini-card 选择,受控驱动中栏换皮。 */
export function LeftTemplate({ value, onChange }: LeftTemplateProps) {
  return (
    <div style={{ overflow: 'auto', padding: '4px 2px 18px' }}>
      <span className="hf-pill" style={{ height: 24, marginBottom: 12 }}>
        5 个模板 · 默认素白单栏(纯净无色)
      </span>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 12 }}>
        {TEMPLATES.map((tpl, i) => {
          const on = value === tpl.id;
          return (
          <button
            key={tpl.id}
            onClick={() => onChange(tpl.id)}
            style={{
              textAlign: 'left',
              borderRadius: 10,
              padding: 7,
              cursor: 'pointer',
              background: on ? 'var(--terracotta-wash)' : 'var(--ivory)',
              boxShadow: on ? '0 0 0 1.5px var(--terracotta)' : '0 0 0 1px var(--border-warm)',
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
                font: `${on ? 600 : 500} 11px var(--font-sans)`,
                color: on ? 'var(--terracotta-strong)' : 'var(--olive)',
                textAlign: 'center',
              }}
            >
              {tpl.name}
            </div>
          </button>
          );
        })}
      </div>
    </div>
  );
}
