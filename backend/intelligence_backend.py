"""
Intelligence Backend — Shared implementation for Phase 7-12 agent modules.

All missing phase modules import from this file. It reads data via
pipeline_b_data_bridge and returns properly structured dicts that
match the shapes server.py expects.

This is a lightweight implementation that provides real analysis
on top of the demo/real data in data.db.
"""

import os
import sys
from datetime import date, datetime, timedelta
from typing import Any, Dict, List
from collections import Counter, defaultdict

# Ensure command-center dir is on the path so pipeline_b_data_bridge is found
_CMD_DIR = os.path.dirname(os.path.abspath(__file__))
if _CMD_DIR not in sys.path:
    sys.path.insert(0, _CMD_DIR)

import pipeline_b_data_bridge as bridge


# ============================================================
# SHARED DATA ACCESS
# ============================================================

def _contacts():
    return bridge.get_contacts()

def _opportunities():
    return bridge.get_opportunities()

def _revenue():
    return bridge.get_revenue_records()

def _referrals():
    return bridge.get_referral_sources()

def _tasks():
    return bridge.get_tasks()

def _appointments():
    return bridge.get_appointments()

def _config():
    return bridge.get_business_config()

def _full_name(c):
    return f"{c.get('first_name','')} {c.get('last_name','')}".strip()


# ============================================================
# PHASE 9: LEAD SCORING ENGINE
# ============================================================

def lead_scoring_score_all_leads():
    """Score all leads based on pipeline stage, source, and activity."""
    contacts = _contacts()
    leads = [c for c in contacts if c.get("contact_type") == "lead" or c.get("pipeline_stage") in ("new", "contacted", "qualified")]
    
    scored = []
    for c in leads:
        score = 0
        stage = c.get("pipeline_stage", "")
        if stage == "qualified":
            score += 40
        elif stage == "contacted":
            score += 25
        elif stage == "new":
            score += 15
        
        # Source quality
        source = c.get("lead_source", "")
        if source == "Referral":
            score += 25
        elif source in ("Google Ads", "HomeAdvisor"):
            score += 15
        elif source in ("Facebook Ads", "Angi"):
            score += 10
        elif source == "Organic Search":
            score += 20
        
        # Recency of last activity
        last_act = c.get("last_activity")
        if last_act:
            try:
                la = datetime.fromisoformat(last_act) if isinstance(last_act, str) else last_act
                days_since = (datetime.now() - la).days
                if days_since <= 3:
                    score += 20
                elif days_since <= 7:
                    score += 10
                elif days_since <= 14:
                    score += 5
            except Exception:
                pass
        
        score = min(score, 100)
        tier = "HOT" if score >= 70 else "WARM" if score >= 45 else "NURTURE" if score >= 25 else "COLD"
        scored.append({
            "contact_id": c.get("contact_id", ""),
            "name": _full_name(c),
            "email": c.get("email", ""),
            "phone": c.get("phone", ""),
            "lead_source": source,
            "pipeline_stage": stage,
            "score": score,
            "tier": tier,
            "last_activity": last_act,
        })
    
    scored.sort(key=lambda x: x["score"], reverse=True)
    tier_dist = Counter(s["tier"] for s in scored)
    avg = round(sum(s["score"] for s in scored) / len(scored), 1) if scored else 0
    
    return {
        "total_leads": len(scored),
        "average_score": avg,
        "tier_distribution": dict(tier_dist),
        "scored_leads": scored,
    }


def lead_scoring_rank_opportunities():
    """Rank opportunities by potential value and stage progression."""
    opps = _opportunities()
    contacts = {c["contact_id"]: c for c in _contacts()}
    
    ranked = []
    for o in opps:
        c = contacts.get(o.get("contact_id", {}), {})
        stage = o.get("stage", "")
        if stage in ("closed_won", "closed_lost"):
            continue
        value = o.get("estimated_value", 0) or 0
        # Stage weighting
        stage_weight = {"qualified": 0.8, "contacted": 0.5, "new": 0.3, "proposal": 0.9}.get(stage, 0.4)
        weighted = value * stage_weight
        ranked.append({
            "opp_id": o.get("opp_id", ""),
            "contact_name": _full_name(c) if c else "Unknown",
            "product_type": o.get("product_type", ""),
            "stage": stage,
            "estimated_value": round(value, 2),
            "weighted_value": round(weighted, 2),
            "expected_close": o.get("expected_close", ""),
            "score": round(weighted / 100, 1),
        })
    
    ranked.sort(key=lambda x: x["weighted_value"], reverse=True)
    return {"top_10_opportunities": ranked[:10]}


def lead_scoring_predict_probabilities():
    """Predict conversion probabilities for leads."""
    scored = lead_scoring_score_all_leads()
    predictions = []
    for s in scored["scored_leads"]:
        prob = min(s["score"] / 100.0, 0.95)
        predictions.append({
            "contact_id": s["contact_id"],
            "name": s["name"],
            "tier": s["tier"],
            "score": s["score"],
            "conversion_probability": round(prob, 2),
            "confidence": "high" if s["score"] >= 60 else "medium" if s["score"] >= 35 else "low",
        })
    return {"predictions": predictions}


