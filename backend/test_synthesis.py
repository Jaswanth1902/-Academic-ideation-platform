import sys
sys.path.insert(0, "backend")
from database import get_connection
from synthesis_engine import SynthesisEngine
import time

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT * FROM papers LIMIT 1")
paper = dict(cur.fetchone())
print("Paper Title:", paper["title"])

engine = SynthesisEngine()
t0 = time.time()
print("Starting synthesis...")
bp = engine.evaluate_paper(paper)
print("Finished in:", time.time() - t0, "seconds")
print("Blueprint:", bp is not None)
if bp:
    print("Title:", bp.get("title"))
    print("Domains:", bp.get("domains"))
    print("Viability:", bp.get("viability_score"))
