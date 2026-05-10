/* global React, Easing, interpolate, clamp, useTime, useSprite */

// ── Shared utilities ──────────────────────────────────────────────────────

// Linear, no-ease, no bounce fade helper using progress
const fadeIn = (t, dur = 0.4) => clamp(t / dur, 0, 1);
const fadeOut = (localTime, duration, dur = 0.4) => {
  const start = duration - dur;
  if (localTime < start) return 1;
  return 1 - clamp((localTime - start) / dur, 0, 1);
};

// Fade in-hold-out wrapper (fills parent)
function FadeBox({ entryDur = 0.5, exitDur = 0.5, children, style }) {
  const { localTime, duration } = useSprite();
  const opacity = Math.min(
    fadeIn(localTime, entryDur),
    fadeOut(localTime, duration, exitDur)
  );
  return (
    <div style={{ opacity, ...style }}>{children}</div>
  );
}

// ── Brand mark ────────────────────────────────────────────────────────────

function JRLogo({ size = 1, dark = false, pulse = false, time = 0 }) {
  const markSize = 40 * size;
  const dot = 12 * size;
  const pulseScale = pulse ? 1 + 0.25 * Math.sin(time * 4) : 1;
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 14 * size,
    }}>
      <div style={{
        width: markSize, height: markSize, borderRadius: 12 * size,
        background: dark ? '#faf9f5' : '#141413',
        position: 'relative',
      }}>
        <div style={{
          position: 'absolute',
          top: (markSize - dot) / 2, left: (markSize - dot) / 2,
          width: dot, height: dot, borderRadius: '50%',
          background: '#c96442',
          boxShadow: '0 0 0 4px rgba(201,100,66,0.25)',
          transform: `scale(${pulseScale})`,
          transition: 'transform 0.1s',
        }} />
      </div>
      <span style={{
        fontFamily: "'Fraunces','Noto Serif SC', serif",
        fontSize: 32 * size, fontWeight: 500, letterSpacing: '-0.02em',
        color: dark ? '#faf9f5' : '#141413',
      }}>JobRadar</span>
    </div>
  );
}

// ── Count-up number for sprite timelines ──────────────────────────────────

function CountNumber({ to, dur = 1.2, format = (v) => v.toLocaleString(), style }) {
  const { localTime } = useSprite();
  const t = Easing.easeOutCubic(clamp(localTime / dur, 0, 1));
  const v = Math.round(to * t);
  return <span style={style}>{format(v)}</span>;
}

// ── Mini screen frame (browser chrome around actual screen content) ──────

function BrowserFrame({ url, width, height, children }) {
  return (
    <div style={{
      width, height,
      borderRadius: 18, overflow: 'hidden',
      background: '#faf9f5',
      boxShadow: '0 0 0 1px #e8e6dc, 0 40px 80px rgba(0,0,0,0.18), 0 10px 30px rgba(0,0,0,0.08)',
      display: 'flex', flexDirection: 'column',
    }}>
      <div style={{
        height: 32, background: '#f0eee6', borderBottom: '1px solid #e8e6dc',
        display: 'flex', alignItems: 'center', padding: '0 14px', gap: 6, flexShrink: 0,
      }}>
        <span style={{ width: 10, height: 10, borderRadius: 5, background: '#e68786' }} />
        <span style={{ width: 10, height: 10, borderRadius: 5, background: '#ebc17a' }} />
        <span style={{ width: 10, height: 10, borderRadius: 5, background: '#a6c79d' }} />
        <div style={{
          margin: '0 auto', fontSize: 11, color: '#87867f',
          fontFamily: "'JetBrains Mono', monospace",
        }}>{url}</div>
      </div>
      <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
        {children}
      </div>
    </div>
  );
}

// ── Pill ──────────────────────────────────────────────────────────────────

