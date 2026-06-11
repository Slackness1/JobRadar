'use client';
import { useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { ChevronDown, ChevronUp, Quote } from 'lucide-react';
import type { ResumeProfile, ResumeSection, TimelineItem } from './resumeSample';

const inputStyle: CSSProperties = {
  width: '100%',
  font: '400 11.5px var(--font-sans)',
  color: 'var(--ink)',
  background: 'var(--ivory)',
  border: '1px solid var(--border-warm)',
  borderRadius: 7,
  padding: '6px 8px',
  outline: 'none',
  boxSizing: 'border-box',
};
const taStyle: CSSProperties = { ...inputStyle, minHeight: 56, lineHeight: 1.5, resize: 'vertical' };
const labelStyle: CSSProperties = {
  font: '500 10px var(--font-sans)',
  color: 'var(--stone)',
  margin: '0 0 4px',
  display: 'block',
};

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={{ marginBottom: 9 }}>
      <span style={labelStyle}>{label}</span>
      {children}
    </div>
  );
}

export interface LeftEditProps {
  profile: ResumeProfile;
  onProfile: (p: ResumeProfile) => void;
  onQuote: (k: string) => void;
}

/** 左栏「简历编辑」tab — 分模块手风琴,就地编辑实时写回中栏文档。 */
export function LeftEdit({ profile, onProfile, onQuote }: LeftEditProps) {
  const [open, setOpen] = useState<string>('intern');
  const toggle = (id: string) => setOpen((cur) => (cur === id ? '' : id));

  const setBasic = (patch: Partial<Pick<ResumeProfile, 'name' | 'email' | 'skillsText'>>) =>
    onProfile({ ...profile, ...patch });

  const patchSection = (id: string, fn: (s: ResumeSection) => ResumeSection) =>
    onProfile({ ...profile, sections: profile.sections.map((s) => (s.id === id ? fn(s) : s)) });

  const setItem = (secId: string, idx: number, patch: Partial<TimelineItem>) =>
    patchSection(secId, (s) =>
      s.type === 'timeline'
        ? { ...s, items: s.items.map((it, i) => (i === idx ? { ...it, ...patch } : it)) }
        : s,
    );

  const moduleCard = (id: string, title: string, body: ReactNode) => {
    const isOpen = open === id;
    return (
      <div
        key={id}
        style={{
          borderRadius: 12,
          background: 'var(--ivory)',
          boxShadow: isOpen ? '0 0 0 1px var(--terracotta-ring)' : '0 0 0 1px var(--border-warm)',
          overflow: 'hidden',
        }}
      >
        <button
          onClick={() => toggle(id)}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '10px 12px',
            background: 'transparent',
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          <span style={{ font: '600 12.5px var(--font-sans)', color: 'var(--ink)' }}>{title}</span>
          <span style={{ marginLeft: 'auto', color: 'var(--stone)', display: 'inline-flex' }}>
            {isOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </span>
        </button>
        {isOpen && <div style={{ padding: '0 12px 12px' }}>{body}</div>}
      </div>
    );
  };

  function sectionBody(section: ResumeSection): ReactNode {
    if (section.type === 'timeline') {
      return section.items.map((it, idx) => (
        <div
          key={idx}
          style={{
            paddingTop: idx ? 10 : 0,
            marginTop: idx ? 10 : 0,
            borderTop: idx ? '1px solid var(--border-cream)' : 'none',
          }}
        >
          <Field label="机构 / 标题">
            <input style={inputStyle} value={it.org} onChange={(e) => setItem(section.id, idx, { org: e.target.value })} />
          </Field>
          <Field label="时间">
            <input style={inputStyle} value={it.date} onChange={(e) => setItem(section.id, idx, { date: e.target.value })} />
          </Field>
          <Field label="地点">
            <input
              style={inputStyle}
              value={it.location ?? ''}
              placeholder="如:上海 / 北京 / 远程"
              onChange={(e) => setItem(section.id, idx, { location: e.target.value })}
            />
          </Field>
          {it.sub !== undefined && (
            <Field label="副标题">
              <input style={inputStyle} value={it.sub} onChange={(e) => setItem(section.id, idx, { sub: e.target.value })} />
            </Field>
          )}
          {it.course !== undefined && (
            <Field label="主修 / 备注">
              <input
                style={inputStyle}
                value={it.course}
                onChange={(e) => setItem(section.id, idx, { course: e.target.value })}
              />
            </Field>
          )}
          {it.desc !== undefined && (
            <Field label="描述">
              <textarea
                style={taStyle}
                value={it.desc}
                onChange={(e) => setItem(section.id, idx, { desc: e.target.value })}
              />
            </Field>
          )}
          {it.bullets !== undefined && (
            <Field label="要点(每行一条)">
              <textarea
                style={{ ...taStyle, minHeight: 72 }}
                value={it.bullets.join('\n')}
                onChange={(e) =>
                  setItem(section.id, idx, { bullets: e.target.value.split('\n').filter((l) => l.trim() !== '') })
                }
              />
            </Field>
          )}
          <button
            onClick={() => onQuote(section.id)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              font: '500 10px var(--font-sans)',
              color: 'var(--terracotta-strong)',
              background: 'var(--terracotta-wash)',
              boxShadow: '0 0 0 1px #eccfb6',
              borderRadius: 7,
              padding: '3px 7px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            <Quote size={11} /> 引用此段
          </button>
        </div>
      ));
    }
    if (section.type === 'paragraphs') {
      return section.items.map((p, idx) => (
        <Field key={idx} label={`第 ${idx + 1} 段`}>
          <textarea
            style={{ ...taStyle, minHeight: 72 }}
            value={p}
            onChange={(e) =>
              patchSection(section.id, (s) =>
                s.type === 'paragraphs'
                  ? { ...s, items: s.items.map((x, i) => (i === idx ? e.target.value : x)) }
                  : s,
              )
            }
          />
        </Field>
      ));
    }
    if (section.type === 'skills') {
      return (
        <Field label="技能(自由文本)">
          <textarea
            style={{ ...taStyle, minHeight: 90 }}
            value={profile.skillsText}
            onChange={(e) => setBasic({ skillsText: e.target.value })}
          />
        </Field>
      );
    }
    // tags
    return (
      <Field label="条目(英文逗号分隔)">
        <input
          style={inputStyle}
          value={section.items.join(', ')}
          onChange={(e) =>
            patchSection(section.id, (s) =>
              s.type === 'tags'
                ? { ...s, items: e.target.value.split(',').map((x) => x.trim()).filter(Boolean) }
                : s,
            )
          }
        />
      </Field>
    );
  }

  return (
    <div style={{ overflow: 'auto', padding: '4px 2px 18px' }}>
      <span className="hf-pill" style={{ height: 24, marginBottom: 10, whiteSpace: 'nowrap' }}>
        就地编辑 · 改完即时刷新预览
      </span>
      <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {/* 基本信息 */}
        {moduleCard(
          'basic',
          '基本信息',
          <>
            <Field label="姓名">
              <input style={inputStyle} value={profile.name} onChange={(e) => setBasic({ name: e.target.value })} />
            </Field>
            <Field label="邮箱 / 联系方式">
              <input style={inputStyle} value={profile.email} onChange={(e) => setBasic({ email: e.target.value })} />
            </Field>
          </>,
        )}
        {/* 各简历段 */}
        {profile.sections.map((s) => moduleCard(s.id, s.label, sectionBody(s)))}
        <div
          style={{
            borderRadius: 10,
            border: '1px dashed var(--border-strong)',
            padding: '10px',
            font: '500 12px var(--font-sans)',
            color: 'var(--stone)',
            textAlign: 'center',
          }}
        >
          + 自定义模块(证书 / 社团 / 作品…)
        </div>
      </div>
    </div>
  );
}
