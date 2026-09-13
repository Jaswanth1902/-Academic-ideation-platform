"""
Background Cron Worker and Pipeline Orchestrator.
Schedules periodic OpenAlex queries, triggers LLM synthesis, and routes failures to DLQ.
"""

import time
import argparse
import sys
from typing import Dict, Any, Optional
from config import DB_PATH
from database import (
    init_db,
    get_connection,
    insert_or_update_paper,
    get_pending_papers,
    update_paper_status,
    update_paper_synthesis_status,
    insert_project_idea,
    get_telemetry_stats
)
from openalex_client import OpenAlexClient, is_hardware_or_iot
from synthesis_engine import SynthesisEngine
from dlq_manager import DLQManager
from pathlib import Path
import importlib.util


def _safe_stderr_write(msg: str) -> None:
    """Safely writes diagnostic messages to stderr without crashing on closed streams."""
    try:
        if sys.stderr and not getattr(sys.stderr, "closed", False):
            sys.stderr.write(msg)
            sys.stderr.flush()
    except Exception:
        try:
            if hasattr(sys, "__stderr__") and sys.__stderr__ and not getattr(sys.__stderr__, "closed", False):
                sys.__stderr__.write(msg)
                sys.__stderr__.flush()
        except Exception:
            pass


_FINOPS_BREAKER_INSTANCE = None


def get_finops_breaker():
    """Loads FinOpsCircuitBreaker from 99_Meta/Scripts/finops_guard.py safely."""
    global _FINOPS_BREAKER_INSTANCE
    if _FINOPS_BREAKER_INSTANCE is not None:
        return _FINOPS_BREAKER_INSTANCE

    try:
        finops_path = Path(__file__).resolve().parent.parent.parent.parent / "99_Meta" / "Scripts" / "finops_guard.py"
        if finops_path.exists():
            import importlib.util
            if "finops_guard" in sys.modules:
                mod = sys.modules["finops_guard"]
            else:
                spec = importlib.util.spec_from_file_location("finops_guard", str(finops_path))
                mod = importlib.util.module_from_spec(spec)
                sys.modules["finops_guard"] = mod
                spec.loader.exec_module(mod)
            _FINOPS_BREAKER_INSTANCE = mod.FinOpsCircuitBreaker(quiet=True)
            return _FINOPS_BREAKER_INSTANCE
    except Exception as exc:
        _safe_stderr_write(f"[FinOps] Warning: could not load finops_guard: {exc}\n")
    return None



