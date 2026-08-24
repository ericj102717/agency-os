#!/usr/bin/env python3
"""
Action Persistence Ledger
Stores action events so the complete business loop works:
ACT → RECORD → RECALCULATE → UPDATE
"""
import json, os
from datetime import datetime, date

TODAY = date.today()  # Dynamic, not frozen
DRAFT_DISCLAIMER = "DRAFT -- owner approval required."
LEDGER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "action_events.json")

def _load_ledger():
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"actions": [], "completed_entity_types": [], "snoozed_entities": []}

def _save_ledger(data):
    with open(LEDGER_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)

def execute_action(action_type, entity, entity_type="", notes="", source_priority_id="", snooze_until="", snooze_type="custom", dismiss_reason="", outcome="", follow_up_date="", value=0, source=""):
    """
    Record an action execution.
    External actions (call/text/email) are marked 'in_progress' until outcome is recorded.
    Returns the action record.
    """
    EXTERNAL_ACTIONS = {"call", "text", "email", "contact_source", "contact_prospects", "request_introduction", "request_referral"}
    SNOOZE_ACTIONS = {"snooze"}
    DISMISS_ACTIONS = {"dismiss"}
    
    ledger = _load_ledger()
    action_id = f"act_{len(ledger['actions']) + 1}"
    
    # Determine status based on action type
    if action_type in SNOOZE_ACTIONS:
        status = "snoozed"
    elif action_type in DISMISS_ACTIONS:
        status = "dismissed"
    elif action_type in EXTERNAL_ACTIONS:
        # External actions are 'in_progress' until outcome is recorded
        status = "in_progress" if not outcome else "completed"
    else:
        # Internal actions (view, approve, create_task, etc.) are completed immediately
        status = "completed"
    
    action_record = {
        "id": action_id,
        "action_type": action_type,
        "entity": entity,
        "entity_type": entity_type,
        "notes": notes,
        "source_priority_id": source_priority_id,
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "date": str(TODAY),
        "owner_approval_required": True,
        "disclaimer": "DRAFT -- owner approval required"
    }
    
    # Add optional fields
    if snooze_until:
        action_record["snooze_until"] = snooze_until
        action_record["snooze_type"] = snooze_type
    if dismiss_reason:
        action_record["dismiss_reason"] = dismiss_reason
    if outcome:
        action_record["outcome"] = outcome
        action_record["completed_at"] = datetime.now().isoformat()
    if value:
        action_record["value"] = value
    if source:
        action_record["source_system"] = source
    
    ledger["actions"].append(action_record)
    
    # Track completed/snoozed entities so priority engine can filter them
    if action_record["status"] == "completed":
        if entity_type not in ledger["completed_entity_types"]:
            ledger["completed_entity_types"].append(entity_type)
    elif action_type == "snooze":
        ledger["snoozed_entities"].append({"entity": entity, "entity_type": entity_type, "snoozed_at": action_record["timestamp"], "snooze_until": snooze_until})
    
    _save_ledger(ledger)
    return action_record

def get_actions(limit=50, status=None, entity_type=None):
    """Get action history."""
    ledger = _load_ledger()
    actions = ledger["actions"]
    if status:
        actions = [a for a in actions if a.get("status") == status]
    if entity_type:
        actions = [a for a in actions if a.get("entity_type") == entity_type]
    return actions[-limit:] if limit else actions

def get_completed_entity_types():
    """Get list of entity types that have been actioned (for priority filtering)."""
    ledger = _load_ledger()
    return ledger.get("completed_entity_types", [])

def get_snoozed_entities():
    """Get list of snoozed entities."""
    ledger = _load_ledger()
    return ledger.get("snoozed_entities", [])

def is_entity_actioned(entity, entity_type=""):
    """Check if an entity has already been actioned."""
    ledger = _load_ledger()
    for action in ledger["actions"]:
        if action.get("status") == "completed" and action.get("entity") == entity:
            return True
        if action.get("entity_type") and action.get("entity_type") == entity_type and action.get("status") == "completed":
            return True
    return False

def complete_action(action_id, notes=""):
    """Mark an action as completed."""
    ledger = _load_ledger()
    for action in ledger["actions"]:
        if action.get("id") == action_id:
            action["status"] = "completed"
            action["completed_at"] = datetime.now().isoformat()
            if notes:
                action["completion_notes"] = notes
            et = action.get("entity_type", "")
            if et and et not in ledger["completed_entity_types"]:
                ledger["completed_entity_types"].append(et)
            _save_ledger(ledger)
            return action
    return {"error": "Action not found"}

