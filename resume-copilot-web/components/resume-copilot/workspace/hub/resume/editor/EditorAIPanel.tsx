'use client';

import type { JSX } from 'react';
import { Sparkles } from 'lucide-react';
import { EditorScoreReportThick } from './EditorScoreReportThick';
import { ChatThread } from './ChatThread';
import type { DeepOptimizeStartIn, ScoreSectionGap } from '../../../../api';

const TABS: [string, string][] = [
  ['score', '简历打分'],
  ['deep', '深度优化'],
  // 自由问后端接好前先藏(占位回声让用户一头雾水);ChatThread mode='free' 已接
  // /chat,下版本恢复 ['free', '自由问'] 即可。
];

export interface EditorAIPanelProps {
  sessionId: number;
  /** 当前深度优化播种(从打分缺口 CTA 构造)。null = 还没选段。 */
  seed: DeepOptimizeStartIn | null;
  setSeed: (s: DeepOptimizeStartIn | null) => void;
  /** 受控 tab。 */
  tab: string;
  setTab: (t: string) => void;
  /** 写回成功 → 父组件把 section 映射成 A4 lit。 */
  onWriteBack: (section: string) => void;
  /** 无真实 session 时走样例。 */
  mock?: boolean;
}

/** 简历编辑器右栏「AI 简历助手 v2」三能力壳:简历打分 / 深度优化 / 自由问。 */
export function EditorAIPanel({
  sessionId,
  seed,
  setSeed,
  tab,
  setTab,
  onWriteBack,
  mock = false,
}: EditorAIPanelProps): JSX.Element {
  // 打分缺口「去深度优化这段」→ 构造 seed(带真实目标赛道)→ 切到深度优化 tab(gap→deep 串联)。
  function handleOptimize(gap: ScoreSectionGap, targetTrack: string): void {
    setSeed({
      section: gap.section,
      label: gap.label,
      gaps: gap.gaps,
      detail: gap.detail,
      target_track: targetTrack,
    });
    setTab('deep');
  }

  return (
    <div
      style={{
        borderLeft: '1px solid var(--border-warm)',
        background: 'var(--ivory)',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
      }}
    >
      {/* 头部 */}
      <div
        style={{
          padding: '13px 16px',
          borderBottom: '1px solid var(--border-warm)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          flex: 'none',
        }}
      >
        <span
          style={{
            width: 28,
            height: 28,
            flex: 'none',
            borderRadius: 999,
            display: 'grid',
            placeItems: 'center',
            color: '#faf9f5',
            background:
              'radial-gradient(circle at 35% 30%, #e38066 0%, var(--terracotta) 45%, var(--terracotta-strong) 100%)',
            boxShadow: '0 4px 12px rgba(201,100,66,0.26)',
          }}
        >
          <Sparkles size={15} />
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ font: '600 13.5px var(--font-sans)', color: 'var(--ink)' }}>AI 简历助手 v2</div>
          <div style={{ font: '400 10.5px var(--font-sans)', color: 'var(--stone)' }}>
            诚实打分 · 反问取证 · 写回即刷新
          </div>
        </div>
      </div>

      {/* 三能力切换 */}
      <div
        style={{
          padding: '10px 14px',
          borderBottom: '1px solid var(--border-warm)',
          display: 'flex',
          gap: 6,
          flex: 'none',
        }}
      >
        {TABS.map(([k, t]) => {
          const on = tab === k;
          return (
            <button
              key={k}
              onClick={() => setTab(k)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                height: 30,
                padding: '0 12px',
                borderRadius: 999,
                cursor: 'pointer',
                font: `${on ? 600 : 500} 12px var(--font-sans)`,
                background: on ? 'var(--terracotta)' : 'var(--ivory)',
                color: on ? 'var(--ivory)' : 'var(--ink-soft)',
                boxShadow: on ? '0 0 0 1px var(--terracotta)' : '0 0 0 1px var(--border-warm)',
              }}
            >
              {t}
              {k === 'deep' && seed && !on && (
                <span style={{ width: 5, height: 5, borderRadius: 999, background: 'var(--terracotta)' }} />
              )}
            </button>
          );
        })}
      </div>

      {/* 三能力内容(用 display 切换以保留各自状态)。 */}
      <div style={{ flex: 1, minHeight: 0, display: tab === 'score' ? 'flex' : 'none', flexDirection: 'column' }}>
        <EditorScoreReportThick sessionId={sessionId} onOptimize={handleOptimize} mock={mock} />
      </div>
      <div style={{ flex: 1, minHeight: 0, display: tab === 'deep' ? 'flex' : 'none', flexDirection: 'column' }}>
        <ChatThread sessionId={sessionId} mode="deep" seed={seed} onWriteBack={onWriteBack} mock={mock} />
      </div>
      {/* 自由问内容随 tab 一起藏(TABS 注释见上)。 */}
    </div>
  );
}
