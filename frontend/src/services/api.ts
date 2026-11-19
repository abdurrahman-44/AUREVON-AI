import {
  AITestResponse,
  AdminAnalyticsResponse,
  AdminUserDetailResponse,
  AdminUserItem,
  AuthResponse,
  BootstrapStatus,
  Conversation,
  ConversationDetail,
  ErrorLogsResponse,
  LogPruneResponse,
  ModelInfo,
  PaginatedAPIRequestLogsResponse,
  PaginatedAdminAuditLogsResponse,
  PaginatedSecurityEventsResponse,
  PaginatedUsersResponse,
  PlatformConfigResponse,
  CitationItem,
  PublicIntelligenceConfig,
  SystemAIConfigResponse,
  ToolCallEvent,
  SystemDiagnosticsResponse,
  SystemMonitoringResponse,
  SystemStatus,
  TerminalCommandInfo,
  TerminalExecuteResponse,
  TwoFactorSetupResponse,
  TwoFactorStatusResponse,
  User,
  UserSettings,
} from '../types';

export class TwoFactorRequiredError extends Error {
  twoFactorRequired = true;
  constructor(message = 'Two-factor authentication code required') {
    super(message);
    this.name = 'TwoFactorRequiredError';
  }
}

const API_BASE = '/api';

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem('aurevon_token');
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

async function parseError(res: Response, fallback: string): Promise<string> {
  try {
    const err = await res.json();
    if (typeof err?.detail === 'string') return err.detail;
  } catch {
    // ignore JSON parse failure
  }
  return res.statusText || fallback;
}

// ----------------- Auth & Bootstrap -----------------
export async function registerUser(username: string, email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email, password }),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Registration failed'));
  return res.json();
}

export async function loginUser(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Login failed'));
  return res.json();
}

export async function adminLogin(
  email: string,
  password: string,
  totpCode?: string
): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/auth/admin-login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      password,
      totp_code: totpCode?.trim() || undefined,
    }),
  });
  if (!res.ok) {
    const msg = await parseError(res, 'Administrator authentication failed');
    if (res.status === 401 && res.headers.get('X-AUREVON-2FA-Required') === 'true') {
      throw new TwoFactorRequiredError(msg);
    }
    throw new Error(msg);
  }
  return res.json();
}

export async function logoutUser(): Promise<void> {
  try {
    await fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      headers: { ...getAuthHeader() },
    });
  } catch {
    // Best-effort revocation; client still clears token locally
  }
}

export async function fetchBootstrapStatus(): Promise<BootstrapStatus> {
  const res = await fetch(`${API_BASE}/auth/bootstrap-status`);
  if (!res.ok) throw new Error(await parseError(res, 'Failed to check bootstrap status'));
  return res.json();
}

export async function bootstrapOwner(
  username: string,
  email: string,
  password: string,
  bootstrapToken?: string
): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/auth/bootstrap-owner`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username,
      email,
      password,
      bootstrap_token: bootstrapToken || undefined,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Owner bootstrap failed'));
  return res.json();
}

export async function fetchMe(): Promise<User> {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error('Not authenticated');
  return res.json();
}

export async function fetchUserSettings(): Promise<UserSettings> {
  const res = await fetch(`${API_BASE}/settings`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error('Failed to fetch settings');
  return res.json();
}

export async function updateUserSettings(settings: Partial<UserSettings>): Promise<UserSettings> {
  const res = await fetch(`${API_BASE}/settings`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
    },
    body: JSON.stringify(settings),
  });
  if (!res.ok) throw new Error('Failed to update settings');
  return res.json();
}

// ----------------- Public Intelligence Config -----------------
export async function fetchPublicIntelligence(): Promise<PublicIntelligenceConfig> {
  const res = await fetch(`${API_BASE}/intelligence/public`);
  if (!res.ok) throw new Error('Failed to fetch intelligence config');
  return res.json();
}

// ----------------- Owner Console & Control Centre API -----------------
export async function fetchAdminAnalytics(
  range: '24h' | '7d' | '30d' | '90d' | 'custom' = '7d',
  startDate?: string,
  endDate?: string
): Promise<AdminAnalyticsResponse> {
  const params = new URLSearchParams({ range });
  if (range === 'custom' && startDate && endDate) {
    params.set('start_date', startDate);
    params.set('end_date', endDate);
  }
  const res = await fetch(`${API_BASE}/admin/analytics?${params.toString()}`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to fetch analytics'));
  return res.json();
}

export async function fetchAdminUsers(params: {
  page?: number;
  pageSize?: number;
  search?: string;
  role?: string;
  isActive?: string;
}): Promise<PaginatedUsersResponse> {
  const qs = new URLSearchParams();
  qs.set('page', String(params.page || 1));
  qs.set('page_size', String(params.pageSize || 15));
  if (params.search?.trim()) qs.set('search', params.search.trim());
  if (params.role && params.role !== 'all') qs.set('role', params.role);
  if (params.isActive === 'active') qs.set('is_active', 'true');
  if (params.isActive === 'suspended') qs.set('is_active', 'false');

  const res = await fetch(`${API_BASE}/admin/users?${qs.toString()}`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to load users'));
  return res.json();
}

export async function updateAdminUserStatus(userId: string, isActive: boolean): Promise<AdminUserItem> {
  const res = await fetch(`${API_BASE}/admin/users/${userId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
    body: JSON.stringify({ is_active: isActive }),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to update account status'));
  return res.json();
}

