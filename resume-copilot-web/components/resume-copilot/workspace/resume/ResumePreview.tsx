'use client';

/**
 * ResumePreview — read-only resume render with hover-✏️ rewrite entry (C-6).
 *
 * Phase 2 FE-3 (2026-05-20).
 *
 * - 渲染当前 session 的 confirmed_profile(基本信息 / 个人介绍 / 教育 / 实习 /
 *   项目 / 技能 / 其他).
 * - 每条 bullet hover → 右上角浮出 ✏️ 改写按钮(C-6 入口之一).
 * - 父组件(RightResumePane)负责实际触发 v0/v2 API + 渲染 inline diff,这里
 *   只负责"显示 + 暴露 path"(单一职责).
 *
 * Field path 约定(dot-style, 跟 backend chat.py 的 `_resolve_field` 一致):
 *   - 教育 highlight:  `education.{i}.highlights.{j}`
 *   - 实习 bullet:    `internships.{i}.bullets.{j}`
 *   - 项目 bullet:    `projects.{i}.bullets.{j}`
 *   - 个人介绍整段:   `candidate_summary`
 *
 * 注:旧 EditableResumeCanvas 里的 module edit / layout controls / 自定义模块 /
 *    PDF 导出按钮都**不**搬过来 — 主工作台只做"预览 + 改写入口",编辑能力交给
 *    plan-mode (§4 design doc).
 */

import type { ReactNode } from 'react';
import type { ResumeProfilePayload } from '../../types';
import { BulletRewriteDiff } from './BulletRewriteDiff';
import type { RewriteV0V2Out } from '../../api';
import type { FabricationWarningAction } from './FabricationWarning';

export interface ActiveRewrite {
  fieldPath: string;
  originalBullet: string;
  loading: boolean;
  result: RewriteV0V2Out | null;
  error?: string | null;
}

export interface ResumePreviewProps {
  profile: ResumeProfilePayload;
  /** 当前正在改写哪条 bullet — null 表示没在改写;由父组件 (RightResumePane) state */
  activeRewrite: ActiveRewrite | null;
  /** 学生点 ✏️ 触发(父组件负责调 API + 设 activeRewrite) */
  onRequestRewrite(fieldPath: string, bulletText: string, section: string): void;
  onAcceptRewrite(v2Text: string, original: string, fieldPath: string): void;
  onDismissRewrite(): void;
  onPlanModeRequest?: (fieldPath: string, originalBullet: string) => void;
  onWarningAction?: (action: FabricationWarningAction, detail: string) => void;
  /** Demo session 是只读 — 改写入口隐藏 */
  isDemo?: boolean;
}

function joinNonEmpty(parts: Array<string | undefined | null>, sep = ' · '): string {
  return parts.filter((part) => part && String(part).trim().length > 0).join(sep);
}

interface BulletRowProps {
  text: string;
  fieldPath: string;
  section: string;
  activeRewrite: ActiveRewrite | null;
  onRequestRewrite: ResumePreviewProps['onRequestRewrite'];
  onAcceptRewrite: ResumePreviewProps['onAcceptRewrite'];
  onDismissRewrite: ResumePreviewProps['onDismissRewrite'];
  onPlanModeRequest?: ResumePreviewProps['onPlanModeRequest'];
  onWarningAction?: ResumePreviewProps['onWarningAction'];
  isDemo?: boolean;
}

