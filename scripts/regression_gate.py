#!/usr/bin/env python3
"""
Regression Gate — Pre-deploy validation
========================================
Runs the regression harness and blocks deploy if any tests fail.

Usage:
    python scripts/regression_gate.py [--base-url URL] [--timeout SECONDS]

Exit codes:
    0 — all tests passed, safe to deploy
    1 — one or more tests failed, DO NOT deploy
    2 — could not connect to backend
"""

import sys
import os
import json
import time
import argparse
import urllib.request
import urllib.error

DEFAULT_URL = "https://agency-os-backend-cf5y.onrender.com"
DEFAULT_TIMEOUT = 30

def check_health(base_url: str) -> bool:
    """Check if backend is up and responsive."""
    try:
        req = urllib.request.Request(f"{base_url}/health", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("status") == "healthy"
    except Exception:
        return False

def run_endpoint_tests(base_url: str, timeout: int) -> dict:
    """Run the endpoint tests."""
    # Import the regression harness
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
    
    endpoints = [
        ("/health", "GET", None),
        ("/api/summary", "GET", None),
        ("/api/command-center", "GET", None),
        ("/api/command-center-v2", "GET", None),
        ("/api/pipeline", "GET", None),
        ("/api/revenue", "GET", None),
        ("/api/revenue-forecasting", "GET", None),
        ("/api/action-center", "GET", None),
        ("/api/action-center?include_closed=true", "GET", None),
        ("/api/action-queue", "GET", None),
        ("/api/marketing-posts", "GET", None),
        ("/api/client-activity/timeline", "GET", None),
        ("/api/charts", "GET", None),
        ("/api/contacts", "GET", None),
    ]
    
    results = {"passed": 0, "failed": 0, "errors": []}
    
    for path, method, body in endpoints:
        url = f"{base_url}{path}"
        try:
            req = urllib.request.Request(url, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
                data = json.loads(resp.read())
                
                # Check for computing status (acceptable but noted)
                if isinstance(data, dict) and data.get("status") == "computing":
                    results["passed"] += 1
                    continue
                
                if status < 400:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append(f"{method} {path} → {status}")
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{method} {path} → {str(e)[:100]}")
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Pre-deploy regression gate")
    parser.add_argument("--base-url", default=DEFAULT_URL, help="Backend URL")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Per-endpoint timeout")
    args = parser.parse_args()
    
    print(f"╔══════════════════════════════════════════════════╗")
    print(f"║  Agency OS — Pre-Deploy Regression Gate         ║")
    print(f"╚══════════════════════════════════════════════════╝")
    print(f"\nTarget: {args.base_url}")
    print(f"Timeout: {args.timeout}s per endpoint\n")
    
    # Step 1: Health check
    print("Step 1: Health check...")
    if not check_health(args.base_url):
        print("  FAIL — Backend not responding to /health")
        print("\n  DEPLOY BLOCKED: Backend is not healthy")
        sys.exit(2)
    print("  PASS — Backend is healthy\n")
    
    # Step 2: Endpoint tests
    print("Step 2: Running endpoint tests...")
    start = time.time()
    results = run_endpoint_tests(args.base_url, args.timeout)
    duration = time.time() - start
    
    print(f"\n  Passed: {results['passed']}")
    print(f"  Failed: {results['failed']}")
    print(f"  Duration: {duration:.1f}s")
    
    if results["errors"]:
        print("\n  Errors:")
        for err in results["errors"]:
            print(f"    - {err}")
    
    # Step 3: Verdict
    print(f"\n{'='*50}")
    if results["failed"] == 0:
        print(f"  RESULT: {results['passed']}/{results['passed']} tests passed — DEPLOY APPROVED")
        sys.exit(0)
    else:
        total = results["passed"] + results["failed"]
        print(f"  RESULT: {results['passed']}/{total} tests passed — DEPLOY BLOCKED")
        sys.exit(1)

if __name__ == "__main__":
    main()
