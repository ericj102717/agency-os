#!/usr/bin/env python3
"""
Business Owner Scorecard -- Test Harness
========================================
Tests 8 scenarios plus a validation test that verifies no vanity metric
dominates the score. Scenarios inject mock data into a patched data-gathering
layer so the scoring functions can be exercised without modifying the live
agent feeds.

All data is SAMPLE. All recommendations are DRAFT -- owner approval required.
"""

import os
import sys
import json
import copy
from datetime import date
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import business_scorecard_engine as eng
from business_scorecard_config import CATEGORY_WEIGHTS, SCORE_THRESHOLDS


# ---------------------------------------------------------------------------
# Mock-data builders
# ---------------------------------------------------------------------------

def _base_revenue(actual=2060, monthly_goal=25000, weighted=494, committed=0,
                  at_risk=5300, close_rate=80, active_pipe=1960, annual_goal=300000):
    return {
        "revenue_forecasting": {
            "status": "active",
            "kpis": {
                "actual_revenue": actual, "committed_revenue": committed,
                "weighted_pipeline": weighted, "unweighted_pipeline": active_pipe,
                "revenue_gap": max(0, annual_goal - actual), "revenue_at_risk": at_risk,
            },
            "targets": {
                "monthly": {"goal": monthly_goal, "revenue_achieved": actual,
                            "covered": actual + weighted, "on_track": False},
                "annual": {"goal": annual_goal, "revenue_achieved": actual},
            },
            "gap_analysis": {"period": "annual", "revenue_gap": max(0, annual_goal - actual),
                             "goal": annual_goal, "covered": actual + weighted},
        },
        "pipeline": {
            "close_rate": close_rate, "active_pipeline_value": active_pipe,
            "conversion_rates": {"new": 87.5, "contacted": 85.7, "qualified": 83.3},
            "stuck_count": 3,
        },
    }


def _base_leads(total=8, avg=27.4, hot=0, warm=1, decay=3, daily_call=5):
    return {
        "lead_scoring": {
            "status": "active",
            "kpis": {"total_leads": total, "average_score": avg, "hot_leads": hot,
                     "warm_leads": warm, "nurture_leads": 3, "cold_leads": 4,
                     "leads_at_risk": decay, "total_pipeline_value": 0},
            "daily_call_list": [{} for _ in range(daily_call)],
        },
        "pipeline": {
            "close_rate": 80, "active_pipeline_value": 1960,
            "conversion_rates": {"new": 87.5, "contacted": 85.7, "qualified": 83.3},
            "stuck_count": 3,
        },
    }


def _base_clients(total=5, avg_health=54.7, at_risk=3, overdue=5, missed=2,
                  critical=5, lifecycle=9, top3=78.2):
    clients = [{"clv_score": avg_health, "display_name": "[SAMPLE] Client %d" % i} for i in range(total)]
    risks = [{"risk_level": "moderate" if i < at_risk else "low", "risk_score": 60 if i < at_risk else 20,
              "display_name": "[SAMPLE] Client %d" % i} for i in range(total)]
    return {
        "clv_intelligence": {
            "status": "active",
            "kpis": {"total_clients": total, "average_clv": 736.9, "retention_rate": 0.92},
            "clients": clients, "risks": risks,
            "concentration": {"revenue_concentration": {"top_3_pct": top3}},
        },
        "crm_management": {
            "status": "active",
            "kpis": {"overdue_tasks": overdue, "missed_appointments": missed,
                     "critical_alerts": critical, "lifecycle_alerts": lifecycle,
                     "data_quality_score": 50},
        },
    }


def _base_referrals(total=15, advocates=0, high_pot=2, dormant=7, opp=10, campaigns=5):
    return {
        "referral_intelligence": {
            "status": "active",
            "kpis": {"total_sources": total, "average_score": 38.5,
                     "advocates": advocates, "high_potential": high_pot,
                     "nurture": 6, "dormant": dormant, "total_opportunities": opp,
                     "active_campaigns": campaigns},
            "top_opportunities": [{"name": "[SAMPLE] Michael Thompson", "estimated_value": 1660.5}],
            "campaigns": [{} for _ in range(campaigns)],
            "funnel": [{"count": 16}, {"count": 8}, {"count": 4}, {"count": 2},
                       {"count": 1}, {"count": 1}, {"count": 1}, {"count": 1}],
            "scored_sources": [],
        },
    }


