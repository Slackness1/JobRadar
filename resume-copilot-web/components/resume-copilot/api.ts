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
  // 登录用户优先用 u_<id> 作为 user_key (永久 stable, 跨 session)
  const logged = getAuthUser();
  if (logged?.user_key) return logged.user_key;
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

// ── 账号系统 (alpha-1 内测,邀请码 gated) ────────────────────────────────────

const AUTH_TOKEN_KEY = 'jobradar.auth.token';
const AUTH_USER_KEY = 'jobradar.auth.user';

export interface AuthUser {
  user_id: number;
  email: string;
  email_verified: boolean;
  user_key: string;   // u_<id>
}

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(AUTH_TOKEN_KEY);
}

export function getAuthUser(): AuthUser | null {
  if (typeof window === 'undefined') return null;
  const raw = window.localStorage.getItem(AUTH_USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw) as AuthUser; } catch { return null; }
}

export function isAuthenticated(): boolean {
  return !!getAuthToken() && !!getAuthUser();
}

function setAuthState(token: string, user: AuthUser) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(AUTH_TOKEN_KEY, token);
  window.localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
  // 登录后强制 user_key = u_<id>,覆盖原 UUID
  window.localStorage.setItem(USER_KEY_STORAGE_KEY, user.user_key);
  // 登录态跟 guest 态互斥
  window.sessionStorage.removeItem(GUEST_STORAGE_KEY);
}

export function clearAuthState() {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
  window.localStorage.removeItem(AUTH_USER_KEY);
  // 不清 USER_KEY_STORAGE_KEY 留着原 UUID,登出后还能继续匿名
}

// 注册/登录/验证邮箱 API (走 backend /api/auth/*)

export interface RegisterResult {
  user_id: number;
  email: string;
  email_verified: boolean;
  message: string;
}

export interface AuthSuccessResult {
  token: string;
  user_id: number;
  email: string;
  email_verified: boolean;
}

export async function apiRegister(payload: {
  email: string; password: string; invite_code: string;
}): Promise<RegisterResult> {
  return requestJson<RegisterResult>('/api/auth/register', {
    method: 'POST', body: JSON.stringify(payload),
  });
}

export async function apiVerifyEmail(payload: { user_id: number; code: string }): Promise<AuthSuccessResult> {
  const result = await requestJson<AuthSuccessResult>('/api/auth/verify-email', {
    method: 'POST', body: JSON.stringify(payload),
  });
  setAuthState(result.token, {
    user_id: result.user_id, email: result.email,
    email_verified: result.email_verified, user_key: `u_${result.user_id}`,
  });
  return result;
}

export async function apiResendVerification(user_id: number): Promise<{ message: string }> {
  return requestJson<{ message: string }>('/api/auth/resend-verification', {
    method: 'POST', body: JSON.stringify({ user_id }),
  });
}

export async function apiLogin(payload: { email: string; password: string }): Promise<AuthSuccessResult> {
  const result = await requestJson<AuthSuccessResult>('/api/auth/login', {
    method: 'POST', body: JSON.stringify(payload),
  });
  setAuthState(result.token, {
    user_id: result.user_id, email: result.email,
    email_verified: result.email_verified, user_key: `u_${result.user_id}`,
  });
  return result;
}

export async function apiLogout(): Promise<void> {
  try {
    await requestJson<void>('/api/auth/logout', { method: 'POST' });
  } finally {
    clearAuthState();
  }
}

// ── Base request helper ───────────────────────────────────────────────────────

async function requestJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const userKey = getOrCreateUserKey();
  const token = getAuthToken();
  const extraHeaders: Record<string, string> = {};
  if (token) extraHeaders['Authorization'] = `Bearer ${token}`;
  if (!token && isGuestUser()) extraHeaders['X-Guest'] = '1';

  const response = await fetch(input, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      'X-Resume-User-Key': userKey,
      ...extraHeaders,
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

export async function downloadResumePdf(sessionId: number): Promise<void> {
  const userKey = getOrCreateUserKey();
  const headers: Record<string, string> = { 'X-Resume-User-Key': userKey };
  if (isGuestUser()) headers['X-Guest'] = '1';
  const response = await fetch(`/api/resume-copilot/sessions/${sessionId}/export.pdf`, { headers });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `导出失败 (${response.status})`);
  }
  const blob = await response.blob();
  const disposition = response.headers.get('content-disposition') || '';
  let filename = `resume-${sessionId}.pdf`;
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  const plainMatch = disposition.match(/filename=("?)([^";]+)\1/i);
  if (utf8Match) {
    try {
      filename = decodeURIComponent(utf8Match[1]);
    } catch {
      // fall through to plain or default
    }
  } else if (plainMatch) {
    filename = plainMatch[2];
  }
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
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

