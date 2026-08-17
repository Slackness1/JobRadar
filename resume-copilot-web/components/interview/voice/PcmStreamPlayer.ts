const MIN_SCHEDULE_SAMPLES = 2048;
const START_BUFFER_SECONDS = 0.03;

interface PcmStreamPlayerOptions {
  sampleRate: number;
  onFirstAudioScheduled?: (delayMs: number) => void;
}

export class PcmStreamPlayer {
  private readonly context: AudioContext;
  private readonly sampleRate: number;
  private readonly onFirstAudioScheduled?: (delayMs: number) => void;
  private readonly sources = new Set<AudioBufferSourceNode>();
  private readonly queuedSamples: Float32Array[] = [];
  private queuedSampleCount = 0;
  private pendingByte: number | null = null;
  private nextStartTime = 0;
  private firstStartTime: number | null = null;
  private totalScheduledSeconds = 0;
  private inputFinished = false;
  private stopped = false;
  private doneSettled = false;
  private readonly donePromise: Promise<void>;
  private resolveDone!: () => void;

  constructor(options: PcmStreamPlayerOptions) {
    this.sampleRate = options.sampleRate;
    this.onFirstAudioScheduled = options.onFirstAudioScheduled;
    this.context = new AudioContext();
    this.donePromise = new Promise<void>((resolve) => {
      this.resolveDone = resolve;
    });
  }

  async prepare(): Promise<void> {
    if (this.context.state === 'suspended') await this.context.resume();
  }

  append(chunk: Uint8Array): void {
    if (this.stopped || this.inputFinished || chunk.byteLength === 0) return;
    const decoded = this.decodeS16Le(chunk);
    if (decoded.length === 0) return;
    this.queuedSamples.push(decoded);
    this.queuedSampleCount += decoded.length;
    if (this.queuedSampleCount >= MIN_SCHEDULE_SAMPLES) this.flushQueuedSamples();
  }

  async finish(): Promise<void> {
    if (this.stopped) return;
    this.inputFinished = true;
    if (this.pendingByte !== null) {
      throw new Error('PCM stream ended on an incomplete sample');
    }
    this.flushQueuedSamples();
    if (this.firstStartTime === null) throw new Error('TTS returned an empty PCM stream');
    this.resolveIfComplete();
    await this.donePromise;
  }

  stop(): void {
    if (this.stopped) return;
    this.stopped = true;
    this.queuedSamples.length = 0;
    this.queuedSampleCount = 0;
    this.pendingByte = null;
    for (const source of this.sources) {
      try {
        source.stop();
      } catch {
        // A source that has already ended is safe to ignore during cancellation.
      }
    }
    this.sources.clear();
    this.settleDone();
    void this.context.close();
  }

  async close(): Promise<void> {
    if (this.context.state !== 'closed') await this.context.close();
  }

  get progress(): number {
    if (this.firstStartTime === null || this.totalScheduledSeconds <= 0) return 0;
    const playedSeconds = Math.max(0, this.context.currentTime - this.firstStartTime);
    if (this.inputFinished) {
      return Math.min(1, playedSeconds / this.totalScheduledSeconds);
    }
    const activeWindow = Math.max(this.totalScheduledSeconds, playedSeconds + 0.35);
    return Math.min(0.92, playedSeconds / activeWindow);
  }

  private decodeS16Le(chunk: Uint8Array): Float32Array {
    const totalBytes = chunk.byteLength + (this.pendingByte === null ? 0 : 1);
    const sampleCount = Math.floor(totalBytes / 2);
    const samples = new Float32Array(sampleCount);
    let chunkOffset = 0;
    let sampleOffset = 0;

    if (this.pendingByte !== null && chunk.byteLength > 0) {
      samples[sampleOffset] = this.normalizeSample(this.pendingByte | (chunk[0] << 8));
      sampleOffset += 1;
      chunkOffset = 1;
      this.pendingByte = null;
    }

    while (chunkOffset + 1 < chunk.byteLength) {
      const raw = chunk[chunkOffset] | (chunk[chunkOffset + 1] << 8);
      samples[sampleOffset] = this.normalizeSample(raw);
      sampleOffset += 1;
      chunkOffset += 2;
    }

    if (chunkOffset < chunk.byteLength) this.pendingByte = chunk[chunkOffset];
    return samples;
  }

  private normalizeSample(raw: number): number {
    const signed = raw >= 0x8000 ? raw - 0x10000 : raw;
    return signed / 32768;
  }

  private flushQueuedSamples(): void {
    if (this.queuedSampleCount === 0 || this.stopped) return;
    const samples = new Float32Array(this.queuedSampleCount);
    let offset = 0;
    for (const queued of this.queuedSamples) {
      samples.set(queued, offset);
      offset += queued.length;
    }
    this.queuedSamples.length = 0;
    this.queuedSampleCount = 0;
    this.schedule(samples);
  }

  private schedule(samples: Float32Array): void {
    const buffer = this.context.createBuffer(1, samples.length, this.sampleRate);
    buffer.getChannelData(0).set(samples);
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.context.destination);

    const earliestStart = this.context.currentTime + START_BUFFER_SECONDS;
    const startTime = Math.max(this.nextStartTime, earliestStart);
    if (this.firstStartTime === null) {
      this.firstStartTime = startTime;
      this.onFirstAudioScheduled?.(
        Math.max(0, startTime - this.context.currentTime) * 1000,
      );
    }
    this.nextStartTime = startTime + buffer.duration;
    this.totalScheduledSeconds = this.nextStartTime - this.firstStartTime;
    this.sources.add(source);
    source.onended = () => {
      this.sources.delete(source);
      this.resolveIfComplete();
    };
    source.start(startTime);
  }

  private resolveIfComplete(): void {
    if (this.inputFinished && this.sources.size === 0) this.settleDone();
  }

  private settleDone(): void {
    if (this.doneSettled) return;
    this.doneSettled = true;
    this.resolveDone();
  }
}
