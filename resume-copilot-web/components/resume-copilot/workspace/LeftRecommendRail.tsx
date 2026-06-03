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
  ResumeJobMode,
  ResumeRecommendationItem,
  ResumeRecommendationPlatform,
  ResumeRecommendationResult,
} from '../types';
import {
  getResumeCopilotJobMode,
  getResumeCopilotPlatforms,
  getPlatformsByTier,
  getTierFit,
  postRejectRecommendation,
  type PlatformSkeleton,
  type RecommendRejectReason,
  type TierFit,
} from '../api';
import { CoachThinkingIndicator } from './chat/CoachThinkingIndicator';
import { PlatformCard } from './recommend/PlatformCard';
import { PlatformTierGroup } from './recommend/PlatformTierGroup';
import { RecommendCard } from './recommend/RecommendCard';
import { TierLadderStrip } from './recommend/TierLadderStrip';
import { useFlipAnimation } from './recommend/use-flip-animation';
import { WorkspaceThinkingTimeline } from './WorkspaceThinkingTimeline';

const LAST_SEEN_KEY_PREFIX = 'jobradar.workspace.lastSeenRejectedCount.';
const TOAST_AUTO_DISMISS_MS = 2600;

const platformsCache = new Map<number, ResumeRecommendationPlatform[]>();
const jobModeCache = new Map<number, ResumeJobMode>();
const tierFitCache = new Map<string, TierFit | null>();
const platformSkeletonCache = new Map<string, PlatformSkeleton>();

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
  /** P0b — 学生点小红书 badge 或卡内 "同辈情报" 按钮触发. 父切右栏到 IntelDrawer。 */
  onOpenIntel?: (
    company: string,
    ctx?: { priority?: string | null; xhsCount?: number | null; jobId?: number | null },
  ) => void;
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
  onOpenIntel,
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
  // Phase G tier skeleton — multi-card expand uses Set (not single string)
  const [expandedCompanies, setExpandedCompanies] = useState<Set<string>>(() => new Set());
  const platformFetchingRef = useRef(false);
  // Phase G梯队骨架 state
  const [platformSkeleton, setPlatformSkeleton] = useState<PlatformSkeleton | null>(null);
  // 已拉过骨架的 sub_cat（undefined=未初始化, null=无 sub_cat, string=已拉过的赛道）
  const skeletonFetchedSubCatRef = useRef<string | null | undefined>(undefined);
  // Phase G G2-D — 求职模式判定 (实习/全职/both) + 默认 tab + 解释 banner
  const [jobMode, setJobMode] = useState<ResumeJobMode | null>(null);
  const jobModeFetchingRef = useRef(false);
  const [modeBannerDismissed, setModeBannerDismissed] = useState<boolean>(false);
  // Phase G — 档次阶梯条
  const [tierFit, setTierFit] = useState<TierFit | null>(null);
  const tierFitFetchingRef = useRef(false);
  // track the sub_cat for which tierFit was last fetched (state so it's ok to reset during render)
  const [tierFitSubCat, setTierFitSubCat] = useState<string | null>(null);

  // "Adjusting state when props change" idiom (React 19): track previous
  // recommendations via a setState rather than a ref (react-compiler bans ref
  // access during render). When upstream recommendations changes reference
  // (new generation / session switch), reset hidden + expanded + banner.
  //
  // ⚠️ 不能用对象引用 (recommendations !== prev) 当触发条件：父组件在生成中
  // 每 1.6s 轮询一次 setRecommendations(新对象)，引用每轮都变，会导致下面
  // setJobMode(null)/setPlatformSkeleton(null) 每轮触发 → 主推 banner + 梯队骨架
  // 一闪一闪、骨架加载完又被抹回"继续思考"。改用内容签名：只有真正换了会话 /
  // 换了一代推荐（条数 / 首个岗位变了）才 reset，内容相同的轮询不动 UI 状态。
  const recSignature = recommendations
    ? `${recommendations.session_id}:${recommendations.status}:${recommendations.items.length}:${recommendations.items[0]?.job_id ?? ''}`
    : null;
  const [lastRecSig, setLastRecSig] = useState<string | null>(recSignature);
  if (recSignature !== lastRecSig) {
    setLastRecSig(recSignature);
    setHiddenJobIds(new Set());
    setExpandedJobId(null);
    setBannerDismissed(false);
    setPlatforms(null);
    setExpandedCompanies(new Set());
    setJobMode(null);
    setModeBannerDismissed(false);
    setTierFit(null);
    setTierFitSubCat(null);
    setPlatformSkeleton(null);
  }
  // recommendations 变化时通过 setPlatformSkeleton(null) 已触发重拉，
  // skeletonFetchedSubCatRef 的 reset 在 skeleton useEffect 内部处理（仅在 effect 里写 ref）

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

  // ⚠️ 这几个派生数据拉取 effect **绝不能依赖 recommendations / jobMode 对象本身**。
  // 父组件在生成中每 1.6s 轮询一次就换一个新 recommendations 对象引用，若把它放进
  // 依赖数组，effect 每轮都重跑、cleanup 每轮都 abort() 掉正在飞的请求；骨架请求被
  // abort 后又被 skeletonFetchedSubCatRef 标记"已试过"不再重试 → 永远卡在
  // "正在加载梯队骨架…"。改成只依赖稳定的 recReady(布尔) + primarySubCat(字符串)：
  // 轮询不再触发重跑/abort，请求一次拉到底。
  const recReady = recommendations !== null && (recommendations.items?.length ?? 0) > 0;
  const primarySubCat = jobMode?.primary_sub_cat || undefined;

  useEffect(() => {
    if (!sid || platforms !== null || platformFetchingRef.current) return;
    if (!recReady) return;
    if (platformsCache.has(sid)) {
      queueMicrotask(() => setPlatforms(platformsCache.get(sid) ?? []));
      return;
    }
    platformFetchingRef.current = true;
    getResumeCopilotPlatforms(sid)
      .then((r) => {
        const next = r.platforms ?? [];
        platformsCache.set(sid, next);
        setPlatforms(next);
      })
      .catch(() => setPlatforms([]))
      .finally(() => { platformFetchingRef.current = false; });
  }, [sid, platforms, recReady]);

  // Phase G G2-D — 拉求职模式判定 (session ready 后一次)
  useEffect(() => {
    if (!sid || jobMode !== null || jobModeFetchingRef.current) return;
    if (!recReady) return;
    const cached = jobModeCache.get(sid);
    if (cached) {
      queueMicrotask(() => {
        setJobMode(cached);
      });
      return;
    }
    jobModeFetchingRef.current = true;
    getResumeCopilotJobMode(sid)
      .then((m) => {
        jobModeCache.set(sid, m);
        setJobMode(m);
      })
      .catch(() => setJobMode(null))
      .finally(() => { jobModeFetchingRef.current = false; });
  }, [sid, jobMode, recReady]);

  // Phase G — 拉档次阶梯条 (依赖 jobMode.primary_sub_cat; sub_cat 变化时重拉)
  // tierFit 移出依赖数组，仅靠 tierFitSubCat 判断是否已拉过，防止 catch 后无限重试
  useEffect(() => {
    if (!sid) return;
    if (!recReady) return;
    // 等 jobMode 落下来再拿 primary_sub_cat(若已 null 则用 undefined — 后端给默认值)
    const subCat = primarySubCat;
    const subCatKey = subCat ?? null;
    const cacheKey = `${sid}:${subCatKey ?? ''}`;
    if (tierFitCache.has(cacheKey)) {
      queueMicrotask(() => {
        setTierFit(tierFitCache.get(cacheKey) ?? null);
        setTierFitSubCat(subCatKey);
      });
      return;
    }
    // 已经拉过这个 sub_cat（无论成功/失败）就不再重试
    if (tierFitFetchingRef.current) return;
    if (tierFitSubCat === subCatKey) return;
    tierFitFetchingRef.current = true;
    const controller = new AbortController();
    getTierFit(sid, subCat)
      .then((r) => {
        if (!controller.signal.aborted) {
          tierFitCache.set(cacheKey, r);
          setTierFit(r);
          setTierFitSubCat(subCatKey);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          // 标记"这个赛道试过了"，防止无限重试
          tierFitCache.set(cacheKey, null);
          setTierFitSubCat(subCatKey);
          setTierFit(null);
        }
      })
      .finally(() => { tierFitFetchingRef.current = false; });
    return () => { controller.abort(); };
  }, [sid, recReady, primarySubCat, tierFitSubCat]);

  // Phase G — 拉梯队骨架 (依赖 jobMode.primary_sub_cat; sub_cat 变化时重拉)
  // skeletonFetchedSubCatRef 仅在 effect 内读写，防止 catch(null) 后无限重试。
  // recommendations reset 时 setPlatformSkeleton(null) + setJobMode(null) 已触发重拉。
  useEffect(() => {
    if (!sid || !recReady) return;
    const subCat = primarySubCat;
    const subCatKey = subCat ?? null;
    // 主推实习的学生(default_tab==='intern')→ 骨架在招岗实习优先,不被校招挤出 LIMIT 5。
    const skMode = jobMode?.default_tab === 'intern' ? 'intern' : undefined;
    // guard key 带 sid + mode：换简历/换模式 key 必变 → 正常重拉。
    const guardKey = `${sid}:${subCatKey ?? ''}:${skMode ?? ''}`;
    const cached = platformSkeletonCache.get(guardKey);
    if (cached) {
      skeletonFetchedSubCatRef.current = guardKey;
      queueMicrotask(() => setPlatformSkeleton(cached));
      return;
    }
    // 本 (会话,赛道,模式) 已发起过就不重复发(在飞的 .then 会自己落)。
    if (skeletonFetchedSubCatRef.current === guardKey) return;
    skeletonFetchedSubCatRef.current = guardKey;
    // ⚠️ 不要用 AbortController：deps churn(jobMode 落地翻 primarySubCat/default_tab)
    // 会让 effect 重跑,cleanup 一 abort 就把已 200 的请求丢掉 → platformSkeleton 永远
    // 是 null → 永久"正在加载梯队骨架"。这里不 abort,让请求落地;靠 guardKey 去重 +
    // 落地时校验 key 仍匹配,避免切换被旧结果覆盖。
    getPlatformsByTier(sid, subCat, skMode)
      .then((r) => {
        platformSkeletonCache.set(guardKey, r);
        if (skeletonFetchedSubCatRef.current === guardKey) setPlatformSkeleton(r);
      })
      .catch(() => {
        // 失败兜底成"无骨架"(渲染走扁平在招列表),绝不让它停在永久转圈。
        if (skeletonFetchedSubCatRef.current === guardKey) {
          setPlatformSkeleton({ sub_cat: subCat ?? '', has_skeleton: false, tiers: [] } as PlatformSkeleton);
        }
      });
  }, [sid, recReady, primarySubCat, jobMode?.default_tab]);

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

  // Phase G 梯队骨架 — 多卡展开/收起 (Set, not mutual-exclusive)
  const handleCompanyToggle = useCallback((companyName: string) => {
    setExpandedCompanies((prev) => {
      const next = new Set(prev);
      if (next.has(companyName)) {
        next.delete(companyName);
      } else {
        next.add(companyName);
      }
      return next;
    });
  }, []);

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
  // 推荐是否"可展示"只看 items 快照。`session.has_recommendations` 是后端
  // 会话级摘要,生成中第一批规则结果已落库时可能仍为 false；如果这里继续绑它,
  // 首次上传会只看到轻量列表/等待态,平台梯队骨架不进入渲染。
  const sessionReady = recReady;
  const isGeneratingRecommendations = session?.recommendation_status === 'running';
  const hasEmptyRecommendationSnapshot = recommendations !== null && !recReady && !isGeneratingRecommendations;
  const jobsCount = viewMode === 'campus' ? campusItems.length : internItems.length;
  const platformTotalCount = platformSkeleton?.has_skeleton
    ? platformSkeleton.tiers.reduce((acc, t) => acc + t.companies.length, 0)
    : (platforms?.length ?? 0);
  const totalCount = viewMode === 'platform' ? platformTotalCount : jobsCount;
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
        <>
          <div className="workspace-hifi__rec-tabs" role="tablist" aria-label="推荐视图">
            <button
              type="button"
              role="tab"
              aria-selected={viewMode === 'platform'}
              className={`workspace-hifi__rec-tab${viewMode === 'platform' ? ' is-active' : ''}`}
              onClick={() => setViewMode('platform')}
            >
              平台 <span className="workspace-hifi__rec-tab-count">{platformTotalCount}</span>
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
            <button
              type="button"
              className="workspace-hifi__rec-tabs-radar"
              title="重新推荐"
              aria-label="重新推荐"
              onClick={() => {
                // P0b placeholder — P1 wire to refresh recommendations.
                console.log('[LeftRecommendRail] re-recommend — P1');
              }}
            >
              {I.radar(16)}
            </button>
          </div>
          {/* Phase G G2-D — 求职模式解释 banner (时点×门槛×经历 → 主推策略) */}
          {jobMode && jobMode.advice_text && !modeBannerDismissed && (
            <div className="workspace-hifi__mode-banner" role="note">
              <div className="workspace-hifi__mode-banner-head">
                <span className="workspace-hifi__mode-banner-tag">{jobMode.mode_label}</span>
                {jobMode.stage_label && (
                  <span className="workspace-hifi__mode-banner-stage">
                    {jobMode.stage_inferred
                      ? `按简历推断：${jobMode.stage_label}（可在偏好里改）`
                      : jobMode.stage_label}
                  </span>
                )}
                <button
                  type="button"
                  className="workspace-hifi__mode-banner-close"
                  aria-label="收起"
                  onClick={() => setModeBannerDismissed(true)}
                >
                  ✕
                </button>
              </div>
              <p className="workspace-hifi__mode-banner-body">{jobMode.advice_text}</p>
              {jobMode.advice_evidence && (
                <p className="workspace-hifi__mode-banner-evidence">
                  依据 · {jobMode.advice_evidence}
                </p>
              )}
            </div>
          )}
          {/* P0b — 过滤行 (视觉 placeholder,不接 filter 逻辑) */}
          <div className="workspace-hifi__rec-filter-row" aria-hidden>
            <span className="hf-pill">行业 ▾</span>
            <span className="hf-pill">优先级 ▾</span>
            <span className="hf-pill terra">有情报</span>
            <span className="workspace-hifi__rec-filter-count">
              {totalCount} → {totalCount}
            </span>
          </div>
        </>
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

        {/* PROG-T5: 看得见的思考 — 时间线(组件自带空/进行中/完成收一行三态) */}
        <WorkspaceThinkingTimeline
          trace={recommendations?.agent_trace ?? []}
          running={isGeneratingRecommendations}
        />

        {/* PROG-T5: 生成中且已到第一批部分结果 — 先铺轻量列表(不走 platform/骨架机制) */}
        {!sessionReady && recReady && (
          <div className="workspace-hifi__rec-list" role="list">
            {(recommendations?.items ?? []).map((item, idx) => {
              const jobId = String(item.job_id);
              return (
                <div
                  key={jobId}
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
                    onOpenIntel={onOpenIntel}
                  />
                </div>
              );
            })}
          </div>
        )}

        {!sessionReady && isGeneratingRecommendations && !recReady && (
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

        {!sessionReady && hasEmptyRecommendationSnapshot && (
          <div className="workspace-hifi__rec-empty">
            <span className="workspace-hifi__rec-empty-title">暂无可展示推荐</span>
            <span className="workspace-hifi__rec-empty-hint">
              这份简历上一次推荐没有留下可展示岗位；这不是后台仍在思考。
            </span>
          </div>
        )}

        {!sessionReady && !isGeneratingRecommendations && !hasEmptyRecommendationSnapshot && (
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
            {/* 档次阶梯条 — 平台 tab 顶部 (保留作"一句话定位+理由折叠") */}
            {tierFit && <TierLadderStrip data={tierFit} />}

            {/* ── 梯队骨架视图 (has_skeleton=true) ── */}
            {platformSkeleton === null && (
              <div className="workspace-hifi__rec-empty">
                <CoachThinkingIndicator
                  active
                  label="正在加载梯队骨架…"
                  orbSize={96}
                  minVisibleMs={0}
                />
              </div>
            )}

            {platformSkeleton !== null && platformSkeleton.has_skeleton && platformSkeleton.tiers.length > 0 && (
              <>
                {/* 顶部 intro 条 */}
                <div className="workspace-hifi__tier-intro-bar" role="note">
                  <span className="workspace-hifi__tier-intro-icon" aria-hidden>
                    {I.radar(15)}
                  </span>
                  <div className="workspace-hifi__tier-intro-text">
                    <strong>{platformSkeleton.sub_cat}</strong> 平台格局 · 按梯队展示。
                    <span className="workspace-hifi__tier-intro-live"> 在招</span>{' '}
                    与 <span className="workspace-hifi__tier-intro-none">暂无对口岗</span> 的头部公司都在，匹配档已高亮。
                  </div>
                </div>

                {/* 梯队分组 */}
                {platformSkeleton.tiers.map((tier, idx) => (
                  <PlatformTierGroup
                    key={tier.tier}
                    tier={tier}
                    expandedCompanies={expandedCompanies}
                    onToggle={handleCompanyToggle}
                    onOpenIntel={onOpenIntel ? (company, ctx) =>
                      onOpenIntel(company, { xhsCount: ctx?.n_insights ?? null })
                      : undefined
                    }
                    isFirst={idx === 0}
                    isLast={idx === platformSkeleton.tiers.length - 1}
                  />
                ))}

                {/* 底部说明 */}
                <div className="workspace-hifi__tier-footer" role="contentinfo">
                  骨架来自 GT 公司库 · 在招标记每日刷新
                </div>
              </>
            )}

            {/* ── 无骨架退化: 扁平在招列表 (has_skeleton=false) ── */}
            {platformSkeleton !== null && !platformSkeleton.has_skeleton && (
              <>
                <div className="workspace-hifi__tier-no-skeleton-notice" role="note">
                  <span className="workspace-hifi__tier-no-skeleton-icon" aria-hidden>📋</span>
                  <span>该赛道梯队数据整理中，先按在招平台展示。</span>
                </div>
                {/* 退化回原有 platforms 扁平列表 */}
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
                {platforms !== null && platforms.filter((p) => !p.is_fallback).map((p, idx) => (
                  <div key={p.company} className="workspace-hifi__rec-list-item" role="listitem">
                    <PlatformCard
                      platform={p}
                      rank={idx + 1}
                      isExpanded={expandedCompanies.has(p.company)}
                      onToggle={() => handleCompanyToggle(p.company)}
                      sessionId={sid}
                      onOpenIntel={onOpenIntel}
                    />
                  </div>
                ))}
                {platforms !== null && platforms.some((p) => p.is_fallback) && (
                  <div className="workspace-hifi__rec-fallback-divider" role="presentation">
                    <span className="workspace-hifi__rec-fallback-divider-label">
                      你的目标公司 · 本季暂未开新岗，按招聘窗口提前准备
                    </span>
                  </div>
                )}
                {platforms !== null && platforms.filter((p) => p.is_fallback).map((p, idx) => {
                  const liveCount = platforms.filter((x) => !x.is_fallback).length;
                  return (
                    <div key={`fb-${p.company}`} className="workspace-hifi__rec-list-item" role="listitem">
                      <PlatformCard
                        platform={p}
                        rank={liveCount + idx + 1}
                        isExpanded={expandedCompanies.has(p.company)}
                        onToggle={() => handleCompanyToggle(p.company)}
                        sessionId={sid}
                        onOpenIntel={onOpenIntel}
                      />
                    </div>
                  );
                })}
                {platforms !== null && platforms.length === 0 && (
                  <div className="workspace-hifi__rec-empty">
                    <span className="workspace-hifi__rec-empty-title">暂无平台数据</span>
                    <span className="workspace-hifi__rec-empty-hint">
                      切到校招 / 实习 tab 查看原始推荐列表。
                    </span>
                  </div>
                )}
              </>
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
                    onOpenIntel={onOpenIntel}
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
