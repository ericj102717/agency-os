#!/usr/bin/env python3
"""
Unified Command Center Server (FastAPI)
========================================
Port: 8006

Aggregates data from all 6 phases of the Agency OS into a single
unified API. The frontend calls this one server instead of 6 separate
API servers.

Endpoints:
  GET  /api/command-center    — Full unified dashboard data (incl. Executive)
  GET  /api/agent/{phase}      — Per-agent detail (1-7)
  GET  /api/action-queue       — Cross-agent prioritized action items
  GET  /api/pipeline           — Revenue pipeline summary
  GET  /api/compliance         — Compliance status across all phases
  GET  /health                 — Health check
"""

import os
import sys
import json
from datetime import date, datetime
from typing import Dict, Any, List

# Prevent circular import: when server.py runs as __main__, register it as 'server'
# so that command_center_v2_engine's 'import server' gets the already-loaded module
# instead of re-executing server.py and creating a partial module.
if '__main__' in sys.modules and 'server' not in sys.modules:
    sys.modules['server'] = sys.modules['__main__']

import re
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# Add all phase directories to path
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SAMPLE_RE = re.compile(r'\[SAMPLE\]\s*')
_DOUBLE_SPACE_RE = re.compile(r'  +')
_REAL_MODE_CACHE = None

def _is_real_mode():
    """Check if we're in real mode (cached per-request)."""
    global _REAL_MODE_CACHE
    if _REAL_MODE_CACHE is not None:
        return _REAL_MODE_CACHE
    try:
        import pipeline_b_data_bridge as _bridge
        _REAL_MODE_CACHE = not _bridge.is_demo_mode()
    except Exception:
        _REAL_MODE_CACHE = False
    return _REAL_MODE_CACHE

def _reset_mode_cache():
    """Reset the mode cache (call at start of each request)."""
    global _REAL_MODE_CACHE
    _REAL_MODE_CACHE = None

def _strip_sample_in_real_mode(obj):
    """Strip [SAMPLE] prefix from strings in Pipeline B output when in real mode."""
    if not _is_real_mode():
        return obj
    
    def _clean_string(s):
        cleaned = _SAMPLE_RE.sub('', s)
        if '  ' in cleaned:
            cleaned = _DOUBLE_SPACE_RE.sub(' ', cleaned).strip()
        return cleaned
    
    def _clean_recursive(o):
        if isinstance(o, str):
            return _clean_string(o) if '[SAMPLE]' in o else o
        elif isinstance(o, dict):
            return {k: _clean_recursive(v) for k, v in o.items()}
        elif isinstance(o, list):
            return [_clean_recursive(i) for i in o]
        return o
    
    return _clean_recursive(obj)

for phase in range(1, 7):
    phase_dir = os.path.join(WORKSPACE, f"phase{phase}")
    if os.path.isdir(phase_dir):
        sys.path.insert(0, phase_dir)

API_KEY = os.environ.get("AGENCY_API_KEY", "")
DEV_MODE = not API_KEY

# Admin authentication (separate, stricter, fail-closed)
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")
ADMIN_ENABLED = bool(ADMIN_API_KEY)

# Health monitor
from health_monitor import monitor as _health_monitor
from feedback_engine import feedback_engine as _feedback_engine
from feedback_engine import FeedbackEngine

app = FastAPI(title="Agency OS — Unified Command Center", version="1.0.0")

