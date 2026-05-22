'use client';

/**
 * WorkspaceConfirmGuide — overlay shown when a session lands on
 * `/resume-copilot` but `has_confirmed_profile === false`.
 *
 * 2026-05-21 v3 (option A — 单页合并确认):
 *   原来这页只让学生确认 parser 的 profile, 赛道靠 inferred 自动猜, 地点
 *   根本没问 → 第一批推荐经常推错赛道, 学生 30 秒内信任就崩。
 *   现在把"想准备的赛道"和"目标城市"两个 chip 多选合并进同一页, 学生顺手
 *   prune 一下, "确认进入工作台" 一次提交:
 *      1. PUT /preferences (tracks + locations)
 *      2. PUT /confirmed-profile
 *      3. POST /generate
 *   这样第一批推荐就是按学生本人意图生成的, 而不是 AI 猜的。
 *
 * Non-dismissable (no close button) — 没确认前没东西给学生看。
 */

import { useEffect, useMemo, useState } from 'react';
import { message as antdMessage } from 'antd';
import {
  getResumeCopilotParsedProfile,
  postResumeCopilotGenerate,
  putResumeCopilotConfirmedProfile,
  putResumeCopilotPreferences,
} from '../api';
import { EMPTY_PREFERENCES, type ResumeProfilePayload } from '../types';
import { TRACKS } from './TrackPickerModal';

// SAIF MF 学生主流目标城市 — 顺序按"投递热度"排, 北京+上海默认勾选
// (大多数 MF 学生默认 target)。其他城市学生可加。
const COMMON_LOCATIONS: string[] = [
  '北京',
  '上海',
  '深圳',
  '香港',
  '杭州',
  '广州',
  '南京',
  '苏州',
  '成都',
  '其他',
];
const DEFAULT_LOCATIONS = ['北京', '上海'];

export interface WorkspaceConfirmGuideProps {
  sessionId: number;
  /** Called after confirm + generate succeed so parent can re-poll session. */
  onConfirmed: () => void;
}

type FetchState =
  | { kind: 'loading' }
  | { kind: 'ready'; profile: ResumeProfilePayload }
  | { kind: 'error'; message: string };

