#!/usr/bin/env python3
"""
Business Data Adapter
=====================
Bridge layer that reads from SQLite (real imported data) when available,
falls back to demo data (DEMO_CONTACTS, DEMO_OPPORTUNITIES) when empty.

This allows the Command Center to seamlessly switch from demo data to
real data once the user imports their CSV files.

DRAFT -- owner approval required.
"""

import sys
import os
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import data_store

# Demo data imports (fallback)
try:
    sys.path.insert(0, "/home/user/workspace/phase6")
    from crm_data_quality_auditor import DEMO_CONTACTS
    _demo_contacts_available = True
except Exception:
    _demo_contacts_available = False
    DEMO_CONTACTS = []

try:
    from pipeline_analytics import DEMO_OPPORTUNITIES
    _demo_opps_available = True
except Exception:
    _demo_opps_available = False
    DEMO_OPPORTUNITIES = []

SAMPLE_PREFIX = "[SAMPLE]"

def _sample_prefix(name: str) -> str:
    if not name:
        return name
    name = name.strip()
    if name.startswith(SAMPLE_PREFIX):
        return name
    return f"{SAMPLE_PREFIX} {name}"


def get_contacts() -> List[Dict[str, Any]]:
    """Get contacts from SQLite if available, otherwise demo data."""
    if data_store.has_real_contacts():
        db_contacts = data_store.get_contacts()
        # Convert DB rows to the same format as DEMO_CONTACTS
        result = []
        for c in db_contacts:
            result.append({
                "contact_id": c.get("contact_id", ""),
                "first_name": c.get("first_name", ""),
                "last_name": c.get("last_name", ""),
                "email": c.get("email", ""),
                "phone": c.get("phone", ""),
                "date_of_birth": c.get("date_of_birth"),
                "contact_type": c.get("contact_type", "lead"),
                "lead_source": c.get("lead_source", ""),
                "pipeline_stage": c.get("pipeline_stage", "new"),
                "medicare_status": c.get("medicare_status", ""),
                "email_consent": bool(c.get("email_consent", 0)),
                "sms_consent": bool(c.get("sms_consent", 0)),
                "call_consent": bool(c.get("call_consent", 0)),
                "last_activity": c.get("last_activity"),
                "client_since": c.get("client_since"),
                "zip_code": c.get("zip_code", ""),
                "state": c.get("state", ""),
                "tags": c.get("tags", ""),
                "is_real_data": True,
            })
        return result
    elif _demo_contacts_available:
        # Return demo data with [SAMPLE] prefix
        result = []
        for c in DEMO_CONTACTS:
            contact = dict(c)
            contact["first_name"] = _sample_prefix(contact.get("first_name", ""))
            contact["is_real_data"] = False
            result.append(contact)
        return result
    return []


def get_opportunities() -> List[Dict[str, Any]]:
    """Get opportunities from SQLite if available, otherwise demo data."""
    if data_store.has_real_opportunities():
        db_opps = data_store.get_opportunities()
        result = []
        for o in db_opps:
            import json
            stage_history = o.get("stage_history", "[]")
            if isinstance(stage_history, str):
                try:
                    stage_history = json.loads(stage_history)
                except Exception:
                    stage_history = []
            result.append({
                "opp_id": o.get("opp_id", ""),
                "contact_id": o.get("contact_id", ""),
                "product_type": o.get("product_type", ""),
                "stage": o.get("stage", "new"),
                "entered_stage": o.get("entered_stage"),
                "expected_close": o.get("expected_close"),
                "estimated_value": o.get("estimated_value", 0),
                "created_date": o.get("created_date"),
                "stage_history": stage_history,
                "is_real_data": True,
            })
        return result
    elif _demo_opps_available:
        result = []
        for o in DEMO_OPPORTUNITIES:
            opp = dict(o)
            opp["is_real_data"] = False
            result.append(opp)
        return result
    return []


def get_revenue_records() -> List[Dict[str, Any]]:
    """Get revenue records from SQLite if available."""
    if data_store.has_real_revenue():
        return data_store.get_revenue_records()
    return []


def get_referral_sources() -> List[Dict[str, Any]]:
    """Get referral sources from SQLite if available."""
    if data_store.has_real_referrals():
        return data_store.get_referral_sources()
    return []


