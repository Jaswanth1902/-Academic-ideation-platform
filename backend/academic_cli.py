#!/usr/bin/env python3
"""
ACADEMIC CLI — Master Automation & Research Orchestrator.
Unified command-line interface for the Academic Ideation Platform:
- Zero-LLM Idea Research Discovery & Structuring (<3s)
- Automated OpenAlex & ArXiv Paper Harvesting
- Batch Software Blueprint Synthesis (Cloud Gemini / Local Ollama)
- Proposal Compilations & Multi-Format Exports (DOCX, CSV, Markdown)
- Continuous Background Automation Daemon
"""

import sys
import os
import json
import time
import socket
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure backend directory is in sys.path
PLATFORM_DIR = Path(__file__).resolve().parent
BACKEND_DIR = PLATFORM_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Windows console UTF-8 resilience
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from config import DB_PATH
from database import (
    init_db,
    get_connection,
    get_telemetry_stats,
    get_idea_collections,
    get_collection_papers,
    get_all_ideas
)
from openalex_client import OpenAlexClient
from idea_collector import IdeaPaperCollector
from synthesis_worker import SynthesisWorkerDaemon
from exporter import export_all_ideas_to_docx_bytes, export_all_ideas_to_csv_bytes


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """Checks if a TCP port is active."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.3)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


def cmd_status(args):
    """Displays platform telemetry and engine status."""
    init_db(DB_PATH)
    stats = get_telemetry_stats()
    collections = get_idea_collections(limit=5)

    ollama_ok = is_port_open(11435)
    coord_ok = is_port_open(11434)
    api_ok = is_port_open(8055)

    print("=" * 75)
    print("  ACADEMIC IDEATION PLATFORM: TELEMETRY & AUTOMATION DASHBOARD")
    print("=" * 75)
    print("  Engine Connectivity:")
    print(f"    • Ollama Raw Engine (11435)   : {'[ONLINE]' if ollama_ok else '[OFFLINE]'}")
    print(f"    • LLM Coordinator (11434)     : {'[ONLINE]' if coord_ok else '[OFFLINE]'}")
    print(f"    • Platform REST API (8055)    : {'[ONLINE]' if api_ok else '[OFFLINE]'}")
    print()
    print("  Database Repository Metrics:")
    print(f"    • Total Ingested Papers       : {stats.get('total_papers', 0):,}")
    print(f"    • Pending Synthesis Queue     : {stats.get('synthesis_pending', 0):,}")
    print(f"    • Completed Project Blueprints: {stats.get('total_ideas', 0):,}")
    print(f"    • Average Viability Score     : {stats.get('average_viability_score', 0)} / 100")
    print(f"    • Discarded (Hardware/IoT)    : {stats.get('discarded_papers', 0):,}")
    print(f"    • Dead-Letter Queue (DLQ)     : {stats.get('dlq_stats', {}).get('total_failures', 0):,} failures ({stats.get('dlq_stats', {}).get('retryable', 0):,} retryable)")
    print()

    if collections:
        print("  Recent Idea Research Collections (Zero-LLM):")
        for c in collections:
            print(f"    [#{c['id']}] '{c['query_title']}' ({c['paper_count']} papers, {c['created_at'][:16]})")
        print()

    print("  CLI Automation Capabilities:")
    print("    • academic_cli.py search <idea>   -> Zero-LLM literature discovery & structuring")
    print("    • academic_cli.py harvest         -> Query OpenAlex/ArXiv for fresh CS papers")
    print("    • academic_cli.py synthesize      -> Batch synthesize blueprints with local/cloud LLM")
    print("    • academic_cli.py export          -> Compile DOCX / CSV research archives")
    print("    • academic_cli.py auto            -> Continuous autonomous pipeline daemon")
    print("=" * 75)


def cmd_search(args):
    """Runs Zero-LLM Idea Paper Collector."""
    print(f"[*] Grounding idea literature: '{args.query}' (limit: {args.limit})...")
    t0 = time.perf_counter()
    collector = IdeaPaperCollector(db_path=DB_PATH)
    res = collector.collect_papers_for_idea(
        query=args.query,
        limit=args.limit,
        domain=args.domain,
        save_markdown=not args.no_md
    )
    elapsed = time.perf_counter() - t0

    print("=" * 75)
    print(f"  IDEA LITERATURE GROUNDING: '{res['query']}' ({elapsed:.2f}s, Zero-LLM)")
    print(f"  Discovered & Structured: {res['count']} papers")
    if res["markdown_path"]:
        print(f"  Executive Digest:        {res['markdown_path']}")
    print("=" * 75)

    for idx, p in enumerate(res["papers"], start=1):
        techs = ", ".join(p.get("key_techniques", [])[:4]) or "Core Systems"
        print(f"  [{idx}] ({p['relevance_score']}%) {p['title']} ({p['publication_year']}, {p['cited_by_count']} cites)")
        print(f"       Mechanisms: {techs}")
        if p.get("doi"):
            print(f"       DOI:        {p['doi']}")
        print()


def cmd_harvest(args):
    """Harvests fresh CS papers from OpenAlex & ArXiv."""
    print(f"[*] Harvesting up to {args.limit} new papers from OpenAlex / ArXiv CS...")
    t0 = time.perf_counter()
    client = OpenAlexClient()
    conn = get_connection(DB_PATH)

    try:
        existing_ids = set(row[0] for row in conn.execute("SELECT openalex_id FROM papers;").fetchall())
        papers = client.fetch_papers(
            per_page=args.limit,
            allow_iot=args.allow_iot,
            exclude_ids=existing_ids,
            target_new=args.limit,
            search_term=args.track
        )

        from database import insert_or_update_paper
        new_count = 0
        with conn:
            for p in papers:
                _, is_new = insert_or_update_paper(
                    openalex_id=p["openalex_id"],
                    title=p["title"],
                    authors=p["authors"],
                    publication_year=p["publication_year"],
                    cited_by_count=p["cited_by_count"],
                    doi=p.get("doi", ""),
                    abstract=p.get("abstract", ""),
                    concepts=p.get("concepts", ""),
                    status="pending",
                    synthesis_status="pending",
                    conn=conn,
                    return_is_new=True
                )
                if is_new:
                    new_count += 1

        elapsed = time.perf_counter() - t0
        print(f"[+] Harvested {len(papers)} candidate papers ({new_count} newly inserted into database) in {elapsed:.2f}s.")
    finally:
        conn.close()


def cmd_synthesize(args):
    """Runs batch synthesis worker."""
    print(f"[*] Initiating synthesis batch (batch size: {args.batch}, fast mode: {args.fast})...")
    worker = SynthesisWorkerDaemon(
        db_path=DB_PATH,
        batch_size=args.batch,
        allow_iot=args.allow_iot,
        fast_mode=args.fast,
        once=True
    )
    report = worker.run_cycle()
    print("=" * 75)
    print("  SYNTHESIS BATCH REPORT")
    print(f"  • Papers Scanned   : {report.get('pending_scanned', 0)}")
    print(f"  • Synthesized Ideas: {report.get('completed', 0)}")
    print(f"  • Rejected/Failed  : {report.get('failed', 0)}")
    print("=" * 75)


def cmd_export(args):
    """Exports proposal archives to DOCX, CSV, or Markdown."""
    init_db(DB_PATH)
    ideas = get_all_ideas(bookmarked_only=args.bookmarked)
    if not ideas:
        print("[!] No project blueprints found matching criteria.")
        return

    out_dir = Path(args.output) if args.output else PLATFORM_DIR / "data" / "Exports"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.format == "csv":
        data = export_all_ideas_to_csv_bytes(ideas)
        target = out_dir / f"Academic_Proposals_{'Bookmarked' if args.bookmarked else 'Master'}.csv"
        target.write_bytes(data)
        print(f"[+] Exported {len(ideas)} ideas to CSV: {target}")

    elif args.format == "docx":
        data = export_all_ideas_to_docx_bytes(ideas)
        target = out_dir / f"Academic_Proposals_{'Bookmarked' if args.bookmarked else 'Master'}.docx"
        target.write_bytes(data)
        print(f"[+] Exported {len(ideas)} ideas to DOCX: {target}")

    elif args.format == "md":
        target = out_dir / f"Academic_Proposals_{'Bookmarked' if args.bookmarked else 'Master'}.md"
        lines = [
            f"# 🎓 Academic Project Blueprints ({'Bookmarked' if args.bookmarked else 'Master Catalog'})",
            f"*Total Projects: {len(ideas)}*",
            "",
            "---"
        ]
        for idx, item in enumerate(ideas, start=1):
            lines.extend([
                f"## {idx}. {item.get('title')} ({item.get('domain')})",
                f"- **Core Concept**: {item.get('core_concept') or item.get('summary')}",
                f"- **Viability Score**: {item.get('viability_score')} / 100 | **Difficulty**: {item.get('difficulty')}",
                f"- **Core Mechanism**: {item.get('core_mechanism')}",
                f"- **Paper**: {item.get('paper_title')} ({item.get('publication_year')})",
                "",
                "---"
            ])
        target.write_text("\n".join(lines), encoding="utf-8")
        print(f"[+] Exported {len(ideas)} ideas to Markdown: {target}")


def cmd_auto(args):
    """Runs continuous autonomous pipeline daemon."""
    print(f"[*] Starting Academic Ideation Autonomous Daemon (interval: {args.interval}s, batch size: {args.batch}, fast: {args.fast})")
    print("    Press Ctrl+C to stop.\n")
    worker = SynthesisWorkerDaemon(
        db_path=DB_PATH,
        interval=args.interval,
        batch_size=args.batch,
        allow_iot=args.allow_iot,
        fast_mode=args.fast,
        once=False
    )
    worker.start()


def cmd_diagnose(args):
    """Runs system and pipeline diagnostics."""
    from diagnostics import PipelineDiagnostics
    diagnostics = PipelineDiagnostics()
    diag_result = diagnostics.run_full_diagnosis()

    if args.auto_fix:
        print("[*] Running Automated Remediation on detected sub-optimal paths...")
        applied_fixes = diagnostics.apply_auto_optimizations()
        for fix in applied_fixes:
            print(f"    [✓] {fix}")
        print("[*] Re-running diagnostics to verify improvements...\n")
        diag_result = diagnostics.run_full_diagnosis()

    if args.json:
        print(json.dumps(diag_result, indent=2))
    else:
        diagnostics.print_terminal_report(diag_result)

    rep_path = diagnostics.export_markdown_report(diag_result)
    print(f"\n[+] Detailed diagnostics report saved to: {rep_path}")


def main():
    parser = argparse.ArgumentParser(
        description="ACADEMIC CLI — Master Automation & Research Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="action", help="Platform command")

    # status
    subparsers.add_parser("status", help="Display platform telemetry, queue metrics, and service health")

    # diagnose
    p_diag = subparsers.add_parser("diagnose", help="Mine logs, audit query plans, and evaluate execution path optimality")
    p_diag.add_argument("--fix", "--optimize", action="store_true", dest="auto_fix", help="Automatically resolve detected sub-optimal paths")
    p_diag.add_argument("--json", action="store_true", help="Output raw JSON payload")

    # search (zero-llm)
    p_search = subparsers.add_parser("search", help="Search, score, and structure research papers for an idea (Zero-LLM)")
    p_search.add_argument("query", type=str, help="Idea title or research topic")
    p_search.add_argument("--limit", "-n", type=int, default=8, help="Max papers to return (default: 8)")
    p_search.add_argument("--domain", "-d", type=str, default="Computer Science", help="Domain filter")
    p_search.add_argument("--no-md", action="store_true", help="Skip Markdown digest generation")

    # harvest
    p_harvest = subparsers.add_parser("harvest", help="Harvest fresh CS papers from OpenAlex / ArXiv")
    p_harvest.add_argument("--track", "-t", type=str, help="Optional topic/track query filter")
    p_harvest.add_argument("--limit", "-n", type=int, default=15, help="Number of papers to harvest")
    p_harvest.add_argument("--allow-iot", action="store_true", help="Allow IoT/Hardware architectures")

    # synthesize
    p_synth = subparsers.add_parser("synthesize", help="Batch synthesize software blueprints from pending papers")
    p_synth.add_argument("--batch", "-b", type=int, default=5, help="Number of pending papers to synthesize")
    p_synth.add_argument("--model", "-m", type=str, help="Model override")
    p_synth.add_argument("--fast", action="store_true", help="Use fast, compact synthesis mode")
    p_synth.add_argument("--allow-iot", action="store_true", help="Allow IoT/Hardware architectures")

    # export
    p_export = subparsers.add_parser("export", help="Compile and export master research archives")
    p_export.add_argument("--format", "-f", type=str, default="md", choices=["md", "docx", "csv"], help="Export format")
    p_export.add_argument("--bookmarked", "-b", action="store_true", help="Export bookmarked ideas only")
    p_export.add_argument("--output", "-o", type=str, help="Output directory")

    # auto
    p_auto = subparsers.add_parser("auto", help="Run autonomous continuous pipeline daemon")
    p_auto.add_argument("--interval", "-i", type=float, default=10.0, help="Loop interval in seconds")
    p_auto.add_argument("--batch", "-b", type=int, default=3, help="Batch size per cycle")
    p_auto.add_argument("--fast", action="store_true", help="Use fast, compact synthesis mode")
    p_auto.add_argument("--allow-iot", action="store_true", help="Allow IoT/Hardware architectures")

    args = parser.parse_args()

    if args.action == "status":
        cmd_status(args)
    elif args.action == "diagnose":
        cmd_diagnose(args)
    elif args.action == "search":
        cmd_search(args)
    elif args.action == "harvest":
        cmd_harvest(args)
    elif args.action == "synthesize":
        cmd_synthesize(args)
    elif args.action == "export":
        cmd_export(args)
    elif args.action == "auto":
        cmd_auto(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
