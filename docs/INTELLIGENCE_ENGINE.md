# AUREVON AI — Intelligence Engine Guide

The **AUREVON Intelligence Engine** upgrades the core chat assistant with deterministic 12-intent routing, warm local-first Ollama model orchestration, a modular security-sandboxed tool engine, rolling conversation summarization, hybrid SQLite FTS5 + semantic RAG, optional consent-gated cloud inference, and deep Control Centre / Admin Terminal observability.

---

## 1. Architecture Overview

| Subsystem | Implementation | Key Behavior |
| :--- | :--- | :--- |
| **Intent Router** | [`backend/app/services/ai/router.py`](../backend/app/services/ai/router.py) (`RequestRouter`) | Deterministic classification across 16 categories (`greeting`, `general`, `knowledge`, `reasoning`, `math`, `programming`, `document_analysis`, `web_research`, `data_analysis`, `memory`, `tool_execution`, `app_help`, `weather`, `news`, `currency`, `age_date_calc`) without slow extra LLM calls. |
| **Fast Greeting Path** | [`backend/app/api/routes/chat.py`](../backend/app/api/routes/chat.py) | Pure greetings (`Hi`, `Hello`, `Hey`, `Good morning`, `Thanks`) stream back deterministically and persist in DB without waiting on LLM/RAG/Memory (measured `488.3 ms` cold ASGI round-trip vs historical `34,231.5 ms` average). |
| **Live Intelligence** | [`backend/app/services/live/`](../backend/app/services/live/) | Zero-key Open-Meteo live weather & forecasts, Frankfurter/OpenExchange financial forex rates, and DuckDuckGo news intelligence with resilient offline baselines. |
| **Date & Age Engine** | [`backend/app/services/tools/date_calculator.py`](../backend/app/services/tools/date_calculator.py) | Deterministic calendar-accurate exact age calculation (e.g., DOB: 15 March 2004, Current: 13 Nov 2026 -> 22 years, 7 months, 29 days; handling leap years and Feb 29), working days, and date differences. |
| **Model Manager** | [`backend/app/services/ai/model_manager.py`](../backend/app/services/ai/model_manager.py) (`ModelManager`) | Live Ollama `/api/tags` + `/api/ps` discovery, `_model_load_lock` cold-load serialization, `KEEP_ALIVE_SECONDS=900`, specialist routing, Google Gemini API adapter, and cloud consent/daily-limit enforcement. |
| **Tool Engine** | [`backend/app/services/tools/`](../backend/app/services/tools/) | 9 policy-governed tools (`calculator`, `date_time`, `weather`, `currency_converter`, `news_search`, `python_data_analysis`, `knowledge_retrieval`, `document_reader`, `web_search`), validated schemas, bounded loops (`MAX_TOOL_ITERATIONS=3`), and `ToolExecutionLog` auditing. |
| **Conversation Memory** | [`backend/app/repositories/message_repo.py`](../backend/app/repositories/message_repo.py), [`summarizer.py`](../backend/app/services/memory/summarizer.py), [`manager.py`](../backend/app/services/memory/manager.py) | Preserves the newest `N` turns chronologically, generates rolling `ConversationSummary` snapshots beyond 14 turns, and stores persistent memories only on explicit user opt-in (`Remember that...`). |
| **Hybrid Local RAG** | [`backend/app/services/documents/rag.py`](../backend/app/services/documents/rag.py), [`extractor.py`](../backend/app/services/documents/extractor.py) | Extracts `.pdf`, `.docx`, `.xlsx`, `.csv`, `.txt`, code files; deduplicates via SHA-256 `content_hash`; indexes via SQLite `document_chunks_fts` (FTS5) + deterministic cosine vectors; redacts prompt injections inside `<document_context untrusted="true">`. |

---

## 2. Managing Local Ollama Models (Windows CMD & PowerShell)

AUREVON does **not** auto-download large models on startup. Pull only the models appropriate for your RAM/hardware:

### Install / Pull a Model (Windows CMD or PowerShell)
```cmd
ollama pull qwen2.5:3b
ollama pull qwen3:4b
```
*(Optional coding specialist if your machine has sufficient RAM: `ollama pull qwen2.5-coder:3b` or `qwen2.5-coder:7b`)*

### Verify Installed & Loaded Models
```cmd
ollama list
ollama ps
```

