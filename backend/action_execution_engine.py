#!/usr/bin/env python3
"""
Action Execution Engine
=======================
Maps entity types to smart action buttons and prepares the full action
context for the Command Center frontend.

This engine does NOT perform any real outbound automation. External actions
(call, text, email) are surfaced as DRAFT items that require an external
integration (tel: / mailto: / copy-draft). Internal actions (view, snooze,
dismiss, create_task, add_note, approve) are handled in-app.

All data is marked [SAMPLE] and all recommendations carry the DRAFT
disclaimer -- owner approval is always required.
"""
import os
import sys
from datetime import date
from typing import Dict, Any, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TODAY = date(2026, 8, 16)
DRAFT_DISCLAIMER = "DRAFT -- owner approval required."
SAMPLE_TAG = "[SAMPLE]"

# ---------------------------------------------------------------------------
# 1. ENTITY_ACTIONS -- entity_type -> list of appropriate smart actions
# ---------------------------------------------------------------------------
ENTITY_ACTIONS: Dict[str, List[str]] = {
    "lead": ["call", "text", "email", "follow_up", "schedule", "view_lead", "create_task"],
    "new_lead": ["call", "text", "email", "follow_up", "schedule", "view_lead", "create_task"],
    "at_risk_client": ["schedule", "call", "add_note", "request_referral", "view_client"],
    "high_value_client": ["schedule_review", "call", "add_note", "view_client"],
    "referral_opportunity": ["contact_source", "request_introduction", "follow_up", "create_task"],
    "revenue_gap": ["follow_up_opportunities", "create_action_plan", "review_pipeline", "contact_prospects"],
    "revenue_risk": ["contact_prospects", "review_pipeline", "create_task"],
    "marketing_content": ["approve", "edit", "schedule", "review_performance"],
    "nurture_task": ["send_message", "schedule_contact", "mark_completed", "snooze"],
    "overdue_task": ["complete", "reschedule", "dismiss"],
    "decaying_lead": ["call", "text", "email", "follow_up"],
    "compliance_block": ["review", "approve", "edit"],
    "default": ["view", "snooze", "dismiss"],
}

# Human-readable labels for each action button (emoji-free)
ACTION_LABELS: Dict[str, str] = {
    "call": "Call",
    "text": "Text",
    "email": "Email",
    "follow_up": "Follow Up",
    "schedule": "Schedule",
    "view_lead": "View Lead",
    "create_task": "Create Task",
    "add_note": "Add Note",
    "request_referral": "Request Referral",
    "view_client": "View Client",
    "schedule_review": "Schedule Review",
    "contact_source": "Contact Source",
    "request_introduction": "Request Introduction",
    "follow_up_opportunities": "Follow Up Opportunities",
    "create_action_plan": "Create Action Plan",
    "review_pipeline": "Review Pipeline",
    "contact_prospects": "Contact Prospects",
    "approve": "Approve",
    "edit": "Edit",
    "review_performance": "Review Performance",
    "send_message": "Send Message",
    "schedule_contact": "Schedule Contact",
    "mark_completed": "Mark Completed",
    "snooze": "Snooze",
    "complete": "Complete",
    "reschedule": "Reschedule",
    "dismiss": "Dismiss",
    "review": "Review",
    "view": "View",
}

# External actions require an integration we do not own (dialer, SMS, email API).
EXTERNAL_ACTIONS = {
    "call", "text", "email", "send_message", "contact_source",
    "contact_prospects", "request_referral", "request_introduction",
}

# Internal actions are fully handled inside the Command Center.
INTERNAL_ACTIONS = {
    "view", "view_lead", "view_client", "snooze", "dismiss", "create_task",
    "add_note", "approve", "edit", "review", "schedule", "schedule_review",
    "schedule_contact", "mark_completed", "complete", "reschedule",
    "follow_up", "follow_up_opportunities", "create_action_plan",
    "review_pipeline", "review_performance",
}

# Actions that should trigger an AI-drafted follow-up message.
MESSAGE_ACTIONS = {
    "call", "text", "email", "follow_up", "send_message", "contact_source",
    "request_introduction", "follow_up_opportunities", "contact_prospects",
}