function BulletRow(props: BulletRowProps) {
  const {
    text,
    fieldPath,
    section,
    activeRewrite,
    onRequestRewrite,
    onAcceptRewrite,
    onDismissRewrite,
    onPlanModeRequest,
    onWarningAction,
    isDemo,
  } = props;

  const isActive = activeRewrite?.fieldPath === fieldPath;

  return (
    <li className="workspace-hifi__resume-bullet">
      <div className="workspace-hifi__resume-bullet-row">
        <span className="workspace-hifi__resume-bullet-dot" aria-hidden>
          •
        </span>
        <span className="workspace-hifi__resume-bullet-text">{text}</span>
        {!isDemo ? (
          <button
            type="button"
            className="workspace-hifi__resume-bullet-edit"
            aria-label={`改写这条 bullet: ${text.slice(0, 30)}…`}
            title="✏️ 让 AI 基于你的档案改写这条 bullet"
            onClick={() => onRequestRewrite(fieldPath, text, section)}
            disabled={activeRewrite?.loading}
          >
            ✏️ 改写
          </button>
        ) : null}
      </div>
      {isActive ? (
        <BulletRewriteDiff
          loading={activeRewrite.loading}
          result={activeRewrite.result}
          error={activeRewrite.error ?? null}
          originalBullet={activeRewrite.originalBullet}
          fieldPath={activeRewrite.fieldPath}
          onAccept={onAcceptRewrite}
          onDismiss={onDismissRewrite}
          onPlanModeRequest={onPlanModeRequest}
          onWarningAction={onWarningAction}
        />
      ) : null}
    </li>
  );
}

interface ResumeSectionProps {
  title: string;
  children: ReactNode;
  emptyHint?: string;
  count?: number;
}

function ResumeSection({ title, children, emptyHint, count }: ResumeSectionProps) {
  const isEmpty = count === 0;
  return (
    <section className="workspace-hifi__resume-section">
      <h3 className="workspace-hifi__resume-section-title">{title}</h3>
      {isEmpty && emptyHint ? (
        <div className="workspace-hifi__resume-section-empty">{emptyHint}</div>
      ) : (
        children
      )}
    </section>
  );
}

