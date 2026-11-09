# AUREVON AI (v1.0)

<div align="center">
  <img src="frontend/public/logo.svg" width="115" height="115" alt="AUREVON AI Logo" />
  <h3>Independent, Open-Source-First, Multimodal AI Assistant Platform</h3>
  <p>Local-first inference • Provider-independent architecture • Relational persistence • Document RAG • Long-Term Memory • Autonomous Agents</p>
</div>

---

## 🌟 Executive Overview

**AUREVON AI** is an independent, model-independent AI assistant platform engineered for deep reasoning, research, document intelligence, long-term memory, and autonomous agent workflows.

Designed around consumer hardware constraints (Windows 11, CPU inference, integrated graphics, 16 GB RAM), AUREVON eliminates vendor lock-in by supporting both local privacy-first runtimes ([Ollama](https://ollama.com)) and high-performance cloud providers (OpenAI, Groq, DeepSeek) through a single unified architecture.

---

## 🏆 Full Feature Suite (Phases 1–10 Completed)

### 1. Intelligent Conversational Interface
- **Real-Time Token Streaming**: Server-Sent Events (SSE) stream tokens with zero buffering.
- **Relational Conversation Persistence**: Full CRUD for threads with renaming, deletion, and search.
- **Multi-Turn Context Management**: Context window tracking with automated safe message truncation.
- **Markdown & Syntax Highlighting**: Code blocks with language tagging, copy buttons, and table formatting.

### 2. User Accounts & Security
- **JWT Authentication**: Passwords salted and hashed via PBKDF2 SHA-256.
- **Scoped User Ownership**: Conversations and data isolated per user with guest fallback.
- **Configurable Preferences**: Theme customization (Dark / Light / System), generation temperature, and custom system instructions.

### 3. Model Independence & Provider Hub
- **Unified Catalog**: Simultaneous support for local Ollama models (`qwen2.5:3b`, `llava:7b`, `llama3.2:3b`) and cloud providers (`gpt-4o`, `llama-3.3-70b-versatile`, `deepseek-chat`).
- **Dynamic Model Pulling**: Pull new Ollama models straight from the interface.
- **In-Memory API Key Management**: Configure and hot-swap cloud API keys securely.

### 4. Document Intelligence & Semantic RAG
- **Multi-Format Ingestion**: Supports PDF, TXT, Markdown, CSV, Python, JavaScript, and HTML.
- **Token-Aware Chunking**: Semantic windowing with overlap preserving document structure.
- **Vector Similarity Search**: Asynchronous embedding pipeline retrieving source chunks.
- **Context Grounding**: Assistant automatically cites document references when answering queries.

### 5. Long-Term Semantic Memory
- **Episodic & Fact Extraction**: Persists user preferences, projects, facts, and instructions across conversations.
- **User-Controlled Memory Dashboard**: View, edit, toggle active status, and delete memories.
- **System Prompt Injection**: Active memories are automatically injected into conversational turns.

### 6. Autonomous Web Research
- **Live Search Scraping**: Extracts real-time web results via DuckDuckGo.
- **Multi-Source Synthesis**: Aggregates disparate web findings into a structured research report.
- **Verified Citations**: Displays clickable ground-truth source links with relevant snippets.

### 7. Autonomous Agent Platform
- **Extensible Sandboxed Tools**:
  - `SafeCalculator`: Mathematical expressions evaluated via Python AST parsing (zero `eval()` vulnerabilities).
  - `ASTCodeAnalyzer`: Static AST analysis of Python syntax, functions, classes, and complexity.
  - `WebSearchTool`: Dynamic web intelligence querying.
  - `DocumentSearchTool`: Real-time RAG similarity searches.
- **Multi-Step Execution Pipeline**: Planning -> Tool Invocation -> Grounded Synthesis.
- **Execution Audit Logging**: Persistent trace logs recording every intermediate step, input, and output.

### 8. Multimodal AI (Vision)
- **Image Understanding**: Direct upload and attachment of images (PNG, JPEG, WebP) in chat.
- **Capability Checking**: Model capabilities are enforced—text-only models gracefully warn the user to select a vision model (`llava:7b`, `gpt-4o`) rather than failing.

### 9. Production Orchestration & Docker
- **Docker Compose**: Production-ready configuration orchestrating PostgreSQL 16, FastAPI backend, and Nginx reverse proxy.
- **Hardened Containers**: Python backend runs as unprivileged user `appuser`.
- **Nginx SPA & SSE Proxy**: Static asset caching and unbuffered streaming proxy configuration.

### 10. Comprehensive Verification
- **100% Automated Test Suite**: 11 automated test suites in `backend/tests/` verifying all subsystem acceptance criteria (`11 passed in 47.98s`).

---

## 🛠️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, Framer Motion, Lucide React, React Markdown |
| **Backend** | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (Async), HTTPX, Uvicorn |
| **Database** | PostgreSQL 16 (Production) / SQLite Async (Local Development) |
| **Local Inference** | Ollama (`http://127.0.0.1:11434`) |
| **Deployment** | Docker, Docker Compose, Nginx Alpine, Multi-stage builds |

---

## 💻 Quick Start (Local Development)

### 1. Launch with One Command (PowerShell)
```powershell
.\scripts\run_dev.ps1
```
- **Web UI**: `http://127.0.0.1:5173`
- **Backend API**: `http://127.0.0.1:8000`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`

---

## 🐳 Production Deployment (Docker Compose)

### 1. Configure Environment
```bash
cp .env.production.example .env
```

### 2. Launch Stack
```bash
docker compose up -d --build
```
- **Web UI**: `http://localhost:3000`
- **Backend API**: `http://localhost:8000`
- **PostgreSQL**: Port 5432 (Internal)

---

## 🧪 Verification & Automated Testing

### Run Backend Pytest Suite
```powershell
& "backend\.venv\Scripts\python.exe" -m pytest backend/tests/ -v
```

### Build Frontend Production Assets
```powershell
cd frontend
npm run build
```

---

## 📄 License
AUREVON AI is open-source software released under the Apache 2.0 License.
