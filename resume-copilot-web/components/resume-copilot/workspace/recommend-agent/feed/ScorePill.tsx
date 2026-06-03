'use client';

/**
 * ScorePill — 岗位卡上的分数胶囊 (Phase G 子项④ 流动 feed).
 *
 *   kind="base"     → 暖砂底 Base 分,始终展示(规则分).
 *   kind="enhanced" → terracotta 实底 Enhanced 分,深挖后(used_ai=true)才出.
 *   kind="pending"  → 虚线占位「—」,未深挖时(used_ai 假)的 Enhanced 占位.
 *
 * 纯展示组件,无 state;样式全 scope 在 recommend-agent.css。
 */

export interface ScorePillProps {
  kind: 'base' | 'enhanced' | 'pending';
  value?: number | null;
}

export function ScorePill({ kind, value }: ScorePillProps) {
  if (kind === 'base') {
    return (
      <span className="recommend-feed__pill recommend-feed__pill--base">
        <span className="recommend-feed__pill-label">Base</span>
        {value ?? '—'}
      </span>
    );
  }
  if (kind === 'enhanced') {
    return (
      <span className="recommend-feed__pill recommend-feed__pill--enh">
        <span className="recommend-feed__pill-label">Enhanced</span>
        {value ?? '—'}
      </span>
    );
  }
  return (
    <span className="recommend-feed__pill recommend-feed__pill--pending">
      <span className="recommend-feed__pill-label">Enhanced</span>—
    </span>
  );
}
