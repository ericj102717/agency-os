#!/usr/bin/env python3
"""
Data Store
=========
SQLite-backed storage layer for real business data.
Replaces hardcoded Python demo constants with a real database.

Tables:
  - contacts (leads, clients, prospects)
  - opportunities (pipeline deals)
  - revenue_records (closed revenue)
  - referral_sources (referral partners)
  - import_batches (import audit trail)
  - import_issues (per-row validation errors/warnings)

All data marked [SAMPLE] when imported from demo files.
DRAFT -- owner approval required.
"""

import json
import os
import re
import hashlib
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

# Use db.py abstraction (Postgres when DATABASE_URL is set, SQLite fallback)
try:
    import db as _db
    DB_TYPE = _db.DB_TYPE
except ImportError:
    _db = None
    DB_TYPE = "sqlite"

import sqlite3 as _sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")
DRAFT_DISCLAIMER = "DRAFT -- owner approval required."
SAMPLE_PREFIX = "[SAMPLE]"

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id TEXT UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT DEFAULT '',
    email TEXT DEFAULT '',
    normalized_email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    normalized_phone TEXT DEFAULT '',
    date_of_birth TEXT,
    contact_type TEXT NOT NULL DEFAULT 'lead',
    lead_source TEXT DEFAULT '',
    pipeline_stage TEXT DEFAULT 'new',
    medicare_status TEXT DEFAULT '',
    email_consent INTEGER DEFAULT 0,
    sms_consent INTEGER DEFAULT 0,
    call_consent INTEGER DEFAULT 0,
    last_activity TEXT,
    client_since TEXT,
    zip_code TEXT DEFAULT '',
    state TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    is_sample INTEGER DEFAULT 0,
    import_batch_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opp_id TEXT UNIQUE,
    contact_id TEXT,
    product_type TEXT DEFAULT '',
    stage TEXT NOT NULL DEFAULT 'new',
    entered_stage TEXT,
    expected_close TEXT,
    estimated_value REAL DEFAULT 0,
    created_date TEXT,
    stage_history TEXT DEFAULT '[]',
    is_sample INTEGER DEFAULT 0,
    import_batch_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS revenue_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id TEXT UNIQUE,
    contact_id TEXT,
    product_type TEXT DEFAULT '',
    amount REAL NOT NULL DEFAULT 0,
    revenue_date TEXT,
    revenue_category TEXT DEFAULT 'commission',
    payment_status TEXT DEFAULT 'received',
    source TEXT DEFAULT '',
    is_sample INTEGER DEFAULT 0,
    import_batch_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS referral_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT UNIQUE,
    source_name TEXT NOT NULL,
    source_type TEXT DEFAULT 'client',
    contact_info TEXT DEFAULT '',
    relationship_strength INTEGER DEFAULT 50,
    referrals_generated INTEGER DEFAULT 0,
    referrals_converted INTEGER DEFAULT 0,
    conversion_rate REAL DEFAULT 0,
    total_revenue_generated REAL DEFAULT 0,
    last_referral_date TEXT,
    status TEXT DEFAULT 'active',
    is_sample INTEGER DEFAULT 0,
    import_batch_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS import_batches (
    batch_id TEXT PRIMARY KEY,
    data_type TEXT NOT NULL,
    filename TEXT,
    total_rows INTEGER DEFAULT 0,
    valid_rows INTEGER DEFAULT 0,
    invalid_rows INTEGER DEFAULT 0,
    duplicate_rows INTEGER DEFAULT 0,
    imported_rows INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    field_mapping TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS import_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT,
    row_number INTEGER,
    field_name TEXT,
    issue_type TEXT,
    message TEXT,
    row_data TEXT
);

CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(normalized_email);
CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(normalized_phone);
CREATE INDEX IF NOT EXISTS idx_contacts_type ON contacts(contact_type);
CREATE INDEX IF NOT EXISTS idx_opp_contact ON opportunities(contact_id);
CREATE INDEX IF NOT EXISTS idx_rev_contact ON revenue_records(contact_id);
CREATE INDEX IF NOT EXISTS idx_issues_batch ON import_issues(batch_id);