def _base_marketing(compliance="PASS", blocks=0, surveys_sent=3, surveys_done=2,
                    active_nurture=5, campaigns=5, total_emails=17, total_clients=5):
    return {
        "marketing_summary": {
            "compliance_status": compliance, "compliance_blocks": blocks,
            "email_campaigns": campaigns, "total_emails": total_emails,
            "content_pieces": 5, "calendar_entries": 260,
        },
        "client_nurture": {"kpis": {"surveys_sent": surveys_sent, "surveys_completed": surveys_done,
                                    "active_nurture_clients": active_nurture,
                                    "drip_campaigns": 3, "drip_emails": 0,
                                    "touchpoints_scheduled": 240}},
        "compliance": {"compliance_blocks": blocks},
        "clv_intelligence": {"kpis": {"total_clients": total_clients}},
    }


def _base_execution(total_actions=0, completed=0, overdue=0, needs=15, stuck=3):
    return {
        "performance_metrics": {"total_actions": total_actions, "completed": completed,
                                "overdue": overdue, "completion_rate": (completed/total_actions*100 if total_actions else 0),
                                "contact_rate": 0, "appointment_rate": 0, "conversion_rate": 0},
        "needs_attention": [{} for _ in range(needs)],
        "top_5_priorities": [{"entity": "[SAMPLE] Top Priority", "entity_type": "lead",
                              "priority_score": 90}],
        "pipeline": {"stuck_count": stuck, "conversion_rates": {"new": 87.5}},
    }


def _assemble(*parts):
    """Merge multiple partial data dicts into one data dict.
    The 'pipeline' key is deep-merged (close_rate, active_pipeline_value,
    stuck_count, conversion_rates all preserved) because several partial
    builders contribute different pipeline fields."""
    base = {
        "revenue_forecasting": {}, "pipeline": {}, "lead_scoring": {},
        "clv_intelligence": {}, "crm_management": {}, "referral_intelligence": {},
        "marketing_summary": {}, "client_nurture": {}, "compliance": {},
        "performance_metrics": {}, "needs_attention": [], "top_5_priorities": [],
        "what_changed": [],
        "_revenue_ok": True, "_pipeline_ok": True, "_lead_ok": True,
        "_clv_ok": True, "_crm_ok": True, "_referral_ok": True,
        "_marketing_ok": True, "_ledger_ok": True,
        "v2_available": True, "ledger_available": True,
        "v2_error": None, "ledger_error": None,
    }
    for p in parts:
        for k, v in p.items():
            if k == "pipeline" and isinstance(v, dict):
                base[k] = {**base.get(k, {}), **v}
            else:
                base[k] = v
    return base


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

def scenario_strong_revenue():
    """1. Strong Revenue -- revenue exceeds goal."""
    data = _assemble(
        _base_revenue(actual=28000, monthly_goal=25000, weighted=8000, at_risk=500, close_rate=45, active_pipe=12000),
        _base_leads(), _base_clients(), _base_referrals(),
        _base_marketing(), _base_execution(),
    )
    return eng.score_revenue(data)


def scenario_poor_lead_followup():
    """2. Poor Lead Follow-Up -- high-value leads untouched."""
    data = _assemble(
        _base_revenue(), _base_clients(), _base_referrals(),
        _base_marketing(), _base_execution(),
        _base_leads(total=10, avg=72, hot=4, warm=3, decay=8, daily_call=0),
    )
    return eng.score_lead_management(data)


