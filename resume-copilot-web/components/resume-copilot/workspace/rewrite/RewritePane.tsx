'use client';

/**
 * RewritePane — 中栏 takeover (P1, 决策 ①a).
 *
 * 设计参考 `hifi-ws-intel.jsx::HFRewrite`.
 *
 * 触发链:
 *   1. 学生在 RightResumePane bullet hover ✏️ → handleRequestRewrite
 *   2. RightResumePane setActiveRewrite + rewriteCtx.beginThinking
 *      并通过 `onMiddleRewriteRequested` 上传 workspace-level bullet 上下文
 *   3. WorkspaceShell setRewriteBulletContext → MiddleChatPane 切到 RewritePane
 *   4. RewritePane 通过 useRewriteState 读 v0/v2/warnings (同源 = 后端 v0v2 endpoint)
 *
 * 决策 ①a (2 候选, 不强行 v3):
 *   后端 generate_rewrite_v0_v2 当前只返 v0 (echo) + v2 (thesis-aware), 不
 *   伪造第 3 个候选; 学生点 "再来 2 版" ghost 重新拉.
 *
 * RewriteWarning 字段对接 (D-? 严契约红线):
 *   读 v2.warnings[] (RewriteWarningDto[]) → 喂 FabricationGuardPanel.
 *   不剥离, 不 suppress.
 */

import { useState } from 'react';

import { I, HFBtn } from '@/components/hifi/hifi-primitives';
import { useRewriteState } from '../RewriteContext';
import { RewriteOption, type RewriteOptionData } from './RewriteOption';
import { FabricationGuardPanel } from './FabricationGuardPanel';
import type { RewriteV0V2Out } from '../../api';

export interface RewriteBulletContext {
  /** RightResumePane 的 fieldPath (e.g. "internships.0.bullets.2"). */
  bulletId: string;
  /** 原文 — display 用. */
  originalText: string;
  /** 实习/项目 name — header 副标识用 (可选). */
  sectionTitle?: string;
}

export interface RewritePaneProps {
  bullet: RewriteBulletContext;
  /** 关闭 pane → 回到 chat. RightResumePane 那边的 activeRewrite 由其自己管理. */
  onClose: () => void;
  /** "应用 vN" — 学生采纳改写. P1 阶段 = 复制 v2 到剪贴板 (RightResumePane 已实现).
   *  这里只暴露 callback, 真采纳逻辑由 父 wire. */
  onApply?: (versionId: 'v0' | 'v2', text: string) => void;
  /** "再来 2 版" — 重新触发 v0v2 改写. P1 阶段 placeholder. */
  onRegenerate?: () => void;
  /** v0v2 完整 result (含 rationale + memory_refs). 可选 — 没传时仅靠 RewriteContext. */
  result?: RewriteV0V2Out | null;
}

