from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from google import genai
from google.genai import types

from .schemas import VADConfig


async def create_ephemeral_token(
    *,
    api_key: str,
    realtime_model: str,
    max_session_duration_seconds: int,
    vad_config: VADConfig,
    tool_declarations: list[dict[str, Any]],
    system_instruction: str,
) -> str:
    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1alpha'})
    now = datetime.now(timezone.utc)
    live_config = types.LiveConnectConfig(
        response_modalities=['AUDIO'],
        input_audio_transcription={},
        output_audio_transcription={},
        realtime_input_config=types.RealtimeInputConfig(
            activity_handling='START_OF_ACTIVITY_INTERRUPTS',
            automatic_activity_detection=types.AutomaticActivityDetection(
                disabled=vad_config.disabled,
                start_of_speech_sensitivity=vad_config.start_of_speech_sensitivity,
                end_of_speech_sensitivity=vad_config.end_of_speech_sensitivity,
                prefix_padding_ms=vad_config.prefix_padding_ms,
                silence_duration_ms=vad_config.silence_duration_ms,
            )
        ),
        system_instruction=system_instruction,
        tools=[types.Tool(function_declarations=tool_declarations)] if tool_declarations else [],
        session_resumption={},
        max_output_tokens=2048,
    )
    token = client.auth_tokens.create(
        config=types.CreateAuthTokenConfig(
            uses=1,
            expire_time=now + timedelta(minutes=30),
            new_session_expire_time=now + timedelta(minutes=1),
            live_ephemeral_parameters=types.LiveEphemeralParameters(
                model=realtime_model,
                config=live_config,
            ),
        )
    )
    return token.name


async def generate_text_response(*, api_key: str, model: str, system_instruction: str, prompt: str) -> str:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config={'system_instruction': system_instruction},
    )
    return getattr(response, 'text', '') or 'I could not generate a response.'
