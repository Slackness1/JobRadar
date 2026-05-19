'use client';

/**
 * TopTrackBar — 顶部赛道 sticky bar (E-5).
 *
 * 当前 placeholder 数据 (score "6.2/10" + track name) — 真实接入算法属 P2-1,
 * 此 commit (FE-1) 只搭骨架。
 *
 * Props 接口稳定:FE-2/3/4 / 后续 P2-1 算法接入只填值,不动签名。
 */

import { HFBtn, I } from '@/components/hifi/hifi-primitives';

export interface TopTrackBarProps {
  /** 当前选中的赛道名,例如 "公募行研·买方基本面"。null = 尚未选定 */
  trackName: string | null;
  /** 适配度评分 0-10。null = 尚未计算(P2-1 之前都是 placeholder) */
  fitScore: number | null;
  /** 用户点 "[换赛道]" 时回调 */
  onChangeTrack?: () => void;
}

export function TopTrackBar({ trackName, fitScore, onChangeTrack }: TopTrackBarProps) {
  const displayTrack = trackName ?? '尚未选定赛道';
  const scoreLabel = fitScore != null ? fitScore.toFixed(1) : '--';

  return (
    <div className="workspace-hifi__top-bar" data-testid="workspace-top-bar">
      <span className="workspace-hifi__top-bar-target">
        <span className="workspace-hifi__top-bar-target-icon" aria-hidden>
          {I.radar(14)}
        </span>
        <span>当前赛道:</span>
        <strong style={{ fontWeight: 600, color: 'var(--ink)' }}>{displayTrack}</strong>
      </span>
      <span className="workspace-hifi__top-bar-divider" aria-hidden />
      <span className="workspace-hifi__top-bar-score">
        <span>适配度</span>
        <span className="workspace-hifi__top-bar-score-value">{scoreLabel}</span>
        <span style={{ color: 'var(--stone)' }}>/10</span>
      </span>
      <div className="workspace-hifi__top-bar-actions">
        <HFBtn variant="ghost" size="sm" onClick={onChangeTrack}>
          换赛道
        </HFBtn>
      </div>
    </div>
  );
}
