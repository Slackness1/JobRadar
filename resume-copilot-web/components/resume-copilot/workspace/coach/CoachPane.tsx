'use client';

/**
 * CoachPane — 中栏 takeover (P1, 决策 ⑥a).
 *
 * 当 `coachContext` 非空时由 MiddleChatPane 渲染。
 *
 * 设计参考:`hifi-ws-coach.jsx::HFCoach`.
 *
 * 视觉外壳:
 *   - Coach ribbon header (terra wash gradient + 1.5px terra border-bottom)
 *   - StarStepper 横向 4 节点 (S/T/A/R, 来自 plan-mode anchor state)
 *   - 中部:同辈情报引用块 (可选) + plan-mode 实际 UI 作为 children 传入
 *   - Footer ribbon "完成后将得到" 3 胶囊 + 保存草稿
 *
 * 业务逻辑 wrap-not-rewrite (决策 ⑥a):
 *   - 不接管 plan-mode 的 state / API call / chat stream — 由 MiddleChatPane
 *     传 `children` 进来 (= 现有 plan-mode 渲染), 这里只换视觉外壳.
 *   - `account_memory` 写入路径继续走 MiddleChatPane → BackgroundTasks
 *     extract_for_chat_turn / PlanDraftCard onArchive. CoachPane 不写 memory.
 */

import { type ReactNode, useMemo } from 'react';

import { I, HFBtn } from '@/components/hifi/hifi-primitives';
import type { AnchorState } from '../chat/PlanProgressBar';
import { StarStepper, starStepsFromAnchors, type StarLetter } from './StarStepper';
import { PhaseTrack } from './PhaseTrack';

export interface CoachContext {
  /** 公司中文名 (header 显示用). */
  company: string;
  /** 公司首字 / 简称, 用作 logo bubble 字 (无则 fallback 用 company[0]). */
  ch?: string;
  /** priority letter A/B/C, 用作 logo tone. */
  pri?: string;
  /** 同辈情报条数 (header overline 显示). */
  xhsCount?: number;
  /** 可选 — header 上方"基于 N 条同辈情报" 引用 1 条 verbatim quote. */
  quote?: {
    text: string;
    author?: string;
    hearts?: number;
  };
}

export interface CoachPaneProps {
  coach: CoachContext;
  /** Plan-mode anchors → STAR stepper state. 由 MiddleChatPane 传 derivePlanAnchors 结果. */
  anchors: AnchorState;
  /** 每个 anchor 的简短 summary, 来自 plan_state.items[*].draft / open_questions. */
  starSummaries?: Partial<Record<StarLetter, string>>;
  /** 当前 phase (B-1/B-2/B-3/B-4) — 默认 anchors 已 done 数 +1. */
  currentPhase?: number;
  /** 中栏 body — MiddleChatPane 传现有 plan-mode 渲染 (chat-stream + picker + draft card). */
  children: ReactNode;
  /** 关闭 Coach pane → 回到正常 chat 模式. */
  onClose: () => void;
  /** "回 Chat" — 同 onClose; 留独立 callback 让父定制 (e.g. preserve plan state). */
  onSwitchChat?: () => void;
  /** "保存草稿" footer ghost 按钮 — placeholder; 真存档走 PlanDraftCard. */
  onSaveDraft?: () => void;
}

function companyInitial(s: string): string {
  const t = (s || '').trim();
  if (!t) return '?';
  const first = t[0];
  return /[A-Za-z0-9]/.test(first) ? first.toUpperCase() : first;
}

function toneClass(pri?: string): string {
  if (pri === 'A' || pri === 'B' || pri === 'C') return pri;
  return 'A';
}

