'use client';

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ChangeEvent,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  ArrowUpRight,
  Check,
  ChevronDown,
  FileText,
  Github,
  Home,
  Linkedin,
  Link as LinkIcon,
  Loader2,
  Mail,
  MapPin,
  PencilLine,
  Phone,
  Plus,
  Sparkles,
  Trash2,
  UploadCloud,
} from 'lucide-react';

import {
  DEMO_SESSION_ID,
  createResumeCopilotSession,
  deleteResumeCopilotSession,
  getChatMessages,
  getDirectionAnalysis,
  getResumeCopilotFeedback,
  getResumeCopilotParsedProfile,
  getResumeCopilotPreferences,
  getResumeCopilotRecommendations,
  getResumeCopilotSession,
  listResumeCopilotSessions,
  postApplyRewrite,
  postChatMessage,
  postResumeCopilotGenerate,
  putResumeCopilotConfirmedProfile,
  putResumeCopilotPreferences,
  renameResumeCopilotSession,
} from './api';
import {
  type CopilotMessage,
  type DirectionTierResult,
  type ResumeAgentTraceItem,
  EMPTY_PREFERENCES,
  EMPTY_PROFILE,
  type ResumeCopilotSession,
  type ResumeCopilotSessionListItem,
  type ResumeEducationItem,
  type ResumeFeedbackResult,
  type ResumeInternshipItem,
  type ResumePreferencePayload,
  type ResumeProfilePayload,
  type ResumeProjectItem,
  type ResumeRecommendationItem,
  type ResumeRecommendationResult,
  type RewriteOption,
} from './types';
import { DemoBanner } from '@/components/hifi/demo-banner';
import { HFLogo, HFRadarPulse } from '@/components/hifi/hifi-primitives';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

const EMPTY_EDUCATION: ResumeEducationItem = {
  school: '',
  degree: '',
  major: '',
  start_date: '',
  end_date: '',
  highlights: [],
};

const EMPTY_INTERNSHIP: ResumeInternshipItem = {
  company: '',
  role: '',
  start_date: '',
  end_date: '',
  bullets: [],
};

const EMPTY_PROJECT: ResumeProjectItem = {
  name: '',
  role: '',
  tech_stack: [],
  bullets: [],
};

const CUSTOM_MODULES_KEY = '__custom_modules_json';

interface CustomResumeModule {
  id: string;
  title: string;
  content: string;
}

interface ResumeLayoutSettings {
  fontSize: number;
  lineHeight: number;
  pagePaddingX: number;
  pagePaddingY: number;
  moduleGap: number;
}

const DEFAULT_RESUME_LAYOUT: ResumeLayoutSettings = {
  fontSize: 14,
  lineHeight: 1.72,
  pagePaddingX: 56,
  pagePaddingY: 48,
  moduleGap: 24,
};

type ResumeLayoutControlKey = 'pagePadding' | 'moduleGap' | 'lineHeight' | 'fontSize';

const RESUME_LAYOUT_CONTROL_META: Record<
  ResumeLayoutControlKey,
  {
    title: string;
    description: string;
    min: number;
    max: number;
    step: number;
    unit: string;
    range: string;
  }
> = {
  pagePadding: {
    title: '页边距',
    description: '调整简历页面四周留白',
    min: 36,
    max: 84,
    step: 1,
    unit: 'px',
    range: '36 - 84',
  },
  moduleGap: {
    title: '模块边距',
    description: '调整简历模块之间的距离',
    min: 12,
    max: 40,
    step: 1,
    unit: 'px',
    range: '12 - 40',
  },
  lineHeight: {
    title: '行间距',
    description: '调整简历文本的行间距',
    min: 1,
    max: 2.5,
    step: 0.01,
    unit: '',
    range: '1.0 - 2.5',
  },
  fontSize: {
    title: '字体大小',
    description: '调整简历正文的字体大小',
    min: 12,
    max: 18,
    step: 0.1,
    unit: 'px',
    range: '12 - 18',
  },
};

const TRACK_OPTIONS = ['金融科技', '咨询', '数据分析', '产品运营', '后端开发', '投研'];
const LOCATION_OPTIONS = ['上海', '北京', '深圳', '杭州', '广州', '远程'];
const ROLE_OPTIONS = ['数据分析师', '后端工程师', '产品经理', '咨询顾问', '投研实习生'];
const COMPANY_OPTIONS = ['互联网', '金融机构', '咨询公司', '外企', '初创公司', '国央企'];
interface ResumeHistoryItem {
  id: number;
  fileName: string;
  name: string;
  status: string;
  updatedAt: string | null;
  hasRecommendations: boolean;
}

function mapListItem(item: ResumeCopilotSessionListItem): ResumeHistoryItem {
  return {
    id: item.id,
    fileName: item.file_name,
    name: item.name,
    status: item.status,
    updatedAt: item.updated_at,
    hasRecommendations: item.has_recommendations,
  };
}

function timeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  const ms = Date.now() - new Date(dateStr).getTime();
  if (ms < 60_000) return '刚刚';
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)} 分钟前`;
  if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)} 小时前`;
  if (ms < 7 * 86_400_000) return `${Math.floor(ms / 86_400_000)} 天前`;
  return new Date(dateStr).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

function splitLines(value: string) {
  return value
    .split('\n')
    .map((line) => line.replace(/^[-*•]\s*/, '').trim())
    .filter(Boolean);
}

function joinLines(values: string[]) {
  return values.join('\n');
}

function appendUnique(values: string[], value: string) {
  const normalized = value.trim();
  if (!normalized || values.includes(normalized)) return values;
  return [...values, normalized];
}


function sessionIsActive(session: ResumeCopilotSession | null) {
  if (!session) return false;
  return (
    session.status === 'parsing_profile' ||
    session.status === 'generating_recommendations' ||
    session.recommendation_status === 'running' ||
    session.feedback_status === 'running'
  );
}

function formatModelFallback(reason: string | undefined) {
  if (!reason) return '';
  if (reason.includes('RESUME_COPILOT_LLM_API_KEY')) {
    return '当前后端进程没有加载模型 Key，已先使用规则排序。';
  }
  return reason;
}

function enrichmentStatusLabel(status: string, needEnrichment: boolean) {
  if (status === 'ready') return '情报缓存已命中';
  if (status === 'quick_enriched') return '快增强已完成';
  if (status === 'internal_beta_pending' || needEnrichment) return '情报增强内测中';
  return '基础推荐';
}

function enrichmentBadgeClass(status: string, needEnrichment: boolean) {
  if (status === 'ready') return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (status === 'quick_enriched') return 'border-sky-100 bg-sky-50 text-sky-700';
  if (status === 'internal_beta_pending' || needEnrichment) return 'border-amber-100 bg-amber-50 text-amber-700';
  return 'border-slate-200 bg-slate-50 text-slate-500';
}

// All known agents — shown in parallel from the moment the panel appears
const ALL_AGENTS = ['Agent 1', 'Agent 2', 'Agent 3'] as const;
type AgentName = typeof ALL_AGENTS[number];

// Claude Code-style spinner: · ✢ ✳ ✶ ✻ ✽
const SPINNER_FRAMES = ['·', '✢', '✳', '✶', '✻', '✽'] as const;
const POLL_MAX_DURATION_MS = 5 * 60 * 1000; // 5 minutes
const POLL_ERROR_LIMIT = 3;

// Cycling verbs shown as placeholder while waiting for real backend messages
const AGENT_VERBS: Record<AgentName, string[]> = {
  'Agent 1': ['召回岗位中', '计算匹配权重', '评估候选岗位', '对齐求职偏好', '初筛排序'],
  'Agent 2': ['生成检索词', '检索互联网', '聚合搜索结果', '过滤去重'],
  'Agent 3': ['提取页面正文', '分析岗位信息', '生成轻量画像', '评估相关性'],
};

// Start each agent's spinner at a different frame so they look visually offset
const AGENT_SPINNER_OFFSETS: Record<AgentName, number> = {
  'Agent 1': 0,
  'Agent 2': 2,
  'Agent 3': 4,
};

const TOOL_META: Record<string, { icon: string; label: string }> = {
  search_candidates: { icon: '🔍', label: '检索候选岗位' },
  inspect_jobs:      { icon: '📄', label: '阅读岗位详情' },
  get_company_intel: { icon: '🏢', label: '查询公司情报' },
  search_web:        { icon: '🌐', label: '搜索外部信息' },
  finalize:          { icon: '✅', label: '生成最终推荐' },
};

