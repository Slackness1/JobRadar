export interface MockSession {
  username: string;
  rememberMe: boolean;
  autoLogin: boolean;
}

export interface PreviewLoginInput {
  username: string;
  password: string;
  rememberMe: boolean;
  autoLogin: boolean;
}

export const STORAGE_KEY = 'jobradar_mock_session';

const PREVIEW_ACCOUNTS = new Map([
  ['slackness', 'Zcbpp991060.'],
  ['guest', '123456'],
]);

// Phase 3 admin gate. Only the owner ('slackness') can approve/reject teacher
// drafts. Guest accounts can view the dashboard but write actions return 401.
//
// Token must match backend env TEACHER_ENTRY_ADMIN_TOKEN. For prod we'll wire
// this through a real session/JWT — for the demo we ship the dev token in the
// frontend bundle since the gate is just to keep curious viewers from clicking.
const ADMIN_USERNAME = 'slackness';
const ADMIN_TOKEN_DEV = 'jobradar-admin-dev-token-change-me';

export function isAdminUser(): boolean {
  const session = readMockSession();
  return session?.username === ADMIN_USERNAME;
}

export function getAdminToken(): string | null {
  return isAdminUser() ? ADMIN_TOKEN_DEV : null;
}

function isMockSession(value: unknown): value is MockSession {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const candidate = value as Record<string, unknown>;

  return typeof candidate.username === 'string'
    && typeof candidate.rememberMe === 'boolean'
    && typeof candidate.autoLogin === 'boolean';
}

function parseStoredSession(storage: Storage): MockSession | null {
  const raw = storage.getItem(STORAGE_KEY);
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw) as unknown;

    if (!isMockSession(parsed)) {
      storage.removeItem(STORAGE_KEY);
      return null;
    }

    return parsed;
  } catch {
    storage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function readMockSession(): MockSession | null {
  return parseStoredSession(window.sessionStorage) ?? parseStoredSession(window.localStorage);
}

export function writeMockSession(session: MockSession) {
  const storage = session.rememberMe ? window.localStorage : window.sessionStorage;
  const otherStorage = session.rememberMe ? window.sessionStorage : window.localStorage;

  otherStorage.removeItem(STORAGE_KEY);
  storage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearMockSession() {
  window.localStorage.removeItem(STORAGE_KEY);
  window.sessionStorage.removeItem(STORAGE_KEY);
}

export async function submitPreviewLogin(input: PreviewLoginInput) {
  await new Promise((resolve) => window.setTimeout(resolve, 400));

  if (PREVIEW_ACCOUNTS.get(input.username) !== input.password) {
    throw new Error('INVALID_CREDENTIALS');
  }

  writeMockSession({
    username: input.username,
    rememberMe: input.rememberMe,
    autoLogin: input.autoLogin,
  });
}