export function WorkspaceConfirmGuide({ sessionId, onConfirmed }: WorkspaceConfirmGuideProps) {
  const [fetchState, setFetchState] = useState<FetchState>({ kind: 'loading' });
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // 学生选的赛道 / 城市 — profile 拉到后用 inferred_tracks 初始化
  const [selectedTracks, setSelectedTracks] = useState<string[]>([]);
  const [selectedLocations, setSelectedLocations] = useState<string[]>(DEFAULT_LOCATIONS);
  // inferred_tracks 里有合法赛道的, 在 chip 上加 "AI 推断" 角标
  const inferredSet = useMemo(() => {
    if (fetchState.kind !== 'ready') return new Set<string>();
    return new Set((fetchState.profile.inferred_tracks ?? []).filter(Boolean));
  }, [fetchState]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const parsed = await getResumeCopilotParsedProfile(sessionId);
        if (cancelled) return;
        if (!parsed?.profile) {
          setFetchState({ kind: 'error', message: 'parser 没返回 profile, 解析可能没完成。' });
          return;
        }
        setFetchState({ kind: 'ready', profile: parsed.profile });
        // 默认勾选 AI 推断的赛道(只保留 canonical 列表里有的, 防止 AI 编新词)
        const validKeys = new Set(TRACKS.map((t) => t.key));
        const inferredValid = (parsed.profile.inferred_tracks ?? []).filter(
          (t) => validKeys.has(t),
        );
        if (inferredValid.length > 0) {
          setSelectedTracks(inferredValid);
        }
      } catch (e) {
        if (cancelled) return;
        setFetchState({
          kind: 'error',
          message: e instanceof Error ? e.message : String(e),
        });
      }
    })();
    return () => { cancelled = true; };
  }, [sessionId]);

  const toggleTrack = (key: string) => {
    setSelectedTracks((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  };
  const toggleLocation = (loc: string) => {
    setSelectedLocations((prev) =>
      prev.includes(loc) ? prev.filter((l) => l !== loc) : [...prev, loc],
    );
  };

  const canSubmit =
    fetchState.kind === 'ready' &&
    selectedTracks.length > 0 &&
    selectedLocations.length > 0;

  const handleConfirm = async () => {
    if (fetchState.kind !== 'ready') return;
    if (selectedTracks.length === 0) {
      setSubmitError('请至少选一个想准备的赛道。');
      return;
    }
    if (selectedLocations.length === 0) {
      setSubmitError('请至少选一个目标城市。');
      return;
    }
    setBusy(true);
    setSubmitError(null);
    try {
      // 1. 先把赛道+地点提交, 让推荐能按学生意图生成
      const prefResult = await putResumeCopilotPreferences(sessionId, {
        ...EMPTY_PREFERENCES,
        preferred_tracks: selectedTracks,
        preferred_locations: selectedLocations,
        all_skipped: false,
      });
      // #3 (2026-05-21): BE 把不认识的赛道名通过 X-Unknown-Tracks header 透出。
      // 学生 / 老师 import 老 persona JSON 时, 系统会默默 canonicalize, 这里
      // 弹 toast 让学生知道发生了映射, 流程不阻塞 (confirm 仍然继续)。
      if (prefResult.unknownTracks && prefResult.unknownTracks.length > 0) {
        const unknown = prefResult.unknownTracks.join('、');
        void antdMessage.warning({
          content: `「${unknown}」不在 10 个 SAIF 赛道中, 已尽量按规则映射 — 如要精确匹配请从 chip 列表重选。`,
          duration: 6,
        });
      }
      // 2. 简历 profile 入库
      await putResumeCopilotConfirmedProfile(sessionId, fetchState.profile);
      // 3. 触发 /generate — 此时 preferences 已就位, recommend pipeline 会按
      //    preferred_tracks 而不是 inferred_tracks 出第一批
      await postResumeCopilotGenerate(sessionId);
      onConfirmed();
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  };

  return (
    <div className="workspace-hifi__confirm-guide-backdrop" role="dialog" aria-modal="true">
      <div className="workspace-hifi__confirm-guide-card">
        <div className="workspace-hifi__confirm-guide-icon" aria-hidden>📄</div>
        <h2 className="workspace-hifi__confirm-guide-title">
          AI 已解析你的简历
        </h2>
        <p className="workspace-hifi__confirm-guide-subtitle">
          看一眼下面三块都对得上吗 — 解析的简历 / 想准备的赛道 / 目标城市,
          一次确认我就按你的意图出第一批推荐。
        </p>

        {fetchState.kind === 'loading' ? (
          <div className="workspace-hifi__confirm-guide-loading">解析中…</div>
        ) : fetchState.kind === 'error' ? (
          <div className="workspace-hifi__confirm-guide-error" role="alert">
            读取 parser 结果出错:{fetchState.message}
          </div>
        ) : (
          <>
            <ParsedPreview profile={fetchState.profile} />

            <section
              className="workspace-hifi__confirm-guide-section"
              aria-labelledby="confirm-guide-tracks-label"
            >
              <header className="workspace-hifi__confirm-guide-section-head">
                <h3
                  id="confirm-guide-tracks-label"
                  className="workspace-hifi__confirm-guide-section-title"
                >
                  想准备的赛道
                </h3>
                <span className="workspace-hifi__confirm-guide-section-hint">
                  AI 已根据简历预先勾选, 你可以加 / 减
                </span>
              </header>
              <div className="workspace-hifi__confirm-guide-chips">
                {TRACKS.map((t) => {
                  const checked = selectedTracks.includes(t.key);
                  const inferred = inferredSet.has(t.key);
                  return (
                    <button
                      key={t.key}
                      type="button"
                      role="checkbox"
                      aria-checked={checked}
                      className={`workspace-hifi__confirm-guide-chip${
                        checked ? ' is-checked' : ''
                      }`}
                      onClick={() => toggleTrack(t.key)}
                      disabled={busy}
                      title={t.blurb}
                    >
                      <span className="workspace-hifi__confirm-guide-chip-icon" aria-hidden>
                        {t.icon}
                      </span>
                      <span className="workspace-hifi__confirm-guide-chip-label">
                        {t.label}
                      </span>
                      {inferred && (
                        <span
                          className="workspace-hifi__confirm-guide-chip-badge"
                          aria-label="AI 从简历推断"
                          title="AI 从你的简历推断的赛道"
                        >
                          AI
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </section>

            <section
              className="workspace-hifi__confirm-guide-section"
              aria-labelledby="confirm-guide-locations-label"
            >
              <header className="workspace-hifi__confirm-guide-section-head">
                <h3
                  id="confirm-guide-locations-label"
                  className="workspace-hifi__confirm-guide-section-title"
                >
                  目标城市
                </h3>
                <span className="workspace-hifi__confirm-guide-section-hint">
                  默认勾选北京 + 上海 — 加多个城市推荐会更全
                </span>
              </header>
              <div className="workspace-hifi__confirm-guide-chips">
                {COMMON_LOCATIONS.map((loc) => {
                  const checked = selectedLocations.includes(loc);
                  return (
                    <button
                      key={loc}
                      type="button"
                      role="checkbox"
                      aria-checked={checked}
                      className={`workspace-hifi__confirm-guide-chip workspace-hifi__confirm-guide-chip--loc${
                        checked ? ' is-checked' : ''
                      }`}
                      onClick={() => toggleLocation(loc)}
                      disabled={busy}
                    >
                      <span className="workspace-hifi__confirm-guide-chip-label">
                        {loc}
                      </span>
                    </button>
                  );
                })}
              </div>
            </section>
          </>
        )}

        {submitError ? (
          <div className="workspace-hifi__confirm-guide-error" role="alert">
            出错了:{submitError}
          </div>
        ) : null}

        <div className="workspace-hifi__confirm-guide-actions">
          <button
            type="button"
            className="workspace-hifi__confirm-guide-btn workspace-hifi__confirm-guide-btn--primary"
            onClick={handleConfirm}
            disabled={busy || !canSubmit}
            title={
              !canSubmit && fetchState.kind === 'ready'
                ? '请至少选一个赛道 + 一个城市'
                : undefined
            }
          >
            {busy ? '处理中…' : '✅ 确认进入工作台'}
          </button>
          <a
            href="/upload"
            className="workspace-hifi__confirm-guide-btn"
          >
            ✎ 去 /upload 详细看 + 改
          </a>
        </div>
      </div>
    </div>
  );
}


function ParsedPreview({ profile }: { profile: ResumeProfilePayload }) {
  const name = profile.basic_info?.name || profile.basic_info?.full_name || '(未识别)';
  const headline = profile.basic_info?.headline || '';
  const eduCount = profile.education?.length || 0;
  const eduFirst = eduCount > 0 ? profile.education[0] : null;
  const internships = profile.internships || [];
  const projects = profile.projects || [];
  const skillsTechnical = profile.skills?.technical || [];
  const skillsTools = profile.skills?.tools || [];
  const skillCount = skillsTechnical.length + skillsTools.length;
  const summary = (profile.candidate_summary || '').trim();
  const summarySnippet = summary.length > 110 ? summary.slice(0, 110) + '…' : summary;

  return (
    <dl className="workspace-hifi__confirm-guide-preview">
      <PreviewRow label="姓名" value={name} />
      {eduFirst ? (
        <PreviewRow
          label="学校"
          value={`${eduFirst.school || '(未识别)'} · ${eduFirst.degree || ''} ${eduFirst.major || ''}`.trim()}
          extra={eduCount > 1 ? `+${eduCount - 1} 段` : undefined}
        />
      ) : (
        <PreviewRow label="学校" value="(未识别)" />
      )}
      <PreviewRow
        label={`实习经历 (${internships.length} 段)`}
        value={internships.length === 0 ? '(无)' : ''}
      >
        {internships.length > 0 ? (
          <ul className="workspace-hifi__confirm-guide-preview-list">
            {internships.map((it, i) => (
              <li key={i}>
                {it.company || '(未识别)'}
                {it.role ? ` · ${it.role}` : ''}
              </li>
            ))}
          </ul>
        ) : null}
      </PreviewRow>
      {projects.length > 0 ? (
        <PreviewRow label={`项目经历 (${projects.length} 段)`} value="">
          <ul className="workspace-hifi__confirm-guide-preview-list">
            {projects.map((p, i) => (
              <li key={i}>{p.name || p.role || '(未识别)'}</li>
            ))}
          </ul>
        </PreviewRow>
      ) : null}
      <PreviewRow
        label="技能"
        value={skillCount === 0 ? '(无)' : `${skillCount} 项`}
        extra={skillCount > 0 ? [...skillsTechnical, ...skillsTools].slice(0, 4).join(' / ') + (skillCount > 4 ? ' …' : '') : undefined}
      />
      {headline ? <PreviewRow label="目标 / Headline" value={headline} /> : null}
      {summarySnippet ? <PreviewRow label="个人介绍" value={summarySnippet} /> : null}
    </dl>
  );
}


function PreviewRow({
  label,
  value,
  extra,
  children,
}: {
  label: string;
  value: string;
  extra?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="workspace-hifi__confirm-guide-preview-row">
      <dt>{label}</dt>
      <dd>
        {value}
        {extra ? (
          <span className="workspace-hifi__confirm-guide-preview-extra"> · {extra}</span>
        ) : null}
        {children}
      </dd>
    </div>
  );
}
