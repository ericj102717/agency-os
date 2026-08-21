#!/usr/bin/env python3
"""
Command Center Action Engine
=============================
Converts intelligence items from the V2 priority engine into actionable
buttons. Determines the appropriate action(s) for each priority item based on
its entity_type and context.

No external automation is ever pretended. When no real integration exists,
the engine produces an internal workflow action (open modal/panel, create a
local task, show "DRAFT -- owner approval required").
"""

import os
import sys
from datetime import datetime, date
from typing import Dict, Any, List

sys.path.insert(0, '/home/user/workspace/command-center')

DRAFT_DISCLAIMER = "DRAFT -- owner approval required."

# All available action types
AVAILABLE_ACTIONS = [
    "call", "text", "email", "schedule", "view", "approve", "follow_up",
    "add_note", "create_task", "snooze", "dismiss", "take_action",
    "view_details", "not_now",
]

# SVG path data for each action icon (emoji-free, simple line icons)
ICON_PATHS = {
    "call": "M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.81.36 1.6.7 2.34a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.74-1.74a2 2 0 0 1 2.11-.45c.74.34 1.53.57 2.34.7A2 2 0 0 1 22 16.92z",
    "text": "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
    "email": "M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z M22 6l-10 7L2 6",
    "schedule": "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z M12 6v6l4 2",
    "view": "M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
    "approve": "M20 6L9 17l-5-5",
    "follow_up": "M9 11l3 3L22 4 M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
    "add_note": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M12 18v-6 M9 15h6",
    "create_task": "M9 11l3 3L22 4 M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
    "snooze": "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z M12 6v6l4 2",
    "dismiss": "M18 6L6 18 M6 6l12 12",
    "take_action": "M13 2L3 14h9l-1 8 10-12h-9l1-8z",
    "view_details": "M2 12s4-8 10-8 10 8 10 8-4 8-10 8-10-8-10-8z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
    "not_now": "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z M8 12h8",
}


def _label_for(action_type: str) -> str:
    """Human-readable label for an action type."""
    labels = {
        "call": "Call",
        "text": "Text",
        "email": "Email",
        "schedule": "Schedule",
        "view": "View",
        "approve": "Approve",
        "follow_up": "Follow Up",
        "add_note": "Add Note",
        "create_task": "Create Task",
        "snooze": "Snooze",
        "dismiss": "Dismiss",
        "take_action": "Take Action",
        "view_details": "View Details",
        "not_now": "Not Now",
    }
    return labels.get(action_type, action_type.replace("_", " ").title())


def _icon_for(action_type: str) -> str:
    """Return SVG path data for an action (emoji-free)."""
    return ICON_PATHS.get(action_type, ICON_PATHS["view"])


def _has_external_integration() -> bool:
    """Check whether any real external integration (dialer, email API, etc.) exists.

    Returns False by default -- the Command Center does not currently own any
    outbound automation. All external actions are surfaced as DRAFT items.
    """
    return False


# ---------------------------------------------------------------------------
# Action selection rules
# ---------------------------------------------------------------------------

