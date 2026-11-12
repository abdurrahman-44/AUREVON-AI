export interface UserSettings {
  theme: string;
  default_model: string;
  memory_enabled: boolean;
  other_preferences: Record<string, any>;
}

export interface User {
  id: string;
  username: string;
  email: string;
  role: 'user' | 'owner';
  is_active: boolean;
  totp_enabled?: boolean;
  last_active_at?: string | null;
  created_at: string;
  settings?: UserSettings;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface BootstrapStatus {
  owner_exists: boolean;
  requires_bootstrap_token: boolean;
  web_bootstrap_allowed: boolean;
}

export interface PublicIntelligenceConfig {
  active_provider: string;
  active_model: string;
  allow_user_model_switching: boolean;
  context_window: number;
  temperature: number;
  enable_memory_injection: boolean;
  enable_rag_injection: boolean;
  enable_agent_tools: boolean;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  model?: string;
  token_usage?: {
    prompt_tokens?: number | null;
    completion_tokens?: number | null;
    total_tokens?: number | null;
  } | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  user_id?: string;
  created_at: string;
  updated_at: string;
  message_count?: number;
  last_message_preview?: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface ModelCapability {
  vision: boolean;
  tools: boolean;
  context_length: number;
  family: string;
}

export interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  size?: string;
  parameters?: string;
  capabilities: ModelCapability;
  is_available: boolean;
  is_default: boolean;
}

export interface ProviderHealth {
  provider: string;
  status: 'healthy' | 'unhealthy' | 'offline';
  url: string;
  available_models: string[];
  error_message?: string;
}

export interface SystemStatus {
  app_name: string;
  version: string;
  database: string;
  providers: ProviderHealth[];
}

// -------- Owner Console Analytics & Monitoring --------

export interface AdminUserItem {
  id: string;
  username: string;
  email: string;
  role: 'user' | 'owner';
  is_active: boolean;
  created_at: string;
  last_active_at?: string | null;
  conversation_count: number;
  ai_request_count: number;
  total_tokens?: number | null;
}

export interface PaginatedUsersResponse {
  items: AdminUserItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AnalyticsOverview {
  total_users: number;
  active_users_24h: number;
  active_users_7d: number;
  active_users_30d: number;
  total_conversations: number;
  total_ai_requests: number;
  requests_today: number;
  new_users: number;
  successful_requests: number;
  failed_requests: number;
  success_rate_pct: number | null;
}

export interface AIPerformanceMetrics {
  avg_latency_ms: number | null;
  median_latency_ms: number | null;
  p95_latency_ms: number | null;
  avg_first_token_ms: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  requests_per_minute: number | null;
  requests_per_day: number | null;
}

export interface ModelUtilizationItem {
  provider: string;
  model: string;
  request_count: number;
  successful_count: number;
  failed_count: number;
  total_tokens: number | null;
  avg_latency_ms: number | null;
}

export interface ErrorBreakdownItem {
  error_category: string;
  count: number;
}

export interface DailyTimeSeriesPoint {
  date: string;
  requests: number;
  successful_requests: number;
  failed_requests: number;
  new_users: number;
  active_users: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  avg_latency_ms: number | null;
}

export interface AdminAnalyticsResponse {
  range_label: string;
  start_date: string;
  end_date: string;
  overview: AnalyticsOverview;
  performance: AIPerformanceMetrics;
  model_utilization: ModelUtilizationItem[];
  error_breakdown: ErrorBreakdownItem[];
  time_series: DailyTimeSeriesPoint[];
}

export interface ProviderConnectivityItem {
  provider: string;
  available: boolean;
  models_count: number;
  error?: string | null;
}

export interface RecentErrorItem {
  timestamp: string;
  source: string;
  category: string;
  message: string;
  model?: string | null;
  provider?: string | null;
}

export interface SystemMonitoringResponse {
  checked_at: string;
  backend_status: string;
  database_connected: boolean;
  database_dialect: string;
  active_provider: string;
  active_model: string;
  provider_health: ProviderConnectivityItem[];
  cpu_percent: number | null;
  ram_total_mb: number | null;
  ram_used_mb: number | null;
  ram_percent: number | null;
  process_rss_mb: number | null;
  uptime_seconds?: number | null;
  host_environment?: string;
  os_platform?: string | null;
  python_version?: string | null;
  process_id?: number | null;
  storage_total_gb?: number | null;
  storage_used_gb?: number | null;
  storage_free_gb?: number | null;
  storage_percent?: number | null;
  cache_status?: {
    entries: number;
    max_entries: number;
    keys: string[];
  } | null;
  recent_failed_ai_requests: RecentErrorItem[];
  recent_app_errors: RecentErrorItem[];
}

export interface SystemPromptVersion {
  id: string;
  version_number: number;
  name: string;
  content: string;
  notes?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface SystemAIConfigResponse {
  active_provider: string;
  active_model: string;
  context_window: number;
  temperature: number;
  allow_user_model_switching: boolean;
  fallback_provider?: string | null;
  fallback_model?: string | null;
  enable_memory_injection: boolean;
  enable_rag_injection: boolean;
  enable_agent_tools: boolean;
  active_prompt_version_id?: string | null;
  active_prompt?: SystemPromptVersion | null;
  prompt_versions: SystemPromptVersion[];
  updated_at: string;
  provider_keys_configured: Record<string, boolean>;
}

// -------- AUREVON Control Centre Types --------

export type AdminSectionRoute =
  | '/admin'
  | '/admin/terminal'
  | '/admin/ai'
  | '/admin/users'
  | '/admin/system'
  | '/admin/logs'
  | '/admin/security'
  | '/admin/settings';

export interface AdminUserDetailResponse {
  id: string;
  username: string;
  email: string;
  role: 'user' | 'owner';
  is_active: boolean;
  totp_enabled: boolean;
  created_at: string;
  last_active_at?: string | null;
  conversation_count: number;
  message_count: number;
  document_count: number;
  memory_count: number;
  ai_request_count: number;
  successful_ai_requests: number;
  failed_ai_requests: number;
  total_tokens?: number | null;
  recent_ai_models: string[];
}

export interface AITestResponse {
  provider: string;
  model: string;
  success: boolean;
  latency_ms: number;
  response_preview?: string | null;
  error_message?: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  checked_at: string;
}

export interface DiagnosticCheckItem {
  name: string;
  status: 'pass' | 'warn' | 'fail' | string;
  latency_ms?: number | null;
  detail: string;
}

export interface SystemDiagnosticsResponse {
  checked_at: string;
  overall_status: string;
  host_scope_note: string;
  checks: DiagnosticCheckItem[];
}

export interface TerminalCommandInfo {
  command: string;
  category: string;
  description: string;
  usage: string;
  requires_confirmation: boolean;
}

export interface TerminalExecuteResponse {
  command: string;
  status: string;
  exit_code: number;
  duration_ms: number;
  executed_at: string;
  output: string;
  structured_data?: any;
  requires_confirmation: boolean;
  confirm_token?: string | null;
}

export interface APIRequestLogItem {
  id: string;
  method: string;
  path: string;
  status_code: number;
  duration_ms: number;
  user_id?: string | null;
  client_ip?: string | null;
  created_at: string;
}

export interface PaginatedAPIRequestLogsResponse {
  items: APIRequestLogItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AdminAuditLogItem {
  id: string;
  actor_user_id?: string | null;
  actor_username: string;
  action: string;
  target_type?: string | null;
  target_id?: string | null;
  status: string;
  summary: string;
  details?: Record<string, any> | null;
  ip_address?: string | null;
  created_at: string;
}

export interface PaginatedAdminAuditLogsResponse {
  items: AdminAuditLogItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ErrorLogsResponse {
  failed_ai_requests: RecentErrorItem[];
  recent_app_errors: RecentErrorItem[];
}

export interface SecurityEventItem {
  id: string;
  event_type: string;
  severity: 'info' | 'warning' | 'critical' | string;
  user_id?: string | null;
  identifier?: string | null;
  ip_address?: string | null;
  path?: string | null;
  detail: string;
  created_at: string;
}

export interface PaginatedSecurityEventsResponse {
  items: SecurityEventItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface LogPruneResponse {
  retention_days: number;
  deleted: Record<string, number>;
  pruned_at: string;
}

export interface TwoFactorStatusResponse {
  totp_enabled: boolean;
}

export interface TwoFactorSetupResponse {
  secret: string;
  otpauth_uri: string;
  issuer: string;
  account_name: string;
}

export interface PlatformConfigResponse {
  app_display_name: string;
  maintenance_mode: boolean;
  maintenance_message: string;
  allow_public_registration: boolean;
  log_retention_days: number;
  auth_rate_limit_per_min: number;
  chat_rate_limit_per_min: number;
  upload_rate_limit_per_min: number;
  enable_api_request_logging: boolean;
  updated_at: string;
}
