"""
Pipeline B Data Bridge
======================
Canonical bridge between data.db and the Phase 7-12 intelligence engines.

Reads contacts, opportunities, revenue, referrals, tasks, and business config
from data.db and returns them in the exact shapes the phase modules expect
(matching the DEMO_* constants they previously used).

Mode rules:
  - Demo mode (is_demo_mode=1): returns is_sample=1 data, labels as "demo"
  - Real mode  (is_demo_mode=0): returns is_sample=0 data, labels as "real"
  - Empty: returns empty collections, labels as "empty"

This module does NOT fabricate data. If data.db has no rows, it returns
empty lists and the caller is responsible for showing "Not enough data yet."
"""

import sqlite3
import os
import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")

# Use db.py abstraction when DATABASE_URL is set (Postgres), fall back to SQLite
import db as _dbmod
_PG = _dbmod.DB_TYPE == "postgres"

def _get_conn():
    if _PG:
        return _dbmod.get_conn()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _return_conn(conn):
    if _PG:
        _dbmod.return_conn(conn)
    else:
        _return_conn(conn)


def is_demo_mode() -> bool:
    """Check if demo mode is currently active."""
    try:
        conn = _get_conn()
        # Try Postgres schema
        try:
            row = conn.execute("SELECT business_id FROM demo_state WHERE business_id IS NOT NULL LIMIT 1").fetchone()
            _return_conn(conn)
            return bool(row and row[0])
        except Exception:
            pass
        # Fall back to SQLite schema
        row = conn.execute("SELECT is_demo_mode FROM demo_state WHERE id = 1").fetchone()
        _return_conn(conn)
        return bool(row[0]) if row else False
    except Exception:
        return False


def get_data_source_label() -> str:
    """Return 'demo', 'real', or 'empty' based on current state."""
    if is_demo_mode():
        has = has_data(is_sample=1)
    else:
        has = has_data(is_sample=0)
    if not has:
        return "empty"
    return "demo" if is_demo_mode() else "real"


def has_data(is_sample: int = 0) -> bool:
    """Check if any data exists for the given is_sample flag."""
    try:
        conn = _get_conn()
        count = conn.execute(
            "SELECT COUNT(*) FROM contacts WHERE is_sample = ?", (is_sample,)
        ).fetchone()[0]
        _return_conn(conn)
        return count > 0
    except Exception:
        return False


def _sample_filter() -> str:
    """Return SQL WHERE clause for is_sample based on demo mode."""
    return "is_sample = 1" if is_demo_mode() else "is_sample = 0"


def get_contacts() -> List[Dict[str, Any]]:
    """Return contacts from data.db matching the DEMO_CONTACTS shape."""
    conn = _get_conn()
    filt = _sample_filter()
    rows = conn.execute(
        f"""SELECT contact_id, first_name, last_name, email, phone, contact_type,
                  pipeline_stage, lead_source, medicare_status, state, zip_code,
                  date_of_birth, client_since, last_activity, tags,
                  call_consent, sms_consent, email_consent
           FROM contacts WHERE {filt}"""
    ).fetchall()
    _return_conn(conn)
    contacts = []
    for r in rows:
        c = dict(r)
        # Parse tags from JSON string if needed
        if isinstance(c.get("tags"), str):
            try:
                c["tags"] = json.loads(c["tags"])
            except (json.JSONDecodeError, TypeError):
                c["tags"] = []
        elif c.get("tags") is None:
            c["tags"] = []
        # Ensure all expected fields exist
        c.setdefault("is_real_data", not is_demo_mode())
        contacts.append(c)
    return contacts


def get_opportunities() -> List[Dict[str, Any]]:
    """Return opportunities from data.db matching the DEMO_OPPORTUNITIES shape."""
    conn = _get_conn()
    filt = _sample_filter()
    rows = conn.execute(
        f"""SELECT opp_id, contact_id, product_type, stage, estimated_value,
                  expected_close, created_date, entered_stage, stage_history
           FROM opportunities WHERE {filt}"""
    ).fetchall()
    _return_conn(conn)
    opps = []
    for r in rows:
        o = dict(r)
        # Parse stage_history from JSON string if needed
        if isinstance(o.get("stage_history"), str):
            try:
                o["stage_history"] = json.loads(o["stage_history"])
            except (json.JSONDecodeError, TypeError):
                o["stage_history"] = []
        elif o.get("stage_history") is None:
            o["stage_history"] = []
        o.setdefault("is_real_data", not is_demo_mode())
        opps.append(o)
    return opps


