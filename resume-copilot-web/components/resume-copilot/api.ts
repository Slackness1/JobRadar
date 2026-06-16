import type {
  ApplyRewriteOut,
  CopilotMessage,
  DirectionTierResult,
  JobState,
  MyJobsResult,
  RecommendFeedItem,
  RecommendTurnResponse,
  ResumeConfirmedProfileOut,
  ResumeCopilotSession,
  ResumeCopilotSessionCreatedOut,
  ResumeCopilotSessionListItem,
  ResumeFeedbackResult,
  ResumeJobMode,
  ResumeParsedProfileOut,
  ResumePreferenceOut,
  ResumePreferencePayload,
  ResumeProfilePayload,
  ResumeRecommendationPlatformsOut,
  ResumeRecommendationResult,
  SubCatSuggestionsResponse,
  WorkingQuery,
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

// ── 双语翻译 (B5) ────────────────────────────────────────────────────────────

export interface TranslateWarning { path: string; extra: string; }
export interface TranslateProfileOut { profile: unknown; warnings: TranslateWarning[]; }

export function translateProfile(profile: unknown): Promise<TranslateProfileOut> {
  return requestJson<TranslateProfileOut>('/api/resume-copilot/translate-profile', {
    method: 'POST',
    body: JSON.stringify({ profile, target: 'en' }),
  });
}

// ── 简历多维度打分 (B1) ─────────────────────────────────────────────────────
export interface ScoreDimension {
  key: string;
  name: string;
  score: number;
  ceiling: number;
  reason: string;
}
export interface ScoreSectionGap {
  section: string;
  label: string;
  gaps: string[];
  detail: string;
}
export interface ScoreReportData {
  session_id: number;
  target_track: string;
  overall_current: number;
  overall_potential_low: number;
  overall_potential_high: number;
  summary: string;
  dimensions: ScoreDimension[];
  section_gaps: ScoreSectionGap[];
  used_ai: boolean;
}

export function scoreResume(sessionId: number, targetTrack = ''): Promise<ScoreReportData> {
  return requestJson<ScoreReportData>(`/api/resume-copilot/sessions/${sessionId}/score`, {
    method: 'POST',
    body: JSON.stringify({ target_track: targetTrack }),
  });
}

// ── 打分任务制(start 立即返回 + status 轮询真实阶段)────────────────────────
// 打分在服务端线程跑: 切对话/跳页不中断(后台续跑), 浏览器不再被 90s 长请求
// 占连接池。done 时 status 带完整报告(服务端缓存) — 对话卡/报告面板共用一份。
export interface ScoreTaskStatus {
  session_id: number;
  status: 'none' | 'running' | 'done' | 'failed';
  stage: string; // prepare | llm | parse | done
  elapsed_seconds: number | null;
  report: ScoreReportData | null;
  error: string;
}

export function startScoreTask(
  sessionId: number,
  opts: { targetTrack?: string; force?: boolean; profile?: unknown } = {},
): Promise<Omit<ScoreTaskStatus, 'report'>> {
  // profile 覆盖 = 给「指定版本」的快照打分(不复用服务端缓存)。
  // 传 profile 时强制 force:true,避免命中旧版本的缓存报告。
  const body: Record<string, unknown> = {
    target_track: opts.targetTrack ?? '',
    force: opts.profile != null ? true : opts.force ?? false,
  };
  if (opts.profile != null) body.profile = opts.profile;
  return requestJson<Omit<ScoreTaskStatus, 'report'>>(
    `/api/resume-copilot/sessions/${sessionId}/score/start`,
    {
      method: 'POST',
      body: JSON.stringify(body),
    },
  );
}

export function getScoreTaskStatus(sessionId: number): Promise<ScoreTaskStatus> {
  return requestJson<ScoreTaskStatus>(`/api/resume-copilot/sessions/${sessionId}/score/status`);
}

// ── 简历编辑器草稿(跨设备持久化)─────────────────────────────────────────────
// 渲染模型 + 模板/布局/隐藏项落库, 换设备/浏览器也能恢复上次编辑。
export interface EditorDraftPayload {
  profile: unknown;
  template: string;
  layout: unknown;
  hidden: string[];
}

export function getEditorDraft(sessionId: number): Promise<{ draft: EditorDraftPayload | null }> {
  return requestJson<{ draft: EditorDraftPayload | null }>(
    `/api/resume-copilot/sessions/${sessionId}/editor-draft`,
  );
}

export function putEditorDraft(
  sessionId: number,
  draft: EditorDraftPayload,
): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/resume-copilot/sessions/${sessionId}/editor-draft`, {
    method: 'PUT',
    body: JSON.stringify({ draft }),
  });
}

// ── Hub 多对话持久化(简历是 base, 一份简历下多个对话)─────────────────────────
// messages = 有序消息数组(turn/result/trace/memory/intel; 不含 skillrun 思考表演)。
// 进会话 list 取最新对话水合; 「新对话」= create 插新行(旧对话原样保留);
// 每轮对话变动即时 PUT 落到自己的对话行, 不再共用单槽互相覆盖。
export interface HubConversationListItem {
  id: number;
  title: string;
  updated_at: string | null;
  message_count: number;
}

export function listHubConversations(
  sessionId: number,
): Promise<{ conversations: HubConversationListItem[] }> {
  return requestJson<{ conversations: HubConversationListItem[] }>(
    `/api/resume-copilot/sessions/${sessionId}/hub-conversations`,
  );
}

export function createHubConversation(
  sessionId: number,
  title: string,
  messages: unknown[],
): Promise<{ id: number; title: string }> {
  return requestJson<{ id: number; title: string }>(
    `/api/resume-copilot/sessions/${sessionId}/hub-conversations`,
    { method: 'POST', body: JSON.stringify({ title, messages }) },
  );
}

export function getHubConversationDetail(
  sessionId: number,
  convId: number,
): Promise<{ id: number; title: string; messages: unknown[] }> {
  return requestJson<{ id: number; title: string; messages: unknown[] }>(
    `/api/resume-copilot/sessions/${sessionId}/hub-conversations/${convId}`,
  );
}

export function putHubConversationDetail(
  sessionId: number,
  convId: number,
  messages: unknown[],
): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(
    `/api/resume-copilot/sessions/${sessionId}/hub-conversations/${convId}`,
    { method: 'PUT', body: JSON.stringify({ messages }) },
  );
}

// ── 简历版本(显式保存的快照 + 对应打分报告)+ 编辑器对话(深度优化多 tab)──────
// 两者都是整组替换式持久化:GET 取整组水合, PUT 整组覆盖。
// demo / 只读 session 的 PUT 返 403 —— 调用方 catch 后内存态继续, 不崩。
export function getResumeVersions(sessionId: number): Promise<{ versions: unknown[] }> {
  return requestJson<{ versions: unknown[] }>(
    `/api/resume-copilot/sessions/${sessionId}/resume-versions`,
  );
}

export function putResumeVersions(
  sessionId: number,
  versions: unknown[],
): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(
    `/api/resume-copilot/sessions/${sessionId}/resume-versions`,
    { method: 'PUT', body: JSON.stringify({ versions }) },
  );
}

export function getEditorConversations(
  sessionId: number,
): Promise<{ conversations: unknown[] }> {
  return requestJson<{ conversations: unknown[] }>(
    `/api/resume-copilot/sessions/${sessionId}/editor-conversations`,
  );
}

export function putEditorConversations(
  sessionId: number,
  conversations: unknown[],
): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(
    `/api/resume-copilot/sessions/${sessionId}/editor-conversations`,
    { method: 'PUT', body: JSON.stringify({ conversations }) },
  );
}

// ── 深度优化(反问取证)— 复用现有 plan 管道 ────────────────────────────
export interface DeepOptimizeStartIn {
  section: string;
  label: string;
  gaps: string[];
  detail: string;
  target_track: string;
}

/**
 * 「待引用」片段(低调引子)。引用此段 / 选行引用都先挂成它,
 * 不自动发问;用户在深度优化输入框打字发送时才据此启动 deepOptimizeStart。
 */
export interface PendingQuote {
  /** 被引用的原文文字(可多行)。 */
  text: string;
  /** 后端 section path(如 'internships.0')。 */
  section: string;
  /** 人类可读段标签(如「九坤投资 · 量化研究实习」)。 */
  label: string;
  /** 目标赛道(可空,启动时回落到默认)。 */
  target_track: string;
}

// 注:PlanStateOut / PlanItemWire / PlanOpenQuestionWire 已在本文件下方(约 804–841)
// 定义为 canonical wire 类型,这里直接复用,不重复声明。

/** 从打分逐段缺口播种深度优化 → 单段 CLARIFYING plan(首问已对齐目标赛道)。 */
export function deepOptimizeStart(sessionId: number, body: DeepOptimizeStartIn): Promise<PlanStateOut> {
  return requestJson<PlanStateOut>(`/api/resume-copilot/sessions/${sessionId}/deep-optimize/start`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/** 续走一回合反问(plan-mode one-tool-per-turn);content = 学生这轮回答。 */
export function planTurn(sessionId: number, content: string, activeJobId = ''): Promise<PlanStateOut> {
  return requestJson<PlanStateOut>(`/api/resume-copilot/sessions/${sessionId}/plan/turn`, {
    method: 'POST',
    body: JSON.stringify({ content, active_job_id: activeJobId }),
  });
}

/** 深度优化写回:把当前 finalized draft 写进 profile 对应段落 → 返回更新后 profile + 段落(供高亮)。 */
export interface DeepOptimizeWriteBackResult {
  profile: Record<string, unknown>;
  section: string;
  applied: boolean;
}
export function deepOptimizeWriteBack(sessionId: number): Promise<DeepOptimizeWriteBackResult> {
  return requestJson<DeepOptimizeWriteBackResult>(`/api/resume-copilot/sessions/${sessionId}/deep-optimize/write-back`, {
    method: 'POST',
    body: JSON.stringify({}),
  });
}

/** 应用某条 v0/v2 改写选项(按 message_id + option_id)→ 返回写回后的完整 profile。 */
export interface ApplyRewriteResult {
  profile: Record<string, unknown>;
  applied: boolean;
}
export function applyRewrite(sessionId: number, messageId: number, optionId: string): Promise<ApplyRewriteResult> {
  return requestJson<ApplyRewriteResult>(`/api/resume-copilot/sessions/${sessionId}/chat/apply-rewrite`, {
    method: 'POST',
    body: JSON.stringify({ message_id: messageId, option_id: optionId }),
  });
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

/** 复制一份会话(克隆 简历/偏好/推荐快照)。后端 409 = 在用简历达上限。 */
export function duplicateResumeCopilotSession(sessionId: number) {
  return requestJson<ResumeCopilotSessionListItem>(
    `/api/resume-copilot/sessions/${sessionId}/duplicate`,
    { method: 'POST' },
  );
}

// ── Profile / preferences / generate ─────────────────────────────────────────

export function getResumeCopilotParsedProfile(sessionId: number) {
  return requestJson<ResumeParsedProfileOut>(`/api/resume-copilot/sessions/${sessionId}/parsed-profile`);
}

export function getResumeCopilotConfirmedProfile(sessionId: number) {
  return requestJson<ResumeConfirmedProfileOut>(`/api/resume-copilot/sessions/${sessionId}/confirmed-profile`);
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

/** #3 (2026-05-21): 拓展 PUT /preferences 返回值, 把后端 `X-Unknown-Tracks`
 *  header 一起带出, FE 可据此 toast 提示"你填的赛道 X 已自动映射为 Y"。
 *  老调用方期望 ResumePreferenceOut 形状 — 用 PromiseLike 加属性的方式扩展,
 *  既不破坏现有 destructure, 又能让新调用拿到 unknownTracks 数组。
 */
export interface ResumePreferenceOutWithMeta extends ResumePreferenceOut {
  unknownTracks?: string[];
}

export async function putResumeCopilotPreferences(
  sessionId: number,
  preferences: ResumePreferencePayload,
): Promise<ResumePreferenceOutWithMeta> {
  const userKey = getOrCreateUserKey();
  const token = getAuthToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Resume-User-Key': userKey,
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!token && isGuestUser()) headers['X-Guest'] = '1';

  const response = await fetch(`/api/resume-copilot/sessions/${sessionId}/preferences`, {
    method: 'PUT',
    headers,
    body: JSON.stringify({ preferences }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  const body = (await response.json()) as ResumePreferenceOut;
  // 后端把未识别的赛道 URL-encode 后塞 X-Unknown-Tracks header (latin-1 限制)
  const raw = response.headers.get('x-unknown-tracks') || '';
  const unknownTracks = raw
    ? raw.split(',').map((s) => {
        try { return decodeURIComponent(s); } catch { return s; }
      }).filter(Boolean)
    : undefined;
  return { ...body, unknownTracks };
}

export function postResumeCopilotGenerate(sessionId: number) {
  return requestJson<ResumeCopilotSessionCreatedOut>(`/api/resume-copilot/sessions/${sessionId}/generate`, {
    method: 'POST',
  });
}

export function getResumeCopilotRecommendations(sessionId: number) {
  return requestJson<ResumeRecommendationResult>(`/api/resume-copilot/sessions/${sessionId}/recommendations`);
}

export function getResumeCopilotPlatforms(sessionId: number) {
  return requestJson<ResumeRecommendationPlatformsOut>(
    `/api/resume-copilot/sessions/${sessionId}/recommendations/platforms`,
  );
}

// Phase G G2-D — 求职模式判定 (实习/全职/both) + 默认 tab + 解释 banner
export function getResumeCopilotJobMode(sessionId: number) {
  return requestJson<ResumeJobMode>(
    `/api/resume-copilot/sessions/${sessionId}/job-mode`,
  );
}

// Phase G Task 6 — 细分方向 LLM 预勾建议 (确认页两级勾选)
export function getSubCatSuggestions(
  sessionId: number,
  tracks: string[],
): Promise<SubCatSuggestionsResponse> {
  return requestJson<SubCatSuggestionsResponse>(
    `/api/resume-copilot/sessions/${sessionId}/sub-cat-suggestions`,
    {
      method: 'POST',
      body: JSON.stringify({ tracks }),
    },
  );
}

// Phase 7 — LLM 个性化推荐叙事 (2026-05-25)
// Phase 8 — 加 narrative_short 给平台 tab mini job 行用 (同一 LLM call 一并生成)
export interface RecommendNarrativeOut {
  narrative: string;
  narrative_short: string;
  action_tip: string;
  evidence_refs: string[];
  generated_at: string;
  from_cache: boolean;
  status: string;
}

export function getResumeCopilotNarrative(sessionId: number, jobId: string) {
  return requestJson<RecommendNarrativeOut>(
    `/api/resume-copilot/sessions/${sessionId}/recommendations/${encodeURIComponent(jobId)}/narrative`,
  );
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

export function postChatMessage(
  sessionId: number,
  content: string,
  opts?: { activeJobId?: string },
) {
  const body: { content: string; active_job_id?: string } = { content };
  if (opts?.activeJobId) body.active_job_id = opts.activeJobId;
  return requestJson<CopilotMessage>(`/api/resume-copilot/sessions/${sessionId}/chat`, {
    method: 'POST',
    body: JSON.stringify(body),
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
  /** Non-blocking nudge when memory is empty (Fix #2). Empty string when
   *  memory had hits; UI renders as a soft banner under v2 text. */
  soft_hint?: string;
  /** 2026-05-22 #114 Phase 1: 港新学生 (inferred_offices ⊇ {hk,sg}) 的英文 bullet。
   *  其它学生为空字符串,UI 不渲染英文块。 */
  en_text?: string;
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

// ── Recommendation reject (BE-3, D-2 / D-3) ──────────────────────────────────

/** Canonical reason keys accepted by BE-3 reject endpoint. */
export type RecommendRejectReason =
  | 'wrong_track'
  | 'company_disliked'
  | 'school_mismatch'
  | 'timing'
  | 'other';

export interface RecommendRejectIn {
  reason: RecommendRejectReason;
  note?: string;
}

export interface RecommendRejectOut {
  ok: boolean;
  memory_entry_id: number | null;
  rejected_count: number;
}

/** D-2/D-3: 学生 ✗ 拒绝一个推荐岗。BE 会写一条 account_memory.preference
 *  + 把 job_id 追加到 session.rejected_job_ids_json,下次 recommend 会过滤掉。 */
export function postRejectRecommendation(
  sessionId: number,
  jobId: string,
  payload: RecommendRejectIn,
) {
  return requestJson<RecommendRejectOut>(
    `/api/resume-copilot/sessions/${sessionId}/recommendations/${encodeURIComponent(jobId)}/reject`,
    {
      method: 'POST',
      body: JSON.stringify({
        reason: payload.reason,
        note: payload.note ?? '',
      }),
    },
  );
}

// ── Account memory (Phase 0 P0-2 + BE-1; FE-4 consumer) ─────────────────────
//
// 8 canonical categories: experience / skill_claim / preference / identity_fact
// / evidence / goal / commitment / weakness_signal.
// (A-4 简: 当前 chat extractor 只写 experience / skill_claim / preference,
//  其余 5 类暂留以兼容旧 writers。)

export const MEMORY_CATEGORIES = [
  'experience',
  'skill_claim',
  'preference',
  'identity_fact',
  'evidence',
  'goal',
  'commitment',
  'weakness_signal',
] as const;

export type MemoryCategory = (typeof MEMORY_CATEGORIES)[number];

export interface MemoryEntry {
  id: number;
  category: MemoryCategory | string;
  summary: string;
  payload: Record<string, unknown>;
  confidence: number;
  user_confirmed: boolean;
  use_count: number;
  is_archived: boolean;
  superseded_by_id: number | null;
  source_module: string;
  source_session_id: number | null;
  raw_excerpt: string;
  captured_at: string | null;
  last_verified_at: string | null;
  last_used_at: string | null;
  /** Plan 1 (2026-05-20): which resume bullets this memory came from. */
  linked_field_paths?: string[];
  /** Set to true when student edited a linked bullet — UI shows 🔄 badge. */
  needs_resync?: boolean;
  /** Plan ② (2026-05-20): canonical 赛道 name when captured (e.g.
   *  '二级买方·基本面'). Empty = general / cross-track. UI shows a tag. */
  linked_track?: string;
}

export interface MemoryGroupedResponse {
  session_id: number;
  user_key: string;
  entries: Record<string, MemoryEntry[]>;
}

export function getSessionMemory(sessionId: number) {
  return requestJson<MemoryGroupedResponse>(
    `/api/resume-copilot/sessions/${sessionId}/memory`,
  );
}

export interface MemoryCreateIn {
  category: MemoryCategory | string;
  summary: string;
  payload?: Record<string, unknown>;
  raw_excerpt?: string;
  confidence?: number;
}

export function postSessionMemory(sessionId: number, payload: MemoryCreateIn) {
  return requestJson<MemoryEntry>(
    `/api/resume-copilot/sessions/${sessionId}/memory`,
    {
      method: 'POST',
      body: JSON.stringify({
        category: payload.category,
        summary: payload.summary,
        payload: payload.payload ?? {},
        raw_excerpt: payload.raw_excerpt ?? '',
        confidence: payload.confidence ?? 1.0,
      }),
    },
  );
}

export interface MemoryPatchIn {
  summary?: string;
  payload?: Record<string, unknown>;
}

export function patchSessionMemoryEntry(
  sessionId: number,
  entryId: number,
  body: MemoryPatchIn,
) {
  const payload: Record<string, unknown> = {};
  if (body.summary !== undefined) payload.summary = body.summary;
  if (body.payload !== undefined) payload.payload = body.payload;
  return requestJson<MemoryEntry>(
    `/api/resume-copilot/sessions/${sessionId}/memory/${entryId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(payload),
    },
  );
}

