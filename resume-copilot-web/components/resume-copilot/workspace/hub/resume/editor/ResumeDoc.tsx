'use client';
import { useLayoutEffect, useRef, useState } from 'react';
import type { CSSProperties, JSX } from 'react';
import './resume-doc.css';
import {
  TEMPLATES,
  layoutToVars,
  type LayoutState,
  type ResumeProfile,
  type ResumeSection,
  type TimelineItem,
} from './resumeSample';

const PAGE_H = 1123; // A4 内容高度 @96dpi
const SHEET_GAP = 26; // 页与页之间的留白(看起来像两张纸)
const TOP_PAD = 36; // 被挤到下一页的块,距纸张顶部留白
const KEEP_PEEK = 90; // 段标题至少要带下文这么高才不被孤立

type Offsets = Record<string, number>;

const MailIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M3 7l9 6 9-6" />
  </svg>
);
const GearIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1" />
  </svg>
);

/** 给可分页块带上 data-blk + marginTop(分页时把块整体下推)。 */
function blk(key: string, offsets: Offsets, keep?: boolean): Record<string, unknown> {
  return {
    'data-blk': key,
    ...(keep ? { 'data-keep': '1' } : {}),
    style: { marginTop: offsets[key] || 0 } as CSSProperties,
  };
}

function Head({ profile, offsets }: { profile: ResumeProfile; offsets: Offsets }) {
  return (
    <div className="rhead" {...blk('head', offsets)}>
      <div className="rname">{profile.name}</div>
      <div className="rcontact">
        <MailIcon />
        <span>{profile.email}</span>
      </div>
    </div>
  );
}