export function RewritePane({
  bullet,
  onClose,
  onApply,
  onRegenerate,
  result,
}: RewritePaneProps) {
  const rewriteState = useRewriteState();

  // result 来源优先级:explicit prop > rewriteState (context broadcast)
  const v0Text = result?.v0?.text ?? rewriteState.v0 ?? bullet.originalText;
  const v2Text = result?.v2?.text ?? rewriteState.v2 ?? '';
  const warnings = result?.v2?.warnings;
  const rationale = result?.rationale;
  const softHint = result?.v2?.soft_hint;
  const enText = result?.v2?.en_text;
  const needsPlan = result?.v2?.needs_plan_mode === true;

  const status = rewriteState.status;
  const isLoading = status === 'thinking' && !v2Text;
  const isError = status === 'error';

  // 默认选 v2 (Copilot 改写版); 学生可点 v0 切回原文对照. 不在 effect 里改 —
  // 用 derived state: 如果 selected 是 stale 'v2' 但 v2Text 空, button render
  // 已 disable 它, 不影响 UX.
  const [selected, setSelected] = useState<'v0' | 'v2'>('v2');

  // Section subtitle derivation (e.g. "实习经历 / bullet #N").
  // fieldPath like "internships.0.bullets.2" → "实习 #1 · bullet #3".
  const subtitle = ((): string => {
    if (bullet.sectionTitle) return bullet.sectionTitle;
    const m = bullet.bulletId.match(
      /^(internships|projects|education)\.(\d+)\.[a-z]+\.(\d+)$/i,
    );
    if (!m) return bullet.bulletId;
    const sectionMap: Record<string, string> = {
      internships: '实习',
      projects: '项目',
      education: '教育',
    };
    const sec = sectionMap[m[1].toLowerCase()] || m[1];
    return `${sec} #${Number(m[2]) + 1} · bullet #${Number(m[3]) + 1}`;
  })();

  // ── audit hint line — 列已检出的 "动词软 / 量化缺失 / ..." 触发点
  // backend v0v2 endpoint 目前不显式返 audit risks; 用 warnings 数 + soft_hint
  // 做近似展示 (≥1 fabrication → "AI 在 v2 引入了未验证数字").
  const auditHints: string[] = [];
  if (warnings && warnings.length > 0) {
    auditHints.push(`AI 在 v2 写了 ${warnings.length} 个 profile 查不到的数字`);
  }
  if (needsPlan) {
    auditHints.push('证据不足, 建议先去 coach 聊这段经历');
  }

  return (
    <section
      className="workspace-hifi__rewrite-pane"
      aria-label={`改写 bullet · ${subtitle}`}
    >
      {/* ── Header ────────────────────────────────────────────────────────── */}
      <header className="workspace-hifi__rewrite-header">
        <span className="workspace-hifi__rewrite-header-icon" aria-hidden>
          {I.edit(16)}
        </span>
        <div className="workspace-hifi__rewrite-header-title-wrap">
          <div className="workspace-hifi__rewrite-header-title">改写 bullet</div>
          <div className="workspace-hifi__rewrite-header-sub">{subtitle}</div>
        </div>
        <HFBtn
          variant="ghost"
          size="sm"
          onClick={onClose}
          style={{ marginLeft: 'auto', height: 28, padding: '0 12px', fontSize: 12 }}
        >
          <span style={{ display: 'inline-flex', marginRight: 4 }}>
            {I.close(13)}
          </span>
          返回 Chat
        </HFBtn>
      </header>

      <div className="workspace-hifi__rewrite-body">
        {/* ── 原文块 ─────────────────────────────────────────────────────── */}
        <section className="workspace-hifi__rewrite-original">
          <div className="hf-overline workspace-hifi__rewrite-overline">原文</div>
          <div className="workspace-hifi__rewrite-original-text">
            &ldquo;{bullet.originalText}&rdquo;
          </div>
          {auditHints.length > 0 && (
            <div className="workspace-hifi__rewrite-original-hint">
              Copilot 检测到 {auditHints.length} 个问题:
              {auditHints.map((h, i) => (
                <span key={i} className="workspace-hifi__rewrite-hint-chip">
                  {h}
                </span>
              ))}
            </div>
          )}
        </section>

        {/* ── 2 候选区 ───────────────────────────────────────────────────── */}
        {isLoading ? (
          <div className="workspace-hifi__rewrite-loading">
            <span className="hf-spin" aria-hidden />
            <span>AI 正在基于你的档案做 thesis-aware 改写…</span>
          </div>
        ) : isError ? (
          <div className="workspace-hifi__rewrite-error" role="alert">
            改写失败:{rewriteState.errorMessage || '未知错误'}
          </div>
        ) : needsPlan ? (
          <div className="workspace-hifi__rewrite-needs-plan">
            <div className="workspace-hifi__rewrite-needs-plan-text">
              📌 这段经历在你的档案里证据不足。建议切到 <strong>coach</strong> 把
              关键决策 / 量化结果聊透再回来改写。
            </div>
          </div>
        ) : (
          <>
            <div className="hf-overline workspace-hifi__rewrite-overline">
              2 个改写方向
            </div>
            <div className="workspace-hifi__rewrite-options">
              {[
                {
                  versionId: 'v0' as const,
                  tag: '保留原文',
                  text: v0Text,
                  why: '当前简历原文 — 没有任何改动, 作为对照基线。',
                },
                {
                  versionId: 'v2' as const,
                  tag: result?.v2 ? 'STAR · 强量化' : 'thesis-aware',
                  text: v2Text || '(v2 未返回文本)',
                  why: rationale || softHint || undefined,
                },
              ].map((opt: RewriteOptionData) => (
                <RewriteOption
                  key={opt.versionId}
                  option={opt}
                  selected={selected === opt.versionId}
                  onSelect={setSelected}
                />
              ))}
            </div>

            {/* 港新 EN bullet (#114) — 只在 backend 真返 en_text 时显示 */}
            {enText ? (
              <div className="workspace-hifi__rewrite-en-block">
                <div className="hf-overline workspace-hifi__rewrite-overline">
                  EN · IB / MBB style
                </div>
                <div className="workspace-hifi__rewrite-en-text">{enText}</div>
              </div>
            ) : null}

            {/* ── 底部按钮行 ────────────────────────────────────────────── */}
            <div className="workspace-hifi__rewrite-actions">
              <HFBtn
                variant="primary"
                size="md"
                onClick={() => {
                  const text = selected === 'v0' ? v0Text : v2Text;
                  onApply?.(selected, text);
                }}
                disabled={!v2Text && selected === 'v2'}
                icon={I.check(14)}
              >
                应用 {selected}
              </HFBtn>
              <HFBtn
                variant="ghost"
                size="md"
                onClick={onRegenerate}
                disabled={!onRegenerate}
              >
                再来 2 版
              </HFBtn>
              <HFBtn
                variant="link"
                size="md"
                onClick={onClose}
                style={{ marginLeft: 4 }}
              >
                保留原文
              </HFBtn>
            </div>
          </>
        )}

        {/* ── 守卫面板 (D-? 严契约红线 — 必须显式露出) ──────────────────── */}
        {!isLoading && !isError && (
          <FabricationGuardPanel warnings={warnings} />
        )}
      </div>
    </section>
  );
}
