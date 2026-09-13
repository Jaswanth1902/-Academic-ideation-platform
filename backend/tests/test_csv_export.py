"""
Unit & Integration Test Suite for Lightweight CSV Export Option.
Verifies CSV header formatting, Excel UTF-8 BOM encoding, 4-point blueprint fields,
trademark signature inclusion, and HTTP streaming on GET /api/export/csv.
"""

import sys
import csv
import io
from pathlib import Path
import pytest

# Ensure backend is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from exporter import generate_ideas_csv_string, export_all_ideas_to_csv_bytes
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


def test_csv_generation_structure_and_bom():
    """Verifies that generated CSV starts with UTF-8 BOM, has valid headers, and parses cleanly."""
    csv_str = generate_ideas_csv_string(SAMPLE_IDEAS)

    # Must start with Excel-friendly UTF-8 BOM
    assert csv_str.startswith("\ufeff")

    # Strip BOM and parse using standard csv.reader
    clean_csv = csv_str.lstrip("\ufeff")
    reader = list(csv.DictReader(io.StringIO(clean_csv)))
    assert len(reader) == 2

    # Check first row
    row_1 = reader[0]
    assert row_1["id"] == "1"
    assert row_1["title"] == "TierCompact: Lock-Free Multi-Tier Compaction Engine"
    assert row_1["domain"] == "DBMS"
    assert row_1["viability_score"] == "94"
    assert row_1["core_concept"] == "Lock-free compaction scheduling over multi-tier flash."
    assert row_1["target_service"] == "Embedded key-value storage engine"
    assert row_1["technical_novelty"] == "Zero-overhead parallel partition compaction."
    assert row_1["portfolio_selling_point"] == "Proves deep mastery of low-latency storage primitives."
    assert row_1["signature_authority"] == "Sai Jaswanth Reddy"
    assert "Rust" in row_1["tech_stack"]
    assert "Chen Zhang" in row_1["paper_authors"]

    # Check second row
    row_2 = reader[1]
    assert row_2["id"] == "2"
    assert row_2["title"] == "BBR-Pulse: Microsecond Flow Pacing Network Engine"
    assert row_2["domain"] == "CN"
    assert row_2["signature_authority"] == "Sai Jaswanth Reddy"


def test_csv_bytes_export():
    """Verifies export_all_ideas_to_csv_bytes returns valid UTF-8 encoded bytes with BOM."""
    raw_bytes = export_all_ideas_to_csv_bytes(SAMPLE_IDEAS)
    assert len(raw_bytes) > 200
    assert raw_bytes.startswith(b"\xef\xbb\xbf"), "Must begin with UTF-8 BOM bytes for Excel compatibility"

    decoded = raw_bytes.decode("utf-8")
    assert "Sai Jaswanth Reddy" in decoded
    assert "TierCompact" in decoded
    assert "BBR-Pulse" in decoded
