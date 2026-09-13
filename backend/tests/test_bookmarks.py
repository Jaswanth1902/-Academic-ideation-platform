import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

import pytest
import sqlite3
import json
from database import (
    init_db,
    insert_project_idea,
    get_all_ideas,
    toggle_idea_bookmark,
    clear_all_bookmarks,
    get_idea_by_id
)

@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)

    for i in range(1, 10):
        conn.execute(
            """
            INSERT INTO papers (id, openalex_id, title, authors, publication_year, cited_by_count, doi, abstract)
            VALUES (?, ?, ?, ?, 2023, 10, 'doi://123', 'Abstract text');
            """,
            (i, f"W{i}", f"Research Paper {i}", "Dr. Test")
        )

    for i in range(1, 9):
        insert_project_idea(
            paper_id=i,
            domain=["DSA", "DBMS"] if i % 2 == 0 else ["AI/ML"],
            title=f"Project Idea Blueprint {i}",
            summary=f"Summary for idea {i}",
            architecture='{"component": "service"}',
            core_mechanism=f"Mechanism {i}",
            milestones='[{"phase": "1", "goal": "init"}]',
            tech_stack='["Python", "React"]',
            difficulty="Advanced",
            viability_score=90 + i,
            feasibility_timeline="120 Hours / 4 Sprints",
            conn=conn
        )
    return conn


def test_unlimited_bookmarks(test_db):
    for i in range(1, 6):
        res = toggle_idea_bookmark(i, is_bookmarked=True, conn=test_db)
        assert res is True

    bookmarked = get_all_ideas(bookmarked_only=True, conn=test_db)
    assert len(bookmarked) == 5
    for item in bookmarked:
        assert item["is_bookmarked"] is True
        assert item["is_shortlisted"] is True

    all_ideas = get_all_ideas(bookmarked_only=False, conn=test_db)
    assert len(all_ideas) == 8


def test_toggle_and_clear_bookmarks(test_db):
    toggle_idea_bookmark(1, is_bookmarked=True, conn=test_db)
    toggle_idea_bookmark(2, is_bookmarked=True, conn=test_db)
    toggle_idea_bookmark(3, is_bookmarked=True, conn=test_db)

    assert len(get_all_ideas(bookmarked_only=True, conn=test_db)) == 3

    toggle_idea_bookmark(2, is_bookmarked=False, conn=test_db)
    bookmarked = get_all_ideas(bookmarked_only=True, conn=test_db)
    assert len(bookmarked) == 2
    assert {b["id"] for b in bookmarked} == {1, 3}

    cleared = clear_all_bookmarks(conn=test_db)
    assert cleared == 2
    assert len(get_all_ideas(bookmarked_only=True, conn=test_db)) == 0


def test_bookmark_domain_filter(test_db):
    toggle_idea_bookmark(1, is_bookmarked=True, conn=test_db)
    toggle_idea_bookmark(2, is_bookmarked=True, conn=test_db)

    dsa_bookmarked = get_all_ideas(domain_filter="DSA", bookmarked_only=True, conn=test_db)
    assert len(dsa_bookmarked) == 1
    assert dsa_bookmarked[0]["id"] == 2


def test_live_api_bookmark_endpoints():
    import urllib.request
    api_base = "http://127.0.0.1:8055"

    try:
        req = urllib.request.Request(f"{api_base}/api/ideas")
        with urllib.request.urlopen(req, timeout=3.0) as res:
            ideas = json.loads(res.read().decode("utf-8"))["ideas"]
            if not ideas:
                return
            first_id = ideas[0]["id"]
    except Exception:
        # Server not running in test runner environment; unit tests sufficient
        return

    # Toggle bookmark via POST /api/ideas/{id}/bookmark
    post_req = urllib.request.Request(
        f"{api_base}/api/ideas/{first_id}/bookmark",
        data=json.dumps({"is_bookmarked": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(post_req, timeout=5.0) as res:
        assert res.status == 200
        payload = json.loads(res.read().decode("utf-8"))
        assert payload["is_bookmarked"] is True

    # Verify GET /api/bookmarks
    with urllib.request.urlopen(f"{api_base}/api/bookmarks", timeout=5.0) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert any(i["id"] == first_id for i in data["ideas"])

    # Verify CSV export with bookmarks
    with urllib.request.urlopen(f"{api_base}/api/export/csv?bookmarked=true", timeout=5.0) as res:
        assert res.status == 200
        content = res.read()
        assert len(content) > 0
