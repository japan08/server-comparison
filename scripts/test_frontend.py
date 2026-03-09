#!/usr/bin/env python3
"""
Test frontend is served and /recommend returns valid response.
Run with server up: uvicorn app.main:app --reload --port 8000
Usage: PYTHONPATH=. python3 scripts/test_frontend.py
"""
import sys
import urllib.request
import urllib.error
import json

BASE = "http://127.0.0.1:8000"


def test_frontend_served():
    """GET / should return HTML with CloudCompare."""
    req = urllib.request.Request(BASE + "/", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode()
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            assert "CloudCompare" in body or "Cloud Compare" in body, "Frontend HTML should contain app title"
            assert "recommend" in body or "Search" in body, "Frontend should reference recommend/search"
            print("OK  GET /  → frontend HTML served")
    except urllib.error.URLError as e:
        print(f"FAIL GET /  → {e}")
        assert False, f"GET / failed: {e}"


def test_recommend_response():
    """POST /recommend with structured body should return recommendations array."""
    payload = {"cpu": 4, "ram": 16, "budget": 100, "region": "Europe"}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + "/recommend",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
            out = json.loads(body)
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            assert "recommendations" in out, "Response must have 'recommendations'"
            assert isinstance(out["recommendations"], list), "'recommendations' must be a list"
            # With seed data we expect at least one result for 4/16/100/Europe
            if out["recommendations"]:
                r = out["recommendations"][0]
                assert "provider" in r and "price_monthly" in r, "Each recommendation must have provider and price_monthly"
                print(f"OK  POST /recommend  → {len(out['recommendations'])} recommendation(s), e.g. {r.get('provider')} ${r.get('price_monthly')}/mo")
            else:
                print("OK  POST /recommend  → 200, recommendations: [] (run seed_data.py if you want sample results)")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"FAIL POST /recommend  → {e.code} {body[:200]}")
        assert False, f"POST /recommend failed: {e.code} {body[:200]}"
    except urllib.error.URLError as e:
        print(f"FAIL POST /recommend  → {e}")
        assert False, f"POST /recommend failed: {e}"


def main():
    print("Testing frontend and API (server must be running on 127.0.0.1:8000)\n")
    test_frontend_served()
    test_recommend_response()
    print()
    print("All checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
