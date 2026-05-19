'use client';

/**
 * ArchiveEntryCard — 单条 account_memory 条目卡 (A-2 / A-3 简).
 *
 * Phase 2 FE-4 (2026-05-20).
 *
 * Responsibilities:
 *   - 默认渲染 summary 一行 + meta(category / captured_at / new-flag);
 *     点击展开看 payload (key-value 表) + raw_excerpt(原话出处).
 *   - 行右上 `⋯` 菜单:**编辑** (inline summary + payload JSON textarea)
 *     / **删除** (toast undo 模式 —— DELETE 立即调用 + toast 提示;
 *     BE 没有 unarchive endpoint 所以"撤回"留为 TODO 不真撤回).
 *
 * Wire callbacks:
 *   - onEdited(entry):  PATCH 成功后通知父刷新缓存
 *   - onDeleted(entryId): DELETE 成功后通知父从列表中移除
 *   - onToast(msg):  父统一 toast (避免每张卡自己长 toast)
 *
 * Design system:
 *   - Scoped under `.workspace-hifi` (workspace-theme.css);
 *     HiFi tokens 来自 `.hf` 父层。
 */

import { useCallback, useMemo, useState } from 'react';

import {
  patchSessionMemoryEntry,
  deleteSessionMemoryEntry,
  type MemoryEntry,
} from '../../api';

export interface ArchiveEntryCardProps {
  sessionId: number;
  entry: MemoryEntry;
  /** 是否被视为"新增条目"(用于 🟢 角标);由 ArchivePanel 计算后传入。 */
  isNew?: boolean;
  onEdited?: (entry: MemoryEntry) => void;
  onDeleted?: (entryId: number) => void;
  onToast?: (msg: string) => void;
}

const CATEGORY_LABELS: Record<string, string> = {
  experience: '经历',
  skill_claim: '技能',
  preference: '偏好',
  identity_fact: '身份',
  evidence: '佐证',
  goal: '目标',
  commitment: '承诺',
  weakness_signal: '弱点信号',
};

function formatCaptured(value?: string | null): string {
  if (!value) return '';
  try {
    const d = new Date(value);
    if (Number.isNaN(d.valueOf())) return value;
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  } catch {
    return value;
  }
}