export function deleteSessionMemoryEntry(sessionId: number, entryId: number) {
  return requestJson<void>(
    `/api/resume-copilot/sessions/${sessionId}/memory/${entryId}`,
    { method: 'DELETE' },
  );
}

// ── Plan-mode (B-1 / B-2 简 / B-3 / B-4) ────────────────────────────────────
//
// Backend lives in app/routers/resume_copilot.py around /plan/* — the schema
// is the rich PlanState (items[], evidence, drafts, …).  FE-4 only needs:
//   1. start  → POST /plan/start (body is empty in current BE; the prompt
//      contract carries focus_kind/focus_id which BE silently ignores today —
//      see report §9. We still send it so the wire matches the design doc.)
//   2. turn   → POST /plan/turn   (composer message → AI follow-up + state)
//   3. finalize → POST /plan/actions {action:"finalize", item_id, expected_version}
//      (BE has no /plan/finalize endpoint; the "finalize" semantic lives in
//      apply_action.)
//   4. get    → GET /plan          (rehydrate after refresh)

export interface PlanEvidenceTagWire {
  type: string;
  value: string;
  raw: string;
}

export interface PlanEvidenceWire {
  id: string;
  source: string;
  text: string;
  tags: PlanEvidenceTagWire[];
  citation_msg_id: string | null;
  extracted_at: string;
}

