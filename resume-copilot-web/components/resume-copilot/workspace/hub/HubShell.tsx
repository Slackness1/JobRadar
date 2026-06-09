'use client';
import './hub-theme.css';

export default function HubShell({ sessionId }: { sessionId: number }) {
  return (
    <div data-theme="hub" className="hf" style={{ height: '100vh', display: 'flex', overflow: 'hidden', background: 'var(--parchment)' }}>
      <div style={{ margin: 'auto', font: '500 18px var(--font-serif)', color: 'var(--ink)' }}>
        Hub 外壳 · session {sessionId}
      </div>
    </div>
  );
}
