"""
Asynchronous Synthesis Worker Daemon.
Operates as an independent background daemon process querying the database
for papers with synthesis_status='pending', synthesizing project blueprints
via local Ollama / Gemini, and managing the state machine transitions (pending -> completed / failed).
"""

import sys
import os
import time
import signal
import argparse
from pathlib import Path
from typing import Dict, Any, Optional, List

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import DB_PATH
from database import (
    init_db,
    get_connection,
    get_pending_papers,
    update_paper_synthesis_status,
    insert_project_idea,
    get_telemetry_stats
)
from synthesis_engine import SynthesisEngine
from dlq_manager import DLQManager
from openalex_client import is_hardware_or_iot


def _safe_print(msg: str) -> None:
    """Safely writes UTF-8 diagnostic messages to stdout without crashing on Windows cp1252."""
    try:
        if sys.stdout and not getattr(sys.stdout, "closed", False):
            sys.stdout.write(f"{msg}\n")
            sys.stdout.flush()
    except Exception:
        pass


class SynthesisWorkerDaemon:
    """
    Dedicated background worker process that drives paper synthesis asynchronously.
    Decoupled from API server to guarantee zero latency penalty on read endpoints.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        interval: float = 5.0,
        batch_size: int = 5,
        allow_iot: bool = False,
        once: bool = False,
        engine: Optional[SynthesisEngine] = None,
        fast_mode: bool = False
    ):
        self.db_path = db_path or DB_PATH
        self.interval = max(0.5, float(interval))
        self.batch_size = max(1, int(batch_size))
        self.allow_iot = allow_iot
        self.once = once
        self.fast_mode = fast_mode
        self.running = True

        init_db(self.db_path)
        self.engine = engine or SynthesisEngine()
        self.dlq = DLQManager(self.db_path)

    def run_cycle(self) -> Dict[str, Any]:
        """
        Executes a single pass over pending papers:
        1. Queries up to batch_size pending papers.
        2. Evaluates each paper through SynthesisEngine.
        3. On success: inserts idea and transitions status to 'completed'.
        4. On rejection / failure: transitions status to 'failed' and routes to DLQ.
        """
        conn = get_connection(self.db_path)
        cycle_report = {
            "pending_scanned": 0,
            "completed": 0,
            "failed": 0,
            "discarded_hardware": 0,
            "errors": 0
        }

        try:
            pending_papers = get_pending_papers(limit=self.batch_size, conn=conn)
            cycle_report["pending_scanned"] = len(pending_papers)

            if not pending_papers:
                return cycle_report

            _safe_print(f"[SynthesisWorker] Picked up {len(pending_papers)} pending papers for processing.")

            for paper in pending_papers:
                if not self.running:
                    break

                paper_id = paper["id"]
                title = paper.get("title", f"Paper #{paper_id}")
                _safe_print(f"[SynthesisWorker] Synthesizing Paper [{paper_id}]: '{title[:65]}'")

                # Check hardware/IoT filter pre-flight if IoT is not allowed
                if not self.allow_iot:
                    composite_text = f"{paper.get('title', '')} {paper.get('abstract', '')} {paper.get('concepts', '')}"
                    is_hw, kw = is_hardware_or_iot(composite_text)
                    if is_hw:
                        _safe_print(f"[SynthesisWorker] Paper [{paper_id}] rejected as Hardware/IoT ('{kw}'). Transitioning to 'failed'.")
                        update_paper_synthesis_status(paper_id, "failed", conn=conn)
                        cycle_report["discarded_hardware"] += 1
                        cycle_report["failed"] += 1
                        continue

                try:
                    blueprint = self.engine.evaluate_paper(paper, allow_iot=self.allow_iot, fast_mode=self.fast_mode)

                    if blueprint:
                        # Insert generated project blueprint into project_ideas
                        insert_project_idea(
                            paper_id=paper_id,
                            domain=blueprint.get("domains") or blueprint["domain"],
                            title=blueprint["title"],
                            summary=blueprint["summary"],
                            architecture=blueprint["architecture"],
                            core_mechanism=blueprint["core_mechanism"],
                            milestones=blueprint["milestones"],
                            tech_stack=blueprint["tech_stack"],
                            difficulty=blueprint["difficulty"],
                            viability_score=blueprint["viability_score"],
                            core_concept=blueprint.get("core_concept"),
                            target_service=blueprint.get("target_service"),
                            novelty=blueprint.get("novelty"),
                            selling_point=blueprint.get("selling_point"),
                            feasibility_timeline=blueprint.get("feasibility_timeline", "120 Hours / 4 Sprints"),
                            conn=conn
                        )

                        # State Machine Transition: pending -> completed
                        update_paper_synthesis_status(paper_id, "completed", conn=conn)
                        self.dlq.mark_resolved("paper_synthesis", str(paper_id), conn=conn)
                        cycle_report["completed"] += 1
                        _safe_print(f"[SynthesisWorker] Paper [{paper_id}] synthesis COMPLETED -> '{blueprint['title']}'")
                    else:
                        # Failed to synthesize viable software blueprint
                        update_paper_synthesis_status(paper_id, "failed", conn=conn)
                        self.dlq.record_failure(
                            entity_type="paper_synthesis",
                            entity_id=str(paper_id),
                            error_message="SynthesisEngine returned null blueprint (unviable or model unavailable)",
                            conn=conn
                        )
                        cycle_report["failed"] += 1
                        _safe_print(f"[SynthesisWorker] Paper [{paper_id}] synthesis FAILED (null blueprint). Transitioning to 'failed'.")

                except Exception as exc:
                    cycle_report["errors"] += 1
                    cycle_report["failed"] += 1
                    _safe_print(f"[SynthesisWorker] Paper [{paper_id}] encountered exception: {exc}. Transitioning to 'failed'.")
                    update_paper_synthesis_status(paper_id, "failed", conn=conn)
                    self.dlq.record_failure(
                        entity_type="paper_synthesis",
                        entity_id=str(paper_id),
                        error_message=str(exc),
                        conn=conn
                    )

            return cycle_report
        finally:
            conn.close()

    def start(self) -> None:
        """Starts the worker daemon loop with graceful shutdown signal handlers."""
        def _handle_shutdown(signum, frame):
            _safe_print("\n[SynthesisWorker] Intercepted termination signal. Shutting down gracefully...")
            self.running = False

        try:
            signal.signal(signal.SIGINT, _handle_shutdown)
            signal.signal(signal.SIGTERM, _handle_shutdown)
        except Exception:
            pass

        _safe_print("=" * 70)
        _safe_print("  ACADEMIC IDEATION PLATFORM: ASYNCHRONOUS SYNTHESIS DAEMON")
        _safe_print(f"  Target Database:  {self.db_path}")
        _safe_print(f"  Batch Size:       {self.batch_size} papers / tick")
        _safe_print(f"  Poll Interval:    {self.interval}s")
        _safe_print(f"  Mode:             {'ONE-SHOT (--once)' if self.once else 'CONTINUOUS DAEMON'}")
        _safe_print("=" * 70)

        total_processed = 0
        total_completed = 0
        total_failed = 0

        while self.running:
            report = self.run_cycle()
            total_processed += report["pending_scanned"]
            total_completed += report["completed"]
            total_failed += report["failed"]

            if self.once:
                break

            # Sleep between poll intervals if no papers were processed or after batch
            sleep_time = self.interval if report["pending_scanned"] == 0 else min(1.0, self.interval)
            step = 0.2
            elapsed = 0.0
            while self.running and elapsed < sleep_time:
                time.sleep(step)
                elapsed += step

        _safe_print("=" * 70)
        _safe_print(f"[SynthesisWorker] Daemon exited. Summary: Scanned={total_processed}, Completed={total_completed}, Failed={total_failed}")
        _safe_print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Asynchronous Academic Ideation Synthesis Worker.")
    parser.add_argument("--once", action="store_true", help="Process a single pending batch and exit.")
    parser.add_argument("--interval", type=float, default=5.0, help="Poll interval in seconds (default: 5.0).")
    parser.add_argument("--batch-size", type=int, default=5, help="Number of pending papers to process per cycle (default: 5).")
    parser.add_argument("--db", type=str, default=DB_PATH, help="Target SQLite database path.")
    parser.add_argument("--allow-iot", action="store_true", help="Allow IoT and Hardware research architectures.")
    parser.add_argument("--fast", action="store_true", help="Enable fast, compact synthesis mode.")
    args = parser.parse_args()

    daemon = SynthesisWorkerDaemon(
        db_path=args.db,
        interval=args.interval,
        batch_size=args.batch_size,
        allow_iot=args.allow_iot,
        fast_mode=args.fast,
        once=args.once
    )
    daemon.start()


if __name__ == "__main__":
    main()
