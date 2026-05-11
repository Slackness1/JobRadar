import type { InterviewMessage, InterviewReport, InterviewReportRow } from './types';

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

// ---------------------------------------------------------------------------
// New typed payloads from the upgraded backend endpoints (Task 14)
// ---------------------------------------------------------------------------

export interface ScorePayload {
  overall: number | null;
  hits: string[];
  misses: string[];
  bonuses: string[];
}

export interface VoiceMetricsPayload {
  filler_rate: number | null;
  wpm: number | null;
  pause_count: number | null;
  response_latency_ms: number | null;
  confidence_score: number | null;
}

export interface TurnPayload {
  turn_index: number;
  question: string;
  user_answer: string;
  reference_answer: string;
  question_source: string;
  parent_turn_index: number | null;
  score: ScorePayload | null;
  voice_metrics: VoiceMetricsPayload | null;
  created_at: string;
}

export interface LatestScorePayload {
  turn_index: number;
  hint: string;
}

export interface InterviewReportPayload {
  id: number;
  target_job: string;
  transcript: { role: string; content: string }[];
  report: Record<string, unknown>;
  duration_seconds: number;
  created_at: string;
  turn_count: number;
  weakness_profile: {
    avg_score: number | null;
    weak_topics: string[];
    strong_topics: string[];
    gap_warnings: string[];
  } | null;
  weekly_plan_md: string;
}

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url, {
    headers: { 'X-Resume-User-Key': getUserKey() },
  });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

export function getInterviewTurns(sessionId: string): Promise<TurnPayload[]> {
  return getJson<TurnPayload[]>(`/api/interview/sessions/${sessionId}/turns`);
}

export interface SkeletonPayload {
  chip: string;
  matched: boolean;
  topic_labels: string[];
  questions: string[];
}

export function getInterviewSkeleton(chip: string): Promise<SkeletonPayload> {
  return getJson<SkeletonPayload>(`/api/interview/skeleton?chip=${encodeURIComponent(chip)}`);
}

export function getLatestScore(sessionId: string): Promise<LatestScorePayload | null> {
  return getJson<LatestScorePayload | null>(
    `/api/interview/sessions/${sessionId}/turns/latest-score`,
  );
}

// ---------------------------------------------------------------------------
// Streaming turn helper
// ---------------------------------------------------------------------------

export interface StreamInterviewTurnOptions {
  sessionId?: string;
  asrTranscript?: string;
  jdContent?: string;
}

/**
 * Parse a single raw SSE line and dispatch to the appropriate callback.
 *
 * New backend event types (Task 16):
 *   { type: "chunk", delta: string }         — text delta to append
 *   { type: "turn_complete", turn_index: number, question: string } — turn persisted
 *   { type: "error", error: string }          — LLM-level error
 *
 * Legacy fallback: raw OpenAI-style `choices[0].delta.content` objects
 * (kept so the handler works even if backend hasn't been updated yet).
 */
export function handleSSEMessage(
  rawLine: string,
  onChunk: (delta: string) => void,
  onTurnComplete: (idx: number, q: string) => void,
): void {
  if (!rawLine.startsWith('data:')) return;
  const payload = rawLine.slice(5).trim();
  if (!payload || payload === '[DONE]') return;
  try {
    const event = JSON.parse(payload) as {
      type?: string;
      delta?: string;
      turn_index?: number;
      question?: string;
      error?: string;
      choices?: { delta?: { content?: string } }[];
    };
    if (event.type === 'chunk' && typeof event.delta === 'string') {
      onChunk(event.delta);
    } else if (
      event.type === 'turn_complete' &&
      typeof event.turn_index === 'number' &&
      typeof event.question === 'string'
    ) {
      onTurnComplete(event.turn_index, event.question);
    } else if (event.error) {
      throw new Error(`LLM error: ${event.error}`);
    } else {
      // Legacy: OpenAI-style choices delta
      const token: string = event?.choices?.[0]?.delta?.content ?? '';
      if (token) onChunk(token);
    }
  } catch (err) {
    if (err instanceof Error && err.message.startsWith('LLM error:')) {
      throw err;
    }
    // Legacy: treat the whole payload as a chunk delta
    onChunk(payload);
  }
}

/** Stream a single interview turn. Calls onToken for each text delta, onDone when stream ends. */
export async function streamInterviewTurn(
  targetJob: string,
  messages: InterviewMessage[],
  onToken: (token: string) => void,
  onDone: () => void,
  options?: StreamInterviewTurnOptions & {
    onTurnComplete?: (turnIndex: number, question: string) => void;
  },
): Promise<void> {
  const response = await fetch('/api/interview/turn', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Resume-User-Key': getUserKey(),
    },
    body: JSON.stringify({
      target_job: targetJob,
      messages,
      ...(options?.sessionId ? { session_id: options.sessionId } : {}),
      ...(options?.asrTranscript ? { asr_transcript: options.asrTranscript } : {}),
      ...(options?.jdContent ? { jd_content: options.jdContent } : {}),
    }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Stream failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const onTurnComplete = options?.onTurnComplete ?? (() => {});

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value, { stream: true });
    for (const line of chunk.split('\n')) {
      handleSSEMessage(line.trim(), onToken, onTurnComplete);
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

export async function getInterviewReport(id: number): Promise<InterviewReportPayload> {
  const res = await fetch(`/api/interview/reports/${id}`, {
    headers: { 'X-Resume-User-Key': getUserKey() },
  });
  if (!res.ok) throw new Error(`Not found: ${id}`);
  return res.json();
}