function SectionBody({
  section,
  profile,
  offsets,
}: {
  section: ResumeSection;
  profile: ResumeProfile;
  offsets: Offsets;
}) {
  if (section.type === 'timeline') {
    return (
      <>
        {section.items.map((it: TimelineItem, i) => (
          <div className="item" key={i} {...blk(`it:${section.id}:${i}`, offsets)}>
            <div className="item-top">
              <span className="item-org">{it.org}</span>
              {it.location && <span className="item-loc">{it.location}</span>}
              <span className="item-date">{it.date}</span>
            </div>
            {it.sub && (
              <div className="item-sub">
                {it.sub.includes('·')
                  ? it.sub.split('·').map((part, k, arr) => (
                      <span key={k}>
                        {part}
                        {k < arr.length - 1 && <span className="dot">·</span>}
                      </span>
                    ))
                  : it.sub}
              </div>
            )}
            {it.course && <div className="item-course">{it.course}</div>}
            {it.desc && <div className="item-desc">{it.desc}</div>}
            {it.bullets && (
              <ul className="blist">
                {it.bullets.map((b, k) => (
                  <li key={k}>{b}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </>
    );
  }
  if (section.type === 'paragraphs') {
    return (
      <>
        {section.items.map((p, i) => {
          const idx = p.indexOf('：');
          return (
            <p className="para" key={i} {...blk(`pa:${section.id}:${i}`, offsets)}>
              {idx > -1 ? (
                <>
                  <b>{p.slice(0, idx + 1)}</b>
                  {p.slice(idx + 1)}
                </>
              ) : (
                p
              )}
            </p>
          );
        })}
      </>
    );
  }
  if (section.type === 'skills') {
    return (
      <div className="skills" {...blk(`sk:${section.id}`, offsets)}>
        {profile.skillsText}
      </div>
    );
  }
  return (
    <div className="tags" {...blk(`tg:${section.id}`, offsets)}>
      {section.items.map((t, i) => (
        <span key={i}>{t}</span>
      ))}
    </div>
  );
}

function Section({
  section,
  profile,
  lit,
  offsets,
}: {
  section: ResumeSection;
  profile: ResumeProfile;
  lit: boolean;
  offsets: Offsets;
}) {
  return (
    <div className={`sec${lit ? ' is-lit' : ''}`}>
      <div className="sec-h" {...blk(`hd:${section.id}`, offsets, true)}>
        <span className="t">{section.label}</span>
      </div>
      {lit && <span className="lit-badge">AI 刚写回</span>}
      <SectionBody section={section} profile={profile} offsets={offsets} />
    </div>
  );
}

/** 测量自然几何 → 计算每个块的下推量 + 总页数(块级分页,不切断内容)。 */
function paginate(root: HTMLElement): { off: Offsets; pages: number } {
  const rootTop = root.getBoundingClientRect().top;
  const els = Array.from(root.querySelectorAll<HTMLElement>('[data-blk]'));
  const blocks = els.map((el) => {
    const r = el.getBoundingClientRect();
    return {
      key: el.getAttribute('data-blk') as string,
      keep: el.getAttribute('data-keep') === '1',
      top: r.top - rootTop,
      height: r.height,
    };
  });
  const off: Offsets = {};
  let push = 0;
  let maxBottom = PAGE_H;
  for (let i = 0; i < blocks.length; i++) {
    const b = blocks[i];
    const adjTop = b.top + push;
    const pageIdx = Math.floor(adjTop / PAGE_H);
    const pageBottom = (pageIdx + 1) * PAGE_H;
    let need = b.height;
    if (b.keep && i + 1 < blocks.length) need += Math.min(blocks[i + 1].height, KEEP_PEEK);
    const fitsAlone = b.height <= PAGE_H - TOP_PAD;
    const startsAtTop = adjTop <= pageIdx * PAGE_H + 1;
    if (adjTop + need > pageBottom && fitsAlone && !startsAtTop) {
      const delta = pageBottom - adjTop + TOP_PAD;
      off[b.key] = delta;
      push += delta;
      maxBottom = Math.max(maxBottom, adjTop + delta + b.height);
    } else {
      maxBottom = Math.max(maxBottom, adjTop + b.height);
    }
  }
  return { off, pages: Math.max(1, Math.ceil(maxBottom / PAGE_H)) };
}

export interface ResumeDocProps {
  profile: ResumeProfile;
  /** 模板 id(classic / sidebar / darkhdr / tealcurve / cyanblock)。 */
  templateId: string;
  layout?: LayoutState;
  hidden?: Set<string>;
  litSectionId?: string;
  onPages?: (pages: number) => void;
}

/**
 * WYSIWYG A4 简历文档 — 5 套皮肤单源渲染。超 1 页时按块级分页切成多张独立 A4 纸,
 * 跨页处把整块下推到下一页(不切断条目),纸张之间留白。
 */
export function ResumeDoc({
  profile,
  templateId,
  layout,
  hidden,
  litSectionId,
  onPages,
}: ResumeDocProps): JSX.Element {
  const tpl = TEMPLATES.find((t) => t.id === templateId) ?? TEMPLATES[0];
  const measureRef = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<{ off: Offsets; pages: number }>({ off: {}, pages: 1 });

  const docStyle = (layout ? layoutToVars(layout) : {}) as CSSProperties;
  const isHidden = (id: string) => !!hidden && hidden.has(id);
  const visibleSections = profile.sections.filter((s) => !isHidden(s.id));
  const isLit = (id: string) => !!litSectionId && id === litSectionId;

  // 量稿(零偏移)→ 算分页。useLayoutEffect 在 paint 前出结果,无闪烁。
  useLayoutEffect(() => {
    const el = measureRef.current;
    if (!el) return;
    const recompute = () => {
      const next = paginate(el);
      setState((prev) =>
        prev.pages === next.pages && JSON.stringify(prev.off) === JSON.stringify(next.off) ? prev : next,
      );
      onPages?.(next.pages);
    };
    recompute();
    const ro = new ResizeObserver(recompute);
    ro.observe(el);
    const t = setTimeout(recompute, 120); // 字体加载后重排补算一次
    return () => {
      ro.disconnect();
      clearTimeout(t);
    };
  }, [profile, templateId, layout, hidden, litSectionId, onPages]);

  // 单源渲染:offsets 为空 = 自然量稿;传入计算值 = 分页后的可见纸张。
  const renderContent = (offsets: Offsets): JSX.Element => {
    const sections = visibleSections.map((s) => (
      <Section key={s.id} section={s} profile={profile} lit={isLit(s.id)} offsets={offsets} />
    ));

    if (tpl.id === 'sidebar') {
      const main = visibleSections.filter((s) => s.id !== 'skills');
      const showSkills = !isHidden('skills');
      return (
        <div className="doc t-sidebar" style={docStyle}>
          {showSkills && (
            <div className="aside">
              <div className="a-h">
                <GearIcon />
                <span>掌握技能</span>
              </div>
              <div className="a-skills">{profile.skillsText}</div>
            </div>
          )}
          <div className="main">
            <Head profile={profile} offsets={offsets} />
            {main.map((s) => (
              <Section key={s.id} section={s} profile={profile} lit={isLit(s.id)} offsets={offsets} />
            ))}
          </div>
        </div>
      );
    }

    let body: JSX.Element;
    if (tpl.id === 'darkhdr') {
      body = (
        <>
          <div className="band">
            <Head profile={profile} offsets={offsets} />
          </div>
          {sections}
        </>
      );
    } else if (tpl.id === 'tealcurve') {
      body = (
        <>
          <div className="band" />
          <Head profile={profile} offsets={offsets} />
          {sections}
        </>
      );
    } else {
      body = (
        <>
          <Head profile={profile} offsets={offsets} />
          {sections}
        </>
      );
    }

    return (
      <div className={`doc ${tpl.cls}`} style={docStyle}>
        <div className="pad">{body}</div>
      </div>
    );
  };

  const { off, pages } = state;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: SHEET_GAP }}>
      {Array.from({ length: pages }, (_, i) => (
        <div
          key={i}
          style={{
            position: 'relative',
            width: 794,
            height: PAGE_H,
            background: '#fff',
            boxShadow: '0 0 0 1px rgba(0,0,0,0.06), 0 18px 48px rgba(0,0,0,0.12)',
            overflow: 'hidden',
            flex: 'none',
          }}
        >
          <div style={{ position: 'absolute', top: -i * PAGE_H, left: 0, width: 794 }}>{renderContent(off)}</div>
          {pages > 1 && (
            <span
              style={{
                position: 'absolute',
                right: 12,
                bottom: 10,
                font: '600 10px var(--font-mono)',
                color: 'var(--warm-silver)',
                background: 'rgba(255,255,255,0.85)',
                borderRadius: 5,
                padding: '1px 6px',
              }}
            >
              {i + 1} / {pages}
            </span>
          )}
        </div>
      ))}
      {/* 隐藏量稿 — 零偏移、不裁切,量真实几何 */}
      <div
        ref={measureRef}
        aria-hidden
        style={{ position: 'absolute', left: -99999, top: 0, width: 794, visibility: 'hidden', pointerEvents: 'none' }}
      >
        {renderContent({})}
      </div>
    </div>
  );
}
