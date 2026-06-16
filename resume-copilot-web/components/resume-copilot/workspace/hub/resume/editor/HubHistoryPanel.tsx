'use client';

import { useEffect, useState } from 'react';
import type { JSX } from 'react';
import { createPortal } from 'react-dom';
import {
  History,
  X,
  ArrowRight,
  TrendingUp,
  FileText,
  Plus,
  MessageSquare,
  Trash2,
} from 'lucide-react';
import type { ScoreReportData } from '../../../../api';

// 历史浮层里要展示的「会话项」(深度优化对话的轻量视图;含未打开的历史会话)。
export interface HistoryConvoItem {
  id: number;
  title: string;
  date: string;
  active?: boolean; // 正是当前激活的那个 tab
  open?: boolean; // 当前作为 tab 打开着(可能非激活)
}

// 历史浮层里要展示的「打分报告项」(从保存的版本派生)。
export interface HistoryReportItem {
  vid: string;
  track: string;
  score: number;
  potential?: string;
  date: string;
  current?: boolean;
}

// 评分按区间染色(与雷达 / 打分页同调)。
function scoreTone(v: number): { fg: string; bg: string; ring: string } {
  if (v >= 75) return { fg: 'var(--emerald)', bg: 'var(--emerald-soft)', ring: '#c7d9c2' };
  if (v >= 65) return { fg: 'var(--terracotta-strong)', bg: 'var(--terracotta-wash)', ring: '#eccfb6' };
  return { fg: 'var(--amber-fg)', bg: 'var(--amber-bg)', ring: '#ecdfa4' };
}

/** 从 ScoreReportData 派生出潜力区间短串。 */
export function reportPotential(r: ScoreReportData): string {
  return `${r.overall_potential_low}–${r.overall_potential_high}`;
}

export interface HubHistoryPanelProps {
  onClose: () => void;
  /** 深度优化对话 tab 列表(会话历史)。 */
  convos: HistoryConvoItem[];
  /** 保存版本的打分报告(最新在前)。 */
  reports: HistoryReportItem[];
  /** 点会话项 → 切到那个对话 tab。 */
  onOpenConvo?: (id: number) => void;
  /** 「开始新对话」(新增一个深度优化 tab)。 */
  onNew?: () => void;
  /** 点报告项 → 切到打分 tab 并展示那一版报告。 */
  onOpenReport?: (vid: string) => void;
  /** 打开浮层时初始选中的分段(跟随当前 AI 面板所在 tab)。 */
  initialSegment?: 'convo' | 'report';
  top?: number;
  right?: number;
  /** 删除一段会话(从历史移除)。 */
  onDeleteConvo?: (id: number) => void;
}

/** 历史记录浮层 — 两类历史:① 会话历史(深度优化 tab) ② 简历打分报告(保存版本)。
 *  移植自 hub-history.jsx,数据接真实对话 tab + 版本报告(非 mock)。
 *  portal 到 body,层级高于全屏编辑器壳;点外面 / Esc 关闭。 */
