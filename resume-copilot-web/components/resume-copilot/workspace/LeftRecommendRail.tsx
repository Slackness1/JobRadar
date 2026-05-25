'use client';

/**
 * LeftRecommendRail — 左栏推荐 (FE-2 实装 of E-2 / D-1 / D-2 / D-3 / E-4).
 *
 * 职责:
 *   - 渲染 recommendations.items(已被 BE-3 过滤:top10 + 50 分 + 排除 rejected)
 *   - 卡片展开/收起 — 同时只允许 1 张展开,父统一管 `expandedJobId`
 *   - ✗ 反馈 inline 表单(在卡片内,不是 modal)— 调 POST .../reject
 *   - 1.5s FLIP 柔和重排动画(reject 移除一条 / 列表顺序变化)
 *   - 第一次进工作台时,如果检测到本会话新增 reject 数,顶部 banner
 *     「👍 已记你不喜欢 X 条,已排除」。localStorage 记
 *     `jobradar.workspace.lastSeenRejectedCount.<sessionId>` 做对比。
 *
 * 不动:
 *   - HiFi tokens(只用,scope 严格 `.workspace-hifi`)
 *   - WorkspaceShell signature(只追加可选 prop,不破坏)
 *   - 其他 panes(FE-3/FE-4 负责)
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { I } from '@/components/hifi/hifi-primitives';
import type {
  ResumeCopilotSession,
  ResumeRecommendationItem,
  ResumeRecommendationPlatform,
  ResumeRecommendationResult,
} from '../types';
import {
  getResumeCopilotPlatforms,
  postRejectRecommendation,
  type RecommendRejectReason,
} from '../api';
import { CoachThinkingIndicator } from './chat/CoachThinkingIndicator';
import { PlatformCard } from './recommend/PlatformCard';
import { RecommendCard } from './recommend/RecommendCard';
import { useFlipAnimation } from './recommend/use-flip-animation';

const LAST_SEEN_KEY_PREFIX = 'jobradar.workspace.lastSeenRejectedCount.';
const TOAST_AUTO_DISMISS_MS = 2600;

export interface LeftRecommendRailProps {
  session: ResumeCopilotSession | null;
  recommendations: ResumeRecommendationResult | null;
  /** 学生点 ✗ 反馈触发(FE-2 → BE-3 D-2/D-3) */
  onRejectRecommendation?: (jobId: string, reason: string, note: string) => void;
  /** 学生点 "针对这家改写" 触发 — 跨栏信号给 RightResumePane 出 chat 思考 (C-6) */
  onRequestRewrite?: (jobId: string) => void;
  /** 推荐列表变化(reject 成功后)— 父可选择重新拉 recommendations。
   *  不传也 OK,本组件用本地 hidden set 做即时 UI 反馈。 */
  onRecommendationsChanged?: () => void;
  /** Plan ② Job plan-mode (2026-05-21): 学生在卡上点 "🎯 针对这家定制" 触发,
   *  父切到 plan-mode 并把 job_id 当作 chat turn 的 active_job_id 发回后端。 */
  onCustomiseForJob?: (item: ResumeRecommendationItem) => void;
}

function readLastSeen(sessionId: number | undefined): number {
  if (sessionId === undefined) return 0;
  if (typeof window === 'undefined') return 0;
  const raw = window.localStorage.getItem(`${LAST_SEEN_KEY_PREFIX}${sessionId}`);
  return Number(raw || '0') || 0;
}

function writeLastSeen(sessionId: number | undefined, count: number): void {
  if (sessionId === undefined) return;
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(`${LAST_SEEN_KEY_PREFIX}${sessionId}`, String(count));
}

