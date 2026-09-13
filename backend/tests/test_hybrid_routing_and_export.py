"""
Test Suite for Hybrid Routing, Env Setup, FinOps Circuit Breaker, and DOCX Export.
Verifies:
1. .env loading and .gitignore protection.
2. Gemini HTTP 429 quota exhaustion autonomous failover to local vLLM_Engine with RadixAttention prefix caching.
3. FinOps token circuit breaker halting behavior.
4. Executive DOCX proposal compilation and Office Open XML package validity.
"""

import io
import os
import sys
import json
import zipfile
import tempfile
import urllib.error
from pathlib import Path
import pytest

# Windows pytest capture resilience: preserve original stream handles
_ORIG_STDOUT = sys.stdout
_ORIG_STDERR = sys.stderr

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from synthesis_engine import SynthesisEngine
from exporter import generate_proposal_markdown, export_idea_to_docx, build_fallback_docx
from cron_worker import run_pipeline_cycle
from database import init_db, get_connection, insert_or_update_paper

# Restore pytest stream captures if any imported script re-wrapped them
sys.stdout = _ORIG_STDOUT
sys.stderr = _ORIG_STDERR


@pytest.fixture(autouse=True)
def preserve_streams():
    """Ensures pytest stdout/stderr capture buffers are not corrupted by external imports."""
    saved_out = sys.stdout
    saved_err = sys.stderr
    yield
    sys.stdout = saved_out
    sys.stderr = saved_err


@pytest.fixture
def temp_db():
    """Creates a temporary SQLite database for isolated test runs using Windows-safe mkstemp."""
    import gc
    fd, path = tempfile.mkstemp(suffix="_test_hybrid.db")
    os.close(fd)
    init_db(path)
    yield path
    gc.collect()
    try:
        if os.path.exists(path):
            os.remove(path)
    except (PermissionError, OSError):
        pass


def test_env_loading_and_gitignore_protection():
    """Verifies that .env is scaffolded, loaded into config, and protected by .gitignore."""
    project_root = Path(__file__).resolve().parent.parent
    env_file = project_root / ".env"
    gitignore_file = project_root / ".gitignore"

    assert env_file.exists(), ".env file must exist in project root"
    assert gitignore_file.exists(), ".gitignore file must exist in project root"

    env_content = env_file.read_text(encoding="utf-8")
    assert "GEMINI_API_KEY=" in env_content
    assert "VLLM_API_URL=" in env_content
    assert "VLLM_MODEL=" in env_content

    gitignore_content = gitignore_file.read_text(encoding="utf-8")
    assert ".env" in gitignore_content
    assert "*.docx" in gitignore_content
    assert "*.py[cod]" in gitignore_content or "__pycache__" in gitignore_content


def test_gemini_429_autonomous_failover_to_vllm(monkeypatch):
    """
    Simulates a Gemini HTTP 429 Too Many Requests error.
    Verifies that SynthesisEngine autonomously catches the quota exhaustion and fails over
    to the local vLLM_Engine with RadixAttention prefix caching.
    """
    engine = SynthesisEngine(api_key="mock_gemini_key", vllm_url="http://localhost:8000/v1")

    paper = {
        "title": "Decentralized Transport Layer Congestion Control with Microsecond Pacing",
        "abstract": "We present an autonomous transport proxy using eBPF/AF_XDP to pace packets at microsecond resolution.",
        "cited_by_count": 30,
        "concepts": "computer network, congestion control, tcp"
    }

    gemini_called = []
    vllm_called = []

    def mock_gemini(p, domain, allow_iot=False):
        gemini_called.append(True)
        # Raise HTTP 429 Quota Exhaustion
        raise urllib.error.HTTPError(
            url="https://generativelanguage.googleapis.com",
            code=429,
            msg="Too Many Requests: RESOURCE_EXHAUSTED",
            hdrs={},
            fp=io.BytesIO(b'{"error": {"code": 429, "message": "Resource has been exhausted (e.g. check quota)."}}')
        )

    def mock_vllm(p, domain, allow_iot=False):
        vllm_called.append(True)
        return {
            "domain": domain,
            "title": "NetPacer: High-Velocity eBPF Congestion Proxy",
            "core_concept": "Autonomous network proxy pacing traffic at microsecond scale.",
            "target_service": "eBPF/AF_XDP zero-copy proxy daemon",
            "novelty": "Microsecond probe-interval drain rate estimation.",
            "selling_point": "Advanced kernel bypass networking portfolio piece.",
            "summary": "High-impact transport proxy synthesized by local vLLM failover engine.",
            "architecture": "{}",
            "core_mechanism": "Microsecond pacing state machine.",
            "milestones": "[]",
            "tech_stack": "[\"Rust\", \"eBPF\"]",
            "difficulty": "Hardcore",
            "viability_score": 94
        }

    monkeypatch.setattr(engine, "_synthesize_with_gemini", mock_gemini)
    monkeypatch.setattr(engine, "_synthesize_with_vllm", mock_vllm)
    engine._ollama_disabled_this_session = True

    blueprint = engine.evaluate_paper(paper, allow_iot=True)

    # Assert both engines were routed correctly
    assert len(gemini_called) == 1, "Gemini call should have been attempted first"
    assert len(vllm_called) == 1, "vLLM failover should have been called upon 429 quota exhaustion"
    assert blueprint is not None
    assert blueprint["title"] == "NetPacer: High-Velocity eBPF Congestion Proxy"
    assert blueprint["viability_score"] == 94


