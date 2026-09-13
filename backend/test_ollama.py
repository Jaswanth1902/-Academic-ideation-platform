import urllib.request
import json
import time

t0 = time.time()
payload = {
    "model": "qwen2.5-coder:7b",
    "prompt": "Return JSON: {\"answer\": 4}",
    "stream": False,
    "format": "json"
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