// ── Rewrite v0/v2 (C-1 thesis-aware, P1 BE-2) ────────────────────────────────
// v0 = 学生原文 (echo); v2 = thesis-aware 改写.
// FE-3 hooks this on bullet hover ✏️ → inline diff in RightResumePane.
// Apply 链路暂未接 (see RightResumePane README) — 本助手只拉 v0/v2 + warnings,
// 学生用 "复制到剪贴板" 自行粘贴回简历;完整 apply P1 末尾再接.

export interface RewriteWarningSuggestionDto {
  action: 'fill_real' | 'delete_number' | 'vague' | string;
  label: string;
}

export interface RewriteWarningDto {
  type: 'fabricated_number' | string;
  number: string;
  suggestion_options: RewriteWarningSuggestionDto[];
  detail: string;
}

export interface RewriteVersionV0Dto {
  text: string;
}

export interface RewriteVersionV2Dto {
  text: string;
  needs_plan_mode: boolean;
  warnings: RewriteWarningDto[];
}

export interface RewriteV0V2Out {
  field_path: string;
  section: string;
  target_title: string;
  v0: RewriteVersionV0Dto;
  v2: RewriteVersionV2Dto;
  rationale: string;
  memory_refs: number[];
}

export interface RewriteV0V2In {
  bullet_text: string;
  field_path: string;
  target_job_description?: string;
  target_title?: string;
  section?: string;
}

export function postRewriteV0V2(sessionId: number, payload: RewriteV0V2In) {
  return requestJson<RewriteV0V2Out>(
    `/api/resume-copilot/sessions/${sessionId}/rewrite/v0v2`,
    {
      method: 'POST',
      body: JSON.stringify({
        bullet_text: payload.bullet_text,
        field_path: payload.field_path,
        target_job_description: payload.target_job_description ?? '',
        target_title: payload.target_title ?? '',
        section: payload.section ?? '',
      }),
    }
  );
}

// ── Student KB (personal knowledge base, cross-session) ──────────────────────

export interface StudentExperienceIndexItem {
  id: number;
  summary: string;
  category: string;
  star_dimensions: string[];
  confidence: number;
  user_confirmed: boolean;
  captured_at: string;
  age_days: number;
}

export interface StudentExperienceDetail extends StudentExperienceIndexItem {
  name: string;
  behavioral_hook: string;
  quantified: Record<string, unknown>;
  raw_excerpt: string;
  has_temporal_anchor: boolean;
  has_concrete_action: boolean;
  has_outcome: boolean;
  last_verified_at: string | null;
  last_used_at: string | null;
  use_count: number;
  is_archived: boolean;
  source_session_id: number | null;
}

export interface StudentKbIndexResponse {
  user_key: string;
  total: number;
  pending_confirm_count: number;
  items: StudentExperienceIndexItem[];
}

export interface StudentKbListResponse {
  total: number;
  items: StudentExperienceDetail[];
}

export function getStudentKbIndex(includeArchived = false) {
  const qs = includeArchived ? '?include_archived=true' : '';
  return requestJson<StudentKbIndexResponse>(`/api/student-kb/index${qs}`);
}

export function listStudentExperiences(opts: {
  category?: string;
  dimension?: string;
  confirmedOnly?: boolean;
  includeArchived?: boolean;
  limit?: number;
} = {}) {
  const params = new URLSearchParams();
  if (opts.category) params.set('category', opts.category);
  if (opts.dimension) params.set('dimension', opts.dimension);
  if (opts.confirmedOnly) params.set('confirmed_only', 'true');
  if (opts.includeArchived) params.set('include_archived', 'true');
  if (opts.limit) params.set('limit', String(opts.limit));
  const qs = params.toString();
  return requestJson<StudentKbListResponse>(
    `/api/student-kb/experiences${qs ? '?' + qs : ''}`
  );
}

export function confirmStudentExperience(expId: number) {
  return requestJson<StudentExperienceDetail>(
    `/api/student-kb/experiences/${expId}/confirm`,
    { method: 'POST' }
  );
}

export function archiveStudentExperience(expId: number) {
  return requestJson<StudentExperienceDetail>(
    `/api/student-kb/experiences/${expId}/archive`,
    { method: 'POST' }
  );
}

export function deleteStudentExperience(expId: number) {
  return requestJson<void>(
    `/api/student-kb/experiences/${expId}`,
    { method: 'DELETE' }
  );
}
