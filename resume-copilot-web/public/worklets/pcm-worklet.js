// AudioWorkletProcessor that converts Float32 input samples to 16-bit PCM
// and posts them to the main thread in fixed-size frames (~100ms @ 16kHz = 1600 samples).

class PcmWorkletProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.frameSize = 1600; // 100ms at 16kHz
    this.buffer = new Int16Array(this.frameSize);
    this.bufferIdx = 0;
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (!channel) return true;

    for (let i = 0; i < channel.length; i++) {
      // Float32 [-1, 1] → Int16 [-32768, 32767]
      const s = Math.max(-1, Math.min(1, channel[i]));
      this.buffer[this.bufferIdx++] = s < 0 ? s * 0x8000 : s * 0x7fff;
      if (this.bufferIdx >= this.frameSize) {
        // Post a copy; reuse the buffer
        this.port.postMessage(this.buffer.buffer.slice(0));
        this.bufferIdx = 0;
      }
    }
    return true;
  }
}

registerProcessor('pcm-worklet', PcmWorkletProcessor);
