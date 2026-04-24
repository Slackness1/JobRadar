'use client';

import { useCallback, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { MicTest } from '@/components/interview/devices/MicTest';
import { CameraTest } from '@/components/interview/devices/CameraTest';
import { SpeakerTest } from '@/components/interview/devices/SpeakerTest';

export default function InterviewDeviceCheckPage() {
  const router = useRouter();
  const { sessionId } = useParams<{ sessionId: string }>();

  const [micPassed, setMicPassed] = useState(false);
  const [cameraPassed, setCameraPassed] = useState(false);
  const [speakerPassed, setSpeakerPassed] = useState(false);

  const allPassed = micPassed && cameraPassed && speakerPassed;

  const handleMicPassed = useCallback(() => setMicPassed(true), []);
  const handleCameraPassed = useCallback(() => setCameraPassed(true), []);
  const handleSpeakerPassed = useCallback(() => setSpeakerPassed(true), []);

  function proceed() {
    if (!allPassed) return;
    router.push(`/interview/${sessionId}`);
  }

  function skipCheck() {
    router.push(`/interview/${sessionId}`);
  }

  return (
    <main className="flex min-h-screen flex-col bg-[var(--background)]">
      <div className="mx-auto w-full max-w-4xl px-6 py-10">
        <div className="mb-6">
          <h1 className="mb-1 text-[22px] font-semibold text-[var(--ink)]">设备调试</h1>
          <p className="text-[14px] text-[var(--muted)]">
            面试开始前，请确认麦克风、摄像头和扬声器都能正常工作。
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <MicTest passed={micPassed} onPassed={handleMicPassed} />
          <CameraTest passed={cameraPassed} onPassed={handleCameraPassed} />
          <SpeakerTest passed={speakerPassed} onPassed={handleSpeakerPassed} />
        </div>

        <div className="mt-8 flex items-center justify-between">
          <button
            onClick={() => router.push('/interview')}
            className="text-[13px] text-[var(--muted)] underline hover:text-[var(--ink)]"
          >
            ← 返回
          </button>
          <div className="flex items-center gap-3">
            <button
              onClick={skipCheck}
              className="rounded-[12px] border border-[var(--border)] px-4 py-3 text-[13px] text-[var(--muted)] transition-colors hover:bg-[var(--soft)] hover:text-[var(--ink)]"
              title="跳过设备调试，直接进入面试（如果设备出问题面试体验会受影响）"
            >
              跳过调试
            </button>
            <button
              onClick={proceed}
              disabled={!allPassed}
              className="rounded-[12px] bg-[var(--primary)] px-6 py-3 text-[14px] font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {allPassed ? '设备就绪，开始面试 →' : '请完成所有设备验证'}
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
