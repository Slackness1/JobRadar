'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import type { InterviewMessage, InterviewReport as InterviewReportType, InterviewState } from '@/components/interview/types';
import { streamInterviewTurn, saveInterviewReport } from '@/components/interview/api';
import { InterviewChat } from '@/components/interview/InterviewChat';
import { InterviewReport } from '@/components/interview/InterviewReport';

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

  // Initialize from localStorage or sessionStorage on first render (lazy initializers run only once)
  const [targetJob] = useState(() => {
    const saved = loadSession(sessionId);
    if (saved) return saved.targetJob;
    if (typeof window === 'undefined') return '';
    return sessionStorage.getItem(`interview.${sessionId}.job`) || '';
  });
  const [messages, setMessages] = useState<InterviewMessage[]>(() => loadSession(sessionId)?.messages ?? []);
  const [round, setRound] = useState(() => {
    const saved = loadSession(sessionId);
    return saved ? saved.messages.filter((m) => m.role === 'assistant').length : 0;
  });

  const [streamingContent, setStreamingContent] = useState('');
  const [state, setState] = useState<InterviewState>('interviewing');
  const [report, setReport] = useState<InterviewReportType | null>(null);
  const [reportError, setReportError] = useState('');
  const [finalDuration, setFinalDuration] = useState(0);
  const startTimeRef = useRef<number>(0);

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
          setStreamingContent(accumulated);
        },
        () => {
          const hasEnd = accumulated.includes(INTERVIEW_END_MARKER);
          const clean = accumulated.replace(INTERVIEW_END_MARKER, '').trim();
          const newMsg: InterviewMessage = { role: 'assistant', content: clean };
          const updatedMsgs = [...msgs, newMsg];
          setMessages(updatedMsgs);
          setStreamingContent('');
          setRound((r) => r + 1);
          saveSession(sessionId, updatedMsgs, job);
          if (hasEnd) triggerReport(job, updatedMsgs);
        },
      );
    } catch {
      setStreamingContent('');
      setMessages((prev) => [...prev, { role: 'assistant', content: '⚠️ 网络错误，请重新发送。' }]);
    }
  }, [sessionId, triggerReport]);

  // On first visit (no localStorage data): clean up sessionStorage and start first turn
  useEffect(() => {
    if (loadSession(sessionId)) return; // restored from localStorage, skip
    const job = sessionStorage.getItem(`interview.${sessionId}.job`) || '';
    if (!job) { router.push('/interview'); return; }
    sessionStorage.removeItem(`interview.${sessionId}.job`);
    setTimeout(() => startTurn(job, []), 0);
  }, [sessionId, router, startTurn]);

  function handleSend(content: string) {
    const userMsg: InterviewMessage = { role: 'user', content };
    const updatedMsgs = [...messages, userMsg];
    setMessages(updatedMsgs);
    setStreamingContent('');
    setState('interviewing');
    saveSession(sessionId, updatedMsgs, targetJob);
    startTurn(targetJob, updatedMsgs);
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
      <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--paper)] px-6 py-3">
        <div>
          <h1 className="text-[15px] font-semibold text-[var(--ink)]">{targetJob || '模拟面试'}</h1>
          <p className="text-[12px] text-[var(--muted)]">第 {round} 轮</p>
        </div>
        <div className="flex items-center gap-3">
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

      <InterviewChat
        messages={messages}
        streamingContent={streamingContent}
        isStreaming={!!streamingContent}
        disabled={state !== 'interviewing'}
        onSend={handleSend}
      />
    </main>
  );
}
