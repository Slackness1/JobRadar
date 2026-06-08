// nlrec-chat.jsx — center NL 对话栏: turns, thinking (border-beam), 意图解析 trace, intel, composer
/* global React, window */
const { useState, useEffect, useRef } = React;

const GLYPHS = ['·', '✢', '✳', '✶', '✻', '✽'];
function Spinner({ color }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((x) => (x + 1) % GLYPHS.length), 120);
    return () => clearInterval(t);
  }, []);
  return <span style={{ font: '500 14px var(--font-mono)', color: color || 'var(--terracotta)', minWidth: '1ch', display: 'inline-block', textAlign: 'center' }}>{GLYPHS[i]}</span>;
}

// avatar dot
function Avatar({ size = 28 }) {
  return (
    <div style={{ width: size, height: size, borderRadius: 999, color: 'var(--ivory)', display: 'grid', placeItems: 'center', flex: 'none',
      background: 'radial-gradient(circle at 35% 30%, #e38066 0%, var(--terracotta) 45%, var(--terracotta-strong, #a84f34) 100%)',
      boxShadow: '0 2px 7px rgba(201,100,66,0.26)' }}>
      <svg width={size * 0.54} height={size * 0.54} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ filter: 'drop-shadow(0 1px 1px rgba(0,0,0,0.18))' }}>
        <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z" />
        <path d="M20 3v4" />
        <path d="M22 5h-4" />
        <path d="M4 17v2" />
        <path d="M5 18H3" />
      </svg>
    </div>
  );
}

function Turn({ who, children }) {
  const me = who === 'me';
  return (
    <div className="hf-slide" style={{ display: 'flex', justifyContent: me ? 'flex-end' : 'flex-start', gap: 9, alignItems: 'flex-start' }}>
      {!me && <Avatar />}
      <div style={{ maxWidth: '82%', font: '400 13.5px/1.6 var(--font-sans)',
        color: me ? 'var(--ivory)' : 'var(--ink-soft)',
        background: me ? 'var(--dark-surface)' : 'var(--ivory)',
        boxShadow: me ? 'none' : '0 0 0 1px var(--border)',
        borderRadius: 15, borderTopLeftRadius: me ? 15 : 5, borderTopRightRadius: me ? 5 : 15, padding: '10px 14px' }}>
        {children}
      </div>
    </div>
  );
}

// border-beam "意图解析中" thinking card
function ThinkingCard() {
  return (
    <div className="hf-slide" style={{ display: 'flex', gap: 9, alignItems: 'flex-start' }}>
      <Avatar />
      <div style={{ position: 'relative', borderRadius: 15, borderTopLeftRadius: 5, background: 'var(--ivory)', padding: '11px 15px', boxShadow: '0 0 0 1px var(--border)', overflow: 'hidden' }}>
        <div className="ds-border-beam" />
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, position: 'relative' }}>
          <Spinner />
          <span style={{ font: '500 13px var(--font-sans)', color: 'var(--muted)' }}>意图解析中 · flash</span>
          <span className="hf-mono-sm" style={{ color: 'var(--stone)', fontSize: 11 }}>1 次 LLM / 轮</span>
        </div>
      </div>
    </div>
  );
}

// 意图解析 trace — collapsible JSON contract
function TraceCard({ trace }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginLeft: 37, marginTop: -2 }}>
      <button onClick={() => setOpen((o) => !o)} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 0', font: '600 10px var(--font-sans)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--stone)' }}>
        <span style={{ color: 'var(--terracotta-strong)' }}>意图解析</span> · flash 1 次
        <span style={{ transition: 'transform .15s', transform: open ? 'rotate(180deg)' : 'none', fontSize: 9 }}>▾</span>
      </button>
      {open && (
        <div className="hf-slide" style={{ marginTop: 5, borderRadius: 12, padding: '11px 13px', background: 'var(--library-rail)', boxShadow: '0 0 0 1px var(--border)', borderStyle: 'dashed', font: '500 11.5px/1.8 var(--font-mono)', color: 'var(--ink-soft)' }}>
          <div>intent: <b style={{ color: 'var(--terracotta-strong)' }}>{trace.intent}</b></div>
          <div>query_delta: {trace.query_delta}</div>
          <div>remember: {trace.remember} <span style={{ color: 'var(--stone)', fontFamily: 'var(--font-sans)', fontSize: 11 }}>{trace.rememberNote}</span></div>
        </div>
      )}
    </div>
  );
}

