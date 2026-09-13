#!/usr/bin/env python3
"""
Academic Project Ideation Platform — Unified Platform Launcher.
Orchestrates and manages the full stack:
  1. Backend REST API Server (Port 8055)
  2. Background Cron Worker Daemon (OpenAlex Ingestion & Synthesis)
  3. Frontend Vite Server (Port 5173)

Features:
  - Pre-flight dependency and environment validation (.env, node_modules, SQLite)
  - Non-blocking concurrent process management
  - Health check polling with visual readiness status
  - Clean cross-platform process tree termination on Ctrl+C (no orphan ports)
  - Flags: --no-frontend, --no-cron, --open, --status, --stop
"""

import os
import sys
import time
import signal
import socket
import argparse
import subprocess
import urllib.request
import urllib.error
import webbrowser
from pathlib import Path
from typing import List, Optional, Dict, Any

# Root directory of the project
PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DATA_DIR = PROJECT_ROOT / "data"
ENV_FILE = PROJECT_ROOT / ".env"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"

# ANSI Terminal Styling
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
GRAY = "\033[90m"


def log(tag: str, msg: str, color: str = CYAN) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"{GRAY}[{timestamp}]{RESET} {color}{BOLD}[{tag}]{RESET} {msg}")


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Checks whether a TCP port is currently listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def kill_process_tree(pid: int) -> None:
    """Safely terminates a process and all its descendants on Windows and POSIX."""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass


def kill_processes_on_port(port: int) -> bool:
    """Finds and kills any processes holding a specific port."""
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True, text=True)
            killed = False
            for line in out.splitlines():
                parts = line.strip().split()
                if len(parts) >= 5 and "LISTENING" in parts:
                    pid = int(parts[-1])
                    if pid > 0 and pid != os.getpid():
                        kill_process_tree(pid)
                        killed = True
            return killed
        except Exception:
            return False
    else:
        try:
            out = subprocess.check_output(f"lsof -t -i:{port}", shell=True, text=True)
            for pid_str in out.splitlines():
                pid = int(pid_str.strip())
                if pid > 0 and pid != os.getpid():
                    os.kill(pid, signal.SIGKILL)
            return True
        except Exception:
            return False


