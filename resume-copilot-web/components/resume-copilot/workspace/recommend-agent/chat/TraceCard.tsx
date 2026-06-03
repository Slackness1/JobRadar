'use client';

/**
 * TraceCard — 意图解析 trace 折叠卡 (推荐工作台 NL 对话栏).
 *
 * 默认折叠,点开展示 intent / query_delta(JSON) / remember_note —— 让「这轮 agent
 * 怎么解你的话」可证伪. 数据来自 RecommendTurnResponse.trace.
 * 仅 open toggle 一个 state,setState 在 onClick 回调里,react-compiler 安全.
 */

import { useState } from 'react';

import type { RecommendTrace } from '../../../types';

export interface TraceCardProps {
  trace: RecommendTrace;
}

export function TraceCard({ trace }: TraceCardProps) {
  const [open, setOpen] = useState(false);

  let queryDeltaText: string;
  try {
    queryDeltaText = JSON.stringify(trace.query_delta ?? {}, null, 0);
  } catch {
    queryDeltaText = String(trace.query_delta);
  }

  return (
    <div className="recommend-chat__trace">
      <button
        type="button"
        className="recommend-chat__trace-toggle"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="recommend-chat__trace-label">意图解析</span> · flash 1 次
        <span className="recommend-chat__trace-chevron">▾</span>
      </button>
      {open && (
        <div className="recommend-chat__trace-body hf-slide">
          <div>
            intent: <b>{trace.intent}</b>
          </div>
          <div>query_delta: {queryDeltaText}</div>
          {trace.remember_note ? (
            <div>remember: {trace.remember_note}</div>
          ) : null}
        </div>
      )}
    </div>
  );
}
