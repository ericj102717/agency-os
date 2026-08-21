#!/usr/bin/env python3
"""
Owner Operating Layer
=====================
Unified intelligence orchestration module that synthesizes data from all
existing Command Center V2 modules into a single Daily Owner Brief.

This module does NOT duplicate computations. It gathers existing outputs
from business_data_service, cached scorecard/V2 data, and synthesizes them
into prioritized, actionable recommendations.

Architecture:
  business_data_service.py  = data access, CRUD, KPI helpers
  owner_operating_layer.py  = synthesis, prioritization, scoring, grouping
  server.py                 = thin endpoint wrapper
  app.js                    = mobile-first Daily Owner Brief UI
"""

import sys
import os
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DRAFT = "DRAFT -- owner approval required. All recommendations require human review before action."
SAMPLE = "All data marked [SAMPLE]."

# ---------------------------------------------------------------------------
# Priority Scoring Model (transparent, explainable)
# ---------------------------------------------------------------------------

def compute_priority_score(
    revenue_impact: float = 0,
    urgency: str = "low",
    probability: float = 50,
    customer_importance: str = "normal",
    risk: str = "low",
    effort: str = "medium",
) -> Tuple[int, List[Dict[str, str]]]:
    """
    Deterministic priority score 0-100 with explainable factors.
    
    Weights:
      Revenue impact:  30%
      Urgency:         20%
      Probability:     15%
      Risk:            15%
      Customer impact: 10%
      Ease of execution: 10% (inverse - low effort = high score)
    """
    factors = []
    
    # Revenue impact (0-30): scaled logarithmically
    if revenue_impact >= 10000:
        rev_score = 30
    elif revenue_impact >= 5000:
        rev_score = 25
    elif revenue_impact >= 2500:
        rev_score = 20
    elif revenue_impact >= 1000:
        rev_score = 15
    elif revenue_impact > 0:
        rev_score = 10
    else:
        rev_score = 5
    factors.append({"factor": "Revenue impact", "score": rev_score, "max": 30, 
                    "reason": f"${revenue_impact:,.0f} potential revenue" if revenue_impact > 0 else "No direct revenue impact"})
    
    # Urgency (0-20)
    urgency_map = {"critical": 20, "high": 16, "medium": 10, "low": 5}
    urg_score = urgency_map.get(urgency, 8)
    factors.append({"factor": "Urgency", "score": urg_score, "max": 20,
                    "reason": f"{urgency.capitalize()} urgency" + (" -- time-sensitive" if urgency in ("critical","high") else "")})
    
    # Probability (0-15)
    prob_score = int(probability / 100 * 15)
    factors.append({"factor": "Probability", "score": prob_score, "max": 15,
                    "reason": f"{probability:.0f}% likely to produce outcome"})
    
    # Risk (0-15)
    risk_map = {"high": 15, "medium": 9, "low": 4}
    risk_score = risk_map.get(risk, 6)
    factors.append({"factor": "Risk if ignored", "score": risk_score, "max": 15,
                    "reason": f"{risk.capitalize()} risk if no action taken"})
    
    # Customer importance (0-10)
    cust_map = {"high": 10, "normal": 6, "low": 3}
    cust_score = cust_map.get(customer_importance, 6)
    factors.append({"factor": "Customer impact", "score": cust_score, "max": 10,
                    "reason": f"{customer_importance.capitalize()} customer impact"})
    
    # Ease of execution (inverse: low effort = high score, 0-10)
    effort_map = {"low": 10, "medium": 6, "high": 3}
    ease_score = effort_map.get(effort, 6)
    factors.append({"factor": "Ease of execution", "score": ease_score, "max": 10,
                    "reason": f"{effort.capitalize()} effort required"})
    
    total = min(100, sum(f["score"] for f in factors))
    return total, factors


# ---------------------------------------------------------------------------
# Can I Wait? Logic
# ---------------------------------------------------------------------------

