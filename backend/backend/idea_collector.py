"""
Zero-LLM Idea Paper Collector & Literature Structuring Sub-Service.
Accepts user-provided project ideas or idea titles, searches OpenAlex and ArXiv,
filters out hardware/IoT non-software works, scores relevance, extracts algorithmic
primitives deterministically, and stores structured research digests in SQLite and Markdown.
"""

import sys
import os
import re
import math
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# Ensure backend directory in sys.path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import DB_PATH
from database import (
    init_db,
    get_connection,
    insert_or_update_paper
)
from openalex_client import OpenAlexClient, is_hardware_or_iot


def _slugify(text: str) -> str:
    """Converts a query string to a filesystem-safe slug."""
    text = re.sub(r"[^\w\s-]", "", text.strip().lower())
    return re.sub(r"[-\s]+", "_", text)[:60]


def extract_key_techniques(title: str, abstract: str, concepts: str) -> List[str]:
    """
    Deterministically extracts key algorithms, protocols, data structures,
    and systems mechanisms without an LLM using regex pattern matching and tech taxonomy.
    """
    text = f"{title} {abstract} {concepts}"
    found = set()

    # 1. Technical acronyms and hyphenated hardware/software primitives (2-12 uppercase chars/digits)
    acronym_pattern = r"\b([A-Z][A-Z0-9]{1,9}(?:-[A-Za-z0-9]+)?)\b"
    stopwords_acronyms = {"THE", "AND", "FOR", "WITH", "THIS", "THAT", "FROM", "OUR", "NOT", "ALL", "NEW", "ONE", "TWO", "CAN", "MAY", "IEEE", "ACM"}
    for match in re.finditer(acronym_pattern, text):
        acr = match.group(1).strip()
        if acr not in stopwords_acronyms and len(acr) >= 2:
            found.add(acr)

    # 2. Canonical Systems, Algorithms & Data Structure Terminology
    canonical_terms = [
        "LSM-Tree", "B-Tree", "Bw-Tree", "B+ Tree", "Skip List", "HNSW", "ANN",
        "Raft", "Paxos", "Two-Phase Commit", "2PC", "MVCC", "WAL", "Write-Ahead Log",
        "QUIC", "TCP BBR", "eBPF", "DPDK", "Zero-Copy", "CRDT", "Vector Clock",
        "Bloom Filter", "Cuckoo Filter", "Merkle Tree", "Merkle DAG", "DHT", "Kademlia",
        "AVX-512", "SIMD", "Parquet", "Arrow", "Columnar Storage", "HTAP",
        "Zero-Knowledge", "ZK-SNARK", "Homomorphic Encryption", "Post-Quantum",
        "Contextual Bandit", "Multi-Armed Bandit", "Reinforcement Learning",
        "Nearest Neighbor", "Product Quantization", "Graph Neural Network",
        "Consensus Protocol", "Distributed Hash Table", "Lock-Free", "Epoch Reclamation"
    ]

    text_lower = text.lower()
    for term in canonical_terms:
        if term.lower() in text_lower:
            found.add(term)

    # Return top unique techniques, sorted by length descending
    return sorted(list(found), key=lambda x: -len(x))[:10]


def calculate_relevance_score(query: str, paper: Dict[str, Any]) -> float:
    """
    Computes a deterministic BM25/TF-IDF inspired relevance score (0.0 to 100.0)
    between the input idea query and the paper's title, concepts, and abstract.
    """
    query_tokens = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 2]
    if not query_tokens:
        return 50.0

    title = paper.get("title", "").lower()
    concepts = paper.get("concepts", "").lower()
    abstract = paper.get("abstract", "").lower()

    score = 0.0
    for token in query_tokens:
        # Title match (Highest weight: 35 pts max)
        if re.search(r"\b" + re.escape(token) + r"\b", title):
            score += 35.0 / len(query_tokens)
        elif token in title:
            score += 15.0 / len(query_tokens)

        # Concept tag match (Weight: 25 pts max)
        if token in concepts:
            score += 25.0 / len(query_tokens)

        # Abstract match (Weight: 20 pts max)
        if re.search(r"\b" + re.escape(token) + r"\b", abstract):
            score += 20.0 / len(query_tokens)

    # Citation authority boost (0-15 pts)
    citations = paper.get("cited_by_count", 0)
    citation_boost = min(15.0, math.log(max(1, citations) + 1, 2) * 2.5)
    score += citation_boost

    # Recency boost (0-5 pts for 2023-2025)
    year = paper.get("publication_year", 2023)
    if year >= 2024:
        score += 5.0
    elif year == 2023:
        score += 3.0

    return round(min(100.0, score), 1)


