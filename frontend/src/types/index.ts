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
  created_at: string;
  settings?: UserSettings;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  model?: string;
  token_usage?: Record<string, any>;
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
