'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import type { InterviewMessage, InterviewReport as InterviewReportType, InterviewState } from '@/components/interview/types';
import { streamInterviewTurn, saveInterviewReport } from '@/components/interview/api';
import { InterviewChat } from '@/components/interview/InterviewChat';
import { InterviewReport } from '@/components/interview/InterviewReport';
import { VoiceControls } from '@/components/interview/voice/VoiceControls';
import { useTTSPlayer } from '@/components/interview/voice/useTTSPlayer';
import { SelfView } from '@/components/interview/devices/SelfView';
import { AvatarView } from '@/components/interview/devices/AvatarView';

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

  // Initialize from localStorage (session or pending key set by setup page)
  const [targetJob] = useState(() => {
    const saved = loadSession(sessionId);
    if (saved) return saved.targetJob;
    if (typeof window === 'undefined') return '';
    return localStorage.getItem(`interview.pending.${sessionId}`) || '';
  });
  const [messages, setMessages] = useState<InterviewMessage[]>(() => loadSession(sessionId)?.messages ?? []);
  const [round, setRound] = useState(() => {
    const saved = loadSession(sessionId);
    return saved ? saved.messages.filter((m) => m.role === 'assistant').length : 0;
  });

  const [streamingContent, setStreamingContent] = useState('');
  const [streamError, setStreamError] = useState('');
  const [isTurning, setIsTurning] = useState(false);
  const [state, setState] = useState<InterviewState>('interviewing');
  const [report, setReport] = useState<InterviewReportType | null>(null);
  const [reportError, setReportError] = useState('');
  const [finalDuration, setFinalDuration] = useState(0);
  const [voiceMode, setVoiceMode] = useState(false);
  // Text buffered while TTS is fetching / playing; revealed char-by-char as audio plays.
  const [pendingAssistantText, setPendingAssistantText] = useState('');
  const pendingMetaRef = useRef<{ msgs: InterviewMessage[]; job: string; hasEnd: boolean } | null>(null);
  const ttsTriggeredRef = useRef(false);
  const voiceModeRef = useRef(voiceMode);
  const startTimeRef = useRef<number>(0);
  const initializedRef = useRef(false);

  useEffect(() => { voiceModeRef.current = voiceMode; }, [voiceMode]);

  const tts = useTTSPlayer();

  useEffect(() => {
    startTimeRef.current = Date.now();
  }, []);

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

  const startTurn = useCallback(async (job: string, msgs: InterviewMessage[]) => {
    let accumulated = '';

    try {
      await streamInterviewTurn(
        job,
        msgs,
        (token) => {
          accumulated += token;
          // In voice mode we hide the LLM-streamed text and reveal it in sync
          // with TTS playback later. Keep streamingContent empty to show the spinner.
          if (!voiceModeRef.current) setStreamingContent(accumulated);
        },
        () => {
          const hasEnd = accumulated.includes(INTERVIEW_END_MARKER);
          const clean = accumulated.replace(INTERVIEW_END_MARKER, '').trim();
          if (!clean) {
            setStreamingContent('');
            setIsTurning(false);
            setStreamError('面试官回复为空，可能是 LLM 接口异常。请检查后端日志或重试。');
            return;
          }
          if (voiceModeRef.current) {
            // Hand off to the TTS-reveal pipeline; commit happens when audio ends.
            pendingMetaRef.current = { msgs, job, hasEnd };
            ttsTriggeredRef.current = false;
            setStreamingContent('');
            setPendingAssistantText(clean);
            // isTurning stays true until TTS finishes.
            return;
          }
          // Text mode: commit immediately.
          const newMsg: InterviewMessage = { role: 'assistant', content: clean };
          const updatedMsgs = [...msgs, newMsg];
          setMessages(updatedMsgs);
          setStreamingContent('');
          setIsTurning(false);
          setRound((r) => r + 1);
          saveSession(sessionId, updatedMsgs, job);
          if (hasEnd) triggerReport(job, updatedMsgs);
        },
      );
    } catch (err) {
      setStreamingContent('');
      setIsTurning(false);
      setStreamError(err instanceof Error ? err.message : '网络错误，请重试。');
    }
  }, [sessionId, triggerReport]);

  // On first visit: read pending job from localStorage, start first turn.
  // Strict Mode fires this effect twice in dev. The ref guards against double-execution
  // (refs are preserved across Strict Mode's simulated unmount/remount).
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;
    if (loadSession(sessionId)) return; // restored from localStorage
    const job = localStorage.getItem(`interview.pending.${sessionId}`) || '';
    if (!job) { router.push('/interview'); return; }
    localStorage.removeItem(`interview.pending.${sessionId}`);
    setTimeout(() => { setIsTurning(true); startTurn(job, []); }, 0);
  }, [sessionId, router, startTurn]);

  function handleSend(content: string) {
    tts.stop();
    const userMsg: InterviewMessage = { role: 'user', content };
    const updatedMsgs = [...messages, userMsg];
    setMessages(updatedMsgs);
    setStreamingContent('');
    setStreamError('');
    setIsTurning(true);
    setState('interviewing');
    saveSession(sessionId, updatedMsgs, targetJob);
    startTurn(targetJob, updatedMsgs);
  }

  // ---- Voice-mode pipeline ----
  // 1. When pending text is set, kick off TTS (once).
  useEffect(() => {
    if (!voiceMode || !pendingAssistantText || ttsTriggeredRef.current) return;
    ttsTriggeredRef.current = true;
    tts.speak(pendingAssistantText);
  }, [pendingAssistantText, voiceMode, tts]);

  // 2. Character reveal is computed at render time from progress (see JSX below).

  // 3. When TTS ends (or errors), commit the pending message and move on.
  useEffect(() => {
    if (!pendingAssistantText || !ttsTriggeredRef.current) return;
    const finished = !tts.isPlaying && (tts.progress >= 1 || !!tts.error);
    if (!finished) return;

    const meta = pendingMetaRef.current;
    if (!meta) return;
    const newMsg: InterviewMessage = { role: 'assistant', content: pendingAssistantText };
    const updatedMsgs = [...meta.msgs, newMsg];
    setMessages(updatedMsgs);
    setStreamingContent('');
    setIsTurning(false);
    setRound((r) => r + 1);
    saveSession(sessionId, updatedMsgs, meta.job);
    if (meta.hasEnd) triggerReport(meta.job, updatedMsgs);

    pendingMetaRef.current = null;
    ttsTriggeredRef.current = false;
    setPendingAssistantText('');
  }, [tts.isPlaying, tts.progress, tts.error, pendingAssistantText, sessionId, triggerReport]);

  const toggleVoiceMode = useCallback(() => {
    const next = !voiceMode;
    setVoiceMode(next);
    tts.stop();
    // If turning OFF voice while a message is waiting for TTS reveal, commit it now.
    if (!next && pendingAssistantText) {
      const meta = pendingMetaRef.current;
      if (meta) {
        const newMsg: InterviewMessage = { role: 'assistant', content: pendingAssistantText };
        const updatedMsgs = [...meta.msgs, newMsg];
        setMessages(updatedMsgs);
        setIsTurning(false);
        setRound((r) => r + 1);
        saveSession(sessionId, updatedMsgs, meta.job);
        if (meta.hasEnd) triggerReport(meta.job, updatedMsgs);
      }
      setStreamingContent('');
      setPendingAssistantText('');
      pendingMetaRef.current = null;
      ttsTriggeredRef.current = false;
    }
  }, [voiceMode, pendingAssistantText, sessionId, triggerReport, tts]);

  function handleRetry() {
    setStreamError('');
    setIsTurning(true);
    startTurn(targetJob, messages);
  }

  function handleEndInterview() {
    if (state !== 'interviewing') return;
    triggerReport(targetJob, messages);
  }

  if (state === 'report_ready' && report) {
    return (
      <main className="flex min-h-screen flex-col bg-[var(--background)]">
        <div className="border-b border-[var(--border)] bg-[var(--paper)] px-6 py-4">
          <h1 className="text-[16px] font-semibold text-[var(--ink)]">面试完成 · {targetJob}</h1>
        </div>
        <InterviewReport
          report={report}
          targetJob={targetJob}
          durationSeconds={finalDuration}
          onRestart={() => router.push('/interview')}
        />
      </main>
    );
  }

  return (
    <main className="flex h-screen flex-col bg-[var(--background)]">
      {voiceMode ? <AvatarView /> : <SelfView />}
      <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--paper)] px-6 py-3">
        <div>
          <h1 className="text-[15px] font-semibold text-[var(--ink)]">{targetJob || '模拟面试'}</h1>
          <p className="text-[12px] text-[var(--muted)]">第 {round} 轮</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={toggleVoiceMode}
            className={`rounded-[10px] border px-3 py-1.5 text-[13px] transition-colors ${
              voiceMode
                ? 'border-[var(--primary)] bg-[var(--primary)] text-white'
                : 'border-[var(--border)] text-[var(--muted)] hover:bg-[var(--soft)]'
            }`}
            title="切换语音 / 文字模式"
          >
            {voiceMode ? '🎙 语音模式' : '💬 文字模式'}
          </button>
          {tts.isPlaying && (
            <button
              onClick={() => tts.stop()}
              className="text-[12px] text-[var(--muted)] underline hover:text-[var(--ink)]"
            >
              停止播放
            </button>
          )}
          {state === 'generating_report' && (
            <span className="text-[13px] text-[var(--muted)]">生成报告中…</span>
          )}
          {reportError && (
            <button
              onClick={() => triggerReport(targetJob, messages)}
              className="text-[13px] text-red-500 underline"
            >
              {reportError} 重试
            </button>
          )}
          <button
            onClick={handleEndInterview}
            disabled={state !== 'interviewing' || messages.length < 2}
            className="rounded-[10px] border border-[var(--border)] px-3 py-1.5 text-[13px] text-[var(--muted)] hover:bg-[var(--soft)] disabled:opacity-30 transition-colors"
          >
            结束面试
          </button>
        </div>
      </div>

      {streamError && (
        <div className="mx-4 mt-3 flex items-center justify-between rounded-[10px] border border-red-300 bg-red-50 px-4 py-2.5 text-[13px] text-red-700">
          <span>⚠️ {streamError}</span>
          <button
            onClick={handleRetry}
            className="ml-3 rounded-[8px] border border-red-300 bg-white px-3 py-1 text-[12px] font-medium text-red-700 hover:bg-red-100"
          >
            重试
          </button>
        </div>
      )}

      <InterviewChat
        messages={messages}
        streamingContent={(() => {
          if (voiceMode && pendingAssistantText) {
            const len = pendingAssistantText.length;
            const revealed = Math.max(0, Math.round(len * tts.progress));
            return pendingAssistantText.slice(0, revealed);
          }
          return streamingContent;
        })()}
        isStreaming={isTurning || !!streamingContent || !!pendingAssistantText}
        disabled={isTurning || state !== 'interviewing'}
        onSend={handleSend}
        hideInput={voiceMode}
      />

      {voiceMode && (
        <VoiceControls
          disabled={isTurning || state !== 'interviewing' || tts.isPlaying}
          onSubmit={handleSend}
        />
      )}
    </main>
  );
}
