import { downsampleBuffer, floatToPcm16, normalizeBase64Data, pcm16ToBase64, pcm16ToFloat32, resampleBuffer } from './utils';

const GEMINI_OUTPUT_SAMPLE_RATE = 24000;
const WORKLET_PROCESSOR_NAME = 'voice-support-audio-playback';
const WORKLET_PREROLL_SECONDS = 0.15;
const FALLBACK_PREROLL_SECONDS = 0.18;
const FALLBACK_LEAD_SECONDS = 0.12;

const PLAYBACK_WORKLET_SOURCE = `
class VoiceSupportPlaybackProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = [];
    this.currentChunk = null;
    this.currentOffset = 0;
    this.bufferedFrames = 0;
    this.minBufferFrames = 0;
    this.started = false;
    this.generation = 0;
    this.port.onmessage = (event) => {
      const message = event.data ?? {};
      switch (message.type) {
        case 'configure':
          this.minBufferFrames = Math.max(0, Number(message.minBufferFrames) || 0);
          break;
        case 'append':
          if (typeof message.generation === 'number' && message.generation !== this.generation) {
            return;
          }
          if (message.samples instanceof Float32Array && message.samples.length > 0) {
            this.queue.push(message.samples);
            this.bufferedFrames += message.samples.length;
            if (!this.started && this.bufferedFrames >= this.minBufferFrames) {
              this.started = true;
            }
          }
          break;
        case 'clear':
          this.generation = typeof message.generation === 'number' ? message.generation : this.generation + 1;
          this.queue = [];
          this.currentChunk = null;
          this.currentOffset = 0;
          this.bufferedFrames = 0;
          this.started = false;
          break;
        default:
          break;
      }
    };
  }

  process(_inputs, outputs) {
    const output = outputs[0]?.[0];
    if (!output) {
      return true;
    }

    output.fill(0);
    if (!this.started) {
      return true;
    }

    let writeOffset = 0;
    while (writeOffset < output.length) {
      if (!this.currentChunk || this.currentOffset >= this.currentChunk.length) {
        this.currentChunk = this.queue.shift() ?? null;
        this.currentOffset = 0;
        if (!this.currentChunk) {
          break;
        }
      }

      const remainingInChunk = this.currentChunk.length - this.currentOffset;
      const framesToWrite = Math.min(output.length - writeOffset, remainingInChunk);
      output.set(this.currentChunk.subarray(this.currentOffset, this.currentOffset + framesToWrite), writeOffset);
      this.currentOffset += framesToWrite;
      writeOffset += framesToWrite;
      this.bufferedFrames = Math.max(0, this.bufferedFrames - framesToWrite);
    }

    if (
      this.bufferedFrames === 0 &&
      this.queue.length === 0 &&
      (!this.currentChunk || this.currentOffset >= this.currentChunk.length)
    ) {
      this.started = false;
    }

    return true;
  }
}

registerProcessor('${WORKLET_PROCESSOR_NAME}', VoiceSupportPlaybackProcessor);
`;

function concatFloat32Arrays(chunks: Float32Array[]): Float32Array {
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const merged = new Float32Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
  return merged;
}

export class MicStreamer {
  private audioContext: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private processor: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private sink: GainNode | null = null;

  async start(onChunk: (base64Audio: string) => void): Promise<void> {
    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    });
    this.audioContext = new AudioContext();
    await this.audioContext.resume();
    this.source = this.audioContext.createMediaStreamSource(this.mediaStream);
    this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);
    this.sink = this.audioContext.createGain();
    this.sink.gain.value = 0;
    this.processor.onaudioprocess = (event) => {
      const input = event.inputBuffer.getChannelData(0);
      const mono = new Float32Array(input);
      const downsampled = downsampleBuffer(mono, this.audioContext?.sampleRate ?? 48000, 16000);
      const pcm = floatToPcm16(downsampled);
      onChunk(pcm16ToBase64(pcm));
    };
    this.source.connect(this.processor);
    this.processor.connect(this.sink);
    this.sink.connect(this.audioContext.destination);
  }

  async stop(): Promise<void> {
    this.processor?.disconnect();
    this.source?.disconnect();
    this.sink?.disconnect();
    this.mediaStream?.getTracks().forEach((track) => track.stop());
    if (this.audioContext && this.audioContext.state !== 'closed') {
      await this.audioContext.close();
    }
    this.processor = null;
    this.source = null;
    this.sink = null;
    this.mediaStream = null;
    this.audioContext = null;
  }
}

export class AudioPlaybackQueue {
  private audioContext: AudioContext | null = null;
  private sink: GainNode | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private initializationPromise: Promise<void> | null = null;
  private usingFallbackScheduler = false;
  private nextStartTime = 0;
  private scheduledNodes: AudioBufferSourceNode[] = [];
  private fallbackChunks: Float32Array[] = [];
  private fallbackBufferedFrames = 0;
  private generation = 0;

