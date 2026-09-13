"""
Unit & Integration Test Suite for Academic Project Ideation Platform.
Verifies OpenAlex ingestion filters, hardware exclusion, multi-domain synthesis,
SQLite persistence, and Dead-Letter Queue (DLQ) 2-retry silent discard logic.
"""

import sys
import os
import tempfile
import sqlite3
import pytest
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from openalex_client import OpenAlexClient, reconstruct_abstract, is_hardware_or_iot
from synthesis_engine import SynthesisEngine
from dlq_manager import DLQManager
from database import (
    init_db,
    get_connection,
    insert_or_update_paper,
    get_pending_papers,
    update_paper_status,
    insert_project_idea,
    get_all_ideas,
    get_idea_by_id,
    get_telemetry_stats
)
from cron_worker import run_pipeline_cycle
import cron_worker


@pytest.fixture(autouse=True)
def mock_pipeline_finops(monkeypatch):
    """Ensures test_pipeline executes with finops breaker closed and fresh state."""
    class MockBreaker:
        def evaluate(self):
            return {"circuit_breaker_state": "CLOSED"}
        @property
        def state(self):
            return {}
        def save_state(self):
            pass

    monkeypatch.setattr(cron_worker, "get_finops_breaker", lambda: MockBreaker())


@pytest.fixture
def temp_db():
    """Creates a fresh temporary SQLite database for testing."""
    import gc
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    gc.collect()
    try:
        if os.path.exists(path):
            os.remove(path)
    except (PermissionError, OSError):
        pass


def test_abstract_reconstruction():
    """Verifies that OpenAlex inverted index correctly formats into ordered text."""
    inverted = {
        "High-performance": [0],
        "LSM-tree": [1],
        "storage": [2],
        "engine": [3]
    }
    result = reconstruct_abstract(inverted)
    assert result == "High-performance LSM-tree storage engine"


def test_hardware_iot_exclusion():
    """Verifies strict zero-tolerance hardware / IoT filtering."""
    # Hardware papers must be detected and rejected
    hw_texts = [
        "A low-power IoT sensor node for precision agriculture",
        "FPGA-based hardware accelerator for convolutional neural networks",
        "Arduino microcontroller implementation of RFID gate access",
        "Wearable MEMS sensor array for biomedical telemetry",
        "Autonomous drone flight controller with embedded firmware"
    ]
    for text in hw_texts:
        is_hw, kw = is_hardware_or_iot(text)
        assert is_hw is True, f"Failed to detect hardware keyword in: {text}"
        assert len(kw) > 0

    # Pure software papers must pass cleanly
    sw_texts = [
        "Optimizing LSM-Tree Compactions for NVMe Storage Engines",
        "Deterministic Merkle DAGs for Peer-to-Peer Chunk Distribution",
        "Concurrent Skip Lists with Lock-Free Memory Reclamation",
        "Distributed Reactive Micro-Frontends with Shared ArrayBuffers"
    ]
    for text in sw_texts:
        is_hw, kw = is_hardware_or_iot(text)
        assert is_hw is False, f"False positive hardware detection in: {text}"


def test_openalex_client_bounds_and_filtering():
    """Verifies OpenAlex client enforces year >= 2023 and citations between 5 and 50."""
    client = OpenAlexClient()
    papers = client.fetch_papers(per_page=10)
    assert len(papers) > 0

    for paper in papers:
        assert paper["publication_year"] >= 2023, f"Paper year {paper['publication_year']} < 2023"
        assert 5 <= paper["cited_by_count"] <= 50, f"Citations {paper['cited_by_count']} not in [5, 50]"
        is_hw, _ = is_hardware_or_iot(f"{paper['title']} {paper['abstract']}")
        assert is_hw is False, f"Hardware paper slipped through: {paper['title']}"


