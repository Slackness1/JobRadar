'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  Mic, MicOff, PhoneOff, Type, RotateCcw, Captions,
  MessageCircleQuestion,
} from 'lucide-react';
import type { InterviewMessage, InterviewReport as InterviewReportType, InterviewState } from '@/components/interview/types';
import { streamInterviewTurn, saveInterviewReport, getInterviewSkeleton } from '@/components/interview/api';
import { LiveHintBar } from '@/components/interview/LiveHintBar';
import { ProgressRail } from '@/components/interview/ProgressRail';
import { InterviewReport } from '@/components/interview/InterviewReport';
import { useTTSPlayer } from '@/components/interview/voice/useTTSPlayer';
import { useRecorder } from '@/components/interview/voice/useRecorder';
import { TopBar, Pill, AIOrb, ListenWave } from '@/components/interview/primitives';

const INTERVIEW_END_MARKER = '[INTERVIEW_END]';
const LS_PREFIX = 'interview.';

function loadSession(sessionId: string): { messages: InterviewMessage[]; targetJob: string } | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(`${LS_PREFIX}${sessionId}`);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return null;
}

function saveSession(sessionId: string, messages: InterviewMessage[], targetJob: string) {
  try {
    localStorage.setItem(`${LS_PREFIX}${sessionId}`, JSON.stringify({ messages, targetJob }));
  } catch { /* ignore */ }
}