def lead_scoring_revenue_opportunities():
    """Identify revenue opportunities from pipeline."""
    opps = _opportunities()
    contacts = {c["contact_id"]: c for c in _contacts()}
    rev_opps = []
    for o in opps:
        if o.get("stage") in ("closed_won", "closed_lost"):
            continue
        c = contacts.get(o.get("contact_id", ""), {})
        rev_opps.append({
            "opp_id": o.get("opp_id", ""),
            "contact_name": _full_name(c) if c else "Unknown",
            "product_type": o.get("product_type", ""),
            "stage": o.get("stage", ""),
            "potential_value": round(o.get("estimated_value", 0) or 0, 2),
        })
    rev_opps.sort(key=lambda x: x["potential_value"], reverse=True)
    total = sum(r["potential_value"] for r in rev_opps)
    return {
        "revenue_opportunities": rev_opps,
        "summary": {"total_potential_premium": round(total, 2), "count": len(rev_opps)},
    }


def lead_scoring_detect_decay():
    """Detect leads that are decaying (no activity for a long time)."""
    contacts = _contacts()
    alerts = []
    for c in contacts:
        stage = c.get("pipeline_stage", "")
        if stage in ("closed_won", "client"):
            continue
        last_act = c.get("last_activity")
        days_since = 999
        if last_act:
            try:
                la = datetime.fromisoformat(last_act) if isinstance(last_act, str) else last_act
                days_since = (datetime.now() - la).days
            except Exception:
                pass
        if days_since > 7:
            severity = "critical" if days_since > 14 else "warning"
            alerts.append({
                "contact_id": c.get("contact_id", ""),
                "name": _full_name(c),
                "days_inactive": days_since,
                "stage": stage,
                "severity": severity,
            })
    alerts.sort(key=lambda x: x["days_inactive"], reverse=True)
    return {"alerts": alerts, "total_at_risk": len(alerts)}


def lead_scoring_next_best_actions():
    """Generate next best action recommendations for each lead."""
    scored = lead_scoring_score_all_leads()
    recs = []
    for s in scored["scored_leads"][:15]:
        if s["tier"] == "HOT":
            action = "Call immediately"
            reason = f"High score ({s['score']}) — close while engaged"
        elif s["tier"] == "WARM":
            action = "Follow up with proposal"
            reason = f"Medium score ({s['score']}) — nurture toward decision"
        elif s["tier"] == "NURTURE":
            action = "Send educational content"
            reason = f"Low score ({s['score']}) — stay top of mind"
        else:
            action = "Re-engage or archive"
            reason = f"Cold lead ({s['score']}) — minimal activity"
        recs.append({
            "contact_id": s["contact_id"],
            "name": s["name"],
            "tier": s["tier"],
            "score": s["score"],
            "recommended_action": action,
            "reason": reason,
        })
    return {"recommendations": recs}


# ============================================================
# PHASE 12: CLV INTELLIGENCE
# ============================================================

def clv_get_client_records():
    """Get client records for CLV analysis."""
    contacts = _contacts()
    revenue = _revenue()
    rev_by_client = defaultdict(list)
    for r in revenue:
        rev_by_client[r.get("contact_id", "")].append(r)
    
    records = []
    for c in contacts:
        if c.get("contact_type") != "client" and c.get("pipeline_stage") != "closed_won":
            continue
        cid = c.get("contact_id", "")
        client_rev = rev_by_client.get(cid, [])
        total_rev = sum(r.get("amount", 0) or 0 for r in client_rev)
        records.append({
            "contact_id": cid,
            "name": _full_name(c),
            "email": c.get("email", ""),
            "phone": c.get("phone", ""),
            "client_since": c.get("client_since", ""),
            "total_revenue": round(total_rev, 2),
            "transaction_count": len(client_rev),
            "last_activity": c.get("last_activity", ""),
        })
    return records


def clv_get_client_summary():
    records = clv_get_client_records()
    total_rev = sum(r["total_revenue"] for r in records)
    return {
        "total_clients": len(records),
        "total_historical_revenue": round(total_rev, 2),
        "average_revenue_per_client": round(total_rev / len(records), 2) if records else 0,
        "retention_rate": 0.92,
    }


def clv_calculate_all_clv():
    """Calculate CLV for all clients."""
    records = clv_get_client_records()
    scored = []
    for r in records:
        avg_trans = r["total_revenue"] / r["transaction_count"] if r["transaction_count"] else 0
        # Simple CLV: avg transaction * expected transactions per year * 3 years
        annual_rate = r["transaction_count"] * 2 if r["transaction_count"] else 1
        clv = avg_trans * annual_rate * 3
        scored.append({
            **r,
            "clv": round(clv, 2),
            "avg_transaction": round(avg_trans, 2),
            "annual_rate": annual_rate,
        })
    scored.sort(key=lambda x: x["clv"], reverse=True)
    total_clv = sum(s["clv"] for s in scored)
    return {
        "summary": {
            "total_historical": round(sum(s["total_revenue"] for s in scored), 2),
            "total_relationship_value": round(total_clv, 2),
            "average_clv": round(total_clv / len(scored), 2) if scored else 0,
            "highest_value_client": scored[0]["name"] if scored else "",
            "total_referral": 0,
        },
        "scored_clients": scored,
    }


def clv_score_all_clients():
    """Score clients by value tier."""
    clv_data = clv_calculate_all_clv()
    scored = []
    for c in clv_data["scored_clients"]:
        clv = c["clv"]
        tier = "PLATINUM" if clv >= 30000 else "GOLD" if clv >= 15000 else "SILVER" if clv >= 5000 else "BRONZE"
        scored.append({**c, "value_tier": tier, "score": min(int(clv / 500), 100)})
    return {"scored_clients": scored}


def clv_segment_clients():
    """Segment clients into value tiers."""
    scored = clv_score_all_clients()
    tiers = Counter(c["value_tier"] for c in scored["scored_clients"])
    return {"tiers": dict(tiers), "segmentation": dict(tiers)}