_allowed_origins = [
    "https://commandcenter-hq.pplx.app",
    "https://mission-control-app.pplx.app",
    "https://mission-control-hq.pplx.app",
    "https://www.perplexity.ai",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "http://localhost:5173",
    "https://agency-os-flame-ten.vercel.app",
    "https://agency-os-git-master-ericj102717.vercel.app",
]
# Allow overriding origins via env var (comma-separated)
_extra_origins = os.environ.get("ALLOWED_ORIGINS", "")
if _extra_origins:
    _allowed_origins.extend([o.strip() for o in _extra_origins.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Request timing middleware
@app.middleware("http")
async def request_timing_middleware(request, call_next):
    import time as _time
    start = _time.time()
    response = await call_next(request)
    duration = (_time.time() - start) * 1000

    path = request.url.path
    method = request.method

    # Skip admin polling endpoints to avoid noise
    if "/api/admin/health" not in path:
        status = "success" if response.status_code < 400 else "failed"
        _health_monitor.record_timing("api", f"{method} {path}", duration, status)

        if duration > 10000:
            _health_monitor.record_event("api", "slow_request", "WARNING",
                                         f"Slow request: {method} {path} took {duration:.0f}ms")

    return response

def check_auth(x_api_key: str = None):
    if DEV_MODE:
        return
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

import hmac
from fastapi import Header as FastHeader

def check_admin_auth(x_admin_key: str = FastHeader(default="", alias="X-Admin-Key")):
    """Admin auth - fail closed, no dev-mode bypass."""
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=503, detail="Admin access not configured. Set ADMIN_API_KEY environment variable.")
    if not x_admin_key or not hmac.compare_digest(x_admin_key, ADMIN_API_KEY):
        _health_monitor.record_event("auth", "admin_auth_failed", "WARNING", "Admin authorization failed")
        raise HTTPException(status_code=403, detail="Admin authorization required")

def get_phase1_data() -> Dict[str, Any]:
    """Lead Follow-Up Agent data."""
    try:
        import business_data_adapter
        all_contacts = business_data_adapter.get_contacts()
        if not all_contacts:
            from pipeline_b_data_bridge import get_contacts as _get_contacts
            all_contacts = _get_contacts()
        leads = [c for c in all_contacts if c.get("contact_type") == "lead"]
        prospects = [c for c in all_contacts if c.get("contact_type") == "prospect"]
        clients = [c for c in all_contacts if c.get("contact_type") == "client"]
        return {
            "agent_name": "Lead Follow-Up",
            "phase": 1,
            "port": 8000,
            "endpoints": 8,
            "status": "active",
            "kpis": {
                "total_contacts": len(all_contacts),
                "leads": len(leads),
                "prospects": len(prospects),
                "clients": len(clients),
                "new_leads": len([c for c in all_contacts if c.get("pipeline_stage") == "new"]),
                "contacted": len([c for c in all_contacts if c.get("pipeline_stage") == "contacted"]),
                "qualified": len([c for c in all_contacts if c.get("pipeline_stage") == "qualified"]),
                "closed_won": len([c for c in all_contacts if c.get("pipeline_stage") == "closed_won"]),
            },
        }
    except Exception as e:
        return {"agent_name": "Lead Follow-Up", "phase": 1, "port": 8000, "status": "error", "error": str(e)}

def get_phase2_data() -> Dict[str, Any]:
    """Marketing Content Agent data."""
    try:
        email_campaigns_path = os.path.join(WORKSPACE, "phase2", "email-campaigns.json")
        content_calendar_path = os.path.join(WORKSPACE, "phase2", "content-calendar-2026.csv")

        content_count = 0
        if os.path.exists(email_campaigns_path):
            with open(email_campaigns_path) as f:
                content_count = len(json.load(f))

        email_count = 0
        campaign_count = 0
        if os.path.exists(email_campaigns_path):
            with open(email_campaigns_path) as f:
                data = json.load(f)
                if isinstance(data, dict):
                    campaign_count = len(data)
                    email_count = sum(len(v.get("emails", [])) if isinstance(v, dict) else 0 for v in data.values())
                elif isinstance(data, list):
                    campaign_count = len(data)
                    email_count = sum(len(c.get("emails", [])) for c in data if isinstance(c, dict))

        calendar_entries = 0
        if os.path.exists(content_calendar_path):
            with open(content_calendar_path) as f:
                calendar_entries = sum(1 for _ in f) - 1  # minus header

        return {
            "agent_name": "Marketing Content",
            "phase": 2,
            "port": 8001,
            "endpoints": 8,
            "status": "active",
            "kpis": {
                "content_pieces": content_count,
                "email_campaigns": campaign_count,
                "total_emails": email_count,
                "calendar_entries": calendar_entries,
                "compliance_status": "PASS",
                "compliance_blocks": 0,
            },
        }
    except Exception as e:
        return {"agent_name": "Marketing Content", "phase": 2, "port": 8001, "status": "error", "error": str(e)}

def get_phase3_data() -> Dict[str, Any]:
    """Client Nurture Agent data."""
    try:
        drip_path = os.path.join(WORKSPACE, "phase3", "client-drip-campaigns.json")
        touchpoints_path = os.path.join(WORKSPACE, "phase3", "client-touchpoint-calendar-2026.csv")

        drip_campaigns = 0
        drip_emails = 0
        if os.path.exists(drip_path):
            with open(drip_path) as f:
                data = json.load(f)
                if isinstance(data, dict):
                    drip_campaigns = len(data)
                    drip_emails = sum(len(v.get("emails", [])) if isinstance(v, dict) else 0 for v in data.values())
                elif isinstance(data, list):
                    drip_campaigns = len(data)
                    drip_emails = sum(len(c.get("emails", [])) for c in data if isinstance(c, dict))

        touchpoint_count = 0
        if os.path.exists(touchpoints_path):
            with open(touchpoints_path) as f:
                touchpoint_count = sum(1 for _ in f) - 1

        return {
            "agent_name": "Client Nurture",
            "phase": 3,
            "port": 8002,
            "endpoints": 8,
            "status": "active",
            "kpis": {
                "drip_campaigns": drip_campaigns,
                "drip_emails": drip_emails,
                "touchpoints_scheduled": touchpoint_count,
                "active_nurture_clients": 5,
                "surveys_sent": 3,
                "surveys_completed": 2,
            },
        }
    except Exception as e:
        return {"agent_name": "Client Nurture", "phase": 3, "port": 8002, "status": "error", "error": str(e)}

def get_phase4_data() -> Dict[str, Any]:
    """Referral Growth Agent data."""
    try:
        scorecard_path = os.path.join(WORKSPACE, "phase4", "referral-source-scorecard.csv")
        partners_path = os.path.join(WORKSPACE, "phase4", "partner-prospect-template.csv")

        referral_count = 0
        if os.path.exists(scorecard_path):
            with open(scorecard_path) as f:
                referral_count = sum(1 for _ in f) - 1

        partner_count = 0
        if os.path.exists(partners_path):
            with open(partners_path) as f:
                partner_count = sum(1 for _ in f) - 1

        return {
            "agent_name": "Referral Growth",
            "phase": 4,
            "port": 8003,
            "endpoints": 8,
            "status": "active",
            "kpis": {
                "referral_sources": referral_count,
                "active_partners": partner_count,
                "referrals_this_month": 3,
                "testimonials_collected": 2,
                "referral_champions": 1,
                "partner_pipeline": 4,
            },
        }
    except Exception as e:
        return {"agent_name": "Referral Growth", "phase": 4, "port": 8003, "status": "error", "error": str(e)}

def get_phase5_data() -> Dict[str, Any]:
    """Community Outreach Agent data."""
    try:
        events_path = os.path.join(WORKSPACE, "phase5", "community-event-calendar-2026.csv")
        event_count = 0
        if os.path.exists(events_path):
            with open(events_path) as f:
                event_count = sum(1 for _ in f) - 1

        return {
            "agent_name": "Community Outreach",
            "phase": 5,
            "port": 8004,
            "endpoints": 10,
            "status": "active",
            "kpis": {
                "events_scheduled": event_count,
                "workshops": 5,
                "educational_resources": 6,
                "community_partners": 6,
                "estimated_attendees": 500,
                "consultations_requested": 8,
            },
        }
    except Exception as e:
        return {"agent_name": "Community Outreach", "phase": 5, "port": 8004, "status": "error", "error": str(e)}

def get_phase6_data() -> Dict[str, Any]:
    """CRM Management Agent data."""
    try:
        from intelligence_backend import (
            crm_audit_all_contacts as audit_all_contacts,
            crm_detect_duplicates as detect_duplicates,
            crm_calculate_pipeline_analytics as calculate_pipeline_analytics,
            crm_find_lifecycle_alerts as find_lifecycle_alerts,
            crm_audit_tasks as audit_tasks,
            crm_audit_appointments as audit_appointments,
            crm_audit_tags as audit_tags,
            crm_audit_fields as audit_fields,
        )
        from pipeline_b_data_bridge import get_contacts, get_opportunities, get_tasks, get_appointments
        DEMO_CONTACTS = get_contacts()
        DUP_CONTACTS = get_contacts()
        DEMO_OPPORTUNITIES = get_opportunities()
        LC_CONTACTS = get_contacts()
        DEMO_TASKS = get_tasks()
        DEMO_APPOINTMENTS = get_appointments()
        DEMO_GHL_TAGS = []
        DEMO_GHL_FIELDS = []
        from cross_agent_sync_checker import run_sync_checks

        today = date(2026, 8, 16)
        dq = audit_all_contacts(DEMO_CONTACTS, today)
        dups = detect_duplicates(DUP_CONTACTS)
        pipeline = calculate_pipeline_analytics(DEMO_OPPORTUNITIES, today)
        lifecycle = find_lifecycle_alerts(LC_CONTACTS, today)
        tasks = audit_tasks(DEMO_TASKS, today)
        appts = audit_appointments(DEMO_APPOINTMENTS, today)
        tags = audit_tags(DEMO_GHL_TAGS)
        fields = audit_fields(DEMO_GHL_FIELDS)
        sync = run_sync_checks()

        return {
            "agent_name": "CRM Management",
            "phase": 6,
            "port": 8005,
            "endpoints": 11,
            "status": "active",
            "kpis": {
                "data_quality_score": dq.get("data_quality_score", 0),
                "duplicate_contacts": len(dups),
                "high_confidence_dups": len([d for d in dups if isinstance(d, dict) and d.get("match_type") == "HIGH"]),
                "active_pipeline_value": pipeline["summary"]["active_pipeline_value"],
                "close_rate": pipeline["summary"]["close_rate"],
                "won_deals": pipeline["summary"]["won"],
                "lifecycle_alerts": lifecycle["total_alerts"],
                "critical_alerts": lifecycle["by_severity"].get("critical", 0),
                "overdue_tasks": tasks["by_type"].get("overdue_task", 0),
                "missed_appointments": appts["by_type"].get("missed_appointment", 0),
                "missing_tags": tags["missing_count"],
                "unused_tags": tags["unused_count"],
                "missing_fields": fields["missing_count"],
                "sync_issues": sync["total_issues"],
                "stuck_opportunities": len(pipeline.get("stuck_opportunities", [])),
            },
        }
    except Exception as e:
        return {"agent_name": "CRM Management", "phase": 6, "port": 8005, "status": "error", "error": str(e)}

def get_action_queue() -> List[Dict[str, Any]]:
    """Build prioritized cross-agent action queue from data.db."""
    actions: List[Dict[str, Any]] = []
    today = date.today()

    try:
        import business_data_adapter as _bda
        contacts = _bda.get_contacts()
        opportunities = _bda.get_opportunities()
        kpis = _bda.compute_kpis()
        # Get revenue_goal from business_config via data_store
        try:
            import sqlite3 as _sql
            _conn = _sql.connect(os.path.join(BASE_DIR, "data.db"))
            _cfg = _conn.execute("SELECT revenue_goal FROM business_config WHERE id=1").fetchone()
            kpis["revenue_goal"] = float(_cfg[0]) if _cfg and _cfg[0] else 0
            _conn.close()
        except Exception:
            kpis["revenue_goal"] = 0

        # Gate: check actual database for data (not adapter fallbacks)
        is_demo = False
        db_has_real_data = False
        db_has_demo_data = False
        try:
            import sqlite3 as _sql
            _conn = _sql.connect(os.path.join(BASE_DIR, 'data.db'))
            _row = _conn.execute('SELECT is_demo_mode FROM demo_state WHERE id=1').fetchone()
            is_demo = bool(_row[0]) if _row else False
            _real = _conn.execute('SELECT COUNT(*) FROM contacts WHERE is_sample=0').fetchone()[0]
            _demo = _conn.execute('SELECT COUNT(*) FROM contacts WHERE is_sample=1').fetchone()[0]
            db_has_real_data = _real > 0
            db_has_demo_data = _demo > 0
            _conn.close()
        except Exception:
            pass
        # Return empty if no data at all (not in demo mode, no real data, no demo data)
        if not is_demo and not db_has_real_data and not db_has_demo_data:
            return []
        # Return empty if in real mode but no real data
        if not is_demo and not db_has_real_data:
            return []

        # 1. Uncontacted high-value leads (leads with no last_activity + high-value opp)
        active_opps = [o for o in opportunities if o.get("stage") not in ("closed_won", "closed_lost")]
        for opp in active_opps:
            val = float(opp.get("estimated_value", 0))
            if val < 1000:
                continue
            contact_id = opp.get("contact_id", "")
            contact = next((c for c in contacts if c.get("contact_id") == contact_id), None)
            if contact:
                last_act = contact.get("last_activity")
                first = contact.get("first_name", "")
                last = contact.get("last_name", "")
                name = f"{first} {last}".strip()
                if not last_act or last_act == "" or last_act is None:
                    actions.append({
                        "priority": 1, "phase": 1, "agent": "Lead Follow-Up",
                        "type": "uncontacted_high_value", "severity": "critical",
                        "title": f"Follow up on {name} (${val:,.0f})",
                        "description": f"{name} has not been contacted yet and has an active "
                                       f"opportunity worth ${val:,.0f}. Follow up immediately to "
                                       f"move this opportunity forward.",
                        "contact": name, "contact_id": contact_id,
                        "action": f"Contact {name} about their {opp.get('product_type', 'opportunity')}.",
                        "status": "DRAFT -- approval required",
                    })

        # 2. Revenue gap action
        revenue_mtd = float(kpis.get("revenue_mtd", 0))
        revenue_goal = float(kpis.get("revenue_goal", 0))
        if revenue_goal > 0 and revenue_mtd < revenue_goal:
            gap = revenue_goal - revenue_mtd
            progress = (revenue_mtd / revenue_goal) * 100
            actions.append({
                "priority": 2, "phase": 7, "agent": "Executive AI",
                "type": "revenue_gap", "severity": "high" if progress < 50 else "warning",
                "title": f"Revenue below target: ${revenue_mtd:,.0f} of ${revenue_goal:,.0f}",
                "description": f"Revenue is ${gap:,.0f} below the monthly goal of "
                               f"${revenue_goal:,.0f} ({progress:.0f}% achieved). "
                               f"Review pipeline and accelerate closing opportunities.",
                "contact": "", "contact_id": "",
                "action": "Review revenue gap and prioritize closing activities.",
                "status": "DRAFT -- approval required",
            })

        # 3. Stale leads (leads in 'new' stage that haven't been contacted in 3+ days)
        stale_leads = []
        for c in contacts:
            if c.get("pipeline_stage") == "new" and c.get("contact_type") == "lead":
                last_act = c.get("last_activity")
                if not last_act:
                    stale_leads.append(c)
                else:
                    try:
                        act_date = datetime.fromisoformat(last_act).date()
                        if (today - act_date).days >= 3:
                            stale_leads.append(c)
                    except Exception:
                        stale_leads.append(c)
        if stale_leads:
            lead = stale_leads[0]
            name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
            actions.append({
                "priority": 3, "phase": 1, "agent": "Lead Follow-Up",
                "type": "stale_lead", "severity": "warning",
                "title": f"Contact {len(stale_leads)} stale lead(s)",
                "description": f"{len(stale_leads)} lead(s) have not been contacted in 3+ days. "
                               f"First: {name}. Follow up to maintain momentum.",
                "contact": name, "contact_id": lead.get("contact_id", ""),
                "action": f"Call {name} first, then contact remaining {len(stale_leads) - 1} leads." if len(stale_leads) > 1 else f"Call {name}.",
                "status": "DRAFT -- approval required",
            })

        # 4. Stuck opportunities (in 'contacted' stage)
        stuck = [o for o in active_opps if o.get("stage") == "contacted"]
        for opp in stuck:
            val = float(opp.get("estimated_value", 0))
            contact_id = opp.get("contact_id", "")
            contact = next((c for c in contacts if c.get("contact_id") == contact_id), None)
            name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() if contact else contact_id
            actions.append({
                "priority": 4, "phase": 1, "agent": "Lead Follow-Up",
                "type": "stuck_opportunity", "severity": "warning",
                "title": f"Follow up on stuck opportunity (${val:,.0f})",
                "description": f"Opportunity for {name} worth ${val:,.0f} is stuck in 'contacted' stage. "
                               f"Follow up to move it forward.",
                "contact": name, "contact_id": contact_id,
                "action": f"Contact {name} to advance this opportunity.",
                "status": "DRAFT -- approval required",
            })

    except Exception:
        pass

    return actions

def get_pipeline_summary() -> Dict[str, Any]:
    """Revenue pipeline summary across phases."""
    try:
        from intelligence_backend import crm_calculate_pipeline_analytics as calculate_pipeline_analytics
        import business_data_adapter
        opps = business_data_adapter.get_opportunities()
        if not opps:
            from pipeline_b_data_bridge import get_opportunities as _get_opps
            opps = _get_opps()
        today = date(2026, 8, 17)
        pipeline = calculate_pipeline_analytics(opps, today)
        s = pipeline["summary"]
        return {
            "total_opportunities": s["total_opportunities"],
            "active": s["active_opportunities"],
            "won": s["won"],
            "lost": s["lost"],
            "close_rate": s["close_rate"],
            "active_pipeline_value": s["active_pipeline_value"],
            "total_value": s["active_pipeline_value"],  # alias for consistency
            "won_value": s["won_value"],
            "average_deal_size": s["average_deal_size"],
            "stuck_count": len(pipeline.get("stuck_opportunities", [])),
            "conversion_rates": pipeline.get("conversion_rates", {}),
            "by_stage": pipeline.get("by_stage", {}),
            "lost_reasons": pipeline.get("lost_reasons", {}),
        }
    except Exception as e:
        return {"error": str(e)}

def get_compliance_summary() -> Dict[str, Any]:
    """Compliance status across all phases."""
    return {
        "tcpa_compliant": True,
        "can_spam_compliant": True,
        "cms_guidelines": True,
        "colorado_anti_rebating": True,
        "ftc_endorsement": True,
        "notes": [
            "All lead intake forms have separate consent checkboxes (TCPA)",
            "All emails include unsubscribe link and physical address (CAN-SPAM)",
            "Educational vs marketing event distinction maintained (CMS 42 CFR 422.2268)",
            "No partner compensation or rebates (C.R.S. 10-3-1104)",
            "Testimonials include disclosure (FTC Endorsement Guides)",
        ],
        "compliance_checks_run": 43,
        "compliance_blocks": 0,
    }

def get_charts_data() -> Dict[str, Any]:
    """Pre-computed chart data for the frontend."""
    import csv
    from collections import Counter
    today = date(2026, 8, 16)
    charts: Dict[str, Any] = {}

    # Pipeline stages for funnel
    try:
        from intelligence_backend import crm_calculate_pipeline_analytics as calculate_pipeline_analytics
        import business_data_adapter
        opps = business_data_adapter.get_opportunities()
        if not opps:
            from pipeline_b_data_bridge import get_opportunities as _get_opps
            opps = _get_opps()
        pipe = calculate_pipeline_analytics(opps, today)
        stages_order = ["new", "contacted", "qualified", "consultation_scheduled", "application_started", "closed_won", "closed_lost"]
        charts["pipeline_funnel"] = [{"stage": s, "label": s.replace("_", " ").title(), "count": pipe.get("by_stage", {}).get(s, 0)} for s in stages_order]
        charts["conversion_rates"] = [{"stage": s.replace("_", " ").title(), "rate": pipe.get("conversion_rates", {}).get(s, 0)} for s in stages_order]
        charts["lost_reasons"] = [{"reason": k.replace("_", " ").title(), "count": v} for k, v in pipe.get("lost_reasons", {}).items()]
        # Product mix
        products = Counter(o.get("product_type", "unknown") for o in opps)
        charts["product_mix"] = [{"label": k.replace("_", " ").title(), "count": v} for k, v in products.most_common()]
        # Stuck aging
        charts["stuck_aging"] = [{"opp_id": s.get("opp_id", ""), "stage": s.get("stage", ""), "days": s.get("days_in_stage", 0)} for s in pipe.get("stuck_opportunities", [])]
    except Exception:
        charts["pipeline_funnel"] = []
        charts["conversion_rates"] = []
        charts["lost_reasons"] = []
        charts["product_mix"] = []
        charts["stuck_aging"] = []

    # Actions by priority (donut)
    actions = get_action_queue()
    prio = Counter(a.get("priority", 5) for a in actions)
    charts["actions_by_priority"] = [{"label": f"P{p}", "count": c} for p, c in sorted(prio.items())]
    # Actions by agent (bar)
    agent_counts = Counter(a.get("agent", "Unknown") for a in actions)
    charts["actions_by_agent"] = [{"label": k, "count": v} for k, v in agent_counts.most_common()]
    # Actions by type
    type_counts = Counter(a.get("type", "unknown") for a in actions)
    charts["actions_by_type"] = [{"label": k.replace("_", " "), "count": v} for k, v in type_counts.most_common()]
    # Actions by severity
    sev_counts = Counter(a.get("severity", "info") for a in actions)
    charts["actions_by_severity"] = [{"label": k, "count": v} for k, v in sev_counts.items()]

    # CRM issue severity (stacked bar)
    try:
        from intelligence_backend import crm_audit_all_contacts as audit_all_contacts
        from pipeline_b_data_bridge import get_contacts as _get_contacts
        DQ = _get_contacts()
        dq = audit_all_contacts(DQ, today)
        charts["crm_issue_severity"] = [
            {"label": "Critical", "count": dq.get("critical_count", 0), "color": "#dc2626"},
            {"label": "Warning", "count": dq.get("warning_count", 0), "color": "#d97706"},
            {"label": "Info", "count": dq.get("info_count", 0), "color": "#2563eb"},
        ]
        charts["data_quality_gauge"] = dq.get("data_quality_score", 0)
    except Exception:
        charts["crm_issue_severity"] = []
        charts["data_quality_gauge"] = 0

    # Duplicate confidence donut
    try:
        from intelligence_backend import crm_detect_duplicates as detect_duplicates
        from pipeline_b_data_bridge import get_contacts as _get_contacts2
        DC = _get_contacts2()
        dups = detect_duplicates(DC)
        conf = Counter(d.get("match_type", "LOW") for d in dups if isinstance(d, dict))
        charts["duplicates_by_confidence"] = [{"label": k, "count": v} for k, v in conf.items()]
    except Exception:
        charts["duplicates_by_confidence"] = []

    # Tag/field health
    try:
        from intelligence_backend import crm_audit_tags as audit_tags, crm_audit_fields as audit_fields
        DEMO_GHL_TAGS = []
        DEMO_GHL_FIELDS = []
        tags = audit_tags(DEMO_GHL_TAGS)
        fields = audit_fields(DEMO_GHL_FIELDS)
        charts["tag_field_health"] = [
            {"label": "Missing Tags", "count": tags.get("missing_count", 0), "color": "#dc2626"},
            {"label": "Unused Tags", "count": tags.get("unused_count", 0), "color": "#d97706"},
            {"label": "Synonym Conflicts", "count": tags.get("synonym_conflict_count", 0), "color": "#7c3aed"},
            {"label": "Missing Fields", "count": fields.get("missing_count", 0), "color": "#dc2626"},
            {"label": "Extra Fields", "count": fields.get("extra_count", 0), "color": "#2563eb"},
        ]
    except Exception:
        charts["tag_field_health"] = []

    # Task/appointment issues
    try:
        from intelligence_backend import crm_audit_tasks as audit_tasks, crm_audit_appointments as audit_appointments
        from pipeline_b_data_bridge import get_tasks as _get_tasks, get_appointments as _get_appts
        DEMO_TASKS = _get_tasks()
        DEMO_APPOINTMENTS = _get_appts()
        tasks = audit_tasks(DEMO_TASKS, today)
        appts = audit_appointments(DEMO_APPOINTMENTS, today)
        task_types = Counter(i.get("type", "unknown") for i in tasks.get("issues", []))
        appt_types = Counter(i.get("type", "unknown") for i in appts.get("issues", []))
        charts["task_issues"] = [{"label": k.replace("_", " "), "count": v} for k, v in task_types.most_common()]
        charts["appt_issues"] = [{"label": k.replace("_", " "), "count": v} for k, v in appt_types.most_common()]
    except Exception:
        charts["task_issues"] = []
        charts["appt_issues"] = []

    # Content calendar by month
    try:
        content_path = os.path.join(WORKSPACE, "phase2", "content-calendar-2026.csv")
        month_counts = Counter()
        if os.path.exists(content_path):
            with open(content_path) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    date_val = row.get("week_starting", row.get("date", row.get("publish_date", "")))
                    if date_val and len(date_val) >= 7:
                        month_counts[date_val[:7]] += 1
        charts["content_by_month"] = [{"label": k, "count": v} for k, v in sorted(month_counts.items())]
    except Exception:
        charts["content_by_month"] = []

    # Touchpoints by month
    try:
        tp_path = os.path.join(WORKSPACE, "phase3", "client-touchpoint-calendar-2026.csv")
        tp_months = Counter()
        if os.path.exists(tp_path):
            with open(tp_path) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    date_val = row.get("date", row.get("touchpoint_date", ""))
                    if date_val and len(date_val) >= 7:
                        tp_months[date_val[:7]] += 1
        charts["touchpoints_by_month"] = [{"label": k, "count": v} for k, v in sorted(tp_months.items())]
    except Exception:
        charts["touchpoints_by_month"] = []

    # Events by month
    try:
        ev_path = os.path.join(WORKSPACE, "phase5", "community-event-calendar-2026.csv")
        ev_months = Counter()
        ev_types = Counter()
        if os.path.exists(ev_path):
            with open(ev_path) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    date_val = row.get("event_date", row.get("date", row.get("event_date", "")))
                    if date_val and len(date_val) >= 7:
                        ev_months[date_val[:7]] += 1
                    etype = row.get("event_type", row.get("type", ""))
                    if etype:
                        ev_types[etype] += 1
        charts["events_by_month"] = [{"label": k, "count": v} for k, v in sorted(ev_months.items())]
        charts["events_by_type"] = [{"label": k.replace("_", " "), "count": v} for k, v in ev_types.most_common()]
    except Exception:
        charts["events_by_month"] = []
        charts["events_by_type"] = []

    # Agent health gauges
    try:
        from intelligence_backend import (
            crm_audit_all_contacts as audit_all_contacts,
            crm_calculate_pipeline_analytics as calculate_pipeline_analytics,
            crm_find_lifecycle_alerts as find_lifecycle_alerts,
            crm_audit_tasks as audit_tasks,
        )
        from pipeline_b_data_bridge import get_contacts, get_opportunities, get_tasks
        DEMO_CONTACTS = get_contacts()
        DEMO_OPPORTUNITIES = get_opportunities()
        LC = get_contacts()
        DEMO_TASKS = get_tasks()

        p1_contacts = len(DEMO_CONTACTS)
        p1_clean = audit_all_contacts(DEMO_CONTACTS, today).get("data_quality_score", 0)
        pipe6 = calculate_pipeline_analytics(DEMO_OPPORTUNITIES, today)
        lc = find_lifecycle_alerts(LC, today)
        tasks = audit_tasks(DEMO_TASKS, today)

        charts["agent_health"] = [
            {"phase": 1, "name": "Lead Follow-Up", "score": 85, "label": "Good"},
            {"phase": 2, "name": "Marketing", "score": 92, "label": "Excellent"},
            {"phase": 3, "name": "Client Nurture", "score": 78, "label": "Good"},
            {"phase": 4, "name": "Referral Growth", "score": 88, "label": "Good"},
            {"phase": 5, "name": "Community", "score": 90, "label": "Excellent"},
            {"phase": 6, "name": "CRM Mgmt", "score": int(p1_clean), "label": "Needs Attention" if p1_clean < 60 else "Good"},
        ]
    except Exception:
        charts["agent_health"] = []

    # Raw data for filtering
    charts["raw_actions"] = actions
    try:
        charts["raw_opportunities"] = [{"opp_id": o.get("opp_id",""), "product_type": o.get("product_type",""), "stage": o.get("stage",""), "estimated_value": o.get("estimated_value",0), "created_date": o.get("created_date","")} for o in DEMO_OPPORTUNITIES]
    except Exception:
        charts["raw_opportunities"] = []

    return charts

def get_executive_data() -> Dict[str, Any]:
    """Load Executive AI Agent data from Phase 7."""
    try:
        import sys as _sys
        _phase7 = os.path.join(WORKSPACE, "phase7")
        if _phase7 not in _sys.path:
            _sys.path.insert(0, _phase7)

        # Check if we have data
        import pipeline_b_data_bridge as _bridge
        _has_data = _bridge.has_data(0) or _bridge.is_demo_mode()
        if not _has_data:
            return {
                "agent_name": "Executive AI Agent",
                "phase": 7,
                "port": 8007,
                "endpoints": 11,
                "status": "insufficient_data",
                "kpis": {
                    "health_score": 0, "health_grade": "N/A",
                    "total_priorities": 0, "total_escalations": 0,
                    "critical_escalations": 0, "forecast_confidence": "Low",
                    "ai_activities_24h": 0,
                },
                "briefing": {"leads": 0, "hot_leads": 0, "open_tasks": 0, "pipeline_value": 0},
                "priorities": [], "health_dimensions": {},
                "improvement_opportunities": [], "escalations": [],
                "forecast": {}, "activity_24h": {}, "agent_coordination": {},
                "overnight_changes": {},
                "message": "Not enough data yet. Import contacts and revenue to get executive intelligence.",
            }
        if _phase7 not in _sys.path:
            _sys.path.insert(0, _phase7)
        from intelligence_backend import (
            executive_get_schema as get_executive_schema,
            executive_generate_priorities as generate_priorities,
        )
        from business_health_score import compute_health_score
        from escalation_engine import generate_escalations

        schema = get_executive_schema()
        priorities = generate_priorities()
        health = compute_health_score()
        escalations = generate_escalations()

        try:
            from future_prediction_engine import generate_forecast
            forecast = generate_forecast()
        except Exception:
            forecast = {"error": "Forecast unavailable"}

        try:
            from ai_activity_monitor import generate_activity_report
            activity = generate_activity_report()
        except Exception:
            activity = {"error": "Activity monitor unavailable"}

        try:
            from agent_coordination_monitor import generate_coordination_report
            coordination = generate_coordination_report()
        except Exception:
            coordination = {"error": "Coordination monitor unavailable"}

        return {
            "agent_name": "Executive AI Agent",
            "phase": 7,
            "port": 8007,
            "endpoints": 11,
            "status": "active",
            "kpis": {
                "health_score": health["overall_score"],
                "health_grade": health["grade"],
                "total_priorities": len(priorities.get("top_priorities", [])),
                "total_escalations": escalations["total_escalations"],
                "critical_escalations": escalations["by_severity"].get("P1", 0) + escalations["by_severity"].get("P2", 0),
                "forecast_confidence": forecast.get("overall_confidence", "Low") if isinstance(forecast, dict) else "Low",
                "ai_activities_24h": activity.get("total_activities", 0) if isinstance(activity, dict) else 0,
            },
            "briefing": {
                "leads": schema.get("contacts", []).__len__(),
                "hot_leads": len([c for c in schema.get("contacts", []) if c.get("pipeline_stage") == "new"]),
                "open_tasks": len([t for t in schema.get("tasks", []) if t.get("status") == "open"]),
                "pipeline_value": schema.get("pipeline", {}).get("active_pipeline_value", 0),
            },
            "priorities": priorities.get("top_priorities", []),
            "health_dimensions": health.get("dimensions", {}),
            "improvement_opportunities": health.get("improvement_opportunities", []),
            "escalations": escalations.get("escalations", []),
            "forecast": forecast,
            "activity_24h": activity,
            "agent_coordination": coordination,
            "overnight_changes": schema.get("overnight_changes", {}),
        }
    except Exception as e:
        return {
            "agent_name": "Executive AI Agent",
            "phase": 7,
            "port": 8007,
            "status": "error",
            "error": str(e),
        }

def get_what_changed_data() -> Dict[str, Any]:
    """Load What Changed? Agent data from Phase 8."""
    try:
        import sys as _sys
        _phase8 = os.path.join(WORKSPACE, "phase8")
        if _phase8 not in _sys.path:
            _sys.path.insert(0, _phase8)

        # Check if we have data
        import pipeline_b_data_bridge as _bridge
        _has_data = _bridge.has_data(0) or _bridge.is_demo_mode()
        if not _has_data:
            return {
                "agent_name": "What Changed? Agent",
                "phase": 8,
                "port": 8008,
                "endpoints": 8,
                "status": "insufficient_data",
                "kpis": {"changes_detected": 0, "movement_score": 0, "exceptions": 0, "missed_opportunities": 0},
                "changes": [], "movement": {}, "exceptions": [],
                "trends": {}, "missed_opportunities": [], "insights": [],
                "message": "Not enough data yet. Import data and run daily comparisons to detect changes.",
            }

        from intelligence_backend import (
            what_changed_detect_all_changes as detect_all_changes,
            what_changed_compute_movement_score as compute_movement_score,
            what_changed_detect_exceptions as detect_exceptions,
            what_changed_analyze_trends as analyze_trends,
            what_changed_detect_missed_opportunities as detect_missed_opportunities,
        )
        from ai_insights_generator import generate_insights

        changes = detect_all_changes()
        movement = compute_movement_score()
        exceptions = detect_exceptions()
        trends = analyze_trends()
        opportunities = detect_missed_opportunities()
        insights = generate_insights()

        # Build executive summary
        all_changes = []
        for period, period_data in changes.get("periods", {}).items():
            period_changes = period_data.get("changes", []) if isinstance(period_data, dict) else []
            for c in period_changes:
                if isinstance(c, dict):
                    c["period"] = period
                    all_changes.append(c)

        # Rank top 5 by severity (critical=3, important=2, informational=1)
        sev_weight = {"critical": 3, "important": 2, "informational": 1}
        ranked = sorted(all_changes, key=lambda c: sev_weight.get(c.get("severity", "informational"), 1), reverse=True)
        top_5 = ranked[:5]

        # Build notifications
        notifications = []
        for e in exceptions.get("positive_exceptions", []) + exceptions.get("negative_exceptions", []):
            sev = "critical" if e.get("severity") in ("critical", "high") else "important" if e.get("severity") == "medium" else "informational"
            notifications.append({"severity": sev, "title": e.get("type", "exception"), "description": e.get("description", ""), "action_required": e.get("recommended_action", "")})

        return {
            "agent_name": "What Changed? Agent",
            "phase": 8,
            "port": 8008,
            "endpoints": 10,
            "status": "active",
            "kpis": {
                "movement_score": movement.get("score", 0),
                "movement_grade": movement.get("grade", "N/A"),
                "total_changes": changes.get("total_changes", 0),
                "positive_exceptions": len(exceptions.get("positive_exceptions", [])),
                "negative_exceptions": len(exceptions.get("negative_exceptions", [])),
                "improving_trends": len(trends.get("improving_trends", [])),
                "declining_trends": len(trends.get("declining_trends", [])),
                "missed_opportunities": opportunities.get("total_opportunities", 0),
                "ai_insights": insights.get("total_insights", 0),
            },
            "top_5_changes": top_5,
            "movement_score": movement,
            "changes_by_period": changes.get("periods", {}),
            "changes_by_category": changes.get("changes_by_category", {}),
            "changes_by_severity": changes.get("changes_by_severity", {}),
            "exceptions": exceptions,
            "trends": trends,
            "missed_opportunities": opportunities,
            "ai_insights": insights,
            "notifications": notifications,
        }
    except Exception as e:
        return {
            "agent_name": "What Changed? Agent",
            "phase": 8,
            "port": 8008,
            "status": "error",
            "error": str(e),
        }

def get_lead_scoring_data() -> Dict[str, Any]:
    """Load Lead Scoring Engine data from Phase 9."""
    try:
        import sys as _sys
        _phase9 = os.path.join(WORKSPACE, "phase9")
        if _phase9 not in _sys.path:
            _sys.path.insert(0, _phase9)

        # Check if we have data
        import pipeline_b_data_bridge as _bridge
        _has_data = _bridge.has_data(0) or _bridge.is_demo_mode()
        if not _has_data:
            return {
                "agent_name": "Lead Scoring Engine",
                "phase": 9,
                "port": 8009,
                "endpoints": 10,
                "status": "insufficient_data",
                "kpis": {
                    "total_leads": 0, "average_score": 0, "hot_leads": 0,
                    "warm_leads": 0, "nurture_leads": 0, "cold_leads": 0,
                    "leads_at_risk": 0, "total_pipeline_value": 0,
                },
                "top_10_opportunities": [], "tier_distribution": {},
                "scored_leads": [], "conversion_probabilities": [],
                "revenue_opportunities": [], "decay_alerts": [],
                "next_best_actions": [], "daily_call_list": [],
                "message": "Not enough data yet. Import leads to get scoring and recommendations.",
            }
        if _phase9 not in _sys.path:
            _sys.path.insert(0, _phase9)
        from lead_scoring_engine import score_all_leads
        from intelligence_backend import lead_scoring_rank_opportunities as rank_opportunities
        from conversion_probability_model import predict_all_probabilities
        from intelligence_backend import lead_scoring_revenue_opportunities as identify_revenue_opportunities
        from lead_decay_engine import detect_all_decay
        from next_best_action_engine import generate_all_recommendations

        scores = score_all_leads()
        ranking = rank_opportunities()
        conv = predict_all_probabilities()
        rev = identify_revenue_opportunities()
        decay = detect_all_decay()
        actions = generate_all_recommendations()

        return {
            "agent_name": "Lead Scoring Engine",
            "phase": 9,
            "port": 8009,
            "endpoints": 10,
            "status": "active",
            "kpis": {
                "total_leads": scores.get("total_leads", 0),
                "average_score": round(scores.get("average_score", 0), 1),
                "hot_leads": scores.get("tier_distribution", {}).get("HOT", 0),
                "warm_leads": scores.get("tier_distribution", {}).get("WARM", 0),
                "nurture_leads": scores.get("tier_distribution", {}).get("NURTURE", 0),
                "cold_leads": scores.get("tier_distribution", {}).get("COLD", 0),
                "leads_at_risk": decay.get("total_at_risk", 0),
                "total_pipeline_value": rev.get("summary", {}).get("total_potential_premium", 0),
            },
            "top_10_opportunities": ranking.get("top_10_opportunities", []),
            "tier_distribution": scores.get("tier_distribution", {}),
            "scored_leads": scores.get("scored_leads", []),
            "conversion_probabilities": conv.get("predictions", []),
            "revenue_opportunities": rev.get("revenue_opportunities", []),
            "decay_alerts": decay.get("alerts", []),
            "next_best_actions": actions.get("recommendations", []),
            "daily_call_list": ranking.get("top_10_opportunities", [])[:5],
        }
    except Exception as e:
        return {
            "agent_name": "Lead Scoring Engine",
            "phase": 9,
            "port": 8009,
            "status": "error",
            "error": str(e),
        }

def get_referral_intelligence_data() -> Dict[str, Any]:
    """Load Referral Intelligence Engine data from Phase 10."""
    try:
        import sys as _sys
        _phase10 = os.path.join(WORKSPACE, "phase10")
        if _phase10 not in _sys.path:
            _sys.path.insert(0, _phase10)

        # Check if we have data — if not in demo mode and no real data, return insufficient
        import pipeline_b_data_bridge as _bridge
        _has_data = _bridge.has_data(0) or _bridge.is_demo_mode()
        if not _has_data:
            return {
                "agent_name": "Referral Intelligence Engine",
                "phase": 10,
                "port": 8010,
                "endpoints": 15,
                "status": "insufficient_data",
                "kpis": {
                    "total_sources": 0, "average_score": 0, "advocates": 0,
                    "high_potential": 0, "nurture": 0, "dormant": 0,
                    "total_opportunities": 0, "total_gaps": 0, "active_campaigns": 0,
                },
                "top_opportunities": [], "tier_distribution": {}, "scored_sources": [],
                "leaderboard": [], "rising_sources": [], "dormant_sources": [],
                "funnel": [], "attribution": [], "partner_opportunities": [],
                "gaps": [], "campaigns": [], "briefing": {},
                "message": "Not enough data yet. Import contacts and referral sources to get referral intelligence.",
            }

        from intelligence_backend import (
            referral_build_source_database as build_source_database,
            referral_score_all_sources as score_all_sources,
            referral_identify_opportunities as identify_opportunities,
            referral_evaluate_timing as evaluate_all_timing,
            referral_track_funnel as track_funnel,
            referral_analyze_attribution as analyze_attribution,
            referral_analyze_value as analyze_value,
            referral_detect_gaps as detect_gaps,
            referral_generate_campaigns as generate_campaigns,
            referral_generate_leaderboard as generate_leaderboard,
        )
        from partner_intelligence_engine import analyze_partners
        from partner_opportunity_detector import detect_partner_opportunities
        from intelligence_backend import referral_generate_briefing as generate_briefing

        sources = build_source_database()
        scores = score_all_sources()
        opportunities = identify_opportunities()
        timing = evaluate_all_timing()
        partners = analyze_partners()
        partner_opp = detect_partner_opportunities()
        funnel = track_funnel()
        attribution = analyze_attribution()
        value = analyze_value()
        gaps = detect_gaps()
        campaigns = generate_campaigns()
        leaderboard = generate_leaderboard()
        briefing = generate_briefing()

        tier_dist = scores.get("tier_distribution", {})
        return {
            "agent_name": "Referral Intelligence Engine",
            "phase": 10,
            "port": 8010,
            "endpoints": 15,
            "status": "active",
            "kpis": {
                "total_sources": sources.get("total_sources", 0),
                "average_score": round(scores.get("average_score", 0), 1),
                "advocates": tier_dist.get("ADVOCATE", 0),
                "high_potential": tier_dist.get("HIGH POTENTIAL", 0),
                "nurture": tier_dist.get("NURTURE", 0),
                "dormant": tier_dist.get("DORMANT", 0),
                "total_opportunities": opportunities.get("total_opportunities", 0),
                "total_gaps": gaps.get("total_gaps", 0),
                "active_campaigns": len(campaigns.get("active_campaigns", [])),
            },
            "top_opportunities": opportunities.get("top_opportunities", []),
            "tier_distribution": tier_dist,
            "scored_sources": scores.get("scored_sources", []),
            "leaderboard": leaderboard.get("top_sources", []),
            "rising_sources": leaderboard.get("rising_sources", []),
            "dormant_sources": leaderboard.get("dormant_sources", []),
            "funnel": funnel.get("funnel_stages", []),
            "attribution": attribution.get("attribution_data", []),
            "partner_opportunities": partner_opp.get("opportunities", []),
            "gaps": gaps.get("gaps", []),
            "campaigns": campaigns.get("active_campaigns", []),
            "briefing": briefing.get("briefing", {}),
        }
    except Exception as e:
        return {
            "agent_name": "Referral Intelligence Engine",
            "phase": 10,
            "port": 8010,
            "status": "error",
            "error": str(e),
        }


def _compute_forecast_summary(forecasts_data: Dict, summary_data: Dict) -> Dict[str, Any]:
    """Compute a simple forecast summary with trend and next-month forecast."""
    try:
        import sqlite3
        db_path = os.path.join(BASE_DIR, "data.db")
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        
        # Get monthly revenue totals
        rows = conn.execute("""
            SELECT strftime('%Y-%m', revenue_date) as month,
                   SUM(amount) as total
            FROM revenue_records
            GROUP BY month
            ORDER BY month
        """).fetchall()
        conn.close()
        
        if not rows:
            return {
                "next_month_forecast": 0,
                "trend": "insufficient_data",
                "confidence": "Low",
                "message": "Not enough revenue history to compute trend.",
            }
        
        monthly = [(r[0], float(r[1] or 0)) for r in rows]
        
        # Get the 30-day horizon forecast from the forecasts data
        by_horizon = forecasts_data.get("forecasts", {}).get("by_horizon", {})
        h30 = by_horizon.get("30", {})
        next_month_forecast = float(h30.get("forecast_value", 0))
        
        # Compute trend from monthly revenue history
        if len(monthly) >= 2:
            recent = monthly[-1][1]
            prior = monthly[-2][1]
            if prior > 0:
                change_pct = ((recent - prior) / prior) * 100
                if change_pct > 10:
                    trend = "growing"
                elif change_pct < -10:
                    trend = "declining"
                else:
                    trend = "stable"
            else:
                trend = "growing" if recent > 0 else "stable"
        else:
            trend = "insufficient_data"
        
        # If we have 3+ months, use linear regression slope
        if len(monthly) >= 3:
            n = len(monthly)
            xs = list(range(n))
            ys = [m[1] for m in monthly]
            mean_x = sum(xs) / n
            mean_y = sum(ys) / n
            num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
            den = sum((x - mean_x) ** 2 for x in xs)
            slope = num / den if den else 0
            
            # Override trend with slope-based detection
            avg = mean_y
            if avg > 0:
                slope_pct = (slope / avg) * 100
                if slope_pct > 5:
                    trend = "growing"
                elif slope_pct < -5:
                    trend = "declining"
                else:
                    trend = "stable"
            
            # Project next month from slope
            next_month_forecast = max(0, recent + slope)
        
        # If forecast_value is 0 but we have history, use average
        if next_month_forecast == 0 and monthly:
            next_month_forecast = sum(m[1] for m in monthly) / len(monthly)
        
        msg = "All values are estimates, not guaranteed revenue."
        conf = "Medium" if len(monthly) >= 3 else "Low"
        if len(monthly) < 3:
            msg = "Not enough data yet. Import at least 3 months of revenue for reliable forecasts."
        return {
            "next_month_forecast": round(next_month_forecast, 2),
            "trend": trend,
            "monthly_history": [{"month": m, "revenue": v} for m, v in monthly],
            "confidence": conf,
            "confidence_level": conf,
            "message": msg,
        }
    except Exception:
        return {
            "next_month_forecast": 0,
            "trend": "insufficient_data",
            "confidence": "Low",
        }

def get_revenue_forecasting_data() -> Dict[str, Any]:
    """Load Revenue Forecasting Engine data from Phase 11."""
    try:
        import sys as _sys
        _phase11 = os.path.join(WORKSPACE, "phase11")
        if _phase11 not in _sys.path:
            _sys.path.insert(0, _phase11)

        # Check if we have data
        import pipeline_b_data_bridge as _bridge
        _has_data = _bridge.has_data(0) or _bridge.is_demo_mode()
        if not _has_data:
            return {
                "agent_name": "Revenue Forecasting Engine",
                "phase": 11,
                "port": 8011,
                "endpoints": 12,
                "status": "insufficient_data",
                "kpis": {
                    "actual_revenue": 0, "committed_revenue": 0,
                    "weighted_pipeline": 0, "unweighted_pipeline": 0,
                    "revenue_gap": 0, "revenue_at_risk": 0,
                },
                "forecast": [], "scenarios": {}, "action_plan": {},
                "message": "Not enough data yet. Import revenue and pipeline data to get forecasts.",
            }
        if _phase11 not in _sys.path:
            _sys.path.insert(0, _phase11)
        from intelligence_backend import (
            revenue_get_revenue_summary as get_revenue_summary,
            revenue_categorize_revenue as categorize_revenue,
            revenue_calculate_target_progress as calculate_target_progress,
            revenue_analyze_gap as analyze_gap,
            revenue_generate_action_plan as generate_action_plan,
            revenue_identify_risks as identify_risks,
            revenue_identify_opportunities as identify_opportunities,
        )
        from forecasting_model import generate_all_forecasts
        from scenario_forecasting_engine import generate_scenarios
        from product_forecast_engine import forecast_by_product
        from source_forecast_engine import forecast_by_source
        from intelligence_backend import revenue_generate_briefing as generate_briefing

        summary = get_revenue_summary()
        categories = categorize_revenue()
        forecasts = generate_all_forecasts()
        scenarios = generate_scenarios()
        targets = calculate_target_progress()
        gap = analyze_gap()
        actions = generate_action_plan()
        product = forecast_by_product()
        source = forecast_by_source()
        risks = identify_risks()
        opportunities = identify_opportunities()
        briefing = generate_briefing()

        cats = categories.get("categories", {})
        return {
            "agent_name": "Revenue Forecasting Engine",
            "phase": 11,
            "port": 8011,
            "endpoints": 17,
            "status": "active",
            "kpis": {
                "actual_revenue": cats.get("actual", {}).get("total_value", 0),
                "committed_revenue": cats.get("committed", {}).get("total_value", 0),
                "weighted_pipeline": cats.get("weighted_pipeline", {}).get("total_value", 0),
                "unweighted_pipeline": cats.get("unweighted_pipeline", {}).get("total_value", 0),
                "revenue_gap": gap.get("gap_analysis", {}).get("revenue_gap", 0),
                "revenue_at_risk": risks.get("total_revenue_at_risk", 0),
            },
            "categories": cats,
            "forecasts": forecasts.get("forecasts", {}),
            "scenarios": scenarios.get("scenarios", {}),
            "targets": targets.get("targets", {}),
            "gap_analysis": gap.get("gap_analysis", {}),
            "action_plan": actions.get("actions", []),
            "product_forecast": {
                "medicare": product.get("medicare", {}),
                "life_insurance": product.get("life_insurance", {}),
                "combined": product.get("combined_agency_forecast", {}),
            },
            "source_forecast": source.get("sources", []),
            "risks": risks.get("risks", []),
            "opportunities": opportunities.get("opportunities", []),
            "briefing": briefing,
            "forecast": _compute_forecast_summary(forecasts, summary),
        }
    except Exception as e:
        return {
            "agent_name": "Revenue Forecasting Engine",
            "phase": 11,
            "port": 8011,
            "status": "error",
            "error": str(e),
        }

def get_clv_intelligence_data() -> Dict[str, Any]:
    """Load CLV Intelligence Dashboard data from Phase 12."""
    try:
        import sys as _sys
        _phase12 = os.path.join(WORKSPACE, "phase12")
        if _phase12 not in _sys.path:
            _sys.path.insert(0, _phase12)

        # Check if we have data — if not in demo mode and no real data, return insufficient
        import pipeline_b_data_bridge as _bridge
        _has_data = _bridge.has_data(0) or _bridge.is_demo_mode()
        if not _has_data:
            return {
                "agent_name": "CLV Intelligence Dashboard",
                "phase": 12,
                "port": 8012,
                "endpoints": 15,
                "status": "insufficient_data",
                "kpis": {
                    "total_clients": 0, "total_historical_revenue": 0,
                    "estimated_total_clv": 0, "average_clv": 0,
                    "highest_value_client": "", "total_referral_revenue": 0,
                    "retention_rate": 0,
                },
                "clients": [], "risks": [], "opportunities": [],
                "portfolio": {}, "concentration": {}, "call_priorities": [],
                "briefing": {},
                "message": "Not enough data yet. Import client data to get CLV intelligence.",
            }
        if _phase12 not in _sys.path:
            _sys.path.insert(0, _phase12)
        from intelligence_backend import (
            clv_get_client_records as get_client_records,
            clv_get_client_summary as get_client_summary,
            clv_calculate_all_clv as calculate_all_clv,
            clv_score_all_clients as score_all_clients,
            clv_segment_clients as segment_clients,
            clv_build_matrix as build_matrix,
            clv_identify_risks as identify_risks,
            clv_identify_opportunities as identify_opportunities,
            clv_analyze_portfolio as analyze_portfolio,
            clv_assess_concentration as assess_concentration,
            clv_generate_briefing as generate_briefing,
        )
        from relationship_health_score import score_all_health
        from who_should_i_call_engine import generate_call_list

        records = get_client_records()
        summary = get_client_summary()
        clv = calculate_all_clv()
        scores = score_all_clients()
        segments = segment_clients()
        health = score_all_health()
        matrix = build_matrix()
        risks = identify_risks()
        opps = identify_opportunities()
        portfolio = analyze_portfolio()
        concentration = assess_concentration()
        call_list = generate_call_list()
        briefing = generate_briefing()

        scored = scores.get("scored_clients", scores.get("clients", []))
        return {
            "agent_name": "CLV Intelligence Dashboard",
            "phase": 12,
            "port": 8012,
            "endpoints": 22,
            "status": "active",
            "kpis": {
                "total_clients": summary.get("total_clients", len(records)),
                "total_historical_revenue": clv.get("summary", {}).get("total_historical", 0),
                "estimated_total_clv": clv.get("summary", {}).get("total_relationship_value", 0),
                "average_clv": clv.get("summary", {}).get("average_clv", 0),
                "highest_value_client": clv.get("summary", {}).get("highest_value_client", ""),
                "total_referral_revenue": clv.get("summary", {}).get("total_referral", 0),
                "retention_rate": summary.get("retention_rate", 0.92),
            },
            "clients": scored[:10],
            "leaderboard": scored[:10],
            "segments": segments.get("tiers", segments.get("segmentation", {})),
            "health_scores": health.get("health_scores", health.get("clients", [])),
            "matrix": matrix.get("points", []),
            "quadrants": matrix.get("quadrants", {}),
            "risks": risks.get("risks", []),
            "opportunities": opps.get("opportunities", []),
            "portfolio": portfolio,
            "concentration": concentration,
            "call_priorities": call_list.get("priorities", call_list.get("call_list", [])),
            "briefing": briefing,
        }
    except Exception as e:
        return {
            "agent_name": "CLV Intelligence Dashboard",
            "phase": 12,
            "port": 8012,
            "status": "error",
            "error": str(e),
        }

@app.get("/health")
def health():
    return {"status": "healthy", "server": "Unified Command Center", "port": 8020, "agents": 12}

@app.get("/api/admin/init-schema")
def init_schema(x_api_key: str = None):
    """Manually trigger database schema initialization. Returns detailed status."""
    check_auth(x_api_key)
    results = []
    try:
        import os as _os
        import psycopg2 as _pg2
        from psycopg2 import extras as _pg2extras
        results.append(f"DATABASE_URL set: {bool(os.environ.get('DATABASE_URL'))}")
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            return {"status": "error", "error": "DATABASE_URL not set"}
        # Use a direct connection — bypass the pool entirely
        results.append("Creating direct connection...")
        conn = _pg2.connect(db_url, cursor_factory=_pg2extras.RealDictCursor, connect_timeout=30)
        try:
            cursor = conn.cursor()
            migration_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "migrations", "001_supabase_schema.sql")
            results.append(f"Migration path: {migration_path}")
            results.append(f"Migration file exists: {_os.path.exists(migration_path)}")
            if _os.path.exists(migration_path):
                with open(migration_path) as f:
                    sql = f.read()
                results.append(f"SQL length: {len(sql)} chars")
                # Execute entire SQL file at once
                try:
                    cursor.execute(sql)
                    conn.commit()
                    results.append("Schema SQL executed successfully")
                except Exception as e:
                    # If batch execution fails, try statement by statement
                    conn.rollback()
                    import re as _re
                    statements = _re.split(r';\s*$', sql, flags=_re.MULTILINE)
                    results.append(f"Trying statement by statement: {len(statements)} statements")
                    executed = 0
                    errors = []
                    for stmt in statements:
                        lines = stmt.strip().splitlines()
                        clean = "\n".join(l for l in lines if not l.strip().startswith("--")).strip()
                        if not clean:
                            continue
                        try:
                            cursor.execute(clean)
                            conn.commit()  # Commit after each statement to prevent transaction abort cascade
                            executed += 1
                        except Exception as e2:
                            conn.rollback()  # Reset transaction state after error
                            err = str(e2)
                            if "already exists" not in err:
                                errors.append(f"{clean[:80]}... → {err[:100]}")
                    conn.commit()
                    results.append(f"Executed: {executed} statements")
                    if errors:
                        results.append(f"Errors ({len(errors)}):")
                        for e in errors[:5]:
                            results.append(f"  - {e}")
            # List tables
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;")
            tables = [row[0] if isinstance(row, tuple) else row.get('tablename', str(row)) for row in cursor.fetchall()]
            results.append(f"All tables: {tables}")
        finally:
            conn.close()
    except Exception as e:
        import traceback
        results.append(f"ERROR: {e}")
        results.append(traceback.format_exc()[:500])
    return {"status": "ok", "results": results}

