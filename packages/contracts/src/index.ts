import { z } from 'zod';

export const requestedModeSchema = z.enum(['voice', 'text']);
export type RequestedMode = z.infer<typeof requestedModeSchema>;

export const customerIdentitySchema = z.object({
  id: z.string().min(1),
  email: z.string().email().optional(),
  name: z.string().optional(),
  metadata: z.record(z.string(), z.string()).optional(),
}).optional();

export const voiceSessionBootstrapSchema = z.object({
  siteId: z.string().min(1),
  requestedMode: requestedModeSchema.default('voice'),
  widgetVersion: z.string().min(1),
  customer: customerIdentitySchema,
});
export type VoiceSessionBootstrap = z.infer<typeof voiceSessionBootstrapSchema>;

export const vadConfigSchema = z.object({
  disabled: z.boolean().default(false),
  startOfSpeechSensitivity: z.enum(['START_SENSITIVITY_LOW', 'START_SENSITIVITY_HIGH']).default('START_SENSITIVITY_LOW'),
  endOfSpeechSensitivity: z.enum(['END_SENSITIVITY_LOW', 'END_SENSITIVITY_HIGH']).default('END_SENSITIVITY_LOW'),
  prefixPaddingMs: z.number().int().min(0).max(2000).default(80),
  silenceDurationMs: z.number().int().min(50).max(3000).default(600),
});
export type VADConfig = z.infer<typeof vadConfigSchema>;

export const toolDescriptorSchema = z.object({
  name: z.string().min(1),
  description: z.string().min(1),
});
export type ToolDescriptor = z.infer<typeof toolDescriptorSchema>;

export const widgetSessionConfigSchema = z.object({
  sessionId: z.string().uuid(),
  sessionJwt: z.string().min(1),
  ephemeralToken: z.string().min(1),
  realtimeModel: z.string().min(1),
  maxSessionDurationSeconds: z.number().int().min(60).max(900),
  enabledTools: z.array(toolDescriptorSchema),
  textFallbackModel: z.string().min(1),
  textFallbackEnabled: z.boolean().default(true),
  defaultMode: requestedModeSchema.default('voice'),
  voiceEnabled: z.boolean().default(true),
  textEnabled: z.boolean().default(true),
  theme: z.enum(['graphite', 'sand', 'ocean']).default('graphite'),
  vadConfig: vadConfigSchema,
  strictBehaviorEnabled: z.boolean().default(true),
  controlStreamUrl: z.string().min(1),
  strikePolicy: z.object({
    maxStrikes: z.number().int().min(1).default(3),
    ambiguousAction: z.string().min(1),
  }),
  ui: z.object({
    title: z.string().default('Support assistant'),
    welcomeMessage: z.string().default('How can I help you today?'),
    countdownWarningSeconds: z.number().int().min(10).default(60),
  }),
});
export type WidgetSessionConfig = z.infer<typeof widgetSessionConfigSchema>;

export const widgetPublicConfigSchema = z.object({
  defaultMode: requestedModeSchema.default('voice'),
  voiceEnabled: z.boolean().default(true),
  textEnabled: z.boolean().default(true),
  theme: z.enum(['graphite', 'sand', 'ocean']).default('graphite'),
  strictBehaviorEnabled: z.boolean().default(true),
  ui: z.object({
    title: z.string().default('Support assistant'),
    welcomeMessage: z.string().default('How can I help you today?'),
    countdownWarningSeconds: z.number().int().min(10).default(60),
  }),
  vadConfig: vadConfigSchema,
});
export type WidgetPublicConfig = z.infer<typeof widgetPublicConfigSchema>;

export const toolExecutionRequestSchema = z.object({
  sessionId: z.string().uuid(),
  toolName: z.string().min(1),
  callId: z.string().min(1),
  args: z.record(z.string(), z.unknown()),
});
export type ToolExecutionRequest = z.infer<typeof toolExecutionRequestSchema>;

