@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "ROOT=%~dp0"
set "FRONTEND=%ROOT%frontend"
set "BACKEND_PY=%ROOT%backend\.venv\Scripts\python.exe"

title AUREVON AI Launcher
 echo.
 echo  =====================================================
 echo                  AUREVON AI STARTUP
 echo  =====================================================
 echo.

if not exist "%BACKEND_PY%" (
  echo [ERROR] Backend virtual environment was not found:
  echo         %BACKEND_PY%
  echo.
  echo Open Antigravity terminal in the project root and run:
  echo   py -3.12 -m venv backend\.venv
  echo   backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
  echo.
  pause
  exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js was not found in PATH. Install Node.js or fix PATH first.
  pause
  exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm was not found in PATH. Reinstall Node.js with npm included.
  pause
  exit /b 1
)

if not exist "%FRONTEND%\node_modules\vite\bin\vite.js" (
  echo [INFO] Frontend dependencies are missing. Installing them...
  pushd "%FRONTEND%"
  call npm install
  if errorlevel 1 (
    echo [ERROR] npm install failed. Check your internet connection and npm setup.
    popd
    pause
    exit /b 1
  )
  popd
)

where ollama >nul 2>nul
if errorlevel 1 (
  echo [WARNING] Ollama command was not found in PATH. The web app can start, but local AI may be offline.
) else (
  curl.exe -fsS --max-time 2 http://127.0.0.1:11434/api/tags >nul 2>nul
  if errorlevel 1 (
    echo [INFO] Starting Ollama service...
    start "AUREVON - Ollama" cmd /k "ollama serve"
    timeout /t 4 /nobreak >nul
  ) else (
    echo [OK] Ollama is already running.
  )
  ollama list | findstr /i /c:"qwen2.5:3b" >nul
  if errorlevel 1 (
    echo [WARNING] qwen2.5:3b is not installed. Run once: ollama pull qwen2.5:3b
  ) else (
    echo [OK] qwen2.5:3b model is installed.
  )
)

curl.exe -fsS --max-time 2 http://127.0.0.1:8000/ >nul 2>nul
if errorlevel 1 (
  echo [INFO] Starting backend...
  start "AUREVON - Backend" powershell -NoProfile -ExecutionPolicy Bypass -NoExit -File "%ROOT%scripts\run_backend.ps1"
) else (
  echo [OK] Backend already responds on port 8000. Skipping duplicate start.
)

curl.exe -fsS --max-time 2 http://127.0.0.1:5173/ >nul 2>nul
if errorlevel 1 (
  echo [INFO] Starting frontend...
  start "AUREVON - Frontend" powershell -NoProfile -ExecutionPolicy Bypass -NoExit -File "%ROOT%scripts\run_frontend.ps1"
) else (
  echo [OK] Frontend already responds on port 5173. Skipping duplicate start.
)

echo.
echo  Waiting for the web interface...
timeout /t 6 /nobreak >nul
start "" "http://127.0.0.1:5173"
echo.
echo  =====================================================
echo   Startup commands have been issued.
echo   Web UI:      http://127.0.0.1:5173
echo   Backend:     http://127.0.0.1:8000
 echo  API docs:    http://127.0.0.1:8000/docs
 echo  Ollama API:  http://127.0.0.1:11434/api/tags
 echo  =====================================================
echo.
echo Keep the Backend and Frontend PowerShell windows open while using AUREVON.
echo The SQLite database is initialized by the backend during startup.
echo.
pause
endlocal