export function ArchiveEntryCard({
  sessionId,
  entry,
  isNew = false,
  onEdited,
  onDeleted,
  onToast,
}: ArchiveEntryCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [savingPatch, setSavingPatch] = useState(false);

  const [draftSummary, setDraftSummary] = useState(entry.summary);
  const [draftPayload, setDraftPayload] = useState<string>(() =>
    JSON.stringify(entry.payload ?? {}, null, 2),
  );
  const [payloadError, setPayloadError] = useState<string | null>(null);

  const categoryLabel = CATEGORY_LABELS[String(entry.category)] || String(entry.category);

  const beginEdit = useCallback(() => {
    setEditing(true);
    setMenuOpen(false);
    setExpanded(true);
    setDraftSummary(entry.summary);
    setDraftPayload(JSON.stringify(entry.payload ?? {}, null, 2));
    setPayloadError(null);
  }, [entry.payload, entry.summary]);

  const cancelEdit = useCallback(() => {
    setEditing(false);
    setPayloadError(null);
  }, []);

  const handleSave = useCallback(async () => {
    setPayloadError(null);
    const summaryTrimmed = draftSummary.trim();
    if (!summaryTrimmed) {
      setPayloadError('摘要不能为空。');
      return;
    }
    let parsedPayload: Record<string, unknown> | undefined;
    if (draftPayload.trim()) {
      try {
        const parsed = JSON.parse(draftPayload);
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
          parsedPayload = parsed as Record<string, unknown>;
        } else {
          setPayloadError('payload 必须是 JSON 对象,不能是数组 / 基础类型。');
          return;
        }
      } catch (err) {
        setPayloadError(
          `payload 不是合法 JSON: ${err instanceof Error ? err.message : String(err)}`,
        );
        return;
      }
    } else {
      parsedPayload = {};
    }

    setSavingPatch(true);
    try {
      const updated = await patchSessionMemoryEntry(sessionId, entry.id, {
        summary: summaryTrimmed,
        payload: parsedPayload,
      });
      setEditing(false);
      onEdited?.(updated);
      onToast?.('已更新档案条目。');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setPayloadError(`保存失败:${msg}`);
    } finally {
      setSavingPatch(false);
    }
  }, [
    draftPayload,
    draftSummary,
    entry.id,
    onEdited,
    onToast,
    sessionId,
  ]);

  const handleDelete = useCallback(async () => {
    setMenuOpen(false);
    // BE 没暴露 unarchive 接口,撤回先空跑 + TODO。
    const summarySnippet =
      entry.summary.length > 18 ? entry.summary.slice(0, 18) + '…' : entry.summary;
    try {
      await deleteSessionMemoryEntry(sessionId, entry.id);
      onDeleted?.(entry.id);
      onToast?.(`已删除「${summarySnippet}」 · 撤回 (暂未启用)`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      onToast?.(`删除失败:${msg}`);
    }
  }, [entry.id, entry.summary, onDeleted, onToast, sessionId]);

  const payloadEntries = useMemo(() => {
    const pl = entry.payload ?? {};
    if (!pl || typeof pl !== 'object') return [] as Array<[string, unknown]>;
    return Object.entries(pl as Record<string, unknown>);
  }, [entry.payload]);

  return (
    <li
      className={`workspace-hifi__archive-card${expanded ? ' is-expanded' : ''}${
        isNew ? ' is-new' : ''
      }`}
    >
      <div className="workspace-hifi__archive-card-head">
        <button
          type="button"
          className="workspace-hifi__archive-card-summary"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          aria-label={expanded ? '收起条目' : '展开条目'}
        >
          {isNew && (
            <span className="workspace-hifi__archive-card-new" aria-label="新增">
              新
            </span>
          )}
          <span className="workspace-hifi__archive-card-summary-text">{entry.summary}</span>
        </button>
        <div className="workspace-hifi__archive-card-meta-row">
          <span className="workspace-hifi__archive-card-category" data-cat={entry.category}>
            {categoryLabel}
          </span>
          {entry.captured_at && (
            <span className="workspace-hifi__archive-card-captured">
              {formatCaptured(entry.captured_at)}
            </span>
          )}
          <div className="workspace-hifi__archive-card-menu-wrap">
            <button
              type="button"
              className="workspace-hifi__archive-card-menu-btn"
              onClick={() => setMenuOpen((v) => !v)}
              aria-label="更多操作"
              aria-haspopup="menu"
              aria-expanded={menuOpen}
            >
              ⋯
            </button>
            {menuOpen && (
              <div className="workspace-hifi__archive-card-menu" role="menu">
                <button
                  type="button"
                  role="menuitem"
                  className="workspace-hifi__archive-card-menu-item"
                  onClick={beginEdit}
                >
                  编辑
                </button>
                <button
                  type="button"
                  role="menuitem"
                  className="workspace-hifi__archive-card-menu-item is-danger"
                  onClick={handleDelete}
                >
                  删除
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {expanded && !editing && (
        <div className="workspace-hifi__archive-card-body">
          {payloadEntries.length > 0 && (
            <dl className="workspace-hifi__archive-card-payload">
              {payloadEntries.map(([k, v]) => (
                <div key={k} className="workspace-hifi__archive-card-payload-row">
                  <dt>{k}</dt>
                  <dd>
                    {typeof v === 'string'
                      ? v
                      : v == null
                        ? '—'
                        : JSON.stringify(v)}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          {entry.raw_excerpt && (
            <div className="workspace-hifi__archive-card-excerpt">
              <span className="workspace-hifi__archive-card-excerpt-label">原话出处</span>
              <p>{entry.raw_excerpt}</p>
            </div>
          )}
          {payloadEntries.length === 0 && !entry.raw_excerpt && (
            <p className="workspace-hifi__archive-card-empty">没有更多结构化字段。</p>
          )}
        </div>
      )}

      {expanded && editing && (
        <div className="workspace-hifi__archive-card-edit">
          <label className="workspace-hifi__archive-card-edit-label">
            <span>摘要</span>
            <input
              type="text"
              value={draftSummary}
              maxLength={200}
              onChange={(e) => setDraftSummary(e.target.value)}
              className="workspace-hifi__archive-card-edit-input"
            />
          </label>
          <label className="workspace-hifi__archive-card-edit-label">
            <span>payload (JSON 对象)</span>
            <textarea
              rows={5}
              value={draftPayload}
              onChange={(e) => setDraftPayload(e.target.value)}
              className="workspace-hifi__archive-card-edit-textarea"
              spellCheck={false}
            />
          </label>
          {payloadError && (
            <div className="workspace-hifi__archive-card-edit-error" role="alert">
              {payloadError}
            </div>
          )}
          <div className="workspace-hifi__archive-card-edit-actions">
            <button
              type="button"
              className="workspace-hifi__archive-card-edit-btn"
              onClick={cancelEdit}
              disabled={savingPatch}
            >
              取消
            </button>
            <button
              type="button"
              className="workspace-hifi__archive-card-edit-btn is-primary"
              onClick={handleSave}
              disabled={savingPatch}
            >
              {savingPatch ? '保存中…' : '保存'}
            </button>
          </div>
        </div>
      )}
    </li>
  );
}