@app.get("/api/summary")
def quick_summary(x_api_key: str = None):
    """Lightweight summary for fast initial dashboard render."""
    check_auth(x_api_key)
    try:
        import business_data_adapter
        kpis = business_data_adapter.compute_kpis()
        p1 = get_phase1_data()
        pipe = get_pipeline_summary()
        # Include revenue_goal from business_config so frontend doesn't fall back to $50,000
        config = _bds.get_business_config() if _bds_available else {}
        revenue_goal = float(config.get('revenue_goal', 0) or 0)
        revenue_mtd = kpis.get("revenue_mtd", 0)
        goal_progress = round((revenue_mtd / revenue_goal) * 100, 1) if revenue_goal > 0 else 0
        return {
            "scan_date": date(2026, 8, 17).isoformat(),
            "kpis": {
                "revenue_mtd": kpis["revenue_mtd"],
                "revenue_forecast": kpis["revenue_forecast"],
                "pipeline_value": kpis["pipeline_value"],
                "new_leads": kpis["new_leads"],
                "conversion_rate": kpis["conversion_rate"],
                "active_clients": kpis["active_clients"],
                "client_lifetime_value": kpis["client_lifetime_value"],
                "referral_opportunities": kpis["referral_opportunities"],
                "revenue_goal": revenue_goal,
                "goal_progress": goal_progress,
                "revenue_gap": revenue_goal - revenue_mtd - kpis.get("revenue_forecast", 0) if revenue_goal else 0,
            },
            "data_source": kpis.get("data_source", "demo"),
            "action_count": len(get_action_queue()),
            "agents_online": 12,
            "status": "ok",
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "kpis": {}, "action_count": 0}

