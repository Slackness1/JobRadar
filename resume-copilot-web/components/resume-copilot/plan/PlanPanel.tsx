'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import { approvePlan, getPlan, postPlanTurn, startPlan } from './api';
import type { ItemKind, ItemStatus, PlanItem, PlanState } from './types';

interface PlanPanelProps {
  sessionId: number;
}

// status → terracotta-derived color
const STATUS_COLOR: Record<ItemStatus, { bg: string; fg: string; label: string }> = {
  pending:         { bg: '#f5f4ed', fg: '#6b665e', label: '待处理' },
  clarifying:      { bg: '#fdf2dc', fg: '#a86628', label: '追问中' },
  ready_to_write:  { bg: '#fbeadf', fg: '#a04922', label: '可写入' },
  drafting:        { bg: '#e7f0ff', fg: '#1f59c4', label: '生成中' },
  awaiting_review: { bg: '#fff2c2', fg: '#7a5d10', label: '待确认' },
  finalized:       { bg: '#dff5e1', fg: '#1f7032', label: '已定稿' },
  dropped:         { bg: '#eee', fg: '#999', label: '已删除' },
  blocked:         { bg: '#f0f0f0', fg: '#777', label: '暂停' },
};

const KIND_LABEL: Record<ItemKind, string> = {
  self_intro:      '自我介绍',
  education:       '教育经历',
  internship:      '实习',
  project:         '项目',
  campus_activity: '社团/活动',
  skill:           '技能',
  award:           '奖项',
};

function groupItemsByParent(items: PlanItem[]): Map<string | null, PlanItem[]> {
  const map = new Map<string | null, PlanItem[]>();
  for (const it of items) {
    const key = it.parent_id ?? null;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(it);
  }
  for (const list of map.values()) list.sort((a, b) => a.order - b.order);
  return map;
}