export const toolExecutionResponseSchema = z.object({
  callId: z.string().min(1),
  toolName: z.string().min(1),
  output: z.unknown(),
  isError: z.boolean().default(false),
});
export type ToolExecutionResponse = z.infer<typeof toolExecutionResponseSchema>;

export const transcriptEventSchema = z.object({
  sessionId: z.string().uuid(),
  role: z.enum(['user', 'assistant', 'system']),
  text: z.string().default(''),
  final: z.boolean().default(false),
  sequence: z.number().int().nonnegative(),
  source: z.enum(['input_transcription', 'output_transcription', 'text_fallback']),
});
export type TranscriptEvent = z.infer<typeof transcriptEventSchema>;

export const usageEventSchema = z.object({
  sessionId: z.string().uuid(),
  inputTokens: z.number().int().nonnegative().default(0),
  outputTokens: z.number().int().nonnegative().default(0),
  audioInputSeconds: z.number().nonnegative().default(0),
  audioOutputSeconds: z.number().nonnegative().default(0),
});
export type UsageEvent = z.infer<typeof usageEventSchema>;

export const widgetEventSchema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('transcript'), payload: transcriptEventSchema }),
  z.object({ type: z.literal('usage'), payload: usageEventSchema }),
  z.object({
    type: z.literal('session_end'),
    payload: z.object({
      sessionId: z.string().uuid(),
      reason: z.enum(['completed', 'max_duration_reached', 'fallback_to_text', 'socket_error', 'user_closed']),
    }),
  }),
  z.object({
    type: z.literal('connection_state'),
    payload: z.object({
      sessionId: z.string().uuid(),
      state: z.enum(['connecting', 'open', 'closed', 'error']),
      detail: z.string().optional(),
    }),
  }),
]);
export type WidgetEvent = z.infer<typeof widgetEventSchema>;

export const policyControlEventSchema = z.object({
  type: z.enum(['policy_state', 'policy_warning', 'policy_strike', 'policy_terminated']),
  message: z.string().nullable().optional(),
  currentStrikeCount: z.number().int().nonnegative().default(0),
  maxStrikes: z.number().int().positive().default(3),
  terminated: z.boolean().default(false),
  classification: z.enum(['IN_SCOPE', 'OUT_OF_SCOPE', 'AMBIGUOUS']).nullable().optional(),
  reasonCode: z.string().nullable().optional(),
  reviewTag: z.string().nullable().optional(),
});
export type PolicyControlEvent = z.infer<typeof policyControlEventSchema>;

export const userTurnRequestSchema = z.object({
  sessionId: z.string().uuid(),
  role: z.literal('user').default('user'),
  text: z.string().min(1),
  source: z.enum(['voice_input_transcription', 'text_input']),
  sequence: z.number().int().nonnegative(),
  final: z.literal(true).default(true),
  timestamp: z.string().datetime().optional(),
});
export type UserTurnRequest = z.infer<typeof userTurnRequestSchema>;

export const userTurnResponseSchema = z.object({
  accepted: z.boolean().default(true),
  currentStrikeCount: z.number().int().nonnegative().default(0),
  terminated: z.boolean().default(false),
  classification: z.enum(['IN_SCOPE', 'OUT_OF_SCOPE', 'AMBIGUOUS']).optional(),
  reasonCode: z.string().optional(),
  policyEvent: policyControlEventSchema.optional(),
});
export type UserTurnResponse = z.infer<typeof userTurnResponseSchema>;

export const adminSiteSummarySchema = z.object({
  siteId: z.string(),
  displayName: z.string(),
  activeSessions: z.number().int().nonnegative(),
  dailySessions: z.number().int().nonnegative(),
  monthlyEstimatedCost: z.number().nonnegative(),
  monthlyBudget: z.number().nonnegative(),
});
export type AdminSiteSummary = z.infer<typeof adminSiteSummarySchema>;