function Pill({ children, tone = 'default', style }) {
  const tones = {
    default: { bg: '#faf9f5', fg: '#3d3d3a', border: '#e8e6dc' },
    terra: { bg: '#f8ecd9', fg: '#a84f34', border: '#eccfb6' },
    emerald: { bg: '#e5efe2', fg: '#3f9a5d', border: '#c7d9c2' },
    dark: { bg: '#141413', fg: '#faf9f5', border: '#141413' },
  };
  const t = tones[tone] || tones.default;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      height: 26, padding: '0 12px', borderRadius: 999,
      fontSize: 12, fontWeight: 500,
      background: t.bg, color: t.fg,
      boxShadow: `0 0 0 1px ${t.border}`,
      fontFamily: "'Inter','Noto Sans SC', sans-serif",
      ...style,
    }}>{children}</span>
  );
}

// ── Section number overline ──────────────────────────────────────────────

function Overline({ children, color = '#c96442' }) {
  return (
    <span style={{
      fontFamily: "'Inter','Noto Sans SC', sans-serif",
      fontSize: 12, fontWeight: 600,
      letterSpacing: '0.18em',
      textTransform: 'uppercase',
      color,
    }}>{children}</span>
  );
}

// ── Radar ping dot ────────────────────────────────────────────────────────

function RadarDot({ time = 0, size = 14, color = '#c96442' }) {
  // Ping ring animates with time
  const ringT = (time * 0.8) % 1;
  const ringScale = 1 + ringT * 2.5;
  const ringOpacity = 1 - ringT;
  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <div style={{
        position: 'absolute', inset: 0, borderRadius: '50%',
        background: color, opacity: 0.5,
        transform: `scale(${ringScale})`,
        opacity: ringOpacity * 0.55,
      }} />
      <div style={{
        position: 'absolute', inset: 0, borderRadius: '50%',
        background: color,
      }} />
    </div>
  );
}

// ── Progress bar ──────────────────────────────────────────────────────────

function ProgressBar({ progress, color = '#c96442', height = 10, width = '100%' }) {
  return (
    <div style={{
      width, height, borderRadius: 999,
      background: '#f0eee6', overflow: 'hidden',
      boxShadow: 'inset 0 0 0 1px #e8e6dc',
    }}>
      <div style={{
        width: `${progress * 100}%`, height: '100%',
        background: color,
        transition: 'width 0.1s',
        backgroundImage: 'linear-gradient(45deg, rgba(255,255,255,0.22) 25%, transparent 25%, transparent 50%, rgba(255,255,255,0.22) 50%, rgba(255,255,255,0.22) 75%, transparent 75%)',
        backgroundSize: '20px 20px',
      }} />
    </div>
  );
}

// ── Ink caption bar (bottom of frame) ─────────────────────────────────────

function Caption({ kicker, title, subtitle, progress = 1 }) {
  return (
    <div style={{
      position: 'absolute', bottom: 60, left: 80,
      maxWidth: 640, opacity: progress,
      transform: `translateY(${(1 - progress) * 20}px)`,
    }}>
      {kicker && <div style={{ marginBottom: 12 }}><Overline>{kicker}</Overline></div>}
      {title && (
        <div style={{
          fontFamily: "'Fraunces','Noto Serif SC', serif",
          fontSize: 64, fontWeight: 500, letterSpacing: '-0.025em',
          lineHeight: 1.05, color: '#141413',
          textWrap: 'pretty',
        }}>{title}</div>
      )}
      {subtitle && (
        <div style={{
          marginTop: 18, fontSize: 20, lineHeight: 1.5,
          color: '#5e5d59', maxWidth: 560,
          fontFamily: "'Inter','Noto Sans SC', sans-serif",
        }}>{subtitle}</div>
      )}
    </div>
  );
}

Object.assign(window, {
  fadeIn, fadeOut, FadeBox,
  JRLogo, CountNumber, BrowserFrame, Pill, Overline,
  RadarDot, ProgressBar, Caption,
});
