'use client';

const TARGET_SAMPLE_RATE = 16000;
const MAX_CAPTURE_BYTES = 12 * 1024 * 1024;

export function encodePcmWav(chunks: ArrayBuffer[], sampleRate: number): Blob | null {
  const pcmBytes = chunks.reduce((total, chunk) => total + chunk.byteLength, 0);
  if (!pcmBytes) return null;
  const output = new ArrayBuffer(44 + pcmBytes);
  const view = new DataView(output);
  const writeText = (offset: number, value: string) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index));
    }
  };

  writeText(0, 'RIFF');
  view.setUint32(4, 36 + pcmBytes, true);
  writeText(8, 'WAVE');
  writeText(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeText(36, 'data');
  view.setUint32(40, pcmBytes, true);

  let offset = 44;
  for (const chunk of chunks) {
    new Uint8Array(output, offset, chunk.byteLength).set(new Uint8Array(chunk));
    offset += chunk.byteLength;
  }
  return new Blob([output], { type: 'audio/wav' });
}

export interface PcmWavCapture {
  stop: () => Promise<Blob | null>;
  discard: () => Promise<void>;
}

/** Capture an existing microphone track without owning or stopping that track. */
export async function captureTrackAsWav(track: MediaStreamTrack): Promise<PcmWavCapture> {
  const AudioCtx = window.AudioContext
    || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const audioContext = new AudioCtx({ sampleRate: TARGET_SAMPLE_RATE });
  await audioContext.audioWorklet.addModule('/worklets/pcm-worklet.js');
  const source = audioContext.createMediaStreamSource(new MediaStream([track]));
  const worklet = new AudioWorkletNode(audioContext, 'pcm-worklet');
  const chunks: ArrayBuffer[] = [];
  let capturedBytes = 0;
  let closed = false;

  worklet.port.onmessage = (event) => {
    const chunk = event.data as ArrayBuffer;
    if (closed || capturedBytes + chunk.byteLength > MAX_CAPTURE_BYTES) return;
    chunks.push(chunk.slice(0));
    capturedBytes += chunk.byteLength;
  };
  source.connect(worklet);

  const close = async () => {
    if (closed) return;
    closed = true;
    source.disconnect();
    worklet.disconnect();
    if (audioContext.state !== 'closed') await audioContext.close();
  };

  return {
    stop: async () => {
      await close();
      return encodePcmWav(chunks, audioContext.sampleRate);
    },
    discard: async () => {
      chunks.length = 0;
      await close();
    },
  };
}
