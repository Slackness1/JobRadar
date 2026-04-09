import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { clearMockSession, readMockSession, STORAGE_KEY, submitPreviewLogin } from './mockSession';

describe('mockSession', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('persists remembered preview sessions in localStorage', async () => {
    const submitPromise = submitPreviewLogin({
      username: 'slackness',
      password: 'Zcbpp991060.',
      rememberMe: true,
      autoLogin: false,
    });

    await vi.advanceTimersByTimeAsync(400);
    await submitPromise;

    expect(window.localStorage.getItem(STORAGE_KEY)).not.toBeNull();
    expect(window.sessionStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(readMockSession()).toEqual({
      username: 'slackness',
      rememberMe: true,
      autoLogin: false,
    });
  });

  it('persists non-remembered preview sessions in sessionStorage', async () => {
    const submitPromise = submitPreviewLogin({
      username: 'guest',
      password: '123456',
      rememberMe: false,
      autoLogin: true,
    });

    await vi.advanceTimersByTimeAsync(400);
    await submitPromise;

    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(window.sessionStorage.getItem(STORAGE_KEY)).not.toBeNull();
    expect(readMockSession()).toEqual({
      username: 'guest',
      rememberMe: false,
      autoLogin: true,
    });
  });

  it('accepts the guest account credentials', async () => {
    const submitPromise = submitPreviewLogin({
      username: 'guest',
      password: '123456',
      rememberMe: true,
      autoLogin: false,
    });

    await vi.advanceTimersByTimeAsync(400);
    await submitPromise;

    expect(readMockSession()).toEqual({
      username: 'guest',
      rememberMe: true,
      autoLogin: false,
    });
  });

  it('rejects invalid preview credentials without persisting a session', async () => {
    const submitPromise = submitPreviewLogin({
      username: 'slackness',
      password: 'wrong-password',
      rememberMe: true,
      autoLogin: false,
    });
    const rejection = expect(submitPromise).rejects.toThrow('INVALID_CREDENTIALS');

    await vi.advanceTimersByTimeAsync(400);

    await rejection;
    expect(readMockSession()).toBeNull();
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(window.sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('clears preview sessions from both browser storage scopes', async () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ username: 'saved', rememberMe: true, autoLogin: false }));
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ username: 'temp', rememberMe: false, autoLogin: false }));

    clearMockSession();

    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(window.sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it('clears malformed stored session payloads and returns null', () => {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify({}));

    expect(readMockSession()).toBeNull();
    expect(window.sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });
});
