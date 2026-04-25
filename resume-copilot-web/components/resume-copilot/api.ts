import type {
  ApplyRewriteOut,
  CopilotMessage,
  DirectionTierResult,
  ResumeConfirmedProfileOut,
  ResumeCopilotSession,
  ResumeCopilotSessionCreatedOut,
  ResumeCopilotSessionListItem,
  ResumeFeedbackResult,
  ResumeParsedProfileOut,
  ResumePreferenceOut,
  ResumePreferencePayload,
  ResumeProfilePayload,
  ResumeRecommendationResult,
} from './types';

// ── Constants ────────────────────────────────────────────────────────────────

export const DEMO_SESSION_ID = 1;

// ── User key (anonymous per-browser identity stored in localStorage) ─────────

const USER_KEY_STORAGE_KEY = 'jobradar.resumeCopilot.userKey';
const GUEST_STORAGE_KEY = 'jobradar.resumeCopilot.isGuest';

export function getOrCreateUserKey(): string {
  if (typeof window === 'undefined') return '';
  let key = window.localStorage.getItem(USER_KEY_STORAGE_KEY) || '';
  if (!key) {
    key = crypto.randomUUID();
    window.localStorage.setItem(USER_KEY_STORAGE_KEY, key);
  }
  return key;
}

export function isGuestUser(): boolean {
  if (typeof window === 'undefined') return false;
  return window.sessionStorage.getItem(GUEST_STORAGE_KEY) === '1';
}

export function markAsGuest(): void {
  if (typeof window === 'undefined') return;
  window.sessionStorage.setItem(GUEST_STORAGE_KEY, '1');
}

// ── Base request helper ───────────────────────────────────────────────────────

async function requestJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const userKey = getOrCreateUserKey();
  const guestHeaders: Record<string, string> = isGuestUser() ? { 'X-Guest': '1' } : {};
  const response = await fetch(input, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      'X-Resume-User-Key': userKey,
      ...guestHeaders,
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }

  if (response.status === 204 || response.headers.get('content-length') === '0') {
    return undefined as T;
  }
  const text = await response.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

// ── Session CRUD ──────────────────────────────────────────────────────────────

export function listResumeCopilotSessions() {
  return requestJson<ResumeCopilotSessionListItem[]>('/api/resume-copilot/sessions');
}

export function createResumeCopilotSession(file: File) {
  const form = new FormData();
  form.append('file', file);
  return requestJson<ResumeCopilotSessionCreatedOut>('/api/resume-copilot/sessions', {
    method: 'POST',
    body: form,
  });
}

export function getResumeCopilotSession(sessionId: number) {
  return requestJson<ResumeCopilotSession>(`/api/resume-copilot/sessions/${sessionId}`);
}

export function renameResumeCopilotSession(sessionId: number, name: string) {
  return requestJson<ResumeCopilotSession>(`/api/resume-copilot/sessions/${sessionId}`, {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  });
}

export function deleteResumeCopilotSession(sessionId: number) {
  return requestJson<void>(`/api/resume-copilot/sessions/${sessionId}`, { method: 'DELETE' });
}

// ── Profile / preferences / generate ─────────────────────────────────────────

export function getResumeCopilotParsedProfile(sessionId: number) {
  return requestJson<ResumeParsedProfileOut>(`/api/resume-copilot/sessions/${sessionId}/parsed-profile`);
}

export function putResumeCopilotConfirmedProfile(sessionId: number, profile: ResumeProfilePayload) {
  return requestJson<ResumeConfirmedProfileOut>(`/api/resume-copilot/sessions/${sessionId}/confirmed-profile`, {
    method: 'PUT',
    body: JSON.stringify({ profile }),
  });
}

export function getResumeCopilotPreferences(sessionId: number) {
  return requestJson<ResumePreferenceOut>(`/api/resume-copilot/sessions/${sessionId}/preferences`);
}

export function putResumeCopilotPreferences(sessionId: number, preferences: ResumePreferencePayload) {
  return requestJson<ResumePreferenceOut>(`/api/resume-copilot/sessions/${sessionId}/preferences`, {
    method: 'PUT',
    body: JSON.stringify({ preferences }),
  });
}

export function postResumeCopilotGenerate(sessionId: number) {
  return requestJson<ResumeCopilotSessionCreatedOut>(`/api/resume-copilot/sessions/${sessionId}/generate`, {
    method: 'POST',
  });
}

export function getResumeCopilotRecommendations(sessionId: number) {
  return requestJson<ResumeRecommendationResult>(`/api/resume-copilot/sessions/${sessionId}/recommendations`);
}

export function getResumeCopilotFeedback(sessionId: number) {
  return requestJson<ResumeFeedbackResult>(`/api/resume-copilot/sessions/${sessionId}/feedback`);
}

export function getDirectionAnalysis(sessionId: number) {
  return requestJson<DirectionTierResult[]>(
    `/api/resume-copilot/sessions/${sessionId}/direction-analysis`
  );
}

export function getChatMessages(sessionId: number) {
  return requestJson<CopilotMessage[]>(
    `/api/resume-copilot/sessions/${sessionId}/chat`
  );
}

export function postChatMessage(sessionId: number, content: string) {
  return requestJson<CopilotMessage>(`/api/resume-copilot/sessions/${sessionId}/chat`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
}

export function postApplyRewrite(sessionId: number, messageId: number, optionId: string) {
  return requestJson<ApplyRewriteOut>(
    `/api/resume-copilot/sessions/${sessionId}/chat/apply-rewrite`,
    {
      method: 'POST',
      body: JSON.stringify({ message_id: messageId, option_id: optionId }),
    }
  );
}
