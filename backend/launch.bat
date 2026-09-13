@echo off
REM =========================================================================
REM Academic Project Ideation Platform — Single Click Launcher
REM Boots Backend REST API (8055), Ingestion Cron Daemon, and Frontend (5173)
REM =========================================================================

cd /d "%~dp0"
python launch.py %*
pause
