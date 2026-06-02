'use client';
import { useState } from 'react';
import type { ResumeAgentTraceItem } from '../types';

export function WorkspaceThinkingTimeline({
  trace,
  running,
}: {
  trace: ResumeAgentTraceItem[];
  running: boolean;
}) {
  const [expanded, setExpanded] = useState(true);
  if (!running && !trace.length) return null;

  // 按 step_index 折叠成每阶段一行：已完成优先且粘住；否则用最新的一条
  // (后到覆盖先到) → "强模型精排 x/N" 这类计数能原地动起来。
  const stepMap = new Map<number, ResumeAgentTraceItem>();
  for (const it of trace) {
    const idx = it.step_index ?? 0;
    if (!idx) continue;
    const ex = stepMap.get(idx);
    if (!ex || it.status === 'completed' || ex.status !== 'completed') {
      stepMap.set(idx, it);
    }
  }
  const steps = [...stepMap.values()].sort(
    (a, b) => (a.step_index ?? 0) - (b.step_index ?? 0),
  );
  const finishedAll = !running && steps.length > 0;

  // 完成后收成一行，可点开
  if (finishedAll && !expanded) {
    return (
      <button
        type="button"
        className="workspace-hifi__think-collapsed"
        onClick={() => setExpanded(true)}
      >
        ✓ 已完成 · {steps.length} 步推理 · 点开看
      </button>
    );
  }

  return (
    <div className="workspace-hifi__think" data-running={running ? '1' : '0'}>
      <div className="workspace-hifi__think-head">
        <span>{running ? 'AI 正在为你推理…' : '推理完成'}</span>
        {finishedAll && (
          <button
            type="button"
            className="workspace-hifi__think-toggle"
            onClick={() => setExpanded(false)}
          >
            收起
          </button>
        )}
      </div>
      <ol className="workspace-hifi__think-list">
        {steps.map((s) => (
          <li key={s.step_index} data-status={s.status}>
            <span className="workspace-hifi__think-mark">
              {s.status === 'completed' ? '✓' : '⟳'}
            </span>
            <div className="workspace-hifi__think-body">
              <div className="workspace-hifi__think-msg">{s.message}</div>
              {s.result_summary ? (
                <div className="workspace-hifi__think-reason">{s.result_summary}</div>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
