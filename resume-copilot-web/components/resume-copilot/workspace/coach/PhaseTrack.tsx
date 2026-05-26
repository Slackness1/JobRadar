'use client';

/**
 * PhaseTrack — 小型 B-1/B-2/B-3/B-4 阶段胶囊 (CoachPane ribbon header 右上).
 *
 * 设计参考 `hifi-ws-coach.jsx::HFPhaseTrack`.
 *
 * - 4 个胶囊水平排列, 16x2 连接线.
 * - active 节点 = terracotta 实心 + 白字 (step 编号), 带 box-shadow halo.
 * - done 节点 = terracotta-wash 底色, ✓ 字.
 * - pending = warm-sand 底, stone 灰字 (B-N).
 * - 尾部 mono 字 "step/total".
 */

export interface PhaseTrackProps {
  /** 当前 step (1..total). 0 = 都没开始. */
  step: number;
  total?: number;
}

export function PhaseTrack({ step, total = 4 }: PhaseTrackProps) {
  const labels = ['B-1', 'B-2', 'B-3', 'B-4'].slice(0, total);
  return (
    <div className="workspace-hifi__phase-track" aria-label={`phase ${step}/${total}`}>
      {labels.map((p, i) => {
        const idx = i + 1;
        const state =
          idx < step ? 'done' : idx === step ? 'active' : 'pending';
        return (
          <span
            key={p}
            className="workspace-hifi__phase-track-cell"
          >
            {i > 0 && (
              <span
                className={`workspace-hifi__phase-track-line${
                  idx <= step ? ' is-on' : ''
                }`}
                aria-hidden
              />
            )}
            <span className={`workspace-hifi__phase-track-pill workspace-hifi__phase-track-pill--${state}`}>
              {state === 'done' ? '✓' : p}
            </span>
          </span>
        );
      })}
      <span className="workspace-hifi__phase-track-count">
        {Math.min(step, total)}/{total}
      </span>
    </div>
  );
}
