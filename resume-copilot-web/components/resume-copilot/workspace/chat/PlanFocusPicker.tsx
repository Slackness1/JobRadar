'use client';

/**
 * PlanFocusPicker — plan-mode 启动时让学生从档案选一条经历 (B-2 简).
 *
 * Phase 2 FE-4 (2026-05-20).
 *
 * 设计:
 *   学生切到 📌 plan-mode 时,若 session 没有 active plan:
 *     - 拉 `/sessions/{id}/memory`,展示 experience entries 列表
 *     - 学生点选一条 → 父调 `postPlanStart({focus_kind:"experience", focus_id})`
 *     - 学生选"自由聊一段新经历" → 父调 `postPlanStart({focus_kind:"experience"})`(无 id)
 *     - 学生取消 → 父切回 normal mode
 *
 * 兜底:
 *   - memory 拉失败:展示错误 + "继续(自由聊一段)"按钮
 *   - 没有 experience entries:只显示"自由聊一段"按钮 + 引导提示
 *
 * 不做:
 *   - LLM 推断梳理对象(B-2 砍了,直接列档案给学生选)
 */

import { useCallback, useEffect, useState } from 'react';

import { getSessionMemory, type MemoryEntry } from '../../api';

export interface PlanFocusPickerProps {
  sessionId: number;
  onConfirm: (params: { focusKind: 'experience'; focusId?: number }) => void;
  onCancel: () => void;
  /** 父预选条目 — 来自档案 banner 点击;有此值时直接展示该条而不拉列表。 */
  preselectedEntryId?: number;
}

export function PlanFocusPicker({
  sessionId,
  onConfirm,
  onCancel,
  preselectedEntryId,
}: PlanFocusPickerProps) {
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [experiences, setExperiences] = useState<MemoryEntry[]>([]);

  useEffect(() => {
    let cancelled = false;
    getSessionMemory(sessionId)
      .then((res) => {
        if (cancelled) return;
        const list = res.entries?.experience ?? [];
        setExperiences(list);
        setErrorMsg(null);
      })
      .catch((err) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : String(err);
        setErrorMsg(`档案加载失败:${msg}`);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const handlePickEntry = useCallback(
    (entry: MemoryEntry) => {
      onConfirm({ focusKind: 'experience', focusId: entry.id });
    },
    [onConfirm],
  );

  const handleFreeForm = useCallback(() => {
    onConfirm({ focusKind: 'experience' });
  }, [onConfirm]);

  return (
    <div
      className="workspace-hifi__plan-picker"
      role="dialog"
      aria-label="选择要梳理的经历"
    >
      <div className="workspace-hifi__plan-picker-header">
        <span className="workspace-hifi__plan-picker-title">
          📌 想聊哪段经历?
        </span>
        <button
          type="button"
          className="workspace-hifi__plan-picker-close"
          onClick={onCancel}
          aria-label="取消 coach"
        >
          ✕
        </button>
      </div>

      {loading && (
        <div className="workspace-hifi__plan-picker-loading">加载档案…</div>
      )}

      {errorMsg && (
        <div className="workspace-hifi__plan-picker-error" role="alert">
          {errorMsg}
        </div>
      )}

      {!loading && experiences.length > 0 && (
        <ul className="workspace-hifi__plan-picker-list">
          {experiences.map((e) => {
            const preselected = preselectedEntryId === e.id;
            return (
              <li key={e.id}>
                <button
                  type="button"
                  className={`workspace-hifi__plan-picker-item${
                    preselected ? ' is-preselected' : ''
                  }`}
                  onClick={() => handlePickEntry(e)}
                >
                  <span className="workspace-hifi__plan-picker-item-summary">
                    {e.summary}
                  </span>
                  {e.raw_excerpt && (
                    <span className="workspace-hifi__plan-picker-item-quote">
                      「{e.raw_excerpt.length > 50 ? e.raw_excerpt.slice(0, 50) + '…' : e.raw_excerpt}」
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {!loading && experiences.length === 0 && !errorMsg && (
        <p className="workspace-hifi__plan-picker-empty">
          档案里还没有经历条目 — 你可以自由聊一段新经历,AI 会带你 4 个 anchor 补齐。
        </p>
      )}

      <div className="workspace-hifi__plan-picker-actions">
        <button
          type="button"
          className="workspace-hifi__plan-picker-btn"
          onClick={onCancel}
        >
          取消
        </button>
        <button
          type="button"
          className="workspace-hifi__plan-picker-btn is-primary"
          onClick={handleFreeForm}
        >
          自由聊一段新经历
        </button>
      </div>
    </div>
  );
}