def test_synthesis_engine_classification_and_rejection(monkeypatch):
    """Verifies synthesis engine rejects hardware and correctly categorizes software domains."""
    engine = SynthesisEngine()

    def mock_ollama_generate(prompt, system=None, timeout=30.0):
        if "BBR" in prompt or "Congestion Control" in prompt:
            return {
                "title": "BBR-Net: Congestion Control Daemon",
                "viability_score": 89,
                "domain": "CN",
                "domains": ["CN"],
                "difficulty": "Intermediate",
                "feasibility_timeline": "80 Hours / 3 Sprints",
                "summary": "Transport layer pacing daemon.",
                "architecture": {"core": "BBR"},
                "milestones": [{"phase": "1", "goal": "Prototype"}]
            }
        elif "Skip Lists" in prompt or "Concurrent" in prompt:
            return {
                "title": "LockFreeSkipList: SIMD Concurrent Skip List",
                "viability_score": 94,
                "domain": "DSA",
                "domains": ["DSA"],
                "difficulty": "Hardcore",
                "feasibility_timeline": "160 Hours / 5 Sprints",
                "summary": "Non-blocking search tree data structure.",
                "architecture": {"core": "SkipList"},
                "milestones": [{"phase": "1", "goal": "Prototype"}]
            }
        else:
            return {
                "title": "Leveled Compaction Engine (LCE) - LSM-Tree Storage",
                "viability_score": 92,
                "domain": "DBMS",
                "domains": ["DBMS"],
                "difficulty": "Advanced",
                "feasibility_timeline": "120 Hours / 4 Sprints",
                "summary": "Storage engine optimizing write amplification.",
                "architecture": {"core": "LSM"},
                "milestones": [{"phase": "1", "goal": "Prototype"}]
            }

    monkeypatch.setattr(engine.ollama_worker, "generate", mock_ollama_generate)

    # Hardware paper rejection
    hw_paper = {
        "title": "Low-Power IoT Sensor Node with LoRa Telemetry",
        "abstract": "We develop an Arduino microcontroller sensor circuit...",
        "concepts": "Internet of Things, Sensor, Microcontroller",
        "cited_by_count": 12
    }
    assert engine.evaluate_paper(hw_paper) is None

    # DBMS software paper
    db_paper = {
        "title": "LSM-Tree Partitioned Storage Engine with Leveled Compaction",
        "abstract": "We evaluate Write-Ahead Log (WAL) and SSTable write amplification...",
        "concepts": "Database, Log-structured merge-tree, Key-value store",
        "cited_by_count": 25
    }
    db_blueprint = engine.evaluate_paper(db_paper)
    assert db_blueprint is not None
    assert db_blueprint["domain"] == "DBMS"
    assert db_blueprint["viability_score"] >= 85
    assert len(db_blueprint["milestones"]) > 0

    # CN software paper
    cn_paper = {
        "title": "BBR Congestion Control and Packet Queueing for High-Bandwidth Networks",
        "abstract": "Transport layer pacing algorithm to prevent TCP bufferbloat in network proxies...",
        "concepts": "Computer network, TCP, Congestion control",
        "cited_by_count": 30
    }
    cn_blueprint = engine.evaluate_paper(cn_paper)
    assert cn_blueprint is not None
    assert cn_blueprint["domain"] == "CN"

    # DSA software paper
    dsa_paper = {
        "title": "Lock-Free Concurrent Skip Lists with Hazard Pointer Reclamation",
        "abstract": "A non-blocking search tree data structure with SIMD acceleration...",
        "concepts": "Algorithms, Data structure, Concurrency",
        "cited_by_count": 18
    }
    dsa_blueprint = engine.evaluate_paper(dsa_paper)
    assert dsa_blueprint is not None
    assert dsa_blueprint["domain"] == "DSA"


def test_database_and_dlq_lifecycle(temp_db):
    """Verifies SQLite persistence and DLQ 2-retry silent discard policy."""
    conn = get_connection(temp_db)
    dlq = DLQManager(temp_db)

    # 1. Insert paper
    paper_id = insert_or_update_paper(
        openalex_id="W_TEST_101",
        title="Test Research Paper on Distributed Consensus",
        authors="Alice Smith, Bob Jones",
        publication_year=2023,
        cited_by_count=20,
        doi="https://doi.org/10.1000/182",
        abstract="Novel Raft consensus optimization...",
        concepts="Distributed systems, Consensus",
        status="pending",
        conn=conn
    )
    assert paper_id > 0

    # 2. First failure -> retryable (retry_count = 1)
    fail_1 = dlq.record_failure(
        entity_type="paper_synthesis",
        entity_id=str(paper_id),
        error_message="Simulated LLM Timeout Error",
        conn=conn
    )
    assert fail_1["retry_count"] == 1
    assert fail_1["status"] == "retryable"
    assert fail_1["silently_discarded"] is False

    # Check retryable entries list
    retryables = dlq.get_retryable_entries(conn=conn)
    assert len(retryables) == 1
    assert retryables[0]["entity_id"] == str(paper_id)

    # 3. Second failure -> max retries exhausted -> silent discard
    fail_2 = dlq.record_failure(
        entity_type="paper_synthesis",
        entity_id=str(paper_id),
        error_message="Simulated API Schema Parse Failure",
        conn=conn
    )
    assert fail_2["retry_count"] == 2
    assert fail_2["status"] == "discarded"
    assert fail_2["silently_discarded"] is True

    # Check that retryables is now empty and discarded contains entry
    retryables_after = dlq.get_retryable_entries(conn=conn)
    assert len(retryables_after) == 0

    discarded = dlq.get_discarded_entries(conn=conn)
    assert len(discarded) == 1
    assert discarded[0]["entity_id"] == str(paper_id)

    # Verify paper status was updated to 'discarded' in papers table
    paper_row = conn.execute("SELECT status FROM papers WHERE id = ?;", (paper_id,)).fetchone()
    assert paper_row["status"] == "discarded"

    conn.close()