  private ensureContext(): AudioContext {
    if (!this.audioContext) {
      this.audioContext = new AudioContext();
      this.sink = this.audioContext.createGain();
      this.sink.gain.value = 1;
      this.sink.connect(this.audioContext.destination);
    }
    return this.audioContext;
  }

  private async setupPlaybackNode(): Promise<void> {
    const context = this.ensureContext();
    await context.resume();
    if (this.workletNode || this.usingFallbackScheduler) {
      return;
    }

    if (typeof AudioWorkletNode === 'undefined' || !('audioWorklet' in context)) {
      this.usingFallbackScheduler = true;
      return;
    }

    const blobUrl = URL.createObjectURL(new Blob([PLAYBACK_WORKLET_SOURCE], { type: 'application/javascript' }));
    try {
      await context.audioWorklet.addModule(blobUrl);
    } catch {
      this.usingFallbackScheduler = true;
      return;
    } finally {
      URL.revokeObjectURL(blobUrl);
    }

    if (!this.sink) {
      this.usingFallbackScheduler = true;
      return;
    }

    this.workletNode = new AudioWorkletNode(context, WORKLET_PROCESSOR_NAME, {
      numberOfInputs: 0,
      numberOfOutputs: 1,
      outputChannelCount: [1],
    });
    this.workletNode.connect(this.sink);
    this.workletNode.port.postMessage({
      type: 'configure',
      minBufferFrames: Math.round(context.sampleRate * WORKLET_PREROLL_SECONDS),
    });
  }

  async initialize(): Promise<void> {
    if (!this.initializationPromise) {
      this.initializationPromise = this.setupPlaybackNode();
    }
    await this.initializationPromise;
  }

  private normalizeOutputSamples(rawData: string | Uint8Array | ArrayBuffer, outputRate: number): Float32Array {
    const bytes = normalizeBase64Data(rawData);
    if (bytes.length === 0) {
      return new Float32Array(0);
    }

    const samples = pcm16ToFloat32(bytes);
    if (outputRate === GEMINI_OUTPUT_SAMPLE_RATE) {
      return samples;
    }

    return resampleBuffer(samples, GEMINI_OUTPUT_SAMPLE_RATE, outputRate);
  }

  private enqueueFallback(samples: Float32Array, context: AudioContext): void {
    if (samples.length === 0 || !this.sink) {
      return;
    }

    this.fallbackChunks.push(samples);
    this.fallbackBufferedFrames += samples.length;
    const minBufferedFrames = Math.round(context.sampleRate * FALLBACK_PREROLL_SECONDS);
    if (this.scheduledNodes.length === 0 && this.fallbackBufferedFrames < minBufferedFrames) {
      return;
    }

    const merged = concatFloat32Arrays(this.fallbackChunks);
    this.fallbackChunks = [];
    this.fallbackBufferedFrames = 0;

    const buffer = context.createBuffer(1, merged.length, context.sampleRate);
    buffer.copyToChannel(merged, 0);

    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.sink);

    const startAt = Math.max(context.currentTime + FALLBACK_LEAD_SECONDS, this.nextStartTime);
    source.start(startAt);
    this.nextStartTime = startAt + buffer.duration;
    this.scheduledNodes.push(source);
    source.onended = () => {
      this.scheduledNodes = this.scheduledNodes.filter((node) => node !== source);
      if (this.scheduledNodes.length === 0 && this.audioContext) {
        this.nextStartTime = Math.max(this.audioContext.currentTime, 0);
      }
    };
  }

  async enqueue(rawData: string | Uint8Array | ArrayBuffer): Promise<void> {
    const generation = this.generation;
    await this.initialize();
    const context = this.ensureContext();
    await context.resume();

    const samples = this.normalizeOutputSamples(rawData, context.sampleRate);
    if (samples.length === 0) {
      return;
    }

    if (this.workletNode) {
      const transferable = samples.byteOffset === 0 && samples.byteLength === samples.buffer.byteLength ? samples : samples.slice();
      this.workletNode.port.postMessage(
        {
          type: 'append',
          generation,
          samples: transferable,
        },
        [transferable.buffer],
      );
      return;
    }

    this.enqueueFallback(samples, context);
  }

  clear(): void {
    this.generation += 1;
    this.fallbackChunks = [];
    this.fallbackBufferedFrames = 0;
    this.workletNode?.port.postMessage({ type: 'clear', generation: this.generation });
    this.scheduledNodes.forEach((node) => {
      try {
        node.stop();
      } catch {
        return;
      }
    });
    this.scheduledNodes = [];
    if (this.audioContext) {
      this.nextStartTime = this.audioContext.currentTime;
    } else {
      this.nextStartTime = 0;
    }
  }

  async destroy(): Promise<void> {
    this.clear();
    this.workletNode?.disconnect();
    this.sink?.disconnect();
    if (this.audioContext && this.audioContext.state !== 'closed') {
      await this.audioContext.close();
    }
    this.initializationPromise = null;
    this.sink = null;
    this.workletNode = null;
    this.audioContext = null;
    this.nextStartTime = 0;
    this.usingFallbackScheduler = false;
  }
}
