"""
Dead-Letter Queue (DLQ) Manager for resilient pipeline failures.
Enforces max 2 API/LLM retries before silent discard per specification.
"""

import sqlite3
from typing import Dict, Any, List, Optional
from config import MAX_RETRIES
from database import get_connection, update_paper_status


class DLQManager:
    """Manages Dead-Letter Queue items, retry cycles, and silent discard policies."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def record_failure(
        self,
        entity_type: str,
        entity_id: str,
        error_message: str,
        conn: Optional[sqlite3.Connection] = None
    ) -> Dict[str, Any]:
        """
        Records a failure for an entity (paper_fetch, paper_synthesis).
        Increments retry count. If retry_count >= MAX_RETRIES (2),
        marks as 'discarded' (silent discard) and terminates retry loop.
        """
        should_close = False
        if conn is None:
            conn = get_connection(self.db_path)
            should_close = True

        try:
            with conn:
                cursor = conn.execute(
                    """
                    SELECT id, retry_count, status
                    FROM dead_letter_queue
                    WHERE entity_type = ? AND entity_id = ?;
                    """,
                    (entity_type, entity_id)
                )
                existing = cursor.fetchone()

                if existing:
                    new_retry_count = existing["retry_count"] + 1
                    new_status = "discarded" if new_retry_count >= MAX_RETRIES else "retryable"

                    conn.execute(
                        """
                        UPDATE dead_letter_queue
                        SET retry_count = ?,
                            status = ?,
                            error_message = ?,
                            last_attempt = CURRENT_TIMESTAMP
                        WHERE id = ?;
                        """,
                        (new_retry_count, new_status, error_message, existing["id"])
                    )
                    dlq_id = existing["id"]
                else:
                    new_retry_count = 1
                    new_status = "retryable"
                    cursor = conn.execute(
                        """
                        INSERT INTO dead_letter_queue (
                            entity_type, entity_id, error_message, retry_count, status
                        ) VALUES (?, ?, ?, ?, ?)
                        RETURNING id;
                        """,
                        (entity_type, entity_id, error_message, new_retry_count, new_status)
                    )
                    row = cursor.fetchone()
                    dlq_id = row["id"] if row else -1

                # If permanently discarded and entity is a paper, update paper status
                if new_status == "discarded" and entity_type in ("paper_synthesis", "paper_fetch"):
                    try:
                        paper_num_id = int(entity_id)
                        conn.execute("UPDATE papers SET status = 'discarded' WHERE id = ?;", (paper_num_id,))
                    except ValueError:
                        pass

                return {
                    "dlq_id": dlq_id,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "retry_count": new_retry_count,
                    "status": new_status,
                    "silently_discarded": (new_status == "discarded")
                }
        finally:
            if should_close:
                conn.close()

    def mark_resolved(
        self,
        entity_type: str,
        entity_id: str,
        conn: Optional[sqlite3.Connection] = None
    ) -> bool:
        """Removes an entity from DLQ upon successful processing."""
        should_close = False
        if conn is None:
            conn = get_connection(self.db_path)
            should_close = True

        try:
            with conn:
                cursor = conn.execute(
                    "DELETE FROM dead_letter_queue WHERE entity_type = ? AND entity_id = ?;",
                    (entity_type, entity_id)
                )
                return cursor.rowcount > 0
        finally:
            if should_close:
                conn.close()

    def get_retryable_entries(
        self,
        entity_type: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None
    ) -> List[Dict[str, Any]]:
        """Returns entries that have not exceeded MAX_RETRIES."""
        should_close = False
        if conn is None:
            conn = get_connection(self.db_path)
            should_close = True

        try:
            if entity_type:
                cursor = conn.execute(
                    """
                    SELECT * FROM dead_letter_queue
                    WHERE status = 'retryable' AND entity_type = ? AND retry_count < ?
                    ORDER BY last_attempt ASC;
                    """,
                    (entity_type, MAX_RETRIES)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM dead_letter_queue
                    WHERE status = 'retryable' AND retry_count < ?
                    ORDER BY last_attempt ASC;
                    """,
                    (MAX_RETRIES,)
                )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            if should_close:
                conn.close()

    def get_discarded_entries(
        self,
        limit: int = 50,
        conn: Optional[sqlite3.Connection] = None
    ) -> List[Dict[str, Any]]:
        """Returns entries silently discarded after exhausting max retries."""
        should_close = False
        if conn is None:
            conn = get_connection(self.db_path)
            should_close = True

        try:
            cursor = conn.execute(
                """
                SELECT * FROM dead_letter_queue
                WHERE status = 'discarded'
                ORDER BY last_attempt DESC
                LIMIT ?;
                """,
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            if should_close:
                conn.close()