export function CoachPane({
  coach,
  anchors,
  starSummaries,
  currentPhase,
  children,
  onClose,
  onSwitchChat,
  onSaveDraft,
}: CoachPaneProps) {
  const steps = useMemo(
    () => starStepsFromAnchors(anchors, starSummaries),
    [anchors, starSummaries],
  );

  // Phase = done count + 1 (clamped to 4). 0 anchors filled → phase 1.
  const doneCount = steps.filter((s) => s.state === 'done').length;
  const phase = Math.min(4, Math.max(1, currentPhase ?? doneCount + 1));

  const logoCh = coach.ch || companyInitial(coach.company);
  const tone = toneClass(coach.pri);
  const xhsCount = typeof coach.xhsCount === 'number' ? coach.xhsCount : null;

  return (
    <section
      className="workspace-hifi__coach-pane"
      aria-label={`Coach mode · ${coach.company}`}
      data-coach-company={coach.company}
    >
      {/* ── Ribbon header ─────────────────────────────────────────────────── */}
      <header className="workspace-hifi__coach-ribbon">
        <span className="workspace-hifi__coach-ribbon-icon" aria-hidden>
          {I.target(18)}
        </span>
        <div className="workspace-hifi__coach-ribbon-title-wrap">
          <div className="workspace-hifi__coach-ribbon-overline">
            <span>Coach mode</span>
            {xhsCount != null && xhsCount > 0 ? (
              <>
                <span className="workspace-hifi__coach-ribbon-overline-sep">·</span>
                <span className="workspace-hifi__coach-ribbon-overline-sub">
                  基于 {xhsCount} 条同辈情报
                </span>
              </>
            ) : null}
          </div>
          <div className="workspace-hifi__coach-ribbon-title">
            <span
              className="workspace-hifi__coach-ribbon-logo"
              data-tone={tone}
              aria-hidden
            >
              {logoCh}
            </span>
            <span className="workspace-hifi__coach-ribbon-company">
              {coach.company}
            </span>
          </div>
        </div>
        <div className="workspace-hifi__coach-ribbon-spacer" />
        <PhaseTrack step={phase} />
        <HFBtn
          variant="ghost"
          size="sm"
          onClick={onSwitchChat ?? onClose}
          style={{ height: 28, padding: '0 12px', fontSize: 12 }}
        >
          回 Chat
        </HFBtn>
        <button
          type="button"
          className="workspace-hifi__coach-ribbon-close"
          onClick={onClose}
          aria-label="关闭 coach 模式"
        >
          {I.close(16)}
        </button>
      </header>

      {/* ── STAR stepper ──────────────────────────────────────────────────── */}
      <StarStepper steps={steps} />

      {/* ── Body: optional intel quote + plan-mode children ───────────────── */}
      <div className="workspace-hifi__coach-body">
        {coach.quote ? (
          <div className="workspace-hifi__coach-quote" role="note">
            <span className="workspace-hifi__coach-quote-icon" aria-hidden>
              {I.book(16)}
            </span>
            <div className="workspace-hifi__coach-quote-content">
              <div className="workspace-hifi__coach-quote-overline">
                引用 1 条同辈情报
              </div>
              <div className="workspace-hifi__coach-quote-text">
                &ldquo;{coach.quote.text}&rdquo;
              </div>
              <div className="workspace-hifi__coach-quote-meta">
                {coach.quote.author ? `@${coach.quote.author}` : '匿名'}
                {typeof coach.quote.hearts === 'number'
                  ? ` · ❤ ${coach.quote.hearts}`
                  : null}
              </div>
            </div>
          </div>
        ) : null}

        <div className="workspace-hifi__coach-children-slot">{children}</div>
      </div>

      {/* ── Footer ribbon ─────────────────────────────────────────────────── */}
      <footer className="workspace-hifi__coach-footer">
        <span className="hf-overline workspace-hifi__coach-footer-overline">
          完成后将得到
        </span>
        {[
          { icon: I.book(13), label: 'Mock interview', sub: '自动喂题' },
          { icon: I.target(13), label: '下次推荐加权', sub: '跨界研究 +6' },
          { icon: I.edit(13), label: '简历 bullet 改写', sub: '素材可复用' },
        ].map((it) => (
          <span key={it.label} className="workspace-hifi__coach-footer-pill">
            <span className="workspace-hifi__coach-footer-pill-icon" aria-hidden>
              {it.icon}
            </span>
            <span className="workspace-hifi__coach-footer-pill-label">
              {it.label}
            </span>
            <span className="workspace-hifi__coach-footer-pill-sub">
              · {it.sub}
            </span>
          </span>
        ))}
        <div className="workspace-hifi__coach-footer-spacer" />
        <HFBtn
          variant="ghost"
          size="sm"
          onClick={onSaveDraft}
          disabled={!onSaveDraft}
          style={{ height: 28, padding: '0 12px', fontSize: 12 }}
        >
          保存草稿
        </HFBtn>
      </footer>
    </section>
  );
}
