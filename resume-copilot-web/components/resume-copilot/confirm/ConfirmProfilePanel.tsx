'use client';

/**
 * ConfirmProfilePanel — main shell for `/resume-copilot/confirm`.
 *
 * P2 (2026-05-26): replaces the in-workspace `WorkspaceConfirmGuide` overlay.
 * After upload + parse, the student lands here to verify the parsed resume,
 * pick a track, and pick target cities — then "确认进入工作台" submits
 * everything in one go and redirects to `/resume-copilot?sessionId=N`.
 *
 * Layout:
 *   .hf .rc-confirm
 *     mini topbar (HFLogo + 步骤 2/3 指示)
 *     header (file icon + h2 + subtitle)
 *     body (max-width 880)
 *       <ResumeSummaryCard/>
 *       <TrackBlock/>
 *       <CityBlock/>
 *       actions ("确认进入工作台" primary + "去 /upload 详细看 + 改" ghost)
 *       footnote
 *
 * Data flow:
 *   Mount → parallel GET /parsed-profile + GET /preferences
 *   Pre-seed selectedTrack from preferences.preferred_tracks[0] (fallback to
 *   profile.inferred_tracks[0] mapped to canonical TRACKS keys)
 *   Pre-seed selectedCities from preferences.preferred_locations (fallback to
 *   inferred_offices → city mapping, fallback to ['北京', '上海'])
 *   On confirm → PUT /preferences + PUT /confirmed-profile → router.push
 *   (workspace) → `has_confirmed_profile === true` so workspace doesn't
 *   redirect back here.
 *
 * `_assert_not_demo` is enforced server-side. We never call PUT for the demo
 * session (id 1) — `useEffect` short-circuits with an error banner.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';

import { HFBtn, HFLogo, I } from '@/components/hifi/hifi-primitives';
import {
  DEMO_SESSION_ID,
  getResumeCopilotParsedProfile,
  getResumeCopilotPreferences,
  postResumeCopilotGenerate,
  putResumeCopilotConfirmedProfile,
  putResumeCopilotPreferences,
} from '../api';
import {
  EMPTY_PREFERENCES,
  type ResumePreferencePayload,
  type ResumeProfilePayload,
} from '../types';
import { TRACKS } from '../workspace/TrackPickerModal';

import { ResumeSummaryCard } from './ResumeSummaryCard';
import { TrackBlock } from './TrackBlock';
import { CityBlock } from './CityBlock';

import './confirm-theme.css';

// Default city pre-selection when parser hasn't inferred anything specific.
const DEFAULT_CITIES = ['北京', '上海'];

// parser-inferred office region → which cities to pre-tick.
const OFFICE_TO_CITIES: Record<string, string[]> = {
  hk: ['香港'],
  sg: ['新加坡'],
  mainland: ['北京', '上海'],
  global: ['香港', '新加坡', '上海'],
};

// 从简历 education 取最晚一段的毕业时间, 归一成 YYYY-MM (给 <input type=month>)。
// 抠不出 (含 至今/Present) → 返 ''。
function latestGradDate(profile: ResumeProfilePayload): string {
  let best = '';
  for (const edu of profile.education ?? []) {
    const end = (edu?.end_date ?? '').trim();
    const m = end.match(/(\d{4})\s*[.\-/年]?\s*(\d{1,2})?/);
    if (!m) continue;
    const ym = `${m[1]}-${String(m[2] ? Number(m[2]) : 6).padStart(2, '0')}`;
    if (ym > best) best = ym;
  }
  return best;
}

// 前端镜像 backend job_mode.infer_stage_from_education 的阈值, 用于毕业时间→阶段
// 的即时预选 (后端仍是判定权威; 这里只为 UX 默认勾选)。
function deriveStage(gradYM: string): string {
  const m = gradYM.match(/^(\d{4})-(\d{1,2})$/);
  if (!m) return '';
  const now = new Date();
  const months =
    (Number(m[1]) - now.getFullYear()) * 12 + (Number(m[2]) - (now.getMonth() + 1));
  if (months < 0) return 'graduated';
  if (months <= 13) return 'fresh_grad';
  return 'in_school';
}

type FetchState =
  | { kind: 'loading' }
  | {
      kind: 'ready';
      profile: ResumeProfilePayload;
      preferences: ResumePreferencePayload;
    }
  | { kind: 'error'; message: string };

export interface ConfirmProfilePanelProps {
  sessionId: number;
}

export function ConfirmProfilePanel({ sessionId }: ConfirmProfilePanelProps) {
  const router = useRouter();
  const isDemo = sessionId === DEMO_SESSION_ID;

  const [fetchState, setFetchState] = useState<FetchState>({ kind: 'loading' });
  const [selectedTrack, setSelectedTrack] = useState<string | null>(null);
  const [selectedCities, setSelectedCities] = useState<string[]>(DEFAULT_CITIES);
  // Phase G G2-B — 学生阶段 (在读/应届/已毕业); 后端按毕业时间预填, 学生可改
  const [selectedStage, setSelectedStage] = useState<string>('');
  // Phase G — 学生确认的预计毕业时间 (YYYY-MM); 改它会即时重算建议阶段
  const [gradDate, setGradDate] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Canonical track-key set for validation against AI-inferred values.
  const validTrackKeys = useMemo(() => new Set(TRACKS.map((t) => t.key)), []);

  // Inferred-set (for chip "AI" badge on the active selection).
  const inferredKeys = useMemo(() => {
    if (fetchState.kind !== 'ready') return new Set<string>();
    return new Set(
      (fetchState.profile.inferred_tracks ?? []).filter((k) => validTrackKeys.has(k)),
    );
  }, [fetchState, validTrackKeys]);

  const inferredOffices = useMemo(() => {
    if (fetchState.kind !== 'ready') return [];
    return (fetchState.profile.inferred_offices ?? []).filter(Boolean);
  }, [fetchState]);

  // ── Mount: parallel fetch profile + preferences, then seed selections ────
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [parsed, prefs] = await Promise.all([
          getResumeCopilotParsedProfile(sessionId),
          getResumeCopilotPreferences(sessionId).catch(() => null),
        ]);
        if (cancelled) return;
        if (!parsed?.profile) {
          setFetchState({
            kind: 'error',
            message: 'parser 没返回 profile, 解析可能还没完成。',
          });
          return;
        }
        const preferences = prefs?.preferences ?? EMPTY_PREFERENCES;
        setFetchState({ kind: 'ready', profile: parsed.profile, preferences });

        // ── Seed 毕业时间 + 阶段 ─────────────────────────────────────────
        // 毕业时间: 学生上次确认的 > 简历解析的最晚毕业时间
        const seededGrad =
          (preferences.graduation_date ?? '').trim() || latestGradDate(parsed.profile);
        setGradDate(seededGrad);
        // 阶段: 学生上次显式选的 > 由毕业时间即时推导 (后端仍是判定权威)
        setSelectedStage(
          (preferences.job_stage ?? '').trim() || deriveStage(seededGrad),
        );

        // ── Seed selectedTrack ─────────────────────────────────────────
        // 1. preferences.preferred_tracks[0] (if valid canonical key)
        // 2. profile.inferred_tracks[0] (first valid)
        // 3. null (student must pick)
        const valid = new Set(TRACKS.map((t) => t.key));
        const fromPrefs = (preferences.preferred_tracks ?? []).find((k) => valid.has(k));
        if (fromPrefs) {
          setSelectedTrack(fromPrefs);
        } else {
          const fromInferred = (parsed.profile.inferred_tracks ?? []).find((k) =>
            valid.has(k),
          );
          if (fromInferred) setSelectedTrack(fromInferred);
        }

        // ── Seed selectedCities ────────────────────────────────────────
        // 1. preferences.preferred_locations (if non-empty)
        // 2. office-inferred prefill
        // 3. DEFAULT_CITIES (北京 + 上海)
        const fromPrefLocs = preferences.preferred_locations ?? [];
        if (fromPrefLocs.length > 0) {
          setSelectedCities(fromPrefLocs);
        } else {
          const offices = (parsed.profile.inferred_offices ?? []).filter(
            (o) => o in OFFICE_TO_CITIES,
          );
          if (offices.length > 0) {
            const prefilled = new Set<string>();
            for (const off of offices) {
              (OFFICE_TO_CITIES[off] ?? []).forEach((c) => prefilled.add(c));
            }
            if (prefilled.size > 0) setSelectedCities(Array.from(prefilled));
          }
        }
      } catch (e) {
        if (cancelled) return;
        setFetchState({
          kind: 'error',
          message: e instanceof Error ? e.message : String(e),
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  // ── Toggle handlers ─────────────────────────────────────────────────────
  const toggleCity = useCallback((city: string) => {
    setSelectedCities((prev) =>
      prev.includes(city) ? prev.filter((c) => c !== city) : [...prev, city],
    );
  }, []);

  // ── Confirm handler ─────────────────────────────────────────────────────
  const canSubmit =
    fetchState.kind === 'ready' &&
    !!selectedTrack &&
    selectedCities.length > 0 &&
    !isDemo;

  const handleConfirm = useCallback(async () => {
    if (fetchState.kind !== 'ready') return;
    if (isDemo) {
      setSubmitError('demo 会话只读 — 请先用自己的简历开新会话。');
      return;
    }
    if (!selectedTrack) {
      setSubmitError('请至少选一个想准备的赛道。');
      return;
    }
    if (selectedCities.length === 0) {
      setSubmitError('请至少选一个目标城市。');
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      // 1. Persist preferences (赛道 + 城市) so /generate downstream uses them.
      await putResumeCopilotPreferences(sessionId, {
        ...fetchState.preferences,
        preferred_tracks: [selectedTrack],
        preferred_locations: selectedCities,
        job_stage: selectedStage,
        graduation_date: gradDate,
        all_skipped: false,
      });
      // 2. Persist confirmed-profile — flips has_confirmed_profile=true and
      //    enables /generate (PUT itself does not auto-trigger the run).
      await putResumeCopilotConfirmedProfile(sessionId, fetchState.profile);
      // 3. Kick off the recommendation run so the workspace lands on a
      //    `recommendation_status=running` session (~20s) instead of cold.
      //    Matches the legacy WorkspaceConfirmGuide.handleConfirm flow.
      await postResumeCopilotGenerate(sessionId);
      // 4. Redirect to workspace. WorkspaceShell will NOT bounce back because
      //    has_confirmed_profile is now true.
      router.push(`/resume-copilot?sessionId=${sessionId}`);
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : String(e));
      setSubmitting(false);
    }
  }, [fetchState, isDemo, router, sessionId, selectedCities, selectedTrack, selectedStage, gradDate]);

  const handleBackToUpload = useCallback(() => {
    router.push('/upload');
  }, [router]);

  // ── Render ──────────────────────────────────────────────────────────────
  return (
    <div className="hf">
      <div className="rc-confirm" data-testid="rc-confirm-panel">
        {/* Mini topbar */}
        <div className="rc-confirm__topbar">
          <HFLogo size="sm" />
          <div className="rc-confirm__topbar-spacer" />
          <span className="rc-confirm__step-indicator">
            <span className="rc-confirm__step-dots">○●○</span> · 步骤 2 / 3 · 解析确认
          </span>
        </div>

        {/* Header */}
        <div className="rc-confirm__header">
          <div className="rc-confirm__file-icon" aria-hidden>
            {I.file(28)}
          </div>
          <h2 className="rc-confirm__title">AI 已解析你的简历</h2>
          <p className="rc-confirm__subtitle">
            看一眼下面三块都对得上吗 —{' '}
            <strong>解析的简历 / 想准备的赛道 / 目标城市</strong>, 一次确认我就按你的意图出第一批推荐。
          </p>
        </div>

        {/* Body */}
        <div className="rc-confirm__body">
          {fetchState.kind === 'loading' ? (
            <div className="rc-confirm__state" aria-busy="true">
              <span className="hf-spin" aria-hidden /> 解析中…
            </div>
          ) : fetchState.kind === 'error' ? (
            <div className="rc-confirm__error" role="alert">
              读取 parser 结果出错: {fetchState.message}
            </div>
          ) : (
            <>
              <ResumeSummaryCard profile={fetchState.profile} />
              <TrackBlock
                activeTrackKey={selectedTrack}
                onChange={setSelectedTrack}
                inferredKeys={inferredKeys}
                disabled={submitting}
              />
              <CityBlock
                selectedCities={selectedCities}
                onToggleCity={toggleCity}
                inferredOffices={inferredOffices}
                disabled={submitting}
              />
              {/* Phase G G2-B/G2-grad — 毕业时间 + 阶段 (驱动主推实习/全职/both) */}
              <div className="rc-confirm__stage-block">
                <div className="rc-confirm__stage-head">
                  <span className="rc-confirm__stage-title">毕业时间与阶段</span>
                  <span className="rc-confirm__stage-hint">
                    确认毕业时间，我据此判断主推实习还是全职
                  </span>
                </div>
                <div className="rc-confirm__grad-row">
                  <label className="rc-confirm__grad-label" htmlFor="rc-grad-date">
                    预计毕业时间
                  </label>
                  <input
                    id="rc-grad-date"
                    type="month"
                    className="rc-confirm__grad-input"
                    value={gradDate}
                    disabled={submitting}
                    onChange={(e) => {
                      const v = e.target.value;
                      setGradDate(v);
                      // 改毕业时间 → 即时重算建议阶段 (学生随后仍可手动覆盖)
                      const d = deriveStage(v);
                      if (d) setSelectedStage(d);
                    }}
                  />
                  {!gradDate && (
                    <span className="rc-confirm__grad-warn">
                      简历没解析出毕业时间，请补一下
                    </span>
                  )}
                </div>
                <div className="rc-confirm__stage-options" role="radiogroup" aria-label="求职阶段">
                  {[
                    { v: 'in_school', label: '在读', sub: '距毕业一年以上' },
                    { v: 'fresh_grad', label: '应届', sub: '今年毕业找全职' },
                    { v: 'graduated', label: '已毕业', sub: '走全职/社招' },
                  ].map((opt) => (
                    <button
                      key={opt.v}
                      type="button"
                      role="radio"
                      aria-checked={selectedStage === opt.v}
                      className={`rc-confirm__stage-opt${selectedStage === opt.v ? ' is-active' : ''}`}
                      onClick={() => setSelectedStage(opt.v)}
                      disabled={submitting}
                    >
                      <span className="rc-confirm__stage-opt-label">{opt.label}</span>
                      <span className="rc-confirm__stage-opt-sub">{opt.sub}</span>
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}

          {submitError ? (
            <div className="rc-confirm__error" role="alert">
              出错了: {submitError}
            </div>
          ) : null}

          {/* CTAs — only show after fetch succeeds (otherwise no track / no profile to submit) */}
          {fetchState.kind === 'ready' && (
            <>
              <div className="rc-confirm__actions">
                <HFBtn
                  variant="primary"
                  size="lg"
                  icon={I.check(15)}
                  onClick={handleConfirm}
                  disabled={submitting || !canSubmit}
                  title={
                    !canSubmit && !isDemo
                      ? '请至少选一个赛道 + 一个城市'
                      : isDemo
                      ? 'demo 会话只读'
                      : undefined
                  }
                >
                  {submitting ? '处理中…' : '确认进入工作台'}
                </HFBtn>
                <HFBtn
                  variant="ghost"
                  size="lg"
                  icon={I.edit(14)}
                  onClick={handleBackToUpload}
                  disabled={submitting}
                >
                  去 /upload 详细看 + 改
                </HFBtn>
              </div>
              <div className="rc-confirm__footnote">
                确认后会跑约 20 秒生成 Top 推荐 · 之后可随时在工作台右上角重选赛道
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
