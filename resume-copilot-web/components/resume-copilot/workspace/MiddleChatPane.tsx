'use client';

/**
 * MiddleChatPane — 中栏 chat / plan-mode 主区 (B-1 / B-2 简 / B-3 / B-4 / E-3).
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
 *   - plan   → 走 plan-mode 流程:
 *       a) 启动:展示 PlanFocusPicker 让学生选 entry → postPlanStart
 *       b) approve:plan 处 `awaiting_plan_approval` → postPlanApprove → CLARIFYING
 *       c) turn:学生每次 send → postPlanTurn(content) → 刷 plan state
 *       d) finalize:4 anchor 全 ✓ → postPlanFinalize(active item)
 *       e) draft review:PlanDraftCard 出现,学生入档 / 再聊几轮
 *
 * 学生切回 normal mid-flight (B-3):弹确认 → onCancelPlan
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { CopilotMessage, ResumeCopilotSession } from '../types';
import { HFBtn, I } from '@/components/hifi/hifi-primitives';
import {
  postPlanStart,
  postPlanApprove,
  postPlanTurn,
  postPlanFinalize,
  getPlan,
  postSessionMemory,
  type PlanStateOut,
  type PlanItemWire,
} from '../api';
import { RewriteThinkingBubble } from './chat/RewriteThinkingBubble';
import { ChatMessageBubble } from './chat/ChatMessageBubble';
import {
  PlanProgressBar,
  derivePlanAnchors,
  emptyAnchorState,
} from './chat/PlanProgressBar';
import { PlanFocusPicker } from './chat/PlanFocusPicker';
import { PlanDraftCard } from './chat/PlanDraftCard';

export type ChatComposerMode = 'normal' | 'plan';

/** Plan-mode internal phases (FE-only — BE has its own plan_status enum). */
type PlanPhase =
  | 'idle'         // 还没切到 plan-mode 或刚回 normal
  | 'picking'      // 显示 PlanFocusPicker, 等学生选 entry
  | 'starting'     // postPlanStart in-flight
  | 'turning'      // 正常 plan 对话中
  | 'finalizing'   // 4 anchor 全 ✓, 在调 postPlanFinalize
  | 'reviewing'    // 草稿出来了, 展示 PlanDraftCard
  | 'archiving';   // 学生点入档, 在调 postSessionMemory

export interface MiddleChatPaneProps {
  session: ResumeCopilotSession | null;
  chatMessages: CopilotMessage[];
  isSendingChat: boolean;
  applyingOption: string | null;
  sendChatMessage: (content: string) => Promise<void>;
  applyRewriteOption: (messageId: number, optionId: string) => Promise<void>;
  /** 当前 composer mode(B-1); 父可控/不控均可 */
  composerMode?: ChatComposerMode;
  onComposerModeChange?: (mode: ChatComposerMode) => void;
  isDemo?: boolean;
  /** 父传一个回调用于 ArchivePanel banner → 自动开 plan-mode + 预选 entry */
  planFocusRequest?: { focusKind: 'experience'; focusId?: number } | null;
  /** 父消费完 planFocusRequest 后调一次,清空(防止重复触发) */
  onPlanFocusRequestConsumed?: () => void;
  /** 入档成功后让外层刷新 ArchivePanel */
  onMemoryArchived?: () => void;
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
  composerMode: composerModeProp,
  onComposerModeChange,
  isDemo = false,
  planFocusRequest,
  onPlanFocusRequestConsumed,
  onMemoryArchived,
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

