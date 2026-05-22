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
  /** Plan 1 (2026-05-20): 学生点 🔄 "内容已变,建议重聊" badge → 进 plan-mode
   *  focus 这条记忆对应的 bullet。 父 (ArchivePanel) 转发到 MiddleChatPane。 */
  onResyncClick?: (entry: MemoryEntry) => void;
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

/**
 * 入库时间格式 — 用户口径 (2026-05-21):
 *   - 今天                  → "今天 HH:mm"
 *   - 昨天                  → "昨天 HH:mm"
 *   - 本周内(早于昨天)       → "星期X HH:mm"
 *   - 同年内(早于本周)       → "MM-DD"
 *   - 跨年                  → "YYYY-MM-DD"
 *
 * 时间 = 北京时间 (UTC+8). 后端用 naive UTC 存; new Date() 把无时区的
 * ISO 串当成本地, 不可靠 — 这里直接把 ms 加 8h 偏移再走 UTC getters。
 */
const WEEKDAY_CN = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];

function toBeijing(input: string): Date {
  // 后端 captured_at 形如 "2026-05-21T06:54:48.424684" (naive UTC).
  // 加 'Z' 强制按 UTC 解析, 再 +8h 偏移得到北京时间。
  let s = input;
  if (!/Z|[+-]\d{2}:?\d{2}$/.test(s)) s = s.replace(/\s+/, 'T') + 'Z';
  const utcMs = new Date(s).valueOf();
  return new Date(utcMs + 8 * 3600 * 1000);
}

function beijingNow(): Date {
  return new Date(Date.now() + 8 * 3600 * 1000);
}

function formatCaptured(value?: string | null): string {
  if (!value) return '';
  try {
    const d = toBeijing(value);
    if (Number.isNaN(d.valueOf())) return value;
    const now = beijingNow();

    // 用 UTC getters 因为我们把"北京时间"塞进了 UTC 字段里。
    const hh = String(d.getUTCHours()).padStart(2, '0');
    const mi = String(d.getUTCMinutes()).padStart(2, '0');
    const time = `${hh}:${mi}`;

    // 比较时只看年/月/日(都按北京算)
    const dDay = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
    const nowDay = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
    const dayDiff = Math.round((nowDay - dDay) / 86400000);

    if (dayDiff === 0) return `今天 ${time}`;
    if (dayDiff === 1) return `昨天 ${time}`;

    // 本周 = 距今 < 7 天, 且周一到周日同一个 ISO 周
    // 简化:dayDiff 在 2..6 之间, 且和今天属于同一个"周起点 (周一)"
    const dWeekStart = nowDay - ((now.getUTCDay() + 6) % 7) * 86400000;
    if (dDay >= dWeekStart && dayDiff < 7) {
      return `${WEEKDAY_CN[d.getUTCDay()]} ${time}`;
    }

    const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
    const dd = String(d.getUTCDate()).padStart(2, '0');
    if (d.getUTCFullYear() === now.getUTCFullYear()) {
      return `${mm}-${dd}`;
    }
    return `${d.getUTCFullYear()}-${mm}-${dd}`;
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
  onResyncClick,
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

  const needsResync = entry.needs_resync === true;

  return (
    <li
      className={`workspace-hifi__archive-card${expanded ? ' is-expanded' : ''}${
        isNew ? ' is-new' : ''
      }${needsResync ? ' is-needs-resync' : ''}`}
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
          {needsResync && (
            <button
              type="button"
              className="workspace-hifi__archive-card-resync"
              onClick={(e) => { e.stopPropagation(); onResyncClick?.(entry); }}
              title="你改了对应的简历段落 — AI 的理解可能已过时, 点这里去 coach 重聊一下"
              aria-label="内容已变,建议去 coach 重聊"
            >
              🔄 重聊
            </button>
          )}
          <span className="workspace-hifi__archive-card-summary-text">{entry.summary}</span>
        </button>
        <div className="workspace-hifi__archive-card-meta-row">
          <span className="workspace-hifi__archive-card-category" data-cat={entry.category}>
            {categoryLabel}
          </span>
          {entry.linked_track ? (
            <span
              className="workspace-hifi__archive-card-track"
              title={`聊这条经历时, 当时在准备的赛道是「${entry.linked_track}」`}
            >
              🎯 {entry.linked_track}
            </span>
          ) : null}
          {entry.captured_at && (
            <span
              className="workspace-hifi__archive-card-captured"
              title={`这条经历是在 ${formatCaptured(entry.captured_at)} 入档的`}
            >
              📅 入库 {formatCaptured(entry.captured_at)}
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
