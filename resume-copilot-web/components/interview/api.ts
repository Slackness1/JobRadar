import type { InterviewMessage, InterviewReport, InterviewReportRow, SavedReport } from './types';

const USER_KEY_STORAGE_KEY = 'jobradar.resumeCopilot.userKey';

function getUserKey(): string {
  if (typeof window === 'undefined') return '';
  let key = window.localStorage.getItem(USER_KEY_STORAGE_KEY) || '';
  if (!key) {
    key = crypto.randomUUID();
    window.localStorage.setItem(USER_KEY_STORAGE_KEY, key);
  }
  return key;
}

/** Stream a single interview turn. Calls onToken for each text delta, onDone when stream ends. */
export async function streamInterviewTurn(
  targetJob: string,
  messages: InterviewMessage[],
  onToken: (token: string) => void,
  onDone: () => void,
): Promise<void> {
  const response = await fetch('/api/interview/turn', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Resume-User-Key': getUserKey(),
    },
    body: JSON.stringify({ target_job: targetJob, messages }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Stream failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    for (const line of chunk.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed.startsWith('data:')) continue;
      const data = trimmed.slice(5).trim();
      if (data === '[DONE]') continue;
      try {
        const event = JSON.parse(data);
        const token: string = event?.choices?.[0]?.delta?.content ?? '';
        if (token) onToken(token);
      } catch {
        // skip malformed SSE lines
      }
    }
  }
  onDone();
}

export async function saveInterviewReport(
  targetJob: string,
  messages: InterviewMessage[],
  durationSeconds: number,
): Promise<{ id: number; report: InterviewReport }> {
  const res = await fetch('/api/interview/report', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Resume-User-Key': getUserKey(),
    },
    body: JSON.stringify({ target_job: targetJob, messages, duration_seconds: durationSeconds }),
  });
  if (!res.ok) throw new Error(`Report failed: ${res.status}`);
  return res.json();
}

export async function listInterviewReports(): Promise<InterviewReportRow[]> {
  const res = await fetch('/api/interview/reports', {
    headers: { 'X-Resume-User-Key': getUserKey() },
  });
  if (!res.ok) return [];
  return res.json();
}

export async function getInterviewReport(id: number): Promise<SavedReport> {
  const res = await fetch(`/api/interview/reports/${id}`, {
    headers: { 'X-Resume-User-Key': getUserKey() },
  });
  if (!res.ok) throw new Error(`Not found: ${id}`);
  return res.json();
}
