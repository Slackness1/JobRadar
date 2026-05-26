'use client';

/**
 * MiddleChatPane — 中栏 chat / coach 主区 (B-1 / B-2 简 / B-3 / B-4 / E-3).
 *
 * Phase 2 FE-4 (2026-05-20).
 *
 * 三块自上而下:
 *   1. RewriteThinkingBubble (FE-3) — 改写 in-flight 时 chat 顶部浮出
 *   2. 消息流(messages list + plan picker / plan draft 卡)
 *   3. Composer (mode toggle + 4-anchor progress + textarea + send)
 *
 * Mode 切换 (B-1):
 *   - normal → sendChatMessage(content)(老 chat router /chat)
 *   - plan   → 走 coach 流程:
 *       a) 启动:展示 PlanFocusPicker 让学生选 entry → postPlanStart
 *       b) approve:plan 处 `awaiting_plan_approval` → postPlanApprove → CLARIFYING
 *       c) turn:学生每次 send → postPlanTurn(content) → 刷 plan state
 *       d) draft review:PlanDraftCard 出现,学生入档 / 再聊几轮
 *
 * 学生切回 normal mid-flight (B-3):弹确认 → onCancelPlan
 */

import { useCallback, useEffect, useMemo, useState } from 'react';

import type { CopilotMessage, ResumeCopilotSession } from '../types';
import { HFBtn, I } from '@/components/hifi/hifi-primitives';
import {
  postPlanStart,
  postPlanApprove,
  postPlanTurn,
  getPlan,
  deletePlan,
  postPlanDistill,
  postSessionMemory,
  type PlanStateOut,
  type PlanItemWire,
  type RewriteV0V2Out,
} from '../api';
import { RewriteThinkingBubble } from './chat/RewriteThinkingBubble';
import { CoachThinkingIndicator, type CoachThinkingPhase } from './chat/CoachThinkingIndicator';
import { AIOrb } from '@/components/interview/primitives';
import { ChatMessageBubble } from './chat/ChatMessageBubble';
import {
  PlanProgressBar,
  derivePlanAnchors,
  emptyAnchorState,
} from './chat/PlanProgressBar';
import { PlanFocusPicker } from './chat/PlanFocusPicker';
import { PlanDraftCard } from './chat/PlanDraftCard';
import { ChatEmpty } from './chat/ChatEmpty';
import { CoachPane, type CoachContext } from './coach/CoachPane';
import { RewritePane, type RewriteBulletContext } from './rewrite/RewritePane';
import type { StarLetter } from './coach/StarStepper';

export type ChatComposerMode = 'normal' | 'plan';

/** Plan-mode internal phases (FE-only — BE has its own plan_status enum). */
type PlanPhase =
  | 'idle'         // 还没切到 coach 或刚回 normal
  | 'picking'      // 显示 PlanFocusPicker, 等学生选 entry
  | 'starting'     // postPlanStart in-flight
  | 'turning'      // 正常 plan 对话中
  | 'finalizing'   // reserved for future explicit finalize action
  | 'reviewing'    // 草稿出来了, 展示 PlanDraftCard
  | 'archiving';   // 学生点入档, 在调 postSessionMemory

export interface MiddleChatPaneProps {
  session: ResumeCopilotSession | null;
  chatMessages: CopilotMessage[];
  isSendingChat: boolean;
  applyingOption: string | null;
  sendChatMessage: (content: string, opts?: { activeJobId?: string }) => Promise<void>;
  applyRewriteOption: (messageId: number, optionId: string) => Promise<void>;
  /** plan-mode /plan/turn writes chat messages on the backend; refresh parent rail. */
  refreshChatMessages?: () => Promise<void>;
  /** 当前 composer mode(B-1); 父可控/不控均可 */
  composerMode?: ChatComposerMode;
  onComposerModeChange?: (mode: ChatComposerMode) => void;
  isDemo?: boolean;
  /** 父传一个回调用于 ArchivePanel banner → 自动开 coach + 预选 entry */
  planFocusRequest?: { focusKind: 'experience'; focusId?: number } | null;
  /** 父消费完 planFocusRequest 后调一次,清空(防止重复触发) */
  onPlanFocusRequestConsumed?: () => void;
  /** 入档成功后让外层刷新 ArchivePanel */
  onMemoryArchived?: () => void;
  /** ArchivePanel 节点(2026-05-20:从右栏底部搬到中栏顶部,提升可见性) */
  archiveSlot?: React.ReactNode;
  /** Plan ② Job coach (2026-05-21): when set, every chat turn this pane
   *  sends includes `active_job_id` so the backend tags extracted memory
   *  with linked_job_id for per-job customisation. Banner shown at top. */
  activeJobContext?: { job_id: string; company: string; job_title: string } | null;
  /** "退出岗位定制模式" — clears the job context banner. */
  onClearJobContext?: () => void;