def preflight_checks() -> bool:
    """Validates runtime prerequisites before launching services."""
    log("PREFLIGHT", "Verifying system prerequisites and directory integrity...")

    # 1. Check Python version
    if sys.version_info < (3, 10):
        log("ERROR", f"Python 3.10+ is required. Found {sys.version}", RED)
        return False

    # 2. Check and initialize .env
    if not ENV_FILE.exists():
        if ENV_EXAMPLE.exists():
            log("CONFIG", "Scaffolding .env from .env.example...", YELLOW)
            ENV_FILE.write_text(ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            log("CONFIG", "Creating template .env file...", YELLOW)
            ENV_FILE.write_text(
                "GEMINI_API_KEY=your_key_here\n"
                "VLLM_API_URL=http://localhost:8000/v1\n"
                "VLLM_MODEL=meta-llama/Llama-3-8B-Instruct\n",
                encoding="utf-8"
            )

    # 3. Ensure data/ directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 4. Check frontend dependencies
    if not (FRONTEND_DIR / "node_modules").exists():
        log("FRONTEND", "node_modules not detected. Running 'npm install'...", YELLOW)
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
        try:
            subprocess.run([npm_cmd, "install"], cwd=str(FRONTEND_DIR), check=True)
            log("FRONTEND", "npm install completed successfully.", GREEN)
        except Exception as exc:
            log("ERROR", f"Failed to install frontend dependencies: {exc}", RED)
            return False

    log("PREFLIGHT", "All system prerequisites satisfied.", GREEN)
    return True


def poll_http_endpoint(url: str, timeout_sec: int = 15, expected_status: int = 200) -> bool:
    """Polls an HTTP endpoint until it returns the expected status code or times out."""
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AntigravityLauncher/1.0"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == expected_status:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def print_banner(services: Dict[str, Any]) -> None:
    """Renders the executive terminal status banner."""
    api_url = "http://localhost:8055"
    frontend_url = "http://localhost:5173"
    db_path = "data/academic_ideation.db"

    print("\n" + "=" * 70)
    print(f"{BOLD}{CYAN}   ACADEMIC PROJECT IDEATION PLATFORM — RUNTIME READY{RESET}")
    print("=" * 70)
    print(f"   {BOLD}Frontend Interface{RESET}  :  {GREEN}{frontend_url}{RESET}")
    print(f"   {BOLD}Backend REST API{RESET}    :  {GREEN}{api_url}/api/health{RESET}")
    print(f"   {BOLD}Export Endpoint{RESET}     :  {GREEN}{api_url}/api/export/:paper_id{RESET}")
    print(f"   {BOLD}Active Database{RESET}     :  {GRAY}{db_path} (SQLite Connected){RESET}")
    print(f"   {BOLD}Model Router{RESET}        :  {GRAY}Hybrid (Gemini 1.5 -> vLLM Failover -> Compiler){RESET}")

    if services.get("cron"):
        print(f"   {BOLD}Cron Worker Daemon{RESET}  :  {GREEN}Running (Interval: 3600s){RESET}")
    else:
        print(f"   {BOLD}Cron Worker Daemon{RESET}  :  {YELLOW}Disabled (--no-cron){RESET}")

    print("-" * 70)
    print(f"   {BOLD}Controls{RESET}            :  Press {RED}{BOLD}Ctrl+C{RESET} in this terminal to halt all services.")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Kickstart launcher for Academic Project Ideation Platform."
    )
    parser.add_argument("--no-frontend", action="store_true", help="Launch only backend and cron worker.")
    parser.add_argument("--no-cron", action="store_true", help="Do not launch background cron worker.")
    parser.add_argument("--open", action="store_true", help="Automatically open browser to frontend URL.")
    parser.add_argument("--status", action="store_true", help="Inspect runtime status of ports and services.")
    parser.add_argument("--stop", action="store_true", help="Terminate any running services on ports 8055 and 5173.")
    parser.add_argument("--cron-interval", type=int, default=3600, help="Cron worker interval in seconds (default: 3600).")
    args = parser.parse_args()

    # Handle status check
    if args.status:
        api_busy = is_port_in_use(8055)
        fe_busy = is_port_in_use(5173)
        print("\n--- Platform Service Status ---")
        print(f"Backend API  (Port 8055): {'[RUNNING]' if api_busy else '[STOPPED]'}")
        print(f"Frontend UI  (Port 5173): {'[RUNNING]' if fe_busy else '[STOPPED]'}")
        print("-------------------------------\n")
        return

    # Handle stop command
    if args.stop:
        log("STOP", "Stopping active services on ports 8055 and 5173...", YELLOW)
        k1 = kill_processes_on_port(8055)
        k2 = kill_processes_on_port(5173)
        if k1 or k2:
            log("STOP", "Services stopped successfully.", GREEN)
        else:
            log("STOP", "No active listeners were found on ports 8055 or 5173.", GRAY)
        return

    # 1. Preflight
    if not preflight_checks():
        sys.exit(1)

    # 2. Check for port conflicts
    if is_port_in_use(8055):
        log("PORT", "Port 8055 is currently in use. Releasing port...", YELLOW)
        kill_processes_on_port(8055)
        time.sleep(1)

    if not args.no_frontend and is_port_in_use(5173):
        log("PORT", "Port 5173 is currently in use. Releasing port...", YELLOW)
        kill_processes_on_port(5173)
        time.sleep(1)

    spawned_processes: List[subprocess.Popen] = []

    def cleanup(signum=None, frame=None):
        """Terminates all spawned child process trees."""
        print("\n")
        log("SHUTDOWN", "Stopping platform daemons...", YELLOW)
        for p in spawned_processes:
            if p.poll() is None:
                kill_process_tree(p.pid)
        log("SHUTDOWN", "All platform services terminated safely.", GREEN)
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        # Step A: Launch Backend API Server
        log("LAUNCH", "Starting Backend REST API server on port 8055...", CYAN)
        api_cmd = [sys.executable, "-u", str(BACKEND_DIR / "api_server.py")]
        api_proc = subprocess.Popen(
            api_cmd,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        spawned_processes.append(api_proc)

        # Step B: Launch Background Cron Worker Daemon (if enabled)
        cron_proc = None
        if not args.no_cron:
            log("LAUNCH", f"Starting Ingestion Cron Worker (interval: {args.cron_interval}s)...", CYAN)
            cron_cmd = [sys.executable, "-u", str(BACKEND_DIR / "cron_worker.py"), "--interval", str(args.cron_interval)]
            cron_proc = subprocess.Popen(
                cron_cmd,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            spawned_processes.append(cron_proc)

        # Step C: Launch Frontend Vite Server (if enabled)
        fe_proc = None
        if not args.no_frontend:
            log("LAUNCH", "Starting Frontend Vite server on port 5173...", CYAN)
            npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
            fe_proc = subprocess.Popen(
                [npm_cmd, "run", "dev"],
                cwd=str(FRONTEND_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            spawned_processes.append(fe_proc)

        # Step D: Health Polling
        log("HEALTH", "Waiting for Backend API readiness...", GRAY)
        api_ready = poll_http_endpoint("http://localhost:8055/api/health", timeout_sec=12)
        if not api_ready:
            log("ERROR", "Backend API failed to become healthy within 12 seconds.", RED)
            cleanup()

        if not args.no_frontend:
            log("HEALTH", "Waiting for Frontend UI readiness...", GRAY)
            fe_ready = poll_http_endpoint("http://localhost:5173", timeout_sec=15)
            if not fe_ready:
                log("WARNING", "Frontend server taking longer than usual to respond.", YELLOW)

        # Step E: Print Banner
        print_banner({"cron": not args.no_cron, "frontend": not args.no_frontend})

        # Step F: Auto-open browser if requested
        if args.open and not args.no_frontend:
            webbrowser.open("http://localhost:5173")

        # Step G: Supervise processes
        while True:
            time.sleep(1.0)
            for p in spawned_processes:
                if p.poll() is not None:
                    log("ALERT", f"Process (PID {p.pid}) exited unexpectedly with code {p.returncode}.", RED)
                    cleanup()

    except KeyboardInterrupt:
        cleanup()
    except Exception as exc:
        log("FATAL", f"Runtime exception encountered: {exc}", RED)
        cleanup()


if __name__ == "__main__":
    main()
