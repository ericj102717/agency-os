#!/usr/bin/env python3
"""
Command Center V2 Engine
========================
Priority engine that normalizes intelligence from all 12 AI agents into a
unified priority list. Sits above the existing server.py data functions and
produces a single "what should I do next" view for the agency owner.

All data is SAMPLE. All recommendations are DRAFT -- owner approval required.
"""

import os
import sys
import json
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional

# Ensure the command-center directory (and phase dirs) are importable
sys.path.insert(0, '/home/user/workspace/command-center')
# server.py itself adds phase1..phase6 to sys.path; importing it triggers that.
try:
    import server as _server  # noqa: F401  (import for side effects + functions)
    from server import (
        get_phase1_data, get_phase2_data, get_phase3_data,
        get_phase4_data, get_phase5_data, get_phase6_data,
        get_executive_data, get_what_changed_data,
        get_lead_scoring_data, get_referral_intelligence_data,
        get_revenue_forecasting_data, get_clv_intelligence_data,
        get_action_queue, get_pipeline_summary, get_compliance_summary,
    )
except Exception as _import_err:  # pragma: no cover - fallback shim
    _SERVER_IMPORT_ERROR = _import_err
    get_phase1_data = get_phase2_data = get_phase3_data = lambda: {"status": "error", "error": "server import failed"}
    get_phase4_data = get_phase5_data = get_phase6_data = lambda: {"status": "error", "error": "server import failed"}
    get_executive_data = get_what_changed_data = lambda: {"status": "error", "error": "server import failed"}
    get_lead_scoring_data = get_referral_intelligence_data = lambda: {"status": "error", "error": "server import failed"}
    get_revenue_forecasting_data = get_clv_intelligence_data = lambda: {"status": "error", "error": "server import failed"}
    get_action_queue = lambda: []
    get_pipeline_summary = lambda: {}
    get_compliance_summary = lambda: {}
else:
    _SERVER_IMPORT_ERROR = None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TODAY = date.today()  # Dynamic, not frozen
SAMPLE_DISCLAIMER = "All data marked [SAMPLE]."
DRAFT_DISCLAIMER = "DRAFT -- owner approval required."

AGENT_LABELS = {
    1: "Lead Follow-Up",
    2: "Marketing Content",
    3: "Client Nurture",
    4: "Referral Growth",
    5: "Community Outreach",
    6: "CRM Management",
    7: "Executive AI",
    8: "What Changed?",
    9: "Lead Scoring",
    10: "Referral Intelligence",
    11: "Revenue Forecasting",
    12: "CLV Intelligence",
}

# ---------------------------------------------------------------------------
# Sanitization helpers
# ---------------------------------------------------------------------------