export default function InterviewSessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const router = useRouter();

  /* ───────────────────── Hydration ──────────────────────────────────────── */
  const [targetJob, setTargetJob] = useState('');
  const [messages, setMessages] = useState<InterviewMessage[]>([]);
  const [round, setRound] = useState(0);
  // Topic labels for the 6-question skeleton, fetched from backend once we know
  // targetJob. Drives both ProgressRail's labels and the caption "topic chip".
  // Falls back to default labels (matches backend SKELETON_TOPIC_LABELS) if fetch fails.
  const [topicLabels, setTopicLabels] = useState<string[]>([
    '自我介绍与来意', '主导过的核心项目', '关键技术 / 业务取舍',
    '在不确定下的决策', '为什么是这家公司', '反问环节',
  ]);

  // Synthesized JD context from the recommendation card (target_direction +
  // topic_summary + enrichment + why/strengths/risks). Sent to backend so the
  // interview drills on 岗位特定 考察点 instead of just generic track questions.
  const [jdContent, setJdContent] = useState('');

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    const saved = loadSession(sessionId);
    if (saved) {
      setTargetJob(saved.targetJob);
      setMessages(saved.messages);
      // round = turn_index of the question being currently asked (0-based).
      // = (number of assistant messages) - 1, clamped to >= 0.
      const assistantCount = saved.messages.filter((m) => m.role === 'assistant').length;
      setRound(Math.max(0, assistantCount - 1));
    } else {
      setTargetJob(localStorage.getItem(`interview.pending.${sessionId}`) || '');
    }
    try {
      setJdContent(localStorage.getItem(`interview.jd.${sessionId}`) || '');
    } catch { /* ignore */ }
  }, [sessionId]);
  /* eslint-enable react-hooks/set-state-in-effect */

  // Fetch authoritative topic labels from backend whenever target job changes.
  // Backend is the single source of truth — eliminates the prior bug where
  // ProgressRail showed "为什么是这家公司" while backend was asking "团队冲突".
  useEffect(() => {
    if (!targetJob) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await getInterviewSkeleton(targetJob);
        if (!cancelled && Array.isArray(data.topic_labels) && data.topic_labels.length > 0) {
          setTopicLabels(data.topic_labels);
        }
      } catch { /* keep fallback labels */ }
    })();
    return () => { cancelled = true; };
  }, [targetJob]);

  /* ───────────────────── Stream / state ─────────────────────────────────── */
  const [streamingContent, setStreamingContent] = useState('');
  const [streamError, setStreamError] = useState('');
  const [isTurning, setIsTurning] = useState(false);
  const [state, setState] = useState<InterviewState>('interviewing');
  const [report, setReport] = useState<InterviewReportType | null>(null);
  const [reportError, setReportError] = useState('');
  const [finalDuration, setFinalDuration] = useState(0);

  // mode: voice (default — speak via mic) or text (type your answer).
  const [mode, setMode] = useState<'voice' | 'text'>('voice');
  // The text the AI just produced; revealed char-by-char as TTS plays.
  const [pendingAssistantText, setPendingAssistantText] = useState('');
  const pendingMetaRef = useRef<{ msgs: InterviewMessage[]; job: string; hasEnd: boolean } | null>(null);
  const ttsTriggeredRef = useRef(false);
  // Tracks whether TTS audio has actually started playing for the CURRENT pending text.
  // Without this, round 2+ commits early because tts.progress is still 1 from round 1
  // before the new speak() call resets it.
  const ttsPlayedRef = useRef(false);
  const modeRef = useRef(mode);
  const startTimeRef = useRef<number>(0);
  const initializedRef = useRef(false);
  const [showTranscript, setShowTranscript] = useState(false);
  const [textDraft, setTextDraft] = useState('');
  const [toast, setToast] = useState('');
  const [micMuted, setMicMuted] = useState(false);

  useEffect(() => { modeRef.current = mode; }, [mode]);

  const tts = useTTSPlayer();
  const recorder = useRecorder({
    onFinalizedChange: (text) => { if (mode === 'voice') setTextDraft(text); },
  });

  useEffect(() => { startTimeRef.current = Date.now(); }, []);

  /* ───────────────────── Elapsed timer for the rail ─────────────────────── */
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - startTimeRef.current) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);

  /* ───────────────────── Report flow ────────────────────────────────────── */
  const triggerReport = useCallback(async (job: string, msgs: InterviewMessage[]) => {
    setState('generating_report');
    setReportError('');
    const duration = Math.floor((Date.now() - startTimeRef.current) / 1000);
    setFinalDuration(duration);
    try {
      const { report: r } = await saveInterviewReport(job, msgs, duration);
      setReport(r);
      setState('report_ready');
    } catch {
      setReportError('报告生成失败，请重试。');
      setState('interviewing');
    }
  }, []);

  /* ───────────────────── LLM streaming turn ─────────────────────────────── */
  const startTurn = useCallback(async (job: string, msgs: InterviewMessage[], asrTranscript?: string) => {
    let accumulated = '';
    try {
      await streamInterviewTurn(
        job,
        msgs,
        (token) => {
          accumulated += token;
          if (modeRef.current === 'text') setStreamingContent(accumulated);
        },
        () => {
          const hasEnd = accumulated.includes(INTERVIEW_END_MARKER);
          const clean = accumulated.replace(INTERVIEW_END_MARKER, '').trim();
          if (!clean) {
            setStreamingContent('');
            setIsTurning(false);
            setStreamError('面试官回复为空，可能是 LLM 接口异常。请稍后重试。');
            return;
          }
          if (modeRef.current === 'voice') {
            pendingMetaRef.current = { msgs, job, hasEnd };
            ttsTriggeredRef.current = false;
            setStreamingContent('');
            setPendingAssistantText(clean);
            return;
          }
          // text mode: commit immediately
          const newMsg: InterviewMessage = { role: 'assistant', content: clean };
          const updated = [...msgs, newMsg];
          setMessages(updated);
          setStreamingContent('');
          setIsTurning(false);
          saveSession(sessionId, updated, job);
          if (hasEnd) triggerReport(job, updated);
        },
        {
          sessionId,
          asrTranscript,
          jdContent: jdContent || undefined,
          onTurnComplete: (turnIndex) => {
            // round = current question's turn_index (0-based, matches backend).
            // turnIndex is the just-asked question's index, so it IS the current round.
            setRound(turnIndex);
          },
        },
      );
    } catch (err) {
      setStreamingContent('');
      setIsTurning(false);
      setStreamError(err instanceof Error ? err.message : '网络错误，请重试。');
    }
  }, [sessionId, triggerReport, jdContent]);

  /* ───────────────────── Kick off the first turn on first visit ─────────── */
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;
    if (loadSession(sessionId)) return;
    const job = localStorage.getItem(`interview.pending.${sessionId}`) || '';
    if (!job) { router.push('/interview'); return; }
    localStorage.removeItem(`interview.pending.${sessionId}`);
    setTimeout(() => { setIsTurning(true); startTurn(job, []); }, 0);
  }, [sessionId, router, startTurn]);

  /* ───────────────────── Voice pipeline: TTS speak + commit ─────────────── */
  useEffect(() => {
    if (mode !== 'voice' || !pendingAssistantText || ttsTriggeredRef.current) return;
    ttsTriggeredRef.current = true;
    ttsPlayedRef.current = false; // reset for this turn
    tts.speak(pendingAssistantText);
  }, [pendingAssistantText, mode, tts]);

  // Watch for TTS actually starting (so we don't mistake stale round-1 progress for "done").
  useEffect(() => {
    if (tts.isPlaying) ttsPlayedRef.current = true;
  }, [tts.isPlaying]);

  useEffect(() => {
    if (!pendingAssistantText || !ttsTriggeredRef.current) return;
    // Only consider "finished" once TTS has actually played at least once for THIS turn.
    if (!ttsPlayedRef.current && !tts.error) return;
    const finished = !tts.isPlaying && (tts.progress >= 1 || !!tts.error);
    if (!finished) return;

    const meta = pendingMetaRef.current;
    if (!meta) return;
    const newMsg: InterviewMessage = { role: 'assistant', content: pendingAssistantText };
    const updated = [...meta.msgs, newMsg];
    setMessages(updated);
    setStreamingContent('');
    setIsTurning(false);
    saveSession(sessionId, updated, meta.job);
    if (meta.hasEnd) triggerReport(meta.job, updated);

    pendingMetaRef.current = null;
    ttsTriggeredRef.current = false;
    ttsPlayedRef.current = false;
    setPendingAssistantText('');
    setToast('已记录回答 · 进入下一问');
    setTimeout(() => setToast(''), 2000);
  }, [tts.isPlaying, tts.progress, tts.error, pendingAssistantText, sessionId, triggerReport]);

  /* ───────────────────── Self-view camera ───────────────────────────────── */
  const selfVideoRef = useRef<HTMLVideoElement>(null);
  const selfStreamRef = useRef<MediaStream | null>(null);
  const [selfReady, setSelfReady] = useState(false);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const s = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
        if (cancelled) { s.getTracks().forEach((t) => t.stop()); return; }
        selfStreamRef.current = s;
        if (selfVideoRef.current) {
          selfVideoRef.current.srcObject = s;
          await selfVideoRef.current.play().catch(() => {});
        }
        setSelfReady(true);
      } catch { /* denied */ }
    })();
    return () => { cancelled = true; selfStreamRef.current?.getTracks().forEach((t) => t.stop()); };
  }, []);

  /* ───────────────────── Mic input bar (voice mode) ─────────────────────── */
  const handleSend = useCallback((content: string, asrTranscript?: string) => {
    tts.stop();
    const userMsg: InterviewMessage = { role: 'user', content };
    const updated = [...messages, userMsg];
    setMessages(updated);
    setStreamingContent('');
    setStreamError('');
    setIsTurning(true);
    setState('interviewing');
    setTextDraft('');
    saveSession(sessionId, updated, targetJob);
    startTurn(targetJob, updated, asrTranscript);
  }, [messages, sessionId, startTurn, targetJob, tts]);

  const startListening = useCallback(() => {
    if (mode !== 'voice' || micMuted) return;
    setTextDraft('');
    recorder.start();
  }, [mode, recorder, micMuted]);

  const stopListeningAndSend = useCallback(() => {
    recorder.stop();
    const text = (recorder.finalText + recorder.partialText).trim();
    if (!text) return;
    // Pass the ASR transcript for backend voice-metrics analysis.
    handleSend(text, text);
  }, [recorder, handleSend]);

  // Tap-to-toggle space:
  //   • AI is speaking          → interrupt the AI (do not start recording)
  //   • Already recording        → stop + send what was captured
  //   • Idle                     → start recording
  useEffect(() => {
    if (mode !== 'voice') return;
    const onDown = (e: KeyboardEvent) => {
      if (e.code !== 'Space' || e.repeat) return;
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      e.preventDefault();
      if (tts.isPlaying) { tts.stop(); return; }
      if (recorder.isRecording) { stopListeningAndSend(); return; }
      if (micMuted) return;
      startListening();
    };
    window.addEventListener('keydown', onDown);
    return () => { window.removeEventListener('keydown', onDown); };
  }, [mode, startListening, stopListeningAndSend, tts, recorder.isRecording, micMuted]);

  /* ───────────────────── Caption text (TTS-progress reveal) ─────────────── */
  const captionText = useMemo(() => {
    if (mode === 'voice' && pendingAssistantText) {
      const len = pendingAssistantText.length;
      return pendingAssistantText.slice(0, Math.round(len * tts.progress));
    }
    return streamingContent;
  }, [mode, pendingAssistantText, tts.progress, streamingContent]);

  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant');
  // While a turn is in flight (LLM streaming or TTS playing), show the live caption
  // even if it's currently an empty string. Only fall back to the last committed
  // message when there is genuinely nothing in flight — otherwise round 2+ would
  // briefly flash round 1's full text whenever progress is 0.
  const turnInFlight = isTurning || !!pendingAssistantText || tts.isPlaying;
  const captionDisplayed = turnInFlight ? captionText : (lastAssistant?.content ?? '');
  const showCursor = isTurning || (mode === 'voice' && tts.isPlaying && captionText.length < pendingAssistantText.length);

  /* ───────────────────── Status (orb + caption header) ──────────────────── */
  const isThinking = isTurning && !tts.isPlaying;
  const isSpeaking = tts.isPlaying;
  const isListening = recorder.isRecording;
  const orbStatus = isThinking ? '正在思考下一问…'
    : isSpeaking ? `正在讲第 ${round + 1} 问…`
    : isListening ? '听你说…'
    : round === 0 ? '准备就绪'
    : '讲完了 · 等你作答';

  /* ───────────────────── End interview / Skip ───────────────────────────── */
  const handleEndInterview = useCallback(() => {
    if (state !== 'interviewing') return;
    triggerReport(targetJob, messages);
  }, [state, targetJob, messages, triggerReport]);

  const handleRetry = useCallback(() => {
    setStreamError('');
    setIsTurning(true);
    startTurn(targetJob, messages);
  }, [targetJob, messages, startTurn]);

  /* ───────────────────── Report screen ──────────────────────────────────── */
  if (state === 'report_ready' && report) {
    return (
      <main className="min-h-screen" style={{ background: 'var(--parchment)' }}>
        <TopBar crumb={<>模拟面试 · <b className="font-medium text-[var(--ink-soft)]">面试报告</b></>} />
        <div className="mx-auto max-w-[960px] px-6 py-6">
          <h1
            className="mb-4 text-[28px] text-[var(--ink)]"
            style={{ fontFamily: 'var(--font-serif)', fontWeight: 500 }}
          >
            面试完成 · {targetJob}
          </h1>
          <InterviewReport
            report={report}
            targetJob={targetJob}
            durationSeconds={finalDuration}
            onRestart={() => router.push('/interview')}
          />
        </div>
      </main>
    );
  }

  /* ───────────────────── Render — interview stage ───────────────────────── */
  return (
    <main className="grid h-screen grid-rows-[auto_1fr_auto] overflow-hidden" style={{ background: 'var(--parchment)' }}>
      {/* TOP BAR */}
      <header
        className="flex items-center gap-[14px] border-b border-[var(--border)] px-[22px] py-[12px]"
        style={{ background: 'rgba(245,244,237,0.92)', backdropFilter: 'blur(10px)' }}
      >
        <span
          className="inline-flex items-center gap-[10px] text-[17px] tracking-[-0.02em] text-[var(--ink)]"
          style={{ fontFamily: 'var(--font-serif)', fontWeight: 500 }}
        >
          <span className="inline-block h-[9px] w-[9px] rounded-full" style={{ background: 'var(--terracotta)' }} />
          JobRadar
        </span>
        <div
          className="ml-1 border-l border-[var(--border-strong)] pl-[14px] text-[13px] font-semibold leading-[1.35] text-[var(--ink)]"
        >
          {targetJob || '模拟面试'}
          <span className="block text-[11px] font-normal text-[var(--stone)]">AI 面试官 · 姜老师</span>
        </div>
        <span className="flex-1" />
        <Pill>
          <span className="inline-block h-[6px] w-[6px] rounded-full" style={{ background: 'var(--emerald)' }} />
          已连接 · 16 kHz
        </Pill>
        <ModeTabs mode={mode} onChange={setMode} />
        <button
          onClick={handleEndInterview}
          className="inline-flex items-center gap-[8px] rounded-[10px] border bg-white px-[16px] py-[8px] text-[13px] font-semibold text-[var(--crimson)] hover:bg-[#fdf4f4]"
          style={{ borderColor: '#e8cdcd' }}
        >
          <PhoneOff size={14} strokeWidth={1.7} />结束面试
        </button>
      </header>

      {/* MAIN STAGE */}
      <section className="relative overflow-hidden">
        {/* Question marker — derives topic label from backend's authoritative
            skeleton, not a hardcoded "项目深挖" string. Past the skeleton (turn
            >= labels.length) it's a generated follow-up so we just say 深挖追问. */}
        <div className="absolute left-[28px] top-[68px] z-[2] text-[11px] tracking-[0.08em] text-[var(--stone)]">
          <b className="mr-[6px] text-[12px] font-semibold text-[var(--ink)]">第 {round + 1} 问</b>
          {round < topicLabels.length ? topicLabels[round] : '深挖追问'}
        </div>

        {/* CAPTIONS — Border Beam wraps the entire box during thinking */}
        <div
          className="absolute left-1/2 top-[26px] z-[5] w-[calc(100%-56px)] max-w-[960px] -translate-x-1/2"
        >
          <div
            className="relative rounded-[18px]"
            style={{
              background: 'var(--deep-dark)',
              color: '#faf9f5',
              padding: '18px 26px 20px',
              boxShadow: '0 20px 48px rgba(0,0,0,0.18), 0 0 0 1px rgba(255,255,255,0.04)',
            }}
          >
            <div className="mb-[10px] flex items-center gap-[10px] text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--warm-silver)]">
              <span
                className="relative inline-block h-[18px] w-[18px] rounded-full"
                style={{
                  background: 'var(--terracotta)',
                  animation: 'itv-breathe 1.8s ease-in-out infinite',
                }}
              />
              <span>AI 面试官 · {isThinking ? '正在思考' : isSpeaking ? '正在讲' : isListening ? '在听你说' : '等你作答'}</span>
              <span className="text-[var(--warm-silver)] font-medium tracking-[0.12em]">· Question {round + 1}</span>
              <span className="flex-1" />
              <span className="text-[11px] font-normal tracking-normal text-[var(--warm-silver)]" style={{ fontFamily: 'var(--font-mono)' }}>
                {fmtMMSS(elapsed)}
              </span>
            </div>

            <div
              className="text-[#faf9f5]"
              style={{
                fontFamily: 'var(--font-serif)',
                fontWeight: 500,
                fontSize: 22,
                lineHeight: 1.55,
                letterSpacing: '-0.005em',
                minHeight: 68,
              }}
            >
              {captionDisplayed || (
                <span className="text-[var(--warm-silver)]">{isThinking ? '…' : '面试即将开始。'}</span>
              )}
              {showCursor && (
                <span
                  className="ml-[2px] inline-block align-baseline"
                  style={{
                    width: 10,
                    height: '1.1em',
                    verticalAlign: '-0.15em',
                    background: 'var(--terracotta)',
                    animation: 'itv-blink-cursor 1s step-end infinite',
                  }}
                />
              )}
            </div>

            <div
              className="mt-[14px] flex items-center gap-[6px] border-t pt-[12px] text-[11px] text-[var(--warm-silver)]"
              style={{ borderColor: 'rgba(255,255,255,0.07)' }}
            >
              <span
                className="inline-flex items-center gap-[5px] rounded-full px-[9px] py-[4px] text-[11px] font-medium"
                style={{
                  background: 'rgba(201,100,66,0.18)',
                  border: '1px solid rgba(201,100,66,0.4)',
                  color: '#faf9f5',
                }}
              >
                <MessageCircleQuestion size={12} strokeWidth={1.8} />
                {round < topicLabels.length ? topicLabels[round] : '深挖追问'}
              </span>
              <span
                className="inline-flex items-center gap-[5px] rounded-full px-[9px] py-[4px] text-[11px] font-medium"
                style={{
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.08)',
                }}
              >
                岗位：{targetJob || '—'}
              </span>
              <span className="flex-1" />
              <button
                className="cursor-pointer text-[var(--warm-silver)] underline"
                onClick={() => setShowTranscript((v) => !v)}
              >
                {showTranscript ? '收起逐字稿' : '查看全文逐字稿'}
              </button>
            </div>

            {/* Border Beam — show whenever AI is busy (streaming OR speaking),
                not just during the brief LLM-streaming-before-TTS window. */}
            {turnInFlight && <div className="border-beam" style={{ borderRadius: 18 }} />}

            {/* Live hint bar — polls /turns/latest-score, fades in after AI speaks */}
            <LiveHintBar sessionId={sessionId} suppressed={turnInFlight} />
          </div>
        </div>

        {/* TRANSCRIPT (overlay, toggled) */}
        {showTranscript && (
          <div
            className="absolute left-1/2 z-[4] w-[calc(100%-56px)] max-w-[960px] -translate-x-1/2 overflow-y-auto rounded-[18px] border border-[var(--border)] p-[16px_26px]"
            style={{
              top: 230,
              maxHeight: 'calc(100vh - 420px)',
              background: 'var(--ivory)',
              boxShadow: 'var(--shadow-whisper)',
            }}
          >
            {messages.map((m, i) => (
              <div
                key={i}
                className="flex gap-[14px] border-b border-dashed border-[var(--border)] py-[10px] last:border-b-0"
              >
                <div
                  className="w-[64px] flex-none pt-[2px] text-[11px] font-semibold uppercase tracking-[0.1em]"
                  style={{ color: m.role === 'assistant' ? 'var(--terracotta-strong)' : 'var(--ink)' }}
                >
                  {m.role === 'assistant' ? '面试官' : '你'}
                </div>
                <div className="flex-1 text-[14px] leading-[1.6] text-[var(--ink)]">{m.content}</div>
              </div>
            ))}
            {messages.length === 0 && (
              <div className="text-[13px] text-[var(--olive)]">面试还未开始。</div>
            )}
          </div>
        )}

        {/* PROGRESS RAIL — hidden < 1200px. Polls /turns to show real skeleton + sub-questions.
            topicLabels comes from backend; ProgressRail uses them as the rail's
            section names so the labels never lie about what's actually being asked. */}
        <ProgressRail
          sessionId={sessionId}
          topicLabels={topicLabels}
          currentTurnIndex={round}
          elapsedLabel={fmtMMSS(elapsed)}
        />

        {/* CENTER — AI orb */}
        <div
          className="pointer-events-none absolute flex flex-col items-center justify-center gap-[18px]"
          style={{ inset: '240px 0 160px' }}
        >
          <AIOrb />
          <div className="text-center">
            <div
              className="text-[22px] tracking-[-0.01em] text-[var(--ink)]"
              style={{ fontFamily: 'var(--font-serif)', fontWeight: 500 }}
            >
              姜老师 · AI 面试官
            </div>
            <div className="mt-[4px] inline-flex items-center gap-[8px] text-[12px] text-[var(--olive)]">
              <span
                className="inline-block h-[6px] w-[6px] rounded-full"
                style={{
                  background: isListening ? 'var(--emerald)' : 'var(--terracotta)',
                  animation: 'itv-pulse-dot 1.2s ease-in-out infinite',
                }}
              />
              {orbStatus}
            </div>
            <div className="mt-1 grid place-items-center">
              <ListenWave active={isListening} />
            </div>
          </div>
        </div>

        {/* SELF-VIEW */}
        <div
          className="absolute right-[28px] bottom-[110px] z-[3] w-[220px] overflow-hidden rounded-[16px]"
          style={{
            background: '#1c1c1b',
            boxShadow: '0 10px 30px rgba(0,0,0,0.18), 0 0 0 1px var(--border)',
          }}
        >
          <video
            ref={selfVideoRef}
            autoPlay muted playsInline
            className="block w-full"
            style={{ aspectRatio: '4 / 3', objectFit: 'cover', transform: 'scaleX(-1)', background: '#1c1c1b' }}
          />
          {!selfReady && (
            <div
              className="grid w-full place-items-center gap-[6px] text-[12px] text-[var(--warm-silver)]"
              style={{
                aspectRatio: '4 / 3',
                background: 'repeating-linear-gradient(135deg, #1c1c1b, #1c1c1b 14px, #232321 14px, #232321 28px)',
              }}
            >
              摄像头预览
            </div>
          )}
          <button
            type="button"
            onClick={() => {
              setMicMuted((m) => {
                const next = !m;
                if (next && recorder.isRecording) recorder.stop();
                setToast(next ? '已静音麦克风' : '已开启麦克风');
                setTimeout(() => setToast(''), 1600);
                return next;
              });
            }}
            title={micMuted ? '点击取消静音' : '点击静音麦克风'}
            className="flex w-full items-center gap-[8px] px-[12px] py-[8px] text-[11px] text-[#faf9f5] transition-colors hover:bg-[#262624]"
            style={{ background: '#1c1c1b', borderTop: '1px solid #30302e' }}
          >
            <span className="relative inline-flex">
              {micMuted ? <MicOff size={12} strokeWidth={1.7} /> : <Mic size={12} strokeWidth={1.7} />}
              {!micMuted && (
                <span
                  className="absolute -right-[3px] -top-[3px] inline-block h-[6px] w-[6px] rounded-full"
                  style={{
                    background: isListening ? 'var(--emerald)' : '#5fbf7a',
                    boxShadow: isListening
                      ? '0 0 0 2px rgba(95,191,122,0.25)'
                      : '0 0 0 2px rgba(95,191,122,0.15)',
                    animation: isListening ? 'itv-pulse-dot 1.2s ease-in-out infinite' : undefined,
                  }}
                />
              )}
            </span>
            <span>
              你 · 麦克风
              {micMuted ? '已静音' : isListening ? '打开中' : '在线'}
            </span>
            <span className="ml-auto inline-flex h-[12px] items-end gap-[2px]" style={{ opacity: micMuted ? 0.25 : 1 }}>
              {[0, 0.1, 0.2, 0.3].map((d, i) => (
                <span
                  key={i}
                  style={{
                    width: 3,
                    height: 4 + i * 2,
                    background: micMuted ? 'var(--stone)' : 'var(--emerald)',
                    borderRadius: 1,
                    animation: micMuted ? undefined : `itv-self-blip 1.2s ease-in-out infinite ${d}s`,
                  }}
                />
              ))}
            </span>
          </button>
        </div>

        {/* TOAST */}
        {toast && (
          <div
            className="absolute left-1/2 z-10 flex -translate-x-1/2 items-center gap-[8px] rounded-full px-[18px] py-[10px] text-[12.5px] text-[#faf9f5]"
            style={{
              bottom: 120,
              background: 'var(--deep-dark)',
              boxShadow: '0 10px 28px rgba(0,0,0,0.3)',
              animation: 'itv-toast-in 0.4s ease-out',
            }}
          >
            <span className="inline-block h-[6px] w-[6px] rounded-full" style={{ background: 'var(--emerald)' }} />
            {toast}
          </div>
        )}

        {streamError && (
          <div
            className="absolute left-1/2 z-10 -translate-x-1/2 rounded-[12px] border border-[#e8cdcd] bg-white px-[16px] py-[10px] text-[13px] text-[var(--crimson)] shadow"
            style={{ bottom: 160 }}
          >
            {streamError} ·
            <button onClick={handleRetry} className="ml-2 underline">重试</button>
          </div>
        )}

        {state === 'generating_report' && (
          <div
            className="absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-1/2 rounded-[18px] border border-[var(--border)] bg-[var(--ivory)] px-[24px] py-[18px] text-[14px] text-[var(--ink)] shadow"
          >
            生成面试报告中…
            {reportError && <div className="mt-2 text-[var(--crimson)]">{reportError}</div>}
          </div>
        )}
      </section>

      {/* FOOTER — mic input bar */}
      <footer
        className="flex items-center gap-[14px] border-t border-[var(--border)] px-[22px] py-[14px]"
        style={{ background: 'var(--library-rail)' }}
      >
        <button
          onClick={() => (isListening ? stopListeningAndSend() : startListening())}
          disabled={mode !== 'voice' || isTurning || isSpeaking || micMuted}
          title={micMuted ? '麦克风已静音 · 点击右下角解除' : '按住空格 / 点击切换'}
          className="grid h-[46px] w-[46px] place-items-center rounded-full border bg-white text-[var(--ink)] transition-colors disabled:cursor-not-allowed disabled:opacity-50"
          style={
            isListening
              ? {
                  background: 'var(--terracotta)',
                  color: '#faf9f5',
                  borderColor: 'var(--terracotta)',
                  boxShadow: '0 0 0 4px rgba(201,100,66,0.16), 0 0 0 8px rgba(201,100,66,0.06)',
                  animation: 'itv-pulse-dot 1.4s ease-in-out infinite',
                }
              : { borderColor: 'var(--border-strong)' }
          }
        >
          <Mic size={22} strokeWidth={1.7} />
        </button>

        <div
          className="flex min-h-[52px] flex-1 items-center gap-[12px] rounded-[14px] border border-[var(--border-strong)] bg-white px-[16px] py-[12px]"
        >
          {mode === 'voice' ? (
            <span className={`flex-1 text-[13px] ${isListening ? 'text-[var(--ink)]' : 'text-[var(--stone)]'}`}>
              {isListening
                ? `正在聆听你的回答 · ${textDraft || '…'}`
                : isSpeaking
                  ? '面试官在说话…'
                  : isTurning
                    ? '面试官思考中…'
                    : '点击麦克风开始语音作答 · 或按住空格键说话'}
              {isListening && (
                <span className="ml-[2px] text-[var(--terracotta)]" style={{ animation: 'itv-blink-cursor 1s step-end infinite' }}>｜</span>
              )}
            </span>
          ) : (
            <input
              className="flex-1 bg-transparent text-[13px] text-[var(--ink)] outline-none placeholder:text-[var(--stone)]"
              placeholder={isTurning ? '面试官思考中…' : '输入你的回答（Enter 提交）'}
              value={textDraft}
              onChange={(e) => setTextDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey && textDraft.trim() && !isTurning && !isSpeaking) {
                  e.preventDefault();
                  handleSend(textDraft.trim());
                }
              }}
              disabled={isTurning || isSpeaking}
            />
          )}
        </div>

        <div className="flex items-center gap-[8px]">
          <IconBtn title="重复问题" onClick={() => { if (lastAssistant && mode === 'voice') tts.speak(lastAssistant.content); }}>
            <RotateCcw size={18} strokeWidth={1.6} />
          </IconBtn>
          <IconBtn title="切换模式" onClick={() => setMode((m) => (m === 'voice' ? 'text' : 'voice'))}>
            {mode === 'voice' ? <Type size={18} strokeWidth={1.6} /> : <Mic size={18} strokeWidth={1.6} />}
          </IconBtn>
          <IconBtn title="切换字幕" onClick={() => setShowTranscript((v) => !v)}>
            <Captions size={18} strokeWidth={1.6} />
          </IconBtn>
          <IconBtn
            title={micMuted ? '点击取消静音麦克风' : '点击静音麦克风'}
            onClick={() => {
              setMicMuted((m) => {
                const next = !m;
                if (next && recorder.isRecording) recorder.stop();
                setToast(next ? '已静音麦克风' : '已开启麦克风');
                setTimeout(() => setToast(''), 1600);
                return next;
              });
            }}
            active={!micMuted}
            indicatorPulse={isListening}
          >
            {micMuted ? <MicOff size={18} strokeWidth={1.6} /> : <Mic size={18} strokeWidth={1.6} />}
          </IconBtn>
        </div>

        <span className="text-[11px] text-[var(--stone)]" style={{ fontFamily: 'var(--font-mono)' }}>
          Space 开始/结束 · Enter 提交
        </span>
      </footer>
    </main>
  );
}

