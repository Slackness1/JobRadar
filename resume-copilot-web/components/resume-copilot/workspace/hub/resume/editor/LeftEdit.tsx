'use client';
import { ChevronDown, Quote } from 'lucide-react';

const MODULES = ['基本信息', '个人介绍', '教育经历', '实习经历', '项目经历', '掌握技能'];

const INTERN = {
  key: 'intern',
  head: '九坤投资 · 量化研究实习',
  bullets: ['协助搭建多因子回测框架,参与日频数据清洗与对齐', '负责单因子有效性检验,整理因子库文档'],
};

/** 左栏「简历编辑」tab — 就地编辑分模块。每段头有「引用此段」按钮调 onQuote。 */
export function LeftEdit({ onQuote }: { onQuote: (k: string) => void }) {
  return (
    <div style={{ overflow: 'auto', padding: '4px 2px 0' }}>
      <span className="hf-pill" style={{ height: 24, marginBottom: 10, whiteSpace: 'nowrap' }}>
        就地编辑 · 分模块
      </span>
      <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {/* 展开的 实习经历 */}
        <div style={{ borderRadius: 12, background: 'var(--ivory)', boxShadow: '0 0 0 1px var(--terracotta-ring)', padding: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 9 }}>
            <span style={{ font: '600 12.5px var(--font-sans)', color: 'var(--ink)', whiteSpace: 'nowrap' }}>
              实习经历 · 就地编辑
            </span>
            <span style={{ marginLeft: 'auto', color: 'var(--stone)', display: 'inline-flex' }}>
              <ChevronDown size={13} />
            </span>
          </div>
          <div style={{ font: '600 11.5px var(--font-sans)', color: 'var(--ink-soft)', marginBottom: 8 }}>{INTERN.head}</div>
          {INTERN.bullets.map((b, i) => (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 8,
                padding: '8px 0',
                borderTop: '1px solid var(--border-cream)',
              }}
            >
              <span style={{ color: 'var(--warm-silver)', fontSize: 12, lineHeight: '16px' }}>•</span>
              <div style={{ flex: 1, font: '400 11px/1.55 var(--font-sans)', color: 'var(--ink-soft)' }}>{b}</div>
              <button
                onClick={() => onQuote(INTERN.key)}
                style={{
                  flex: 'none',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  font: '500 10px var(--font-sans)',
                  color: 'var(--terracotta-strong)',
                  background: 'var(--terracotta-wash)',
                  boxShadow: '0 0 0 1px #eccfb6',
                  borderRadius: 7,
                  padding: '3px 7px',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                }}
              >
                <Quote size={11} /> 引用此段
              </button>
            </div>
          ))}
        </div>
        {/* 其余模块折叠条 */}
        {MODULES.filter((m) => m !== '实习经历').map((m, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              alignItems: 'center',
              borderRadius: 10,
              background: 'var(--ivory)',
              boxShadow: '0 0 0 1px var(--border-warm)',
              padding: '10px 12px',
              cursor: 'pointer',
            }}
          >
            <span style={{ font: '500 12px var(--font-sans)', color: 'var(--ink-soft)' }}>{m}</span>
            <span style={{ marginLeft: 'auto', color: 'var(--warm-silver)', display: 'inline-flex' }}>
              <ChevronDown size={13} />
            </span>
          </div>
        ))}
        <div
          style={{
            borderRadius: 10,
            boxShadow: '0 0 0 1px var(--border-strong)',
            borderStyle: 'dashed',
            padding: '10px',
            font: '500 12px var(--font-sans)',
            color: 'var(--stone)',
            textAlign: 'center',
          }}
        >
          + 自定义模块(证书 / 社团 / 作品…)
        </div>
      </div>
    </div>
  );
}