def safe_num(value, default=0):
    """Convert value to int or float, falling back to default."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    try:
        if isinstance(value, str):
            v = value.strip().replace("$", "").replace(",", "").replace("%", "")
            if v == "":
                return default
            if "." in v:
                return float(v)
            return int(v)
    except (ValueError, TypeError):
        pass
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_str(value, default=""):
    """Convert value to a clean string."""
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


def safe_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    if value is None:
        return []
    return [value]


def safe_dict(value):
    if isinstance(value, dict):
        return value
    return {}


def sanitize(obj):
    """Recursively convert nested objects into primitive types."""
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float)):
        return obj
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return {safe_str(k): sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [sanitize(v) for v in obj]
    # datetime / date objects
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    # fall back to string
    return safe_str(obj)


# ---------------------------------------------------------------------------
# Time-based greeting
# ---------------------------------------------------------------------------

def get_greeting(now: Optional[datetime] = None) -> str:
    """Return 'Good morning/afternoon/evening' based on current hour."""
    if now is None:
        now = datetime.now()
    hour = now.hour
    if hour < 12:
        return "Good morning"
    if hour < 18:
        return "Good afternoon"
    return "Good evening"


# ---------------------------------------------------------------------------
# Data collection -- call all 12 agent functions safely
# ---------------------------------------------------------------------------

def _collect_all_agent_data() -> Dict[str, Any]:
    """Call every agent data function and return a dict keyed by phase number."""
    fetchers = {
        1: get_phase1_data,
        2: get_phase2_data,
        3: get_phase3_data,
        4: get_phase4_data,
        5: get_phase5_data,
        6: get_phase6_data,
        7: get_executive_data,
        8: get_what_changed_data,
        9: get_lead_scoring_data,
        10: get_referral_intelligence_data,
        11: get_revenue_forecasting_data,
        12: get_clv_intelligence_data,
    }
    out = {}
    for phase, fn in fetchers.items():
        try:
            out[phase] = fn() or {}
        except Exception as e:
            out[phase] = {"agent_name": AGENT_LABELS.get(phase, f"Phase {phase}"),
                          "phase": phase, "status": "error", "error": safe_str(e)}
    return out


# ---------------------------------------------------------------------------
# Unified intelligence item schema
# ---------------------------------------------------------------------------

def _new_item(entity, entity_type, source_system, reason, **extra):
    """Create a normalized intelligence item dict."""
    item = {
        "entity": safe_str(entity),
        "entity_type": safe_str(entity_type),
        "priority_score": 0,
        "reason": safe_str(reason),
        "opportunity_value": 0.0,
        "risk": "low",
        "recommended_action": "",
        "action_type": "view",
        "due_date": None,
        "source_system": safe_str(source_system),
        "timestamp": datetime.now().isoformat(),
        "status": "open",
        "explanation": "",
        "contributing_factors": {},
    }
    item.update(extra)
    return item


# ---------------------------------------------------------------------------
# Normalizers -- one per agent, returns list of normalized items
# ---------------------------------------------------------------------------

def _normalize_executive(data) -> List[Dict[str, Any]]:
    items = []
    kpis = safe_dict(data.get("kpis"))
    for prio in safe_list(data.get("priorities")):
        p = safe_dict(prio)
        items.append(_new_item(
            entity=p.get("title", p.get("priority", "Executive Priority")),
            entity_type="executive_priority",
            source_system="Executive AI",
            reason=p.get("reason", p.get("description", "Flagged by Executive AI")),
            opportunity_value=safe_num(p.get("value", p.get("impact_value", 0))),
            risk=safe_str(p.get("severity", p.get("risk", "medium")), "medium"),
            recommended_action=safe_str(p.get("recommended_action", p.get("action", ""))),
            action_type="take_action",
            status="open",
        ))
    # Escalations
    for esc in safe_list(data.get("escalations")):
        e = safe_dict(esc)
        items.append(_new_item(
            entity=e.get("title", e.get("escalation", "Escalation")),
            entity_type="escalation",
            source_system="Executive AI",
            reason=e.get("reason", e.get("description", "Escalated item")),
            risk=safe_str(e.get("severity", "high"), "high"),
            recommended_action=safe_str(e.get("recommended_action", e.get("action", ""))),
            action_type="take_action",
        ))
    return items


def _normalize_what_changed(data) -> List[Dict[str, Any]]:
    items = []
    for change in safe_list(data.get("top_5_changes")):
        c = safe_dict(change)
        sev = safe_str(c.get("severity", "informational"), "informational")
        risk = "high" if sev == "critical" else "medium" if sev == "important" else "low"
        items.append(_new_item(
            entity=c.get("title", c.get("change", "Detected change")),
            entity_type="change",
            source_system="What Changed?",
            reason=c.get("description", c.get("summary", "Detected change")),
            risk=risk,
            recommended_action=safe_str(c.get("recommended_action", c.get("action", "Review change"))),
            action_type="view_details",
        ))
    # Missed opportunities
    mo = safe_dict(data.get("missed_opportunities"))
    for opp in safe_list(mo.get("opportunities", mo.get("missed_opportunities", []))):
        o = safe_dict(opp)
        items.append(_new_item(
            entity=o.get("title", o.get("opportunity", "Missed opportunity")),
            entity_type="missed_opportunity",
            source_system="What Changed?",
            reason=o.get("description", o.get("reason", "Missed opportunity detected")),
            opportunity_value=safe_num(o.get("estimated_value", o.get("value", 0))),
            risk="medium",
            recommended_action=safe_str(o.get("recommended_action", "Pursue opportunity")),
            action_type="take_action",
        ))
    return items


def _normalize_lead_scoring(data) -> List[Dict[str, Any]]:
    items = []
    for opp in safe_list(data.get("top_10_opportunities")):
        o = safe_dict(opp)
        score = safe_num(o.get("score", o.get("priority_score", o.get("rank_score", 0))))
        items.append(_new_item(
            entity=o.get("name", o.get("contact_name", o.get("lead_name", "Lead"))),
            entity_type="lead",
            source_system="Lead Scoring",
            reason=o.get("reason", o.get("recommendation", "High-value lead")),
            opportunity_value=safe_num(o.get("estimated_value", o.get("potential_value", o.get("value", 0)))),
            risk="low",
            recommended_action=safe_str(o.get("recommended_action", o.get("next_action", "Contact lead"))),
            action_type="call",
            status="open",
        ))
    # Decay alerts -> needs attention
    for alert in safe_list(data.get("decay_alerts")):
        a = safe_dict(alert)
        items.append(_new_item(
            entity=a.get("contact_name", a.get("lead_name", "Decaying lead")),
            entity_type="decaying_lead",
            source_system="Lead Scoring",
            reason=a.get("reason", a.get("description", "Lead decaying")),
            risk="medium",
            recommended_action=safe_str(a.get("recommended_action", a.get("action", "Re-engage lead"))),
            action_type="follow_up",
        ))
    return items


def _normalize_referral_intelligence(data) -> List[Dict[str, Any]]:
    items = []
    for opp in safe_list(data.get("top_opportunities")):
        o = safe_dict(opp)
        items.append(_new_item(
            entity=o.get("name", o.get("source_name", o.get("referral_source", "Referral opportunity"))),
            entity_type="referral_opportunity",
            source_system="Referral Intelligence",
            reason=o.get("reason", o.get("description", "Referral opportunity")),
            opportunity_value=safe_num(o.get("estimated_value", o.get("potential_value", o.get("value", 0)))),
            risk="low",
            recommended_action=safe_str(o.get("recommended_action", o.get("action", "Engage referral source"))),
            action_type="email",
            status="open",
        ))
    return items


def _normalize_revenue_forecasting(data) -> List[Dict[str, Any]]:
    items = []
    kpis = safe_dict(data.get("kpis"))
    gap = safe_dict(data.get("gap_analysis"))
    gap_val = safe_num(gap.get("revenue_gap", kpis.get("revenue_gap", 0)))
    if gap_val > 0:
        items.append(_new_item(
            entity="Revenue Gap",
            entity_type="revenue_gap",
            source_system="Revenue Forecasting",
            reason="Projected revenue gap to target detected",
            opportunity_value=gap_val,
            risk="high",
            recommended_action=safe_str(gap.get("recommended_action", "Close revenue gap")),
            action_type="take_action",
            status="open",
        ))
    for risk in safe_list(data.get("risks")):
        r = safe_dict(risk)
        items.append(_new_item(
            entity=r.get("title", r.get("risk", "Revenue risk")),
            entity_type="revenue_risk",
            source_system="Revenue Forecasting",
            reason=r.get("description", r.get("reason", "Revenue risk identified")),
            opportunity_value=safe_num(r.get("amount", r.get("value", 0))),
            risk="high",
            recommended_action=safe_str(r.get("recommended_action", r.get("mitigation", "Mitigate risk"))),
            action_type="take_action",
        ))
    for action in safe_list(data.get("action_plan")):
        a = safe_dict(action)
        items.append(_new_item(
            entity=a.get("title", a.get("action", "Revenue action")),
            entity_type="revenue_action",
            source_system="Revenue Forecasting",
            reason=a.get("description", a.get("reason", "Revenue action recommended")),
            opportunity_value=safe_num(a.get("impact", a.get("value", 0))),
            risk=safe_str(a.get("risk", "medium"), "medium"),
            recommended_action=safe_str(a.get("action", a.get("recommended_action", "Execute action"))),
            action_type="take_action",
        ))
    return items


def _normalize_clv(data) -> List[Dict[str, Any]]:
    items = []
    for risk in safe_list(data.get("risks")):
        r = safe_dict(risk)
        items.append(_new_item(
            entity=r.get("client_name", r.get("name", "At-risk client")),
            entity_type="at_risk_client",
            source_system="CLV Intelligence",
            reason=r.get("description", r.get("reason", "Client at risk")),
            opportunity_value=safe_num(r.get("clv", r.get("value", 0))),
            risk="high",
            recommended_action=safe_str(r.get("recommended_action", r.get("action", "Retain client"))),
            action_type="call",
        ))
    for call in safe_list(data.get("call_priorities")):
        c = safe_dict(call)
        items.append(_new_item(
            entity=c.get("client_name", c.get("name", "Client call priority")),
            entity_type="client_call",
            source_system="CLV Intelligence",
            reason=c.get("reason", c.get("description", "High-value client to call")),
            opportunity_value=safe_num(c.get("clv", c.get("value", 0))),
            risk="low",
            recommended_action=safe_str(c.get("recommended_action", "Call client")),
            action_type="call",
        ))
    for opp in safe_list(data.get("opportunities")):
        o = safe_dict(opp)
        items.append(_new_item(
            entity=o.get("client_name", o.get("title", "Client opportunity")),
            entity_type="client_opportunity",
            source_system="CLV Intelligence",
            reason=o.get("description", o.get("reason", "Client opportunity")),
            opportunity_value=safe_num(o.get("value", o.get("estimated_value", 0))),
            risk="low",
            recommended_action=safe_str(o.get("recommended_action", "Pursue opportunity")),
            action_type="email",
        ))
    return items


def _normalize_crm(data) -> List[Dict[str, Any]]:
    items = []
    kpis = safe_dict(data.get("kpis"))
    if safe_num(kpis.get("critical_alerts", 0)) > 0:
        items.append(_new_item(
            entity="Critical CRM Alerts",
            entity_type="crm_alert",
            source_system="CRM Management",
            reason="Critical lifecycle alerts require attention",
            risk="high",
            recommended_action="Review critical CRM alerts",
            action_type="view_details",
        ))
    if safe_num(kpis.get("overdue_tasks", 0)) > 0:
        items.append(_new_item(
            entity="Overdue Tasks",
            entity_type="overdue_task",
            source_system="CRM Management",
            reason="Tasks are overdue",
            risk="medium",
            recommended_action="Complete or reschedule overdue tasks",
            action_type="take_action",
        ))
    if safe_num(kpis.get("high_confidence_dups", 0)) > 0:
        items.append(_new_item(
            entity="Duplicate Contacts",
            entity_type="duplicate",
            source_system="CRM Management",
            reason="High-confidence duplicate contacts detected",
            risk="medium",
            recommended_action="Merge duplicate contacts",
            action_type="take_action",
        ))
    if safe_num(kpis.get("sync_issues", 0)) > 0:
        items.append(_new_item(
            entity="Cross-Agent Sync Issues",
            entity_type="sync_issue",
            source_system="CRM Management",
            reason="Data sync issues across agents",
            risk="medium",
            recommended_action="Resolve sync issues",
            action_type="take_action",
        ))
    return items


def _normalize_phase1(data) -> List[Dict[str, Any]]:
    items = []
    kpis = safe_dict(data.get("kpis"))
    new_leads = safe_num(kpis.get("new_leads", 0))
    if new_leads > 0:
        items.append(_new_item(
            entity=f"{new_leads} New Leads",
            entity_type="new_lead_batch",
            source_system="Lead Follow-Up",
            reason="New leads awaiting first contact",
            opportunity_value=new_leads * 500,
            risk="medium",
            recommended_action="Contact new leads within 24 hours",
            action_type="call",
            due_date=TODAY.isoformat(),
        ))
    return items


def _normalize_phase2(data) -> List[Dict[str, Any]]:
    items = []
    kpis = safe_dict(data.get("kpis"))
    blocks = safe_num(kpis.get("compliance_blocks", 0))
    if blocks > 0:
        items.append(_new_item(
            entity="Compliance Blocks",
            entity_type="compliance_block",
            source_system="Marketing Content",
            reason="Compliance blocks on marketing content",
            risk="high",
            recommended_action="Review and resolve compliance blocks",
            action_type="approve",
        ))
    return items


def _normalize_phase3(data) -> List[Dict[str, Any]]:
    items = []
    kpis = safe_dict(data.get("kpis"))
    surveys_sent = safe_num(kpis.get("surveys_sent", 0))
    surveys_completed = safe_num(kpis.get("surveys_completed", 0))
    if surveys_sent > 0 and surveys_completed < surveys_sent:
        items.append(_new_item(
            entity="Pending Survey Responses",
            entity_type="survey_follow_up",
            source_system="Client Nurture",
            reason="Outstanding survey responses",
            risk="low",
            recommended_action="Follow up on pending surveys",
            action_type="email",
        ))
    return items


def _normalize_phase4(data) -> List[Dict[str, Any]]:
    items = []
    kpis = safe_dict(data.get("kpis"))
    partner_pipeline = safe_num(kpis.get("partner_pipeline", 0))
    if partner_pipeline > 0:
        items.append(_new_item(
            entity=f"{partner_pipeline} Partner Prospects",
            entity_type="partner_prospect",
            source_system="Referral Growth",
            reason="Partner prospects in pipeline",
            opportunity_value=partner_pipeline * 1000,
            risk="low",
            recommended_action="Advance partner prospects",
            action_type="email",
        ))
    return items


def _normalize_phase5(data) -> List[Dict[str, Any]]:
    items = []
    kpis = safe_dict(data.get("kpis"))
    consults = safe_num(kpis.get("consultations_requested", 0))
    if consults > 0:
        items.append(_new_item(
            entity=f"{consults} Consultation Requests",
            entity_type="consultation_request",
            source_system="Community Outreach",
            reason="Consultation requests from community events",
            opportunity_value=consults * 750,
            risk="low",
            recommended_action="Schedule consultations",
            action_type="schedule",
        ))
    return items


def _normalize_action_queue(actions) -> List[Dict[str, Any]]:
    items = []
    for a in safe_list(actions):
        a = safe_dict(a)
        sev = safe_str(a.get("severity", "info"), "info")
        risk = "high" if sev in ("critical", "high") else "medium" if sev == "warning" else "low"
        items.append(_new_item(
            entity=safe_str(a.get("contact", a.get("type", "Action item"))),
            entity_type=safe_str(a.get("type", "action_item")),
            source_system=safe_str(a.get("agent", "Action Queue")),
            reason=safe_str(a.get("action", "Queued action")),
            risk=risk,
            recommended_action=safe_str(a.get("action", "Review action")),
            action_type="take_action",
            status=safe_str(a.get("status", "open")),
        ))
    return items


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------

def _score_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Score an item 0-100 and attach contributing factors + explanation."""
    factors = {}

    # Urgency (0-25): risk level + due date proximity
    risk = safe_str(item.get("risk", "low"), "low").lower()
    urgency_base = {"high": 20, "medium": 12, "low": 5}.get(risk, 8)
    due = item.get("due_date")
    deadline_bonus = 0
    if due:
        try:
            due_date = date.fromisoformat(safe_str(due)[:10])
            days = (due_date - TODAY).days
            if days <= 0:
                deadline_bonus = 5
            elif days <= 3:
                deadline_bonus = 4
            elif days <= 7:
                deadline_bonus = 2
        except Exception:
            deadline_bonus = 0
    urgency = min(25, urgency_base + deadline_bonus)
    factors["urgency"] = round(urgency, 1)

    # Value (0-25): opportunity value scaled
    val = safe_num(item.get("opportunity_value", 0))
    if val >= 10000:
        value_score = 25
    elif val >= 5000:
        value_score = 20
    elif val >= 1000:
        value_score = 15
    elif val > 0:
        value_score = 10
    else:
        value_score = 5
    factors["value"] = round(value_score, 1)

    # Probability (0-15): entity_type based heuristic
    etype = safe_str(item.get("entity_type", "")).lower()
    prob_map = {
        "escalation": 13, "at_risk_client": 12, "revenue_gap": 11,
        "revenue_risk": 12, "critical": 13, "crm_alert": 10,
        "lead": 10, "referral_opportunity": 9, "client_opportunity": 9,
        "missed_opportunity": 9, "decaying_lead": 8, "overdue_task": 10,
        "new_lead_batch": 9, "partner_prospect": 7, "consultation_request": 8,
        "duplicate": 6, "sync_issue": 7, "compliance_block": 11,
        "client_call": 11,
    }
    probability = prob_map.get(etype, 7)
    factors["probability"] = round(float(probability), 1)

    # Risk (0-15): already mapped
    risk_score = {"high": 15, "medium": 9, "low": 4}.get(risk, 6)
    factors["risk"] = round(float(risk_score), 1)

    # Recency (0-5): all current = full
    factors["recency"] = 5.0

    # Deadline (0-5)
    factors["deadline"] = round(float(deadline_bonus), 1)

    # Strategic importance (0-10): high-value entity types
    strategic_types = {"escalation", "revenue_gap", "revenue_risk", "at_risk_client",
                       "compliance_block", "executive_priority", "critical"}
    strategic = 10 if etype in strategic_types else 5
    factors["strategic_importance"] = round(float(strategic), 1)

    total = sum(factors.values())
    total = min(100.0, round(total, 1))
    item["priority_score"] = total
    item["contributing_factors"] = factors

    # "Why this is #1" explanation
    top_factors = sorted(factors.items(), key=lambda x: x[1], reverse=True)[:3]
    factor_names = [f for f, _ in top_factors]
    item["explanation"] = (
        "Ranked #{rank} because of high {factors}. {reason} "
        "[SAMPLE] {draft}".format(
            rank="__RANK__",
            factors=", ".join(factor_names),
            reason=safe_str(item.get("reason", "")),
            draft=DRAFT_DISCLAIMER,
        )
    )
    return item


