from __future__ import annotations

import asyncio

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .adapters.registry import AdapterRegistry
from .config import Settings, get_settings
from .control_stream import control_stream_broker
from .database import SessionLocal, get_db_session, init_db
from .google_live import create_ephemeral_token, generate_text_response
from .moderation import ScopeDecision, moderate_user_turn
from .models import Site
from .policy import build_live_system_instruction, build_text_system_instruction, filter_allowed_tools, get_policy
from .repository import (
    add_tool_event,
    add_transcript_event,
    add_usage_event,
    create_session,
    get_active_session_count,
    get_daily_session_count,
    get_moderation_state,
    get_monthly_estimated_cost,
    get_recent_transcript_text,
    get_site,
    import_site_settings,
    list_knowledge_entries,
    list_recent_sessions,
    list_site_summaries,
    mark_session_state,
    prune_stale_sessions,
    replace_site_knowledge,
    seed_demo_site,
    update_site_settings,
    upsert_session_memory,
)
from .schemas import (
    ConnectionStatePayload,
    KnowledgeEntryResponse,
    KnowledgeImportRequest,
    PolicyControlEvent,
    SessionEndPayload,
    SessionSummaryResponse,
    SiteSummaryResponse,
    TextTurnRequest,
    TextTurnResponse,
    ToolExecutionRequest,
    ToolExecutionResponse,
    TranscriptPayload,
    UserTurnRequest,
    UserTurnResponse,
    UsagePayload,
    VoiceSessionBootstrap,
    VADConfig,
    WidgetEvent,
    WidgetPublicConfig,
    WidgetSessionConfig,
    WidgetSessionUI,
)
from .security import AuthError, create_session_jwt, decrypt_secret, validate_origin, verify_session_jwt
from .site_settings import (
    ImportSiteSettingsRequest,
    SiteBehaviorSettings,
    SiteConfigFile,
    SiteSettingsResponse,
    UpdateSiteSettingsRequest,
    build_api_key_status,
    export_site_config_json,
    load_site_config_file,
    site_to_config_file,
    site_to_settings_response,
)

settings = get_settings()
app = FastAPI(title='Voice Support API', version='0.1.0')
registry = AdapterRegistry()

@app.on_event('startup')
async def startup() -> None:
    await init_db()
    async for db in get_db_session():
        await seed_demo_site(db, settings)
        await prune_stale_sessions(db)
        break


async def is_origin_known(origin: str | None) -> bool:
    if not origin:
        return False
    normalized = origin.rstrip('/')
    async with SessionLocal() as session:
        rows = (await session.scalars(select(Site.allowed_origins))).all()
    allowed = {candidate.rstrip('/') for row in rows for candidate in row}
    return normalized in allowed


@app.middleware('http')
async def dynamic_cors(request: Request, call_next):
    origin = request.headers.get('origin')
    known_origin = await is_origin_known(origin)
    is_cors_managed_path = request.url.path.startswith('/widget/') or request.url.path.startswith('/admin/')
    if request.method == 'OPTIONS' and is_cors_managed_path:
        response = Response(status_code=204)
    else:
        response = await call_next(request)
    if known_origin and origin:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, Origin'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
        response.headers['Vary'] = 'Origin'
    return response


def get_vad_config(site) -> VADConfig:
    return VADConfig(**site.vad_preset)


def get_site_behavior_settings(site: Site) -> SiteBehaviorSettings:
    return SiteBehaviorSettings.model_validate((site.site_config or {}).get('behavior', {}))


def get_site_widget_settings(site: Site) -> dict:
    return (site.site_config or {}).get('widget', {})


def build_widget_public_config(site: Site) -> WidgetPublicConfig:
    widget_settings = get_site_widget_settings(site)
    behavior_settings = get_site_behavior_settings(site)
    return WidgetPublicConfig(
        defaultMode=widget_settings.get('defaultMode', 'voice'),
        voiceEnabled=bool(widget_settings.get('voiceEnabled', True)),
        textEnabled=bool(widget_settings.get('textEnabled', True)),
        theme=widget_settings.get('theme', 'graphite'),
        strictBehaviorEnabled=behavior_settings.strict_behavior_enabled,
        vadConfig=get_vad_config(site),
        ui=WidgetSessionUI(
            title=widget_settings.get('title', 'Support assistant'),
            welcomeMessage=widget_settings.get('welcomeMessage', 'How can I help you today?'),
            countdownWarningSeconds=widget_settings.get('countdownWarningSeconds', 60),
        ),
    )