-- Business configuration (single source of truth)
CREATE TABLE IF NOT EXISTS business_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    business_name TEXT DEFAULT '',
    industry TEXT DEFAULT '',
    primary_objective TEXT DEFAULT '',
    revenue_goal REAL DEFAULT 0,
    goal_period TEXT DEFAULT 'monthly',
    avg_transaction_value REAL DEFAULT 0,
    current_revenue REAL DEFAULT 0,
    reporting_period TEXT DEFAULT 'monthly',
    setup_complete INTEGER DEFAULT 0,
    setup_completed_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    avg_price REAL DEFAULT 0,
    category TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lead_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sales_stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    label TEXT DEFAULT '',
    probability REAL DEFAULT 0,
    sort_order INTEGER DEFAULT 0,
    is_closed INTEGER DEFAULT 0,
    is_won INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id TEXT UNIQUE,
    entity_type TEXT DEFAULT '',
    entity_id TEXT DEFAULT '',
    entity_name TEXT DEFAULT '',
    action_type TEXT NOT NULL,
    title TEXT DEFAULT '',
    description TEXT DEFAULT '',
    priority INTEGER DEFAULT 5,
    due_date TEXT,
    status TEXT DEFAULT 'pending',
    completed_date TEXT,
    expected_value REAL DEFAULT 0,
    actual_outcome TEXT DEFAULT '',
    recommendation_id TEXT,
    source_module TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rec_id TEXT UNIQUE,
    entity_type TEXT DEFAULT '',
    entity_id TEXT DEFAULT '',
    rec_type TEXT NOT NULL,
    title TEXT DEFAULT '',
    description TEXT DEFAULT '',
    priority INTEGER DEFAULT 5,
    expected_impact TEXT DEFAULT '',
    ignore_consequence TEXT DEFAULT '',
    next_step TEXT DEFAULT '',
    explanation_data TEXT DEFAULT '{}',
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS recommendation_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rec_id TEXT NOT NULL,
    user_action TEXT DEFAULT '',
    completed INTEGER DEFAULT 0,
    outcome TEXT DEFAULT '',
    revenue_generated REAL DEFAULT 0,
    conversion_result TEXT DEFAULT '',
    time_to_complete_hours REAL DEFAULT 0,
    feedback_notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS business_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id TEXT UNIQUE,
    entity_type TEXT DEFAULT '',
    entity_id TEXT DEFAULT '',
    entity_name TEXT DEFAULT '',
    memory_text TEXT NOT NULL,
    memory_category TEXT DEFAULT 'general',
    relevance_score INTEGER DEFAULT 50,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status);