def get_revenue_records() -> List[Dict[str, Any]]:
    """Return revenue records from data.db."""
    conn = _get_conn()
    filt = _sample_filter()
    rows = conn.execute(
        f"""SELECT record_id, contact_id, product_type, amount, revenue_date,
                  revenue_category, payment_status, source
           FROM revenue_records WHERE {filt}"""
    ).fetchall()
    _return_conn(conn)
    return [dict(r) for r in rows]


def get_referral_sources() -> List[Dict[str, Any]]:
    """Return referral sources from data.db."""
    conn = _get_conn()
    filt = _sample_filter()
    rows = conn.execute(
        f"""SELECT source_id, source_name, source_type, contact_info,
                  relationship_strength, referrals_generated, referrals_converted,
                  conversion_rate, total_revenue_generated, last_referral_date, status
           FROM referral_sources WHERE {filt}"""
    ).fetchall()
    _return_conn(conn)
    return [dict(r) for r in rows]


def get_tasks() -> List[Dict[str, Any]]:
    """Return tasks from data.db actions table, mapped to DEMO_TASKS shape."""
    conn = _get_conn()
    filt = _sample_filter() if is_demo_mode() else "1=1"
    # Actions don't have is_sample column — return all when in real mode
    try:
        rows = conn.execute(
            f"""SELECT action_id as task_id, entity_id as contact_id, title,
                      priority, status, due_date, created_date, source_module as assigned_to
               FROM actions WHERE status IN ('pending', 'in_progress', 'open')
               ORDER BY due_date IS NULL, due_date ASC"""
        ).fetchall()
    except Exception:
        rows = []
    _return_conn(conn)
    tasks = []
    for r in rows:
        t = dict(r)
        t.setdefault("task_id", "")
        t.setdefault("contact_id", "")
        t.setdefault("title", "")
        t.setdefault("priority", "medium")
        t.setdefault("status", "open")
        t.setdefault("due_date", None)
        t.setdefault("created_date", None)
        t.setdefault("assigned_to", "system")
        tasks.append(t)
    return tasks


def get_appointments() -> List[Dict[str, Any]]:
    """Return appointments from data.db actions table."""
    # Actions table doesn't have appointment-specific fields
    # Return empty for now — appointments are tracked via actions with action_type='appointment'
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT action_id as appt_id, entity_id as contact_id, title,
                      due_date as scheduled_date, status, actual_outcome as outcome
               FROM actions WHERE action_type = 'appointment'
               ORDER BY due_date IS NULL, due_date ASC"""
        ).fetchall()
    except Exception:
        rows = []
    _return_conn(conn)
    appts = []
    for r in rows:
        a = dict(r)
        a.setdefault("follow_up_task_created", False)
        appts.append(a)
    return appts


def get_business_config() -> Dict[str, Any]:
    """Return business config from data.db."""
    conn = _get_conn()
    try:
        row = conn.execute(
            """SELECT business_name, industry, primary_objective, revenue_goal,
                      goal_period, avg_transaction_value, current_revenue,
                      reporting_period, setup_complete
               FROM business_config WHERE id = 1"""
        ).fetchone()
    except Exception:
        row = None
    _return_conn(conn)
    if not row:
        return {
            "business_name": "",
            "industry": "",
            "primary_objective": "",
            "revenue_goal": 0,
            "goal_period": "monthly",
            "avg_transaction_value": 0,
            "current_revenue": 0,
            "reporting_period": "monthly",
            "setup_complete": 0,
        }
    return dict(row)


def get_today() -> date:
    """Return today's date (dynamic, not frozen)."""
    return date.today()


def get_source_metadata() -> Dict[str, Any]:
    """Return metadata about the data source for transparency."""
    label = get_data_source_label()
    demo = is_demo_mode()
    return {
        "data_source": label,
        "is_demo_mode": demo,
        "as_of": datetime.now().isoformat(),
        "source_db": DB_PATH,
        "sample_filter": _sample_filter(),
        "contacts_count": len(get_contacts()),
        "opportunities_count": len(get_opportunities()),
        "revenue_records_count": len(get_revenue_records()),
        "referral_sources_count": len(get_referral_sources()),
        "insufficient_data": label == "empty",
        "insufficient_data_reason": "No data in database. Import contacts and revenue to get started." if label == "empty" else None,
    }
