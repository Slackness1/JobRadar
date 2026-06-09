'use client';

/**
 * HubLanding — Hub 落地态(对话居中).
 *
 * 居中问候 + 打字机输入框 + SkillBar + 2 张入口卡(职位推荐 / 简历优化).
 * 点 chip / 入口卡只「激活」(高亮 + 引导), 说一句话才「激发交付物」—— 这是
 * 用户坚持的两步契约, 落地卡也不例外.
 *
 * Token: 全部取自 `.hf`(HubShell 已 className="hf").
 */

import { useEffect, useRef, useState } from 'react';
import SkillBar from './SkillBar';
import type { HubModule } from './hub-types';

// ── 打字机提示 — 轮转 suggestion, 逐字打出 → 停 → 删 → 下一条. 聚焦/有输入时暂停. ──
function useTypewriterHint(hints: string[], paused: boolean): string {
  const [text, setText] = useState('');
  const st = useRef({ i: 0, sub: 0, dir: 1 });

  useEffect(() => {
    if (paused || hints.length === 0) return;
    let timer: ReturnType<typeof setTimeout>;
    const tick = () => {
      const s = st.current;
      const full = hints[s.i % hints.length] || '';
      if (s.dir === 1) {
        s.sub += 1;
        setText(full.slice(0, s.sub));
        if (s.sub >= full.length) {
          s.dir = 0;
          timer = setTimeout(tick, 1500);
          return;
        }
        timer = setTimeout(tick, 58 + Math.random() * 46);
      } else {
        s.sub -= 1;
        setText(full.slice(0, s.sub));
        if (s.sub <= 0) {
          s.dir = 1;
          s.i += 1;
          timer = setTimeout(tick, 320);
          return;
        }
        timer = setTimeout(tick, 26);
      }
    };
    timer = setTimeout(tick, 460);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paused, hints.join('|')]);

  return text;
}

const HINTS = [
  '多来点固收',
  '看看券商资管的梯队',
  '一直不考虑国企',
  '只看头部，按薪资排',
  '讲讲中信资管',
  '帮我看下个人档案',
];

function LandingInput({ onSend }: { onSend: (text: string) => void }) {
  const [val, setVal] = useState('');
  const [focused, setFocused] = useState(false);
  const typed = useTypewriterHint(HINTS, focused || val.length > 0);

  const send = () => {
    const v = val.trim();
    if (!v) return;
    onSend(v);
    setVal('');
  };

  const ph = '例如：' + (typed ? typed + ' ▍' : ' ▍');

  return (
    <>
      <input
        value={val}
        onChange={(e) => setVal(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') send();
        }}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        placeholder={ph}
        style={{
          flex: 1,
          minWidth: 0,
          background: 'transparent',
          border: 0,
          outline: 0,
          font: '400 14.5px var(--font-sans)',
          color: 'var(--ink)',
        }}
      />
      <button
        type="button"
        onClick={send}
        className="hf-btn primary"
        title="发送"
        style={{ width: 38, height: 38, padding: 0, borderRadius: 999, flex: 'none' }}
      >
        <svg
          width="17"
          height="17"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M12 19V5M5 12l7-7 7 7" />
        </svg>
      </button>
    </>
  );
}

// ── 入口卡(职位推荐 / 简历优化)— 点卡只激活 ──────────────────────────────────
interface EntryCard {
  key: HubModule;
  icon: React.ReactNode;
  title: string;
  desc: string;
}

const RADAR_ICON = (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.7"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="12" r="5" />
    <circle cx="12" cy="12" r="1" />
  </svg>
);

const FILE_ICON = (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.7"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6" />
    <path d="M8 13h8M8 17h5" />
  </svg>
);

const ARROW_ICON = (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);

const ENTRY_CARDS: EntryCard[] = [
  { key: 'feed', icon: RADAR_ICON, title: '职位推荐', desc: '按确认赛道给第一版 Top，再快增强' },
  { key: 'resume', icon: FILE_ICON, title: '简历优化', desc: '诚实打分 + 反问取证，写回实时刷新' },
];

const ARM_HINT_FOR: Partial<Record<HubModule, string>> = {
  feed: '已激活「职位推荐」· 说一句就给你排第一版岗位',
  skeleton: '已激活「梯队骨架」· 说一句就铺开档次全景',
  resume: '已激活「简历优化」· 说一句就开始打分诊断',
};

export interface HubLandingProps {
  selected: HubModule | null;
  onPick: (k: HubModule) => void;
  onSend: (text: string) => void;
}

export default function HubLanding({ selected, onPick, onSend }: HubLandingProps) {
  return (
    <div style={{ width: '100%', maxWidth: 580 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div
          style={{
            font: '500 28px/1.3 var(--font-serif)',
            color: 'var(--ink)',
            letterSpacing: '-0.02em',
          }}
        >
          晚上好，陈思远。今天想看哪个方向？
        </div>
      </div>

      <div style={{ marginTop: 22 }}>
        <div
          style={{
            display: 'flex',
            gap: 8,
            alignItems: 'center',
            background: 'var(--library-rail)',
            borderRadius: 16,
            padding: '10px 10px 10px 16px',
            boxShadow: selected ? '0 0 0 1px var(--terracotta-ring)' : '0 0 0 1px var(--border-warm)',
            transition: 'box-shadow .2s',
          }}
        >
          <LandingInput onSend={onSend} />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 12, minHeight: 32 }}>
          <SkillBar active={selected} onPick={onPick} />
          {selected && ARM_HINT_FOR[selected] && (
            <span
              style={{
                font: '400 11.5px var(--font-sans)',
                color: 'var(--terracotta-strong)',
                whiteSpace: 'nowrap',
              }}
            >
              {ARM_HINT_FOR[selected]}
            </span>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, marginTop: 18 }}>
        {ENTRY_CARDS.map((card) => {
          const on = selected === card.key;
          return (
            <button
              key={card.key}
              type="button"
              onClick={() => onPick(card.key)}
              style={{
                flex: 1,
                textAlign: 'left',
                borderRadius: 14,
                padding: '14px 15px',
                cursor: 'pointer',
                background: on ? 'var(--terracotta-wash)' : 'var(--ivory)',
                boxShadow: on ? '0 0 0 1.5px var(--terracotta)' : '0 0 0 1px var(--border-warm)',
                transition: 'box-shadow .15s, background .15s',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <span style={{ color: 'var(--terracotta-strong)', display: 'inline-flex' }}>
                  {card.icon}
                </span>
                <span style={{ font: '600 13.5px var(--font-sans)', color: 'var(--ink)' }}>
                  {card.title}
                </span>
                {on ? (
                  <span
                    style={{
                      marginLeft: 'auto',
                      font: '600 9.5px var(--font-sans)',
                      color: '#fff',
                      background: 'var(--terracotta)',
                      borderRadius: 999,
                      padding: '2px 8px',
                    }}
                  >
                    已激活
                  </span>
                ) : (
                  <span style={{ marginLeft: 'auto', color: 'var(--stone)', display: 'inline-flex' }}>
                    {ARROW_ICON}
                  </span>
                )}
              </div>
              <div style={{ font: '400 11.5px/1.5 var(--font-sans)', color: 'var(--stone)' }}>
                {card.desc}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