def test_complete_pipeline_cycle(temp_db, monkeypatch):
    """Executes a full end-to-end cycle of ingestion, synthesis, and DLQ tracking."""
    from synthesis_engine import OllamaLocalWorker

    call_count = [0]
    domains_cycle = ["DBMS", "CN", "DSA", "Network Security", "Full-Stack", "AI/ML"]

    def mock_ollama_generate(self, prompt, system=None, timeout=30.0):
        domain = domains_cycle[call_count[0] % len(domains_cycle)]
        call_count[0] += 1
        return {
            "title": f"SynthProject: {domain} Prototype",
            "viability_score": 91,
            "domain": domain,
            "domains": [domain],
            "difficulty": "Intermediate",
            "feasibility_timeline": "120 Hours / 4 Sprints",
            "core_concept": f"Autonomous software system executing {domain} primitives.",
            "target_service": f"{domain} Service Daemon",
            "novelty": "Novel algorithmic scheduling and state handling.",
            "selling_point": "High-impact portfolio demonstration.",
            "summary": f"Full software implementation of {domain} research paper.",
            "architecture": {"core": "ServiceCore", "storage": "SQLite"},
            "milestones": [{"phase": "1", "goal": "Foundation"}, {"phase": "2", "goal": "Deployment"}]
        }

    monkeypatch.setattr(OllamaLocalWorker, "generate", mock_ollama_generate)

    stats = run_pipeline_cycle(db_path=temp_db, per_page=6)
    assert stats["fetched"] > 0
    assert stats["synthesized_ideas"] > 0

    conn = get_connection(temp_db)
    ideas = get_all_ideas(conn=conn)
    assert len(ideas) >= 4

    # Verify domain variety
    domains_present = {idea["domain"] for idea in ideas}
    assert len(domains_present) >= 3

    # Check telemetry calculation
    telemetry = get_telemetry_stats(conn=conn)
    assert telemetry["total_papers"] > 0
    assert telemetry["total_ideas"] > 0
    assert telemetry["average_viability_score"] > 80

    conn.close()


def test_iot_toggle_and_scannable_blueprint(temp_db, monkeypatch):
    """Verifies that allow_iot flag dynamically includes IoT research and produces 4-point scannable fields."""
    from synthesis_engine import OllamaLocalWorker

    def mock_ollama_generate(self, prompt, system=None, timeout=30.0):
        return {
            "title": "EdgeMesh: Distributed IoT Telemetry Daemon",
            "viability_score": 88,
            "domain": "Full-Stack",
            "domains": ["Full-Stack", "CN"],
            "difficulty": "Intermediate",
            "feasibility_timeline": "80 Hours / 3 Sprints",
            "core_concept": "Telemetry ingestion server for edge nodes.",
            "target_service": "EdgeMesh Ingestion Daemon",
            "novelty": "Zero-copy packet routing and buffer ring architecture.",
            "selling_point": "High-throughput systems programming demonstration.",
            "summary": "Full software implementation for edge telemetry ingestion.",
            "architecture": {"core": "BufferRing"},
            "milestones": [{"phase": "1", "goal": "Foundation"}]
        }

    monkeypatch.setattr(OllamaLocalWorker, "generate", mock_ollama_generate)

    # Run with allow_iot=True
    stats = run_pipeline_cycle(db_path=temp_db, per_page=10, allow_iot=True)
    assert stats["allow_iot"] is True

    conn = get_connection(temp_db)
    ideas = get_all_ideas(conn=conn)
    assert len(ideas) > 0

    # Verify all 4 scannable blueprint fields exist and are populated
    for idea in ideas:
        assert "core_concept" in idea and len(idea["core_concept"]) > 0
        assert "target_service" in idea and len(idea["target_service"]) > 0
        assert "novelty" in idea and len(idea["novelty"]) > 0
        assert "selling_point" in idea and len(idea["selling_point"]) > 0

    conn.close()
