"""
Test Suite for Dynamic Synthesis and Deduplication.
Verifies that:
1. 3 distinct OpenAlex papers produce 3 completely distinct project titles.
2. No repetitive fallback prefixes (FluxSync, VectorSkip, FlashKV, HyperPacer) appear.
3. Viability scores vary realistically within the 83-96 range.
4. Database insertion is idempotent on paper_id (updates instead of duplicating).
"""

import os
import sys
import tempfile
import sqlite3
import pytest
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from synthesis_engine import SynthesisEngine
from database import init_db, get_connection, insert_project_idea, get_all_ideas


@pytest.fixture
def temp_db():
    """Creates a temporary SQLite database for isolated test runs."""
    import gc
    fd, path = tempfile.mkstemp(suffix="_test_synthesis.db")
    os.close(fd)
    init_db(path)
    yield path
    gc.collect()
    try:
        if os.path.exists(path):
            os.remove(path)
    except (PermissionError, OSError):
        pass


def test_three_distinct_papers_produce_unique_titles_and_scores(monkeypatch):
    """Verifies that 3 distinct papers generate completely distinct titles, non-repetitive codenames, and varied scores."""
    engine = SynthesisEngine(api_key=None)

    def mock_generate(prompt, system=None, timeout=30.0):
        if "Maritime" in prompt:
            return {
                "title": "AeroHelm: Autonomous Maritime Navigation",
                "viability_score": 88,
                "domain": "DSA",
                "domains": ["DSA"],
                "difficulty": "Intermediate",
                "feasibility_timeline": "80 Hours / 3 Sprints",
                "summary": "Maritime collision avoidance algorithm.",
                "architecture": {},
                "milestones": []
            }
        elif "Spectral" in prompt:
            return {
                "title": "SpectraIndex: Vector Curve Search",
                "viability_score": 92,
                "domain": "DSA",
                "domains": ["DSA"],
                "difficulty": "Advanced",
                "feasibility_timeline": "120 Hours / 4 Sprints",
                "summary": "High-dimensional vector indexing algorithm.",
                "architecture": {},
                "milestones": []
            }
        else:
            return {
                "title": "TierLSM: Non-Blocking Compaction Daemon",
                "viability_score": 95,
                "domain": "DBMS",
                "domains": ["DBMS"],
                "difficulty": "Hardcore",
                "feasibility_timeline": "160 Hours / 5 Sprints",
                "summary": "Tiered compaction scheduling for NVMe flash.",
                "architecture": {},
                "milestones": []
            }

    monkeypatch.setattr(engine.ollama_worker, "generate", mock_generate)

    paper_maritime = {
        "title": "Autonomous Maritime Surface Fleet Routing and Collision Avoidance",
        "abstract": "We present a decentralized trajectory coordination mechanism for autonomous maritime vessels operating in constrained waterways, ensuring collision-free navigation under high density.",
        "cited_by_count": 25,
        "concepts": "distributed computing, navigation, algorithms"
    }

    paper_spectral = {
        "title": "High-Dimensional Soil Spectral Reflectance Indexing for Precision Agriculture",
        "abstract": "This study develops a cache-conscious vector indexing algorithm to process hyperspectral soil reflectance curves, reducing neighbor search latency across large agricultural datasets.",
        "cited_by_count": 14,
        "concepts": "data structure, algorithm, vector index"
    }

    paper_lsm = {
        "title": "Non-Blocking Compaction Scheduling in Log-Structured Key-Value Storage",
        "abstract": "We introduce tiered SSTable compaction scheduling that eliminates NVMe write stalls in persistent log-structured key-value stores under heavy write ingestion.",
        "cited_by_count": 42,
        "concepts": "database, key-value, storage systems, lsm-tree"
    }

    blueprint_maritime = engine.evaluate_paper(paper_maritime, allow_iot=True)
    blueprint_spectral = engine.evaluate_paper(paper_spectral, allow_iot=True)
    blueprint_lsm = engine.evaluate_paper(paper_lsm, allow_iot=True)

    assert blueprint_maritime is not None
    assert blueprint_spectral is not None
    assert blueprint_lsm is not None

    titles = [blueprint_maritime["title"], blueprint_spectral["title"], blueprint_lsm["title"]]
    scores = [blueprint_maritime["viability_score"], blueprint_spectral["viability_score"], blueprint_lsm["viability_score"]]

    # 1. Verify 3 distinct titles
    assert len(set(titles)) == 3, f"Expected 3 unique titles, got: {titles}"

    # 2. Verify NO repetitive prefixes
    forbidden_prefixes = ["FluxSync:", "VectorSkip:", "FlashKV:", "HyperPacer:"]
    for title in titles:
        for prefix in forbidden_prefixes:
            assert not title.startswith(prefix), f"Title '{title}' illegally starts with fallback prefix '{prefix}'"

    # 3. Verify viability scores are within 83-96 range
    for score in scores:
        assert 83 <= score <= 96, f"Score {score} is out of the expected 83-96 range"

    # 4. Verify scores are varied (not all identical)
    assert len(set(scores)) > 1, f"Expected score diversity, but all scores were identical: {scores}"