function AgentRow({
  agentName,
  latest,
  running,
}: {
  agentName: AgentName;
  latest: ResumeAgentTraceItem | undefined;
  running: boolean;
}) {
  const isDone = latest?.status === 'completed' || latest?.status === 'failed';
  const animate = running && !isDone;

  const [frameIdx, setFrameIdx] = useState(AGENT_SPINNER_OFFSETS[agentName]);
  const [verbIdx, setVerbIdx] = useState(0);

  useEffect(() => {
    if (!animate) return;
    const spinTimer = setInterval(
      () => setFrameIdx((i) => (i + 1) % SPINNER_FRAMES.length),
      120,
    );
    const verbMs = 2000 + AGENT_SPINNER_OFFSETS[agentName] * 150;
    const verbTimer = setInterval(
      () => setVerbIdx((i) => (i + 1) % AGENT_VERBS[agentName].length),
      verbMs,
    );
    return () => {
      clearInterval(spinTimer);
      clearInterval(verbTimer);
    };
  }, [animate, agentName]);

  const spinChar = isDone ? '✓' : SPINNER_FRAMES[frameIdx];
  const toolMeta = latest?.tool ? TOOL_META[latest.tool] : undefined;
  const displayMessage = latest?.message ?? (running ? AGENT_VERBS[agentName][verbIdx] : '—');

  return (
    <div
      className="flex items-start gap-3 py-2"
      style={{
        animation: isDone && latest?.tool ? 'slideInUp 0.28s ease-out both' : 'none',
      }}
    >
      <span
        className="mt-[2px] shrink-0 font-mono text-[15px] leading-snug"
        style={{
          color: isDone ? '#4ade80' : '#7c9ef7',
          minWidth: '1ch',
          display: 'inline-block',
          textAlign: 'center',
        }}
      >
        {spinChar}
      </span>
      <div className="min-w-0 flex-1">
        {toolMeta && isDone ? (
          <>
            <div className="flex items-center gap-1.5">
              <span className="text-[13px]">{toolMeta.icon}</span>
              <span className="text-[13px] font-semibold text-slate-800">{toolMeta.label}</span>
            </div>
            <div className="mt-0.5 text-[12px] leading-snug text-slate-500">{displayMessage}</div>
            {latest?.result_summary && (
              <div className="mt-0.5 text-[11px] leading-snug text-slate-400">{latest.result_summary}</div>
            )}
          </>
        ) : (
          <div className="flex items-baseline gap-2">
            <span className="shrink-0 text-[13px] font-semibold text-slate-800">{agentName}</span>
            <span className="shrink-0 text-[12px] text-slate-300">·</span>
            <span className="min-w-0 truncate text-[13px] leading-snug text-slate-500">{displayMessage}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function StepCard({ item }: { item: ResumeAgentTraceItem }) {
  const toolMeta = item.tool ? TOOL_META[item.tool] : undefined;
  return (
    <div
      className="flex items-start gap-3 py-2"
      style={{ animation: 'slideInUp 0.28s ease-out both' }}
    >
      <span
        className="mt-[2px] shrink-0 font-mono text-[15px] leading-snug"
        style={{ color: '#4ade80', minWidth: '1ch', display: 'inline-block', textAlign: 'center' }}
      >
        ✓
      </span>
      <div className="min-w-0 flex-1">
        {toolMeta ? (
          <>
            <div className="flex items-center gap-1.5">
              <span className="text-[13px]">{toolMeta.icon}</span>
              <span className="text-[13px] font-semibold text-slate-800">{toolMeta.label}</span>
            </div>
            <div className="mt-0.5 text-[12px] leading-snug text-slate-500">{item.message}</div>
            {item.result_summary && (
              <div className="mt-0.5 text-[11px] leading-snug text-slate-400">{item.result_summary}</div>
            )}
          </>
        ) : (
          <div className="text-[13px] leading-snug text-slate-500">{item.message}</div>
        )}
      </div>
    </div>
  );
}

function RunningStepRow({ message }: { message?: string }) {
  const [frameIdx, setFrameIdx] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setFrameIdx((i) => (i + 1) % SPINNER_FRAMES.length), 120);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="flex items-start gap-3 py-2">
      <span
        className="mt-[2px] shrink-0 font-mono text-[15px] leading-snug"
        style={{ color: '#7c9ef7', minWidth: '1ch', display: 'inline-block', textAlign: 'center' }}
      >
        {SPINNER_FRAMES[frameIdx]}
      </span>
      <div className="min-w-0 flex-1">
        <span className="text-[13px] leading-snug text-slate-500">{message ?? '正在推理…'}</span>
      </div>
    </div>
  );
}

function AgentThinkingPanel({
  trace,
  running,
}: {
  trace: ResumeAgentTraceItem[];
  running: boolean;
}) {
  if (!running && !trace.length) return null;

  // Detect ReAct trace: any item has a non-empty tool field
  const isReActTrace = trace.some((item) => item.tool);

  if (!isReActTrace) {
    // Backward compat: old agent-name-based rendering
    const agentLatest = new Map<string, ResumeAgentTraceItem>();
    for (const item of trace) agentLatest.set(item.agent, item);
    const agentsToShow: AgentName[] = running
      ? [...ALL_AGENTS]
      : ALL_AGENTS.filter((a) => agentLatest.has(a));
    return (
      <div className="rounded-[18px] border border-[var(--border)] bg-white px-4 py-3.5 shadow-[0_4px_18px_rgba(15,23,42,0.06)]">
        <div className="mb-2 flex items-center gap-2">
          {running && <HFRadarPulse size={18} />}
          <span className="text-[11px] font-semibold uppercase tracking-widest text-[var(--muted)]">
            {running ? '代理思考中' : '代理编排完成'}
          </span>
          <span className="rounded-full bg-[var(--soft-blue)] px-2 py-0.5 text-[11px] leading-5 text-[var(--primary)]">
            快增强
          </span>
        </div>
        <div className="divide-y divide-[var(--border)]">
          {agentsToShow.map((agentName) => (
            <AgentRow
              key={agentName}
              agentName={agentName}
              latest={agentLatest.get(agentName)}
              running={running}
            />
          ))}
        </div>
      </div>
    );
  }

  // ReAct trace: deduplicate by step_index, prefer completed over running
  const stepMap = new Map<number, ResumeAgentTraceItem>();
  for (const item of trace) {
    const idx = item.step_index ?? 0;
    if (!idx) continue; // skip pre-agent workflow items (step_index=0)
    const existing = stepMap.get(idx);
    if (!existing || item.status === 'completed') stepMap.set(idx, item);
  }
  const steps = [...stepMap.values()].sort((a, b) => (a.step_index ?? 0) - (b.step_index ?? 0));
  const completedSteps = steps.filter((s) => s.status === 'completed' && s.tool);
  const currentRunning = steps.find((s) => s.status === 'running' && s.tool);

  return (
    <div className="rounded-[18px] border border-[var(--border)] bg-white px-4 py-3.5 shadow-[0_4px_18px_rgba(15,23,42,0.06)]">
      <div className="mb-2 flex items-center gap-2">
        {running && <HFRadarPulse size={18} />}
        <span className="text-[11px] font-semibold uppercase tracking-widest text-[var(--muted)]">
          {running ? 'AI 推理中' : '推理完成'}
        </span>
      </div>
      <div className="space-y-0.5">
        {completedSteps.map((item) => (
          <StepCard key={item.step_index} item={item} />
        ))}
        {running && <RunningStepRow message={currentRunning?.message} />}
      </div>
    </div>
  );
}

function getProfileName(profile: ResumeProfilePayload) {
  return getBasicInfoValue(profile.basic_info, ['name', 'full_name', '姓名']) || '候选人姓名';
}

function getProfileHeadline(profile: ResumeProfilePayload) {
  return getBasicInfoValue(profile.basic_info, ['headline', 'target_role', 'title', '目标岗位']) || profile.inferred_roles[0] || '目标岗位 / 当前身份';
}

function getBasicInfoValue(basicInfo: Record<string, string>, keys: string[]) {
  for (const key of keys) {
    const value = basicInfo[key];
    if (value) return value;
  }
  return '';
}

function getProfileContactItems(profile: ResumeProfilePayload) {
  const basicInfo = profile.basic_info;
  const items = [
    {
      key: 'email',
      value: getBasicInfoValue(basicInfo, ['email', '邮箱', '电子邮箱']),
      icon: <Mail className="size-3.5" />,
    },
    {
      key: 'phone',
      value: getBasicInfoValue(basicInfo, ['phone', 'mobile', 'tel', '电话', '手机号']),
      icon: <Phone className="size-3.5" />,
    },
    {
      key: 'github',
      value: getBasicInfoValue(basicInfo, ['github', 'github_url', 'GitHub']),
      icon: <Github className="size-3.5" />,
    },
    {
      key: 'linkedin',
      value: getBasicInfoValue(basicInfo, ['linkedin', 'linkedin_url', 'LinkedIn', '领英']),
      icon: <Linkedin className="size-3.5" />,
    },
    {
      key: 'website',
      value: getBasicInfoValue(basicInfo, ['website', 'portfolio', '个人网站', '个人主页']),
      icon: <LinkIcon className="size-3.5" />,
    },
    {
      key: 'location',
      value: getBasicInfoValue(basicInfo, ['location', '所在地', '地址']),
      icon: <MapPin className="size-3.5" />,
    },
  ];

  return items.filter((item) => Boolean(item.value));
}

function readCustomModules(profile: ResumeProfilePayload): CustomResumeModule[] {
  const rawValue = profile.basic_info[CUSTOM_MODULES_KEY];
  if (!rawValue) return [];

  try {
    const parsed = JSON.parse(rawValue) as CustomResumeModule[];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item) => item && typeof item.id === 'string');
  } catch {
    return [];
  }
}

function updateCustomModules(
  updateProfile: (updater: (profile: ResumeProfilePayload) => ResumeProfilePayload) => void,
  modules: CustomResumeModule[],
) {
  updateProfile((previous) => ({
    ...previous,
    basic_info: {
      ...previous.basic_info,
      [CUSTOM_MODULES_KEY]: JSON.stringify(modules),
    },
  }));
}

function nextCustomModuleId(modules: CustomResumeModule[]) {
  const existingIds = new Set(modules.map((module) => module.id));
  let index = modules.length + 1;
  while (existingIds.has(`custom-${index}`)) {
    index += 1;
  }
  return `custom-${index}`;
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  className,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}) {
  return (
    <label className={cn('grid gap-1.5 text-sm font-semibold text-[var(--ink)]', className)}>
      <span>{label}</span>
      <Input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
    </label>
  );
}

function AreaField({
  label,
  value,
  onChange,
  placeholder,
  rows = 4,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
}) {
  return (
    <label className="grid gap-1.5 text-sm font-semibold text-[var(--ink)]">
      <span>{label}</span>
      <Textarea rows={rows} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
    </label>
  );
}

function ChipEditor({
  label,
  values,
  placeholder,
  onChange,
}: {
  label: string;
  values: string[];
  placeholder: string;
  onChange: (values: string[]) => void;
}) {
  const [draft, setDraft] = useState('');

  const addDraft = () => {
    onChange(appendUnique(values, draft));
    setDraft('');
  };

  return (
    <div className="grid gap-2">
      <div className="text-sm font-semibold text-[var(--ink)]">{label}</div>
      <div className="flex flex-wrap gap-2 rounded-2xl border border-[var(--border)] bg-white p-3">
        {values.map((item) => (
          <span
            key={item}
            className="inline-flex items-center gap-1.5 rounded-full bg-[var(--soft-blue)] px-3 py-1.5 text-sm font-semibold text-[var(--primary-strong)]"
          >
            {item}
            <button
              type="button"
              className="rounded-full px-1 text-[var(--primary)] hover:bg-white"
              aria-label={`删除${item}`}
              onClick={() => onChange(values.filter((value) => value !== item))}
            >
              ×
            </button>
          </span>
        ))}
        <input
          className="min-w-32 flex-1 bg-transparent px-1 py-1.5 text-sm outline-none placeholder:text-[var(--muted)]"
          value={draft}
          placeholder={placeholder}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              addDraft();
            }
          }}
        />
        <Button type="button" variant="secondary" size="sm" onClick={addDraft}>
          <Plus />
          添加
        </Button>
      </div>
    </div>
  );
}

