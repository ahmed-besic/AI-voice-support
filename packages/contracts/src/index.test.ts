import { describe, expect, it } from 'vitest';

import { voiceSessionBootstrapSchema, widgetSessionConfigSchema } from './index';

describe('contracts', () => {
  it('validates widget bootstrap payloads', () => {
    const parsed = voiceSessionBootstrapSchema.parse({
      siteId: 'demo-site',
      requestedMode: 'voice',
      widgetVersion: '0.1.0',
    });
    expect(parsed.siteId).toBe('demo-site');
  });

  it('validates session config payloads', () => {
    const parsed = widgetSessionConfigSchema.parse({
      sessionId: crypto.randomUUID(),
      sessionJwt: 'token',
      ephemeralToken: 'token',
      realtimeModel: 'gemini-live',
      maxSessionDurationSeconds: 480,
      enabledTools: [{ name: 'faq_search', description: 'Search FAQ' }],
      textFallbackModel: 'gemini-text',
      textFallbackEnabled: true,
      strictBehaviorEnabled: true,
      controlStreamUrl: 'http://localhost:8000/widget/sessions/demo/control-stream?token=token',
      strikePolicy: {
        maxStrikes: 3,
        ambiguousAction: 'log_only',
      },
      vadConfig: {
        disabled: false,
        startOfSpeechSensitivity: 'START_SENSITIVITY_LOW',
        endOfSpeechSensitivity: 'END_SENSITIVITY_LOW',
        prefixPaddingMs: 80,
        silenceDurationMs: 600,
      },
      ui: {
        title: 'Support assistant',
        welcomeMessage: 'Hello',
        countdownWarningSeconds: 60,
      },
    });
    expect(parsed.enabledTools).toHaveLength(1);
  });
});
