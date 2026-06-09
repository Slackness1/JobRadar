'use client';

/**
 * DeepThinkCard — 统一对话 Hub 的「深度思考」卡(两段式).
 *
 * 取代旧的 border-beam SkillRunCard。两段式思考,单一动画:
 *   1. 我的理解  (确认赛道 + 记忆 pill, 先说清我懂你要什么, ~1.6s)
 *   2. 思考过程  (4 节点连接线轨迹逐个点亮, 每步可展开 input/output)
 *   3. 自动折叠  (done 时把思考过程收成一行, 点开可看) → fire onComplete()
 *
 * 设计铁律(来自用户明确反馈):
 *   - 全卡只有「一个」思考动画 —— 顶部不放轻量气泡。
 *   - 不用 border-beam(共享 AI-thinking glow)。
 *   - 不用彩色小标 —— 图标统一单色描边, 唯一彩色是调色板里的 terracotta。
 *
 * 真实数据接缝(本任务只留口, 由 Task 5/6 灌数):
 *   - understandOverride: HubShell 注入真实赛道 / 记忆(merge 进 cfg.understand)。
 *   - outputOverride:     节点序号 → 真实计数 output(done 态优先用真实计数)。
 *   - 二者皆 undefined 时回落 DEEP_META 静态文案。
 *
 * Token: 全部取自 `.hf`(HubShell 已 className="hf")。
 *   原型用过 `var(--border)` / `var(--muted)` —— 这两个名在 `.hf` 不存在,
 *   分别替换为 `--border-warm`(#e8e6dc, 同 globals.css 的 --border)
 *   与 `--olive`(#5e5d59, 同 globals.css 的 --muted)。
 */

import { useEffect, useRef, useState } from 'react';
import {
  DEEP_META,
  DTIcon,
  type DeepMeta,
  type DeepNode,
  type DeepUnderstand,
} from './deep-think-meta';

// ── timing (ms) ──────────────────────────────────────────────────────────────
const UNDERSTAND_MS = 1600; // 我的理解 停留时长
const NODE_STEP_MS = 760; // 每个思考节点点亮间隔
const DONE_TAIL_MS = 320; // 最后一个节点完成 → done 的尾巴
const TYPE_TICK_MS = 22; // 打字机心跳
const TYPE_STEP = 2; // 每跳推进字符数

// ── small inline primitives (原型用 window.NLChat.{Avatar,Spinner}) ──────────

/** terracotta 实心圆 + sparkle glyph(对齐 RecommendAvatar)。纯展示。 */
function DTAvatar({ size = 28 }: { size?: number }) {
  return (
    <div
      aria-hidden="true"
      style={{
        flex: 'none',
        width: size,
        height: size,
        borderRadius: 999,
        display: 'grid',
        placeItems: 'center',
        background: 'var(--terracotta)',
        color: 'var(--ivory)',
        boxShadow: '0 0 0 1px var(--terracotta-strong)',
      }}
    >
      <svg
        width={size * 0.52}
        height={size * 0.52}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1" />
        <circle cx="12" cy="12" r="3.2" fill="currentColor" stroke="none" />
      </svg>
    </div>
  );
}

/** terracotta 旋转 spinner(复用 .hf-spin 关键帧)。单一思考动画的载体。 */
function DTSpinner({ size = 14 }: { size?: number }) {
  return <span className="hf-spin" style={{ width: size, height: size }} aria-hidden="true" />;
}

/** 圆形 check 标(done 态)。emerald 仅作语义"完成",非彩色小标。 */
function DTCheck({ size = 16, on }: { size?: number; on: boolean }) {
  return (
    <span
      style={{
        width: size,
        height: size,
        borderRadius: 999,
        flex: 'none',
        display: 'inline-grid',
        placeItems: 'center',
        background: on ? 'var(--emerald-soft)' : 'transparent',
        boxShadow: on ? '0 0 0 1px #c1ddc0' : '0 0 0 1.5px var(--ring-warm)',
        transition: 'background .25s ease-out, box-shadow .25s ease-out',
      }}
    >
      {on && (
        <svg
          width={size * 0.6}
          height={size * 0.6}
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--emerald)"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M20 6 9 17l-5-5" />
        </svg>
      )}
    </span>
  );
}