def get_revenue_forecasting_light() -> Dict[str, Any]:
    """Lightweight Phase 11 summary for command-center (avoids 23s full computation)."""
    try:
        import sys as _sys
        _phase11 = os.path.join(WORKSPACE, "phase11")
        if _phase11 not in _sys.path:
            _sys.path.insert(0, _phase11)
        from intelligence_backend import (
            revenue_get_revenue_summary as get_revenue_summary,
            revenue_categorize_revenue as categorize_revenue,
            revenue_analyze_gap as analyze_gap,
        )
        summary = get_revenue_summary()
        cats = categorize_revenue()
        gap = analyze_gap()
        forecasts = {"forecasts": {}}
        # Use the light forecast summary
        try:
            from forecasting_model import generate_all_forecasts as _gaf
            forecasts = _gaf()
        except Exception:
            pass
        return {
            "agent_name": "Revenue Forecasting Engine",
            "phase": 11,
            "port": 8011,
            "endpoints": 17,
            "status": "active",
            "kpis": {
                "actual_revenue": cats.get("categories", {}).get("actual", {}).get("total_value", 0),
                "committed_revenue": cats.get("categories", {}).get("committed", {}).get("total_value", 0),
                "weighted_pipeline": cats.get("categories", {}).get("weighted_pipeline", {}).get("total_value", 0),
                "unweighted_pipeline": cats.get("categories", {}).get("unweighted_pipeline", {}).get("total_value", 0),
                "revenue_gap": gap.get("gap_analysis", {}).get("revenue_gap", 0),
                "revenue_at_risk": 0,
            },
            "categories": cats.get("categories", {}),
            "forecasts": forecasts.get("forecasts", {}),
            "gap_analysis": gap.get("gap_analysis", {}),
            "forecast": _compute_forecast_summary(forecasts, summary),
            "briefing": {"message": "See /api/agent/11 for full briefing."},
            "scenarios": {}, "action_plan": [],
            "product_forecast": {}, "source_forecast": [],
            "risks": [], "opportunities": [],
        }
    except Exception as e:
        return {"agent_name": "Revenue Forecasting Engine", "phase": 11, "status": "error", "error": str(e)}

def get_clv_intelligence_light() -> Dict[str, Any]:
    """Lightweight Phase 12 summary for command-center."""
    try:
        import sys as _sys
        _phase12 = os.path.join(WORKSPACE, "phase12")
        if _phase12 not in _sys.path:
            _sys.path.insert(0, _phase12)
        from intelligence_backend import (
            clv_get_client_records as get_client_records,
            clv_get_client_summary as get_client_summary,
            clv_calculate_all_clv as calculate_all_clv,
            clv_score_all_clients as score_all_clients,
            clv_segment_clients as segment_clients,
            clv_build_matrix as build_matrix,
            clv_identify_risks as identify_risks,
            clv_identify_opportunities as identify_opportunities,
            clv_assess_concentration as assess_concentration,
        )
        from relationship_health_score import score_all_health
        from who_should_i_call_engine import generate_call_list
        records = get_client_records()
        summary = get_client_summary()
        clv = calculate_all_clv()
        clv_summary = clv.get("summary", {})
        scored = score_all_clients().get("scored_clients", [])
        seg = segment_clients()
        health = score_all_health()
        matrix = build_matrix()
        risks = identify_risks()
        opps = identify_opportunities()
        concentration = assess_concentration()
        call_list = generate_call_list().get("call_list", [])
        total_clients = len(records) if records else 0
        total_clv = clv_summary.get("total_relationship_value", 0)
        # Map PLATINUM/GOLD/SILVER/BRONZE to A/B/C/D for frontend
        tier_map = {"PLATINUM": "A", "GOLD": "B", "SILVER": "C", "BRONZE": "D"}
        raw_tiers = seg.get("tiers", seg.get("segmentation", {}))
        segments_out = {}
        for tier, count in raw_tiers.items():
            key = tier_map.get(tier, tier)
            tier_clients = [c for c in scored if c.get("value_tier") == tier]
            segments_out[key] = {
                "count": count,
                "client_count": count,
                "total_value": sum(c.get("clv", 0) for c in tier_clients),
                "total_clv": sum(c.get("clv", 0) for c in tier_clients),
            }
        # Ensure all 4 tiers exist
        for k in ["A", "B", "C", "D"]:
            if k not in segments_out:
                segments_out[k] = {"count": 0, "client_count": 0, "total_value": 0, "total_clv": 0}
        # Map matrix quadrants to frontend keys
        q_map = {"star": "protect_grow", "cash_cow": "protect_retain", "rising_star": "develop", "question_mark": "maintain_efficiently"}
        quadrants_out = {}
        for p in matrix.get("points", []):
            q_key = q_map.get(p.get("quadrant", ""), "maintain_efficiently")
            if q_key not in quadrants_out:
                quadrants_out[q_key] = []
            quadrants_out[q_key].append(p)
        # Map call list to call_priorities shape
        call_priorities = []
        for c in call_list:
            call_priorities.append({
                "display_name": c.get("name", ""),
                "client_name": c.get("name", ""),
                "name": c.get("name", ""),
                "reason": c.get("reason", ""),
                "reasoning": c.get("reason", ""),
                "recommended_action": c.get("priority", "") + " priority" if c.get("priority") else "",
                "priority": c.get("priority", "medium"),
            })
        # Concentration in the shape frontend expects
        conc_out = {
            "revenue_concentration": {"top_3_pct": concentration.get("top_client_pct", 0) / 100},
            "referral_concentration": {"top_3_pct": 0},
        }
        return {
            "agent_name": "CLV Intelligence Dashboard",
            "phase": 12,
            "port": 8012,
            "endpoints": 15,
            "status": "active",
            "kpis": {
                "total_clients": total_clients,
                "average_clv": clv_summary.get("average_clv", 0),
                "estimated_total_clv": total_clv,
                "total_clv": total_clv,
                "total_historical_revenue": summary.get("total_historical_revenue", 0) if summary else 0,
                "highest_value_client": clv_summary.get("highest_value_client", ""),
                "total_referral_revenue": clv_summary.get("total_referral", 0),
                "retention_rate": summary.get("retention_rate", 0.92) if summary else 0.92,
            },
            "client_records_count": total_clients,
            "summary": summary or {},
            "clients": scored[:10],
            "leaderboard": scored[:10],
            "segments": segments_out,
            "health_scores": health.get("health_scores", health.get("clients", [])),
            "matrix": matrix.get("points", []),
            "quadrants": quadrants_out,
            "risks": risks.get("risks", []),
            "opportunities": opps.get("opportunities", []),
            "portfolio": {},
            "concentration": conc_out,
            "call_priorities": call_priorities,
            "call_list": call_list,
            "briefing": {"message": "See /api/agent/12 for full briefing."},
        }
    except Exception as e:
        return {"agent_name": "CLV Intelligence Dashboard", "phase": 12, "status": "error", "error": str(e)}

_cc_cache = {"fingerprint": None, "data": None, "ts": 0}

def _db_fingerprint() -> str:
    """Compute a quick fingerprint of the database state for cache invalidation."""
    try:
        import sqlite3
        db_path = os.path.join(BASE_DIR, "data.db")
        conn = sqlite3.connect(db_path)
        row = conn.execute("""
            SELECT 
                (SELECT COUNT(*) FROM contacts) || '-' ||
                (SELECT COUNT(*) FROM opportunities) || '-' ||
                (SELECT COUNT(*) FROM revenue_records) || '-' ||
                (SELECT COUNT(*) FROM referral_sources) || '-' ||
                (SELECT is_demo_mode FROM demo_state WHERE id=1) || '-' ||
                (SELECT revenue_goal FROM business_config WHERE id=1)
        """).fetchone()
        conn.close()
        return str(row[0]) if row else "empty"
    except Exception:
        return "error"

@app.get("/api/command-center")
def command_center(x_api_key: str = None):
    """Full unified dashboard data from all agents (cached by DB fingerprint)."""
    check_auth(x_api_key)
    _reset_mode_cache()
    
    # Check cache — skip recompute if DB hasn't changed
    fp = _db_fingerprint()
    now = _time_mod.time()
    if _cc_cache["data"] is not None and _cc_cache["fingerprint"] == fp and (now - _cc_cache["ts"]) < _CACHE_TTL:
        return _cc_cache["data"]
    
    # Use lightweight Phase 11/12 for command center performance
    _exec = get_executive_data()
    _wc = get_what_changed_data()
    _ls = get_lead_scoring_data()
    _ri = get_referral_intelligence_data()
    _rf = get_revenue_forecasting_light()
    _clv = get_clv_intelligence_light()
    
    _exec_s = _strip_sample_in_real_mode(_exec)
    _wc_s = _strip_sample_in_real_mode(_wc)
    _ls_s = _strip_sample_in_real_mode(_ls)
    _ri_s = _strip_sample_in_real_mode(_ri)
    _rf_s = _strip_sample_in_real_mode(_rf)
    _clv_s = _strip_sample_in_real_mode(_clv)
    
    result = {
        "scan_date": date.today().isoformat(),
        "agents": [
            get_phase1_data(),
            get_phase2_data(),
            get_phase3_data(),
            get_phase4_data(),
            get_phase5_data(),
            get_phase6_data(),
            _exec_s,
            _wc_s,
            _ls_s,
            _ri_s,
            _rf_s,
            _clv_s,
        ],
        "executive": _exec_s,
        "what_changed": _wc_s,
        "lead_scoring": _ls_s,
        "referral_intelligence": _ri_s,
        "revenue_forecasting": _rf_s,
        "clv_intelligence": _clv_s,
        "pipeline": get_pipeline_summary(),
        "compliance": get_compliance_summary(),
        "action_queue": get_action_queue(),
        "charts": get_charts_data(),
        "summary": {
            "total_scripts": 143,
            "total_endpoints": 138,
            "api_ports": "8000-8012",
            "monthly_cost": "$113",
            "hours_saved_weekly": "80-85",
            "phases_built": 12,
        },
    }
    
    # Cache the result
    _cc_cache["fingerprint"] = fp
    _cc_cache["data"] = result
    _cc_cache["ts"] = now
    
    return result

@app.get("/api/agent/{phase}")
def agent_detail(phase: int, x_api_key: str = None):
    """Per-agent detail."""
    check_auth(x_api_key)
    agents = {1: get_phase1_data, 2: get_phase2_data, 3: get_phase3_data,
              4: get_phase4_data, 5: get_phase5_data, 6: get_phase6_data,
              7: get_executive_data, 8: get_what_changed_data,
              9: get_lead_scoring_data, 10: get_referral_intelligence_data,
              11: get_revenue_forecasting_data,
              12: get_clv_intelligence_data}
    if phase not in agents:
        raise HTTPException(status_code=404, detail="Phase not found")
    _reset_mode_cache()
    _result = agents[phase]()
    if phase >= 7:
        return _strip_sample_in_real_mode(_result)
    return _result

@app.get("/api/charts")
def charts_endpoint(x_api_key: str = None):
    check_auth(x_api_key)
    return get_charts_data()

