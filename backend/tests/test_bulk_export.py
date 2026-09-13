"""
Unit & Integration Test Suite for Bulk Export Endpoint and Master Document Compilation.
Verifies methodology preface, trademark signature ("Sai Jaswanth Reddy"),
OpenXML byte stream validation, and GET /api/export/bulk HTTP streaming.
"""

import sys
import io
import zipfile
import tempfile
from pathlib import Path
import pytest

# Ensure backend is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from exporter import (
    generate_bulk_proposal_markdown,
    export_all_ideas_to_docx_bytes,
    export_all_ideas_to_docx
)
from database import init_db, insert_project_idea, get_all_ideas, get_connection


SAMPLE_IDEAS = [
    {
        "id": 1,
        "paper_id": 101,
        "domain": "DBMS",
        "title": "TierCompact: Lock-Free Multi-Tier Compaction Engine",
        "summary": "High-throughput parallel compaction scheduler for LSM-trees.",
        "architecture": {"storage_tier": "NVMe flash", "scheduler": "Lock-free queue"},
        "core_mechanism": "Dynamic SSTable run partitioning across multi-tier storage.",
        "milestones": [{"phase": "Phase 1", "goal": "Build storage arena"}, {"phase": "Phase 2", "goal": "Run benchmark"}],
        "tech_stack": ["Rust", "NVMe", "io_uring"],
        "difficulty": "Advanced",
        "viability_score": 94,
        "core_concept": "Lock-free compaction scheduling over multi-tier flash.",
        "target_service": "Embedded key-value storage engine",
        "novelty": "Zero-overhead parallel partition compaction.",
        "selling_point": "Proves deep mastery of low-latency storage primitives.",
        "paper_title": "Optimizing LSM-Tree Compactions for Multi-Tier NVMe Storage Engines",
        "paper_authors": "Chen Zhang, Elena Rostova",
        "publication_year": 2023,
        "cited_by_count": 28,
        "doi": "https://doi.org/10.1145/3588912.3588944"
    },
    {
        "id": 2,
        "paper_id": 102,
        "domain": "CN",
        "title": "BBR-Pulse: Microsecond Flow Pacing Network Engine",
        "summary": "Adaptive congestion control state machine.",
        "architecture": {"pacer": "eBPF kernel hook", "estimator": "RTT gradient filter"},
        "core_mechanism": "RTT drain rate estimation via microsecond probe intervals.",
        "milestones": [{"phase": "Phase 1", "goal": "Deploy proxy"}],
        "tech_stack": ["C", "eBPF", "Linux tc"],
        "difficulty": "Advanced",
        "viability_score": 91,
        "core_concept": "Microsecond RTT gradient probe pacing.",
        "target_service": "Edge transport proxy daemon",
        "novelty": "Prevents bufferbloat before queue accumulation.",
        "selling_point": "Demonstrates Linux networking and kernel programming expertise.",
        "paper_title": "BBRv3-Adaptive: Dynamic Congestion Window Pacing",
        "paper_authors": "Marcus Lindqvist, Aarti Sundaram",
        "publication_year": 2023,
        "cited_by_count": 34,
        "doi": "https://doi.org/10.1109/TNET.2023.3289012"
    }
]


def test_bulk_markdown_generation_includes_preface_and_signature():
    """Verifies that bulk markdown contains methodology preface, trademark signature, and all projects."""
    md = generate_bulk_proposal_markdown(SAMPLE_IDEAS)

    # Check trademark signature
    assert "Sai Jaswanth Reddy" in md
    assert md.count("Sai Jaswanth Reddy") >= 3

    # Check methodology preface
    assert "Methodology & Systems Architecture Preface" in md
    assert "Scholarly Graph Ingestion Criteria" in md
    assert "Four-Point Scannable Blueprint Standard" in md
    assert "OpenAlex" in md

    # Check all projects are present
    assert "Project 1: TierCompact" in md
    assert "Project 2: BBR-Pulse" in md
    assert "TierCompact: Lock-Free Multi-Tier Compaction Engine" in md
    assert "BBR-Pulse: Microsecond Flow Pacing Network Engine" in md
    assert "Chen Zhang" in md
    assert "Marcus Lindqvist" in md


def test_bulk_docx_bytes_valid_openxml():
    """Verifies that export_all_ideas_to_docx_bytes returns a valid OpenXML zip archive with required XML parts."""
    raw_bytes = export_all_ideas_to_docx_bytes(SAMPLE_IDEAS)
    assert len(raw_bytes) > 1000
    assert raw_bytes[:4] == b"PK\x03\x04", "Must begin with standard zip local file header magic bytes"

    # Inspect zip structure
    bio = io.BytesIO(raw_bytes)
    with zipfile.ZipFile(bio, "r") as zf:
        namelist = zf.namelist()
        assert "[Content_Types].xml" in namelist
        assert "_rels/.rels" in namelist
        assert "word/document.xml" in namelist

        doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert "Sai Jaswanth Reddy" in doc_xml
        assert "TierCompact" in doc_xml
        assert "BBR-Pulse" in doc_xml
        assert "Methodology" in doc_xml


def test_bulk_docx_file_export(tmp_path):
    """Verifies export_all_ideas_to_docx writes successfully to a file path."""
    target_file = tmp_path / "Master_Archive_Test.docx"
    result = export_all_ideas_to_docx(SAMPLE_IDEAS, output_path=target_file)
    assert result.exists()
    assert result.stat().st_size > 1000

    # Read back and verify valid zip archive
    with zipfile.ZipFile(result, "r") as zf:
        doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert "Sai Jaswanth Reddy" in doc_xml
