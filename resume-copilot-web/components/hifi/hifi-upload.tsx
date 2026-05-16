'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react';

import {
  DEMO_SESSION_ID,
  createResumeCopilotSession,
  getResumeCopilotParsedProfile,
  getResumeCopilotSession,
  isAuthenticated,
  isGuestUser,
} from '@/components/resume-copilot/api';
import type {
  ResumeCopilotSession,
  ResumeCopilotSessionCreatedOut,
  ResumeProfilePayload,
} from '@/components/resume-copilot/types';
import { HFBtn, HFLogo, HFPill, I } from './hifi-primitives';

// ── Stages ───────────────────────────────────────────────────────────────────

type StageState = 'pending' | 'active' | 'done' | 'failed';

interface StageDef {
  key: 'read_pdf' | 'extract' | 'ready';
  label: string;
  hint: string;
}

const STAGES: StageDef[] = [
  { key: 'read_pdf', label: '读取 PDF · 抽取文本层', hint: '解析页面内容' },
  { key: 'extract', label: '结构化解析（LLM）· 教育/实习/项目/技能', hint: '推断方向与画像' },
  { key: 'ready', label: '准备就绪 · 字段预览', hint: '可进入工作台' },
];

// Sub-steps shown under stage 2 while the LLM is extracting structured fields.
// These are simulated front-end ticks (the backend runs one LLM call) — they exist
// to make the wait feel transparent and surface what the parser is actually inferring.
interface ParseSubstep {
  key: string;
  label: string;
  detail: string;
}

const PARSE_SUBSTEPS: ParseSubstep[] = [
  { key: 'tokens', label: '切分页面文本块', detail: 'tokenize · 段落归并' },
  { key: 'basic', label: '识别姓名 · 联系方式 · 求职意向', detail: 'basic_info · contact' },
  { key: 'edu', label: '解析教育经历（学校 · 学历 · 专业）', detail: 'education[]' },
  { key: 'exp', label: '解析实习与项目经历', detail: 'internships[] · projects[]' },
  { key: 'skill', label: '抽取技能与工具栈', detail: 'skills.technical · tools' },
  { key: 'infer', label: '推断目标方向与岗位画像', detail: 'inferred_tracks · roles' },
];

// ── Page ─────────────────────────────────────────────────────────────────────

type PageState =
  | { kind: 'idle' }
  | { kind: 'uploading' }
  | { kind: 'parsing'; sessionId: number; pageCount: number; fileBytes: number; fileName: string }
  | { kind: 'done'; sessionId: number; pageCount: number; fileBytes: number; fileName: string; profile: ResumeProfilePayload }
  | { kind: 'failed'; message: string };

