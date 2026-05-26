'use client';

/**
 * ResumeSummaryCard — key/value grid of parsed resume fields shown on the
 * `/resume-copilot/confirm` page (P2, 2026-05-26).
 *
 * Replaces the old WorkspaceConfirmGuide overlay's `<ParsedPreview/>` table —
 * same field set, restyled to match design `hifi-ws-confirm.jsx::HFResumeSummary`
 * (single-column 120/1fr grid, first row no top border, ivory card on
 * `#fdfbf3`).
 *
 * Scope: `.hf .rc-confirm` (styles in confirm-theme.css).
 */

import type { ResumeProfilePayload } from '../types';

interface ResumeSummaryCardProps {
  profile: ResumeProfilePayload;
}

interface SummaryRow {
  key: string;
  /** Either a plain string OR list-of-lines (rendered as `<ul>`). */
  value: string | string[];
}

export function ResumeSummaryCard({ profile }: ResumeSummaryCardProps) {
  const name =
    profile.basic_info?.name ||
    profile.basic_info?.full_name ||
    '—';
  const headline = profile.basic_info?.headline || '';

  // 学校 — 首段 education 拼装 "学校 · 学历 专业 +N 段"
  const eduFirst = profile.education?.[0];
  const eduExtra = profile.education?.length > 1 ? ` · +${profile.education.length - 1} 段` : '';
  const school = eduFirst
    ? `${eduFirst.school || '—'} · ${eduFirst.degree || ''} ${eduFirst.major || ''}`.trim() +
      eduExtra
    : '—';

  // 实习经历 — 列表
  const internships = profile.internships || [];
  const internshipsLabel = `实习经历 (${internships.length} 段)`;
  const internshipsValue: string | string[] =
    internships.length === 0
      ? '—'
      : internships.map((it) => `${it.company || '—'}${it.role ? ` · ${it.role}` : ''}`);

  // 项目经历 — 列表
  const projects = profile.projects || [];
  const projectsLabel = `项目经历 (${projects.length} 段)`;
  const projectsValue: string | string[] =
    projects.length === 0
      ? '—'
      : projects.map((p) => p.name || p.role || '—');

  // 技能 — 拼 "N 项 · top 4 / ..."
  const techSkills = profile.skills?.technical || [];
  const toolSkills = profile.skills?.tools || [];
  const skillCount = techSkills.length + toolSkills.length;
  const skillTop = [...techSkills, ...toolSkills].slice(0, 4).join(' / ');
  const skills =
    skillCount === 0 ? '—' : `${skillCount} 项 · ${skillTop}${skillCount > 4 ? ' …' : ''}`;

  const summary = (profile.candidate_summary || '').trim() || '—';

  const rows: SummaryRow[] = [
    { key: '姓名', value: name },
    { key: '学校', value: school },
    { key: internshipsLabel, value: internshipsValue },
    { key: projectsLabel, value: projectsValue },
    { key: '技能', value: skills },
    { key: '目标 / Headline', value: headline || '—' },
    { key: '个人介绍', value: summary },
  ];

  return (
    <div className="rc-confirm__card rc-confirm__summary">
      {rows.map((row, i) => (
        <div key={i} className="rc-confirm__summary-row">
          <div className="rc-confirm__summary-key">{row.key}</div>
          <div
            className={`rc-confirm__summary-value${row.value === '—' ? ' rc-confirm__summary-value-muted' : ''}`}
          >
            {Array.isArray(row.value) ? (
              <ul className="rc-confirm__summary-list">
                {row.value.map((line, j) => (
                  <li key={j}>· {line}</li>
                ))}
              </ul>
            ) : (
              row.value
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