def _label(action_type: str) -> str:
    """Return a human-readable label for an action type."""
    return ACTION_LABELS.get(action_type, action_type.replace("_", " ").title())


# ---------------------------------------------------------------------------
# 2. get_smart_actions(entity_type)
# ---------------------------------------------------------------------------
def get_smart_actions(entity_type: str) -> List[Dict[str, Any]]:
    """Return the appropriate smart action buttons for an entity type.

    Each button is a dict: {action, label, executable, method, fallback}.
    Falls back to the default action set for unknown entity types.
    """
    etype = (entity_type or "").strip().lower()
    actions = ENTITY_ACTIONS.get(etype, ENTITY_ACTIONS["default"])
    buttons = []
    for action in actions:
        executable, method, fallback = is_action_executable(action)
        buttons.append({
            "action": action,
            "label": _label(action),
            "executable": executable,
            "method": method,
            "fallback": fallback,
        })
    return buttons


# ---------------------------------------------------------------------------
# 3. prepare_action_context(entity, entity_type, reason, value, urgency, source)
# ---------------------------------------------------------------------------
def prepare_action_context(
    entity: str,
    entity_type: str,
    reason: str,
    value: float = 0,
    urgency: str = "medium",
    source: str = "",
) -> Dict[str, Any]:
    """Prepare the full action context for a priority item.

    Returns a dict with: action, why, value, urgency, buttons,
    context_summary. All marked [SAMPLE] with DRAFT disclaimer.
    """
    etype = (entity_type or "").strip().lower()
    buttons = get_smart_actions(etype)
    # Primary action = first button
    primary = buttons[0]["action"] if buttons else "view"

    # Urgency -> human label
    urgency = (urgency or "medium").strip().lower()
    urgency_label = {
        "high": "High",
        "medium": "Medium",
        "low": "Low",
    }.get(urgency, "Medium")

    # Value formatting
    try:
        value_num = float(value or 0)
    except (TypeError, ValueError):
        value_num = 0.0
    value_str = "${:,.0f}".format(value_num) if value_num > 0 else "N/A"

    # Context summary -- one-line description for the action card
    context_summary = "{entity} ({etype}) flagged by {source}. {reason} {sample} {draft}".format(
        entity=entity or "Unknown entity",
        etype=etype or "unknown",
        source=source or "the system",
        reason=reason or "Action recommended.",
        sample=SAMPLE_TAG,
        draft=DRAFT_DISCLAIMER,
    )

    return {
        "action": primary,
        "why": reason or "Recommended by {}".format(source or "the system"),
        "value": value_num,
        "value_display": value_str,
        "urgency": urgency,
        "urgency_label": urgency_label,
        "buttons": buttons,
        "context_summary": context_summary,
        "source_system": source,
        "disclaimer": DRAFT_DISCLAIMER,
        "sample": True,
    }


