# AUREVON AI — Development Guide

## Prerequisites

- **OS**: Windows 11 / Linux / macOS
- **Python**: 3.12+ (or managed with `uv`)
- **Node.js**: 20+ (Node 24 recommended)
- **Local AI Runtime**: [Ollama](https://ollama.com) (Recommended initial model: `qwen2.5:3b` or `qwen3:4b`)
- **Database**: PostgreSQL (Production) or SQLite (automatic zero-config development default)

---

## Quick Start (Windows PowerShell)

### 1. Launch the Complete Development Environment
Run the launcher script:
```powershell
.\scripts\run_dev.ps1
```
This starts:
- Frontend: `http://127.0.0.1:5173`
- Backend: `http://127.0.0.1:8000`
- Interactive API Docs: `http://127.0.0.1:8000/docs`

---

## Manual Step-by-Step Setup

### Backend Setup
1. Open PowerShell and navigate to the project directory:
   ```powershell
   cd c:\Users\abdur\OneDrive\Desktop\AUREVON-AI
   ```

2. Create virtual environment and install dependencies:
   ```powershell
   uv venv backend/.venv
   uv pip install -r backend/requirements.txt --python backend/.venv/Scripts/python.exe
   ```

3. Configure environment:
   ```powershell
   Copy-Item backend\.env.example backend\.env
   ```

4. Run the FastAPI development server:
   ```powershell
   $env:PYTHONPATH = (Get-Location).Path
   & "backend\.venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

### Frontend Setup
1. Open a new terminal and navigate to `frontend`:
   ```powershell
   cd frontend
   npm install
   ```

2. Start Vite development server:
   ```powershell
   npm run dev
   ```

---

## Running Automated Tests

Run backend integration and acceptance test suite:
```powershell
$env:PYTHONPATH = (Get-Location).Path
& "backend\.venv\Scripts\python.exe" -m pytest backend/tests/ -v
```

Run frontend production build verification:
```powershell
cd frontend
npm run build
```

---

## Connecting Ollama Local AI

1. Install Ollama:
   ```powershell
   winget install Ollama.Ollama
   ```
2. Pull recommended local models:
   ```powershell
   ollama run qwen2.5:3b
   ```
   *(Or for 4B target: `ollama run qwen3:4b`)*
3. AUREVON automatically connects to `http://127.0.0.1:11434` and discovers installed models dynamically.
