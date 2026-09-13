"""
Unit tests for ArXiv CS API failover, HTTP 429 recovery, and pipeline thread lock safety.
"""

import sys
import threading
import time
import urllib.error
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Ensure backend is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from openalex_client import OpenAlexClient, OFFLINE_BENCHMARK_PAPERS
from api_server import _PIPELINE_LOCK


def test_arxiv_xml_parsing_structure():
    """Verifies that ArXiv XML response parses correctly into the standardized paper schema."""
    sample_arxiv_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry>
        <id>http://arxiv.org/abs/2403.09999v1</id>
        <published>2024-03-15T12:00:00Z</published>
        <title>FastLSM: Compaction Scheduling for Distributed Key-Value Engines</title>
        <summary>This paper proposes a lock-free compaction scheduler for leveled LSM trees.</summary>
        <author><name>Dr. Alice Smith</name></author>
        <author><name>Bob Jones</name></author>
        <category term="cs.DB"/>
        <arxiv:doi>10.1145/3600000.3600001</arxiv:doi>
      </entry>
    </feed>
    """
    client = OpenAlexClient()

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = sample_arxiv_xml.encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        papers = client._fetch_from_arxiv(per_page=1, target_new=1)

    assert len(papers) == 1
    p = papers[0]
    assert p["openalex_id"] == "arxiv:2403.09999v1"
    assert p["title"] == "FastLSM: Compaction Scheduling for Distributed Key-Value Engines"
    assert p["publication_year"] == 2024
    assert 5 <= p["cited_by_count"] <= 50
    assert "Database" in p["concepts"]
    assert "Alice Smith" in p["authors"]
    assert p["doi"] == "https://doi.org/10.1145/3600000.3600001"


def test_openalex_429_failover_to_arxiv():
    """Verifies that when OpenAlex returns HTTP 429, fetch_papers automatically falls over to ArXiv."""
    client = OpenAlexClient()

    # Create a 429 HTTPError
    err_429 = urllib.error.HTTPError(
        url="https://api.openalex.org/works",
        code=429,
        msg="Too Many Requests: Insufficient budget",
        hdrs={},
        fp=MagicMock()
    )

    fake_arxiv_paper = {
        "openalex_id": "arxiv:2405.12345v1",
        "title": "Decentralized State Sync for Distributed Micro-Frontends",
        "authors": "Carol White",
        "publication_year": 2024,
        "cited_by_count": 25,
        "doi": "https://doi.org/10.48550/arXiv.2405.12345",
        "abstract": "We develop a state-based CRDT for distributed browser workers.",
        "concepts": "Software engineering, Full-Stack architecture"
    }

    # First call throws 429 on OpenAlex, _fetch_from_arxiv returns fake paper
    with patch("urllib.request.urlopen", side_effect=err_429):
        with patch.object(client, "_fetch_from_arxiv", return_value=[fake_arxiv_paper]) as mock_arxiv:
            results = client.fetch_papers(per_page=2, target_new=1)
            mock_arxiv.assert_called_once()
            assert len(results) >= 1
            assert results[0]["openalex_id"] == "arxiv:2405.12345v1"


def test_offline_benchmark_expanded_capacity():
    """Verifies that OFFLINE_BENCHMARK_PAPERS contains at least 30 diverse papers across all domains."""
    assert len(OFFLINE_BENCHMARK_PAPERS) >= 30

    domains_found = set()
    for paper in OFFLINE_BENCHMARK_PAPERS:
        assert paper["publication_year"] >= 2023
        assert 5 <= paper["cited_by_count"] <= 50
        assert len(paper["abstract"]) > 50
        concepts = paper.get("concepts", "").lower()
        if "database" in concepts or "lsm" in concepts or "storage" in concepts:
            domains_found.add("DBMS")
        if "network" in concepts or "bbr" in concepts or "quic" in concepts:
            domains_found.add("CN")
        if "data structure" in concepts or "algorithm" in concepts or "tree" in concepts:
            domains_found.add("DSA")
        if "full-stack" in concepts or "web" in concepts or "react" in concepts:
            domains_found.add("Full-Stack")

    assert len(domains_found) == 4, f"Missing domains: {set(['DBMS', 'CN', 'DSA', 'Full-Stack']) - domains_found}"


def test_pipeline_thread_lock_mutual_exclusion():
    """Verifies that _PIPELINE_LOCK enforces strict mutual exclusion between threads."""
    execution_order = []

    def task(task_id: str, hold_duration: float):
        with _PIPELINE_LOCK:
            execution_order.append(f"start_{task_id}")
            time.sleep(hold_duration)
            execution_order.append(f"end_{task_id}")

    t1 = threading.Thread(target=task, args=("T1", 0.08))
    t2 = threading.Thread(target=task, args=("T2", 0.02))

    t1.start()
    time.sleep(0.01)  # Ensure T1 acquires lock first
    t2.start()

    t1.join()
    t2.join()

    # T1 must finish completely before T2 starts
    assert execution_order == ["start_T1", "end_T1", "start_T2", "end_T2"]
