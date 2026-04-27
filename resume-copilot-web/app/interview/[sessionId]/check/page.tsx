'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  Mic, Volume2, Video, ShieldCheck, Clock3, Sparkles, Lock, Play, Camera, Check,
  ArrowRight,
} from 'lucide-react';
import { TopBar, StatusDot, Eyebrow } from '@/components/interview/primitives';
import { useTTSPlayer } from '@/components/interview/voice/useTTSPlayer';
import { useRecorder } from '@/components/interview/voice/useRecorder';

const SPEECH_PHRASE = '我确认参加面试';

/** Strip non-CJK / word chars so punctuation differences don't matter. */
function normalize(t: string): string {
  return t.replace(/[^一-鿿\w]/g, '');
}

const MIC_BARS = 22;

export default function InterviewDeviceCheckPage() {
  const router = useRouter();
  const { sessionId } = useParams<{ sessionId: string }>();

  const [targetJob, setTargetJob] = useState('');
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    setTargetJob(localStorage.getItem(`interview.pending.${sessionId}`) || '');
  }, [sessionId]);
  /* eslint-enable react-hooks/set-state-in-effect */

  /* ───────────────────────── Step state ─────────────────────────────────── */
  const [micPassed, setMicPassed] = useState(false);
  const [spPassed, setSpPassed] = useState(false);
  const [camPassed, setCamPassed] = useState(false);
  const allPassed = micPassed && spPassed && camPassed;

  // Active = the first un-passed step.
  const activeStep: 'mic' | 'sp' | 'cam' | null = !micPassed
    ? 'mic'
    : !spPassed
      ? 'sp'
      : !camPassed
        ? 'cam'
        : null;

  /* ───────────────────────── Mic — real recorder + meter ─────────────── */
  const recorder = useRecorder();
  const meterRef = useRef<HTMLDivElement>(null);
  const [micDb, setMicDb] = useState(-60);

  // Local audio level meter (independent of the WS recorder, for visual feedback).
  useEffect(() => {
    if (activeStep !== 'mic' || micPassed) return;
    let raf = 0;
    let ctx: AudioContext | null = null;
    let stream: MediaStream | null = null;
    let analyser: AnalyserNode | null = null;
    const bars = meterRef.current?.querySelectorAll<HTMLSpanElement>('.bar');

    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        ctx = new AudioContext();
        const src = ctx.createMediaStreamSource(stream);
        analyser = ctx.createAnalyser();
        analyser.fftSize = 64;
        src.connect(analyser);
        const data = new Uint8Array(analyser.frequencyBinCount);

        const tick = () => {
          if (!analyser) return;
          analyser.getByteFrequencyData(data);
          let peak = 0;
          bars?.forEach((b, i) => {
            const v = data[i % data.length] / 255;
            const h = Math.max(3, v * 40);
            b.style.height = h + 'px';
            b.classList.toggle('on', v > 0.08);
            peak = Math.max(peak, v);
          });
          setMicDb(-Math.max(3, Math.round(60 - peak * 55)));
          raf = requestAnimationFrame(tick);
        };
        tick();
      } catch {
        /* mic denied — leave bars at idle */
      }
    })();

    return () => {
      cancelAnimationFrame(raf);
      stream?.getTracks().forEach((t) => t.stop());
      ctx?.close();
    };
  }, [activeStep, micPassed]);

  // Auto-pass when the spoken phrase is recognized via real ASR.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (activeStep !== 'mic' || micPassed) return;
    const combined = recorder.finalText + recorder.partialText;
    if (combined && normalize(combined).includes(normalize(SPEECH_PHRASE))) {
      setMicPassed(true);
      recorder.stop();
    }
  }, [recorder, activeStep, micPassed]);
  /* eslint-enable react-hooks/set-state-in-effect */

  /* ───────────────────────── Speaker — real TTS playback ─────────────── */
  const tts = useTTSPlayer();
  const [spWaveActive, setSpWaveActive] = useState(false);
  const playSpeakerTest = useCallback(() => {
    setSpWaveActive(true);
    tts.speak('你好，这是面试官的声音测试，听到这句话就可以点听得清。');
  }, [tts]);
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (!tts.isPlaying && spWaveActive && (tts.progress >= 1 || tts.error)) {
      setSpWaveActive(false);
    }
  }, [tts.isPlaying, tts.progress, tts.error, spWaveActive]);
  /* eslint-enable react-hooks/set-state-in-effect */

  /* ───────────────────────── Camera — getUserMedia ─────────────────────── */
  const camPrevRef = useRef<HTMLVideoElement>(null);
  const sideCamRef = useRef<HTMLVideoElement>(null);
  const camStreamRef = useRef<MediaStream | null>(null);
  const [camAuthed, setCamAuthed] = useState(false);

  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720 },
      });
      camStreamRef.current = stream;
      if (camPrevRef.current) {
        camPrevRef.current.srcObject = stream;
        await camPrevRef.current.play().catch(() => {});
      }
      if (sideCamRef.current) {
        sideCamRef.current.srcObject = stream;
        await sideCamRef.current.play().catch(() => {});
      }
      setCamAuthed(true);
    } catch {
      /* denied — placeholder shows */
    }
  }, []);

  useEffect(() => () => camStreamRef.current?.getTracks().forEach((t) => t.stop()), []);

  /* ───────────────────────── Actions ────────────────────────────────────── */
  const proceed = useCallback(() => {
    if (!allPassed) return;
    router.push(`/interview/${sessionId}`);
  }, [allPassed, router, sessionId]);

  const skip = useCallback(() => {
    router.push(`/interview/${sessionId}`);
  }, [router, sessionId]);

  // Enter to start when ready.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Enter' && allPassed) proceed();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [allPassed, proceed]);

  /* ───────────────────────── Render ─────────────────────────────────────── */
  return (
    <main className="min-h-screen" style={{ background: 'var(--parchment)' }}>
      <div className="grid min-h-screen grid-rows-[auto_1fr_auto]">
        <TopBar
          crumb={
            <>
              模拟面试 · <b className="font-medium text-[var(--ink-soft)]">设备检测</b>
            </>
          }
          meta={
            <>
              <span className="inline-flex items-center gap-[6px]">
                <StatusDot color="emerald" />AI 面试官 · 已待命
              </span>
              <span className="h-3 w-px" style={{ background: 'var(--border-strong)' }} />
              <span>步骤 1 / 2</span>
            </>
          }
        />

        {/* Main */}
        <div
          className="mx-auto grid w-full max-w-[1200px] gap-x-[48px] gap-y-[40px] px-[28px] py-[40px] pb-[56px] md:grid-cols-[minmax(0,1.15fr)_minmax(420px,1fr)]"
          style={{ alignItems: 'start' }}
        >
          {/* Left — intro + checklist */}
          <section>
            <Eyebrow>MOCK INTERVIEW · PRE-FLIGHT</Eyebrow>
            <h1
              className="mb-[16px] mt-[18px] text-[var(--ink)]"
              style={{
                fontFamily: 'var(--font-serif)',
                fontWeight: 500,
                fontSize: 56,
                lineHeight: 1.04,
                letterSpacing: '-0.035em',
              }}
            >
              在开始前，<br />
              先把
              <em
                className="not-italic"
                style={{
                  background:
                    'linear-gradient(to top, rgba(201,100,66,0.18) 0 38%, transparent 38%)',
                  padding: '0 2px',
                }}
              >
                麦克风 · 扬声器 · 摄像头
              </em>
              <br />
              都调到舒服的状态。
            </h1>
            <p className="mb-[28px] max-w-[46ch] text-[16px] leading-[1.65] text-[var(--olive)]">
              我们会让 AI 面试官在接下来约 20 分钟里，针对你上传的简历提出 6–8 个问题。为了让对话顺畅，请依次完成下面的检测——每一项都通过之后，开始按钮会自动亮起。
            </p>

            <div className="mb-[26px] flex gap-[10px]">
              <Badge tone="amber" icon={<ShieldCheck size={14} strokeWidth={1.6} />}>本地处理</Badge>
              <Badge tone="muted" icon={<Clock3 size={14} strokeWidth={1.6} />}>约 1 分钟</Badge>
            </div>

            <div className="flex flex-col gap-[14px]">
              {/* 1 — Microphone */}
              <CheckCard
                step="mic"
                icon={<Mic size={20} strokeWidth={1.6} />}
                title="麦克风"
                subtitle="Microphone"
                meta="念一句「我确认参加面试」，系统会自动识别并通过。"
                state={micPassed ? 'pass' : activeStep === 'mic' ? 'active' : 'todo'}
                statusText={micPassed ? '已通过' : activeStep === 'mic' ? '说一句话试试' : '待检测'}
              >
                <div className="flex flex-wrap items-center gap-[12px]">
                  <div
                    ref={meterRef}
                    className="flex h-[44px] flex-1 items-end gap-[3px] rounded-[12px] border border-[var(--border)] px-[10px] py-[6px]"
                    style={{ background: 'var(--library-rail)', minWidth: 180 }}
                  >
                    {Array.from({ length: MIC_BARS }).map((_, i) => (
                      <span
                        key={i}
                        className="bar"
                        style={{
                          flex: 1,
                          minHeight: 3,
                          height: 3,
                          opacity: 0.35,
                          background:
                            'linear-gradient(to top, var(--terracotta) 0%, var(--terracotta) 55%, #e8a791 100%)',
                          borderRadius: 2,
                          transition: 'height 80ms ease-out',
                        }}
                      />
                    ))}
                  </div>
                  <span
                    className="min-w-[48px] text-right text-[12px] text-[var(--olive)]"
                    style={{ fontFamily: 'var(--font-mono)', letterSpacing: '-0.02em' }}
                  >
                    {micDb} dB
                  </span>
                  <GhostButton
                    onClick={() => {
                      if (recorder.isRecording) recorder.stop();
                      else recorder.start();
                    }}
                  >
                    <Mic size={14} strokeWidth={1.7} />
                    {recorder.isRecording ? '停止录音' : '开始录音'}
                  </GhostButton>
                  <GhostButton onClick={() => setMicPassed(true)}>
                    <Check size={14} strokeWidth={1.7} />
                    通过
                  </GhostButton>
                </div>
                <div className="mt-[10px] text-[13px] leading-[1.5] text-[var(--olive)]">
                  当前识别：
                  <span className="text-[var(--ink)]">{recorder.finalText}</span>
                  <span className="text-[var(--stone)]">{recorder.partialText && ' '}{recorder.partialText}</span>
                  {!recorder.finalText && !recorder.partialText && (
                    <span className="text-[var(--stone)]">（点击开始录音并朗读上面的短语）</span>
                  )}
                  {recorder.error && (
                    <span className="ml-2 text-[var(--crimson)]">{recorder.error}</span>
                  )}
                </div>
              </CheckCard>

              {/* 2 — Speaker */}
              <CheckCard
                step="sp"
                icon={<Volume2 size={20} strokeWidth={1.6} />}
                title="扬声器"
                subtitle="Speaker"
                meta="点击播放面试官真实音色（longyingtian），确认能听清。"
                state={spPassed ? 'pass' : activeStep === 'sp' ? 'active' : 'todo'}
                statusText={spPassed ? '已通过' : activeStep === 'sp' ? '点播放' : '待检测'}
              >
                <div className="flex flex-wrap items-center gap-[12px]">
                  <GhostButton onClick={playSpeakerTest} disabled={tts.isPlaying}>
                    <Play size={14} strokeWidth={1.7} />
                    {tts.isPlaying ? '播放中…' : '播放试听'}
                  </GhostButton>
                  <div
                    className="flex h-[44px] flex-1 items-center justify-center gap-[2px] rounded-[12px] border border-[var(--border)] px-[12px] text-[12px]"
                    style={{
                      background: 'var(--library-rail)',
                      color: 'var(--olive)',
                      minWidth: 180,
                    }}
                  >
                    {Array.from({ length: 12 }).map((_, i) => (
                      <span
                        key={i}
                        style={{
                          width: 3,
                          height: spWaveActive
                            ? `${10 + Math.abs(Math.sin(i * 0.6)) * 18}px`
                            : 8,
                          background: 'var(--terracotta)',
                          borderRadius: 2,
                          opacity: spWaveActive ? 1 : 0.4,
                          animation: spWaveActive
                            ? `itv-listen-bar 1.1s ease-in-out infinite ${i * 0.08}s`
                            : 'none',
                        }}
                      />
                    ))}
                  </div>
                  <GhostButton onClick={() => setSpPassed(true)}>
                    <Check size={14} strokeWidth={1.7} />
                    听得清
                  </GhostButton>
                </div>
                {tts.error && (
                  <div className="mt-[10px] text-[13px] text-[var(--crimson)]">{tts.error}</div>
                )}
              </CheckCard>

              {/* 3 — Camera */}
              <CheckCard
                step="cam"
                icon={<Video size={20} strokeWidth={1.6} />}
                title="摄像头"
                subtitle="Camera"
                meta="确认画面中的你在取景框内，光线均匀，背景整洁。"
                state={camPassed ? 'pass' : activeStep === 'cam' ? 'active' : 'todo'}
                statusText={camPassed ? '已通过' : activeStep === 'cam' ? '开启摄像头' : '待检测'}
              >
                <div
                  className="relative w-full overflow-hidden rounded-[16px] border border-[var(--border)]"
                  style={{ aspectRatio: '16 / 10', background: '#1c1c1b' }}
                >
                  <video
                    ref={camPrevRef}
                    autoPlay
                    muted
                    playsInline
                    className="block h-full w-full object-cover"
                    style={{ transform: 'scaleX(-1)', background: '#1c1c1b' }}
                  />
                  {!camAuthed && (
                    <div
                      className="absolute inset-0 grid place-items-center gap-[8px] text-[13px] text-[var(--warm-silver)]"
                      style={{
                        background:
                          'repeating-linear-gradient(135deg, #1c1c1b, #1c1c1b 14px, #232321 14px, #232321 28px)',
                      }}
                    >
                      <Video size={26} strokeWidth={1.5} className="opacity-60" />
                      <div>尚未授权摄像头 · 点击下方开启</div>
                    </div>
                  )}
                  <div
                    className="pointer-events-none absolute rounded-[10px] border border-dashed"
                    style={{ inset: 12, borderColor: 'rgba(255,255,255,0.22)' }}
                  />
                  <div
                    className="absolute bottom-[12px] left-[12px] flex items-center gap-[6px] rounded-full px-[10px] py-[5px] text-[11px] tracking-[0.02em]"
                    style={{
                      background: 'rgba(0,0,0,0.42)',
                      color: '#faf9f5',
                      backdropFilter: 'blur(6px)',
                    }}
                  >
                    <span
                      className="inline-block h-[6px] w-[6px] rounded-full"
                      style={{
                        background: 'var(--terracotta)',
                        boxShadow: '0 0 0 3px rgba(201,100,66,0.35)',
                      }}
                    />
                    保持双眼与摄像头水平 · 距离 50–70 cm
                  </div>
                </div>
                <div className="mt-[12px] flex items-center justify-between">
                  <GhostButton onClick={startCamera}>
                    <Camera size={14} strokeWidth={1.7} />
                    {camAuthed ? '重新开启' : '开启摄像头'}
                  </GhostButton>
                  <GhostButton onClick={() => setCamPassed(true)} disabled={!camAuthed}>
                    <Check size={14} strokeWidth={1.7} />
                    画面 OK
                  </GhostButton>
                </div>
              </CheckCard>
            </div>
          </section>

          {/* Right — session summary */}
          <aside
            className="overflow-hidden rounded-[22px] border border-[var(--border)]"
            style={{
              position: 'sticky',
              top: 88,
              background: 'var(--ivory)',
              boxShadow: 'var(--shadow-paper)',
            }}
          >
            <div className="flex items-center gap-[12px] border-b border-[var(--border)] px-[22px] pb-[14px] pt-[18px]">
              <div
                className="grid h-[38px] w-[38px] place-items-center rounded-full"
                style={{ background: 'var(--terracotta)', color: '#faf9f5' }}
              >
                <Sparkles size={18} strokeWidth={1.6} />
              </div>
              <div>
                <div
                  className="text-[20px] tracking-[-0.01em] text-[var(--ink)]"
                  style={{ fontFamily: 'var(--font-serif)', fontWeight: 500 }}
                >
                  本次面试 · 信息
                </div>
                <div className="mt-[2px] text-[11px] text-[var(--olive)]">实时生成 · {new Date().toLocaleString('zh-CN')}</div>
              </div>
            </div>

            <div className="px-[22px] pb-[8px] pt-[18px]">
              <Brief k="岗位" v={
                <>
                  {targetJob || '（未指定）'}<br />
                  <span className="text-[12px] text-[var(--stone)]">由你在上一步填写或选择</span>
                </>
              } />
              <Brief k="面试官" v={
                <>
                  AI 面试官 · 姜老师<br />
                  <span className="mr-[6px] inline-block rounded-full border border-[var(--border)] px-[8px] py-[2px] text-[11px] text-[var(--olive)]" style={{ background: 'var(--library-rail)' }}>项目深挖</span>
                  <span className="mr-[6px] inline-block rounded-full border border-[var(--border)] px-[8px] py-[2px] text-[11px] text-[var(--olive)]" style={{ background: 'var(--library-rail)' }}>行为题</span>
                  <span className="mr-[6px] inline-block rounded-full border border-[var(--border)] px-[8px] py-[2px] text-[11px] text-[var(--olive)]" style={{ background: 'var(--library-rail)' }}>中文</span>
                </>
              } />
              <Brief k="时长" v={
                <>
                  约 14 轮 · 10–20 分钟<br />
                  <span className="text-[12px] text-[var(--stone)]">随时可暂停，浏览器自动保存</span>
                </>
              } />
              <Brief k="重点" v={<span className="text-[13px] text-[var(--olive)]">先 3 轮行为题，之后根据岗位切换技术 / 业务追问，重点考察主导度与决策思路。</span>} />
            </div>

            <div
              className="relative mx-[22px] mb-[18px] mt-[4px] overflow-hidden rounded-[16px] border border-[var(--border)]"
              style={{ aspectRatio: '16 / 11', background: '#1c1c1b' }}
            >
              <video
                ref={sideCamRef}
                autoPlay
                muted
                playsInline
                className="block h-full w-full object-cover"
                style={{ transform: 'scaleX(-1)', background: '#1c1c1b' }}
              />
              {!camAuthed && (
                <div
                  className="absolute inset-0 grid place-items-center gap-[6px] text-[12px] text-[var(--warm-silver)]"
                  style={{
                    background:
                      'repeating-linear-gradient(135deg, #1c1c1b, #1c1c1b 14px, #232321 14px, #232321 28px)',
                  }}
                >
                  <Camera size={22} strokeWidth={1.5} />
                  摄像头预览
                </div>
              )}
              <div
                className="absolute bottom-[12px] left-[12px] flex items-center gap-[6px] rounded-full px-[10px] py-[5px] text-[11px]"
                style={{ background: 'rgba(0,0,0,0.42)', color: '#faf9f5', backdropFilter: 'blur(6px)' }}
              >
                <span
                  className="inline-block h-[6px] w-[6px] rounded-full"
                  style={{ background: 'var(--terracotta)', boxShadow: '0 0 0 3px rgba(201,100,66,0.35)' }}
                />
                预览
              </div>
            </div>

            <button
              onClick={proceed}
              disabled={!allPassed}
              className="mx-[22px] mb-[22px] flex w-[calc(100%-44px)] items-center justify-center gap-[10px] rounded-[14px] px-[18px] py-[14px] text-[15px] font-semibold transition-colors"
              style={{
                background: allPassed ? 'var(--terracotta)' : 'var(--warm-sand)',
                color: allPassed ? '#faf9f5' : 'var(--stone)',
                cursor: allPassed ? 'pointer' : 'not-allowed',
                boxShadow: allPassed
                  ? '0 0 0 1px var(--terracotta), 0 1px 2px rgba(168,79,52,0.18)'
                  : 'none',
              }}
            >
              {allPassed ? (
                <>开始模拟面试<KeyHint>Enter</KeyHint><ArrowRight size={16} strokeWidth={1.8} /></>
              ) : (
                <><Lock size={16} strokeWidth={1.7} />请先完成设备检测</>
              )}
            </button>
          </aside>
        </div>

        {/* Footer */}
        <footer
          className="flex items-center justify-between border-t border-[var(--border)] px-[28px] py-[14px] text-[12px] text-[var(--stone)]"
        >
          <div>你的语音与视频仅在本次面试期间用于评估，结束后 7 天内自动删除。</div>
          <div className="flex items-center gap-[8px]">
            <a className="text-[var(--olive)] hover:text-[var(--ink)]" href="#">遇到问题？</a>
            <span>·</span>
            <button onClick={skip} className="text-[var(--olive)] underline-offset-2 hover:text-[var(--ink)] hover:underline">跳过检测</button>
          </div>
        </footer>
      </div>

      <style jsx global>{`
        [data-theme='interview'] .bar.on { opacity: 1 !important; }
      `}</style>
    </main>
  );
}