@app.get("/api/action-queue")
def action_queue(x_api_key: str = None):
    check_auth(x_api_key)
    return {"actions": get_action_queue(), "total": len(get_action_queue())}

@app.get("/api/pipeline")
def pipeline_summary(x_api_key: str = None):
    check_auth(x_api_key)
    return get_pipeline_summary()

@app.get("/api/compliance")
def compliance_summary(x_api_key: str = None):
    check_auth(x_api_key)
    return get_compliance_summary()

# --- Marketing Posts ---
try:
    import marketing_posts_engine as _mp_engine
    _mp_available = True
except Exception as e:
    _mp_available = False
    _mp_error = str(e)

@app.get("/api/marketing-posts/config")
def marketing_posts_config(x_api_key: str = None):
    check_auth(x_api_key)
    if not _mp_available:
        return {"status": "error", "error": _mp_error}
    return _mp_engine.get_marketing_config()

@app.get("/api/marketing-posts")
def get_marketing_posts(
    company: str = None,
    industry: str = None,
    tone: str = "friendly",
    channel: str = "facebook",
    cta: str = None,
    offer: str = None,
    target_date: str = None,
    x_api_key: str = None,
):
    check_auth(x_api_key)
    if not _mp_available:
        return {"status": "error", "error": _mp_error}
    return _mp_engine.generate_daily_posts(
        company=company,
        industry=industry,
        tone=tone,
        channel=channel,
        cta=cta,
        offer=offer,
        target_date=target_date,
    )

