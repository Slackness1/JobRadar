/* global React */
// Shared hi-fi primitives for JobRadar

const { useState, useEffect, useRef, useMemo } = React;

// ---------- Logo ----------
const HFLogo = ({ size = 'md', dark = false }) => (
  <div className="hf-logo" style={dark ? { color: '#faf9f5' } : {}}>
    <span className="hf-logo__word" style={{
      color: dark ? '#faf9f5' : undefined,
      fontSize: size === 'lg' ? 22 : size === 'sm' ? 15 : 18,
    }}>JobRadar</span>
  </div>
);

// ---------- Button ----------
const HFBtn = ({ variant='primary', size='md', children, onClick, icon, iconRight, style, disabled, ...rest }) => (
  <button className={`hf-btn ${variant} ${size==='md'?'':size}`} onClick={onClick} disabled={disabled} style={{ opacity: disabled ? 0.5 : 1, ...style }} {...rest}>
    {icon && <span style={{ display:'inline-flex' }}>{icon}</span>}
    <span>{children}</span>
    {iconRight && <span style={{ display:'inline-flex' }}>{iconRight}</span>}
  </button>
);

// ---------- Pill ----------
const HFPill = ({ children, tone, style, onClick }) => (
  <span className={`hf-pill ${tone||''}`} style={style} onClick={onClick}>{children}</span>
);

// ---------- Icon set (simple inline) ----------
const I = {
  arrowUp: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M12 19V5M5 12l7-7 7 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  arrowRight: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M5 12h14M13 5l7 7-7 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  send: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M5 12l15-7-7 15-2.5-6L5 12z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round"/></svg>,
  upload: (s=16)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M12 15V4M7 9l5-5 5 5M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  file: (s=16)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/><path d="M14 2v6h6" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/></svg>,
  check: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M4 12l5 5L20 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  sparkle: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>,
  radar: (s=16)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.5"/><circle cx="12" cy="12" r="5" stroke="currentColor" strokeWidth="1.5"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/></svg>,
  menu: (s=16)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/></svg>,
  plus: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg>,
  close: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/></svg>,
  search: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="1.6"/><path d="M20 20l-3.5-3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>,
  chevron: (s=12)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  book: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M4 4h9a4 4 0 014 4v13H8a4 4 0 01-4-4V4zm16 0v13" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/></svg>,
  bolt: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" fill="none"/></svg>,
  pin: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M12 22s7-7.5 7-13a7 7 0 10-14 0c0 5.5 7 13 7 13z" stroke="currentColor" strokeWidth="1.6"/><circle cx="12" cy="9" r="2.5" stroke="currentColor" strokeWidth="1.6"/></svg>,
  edit: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M4 20h4L20 8l-4-4L4 16v4zM14 6l4 4" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/></svg>,
  target: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.5"/><circle cx="12" cy="12" r="5" stroke="currentColor" strokeWidth="1.5"/><circle cx="12" cy="12" r="1.4" fill="currentColor"/></svg>,
  quote: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M7 7h3l-1.5 4H7V7zm7 0h3l-1.5 4H14V7z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/><path d="M7 17v-3M14 17v-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>,
  yen: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M6 5l6 8 6-8M8 12h8M8 16h8M12 13v6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  clipboard: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><rect x="5" y="5" width="14" height="16" rx="2" stroke="currentColor" strokeWidth="1.6"/><rect x="9" y="3" width="6" height="4" rx="1" stroke="currentColor" strokeWidth="1.6"/><path d="M8 11h8M8 15h6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>,
  history: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M3 12a9 9 0 109-9 9 9 0 00-6.4 2.6L3 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/><path d="M3 4v4h4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/><path d="M12 8v5l3 2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>,
  shield: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/><path d="M9 12l2 2 4-4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  save: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M5 5h11l3 3v11a1 1 0 01-1 1H5a1 1 0 01-1-1V6a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/><rect x="8" y="13" width="8" height="6" stroke="currentColor" strokeWidth="1.6"/><rect x="8" y="5" width="6" height="4" stroke="currentColor" strokeWidth="1.6"/></svg>,
  download: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M12 4v12M7 11l5 5 5-5M4 20h16" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  refresh: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M21 12a9 9 0 11-3.5-7.1L21 8m0-5v5h-5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  bell: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M6 19h12M9 19a3 3 0 006 0M12 4a6 6 0 016 6c0 5 2 6 2 6H4s2-1 2-6a6 6 0 016-6zM12 2v2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  briefcase: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><rect x="3" y="7" width="18" height="13" rx="2" stroke="currentColor" strokeWidth="1.6"/><path d="M9 7V5a2 2 0 012-2h2a2 2 0 012 2v2M3 13h18" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>,
  barChart: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M4 20V10M10 20V4M16 20v-8M22 20H2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>,
  trending: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M3 17l6-6 4 4 8-9M14 6h7v7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  microscope: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M6 21h12M9 21v-3M9 18a3 3 0 100-6 3 3 0 000 6zM9 12V6a2 2 0 012-2h2l3 3-3 3M16 9v2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  landmark: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M3 9l9-6 9 6M5 9v11h14V9M9 20v-7M15 20v-7M3 21h18" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  scale: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><path d="M12 3v18M3 8h18M7 8l-3 6a3 3 0 006 0L7 8zM17 8l-3 6a3 3 0 006 0L17 8z" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  cpu: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><rect x="6" y="6" width="12" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.6"/><rect x="9" y="9" width="6" height="6" stroke="currentColor" strokeWidth="1.6"/><path d="M10 2v3M14 2v3M10 19v3M14 19v3M2 10h3M2 14h3M19 10h3M19 14h3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>,
  users: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><circle cx="9" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.6"/><path d="M2 21a7 7 0 0114 0M16 5a3 3 0 010 6M21 21a6 6 0 00-4-5.6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>,
  barrel: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><ellipse cx="12" cy="5" rx="7" ry="2" stroke="currentColor" strokeWidth="1.6"/><path d="M5 5v14a7 2 0 0014 0V5M5 12a7 2 0 0014 0" stroke="currentColor" strokeWidth="1.6"/></svg>,
  user: (s=14)=> <svg width={s} height={s} viewBox="0 0 24 24" fill="none"><circle cx="12" cy="8" r="4" stroke="currentColor" strokeWidth="1.6"/><path d="M4 21a8 8 0 0116 0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>,
};

