'use client';

/**
 * StarStepper — 横向 S / T / A / R 4 节点 stepper (P1 CoachPane).
 *
 * 设计参考 `hifi-ws-coach.jsx::HFStarStepper`.
 *
 * 状态 (per step):
 *   - done    → terracotta 实心圆 + 白 ✓
 *   - active  → 白底 + terra border + box-shadow + rc-pulsering 扩散环
 *   - pending → warm-sand + warm-silver 字, 整段 opacity 0.55
 *
 * Plan-mode 的 `derivePlanAnchors` 返 4 个 anchor (situation/action/tool/result).
 * P1 把它们映射到 S=situation T=tool A=action R=result 显示 — 与设计 S/T/A/R 顺
 * 序一致, 学生看到的 label 就是 "Situation 背景 / Task 任务 / Action 动作 /
 * Result 结果"。
 */

import type { AnchorState } from '../chat/PlanProgressBar';

export type StarLetter = 'S' | 'T' | 'A' | 'R';
export type StarState = 'done' | 'active' | 'pending';

export interface StarStepperStep {
  letter: StarLetter;
  label: string;
  summary?: string;
  state: StarState;
}

const STAR_DEFAULTS: { letter: StarLetter; label: string }[] = [
  { letter: 'S', label: 'Situation 背景' },
  { letter: 'T', label: 'Task 任务' },
  { letter: 'A', label: 'Action 动作' },
  { letter: 'R', label: 'Result 结果' },
];

/** Convert plan-mode anchor state → 4 StarStepperStep entries.
 *
 *  Mapping: S = situation · T = tool · A = action · R = result.
 *  The "active" step is the first un-filled one (first pending after the last
 *  done); if all filled → no active, all done; if none filled → S active. */
export function starStepsFromAnchors(
  anchors: AnchorState,
  summaries?: Partial<Record<StarLetter, string>>,
): StarStepperStep[] {
  const order: StarLetter[] = ['S', 'T', 'A', 'R'];
  const anchorKey = {
    S: 'situation' as const,
    T: 'tool' as const,
    A: 'action' as const,
    R: 'result' as const,
  };
  const filled = order.map((l) => Boolean(anchors.filled[anchorKey[l]]));
  // First false index → active (S/T/A/R sequential). If all true → no active.
  const firstFalse = filled.findIndex((f) => !f);

  return STAR_DEFAULTS.map((d, i) => {
    let state: StarState;
    if (filled[i]) state = 'done';
    else if (i === firstFalse) state = 'active';
    else state = 'pending';
    return {
      letter: d.letter,
      label: d.label,
      summary: summaries?.[d.letter],
      state,
    };
  });
}

export interface StarStepperProps {
  steps: StarStepperStep[];
}

export function StarStepper({ steps }: StarStepperProps) {
  return (
    <div
      className="workspace-hifi__star-stepper"
      role="list"
      aria-label="STAR 4 anchor 拆解进度"
    >
      {steps.map((s, i) => (
        <div
          key={s.letter}
          className={`workspace-hifi__star-step workspace-hifi__star-step--${s.state}`}
          role="listitem"
        >
          <div className="workspace-hifi__star-step-inner">
            <span className="workspace-hifi__star-node" aria-hidden>
              {s.state === 'done' ? '✓' : s.letter}
              {s.state === 'active' && (
                <span className="workspace-hifi__star-node-ring" aria-hidden />
              )}
            </span>
            <div className="workspace-hifi__star-step-text">
              <div className="workspace-hifi__star-step-head">
                <span className="workspace-hifi__star-step-label">{s.label}</span>
                {s.state === 'active' && (
                  <span className="workspace-hifi__star-step-active-tag">正在拆</span>
                )}
              </div>
              <span className="workspace-hifi__star-step-summary">
                {s.summary || '—'}
              </span>
            </div>
          </div>
          {i < steps.length - 1 && (
            <div className="workspace-hifi__star-step-sep" aria-hidden />
          )}
        </div>
      ))}
    </div>
  );
}