function OptionPills({
  label,
  options,
  values,
  onChange,
}: {
  label: string;
  options: string[];
  values: string[];
  onChange: (values: string[]) => void;
}) {
  return (
    <div className="grid gap-2">
      <div className="text-sm font-semibold text-[var(--ink)]">{label}</div>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const selected = values.includes(option);
          return (
            <button
              key={option}
              type="button"
              className={cn(
                'rounded-full border px-3 py-1.5 text-sm font-semibold transition',
                selected
                  ? 'border-[var(--primary)] bg-[var(--primary)] text-white shadow-sm'
                  : 'border-[var(--border)] bg-white text-[var(--muted)] hover:border-[var(--primary)] hover:text-[var(--primary)]',
              )}
              onClick={() => onChange(selected ? values.filter((value) => value !== option) : [...values, option])}
            >
              {option}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function PreviewSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-[var(--resume-section-gap)]">
      <h2 className="mb-3 inline-block border-b-2 border-[var(--primary)] pb-1 text-[14px] font-semibold tracking-[0.08em] text-[var(--primary-strong)]">
        {title}
      </h2>
      <div className="grid gap-3">{children}</div>
    </section>
  );
}

function PreviewEntry({
  title,
  meta,
  date,
  bullets,
}: {
  title: string;
  meta?: string;
  date?: string;
  bullets?: string[];
}) {
  return (
    <article>
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="font-semibold text-slate-950">{title || '未命名条目'}</div>
          {meta && <div className="text-[12px] text-slate-500">{meta}</div>}
        </div>
        {date && <div className="whitespace-nowrap text-[12px] text-slate-500">{date}</div>}
      </div>
      {Boolean(bullets?.length) && (
        <ul className="mt-1 list-disc space-y-1 pl-4 text-slate-700">
          {bullets?.slice(0, 4).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </article>
  );
}

function LandingUploadGate({
  onUpload,
  isUploading,
  error,
}: {
  onUpload: (event: ChangeEvent<HTMLInputElement>) => void;
  isUploading: boolean;
  error: string;
}) {
  const tickerItems = [
    '互联网 · 腾讯 · 后端开发工程师 · 深圳',
    '互联网 · 字节跳动 · 算法工程师 · 北京',
    '互联网 · 阿里巴巴 · 数据分析师 · 杭州',
    '券商 · 中金公司 · 研究助理 · 上海',
    '国央企 · 国家电网 · 技术培训生 · 西安',
    '外企 · 雀巢 · 管培生 · 上海',
  ];

  const highlightItems = [
    '优先主流赛道顶级平台，先把值得投的岗位排到前面',
    '先给第一版推荐，再对重点岗位做 10–20 秒快增强',
    '把平台梯队、岗位画像和不确定点一起讲清楚',
  ];

  return (
    <main className="min-h-screen bg-[#f6f7f8] text-slate-950">
      <section className="border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-[1600px] gap-3 overflow-x-auto px-5 py-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {tickerItems.map((item) => (
            <div
              key={item}
              className="shrink-0 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 shadow-[0_10px_30px_rgba(15,23,42,0.04)]"
            >
              {item}
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto grid max-w-[1400px] gap-10 px-6 py-12 lg:grid-cols-[minmax(0,1.15fr)_420px] lg:px-10 lg:py-16">
        <div>
          <div className="max-w-4xl">
            <Badge className="border-[var(--primary-ring)] bg-[var(--soft-blue)] text-[var(--primary-strong)]">Resume Copilot</Badge>
            <h1 className="mt-6 max-w-[920px] text-balance text-[clamp(3rem,6vw,5.5rem)] font-black leading-[0.94] tracking-[-0.06em] text-slate-950">
              更快发现真正值得投递的岗位
            </h1>
            <p className="mt-6 max-w-[760px] text-lg leading-8 text-slate-600">
              面向高校学生的求职推荐入口。先基于真实岗位库给出第一版推荐，再对重点岗位做轻量增强，把平台、岗位倾向和不确定点一起讲清楚。
            </p>
          </div>

          <div className="mt-10 grid gap-4">
            {highlightItems.map((item) => (
              <div
                key={item}
                className="flex items-center gap-4 rounded-[22px] border border-slate-200 bg-white px-5 py-5 shadow-[0_18px_50px_rgba(15,23,42,0.05)]"
              >
                <span className="grid size-7 shrink-0 place-items-center rounded-full bg-sky-100">
                  <span className="size-3 rounded-full bg-[var(--primary)]" />
                </span>
                <span className="text-base font-semibold tracking-[-0.02em] text-slate-800">{item}</span>
              </div>
            ))}
          </div>

          <div className="mt-8 flex flex-wrap gap-3">
            <Badge className="border-[var(--primary-ring)] bg-[var(--soft-blue)] text-[var(--primary-strong)]">优先主流赛道顶级平台</Badge>
            <Badge className="border-[var(--border)] bg-white text-[var(--muted)]">Base / Enhanced 双分数</Badge>
            <Badge className="border-slate-200 bg-white text-[var(--muted)]">代理思考式快增强</Badge>
            <Badge className="border-amber-100 bg-amber-50 text-amber-700">岗位情报增强内测中</Badge>
          </div>

          <div className="mt-12 grid gap-6 md:grid-cols-3">
            <div className="rounded-[24px] border border-slate-200 bg-white px-6 py-6 shadow-[0_18px_50px_rgba(15,23,42,0.05)]">
              <div className="text-4xl font-black tracking-[-0.05em] text-slate-950">Top 平台</div>
              <div className="mt-3 text-sm leading-6 text-slate-500">腾讯、阿里、字节、美团、蚂蚁、头部券商、核心国央企会优先进入学生向推荐池。</div>
            </div>
            <div className="rounded-[24px] border border-slate-200 bg-white px-6 py-6 shadow-[0_18px_50px_rgba(15,23,42,0.05)]">
              <div className="text-4xl font-black tracking-[-0.05em] text-slate-950">快增强</div>
              <div className="mt-3 text-sm leading-6 text-slate-500">生成 query、搜索公开网页、抽正文，再给出岗位偏技术还是偏业务的轻量画像。</div>
            </div>
            <div className="rounded-[24px] border border-slate-200 bg-white px-6 py-6 shadow-[0_18px_50px_rgba(15,23,42,0.05)]">
              <div className="text-4xl font-black tracking-[-0.05em] text-slate-950">可解释</div>
              <div className="mt-3 text-sm leading-6 text-slate-500">不是只给一个分数，还会告诉你为什么排前面、哪里不确定、下一步该怎么看。</div>
            </div>
          </div>
        </div>

        <div className="lg:sticky lg:top-8 lg:self-start">
          <section className="rounded-[28px] border border-slate-200 bg-white px-8 py-8 shadow-[0_24px_70px_rgba(15,23,42,0.08)]">
            <div className="grid size-16 place-items-center rounded-full bg-sky-50 text-[var(--primary)]">
              {isUploading ? <Loader2 className="size-7 animate-spin" /> : <UploadCloud className="size-7" />}
            </div>

            <h2 className="mt-6 text-2xl font-black tracking-tight text-slate-950">上传你的简历</h2>
            <p className="mt-3 text-sm leading-6 text-slate-600">支持 PDF，先生成第一版推荐，再对前排岗位做 10–20 秒快增强。</p>

            <label className="mt-8 inline-flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl bg-[var(--primary)] px-5 py-3 text-base font-semibold text-white shadow-sm transition hover:bg-[var(--primary-strong)]">
              <input type="file" accept="application/pdf" className="hidden" onChange={onUpload} />
              {isUploading ? <Loader2 className="size-4 animate-spin" /> : <UploadCloud className="size-4" />}
              {isUploading ? '上传中' : '上传简历'}
            </label>

            <div className="mt-5 text-xs leading-6 text-slate-500">最大 10MB。建议使用包含教育、实习、项目与技能信息的简历版本。</div>

            <div className="mt-8 rounded-2xl bg-slate-50 px-4 py-4 text-sm leading-6 text-slate-600">
              上传后你会依次看到：
              <ul className="mt-3 grid gap-2 text-slate-500">
                <li>1. 简历解析与画像确认</li>
                <li>2. 基础推荐与平台优先排序</li>
                <li>3. 代理思考式快增强</li>
              </ul>
            </div>

            {error && <div className="mt-6 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
          </section>
        </div>
      </section>
    </main>
  );
}

function ParsingGate({
  session,
  error,
  onUpload,
  isUploading,
}: {
  session: ResumeCopilotSession | null;
  notice: string;
  error: string;
  onUpload: (event: ChangeEvent<HTMLInputElement>) => void;
  isUploading: boolean;
}) {
  const failed = session?.status === 'failed';

  if (failed) {
    return (
      <main className="hf min-h-screen hf-parchment-grid flex items-center justify-center px-6 py-16">
        <div className="hf-card paper" style={{ padding: 28, borderRadius: 20, maxWidth: 480, textAlign: 'center' }}>
          <div className="hf-h3" style={{ color: 'var(--crimson)', margin: 0, marginBottom: 8 }}>
            解析未能完成
          </div>
          <div className="hf-body" style={{ marginBottom: 18, color: 'var(--ink-soft)' }}>
            {error || '后端返回失败状态，请重新上传或检查模型配置。'}
          </div>
          <label className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold text-white transition" style={{ background: 'var(--terracotta)' }}>
            <input type="file" accept="application/pdf" className="hidden" onChange={onUpload} />
            {isUploading ? <Loader2 className="size-4 animate-spin" /> : <UploadCloud className="size-4" />}
            重新上传
          </label>
        </div>
      </main>
    );
  }

  return (
    <main className="hf min-h-screen hf-parchment-grid flex items-center justify-center">
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
        <span className="hf-spin" style={{ width: 28, height: 28, borderWidth: 2 }} />
        <div className="hf-cap" style={{ color: 'var(--olive)' }}>
          载入工作台…
        </div>
      </div>
    </main>
  );
}

export function PublicResumeCopilot() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialSessionId = Number(searchParams.get('sessionId') ?? 0) || null;

  const [sessionId, setSessionId] = useState<number | null>(initialSessionId);
  const [session, setSession] = useState<ResumeCopilotSession | null>(null);
  const hasAutoLoaded = useRef(false);
  const sessionIdRef = useRef<number | null>(initialSessionId);
  const [profile, setProfile] = useState<ResumeProfilePayload | null>(null);
  const [preferences, setPreferences] = useState<ResumePreferencePayload>(EMPTY_PREFERENCES);
  const [savedPreferences, setSavedPreferences] = useState<ResumePreferencePayload>(EMPTY_PREFERENCES);
  const [recommendations, setRecommendations] = useState<ResumeRecommendationResult | null>(null);
  const [feedback, setFeedback] = useState<ResumeFeedbackResult | null>(null);
  const [directionResults, setDirectionResults] = useState<DirectionTierResult[]>([]);
  const [activeDirection, setActiveDirection] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<CopilotMessage[]>([]);
  const [isSendingChat, setIsSendingChat] = useState(false);
  const [applyingOption, setApplyingOption] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [resumeHistory, setResumeHistory] = useState<ResumeHistoryItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [pollStartedAt, setPollStartedAt] = useState<number | null>(null);
  const [pollErrorStreak, setPollErrorStreak] = useState(0);
  const [pollGaveUp, setPollGaveUp] = useState(false);

  const currentProfile = profile ?? EMPTY_PROFILE;
  const designParam = searchParams.get('design');
  const designVariant = designParam === 'apple' || designParam === 'default' ? designParam : 'claude';

  const refreshHistory = useCallback(async () => {
    try {
      const items = await listResumeCopilotSessions();
      setResumeHistory(items.map(mapListItem));
      return items;
    } catch {
      return [];
    }
  }, []);

  useEffect(() => {
    refreshHistory().then((items) => {
      if (!hasAutoLoaded.current && !sessionIdRef.current && items && items.length > 0) {
        hasAutoLoaded.current = true;
        const firstId = items[0].id;
        sessionIdRef.current = firstId;
        setSessionId(firstId);
        router.replace(`/resume-copilot?sessionId=${firstId}`);
      }
    });
  }, [refreshHistory]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadSession = useCallback(async (id: number) => {
    const nextSession = await getResumeCopilotSession(id);
    setSession(nextSession);
    refreshHistory();
    if (nextSession.status === 'failed' && nextSession.error_message) {
      setError(nextSession.error_message);
    }

    if (nextSession.has_parsed_profile) {
      try {
        const parsed = await getResumeCopilotParsedProfile(id);
        setProfile((existing) => existing ?? parsed.profile);
      } catch {
        // Parsed profile may not be committed yet during a tight polling window.
      }
    }

    if (nextSession.has_recommendations || nextSession.recommendation_status === 'running') {
      try {
        setRecommendations(await getResumeCopilotRecommendations(id));
      } catch {
        // Recommendation run is created asynchronously after generation starts.
      }
    }

    if (nextSession.has_feedback || nextSession.feedback_status === 'running') {
      try {
        setFeedback(await getResumeCopilotFeedback(id));
      } catch {
        // Feedback follows the same async lifecycle.
      }
    }

    if (nextSession.has_preferences) {
      try {
        const prefOut = await getResumeCopilotPreferences(id);
        setSavedPreferences(prefOut.preferences);
        setPreferences(prefOut.preferences);
      } catch {
        // Preferences may not be committed yet.
      }
    }
  }, [refreshHistory]);

  useEffect(() => {
    if (!sessionId) return;

    let cancelled = false;
    loadSession(sessionId).catch(async (reason: unknown) => {
      if (cancelled) return;
      const msg = reason instanceof Error ? reason.message : String(reason);
      if (msg.toLowerCase().includes('not found')) {
        const items = await refreshHistory();
        if (cancelled) return;
        if (items && items.length > 0) {
          sessionIdRef.current = items[0].id;
          setSessionId(items[0].id);
          router.replace(`/resume-copilot?sessionId=${items[0].id}`);
        } else {
          sessionIdRef.current = null;
          setSessionId(null);
          router.replace('/resume-copilot');
        }
      } else {
        setError(msg);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [loadSession, sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!sessionId || !sessionIsActive(session)) {
      setPollStartedAt(null);
      setPollErrorStreak(0);
      setPollGaveUp(false);
      return;
    }
    if (pollGaveUp) return;
    if (pollStartedAt == null) setPollStartedAt(Date.now());

    const timer = window.setInterval(() => {
      if (pollStartedAt != null && Date.now() - pollStartedAt > POLL_MAX_DURATION_MS) {
        setPollGaveUp(true);
        return;
      }
      loadSession(sessionId)
        .then(() => setPollErrorStreak(0))
        .catch((reason: unknown) => {
          setPollErrorStreak((n) => n + 1);
          setError(reason instanceof Error ? reason.message : '刷新状态失败');
        });
    }, 1600);

    return () => window.clearInterval(timer);
  }, [loadSession, session, sessionId, pollStartedAt, pollGaveUp]);

  useEffect(() => {
    if (session?.has_parsed_profile && profile && !editorOpen) {
      setNotice('AI 已生成结构化画像。你可以先看右侧预览，需要修改时再展开编辑模块。');
    }
  }, [editorOpen, profile, session?.has_parsed_profile]);

  useEffect(() => {
    if (!session || session.feedback_status !== 'completed') return;
    getDirectionAnalysis(session.id).then((results) => {
      setDirectionResults(results);
      if (results.length > 0 && !activeDirection) {
        const sorted = [...results].sort((a, b) => a.tier - b.tier);
        setActiveDirection(sorted[0].direction);
      }
    }).catch(() => {});
  }, [session?.feedback_status, session?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!sessionId) {
      setChatMessages([]);
      return;
    }
    if (!session || session.feedback_status !== 'completed') return;
    let cancelled = false;
    getChatMessages(sessionId).then((msgs) => {
      if (!cancelled) setChatMessages(msgs);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [sessionId, session?.feedback_status]); // eslint-disable-line react-hooks/exhaustive-deps

  const updateProfile = (updater: (profile: ResumeProfilePayload) => ResumeProfilePayload) => {
    setProfile((previous) => updater(previous ?? EMPTY_PROFILE));
  };

  const sendChatMessage = async (content: string): Promise<void> => {
    if (!sessionId || isSendingChat) return;
    const trimmed = content.trim();
    if (!trimmed) return;
    const optimistic: CopilotMessage = {
      id: -Date.now(),
      role: 'user',
      content: trimmed,
      rewrite_options: null,
      applied_option_id: null,
      created_at: new Date().toISOString(),
    };
    setChatMessages((prev) => [...prev, optimistic]);
    setIsSendingChat(true);
    setError('');
    try {
      const assistantMsg = await postChatMessage(sessionId, trimmed);
      const refreshed = await getChatMessages(sessionId).catch(() => null);
      if (refreshed) {
        setChatMessages(refreshed);
      } else {
        setChatMessages((prev) => [
          ...prev.filter((m) => m.id !== optimistic.id),
          optimistic,
          assistantMsg,
        ]);
      }
    } catch (reason) {
      setChatMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
      setError(reason instanceof Error ? reason.message : '发送失败，请稍后再试');
    } finally {
      setIsSendingChat(false);
    }
  };

  const applyRewriteOption = async (messageId: number, optionId: string): Promise<void> => {
    if (!sessionId || applyingOption) return;
    setApplyingOption(`${messageId}:${optionId}`);
    setError('');
    try {
      const result = await postApplyRewrite(sessionId, messageId, optionId);
      setProfile(result.profile);
      setChatMessages((prev) => prev.map((m) =>
        m.id === messageId ? { ...m, applied_option_id: optionId } : m,
      ));
      setNotice('已将改写应用到简历。');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '应用改写失败');
    } finally {
      setApplyingOption(null);
    }
  };

  const updateBasicInfo = (key: string, value: string) => {
    updateProfile((previous) => ({
      ...previous,
      basic_info: {
        ...previous.basic_info,
        [key]: value,
      },
    }));
  };

  const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setError('');
    setNotice('');
    setIsUploading(true);
    setEditorOpen(false);
    setRecommendations(null);
    setFeedback(null);
    hasAutoLoaded.current = true; // prevent auto-load from overriding this upload

    try {
      const created = await createResumeCopilotSession(file);
      sessionIdRef.current = created.session_id;
      setSessionId(created.session_id);
      setSession({
        id: created.session_id,
        file_name: file.name,
        name: '',
        status: created.status,
        error_message: '',
        recommendation_status: 'pending',
        feedback_status: 'pending',
        has_parsed_profile: false,
        has_confirmed_profile: false,
        has_preferences: false,
        has_recommendations: false,
        has_feedback: false,
        has_direction_analysis: false,
        created_at: null,
        updated_at: null,
        finished_at: null,
      });
      setProfile(null);
      router.replace(`/resume-copilot?sessionId=${created.session_id}`);
      refreshHistory();
      setNotice('已创建解析任务。中间会显示 AI 简历助手进度，右侧预览会在解析完成后出现。');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '上传失败，请检查 PDF 文件');
    } finally {
      setIsUploading(false);
      event.target.value = '';
    }
  };

  const saveProfile = async () => {
    if (!sessionId || !profile) return;
    setError('');
    setNotice('');
    setIsSaving(true);
    try {
      await putResumeCopilotConfirmedProfile(sessionId, profile);
      await loadSession(sessionId);
      setEditorOpen(false);
      setNotice('简历画像已确认。现在可以填写偏好，也可以直接生成推荐。');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '保存简历画像失败');
    } finally {
      setIsSaving(false);
    }
  };

  const savePreferences = async (nextPreferences = preferences) => {
    if (!sessionId) return;
    setError('');
    setNotice('');
    setIsSaving(true);
    try {
      await putResumeCopilotPreferences(sessionId, nextPreferences);
      setSavedPreferences(nextPreferences);
      await loadSession(sessionId);
      setNotice(nextPreferences.all_skipped ? '已跳过偏好，将只基于简历客观信息推荐。' : '求职偏好已保存。');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '保存偏好失败');
    } finally {
      setIsSaving(false);
    }
  };

  const generate = async () => {
    if (!sessionId || !profile) return;
    setError('');
    setNotice('');
    setIsGenerating(true);
    try {
      await putResumeCopilotConfirmedProfile(sessionId, profile);
      await putResumeCopilotPreferences(sessionId, preferences);
      await postResumeCopilotGenerate(sessionId);
      await loadSession(sessionId);
      setEditorOpen(false);
      setNotice('推荐与反馈生成中，完成后会自动刷新到结果区。');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '生成推荐失败');
    } finally {
      setIsGenerating(false);
    }
  };

  const skipPreferences = () => {
    const skipped = {
      ...EMPTY_PREFERENCES,
      all_skipped: true,
    };
    setPreferences(skipped);
    void savePreferences(skipped);
  };

  const switchResumeSession = (nextSessionId: number) => {
    if (nextSessionId === sessionId) return;
    sessionIdRef.current = nextSessionId;
    setError('');
    setNotice('');
    setSessionId(nextSessionId);
    setSession(null);
    setProfile(null);
    setEditorOpen(false);
    setRecommendations(null);
    setFeedback(null);
    setDirectionResults([]);
    setActiveDirection(null);
    router.replace(`/resume-copilot?sessionId=${nextSessionId}`);
  };

  const handleRenameSession = async (id: number, name: string) => {
    try {
      await renameResumeCopilotSession(id, name);
      setResumeHistory((prev) => prev.map((item) => (item.id === id ? { ...item, name } : item)));
      if (session && session.id === id) setSession((s) => (s ? { ...s, name } : s));
    } catch {
      // Rename failure is non-critical — ignore silently.
    }
  };

  const handleDeleteSession = async (id: number) => {
    try {
      await deleteResumeCopilotSession(id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '删除简历失败');
      return;
    }
    const remaining = resumeHistory.filter((item) => item.id !== id);
    setResumeHistory(remaining);
    if (sessionId === id) {
      if (remaining.length > 0) {
        const nextId = remaining[0].id;
        sessionIdRef.current = nextId;
        setError('');
        setNotice('');
        setSessionId(nextId);
        router.replace(`/resume-copilot?sessionId=${nextId}`);
        setSession(null);
        setProfile(null);
        setRecommendations(null);
        setFeedback(null);
      } else {
        sessionIdRef.current = null;
        hasAutoLoaded.current = true;
        setSessionId(null);
        setSession(null);
        setProfile(null);
        setRecommendations(null);
        setFeedback(null);
        router.replace('/resume-copilot');
      }
    }
    void refreshHistory();
  };

  if (!sessionId && !profile) {
    return <LandingUploadGate onUpload={handleUpload} isUploading={isUploading} error={error} />;
  }

  if (sessionId && !profile) {
    return (
      <ParsingGate
        session={session}
        notice={notice}
        error={error}
        onUpload={handleUpload}
        isUploading={isUploading}
      />
    );
  }

  return (
    <main className={cn('resume-copilot-shell min-h-screen bg-[#f6f7f8] text-slate-950', `resume-design-${designVariant}`)}>
      {sessionId === DEMO_SESSION_ID && <DemoBanner />}
      {sessionId && pollErrorStreak >= POLL_ERROR_LIMIT && !pollGaveUp ? (
        <div style={{ padding: '8px 12px', background: 'var(--soft-blue, #eef4ff)', border: '1px solid var(--border, #d8dde3)', borderRadius: 8, fontSize: 13, color: 'var(--ink, #2c3036)' }}>
          连接不稳定（连续 {pollErrorStreak} 次失败）。
          <button
            type="button"
            style={{ marginLeft: 8, color: 'var(--primary, #2563eb)', background: 'none', border: 'none', padding: 0, cursor: 'pointer', textDecoration: 'underline' }}
            onClick={() => {
              setPollErrorStreak(0);
              setError('');
              if (sessionId) loadSession(sessionId).catch(() => {});
            }}
          >
            重试
          </button>
        </div>
      ) : null}
      {pollGaveUp ? (
        <div style={{ padding: '8px 12px', background: 'var(--soft-blue, #eef4ff)', border: '1px solid var(--border, #d8dde3)', borderRadius: 8, fontSize: 13, color: 'var(--ink, #2c3036)' }}>
          刷新状态已停止（持续 5 分钟未完成）。
          <button
            type="button"
            style={{ marginLeft: 8, color: 'var(--primary, #2563eb)', background: 'none', border: 'none', padding: 0, cursor: 'pointer', textDecoration: 'underline' }}
            onClick={() => {
              setPollGaveUp(false);
              setPollStartedAt(Date.now());
              setPollErrorStreak(0);
            }}
          >
            恢复轮询
          </button>
        </div>
      ) : null}
      <section className="grid min-h-screen lg:grid-cols-[minmax(560px,52vw)_minmax(0,1fr)]">
        <ResumeChatRail
          session={session}
          notice={notice}
          error={error}
          preferences={preferences}
          savedPreferences={savedPreferences}
          setPreferences={setPreferences}
          savePreferences={savePreferences}
          skipPreferences={skipPreferences}
          generate={generate}
          isSaving={isSaving}
          isGenerating={isGenerating}
          recommendations={recommendations}
          feedback={feedback}
          directionResults={directionResults}
          activeDirection={activeDirection}
          onSetActiveDirection={setActiveDirection}
          currentSessionId={sessionId}
          resumeHistory={resumeHistory}
          onSwitchSession={switchResumeSession}
          onRenameSession={handleRenameSession}
          onDeleteSession={handleDeleteSession}
          onUpload={handleUpload}
          isUploading={isUploading}
          chatMessages={chatMessages}
          sendChatMessage={sendChatMessage}
          applyRewriteOption={applyRewriteOption}
          isSendingChat={isSendingChat}
          applyingOption={applyingOption}
        />
        <EditableResumeCanvas
          profile={currentProfile}
          updateProfile={updateProfile}
          updateBasicInfo={updateBasicInfo}
          onSave={saveProfile}
          isSaving={isSaving}
        />
      </section>
    </main>
  );
}

function ChatMessageBubble({
  message,
  applyingOption,
  onApply,
  isDemo = false,
}: {
  message: CopilotMessage;
  applyingOption: string | null;
  onApply: (messageId: number, optionId: string) => Promise<void>;
  isDemo?: boolean;
}) {
  if (message.role === 'user') {
    return (
      <div className="ml-auto max-w-[88%] rounded-2xl rounded-tr-md bg-[var(--primary)] px-4 py-3 text-sm leading-6 text-white">
        {message.content}
      </div>
    );
  }

  const isSystem = message.role === 'system';
  const options = message.rewrite_options ?? [];

  return (
    <div
      className={cn(
        'max-w-[92%] rounded-2xl rounded-tl-md px-4 py-3 text-sm leading-6',
        isSystem ? 'bg-amber-50 text-amber-900' : 'bg-slate-50 text-slate-700',
      )}
    >
      <div className="whitespace-pre-wrap">{message.content}</div>
      {options.length > 0 && (
        <div className="mt-3 grid gap-2">
          {options.map((opt) => (
            <RewriteOptionCard
              key={opt.option_id}
              messageId={message.id}
              option={opt}
              applied={message.applied_option_id === opt.option_id}
              disabled={Boolean(message.applied_option_id) || applyingOption !== null || isDemo}
              isApplying={applyingOption === `${message.id}:${opt.option_id}`}
              onApply={onApply}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function RewriteOptionCard({
  messageId,
  option,
  applied,
  disabled,
  isApplying,
  onApply,
}: {
  messageId: number;
  option: RewriteOption;
  applied: boolean;
  disabled: boolean;
  isApplying: boolean;
  onApply: (messageId: number, optionId: string) => Promise<void>;
}) {
  const originalLines = option.original ?? [];
  const improvedLines = option.improved ?? [];
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-semibold text-slate-950">{option.label || `方案 ${option.option_id}`}</div>
          {option.target_title && (
            <div className="mt-0.5 truncate text-[11px] text-slate-500">{option.target_title}</div>
          )}
        </div>
        <Badge className="shrink-0 bg-slate-100 text-[10px] text-slate-500">{option.section || option.field_path}</Badge>
      </div>
      {originalLines.length > 0 && (
        <div className="mt-2 rounded-lg bg-slate-50 px-2.5 py-2 text-xs leading-5 text-slate-500">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">原文</div>
          <ul className="list-disc space-y-1 pl-4">
            {originalLines.map((line, idx) => (
              <li key={idx}>{line}</li>
            ))}
          </ul>
        </div>
      )}
      {improvedLines.length > 0 && (
        <div className="mt-2 rounded-lg bg-emerald-50 px-2.5 py-2 text-xs leading-5 text-emerald-900">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-emerald-600">改写</div>
          <ul className="list-disc space-y-1 pl-4">
            {improvedLines.map((line, idx) => (
              <li key={idx}>{line}</li>
            ))}
          </ul>
        </div>
      )}
      {option.rationale && (
        <div className="mt-2 text-[11px] leading-5 text-slate-500">理由：{option.rationale}</div>
      )}
      <div className="mt-3 flex justify-end">
        <Button
          type="button"
          size="sm"
          variant={applied ? 'secondary' : 'default'}
          disabled={disabled || applied}
          onClick={() => void onApply(messageId, option.option_id)}
        >
          {isApplying ? <Loader2 className="size-3.5 animate-spin" /> : applied ? <Check className="size-3.5" /> : null}
          {applied ? '已应用' : '一键应用到简历'}
        </Button>
      </div>
    </div>
  );
}


function ResumeChatRail({
  session,
  notice,
  error,
  preferences,
  savedPreferences,
  setPreferences,
  savePreferences,
  skipPreferences,
  generate,
  isSaving,
  isGenerating,
  recommendations,
  feedback,
  directionResults,
  activeDirection,
  onSetActiveDirection,
  currentSessionId,
  resumeHistory,
  onSwitchSession,
  onRenameSession,
  onDeleteSession,
  onUpload,
  isUploading,
  chatMessages,
  sendChatMessage,
  applyRewriteOption,
  isSendingChat,
  applyingOption,
}: {
  session: ResumeCopilotSession | null;
  notice: string;
  error: string;
  preferences: ResumePreferencePayload;
  savedPreferences: ResumePreferencePayload;
  setPreferences: Dispatch<SetStateAction<ResumePreferencePayload>>;
  savePreferences: () => Promise<void>;
  skipPreferences: () => void;
  generate: () => Promise<void>;
  isSaving: boolean;
  isGenerating: boolean;
  recommendations: ResumeRecommendationResult | null;
  feedback: ResumeFeedbackResult | null;
  directionResults: DirectionTierResult[];
  activeDirection: string | null;
  onSetActiveDirection: (direction: string) => void;
  currentSessionId: number | null;
  resumeHistory: ResumeHistoryItem[];
  onSwitchSession: (sessionId: number) => void;
  onRenameSession: (id: number, name: string) => void;
  onDeleteSession: (id: number) => void;
  onUpload: (event: ChangeEvent<HTMLInputElement>) => void;
  isUploading: boolean;
  chatMessages: CopilotMessage[];
  sendChatMessage: (content: string) => Promise<void>;
  applyRewriteOption: (messageId: number, optionId: string) => Promise<void>;
  isSendingChat: boolean;
  applyingOption: string | null;
}) {
  const [draft, setDraft] = useState('');
  const [targetOpen, setTargetOpen] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(true);
  const [contextMenu, setContextMenu] = useState<{ id: number; x: number; y: number } | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingName, setEditingName] = useState('');
  const contextMenuRef = useRef<HTMLDivElement>(null);
  const isDemoSession = currentSessionId === DEMO_SESSION_ID;
  const canChat = Boolean(session?.has_parsed_profile) && !sessionIsActive(session) && !isDemoSession;
  const selectedRoles = preferences.preferred_roles.length ? preferences.preferred_roles.join('、') : '未设定';
  const selectedTracks = preferences.preferred_tracks.length ? preferences.preferred_tracks.join('、') : '未设定';
  const selectedLocations = preferences.preferred_locations.length ? preferences.preferred_locations.join('、') : '未设定';
  const selectedCompanyTypes = preferences.preferred_company_types.length ? preferences.preferred_company_types.join('、') : '未设定';
  const activeDirectionResult = directionResults.find(r => r.direction === activeDirection) ?? null;
  const filteredRecommendations = activeDirection
    ? (recommendations?.items ?? []).filter(r => !r.target_direction || r.target_direction === activeDirection)
    : (recommendations?.items ?? []);
  const topRecommendations = filteredRecommendations.slice(0, 5);
  const recommendationFallback = formatModelFallback(recommendations?.fallback_reason);
  const feedbackFallback = formatModelFallback(feedback?.error_message);

  useEffect(() => {
    if (!contextMenu) return;
    const handleClick = (e: MouseEvent) => {
      if (!contextMenuRef.current?.contains(e.target as Node)) setContextMenu(null);
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [contextMenu]);

  const commitRename = (id: number) => {
    const trimmed = editingName.trim();
    if (trimmed) onRenameSession(id, trimmed);
    setEditingId(null);
    setEditingName('');
  };

  const sendMessage = () => {
    const content = draft.trim();
    if (!content || !canChat || isSendingChat) return;
    setDraft('');
    void sendChatMessage(content);
  };

  const interviewRouter = useRouter();
  const handleStartInterview = (item: ResumeRecommendationItem) => {
    const targetJob = [item.job_title, item.company].filter(Boolean).join(' · ');
    if (!targetJob) return;
    const sessionId = crypto.randomUUID();
    try {
      window.localStorage.setItem(`interview.pending.${sessionId}`, targetJob);
    } catch {
      /* localStorage unavailable — interview page will fall back to empty target */
    }
    interviewRouter.push(`/interview/${sessionId}/check`);
  };

  return (
    <aside className="resume-chat-shell min-h-screen border-r border-slate-200 bg-white">
      <div className={cn('grid h-screen transition-[grid-template-columns] duration-200', libraryOpen ? 'grid-cols-[300px_minmax(0,1fr)]' : 'grid-cols-[64px_minmax(0,1fr)]')}>
        {libraryOpen ? (
          <aside className="resume-library-panel flex min-w-0 flex-col border-r border-slate-200 bg-[#f6f7fa]">
            <div className="resume-library-header flex h-[60px] items-center justify-between border-b border-slate-200 px-5">
              <div className="flex min-w-0 items-center gap-3">
                <HFLogo label="简历雷达" />
              </div>
              <button
                type="button"
                className="grid size-8 place-items-center rounded-lg text-slate-600 transition hover:bg-white hover:text-slate-950"
                aria-label="收起简历管理"
                onClick={() => setLibraryOpen(false)}
              >
                <ChevronDown className="size-4 -rotate-90" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-4">
              <label className="resume-new-session mb-5 flex h-11 cursor-pointer items-center justify-center gap-3 rounded-lg bg-[var(--primary)] px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-[var(--primary-strong)]">
                <input type="file" accept="application/pdf" className="hidden" onChange={onUpload} />
                {isUploading ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
                新建会话
              </label>

              <div className="mb-3 text-sm font-medium text-slate-500">我的简历</div>
              <div className="grid gap-1.5">
                {resumeHistory.length > 0 ? (
                  resumeHistory.map((item, index) => {
                    const displayName = item.name || (item.fileName ? item.fileName.replace(/\.pdf$/i, '') : `新简历 ${resumeHistory.length - index}`);
                    const isActive = currentSessionId === item.id;
                    const isEditing = editingId === item.id;
                    return (
                      <div
                        key={item.id}
                        className={cn(
                          'resume-history-item group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-left transition',
                          isActive ? 'bg-slate-200/70 text-slate-950' : 'text-slate-600 hover:bg-white',
                        )}
                        onContextMenu={(e) => {
                          e.preventDefault();
                          setContextMenu({ id: item.id, x: e.clientX, y: e.clientY });
                        }}
                      >
                        <FileText className={cn('size-4 shrink-0', isActive ? 'text-[var(--primary)]' : 'text-slate-400')} />
                        <span className="min-w-0 flex-1" onClick={() => !isEditing && onSwitchSession(item.id)}>
                          {isEditing ? (
                            <input
                              autoFocus
                              className="w-full rounded border border-[var(--primary)] bg-white px-1.5 py-0.5 text-sm font-semibold text-slate-950 outline-none"
                              value={editingName}
                              onChange={(e) => setEditingName(e.target.value)}
                              onBlur={() => commitRename(item.id)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') commitRename(item.id);
                                if (e.key === 'Escape') { setEditingId(null); setEditingName(''); }
                              }}
                              onClick={(e) => e.stopPropagation()}
                            />
                          ) : (
                            <>
                              <span className="block truncate text-sm font-semibold">{displayName}</span>
                              <span className="mt-0.5 block text-xs text-slate-400">
                                {isActive ? '当前简历' : (timeAgo(item.updatedAt) || '最近使用')}
                              </span>
                            </>
                          )}
                        </span>
                      </div>
                    );
                  })
                ) : (
                  <div className="rounded-xl bg-white px-3 py-4 text-sm leading-6 text-slate-400">上传简历后，会在这里管理不同版本。</div>
                )}
              </div>

              {/* Right-click context menu */}
              {contextMenu && (
                <div
                  ref={contextMenuRef}
                  className="fixed z-50 min-w-[140px] overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg"
                  style={{ left: contextMenu.x, top: contextMenu.y }}
                >
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50"
                    onClick={() => {
                      const item = resumeHistory.find((h) => h.id === contextMenu.id);
                      setEditingId(contextMenu.id);
                      setEditingName(item?.name || item?.fileName?.replace(/\.pdf$/i, '') || '');
                      setContextMenu(null);
                    }}
                  >
                    <PencilLine className="size-3.5 shrink-0 text-slate-400" />
                    重命名
                  </button>
                  <div className="my-1 h-px bg-slate-100" />
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50"
                    onClick={() => {
                      onDeleteSession(contextMenu.id);
                      setContextMenu(null);
                    }}
                  >
                    <Trash2 className="size-3.5 shrink-0" />
                    删除
                  </button>
                </div>
              )}
            </div>

            <button
              type="button"
              className="flex h-14 items-center gap-3 border-t border-slate-200 px-6 text-sm font-medium text-slate-600 transition hover:bg-white hover:text-slate-950"
            >
              <Home className="size-4" />
              返回首页
            </button>
          </aside>
        ) : (
          <nav className="resume-library-rail flex flex-col items-center border-r border-slate-200 bg-[#f6f7fa] py-3">
          <button
            type="button"
            className="grid size-9 place-items-center rounded-xl text-slate-500 transition hover:bg-white hover:text-slate-900"
            aria-label="展开简历管理"
            onClick={() => setLibraryOpen(true)}
          >
            <ChevronDown className="size-4 rotate-90" />
          </button>

          <label className="mt-5 grid size-10 cursor-pointer place-items-center rounded-lg bg-[var(--primary)] text-white shadow-sm transition hover:bg-[var(--primary-strong)]">
            <input type="file" accept="application/pdf" className="hidden" onChange={onUpload} />
            {isUploading ? <Loader2 className="size-5 animate-spin" /> : <Plus className="size-5" />}
          </label>

          <div className="mt-5 grid gap-2">
            {resumeHistory.slice(0, 4).map((item) => (
              <button
                key={item.id}
                type="button"
                title={item.fileName}
                className={cn(
                  'grid size-9 place-items-center rounded-lg text-slate-500 transition hover:bg-white hover:text-slate-900',
                  currentSessionId === item.id && 'bg-slate-200 text-slate-800',
                )}
                onClick={() => onSwitchSession(item.id)}
              >
                <FileText className="size-4" />
              </button>
            ))}
          </div>

          <button
            type="button"
            className="mt-auto grid size-9 place-items-center rounded-lg text-slate-500 transition hover:bg-white hover:text-slate-900"
            aria-label="返回首页"
          >
            <Home className="size-4" />
          </button>
          </nav>
        )}

        <div className="resume-ai-panel flex min-w-0 flex-col bg-white">
          <header className="resume-ai-header flex h-[60px] items-center justify-between border-b border-slate-200 px-4">
            <div className="flex items-center gap-3">
              <span className="grid size-10 place-items-center rounded-full bg-[var(--primary)] text-white">
                <Sparkles className="size-5" />
              </span>
              <div>
                <div className="text-[16px] font-semibold leading-tight tracking-tight text-slate-950">AI 简历助手</div>
                <div className="mt-0.5 text-xs leading-tight text-slate-500">AI 简历助手</div>
              </div>
            </div>
            {sessionIsActive(session) ? (
              <Loader2 className="size-4 animate-spin text-[var(--primary)]" />
            ) : (
              <Check className="size-4 text-emerald-500" />
            )}
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
            <p className="resume-ai-status text-sm leading-6 text-slate-600">
              {!canChat
                ? '等待首次分析完成后可对话。'
                : topRecommendations.length
                  ? '已基于当前真实岗位库生成初筛推荐。你可以修改目标岗位后重新分析。'
                  : '暂无分析结果。如需重新分析，请在下方修改目标岗位后点击“保存并重新分析”。'}
            </p>

            <div className="mt-5 grid gap-3">
              {notice && <div className="max-w-[88%] rounded-2xl rounded-tl-md bg-emerald-50 px-4 py-3 text-sm leading-6 text-emerald-700">{notice}</div>}
              {error && <div className="max-w-[88%] rounded-2xl rounded-tl-md bg-red-50 px-4 py-3 text-sm leading-6 text-red-700">{error}</div>}
              <AgentThinkingPanel trace={recommendations?.agent_trace ?? []} running={Boolean(session?.recommendation_status === 'running')} />

              {chatMessages.map((message) => (
                <ChatMessageBubble
                  key={message.id}
                  message={message}
                  applyingOption={applyingOption}
                  onApply={applyRewriteOption}
                  isDemo={isDemoSession}
                />
              ))}
              {isSendingChat && (
                <div className="max-w-[88%] rounded-2xl rounded-tl-md bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-500">
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="size-3.5 animate-spin" />
                    AI 思考中…
                  </span>
                </div>
              )}

              {topRecommendations.length > 0 ? (
                <div className="max-w-[92%] rounded-2xl rounded-tl-md bg-slate-50 text-sm text-slate-700" style={{ overflow: 'hidden' }}>
                  <div className="flex items-center justify-between gap-3 px-4 pt-3">
                    <div className="font-semibold text-slate-950">真实岗位推荐 Top 5</div>
                    <Badge className="bg-white text-slate-500">{recommendations?.used_ai ? 'AI 重排' : '规则排序'}</Badge>
                  </div>
                  {directionResults.length > 0 && (
                    <div style={{ display: 'flex', gap: 6, padding: '10px 12px 0', flexWrap: 'wrap', borderBottom: '1px solid var(--border)' }}>
                      {directionResults.map((dr) => {
                        const isActive = activeDirection === dr.direction;
                        const badgeColor = dr.tier === 1 ? { bg: '#dcfce7', color: '#166534' }
                          : dr.tier === 2 ? { bg: '#fef9c3', color: '#854d0e' }
                          : { bg: '#fee2e2', color: '#991b1b' };
                        return (
                          <button
                            key={dr.direction}
                            onClick={() => onSetActiveDirection(dr.direction)}
                            style={{
                              padding: '5px 12px 8px',
                              borderRadius: '8px 8px 0 0',
                              border: `1px solid ${isActive ? 'var(--border)' : 'transparent'}`,
                              borderBottom: isActive ? '1px solid white' : '1px solid transparent',
                              background: isActive ? 'white' : 'transparent',
                              color: isActive ? 'var(--ink)' : 'var(--muted)',
                              fontWeight: isActive ? 600 : 400,
                              fontSize: 12,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: 6,
                              position: 'relative',
                              bottom: -1,
                            }}
                          >
                            {dr.direction}
                            <span style={{ background: badgeColor.bg, color: badgeColor.color, borderRadius: 10, padding: '1px 7px', fontSize: 10, fontWeight: 600 }}>
                              {dr.tier_label}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                  <div className="px-4 pb-3">
                  {recommendationFallback && (
                    <div className="mt-2 rounded-lg bg-white px-3 py-2 text-xs leading-5 text-slate-500">
                      AI 重排未启用：{recommendationFallback}
                    </div>
                  )}
                  {feedback?.status === 'failed' && (
                    <div className="mt-2 rounded-lg bg-white px-3 py-2 text-xs leading-5 text-slate-500">
                      简历反馈暂未生成：{feedbackFallback || '外部模型暂不可用'}
                    </div>
                  )}
                  <div className="mt-3 grid gap-2">
                    {activeDirectionResult?.tier === 2 && activeDirectionResult.transferable_from.length > 0 && (
                      <div style={{ background: '#fefce8', border: '1px solid #fde68a', borderRadius: 8, padding: '8px 12px', fontSize: 11.5, color: '#78350f', marginBottom: 8, lineHeight: 1.5 }}>
                        💡 <strong>可迁移方向</strong> · {activeDirectionResult.transferable_from[0]}——右侧对话可帮你改写表达
                      </div>
                    )}
                    {activeDirectionResult?.tier === 3 && (
                      <div style={{ background: '#fff1f2', border: '1px solid #fecdd3', borderRadius: 8, padding: '8px 12px', fontSize: 11.5, color: '#881337', marginBottom: 8, lineHeight: 1.5 }}>
                        ⚠️ <strong>差距较大</strong>{activeDirectionResult.gaps.length > 0 ? ` · 缺少：${activeDirectionResult.gaps.slice(0, 2).join('、')}` : ''}。当前为你推荐接受零经验的入门机会。
                      </div>
                    )}
                    {topRecommendations.map((item, index) => (
                      <div
                        key={`${item.job_id}-${item.company}`}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 transition hover:border-[var(--primary)] hover:shadow-sm"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="truncate text-sm font-semibold text-slate-950">
                              {index + 1}. {item.job_title}
                            </div>
                            <div className="mt-1 truncate text-xs text-slate-500">
                              {item.company} · {item.location || '地点待确认'}
                            </div>
                          </div>
                          <div className="flex shrink-0 items-center gap-1 text-xs font-semibold text-[var(--primary)]">
                            {Math.round(item.final_score)}
                          </div>
                        </div>
                        <div className="mt-2 text-[11px] leading-4 text-slate-400">
                          规则分 {item.base_match_score} · 增强分 {item.enhanced_score} · 最终分 {item.final_score}
                          {item.company_priority_label ? ` · ${item.company_priority_label}` : ''}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {item.company_priority_label && (
                            <Badge className="border-[var(--primary-ring)] bg-[var(--soft-blue)] text-[var(--primary-strong)]">
                              {item.company_priority_label}
                            </Badge>
                          )}
                          <Badge className={enrichmentBadgeClass(item.topic_cache_status, item.need_enrichment)}>
                            {enrichmentStatusLabel(item.topic_cache_status, item.need_enrichment)}
                          </Badge>
                        </div>
                        <div className="mt-3 flex flex-wrap items-center gap-2">
                          {item.detail_url && (
                            <a
                              href={item.detail_url}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-[11px] font-medium text-slate-600 transition hover:border-[var(--primary)] hover:text-[var(--primary)]"
                            >
                              查看岗位 <ArrowUpRight className="size-3" />
                            </a>
                          )}
                          <button
                            type="button"
                            onClick={() => handleStartInterview(item)}
                            className="inline-flex items-center gap-1 rounded-md bg-[var(--primary)] px-2 py-1 text-[11px] font-medium text-white transition hover:bg-[var(--primary-strong)]"
                          >
                            <Sparkles className="size-3" /> 模拟面试
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                  </div>
                </div>
              ) : null}
            </div>
          </div>

          <div className="border-t border-slate-200 bg-white px-4 py-4">
            <div className="resume-target-card rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_4px_16px_rgba(15,23,42,0.08)]">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="mb-1 flex items-center gap-2 text-sm font-semibold">
                    修改目标岗位
                    <Badge className="bg-slate-100 text-slate-500">已确认</Badge>
                  </div>
                  <div className="text-sm font-medium text-slate-900">{selectedRoles}</div>
                  <div className="mt-1 text-xs leading-5 text-slate-500">
                    {selectedTracks} · {selectedLocations} · {selectedCompanyTypes}
                  </div>
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  className="shrink-0"
                  onClick={() => setTargetOpen((value) => {
                    if (!value) setPreferences(savedPreferences);
                    return !value;
                  })}
                >
                  <PencilLine className="size-4" />
                  修改目标岗位
                  <ChevronDown className={cn('size-4 transition-transform', targetOpen && 'rotate-180')} />
                </Button>
              </div>

              {targetOpen && (
                <div className="mt-4 grid gap-4 border-t border-slate-100 pt-4">
                  <div className="text-xs leading-5 text-slate-400">岗位大类、目标岗位、地点和公司类型会影响后续推荐排序。</div>
                  <OptionPills
                    label="目标赛道"
                    options={TRACK_OPTIONS}
                    values={preferences.preferred_tracks}
                    onChange={(values) => setPreferences((previous) => ({ ...previous, preferred_tracks: values, all_skipped: false }))}
                  />
                  <OptionPills
                    label="岗位方向"
                    options={ROLE_OPTIONS}
                    values={preferences.preferred_roles}
                    onChange={(values) => setPreferences((previous) => ({ ...previous, preferred_roles: values, all_skipped: false }))}
                  />
                  <OptionPills
                    label="地点偏好"
                    options={LOCATION_OPTIONS}
                    values={preferences.preferred_locations}
                    onChange={(values) => setPreferences((previous) => ({ ...previous, preferred_locations: values, all_skipped: false }))}
                  />
                  <OptionPills
                    label="公司类型"
                    options={COMPANY_OPTIONS}
                    values={preferences.preferred_company_types}
                    onChange={(values) =>
                      setPreferences((previous) => ({ ...previous, preferred_company_types: values, all_skipped: false }))
                    }
                  />
                  <div className="flex justify-end gap-2 pt-1">
                    <Button type="button" variant="ghost" size="sm" onClick={skipPreferences} disabled={isSaving}>
                      跳过偏好
                    </Button>
                    <Button type="button" variant="secondary" size="sm" onClick={() => void savePreferences()} disabled={isSaving}>
                      {isSaving ? <Loader2 className="animate-spin" /> : <Check />}
                      保存
                    </Button>
                    <Button type="button" size="sm" onClick={generate} disabled={isGenerating}>
                      {isGenerating ? <Loader2 className="animate-spin" /> : <Sparkles />}
                      保存并重新分析
                    </Button>
                  </div>
                </div>
              )}
            </div>

            <div className={cn('resume-chat-input mt-3 flex items-end gap-2 rounded-xl bg-slate-50 p-3', (!canChat || isSendingChat) && 'opacity-70')}>
              <Textarea
                rows={2}
                value={draft}
                disabled={!canChat || isSendingChat}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    sendMessage();
                  }
                }}
                placeholder={canChat ? '问我如何优化这份简历...' : isDemoSession ? '示例会话只读 — 上传你自己的简历后可对话' : '等待首次分析完成后可对话...'}
                className="min-h-16 resize-none border-0 bg-transparent shadow-none focus-visible:ring-0"
              />
              <Button type="button" size="icon" className="mb-1 rounded-full" disabled={!canChat || !draft.trim() || isSendingChat} onClick={sendMessage}>
                {isSendingChat ? <Loader2 className="size-4 animate-spin" /> : <ArrowUpRight className="size-4" />}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}

function EditableResumeCanvas({
  profile,
  updateProfile,
  updateBasicInfo,
  onSave,
  isSaving,
}: {
  profile: ResumeProfilePayload;
  updateProfile: (updater: (profile: ResumeProfilePayload) => ResumeProfilePayload) => void;
  updateBasicInfo: (key: string, value: string) => void;
  onSave: () => Promise<void>;
  isSaving: boolean;
}) {
  const [editMode, setEditMode] = useState(false);
  const [layoutSettings, setLayoutSettings] = useState<ResumeLayoutSettings>(DEFAULT_RESUME_LAYOUT);
  const name = getProfileName(profile);
  const headline = getProfileHeadline(profile);
  const contactItems = getProfileContactItems(profile);
  const skills = [...profile.skills.technical, ...profile.skills.tools, ...profile.skills.languages, ...profile.languages].filter(
    (value, index, values) => Boolean(value) && values.indexOf(value) === index,
  );
  const customModules = readCustomModules(profile);
  const canvasStyle = {
    fontSize: `${layoutSettings.fontSize}px`,
    lineHeight: layoutSettings.lineHeight,
    padding: `${layoutSettings.pagePaddingY}px ${layoutSettings.pagePaddingX}px`,
    '--resume-section-gap': `${layoutSettings.moduleGap}px`,
    '--resume-module-gap': `${layoutSettings.moduleGap}px`,
  } as CSSProperties;

  const setCustomModules = (modules: CustomResumeModule[]) => updateCustomModules(updateProfile, modules);

  return (
    <section className="min-w-0 overflow-hidden rounded-[18px] border border-slate-200 bg-white shadow-[0_12px_36px_rgba(15,23,42,0.06)]">
      <div className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-100 bg-white/95 px-5 py-3 backdrop-blur">
        <div className="text-sm text-slate-500">{editMode ? '模块编辑' : '简历预览'}</div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <ResumeLayoutControls value={layoutSettings} onChange={setLayoutSettings} />
          <Button type="button" variant="secondary" size="sm" onClick={() => setEditMode((value) => !value)}>
            <PencilLine />
            {editMode ? '预览' : '编辑'}
          </Button>
          <Button type="button" size="sm" onClick={onSave} disabled={isSaving}>
            {isSaving ? <Loader2 className="animate-spin" /> : <Check />}
            保存
          </Button>
        </div>
      </div>

      <div className="h-[calc(100vh-98px)] overflow-y-auto bg-[#f7f7f7] px-4 py-8">
        <article
          className="resume-paper-shadow mx-auto min-h-[1120px] max-w-[920px] bg-white text-slate-800"
          style={canvasStyle}
        >
          {editMode ? (
            <div className="grid gap-[var(--resume-module-gap)]">
              <ModuleEditBlock title="基本信息">
                <div className="grid gap-3 md:grid-cols-2">
                  <Field label="姓名" value={profile.basic_info.name ?? ''} onChange={(value) => updateBasicInfo('name', value)} />
                  <Field label="目标岗位 / 当前身份" value={profile.basic_info.headline ?? ''} onChange={(value) => updateBasicInfo('headline', value)} />
                  <Field label="邮箱" value={profile.basic_info.email ?? ''} onChange={(value) => updateBasicInfo('email', value)} />
                  <Field label="电话" value={profile.basic_info.phone ?? ''} onChange={(value) => updateBasicInfo('phone', value)} />
                  <Field label="GitHub" value={profile.basic_info.github ?? ''} onChange={(value) => updateBasicInfo('github', value)} />
                  <Field label="LinkedIn / 领英" value={profile.basic_info.linkedin ?? ''} onChange={(value) => updateBasicInfo('linkedin', value)} />
                  <Field label="个人网站 / 作品集" value={profile.basic_info.website ?? ''} onChange={(value) => updateBasicInfo('website', value)} />
                  <Field label="所在地" value={profile.basic_info.location ?? ''} onChange={(value) => updateBasicInfo('location', value)} />
                </div>
              </ModuleEditBlock>

              <ModuleEditBlock title="个人介绍">
                <AreaField
                  label="摘要"
                  value={profile.candidate_summary}
                  onChange={(value) => updateProfile((previous) => ({ ...previous, candidate_summary: value }))}
                />
              </ModuleEditBlock>

              <ModuleEditBlock title="教育背景">
                <CompactEducationEditor profile={profile} updateProfile={updateProfile} />
              </ModuleEditBlock>

              <ModuleEditBlock title="工作经历">
                <CompactInternshipEditor profile={profile} updateProfile={updateProfile} />
              </ModuleEditBlock>

              <ModuleEditBlock title="项目经历">
                <CompactProjectEditor profile={profile} updateProfile={updateProfile} />
              </ModuleEditBlock>

              <ModuleEditBlock title="专业技能">
                <CompactSkillEditor profile={profile} updateProfile={updateProfile} />
              </ModuleEditBlock>

              {customModules.map((module) => (
                <ModuleEditBlock
                  key={module.id}
                  title={module.title || '自定义模块'}
                  onDelete={() => setCustomModules(customModules.filter((item) => item.id !== module.id))}
                >
                  <Field
                    label="模块标题"
                    value={module.title}
                    onChange={(value) =>
                      setCustomModules(customModules.map((item) => (item.id === module.id ? { ...item, title: value } : item)))
                    }
                  />
                  <AreaField
                    label="模块内容"
                    value={module.content}
                    placeholder="可以写证书、志愿经历、社团经历、作品链接等"
                    onChange={(value) =>
                      setCustomModules(customModules.map((item) => (item.id === module.id ? { ...item, content: value } : item)))
                    }
                  />
                </ModuleEditBlock>
              ))}

              <button
                type="button"
                className="rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-8 text-center text-sm font-semibold text-slate-500 transition hover:border-sky-300 hover:bg-sky-50 hover:text-[var(--primary)]"
                onClick={() =>
                  setCustomModules([
                    ...customModules,
                    {
                      id: nextCustomModuleId(customModules),
                      title: '自定义模块',
                      content: '',
                    },
                  ])
                }
              >
                <Plus className="mx-auto mb-2 size-5" />
                添加自定义模块
                <div className="mt-1 text-xs font-normal">如：证书资质、荣誉奖项、志愿经历、作品链接等</div>
              </button>
            </div>
          ) : (
            <>
              <header className="border-b border-slate-200 pb-5 text-center">
                <h1 className="text-[28px] font-semibold tracking-[0.04em] text-slate-950">{name}</h1>
                <p className="mt-2 text-[14px] font-medium text-slate-600">{headline}</p>
                <div className="mt-3 flex flex-wrap justify-center gap-x-4 gap-y-1 text-[12px] text-slate-500">
                  {contactItems.map((item) => (
                    <span key={item.key} className="inline-flex items-center gap-1.5">
                      {item.icon}
                      {item.value}
                    </span>
                  ))}
                </div>
              </header>

              {profile.candidate_summary && (
                <PreviewSection title="个人介绍">
                  <p>{profile.candidate_summary}</p>
                </PreviewSection>
              )}

              {profile.education.length > 0 && (
                <PreviewSection title="教育背景">
                  {profile.education.map((item, index) => (
                    <PreviewEntry
                      key={`${item.school}-${index}`}
                      title={item.school}
                      meta={[item.degree, item.major].filter(Boolean).join(' · ')}
                      date={[item.start_date, item.end_date].filter(Boolean).join(' - ')}
                      bullets={item.highlights}
                    />
                  ))}
                </PreviewSection>
              )}

              {profile.internships.length > 0 && (
                <PreviewSection title="工作经历">
                  {profile.internships.map((item, index) => (
                    <PreviewEntry
                      key={`${item.company}-${index}`}
                      title={item.company}
                      meta={item.role}
                      date={[item.start_date, item.end_date].filter(Boolean).join(' - ')}
                      bullets={item.bullets}
                    />
                  ))}
                </PreviewSection>
              )}

              {profile.projects.length > 0 && (
                <PreviewSection title="项目经历">
                  {profile.projects.map((item, index) => (
                    <PreviewEntry
                      key={`${item.name}-${index}`}
                      title={item.name}
                      meta={[item.role, item.tech_stack.join(' / ')].filter(Boolean).join(' · ')}
                      bullets={item.bullets}
                    />
                  ))}
                </PreviewSection>
              )}

              {skills.length > 0 && (
                <PreviewSection title="专业技能">
                  <p>{skills.join(' · ')}</p>
                </PreviewSection>
              )}

              {customModules.map((module) => (
                <PreviewSection key={module.id} title={module.title || '自定义模块'}>
                  <p className="whitespace-pre-line">{module.content}</p>
                </PreviewSection>
              ))}
            </>
          )}
        </article>
      </div>
    </section>
  );
}

function ResumeLayoutControls({
  value,
  onChange,
}: {
  value: ResumeLayoutSettings;
  onChange: (value: ResumeLayoutSettings) => void;
}) {
  const [activeControl, setActiveControl] = useState<ResumeLayoutControlKey | null>(null);

  const getControlValue = (key: ResumeLayoutControlKey) => {
    if (key === 'pagePadding') return value.pagePaddingX;
    return value[key];
  };

  const updateControl = (key: ResumeLayoutControlKey, nextValue: number) => {
    if (key === 'pagePadding') {
      onChange({
        ...value,
        pagePaddingX: nextValue,
        pagePaddingY: Math.round(nextValue * 0.86),
      });
      return;
    }

    onChange({
      ...value,
      [key]: nextValue,
    });
  };

  const activeMeta = activeControl ? RESUME_LAYOUT_CONTROL_META[activeControl] : null;
  const activeValue = activeControl ? getControlValue(activeControl) : 0;

  return (
    <div className="relative hidden items-center gap-2 xl:flex">
      {(Object.keys(RESUME_LAYOUT_CONTROL_META) as ResumeLayoutControlKey[]).map((key) => (
        <Button
          key={key}
          type="button"
          variant={activeControl === key ? 'default' : 'secondary'}
          size="sm"
          className="rounded-lg"
          onClick={() => setActiveControl((current) => (current === key ? null : key))}
        >
          {RESUME_LAYOUT_CONTROL_META[key].title}
        </Button>
      ))}

      {activeControl && activeMeta && (
        <div className="absolute right-0 top-[calc(100%+10px)] z-50 w-[360px] rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_24px_70px_rgba(15,23,42,0.18)]">
          <div className="mb-5 flex items-start justify-between gap-4">
            <div>
              <div className="text-base font-semibold text-slate-950">{activeMeta.title}</div>
              <div className="mt-1 text-sm text-slate-500">{activeMeta.description}</div>
            </div>
            <div className="rounded-lg bg-slate-50 px-2 py-1 font-mono text-xs text-slate-500">
              {Number.isInteger(activeValue) ? activeValue : activeValue.toFixed(2)}
              {activeMeta.unit}
            </div>
          </div>

          <input
            type="range"
            className="h-1.5 w-full cursor-pointer accent-[var(--primary)]"
            min={activeMeta.min}
            max={activeMeta.max}
            step={activeMeta.step}
            value={activeValue}
            onChange={(event) => updateControl(activeControl, Number(event.target.value))}
          />

          <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
            <span>范围：{activeMeta.range}</span>
            <span>拖动滑杆无级调节</span>
          </div>

          <div className="mt-6 flex justify-end gap-2 border-t border-slate-100 pt-4">
            <Button type="button" variant="secondary" onClick={() => setActiveControl(null)}>
              取消
            </Button>
            <Button type="button" onClick={() => setActiveControl(null)}>
              确定
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function ModuleEditBlock({
  title,
  children,
  onDelete,
}: {
  title: string;
  children: ReactNode;
  onDelete?: () => void;
}) {
  return (
    <section className="group rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_1px_8px_rgba(15,23,42,0.04)]">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="inline-block border-b-2 border-[var(--primary)] pb-1 text-[14px] font-semibold tracking-[0.08em] text-[var(--primary-strong)]">
          {title}
        </h2>
        {onDelete && (
          <button
            type="button"
            className="rounded-lg p-2 text-red-400 transition hover:bg-red-50 hover:text-red-600"
            aria-label={`删除${title}`}
            onClick={onDelete}
          >
            <Trash2 className="size-4" />
          </button>
        )}
      </div>
      <div className="grid gap-3">{children}</div>
    </section>
  );
}
function CompactEducationEditor({
  profile,
  updateProfile,
}: {
  profile: ResumeProfilePayload;
  updateProfile: (updater: (profile: ResumeProfilePayload) => ResumeProfilePayload) => void;
}) {
  return (
    <div className="grid gap-3">
      {profile.education.map((item, index) => (
        <div key={`education-edit-${index}`} className="grid gap-2 rounded-xl border border-slate-200 bg-white p-3">
          <div className="grid gap-2 md:grid-cols-2">
            <Field label="学校" value={item.school} onChange={(value) => updateProfile((previous) => ({ ...previous, education: previous.education.map((entry, itemIndex) => (itemIndex === index ? { ...entry, school: value } : entry)) }))} />
            <Field label="专业" value={item.major} onChange={(value) => updateProfile((previous) => ({ ...previous, education: previous.education.map((entry, itemIndex) => (itemIndex === index ? { ...entry, major: value } : entry)) }))} />
            <Field label="学历" value={item.degree} onChange={(value) => updateProfile((previous) => ({ ...previous, education: previous.education.map((entry, itemIndex) => (itemIndex === index ? { ...entry, degree: value } : entry)) }))} />
            <Field label="时间" value={[item.start_date, item.end_date].filter(Boolean).join(' - ')} onChange={(value) => {
              const [start = '', end = ''] = value.split(/\s*-\s*/);
              updateProfile((previous) => ({ ...previous, education: previous.education.map((entry, itemIndex) => (itemIndex === index ? { ...entry, start_date: start, end_date: end } : entry)) }));
            }} />
          </div>
          <AreaField label="亮点" value={joinLines(item.highlights)} onChange={(value) => updateProfile((previous) => ({ ...previous, education: previous.education.map((entry, itemIndex) => (itemIndex === index ? { ...entry, highlights: splitLines(value) } : entry)) }))} />
        </div>
      ))}
      <Button type="button" variant="secondary" size="sm" onClick={() => updateProfile((previous) => ({ ...previous, education: [...previous.education, EMPTY_EDUCATION] }))}>
        <Plus />
        添加教育
      </Button>
    </div>
  );
}

function CompactInternshipEditor({
  profile,
  updateProfile,
}: {
  profile: ResumeProfilePayload;
  updateProfile: (updater: (profile: ResumeProfilePayload) => ResumeProfilePayload) => void;
}) {
  return (
    <div className="grid gap-3">
      {profile.internships.map((item, index) => (
        <div key={`internship-edit-${index}`} className="grid gap-2 rounded-xl border border-slate-200 bg-white p-3">
          <div className="grid gap-2 md:grid-cols-2">
            <Field label="公司" value={item.company} onChange={(value) => updateProfile((previous) => ({ ...previous, internships: previous.internships.map((entry, itemIndex) => (itemIndex === index ? { ...entry, company: value } : entry)) }))} />
            <Field label="职位" value={item.role} onChange={(value) => updateProfile((previous) => ({ ...previous, internships: previous.internships.map((entry, itemIndex) => (itemIndex === index ? { ...entry, role: value } : entry)) }))} />
            <Field label="开始" value={item.start_date} onChange={(value) => updateProfile((previous) => ({ ...previous, internships: previous.internships.map((entry, itemIndex) => (itemIndex === index ? { ...entry, start_date: value } : entry)) }))} />
            <Field label="结束" value={item.end_date} onChange={(value) => updateProfile((previous) => ({ ...previous, internships: previous.internships.map((entry, itemIndex) => (itemIndex === index ? { ...entry, end_date: value } : entry)) }))} />
          </div>
          <AreaField label="职责与成果" value={joinLines(item.bullets)} onChange={(value) => updateProfile((previous) => ({ ...previous, internships: previous.internships.map((entry, itemIndex) => (itemIndex === index ? { ...entry, bullets: splitLines(value) } : entry)) }))} />
        </div>
      ))}
      <Button type="button" variant="secondary" size="sm" onClick={() => updateProfile((previous) => ({ ...previous, internships: [...previous.internships, EMPTY_INTERNSHIP] }))}>
        <Plus />
        添加经历
      </Button>
    </div>
  );
}

function CompactProjectEditor({
  profile,
  updateProfile,
}: {
  profile: ResumeProfilePayload;
  updateProfile: (updater: (profile: ResumeProfilePayload) => ResumeProfilePayload) => void;
}) {
  return (
    <div className="grid gap-3">
      {profile.projects.map((item, index) => (
        <div key={`project-edit-${index}`} className="grid gap-2 rounded-xl border border-slate-200 bg-white p-3">
          <div className="grid gap-2 md:grid-cols-2">
            <Field label="项目名称" value={item.name} onChange={(value) => updateProfile((previous) => ({ ...previous, projects: previous.projects.map((entry, itemIndex) => (itemIndex === index ? { ...entry, name: value } : entry)) }))} />
            <Field label="角色" value={item.role} onChange={(value) => updateProfile((previous) => ({ ...previous, projects: previous.projects.map((entry, itemIndex) => (itemIndex === index ? { ...entry, role: value } : entry)) }))} />
          </div>
          <ChipEditor label="技术栈" values={item.tech_stack} placeholder="Python / SQL" onChange={(values) => updateProfile((previous) => ({ ...previous, projects: previous.projects.map((entry, itemIndex) => (itemIndex === index ? { ...entry, tech_stack: values } : entry)) }))} />
          <AreaField label="项目内容" value={joinLines(item.bullets)} onChange={(value) => updateProfile((previous) => ({ ...previous, projects: previous.projects.map((entry, itemIndex) => (itemIndex === index ? { ...entry, bullets: splitLines(value) } : entry)) }))} />
        </div>
      ))}
      <Button type="button" variant="secondary" size="sm" onClick={() => updateProfile((previous) => ({ ...previous, projects: [...previous.projects, EMPTY_PROJECT] }))}>
        <Plus />
        添加项目
      </Button>
    </div>
  );
}

function CompactSkillEditor({
  profile,
  updateProfile,
}: {
  profile: ResumeProfilePayload;
  updateProfile: (updater: (profile: ResumeProfilePayload) => ResumeProfilePayload) => void;
}) {
  return (
    <div className="grid gap-3">
      <ChipEditor label="技能" values={profile.skills.technical} placeholder="输入后回车" onChange={(values) => updateProfile((previous) => ({ ...previous, skills: { ...previous.skills, technical: values } }))} />
      <ChipEditor label="工具" values={profile.skills.tools} placeholder="输入后回车" onChange={(values) => updateProfile((previous) => ({ ...previous, skills: { ...previous.skills, tools: values } }))} />
      <ChipEditor label="语言" values={[...profile.skills.languages, ...profile.languages].filter((value, index, values) => values.indexOf(value) === index)} placeholder="英语 / 普通话" onChange={(values) => updateProfile((previous) => ({ ...previous, languages: values, skills: { ...previous.skills, languages: values } }))} />
    </div>
  );
}
