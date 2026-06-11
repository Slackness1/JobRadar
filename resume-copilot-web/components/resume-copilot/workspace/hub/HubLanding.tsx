'use client';

/**
 * HubLanding — Hub 落地态(对话居中).
 *
 * 重设计 2026-06-12: 问候 → 两张「预览卡」(职位推荐 / 简历优化, 卡内含模块预览态)
 * → 输入框 → SkillBar chips. 卡片上移到输入框之上、做成预览态(对齐本人新设计稿).
 * 点 chip / 预览卡只「激活」(高亮 + 引导), 说一句话才「激发交付物」—— 两步契约不变.
 *
 * 姓名来自真实简历 profile.basic_info.name(HubShell 注入); 拿不到则退「同学」.
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

  const ph = '例如：' + (typed ? typed + ' ▍' : ' ▍');

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

// ── 图标 ──────────────────────────────────────────────────────────────────────
const RADAR_ICON = (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="12" r="5" />
    <circle cx="12" cy="12" r="1" />
  </svg>
);

const FILE_ICON = (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6" />
    <path d="M8 13h8M8 17h5" />
  </svg>
);

const ARROW_ICON = (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);

// 雷达六边形(简历卡的得分预览图标)
const HEX_ICON = (
  <svg width="34" height="34" viewBox="0 0 40 40" fill="none" stroke="var(--terracotta)" strokeWidth="1.4" aria-hidden="true">
    <polygon points="20,4 33,12 33,28 20,36 7,28 7,12" opacity="0.35" />
    <polygon points="20,11 27,15 27,25 20,29 13,25 13,15" opacity="0.6" />
    <circle cx="20" cy="20" r="1.6" fill="var(--terracotta)" stroke="none" />
  </svg>
);

// 灰条骨架(预览态装饰, 非数据)
function Bar({ w, h = 7 }: { w: number | string; h?: number }) {
  return (
    <span
      style={{
        display: 'block',
        width: typeof w === 'number' ? `${w}%` : w,
        height: h,
        borderRadius: 999,
        background: 'var(--border-warm)',
      }}
    />
  );
}

// ── 预览卡 ────────────────────────────────────────────────────────────────────
const ARM_HINT_FOR: Partial<Record<HubModule, string>> = {
  feed: '已激活「职位推荐」· 说一句就给你排第一版岗位',
  skeleton: '已激活「梯队骨架」· 说一句就铺开档次全景',
  resume: '已激活「简历优化」· 说一句就开始打分诊断',
};

function CardShell({
  on,
  onClick,
  children,
}: {
  on: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        flex: 1,
        minWidth: 0,
        textAlign: 'left',
        borderRadius: 16,
        padding: 14,
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        background: on ? 'var(--terracotta-wash)' : 'var(--ivory)',
        boxShadow: on ? '0 0 0 1.5px var(--terracotta)' : '0 0 0 1px var(--border-warm)',
        transition: 'box-shadow .15s, background .15s',
      }}
    >
      {children}
    </button>
  );
}

function CardFooter({
  icon,
  title,
  desc,
  on,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  on: boolean;
}) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
        <span style={{ color: 'var(--terracotta-strong)', display: 'inline-flex' }}>{icon}</span>
        <span style={{ font: '600 13.5px var(--font-sans)', color: 'var(--ink)' }}>{title}</span>
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
      <div style={{ font: '400 11.5px/1.5 var(--font-sans)', color: 'var(--stone)', marginTop: 5 }}>
        {desc}
      </div>
    </div>
  );
}

// 推荐预览: 两条「岗位行」(rank chip + 骨架 + 匹配/深度徽章)
function FeedPreview() {
  const rows = [
    { rank: '#1', match: '匹配 96', depth: '深度 94' },
    { rank: '#2', match: '匹配 91', depth: '深度 —' },
  ];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {rows.map((r) => (
        <div
          key={r.rank}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 9,
            padding: '9px 10px',
            borderRadius: 11,
            background: 'var(--parchment)',
            boxShadow: 'inset 0 0 0 1px var(--border-warm)',
          }}
        >
          <span style={{ font: '600 10px var(--font-mono)', color: 'var(--stone)', flex: 'none' }}>
            {r.rank}
          </span>
          <span style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
            <Bar w={72} />
            <Bar w={46} h={6} />
          </span>
          <span style={{ display: 'flex', gap: 5, flex: 'none' }}>
            <span style={{ font: '600 9.5px var(--font-sans)', color: 'var(--stone)', background: 'var(--library-rail)', borderRadius: 999, padding: '2px 7px' }}>
              {r.match}
            </span>
            <span style={{ font: '600 9.5px var(--font-sans)', color: 'var(--olive)', background: 'rgba(122,132,92,0.12)', borderRadius: 999, padding: '2px 7px' }}>
              {r.depth}
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}

// 简历预览: 现状分 + 雷达六边形 + 深度优化按钮
function ResumePreview() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '10px 12px',
          borderRadius: 11,
          background: 'var(--parchment)',
          boxShadow: 'inset 0 0 0 1px var(--border-warm)',
        }}
      >
        <div style={{ flex: 'none', textAlign: 'center' }}>
          <div style={{ font: '600 26px/1 var(--font-serif)', color: 'var(--ink)' }}>72</div>
          <div style={{ font: '400 9.5px var(--font-sans)', color: 'var(--stone)', marginTop: 3 }}>现状分</div>
        </div>
        <span style={{ flex: 'none', display: 'inline-flex' }}>{HEX_ICON}</span>
        <span style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 5, minWidth: 0 }}>
          <Bar w={'90%'} />
          <Bar w={'64%'} h={6} />
        </span>
      </div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 9,
          padding: '8px 10px',
          borderRadius: 11,
          background: 'var(--parchment)',
          boxShadow: 'inset 0 0 0 1px var(--border-warm)',
        }}
      >
        <span style={{ flex: 1, minWidth: 0 }}>
          <Bar w={'70%'} />
        </span>
        <span
          style={{
            flex: 'none',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            font: '600 10px var(--font-sans)',
            color: 'var(--terracotta-strong)',
            background: 'var(--terracotta-wash)',
            borderRadius: 999,
            padding: '4px 9px',
          }}
        >
          深度优化 {ARROW_ICON}
        </span>
      </div>
    </div>
  );
}

// ── 时段问候 ──────────────────────────────────────────────────────────────────
function greetPrefix(): string {
  const h = new Date().getHours();
  if (h < 6) return '夜深了';
  if (h < 11) return '早上好';
  if (h < 14) return '中午好';
  if (h < 18) return '下午好';
  return '晚上好';
}

export interface HubLandingProps {
  selected: HubModule | null;
  onPick: (k: HubModule) => void;
  onSend: (text: string) => void;
  /** 真实候选人姓名(profile.basic_info.name); 空则用「同学」 */
  userName?: string;
}