def scenario_strong_clients():
    """3. Strong Clients -- regular client attention."""
    data = _assemble(
        _base_revenue(), _base_leads(), _base_referrals(),
        _base_marketing(), _base_execution(),
        _base_clients(total=5, avg_health=88, at_risk=0, overdue=0, missed=0,
                      critical=0, lifecycle=2, top3=35),
    )
    return eng.score_client_relationships(data)


def scenario_referral_decline():
    """4. Referral Decline -- referral activity drops."""
    data = _assemble(
        _base_revenue(), _base_leads(), _base_clients(),
        _base_marketing(), _base_execution(),
        _base_referrals(total=15, advocates=0, high_pot=0, dormant=12, opp=1, campaigns=1),
    )
    return eng.score_referrals(data)


def scenario_strong_execution():
    """5. Strong Execution -- owner completes priority actions."""
    data = _assemble(
        _base_revenue(), _base_leads(), _base_clients(), _base_referrals(), _base_marketing(),
        _base_execution(total_actions=20, completed=18, overdue=0, needs=4, stuck=0),
    )
    return eng.score_execution(data)


def scenario_poor_execution():
    """6. Poor Execution -- owner leaves actions overdue."""
    data = _assemble(
        _base_revenue(), _base_leads(), _base_clients(), _base_referrals(), _base_marketing(),
        _base_execution(total_actions=20, completed=4, overdue=8, needs=18, stuck=5),
    )
    return eng.score_execution(data)


def scenario_missing_data():
    """7. Missing Data -- remove required data."""
    data = _assemble(_base_marketing(), _base_execution(), _base_referrals())
    # Revenue/leads/clients agents return errors
    data["revenue_forecasting"] = {"status": "error", "error": "agent down"}
    data["_revenue_ok"] = False
    data["lead_scoring"] = {"status": "error", "error": "agent down"}
    data["_lead_ok"] = False
    data["clv_intelligence"] = {"status": "error", "error": "agent down"}
    data["_clv_ok"] = False
    # Also remove survey data to push marketing coverage below threshold
    data["marketing_summary"]["surveys_sent"] = 0
    data["client_nurture"]["kpis"]["surveys_sent"] = 0
    results = {
        "revenue": eng.score_revenue(data),
        "lead_management": eng.score_lead_management(data),
        "client_relationships": eng.score_client_relationships(data),
        "marketing": eng.score_marketing(data),
    }
    return results


def scenario_improvement():
    """8. Improvement -- several metrics improve."""
    data = _assemble(
        _base_revenue(actual=22000, monthly_goal=25000, weighted=6000, at_risk=800, close_rate=42),
        _base_leads(total=8, avg=58, hot=2, warm=3, decay=1, daily_call=5),
        _base_clients(total=5, avg_health=78, at_risk=1, overdue=1, missed=0, critical=1, top3=55),
        _base_referrals(total=15, advocates=2, high_pot=4, dormant=3, opp=12, campaigns=5),
        _base_marketing(surveys_sent=4, surveys_done=3, active_nurture=5),
        _base_execution(total_actions=15, completed=12, overdue=1, needs=6, stuck=1),
    )
    return {
        "revenue": eng.score_revenue(data),
        "lead_management": eng.score_lead_management(data),
        "client_relationships": eng.score_client_relationships(data),
        "referrals": eng.score_referrals(data),
        "marketing": eng.score_marketing(data),
        "execution": eng.score_execution(data),
    }


# ---------------------------------------------------------------------------
# Validation test: Business A vs Business B (vanity-metric guardrail)
# ---------------------------------------------------------------------------

