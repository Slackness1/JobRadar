'use client';
import { useState } from 'react';
import './hub-theme.css';
import HubSidebar from './HubSidebar';
import type { HubModule } from './hub-types';

export default function HubShell({ sessionId }: { sessionId: number }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div
      data-theme="hub"
      className="hf"
      style={{ height: '100vh', display: 'flex', overflow: 'hidden', background: 'var(--parchment)' }}
    >
      {/* Left: collapsible sidebar */}
      <HubSidebar
        collapsed={collapsed}
        onToggle={() => setCollapsed((c) => !c)}
        active={null}
        onNav={(k: HubModule) => console.log('nav', k)}
        onNew={() => {}}
      />

      {/* Center: placeholder — real conversation panel arrives in a later task */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minWidth: 0,
        }}
      >
        <span style={{ font: '500 18px var(--font-serif)', color: 'var(--ink)' }}>
          Hub 外壳 · session {sessionId}
        </span>
      </div>
    </div>
  );
}
