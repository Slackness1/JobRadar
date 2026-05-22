'use client';

/**
 * PlanProgressBar — plan-mode 4 anchor 进度条 (B-3 / B-4).
 *
 * Phase 2 FE-4 (2026-05-20).
 *
 * 设计意图 (per main-workspace-redesign-2026-05-20 §2 B-3):
 *   plan turn 响应里的 AI 反问 + 4 anchor 进度,FE 在 composer 上方
 *   显示 `时间 ✓ 行动 ✓ 工具 ○ 结果 ○`,让学生知道这一轮 coach 还差什么。
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
 *   写作/收尾由后端 plan state 决定;这个组件只负责展示进度。
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

// User-facing tooltip for each anchor — hover shows what AI will ask.
export const ANCHOR_HINTS: Record<AnchorKey, string> = {
  situation: '什么时候做的 / 项目持续多久(让经历可考证)',
  action: '你具体做了什么 / 角色是什么(动词 + 主语)',
  tool: '用了什么方法 / 工具 / 模型 / 框架',
  result: '产出是什么 / 量化指标 / 业务影响',
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
  /** true 当 4 个 anchor 全部 ✓。 */
  allFilled: boolean;
  /** active item id. */
  activeItemId: string | null;
  /** user-visible title of the item currently being coached. */
  activeItemTitle: string | null;
  /** plan version. */
  expectedVersion: number;
}

export function emptyAnchorState(): AnchorState {
  return {
    filled: { situation: false, action: false, tool: false, result: false },
    allFilled: false,
    activeItemId: null,
    activeItemTitle: null,
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
      // Parsed resume evidence is useful context for the AI, but it made this
      // progress row look half-complete before the student had actually
      // answered anything. Show only what the coach conversation collected.
      if (String(ev.source) !== 'user_clarification') continue;
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
    activeItemTitle: item?.title ?? null,
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
  const doneCount = order.filter((k) => anchors.filled[k]).length;
  return (
    <div
      className={`workspace-hifi__plan-progress${anchors.allFilled ? ' is-complete' : ''}`}
      role="group"
      aria-label="coach 4 anchor 进度"
    >
      {/* Header explains what the row is — without it, students just see
       *  four mysterious circles. 2026-05-21. */}
      <div className="workspace-hifi__plan-progress-header">
        <span className="workspace-hifi__plan-progress-title">
          {anchors.activeItemTitle
            ? `正在 coach: ${anchors.activeItemTitle}`
            : 'AI 想问你这 4 件事'}
        </span>
        <span className="workspace-hifi__plan-progress-count">
          {doneCount} / 4
        </span>
      </div>
      {anchors.activeItemTitle && (
        <div className="workspace-hifi__plan-progress-subtitle">
          AI 会按这 4 个点把这一段聊清楚
        </div>
      )}
      <div className="workspace-hifi__plan-progress-steps">
        {order.map((k) => {
          const done = anchors.filled[k];
          return (
            <button
              key={k}
              type="button"
              className={`workspace-hifi__plan-progress-step${done ? ' is-done' : ''}`}
              onClick={onAnchorClick ? () => onAnchorClick(k) : undefined}
              disabled={!onAnchorClick}
              title={`${ANCHOR_LABELS[k]} — ${ANCHOR_HINTS[k]}${done ? ' (已补齐)' : ' (待补充)'}`}
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
      </div>
      {anchors.allFilled && (
        <span className="workspace-hifi__plan-progress-hint">
          4 个 anchor 已齐 — 自动收尾中…
        </span>
      )}
    </div>
  );
}
