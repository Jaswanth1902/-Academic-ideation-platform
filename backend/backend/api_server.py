"""
Lightweight REST API server for Academic Ideation Platform.
Serves synthesized ideas, telemetry stats, and pipeline triggers with strict security headers.
Zero external dependencies (uses standard library http.server).
"""

import json
import urllib.parse
import threading
import time
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional
from config import SERVER_HOST, SERVER_PORT, DB_PATH
from database import (
    init_db,
    get_connection,
    get_all_ideas,
    get_idea_by_id,
    get_idea_by_paper_or_id,
    get_telemetry_stats,
    toggle_idea_shortlist,
    toggle_idea_bookmark,
    clear_all_bookmarks
)
from dlq_manager import DLQManager
from cron_worker import run_pipeline_cycle
from exporter import export_idea_to_docx, export_all_ideas_to_docx_bytes, export_all_ideas_to_csv_bytes

# Thread lock protecting concurrent pipeline executions
_PIPELINE_LOCK = threading.RLock()


class AcademicApiHandler(BaseHTTPRequestHandler):
    """HTTP request handler providing REST endpoints and security headers."""

    def _set_security_headers(self, content_type: str = "application/json") -> None:
        """Enforces HTTP security headers required by static security auditing."""
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline' https:;")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

        # Universal local development CORS authorization
        origin = self.headers.get("Origin")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        else:
            self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, Accept, Origin")
        self.send_header("Access-Control-Max-Age", "86400")

    def do_OPTIONS(self):
        """Handles pre-flight CORS requests."""
        self.send_response(204)
        self._set_security_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        """Routes GET requests."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.rstrip("/")
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if path == "/api/health":
            self._send_json(200, {"status": "HEALTHY", "service": "AcademicIdeationAPI", "version": "1.0.0"})

        elif path in ("/api/ideas", "/api/bookmarks"):
            domain_filter = query_params.get("domain", [None])[0]
            sort_by = query_params.get("sort", ["created_at"])[0]
            bookmarked_param = query_params.get("bookmarked", ["false"])[0].lower()
            bookmarked_only = path == "/api/bookmarks" or bookmarked_param in ("true", "1", "yes")
            ideas = get_all_ideas(domain_filter=domain_filter, sort_by=sort_by, bookmarked_only=bookmarked_only)
            self._send_json(200, {
                "ideas": ideas,
                "count": len(ideas),
                "filter": domain_filter or "ALL",
                "sort": sort_by,
                "bookmarked_only": bookmarked_only
            })

        elif path.startswith("/api/ideas/"):
            try:
                idea_id = int(path.split("/")[-1])
                idea = get_idea_by_id(idea_id)
                if idea:
                    self._send_json(200, idea)
                else:
                    self._send_json(404, {"error": f"Idea with ID {idea_id} not found."})
            except ValueError:
                self._send_json(400, {"error": "Invalid idea ID format."})

        elif path == "/api/stats":
            stats = get_telemetry_stats()
            stats["runtime"] = {
                "status": "Idle",
                "port": SERVER_PORT,
                "db_status": "SQLite Connected",
                "protocol": "HTTP/1.1 REST"
            }
            self._send_json(200, stats)

        elif path == "/api/dlq":
            dlq = DLQManager(DB_PATH)
            retryable = dlq.get_retryable_entries()
            discarded = dlq.get_discarded_entries()
            self._send_json(200, {
                "retryable": retryable,
                "silently_discarded": discarded,
                "total_dlq": len(retryable) + len(discarded)
            })

        elif path in ("/api/export/csv", "/api/export/all.csv", "/api/export/bookmarks.csv") or (path == "/api/export/bulk" and query_params.get("format", [""])[0].lower() == "csv"):
            try:
                bookmarked_param = query_params.get("bookmarked", ["false"])[0].lower()
                bookmarked_only = path == "/api/export/bookmarks.csv" or bookmarked_param in ("true", "1", "yes")
                ideas = get_all_ideas(bookmarked_only=bookmarked_only)
                if not ideas:
                    self._send_json(404, {"error": "No project ideas found matching export criteria."})
                    return

                csv_bytes = export_all_ideas_to_csv_bytes(ideas)
                filename = "Academic_Ideation_Bookmarked_Archive.csv" if bookmarked_only else "Academic_Ideation_Master_Archive.csv"

                self.send_response(200)
                self._set_security_headers(content_type="text/csv; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(len(csv_bytes)))
                self.end_headers()
                self.wfile.write(csv_bytes)
            except Exception as exc:
                self._send_json(500, {"error": f"CSV export failed: {str(exc)}"})

        elif path in ("/api/export/bulk", "/api/export/bookmarks.docx"):
            try:
                bookmarked_param = query_params.get("bookmarked", ["false"])[0].lower()
                bookmarked_only = path == "/api/export/bookmarks.docx" or bookmarked_param in ("true", "1", "yes")
                ideas = get_all_ideas(bookmarked_only=bookmarked_only)
                if not ideas:
                    self._send_json(404, {"error": "No project ideas found matching export criteria."})
                    return

                docx_bytes = export_all_ideas_to_docx_bytes(ideas)
                if not docx_bytes:
                    self._send_json(500, {"error": "Failed to compile master bulk proposal archive."})
                    return

                filename = "Academic_Ideation_Bookmarked_Archive.docx" if bookmarked_only else "Academic_Ideation_Master_Archive.docx"
                self.send_response(200)
                self._set_security_headers(content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(len(docx_bytes)))
                self.end_headers()
                self.wfile.write(docx_bytes)
            except Exception as exc:
                self._send_json(500, {"error": f"Bulk export failed: {str(exc)}"})

        elif path.startswith("/api/export/"):
            try:
                target_id = int(path.split("/")[-1])
                idea = get_idea_by_paper_or_id(target_id)
                if not idea:
                    self._send_json(404, {"error": f"No project idea found for ID {target_id}."})
                    return

                docx_path = export_idea_to_docx(idea)
                if not docx_path or not docx_path.exists():
                    self._send_json(500, {"error": "Failed to compile proposal document."})
                    return

                docx_bytes = docx_path.read_bytes()
                safe_title = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in idea.get("title", "Proposal"))
                filename = f"{safe_title}_Proposal.docx"

                self.send_response(200)
                self._set_security_headers(content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(len(docx_bytes)))
                self.end_headers()
                self.wfile.write(docx_bytes)
            except ValueError:
                self._send_json(400, {"error": "Invalid ID format in export path."})
            except Exception as exc:
                self._send_json(500, {"error": f"Export failed: {str(exc)}"})

        elif path == "/api/ideas/collections":
            try:
                conn = get_connection(DB_PATH)
                try:
                    rows = conn.execute("SELECT id, query_title, domain, paper_count, created_at FROM idea_collections ORDER BY id DESC LIMIT 50;").fetchall()
                    collections = [dict(r) for r in rows]
                    self._send_json(200, {"collections": collections})
                finally:
                    conn.close()
            except Exception as exc:
                self._send_json(500, {"error": f"Failed fetching collections: {str(exc)}"})

        else:
            self._send_json(404, {"error": f"Endpoint '{path}' not found."})

    def do_POST(self):
        """Routes POST requests."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.rstrip("/")

        if path == "/api/pipeline/run":
            # Run one cycle of ingestion & synthesis
            try:
                allow_iot = False
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length > 0:
                    body_data = self.rfile.read(content_length).decode("utf-8")
                    try:
                        parsed_body = json.loads(body_data)
                        if isinstance(parsed_body, dict):
                            allow_iot = bool(parsed_body.get("allow_iot", False))
                    except Exception:
                        pass

                # Check query parameter as alternative
                query_params = urllib.parse.parse_qs(parsed_url.query)
                if "allow_iot" in query_params:
                    allow_iot = query_params["allow_iot"][0].lower() in ("true", "1", "yes")

                per_page = 6
                if isinstance(parsed_body, dict) and "per_page" in parsed_body:
                    try:
                        per_page = max(1, min(15, int(parsed_body["per_page"])))
                    except Exception:
                        per_page = 6

                with _PIPELINE_LOCK:
                    cycle_results = run_pipeline_cycle(db_path=DB_PATH, allow_iot=allow_iot, per_page=per_page)
                self._send_json(200, {
                    "message": "Pipeline cycle executed successfully.",
                    "results": cycle_results
                })
            except Exception as exc:
                self._send_json(500, {"error": f"Pipeline execution failed: {str(exc)}"})

        elif path.startswith("/api/ideas/") and (path.endswith("/shortlist") or path.endswith("/bookmark")):
            try:
                parts = path.split("/")
                idea_id = int(parts[3])
                content_length = int(self.headers.get("Content-Length", 0))
                is_target = None
                if content_length > 0:
                    body_data = self.rfile.read(content_length).decode("utf-8")
                    try:
                        parsed_body = json.loads(body_data)
                        if isinstance(parsed_body, dict):
                            if "is_bookmarked" in parsed_body:
                                is_target = bool(parsed_body["is_bookmarked"])
                            elif "is_shortlisted" in parsed_body:
                                is_target = bool(parsed_body["is_shortlisted"])
                    except Exception:
                        pass
                updated = toggle_idea_bookmark(idea_id, is_bookmarked=is_target)
                if updated is not None:
                    self._send_json(200, {
                        "id": idea_id,
                        "is_shortlisted": updated,
                        "is_bookmarked": updated
                    })
                else:
                    self._send_json(404, {"error": f"Idea with ID {idea_id} not found."})
            except Exception as exc:
                self._send_json(500, {"error": f"Failed to toggle bookmark: {str(exc)}"})

        elif path in ("/api/bookmarks/clear", "/api/shortlist/clear"):
            try:
                cleared_count = clear_all_bookmarks()
                self._send_json(200, {
                    "cleared_count": cleared_count,
                    "message": f"Successfully cleared {cleared_count} bookmarks."
                })
            except Exception as exc:
                self._send_json(500, {"error": f"Failed to clear bookmarks: {str(exc)}"})
        elif path in ("/api/ideas/collect", "/api/papers/collect"):
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length <= 0:
                    self._send_json(400, {"error": "Missing JSON request body."})
                    return
                body_data = self.rfile.read(content_length).decode("utf-8")
                payload = json.loads(body_data)
                query = payload.get("query") or payload.get("title") or ""
                if not query.strip():
                    self._send_json(400, {"error": "Field 'query' or 'title' is required."})
                    return
                limit = int(payload.get("limit", 10))
                domain = payload.get("domain")

                from idea_collector import IdeaPaperCollector
                collector = IdeaPaperCollector(db_path=DB_PATH)
                result = collector.collect_papers_for_idea(query=query, limit=limit, domain=domain)
                self._send_json(200, {
                    "message": "Papers collected and structured successfully.",
                    "data": result
                })
            except Exception as exc:
                self._send_json(500, {"error": f"Paper collection failed: {str(exc)}"})

        else:
            self._send_json(404, {"error": f"POST endpoint '{path}' not found."})

    def _send_json(self, status_code: int, data: Any) -> None:
        """Helper to serialize and transmit JSON responses."""
        payload = json.dumps(data, indent=2).encode("utf-8")
        try:
            self.send_response(status_code)
            self._set_security_headers()
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def log_message(self, format, *args):
        """Suppresses default noisy request logging to keep output clean."""
        pass


