import pytest
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / 'backend'))

from idea_collector import extract_key_techniques, calculate_relevance_score, IdeaPaperCollector
from synthesis_engine import SynthesisEngine
from database import init_db, get_connection, get_idea_collections, get_collection_papers

def test_extract_key_techniques():
    title = 'High Performance Vector Search via HNSW and SIMD Acceleration'
    abstract = 'We propose an LSM-Tree index integrated with Raft consensus and eBPF kernel bypass.'
    concepts = 'Distributed Systems, Data Structures'
    techniques = extract_key_techniques(title, abstract, concepts)
    assert any('HNSW' in t for t in techniques)
    assert any('SIMD' in t for t in techniques)
    assert any('LSM-Tree' in t for t in techniques)
    assert any('Raft' in t for t in techniques)
    assert any('eBPF' in t for t in techniques)

def test_calculate_relevance_score():
    query = 'Distributed Key-Value Store Raft'
    paper_relevant = {
        'title': 'A Distributed Key-Value Store with Raft Consensus',
        'concepts': 'Distributed Systems, Consensus',
        'abstract': 'Design and evaluation of a high-throughput key-value storage engine.',
        'cited_by_count': 25,
        'publication_year': 2025
    }
    paper_irrelevant = {
        'title': 'Quantum Chemistry Calculations of Rare Earth Catalysts',
        'concepts': 'Chemistry, Material Science',
        'abstract': 'We analyze molecular orbital structures using density functional theory.',
        'cited_by_count': 2,
        'publication_year': 2020
    }
    score_rel = calculate_relevance_score(query, paper_relevant)
    score_irrel = calculate_relevance_score(query, paper_irrelevant)
    assert score_rel > score_irrel
    assert score_rel >= 50.0

def test_synthesis_engine_fast_mode_schema():
    engine = SynthesisEngine()
    paper = {
        'title': 'Scalable eBPF Packet Filtering for Microservice Mesh',
        'authors': 'Jane Doe et al.',
        'abstract': 'We present an eBPF-driven zero-copy network telemetry and packet filtering pipeline.',
        'concepts': 'Network Security, Operating Systems'
    }
    fast_prompt = engine._build_fast_prompt(paper, 'CN')
    assert 'Return ONLY a valid JSON object' in fast_prompt
    assert 'core_mechanism' in fast_prompt
    
    mock_fast_parsed = {
        'title': 'eBPF-FilterMesh',
        'core_concept': 'Zero-copy microservice packet filter using eBPF.',
        'core_mechanism': 'eBPF XDP hook with lock-free ring buffer',
        'tech_stack': ['Rust', 'eBPF', 'Linux Kernel'],
        'difficulty': 'Advanced',
        'viability_score': 94
    }
    normalized = engine._normalize_llm_response(mock_fast_parsed, 'CN', paper)
    assert normalized['title'] == 'eBPF-FilterMesh'
    assert 'architecture' in normalized
    assert 'milestones' in normalized
    assert normalized['viability_score'] == 94
    assert normalized['difficulty'] == 'Advanced'
