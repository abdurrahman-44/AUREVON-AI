from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AdminUserItem(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_active_at: Optional[datetime] = None
    conversation_count: int = 0
    ai_request_count: int = 0
    total_tokens: Optional[int] = None


class PaginatedUsersResponse(BaseModel):
    items: List[AdminUserItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class UserStatusUpdateRequest(BaseModel):
    is_active: bool


class UserRoleUpdateRequest(BaseModel):
    role: str = Field(..., pattern="^(user|owner)$")


class AnalyticsOverviewResponse(BaseModel):
    total_users: int
    active_users_24h: int
    active_users_7d: int
    active_users_30d: int
    total_conversations: int
    total_ai_requests: int
    requests_today: int = 0
    new_users: int = 0
    successful_requests: int
    failed_requests: int
    success_rate_pct: Optional[float] = None


class AIPerformanceMetrics(BaseModel):
    avg_latency_ms: Optional[float] = None
    median_latency_ms: Optional[float] = None
    p95_latency_ms: Optional[float] = None
    avg_first_token_ms: Optional[float] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    requests_per_minute: Optional[float] = None
    requests_per_day: Optional[float] = None


class ModelUtilizationItem(BaseModel):
    provider: str
    model: str
    request_count: int
    successful_count: int
    failed_count: int
    total_tokens: Optional[int] = None
    avg_latency_ms: Optional[float] = None


class ErrorBreakdownItem(BaseModel):
    error_category: str
    count: int


class DailyTimeSeriesPoint(BaseModel):
    date: str
    requests: int
    successful_requests: int
    failed_requests: int
    new_users: int
    active_users: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    avg_latency_ms: Optional[float] = None


class AdminAnalyticsResponse(BaseModel):
    range_label: str
    start_date: datetime
    end_date: datetime
    overview: AnalyticsOverviewResponse
    performance: AIPerformanceMetrics
    model_utilization: List[ModelUtilizationItem]
    error_breakdown: List[ErrorBreakdownItem]
    time_series: List[DailyTimeSeriesPoint]


class ProviderConnectivityItem(BaseModel):
    provider: str
    available: bool
    models_count: int
    error: Optional[str] = None


class RecentErrorItem(BaseModel):
    timestamp: datetime
    source: str
    category: str
    message: str
    model: Optional[str] = None
    provider: Optional[str] = None


class SystemMonitoringResponse(BaseModel):
    checked_at: datetime
    backend_status: str
    database_connected: bool
    database_dialect: str
    active_provider: str
    active_model: str
    provider_health: List[ProviderConnectivityItem]
    cpu_percent: Optional[float] = None
    ram_total_mb: Optional[float] = None
    ram_used_mb: Optional[float] = None
    ram_percent: Optional[float] = None
    process_rss_mb: Optional[float] = None
    uptime_seconds: Optional[int] = None
    host_environment: str = "backend_host"
    os_platform: Optional[str] = None
    python_version: Optional[str] = None
    process_id: Optional[int] = None
    storage_total_gb: Optional[float] = None
    storage_used_gb: Optional[float] = None
    storage_free_gb: Optional[float] = None
    storage_percent: Optional[float] = None
    cache_status: Optional[Dict[str, Any]] = None
    recent_failed_ai_requests: List[RecentErrorItem]
    recent_app_errors: List[RecentErrorItem]


class SystemPromptVersionResponse(BaseModel):
    id: str
    version_number: int
    name: str
    content: str
    notes: Optional[str] = None
    is_active: bool
    created_at: datetime


class SystemPromptCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    content: str = Field(..., min_length=10, max_length=16000)
    notes: Optional[str] = Field(None, max_length=255)
    activate: bool = True


class SystemAIConfigResponse(BaseModel):
    active_provider: str
    active_model: str
    context_window: int
    temperature: float
    allow_user_model_switching: bool
    fallback_provider: Optional[str] = None
    fallback_model: Optional[str] = None
    enable_memory_injection: bool
    enable_rag_injection: bool
    enable_agent_tools: bool
    active_prompt_version_id: Optional[str] = None
    active_prompt: Optional[SystemPromptVersionResponse] = None
    prompt_versions: List[SystemPromptVersionResponse] = []
    updated_at: datetime
    provider_keys_configured: Dict[str, bool] = {}


class SystemAIConfigUpdateRequest(BaseModel):
    active_provider: Optional[str] = None
    active_model: Optional[str] = None
    context_window: Optional[int] = Field(None, ge=512, le=131072)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    allow_user_model_switching: Optional[bool] = None
    fallback_provider: Optional[str] = None
    fallback_model: Optional[str] = None
    enable_memory_injection: Optional[bool] = None
    enable_rag_injection: Optional[bool] = None
    enable_agent_tools: Optional[bool] = None
    active_prompt_version_id: Optional[str] = None


class PublicIntelligenceResponse(BaseModel):
    active_provider: str
    active_model: str
    allow_user_model_switching: bool
    context_window: int
    temperature: float
    enable_memory_injection: bool
    enable_rag_injection: bool
    enable_agent_tools: bool


class AdminUserDetailResponse(BaseModel):
    """Privacy-safe owner view of an account's metadata & usage counters (never exposes credentials or private chats)."""

    id: str
    username: str
    email: str
    role: str
    is_active: bool
    totp_enabled: bool = False
    created_at: datetime
    last_active_at: Optional[datetime] = None
    conversation_count: int = 0
    message_count: int = 0
    document_count: int = 0
    memory_count: int = 0
    ai_request_count: int = 0
    successful_ai_requests: int = 0
    failed_ai_requests: int = 0
    total_tokens: Optional[int] = None
    recent_ai_models: List[str] = []


class AITestRequest(BaseModel):
    provider: Optional[str] = Field(None, max_length=64)
    model: Optional[str] = Field(None, max_length=128)
    prompt: str = Field("Respond concisely with the word OK.", min_length=1, max_length=500)


class AITestResponse(BaseModel):
    provider: str
    model: str
    success: bool
    latency_ms: int
    response_preview: Optional[str] = None
    error_message: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    checked_at: datetime


class DiagnosticCheckItem(BaseModel):
    name: str
    status: str
    latency_ms: Optional[float] = None
    detail: str


class SystemDiagnosticsResponse(BaseModel):
    checked_at: datetime
    overall_status: str
    host_scope_note: str
    checks: List[DiagnosticCheckItem]


class TerminalCommandInfo(BaseModel):
    command: str
    category: str
    description: str
    usage: str
    requires_confirmation: bool = False


class TerminalExecuteRequest(BaseModel):
    command: str = Field(..., min_length=1, max_length=256)
    confirm_token: Optional[str] = Field(None, max_length=128)


class TerminalExecuteResponse(BaseModel):
    command: str
    status: str
    exit_code: int
    duration_ms: int
    executed_at: datetime
    output: str
    structured_data: Optional[Any] = None
    requires_confirmation: bool = False
    confirm_token: Optional[str] = None


class APIRequestLogItem(BaseModel):
    id: str
    method: str
    path: str
    status_code: int
    duration_ms: int
    user_id: Optional[str] = None
    client_ip: Optional[str] = None
    created_at: datetime


class PaginatedAPIRequestLogsResponse(BaseModel):
    items: List[APIRequestLogItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class AdminAuditLogItem(BaseModel):
    id: str
    actor_user_id: Optional[str] = None
    actor_username: str
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    status: str
    summary: str
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime


class PaginatedAdminAuditLogsResponse(BaseModel):
    items: List[AdminAuditLogItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class ErrorLogsResponse(BaseModel):
    failed_ai_requests: List[RecentErrorItem]
    recent_app_errors: List[RecentErrorItem]


class SecurityEventItem(BaseModel):
    id: str
    event_type: str
    severity: str
    user_id: Optional[str] = None
    identifier: Optional[str] = None
    ip_address: Optional[str] = None
    path: Optional[str] = None
    detail: str
    created_at: datetime


class PaginatedSecurityEventsResponse(BaseModel):
    items: List[SecurityEventItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class LogPruneRequest(BaseModel):
    retention_days: int = Field(..., ge=1, le=365)


class LogPruneResponse(BaseModel):
    retention_days: int
    deleted: Dict[str, int]
    pruned_at: datetime


class TwoFactorStatusResponse(BaseModel):
    totp_enabled: bool


class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    issuer: str
    account_name: str


class TwoFactorVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=12)


class PlatformConfigResponse(BaseModel):
    app_display_name: str
    maintenance_mode: bool
    maintenance_message: str
    allow_public_registration: bool
    log_retention_days: int
    auth_rate_limit_per_min: int
    chat_rate_limit_per_min: int
    upload_rate_limit_per_min: int
    enable_api_request_logging: bool
    updated_at: datetime


class PlatformConfigUpdateRequest(BaseModel):
    app_display_name: Optional[str] = Field(None, min_length=2, max_length=128)
    maintenance_mode: Optional[bool] = None
    maintenance_message: Optional[str] = Field(None, min_length=5, max_length=255)
    allow_public_registration: Optional[bool] = None
    log_retention_days: Optional[int] = Field(None, ge=1, le=365)
    auth_rate_limit_per_min: Optional[int] = Field(None, ge=5, le=300)
    chat_rate_limit_per_min: Optional[int] = Field(None, ge=5, le=300)
    upload_rate_limit_per_min: Optional[int] = Field(None, ge=2, le=300)
    enable_api_request_logging: Optional[bool] = None
