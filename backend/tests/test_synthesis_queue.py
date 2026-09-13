"""
Test Suite for Asynchronous Queue, State Machine, and True Local Ollama Synthesis.
Verifies:
1. Database State Machine transitions ('pending' -> 'completed', 'pending' -> 'failed', rejection of invalid states).
2. revert_corrupted_papers purges deterministic fallback ideas and resets state to 'pending'.
3. OllamaLocalWorker payload structure, format="json", and generation parsing.
4. Gemini quota error (HTTP 429) immediate failover to OllamaLocalWorker.
5. Absolute eradication of deterministic fallback (returns None upon LLM failure).
6. Asynchronous SynthesisWorkerDaemon execution cycle and queue processing.
"""

import os
import sys
import json
import tempfile
import urllib.request
import urllib.error
import pytest
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import (
    init_db,
    get_connection,
    insert_or_update_paper,
    get_pending_papers,
    update_paper_synthesis_status,
    revert_corrupted_papers,
    insert_project_idea,
    get_telemetry_stats
)
from synthesis_engine import SynthesisEngine, OllamaLocalWorker
from synthesis_worker import SynthesisWorkerDaemon


@pytest.fixture
def temp_queue_db():
    """Creates an isolated temporary SQLite database for state machine verification."""
    fd, path = tempfile.mkstemp(suffix="_test_queue.db")
    os.close(fd)
    init_db(path)
    yield path
    try:
        if os.path.exists(path):
            os.remove(path)
    except (PermissionError, OSError):
        pass


def test_database_synthesis_state_machine_transitions(temp_queue_db):
    """Verifies state machine transitions: pending -> completed, pending -> failed, and invalid status rejection."""
    conn = get_connection(temp_queue_db)

    # 1. Insert new paper (default synthesis_status: pending)
    paper_id = insert_or_update_paper(
        openalex_id="W_TEST_001",
        title="Scalable Distributed Key-Value Store",
        authors="A. Turing, C. Shannon",
        publication_year=2024,
        cited_by_count=20,
        doi="https://doi.org/10.1000/182",
        abstract="A low-latency distributed hash table architecture.",
        concepts="distributed systems, databases",
        conn=conn
    )

    pending = get_pending_papers(limit=10, conn=conn)
    assert any(p["id"] == paper_id for p in pending)
    row = conn.execute("SELECT status, synthesis_status FROM papers WHERE id = ?;", (paper_id,)).fetchone()
    assert row["synthesis_status"] == "pending"
    assert row["status"] == "pending"

    # 2. Transition: pending -> completed
    update_paper_synthesis_status(paper_id, "completed", conn=conn)
    row_completed = conn.execute("SELECT status, synthesis_status FROM papers WHERE id = ?;", (paper_id,)).fetchone()
    assert row_completed["synthesis_status"] == "completed"
    assert row_completed["status"] == "processed"

    # Completed paper must no longer appear in pending queue
    pending_after_complete = get_pending_papers(limit=10, conn=conn)
    assert not any(p["id"] == paper_id for p in pending_after_complete)

    # 3. Transition: completed -> failed
    update_paper_synthesis_status(paper_id, "failed", conn=conn)
    row_failed = conn.execute("SELECT status, synthesis_status FROM papers WHERE id = ?;", (paper_id,)).fetchone()
    assert row_failed["synthesis_status"] == "failed"

    # 4. Strict state machine rejection of illegal states
    with pytest.raises(ValueError) as excinfo:
        update_paper_synthesis_status(paper_id, "in_progress", conn=conn)
    assert "Invalid synthesis_status" in str(excinfo.value)

    with pytest.raises(ValueError):
        update_paper_synthesis_status(paper_id, "unknown_status", conn=conn)

    conn.close()


