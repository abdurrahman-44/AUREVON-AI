import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    Boolean,
    Integer,
    Float,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship
from backend.app.database.session import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), default="user", nullable=False, index=True)  # user | owner
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    last_active_at = Column(DateTime, nullable=True, index=True)
    totp_secret = Column(String(64), nullable=True)
    totp_enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    agent_runs = relationship("AgentRun", back_populates="user", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), nullable=False, default="New Conversation")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")
    summary = relationship("ConversationSummary", back_populates="conversation", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_conversations_user_updated", "user_id", "updated_at"),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), nullable=False)  # "user", "assistant", "system"
    content = Column(Text, nullable=False)
    model = Column(String(128), nullable=True)
    token_usage = Column(JSON, nullable=True)
    tool_calls = Column(JSON, nullable=True)
    citations = Column(JSON, nullable=True)
    intent = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_conv_created", "conversation_id", "created_at"),
    )


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    theme = Column(String(32), default="dark", nullable=False)
    default_model = Column(String(128), default="qwen2.5:3b", nullable=False)
    memory_enabled = Column(Boolean, default=True, nullable=False)
    other_preferences = Column(JSON, default=dict, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="settings")


class Memory(Base):
    __tablename__ = "memories"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    category = Column(String(64), default="general", nullable=False, index=True)  # preference, fact, project, instruction
    source = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="memories")


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(32), nullable=False)
    file_size_bytes = Column(Integer, default=0, nullable=False)
    content_hash = Column(String(64), nullable=True, index=True)
    storage_path = Column(String(512), nullable=False)
    processing_status = Column(String(32), default="pending", nullable=False)  # pending, processing, completed, failed
    chunk_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan", order_by="DocumentChunk.chunk_index")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    embedding = Column(JSON, nullable=True)

    document = relationship("Document", back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_doc_idx", "document_id", "chunk_index"),
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    task = Column(Text, nullable=False)
    status = Column(String(32), default="pending", nullable=False)  # pending, running, completed, failed, cancelled
    execution_log = Column(JSON, default=list, nullable=False)
    final_output = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="agent_runs")


