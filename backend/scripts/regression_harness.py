#!/usr/bin/env python3
"""
Regression Test Harness for Agency OS Command Center.

Validates every API endpoint against expected response shapes.
Supports baseline snapshot saving and comparison.

Usage:
  # Save baseline from live site
  python3 backend/scripts/regression_harness.py --base-url https://mission-control-app.pplx.app/port/5000 --save-baseline

  # Run validation only (no baseline comparison)
  python3 backend/scripts/regression_harness.py --base-url http://127.0.0.1:8088

  # Compare against saved baseline
  python3 backend/scripts/regression_harness.py --base-url http://127.0.0.1:8088 --compare-baseline

  # Run only specific group
  python3 backend/scripts/regression_harness.py --base-url http://127.0.0.1:8088 --group core

  # Publish-safe run: save baseline from live, then compare local against it
  python3 backend/scripts/regression_harness.py --base-url https://mission-control-app.pplx.app/port/5000 --save-baseline
  python3 backend/scripts/regression_harness.py --base-url http://127.0.0.1:8088 --compare-baseline

Exit codes:
  0 = all endpoints pass
  1 = one or more endpoints failed
  2 = harness error (couldn't run)
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Endpoint specifications
# ---------------------------------------------------------------------------

# Fields to normalize when comparing baselines (volatile, non-deterministic)
VOLATILE_FIELDS = {
    "scan_date", "last_synced_at", "connected_at", "created_at", "updated_at",
    "timestamp", "generated_at", "date", "today", "last_query_datetime",
    "token_expires_at", "expires_in",
}

# Fields whose values may legitimately change between runs (counts, etc.)
VOLATILE_NUMERIC = {
    "action_count", "agents_online", "count", "total",
}

# Fields that indicate OAuth status depends on credentials (not a failure)
OAUTH_FIELDS = {
    "configured", "connected", "email", "provider",
}


def _spec(
    name: str,
    path: str,
    group: str,
    expected_status: int = 200,
    required_keys: Optional[List[str]] = None,
    key_types: Optional[Dict[str, type]] = None,
    method: str = "GET",
    description: str = "",
) -> Dict[str, Any]:
    """Create an endpoint spec."""
    return {
        "name": name,
        "path": path,
        "group": group,
        "method": method,
        "expected_status": expected_status,
        "required_keys": required_keys or [],
        "key_types": key_types or {},
        "description": description,
    }


ENDPOINTS: List[Dict[str, Any]] = [
    # ── Core ──────────────────────────────────────────────────────────────
    _spec("summary", "/api/summary", "core",
          required_keys=["kpis", "data_source", "status"],
          key_types={"kpis": dict, "data_source": str, "status": str},
          description="Home dashboard KPIs"),
    _spec("command-center", "/api/command-center", "core",
          required_keys=["scan_date", "agents"],
          key_types={"agents": list},
          description="Command center aggregated data"),
    _spec("action-center", "/api/action-center", "core",
          description="Action center items"),
    _spec("action-queue", "/api/action-queue", "core",
          description="Legacy action queue items"),
    _spec("charts", "/api/charts", "core",
          description="Pre-computed chart data"),
    _spec("pipeline", "/api/pipeline", "core",
          description="Pipeline summary"),
    _spec("compliance", "/api/compliance", "core",
          description="Compliance check"),
    _spec("command-center-v2", "/api/command-center-v2", "core",
          description="Command Center V2 data"),
    _spec("demo-state", "/api/demo/state", "core",
          description="Demo mode state"),
    _spec("import-schemas", "/api/import/schemas", "core",
          description="Available import schemas"),

    # ── Data ──────────────────────────────────────────────────────────────
    _spec("communications", "/api/communications", "data",
          description="Communications log (calls, texts, emails)"),
    _spec("calendar-events", "/api/calendar/events", "data",
          description="Calendar events"),
    _spec("calendar-connections", "/api/calendar/connections", "data",
          expected_status=200,
          description="Calendar OAuth connection status"),
    _spec("client-activity-timeline", "/api/client-activity/timeline", "data",
          description="Client activity timeline"),
    _spec("revenue", "/api/revenue", "data",
          description="Revenue records"),
    _spec("revenue-forecasting", "/api/revenue-forecasting", "data",
          description="Revenue forecasting data"),
    _spec("revenue-gap-recovery", "/api/revenue-gap-recovery", "data",
          description="Revenue gap recovery analysis"),
    _spec("lead-sources", "/api/lead-sources", "data",
          description="Lead sources list"),
    _spec("referral-sources", "/api/referral-sources", "data",
          description="Referral sources list"),

    # ── Agents (Phase 1-12 via /api/agent/{phase}) ─────────────────────────
    _spec("agent-1", "/api/agent/1", "agents",
          required_keys=["agent_name", "status"],
          key_types={"agent_name": str, "status": str},
          description="Lead Follow-Up Agent"),
    _spec("agent-2", "/api/agent/2", "agents",
          required_keys=["agent_name", "status"],
          key_types={"agent_name": str, "status": str},
          description="Marketing Agent"),
    _spec("agent-3", "/api/agent/3", "agents",
          required_keys=["agent_name", "status"],
          key_types={"agent_name": str, "status": str},
          description="Client Nurture Agent"),
    _spec("agent-4", "/api/agent/4", "agents",
          required_keys=["agent_name", "status"],
          key_types={"agent_name": str, "status": str},
          description="Referral Growth Agent"),
    _spec("agent-5", "/api/agent/5", "agents",
          required_keys=["agent_name", "status"],
          key_types={"agent_name": str, "status": str},
          description="Community Agent"),
    _spec("agent-6", "/api/agent/6", "agents",
          required_keys=["agent_name", "status"],
          key_types={"agent_name": str, "status": str},
          description="CRM Management Agent"),
    _spec("agent-7", "/api/agent/7", "agents",
          required_keys=["agent_name", "status"],
          key_types={"agent_name": str, "status": str},
          description="Executive AI Agent"),
    _spec("agent-8", "/api/agent/8", "agents",
          required_keys=["agent_name", "status"],
          key_types={"agent_name": str, "status": str},
          description="Business Strategy Agent"),
    _spec("agent-9", "/api/agent/9", "agents",
          required_keys=["agent_name", "status"],
          key_types={"agent_name": str, "status": str},
          description="Lead Scoring Agent"),
    _spec("agent-10", "/api/agent/10", "agents",
          required_keys=["agent_name", "status"],
          key_types={"agent_name": str, "status": str},
          description="Revenue Forecasting Agent"),
    _spec("agent-11", "/api/agent/11", "agents",
          required_keys=["agent_name", "status"],
          key_types={"agent_name": str, "status": str},
          description="Revenue Forecasting Engine"),
    _spec("agent-12", "/api/agent/12", "agents",
          required_keys=["agent_name", "status"],
          key_types={"agent_name": str, "status": str},
          description="CLV Intelligence Agent"),

    # ── Intelligence / Scorecard ──────────────────────────────────────────
    _spec("scorecard", "/api/scorecard", "intelligence",
          description="Business scorecard"),
    _spec("scorecard-trends", "/api/scorecard/trends", "intelligence",
          description="Scorecard trend data"),
    _spec("v2-priority-engine", "/api/v2/priority-engine", "intelligence",
          description="V2 priority engine data"),
    _spec("v2-next-action", "/api/v2/next-action", "intelligence",
          description="V2 next best action"),
    _spec("v2-needs-attention", "/api/v2/needs-attention", "intelligence",
          description="V2 items needing attention"),
    _spec("v2-intelligence-map", "/api/v2/intelligence-map", "intelligence",
          description="V2 intelligence map"),
    _spec("v2-action-center", "/api/v2/action-center", "intelligence",
          description="V2 action center data"),
    _spec("v2-action-summary", "/api/v2/action-summary", "intelligence",
          description="V2 action summary"),
    _spec("v2-actions-smart", "/api/v2/actions/smart?entity_type=client", "intelligence",
          description="V2 smart actions"),

    # ── Marketing ──────────────────────────────────────────────────────────
    _spec("marketing-posts", "/api/marketing-posts", "marketing",
          description="Marketing post suggestions"),
    _spec("marketing-posts-config", "/api/marketing-posts/config", "marketing",
          description="Marketing posts configuration"),

    # ── Training ───────────────────────────────────────────────────────────
    _spec("training", "/api/training", "training",
          required_keys=["status", "modules"],
          key_types={"status": str, "modules": list},
          description="Training mode modules and simulations"),
    _spec("training-health", "/api/training/health", "training",
          description="Training mode health check"),
    _spec("training-certificate", "/api/training/certificate", "training",
          description="Training certificate status"),
]


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize_value(val: Any, depth: int = 0) -> Any:
    """Normalize a value for baseline comparison — strip volatile fields."""
    if depth > 10:
        return "<truncated>"
    if isinstance(val, dict):
        return {
            k: normalize_value(v, depth + 1)
            for k, v in val.items()
            if k not in VOLATILE_FIELDS
        }
    if isinstance(val, list):
        if len(val) > 20:
            return [normalize_value(val[0], depth + 1), f"... ({len(val)} items)"]
        return [normalize_value(v, depth + 1) for v in val]
    if isinstance(val, float):
        return round(val, 2)  # Normalize float precision
    return val


def normalize_response(data: Any) -> Any:
    """Normalize full response for baseline comparison."""
    return normalize_value(data)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def fetch_endpoint(base_url: str, path: str, method: str = "GET",
                   timeout: int = 30, headers: Optional[Dict] = None) -> Tuple[int, Any, float]:
    """Fetch an endpoint. Returns (status_code, json_or_none, elapsed_ms)."""
    url = base_url.rstrip("/") + path
    req = urllib.request.Request(url, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    req.add_header("User-Agent", "regression-harness/1.0")

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            elapsed = (time.time() - start) * 1000
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return resp.status, {"_raw_body": body[:500]}, elapsed
            return resp.status, data, elapsed
    except urllib.error.HTTPError as e:
        elapsed = (time.time() - start) * 1000
        body = e.read().decode("utf-8", errors="replace")[:500]
        try:
            data = json.loads(body)
        except Exception:
            data = {"_error_body": body}
        return e.code, data, elapsed
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return -1, {"_exception": str(e)}, elapsed


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_response(spec: Dict[str, Any], status: int, data: Any) -> List[str]:
    """Validate a response against its spec. Returns list of error messages."""
    errors = []

    # Status code check
    if status != spec["expected_status"]:
        errors.append(f"status {status} != expected {spec['expected_status']}")

    # If we got an error response, note it
    if isinstance(data, dict) and data.get("status") == "error":
        # Error responses are acceptable if status is 200 (graceful degradation)
        if status == 200 and "error" in data:
            # Check if it's a "not enough data" message (acceptable)
            err_msg = str(data.get("error", ""))
            if "not enough data" in err_msg.lower() or "no data" in err_msg.lower():
                pass  # graceful degradation, not a failure
            else:
                errors.append(f"error response: {err_msg[:100]}")

    # Required keys check (only if we got a dict and expected 200)
    if status == 200 and isinstance(data, dict) and spec["required_keys"]:
        for key in spec["required_keys"]:
            if key not in data:
                errors.append(f"missing required key: {key}")

    # Key type checks
    if status == 200 and isinstance(data, dict):
        for key, expected_type in spec.get("key_types", {}).items():
            if key in data:
                val = data[key]
                if expected_type == dict and not isinstance(val, dict):
                    errors.append(f"key '{key}' expected dict, got {type(val).__name__}")
                elif expected_type == list and not isinstance(val, list):
                    errors.append(f"key '{key}' expected list, got {type(val).__name__}")
                elif expected_type == str and not isinstance(val, str):
                    errors.append(f"key '{key}' expected str, got {type(val).__name__}")
                elif expected_type == int and not isinstance(val, (int, float)):
                    errors.append(f"key '{key}' expected int, got {type(val).__name__}")

    return errors


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

def run_harness(
    base_url: str,
    endpoints: List[Dict[str, Any]],
    timeout: int = 30,
    admin_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Run the harness against all endpoints. Returns results list."""
    results = []
    headers = {}
    if admin_key:
        headers["X-Admin-Key"] = admin_key

    for spec in endpoints:
        name = spec["name"]
        path = spec["path"]
        group = spec["group"]

        status, data, elapsed = fetch_endpoint(
            base_url, path, spec["method"], timeout, headers
        )

        errors = validate_response(spec, status, data)
        normalized = normalize_response(data) if status == 200 else None

        result = {
            "name": name,
            "group": group,
            "path": path,
            "status": status,
            "expected_status": spec["expected_status"],
            "elapsed_ms": round(elapsed, 0),
            "errors": errors,
            "passed": len(errors) == 0,
            "response_shape": _get_shape(data) if status == 200 else None,
            "normalized": normalized,
        }
        results.append(result)

        # Print live result
        status_str = "PASS" if result["passed"] else "FAIL"
        status_code = status if status > 0 else "ERR"
        print(f"  {status_str:4} {name:25} {status_code}  {elapsed:6.0f}ms  {spec['description']}")

        if errors:
            for err in errors:
                print(f"         → {err}")

    return results