export function HubHistoryPanel({
  onClose,
  convos,
  reports,
  onOpenConvo,
  onNew,
  onOpenReport,
  initialSegment = 'convo',
  top = 56,
  right = 16,
  onDeleteConvo,
}: HubHistoryPanelProps): JSX.Element | null {
  // 初始分段跟随当前 AI 面板 tab(报告 tab→打分报告;深度对话 tab→会话历史);
  // 仍可在浮层内自由切换两段。
  const [tab, setTab] = useState<'convo' | 'report'>(initialSegment);
  const [pickConvo, setPickConvo] = useState<number | null>(null);
  const [pickReport, setPickReport] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState<number | null>(null);

  // Esc 关闭。
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);

  if (typeof document === 'undefined') return null;

  const TABS: [('convo' | 'report'), string, number][] = [
    ['convo', '会话历史', convos.length],
    ['report', '简历打分报告', reports.length],
  ];

  return createPortal(
    <div className="hf" data-theme="hub">
      {/* 点外面关掉 */}
      <div
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, zIndex: 80, background: 'transparent' }}
      />
      <div
        className="hub-pop"
        style={{
          position: 'fixed',
          top,
          right,
          zIndex: 81,
          width: 360,
          maxHeight: 'min(78vh, 640px)',
          display: 'flex',
          flexDirection: 'column',
          background: 'var(--ivory)',
          borderRadius: 18,
          boxShadow: 'var(--sh-paper)',
          overflow: 'hidden',
          transformOrigin: '90% 0',
        }}
      >
        {/* header */}
        <div style={{ flex: 'none', padding: '14px 14px 10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <span style={{ color: 'var(--terracotta-strong)', display: 'inline-flex', flex: 'none' }}>
              <History size={15} />
            </span>
            <span className="hf-overline" style={{ color: 'var(--olive)', flex: 'none' }}>
              历史记录
            </span>
            <span
              style={{
                font: '400 11px var(--font-sans)',
                color: 'var(--stone)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                flex: 1,
                minWidth: 0,
              }}
            >
              · 它都替你记着
            </span>
            <button
              onClick={onClose}
              title="关闭"
              aria-label="关闭"
              style={{
                flex: 'none',
                width: 26,
                height: 26,
                borderRadius: 8,
                display: 'grid',
                placeItems: 'center',
                color: 'var(--stone)',
                cursor: 'pointer',
                border: 'none',
                background: 'transparent',
                boxShadow: '0 0 0 1px var(--border-warm)',
              }}
            >
              <X size={13} />
            </button>
          </div>
          {/* segmented tabs */}
          <div
            style={{
              display: 'flex',
              gap: 3,
              padding: 3,
              background: 'var(--library-rail)',
              borderRadius: 11,
              boxShadow: '0 0 0 1px var(--border-warm)',
            }}
          >
            {TABS.map(([k, t, n]) => (
              <button
                key={k}
                onClick={() => setTab(k)}
                style={{
                  flex: 1,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 6,
                  cursor: 'pointer',
                  border: 'none',
                  font: `${tab === k ? 600 : 500} 12.5px var(--font-sans)`,
                  padding: '7px 0',
                  borderRadius: 8,
                  color: tab === k ? 'var(--ink)' : 'var(--olive)',
                  background: tab === k ? 'var(--ivory)' : 'transparent',
                  boxShadow:
                    tab === k ? '0 0 0 1px var(--border-strong), 0 1px 2px rgba(0,0,0,0.04)' : 'none',
                }}
              >
                {t}
                <span
                  style={{
                    font: '600 10px var(--font-mono)',
                    color: tab === k ? 'var(--terracotta-strong)' : 'var(--warm-silver)',
                  }}
                >
                  {n}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* list */}
        <div style={{ flex: 1, overflow: 'auto', padding: '2px 10px 8px', minHeight: 0 }}>
          {tab === 'convo'
            ? convos.length === 0
              ? (
                <div
                  style={{
                    padding: '32px 16px',
                    textAlign: 'center',
                    font: '400 12px/1.6 var(--font-sans)',
                    color: 'var(--stone)',
                  }}
                >
                  还没有深度优化对话。点下方「开始新对话」,或在打分缺口点「去深度优化这段」就会开一段。
                </div>
              )
              : convos.map((c) => {
                const on = pickConvo === c.id;
                const confirming = confirmingDelete === c.id;
                return (
                  <div
                    key={c.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                      padding: '2px 2px 2px 0',
                      borderRadius: 11,
                      marginBottom: 2,
                      background: on ? 'var(--terracotta-wash)' : 'transparent',
                      boxShadow: on ? '0 0 0 1px #eccfb6' : 'none',
                    }}
                  >
                    <button
                      onClick={() => {
                        setPickConvo(c.id);
                        onOpenConvo?.(c.id);
                      }}
                      style={{
                        flex: 1,
                        minWidth: 0,
                        textAlign: 'left',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 11,
                        padding: '10px 11px',
                        borderRadius: 11,
                        cursor: 'pointer',
                        border: 'none',
                        background: 'transparent',
                      }}
                    >
                      <span
                        style={{
                          flex: 'none',
                          width: 30,
                          height: 30,
                          borderRadius: 9,
                          display: 'grid',
                          placeItems: 'center',
                          color: on ? 'var(--terracotta-strong)' : 'var(--stone)',
                          background: on ? 'var(--ivory)' : 'var(--library-rail)',
                          boxShadow: on ? '0 0 0 1px #eccfb6' : '0 0 0 1px var(--border-warm)',
                        }}
                      >
                        <MessageSquare size={15} />
                      </span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div
                          style={{
                            font: `${on ? 600 : 500} 13px var(--font-sans)`,
                            color: on ? 'var(--ink)' : 'var(--ink-soft)',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          {c.title}
                        </div>
                        <div style={{ font: '400 11px var(--font-mono)', color: 'var(--stone)', marginTop: 2 }}>
                          {c.date}
                          {c.active ? (
                            <span style={{ fontFamily: 'var(--font-sans)', color: 'var(--terracotta-strong)' }}>
                              {' · 当前会话'}
                            </span>
                          ) : c.open ? (
                            <span style={{ fontFamily: 'var(--font-sans)', color: 'var(--olive)' }}>{' · 已在标签'}</span>
                          ) : null}
                        </div>
                      </div>
                    </button>
                    {confirming ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 'none', paddingRight: 6 }}>
                        <button
                          onClick={() => {
                            onDeleteConvo?.(c.id);
                            setConfirmingDelete(null);
                          }}
                          className="hf-btn primary sm"
                          style={{ height: 26, padding: '0 9px', fontSize: 11 }}
                        >
                          删
                        </button>
                        <button
                          onClick={() => setConfirmingDelete(null)}
                          className="hf-btn ghost sm"
                          style={{ height: 26, padding: '0 9px', fontSize: 11 }}
                        >
                          取消
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setConfirmingDelete(c.id)}
                        title="删除这段对话"
                        aria-label="删除对话"
                        style={{
                          flex: 'none',
                          width: 28,
                          height: 28,
                          marginRight: 6,
                          borderRadius: 8,
                          display: 'grid',
                          placeItems: 'center',
                          cursor: 'pointer',
                          border: 'none',
                          color: 'var(--stone)',
                          background: 'transparent',
                        }}
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                );
              })
            : reports.length === 0
              ? (
                <div
                  style={{
                    padding: '32px 16px',
                    textAlign: 'center',
                    font: '400 12px/1.6 var(--font-sans)',
                    color: 'var(--stone)',
                  }}
                >
                  还没有打分存档。在「简历打分」里点重新打分,这一版的报告会自动归档到这里。
                </div>
              )
              : reports.map((r) => {
                  const on = pickReport === r.vid;
                  const tone = scoreTone(r.score);
                  return (
                    <button
                      key={r.vid}
                      onClick={() => {
                        setPickReport(r.vid);
                        onOpenReport?.(r.vid);
                      }}
                      style={{
                        width: '100%',
                        textAlign: 'left',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 11,
                        padding: '10px 11px',
                        borderRadius: 12,
                        cursor: 'pointer',
                        marginBottom: 4,
                        border: 'none',
                        background: on ? 'var(--terracotta-wash)' : 'var(--parchment)',
                        boxShadow: on ? '0 0 0 1px #eccfb6' : '0 0 0 1px var(--border-warm)',
                        transition: 'background .12s, box-shadow .12s',
                      }}
                    >
                      {/* score tile */}
                      <span
                        style={{
                          flex: 'none',
                          width: 42,
                          height: 42,
                          borderRadius: 11,
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          justifyContent: 'center',
                          background: tone.bg,
                          boxShadow: `0 0 0 1px ${tone.ring}`,
                        }}
                      >
                        <span style={{ font: '500 18px/1 var(--font-mono)', color: tone.fg }}>{r.score}</span>
                      </span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div
                          style={{
                            font: '600 13px var(--font-sans)',
                            color: 'var(--ink)',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          {r.track}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 3 }}>
                          <span style={{ font: '400 11px var(--font-mono)', color: 'var(--stone)' }}>{r.date}</span>
                          {r.current ? (
                            <span className="hf-pill terra" style={{ height: 18, fontSize: 9.5, padding: '0 7px' }}>
                              当前
                            </span>
                          ) : null}
                          {r.potential && (
                            <span style={{ font: '400 10.5px var(--font-mono)', color: 'var(--warm-silver)' }}>
                              潜力 {r.potential}
                            </span>
                          )}
                        </div>
                      </div>
                      <span
                        style={{
                          color: on ? 'var(--terracotta-strong)' : 'var(--warm-silver)',
                          display: 'inline-flex',
                          flex: 'none',
                        }}
                      >
                        <ArrowRight size={14} />
                      </span>
                    </button>
                  );
                })}
        </div>

        {/* footer */}
        <div
          style={{
            flex: 'none',
            borderTop: '1px solid var(--border-cream)',
            padding: '10px 12px',
            display: 'flex',
            alignItems: 'center',
            gap: 9,
          }}
        >
          {tab === 'convo' ? (
            <>
              <button
                className="hf-btn primary sm"
                style={{ flex: 1, gap: 6 }}
                onClick={() => {
                  onClose();
                  onNew?.();
                }}
              >
                <Plus size={13} /> 开始新对话
              </button>
              <span style={{ font: '400 11px var(--font-sans)', color: 'var(--stone)', flex: 'none' }}>
                同一画像延续
              </span>
            </>
          ) : (
            <>
              <span style={{ color: 'var(--stone)', display: 'inline-flex', flex: 'none' }}>
                <FileText size={13} />
              </span>
              <span style={{ font: '400 11px/1.4 var(--font-sans)', color: 'var(--stone)', flex: 1 }}>
                每次打分自动存档 · 点开回看那一版报告
              </span>
              <TrendingUp size={12} style={{ color: 'var(--warm-silver)', flex: 'none' }} />
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
