from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class CustomerIdentity(BaseModel):
    id: str
    email: str | None = None
    name: str | None = None
    metadata: dict[str, str] | None = None


class VoiceSessionBootstrap(BaseModel):
    site_id: str = Field(alias='siteId')
    requested_mode: Literal['voice', 'text'] = Field(default='voice', alias='requestedMode')
    widget_version: str = Field(alias='widgetVersion')
    customer: CustomerIdentity | None = None


class ToolDescriptor(BaseModel):
    name: str
    description: str


class VADConfig(BaseModel):
    disabled: bool = False
    start_of_speech_sensitivity: str = Field(default='START_SENSITIVITY_LOW', alias='startOfSpeechSensitivity')
    end_of_speech_sensitivity: str = Field(default='END_SENSITIVITY_LOW', alias='endOfSpeechSensitivity')
    prefix_padding_ms: int = Field(default=80, alias='prefixPaddingMs')
    silence_duration_ms: int = Field(default=600, alias='silenceDurationMs')


class WidgetSessionUI(BaseModel):
    title: str = 'Support assistant'
    welcome_message: str = Field(default='How can I help you today?', alias='welcomeMessage')
    countdown_warning_seconds: int = Field(default=60, alias='countdownWarningSeconds')


class WidgetPublicConfig(BaseModel):
    default_mode: Literal['voice', 'text'] = Field(default='voice', alias='defaultMode')
    voice_enabled: bool = Field(default=True, alias='voiceEnabled')
    text_enabled: bool = Field(default=True, alias='textEnabled')
    theme: str = 'graphite'
    strict_behavior_enabled: bool = Field(default=True, alias='strictBehaviorEnabled')
    vad_config: VADConfig = Field(alias='vadConfig')
    ui: WidgetSessionUI


class WidgetSessionConfig(BaseModel):
    session_id: str = Field(alias='sessionId')
    session_jwt: str = Field(alias='sessionJwt')
    ephemeral_token: str = Field(alias='ephemeralToken')
    realtime_model: str = Field(alias='realtimeModel')
    max_session_duration_seconds: int = Field(alias='maxSessionDurationSeconds')
    enabled_tools: list[ToolDescriptor] = Field(alias='enabledTools')
    text_fallback_model: str = Field(alias='textFallbackModel')
    text_fallback_enabled: bool = Field(default=True, alias='textFallbackEnabled')
    default_mode: Literal['voice', 'text'] = Field(default='voice', alias='defaultMode')
    voice_enabled: bool = Field(default=True, alias='voiceEnabled')
    text_enabled: bool = Field(default=True, alias='textEnabled')
    theme: str = 'graphite'
    vad_config: VADConfig = Field(alias='vadConfig')
    strict_behavior_enabled: bool = Field(default=True, alias='strictBehaviorEnabled')
    control_stream_url: str = Field(alias='controlStreamUrl')
    strike_policy: dict[str, Any] = Field(alias='strikePolicy')
    ui: WidgetSessionUI


class ToolExecutionRequest(BaseModel):
    session_id: str = Field(alias='sessionId')
    tool_name: str = Field(alias='toolName')
    call_id: str = Field(alias='callId')
    args: dict[str, Any]


class ToolExecutionResponse(BaseModel):
    call_id: str = Field(alias='callId')
    tool_name: str = Field(alias='toolName')
    output: Any
    is_error: bool = Field(default=False, alias='isError')


class TranscriptPayload(BaseModel):
    session_id: str = Field(alias='sessionId')
    role: Literal['user', 'assistant', 'system']
    text: str = ''
    final: bool = False
    sequence: int
    source: Literal['input_transcription', 'output_transcription', 'text_fallback']


class UsagePayload(BaseModel):
    session_id: str = Field(alias='sessionId')
    input_tokens: int = Field(default=0, alias='inputTokens')
    output_tokens: int = Field(default=0, alias='outputTokens')
    audio_input_seconds: float = Field(default=0.0, alias='audioInputSeconds')
    audio_output_seconds: float = Field(default=0.0, alias='audioOutputSeconds')


class SessionEndPayload(BaseModel):
    session_id: str = Field(alias='sessionId')
    reason: Literal['completed', 'max_duration_reached', 'fallback_to_text', 'socket_error', 'user_closed']


class ConnectionStatePayload(BaseModel):
    session_id: str = Field(alias='sessionId')
    state: Literal['connecting', 'open', 'closed', 'error']
    detail: str | None = None


class WidgetEvent(BaseModel):
    type: Literal['transcript', 'usage', 'session_end', 'connection_state']
    payload: dict[str, Any]


class TextTurnRequest(BaseModel):
    session_id: str = Field(alias='sessionId')
    text: str


class PolicyControlEvent(BaseModel):
    type: Literal['policy_state', 'policy_warning', 'policy_strike', 'policy_terminated']
    message: str | None = None
    current_strike_count: int = Field(default=0, alias='currentStrikeCount')
    max_strikes: int = Field(default=3, alias='maxStrikes')
    terminated: bool = False
    classification: str | None = None
    reason_code: str | None = Field(default=None, alias='reasonCode')
    review_tag: str | None = Field(default=None, alias='reviewTag')


class TextTurnResponse(BaseModel):
    session_id: str = Field(alias='sessionId')
    text: str
    current_strike_count: int = Field(default=0, alias='currentStrikeCount')
    terminated: bool = False
    policy_event: PolicyControlEvent | None = Field(default=None, alias='policyEvent')


class UserTurnRequest(BaseModel):
    session_id: str = Field(alias='sessionId')
    role: Literal['user'] = 'user'
    text: str
    source: Literal['voice_input_transcription', 'text_input']
    sequence: int
    final: Literal[True] = True
    timestamp: datetime | None = None


class UserTurnResponse(BaseModel):
    accepted: bool = True
    current_strike_count: int = Field(default=0, alias='currentStrikeCount')
    terminated: bool = False
    classification: Literal['IN_SCOPE', 'OUT_OF_SCOPE', 'AMBIGUOUS'] | None = None
    reason_code: str | None = Field(default=None, alias='reasonCode')
    policy_event: PolicyControlEvent | None = Field(default=None, alias='policyEvent')


class KnowledgeEntryInput(BaseModel):
    title: str
    content: str
    source: str | None = None
    metadata: dict[str, str] | None = None


class KnowledgeImportRequest(BaseModel):
    entries: list[KnowledgeEntryInput]


class KnowledgeEntryResponse(BaseModel):
    id: str
    site_id: str
    title: str
    content: str
    source: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    created_at: datetime


class SiteSummaryResponse(BaseModel):
    site_id: str
    display_name: str
    active_sessions: int
    daily_sessions: int
    monthly_estimated_cost: float
    monthly_budget: float


class SessionSummaryResponse(BaseModel):
    id: str
    status: str
    mode: str
    estimated_cost: float
    created_at: datetime
