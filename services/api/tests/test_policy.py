from pathlib import Path
from types import SimpleNamespace

from app.policy import load_policy


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
