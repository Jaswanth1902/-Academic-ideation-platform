import pytest
from pathlib import Path
import sys
import tempfile
import json
import sqlite3

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "backend"))

from diagnostics import LogAnalyzer, DatabaseAuditor, ServiceProber, PipelineDiagnostics


def test_log_analyzer_metrics():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as tmp:
        sample_entries = [
            {"event_type": "request_start", "details": {"original_model": "llama3.2:3b"}},
            {"event_type": "request_end", "status_code": 200, "latency_ms": 1500.0},
            {"event_type": "request_start", "details": {"original_model": "triage_model"}},
            {"event_type": "request_end", "status_code": 200, "latency_ms": 2500.0},
            {"event_type": "hammer_engaged", "timestamp": "2026-09-08T12:00:00Z"},
            {"event_type": "hammer_restored", "timestamp": "2026-09-08T12:00:10Z"},
        ]
        for e in sample_entries:
            tmp.write(json.dumps(e) + "\n")
        tmp_path = Path(tmp.name)

    try:
        analyzer = LogAnalyzer(tmp_path)
        res = analyzer.analyze()
        assert res["log_exists"] is True
        assert res["total_requests"] == 2
        assert res["completed_requests"] == 2
        assert res["status_distribution"].get(200) == 2
        assert res["latency_stats"]["count"] == 2
        assert res["latency_stats"]["avg_ms"] == 2000.0
        assert res["latency_stats"]["min_ms"] == 1500.0
        assert res["latency_stats"]["max_ms"] == 2500.0
        assert res["hammer_engagements"] == 1
        assert res["hammer_restorations"] == 1
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_database_auditor():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        from database import init_db
        init_db(tmp_path)

        conn = sqlite3.connect(str(tmp_path))
        with conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_pending_opt ON papers (synthesis_status, cited_by_count DESC);")
        conn.close()

        auditor = DatabaseAuditor(tmp_path)
        res = auditor.audit()
        assert res["db_exists"] is True
        assert res["pragmas"]["journal_mode"].lower() == "wal"
        assert res["pragmas"]["busy_timeout"] == 5000
        assert "get_pending_papers" in res["query_plans"]
        assert res["query_plans"]["get_pending_papers"]["optimal"] is True
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_pipeline_diagnostics_integration():
    diag = PipelineDiagnostics()
    res = diag.run_full_diagnosis()
    assert "optimality_score" in res
    assert res["optimality_score"] >= 80
    assert len(res["paths_summary"]) == 4
    assert res["database"]["db_exists"] is True
    assert res["database"]["pragmas"]["journal_mode"].lower() == "wal"
