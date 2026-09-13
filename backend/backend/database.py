"""
Persistent SQLite database layer with parameterized queries and schema migrations.
Zero third-party dependencies (uses Python standard library sqlite3).
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from config import DB_PATH, DATA_DIR


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Returns a SQLite connection configured with WAL journal mode and row factory."""
    resolved_path = Path(db_path or DB_PATH)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(resolved_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def init_db(db_path: Optional[Any] = None) -> None:
    """Initializes schema tables: papers, project_ideas, and dead_letter_queue."""
    should_close = True
    if isinstance(db_path, sqlite3.Connection):
        conn = db_path
        should_close = False
    else:
        conn = get_connection(db_path)
    with conn:
        # 1. Papers table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS papers (
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
                synthesis_status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Ensure synthesis_status column exists for existing SQLite tables
        cursor_papers = conn.execute("PRAGMA table_info(papers);")
        paper_cols = {row["name"] for row in cursor_papers.fetchall()}
        if "synthesis_status" not in paper_cols:
            conn.execute("ALTER TABLE papers ADD COLUMN synthesis_status TEXT NOT NULL DEFAULT 'pending';")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_status ON papers (status);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_synthesis_status ON papers (synthesis_status);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_year ON papers (publication_year);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_citations ON papers (cited_by_count);")

        # 2. Project Ideas table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_ideas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id INTEGER NOT NULL,
                domain TEXT NOT NULL,
                title TEXT NOT NULL,
                core_concept TEXT,
                target_service TEXT,
                novelty TEXT,
                selling_point TEXT,
                summary TEXT NOT NULL,
                architecture TEXT NOT NULL,
                core_mechanism TEXT NOT NULL,
                milestones TEXT NOT NULL,
                tech_stack TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                viability_score INTEGER NOT NULL,
                feasibility_timeline TEXT DEFAULT '120 Hours / 4 Sprints',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paper_id) REFERENCES papers (id) ON DELETE CASCADE
            );
        """)
        # Dynamic schema migration for existing SQLite databases
        cursor = conn.execute("PRAGMA table_info(project_ideas);")
        existing_cols = {row["name"] for row in cursor.fetchall()}
        for col in ["core_concept", "target_service", "novelty", "selling_point"]:
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE project_ideas ADD COLUMN {col} TEXT;")
        if "is_shortlisted" not in existing_cols:
            conn.execute("ALTER TABLE project_ideas ADD COLUMN is_shortlisted INTEGER NOT NULL DEFAULT 0;")
        if "feasibility_timeline" not in existing_cols:
            conn.execute("ALTER TABLE project_ideas ADD COLUMN feasibility_timeline TEXT DEFAULT '120 Hours / 4 Sprints';")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_ideas_domain ON project_ideas (domain);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ideas_score ON project_ideas (viability_score);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ideas_shortlisted ON project_ideas (is_shortlisted);")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ideas_paper_id ON project_ideas (paper_id);")

        # Papers schema migration for synthesis_status column
        cursor_papers = conn.execute("PRAGMA table_info(papers);")
        paper_cols = {row["name"] for row in cursor_papers.fetchall()}
        if "synthesis_status" not in paper_cols:
            conn.execute("ALTER TABLE papers ADD COLUMN synthesis_status TEXT NOT NULL DEFAULT 'pending';")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_synthesis_status ON papers (synthesis_status);")

        # Automatically migrate scalar domains and missing timelines
        migrate_domains_and_timelines(conn)

        # Revert all existing corrupted papers to pending state
        revert_corrupted_papers(conn)

        # 3. Dead-Letter Queue (DLQ) table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dead_letter_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                error_message TEXT NOT NULL,
                retry_count INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'retryable',
                last_attempt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (entity_type, entity_id)
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_dlq_status ON dead_letter_queue (status);")

        # 4. Idea Collections & Idea Papers (User-Initiated Idea Search, Zero-LLM)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS idea_collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_title TEXT NOT NULL,
                domain TEXT,
                paper_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_idea_collections_query ON idea_collections (query_title);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS idea_collection_papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_id INTEGER NOT NULL,
                paper_id INTEGER NOT NULL,
                relevance_rank INTEGER NOT NULL,
                relevance_score REAL NOT NULL DEFAULT 0.0,
                key_techniques TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (collection_id) REFERENCES idea_collections (id) ON DELETE CASCADE,
                FOREIGN KEY (paper_id) REFERENCES papers (id) ON DELETE CASCADE,
                UNIQUE (collection_id, paper_id)
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_idea_collection_papers_coll ON idea_collection_papers (collection_id);")
    if should_close:
        conn.close()


def migrate_domains_and_timelines(conn: Optional[sqlite3.Connection] = None) -> int:
    """
    Migrates existing project_ideas records:
    - Converts scalar domain string to JSON array string (e.g. 'DBMS' -> '["DBMS"]').
    - Ensures feasibility_timeline is populated according to difficulty.
    Returns the count of updated records.
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    updated_count = 0
    try:
        cursor = conn.execute("SELECT id, domain, difficulty, feasibility_timeline FROM project_ideas;")
        rows = cursor.fetchall()
        for row in rows:
            raw_dom = row["domain"]
            raw_timeline = row["feasibility_timeline"]
            needs_update = False

            # Check domain
            dom_list = []
            if raw_dom:
                try:
                    parsed = json.loads(raw_dom)
                    if isinstance(parsed, list):
                        dom_list = [str(d).strip() for d in parsed if str(d).strip()]
                    elif isinstance(parsed, str):
                        dom_list = [parsed.strip()]
                        needs_update = True
                    else:
                        dom_list = [str(parsed).strip()]
                        needs_update = True
                except Exception:
                    if "," in raw_dom:
                        dom_list = [d.strip() for d in raw_dom.split(",") if d.strip()]
                    else:
                        dom_list = [raw_dom.strip()]
                    needs_update = True
            else:
                dom_list = ["Full-Stack"]
                needs_update = True

            # Check timeline
            timeline = raw_timeline
            if not timeline or not str(timeline).strip():
                diff = (row["difficulty"] or "Intermediate").strip().lower()
                if "hard" in diff:
                    timeline = "160 Hours / 5 Sprints"
                elif "adv" in diff:
                    timeline = "120 Hours / 4 Sprints"
                elif "beg" in diff:
                    timeline = "60 Hours / 2 Sprints"
                else:
                    timeline = "80 Hours / 3 Sprints"
                needs_update = True

            if needs_update:
                conn.execute(
                    "UPDATE project_ideas SET domain = ?, feasibility_timeline = ? WHERE id = ?;",
                    (json.dumps(dom_list), timeline, row["id"])
                )
                updated_count += 1
        return updated_count
    finally:
        if should_close:
            conn.close()


