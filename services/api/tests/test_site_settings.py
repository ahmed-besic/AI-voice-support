import json
from types import SimpleNamespace

from app.site_settings import (
    ImportSiteSettingsRequest,
    UpdateSiteSettingsRequest,
    build_api_key_status,
    ensure_site_config_file,
)


def test_api_key_status_hides_secret_value():
    status = build_api_key_status(SimpleNamespace(default_google_api_key='secret-key'))
    assert status.configured is True
    assert status.message == 'API key configured'


def test_ensure_site_config_file_creates_default_payload(tmp_path):
    config = ensure_site_config_file(
        SimpleNamespace(
            demo_site_id='demo-site',
            demo_site_name='Demo Site',
            demo_allowed_origin_list=['http://localhost:3000'],
            demo_max_session_duration_seconds=480,
            demo_monthly_budget=25.0,
            google_realtime_model='gemini-live',
            google_text_model='gemini-text',
            google_summary_model='gemini-summary',
        ),
        tmp_path / 'site.json',
    )
    assert config.site_id == 'demo-site'
    assert config.widget.theme == 'graphite'
    payload = json.loads((tmp_path / 'site.json').read_text())
    assert payload['siteId'] == 'demo-site'


def test_refusal_tone_validation_rejects_unknown_values():
    payload = {
        'siteId': 'demo-site',
        'displayName': 'Demo Site',
        'allowedOrigins': ['http://localhost:3000'],
        'widget': {
            'title': 'Support',
            'welcomeMessage': 'Hello',
            'defaultMode': 'voice',
            'voiceEnabled': True,
            'textEnabled': True,
            'theme': 'graphite',
            'countdownWarningSeconds': 60,
            'vadConfig': {
                'disabled': False,
                'startOfSpeechSensitivity': 'START_SENSITIVITY_LOW',
                'endOfSpeechSensitivity': 'END_SENSITIVITY_LOW',
                'prefixPaddingMs': 80,
                'silenceDurationMs': 600,
            },
        },
        'models': {
            'realtimeModel': 'gemini-live',
            'textFallbackModel': 'gemini-text',
            'summaryModel': 'gemini-summary',
        },
        'limits': {
            'maxSessionDurationSeconds': 480,
            'maxConcurrentSessions': 3,
            'dailySessionLimit': 200,
            'monthlyUsageBudget': 25,
        },
        'behavior': {
            'strictBehaviorEnabled': True,
            'supportedTopics': ['billing'],
            'forbiddenTopics': ['trivia'],
            'refusalTone': 'professional',
            'customInstructions': '',
        },
        'adapters': {
            'enabledAdapters': ['faq_search'],
        },
    }

    try:
        ImportSiteSettingsRequest.model_validate(payload)
        assert False, 'Expected refusal tone validation error'
    except Exception:
        assert True


def test_update_request_accepts_supported_refusal_tone():
    payload = UpdateSiteSettingsRequest.model_validate(
        {
            'displayName': 'Demo Site',
            'allowedOrigins': ['http://localhost:3000'],
            'widget': {
                'title': 'Support',
                'welcomeMessage': 'Hello',
                'defaultMode': 'text',
                'voiceEnabled': False,
                'textEnabled': True,
                'theme': 'sand',
                'countdownWarningSeconds': 45,
                'vadConfig': {
                    'disabled': True,
                    'startOfSpeechSensitivity': 'START_SENSITIVITY_LOW',
                    'endOfSpeechSensitivity': 'END_SENSITIVITY_HIGH',
                    'prefixPaddingMs': 80,
                    'silenceDurationMs': 700,
                },
            },
            'models': {
                'realtimeModel': 'gemini-live',
                'textFallbackModel': 'gemini-text',
                'summaryModel': 'gemini-summary',
            },
            'limits': {
                'maxSessionDurationSeconds': 480,
                'maxConcurrentSessions': 3,
                'dailySessionLimit': 200,
                'monthlyUsageBudget': 25,
            },
            'behavior': {
                'strictBehaviorEnabled': False,
                'supportedTopics': ['billing'],
                'forbiddenTopics': ['trivia'],
                'refusalTone': 'brief',
                'customInstructions': 'Stay short.',
            },
            'adapters': {
                'enabledAdapters': ['faq_search'],
            },
        }
    )
    assert payload.behavior.refusal_tone == 'brief'