class AIRequestLog(Base):
    """Privacy-preserving AI request telemetry. Never stores user prompts or assistant outputs."""

    __tablename__ = "ai_request_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    request_type = Column(String(32), default="chat", nullable=False, index=True)  # chat, agent, document_qa
    provider = Column(String(64), nullable=False, index=True)
    model = Column(String(128), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    duration_ms = Column(Integer, nullable=True)
    first_token_ms = Column(Integer, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    success = Column(Boolean, default=True, nullable=False, index=True)
    error_category = Column(String(64), nullable=True, index=True)
    error_message = Column(String(255), nullable=True)
    intent = Column(String(64), nullable=True, index=True)
    tools_used = Column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_ai_logs_created_success", "created_at", "success"),
        Index("ix_ai_logs_provider_model", "provider", "model"),
    )


class SystemAIConfig(Base):
    """Server-side centralized AUREVON Intelligence Core configuration."""

    __tablename__ = "system_ai_configs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    config_key = Column(String(64), unique=True, nullable=False, default="default", index=True)
    active_provider = Column(String(64), nullable=False, default="ollama")
    active_model = Column(String(128), nullable=False, default="qwen2.5:3b")
    coding_provider = Column(String(64), nullable=True)
    coding_model = Column(String(128), nullable=True)
    context_window = Column(Integer, nullable=False, default=8192)
    max_output_tokens = Column(Integer, nullable=False, default=2048)
    temperature = Column(Float, nullable=False, default=0.7)
    keep_alive_seconds = Column(Integer, nullable=False, default=900)
    request_timeout_seconds = Column(Integer, nullable=False, default=120)
    streaming_enabled = Column(Boolean, nullable=False, default=True)
    web_search_enabled = Column(Boolean, nullable=False, default=False)
    cloud_inference_enabled = Column(Boolean, nullable=False, default=False)
    require_cloud_consent = Column(Boolean, nullable=False, default=True)
    cloud_daily_limit = Column(Integer, nullable=False, default=100)
    allow_user_model_switching = Column(Boolean, nullable=False, default=False)
    fallback_provider = Column(String(64), nullable=True)
    fallback_model = Column(String(128), nullable=True)
    enable_memory_injection = Column(Boolean, nullable=False, default=True)
    enable_rag_injection = Column(Boolean, nullable=False, default=True)
    enable_agent_tools = Column(Boolean, nullable=False, default=True)
    active_prompt_version_id = Column(String(36), ForeignKey("system_prompt_versions.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class SystemPromptVersion(Base):
    """Version-controlled AUREVON master system prompt history."""

    __tablename__ = "system_prompt_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    version_number = Column(Integer, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    content = Column(Text, nullable=False)
    notes = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=False, index=True)
    created_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class RevokedToken(Base):
    """Stores explicitly revoked JWT JTIs from logout to enforce true session termination."""

    __tablename__ = "revoked_tokens"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    jti = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    revoked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class AdminAuditLog(Base):
    """Immutable audit record of sensitive owner administrative operations."""

    __tablename__ = "admin_audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    actor_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_username = Column(String(64), nullable=False)
    action = Column(String(64), nullable=False, index=True)
    target_type = Column(String(64), nullable=True)
    target_id = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, default="success", index=True)
    summary = Column(String(255), nullable=False)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class SecurityEvent(Base):
    """Privacy-safe authentication & authorization security telemetry."""

    __tablename__ = "security_events"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    severity = Column(String(16), nullable=False, default="info", index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    identifier = Column(String(255), nullable=True)
    ip_address = Column(String(64), nullable=True)
    path = Column(String(255), nullable=True)
    detail = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class APIRequestLog(Base):
    """Sanitized HTTP API telemetry (never stores bodies, auth headers, or query secrets)."""

    __tablename__ = "api_request_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    method = Column(String(16), nullable=False)
    path = Column(String(255), nullable=False, index=True)
    status_code = Column(Integer, nullable=False, index=True)
    duration_ms = Column(Integer, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    client_ip = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index("ix_api_logs_created_status", "created_at", "status_code"),
    )


class PlatformConfig(Base):
    """Owner-controlled runtime platform policies, rate-limit settings, and maintenance mode."""

    __tablename__ = "platform_configs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    config_key = Column(String(64), unique=True, nullable=False, default="default", index=True)
    app_display_name = Column(String(128), nullable=False, default="AUREVON AI")
    maintenance_mode = Column(Boolean, nullable=False, default=False)
    maintenance_message = Column(
        String(255),
        nullable=False,
        default="AUREVON AI is currently undergoing scheduled maintenance. Please check back shortly.",
    )
    allow_public_registration = Column(Boolean, nullable=False, default=True)
    log_retention_days = Column(Integer, nullable=False, default=30)
    auth_rate_limit_per_min = Column(Integer, nullable=False, default=15)
    chat_rate_limit_per_min = Column(Integer, nullable=False, default=30)
    upload_rate_limit_per_min = Column(Integer, nullable=False, default=20)
    enable_api_request_logging = Column(Boolean, nullable=False, default=True)
    updated_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ConversationSummary(Base):
    """Rolling summary of older conversation turns so long chats preserve context without blowing token limits."""

    __tablename__ = "conversation_summaries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    summary_text = Column(Text, nullable=False, default="")
    summarized_message_count = Column(Integer, nullable=False, default=0)
    last_message_id = Column(String(36), nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    conversation = relationship("Conversation", back_populates="summary")


class ToolConfig(Base):
    """Owner-governed tool toggle, permission tier, and execution limits."""

    __tablename__ = "tool_configs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tool_name = Column(String(64), unique=True, nullable=False, index=True)
    display_name = Column(String(128), nullable=False)
    description = Column(String(255), nullable=False)
    is_enabled = Column(Boolean, nullable=False, default=True)
    permission_level = Column(String(32), nullable=False, default="standard")  # standard | owner_only | disabled
    timeout_seconds = Column(Integer, nullable=False, default=10)
    max_calls_per_request = Column(Integer, nullable=False, default=3)
    updated_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class ToolExecutionLog(Base):
    """Privacy-safe telemetry log for tool executions inside chat/agent pipelines."""

    __tablename__ = "tool_execution_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    tool_name = Column(String(64), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="success", index=True)  # success | error | timeout | blocked
    duration_ms = Column(Integer, nullable=False, default=0)
    error_summary = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class ProviderUsageLog(Base):
    """Tracks local & optional cloud provider token usage, consent, and cost estimates."""

    __tablename__ = "provider_usage_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    provider = Column(String(64), nullable=False, index=True)
    model = Column(String(128), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    is_cloud = Column(Boolean, nullable=False, default=False, index=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    estimated_cost_usd = Column(Float, nullable=False, default=0.0)
    consent_granted = Column(Boolean, nullable=False, default=False)
    success = Column(Boolean, nullable=False, default=True, index=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
