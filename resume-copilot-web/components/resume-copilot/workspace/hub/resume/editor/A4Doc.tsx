'use client';
import type { CSSProperties } from 'react';

/** 一段简历内容。普通段用 `lines` 渲染灰条占位;被点亮(AI 刚写回)的段用 `bullet` 渲染真实文本。 */
export interface EditorSection {
  title: string;
  /** 灰条占位宽度数组(数字=px,字符串=百分比)。 */
  lines?: (string | number)[];
  /** 真实 bullet 文本(点亮段用)。 */
  bullet?: string;
}

const grayLine = (w: number | string, i: number) => (
  <div
    key={i}
    style={{ width: w, height: 4.5, background: 'var(--border-warm)', borderRadius: 3, marginBottom: 6 }}
  />
);

/**
 * WYSIWYG A4 文档 — 移植自 hub-prototype A4Doc。
 * `lit` = 要高亮("AI 刚写回")的段索引:terracotta-wash 底 + ring。
 */
export function A4Doc({ sections, lit }: { sections: EditorSection[]; lit?: number }) {
  const wrap: CSSProperties = {
    background: '#fff',
    width: 480,
    padding: '40px 46px',
    boxSizing: 'border-box',
    borderRadius: 4,
    boxShadow: '0 0 0 1px var(--border-warm), 0 16px 44px rgba(0,0,0,0.10)',
  };
  return (
    <div style={wrap}>
      <div style={{ borderBottom: '2px solid var(--ink)', paddingBottom: 14, marginBottom: 18 }}>
        <div
          style={{ font: '600 26px/1 var(--font-sans)', color: 'var(--ink)', marginBottom: 10, letterSpacing: '-0.01em' }}
        >
          陈一帆
        </div>
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', font: '400 11px var(--font-sans)', color: 'var(--olive)' }}>
          {['上海 · 可立即到岗', '178-0000-0000', 'chenyf@fudan.edu.cn'].map((c, i) => (
            <span key={i} style={{ whiteSpace: 'nowrap' }}>
              {c}
            </span>
          ))}
        </div>
      </div>
      {sections.map((s, idx) => {
        const on = lit === idx;
        return (
          <div
            key={idx}
            style={{
              background: on ? 'var(--terracotta-wash)' : 'transparent',
              borderRadius: on ? 8 : 0,
              margin: on ? '0 -12px 20px' : '0 0 20px',
              padding: on ? '11px 12px' : 0,
              boxShadow: on ? '0 0 0 1.5px var(--terracotta)' : 'none',
              transition: 'box-shadow .2s',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 9 }}>
              <span style={{ font: '600 12px/1 var(--font-sans)', color: 'var(--ink-soft)', letterSpacing: '0.06em' }}>
                {s.title}
              </span>
              <span style={{ flex: 1, height: 1, background: 'var(--border-warm)' }} />
              {on && (
                <span
                  style={{
                    font: '600 9px var(--font-sans)',
                    color: '#fff',
                    background: 'var(--terracotta)',
                    borderRadius: 999,
                    padding: '2px 8px',
                  }}
                >
                  AI 刚写回
                </span>
              )}
            </div>
            {on && s.bullet ? (
              <div style={{ display: 'flex', gap: 7, font: '400 11.5px/1.6 var(--font-sans)', color: 'var(--ink-soft)' }}>
                <span style={{ color: 'var(--stone)', flex: 'none' }}>•</span>
                <span>{s.bullet}</span>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {(s.lines ?? ['100%', '100%', '64%']).map((w, i) => grayLine(w, i))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