/* ─────────────────────────── Local subcomponents ──────────────────────────── */

function Badge({
  children,
  tone,
  icon,
}: {
  children: React.ReactNode;
  tone: 'amber' | 'muted';
  icon?: React.ReactNode;
}) {
  const styles = tone === 'amber'
    ? { background: 'var(--amber-bg)', color: 'var(--amber-fg)', borderColor: '#e8dfb6' }
    : { background: 'var(--library-rail)', color: 'var(--olive)', borderColor: 'var(--border)' };
  return (
    <span
      className="inline-flex items-center gap-[6px] rounded-full border px-[10px] py-[4px] text-[11px] font-semibold"
      style={styles}
    >
      {icon}{children}
    </span>
  );
}

function GhostButton({
  children, onClick, disabled,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center gap-[8px] rounded-[10px] border border-[var(--border-strong)] bg-white px-[14px] py-[9px] text-[13px] font-medium text-[var(--ink)] transition-colors hover:bg-[var(--library-rail)] disabled:cursor-not-allowed disabled:opacity-50"
    >
      {children}
    </button>
  );
}

function CheckCard({
  icon, title, subtitle, meta, state, statusText, children,
}: {
  step: string;
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  meta: string;
  state: 'todo' | 'active' | 'pass';
  statusText: string;
  children?: React.ReactNode;
}) {
  const isActive = state === 'active';
  const isPass = state === 'pass';

  return (
    <article
      className="grid items-center gap-[16px] rounded-[18px] border p-[16px_18px]"
      style={{
        gridTemplateColumns: '44px 1fr auto',
        background: isPass ? '#f3f7f0' : 'var(--ivory)',
        borderColor: isPass ? '#c6e0c9' : isActive ? 'var(--terracotta)' : 'var(--border)',
        boxShadow: isActive
          ? '0 0 0 1px var(--terracotta), var(--shadow-whisper)'
          : 'var(--shadow-whisper)',
        transition: '0.2s',
      }}
    >
      <div
        className="grid h-[44px] w-[44px] place-items-center rounded-[12px] border"
        style={{
          background: isPass ? '#e8f4e9' : isActive ? 'var(--terracotta)' : 'var(--library-rail)',
          color: isPass ? '#185c37' : isActive ? '#faf9f5' : 'var(--ink-soft)',
          borderColor: isPass ? '#c6e0c9' : isActive ? 'var(--terracotta)' : 'var(--border)',
        }}
      >
        {isPass ? <Check size={20} strokeWidth={1.7} /> : icon}
      </div>
      <div>
        <div className="flex items-baseline gap-[10px] text-[15px] font-semibold text-[var(--ink)]">
          {title}
          <span className="text-[12px] font-normal text-[var(--stone)]">{subtitle}</span>
        </div>
        <div className="mt-[3px] text-[13px] leading-[1.5] text-[var(--olive)]">{meta}</div>
      </div>
      <div
        className="inline-flex items-center gap-[6px] rounded-full border px-[10px] py-[5px] text-[12px] font-semibold"
        style={
          isPass
            ? { background: '#e8f4e9', borderColor: '#c6e0c9', color: '#185c37' }
            : isActive
              ? { background: '#fff2ec', borderColor: '#f2c0aa', color: 'var(--terracotta-strong)' }
              : { background: 'var(--library-rail)', borderColor: 'var(--border)', color: 'var(--olive)' }
        }
      >
        <span
          className="inline-block h-[6px] w-[6px] rounded-full"
          style={{
            background: isPass ? '#22a559' : isActive ? 'var(--terracotta)' : 'var(--stone)',
            animation: isActive ? 'itv-pulse-dot 1.2s ease-in-out infinite' : undefined,
          }}
        />
        {statusText}
      </div>

      {/* Test body — only shown for the active card */}
      {isActive && (
        <div
          className="border-t border-dashed pt-[14px]"
          style={{ gridColumn: '1 / -1', marginTop: 4, borderColor: 'var(--border-strong)' }}
        >
          {children}
        </div>
      )}
    </article>
  );
}

function Brief({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div
      className="flex items-start gap-[14px] border-b border-dashed border-[var(--border)] py-[10px] last:border-b-0"
    >
      <div className="min-w-[78px] pt-[2px] text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--stone)]">
        {k}
      </div>
      <div className="flex-1 text-[14px] leading-[1.55] text-[var(--ink)]">{v}</div>
    </div>
  );
}

function KeyHint({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="rounded-[6px] border px-[6px] py-[2px] text-[11px]"
      style={{
        fontFamily: 'var(--font-mono)',
        background: 'rgba(255,255,255,0.18)',
        borderColor: 'rgba(255,255,255,0.22)',
      }}
    >
      {children}
    </span>
  );
}