export function HFUpload() {
  const router = useRouter();
  const [state, setState] = useState<PageState>({ kind: 'idle' });
  const [progress, setProgress] = useState(0);
  const [stageIndex, setStageIndex] = useState(0);
  const [stageTimes, setStageTimes] = useState<number[]>([0, 0, 0]);
  const [parseSubstep, setParseSubstep] = useState(0);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const stageStartRef = useRef<number>(performance.now());

  // Guard: 必须登录 (账号 或 guest 任一)
  useEffect(() => {
    if (!isAuthenticated() && !isGuestUser()) {
      router.replace('/');
    }
  }, [router]);

  // Polling for parse status
  useEffect(() => {
    if (state.kind !== 'parsing') return;
    let aborted = false;
    const sessionId = state.sessionId;

    const tick = async (): Promise<void> => {
      if (aborted) return;
      try {
        const session: ResumeCopilotSession = await getResumeCopilotSession(sessionId);
        if (aborted) return;
        if (session.status === 'awaiting_user_confirmation' || session.has_parsed_profile) {
          // Stage 2 → 3
          finishStage(1);
          startStage(2);
          const parsed = await getResumeCopilotParsedProfile(sessionId);
          if (aborted) return;
          finishStage(2);
          setState({
            kind: 'done',
            sessionId,
            pageCount: state.pageCount,
            fileBytes: state.fileBytes,
            fileName: state.fileName,
            profile: parsed.profile,
          });
          return;
        }
        if (session.status === 'failed') {
          setState({ kind: 'failed', message: session.error_message || '解析失败，请重试' });
          return;
        }
      } catch (err) {
        // transient error — keep polling but log
        console.warn('poll failed', err);
      }
      window.setTimeout(tick, 1500);
    };

    void tick();
    return () => {
      aborted = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.kind === 'parsing' ? state.sessionId : null]);

  // Substep ticker — advances through PARSE_SUBSTEPS while stage 2 is active.
  // Holds at the last item until the real parse completes (then setState flips
  // to 'done' and the AgentTrace renders all sub-steps as ✓).
  useEffect(() => {
    if (state.kind !== 'parsing') {
      setParseSubstep(0);
      return;
    }
    const timer = window.setInterval(() => {
      setParseSubstep((idx) => Math.min(idx + 1, PARSE_SUBSTEPS.length - 1));
    }, 1400);
    return () => window.clearInterval(timer);
  }, [state.kind]);

  const startStage = (idx: number) => {
    setStageIndex(idx);
    stageStartRef.current = performance.now();
  };

  const finishStage = (idx: number) => {
    setStageTimes((prev) => {
      const next = [...prev];
      next[idx] = (performance.now() - stageStartRef.current) / 1000;
      return next;
    });
  };

  const reset = () => {
    setState({ kind: 'idle' });
    setProgress(0);
    setStageIndex(0);
    setStageTimes([0, 0, 0]);
  };

  const startUpload = async (file: File) => {
    setState({ kind: 'uploading' });
    setProgress(0);
    setStageIndex(0);
    startStage(0);

    // Fake progress while real upload runs (pypdf extraction is sub-second so we keep this short)
    const progressTimer = window.setInterval(() => {
      setProgress((p) => (p < 88 ? Math.min(88, p + 7 + Math.random() * 6) : p));
    }, 80);

    try {
      const created: ResumeCopilotSessionCreatedOut = await createResumeCopilotSession(file);
      window.clearInterval(progressTimer);
      setProgress(100);
      finishStage(0);
      startStage(1);

      setState({
        kind: 'parsing',
        sessionId: created.session_id,
        pageCount: created.page_count ?? 0,
        fileBytes: created.file_size_bytes ?? file.size,
        fileName: file.name,
      });
    } catch (err) {
      window.clearInterval(progressTimer);
      const message = err instanceof Error ? err.message : '上传失败，请检查 PDF 文件';
      setState({ kind: 'failed', message });
    }
  };

  const onPickFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (file) void startUpload(file);
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragOver(false);
    const file = event.dataTransfer.files?.[0];
    if (file) void startUpload(file);
  };

  const onDemo = () => {
    router.push(`/resume-copilot?sessionId=${DEMO_SESSION_ID}`);
  };

  const stepperState = state.kind === 'idle' || state.kind === 'failed' || state.kind === 'uploading'
    ? 0
    : state.kind === 'parsing'
      ? 1
      : 2;

  return (
    <div className="hf hf-upload-page">
      {/* Top strip */}
      <div className="hf-upload-page__nav">
        <HFLogo />
        <div style={{ display: 'flex', alignItems: 'center', gap: 18, flexWrap: 'wrap' }}>
          <HFStepper current={stepperState} />
          <HFBtn variant="ghost" size="sm" onClick={reset}>
            取消并重来
          </HFBtn>
        </div>
      </div>

      <div className="hf-upload-page__main">
        {/* LEFT */}
        <div>
          <div className="hf-overline" style={{ marginBottom: 10 }}>
            第 1 步 · 上传简历
          </div>

          {state.kind === 'idle' && (
            <Dropzone
              dragOver={dragOver}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              onPick={() => fileInputRef.current?.click()}
              onDemo={onDemo}
            />
          )}

          {state.kind === 'failed' && (
            <FailedCard message={state.message} onRetry={reset} />
          )}

          {(state.kind === 'uploading' || state.kind === 'parsing' || state.kind === 'done') && (
            <FileCard
              fileName={state.kind === 'uploading' ? '上传中.pdf' : state.fileName}
              fileBytes={state.kind === 'uploading' ? 0 : state.fileBytes}
              pageCount={state.kind === 'uploading' ? 0 : state.pageCount}
              state={state.kind}
              progress={progress}
              profile={state.kind === 'done' ? state.profile : null}
            />
          )}

          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            style={{ display: 'none' }}
            onChange={onPickFile}
          />
        </div>

        {/* RIGHT — Agent trace */}
        <div>
          <div className="hf-overline" style={{ marginBottom: 10 }}>
            {state.kind === 'idle'
              ? '待命 · Agent 将在解析时启动'
              : state.kind === 'failed'
                ? 'Agent · 出错'
                : state.kind === 'uploading'
                  ? 'Agent · 待命'
                  : state.kind === 'parsing'
                    ? 'Agent · 推理中'
                    : 'Agent · 完成'}
          </div>

          <AgentTrace
            stageIndex={stageIndex}
            stageTimes={stageTimes}
            parseSubstep={parseSubstep}
            kind={state.kind}
            fileName={
              state.kind === 'uploading'
                ? ''
                : state.kind === 'parsing' || state.kind === 'done'
                  ? state.fileName
                  : ''
            }
            fileBytes={
              state.kind === 'parsing' || state.kind === 'done' ? state.fileBytes : 0
            }
            pageCount={
              state.kind === 'parsing' || state.kind === 'done' ? state.pageCount : 0
            }
            sessionId={
              state.kind === 'parsing' || state.kind === 'done' ? state.sessionId : 0
            }
            inferred={
              state.kind === 'done' ? state.profile.inferred_tracks?.[0] || '' : ''
            }
          />

          {state.kind === 'done' && (
            <CompletionStrip
              profile={state.profile}
              onEnter={() => router.push(`/resume-copilot?sessionId=${state.sessionId}`)}
            />
          )}
        </div>
      </div>

      {/* Footer help */}
      <div className="hf-upload-page__footer">
        <div className="hf-cap">💡 三步流程：上传 · 解析 · 确认偏好 — 每步都可撤回</div>
        <div className="hf-cap hf-mono" style={{ letterSpacing: '0.04em' }}>
          {state.kind === 'parsing' || state.kind === 'done' ? `session #${state.sessionId}` : ''}
        </div>
      </div>
    </div>
  );
}

