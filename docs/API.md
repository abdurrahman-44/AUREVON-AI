# AUREVON AI — Complete REST & Streaming API Reference (v1.0)

Base URL: `http://localhost:8000/api` (or `/api` behind Nginx proxy)

All protected endpoints accept the `Authorization: Bearer <jwt_token>` header.

---

## 1. System & Health

### `GET /api/health`
Returns system health, database connectivity status, and model provider diagnostics.
- **Auth**: None
- **Response `200 OK`**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "connected",
  "providers": [
    {
      "provider": "ollama",
      "status": "healthy",
      "url": "http://127.0.0.1:11434",
      "available_models": ["qwen2.5:3b", "llava:7b"],
      "error_message": null
    }
  ]
}
```

---

## 2. Authentication & Accounts

### `POST /api/auth/register`
Creates a new user account.
- **Body**:
```json
{
  "email": "user@aurevon.ai",
  "username": "aurevon_user",
  "password": "StrongPassword123!"
}
```
- **Response `200 OK`**: User profile and JWT bearer token.

### `POST /api/auth/login`
Authenticates user and returns JWT.
- **Body**:
```json
{
  "email": "user@aurevon.ai",
  "password": "StrongPassword123!"
}
```
- **Response `200 OK`**: Returns access token and user profile.

### `GET /api/auth/me`
Retrieves currently authenticated user profile and settings.
- **Auth**: Bearer token

---

## 3. User Settings

### `GET /api/settings`
Retrieves settings for current user.

### `PATCH /api/settings`
Updates user settings.
- **Body**:
```json
{
  "theme": "dark",
  "default_model": "qwen2.5:3b",
  "temperature": 0.7,
  "system_prompt": "You are AUREVON AI.",
  "memory_enabled": true
}
```

---

## 4. Conversations & Messaging

### `GET /api/conversations`
Lists all conversations belonging to the current user (or guest session).

### `POST /api/conversations`
Creates a new conversation.
- **Body**: `{"title": "My New Conversation"}`

### `GET /api/conversations/{id}`
Returns conversation details including all chronologically ordered messages.

### `PATCH /api/conversations/{id}`
Renames conversation title.
- **Body**: `{"title": "Updated Title"}`

### `DELETE /api/conversations/{id}`
Deletes conversation and associated messages.

---

## 5. Real-Time Streaming Chat

### `POST /api/chat`
Streams real-time token chunks via Server-Sent Events (SSE).
- **Body**:
```json
{
  "conversation_id": "optional-uuid",
  "message": "Explain quantum computing",
  "model": "qwen2.5:3b",
  "temperature": 0.7,
  "stream": true,
  "images": ["optional_base64_image_data"]
}
```
- **Response**: `text/event-stream` delivering SSE events:
  - `data: {"conversation_id": "...", "user_message_id": "...", "delta": "", "done": false}`
  - `data: {"conversation_id": "...", "delta": "token", "done": false}`
  - `data: {"conversation_id": "...", "assistant_message_id": "...", "delta": "", "done": true}`

---

## 6. AI Model Management

### `GET /api/models`
Returns unified catalog of available local and cloud models with capabilities metadata.

### `POST /api/models/pull`
Pulls an Ollama model asynchronously.
- **Body**: `{"model_name": "qwen2.5:3b"}`

### `POST /api/models/keys`
Configures cloud provider API keys in memory.
- **Body**:
```json
{
  "provider": "openai",
  "api_key": "sk-proj-..."
}
```

---

## 7. Document Intelligence & RAG

### `POST /api/documents/upload`
Uploads and indexes a document for semantic retrieval.
- **Content-Type**: `multipart/form-data` (file: Binary, title: Optional String)
- **Supported Formats**: PDF, TXT, Markdown, CSV, Python, JS, TS, HTML.

### `GET /api/documents`
Lists uploaded documents with chunk count and parsing status.

### `POST /api/documents/query`
Performs standalone semantic RAG similarity search across document chunks.
- **Body**: `{"query": "revenue metrics 2024", "top_k": 3}`

### `DELETE /api/documents/{id}`
Deletes document and all associated embedding chunks.

---

## 8. Long-Term Semantic Memory

### `GET /api/memory`
Lists all long-term user memories.

### `POST /api/memory`
Creates a new memory entry.
- **Body**:
```json
{
  "content": "User prefers concise TypeScript without semicolons",
  "category": "preference"
}
```

### `PATCH /api/memory/{id}`
Updates a memory or toggles `is_active`.
- **Body**: `{"is_active": false}`

### `DELETE /api/memory/{id}`
Deletes a memory record permanently.

---

## 9. Autonomous Web Research

### `POST /api/research`
Executes real-time web search and synthesizes grounded research report.
- **Body**:
```json
{
  "query": "Solid-state battery breakthroughs 2025",
  "max_sources": 4
}
```
- **Response `200 OK`**:
```json
{
  "query": "Solid-state battery breakthroughs 2025",
  "sources": [
    {
      "title": "Article Title",
      "url": "https://example.com/article",
      "snippet": "Summary snippet..."
    }
  ],
  "synthesis": "Comprehensive markdown synthesis report..."
}
```

---

## 10. Autonomous Agent Platform

### `GET /api/agents/tools`
Lists all registered sandboxed tools (`calculator`, `code_analyzer`, `search`, `doc_search`).

### `POST /api/agents/run`
Dispatches a multi-step autonomous agent execution run.
- **Body**:
```json
{
  "task": "Calculate (150 * 4) / 2 + 25 and inspect code 'def test(): pass'",
  "model": "qwen2.5:3b"
}
```
- **Response `200 OK`**: Returns run ID, step-by-step trace log with tool inputs/outputs, and final synthesized output.

### `GET /api/agents/runs`
Returns past agent execution audit history.