def test_database_idempotency_and_deduplication(temp_db):
    """Verifies that insert_project_idea updates an existing record for the same paper_id without duplication."""
    conn = get_connection(temp_db)
    try:
        # Create a mock paper record
        cursor = conn.execute(
            "INSERT INTO papers (openalex_id, title, authors, publication_year, cited_by_count, doi, abstract, concepts, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("W123456", "Test Paper", "A. Author", 2024, 10, "10.1234/test", "Test abstract", "CS", "pending")
        )
        paper_id = cursor.lastrowid

        # First insert
        id_1 = insert_project_idea(
            paper_id=paper_id,
            domain="Full-Stack",
            title="InitialTitle: Subtitle One",
            summary="Initial summary",
            architecture="{}",
            core_mechanism="Mechanism A",
            milestones="[]",
            tech_stack="[]",
            difficulty="Intermediate",
            viability_score=85,
            core_concept="Concept A",
            target_service="Service A",
            novelty="Novelty A",
            selling_point="Point A",
            conn=conn
        )
        assert id_1 > 0

        # Check count
        count_1 = conn.execute("SELECT count(*) FROM project_ideas WHERE paper_id = ?", (paper_id,)).fetchone()[0]
        assert count_1 == 1

        # Second insert with updated content for the same paper_id
        id_2 = insert_project_idea(
            paper_id=paper_id,
            domain="Full-Stack",
            title="UpdatedTitle: Dynamic Subtitle Two",
            summary="Updated summary",
            architecture="{}",
            core_mechanism="Mechanism B",
            milestones="[]",
            tech_stack="[]",
            difficulty="Advanced",
            viability_score=92,
            core_concept="Concept B",
            target_service="Service B",
            novelty="Novelty B",
            selling_point="Point B",
            conn=conn
        )

        # Should return the same record ID
        assert id_2 == id_1

        # Check count remains 1 (no duplicate rows)
        count_2 = conn.execute("SELECT count(*) FROM project_ideas WHERE paper_id = ?", (paper_id,)).fetchone()[0]
        assert count_2 == 1

        # Verify updated values persisted
        row = conn.execute("SELECT title, viability_score FROM project_ideas WHERE id = ?", (id_1,)).fetchone()
        assert row[0] == "UpdatedTitle: Dynamic Subtitle Two"
        assert row[1] == 92
    finally:
        conn.close()


def test_keyword_extraction_filters_stopwords():
    """Verifies that _extract_keywords strips generic terms and returns meaningful keywords."""
    engine = SynthesisEngine()
    keywords = engine._extract_keywords(
        title="A Comprehensive Survey of Recent Advancements in Graph Partitioning",
        abstract="In this paper, we study the impact of modern machine learning algorithms on high-performance distributed systems."
    )
    assert "Comprehensive" not in keywords
    assert "Survey" not in keywords
    assert "Recent" not in keywords
    assert "Advancements" not in keywords
    assert "Impact" not in keywords
    # Meaningful domain terms should be present
    assert any(k in ["Graph", "Partitioning", "Distributed"] for k in keywords)