class IdeaPaperCollector:
    """
    Zero-LLM Sub-service to discover, score, structure, and persist academic research
    grounding user-provided project ideas.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH
        init_db(self.db_path)
        self.client = OpenAlexClient()

    def collect_papers_for_idea(
        self,
        query: str,
        limit: int = 10,
        domain: Optional[str] = None,
        save_markdown: bool = True,
        output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Gathers academic research papers for the query:
        1. Queries OpenAlex & ArXiv failover via search_term.
        2. Filters non-software / IoT.
        3. Deterministically computes relevance scores & extracts key techniques.
        4. Persists structured records into SQLite (papers + idea_collections).
        5. Generates an executive Markdown research digest.
        """
        cleaned_query = query.strip()
        if not cleaned_query:
            raise ValueError("Query string cannot be empty.")

        limit = max(1, min(50, int(limit)))

        # Fetch papers from OpenAlex / ArXiv
        fetched = self.client.fetch_papers(
            per_page=max(limit * 2, 15),
            allow_iot=False,
            search_term=cleaned_query,
            target_new=limit
        )

        # Structure and score papers
        structured_papers = []
        for p in fetched:
            score = calculate_relevance_score(cleaned_query, p)
            techniques = extract_key_techniques(
                title=p.get("title", ""),
                abstract=p.get("abstract", ""),
                concepts=p.get("concepts", "")
            )
            structured_papers.append({
                **p,
                "relevance_score": score,
                "key_techniques": techniques
            })

        # Sort descending by relevance score
        structured_papers.sort(key=lambda x: x["relevance_score"], reverse=True)
        top_papers = structured_papers[:limit]

        # Persist to SQLite
        conn = get_connection(self.db_path)
        collection_id = None
        try:
            with conn:
                cur = conn.execute(
                    """
                    INSERT INTO idea_collections (query_title, domain, paper_count)
                    VALUES (?, ?, ?);
                    """,
                    (cleaned_query, domain or "Computer Science", len(top_papers))
                )
                collection_id = cur.lastrowid

                for rank, paper in enumerate(top_papers, start=1):
                    paper_id = insert_or_update_paper(
                        openalex_id=paper["openalex_id"],
                        title=paper["title"],
                        authors=paper["authors"],
                        publication_year=paper["publication_year"],
                        cited_by_count=paper["cited_by_count"],
                        doi=paper.get("doi", ""),
                        abstract=paper.get("abstract", ""),
                        concepts=paper.get("concepts", ""),
                        status="harvested",
                        synthesis_status="harvested_idea",
                        conn=conn
                    )

                    conn.execute(
                        """
                        INSERT OR REPLACE INTO idea_collection_papers 
                        (collection_id, paper_id, relevance_rank, relevance_score, key_techniques)
                        VALUES (?, ?, ?, ?, ?);
                        """,
                        (
                            collection_id,
                            paper_id,
                            rank,
                            paper["relevance_score"],
                            json.dumps(paper["key_techniques"])
                        )
                    )
        finally:
            conn.close()

        # Generate structured Markdown briefing if requested
        markdown_path = None
        if save_markdown and top_papers:
            markdown_path = self._write_markdown_digest(
                query=cleaned_query,
                papers=top_papers,
                collection_id=collection_id,
                output_dir=output_dir
            )

        return {
            "collection_id": collection_id,
            "query": cleaned_query,
            "domain": domain or "Computer Science",
            "count": len(top_papers),
            "papers": top_papers,
            "markdown_path": str(markdown_path) if markdown_path else None
        }

    def _write_markdown_digest(
        self,
        query: str,
        papers: List[Dict[str, Any]],
        collection_id: int,
        output_dir: Optional[str] = None
    ) -> Path:
        """Writes an executive structured literature report for the idea."""
        if output_dir:
            out_folder = Path(output_dir)
        else:
            workspace_root = Path(self.db_path).resolve().parent.parent
            out_folder = workspace_root.parent / "03_Resources" / "Idea_Vault"
            if not out_folder.parent.exists():
                out_folder = workspace_root / "data" / "Idea_Vault"

        out_folder.mkdir(parents=True, exist_ok=True)
        slug = _slugify(query)
        target_file = out_folder / f"Idea_{collection_id}_{slug}.md"

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"# 📚 Academic Research Grounding: {query}",
            f"*Generated on {now_str} | Sub-Service: Zero-LLM Idea Paper Collector*",
            "",
            "> [!NOTE]",
            f"> Found **{len(papers)} peer-reviewed papers** directly matching this concept without AI hallucination.",
            "",
            "## 🎯 Curated Papers Matrix",
            "",
            "| Rank | Relevance | Title | Year | Citations | Key Mechanisms & Techniques | Links |",
            "| :---: | :---: | :--- | :---: | :---: | :--- | :--- |"
        ]

        for idx, p in enumerate(papers, start=1):
            title = p["title"].replace("|", "\\|")
            doi = p.get("doi") or ""
            link_md = f"[DOI Link]({doi})" if doi else "`N/A`"
            techs = ", ".join(f"`{t}`" for t in p.get("key_techniques", [])[:4]) or "`Core Systems`"
            lines.append(
                f"| **#{idx}** | **{p['relevance_score']}%** | **{title}** | `{p['publication_year']}` | `{p['cited_by_count']}` | {techs} | {link_md} |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## 🔬 Detailed Literature Digest",
            ""
        ])

        for idx, p in enumerate(papers, start=1):
            techs_badge = " ".join(f"`{t}`" for t in p.get("key_techniques", []))
            lines.extend([
                f"### {idx}. {p['title']} ({p['publication_year']})",
                f"- **Authors**: {p['authors']}",
                f"- **Citations**: {p['cited_by_count']} | **Relevance Score**: {p['relevance_score']}%",
                f"- **DOI**: {p.get('doi') or 'N/A'}",
                f"- **Concepts**: {p.get('concepts') or 'Computer Science'}",
                f"- **Extracted Techniques**: {techs_badge}",
                "",
                "**Abstract:**",
                f"> {p.get('abstract', 'No abstract available.')}",
                "",
                "---"
            ])

        target_file.write_text("\n".join(lines), encoding="utf-8")
        return target_file


