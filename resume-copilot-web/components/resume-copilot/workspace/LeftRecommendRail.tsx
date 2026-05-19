'use client';

/**
 * LeftRecommendRail — 左栏推荐 (E-2 / D-1 / D-2 / D-3 / D-5 / D-6).
 *
 * FE-1 placeholder。真正实现由 FE-2 子代理来做:
 *   - 卡片可展开,同一时间只允许 1 张展开
 *   - 两层分(规则 + LLM 共识),snapshot 删除后
 *   - "为什么推" bullet 列表 + ✗ 反馈 inline 表单
 *   - FLIP 1.5s 柔和重排
 *
 * 此 placeholder 只负责:
 *   - 渲染 pane 容器 + header
 *   - 暴露 props 接口让 PublicResumeCopilot 把已有的 recommendations + 回调
 *     提前接进来,FE-2 实现时只填 body
 *
 * TODO(FE-2): 现 `<ResumeChatRail>` 里的推荐列表 JSX 应该搬过来 ──
 *             见 public-resume-copilot.tsx 旧 `RecommendationsBlock` /
 *             "推荐结果" 段落(原 ResumeChatRail 内部)。
 */

import type { ResumeRecommendationResult, ResumeCopilotSession } from '../types';
import { I } from '@/components/hifi/hifi-primitives';

export interface LeftRecommendRailProps {
  session: ResumeCopilotSession | null;
  recommendations: ResumeRecommendationResult | null;
  /** 学生点 ✗ 反馈触发(FE-2 实现时连后端 D-2/D-3) */
  onRejectRecommendation?: (jobId: string, reason: string, note: string) => void;
  /** 学生点 "针对这家改写" 触发 — 跨栏信号给 RightResumePane 出 chat 思考 (C-6) */
  onRequestRewrite?: (jobId: string) => void;
}

export function LeftRecommendRail({
  session,
  recommendations,
  onRejectRecommendation,
  onRequestRewrite,
}: LeftRecommendRailProps) {
  // Reserved for FE-2 wiring; reference so lint stays clean while the shell ships.
  void onRejectRecommendation;
  void onRequestRewrite;

  const itemCount = recommendations?.items?.length ?? 0;
  const sessionReady = session?.has_recommendations === true;

  return (
    <aside className="workspace-hifi__pane workspace-hifi__pane--left" aria-label="推荐岗位">
      <header className="workspace-hifi__pane-header">
        <span className="workspace-hifi__pane-header-icon" aria-hidden>
          {I.radar(16)}
        </span>
        <span>推荐</span>
        <span className="workspace-hifi__pane-header-count">
          {sessionReady ? `${itemCount} 条` : '等待生成'}
        </span>
      </header>
      <div className="workspace-hifi__pane-body">
        <div className="workspace-hifi__placeholder">
          <span className="workspace-hifi__placeholder-todo">FE-2 占位</span>
          <span className="workspace-hifi__placeholder-title">推荐列表</span>
          <span className="workspace-hifi__placeholder-hint">
            E-2 / D-1 / D-2 / D-3 / D-5 / D-6
            <br />
            原 ResumeChatRail 内的推荐区将搬到这里。
          </span>
        </div>
      </div>
    </aside>
  );
}
