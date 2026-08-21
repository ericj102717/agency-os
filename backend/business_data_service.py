#!/usr/bin/env python3
"""
Business Data Service
=====================
The single authoritative data service layer for the entire application.
Every module, agent, dashboard, and API endpoint should call this service
to read and write business data. No module should access data_store.py
or demo data directly.

This service:
- Reads from SQLite (real data) when available
- Falls back to demo data when no real data exists
- Provides CRUD operations for all business entities
- Computes derived metrics (KPIs, forecasts, data quality)
- Generates recommendations with explanations

DRAFT -- owner approval required.
"""

import json
import os
import sys
import uuid
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data_store

# ---------------------------------------------------------------------------
# Connection helper - use fresh connection per write to avoid stale reads
# ---------------------------------------------------------------------------

def _execute(fn):
    """Execute a function with a fresh DB connection, ensuring commits are visible."""
    conn = data_store.get_conn()
    try:
        result = fn(conn)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        data_store.return_conn(conn)

def _query(fn):
    """Execute a read function, ensuring we see latest committed data."""
    conn = data_store.get_conn()
    try:
        # In WAL mode, commit to end any active read transaction so we see
        # the latest committed writes from other connections.
        conn.commit()
        return fn(conn)
    except Exception:
        conn.rollback()
        raise
    finally:
        data_store.return_conn(conn)

# ---------------------------------------------------------------------------
# Business Configuration
# ---------------------------------------------------------------------------

def get_business_config() -> Dict[str, Any]:
    """Get the single business configuration record."""
    def _get(conn):
        row = conn.execute("SELECT * FROM business_config WHERE id = 1").fetchone()
        if row:
            return dict(row)
        return None
    config = _query(_get)
    if not config:
        # Create default record
        _execute(lambda c: c.execute(
            "INSERT INTO business_config (id) VALUES (1)"
        ))
        config = _query(_get)
    return config or {}

def update_business_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update business configuration fields."""
    allowed = ['business_name', 'industry', 'primary_objective', 'revenue_goal',
               'goal_period', 'avg_transaction_value', 'current_revenue',
               'reporting_period', 'setup_complete', 'setup_completed_at']
    sets = ', '.join(f"{k} = ?" for k in updates if k in allowed)
    vals = [updates[k] for k in updates if k in allowed]
    if sets:
        vals.append(datetime.now().isoformat())
        sets += ', updated_at = ?'
        _execute(lambda c: c.execute(
            f"UPDATE business_config SET {sets} WHERE id = 1", vals
        ))
    return get_business_config()

def is_setup_complete() -> bool:
    config = get_business_config()
    return bool(config.get('setup_complete', 0))

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

def get_services(active_only: bool = False) -> List[Dict[str, Any]]:
    def _get(conn):
        q = "SELECT * FROM services"
        if active_only:
            q += " WHERE is_active = 1"
        q += " ORDER BY sort_order, name"
        return [dict(r) for r in conn.execute(q).fetchall()]
    return _query(_get)

def add_service(name: str, description: str = '', avg_price: float = 0,
                category: str = '', sort_order: int = 0) -> Dict[str, Any]:
    def _add(conn):
        cur = conn.execute(
            "INSERT INTO services (name, description, avg_price, category, sort_order) VALUES (?, ?, ?, ?, ?)",
            (name, description, avg_price, category, sort_order)
        )
        return cur.lastrowid
    sid = _execute(_add)
    return {"id": sid, "name": name, "description": description, "avg_price": avg_price}

def delete_service(service_id: int) -> bool:
    _execute(lambda c: c.execute("DELETE FROM services WHERE id = ?", (service_id,)))
    return True

# ---------------------------------------------------------------------------
# Lead Sources
# ---------------------------------------------------------------------------

def get_lead_sources(active_only: bool = False) -> List[Dict[str, Any]]:
    def _get(conn):
        q = "SELECT * FROM lead_sources"
        if active_only:
            q += " WHERE is_active = 1"
        q += " ORDER BY sort_order, name"
        return [dict(r) for r in conn.execute(q).fetchall()]
    return _query(_get)

def add_lead_source(name: str, description: str = '', sort_order: int = 0) -> Dict[str, Any]:
    try:
        def _add(conn):
            cur = conn.execute(
                "INSERT INTO lead_sources (name, description, sort_order) VALUES (?, ?, ?)",
                (name, description, sort_order)
            )
            return cur.lastrowid
        sid = _execute(_add)
        return {"id": sid, "name": name}
    except Exception:
        return {"error": "Lead source already exists"}

def delete_lead_source(source_id: int) -> bool:
    _execute(lambda c: c.execute("DELETE FROM lead_sources WHERE id = ?", (source_id,)))
    return True

# ---------------------------------------------------------------------------
# Sales Stages
# ---------------------------------------------------------------------------

def get_sales_stages() -> List[Dict[str, Any]]:
    def _get(conn):
        return [dict(r) for r in conn.execute(
            "SELECT * FROM sales_stages ORDER BY sort_order"
        ).fetchall()]
    return _query(_get)

def add_sales_stage(name: str, label: str = '', probability: float = 0,
                    sort_order: int = 0, is_closed: bool = False,
                    is_won: bool = False) -> Dict[str, Any]:
    try:
        def _add(conn):
            cur = conn.execute(
                "INSERT INTO sales_stages (name, label, probability, sort_order, is_closed, is_won) VALUES (?, ?, ?, ?, ?, ?)",
                (name, label, probability, sort_order, int(is_closed), int(is_won))
            )
            return cur.lastrowid
        sid = _execute(_add)
        return {"id": sid, "name": name}
    except Exception:
        return {"error": "Stage already exists"}

# ---------------------------------------------------------------------------
# Contacts (Leads, Clients, Prospects)
# ---------------------------------------------------------------------------

def get_contacts(contact_type: str = None) -> List[Dict[str, Any]]:
    def _get(conn):
        q = "SELECT * FROM contacts"
        params = ()
        if contact_type:
            q += " WHERE contact_type = ?"
            params = (contact_type,)
        q += " ORDER BY created_at DESC"
        return [dict(r) for r in conn.execute(q, params).fetchall()]
    return _query(_get)

def get_contact(contact_id: str) -> Optional[Dict[str, Any]]:
    def _get(conn):
        row = conn.execute("SELECT * FROM contacts WHERE contact_id = ?", (contact_id,)).fetchone()
        return dict(row) if row else None
    return _query(_get)

def add_contact(data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a single contact. Auto-generates contact_id if missing."""
    # Server-side validation
    if not data.get('first_name') or not str(data.get('first_name', '')).strip():
        return {"status": "error", "error": "First name is required"}
    if not data.get('contact_id'):
        data['contact_id'] = f"CNT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    # Normalize email/phone
    data['normalized_email'] = data_store.normalize_email(data.get('email', ''))
    data['normalized_phone'] = data_store.normalize_phone(data.get('phone', ''))
    # Convert booleans
    for k in ['email_consent', 'sms_consent', 'call_consent']:
        v = data.get(k, False)
        data[k] = 1 if v in (True, 'true', '1', 'yes', 'True') else 0
    
    cols = ['contact_id', 'first_name', 'last_name', 'email', 'normalized_email',
            'phone', 'normalized_phone', 'date_of_birth', 'contact_type', 'lead_source',
            'pipeline_stage', 'medicare_status', 'email_consent', 'sms_consent',
            'call_consent', 'last_activity', 'client_since', 'zip_code', 'state', 'tags', 'notes']
    vals = [data.get(k, '' if k != 'contact_type' else 'lead') for k in cols]
    placeholders = ', '.join(['?'] * len(cols))
    colnames = ', '.join(cols)
    
    try:
        def _add(conn):
            conn.execute(f"INSERT INTO contacts ({colnames}) VALUES ({placeholders})", vals)
        _execute(_add)
        return {"status": "ok", "contact_id": data['contact_id']}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# Allowlist of updatable columns for contacts