// ── Stepper ──────────────────────────────────────────────────────────────────

interface StepperProps {
  current: number;
}

function HFStepper({ current }: StepperProps) {
  const items = ['上传', '解析', '确认偏好'];
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      {items.map((label, i) => {
        const active = i === current;
        const done = i < current;
        return (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span
              style={{
                width: 22,
                height: 22,
                borderRadius: 11,
                fontSize: 11,
                fontWeight: 600,
                background: active || done ? 'var(--terracotta)' : 'var(--library-rail)',
                color: active || done ? '#fff' : 'var(--stone)',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: active ? '0 0 0 4px rgba(201,100,66,0.18)' : 'none',
              }}
            >
              {done ? I.check(12) : i + 1}
            </span>
            <span
              style={{
                fontSize: 13,
                fontWeight: active ? 600 : 400,
                color: active ? 'var(--ink)' : 'var(--stone)',
              }}
            >
              {label}
            </span>
            {i < 2 ? <span style={{ width: 24, height: 1, background: 'var(--border-warm)', marginLeft: 6 }} /> : null}
          </div>
        );
      })}
    </div>
  );
}

// ── Dropzone ─────────────────────────────────────────────────────────────────

interface DropzoneProps {
  dragOver: boolean;
  onDragOver: (e: DragEvent) => void;
  onDragLeave: () => void;
  onDrop: (e: DragEvent) => void;
  onPick: () => void;
  onDemo: () => void;
}