async def require_site_and_origin(
    request: Request,
    bootstrap: VoiceSessionBootstrap,
    db: AsyncSession,
):
    site = await get_site(db, bootstrap.site_id)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Unknown site')
    try:
        origin = validate_origin(request.headers.get('origin'), site.allowed_origins)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return site, origin


async def require_session_token(
    authorization: str = Header(default=''),
) -> dict:
    if not authorization.startswith('Bearer '):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Missing bearer token')
    token = authorization.removeprefix('Bearer ').strip()
    try:
        return verify_session_jwt(token)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def verify_session_token_value(token: str) -> dict:
    try:
        return verify_session_jwt(token)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@app.get('/health')
async def health() -> dict[str, str]:
    return {'status': 'ok'}


def build_control_stream_url(request: Request, *, session_id: str, session_jwt: str) -> str:
    base = str(request.base_url).rstrip('/')
    return f'{base}/widget/sessions/{session_id}/control-stream?token={session_jwt}'


@app.post('/widget/bootstrap', response_model=WidgetSessionConfig)
async def widget_bootstrap(
    bootstrap: VoiceSessionBootstrap,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> WidgetSessionConfig:
    site, origin = await require_site_and_origin(request, bootstrap, db)
    policy = get_policy()
    widget_settings = get_site_widget_settings(site)
    behavior_settings = get_site_behavior_settings(site)
    allowed_adapter_names = filter_allowed_tools(site.enabled_adapters, policy)
    api_key = decrypt_secret(site.google_api_key_encrypted) or settings.default_google_api_key
    default_mode = widget_settings.get('defaultMode', 'voice')
    voice_enabled = bool(widget_settings.get('voiceEnabled', True))
    text_enabled = bool(widget_settings.get('textEnabled', True))
    if not voice_enabled and not text_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='Both voice and text modes are disabled for this site')

    requested_mode = bootstrap.requested_mode
    if requested_mode == 'voice' and not voice_enabled:
        if not text_enabled:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Voice mode is disabled for this site')
        requested_mode = 'text'
    if requested_mode == 'text' and not text_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Text mode is disabled for this site')

    if requested_mode == 'voice' and await get_active_session_count(db, site.id) >= site.max_concurrent_sessions:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail='Concurrent session limit reached')
    if await get_daily_session_count(db, site.id) >= site.daily_session_limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail='Daily session limit reached')
    if await get_monthly_estimated_cost(db, site.id) >= site.monthly_usage_budget:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail='Monthly budget reached')

    if requested_mode == 'text':
        ephemeral_token = 'text-only-session'
    elif not api_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='No Google API key is configured for this site')
    else:
        ephemeral_token = await create_ephemeral_token(
            api_key=api_key,
            realtime_model=site.realtime_model,
            max_session_duration_seconds=site.max_session_duration_seconds,
            vad_config=get_vad_config(site),
            tool_declarations=registry.list_live_tool_declarations(allowed_adapter_names),
            system_instruction=build_live_system_instruction(
                company_name=site.display_name,
                policy=policy,
                allowed_tools=allowed_adapter_names,
                behavior=behavior_settings,
            ),
        )

    session = await create_session(
        db,
        site=site,
        origin=origin,
        mode=requested_mode,
        customer_identity=bootstrap.customer.model_dump() if bootstrap.customer else None,
    )
    session_jwt = create_session_jwt(
        session_id=session.id,
        site_id=site.id,
        origin=origin,
        ttl_seconds=site.max_session_duration_seconds + 120,
    )
    return WidgetSessionConfig(
        sessionId=session.id,
        sessionJwt=session_jwt,
        ephemeralToken=ephemeral_token,
        realtimeModel=site.realtime_model,
        maxSessionDurationSeconds=site.max_session_duration_seconds,
        enabledTools=registry.list_tool_descriptors(allowed_adapter_names),
        textFallbackModel=site.text_fallback_model,
        textFallbackEnabled=text_enabled,
        defaultMode=default_mode,
        voiceEnabled=voice_enabled,
        textEnabled=text_enabled,
        theme=widget_settings.get('theme', 'graphite'),
        vadConfig=get_vad_config(site),
        strictBehaviorEnabled=behavior_settings.strict_behavior_enabled,
        controlStreamUrl=build_control_stream_url(request, session_id=session.id, session_jwt=session_jwt),
        strikePolicy={'maxStrikes': policy.max_strikes, 'ambiguousAction': policy.ambiguous.action},
        ui=WidgetSessionUI(
            title=widget_settings.get('title', 'Support assistant'),
            welcomeMessage=widget_settings.get('welcomeMessage', 'How can I help you today?'),
            countdownWarningSeconds=widget_settings.get('countdownWarningSeconds', 60),
        ),
    )


