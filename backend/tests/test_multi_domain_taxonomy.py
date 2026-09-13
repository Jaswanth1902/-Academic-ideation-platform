"""
Unit tests for Multi-Domain Taxonomy, Schema Migration, Feasibility Timeline,
and Domain Selection Matrix.
"""

import os
import sys
import json
import sqlite3
import pytest
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from database import (
    init_db,
    get_connection,
    migrate_domains_and_timelines,
    insert_project_idea,
    get_all_ideas,
    get_idea_by_id,
    get_telemetry_stats
)
from synthesis_engine import SynthesisEngine


@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_academic.db"
    init_db(str(db_file))
    return str(db_file)


def test_schema_and_migration_legacy_records(tmp_path):
    """Verifies that legacy records with scalar domain string are cleanly migrated to JSON arrays."""
    db_file = str(tmp_path / "legacy_test.db")
    conn = sqlite3.connect(db_file)
    conn.execute("""
        CREATE TABLE papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            openalex_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            authors TEXT,
            publication_year INTEGER NOT NULL,
            cited_by_count INTEGER NOT NULL,
            doi TEXT,
            abstract TEXT,
            concepts TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.execute("""
        CREATE TABLE project_ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id INTEGER NOT NULL,
            domain TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            architecture TEXT NOT NULL,
            core_mechanism TEXT NOT NULL,
            milestones TEXT NOT NULL,
            tech_stack TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            viability_score INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # Insert a legacy row with scalar domain string and no feasibility_timeline column
    conn.execute("INSERT INTO papers (openalex_id, title, publication_year, cited_by_count) VALUES ('W123', 'Legacy Paper', 2023, 10);")
    conn.execute("""
        INSERT INTO project_ideas (paper_id, domain, title, summary, architecture, core_mechanism, milestones, tech_stack, difficulty, viability_score)
        VALUES (1, 'DBMS', 'Legacy KV Engine', 'Legacy summary.', '{}', 'WAL log', '[]', '[]', 'Advanced', 91);
    """)
    conn.commit()
    conn.close()

    # Now run init_db which adds columns and runs migrate_domains_and_timelines
    init_db(db_file)

    ideas = get_all_ideas(conn=get_connection(db_file))
    assert len(ideas) == 1
    legacy_item = ideas[0]
    assert legacy_item["domains"] == ["DBMS"]
    assert legacy_item["domain"] == "DBMS"
    assert legacy_item["feasibility_timeline"] == "120 Hours / 4 Sprints"


def test_insert_multi_domain_and_filter(temp_db):
    """Tests inserting project idea with multiple domain tags and filtering by secondary tag."""
    conn = get_connection(temp_db)
    conn.execute("INSERT INTO papers (openalex_id, title, publication_year, cited_by_count) VALUES ('W456', 'Crypto Graphs', 2024, 25);")

    idea_id = insert_project_idea(
        paper_id=1,
        domain=["DSA", "Cryptography", "Network Security"],
        title="Zero-Knowledge Skip Graph",
        summary="A verifiable skip graph with zero-knowledge membership proofs.",
        architecture=json.dumps({"core": "ZK graph verification pipeline"}),
        core_mechanism="BLAKE3 Merkle hashing over hierarchical skip list nodes",
        milestones=json.dumps([{"phase": "1. Foundation", "goal": "Merkle skip list"}]),
        tech_stack=json.dumps(["Rust", "arkworks", "WebAssembly"]),
        difficulty="Hardcore",
        viability_score=95,
        feasibility_timeline="160 Hours / 5 Sprints",
        conn=conn
    )
    assert idea_id > 0

    # Fetch by id
    idea = get_idea_by_id(idea_id, conn=conn)
    assert idea is not None
    assert idea["domains"] == ["DSA", "Cryptography", "Network Security"]
    assert idea["domain"] == "DSA"
    assert idea["feasibility_timeline"] == "160 Hours / 5 Sprints"
    assert idea["tech_stack"] == ["Rust", "arkworks", "WebAssembly"]

    # Filter by primary domain
    dsa_ideas = get_all_ideas(domain_filter="DSA", conn=conn)
    assert len(dsa_ideas) == 1
    assert dsa_ideas[0]["id"] == idea_id

    # Filter by secondary domain
    crypto_ideas = get_all_ideas(domain_filter="Cryptography", conn=conn)
    assert len(crypto_ideas) == 1
    assert crypto_ideas[0]["id"] == idea_id

    # Filter by non-matching domain
    cn_ideas = get_all_ideas(domain_filter="CN", conn=conn)
    assert len(cn_ideas) == 0


def test_multi_domain_classifier():
    """Tests that _classify_multi_domain returns 1 to 3 relevant domains based on text semantics."""
    engine = SynthesisEngine()

    # Case 1: Cryptography + Network Security + DSA
    text1 = "Zero-knowledge proofs and digital signatures for intrusion detection in distributed Merkle tree algorithms."
    domains1 = engine._classify_multi_domain(text1, max_domains=3)
    assert 1 <= len(domains1) <= 3
    assert any(d in domains1 for d in ["Cryptography", "Network Security", "DSA"])

    # Case 2: Computer Vision + AI/ML
    text2 = "Object detection and semantic segmentation using convolutional neural networks and vision transformers."
    domains2 = engine._classify_multi_domain(text2, max_domains=3)
    assert 1 <= len(domains2) <= 3
    assert "Computer Vision" in domains2 or "AI/ML" in domains2

    # Case 3: Empty or generic text defaults to Full-Stack
    domains3 = engine._classify_multi_domain("", max_domains=3)
    assert domains3 == ["Full-Stack"]


def test_llm_synthesis_multi_domains_and_timeline():
    """Verifies that normalized LLM response generates multi-domains and non-empty timeline."""
    engine = SynthesisEngine()
    paper = {
        "title": "Adaptive Pacing and Congestion Control for Multipath Transport Networks",
        "abstract": "We present an adaptive pacing protocol mitigating bufferbloat across concurrent transport routes.",
        "cited_by_count": 30
    }
    domains = ["CN", "Network Security"]
    raw_llm = {
        "title": "PaceNet: Multipath Congestion Daemon",
        "domains": domains,
        "difficulty": "Hardcore",
        "feasibility_timeline": "160 Hours / 5 Sprints",
        "summary": "High-velocity pacing protocol implementation.",
        "architecture": {},
        "milestones": []
    }
    blueprint = engine._normalize_llm_response(raw_llm, domain="CN", paper=paper, domains=domains)

    assert blueprint["domain"] == "CN"
    assert blueprint["domains"] == ["CN", "Network Security"]
    assert "Hours" in blueprint["feasibility_timeline"]
    assert "Sprints" in blueprint["feasibility_timeline"]
    assert blueprint["difficulty"] in ("Intermediate", "Advanced", "Hardcore")


def test_telemetry_tallies_individual_domains(temp_db):
    """Verifies that get_telemetry_stats tallies each domain tag inside JSON arrays."""
    conn = get_connection(temp_db)
    conn.execute("INSERT INTO papers (openalex_id, title, publication_year, cited_by_count) VALUES ('P1', 'Paper 1', 2024, 10);")
    conn.execute("INSERT INTO papers (openalex_id, title, publication_year, cited_by_count) VALUES ('P2', 'Paper 2', 2024, 15);")

    insert_project_idea(
        paper_id=1,
        domain=["DSA", "AI/ML"],
        title="Idea 1",
        summary="Summary 1",
        architecture="{}",
        core_mechanism="Mech 1",
        milestones="[]",
        tech_stack="[]",
        difficulty="Intermediate",
        viability_score=88,
        conn=conn
    )
    insert_project_idea(
        paper_id=2,
        domain=["AI/ML", "Computer Vision"],
        title="Idea 2",
        summary="Summary 2",
        architecture="{}",
        core_mechanism="Mech 2",
        milestones="[]",
        tech_stack="[]",
        difficulty="Advanced",
        viability_score=92,
        conn=conn
    )

    stats = get_telemetry_stats(conn=conn)
    counts = stats["domain_counts"]
    assert counts.get("AI/ML") == 2
    assert counts.get("DSA") == 1
    assert counts.get("Computer Vision") == 1