# Map entity_type -> list of (action_type, reason) tuples, in priority order.
ENTITY_ACTION_RULES: Dict[str, List[Dict[str, Any]]] = {
    "lead": [
        {"action_type": "call", "reason": "Direct contact recommended for high-value leads."},
        {"action_type": "email", "reason": "Send introductory email to lead."},
        {"action_type": "create_task", "reason": "Create follow-up task to track engagement."},
    ],
    "new_lead_batch": [
        {"action_type": "call", "reason": "Contact new leads within 24 hours."},
        {"action_type": "create_task", "reason": "Assign leads to follow-up tasks."},
        {"action_type": "email", "reason": "Send welcome sequence to new leads."},
    ],
    "decaying_lead": [
        {"action_type": "follow_up", "reason": "Re-engage decaying lead before it goes cold."},
        {"action_type": "call", "reason": "Direct call recommended to revive momentum."},
        {"action_type": "add_note", "reason": "Document re-engagement attempt."},
    ],
    "at_risk_client": [
        {"action_type": "call", "reason": "Personal call recommended to retain at-risk client."},
        {"action_type": "schedule", "reason": "Schedule a retention conversation."},
        {"action_type": "create_task", "reason": "Create retention task."},
    ],
    "client_call": [
        {"action_type": "call", "reason": "High-value client call priority."},
        {"action_type": "add_note", "reason": "Prepare notes before calling."},
    ],
    "client_opportunity": [
        {"action_type": "email", "reason": "Reach out regarding client opportunity."},
        {"action_type": "schedule", "reason": "Schedule opportunity discussion."},
    ],
    "referral_opportunity": [
        {"action_type": "email", "reason": "Engage referral source by email."},
        {"action_type": "call", "reason": "Personal call to referral source."},
        {"action_type": "follow_up", "reason": "Follow up on referral opportunity."},
    ],
    "partner_prospect": [
        {"action_type": "email", "reason": "Outreach to partner prospect."},
        {"action_type": "schedule", "reason": "Schedule partnership discussion."},
    ],
    "consultation_request": [
        {"action_type": "schedule", "reason": "Schedule requested consultation."},
        {"action_type": "call", "reason": "Confirm consultation by phone."},
    ],
    "escalation": [
        {"action_type": "take_action", "reason": "Escalation requires immediate action."},
        {"action_type": "view_details", "reason": "Review escalation details."},
    ],
    "executive_priority": [
        {"action_type": "take_action", "reason": "Executive priority requires action."},
        {"action_type": "view_details", "reason": "Review priority details."},
    ],
    "revenue_gap": [
        {"action_type": "take_action", "reason": "Close the revenue gap with pipeline acceleration."},
        {"action_type": "view_details", "reason": "Review gap analysis."},
    ],
    "revenue_risk": [
        {"action_type": "take_action", "reason": "Mitigate revenue risk."},
        {"action_type": "view_details", "reason": "Review risk details."},
    ],
    "revenue_action": [
        {"action_type": "take_action", "reason": "Execute recommended revenue action."},
        {"action_type": "create_task", "reason": "Create task to track revenue action."},
    ],
    "compliance_block": [
        {"action_type": "approve", "reason": "Review and approve blocked content."},
        {"action_type": "view_details", "reason": "Review compliance details."},
    ],
    "overdue_task": [
        {"action_type": "take_action", "reason": "Complete or reschedule overdue task."},
        {"action_type": "snooze", "reason": "Snooze task if not urgent."},
    ],
    "duplicate": [
        {"action_type": "take_action", "reason": "Merge duplicate contacts."},
        {"action_type": "view_details", "reason": "Review duplicate details."},
    ],
    "sync_issue": [
        {"action_type": "take_action", "reason": "Resolve cross-agent sync issue."},
        {"action_type": "view_details", "reason": "Review sync issue details."},
    ],
    "crm_alert": [
        {"action_type": "view_details", "reason": "Review critical CRM alerts."},
        {"action_type": "take_action", "reason": "Address critical alert."},
    ],
    "missed_opportunity": [
        {"action_type": "take_action", "reason": "Pursue missed opportunity."},
        {"action_type": "follow_up", "reason": "Follow up on opportunity."},
    ],
    "change": [
        {"action_type": "view_details", "reason": "Review detected change."},
        {"action_type": "not_now", "reason": "Defer if not actionable."},
    ],
    "survey_follow_up": [
        {"action_type": "email", "reason": "Send survey reminder email."},
        {"action_type": "follow_up", "reason": "Follow up on pending survey."},
    ],
    "action_item": [
        {"action_type": "take_action", "reason": "Action queue item requires attention."},
        {"action_type": "view_details", "reason": "Review action details."},
    ],
}


def _default_actions() -> List[Dict[str, Any]]:
    """Default actions available for any entity type."""
    return [
        {"action_type": "view_details", "reason": "Review item details."},
        {"action_type": "create_task", "reason": "Create a task for this item."},
        {"action_type": "snooze", "reason": "Snooze for later."},
        {"action_type": "dismiss", "reason": "Dismiss this item."},
    ]


def _is_external_action(action_type: str) -> bool:
    """Whether an action touches an external system (dialer, email API, etc.)."""
    return action_type in ("call", "text", "email", "schedule")


