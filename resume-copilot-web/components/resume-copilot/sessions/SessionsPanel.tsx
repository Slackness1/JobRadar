'use client';

/**
 * SessionsPanel — main shell for `/resume-copilot/sessions` ("我的简历会话").
 *
 * Layout:
 *   .hf .rc-sessions
 *     topbar  (HFLogo / breadcrumb / back-to-workspace / user avatar)
 *     page header (overline + h1 + blurb)
 *     toolbar (filter tabs + search placeholder + sort select)
 *     3-col grid (SessionCard × N + UploadCard at end)
 *     footer tip (delete policy reminder)
 *
 * Data: `GET /api/resume-copilot/sessions` via `listResumeCopilotSessions`.
 * Stats / topPicks are P0a 占位 (default 0 / []); 真值聚合留 P2.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import { HFBtn, HFLogo, I } from '@/components/hifi/hifi-primitives';
import { GuideModal } from '@/components/onboarding/GuideModal';
import { GuidePanel } from '@/components/onboarding/GuidePanel';
import { hasSeenGuide, markGuideSeen } from '@/components/onboarding/guide-seen';
import {
  deleteResumeCopilotSession,
  duplicateResumeCopilotSession,
  isAuthenticated,
  isGuestUser,
  listResumeCopilotSessions,
} from '../api';
import type { ResumeCopilotSessionListItem } from '../types';

import { SessionCard, type SessionCardData } from './SessionCard';
import { UploadCard } from './UploadCard';
import { SessionsToolbar, type SessionFilter, type SessionSort } from './SessionsToolbar';

import './sessions-theme.css';

// Stable colors for thumbnail accent — cycles per-index so each card looks
// slightly different without needing a backend field.
const COVER_PALETTE = [
  '#fdebe2',
  '#f5e8d6',
  '#e8eef0',
  '#ece6da',
  '#f0e6e2',
  '#e6ece6',
];

function pickCover(idx: number): string {
  return COVER_PALETTE[idx % COVER_PALETTE.length];
}

// 每账号"在使用中"(非归档)简历上限 — 与后端 MAX_ACTIVE_SESSIONS 对齐。
const MAX_ACTIVE_SESSIONS = 3;

function compareSessions(a: ResumeCopilotSessionListItem, b: ResumeCopilotSessionListItem, sort: SessionSort): number {
  if (sort === 'name') {
    return (a.name || a.file_name || '').localeCompare(b.name || b.file_name || '', 'zh-CN');
  }
  const aTs = sort === 'created' ? a.created_at : a.updated_at;
  const bTs = sort === 'created' ? b.created_at : b.updated_at;
  const aMs = aTs ? new Date(aTs).getTime() : 0;
  const bMs = bTs ? new Date(bTs).getTime() : 0;
  return bMs - aMs;
}

export function SessionsPanel() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const currentSessionId = useMemo(() => {
    const raw = searchParams.get('sessionId') ?? searchParams.get('session_id');
    const n = Number(raw);
    return Number.isFinite(n) && n > 0 ? n : null;
  }, [searchParams]);

  const [sessions, setSessions] = useState<ResumeCopilotSessionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filter, setFilter] = useState<SessionFilter>('active');
  const [sort, setSort] = useState<SessionSort>('updated');
  const [guideOpen, setGuideOpen] = useState(false);

  useEffect(() => {
    // Sessions are user-scoped via X-Resume-User-Key (api.ts handles that
    // automatically from localStorage). For un-logged users we still call so
    // backend returns an empty list — keeps the UX consistent with login bypass.
    let cancelled = false;
    const run = async () => {
      try {
        const items = await listResumeCopilotSessions();
        if (cancelled) return;
        setSessions(items ?? []);
      } catch (err: unknown) {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        setSessions([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!hasSeenGuide()) {
      setGuideOpen(true);
    }
  }, []);

  // ── Derived ─────────────────────────────────────────────────────────────
  const activeCount = useMemo(
    () => sessions.filter((s) => !s.is_archived).length,
    [sessions],
  );
  const archivedCount = useMemo(
    () => sessions.filter((s) => !!s.is_archived).length,
    [sessions],
  );

  const visibleSessions = useMemo(() => {
    const filtered = sessions.filter((s) => {
      if (filter === 'active') return !s.is_archived;
      if (filter === 'archived') return !!s.is_archived;
      return true;
    });
    return [...filtered].sort((a, b) => compareSessions(a, b, sort));
  }, [sessions, filter, sort]);

  const cards = useMemo<SessionCardData[]>(() => {
    return visibleSessions.map((s, idx) => ({
      ...s,
      isCurrent: currentSessionId === s.id,
      // 2026-05-29: 用列表接口回的真实摘要 (没回时回退占位)。
      trackTitle: (s.track && s.track.trim()) || '尚未选定赛道',
      trackIcon: 'target',
      coverColor: pickCover(idx),
      stats: {
        companies: s.n_companies ?? 0,
        jobs: s.n_jobs ?? 0,
        intel: 0, // 同辈情报数据待重新入库, 暂 0
        rewrites: 0,
      },
      topPicks: s.top_companies ?? [],
    }));
  }, [visibleSessions, currentSessionId]);

  // ── Handlers ────────────────────────────────────────────────────────────
  const handleSwitch = useCallback(
    (sessionId: number) => {
      router.push(`/resume-copilot?sessionId=${sessionId}`);
    },
    [router],
  );

  const handleUpload = useCallback(() => {
    router.push('/upload');
  }, [router]);

  // ⋯ 菜单 → 删除 / 复制。busyId 防重复点。
  const [busyId, setBusyId] = useState<number | null>(null);
  const handleDelete = useCallback(
    async (sessionId: number) => {
      const target = sessions.find((s) => s.id === sessionId);
      const label =
        (target?.name && target.name.trim()) || target?.file_name || `会话 #${sessionId}`;
      const ok = window.confirm(
        `删除「${label}」?\n会同时清掉这份简历的推荐 / 同辈情报 / Coach 拆解 / 改写记录,且不可恢复。`,
      );
      if (!ok) return;
      setBusyId(sessionId);
      try {
        await deleteResumeCopilotSession(sessionId);
        setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        window.alert(`删除失败: ${msg}`);
      } finally {
        setBusyId(null);
      }
    },
    [sessions],
  );
  const handleDuplicate = useCallback(
    async (sessionId: number) => {
      setBusyId(sessionId);
      try {
        const dup = await duplicateResumeCopilotSession(sessionId);
        // 新副本插到列表最前 (后端已按 updated_at desc, 这里乐观前插)
        setSessions((prev) => [dup, ...prev]);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        window.alert(
          /\b409\b|上限/.test(msg)
            ? '在使用中的简历已达 3 份上限,请先删除或归档一份再复制。'
            : `复制失败: ${msg}`,
        );
      } finally {
        setBusyId(null);
      }
    },
    [],
  );

  const handleBackToWorkspace = useCallback(() => {
    if (currentSessionId) {
      router.push(`/resume-copilot?sessionId=${currentSessionId}`);
    } else {
      router.push('/resume-copilot');
    }
  }, [router, currentSessionId]);

  const closeGuide = () => {
    markGuideSeen();
    setGuideOpen(false);
  };
  const startFromGuide = () => {
    markGuideSeen();
    setGuideOpen(false);
    router.push('/upload');
  };

  // Display name for top-right avatar — same logic as hifi-hero.
  const avatarLabel = (() => {
    if (typeof window === 'undefined') return '';
    if (isAuthenticated()) return 'U';
    if (isGuestUser()) return 'G';
    return '?';
  })();

  return (
    <div className="hf">
      <div className="rc-sessions" data-testid="rc-sessions-panel">
        {/* Top bar */}
        <div className="rc-sessions__topbar">
          <HFLogo size="sm" />
          <span className="rc-sessions__crumb-sep">/</span>
          <span className="rc-sessions__crumb">Resume Copilot</span>
          <span className="rc-sessions__crumb-sep">/</span>
          <span className="rc-sessions__crumb-current">我的简历会话</span>
          <div className="rc-sessions__topbar-spacer" />
          <HFBtn variant="link" size="sm" icon={I.book(14)} onClick={() => setGuideOpen(true)}>
            怎么用
          </HFBtn>
          {currentSessionId ? (
            <HFBtn
              variant="ghost"
              size="sm"
              onClick={handleBackToWorkspace}
              icon={I.arrowRight(13)}
            >
              回到工作台
            </HFBtn>
          ) : null}
          <div className="rc-sessions__user-avatar" aria-hidden>
            {avatarLabel ? (
              <span style={{ fontSize: 12, fontWeight: 600 }}>{avatarLabel}</span>
            ) : (
              I.user(15)
            )}
          </div>
        </div>

        {/* Page body */}
        <div className="rc-sessions__page">
          <div className="hf-overline rc-sessions__hero-overline">Sessions</div>
          <h1 className="hf-h1 rc-sessions__hero-title">我的简历会话</h1>
          <p className="hf-body rc-sessions__hero-blurb">
            每份简历是一个独立会话 — 自己的推荐排序 / 同辈情报缓存 / Coach 拆解记录 /
            bullet 改写历史。换赛道时建议开新会话,不要覆盖原版。
          </p>

          <SessionsToolbar
            filter={filter}
            onFilterChange={setFilter}
            sort={sort}
            onSortChange={setSort}
            activeCount={activeCount}
            archivedCount={archivedCount}
          />

          {error ? (
            <div className="rc-sessions__empty" role="alert">
              <div className="rc-sessions__empty-title">加载失败</div>
              <div className="rc-sessions__empty-blurb">
                {error || '稍后再试一次,或先上传一份新简历开始。'}
              </div>
            </div>
          ) : loading ? (
            <div className="rc-sessions__empty" aria-busy="true">
              <span className="hf-spin" aria-hidden />
              <div className="rc-sessions__empty-blurb">加载会话列表中…</div>
            </div>
          ) : cards.length === 0 && filter !== 'all' ? (
            <div className="rc-sessions__grid">
              <UploadCard onUpload={handleUpload} />
            </div>
          ) : (
            <div className="rc-sessions__grid">
              {cards.map((c) => (
                <SessionCard
                  key={c.id}
                  data={c}
                  onSwitch={handleSwitch}
                  onDuplicate={handleDuplicate}
                  onDelete={handleDelete}
                  duplicateDisabled={activeCount >= MAX_ACTIVE_SESSIONS}
                  busy={busyId === c.id}
                />
              ))}
              {activeCount >= MAX_ACTIVE_SESSIONS ? (
                <div className="rc-sessions__limit-card">
                  <div className="rc-sessions__limit-title">在用简历已达 {MAX_ACTIVE_SESSIONS} 份上限</div>
                  <div className="rc-sessions__limit-blurb">
                    想试新赛道?先删除或归档一份(归档不占额),再上传或复制。
                  </div>
                </div>
              ) : (
                <UploadCard onUpload={handleUpload} />
              )}
            </div>
          )}

          {/* Footer tip */}
          <div className="rc-sessions__footer-tip">
            <span className="rc-sessions__footer-tip-icon" aria-hidden>
              {I.shield(15)}
            </span>
            <span>
              每份简历独立 cache。删除会话会同时清掉 unlocked 情报 + Coach 拆解记录,确认前会再问一次。
            </span>
          </div>
        </div>
        <GuideModal open={guideOpen} onClose={closeGuide}>
          <GuidePanel onStart={startFromGuide} onDismiss={closeGuide} />
        </GuideModal>
      </div>
    </div>
  );
}
