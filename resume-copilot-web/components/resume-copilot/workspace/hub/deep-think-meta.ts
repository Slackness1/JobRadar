/**
 * deep-think-meta.ts — 统一对话 Hub 深度思考卡静态底座
 *
 * 4 模块「我的理解」文案 + 4 思考节点 + 工具名。
 * 真实数据（赛道 / 记忆 pills、节点实际计数）由 HubShell 注入为 overrides；
 * 本文件只持有默认值，不含运行时逻辑。
 *
 * 图标方案：lucide-react 已是项目依赖（^0.468.0），
 * 使用 lucide 图标组件 re-export，避免手写 SVG path 字符串。
 * DTIcon render helper 接受图标名查 ICONS 表，返回带统一 stroke 的 <svg>。
 */

import type { LucideIcon } from 'lucide-react';
import {
  Target,
  Search,
  SearchCheck,
  BarChart2,
  Gauge,
  ListChecks,
  FileText,
  Pencil,
  Layers,
  Building2,
  Grid2X2,
  Clock,
  UserCheck,
  DoorOpen,
} from 'lucide-react';

// ── Types ────────────────────────────────────────────────────────────────────

export interface DeepNode {
  /** Lucide icon name key — look up in ICONS */
  icon: string;
  /** 4-char node name shown in the step header */
  title: string;
  /** Tool name shown as monospace badge */
  tool: string;
  /** Input key-value pairs shown in expanded tool body */
  input: Record<string, string | string[]>;
  /** Completed-state output text (overridable by real counts) */
  output: string;
  /** Completed-state result chips */
  chips: string[];
}

export interface DeepUnderstand {
  /** 「我理解你要的是 —— <headline>」 */
  headline: string;
  /** 赛道 pill list (real data may override) */
  tracks: string[];
  /** 记忆 pill list (real data may override) */
  memory: string[];
  /** Typewriter reasoning paragraph */
  reasoning: string;
}

export interface DeepMeta {
  understand: DeepUnderstand;
  nodes: DeepNode[];
}

export type HubModule = 'feed' | 'skeleton' | 'resume' | 'interview';

// ── Static data ──────────────────────────────────────────────────────────────