export function PlanPanel({ sessionId }: PlanPanelProps) {
  const [plan, setPlan] = useState<PlanState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const p = await getPlan(sessionId);
      setPlan(p);
    } catch (e: unknown) {
      const err = e as { status?: number; detail?: unknown };
      if (err.status === 404) {
        setPlan(null);  // expected pre-start
      } else {
        setError(String(err.detail ?? err));
      }
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => { void reload(); }, [reload]);

  const handleStart = useCallback(async () => {
    setBusy(true); setError('');
    try {
      const p = await startPlan(sessionId);
      setPlan(p);
    } catch (e: unknown) {
      const err = e as { detail?: unknown };
      setError(String(err.detail ?? e));
    } finally {
      setBusy(false);
    }
  }, [sessionId]);

  const handleApprove = useCallback(async () => {
    setBusy(true); setError('');
    try {
      const p = await approvePlan(sessionId);
      setPlan(p);
    } catch (e: unknown) {
      const err = e as { detail?: unknown };
      setError(String(err.detail ?? e));
    } finally {
      setBusy(false);
    }
  }, [sessionId]);

  const handleTurn = useCallback(async () => {
    if (!input.trim()) return;
    setBusy(true); setError('');
    const userMessage = input;
    setInput('');
    try {
      const p = await postPlanTurn(sessionId, { content: userMessage, targetItemId: selectedId });
      setPlan(p);
      if (p.current_item_id) setSelectedId(p.current_item_id);
    } catch (e: unknown) {
      const err = e as { detail?: unknown };
      setError(String(err.detail ?? e));
    } finally {
      setBusy(false);
    }
  }, [input, selectedId, sessionId]);

  const itemsByParent = useMemo(
    () => (plan ? groupItemsByParent(plan.items) : new Map()),
    [plan],
  );
  const selectedItem = useMemo(
    () => plan?.items.find(i => i.id === selectedId) ?? null,
    [plan, selectedId],
  );

  // ── States: no plan yet, draft pending, normal ────────────────────────────

  if (loading) {
    return <div className="p-8 text-sm text-gray-500">加载计划中…</div>;
  }

  if (!plan) {
    return (
      <div className="p-8 max-w-xl">
        <h2 className="text-xl font-semibold mb-4">定向简历建造</h2>
        <p className="text-sm text-gray-600 mb-6">
          基于已上传的简历建立一份「逐条追问 + 证据闸门」的建造计划。
          AI 不会一次性写完——会一条一条问、一条一条写、每条都标出处。
        </p>
        <button
          onClick={handleStart}
          disabled={busy}
          className="px-4 py-2 bg-orange-700 text-white rounded hover:bg-orange-800 disabled:opacity-50"
        >
          {busy ? '初始化中…' : '生成建造计划'}
        </button>
        {error && <div className="mt-3 text-sm text-red-600">{error}</div>}
      </div>
    );
  }

  // ── Awaiting approval banner ──────────────────────────────────────────────

  const isAwaitingApproval = plan.status === 'awaiting_plan_approval';

  return (
    <div className="flex h-full" style={{ fontFamily: 'Inter, "Noto Sans SC", system-ui' }}>
      {/* Left: items list */}
      <aside className="w-80 border-r overflow-y-auto p-3 bg-white">
        <h3 className="font-semibold mb-2 text-sm uppercase tracking-wider text-gray-600">
          建造计划 (v{plan.version})
        </h3>
        <div className="text-xs text-gray-500 mb-3">
          状态: {plan.status} · {plan.items.length} 项
        </div>
        <PlanItemTree
          parentMap={itemsByParent}
          parentId={null}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
      </aside>

      {/* Right: detail + input */}
      <main className="flex-1 flex flex-col">
        {isAwaitingApproval && (
          <div className="border-b bg-yellow-50 px-4 py-3 flex items-center justify-between">
            <span className="text-sm text-yellow-900">
              计划已生成。检查左侧列表，调整后点击「批准并开始追问」。
            </span>
            <button
              onClick={handleApprove}
              disabled={busy}
              className="px-3 py-1.5 bg-orange-700 text-white text-sm rounded hover:bg-orange-800 disabled:opacity-50"
            >
              批准并开始追问
            </button>
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-6">
          {selectedItem ? (
            <ItemDetail item={selectedItem} />
          ) : (
            <div className="text-sm text-gray-500">
              👈 从左侧选一条 plan item 开始
            </div>
          )}
        </div>

        {!isAwaitingApproval && (
          <div className="border-t p-4 bg-white">
            <div className="text-xs text-gray-500 mb-2">
              {selectedItem
                ? `正在处理: ${KIND_LABEL[selectedItem.kind]} · ${selectedItem.title}`
                : '提示: 选中一条 item 后输入答复'}
            </div>
            <div className="flex gap-2">
              <textarea
                value={input}
                onChange={e => setInput(e.target.value)}
                placeholder="回答 agent 的问题，或描述这条经历的细节…"
                className="flex-1 border rounded p-2 text-sm h-20 resize-none"
                disabled={busy}
              />
              <button
                onClick={handleTurn}
                disabled={busy || !input.trim()}
                className="px-4 py-2 bg-orange-700 text-white rounded hover:bg-orange-800 disabled:opacity-50 self-end"
              >
                {busy ? '处理中…' : '发送'}
              </button>
            </div>
            {error && <div className="mt-2 text-sm text-red-600">{error}</div>}
          </div>
        )}
      </main>
    </div>
  );
}

interface PlanItemTreeProps {
  parentMap: Map<string | null, PlanItem[]>;
  parentId: string | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
  depth?: number;
}

function PlanItemTree({ parentMap, parentId, selectedId, onSelect, depth = 0 }: PlanItemTreeProps) {
  const items = parentMap.get(parentId) || [];
  if (items.length === 0) return null;
  return (
    <ul className={depth === 0 ? '' : 'ml-3 border-l pl-2'}>
      {items.map(it => {
        const color = STATUS_COLOR[it.status];
        const isSelected = it.id === selectedId;
        return (
          <li key={it.id} className="mb-1">
            <button
              onClick={() => onSelect(it.id)}
              className={`w-full text-left px-2 py-1 rounded text-sm flex items-center justify-between gap-2 ${
                isSelected ? 'ring-2 ring-orange-600' : 'hover:bg-gray-50'
              }`}
            >
              <span className="truncate">{it.title}</span>
              <span
                className="text-[10px] px-1.5 py-0.5 rounded shrink-0"
                style={{ backgroundColor: color.bg, color: color.fg }}
              >
                {color.label}
              </span>
            </button>
            <PlanItemTree
              parentMap={parentMap}
              parentId={it.id}
              selectedId={selectedId}
              onSelect={onSelect}
              depth={depth + 1}
            />
          </li>
        );
      })}
    </ul>
  );
}

function ItemDetail({ item }: { item: PlanItem }) {
  const color = STATUS_COLOR[item.status];
  return (
    <div className="max-w-3xl">
      <div className="flex items-center gap-2 mb-3">
        <h2 className="text-lg font-semibold">{item.title}</h2>
        <span
          className="text-xs px-2 py-0.5 rounded"
          style={{ backgroundColor: color.bg, color: color.fg }}
        >
          {color.label}
        </span>
      </div>
      <div className="text-xs text-gray-500 mb-4">类型: {KIND_LABEL[item.kind]}</div>

      {item.rationale && (
        <section className="mb-4">
          <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-1">说明</h3>
          <p className="text-sm">{item.rationale}</p>
        </section>
      )}

      {item.open_questions.length > 0 && (
        <section className="mb-4">
          <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-1">待回答问题</h3>
          <ul className="space-y-1">
            {item.open_questions.map(q => (
              <li
                key={q.id}
                className={`text-sm border-l-2 pl-3 ${
                  q.answered_at ? 'border-green-400 text-gray-500 line-through' : 'border-amber-500'
                }`}
              >
                {q.text}
              </li>
            ))}
          </ul>
        </section>
      )}

      {item.draft && (
        <section className="mb-4">
          <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-1">当前草稿</h3>
          <div className="border rounded p-3 bg-amber-50 text-sm whitespace-pre-wrap">
            {item.draft.text}
          </div>
          {item.draft.risk_flags.length > 0 && (
            <div className="mt-2 text-xs space-y-0.5">
              {item.draft.risk_flags.map((f, i) => (
                <div
                  key={i}
                  className={f.blocking ? 'text-red-700' : 'text-amber-700'}
                >
                  ⚠ {f.kind}: {f.detail}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {item.evidence.length > 0 && (
        <section>
          <h3 className="text-xs uppercase tracking-wider text-gray-500 mb-1">
            证据 ({item.evidence.length})
          </h3>
          <ul className="space-y-2">
            {item.evidence.map(ev => (
              <li key={ev.id} className="border rounded p-2 text-sm bg-gray-50">
                <div className="text-xs text-gray-500 mb-1">{ev.source}</div>
                <div className="whitespace-pre-wrap mb-1">{ev.text}</div>
                {ev.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {ev.tags.map((t, i) => (
                      <span
                        key={i}
                        className="text-[10px] px-1.5 py-0.5 rounded bg-white border"
                        title={t.raw}
                      >
                        {t.type}: {t.value}
                      </span>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
