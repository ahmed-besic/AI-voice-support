import { describe, expect, it } from 'vitest';

import { collectInlineAudioParts, downsampleBuffer, floatToPcm16, formatRemaining, resampleBuffer } from './utils';

describe('widget utils', () => {
  it('formats countdown values', () => {
    expect(formatRemaining(125)).toBe('2:05');
  });

  it('converts float audio to pcm16', () => {
    const pcm = floatToPcm16(new Float32Array([0, 1, -1]));
    expect(Array.from(pcm)).toEqual([0, 32767, -32768]);
  });

  it('downs samples to a smaller sample rate', () => {
    const input = new Float32Array([1, 1, 0, 0]);
    const output = downsampleBuffer(input, 4, 2);
    expect(Array.from(output)).toEqual([1, 0]);
  });

  it('resamples audio when playback sample rates differ', () => {
    const input = new Float32Array([0, 1]);
    const output = resampleBuffer(input, 2, 4);
    expect(Array.from(output)).toEqual([0, 0.5, 1, 1]);
  });

  it('collects all inline audio parts from multi-part live events', () => {
    const message = {
      serverContent: {
        modelTurn: {
          parts: [
            { inlineData: { data: 'first-audio' } },
            { text: 'ignored' },
            { inlineData: { data: 'second-audio' } },
          ],
        },
      },
    };

    expect(collectInlineAudioParts(message)).toEqual(['first-audio', 'second-audio']);
  });
});
