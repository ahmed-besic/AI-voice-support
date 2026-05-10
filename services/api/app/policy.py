from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from .config import Settings, get_settings
from .site_settings import SiteBehaviorSettings, RefusalTone


class AmbiguousHandlingPolicy(BaseModel):
    action: Literal['log_only', 'soft_warning', 'count_strike'] = 'log_only'
    strike: bool = False
    emit_warning: bool = False
    review_tag: str = 'ambiguous_scope'


class WarningMessages(BaseModel):
    first: str
    second: str


class StrictBehaviorPolicy(BaseModel):
    supported_topics: list[str] = Field(default_factory=list)
    forbidden_topics: list[str] = Field(default_factory=list)
    ambiguous: AmbiguousHandlingPolicy = Field(default_factory=AmbiguousHandlingPolicy)
    refusal_message: str
    warning_messages: WarningMessages
    termination_message: str
    allowed_tools: list[str] = Field(default_factory=list)
    voice_prompt_addition: str = ''
    text_prompt_addition: str = ''
    max_strikes: int = 3


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f'Policy file not found: {path}')
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError(f'Policy file must contain an object at the top level: {path}')
    return data


def load_policy(settings: Settings | None = None) -> StrictBehaviorPolicy:
    resolved_settings = settings or get_settings()
    default_path = Path(resolved_settings.strict_policy_path)
    default_data = _load_yaml_file(default_path)
    override_path = resolved_settings.strict_policy_override_path
    if override_path:
        override_data = _load_yaml_file(Path(override_path))
        default_data = _deep_merge(default_data, override_data)
    return StrictBehaviorPolicy.model_validate(default_data)


@lru_cache(maxsize=1)
def get_policy() -> StrictBehaviorPolicy:
    return load_policy()


def clear_policy_cache() -> None:
    get_policy.cache_clear()


def build_live_system_instruction(
    *,
    company_name: str,
    policy: StrictBehaviorPolicy,
    allowed_tools: list[str],
    behavior: SiteBehaviorSettings | None = None,
) -> str:
    resolved_behavior = behavior or SiteBehaviorSettings()
    supported_topics = '\n'.join(f'- {topic}' for topic in (resolved_behavior.supported_topics or policy.supported_topics)) or '- No supported topics configured.'
    forbidden_topics = '\n'.join(f'- {topic}' for topic in (resolved_behavior.forbidden_topics or policy.forbidden_topics)) or '- No forbidden topics configured.'
    tools = '\n'.join(f'- {tool}' for tool in allowed_tools) or '- No tools are allowed.'
    extra = f'\nAdditional guidance:\n{policy.voice_prompt_addition.strip()}' if policy.voice_prompt_addition.strip() else ''
    custom_instructions = resolved_behavior.custom_instructions.strip()
    if custom_instructions:
        extra += f'\nSite custom instructions:\n{custom_instructions}'
    return (
        f'You are the voice support assistant for {company_name}.\n'
        'Only help with company support topics.\n'
        'If the user asks for general trivia, unrelated conversation, or anything outside company support, refuse briefly.\n'
        f'Use this refusal style exactly in spirit: {policy.refusal_message}\n'
        f'Refusal tone: {_describe_refusal_tone(resolved_behavior.refusal_tone)}.\n'
        'Never answer unrelated trivia even if you know it.\n'
        'Do not invent policies or product details.\n'
        'Supported topics:\n'
        f'{supported_topics}\n'
        'Out-of-scope topics:\n'
        f'{forbidden_topics}\n'
        'Allowed tools:\n'
        f'{tools}'
        f'{extra}'
    )


def build_text_system_instruction(
    *,
    company_name: str,
    policy: StrictBehaviorPolicy,
    behavior: SiteBehaviorSettings | None = None,
) -> str:
    resolved_behavior = behavior or SiteBehaviorSettings()
    extra = f'\nAdditional guidance:\n{policy.text_prompt_addition.strip()}' if policy.text_prompt_addition.strip() else ''
    if resolved_behavior.custom_instructions.strip():
        extra += f'\nSite custom instructions:\n{resolved_behavior.custom_instructions.strip()}'
    supported_topics = '\n'.join(f'- {topic}' for topic in (resolved_behavior.supported_topics or policy.supported_topics)) or '- No supported topics configured.'
    forbidden_topics = '\n'.join(f'- {topic}' for topic in (resolved_behavior.forbidden_topics or policy.forbidden_topics)) or '- No forbidden topics configured.'
    return (
        f'You are a concise customer support assistant for {company_name}.\n'
        'Answer only within company support scope.\n'
        'Use provided knowledge context when relevant.\n'
        f'If the user is out of scope, refuse briefly using this style: {policy.refusal_message}\n'
        f'Refusal tone: {_describe_refusal_tone(resolved_behavior.refusal_tone)}.\n'
        'If you do not know, say so plainly.\n'
        'Supported topics:\n'
        f'{supported_topics}\n'
        'Out-of-scope topics:\n'
        f'{forbidden_topics}'
        f'{extra}'
    )


def filter_allowed_tools(enabled_tools: list[str], policy: StrictBehaviorPolicy) -> list[str]:
    if not policy.allowed_tools:
        return list(enabled_tools)
    allowed = set(policy.allowed_tools)
    return [tool for tool in enabled_tools if tool in allowed]


def _describe_refusal_tone(refusal_tone: RefusalTone) -> str:
    if refusal_tone == 'firm':
        return 'firm, direct, and professional'
    if refusal_tone == 'brief':
        return 'very brief and minimal'
    return 'polite, calm, and redirecting'
