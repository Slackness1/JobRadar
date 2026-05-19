'use client';

/**
 * PlanDraftCard — plan-mode finalize 后的"加厚后的草稿"卡 (B-4).
 *
 * Phase 2 FE-4 (2026-05-20).
 *
 * 展示 BE 拼好的 summary + draft text + 4 个 anchor evidence.
 * 学生两条出路:
 *   - **入档**:调 POST /sessions/{id}/memory 写一条 experience entry
 *   - **再聊几轮**:关掉卡片回到 plan turn 模式继续
 *
 * Wire (父在 MiddleChatPane 里):
 *   - draftItem: 来自 plan.items[?] (active item with status=FINALIZED 或 AWAITING_REVIEW)
 *   - onArchive(): 父调 postSessionMemory + 关闭 + toast
 *   - onContinue(): 父关闭卡片 + 学生继续在 composer 输入
 */

import type { PlanItemWire } from '../../api';

export interface PlanDraftCardProps {
  draftItem: PlanItemWire;
  isArchiving?: boolean;
  onArchive: () => void;
  onContinue: () => void;
}

const KIND_LABELS: Record<string, string> = {
  self_intro: '自我介绍',
  education: '教育',
  internship: '实习',
  project: '项目',
  campus_activity: '校园活动',
  skill: '技能',
  award: '奖项',
};

export function PlanDraftCard({
  draftItem,
  isArchiving = false,
  onArchive,
  onContinue,
}: PlanDraftCardProps) {
  const draftText =
    draftItem.draft?.text?.trim() ||
    `(暂无 AI 拼好的草稿 — 当前 item 状态 ${draftItem.status},可继续多聊几轮以补齐 anchor)`;
  const kindLabel = KIND_LABELS[String(draftItem.kind)] || String(draftItem.kind);

  return (
    <div
      className="workspace-hifi__plan-draft"
      role="region"
      aria-label="plan-mode 草稿 review"
    >
      <header className="workspace-hifi__plan-draft-header">
        <span className="workspace-hifi__plan-draft-badge">📝 加厚后的草稿</span>
        <span className="workspace-hifi__plan-draft-kind">{kindLabel}</span>
      </header>
      <h4 className="workspace-hifi__plan-draft-title">{draftItem.title}</h4>
      <p className="workspace-hifi__plan-draft-text">{draftText}</p>

      {(draftItem.evidence ?? []).length > 0 && (
        <details className="workspace-hifi__plan-draft-evidence">
          <summary>查看 {draftItem.evidence.length} 条原话出处</summary>
          <ul>
            {draftItem.evidence.map((ev) => (
              <li key={ev.id}>
                <span className="workspace-hifi__plan-draft-evidence-src">
                  {ev.source}
                </span>
                : {ev.text}
              </li>
            ))}
          </ul>
        </details>
      )}

      <div className="workspace-hifi__plan-draft-actions">
        <button
          type="button"
          className="workspace-hifi__plan-draft-btn"
          onClick={onContinue}
          disabled={isArchiving}
        >
          再聊几轮
        </button>
        <button
          type="button"
          className="workspace-hifi__plan-draft-btn is-primary"
          onClick={onArchive}
          disabled={isArchiving}
        >
          {isArchiving ? '入档中…' : '入档'}
        </button>
      </div>
    </div>
  );
}
