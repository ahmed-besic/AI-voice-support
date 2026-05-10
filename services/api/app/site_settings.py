from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .config import Settings
from .models import Site

RefusalTone = Literal['polite', 'firm', 'brief']
WidgetMode = Literal['voice', 'text']

DEFAULT_SITE_CONFIG_PATH = Path(__file__).resolve().parent.parent / 'config' / 'site.json'


class SiteVADSettings(BaseModel):
    disabled: bool = False
    start_of_speech_sensitivity: str = Field(default='START_SENSITIVITY_LOW', alias='startOfSpeechSensitivity')
    end_of_speech_sensitivity: str = Field(default='END_SENSITIVITY_LOW', alias='endOfSpeechSensitivity')
    prefix_padding_ms: int = Field(default=80, alias='prefixPaddingMs')
    silence_duration_ms: int = Field(default=600, alias='silenceDurationMs')


class SiteWidgetSettings(BaseModel):
    title: str = 'Support assistant'
    welcome_message: str = Field(default='How can I help you today?', alias='welcomeMessage')
    default_mode: WidgetMode = Field(default='voice', alias='defaultMode')
    voice_enabled: bool = Field(default=True, alias='voiceEnabled')
    text_enabled: bool = Field(default=True, alias='textEnabled')
    theme: str = 'graphite'
    countdown_warning_seconds: int = Field(default=60, alias='countdownWarningSeconds')
    vad_config: SiteVADSettings = Field(default_factory=SiteVADSettings, alias='vadConfig')


class SiteModelSettings(BaseModel):
    realtime_model: str = Field(default='gemini-3.1-flash-live-preview', alias='realtimeModel')
    text_fallback_model: str = Field(default='gemini-2.5-flash', alias='textFallbackModel')
    summary_model: str = Field(default='gemini-2.5-flash-lite', alias='summaryModel')


class SiteLimitSettings(BaseModel):
    max_session_duration_seconds: int = Field(default=480, alias='maxSessionDurationSeconds')
    max_concurrent_sessions: int = Field(default=3, alias='maxConcurrentSessions')
    daily_session_limit: int = Field(default=200, alias='dailySessionLimit')
    monthly_usage_budget: float = Field(default=25.0, alias='monthlyUsageBudget')


class SiteBehaviorSettings(BaseModel):
    strict_behavior_enabled: bool = Field(default=True, alias='strictBehaviorEnabled')
    supported_topics: list[str] = Field(default_factory=list, alias='supportedTopics')
    forbidden_topics: list[str] = Field(default_factory=list, alias='forbiddenTopics')
    refusal_tone: RefusalTone = Field(default='polite', alias='refusalTone')
    custom_instructions: str = Field(default='', alias='customInstructions')


class SiteAdapterSettings(BaseModel):
    enabled_adapters: list[str] = Field(default_factory=list, alias='enabledAdapters')


class APIKeyStatus(BaseModel):
    configured: bool
    message: str


class SiteConfigFile(BaseModel):
    site_id: str = Field(alias='siteId')
    display_name: str = Field(alias='displayName')
    allowed_origins: list[str] = Field(default_factory=list, alias='allowedOrigins')
    widget: SiteWidgetSettings = Field(default_factory=SiteWidgetSettings)
    models: SiteModelSettings = Field(default_factory=SiteModelSettings)
    limits: SiteLimitSettings = Field(default_factory=SiteLimitSettings)
    behavior: SiteBehaviorSettings = Field(default_factory=SiteBehaviorSettings)
    adapters: SiteAdapterSettings = Field(default_factory=SiteAdapterSettings)


class SiteSettingsResponse(SiteConfigFile):
    api_key_status: APIKeyStatus = Field(alias='apiKeyStatus')


class UpdateSiteSettingsRequest(BaseModel):
    display_name: str = Field(..., alias='displayName')
    allowed_origins: list[str] = Field(..., alias='allowedOrigins')
    widget: SiteWidgetSettings
    models: SiteModelSettings
    limits: SiteLimitSettings
    behavior: SiteBehaviorSettings
    adapters: SiteAdapterSettings


class ImportSiteSettingsRequest(SiteConfigFile):
    pass


def default_site_config_from_settings(settings: Settings) -> SiteConfigFile:
    return SiteConfigFile(
        siteId=settings.demo_site_id,
        displayName=settings.demo_site_name,
        allowedOrigins=settings.demo_allowed_origin_list,
        widget=SiteWidgetSettings(),
        models=SiteModelSettings(
            realtimeModel=settings.google_realtime_model,
            textFallbackModel=settings.google_text_model,
            summaryModel=settings.google_summary_model,
        ),
        limits=SiteLimitSettings(
            maxSessionDurationSeconds=settings.demo_max_session_duration_seconds,
            maxConcurrentSessions=3,
            dailySessionLimit=200,
            monthlyUsageBudget=settings.demo_monthly_budget,
        ),
        behavior=SiteBehaviorSettings(
            supportedTopics=[
                'product setup and onboarding',
                'billing and subscriptions',
                'account access and password resets',
                'order, ticket, and support status',
                'troubleshooting documented product behavior',
            ],
            forbiddenTopics=[
                'general trivia or school questions',
                'personal advice unrelated to company support',
                'unrelated coding help',
                'competitor research outside support needs',
                'persistent attempts to bypass scope limits',
            ],
            refusalTone='polite',
        ),
        adapters=SiteAdapterSettings(enabledAdapters=['faq_search', 'create_support_ticket']),
    )