@app.get('/widget/sites/{site_id}/settings', response_model=WidgetPublicConfig)
async def widget_public_settings(
    site_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> WidgetPublicConfig:
    site = await get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Unknown site')
    try:
        validate_origin(request.headers.get('origin'), site.allowed_origins)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return build_widget_public_config(site)


@app.post('/widget/tools/execute', response_model=ToolExecutionResponse)
async def execute_tool(
    payload: ToolExecutionRequest,
    session_claims: dict = Depends(require_session_token),
    db: AsyncSession = Depends(get_db_session),
) -> ToolExecutionResponse:
    if session_claims['sub'] != payload.session_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Session mismatch')
    moderation_state = await get_moderation_state(db, payload.session_id)
    if moderation_state and moderation_state.terminated:
        return ToolExecutionResponse(
            callId=payload.call_id,
            toolName=payload.tool_name,
            output={'error': 'Session terminated by policy enforcement.'},
            isError=True,
        )
    adapter = registry.get(payload.tool_name)
    if not adapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Unknown tool')
    try:
        output = await adapter.execute(payload.args, session_id=payload.session_id, site_id=session_claims['site_id'])
        response = ToolExecutionResponse(callId=payload.call_id, toolName=payload.tool_name, output=output, isError=False)
        await add_tool_event(
            db,
            session_id=payload.session_id,
            tool_name=payload.tool_name,
            call_id=payload.call_id,
            request_payload=payload.model_dump(mode='json', by_alias=True),
            response_payload=response.model_dump(mode='json', by_alias=True),
            is_error=False,
        )
        return response
    except Exception as exc:  # pragma: no cover - protective logging path
        response = ToolExecutionResponse(callId=payload.call_id, toolName=payload.tool_name, output={'error': str(exc)}, isError=True)
        await add_tool_event(
            db,
            session_id=payload.session_id,
            tool_name=payload.tool_name,
            call_id=payload.call_id,
            request_payload=payload.model_dump(mode='json', by_alias=True),
            response_payload=response.model_dump(mode='json', by_alias=True),
            is_error=True,
        )
        return response


@app.post('/widget/sessions/{session_id}/turns', response_model=UserTurnResponse)
async def ingest_user_turn(
    session_id: str,
    payload: UserTurnRequest,
    session_claims: dict = Depends(require_session_token),
    db: AsyncSession = Depends(get_db_session),
) -> UserTurnResponse:
    if session_claims['sub'] != session_id or payload.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Session mismatch')
    site = await get_site(db, session_claims['site_id'])
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Unknown site')
    behavior_settings = get_site_behavior_settings(site)
    if not behavior_settings.strict_behavior_enabled:
        return UserTurnResponse(accepted=True, currentStrikeCount=0, terminated=False)
    api_key = decrypt_secret(site.google_api_key_encrypted) or settings.default_google_api_key
    if not api_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='No Google API key configured')
    policy = get_policy()
    return await moderate_user_turn(
        db,
        session_id=session_id,
        source=payload.source,
        sequence=payload.sequence,
        text=payload.text,
        company_name=site.display_name,
        model=site.text_fallback_model,
        api_key=api_key,
        policy=policy,
    )


@app.get('/widget/sessions/{session_id}/control-stream')
async def control_stream(
    session_id: str,
    token: str = Query(default=''),
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    session_claims = verify_session_token_value(token)
    if session_claims['sub'] != session_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Session mismatch')

    moderation_state = await get_moderation_state(db, session_id)
    policy = get_policy()
    initial_event = PolicyControlEvent(
        type='policy_state',
        message=None,
        currentStrikeCount=moderation_state.strike_count if moderation_state else 0,
        maxStrikes=policy.max_strikes,
        terminated=moderation_state.terminated if moderation_state else False,
        classification=moderation_state.last_decision if moderation_state else None,
        reasonCode=moderation_state.last_reason_code if moderation_state else None,
        reviewTag=moderation_state.last_review_tag if moderation_state else None,
    )

    async def event_generator():
        queue = await control_stream_broker.subscribe(session_id)
        try:
            yield f'event: policy_state\ndata: {initial_event.model_dump_json(by_alias=True)}\n\n'
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=15)
                    yield message
                except asyncio.TimeoutError:
                    yield ': keep-alive\n\n'
        finally:
            await control_stream_broker.unsubscribe(session_id, queue)

    return StreamingResponse(event_generator(), media_type='text/event-stream')