def test_revert_corrupted_papers_purges_deterministic_fallbacks(temp_queue_db):
    """Verifies that revert_corrupted_papers purges boilerplate fallback ideas and resets state to pending."""
    conn = get_connection(temp_queue_db)

    # Insert 2 papers
    pid_corrupt = insert_or_update_paper(
        openalex_id="W_CORRUPT_01",
        title="Corrupted Paper with Deterministic Boilerplate",
        authors="Test Author",
        publication_year=2024,
        cited_by_count=15,
        doi="https://doi.org/10.1000/corrupt",
        abstract="Test abstract for corrupted idea.",
        concepts="algorithms",
        conn=conn
    )

    pid_valid = insert_or_update_paper(
        openalex_id="W_VALID_02",
        title="Valid Paper with Real LLM Blueprint",
        authors="Valid Author",
        publication_year=2024,
        cited_by_count=30,
        doi="https://doi.org/10.1000/valid",
        abstract="Test abstract for legitimate idea.",
        concepts="databases",
        conn=conn
    )

    # Insert deterministic boilerplate idea for pid_corrupt
    insert_project_idea(
        paper_id=pid_corrupt,
        domain="Full-Stack",
        title="TransfWire: Real-Time The Impact of AI",
        summary="Engineered directly from research. Addresses systems challenge.",
        architecture="{}",
        core_mechanism="Low-level systems primitives.",
        milestones="[]",
        tech_stack="[\"TypeScript\"]",
        difficulty="Advanced",
        viability_score=90,
        selling_point="Demonstrates advanced mastery in Full-Stack systems engineering by translating peer-reviewed research ('The Impact of AI') into a benchmark-verified production prototype.",
        conn=conn
    )
    update_paper_synthesis_status(pid_corrupt, "completed", conn=conn)

    # Insert legitimate non-boilerplate idea for pid_valid
    insert_project_idea(
        paper_id=pid_valid,
        domain="DBMS",
        title="LSM-Shard: High-Velocity Key-Value Daemon",
        summary="Production LSM-tree storage engine with partitioned write-ahead logs.",
        architecture="{\"storage\": \"WAL + SSTables\"}",
        core_mechanism="Dynamic range partitioning with concurrent compaction.",
        milestones="[]",
        tech_stack="[\"Rust\", \"RocksDB\"]",
        difficulty="Hardcore",
        viability_score=95,
        selling_point="Custom NVMe-tailored concurrency engine demonstrating low-level systems programming.",
        conn=conn
    )
    update_paper_synthesis_status(pid_valid, "completed", conn=conn)

    # Execute reversion
    reverted_count = revert_corrupted_papers(conn=conn)
    assert reverted_count >= 1

    # Verify corrupt paper was reverted to pending and its idea purged
    corrupt_row = conn.execute("SELECT synthesis_status, status FROM papers WHERE id = ?;", (pid_corrupt,)).fetchone()
    assert corrupt_row["synthesis_status"] == "pending"
    assert corrupt_row["status"] == "pending"

    corrupt_idea = conn.execute("SELECT id FROM project_ideas WHERE paper_id = ?;", (pid_corrupt,)).fetchone()
    assert corrupt_idea is None, "Deterministic fallback idea must be deleted"

    # Verify valid paper remains completed and its idea preserved
    valid_row = conn.execute("SELECT synthesis_status, status FROM papers WHERE id = ?;", (pid_valid,)).fetchone()
    assert valid_row["synthesis_status"] == "completed"

    valid_idea = conn.execute("SELECT title FROM project_ideas WHERE paper_id = ?;", (pid_valid,)).fetchone()
    assert valid_idea is not None
    assert valid_idea["title"] == "LSM-Shard: High-Velocity Key-Value Daemon"

    conn.close()


