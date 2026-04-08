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

const PREVIEW_USERNAME = 'preview';
const PREVIEW_PASSWORD = 'preview';

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

  if (input.username !== PREVIEW_USERNAME || input.password !== PREVIEW_PASSWORD) {
    throw new Error('INVALID_CREDENTIALS');
  }

  writeMockSession({
    username: input.username,
    rememberMe: input.rememberMe,
    autoLogin: input.autoLogin,
  });
}
