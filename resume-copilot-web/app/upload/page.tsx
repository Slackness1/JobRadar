'use client';

import { useState, type ChangeEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2, UploadCloud } from 'lucide-react';

import { createResumeCopilotSession } from '@/components/resume-copilot/api';

export default function UploadPage() {
  const router = useRouter();
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string>('');

  const onPickFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    setError('');
    setIsUploading(true);
    try {
      const created = await createResumeCopilotSession(file);
      router.replace(`/resume-copilot?sessionId=${created.session_id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '上传失败，请检查 PDF 文件');
      setIsUploading(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#f6f7f8] px-6 py-16 text-slate-950">
      <section className="mx-auto flex min-h-[78vh] max-w-3xl items-center justify-center">
        <div className="w-full max-w-[480px] rounded-[28px] border border-slate-200 bg-white px-8 py-9 shadow-[0_24px_70px_rgba(15,23,42,0.08)]">
          <div className="grid size-16 place-items-center rounded-full bg-sky-50 text-sky-600">
            <UploadCloud className="size-7" />
          </div>

          <h1 className="mt-6 text-3xl font-black tracking-tight text-slate-950">上传你的简历</h1>
          <p className="mt-3 text-sm leading-7 text-slate-600">
            支持 PDF。先生成第一版推荐，再对前排岗位做 10–20 秒快增强。
          </p>

          <label className="mt-8 inline-flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl bg-sky-700 px-5 py-3 text-base font-semibold text-white shadow-sm transition hover:bg-sky-800">
            <input
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={onPickFile}
              disabled={isUploading}
            />
            {isUploading ? <Loader2 className="size-4 animate-spin" /> : <UploadCloud className="size-4" />}
            {isUploading ? '上传中' : '上传简历'}
          </label>

          {error && (
            <div className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm leading-6 text-red-600">{error}</div>
          )}

          <div className="mt-5 text-xs leading-6 text-slate-500">
            最大 10MB。建议使用包含教育、实习、项目与技能信息的简历版本。
          </div>
        </div>
      </section>
    </main>
  );
}