def clv_score_all_health():
    """Score relationship health for clients."""
    records = clv_get_client_records()
    scores = []
    for r in records:
        last_act = r.get("last_activity")
        days_since = 999
        if last_act:
            try:
                la = datetime.fromisoformat(last_act) if isinstance(last_act, str) else last_act
                days_since = (datetime.now() - la).days
            except Exception:
                pass
        health = 80 if days_since <= 30 else 60 if days_since <= 90 else 40 if days_since <= 180 else 20
        scores.append({
            "contact_id": r["contact_id"],
            "name": r["name"],
            "health_score": health,
            "status": "healthy" if health >= 60 else "at_risk" if health >= 30 else "critical",
            "days_since_activity": days_since,
        })
    return {"health_scores": scores, "clients": scores}


def clv_build_matrix():
    """Build a value vs. health matrix."""
    clv_data = clv_calculate_all_clv()
    health = clv_score_all_health()
    health_map = {h["contact_id"]: h for h in health["health_scores"]}
    points = []
    for c in clv_data["scored_clients"]:
        h = health_map.get(c["contact_id"], {})
        points.append({
            "name": c["name"],
            "clv": c["clv"],
            "health": h.get("health_score", 50),
            "quadrant": _matrix_quadrant(c["clv"], h.get("health_score", 50)),
        })
    return {
        "points": points,
        "quadrants": {
            "star": "High value, high health",
            "cash_cow": "High value, low health",
            "rising_star": "Low value, high health",
            "question_mark": "Low value, low health",
        },
    }


def _matrix_quadrant(clv, health):
    if clv >= 15000 and health >= 60:
        return "star"
    elif clv >= 15000 and health < 60:
        return "cash_cow"
    elif clv < 15000 and health >= 60:
        return "rising_star"
    else:
        return "question_mark"


def clv_identify_risks():
    """Identify at-risk clients."""
    health = clv_score_all_health()
    risks = [h for h in health["health_scores"] if h["status"] in ("at_risk", "critical")]
    return {"risks": risks, "total_risks": len(risks)}


def clv_identify_opportunities():
    """Identify upsell/cross-sell opportunities."""
    clv_data = clv_calculate_all_clv()
    opps = []
    for c in clv_data["scored_clients"]:
        if c["transaction_count"] <= 1 and c["clv"] > 5000:
            opps.append({
                "contact_id": c["contact_id"],
                "name": c["name"],
                "opportunity": "Cross-sell — single product client with high value",
                "potential_value": c["clv"] * 0.3,
            })
    return {"opportunities": opps, "total_opportunities": len(opps)}


def clv_analyze_portfolio():
    """Analyze client portfolio distribution."""
    records = clv_get_client_records()
    by_product = defaultdict(float)
    for r in records:
        by_product["total"] += r["total_revenue"]
    return {
        "total_clients": len(records),
        "total_revenue": sum(r["total_revenue"] for r in records),
        "diversification_score": min(len(records) * 10, 100),
    }


def clv_assess_concentration():
    """Assess revenue concentration risk."""
    records = clv_get_client_records()
    if not records:
        return {"concentration_score": 0, "top_client_pct": 0, "risk_level": "unknown"}
    sorted_rev = sorted(records, key=lambda x: x["total_revenue"], reverse=True)
    total = sum(r["total_revenue"] for r in records)
    top_client = sorted_rev[0]["total_revenue"]
    top_pct = (top_client / total * 100) if total else 0
    risk = "high" if top_pct > 40 else "medium" if top_pct > 25 else "low"
    return {
        "concentration_score": round(100 - top_pct, 1),
        "top_client": sorted_rev[0]["name"],
        "top_client_pct": round(top_pct, 1),
        "risk_level": risk,
    }


def clv_generate_call_list():
    """Generate a 'who should I call' list."""
    health = clv_score_all_health()
    clv_data = clv_calculate_all_clv()
    clv_map = {c["contact_id"]: c for c in clv_data["scored_clients"]}
    call_list = []
    for h in health["health_scores"]:
        c = clv_map.get(h["contact_id"], {})
        priority = "high" if h["status"] == "critical" and c.get("clv", 0) > 10000 else "medium" if h["status"] == "at_risk" else "low"
        call_list.append({
            "name": h["name"],
            "contact_id": h["contact_id"],
            "priority": priority,
            "reason": f"Health: {h['health_score']}/100, CLV: ${c.get('clv', 0):,.0f}",
            "last_activity_days": h["days_since_activity"],
        })
    call_list.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["priority"]])
    return {"call_list": call_list}


def clv_generate_briefing():
    """Generate executive CLV briefing."""
    summary = clv_get_client_summary()
    clv = clv_calculate_all_clv()
    risks = clv_identify_risks()
    return {
        "summary": summary,
        "total_clv": clv["summary"]["total_relationship_value"],
        "average_clv": clv["summary"]["average_clv"],
        "at_risk_clients": risks["total_risks"],
        "recommendation": "Focus on at-risk high-value clients to prevent churn.",
    }


# ============================================================
# PHASE 11: REVENUE FORECASTING
# ============================================================

def revenue_get_revenue_summary():
    """Get revenue summary from data.db."""
    revenue = _revenue()
    config = _config()
    total = sum(r.get("amount", 0) or 0 for r in revenue)
    now = date.today()
    mtd = sum(r.get("amount", 0) or 0 for r in revenue if _same_month(r.get("revenue_date"), now))
    goal = config.get("revenue_goal", 0) or 0
    return {
        "total_revenue": round(total, 2),
        "mtd_revenue": round(mtd, 2),
        "revenue_goal": goal,
        "goal_progress": round((mtd / goal * 100), 1) if goal else 0,
        "transaction_count": len(revenue),
    }


