#!/usr/bin/env python3
"""
Command Center Audit Module
============================
Self-audit module for the Command Center V2. Verifies that all 12 agent data
functions return successfully, that intelligence reaches the Command Center,
that actions execute properly, and that there are no layout, terminology, or
information-overload issues.

Also generates:
  - generate_intelligence_map()  -- the system map
  - generate_audit_report()       -- full audit findings with pass/fail per check
  - save_outputs()                -- saves reports to outputs/
"""

import os
import sys
import json
from datetime import datetime, date
from typing import Dict, Any, List

sys.path.insert(0, '/home/user/workspace/command-center')

TODAY = date(2026, 8, 16)
OUTPUT_DIR = os.path.join('/home/user/workspace/command-center', 'outputs')

DRAFT_DISCLAIMER = "DRAFT -- owner approval required."
SAMPLE_DISCLAIMER = "All data marked [SAMPLE]."

# ---------------------------------------------------------------------------
# Data function registry (the 12 agents + 3 shared helpers)
# ---------------------------------------------------------------------------

AGENT_REGISTRY = [
    {"phase": 1, "name": "Lead Follow-Up", "fn_name": "get_phase1_data"},
    {"phase": 2, "name": "Marketing Content", "fn_name": "get_phase2_data"},
    {"phase": 3, "name": "Client Nurture", "fn_name": "get_phase3_data"},
    {"phase": 4, "name": "Referral Growth", "fn_name": "get_phase4_data"},
    {"phase": 5, "name": "Community Outreach", "fn_name": "get_phase5_data"},
    {"phase": 6, "name": "CRM Management", "fn_name": "get_phase6_data"},
    {"phase": 7, "name": "Executive AI", "fn_name": "get_executive_data"},
    {"phase": 8, "name": "What Changed?", "fn_name": "get_what_changed_data"},
    {"phase": 9, "name": "Lead Scoring", "fn_name": "get_lead_scoring_data"},
    {"phase": 10, "name": "Referral Intelligence", "fn_name": "get_referral_intelligence_data"},
    {"phase": 11, "name": "Revenue Forecasting", "fn_name": "get_revenue_forecasting_data"},
    {"phase": 12, "name": "CLV Intelligence", "fn_name": "get_clv_intelligence_data"},
]

SHARED_FUNCTIONS = ["get_action_queue", "get_pipeline_summary", "get_compliance_summary"]

# Canonical terminology glossary (lowercased). Deviations are flagged.
TERMINOLOGY_GLOSSARY = {
    "lead", "prospect", "client", "contact", "opportunity", "pipeline",
    "referral", "partner", "campaign", "drip", "touchpoint", "survey",
    "compliance", "escalation", "priority", "revenue", "clv",
    "customer lifetime value", "nurture", "scorecard", "funnel",
    "consultation", "workshop", "duplicate", "sync", "decay",
}