def get_data_source_info() -> Dict[str, Any]:
    """Return info about which data source is active (real vs demo)."""
    summary = data_store.get_data_summary()
    return {
        "using_real_data": summary["has_real_data"],
        "contacts_source": "real" if summary["contacts"] > 0 else "demo",
        "opportunities_source": "real" if summary["opportunities"] > 0 else "demo",
        "revenue_source": "real" if summary["revenue_records"] > 0 else "demo",
        "referrals_source": "real" if summary["referral_sources"] > 0 else "demo",
        "data_summary": summary,
    }


def compute_kpis() -> Dict[str, Any]:
    """
    Compute dashboard KPIs from imported data when available.
    Falls back to demo values when no real data exists.
    """
    from datetime import date, datetime
    today = date(2026, 8, 17)

    contacts = get_contacts()
    opportunities = get_opportunities()
    revenue_records = get_revenue_records()
    referral_sources = get_referral_sources()

    has_real = data_store.has_real_contacts() or data_store.has_real_opportunities() or data_store.has_real_revenue()
    _demo_mode = data_store._is_demo_mode()

    if not has_real:
        # Return zeros when no data exists — never fabricate values
        return {
            "revenue_mtd": 0,
            "revenue_forecast": 0,
            "pipeline_value": 0,
            "new_leads": 0,
            "conversion_rate": 0,
            "active_clients": 0,
            "client_lifetime_value": 0,
            "referral_opportunities": 0,
            "revenue_goal": 0,
            "data_source": "empty",
        }

    # Compute from real data
    # Active clients = contacts with contact_type == 'client'
    active_clients = len([c for c in contacts if c.get("contact_type") == "client"])

    # New leads = contacts with pipeline_stage == 'new'
    new_leads = len([c for c in contacts if c.get("pipeline_stage") == "new"])

    # Pipeline value = sum of estimated_value for non-closed opportunities
    active_opps = [o for o in opportunities if o.get("stage") not in ("closed_won", "closed_lost")]
    pipeline_value = sum(float(o.get("estimated_value", 0) or 0) for o in active_opps)

    # Revenue MTD = sum of revenue in current month
    revenue_mtd = 0
    for r in revenue_records:
        rev_date = r.get("revenue_date", "")
        if rev_date and str(today.year) in str(rev_date) and str(today.month).zfill(2) in str(rev_date)[:7]:
            revenue_mtd += float(r.get("amount", 0) or 0)
    # If no revenue records, estimate from won opportunities
    if revenue_mtd == 0 and opportunities:
        won_value = sum(float(o.get("estimated_value", 0) or 0) for o in opportunities if o.get("stage") == "closed_won")
        revenue_mtd = won_value

    # Revenue forecast = pipeline_value * historical close_rate / 100
    won_count = len([o for o in opportunities if o.get("stage") == "closed_won"])
    total_closed = won_count + len([o for o in opportunities if o.get("stage") == "closed_lost"])
    close_rate = int((won_count / total_closed * 100) if total_closed > 0 else 0)
    revenue_forecast = int(pipeline_value * close_rate / 100)

    # CLV = total revenue / active_clients (if revenue exists)
    total_revenue = sum(float(r.get("amount", 0) or 0) for r in revenue_records)
    clv = int(total_revenue / active_clients) if active_clients > 0 and total_revenue > 0 else 0

    # Referral opportunities = count of referral sources with status 'active'
    referral_opps = len([r for r in referral_sources if r.get("status") == "active"]) if referral_sources else 0

    # Get revenue_goal from business_config
    revenue_goal = 0
    try:
        config = data_store.get_business_config()
        revenue_goal = float(config.get("revenue_goal", 0) or 0)
    except Exception:
        pass

    return {
        "revenue_mtd": revenue_mtd,
        "revenue_forecast": revenue_forecast,
        "pipeline_value": int(pipeline_value),
        "new_leads": new_leads,
        "conversion_rate": close_rate,
        "active_clients": active_clients,
        "client_lifetime_value": clv,
        "referral_opportunities": referral_opps,
        "revenue_goal": revenue_goal,
        "data_source": "demo" if _demo_mode else "real",
        "contacts_count": len(contacts),
        "opportunities_count": len(opportunities),
        "revenue_records_count": len(revenue_records),
        "referral_sources_count": len(referral_sources),
    }