export async function updateAdminUserRole(userId: string, role: 'user' | 'owner'): Promise<AdminUserItem> {
  const res = await fetch(`${API_BASE}/admin/users/${userId}/role`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
    body: JSON.stringify({ role }),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to update role'));
  return res.json();
}

export async function fetchAdminMonitoring(): Promise<SystemMonitoringResponse> {
  const res = await fetch(`${API_BASE}/admin/monitoring`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to fetch system monitoring'));
  return res.json();
}

export async function fetchAdminIntelligence(): Promise<SystemAIConfigResponse> {
  const res = await fetch(`${API_BASE}/admin/intelligence`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to fetch intelligence configuration'));
  return res.json();
}

export async function updateAdminIntelligence(payload: Partial<SystemAIConfigResponse>): Promise<SystemAIConfigResponse> {
  const res = await fetch(`${API_BASE}/admin/intelligence`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to save intelligence configuration'));
  return res.json();
}

export async function createSystemPromptVersion(payload: {
  name: string;
  content: string;
  notes?: string;
  activate?: boolean;
}): Promise<SystemAIConfigResponse> {
  const res = await fetch(`${API_BASE}/admin/intelligence/prompts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
    body: JSON.stringify({ activate: true, ...payload }),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to create system prompt version'));
  return res.json();
}

export async function configureCloudProvider(provider: string, apiKey: string): Promise<any> {
  const res = await fetch(`${API_BASE}/models/configure`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
    body: JSON.stringify({ provider, api_key: apiKey }),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to configure provider'));
  return res.json();
}

export async function fetchAdminAIModels(): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/ai/models`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to discover models'));
  return res.json();
}

export async function selectAdminAIModel(payload: Record<string, any>): Promise<SystemAIConfigResponse> {
  const res = await fetch(`${API_BASE}/admin/ai/models/select`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to select model'));
  return res.json();
}

export async function fetchAdminAITools(): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/ai/tools`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to load AI tools'));
  return res.json();
}

export async function updateAdminAITool(toolName: string, payload: Record<string, any>): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/ai/tools/${encodeURIComponent(toolName)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to update tool configuration'));
  return res.json();
}

export async function fetchAdminAIKnowledge(): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/ai/knowledge`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to load knowledge index'));
  return res.json();
}

export async function rebuildAdminKnowledgeIndex(): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/ai/knowledge/rebuild`, {
    method: 'POST',
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to rebuild knowledge index'));
  return res.json();
}

export async function deleteAdminKnowledgeDoc(docId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/ai/knowledge/${encodeURIComponent(docId)}`, {
    method: 'DELETE',
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to remove document'));
  return res.json();
}

export async function fetchAdminAIProviders(): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/ai/providers`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to load provider usage'));
  return res.json();
}

export async function fetchAdminAIPerformance(range: '24h' | '7d' | '30d' = '7d'): Promise<any> {
  const res = await fetch(`${API_BASE}/admin/ai/performance?range_key=${range}`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to load AI performance metrics'));
  return res.json();
}

export async function fetchAdminUserDetail(userId: string): Promise<AdminUserDetailResponse> {
  const res = await fetch(`${API_BASE}/admin/users/${userId}`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to fetch user profile'));
  return res.json();
}

export async function runAdminAITest(payload?: {
  provider?: string;
  model?: string;
  prompt?: string;
}): Promise<AITestResponse> {
  const res = await fetch(`${API_BASE}/admin/ai/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
    body: JSON.stringify(payload || {}),
  });
  if (!res.ok) throw new Error(await parseError(res, 'AI connectivity test failed'));
  return res.json();
}

export async function fetchAdminDiagnostics(): Promise<SystemDiagnosticsResponse> {
  const res = await fetch(`${API_BASE}/admin/diagnostics`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to run diagnostics'));
  return res.json();
}

export async function fetchAdminTerminalCommands(): Promise<TerminalCommandInfo[]> {
  const res = await fetch(`${API_BASE}/admin/terminal/commands`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to load terminal command catalog'));
  return res.json();
}

export async function executeAdminTerminalCommand(
  command: string,
  confirmToken?: string
): Promise<TerminalExecuteResponse> {
  const res = await fetch(`${API_BASE}/admin/terminal/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
    body: JSON.stringify({
      command,
      confirm_token: confirmToken || undefined,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Terminal execution failed'));
  return res.json();
}

export async function fetchApiRequestLogs(params: {
  page?: number;
  pageSize?: number;
  method?: string;
  statusCode?: number;
  pathSearch?: string;
}): Promise<PaginatedAPIRequestLogsResponse> {
  const qs = new URLSearchParams();
  qs.set('page', String(params.page || 1));
  qs.set('page_size', String(params.pageSize || 25));
  if (params.method?.trim()) qs.set('method', params.method.trim());
  if (params.statusCode) qs.set('status_code', String(params.statusCode));
  if (params.pathSearch?.trim()) qs.set('path_search', params.pathSearch.trim());

  const res = await fetch(`${API_BASE}/admin/logs/requests?${qs.toString()}`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to load API request logs'));
  return res.json();
}

export async function fetchAdminAuditLogs(params: {
  page?: number;
  pageSize?: number;
  action?: string;
  statusFilter?: string;
  search?: string;
}): Promise<PaginatedAdminAuditLogsResponse> {
  const qs = new URLSearchParams();
  qs.set('page', String(params.page || 1));
  qs.set('page_size', String(params.pageSize || 25));
  if (params.action?.trim()) qs.set('action', params.action.trim());
  if (params.statusFilter?.trim()) qs.set('status_filter', params.statusFilter.trim());
  if (params.search?.trim()) qs.set('search', params.search.trim());

  const res = await fetch(`${API_BASE}/admin/logs/audit?${qs.toString()}`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to load admin audit logs'));
  return res.json();
}

export async function fetchRecentErrorLogs(): Promise<ErrorLogsResponse> {
  const res = await fetch(`${API_BASE}/admin/logs/errors`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to load error logs'));
  return res.json();
}

export async function pruneOperationalLogs(retentionDays: number): Promise<LogPruneResponse> {
  const res = await fetch(`${API_BASE}/admin/logs/prune`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
    body: JSON.stringify({ retention_days: retentionDays }),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to prune operational logs'));
  return res.json();
}

export async function fetchSecurityEvents(params: {
  page?: number;
  pageSize?: number;
  eventType?: string;
  severity?: string;
}): Promise<PaginatedSecurityEventsResponse> {
  const qs = new URLSearchParams();
  qs.set('page', String(params.page || 1));
  qs.set('page_size', String(params.pageSize || 25));
  if (params.eventType?.trim()) qs.set('event_type', params.eventType.trim());
  if (params.severity && params.severity !== 'all') qs.set('severity', params.severity);

  const res = await fetch(`${API_BASE}/admin/security/events?${qs.toString()}`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to load security events'));
  return res.json();
}

export async function fetchTwoFactorStatus(): Promise<TwoFactorStatusResponse> {
  const res = await fetch(`${API_BASE}/admin/security/2fa/status`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to check 2FA status'));
  return res.json();
}

export async function setupTwoFactor(): Promise<TwoFactorSetupResponse> {
  const res = await fetch(`${API_BASE}/admin/security/2fa/setup`, {
    method: 'POST',
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to initiate 2FA setup'));
  return res.json();
}

export async function enableTwoFactor(code: string): Promise<TwoFactorStatusResponse> {
  const res = await fetch(`${API_BASE}/admin/security/2fa/enable`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
    body: JSON.stringify({ code }),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to enable 2FA'));
  return res.json();
}

export async function disableTwoFactor(code: string): Promise<TwoFactorStatusResponse> {
  const res = await fetch(`${API_BASE}/admin/security/2fa/disable`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
    body: JSON.stringify({ code }),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to disable 2FA'));
  return res.json();
}

export async function fetchPlatformSettings(): Promise<PlatformConfigResponse> {
  const res = await fetch(`${API_BASE}/admin/settings`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to load platform settings'));
  return res.json();
}

export async function updatePlatformSettings(
  payload: Partial<PlatformConfigResponse>
): Promise<PlatformConfigResponse> {
  const res = await fetch(`${API_BASE}/admin/settings`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to save platform settings'));
  return res.json();
}

// ----------------- Documents (RAG) -----------------
export async function uploadDocument(file: File): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/documents/upload`, {
    method: 'POST',
    headers: { ...getAuthHeader() },
    body: formData,
  });
  if (!res.ok) throw new Error(await parseError(res, 'Upload failed'));
  return res.json();
}

export async function fetchDocuments(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/documents`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to fetch documents'));
  return res.json();
}

export async function deleteDocument(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/documents/${id}`, {
    method: 'DELETE',
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to delete document'));
}

export async function queryDocuments(query: string, topK: number = 4): Promise<any> {
  const res = await fetch(`${API_BASE}/documents/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
    },
    body: JSON.stringify({ query, top_k: topK }),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Query failed'));
  return res.json();
}

// ----------------- Memory System -----------------
export async function fetchMemories(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/memory`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to fetch memories'));
  return res.json();
}

export async function createMemory(content: string, category: string = 'general'): Promise<any> {
  const res = await fetch(`${API_BASE}/memory`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
    },
    body: JSON.stringify({ content, category }),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to create memory'));
  return res.json();
}

export async function updateMemory(
  id: string,
  updates: { content?: string; category?: string; is_active?: boolean }
): Promise<any> {
  const res = await fetch(`${API_BASE}/memory/${id}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
    },
    body: JSON.stringify(updates),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to update memory'));
  return res.json();
}

export async function deleteMemory(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/memory/${id}`, {
    method: 'DELETE',
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to delete memory'));
}

// ----------------- Web Research -----------------
export async function executeResearch(query: string, maxSources: number = 4): Promise<any> {
  const res = await fetch(`${API_BASE}/research`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
    },
    body: JSON.stringify({ query, max_sources: maxSources }),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Research failed'));
  return res.json();
}

// ----------------- AI Agent Platform -----------------
export async function fetchAgentTools(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/agents/tools`);
  if (!res.ok) throw new Error('Failed to fetch agent tools');
  return res.json();
}

export async function runAgentTask(task: string, model?: string): Promise<any> {
  const res = await fetch(`${API_BASE}/agents/run`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
    },
    body: JSON.stringify({ task, model }),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Agent execution failed'));
  return res.json();
}

export async function fetchAgentRuns(): Promise<any[]> {
  const res = await fetch(`${API_BASE}/agents/runs`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to fetch agent runs'));
  return res.json();
}

// ----------------- Conversations -----------------
export async function fetchConversations(): Promise<Conversation[]> {
  const res = await fetch(`${API_BASE}/conversations`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to fetch conversations'));
  return res.json();
}

export async function fetchConversation(id: string): Promise<ConversationDetail> {
  const res = await fetch(`${API_BASE}/conversations/${id}`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to fetch conversation'));
  return res.json();
}

export async function createConversation(title?: string): Promise<Conversation> {
  const res = await fetch(`${API_BASE}/conversations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
    },
    body: JSON.stringify({ title: title || 'New Conversation' }),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to create conversation'));
  return res.json();
}

export async function updateConversationTitle(id: string, title: string): Promise<Conversation> {
  const res = await fetch(`${API_BASE}/conversations/${id}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
    },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to update conversation'));
  return res.json();
}

export async function deleteConversation(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/conversations/${id}`, {
    method: 'DELETE',
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(await parseError(res, 'Failed to delete conversation'));
}

// ----------------- System & Models -----------------
export async function fetchModels(): Promise<ModelInfo[]> {
  const res = await fetch(`${API_BASE}/models`);
  if (!res.ok) throw new Error(`Failed to fetch models: ${res.statusText}`);
  return res.json();
}

export async function fetchSystemHealth(): Promise<SystemStatus> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error(`Failed to check health: ${res.statusText}`);
  return res.json();
}

export interface StreamChatParams {
  conversationId?: string | null;
  message: string;
  model?: string;
  temperature?: number;
  images?: string[];
  documentIds?: string[];
  webSearch?: boolean;
  allowCloud?: boolean;
  regenerate?: boolean;
  abortSignal?: AbortSignal;
  onChunk: (delta: string) => void;
  onStatus?: (status: string) => void;
  onToolEvent?: (toolEvent: ToolCallEvent) => void;
  onCitations?: (citations: CitationItem[]) => void;
  onCharts?: (charts: string[]) => void;
  onInit?: (data: {
    conversation_id: string;
    user_message_id: string;
    model?: string;
    provider?: string;
    model_pinned?: boolean;
    intent?: string;
  }) => void;
  onDone?: (data: {
    conversation_id: string;
    assistant_message_id: string;
    model?: string;
    provider?: string;
    intent?: string;
    token_usage?: Record<string, any> | null;
    citations?: CitationItem[] | null;
    tools_used?: ToolCallEvent[] | null;
  }) => void;
  onError?: (error: Error) => void;
}

export async function streamChat({
  conversationId,
  message,
  model,
  temperature = 0.7,
  images,
  documentIds,
  webSearch = false,
  allowCloud = false,
  regenerate = false,
  abortSignal,
  onChunk,
  onStatus,
  onToolEvent,
  onCitations,
  onCharts,
  onInit,
  onDone,
  onError,
}: StreamChatParams): Promise<void> {
  try {
    const response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...getAuthHeader(),
      },
      body: JSON.stringify({
        conversation_id: conversationId,
        message,
        model,
        temperature,
        images,
        document_ids: documentIds && documentIds.length > 0 ? documentIds : undefined,
        web_search: webSearch,
        allow_cloud: allowCloud,
        regenerate,
        stream: true,
      }),
      signal: abortSignal,
    });

    if (!response.ok) {
      const msg = await parseError(response, `Chat API error (${response.status})`);
      throw new Error(msg);
    }

    if (!response.body) {
      throw new Error('Response body is null');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('data: ')) {
          const jsonStr = trimmed.slice(6);
          try {
            const data = JSON.parse(jsonStr);
            if (data.user_message_id && onInit) {
              onInit(data);
            }
            if (data.status && onStatus) {
              onStatus(data.status);
            }
            if (data.tool_event && onToolEvent) {
              onToolEvent(data.tool_event);
            }
            if (Array.isArray(data.citations) && onCitations) {
              onCitations(data.citations);
            }
            if (Array.isArray(data.charts) && onCharts) {
              onCharts(data.charts);
            }
            if (data.delta) {
              onChunk(data.delta);
            }
            if (data.done && onDone) {
              onDone(data);
            }
          } catch (e) {
            console.error('Failed to parse SSE line:', jsonStr, e);
          }
        }
      }
    }
  } catch (err: any) {
    if (err.name === 'AbortError') {
      return;
    }
    if (onError) onError(err);
    throw err;
  }
}
