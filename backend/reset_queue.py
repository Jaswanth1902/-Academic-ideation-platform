import sqlite3
for path in [
    r"C:\Users\jaswa\Antigravity\01_Projects\Academic_Ideation_Platform\data\academic_ideation.db",
    r"c:\Users\jaswa\Downloads\Antigrav\01_Projects\Academic_Ideation_Platform\data\academic_ideation.db"
]:
    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("UPDATE papers SET synthesis_status = 'pending' WHERE synthesis_status = 'failed';")
        reset_count = cur.rowcount
        cur.execute("DELETE FROM dead_letter_queue;")
        dlq_count = cur.rowcount
        conn.commit()
        cur.execute("SELECT synthesis_status, count(*) FROM papers GROUP BY synthesis_status;")
        stats = cur.fetchall()
        print(f"[{path}] Reset {reset_count} papers to pending, cleared {dlq_count} DLQ entries. Status: {stats}")
        conn.close()
    except Exception as e:
        print(f"[{path}] Error: {e}")
