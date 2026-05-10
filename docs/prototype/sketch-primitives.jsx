/* global React */
// Shared primitives for sketch wireframes.

const Box = ({ className = '', style, children, ...rest }) => (
  <div className={`sk-box ${className}`} style={style} {...rest}>{children}</div>
);

const Pill = ({ className = '', children, style }) => (
  <span className={`sk-pill ${className}`} style={style}>{children}</span>
);

const Line = ({ w = '100%', className = '', style }) => (
  <span className={`sk-line ${className}`} style={{ width: w, ...style }} />
);

// Stacked placeholder text rows, like a paragraph
const Para = ({ rows = 3, widths = ['100%','92%','68%'], className='', gap = 6, style }) => (
  <div className={className} style={{ display: 'flex', flexDirection: 'column', gap, ...style }}>
    {Array.from({ length: rows }).map((_, i) => (
      <Line key={i} w={widths[i] || widths[widths.length-1]} />
    ))}
  </div>
);

// Placeholder image box with X
const ImgBox = ({ className = '', style, label }) => (
  <div className={`sk-img ${className}`} style={{ position: 'relative', ...style }}>
    {label && (
      <span style={{
        position: 'absolute', inset: 0, display:'flex', alignItems:'center', justifyContent:'center',
        fontFamily: "'Caveat', cursive", fontSize: 14, color: 'var(--soft)', zIndex: 1
      }}>{label}</span>
    )}
  </div>
);

// Small sticky note with annotation
const Note = ({ children, style, side = 'l' }) => (
  <div className={`sk-note ${side === 'r' ? 'r' : ''}`} style={style} data-note="1">
    {children}
  </div>
);

// Hand-drawn arrow (straight)
const Arrow = ({ from, to, curve = 0, accent = false, style }) => {
  // from/to: [x,y] absolute within parent (positioned abs)
  const [x1, y1] = from; const [x2, y2] = to;
  const mx = (x1 + x2) / 2 + curve;
  const my = (y1 + y2) / 2 - Math.abs(curve) * 0.4;
  return (
    <svg style={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'visible', ...style }}>
      <path
        className={`sk-arrow ${accent ? 'accent' : ''}`}
        d={`M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`}
      />
      <path
        className={`sk-arrow ${accent ? 'accent' : ''}`}
        d={`M ${x2} ${y2} l -7 -3 M ${x2} ${y2} l -5 5`}
      />
    </svg>
  );
};

// Artboard header / caption row above content
const Caption = ({ label, kind, n }) => (
  <div style={{ display:'flex', alignItems:'baseline', gap: 10, marginBottom: 10 }}>
    <span className="sk-hw-b" style={{ fontSize: 22, color:'var(--accent)' }}>{n}</span>
    <span className="sk-hw-b" style={{ fontSize: 20 }}>{label}</span>
    {kind && <span className="sk-caption">· {kind}</span>}
  </div>
);

// JobRadar brand dot + wordmark
const BrandDot = ({ size = 22 }) => (
  <span style={{
    width: size, height: size, borderRadius: '50%',
    background: 'var(--accent)',
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    color: '#fff', fontFamily: "'Inter', sans-serif", fontWeight: 700, fontSize: size * 0.5,
  }}>J</span>
);

const Wordmark = ({ size = 16 }) => (
  <span style={{ display:'inline-flex', alignItems:'center', gap: 8 }}>
    <BrandDot size={size + 6} />
    <span className="sk-sans" style={{ fontWeight: 700, fontSize: size, letterSpacing: '-0.02em' }}>JobRadar</span>
  </span>
);

// Tiny tool icon row helper (emoji)
const ToolLine = ({ icon, label, done }) => (
  <div style={{ display:'flex', alignItems:'center', gap: 8, fontSize: 14 }}>
    <span style={{ width: 16, textAlign: 'center', color: done ? 'var(--accent)' : 'var(--soft)' }}>
      {done ? '✓' : '·'}
    </span>
    <span style={{ fontSize: 15 }}>{icon}</span>
    <span className="sk-hw" style={{ fontSize: 17 }}>{label}</span>
  </div>
);

// Squared label (sketch-y input)
const Input = ({ w='100%', h=28, placeholder, style }) => (
  <div className="sk-box thin" style={{ width: w, height: h, padding: '4px 10px', display:'flex', alignItems:'center', ...style }}>
    {placeholder && <span className="sk-hw" style={{ color:'var(--soft)', fontSize: 16 }}>{placeholder}</span>}
  </div>
);

// Button
const Btn = ({ label, variant='line', w, h=32, style }) => {
  const cls = {
    line: '',
    accent: 'filled-accent',
    soft: 'filled-soft',
    dark: 'filled-dark',
  }[variant] || '';
  return (
    <div className={`sk-box ${cls}`} style={{
      height: h, padding: '0 14px', display:'inline-flex', alignItems:'center', justifyContent:'center',
      width: w, borderRadius: 12, ...style
    }}>
      <span className="sk-hw-b" style={{ fontSize: 16 }}>{label}</span>
    </div>
  );
};

// Agent spinner glyph
const Spin = ({ ch = '✢', accent }) => (
  <span className="sk-mono" style={{
    display:'inline-block', width: '1ch', textAlign:'center',
    color: accent ? 'var(--accent)' : 'var(--soft)', fontSize: 15
  }}>{ch}</span>
);

Object.assign(window, {
  Box, Pill, Line, Para, ImgBox, Note, Arrow, Caption,
  BrandDot, Wordmark, ToolLine, Input, Btn, Spin,
});