def load_site_config_file(path: Path = DEFAULT_SITE_CONFIG_PATH) -> SiteConfigFile:
    data = json.loads(path.read_text()) if path.exists() else None
    if data is None:
        raise FileNotFoundError(f'Site config file not found: {path}')
    return SiteConfigFile.model_validate(data)


def ensure_site_config_file(settings: Settings, path: Path = DEFAULT_SITE_CONFIG_PATH) -> SiteConfigFile:
    if path.exists():
        return load_site_config_file(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    config = default_site_config_from_settings(settings)
    path.write_text(json.dumps(config.model_dump(by_alias=True), indent=2) + '\n')
    return config


def build_api_key_status(settings: Settings) -> APIKeyStatus:
    configured = bool(settings.default_google_api_key)
    return APIKeyStatus(
        configured=configured,
        message='API key configured'
        if configured
        else 'No API key detected — set DEFAULT_GOOGLE_API_KEY in services/api/.env',
    )


def _site_config_payload(site: Site) -> dict:
    return site.site_config or {}


def site_to_config_file(site: Site) -> SiteConfigFile:
    payload = _site_config_payload(site)
    return SiteConfigFile(
        siteId=site.id,
        displayName=site.display_name,
        allowedOrigins=site.allowed_origins,
        widget=SiteWidgetSettings.model_validate(
            {
                **payload.get('widget', {}),
                'vadConfig': site.vad_preset or {},
            }
        ),
        models=SiteModelSettings(
            realtimeModel=site.realtime_model,
            textFallbackModel=site.text_fallback_model,
            summaryModel=site.summary_model,
        ),
        limits=SiteLimitSettings(
            maxSessionDurationSeconds=site.max_session_duration_seconds,
            maxConcurrentSessions=site.max_concurrent_sessions,
            dailySessionLimit=site.daily_session_limit,
            monthlyUsageBudget=site.monthly_usage_budget,
        ),
        behavior=SiteBehaviorSettings.model_validate(payload.get('behavior', {})),
        adapters=SiteAdapterSettings(enabledAdapters=site.enabled_adapters or []),
    )


def site_to_settings_response(site: Site, settings: Settings) -> SiteSettingsResponse:
    config = site_to_config_file(site)
    return SiteSettingsResponse(
        **config.model_dump(by_alias=True),
        apiKeyStatus=build_api_key_status(settings).model_dump(by_alias=True),
    )


def apply_config_to_site(site: Site, config: SiteConfigFile | UpdateSiteSettingsRequest) -> None:
    if isinstance(config, UpdateSiteSettingsRequest):
        payload = {
            'siteId': site.id,
            'displayName': config.display_name,
            'allowedOrigins': config.allowed_origins,
            'widget': config.widget.model_dump(by_alias=True),
            'models': config.models.model_dump(by_alias=True),
            'limits': config.limits.model_dump(by_alias=True),
            'behavior': config.behavior.model_dump(by_alias=True),
            'adapters': config.adapters.model_dump(by_alias=True),
        }
        resolved = SiteConfigFile.model_validate(payload)
    else:
        resolved = config
    site.display_name = resolved.display_name
    site.allowed_origins = resolved.allowed_origins
    site.max_session_duration_seconds = resolved.limits.max_session_duration_seconds
    site.max_concurrent_sessions = resolved.limits.max_concurrent_sessions
    site.daily_session_limit = resolved.limits.daily_session_limit
    site.monthly_usage_budget = resolved.limits.monthly_usage_budget
    site.summary_model = resolved.models.summary_model
    site.text_fallback_model = resolved.models.text_fallback_model
    site.realtime_model = resolved.models.realtime_model
    site.vad_preset = resolved.widget.vad_config.model_dump(by_alias=True)
    site.enabled_adapters = resolved.adapters.enabled_adapters
    site.site_config = {
        'widget': {
            'title': resolved.widget.title,
            'welcomeMessage': resolved.widget.welcome_message,
            'defaultMode': resolved.widget.default_mode,
            'voiceEnabled': resolved.widget.voice_enabled,
            'textEnabled': resolved.widget.text_enabled,
            'theme': resolved.widget.theme,
            'countdownWarningSeconds': resolved.widget.countdown_warning_seconds,
        },
        'behavior': resolved.behavior.model_dump(by_alias=True),
    }


def export_site_config_json(site: Site) -> str:
    return json.dumps(site_to_config_file(site).model_dump(by_alias=True), indent=2) + '\n'