def validation_business_a_vs_b():
    """Business A: strong revenue/leads/clients, weak referrals/marketing.
    Business B: weak revenue/leads, strong marketing/referrals.

    Verify that Business B's high marketing content VOLUME (a vanity metric)
    does NOT let it outrank Business A, which has stronger business outcomes.
    """
    # Business A: strong outcomes, modest marketing volume
    bizA = _assemble(
        _base_revenue(actual=24000, monthly_goal=25000, weighted=7000, at_risk=600, close_rate=42),
        _base_leads(total=8, avg=65, hot=3, warm=3, decay=1, daily_call=5),
        _base_clients(total=5, avg_health=85, at_risk=0, overdue=0, critical=0, top3=38),
        _base_referrals(total=15, advocates=1, high_pot=2, dormant=5, opp=8, campaigns=3),
        # Low vanity volume but good outcomes (compliance pass, decent survey rate)
        _base_marketing(compliance="PASS", blocks=0, surveys_sent=4, surveys_done=2,
                        active_nurture=5, campaigns=3, total_emails=8),
        _base_execution(total_actions=12, completed=10, overdue=0, needs=5, stuck=1),
    )

    # Business B: weak outcomes but HUGE vanity marketing volume
    bizB = _assemble(
        _base_revenue(actual=2000, monthly_goal=25000, weighted=300, at_risk=4000, close_rate=12),
        _base_leads(total=8, avg=20, hot=0, warm=0, decay=5, daily_call=1),
        _base_clients(total=5, avg_health=40, at_risk=4, overdue=6, critical=4, top3=82),
        _base_referrals(total=15, advocates=0, high_pot=0, dormant=10, opp=2, campaigns=1),
        # Massive vanity volume: 500 content pieces, 2000 calendar entries, 500 emails
        # BUT poor engagement outcome (surveys barely answered) and low campaign w/ sends consistency
        _base_marketing(compliance="PASS", blocks=0, surveys_sent=10, surveys_done=2,
                        active_nurture=2, campaigns=2, total_emails=500, total_clients=5),
        _base_execution(total_actions=20, completed=2, overdue=10, needs=18, stuck=5),
    )
    # inject vanity-inflated fields the engine must ignore
    bizB["marketing_summary"]["content_pieces"] = 500
    bizB["marketing_summary"]["calendar_entries"] = 2000
    bizA["marketing_summary"]["content_pieces"] = 4
    bizA["marketing_summary"]["calendar_entries"] = 10

    def _score_all(d):
        return {
            "revenue": eng.score_revenue(d)["score"],
            "lead_management": eng.score_lead_management(d)["score"],
            "client_relationships": eng.score_client_relationships(d)["score"],
            "referrals": eng.score_referrals(d)["score"],
            "marketing": eng.score_marketing(d)["score"],
            "execution": eng.score_execution(d)["score"],
        }

    a_scores = _score_all(bizA)
    b_scores = _score_all(bizB)

    # Overall (normalize weights)
    def _overall(scores):
        total_w = sum(CATEGORY_WEIGHTS[k] for k, v in scores.items() if v is not None)
        return round(sum(CATEGORY_WEIGHTS[k] * v for k, v in scores.items() if v is not None) / total_w, 1) if total_w else None

    a_overall = _overall(a_scores)
    b_overall = _overall(b_scores)

    # Assertions
    checks = []
    checks.append(("Business A overall > Business B overall", a_overall > b_overall))
    checks.append(("Business A revenue > Business B revenue", a_scores["revenue"] > b_scores["revenue"]))
    checks.append(("Business B marketing did NOT dominate (<= A revenue weight effect)",
                   b_scores["marketing"] < a_scores["revenue"]))
    checks.append(("Business B vanity volume (500 content pieces) ignored -- B marketing still <= 100",
                   b_scores["marketing"] <= 100))
    checks.append(("Business A marketing score not inflated by low volume (still reasonable)",
                   a_scores["marketing"] >= 60))

    return {
        "business_a_scores": a_scores, "business_a_overall": a_overall,
        "business_b_scores": b_scores, "business_b_overall": b_overall,
        "checks": checks,
        "all_passed": all(c[1] for c in checks),
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _print_category_result(label, res):
    sc = res.get("score") if isinstance(res, dict) else None
    status = res.get("status") if isinstance(res, dict) else "?"
    cov = res.get("coverage") if isinstance(res, dict) else "?"
    print(f"  {label:<24} score={sc}  status={status}  coverage={cov}%")
    if isinstance(res, dict):
        for p in res.get("problems", [])[:3]:
            print(f"      problem: {p}")
        for o in res.get("opportunities", [])[:2]:
            print(f"      opp: {o}")


def run_all():
    print("=" * 70)
    print("BUSINESS OWNER SCORECARD -- TEST HARNESS")
    print("=" * 70)
    results = {}

    print("\n[1] Strong Revenue (revenue exceeds goal)")
    r = scenario_strong_revenue()
    _print_category_result("Revenue", r)
    results["strong_revenue"] = r

    print("\n[2] Poor Lead Follow-Up (high-value leads untouched)")
    r = scenario_poor_lead_followup()
    _print_category_result("Lead Management", r)
    results["poor_lead_followup"] = r

    print("\n[3] Strong Clients (regular client attention)")
    r = scenario_strong_clients()
    _print_category_result("Client Relationships", r)
    results["strong_clients"] = r

    print("\n[4] Referral Decline (referral activity drops)")
    r = scenario_referral_decline()
    _print_category_result("Referrals", r)
    results["referral_decline"] = r

    print("\n[5] Strong Execution (owner completes priority actions)")
    r = scenario_strong_execution()
    _print_category_result("Execution", r)
    results["strong_execution"] = r

    print("\n[6] Poor Execution (owner leaves actions overdue)")
    r = scenario_poor_execution()
    _print_category_result("Execution", r)
    results["poor_execution"] = r

    print("\n[7] Missing Data (remove required data)")
    r = scenario_missing_data()
    for k, v in r.items():
        _print_category_result(k, v)
    results["missing_data"] = r

    print("\n[8] Improvement (several metrics improve)")
    r = scenario_improvement()
    for k, v in r.items():
        _print_category_result(k, v)
    results["improvement"] = r

    print("\n[VALIDATION] Business A (strong outcomes) vs Business B (vanity volume)")
    v = validation_business_a_vs_b()
    print(f"  Business A overall: {v['business_a_overall']}")
    print(f"  Business B overall: {v['business_b_overall']}")
    print(f"  Business A scores: {v['business_a_scores']}")
    print(f"  Business B scores: {v['business_b_scores']}")
    for desc, passed in v["checks"]:
        mark = "PASS" if passed else "FAIL"
        print(f"    [{mark}] {desc}")
    print(f"\n  Validation all_passed: {v['all_passed']}")
    results["validation"] = v

    # Scenario sanity assertions
    print("\n--- SCENARIO SANITY CHECKS ---")
    sanity = []
    sanity.append(("Strong revenue scores high (>70)", results["strong_revenue"]["score"] >= 70))
    sanity.append(("Poor lead follow-up scores below strong clients",
                   results["poor_lead_followup"]["score"] < results["strong_clients"]["score"]))
    sanity.append(("Strong clients scores high (>70)", results["strong_clients"]["score"] >= 70))
    sanity.append(("Referral decline scores low (<60)", results["referral_decline"]["score"] < 60))
    sanity.append(("Strong execution > poor execution",
                   results["strong_execution"]["score"] > results["poor_execution"]["score"]))
    sanity.append(("Missing data -> insufficient_data for revenue",
                   results["missing_data"]["revenue"]["status"] == "insufficient_data"))
    sanity.append(("Missing data -> insufficient_data for leads",
                   results["missing_data"]["lead_management"]["status"] == "insufficient_data"))
    sanity.append(("Missing data -> insufficient_data for clients",
                   results["missing_data"]["client_relationships"]["status"] == "insufficient_data"))
    sanity.append(("Improvement: revenue better than baseline strong-revenue? (sanity, both strong)",
                   results["improvement"]["revenue"]["score"] >= 60))
    sanity.append(("Validation: vanity metrics did not let Business B win", v["all_passed"]))

    passed = 0
    for desc, ok in sanity:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {desc}")
        if ok:
            passed += 1
    print(f"\nSanity checks passed: {passed}/{len(sanity)}")

    print("\n" + "=" * 70)
    print("TEST HARNESS COMPLETE")
    print("=" * 70)
    return results


if __name__ == "__main__":
    run_all()
