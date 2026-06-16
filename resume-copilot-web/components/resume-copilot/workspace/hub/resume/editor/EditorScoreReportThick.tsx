'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { JSX, ReactNode } from 'react';
import { History, RotateCw } from 'lucide-react';
import { HubRadar, type RadarDatum } from '../HubRadar';
import {
  getScoreTaskStatus,
  startScoreTask,
  type ScoreReportData,
  type ScoreSectionGap,
} from '../../../../api';
import type { ResumeProfile } from './resumeSample';
import { cacheScoreReport, readFreshScoreReport } from '../../scoreCache';

// 8 维 → 雷达短标签 + 金融维标记(对齐 ResumeScorePanel / ScoreReport 顺序)。
const DIM_META: { key: string; radarLabel: string; fin?: boolean }[] = [
  { key: 'logic', radarLabel: '逻辑' },
  { key: 'star', radarLabel: 'STAR' },
  { key: 'readability', radarLabel: '可读' },
  { key: 'completeness', radarLabel: '完整' },
  { key: 'expression', radarLabel: '表达' },
  { key: 'quantification', radarLabel: '量化' },
  { key: 'track_fit', radarLabel: '匹配度', fin: true },
  { key: 'defensibility', radarLabel: '佐证', fin: true },
];
const SURFACE_KEYS = ['logic', 'star', 'readability', 'completeness', 'expression', 'quantification'];
const FIN_KEYS = ['track_fit', 'defensibility'];

// 现状样例(无 session 时用,沿用 ResumeScorePanel 的 MOCK shape)。
const MOCK: ScoreReportData = {
  session_id: 0,
  target_track: '量化私募 · 研究',
  overall_current: 72,
  overall_potential_low: 80,
  overall_potential_high: 85,
  summary:
    '整体框架与表达不错,但成果量化与 STAR 的 Result 段是明显短板。把真实细节经反问取证补齐后,可达 80–85,绝不靠编造刷分。',
  dimensions: [
    { key: 'logic', name: '逻辑清晰', score: 78, ceiling: 86, reason: '经历排布有主线,部分项目仍缺一句话点题。' },
    { key: 'star', name: 'STAR 应用', score: 58, ceiling: 84, reason: '多数 bullet 停在 Action,Result 缺失或含糊。' },
    { key: 'readability', name: '内容可读', score: 84, ceiling: 88, reason: '排版与措辞清爽,信息密度合适。' },
    { key: 'completeness', name: '内容完整', score: 70, ceiling: 80, reason: '技能栈完整,但部分实习缺时间/角色锚点。' },
    { key: 'expression', name: '专业表达', score: 80, ceiling: 86, reason: '术语使用准确,个别动词偏弱。' },
    { key: 'quantification', name: '成果量化', score: 52, ceiling: 82, reason: '关键成果普遍无数字锚点,难以体现影响力。' },
    { key: 'track_fit', name: '赛道匹配度', score: 64, ceiling: 82, reason: '与量化研究相关,但因子/回测细节露出不足。' },
    { key: 'defensibility', name: '佐证充分度', score: 55, ceiling: 80, reason: '声明缺少可追问的过程证据,易被面试官问空。' },
  ],
  section_gaps: [
    {
      section: 'internships.0',
      label: '九坤投资 · 量化研究实习',
      gaps: ['STAR 缺 Result', '佐证不足'],
      detail: '描述了在做什么因子研究,但没有写出结果指标(IC / 夏普 / 回撤改善),也缺少可追问的方法细节。',
    },
    {
      section: 'projects.1',
      label: '校园量化策略项目',
      gaps: ['成果无量化锚点'],
      detail: '策略收益、回测区间、对照基准都没写,读者无法判断这段经历的真实分量。',
    },
  ],
  used_ai: false,
};

/** fillClass 移植自 ScoreReport.tsx,用 .hf token 表达:
 *  >=75 强(terracotta-strong) / >=65 中(terracotta) / 其余 低(coral 浅)。 */
function fillColor(score: number): string {
  if (score >= 75) return 'var(--terracotta-strong)';
  if (score >= 65) return 'var(--terracotta)';
  return 'var(--coral)';
}

