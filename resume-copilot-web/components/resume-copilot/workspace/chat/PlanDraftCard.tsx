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

const RISK_LABELS: Record<string, string> = {
  overclaim: '有数字或结论还缺原始证据',
  leadership_unverified: '主导度还需要确认',
  tech_unverified: '工具 / 技术细节还需要确认',
  missing_metric: '结果指标还不够具体',
  vague_verb: '动作表述还偏泛',
  vague_quantification: '量化表述还偏模糊',
  evidence_scope_unverified: '调研 / 访谈规模还需要出处',
  implausible_scale: '项目规模 / 金额和实习角色需要再对齐',
  student_introduced_number: '有聊天中新补充的数字,入档前请确认准确',
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
  const riskFlags = draftItem.draft?.risk_flags ?? [];

  return (
    <div
      className="workspace-hifi__plan-draft"
      role="region"
      aria-label="coach 草稿 review"
    >
      <header className="workspace-hifi__plan-draft-header">
        <span className="workspace-hifi__plan-draft-badge">📝 加厚后的草稿</span>
        <span className="workspace-hifi__plan-draft-kind">{kindLabel}</span>
      </header>
      <h4 className="workspace-hifi__plan-draft-title">{draftItem.title}</h4>
      <p className="workspace-hifi__plan-draft-text">{draftText}</p>

      {riskFlags.length > 0 && (
        <div className="workspace-hifi__plan-draft-risks" role="alert">
          <div className="workspace-hifi__plan-draft-risks-title">
            入档前请确认这些点
          </div>
          <ul>
            {riskFlags.map((flag, i) => (
              <li key={`${flag.kind}-${i}`}>
                {RISK_LABELS[flag.kind] ?? '这条草稿仍有待确认的信息'}
              </li>
            ))}
          </ul>
        </div>
      )}

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
