'use client';

/**
 * CanvasSlot — 统一对话 Hub 右栏「会变形的画布槽」.
 *
 * 产品铁律(点开才出): 面板**不**在技能跑完时自动弹出 —— runSkill 故意 setActive('none'),
 *   让学生先看「想」的过程; 只有点结果卡 CTA(查看岗位 / 查看全景 …)才 setActive(那个视图),
 *   面板这才滑出. 关闭 → 全宽对话.
 *
 * 本任务(Task 7)只接通 feed 视图: 原样复用真实 RecommendFeedPane(它自带召回 + 深挖,
 *   深度匹配走 pane 内部 onDeepen → postRecommendDeepen, CanvasSlot 不重写).
 *   skeleton / resume / profile 分支留待 Task 8/9/10, 这里只占宽 + 占位.
 *
 * Token 全取自 `.hf`(外层 HubShell className="hf"); 左描边 + 羊皮纸底 + 全高 + 右上角关闭.
 */

import { RecommendFeedPane, type RecommendFeedPaneProps } from '../recommend-agent/RecommendFeedPane';
import { RecommendSkeletonPane } from '../recommend-agent/RecommendSkeletonPane';
import HubProfileView from './HubProfileView';
import ResumeSlotPlaceholder from './ResumeSlotPlaceholder';
import type { HubSlot } from './hub-types';

// 每个视图的宽度(对齐原型): feed 448 / skeleton 436 / resume 500 / profile 460.
const SLOT_WIDTH: Record<Exclude<HubSlot, 'none'>, number> = {
  feed: 448,
  skeleton: 436,
  resume: 500,
  profile: 460,
};

export interface CanvasSlotProps {
  active: HubSlot;
  sessionId: number;
  /** 真实 RecommendFeedPane 的全部 props(由 HubShell 持有共享态后传入)。 */
  feedProps: RecommendFeedPaneProps;
  /** feed 卡点选公司 → 梯队骨架卡高亮 + 滚动定位(Task 8)。 */
  highlightCompany?: string | null;
  /** 骨架公司卡「讲讲这家」→ 情报回流对话主轴。 */
  onOpenIntel?: (company: string, ctx?: { n_insights?: number }) => void;
  /** 骨架公司卡「定制深挖」→ 定制回流对话主轴。 */
  onOpenCoach?: (company: string) => void;
  onClose: () => void;
}

function CloseButton({ onClose }: { onClose: () => void }) {
  return (
    <button
      type="button"
      onClick={onClose}
      aria-label="关闭面板"
      title="关闭"
      className="hf-btn ghost sm"
      style={{
        position: 'absolute',
        top: 10,
        right: 12,
        zIndex: 2,
        width: 28,
        height: 28,
        minWidth: 28,
        padding: 0,
        borderRadius: 999,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <svg
        width="15"
        height="15"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M18 6 6 18M6 6l12 12" />
      </svg>
    </button>
  );
}

export default function CanvasSlot({
  active,
  sessionId,
  feedProps,
  highlightCompany,
  onOpenIntel,
  onOpenCoach,
  onClose,
}: CanvasSlotProps) {
  if (active === 'none') return null;

  return (
    <div
      className="hf-slide"
      data-session-id={sessionId}
      style={{
        position: 'relative',
        width: SLOT_WIDTH[active],
        flex: 'none',
        minWidth: 0,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        borderLeft: '1px solid var(--border-warm)',
        background: 'var(--parchment)',
        overflow: 'hidden',
      }}
    >
      {/* profile 视图自带头部关闭(SlotHead right), 不叠全局浮层关闭, 免双按钮. */}
      {active !== 'profile' && <CloseButton onClose={onClose} />}

      {/* 个人档案: B 闭环视图(真 KB 数据, 确认/否掉). 自带头部 + 滚动体,
          直接占满 flex 列(header flex:none + body flex:1), 不套通用 overflow 容器. */}
      {active === 'profile' ? (
        <HubProfileView sessionId={sessionId} onClose={onClose} />
      ) : (
        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          {active === 'feed' && <RecommendFeedPane {...feedProps} />}

          {/* 梯队骨架 —— 复用 /recommend 的同源 Pane(getPlatformsByTier),
              情报「讲讲这家」+ 定制「定制深挖」回流对话主轴。 */}
          {active === 'skeleton' && (
            <RecommendSkeletonPane
              sessionId={sessionId}
              highlightCompany={highlightCompany}
              onOpenIntel={onOpenIntel}
              onOpenCoach={onOpenCoach}
            />
          )}

          {/* 简历优化 — 接口位占位(真实打分/优化视图归 resume-copilot 分支，日后塞进同槽). */}
          {active === 'resume' && <ResumeSlotPlaceholder />}
        </div>
      )}
    </div>
  );
}