function finMeta(key: string, targetTrack: string): string {
  if (key === 'track_fit') return `这段经历对「${targetTrack || '目标赛道'}」的对口程度`;
  if (key === 'defensibility') return '声明是否有足够支撑、经得起面试官追问';
  return '';
}

export interface EditorScoreReportThickProps {
  sessionId: number;
  /** 逐段缺口 CTA「去深度优化这段」点击回调;带上当前目标赛道,供深度优化锁定 subcat。 */
  onOptimize: (gap: ScoreSectionGap, targetTrack: string) => void;
  /** 无 session 时渲染样例。 */
  mock?: boolean;
  // ── 版本对应 + 重新打分(由 ResumeEditorOverlay 上提)──────────────────────
  /** 外部指定要展示的报告(选中某版本 / 重新打分后的结果)。传了就用它、跳过自动轮询。 */
  reportOverride?: ScoreReportData | null;
  /** 打分面板当前展示的是哪一版的报告(版本名,如 'V2')。 */
  shownVName?: string;
  /** 当前编辑中的版本名(如 'V3')。 */
  currentVName?: string;
  /** 展示报告版本 ≠ 当前版本 → 横幅转琥珀、重新打分高亮。 */
  stale?: boolean;
  /** 当前版本的简历快照 —— 重新打分就给它打。 */
  currentProfile?: ResumeProfile;
  /** 当前目标赛道(重新打分透传)。 */
  targetTrack?: string;
  /** 重新打分跑出报告 → 回调父组件:盖到当前版本上。 */
  onRescored?: (report: ScoreReportData) => void;
}

/** 简历打分「厚版」报告 — 编辑器全屏右栏「简历打分」tab 用。
 *  相较紧凑侧栏面板,这一版多出:潜力进度条 + 逐维 fill bar + reason + 金融维标注。
 *  只读:仅 scoreResume + onOptimize 回调,不接深度优化/chat(那是 E3)。 */
