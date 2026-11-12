# AUREVON AI (v2.0)

<div align="center">
  <img src="frontend/public/logo.svg" width="115" height="115" alt="AUREVON AI Logo" />
  <h3>Independent, Open-Source-First, Multimodal AI Assistant Platform</h3>
  <p>Centralized Intelligence Core • Owner Administration Console • Local & Hosted Inference • Document RAG • Long-Term Memory • Autonomous Agents</p>
</div>

---

## Overview

**AUREVON AI v2.0** upgrades the v1.0 platform into a production-ready AI web ecosystem designed around clarity, model independence, privacy, and operational observability.

It supports two first-class deployment modes without changing application code:
1. **Local Development Mode**: SQLite (`aurevon.db`) + local [Ollama](https://ollama.com) runtime (`qwen2.5:3b` by default) tuned for modest consumer hardware (Windows 11, CPU/integrated graphics, 16 GB RAM).
2. **Public Production Mode**: PostgreSQL 16 + decoupled hosted cloud/GPU OpenAI-compatible inference (`PRODUCTION_INFERENCE_URL` / Groq / OpenAI / DeepSeek) served behind Nginx, keeping public traffic completely independent of any developer laptop.

---

## Key Capabilities in v2.0

### 1. Owner-Only Administration & Security (`/admin`)
- **Role-Based Access Control**: Public `/api/auth/register` always creates ordinary `role="user"` accounts. Owner privileges (`role="owner"`) are granted only via one-time secure bootstrap or explicit promotion by an existing owner.
- **Dedicated Admin Flow**: `/api/auth/admin-login` and `/admin` Owner Console reject non-owner accounts with HTTP `403` and isolate admin-only endpoints under `require_admin`.
- **Account Management**: Paginated user directory with search/filtering, conversation and token totals, account suspension/reactivation (blocking both login and active JWTs), and protection against self-suspension or removing the final owner.
- **Strict Tenant Isolation**: Ordinary users and guests are isolated across conversations, memories, uploaded documents (UUID-prefixed filenames), and agent runs.
- **API Hardening**: Sliding-window rate limiting (`429`) on auth, chat, agent, and upload routes; restricted CORS methods/headers; configurable OpenAPI docs disabling (`ENABLE_DOCS=false`); and sanitized exception handling.

### 2. AUREVON Owner Console (`/admin`)
- **Platform Overview**: Total registered users, 24h / 7d / 30d active users, total conversations, AI requests, successes, failures, and success percentage.
- **AI Performance Telemetry**: Average, median, and P95 response latency, time-to-first-token (TTFT), prompt/completion/total token counts captured from real provider completion metadata, requests per minute/day, and error category breakdowns. Missing samples remain `N/A` (`null`) rather than synthetic zeros.
- **Visual Analytics**: Six interactive SVG telemetry views (Daily Request Volume, User Growth, Token Consumption, Latency Trend, Model Utilization, Error Frequency) with `24h`, `7d`, `30d`, and custom date range filters.
- **Live System Monitoring**: Real-time backend status, database connectivity & dialect, provider health checks, OS CPU/RAM utilization, process RSS memory, recent failed AI requests, and recent application error ring buffer.
- **Privacy-Safe Usage Logging**: `ai_request_logs` records timing, tokens, model/provider, and error categories—never full user prompts or assistant responses by default.

### 3. Centralized AUREVON Intelligence Core
- **Server-Side Model Pinning**: Enforces the active model, provider, context window, and temperature on the backend (`SystemAIConfig`). When `allow_user_model_switching` is `false` (v2.0 default), ordinary user requests cannot override the server model.
- **Versioned Master System Prompts**: Manage, create, and roll back `SystemPromptVersion` instructions cleanly from `/admin` without code redeploys.
- **Grounded Pipelines & Graceful Failover**: Optional memory injection, document RAG retrieval, agent tool execution guards (`enable_agent_tools`), primary->fallback provider failover, and honest offline web research notifications.

### 4. Refined Dual-Theme Workspace UI
- **Minimalist Design System**: Neutral stone Light theme and low-glare obsidian Dark theme powered by CSS custom property tokens, responsive layout (`100dvh`), readable typography, collapsible navigation, markdown/code rendering, and dedicated `/admin` Owner Console.
- **End-to-End Subsystems**: SSE chat streaming, image vision capability checks, semantic document upload/RAG, long-term memory editor, sandboxed AST calculator/analyzer agents, and DuckDuckGo research citations.

---

## Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, Framer Motion, Lucide React, React Markdown, Remark GFM |
| **Backend** | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (Async), Alembic, HTTPX, Uvicorn |
| **Database** | SQLite Async (`aiosqlite`, local default) / PostgreSQL 16 (`asyncpg`, production) |
| **AI Providers** | Ollama local runtime (`qwen2.5:3b` default), Hosted OpenAI-compatible endpoints, OpenAI, Groq, DeepSeek |
| **Deployment** | Docker, Docker Compose, Nginx Alpine (unbuffered SSE + SPA routing) |

---

## Local Development Setup (Windows / macOS / Linux)

### 1. Environment Configuration
Copy [`backend/.env.example`](backend/.env.example) to `backend/.env` if customizing local settings:
```powershell
Copy-Item backend\.env.example backend\.env
```

### 2. Launch Development Servers (PowerShell)
```powershell
.\scripts\run_dev.ps1
```
- **Web Interface**: `http://127.0.0.1:5173`
- **Owner Console**: `http://127.0.0.1:5173/admin`
- **Backend API**: `http://127.0.0.1:8000`
- **API Docs**: `http://127.0.0.1:8000/docs`

### 3. Bootstrap the First Owner Account
You can initialize the first owner via the `/admin` bootstrap form (allowed once in `development` mode, or when `ADMIN_BOOTSTRAP_TOKEN` matches) **or** via the CLI:
```powershell
& "backend\.venv\Scripts\python.exe" -m backend.scripts.bootstrap_owner --username owner --email owner@example.com
```
Once an owner exists, public/web owner bootstrap is permanently locked (`403`). Additional owners can only be promoted via CLI (`--promote-existing`) or an authenticated owner in `/admin`.

---

## AUREVON Control Centre (`/admin`)

The private owner-only **AUREVON Control Centre** provides dark-first operational control across 8 dedicated routes:
- `/admin` — Real-time KPIs (`24h`, `7d`, `30d`, `90d`, `custom`), throughput, latency percentiles (`avg`, `median`, `p95`, `TTFT`), token consumption, and model utilization.
- `/admin/terminal` — Audited, allowlist-enforced operations terminal (`status`, `system diagnostics`, `db stats`, `ai test`, `users count`, `logs recent`, `cache clear` with interactive confirmation) — zero arbitrary OS shell or SQL execution.
- `/admin/ai` — Live AI connectivity probe (`POST /api/admin/ai/test`), centralized provider/model pinning, context/temperature defaults, runtime API keys, and versioned master system prompts.
- `/admin/users` — Searchable account directory, status suspension/reactivation, role governance, and privacy-safe metadata drawer (never exposes passwords, tokens, or chat contents).
- `/admin/system` — Host/container CPU, RAM, process RSS, disk storage, uptime, TTL cache inspector, and live diagnostics suite.
- `/admin/logs` — Paginated HTTP request telemetry, owner audit trail, error feeds, and retention pruning (`POST /api/admin/logs/prune`).
- `/admin/security` — Optional RFC 6238 TOTP 2FA setup/verification, JWT logout revocation (`POST /api/auth/logout`), and security event log.
- `/admin/settings` — Runtime maintenance mode (`503` guard), public signup policy, API telemetry toggle, and live sliding-window rate limits.

---

## Public Production Deployment (Docker Compose)

Production deployments use **PostgreSQL 16** and a **decoupled hosted inference API** (such as Groq, OpenAI, vLLM, or any OpenAI-compatible GPU server) so public web users never depend on a local developer machine.

### 1. Configure `.env`
```bash
cp .env.production.example .env
```
Set strong values for `POSTGRES_PASSWORD`, `SECRET_KEY`, `ADMIN_BOOTSTRAP_TOKEN`, `CORS_ORIGINS`, `PRODUCTION_INFERENCE_URL`, `PRODUCTION_INFERENCE_API_KEY`, and `PRODUCTION_DEFAULT_MODEL`. Never commit `.env` or API secrets.

### 2. Start PostgreSQL, FastAPI & Nginx
```bash
docker compose up -d --build
docker compose exec backend alembic -c alembic.ini upgrade head
docker compose exec backend python -m backend.scripts.bootstrap_owner
```
- **Web UI & Owner Console**: `http://localhost:3000` and `http://localhost:3000/admin` (place behind TLS/reverse proxy in public hosting)
- **Backend API**: `http://localhost:8000`

*(Optional)* To run a dedicated private Ollama container alongside Docker Compose instead of an external inference API:
```bash
docker compose --profile selfhost-ollama up -d --build
```

---

## Database Migrations (Non-Destructive)

Existing v1.0 SQLite databases (`aurevon.db`) are upgraded non-destructively at startup via `init_db()` (`_apply_v2_column_upgrades`) or explicitly with Alembic:
```powershell
& "backend\.venv\Scripts\python.exe" -m alembic -c alembic.ini upgrade head
```

---

## Verification & Build Commands

### Backend Automated Test Suite
```powershell
& "backend\.venv\Scripts\python.exe" -m pytest backend/tests/ -v
```

### Frontend Typecheck & Production Build
```powershell
cd frontend
npm run build
```

---

## License

AUREVON AI is open-source software released under the Apache 2.0 License.
