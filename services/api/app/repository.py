from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import and_, delete, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .costs import clamp_session_duration, estimate_session_cost
from .models import (
    AdapterBinding,
    ConversationState,
    KnowledgeEntry,
    ModerationEvent,
    ModerationState,
    SessionMemory,
    Site,
    ToolEvent,
    Transcript,
    Turn,
    VoiceSession,
)
from .schemas import ConnectionStatePayload, SessionEndPayload, TranscriptPayload, UsagePayload
from .security import encrypt_secret
from .site_settings import (
    ImportSiteSettingsRequest,
    SiteConfigFile,
    UpdateSiteSettingsRequest,
    apply_config_to_site,
    ensure_site_config_file,
)

FAQ_PATH = Path(__file__).resolve().parent.parent / 'data' / 'faq.json'


async def seed_demo_site(db: AsyncSession, settings) -> None:
    seed_config = ensure_site_config_file(settings)
    existing = await db.get(Site, settings.demo_site_id)
    if existing:
        await seed_site_knowledge_from_entries(
            db,
            site_id=settings.demo_site_id,
            entries=load_seed_faq_entries(),
        )
        return
    demo_site = Site(
        id=settings.demo_site_id,
        display_name=settings.demo_site_name,
        allowed_origins=settings.demo_allowed_origin_list,
        max_session_duration_seconds=clamp_session_duration(settings.demo_max_session_duration_seconds),
        max_concurrent_sessions=3,
        daily_session_limit=200,
        monthly_usage_budget=settings.demo_monthly_budget,
        summary_model=settings.google_summary_model,
        text_fallback_model=settings.google_text_model,
        realtime_model=settings.google_realtime_model,
        vad_preset={},
        enabled_adapters=[],
        site_config={},
        google_api_key_encrypted=encrypt_secret(settings.default_google_api_key) if settings.default_google_api_key else None,
    )
    apply_config_to_site(demo_site, seed_config)
    demo_site.max_session_duration_seconds = clamp_session_duration(demo_site.max_session_duration_seconds)
    db.add(demo_site)
    await db.flush()
    db.add_all(
        [
            AdapterBinding(site_id=settings.demo_site_id, adapter_name='faq_search', adapter_type='knowledge'),
            AdapterBinding(site_id=settings.demo_site_id, adapter_name='create_support_ticket', adapter_type='tool'),
        ]
    )
    await db.commit()
    await seed_site_knowledge_from_entries(
        db,
        site_id=settings.demo_site_id,
        entries=load_seed_faq_entries(),
    )


async def prune_stale_sessions(db: AsyncSession, *, site_id: str | None = None) -> int:
    now = datetime.now(timezone.utc)
    ended_before = now - timedelta(minutes=15)
    conditions = [
        or_(
            VoiceSession.expires_at <= now,
            and_(
                VoiceSession.status.in_(['completed', 'closed', 'error', 'fallback_text']),
                VoiceSession.updated_at <= ended_before,
            ),
        )
    ]
    if site_id:
        conditions.append(VoiceSession.site_id == site_id)
    result = await db.execute(delete(VoiceSession).where(and_(*conditions)))
    await db.commit()
    return int(result.rowcount or 0)


def load_seed_faq_entries() -> list[dict]:
    return json.loads(FAQ_PATH.read_text())


async def update_site_settings(db: AsyncSession, site: Site, payload: UpdateSiteSettingsRequest) -> Site:
    apply_config_to_site(site, payload)
    site.max_session_duration_seconds = clamp_session_duration(site.max_session_duration_seconds)
    await db.commit()
    await db.refresh(site)
    return site


async def import_site_settings(db: AsyncSession, site: Site | None, payload: ImportSiteSettingsRequest) -> Site:
    target = site or Site(
        id=payload.site_id,
        display_name=payload.display_name,
        allowed_origins=payload.allowed_origins,
        max_session_duration_seconds=payload.limits.max_session_duration_seconds,
        max_concurrent_sessions=payload.limits.max_concurrent_sessions,
        daily_session_limit=payload.limits.daily_session_limit,
        monthly_usage_budget=payload.limits.monthly_usage_budget,
        summary_model=payload.models.summary_model,
        text_fallback_model=payload.models.text_fallback_model,
        realtime_model=payload.models.realtime_model,
        vad_preset={},
        enabled_adapters=[],
        site_config={},
    )
    apply_config_to_site(target, payload)
    target.max_session_duration_seconds = clamp_session_duration(target.max_session_duration_seconds)
    if site is None:
        db.add(target)
        await db.flush()
    await db.commit()
    await db.refresh(target)
    return target


