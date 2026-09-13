@echo off
@setlocal EnableDelayedExpansion
title Academic Project Ideation Platform — Teardown
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ==============================================================================
echo   ACADEMIC PROJECT IDEATION PLATFORM - SERVICE TEARDOWN
echo ==============================================================================
echo [*] Releasing platform ports (8055, 5173)...

powershell -NoProfile -Command "
    Get-NetTCPConnection -LocalPort 8055,5173 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        $p = Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue
        if ($p) {
            Write-Output ('[STOP] Terminated ' + $p.ProcessName + ' on port ' + $_.LocalPort + ' (PID ' + $p.Id + ')')
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        }
    }
" 2>nul

echo.
echo [OK] All Academic Ideation Platform services terminated cleanly.
timeout /t 2 /nobreak >nul
exit /b 0