def revert_corrupted_papers(conn: Optional[sqlite3.Connection] = None) -> int:
    """
    Reverts all existing corrupted papers to 'pending' state.
    Identifies corrupted papers:
      1. Papers associated with boilerplate/deterministic fallback ideas.
      2. Papers marked completed/processed but having no corresponding project idea.
      3. Papers where synthesis_status is corrupted or not in ('pending', 'completed', 'failed').
    Purges corrupted project_ideas and sets synthesis_status = 'pending', status = 'pending'.
    Returns the count of reverted papers.
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    reverted_count = 0
    try:
        with conn:
            # Find paper IDs with deterministic boilerplate ideas
            cursor = conn.execute("""
                SELECT DISTINCT paper_id FROM project_ideas 
                WHERE selling_point LIKE '%benchmark-verified production prototype%'
                   OR summary LIKE '%Engineered directly from%'
                   OR architecture LIKE '%High-velocity client interface%'
                   OR core_concept LIKE '%A production-grade implementation of%';
            """)
            deterministic_paper_ids = [row[0] for row in cursor.fetchall()]

            # Find papers marked processed/completed that have no idea in project_ideas
            cursor2 = conn.execute("""
                SELECT id FROM papers 
                WHERE (status = 'processed' OR synthesis_status = 'completed')
                  AND id NOT IN (SELECT paper_id FROM project_ideas);
            """)
            missing_idea_paper_ids = [row[0] for row in cursor2.fetchall()]

            # Find papers with invalid or missing synthesis_status
            cursor3 = conn.execute("""
                SELECT id FROM papers 
                WHERE synthesis_status NOT IN ('pending', 'completed', 'failed')
                   OR synthesis_status IS NULL;
            """)
            invalid_status_paper_ids = [row[0] for row in cursor3.fetchall()]

            all_to_revert = set(deterministic_paper_ids + missing_idea_paper_ids + invalid_status_paper_ids)

            if deterministic_paper_ids:
                conn.execute(f"""
                    DELETE FROM project_ideas 
                    WHERE paper_id IN ({','.join(['?'] * len(deterministic_paper_ids))});
                """, deterministic_paper_ids)

            for pid in all_to_revert:
                conn.execute("""
                    UPDATE papers 
                    SET synthesis_status = 'pending', status = 'pending' 
                    WHERE id = ?;
                """, (pid,))
                reverted_count += 1

            # For papers that already have valid non-deterministic ideas, ensure their status is 'completed'
            conn.execute("""
                UPDATE papers 
                SET synthesis_status = 'completed', status = 'processed'
                WHERE id IN (SELECT paper_id FROM project_ideas)
                  AND synthesis_status != 'completed';
            """)

            # Ensure any paper without ideas is marked pending
            conn.execute("""
                UPDATE papers 
                SET synthesis_status = 'pending', status = 'pending'
                WHERE id NOT IN (SELECT paper_id FROM project_ideas)
                  AND synthesis_status = 'completed';
            """)

        return reverted_count
    finally:
        if should_close:
            conn.close()


def insert_or_update_paper(
    openalex_id: str,
    title: str,
    authors: str,
    publication_year: int,
    cited_by_count: int,
    doi: str,
    abstract: str,
    concepts: str,
    status: str = "pending",
    conn: Optional[sqlite3.Connection] = None,
    return_is_new: bool = False,
    synthesis_status: str = "pending"
) -> Any:
    """
    Inserts a new paper or returns existing paper id using parameterized SQL.
    If paper was previously stored but never generated a project idea, it is re-queued as 'pending'.
    Returns int id, or tuple (id, is_new) if return_is_new is True.
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        with conn:
            existing = conn.execute(
                "SELECT id, status, synthesis_status FROM papers WHERE openalex_id = ? LIMIT 1;",
                (openalex_id,)
            ).fetchone()

            if not existing:
                cursor = conn.execute(
                    """
                    INSERT INTO papers (openalex_id, title, authors, publication_year, cited_by_count, doi, abstract, concepts, status, synthesis_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (openalex_id, title, authors, publication_year, cited_by_count, doi, abstract, concepts, status, synthesis_status)
                )
                paper_id = cursor.lastrowid
                return (paper_id, True) if return_is_new else paper_id
            else:
                paper_id = existing["id"]
                # Check if this paper ever produced a synthesized project idea
                has_idea = conn.execute(
                    "SELECT 1 FROM project_ideas WHERE paper_id = ? LIMIT 1;",
                    (paper_id,)
                ).fetchone()

                if not has_idea and (existing["status"] != "pending" or existing["synthesis_status"] != "pending"):
                    # Re-queue for synthesis
                    conn.execute(
                        "UPDATE papers SET status = 'pending', synthesis_status = 'pending', cited_by_count = ? WHERE id = ?;",
                        (cited_by_count, paper_id)
                    )
                    return (paper_id, True) if return_is_new else paper_id
                else:
                    conn.execute(
                        "UPDATE papers SET cited_by_count = ? WHERE id = ?;",
                        (cited_by_count, paper_id)
                    )
                    return (paper_id, False) if return_is_new else paper_id
    finally:
        if should_close:
            conn.close()


def get_pending_papers(limit: int = 50, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """Retrieves pending papers ready for synthesis."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        cursor = conn.execute(
            """
            SELECT * FROM papers 
            WHERE synthesis_status = 'pending' 
               OR (synthesis_status IS NULL AND status = 'pending')
            ORDER BY cited_by_count DESC 
            LIMIT ?;
            """,
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        if should_close:
            conn.close()


VALID_SYNTHESIS_STATUSES = {"pending", "completed", "failed"}


def update_paper_synthesis_status(paper_id: int, synthesis_status: str, conn: Optional[sqlite3.Connection] = None) -> None:
    """
    Updates synthesis state machine status of a paper with strict validation.
    Permitted states: 'pending', 'completed', 'failed'.
    """
    if synthesis_status not in VALID_SYNTHESIS_STATUSES:
        raise ValueError(f"Invalid synthesis_status: '{synthesis_status}'. Must be one of {sorted(VALID_SYNTHESIS_STATUSES)}")

    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    legacy_status = "processed" if synthesis_status == "completed" else synthesis_status

    try:
        with conn:
            conn.execute(
                "UPDATE papers SET synthesis_status = ?, status = ? WHERE id = ?;",
                (synthesis_status, legacy_status, paper_id)
            )
    finally:
        if should_close:
            conn.close()


def update_paper_status(paper_id: int, status: str, conn: Optional[sqlite3.Connection] = None) -> None:
    """Updates processing status of a paper (legacy wrapper)."""
    if status == "processed":
        synthesis_status = "completed"
    elif status in ("discarded", "failed"):
        synthesis_status = "failed"
    else:
        synthesis_status = "pending"
    update_paper_synthesis_status(paper_id, synthesis_status, conn=conn)


def _hydrate_idea_row(item: Dict[str, Any]) -> Dict[str, Any]:
    """Hydrates raw SQLite row dictionary into fully parsed and normalized project idea."""
    # 1. Parse domain into domains list + domain scalar
    raw_dom = item.get("domain", "")
    dom_list = []
    if raw_dom:
        try:
            parsed = json.loads(raw_dom)
            if isinstance(parsed, list):
                dom_list = [str(d).strip() for d in parsed if str(d).strip()]
            elif isinstance(parsed, str):
                dom_list = [parsed.strip()]
            else:
                dom_list = [str(parsed).strip()]
        except Exception:
            if "," in raw_dom:
                dom_list = [d.strip() for d in raw_dom.split(",") if d.strip()]
            else:
                dom_list = [raw_dom.strip()]
    if not dom_list:
        dom_list = ["Full-Stack"]

    item["domains"] = dom_list
    item["domain"] = dom_list[0]

    # 2. Feasibility timeline
    if not item.get("feasibility_timeline"):
        diff = (item.get("difficulty") or "Intermediate").strip().lower()
        if "hard" in diff:
            item["feasibility_timeline"] = "160 Hours / 5 Sprints"
        elif "adv" in diff:
            item["feasibility_timeline"] = "120 Hours / 4 Sprints"
        elif "beg" in diff:
            item["feasibility_timeline"] = "60 Hours / 2 Sprints"
        else:
            item["feasibility_timeline"] = "80 Hours / 3 Sprints"

    # 3. 4-point scannable fields
    primary_domain = item["domain"]
    if not item.get("core_concept"):
        item["core_concept"] = item.get("summary", "").split(".")[0] + "." if item.get("summary") else f"High-performance {primary_domain} systems implementation."
    if not item.get("target_service"):
        item["target_service"] = f"{primary_domain} production service runtime"
    if not item.get("novelty"):
        mech = item.get("core_mechanism", "")
        item["novelty"] = mech[:120] + "..." if len(mech) > 120 else (mech or "Algorithmic optimization derived from research.")
    if not item.get("selling_point"):
        item["selling_point"] = f"Demonstrates mastery of {primary_domain} architecture and low-latency engineering."

    # 4. JSON fields
    for key in ["architecture", "milestones", "tech_stack"]:
        if isinstance(item.get(key), str):
            try:
                item[key] = json.loads(item[key])
            except Exception:
                pass
    item["is_shortlisted"] = bool(item.get("is_shortlisted", 0))
    item["is_bookmarked"] = item["is_shortlisted"]
    return item


def insert_project_idea(
    paper_id: int,
    domain: Any,
    title: str,
    summary: str,
    architecture: str,
    core_mechanism: str,
    milestones: str,
    tech_stack: str,
    difficulty: str,
    viability_score: int,
    core_concept: Optional[str] = None,
    target_service: Optional[str] = None,
    novelty: Optional[str] = None,
    selling_point: Optional[str] = None,
    feasibility_timeline: str = "120 Hours / 4 Sprints",
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """Inserts or updates an evaluated project idea idempotently to prevent duplicate records."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    # Normalize domain to JSON array string
    if isinstance(domain, list):
        clean_domains = [str(d).strip() for d in domain if str(d).strip()]
        domain_str = json.dumps(clean_domains if clean_domains else ["Full-Stack"])
    elif isinstance(domain, str):
        if domain.startswith("[") and domain.endswith("]"):
            try:
                parsed = json.loads(domain)
                domain_str = json.dumps(parsed if isinstance(parsed, list) else [str(parsed)])
            except Exception:
                domain_str = json.dumps([domain])
        elif "," in domain:
            domain_str = json.dumps([d.strip() for d in domain.split(",") if d.strip()])
        else:
            domain_str = json.dumps([domain.strip()] if domain.strip() else ["Full-Stack"])
    else:
        domain_str = json.dumps(["Full-Stack"])

    # Provide timeline fallback based on difficulty if not provided
    if not feasibility_timeline or not str(feasibility_timeline).strip():
        diff = (difficulty or "Intermediate").strip().lower()
        if "hard" in diff:
            feasibility_timeline = "160 Hours / 5 Sprints"
        elif "adv" in diff:
            feasibility_timeline = "120 Hours / 4 Sprints"
        elif "beg" in diff:
            feasibility_timeline = "60 Hours / 2 Sprints"
        else:
            feasibility_timeline = "80 Hours / 3 Sprints"

    try:
        with conn:
            existing = conn.execute(
                "SELECT id FROM project_ideas WHERE paper_id = ? LIMIT 1;",
                (paper_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE project_ideas SET
                        domain = ?, title = ?, summary = ?, architecture = ?,
                        core_mechanism = ?, milestones = ?, tech_stack = ?, difficulty = ?, viability_score = ?,
                        core_concept = ?, target_service = ?, novelty = ?, selling_point = ?, feasibility_timeline = ?
                    WHERE id = ?;
                    """,
                    (
                        domain_str, title, summary, architecture,
                        core_mechanism, milestones, tech_stack, difficulty, viability_score,
                        core_concept, target_service, novelty, selling_point, feasibility_timeline,
                        existing["id"]
                    )
                )
                return existing["id"]
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO project_ideas (
                        paper_id, domain, title, summary, architecture,
                        core_mechanism, milestones, tech_stack, difficulty, viability_score,
                        core_concept, target_service, novelty, selling_point, feasibility_timeline
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    RETURNING id;
                    """,
                    (
                        paper_id, domain_str, title, summary, architecture,
                        core_mechanism, milestones, tech_stack, difficulty, viability_score,
                        core_concept, target_service, novelty, selling_point, feasibility_timeline
                    )
                )
                row = cursor.fetchone()
                return row["id"] if row else -1
    finally:
        if should_close:
            conn.close()


def get_all_ideas(
    domain_filter: Optional[str] = None,
    sort_by: str = "created_at",
    bookmarked_only: bool = False,
    conn: Optional[sqlite3.Connection] = None
) -> List[Dict[str, Any]]:
    """
    Fetches all project ideas with joined paper metadata, optionally filtered by domain and sorted.
    Default sort is 'created_at' (newest first) to ensure newly ingested ideas appear at the top.
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    # Determine ordering
    if sort_by in ("viability", "score"):
        order_clause = "ORDER BY pi.viability_score DESC, pi.created_at DESC"
    else:
        # Default: newest first
        order_clause = "ORDER BY pi.created_at DESC, pi.id DESC"

    try:
        cursor = conn.execute(
            f"""
            SELECT
                pi.*,
                p.title AS paper_title,
                p.authors AS paper_authors,
                p.publication_year,
                p.cited_by_count,
                p.doi,
                p.abstract AS paper_abstract
            FROM project_ideas pi
            JOIN papers p ON pi.paper_id = p.id
            {order_clause};
            """
        )

        results = []
        for row in cursor.fetchall():
            item = _hydrate_idea_row(dict(row))

            # Filter by bookmark status if requested
            if bookmarked_only and not item.get("is_bookmarked", False):
                continue

            # Filter by domain if specified (matching any in domains list or primary domain)
            if domain_filter and domain_filter.upper() != "ALL":
                if domain_filter not in item["domains"] and domain_filter != item["domain"]:
                    continue

            results.append(item)
        return results
    finally:
        if should_close:
            conn.close()


def get_idea_by_id(idea_id: int, conn: Optional[sqlite3.Connection] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a single project idea by id."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        cursor = conn.execute(
            """
            SELECT
                pi.*,
                p.title AS paper_title,
                p.authors AS paper_authors,
                p.publication_year,
                p.cited_by_count,
                p.doi,
                p.abstract AS paper_abstract
            FROM project_ideas pi
            JOIN papers p ON pi.paper_id = p.id
            WHERE pi.id = ?;
            """,
            (idea_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return _hydrate_idea_row(dict(row))
    finally:
        if should_close:
            conn.close()


def get_idea_by_paper_or_id(identifier: int, conn: Optional[sqlite3.Connection] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a single project idea by paper_id or idea id."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        cursor = conn.execute(
            """
            SELECT
                pi.*,
                p.title AS paper_title,
                p.authors AS paper_authors,
                p.publication_year,
                p.cited_by_count,
                p.doi,
                p.abstract AS paper_abstract
            FROM project_ideas pi
            JOIN papers p ON pi.paper_id = p.id
            WHERE pi.paper_id = ? OR pi.id = ?
            ORDER BY pi.id DESC
            LIMIT 1;
            """,
            (identifier, identifier)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return _hydrate_idea_row(dict(row))
    finally:
        if should_close:
            conn.close()


def toggle_idea_shortlist(
    idea_id: int,
    is_shortlisted: Optional[bool] = None,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[bool]:
    """
    Toggles or sets the shortlist state for a given idea.
    Returns the updated boolean status or None if the idea does not exist.
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        with conn:
            cursor = conn.execute("SELECT is_shortlisted FROM project_ideas WHERE id = ? LIMIT 1;", (idea_id,))
            row = cursor.fetchone()
            if not row:
                return None
            current = bool(row["is_shortlisted"])
            target = not current if is_shortlisted is None else bool(is_shortlisted)
            val = 1 if target else 0
            conn.execute("UPDATE project_ideas SET is_shortlisted = ? WHERE id = ?;", (val, idea_id))
            return target
    finally:
        if should_close:
            conn.close()


def toggle_idea_bookmark(
    idea_id: int,
    is_bookmarked: Optional[bool] = None,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[bool]:
    """Alias for toggle_idea_shortlist to support the Bookmarks API."""
    return toggle_idea_shortlist(idea_id, is_shortlisted=is_bookmarked, conn=conn)


def clear_all_bookmarks(conn: Optional[sqlite3.Connection] = None) -> int:
    """Resets is_shortlisted to 0 for all project ideas. Returns count of affected rows."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        with conn:
            cursor = conn.execute("UPDATE project_ideas SET is_shortlisted = 0 WHERE is_shortlisted = 1;")
            return cursor.rowcount
    finally:
        if should_close:
            conn.close()


def get_telemetry_stats(conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Aggregates platform statistics for telemetry dashboards."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        total_papers = conn.execute("SELECT COUNT(*) AS count FROM papers;").fetchone()["count"]
        processed_papers = conn.execute("SELECT COUNT(*) AS count FROM papers WHERE status = 'processed';").fetchone()["count"]
        pending_papers = conn.execute("SELECT COUNT(*) AS count FROM papers WHERE status = 'pending';").fetchone()["count"]
        discarded_papers = conn.execute("SELECT COUNT(*) AS count FROM papers WHERE status = 'discarded';").fetchone()["count"]

        total_ideas = conn.execute("SELECT COUNT(*) AS count FROM project_ideas;").fetchone()["count"]
        avg_score = conn.execute("SELECT COALESCE(AVG(viability_score), 0) AS avg FROM project_ideas;").fetchone()["avg"]

        domain_counts = {}
        domain_rows = conn.execute("SELECT domain FROM project_ideas;").fetchall()
        for row in domain_rows:
            raw = row["domain"]
            if raw:
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        for d in parsed:
                            d_clean = str(d).strip()
                            if d_clean:
                                domain_counts[d_clean] = domain_counts.get(d_clean, 0) + 1
                    elif isinstance(parsed, str):
                        domain_counts[parsed] = domain_counts.get(parsed, 0) + 1
                except Exception:
                    domain_counts[raw] = domain_counts.get(raw, 0) + 1

        dlq_total = conn.execute("SELECT COUNT(*) AS count FROM dead_letter_queue;").fetchone()["count"]
        dlq_retryable = conn.execute("SELECT COUNT(*) AS count FROM dead_letter_queue WHERE status = 'retryable';").fetchone()["count"]
        dlq_discarded = conn.execute("SELECT COUNT(*) AS count FROM dead_letter_queue WHERE status = 'discarded';").fetchone()["count"]

        cursor_synth = conn.execute("PRAGMA table_info(papers);")
        has_synth_col = any(r["name"] == "synthesis_status" for r in cursor_synth.fetchall())
        if has_synth_col:
            synthesis_completed = conn.execute("SELECT COUNT(*) AS count FROM papers WHERE synthesis_status = 'completed';").fetchone()["count"]
            synthesis_pending = conn.execute("SELECT COUNT(*) AS count FROM papers WHERE synthesis_status = 'pending';").fetchone()["count"]
            synthesis_failed = conn.execute("SELECT COUNT(*) AS count FROM papers WHERE synthesis_status = 'failed';").fetchone()["count"]
        else:
            synthesis_completed = processed_papers
            synthesis_pending = pending_papers
            synthesis_failed = discarded_papers

        return {
            "total_papers": total_papers,
            "processed_papers": processed_papers,
            "pending_papers": pending_papers,
            "discarded_papers": discarded_papers,
            "synthesis_completed": synthesis_completed,
            "synthesis_pending": synthesis_pending,
            "synthesis_failed": synthesis_failed,
            "total_ideas": total_ideas,
            "average_viability_score": round(avg_score, 1),
            "domain_counts": domain_counts,
            "dlq_stats": {
                "total_failures": dlq_total,
                "retryable": dlq_retryable,
                "silently_discarded": dlq_discarded,
            }
        }
    finally:
        if should_close:
            conn.close()


def get_idea_collections(limit: int = 50, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """Retrieves recent user-initiated idea research collections."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    try:
        rows = conn.execute(
            "SELECT id, query_title, domain, paper_count, created_at FROM idea_collections ORDER BY id DESC LIMIT ?;",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if should_close:
            conn.close()


def get_collection_papers(collection_id: int, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    """Retrieves all structured papers associated with an idea collection."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    try:
        rows = conn.execute("""
            SELECT p.id, p.openalex_id, p.title, p.authors, p.publication_year, 
                   p.cited_by_count, p.doi, p.abstract, p.concepts,
                   icp.relevance_rank, icp.relevance_score, icp.key_techniques
            FROM idea_collection_papers icp
            JOIN papers p ON icp.paper_id = p.id
            WHERE icp.collection_id = ?
            ORDER BY icp.relevance_rank ASC;
        """, (collection_id,)).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            if d.get("key_techniques"):
                try:
                    d["key_techniques"] = json.loads(d["key_techniques"])
                except Exception:
                    pass
            results.append(d)
        return results
    finally:
        if should_close:
            conn.close()

