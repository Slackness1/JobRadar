'use client';

/**
 * ArchivePanel — 我的档案 (A-1 / A-2 / A-5 / A-6 / A-7).
 *
 * Phase 2 FE-4 (2026-05-20).
 *
 * 形态:
 *   - 默认收起浮条 (~48px) 显示 `📌 我的档案 (N 条)` + 🟢 新增提示;
 *     点击展开成 ~70vh 抽屉 (在 RightResumePane 底部 archive slot 内).
 *   - 展开后:
 *     - 经历主区 (experience entries 列表, 默认全展开 by category)
 *     - 其他次区 (skill_claim / preference / 其他 5 类合并, 默认折叠)
 *     - 排序:新增条目 (last 24h) 置顶 + 时间倒序 (后续 ⭐ 重要置顶被砍)
 *   - 第一次进档案 / empty:底部引导 banner
 *     「让 AI 跟你聊聊每段经历」按钮 → 触发 plan-mode (B-2)
 *
 * 小绿点逻辑:
 *   - localStorage key `jobradar.workspace.lastSeenArchiveCount.<sessionId>`
 *   - 当前 total > lastSeen → 显示 🟢
 *   - 用户点开 ArchivePanel → 更新 lastSeen = current → 绿点消失
 *
 * Wire:
 *   - sessionId 从 WorkspaceShell.session.id 派下来
 *   - onStartPlanMode(focusKind, focusId?) 由 WorkspaceShell wire 到 MiddleChatPane
 *     (打开 plan-mode + 自动 select 该 entry)
 */

import { useCallback, useEffect, useMemo, useState } from 'react';

import {
  getSessionMemory,
  MEMORY_CATEGORIES,
  type MemoryEntry,
  type MemoryGroupedResponse,
} from '../../api';
import { ArchiveEntryCard } from './ArchiveEntryCard';

export interface ArchivePanelProps {
  sessionId: number | null;
  /** demo / guest 不写 memory — 父传入以避免空请求 */
  isDemo?: boolean;
  /** 学生点底部引导 banner → 切到 plan-mode 选 entry。 */
  onStartPlanMode?: (focusKind: string, focusId?: number) => void;
  /** 学生切到 plan-mode 时,父打开后会调这里关闭 panel(可选) */
  onPanelClosed?: () => void;
}

// LocalStorage key prefix for "已看过的档案数量"(小绿点判断)
const LAST_SEEN_PREFIX = 'jobradar.workspace.lastSeenArchiveCount.';

// 24h 视窗用作"新增条目置顶"判断
const NEW_WINDOW_MS = 24 * 60 * 60 * 1000;

const PRIMARY_CATEGORY = 'experience';
const SECONDARY_CATEGORIES = MEMORY_CATEGORIES.filter(
  (c) => c !== PRIMARY_CATEGORY,
);

const CATEGORY_LABELS_FULL: Record<string, string> = {
  experience: '经历',
  skill_claim: '技能',
  preference: '偏好',
  identity_fact: '身份',
  evidence: '佐证',
  goal: '目标',
  commitment: '承诺',
  weakness_signal: '弱点信号',
};

function parseTs(value?: string | null): number {
  if (!value) return 0;
  const t = Date.parse(value);
  return Number.isNaN(t) ? 0 : t;
}

function sortNewestWithRecentTop(entries: MemoryEntry[]): MemoryEntry[] {
  const now = Date.now();
  return [...entries].sort((a, b) => {
    const ta = parseTs(a.captured_at);
    const tb = parseTs(b.captured_at);
    const aNew = now - ta < NEW_WINDOW_MS;
    const bNew = now - tb < NEW_WINDOW_MS;
    if (aNew !== bNew) return aNew ? -1 : 1;
    return tb - ta; // newest first
  });
}

function readLastSeen(sessionId: number | null): number {
  if (typeof window === 'undefined' || sessionId == null) return 0;
  try {
    const raw = window.localStorage.getItem(LAST_SEEN_PREFIX + sessionId);
    if (!raw) return 0;
    const n = Number(raw);
    return Number.isFinite(n) ? n : 0;
  } catch {
    return 0;
  }
}

function writeLastSeen(sessionId: number | null, count: number) {
  if (typeof window === 'undefined' || sessionId == null) return;
  try {
    window.localStorage.setItem(LAST_SEEN_PREFIX + sessionId, String(count));
  } catch {
    // ignore quota / private-mode errors
  }
}