/** 折叠箭头。 */
function DTChevron({ open, size = 12 }: { open: boolean; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="var(--stone)"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{
        transition: 'transform .2s ease-out',
        transform: open ? 'rotate(180deg)' : 'none',
        flex: 'none',
      }}
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

/** 进场上浮(对齐原型 DTEnter)。用 .hf-slide CSS 关键帧, 避免 effect 内 setState。 */
function DTEnter({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <div className="hf-slide" style={style}>
      {children}
    </div>
  );
}

type NodeStatus = 'pending' | 'running' | 'done';

// ── tool input/output body ───────────────────────────────────────────────────
function DTToolBody({
  node,
  status,
  outputText,
}: {
  node: DeepNode;
  status: NodeStatus;
  outputText: string;
}) {
  const done = status === 'done';
  return (
    <div
      style={{
        marginTop: 9,
        borderRadius: 12,
        background: 'var(--library-rail)',
        boxShadow: '0 0 0 1px var(--border-cream)',
        overflow: 'hidden',
      }}
    >
      <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border-cream)' }}>
        <div
          style={{
            font: '600 9.5px var(--font-sans)',
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            color: 'var(--stone)',
            marginBottom: 5,
          }}
        >
          Input
        </div>
        <code
          style={{
            font: '500 11.5px/1.7 var(--font-mono)',
            color: 'var(--ink-soft)',
            display: 'block',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {Object.entries(node.input).map(([k, v]) => (
            <span key={k}>
              <span style={{ color: 'var(--terracotta-strong)' }}>{k}</span>:{' '}
              {Array.isArray(v) ? `[${v.join(', ')}]` : String(v)}
              {'\n'}
            </span>
          ))}
        </code>
      </div>
      <div style={{ padding: '8px 12px' }}>
        <div
          style={{
            font: '600 9.5px var(--font-sans)',
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            color: 'var(--stone)',
            marginBottom: 5,
          }}
        >
          Output
        </div>
        {done ? (
          <div style={{ font: '500 12px var(--font-mono)', color: 'var(--ink)' }}>{outputText}</div>
        ) : (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 7,
              font: '500 12px var(--font-mono)',
              color: 'var(--stone)',
            }}
          >
            <DTSpinner /> 执行中…
          </div>
        )}
      </div>
    </div>
  );
}

// ── one chain-of-thought step ────────────────────────────────────────────────
function DTStep({
  node,
  status,
  last,
  outputText,
}: {
  node: DeepNode;
  status: NodeStatus;
  last: boolean;
  outputText: string;
}) {
  const [userOpen, setUserOpen] = useState<boolean | null>(null);
  const open = userOpen !== null ? userOpen : status === 'running';
  return (
    <DTEnter style={{ display: 'flex', gap: 12, position: 'relative' }}>
      {!last && (
        <div
          style={{
            position: 'absolute',
            left: 14,
            top: 30,
            bottom: -6,
            width: 2,
            background: status === 'done' ? 'var(--terracotta)' : 'var(--warm-sand)',
            transition: 'background .3s ease-out',
          }}
        />
      )}
      <div
        style={{
          flex: 'none',
          width: 29,
          height: 29,
          borderRadius: 999,
          display: 'grid',
          placeItems: 'center',
          background: 'var(--ivory)',
          boxShadow:
            status === 'done'
              ? '0 0 0 1.5px #c1ddc0'
              : status === 'running'
                ? '0 0 0 1.5px var(--terracotta)'
                : '0 0 0 1.5px var(--ring-warm)',
          zIndex: 1,
          transition: 'box-shadow .3s ease-out',
        }}
      >
        {status === 'done' ? (
          <svg
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="var(--emerald)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M20 6 9 17l-5-5" />
          </svg>
        ) : status === 'running' ? (
          <DTSpinner />
        ) : (
          <DTIcon name={node.icon} size={14} color="var(--stone)" />
        )}
      </div>
      <div style={{ flex: 1, paddingBottom: 16, minWidth: 0 }}>
        <button
          type="button"
          onClick={() => setUserOpen(!open)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            width: '100%',
            textAlign: 'left',
            background: 'none',
            border: 0,
            cursor: 'pointer',
            padding: 0,
          }}
        >
          <DTIcon name={node.icon} size={15} color="var(--ink-soft)" />
          <span
            style={{
              font: '500 13.5px var(--font-sans)',
              color: status === 'pending' ? 'var(--stone)' : 'var(--ink)',
            }}
          >
            {node.title}
          </span>
          <span
            style={{
              font: '500 10px var(--font-mono)',
              color: 'var(--stone)',
              background: 'var(--library-rail)',
              padding: '1px 6px',
              borderRadius: 999,
            }}
          >
            {node.tool}
          </span>
          {status === 'running' && (
            <span
              style={{ font: '400 11px var(--font-sans)', color: 'var(--coral)', whiteSpace: 'nowrap' }}
            >
              运行中…
            </span>
          )}
          <span style={{ marginLeft: 'auto', opacity: status === 'pending' ? 0.4 : 1 }}>
            <DTChevron open={open} />
          </span>
        </button>
        {open && <DTToolBody node={node} status={status} outputText={outputText} />}
        {status === 'done' && (
          <DTEnter style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 9 }}>
            {node.chips.map((c) => (
              <span key={c} className="hf-pill" style={{ height: 24, fontSize: 11.5 }}>
                {c}
              </span>
            ))}
          </DTEnter>
        )}
      </div>
    </DTEnter>
  );
}