# ---------------------------------------------------------------------------
# 4. draft_follow_up_message(entity, entity_type, reason, tone)
# ---------------------------------------------------------------------------
def draft_follow_up_message(
    entity: str,
    entity_type: str,
    reason: str,
    tone: str = "professional",
) -> str:
    """Draft a follow-up message for an external contact action.

    Returns a multi-line string with: greeting, reason for contact, relevant
    context, suggested next step, and closing. Marked DRAFT. Emoji-free.

    tone: professional (default), friendly, formal.
    """
    etype = (entity_type or "").strip().lower()
    tone = (tone or "professional").strip().lower()
    name = entity or "there"

    # Greeting by tone
    if tone == "friendly":
        greeting = "Hi {name},".format(name=name)
    elif tone == "formal":
        greeting = "Dear {name},".format(name=name)
    else:
        greeting = "Hello {name},".format(name=name)

    # Reason for contact -- tailored by entity type
    reason_text = reason or "I wanted to follow up with you."

    # Relevant context by entity type
    context_map = {
        "lead": "Based on your recent interest, I have a few options that may be a strong fit for your goals.",
        "new_lead": "Thank you for reaching out. I have reviewed your information and have some relevant next steps to share.",
        "decaying_lead": "It has been a little while since we last connected, and I wanted to make sure you still have what you need.",
        "at_risk_client": "I noticed we have not spoken recently and want to make sure you are getting full value from our work together.",
        "high_value_client": "I would like to schedule a review to make sure our strategy still aligns with your priorities.",
        "referral_opportunity": "I have been thinking about the introduction we discussed and wanted to share a few details.",
        "revenue_gap": "I am reaching out about a few open opportunities that could help close the current revenue gap.",
        "revenue_risk": "I wanted to flag an item in the pipeline that may need attention soon.",
        "nurture_task": "Following up as part of our ongoing outreach to keep things moving.",
        "overdue_task": "Following up on an item that is now past due.",
    }
    context = context_map.get(etype, "I have some relevant information to share with you.")

    # Suggested next step by entity type
    next_step_map = {
        "lead": "Would you have 15 minutes this week for a quick call to explore fit?",
        "new_lead": "Could we schedule a brief call this week to walk through next steps?",
        "decaying_lead": "Would a short check-in call this week work for you?",
        "at_risk_client": "Would you be open to a quick review call this week?",
        "high_value_client": "Would a 30-minute review in the next week or two work for your calendar?",
        "referral_opportunity": "Could we set up a brief introduction call at your convenience?",
        "revenue_gap": "Could we review the open opportunities together this week?",
        "revenue_risk": "Could we connect this week to discuss the pipeline item?",
        "nurture_task": "Would a quick follow-up this week be helpful?",
        "overdue_task": "Could we confirm a time to complete this item this week?",
    }
    next_step = next_step_map.get(etype, "Would a brief call this week work for you?")

    # Closing by tone
    if tone == "friendly":
        closing = "Thanks,\n[Your name]"
    elif tone == "formal":
        closing = "Sincerely,\n[Your name]"
    else:
        closing = "Best regards,\n[Your name]"

    message = (
        "{greeting}\n\n"
        "{reason}\n\n"
        "{context}\n\n"
        "{next_step}\n\n"
        "{closing}\n\n"
        "--- DRAFT -- owner approval required. {sample} ---"
    ).format(
        greeting=greeting,
        reason=reason_text,
        context=context,
        next_step=next_step,
        closing=closing,
        sample=SAMPLE_TAG,
    )
    return message


# ---------------------------------------------------------------------------
# 5. is_action_executable(action_type)
# ---------------------------------------------------------------------------
def is_action_executable(action_type: str) -> Tuple[bool, str, str]:
    """Determine whether an action can run internally or needs an integration.

    Returns (executable: bool, method: str, fallback: str).
      - External actions (call, text, email) -> (False,
        "external_integration_required", "tel:/mailto:/copy_draft")
      - Internal actions (view, snooze, dismiss, create_task, add_note,
        approve) -> (True, "internal", "")
    """
    action = (action_type or "").strip().lower()
    if action in EXTERNAL_ACTIONS:
        return (False, "external_integration_required", "tel:/mailto:/copy_draft")
    if action in INTERNAL_ACTIONS:
        return (True, "internal", "")
    # Unknown action -> treat as internal view for safety
    return (True, "internal", "")