export function EditorScoreReportThick({
  sessionId,
  onOptimize,
  mock = false,
  reportOverride,
  shownVName,
  currentVName,
  stale = false,
  // currentProfile 不再用于打分(编辑器渲染模型 ≠ 后端 ResumeProfilePayload, 传了会被当空简历)。
  // 重新打分一律打库里 confirmed 简历;prop 保留在接口上供将来"渲染模型→payload"转换接入。
  targetTrack,
  onRescored,
}: EditorScoreReportThickProps): JSX.Element {
  const [polledReport, setPolledReport] = useState<ScoreReportData | null>(mock ? MOCK : null);
  const [loading, setLoading] = useState(!mock);
  const [stageNote, setStageNote] = useState('');
  const [error, setError] = useState('');
  // 重新打分(给当前版本的快照打)进行中。
  const [rescoring, setRescoring] = useState(false);
  const rescorePoll = useRef<number | undefined>(undefined);

  // 父组件接管了版本/报告(传了 reportOverride)→ 直接展示它,不再自动轮询。
  // 这是「版本对应」开启后的常态路径:每个版本的报告由 overlay 持有。
  const controlled = reportOverride !== undefined;
  const shownReport = controlled ? reportOverride : polledReport;

  useEffect(() => {
    if (controlled) return; // 受控:报告由父组件给
    if (mock || !sessionId) return;
    // 与打分报告面板同一套「看表」逻辑: 对话/面板已打过的分直接复用(本地缓存 /
    // 服务端任务缓存), 在跑的轮询真实阶段, 都没有才自己起后台任务 ——
    // 不再每次进编辑器同步重打一遍 LLM(90s 超时报错的根因)。
    let alive = true;
    let timer: number | undefined;
    let startedOnce = false;
    const cached = readFreshScoreReport(sessionId);
    if (cached) {
      Promise.resolve().then(() => {
        if (!alive) return;
        setPolledReport(cached);
        setError('');
        setLoading(false);
      });
      return () => { alive = false; };
    }
    const poll = async () => {
      try {
        const st = await getScoreTaskStatus(sessionId);
        if (!alive) return;
        if (st.status === 'done' && st.report) {
          cacheScoreReport(sessionId, st.report);
          setPolledReport(st.report);
          setError('');
          setLoading(false);
          return;
        }
        if (st.status === 'running') {
          setStageNote(
            st.stage === 'llm'
              ? `评审模型工作中 · 已 ${Math.round(st.elapsed_seconds ?? 0)}s`
              : st.stage === 'parse'
                ? '正在整理维度与缺口…'
                : '准备打分材料…',
          );
          timer = window.setTimeout(() => void poll(), 2500);
          return;
        }
        if (st.status === 'failed' && startedOnce) {
          setError(st.error || '打分没跑成,稍后再试');
          setLoading(false);
          return;
        }
        startedOnce = true;
        await startScoreTask(sessionId, {});
        timer = window.setTimeout(() => void poll(), 2000);
      } catch (e) {
        if (alive) {
          setError(e instanceof Error ? e.message : '打分失败');
          setLoading(false);
        }
      }
    };
    void poll();
    return () => {
      alive = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [mock, sessionId, controlled]);

  // 重新打分:给「当前版本」的快照打分(profile 覆盖 + force),轮询到 done → 回调父组件盖版。
  const handleRescore = useCallback(() => {
    if (rescoring) return;
    if (mock || !sessionId) {
      // 离线目测:本地造一份「与展示一致」的报告即可,主要给设计走查。
      const base = shownReport ?? MOCK;
      onRescored?.({ ...base });
      return;
    }
    setRescoring(true);
    const poll = async () => {
      try {
        const st = await getScoreTaskStatus(sessionId);
        if (st.status === 'done' && st.report) {
          cacheScoreReport(sessionId, st.report);
          onRescored?.(st.report);
          setRescoring(false);
          return;
        }
        if (st.status === 'failed') {
          setError(st.error || '重新打分没跑成,稍后再试');
          setRescoring(false);
          return;
        }
        rescorePoll.current = window.setTimeout(() => void poll(), 2500);
      } catch (e) {
        setError(e instanceof Error ? e.message : '重新打分失败');
        setRescoring(false);
      }
    };
    // 打库里那份完整简历(force 重打)。注意:不能把编辑器的"渲染模型"(name/sections/…)
    // 当 profile 覆盖传后端 —— 后端要的是 ResumeProfilePayload(education/internships/projects),
    // 形态不同会被解析成空简历 → "简历完全空白 0 分"(实测 cz9z 的 V1=0 即此因)。
    // 深度优化写回会落到后端简历,所以打库里这份即当前内容。
    startScoreTask(sessionId, { targetTrack: targetTrack ?? '', force: true })
      .then(() => {
        rescorePoll.current = window.setTimeout(() => void poll(), 1500);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : '重新打分失败');
        setRescoring(false);
      });
  }, [rescoring, mock, sessionId, shownReport, onRescored, targetTrack]);

  useEffect(() => () => {
    if (rescorePoll.current) window.clearTimeout(rescorePoll.current);
  }, []);

  // 首进编辑器:当前版本还没打分(受控且 reportOverride===null)→ 自动给库里完整简历打一次真分,
  // 不传 profile 覆盖 → 打的是后端 confirmed 简历(完整),不会出现"空白简历 0 分"。打完由
  // onRescored 落进当前版本并持久化,下次进来直接复用、不再重打。
  const autoScored = useRef(false);
  useEffect(() => {
    if (!controlled || reportOverride !== null) return;
    if (mock || !sessionId) return;
    if (autoScored.current || rescoring) return;
    autoScored.current = true;
    // 异步触发,避免在 effect 内同步 setState(setRescoring)。
    const t = window.setTimeout(() => handleRescore(), 0);
    return () => window.clearTimeout(t);
  }, [controlled, reportOverride, mock, sessionId, rescoring, handleRescore]);

  // 受控态:报告由父组件给。loading/error 仅在非受控自动轮询路径展示。
  if (!controlled && loading) {
    return (
      <div style={{ padding: 40, color: 'var(--stone)', font: '400 13px var(--font-sans)' }}>
        打分中… {stageNote && <span style={{ color: 'var(--olive)' }}>{stageNote}</span>}
      </div>
    );
  }
  if (!controlled && error) {
    return (
      <div style={{ padding: 40, color: 'var(--terracotta-strong)', font: '400 13px var(--font-sans)' }}>
        打分失败:{error}
      </div>
    );
  }

  // 版本横幅 —— 即使当前版本「未打分」也要露出(配重新打分按钮)。
  // 受控态没有可展示报告时,只渲染横幅 + 空态提示。
  const banner =
    controlled && (shownVName || currentVName) ? (
      <VersionBanner
        stale={stale}
        shownVName={shownVName}
        currentVName={currentVName}
        rescoring={rescoring}
        onRescore={handleRescore}
        error={error}
      />
    ) : null;

  if (!shownReport) {
    return (
      <div style={{ overflow: 'auto', height: '100%', background: 'var(--parchment)' }}>
        <div style={{ maxWidth: 720, margin: '0 auto', padding: '20px 22px 28px' }}>
          {banner}
          <div
            style={{
              padding: '40px 16px',
              textAlign: 'center',
              color: 'var(--stone)',
              font: '400 13px/1.6 var(--font-sans)',
            }}
          >
            这一版还没打分。点上方「重新打分」给当前版本算一份报告。
          </div>
        </div>
      </div>
    );
  }
  const report = shownReport;

  const dimByKey = new Map(report.dimensions.map((d) => [d.key, d]));
  const radarData: RadarDatum[] = DIM_META.map((m) => ({
    k: m.radarLabel,
    fin: m.fin,
    v: dimByKey.get(m.key)?.score ?? 0,
  }));

  const current = report.overall_current;
  const gain = Math.max(0, report.overall_potential_high - current);

  return (
    <div style={{ overflow: 'auto', height: '100%', background: 'var(--parchment)' }}>
      <div style={{ maxWidth: 720, margin: '0 auto', padding: '20px 22px 28px' }}>
        {/* 目标赛道 + 现状/潜力 + 顶部小雷达 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
          <span className="hf-overline" style={{ fontSize: 9.5 }}>目标赛道</span>
          <span className="hf-pill terra" style={{ height: 26 }}>{report.target_track || '未指定'}</span>
        </div>

        {/* 版本对应 + 重新打分横幅(版本不一致 → 琥珀 + 按钮高亮) */}
        {banner}

        <div className="hf-card" style={{ padding: 16, marginBottom: 16 }}>
          {/* 现状 + 潜力 一行(雷达不再挤这行,改放独立一行,窄栏才不塌) */}
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16 }}>
            <div style={{ flex: 'none' }}>
              <div style={{ font: '500 52px/0.86 var(--font-mono)', color: 'var(--ink)', letterSpacing: '-0.03em', whiteSpace: 'nowrap' }}>
                {current}<span style={{ fontSize: 18, color: 'var(--stone)', marginLeft: 3 }}>分</span>
              </div>
              <div style={{ font: '500 11.5px var(--font-sans)', color: 'var(--olive)', marginTop: 7, whiteSpace: 'nowrap' }}>
                现状分 · 老实反映当前简历
              </div>
            </div>

            {/* 潜力进度条:现状填充 + 潜力增益(斜纹浅段) */}
            <div style={{ flex: 1, minWidth: 0, borderLeft: '1px solid var(--border-warm)', paddingLeft: 16 }}>
              <div style={{ font: '600 16px var(--font-mono)', color: 'var(--terracotta-strong)', whiteSpace: 'nowrap' }}>
                潜力 {report.overall_potential_low}–{report.overall_potential_high}
              </div>
              <div
                style={{
                  position: 'relative', height: 7, borderRadius: 'var(--r-pill)',
                  background: 'var(--warm-sand)', overflow: 'hidden', margin: '7px 0 6px',
                }}
              >
                <div
                  style={{
                    position: 'absolute', left: 0, top: 0, height: '100%', width: `${current}%`,
                    borderRadius: 'var(--r-pill)', background: 'var(--ink-soft)',
                  }}
                />
                <div
                  style={{
                    position: 'absolute', top: 0, height: '100%', left: `${current}%`, width: `${gain}%`,
                    opacity: 0.5,
                    background:
                      'repeating-linear-gradient(45deg, var(--terracotta) 0 4px, transparent 4px 8px)',
                  }}
                />
              </div>
              <div style={{ font: '400 11.5px/1.5 var(--font-sans)', color: 'var(--stone)' }}>
                把下列缺口经反问取证如实补齐后可达,不靠编造
              </div>
            </div>
          </div>

          {/* 雷达 — 独立一行居中,不再和分数抢宽 */}
          <div style={{ display: 'flex', justifyContent: 'center', marginTop: 16 }}>
            <div
              style={{
                background: 'var(--ivory)', borderRadius: 'var(--r-lg)',
                boxShadow: 'var(--sh-ring)', padding: 12,
              }}
            >
              <HubRadar size={188} data={radarData} />
            </div>
          </div>

          {report.summary && (
            <p style={{ margin: '14px 0 0', font: '400 13.5px/1.65 var(--font-sans)', color: 'var(--ink-soft)' }}>
              {report.summary}
            </p>
          )}
        </div>

        {/* 6 表层维 — 逐维 fill bar + reason */}
        <DimsLabel>6 表层维</DimsLabel>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 18 }}>
          {SURFACE_KEYS.map((key) => {
            const d = dimByKey.get(key);
            if (!d) return null;
            return <DimRow key={key} name={d.name} score={d.score} reason={d.reason} />;
          })}
        </div>

        {/* 2 金融独有维 — terracotta 标注 */}
        <DimsLabel>2 金融独有维</DimsLabel>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 18 }}>
          {FIN_KEYS.map((key) => {
            const d = dimByKey.get(key);
            if (!d) return null;
            return (
              <DimRow
                key={key}
                name={d.name}
                score={d.score}
                reason={d.reason}
                meta={finMeta(key, report.target_track)}
                fin
              />
            );
          })}
        </div>

        {/* 逐段缺口 · 深度优化入口 */}
        <DimsLabel>逐段缺口 · 深度优化入口</DimsLabel>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {report.section_gaps.map((g, i) => (
            <div
              key={g.section || i}
              className="hf-card"
              style={{ padding: '14px 16px', boxShadow: 'var(--sh-whisper), var(--sh-ring)' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                <span style={{ font: '700 13.5px var(--font-sans)', color: 'var(--ink)' }}>
                  {g.label || g.section}
                </span>
                {g.section && (
                  <span style={{ font: '400 11px var(--font-mono)', color: 'var(--stone)' }}>{g.section}</span>
                )}
                <span style={{ display: 'flex', gap: 6, marginLeft: 'auto', flexWrap: 'wrap' }}>
                  {g.gaps.map((t, j) => (
                    <span key={j} className="hf-pill amber" style={{ height: 22, fontSize: 10.5, whiteSpace: 'nowrap' }}>
                      {t}
                    </span>
                  ))}
                </span>
              </div>
              {g.detail && (
                <p style={{ margin: '0 0 12px', font: '400 13px/1.6 var(--font-sans)', color: 'var(--olive)' }}>
                  {g.detail}
                </p>
              )}
              <button className="hf-btn sand sm" onClick={() => onOptimize(g, report.target_track)}>
                去深度优化这段 →
              </button>
            </div>
          ))}
        </div>

        <div
          style={{
            font: '400 10.5px/1.5 var(--font-sans)', color: 'var(--stone)', textAlign: 'center', marginTop: 16,
          }}
        >
          只诊断、不改写 · 提分靠深度优化反问取证,把你真实的细节补出来——绝不靠 AI 补内容刷分
        </div>
      </div>
    </div>
  );
}

