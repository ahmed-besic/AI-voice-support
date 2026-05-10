from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from baml_py import ClientRegistry

from .baml_client.baml_client.async_client import b as baml_client
from .control_stream import control_stream_broker
from .policy import StrictBehaviorPolicy
from .repository import (
    add_moderation_event,
    commit,
    get_moderation_event_by_turn_key,
    get_or_create_moderation_state,
)
from .schemas import PolicyControlEvent, UserTurnResponse


class ScopeDecision(str, Enum):
    IN_SCOPE = 'IN_SCOPE'
    OUT_OF_SCOPE = 'OUT_OF_SCOPE'
    AMBIGUOUS = 'AMBIGUOUS'


@dataclass
class ClassificationResult:
    decision: ScopeDecision
    reason_code: str
    explanation: str


def build_turn_key(session_id: str, source: str, sequence: int) -> str:
    return f'{session_id}:{source}:{sequence}'


async def classify_user_intent(
    *,
    api_key: str,
    model: str,
    company_name: str,
    policy: StrictBehaviorPolicy,
    message: str,
) -> ClassificationResult:
    registry = ClientRegistry()
    registry.add_llm_client(
        name='PolicyClient',
        provider='google-ai',
        options={
            'model': model,
            'api_key': api_key,
            'temperature': 0,
        },
    )
    registry.set_primary('PolicyClient')
    result = await baml_client.ScopeCheck(
        company_name=company_name,
        supported_topics=policy.supported_topics,
        forbidden_topics=policy.forbidden_topics,
        message=message,
        baml_options={'client_registry': registry},
    )
    return ClassificationResult(
        decision=ScopeDecision(result.decision.value),
        reason_code=result.reason_code.strip() or 'unspecified',
        explanation=result.explanation.strip() or 'No explanation provided.',
    )


async def moderate_user_turn(
    db,
    *,
    session_id: str,
    source: str,
    sequence: int,
    text: str,
    company_name: str,
    model: str,
    api_key: str,
    policy: StrictBehaviorPolicy,
) -> UserTurnResponse:
    turn_key = build_turn_key(session_id, source, sequence)
    existing_event = await get_moderation_event_by_turn_key(db, turn_key)
    if existing_event:
        return UserTurnResponse.model_validate(existing_event.payload)

    state = await get_or_create_moderation_state(db, session_id)
    if state.terminated:
        policy_event = PolicyControlEvent(
            type='policy_terminated',
            message=policy.termination_message,
            currentStrikeCount=state.strike_count,
            maxStrikes=policy.max_strikes,
            terminated=True,
            classification=state.last_decision,
            reasonCode=state.last_reason_code,
            reviewTag=state.last_review_tag,
        )
        response = UserTurnResponse(
            accepted=False,
            currentStrikeCount=state.strike_count,
            terminated=True,
            classification=state.last_decision,
            reasonCode=state.last_reason_code,
            policyEvent=policy_event,
        )
        return response

    classification = await classify_user_intent(
        api_key=api_key,
        model=model,
        company_name=company_name,
        policy=policy,
        message=text,
    )

    state.last_decision = classification.decision.value
    state.last_reason_code = classification.reason_code
    state.last_review_tag = None

    policy_event: PolicyControlEvent | None = None
    review_tag: str | None = None
    event_type = 'turn_evaluated'

    if classification.decision is ScopeDecision.OUT_OF_SCOPE:
        state.strike_count += 1
        event_type = 'policy_strike'
        terminated = state.strike_count >= policy.max_strikes
        if terminated:
            state.terminated = True
            policy_event = PolicyControlEvent(
                type='policy_terminated',
                message=policy.termination_message,
                currentStrikeCount=state.strike_count,
                maxStrikes=policy.max_strikes,
                terminated=True,
                classification=classification.decision.value,
                reasonCode=classification.reason_code,
            )
        else:
            warning_message = (
                policy.warning_messages.first
                if state.strike_count == 1
                else policy.warning_messages.second
            )
            policy_event = PolicyControlEvent(
                type='policy_strike',
                message=warning_message,
                currentStrikeCount=state.strike_count,
                maxStrikes=policy.max_strikes,
                terminated=False,
                classification=classification.decision.value,
                reasonCode=classification.reason_code,
            )
    elif classification.decision is ScopeDecision.AMBIGUOUS:
        review_tag = policy.ambiguous.review_tag
        state.last_review_tag = review_tag
        if policy.ambiguous.action == 'soft_warning':
            policy_event = PolicyControlEvent(
                type='policy_warning',
                message=policy.warning_messages.first,
                currentStrikeCount=state.strike_count,
                maxStrikes=policy.max_strikes,
                terminated=False,
                classification=classification.decision.value,
                reasonCode=classification.reason_code,
                reviewTag=review_tag,
            )
        elif policy.ambiguous.action == 'count_strike':
            state.strike_count += 1
            terminated = state.strike_count >= policy.max_strikes
            if terminated:
                state.terminated = True
                policy_event = PolicyControlEvent(
                    type='policy_terminated',
                    message=policy.termination_message,
                    currentStrikeCount=state.strike_count,
                    maxStrikes=policy.max_strikes,
                    terminated=True,
                    classification=classification.decision.value,
                    reasonCode=classification.reason_code,
                    reviewTag=review_tag,
                )
            else:
                policy_event = PolicyControlEvent(
                    type='policy_strike',
                    message=policy.warning_messages.first,
                    currentStrikeCount=state.strike_count,
                    maxStrikes=policy.max_strikes,
                    terminated=False,
                    classification=classification.decision.value,
                    reasonCode=classification.reason_code,
                    reviewTag=review_tag,
                )

    response = UserTurnResponse(
        accepted=True,
        currentStrikeCount=state.strike_count,
        terminated=state.terminated,
        classification=classification.decision.value,
        reasonCode=classification.reason_code,
        policyEvent=policy_event,
    )

    await add_moderation_event(
        db,
        session_id=session_id,
        event_type='turn_evaluated',
        strike_count=state.strike_count,
        payload=response.model_dump(mode='json', by_alias=True),
        turn_key=turn_key,
        source=source,
        sequence=sequence,
        classification=classification.decision.value,
        reason_code=classification.reason_code,
    )

    if policy_event:
        await add_moderation_event(
            db,
            session_id=session_id,
            event_type=policy_event.type,
            strike_count=state.strike_count,
            payload=policy_event.model_dump(mode='json', by_alias=True),
            source=source,
            sequence=sequence,
            classification=classification.decision.value,
            reason_code=classification.reason_code,
        )

    await commit(db)

    if policy_event:
        await control_stream_broker.publish(
            session_id,
            policy_event.type,
            policy_event.model_dump(mode='json', by_alias=True),
        )
    return response
