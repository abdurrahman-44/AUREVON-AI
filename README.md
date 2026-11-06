# AUREVON AI

<div align="center">
  <img src="frontend/public/logo.svg" width="110" height="110" alt="AUREVON AI Logo" />
  <h3>Independent, Open-Source-First, Multimodal AI Assistant Platform</h3>
  <p>Local-first inference • Provider-independent architecture • Relational persistence • Private & Extensible</p>
</div>

---

## 🌟 Overview

**AUREVON AI** is an independent, model-independent AI assistant platform engineered for deep reasoning, research, coding, memory, and autonomous workflows.

Unlike single-provider chatbots, AUREVON is architected as an extensible ecosystem that prioritizes:
- **Local AI & User Privacy**: Zero-cloud dependency required — runs locally on consumer hardware via [Ollama](https://ollama.com).
- **Model Independence**: Pluggable AI provider abstraction layer supporting Qwen, Llama, Gemma, and future cloud APIs without codebase rewrites.
- **Persistent Conversational Context**: Relational database storage with schema enforcement, thread management, and multi-turn context retention.
- **Refined Charcoal Dark UI**: Professional, minimalist aesthetic built with React, Vite, Tailwind CSS, Framer Motion, and Markdown syntax highlighting.

---

## 🚀 Phase 1 Foundation (v0.1) — Implemented & Tested

The initial Phase 1 milestone is fully implemented and passes all automated acceptance tests:

- [x] **Real-Time Streamed Chat**: Token-by-token streaming via Server-Sent Events (SSE).
- [x] **Ollama Local AI Provider**: Native integration with local model discovery and status monitoring (`qwen2.5:3b`, `qwen3:4b`, `llama3.2:3b`).
- [x] **Relational Persistence**: PostgreSQL-compatible schema with automatic SQLite development fallback (`sqlite+aiosqlite:///`).
- [x] **Thread & History Management**: Create new chats, rename conversation titles, search chats, and delete conversations.
- [x] **Multi-Turn Context Retention**: Conversation history is windowed and transmitted across consecutive conversational turns.
- [x] **Interactive Markdown & Code**: Code blocks with copy-to-clipboard buttons, syntax highlighting, and formatting.
- [x] **Model Selector**: Switch active models on the fly directly from the message composer.
- [x] **Generation Controls**: Stop generation in real-time using `AbortController`.
- [x] **Automated Acceptance Suite**: Complete end-to-end pytest suite verifying 100% of Phase 1 requirements.

---

## 🛠️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, Framer Motion, Lucide React, React Markdown, Remark GFM |
| **Backend** | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (Async), HTTPX, Uvicorn |
| **Database** | PostgreSQL (`postgresql+asyncpg://`) with SQLite development fallback (`sqlite+aiosqlite://`) |
| **Local AI Runtime** | Ollama (`http://127.0.0.1:11434`) |
| **Target Local Model** | `qwen2.5:3b` / `qwen3:4b` (Configurable via environment variables) |

---

## 💻 Quick Start (Windows 11)

### 1. Launch with One Command
From PowerShell in the project root:
```powershell
.\scripts\run_dev.ps1
```
This automatically launches the FastAPI backend and Vite frontend in parallel:
- **Web Interface**: `http://127.0.0.1:5173`
- **Backend API**: `http://127.0.0.1:8000`
- **Interactive API Documentation**: `http://127.0.0.1:8000/docs`

---

## 📦 Manual Installation & Setup

### 1. Backend Setup
```powershell
# Create virtual environment with uv or python
uv venv backend/.venv

# Install dependencies
uv pip install -r backend/requirements.txt --python backend/.venv/Scripts/python.exe

# Setup environment file
Copy-Item backend\.env.example backend\.env

# Launch backend
$env:PYTHONPATH = (Get-Location).Path
& "backend\.venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend Setup
```powershell
cd frontend
npm install
npm run dev
```

### 3. Setting Up Ollama (Local AI)
To enable local inference:
```powershell
# Install Ollama (Windows)
winget install Ollama.Ollama

# Pull the recommended lightweight model
ollama run qwen2.5:3b
```
AUREVON detects Ollama automatically on startup at `http://127.0.0.1:11434`.

---

## 🧪 Testing & Quality Assurance

Run the automated test suite:
```powershell
$env:PYTHONPATH = (Get-Location).Path
& "backend\.venv\Scripts\python.exe" -m pytest backend/tests/ -v
```
All Phase 1 acceptance criteria (health checks, conversation CRUD, SSE streaming, multi-turn persistence, and thread isolation) pass cleanly.

Verify frontend TypeScript types and production bundle:
```powershell
cd frontend
npm run build
```

---

## 🗺️ Project Structure

```text
AUREVON-AI/
│
├── frontend/                     # React + TypeScript + Vite UI
│   ├── src/
│   │   ├── components/
│   │   │   ├── chat/             # ChatMessage, WelcomeScreen
│   │   │   ├── sidebar/          # Sidebar, ThreadList, Status
│   │   │   ├── composer/         # Composer, Model Selector
│   │   ├── services/             # API client & SSE stream reader
│   │   ├── types/                # TypeScript type definitions
│   │   ├── App.tsx               # Main application controller
│   │   └── main.tsx
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
│
├── backend/                      # FastAPI Backend
│   ├── app/
│   │   ├── api/routes/           # Chat, Conversations, Models, Health
│   │   ├── core/                 # Config & Pydantic settings
│   │   ├── database/             # Async session & engine manager
│   │   ├── models/               # SQLAlchemy ORM entities
│   │   ├── schemas/              # Pydantic request/response schemas
│   │   ├── services/ai/          # Provider abstraction & Ollama engine
│   │   ├── repositories/         # Database access layer
│   │   └── main.py               # FastAPI entrypoint & lifespan
│   ├── tests/                    # Acceptance & integration tests
│   ├── requirements.txt
│   └── .env.example
│
├── docs/                         # Technical Documentation
│   ├── ARCHITECTURE.md           # System design & data flow
│   ├── ROADMAP.md                # 10-Phase progression plan
│   ├── API.md                    # REST endpoint specifications
│   └── DEVELOPMENT.md            # Developer setup instructions
│
├── scripts/                      # PowerShell launcher & helper scripts
│   ├── run_dev.ps1               # Complete app launcher
│   ├── run_backend.ps1           # Backend launcher
│   ├── run_frontend.ps1          # Frontend launcher
│   └── setup_ollama.ps1          # Ollama model setup helper
│
├── .gitignore
├── LICENSE                       # MIT License
└── README.md
```

---

## 🛡️ Security & Privacy Notice
- API keys, local models, and user conversations are never exposed to third-party servers by default.
- Passwords and credentials must not be committed to source control.
- In-memory and local SQLite/PostgreSQL storage reside entirely within your machine.

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
