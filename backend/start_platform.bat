@echo off
@setlocal EnableDelayedExpansion
title Academic Project Ideation Platform — Offline Unified Launcher
chcp 65001 >nul 2>&1
cd /d "%~dp0"

cls
echo ==============================================================================
echo   ACADEMIC PROJECT IDEATION PLATFORM - OFFLINE UNIFIED LAUNCHER
echo ==============================================================================
echo [*] Initializing offline startup sequence...
echo.

:: ----------------------------------------------------------------------------
:: 1. PRE-FLIGHT CHECKS & ENVIRONMENT VALIDATION
:: ----------------------------------------------------------------------------
echo [1/5] Validating runtime environment and dependencies...

:: Python Check
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python was not found in your system PATH.
    echo Please install Python 3.10+ and ensure it is added to PATH.
    pause
    exit /b 1
)

:: Node / NPM Check
set "NPM_AVAILABLE=1"
where npm >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [WARNING] npm was not found in system PATH.
    echo Frontend UI requires Node.js/NPM to run.
    set "NPM_AVAILABLE=0"
)

:: Ensure data/ directory exists
if not exist "data" (
    mkdir "data"
    echo [INFO] Created local data directory: data\
)

:: Initialize .env if missing
if not exist ".env" (
    if exist ".env.example" (
        copy /y ".env.example" ".env" >nul
        echo [CONFIG] Created .env from .env.example
    ) else (
        (
            echo # Academic Project Ideation Platform Local Configuration
            echo API_PORT=8055
            echo API_HOST=127.0.0.1
            echo SQLITE_DB_PATH=data/academic_ideation.db
            echo OLLAMA_API_URL=http://localhost:11435
            echo OLLAMA_MODEL=qwen2.5-coder:7b
        ) > ".env"
        echo [CONFIG] Generated default .env file
    )
)

:: Ensure frontend dependencies are installed
if "%NPM_AVAILABLE%"=="1" if exist "frontend" (
    if not exist "frontend\node_modules" (
        echo [FRONTEND] node_modules not detected. Installing dependencies via npm...
        pushd "frontend"
        call npm install
        popd
        echo [FRONTEND] Dependencies installed.
    )
)

:: ----------------------------------------------------------------------------
:: 2. OLLAMA OFFLINE LLM INFERENCE ENGINE
:: ----------------------------------------------------------------------------
echo.
echo [2/5] Detecting and initializing Ollama offline LLM service...

set "OLLAMA_PORT=11435"
set "OLLAMA_ACTIVE=0"

:: Check if Ollama is already listening on port 11435 or 11434
powershell -NoProfile -Command "$ports = @(11435, 11434); foreach ($p in $ports) { $c = New-Object System.Net.Sockets.TcpClient; try { $c.Connect('127.0.0.1', $p); Write-Output $p; $c.Close(); break } catch {} }" > "%TEMP%\ollama_port.tmp" 2>nul
set /p DETECTED_OLLAMA_PORT=<"%TEMP%\ollama_port.tmp"
del /f /q "%TEMP%\ollama_port.tmp" >nul 2>&1

if defined DETECTED_OLLAMA_PORT (
    set "OLLAMA_PORT=%DETECTED_OLLAMA_PORT%"
    set "OLLAMA_ACTIVE=1"
    echo [OLLAMA] Existing Ollama service detected active on port !OLLAMA_PORT!.
) else (
    echo [OLLAMA] Ollama not currently running. Attempting offline daemon launch...
    set "OLLAMA_EXE="
    where ollama >nul 2>&1 && set "OLLAMA_EXE=ollama"
    if not defined OLLAMA_EXE if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
    if not defined OLLAMA_EXE if exist "%PROGRAMFILES%\Ollama\ollama.exe" set "OLLAMA_EXE=%PROGRAMFILES%\Ollama\ollama.exe"
    
    if defined OLLAMA_EXE (
        echo [OLLAMA] Launching Ollama daemon on port 11435: !OLLAMA_EXE!...
        set "OLLAMA_HOST=127.0.0.1:11435"
        start "Ollama Engine (Port 11435)" /min "!OLLAMA_EXE!" serve
        set "OLLAMA_PORT=11435"
        
        :: Poll for Ollama startup
        echo [OLLAMA] Waiting for Ollama engine to accept connections on port 11435...
        for /L %%i in (1,1,15) do (
            powershell -NoProfile -Command "$c = New-Object System.Net.Sockets.TcpClient; try { $c.Connect('127.0.0.1', 11435); Write-Output 'UP'; $c.Close() } catch {}" 2>nul | findstr "UP" >nul
            if !ERRORLEVEL! equ 0 (
                set "OLLAMA_ACTIVE=1"
                echo [OLLAMA] Ollama daemon is online and responsive on port 11435.
                goto :ollama_check_done
            )
            timeout /t 1 /nobreak >nul
        )
        echo [WARNING] Ollama did not answer within 15s. Platform will utilize local deterministic fallback.
    ) else (
        echo [WARNING] ollama.exe was not found in PATH or standard installation paths.
        echo [INFO] Platform will proceed using offline deterministic compiler fallback.
    )
)

