# =========================================================================
# Academic Project Ideation Platform — PowerShell Launcher
# Boots Backend REST API (8055), Ingestion Cron Daemon, and Frontend (5173)
# =========================================================================

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $ScriptDir

python launch.py $args