export interface PlanOpenQuestionWire {
  id: string;
  text: string;
  asked_at: string;
  answered_at: string | null;
  answer_msg_id: string | null;
}

export interface PlanDraftWire {
  text: string;
  used_evidence_ids: string[];
  risk_flags: Array<{ kind: string; detail: string; blocking: boolean }>;
  generated_at: string;
}

export interface PlanItemWire {
  id: string;
  kind: string;
  title: string;
  parent_id: string | null;
  order: number;
  status: string;
  evidence: PlanEvidenceWire[];
  draft: PlanDraftWire | null;
  open_questions: PlanOpenQuestionWire[];
  rationale: string | null;
  last_transition_at: string;
}

export interface PlanStateOut {
  version: number;
  status: string;
  current_item_id: string | null;
  items: PlanItemWire[];
  replan_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface PlanStartIn {
  /** Designed contract per main-workspace-redesign-2026-05-20 §2 B-2 简.
   *  BE silently ignores until P1.x — included so the wire matches and we
   *  can flip BE later without touching FE. */
  focus_kind?: 'experience' | string;
  focus_id?: number;
}

export function postPlanStart(sessionId: number, payload?: PlanStartIn) {
  return requestJson<PlanStateOut>(
    `/api/resume-copilot/sessions/${sessionId}/plan/start`,
    {
      method: 'POST',
      body: JSON.stringify(payload ?? {}),
    },
  );
}

export function getPlan(sessionId: number) {
  return requestJson<PlanStateOut>(
    `/api/resume-copilot/sessions/${sessionId}/plan`,
  );
}

/** H 2026-05-22: 入档前 LLM 精炼。 学生反馈 "入档时有很多重复的原话",
 *  这个 endpoint 把 draft + raw evidence 喂 LLM, 返回干净的 summary + STAR +
 *  去重 quantified + 精简 raw_excerpt_clean, FE 拿这个再 POST /memory 入档。
 */
export interface PlanDistillOut {
  summary: string;
  star: { situation: string; task: string; action: string; result: string };
  quantified: Record<string, string>;
  raw_excerpt_clean: string;
  used_evidence_ids: string[];
}

export function postPlanDistill(sessionId: number, itemId?: string): Promise<PlanDistillOut> {
  const qs = itemId ? `?item_id=${encodeURIComponent(itemId)}` : '';
  return requestJson<PlanDistillOut>(
    `/api/resume-copilot/sessions/${sessionId}/plan/distill${qs}`,
    { method: 'POST' },
  );
}

/** Wipe the existing plan_json so /plan/start can run fresh.
 *  Added 2026-05-21 to unstick sessions with stale clarifying plans
 *  whose current_item_id is null (the "click coach → 5 min nothing" bug). */
export function deletePlan(sessionId: number): Promise<void> {
  return requestJson<void>(
    `/api/resume-copilot/sessions/${sessionId}/plan`,
    { method: 'DELETE' },
  );
}

export function postPlanApprove(sessionId: number) {
  return requestJson<PlanStateOut>(
    `/api/resume-copilot/sessions/${sessionId}/plan/approve`,
    { method: 'POST' },
  );
}

export interface PlanTurnIn {
  user_message: string;
  target_item_id?: string | null;
}

export function postPlanTurn(sessionId: number, body: PlanTurnIn) {
  const qs =
    body.target_item_id != null
      ? `?target_item_id=${encodeURIComponent(body.target_item_id)}`
      : '';
  return requestJson<PlanStateOut>(
    `/api/resume-copilot/sessions/${sessionId}/plan/turn${qs}`,
    {
      method: 'POST',
      body: JSON.stringify({ content: body.user_message }),
    },
  );
}

export interface PlanActionIn {
  action: 'finalize' | 'ready_to_write' | 'drop' | 'block' | string;
  item_id: string;
  payload?: Record<string, unknown>;
  expected_version?: number;
}

export function postPlanAction(sessionId: number, body: PlanActionIn) {
  return requestJson<PlanStateOut>(
    `/api/resume-copilot/sessions/${sessionId}/plan/actions`,
    {
      method: 'POST',
      body: JSON.stringify({
        action: body.action,
        item_id: body.item_id,
        payload: body.payload ?? {},
        expected_version: body.expected_version ?? null,
      }),
    },
  );
}

/** Convenience wrapper requested by the FE-4 task spec.  Maps to BE's
 *  apply_action("finalize") on the currently-active item. */
export function postPlanFinalize(
  sessionId: number,
  body: { item_id: string; expected_version?: number },
) {
  return postPlanAction(sessionId, {
    action: 'finalize',
    item_id: body.item_id,
    expected_version: body.expected_version,
  });
}

// ── Job intel card (GET /api/job-intel/card?job_id=<int>) ────────────────────

export interface JobIntelDim {
  /** threshold 维独有 */
  hard?: string[];
  soft?: string[];
  /** compensation / outlook 维有 */
  summary?: string | null;
  badge: 1 | 2 | 3;
  cross: 'verified' | 'single' | 'conflicting';
  n: number;
  quotes: { text: string; source: string; author: string }[];
}

export interface JobIntelCard {
  job_id: number;
  company: string;
  role_title: string;
  positioning: {
    sub_category: string | null;
    tier: string | null;
    tier_label: string;
    track_line: string;
    one_liner: string;
  };
  intel: Record<'threshold' | 'compensation' | 'outlook', JobIntelDim>;
  provenance: {
    label: string;
    n_insights: number;
    sources: string[];
  };
}

export async function getJobIntelCard(jobId: number): Promise<JobIntelCard> {
  return requestJson<JobIntelCard>(`/api/job-intel/card?job_id=${jobId}`);
}

// ── Tier-fit ladder (GET /api/resume-copilot/sessions/{id}/tier-fit) ─────────

export interface TierLadderBand {
  band: '头部' | '次头部' | '腰部';
  rank: number;
  native_labels: string[];
  companies: string[];
  n_jobs: number;
}

export interface TierFitReason {
  text: string;
  evidence: string;
  evidence_source: string;
}

export interface TierFitData {
  floor_band: string;
  match_band: string;
  stretch_band: string;
  single_band: boolean;
  reasons: TierFitReason[];
  upgrade_hint: string;
  data_confidence: 'strong' | 'thin';
}

export interface TierFit {
  session_id: number;
  sub_cat: string | null;
  ladder: TierLadderBand[];
  fit: TierFitData | null;
}

export function getTierFit(sessionId: number, subCat?: string): Promise<TierFit> {
  const q = subCat ? `?sub_cat=${encodeURIComponent(subCat)}` : '';
  return requestJson<TierFit>(
    `/api/resume-copilot/sessions/${sessionId}/tier-fit${q}`,
  );
}

// ── Platforms-by-tier skeleton (GET /api/resume-copilot/sessions/{id}/platforms-by-tier) ──

export interface PlatformSkeletonJob {
  id: number;
  title: string;
  detail_url?: string;
  location?: string;
  is_internship?: boolean;
}

export interface PlatformSkeletonIntel {
  threshold: { hard: string[]; soft: string[]; requirements: string[] };
  compensation: { summary: string | null };
  comp_empty: boolean;
  comp_empty_note: string;
  outlook: { summary: string | null };
}

export interface PlatformSkeletonCompany {
  name: string;
  band: string;
  has_live: boolean;
  n_live: number;
  n_insights: number;
  match: '强匹配' | '可迁移' | '有差距' | string;
  jobs: PlatformSkeletonJob[];
  /** 往年招聘窗口文字 (骨架公司) */
  hiring_window?: string | null;
  /** 三维情报 (缓存命中时有值；null 表示未预热，显占位) */
  intel?: PlatformSkeletonIntel | null;
}

export interface PlatformSkeletonTier {
  tier: number;
  band: string;
  role: 'match' | 'stretch' | 'floor';
  label: string;
  companies: PlatformSkeletonCompany[];
}

export interface PlatformSkeleton {
  sub_cat: string;
  has_skeleton: boolean;
  tiers: PlatformSkeletonTier[];
}

export function getPlatformsByTier(
  sessionId: number,
  subCat?: string,
  mode?: string,
): Promise<PlatformSkeleton> {
  const params = new URLSearchParams();
  if (subCat) params.set('sub_cat', subCat);
  if (mode) params.set('mode', mode);
  const q = params.toString() ? `?${params.toString()}` : '';
  return requestJson<PlatformSkeleton>(
    `/api/resume-copilot/sessions/${sessionId}/platforms-by-tier${q}`,
  );
}

export interface CompanyTrackJobsResult {
  company: string;
  sub_cat: string | null;
  n: number;
  jobs: PlatformSkeletonJob[];
}

export function getCompanyTrackJobs(
  sessionId: number,
  company: string,
  subCat?: string | null,
  mode?: string,
): Promise<CompanyTrackJobsResult> {
  const params = new URLSearchParams({ company });
  if (subCat) params.set('sub_cat', subCat);
  if (mode) params.set('mode', mode);
  return requestJson<CompanyTrackJobsResult>(
    `/api/resume-copilot/sessions/${sessionId}/company-track-jobs?${params.toString()}`,
    { method: 'GET' },
  );
}

// ── Recommend-chat / working-query / deepen (Phase G Task 8) ─────────────────

export async function postRecommendChat(
  sessionId: number,
  message: string,
): Promise<RecommendTurnResponse> {
  return requestJson<RecommendTurnResponse>(
    `/api/resume-copilot/sessions/${sessionId}/recommend-chat`,
    {
      method: 'POST',
      body: JSON.stringify({ message }),
    },
  );
}

export async function getWorkingQuery(
  sessionId: number,
): Promise<{ working_query: WorkingQuery | null }> {
  return requestJson<{ working_query: WorkingQuery | null }>(
    `/api/resume-copilot/sessions/${sessionId}/working-query`,
  );
}

export async function updateWorkingQuery(
  sessionId: number,
  op: {
    remove_sub_cat?: string;
    clear_only?: boolean;
    sort?: string;
    reseed?: boolean;
  },
): Promise<{ working_query: WorkingQuery; feed: RecommendFeedItem[] }> {
  return requestJson<{ working_query: WorkingQuery; feed: RecommendFeedItem[] }>(
    `/api/resume-copilot/sessions/${sessionId}/working-query/update`,
    {
      method: 'POST',
      body: JSON.stringify(op),
    },
  );
}

export async function postRecommendDeepen(
  sessionId: number,
  jobIds: string[],
): Promise<{ items: RecommendFeedItem[] }> {
  return requestJson<{ items: RecommendFeedItem[] }>(
    `/api/resume-copilot/sessions/${sessionId}/recommend-deepen`,
    {
      method: 'POST',
      body: JSON.stringify({ job_ids: jobIds }),
    },
  );
}

// ── 岗位推荐 2.0 — 求职状态 + 下一批推荐 + 我的岗位 (Task 10) ───────────────────

/** 标记一个推荐岗的求职状态。state='' 清除已有状态。 */
export function markJobState(
  sessionId: number,
  jobId: string,
  state: '' | JobState,
): Promise<{ ok: boolean; job_id: string; state: string }> {
  return requestJson<{ ok: boolean; job_id: string; state: string }>(
    `/api/resume-copilot/sessions/${sessionId}/jobs/${encodeURIComponent(jobId)}/state`,
    { method: 'POST', body: JSON.stringify({ state }) },
  );
}

/** 触发下一批推荐岗。返回与 GET /recommendations 相同结构。 */
export function nextRecommendBatch(sessionId: number): Promise<ResumeRecommendationResult> {
  return requestJson<ResumeRecommendationResult>(
    `/api/resume-copilot/sessions/${sessionId}/recommendations/next-batch`,
    { method: 'POST' },
  );
}

/** 获取学生已收藏/已投递/已屏蔽的岗位列表。 */
export function getMyJobs(): Promise<MyJobsResult> {
  return requestJson<MyJobsResult>('/api/resume-copilot/my-jobs', { method: 'GET' });
}