def _get_shape(data: Any, depth: int = 0) -> Any:
    """Get a structural shape of the response (keys only, no values)."""
    if depth > 5:
        return "..."
    if isinstance(data, dict):
        return {k: _get_shape(v, depth + 1) for k, v in list(data.items())[:20]}
    if isinstance(data, list):
        if not data:
            return []
        return [_get_shape(data[0], depth + 1)]
    return type(data).__name__


def compare_to_baseline(results: List[Dict], baseline: List[Dict]) -> List[str]:
    """Compare current results to baseline. Returns list of diffs."""
    diffs = []
    baseline_map = {r["name"]: r for r in baseline}
    current_map = {r["name"]: r for r in results}

    all_names = sorted(set(list(baseline_map.keys()) + list(current_map.keys())))

    for name in all_names:
        if name not in current_map:
            diffs.append(f"MISSING: {name} (was in baseline, not in current run)")
            continue
        if name not in baseline_map:
            diffs.append(f"NEW: {name} (not in baseline, new endpoint)")
            continue

        old = baseline_map[name]
        new = current_map[name]

        # Status change
        if old["status"] != new["status"]:
            diffs.append(f"STATUS CHANGE: {name} {old['status']} → {new['status']}")

        # Pass/fail change
        if old["passed"] != new["passed"]:
            diffs.append(
                f"REGRESSION: {name} was {'PASS' if old['passed'] else 'FAIL'}, "
                f"now {'PASS' if new['passed'] else 'FAIL'}"
            )

        # Response shape change
        if old.get("response_shape") != new.get("response_shape"):
            old_shape = json.dumps(old.get("response_shape"), sort_keys=True)
            new_shape = json.dumps(new.get("response_shape"), sort_keys=True)
            if old_shape != new_shape:
                diffs.append(f"SHAPE CHANGE: {name} response structure changed")

    return diffs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Regression test harness for Agency OS Command Center"
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8088",
        help="Base URL for the API (default: http://127.0.0.1:8088)",
    )
    parser.add_argument(
        "--baseline",
        default="backend/test_baselines/regression_baseline.json",
        help="Path to baseline file (default: backend/test_baselines/regression_baseline.json)",
    )
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="Save current results as the new baseline",
    )
    parser.add_argument(
        "--compare-baseline",
        action="store_true",
        help="Compare current results against saved baseline",
    )
    parser.add_argument(
        "--group",
        choices=["core", "data", "agents", "intelligence", "training", "all"],
        default="all",
        help="Only run endpoints in this group",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--admin-key",
        default=os.environ.get("ADMIN_API_KEY", ""),
        help="Admin API key for admin endpoints (default: $ADMIN_API_KEY)",
    )
    parser.add_argument(
        "--output-dir",
        default="backend/test_reports",
        help="Directory for test report files",
    )

    args = parser.parse_args()

    # Filter endpoints by group
    if args.group == "all":
        endpoints = ENDPOINTS
    else:
        endpoints = [e for e in ENDPOINTS if e["group"] == args.group]

    print(f"\n{'='*70}")
    print(f"  Agency OS Regression Harness")
    print(f"  Base URL:  {args.base_url}")
    print(f"  Endpoints: {len(endpoints)} ({args.group})")
    print(f"  Mode:      {'save-baseline' if args.save_baseline else 'compare-baseline' if args.compare_baseline else 'validate-only'}")
    print(f"{'='*70}\n")

    # Run the harness
    results = run_harness(args.base_url, endpoints, args.timeout, args.admin_key)

    # Summary
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    total = len(results)

    print(f"\n{'='*70}")
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    if failed:
        print(f"\n  FAILED ENDPOINTS:")
        for r in results:
            if not r["passed"]:
                print(f"    ✗ {r['name']:25} {r['status']}  {', '.join(r['errors'])}")
    print(f"{'='*70}\n")

    # Save report
    report_dir = os.path.join(os.getcwd(), args.output_dir)
    os.makedirs(report_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(report_dir, f"regression_{timestamp}.json")
    report = {
        "timestamp": timestamp,
        "base_url": args.base_url,
        "group": args.group,
        "total": total,
        "passed": passed,
        "failed": failed,
        "results": [
            {k: v for k, v in r.items() if k != "normalized"}
            for r in results
        ],
    }

    # Baseline comparison
    if args.compare_baseline:
        baseline_path = os.path.join(os.getcwd(), args.baseline)
        if not os.path.exists(baseline_path):
            print(f"  ⚠ Baseline not found at {baseline_path}, skipping comparison")
        else:
            with open(baseline_path) as f:
                baseline = json.load(f)
            diffs = compare_to_baseline(results, baseline.get("results", []))
            report["baseline_diffs"] = diffs
            if diffs:
                print(f"  BASELINE COMPARISON: {len(diffs)} differences found\n")
                for d in diffs:
                    print(f"    → {d}")
                print()
            else:
                print(f"  BASELINE COMPARISON: no differences detected\n")

    # Save baseline
    if args.save_baseline:
        baseline_dir = os.path.dirname(os.path.join(os.getcwd(), args.baseline))
        if baseline_dir:
            os.makedirs(baseline_dir, exist_ok=True)
        baseline_path = os.path.join(os.getcwd(), args.baseline)
        baseline_data = {
            "timestamp": timestamp,
            "base_url": args.base_url,
            "results": [
                {
                    "name": r["name"],
                    "group": r["group"],
                    "path": r["path"],
                    "status": r["status"],
                    "expected_status": r["expected_status"],
                    "passed": r["passed"],
                    "errors": r["errors"],
                    "response_shape": r["response_shape"],
                    "normalized": r["normalized"],
                }
                for r in results
            ],
        }
        with open(baseline_path, "w") as f:
            json.dump(baseline_data, f, indent=2, default=str)
        print(f"  Baseline saved to {baseline_path}\n")

    # Save report
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"  Report saved to {report_path}")

    # Exit code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