function Dropzone({ dragOver, onDragOver, onDragLeave, onDrop, onPick, onDemo }: DropzoneProps) {
  return (
    <div
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      style={{
        height: 440,
        borderRadius: 24,
        padding: 28,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 12,
        background: dragOver ? 'var(--terracotta-wash)' : 'var(--ivory)',
        boxShadow: `0 0 0 ${dragOver ? 2 : 1.5}px ${dragOver ? 'var(--terracotta)' : 'var(--border-strong)'}`,
        backgroundImage: dragOver ? undefined : 'radial-gradient(circle, var(--border-strong) 1px, transparent 1px)',
        backgroundSize: '12px 12px',
        transition: 'all .18s',
      }}
    >
      <div
        style={{
          width: 72,
          height: 72,
          borderRadius: 36,
          background: 'var(--terracotta-wash)',
          color: 'var(--terracotta)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {I.upload(26)}
      </div>
      <div className="hf-h2" style={{ margin: 0 }}>把 PDF 简历拖进来</div>
      <div className="hf-body" style={{ marginTop: -4 }}>
        支持 PDF · 最大 10 MB · 文本层简历优先
      </div>
      <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
        <HFBtn variant="primary" onClick={onPick} icon={I.upload(14)}>
          选择本地文件
        </HFBtn>
        <HFBtn variant="ghost" onClick={onDemo}>
          使用示例简历
        </HFBtn>
      </div>
      <div className="hf-cap" style={{ marginTop: 14 }}>
        安全提示 · 文件仅用于推理与结构化，不会入库训练；guest 会话 2 小时自动清理
      </div>
    </div>
  );
}

// ── File card ────────────────────────────────────────────────────────────────

interface FileCardProps {
  fileName: string;
  fileBytes: number;
  pageCount: number;
  state: 'uploading' | 'parsing' | 'done';
  progress: number;
  profile: ResumeProfilePayload | null;
}

function FileCard({ fileName, fileBytes, pageCount, state, progress, profile }: FileCardProps) {
  const tone: 'amber' | 'terra' | 'emerald' =
    state === 'uploading' ? 'amber' : state === 'parsing' ? 'terra' : 'emerald';
  const label = state === 'uploading' ? '上传中' : state === 'parsing' ? '解析中' : '已完成';
  const sizeMB = fileBytes ? (fileBytes / 1024 / 1024).toFixed(2) : '—';
  const pageText = pageCount ? `${pageCount} 页` : '— 页';

  return (
    <div className="hf-card paper" style={{ padding: 22, borderRadius: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div
          style={{
            width: 44,
            height: 54,
            background: 'var(--ivory)',
            border: '1px solid var(--border-warm)',
            borderRadius: 6,
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div style={{ position: 'absolute', top: 4, right: 4, fontSize: 9, color: 'var(--terracotta)', fontWeight: 700 }}>PDF</div>
          <div
            style={{
              width: 22,
              height: 2,
              background: 'var(--border-strong)',
              boxShadow: '0 4px 0 0 var(--border-strong), 0 8px 0 0 var(--border-strong)',
            }}
          />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 15, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {fileName}
          </div>
          <div className="hf-cap">
            {sizeMB} MB · {pageText} · 刚刚上传
          </div>
        </div>
        <HFPill tone={tone}>{label}</HFPill>
      </div>

      <div style={{ marginTop: 18 }}>
        <div
          style={{
            height: 8,
            borderRadius: 99,
            background: 'var(--library-rail)',
            overflow: 'hidden',
            boxShadow: 'inset 0 0 0 1px var(--border-cream)',
          }}
        >
          <div
            className={state === 'uploading' || state === 'parsing' ? 'hf-bar-stripe' : ''}
            style={{
              width: `${state === 'uploading' ? progress : 100}%`,
              height: '100%',
              background: 'var(--terracotta)',
              transition: 'width .2s',
            }}
          />
        </div>
        <div className="hf-cap" style={{ textAlign: 'right', marginTop: 6 }}>
          {state === 'uploading' && `${Math.round(progress)}% · 正在传输`}
          {state === 'parsing' && '100% · 等待 LLM 推理'}
          {state === 'done' && '完成 · 字段已就绪'}
        </div>
      </div>

      {/* extracted fields preview */}
      <div style={{ marginTop: 18, padding: 14, background: 'var(--library-rail)', borderRadius: 12 }}>
        <div className="hf-overline" style={{ marginBottom: 8 }}>结构化预览</div>
        <FieldsPreview profile={profile} />
      </div>
    </div>
  );
}

function FieldsPreview({ profile }: { profile: ResumeProfilePayload | null }) {
  const skeletonRow = (label: string) => (
    <>
      <div style={{ color: 'var(--stone)' }}>{label}</div>
      <div style={{ height: 14, background: 'var(--ring-warm)', borderRadius: 6, opacity: 0.4 }} className="hf-pulse" />
    </>
  );

  if (!profile) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', rowGap: 8, columnGap: 14, fontSize: 13 }}>
        {skeletonRow('姓名')}
        {skeletonRow('目标')}
        {skeletonRow('学历')}
        {skeletonRow('经历')}
        {skeletonRow('技能')}
      </div>
    );
  }

  const name = profile.basic_info?.name || '—';
  const target = [
    profile.inferred_tracks?.[0] || '',
    profile.inferred_roles?.[0] || '',
  ].filter(Boolean).join(' · ') || '—';
  const edu = profile.education?.[0];
  const eduText = edu ? `${edu.school} · ${edu.degree}${edu.major ? ' · ' + edu.major : ''}` : '—';
  const internships = profile.internships?.slice(0, 3).map((i) => `${i.company}`).join(' · ') || '—';
  const skills = [
    ...(profile.skills?.technical || []),
    ...(profile.skills?.tools || []),
  ].slice(0, 6);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', rowGap: 8, columnGap: 14, fontSize: 13 }}>
      <div style={{ color: 'var(--stone)' }}>姓名</div>
      <div style={{ color: 'var(--ink)', fontWeight: 500 }}>{name}</div>
      <div style={{ color: 'var(--stone)' }}>目标</div>
      <div style={{ color: 'var(--ink)' }}>{target}</div>
      <div style={{ color: 'var(--stone)' }}>学历</div>
      <div style={{ color: 'var(--ink)' }}>{eduText}</div>
      <div style={{ color: 'var(--stone)' }}>经历</div>
      <div style={{ color: 'var(--ink)' }}>{internships}</div>
      {skills.length > 0 && (
        <>
          <div style={{ color: 'var(--stone)' }}>技能</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {skills.map((s) => (
              <span key={s} className="hf-pill" style={{ height: 22, fontSize: 11.5 }}>{s}</span>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ── Failed card ──────────────────────────────────────────────────────────────

function FailedCard({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div
      className="hf-card paper"
      style={{
        padding: 28,
        borderRadius: 20,
        border: '1px solid #f1c0bb',
        background: '#fdf3f1',
      }}
    >
      <div className="hf-h3" style={{ color: 'var(--crimson)', margin: 0, marginBottom: 8 }}>
        解析未能完成
      </div>
      <div className="hf-body" style={{ marginBottom: 18, color: 'var(--ink-soft)' }}>
        {message}
      </div>
      <HFBtn variant="primary" onClick={onRetry}>
        重新上传
      </HFBtn>
    </div>
  );
}

// ── Agent trace ──────────────────────────────────────────────────────────────

interface AgentTraceProps {
  stageIndex: number;
  stageTimes: number[];
  parseSubstep: number;
  kind: PageState['kind'];
  fileName: string;
  fileBytes: number;
  pageCount: number;
  sessionId: number;
  inferred: string;
}

function AgentTrace({ stageIndex, stageTimes, parseSubstep, kind, fileName, fileBytes, pageCount, sessionId, inferred }: AgentTraceProps) {
  return (
    <div className="hf-card lift" style={{ padding: 22, borderRadius: 20, minHeight: 440, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <div style={{ width: 28, height: 28, borderRadius: 8, background: 'var(--deep-dark)', position: 'relative' }}>
          <div
            style={{
              position: 'absolute',
              top: 10,
              left: 10,
              width: 8,
              height: 8,
              borderRadius: 4,
              background: 'var(--terracotta)',
              boxShadow: '0 0 0 3px rgba(201,100,66,0.2)',
            }}
          />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: 14 }}>Resume Parser Agent</div>
          <div className="hf-cap">structured extract · llm-backed</div>
        </div>
        {kind === 'uploading' || kind === 'parsing' ? (
          <span className="hf-spin cool" />
        ) : null}
        {kind === 'done' ? <HFPill tone="emerald">{I.check(12)} 完成</HFPill> : null}
        {kind === 'failed' ? <HFPill tone="terra">出错</HFPill> : null}
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {STAGES.map((s, i) => {
          let stageState: StageState;
          if (kind === 'idle' || kind === 'failed') stageState = 'pending';
          else if (kind === 'done') stageState = 'done';
          else if (kind === 'uploading' || kind === 'parsing') {
            if (i < stageIndex) stageState = 'done';
            else if (i === stageIndex) stageState = 'active';
            else stageState = 'pending';
          } else stageState = 'pending';
          if (kind === 'failed' && i === stageIndex) stageState = 'failed';

          return (
            <div key={s.key} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <StageRow
                stage={s}
                state={stageState}
                index={i}
                durationSec={stageTimes[i] || 0}
              />
              {i === 1 && (stageState === 'active' || stageState === 'done') && (
                <ParseSubstepList
                  substepIndex={parseSubstep}
                  allDone={stageState === 'done'}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Terminal log */}
      <div
        style={{
          marginTop: 14,
          padding: '12px 14px',
          background: 'var(--deep-dark)',
          borderRadius: 12,
          fontFamily: 'var(--font-mono)',
          fontSize: 11.5,
          lineHeight: 1.7,
          color: 'var(--warm-silver)',
        }}
      >
        <div>
          <span style={{ color: 'var(--terracotta)' }}>$</span> parser.run(file={fileName || 'resume.pdf'}, size=
          {fileBytes ? (fileBytes / 1024).toFixed(1) + 'KB' : '—'})
        </div>
        {(kind === 'parsing' || kind === 'done') && (
          <div>
            <span style={{ color: '#86b97a' }}>✓</span> read_pdf → {pageCount || '?'} pages
          </div>
        )}
        {kind === 'done' && (
          <>
            <div>
              <span style={{ color: '#86b97a' }}>✓</span> structure_extract → ok
            </div>
            <div>
              <span style={{ color: '#86b97a' }}>✓</span> infer_target → {inferred || 'ready'}
            </div>
            <div style={{ color: '#fff' }}>
              → session_ready_{shortId(sessionId)}
              <span className="hf-caret" style={{ color: 'var(--terracotta)', height: '0.9em' }} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

interface StageRowProps {
  stage: StageDef;
  state: StageState;
  index: number;
  durationSec: number;
}

function StageRow({ stage, state, index, durationSec }: StageRowProps) {
  const isActive = state === 'active';
  const isDone = state === 'done';
  const isFailed = state === 'failed';
  const isPending = state === 'pending';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '12px 14px',
        borderRadius: 12,
        background: isActive
          ? 'var(--terracotta-wash)'
          : isDone
            ? 'var(--emerald-soft)'
            : isFailed
              ? '#fdf3f1'
              : 'var(--library-rail)',
        boxShadow: `0 0 0 1px ${isActive ? '#eccfb6' : isDone ? '#c7d9c2' : isFailed ? '#f1c0bb' : 'var(--border-cream)'}`,
        opacity: isPending ? 0.55 : 1,
        transition: 'all .25s',
      }}
    >
      <span
        style={{
          width: 26,
          height: 26,
          borderRadius: 13,
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: isActive ? 'var(--terracotta)' : isDone ? 'var(--emerald)' : isFailed ? 'var(--crimson)' : 'var(--ivory)',
          color: isActive || isDone || isFailed ? '#fff' : 'var(--stone)',
          boxShadow: isActive || isDone || isFailed ? 'none' : '0 0 0 1px var(--border-warm)',
        }}
      >
        {isActive ? (
          <span
            className="hf-spin"
            style={{ width: 12, height: 12, borderColor: 'rgba(255,255,255,0.4)', borderTopColor: '#fff' }}
          />
        ) : isDone ? (
          I.check(14)
        ) : (
          <span style={{ fontSize: 11, fontWeight: 600 }}>{index + 1}</span>
        )}
      </span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--ink)' }}>{stage.label}</div>
        <div className="hf-cap" style={{ marginTop: 1 }}>
          {isActive ? '推理中…' : isDone ? stage.hint : isFailed ? '失败' : '等待'}
        </div>
      </div>
      <span className="hf-mono-sm" style={{ color: 'var(--stone)', fontSize: 11 }}>
        {isDone && durationSec > 0 ? `${durationSec.toFixed(1)}s` : isActive ? '…' : '—'}
      </span>
    </div>
  );
}

// ── Parse sub-step list (under stage 2) ──────────────────────────────────────

interface ParseSubstepListProps {
  substepIndex: number;
  allDone: boolean;
}

function ParseSubstepList({ substepIndex, allDone }: ParseSubstepListProps) {
  return (
    <div
      style={{
        marginLeft: 38,
        paddingLeft: 14,
        borderLeft: '1px dashed var(--border-warm)',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
      }}
    >
      {PARSE_SUBSTEPS.map((sub, i) => {
        const isDone = allDone || i < substepIndex;
        const isActive = !allDone && i === substepIndex;
        return (
          <div
            key={sub.key}
            className={isActive ? 'hf-slide' : undefined}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              fontSize: 12.5,
              color: isDone ? 'var(--ink-soft)' : isActive ? 'var(--ink)' : 'var(--stone)',
              opacity: isDone || isActive ? 1 : 0.55,
              transition: 'opacity .25s, color .25s',
            }}
          >
            <span
              style={{
                width: 16,
                height: 16,
                borderRadius: 8,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: isDone
                  ? 'var(--emerald)'
                  : isActive
                    ? 'var(--terracotta)'
                    : 'var(--ivory)',
                color: isDone || isActive ? '#fff' : 'var(--stone)',
                boxShadow: isDone || isActive ? 'none' : '0 0 0 1px var(--border-warm)',
                flexShrink: 0,
              }}
            >
              {isDone ? (
                I.check(10)
              ) : isActive ? (
                <span
                  className="hf-spin"
                  style={{
                    width: 8,
                    height: 8,
                    borderWidth: 1.2,
                    borderColor: 'rgba(255,255,255,0.45)',
                    borderTopColor: '#fff',
                  }}
                />
              ) : (
                <span style={{ width: 4, height: 4, borderRadius: 2, background: 'var(--stone)' }} />
              )}
            </span>
            <span style={{ flex: 1 }}>{sub.label}</span>
            <span
              className="hf-mono-sm"
              style={{ fontSize: 10.5, color: 'var(--stone)', letterSpacing: '0.02em' }}
            >
              {sub.detail}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Completion strip ─────────────────────────────────────────────────────────

interface CompletionStripProps {
  profile: ResumeProfilePayload;
  onEnter: () => void;
}

function CompletionStrip({ profile, onEnter }: CompletionStripProps) {
  const track = profile.inferred_tracks?.[0] || '';
  const role = profile.inferred_roles?.[0] || '';
  const city = profile.basic_info?.city || '';
  const parts = [track, role, city].filter(Boolean);
  const message = parts.length > 0 ? `已推断目标：${parts.join(' · ')}。下一步可微调。` : '已就绪。下一步可微调偏好。';

  return (
    <div
      className="hf-slide"
      style={{
        marginTop: 14,
        padding: 14,
        background: 'var(--ivory)',
        borderRadius: 12,
        boxShadow: 'var(--sh-ring)',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        flexWrap: 'wrap',
      }}
    >
      <div style={{ color: 'var(--terracotta)' }}>{I.sparkle(16)}</div>
      <div style={{ flex: 1, fontSize: 13.5, color: 'var(--ink-soft)', minWidth: 220 }}>{message}</div>
      <HFBtn variant="primary" size="sm" iconRight={I.arrowRight(12)} onClick={onEnter}>
        进入工作台
      </HFBtn>
    </div>
  );
}

// ── helpers ──────────────────────────────────────────────────────────────────

function shortId(id: number): string {
  if (!id) return '----';
  return id.toString(16).padStart(4, '0').slice(-4);
}