  // ── P1: Coach mode middle-pane takeover (决策 ⑥a) ───────────────────────
  /** 非空时中栏切换到 CoachPane (wrap 现有 plan-mode 渲染 + 公司 context). */
  coachContext?: CoachContext | null;
  /** Coach pane 关闭 → 父清掉 coachContext, 回到正常 chat. */
  onCloseCoach?: () => void;

  // ── P1: Rewrite middle-pane takeover (决策 ①a) ──────────────────────────
  /** 非空时中栏切换到 RewritePane. 由 RightResumePane 触发 v0v2 时父 set. */
  rewriteBulletContext?: RewriteBulletContext | null;
  /** Rewrite pane 关闭 — 父清掉 rewriteBulletContext. */
  onCloseRewrite?: () => void;
  /** v0v2 完整 result (含 rationale + warnings + en_text). 父透传; 没有时
   *  RewritePane 会 fallback 到 RewriteContext (useRewriteState). */
  rewriteResult?: RewriteV0V2Out | null;
  /** ChatEmpty 用 — 简历主人名字 (来自 confirmed_profile.basic_info.name). */
  studentName?: string;
  /** ChatEmpty 用 — 今天有几张公司推荐卡 (recommendations.length). */
  companyCount?: number | null;
}

const PLAN_TERMINAL_STATUSES = new Set([
  'done',
  'idle',
  'paused',
]);