CONTACT_COLUMNS = {'first_name','last_name','email','phone','normalized_email','normalized_phone',
    'email_consent','sms_consent','call_consent','lead_score','status','source',
    'notes','address','city','state','zip','tags','assigned_to','company'}

def update_contact(contact_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    if 'email' in updates:
        updates['normalized_email'] = data_store.normalize_email(updates['email'])
    if 'phone' in updates:
        updates['normalized_phone'] = data_store.normalize_phone(updates['phone'])
    for k in ['email_consent', 'sms_consent', 'call_consent']:
        if k in updates:
            updates[k] = 1 if updates[k] in (True, 'true', '1', 'yes') else 0
    
    safe = {k: v for k, v in updates.items() if k in CONTACT_COLUMNS}
    if not safe:
        return {"status": "error", "error": "No valid columns to update"}
    sets = ', '.join(f"{k} = ?" for k in safe)
    vals = list(safe.values()) + [datetime.now().isoformat(), contact_id]
    sets += ', updated_at = ?'
    
    _execute(lambda c: c.execute(f"UPDATE contacts SET {sets} WHERE contact_id = ?", vals))
    return get_contact(contact_id) or {"status": "not found"}

def delete_contact(contact_id: str) -> bool:
    _execute(lambda c: c.execute("DELETE FROM contacts WHERE contact_id = ?", (contact_id,)))
    return True

# ---------------------------------------------------------------------------
# Opportunities
# ---------------------------------------------------------------------------

def get_opportunities(stage: str = None) -> List[Dict[str, Any]]:
    def _get(conn):
        q = "SELECT * FROM opportunities"
        params = ()
        if stage:
            q += " WHERE stage = ?"
            params = (stage,)
        q += " ORDER BY created_at DESC"
        return [dict(r) for r in conn.execute(q, params).fetchall()]
    return _query(_get)

def add_opportunity(data: Dict[str, Any]) -> Dict[str, Any]:
    if not data.get('opp_id'):
        data['opp_id'] = f"OPP-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    cols = ['opp_id', 'contact_id', 'product_type', 'stage', 'entered_stage',
            'expected_close', 'estimated_value', 'created_date', 'stage_history']
    vals = [data.get(k, '' if k != 'stage' else 'new') for k in cols]
    if not vals[7]:  # created_date
        vals[7] = date.today().isoformat()
    if not vals[8]:  # stage_history
        vals[8] = '[]'
    placeholders = ', '.join(['?'] * len(cols))
    colnames = ', '.join(cols)
    
    try:
        def _add(conn):
            conn.execute(f"INSERT INTO opportunities ({colnames}) VALUES ({placeholders})", vals)
        _execute(_add)
        return {"status": "ok", "opp_id": data['opp_id']}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# Allowlist of updatable columns for opportunities