def compute_can_wait(urgency: str, revenue_impact: float, deadline: Optional[str] = None) -> Dict[str, Any]:
    """Minimal 'Can I Wait?' analysis derived from urgency, revenue, and deadline."""
    if urgency == "critical":
        return {
            "can_wait": False,
            "message": "This requires immediate attention. Delaying risks losing the opportunity.",
            "recommended_deadline": "Today",
            "revenue_at_risk": revenue_impact,
        }
    elif urgency == "high":
        return {
            "can_wait": True,
            "message": "You can wait 1-2 days, but delaying beyond that reduces the likelihood of a positive outcome.",
            "recommended_deadline": "Within 2 days",
            "revenue_at_risk": revenue_impact * 0.5,
        }
    elif urgency == "medium":
        return {
            "can_wait": True,
            "message": "This can wait up to a week without significant impact, but should not be deferred indefinitely.",
            "recommended_deadline": "Within 1 week",
            "revenue_at_risk": revenue_impact * 0.25,
        }
    else:
        return {
            "can_wait": True,
            "message": "This is not time-sensitive. Address it when higher-priority items are complete.",
            "recommended_deadline": "Within 2 weeks",
            "revenue_at_risk": 0,
        }


# ---------------------------------------------------------------------------
# Trust Labels
# ---------------------------------------------------------------------------

def trust_label(data_type: str) -> str:
    """Label data with trust classification."""
    labels = {
        "fact": "FACT",
        "inference": "INFERENCE",
        "recommendation": "RECOMMENDATION",
        "forecast": "FORECAST",
    }
    return labels.get(data_type, "INFERENCE")


# ---------------------------------------------------------------------------
# Business Health Synthesis
# ---------------------------------------------------------------------------

