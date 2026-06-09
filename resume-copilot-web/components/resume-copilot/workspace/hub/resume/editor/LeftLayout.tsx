'use client';
import { useState } from 'react';
import { Check } from 'lucide-react';

const MODULES = ['基本信息', '个人介绍', '教育经历', '实习经历', '项目经历', '掌握技能'];
const SLIDERS: [string, number][] = [
  ['字号', 0.5],
  ['行高', 0.62],
  ['页边距', 0.4],
  ['模块间距', 0.55],
];

/** 左栏「布局」tab — 排版滑块 + 模块显示/隐藏 + 超页提醒。 */
export function LeftLayout() {
  const [values, setValues] = useState<number[]>(SLIDERS.map(([, v]) => v));
  const [hidden, setHidden] = useState<Set<string>>(() => new Set(['个人介绍']));

  const toggle = (m: string) =>
    setHidden((s) => {
      const n = new Set(s);
      if (n.has(m)) n.delete(m);
      else n.add(m);
      return n;
    });

  const setValue = (i: number, v: number) =>
    setValues((arr) => arr.map((cur, idx) => (idx === i ? v : cur)));

  return (
    <div style={{ overflow: 'auto', padding: '4px 2px 0' }}>
      {/* 超页提醒 */}
      <div
        style={{
          display: 'flex',
          gap: 9,
          alignItems: 'flex-start',
          background: 'var(--amber-bg)',
          boxShadow: '0 0 0 1px #ecdfa4',
          borderRadius: 11,
          padding: 11,
          marginBottom: 14,
        }}
      >
        <span
          style={{
            font: '600 11px var(--font-mono)',
            color: 'var(--amber-fg)',
            boxShadow: '0 0 0 1px #ecdfa4',
            borderRadius: 6,
            padding: '2px 7px',
            background: 'var(--ivory)',
            flex: 'none',
          }}
        >
          2 页
        </span>
        <div style={{ font: '400 11px/1.5 var(--font-sans)', color: 'var(--amber-fg)' }}>
          当前超过 1 页 · 仅提醒,不自动缩排。下调字号或页边距,或隐藏次要模块。
        </div>
      </div>

      <span className="hf-pill" style={{ height: 24, marginBottom: 12 }}>
        排版滑块
      </span>
      <div style={{ marginTop: 12 }}>
        {SLIDERS.map(([l], i) => {
          const v = values[i];
          return (
            <div key={i} style={{ marginBottom: 14 }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  font: '500 11.5px var(--font-sans)',
                  color: 'var(--ink-soft)',
                  marginBottom: 7,
                }}
              >
                <span>{l}</span>
              </div>
              <div style={{ position: 'relative', height: 14 }}>
                <div
                  style={{
                    position: 'absolute',
                    top: 5,
                    left: 0,
                    right: 0,
                    height: 4,
                    background: 'var(--library-rail)',
                    borderRadius: 999,
                    boxShadow: '0 0 0 1px var(--border-warm)',
                  }}
                />
                <div
                  style={{
                    position: 'absolute',
                    left: 0,
                    top: 5,
                    height: 4,
                    width: `${v * 100}%`,
                    background: 'var(--terracotta)',
                    borderRadius: 999,
                  }}
                />
                <div
                  style={{
                    position: 'absolute',
                    left: `calc(${v * 100}% - 7px)`,
                    top: 0,
                    width: 14,
                    height: 14,
                    borderRadius: 999,
                    background: '#fff',
                    boxShadow: '0 0 0 1.5px var(--terracotta), 0 1px 3px rgba(0,0,0,0.15)',
                    pointerEvents: 'none',
                  }}
                />
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.01}
                  value={v}
                  onChange={(e) => setValue(i, Number(e.target.value))}
                  aria-label={l}
                  style={{
                    position: 'absolute',
                    inset: 0,
                    width: '100%',
                    margin: 0,
                    opacity: 0,
                    cursor: 'pointer',
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      <span className="hf-pill" style={{ height: 24, margin: '6px 0 10px' }}>
        模块显示 / 隐藏
      </span>
      <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 3 }}>
        {MODULES.map((m, i) => {
          const off = hidden.has(m);
          return (
            <button
              key={i}
              onClick={() => toggle(m)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '7px 6px',
                borderRadius: 8,
                cursor: 'pointer',
                background: 'transparent',
                textAlign: 'left',
              }}
            >
              <span
                style={{
                  width: 16,
                  height: 16,
                  flex: 'none',
                  borderRadius: 5,
                  display: 'grid',
                  placeItems: 'center',
                  color: '#fff',
                  background: off ? 'var(--ivory)' : 'var(--terracotta)',
                  boxShadow: off ? '0 0 0 1.5px var(--border-strong)' : '0 0 0 1px var(--terracotta)',
                }}
              >
                {!off && <Check size={11} />}
              </span>
              <span style={{ font: '500 12px var(--font-sans)', color: off ? 'var(--stone)' : 'var(--ink-soft)' }}>{m}</span>
              {off && (
                <span style={{ marginLeft: 'auto', font: '400 10px var(--font-sans)', color: 'var(--stone)' }}>已隐藏</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