interface VersionBannerProps {
  stale: boolean;
  shownVName?: string;
  currentVName?: string;
  rescoring: boolean;
  onRescore: () => void;
  error?: string;
}

/** 版本对应横幅 + 重新打分按钮(移植自 hub-editor-ai.jsx ScoreReport banner)。
 *  版本一致:素色 + ghost 按钮;不一致:琥珀色 + primary 按钮带 ring 高亮。 */
function VersionBanner({
  stale,
  shownVName,
  currentVName,
  rescoring,
  onRescore,
  error,
}: VersionBannerProps): JSX.Element {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 9,
        marginBottom: 16,
        padding: '9px 11px',
        borderRadius: 12,
        background: stale ? 'var(--amber-bg)' : 'var(--library-rail)',
        boxShadow: stale ? '0 0 0 1px #ecdfa4' : '0 0 0 1px var(--border-warm)',
      }}
    >
      <span
        style={{
          color: stale ? 'var(--amber-fg)' : 'var(--stone)',
          display: 'inline-flex',
          flex: 'none',
        }}
      >
        <History size={14} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            font: '600 11.5px var(--font-sans)',
            color: stale ? 'var(--amber-fg)' : 'var(--ink-soft)',
          }}
        >
          {stale
            ? `打分基于 ${shownVName ?? '旧版'} · 当前 ${currentVName ?? ''}`
            : `当前打分 · ${shownVName ?? currentVName ?? ''}`}
        </div>
        <div style={{ font: '400 10.5px var(--font-sans)', color: 'var(--stone)', marginTop: 1 }}>
          {error ? error : stale ? '简历已更新,建议重新打分' : '版本与打分一致'}
        </div>
      </div>
      <button
        onClick={onRescore}
        disabled={rescoring}
        className={stale ? 'hf-btn primary sm' : 'hf-btn ghost sm'}
        style={{
          gap: 6,
          flex: 'none',
          boxShadow: stale ? '0 0 0 1px var(--terracotta), 0 0 0 4px var(--terracotta-ring)' : undefined,
        }}
      >
        {rescoring ? <span className="hf-spin" /> : <RotateCw size={13} />}
        {rescoring ? '打分中' : '重新打分'}
      </button>
    </div>
  );
}