def build_business_health(
    kpis: Dict[str, Any],
    scorecard: Optional[Dict[str, Any]] = None,
    v2_snapshot: Optional[Dict[str, Any]] = None,
    data_quality: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Synthesize business health from existing data sources."""
    
    # Use scorecard overall score if available, otherwise compute from KPIs
    if scorecard and scorecard.get("overall_score") is not None:
        overall = scorecard["overall_score"]
        overall_label = scorecard.get("overall_label", "Business Health Score")
        overall_status = scorecard.get("overall_status", "")
    else:
        # Fallback: compute from KPIs
        health = 50
        if kpis.get("data_source") == "real":
            health += 10
        goal = kpis.get("revenue_goal", 0)
        if goal and goal > 0:
            mtd = kpis.get("revenue_mtd", 0)
            progress = min(100, (mtd / goal) * 100) if goal else 0
            health = int((health + progress) / 2)
        overall = min(100, max(0, health))
        overall_label = "Business Health Score"
        overall_status = "excellent" if overall >= 80 else "good" if overall >= 60 else "needs_attention" if overall >= 40 else "critical"
    
    # Category scores from scorecard
    categories = {}
    if scorecard and scorecard.get("categories"):
        for cat in scorecard["categories"]:
            cat_name = cat.get("category", "")
            categories[cat_name] = {
                "score": cat.get("score", 0),
                "label": cat.get("label", cat_name),
                "status": cat.get("status", ""),
            }
    
    # Build status summaries
    revenue_goal = kpis.get("revenue_goal", 0)
    revenue_mtd = kpis.get("revenue_mtd", 0)
    revenue_gap = kpis.get("revenue_gap", 0)
    
    def _revenue_status():
        if not revenue_goal or revenue_goal <= 0:
            return {"status": "No goal set", "detail": "Set a revenue goal in Business Setup", "score": None}
        progress = (revenue_mtd / revenue_goal) * 100
        if progress >= 80:
            return {"status": "On track", "detail": f"${revenue_mtd:,.0f} of ${revenue_goal:,.0f} ({progress:.0f}%)", "score": min(100, int(progress))}
        elif progress >= 50:
            return {"status": "Behind", "detail": f"${revenue_mtd:,.0f} of ${revenue_goal:,.0f} ({progress:.0f}%) -- gap of ${revenue_gap:,.0f}", "score": min(100, int(progress))}
        else:
            return {"status": "Critical", "detail": f"Only ${revenue_mtd:,.0f} of ${revenue_goal:,.0f} ({progress:.0f}%)", "score": min(100, int(progress))}
    
    def _lead_status():
        new_leads = kpis.get("new_leads", 0)
        total_contacts = kpis.get("contacts_count", 0)
        if total_contacts == 0:
            return {"status": "No leads yet", "detail": "Add your first lead to begin", "score": 0}
        return {"status": f"{new_leads} new leads", "detail": f"{total_contacts} total contacts", "score": min(100, 60 + new_leads * 5)}
    
    def _customer_status():
        clients = kpis.get("active_clients", 0)
        if clients == 0:
            return {"status": "No clients yet", "detail": "Convert leads to clients", "score": 0}
        return {"status": f"{clients} active clients", "detail": f"CLV: ${kpis.get('client_lifetime_value', 0):,.0f}", "score": min(100, 50 + clients * 5)}
    
    def _pipeline_status():
        pipeline_value = kpis.get("pipeline_value", 0)
        opp_count = kpis.get("opportunities_count", 0)
        if opp_count == 0:
            return {"status": "Empty pipeline", "detail": "No opportunities in pipeline", "score": 0}
        return {"status": f"${pipeline_value:,.0f} in pipeline", "detail": f"{opp_count} opportunities", "score": min(100, 40 + opp_count * 8)}
    
    def _marketing_status():
        if v2_snapshot and v2_snapshot.get("marketing_summary"):
            ms = v2_snapshot["marketing_summary"]
            if isinstance(ms, list) and ms:
                return {"status": f"{len(ms)} active campaigns", "detail": "Content & campaigns running", "score": 60}
        return {"status": "Limited data", "detail": "Marketing performance not fully configured", "score": None}
    
    def _referral_status():
        ref_count = kpis.get("referral_sources_count", 0)
        ref_opps = kpis.get("referral_opportunities", 0)
        if ref_count == 0:
            return {"status": "No referral sources", "detail": "Add referral partners", "score": 0}
        return {"status": f"{ref_count} referral sources", "detail": f"{ref_opps} opportunities", "score": min(100, 50 + ref_count * 8)}
    
    def _operational_risk():
        if data_quality:
            errors = data_quality.get("error_count", 0)
            warnings = data_quality.get("warning_count", 0)
            if errors > 0:
                return {"status": f"{errors} errors", "detail": "Data quality issues need fixing", "score": max(0, 100 - errors * 15)}
            elif warnings > 5:
                return {"status": f"{warnings} warnings", "detail": "Data quality warnings", "score": max(0, 100 - warnings * 3)}
            else:
                return {"status": "Healthy", "detail": "No data quality errors", "score": 90}
        return {"status": "Unknown", "detail": "Data quality not assessed", "score": None}
    
    return {
        "overall_score": overall,
        "overall_label": overall_label,
        "overall_status": overall_status,
        "revenue_goal": kpis.get("revenue_goal", 0),
        "revenue_mtd": kpis.get("revenue_mtd", 0),
        "revenue_status": _revenue_status(),
        "lead_status": _lead_status(),
        "customer_status": _customer_status(),
        "pipeline_status": _pipeline_status(),
        "marketing_status": _marketing_status(),
        "referral_status": _referral_status(),
        "operational_risk": _operational_risk(),
        "category_scores": categories,
        "trust": trust_label("fact") if kpis.get("data_source") == "real" else trust_label("inference"),
    }


# ---------------------------------------------------------------------------
# Recommendation Builder
# ---------------------------------------------------------------------------

def _build_recommendation(
    rec_id: str,
    title: str,
    what: str,
    why: str,
    impact: str,
    action: str,
    action_type: str,
    target_view: str,
    revenue_impact: float = 0,
    urgency: str = "medium",
    probability: float = 50,
    customer_importance: str = "normal",
    risk: str = "low",
    effort: str = "medium",
    source_modules: List[str] = None,
    trust_labels: List[str] = None,
    entity_id: str = "",
    entity_type: str = "",
    deadline: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a single recommendation with full context."""
    score, factors = compute_priority_score(
        revenue_impact=revenue_impact,
        urgency=urgency,
        probability=probability,
        customer_importance=customer_importance,
        risk=risk,
        effort=effort,
    )
    can_wait = compute_can_wait(urgency, revenue_impact, deadline)
    
    return {
        "id": rec_id,
        "title": title,
        "what": what,
        "why": why,
        "impact": impact,
        "recommended_action": action,
        "action_type": action_type,
        "target_view": target_view,
        "entity_id": entity_id,
        "entity_type": entity_type,
        "priority_score": score,
        "priority_factors": factors,
        "can_wait": can_wait,
        "revenue_impact": revenue_impact,
        "urgency": urgency,
        "source_modules": source_modules or [],
        "trust_labels": trust_labels or [trust_label("recommendation")],
        "deadline": deadline,
    }


def build_recommendations(
    kpis: Dict[str, Any],
    brief: Dict[str, Any],
    revenue_gap: Dict[str, Any],
    contacts: List[Dict[str, Any]],
    opportunities: List[Dict[str, Any]],
    referrals: List[Dict[str, Any]],
    actions: List[Dict[str, Any]],
    v2_priorities: List[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Build unified recommendations from all data sources."""
    recs = []
    
    active_opps = [o for o in opportunities if o.get("stage") not in ("closed_won", "closed_lost")]
    stale_leads = [c for c in contacts if c.get("pipeline_stage") == "new" and c.get("contact_type") == "lead"]
    stuck_opps = [o for o in active_opps if o.get("stage") == "contacted"]
    
    # 1. Revenue gap recovery
    gap = revenue_gap.get("gap", 0)
    if gap and gap > 0:
        recovery_actions = revenue_gap.get("recovery_actions", [])
        top_recovery = recovery_actions[0] if recovery_actions else None
        if top_recovery:
            rec_val = float(top_recovery.get("potential_revenue", 0))
            recs.append(_build_recommendation(
                rec_id=f"REC-REVENUE-GAP-{date.today().isoformat()}",
                title=f"Close revenue gap of ${gap:,.0f}",
                what=f"Revenue is ${gap:,.0f} behind your monthly goal of ${revenue_gap.get('goal', 0):,.0f}.",
                why=f"You've earned ${revenue_gap.get('mtd', 0):,.0f} and forecast ${revenue_gap.get('forecast', 0):,.0f}. The gap requires action to close.",
                impact=f"Top recovery action: {top_recovery.get('action', '')} worth ${rec_val:,.0f}.",
                action=top_recovery.get("action", "Review revenue gap recovery plan"),
                action_type="revenue_gap",
                target_view="revenue-forecast",
                revenue_impact=rec_val,
                urgency="high",
                probability=40,
                risk="high",
                effort="medium",
                source_modules=["revenue_forecasting", "revenue_gap_recovery"],
                trust_labels=[trust_label("fact"), trust_label("recommendation")],
                entity_id=top_recovery.get("entity_id", ""),
                entity_type="revenue_gap",
            ))
    
    # 2. High-value opportunity follow-up
    if active_opps:
        biggest = max(active_opps, key=lambda o: float(o.get("estimated_value", 0)))
        val = float(biggest.get("estimated_value", 0))
        if val > 0:
            recs.append(_build_recommendation(
                rec_id=f"REC-OPP-FOLLOWUP-{date.today().isoformat()}",
                title=f"Follow up on {biggest.get('product_type', 'opportunity')} (${val:,.0f})",
                what=f"You have an active {biggest.get('product_type', 'opportunity')} worth ${val:,.0f} in stage '{biggest.get('stage', 'unknown')}'.",
                why="Active opportunities lose momentum quickly without follow-up. This is your highest-value pipeline item.",
                impact=f"${val:,.0f} in potential revenue. Closing this opportunity significantly impacts monthly goal.",
                action=f"Contact the client about this {biggest.get('product_type', 'opportunity')}.",
                action_type="opportunity_followup",
                target_view="pipeline",
                revenue_impact=val,
                urgency="high" if biggest.get("stage") == "qualified" else "medium",
                probability=50,
                risk="high",
                effort="low",
                source_modules=["lead_scoring", "pipeline"],
                trust_labels=[trust_label("fact"), trust_label("recommendation")],
                entity_id=biggest.get("opp_id", ""),
                entity_type="opportunity",
            ))
    
    # 3. Stale leads
    if stale_leads:
        lead = stale_leads[0]
        est_val = 850  # Industry average commission estimate
        today_str = date.today().isoformat()
        recs.append(_build_recommendation(
            rec_id=f"REC-LEAD-CONTACT-{today_str}",
            title=f"Contact {len(stale_leads)} new lead{'s' if len(stale_leads) > 1 else ''} within 24 hours",
            what=f"{len(stale_leads)} lead{'s' if len(stale_leads) > 1 else ''} have not been contacted yet. First: {lead.get('first_name', '')} {lead.get('last_name', '')}.",
            why="Industry data suggests leads contacted within 24 hours have significantly higher conversion rates. Each day of delay reduces conversion probability.",
            impact=f"Estimated ${est_val * len(stale_leads):,.0f} in potential revenue from these leads (based on industry average commission).",
            action=f"Call {lead.get('first_name', '')} {lead.get('last_name', '')} first, then contact remaining {len(stale_leads) - 1} leads." if len(stale_leads) > 1 else f"Call {lead.get('first_name', '')} {lead.get('last_name', '')}.",
            action_type="lead_contact",
            target_view="leads",
            revenue_impact=est_val * len(stale_leads),
            urgency="high",
            probability=30,
            customer_importance="high",
            risk="medium",
            effort="low",
            source_modules=["lead_scoring", "lead_followup"],
            trust_labels=[trust_label("fact"), trust_label("inference"), trust_label("recommendation")],
            entity_id=lead.get("contact_id", ""),
            entity_type="lead",
        ))
    
    # 4. Stuck opportunities
    if stuck_opps:
        stuck_val = sum(float(o.get("estimated_value", 0)) for o in stuck_opps)
        recs.append(_build_recommendation(
            rec_id=f"REC-STUCK-OPPS-{date.today().isoformat()}",
            title=f"Advance {len(stuck_opps)} stuck opportunit{'ies' if len(stuck_opps) > 1 else 'y'}",
            what=f"{len(stuck_opps)} opportunit{'ies are' if len(stuck_opps) > 1 else 'y is'} stuck in 'contacted' stage. Combined value: ${stuck_val:,.0f}.",
            why="Opportunities in 'contacted' stage for too long typically indicate the client needs a next step -- a meeting, quote, or application.",
            impact=f"${stuck_val:,.0f} in pipeline value at risk of going stale.",
            action="Move each opportunity to the next stage by scheduling a follow-up meeting or sending a quote.",
            action_type="opportunity_advance",
            target_view="pipeline",
            revenue_impact=stuck_val,
            urgency="medium",
            probability=35,
            risk="medium",
            effort="medium",
            source_modules=["pipeline", "what_changed"],
            trust_labels=[trust_label("fact"), trust_label("recommendation")],
            entity_type="stuck_opportunities",
        ))
    
    # 5. Referral partner outreach
    active_referrals = [r for r in referrals if r.get("status") == "active" and int(r.get("relationship_strength", 0) or 0) > 50]
    if active_referrals:
        best = max(active_referrals, key=lambda r: int(r.get("referrals_generated", 0) or 0))
        gen = int(best.get("referrals_generated", 0) or 0)
        today_str = date.today().isoformat()
        recs.append(_build_recommendation(
            rec_id=f"REC-REFERRAL-OUTREACH-{today_str}",
            title=f"Reach out to referral partner: {best.get('source_name', '')}",
            what=f"{best.get('source_name', '')} has generated {gen} referrals and has a relationship strength of {best.get('relationship_strength', 0)}/100.",
            why="Active referral partners who haven't been contacted recently may direct referrals elsewhere. Maintaining the relationship keeps referrals flowing.",
            impact=f"Each referral from this partner is worth approximately $850 in potential revenue (industry average estimate).",
            action=f"Call or email {best.get('source_name', '')} to check in and discuss upcoming opportunities.",
            action_type="referral_outreach",
            target_view="referrals",
            revenue_impact=850,
            urgency="medium" if gen > 5 else "low",
            probability=40,
            customer_importance="high",
            risk="low",
            effort="low",
            source_modules=["referral_intelligence", "referral_growth"],
            trust_labels=[trust_label("fact"), trust_label("inference"), trust_label("recommendation")],
            entity_id=best.get("source_id", ""),
            entity_type="referral_partner",
        ))
    
    # 6. Data quality errors
    dq = brief.get("kpis", {})
    if brief.get("needs_attention"):
        for item in brief["needs_attention"]:
            if "data quality" in item.lower() and "error" in item.lower():
                recs.append(_build_recommendation(
                    rec_id=f"REC-DATA-QUALITY-{date.today().isoformat()}",
                    title="Fix data quality errors",
                    what=item,
                    why="Data quality errors affect the accuracy of all business calculations and recommendations.",
                    impact="Inaccurate data leads to incorrect business decisions and missed opportunities.",
                    action="Review and fix data quality issues in the Data Quality dashboard.",
                    action_type="data_quality_fix",
                    target_view="data-quality",
                    revenue_impact=0,
                    urgency="medium",
                    probability=100,
                    risk="medium",
                    effort="low",
                    source_modules=["crm_management", "data_quality"],
                    trust_labels=[trust_label("fact")],
                    entity_type="data_quality",
                ))
                break
    
    # 7. Pending actions
    pending_actions = [a for a in actions if a.get("status") == "pending"]
    if pending_actions and not any('LEAD-CONTACT' in r["id"] for r in recs):
        top_action = pending_actions[0]
        recs.append(_build_recommendation(
            rec_id=f"REC-PENDING-ACTION-{date.today().isoformat()}",
            title=f"Complete pending action: {top_action.get('title', 'Action item')}",
            what=top_action.get("title", "A pending action needs your attention."),
            why=top_action.get("description", "This action has been queued and is awaiting completion."),
            impact="Completing queued actions keeps your business operations running smoothly.",
            action="Review and complete this action.",
            action_type="complete_action",
            target_view="actions",
            revenue_impact=0,
            urgency="low",
            probability=80,
            risk="low",
            effort="low",
            source_modules=["action_center"],
            trust_labels=[trust_label("fact")],
            entity_id=str(top_action.get("action_id", "")),
            entity_type="action",
        ))
    
    # Sort by priority score
    recs.sort(key=lambda r: r["priority_score"], reverse=True)
    return recs


# ---------------------------------------------------------------------------
# What Changed Synthesis
# ---------------------------------------------------------------------------

def build_meaningful_changes(
    v2_snapshot: Optional[Dict[str, Any]] = None,
    kpis: Dict[str, Any] = None,
    brief: Dict[str, Any] = None,
) -> List[Dict[str, Any]]:
    """Extract meaningful changes from V2 What Changed module."""
    changes = []
    
    # From V2 engine
    if v2_snapshot and v2_snapshot.get("what_changed_summary"):
        for change in v2_snapshot["what_changed_summary"][:5]:
            changes.append({
                "title": change.get("title", "Change detected"),
                "severity": change.get("severity", "informational"),
                "description": change.get("description", ""),
                "category": change.get("category", ""),
                "recommended_action": change.get("recommended_action", ""),
                "source": "What Changed? Agent",
                "trust": trust_label("fact"),
            })
    
    # From brief needs_attention (these represent changes from normal)
    if brief and brief.get("needs_attention"):
        for item in brief["needs_attention"][:3]:
            if "data quality" not in item.lower():
                changes.append({
                    "title": item,
                    "severity": "warning",
                    "description": item,
                    "category": "attention",
                    "recommended_action": "Review and take action",
                    "source": "Daily Brief",
                    "trust": trust_label("fact"),
                })
    
    # Revenue status change
    if kpis:
        gap = kpis.get("revenue_gap", 0)
        if gap and gap > 0:
            changes.append({
                "title": f"Revenue is ${gap:,.0f} behind goal",
                "severity": "warning" if gap > 5000 else "informational",
                "description": f"MTD revenue of ${kpis.get('revenue_mtd', 0):,.0f} with forecast of ${kpis.get('revenue_forecast', 0):,.0f} against goal of ${kpis.get('revenue_goal', 0):,.0f}.",
                "category": "revenue",
                "recommended_action": "Review revenue gap recovery plan",
                "source": "Revenue Forecasting",
                "trust": trust_label("fact"),
            })
    
    return changes[:7]  # Limit to 7 most important


# ---------------------------------------------------------------------------
# Today / This Week / Later Grouping
# ---------------------------------------------------------------------------

def group_by_horizon(recommendations: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group recommendations into time horizons based on urgency and can_wait."""
    today = []
    this_week = []
    later = []
    
    for rec in recommendations:
        urgency = rec.get("urgency", "low")
        can_wait = rec.get("can_wait", {})
        deadline = can_wait.get("recommended_deadline", "")
        
        if urgency in ("critical", "high") or "Today" in deadline or "2 days" in deadline:
            today.append(rec)
        elif urgency == "medium" or "week" in deadline.lower():
            this_week.append(rec)
        else:
            later.append(rec)
    
    return {
        "today": today[:5],
        "this_week": this_week[:5],
        "later": later[:5],
    }


# ---------------------------------------------------------------------------
# Low Data Warnings
# ---------------------------------------------------------------------------

def check_low_data(kpis: Dict[str, Any], contacts: List[Dict], opportunities: List[Dict]) -> List[Dict[str, str]]:
    """Check for insufficient data and return warnings."""
    warnings = []
    
    if kpis.get("data_source") != "real":
        warnings.append({
            "area": "Business Data",
            "message": "Not enough data yet. Using demo data. Import your contacts and revenue to get personalized recommendations.",
            "action": "Use the Data Import wizard or add leads manually.",
        })
    
    contact_count = len(contacts)
    if contact_count < 5:
        warnings.append({
            "area": "Contacts",
            "message": f"Not enough data yet. Only {contact_count} contacts in the system. Recommendations will be limited until you have more data.",
            "action": "Add at least 10-20 contacts for meaningful insights.",
        })
    
    if len(opportunities) < 3:
        warnings.append({
            "area": "Pipeline",
            "message": f"Not enough data yet. Only {len(opportunities)} opportunities in the pipeline. Revenue forecasting accuracy is low.",
            "action": "Add opportunities as you identify them for better forecasting.",
        })
    
    revenue_goal = kpis.get("revenue_goal", 0)
    if not revenue_goal or revenue_goal <= 0:
        warnings.append({
            "area": "Revenue Goal",
            "message": "Not enough data yet. No revenue goal set. Set a monthly revenue goal in Business Setup to enable gap analysis.",
            "action": "Complete the Business Setup wizard.",
        })
    
    return warnings


# ---------------------------------------------------------------------------
# MAIN: Build Daily Owner Brief
# ---------------------------------------------------------------------------

def build_daily_owner_brief(
    kpis: Dict[str, Any],
    brief: Dict[str, Any],
    revenue_gap: Dict[str, Any],
    weekly_wins: Dict[str, Any],
    data_quality: Dict[str, Any],
    contacts: List[Dict[str, Any]],
    opportunities: List[Dict[str, Any]],
    referrals: List[Dict[str, Any]],
    actions: List[Dict[str, Any]],
    config: Dict[str, Any],
    scorecard: Optional[Dict[str, Any]] = None,
    v2_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build the complete Daily Owner Brief response.
    
    All inputs are pre-computed by the caller (server.py) from existing functions.
    This module does NOT call any external APIs or recompute heavy operations.
    """
    today_str = date.today().isoformat()
    
    # 1. Business Health
    business_health = build_business_health(kpis, scorecard, v2_snapshot, data_quality)
    
    # 2. Recommendations
    recommendations = build_recommendations(
        kpis=kpis,
        brief=brief,
        revenue_gap=revenue_gap,
        contacts=contacts,
        opportunities=opportunities,
        referrals=referrals,
        actions=actions,
    )
    
    # 3. Primary action (#1 recommendation)
    primary_action = recommendations[0] if recommendations else None
    
    # 4. What Matters Today (top 3-5 items)
    what_matters_today = []
    for rec in recommendations[:5]:
        what_matters_today.append({
            "id": rec["id"],
            "what": rec["what"],
            "why": rec["why"],
            "impact": rec["impact"],
            "action": rec["recommended_action"],
            "priority_score": rec["priority_score"],
            "urgency": rec["urgency"],
            "target_view": rec["target_view"],
            "entity_id": rec.get("entity_id", ""),
            "action_type": rec.get("action_type", ""),
            "can_wait": rec["can_wait"],
        })
    
    # 5. Actions by horizon
    actions_by_horizon = group_by_horizon(recommendations)
    
    # 6. Meaningful changes
    meaningful_changes = build_meaningful_changes(v2_snapshot, kpis, brief)
    
    # 7. Low data warnings
    low_data_warnings = check_low_data(kpis, contacts, opportunities)
    
    # 8. Weekly wins summary
    wins_summary = {
        "total_wins": weekly_wins.get("total_wins", 0),
        "new_clients": weekly_wins.get("new_clients", 0),
        "revenue_received": weekly_wins.get("revenue_received", 0),
        "new_opportunities": weekly_wins.get("new_opportunities", 0),
    }
    
    return {
        "date": today_str,
        "timestamp": datetime.now().isoformat(),
        "business_name": config.get("business_name", "Your Business"),
        "kpis": kpis,
        "business_health": business_health,
        "primary_action": primary_action,
        "what_matters_today": what_matters_today,
        "actions_by_horizon": actions_by_horizon,
        "meaningful_changes": meaningful_changes,
        "low_data_warnings": low_data_warnings,
        "weekly_wins": wins_summary,
        "total_recommendations": len(recommendations),
        "disclaimer": f"{SAMPLE} {DRAFT}",
    }