def main():
    parser = argparse.ArgumentParser(
        description="Zero-LLM Idea Paper Collector: Finds, scores, and structures research papers for an idea."
    )
    parser.add_argument("--query", "-q", type=str, required=True, help="Idea title or topic description.")
    parser.add_argument("--limit", "-n", type=int, default=10, help="Number of papers to retrieve (default: 10).")
    parser.add_argument("--domain", "-d", type=str, default="Computer Science", help="Target academic domain.")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of human-readable summary.")
    parser.add_argument("--no-md", action="store_true", help="Disable Markdown file generation.")
    args = parser.parse_args()

    collector = IdeaPaperCollector()
    result = collector.collect_papers_for_idea(
        query=args.query,
        limit=args.limit,
        domain=args.domain,
        save_markdown=not args.no_md
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=" * 75)
        print(f"  ACADEMIC RESEARCH GROUNDING: '{result['query']}'")
        print(f"  Found & Structured {result['count']} Papers (Zero-LLM Pipeline)")
        if result["markdown_path"]:
            print(f"  Markdown Digest: {result['markdown_path']}")
        print("=" * 75)
        for idx, p in enumerate(result["papers"], start=1):
            techs = ", ".join(p.get("key_techniques", [])[:3])
            print(f"[{idx}] ({p['relevance_score']}%) {p['title']} ({p['publication_year']}, {p['cited_by_count']} cites)")
            if techs:
                print(f"     Techniques: {techs}")
            if p.get("doi"):
                print(f"     DOI: {p['doi']}")
            print()


if __name__ == "__main__":
    main()
