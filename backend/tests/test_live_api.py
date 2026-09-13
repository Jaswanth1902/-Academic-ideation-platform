import json
import urllib.request
import pytest


API_BASE = "http://127.0.0.1:8055"


def test_api_health():
    url = f"{API_BASE}/api/health"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5.0) as res:
        assert res.status == 200
        headers = dict(res.headers)
        assert headers.get("X-Frame-Options") == "DENY"
        assert headers.get("X-Content-Type-Options") == "nosniff"
        assert "Content-Security-Policy" in headers
        data = json.loads(res.read().decode("utf-8"))
        assert data["status"] == "HEALTHY"


def test_api_ideas_and_filtering():
    url = f"{API_BASE}/api/ideas"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5.0) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert "ideas" in data
        assert len(data["ideas"]) > 0

        first = data["ideas"][0]
        assert "domain" in first
        assert "viability_score" in first
        assert "architecture" in first
        assert "milestones" in first
        assert "core_mechanism" in first

    # Test filtering by domain
    target_domain = first["domain"]
    filter_url = f"{API_BASE}/api/ideas?domain={target_domain}"
    with urllib.request.urlopen(filter_url, timeout=5.0) as res:
        assert res.status == 200
        filtered_data = json.loads(res.read().decode("utf-8"))
        assert all(target_domain in i.get("domains", [i.get("domain")]) or i["domain"] == target_domain for i in filtered_data["ideas"])


def test_api_stats_and_telemetry():
    url = f"{API_BASE}/api/stats"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5.0) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert data["total_papers"] > 0
        assert data["total_ideas"] > 0
        assert data["average_viability_score"] > 80
        assert "dlq_stats" in data
