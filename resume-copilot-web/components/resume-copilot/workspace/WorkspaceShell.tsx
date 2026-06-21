'use client';

/**
 * WorkspaceShell — `/resume-copilot` 三栏主工作台容器 (E-1 / E-5).
 *
 * 结构(top-down):
 *   .hf                              ← 项目 HiFi token scope (terracotta/parchment)
 *     .workspace-hifi                ← FE-1 工作台 layout scope
 *       <TopTrackBar/>               ← E-5 顶部 sticky bar(全宽)
 *       .workspace-hifi__grid        ← 三栏 grid(280 / fluid / 420)
 *         <LeftRecommendRail/>       ← E-2 / D-1..D-6 (FE-2 实装)
 *         <MiddleChatPane/>          ← B-1..B-4 / E-3 (FE-4 实装)
 *         <RightResumePane/>         ← A / C / E-3 (FE-3 + FE-4 实装)
 *
 * 设计系统隔离:
 *   - `.hf` 来自 `components/hifi/hifi-tokens.css` 已 scope(`:root` 没污染)
 *   - `.workspace-hifi` 来自本目录 `workspace-theme.css`,所有规则都 `.workspace-hifi ...`
 *   - 不会渗到 `/`、`/upload`、`/interview/*`
 */

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import type {
  CopilotMessage,
  ResumeCopilotSession,
  ResumeProfilePayload,
  ResumeRecommendationResult,
  ResumeRecommendationItem,
} from '../types';

import { TopTrackBar } from './TopTrackBar';
import { LeftRecommendRail } from './LeftRecommendRail';
import { MiddleChatPane } from './MiddleChatPane';
import { RightResumePane } from './RightResumePane';
import { RewriteProvider } from './RewriteContext';
import { ArchivePanel } from './archive/ArchivePanel';
import { ResizeHandle } from './ResizeHandle';
import { IntelDrawer } from './intel/IntelDrawer';
import type { CoachContext } from './coach/CoachPane';
import type { RewriteBulletContext } from './rewrite/RewritePane';
import type { RewriteV0V2Out } from '../api';

import './workspace-theme.css';

export interface WorkspaceShellProps {
  // ── Session / data ────────────────────────────────────────────────────────
  session: ResumeCopilotSession | null;
  profile: ResumeProfilePayload;
  recommendations: ResumeRecommendationResult | null;
  chatMessages: CopilotMessage[];

  // ── Loading flags ─────────────────────────────────────────────────────────
  isSendingChat: boolean;
  applyingOption: string | null;
  isExporting: boolean;
  canExport: boolean;
  isDemo: boolean;

  // ── Callbacks ─────────────────────────────────────────────────────────────
  sendChatMessage: (content: string, opts?: { activeJobId?: string }) => Promise<void>;
  applyRewriteOption: (messageId: number, optionId: string) => Promise<void>;
  refreshChatMessages?: () => Promise<void>;
  onExport: () => void;
  /** 学生在 TopTrackBar 点 "换赛道" — 跳 prefs 编辑或开 modal */
  onChangeTrack?: () => void;
  /** 学生在 RightResumePane 档案浮条点开 */
  onOpenArchive?: () => void;

  // ── 推荐栏 callback (FE-2) ────────────────────────────────────────────────
  /** 学生在左栏点 ✗ 反馈 — FE-2 内部已经 POST 了 reject,这里只用作 analytics
   *  / 日志 hook,父不需要再发请求 */
  onRejectRecommendation?: (jobId: string, reason: string, note: string) => void;
  /** 学生在左栏点 "针对这家改写" — 跨栏信号给 RightResumePane (C-6,FE-3) */
  onRequestRewrite?: (jobId: string) => void;
  /** 推荐列表变化 (reject 后) — 父可选择重新拉 recommendations 拿最新顺序 */
  onRecommendationsChanged?: () => void;

  // ── 占位 props（FE-2/3/4 实装时连后端） ───────────────────────────────────
  /** 顶部赛道 placeholder 数据,FE-2/P2-1 算法接入后真填 */
  currentTrackName?: string | null;
  currentFitScore?: number | null;

  // ── FE-4 wiring ───────────────────────────────────────────────────────────
  /** 当前用户 X-Resume-User-Key — api.ts 自己会从 localStorage 拿,这里传入主要
   *  让 ArchivePanel / chat 子组件做 user-scope 检查或 future toast. */
  xResumeUserKey?: string;
  /** 学生从 ArchivePanel 引导 banner 或档案 entry 触发 plan-mode (FE-4 B-2). */
  onStartPlanMode?: (focusKind: string, focusId?: number) => void;

  /** Called after the user clicks "确认" in the awaiting_user_confirmation
   *  overlay. Parent should re-fetch session so the workspace re-renders
   *  with the post-generate state. */
  onSessionConfirmed?: () => void;
}

