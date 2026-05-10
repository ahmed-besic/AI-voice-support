import uuid
from datetime import datetime, timezone
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Site(Base):
    __tablename__ = 'sites'

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255))
    allowed_origins: Mapped[list] = mapped_column(JSON, default=list)
    max_session_duration_seconds: Mapped[int] = mapped_column(Integer, default=480)
    max_concurrent_sessions: Mapped[int] = mapped_column(Integer, default=5)
    daily_session_limit: Mapped[int] = mapped_column(Integer, default=100)
    monthly_usage_budget: Mapped[float] = mapped_column(Float, default=25.0)
    summary_model: Mapped[str] = mapped_column(String(255), default='gemini-2.5-flash-lite')
    text_fallback_model: Mapped[str] = mapped_column(String(255), default='gemini-2.5-flash')
    realtime_model: Mapped[str] = mapped_column(String(255), default='gemini-3.1-flash-live-preview')
    vad_preset: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled_adapters: Mapped[list] = mapped_column(JSON, default=list)
    site_config: Mapped[dict] = mapped_column(JSON, default=dict)
    google_api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_token_price_per_1k: Mapped[float] = mapped_column(Float, default=0.0)
    output_token_price_per_1k: Mapped[float] = mapped_column(Float, default=0.0)
    audio_input_price_per_second: Mapped[float] = mapped_column(Float, default=0.0)
    audio_output_price_per_second: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AdapterBinding(Base):
    __tablename__ = 'adapter_bindings'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    site_id: Mapped[str] = mapped_column(ForeignKey('sites.id', ondelete='CASCADE'))
    adapter_name: Mapped[str] = mapped_column(String(255))
    adapter_type: Mapped[str] = mapped_column(String(32), default='tool')
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)


class KnowledgeEntry(Base):
    __tablename__ = 'knowledge_entries'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    site_id: Mapped[str] = mapped_column(ForeignKey('sites.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text, default='')
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict] = mapped_column('metadata', JSON, default=dict)
    embedding: Mapped[Optional[list]] = mapped_column(Vector(768), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class VoiceSession(Base):
    __tablename__ = 'voice_sessions'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    site_id: Mapped[str] = mapped_column(ForeignKey('sites.id', ondelete='CASCADE'), index=True)
    customer_identity: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    origin: Mapped[str] = mapped_column(String(255))
    mode: Mapped[str] = mapped_column(String(16), default='voice')
    status: Mapped[str] = mapped_column(String(32), default='bootstrapped')
    max_session_duration_seconds: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    usage_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Turn(Base):
    __tablename__ = 'turns'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey('voice_sessions.id', ondelete='CASCADE'), index=True)
    role: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text, default='')
    final: Mapped[bool] = mapped_column(Boolean, default=False)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[Optional[list]] = mapped_column(Vector(768), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Transcript(Base):
    __tablename__ = 'transcripts'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey('voice_sessions.id', ondelete='CASCADE'), index=True)
    role: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text, default='')
    final: Mapped[bool] = mapped_column(Boolean, default=False)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(64))
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ToolEvent(Base):
    __tablename__ = 'tool_events'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey('voice_sessions.id', ondelete='CASCADE'), index=True)
    tool_name: Mapped[str] = mapped_column(String(255))
    call_id: Mapped[str] = mapped_column(String(255))
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    response_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    is_error: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SessionMemory(Base):
    __tablename__ = 'session_memory'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey('voice_sessions.id', ondelete='CASCADE'), index=True)
    summary_text: Mapped[str] = mapped_column(Text, default='')
    summary_model: Mapped[str] = mapped_column(String(255))
    embedding: Mapped[Optional[list]] = mapped_column(Vector(768), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModerationState(Base):
    __tablename__ = 'moderation_state'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey('voice_sessions.id', ondelete='CASCADE'), index=True, unique=True)
    strike_count: Mapped[int] = mapped_column(Integer, default=0)
    terminated: Mapped[bool] = mapped_column(Boolean, default=False)
    last_decision: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_reason_code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_review_tag: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ModerationEvent(Base):
    __tablename__ = 'moderation_events'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey('voice_sessions.id', ondelete='CASCADE'), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    turn_key: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sequence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    classification: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    reason_code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    strike_count: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConversationState(Base):
    __tablename__ = 'conversation_state'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey('voice_sessions.id', ondelete='CASCADE'), index=True)
    state: Mapped[str] = mapped_column(String(64), default='active')
    state_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
