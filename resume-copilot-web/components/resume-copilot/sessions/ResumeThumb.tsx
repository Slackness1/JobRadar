'use client';

/**
 * ResumeThumb — mini resume preview used by SessionCard.
 *
 * Stylistically a faked "paper" — 顶部姓名 + tag,3 段标记栏 (实习经历 / 教育背景 /
 * 技能),用色块假装 bullet。不是真简历内容渲染,只是给 SessionCard 一个视觉锚。
 *
 * Pure presentational; no data fetch.
 */

import type { CSSProperties } from 'react';

interface ResumeThumbProps {
  /** Top-right gradient accent color (cardCoverColor — falls back to wash) */
  accentColor?: string;
  /** Display name in header (default "我的简历") */
  name?: string;
  /** Small tag under the name, e.g. "MF" / "投行 v2" */
  tag?: string;
  /** 2026-05-29: 真实简历段落 (来自列表接口的 thumb_sections)。给了就按真实段落
   *  + 条数渲染, 让缩略图反映这份简历的实际结构; 没给/空数组则回退占位骨架。 */
  sections?: Array<{ label: string; bullets: number }>;
}

const PLACEHOLDER_SECTIONS: Array<{ label: string; bullets: number }> = [
  { label: '实习经历', bullets: 4 },
  { label: '教育背景', bullets: 2 },
  { label: '技能', bullets: 2 },
];

// Deterministic bullet widths — keeps the visual stable across re-renders
// and matches the original HiFi source. The `_sectionIdx` arg is kept for
// callsite symmetry / future variation; current formula only varies by bullet.
function bulletWidth(_sectionIdx: number, bulletIdx: number): string {
  const pct = ((bulletIdx * 17 + 60) % 95) + 5;
  return `${pct}%`;
}

export function ResumeThumb({
  accentColor = '#fdebe2',
  name = '我的简历',
  tag = 'JobRadar',
  sections: realSections,
}: ResumeThumbProps) {
  const sections =
    realSections && realSections.length > 0 ? realSections : PLACEHOLDER_SECTIONS;

  const cornerStyle: CSSProperties = {
    background: `linear-gradient(225deg, ${accentColor}, transparent 70%)`,
  };

  return (
    <div className="rc-sessions__thumb">
      <div className="rc-sessions__thumb-header">
        <div className="rc-sessions__thumb-name">{name}</div>
        <div className="rc-sessions__thumb-tag">{tag} · 上海</div>
      </div>
      {sections.map((sec, sIdx) => (
        <div key={sec.label} className="rc-sessions__thumb-section">
          <div className="rc-sessions__thumb-section-label">{sec.label}</div>
          <div className="rc-sessions__thumb-bullet-list">
            {Array.from({ length: sec.bullets }).map((_, bIdx) => (
              <div key={bIdx} className="rc-sessions__thumb-bullet">
                <span className="rc-sessions__thumb-bullet-dot" aria-hidden />
                <div
                  className="rc-sessions__thumb-bullet-line"
                  style={{ width: bulletWidth(sIdx, bIdx), maxWidth: bulletWidth(sIdx, bIdx) }}
                />
              </div>
            ))}
          </div>
        </div>
      ))}
      <div className="rc-sessions__thumb-corner" style={cornerStyle} aria-hidden />
    </div>
  );
}
