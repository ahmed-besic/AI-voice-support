from pathlib import Path
from types import SimpleNamespace

from app.policy import build_live_system_instruction, build_text_system_instruction, load_policy
from app.site_settings import SiteBehaviorSettings


def test_load_policy_merges_override(tmp_path: Path):
    default_path = tmp_path / 'default.yaml'
    override_path = tmp_path / 'override.yaml'

    default_path.write_text(
        '\n'.join(
            [
                'supported_topics:',
                '  - billing',
                'ambiguous:',
                '  action: log_only',
                '  strike: false',
                '  emit_warning: false',
                '  review_tag: ambiguous_scope',
                'refusal_message: default refusal',
                'warning_messages:',
                '  first: first warning',
                '  second: second warning',
                'termination_message: stop',
                'allowed_tools:',
                '  - faq_search',
                'max_strikes: 3',
            ]
        )
    )
    override_path.write_text(
        '\n'.join(
            [
                'supported_topics:',
                '  - billing',
                '  - account access',
                'ambiguous:',
                '  action: soft_warning',
                '  emit_warning: true',
                'text_prompt_addition: extra text guidance',
            ]
        )
    )

    policy = load_policy(
        SimpleNamespace(
            strict_policy_path=str(default_path),
            strict_policy_override_path=str(override_path),
        )
    )

    assert policy.supported_topics == ['billing', 'account access']
    assert policy.ambiguous.action == 'soft_warning'
    assert policy.ambiguous.strike is False
    assert policy.text_prompt_addition == 'extra text guidance'


def test_system_instruction_includes_site_behavior_overrides(tmp_path: Path):
    default_path = tmp_path / 'default.yaml'
    default_path.write_text(
        '\n'.join(
            [
                'supported_topics:',
                '  - billing',
                'forbidden_topics:',
                '  - trivia',
                'ambiguous:',
                '  action: log_only',
                '  strike: false',
                '  emit_warning: false',
                '  review_tag: ambiguous_scope',
                'refusal_message: default refusal',
                'warning_messages:',
                '  first: first warning',
                '  second: second warning',
                'termination_message: stop',
                'allowed_tools:',
                '  - faq_search',
                'voice_prompt_addition: stay helpful',
                'text_prompt_addition: use knowledge',
                'max_strikes: 3',
            ]
        )
    )
    policy = load_policy(
        SimpleNamespace(
            strict_policy_path=str(default_path),
            strict_policy_override_path=None,
        )
    )
    behavior = SiteBehaviorSettings(
        supportedTopics=['refunds', 'password resets'],
        forbiddenTopics=['sports'],
        refusalTone='firm',
        customInstructions='Mention warranty limits when relevant.',
    )

    live_instruction = build_live_system_instruction(
        company_name='Acme',
        policy=policy,
        allowed_tools=['faq_search'],
        behavior=behavior,
    )
    text_instruction = build_text_system_instruction(
        company_name='Acme',
        policy=policy,
        behavior=behavior,
    )

    assert 'refunds' in live_instruction
    assert 'sports' in live_instruction
    assert 'firm, direct, and professional' in live_instruction
    assert 'Mention warranty limits when relevant.' in live_instruction
    assert 'refunds' in text_instruction
    assert 'sports' in text_instruction
