# AUREVON AI — REST API Reference

The backend exposes a clean REST API built with FastAPI. Interactive OpenAPI documentation is available locally at `http://127.0.0.1:8000/docs`.

---

## 1. System Health & Models

### `GET /api/health`
Checks backend status, database connectivity, and configured AI providers.

**Response:**
```json
{
  "app_name": "AUREVON AI",
  "version": "0.1.0",
  "database": "connected",
  "providers": [
    {
      "provider": "ollama",
      "status": "healthy",
      "url": "http://127.0.0.1:11434",
      "available_models": ["qwen2.5:3b", "qwen3:4b"],
      "error_message": null
    }
  ]
}
```

### `GET /api/models`
Returns available models with capability flags and parameter metadata.

### `GET /api/models/health`
Returns live health metadata for the primary AI provider.

---

## 2. Conversations

### `GET /api/conversations`
Lists conversations ordered by `updated_at` descending.

### `POST /api/conversations`
Creates a new conversation.

**Request Body:**
```json
{
  "title": "Quantum Computing Architecture"
}
```

### `GET /api/conversations/{id}`
Retrieves a conversation thread with all associated messages.

### `PATCH /api/conversations/{id}`
Renames a conversation.

**Request Body:**
```json
{
  "title": "Renamed Title"
}
```

### `DELETE /api/conversations/{id}`
Deletes a conversation and its messages.

---

## 3. Streaming Chat

### `POST /api/chat`
Dispatches a user prompt to the conversation context and streams back token chunks via Server-Sent Events (SSE).

**Request Body:**
```json
{
  "conversation_id": "optional-uuid-here",
  "message": "Explain how GGUF quantization works.",
  "model": "qwen2.5:3b",
  "temperature": 0.7,
  "stream": true
}
```

**SSE Event Stream:**
```text
data: {"conversation_id": "...", "user_message_id": "...", "delta": "", "done": false}

data: {"conversation_id": "...", "delta": "GGUF", "done": false}

data: {"conversation_id": "...", "delta": " is a format...", "done": false}

data: {"conversation_id": "...", "assistant_message_id": "...", "delta": "", "done": true}
```