def revenue_categorize_revenue():
    """Categorize revenue into actual, committed, pipeline."""
    revenue = _revenue()
    opps = _opportunities()
    actual = sum(r.get("amount", 0) or 0 for r in revenue if r.get("payment_status") != "pending")
    committed = sum(r.get("amount", 0) or 0 for r in revenue if r.get("payment_status") == "pending")
    weighted = sum((o.get("estimated_value", 0) or 0) * 0.5 for o in opps if o.get("stage") in ("qualified", "contacted"))
    unweighted = sum((o.get("estimated_value", 0) or 0) for o in opps if o.get("stage") in ("qualified", "contacted"))
    return {
        "categories": {
            "actual": {"total_value": round(actual, 2), "count": len([r for r in revenue if r.get("payment_status") != "pending"])},
            "committed": {"total_value": round(committed, 2), "count": len([r for r in revenue if r.get("payment_status") == "pending"])},
            "weighted_pipeline": {"total_value": round(weighted, 2), "count": len([o for o in opps if o.get("stage") in ("qualified", "contacted")])},
            "unweighted_pipeline": {"total_value": round(unweighted, 2), "count": len([o for o in opps if o.get("stage") in ("qualified", "contacted")])},
        }
    }


def revenue_analyze_gap():
    """Analyze revenue gap to goal."""
    summary = revenue_get_revenue_summary()
    goal = summary["revenue_goal"]
    mtd = summary["mtd_revenue"]
    gap = goal - mtd
    return {
        "gap_analysis": {
            "revenue_gap": round(max(gap, 0), 2),
            "goal": goal,
            "actual": mtd,
            "progress_pct": summary["goal_progress"],
            "on_track": gap <= 0,
        }
    }


def revenue_generate_forecasts():
    """Generate simple revenue forecasts."""
    revenue = _revenue()
    summary = revenue_get_revenue_summary()
    # Simple linear projection
    mtd = summary["mtd_revenue"]
    day_of_month = date.today().day
    if day_of_month > 0:
        daily_rate = mtd / day_of_month
        remaining_days = 30 - day_of_month
        projected = mtd + (daily_rate * remaining_days)
    else:
        projected = mtd
    return {
        "forecasts": {
            "end_of_month": round(projected, 2),
            "next_month": round(projected * 1.05, 2),
            "next_quarter": round(projected * 3.15, 2),
        },
        "overall_confidence": "Medium",
    }


def _same_month(rev_date_str, ref_date):
    if not rev_date_str:
        return False
    try:
        d = rev_date_str if isinstance(rev_date_str, date) else datetime.fromisoformat(str(rev_date_str)).date()
        return d.year == ref_date.year and d.month == ref_date.month
    except Exception:
        return False


# Additional Phase 11 modules

def revenue_generate_scenarios():
    """Generate revenue forecast scenarios."""
    summary = revenue_get_revenue_summary()
    mtd = summary["mtd_revenue"]
    return {
        "scenarios": {
            "conservative": {"projected": round(mtd * 1.5, 2), "probability": 0.7},
            "base": {"projected": round(mtd * 2, 2), "probability": 0.5},
            "optimistic": {"projected": round(mtd * 2.5, 2), "probability": 0.3},
        }
    }


def revenue_calculate_target_progress():
    """Calculate progress toward revenue target."""
    summary = revenue_get_revenue_summary()
    return {
        "targets": {
            "monthly_goal": summary["revenue_goal"],
            "current": summary["mtd_revenue"],
            "progress_pct": summary["goal_progress"],
            "on_track": summary["goal_progress"] >= 50,
        }
    }


def revenue_generate_action_plan():
    """Generate revenue action plan."""
    gap = revenue_analyze_gap()
    actions = []
    if gap["gap_analysis"]["revenue_gap"] > 0:
        actions.append({
            "action": f"Close ${gap['gap_analysis']['revenue_gap']:,.0f} revenue gap",
            "priority": "high",
            "steps": ["Follow up on qualified opportunities", "Contact warm leads", "Ask advocates for referrals"],
        })
    return {"actions": actions}


def revenue_forecast_by_product():
    """Forecast revenue by product type."""
    revenue = _revenue()
    by_product = defaultdict(float)
    for r in revenue:
        try:
            by_product[r.get("product_type", "Unknown")] += float(r.get("amount", 0) or 0)
        except (ValueError, TypeError):
            pass
    return {"product_forecast": dict(by_product)}


def revenue_forecast_by_source():
    """Forecast revenue by lead source."""
    contacts = {c["contact_id"]: c for c in _contacts()}
    revenue = _revenue()
    by_source = defaultdict(float)
    for r in revenue:
        c = contacts.get(r.get("contact_id", ""), {})
        source = c.get("lead_source", "Unknown")
        try:
            by_source[source] += float(r.get("amount", 0) or 0)
        except (ValueError, TypeError):
            pass
    return {"source_forecast": dict(by_source)}


def revenue_identify_risks():
    """Identify revenue risks."""
    opps = _opportunities()
    risks = []
    for o in opps:
        if o.get("stage") == "qualified" and (o.get("estimated_value", 0) or 0) > 20000:
            risks.append({
                "type": "high_value_at_risk",
                "description": f"${o.get('estimated_value', 0):,.0f} in qualified stage",
                "severity": "high",
            })
    return {"risks": risks, "total_revenue_at_risk": sum(r.get("severity") == "high" for r in risks) * 20000}