def _build_action(action_type: str, reason: str, entity_type: str = "") -> Dict[str, Any]:
    """Build a single action button metadata dict."""
    external = _is_external_action(action_type)
    available = True
    final_reason = reason
    if external and not _has_external_integration():
        # No real integration -- surface as internal workflow action.
        available = False
        final_reason = (
            "No external integration connected. Opens internal workflow panel. "
            + DRAFT_DISCLAIMER
        )
    return {
        "action_type": action_type,
        "label": _label_for(action_type),
        "icon": _icon_for(action_type),
        "icon_type": "svg_path",
        "available": available,
        "reason": final_reason,
        "is_external": external,
        "requires_approval": True,
        "disclaimer": DRAFT_DISCLAIMER,
        "entity_type_hint": entity_type,
    }


def get_actions_for_priority(priority_item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the list of available actions for a single priority item.

    Determines appropriate actions based on entity_type and context. Always
    appends a set of universal actions (view details, create task, snooze,
    dismiss).
    """
    entity_type = str(priority_item.get("entity_type", "")).lower().strip()
    rules = ENTITY_ACTION_RULES.get(entity_type, [])
    actions: List[Dict[str, Any]] = []
    seen = set()
    for rule in rules:
        at = rule.get("action_type", "view_details")
        if at in seen:
            continue
        seen.add(at)
        actions.append(_build_action(at, rule.get("reason", ""), entity_type))
    # Append universal actions not already present
    for default in _default_actions():
        at = default["action_type"]
        if at in seen:
            continue
        seen.add(at)
        actions.append(_build_action(at, default["reason"], entity_type))
    return actions


def get_all_actions(top_5: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return actions for all top-5 priorities, grouped by rank."""
    result = []
    for idx, priority in enumerate(top_5, 1):
        actions = get_actions_for_priority(priority)
        result.append({
            "rank": idx,
            "entity": str(priority.get("entity", "")),
            "entity_type": str(priority.get("entity_type", "")),
            "priority_score": priority.get("priority_score", 0),
            "actions": actions,
            "disclaimer": DRAFT_DISCLAIMER,
        })
    return result


def render_action_button(action: Dict[str, Any]) -> Dict[str, Any]:
    """Return button metadata suitable for frontend rendering.

    Includes type, label, icon (SVG path), availability flag, styling hints,
    and the reason the action is (or is not) available.
    """
    action_type = str(action.get("action_type", "view"))
    available = bool(action.get("available", True))
    return {
        "button_type": action_type,
        "label": action.get("label", _label_for(action_type)),
        "icon": action.get("icon", _icon_for(action_type)),
        "icon_format": "svg_path",
        "available": available,
        "variant": "primary" if available else "disabled",
        "onclick": "openWorkflowModal" if not available else "dispatchAction",
        "tooltip": action.get("reason", ""),
        "requires_approval": True,
        "is_external": bool(action.get("is_external", False)),
        "disclaimer": DRAFT_DISCLAIMER,
        "metadata": {
            "entity_type_hint": action.get("entity_type_hint", ""),
            "reason": action.get("reason", ""),
        },
    }


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("COMMAND CENTER ACTION ENGINE -- TEST RUN")
    print("=" * 70)
    sample_priorities = [
        {"entity": "Revenue Gap", "entity_type": "revenue_gap", "priority_score": 86.0},
        {"entity": "At-Risk Client Acme", "entity_type": "at_risk_client", "priority_score": 80.0},
        {"entity": "Hot Lead Jane Doe", "entity_type": "lead", "priority_score": 72.0},
        {"entity": "Referral Source Bob", "entity_type": "referral_opportunity", "priority_score": 68.0},
        {"entity": "Compliance Block", "entity_type": "compliance_block", "priority_score": 65.0},
    ]
    all_actions = get_all_actions(sample_priorities)
    for group in all_actions:
        print("\n#{} [{}] {} ({})".format(
            group["rank"], group["priority_score"], group["entity"], group["entity_type"]))
        for a in group["actions"]:
            btn = render_action_button(a)
            avail = "OK" if btn["available"] else "DISABLED"
            print("  [{}] {} -- {}".format(avail, btn["label"], btn["tooltip"][:70]))
    print("\n" + "=" * 70)
    print("ACTION ENGINE TEST COMPLETE.")
    print("=" * 70)
