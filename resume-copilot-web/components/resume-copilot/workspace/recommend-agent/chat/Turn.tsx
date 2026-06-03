'use client';

/**
 * Turn — me / ai 对话气泡 (推荐工作台 NL 对话栏).
 *
 * me 走深色右贴气泡;ai 走 ivory 左贴气泡 + agent avatar.
 * 纯展示,无 state — react-compiler 安全.
 */

import type { ReactNode } from 'react';

import { RecommendAvatar } from './RecommendAvatar';

export interface TurnProps {
  who: 'me' | 'ai';
  children: ReactNode;
}

export function Turn({ who, children }: TurnProps) {
  const me = who === 'me';
  return (
    <div
      className={`recommend-chat__turn hf-slide${me ? ' is-me' : ''}`}
    >
      {!me && <RecommendAvatar />}
      <div className="recommend-chat__bubble">{children}</div>
    </div>
  );
}
