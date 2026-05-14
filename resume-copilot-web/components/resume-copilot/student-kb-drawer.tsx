'use client';

/**
 * 我的求职档案 — Drawer-style panel showing the cross-session student KB.
 *
 * Phase 1 scope: list + confirm + archive + delete. No editing yet.
 * Data is captured passively by the chat-turn BackgroundTask in the backend;
 * everything here is a read/curation surface for the user.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  Check,
  Loader2,
  Trash2,
  X,
  Archive,
  AlertCircle,
  Brain,
} from 'lucide-react';

import {
  archiveStudentExperience,
  confirmStudentExperience,
  deleteStudentExperience,
  getStudentKbIndex,
  listStudentExperiences,
  type StudentExperienceDetail,
  type StudentExperienceIndexItem,
  type StudentKbIndexResponse,
} from './api';


const CATEGORY_LABEL: Record<string, string> = {
  experience: '经历',
  skill_claim: '技能',
  preference: '偏好',
  identity_fact: '身份',
};

const DIMENSION_LABEL: Record<string, string> = {
  leadership: '领导力',
  teamwork: '团队协作',
  conflict_resolution: '冲突解决',
  initiative: '主动性',
  deadline_pressure: '抗压',
  ambiguity: '不确定性',
  cross_functional: '跨部门',
  failure_recovery: '失败复盘',
  planning: '规划',
  analytical_thinking: '分析',
  creativity: '创意',
  communication: '沟通',
  stakeholder_mgmt: '相关方',
  ownership: 'Ownership',
};


function dimensionLabel(d: string): string {
  return DIMENSION_LABEL[d] || d;
}


interface Props {
  open: boolean;
  onClose: () => void;
}


export function StudentKbDrawer({ open, onClose }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [index, setIndex] = useState<StudentKbIndexResponse | null>(null);
  const [details, setDetails] = useState<Record<number, StudentExperienceDetail>>({});
  const [expanded, setExpanded] = useState<number | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const idx = await getStudentKbIndex(false);
      setIndex(idx);
      // Hydrate details for displayed cards so confirm/raw_excerpt render without an extra round-trip.
      const list = await listStudentExperiences({ limit: 100 });
      const detailMap: Record<number, StudentExperienceDetail> = {};
      for (const d of list.items) {
        detailMap[d.id] = d;
      }
      setDetails(detailMap);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      void refresh();
    }
  }, [open, refresh]);

  if (!open) return null;

  const items = index?.items ?? [];
  const pendingCount = index?.pending_confirm_count ?? 0;
  const totalCount = index?.total ?? 0;

  const handleConfirm = async (id: number) => {
    setBusyId(id);
    try {
      const updated = await confirmStudentExperience(id);
      setDetails((prev) => ({ ...prev, [id]: updated }));
      // Bump the index optimistically: just refresh the count display.
      setIndex((prev) =>
        prev
          ? {
              ...prev,
              pending_confirm_count: Math.max(0, prev.pending_confirm_count - 1),
              items: prev.items.map((it) =>
                it.id === id ? { ...it, user_confirmed: true } : it
              ),
            }
          : prev
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  const handleArchive = async (id: number) => {
    setBusyId(id);
    try {
      await archiveStudentExperience(id);
      // Refresh to remove from default (non-archived) view.
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('删除后无法恢复,确定吗？')) return;
    setBusyId(id);
    try {
      await deleteStudentExperience(id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      {/* Drawer */}
      <aside
        role="dialog"
        aria-label="我的求职档案"
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[520px] flex-col bg-white shadow-2xl"
      >
        <header className="flex h-[68px] shrink-0 items-center justify-between border-b border-slate-200 px-5">
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-full bg-[var(--primary)]/10 text-[var(--primary)]">
              <Brain className="size-5" />
            </span>
            <div>
              <div className="text-[15px] font-semibold leading-tight tracking-tight text-slate-950">
                我的求职档案
              </div>
              <div className="mt-0.5 text-xs leading-tight text-slate-500">
                {totalCount > 0 ? `${totalCount} 条已沉淀` : '暂未沉淀任何经历'}
                {pendingCount > 0 ? ` · ${pendingCount} 条待确认` : ''}
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="grid size-9 place-items-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <X className="size-5" />
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {loading && (
            <div className="flex items-center justify-center gap-2 py-12 text-slate-400">
              <Loader2 className="size-4 animate-spin" />
              <span className="text-sm">加载中…</span>
            </div>
          )}

          {error && (
            <div className="mb-4 flex items-start gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              <AlertCircle className="mt-0.5 size-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {!loading && !error && items.length === 0 && (
            <div className="rounded-xl border border-dashed border-slate-200 px-5 py-10 text-center">
              <Brain className="mx-auto size-7 text-slate-300" />
              <div className="mt-3 text-sm font-medium text-slate-700">还没有沉淀任何经历</div>
              <div className="mt-1 text-xs leading-5 text-slate-500">
                在聊天中详细聊聊你的项目、实习、活动经历,
                系统会自动把可用的内容沉淀到这里,
                <br />
                未来模拟面试时再调用出来。
              </div>
            </div>
          )}

          {!loading && !error && items.length > 0 && (
            <div className="space-y-3">
              {items.map((item) => (
                <ExperienceCard
                  key={item.id}
                  item={item}
                  detail={details[item.id]}
                  isExpanded={expanded === item.id}
                  onToggle={() => setExpanded((curr) => (curr === item.id ? null : item.id))}
                  busy={busyId === item.id}
                  onConfirm={() => handleConfirm(item.id)}
                  onArchive={() => handleArchive(item.id)}
                  onDelete={() => handleDelete(item.id)}
                />
              ))}
            </div>
          )}
        </div>

        <footer className="border-t border-slate-200 px-5 py-3 text-xs leading-5 text-slate-500">
          经历库会自动从你的对话中积累。
          模拟面试时,这里的经历会被优先调用,帮你回忆起合适的素材。
        </footer>
      </aside>
    </>
  );
}