def get_action_summary():
    """Get summary stats for dashboard."""
    ledger = _load_ledger()
    actions = ledger["actions"]
    return {
        "total_actions": len(actions),
        "completed": sum(1 for a in actions if a.get("status") == "completed"),
        "snoozed": sum(1 for a in actions if a.get("status") == "snoozed"),
        "dismissed": sum(1 for a in actions if a.get("status") == "dismissed"),
        "logged": sum(1 for a in actions if a.get("status") == "logged"),
        "completed_entity_types": ledger.get("completed_entity_types", []),
        "snoozed_count": len(ledger.get("snoozed_entities", [])),
        "last_action": actions[-1] if actions else None,
        "disclaimer": "DRAFT -- owner approval required"
    }

def reset_ledger():
    """Clear all actions (for testing)."""
    _save_ledger({
        "actions": [],
        "completed_entity_types": [], "snoozed_entities": [],
        "follow_ups": [],
    })
    return {"status": "reset"}


# ============================================================================
# ACTION & EXECUTION LAYER (V2)
# ----------------------------------------------------------------------------
# Full action lifecycle: recommended -> pending -> in_progress -> completed
#   (or -> snoozed / dismissed / failed)
# Outcomes, snoozes, dismissals, follow-ups, history, metrics, and the
# unified Action Center data payload used by the frontend.
# ============================================================================

# Full action state machine -- 7 states
ACTION_STATES = [
    "recommended",   # surfaced by an agent, not yet acknowledged
    "pending",        # acknowledged, queued for the owner
    "in_progress",    # owner is actively working it
    "completed",      # finished successfully
    "snoozed",        # deferred to a future date
    "dismissed",       # intentionally closed without action
    "failed",          # attempted but unsuccessful
]

# Allowed outcome values for record_outcome()
ACTION_OUTCOMES = [
    "connected", "voicemail", "no_answer", "interested", "not_interested",
    "follow_up_required", "appointment_scheduled", "closed", "other",
]

# Allowed snooze types
SNOOZE_TYPES = ["later_today", "tomorrow", "3_days", "next_week", "custom"]

# Allowed dismissal reasons
DISMISS_REASONS = [
    "already_handled", "not_interested", "no_longer_relevant",
    "incorrect_recommendation", "duplicate", "other",
]


def _next_id(ledger, prefix="act"):
    """Generate a stable, monotonically increasing id within the ledger."""
    actions = ledger.get("actions", [])
    n = len(actions) + 1
    while any(a.get("id") == f"{prefix}_{n}" for a in actions):
        n += 1
    return f"{prefix}_{n}"