@app.post('/widget/events')
async def widget_event(
    event: WidgetEvent,
    session_claims: dict = Depends(require_session_token),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    session_id = event.payload.get('sessionId')
    if session_claims['sub'] != session_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Session mismatch')

    site = await get_site(db, session_claims['site_id'])
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Unknown site')

    if event.type == 'transcript':
        await add_transcript_event(db, TranscriptPayload(**event.payload))
    elif event.type == 'usage':
        await add_usage_event(db, site, UsagePayload(**event.payload))
    elif event.type == 'connection_state':
        await mark_session_state(db, ConnectionStatePayload(**event.payload))
    elif event.type == 'session_end':
        payload = SessionEndPayload(**event.payload)
        await mark_session_state(db, payload)
        transcript = await get_recent_transcript_text(db, payload.session_id)
        api_key = decrypt_secret(site.google_api_key_encrypted) or settings.default_google_api_key
        if transcript and api_key:
            summary = await generate_text_response(
                api_key=api_key,
                model=site.summary_model,
                system_instruction='Summarize the support session in 3 concise bullet points with decisions and next steps.',
                prompt=transcript,
            )
            await upsert_session_memory(db, session_id=payload.session_id, summary_text=summary, summary_model=site.summary_model)
    return {'status': 'ok'}


@app.post('/widget/text-turn', response_model=TextTurnResponse)
async def text_turn(
    payload: TextTurnRequest,
    session_claims: dict = Depends(require_session_token),
    db: AsyncSession = Depends(get_db_session),
) -> TextTurnResponse:
    if session_claims['sub'] != payload.session_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Session mismatch')
    site = await get_site(db, session_claims['site_id'])
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Unknown site')
    widget_settings = get_site_widget_settings(site)
    behavior_settings = get_site_behavior_settings(site)
    if not bool(widget_settings.get('textEnabled', True)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Text mode is disabled for this site')
    policy = get_policy()
    api_key = decrypt_secret(site.google_api_key_encrypted) or settings.default_google_api_key
    if not api_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='No Google API key configured')
    policy_event = None
    current_strike_count = 0
    terminated = False

    if behavior_settings.strict_behavior_enabled:
        moderation_state = await get_moderation_state(db, payload.session_id)
        if moderation_state and moderation_state.terminated:
            policy_event = PolicyControlEvent(
                type='policy_terminated',
                message=policy.termination_message,
                currentStrikeCount=moderation_state.strike_count,
                maxStrikes=policy.max_strikes,
                terminated=True,
                classification=moderation_state.last_decision,
                reasonCode=moderation_state.last_reason_code,
                reviewTag=moderation_state.last_review_tag,
            )
            return TextTurnResponse(
                sessionId=payload.session_id,
                text=policy.termination_message,
                currentStrikeCount=moderation_state.strike_count,
                terminated=True,
                policyEvent=policy_event,
            )

        moderation_result = await moderate_user_turn(
            db,
            session_id=payload.session_id,
            source='text_input',
            sequence=int(asyncio.get_running_loop().time() * 1000),
            text=payload.text,
            company_name=site.display_name,
            model=site.text_fallback_model,
            api_key=api_key,
            policy=policy,
        )
        policy_event = moderation_result.policy_event
        current_strike_count = moderation_result.current_strike_count
        terminated = moderation_result.terminated

        if moderation_result.classification == ScopeDecision.OUT_OF_SCOPE.value:
            response_text = policy.refusal_message
        elif moderation_result.classification == ScopeDecision.AMBIGUOUS.value and policy.ambiguous.action == 'count_strike':
            response_text = policy.refusal_message
        else:
            faq_hits = await registry.faq_adapter().search(payload.text, site.id)
            transcript = await get_recent_transcript_text(db, payload.session_id)
            context = '\n'.join(f"- {hit['title']}: {hit['content']}" for hit in faq_hits) or '- No FAQ results available.'
            response_text = await generate_text_response(
                api_key=api_key,
                model=site.text_fallback_model,
                system_instruction=build_text_system_instruction(
                    company_name=site.display_name,
                    policy=policy,
                    behavior=behavior_settings,
                ),
                prompt=f'Conversation so far:\n{transcript}\n\nFAQ context:\n{context}\n\nUser message:\n{payload.text}',
            )
    else:
        faq_hits = await registry.faq_adapter().search(payload.text, site.id)
        transcript = await get_recent_transcript_text(db, payload.session_id)
        context = '\n'.join(f"- {hit['title']}: {hit['content']}" for hit in faq_hits) or '- No FAQ results available.'
        response_text = await generate_text_response(
            api_key=api_key,
            model=site.text_fallback_model,
            system_instruction=build_text_system_instruction(
                company_name=site.display_name,
                policy=policy,
                behavior=behavior_settings,
            ),
            prompt=f'Conversation so far:\n{transcript}\n\nFAQ context:\n{context}\n\nUser message:\n{payload.text}',
        )
    await add_transcript_event(
        db,
        TranscriptPayload(
            sessionId=payload.session_id,
            role='assistant',
            text=response_text,
            final=True,
            sequence=999999,
            source='text_fallback',
        ),
    )
    return TextTurnResponse(
        sessionId=payload.session_id,
        text=response_text,
        currentStrikeCount=current_strike_count,
        terminated=terminated,
        policyEvent=policy_event,
    )


@app.get('/admin/sites', response_model=list[SiteSummaryResponse])
async def admin_sites(db: AsyncSession = Depends(get_db_session)) -> list[SiteSummaryResponse]:
    sites = await list_site_summaries(db)
    response: list[SiteSummaryResponse] = []
    for site in sites:
        response.append(
            SiteSummaryResponse(
                site_id=site.id,
                display_name=site.display_name,
                active_sessions=await get_active_session_count(db, site.id),
                daily_sessions=await get_daily_session_count(db, site.id),
                monthly_estimated_cost=await get_monthly_estimated_cost(db, site.id),
                monthly_budget=site.monthly_usage_budget,
            )
        )
    return response


@app.get('/admin/site/settings', response_model=SiteSettingsResponse)
async def admin_site_settings(db: AsyncSession = Depends(get_db_session)) -> SiteSettingsResponse:
    site = await get_site(db, settings.demo_site_id)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Unknown site')
    return site_to_settings_response(site, settings)


@app.put('/admin/site/settings', response_model=SiteSettingsResponse)
async def admin_update_site_settings(
    payload: UpdateSiteSettingsRequest,
    db: AsyncSession = Depends(get_db_session),
) -> SiteSettingsResponse:
    site = await get_site(db, settings.demo_site_id)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Unknown site')
    site = await update_site_settings(db, site, payload)
    return site_to_settings_response(site, settings)


@app.get('/admin/site/settings/export', response_model=SiteConfigFile)
async def admin_export_site_settings(db: AsyncSession = Depends(get_db_session)) -> SiteConfigFile:
    site = await get_site(db, settings.demo_site_id)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Unknown site')
    return site_to_config_file(site)


@app.post('/admin/site/settings/import', response_model=SiteSettingsResponse)
async def admin_import_site_settings(
    payload: ImportSiteSettingsRequest,
    db: AsyncSession = Depends(get_db_session),
) -> SiteSettingsResponse:
    if payload.site_id != settings.demo_site_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Imported siteId must match the configured default site')
    site = await get_site(db, settings.demo_site_id)
    imported = await import_site_settings(db, site, payload)
    return site_to_settings_response(imported, settings)


@app.get('/admin/sites/{site_id}/knowledge', response_model=list[KnowledgeEntryResponse])
async def admin_site_knowledge(site_id: str, db: AsyncSession = Depends(get_db_session)) -> list[KnowledgeEntryResponse]:
    site = await get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Unknown site')
    rows = await list_knowledge_entries(db, site_id)
    return [
        KnowledgeEntryResponse(
            id=row.id,
            site_id=row.site_id,
            title=row.title,
            content=row.content,
            source=row.source,
            metadata=row.metadata_json,
            created_at=row.created_at,
        )
        for row in rows
    ]


@app.post('/admin/sites/{site_id}/knowledge', response_model=list[KnowledgeEntryResponse])
async def admin_replace_site_knowledge(
    site_id: str,
    payload: KnowledgeImportRequest,
    db: AsyncSession = Depends(get_db_session),
) -> list[KnowledgeEntryResponse]:
    site = await get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Unknown site')
    rows = await replace_site_knowledge(
        db,
        site_id=site_id,
        entries=[entry.model_dump() for entry in payload.entries],
    )
    return [
        KnowledgeEntryResponse(
            id=row.id,
            site_id=row.site_id,
            title=row.title,
            content=row.content,
            source=row.source,
            metadata=row.metadata_json,
            created_at=row.created_at,
        )
        for row in rows
    ]


@app.get('/admin/sites/{site_id}/sessions', response_model=list[SessionSummaryResponse])
async def admin_site_sessions(site_id: str, db: AsyncSession = Depends(get_db_session)) -> list[SessionSummaryResponse]:
    rows = await list_recent_sessions(db, site_id)
    return [
        SessionSummaryResponse(
            id=row.id,
            status=row.status,
            mode=row.mode,
            estimated_cost=row.estimated_cost,
            created_at=row.created_at,
        )
        for row in rows
    ]