CREATE INDEX IF NOT EXISTS idx_actions_entity ON actions(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_actions_priority ON actions(priority);
CREATE INDEX IF NOT EXISTS idx_recs_status ON recommendations(status);
CREATE INDEX IF NOT EXISTS idx_recs_entity ON recommendations(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_feedback_rec ON recommendation_feedback(rec_id);
CREATE INDEX IF NOT EXISTS idx_memory_entity ON business_memory(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_services_active ON services(is_active);
CREATE INDEX IF NOT EXISTS idx_lead_sources_active ON lead_sources(is_active);
CREATE INDEX IF NOT EXISTS idx_sales_stages_order ON sales_stages(sort_order);
"""

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

_conn = None

def get_conn():
    """Get a database connection (Postgres or SQLite)."""
    if _db and _db.DB_TYPE == "postgres":
        return _db.get_conn()
    # SQLite path
    global _conn
    if _conn is None:
        _conn = _sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = _sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
    return _conn

def return_conn(conn):
    """Return a connection to the pool (Postgres) or no-op (SQLite)."""
    if _db and _db.DB_TYPE == "postgres":
        _db.return_conn(conn)
        return
    # SQLite uses a single shared connection — no-op
    pass

def init_db():
    """Initialize the database schema."""
    if _db and _db.DB_TYPE == "postgres":
        _db.init_db()
        return
    conn = get_conn()
    conn.executescript(SCHEMA_SQL)
    conn.commit()

# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def normalize_email(email: str) -> str:
    if not email:
        return ""
    return re.sub(r'\s+', '', email.strip().lower())

def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    return re.sub(r'[^0-9]', '', phone)

def sample_prefix(name: str) -> str:
    if not name:
        return name
    name = name.strip()
    if name.startswith(SAMPLE_PREFIX):
        return name
    return f"{SAMPLE_PREFIX} {name}"

# ---------------------------------------------------------------------------
# Contacts CRUD
# ---------------------------------------------------------------------------

def insert_contact(row: Dict[str, Any], batch_id: str = "", is_sample: bool = False) -> Tuple[bool, Optional[str]]:
    """Insert a contact. Returns (success, error_message)."""
    conn = get_conn()
    try:
        first_name = row.get("first_name", "").strip()
        last_name = row.get("last_name", "").strip()
        email = row.get("email", "").strip()
        phone = row.get("phone", "").strip()
        contact_type = row.get("contact_type", "lead").strip().lower()
        contact_id = row.get("contact_id", "") or f"CNT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{conn.execute('SELECT COALESCE(MAX(id),0)+1 FROM contacts').fetchone()[0]}"

        conn.execute("""
            INSERT INTO contacts (
                contact_id, first_name, last_name, email, normalized_email,
                phone, normalized_phone, date_of_birth, contact_type, lead_source,
                pipeline_stage, medicare_status, email_consent, sms_consent, call_consent,
                last_activity, client_since, zip_code, state, tags, notes, is_sample, import_batch_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            contact_id, first_name, last_name, email, normalize_email(email),
            phone, normalize_phone(phone), row.get("date_of_birth"),
            contact_type, row.get("lead_source", ""), row.get("pipeline_stage", "new"),
            row.get("medicare_status", ""),
            int(bool(row.get("email_consent", False))),
            int(bool(row.get("sms_consent", False))),
            int(bool(row.get("call_consent", False))),
            row.get("last_activity"), row.get("client_since"),
            row.get("zip_code", ""), row.get("state", ""),
            row.get("tags", ""), row.get("notes", ""),
            int(is_sample), batch_id
        ))
        conn.commit()
        return True, None
    except (_sqlite3.IntegrityError if DB_TYPE == "sqlite" else Exception) as e:
        return False, f"Duplicate contact_id: {contact_id}"
    except Exception as e:
        return False, str(e)

def check_contact_duplicate(row: Dict[str, Any], exclude_id: int = None) -> Optional[Dict[str, Any]]:
    """Check if a contact already exists. Returns the existing contact or None."""
    conn = get_conn()
    email = normalize_email(row.get("email", ""))
    phone = normalize_phone(row.get("phone", ""))
    contact_id = row.get("contact_id", "")

    if contact_id:
        existing = conn.execute("SELECT * FROM contacts WHERE contact_id = ?", (contact_id,)).fetchone()
        if existing:
            return dict(existing)

    if email:
        existing = conn.execute("SELECT * FROM contacts WHERE normalized_email = ?", (email,)).fetchone()
        if existing:
            return dict(existing)

    if phone and len(phone) >= 10:
        existing = conn.execute("SELECT * FROM contacts WHERE normalized_phone = ?", (phone,)).fetchone()
        if existing:
            return dict(existing)

    return None

def get_contacts(contact_type: str = None, include_all: bool = False) -> List[Dict[str, Any]]:
    """Get contacts, filtered by demo mode unless include_all=True."""
    conn = get_conn()
    conn.commit()  # End active read transaction to see latest writes
    # Determine is_sample filter based on demo mode
    if include_all:
        sample_filter = ""
        params = ()
    else:
        is_demo = _is_demo_mode()
        sample_filter = " WHERE is_sample = ?"
        params = (1 if is_demo else 0,)
    
    if contact_type:
        if sample_filter:
            sample_filter += " AND contact_type = ?"
            params = params + (contact_type,)
        else:
            sample_filter = " WHERE contact_type = ?"
            params = (contact_type,)
    
    rows = conn.execute(f"SELECT * FROM contacts{sample_filter} ORDER BY id", params).fetchall()
    return [dict(r) for r in rows]

def get_contact_count() -> int:
    conn = get_conn()
    return conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]

# ---------------------------------------------------------------------------
# Opportunities CRUD
# ---------------------------------------------------------------------------

def insert_opportunity(row: Dict[str, Any], batch_id: str = "", is_sample: bool = False) -> Tuple[bool, Optional[str]]:
    conn = get_conn()
    try:
        opp_id = row.get("opp_id", "") or f"OPP-{datetime.now().strftime('%Y%m%d%H%M%S')}-{conn.execute('SELECT COALESCE(MAX(id),0)+1 FROM opportunities').fetchone()[0]}"
        stage_history = row.get("stage_history", "[]")
        if isinstance(stage_history, list):
            stage_history = json.dumps(stage_history)

        conn.execute("""
            INSERT INTO opportunities (
                opp_id, contact_id, product_type, stage, entered_stage,
                expected_close, estimated_value, created_date, stage_history, is_sample, import_batch_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            opp_id, row.get("contact_id", ""), row.get("product_type", ""),
            row.get("stage", "new"), row.get("entered_stage"),
            row.get("expected_close"), float(row.get("estimated_value", 0)),
            row.get("created_date"), stage_history, int(is_sample), batch_id
        ))
        conn.commit()
        return True, None
    except (_sqlite3.IntegrityError if DB_TYPE == "sqlite" else Exception):
        return False, f"Duplicate opp_id"
    except Exception as e:
        return False, str(e)

def check_opp_duplicate(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    opp_id = row.get("opp_id", "")
    if opp_id:
        existing = conn.execute("SELECT * FROM opportunities WHERE opp_id = ?", (opp_id,)).fetchone()
        if existing:
            return dict(existing)
    return None

def get_opportunities() -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM opportunities ORDER BY id").fetchall()
    return [dict(r) for r in rows]

def get_opp_count() -> int:
    conn = get_conn()
    return conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]

# ---------------------------------------------------------------------------
# Revenue Records CRUD
# ---------------------------------------------------------------------------

def insert_revenue(row: Dict[str, Any], batch_id: str = "", is_sample: bool = False) -> Tuple[bool, Optional[str]]:
    conn = get_conn()
    try:
        record_id = row.get("record_id", "") or f"REV-{datetime.now().strftime('%Y%m%d%H%M%S')}-{conn.execute('SELECT COALESCE(MAX(id),0)+1 FROM revenue_records').fetchone()[0]}"
        conn.execute("""
            INSERT INTO revenue_records (
                record_id, contact_id, product_type, amount, revenue_date,
                revenue_category, payment_status, source, is_sample, import_batch_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record_id, row.get("contact_id", ""), row.get("product_type", ""),
            float(row.get("amount", 0)), row.get("revenue_date"),
            row.get("revenue_category", "commission"), row.get("payment_status", "received"),
            row.get("source", ""), int(is_sample), batch_id
        ))
        conn.commit()
        return True, None
    except (_sqlite3.IntegrityError if DB_TYPE == "sqlite" else Exception):
        return False, f"Duplicate record_id"
    except Exception as e:
        return False, str(e)

def get_revenue_records() -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM revenue_records ORDER BY id").fetchall()
    return [dict(r) for r in rows]

def get_revenue_count() -> int:
    conn = get_conn()
    return conn.execute("SELECT COUNT(*) FROM revenue_records").fetchone()[0]

# ---------------------------------------------------------------------------
# Referral Sources CRUD
# ---------------------------------------------------------------------------

def insert_referral_source(row: Dict[str, Any], batch_id: str = "", is_sample: bool = False) -> Tuple[bool, Optional[str]]:
    conn = get_conn()
    try:
        source_id = row.get("source_id", "") or f"REF-{datetime.now().strftime('%Y%m%d%H%M%S')}-{conn.execute('SELECT COALESCE(MAX(id),0)+1 FROM referral_sources').fetchone()[0]}"
        conn.execute("""
            INSERT INTO referral_sources (
                source_id, source_name, source_type, contact_info,
                relationship_strength, referrals_generated, referrals_converted,
                conversion_rate, total_revenue_generated, last_referral_date,
                status, is_sample, import_batch_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            source_id, row.get("source_name", ""), row.get("source_type", "client"),
            row.get("contact_info", ""), int(row.get("relationship_strength", 50)),
            int(row.get("referrals_generated", 0)), int(row.get("referrals_converted", 0)),
            float(row.get("conversion_rate", 0)), float(row.get("total_revenue_generated", 0)),
            row.get("last_referral_date"), row.get("status", "active"),
            int(is_sample), batch_id
        ))
        conn.commit()
        return True, None
    except (_sqlite3.IntegrityError if DB_TYPE == "sqlite" else Exception):
        return False, f"Duplicate source_id"
    except Exception as e:
        return False, str(e)

def get_referral_sources() -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM referral_sources ORDER BY id").fetchall()
    return [dict(r) for r in rows]

def get_referral_count() -> int:
    conn = get_conn()
    return conn.execute("SELECT COUNT(*) FROM referral_sources").fetchone()[0]

# ---------------------------------------------------------------------------
# Import Batch tracking
# ---------------------------------------------------------------------------

def create_batch(batch_id: str, data_type: str, filename: str, total_rows: int, field_mapping: dict) -> Dict[str, Any]:
    conn = get_conn()
    conn.execute("""
        INSERT INTO import_batches (batch_id, data_type, filename, total_rows, field_mapping, status)
        VALUES (?, ?, ?, ?, ?, 'in_progress')
    """, (batch_id, data_type, filename, total_rows, json.dumps(field_mapping)))
    conn.commit()
    return {"batch_id": batch_id, "status": "in_progress"}

def update_batch(batch_id: str, **kwargs):
    conn = get_conn()
    sets = []
    vals = []
    for k, v in kwargs.items():
        if k == "status" and v == "completed":
            sets.append("completed_at = datetime('now')")
        sets.append(f"{k} = ?")
        vals.append(v)
    vals.append(batch_id)
    conn.execute(f"UPDATE import_batches SET {', '.join(sets)} WHERE batch_id = ?", vals)
    conn.commit()

def get_batch(batch_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM import_batches WHERE batch_id = ?", (batch_id,)).fetchone()
    return dict(row) if row else None

def add_issue(batch_id: str, row_number: int, field_name: str, issue_type: str, message: str, row_data: str = ""):
    conn = get_conn()
    conn.execute("""
        INSERT INTO import_issues (batch_id, row_number, field_name, issue_type, message, row_data)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (batch_id, row_number, field_name, issue_type, message, row_data))
    conn.commit()

def get_issues(batch_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM import_issues WHERE batch_id = ? ORDER BY row_number LIMIT ?", (batch_id, limit)
    ).fetchall()
    return [dict(r) for r in rows]

# ---------------------------------------------------------------------------
# Data availability checks
# ---------------------------------------------------------------------------

def _is_demo_mode() -> bool:
    """Check if demo mode is currently active."""
    try:
        conn = get_conn()
        # Try Postgres schema (business_id, scenario_id, state_json)
        try:
            row = conn.execute("SELECT business_id FROM demo_state WHERE business_id IS NOT NULL LIMIT 1").fetchone()
            if row:
                return bool(row[0])
            return False
        except Exception:
            pass
        # Fall back to SQLite schema (id, is_demo_mode, business_id, scenario_id)
        row = conn.execute("SELECT is_demo_mode FROM demo_state WHERE id = 1").fetchone()
        return bool(row[0]) if row else False
    except Exception:
        return False

def has_real_contacts() -> bool:
    """Check for usable contacts — real data OR demo data when demo mode is active."""
    conn = get_conn()
    conn.commit()  # See latest writes
    if _is_demo_mode():
        return conn.execute("SELECT COUNT(*) FROM contacts WHERE is_sample = 1").fetchone()[0] > 0
    return conn.execute("SELECT COUNT(*) FROM contacts WHERE is_sample = 0").fetchone()[0] > 0

def has_real_opportunities() -> bool:
    """Check for usable opportunities — real data OR demo data when demo mode is active."""
    conn = get_conn()
    conn.commit()
    if _is_demo_mode():
        return conn.execute("SELECT COUNT(*) FROM opportunities WHERE is_sample = 1").fetchone()[0] > 0
    return conn.execute("SELECT COUNT(*) FROM opportunities WHERE is_sample = 0").fetchone()[0] > 0

def has_real_revenue() -> bool:
    """Check for usable revenue records — real data OR demo data when demo mode is active."""
    conn = get_conn()
    conn.commit()
    if _is_demo_mode():
        return conn.execute("SELECT COUNT(*) FROM revenue_records WHERE is_sample = 1").fetchone()[0] > 0
    return conn.execute("SELECT COUNT(*) FROM revenue_records WHERE is_sample = 0").fetchone()[0] > 0

def has_real_referrals() -> bool:
    """Check for usable referral sources — real data OR demo data when demo mode is active."""
    conn = get_conn()
    if _is_demo_mode():
        return conn.execute("SELECT COUNT(*) FROM referral_sources WHERE is_sample = 1").fetchone()[0] > 0
    return conn.execute("SELECT COUNT(*) FROM referral_sources WHERE is_sample = 0").fetchone()[0] > 0

def get_data_summary() -> Dict[str, Any]:
    return {
        "contacts": get_contact_count(),
        "opportunities": get_opp_count(),
        "revenue_records": get_revenue_count(),
        "referral_sources": get_referral_count(),
        "has_real_data": any([has_real_contacts(), has_real_opportunities(), has_real_revenue(), has_real_referrals()]),
    }

# ---------------------------------------------------------------------------
# Initialize on import
# ---------------------------------------------------------------------------

init_db()