:ollama_check_done
set "OLLAMA_API_URL=http://127.0.0.1:!OLLAMA_PORT!"

:: Query active models if Ollama is up
if "!OLLAMA_ACTIVE!"=="1" (
    powershell -NoProfile -Command "try { $r = Invoke-RestMethod -Uri 'http://127.0.0.1:!OLLAMA_PORT!/api/tags' -TimeoutSec 2; $names = ($r.models | ForEach-Object { $_.name }) -join ', '; if ($names) { Write-Output ('[OLLAMA] Available models: ' + $names) } } catch {}" 2>nul
)

:: ----------------------------------------------------------------------------
:: 3. PORT HYGIENE & CLEANUP
:: ----------------------------------------------------------------------------
echo.
echo [3/5] Performing port hygiene check (8055, 5173)...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8055,5173 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $proc = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue; if ($proc) { Write-Output ('[CLEANUP] Terminating stale listener on port ' + $_.LocalPort + ' (PID ' + $proc.Id + ')'); Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } }" 2>nul
timeout /t 1 /nobreak >nul

:: ----------------------------------------------------------------------------
:: 4. LAUNCH BACKEND REST API & CRON WORKER
:: ----------------------------------------------------------------------------
echo.
echo [4/5] Launching Backend REST API Server on port 8055...

set "API_HOST=127.0.0.1"
set "API_PORT=8055"

start "Academic Ideation API [8055]" /min cmd /c "cd /d "%~dp0" && set OLLAMA_API_URL=!OLLAMA_API_URL! && python backend\api_server.py"

:: Verify API Health
echo [HEALTH] Waiting for Backend REST API readiness...
set "API_HEALTHY=0"
for /L %%i in (1,1,15) do (
    powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8055/api/health' -UseBasicParsing -TimeoutSec 1; if ($r.StatusCode -eq 200) { Write-Output 'HEALTHY' } } catch {}" 2>nul | findstr "HEALTHY" >nul
    if !ERRORLEVEL! equ 0 (
        set "API_HEALTHY=1"
        echo [BACKEND] Backend REST API is verified healthy on http://127.0.0.1:8055.
        goto :backend_ready
    )
    timeout /t 1 /nobreak >nul
)
echo [WARNING] Backend API did not signal health within 15 seconds.

:backend_ready

:: Launch Cron Ingestion Daemon
echo [WORKER] Starting background ingestion and synthesis cron worker...
start "Academic Ideation Cron Worker" /min cmd /c "cd /d "%~dp0" && set OLLAMA_API_URL=!OLLAMA_API_URL! && python backend\cron_worker.py --interval 3600"

