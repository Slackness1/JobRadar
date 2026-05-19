'use client';

/**
 * RecommendRejectForm — D-2 / D-3 inline 反馈卡。
 *
 * 渲染在 `<RecommendCard>` 底部(非 modal),5 个 radio + 自由备注 textarea +
 * 取消 / 提交 两按钮。提交调 `postRejectRecommendation` (BE-3),成功后由父
 * 卡接管 — 父卡用 FLIP 移除该条 + 父 rail toast。
 *
 * reason key / label 对照表跟 BE `REJECT_REASON_LABELS` 完全一致
 * (`backend/app/schemas_resume_copilot.py:434`):
 *   wrong_track / company_disliked / school_mismatch / timing / other
 */

import { useState, useId } from 'react';
import { I } from '@/components/hifi/hifi-primitives';
import type { RecommendRejectReason } from '../../api';

interface ReasonOption {
  key: RecommendRejectReason;
  label: string;
}

const REASON_OPTIONS: ReasonOption[] = [
  { key: 'wrong_track', label: '赛道不对' },
  { key: 'company_disliked', label: '公司不喜欢' },
  { key: 'school_mismatch', label: '学校段位不匹配' },
  { key: 'timing', label: '时间不合适' },
  { key: 'other', label: '其他' },
];

const NOTE_MAX = 200;

export interface RecommendRejectFormProps {
  /** Called when student presses 提交 — parent runs the actual fetch + animation. */
  onSubmit: (reason: RecommendRejectReason, note: string) => Promise<void>;
  /** Called when student presses 取消 — parent collapses the form. */
  onCancel: () => void;
}

export function RecommendRejectForm({ onSubmit, onCancel }: RecommendRejectFormProps) {
  const groupName = useId();
  const [reason, setReason] = useState<RecommendRejectReason | ''>('');
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>('');

  const canSubmit = reason !== '' && !submitting;

  const handleSubmit = async () => {
    if (reason === '' || submitting) return;
    const selectedReason: RecommendRejectReason = reason;
    setSubmitting(true);
    setError('');
    try {
      await onSubmit(selectedReason, note.trim());
      // Parent unmounts the form on success — no further state to reset.
    } catch (err) {
      setSubmitting(false);
      setError(err instanceof Error ? err.message : '提交失败,请稍后再试');
    }
  };

  return (
    <div
      className="workspace-hifi__reject-form"
      role="group"
      aria-label="反馈为什么不想要这个推荐"
    >
      <div className="workspace-hifi__reject-form-title">
        告诉我为什么不喜欢
      </div>
      <div className="workspace-hifi__reject-form-reasons">
        {REASON_OPTIONS.map((opt) => (
          <label
            key={opt.key}
            className={`workspace-hifi__reject-reason${reason === opt.key ? ' is-active' : ''}`}
          >
            <input
              type="radio"
              name={groupName}
              value={opt.key}
              checked={reason === opt.key}
              onChange={() => setReason(opt.key)}
              disabled={submitting}
            />
            <span>{opt.label}</span>
          </label>
        ))}
      </div>
      <textarea
        className="workspace-hifi__reject-note"
        placeholder="备注(可选,≤200 字) — 比如「想去一线城市」「学校卡到 985」"
        value={note}
        onChange={(e) => setNote(e.target.value.slice(0, NOTE_MAX))}
        disabled={submitting}
        rows={2}
      />
      <div className="workspace-hifi__reject-note-count">
        {note.length} / {NOTE_MAX}
      </div>
      {error && (
        <div className="workspace-hifi__reject-error" role="alert">
          {error}
        </div>
      )}
      <div className="workspace-hifi__reject-actions">
        <button
          type="button"
          className="workspace-hifi__reject-btn workspace-hifi__reject-btn--ghost"
          onClick={onCancel}
          disabled={submitting}
        >
          取消
        </button>
        <button
          type="button"
          className="workspace-hifi__reject-btn workspace-hifi__reject-btn--primary"
          onClick={() => void handleSubmit()}
          disabled={!canSubmit}
        >
          <span aria-hidden style={{ display: 'inline-flex' }}>{I.check(13)}</span>
          {submitting ? '提交中...' : '提交'}
        </button>
      </div>
    </div>
  );
}