export default function HubLanding({ selected, onPick, onSend, userName }: HubLandingProps) {
  const who = (userName || '').trim() || '同学';
  return (
    <div
      style={{
        flex: 1,
        width: '100%',
        maxWidth: 680,
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* ── 顶部留白(小): 把问候+卡片压到中上部约 1/4 处, 不贴顶 ── */}
      <div style={{ flex: 1, minHeight: 40 }} />

      {/* ── 上块: 问候 + 预览卡(中上部) ── */}
      <div style={{ flex: 'none' }}>
        <div
          style={{
            font: '500 27px/1.3 var(--font-serif)',
            color: 'var(--ink)',
            letterSpacing: '-0.02em',
          }}
        >
          {greetPrefix()}，{who}。今天想看哪个方向？
        </div>

        {/* 两张预览卡 */}
        <div style={{ display: 'flex', gap: 14, marginTop: 22 }}>
          <CardShell on={selected === 'feed'} onClick={() => onPick('feed')}>
            <FeedPreview />
            <CardFooter
              icon={RADAR_ICON}
              title="职位推荐"
              desc="了解你和你的需求，精准匹配职位"
              on={selected === 'feed'}
            />
          </CardShell>
          <CardShell on={selected === 'resume'} onClick={() => onPick('resume')}>
            <ResumePreview />
            <CardFooter
              icon={FILE_ICON}
              title="简历优化"
              desc="AI 对话修改简历，懂你更懂 HR 的简历"
              on={selected === 'resume'}
            />
          </CardShell>
        </div>
      </div>

      {/* ── 弹性留白(大): 把对话框推到底, 与顶部 1:2 → 内容落在中上部 ── */}
      <div style={{ flex: 2, minHeight: 48 }} />

      {/* ── 下块: 对话框沉底 + 技能 chips ── */}
      <div style={{ flex: 'none', paddingBottom: 28 }}>
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
    </div>
  );
}