OPPORTUNITY_COLUMNS = {'contact_id','stage','value','probability','expected_close_date',
    'product_type','notes','assigned_to','source','entered_stage'}

def update_opportunity(opp_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    if 'stage' in updates:
        updates['entered_stage'] = datetime.now().isoformat()
    safe = {k: v for k, v in updates.items() if k in OPPORTUNITY_COLUMNS}
    if not safe:
        return {"status": "error", "error": "No valid columns to update"}
    sets = ', '.join(f"{k} = ?" for k in safe)
    vals = list(safe.values()) + [datetime.now().isoformat(), opp_id]
    sets += ', updated_at = ?'
    _execute(lambda c: c.execute(f"UPDATE opportunities SET {sets} WHERE opp_id = ?", vals))
    return {"status": "ok"}

def delete_opportunity(opp_id: str) -> bool:
    _execute(lambda c: c.execute("DELETE FROM opportunities WHERE opp_id = ?", (opp_id,)))
    return True

# ---------------------------------------------------------------------------
# Revenue Records
# ---------------------------------------------------------------------------

def get_revenue_records() -> List[Dict[str, Any]]:
    def _get(conn):
        return [dict(r) for r in conn.execute(
            "SELECT * FROM revenue_records ORDER BY revenue_date DESC"
        ).fetchall()]
    return _query(_get)

def add_revenue(data: Dict[str, Any]) -> Dict[str, Any]:
    # Server-side validation
    client = str(data.get('client_name', '')).strip()
    if not client:
        return {"status": "error", "error": "Client name is required"}
    try:
        amount = float(data.get('amount', 0))
        if amount <= 0:
            return {"status": "error", "error": "Amount must be greater than 0"}
    except (ValueError, TypeError):
        return {"status": "error", "error": "Amount must be a valid number"}
    if not data.get('record_id'):
        data['record_id'] = f"REV-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    cols = ['record_id', 'contact_id', 'product_type', 'amount', 'revenue_date',
            'revenue_category', 'payment_status', 'source']
    vals = [data.get(k, '') for k in cols]
    if not vals[4]:  # revenue_date
        vals[4] = date.today().isoformat()
    placeholders = ', '.join(['?'] * len(cols))
    colnames = ', '.join(cols)
    
    try:
        def _add(conn):
            conn.execute(f"INSERT INTO revenue_records ({colnames}) VALUES ({placeholders})", vals)
        _execute(_add)
        return {"status": "ok", "record_id": data['record_id']}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def delete_revenue(record_id: str) -> bool:
    _execute(lambda c: c.execute("DELETE FROM revenue_records WHERE record_id = ?", (record_id,)))
    return True

# ---------------------------------------------------------------------------
# Referral Sources / Partners
# ---------------------------------------------------------------------------

def get_referral_sources() -> List[Dict[str, Any]]:
    def _get(conn):
        return [dict(r) for r in conn.execute(
            "SELECT * FROM referral_sources ORDER BY created_at DESC"
        ).fetchall()]
    return _query(_get)

def add_referral_source(data: Dict[str, Any]) -> Dict[str, Any]:
    if not data.get('source_id'):
        data['source_id'] = f"REF-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    cols = ['source_id', 'source_name', 'source_type', 'contact_info',
            'relationship_strength', 'referrals_generated', 'referrals_converted',
            'conversion_rate', 'total_revenue_generated', 'last_referral_date', 'status']
    vals = [data.get(k, '') for k in cols]
    if not vals[4]:  # relationship_strength
        vals[4] = 50
    if not vals[10]:  # status
        vals[10] = 'active'
    placeholders = ', '.join(['?'] * len(cols))
    colnames = ', '.join(cols)
    
    try:
        def _add(conn):
            conn.execute(f"INSERT INTO referral_sources ({colnames}) VALUES ({placeholders})", vals)
        _execute(_add)
        return {"status": "ok", "source_id": data['source_id']}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def delete_referral_source(source_id: str) -> bool:
    _execute(lambda c: c.execute("DELETE FROM referral_sources WHERE source_id = ?", (source_id,)))
    return True

# ---------------------------------------------------------------------------
# Actions / Tasks
# ---------------------------------------------------------------------------

def get_actions(status: str = None, limit: int = 100) -> List[Dict[str, Any]]:
    def _get(conn):
        q = "SELECT * FROM actions"
        params = ()
        if status:
            q += " WHERE status = ?"
            params = (status,)
        q += " ORDER BY priority ASC, due_date ASC"
        if limit:
            q += f" LIMIT {limit}"
        return [dict(r) for r in conn.execute(q, params).fetchall()]
    return _query(_get)

