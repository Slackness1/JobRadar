'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Lingmou digital-human avatar. Fetches a session from our backend,
 * initializes the `lm-avatar-chat-sdk`, and renders the avatar video.
 *
 * The SDK is loaded dynamically to avoid SSR issues.
 */

interface AvatarState {
  status: 'loading' | 'ready' | 'error' | 'idle';
  error: string;
}

export function AvatarView() {
  const [state, setState] = useState<AvatarState>({ status: 'idle', error: '' });
  const [hidden, setHidden] = useState(false);
  const avatarRef = useRef<unknown>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const initRef = useRef(false);

  const initAvatar = useCallback(async () => {
    if (initRef.current) return;
    initRef.current = true;
    setState({ status: 'loading', error: '' });

    try {
      // 1. Fetch session params from our backend
      const res = await fetch('/api/interview/avatar/session', { method: 'POST' });
      if (!res.ok) {
        const detail = await res.text().catch(() => '');
        throw new Error(`创建数字人会话失败: ${res.status} ${detail}`);
      }
      const rtcParams = await res.json();

      // 2. Dynamically import the SDK (avoid SSR)
      const { createAvatar, TYAvatarType } = await import('lm-avatar-chat-sdk');

      // 3. Create avatar instance
      const avatar = createAvatar(TYAvatarType.cloudAvatar, {
        rootContainer: '#avatarContainer',
        ...rtcParams,
      });
      avatarRef.current = avatar;

      // 4. Set up callbacks
      avatar.onFirstFrameReceived = () => {
        setState({ status: 'ready', error: '' });
      };
      avatar.onErrorReceived = (err: unknown) => {
        const msg = typeof err === 'string' ? err : (err as { message?: string })?.message || 'Avatar error';
        setState({ status: 'error', error: msg });
      };
      avatar.onReadyToSpeech = () => {
        // Avatar is ready for interaction
      };

      // 5. Start the avatar session
      avatar.start();
    } catch (err) {
      const msg = err instanceof Error ? err.message : '数字人初始化失败';
      setState({ status: 'error', error: msg });
      initRef.current = false;
    }
  }, []);

  useEffect(() => {
    initAvatar();
    return () => {
      if (avatarRef.current) {
        try {
          (avatarRef.current as { exit?: () => void }).exit?.();
        } catch { /* ignore */ }
        avatarRef.current = null;
        initRef.current = false;
      }
    };
  }, [initAvatar]);

  if (hidden) return null;

  return (
    <div className="fixed right-4 top-20 z-40 flex flex-col items-end gap-1">
      <div className="relative overflow-hidden rounded-[14px] border border-[var(--border)] bg-black shadow-lg">
        <video
          id="avatarContainer"
          ref={videoRef}
          playsInline
          muted
          className={`h-[216px] w-[162px] object-cover transition-opacity ${
            state.status === 'ready' ? 'opacity-100' : 'opacity-30'
          }`}
        />

        {state.status === 'loading' && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/60">
            <span className="text-[12px] text-white/70">数字人加载中…</span>
          </div>
        )}

        {state.status === 'error' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/80 px-2">
            <span className="text-center text-[11px] text-red-400">{state.error}</span>
            <button
              onClick={() => { initRef.current = false; initAvatar(); }}
              className="rounded-[6px] bg-white/20 px-2 py-0.5 text-[11px] text-white hover:bg-white/30"
            >
              重试
            </button>
          </div>
        )}

        <button
          onClick={() => {
            if (avatarRef.current) {
              try { (avatarRef.current as { exit?: () => void }).exit?.(); } catch { /* ignore */ }
            }
            setHidden(true);
          }}
          className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-black/60 text-white text-[10px] hover:bg-black/80"
          title="关闭数字人"
        >
          ×
        </button>
      </div>
    </div>
  );
}
