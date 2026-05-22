'use client';

/**
 * BulletRewriteDiff — inline v0/v2 diff panel shown beneath a bullet (C-1 简 / E-3).
 *
 * Phase 2 FE-3 (2026-05-20).
 *
 * 渲染逻辑:
 *   - loading:       菊花 + "正在生成 v2…"
 *   - error:         红色提示 + 重试 / 关闭
 *   - needs_plan:    📌 banner + "切到 plan-mode" 按钮 (回调由 RightResumePane 串入)
 *   - normal:        v0 (灰) → arrow → v2 (主色高亮) + 采用 / 关闭 + 红警告 (C-5)
 *
 * Apply 链路暂未接通(详见 RightResumePane README) — 采用按钮目前
 * = "复制 v2 文本到剪贴板" + toast 提示学生粘贴.
 */

import type { RewriteV0V2Out } from '../../api';
import { FabricationWarning, type FabricationWarningAction } from './FabricationWarning';

export interface BulletRewriteDiffProps {
  /** Loading 时 result 为 null */
  result: RewriteV0V2Out | null;
  loading: boolean;
  error?: string | null;
  /** 学生点 "采用 v2 文案" — 由 RightResumePane 处理(目前=复制到剪贴板) */
  onAccept(v2Text: string, original: string, fieldPath: string): void;
  /** 学生点 "关闭" — 收起 diff panel */
  onDismiss(): void;
  /** 学生点 "切到 plan-mode" (needs_plan_mode=true 时) */
  onPlanModeRequest?: (fieldPath: string, originalBullet: string) => void;
  /** 学生在 warning 上点 fill_real / delete_number / vague 时 */
  onWarningAction?: (action: FabricationWarningAction, warningDetail: string) => void;
  /** loading / 失败时也要知道原文 (display 用) */
  originalBullet: string;
  fieldPath: string;
}

export function BulletRewriteDiff({
  result,
  loading,
  error,
  onAccept,
  onDismiss,
  onPlanModeRequest,
  onWarningAction,
  originalBullet,
  fieldPath,
}: BulletRewriteDiffProps) {
  if (loading) {
    return (
      <div className="workspace-hifi__bullet-diff is-loading">
        <div className="workspace-hifi__bullet-diff-spinner" aria-hidden />
        <span className="workspace-hifi__bullet-diff-loading-text">
          AI 正在基于你的档案做 thesis-aware 改写…
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="workspace-hifi__bullet-diff is-error">
        <div className="workspace-hifi__bullet-diff-error">{error}</div>
        <div className="workspace-hifi__bullet-diff-actions">
          <button type="button" className="workspace-hifi__diff-btn" onClick={onDismiss}>
            关闭
          </button>
        </div>
      </div>
    );
  }

  if (!result) return null;

  const v0Text = result.v0?.text || originalBullet;
  const v2 = result.v2;
  const needsPlan = v2?.needs_plan_mode === true;

  return (
    <div className="workspace-hifi__bullet-diff">
      {/* v0 原文 */}
      <div className="workspace-hifi__diff-row workspace-hifi__diff-row--v0">
        <span className="workspace-hifi__diff-label">v0 · 原文</span>
        <span className="workspace-hifi__diff-text">{v0Text}</span>
      </div>

      <div className="workspace-hifi__diff-arrow" aria-hidden>
        ↓
      </div>

      {/* v2 改写 OR plan-mode 引导 */}
      {needsPlan ? (
        <div className="workspace-hifi__diff-plan-hint">
          <div className="workspace-hifi__diff-plan-hint-text">
            📌 这段经历在你的档案里证据不足。建议切到 <strong>coach</strong> 跟 AI 聊聊
            这段经历的关键决策 / 量化结果,再回来改写效果会强很多。
          </div>
          {onPlanModeRequest ? (
            <button
              type="button"
              className="workspace-hifi__diff-btn workspace-hifi__diff-btn--primary"
              onClick={() => onPlanModeRequest(fieldPath, originalBullet)}
            >
              切到 coach 聊这段
            </button>
          ) : null}
          <button
            type="button"
            className="workspace-hifi__diff-btn"
            onClick={onDismiss}
          >
            先关闭
          </button>
        </div>
      ) : (
        <>
          <div className="workspace-hifi__diff-row workspace-hifi__diff-row--v2">
            <span className="workspace-hifi__diff-label workspace-hifi__diff-label--v2">v2 · thesis-aware</span>
            <span className="workspace-hifi__diff-text workspace-hifi__diff-text--v2">
              {v2?.text || '(v2 未返回文本)'}
            </span>
          </div>

          {/* #114 Phase 1: 港新学生英文 bullet (IB/MBB style) */}
          {v2?.en_text ? (
            <div className="workspace-hifi__diff-row workspace-hifi__diff-row--en">
              <span className="workspace-hifi__diff-label workspace-hifi__diff-label--en">
                EN · IB/MBB style
              </span>
              <span className="workspace-hifi__diff-text workspace-hifi__diff-text--en">
                {v2.en_text}
              </span>
            </div>
          ) : null}

          {/* 编数字红警告 (C-5) — 不许 suppress */}
          {v2?.warnings && v2.warnings.length > 0 ? (
            <FabricationWarning
              warnings={v2.warnings}
              onAction={(action, w) =>
                onWarningAction?.(
                  action,
                  `命中数字: ${w.number || '(未知)'} · ${w.detail || ''}`.trim(),
                )
              }
            />
          ) : null}

          {/* 软提示 (Fix #2) — memory 空但仍改写时,引导去 plan-mode 让结果更精准 */}
          {v2?.soft_hint ? (
            <div className="workspace-hifi__diff-soft-hint">
              {v2.soft_hint}
              {onPlanModeRequest ? (
                <button
                  type="button"
                  className="workspace-hifi__diff-soft-hint-btn"
                  onClick={() => onPlanModeRequest(fieldPath, originalBullet)}
                >
                  去 coach 聊聊
                </button>
              ) : null}
            </div>
          ) : null}

          {result.rationale ? (
            <div className="workspace-hifi__diff-rationale">
              <span className="workspace-hifi__diff-rationale-label">改写思路:</span>
              {result.rationale}
            </div>
          ) : null}

          <div className="workspace-hifi__diff-actions">
            <button
              type="button"
              className="workspace-hifi__diff-btn workspace-hifi__diff-btn--primary"
              onClick={() => onAccept(v2?.text || '', v0Text, fieldPath)}
            >
              采用 v2 (复制到剪贴板)
            </button>
            {v2?.en_text ? (
              <button
                type="button"
                className="workspace-hifi__diff-btn"
                onClick={() => {
                  if (typeof navigator !== 'undefined' && navigator.clipboard) {
                    void navigator.clipboard.writeText(v2.en_text || '');
                  }
                }}
                title="复制英文版到剪贴板 (港新外资 IB / MBB 投递用)"
              >
                复制 EN
              </button>
            ) : null}
            <button type="button" className="workspace-hifi__diff-btn" onClick={onDismiss}>
              关闭
            </button>
          </div>
        </>
      )}
    </div>
  );
}