export function MiddleChatPane({
  session,
  chatMessages,
  isSendingChat,
  applyingOption,
  sendChatMessage,
  applyRewriteOption,
  refreshChatMessages,
  composerMode: composerModeProp,
  onComposerModeChange,
  isDemo = false,
  planFocusRequest,
  onPlanFocusRequestConsumed,
  onMemoryArchived,
  archiveSlot,
  activeJobContext,
  onClearJobContext,
  coachContext,
  onCloseCoach,
  rewriteBulletContext,
  onCloseRewrite,
  rewriteResult,
  studentName,
  companyCount,
}: MiddleChatPaneProps) {
  // ── mode + composer state ───────────────────────────────────────────────
  const [internalMode, setInternalMode] = useState<ChatComposerMode>('normal');
  const mode = composerModeProp ?? internalMode;
  const setMode = useCallback(
    (next: ChatComposerMode) => {
      setInternalMode(next);
      onComposerModeChange?.(next);
    },
    [onComposerModeChange],
  );

  const [draft, setDraft] = useState('');
  const [confirmCancelPlan, setConfirmCancelPlan] = useState(false);

  // ── coach state ─────────────────────────────────────────────────────
  const [planPhase, setPlanPhase] = useState<PlanPhase>('idle');
  const [planState, setPlanState] = useState<PlanStateOut | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const [planTurnInFlight, setPlanTurnInFlight] = useState(false);
  const [preselectedEntryId, setPreselectedEntryId] = useState<number | undefined>(
    undefined,
  );

  const sessionId = session?.id ?? null;
  const feedbackReady = session?.feedback_status === 'completed';
  const messageCount = chatMessages.length;
  const canChat = Boolean(sessionId) && feedbackReady && !isDemo;
  const anchors = useMemo(() => derivePlanAnchors(planState), [planState]);

  // ── Rehydrate existing plan on mount / session change ─────────────────
  useEffect(() => {
    if (sessionId == null || isDemo) return;
    const existing = String(session?.plan_status ?? 'idle');
    if (!session?.has_plan && PLAN_TERMINAL_STATUSES.has(existing)) {
      // no plan to rehydrate
      return;
    }
    let cancelled = false;
    getPlan(sessionId)
      .then((p) => {
        if (cancelled) return;
        setPlanState(p);
        if (String(p.status) === 'clarifying' || String(p.status) === 'reviewing') {
          // user previously paused mid-flight → leave in normal until they toggle
        }
      })
      .catch(() => {
        // No plan — fine, ignore.
      });
    return () => {
      cancelled = true;
    };
    // 仅在 session change 时拉一次
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, isDemo]);

  // ── ArchivePanel banner / preselect handoff ───────────────────────────
  useEffect(() => {
    if (!planFocusRequest) return;
    if (sessionId == null || isDemo) return;
    setMode('plan');
    setPreselectedEntryId(planFocusRequest.focusId);
    if (planPhase === 'idle') {
      setPlanPhase('picking');
    }
    onPlanFocusRequestConsumed?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planFocusRequest, sessionId, isDemo]);

  // ── Mode toggle (B-1) ──────────────────────────────────────────────────
  const handleSwitchMode = useCallback(
    (next: ChatComposerMode) => {
      if (next === mode) return;
      // 切回 normal 时 plan 正在进行 → 弹确认 (B-3)
      if (
        next === 'normal' &&
        (planPhase === 'turning' ||
          planPhase === 'picking' ||
          planPhase === 'reviewing')
      ) {
        setConfirmCancelPlan(true);
        return;
      }
      setMode(next);
      if (next === 'plan' && sessionId != null && !isDemo) {
        // 已有 active plan → 直接进 turning;否则进 picking。
        // 2026-05-21: clarifying 但 current_item_id 是 null 是"陈旧 plan
        // (重启后 / approve 没跑) — 进 turning 会渲染空白让学生干等。
        // 这种情况强制 picking,让 picker 重新挑入口。
        const status = String(planState?.status ?? '');
        const hasLiveFocus = planState?.current_item_id != null;
        if (
          planState &&
          hasLiveFocus &&
          (status === 'clarifying' || status === 'reviewing')
        ) {
          setPlanPhase('turning');
        } else {
          setPlanPhase('picking');
        }
      } else if (next === 'normal') {
        setPlanPhase('idle');
      }
    },
    [isDemo, mode, planPhase, planState, sessionId, setMode],
  );

  const confirmCancelPlanFinal = useCallback(() => {
    setConfirmCancelPlan(false);
    setMode('normal');
    setPlanPhase('idle');
    setPreselectedEntryId(undefined);
    // 2026-05-21: 不清掉 planState 的话, 重进 coach 时 status 还是
    // 'clarifying', handleSwitchMode 走 turning 分支, picker 不出来 →
    // 学生看到空白。所以这里强制清回 null, 让重进时回到 picker。
    setPlanState(null);
  }, [setMode]);

  // ── Plan flow handlers ─────────────────────────────────────────────────
  const handleFocusConfirm = useCallback(
    async (params: { focusKind: 'experience'; focusId?: number }) => {
      if (sessionId == null) return;
      setPlanPhase('starting');
      setPlanError(null);
      try {
        let state: PlanStateOut;
        try {
          state = await postPlanStart(sessionId, {
            focus_kind: params.focusKind,
            focus_id: params.focusId,
          });
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          // 409 PLAN_ALREADY_EXISTS — 2026-05-21: 老版本走 getPlan 拉旧
          // plan 继续, 但旧 plan 经常 current_item_id=null + 没 anchor →
          // 学生 click coach 后 turning 空白 5 分钟干等。 现在改成: 删了
          // 旧 plan, 用学生这次选的 focus_id 重新 start, 一定是 fresh state。
          if (msg.includes('PLAN_ALREADY_EXISTS')) {
            await deletePlan(sessionId);
            state = await postPlanStart(sessionId, {
              focus_kind: params.focusKind,
              focus_id: params.focusId,
            });
          } else {
            throw err;
          }
        }
        // auto-approve so first turn can roll
        if (String(state.status) === 'awaiting_plan_approval') {
          try {
            state = await postPlanApprove(sessionId);
          } catch (err) {
            // approve failed → still set plan, let learner type to bootstrap.
            const msg = err instanceof Error ? err.message : String(err);
            setPlanError(`plan 切换失败:${msg}`);
          }
        }
        setPlanState(state);
        setPlanPhase('turning');
        setPreselectedEntryId(undefined);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setPlanError(`coach 启动失败:${msg}`);
        setPlanPhase('picking');
      }
    },
    [sessionId],
  );

  const handleFocusCancel = useCallback(() => {
    setMode('normal');
    setPlanPhase('idle');
    setPreselectedEntryId(undefined);
  }, [setMode]);

  const handlePlanTurnSend = useCallback(
    async (content: string) => {
      if (sessionId == null) return;
      setPlanTurnInFlight(true);
      setPlanError(null);
      try {
        const next = await postPlanTurn(sessionId, { user_message: content });
        setPlanState(next);
        const current =
          next.items.find((item) => item.id === next.current_item_id) ??
          next.items.find((item) => String(item.status) === 'awaiting_review');
        if (current?.draft?.text || String(current?.status) === 'awaiting_review') {
          setPlanPhase('reviewing');
        } else {
          setPlanPhase('turning');
        }
        await refreshChatMessages?.().catch(() => {
          /* plan state already advanced; a later session refresh will recover messages */
        });
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setPlanError(`plan turn 失败:${msg}`);
      } finally {
        setPlanTurnInFlight(false);
      }
    },
    [refreshChatMessages, sessionId],
  );

  // ── Reviewing → 入档 / 再聊几轮 ────────────────────────────────────────
  const draftItem: PlanItemWire | null = useMemo(() => {
    if (!planState) return null;
    // Prefer current_item_id, then any FINALIZED / AWAITING_REVIEW item.
    if (planState.current_item_id) {
      const it = planState.items.find((x) => x.id === planState.current_item_id);
      if (it) return it;
    }
    return (
      planState.items.find((x) =>
        ['finalized', 'awaiting_review'].includes(String(x.status)),
      ) ?? null
    );
  }, [planState]);

  const handleArchiveDraft = useCallback(async () => {
    if (sessionId == null || !draftItem) return;
    setPlanPhase('archiving');
    setPlanError(null);
    try {
      // H 2026-05-22: 先调 /plan/distill, 用 LLM 把 draft + evidence 精炼成
      // 干净的 STAR + 去重 quantified + 去回声 raw_excerpt。 失败了 fall back
      // 到原 raw join 路径, 至少能入档不丢数据。
      let distilled: Awaited<ReturnType<typeof postPlanDistill>> | null = null;
      try {
        distilled = await postPlanDistill(sessionId, draftItem.id);
      } catch (_err) {
        // 静默 fallback — 入档优先, 精炼是 nice-to-have
        distilled = null;
      }
      const summary =
        distilled?.summary
        || draftItem.draft?.text?.slice(0, 200)
        || draftItem.title;
      const star = distilled?.star
        ?? { situation: '', task: '', action: '', result: '' };
      const rawExcerpt =
        distilled?.raw_excerpt_clean
        || (draftItem.evidence ?? [])
            .map((ev) => ev.text)
            .filter(Boolean)
            .join('\n')
            .slice(0, 2000);
      await postSessionMemory(sessionId, {
        category: 'experience',
        summary,
        payload: {
          name: draftItem.title,
          behavioral_hook: draftItem.draft?.text || '',
          situation: star.situation,
          task: star.task,
          action: star.action,
          result: star.result,
          quantified: distilled?.quantified ?? {},
        },
        raw_excerpt: rawExcerpt,
        confidence: 0.9,
      });
      onMemoryArchived?.();
      // Reset coach UI
      setPlanState(null);
      setPlanPhase('idle');
      setMode('normal');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setPlanError(`入档失败:${msg}`);
      setPlanPhase('reviewing');
    }
  }, [draftItem, onMemoryArchived, sessionId, setMode]);

  const handleContinuePlan = useCallback(() => {
    setPlanPhase('turning');
  }, []);

  // ── Composer send (normal or plan turn) ───────────────────────────────
  const sendDisabled =
    !draft.trim() ||
    (mode === 'normal' && (!canChat || isSendingChat)) ||
    (mode === 'plan' &&
      (planTurnInFlight ||
        planPhase === 'picking' ||
        planPhase === 'starting' ||
        planPhase === 'finalizing' ||
        planPhase === 'reviewing' ||
        planPhase === 'archiving' ||
        sessionId == null ||
        isDemo));

  const handleSend = useCallback(async () => {
    const text = draft.trim();
    if (!text) return;
    if (sendDisabled) return;
    // Plan ② Job coach (2026-05-21): pass active_job_id when in
    // job-customisation mode, so backend tags extracted memory with the job.
    const opts = activeJobContext?.job_id
      ? { activeJobId: activeJobContext.job_id }
      : undefined;
    if (mode === 'plan') {
      setDraft('');
      await handlePlanTurnSend(text);
    } else {
      setDraft('');
      await sendChatMessage(text, opts);
    }
  }, [draft, handlePlanTurnSend, mode, sendChatMessage, sendDisabled, activeJobContext]);

  // ── Render ────────────────────────────────────────────────────────────
  // P1 (2026-05-26): 当 rewriteBulletContext 非空时, 中栏完全切到 RewritePane.
  // RightResumePane 触发 v0v2 → WorkspaceShell setRewriteBulletContext → 这里
  // 渲染 RewritePane (改写守卫面板 + 2 候选). 不影响 plan-mode 状态.
  if (rewriteBulletContext) {
    return (
      <RewritePane
        bullet={rewriteBulletContext}
        result={rewriteResult ?? null}
        onClose={() => onCloseRewrite?.()}
      />
    );
  }

  // P1: Coach takeover — coachContext 非空时, 中栏切到 CoachPane.
  // CoachPane wrap (决策 ⑥a) 现有 plan-mode UI; 不重写 plan 业务逻辑,
  // 只给 ribbon + STAR stepper + footer 视觉外壳. 整个 chat-stream + composer
  // 仍然由 MiddleChatPane 内部驱动, 通过 children slot 透传进去.
  const bodyInside = (
    <div className="workspace-hifi__pane-body workspace-hifi__pane-body--middle">
        {/* 📌 我的档案 — 顶部贴条 (2026-05-20: 从右栏底部搬过来, 更显眼).
            Same ArchivePanel collapsed/expanded behaviour, just placed
            above the chat thread for visibility. */}
        {archiveSlot ? (
          <div className="workspace-hifi__middle-archive-slot">{archiveSlot}</div>
        ) : null}

        {/* Plan ② Job coach banner — when student has clicked
            "🎯 针对这家定制" on a recommend card, every chat turn from
            now on is tagged with this job. Banner explains + offers exit. */}
        {activeJobContext ? (
          <div className="workspace-hifi__job-context-banner" role="status">
            <span className="workspace-hifi__job-context-icon" aria-hidden>🎯</span>
            <span className="workspace-hifi__job-context-text">
              <strong>针对这家定制中</strong>
              <span className="workspace-hifi__job-context-detail">
                {activeJobContext.company} · {activeJobContext.job_title}
              </span>
            </span>
            <button
              type="button"
              className="workspace-hifi__job-context-clear"
              onClick={onClearJobContext}
              title="退出岗位定制模式 — 回到赛道通用对话"
            >
              退出
            </button>
          </div>
        ) : null}

        {/* FE-3 cross-pane thinking bubble (sticky top, only renders when 右栏触发) */}
        <RewriteThinkingBubble />

        <div className="workspace-hifi__chat-stream">
          {/* Parsing/feedback indicator — 2026-05-21 v6: 必须独立挂载, 不能
              嵌在 chatMessages.length === 0 分支里, 否则 dashboard 消息一插
              整个分支 unmount, 动画跟着没掉, 看起来就是"一闪而过"。 现在只
              要 feedback 没完成就一直显示, 与 chatMessages 解耦。 */}
          {!feedbackReady && (
            <div className="workspace-hifi__chat-empty">
              <CoachThinkingIndicator
                active={!feedbackReady}
                phase="parsing"
                minVisibleMs={2500}
              />
              <span style={{ marginTop: 8, fontSize: 12, color: 'var(--olive)' }}>
                简历正在分析中,稍候即可开聊。首次上传约 20-40 秒。
              </span>
            </div>
          )}
          {chatMessages.length === 0 &&
            feedbackReady &&
            !isSendingChat &&
            mode === 'normal' &&
            !coachContext &&
            !rewriteBulletContext && (
              <ChatEmpty
                studentName={studentName}
                companyCount={companyCount}
                disabled={!canChat}
                onQuickPick={(prompt) => {
                  if (!canChat) return;
                  const opts = activeJobContext?.job_id
                    ? { activeJobId: activeJobContext.job_id }
                    : undefined;
                  void sendChatMessage(prompt, opts);
                }}
              />
            )}
          {chatMessages.length === 0 && feedbackReady && mode === 'plan' && (
            <div className="workspace-hifi__chat-empty">
              切到了 coach — 选一段经历或自由聊新经历开始。
            </div>
          )}
          {chatMessages.map((m) => (
            <ChatMessageBubble
              key={m.id}
              message={m}
              applyingOption={applyingOption}
              onApply={applyRewriteOption}
              isDemo={isDemo}
            />
          ))}
          {isSendingChat && mode === 'normal' && (
            <div className="workspace-hifi__chat-typing">AI 思考中…</div>
          )}
          {mode === 'plan' && (
            <CoachThinkingIndicator
              active={
                planTurnInFlight ||
                planPhase === 'starting' ||
                planPhase === 'finalizing' ||
                planPhase === 'archiving'
              }
              phase={
                (planPhase === 'starting'
                  ? 'starting'
                  : planPhase === 'finalizing'
                    ? 'finalizing'
                    : planPhase === 'archiving'
                      ? 'archiving'
                      : 'turning') as CoachThinkingPhase
              }
              minVisibleMs={2500}
            />
          )}

          {/* 2026-05-21: turning 进来时 BE 不会自动产生第一个问题, 学生不知
              道该干嘛就傻等 (用户在 v4 复现的"5 分钟没下一步"根因)。
              这里加一张显式开场卡 — 只在 turning + 当前 item 还没动起来
              时出, 学生一发第一句话就消失。 */}
          {mode === 'plan' &&
            planPhase === 'turning' &&
            !planTurnInFlight &&
            planState?.current_item_id != null && (() => {
              const cur = planState.items.find(
                (it) => it.id === planState.current_item_id,
              );
              if ((cur?.open_questions ?? []).length > 0) return null;
              const title = cur?.title ?? '这段经历';
              return (
                <div
                  className="workspace-hifi__plan-kickoff"
                  role="status"
                  style={{
                    // AIOrb 需要这些 token, workspace 默认没定义
                    ['--terracotta' as string]: '#c96442',
                    ['--terracotta-strong' as string]: '#a14e30',
                    ['--border' as string]: '#e8e6dc',
                    ['--border-strong' as string]: '#d3d0c2',
                  }}
                >
                  <div className="workspace-hifi__plan-kickoff-orb" aria-hidden>
                    <AIOrb size={72} />
                  </div>
                  <div className="workspace-hifi__plan-kickoff-text">
                    <div className="workspace-hifi__plan-kickoff-head">
                      <span aria-hidden style={{ marginRight: 6 }}>📌</span>
                      AI coach 已就绪 — 现在轮到你说
                    </div>
                    <p className="workspace-hifi__plan-kickoff-body">
                      我会按 STAR 4 个 anchor 带你聊
                      <strong>「{title}」</strong>:
                      <em>背景 → 你的任务 → 你做了什么 → 结果</em>。
                    </p>
                    <p className="workspace-hifi__plan-kickoff-body">
                      <strong>请先 2-3 句简单说一下你做了什么</strong>,
                      我顺着追问把它聊透。
                    </p>
                  </div>
                </div>
              );
            })()}

          {/* Plan-mode card stack (B-2 / B-4) */}
          {mode === 'plan' && planPhase === 'picking' && sessionId != null && (
            <PlanFocusPicker
              sessionId={sessionId}
              onConfirm={handleFocusConfirm}
              onCancel={handleFocusCancel}
              preselectedEntryId={preselectedEntryId}
            />
          )}

          {mode === 'plan' &&
            (planPhase === 'reviewing' || planPhase === 'archiving') &&
            draftItem && (
              <PlanDraftCard
                draftItem={draftItem}
                isArchiving={planPhase === 'archiving'}
                onArchive={handleArchiveDraft}
                onContinue={handleContinuePlan}
              />
            )}

          {planError && (
            <div className="workspace-hifi__chat-error" role="alert">
              {planError}
            </div>
          )}
        </div>

        {/* ── Composer ───────────────────────────────────────────────── */}
        <div className="workspace-hifi__composer">
          <div className="workspace-hifi__composer-toggle" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'normal'}
              className={`workspace-hifi__composer-toggle-btn${
                mode === 'normal' ? ' is-active' : ''
              }`}
              onClick={() => handleSwitchMode('normal')}
            >
              💬 chat
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'plan'}
              className={`workspace-hifi__composer-toggle-btn${
                mode === 'plan' ? ' is-active' : ''
              }`}
              onClick={() => handleSwitchMode('plan')}
              disabled={isDemo || sessionId == null}
              title={
                isDemo
                  ? 'Demo 只读 — 上传自己的简历后可用 coach'
                  : 'coach:AI 带你 4 个 anchor 把一段经历聊透'
              }
            >
              📌 coach
            </button>
          </div>

          {mode === 'plan' && planPhase === 'turning' && (
            <PlanProgressBar anchors={anchors} />
          )}
          {mode === 'plan' && planPhase === 'idle' && (
            <PlanProgressBar anchors={emptyAnchorState()} />
          )}

          <div className="workspace-hifi__composer-row">
            <textarea
              rows={2}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  void handleSend();
                }
              }}
              disabled={
                mode === 'normal'
                  ? !canChat || isSendingChat
                  : planPhase === 'picking' ||
                    planPhase === 'starting' ||
                    planPhase === 'finalizing' ||
                    planPhase === 'reviewing' ||
                    planPhase === 'archiving' ||
                    sessionId == null ||
                    isDemo
              }
              placeholder={
                isDemo
                  ? 'Demo 只读 — 上传自己的简历后可对话'
                  : mode === 'plan'
                    ? planPhase === 'picking'
                      ? '先在上面选一段经历…'
                      : planPhase === 'turning'
                        ? '回答 AI 的问题,把这段经历聊透…'
                        : 'coach 进行中…'
                    : canChat
                      ? '问我如何优化这份简历…'
                      : '等待首次分析完成后可对话…'
              }
              className="workspace-hifi__composer-textarea"
            />
            <HFBtn
              variant="primary"
              size="sm"
              disabled={sendDisabled}
              onClick={() => void handleSend()}
              style={{ height: 36, width: 36, padding: 0, borderRadius: 10 }}
              aria-label="发送"
            >
              {I.arrowUp(14)}
            </HFBtn>
          </div>
        </div>
      </div>
  );

  const confirmModal = confirmCancelPlan ? (
    <div
      className="workspace-hifi__chat-confirm-backdrop"
      role="dialog"
      aria-modal="true"
    >
      <div className="workspace-hifi__chat-confirm">
        <h4>退出 coach?</h4>
        <p>
          coach 未完成。退出后已聊的内容会暂存在 plan_json 里,下次切回
          📌 还能继续 — 但当前 anchor 进度不会自动入档。
        </p>
        <div className="workspace-hifi__chat-confirm-actions">
          <button
            type="button"
            className="workspace-hifi__chat-confirm-btn"
            onClick={() => setConfirmCancelPlan(false)}
          >
            继续 coach
          </button>
          <button
            type="button"
            className="workspace-hifi__chat-confirm-btn is-danger"
            onClick={confirmCancelPlanFinal}
          >
            确认退出
          </button>
        </div>
      </div>
    </div>
  ) : null;

  // ── P1 Coach takeover ─────────────────────────────────────────────────
  if (coachContext) {
    // STAR summary 来自 plan_state.current_item — 没拿到 plan 时所有 summary
    // 为空, stepper 第一节点 (S) 默认 active.
    const starSummaries: Partial<Record<StarLetter, string>> = {};
    if (planState?.current_item_id) {
      const cur = planState.items.find(
        (it) => it.id === planState.current_item_id,
      );
      if (cur?.title) starSummaries.S = cur.title;
    }
    return (
      <>
        <CoachPane
          coach={coachContext}
          anchors={anchors}
          starSummaries={starSummaries}
          onClose={() => onCloseCoach?.()}
          onSwitchChat={() => onCloseCoach?.()}
        >
          {bodyInside}
        </CoachPane>
        {confirmModal}
      </>
    );
  }

  // ── Default chat / plan-mode render ───────────────────────────────────
  return (
    <section
      className="workspace-hifi__pane workspace-hifi__pane--middle"
      aria-label="Chat 主区"
    >
      <header className="workspace-hifi__pane-header">
        <span className="workspace-hifi__pane-header-icon" aria-hidden>
          {I.sparkle(15)}
        </span>
        <span>AI 简历助手</span>
        <span className="workspace-hifi__pane-header-count">
          {feedbackReady
            ? mode === 'plan'
              ? `coach · ${planPhase}`
              : `${messageCount} 条对话`
            : '等待简历就绪'}
        </span>
      </header>

      {bodyInside}

      {confirmModal}
    </section>
  );
}
