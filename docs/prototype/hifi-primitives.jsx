/* global React */
// Shared hi-fi primitives for JobRadar

const { useState, useEffect, useRef, useMemo } = React;

// ---------- Logo ----------
const HFLogo = ({ size = 'md', dark = false }) => (
  <div className="hf-logo" style={dark ? { color: '#faf9f5' } : {}}>
    <div className="hf-logo__mark" style={dark ? { background: '#faf9f5' } : {}} />
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
