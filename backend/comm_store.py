#!/usr/bin/env python3
"""
Communication & Calendar Store
================================
Tracks all client communications (calls, texts, emails, notes)
and manages the in-app Mission Control calendar.

Tables:
  - client_communications: log of all interactions with contacts
  - mission_calendar_events: appointments, follow-ups, meetings
"""

import json
import uuid
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

try:
    import db as _db
    DB_TYPE = _db.DB_TYPE
except ImportError:
    _db = None
    DB_TYPE = "sqlite"

import sqlite3 as _sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")

_conn = None

def get_conn():
    if _db and _db.DB_TYPE == "postgres":
        return _db.get_conn()
    global _conn
    if _conn is None:
        _conn = _sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = _sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
    return _conn

def return_conn(conn):
    if _db and _db.DB_TYPE == "postgres":
        _db.return_conn(conn)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS client_communications (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL DEFAULT 'default',
    contact_id TEXT,
    contact_name TEXT,
    channel TEXT NOT NULL DEFAULT 'note',
    direction TEXT NOT NULL DEFAULT 'outbound',
    subject TEXT,
    body TEXT,
    summary TEXT,
    status TEXT DEFAULT 'logged',
    occurred_at TEXT NOT NULL,
    duration_seconds INTEGER,
    action_id TEXT,
    calendar_event_id TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mission_calendar_events (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL DEFAULT 'default',
    contact_id TEXT,
    contact_name TEXT,
    title TEXT NOT NULL,
    description TEXT,
    location TEXT,
    event_type TEXT DEFAULT 'appointment',
    status TEXT DEFAULT 'scheduled',
    start_at TEXT NOT NULL,
    end_at TEXT,
    all_day INTEGER DEFAULT 0,
    source TEXT DEFAULT 'manual',
    action_id TEXT,
    communication_id TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cc_business ON client_communications(business_id);
CREATE INDEX IF NOT EXISTS idx_cc_contact ON client_communications(contact_id);
CREATE INDEX IF NOT EXISTS idx_cc_channel ON client_communications(channel);
CREATE INDEX IF NOT EXISTS idx_cc_occurred ON client_communications(occurred_at);
CREATE INDEX IF NOT EXISTS idx_mce_business ON mission_calendar_events(business_id);
CREATE INDEX IF NOT EXISTS idx_mce_contact ON mission_calendar_events(contact_id);
CREATE INDEX IF NOT EXISTS idx_mce_start ON mission_calendar_events(start_at);
CREATE INDEX IF NOT EXISTS idx_mce_status ON mission_calendar_events(status);
"""

VALID_CHANNELS = {"call", "text", "email", "note"}
VALID_DIRECTIONS = {"inbound", "outbound", "internal"}
VALID_COMM_STATUSES = {"logged", "follow_up_needed", "resolved"}
VALID_EVENT_TYPES = {"appointment", "follow_up", "estimate", "call", "meeting", "other"}
VALID_EVENT_STATUSES = {"scheduled", "completed", "canceled", "no_show"}

def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return_conn(conn)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(row) -> Dict[str, Any]:
    if row is None:
        return None
    if isinstance(row, dict):
        d = dict(row)
    elif hasattr(row, "keys"):
        d = {k: row[k] for k in row.keys()}
    else:
        d = dict(row)
    if d.get("metadata_json"):
        try:
            d["metadata"] = json.loads(d["metadata_json"])
        except (json.JSONDecodeError, TypeError):
            d["metadata"] = {}
    else:
        d["metadata"] = {}
    d.pop("metadata_json", None)
    return d

# ---------------------------------------------------------------------------
# Communications CRUD
# ---------------------------------------------------------------------------

def get_communications(
    business_id: str = "default",
    contact_id: Optional[str] = None,
    channel: Optional[str] = None,
    direction: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[Dict]:
    conn = get_conn()
    where = ["business_id = ?"]
    params = [business_id]
    if contact_id:
        where.append("contact_id = ?")
        params.append(contact_id)
    if channel:
        where.append("channel = ?")
        params.append(channel)
    if direction:
        where.append("direction = ?")
        params.append(direction)
    if status:
        where.append("status = ?")
        params.append(status)
    params.append(limit)
    rows = conn.execute(
        f"SELECT * FROM client_communications WHERE {' AND '.join(where)} ORDER BY occurred_at DESC LIMIT ?",
        params
    ).fetchall()
    return_conn(conn)
    return [_row_to_dict(r) for r in rows]

def get_communication(comm_id: str) -> Optional[Dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM client_communications WHERE id = ?", [comm_id]).fetchone()
    return_conn(conn)
    return _row_to_dict(row)

def create_communication(
    business_id: str = "default",
    contact_id: Optional[str] = None,
    contact_name: Optional[str] = None,
    channel: str = "note",
    direction: str = "outbound",
    subject: Optional[str] = None,
    body: Optional[str] = None,
    summary: Optional[str] = None,
    status: str = "logged",
    occurred_at: Optional[str] = None,
    duration_seconds: Optional[int] = None,
    action_id: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> Dict:
    comm_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    occ_at = occurred_at or now
    meta_json = json.dumps(metadata) if metadata else None

    conn = get_conn()
    conn.execute(
        """INSERT INTO client_communications (
            id, business_id, contact_id, contact_name, channel, direction,
            subject, body, summary, status, occurred_at, duration_seconds,
            action_id, metadata_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [comm_id, business_id, contact_id, contact_name, channel, direction,
         subject, body, summary, status, occ_at, duration_seconds,
         action_id, meta_json, now, now]
    )
    conn.commit()
    return_conn(conn)
    return get_communication(comm_id)

def update_communication(comm_id: str, updates: Dict[str, Any]) -> Optional[Dict]:
    existing = get_communication(comm_id)
    if not existing:
        return None
    allowed = {"contact_id", "contact_name", "channel", "direction", "subject",
               "body", "summary", "status", "occurred_at", "duration_seconds"}
    set_clauses = []
    params = []
    for key, value in updates.items():
        if key not in allowed:
            continue
        set_clauses.append(f"{key} = ?")
        params.append(value)
    if not set_clauses:
        return existing
    now = datetime.utcnow().isoformat()
    set_clauses.append("updated_at = ?")
    params.append(now)
    params.append(comm_id)
    conn = get_conn()
    conn.execute(f"UPDATE client_communications SET {', '.join(set_clauses)} WHERE id = ?", params)
    conn.commit()
    return_conn(conn)
    return get_communication(comm_id)

# ---------------------------------------------------------------------------
# Calendar Events CRUD
# ---------------------------------------------------------------------------

def get_calendar_events(
    business_id: str = "default",
    contact_id: Optional[str] = None,
    status: Optional[str] = None,
    start_from: Optional[str] = None,
    start_to: Optional[str] = None,
    limit: int = 100,
) -> List[Dict]:
    conn = get_conn()
    where = ["business_id = ?"]
    params = [business_id]
    if contact_id:
        where.append("contact_id = ?")
        params.append(contact_id)
    if status:
        where.append("status = ?")
        params.append(status)
    if start_from:
        where.append("start_at >= ?")
        params.append(start_from)
    if start_to:
        where.append("start_at <= ?")
        params.append(start_to)
    params.append(limit)
    rows = conn.execute(
        f"SELECT * FROM mission_calendar_events WHERE {' AND '.join(where)} ORDER BY start_at ASC LIMIT ?",
        params
    ).fetchall()
    return_conn(conn)
    return [_row_to_dict(r) for r in rows]

def get_calendar_event(event_id: str) -> Optional[Dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM mission_calendar_events WHERE id = ?", [event_id]).fetchone()
    return_conn(conn)
    return _row_to_dict(row)

def create_calendar_event(
    business_id: str = "default",
    contact_id: Optional[str] = None,
    contact_name: Optional[str] = None,
    title: str = "",
    description: Optional[str] = None,
    location: Optional[str] = None,
    event_type: str = "appointment",
    status: str = "scheduled",
    start_at: str = None,
    end_at: Optional[str] = None,
    all_day: bool = False,
    action_id: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> Dict:
    event_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    start = start_at or now
    meta_json = json.dumps(metadata) if metadata else None

    conn = get_conn()
    conn.execute(
        """INSERT INTO mission_calendar_events (
            id, business_id, contact_id, contact_name, title, description,
            location, event_type, status, start_at, end_at, all_day,
            action_id, metadata_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [event_id, business_id, contact_id, contact_name, title, description,
         location, event_type, status, start, end_at, 1 if all_day else 0,
         action_id, meta_json, now, now]
    )
    conn.commit()
    return_conn(conn)
    return get_calendar_event(event_id)

def update_calendar_event(event_id: str, updates: Dict[str, Any]) -> Optional[Dict]:
    existing = get_calendar_event(event_id)
    if not existing:
        return None
    allowed = {"title", "description", "location", "event_type", "status",
               "start_at", "end_at", "all_day", "contact_id", "contact_name"}
    set_clauses = []
    params = []
    for key, value in updates.items():
        if key not in allowed:
            continue
        if key == "all_day":
            set_clauses.append("all_day = ?")
            params.append(1 if value else 0)
        else:
            set_clauses.append(f"{key} = ?")
            params.append(value)
    if not set_clauses:
        return existing
    now = datetime.utcnow().isoformat()
    set_clauses.append("updated_at = ?")
    params.append(now)
    params.append(event_id)
    conn = get_conn()
    conn.execute(f"UPDATE mission_calendar_events SET {', '.join(set_clauses)} WHERE id = ?", params)
    conn.commit()
    return_conn(conn)
    return get_calendar_event(event_id)

# ---------------------------------------------------------------------------
# Timeline (merged feed)
# ---------------------------------------------------------------------------

def get_timeline(
    business_id: str = "default",
    contact_id: Optional[str] = None,
    limit: int = 50,
) -> List[Dict]:
    """Get a merged timeline of communications and calendar events."""
    comms = get_communications(business_id=business_id, contact_id=contact_id, limit=limit)
    events = get_calendar_events(business_id=business_id, contact_id=contact_id, limit=limit)

    timeline = []
    for c in comms:
        timeline.append({
            **c,
            "timeline_type": "communication",
            "sort_date": c.get("occurred_at", ""),
        })
    for e in events:
        timeline.append({
            **e,
            "timeline_type": "calendar",
            "sort_date": e.get("start_at", ""),
        })

    timeline.sort(key=lambda x: x.get("sort_date", ""), reverse=True)
    return timeline[:limit]

# ---------------------------------------------------------------------------
# Demo Seeding
# ---------------------------------------------------------------------------

DEMO_COMMUNICATIONS = [
    {
        "contact_name": "[SAMPLE] Patricia Johnson",
        "contact_id": "CNT-20260817-3A8884",
        "channel": "call",
        "direction": "outbound",
        "subject": "Estimate follow-up call",
        "body": "Called Patricia about the kitchen remodel estimate. She's reviewing the numbers and will get back to us by Friday. She mentioned her husband wants to compare with one other contractor.",
        "summary": "Estimate sent, awaiting decision by Friday",
        "status": "follow_up_needed",
        "occurred_at_offset": -2,
        "duration_seconds": 480,
    },
    {
        "contact_name": "[SAMPLE] Patricia Johnson",
        "contact_id": "CNT-20260817-3A8884",
        "channel": "email",
        "direction": "outbound",
        "subject": "Re: Kitchen Remodel Estimate - Rocky Mountain Roofing",
        "body": "Hi Patricia, Thank you for your time today. As discussed, I've attached the detailed estimate for your kitchen remodel project. The total comes to $15,200 including materials and labor. Please don't hesitate to reach out with any questions. Best, Mike @ Rocky Mountain Roofing",
        "summary": "Sent detailed estimate via email",
        "status": "logged",
        "occurred_at_offset": -2,
    },
    {
        "contact_name": "[SAMPLE] Daniel Anderson",
        "contact_id": "CNT-20260817-3A8884",
        "channel": "text",
        "direction": "inbound",
        "subject": "Question about scheduling",
        "body": "Hey Mike, can we move the estimate appointment to next Tuesday instead of Monday? Something came up. Thanks! - Dan",
        "summary": "Customer requesting reschedule",
        "status": "follow_up_needed",
        "occurred_at_offset": -1,
    },
    {
        "contact_name": "[SAMPLE] Daniel Anderson",
        "contact_id": "CNT-20260817-3A8884",
        "channel": "text",
        "direction": "outbound",
        "subject": "Re: Question about scheduling",
        "body": "Hi Dan, no problem at all! I've moved you to Tuesday at 10am. See you then! - Mike",
        "summary": "Confirmed reschedule to Tuesday 10am",
        "status": "resolved",
        "occurred_at_offset": -1,
    },
    {
        "contact_name": "[SAMPLE] Jessica Davis",
        "contact_id": "CNT-20260817-3046FC",
        "channel": "call",
        "direction": "inbound",
        "subject": "Referral inquiry",
        "body": "Jessica called to ask about getting a quote for her sister's roof replacement. I scheduled a consultation for next week. She was very happy with the work we did on her roof last year.",
        "summary": "New referral lead from satisfied client",
        "status": "logged",
        "occurred_at_offset": -3,
        "duration_seconds": 360,
    },
    {
        "contact_name": "[SAMPLE] Michael Williams",
        "contact_id": "CNT-20260817-84B87F",
        "channel": "email",
        "direction": "inbound",
        "subject": "Satisfaction follow-up response",
        "body": "Mike, The roof looks great! Thanks for the quick turnaround. I'll definitely recommend you guys to my neighbors. One question - do you offer any warranty on the flashing work? - Michael",
        "summary": "Happy customer, asked about warranty",
        "status": "follow_up_needed",
        "occurred_at_offset": -5,
    },
    {
        "contact_name": "[SAMPLE] Linda Anderson",
        "contact_id": "CNT-20260817-ADBE67",
        "channel": "call",
        "direction": "outbound",
        "subject": "Lead follow-up call",
        "body": "Left a voicemail for Linda following up on her inquiry about roof repair. Mentioned our August special and asked her to call back at her convenience.",
        "summary": "Voicemail left, awaiting callback",
        "status": "follow_up_needed",
        "occurred_at_offset": 0,
        "duration_seconds": 60,
    },
    {
        "contact_name": "[SAMPLE] Linda Clark",
        "contact_id": "CNT-20260817-ADBE67",
        "channel": "note",
        "direction": "internal",
        "subject": "Account note - payment history",
        "body": "Linda has been a client for 3 years. Always pays on time. Last project was a full roof replacement in March. Consider for VIP referral program.",
        "summary": "Internal note about long-term client",
        "status": "logged",
        "occurred_at_offset": -7,
    },
]

DEMO_CALENDAR_EVENTS = [
    {
        "contact_name": "[SAMPLE] Daniel Anderson",
        "contact_id": "CNT-20260817-3A8884",
        "title": "Estimate Appointment - Daniel Anderson",
        "description": "On-site estimate for roof repair. Customer requested reschedule from Monday to Tuesday.",
        "location": "Client Home - 1234 Cedar St, Aurora, CO",
        "event_type": "estimate",
        "start_offset": 1,
        "duration_hours": 1.5,
    },
    {
        "contact_name": "[SAMPLE] Jessica Davis",
        "contact_id": "CNT-20260817-3046FC",
        "title": "Consultation - Jessica's Sister Referral",
        "description": "Roof replacement consultation for Jessica's sister. Jessica was very happy with our previous work.",
        "location": "Office",
        "event_type": "appointment",
        "start_offset": 3,
        "duration_hours": 1,
    },
    {
        "contact_name": "[SAMPLE] Patricia Johnson",
        "contact_id": "CNT-20260817-3A8884",
        "title": "Follow-up Call - Patricia Johnson",
        "description": "Call Patricia to check on estimate decision. She said she'd have an answer by Friday.",
        "location": "Phone",
        "event_type": "call",
        "start_offset": 2,
        "duration_hours": 0.5,
    },
    {
        "contact_name": "[SAMPLE] Michael Williams",
        "contact_id": "CNT-20260817-84B87F",
        "title": "Warranty Discussion - Michael Williams",
        "description": "Discuss flashing warranty options. Michael was happy with roof work and asked about warranty coverage.",
        "location": "Phone",
        "event_type": "call",
        "start_offset": 4,
        "duration_hours": 0.5,
    },
    {
        "contact_name": "[SAMPLE] Linda Anderson",
        "contact_id": "CNT-20260817-ADBE67",
        "title": "Quarterly Check-in - Linda Anderson",
        "description": "Routine satisfaction check-in with long-term VIP client. Discuss referral program.",
        "location": "Phone",
        "event_type": "follow_up",
        "start_offset": 7,
        "duration_hours": 0.5,
    },
]

def seed_demo_communications(business_id: str = "roofing"):
    """Seed demo communications if none exist."""
    conn = get_conn()
    existing = conn.execute(
        "SELECT COUNT(*) as cnt FROM client_communications WHERE business_id = ?",
        [business_id]
    ).fetchone()
    count = existing["cnt"] if existing else 0
    if count > 0:
        return_conn(conn)
        return {"seeded": 0, "existing": count}

    now = datetime.utcnow()
    seeded = 0
    for comm in DEMO_COMMUNICATIONS:
        comm_id = str(uuid.uuid4())
        occ_at = (now + timedelta(days=comm["occurred_at_offset"])).isoformat()
        created = now.isoformat()

        conn.execute(
            """INSERT INTO client_communications (
                id, business_id, contact_id, contact_name, channel, direction,
                subject, body, summary, status, occurred_at, duration_seconds, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [comm_id, business_id, comm.get("contact_id"), comm["contact_name"],
             comm["channel"], comm["direction"], comm.get("subject"),
             comm.get("body"), comm.get("summary"), comm.get("status", "logged"),
             occ_at, comm.get("duration_seconds"), created, created]
        )
        seeded += 1

    conn.commit()
    return_conn(conn)
    return {"seeded": seeded, "existing": 0}

def seed_demo_calendar(business_id: str = "roofing"):
    """Seed demo calendar events if none exist."""
    conn = get_conn()
    existing = conn.execute(
        "SELECT COUNT(*) as cnt FROM mission_calendar_events WHERE business_id = ?",
        [business_id]
    ).fetchone()
    count = existing["cnt"] if existing else 0
    if count > 0:
        return_conn(conn)
        return {"seeded": 0, "existing": count}

    now = datetime.utcnow()
    seeded = 0
    for event in DEMO_CALENDAR_EVENTS:
        event_id = str(uuid.uuid4())
        start = now + timedelta(days=event["start_offset"])
        # Set time to 10am if no specific time
        start = start.replace(hour=10, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=event.get("duration_hours", 1))
        created = now.isoformat()

        conn.execute(
            """INSERT INTO mission_calendar_events (
                id, business_id, contact_id, contact_name, title, description,
                location, event_type, status, start_at, end_at, all_day, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'scheduled', ?, ?, 0, ?, ?)""",
            [event_id, business_id, event.get("contact_id"), event["contact_name"],
             event["title"], event.get("description"), event.get("location"),
             event.get("event_type", "appointment"), start.isoformat(),
             end.isoformat(), created, created]
        )
        seeded += 1

    conn.commit()
    return_conn(conn)
    return {"seeded": seeded, "existing": 0}