### Select Primary, Coding, or Fallback Model
1. Sign in as owner at `http://127.0.0.1:5173/admin`.
2. Open **AI Management -> Models** (`/admin/ai/models`).
3. Inspect discovered models from `/api/tags` and active RAM state from `/api/ps`.
4. Select your **Primary Model** (and optional **Coding Specialist** or **Fallback Model**), tune `temperature`, `context_window`, `max_output_tokens`, and `keep_alive_seconds`, then click **Test Connectivity** or save changes.
   - Or inspect quickly from **Admin Terminal** (`/admin/terminal`): run `ai model`, `ai models`, or `ai test`.

---

## 3. Tool Engine & Security Sandbox

### Available Tools
- **`calculator`**: AST-evaluated arithmetic, scientific functions (`sqrt`, `sin`, `cos`, `log`, `factorial`), percentages (`15% of 240`), and unit conversions (`5 km to m`, temperature, mass, time, data). No `eval()`.
- **`date_time`**: Timezone-aware local/UTC ISO date, time, day of week, day offsets, and deterministic age/calendar calculations (`DateCalculator`).
- **`weather`**: Real-time meteorological intelligence and multi-day forecasts via Open-Meteo REST API (zero API key required) with geocoding and resilient offline baseline fallbacks.
- **`currency_converter`**: Live currency conversion and exchange rates via Frankfurter API (European Central Bank data) with Open Exchange Rates fallback and offline baseline support.
- **`news_search`**: Recent news article discovery and headline summaries across AI, technology, science, business, and regional topics via DuckDuckGo news intelligence.
- **`python_data_analysis`**: Isolated `python -I -B` subprocess with AST import/builtin allowlist (`math`, `statistics`, `json`, `csv`, `collections`, `itertools`, `datetime`, `decimal`, `fractions`, `re`, `random`), scrubbed environment variables (zero app secrets), temporary isolated working directory, timeout enforcement (`PYTHON_SANDBOX_TIMEOUT_SECONDS=6`), POSIX memory limits, and XSS-sanitized SVG helpers (`plot_bar`, `plot_line`).
- **`knowledge_retrieval`**: Tenant-isolated hybrid FTS5 + vector search over indexed documents.
- **`document_reader`**: Owner/tenant-scoped document chunk reader.
- **`web_search`**: Live web search intelligence with citation extraction (domain, title, snippet, and URL).

### Enable / Disable Tools
- Navigate to `/admin/ai/tools` in Control Centre (or run `ai tools` / `ai tools list` in Admin Terminal).
- Toggle `is_enabled`, change `permission_level` (`standard`, `owner_only`, `disabled`), adjust `timeout_seconds`, and set `max_calls_per_request`.
- Tool controls require owner authentication (`require_admin`); ordinary users never see admin controls or internal prompts.

---

## 4. Optional Cloud Providers & Privacy Governance

Local Ollama inference is always the default. Cloud inference (`openai`, `groq`, `deepseek`, hosted `production`) is **disabled by default**.

### Enable Optional Cloud Inference
1. Set provider credentials in `backend/.env` (never in frontend code):
   ```ini
   CLOUD_INFERENCE_ENABLED=true
   REQUIRE_CLOUD_CONSENT=true
   CLOUD_DAILY_REQUEST_LIMIT=100
   OPENAI_API_KEY=sk-...
   ```
2. Or configure runtime keys securely in Control Centre (`/admin/ai/providers`).
3. When `REQUIRE_CLOUD_CONSENT=true`, individual chat requests only route to a cloud provider when the user explicitly toggles **Cloud** consent (`allow_cloud=true`) in the chat composer; otherwise `ModelManager.select_route_model` automatically falls back to local Ollama.

### Disable Cloud Processing Completely
- Set `CLOUD_INFERENCE_ENABLED=false` in `backend/.env` or toggle **Cloud Inference Disabled** under `/admin/ai/providers` (or `/admin/intelligence`). Any request targeting a cloud provider automatically falls back to local Ollama.

---

## 5. Inspecting AI Performance & Knowledge Indexes