export const DEEP_META: Record<HubModule, DeepMeta> = {
  feed: {
    understand: {
      headline: '投研 / 券商资管方向的真实在招岗位,不是泛泛的金融岗。',
      tracks: ['投研', '券商资管'],
      memory: ['看重平台梯队', '可接受 base 985', '记忆 ×3'],
      reasoning:
        '结合你确认过的赛道和偏好:更看重平台梯队而不是起薪。我会先锁定范围,再检索在招、做三维打分,最后排出最值得投的几个。',
    },
    nodes: [
      {
        icon: 'target',
        title: '锁定赛道',
        tool: 'lock_track',
        input: { track: ['投研', '券商资管'], base: '≥ 985' },
        output: '锁定 2 条赛道 · 命中记忆 3 项',
        chips: ['投研', '券商资管', '命中记忆 ×3'],
      },
      {
        icon: 'search',
        title: '检索岗位',
        tool: 'search_candidates',
        input: { tracks: ['投研', '券商资管'], degree: '硕士' },
        output: '召回 40 → 去重 39',
        chips: ['券商研究 ×14', '资管 ×16', '公募 ×9'],
      },
      {
        icon: 'barchart',
        title: '三维打分',
        tool: 'score_jobs',
        input: { dims: ['硬匹配', '情报增强', '赛道契合'], n: '39' },
        output: '39 个岗位三维评分完成',
        chips: ['硬匹配', '情报增强', '赛道契合'],
      },
      {
        icon: 'listchecks',
        title: '排出推荐',
        tool: 'finalize',
        input: { topN: 'Top', guard: 'substring 反幻觉' },
        output: '第一版 Top 已就绪',
        chips: ['Base 96 · Enhanced 96'],
      },
    ],
  },

  skeleton: {
    understand: {
      headline: '把券商资管这条赛道的公司,按梯队分档铺成全景。',
      tracks: ['二级买方', '基本面'],
      memory: ['关注头部 / 主力', '匹配档高亮'],
      reasoning:
        '我会先把这条赛道的相关公司拉全,再按规模与口碑分档,结合你的背景定位你落在哪一档,最后铺成可对照的全景。',
    },
    nodes: [
      {
        icon: 'building',
        title: '拉取公司',
        tool: 'pull_companies',
        input: { track: '二级买方 · 基本面' },
        output: '拉到 18 家 GT 公司',
        chips: ['18 家公司'],
      },
      {
        icon: 'layers',
        title: '梯队分档',
        tool: 'tier_split',
        input: { by: ['规模', '口碑', '在招'] },
        output: '分出 头部 / 主力 / 腰部',
        chips: ['头部', '主力', '腰部'],
      },
      {
        icon: 'target',
        title: '背景定档',
        tool: 'place_profile',
        input: { profile: '陈思远 · 投研' },
        output: '定位到「主力」档',
        chips: ['你 → 主力档'],
      },
      {
        icon: 'grid',
        title: '铺出全景',
        tool: 'finalize',
        input: { layout: '梯队全景' },
        output: '全景已铺好 · 匹配档高亮',
        chips: ['匹配档高亮'],
      },
    ],
  },

  resume: {
    understand: {
      headline: '对这份简历做一次诚实打分 + 缺口定位,不是粉饰。',
      tracks: ['投研', '券商资管'],
      memory: ['只诚实评估', '逐段可补', '中文主版'],
      reasoning:
        '我会先解析简历结构,按目标赛道做诚实打分,再逐段定位缺口在哪,最后给出能落地补的建议 —— 数字与经历都基于你原文,不灌水。',
    },
    nodes: [
      {
        icon: 'filetext',
        title: '解析简历',
        tool: 'parse_resume',
        input: { sections: ['基本', '经历 ×6', '技能'] },
        output: '6 段经历已结构化',
        chips: ['6 段经历'],
      },
      {
        icon: 'gauge',
        title: '诚实打分',
        tool: 'score_resume',
        input: { against: '投研 JD 画像' },
        output: '现状 72 · 潜力 80–85',
        chips: ['现状 72', '潜力 80–85'],
      },
      {
        icon: 'searchcheck',
        title: '定位缺口',
        tool: 'find_gaps',
        input: { scan: ['硬门槛', '量化结果', '关键词'] },
        output: '定位到 3 段可补缺口',
        chips: ['缺量化', '关键词不足', '弱动词'],
      },
      {
        icon: 'listchecks',
        title: '给出建议',
        tool: 'finalize',
        input: { perGap: '逐段入口' },
        output: '3 段建议 · 已挂逐段入口',
        chips: ['逐段入口'],
      },
    ],
  },

  interview: {
    understand: {
      headline: '按你的目标赛道,备一场对路的模拟面试。',
      tracks: ['投研', '券商资管'],
      memory: ['延续同一会话', '记忆延用'],
      reasoning:
        '我会调取你这条会话里的记忆与画像,匹配对路的考官风格,按赛道门槛与真题备好题库,然后进入全屏面试间。',
    },
    nodes: [
      {
        icon: 'clock',
        title: '调取记忆',
        tool: 'load_memory',
        input: { from: '本会话' },
        output: '画像与偏好已载入',
        chips: ['记忆延用'],
      },
      {
        icon: 'usercheck',
        title: '匹配考官',
        tool: 'match_examiner',
        input: { track: '券商资管' },
        output: '匹配到买方研究考官',
        chips: ['买方研究风格'],
      },
      {
        icon: 'listchecks',
        title: '备好题库',
        tool: 'build_bank',
        input: { by: ['门槛', '真题'] },
        output: '题库已就绪',
        chips: ['门槛题', '真题'],
      },
      {
        icon: 'door',
        title: '进入面试间',
        tool: 'finalize',
        input: { mode: '全屏' },
        output: '面试间准备好了',
        chips: ['全屏 · 结束回 Hub'],
      },
    ],
  },
};

// ── Icon table ────────────────────────────────────────────────────────────────
//
// Maps the icon key strings used in DeepNode.icon to lucide-react components.
// All icons are monochrome (stroke="currentColor", no colourful fill).
// The prototype used raw SVG paths; we use lucide-react component re-exports
// instead (cleaner, type-safe, same visual output since lucide-react renders
// identical path geometry). DTIcon (below) is the single render call site.

export const ICONS: Record<string, LucideIcon> = {
  target: Target,
  search: Search,
  searchcheck: SearchCheck,
  barchart: BarChart2,
  gauge: Gauge,
  listchecks: ListChecks,
  filetext: FileText,
  pencil: Pencil,
  layers: Layers,
  building: Building2,
  grid: Grid2X2,
  clock: Clock,
  usercheck: UserCheck,
  door: DoorOpen,
};

// ── DTIcon render helper ──────────────────────────────────────────────────────
//
// Returns a monochrome lucide icon element.  Accepts the same `name` strings
// that DeepNode.icon uses. Falls back to ListChecks if the name is unknown.
// Color is single-stroke currentColor — no colorful fills.

export interface DTIconProps {
  name: string;
  size?: number;
  /** Defaults to 'currentColor' — monochrome only */
  color?: string;
  strokeWidth?: number;
}

export function DTIcon({ name, size = 15, color = 'currentColor', strokeWidth = 1.6 }: DTIconProps) {
  const Icon = ICONS[name] ?? ListChecks;
  return Icon({
    width: size,
    height: size,
    color,
    strokeWidth,
    style: { flex: 'none' },
  } as Parameters<LucideIcon>[0]);
}