  // ── plan-mode state ─────────────────────────────────────────────────────
  const [planPhase, setPlanPhase] = useState<PlanPhase>('idle');
  const [planState, setPlanState] = useState<PlanStateOut | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const [planTurnInFlight, setPlanTurnInFlight] = useState(false);
  const [preselectedEntryId, setPreselectedEntryId] = useState<number | undefined>(
    undefined,
  );
  const finalizeTriggeredRef = useRef(false);

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
        // 已有 active plan → 直接进 turning;否则进 picking
        const status = String(planState?.status ?? '');
        if (planState && (status === 'clarifying' || status === 'reviewing')) {
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
          // 409 PLAN_ALREADY_EXISTS — rehydrate then continue
          if (msg.includes('PLAN_ALREADY_EXISTS')) {
            state = await getPlan(sessionId);
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
        setPlanError(`plan-mode 启动失败:${msg}`);
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
        // 重置 finalize guard
        finalizeTriggeredRef.current = false;
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setPlanError(`plan turn 失败:${msg}`);
      } finally {
        setPlanTurnInFlight(false);
      }
    },
    [sessionId],
  );

  // ── Finalize on 4-anchor complete ─────────────────────────────────────
  useEffect(() => {
    if (sessionId == null) return;
    if (planPhase !== 'turning') return;
    if (!anchors.allFilled) return;
    if (!anchors.activeItemId) return;
    if (finalizeTriggeredRef.current) return;
    finalizeTriggeredRef.current = true;
    setPlanPhase('finalizing');
    (async () => {
      try {
        const next = await postPlanFinalize(sessionId, {
          item_id: anchors.activeItemId!,
          expected_version: anchors.expectedVersion,
        });
        setPlanState(next);
        setPlanPhase('reviewing');
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setPlanError(`finalize 失败:${msg}`);
        setPlanPhase('turning');
        finalizeTriggeredRef.current = false;
      }
    })();
  }, [
    anchors.allFilled,
    anchors.activeItemId,
    anchors.expectedVersion,
    planPhase,
    sessionId,
  ]);

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
      await postSessionMemory(sessionId, {
        category: 'experience',
        summary: draftItem.draft?.text?.slice(0, 200) || draftItem.title,
        payload: {
          name: draftItem.title,
          behavioral_hook: draftItem.draft?.text || '',
          // STAR-derived; FE 端做合理映射, BE 后期可加 schema 强校验
          situation: '',
          task: '',
          action: '',
          result: '',
        },
        raw_excerpt: (draftItem.evidence ?? [])
          .map((ev) => ev.text)
          .filter(Boolean)
          .join('\n')
          .slice(0, 2000),
        confidence: 0.9,
      });
      onMemoryArchived?.();
      // Reset plan-mode UI
      setPlanState(null);
      setPlanPhase('idle');
      setMode('normal');
      finalizeTriggeredRef.current = false;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setPlanError(`入档失败:${msg}`);
      setPlanPhase('reviewing');
    }
  }, [draftItem, onMemoryArchived, sessionId, setMode]);

  const handleContinuePlan = useCallback(() => {
    setPlanPhase('turning');
    finalizeTriggeredRef.current = false;
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
    if (mode === 'plan') {
      setDraft('');
      await handlePlanTurnSend(text);
    } else {
      setDraft('');
      await sendChatMessage(text);
    }
  }, [draft, handlePlanTurnSend, mode, sendChatMessage, sendDisabled]);

  // ── Render ────────────────────────────────────────────────────────────
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
              ? `plan-mode · ${planPhase}`
              : `${messageCount} 条对话`
            : '等待简历就绪'}
        </span>
      </header>

      <div className="workspace-hifi__pane-body workspace-hifi__pane-body--middle">
        {/* FE-3 cross-pane thinking bubble (sticky top, only renders when 右栏触发) */}
        <RewriteThinkingBubble />

        <div className="workspace-hifi__chat-stream">
          {chatMessages.length === 0 && (
            <div className="workspace-hifi__chat-empty">
              {feedbackReady
                ? mode === 'plan'
                  ? '切到了 plan-mode — 选一段经历或自由聊新经历开始。'
                  : '从输入框发起问题,AI 会带着你的真实经历聊。'
                : '简历正在分析中,稍候即可开聊。'}
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
          {planTurnInFlight && mode === 'plan' && (
            <div className="workspace-hifi__chat-typing">AI 在 plan-mode 反问中…</div>
          )}

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
              💬 普通
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
                  ? 'Demo 只读 — 上传自己的简历后可用 plan-mode'
                  : 'plan-mode:AI 带你 4 个 anchor 把一段经历聊透'
              }
            >
              📌 plan-mode
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
                        : 'plan-mode 进行中…'
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

      {/* B-3 切回 normal 确认 modal */}
      {confirmCancelPlan && (
        <div
          className="workspace-hifi__chat-confirm-backdrop"
          role="dialog"
          aria-modal="true"
        >
          <div className="workspace-hifi__chat-confirm">
            <h4>退出 plan-mode?</h4>
            <p>
              plan-mode 未完成。退出后已聊的内容会暂存在 plan_json 里,下次切回
              📌 还能继续 — 但当前 anchor 进度不会自动入档。
            </p>
            <div className="workspace-hifi__chat-confirm-actions">
              <button
                type="button"
                className="workspace-hifi__chat-confirm-btn"
                onClick={() => setConfirmCancelPlan(false)}
              >
                继续 plan-mode
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
      )}
    </section>
  );
}
