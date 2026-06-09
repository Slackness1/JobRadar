'use client';

/**
 * SkillBar — composer 上方的 3 个技能 chip(职位推荐 / 梯队骨架 / 简历优化).
 *
 * 铁律(来自用户明确反馈): 点 chip 只「激活」(高亮), **不**跑技能.
 * 选中态 = terracotta 实心填充; 未选 = ivory + warm border.
 * 单色描边图标, 唯一彩色是调色板里的 terracotta.
 *
 * Token: 全部取自 `.hf`(HubShell 已 className="hf").
 */

import type { HubModule } from './hub-types';

interface ChipDef {
  key: HubModule;
  label: string;
  icon: React.ReactNode;
}

const CHIPS: ChipDef[] = [
  {
    key: 'feed',
    label: '职位推荐',
    icon: (
      <svg
        width="13"
        height="13"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="9" />
        <circle cx="12" cy="12" r="5" />
        <circle cx="12" cy="12" r="1" />
      </svg>
    ),
  },
  {
    key: 'skeleton',
    label: '梯队骨架',
    icon: (
      <svg
        width="13"
        height="13"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M12 3l9 5-9 5-9-5 9-5z" />
        <path d="M3 13l9 5 9-5" />
      </svg>
    ),
  },
  {
    key: 'resume',
    label: '简历优化',
    icon: (
      <svg
        width="13"
        height="13"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6" />
        <path d="M8 13h8M8 17h5" />
      </svg>
    ),
  },
];

export interface SkillBarProps {
  active: HubModule | null;
  onPick: (key: HubModule) => void;
}

export default function SkillBar({ active, onPick }: SkillBarProps) {
  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      {CHIPS.map((c) => {
        const on = active === c.key;
        return (
          <button
            key={c.key}
            type="button"
            onClick={() => onPick(c.key)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              height: 32,
              padding: '0 13px',
              borderRadius: 999,
              cursor: 'pointer',
              font: `${on ? 600 : 500} 12.5px var(--font-sans)`,
              background: on ? 'var(--terracotta)' : 'var(--ivory)',
              color: on ? 'var(--ivory)' : 'var(--ink-soft)',
              boxShadow: on ? '0 0 0 1px var(--terracotta)' : '0 0 0 1px var(--border-warm)',
              transition: 'background .14s, box-shadow .14s, color .14s',
            }}
          >
            {c.icon}
            {c.label}
          </button>
        );
      })}
    </div>
  );
}