function MemoryToast({ text }) {
  return (
    <div className="hf-slide" style={{ marginLeft: 37, display: 'inline-flex', alignItems: 'center', gap: 7, padding: '6px 11px', borderRadius: 999, background: 'var(--library-rail)', boxShadow: '0 0 0 1px var(--border-strong)', borderStyle: 'dashed', width: 'fit-content' }}>
      <span style={{ width: 7, height: 7, borderRadius: 999, background: 'var(--terracotta)' }} />
      <span style={{ font: '500 11px var(--font-mono)', color: 'var(--muted)' }}>{text}</span>
    </div>
  );
}

function IntelCard({ id }) {
  const intel = window.NLData.INTEL[id];
  if (!intel) return null;
  return (
    <div className="hf-slide" style={{ marginLeft: 37, marginTop: 2, background: 'var(--ivory)', borderRadius: 16, padding: '14px 16px', boxShadow: 'var(--sh-ring)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 15 }}>🏢</span>
        <span style={{ font: '600 14px var(--font-sans)', color: 'var(--ink)' }}>{intel.co}</span>
        <span style={{ marginLeft: 'auto', font: '500 11px var(--font-sans)', color: 'var(--stone)' }}>公司情报</span>
      </div>
      <div style={{ font: '400 12.5px/1.6 var(--font-sans)', color: 'var(--ink-soft)', marginBottom: 11 }}>{intel.line}</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7, marginBottom: 11 }}>
        {intel.rows.map(([k, v], i) => (
          <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'baseline' }}>
            <span style={{ flex: 'none', minWidth: 40, font: '600 11px var(--font-sans)', color: 'var(--stone)' }}>{k}</span>
            <span style={{ font: '400 12px var(--font-sans)', color: 'var(--ink-soft)', lineHeight: 1.5 }}>{v}</span>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {intel.tags.map((t) => <span key={t} className="hf-pill terra" style={{ height: 24 }}>{t}</span>)}
      </div>
    </div>
  );
}

function Composer({ chips, onChip, onSend, placeholder }) {
  const [val, setVal] = useState('');
  const send = () => { const v = val.trim(); if (!v) return; onSend(v); setVal(''); };
  return (
    <div style={{ flex: 'none', padding: 16, borderTop: '1px solid var(--border)', background: 'var(--parchment)' }}>
      {chips.length > 0 && (
        <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap', marginBottom: 11 }}>
          {chips.map((c) => (
            <button key={c.key} onClick={() => onChip(c)} className="hf-pill" style={{ height: 30, cursor: 'pointer', boxShadow: '0 0 0 1px var(--border-strong)' }}>
              {c.icon && <span style={{ marginRight: 1 }}>{c.icon}</span>}{c.label}
            </button>
          ))}
        </div>
      )}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', background: 'var(--library-rail)', borderRadius: 16, padding: '8px 8px 8px 14px', boxShadow: '0 0 0 1px var(--border)' }}>
        <input value={val} onChange={(e) => setVal(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder={placeholder} style={{ flex: 1, background: 'transparent', border: 0, outline: 0, font: '400 14px var(--font-sans)', color: 'var(--ink)' }} />
        <button onClick={send} className="hf-btn primary" style={{ width: 36, height: 36, padding: 0, borderRadius: 999 }} title="发送">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
        </button>
      </div>
    </div>
  );
}

window.NLChat = { Turn, ThinkingCard, TraceCard, MemoryToast, IntelCard, Composer, Avatar, Spinner };