def test_vllm_prefix_caching_payload_structure(monkeypatch):
    """Verifies that _synthesize_with_vllm constructs standard OpenAI chat schema with RadixAttention prefix caching headers."""
    engine = SynthesisEngine(vllm_url="http://localhost:8000/v1", vllm_model="meta-llama/Llama-3-8B-Instruct")

    paper = {
        "title": "Hierarchical SkipList Indexing",
        "abstract": "Cache-conscious concurrent skiplist algorithm for NVMe.",
        "cited_by_count": 12,
        "concepts": "data structure, algorithm"
    }

    captured_request = {}

    def mock_urlopen(req, timeout=10.0):
        captured_request["url"] = req.full_url
        captured_request["headers"] = dict(req.headers)
        captured_request["payload"] = json.loads(req.data.decode("utf-8"))

        # Return mock vLLM HTTP response
        mock_resp = io.BytesIO(json.dumps({
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "domain": "DSA",
                        "title": "SkipMesh: Concurrent Index",
                        "core_concept": "Concurrent indexing library.",
                        "target_service": "Index daemon",
                        "novelty": "Cache line packing",
                        "selling_point": "Concurrency mastery",
                        "summary": "High-throughput index",
                        "architecture": {},
                        "core_mechanism": "L1 cache compaction",
                        "milestones": [],
                        "tech_stack": ["C++"],
                        "difficulty": "Advanced",
                        "viability_score": 91
                    })
                }
            }]
        }).encode("utf-8"))

        class MockHTTPResponse:
            def __init__(self, fp):
                self.fp = fp
                self.status = 200
            def read(self):
                return self.fp.read()
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        return MockHTTPResponse(mock_resp)

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    res = engine._synthesize_with_vllm(paper, "DSA", allow_iot=True)

    assert res is not None
    assert captured_request["url"] == "http://localhost:8000/v1/chat/completions"
    assert captured_request["headers"].get("X-radix-prefix-cache") == "true" or captured_request["headers"].get("X-Radix-Prefix-Cache") == "true"
    assert captured_request["payload"]["extra_body"]["radix_attention"] is True
    assert captured_request["payload"]["extra_body"]["prefix_cache"] is True


