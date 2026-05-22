'use client';

import { Sparkles } from 'lucide-react';
import type { ReactNode } from 'react';

/* ─── Top brand-bar (used by both Device Check and Interviewer pages) ──────── */

export function TopBar({
  crumb,
  meta,
  className = '',
}: {
  crumb: ReactNode;
  meta?: ReactNode;
  className?: string;
}) {
  return (
    <header
      className={`sticky top-0 z-10 flex items-center gap-[14px] border-b border-[var(--border)] px-[28px] py-[16px] ${className}`}
      style={{ background: 'rgba(245,244,237,0.85)', backdropFilter: 'blur(10px)' }}
    >
      <span
        className="inline-flex items-center text-[19px] tracking-[-0.02em] text-[var(--ink)]"
        style={{ fontFamily: 'var(--font-serif)', fontWeight: 500 }}
      >
        <span
          className="mr-[10px] inline-block h-[9px] w-[9px] rounded-full"
          style={{ background: 'var(--terracotta)' }}
        />
        JobRadar
      </span>
      <span
        className="ml-1 border-l border-[var(--border-strong)] pl-[14px] text-[12px] text-[var(--stone)]"
      >
        {crumb}
      </span>
      <span className="flex-1" />
      {meta && (
        <span className="flex items-center gap-[18px] text-[12px] text-[var(--olive)]">{meta}</span>
      )}
    </header>
  );
}

/* ─── Pulsing terracotta dot (used in TopBar meta + status indicators) ─────── */

export function StatusDot({
  color = 'emerald',
  pulse = false,
}: {
  color?: 'emerald' | 'terracotta' | 'stone';
  pulse?: boolean;
}) {
  const bg =
    color === 'emerald'
      ? 'var(--emerald)'
      : color === 'terracotta'
        ? 'var(--terracotta)'
        : 'var(--stone)';
  return (
    <span
      className="inline-block h-[6px] w-[6px] rounded-full"
      style={{
        background: bg,
        boxShadow: pulse ? `0 0 0 3px ${color === 'terracotta' ? 'var(--terracotta-ring)' : 'transparent'}` : undefined,
        animation: pulse ? 'itv-pulse-dot 1.2s ease-in-out infinite' : undefined,
      }}
    />
  );
}

/* ─── Pill (small rounded label, e.g. "已连接 · 48 kHz") ───────────────────── */

export function Pill({ children }: { children: ReactNode }) {
  return (
    <span
      className="inline-flex items-center gap-[7px] rounded-full border border-[var(--border)] px-[12px] py-[6px] text-[12px] text-[var(--olive)]"
      style={{ background: 'var(--library-rail)' }}
    >
      {children}
    </span>
  );
}

/* ─── Eyebrow ("MOCK INTERVIEW · PRE-FLIGHT") ─────────────────────────────── */

export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center gap-[10px] text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--olive)]">
      <span className="block h-px w-[22px] flex-none" style={{ background: 'var(--terracotta)' }} />
      {children}
    </div>
  );
}

/* ─── AI orb — pulsing terracotta sphere with three concentric rings ───────── */

export function AIOrb({ size = 220 }: { size?: number }) {
  // The original mock-interview orb was designed at 220px with fixed
  // insets. Workspace coach reuses it at 56-140px, so keep the 220px look
  // as the reference and scale every ring proportionally.
  const outerInset = size * (24 / 220);
  const innerRingInset = size * (48 / 220);
  const coreInset = size * (30 / 220);
  const sparkleSize = Math.max(12, size * (38 / 220));

  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <div
        className="absolute inset-0 rounded-full border"
        style={{ borderColor: 'var(--border-strong)' }}
      />
      <div
        className="absolute rounded-full border"
        style={{ inset: outerInset, borderColor: 'var(--border)' }}
      />
      <div
        className="absolute rounded-full border"
        style={{ inset: innerRingInset, borderColor: 'var(--border)' }}
      />
      <div
        className="absolute grid place-items-center rounded-full"
        style={{
          inset: coreInset,
          background:
            'radial-gradient(circle at 35% 30%, #e38066 0%, var(--terracotta) 45%, var(--terracotta-strong) 100%)',
          boxShadow: '0 20px 50px rgba(201,100,66,0.28)',
          animation: 'itv-orb 2.4s ease-in-out infinite',
        }}
      >
        <Sparkles size={sparkleSize} strokeWidth={1.4} color="#faf9f5" style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.2))' }} />
      </div>
    </div>
  );
}

/* ─── Listening waveform (green bars) ─────────────────────────────────────── */

export function ListenWave({ active }: { active: boolean }) {
  if (!active) return null;
  return (
    <div className="mt-1 inline-flex h-[36px] items-center gap-[3px]">
      {Array.from({ length: 7 }).map((_, i) => (
        <span
          key={i}
          className="rounded-[2px]"
          style={{
            width: 3,
            background: 'var(--emerald)',
            animation: 'itv-listen-bar 1s ease-in-out infinite',
            animationDelay: `${i * 0.1}s`,
          }}
        />
      ))}
    </div>
  );
}
