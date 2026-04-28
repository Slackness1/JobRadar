'use client';

import { useEffect, useState } from 'react';
import { Check } from 'lucide-react';
import { getInterviewTurns, type TurnPayload } from './api';

const POLL_INTERVAL_MS = 2500;

const SKELETON_LABELS = [
  '自我介绍与来意',
  '主导过的核心项目',
  '关键技术 / 业务取舍',
  '在不确定下的决策',
  '为什么是这家公司',
  '反问环节',
];

interface RailItem {
  turnIndex: number | null; // null = placeholder for an unanswered skeleton slot
  label: string;
  source: 'skeleton' | 'follow_up' | 'fallback';
  parent: number | null;
}

/** Build a flat ordered render list with skeleton items + their nested follow-ups.
 *  Skeleton placeholders fill empty slots so the user always sees the planned 6.
 */
function buildRail(turns: TurnPayload[]): RailItem[] {
  const items: RailItem[] = [];
  const skeletonTurns = turns.filter((t) => t.question_source === 'skeleton')
    .sort((a, b) => a.turn_index - b.turn_index);

  // Pre-compute follow-ups grouped by parent_turn_index
  const followupsBy: Record<number, TurnPayload[]> = {};
  for (const t of turns) {
    if (t.question_source !== 'skeleton' && t.parent_turn_index != null) {
      (followupsBy[t.parent_turn_index] ||= []).push(t);
    }
  }

  for (let i = 0; i < SKELETON_LABELS.length; i++) {
    const skel = skeletonTurns[i];
    items.push({
      turnIndex: skel ? skel.turn_index : null,
      label: SKELETON_LABELS[i],
      source: 'skeleton',
      parent: null,
    });
    if (skel) {
      const childs = (followupsBy[skel.turn_index] || []).sort((a, b) => a.turn_index - b.turn_index);
      for (const c of childs) {
        items.push({
          turnIndex: c.turn_index,
          // Trim long LLM follow-up text for the rail; full text lives in caption.
          label: (c.question || '追问').replace(/\s+/g, ' ').slice(0, 22) + ((c.question || '').length > 22 ? '…' : ''),
          source: c.question_source === 'fallback' ? 'fallback' : 'follow_up',
          parent: skel.turn_index,
        });
      }
    }
  }
  // Orphan follow-ups (parent is null or refers to non-skeleton): append at end
  for (const t of turns) {
    if (
      t.question_source !== 'skeleton' &&
      (t.parent_turn_index == null || !skeletonTurns.find((s) => s.turn_index === t.parent_turn_index))
    ) {
      items.push({
        turnIndex: t.turn_index,
        label: (t.question || '追问').slice(0, 22) + ((t.question || '').length > 22 ? '…' : ''),
        source: t.question_source === 'fallback' ? 'fallback' : 'follow_up',
        parent: null,
      });
    }
  }
  return items;
}

export function ProgressRail({
  sessionId,
  currentTurnIndex,
  elapsedLabel,
}: {
  sessionId: string;
  /** turn_index of the question being currently asked / answered. */
  currentTurnIndex: number;
  elapsedLabel: string;
}) {
  const [turns, setTurns] = useState<TurnPayload[]>([]);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const data = await getInterviewTurns(sessionId);
        if (!cancelled) setTurns(data);
      } catch { /* silent */ }
    };
    tick();
    const id = setInterval(tick, POLL_INTERVAL_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, [sessionId]);

  const items = buildRail(turns);

  return (
    <aside
      className="absolute left-[28px] top-1/2 z-[3] hidden -translate-y-1/2 rounded-[18px] border border-[var(--border)] p-[16px_14px] xl:block"
      style={{ background: 'var(--ivory)', boxShadow: 'var(--shadow-whisper)', width: 224, maxHeight: '78vh', overflowY: 'auto' }}
    >
      <div className="mb-[12px] text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--olive)]">
        本轮 6 问 · 进度
      </div>
      {items.map((item, idx) => {
        const isCurrent = item.turnIndex !== null && item.turnIndex === currentTurnIndex;
        const isDone = item.turnIndex !== null && item.turnIndex < currentTurnIndex;
        const status: 'done' | 'now' | 'todo' = isCurrent ? 'now' : isDone ? 'done' : 'todo';
        const isChild = item.parent !== null;
        return (
          <div
            key={`${item.source}-${idx}-${item.turnIndex ?? 'placeholder'}`}
            className="-mx-[8px] flex items-start gap-[10px] rounded-[10px] p-[8px]"
            style={{
              background: status === 'now' ? '#fff2ec' : 'transparent',
              paddingLeft: isChild ? 24 : 8,
            }}
          >
            <span
              className="grid flex-none place-items-center rounded-full border text-[11px]"
              style={{
                width: isChild ? 16 : 22,
                height: isChild ? 16 : 22,
                background: status === 'done'
                  ? 'var(--emerald)'
                  : status === 'now'
                    ? 'var(--terracotta)'
                    : 'var(--library-rail)',
                color: status === 'todo' ? 'var(--stone)' : '#fff',
                borderColor: status === 'done'
                  ? 'var(--emerald)'
                  : status === 'now'
                    ? 'var(--terracotta)'
                    : 'var(--border)',
                animation: status === 'now' ? 'itv-pulse-dot 1.2s ease-in-out infinite' : undefined,
                fontFamily: 'var(--font-mono)',
                fontSize: isChild ? 9 : 11,
              }}
            >
              {status === 'done' ? <Check size={isChild ? 9 : 12} strokeWidth={2.2} /> : isChild ? '↪' : (item.turnIndex !== null ? item.turnIndex + 1 : items.filter(i => !i.parent).indexOf(item) + 1)}
            </span>
            <span
              className="pt-[2px] leading-[1.45]"
              style={{
                color: status === 'todo' ? 'var(--stone)' : 'var(--ink)',
                fontSize: isChild ? 11.5 : 12.5,
                fontStyle: isChild ? 'italic' : 'normal',
              }}
            >
              {isChild && <span className="mr-[4px] text-[var(--terracotta)]">追问</span>}
              {item.label}
            </span>
          </div>
        );
      })}
      <div
        className="mt-[14px] flex items-center justify-between border-t border-dashed border-[var(--border)] pt-[12px] text-[11px] text-[var(--olive)]"
      >
        <span>已进行</span>
        <span className="text-[13px] font-medium text-[var(--ink)]" style={{ fontFamily: 'var(--font-mono)' }}>
          {elapsedLabel}
        </span>
      </div>
    </aside>
  );
}
