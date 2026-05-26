'use client';

import { useEffect, useState, type CSSProperties, type ReactNode } from 'react';

// ── Logo ─────────────────────────────────────────────────────────────────────

interface HFLogoProps {
  size?: 'sm' | 'md' | 'lg';
  dark?: boolean;
  label?: string;
}

export function HFLogoMark({ size = 26, dark = false }: { size?: number; dark?: boolean }) {
  return (
    <span
      className="hf-logo__mark"
      style={{
        width: size,
        height: size,
        background: dark ? '#f5f4ed' : undefined,
      }}
      aria-hidden
    />
  );
}

export function HFLogo({ size = 'md', dark = false, label = 'JobRadar' }: HFLogoProps) {
  const markPx = size === 'lg' ? 32 : size === 'sm' ? 22 : 26;
  const wordPx = size === 'lg' ? 22 : size === 'sm' ? 15 : 18;
  return (
    <div className="hf-logo">
      <HFLogoMark size={markPx} dark={dark} />
      <span
        className="hf-logo__word"
        style={{
          color: dark ? '#faf9f5' : undefined,
          fontSize: wordPx,
        }}
      >
        {label}
      </span>
    </div>
  );
}

export function HFRadarPulse({ size = 24, color = '#c96442' }: { size?: number; color?: string }) {
  return (
    <svg
      className="hf-radar-pulse"
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden
    >
      <circle cx="16" cy="16" r="13" stroke={color} strokeWidth="1.4" opacity="0.3" />
      <circle cx="16" cy="16" r="8" stroke={color} strokeWidth="1.4" opacity="0.55" />
      <circle className="hf-logo__ping hf-logo__ping--a" cx="16" cy="16" r="6" stroke={color} strokeWidth="1.6" />
      <circle className="hf-logo__ping hf-logo__ping--b" cx="16" cy="16" r="6" stroke={color} strokeWidth="1.6" />
      <line className="hf-logo__sweep" x1="16" y1="16" x2="26" y2="6" stroke={color} strokeWidth="1.6" strokeLinecap="round" opacity="0.85" />
      <circle className="hf-logo__core" cx="16" cy="16" r="2.6" fill={color} />
    </svg>
  );
}

// ── Button ───────────────────────────────────────────────────────────────────

type HFBtnVariant = 'primary' | 'ghost' | 'sand' | 'dark' | 'link';
type HFBtnSize = 'sm' | 'md' | 'lg';

interface HFBtnProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: HFBtnVariant;
  size?: HFBtnSize;
  icon?: ReactNode;
  iconRight?: ReactNode;
}

export function HFBtn({
  variant = 'primary',
  size = 'md',
  children,
  icon,
  iconRight,
  style,
  disabled,
  className,
  ...rest
}: HFBtnProps) {
  const sizeClass = size === 'md' ? '' : size;
  return (
    <button
      className={`hf-btn ${variant} ${sizeClass} ${className ?? ''}`.trim()}
      disabled={disabled}
      style={{ opacity: disabled ? 0.5 : 1, ...style }}
      {...rest}
    >
      {icon ? <span style={{ display: 'inline-flex' }}>{icon}</span> : null}
      <span>{children}</span>
      {iconRight ? <span style={{ display: 'inline-flex' }}>{iconRight}</span> : null}
    </button>
  );
}

// ── Pill ─────────────────────────────────────────────────────────────────────

type HFPillTone = '' | 'amber' | 'terra' | 'emerald' | 'dark';

interface HFPillProps {
  children: ReactNode;
  tone?: HFPillTone;
  style?: CSSProperties;
  onClick?: () => void;
}

export function HFPill({ children, tone = '', style, onClick }: HFPillProps) {
  return (
    <span className={`hf-pill ${tone}`.trim()} style={style} onClick={onClick}>
      {children}
    </span>
  );
}

// ── Icons ────────────────────────────────────────────────────────────────────

