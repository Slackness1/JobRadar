'use client';

/**
 * FabricationGuardPanel — RewritePane 守卫面板 (P1, D-? 严契约硬约束).
 *
 * 设计参考 `hifi-ws-intel.jsx::HFRewrite` 末尾守卫卡.
 *
 * 显式展示 backend `_detect_fabricated_numbers` warning 列表.
 *   - 命中: terra 红框醒目, 列出每个编造的数字 + suggestion_options
 *   - 没命中: ivory 卡 + "守卫已通过" emerald 小标
 *
 * 红线 (CLAUDE.md):
 *   - 警告不能被 suppress / hide. 这里不允许折叠或自动消失.
 *   - 数据源 = backend RewriteV0V2Out.v2.warnings (RewriteWarningDto[]).
 */

import { I } from '@/components/hifi/hifi-primitives';
import type { RewriteWarningDto } from '../../api';
import type { RewriteAuditRisk } from '../../types';

export interface FabricationGuardPanelProps {
  /** 来自 RewriteV0V2Out.v2.warnings — backend 已 substring-validate. */
  warnings?: RewriteWarningDto[];
  /** P1 占位:目前 v0v2 endpoint 不返 audit_risks; 给以后 BE 扩展留口子. */
  auditRisks?: RewriteAuditRisk[];
}

export function FabricationGuardPanel({
  warnings,
  auditRisks,
}: FabricationGuardPanelProps) {
  const fabricated = (warnings ?? []).filter(
    (w) => w.type === 'fabricated_number',
  );
  const otherWarns = (warnings ?? []).filter(
    (w) => w.type !== 'fabricated_number',
  );
  const blockingRisks = (auditRisks ?? []).filter((r) => r.blocking);

  const hasIssue =
    fabricated.length > 0 || otherWarns.length > 0 || blockingRisks.length > 0;

  return (
    <aside
      className={`workspace-hifi__guard-panel${hasIssue ? ' is-alert' : ''}`}
      role={hasIssue ? 'alert' : 'note'}
      aria-label="守卫面板"
    >
      <span className="workspace-hifi__guard-panel-icon" aria-hidden>
        {I.shield(15)}
      </span>
      <div className="workspace-hifi__guard-panel-body">
        {hasIssue ? (
          <>
            <div className="workspace-hifi__guard-panel-headline">
              <strong>守卫:</strong> AI 改写命中 {fabricated.length + otherWarns.length + blockingRisks.length} 个编造风险, 学生需要确认.
            </div>
            {fabricated.length > 0 && (
              <ul className="workspace-hifi__guard-panel-list">
                {fabricated.map((w, i) => (
                  <li key={`fab-${i}`}>
                    <span className="workspace-hifi__guard-panel-num">
                      &ldquo;{w.number || '(未知数字)'}&rdquo;
                    </span>
                    {w.detail ? <span> — {w.detail}</span> : null}
                  </li>
                ))}
              </ul>
            )}
            {otherWarns.length > 0 && (
              <ul className="workspace-hifi__guard-panel-list">
                {otherWarns.map((w, i) => (
                  <li key={`oth-${i}`}>{w.detail || w.type}</li>
                ))}
              </ul>
            )}
            {blockingRisks.length > 0 && (
              <ul className="workspace-hifi__guard-panel-list">
                {blockingRisks.map((r, i) => (
                  <li key={`risk-${i}`}>
                    <strong>{r.kind}</strong> — {r.detail}
                  </li>
                ))}
              </ul>
            )}
          </>
        ) : (
          <>
            <div className="workspace-hifi__guard-panel-headline">
              <strong>守卫:</strong> 改写文本里的数字均 substring 命中你简历原文。LLM 不会编不存在的数字 / 公司 / 学校。
            </div>
            <div className="workspace-hifi__guard-panel-pass">
              <span className="hf-pill emerald">
                <span style={{ display: 'inline-flex' }}>{I.check(11)}</span>
                守卫已通过
              </span>
            </div>
          </>
        )}
        <button
          type="button"
          className="workspace-hifi__guard-panel-link"
          onClick={() => {
            // P1 placeholder — P2 wire to docs / decisions panel.
            console.log('[FabricationGuardPanel] full rules — wire P2');
          }}
        >
          看完整守卫规则 →
        </button>
      </div>
    </aside>
  );
}