def test_ollama_local_worker_payload_and_schema(monkeypatch):
    """Verifies that OllamaLocalWorker constructs correct /api/generate payload and parses response."""
    worker = OllamaLocalWorker(base_url="http://localhost:11434", model="llama3")

    captured_url = None
    captured_payload = None

    class MockHTTPResponse:
        def __init__(self, data):
            self.data = data
            self.status = 200

        def read(self):
            return self.data.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def mock_urlopen(req, timeout=30.0):
        nonlocal captured_url, captured_payload
        captured_url = req.full_url
        if captured_url.endswith("/api/tags"):
            return MockHTTPResponse(json.dumps({
                "models": [{"name": "llama3:latest"}, {"name": "phi3:latest"}]
            }))
        if captured_url.endswith("/api/generate"):
            captured_payload = json.loads(req.data.decode("utf-8"))
            mock_llm_json = {
                "domain": "DBMS",
                "domains": ["DBMS", "Database Management"],
                "feasibility_timeline": "120 Hours / 4 Sprints",
                "title": "AetherKV: Zero-Copy WAL Storage Daemon",
                "core_concept": "High-throughput write-ahead logging storage layer.",
                "target_service": "Storage Engine Daemon",
                "novelty": "Lock-free ring-buffer WAL implementation.",
                "selling_point": "Portfolio systems demonstrator.",
                "summary": "Engineered for low-latency NVMe streaming.",
                "architecture": {"core": "RingBuffer"},
                "core_mechanism": "Sequential WAL append without fsync stalls.",
                "milestones": [{"phase": "1", "goal": "WAL buffer"}],
                "tech_stack": ["Rust", "POSIX AIO"],
                "difficulty": "Advanced",
                "viability_score": 94
            }
            return MockHTTPResponse(json.dumps({
                "model": "llama3:latest",
                "response": json.dumps(mock_llm_json),
                "done": True
            }))
        raise urllib.error.HTTPError(captured_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    res = worker.generate(prompt="Analyze this CS paper.", system="You are an architect.")
    assert captured_url.endswith("/api/generate")
    assert captured_payload["model"] == "llama3:latest"
    assert captured_payload["format"] == "json"
    assert captured_payload["stream"] is False
    assert captured_payload["prompt"] == "Analyze this CS paper."
    assert captured_payload["system"] == "You are an architect."
    assert res["title"] == "AetherKV: Zero-Copy WAL Storage Daemon"
    assert res["viability_score"] == 94


def test_gemini_quota_exhaustion_routes_to_ollama(monkeypatch):
    """Verifies that upon Gemini 429 quota exhaustion, SynthesisEngine immediately routes to OllamaLocalWorker."""
    engine = SynthesisEngine(api_key="mock_gemini_key")

    gemini_attempted = []
    ollama_attempted = []

    def mock_gemini(paper, domain, domains=None, allow_iot=False):
        gemini_attempted.append(True)
        # Simulate Gemini 429 quota error
        raise urllib.error.HTTPError(
            url="https://generativelanguage.googleapis.com",
            code=429,
            msg="Resource has been exhausted (e.g. check quota)",
            hdrs={},
            fp=None
        )

    def mock_ollama_generate(prompt, system=None, timeout=30.0):
        ollama_attempted.append(True)
        return {
            "domain": "Network Security",
            "domains": ["Network Security", "CN"],
            "feasibility_timeline": "80 Hours / 3 Sprints",
            "title": "ShieldRoute: Adaptive eBPF Filter Proxy",
            "core_concept": "High-velocity kernel packet inspection.",
            "target_service": "eBPF Proxy Runtime",
            "novelty": "XDP kernel-level packet drops.",
            "selling_point": "Low-overhead Linux network security.",
            "summary": "Real-time mitigation of amplification traffic.",
            "architecture": {},
            "core_mechanism": "Ring-buffer eBPF maps.",
            "milestones": [],
            "tech_stack": ["C", "eBPF", "Go"],
            "difficulty": "Intermediate",
            "viability_score": 89
        }

    monkeypatch.setattr(engine, "_synthesize_with_gemini", mock_gemini)
    monkeypatch.setattr(engine.ollama_worker, "generate", mock_ollama_generate)

    paper = {
        "title": "Mitigating High-Volume DDoS via Programmable Data Planes",
        "abstract": "We develop an adaptive packet classification filter implemented inside network interface cards.",
        "cited_by_count": 22,
        "concepts": "computer network, security"
    }

    blueprint = engine.evaluate_paper(paper, allow_iot=False)

    assert len(gemini_attempted) == 1, "Gemini should be attempted first"
    assert len(ollama_attempted) == 1, "Ollama must be called immediately upon Gemini quota exhaustion"
    assert blueprint is not None
    assert blueprint["title"] == "ShieldRoute: Adaptive eBPF Filter Proxy"
    assert blueprint["domain"] == "Network Security"
    assert engine._gemini_disabled_this_session is True


def test_eradicate_deterministic_fallback_returns_none(monkeypatch):
    """Verifies that when all LLMs fail, evaluate_paper returns None rather than generating synthetic boilerplate."""
    engine = SynthesisEngine(api_key="mock_key")

    # Force Gemini to fail
    def mock_gemini_fail(paper, domain, domains=None, allow_iot=False):
        raise RuntimeError("Cloud service unavailable")

    # Force Ollama to fail
    def mock_ollama_fail(prompt, system=None, timeout=30.0):
        raise ConnectionRefusedError("[WinError 10061] Target machine refused connection")

    monkeypatch.setattr(engine, "_synthesize_with_gemini", mock_gemini_fail)
    monkeypatch.setattr(engine.ollama_worker, "generate", mock_ollama_fail)
    engine._vllm_disabled_this_session = True

    paper = {
        "title": "Formal Verification of Distributed Raft Consensus",
        "abstract": "We specify and verify safety invariants of Raft leader election using TLA+.",
        "cited_by_count": 18,
        "concepts": "distributed computing, formal methods"
    }

    result = engine.evaluate_paper(paper, allow_iot=False)
    # MUST return None, NOT a deterministic fake blueprint
    assert result is None, "Deterministic fallback must be completely eradicated"
    assert not hasattr(engine, "_synthesize_deterministic"), "_synthesize_deterministic method must be deleted"


def test_asynchronous_synthesis_worker_cycle(temp_queue_db, monkeypatch):
    """Verifies that SynthesisWorkerDaemon processes pending papers, updates states to completed, and resolves DLQ."""
    conn = get_connection(temp_queue_db)

    # Insert 2 pending papers
    p1 = insert_or_update_paper(
        openalex_id="W_ASYNC_01",
        title="Async Stream Processing with Zero Memory Copy",
        authors="Engineer A",
        publication_year=2024,
        cited_by_count=25,
        doi="https://doi.org/10.1000/p1",
        abstract="High-velocity streaming dataflow pipeline.",
        concepts="Big Data Systems, stream processing",
        conn=conn
    )

    p2 = insert_or_update_paper(
        openalex_id="W_ASYNC_02_HARDWARE",
        title="Photovoltaic Microcontroller Sensor Node for Wearables",
        authors="Engineer B",
        publication_year=2024,
        cited_by_count=12,
        doi="https://doi.org/10.1000/p2",
        abstract="Embedded sensor circuit using Arduino and BLE beacon.",
        concepts="sensors, hardware, embedded systems",
        conn=conn
    )

    # Mock engine for deterministic unit test speed
    mock_engine = SynthesisEngine(api_key=None)

    def mock_ollama_success(prompt, system=None, timeout=30.0):
        return {
            "domain": "Big Data Systems",
            "domains": ["Big Data Systems"],
            "feasibility_timeline": "120 Hours / 4 Sprints",
            "title": "StreamPipe: Zero-Copy Stream Runtime",
            "core_concept": "High-throughput stream processing pipeline.",
            "target_service": "Stream Engine Daemon",
            "novelty": "Shared memory buffers avoiding serialization.",
            "selling_point": "Demonstrates high-throughput distributed systems.",
            "summary": "Eliminates serialization overhead across stream partitions.",
            "architecture": {},
            "core_mechanism": "Memory-mapped ring buffers.",
            "milestones": [],
            "tech_stack": ["Rust", "Apache Arrow"],
            "difficulty": "Advanced",
            "viability_score": 93
        }

    monkeypatch.setattr(mock_engine.ollama_worker, "generate", mock_ollama_success)

    # Initialize daemon in once mode
    daemon = SynthesisWorkerDaemon(
        db_path=temp_queue_db,
        batch_size=5,
        interval=1.0,
        allow_iot=False,
        once=True,
        engine=mock_engine
    )

    report = daemon.run_cycle()

    assert report["pending_scanned"] == 2
    assert report["completed"] == 1
    assert report["failed"] == 1
    assert report["discarded_hardware"] == 1

    # Verify p1 transitioned to completed
    row_p1 = conn.execute("SELECT synthesis_status FROM papers WHERE id = ?;", (p1,)).fetchone()
    assert row_p1["synthesis_status"] == "completed"

    idea_p1 = conn.execute("SELECT title FROM project_ideas WHERE paper_id = ?;", (p1,)).fetchone()
    assert idea_p1 is not None
    assert idea_p1["title"] == "StreamPipe: Zero-Copy Stream Runtime"

    # Verify p2 (hardware) transitioned to failed
    row_p2 = conn.execute("SELECT synthesis_status FROM papers WHERE id = ?;", (p2,)).fetchone()
    assert row_p2["synthesis_status"] == "failed"

    # Pending queue should now be empty
    remaining_pending = get_pending_papers(limit=10, conn=conn)
    assert len(remaining_pending) == 0

    conn.close()