export const I = {
  arrowUp: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M12 19V5M5 12l7-7 7 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  arrowRight: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M5 12h14M13 5l7 7-7 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  upload: (s = 16) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M12 15V4M7 9l5-5 5 5M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  file: (s = 16) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M14 2v6h6" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  ),
  check: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M4 12l5 5L20 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  sparkle: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  ),
  radar: (s = 16) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="12" cy="12" r="5" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="12" cy="12" r="1.5" fill="currentColor" />
    </svg>
  ),
  search: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="1.6" />
      <path d="M20 20l-3.5-3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  book: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M4 4h9a4 4 0 014 4v13H8a4 4 0 01-4-4V4zm16 0v13" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  ),
  close: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  ),
  plus: (s = 12) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  ),
  // ── design-bundle 2026-05-20 additions ───────────────────────────────────
  send: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M5 12l15-7-7 15-2.5-6L5 12z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
    </svg>
  ),
  menu: (s = 16) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  ),
  chevron: (s = 12) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  bolt: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" fill="none" />
    </svg>
  ),
  pin: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M12 22s7-7.5 7-13a7 7 0 10-14 0c0 5.5 7 13 7 13z" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="12" cy="9" r="2.5" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  ),
  edit: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M4 20h4L20 8l-4-4L4 16v4zM14 6l4 4" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  ),
  // ── P0a additions for Sessions page (2026-05-26) ─────────────────────────
  target: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="12" cy="12" r="5" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="12" cy="12" r="1.4" fill="currentColor" />
    </svg>
  ),
  history: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M3 12a9 9 0 109-9 9 9 0 00-6.4 2.6L3 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M3 4v4h4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 8v5l3 2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  shield: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M9 12l2 2 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  briefcase: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <rect x="3" y="7" width="18" height="13" rx="2" stroke="currentColor" strokeWidth="1.6" />
      <path d="M9 7V5a2 2 0 012-2h2a2 2 0 012 2v2M3 13h18" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  barChart: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M4 20V10M10 20V4M16 20v-8M22 20H2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  trending: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <path d="M3 17l6-6 4 4 8-9M14 6h7v7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  users: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <circle cx="9" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.6" />
      <path d="M2 21a7 7 0 0114 0M16 5a3 3 0 010 6M21 21a6 6 0 00-4-5.6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  user: (s = 14) => (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="8" r="4" stroke="currentColor" strokeWidth="1.6" />
      <path d="M4 21a8 8 0 0116 0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
} as const;

// ── useCountUp ───────────────────────────────────────────────────────────────

export function useCountUp(target: number, duration = 1400, start = true): number {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!start) return;
    let raf = 0;
    const t0 = performance.now();
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setValue(Math.round(target * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration, start]);
  return value;
}

// ── Live tick (count-up then keep slowly increasing) ─────────────────────────

export function useLiveCount(target: number, duration = 1400): number {
  const settled = useCountUp(target, duration, true);
  const [extra, setExtra] = useState(0);
  useEffect(() => {
    let timer: number | undefined;
    const schedule = () => {
      timer = window.setTimeout(() => {
        setExtra((v) => v + 1);
        schedule();
      }, 1200 + Math.floor(Math.random() * 1500));
    };
    const start = window.setTimeout(schedule, duration + 200);
    return () => {
      window.clearTimeout(start);
      if (timer) window.clearTimeout(timer);
    };
  }, [duration]);
  return settled + extra;
}

// ── Ticker ───────────────────────────────────────────────────────────────────

interface FeaturedItem {
  company: string;
  title: string;
  location: string;
  track: string;
}

interface HFTickerProps {
  items: FeaturedItem[];
  paused?: boolean;
}

export function HFTicker({ items, paused = false }: HFTickerProps) {
  return (
    <div
      style={{
        overflow: 'hidden',
        maskImage: 'linear-gradient(90deg, transparent 0, #000 8%, #000 92%, transparent 100%)',
        WebkitMaskImage: 'linear-gradient(90deg, transparent 0, #000 8%, #000 92%, transparent 100%)',
        flex: 1,
      }}
    >
      <div className="hf-ticker" style={{ animationPlayState: paused ? 'paused' : 'running' }}>
        {[...items, ...items].map((it, i) => (
          <span
            key={`${it.company}-${i}`}
            style={{ display: 'inline-flex', alignItems: 'baseline', gap: 8, fontSize: 13.5, color: 'var(--olive)' }}
          >
            <strong
              style={{
                color: 'var(--terracotta)',
                fontWeight: 600,
                fontSize: 11,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
              }}
            >
              {it.track}
            </strong>
            <span style={{ color: 'var(--ink-soft)' }}>{it.company}</span>
            <span style={{ color: 'var(--stone)' }}>· {it.title}</span>
            <span style={{ color: 'var(--stone)' }}>· {it.location}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
