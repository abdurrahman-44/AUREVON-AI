import { Conversation, ConversationDetail, ModelInfo, SystemStatus, User, AuthResponse, UserSettings } from '../types';

const API_BASE = '/api';

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem('aurevon_token');
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

// ----------------- Auth & Settings -----------------
export async function registerUser(username: string, email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Registration failed');
  }
  return res.json();
}

export async function loginUser(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Login failed');
  }
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

// ----------------- Conversations -----------------
export async function fetchConversations(): Promise<Conversation[]> {
  const res = await fetch(`${API_BASE}/conversations`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(`Failed to fetch conversations: ${res.statusText}`);
  return res.json();
}

export async function fetchConversation(id: string): Promise<ConversationDetail> {
  const res = await fetch(`${API_BASE}/conversations/${id}`, {
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(`Failed to fetch conversation: ${res.statusText}`);
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
  if (!res.ok) throw new Error(`Failed to create conversation: ${res.statusText}`);
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
  if (!res.ok) throw new Error(`Failed to update conversation: ${res.statusText}`);
  return res.json();
}

export async function deleteConversation(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/conversations/${id}`, {
    method: 'DELETE',
    headers: { ...getAuthHeader() },
  });
  if (!res.ok) throw new Error(`Failed to delete conversation: ${res.statusText}`);
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
  conversationId?: string;
  message: string;
  model?: string;
  temperature?: number;
  abortSignal?: AbortSignal;
  onChunk: (delta: string) => void;
  onInit?: (data: { conversation_id: string; user_message_id: string }) => void;
  onDone?: (data: { conversation_id: string; assistant_message_id: string }) => void;
  onError?: (error: Error) => void;
}

export async function streamChat({
  conversationId,
  message,
  model,
  temperature = 0.7,
  abortSignal,
  onChunk,
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
        stream: true,
      }),
      signal: abortSignal,
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Chat API error (${response.status}): ${errText}`);
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
      console.log('Stream request aborted by user');
      return;
    }
    console.error('Stream chat exception:', err);
    if (onError) onError(err);
    throw err;
  }
}