### Control Centre Web UI
- `/admin/ai` — Intelligence Core overview, active prompt versioning, safety flags.
- `/admin/ai/models` — Discovered Ollama models, RAM footprint, model pinning, connectivity test.
- `/admin/ai/tools` — Tool status, call counts, failure counts, average durations, permission policies.
- `/admin/ai/performance` — 24h / 7d / 30d latency percentiles (`avg`, `median`, `p95`), TTFT, success rate, and per-intent breakdown.
- `/admin/ai/knowledge` — Indexed documents, SHA-256 hashes, FTS5 chunk counts, one-click **Rebuild FTS5 Index**.
- `/admin/ai/providers` — Cloud policy gates, configured key booleans (never raw secrets), token/cost summary (`ProviderUsageLog`).

### Admin Terminal Allowlisted AI Commands (`/admin/terminal`)
- `ai status` — Current active provider, model, flags, key presence.
- `ai model` — Active model, coding specialist, fallback target, context/output tokens, keep-alive, RAM-loaded models.
- `ai models` — Multi-provider model discovery.
- `ai test` — Live connectivity probe to active provider/model.
- `ai latency` — 24h / 7d avg, P95 latency, avg TTFT, success rate.
- `ai memory` — User memories count, conversation summaries count, Ollama RAM usage.
- `ai tools` / `ai tools list` — Tool registry state and execution telemetry.
- `ai knowledge status` — Document, chunk, and SQLite FTS5 index counts.
- `ai diagnostics` — Unified intelligence health report.
- `ai weather [location]` — Live meteorological query via Open-Meteo geocoding and forecast API (e.g. `ai weather Mawanella`).
- `ai news [topic]` — Live news search and recent article citations via DuckDuckGo news intelligence (e.g. `ai news ai`).
- `ai currency [from] [to]` — Live forex conversion and exchange rate inspection (e.g. `ai currency USD LKR`).

---

## 6. Environment Variable Reference (`backend/.env`)

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `DEFAULT_PROVIDER` | `ollama` | Primary inference provider |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Local Ollama endpoint |
| `DEFAULT_MODEL` | `qwen2.5:3b` | Default pinned local model |
| `DEFAULT_CODING_MODEL` | `null` | Optional coding specialist model |
| `MODEL_CONTEXT_WINDOW` | `8192` | Context token window passed to provider |
| `MAX_OUTPUT_TOKENS` | `2048` | Max generated completion tokens |
| `KEEP_ALIVE_SECONDS` | `900` | Ollama keep-alive duration in seconds (`15m`) |
| `AI_REQUEST_TIMEOUT_SECONDS` | `120` | Streaming HTTP request timeout |
| `STREAMING_ENABLED` | `true` | Toggle streaming responses |
| `WEB_SEARCH_ENABLED` | `false` | Optional web search tool gate |
| `CLOUD_INFERENCE_ENABLED` | `false` | Master switch allowing cloud inference |
| `REQUIRE_CLOUD_CONSENT` | `true` | Require per-request consent for cloud routing |
| `CLOUD_DAILY_REQUEST_LIMIT` | `100` | Daily cloud request cap before local fallback |
| `TOOL_EXECUTION_TIMEOUT_SECONDS` | `10` | Default per-tool timeout |
| `PYTHON_SANDBOX_TIMEOUT_SECONDS` | `6` | Sandbox execution time limit |
| `PYTHON_SANDBOX_MEMORY_MB` | `128` | Sandbox memory limit (POSIX `rlimit`) |
| `MAX_TOOL_ITERATIONS` | `3` | Maximum reactive tool cycles per turn |

---

## 7. Troubleshooting Guide (Windows CMD)

- **Ollama unreachable (`Ollama daemon is unreachable`)**:
  ```cmd
  ollama serve
  curl http://127.0.0.1:11434/api/tags
  ```
- **Model not loaded / high first-token latency**:
  Keep `KEEP_ALIVE_SECONDS=900` in Control Centre so `qwen2.5:3b` stays warm in RAM (`ollama ps`). Avoid setting `MODEL_CONTEXT_WINDOW` unnecessarily high on 16 GB RAM CPU machines (`8192` is balanced; `4096` lowers RAM pressure).
- **Database schema upgrade from v1/v2**:
  ```cmd
  backend\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
  ```
- **FTS5 search returns empty results on legacy documents**:
  Open `/admin/ai/knowledge` and click **Rebuild FTS5 Index** (`POST /api/admin/ai/knowledge/rebuild`).