def _safe_print(msg: str) -> None:
    try:
        sys.stdout.write(str(msg) + "\n")
        sys.stdout.flush()
    except Exception:
        pass


def _background_scheduler_loop(interval_sec: int = 180):
    """
    Autonomous background scheduler daemon.
    Periodically executes pipeline cycles to ingest fresh papers and synthesize blueprints.
    Guarantees mutual exclusion with interactive requests using _PIPELINE_LOCK.
    """
    time.sleep(5)  # Grace delay for server warm-up
    _safe_print(f"[*] Background Ingestion Daemon active (Interval: {interval_sec}s)")
    while True:
        try:
            acquired = _PIPELINE_LOCK.acquire(blocking=False)
            if acquired:
                try:
                    _safe_print(f"[{time.strftime('%H:%M:%S')}] [BackgroundDaemon] Starting autonomous OpenAlex ingestion cycle...")
                    res = run_pipeline_cycle(db_path=DB_PATH, per_page=5, allow_iot=True, skip_synthesis=True)
                    new_count = res.get("new_papers", 0)
                    fetched_count = res.get("fetched", 0)
                    _safe_print(f"[{time.strftime('%H:%M:%S')}] [BackgroundDaemon] Ingestion cycle complete: +{new_count} new papers added to queue ({fetched_count} fetched).")
                finally:
                    _PIPELINE_LOCK.release()
            else:
                _safe_print(f"[{time.strftime('%H:%M:%S')}] [BackgroundDaemon] Ingestion lock active; skipping this scheduled interval.")
        except Exception as exc:
            _safe_print(f"[!] [BackgroundDaemon] Scheduler error: {exc}")
        time.sleep(interval_sec)


def run_api_server(host: str = SERVER_HOST, port: int = SERVER_PORT):
    """Starts the Academic Ideation HTTP API server with background ingestion daemon."""
    init_db()
    server = HTTPServer((host, port), AcademicApiHandler)
    _safe_print(f"[*] Academic Ideation Platform API running at http://{host}:{port}/api/health")

    # Launch autonomous background scheduler daemon
    if os.getenv("DISABLE_BACKGROUND_CRON", "0") not in ("1", "true", "True"):
        cron_interval = int(os.getenv("CRON_INTERVAL_SECONDS", "180"))
        daemon_thread = threading.Thread(
            target=_background_scheduler_loop,
            args=(cron_interval,),
            daemon=True,
            name="AcademicBackgroundDaemon"
        )
        daemon_thread.start()
        _safe_print(f"[*] Background Ingestion Daemon launched (Interval: {cron_interval}s)")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] API server safely stopped.")
        server.server_close()


if __name__ == "__main__":
    run_api_server()
