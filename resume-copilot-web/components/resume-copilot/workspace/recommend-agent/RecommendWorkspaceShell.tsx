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
  postRecommendChat,
} from '../../api';
import type {
  RecommendFeedItem,
  ResumeCopilotSessionListItem,
  WorkingQuery,
} from '../../types';
import { RecommendTopBar } from './RecommendTopBar';
import { RecommendSkeletonPane } from './RecommendSkeletonPane';
import { RecommendFeedPane } from './RecommendFeedPane';
import {
  RecommendChatPane,
  type RecommendChatMessage,
} from './RecommendChatPane';

import './recommend-agent.css';

// 进场 agent 招呼语 —— 先按确认赛道 + 平时偏好给第一版,再让学生说人话调.
const SEED_GREETING: RecommendChatMessage = {
  id: 'seed-greeting',
  kind: 'turn',
  who: 'ai',
  text: '先按你的确认赛道 + 平时偏好排了第一版列表。想换方向、锁某家、或排除什么，直接说就行。',
};

// msgs 消息 id 自增计数器(模块级,纯展示用,不入业务态).
let msgSeq = 0;
function nextMsgId(prefix: string): string {
  msgSeq += 1;
  return `${prefix}-${msgSeq}`;
}

export interface RecommendWorkspaceShellProps {
  sessionId: number;
}

export function RecommendWorkspaceShell({ sessionId }: RecommendWorkspaceShellProps) {
  const router = useRouter();

  // ── 顶栏会话列表 ────────────────────────────────────────────────────────
  const [sessions, setSessions] = useState<ResumeCopilotSessionListItem[]>([]);

  // ── 共享态(子项③④ 接管) ────────────────────────────────────────────────
  const [msgs, setMsgs] = useState<RecommendChatMessage[]>([SEED_GREETING]);
  const [workingQuery, setWorkingQuery] = useState<WorkingQuery | null>(null);
  const [feed, setFeed] = useState<RecommendFeedItem[]>([]);
  const [highlightCompany, setHighlightCompany] = useState<string | null>(null);
  const [thinking, setThinking] = useState(false);
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

  // ── NL 对话发送(中栏 → 快路重排) ────────────────────────────────────────
  // 学生说人话 → 追加 user 气泡 → thinking(border-beam) → 调 recommend-chat:
  // agent 回复 + 意图解析 trace + (命中时) L3 记忆提示, feed / working query 同步更新.
  // 所有 setState 都在 async 回调内(await 之后), react-compiler 安全.
  const handleSend = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      setMsgs((cur) => [
        ...cur,
        { id: nextMsgId('me'), kind: 'turn', who: 'me', text: trimmed },
      ]);
      setThinking(true);

      try {
        const resp = await postRecommendChat(sessionId, trimmed);

        const appended: RecommendChatMessage[] = [
          { id: nextMsgId('ai'), kind: 'turn', who: 'ai', text: resp.reply },
          { id: nextMsgId('trace'), kind: 'trace', trace: resp.trace },
        ];
        if (resp.remembered) {
          appended.push({
            id: nextMsgId('memory'),
            kind: 'memory',
            text: `记忆 → L3 preference · 后台落库（${resp.remembered.dimension}=${resp.remembered.value}）`,
          });
        }
        setMsgs((cur) => [...cur, ...appended]);

        if (resp.feed !== null) setFeed(resp.feed);
        setWorkingQuery(resp.working_query);
      } catch {
        setMsgs((cur) => [
          ...cur,
          {
            id: nextMsgId('ai'),
            kind: 'turn',
            who: 'ai',
            text: '没太听懂，换个说法？feed 没动。',
          },
        ]);
      } finally {
        setThinking(false);
      }
    },
    [sessionId],
  );

  // 占位:供子项⑤(切换赛道)接管 —— 切赛道后 refetch 骨架.
  // 此处仅暴露,void 防 lint no-unused,子项⑤ 会真正调用.
  const refetchSkeleton = useCallback(() => {
    setSkeletonReloadKey((k) => k + 1);
  }, []);
  void refetchSkeleton;

  // 右栏「讲讲这家」→ 把「讲讲{公司}」当普通消息送中栏对话(intent=intel
  // 由后端识别);复用 handleSend,不另开 intel 取数链路.
  const handleIntel = useCallback(
    (company: string) => {
      void handleSend(`讲讲${company}`);
    },
    [handleSend],
  );

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

        {/* 中 — NL 对话 */}
        <div className="recommend-col recommend-col--chat">
          <RecommendChatPane msgs={msgs} thinking={thinking} onSend={handleSend} />
        </div>

        {/* 右 — 流动 feed */}
        <div className="recommend-col recommend-col--feed">
          <RecommendFeedPane
            sessionId={sessionId}
            workingQuery={workingQuery}
            feed={feed}
            setFeed={setFeed}
            setWorkingQuery={setWorkingQuery}
            onHighlightCompany={setHighlightCompany}
            onIntel={handleIntel}
          />
        </div>
      </div>
    </div>
  );
}
