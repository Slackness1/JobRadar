'use client';
import type { CSSProperties } from 'react';

const grayLine = (w: number | string, mb = 6) => (
  <div style={{ width: w, height: 4.5, background: 'var(--border-warm)', borderRadius: 3, marginBottom: mb }} />
);

/** A4 预览 — 移植自 hub-prototype ResumeA4(本期占位灰条 + highlight 段;真实 profile 渲染留编辑器期)。 */
export function ResumeA4({ highlight = false, name = '陈一帆' }: { highlight?: boolean; name?: string }) {
  const secs = ['教育经历', '实习经历', '项目经历', '掌握技能'];
  const wrap: CSSProperties = {
    background: '#fff', width: 322, padding: '24px 28px', boxSizing: 'border-box', borderRadius: 4,
    margin: '0 auto', boxShadow: '0 0 0 1px var(--border-warm), 0 12px 32px rgba(0,0,0,0.09)',
  };
  return (
    <div style={wrap}>
      <div style={{ borderBottom: '2px solid var(--ink)', paddingBottom: 10, marginBottom: 12 }}>
        <div style={{ font: '600 18px/1 var(--font-sans)', color: 'var(--ink)', marginBottom: 8 }}>{name}</div>
        <div style={{ display: 'flex', gap: 12 }}>{grayLine(58, 0)}{grayLine(72, 0)}{grayLine(46, 0)}</div>
      </div>
      {secs.map((s, i) => {
        const lit = highlight && i === 1;
        return (
          <div key={i} style={{
            background: lit ? 'var(--terracotta-wash)' : 'transparent', borderRadius: lit ? 7 : 0,
            margin: lit ? '0 -10px 14px' : '0 0 14px', padding: lit ? '8px 10px' : 0,
            boxShadow: lit ? '0 0 0 1.5px var(--terracotta)' : 'none',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <span style={{ font: '600 11px/1 var(--font-sans)', color: 'var(--ink-soft)', letterSpacing: '0.04em' }}>{s}</span>
              {lit && <span style={{ font: '600 9px var(--font-sans)', color: '#fff', background: 'var(--terracotta)', borderRadius: 999, padding: '2px 8px', marginLeft: 'auto' }}>AI 刚写回</span>}
            </div>
            {lit
              ? <div style={{ font: '400 10px/1.6 var(--font-sans)', color: 'var(--ink-soft)' }}>搭建覆盖 <b>40+ 量价因子</b>的回测框架(<b>2021–2023</b>),将单因子筛选由手动改为一键批量,显著缩短迭代周期。</div>
              : [...Array(i === 3 ? 2 : 3)].map((_, j, a) => grayLine(j === a.length - 1 ? (i === 2 ? '74%' : '56%') : '100%', 5))}
          </div>
        );
      })}
    </div>
  );
}