def run_pipeline_cycle(db_path: Optional[str] = None, per_page: int = 15, allow_iot: bool = False, skip_synthesis: bool = False) -> Dict[str, Any]:
    """
    Executes a complete single pass of the research ingestion and synthesis pipeline:
    1. Ingests fresh CS papers from OpenAlex (>= 2023, 5-50 citations).
    2. Persists candidate papers in SQLite.
    3. Synthesizes software blueprints across Full-Stack, DSA, CN, DBMS.
    4. Enforces FinOps token circuit breaker and Dead-Letter Queue (DLQ).
    """
    init_db(db_path)
    conn = get_connection(db_path)
    dlq = DLQManager(db_path)
    client = OpenAlexClient()
    engine = SynthesisEngine()
    breaker = get_finops_breaker()

    report = {
        "fetched": 0,
        "new_papers": 0,
        "synthesized_ideas": 0,
        "discarded_hardware": 0,
        "failed_dlq": 0,
        "silently_discarded": 0,
        "circuit_breaker_tripped": False,
        "allow_iot": allow_iot
    }

    try:
        # Step 1: Query OpenAlex API for unseen papers
        existing_ids = set(row[0] for row in conn.execute("SELECT openalex_id FROM papers").fetchall())
        papers = client.fetch_papers(
            per_page=per_page,
            allow_iot=allow_iot,
            exclude_ids=existing_ids,
            target_new=min(per_page, 5)
        )
        report["fetched"] = len(papers)

        for p in papers:
            if not allow_iot:
                composite = f"{p['title']} {p['abstract']} {p.get('concepts', '')}"
                is_hw, kw = is_hardware_or_iot(composite)
                if is_hw:
                    report["discarded_hardware"] += 1
                    continue

            paper_id, is_new = insert_or_update_paper(
                openalex_id=p["openalex_id"],
                title=p["title"],
                authors=p["authors"],
                publication_year=p["publication_year"],
                cited_by_count=p["cited_by_count"],
                doi=p["doi"],
                abstract=p["abstract"],
                concepts=p["concepts"],
                status="pending",
                conn=conn,
                return_is_new=True
            )
            if is_new:
                report["new_papers"] += 1

        # Step 2: Synthesize pending papers with FinOps token circuit breaker (skipped if dedicated worker active)
        if not skip_synthesis:
            batch_limit = min(per_page, 6) if per_page > 0 else 6
            pending = get_pending_papers(limit=batch_limit, conn=conn)
            for paper in pending:
                # Check FinOps Token Budget Circuit Breaker before synthesizing
                if breaker:
                    evaluation = breaker.evaluate()
                    if evaluation.get("circuit_breaker_state") == "TRIPPED":
                        _safe_stderr_write("[FinOps] Circuit breaker TRIPPED! Token consumption exceeded session budget ceiling. Halting batch synthesis.\n")
                        report["circuit_breaker_tripped"] = True
                        break

                paper_id = paper["id"]
                try:
                    blueprint = engine.evaluate_paper(paper, allow_iot=allow_iot)
                    if blueprint:
                        # Update FinOps token metrics if an LLM endpoint was reached
                        if breaker and (engine.gemini_api_key or engine.vllm_url):
                            breaker.state["cumulative_prompt_tokens"] = breaker.state.get("cumulative_prompt_tokens", 0) + 520
                            breaker.state["cumulative_completion_tokens"] = breaker.state.get("cumulative_completion_tokens", 0) + 380
                            breaker.state["total_tokens_consumed"] = breaker.state.get("total_tokens_consumed", 0) + 900
                            breaker.save_state()
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
                        update_paper_status(paper_id, "processed", conn=conn)
                        update_paper_synthesis_status(paper_id, "completed", conn=conn)
                        dlq.mark_resolved("paper_synthesis", str(paper_id), conn=conn)
                        report["synthesized_ideas"] += 1
                    else:
                        # Non-viable paper (e.g. filtered out as hardware/irrelevant)
                        update_paper_status(paper_id, "discarded", conn=conn)
                        update_paper_synthesis_status(paper_id, "completed", conn=conn)
                        report["discarded_hardware"] += 1

                except Exception as exc:
                    # Route failure to DLQ
                    dlq_res = dlq.record_failure(
                        entity_type="paper_synthesis",
                        entity_id=str(paper_id),
                        error_message=str(exc),
                        conn=conn
                    )
                    report["failed_dlq"] += 1
                    if dlq_res.get("silently_discarded"):
                        report["silently_discarded"] += 1

        return report
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Academic Ideation Background Cron Worker.")
    parser.add_argument("--once", action="store_true", help="Run a single pipeline cycle and exit.")
    parser.add_argument("--interval", type=int, default=3600, help="Cron interval in seconds (default: 3600).")
    parser.add_argument("--db", type=str, default=DB_PATH, help="Target SQLite database path.")
    args = parser.parse_args()

    print(f"[*] Starting Academic Ideation Cron Worker (Database: {args.db})")
    if args.once:
        stats = run_pipeline_cycle(db_path=args.db)
        print(f"[+] Pipeline cycle completed successfully: {stats}")
        sys.exit(0)

    print(f"[*] Entering scheduled cron loop (interval: {args.interval}s)... Press Ctrl+C to stop.")
    try:
        while True:
            stats = run_pipeline_cycle(db_path=args.db)
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Cycle finished: {stats}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[*] Cron worker safely stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