/** 分组标题 — 带右侧细线(移植自 ScoreReport .dims-label)。 */
function DimsLabel({ children }: { children: ReactNode }): JSX.Element {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '4px 0 11px' }}>
      <span className="hf-overline" style={{ fontSize: 10 }}>{children}</span>
      <span style={{ flex: 1, height: 1, background: 'var(--border-warm)' }} />
    </div>
  );
}

interface DimRowProps {
  name: string;
  score: number;
  reason: string;
  meta?: string;
  fin?: boolean;
}

/** 逐维行:名称 + 分数 + fill bar(宽 = score%)+ reason。金融维 terracotta 标注。 */
function DimRow({ name, score, reason, meta, fin = false }: DimRowProps): JSX.Element {
  return (
    <div
      style={{
        background: fin ? 'var(--terracotta-wash)' : 'var(--ivory)',
        borderRadius: 'var(--r-md)',
        boxShadow: fin ? '0 0 0 1px #eccfb6' : 'var(--sh-ring)',
        padding: '11px 14px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ font: '600 13px var(--font-sans)', color: fin ? 'var(--terracotta-strong)' : 'var(--ink)' }}>
          {name}
        </span>
        <span style={{ font: '600 17px var(--font-mono)', color: 'var(--ink)', marginLeft: 'auto' }}>{score}</span>
      </div>
      <div
        style={{
          position: 'relative', height: 5, borderRadius: 'var(--r-pill)',
          background: 'var(--warm-sand)', overflow: 'hidden', margin: '7px 0 0',
        }}
      >
        <div
          style={{
            position: 'absolute', left: 0, top: 0, height: '100%', width: `${score}%`,
            borderRadius: 'var(--r-pill)', background: fillColor(score),
          }}
        />
      </div>
      {meta && (
        <div style={{ font: '400 11px/1.4 var(--font-sans)', color: 'var(--olive)', marginTop: 6 }}>{meta}</div>
      )}
      {reason && (
        <div style={{ font: '400 12px/1.55 var(--font-sans)', color: 'var(--olive)', marginTop: 6 }}>{reason}</div>
      )}
    </div>
  );
}