/* ─────────────────────────── Local subcomponents ──────────────────────────── */

function ModeTabs({ mode, onChange }: { mode: 'voice' | 'text'; onChange: (m: 'voice' | 'text') => void }) {
  return (
    <div
      className="inline-flex rounded-[10px] border border-[var(--border)] p-[3px]"
      style={{ background: 'var(--library-rail)' }}
    >
      <button
        onClick={() => onChange('voice')}
        className="inline-flex items-center gap-[6px] rounded-[8px] px-[12px] py-[6px] text-[12px] font-medium transition-colors"
        style={{
          background: mode === 'voice' ? '#fff' : 'transparent',
          color: mode === 'voice' ? 'var(--ink)' : 'var(--olive)',
          boxShadow: mode === 'voice' ? '0 0 0 1px var(--border-strong), 0 1px 2px rgba(0,0,0,0.03)' : 'none',
        }}
      >
        <Mic size={14} strokeWidth={1.6} />
        语音模式
      </button>
      <button
        onClick={() => onChange('text')}
        className="inline-flex items-center gap-[6px] rounded-[8px] px-[12px] py-[6px] text-[12px] font-medium transition-colors"
        style={{
          background: mode === 'text' ? '#fff' : 'transparent',
          color: mode === 'text' ? 'var(--ink)' : 'var(--olive)',
          boxShadow: mode === 'text' ? '0 0 0 1px var(--border-strong), 0 1px 2px rgba(0,0,0,0.03)' : 'none',
        }}
      >
        <Type size={14} strokeWidth={1.6} />
        文本模式
      </button>
    </div>
  );
}

function IconBtn({
  children, onClick, title, active, indicatorPulse,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  title?: string;
  active?: boolean;
  indicatorPulse?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="relative grid h-[40px] w-[40px] place-items-center rounded-[10px] border border-transparent text-[var(--olive)] transition-colors hover:border-[var(--border)] hover:bg-white hover:text-[var(--ink)]"
    >
      {children}
      {active && (
        <span
          className="absolute right-[7px] top-[7px] inline-block h-[7px] w-[7px] rounded-full"
          style={{
            background: indicatorPulse ? 'var(--emerald)' : '#5fbf7a',
            boxShadow: indicatorPulse
              ? '0 0 0 2px rgba(95,191,122,0.25)'
              : '0 0 0 2px rgba(95,191,122,0.15)',
            animation: indicatorPulse ? 'itv-pulse-dot 1.2s ease-in-out infinite' : undefined,
          }}
        />
      )}
    </button>
  );
}

function fmtMMSS(secs: number): string {
  const m = String(Math.floor(secs / 60)).padStart(2, '0');
  const s = String(secs % 60).padStart(2, '0');
  return `${m}:${s}`;
}