# ---------------------------------------------------------------------------
# 6. generate_action_card(priority_item)
# ---------------------------------------------------------------------------
def generate_action_card(priority_item: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a full action card from a V2 priority item.

    Returns a dict with: entity, entity_type, reason, value, urgency, buttons
    (smart), context, ai_draft (if a follow-up/message action is present),
    and executable status.
    """
    entity = priority_item.get("entity", "")
    entity_type = priority_item.get("entity_type", "")
    reason = priority_item.get("reason", priority_item.get("explanation", ""))
    value = priority_item.get("opportunity_value", priority_item.get("value", 0)) or 0
    risk = (priority_item.get("risk", "medium") or "medium").lower()
    urgency = {"high": "high", "medium": "medium", "low": "low"}.get(risk, "medium")
    source = priority_item.get("source_system", "")

    # Smart buttons for this entity type
    buttons = get_smart_actions(entity_type)

    # Prepare context
    context = prepare_action_context(
        entity=entity,
        entity_type=entity_type,
        reason=reason,
        value=value,
        urgency=urgency,
        source=source,
    )

    # AI draft: only if a message/follow-up action is among the buttons
    ai_draft = None
    has_message_action = any(b["action"] in MESSAGE_ACTIONS for b in buttons)
    if has_message_action:
        ai_draft = draft_follow_up_message(
            entity=entity,
            entity_type=entity_type,
            reason=reason,
            tone="professional",
        )

    # Executable status of the primary action
    primary_action = context.get("action", "view")
    executable, method, fallback = is_action_executable(primary_action)

    # Priority score + explanation passthrough
    priority_score = priority_item.get("priority_score", 0) or 0
    recommended_action = priority_item.get("recommended_action", "")

    return {
        "entity": entity,
        "entity_type": entity_type,
        "reason": reason,
        "value": value,
        "value_display": context.get("value_display", "N/A"),
        "urgency": urgency,
        "urgency_label": context.get("urgency_label", "Medium"),
        "priority_score": priority_score,
        "recommended_action": recommended_action,
        "source_system": source,
        "buttons": buttons,
        "context": context,
        "context_summary": context.get("context_summary", ""),
        "ai_draft": ai_draft,
        "executable": executable,
        "method": method,
        "fallback": fallback,
        "disclaimer": DRAFT_DISCLAIMER,
        "sample": True,
    }


# ---------------------------------------------------------------------------
# CLI entry point for testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("ACTION EXECUTION ENGINE -- TEST RUN")
    print("=" * 70)

    # 1. ENTITY_ACTIONS coverage
    print("\n--- ENTITY_ACTIONS ---")
    for et, acts in ENTITY_ACTIONS.items():
        print("  {:22s} -> {}".format(et, ", ".join(acts)))

    # 2. get_smart_actions
    print("\n--- get_smart_actions('lead') ---")
    for b in get_smart_actions("lead"):
        print("  {} (executable={}, method={}, fallback={})".format(
            b["label"], b["executable"], b["method"], b["fallback"] or "-"))

    print("\n--- get_smart_actions('unknown_type') -> default ---")
    for b in get_smart_actions("unknown_type"):
        print("  {} (executable={})".format(b["label"], b["executable"]))

    # 3. prepare_action_context
    print("\n--- prepare_action_context ---")
    ctx = prepare_action_context(
        entity="John Smith", entity_type="lead",
        reason="High-value lead, 3 days since last contact",
        value=5000, urgency="high", source="Lead Scoring",
    )
    for k, v in ctx.items():
        if k == "buttons":
            print("  buttons: {}".format([b["label"] for b in v]))
        else:
            print("  {}: {}".format(k, v))

    # 4. draft_follow_up_message
    print("\n--- draft_follow_up_message (lead, professional) ---")
    msg = draft_follow_up_message("John Smith", "lead", "High-value lead", "professional")
    print(msg)

    print("\n--- draft_follow_up_message (at_risk_client, friendly) ---")
    msg2 = draft_follow_up_message("Acme Corp", "at_risk_client", "Client at risk", "friendly")
    print(msg2)

    # 5. is_action_executable
    print("\n--- is_action_executable ---")
    for a in ["call", "text", "email", "view", "snooze", "dismiss", "create_task", "add_note", "approve", "unknown_x"]:
        print("  {:14s} -> {}".format(a, is_action_executable(a)))

    # 6. generate_action_card
    print("\n--- generate_action_card ---")
    priority_item = {
        "entity": "Call John",
        "entity_type": "lead",
        "reason": "High-value lead, 3 days since last contact",
        "opportunity_value": 5000,
        "risk": "high",
        "priority_score": 85,
        "recommended_action": "Call lead within 24 hours",
        "source_system": "Lead Scoring + Executive AI",
    }
    card = generate_action_card(priority_item)
    print("  entity:", card["entity"])
    print("  entity_type:", card["entity_type"])
    print("  value_display:", card["value_display"])
    print("  urgency:", card["urgency_label"])
    print("  buttons:", [b["label"] for b in card["buttons"]])
    print("  executable:", card["executable"], "method:", card["method"])
    print("  ai_draft present:", card["ai_draft"] is not None)
    if card["ai_draft"]:
        print("  ai_draft (first 80 chars):", card["ai_draft"][:80].replace("\n", " "))

    print("\n" + "=" * 70)
    print("ACTION EXECUTION ENGINE TEST COMPLETE")
    print("=" * 70)
