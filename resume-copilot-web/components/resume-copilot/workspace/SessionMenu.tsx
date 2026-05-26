'use client';

/**
 * SessionMenu — 320px dropdown anchored to the session-chip in TopTrackBar.
 *
 * Lists the 最近 3 个 sessions (`GET /api/resume-copilot/sessions` slice 3 — call
 * deferred to the menu's first open so the workspace doesn't pay for it when
 * the dropdown is closed). Current session is highlighted with
 * `var(--terracotta-wash)`. Bottom row links to upload + the full sessions
 * page.
 *
 * Switching sessions does a full router.push('/resume-copilot?sessionId=N') —
 * 决策 ⑦a (任务说明里指明) — 整页 navigate,不做原地 swap。 这让 useEffect 链
 * 简单很多 (session 重 load / 推荐重拉 / chat 历史重拉 都走 React mount path)。
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import { I } from '@/components/hifi/hifi-primitives';
import { listResumeCopilotSessions } from '../api';
import type { ResumeCopilotSessionListItem } from '../types';

interface SessionMenuProps {
  open: boolean;
  currentSessionId: number | null;
  onClose: () => void;
}

function shortLabel(s: ResumeCopilotSessionListItem): string {
  const raw = (s.name && s.name.trim()) || s.file_name || `会话 #${s.id}`;
  return raw.length > 24 ? `${raw.slice(0, 22)}…` : raw;
}

function shortTime(iso: string | null): string {
  if (!iso) return '—';
  const ts = new Date(iso).getTime();
  if (!Number.isFinite(ts)) return '';
  const diffMs = Date.now() - ts;
  if (diffMs < 0) return '刚刚';
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (diffMs < 5 * minute) return '刚刚';
  if (diffMs < hour) return `${Math.floor(diffMs / minute)} 分前`;
  if (diffMs < day) return `${Math.floor(diffMs / hour)} 时前`;
  if (diffMs < 30 * day) return `${Math.floor(diffMs / day)} 天前`;
  return new Date(iso).toLocaleDateString('zh-CN');
}

export function SessionMenu({ open, currentSessionId, onClose }: SessionMenuProps) {
  const router = useRouter();
  const [items, setItems] = useState<ResumeCopilotSessionListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Lazy fetch — only when menu opens for the first time, then keep cached.
  const hasFetched = useRef(false);
  useEffect(() => {
    if (!open || hasFetched.current) return;
    hasFetched.current = true;
    let cancelled = false;
    const run = async () => {
      try {
        const rows = await listResumeCopilotSessions();
        if (cancelled) return;
        setItems(rows ?? []);
      } catch (err: unknown) {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    setLoading(true);
    setError(null);
    void run();
    return () => {
      cancelled = true;
    };
  }, [open]);

  // Close on outside click + Esc.
  useEffect(() => {
    if (!open) return;
    const handlePointer = (e: MouseEvent) => {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    // Pointer listener is registered on next tick so the same click that
    // opened the menu doesn't immediately close it.
    const id = window.setTimeout(() => {
      window.addEventListener('mousedown', handlePointer);
    }, 0);
    window.addEventListener('keydown', handleKey);
    return () => {
      window.clearTimeout(id);
      window.removeEventListener('mousedown', handlePointer);
      window.removeEventListener('keydown', handleKey);
    };
  }, [open, onClose]);

  const handleSwitch = useCallback(
    (sessionId: number) => {
      onClose();
      if (sessionId === currentSessionId) return;
      router.push(`/resume-copilot?sessionId=${sessionId}`);
    },
    [router, currentSessionId, onClose],
  );

  const handleUpload = useCallback(() => {
    onClose();
    router.push('/upload');
  }, [router, onClose]);

  const handleManageAll = useCallback(() => {
    onClose();
    router.push('/resume-copilot/sessions');
  }, [router, onClose]);

  if (!open) return null;

  const top3 = items.slice(0, 3);

  return (
    <div
      ref={containerRef}
      className="workspace-hifi__session-menu"
      role="menu"
      data-testid="workspace-session-menu"
    >
      <div className="workspace-hifi__session-menu-overline">最近会话</div>
      {loading ? (
        <div className="workspace-hifi__session-menu-empty">
          <span className="hf-spin" aria-hidden style={{ marginRight: 6 }} />
          加载中…
        </div>
      ) : error ? (
        <div className="workspace-hifi__session-menu-empty">加载失败 · {error}</div>
      ) : top3.length === 0 ? (
        <div className="workspace-hifi__session-menu-empty">还没有会话 — 上传第一份简历开始</div>
      ) : (
        <div className="workspace-hifi__session-menu-list" role="none">
          {top3.map((s) => {
            const isCurrent = s.id === currentSessionId;
            return (
              <button
                type="button"
                key={s.id}
                onClick={() => handleSwitch(s.id)}
                className="workspace-hifi__session-menu-item"
                data-current={isCurrent ? 'true' : 'false'}
                role="menuitem"
              >
                <span className="workspace-hifi__session-menu-avatar" aria-hidden>
                  {I.user(13)}
                </span>
                <span className="workspace-hifi__session-menu-text">
                  <span className="workspace-hifi__session-menu-name">{shortLabel(s)}</span>
                  <span className="workspace-hifi__session-menu-meta">
                    {s.is_archived ? '归档 · ' : ''}
                    {shortTime(s.updated_at)}
                  </span>
                </span>
                {isCurrent ? (
                  <span className="workspace-hifi__session-menu-current-dot" aria-hidden>
                    {I.check(11)}
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>
      )}

      <div className="workspace-hifi__session-menu-divider" aria-hidden />

      <button
        type="button"
        onClick={handleUpload}
        className="workspace-hifi__session-menu-footer-link"
        role="menuitem"
      >
        <span style={{ display: 'inline-flex' }} aria-hidden>{I.upload(13)}</span>
        <span>上传新简历 · 开始新会话</span>
      </button>
      <button
        type="button"
        onClick={handleManageAll}
        className="workspace-hifi__session-menu-footer-link"
        role="menuitem"
      >
        <span>管理全部简历</span>
        <span style={{ display: 'inline-flex', marginLeft: 'auto' }} aria-hidden>
          {I.arrowRight(12)}
        </span>
      </button>
    </div>
  );
}
