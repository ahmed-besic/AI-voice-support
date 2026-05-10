def estimate_session_cost(site, usage: dict) -> float:
    input_tokens = usage.get('input_tokens', 0)
    output_tokens = usage.get('output_tokens', 0)
    audio_input_seconds = usage.get('audio_input_seconds', 0.0)
    audio_output_seconds = usage.get('audio_output_seconds', 0.0)

    token_cost = (input_tokens / 1000) * site.input_token_price_per_1k
    token_cost += (output_tokens / 1000) * site.output_token_price_per_1k
    audio_cost = audio_input_seconds * site.audio_input_price_per_second
    audio_cost += audio_output_seconds * site.audio_output_price_per_second
    return round(token_cost + audio_cost, 6)


def clamp_session_duration(seconds: int) -> int:
    return max(60, min(seconds, 900))
