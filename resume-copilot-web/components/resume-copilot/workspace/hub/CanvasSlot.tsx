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

import { useRef, useState } from 'react';

import { RecommendFeedPane, type RecommendFeedPaneProps } from '../recommend-agent/RecommendFeedPane';
import { RecommendSkeletonPane } from '../recommend-agent/RecommendSkeletonPane';
import { IntelDrawer } from '../intel/IntelDrawer';
import HubProfileView from './HubProfileView';
import ResumeCanvas from './ResumeCanvas';
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

/**
 * FeedWithIntel — feed 视图的上下分栏壳。
 *   上半:原 RecommendFeedPane(可滚, ~60%)。
 *   下半:点某岗「讲讲这家」就地展开该岗结构化情报卡(IntelDrawer, ~40%, 独立滚动)。
 *
 * 铁律:job 卡「讲讲这家」**只**设本地 intelJob —— 不碰中栏对话(不调 feedProps.onIntel)。
 */
function FeedWithIntel({ feedProps }: { feedProps: RecommendFeedPaneProps }) {
  const [intelJob, setIntelJob] = useState<{ company: string; jobId: string } | null>(
    null,
  );
  // 情报区高度占比(%),可拖中间分隔条上下调整,落 localStorage 记住。
  const SPLIT_KEY = 'hub.intelSplitPct';
  const [intelPct, setIntelPct] = useState<number>(() => {
    if (typeof window === 'undefined') return 58;
    const n = Number(window.localStorage.getItem(SPLIT_KEY));
    return Number.isFinite(n) && n >= 20 && n <= 85 ? n : 58;
  });
  const containerRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);

  function startSplitDrag(e: React.PointerEvent) {
    e.preventDefault();
    draggingRef.current = true;
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
    const onMove = (ev: PointerEvent) => {
      const el = containerRef.current;
      if (!draggingRef.current || !el) return;
      const rect = el.getBoundingClientRect();
      if (rect.height <= 0) return;
      // 情报区在下方:从底边量到指针 = 情报区高度。
      let pct = ((rect.bottom - ev.clientY) / rect.height) * 100;
      pct = Math.max(20, Math.min(85, pct));
      setIntelPct(pct);
    };
    const onUp = () => {
      draggingRef.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      setIntelPct((p) => {
        window.localStorage.setItem(SPLIT_KEY, String(Math.round(p)));
        return p;
      });
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  }

  return (
    <div
      ref={containerRef}
      style={{
        flex: 1,
        minHeight: 0,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* 上半:岗位推荐 feed —— 拦截 onIntel,只设本地态,不进对话。
          情报展开时按 intelPct 让出空间,收起时占满。 */}
      <div
        style={{
          flex: intelJob ? `1 1 ${100 - intelPct}%` : 1,
          minHeight: 0,
          overflow: 'auto',
        }}
      >
        <RecommendFeedPane
          {...feedProps}
          onIntel={(company, jobId) => setIntelJob({ company, jobId })}
        />
      </div>

      {intelJob ? (
        <>
          {/* 中间分隔条:既是明显分隔、又可上下拖拽调情报区高矮。 */}
          <div
            role="separator"
            aria-orientation="horizontal"
            aria-label="拖拽调整情报区高度"
            title="拖拽调整情报区高度"
            onPointerDown={startSplitDrag}
            className="hub-feed__split-handle"
          />
          {/* 下半:就地结构化情报卡(IntelDrawer),按 intelPct 占高,抽屉内部自滚(头部固定)。 */}
          <div
            className="hub-feed__intel-fill"
            style={{
              flex: `1 1 ${intelPct}%`,
              minHeight: 0,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              background: 'var(--parchment)',
            }}
          >
            <IntelDrawer
              key={intelJob.jobId}
              companyName={intelJob.company}
              jobKey={intelJob.jobId}
              onClose={() => setIntelJob(null)}
              hideFooter
            />
          </div>
        </>
      ) : (
        <div
          style={{
            flex: 'none',
            borderTop: '1px solid var(--border-warm)',
            padding: '8px 14px',
            fontSize: 12,
            color: 'var(--ink-soft, #8a7e6f)',
            opacity: 0.7,
          }}
        >
          点某个岗的「🏢 讲讲这家」看同辈情报(就地展开,不进对话)
        </div>
      )}
    </div>
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
  // 拖拽宽度: 覆盖默认 SLOT_WIDTH, 落 localStorage, 刷新后记住。active 必为非 none(下方 guard 前置)。
  const WIDTH_KEY = 'hub.canvasSlotWidth';
  const MIN_W = 360;
  const [overrideW, setOverrideW] = useState<number | null>(() => {
    if (typeof window === 'undefined') return null;
    const v = window.localStorage.getItem(WIDTH_KEY);
    const n = v ? Number(v) : NaN;
    return Number.isFinite(n) ? n : null;
  });
  const draggingRef = useRef(false);

  if (active === 'none') return null;

  const width = overrideW ?? SLOT_WIDTH[active];

  function startResize(e: React.PointerEvent) {
    e.preventDefault();
    const startX = e.clientX;
    const startW = width;
    draggingRef.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    const onMove = (ev: PointerEvent) => {
      if (!draggingRef.current) return;
      const maxW = Math.min(window.innerWidth * 0.72, 1100);
      // 面板在右侧:向左拖(clientX 变小)= 变宽。
      const next = Math.max(MIN_W, Math.min(maxW, startW + (startX - ev.clientX)));
      setOverrideW(next);
    };
    const onUp = () => {
      draggingRef.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      setOverrideW((w) => {
        if (w != null) window.localStorage.setItem(WIDTH_KEY, String(Math.round(w)));
        return w;
      });
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  }

  return (
    <div
      className="hf-slide"
      data-session-id={sessionId}
      style={{
        position: 'relative',
        width,
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
      {/* 左缘拖拽手柄:向左拖加宽右栏 tab,松手记住宽度。 */}
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="拖拽调整面板宽度"
        onPointerDown={startResize}
        className="hub-canvas__resize-handle"
        title="拖拽调整宽度"
      />

      {/* profile / resume 视图自带头部关闭(panel onClose → ✕), 不叠全局浮层关闭, 免双按钮. */}
      {active !== 'profile' && active !== 'resume' && <CloseButton onClose={onClose} />}

      {/* 个人档案: B 闭环视图(真 KB 数据, 确认/否掉). 自带头部 + 滚动体,
          直接占满 flex 列(header flex:none + body flex:1), 不套通用 overflow 容器. */}
      {active === 'profile' ? (
        <HubProfileView sessionId={sessionId} onClose={onClose} />
      ) : active === 'resume' ? (
        // 简历优化: 只内嵌「打分 + 小预览」面板(embedded). 与 HubShell 同源
        // data-theme="hub"(外层已挂), 故**不**套 recommend 主题壳; 直接撑满槽位.
        // 自带头部 ✕(onClose)→ 收回全宽对话. 展开的大编辑器**不**塞进对话,
        // 「展开编辑器/深度优化」走独立编辑页(见 ResumeCanvas embedded 分支)。
        <ResumeCanvas sessionId={sessionId} embedded onClose={onClose} />
      ) : (
        // data-theme="recommend": feed / skeleton 是 /recommend 同源组件, 其样式全
        // scope 在 [data-theme='recommend'] 下; Hub 槽位里必须套这层壳样式才生效。
        // 关键: 这层必须是 **flex 列 + overflow:hidden** —— /recommend 页里这俩 Pane
        // 的父级就是 flex 列, feed(height:100%)/skeleton(flex:1+overflow:auto)才能各自
        // 内部滚动。之前用 block + overflow:auto, skeleton 的 flex:1 落空 → 梯队栏滚不动
        // (头部 16 家压住 腰部/其他, 看着像「只有第一梯队」)。
        <div
          data-theme="recommend"
          style={{ flex: 1, minHeight: 0, height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
        >
          {active === 'feed' && <FeedWithIntel feedProps={feedProps} />}

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
        </div>
      )}
    </div>
  );
}
