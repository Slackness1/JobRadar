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
 * 无 NL「锁定」功能(设计稿 lockOpen 不实现)。confirmed 主赛道只由顶栏「切换
 * 赛道」chip → 既有 TrackPickerModal 改(内部 PUT /preferences);NL 对话永不碰
 * confirmed。切换成功后联动:左骨架 refetch + 右 feed reseed + 中栏系统提示。
 *
 * react-compiler:所有 setState 都在 async 回调 / 事件内,组件 render 纯净.
 */

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

import {
  getResumeCopilotPreferences,
  getWorkingQuery,
  listResumeCopilotSessions,
  postRecommendChat,
  updateWorkingQuery,
} from '../../api';
import type {
  RecommendFeedItem,
  ResumeCopilotSessionListItem,
  ResumePreferencePayload,
  WorkingQuery,
} from '../../types';
import { TrackPickerModal } from '../TrackPickerModal';
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

  // ── 主赛道切换(显式入口 — confirmed 只由 TrackPickerModal 改) ─────────────
  // prefs:整份偏好(给 modal merge,避免重置其它字段);currentTrack:顶栏 chip 显示。
  const [prefs, setPrefs] = useState<ResumePreferencePayload | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const currentTrack = prefs?.preferred_tracks?.[0] ?? null;

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

  // 进场拉确认偏好 — 顶栏 chip 显示当前主赛道 + 切换时 merge 其它字段
  useEffect(() => {
    let cancelled = false;
    getResumeCopilotPreferences(sessionId)
      .then((r) => {
        if (!cancelled) setPrefs(r.preferences);
      })
      .catch(() => {
        if (!cancelled) setPrefs(null);
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

  // ── 主赛道切换成功(TrackPickerModal 内部已 PUT /preferences 落库 confirmed) ──
  // 三栏联动:左骨架按新 confirmed 重塑 / 右 feed 按新 confirmed reseed /
  // 中栏 push 一条系统提示。所有 setState 都在 async 回调内,react-compiler 安全。
  const handleTrackChanged = useCallback(async () => {
    // 左:梯队骨架 refetch(Task 9 机制 — reloadKey 自增触发 refetch)
    setSkeletonReloadKey((k) => k + 1);

    // 刷新顶栏 chip 的当前赛道(重读 confirmed 偏好)
    getResumeCopilotPreferences(sessionId)
      .then((r) => setPrefs(r.preferences))
      .catch(() => {});

    // 右:working query 按新 confirmed + L3 记忆 reseed → 用返回 feed 刷新右栏
    try {
      const { working_query, feed: reseeded } = await updateWorkingQuery(
        sessionId,
        { reseed: true },
      );
      setWorkingQuery(working_query);
      setFeed(reseeded);
    } catch {
      // reseed 失败不阻断 — 骨架已 refetch,feed 保留旧态
    }

    // 中:push 一条系统提示
    setMsgs((cur) => [
      ...cur,
      {
        id: nextMsgId('ai'),
        kind: 'turn',
        who: 'ai',
        text: '已切换主赛道 → 梯队骨架与推荐已同步更新。',
      },
    ]);
  }, [sessionId]);

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
        currentTrack={currentTrack}
        onChangeTrack={() => setPickerOpen(true)}
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

      {/* 切换主赛道 — confirmed 主赛道唯一显式改动入口(内部 PUT /preferences)。
          成功后 handleTrackChanged 联动左骨架 + 右 feed + 中栏系统提示。 */}
      <TrackPickerModal
        open={pickerOpen}
        sessionId={sessionId}
        currentTrack={currentTrack}
        currentPreferences={prefs}
        onChanged={handleTrackChanged}
        onClose={() => setPickerOpen(false)}
      />
    </div>
  );
}
