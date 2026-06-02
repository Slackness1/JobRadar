'use client';

/**
 * CoachThinkingIndicator — 2026-05-21 v5.
 *
 * 用户原话:"我不要所谓的流光特效了 我就要最简单的那个呼吸特效就可以了
 * 就是头像就是那个赤陶球 (就是在模拟面试中的那个 你就拿过来做一模一样的)
 * 然后思考就是在呼吸 下面显示 ai coach 正在思考 并附上思考时间"
 *
 * 实现 = AIOrb (interview/primitives.tsx 原件) + 标题 + 计时。
 * 没有 border-beam, 没有 sub hint, 没有 spinner 字符。
 *
 * 时间格式 (用户指定):
 *   <60s   → `12.4s`
 *   ≥60s   → `3m 4s` (整数分 + 整数秒)
 */

import { useEffect, useRef, useState } from 'react';
import { AIOrb } from '@/components/interview/primitives';

export type CoachThinkingPhase =
  | 'parsing'       // 简历刚上传, AI 在抽取 profile
  | 'starting'      // postPlanStart in flight
  | 'turning'       // a chat turn AI 反问
  | 'finalizing'    // draft 生成
  | 'archiving';    // 入档

/** 解析阶段的循环提示词 — 让"深读简历"的等待有过程感(后端是一次 LLM 调用,
 *  这些是前端循环展示的概念阶段)。模块级常量,身份稳定,作 cyclingLabels 传入。 */
export const PARSE_PHASE_LABELS = [
  '正在逐条精读你的简历…',
  '识别教育与实习经历…',
  '抽取技能与工具栈…',
  '推断目标赛道与岗位画像…',
];

export interface CoachThinkingIndicatorProps {
  active: boolean;
  /** 只用来决定 active=false 之后多久 hide, 不再影响视觉。 */
  phase?: CoachThinkingPhase;
  /** active=false 后多久 hide, 防止一闪。默认 2500ms — 800ms 太短, 用户
   *  反复抱怨 "一闪而过", 2.5s 是经验得来的视觉残留下限。 */
  minVisibleMs?: number;
  /** orb 尺寸, 默认 132,沿用模拟面试官赤陶呼吸球的比例。 */
  orbSize?: number;
  /** 自定义标题, 默认 "AI coach 正在思考"。 */
  label?: string;
  /** 循环展示的阶段提示词(每 ~2.2s 切换)。传了就覆盖 label,做"看得见的思考"。
   *  注意: 传模块级常量数组(身份稳定),别在 render 里现造,否则计时器每帧重置。 */
  cyclingLabels?: string[];
}

function formatElapsed(seconds: number): string {
  const wholeSeconds = Math.max(0, Math.floor(seconds));
  if (seconds < 60) {
    return `${wholeSeconds}s`;
  }
  const m = Math.floor(wholeSeconds / 60);
  const s = wholeSeconds - m * 60;
  return `${m}m ${s}s`;
}

export function CoachThinkingIndicator({
  active,
  minVisibleMs = 2500,
  orbSize = 132,
  label = 'AI coach 正在思考',
  cyclingLabels,
}: CoachThinkingIndicatorProps) {
  const [shown, setShown] = useState(active);
  const startedAtRef = useRef<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [labelIdx, setLabelIdx] = useState(0);

  useEffect(() => {
    if (active) {
      if (startedAtRef.current == null) startedAtRef.current = Date.now();
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setShown(true);
      return;
    }
    const t = window.setTimeout(() => {
      setShown(false);
      startedAtRef.current = null;
    }, minVisibleMs);
    return () => window.clearTimeout(t);
  }, [active, minVisibleMs]);

  useEffect(() => {
    if (!shown) return;
    const interval = window.setInterval(() => {
      if (startedAtRef.current == null) return;
      setElapsed((Date.now() - startedAtRef.current) / 1000);
    }, 250);
    return () => window.clearInterval(interval);
  }, [shown]);

  useEffect(() => {
    if (!shown || !cyclingLabels || cyclingLabels.length < 2) return;
    const id = window.setInterval(() => {
      setLabelIdx((i) => (i + 1) % cyclingLabels.length);
    }, 2200);
    return () => window.clearInterval(id);
  }, [shown, cyclingLabels]);

  if (!shown) return null;

  const displayLabel =
    cyclingLabels && cyclingLabels.length > 0
      ? cyclingLabels[labelIdx % cyclingLabels.length]
      : label;

  return (
    <div
      className="workspace-hifi__coach-thinking"
      role="status"
      aria-live="polite"
      style={{
        // AIOrb 用了 var(--terracotta) / var(--border) 等 token, workspace
        // 主题没定义, 这里就地注入, 保证 orb 在哪都能渲染。
        ['--terracotta' as string]: '#c96442',
        ['--terracotta-strong' as string]: '#a14e30',
        ['--border' as string]: '#e8e6dc',
        ['--border-strong' as string]: '#d3d0c2',
        ['--olive' as string]: '#6b6757',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 14,
        padding: '20px 16px',
      }}
    >
      <AIOrb size={orbSize} />
      <div
        style={{
          textAlign: 'center',
          fontSize: 14,
          color: '#3d3d3a',
          fontWeight: 500,
        }}
      >
        {displayLabel}
      </div>
      <div
        aria-label={`已思考 ${formatElapsed(elapsed)}`}
        style={{
          fontFamily: 'var(--font-mono, ui-monospace, "SF Mono", monospace)',
          fontSize: 12,
          color: '#6b6757',
          letterSpacing: '0.02em',
        }}
      >
        已思考 {formatElapsed(elapsed)}
      </div>
    </div>
  );
}