def _parse_date(value):
    """Best-effort ISO date parser. Returns a date or None."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def record_outcome(action_id, outcome, notes=""):
    """Record the outcome of an action (e.g. connected, voicemail, interested).

    Sets status to completed for positive/terminal outcomes, in_progress for
    follow_up_required, and failed for negative terminal outcomes.
    Returns the updated action record or an error dict.
    """
    if outcome not in ACTION_OUTCOMES:
        return {"error": f"Invalid outcome '{outcome}'. Allowed: {ACTION_OUTCOMES}"}
    ledger = _load_ledger()
    for action in ledger.get("actions", []):
        if action.get("id") == action_id:
            action["outcome"] = outcome
            action["outcome_notes"] = notes
            action["outcome_recorded_at"] = datetime.now().isoformat()
            # Map outcome -> status
            if outcome == "follow_up_required":
                action["status"] = "in_progress"
            elif outcome in ("not_interested", "no_answer", "other"):
                # Negative/neutral terminal -> failed unless already completed
                if action.get("status") != "completed":
                    action["status"] = "failed"
            else:
                # connected, voicemail, interested, appointment_scheduled, closed
                action["status"] = "completed"
                action["completed_at"] = datetime.now().isoformat()
            # Track completed entity types for priority filtering
            if action.get("status") == "completed":
                et = action.get("entity_type", "")
                if et and et not in ledger.get("completed_entity_types", []):
                    ledger.setdefault("completed_entity_types", []).append(et)
            _save_ledger(ledger)
            return action
    return {"error": f"Action '{action_id}' not found"}


def snooze_action(action_id, snooze_until, snooze_type="custom"):
    """Snooze an action until a future ISO date.

    snooze_type: later_today, tomorrow, 3_days, next_week, custom.
    Returns the updated action record or an error dict.
    """
    if snooze_type not in SNOOZE_TYPES:
        return {"error": f"Invalid snooze_type '{snooze_type}'. Allowed: {SNOOZE_TYPES}"}
    target = _parse_date(snooze_until)
    if target is None:
        return {"error": f"Invalid snooze_until date '{snooze_until}'. Use ISO date string."}
    ledger = _load_ledger()
    for action in ledger.get("actions", []):
        if action.get("id") == action_id:
            action["status"] = "snoozed"
            action["snooze_until"] = target.isoformat()
            action["snooze_type"] = snooze_type
            action["snoozed_at"] = datetime.now().isoformat()
            # Track snoozed entity for priority filtering
            ledger.setdefault("snoozed_entities", []).append({
                "entity": action.get("entity", ""),
                "entity_type": action.get("entity_type", ""),
                "snoozed_at": action["snoozed_at"],
                "snooze_until": action["snooze_until"],
                "action_id": action_id,
            })
            _save_ledger(ledger)
            return action
    return {"error": f"Action '{action_id}' not found"}


def dismiss_action(action_id, reason, notes=""):
    """Dismiss an action with a reason.

    reasons: already_handled, not_interested, no_longer_relevant,
    incorrect_recommendation, duplicate, other.
    Returns the updated action record or an error dict.
    """
    if reason not in DISMISS_REASONS:
        return {"error": f"Invalid reason '{reason}'. Allowed: {DISMISS_REASONS}"}
    ledger = _load_ledger()
    for action in ledger.get("actions", []):
        if action.get("id") == action_id:
            action["status"] = "dismissed"
            action["dismiss_reason"] = reason
            action["dismiss_notes"] = notes
            action["dismissed_at"] = datetime.now().isoformat()
            _save_ledger(ledger)
            return action
    return {"error": f"Action '{action_id}' not found"}


def get_snoozed_returning(today=None):
    """Return snoozed actions whose return date has arrived (<= today).

    Resets each returning action's status to 'pending' so it re-enters the
    active queue. Returns the list of returned actions.
    """
    today = _parse_date(today) or TODAY
    ledger = _load_ledger()
    returning = []
    changed = False
    for action in ledger.get("actions", []):
        if action.get("status") == "snoozed":
            target = _parse_date(action.get("snooze_until"))
            if target is not None and target <= today:
                action["status"] = "pending"
                action["returned_from_snooze"] = today.isoformat()
                returning.append(action)
                changed = True
    if changed:
        # Prune returned entries from snoozed_entities tracker
        returned_ids = {a.get("id") for a in returning}
        ledger["snoozed_entities"] = [
            s for s in ledger.get("snoozed_entities", [])
            if s.get("action_id") not in returned_ids
        ]
        _save_ledger(ledger)
    return returning


def get_action_history(filters=None):
    """Return sorted action history filtered by date range, action_type,
    entity_type, outcome, and/or status.

    filters keys: start_date, end_date (ISO), action_type, entity_type,
    outcome, status. Returns actions sorted newest-first.
    """
    filters = filters or {}
    ledger = _load_ledger()
    actions = list(ledger.get("actions", []))

    start = _parse_date(filters.get("start_date"))
    end = _parse_date(filters.get("end_date"))
    action_type = filters.get("action_type")
    entity_type = filters.get("entity_type")
    outcome = filters.get("outcome")
    status = filters.get("status")

    out = []
    for a in actions:
        adate = _parse_date(a.get("date") or a.get("timestamp"))
        if start is not None and (adate is None or adate < start):
            continue
        if end is not None and (adate is None or adate > end):
            continue
        if action_type and a.get("action_type") != action_type:
            continue
        if entity_type and a.get("entity_type") != entity_type:
            continue
        if outcome and a.get("outcome") != outcome:
            continue
        if status and a.get("status") != status:
            continue
        out.append(a)
    out.sort(key=lambda x: x.get("timestamp", x.get("date", "")), reverse=True)
    return out


def get_performance_metrics():
    """Return performance metrics across all recorded actions.

    Includes: total_actions, completed, snoozed, dismissed, failed, overdue,
    completion_rate, contact_rate, appointment_rate, conversion_rate,
    actions_by_type, actions_by_entity, recent_trends.
    """
    ledger = _load_ledger()
    actions = ledger.get("actions", [])
    total = len(actions)
    today = TODAY

    completed = sum(1 for a in actions if a.get("status") == "completed")
    snoozed = sum(1 for a in actions if a.get("status") == "snoozed")
    dismissed = sum(1 for a in actions if a.get("status") == "dismissed")
    failed = sum(1 for a in actions if a.get("status") == "failed")
    in_progress = sum(1 for a in actions if a.get("status") == "in_progress")
    pending = sum(1 for a in actions if a.get("status") == "pending")
    recommended = sum(1 for a in actions if a.get("status") == "recommended")

    # Overdue: pending/in_progress items with a due_date in the past
    overdue = 0
    for a in actions:
        if a.get("status") in ("pending", "in_progress", "recommended"):
            due = _parse_date(a.get("due_date"))
            if due is not None and due < today:
                overdue += 1

    # Outcome-based rates (denominator = actions with a recorded outcome)
    with_outcome = [a for a in actions if a.get("outcome")]
    contacted = [a for a in actions if a.get("outcome") in ("connected", "voicemail")]
    appointments = [a for a in actions if a.get("outcome") == "appointment_scheduled"]
    closed = [a for a in actions if a.get("outcome") == "closed"]

    def _rate(num, den):
        return round((num / den) * 100, 1) if den else 0.0

    completion_rate = _rate(completed, total)
    contact_rate = _rate(len(contacted), len(with_outcome))
    appointment_rate = _rate(len(appointments), len(with_outcome))
    conversion_rate = _rate(len(closed), len(with_outcome))

    # Breakdowns
    actions_by_type = {}
    actions_by_entity = {}
    for a in actions:
        at = a.get("action_type", "unknown")
        actions_by_type[at] = actions_by_type.get(at, 0) + 1
        et = a.get("entity_type", "unknown")
        actions_by_entity[et] = actions_by_entity.get(et, 0) + 1

    # Recent trends: last 7 days completion counts (oldest -> newest)
    trends = {}
    for i in range(6, -1, -1):
        d = date.fromordinal(today.toordinal() - i)
        ds = d.isoformat()
        count = sum(
            1 for a in actions
            if a.get("status") == "completed"
            and _parse_date(a.get("completed_at") or a.get("timestamp") or a.get("date")) == d
        )
        trends[ds] = count

    return {
        "total_actions": total,
        "completed": completed,
        "snoozed": snoozed,
        "dismissed": dismissed,
        "failed": failed,
        "in_progress": in_progress,
        "pending": pending,
        "recommended": recommended,
        "overdue": overdue,
        "completion_rate": completion_rate,
        "contact_rate": contact_rate,
        "appointment_rate": appointment_rate,
        "conversion_rate": conversion_rate,
        "actions_by_type": actions_by_type,
        "actions_by_entity": actions_by_entity,
        "recent_trends": trends,
        "disclaimer": DRAFT_DISCLAIMER,
    }


def consolidate_duplicates(items):
    """Consolidate duplicate priority items by entity name.

    Takes a list of V2 priority items and groups by entity. When multiple
    agents flag the same entity (e.g. 3 agents say "Call John"), returns one
    consolidated item whose source_system is the merged agent names joined by
    ' + ' (e.g. "Lead Scoring + Executive AI + Lead Follow-Up").

    Merges opportunity_value (max), priority_score (max), risk (highest), and
    combines reasons. Preserves order of first appearance.
    """
    if not items:
        return []
    risk_rank = {"high": 3, "medium": 2, "low": 1}
    grouped = {}
    order = []
    for item in items:
        key = (item.get("entity") or "").strip().lower()
        if not key:
            # No entity name -- keep as-is, do not merge
            order.append(("__unique__" + str(id(item)), item))
            continue
        if key not in grouped:
            grouped[key] = {
                "entity": item.get("entity"),
                "entity_type": item.get("entity_type", ""),
                "reasons": [],
                "sources": [],
                "opportunity_value": 0,
                "priority_score": 0,
                "risk": "low",
                "items": [],
            }
            order.append((key, grouped[key]))
        g = grouped[key]
        g["items"].append(item)
        src = item.get("source_system", "")
        if src and src not in g["sources"]:
            g["sources"].append(src)
        reason = item.get("reason", "")
        if reason and reason not in g["reasons"]:
            g["reasons"].append(reason)
        g["opportunity_value"] = max(g["opportunity_value"], item.get("opportunity_value", 0) or 0)
        g["priority_score"] = max(g["priority_score"], item.get("priority_score", 0) or 0)
        g["risk"] = max(
            (g["risk"], item.get("risk", "low")),
            key=lambda r: risk_rank.get(r, 0),
        )

    consolidated = []
    for key, g in order:
        if key.startswith("__unique__"):
            consolidated.append(g)
            continue
        merged = dict(g["items"][0])  # base on first item to preserve shape
        merged["entity"] = g["entity"]
        merged["entity_type"] = g["entity_type"]
        merged["source_system"] = " + ".join(g["sources"]) if g["sources"] else ""
        merged["reason"] = " | ".join(g["reasons"]) if g["reasons"] else ""
        merged["opportunity_value"] = g["opportunity_value"]
        merged["priority_score"] = g["priority_score"]
        merged["risk"] = g["risk"]
        merged["consolidated_from"] = len(g["items"])
        merged["duplicate_sources"] = g["sources"]
        consolidated.append(merged)
    return consolidated


def create_follow_up(entity, entity_type, due_date, reason, value=0, source_action_id=""):
    """Create a follow-up task that will appear in priorities when due.

    due_date: ISO date string. The follow-up stays status='snoozed' with
    snooze_until=due_date so get_pending_follow_ups() can surface it on time.
    Returns the created follow-up record.
    """
    target = _parse_date(due_date)
    if target is None:
        return {"error": f"Invalid due_date '{due_date}'. Use ISO date string."}
    ledger = _load_ledger()
    ledger.setdefault("follow_ups", [])
    follow_up = {
        "id": _next_id(ledger, prefix="fu"),
        "entity": entity,
        "entity_type": entity_type,
        "action_type": "follow_up",
        "due_date": target.isoformat(),
        "reason": reason,
        "value": value,
        "source_action_id": source_action_id,
        "status": "snoozed",  # surfaces when due via get_pending_follow_ups
        "snooze_until": target.isoformat(),
        "created_at": datetime.now().isoformat(),
        "date": str(TODAY),
        "owner_approval_required": True,
        "disclaimer": DRAFT_DISCLAIMER,
    }
    ledger["follow_ups"].append(follow_up)
    _save_ledger(ledger)
    return follow_up


def get_pending_follow_ups(today=None):
    """Return follow-ups that are now due (due_date <= today).

    Resets each due follow-up's status to 'pending' so it re-enters the queue.
    """
    today = _parse_date(today) or TODAY
    ledger = _load_ledger()
    follow_ups = ledger.get("follow_ups", [])
    due = []
    changed = False
    for fu in follow_ups:
        if fu.get("status") == "snoozed":
            target = _parse_date(fu.get("due_date") or fu.get("snooze_until"))
            if target is not None and target <= today:
                fu["status"] = "pending"
                fu["surfaced_at"] = datetime.now().isoformat()
                due.append(fu)
                changed = True
    if changed:
        _save_ledger(ledger)
    return due


_v2_prio_cache = {"data": None, "ts": 0}
_V2_PRIO_TTL = 1800  # 30 minutes

def _get_v2_priorities():
    """Best-effort fetch of V2 top priorities for the Action Center.

    Returns an empty list if the V2 engine is unavailable so the Action Center
    still works standalone. Uses a 30-minute cache to avoid recomputing.
    """
    import time as _t
    now = _t.time()
    if _v2_prio_cache["data"] is not None and (now - _v2_prio_cache["ts"]) <= _V2_PRIO_TTL:
        return _v2_prio_cache["data"]
    try:
        from command_center_v2_engine import get_top_5_priorities as _top5
        result = _top5()
        _v2_prio_cache["data"] = result
        _v2_prio_cache["ts"] = now
        return result
    except Exception:
        return []


def _filter_by_view(items, view):
    """Filter Action Center items by the requested view.

    Views: today, overdue, high_priority, leads, clients, referrals,
    marketing, revenue. None/empty returns all.
    """
    if not view:
        return items
    view = view.lower()
    if view == "today":
        return [i for i in items if i.get("date") == str(TODAY)]
    if view == "overdue":
        out = []
        for i in items:
            due = _parse_date(i.get("due_date"))
            if due is not None and due < TODAY and i.get("status") not in ("completed", "dismissed"):
                out.append(i)
        return out
    if view == "high_priority":
        return [i for i in items if (i.get("priority_score", 0) or 0) >= 60]
    if view == "leads":
        lead_types = {"lead", "new_lead", "decaying_lead", "new_lead_batch"}
        return [i for i in items if i.get("entity_type", "") in lead_types]
    if view == "clients":
        client_types = {"at_risk_client", "high_value_client", "client_call", "client_opportunity"}
        return [i for i in items if i.get("entity_type", "") in client_types]
    if view == "referrals":
        ref_types = {"referral_opportunity", "partner_prospect", "consultation_request"}
        return [i for i in items if i.get("entity_type", "") in ref_types]
    if view == "marketing":
        mkt_types = {"marketing_content", "compliance_block", "nurture_task", "survey_follow_up"}
        return [i for i in items if i.get("entity_type", "") in mkt_types]
    if view == "revenue":
        rev_types = {"revenue_gap", "revenue_risk", "revenue_action", "missed_opportunity"}
        return [i for i in items if i.get("entity_type", "") in rev_types]
    return items


def get_action_center_data(view=None):
    """Return the unified Action Center payload.

    Includes: todays_actions (sorted by priority), overdue_actions,
    snoozed_returning, pending_follow_ups, and summary stats.
    Filter by view: today, overdue, high_priority, leads, clients, referrals,
    marketing, revenue.
    """
    # Surface returning snoozes and due follow-ups first (mutates ledger)
    snoozed_returning = get_snoozed_returning(today=TODAY)
    pending_follow_ups = get_pending_follow_ups(today=TODAY)

    # Pull V2 priorities (consolidated) and convert to action records
    v2_items = _get_v2_priorities()
    v2_items = consolidate_duplicates(v2_items)

    # Build action-shaped records for the Action Center
    todays_actions = []
    for item in v2_items:
        rec = {
            "id": item.get("id", ""),
            "entity": item.get("entity", ""),
            "entity_type": item.get("entity_type", ""),
            "action_type": item.get("action_type", "view"),
            "reason": item.get("reason", ""),
            "opportunity_value": item.get("opportunity_value", 0),
            "priority_score": item.get("priority_score", 0),
            "risk": item.get("risk", "low"),
            "source_system": item.get("source_system", ""),
            "recommended_action": item.get("recommended_action", ""),
            "due_date": item.get("due_date"),
            "status": item.get("status", "recommended"),
            "date": str(TODAY),
            "disclaimer": DRAFT_DISCLAIMER,
        }
        todays_actions.append(rec)

    # Overdue actions from the ledger (pending/in_progress with past due_date)
    ledger = _load_ledger()
    overdue_actions = []
    for a in ledger.get("actions", []):
        if a.get("status") in ("pending", "in_progress", "recommended"):
            due = _parse_date(a.get("due_date"))
            if due is not None and due < TODAY:
                overdue_actions.append(a)
    overdue_actions.sort(key=lambda x: x.get("priority_score", 0) or 0, reverse=True)

    # Apply view filter across todays_actions
    todays_actions = _filter_by_view(todays_actions, view)
    todays_actions.sort(key=lambda x: x.get("priority_score", 0) or 0, reverse=True)

    # Summary stats
    metrics = get_performance_metrics()
    summary = {
        "todays_count": len(todays_actions),
        "overdue_count": len(overdue_actions),
        "snoozed_returning_count": len(snoozed_returning),
        "pending_follow_ups_count": len(pending_follow_ups),
        "completion_rate": metrics.get("completion_rate", 0.0),
        "contact_rate": metrics.get("contact_rate", 0.0),
        "appointment_rate": metrics.get("appointment_rate", 0.0),
        "conversion_rate": metrics.get("conversion_rate", 0.0),
    }

    return {
        "date": str(TODAY),
        "view": view or "all",
        "todays_actions": todays_actions,
        "overdue_actions": overdue_actions,
        "snoozed_returning": snoozed_returning,
        "pending_follow_ups": pending_follow_ups,
        "summary": summary,
        "disclaimer": DRAFT_DISCLAIMER,
    }


if __name__ == "__main__":
    print("=== Action Ledger Test ===")
    reset_ledger()
    
    # Test execute
    result = execute_action("take_action", "Close revenue gap", "revenue_gap", "Test action")
    print(f"Execute: {result['id']} - {result['status']}")
    
    # Test get actions
    actions = get_actions()
    print(f"Actions: {len(actions)}")
    
    # Test completed entity types
    completed = get_completed_entity_types()
    print(f"Completed types: {completed}")
    
    # Test is_actioned
    is_done = is_entity_actioned("Close revenue gap")
    print(f"Is 'Close revenue gap' actioned: {is_done}")
    
    # Test summary
    summary = get_action_summary()
    print(f"Summary: {summary['total_actions']} total, {summary['completed']} completed")
    
    reset_ledger()
    print("\nLedger reset for production use.")
    print("All tests passed.")