def add_action(data: Dict[str, Any]) -> Dict[str, Any]:
    if not data.get('action_id'):
        data['action_id'] = f"ACT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    cols = ['action_id', 'entity_type', 'entity_id', 'entity_name', 'action_type',
            'title', 'description', 'priority', 'due_date', 'status', 'expected_value',
            'recommendation_id', 'source_module']
    vals = [data.get(k, '') for k in cols]
    if not vals[7]:  # priority
        vals[7] = 5
    if not vals[9]:  # status
        vals[9] = 'pending'
    placeholders = ', '.join(['?'] * len(cols))
    colnames = ', '.join(cols)
    
    try:
        def _add(conn):
            conn.execute(f"INSERT INTO actions ({colnames}) VALUES ({placeholders})", vals)
        _execute(_add)
        return {"status": "ok", "action_id": data['action_id']}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# Allowlist of updatable columns for actions
ACTION_COLUMNS = {'status','priority','title','description','assigned_to',
    'due_date','completed_date','contact_id','opportunity_id','action_type'}

def update_action(action_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    if 'status' in updates and updates['status'] == 'completed':
        updates['completed_date'] = datetime.now().isoformat()
    safe = {k: v for k, v in updates.items() if k in ACTION_COLUMNS}
    if not safe:
        return {"status": "error", "error": "No valid columns to update"}
    sets = ', '.join(f"{k} = ?" for k in safe)
    vals = list(safe.values()) + [datetime.now().isoformat(), action_id]
    sets += ', updated_at = ?'
    _execute(lambda c: c.execute(f"UPDATE actions SET {sets} WHERE action_id = ?", vals))
    return {"status": "ok"}

def delete_action(action_id: str) -> bool:
    _execute(lambda c: c.execute("DELETE FROM actions WHERE action_id = ?", (action_id,)))
    return True

# ---------------------------------------------------------------------------
# Recommendations (with explanation data)
# ---------------------------------------------------------------------------

def get_recommendations(status: str = 'active') -> List[Dict[str, Any]]:
    def _get(conn):
        q = "SELECT * FROM recommendations"
        params = ()
        if status:
            q += " WHERE status = ?"
            params = (status,)
        q += " ORDER BY priority ASC, created_at DESC"
        rows = [dict(r) for r in conn.execute(q, params).fetchall()]
        for r in rows:
            try:
                r['explanation_data'] = json.loads(r.get('explanation_data', '{}'))
            except:
                r['explanation_data'] = {}
        return rows
    return _query(_get)

def add_recommendation(data: Dict[str, Any]) -> Dict[str, Any]:
    rec_id = data.get('rec_id') or f"REC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    explanation = data.get('explanation_data', {})
    if isinstance(explanation, dict):
        explanation = json.dumps(explanation)
    
    cols = ['rec_id', 'entity_type', 'entity_id', 'rec_type', 'title', 'description',
            'priority', 'expected_impact', 'ignore_consequence', 'next_step', 'explanation_data', 'status']
    vals = [rec_id, data.get('entity_type', ''), data.get('entity_id', ''),
            data.get('rec_type', ''), data.get('title', ''), data.get('description', ''),
            data.get('priority', 5), data.get('expected_impact', ''),
            data.get('ignore_consequence', ''), data.get('next_step', ''),
            explanation, data.get('status', 'active')]
    placeholders = ', '.join(['?'] * len(cols))
    colnames = ', '.join(cols)
    
    try:
        def _add(conn):
            conn.execute(f"INSERT INTO recommendations ({colnames}) VALUES ({placeholders})", vals)
        _execute(_add)
        return {"status": "ok", "rec_id": rec_id}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def update_recommendation_status(rec_id: str, status: str) -> bool:
    _execute(lambda c: c.execute(
        "UPDATE recommendations SET status = ? WHERE rec_id = ?", (status, rec_id)
    ))
    return True

# ---------------------------------------------------------------------------
# Recommendation Feedback
# ---------------------------------------------------------------------------

def add_feedback(rec_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    cols = ['rec_id', 'user_action', 'completed', 'outcome', 'revenue_generated',
            'conversion_result', 'time_to_complete_hours', 'feedback_notes']
    vals = [rec_id, data.get('user_action', ''), int(data.get('completed', 0)),
            data.get('outcome', ''), data.get('revenue_generated', 0),
            data.get('conversion_result', ''), data.get('time_to_complete_hours', 0),
            data.get('feedback_notes', '')]
    placeholders = ', '.join(['?'] * len(cols))
    colnames = ', '.join(cols)
    
    try:
        def _add(conn):
            conn.execute(f"INSERT INTO recommendation_feedback ({colnames}) VALUES ({placeholders})", vals)
        _execute(_add)
        # Mark recommendation as completed
        if data.get('completed'):
            update_recommendation_status(rec_id, 'completed')
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def get_recommendation_accuracy() -> Dict[str, Any]:
    """Compute recommendation accuracy metrics."""
    def _get(conn):
        total_recs = conn.execute("SELECT COUNT(*) FROM recommendations").fetchone()[0]
        completed = conn.execute("SELECT COUNT(*) FROM recommendations WHERE status = 'completed'").fetchone()[0]
        feedback = [dict(r) for r in conn.execute(
            "SELECT * FROM recommendation_feedback ORDER BY created_at DESC"
        ).fetchall()]
        
        action_rate = (completed / total_recs * 100) if total_recs > 0 else 0
        conversion_count = sum(1 for f in feedback if f.get('conversion_result') == 'converted')
        conversion_rate = (conversion_count / len(feedback) * 100) if feedback else 0
        revenue_influenced = sum(f.get('revenue_generated', 0) for f in feedback)
        
        # By type
        by_type = {}
        for f in feedback:
            rec = conn.execute("SELECT rec_type FROM recommendations WHERE rec_id = ?",
                             (f['rec_id'],)).fetchone()
            if rec:
                rtype = rec[0]
                if rtype not in by_type:
                    by_type[rtype] = {'total': 0, 'completed': 0, 'revenue': 0}
                by_type[rtype]['total'] += 1
                if f.get('completed'):
                    by_type[rtype]['completed'] += 1
                by_type[rtype]['revenue'] += f.get('revenue_generated', 0)
        
        return {
            'total_recommendations': total_recs,
            'completed': completed,
            'action_rate': round(action_rate, 1),
            'conversion_rate': round(conversion_rate, 1),
            'revenue_influenced': revenue_influenced,
            'feedback_count': len(feedback),
            'by_type': by_type,
        }
    return _query(_get)

# ---------------------------------------------------------------------------
# Business Memory
# ---------------------------------------------------------------------------

def get_memories(entity_type: str = None, entity_id: str = None) -> List[Dict[str, Any]]:
    def _get(conn):
        q = "SELECT * FROM business_memory"
        params = ()
        if entity_type and entity_id:
            q += " WHERE entity_type = ? AND entity_id = ?"
            params = (entity_type, entity_id)
        elif entity_type:
            q += " WHERE entity_type = ?"
            params = (entity_type,)
        q += " ORDER BY created_at DESC"
        return [dict(r) for r in conn.execute(q, params).fetchall()]
    return _query(_get)

def add_memory(data: Dict[str, Any]) -> Dict[str, Any]:
    mem_id = data.get('memory_id') or f"MEM-{uuid.uuid4().hex[:8].upper()}"
    
    cols = ['memory_id', 'entity_type', 'entity_id', 'entity_name', 'memory_text',
            'memory_category', 'relevance_score']
    vals = [mem_id, data.get('entity_type', ''), data.get('entity_id', ''),
            data.get('entity_name', ''), data.get('memory_text', ''),
            data.get('memory_category', 'general'), data.get('relevance_score', 50)]
    placeholders = ', '.join(['?'] * len(cols))
    colnames = ', '.join(cols)
    
    try:
        def _add(conn):
            conn.execute(f"INSERT INTO business_memory ({colnames}) VALUES ({placeholders})", vals)
        _execute(_add)
        return {"status": "ok", "memory_id": mem_id}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def delete_memory(memory_id: str) -> bool:
    _execute(lambda c: c.execute("DELETE FROM business_memory WHERE memory_id = ?", (memory_id,)))
    return True

# ---------------------------------------------------------------------------
# KPI Computation (single source of truth for metrics)
# ---------------------------------------------------------------------------

def compute_kpis() -> Dict[str, Any]:
    """Compute all dashboard KPIs from the master data model."""
    today = date.today()
    contacts = get_contacts()
    opportunities = get_opportunities()
    revenue_records = get_revenue_records()
    referral_sources = get_referral_sources()
    config = get_business_config()
    
    has_real = data_store.has_real_contacts() or data_store.has_real_opportunities() or data_store.has_real_revenue()
    _demo_mode = data_store._is_demo_mode()
    
    if not has_real and not config.get('setup_complete'):
        return {
            'revenue_mtd': 0, 'revenue_forecast': 0,
            'pipeline_value': 0, 'new_leads': 0,
            'conversion_rate': 0, 'active_clients': 0,
            'client_lifetime_value': 0, 'referral_opportunities': 0,
            'data_source': 'empty',
        }
    
    # Active clients
    active_clients = len([c for c in contacts if c.get('contact_type') == 'client'])
    
    # New leads
    new_leads = len([c for c in contacts if c.get('pipeline_stage') == 'new'])
    
    # Pipeline value (active opps only)
    active_opps = [o for o in opportunities if o.get('stage') not in ('closed_won', 'closed_lost')]
    pipeline_value = sum(float(o.get('estimated_value', 0) or 0) for o in active_opps)
    
    # Revenue MTD
    revenue_mtd = 0
    for r in revenue_records:
        rev_date = str(r.get('revenue_date', ''))
        if rev_date and str(today.year) in rev_date and str(today.month).zfill(2) in rev_date[:7]:
            try:
                revenue_mtd += float(r.get('amount', 0) or 0)
            except (ValueError, TypeError):
                pass
    
    # Close rate
    won_count = len([o for o in opportunities if o.get('stage') == 'closed_won'])
    lost_count = len([o for o in opportunities if o.get('stage') == 'closed_lost'])
    total_closed = won_count + lost_count
    close_rate = int((won_count / total_closed * 100) if total_closed > 0 else 0)
    
    # Revenue forecast
    revenue_forecast = int(pipeline_value * close_rate / 100)
    
    # Revenue goal
    revenue_goal = float(config.get('revenue_goal', 0) or 0)
    
    # CLV
    total_revenue = 0
    for r in revenue_records:
        try:
            total_revenue += float(r.get('amount', 0) or 0)
        except (ValueError, TypeError):
            pass
    clv = int(total_revenue / active_clients) if active_clients > 0 and total_revenue > 0 else 0
    
    # Referral opportunities
    referral_opps = len([r for r in referral_sources if r.get('status') == 'active']) if referral_sources else 0
    
    return {
        'revenue_mtd': revenue_mtd,
        'revenue_forecast': revenue_forecast,
        'pipeline_value': int(pipeline_value),
        'new_leads': new_leads,
        'conversion_rate': close_rate,
        'active_clients': active_clients,
        'client_lifetime_value': clv,
        'referral_opportunities': referral_opps,
        'revenue_goal': revenue_goal,
        'revenue_gap': revenue_goal - revenue_mtd - revenue_forecast if revenue_goal else 0,
        'data_source': 'demo' if _demo_mode else ('real' if has_real else 'empty'),
        'contacts_count': len(contacts),
        'opportunities_count': len(opportunities),
        'revenue_records_count': len(revenue_records),
        'referral_sources_count': len(referral_sources),
    }

# ---------------------------------------------------------------------------
# Data Quality
# ---------------------------------------------------------------------------

def compute_data_quality() -> Dict[str, Any]:
    """Compute data quality metrics and identify issues."""
    contacts = get_contacts()
    opportunities = get_opportunities()
    revenue_records = get_revenue_records()
    referral_sources = get_referral_sources()
    
    issues = []
    total_records = len(contacts) + len(opportunities) + len(revenue_records) + len(referral_sources)
    
    if total_records == 0:
        return {
            'score': 0,
            'total_records': 0,
            'issues': [],
            'error_count': 0,
            'warning_count': 0,
            'issue_count': 0,
            'summary': {'missing_phone': 0, 'missing_email': 0, 'missing_source': 0,
                       'missing_value': 0, 'missing_close_date': 0, 'stale': 0, 'duplicate': 0}
        }
    
    # Check contacts
    for c in contacts:
        cid = c.get('contact_id', '')
        name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
        if not c.get('phone'):
            issues.append({'entity': 'contact', 'id': cid, 'name': name,
                          'issue': 'missing_phone', 'severity': 'warning',
                          'message': f'{name} is missing a phone number'})
        if not c.get('email'):
            issues.append({'entity': 'contact', 'id': cid, 'name': name,
                          'issue': 'missing_email', 'severity': 'warning',
                          'message': f'{name} is missing an email address'})
        if not c.get('lead_source'):
            issues.append({'entity': 'contact', 'id': cid, 'name': name,
                          'issue': 'missing_source', 'severity': 'info',
                          'message': f'{name} has no lead source recorded'})
        # Stale check (30+ days since last activity)
        last_activity = c.get('last_activity', '')
        if last_activity:
            try:
                la = datetime.fromisoformat(last_activity)
                days = (datetime.now() - la).days
                if days > 30:
                    issues.append({'entity': 'contact', 'id': cid, 'name': name,
                                  'issue': 'stale', 'severity': 'warning',
                                  'message': f'{name} has been inactive for {days} days'})
            except:
                pass
    
    # Check opportunities for missing values
    for o in opportunities:
        oid = o.get('opp_id', '')
        if not o.get('estimated_value') or float(o.get('estimated_value', 0)) == 0:
            issues.append({'entity': 'opportunity', 'id': oid, 'name': oid,
                          'issue': 'missing_value', 'severity': 'error',
                          'message': f'Opportunity {oid} has no estimated value'})
        if not o.get('expected_close'):
            issues.append({'entity': 'opportunity', 'id': oid, 'name': oid,
                          'issue': 'missing_close_date', 'severity': 'warning',
                          'message': f'Opportunity {oid} has no expected close date'})
    
    # Check for duplicates (same email)
    emails = {}
    for c in contacts:
        e = c.get('normalized_email', '')
        if e:
            if e in emails:
                issues.append({'entity': 'contact', 'id': c.get('contact_id', ''),
                              'name': f"{c.get('first_name','')} {c.get('last_name','')}",
                              'issue': 'duplicate', 'severity': 'error',
                              'message': f'Duplicate email: {c.get("email","")}'})
            else:
                emails[e] = True
    
    # Compute score
    error_count = sum(1 for i in issues if i['severity'] == 'error')
    warning_count = sum(1 for i in issues if i['severity'] == 'warning')
    score = max(0, 100 - (error_count * 10 + warning_count * 3))
    
    summary = {
        'missing_phone': sum(1 for i in issues if i['issue'] == 'missing_phone'),
        'missing_email': sum(1 for i in issues if i['issue'] == 'missing_email'),
        'missing_source': sum(1 for i in issues if i['issue'] == 'missing_source'),
        'missing_value': sum(1 for i in issues if i['issue'] == 'missing_value'),
        'missing_close_date': sum(1 for i in issues if i['issue'] == 'missing_close_date'),
        'stale': sum(1 for i in issues if i['issue'] == 'stale'),
        'duplicate': sum(1 for i in issues if i['issue'] == 'duplicate'),
    }
    
    return {
        'score': score,
        'total_records': total_records,
        'issue_count': len(issues),
        'error_count': error_count,
        'warning_count': warning_count,
        'issues': issues[:50],  # Cap at 50 for performance
        'summary': summary,
    }

# ---------------------------------------------------------------------------
# Daily Brief
# ---------------------------------------------------------------------------

def get_daily_brief() -> Dict[str, Any]:
    """Generate a daily business briefing from real data."""
    kpis = compute_kpis()
    contacts = get_contacts()
    opportunities = get_opportunities()
    revenue = get_revenue_records()
    referrals = get_referral_sources()
    actions = get_actions(status='pending', limit=20)
    config = get_business_config()
    dq = compute_data_quality()
    
    # Business health score
    health_score = kpis.get('conversion_rate', 80)
    if kpis.get('data_source') == 'real':
        health_score += 20
    if kpis.get('revenue_goal', 0) > 0:
        goal_progress = (kpis['revenue_mtd'] / kpis['revenue_goal']) * 100
        health_score = int((health_score + min(goal_progress, 100)) / 2)
    else:
        health_score = 65  # Default when no goal set
    
    # Top priority - highest priority pending action
    top_priority = None
    if actions:
        top_priority = actions[0]
    
    # Biggest opportunity - highest value active opp
    active_opps = [o for o in opportunities if o.get('stage') not in ('closed_won', 'closed_lost')]
    biggest_opp = max(active_opps, key=lambda o: float(o.get('estimated_value', 0))) if active_opps else None
    
    # Revenue forecast vs goal
    revenue_goal = float(config.get('revenue_goal', 0) or 0)
    revenue_mtd = kpis['revenue_mtd']
    revenue_forecast = kpis['revenue_forecast']
    revenue_gap = revenue_goal - revenue_mtd - revenue_forecast if revenue_goal else 0
    
    # Needs attention - top 3 issues
    needs_attention = []
    if dq['error_count'] > 0:
        needs_attention.append(f"{dq['error_count']} data quality errors need fixing")
    stale_contacts = [c for c in contacts if c.get('pipeline_stage') == 'new' and c.get('contact_type') == 'lead']
    if stale_contacts:
        needs_attention.append(f"{len(stale_contacts)} new leads have not been contacted yet")
    stuck_opps = [o for o in active_opps if o.get('stage') == 'contacted']
    if stuck_opps:
        needs_attention.append(f"{len(stuck_opps)} opportunities are stuck in 'contacted' stage")
    if not needs_attention:
        needs_attention.append("No critical issues detected")
    
    # Recommended actions
    recommendations = []
    if biggest_opp:
        recommendations.append({
            'title': f"Follow up on {biggest_opp.get('product_type', 'opportunity')}",
            'impact': f"Potential value: ${biggest_opp.get('estimated_value', 0):.0f}",
            'entity': biggest_opp.get('opp_id', ''),
            'type': 'opportunity_followup',
        })
    if stale_contacts:
        first = stale_contacts[0]
        recommendations.append({
            'title': f"Contact new lead: {first.get('first_name', '')} {first.get('last_name', '')}",
            'impact': 'New leads have 5x higher conversion rate when contacted within 24 hours',
            'entity': first.get('contact_id', ''),
            'type': 'lead_contact',
        })
    active_referrals = [r for r in referrals if r.get('status') == 'active' and int(r.get('relationship_strength', 0)) > 70]
    if active_referrals:
        first_r = active_referrals[0]
        recommendations.append({
            'title': f"Reach out to referral partner: {first_r.get('source_name', '')}",
            'impact': f"Has generated {first_r.get('referrals_generated', 0)} referrals",
            'entity': first_r.get('source_id', ''),
            'type': 'referral_outreach',
        })
    
    # Estimated time
    est_time = len(recommendations) * 15  # 15 min per action
    
    return {
        'date': date.today().isoformat(),
        'business_name': config.get('business_name', 'Your Business'),
        'health_score': min(health_score, 100),
        'health_status': 'excellent' if health_score >= 80 else 'good' if health_score >= 60 else 'needs_attention' if health_score >= 40 else 'critical',
        'top_priority': top_priority,
        'biggest_opportunity': {
            'opp_id': biggest_opp.get('opp_id') if biggest_opp else None,
            'product_type': biggest_opp.get('product_type') if biggest_opp else None,
            'estimated_value': biggest_opp.get('estimated_value') if biggest_opp else None,
            'stage': biggest_opp.get('stage') if biggest_opp else None,
        } if biggest_opp else None,
        'revenue_forecast': {
            'goal': revenue_goal,
            'mtd': revenue_mtd,
            'forecast': revenue_forecast,
            'gap': max(0, revenue_gap),
            'on_track': revenue_gap <= 0 if revenue_goal else True,
        },
        'needs_attention': needs_attention[:3],
        'recommended_actions': recommendations,
        'estimated_time_minutes': est_time,
        'kpis': kpis,
    }

# ---------------------------------------------------------------------------
# Revenue Gap Recovery
# ---------------------------------------------------------------------------

def get_revenue_gap_recovery() -> Dict[str, Any]:
    """Analyze revenue gap and generate prioritized recovery plan."""
    kpis = compute_kpis()
    goal = kpis.get('revenue_goal', 0)
    mtd = kpis.get('revenue_mtd', 0)
    forecast = kpis.get('revenue_forecast', 0)
    gap = max(0, goal - mtd - forecast)
    
    if gap <= 0:
        return {
            'goal': goal, 'mtd': mtd, 'forecast': forecast, 'gap': 0,
            'on_track': True,
            'recovery_actions': [],
            'message': 'You are on track to meet your revenue goal.'
        }
    
    opportunities = get_opportunities()
    contacts = get_contacts()
    referrals = get_referral_sources()
    
    recovery_actions = []
    remaining_gap = gap
    
    # 1. High-value open opportunities
    active_opps = sorted(
        [o for o in opportunities if o.get('stage') not in ('closed_won', 'closed_lost')],
        key=lambda o: float(o.get('estimated_value', 0)),
        reverse=True
    )
    for opp in active_opps[:3]:
        val = float(opp.get('estimated_value', 0))
        if val > 0 and remaining_gap > 0:
            recovery_actions.append({
                'priority': len(recovery_actions) + 1,
                'action': f"Close opportunity: {opp.get('product_type', 'Unknown')}",
                'entity_id': opp.get('opp_id', ''),
                'potential_revenue': val,
                'type': 'opportunity',
                'is_guaranteed': False,
                'description': f"Stage: {opp.get('stage', 'unknown')}, Value: ${val:.0f}",
            })
            remaining_gap -= val
    
    # 2. Stale leads
    stale_leads = [c for c in contacts if c.get('contact_type') == 'lead' and c.get('pipeline_stage') == 'new']
    for lead in stale_leads[:2]:
        est_val = 500  # Estimated value of a converted lead
        if remaining_gap > 0:
            recovery_actions.append({
                'priority': len(recovery_actions) + 1,
                'action': f"Follow up with lead: {lead.get('first_name', '')} {lead.get('last_name', '')}",
                'entity_id': lead.get('contact_id', ''),
                'potential_revenue': est_val,
                'type': 'lead',
                'is_guaranteed': False,
                'description': f"Source: {lead.get('lead_source', 'Unknown')}",
            })
            remaining_gap -= est_val
    
    # 3. Referral partner reactivation
    dormant_referrals = [r for r in referrals if r.get('status') == 'dormant']
    for ref in dormant_referrals[:2]:
        est_val = float(ref.get('total_revenue_generated', 0)) * 0.3 if ref.get('total_revenue_generated') else 400
        if remaining_gap > 0:
            recovery_actions.append({
                'priority': len(recovery_actions) + 1,
                'action': f"Reactivate referral partner: {ref.get('source_name', '')}",
                'entity_id': ref.get('source_id', ''),
                'potential_revenue': est_val,
                'type': 'referral',
                'is_guaranteed': False,
                'description': f"Previous referrals: {ref.get('referrals_generated', 0)}",
            })
            remaining_gap -= est_val
    
    # 4. Client referral requests
    clients = [c for c in contacts if c.get('contact_type') == 'client']
    if clients and remaining_gap > 0:
        est_val = min(500, remaining_gap)
        recovery_actions.append({
            'priority': len(recovery_actions) + 1,
            'action': f"Request referrals from {len(clients)} existing clients",
            'entity_id': '',
            'potential_revenue': est_val,
            'type': 'client_referral',
            'is_guaranteed': False,
            'description': f"Average client referral value: ~${est_val / max(len(clients), 1):.0f} per client",
        })
        remaining_gap -= est_val
    
    total_recoverable = sum(a['potential_revenue'] for a in recovery_actions)
    
    return {
        'goal': goal,
        'mtd': mtd,
        'forecast': forecast,
        'gap': gap,
        'on_track': False,
        'total_recoverable': total_recoverable,
        'gap_after_recovery': max(0, gap - total_recoverable),
        'recovery_actions': recovery_actions,
    }

# ---------------------------------------------------------------------------
# Weekly Wins
# ---------------------------------------------------------------------------

def get_weekly_wins() -> Dict[str, Any]:
    """Summarize positive business activity from the past 7 days."""
    today = date.today()
    week_ago = today - timedelta(days=7)
    
    contacts = get_contacts()
    opportunities = get_opportunities()
    revenue = get_revenue_records()
    
    wins = []
    
    # New clients this week
    new_clients = [c for c in contacts if c.get('contact_type') == 'client'
                   and c.get('client_since', '') >= week_ago.isoformat()]
    if new_clients:
        wins.append({'type': 'new_clients', 'count': len(new_clients),
                     'message': f"{len(new_clients)} new client(s) this week"})
    
    # Revenue received this week
    week_revenue = [r for r in revenue if str(r.get('revenue_date', '')) >= week_ago.isoformat()]
    if week_revenue:
        total = sum(float(r.get('amount', 0)) for r in week_revenue)
        wins.append({'type': 'revenue', 'count': len(week_revenue), 'amount': total,
                     'message': f"${total:.0f} in revenue received this week"})
    
    # New opportunities
    new_opps = [o for o in opportunities if str(o.get('created_date', '')) >= week_ago.isoformat()]
    if new_opps:
        wins.append({'type': 'new_opportunities', 'count': len(new_opps),
                     'message': f"{len(new_opps)} new opportunity(ies) created"})
    
    # Closed won
    won = [o for o in opportunities if o.get('stage') == 'closed_won']
    if won:
        wins.append({'type': 'opportunities_closed', 'count': len(won),
                     'message': f"{len(won)} opportunity(ies) closed"})
    
    if not wins:
        wins.append({'type': 'none', 'count': 0,
                     'message': 'No wins recorded yet this week. Import your data to track progress.'})
    
    return {
        'week_of': week_ago.isoformat(),
        'wins': wins,
        'total_wins': len([w for w in wins if w['type'] != 'none']),
    }
