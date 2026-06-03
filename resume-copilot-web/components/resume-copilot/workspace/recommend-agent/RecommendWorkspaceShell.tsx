'use client';

/**
 * RecommendWorkspaceShell — 「推荐工作台」三栏 Shell (Phase G 子项①).
 *
 * 布局:梯队骨架(左·主) | NL 对话(中) | 流动 feed(右).
 *   grid: minmax(300,360) minmax(340,1fr) minmax(372,440)
 * 会话切换收进顶栏下拉(不是独立 sidebar). 中 / 右栏本子项为占位,由子项③④ 填充;
 * 但 Shell 在此持有全部共享态(msgs / workingQuery / feed / highlightCompany /
 * thinking / deepening / skeletonReloadKey),供后续子项接管.
 *
 * 无 NL「锁定」功能(设计稿 lockOpen 不实现);切换赛道是子项④.
 *
 * react-compiler:所有 setState 都在 async 回调 / 事件内,组件 render 纯净.
 */

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import {
  getWorkingQuery,
  listResumeCopilotSessions,
} from '../../api';
import type {
  CopilotMessage,
  RecommendFeedItem,
  ResumeCopilotSessionListItem,
  WorkingQuery,
} from '../../types';
import { RecommendTopBar } from './RecommendTopBar';
import { RecommendSkeletonPane } from './RecommendSkeletonPane';

import './recommend-agent.css';

export interface RecommendWorkspaceShellProps {
  sessionId: number;
}

export function RecommendWorkspaceShell({ sessionId }: RecommendWorkspaceShellProps) {
  const router = useRouter();

  // ── 顶栏会话列表 ────────────────────────────────────────────────────────
  const [sessions, setSessions] = useState<ResumeCopilotSessionListItem[]>([]);

  // ── 共享态(子项③④ 接管) ────────────────────────────────────────────────
  const [msgs] = useState<CopilotMessage[]>([]);
  const [workingQuery, setWorkingQuery] = useState<WorkingQuery | null>(null);
  const [feed] = useState<RecommendFeedItem[]>([]);
  const [highlightCompany, setHighlightCompany] = useState<string | null>(null);
  const [thinking] = useState(false);
  const [deepening] = useState<string | null>(null);
  // 切换赛道后(子项④)自增 → RecommendSkeletonPane refetch
  const [skeletonReloadKey, setSkeletonReloadKey] = useState(0);

  // 拉会话列表(顶栏下拉)
  useEffect(() => {
    let cancelled = false;
    listResumeCopilotSessions()
      .then((items) => {
        if (!cancelled) setSessions(items);
      })
      .catch(() => {
        if (!cancelled) setSessions([]);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  // 进场拉 working query(子项③ 用作 NL 对话初始上下文)
  useEffect(() => {
    let cancelled = false;
    getWorkingQuery(sessionId)
      .then((r) => {
        if (!cancelled) setWorkingQuery(r.working_query);
      })
      .catch(() => {
        if (!cancelled) setWorkingQuery(null);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const handleSelectSession = useCallback(
    (id: number) => {
      router.push(`/recommend?session=${id}`);
    },
    [router],
  );

  const handleNewSession = useCallback(() => {
    // 暂无 NL 新建会话端点 → 走简历上传入口(过渡期)
    router.push('/resume-copilot');
  }, [router]);

  // 占位:供子项③④ 接管 —— 切换赛道后 refetch 骨架 / feed 卡点联高亮.
  // 此处仅暴露,UI 未接入;void 防 lint no-unused,子项③④ 会真正调用.
  const refetchSkeleton = useCallback(() => {
    setSkeletonReloadKey((k) => k + 1);
  }, []);
  // 占位态供子项③④ 接管(NL 对话 / feed 列). void 防 lint no-unused.
  void refetchSkeleton;
  void setHighlightCompany;
  void workingQuery;
  void msgs;
  void feed;
  void thinking;
  void deepening;

  return (
    <div data-theme="recommend" className="hf">
      <RecommendTopBar
        sessions={sessions}
        activeSessionId={sessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
      />

      <div className="recommend-grid">
        {/* 左·主 — 梯队骨架(复用) */}
        <div className="recommend-col recommend-col--skeleton">
          <RecommendSkeletonPane
            sessionId={sessionId}
            highlightCompany={highlightCompany}
            reloadKey={skeletonReloadKey}
          />
        </div>

        {/* 中 — NL 对话(子项③ 填充) */}
        <div className="recommend-col recommend-col--chat">
          <div className="recommend-col__placeholder">
            <div className="recommend-col__placeholder-title">NL 推荐对话</div>
            <div className="recommend-col__placeholder-sub">
              说人话换方向 · 秒级重排，不动确认赛道。对话面板将在下一步接入。
            </div>
          </div>
        </div>

        {/* 右 — 流动 feed(子项④ 填充) */}
        <div className="recommend-col recommend-col--feed">
          <div className="recommend-col__placeholder">
            <div className="recommend-col__placeholder-title">流动推荐 feed</div>
            <div className="recommend-col__placeholder-sub">
              按当前工作查询排出的岗位列表将在这里展示，点击可联动左侧梯队骨架。
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