def test_docx_proposal_export_and_openxml_validity():
    """Verifies that export_idea_to_docx compiles structured markdown into a valid Office Open XML (.docx) package."""
    sample_idea = {
        "title": "AeroKV: High-Throughput NVMe Log-Structured Storage",
        "domain": "DBMS",
        "viability_score": 96,
        "difficulty": "Hardcore",
        "summary": "Production-grade storage engine with tiered compaction to eliminate NVMe write stalls.",
        "core_concept": "Persistent key-value store optimized for NVMe write amplification reduction.",
        "target_service": "Embedded storage daemon with RESP socket protocol",
        "novelty": "Lock-free compaction eliminating write stalls by 84%.",
        "selling_point": "Demonstrates low-level storage systems programming.",
        "core_mechanism": "Tiered SSTable compaction with fractional cascading Bloom filters.",
        "architecture": json.dumps({"client": "RESP TCP server", "engine": "SkipList memtable + WAL"}),
        "milestones": json.dumps([{"phase": "Phase 1", "goal": "Construct WAL"}]),
        "tech_stack": json.dumps(["Rust", "POSIX AIO"]),
        "paper_title": "Non-Blocking Compaction in Persistent Key-Value Systems",
        "paper_authors": "Dr. J. Smith, Dr. K. Patel",
        "publication_year": 2024,
        "cited_by_count": 34,
        "doi": "https://doi.org/10.1145/test.123"
    }

    fd, path_str = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    tmp_path = Path(path_str)

    try:
        exported_path = export_idea_to_docx(sample_idea, output_path=tmp_path)
        assert exported_path.exists(), "DOCX file must exist on disk"
        assert exported_path.stat().st_size > 1000, "DOCX file must be non-empty and well-structured"

        # Verify Office Open XML ZIP structure
        with zipfile.ZipFile(exported_path, "r") as zf:
            file_list = zf.namelist()
            assert "word/document.xml" in file_list, "Missing word/document.xml in DOCX"
            assert "[Content_Types].xml" in file_list, "Missing [Content_Types].xml in DOCX"

            doc_xml = zf.read("word/document.xml").decode("utf-8")
            assert "AeroKV" in doc_xml, "Project title must be in document body"
            assert "Four-Point Software Architecture Blueprint" in doc_xml or "Blueprint" in doc_xml
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass


def test_finops_circuit_breaker_halts_synthesis(temp_db, monkeypatch):
    """Verifies that if FinOps circuit breaker trips (token ceiling exceeded), batch synthesis halts gracefully."""
    conn = get_connection(temp_db)
    insert_or_update_paper(
        openalex_id="W999001",
        title="Unprocessed Paper 1",
        authors="A. Test",
        publication_year=2024,
        cited_by_count=10,
        doi="https://doi.org/10.1000/1",
        abstract="Sample abstract one",
        concepts="Full-Stack",
        status="pending",
        conn=conn
    )
    conn.close()

    # Mock FinOps breaker to return TRIPPED
    class MockTrippedBreaker:
        def evaluate(self):
            return {
                "circuit_breaker_state": "TRIPPED",
                "recommendation": "CIRCUIT BREAKER TRIPPED: Token ceiling exceeded."
            }

    import cron_worker
    monkeypatch.setattr(cron_worker, "get_finops_breaker", lambda: MockTrippedBreaker())

    report = run_pipeline_cycle(db_path=temp_db, per_page=0)
    assert report["circuit_breaker_tripped"] is True, "Pipeline report must flag circuit breaker tripped"
    assert report["synthesized_ideas"] == 0, "No ideas should be synthesized when breaker is tripped"


def test_bytesio_in_memory_export_prevents_closed_file_error():
    """Verifies that in-memory docx export into BytesIO retains an open stream for getvalue()."""
    from exporter import export_idea_to_docx_bytes, export_idea_to_docx, build_fallback_docx_bytes
    sample_idea = {
        "title": "StreamSafe: Memory-Preserving Buffer Engine",
        "domain": "DSA",
        "viability_score": 93,
        "summary": "High-throughput in-memory buffer without stream closure hazards."
    }

    # Test raw bytes helper
    raw_bytes = export_idea_to_docx_bytes(sample_idea)
    assert len(raw_bytes) > 500, "Raw DOCX bytes should be non-empty"

    # Test BytesIO target
    bio = io.BytesIO()
    res = export_idea_to_docx(sample_idea, output_path=bio)
    assert not bio.closed, "BytesIO stream must remain open after export"
    val = bio.getvalue()
    assert len(val) > 500, "getvalue() must succeed without I/O operation on closed file"
    assert val.startswith(b"PK"), "Payload must be a valid zip archive"

