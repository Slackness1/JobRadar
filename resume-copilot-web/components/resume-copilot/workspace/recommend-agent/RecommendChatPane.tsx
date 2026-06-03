'use client';

/**
 * RecommendChatPane — 「推荐工作台」中栏:NL 推荐对话 (Phase G 子项③).
 *
 * 列头(agent 头像 + 标题 + 快路 pill) + 消息流 + Composer. 本组件不持有业务态 ——
 * msgs / thinking / onSend 全由 RecommendWorkspaceShell 下传(Shell 是单一真相源,
 * setFeed / setWorkingQuery 也在 Shell 的 onSend 里调). 这里只渲染 + 把输入回弹给 Shell.
 *
 * 消息流是一个 discriminated union(turn / trace / memory / intel),本文件 export
 * `RecommendChatMessage` 供 Shell 给它的 msgs state 标类型.
 *
 * react-compiler:本组件无 setState(纯渲染 + 回调透传);子组件的 setState 都在
 * 事件 / interval 回调里. 自动滚动用 ref + effect(只读 scrollHeight,不 setState).
 */

import { useEffect, useRef } from 'react';

import type { RecommendTrace } from '../../types';
import { Composer, type ComposerChip } from './chat/Composer';
import { MemoryToast } from './chat/MemoryToast';
import { RecommendAvatar } from './chat/RecommendAvatar';
import { ThinkingCard } from './chat/ThinkingCard';
import { TraceCard } from './chat/TraceCard';
import { Turn } from './chat/Turn';

/** 中栏消息流的一条 —— turn(me/ai 气泡)/ trace(意图解析)/ memory(L3 提示)/ intel. */
export type RecommendChatMessage =
  | { id: string; kind: 'turn'; who: 'me' | 'ai'; text: string }
  | { id: string; kind: 'trace'; trace: RecommendTrace }
  | { id: string; kind: 'memory'; text: string }
  | { id: string; kind: 'intel'; text: string };

/** 快捷 chip —— 点一下就把 label 当一条消息发出. */
const QUICK_CHIPS: ComposerChip[] = [
  { key: 'more-fixed-income', label: '多来点固收' },
  { key: 'no-soe', label: '一直不考虑国企' },
  { key: 'top-brokers-by-pay', label: '只看头部券商资管按薪资' },
  { key: 'intel', label: '讲讲某家' },
];

const COMPOSER_PLACEHOLDER = '只看头部券商资管 / 讲讲中信资管 / 就按这个锁定…';

export interface RecommendChatPaneProps {
  msgs: RecommendChatMessage[];
  thinking: boolean;
  onSend: (text: string) => void;
}

export function RecommendChatPane({ msgs, thinking, onSend }: RecommendChatPaneProps) {
  const bodyRef = useRef<HTMLDivElement | null>(null);

  // 新消息 / thinking 切换时滚到底. 只读写 DOM scrollTop,不 setState.
  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [msgs, thinking]);

  return (
    <div className="recommend-chat">
      <div className="recommend-chat__head">
        <RecommendAvatar size={32} />
        <div className="recommend-chat__head-text">
          <div className="recommend-chat__head-title">推荐 agent</div>
          <div className="recommend-chat__head-sub">
            说人话换方向 · 秒级重排，不动确认赛道
          </div>
        </div>
        <span className="recommend-chat__head-pill hf-pill">
          <span className="recommend-chat__head-pill-dot" />
          快路 · 规则排
        </span>
      </div>

      <div ref={bodyRef} className="recommend-chat__body">
        {msgs.map((m) => {
          if (m.kind === 'turn') {
            return (
              <Turn key={m.id} who={m.who}>
                {m.text}
              </Turn>
            );
          }
          if (m.kind === 'trace') {
            return <TraceCard key={m.id} trace={m.trace} />;
          }
          if (m.kind === 'memory') {
            return <MemoryToast key={m.id} text={m.text} />;
          }
          // intel —— 简短 ai 备注(本子项暂走文本,情报卡留给后续)
          return (
            <Turn key={m.id} who="ai">
              {m.text}
            </Turn>
          );
        })}
        {thinking && <ThinkingCard />}
      </div>

      <Composer
        chips={QUICK_CHIPS}
        placeholder={COMPOSER_PLACEHOLDER}
        disabled={thinking}
        onSend={onSend}
      />
    </div>
  );
}