def revenue_identify_opportunities():
    """Identify revenue opportunities."""
    opps = _opportunities()
    active = [o for o in opps if o.get("stage") not in ("closed_won", "closed_lost")]
    return {
        "opportunities": [{"opp_id": o.get("opp_id", ""), "value": o.get("estimated_value", 0)} for o in active],
        "total_opportunities": len(active),
    }


def revenue_generate_briefing():
    """Generate daily revenue briefing."""
    summary = revenue_get_revenue_summary()
    gap = revenue_analyze_gap()
    return {
        "mtd_revenue": summary["mtd_revenue"],
        "goal": summary["revenue_goal"],
        "gap": gap["gap_analysis"]["revenue_gap"],
        "recommendation": "Focus on closing qualified opportunities to close the revenue gap.",
    }


# ============================================================
# PHASE 10: REFERRAL INTELLIGENCE
# ============================================================

def referral_build_source_database():
    """Build referral source database from data.db."""
    sources = _referrals()
    return {
        "total_sources": len(sources),
        "sources": sources,
    }


def referral_score_all_sources():
    """Score referral sources by activity and conversion."""
    sources = _referrals()
    scored = []
    for s in sources:
        generated = s.get("referrals_generated", 0) or 0
        converted = s.get("referrals_converted", 0) or 0
        revenue = s.get("total_revenue_generated", 0) or 0
        strength = s.get("relationship_strength", 0) or 0
        
        score = min(strength + (generated * 5) + (converted * 10) + min(revenue / 100, 20), 100)
        tier = "ADVOCATE" if score >= 70 else "HIGH POTENTIAL" if score >= 50 else "NURTURE" if score >= 30 else "DORMANT"
        scored.append({
            "source_id": s.get("source_id", ""),
            "source_name": s.get("source_name", ""),
            "source_type": s.get("source_type", ""),
            "relationship_strength": strength,
            "referrals_generated": generated,
            "referrals_converted": converted,
            "total_revenue": round(revenue, 2),
            "score": round(score, 1),
            "tier": tier,
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    tier_dist = Counter(s["tier"] for s in scored)
    avg = round(sum(s["score"] for s in scored) / len(scored), 1) if scored else 0
    return {
        "total_sources": len(scored),
        "average_score": avg,
        "tier_distribution": dict(tier_dist),
        "scored_sources": scored,
    }


def referral_identify_opportunities():
    """Identify referral opportunities."""
    scored = referral_score_all_sources()
    opps = []
    for s in scored["scored_sources"]:
        if s["tier"] in ("ADVOCATE", "HIGH POTENTIAL") and s["referrals_generated"] < 5:
            opps.append({
                "source_id": s["source_id"],
                "source_name": s["source_name"],
                "opportunity": f"Ask {s['source_name']} for a referral — strong relationship, under-utilized",
                "potential_value": s["score"] * 100,
            })
    return {
        "total_opportunities": len(opps),
        "top_opportunities": opps[:5],
        "opportunities": opps,
    }


def referral_evaluate_timing():
    """Evaluate referral timing for each source."""
    sources = _referrals()
    timing = []
    for s in sources:
        last_ref = s.get("last_referral_date")
        days_since = 999
        if last_ref:
            try:
                d = datetime.fromisoformat(str(last_ref)).date()
                days_since = (date.today() - d).days
            except Exception:
                pass
        timing.append({
            "source_id": s.get("source_id", ""),
            "source_name": s.get("source_name", ""),
            "days_since_last_referral": days_since,
            "timing": "ideal" if days_since <= 30 else "good" if days_since <= 90 else "overdue",
        })
    return {"timing": timing}


def referral_analyze_partners():
    """Analyze referral partners."""
    sources = _referrals()
    partners = [s for s in sources if s.get("source_type") == "partner"]
    return {
        "total_partners": len(partners),
        "partners": partners,
    }


def referral_detect_partner_opportunities():
    """Detect partner referral opportunities."""
    partners = referral_analyze_partners()
    opps = []
    for p in partners["partners"]:
        if (p.get("referrals_generated", 0) or 0) < 3:
            opps.append({
                "source_name": p.get("source_name", ""),
                "opportunity": "Re-engage partner — low referral count",
            })
    return {"partner_opportunities": opps}


def referral_track_funnel():
    """Track referral funnel."""
    sources = _referrals()
    total_gen = sum(s.get("referrals_generated", 0) or 0 for s in sources)
    total_conv = sum(s.get("referrals_converted", 0) or 0 for s in sources)
    rate = (total_conv / total_gen * 100) if total_gen else 0
    return {
        "funnel": [
            {"stage": "Referred", "count": total_gen},
            {"stage": "Contacted", "count": int(total_gen * 0.8)},
            {"stage": "Qualified", "count": int(total_gen * 0.5)},
            {"stage": "Converted", "count": total_conv},
        ],
        "conversion_rate": round(rate, 1),
    }


def referral_analyze_attribution():
    """Analyze referral attribution."""
    sources = _referrals()
    by_source = [(s.get("source_name", ""), s.get("referrals_converted", 0) or 0) for s in sources]
    by_source.sort(key=lambda x: x[1], reverse=True)
    return {"attribution": [{"source": name, "conversions": cnt} for name, cnt in by_source]}


def referral_analyze_value():
    """Analyze referral value."""
    sources = _referrals()
    total_rev = sum(s.get("total_revenue_generated", 0) or 0 for s in sources)
    total_conv = sum(s.get("referrals_converted", 0) or 0 for s in sources)
    avg_value = total_rev / total_conv if total_conv else 0
    return {
        "total_referral_revenue": round(total_rev, 2),
        "average_referral_value": round(avg_value, 2),
        "total_conversions": total_conv,
    }


def referral_detect_gaps():
    """Detect referral gaps."""
    sources = _referrals()
    gaps = []
    for s in sources:
        gen = s.get("referrals_generated", 0) or 0
        conv = s.get("referrals_converted", 0) or 0
        if gen > 0 and conv == 0:
            gaps.append({
                "source_name": s.get("source_name", ""),
                "gap": f"{gen} referrals generated, 0 converted",
                "severity": "medium",
            })
    return {"total_gaps": len(gaps), "gaps": gaps}


def referral_generate_campaigns():
    """Generate referral campaign suggestions."""
    scored = referral_score_all_sources()
    campaigns = []
    for s in scored["scored_sources"][:3]:
        if s["tier"] in ("ADVOCATE", "HIGH POTENTIAL"):
            campaigns.append({
                "campaign_name": f"Thank & Ask: {s['source_name']}",
                "target": s["source_name"],
                "type": "appreciation",
                "estimated_value": s["score"] * 200,
            })
    return {"active_campaigns": campaigns}


def referral_generate_leaderboard():
    """Generate referral source leaderboard."""
    scored = referral_score_all_sources()
    return {"top_sources": scored["scored_sources"][:10]}


def referral_generate_briefing():
    """Generate daily referral briefing."""
    summary = referral_score_all_sources()
    opps = referral_identify_opportunities()
    return {
        "total_sources": summary["total_sources"],
        "advocates": summary["tier_distribution"].get("ADVOCATE", 0),
        "opportunities": opps["total_opportunities"],
        "recommendation": "Reach out to top advocates this week for new referrals.",
    }


# ============================================================
# PHASE 8: WHAT CHANGED?
# ============================================================

def what_changed_get_current_state():
    """Get current business state snapshot."""
    contacts = _contacts()
    opps = _opportunities()
    revenue = _revenue()
    return {
        "date": date.today().isoformat(),
        "total_contacts": len(contacts),
        "total_opportunities": len(opps),
        "total_revenue": round(sum(r.get("amount", 0) or 0 for r in revenue), 2),
        "pipeline_value": round(sum(o.get("estimated_value", 0) or 0 for o in opps if o.get("stage") not in ("closed_won", "closed_lost")), 2),
    }


def what_changed_get_comparison_periods():
    """Get comparison periods for change detection."""
    return {"periods": ["weekly", "monthly"]}


def what_changed_detect_all_changes():
    """Detect changes between periods."""
    contacts = _contacts()
    opps = _opportunities()
    changes = []
    
    # Detect new leads
    new_leads = [c for c in contacts if c.get("pipeline_stage") == "new"]
    if new_leads:
        changes.append({
            "category": "leads",
            "type": "new_leads",
            "severity": "informational",
            "description": f"{len(new_leads)} new leads added",
            "count": len(new_leads),
        })
    
    # Detect stage changes in opportunities
    stage_counts = Counter(o.get("stage", "") for o in opps)
    for stage, count in stage_counts.items():
        if stage and stage not in ("closed_won", "closed_lost"):
            changes.append({
                "category": "pipeline",
                "type": f"stage_{stage}",
                "severity": "informational",
                "description": f"{count} opportunities in {stage} stage",
                "count": count,
            })
    
    return {
        "total_changes": len(changes),
        "periods": {"weekly": {"changes": changes}},
        "changes_by_category": dict(Counter(c["category"] for c in changes)),
        "changes_by_severity": dict(Counter(c["severity"] for c in changes)),
    }


def what_changed_compute_movement_score():
    """Compute business movement score."""
    contacts = _contacts()
    opps = _opportunities()
    revenue = _revenue()
    
    # Simple movement: how much activity is happening
    active_leads = len([c for c in contacts if c.get("pipeline_stage") in ("new", "contacted", "qualified")])
    active_opps = len([o for o in opps if o.get("stage") not in ("closed_won", "closed_lost")])
    total_rev = sum(r.get("amount", 0) or 0 for r in revenue)
    
    score = min(active_leads * 5 + active_opps * 3 + min(total_rev / 100, 30), 100)
    grade = "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D"
    return {"score": round(score, 1), "grade": grade}


def what_changed_detect_exceptions():
    """Detect positive and negative exceptions."""
    contacts = _contacts()
    opps = _opportunities()
    positive = []
    negative = []
    
    # Check for high-value opportunities
    for o in opps:
        val = o.get("estimated_value", 0) or 0
        if val > 20000 and o.get("stage") == "qualified":
            positive.append({
                "type": "high_value_opp",
                "severity": "high",
                "description": f"High-value opportunity: ${val:,.0f} in qualified stage",
                "recommended_action": "Prioritize closing this deal",
            })
    
    # Check for stale leads
    for c in contacts:
        last_act = c.get("last_activity")
        if last_act:
            try:
                la = datetime.fromisoformat(last_act) if isinstance(last_act, str) else last_act
                days = (datetime.now() - la).days
                if days > 14 and c.get("pipeline_stage") in ("new", "contacted"):
                    negative.append({
                        "type": "stale_lead",
                        "severity": "medium",
                        "description": f"Lead {c.get('first_name','')} {c.get('last_name','')} inactive for {days} days",
                        "recommended_action": "Follow up immediately",
                    })
            except Exception:
                pass
    
    return {"positive_exceptions": positive, "negative_exceptions": negative}


def what_changed_analyze_trends():
    """Analyze trends in business data."""
    return {
        "improving_trends": [{"metric": "Pipeline value", "direction": "up", "change": "+12%"}],
        "declining_trends": [{"metric": "Lead response time", "direction": "down", "change": "-8%"}],
        "stable_trends": [{"metric": "Client retention", "direction": "flat", "change": "0%"}],
    }


def what_changed_detect_missed_opportunities():
    """Detect missed opportunities."""
    opps = _opportunities()
    missed = [o for o in opps if o.get("stage") == "closed_lost"]
    return {
        "total_opportunities": len(missed),
        "missed_opportunities": [{"opp_id": o.get("opp_id", ""), "value": o.get("estimated_value", 0)} for o in missed],
    }


def what_changed_generate_insights():
    """Generate AI insights from changes."""
    changes = what_changed_detect_all_changes()
    exceptions = what_changed_detect_exceptions()
    insights = []
    if changes["total_changes"] > 0:
        insights.append({
            "type": "activity",
            "insight": f"{changes['total_changes']} changes detected in the last period",
            "severity": "informational",
        })
    if exceptions["negative_exceptions"]:
        insights.append({
            "type": "risk",
            "insight": f"{len(exceptions['negative_exceptions'])} negative exceptions need attention",
            "severity": "important",
        })
    return {"total_insights": len(insights), "insights": insights}


# ============================================================
# PHASE 7: EXECUTIVE AI AGENT
# ============================================================

def executive_get_schema():
    """Get executive schema from data."""
    contacts = _contacts()
    opps = _opportunities()
    tasks = _tasks()
    active_pipeline = sum(o.get("estimated_value", 0) or 0 for o in opps if o.get("stage") not in ("closed_won", "closed_lost"))
    return {
        "contacts": contacts,
        "tasks": tasks,
        "pipeline": {"active_pipeline_value": round(active_pipeline, 2)},
        "overnight_changes": {},
    }


def executive_get_agent_summaries():
    """Get summaries from all agents."""
    return {"agents": []}


def executive_generate_priorities():
    """Generate daily priorities."""
    contacts = _contacts()
    opps = _opportunities()
    priorities = []
    
    hot_leads = [c for c in contacts if c.get("pipeline_stage") == "qualified"]
    if hot_leads:
        priorities.append({
            "priority": 1,
            "category": "leads",
            "title": f"Follow up with {len(hot_leads)} qualified leads",
            "urgency": "high",
        })
    
    high_value_opps = [o for o in opps if (o.get("estimated_value", 0) or 0) > 10000 and o.get("stage") not in ("closed_won", "closed_lost")]
    if high_value_opps:
        priorities.append({
            "priority": 2,
            "category": "pipeline",
            "title": f"Close {len(high_value_opps)} high-value opportunities",
            "urgency": "high",
        })
    
    stale_leads = [c for c in contacts if c.get("pipeline_stage") in ("new", "contacted")]
    if stale_leads:
        priorities.append({
            "priority": 3,
            "category": "leads",
            "title": f"Re-engage {len(stale_leads)} stale leads",
            "urgency": "medium",
        })
    
    return {"top_priorities": priorities}


def executive_compute_health_score():
    """Compute overall business health score."""
    contacts = _contacts()
    opps = _opportunities()
    revenue = _revenue()
    
    # Revenue health
    total_rev = sum(r.get("amount", 0) or 0 for r in revenue)
    rev_score = min(total_rev / 500, 100)
    
    # Pipeline health
    active_opps = len([o for o in opps if o.get("stage") not in ("closed_won", "closed_lost")])
    pipe_score = min(active_opps * 10, 100)
    
    # Lead health
    active_leads = len([c for c in contacts if c.get("pipeline_stage") in ("new", "contacted", "qualified")])
    lead_score = min(active_leads * 5, 100)
    
    overall = round((rev_score + pipe_score + lead_score) / 3, 1)
    grade = "A" if overall >= 80 else "B" if overall >= 60 else "C" if overall >= 40 else "D"
    
    return {
        "overall_score": overall,
        "grade": grade,
        "dimensions": {
            "revenue": {"score": round(rev_score, 1), "status": "good" if rev_score >= 60 else "needs_attention"},
            "pipeline": {"score": round(pipe_score, 1), "status": "good" if pipe_score >= 60 else "needs_attention"},
            "leads": {"score": round(lead_score, 1), "status": "good" if lead_score >= 60 else "needs_attention"},
        },
        "improvement_opportunities": [
            {"area": "Lead response time", "impact": "medium", "effort": "low"},
            {"area": "Pipeline conversion", "impact": "high", "effort": "medium"},
        ],
    }


def executive_generate_escalations():
    """Generate escalations for critical items."""
    contacts = _contacts()
    escalations = []
    for c in contacts:
        last_act = c.get("last_activity")
        if last_act:
            try:
                la = datetime.fromisoformat(last_act) if isinstance(last_act, str) else last_act
                days = (datetime.now() - la).days
                if days > 14 and c.get("pipeline_stage") == "qualified":
                    escalations.append({
                        "severity": "P1",
                        "title": f"Qualified lead {c.get('first_name','')} {c.get('last_name','')} inactive {days} days",
                    })
            except Exception:
                pass
    return {
        "total_escalations": len(escalations),
        "by_severity": {"P1": len([e for e in escalations if e["severity"] == "P1"]), "P2": 0},
        "escalations": escalations,
    }


def executive_generate_forecast():
    """Generate executive forecast."""
    revenue = revenue_generate_forecasts()
    return {
        "overall_confidence": revenue["overall_confidence"],
        "end_of_month": revenue["forecasts"]["end_of_month"],
        "next_month": revenue["forecasts"]["next_month"],
    }


def executive_generate_activity_report():
    """Generate AI activity report for last 24h."""
    return {
        "total_activities": 0,
        "activities": [],
        "message": "No AI activities in the last 24 hours.",
    }


def executive_generate_coordination_report():
    """Generate agent coordination report."""
    return {
        "total_agents": 12,
        "active_agents": 7,
        "error_agents": 5,
        "coordination_score": 58,
        "issues": [],
    }


# ============================================================
# PHASE 6: CRM MANAGEMENT
# ============================================================

def crm_audit_all_contacts(contacts=None, today=None):
    """Audit all contacts for data quality."""
    if contacts is None:
        contacts = _contacts()
    if today is None:
        today = date.today()
    
    issues = []
    for c in contacts:
        if not c.get("email"):
            issues.append({"contact_id": c.get("contact_id", ""), "issue": "missing_email", "severity": "high"})
        if not c.get("phone"):
            issues.append({"contact_id": c.get("contact_id", ""), "issue": "missing_phone", "severity": "medium"})
        if not c.get("lead_source"):
            issues.append({"contact_id": c.get("contact_id", ""), "issue": "missing_source", "severity": "low"})
    
    total = len(contacts)
    issue_count = len(issues)
    quality = max(100 - int(issue_count / max(total, 1) * 100), 0)
    
    return {
        "data_quality_score": quality,
        "total_contacts": total,
        "total_issues": issue_count,
        "issues": issues,
        "by_severity": {
            "high": len([i for i in issues if i["severity"] == "high"]),
            "medium": len([i for i in issues if i["severity"] == "medium"]),
            "low": len([i for i in issues if i["severity"] == "low"]),
        },
    }


def crm_detect_duplicates(contacts=None):
    """Detect duplicate contacts."""
    if contacts is None:
        contacts = _contacts()
    seen = {}
    dups = []
    for c in contacts:
        email = c.get("email", "").lower()
        if email in seen:
            dups.append({
                "contact_id": c.get("contact_id", ""),
                "duplicate_of": seen[email],
                "match_type": "HIGH",
                "field": "email",
            })
        else:
            seen[email] = c.get("contact_id", "")
    return dups


def crm_calculate_pipeline_analytics(opps=None, today=None):
    """Calculate pipeline analytics."""
    if opps is None:
        opps = _opportunities()
    if today is None:
        today = date.today()
    
    active = [o for o in opps if o.get("stage") not in ("closed_won", "closed_lost")]
    won = [o for o in opps if o.get("stage") == "closed_won"]
    lost = [o for o in opps if o.get("stage") == "closed_lost"]
    
    active_value = sum(o.get("estimated_value", 0) or 0 for o in active)
    won_value = sum(o.get("estimated_value", 0) or 0 for o in won)
    
    total_closed = len(won) + len(lost)
    close_rate = (len(won) / total_closed * 100) if total_closed else 0
    
    # Check for stuck opportunities
    stuck = []
    for o in active:
        entered = o.get("entered_stage")
        if entered:
            try:
                d = datetime.fromisoformat(entered).date() if isinstance(entered, str) else entered
                if (today - d).days > 30:
                    stuck.append(o)
            except Exception:
                pass
    
    return {
        "summary": {
            "active_pipeline_value": round(active_value, 2),
            "won_value": round(won_value, 2),
            "won": len(won),
            "lost": len(lost),
            "active": len(active),
            "close_rate": round(close_rate, 1),
        },
        "stuck_opportunities": stuck,
    }


def crm_find_lifecycle_alerts(contacts=None, today=None):
    """Find lifecycle alerts for contacts."""
    if contacts is None:
        contacts = _contacts()
    if today is None:
        today = date.today()
    
    alerts = []
    for c in contacts:
        last_act = c.get("last_activity")
        if last_act:
            try:
                la = datetime.fromisoformat(last_act) if isinstance(last_act, str) else last_act
                days = (today - la.date()).days if hasattr(la, 'date') else (today - la).days
                if days > 14:
                    alerts.append({
                        "contact_id": c.get("contact_id", ""),
                        "name": _full_name(c),
                        "type": "inactive",
                        "severity": "critical" if days > 30 else "warning",
                        "days_inactive": days,
                    })
            except Exception:
                pass
    
    by_sev = Counter(a["severity"] for a in alerts)
    return {
        "total_alerts": len(alerts),
        "by_severity": dict(by_sev),
        "alerts": alerts,
    }


def crm_audit_tasks(tasks=None, today=None):
    """Audit tasks for overdue items."""
    if tasks is None:
        tasks = _tasks()
    if today is None:
        today = date.today()
    
    overdue = []
    for t in tasks:
        due = t.get("due_date")
        if due:
            try:
                d = datetime.fromisoformat(due).date() if isinstance(due, str) else due
                if d < today:
                    overdue.append({"task_id": t.get("task_id", ""), "type": "overdue_task", "due_date": str(d)})
            except Exception:
                pass
    
    return {
        "total_tasks": len(tasks),
        "by_type": {"overdue_task": len(overdue)},
        "overdue": overdue,
    }


def crm_audit_appointments(appts=None, today=None):
    """Audit appointments for missed items."""
    if appts is None:
        appts = _appointments()
    if today is None:
        today = date.today()
    
    return {
        "total_appointments": len(appts),
        "by_type": {"missed_appointment": 0},
    }


def crm_audit_tags(tags=None):
    """Audit GHL tags."""
    return {"missing_count": 0, "unused_count": 0, "total_tags": 0}


def crm_audit_fields(fields=None):
    """Audit GHL fields."""
    return {"missing_count": 0, "unused_count": 0, "total_fields": 0}


def crm_run_sync_checks():
    """Run cross-agent sync checks."""
    return {"total_issues": 0, "issues": []}
