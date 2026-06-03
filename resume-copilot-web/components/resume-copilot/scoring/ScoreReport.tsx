'use client';

import {
  AlignLeft,
  ArrowRight,
  BarChart3,
  ChevronDown,
  Compass,
  GitBranch,
  ListChecks,
  PenLine,
  RefreshCw,
  Shield,
  ShieldCheck,
  Sparkles,
  Target,
  type LucideIcon,
} from 'lucide-react';
import type { ScoreReportData } from '../api';
import { ScoreRadar, type RadarDim } from './ScoreRadar';
import './score-report.css';

/** 8 维元数据:固定顺序 + 图标 + 雷达短标签 + fin 标记。 */
interface DimMeta {
  key: string;
  icon: LucideIcon;
  radarLabel: string;
  fin?: boolean;
}
const DIM_META: DimMeta[] = [
  { key: 'logic', icon: GitBranch, radarLabel: '逻辑' },
  { key: 'star', icon: Target, radarLabel: 'STAR' },
  { key: 'readability', icon: AlignLeft, radarLabel: '可读' },
  { key: 'completeness', icon: ListChecks, radarLabel: '完整' },
  { key: 'expression', icon: PenLine, radarLabel: '表达' },
  { key: 'quantification', icon: BarChart3, radarLabel: '量化' },
  { key: 'track_fit', icon: Compass, radarLabel: '匹配度', fin: true },
  { key: 'defensibility', icon: ShieldCheck, radarLabel: '可防守', fin: true },
];
const META_BY_KEY = new Map(DIM_META.map((d) => [d.key, d]));
const SURFACE_KEYS = ['logic', 'star', 'readability', 'completeness', 'expression', 'quantification'];
const FIN_KEYS = ['track_fit', 'defensibility'];

function fillClass(score: number): string {
  if (score >= 75) return 'f-hi';
  if (score >= 65) return 'f-mid';
  return 'f-lo';
}

function finMeta(key: string, targetTrack: string): string {
  if (key === 'track_fit') return `这段经历对「${targetTrack || '目标赛道'}」的对口程度`;
  if (key === 'defensibility') return '这句话面试官追问时是否站得住';
  return '';
}

export interface ScoreReportProps {
  report: ScoreReportData;
  onDeepOptimize?: (section: string) => void;
  onSwitchTrack?: () => void;
  /** 是否显示外层报告标题(独立页用 true;嵌右栏用 false)。 */
  showHead?: boolean;
}

export function ScoreReport({ report, onDeepOptimize, onSwitchTrack, showHead = true }: ScoreReportProps) {
  const dimByKey = new Map(report.dimensions.map((d) => [d.key, d]));

  const radarData: RadarDim[] = DIM_META.map((m) => ({
    k: m.radarLabel,
    v: dimByKey.get(m.key)?.score ?? 0,
    fin: m.fin,
  }));

  const current = report.overall_current;
  const gain = Math.max(0, report.overall_potential_high - current);

  return (
    <div className="rc-score">
      <div className="report">
        {showHead && (
          <div className="report-head">
            <h1>简历打分报告</h1>
            <span>诚实诊断 · 不改写、不刷分</span>
          </div>
        )}

        <div className="card">
          {/* header */}
          <div className="hd">
            <div className="avatar"><Sparkles /></div>
            <div>
              <div className="hd-t1">AI 简历助手</div>
              <div className="hd-t2">基于目标赛道校准的多维诊断</div>
            </div>
            <div className="tabs">
              <button type="button" className="tab on">简历打分</button>
              <button type="button" className="tab">深度优化</button>
              <button type="button" className="tab">自由问</button>
            </div>
          </div>

          {/* target track */}
          <div className="track">
            <span className="track-label">目标赛道</span>
            <button type="button" className="track-pill">
              {report.target_track || '未指定'} <ChevronDown />
            </button>
            <button type="button" className="track-redo" onClick={onSwitchTrack}>
              <RefreshCw />切换赛道重新打分
            </button>
          </div>

          {/* hero */}
          <div className="hero">
            <div className="hero-left">
              <div className="score-row">
                <div className="score-now">
                  <div className="score-num">{current}<em>分</em></div>
                  <div className="score-cap">现状分 · 老实反映当前简历</div>
                </div>
                <div className="score-pot">
                  <div className="pot-val">潜力 {report.overall_potential_low}–{report.overall_potential_high}</div>
                  <div className="pot-bar">
                    <div className="pot-now" style={{ width: `${current}%` }} />
                    <div className="pot-gain" style={{ left: `${current}%`, width: `${gain}%` }} />
                  </div>
                  <div className="pot-cap">把下列缺口经反问取证<b>如实补齐</b>后可达,不靠编造</div>
                </div>
              </div>
              {report.summary && <p className="summary">{report.summary}</p>}
            </div>
            <div className="radar-wrap"><ScoreRadar data={radarData} size={300} /></div>
          </div>

          {/* dimensions */}
          <div className="dims">
            <div className="dims-label">6 表层维</div>
            <div className="dims-grid">
              {SURFACE_KEYS.map((key) => {
                const d = dimByKey.get(key);
                const meta = META_BY_KEY.get(key);
                if (!d || !meta) return null;
                const Icon = meta.icon;
                return (
                  <div className="dim" key={key}>
                    <div className="dim-ico"><Icon /></div>
                    <div className="dim-mid">
                      <div className="dim-name">{d.name}</div>
                      <div className="dim-meter"><div className={`dim-fill ${fillClass(d.score)}`} style={{ width: `${d.score}%` }} /></div>
                    </div>
                    <div className="dim-score">{d.score}</div>
                  </div>
                );
              })}
            </div>

            <div className="dims-label">2 金融独有维</div>
            <div className="dims-grid">
              {FIN_KEYS.map((key) => {
                const d = dimByKey.get(key);
                const meta = META_BY_KEY.get(key);
                if (!d || !meta) return null;
                const Icon = meta.icon;
                return (
                  <div className="dim fin" key={key}>
                    <div className="dim-ico"><Icon /></div>
                    <div className="dim-mid">
                      <div className="dim-name">{d.name}</div>
                      <div className="dim-meta">{finMeta(key, report.target_track)}</div>
                    </div>
                    <div className="dim-score">{d.score}</div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* gaps */}
          <div className="gaps">
            <div className="dims-label">逐段缺口 · 深度优化入口</div>
            {report.section_gaps.map((g) => (
              <div className="gap" key={g.section}>
                <div className="gap-top">
                  <span className="gap-name">{g.label || g.section}</span>
                  <span className="gap-loc">{g.section}</span>
                  <span className="gap-tags">
                    {g.gaps.map((t, j) => <span className="gtag" key={j}>{t}</span>)}
                  </span>
                </div>
                {g.detail && <p className="gap-desc">{g.detail}</p>}
                <button type="button" className="gap-cta" onClick={() => onDeepOptimize?.(g.section)}>
                  去深度优化这段 <ArrowRight />
                </button>
              </div>
            ))}
          </div>

          {/* footer */}
          <div className="foot">
            <Shield />
            <p>
              <b>诚实契约</b>:打分只诊断、不改写,分数老实反映现状。提分只能通过深度优化的反问取证,把你真实的细节补出来——绝不靠 AI 补内容刷分。
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
