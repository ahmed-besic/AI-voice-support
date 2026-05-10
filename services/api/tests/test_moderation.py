from types import SimpleNamespace

import pytest

from app.moderation import ClassificationResult, ScopeDecision, moderate_user_turn
from app.policy import StrictBehaviorPolicy


def make_policy() -> StrictBehaviorPolicy:
    return StrictBehaviorPolicy.model_validate(
        {
            'supported_topics': ['billing'],
            'forbidden_topics': ['general trivia'],
            'ambiguous': {
                'action': 'log_only',
                'strike': False,
                'emit_warning': False,
                'review_tag': 'ambiguous_scope',
            },
            'refusal_message': 'Support topics only.',
            'warning_messages': {
                'first': 'First warning.',
                'second': 'Second warning.',
            },
            'termination_message': 'Session terminated.',
            'allowed_tools': ['faq_search'],
            'max_strikes': 3,
        }
    )


@pytest.mark.asyncio
async def test_out_of_scope_turn_adds_strike_and_warning(monkeypatch):
    state = SimpleNamespace(
        strike_count=0,
        terminated=False,
        last_decision=None,
        last_reason_code=None,
        last_review_tag=None,
    )
    events: list[tuple[str, dict]] = []
    stream_events: list[tuple[str, dict]] = []

    async def fake_get_event(_db, _turn_key):
        return None

    async def fake_get_state(_db, _session_id):
        return state

    async def fake_add_event(_db, **kwargs):
        events.append((kwargs['event_type'], kwargs['payload']))
        return None

    async def fake_commit(_db):
        return None

    async def fake_publish(session_id, event_type, payload):
        stream_events.append((event_type, payload))

    async def fake_classify(**_kwargs):
        return ClassificationResult(
            decision=ScopeDecision.OUT_OF_SCOPE,
            reason_code='general_trivia',
            explanation='Clearly unrelated trivia.',
        )

    monkeypatch.setattr('app.moderation.get_moderation_event_by_turn_key', fake_get_event)
    monkeypatch.setattr('app.moderation.get_or_create_moderation_state', fake_get_state)
    monkeypatch.setattr('app.moderation.add_moderation_event', fake_add_event)
    monkeypatch.setattr('app.moderation.commit', fake_commit)
    monkeypatch.setattr('app.moderation.classify_user_intent', fake_classify)
    monkeypatch.setattr('app.moderation.control_stream_broker.publish', fake_publish)

    result = await moderate_user_turn(
        object(),
        session_id='session-1',
        source='voice_input_transcription',
        sequence=1,
        text='What is the height of the Eiffel Tower?',
        company_name='Demo Site',
        model='gemini-2.5-flash',
        api_key='secret',
        policy=make_policy(),
    )

    assert result.current_strike_count == 1
    assert result.terminated is False
    assert result.classification == 'OUT_OF_SCOPE'
    assert result.policy_event is not None
    assert result.policy_event.type == 'policy_strike'
    assert state.strike_count == 1
    assert events[0][0] == 'turn_evaluated'
    assert stream_events[0][0] == 'policy_strike'


@pytest.mark.asyncio
async def test_third_out_of_scope_turn_terminates(monkeypatch):
    state = SimpleNamespace(
        strike_count=2,
        terminated=False,
        last_decision=None,
        last_reason_code=None,
        last_review_tag=None,
    )

    async def fake_get_event(_db, _turn_key):
        return None

    async def fake_get_state(_db, _session_id):
        return state

    async def fake_add_event(_db, **kwargs):
        return None

    async def fake_commit(_db):
        return None

    async def fake_publish(_session_id, _event_type, _payload):
        return None

    async def fake_classify(**_kwargs):
        return ClassificationResult(
            decision=ScopeDecision.OUT_OF_SCOPE,
            reason_code='general_trivia',
            explanation='Clearly unrelated trivia.',
        )

    monkeypatch.setattr('app.moderation.get_moderation_event_by_turn_key', fake_get_event)
    monkeypatch.setattr('app.moderation.get_or_create_moderation_state', fake_get_state)
    monkeypatch.setattr('app.moderation.add_moderation_event', fake_add_event)
    monkeypatch.setattr('app.moderation.commit', fake_commit)
    monkeypatch.setattr('app.moderation.classify_user_intent', fake_classify)
    monkeypatch.setattr('app.moderation.control_stream_broker.publish', fake_publish)

    result = await moderate_user_turn(
        object(),
        session_id='session-1',
        source='voice_input_transcription',
        sequence=3,
        text='Still asking trivia.',
        company_name='Demo Site',
        model='gemini-2.5-flash',
        api_key='secret',
        policy=make_policy(),
    )

    assert result.current_strike_count == 3
    assert result.terminated is True
    assert result.policy_event is not None
    assert result.policy_event.type == 'policy_terminated'
    assert state.terminated is True


@pytest.mark.asyncio
async def test_ambiguous_turn_logs_without_strike_by_default(monkeypatch):
    state = SimpleNamespace(
        strike_count=0,
        terminated=False,
        last_decision=None,
        last_reason_code=None,
        last_review_tag=None,
    )

    async def fake_get_event(_db, _turn_key):
        return None

    async def fake_get_state(_db, _session_id):
        return state

    async def fake_add_event(_db, **kwargs):
        return None

    async def fake_commit(_db):
        return None

    async def fake_publish(_session_id, _event_type, _payload):
        return None

    async def fake_classify(**_kwargs):
        return ClassificationResult(
            decision=ScopeDecision.AMBIGUOUS,
            reason_code='ambiguous_scope',
            explanation='Could be support related but lacks context.',
        )

    monkeypatch.setattr('app.moderation.get_moderation_event_by_turn_key', fake_get_event)
    monkeypatch.setattr('app.moderation.get_or_create_moderation_state', fake_get_state)
    monkeypatch.setattr('app.moderation.add_moderation_event', fake_add_event)
    monkeypatch.setattr('app.moderation.commit', fake_commit)
    monkeypatch.setattr('app.moderation.classify_user_intent', fake_classify)
    monkeypatch.setattr('app.moderation.control_stream_broker.publish', fake_publish)

    result = await moderate_user_turn(
        object(),
        session_id='session-1',
        source='voice_input_transcription',
        sequence=2,
        text='Can you help with that issue?',
        company_name='Demo Site',
        model='gemini-2.5-flash',
        api_key='secret',
        policy=make_policy(),
    )

    assert result.current_strike_count == 0
    assert result.terminated is False
    assert result.policy_event is None
    assert state.last_review_tag == 'ambiguous_scope'