// ── props ────────────────────────────────────────────────────────────────────
export interface DeepThinkCardProps {
  module: 'feed' | 'skeleton' | 'resume' | 'interview';
  /** HubShell 注入真实赛道 / 记忆 —— merge 进 cfg.understand */
  understandOverride?: Partial<DeepUnderstand>;
  /** 节点序号 → 真实计数 output(done 态优先) */
  outputOverride?: Record<number, string>;
  onComplete: () => void;
}

type Phase = 'understand' | 'think' | 'done';

// ── the embeddable deep-think card ───────────────────────────────────────────
export default function DeepThinkCard({
  module,
  understandOverride,
  outputOverride,
  onComplete,
}: DeepThinkCardProps) {
  const base: DeepMeta = DEEP_META[module];
  // merge real understand overrides over the static base
  const u: DeepUnderstand = { ...base.understand, ...(understandOverride ?? {}) };
  const nodes: DeepNode[] = base.nodes;

  const [phase, setPhase] = useState<Phase>('understand'); // understand | think | done
  const [step, setStep] = useState(0); // active node index while thinking
  const [chars, setChars] = useState(0); // reasoning typewriter cursor
  const [thinkOpen, setThinkOpen] = useState<boolean | null>(null);
  const fired = useRef(false);

  // keep latest onComplete without re-running the timer effect
  const onCompleteRef = useRef(onComplete);
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  // understanding → think
  useEffect(() => {
    const t = setTimeout(() => setPhase('think'), UNDERSTAND_MS);
    return () => clearTimeout(t);
  }, []);

  // reasoning typewriter — only ticks during understanding.
  // Once phase leaves understand, displayedReasoning falls back to full text
  // (derived below), so no synchronous setState is needed here.
  useEffect(() => {
    if (phase !== 'understand') return;
    let i = 0;
    const id = setInterval(() => {
      i += TYPE_STEP;
      setChars(i);
      if (i >= u.reasoning.length) clearInterval(id);
    }, TYPE_TICK_MS);
    return () => clearInterval(id);
  }, [phase, u.reasoning]);

  // run the nodes one-by-one, then settle to done + fire onComplete once
  useEffect(() => {
    if (phase !== 'think') return;
    const timers = nodes.map((_, i) =>
      setTimeout(() => setStep(i + 1), NODE_STEP_MS * (i + 1)),
    );
    const end = setTimeout(
      () => {
        setPhase('done');
        if (!fired.current) {
          fired.current = true;
          onCompleteRef.current?.();
        }
      },
      NODE_STEP_MS * nodes.length + DONE_TAIL_MS,
    );
    return () => {
      timers.forEach(clearTimeout);
      clearTimeout(end);
    };
    // nodes is stable per module; phase drives the run
  }, [phase, nodes]);

  const understanding = phase === 'understand';
  const running = phase !== 'done';
  const thinkOpenEff = thinkOpen !== null ? thinkOpen : running; // auto-collapse on done
  const doneCount = phase === 'done' ? nodes.length : step;
  const nodeStatus = (i: number): NodeStatus =>
    i < step ? 'done' : i === step && phase === 'think' ? 'running' : 'pending';
  const outputFor = (i: number): string => outputOverride?.[i] ?? nodes[i].output;
  // typewriter while understanding; full text once we move past it
  const displayedReasoning = understanding ? u.reasoning.slice(0, chars) : u.reasoning;

  return (
    <div className="hf-slide" style={{ display: 'flex', gap: 9, alignItems: 'flex-start' }}>
      <DTAvatar />
      <div
        style={{
          flex: 1,
          minWidth: 0,
          maxWidth: 540,
          background: 'var(--ivory)',
          borderRadius: 16,
          borderTopLeftRadius: 5,
          boxShadow: '0 0 0 1px var(--border-warm)',
          overflow: 'hidden',
        }}
      >
        {/* 我的理解 */}
        <div
          style={{
            padding: '13px 15px',
            borderBottom: phase !== 'understand' ? '1px solid var(--border-cream)' : 'none',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 7 }}>
            {understanding ? <DTSpinner size={16} /> : <DTCheck size={16} on />}
            <span
              style={{
                font: '600 11px var(--font-sans)',
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: 'var(--terracotta-strong)',
              }}
            >
              我的理解
            </span>
          </div>
          <p style={{ font: '400 13.5px/1.6 var(--font-sans)', color: 'var(--ink)', margin: 0 }}>
            我理解你要的是 —— <b style={{ fontWeight: 600 }}>{u.headline}</b>
          </p>
          {(u.tracks.length > 0 || u.memory.length > 0) && (
            <div
              style={{
                display: 'flex',
                gap: 6,
                flexWrap: 'wrap',
                marginTop: 9,
                alignItems: 'center',
              }}
            >
              {u.tracks.map((c) => (
                <span key={c} className="hf-pill terra" style={{ height: 24, fontSize: 11.5 }}>
                  {c}
                </span>
              ))}
              {u.memory.length > 0 && (
                <span
                  style={{ width: 1, height: 16, background: 'var(--border-warm)', margin: '0 2px' }}
                />
              )}
              {u.memory.map((c) => (
                <span
                  key={c}
                  className="hf-pill"
                  style={{ height: 24, fontSize: 11, color: 'var(--olive)' }}
                >
                  {/* monochrome clock — 单色, 无彩色小标 */}
                  <svg
                    width="11"
                    height="11"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="var(--stone)"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M12 8v4l3 2" />
                    <circle cx="12" cy="12" r="9" />
                  </svg>
                  {c}
                </span>
              ))}
            </div>
          )}
          <p
            className={understanding ? 'hf-pulse' : ''}
            style={{
              font: '400 12.5px/1.7 var(--font-sans)',
              color: 'var(--olive)',
              whiteSpace: 'pre-wrap',
              margin: '11px 0 0',
              borderLeft: '2px solid var(--warm-sand)',
              paddingLeft: 12,
            }}
          >
            {displayedReasoning}
            {understanding && <span className="hf-caret" style={{ height: '0.9em' }} />}
          </p>
        </div>

        {/* 思考过程 — done 时自动折叠, 点击可重新展开 */}
        {phase !== 'understand' && (
          <div style={{ padding: '13px 15px' }}>
            <button
              type="button"
              onClick={() => setThinkOpen(!thinkOpenEff)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 9,
                width: '100%',
                textAlign: 'left',
                background: 'none',
                border: 0,
                cursor: 'pointer',
                padding: 0,
              }}
            >
              {phase === 'done' ? (
                <DTCheck size={15} on />
              ) : !thinkOpenEff ? (
                <DTSpinner />
              ) : (
                <span style={{ width: 13, flex: 'none' }} />
              )}
              <span
                style={{
                  font: '600 11px var(--font-sans)',
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  color: 'var(--stone)',
                }}
              >
                思考过程
              </span>
              <span style={{ font: '400 11px var(--font-mono)', color: 'var(--stone)' }}>
                {doneCount}/{nodes.length}
                {phase === 'done' ? ' · 已完成' : ''}
              </span>
              <span style={{ marginLeft: 'auto' }}>
                <DTChevron open={thinkOpenEff} />
              </span>
            </button>
            {thinkOpenEff && (
              <div style={{ paddingTop: 15 }}>
                {nodes.map((n, i) => (
                  <DTStep
                    key={n.tool}
                    node={n}
                    status={nodeStatus(i)}
                    last={i === nodes.length - 1}
                    outputText={outputFor(i)}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