def _rank_and_explain(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scored = [_score_item(dict(i)) for i in items]
    scored.sort(key=lambda x: safe_num(x.get("priority_score", 0)), reverse=True)
    for idx, item in enumerate(scored, 1):
        item["explanation"] = item["explanation"].replace("__RANK__", str(idx))
    return scored


# ---------------------------------------------------------------------------
# Public API functions
# ---------------------------------------------------------------------------

def get_top_5_priorities() -> List[Dict[str, Any]]:
    """Return the 5 highest-value actions, ranked. Filters completed/snoozed items."""
    all_items = _build_all_items()
    
    # Filter out completed/snoozed items from action ledger
    try:
        from action_ledger import get_completed_entity_types, get_snoozed_entities
        completed_types = get_completed_entity_types()
        snoozed = get_snoozed_entities()
        snoozed_entities = [s.get("entity", "") for s in snoozed]
        all_items = [i for i in all_items if i.get("entity_type", "") not in completed_types
                     and i.get("entity", "") not in snoozed_entities]
    except Exception:
        pass
    
    # Ensure diversity: cap items per entity_type to 2 so revenue doesn't dominate
    ranked = _rank_and_explain(all_items)
    diverse = []
    type_counts = {}
    for item in ranked:
        et = item.get("entity_type", "unknown")
        type_counts[et] = type_counts.get(et, 0) + 1
        if type_counts[et] <= 2:  # max 2 per type
            diverse.append(item)
        if len(diverse) >= 5:
            break
    return diverse[:5]


def get_what_should_i_do_next() -> Dict[str, Any]:
    """Return the single highest-value action with full explanation."""
    top = get_top_5_priorities()
    if not top:
        return {
            "entity": "No priorities detected",
            "explanation": "No urgent actions detected at this time. [SAMPLE]",
            "recommended_action": "Review dashboard for routine items.",
            "priority_score": 0,
            "disclaimer": DRAFT_DISCLAIMER,
        }
    nxt = top[0]
    nxt = dict(nxt)
    nxt["disclaimer"] = DRAFT_DISCLAIMER
    nxt["sample"] = True
    return nxt


def get_needs_attention() -> List[Dict[str, Any]]:
    """Auto-generated attention items: stale leads, at-risk clients, etc."""
    all_items = _build_all_items()
    attention_types = {
        "at_risk_client", "decaying_lead", "overdue_task", "missed_opportunity",
        "compliance_block", "revenue_risk", "sync_issue", "duplicate",
        "crm_alert", "escalation", "revenue_gap", "survey_follow_up",
    }
    attn = [i for i in all_items if safe_str(i.get("entity_type")) in attention_types]
    attn = [_score_item(dict(i)) for i in attn]
    attn.sort(key=lambda x: safe_num(x.get("priority_score", 0)), reverse=True)
    # Ensure each has a clean attention label
    for a in attn:
        a["attention_label"] = safe_str(a.get("reason", a.get("entity", "Needs attention")))
        a["disclaimer"] = DRAFT_DISCLAIMER
    return attn[:15]


def get_business_snapshot() -> Dict[str, Any]:
    """KPI cards aggregating data from all agents."""
    data = _collect_all_agent_data()
    cards = []
    # Helper to pull kpis safely
    def k(phase):
        return safe_dict(data.get(phase, {}).get("kpis"))

    p1, p2, p3, p4, p5, p6 = k(1), k(2), k(3), k(4), k(5), k(6)
    p7, p8, p9, p10, p11, p12 = k(7), k(8), k(9), k(10), k(11), k(12)

    cards.append({"label": "Total Contacts", "value": safe_num(p1.get("total_contacts", 0)), "agent": "Lead Follow-Up"})
    cards.append({"label": "Open Leads", "value": safe_num(p1.get("leads", 0)), "agent": "Lead Follow-Up"})
    cards.append({"label": "Hot Leads", "value": safe_num(p9.get("hot_leads", 0)), "agent": "Lead Scoring"})
    cards.append({"label": "Business Health", "value": safe_str(p7.get("health_grade", "N/A")), "agent": "Executive AI"})
    cards.append({"label": "Health Score", "value": safe_num(p7.get("health_score", 0)), "agent": "Executive AI"})
    cards.append({"label": "Active Pipeline", "value": "${:,}".format(int(safe_num(p6.get("active_pipeline_value", 0)))), "agent": "CRM Management"})
    cards.append({"label": "Close Rate", "value": "{}%".format(int(safe_num(p6.get("close_rate", 0)))), "agent": "CRM Management"})
    cards.append({"label": "Data Quality", "value": "{}%".format(int(safe_num(p6.get("data_quality_score", 0)))), "agent": "CRM Management"})
    cards.append({"label": "Referral Sources", "value": safe_num(p10.get("total_sources", p4.get("referral_sources", 0))), "agent": "Referral Intelligence"})
    cards.append({"label": "Referral Opportunities", "value": safe_num(p10.get("total_opportunities", 0)), "agent": "Referral Intelligence"})
    cards.append({"label": "Actual Revenue", "value": "${:,}".format(int(safe_num(p11.get("actual_revenue", 0)))), "agent": "Revenue Forecasting"})
    cards.append({"label": "Revenue Gap", "value": "${:,}".format(int(safe_num(p11.get("revenue_gap", 0)))), "agent": "Revenue Forecasting"})
    cards.append({"label": "Total Clients", "value": safe_num(p12.get("total_clients", p1.get("clients", 0))), "agent": "CLV Intelligence"})
    cards.append({"label": "Average CLV", "value": "${:,.0f}".format(safe_num(p12.get("average_clv", 0))), "agent": "CLV Intelligence"})
    cards.append({"label": "Overdue Tasks", "value": safe_num(p6.get("overdue_tasks", 0)), "agent": "CRM Management"})
    cards.append({"label": "Critical Alerts", "value": safe_num(p6.get("critical_alerts", 0)), "agent": "CRM Management"})
    return {"cards": cards, "disclaimer": SAMPLE_DISCLAIMER}


def get_what_changed_summary() -> List[Dict[str, Any]]:
    """Meaningful changes only (not noise)."""
    data = _collect_all_agent_data()
    wc = safe_dict(data.get(8, {}))
    out = []
    for change in safe_list(wc.get("top_5_changes")):
        c = safe_dict(change)
        out.append({
            "title": safe_str(c.get("title", c.get("change", "Change"))),
            "severity": safe_str(c.get("severity", "informational")),
            "description": safe_str(c.get("description", c.get("summary", ""))),
            "category": safe_str(c.get("category", "")),
            "recommended_action": safe_str(c.get("recommended_action", "Review")),
            "source_system": "What Changed?",
            "disclaimer": DRAFT_DISCLAIMER,
        })
    return out


def get_client_health_summary() -> List[Dict[str, Any]]:
    """Concise client intelligence from CLV agent."""
    data = _collect_all_agent_data()
    clv = safe_dict(data.get(12, {}))
    out = []
    for client in safe_list(clv.get("clients")):
        c = safe_dict(client)
        out.append({
            "client_name": safe_str(c.get("client_name", c.get("name", "Client"))),
            "clv": safe_num(c.get("clv", c.get("estimated_clv", c.get("value", 0)))),
            "health_score": safe_num(c.get("health_score", c.get("score", 0))),
            "segment": safe_str(c.get("segment", c.get("tier", ""))),
            "risk_level": safe_str(c.get("risk", c.get("risk_level", "low"))),
            "recommended_action": safe_str(c.get("recommended_action", "Monitor")),
            "source_system": "CLV Intelligence",
            "disclaimer": DRAFT_DISCLAIMER,
        })
    return out[:10]


def get_referral_summary() -> Dict[str, Any]:
    """Referral opportunities surfaced automatically."""
    data = _collect_all_agent_data()
    ref = safe_dict(data.get(10, {}))
    kpis = safe_dict(ref.get("kpis"))
    out = []
    for opp in safe_list(ref.get("top_opportunities")):
        o = safe_dict(opp)
        out.append({
            "source": safe_str(o.get("name", o.get("source_name", "Referral source"))),
            "opportunity": safe_str(o.get("reason", o.get("description", "Referral opportunity"))),
            "estimated_value": safe_num(o.get("estimated_value", o.get("potential_value", 0))),
            "recommended_action": safe_str(o.get("recommended_action", "Engage source")),
            "source_system": "Referral Intelligence",
            "disclaimer": DRAFT_DISCLAIMER,
        })
    return {
        "opportunity_count": safe_num(kpis.get("total_opportunities", len(out))),
        "active_sources": safe_num(kpis.get("total_sources", kpis.get("active_sources", 0))),
        "opportunities": out[:8],
        "source_system": "Referral Intelligence",
        "disclaimer": DRAFT_DISCLAIMER,
    }


def get_marketing_summary() -> Dict[str, Any]:
    """Content approvals, campaigns, engagement."""
    data = _collect_all_agent_data()
    p2 = safe_dict(data.get(2, {}))
    p3 = safe_dict(data.get(3, {}))
    kpis2 = safe_dict(p2.get("kpis"))
    kpis3 = safe_dict(p3.get("kpis"))
    return {
        "content_pieces": safe_num(kpis2.get("content_pieces", 0)),
        "email_campaigns": safe_num(kpis2.get("email_campaigns", 0)),
        "total_emails": safe_num(kpis2.get("total_emails", 0)),
        "calendar_entries": safe_num(kpis2.get("calendar_entries", 0)),
        "compliance_status": safe_str(kpis2.get("compliance_status", "PASS")),
        "compliance_blocks": safe_num(kpis2.get("compliance_blocks", 0)),
        "drip_campaigns": safe_num(kpis3.get("drip_campaigns", 0)),
        "drip_emails": safe_num(kpis3.get("drip_emails", 0)),
        "touchpoints_scheduled": safe_num(kpis3.get("touchpoints_scheduled", 0)),
        "active_nurture_clients": safe_num(kpis3.get("active_nurture_clients", 0)),
        "surveys_sent": safe_num(kpis3.get("surveys_sent", 0)),
        "surveys_completed": safe_num(kpis3.get("surveys_completed", 0)),
        "source_system": "Marketing Content + Client Nurture",
        "disclaimer": SAMPLE_DISCLAIMER,
    }


def get_revenue_summary() -> Dict[str, Any]:
    """30-day forecast, goal, gap, recommendation."""
    data = _collect_all_agent_data()
    rev = safe_dict(data.get(11, {}))
    kpis = safe_dict(rev.get("kpis"))
    gap = safe_dict(rev.get("gap_analysis"))
    targets = safe_dict(rev.get("targets"))
    target_val = safe_num(targets.get("target", targets.get("monthly_target", 0)))
    actual_val = safe_num(kpis.get("actual_revenue", 0))
    gap_val = safe_num(gap.get("revenue_gap", kpis.get("revenue_gap", 0)))
    forecast_30 = safe_num(kpis.get("weighted_pipeline", 0)) + actual_val
    recommendation = "On track to exceed target." if gap_val <= 0 else "Accelerate pipeline to close revenue gap."
    return {
        "forecast_30_day": forecast_30,
        "goal": target_val,
        "gap": gap_val,
        "actual_revenue": actual_val,
        "committed_revenue": safe_num(kpis.get("committed_revenue", 0)),
        "weighted_pipeline": safe_num(kpis.get("weighted_pipeline", 0)),
        "revenue_at_risk": safe_num(kpis.get("revenue_at_risk", 0)),
        "recommendation": recommendation,
        "source_system": "Revenue Forecasting",
        "disclaimer": DRAFT_DISCLAIMER,
    }


# ---------------------------------------------------------------------------
# Internal: build the full normalized item list from all agents
# ---------------------------------------------------------------------------

def _build_all_items() -> List[Dict[str, Any]]:
    data = _collect_all_agent_data()
    items: List[Dict[str, Any]] = []
    items += _normalize_phase1(data.get(1, {}))
    items += _normalize_phase2(data.get(2, {}))
    items += _normalize_phase3(data.get(3, {}))
    items += _normalize_phase4(data.get(4, {}))
    items += _normalize_phase5(data.get(5, {}))
    items += _normalize_crm(data.get(6, {}))
    items += _normalize_executive(data.get(7, {}))
    items += _normalize_what_changed(data.get(8, {}))
    items += _normalize_lead_scoring(data.get(9, {}))
    items += _normalize_referral_intelligence(data.get(10, {}))
    items += _normalize_revenue_forecasting(data.get(11, {}))
    items += _normalize_clv(data.get(12, {}))
    try:
        items += _normalize_action_queue(get_action_queue())
    except Exception:
        pass
    return items


# ---------------------------------------------------------------------------
# Master function
# ---------------------------------------------------------------------------

def get_command_center_v2() -> Dict[str, Any]:
    """Master function returning ALL V2 intelligence."""
    top5 = get_top_5_priorities()
    next_action = get_what_should_i_do_next()
    needs_attention = get_needs_attention()
    snapshot = get_business_snapshot()
    changed = get_what_changed_summary()
    client_health = get_client_health_summary()
    referrals = get_referral_summary()
    marketing = get_marketing_summary()
    revenue = get_revenue_summary()

    # agent status rollup
    data = _collect_all_agent_data()
    agent_status = []
    for phase in range(1, 13):
        d = data.get(phase, {})
        agent_status.append({
            "phase": phase,
            "agent_name": AGENT_LABELS.get(phase, safe_str(d.get("agent_name", f"Phase {phase}"))),
            "status": safe_str(d.get("status", "unknown")),
        })

    result = {
        "greeting": get_greeting(),
        "date": TODAY.isoformat(),
        "timestamp": datetime.now().isoformat(),
        "top_5_priorities": top5,
        "what_should_i_do_next": next_action,
        "needs_attention": needs_attention,
        "business_snapshot": snapshot,
        "what_changed_summary": changed,
        "client_health_summary": client_health,
        "referral_summary": referrals,
        "marketing_summary": marketing,
        "revenue_summary": revenue,
        "agent_status": agent_status,
        "disclaimer": "{} {}".format(SAMPLE_DISCLAIMER, DRAFT_DISCLAIMER),
        "server_import_error": safe_str(_SERVER_IMPORT_ERROR) if _SERVER_IMPORT_ERROR else None,
    }
    return sanitize(result)


# ---------------------------------------------------------------------------
# CLI entry point for testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("COMMAND CENTER V2 ENGINE -- TEST RUN")
    print("=" * 70)
    result = get_command_center_v2()
    print("\nGreeting:", result["greeting"])
    print("Date:", result["date"])
    print("\n--- TOP 5 PRIORITIES ---")
    for i, p in enumerate(result["top_5_priorities"], 1):
        print("  {}. [{}] {} ({}) -- {}".format(
            i,
            p.get("priority_score", 0),
            p.get("entity", "?"),
            p.get("entity_type", ""),
            p.get("reason", "")[:80],
        ))
    print("\n--- WHAT SHOULD I DO NEXT ---")
    nxt = result["what_should_i_do_next"]
    print("  Entity:", nxt.get("entity"))
    print("  Score:", nxt.get("priority_score"))
    print("  Action:", nxt.get("recommended_action"))
    print("  Explanation:", nxt.get("explanation"))
    print("\n--- NEEDS ATTENTION ({} items) ---".format(len(result["needs_attention"])))
    for a in result["needs_attention"][:5]:
        print("  - [{}] {} : {}".format(a.get("priority_score", 0), a.get("entity"), a.get("reason", "")[:70]))
    print("\n--- BUSINESS SNAPSHOT ({} cards) ---".format(len(result["business_snapshot"]["cards"])))
    for c in result["business_snapshot"]["cards"]:
        print("  {}: {} ({})".format(c["label"], c["value"], c["agent"]))
    print("\n--- WHAT CHANGED SUMMARY ({} items) ---".format(len(result["what_changed_summary"])))
    print("\n--- CLIENT HEALTH ({} items) ---".format(len(result["client_health_summary"])))
    print("--- REFERRAL SUMMARY ({} items) ---".format(len(result["referral_summary"])))
    print("--- MARKETING SUMMARY ---")
    m = result["marketing_summary"]
    print("  Content pieces:", m["content_pieces"], "| Campaigns:", m["email_campaigns"], "| Compliance:", m["compliance_status"])
    print("--- REVENUE SUMMARY ---")
    r = result["revenue_summary"]
    print("  Forecast 30d:", r["forecast_30_day"], "| Goal:", r["goal"], "| Gap:", r["gap"])
    print("  Recommendation:", r["recommendation"])
    print("\n--- AGENT STATUS ---")
    for a in result["agent_status"]:
        print("  Phase {}: {} -- {}".format(a["phase"], a["agent_name"], a["status"]))
    if result.get("server_import_error"):
        print("\nSERVER IMPORT ERROR:", result["server_import_error"])
    print("\n" + "=" * 70)
    print("V2 ENGINE TEST COMPLETE -- all sections generated.")
    print("=" * 70)
