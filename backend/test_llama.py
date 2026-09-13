import urllib.request
import json
import time

t0 = time.time()
payload = {
    "model": "llama3.2:3b",
    "prompt": "You are a Principal Software Architect. Synthesize a CS capstone project for this paper in valid JSON with fields title, summary, core_concept, target_service, tech_stack: Paper: High Performance Query Engine on Vector Database.",
    "stream": False,
    "format": "json",
    "options": {
        "temperature": 0.2,
        "num_thread": 8,
        "num_predict": 500,
        "num_ctx": 2048
    }
}
req = urllib.request.Request(
    "http://127.0.0.1:11435/api/generate",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        print("Success in:", time.time() - t0, "seconds")
        print(resp.read().decode("utf-8")[:300])
except Exception as e:
    print("Error:", type(e), e, "after", time.time() - t0, "seconds")
