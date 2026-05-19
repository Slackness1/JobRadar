'use client';

/**
 * PlanProgressBar — plan-mode 4 anchor 进度条 (B-3 / B-4).
 *
 * Phase 2 FE-4 (2026-05-20).
 *
 * 设计意图 (per main-workspace-redesign-2026-05-20 §2 B-3):
 *   plan turn 响应里的 AI 反问 + 4 anchor 进度,FE 在 composer 上方
 *   显示 `时间 ✓ 行动 ✓ 工具 ○ 结果 ○`,4 anchor 全 ✓ → 父自动 finalize.
 *
 * 4 anchor 是 STAR 风格简化:
 *   - 时间 (situation):映射 BE 的 `duration` evidence tag
 *   - 行动 (action):  `verb_subject` 或 `role`
 *   - 工具 (means):  `tool` 或 `tech`
 *   - 结果 (result):  `outcome` 或 `metric`
 *
 * 派生方法:
 *   - 给定当前 active PlanItem (current_item_id 对应那条),把它的
 *     `evidence[].tags[].type` 收集成 Set,然后映射 → 4 个 anchor 是否 ✓。
 *   - 若 plan 没有 active item / item 没 evidence → 4 个全 ○。
 *
 * 父用法:
 *   ```tsx
 *   import { derivePlanAnchors, PlanProgressBar } from './chat/PlanProgressBar';
 *   const anchors = derivePlanAnchors(planState);
 *   <PlanProgressBar anchors={anchors} />
 *   ```
 *   父可以 `useEffect(() => { if (anchors.allFilled) finalize(); })`.
 *
 * 设计系统:
 *   - 所有样式 scope `.workspace-hifi`
 */

import type { PlanItemWire, PlanStateOut } from '../../api';

export type AnchorKey = 'situation' | 'action' | 'tool' | 'result';

export const ANCHOR_LABELS: Record<AnchorKey, string> = {
  situation: '时间',
  action: '行动',
  tool: '工具',
  result: '结果',
};

// EvidenceTagType (BE) → 4 anchor 映射
const TAG_TO_ANCHOR: Record<string, AnchorKey> = {
  duration: 'situation',
  scope: 'situation',
  role: 'action',
  verb_subject: 'action',
  tool: 'tool',
  tech: 'tool',
  outcome: 'result',
  metric: 'result',
};

export interface AnchorState {
  filled: Record<AnchorKey, boolean>;
  /** true 当 4 个 anchor 全部 ✓ — 父可据此自动 finalize。 */
  allFilled: boolean;
  /** active item id;父调 finalize 时需要 */
  activeItemId: string | null;
  /** plan version, 给 finalize 做乐观锁 */
  expectedVersion: number;
}

export function emptyAnchorState(): AnchorState {
  return {
    filled: { situation: false, action: false, tool: false, result: false },
    allFilled: false,
    activeItemId: null,
    expectedVersion: 0,
  };
}

function activeItem(plan: PlanStateOut | null): PlanItemWire | null {
  if (!plan) return null;
  const id = plan.current_item_id;
  if (!id) {
    // fallback: 找 status=clarifying / drafting / awaiting_review 的第一项
    const inProgress = plan.items.find((it) =>
      ['clarifying', 'drafting', 'ready_to_write', 'awaiting_review'].includes(
        String(it.status),
      ),
    );
    return inProgress ?? null;
  }
  return plan.items.find((it) => it.id === id) ?? null;
}

export function derivePlanAnchors(plan: PlanStateOut | null): AnchorState {
  if (!plan) return emptyAnchorState();
  const item = activeItem(plan);
  const filled: Record<AnchorKey, boolean> = {
    situation: false,
    action: false,
    tool: false,
    result: false,
  };
  if (item) {
    for (const ev of item.evidence ?? []) {
      for (const tag of ev.tags ?? []) {
        const anchor = TAG_TO_ANCHOR[String(tag.type)];
        if (anchor) filled[anchor] = true;
      }
    }
    // Drafts that already exist also count as a "result" being assembled.
    if (item.draft?.text) {
      filled.result = filled.result || true;
    }
  }
  const allFilled = Object.values(filled).every(Boolean);
  return {
    filled,
    allFilled,
    activeItemId: item?.id ?? null,
    expectedVersion: plan.version,
  };
}

export interface PlanProgressBarProps {
  anchors: AnchorState;
  /** 学生点单个 anchor — 暂时只展示 tooltip,不做交互。 */
  onAnchorClick?: (anchor: AnchorKey) => void;
}

export function PlanProgressBar({ anchors, onAnchorClick }: PlanProgressBarProps) {
  const order: AnchorKey[] = ['situation', 'action', 'tool', 'result'];
  return (
    <div
      className={`workspace-hifi__plan-progress${anchors.allFilled ? ' is-complete' : ''}`}
      role="group"
      aria-label="plan-mode 4 anchor 进度"
    >
      {order.map((k) => {
        const done = anchors.filled[k];
        return (
          <button
            key={k}
            type="button"
            className={`workspace-hifi__plan-progress-step${done ? ' is-done' : ''}`}
            onClick={onAnchorClick ? () => onAnchorClick(k) : undefined}
            disabled={!onAnchorClick}
            title={done ? `${ANCHOR_LABELS[k]} 已补齐` : `${ANCHOR_LABELS[k]} 待补充`}
          >
            <span className="workspace-hifi__plan-progress-mark" aria-hidden>
              {done ? '✓' : '○'}
            </span>
            <span className="workspace-hifi__plan-progress-label">
              {ANCHOR_LABELS[k]}
            </span>
          </button>
        );
      })}
      {anchors.allFilled && (
        <span className="workspace-hifi__plan-progress-hint">
          4 个 anchor 已齐 — 自动收尾中…
        </span>
      )}
    </div>
  );
}
