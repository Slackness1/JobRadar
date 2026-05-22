'use client';

/**
 * FabricationWarning — C-5 红线警告组件.
 *
 * Phase 2 FE-3 (2026-05-20).
 *
 * 当后端 `_detect_fabricated_numbers()` 在 v2 改写文本里发现 profile 查不到的
 * 数字时,后端会返 `RewriteWarning[]`,前端**必须**显式且红色地展示给学生,
 * 并给 3 条出路按钮 (填实数 / 删数 / 接受模糊版).
 *
 * 硬约束 (CLAUDE.md):
 *   - 警告**不能** suppress / collapse / 折叠
 *   - 学生看完才能 dismiss(我们不主动 hide)
 *   - 红色 banner: background #fee2e2 / border-left #ef4444
 *
 * Callback semantics:
 *   - onAction(action, warning): 由 RightResumePane 决定怎么处理(暂时:
 *     "fill_real" → focus 该 bullet 让学生改;"delete_number" → 替换数字为空;
 *     "vague" → 接受 v2 文本 as-is;FE-3 阶段都简化为 toast + 复制纯净文本).
 */

import type { RewriteWarningDto } from '../../api';

export type FabricationWarningAction = 'fill_real' | 'delete_number' | 'vague' | string;

export interface FabricationWarningProps {
  warnings: RewriteWarningDto[];
  onAction?: (action: FabricationWarningAction, warning: RewriteWarningDto) => void;
}

export function FabricationWarning({ warnings, onAction }: FabricationWarningProps) {
  if (!warnings || warnings.length === 0) return null;

  return (
    <div className="workspace-hifi__fab-warn-stack" role="alert">
      {warnings.map((warn, i) => {
        const headline =
          warn.type === 'fabricated_number'
            ? `AI 在 v2 改写里写了「${warn.number || '某数字'}」,但你的 profile 里查不到这个数字`
            : warn.detail || `AI 改写命中警告:${warn.type}`;
        const buttons = warn.suggestion_options?.length
          ? warn.suggestion_options
          : [
              { action: 'fill_real', label: '填实数' },
              { action: 'delete_number', label: '删数' },
              { action: 'vague', label: '接受模糊版' },
            ];

        return (
          <div
            key={`${warn.type}-${warn.number}-${i}`}
            className="workspace-hifi__fab-warn"
          >
            <div className="workspace-hifi__fab-warn-icon" aria-hidden>
              ⚠
            </div>
            <div className="workspace-hifi__fab-warn-body">
              <div className="workspace-hifi__fab-warn-headline">{headline}</div>
              {warn.detail && warn.type === 'fabricated_number' ? (
                <div className="workspace-hifi__fab-warn-detail">{warn.detail}</div>
              ) : null}
              <div className="workspace-hifi__fab-warn-actions">
                {buttons.map((opt) => (
                  <button
                    key={opt.action}
                    type="button"
                    className="workspace-hifi__fab-warn-btn"
                    onClick={() => onAction?.(opt.action, warn)}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
