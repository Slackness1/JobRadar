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

import type {
  CopilotMessage,
  ResumeCopilotSession,
  ResumeProfilePayload,
  ResumeRecommendationResult,
} from '../types';

import { TopTrackBar } from './TopTrackBar';
import { LeftRecommendRail } from './LeftRecommendRail';
import { MiddleChatPane } from './MiddleChatPane';
import { RightResumePane } from './RightResumePane';
import { RewriteProvider } from './RewriteContext';
import { ArchivePanel } from './archive/ArchivePanel';

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
  sendChatMessage: (content: string) => Promise<void>;
  applyRewriteOption: (messageId: number, optionId: string) => Promise<void>;
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
    onExport,
    onChangeTrack,
    onOpenArchive,
    onRejectRecommendation,
    onRequestRewrite,
    onRecommendationsChanged,
    currentTrackName = null,
    currentFitScore = null,
    xResumeUserKey,
    onStartPlanMode,
  } = props;

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
          <TopTrackBar
            trackName={currentTrackName}
            fitScore={currentFitScore}
            onChangeTrack={onChangeTrack}
          />
          <div className="workspace-hifi__grid">
            <LeftRecommendRail
              session={session}
              recommendations={recommendations}
              onRejectRecommendation={onRejectRecommendation}
              onRequestRewrite={onRequestRewrite}
              onRecommendationsChanged={onRecommendationsChanged}
            />
            <MiddleChatPane
              session={session}
              chatMessages={chatMessages}
              isSendingChat={isSendingChat}
              applyingOption={applyingOption}
              sendChatMessage={sendChatMessage}
              applyRewriteOption={applyRewriteOption}
              isDemo={isDemo}
              planFocusRequest={planFocusRequest}
              onPlanFocusRequestConsumed={handlePlanFocusConsumed}
              onMemoryArchived={handleMemoryArchived}
            />
            <RightResumePane
              session={session}
              profile={profile}
              isExporting={isExporting}
              canExport={canExport}
              isDemo={isDemo}
              xResumeUserKey={xResumeUserKey}
              onOpenArchive={onOpenArchive}
              onExport={onExport}
              archiveSlot={archiveSlot}
            />
          </div>
        </div>
      </RewriteProvider>
    </div>
  );
}
