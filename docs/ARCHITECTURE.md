# AUREVON AI — System Architecture Specification (v1.0)

## 1. Architectural Philosophy

AUREVON AI is built upon five foundational architectural tenets:
1. **Model Independence**: Pluggable provider abstraction isolating application workflows from specific LLM runtimes.
2. **Privacy and Open-Source First**: Optimized for local CPU execution via Ollama without requiring dedicated GPU or CUDA hardware, with seamless cloud failover when desired.
3. **Multi-Layered Context Grounding**: Responses are enriched through three synergistic retrieval layers: conversation short-term memory, long-term episodic facts, and RAG document vectors.
4. **Autonomous Agent Tooling**: Multi-step reasoning pipeline combining sandboxed AST static analysis, safe AST calculators, web discovery, and semantic knowledge retrieval.
5. **Production Hardening**: Strictly decoupled SPA architecture, non-root Docker execution, asynchronous I/O, and zero untyped code paths.

---

## 2. High-Level System Architecture

```mermaid
flowchart TD
    User([User Browser])
    
    subgraph Frontend ["Frontend (React 18 + Vite + Tailwind CSS)"]
        UI[Chat Interface / Workspace]
        Sidebar[Sidebar & History Navigation]
        Composer[Composer & Multimodal Attachment]
        Modals[Documents, Memory, Research, Agents, Models, Settings]
    end

    subgraph NginxGateway ["Edge Layer (Nginx Reverse Proxy)"]
        Nginx[Nginx Alpine Proxy / Port 80/3000]
    end

    subgraph BackendCore ["Backend Core (FastAPI Asynchronous Engine)"]
        API[API Router / Middleware / JWT Security]
        ChatEngine[SSE Token Streaming Engine]
        ContextEnricher[Context Enrichment Pipeline]
        AgentRunner[Autonomous Agent Engine]
        ModelRouter[Model Routing & Capability Checker]
    end

    subgraph KnowledgeLayer ["Knowledge & Retrieval Systems"]
        RAG[RAG Document Service & Semantic Chunker]
        MemoryMgr[Long-Term Memory Manager]
        WebResearch[Live Web Research Engine]
    end

    subgraph ToolRegistry ["Sandboxed Agent Tools"]
        SafeCalc[Safe AST Math Calculator]
        ASTAnalyzer[AST Python Static Code Analyzer]
        DocSearch[Semantic Document Search Tool]
        WebSearch[DuckDuckGo Web Search Tool]
    end

    subgraph StorageLayer ["Persistence Layer"]
        Postgres[(PostgreSQL 16 Relational DB / SQLite Dev)]
        DocStorage[Document File Repository]
    end

    subgraph InferenceLayer ["Inference Layer (Pluggable)"]
        OllamaLocal[Ollama Local Runtime (qwen2.5, llava)]
        OpenAICloud[OpenAI (GPT-4o, GPT-4o-mini)]
        GroqCloud[Groq (Llama-3.3-70B)]
        DeepSeekCloud[DeepSeek (DeepSeek-Chat)]
    end

    User --> Nginx
    Nginx --> UI
    Nginx --> API
    API --> ChatEngine
    ChatEngine --> ContextEnricher
    ChatEngine --> ModelRouter
    ContextEnricher --> MemoryMgr
    ContextEnricher --> RAG
    API --> AgentRunner
    AgentRunner --> ToolRegistry
    MemoryMgr --> StorageLayer
    RAG --> StorageLayer
    API --> StorageLayer
    ModelRouter --> InferenceLayer
```

---

## 3. Core Subsystems

### 3.1 Pluggable Model Provider Architecture (`BaseAIProvider`)
All AI model providers implement a common asynchronous interface:
- `check_health() -> ProviderHealth`
- `list_models() -> List[ModelInfo]`
- `stream_chat(messages, model, temperature, context_window) -> AsyncGenerator[str, None]`
- `complete_chat(messages, model, temperature, context_window) -> str`

The `ProviderFactory` manages active provider singletons (`OllamaProvider`, `OpenAICompatibleProvider`). When a user selects a model:
- `chat.py` automatically routes the request to the matching provider.
- `check_model_vision_capability` verifies if the target model supports multimodal images. If a text-only model is selected with an image, an informative capability notice is returned without crashing.

### 3.2 Context Enrichment Pipeline
Before a prompt is forwarded to the LLM runtime, `chat.py` executes context enrichment:
1. **Recent History**: Last 20 messages of the active conversation.
2. **User Memory Retrieval**: Queries active memories relevant to the user query and injects them under system instructions.
3. **RAG Semantic Search**: Computes prompt embedding, retrieves the most similar document chunks, and formats grounded source context.

### 3.3 Autonomous Agent Architecture
The `AgentRunner` executes complex multi-step reasoning tasks:
1. **Planning Step**: Interprets the user's objective and constructs an execution plan.
2. **Tool Execution Step**: Executes sandboxed tools from the registry (`SafeCalculator`, `ASTCodeAnalyzer`, `WebSearchTool`, `DocumentSearchTool`).
   - Every tool input and output is validated and recorded.
   - Code execution is strictly sandboxed using Python AST parsing—arbitrary shell code execution is disallowed.
3. **Synthesis Step**: Aggregates all intermediate observations and synthesizes a final verified answer.
4. **Audit Trail**: Every execution run is persisted to `agent_runs` in the database for auditing and review.

### 3.4 Production Deployment Architecture
- **Multi-stage backend container**: Runs on `python:3.12-slim-bookworm` as an unprivileged user `appuser`.
- **Multi-stage frontend container**: Compiles static assets with Vite and serves them through high-performance `nginx:alpine`.
- **Database**: PostgreSQL 16 Alpine container with persistent named volume `postgres_data` and automatic schema creation on startup.