export function WorkspaceShell(props: WorkspaceShellProps) {
  const {
    session,
    profile,
    recommendations,
    chatMessages,
    isSendingChat,
    applyingOption,
    isExporting,
    canExport,
    isDemo,
    sendChatMessage,
    applyRewriteOption,
    refreshChatMessages,
    onExport,
    onChangeTrack,
    onRejectRecommendation,
    onRequestRewrite,
    onRecommendationsChanged,
    currentTrackName = null,
    currentFitScore = null,
    xResumeUserKey,
    onStartPlanMode,
    // P2 (2026-05-26): retained for backward-compat with public-resume-copilot
    // but no longer triggered from this shell — confirm step moved to the
    // standalone `/resume-copilot/confirm` page, and a fresh workspace mount
    // post-confirm re-fetches the session naturally.
    onSessionConfirmed: _onSessionConfirmed,
  } = props;
  void _onSessionConfirmed;

  const router = useRouter();
  const needsConfirm = !!session && session.has_confirmed_profile === false;

  // P2 (2026-05-26): If the loaded session hasn't been confirmed yet,
  // redirect to the dedicated `/resume-copilot/confirm?session_id=N` page
  // instead of rendering the legacy in-workspace overlay. Effect-only (not
  // render-time) so SSR / first-paint stays stable. Once the student confirms
  // there, they return to the workspace with `has_confirmed_profile=true`
  // and this effect is a no-op (preventing redirect loops).
  useEffect(() => {
    if (needsConfirm && session) {
      router.push(`/resume-copilot/confirm?session_id=${session.id}`);
    }
  }, [needsConfirm, session, router]);

  // ── Resizable columns (FE-1 polish, 2026-05-20) ─────────────────────────
  // Persist user-chosen widths so they stick across reloads. Defaults match
  // the original CSS (280 / fluid / 420). Lazy initializer reads from
  // localStorage on first render (no useEffect state-set anti-pattern).
  const LEFT_KEY = 'jobradar.workspace.leftWidth';
  const RIGHT_KEY = 'jobradar.workspace.rightWidth';
  const DEFAULT_LEFT = 280;
  const DEFAULT_RIGHT = 420;
  const readStoredWidth = (key: string, fallback: number): number => {
    if (typeof window === 'undefined') return fallback;
    try {
      const v = Number(window.localStorage.getItem(key));
      if (v >= 200 && v <= 640) return v;
    } catch {
      /* no-op (SSR / private mode) */
    }
    return fallback;
  };
  const [leftWidth, setLeftWidth] = useState<number>(() => readStoredWidth(LEFT_KEY, DEFAULT_LEFT));
  const [rightWidth, setRightWidth] = useState<number>(() => readStoredWidth(RIGHT_KEY, DEFAULT_RIGHT));

  const handleLeftResize = useCallback((next: number) => {
    setLeftWidth(next);
    try { window.localStorage.setItem(LEFT_KEY, String(next)); } catch { /* no-op */ }
  }, []);

  const handleRightResize = useCallback((next: number) => {
    setRightWidth(next);
    try { window.localStorage.setItem(RIGHT_KEY, String(next)); } catch { /* no-op */ }
  }, []);

  // Grid template: leftWidth | handle | fluid | handle | rightWidth.
  // The 6px handles let the user drag; resist accidental drag on body.
  const gridTemplateColumns = `${leftWidth}px 6px minmax(0, 1fr) 6px ${rightWidth}px`;

  // Lock body scroll so the three panes own their own vertical overflow.
  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, []);

  // ── FE-4 cross-component wiring ─────────────────────────────────────────
  // ArchivePanel banner / entry → MiddleChatPane plan-mode auto-open.
  const [planFocusRequest, setPlanFocusRequest] = useState<
    { focusKind: 'experience'; focusId?: number } | null
  >(null);
  const [archiveRefreshTick, setArchiveRefreshTick] = useState(0);

  const handleStartPlanMode = useCallback(
    (focusKind: string, focusId?: number) => {
      setPlanFocusRequest({
        focusKind: 'experience',
        focusId: focusKind === 'experience' ? focusId : undefined,
      });
      onStartPlanMode?.(focusKind, focusId);
    },
    [onStartPlanMode],
  );

  const handlePlanFocusConsumed = useCallback(() => {
    setPlanFocusRequest(null);
  }, []);

  const handleMemoryArchived = useCallback(() => {
    // bump ArchivePanel mount key so it re-fetches /memory after入档
    setArchiveRefreshTick((t) => t + 1);
  }, []);

  // Plan ② Job plan-mode (2026-05-21): student clicks "🎯 针对这家定制" on
  // a recommendation card → workspace remembers the job context so the next
  // chat turn carries active_job_id back to the backend (memory extracted
  // gets linked_job_id tag, and recall boosts it for that job's rewrites).
  const [activeJobContext, setActiveJobContext] = useState<
    { job_id: string; company: string; job_title: string } | null
  >(null);

  // ── P0b IntelDrawer state (右栏 swap) ─────────────────────────────────────
  // 当 intelOpenCompany != null 时,右栏渲染 <IntelDrawer/> 而不是 <RightResumePane/>。
  // 决策 ②a:严格替换,不并列。priority / xhsCount 由 PlatformCard / RecommendCard
  // 在 open 时透传,用于 logo tone + header sub-line.
  const [intelOpenCompany, setIntelOpenCompany] = useState<string | null>(null);
  const [intelOpenContext, setIntelOpenContext] = useState<{
    priority?: string | null;
    xhsCount?: number | null;
    jobId?: number | null;
    role?: string | null;
  }>({});

  // ── P1 Coach takeover state (2026-05-26) ──────────────────────────────
  // 入口:① IntelDrawer "用这些做 Coach 定制" ② 公司卡 "针对这家定制"
  // (Fix-1 2026-05-26 补:P1 漏了 ②,导致顶栏徽章 / STAR ribbon 不显示)
  const [coachContext, setCoachContext] = useState<CoachContext | null>(null);

  const handleCustomiseForJob = useCallback((it: ResumeRecommendationItem) => {
    const company = String(it.company || '');
    setActiveJobContext({
      job_id: String(it.job_id),
      company,
      job_title: String(it.job_title || ''),
    });
    // Drop the student into plan-mode focused on the first internship bullet
    // by default — they can switch focus in the picker.
    setPlanFocusRequest({ focusKind: 'experience' });
    // Fix-1 (2026-05-26): 公司卡 "针对这家定制" 也要触发 CoachPane wrap
    // (徽章 / STAR stepper / ribbon / footer). P1 漏了这条入口 — 学生从公司
    // 卡进入时 coachContext 没设,plan-mode body 直接渲染没 CoachPane 外壳.
    if (company) {
      // ch 留空 — CoachPane 自动取首字, 避免长公司名溢出 logo bubble.
      setCoachContext({
        company,
        pri: (it.company_priority_tier || 'A').toString().charAt(0).toUpperCase(),
      });
    }
  }, []);

  const handleClearJobContext = useCallback(() => {
    setActiveJobContext(null);
  }, []);

  const handleOpenIntel = useCallback(
    (company: string, ctx?: { priority?: string | null; xhsCount?: number | null; jobId?: number | null; role?: string | null }) => {
      setIntelOpenCompany(company);
      setIntelOpenContext(ctx ?? {});
    },
    [],
  );

  const handleCloseIntel = useCallback(() => {
    setIntelOpenCompany(null);
    setIntelOpenContext({});
  }, []);

  const handleIntelMock = useCallback(() => {
    if (!intelOpenCompany) return;
    setCoachContext({
      company: intelOpenCompany,
      pri: intelOpenContext.priority ?? 'A',
      xhsCount:
        typeof intelOpenContext.xhsCount === 'number'
          ? intelOpenContext.xhsCount
          : undefined,
    });
    // 关掉 IntelDrawer 让中栏 takeover 显眼些 (右栏回到 RightResumePane).
    setIntelOpenCompany(null);
    setIntelOpenContext({});
    // 同时把 plan-mode focus picker 打开, 学生选一段经历进 STAR.
    setPlanFocusRequest({ focusKind: 'experience' });
  }, [intelOpenCompany, intelOpenContext]);

  const handleCloseCoach = useCallback(() => {
    setCoachContext(null);
  }, []);

  // Fix-2a #4 v2 (2026-05-28): composer "coach" pill + ChatEmpty 卡的入口.
  // 优先级:
  //   1. activeJobContext.company — 学生点过"针对这家定制" → 公司级 Coach
  //   2. currentTrackName — 学生选好赛道但没指定公司 → 赛道级 Coach
  //   3. 兜底 '简历定制' — 都没有时仍显示 Coach 外壳, 避免静默失败
  // CoachPane 外壳(ribbon + STAR stepper + footer)始终出来, 学生才知道自己进了 Coach.
  const handleEnterCoach = useCallback(() => {
    const company =
      activeJobContext?.company
      || currentTrackName
      || '简历定制';
    if (coachContext?.company === company) return;
    // ch 留空, CoachPane companyInitial() 自动取首字, 避免长名溢出 logo bubble.
    setCoachContext({
      company,
      pri: activeJobContext ? 'A' : undefined,
    });
  }, [activeJobContext, currentTrackName, coachContext]);

  // ── P1 Rewrite middle-pane takeover state (2026-05-26) ────────────────
  // RightResumePane 触发 v0v2 改写时, 通过 onMiddleRewriteRequested 上传 bullet
  // 上下文给这里; 中栏切到 RewritePane 显示守卫面板 + 2 候选.
  const [rewriteBulletContext, setRewriteBulletContext] =
    useState<RewriteBulletContext | null>(null);
  const [rewriteResult, setRewriteResult] = useState<RewriteV0V2Out | null>(null);

  const handleMiddleRewriteRequested = useCallback(
    (bulletId: string, originalText: string, sectionTitle?: string) => {
      setRewriteBulletContext({ bulletId, originalText, sectionTitle });
      setRewriteResult(null);
    },
    [],
  );

  const handleMiddleRewriteResult = useCallback(
    (result: RewriteV0V2Out | null) => {
      setRewriteResult(result);
    },
    [],
  );

  const handleCloseRewrite = useCallback(() => {
    setRewriteBulletContext(null);
    setRewriteResult(null);
  }, []);

  const archiveSlot = (
    <ArchivePanel
      key={`${session?.id ?? 'none'}-${archiveRefreshTick}`}
      sessionId={session?.id ?? null}
      isDemo={isDemo}
      onStartPlanMode={handleStartPlanMode}
    />
  );

  return (
    <div className="hf">
      <RewriteProvider>
        <div className="workspace-hifi" data-testid="workspace-shell">
          {/* P2 (2026-05-26): legacy WorkspaceConfirmGuide overlay removed.
              When `needsConfirm` is true, the useEffect above redirects to
              `/resume-copilot/confirm?session_id=N` (standalone page). */}
          <TopTrackBar
            trackName={currentTrackName}
            fitScore={currentFitScore}
            onChangeTrack={onChangeTrack}
            session={session}
            recommendations={recommendations}
            onExport={onExport}
            isExporting={isExporting}
            canExport={canExport}
            coachCompany={coachContext?.company ?? null}
          />
          <div
            className="workspace-hifi__grid"
            style={{ gridTemplateColumns }}
          >
            <LeftRecommendRail
              session={session}
              recommendations={recommendations}
              onRejectRecommendation={onRejectRecommendation}
              onRequestRewrite={onRequestRewrite}
              onRecommendationsChanged={onRecommendationsChanged}
              onCustomiseForJob={handleCustomiseForJob}
              onOpenIntel={handleOpenIntel}
            />
            <ResizeHandle
              width={leftWidth}
              onResize={handleLeftResize}
              side="left"
              minWidth={220}
              maxWidth={520}
              ariaLabel="拖动调整左栏(推荐)宽度"
            />
            <MiddleChatPane
              session={session}
              chatMessages={chatMessages}
              isSendingChat={isSendingChat}
              applyingOption={applyingOption}
              sendChatMessage={sendChatMessage}
              applyRewriteOption={applyRewriteOption}
              refreshChatMessages={refreshChatMessages}
              isDemo={isDemo}
              planFocusRequest={planFocusRequest}
              onPlanFocusRequestConsumed={handlePlanFocusConsumed}
              onMemoryArchived={handleMemoryArchived}
              archiveSlot={archiveSlot}
              activeJobContext={activeJobContext}
              onClearJobContext={handleClearJobContext}
              coachContext={coachContext}
              onCloseCoach={handleCloseCoach}
              rewriteBulletContext={rewriteBulletContext}
              onCloseRewrite={handleCloseRewrite}
              rewriteResult={rewriteResult}
              studentName={
                profile?.basic_info?.name ?? profile?.basic_info?.full_name ?? ''
              }
              companyCount={recommendations?.items?.length ?? null}
              onEnterCoach={handleEnterCoach}
            />
            <ResizeHandle
              width={rightWidth}
              onResize={handleRightResize}
              side="right"
              minWidth={300}
              maxWidth={640}
              ariaLabel="拖动调整右栏(简历)宽度"
            />
            {intelOpenCompany ? (
              <IntelDrawer
                companyName={intelOpenCompany}
                priority={intelOpenContext.priority}
                xhsCount={intelOpenContext.xhsCount}
                jobId={intelOpenContext.jobId}
                role={intelOpenContext.role}
                onClose={handleCloseIntel}
                onMock={handleIntelMock}
              />
            ) : (
              <RightResumePane
                session={session}
                profile={profile}
                isExporting={isExporting}
                canExport={canExport}
                isDemo={isDemo}
                xResumeUserKey={xResumeUserKey}
                onExport={onExport}
                onMiddleRewriteRequested={handleMiddleRewriteRequested}
                onMiddleRewriteResult={handleMiddleRewriteResult}
              />
            )}
          </div>
        </div>
      </RewriteProvider>
    </div>
  );
}