:: ----------------------------------------------------------------------------
:: 5. LAUNCH FRONTEND VITE SERVER
:: ----------------------------------------------------------------------------
echo.
echo [5/5] Launching Frontend Interface on port 5173...
if "%NPM_AVAILABLE%"=="1" if exist "frontend" (
    start "Academic Ideation Frontend [5173]" /min cmd /c "cd /d "%~dp0\frontend" && npm run dev"
    
    echo [HEALTH] Waiting for Frontend UI readiness...
    for /L %%i in (1,1,15) do (
        powershell -NoProfile -Command "$c = New-Object System.Net.Sockets.TcpClient; try { $c.Connect('127.0.0.1', 5173); Write-Output 'UP'; $c.Close() } catch {}" 2>nul | findstr "UP" >nul
        if !ERRORLEVEL! equ 0 (
            echo [FRONTEND] Frontend Vite development server is online at http://localhost:5173.
            goto :frontend_ready
        )
        timeout /t 1 /nobreak >nul
    )
    echo [INFO] Frontend server launched (port polling completed).
) else (
    echo [WARNING] Frontend could not be started because npm or frontend folder is missing.
)

:frontend_ready

:: ----------------------------------------------------------------------------
:: RUNTIME STATUS DASHBOARD
:: ----------------------------------------------------------------------------
echo.
echo ==============================================================================
echo        ACADEMIC PROJECT IDEATION PLATFORM - RUNTIME READY (OFFLINE)
echo ==============================================================================
echo   Frontend Interface : http://localhost:5173
echo   Backend REST API   : http://localhost:8055/api/health
echo   Export Endpoint    : http://localhost:8055/api/export/:paper_id
echo   Ollama Engine      : !OLLAMA_API_URL! [Offline Inference]
echo   Database Storage   : data\academic_ideation.db (SQLite)
echo   Cron Daemon        : Active (OpenAlex Ingestion ^& Synthesis)
echo ==============================================================================
echo.

:: Auto-open browser
echo [*] Opening browser to http://localhost:5173...
start http://localhost:5173

:: ----------------------------------------------------------------------------
:: INTERACTIVE PLATFORM MANAGER
:: ----------------------------------------------------------------------------
:menu_loop
echo.
echo ------------------------------------------------------------------------------
echo   Platform Management Controls:
echo     [O] Open Frontend in default browser
echo     [S] Run health probe on all services
echo     [K] Stop all platform services and exit
echo     [Q] Quit launcher (leaves background services running)
echo ------------------------------------------------------------------------------
set /p USER_CHOICE="Enter selection [O/S/K/Q]: "

if /i "%USER_CHOICE%"=="O" (
    start http://localhost:5173
    goto :menu_loop
)

if /i "%USER_CHOICE%"=="S" (
    echo.
    echo --- Service Status Report ---
    powershell -NoProfile -Command "
        $api = try { (Invoke-WebRequest 'http://127.0.0.1:8055/api/health' -UseBasicParsing -TimeoutSec 1).StatusCode -eq 200 } catch { $false }
        $fe = try { $c = New-Object System.Net.Sockets.TcpClient; $c.Connect('127.0.0.1', 5173); $c.Close(); $true } catch { $false }
        $ol = try { $c = New-Object System.Net.Sockets.TcpClient; $c.Connect('127.0.0.1', !OLLAMA_PORT!); $c.Close(); $true } catch { $false }
        Write-Output ('Backend API  (Port 8055): ' + $(if($api){'[HEALTHY]'}else{'[STOPPED]'}))
        Write-Output ('Frontend UI  (Port 5173): ' + $(if($fe){'[ONLINE]'}else{'[STOPPED]'}))
        Write-Output ('Ollama LLM   (Port ' + !OLLAMA_PORT! + '): ' + $(if($ol){'[ONLINE]'}else{'[STOPPED]'}))
    "
    goto :menu_loop
)

if /i "%USER_CHOICE%"=="K" (
    goto :stop_services
)

if /i "%USER_CHOICE%"=="Q" (
    echo [INFO] Exiting launcher console. Services continue running in background.
    exit /b 0
)

goto :menu_loop

:stop_services
echo.
echo [*] Gracefully halting Academic Ideation Platform services...
powershell -NoProfile -Command "
    Get-NetTCPConnection -LocalPort 8055,5173 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
        if ($p) {
            Write-Output ('[STOP] Terminating process on port ' + $_.LocalPort + ' (PID ' + $p.Id + ')')
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        }
    }
" 2>nul
echo [OK] Backend and Frontend services stopped.
timeout /t 2 /nobreak >nul
exit /b 0