interface CardProps {
  item: StudentExperienceIndexItem;
  detail: StudentExperienceDetail | undefined;
  isExpanded: boolean;
  onToggle: () => void;
  busy: boolean;
  onConfirm: () => void;
  onArchive: () => void;
  onDelete: () => void;
}


function ExperienceCard({
  item,
  detail,
  isExpanded,
  onToggle,
  busy,
  onConfirm,
  onArchive,
  onDelete,
}: CardProps) {
  const isExperience = item.category === 'experience';
  const confidencePct = Math.round(item.confidence * 100);

  return (
    <article
      className={
        'rounded-xl border bg-white transition-shadow ' +
        (item.user_confirmed
          ? 'border-slate-200'
          : 'border-amber-200 bg-amber-50/30')
      }
    >
      <button
        type="button"
        onClick={onToggle}
        className="block w-full px-4 py-3 text-left"
        aria-expanded={isExpanded}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                {CATEGORY_LABEL[item.category] || item.category}
              </span>
              {!item.user_confirmed && (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-800">
                  待确认
                </span>
              )}
              <span className="text-[11px] text-slate-400">
                {item.age_days === 0 ? '今天' : `${item.age_days} 天前`}
              </span>
            </div>
            <div className="mt-1.5 text-[14px] font-medium leading-snug text-slate-900">
              {item.summary}
            </div>
            {isExperience && item.star_dimensions.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {item.star_dimensions.slice(0, 4).map((d) => (
                  <span
                    key={d}
                    className="rounded bg-[var(--primary)]/10 px-1.5 py-0.5 text-[10px] font-medium text-[var(--primary)]"
                  >
                    {dimensionLabel(d)}
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="shrink-0 text-[11px] text-slate-400">
            置信 {confidencePct}%
          </div>
        </div>
      </button>

      {isExpanded && detail && (
        <div className="border-t border-slate-100 px-4 py-3 text-sm leading-6 text-slate-600">
          {detail.behavioral_hook && (
            <div className="mb-3">
              <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
                STAR 切入点
              </div>
              <div className="mt-1 whitespace-pre-wrap text-[13px] leading-6 text-slate-700">
                {detail.behavioral_hook}
              </div>
            </div>
          )}
          {detail.raw_excerpt && (
            <div className="mb-3">
              <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">
                原文片段
              </div>
              <blockquote className="mt-1 border-l-2 border-slate-200 pl-3 text-[12px] italic leading-5 text-slate-500">
                {detail.raw_excerpt}
              </blockquote>
            </div>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            {!item.user_confirmed && (
              <button
                type="button"
                disabled={busy}
                onClick={onConfirm}
                className="inline-flex items-center gap-1 rounded-md bg-emerald-600 px-2.5 py-1 text-[12px] font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                <Check className="size-3" />
                确认这条
              </button>
            )}
            <button
              type="button"
              disabled={busy}
              onClick={onArchive}
              className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[12px] font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            >
              <Archive className="size-3" />
              不再使用
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={onDelete}
              className="inline-flex items-center gap-1 rounded-md border border-red-200 bg-white px-2.5 py-1 text-[12px] font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
            >
              <Trash2 className="size-3" />
              删除
            </button>
          </div>
        </div>
      )}
    </article>
  );
}