async def get_site(db: AsyncSession, site_id: str) -> Site | None:
    return await db.get(Site, site_id)


async def list_knowledge_entries(db: AsyncSession, site_id: str) -> list[KnowledgeEntry]:
    rows = (
        await db.scalars(select(KnowledgeEntry).where(KnowledgeEntry.site_id == site_id).order_by(KnowledgeEntry.created_at.asc()))
    ).all()
    return list(rows)


async def replace_site_knowledge(db: AsyncSession, *, site_id: str, entries: list[dict]) -> list[KnowledgeEntry]:
    existing = (await db.scalars(select(KnowledgeEntry).where(KnowledgeEntry.site_id == site_id))).all()
    for row in existing:
        await db.delete(row)
    for entry in entries:
        db.add(
            KnowledgeEntry(
                site_id=site_id,
                title=entry['title'],
                content=entry['content'],
                source=entry.get('source'),
                metadata_json=entry.get('metadata') or {},
            )
        )
    await db.commit()
    return await list_knowledge_entries(db, site_id)


async def seed_site_knowledge_from_entries(db: AsyncSession, *, site_id: str, entries: list[dict]) -> None:
    existing_count = await db.scalar(
        select(func.count()).select_from(KnowledgeEntry).where(KnowledgeEntry.site_id == site_id)
    )
    if existing_count:
        return
    for entry in entries:
        db.add(
            KnowledgeEntry(
                site_id=site_id,
                title=entry['title'],
                content=entry['content'],
                source=entry.get('source'),
                metadata_json=entry.get('metadata') or {},
            )
        )
    await db.commit()


async def get_active_session_count(db: AsyncSession, site_id: str) -> int:
    await prune_stale_sessions(db, site_id=site_id)
    now = datetime.now(timezone.utc)
    result = await db.scalar(
        select(func.count()).select_from(VoiceSession).where(
            and_(
                VoiceSession.site_id == site_id,
                VoiceSession.status.in_(['bootstrapped', 'active', 'fallback_text']),
                VoiceSession.expires_at > now,
            )
        )
    )
    return int(result or 0)


async def get_daily_session_count(db: AsyncSession, site_id: str) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    result = await db.scalar(
        select(func.count()).select_from(VoiceSession).where(
            and_(VoiceSession.site_id == site_id, VoiceSession.created_at >= since)
        )
    )
    return int(result or 0)


async def get_monthly_estimated_cost(db: AsyncSession, site_id: str) -> float:
    since = datetime.now(timezone.utc) - timedelta(days=30)
    result = await db.scalar(
        select(func.coalesce(func.sum(VoiceSession.estimated_cost), 0.0)).where(
            and_(VoiceSession.site_id == site_id, VoiceSession.created_at >= since)
        )
    )
    return float(result or 0.0)


async def create_session(
    db: AsyncSession,
    *,
    site: Site,
    origin: str,
    mode: str,
    customer_identity: dict | None,
) -> VoiceSession:
    duration = clamp_session_duration(site.max_session_duration_seconds)
    session = VoiceSession(
        site_id=site.id,
        origin=origin,
        mode=mode,
        customer_identity=customer_identity,
        max_session_duration_seconds=duration,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=duration),
        status='bootstrapped',
    )
    db.add(session)
    await db.flush()
    db.add(ConversationState(session_id=session.id, state='bootstrapped', state_payload={'mode': mode}))
    await db.commit()
    await db.refresh(session)
    return session


async def add_transcript_event(db: AsyncSession, payload: TranscriptPayload) -> None:
    transcript = Transcript(
        session_id=payload.session_id,
        role=payload.role,
        text=payload.text,
        final=payload.final,
        sequence=payload.sequence,
        source=payload.source,
        raw_payload=payload.model_dump(mode='json', by_alias=True),
    )
    db.add(transcript)
    if payload.final:
        db.add(
            Turn(
                session_id=payload.session_id,
                role=payload.role,
                text=payload.text,
                final=True,
                sequence=payload.sequence,
                source=payload.source,
            )
        )
    await db.commit()