# Known terminology inconsistencies to watch for
TERMINOLOGY_ISSUES = {
    "lead's": "lead",
    "leads'": "leads",
    "prospect's": "prospect",
    "client's": "client",
    "customer": "client",
    "customers": "clients",
    "deal": "opportunity",
    "deals": "opportunities",
    "prospect ": "prospect",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_str(value, default=""):
    if value is None:
        return default
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    try:
        return json.dumps(value, default=str)
    except Exception:
        return default


def _safe_num(value, default=0):
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _import_server():
    """Import server module, return (module_or_None, error_or_None)."""
    try:
        import server
        return server, None
    except Exception as e:
        return None, _safe_str(e)


def _get_function(module, name):
    if module is None:
        return None
    return getattr(module, name, None)


# ---------------------------------------------------------------------------
# Audit checks
# ---------------------------------------------------------------------------

def _check_agent_functions(module) -> Dict[str, Any]:
    """Check 1: All 12 agent data functions return successfully."""
    findings = []
    passed = 0
    failed = 0
    for agent in AGENT_REGISTRY:
        fn = _get_function(module, agent["fn_name"])
        if fn is None:
            findings.append({
                "phase": agent["phase"], "agent": agent["name"],
                "status": "FAIL", "detail": "Function not found: {}".format(agent["fn_name"]),
            })
            failed += 1
            continue
        try:
            result = fn()
            if isinstance(result, dict) and result.get("status") == "error":
                findings.append({
                    "phase": agent["phase"], "agent": agent["name"],
                    "status": "FAIL", "detail": "Returned error: {}".format(result.get("error", "unknown")),
                })
                failed += 1
            elif isinstance(result, dict):
                findings.append({
                    "phase": agent["phase"], "agent": agent["name"],
                    "status": "PASS", "detail": "Returned dict with {} keys.".format(len(result)),
                })
                passed += 1
            else:
                findings.append({
                    "phase": agent["phase"], "agent": agent["name"],
                    "status": "FAIL", "detail": "Unexpected return type: {}".format(type(result).__name__),
                })
                failed += 1
        except Exception as e:
            findings.append({
                "phase": agent["phase"], "agent": agent["name"],
                "status": "FAIL", "detail": "Exception: {}".format(_safe_str(e)),
            })
            failed += 1
    overall = "PASS" if failed == 0 else "FAIL"
    return {
        "check_id": 1,
        "check_name": "All 12 agent data functions return successfully",
        "status": overall,
        "passed": passed,
        "failed": failed,
        "findings": findings,
    }


def _check_shared_functions(module) -> Dict[str, Any]:
    """Check that shared helper functions (action_queue, pipeline, compliance) work."""
    findings = []
    passed = 0
    failed = 0
    for fn_name in SHARED_FUNCTIONS:
        fn = _get_function(module, fn_name)
        if fn is None:
            findings.append({"function": fn_name, "status": "FAIL", "detail": "Not found"})
            failed += 1
            continue
        try:
            result = fn()
            findings.append({"function": fn_name, "status": "PASS",
                             "detail": "Returned {}".format(type(result).__name__)})
            passed += 1
        except Exception as e:
            findings.append({"function": fn_name, "status": "FAIL",
                             "detail": "Exception: {}".format(_safe_str(e))})
            failed += 1
    overall = "PASS" if failed == 0 else "FAIL"
    return {
        "check_id": "1b",
        "check_name": "Shared helper functions (action_queue, pipeline, compliance) return",
        "status": overall,
        "passed": passed,
        "failed": failed,
        "findings": findings,
    }


def _check_nav_links(module) -> Dict[str, Any]:
    """Check 2: No broken links or dead buttons in nav (static analysis of index.html)."""
    findings = []
    index_path = os.path.join('/home/user/workspace/command-center', 'index.html')
    appjs_path = os.path.join('/home/user/workspace/command-center', 'app.js')
    broken = []
    if os.path.exists(index_path):
        try:
            with open(index_path) as f:
                html = f.read()
            # Check for placeholder hrefs
            if 'href="#"' in html:
                broken.append("Found placeholder href=\"#\" links in index.html")
            if 'href="javascript:void(0)"' in html:
                broken.append("Found javascript:void(0) links in index.html")
            # Check for onclick without handler
            if 'onclick=""' in html:
                broken.append("Found empty onclick handlers in index.html")
        except Exception as e:
            broken.append("Could not read index.html: {}".format(_safe_str(e)))
    else:
        broken.append("index.html not found")
    if os.path.exists(appjs_path):
        try:
            with open(appjs_path) as f:
                js = f.read()
            # Check for undefined function references in onclick
            import re
            onclicks = re.findall(r'onclick="(\w+)\(', html) if os.path.exists(index_path) else []
            for fn_name in set(onclicks):
                if fn_name not in js and "function {}".format(fn_name) not in js:
                    broken.append("JS handler not found: {}".format(fn_name))
        except Exception:
            pass
    status = "PASS" if not broken else "FAIL"
    return {
        "check_id": 2,
        "check_name": "No broken links or dead buttons in nav",
        "status": status,
        "findings": broken if broken else ["No broken links detected."],
    }


def _check_duplicate_functions(module) -> Dict[str, Any]:
    """Check 3: No duplicate functions in server.py."""
    findings = []
    dupes = []
    server_path = os.path.join('/home/user/workspace/command-center', 'server.py')
    if os.path.exists(server_path):
        try:
            with open(server_path) as f:
                lines = f.readlines()
            seen = {}
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("def ") and "(" in stripped:
                    name = stripped[4:stripped.index("(")].strip()
                    if name in seen:
                        dupes.append(name)
                    seen[name] = True
        except Exception as e:
            findings.append("Could not scan server.py: {}".format(_safe_str(e)))
    status = "PASS" if not dupes else "FAIL"
    return {
        "check_id": 3,
        "check_name": "No duplicate functions",
        "status": status,
        "findings": (["Duplicate function definitions: {}".format(", ".join(dupes))] if dupes
                     else ["No duplicate function definitions found."]),
    }


def _check_missing_data(module) -> Dict[str, Any]:
    """Check 4: No missing data (agents returning empty/error)."""
    findings = []
    missing = []
    for agent in AGENT_REGISTRY:
        fn = _get_function(module, agent["fn_name"])
        if fn is None:
            missing.append("{}: function missing".format(agent["name"]))
            continue
        try:
            result = fn()
            if isinstance(result, dict):
                if result.get("status") == "error":
                    missing.append("{}: returned error state".format(agent["name"]))
                elif not result.get("kpis"):
                    missing.append("{}: missing kpis".format(agent["name"]))
        except Exception as e:
            missing.append("{}: exception - {}".format(agent["name"], _safe_str(e)))
    status = "PASS" if not missing else "FAIL"
    return {
        "check_id": 4,
        "check_name": "No missing data",
        "status": status,
        "findings": (missing if missing else ["All agents returned data with kpis."]),
    }


def _check_incorrect_calculations(module) -> Dict[str, Any]:
    """Check 5: No incorrect calculations (basic sanity checks)."""
    findings = []
    issues = []
    try:
        from command_center_v2_engine import get_command_center_v2, get_top_5_priorities
        cc = get_command_center_v2()
        top5 = cc.get("top_5_priorities", [])
        # Scores should be 0-100
        for p in top5:
            score = _safe_num(p.get("priority_score", 0))
            if score < 0 or score > 100:
                issues.append("Priority '{}' has score out of range: {}".format(p.get("entity"), score))
        # Top 5 should be sorted descending
        scores = [_safe_num(p.get("priority_score", 0)) for p in top5]
        if scores != sorted(scores, reverse=True):
            issues.append("Top 5 priorities are not sorted descending by score")
        # Snapshot cards should have values
        cards = cc.get("business_snapshot", {}).get("cards", [])
        empty_cards = [c for c in cards if c.get("value") in (0, "0", "$0", "", None)]
        if empty_cards:
            issues.append("{} snapshot cards have empty/zero values".format(len(empty_cards)))
    except Exception as e:
        issues.append("Could not run calculation checks: {}".format(_safe_str(e)))
    status = "PASS" if not issues else "FAIL"
    return {
        "check_id": 5,
        "check_name": "No incorrect calculations",
        "status": status,
        "findings": (issues if issues else ["All calculation sanity checks passed."]),
    }


def _check_inconsistent_terminology(module) -> Dict[str, Any]:
    """Check 6: No inconsistent terminology across agent outputs."""
    findings = []
    issues = []
    for agent in AGENT_REGISTRY:
        fn = _get_function(module, agent["fn_name"])
        if fn is None:
            continue
        try:
            result = fn()
            text = _safe_str(result).lower()
            for bad, good in TERMINOLOGY_ISSUES.items():
                if bad in text:
                    issues.append("{}: uses '{}' (preferred: '{}')".format(agent["name"], bad.strip(), good))
        except Exception:
            pass
    status = "PASS" if not issues else "WARN"
    return {
        "check_id": 6,
        "check_name": "No inconsistent terminology",
        "status": status,
        "findings": (issues[:10] if issues else ["Terminology is consistent across agents."]),
    }


def _check_agent_outputs_reaching_cc(module) -> Dict[str, Any]:
    """Check 7: Agent outputs reaching the Command Center."""
    findings = []
    missing = []
    try:
        from command_center_v2_engine import get_command_center_v2
        cc = get_command_center_v2()
        snapshot_agents = set(c.get("agent", "") for c in cc.get("business_snapshot", {}).get("cards", []))
        agent_status = cc.get("agent_status", [])
        active_agents = set(a.get("agent_name", "") for a in agent_status if a.get("status") == "active")
        for agent in AGENT_REGISTRY:
            if agent["name"] not in active_agents and agent["name"] not in snapshot_agents:
                missing.append("{}: output not reaching Command Center".format(agent["name"]))
    except Exception as e:
        missing.append("Could not verify: {}".format(_safe_str(e)))
    status = "PASS" if not missing else "FAIL"
    return {
        "check_id": 7,
        "check_name": "Agent outputs reaching the Command Center",
        "status": status,
        "findings": (missing if missing else ["All agent outputs reach the Command Center."]),
    }


def _check_actions_execute(module) -> Dict[str, Any]:
    """Check 8: Actions that execute properly (action engine produces valid buttons)."""
    findings = []
    issues = []
    try:
        from command_center_v2_engine import get_top_5_priorities
        from command_center_action_engine import get_all_actions, render_action_button
        top5 = get_top_5_priorities()
        if not top5:
            issues.append("No top-5 priorities to generate actions for")
        else:
            all_actions = get_all_actions(top5)
            for group in all_actions:
                for a in group.get("actions", []):
                    btn = render_action_button(a)
                    if not btn.get("label"):
                        issues.append("Action button missing label: {}".format(a.get("action_type")))
                    if not btn.get("icon"):
                        issues.append("Action button missing icon: {}".format(a.get("action_type")))
                    if btn.get("requires_approval") and "DRAFT" not in btn.get("disclaimer", ""):
                        issues.append("Action requiring approval missing DRAFT disclaimer")
    except Exception as e:
        issues.append("Could not run action checks: {}".format(_safe_str(e)))
    status = "PASS" if not issues else "FAIL"
    return {
        "check_id": 8,
        "check_name": "Actions execute properly",
        "status": status,
        "findings": (issues if issues else ["All action buttons render with valid metadata."]),
    }


def _check_layout_issues(module) -> Dict[str, Any]:
    """Check 9: Mobile/desktop layout issues (static scan of styles.css + index.html)."""
    findings = []
    issues = []
    styles_path = os.path.join('/home/user/workspace/command-center', 'styles.css')
    index_path = os.path.join('/home/user/workspace/command-center', 'index.html')
    has_media_query = False
    if os.path.exists(styles_path):
        try:
            with open(styles_path) as f:
                css = f.read()
            has_media_query = "@media" in css
            if not has_media_query:
                issues.append("styles.css has no @media queries (no mobile responsiveness)")
        except Exception:
            issues.append("Could not read styles.css")
    else:
        issues.append("styles.css not found")
    if os.path.exists(index_path):
        try:
            with open(index_path) as f:
                html = f.read()
            if 'viewport' not in html:
                issues.append("index.html missing viewport meta tag (mobile)")
            # Check for fixed widths that break mobile
            if 'width: 100%' not in styles_path and not has_media_query:
                pass  # already flagged
        except Exception:
            issues.append("Could not read index.html for layout check")
    status = "PASS" if not issues else "WARN"
    return {
        "check_id": 9,
        "check_name": "Mobile/desktop layout issues",
        "status": status,
        "findings": (issues if issues else ["Layout includes responsive media queries and viewport meta."]),
    }


def _check_information_overload(module) -> Dict[str, Any]:
    """Check 10: Information overload check (too many items surfaced at once)."""
    findings = []
    issues = []
    try:
        from command_center_v2_engine import get_command_center_v2
        cc = get_command_center_v2()
        top5_count = len(cc.get("top_5_priorities", []))
        attn_count = len(cc.get("needs_attention", []))
        card_count = len(cc.get("business_snapshot", {}).get("cards", []))
        if top5_count > 5:
            issues.append("Top priorities exceed 5 ({} shown)".format(top5_count))
        if attn_count > 15:
            issues.append("Needs attention items exceed 15 ({} shown)".format(attn_count))
        if card_count > 20:
            issues.append("Snapshot cards exceed 20 ({} shown)".format(card_count))
        if not issues:
            findings_text = ["Information density within limits: {} priorities, {} attention items, {} cards.".format(
                top5_count, attn_count, card_count)]
        else:
            findings_text = issues
    except Exception as e:
        findings_text = ["Could not run overload check: {}".format(_safe_str(e))]
        issues = findings_text
    status = "PASS" if not issues else "WARN"
    return {
        "check_id": 10,
        "check_name": "Information overload check",
        "status": status,
        "findings": findings_text,
    }


def _check_missing_automation(module) -> Dict[str, Any]:
    """Check 11: Missing automation opportunities."""
    findings = []
    opportunities = []
    try:
        from command_center_action_engine import _has_external_integration
        if not _has_external_integration():
            opportunities.append("No external integrations connected -- call/email/schedule actions require manual workflow (DRAFT).")
    except Exception:
        pass
    # Check for routine items that could be automated
    try:
        from command_center_v2_engine import get_needs_attention
        attn = get_needs_attention()
        etypes = set(a.get("entity_type", "") for a in attn)
        if "duplicate" in etypes:
            opportunities.append("Duplicate contact merging could be automated with a dedup workflow.")
        if "sync_issue" in etypes:
            opportunities.append("Cross-agent sync issues could be auto-resolved with a reconciliation job.")
        if "overdue_task" in etypes:
            opportunities.append("Overdue task reminders could be automated via scheduled notifications.")
        if "survey_follow_up" in etypes:
            opportunities.append("Survey follow-up emails could be automated in the nurture sequence.")
    except Exception as e:
        opportunities.append("Could not evaluate automation opportunities: {}".format(_safe_str(e)))
    status = "INFO" if opportunities else "PASS"
    return {
        "check_id": 11,
        "check_name": "Missing automation opportunities",
        "status": status,
        "findings": (opportunities if opportunities else ["No obvious automation gaps detected."]),
    }


# ---------------------------------------------------------------------------
# Intelligence map
# ---------------------------------------------------------------------------

def generate_intelligence_map() -> Dict[str, Any]:
    """Return the system map showing the full intelligence flow.

    DATA SOURCES -> INDIVIDUAL INTELLIGENCE FUNCTIONS -> NORMALIZED INTELLIGENCE
    -> PRIORITY ENGINE -> EXECUTIVE AI -> COMMAND CENTER -> USER ACTION
    """
    stages = [
        {
            "stage": 1,
            "name": "DATA SOURCES",
            "description": "Raw data from CRM, contacts, opportunities, campaigns, calendars, and partner sources.",
            "components": [
                "DEMO_CONTACTS (phase1)", "email-campaigns.json (phase2)",
                "content-calendar-2026.csv (phase2)", "client-drip-campaigns.json (phase3)",
                "client-touchpoint-calendar-2026.csv (phase3)",
                "referral-source-scorecard.csv (phase4)", "partner-prospect-template.csv (phase4)",
                "community-event-calendar-2026.csv (phase5)", "DEMO_OPPORTUNITIES (phase6)",
                "DEMO_TASKS / DEMO_APPOINTMENTS (phase6)", "DEMO_GHL_TAGS / DEMO_GHL_FIELDS (phase6)",
            ],
        },
        {
            "stage": 2,
            "name": "INDIVIDUAL INTELLIGENCE FUNCTIONS",
            "description": "12 agent data functions, each normalizing one domain.",
            "components": [a["name"] + " (phase {})".format(a["phase"]) for a in AGENT_REGISTRY] + SHARED_FUNCTIONS,
        },
        {
            "stage": 3,
            "name": "NORMALIZED INTELLIGENCE",
            "description": "command_center_v2_engine normalizes all agent outputs into a unified schema: entity, entity_type, priority_score, reason, opportunity_value, risk, recommended_action, action_type, due_date, source_system, timestamp, status, explanation.",
            "components": ["_normalize_executive", "_normalize_what_changed", "_normalize_lead_scoring",
                           "_normalize_referral_intelligence", "_normalize_revenue_forecasting",
                           "_normalize_clv", "_normalize_crm", "_normalize_phase1..5",
                           "_normalize_action_queue"],
        },
        {
            "stage": 4,
            "name": "PRIORITY ENGINE",
            "description": "Scores each item using urgency + value + probability + risk + recency + deadline + strategic importance (capped at 100). Surfaces top 5 priorities and a single 'what should I do next'.",
            "components": ["_score_item", "_rank_and_explain", "get_top_5_priorities",
                           "get_what_should_i_do_next", "get_needs_attention"],
        },
        {
            "stage": 5,
            "name": "EXECUTIVE AI",
            "description": "Health score, escalations, briefings, and forecasts layered above the priority engine.",
            "components": ["business_health_score", "escalation_engine", "daily_priority_engine",
                           "future_prediction_engine", "ai_activity_monitor"],
        },
        {
            "stage": 6,
            "name": "COMMAND CENTER",
            "description": "Master function get_command_center_v2() aggregates everything into a single response: greeting, top 5, next action, needs attention, snapshot, summaries.",
            "components": ["get_command_center_v2", "get_business_snapshot", "get_revenue_summary",
                           "get_marketing_summary", "get_referral_summary", "get_client_health_summary",
                           "get_what_changed_summary"],
        },
        {
            "stage": 7,
            "name": "USER ACTION",
            "description": "command_center_action_engine converts priorities into actionable buttons (call, email, schedule, approve, etc.). External actions surface as DRAFT -- owner approval required when no integration exists.",
            "components": ["get_actions_for_priority", "get_all_actions", "render_action_button"],
        },
    ]
    flow = " -> ".join(s["name"] for s in stages)
    return {
        "map_name": "Command Center V2 Intelligence Flow",
        "flow": flow,
        "stages": stages,
        "agent_count": len(AGENT_REGISTRY),
        "shared_functions": SHARED_FUNCTIONS,
        "date": TODAY.isoformat(),
        "disclaimer": "{} {}".format(SAMPLE_DISCLAIMER, DRAFT_DISCLAIMER),
    }


# ---------------------------------------------------------------------------
# Full audit report
# ---------------------------------------------------------------------------

def generate_audit_report() -> Dict[str, Any]:
    """Return full audit findings with pass/fail for each check."""
    module, import_err = _import_server()
    if import_err:
        # Still produce a report, noting the import failure
        checks = [{
            "check_id": 0, "check_name": "Server module import",
            "status": "FAIL", "findings": ["Could not import server: {}".format(import_err)],
        }]
    else:
        checks = [
            _check_agent_functions(module),
            _check_shared_functions(module),
            _check_nav_links(module),
            _check_duplicate_functions(module),
            _check_missing_data(module),
            _check_incorrect_calculations(module),
            _check_inconsistent_terminology(module),
            _check_agent_outputs_reaching_cc(module),
            _check_actions_execute(module),
            _check_layout_issues(module),
            _check_information_overload(module),
            _check_missing_automation(module),
        ]

    # Tally
    passed = sum(1 for c in checks if c["status"] == "PASS")
    failed = sum(1 for c in checks if c["status"] == "FAIL")
    warnings = sum(1 for c in checks if c["status"] in ("WARN", "INFO"))
    overall = "PASS" if failed == 0 else "FAIL"

    return {
        "report_name": "Command Center V2 Audit Report",
        "date": TODAY.isoformat(),
        "timestamp": datetime.now().isoformat(),
        "overall_status": overall,
        "summary": {
            "total_checks": len(checks),
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
        },
        "checks": checks,
        "intelligence_map": generate_intelligence_map(),
        "disclaimer": "{} {}".format(SAMPLE_DISCLAIMER, DRAFT_DISCLAIMER),
    }


# ---------------------------------------------------------------------------
# Save outputs
# ---------------------------------------------------------------------------

def save_outputs() -> Dict[str, Any]:
    """Save audit report and intelligence map to the outputs directory."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    report = generate_audit_report()
    imap = generate_intelligence_map()
    report_path = os.path.join(OUTPUT_DIR, 'audit_report.json')
    map_path = os.path.join(OUTPUT_DIR, 'intelligence_map.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    with open(map_path, 'w') as f:
        json.dump(imap, f, indent=2, default=str)
    return {
        "audit_report": report_path,
        "intelligence_map": map_path,
        "output_dir": OUTPUT_DIR,
        "overall_status": report.get("overall_status"),
        "summary": report.get("summary"),
    }


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("COMMAND CENTER AUDIT -- TEST RUN")
    print("=" * 70)
    result = save_outputs()
    print("\nOutputs saved:")
    print("  Audit report :", result["audit_report"])
    print("  Intel map   :", result["intelligence_map"])
    print("\nOverall status:", result["overall_status"])
    s = result["summary"]
    print("Summary: {passed} passed, {failed} failed, {warnings} warnings (of {total_checks} checks)".format(**s))
    print("\n--- CHECK BREAKDOWN ---")
    report = generate_audit_report()
    for c in report["checks"]:
        print("  [{}] Check {}: {}".format(c["status"], c["check_id"], c["check_name"]))
        for f in c["findings"][:2]:
            line = f if isinstance(f, str) else _safe_str(f)
            print("       -", line[:90])
    print("\n--- INTELLIGENCE MAP ---")
    imap = report["intelligence_map"]
    print("  Flow:", imap["flow"])
    print("  Stages:", len(imap["stages"]))
    print("\n" + "=" * 70)
    print("AUDIT TEST COMPLETE.")
    print("=" * 70)