def test_dynamic_synthesis_produces_completely_unique_descriptions(monkeypatch):
    """
    Verifies that processing 3 completely different academic abstracts produces
    100% unique summaries, core concepts, novelties, target services, and mechanisms.
    No static templates or echoed payloads are permitted.
    """
    engine = SynthesisEngine(api_key=None)

    def mock_generate(prompt, system=None, timeout=30.0):
        if "LSM-Tree" in prompt:
            return {
                "title": "TierCompact: Non-Blocking Compaction Engine",
                "core_concept": "Lock-free parallel compaction scheduling algorithm.",
                "target_service": "NVMe Storage Engine Daemon",
                "novelty": "Dynamic partitioning of SSTables preserving serializable snapshot isolation.",
                "selling_point": "Demonstrates mastery of database storage engines and NVMe concurrency.",
                "summary": "Optimizes LSM-tree compactions for multi-tier NVMe storage engines.",
                "architecture": {"core": "Leveled Compactor"},
                "core_mechanism": "Parallel compaction scheduling.",
                "milestones": [],
                "tech_stack": ["Rust", "POSIX AIO"],
                "difficulty": "Hardcore",
                "viability_score": 95
            }
        elif "BBRv3" in prompt:
            return {
                "title": "BBRv3-Adaptive: Dynamic Congestion Pacer",
                "core_concept": "Adaptive state machine estimating queue drain rates using microsecond probe intervals.",
                "target_service": "Linux Transport Pacing Proxy",
                "novelty": "Preemptive flight size adjustment prior to buffer buildup.",
                "selling_point": "Advanced network protocol engineering portfolio piece.",
                "summary": "Adaptive congestion window pacing for high-throughput edge networks.",
                "architecture": {"proxy": "eBPF filter"},
                "core_mechanism": "Microsecond probe drain rate estimator.",
                "milestones": [],
                "tech_stack": ["C", "eBPF"],
                "difficulty": "Advanced",
                "viability_score": 91
            }
        else:
            return {
                "title": "CRDT-Sync: Zero-Copy Micro-Frontend Bus",
                "core_concept": "Zero-copy shared ArrayBuffer event bus paired with CRDT synchronization.",
                "target_service": "Worker Thread Coordination Runtime",
                "novelty": "Elimination of serialization across isolated browser threads.",
                "selling_point": "State synchronization architecture demonstration.",
                "summary": "Zero-copy event-driven reactive micro-frontends with distributed state machines.",
                "architecture": {"bus": "SharedArrayBuffer"},
                "core_mechanism": "CRDT event-driven nested state resolution.",
                "milestones": [],
                "tech_stack": ["TypeScript", "WebAssembly"],
                "difficulty": "Advanced",
                "viability_score": 89
            }

    monkeypatch.setattr(engine.ollama_worker, "generate", mock_generate)

    paper_lsm = {
        "title": "Optimizing LSM-Tree Compactions for Multi-Tier NVMe Storage Engines",
        "abstract": "Log-Structured Merge-tree (LSM-tree) based key-value stores suffer from severe write amplification and CPU overhead during leveled compaction. We propose TierCompact, a lock-free parallel compaction scheduling algorithm that dynamically partitions SSTable runs across NVMe flash tiers while preserving serializable snapshot isolation.",
        "cited_by_count": 28,
        "concepts": "Database, Log-structured merge-tree, Concurrency control, Storage systems, Key-value store"
    }

    paper_bbr = {
        "title": "BBRv3-Adaptive: Dynamic Congestion Window Pacing for High-Throughput Edge Networks",
        "abstract": "Bottleneck Bandwidth and RTT (BBR) congestion control provides high link utilization but exhibits queue bloat under bursty wireless cross-traffic. This work presents an adaptive state machine that estimates queue drain rates using microsecond probe intervals and adjusts flight size before buffer buildup occurs.",
        "cited_by_count": 34,
        "concepts": "Computer network, Congestion control, TCP, Edge computing, Packet loss, Network routing"
    }

    paper_crdt = {
        "title": "Zero-Copy Event-Driven Reactive Micro-Frontends with Distributed State Machines",
        "abstract": "Modern web platforms suffer from communication overhead and state drift when orchestrating independent micro-frontends. We demonstrate a zero-copy shared ArrayBuffer event bus paired with Conflict-Free Replicated Data Types (CRDTs) to synchronize nested application state across isolated browser worker threads.",
        "cited_by_count": 19,
        "concepts": "Full-Stack, Distributed computing, Microservices, Web application, CRDT, Reactive programming"
    }

    idea_1 = engine.evaluate_paper(paper_lsm, allow_iot=False)
    idea_2 = engine.evaluate_paper(paper_bbr, allow_iot=False)
    idea_3 = engine.evaluate_paper(paper_crdt, allow_iot=False)

    assert idea_1 is not None
    assert idea_2 is not None
    assert idea_3 is not None

    # Strict pairwise distinctness assertions as required
    assert idea_1["summary"] != idea_2["summary"], "Summaries for idea 1 and 2 must not match"
    assert idea_1["summary"] != idea_3["summary"], "Summaries for idea 1 and 3 must not match"
    assert idea_2["summary"] != idea_3["summary"], "Summaries for idea 2 and 3 must not match"

    assert idea_1["core_concept"] != idea_2["core_concept"], "Core concepts for idea 1 and 2 must not match"
    assert idea_1["core_concept"] != idea_3["core_concept"], "Core concepts for idea 1 and 3 must not match"
    assert idea_2["core_concept"] != idea_3["core_concept"], "Core concepts for idea 2 and 3 must not match"

    assert idea_1["target_service"] != idea_2["target_service"], "Target services must not match"
    assert idea_1["novelty"] != idea_2["novelty"], "Novelties must not match"
    assert idea_1["core_mechanism"] != idea_2["core_mechanism"], "Core mechanisms must not match"
    assert idea_1["selling_point"] != idea_2["selling_point"], "Selling points must not match"

    # Verify that descriptions are grounded in paper abstracts
    assert "TierCompact" in idea_1["core_concept"] or "compaction" in idea_1["core_concept"].lower()
    assert "adaptive state machine" in idea_2["core_concept"].lower() or "probe intervals" in idea_2["core_concept"].lower()
    assert "crdt" in idea_3["core_concept"].lower() or "arraybuffer" in idea_3["core_concept"].lower()