export function LeftRecommendRail({
  session,
  recommendations,
  onRejectRecommendation,
  onRequestRewrite,
  onRecommendationsChanged,
  onCustomiseForJob,
}: LeftRecommendRailProps) {
  // FE-2 reserves this prop for future C-6 cross-pane signal (推荐卡 → 改写).
  void onRequestRewrite;

  // ── Local state ────────────────────────────────────────────────────────────
  // hiddenJobIds: 即时从 UI 隐藏的 jobId(reject 成功后)— 给 FLIP exit 动画
  const [hiddenJobIds, setHiddenJobIds] = useState<Set<string>>(() => new Set());
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [toast, setToast] = useState<string>('');
  const [bannerDismissed, setBannerDismissed] = useState<boolean>(false);
  // Platform view state (Phase 4)
  const [viewMode, setViewMode] = useState<'platform' | 'campus' | 'intern'>('platform');
  const [platforms, setPlatforms] = useState<ResumeRecommendationPlatform[] | null>(null);
  const [expandedCompany, setExpandedCompany] = useState<string | null>(null);
  const platformFetchingRef = useRef(false);

  // "Adjusting state when props change" idiom (React 19): track previous
  // recommendations via a setState rather than a ref (react-compiler bans ref
  // access during render). When upstream recommendations changes reference
  // (new generation / session switch), reset hidden + expanded + banner.
  const [lastRecSeen, setLastRecSeen] = useState<ResumeRecommendationResult | null>(
    recommendations,
  );
  if (recommendations !== lastRecSeen) {
    setLastRecSeen(recommendations);
    setHiddenJobIds(new Set());
    setExpandedJobId(null);
    setBannerDismissed(false);
    setPlatforms(null);
    setExpandedCompany(null);
  }

  const flip = useFlipAnimation<string>();

  // ── Derived list (filter out hidden ids) ───────────────────────────────────
  const allItems: ResumeRecommendationItem[] = useMemo(() => {
    const raw = recommendations?.items ?? [];
    if (hiddenJobIds.size === 0) return raw;
    return raw.filter((r) => !hiddenJobIds.has(String(r.job_id)));
  }, [recommendations, hiddenJobIds]);

  // 2026-05-20: split 校招 / 实习 — backend tags each item with
  // is_internship; show two tabs, default 校招.
  const campusItems = useMemo(
    () => allItems.filter((it) => !it.is_internship),
    [allItems],
  );
  const internItems = useMemo(
    () => allItems.filter((it) => it.is_internship),
    [allItems],
  );
  const items = viewMode === 'campus' ? campusItems : internItems;

  // Prefetch platform data as soon as session has recommendations.
  // (uses session?.id directly — sessionId alias is declared further below)
  const sid = session?.id;
  useEffect(() => {
    if (!sid || platforms !== null || platformFetchingRef.current) return;
    const recReady = recommendations !== null && (recommendations.items?.length ?? 0) > 0;
    if (!recReady) return;
    platformFetchingRef.current = true;
    getResumeCopilotPlatforms(sid)
      .then((r) => setPlatforms(r.platforms ?? []))
      .catch(() => setPlatforms([]))
      .finally(() => { platformFetchingRef.current = false; });
  }, [sid, platforms, recommendations]);

  // ── D-3 banner: first-time-after-reject 提示 (pure-derived) ───────────────
  // session.rejected_job_ids_json 没暴露给前端;改用 localStorage 跟本会话
  // 已隐藏数对比。banner 字符串完全是 derived value — 不在 effect 里 setState。
  const lastSeenRejected = useMemo(
    () => readLastSeen(session?.id),
    [session?.id],
  );
  const currentRejected = hiddenJobIds.size;
  const showBanner = !bannerDismissed && currentRejected > lastSeenRejected;
  const bannerText = showBanner
    ? `👍 已记你不喜欢 ${currentRejected - lastSeenRejected} 条,已从推荐排除`
    : '';

  // Persist the new "last seen" once the banner is shown (or refresh occurs).
  // Effect's only side effect is the localStorage write — no React setState.
  useEffect(() => {
    if (session?.id === undefined) return;
    writeLastSeen(session.id, currentRejected);
  }, [session?.id, currentRejected]);

  // Auto-dismiss toast.
  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(''), TOAST_AUTO_DISMISS_MS);
    return () => window.clearTimeout(t);
  }, [toast]);

  // ── Handlers ───────────────────────────────────────────────────────────────
  const handleToggle = useCallback(
    (jobId: string) => {
      setExpandedJobId((prev) => (prev === jobId ? null : jobId));
    },
    [],
  );

  const sessionId = session?.id;
  const handleReject = useCallback(
    async (jobId: string, reason: RecommendRejectReason, note: string) => {
      if (sessionId === undefined) return;
      // Notify parent (in case it wants to do analytics / log) — fire-and-forget.
      if (onRejectRecommendation) {
        try {
          onRejectRecommendation(jobId, reason, note);
        } catch {
          /* parent callback should not crash the reject flow */
        }
      }
      // POST the reject to BE-3 — this writes account_memory.preference and
      // appends jobId to session.rejected_job_ids_json so future recommends
      // exclude it.
      await postRejectRecommendation(sessionId, jobId, { reason, note });

      // FLIP: snapshot positions before mutating the visible list.
      flip.snapshot();
      setHiddenJobIds((prev) => {
        const next = new Set(prev);
        next.add(jobId);
        return next;
      });
      setExpandedJobId(null);
      setToast('👍 已记入档案');
      // Optional: let parent know it can refetch a fresh recommendations run.
      if (onRecommendationsChanged) {
        try { onRecommendationsChanged(); } catch { /* ignore */ }
      }
    },
    [sessionId, onRejectRecommendation, onRecommendationsChanged, flip],
  );

  // ── Render ─────────────────────────────────────────────────────────────────
  const sessionReady = session?.has_recommendations === true;
  const isGeneratingRecommendations = session?.recommendation_status === 'running';
  const jobsCount = viewMode === 'campus' ? campusItems.length : internItems.length;
  const totalCount = viewMode === 'platform' ? (platforms?.length ?? 0) : jobsCount;
  const isUnderfilled = sessionReady && viewMode !== 'platform' && jobsCount > 0 && jobsCount < 5;
  const isEmpty = sessionReady && viewMode !== 'platform' && jobsCount === 0;

  return (
    <aside className="workspace-hifi__pane workspace-hifi__pane--left" aria-label="推荐岗位">
      <header className="workspace-hifi__pane-header">
        <span className="workspace-hifi__pane-header-icon" aria-hidden>
          {I.radar(16)}
        </span>
        <span>推荐</span>
        <span className="workspace-hifi__pane-header-count">
          {sessionReady ? `${totalCount} 条` : '等待生成'}
        </span>
      </header>

      {sessionReady && (
        <div className="workspace-hifi__rec-tabs" role="tablist" aria-label="推荐视图">
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === 'platform'}
            className={`workspace-hifi__rec-tab${viewMode === 'platform' ? ' is-active' : ''}`}
            onClick={() => setViewMode('platform')}
          >
            平台 <span className="workspace-hifi__rec-tab-count">{platforms?.length ?? 0}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === 'campus'}
            className={`workspace-hifi__rec-tab${viewMode === 'campus' ? ' is-active' : ''}`}
            onClick={() => setViewMode('campus')}
          >
            校招 <span className="workspace-hifi__rec-tab-count">{campusItems.length}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === 'intern'}
            className={`workspace-hifi__rec-tab${viewMode === 'intern' ? ' is-active' : ''}`}
            onClick={() => setViewMode('intern')}
          >
            实习 <span className="workspace-hifi__rec-tab-count">{internItems.length}</span>
          </button>
        </div>
      )}

      <div className="workspace-hifi__pane-body">
        {showBanner && (
          <div className="workspace-hifi__rec-banner" role="status">
            <span>{bannerText}</span>
            <button
              type="button"
              className="workspace-hifi__rec-banner-dismiss"
              aria-label="关闭提示"
              onClick={() => setBannerDismissed(true)}
            >
              {I.close(11)}
            </button>
          </div>
        )}

        {!sessionReady && isGeneratingRecommendations && (
          <div className="workspace-hifi__rec-empty">
            <CoachThinkingIndicator
              active
              label="AI 正在生成推荐"
              orbSize={128}
              minVisibleMs={2500}
            />
            <span className="workspace-hifi__rec-empty-hint">
              正在结合你的赛道、城市和简历经历生成第一批岗位。
            </span>
          </div>
        )}

        {!sessionReady && !isGeneratingRecommendations && (
          <div className="workspace-hifi__rec-empty">
            <span className="workspace-hifi__rec-empty-title">等待生成推荐</span>
            <span className="workspace-hifi__rec-empty-hint">
              上传简历 + 确认偏好后,系统会基于赛道 + 经历推荐 top 10。
            </span>
          </div>
        )}

        {isEmpty && (
          <div className="workspace-hifi__rec-empty">
            <span className="workspace-hifi__rec-empty-title">暂无更多优质推荐</span>
            <span className="workspace-hifi__rec-empty-hint">
              当前赛道下没有达到 50 分门槛的岗位 — 试试换赛道,
              或检查偏好是不是卡得太死。
            </span>
          </div>
        )}

        {/* ── Platform view ─────────────────────────────────────────────── */}
        {sessionReady && viewMode === 'platform' && (
          <div className="workspace-hifi__rec-list" role="list">
            {platforms === null && (
              <div className="workspace-hifi__rec-empty">
                <CoachThinkingIndicator
                  active
                  label="正在聚合平台…"
                  orbSize={96}
                  minVisibleMs={0}
                />
              </div>
            )}
            {platforms !== null && platforms.map((p, idx) => (
              <div key={p.company} className="workspace-hifi__rec-list-item" role="listitem">
                <PlatformCard
                  platform={p}
                  rank={idx + 1}
                  isExpanded={expandedCompany === p.company}
                  onToggle={() =>
                    setExpandedCompany((prev) => (prev === p.company ? null : p.company))
                  }
                />
              </div>
            ))}
            {platforms !== null && platforms.length === 0 && (
              <div className="workspace-hifi__rec-empty">
                <span className="workspace-hifi__rec-empty-title">暂无平台数据</span>
                <span className="workspace-hifi__rec-empty-hint">
                  切到校招 / 实习 tab 查看原始推荐列表。
                </span>
              </div>
            )}
          </div>
        )}

        {/* ── Jobs view (campus / intern) ───────────────────────────────── */}
        {sessionReady && viewMode !== 'platform' && totalCount > 0 && (
          <div className="workspace-hifi__rec-list" role="list">
            {items.map((item, idx) => {
              const jobId = String(item.job_id);
              return (
                <div
                  key={jobId}
                  ref={flip.register(jobId)}
                  className="workspace-hifi__rec-list-item"
                  role="listitem"
                >
                  <RecommendCard
                    item={item}
                    rank={idx + 1}
                    isExpanded={expandedJobId === jobId}
                    onToggle={() => handleToggle(jobId)}
                    onReject={(reason, note) => handleReject(jobId, reason, note)}
                    onCustomiseForJob={onCustomiseForJob}
                    sessionId={sid}
                  />
                </div>
              );
            })}
          </div>
        )}

        {isUnderfilled && (
          <div className="workspace-hifi__rec-underfilled" role="note">
            <span aria-hidden>📭</span>
            <span>
              当前赛道高分岗位较少 — 试试调整偏好或换赛道扩面。
            </span>
          </div>
        )}
      </div>

      {toast && (
        <div className="workspace-hifi__rec-toast" role="status" aria-live="polite">
          {toast}
        </div>
      )}
    </aside>
  );
}