@app.post("/api/marketing-posts/customize")
def customize_marketing_post(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _mp_available:
        return {"status": "error", "error": _mp_error}
    post_id = (payload or {}).get("post_id", "")
    content = (payload or {}).get("content", "")
    company = (payload or {}).get("company")
    channel = (payload or {}).get("channel", "facebook")
    return _mp_engine.customize_post(post_id, content, company=company, channel=channel)

# Serve only a dedicated static directory (never expose .py or .db files)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static_assets")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ---- COMMAND CENTER V2 ENDPOINTS ----
try:
    from command_center_v2_engine import get_command_center_v2 as _get_v2
    from command_center_audit import generate_audit_report as _gen_audit
    from command_center_audit import generate_intelligence_map as _gen_map
    _v2_available = True
except Exception as e:
    _v2_available = False
    _v2_error = str(e)

# ---- CACHE for expensive V2/audit operations (30-minute TTL) ----
import time as _time_mod
import threading as _threading_mod
_v2_cache = {"data": None, "ts": 0, "computing": False}
_v2_needs_cache = {"data": None, "ts": 0}
_audit_cache = {"data": None, "ts": 0}
_map_cache = {"data": None, "ts": 0}
_CACHE_TTL = 1800  # 30 minutes

def _refresh_v2_bg():
    """Refresh V2 cache in background thread (non-blocking)."""
    if _v2_cache["computing"]:
        return
    def _worker():
        try:
            _v2_cache["computing"] = True
            result = _get_v2()
            _v2_cache["data"] = result
            _v2_cache["ts"] = _time_mod.time()
        except Exception as e:
            print(f"V2 background refresh error: {e}")
        finally:
            _v2_cache["computing"] = False
    t = _threading_mod.Thread(target=_worker, daemon=True)
    t.start()

def _cached_v2():
    if _v2_available:
        now = _time_mod.time()
        # If we have fresh cached data, return it
        if _v2_cache["data"] is not None and (now - _v2_cache["ts"]) <= _CACHE_TTL:
            return _v2_cache["data"]
        # If currently computing, return stale data if available, else computing status
        if _v2_cache["computing"]:
            if _v2_cache["data"] is not None:
                return _v2_cache["data"]
            return {"status": "computing", "message": "Command Center V2 is computing. This takes about 30 seconds on first load."}
        # If we have stale data, return it and trigger background refresh
        if _v2_cache["data"] is not None:
            _refresh_v2_bg()
            return _v2_cache["data"]
        # No data yet - trigger background computation and return computing status
        _refresh_v2_bg()
        return {"status": "computing", "message": "Command Center V2 is computing. This takes about 30 seconds on first load."}
    return {"status": "error", "error": _v2_error}

def _cached_audit():
    if _v2_available:
        now = _time_mod.time()
        if _audit_cache["data"] is None or (now - _audit_cache["ts"]) > _CACHE_TTL:
            _audit_cache["data"] = _gen_audit()
            _audit_cache["ts"] = now
        return _audit_cache["data"]
    return {"status": "error", "error": _v2_error}

def _cached_map():
    if _v2_available:
        now = _time_mod.time()
        if _map_cache["data"] is None or (now - _map_cache["ts"]) > _CACHE_TTL:
            _map_cache["data"] = _gen_map()
            _map_cache["ts"] = now
        return _map_cache["data"]
    return {"status": "error", "error": _v2_error}

# Scorecard cache
_scorecard_cache = {"data": None, "ts": 0, "computing": False, "error": None}

def _compute_scorecard_bg():
    """Compute scorecard in background thread on startup."""
    import threading
    def _worker():
        try:
            _scorecard_cache["computing"] = True
            result = _get_scorecard()
            _scorecard_cache["data"] = result
            _scorecard_cache["ts"] = _time_mod.time()
            _scorecard_cache["error"] = None
        except Exception as e:
            _scorecard_cache["error"] = str(e)
        finally:
            _scorecard_cache["computing"] = False
    t = threading.Thread(target=_worker, daemon=True)
    t.start()

def _cached_scorecard():
    if not _scorecard_available:
        return {"status": "error", "error": _scorecard_error}
    now = _time_mod.time()
    # If we have cached data and it's fresh, return it
    if _scorecard_cache["data"] is not None and (now - _scorecard_cache["ts"]) <= _CACHE_TTL:
        return _scorecard_cache["data"]
    # If currently computing, return "still computing" status
    if _scorecard_cache["computing"]:
        return {"status": "computing", "message": "Business Health Score is being calculated. This takes about 3 minutes on first load."}
    # If we have stale data, return it and trigger background refresh
    if _scorecard_cache["data"] is not None:
        _compute_scorecard_bg()
        return _scorecard_cache["data"]
    # No data yet - trigger background computation and return computing status
    _compute_scorecard_bg()
    return {"status": "computing", "message": "Business Health Score is being calculated. This takes about 3 minutes on first load."}

try:
    from action_ledger import execute_action as _exec_action
    from action_ledger import get_actions as _get_actions
    from action_ledger import complete_action as _complete_action
    from action_ledger import get_action_summary as _action_summary
    from action_ledger import get_completed_entity_types as _completed_types  # noqa: F401
    from action_ledger import record_outcome as _record_outcome
    from action_ledger import snooze_action as _snooze_action
    from action_ledger import dismiss_action as _dismiss_action
    from action_ledger import get_snoozed_returning as _snoozed_returning  # noqa: F401
    from action_ledger import get_action_history as _action_history
    from action_ledger import get_performance_metrics as _perf_metrics
    from action_ledger import consolidate_duplicates as _consolidate_dupes  # noqa: F401
    from action_ledger import create_follow_up as _create_follow_up
    from action_ledger import get_pending_follow_ups as _pending_follow_ups  # noqa: F401
    from action_ledger import get_action_center_data as _action_center_data
    _ledger_available = True
except Exception as e:
    _ledger_available = False
    _ledger_error = str(e)

# Action Execution Engine (smart action buttons, AI drafts, action cards)
try:
    from action_execution_engine import get_smart_actions as _smart_actions
    from action_execution_engine import prepare_action_context as _prepare_action_ctx  # noqa: F401
    from action_execution_engine import draft_follow_up_message as _draft_message
    from action_execution_engine import is_action_executable as _is_executable  # noqa: F401
    from action_execution_engine import generate_action_card as _gen_action_card  # noqa: F401
    _engine_available = True
except Exception as e:
    _engine_available = False
    _engine_error = str(e)

# Business Owner Scorecard engine
try:
    from business_scorecard_engine import (
        get_scorecard as _get_scorecard,
        get_category_detail as _scorecard_category,
        save_current_snapshot as _save_scorecard_snapshot,
        load_snapshots as _load_scorecard_snapshots,
        ask_scorecard as _ask_scorecard,
    )
    _scorecard_available = True
    _scorecard_error = None
except Exception as e:
    _scorecard_available = False
    _scorecard_error = str(e)

# Training Mode engine
try:
    from training_mode_engine import (
        get_training_data as _get_training,
        update_progress as _update_training_progress,
        record_knowledge_check as _record_knowledge_check,
        record_simulation as _record_simulation,
        ask_coach as _ask_coach,
        get_contextual_help as _get_contextual_help,
        reset_training as _reset_training,
        get_certificate as _get_training_certificate,
        get_training_health as _get_training_health,
    )
    _training_available = True
    _training_error = None
except Exception as e:
    _training_available = False
    _training_error = str(e)

@app.get("/api/command-center-v2")
def command_center_v2(x_api_key: str = None):
    check_auth(x_api_key)
    if not _v2_available:
        return {"status": "error", "error": _v2_error}
    return _cached_v2()

@app.get("/api/v2/priority-engine")
def v2_priority_engine(x_api_key: str = None):
    check_auth(x_api_key)
    if not _v2_available:
        return {"status": "error", "error": _v2_error}
    data = _cached_v2()
    return {"top_5": data.get("top_5_priorities", []), "next_action": data.get("what_should_i_do_next", {})}

@app.get("/api/v2/next-action")
def v2_next_action(x_api_key: str = None):
    check_auth(x_api_key)
    if not _v2_available:
        return {"status": "error", "error": _v2_error}
    return _cached_v2().get("what_should_i_do_next", {})

@app.get("/api/v2/needs-attention")
def v2_needs_attention(x_api_key: str = None):
    check_auth(x_api_key)
    if not _v2_available:
        return {"status": "error", "error": _v2_error}
    return _cached_v2().get("needs_attention", [])

@app.get("/api/v2/audit")
def v2_audit(x_api_key: str = None):
    check_auth(x_api_key)
    if not _v2_available:
        return {"status": "error", "error": _v2_error}
    return _cached_audit()

@app.get("/api/v2/intelligence-map")
def v2_intelligence_map(x_api_key: str = None):
    check_auth(x_api_key)
    if not _v2_available:
        return {"status": "error", "error": _v2_error}
    return _cached_map()

# ---- ACTION PERSISTENCE ENDPOINTS ----
@app.post("/api/v2/actions/execute")
def v2_execute_action(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _ledger_available:
        return {"status": "error", "error": _ledger_error}
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    action_type = payload.get("action_type", "view")
    entity = payload.get("entity", "Unknown")
    entity_type = payload.get("entity_type", "")
    notes = payload.get("notes", "")
    source_priority_id = payload.get("source_priority_id", "")
    snooze_until = payload.get("snooze_until", "")
    snooze_type = payload.get("snooze_type", "custom")
    dismiss_reason = payload.get("dismiss_reason", "")
    outcome = payload.get("outcome", "")
    follow_up_date = payload.get("follow_up_date", "")
    value = payload.get("value", 0)
    source = payload.get("source", payload.get("source_system", ""))
    result = _exec_action(action_type, entity, entity_type, notes, source_priority_id,
                          snooze_until=snooze_until, snooze_type=snooze_type,
                          dismiss_reason=dismiss_reason, outcome=outcome,
                          follow_up_date=follow_up_date, value=value, source=source)
    return {"status": "ok", "action": result, "action_id": result.get("id", "")}

@app.get("/api/v2/actions")
def v2_get_actions(limit: int = 50, status: str = None, entity_type: str = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _ledger_available:
        return {"status": "error", "error": _ledger_error}
    return {"actions": _get_actions(limit=limit, status=status, entity_type=entity_type), "summary": _action_summary()}

@app.post("/api/v2/actions/complete")
def v2_complete_action(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _ledger_available:
        return {"status": "error", "error": _ledger_error}
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    action_id = payload.get("action_id", "")
    notes = payload.get("notes", "")
    result = _complete_action(action_id, notes)
    return {"status": "ok", "action": result}

@app.get("/api/v2/action-summary")
def v2_action_summary(x_api_key: str = None):
    check_auth(x_api_key)
    if not _ledger_available:
        return {"status": "error", "error": _ledger_error}
    return _action_summary()

# ---- ACTION & EXECUTION LAYER ENDPOINTS ----

@app.get("/api/v2/action-center")
def v2_action_center(view: str = None, x_api_key: str = None):
    """Unified Action Center: todays actions, overdue, snoozed returning,
    pending follow-ups, and summary stats. Optional view filter."""
    check_auth(x_api_key)
    if not _ledger_available:
        return {"status": "error", "error": _ledger_error}
    v2_data = _cached_v2() if _v2_available else {}
    v2_priorities = v2_data.get("top_5_priorities", []) if isinstance(v2_data, dict) and "top_5_priorities" in v2_data else None
    return _action_center_data(view=view, v2_priorities=v2_priorities)

@app.post("/api/v2/actions/snooze")
def v2_actions_snooze(payload: dict = None, x_api_key: str = None):
    """Snooze an action until a future date.
    Payload: {action_id, snooze_until, snooze_type}."""
    check_auth(x_api_key)
    if not _ledger_available:
        return {"status": "error", "error": _ledger_error}
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    action_id = payload.get("action_id", "")
    snooze_until = payload.get("snooze_until", "")
    snooze_type = payload.get("snooze_type", "custom")
    if not action_id or not snooze_until:
        return {"status": "error", "error": "action_id and snooze_until are required"}
    result = _snooze_action(action_id, snooze_until, snooze_type)
    if isinstance(result, dict) and result.get("error"):
        return {"status": "error", "error": result["error"]}
    return {"status": "ok", "action": result}

@app.post("/api/v2/actions/dismiss")
def v2_actions_dismiss(payload: dict = None, x_api_key: str = None):
    """Dismiss an action with a reason.
    Payload: {action_id, reason, notes}."""
    check_auth(x_api_key)
    if not _ledger_available:
        return {"status": "error", "error": _ledger_error}
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    action_id = payload.get("action_id", "")
    reason = payload.get("reason", "")
    notes = payload.get("notes", "")
    if not action_id or not reason:
        return {"status": "error", "error": "action_id and reason are required"}
    result = _dismiss_action(action_id, reason, notes)
    if isinstance(result, dict) and result.get("error"):
        return {"status": "error", "error": result["error"]}
    return {"status": "ok", "action": result}

@app.post("/api/v2/actions/outcome")
def v2_actions_outcome(payload: dict = None, x_api_key: str = None):
    """Record the outcome of an action.
    Payload: {action_id, outcome, notes}."""
    check_auth(x_api_key)
    if not _ledger_available:
        return {"status": "error", "error": _ledger_error}
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    action_id = payload.get("action_id", "")
    outcome = payload.get("outcome", "")
    notes = payload.get("notes", "")
    if not action_id or not outcome:
        return {"status": "error", "error": "action_id and outcome are required"}
    result = _record_outcome(action_id, outcome, notes)
    if isinstance(result, dict) and result.get("error"):
        return {"status": "error", "error": result["error"]}
    return {"status": "ok", "action": result}

@app.get("/api/v2/actions/history")
def v2_actions_history(
    limit: int = 100,
    status: str = None,
    entity_type: str = None,
    outcome: str = None,
    start_date: str = None,
    end_date: str = None,
    action_type: str = None,
    x_api_key: str = None,
):
    """Filtered, sorted action history."""
    check_auth(x_api_key)
    if not _ledger_available:
        return {"status": "error", "error": _ledger_error}
    filters = {
        "status": status,
        "entity_type": entity_type,
        "outcome": outcome,
        "start_date": start_date,
        "end_date": end_date,
        "action_type": action_type,
    }
    history = _action_history(filters)
    if limit:
        history = history[:limit]
    return {"actions": history, "total": len(history)}

@app.get("/api/v2/actions/performance")
def v2_actions_performance(x_api_key: str = None):
    """Performance metrics across all recorded actions."""
    check_auth(x_api_key)
    if not _ledger_available:
        return {"status": "error", "error": _ledger_error}
    return _perf_metrics()

@app.post("/api/v2/actions/follow-up")
def v2_actions_follow_up(payload: dict = None, x_api_key: str = None):
    """Create a follow-up task that appears in priorities when due.
    Payload: {entity, entity_type, due_date, reason, value, source_action_id}."""
    check_auth(x_api_key)
    if not _ledger_available:
        return {"status": "error", "error": _ledger_error}
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    entity = payload.get("entity", "")
    entity_type = payload.get("entity_type", "")
    due_date = payload.get("due_date", "")
    reason = payload.get("reason", "")
    value = payload.get("value", 0)
    source_action_id = payload.get("source_action_id", "")
    if not entity or not due_date:
        return {"status": "error", "error": "entity and due_date are required"}
    result = _create_follow_up(entity, entity_type, due_date, reason, value, source_action_id)
    if isinstance(result, dict) and result.get("error"):
        return {"status": "error", "error": result["error"]}
    return {"status": "ok", "follow_up": result}

@app.get("/api/v2/actions/smart")
def v2_actions_smart(entity_type: str = None, x_api_key: str = None):
    """Return smart action buttons for an entity type."""
    check_auth(x_api_key)
    if not _engine_available:
        return {"status": "error", "error": _engine_error}
    if not entity_type:
        return {"status": "error", "error": "entity_type query parameter is required"}
    return {"entity_type": entity_type, "actions": _smart_actions(entity_type)}

@app.post("/api/v2/actions/draft")
def v2_actions_draft(payload: dict = None, x_api_key: str = None):
    """Generate an AI-drafted follow-up message.
    Payload: {entity, entity_type, reason, tone}."""
    check_auth(x_api_key)
    if not _engine_available:
        return {"status": "error", "error": _engine_error}
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    entity = payload.get("entity", "")
    entity_type = payload.get("entity_type", "")
    reason = payload.get("reason", "")
    tone = payload.get("tone", "professional")
    if not entity:
        return {"status": "error", "error": "entity is required"}
    draft = _draft_message(entity, entity_type, reason, tone)
    return {"status": "ok", "draft": draft, "disclaimer": "DRAFT -- owner approval required."}

# ---- BUSINESS OWNER SCORECARD ENDPOINTS ----

@app.get("/api/scorecard")
def get_scorecard(x_api_key: str = None):
    """Returns the COMPLETE scorecard in one response (no frontend assembly needed)."""
    check_auth(x_api_key)
    if not _scorecard_available:
        return {"status": "error", "error": _scorecard_error}
    return _cached_scorecard()

@app.get("/api/scorecard/category/{category_name}")
def get_scorecard_category(category_name: str, x_api_key: str = None):
    """Returns detailed category breakdown for a single scorecard category."""
    check_auth(x_api_key)
    if not _scorecard_available:
        return {"status": "error", "error": _scorecard_error}
    return _scorecard_category(category_name)

@app.post("/api/scorecard/snapshot")
def save_snapshot(x_api_key: str = None):
    """Saves the current scorecard as a weekly snapshot for trend analysis."""
    check_auth(x_api_key)
    if not _scorecard_available:
        return {"status": "error", "error": _scorecard_error}
    return _save_scorecard_snapshot()

@app.get("/api/scorecard/trends")
def get_trends(x_api_key: str = None):
    """Returns historical snapshots for trend analysis."""
    check_auth(x_api_key)
    if not _scorecard_available:
        return {"status": "error", "error": _scorecard_error}
    snaps = _load_scorecard_snapshots()
    return {"snapshots": snaps, "total": len(snaps)}

@app.post("/api/scorecard/ask")
def ask_scorecard(payload: dict = None, x_api_key: str = None):
    """AI interpretation - answers owner questions using scorecard data.
    Payload: {"question": "Why did my score drop?"}."""
    check_auth(x_api_key)
    if not _scorecard_available:
        return {"status": "error", "error": _scorecard_error}
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    question = payload.get("question", "")
    if not question:
        return {"status": "error", "error": "question is required"}
    return _ask_scorecard(question)

# ---- TRAINING MODE ENDPOINTS ----

@app.get("/api/training")
def get_training(x_api_key: str = None):
    """Returns all training modules, simulations, roles, and progress."""
    check_auth(x_api_key)
    if not _training_available:
        return {"status": "error", "error": _training_error}
    return _get_training()

@app.post("/api/training/progress")
def update_training_progress(payload: dict = None, x_api_key: str = None):
    """Update training progress for a module."""
    check_auth(x_api_key)
    if not _training_available:
        return {"status": "error", "error": _training_error}
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    module_id = payload.get("module_id", "")
    step_index = payload.get("step_index", 0)
    completed = payload.get("completed", False)
    if not module_id:
        return {"status": "error", "error": "module_id is required"}
    return _update_training_progress(module_id, step_index, completed)

@app.post("/api/training/simulation")
def record_training_simulation(payload: dict = None, x_api_key: str = None):
    """Record a simulation action. Does NOT modify live data."""
    check_auth(x_api_key)
    if not _training_available:
        return {"status": "error", "error": _training_error}
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    scenario_id = payload.get("scenario_id", "")
    action_type = payload.get("action_type", "")
    outcome = payload.get("outcome")
    if not scenario_id or not action_type:
        return {"status": "error", "error": "scenario_id and action_type are required"}
    return _record_simulation(scenario_id, action_type, outcome)

@app.post("/api/training/knowledge-check")
def training_knowledge_check(payload: dict = None, x_api_key: str = None):
    """Submit a knowledge check answer."""
    check_auth(x_api_key)
    if not _training_available:
        return {"status": "error", "error": _training_error}
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    module_id = payload.get("module_id", "")
    selected_index = payload.get("selected_index", -1)
    if not module_id:
        return {"status": "error", "error": "module_id is required"}
    return _record_knowledge_check(module_id, selected_index)

@app.post("/api/training/coach")
def training_coach(payload: dict = None, x_api_key: str = None):
    """Ask the training coach a question."""
    check_auth(x_api_key)
    if not _training_available:
        return {"status": "error", "error": _training_error}
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    question = payload.get("question", "")
    if not question:
        return {"status": "error", "error": "question is required"}
    return _ask_coach(question)

@app.get("/api/training/help/{view}")
def training_help(view: str, x_api_key: str = None):
    """Get contextual help for a specific view."""
    check_auth(x_api_key)
    if not _training_available:
        return {"status": "error", "error": _training_error}
    return _get_contextual_help(view)

@app.post("/api/training/reset")
def training_reset(x_api_key: str = None):
    """Reset all training progress."""
    check_auth(x_api_key)
    if not _training_available:
        return {"status": "error", "error": _training_error}
    return _reset_training()

@app.get("/api/training/certificate")
def training_certificate(x_api_key: str = None):
    """Get training certificate if completed."""
    check_auth(x_api_key)
    if not _training_available:
        return {"status": "error", "error": _training_error}
    return _get_training_certificate()

@app.get("/api/training/health")
def training_health(x_api_key: str = None):
    """Get training mode health metrics."""
    check_auth(x_api_key)
    if not _training_available:
        return {"status": "error", "error": _training_error}
    return _get_training_health()

# ---- DATA IMPORT WIZARD ENDPOINTS ----

try:
    import import_engine
    import data_store
    _import_available = True
    _import_error = None
except Exception as e:
    _import_available = False
    _import_error = str(e)

@app.get("/api/import/schemas")
def import_schemas(x_api_key: str = None):
    """Get available import schemas with field definitions and auto-mapping."""
    check_auth(x_api_key)
    if not _import_available:
        return {"status": "error", "error": _import_error}
    return {
        "status": "ok",
        "schemas": import_engine.IMPORT_SCHEMAS,
        "data_summary": data_store.get_data_summary(),
    }

@app.post("/api/import/preview")
def import_preview(payload: dict = None, x_api_key: str = None):
    """Preview an import: validate rows and return summary without committing."""
    check_auth(x_api_key)
    if not _import_available:
        return {"status": "error", "error": _import_error}
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    data_type = payload.get("data_type", "")
    rows = payload.get("rows", [])
    field_mapping = payload.get("field_mapping", {})
    if data_type not in import_engine.IMPORT_SCHEMAS:
        return {"status": "error", "error": f"Unknown data type: {data_type}"}
    if not rows:
        return {"status": "error", "error": "No rows to import"}
    result = import_engine.preview_import(rows, data_type, field_mapping)
    return {"status": "ok", "preview": result}

@app.post("/api/import/start")
def import_start(payload: dict = None, x_api_key: str = None):
    """Start a new import batch. Returns batch_id for subsequent chunk calls."""
    check_auth(x_api_key)
    if not _import_available:
        return {"status": "error", "error": _import_error}
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    data_type = payload.get("data_type", "")
    filename = payload.get("filename", "upload.csv")
    total_rows = payload.get("total_rows", 0)
    field_mapping = payload.get("field_mapping", {})
    if data_type not in import_engine.IMPORT_SCHEMAS:
        return {"status": "error", "error": f"Unknown data type: {data_type}"}
    batch_id = import_engine.start_batch(data_type, filename, total_rows, field_mapping)
    return {"status": "ok", "batch_id": batch_id}

@app.post("/api/import/chunk")
def import_chunk(payload: dict = None, x_api_key: str = None):
    """Commit a chunk of validated rows to the database."""
    check_auth(x_api_key)
    if not _import_available:
        return {"status": "error", "error": _import_error}
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    batch_id = payload.get("batch_id", "")
    rows = payload.get("rows", [])
    data_type = payload.get("data_type", "")
    is_sample = payload.get("is_sample", False)
    if not batch_id or not rows or not data_type:
        return {"status": "error", "error": "Missing batch_id, rows, or data_type"}
    result = import_engine.commit_chunk(rows, data_type, batch_id, is_sample)
    return {"status": "ok", "result": result}

@app.post("/api/import/complete")
def import_complete(payload: dict = None, x_api_key: str = None):
    """Mark an import batch as completed."""
    check_auth(x_api_key)
    if not _import_available:
        return {"status": "error", "error": _import_error}
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    batch_id = payload.get("batch_id", "")
    if not batch_id:
        return {"status": "error", "error": "Missing batch_id"}
    import_engine.complete_batch(batch_id)
    batch = import_engine.get_batch_status(batch_id)
    summary = data_store.get_data_summary()
    return {"status": "ok", "batch": batch, "data_summary": summary}

@app.get("/api/import/status/{batch_id}")
def import_status(batch_id: str, x_api_key: str = None):
    """Get the status of an import batch."""
    check_auth(x_api_key)
    if not _import_available:
        return {"status": "error", "error": _import_error}
    batch = import_engine.get_batch_status(batch_id)
    if not batch:
        return {"status": "error", "error": "Batch not found"}
    return {"status": "ok", "batch": batch}

@app.get("/api/import/data-summary")
def import_data_summary(x_api_key: str = None):
    """Get a summary of all data in the database."""
    check_auth(x_api_key)
    if not _import_available:
        return {"status": "error", "error": _import_error}
    return {"status": "ok", "summary": data_store.get_data_summary()}

@app.get("/api/import/contacts")
def import_get_contacts(contact_type: str = None, limit: int = 100, x_api_key: str = None):
    """Get imported contacts from the database."""
    check_auth(x_api_key)
    if not _import_available:
        return {"status": "error", "error": _import_error}
    contacts = data_store.get_contacts(contact_type=contact_type)
    return {"status": "ok", "contacts": contacts[:limit], "total": len(contacts)}

# ===========================================================================
# BUSINESS DATA SERVICE ENDPOINTS (Phase 2-11)
# ===========================================================================

_bds = None
try:
    import business_data_service as _bds_mod
    _bds = _bds_mod
    _bds_available = True
except Exception as e:
    _bds_available = False
    _bds_error = str(e)

# Owner Operating Layer (intelligence orchestration)
_ool = None
try:
    import owner_operating_layer as _ool_mod
    _ool = _ool_mod
    _ool_available = True
except Exception as e:
    _ool_available = False
    _ool_error = str(e)

# --- Business Config ---
@app.get("/api/business/config")
def get_config(x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.get_business_config()

@app.post("/api/business/config")
def update_config(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.update_business_config(payload or {})

@app.get("/api/business/setup-complete")
def check_setup(x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return {"setup_complete": _bds.is_setup_complete()}

# --- Services ---
@app.get("/api/services")
def get_services(x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return []
    return _bds.get_services()

@app.post("/api/services")
def add_service(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.add_service(payload.get('name', ''), payload.get('description', ''),
                           float(payload.get('avg_price', 0)), payload.get('category', ''))

@app.delete("/api/services/{service_id}")
def delete_service(service_id: int, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return {"deleted": _bds.delete_service(service_id)}

# --- Lead Sources ---
@app.get("/api/lead-sources")
def get_lead_sources(x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return []
    return _bds.get_lead_sources()

@app.post("/api/lead-sources")
def add_lead_source(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.add_lead_source(payload.get('name', ''), payload.get('description', ''))

# --- Sales Stages ---
@app.get("/api/sales-stages")
def get_sales_stages(x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return []
    return _bds.get_sales_stages()

@app.post("/api/sales-stages")
def add_sales_stage(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.add_sales_stage(payload.get('name', ''), payload.get('label', ''),
                               float(payload.get('probability', 0)))

# --- Contacts CRUD ---
@app.get("/api/contacts")
def get_contacts_api(contact_type: str = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return []
    return _bds.get_contacts(contact_type)

@app.post("/api/contacts")
def add_contact_api(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.add_contact(payload or {})

@app.put("/api/contacts/{contact_id}")
def update_contact_api(contact_id: str, payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    print(f"SERVER DEBUG: update_contact_api called, payload keys={list((payload or {}).keys())}", flush=True)
    print(f"SERVER DEBUG: _bds={_bds}, _bds_available={_bds_available}", flush=True)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    result = _bds.update_contact(contact_id, payload or {})
    print(f"SERVER DEBUG: result={result}", flush=True)
    return result

@app.delete("/api/contacts/{contact_id}")
def delete_contact_api(contact_id: str, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return {"deleted": _bds.delete_contact(contact_id)}

# --- Opportunities CRUD ---
@app.get("/api/opportunities")
def get_opps_api(stage: str = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return []
    return _bds.get_opportunities(stage)

@app.post("/api/opportunities")
def add_opp_api(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.add_opportunity(payload or {})

@app.put("/api/opportunities/{opp_id}")
def update_opp_api(opp_id: str, payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.update_opportunity(opp_id, payload or {})

@app.delete("/api/opportunities/{opp_id}")
def delete_opp_api(opp_id: str, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return {"deleted": _bds.delete_opportunity(opp_id)}

# --- Revenue CRUD ---
@app.get("/api/revenue-forecasting")
def revenue_forecasting_endpoint(x_api_key: str = None):
    """Revenue forecasting data with trend and next-month forecast."""
    check_auth(x_api_key)
    _reset_mode_cache()
    result = get_revenue_forecasting_light()
    _cc_cache["fingerprint"] = None  # Invalidate cache
    return _strip_sample_in_real_mode(result)

@app.get("/api/revenue")
def get_revenue_api(x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return []
    return _bds.get_revenue_records()

@app.post("/api/revenue")
def add_revenue_api(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.add_revenue(payload or {})

@app.delete("/api/revenue/{record_id}")
def delete_revenue_api(record_id: str, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return {"deleted": _bds.delete_revenue(record_id)}

# --- Referral Sources CRUD ---
@app.get("/api/referral-sources")
def get_ref_sources_api(x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return []
    return _bds.get_referral_sources()

@app.post("/api/referral-sources")
def add_ref_source_api(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.add_referral_source(payload or {})

@app.delete("/api/referral-sources/{source_id}")
def delete_ref_source_api(source_id: str, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return {"deleted": _bds.delete_referral_source(source_id)}

# --- Actions CRUD ---
@app.get("/api/actions")
def get_actions_api(status: str = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return []
    return _bds.get_actions(status)

@app.post("/api/actions")
def add_action_api(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.add_action(payload or {})

@app.put("/api/actions/{action_id}")
def update_action_api(action_id: str, payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.update_action(action_id, payload or {})

@app.delete("/api/actions/{action_id}")
def delete_action_api(action_id: str, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return {"deleted": _bds.delete_action(action_id)}

# --- Recommendations ---
@app.get("/api/recommendations")
def get_recs_api(status: str = 'active', x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return []
    return _bds.get_recommendations(status)

@app.post("/api/recommendations")
def add_rec_api(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.add_recommendation(payload or {})

@app.post("/api/recommendations/{rec_id}/feedback")
def add_rec_feedback(rec_id: str, payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.add_feedback(rec_id, payload or {})

@app.get("/api/recommendations/accuracy")
def get_rec_accuracy(x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.get_recommendation_accuracy()

# --- Business Memory ---
@app.get("/api/memory")
def get_memory_api(entity_type: str = None, entity_id: str = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return []
    return _bds.get_memories(entity_type, entity_id)

@app.post("/api/memory")
def add_memory_api(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.add_memory(payload or {})

@app.delete("/api/memory/{memory_id}")
def delete_memory_api(memory_id: str, x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return {"deleted": _bds.delete_memory(memory_id)}

# --- Daily Brief ---
@app.get("/api/daily-brief")
def get_daily_brief_api(x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.get_daily_brief()

@app.get("/api/daily-owner-brief")
def get_daily_owner_brief_api(x_api_key: str = None):
    """Unified Daily Owner Brief - the new home page intelligence layer."""
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    if not _ool_available:
        return {"status": "error", "error": _ool_error}
    
    # Gather inputs from EXISTING functions (no duplicate computation)
    kpis = _bds.compute_kpis()
    brief = _bds.get_daily_brief()
    revenue_gap = _bds.get_revenue_gap_recovery()
    weekly_wins = _bds.get_weekly_wins()
    data_quality = _bds.compute_data_quality()
    contacts = _bds.get_contacts()
    opportunities = _bds.get_opportunities()
    referrals = _bds.get_referral_sources()
    actions = _bds.get_actions(status='pending', limit=50)
    config = _bds.get_business_config()
    
    # Peek cache only -- do NOT trigger cold compute of 10s scorecard or 16s V2 engine
    _now = _time_mod.time()
    scorecard = None
    if _scorecard_available and _scorecard_cache["data"] is not None and (_now - _scorecard_cache["ts"]) <= _CACHE_TTL:
        scorecard = _scorecard_cache["data"]
        if 'error' in str(scorecard).lower():
            scorecard = None
    v2_snapshot = None
    if _v2_available and _v2_cache["data"] is not None and (_now - _v2_cache["ts"]) <= _CACHE_TTL:
        v2_snapshot = _v2_cache["data"]
        if 'error' in str(v2_snapshot).lower():
            v2_snapshot = None
    
    # Build the unified brief
    return _ool.build_daily_owner_brief(
        kpis=kpis,
        brief=brief,
        revenue_gap=revenue_gap,
        weekly_wins=weekly_wins,
        data_quality=data_quality,
        contacts=contacts,
        opportunities=opportunities,
        referrals=referrals,
        actions=actions,
        config=config,
        scorecard=scorecard,
        v2_snapshot=v2_snapshot,
    )

# --- Data Quality ---
@app.get("/api/data-quality")
def get_data_quality_api(x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.compute_data_quality()

# --- Revenue Gap Recovery ---
@app.get("/api/revenue-gap-recovery")
def get_revenue_gap_api(x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.get_revenue_gap_recovery()

# --- Weekly Wins ---
@app.get("/api/weekly-wins")
def get_weekly_wins_api(x_api_key: str = None):
    check_auth(x_api_key)
    if not _bds_available:
        return {"status": "error", "error": _bds_error}
    return _bds.get_weekly_wins()


# --- DB Connection Helpers (must be defined before init calls) ---
_PREF_DB_PATH = os.path.join(BASE_DIR, "data.db")

def _get_pref_conn():
    """Get a DB connection for user preferences (Postgres or SQLite)."""
    try:
        import db as _dbmod
        if _dbmod.DB_TYPE == "postgres":
            return _dbmod.get_conn()
    except ImportError:
        pass
    import sqlite3 as _sqlite3
    conn = _sqlite3.connect(_PREF_DB_PATH)
    conn.row_factory = _sqlite3.Row
    return conn

def _return_pref_conn(conn):
    """Return a connection to the pool (Postgres only)."""
    try:
        import db as _dbmod
        if _dbmod.DB_TYPE == "postgres":
            _dbmod.return_conn(conn)
            return
    except ImportError:
        pass
    conn.close()

# --- Demo Business Mode ---
try:
    import demo_business_data as demo_data
    _demo_available = True
    _demo_error = None
except Exception as e:
    _demo_available = False
    _demo_error = str(e)

# Track active demo state (loaded from DB on startup)
_active_demo = {"business_id": None, "scenario_id": None}
_DEMO_DB_PATH = os.path.join(BASE_DIR, "data.db")

def _init_demo_state_table():
    """Create demo_state table and load existing state."""
    global _active_demo
    try:
        conn = _get_pref_conn()
        conn.execute("""CREATE TABLE IF NOT EXISTS demo_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            is_demo_mode INTEGER DEFAULT 1,
            business_id TEXT,
            scenario_id TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        )""")
        # Insert default row with demo mode ON if no row exists
        conn.execute("""INSERT OR IGNORE INTO demo_state (id, is_demo_mode, business_id, scenario_id)
            VALUES (1, 1, 'roofing', 'balanced')""")
        conn.commit()
        row = conn.execute("SELECT business_id, scenario_id FROM demo_state WHERE id = 1").fetchone()
        if row and row["business_id"]:
            _active_demo["business_id"] = row["business_id"]
            _active_demo["scenario_id"] = row["scenario_id"]
        _return_pref_conn(conn)
    except Exception as e:
        print(f"Demo state init error: {e}")

def _save_demo_state(business_id, scenario_id):
    """Persist demo state to DB."""
    try:
        conn = _get_pref_conn()
        conn.execute("""INSERT OR REPLACE INTO demo_state (id, is_demo_mode, business_id, scenario_id, updated_at)
            VALUES (1, 1, ?, ?, datetime('now'))""", (business_id, scenario_id))
        conn.commit()
        _return_pref_conn(conn)
    except Exception as e:
        print(f"Demo state save error: {e}")

# Initialize demo state on module load
_init_demo_state_table()

def _init_user_preferences_table():
    """Create user_preferences table if it doesn't exist."""
    try:
        conn = _get_pref_conn()
        conn.execute("""CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            revenue_goal REAL DEFAULT 85000,
            demo_mode INTEGER DEFAULT 1,
            auto_refresh INTEGER DEFAULT 1,
            refresh_interval INTEGER DEFAULT 60,
            notif_new_leads INTEGER DEFAULT 1,
            notif_revenue_gap INTEGER DEFAULT 1,
            notif_stuck_opps INTEGER DEFAULT 1,
            notif_referral_ops INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT (datetime('now'))
        )""")
        # Insert default row if not exists
        conn.execute("INSERT OR IGNORE INTO user_preferences (id) VALUES (1)")
        conn.commit()
        _return_pref_conn(conn)
    except Exception as e:
        print(f"User preferences init error: {e}")

_init_user_preferences_table()

@app.get("/api/user-preferences")
def get_user_preferences(x_api_key: str = None):
    check_auth(x_api_key)
    try:
        conn = _get_pref_conn()
        row = conn.execute("SELECT * FROM user_preferences WHERE id = 1").fetchone()
        _return_pref_conn(conn)
        if row:
            return {
                "status": "ok",
                "revenue_goal": row["revenue_goal"],
                "demo_mode": bool(row["demo_mode"]),
                "auto_refresh": bool(row["auto_refresh"]),
                "refresh_interval": row["refresh_interval"],
                "notifications": {
                    "new_leads": bool(row["notif_new_leads"]),
                    "revenue_gap": bool(row["notif_revenue_gap"]),
                    "stuck_opps": bool(row["notif_stuck_opps"]),
                    "referral_ops": bool(row["notif_referral_ops"]),
                },
            }
    except Exception as e:
        return {"status": "error", "error": str(e)}
    return {"status": "ok", "revenue_goal": 85000, "demo_mode": True, "auto_refresh": True, "refresh_interval": 60, "notifications": {"new_leads": True, "revenue_gap": True, "stuck_opps": True, "referral_ops": True}}

@app.post("/api/user-preferences")
def save_user_preferences(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    try:
        conn = _get_pref_conn()
        sets = []
        vals = []
        if payload:
            if "revenue_goal" in payload:
                sets.append("revenue_goal = ?")
                vals.append(float(payload["revenue_goal"]))
            if "demo_mode" in payload:
                sets.append("demo_mode = ?")
                vals.append(1 if payload["demo_mode"] else 0)
            if "auto_refresh" in payload:
                sets.append("auto_refresh = ?")
                vals.append(1 if payload["auto_refresh"] else 0)
            if "refresh_interval" in payload:
                sets.append("refresh_interval = ?")
                vals.append(int(payload["refresh_interval"]))
            notif = payload.get("notifications", {})
            if "new_leads" in notif:
                sets.append("notif_new_leads = ?")
                vals.append(1 if notif["new_leads"] else 0)
            if "revenue_gap" in notif:
                sets.append("notif_revenue_gap = ?")
                vals.append(1 if notif["revenue_gap"] else 0)
            if "stuck_opps" in notif:
                sets.append("notif_stuck_opps = ?")
                vals.append(1 if notif["stuck_opps"] else 0)
            if "referral_ops" in notif:
                sets.append("notif_referral_ops = ?")
                vals.append(1 if notif["referral_ops"] else 0)
        if sets:
            sets.append("updated_at = datetime('now')")
            conn.execute(f"UPDATE user_preferences SET {', '.join(sets)} WHERE id = 1", vals)
            conn.commit()
        _return_pref_conn(conn)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/demo/businesses")
def list_demo_businesses(x_api_key: str = None):
    check_auth(x_api_key)
    if not _demo_available:
        return {"status": "error", "error": _demo_error}
    businesses = demo_data.get_demo_list()
    return {"status": "ok", "businesses": businesses}

@app.get("/api/demo/scenarios")
def list_demo_scenarios(x_api_key: str = None):
    check_auth(x_api_key)
    if not _demo_available:
        return {"status": "error", "error": _demo_error}
    scenarios = demo_data.get_scenario_list()
    return {"status": "ok", "scenarios": scenarios}

@app.get("/api/demo/state")
def get_demo_state(x_api_key: str = None):
    check_auth(x_api_key)
    if not _demo_available:
        return {"status": "error", "error": _demo_error}
    return {
        "status": "ok",
        "active_demo": _active_demo,
        "is_demo_mode": _active_demo["business_id"] is not None
    }

@app.post("/api/demo/switch")
def switch_demo(payload: dict, x_api_key: str = None):
    check_auth(x_api_key)
    if not _demo_available:
        return {"status": "error", "error": _demo_error}
    
    business_id = payload.get("business_id", "roofing")
    scenario_id = payload.get("scenario_id", "balanced")
    
    if business_id not in demo_data.DEMO_BUSINESSES:
        return {"status": "error", "error": f"Unknown business: {business_id}"}
    if scenario_id not in demo_data.SCENARIOS:
        return {"status": "error", "error": f"Unknown scenario: {scenario_id}"}
    
    try:
        result = demo_data.materialize_demo(business_id, scenario_id)
        _active_demo["business_id"] = business_id
        _active_demo["scenario_id"] = scenario_id
        _save_demo_state(business_id, scenario_id)
        return {"status": "ok", "result": result}
    except ValueError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Failed to switch demo: {type(e).__name__}: {e}"}

@app.post("/api/demo/reset")
def reset_demo(x_api_key: str = None):
    check_auth(x_api_key)
    if not _demo_available:
        return {"status": "error", "error": _demo_error}
    
    if not _active_demo["business_id"]:
        return {"status": "error", "error": "No active demo to reset"}
    
    business_id = _active_demo["business_id"]
    scenario_id = _active_demo["scenario_id"]
    result = demo_data.materialize_demo(business_id, scenario_id)
    
    return {"status": "ok", "result": result}

@app.get("/")
def root():
    index_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Command Center API", "docs": "/docs"}

@app.get("/styles.css")
def styles():
    return FileResponse(os.path.join(BASE_DIR, "styles.css"), media_type="text/css")

@app.get("/app.js")
def appjs():
    return FileResponse(os.path.join(BASE_DIR, "app.js"), media_type="application/javascript")

# Background pre-computation using FastAPI startup event (avoids circular import deadlock)
@app.on_event("startup")
def _startup_precompute():
    _health_monitor.record_event("application", "started", "INFO",
                                 f"Server started on port {os.environ.get('PORT', '8020')}")
    _health_monitor.run_lightweight_checks()

    # Initialize database schema on startup (creates tables if missing)
    try:
        import db as _dbmod
        _dbmod.init_db()
        print("Database schema initialized")
    except Exception as e:
        print(f"Database schema init error: {e}")

    """Pre-compute V2 and audit data in background after server starts."""
    import threading
    def compute():
        import time as _t
        _t.sleep(5)  # Wait for server to be fully ready
        if _scorecard_available:
            try:
                _compute_scorecard_bg()
            except Exception as e:
                print(f"Scorecard pre-compute error: {e}")
        if _v2_available:
            try:
                _refresh_v2_bg()
                _cached_map()
            except Exception as e:
                print(f"V2 pre-compute error: {e}")
            try:
                _cached_audit()
            except Exception as e:
                print(f"Audit pre-compute error: {e}")
    t = threading.Thread(target=compute, daemon=True)
    t.start()

    # Auto-initialize demo data if demo mode is active but no data exists
    def init_demo():
        import time as _t2
        _t2.sleep(3)  # Wait for DB to be ready
        try:
            if _demo_available and _active_demo.get("business_id"):
                import data_store as _ds
                if not _ds.has_real_contacts():
                    biz = _active_demo.get("business_id", "roofing")
                    sc = _active_demo.get("scenario_id", "balanced")
                    print(f"Auto-materializing demo data: {biz}/{sc}")
                    demo_data.materialize_demo(biz, sc)
                    print("Demo data materialized successfully")
        except Exception as e:
            print(f"Demo auto-init error: {e}")

        # Seed demo actions if needed
        try:
            if _action_store_ready:
                bid = _active_demo.get("business_id", "roofing") or "roofing"
                result = _action_store.seed_demo_actions(business_id=bid)
                if result.get("seeded", 0) > 0:
                    print(f"Seeded {result['seeded']} demo actions")
        except Exception as e:
            print(f"Demo action seeding error: {e}")

        # Seed demo communications + calendar
        try:
            if _comm_store_ready:
                bid = _active_demo.get("business_id", "roofing") or "roofing"
                comm_result = _comm_store.seed_demo_communications(business_id=bid)
                if comm_result.get("seeded", 0) > 0:
                    print(f"Seeded {comm_result['seeded']} demo communications")
                cal_result = _comm_store.seed_demo_calendar(business_id=bid)
                if cal_result.get("seeded", 0) > 0:
                    print(f"Seeded {cal_result['seeded']} demo calendar events")
        except Exception as e:
            print(f"Demo comm/calendar seeding error: {e}")
    threading.Thread(target=init_demo, daemon=True).start()

# ---- CALENDAR OAUTH ENDPOINTS (TEMPORARILY DISABLED) ----

# Initialize calendar_oauth on module load
try:
    import calendar_oauth as _cal_oauth
    _cal_oauth.init_db()
    _cal_oauth_ready = True
except Exception as e:
    print(f"Calendar OAuth init error: {e}")
    _cal_oauth_ready = False

from fastapi.responses import RedirectResponse as _RedirectResponse

@app.get("/api/calendar/oauth/{provider}/start")
def calendar_oauth_start(provider: str, request=None, x_api_key: str = None):
    """Start OAuth flow — returns auth URL for frontend to redirect to."""
    check_auth(x_api_key)
    if not _cal_oauth_ready:
        return JSONResponse(status_code=500, content={"status": "error", "error": "Calendar OAuth not initialized"})
    if provider not in ("google", "outlook"):
        return JSONResponse(status_code=400, content={"status": "error", "error": "Invalid provider"})
    try:
        auth_url = _cal_oauth.get_auth_url(provider, request)
        return {"auth_url": auth_url, "status": "ok"}
    except ValueError as e:
        return JSONResponse(status_code=400, content={"status": "error", "error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})

@app.get("/api/calendar/oauth/{provider}/callback")
def calendar_oauth_callback(provider: str, code: str = None, error: str = None, request=None):
    """OAuth callback — exchange code for tokens, store, redirect to frontend."""
    if not _cal_oauth_ready:
        return JSONResponse(status_code=500, content={"status": "error", "error": "Calendar OAuth not initialized"})
    if error:
        return _RedirectResponse(url=f"/#/client-activity?oauth_error={error}&provider={provider}", status_code=302)
    if not code:
        return JSONResponse(status_code=400, content={"status": "error", "error": "No authorization code provided"})
    if provider not in ("google", "outlook"):
        return JSONResponse(status_code=400, content={"status": "error", "error": "Invalid provider"})
    try:
        bid, _ = _get_business_context()
        tokens = _cal_oauth.exchange_code(provider, code, request)
        conn_info = _cal_oauth.store_connection(business_id=bid, provider=provider, tokens=tokens)
        return _RedirectResponse(url=f"/#/client-activity?oauth_success={provider}", status_code=302)
    except Exception as e:
        return _RedirectResponse(url=f"/#/client-activity?oauth_error={str(e)[:100]}&provider={provider}", status_code=302)

@app.get("/api/calendar/connections")
def calendar_connections_api(x_api_key: str = None):
    """Get calendar connection status for all providers."""
    check_auth(x_api_key)
    if not _cal_oauth_ready:
        return {"connections": {"google": {"configured": False, "connected": False, "email": "", "connected_at": "", "last_synced_at": ""}, "outlook": {"configured": False, "connected": False, "email": "", "connected_at": "", "last_synced_at": ""}}, "status": "ok"}
    bid, _ = _get_business_context()
    status = _cal_oauth.get_status(business_id=bid)
    return {"connections": status, "status": "ok"}

@app.delete("/api/calendar/connections/{provider}")
def calendar_disconnect_api(provider: str, x_api_key: str = None):
    """Disconnect a calendar provider."""
    check_auth(x_api_key)
    if not _cal_oauth_ready:
        return JSONResponse(status_code=500, content={"status": "error", "error": "Calendar OAuth not initialized"})
    if provider not in ("google", "outlook"):
        return JSONResponse(status_code=400, content={"status": "error", "error": "Invalid provider"})
    bid, _ = _get_business_context()
    deleted = _cal_oauth.delete_connection(business_id=bid, provider=provider)
    return {"deleted": deleted, "provider": provider, "status": "ok"}

@app.post("/api/calendar/sync/{provider}")
def calendar_sync_api(provider: str, x_api_key: str = None):
    """Sync events from a calendar provider."""
    check_auth(x_api_key)
    if not _cal_oauth_ready:
        return JSONResponse(status_code=500, content={"status": "error", "error": "Calendar OAuth not initialized"})
    if provider not in ("google", "outlook"):
        return JSONResponse(status_code=400, content={"status": "error", "error": "Invalid provider"})
    bid, _ = _get_business_context()
    try:
        if provider == "google":
            result = _cal_oauth.sync_google_events(business_id=bid)
        else:
            result = _cal_oauth.sync_outlook_events(business_id=bid)
        return {"sync_result": result, "status": "ok"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})

@app.post("/api/calendar/sync-all")
def calendar_sync_all_api(x_api_key: str = None):
    """Sync events from all connected providers."""
    check_auth(x_api_key)
    if not _cal_oauth_ready:
        return JSONResponse(status_code=500, content={"status": "error", "error": "Calendar OAuth not initialized"})
    bid, _ = _get_business_context()
    results = []
    for provider in ("google", "outlook"):
        try:
            if provider == "google":
                result = _cal_oauth.sync_google_events(business_id=bid)
            else:
                result = _cal_oauth.sync_outlook_events(business_id=bid)
            results.append(result)
        except Exception as e:
            results.append({"provider": provider, "error": str(e)})
    return {"sync_results": results, "status": "ok"}

# ---- CLIENT ACTIVITY CENTER ENDPOINTS ----

# Initialize comm store on module load
try:
    import comm_store as _comm_store
    _comm_store.init_db()
    _comm_store_ready = True
except Exception as e:
    print(f"Comm store init error: {e}")
    _comm_store_ready = False

# --- Communications ---

@app.get("/api/communications")
def get_comms_api(
    contact_id: str = None,
    channel: str = None,
    direction: str = None,
    status: str = None,
    limit: int = 100,
    x_api_key: str = None,
):
    check_auth(x_api_key)
    if not _comm_store_ready:
        return {"status": "error", "error": "Comm store not initialized"}
    bid, _ = _get_business_context()
    comms = _comm_store.get_communications(
        business_id=bid, contact_id=contact_id, channel=channel,
        direction=direction, status=status, limit=limit,
    )
    return {"communications": comms, "count": len(comms), "status": "ok"}

@app.post("/api/communications")
def create_comm_api(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _comm_store_ready:
        return JSONResponse(status_code=500, content={"status": "error", "error": "Comm store not initialized"})
    if not payload:
        return JSONResponse(status_code=400, content={"status": "error", "error": "No payload provided"})
    bid, _ = _get_business_context()
    try:
        comm = _comm_store.create_communication(
            business_id=bid,
            contact_id=payload.get("contact_id"),
            contact_name=payload.get("contact_name"),
            channel=payload.get("channel", "note"),
            direction=payload.get("direction", "outbound"),
            subject=payload.get("subject"),
            body=payload.get("body"),
            summary=payload.get("summary"),
            status=payload.get("status", "logged"),
            occurred_at=payload.get("occurred_at"),
            duration_seconds=payload.get("duration_seconds"),
            action_id=payload.get("action_id"),
            metadata=payload.get("metadata"),
        )
        return {"communication": comm, "status": "ok"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})

@app.patch("/api/communications/{comm_id}")
def update_comm_api(comm_id: str, payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _comm_store_ready:
        return JSONResponse(status_code=500, content={"status": "error", "error": "Comm store not initialized"})
    if not payload:
        return JSONResponse(status_code=400, content={"status": "error", "error": "No payload provided"})
    try:
        comm = _comm_store.update_communication(comm_id, payload)
        if not comm:
            return JSONResponse(status_code=404, content={"status": "error", "error": "Communication not found"})
        return {"communication": comm, "status": "ok"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})

# --- Calendar ---

@app.get("/api/calendar/events")
def get_calendar_events_api(
    contact_id: str = None,
    status: str = None,
    start_from: str = None,
    start_to: str = None,
    limit: int = 100,
    x_api_key: str = None,
):
    check_auth(x_api_key)
    if not _comm_store_ready:
        return {"status": "error", "error": "Comm store not initialized"}
    bid, _ = _get_business_context()
    events = _comm_store.get_calendar_events(
        business_id=bid, contact_id=contact_id, status=status,
        start_from=start_from, start_to=start_to, limit=limit,
    )
    return {"events": events, "count": len(events), "status": "ok"}

@app.post("/api/calendar/events")
def create_calendar_event_api(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _comm_store_ready:
        return JSONResponse(status_code=500, content={"status": "error", "error": "Comm store not initialized"})
    if not payload:
        return JSONResponse(status_code=400, content={"status": "error", "error": "No payload provided"})
    bid, _ = _get_business_context()
    try:
        event = _comm_store.create_calendar_event(
            business_id=bid,
            contact_id=payload.get("contact_id"),
            contact_name=payload.get("contact_name"),
            title=payload.get("title", "Untitled Event"),
            description=payload.get("description"),
            location=payload.get("location"),
            event_type=payload.get("event_type", "appointment"),
            start_at=payload.get("start_at"),
            end_at=payload.get("end_at"),
            all_day=payload.get("all_day", False),
            action_id=payload.get("action_id"),
            metadata=payload.get("metadata"),
        )
        return {"event": event, "status": "ok"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})

@app.patch("/api/calendar/events/{event_id}")
def update_calendar_event_api(event_id: str, payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not _comm_store_ready:
        return JSONResponse(status_code=500, content={"status": "error", "error": "Comm store not initialized"})
    if not payload:
        return JSONResponse(status_code=400, content={"status": "error", "error": "No payload provided"})
    try:
        event = _comm_store.update_calendar_event(event_id, payload)
        if not event:
            return JSONResponse(status_code=404, content={"status": "error", "error": "Event not found"})
        return {"event": event, "status": "ok"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})

# --- Timeline ---

@app.get("/api/client-activity/timeline")
def get_timeline_api(
    contact_id: str = None,
    limit: int = 50,
    x_api_key: str = None,
):
    check_auth(x_api_key)
    if not _comm_store_ready:
        return {"status": "error", "error": "Comm store not initialized"}
    bid, _ = _get_business_context()
    timeline = _comm_store.get_timeline(business_id=bid, contact_id=contact_id, limit=limit)
    return {"timeline": timeline, "count": len(timeline), "status": "ok"}

# --- Demo Seeding ---

@app.post("/api/client-activity/seed-demo")
def seed_demo_comm_api(x_api_key: str = None):
    check_auth(x_api_key)
    if not _comm_store_ready:
        return JSONResponse(status_code=500, content={"status": "error", "error": "Comm store not initialized"})
    bid, _ = _get_business_context()
    comm_result = _comm_store.seed_demo_communications(business_id=bid)
    cal_result = _comm_store.seed_demo_calendar(business_id=bid)
    return {"communications": comm_result, "calendar": cal_result, "status": "ok"}

# ---- ACTION EXECUTION CENTER ENDPOINTS ----

# Initialize action store on module load
try:
    import action_store as _action_store
    _action_store.init_db()
    _action_store_ready = True
except Exception as e:
    print(f"Action store init error: {e}")
    _action_store_ready = False

def _action_biz_id():
    """Get the current business_id for actions."""
    bid, _ = _get_business_context()
    return bid

@app.get("/api/action-center")
def get_actions_v2(
    status: str = None,
    priority: str = None,
    source: str = None,
    include_closed: bool = False,
    limit: int = 100,
    x_api_key: str = None,
):
    """Get actions with optional filters."""
    check_auth(x_api_key)
    if not _action_store_ready:
        return {"status": "error", "error": "Action store not initialized"}
    bid = _action_biz_id()
    actions, counts = _action_store.get_actions(
        business_id=bid,
        status=status,
        priority=priority,
        source=source,
        include_closed=include_closed,
        limit=limit,
    )
    return {"actions": actions, "counts": counts, "status": "ok"}

@app.get("/api/action-center/{action_id}")
def get_single_action_v2(action_id: str, x_api_key: str = None):
    """Get a single action by ID with its event history."""
    check_auth(x_api_key)
    if not _action_store_ready:
        return {"status": "error", "error": "Action store not initialized"}
    action = _action_store.get_action(action_id)
    if not action:
        return JSONResponse(status_code=404, content={"status": "error", "error": "Action not found"})
    events = _action_store.get_action_events(action_id)
    return {"action": action, "events": events, "status": "ok"}

@app.post("/api/action-center")
def create_action(payload: dict = None, x_api_key: str = None):
    """Create a new action."""
    check_auth(x_api_key)
    if not _action_store_ready:
        return JSONResponse(status_code=500, content={"status": "error", "error": "Action store not initialized"})
    if not payload:
        return JSONResponse(status_code=400, content={"status": "error", "error": "No payload provided"})
    bid = _action_biz_id()
    try:
        action = _action_store.create_action(
            business_id=bid,
            source=payload.get("source", "manual"),
            source_id=payload.get("source_id"),
            recommendation_id=payload.get("recommendation_id"),
            title=payload.get("title", "Untitled Action"),
            description=payload.get("description"),
            priority=payload.get("priority", "medium"),
            action_type=payload.get("action_type"),
            entity_type=payload.get("entity_type"),
            entity_id=payload.get("entity_id"),
            entity_name=payload.get("entity_name"),
            due_at=payload.get("due_at"),
            notes=payload.get("notes"),
            metadata=payload.get("metadata"),
        )
        return {"action": action, "status": "ok"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})

@app.patch("/api/action-center/{action_id}")
def update_action_endpoint(action_id: str, payload: dict = None, x_api_key: str = None):
    """Partially update an action."""
    check_auth(x_api_key)
    if not _action_store_ready:
        return JSONResponse(status_code=500, content={"status": "error", "error": "Action store not initialized"})
    if not payload:
        return JSONResponse(status_code=400, content={"status": "error", "error": "No payload provided"})
    try:
        action = _action_store.update_action(action_id, payload)
        if not action:
            return JSONResponse(status_code=404, content={"status": "error", "error": "Action not found"})
        return {"action": action, "status": "ok"}
    except ValueError as e:
        return JSONResponse(status_code=400, content={"status": "error", "error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})

@app.post("/api/action-center/{action_id}/events")
def add_action_event(action_id: str, payload: dict = None, x_api_key: str = None):
    """Add an event to an action's history."""
    check_auth(x_api_key)
    if not _action_store_ready:
        return JSONResponse(status_code=500, content={"status": "error", "error": "Action store not initialized"})
    if not payload:
        return JSONResponse(status_code=400, content={"status": "error", "error": "No payload provided"})
    # Verify action exists
    action = _action_store.get_action(action_id)
    if not action:
        return JSONResponse(status_code=404, content={"status": "error", "error": "Action not found"})
    event = _action_store.add_event(
        action_id=action_id,
        event_type=payload.get("event_type", "note_added"),
        note=payload.get("note"),
        outcome=payload.get("outcome"),
        metadata=payload.get("metadata"),
    )
    return {"event": event, "status": "ok"}

@app.post("/api/action-center/seed-demo")
def seed_demo_actions_endpoint(x_api_key: str = None):
    """Manually trigger demo action seeding."""
    check_auth(x_api_key)
    if not _action_store_ready:
        return JSONResponse(status_code=500, content={"status": "error", "error": "Action store not initialized"})
    bid = _action_biz_id()
    result = _action_store.seed_demo_actions(business_id=bid)
    return {**result, "status": "ok"}

# ---- FEEDBACK ENDPOINTS ----

def _get_business_context():
    """Derive business_id and demo state from server state."""
    try:
        import sqlite3 as _sql3
        conn = _sql3.connect(_DEMO_DB_PATH, timeout=3)
        row = conn.execute("SELECT business_id, is_demo_mode FROM demo_state WHERE id=1").fetchone()
        conn.close()
        if row:
            return row[0] or "default", bool(row[1])
        return "default", True
    except Exception:
        return "default", True

@app.post("/api/v2/feedback/recommendation")
def v2_submit_recommendation_feedback(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    business_id, is_demo = _get_business_context()
    environment = "demo" if is_demo else "live"
    rec_id = payload.get("recommendation_id", "")
    rec_key = payload.get("recommendation_key", rec_id)
    rec_type = payload.get("recommendation_type", "")
    source = payload.get("source", "")
    date_gen = payload.get("date_generated", datetime.now().strftime("%Y-%m-%d"))
    user_response = payload.get("user_response", "")
    action_status = payload.get("action_status", "")
    feedback_reason = payload.get("feedback_reason", "")
    valid_responses = ["helpful", "not_helpful", ""]
    if user_response and user_response not in valid_responses:
        return {"status": "error", "error": "Invalid user_response"}
    valid_statuses = ["completed", "in_progress", "not_now", "ignored", ""]
    if action_status and action_status not in valid_statuses:
        return {"status": "error", "error": "Invalid action_status"}
    result = _feedback_engine.submit_recommendation_feedback(
        business_id, environment, rec_id, rec_key, rec_type, source,
        date_gen, user_response, action_status, feedback_reason)
    if result.get("status") == "ok":
        _health_monitor.record_event("feedback", "rec_feedback_submitted", "INFO",
                                     "Feedback: " + user_response + "/" + action_status + " for " + rec_type)
    return result

@app.post("/api/v2/feedback/action-status")
def v2_update_action_status(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    business_id, is_demo = _get_business_context()
    environment = "demo" if is_demo else "live"
    rec_id = payload.get("recommendation_id", "")
    action_status = payload.get("action_status", "")
    valid_statuses = ["completed", "in_progress", "not_now", "ignored"]
    if action_status not in valid_statuses:
        return {"status": "error", "error": "Invalid action_status"}
    return _feedback_engine.update_action_status(business_id, environment, rec_id, action_status)

@app.post("/api/v2/feedback/event")
def v2_record_recommendation_event(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    business_id, is_demo = _get_business_context()
    environment = "demo" if is_demo else "live"
    rec_id = payload.get("recommendation_id", "")
    event_type = payload.get("event_type", "")
    rec_type = payload.get("recommendation_type", "")
    valid_events = ["viewed", "opened", "acted", "dismissed", "completed", "generated"]
    if event_type not in valid_events:
        return {"status": "error", "error": "Invalid event_type"}
    return _feedback_engine.record_recommendation_event(
        business_id, environment, rec_id, event_type, rec_type, payload.get("metadata"))

@app.post("/api/v2/feedback/feature")
def v2_submit_feature_feedback(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    business_id, is_demo = _get_business_context()
    environment = "demo" if is_demo else "live"
    response_text = (payload.get("response_text") or "").strip()
    if not response_text:
        return {"status": "error", "error": "response_text is required"}
    if len(response_text) > 2000:
        return {"status": "error", "error": "response_text too long (max 2000 chars)"}
    return _feedback_engine.submit_feature_feedback(
        business_id, environment, response_text, payload.get("page_context", ""))

@app.post("/api/v2/feedback/satisfaction")
def v2_submit_satisfaction(payload: dict = None, x_api_key: str = None):
    check_auth(x_api_key)
    if not payload:
        return {"status": "error", "error": "No payload provided"}
    business_id, is_demo = _get_business_context()
    environment = "demo" if is_demo else "live"
    rating = payload.get("rating", "")
    prompt_context = payload.get("prompt_context", "")
    return _feedback_engine.submit_satisfaction(business_id, environment, rating, prompt_context)

@app.get("/api/v2/feedback/satisfaction-prompt")
def v2_check_satisfaction_prompt(x_api_key: str = None):
    check_auth(x_api_key)
    business_id, is_demo = _get_business_context()
    environment = "demo" if is_demo else "live"
    should_show = _feedback_engine.should_show_satisfaction_prompt(business_id, environment)
    if should_show:
        _feedback_engine.mark_satisfaction_shown(business_id, environment)
    return {"should_show": should_show}

@app.get("/api/v2/feedback/recommendation-key")
def v2_get_recommendation_key(source: str = "", rec_type: str = "",
                              target_type: str = "", target_id: str = "",
                              action_slug: str = "", x_api_key: str = None):
    check_auth(x_api_key)
    business_id, is_demo = _get_business_context()
    environment = "demo" if is_demo else "live"
    date_gen = datetime.now().strftime("%Y-%m-%d")
    rec_key = FeedbackEngine.generate_recommendation_key(
        business_id, environment, source, rec_type, target_type, target_id, action_slug)
    rec_id = FeedbackEngine.generate_recommendation_id(rec_key, date_gen)
    return {"recommendation_key": rec_key, "recommendation_id": rec_id, "date_generated": date_gen}

# ---- ADMIN FEEDBACK ENDPOINTS ----

@app.get("/api/admin/feedback/report")
def admin_feedback_report(x_admin_key: str = Header(default="", alias="X-Admin-Key"),
                          business_id: str = None, environment: str = None):
    check_admin_auth(x_admin_key)
    report = _feedback_engine.get_admin_feedback_report(business_id, environment)
    _health_monitor.record_admin_action("admin", "view_feedback_report", "feedback", "ok")
    return report

@app.get("/api/admin/feedback/events")
def admin_feedback_events(x_admin_key: str = Header(default="", alias="X-Admin-Key"),
                          business_id: str = None, environment: str = None):
    check_admin_auth(x_admin_key)
    return _feedback_engine.get_event_stats(business_id, environment)

@app.get("/api/admin/feedback/recent")
def admin_feedback_recent(x_admin_key: str = Header(default="", alias="X-Admin-Key"),
                          limit: int = 50):
    check_admin_auth(x_admin_key)
    return {"feedback": _feedback_engine.get_recent_feedback(limit)}

# ---- ADMIN ENDPOINTS ----

@app.get("/admin")
def admin_page():
    """Serve the admin page (separate from main app)."""
    admin_path = os.path.join(BASE_DIR, "admin.html")
    if os.path.exists(admin_path):
        return FileResponse(admin_path)
    return {"status": "error", "error": "Admin page not found"}

@app.get("/api/admin/health")
def admin_health(x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    """Complete health snapshot."""
    check_admin_auth(x_admin_key)
    _health_monitor.run_lightweight_checks()
    return _health_monitor.snapshot()

@app.get("/api/admin/services")
def admin_services(x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    """Service status details."""
    check_admin_auth(x_admin_key)
    _health_monitor.run_lightweight_checks()
    return {"services": _health_monitor.services, "alerts": _health_monitor.alerts}

@app.get("/api/admin/events")
def admin_events(x_admin_key: str = Header(default="", alias="X-Admin-Key"),
                 severity: str = None, limit: int = 50):
    """Recent system events."""
    check_admin_auth(x_admin_key)
    events = list(_health_monitor.events)
    if severity:
        events = [e for e in events if e["severity"] == severity]
    return {"events": events[-limit:], "total": len(_health_monitor.events)}

@app.get("/api/admin/errors")
def admin_errors(x_admin_key: str = Header(default="", alias="X-Admin-Key"),
                severity: str = None, status: str = None, limit: int = 50):
    """Recent errors."""
    check_admin_auth(x_admin_key)
    errors = list(_health_monitor.errors)
    if severity:
        errors = [e for e in errors if e["severity"] == severity]
    if status:
        errors = [e for e in errors if e["status"] == status]
    return {"errors": errors[-limit:], "total": len(_health_monitor.errors)}

@app.get("/api/admin/performance")
def admin_performance(x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    """Performance metrics."""
    check_admin_auth(x_admin_key)
    return {"performance": _health_monitor.get_performance_summary()}

@app.get("/api/admin/freshness")
def admin_freshness(x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    """Data freshness of derived metrics."""
    check_admin_auth(x_admin_key)
    return {"freshness": _health_monitor.get_data_freshness()}

@app.get("/api/admin/audit-log")
def admin_audit_log(x_admin_key: str = Header(default="", alias="X-Admin-Key"),
                    limit: int = 50):
    """Admin audit log."""
    check_admin_auth(x_admin_key)
    return {"audit_log": list(_health_monitor.audit_log)[-limit:]}

@app.post("/api/admin/actions/refresh-health")
def admin_refresh_health(x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    """Refresh health checks."""
    check_admin_auth(x_admin_key)
    _health_monitor.run_lightweight_checks()
    _health_monitor.record_admin_action("admin", "refresh_health", "all", "ok")
    return _health_monitor.snapshot()

@app.post("/api/admin/actions/clear-cache")
def admin_clear_cache(payload: dict = None,
                      x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    """Clear safe caches. Requires confirmation."""
    check_admin_auth(x_admin_key)
    if not payload or payload.get("confirm") != "CLEAR_CACHE":
        return {"status": "error", "error": "Confirmation required: send confirm=CLEAR_CACHE"}
    component = payload.get("component")
    result = _health_monitor.clear_cache(component)
    _health_monitor.record_admin_action("admin", "clear_cache", component or "all", result.get("status", "unknown"))
    return result

@app.post("/api/admin/actions/retry-scorecard")
def admin_retry_scorecard(x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    """Trigger scorecard recomputation."""
    check_admin_auth(x_admin_key)
    result = _health_monitor.retry_scorecard()
    _health_monitor.record_admin_action("admin", "retry_scorecard", "scorecard", result.get("status", "unknown"))
    return result

@app.post("/api/admin/actions/resolve-error/{error_id}")
def admin_resolve_error(error_id: str, payload: dict = None,
                        x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    """Mark an error as resolved."""
    check_admin_auth(x_admin_key)
    resolution = (payload or {}).get("resolution", "Resolved by admin")
    result = _health_monitor.resolve_error(error_id, resolution)
    _health_monitor.record_admin_action("admin", "resolve_error", error_id, result.get("status", "unknown"))
    return result

# Simulation endpoints (non-production only)
@app.post("/api/admin/simulate/{failure_type}")
def admin_simulate_failure(failure_type: str,
                           x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    """Simulate a failure for testing (non-production only)."""
    check_admin_auth(x_admin_key)
    return _health_monitor.simulate_failure("simulation", failure_type)

@app.post("/api/admin/simulate-recovery")
def admin_simulate_recovery(x_admin_key: str = Header(default="", alias="X-Admin-Key")):
    """Clear all simulated failures."""
    check_admin_auth(x_admin_key)
    return _health_monitor.simulate_recovery()

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", "8020"))
    print(f"Starting Unified Command Center on port {port}...")
    print("DEV_MODE:", DEV_MODE)
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