// ---------- CountUp ----------
function useCountUp(target, duration=1400, start=true) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!start) return;
    let raf; const t0 = performance.now();
    const tick = (t) => {
      const p = Math.min(1, (t - t0) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setV(Math.round(target * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration, start]);
  return v;
}

// ---------- Ticker ----------
const HFTicker = ({ items }) => (
  <div style={{ overflow: 'hidden', maskImage: 'linear-gradient(90deg, transparent 0, #000 8%, #000 92%, transparent 100%)' }}>
    <div className="hf-ticker">
      {[...items, ...items].map((it, i) => (
        <span key={i} style={{ display: 'inline-flex', alignItems: 'baseline', gap: 8, fontSize: 13.5, color: 'var(--olive)' }}>
          <strong style={{ color: 'var(--terracotta)', fontWeight: 600, fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase' }}>{it.track}</strong>
          <span style={{ color: 'var(--ink-soft)' }}>{it.company}</span>
          <span style={{ color: 'var(--stone)' }}>· {it.title}</span>
          <span style={{ color: 'var(--stone)' }}>· {it.location}</span>
        </span>
      ))}
    </div>
  </div>
);

// ---------- Top nav ----------
const HFTopNav = ({ onStart }) => (
  <div style={{ display: 'flex', alignItems: 'center', padding: '22px 56px', justifyContent: 'space-between' }}>
    <HFLogo />
    <div style={{ display: 'flex', alignItems: 'center', gap: 28, fontSize: 14.5 }}>
      <a style={{ color: 'var(--ink-soft)', textDecoration: 'none' }}>产品</a>
      <a style={{ color: 'var(--ink-soft)', textDecoration: 'none' }}>覆盖范围</a>
      <a style={{ color: 'var(--ink-soft)', textDecoration: 'none' }}>工作方式</a>
      <a style={{ color: 'var(--ink-soft)', textDecoration: 'none' }}>关于</a>
    </div>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <HFBtn variant="link">登录</HFBtn>
      <HFBtn variant="primary" onClick={onStart} iconRight={I.arrowRight(14)}>上传简历</HFBtn>
    </div>
  </div>
);

Object.assign(window, { HFLogo, HFBtn, HFPill, HFTicker, HFTopNav, I, useCountUp });
