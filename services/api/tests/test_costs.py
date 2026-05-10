from types import SimpleNamespace

from app.costs import clamp_session_duration, estimate_session_cost


def test_clamp_session_duration():
    assert clamp_session_duration(10) == 60
    assert clamp_session_duration(500) == 500
    assert clamp_session_duration(5000) == 900


def test_estimate_session_cost():
    site = SimpleNamespace(
        input_token_price_per_1k=0.002,
        output_token_price_per_1k=0.004,
        audio_input_price_per_second=0.01,
        audio_output_price_per_second=0.02,
    )
    cost = estimate_session_cost(
        site,
        {
            'input_tokens': 1500,
            'output_tokens': 500,
            'audio_input_seconds': 10,
            'audio_output_seconds': 5,
        },
    )
    assert cost == 0.205