export function ResumePreview(props: ResumePreviewProps) {
  const {
    profile,
    activeRewrite,
    onRequestRewrite,
    onAcceptRewrite,
    onDismissRewrite,
    onPlanModeRequest,
    onWarningAction,
    isDemo,
  } = props;

  const bulletProps = {
    activeRewrite,
    onRequestRewrite,
    onAcceptRewrite,
    onDismissRewrite,
    onPlanModeRequest,
    onWarningAction,
    isDemo,
  };

  const name = profile.basic_info?.name || profile.basic_info?.full_name || '未命名';
  const headline = profile.basic_info?.headline || '';
  const contactLine = joinNonEmpty([
    profile.basic_info?.email,
    profile.basic_info?.phone,
    profile.basic_info?.location,
  ]);

  return (
    <article className="workspace-hifi__resume">
      <header className="workspace-hifi__resume-header">
        <h2 className="workspace-hifi__resume-name">{name}</h2>
        {headline ? <div className="workspace-hifi__resume-headline">{headline}</div> : null}
        {contactLine ? (
          <div className="workspace-hifi__resume-contact">{contactLine}</div>
        ) : null}
      </header>

      {/* 个人介绍 (candidate_summary 整段也可以被改写) */}
      {profile.candidate_summary ? (
        <ResumeSection title="个人介绍">
          <ul className="workspace-hifi__resume-bullets">
            <BulletRow
              text={profile.candidate_summary}
              fieldPath="candidate_summary"
              section="candidate_summary"
              {...bulletProps}
            />
          </ul>
        </ResumeSection>
      ) : null}

      <ResumeSection
        title="教育背景"
        count={profile.education.length}
        emptyHint="解析时未拿到教育背景 — 可在 plan-mode 补充"
      >
        {profile.education.map((edu, i) => (
          <div key={`edu-${i}`} className="workspace-hifi__resume-entry">
            <div className="workspace-hifi__resume-entry-head">
              <span className="workspace-hifi__resume-entry-title">{edu.school || '未知学校'}</span>
              <span className="workspace-hifi__resume-entry-date">
                {joinNonEmpty([edu.start_date, edu.end_date], ' – ')}
              </span>
            </div>
            <div className="workspace-hifi__resume-entry-meta">
              {joinNonEmpty([edu.degree, edu.major])}
            </div>
            {edu.highlights.length > 0 ? (
              <ul className="workspace-hifi__resume-bullets">
                {edu.highlights.map((h, j) => (
                  <BulletRow
                    key={`edu-${i}-h-${j}`}
                    text={h}
                    fieldPath={`education.${i}.highlights.${j}`}
                    section="education"
                    {...bulletProps}
                  />
                ))}
              </ul>
            ) : null}
          </div>
        ))}
      </ResumeSection>

      <ResumeSection
        title="实习经历"
        count={profile.internships.length}
        emptyHint="还没添加实习 — 可在档案里补充,然后再回来改写"
      >
        {profile.internships.map((intern, i) => (
          <div key={`intern-${i}`} className="workspace-hifi__resume-entry">
            <div className="workspace-hifi__resume-entry-head">
              <span className="workspace-hifi__resume-entry-title">
                {intern.company || '未知公司'}
              </span>
              <span className="workspace-hifi__resume-entry-date">
                {joinNonEmpty([intern.start_date, intern.end_date], ' – ')}
              </span>
            </div>
            <div className="workspace-hifi__resume-entry-meta">{intern.role}</div>
            {intern.bullets.length > 0 ? (
              <ul className="workspace-hifi__resume-bullets">
                {intern.bullets.map((b, j) => (
                  <BulletRow
                    key={`intern-${i}-b-${j}`}
                    text={b}
                    fieldPath={`internships.${i}.bullets.${j}`}
                    section="internship"
                    {...bulletProps}
                  />
                ))}
              </ul>
            ) : null}
          </div>
        ))}
      </ResumeSection>

      <ResumeSection
        title="项目经历"
        count={profile.projects.length}
        emptyHint="还没添加项目 — 可在档案里补充,然后再回来改写"
      >
        {profile.projects.map((proj, i) => (
          <div key={`proj-${i}`} className="workspace-hifi__resume-entry">
            <div className="workspace-hifi__resume-entry-head">
              <span className="workspace-hifi__resume-entry-title">{proj.name || '未命名项目'}</span>
              <span className="workspace-hifi__resume-entry-date">{proj.role}</span>
            </div>
            {proj.tech_stack && proj.tech_stack.length > 0 ? (
              <div className="workspace-hifi__resume-entry-meta">
                {proj.tech_stack.join(' / ')}
              </div>
            ) : null}
            {proj.bullets.length > 0 ? (
              <ul className="workspace-hifi__resume-bullets">
                {proj.bullets.map((b, j) => (
                  <BulletRow
                    key={`proj-${i}-b-${j}`}
                    text={b}
                    fieldPath={`projects.${i}.bullets.${j}`}
                    section="project"
                    {...bulletProps}
                  />
                ))}
              </ul>
            ) : null}
          </div>
        ))}
      </ResumeSection>

      {/* 技能 — 一行陈列,不提供改写(C-1 改写聚焦在 bullet) */}
      {(profile.skills.technical.length > 0 ||
        profile.skills.tools.length > 0 ||
        profile.skills.languages.length > 0 ||
        profile.languages.length > 0) && (
        <ResumeSection title="专业技能">
          <div className="workspace-hifi__resume-skill-row">
            {[
              ...profile.skills.technical,
              ...profile.skills.tools,
              ...profile.skills.languages,
              ...profile.languages,
            ]
              .filter(Boolean)
              .map((s, i) => (
                <span key={`skill-${i}`} className="workspace-hifi__resume-skill-chip">
                  {s}
                </span>
              ))}
          </div>
        </ResumeSection>
      )}

      {profile.awards.length > 0 && (
        <ResumeSection title="荣誉与证书">
          <ul className="workspace-hifi__resume-bullets">
            {profile.awards.map((a, i) => (
              <li key={`award-${i}`} className="workspace-hifi__resume-bullet">
                <div className="workspace-hifi__resume-bullet-row">
                  <span className="workspace-hifi__resume-bullet-dot" aria-hidden>
                    •
                  </span>
                  <span className="workspace-hifi__resume-bullet-text">{a}</span>
                </div>
              </li>
            ))}
          </ul>
        </ResumeSection>
      )}
    </article>
  );
}