async def add_usage_event(db: AsyncSession, site: Site, payload: UsagePayload) -> None:
    session = await db.get(VoiceSession, payload.session_id)
    if not session:
        return
    usage = session.usage_snapshot or {}
    usage['input_tokens'] = usage.get('input_tokens', 0) + payload.input_tokens
    usage['output_tokens'] = usage.get('output_tokens', 0) + payload.output_tokens
    usage['audio_input_seconds'] = usage.get('audio_input_seconds', 0.0) + payload.audio_input_seconds
    usage['audio_output_seconds'] = usage.get('audio_output_seconds', 0.0) + payload.audio_output_seconds
    session.usage_snapshot = usage
    session.estimated_cost = estimate_session_cost(site, usage)
    session.status = 'active'
    await db.commit()


async def mark_session_state(db: AsyncSession, payload: ConnectionStatePayload | SessionEndPayload) -> None:
    session = await db.get(VoiceSession, payload.session_id)
    if not session:
        return
    if isinstance(payload, ConnectionStatePayload):
        session.status = 'active' if payload.state == 'open' else payload.state
    else:
        mapping = {
            'completed': 'completed',
            'max_duration_reached': 'fallback_text',
            'fallback_to_text': 'fallback_text',
            'socket_error': 'error',
            'user_closed': 'closed',
        }
        session.status = mapping[payload.reason]
    await db.commit()


async def add_tool_event(
    db: AsyncSession,
    *,
    session_id: str,
    tool_name: str,
    call_id: str,
    request_payload: dict,
    response_payload: dict,
    is_error: bool,
) -> None:
    db.add(
        ToolEvent(
            session_id=session_id,
            tool_name=tool_name,
            call_id=call_id,
            request_payload=request_payload,
            response_payload=response_payload,
            is_error=is_error,
        )
    )
    await db.commit()


async def get_recent_transcript_text(db: AsyncSession, session_id: str) -> str:
    rows = (
        await db.scalars(
            select(Turn).where(Turn.session_id == session_id, Turn.final.is_(True)).order_by(Turn.sequence.asc(), Turn.created_at.asc())
        )
    ).all()
    return '\n'.join(f"{row.role}: {row.text}" for row in rows)


async def upsert_session_memory(db: AsyncSession, *, session_id: str, summary_text: str, summary_model: str) -> None:
    row = SessionMemory(session_id=session_id, summary_text=summary_text, summary_model=summary_model)
    db.add(row)
    await db.commit()


async def get_moderation_state(db: AsyncSession, session_id: str) -> ModerationState | None:
    result = await db.scalar(select(ModerationState).where(ModerationState.session_id == session_id))
    return result


async def get_or_create_moderation_state(db: AsyncSession, session_id: str) -> ModerationState:
    row = await get_moderation_state(db, session_id)
    if row:
        return row
    row = ModerationState(session_id=session_id)
    db.add(row)
    await db.flush()
    return row


async def get_moderation_event_by_turn_key(db: AsyncSession, turn_key: str) -> ModerationEvent | None:
    return await db.scalar(select(ModerationEvent).where(ModerationEvent.turn_key == turn_key))


async def add_moderation_event(
    db: AsyncSession,
    *,
    session_id: str,
    event_type: str,
    strike_count: int,
    payload: dict,
    turn_key: str | None = None,
    source: str | None = None,
    sequence: int | None = None,
    classification: str | None = None,
    reason_code: str | None = None,
) -> ModerationEvent:
    row = ModerationEvent(
        session_id=session_id,
        event_type=event_type,
        turn_key=turn_key,
        source=source,
        sequence=sequence,
        classification=classification,
        reason_code=reason_code,
        strike_count=strike_count,
        payload=payload,
    )
    db.add(row)
    await db.flush()
    return row


async def commit(db: AsyncSession) -> None:
    await db.commit()


async def list_site_summaries(db: AsyncSession) -> list[Site]:
    rows = (await db.scalars(select(Site).order_by(Site.display_name.asc()))).all()
    return list(rows)


async def list_recent_sessions(db: AsyncSession, site_id: str) -> list[VoiceSession]:
    rows = (
        await db.scalars(
            select(VoiceSession).where(VoiceSession.site_id == site_id).order_by(desc(VoiceSession.created_at)).limit(25)
        )
    ).all()
    return list(rows)