export function ArchivePanel({
  sessionId,
  isDemo = false,
  onStartPlanMode,
}: ArchivePanelProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [grouped, setGrouped] = useState<MemoryGroupedResponse | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [lastSeen, setLastSeen] = useState<number>(() => readLastSeen(sessionId));
  const [secondaryOpen, setSecondaryOpen] = useState(false);

  // Reload last-seen when session changes (e.g. user switched resume session).
  useEffect(() => {
    setLastSeen(readLastSeen(sessionId));
  }, [sessionId]);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    const id = window.setTimeout(() => setToast(null), 3000);
    return () => window.clearTimeout(id);
  }, []);

  const refresh = useCallback(async () => {
    if (sessionId == null || isDemo) {
      setGrouped(null);
      return;
    }
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await getSessionMemory(sessionId);
      setGrouped(res);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(`档案加载失败:${msg}`);
    } finally {
      setLoading(false);
    }
  }, [isDemo, sessionId]);

  // Auto-fetch on mount / when session changes / when opened first time.
  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Derive flat counts + ordered lists.
  const { primaryList, secondaryByCat, total, newCount } = useMemo(() => {
    const entriesMap = grouped?.entries ?? {};
    const primary = sortNewestWithRecentTop(entriesMap[PRIMARY_CATEGORY] ?? []);
    const secondary: Record<string, MemoryEntry[]> = {};
    let count = primary.length;
    for (const cat of SECONDARY_CATEGORIES) {
      const list = sortNewestWithRecentTop(entriesMap[cat] ?? []);
      if (list.length > 0) {
        secondary[cat] = list;
        count += list.length;
      }
    }
    const now = Date.now();
    let nc = 0;
    for (const list of [primary, ...Object.values(secondary)]) {
      for (const e of list) {
        if (now - parseTs(e.captured_at) < NEW_WINDOW_MS) nc += 1;
      }
    }
    return {
      primaryList: primary,
      secondaryByCat: secondary,
      total: count,
      newCount: nc,
    };
  }, [grouped]);

  const hasGreenDot = !isDemo && total > lastSeen;

  const handleToggleOpen = useCallback(() => {
    setOpen((prev) => {
      const next = !prev;
      if (next) {
        // Opening — mark as seen + refresh in case messages arrived since mount.
        writeLastSeen(sessionId, total);
        setLastSeen(total);
        void refresh();
      }
      return next;
    });
  }, [refresh, sessionId, total]);

  // Patch / Delete handlers — update local state without full refetch.
  const handleEntryEdited = useCallback((updated: MemoryEntry) => {
    setGrouped((prev) => {
      if (!prev) return prev;
      const cat = String(updated.category);
      const list = prev.entries[cat] ?? [];
      const idx = list.findIndex((e) => e.id === updated.id);
      if (idx < 0) return prev;
      const nextList = [...list];
      nextList[idx] = updated;
      return {
        ...prev,
        entries: { ...prev.entries, [cat]: nextList },
      };
    });
  }, []);

  const handleEntryDeleted = useCallback((entryId: number) => {
    setGrouped((prev) => {
      if (!prev) return prev;
      const nextEntries: Record<string, MemoryEntry[]> = {};
      for (const [cat, list] of Object.entries(prev.entries)) {
        nextEntries[cat] = list.filter((e) => e.id !== entryId);
      }
      return { ...prev, entries: nextEntries };
    });
  }, []);

  const handlePlanModeBanner = useCallback(() => {
    onStartPlanMode?.(PRIMARY_CATEGORY);
  }, [onStartPlanMode]);

  // ── Rendering ─────────────────────────────────────────────────────────────

  if (sessionId == null) {
    return (
      <div className="workspace-hifi__archive-empty-shell">
        <span>📌 我的档案</span>
        <span className="workspace-hifi__archive-empty-hint">
          上传简历后,AI 抽取的经历会自动入档。
        </span>
      </div>
    );
  }

  if (isDemo) {
    return (
      <div className="workspace-hifi__archive-empty-shell">
        <span>📌 我的档案 · DEMO</span>
        <span className="workspace-hifi__archive-empty-hint">
          示例会话只读 — 上传自己的简历后这里会出现你的档案。
        </span>
      </div>
    );
  }

  return (
    <section
      className={`workspace-hifi__archive${open ? ' is-open' : ''}`}
      aria-label="我的档案"
    >
      <button
        type="button"
        className="workspace-hifi__archive-toggle"
        onClick={handleToggleOpen}
        aria-expanded={open}
      >
        <span className="workspace-hifi__archive-toggle-icon" aria-hidden>
          📌
        </span>
        <span className="workspace-hifi__archive-toggle-title">我的档案</span>
        <span className="workspace-hifi__archive-toggle-count">
          {loading && !grouped ? '加载中…' : `${total} 条`}
          {newCount > 0 && open === false ? ` · 新增 ${newCount}` : ''}
        </span>
        {hasGreenDot && !open && (
          <span
            className="workspace-hifi__archive-toggle-dot"
            aria-label="有新增条目"
          />
        )}
        <span className="workspace-hifi__archive-toggle-chev" aria-hidden>
          {open ? '▾' : '▴'}
        </span>
      </button>

      {open && (
        <div className="workspace-hifi__archive-panel">
          {errorMsg && (
            <div className="workspace-hifi__archive-error" role="alert">
              {errorMsg}
            </div>
          )}

          {/* ── 经历主区 ───────────────────────────────────────────────── */}
          <div className="workspace-hifi__archive-section">
            <h4 className="workspace-hifi__archive-section-title">
              {CATEGORY_LABELS_FULL[PRIMARY_CATEGORY]}
              <span className="workspace-hifi__archive-section-count">
                {primaryList.length} 条
              </span>
            </h4>
            {primaryList.length > 0 ? (
              <ul className="workspace-hifi__archive-list">
                {primaryList.map((entry) => {
                  const isNew =
                    Date.now() - parseTs(entry.captured_at) < NEW_WINDOW_MS;
                  return (
                    <ArchiveEntryCard
                      key={entry.id}
                      sessionId={sessionId}
                      entry={entry}
                      isNew={isNew}
                      onEdited={handleEntryEdited}
                      onDeleted={handleEntryDeleted}
                      onToast={showToast}
                      onResyncClick={(e) => onStartPlanMode?.(String(e.category), e.id)}
                    />
                  );
                })}
              </ul>
            ) : (
              <p className="workspace-hifi__archive-section-empty">
                暂无经历条目。AI 跟你聊每段经历会自动入档。
              </p>
            )}
          </div>

          {/* ── 其他次区 (折叠) ────────────────────────────────────────── */}
          {Object.keys(secondaryByCat).length > 0 && (
            <div className="workspace-hifi__archive-section">
              <button
                type="button"
                className="workspace-hifi__archive-section-title is-collapsible"
                onClick={() => setSecondaryOpen((v) => !v)}
                aria-expanded={secondaryOpen}
              >
                其他类别
                <span className="workspace-hifi__archive-section-count">
                  {Object.values(secondaryByCat).reduce(
                    (acc, l) => acc + l.length,
                    0,
                  )}{' '}
                  条
                </span>
                <span className="workspace-hifi__archive-section-chev" aria-hidden>
                  {secondaryOpen ? '▾' : '▸'}
                </span>
              </button>
              {secondaryOpen && (
                <div className="workspace-hifi__archive-secondary-stack">
                  {Object.entries(secondaryByCat).map(([cat, list]) => (
                    <div
                      key={cat}
                      className="workspace-hifi__archive-secondary-bucket"
                    >
                      <h5 className="workspace-hifi__archive-secondary-title">
                        {CATEGORY_LABELS_FULL[cat] || cat}
                      </h5>
                      <ul className="workspace-hifi__archive-list">
                        {list.map((entry) => {
                          const isNew =
                            Date.now() - parseTs(entry.captured_at) <
                            NEW_WINDOW_MS;
                          return (
                            <ArchiveEntryCard
                              key={entry.id}
                              sessionId={sessionId}
                              entry={entry}
                              isNew={isNew}
                              onEdited={handleEntryEdited}
                              onDeleted={handleEntryDeleted}
                              onToast={showToast}
                              onResyncClick={(e) => onStartPlanMode?.(String(e.category), e.id)}
                            />
                          );
                        })}
                      </ul>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── A-7 引导 banner (始终在底部) ─────────────────────────── */}
          <div className="workspace-hifi__archive-cta">
            <div className="workspace-hifi__archive-cta-text">
              {total === 0
                ? '档案还是空的 — 让 AI 跟你聊聊每段经历,自动归档。'
                : '想把某段经历聊得更细?切到 coach,AI 会带你 4 个 anchor 补齐。'}
            </div>
            <button
              type="button"
              className="workspace-hifi__archive-cta-btn"
              onClick={handlePlanModeBanner}
            >
              📌 让 AI 跟你聊聊每段经历
            </button>
          </div>

          {toast && (
            <div
              className="workspace-hifi__archive-toast"
              role="status"
              aria-live="polite"
            >
              {toast}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
