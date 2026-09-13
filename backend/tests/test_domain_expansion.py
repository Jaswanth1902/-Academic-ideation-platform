import pytest
import sqlite3
import tempfile
from pathlib import Path
import sys

# Ensure backend directory is in path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from config import VALID_DOMAINS
from synthesis_engine import SynthesisEngine
from database import init_db, get_connection, insert_or_update_paper, insert_project_idea, get_all_ideas, get_idea_by_id, toggle_idea_shortlist
from openalex_client import OpenAlexClient


def test_14_domain_taxonomy_registration():
    """Verifies that config.VALID_DOMAINS contains all 14 software domains."""
    expected_domains = [
        "Database Management",
        "AI/ML",
        "Theory of Computation",
        "Computer Vision",
        "Operations Research",
        "Web Frameworks",
        "GenAI",
        "Big Data Systems",
        "Cryptography",
        "Network Security",
        "Full-Stack",
        "DSA",
        "CN",
        "DBMS",
    ]
    assert len(VALID_DOMAINS) == 14
    for dom in expected_domains:
        assert dom in VALID_DOMAINS, f"Missing domain {dom} in VALID_DOMAINS"


def test_synthesis_engine_classifies_expanded_domains():
    """Verifies that SynthesisEngine._classify_domain correctly identifies the new academic domains."""
    engine = SynthesisEngine()

    # GenAI
    genai_text = "RAG-Agent: Retrieval-Augmented Generation with Large Language Models and Prompt Tuning"
    assert engine._classify_domain(genai_text) == "GenAI"

    # Cryptography
    crypto_text = "Post-Quantum Cryptography using Lattice-Based Zero-Knowledge Proofs and Digital Signatures"
    assert engine._classify_domain(crypto_text) == "Cryptography"

    # Computer Vision
    cv_text = "Real-Time Object Detection and Semantic Segmentation using Vision Transformers and YOLO"
    assert engine._classify_domain(cv_text) == "Computer Vision"

    # Network Security
    sec_text = "Intrusion Detection System Defending Against DDoS Attacks and Malware via Stateful Packet Filtering"
    assert engine._classify_domain(sec_text) == "Network Security"

    # Big Data Systems
    bigdata_text = "Distributed Stream Processing at Scale with Apache Spark, Kafka, and Delta Lakehouse"
    assert engine._classify_domain(bigdata_text) == "Big Data Systems"

    # Operations Research
    or_text = "Combinatorial Optimization for Vehicle Routing Using Integer Programming and Simplex Heuristics"
    assert engine._classify_domain(or_text) == "Operations Research"

    # Theory of Computation
    toc_text = "Formal Verification of Automata and Computational Complexity in Turing Machine Decidability"
    assert engine._classify_domain(toc_text) == "Theory of Computation"

    # Web Frameworks
    wf_text = "Reactive Micro-Frontends and Server-Side Rendering with WebSocket API Gateways"
    assert engine._classify_domain(wf_text) == "Web Frameworks"


def test_sqlite_is_shortlisted_migration_and_toggle():
    """Tests SQLite schema migration for is_shortlisted and persistence of toggle_idea_shortlist."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        # Initialize schema
        init_db(db_path)
        conn = get_connection(db_path)

        # Verify column exists
        cursor = conn.execute("PRAGMA table_info(project_ideas);")
        cols = {row["name"] for row in cursor.fetchall()}
        assert "is_shortlisted" in cols, "is_shortlisted column missing from project_ideas"

        # Insert a paper and project idea
        paper_id = insert_or_update_paper(
            openalex_id="W_TEST_SHORTLIST",
            title="Verifiable Computing with ZK-SNARKs",
            authors="Alice Crypto",
            publication_year=2024,
            cited_by_count=20,
            doi="https://doi.org/10.1145/test",
            abstract="We present verifiable computation on zero knowledge snarks.",
            concepts="Cryptography, Security",
            conn=conn
        )

        idea_id = insert_project_idea(
            paper_id=paper_id,
            domain="Cryptography",
            title="AegisZK: Verifiable SNARK Runtime",
            summary="Zero-knowledge verifiable computing pipeline.",
            architecture='{"verifier": "Rust"}',
            core_mechanism="Lattice-based polynomial commitments",
            milestones='[{"phase": "Phase 1", "goal": "Setup"}]',
            tech_stack='["Rust", "Arkworks"]',
            difficulty="Hardcore",
            viability_score=95,
            core_concept="Verifiable zero knowledge execution.",
            target_service="ZK Daemon",
            novelty="Sub-millisecond verification",
            selling_point="State of the art cryptographic engineering.",
            conn=conn
        )

        # Default state must be 0 (False)
        idea = get_idea_by_id(idea_id, conn=conn)
        assert idea["is_shortlisted"] is False

        # Toggle to True
        new_state = toggle_idea_shortlist(idea_id, is_shortlisted=True, conn=conn)
        assert new_state is True
        updated_idea = get_idea_by_id(idea_id, conn=conn)
        assert updated_idea["is_shortlisted"] is True

        # Toggle back to False
        toggled_back = toggle_idea_shortlist(idea_id, conn=conn)
        assert toggled_back is False
        final_idea = get_idea_by_id(idea_id, conn=conn)
        assert final_idea["is_shortlisted"] is False
    finally:
        try:
            conn.close()
        except Exception:
            pass
        try:
            Path(db_path).unlink(missing_ok=True)
        except Exception:
            pass


def test_arxiv_fallback_query_contains_new_categories():
    """Verifies that OpenAlexClient._fetch_from_arxiv builds search queries with cs.AI, cs.CV, cs.CR, cs.DB, cs.LG, cs.NE."""
    import inspect
    client = OpenAlexClient()
    source = inspect.getsource(client._fetch_from_arxiv)
    assert "cat:cs.AI" in source
    assert "cat:cs.CV" in source
    assert "cat:cs.CR" in source
    assert "cat:cs.DB" in source
    assert "cat:cs.LG" in source
    assert "cat:cs.NE" in source
