'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ConnectionState,
  Room,
  RoomEvent,
  Track,
  type Participant,
  type RemoteParticipant,
  type RemoteTrack,
  type RemoteTrackPublication,
  type TranscriptionSegment,
} from 'livekit-client';
import { createInterviewRealtimeSession } from '@/components/interview/api';
import { captureTrackAsWav, type PcmWavCapture } from './PcmWavCapture';

export type RealtimeAgentState =
  | 'initializing'
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'speaking';

export type RealtimeTransportStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'fallback';

export interface RealtimeTranscript {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  final: boolean;
}

interface UseLiveKitInterviewOptions {
  enabled: boolean;
  sessionId: string;
  targetJob: string;
  jdContent: string;
  turnMode?: 'manual' | 'automatic';
  onTranscript: (transcript: RealtimeTranscript) => void;
  onFallback: (message: string) => void;
  captureAudio?: boolean;
}

export interface RealtimeCommittedTurn {
  transcript: string;
  audioBlob: Blob | null;
}

function isAgent(participant: Participant | undefined): boolean {
  return Boolean(participant?.isAgent);
}

export function useLiveKitInterview({
  enabled,
  sessionId,
  targetJob,
  jdContent,
  turnMode = 'manual',
  onTranscript,
  onFallback,
  captureAudio = false,
}: UseLiveKitInterviewOptions) {
  const [status, setStatus] = useState<RealtimeTransportStatus>('idle');
  const [agentState, setAgentState] = useState<RealtimeAgentState>('initializing');
  const [isMicrophoneEnabled, setIsMicrophoneEnabled] = useState(false);
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [needsAudioStart, setNeedsAudioStart] = useState(false);
  const [effectiveTurnMode, setEffectiveTurnMode] = useState<'manual' | 'automatic'>(turnMode);
  const [interruptionMode, setInterruptionMode] = useState<'vad' | 'adaptive'>('vad');
  const roomRef = useRef<Room | null>(null);
  const intentionalDisconnectRef = useRef(false);
  const agentIdentityRef = useRef('');
  const audioElementsRef = useRef<Set<HTMLMediaElement>>(new Set());
  const transcriptCallbackRef = useRef(onTranscript);
  const fallbackCallbackRef = useRef(onFallback);
  const pcmCaptureRef = useRef<PcmWavCapture | null>(null);
  const captureAudioRef = useRef(captureAudio);

  useEffect(() => { transcriptCallbackRef.current = onTranscript; }, [onTranscript]);
  useEffect(() => { fallbackCallbackRef.current = onFallback; }, [onFallback]);
  useEffect(() => { captureAudioRef.current = captureAudio; }, [captureAudio]);

  const rememberAgent = useCallback((participant?: Participant) => {
    if (!isAgent(participant)) return;
    agentIdentityRef.current = participant?.identity ?? '';
    const state = participant?.attributes['lk.agent.state'];
    if (state && ['initializing', 'idle', 'listening', 'thinking', 'speaking'].includes(state)) {
      setAgentState(state as RealtimeAgentState);
    }
  }, []);

  const removeAttachedAudio = useCallback((track?: RemoteTrack) => {
    if (track) {
      for (const element of track.detach()) {
        element.remove();
        audioElementsRef.current.delete(element);
      }
      return;
    }
    for (const element of audioElementsRef.current) element.remove();
    audioElementsRef.current.clear();
  }, []);

  useEffect(() => {
    if (!enabled || !targetJob) return;
    let cancelled = false;
    intentionalDisconnectRef.current = false;
    const room = new Room({
      adaptiveStream: true,
      dynacast: true,
      disconnectOnPageLeave: true,
      stopLocalTrackOnUnpublish: true,
    });
    roomRef.current = room;
    setStatus('connecting');

    const onParticipantConnected = (participant: RemoteParticipant) => rememberAgent(participant);
    const onAttributesChanged = (_changed: Record<string, string>, participant: Participant) => {
      rememberAgent(participant);
    };
    const onTrackSubscribed = (
      track: RemoteTrack,
      _publication: RemoteTrackPublication,
      participant: RemoteParticipant,
    ) => {
      rememberAgent(participant);
      if (track.kind !== Track.Kind.Audio) return;
      const element = track.attach();
      element.autoplay = true;
      element.style.display = 'none';
      document.body.appendChild(element);
      audioElementsRef.current.add(element);
    };
    const onTrackUnsubscribed = (track: RemoteTrack) => removeAttachedAudio(track);
    const onTranscription = (
      segments: TranscriptionSegment[],
      participant?: Participant,
    ) => {
      const role = isAgent(participant) ? 'assistant' : 'user';
      for (const segment of segments) {
        transcriptCallbackRef.current({
          id: segment.id,
          role,
          text: segment.text,
          final: segment.final,
        });
      }
    };

    room
      .on(RoomEvent.ParticipantConnected, onParticipantConnected)
      .on(RoomEvent.ParticipantAttributesChanged, onAttributesChanged)
      .on(RoomEvent.TrackSubscribed, onTrackSubscribed)
      .on(RoomEvent.TrackUnsubscribed, onTrackUnsubscribed)
      .on(RoomEvent.TranscriptionReceived, onTranscription)
      .on(RoomEvent.Reconnecting, () => setStatus('reconnecting'))
      .on(RoomEvent.Reconnected, () => setStatus('connected'))
      .on(RoomEvent.Disconnected, () => {
        if (cancelled || intentionalDisconnectRef.current) return;
        setStatus('fallback');
        fallbackCallbackRef.current('WebRTC 连接已断开');
      })
      .on(RoomEvent.AudioPlaybackStatusChanged, (playing) => setNeedsAudioStart(!playing));

    (async () => {
      try {
        const credentials = await createInterviewRealtimeSession(
          sessionId,
          targetJob,
          jdContent,
          turnMode,
        );
        if (cancelled) return;
        setEffectiveTurnMode(credentials.turn_mode);
        setInterruptionMode(credentials.interruption_mode);
        await room.connect(credentials.url, credentials.token, { autoSubscribe: true });
        if (cancelled) return;
        for (const participant of room.remoteParticipants.values()) rememberAgent(participant);
        await room.localParticipant.setMicrophoneEnabled(false);
        setStatus('connected');
        try {
          await room.startAudio();
          setNeedsAudioStart(false);
        } catch {
          setNeedsAudioStart(true);
        }
      } catch (error) {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : '实时语音连接失败';
        setStatus('fallback');
        fallbackCallbackRef.current(message);
        await room.disconnect();
      }
    })();

    return () => {
      cancelled = true;
      room.removeAllListeners();
      removeAttachedAudio();
      void pcmCaptureRef.current?.discard();
      pcmCaptureRef.current = null;
      roomRef.current = null;
      void room.disconnect();
    };
  }, [enabled, sessionId, targetJob, jdContent, turnMode, rememberAgent, removeAttachedAudio]);

  const rpc = useCallback(async (method: string, payload = '{}') => {
    const room = roomRef.current;
    const destinationIdentity = agentIdentityRef.current;
    if (!room || room.state !== ConnectionState.Connected) {
      throw new Error('实时语音房间尚未连接');
    }
    if (!destinationIdentity) throw new Error('AI 面试官尚未进入房间');
    return room.localParticipant.performRpc({
      destinationIdentity,
      method,
      payload,
      responseTimeout: 20000,
    });
  }, []);

  const resumeAudio = useCallback(async () => {
    const room = roomRef.current;
    if (!room) return;
    await room.startAudio();
    setNeedsAudioStart(false);
  }, []);

  const startListening = useCallback(async () => {
    const room = roomRef.current;
    if (!room) throw new Error('实时语音房间尚未连接');
    await resumeAudio();
    if (agentState === 'speaking') await rpc('jobradar.interrupt');
    await room.localParticipant.setMicrophoneEnabled(true, {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
      channelCount: 1,
    });
    if (captureAudioRef.current) {
      const publication = room.localParticipant.getTrackPublication(Track.Source.Microphone);
      const mediaTrack = publication?.track?.mediaStreamTrack;
      if (mediaTrack) pcmCaptureRef.current = await captureTrackAsWav(mediaTrack);
    }
    setIsMicrophoneEnabled(true);
  }, [agentState, resumeAudio, rpc]);

  const stopListeningAndCommit = useCallback(async (): Promise<RealtimeCommittedTurn> => {
    const room = roomRef.current;
    if (!room) return { transcript: '', audioBlob: null };
    setIsFinalizing(true);
    try {
      const audioBlob = await pcmCaptureRef.current?.stop() ?? null;
      pcmCaptureRef.current = null;
      await room.localParticipant.setMicrophoneEnabled(false);
      setIsMicrophoneEnabled(false);
      const raw = await rpc('jobradar.commit_user_turn');
      const response = JSON.parse(raw) as { transcript?: string };
      return { transcript: response.transcript ?? '', audioBlob };
    } finally {
      setIsFinalizing(false);
    }
  }, [rpc]);

  const cancelUserTurn = useCallback(async () => {
    const room = roomRef.current;
    if (!room) return;
    await pcmCaptureRef.current?.discard();
    pcmCaptureRef.current = null;
    await room.localParticipant.setMicrophoneEnabled(false);
    setIsMicrophoneEnabled(false);
    await rpc('jobradar.clear_user_turn');
  }, [rpc]);

  const repeatQuestion = useCallback(async () => {
    await resumeAudio();
    await rpc('jobradar.repeat_question');
  }, [resumeAudio, rpc]);

  const fallbackToLegacy = useCallback(async () => {
    intentionalDisconnectRef.current = true;
    setStatus('fallback');
    const room = roomRef.current;
    roomRef.current = null;
    if (room) await room.disconnect();
  }, []);

  return {
    active: enabled && (status === 'connecting' || status === 'connected' || status === 'reconnecting'),
    status,
    agentState,
    effectiveTurnMode,
    interruptionMode,
    isMicrophoneEnabled,
    isFinalizing,
    needsAudioStart,
    startListening,
    stopListeningAndCommit,
    cancelUserTurn,
    repeatQuestion,
    resumeAudio,
    fallbackToLegacy,
  };
}
