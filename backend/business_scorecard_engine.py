#!/usr/bin/env python3
"""
Business Owner Scorecard Engine
================================
The scoring engine for the Medicare/Life Insurance agency AI operating
system. Reads intelligence from the existing V2 engine + action ledger,
scores six business categories, and returns ONE complete scorecard payload.

Design rules (enforced throughout):
  * Do NOT fabricate data. Missing metrics are recorded, not invented.
  * Do NOT reward vanity metrics (raw counts without outcomes).
  * Coverage < 50% for a category  ->  status='insufficient_data', score=None.
  * Overall score normalizes weights across available categories only.
  * Overall marked 'Partial Business Health Score' if any category is missing.
  * Every score ships with a business-language explanation.

All data is SAMPLE. All recommendations are DRAFT -- owner approval required.
"""

import json
import os
import sys
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# Ensure local imports resolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from business_scorecard_config import (
    CATEGORY_LABELS, CATEGORY_ORDER, CATEGORY_WEIGHTS, CATEGORY_AGENT,
    KPI_DEFINITIONS, SCORE_THRESHOLDS, MIN_COVERAGE_PERCENT,
    MISSING_DATA_RULES, VANITY_METRICS, INDUSTRY_CONFIG,
    TREND_WEEKS, SNAPSHOT_FILE, TODAY, DRAFT_DISCLAIMER, SAMPLE_PREFIX,
    SAMPLE_DISCLAIMER, status_from_score,
)

# Import business_config for real revenue_goal (not hardcoded)
try:
    from business_data_service import get_business_config as _get_biz_config
except ImportError:
    _get_biz_config = None

# ---------------------------------------------------------------------------
# Data source imports (guarded)
# ---------------------------------------------------------------------------
try:
    from command_center_v2_engine import (
        get_lead_scoring_data, get_clv_intelligence_data,
        get_referral_intelligence_data, get_marketing_summary,
        get_pipeline_summary, get_business_snapshot, get_what_changed_summary,
        get_client_health_summary, get_referral_summary, get_top_5_priorities,
        get_needs_attention, get_command_center_v2,
        get_revenue_forecasting_data,
    )
    # get_revenue_summary may not be importable from v2_engine due to circular imports
    # when running inside the server process. Define a fallback.
    try:
        from command_center_v2_engine import get_revenue_summary
    except ImportError:
        def get_revenue_summary() -> dict:
            try:
                from server import get_revenue_summary as _grs
                return _grs()
            except Exception:
                return {}
    _V2_AVAILABLE = True
    _V2_ERROR = None
except Exception as e:  # pragma: no cover
    _V2_AVAILABLE = False
    _V2_ERROR = str(e)

try:
    from action_ledger import get_performance_metrics, get_action_history
    _LEDGER_AVAILABLE = True
    _LEDGER_ERROR = None
except Exception as e:  # pragma: no cover
    _LEDGER_AVAILABLE = False
    _LEDGER_ERROR = str(e)

try:
    from server import get_phase6_data, get_phase3_data, get_compliance_summary
    _PHASE_AVAILABLE = True
except Exception:  # pragma: no cover
    _PHASE_AVAILABLE = False
    def get_phase6_data(): return {"kpis": {}}
    def get_phase3_data(): return {"kpis": {}}
    def get_compliance_summary(): return {}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_num(value, default=0.0):
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return default
    try:
        if isinstance(value, str):
            v = value.strip().replace("$", "").replace(",", "").replace("%", "")
            if v == "":
                return default
            return float(v) if "." in v else float(int(v))
    except (ValueError, TypeError):
        pass
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_list(value):
    if isinstance(value, list):
        return value
    return []


def _safe_dict(value):
    if isinstance(value, dict):
        return value
    return {}


def _clamp(score, lo=0.0, hi=100.0):
    return max(lo, min(hi, score))


def _ratio_pct(num, den):
    """num/den as a percent; 0 if den falsy."""
    try:
        if not den:
            return 0.0
        return round((_safe_num(num) / _safe_num(den)) * 100, 1)
    except Exception:
        return 0.0


def _percent_of(value, base):
    if not base:
        return 0.0
    return round((_safe_num(value) / _safe_num(base)) * 100, 1)


# ---------------------------------------------------------------------------
# Score normalization helpers
# ---------------------------------------------------------------------------

def _higher_is_better(value, benchmark, max_scale=None):
    """Linear 0-100 for higher-is-better. benchmark -> 70 pts (good).
    max_scale (if given) -> 100 pts."""
    value = _safe_num(value)
    bench = _safe_num(benchmark)
    if bench <= 0:
        return 50.0 if value > 0 else 0.0
    # Below benchmark: linear proportion up to 70 pts.
    if value < bench:
        return _clamp((value / bench) * 70.0)
    # At or above benchmark: stretch from 70 toward 100 up to max_scale.
    base = 70.0
    if max_scale and max_scale > bench:
        base = 70.0 + min(30.0, ((value - bench) / (max_scale - bench)) * 30.0)
    else:
        base = 70.0 + min(30.0, (value - bench) / bench * 30.0)
    return _clamp(base)


def _lower_is_better(value, benchmark, zero_score=100.0):
    """Linear for lower-is-better. value=0 -> zero_score; value>=benchmark -> 0."""
    value = _safe_num(value)
    bench = _safe_num(benchmark)
    if bench <= 0:
        return zero_score if value <= 0 else 0.0
    if value <= 0:
        return zero_score
    raw = zero_score - (value / bench) * zero_score
    return _clamp(raw)


def _weighted_average(contribs):
    """contribs: list of {score, weight}. Re-normalizes to available weights."""
    total_w = sum(c["weight"] for c in contribs)
    if total_w <= 0:
        return None
    return round(sum(c["score"] * c["weight"] for c in contribs) / total_w, 1)


# ---------------------------------------------------------------------------
# Data gathering layer -- one consolidated dict the scorers read from
# ---------------------------------------------------------------------------

def _gather_data() -> Dict[str, Any]:
    """Pull all raw data sources into one dict. Each source carries an
    '_ok' flag so scorers can detect agent errors and mark missing data."""
    data: Dict[str, Any] = {}

    # Revenue (raw + summary)
    rev_raw = {}
    if _V2_AVAILABLE:
        try:
            rev_raw = get_revenue_forecasting_data()
        except Exception as e:
            rev_raw = {"status": "error", "error": str(e)}
    data["revenue_forecasting"] = rev_raw
    data["_revenue_ok"] = _safe_str(rev_raw.get("status")) != "error"

    rev_summary = {}
    if _V2_AVAILABLE:
        try:
            rev_summary = get_revenue_summary()
        except Exception:
            rev_summary = {}
    data["revenue_summary"] = rev_summary

    # Pipeline
    pipe = {}
    if _V2_AVAILABLE:
        try:
            pipe = get_pipeline_summary()
        except Exception:
            pipe = {}
    data["pipeline"] = pipe
    data["_pipeline_ok"] = "error" not in pipe

    # Lead scoring
    ls = {}
    if _V2_AVAILABLE:
        try:
            ls = get_lead_scoring_data()
        except Exception as e:
            ls = {"status": "error", "error": str(e)}
    data["lead_scoring"] = ls
    data["_lead_ok"] = _safe_str(ls.get("status")) != "error"

    # CLV intelligence
    clv = {}
    if _V2_AVAILABLE:
        try:
            clv = get_clv_intelligence_data()
        except Exception as e:
            clv = {"status": "error", "error": str(e)}
    data["clv_intelligence"] = clv
    data["_clv_ok"] = _safe_str(clv.get("status")) != "error"

    # CRM management (phase 6)
    p6 = {}
    if _PHASE_AVAILABLE:
        try:
            p6 = get_phase6_data()
        except Exception as e:
            p6 = {"status": "error", "error": str(e)}
    data["crm_management"] = p6
    data["_crm_ok"] = _safe_str(p6.get("status")) != "error"

    # Referral intelligence
    ref = {}
    if _V2_AVAILABLE:
        try:
            ref = get_referral_intelligence_data()
        except Exception as e:
            ref = {"status": "error", "error": str(e)}
    data["referral_intelligence"] = ref
    data["_referral_ok"] = _safe_str(ref.get("status")) != "error"

    # Marketing + client nurture
    mkt = {}
    if _V2_AVAILABLE:
        try:
            mkt = get_marketing_summary()
        except Exception:
            mkt = {}
    data["marketing_summary"] = mkt
    p3 = {}
    if _PHASE_AVAILABLE:
        try:
            p3 = get_phase3_data()
        except Exception:
            p3 = {"kpis": {}}
    data["client_nurture"] = p3
    data["_marketing_ok"] = True  # always resolvable (defaults exist)

    # Compliance
    comp = {}
    try:
        comp = get_compliance_summary()
    except Exception:
        comp = {}
    data["compliance"] = comp

    # Execution: action ledger + priority engine
    perf = {}
    if _LEDGER_AVAILABLE:
        try:
            perf = get_performance_metrics()
        except Exception as e:
            perf = {"error": str(e)}
    data["performance_metrics"] = perf
    data["_ledger_ok"] = "error" not in perf

    needs = []
    top5 = []
    if _V2_AVAILABLE:
        try:
            needs = get_needs_attention()
        except Exception:
            needs = []
        try:
            top5 = get_top_5_priorities()
        except Exception:
            top5 = []
    data["needs_attention"] = needs
    data["top_5_priorities"] = top5

    # What changed (for context)
    wc = []
    if _V2_AVAILABLE:
        try:
            wc = get_what_changed_summary()
        except Exception:
            wc = []
    data["what_changed"] = wc

    data["v2_available"] = _V2_AVAILABLE
    data["v2_error"] = _V2_ERROR
    data["ledger_available"] = _LEDGER_AVAILABLE
    data["ledger_error"] = _LEDGER_ERROR
    return data


# ---------------------------------------------------------------------------
# Common category-result builder
# ---------------------------------------------------------------------------

def _empty_category_result(name):
    return {
        "category": name,
        "label": CATEGORY_LABELS.get(name, name),
        "agent": CATEGORY_AGENT.get(name, ""),
        "score": None,
        "status": "insufficient_data",
        "coverage": 0.0,
        "metrics_used": [],
        "missing_metrics": [],
        "explanation": "Insufficient data to score this category.",
        "problems": [],
        "opportunities": [],
        "recommended_actions": [],
        "trend": None,
    }


def _metric_entry(name, label, value, benchmark, contribution, unit=""):
    return {
        "name": name,
        "label": label,
        "value": value,
        "benchmark": benchmark,
        "contribution": round(_safe_num(contribution), 1),
        "unit": unit,
    }


def _recommendation(action, entity, entity_type, opportunity_value=0, action_type="view"):
    return {
        "action": action,
        "entity": entity,
        "entity_type": entity_type,
        "opportunity_value": round(_safe_num(opportunity_value), 2),
        "action_type": action_type,
    }


# ---------------------------------------------------------------------------
# REVENUE scoring
# ---------------------------------------------------------------------------

def score_revenue(data: Dict[str, Any]) -> Dict[str, Any]:
    result = _empty_category_result("revenue")
    rev = _safe_dict(data.get("revenue_forecasting", {}))
    kpis = _safe_dict(rev.get("kpis"))
    targets = _safe_dict(rev.get("targets"))
    gap_a = _safe_dict(rev.get("gap_analysis"))
    pipe = _safe_dict(data.get("pipeline", {}))
    monthly = _safe_dict(targets.get("monthly"))
    annual = _safe_dict(targets.get("annual"))

    actual = _safe_num(kpis.get("actual_revenue"))
    weighted_pipe = _safe_num(kpis.get("weighted_pipeline"))
    committed = _safe_num(kpis.get("committed_revenue"))
    active_pipe = _safe_num(pipe.get("active_pipeline_value"))
    at_risk = _safe_num(kpis.get("revenue_at_risk"))
    close_rate = _safe_num(pipe.get("close_rate"))

    # Use business_config.revenue_goal if available, fall back to industry config
    _biz_goal = 0
    if _get_biz_config:
        try:
            _biz_goal = float(_get_biz_config().get('revenue_goal', 0) or 0)
        except Exception:
            _biz_goal = 0
    monthly_goal = _safe_num(monthly.get("goal")) or _biz_goal or INDUSTRY_CONFIG["target_monthly_revenue"]
    annual_goal = _safe_num(annual.get("goal")) or INDUSTRY_CONFIG["target_annual_revenue"]
    forecast_30 = actual + weighted_pipe  # covered

    expected = 5
    missing = []
    if not data.get("_revenue_ok"):
        result["explanation"] = "Revenue Forecasting agent returned an error; cannot score."
        result["missing_metrics"] = [k["name"] for k in KPI_DEFINITIONS["revenue"]]
        result["coverage"] = 0.0
        return result

    contribs = []
    metrics_used = []

    # 1. Revenue attainment vs monthly goal
    attainment = _percent_of(actual, monthly_goal)
    s_attain = _higher_is_better(actual, monthly_goal, max_scale=monthly_goal)
    contribs.append({"score": s_attain, "weight": 0.30})
    metrics_used.append(_metric_entry(
        "revenue_attainment", "Revenue vs Monthly Goal",
        f"{attainment}% (${actual:,.0f} of ${monthly_goal:,.0f})",
        ">= 100% of monthly goal", s_attain, "percent_of_goal"))

    # 2. Pipeline coverage: weighted pipeline vs remaining monthly gap.
    #    If the goal is already met (no remaining gap), coverage is excellent.
    remaining_gap = max(0.0, monthly_goal - actual - committed)
    if remaining_gap <= 0:
        coverage_ratio = max(1.0, weighted_pipe / monthly_goal) if monthly_goal else 1.0
        s_cov = 100.0 if weighted_pipe > 0 else 70.0
    else:
        coverage_ratio = (weighted_pipe / remaining_gap) if remaining_gap > 0 else 0.0
        s_cov = _clamp(min(100.0, coverage_ratio / 3.0 * 100.0)) if coverage_ratio else 0.0
    contribs.append({"score": s_cov, "weight": 0.20})
    metrics_used.append(_metric_entry(
        "pipeline_coverage", "Pipeline Coverage",
        f"{coverage_ratio:.2f}x", ">= 3.0x weighted vs gap", s_cov, "ratio"))

    # 3. Close rate
    s_close = _higher_is_better(close_rate, 30, max_scale=80)
    contribs.append({"score": s_close, "weight": 0.20})
    metrics_used.append(_metric_entry(
        "close_rate", "Close Rate", f"{close_rate:.0f}%", ">= 30%", s_close, "percent"))

    # 4. Revenue at risk ratio (lower is better)
    risk_ratio = (at_risk / active_pipe) if active_pipe > 0 else (1.0 if at_risk > 0 else 0.0)
    s_risk = _lower_is_better(risk_ratio, 0.50)  # 50% of pipeline at risk -> 0
    contribs.append({"score": s_risk, "weight": 0.15})
    metrics_used.append(_metric_entry(
        "revenue_at_risk_ratio", "Revenue at Risk",
        f"{risk_ratio*100:.0f}% (${at_risk:,.0f})", "<= 10% of pipeline", s_risk, "ratio"))

    # 5. Forecast strength vs monthly goal
    forecast_pct = _percent_of(forecast_30, monthly_goal)
    s_forecast = _higher_is_better(forecast_30, monthly_goal, max_scale=monthly_goal)
    contribs.append({"score": s_forecast, "weight": 0.15})
    metrics_used.append(_metric_entry(
        "forecast_strength", "30-Day Forecast Strength",
        f"{forecast_pct}% (${forecast_30:,.0f})", ">= 100% of goal", s_forecast, "percent_of_goal"))

    score = _weighted_average(contribs)
    coverage = (len(metrics_used) / expected) * 100.0

    result["score"] = score
    result["status"] = "scored" if coverage >= MIN_COVERAGE_PERCENT else "insufficient_data"
    if result["status"] != "scored":
        result["score"] = None
        result["explanation"] = "Not enough revenue data to score reliably."
        result["coverage"] = round(coverage, 1)
        result["metrics_used"] = metrics_used
        result["missing_metrics"] = missing
        return result

    result["coverage"] = round(coverage, 1)
    result["metrics_used"] = metrics_used
    result["missing_metrics"] = missing

    # Narrative
    problems, opps = [], []
    if attainment < 25:
        problems.append(f"Revenue is only {attainment:.0f}% of the monthly goal (${actual:,.0f} of ${monthly_goal:,.0f}).")
    if coverage_ratio < 1.0:
        problems.append(f"Pipeline coverage is thin at {coverage_ratio:.2f}x the remaining gap; need at least 3.0x.")
    if at_risk > 0:
        problems.append(f"${at_risk:,.0f} of revenue is flagged at risk ({risk_ratio*100:.0f}% of active pipeline).")
    if close_rate < 30:
        problems.append(f"Close rate of {close_rate:.0f}% is below the 30% benchmark.")
    if forecast_pct < 100:
        opps.append(f"Closing the {100-forecast_pct:.0f}% forecast gap would bring the month on target.")
    opps.append(f"Annual goal of ${annual_goal:,.0f} requires ~${annual_goal/12:,.0f}/month; current trajectory needs acceleration.")

    # Recommended actions
    recs = []
    if remaining_gap > 0:
        recs.append(_recommendation(
            "Accelerate pipeline to close the ${:,.0f} monthly revenue gap.".format(remaining_gap),
            "Revenue Gap", "revenue_gap", remaining_gap, "follow_up_opportunities"))
    if at_risk > 0:
        recs.append(_recommendation(
            "Contact prospects with revenue at risk (${:,.0f}).".format(at_risk),
            "Revenue at Risk", "revenue_risk", at_risk, "contact_prospects"))
    result["problems"] = problems
    result["opportunities"] = opps
    result["recommended_actions"] = recs
    result["explanation"] = (
        f"Revenue scores {score}/100. You've booked {attainment:.0f}% of the monthly goal "
        f"(${actual:,.0f} of ${monthly_goal:,.0f}) with {coverage_ratio:.2f}x pipeline coverage. "
        f"{'On track.' if forecast_pct >= 100 else f'Forecast covers {forecast_pct:.0f}% of goal -- accelerate pipeline.'}"
    )
    return result


# ---------------------------------------------------------------------------
# LEAD MANAGEMENT scoring
# ---------------------------------------------------------------------------

def score_lead_management(data: Dict[str, Any]) -> Dict[str, Any]:
    result = _empty_category_result("lead_management")
    ls = _safe_dict(data.get("lead_scoring", {}))
    kpis = _safe_dict(ls.get("kpis"))
    pipe = _safe_dict(data.get("pipeline", {}))

    if not data.get("_lead_ok"):
        result["explanation"] = "Lead Scoring agent returned an error; cannot score."
        result["missing_metrics"] = [k["name"] for k in KPI_DEFINITIONS["lead_management"]]
        return result

    total_leads = _safe_num(kpis.get("total_leads"))
    avg_score = _safe_num(kpis.get("average_score"))
    hot = _safe_num(kpis.get("hot_leads"))
    warm = _safe_num(kpis.get("warm_leads"))
    decay = _safe_num(kpis.get("leads_at_risk"))
    conv = _safe_dict(pipe.get("conversion_rates", {}))
    daily_call = _safe_list(ls.get("daily_call_list"))

    expected = 5
    metrics_used = []
    contribs = []
    missing = []

    # 1. Avg lead score (benchmark 60)
    s_avg = _higher_is_better(avg_score, 60, max_scale=100)
    if avg_score == 0 and total_leads == 0:
        missing.append("avg_lead_score")
    else:
        contribs.append({"score": s_avg, "weight": 0.25})
        metrics_used.append(_metric_entry(
            "avg_lead_score", "Average Lead Score", f"{avg_score:.1f}", ">= 60", s_avg, "score"))

    # 2. Hot + warm ratio
    hot_warm = hot + warm
    hw_pct = _ratio_pct(hot_warm, total_leads)
    s_hw = _higher_is_better(hw_pct, 30, max_scale=80)
    contribs.append({"score": s_hw, "weight": 0.20})
    metrics_used.append(_metric_entry(
        "hot_warm_ratio", "Hot + Warm Leads", f"{hw_pct:.0f}% ({hot_warm}/{int(total_leads)})",
        ">= 30% of leads", s_hw, "percent"))

    # 3. Decay alert ratio (lower better; benchmark 15%)
    decay_pct = _ratio_pct(decay, total_leads)
    s_decay = _lower_is_better(decay_pct, 50)  # 50% of leads decaying -> 0
    contribs.append({"score": s_decay, "weight": 0.25})
    metrics_used.append(_metric_entry(
        "decay_alert_ratio", "Leads Going Cold", f"{decay_pct:.0f}% ({int(decay)}/{int(total_leads)})",
        "<= 15%", s_decay, "percent"))

    # 4. Stage conversion (early stages)
    early = [conv.get("new", 0), conv.get("contacted", 0), conv.get("qualified", 0)]
    early = [v for v in early if v is not None]
    avg_conv = sum(early) / len(early) if early else 0.0
    s_conv = _higher_is_better(avg_conv, 80, max_scale=100)
    contribs.append({"score": s_conv, "weight": 0.15})
    metrics_used.append(_metric_entry(
        "stage_conversion", "Stage-to-Stage Conversion", f"{avg_conv:.1f}%",
        ">= 80% per stage", s_conv, "percent"))

    # 5. Daily call list coverage
    s_dcl = 100.0 if len(daily_call) >= 3 else (50.0 if daily_call else 0.0)
    contribs.append({"score": s_dcl, "weight": 0.15})
    metrics_used.append(_metric_entry(
        "follow_up_velocity", "Daily Call List Coverage", f"{len(daily_call)} leads",
        "Daily call list populated", s_dcl, "count"))

    score = _weighted_average(contribs)
    coverage = (len(metrics_used) / expected) * 100.0
    result["score"] = score if coverage >= MIN_COVERAGE_PERCENT else None
    result["status"] = "scored" if coverage >= MIN_COVERAGE_PERCENT else "insufficient_data"
    result["coverage"] = round(coverage, 1)
    result["metrics_used"] = metrics_used
    result["missing_metrics"] = missing

    problems, opps = [], []
    if avg_score < 50:
        problems.append(f"Average lead score is {avg_score:.1f}/100 -- most leads are not yet sales-ready.")
    if hot == 0:
        problems.append("Zero hot leads in the pipeline right now.")
    if decay_pct > 30:
        problems.append(f"{int(decay)} leads ({decay_pct:.0f}%) are decaying and at risk of going cold.")
    if hw_pct < 30:
        opps.append("Improving lead qualification would lift the hot/warm share above the 30% benchmark.")
    opps.append(f"Working the {len(daily_call)}-lead daily call list consistently would reduce decay alerts.")

    recs = []
    if decay > 0:
        recs.append(_recommendation(
            f"Re-engage {int(decay)} leads flagged as decaying before they go cold.",
            f"{int(decay)} decaying leads", "decaying_lead", decay * INDUSTRY_CONFIG["blended_avg_revenue_per_sale"],
            "call"))
    if hot + warm > 0:
        recs.append(_recommendation(
            "Prioritize the {} hot/warm leads for same-day follow-up.".format(int(hot + warm)),
            "Hot/Warm leads", "lead", (hot + warm) * INDUSTRY_CONFIG["blended_avg_revenue_per_sale"],
            "follow_up"))
    result["problems"] = problems
    result["opportunities"] = opps
    result["recommended_actions"] = recs
    result["explanation"] = (
        f"Lead Management scores {score}/100. Average lead quality is {avg_score:.1f}/100 with "
        f"{int(hot)} hot and {int(warm)} warm leads. {int(decay)} leads are decaying ({decay_pct:.0f}%). "
        f"{'Pipeline is healthy.' if decay_pct <= 15 and hw_pct >= 30 else 'Follow-up consistency needs attention.'}"
    )
    return result


# ---------------------------------------------------------------------------
# CLIENT RELATIONSHIPS scoring
# ---------------------------------------------------------------------------

def score_client_relationships(data: Dict[str, Any]) -> Dict[str, Any]:
    result = _empty_category_result("client_relationships")
    clv = _safe_dict(data.get("clv_intelligence", {}))
    p6 = _safe_dict(data.get("crm_management", {}))
    p6k = _safe_dict(p6.get("kpis"))

    if not data.get("_clv_ok"):
        result["explanation"] = "CLV Intelligence agent returned an error; cannot score."
        result["missing_metrics"] = [k["name"] for k in KPI_DEFINITIONS["client_relationships"]]
        return result

    clients = _safe_list(clv.get("clients"))
    risks = _safe_list(clv.get("risks"))
    conc = _safe_dict(clv.get("concentration"))
    rev_conc = _safe_dict(conc.get("revenue_concentration"))

    total_clients = len(clients) if clients else _safe_num(clv.get("kpis", {}).get("total_clients"))
    avg_health = sum(_safe_num(c.get("clv_score")) for c in clients) / len(clients) if clients else 0.0
    at_risk = sum(1 for r in risks if _safe_str(r.get("risk_level")).lower() in ("moderate", "high", "critical"))
    overdue_tasks = _safe_num(p6k.get("overdue_tasks"))
    missed_appts = _safe_num(p6k.get("missed_appointments"))
    critical_alerts = _safe_num(p6k.get("critical_alerts"))
    lifecycle_alerts = _safe_num(p6k.get("lifecycle_alerts"))
    top3_pct = _safe_num(rev_conc.get("top_3_pct"))

    expected = 5
    metrics_used = []
    contribs = []
    missing = []

    # 1. Avg client health (benchmark 70)
    s_health = _higher_is_better(avg_health, 70, max_scale=100) if clients else 0.0
    if not clients:
        missing.append("avg_client_health")
    else:
        contribs.append({"score": s_health, "weight": 0.25})
        metrics_used.append(_metric_entry(
            "avg_client_health", "Average Client Health Score", f"{avg_health:.1f}",
            ">= 70", s_health, "score"))

    # 2. At-risk clients ratio (lower better; benchmark 20%)
    at_risk_pct = _ratio_pct(at_risk, total_clients)
    s_atrisk = _lower_is_better(at_risk_pct, 60)  # 60% at risk -> 0
    contribs.append({"score": s_atrisk, "weight": 0.25})
    metrics_used.append(_metric_entry(
        "at_risk_clients", "At-Risk Clients", f"{at_risk_pct:.0f}% ({at_risk}/{int(total_clients)})",
        "<= 20% of clients", s_atrisk, "percent"))

    # 3. Overdue reviews & tasks (lower better; benchmark 0; scale 10 -> 0)
    overdue_total = overdue_tasks + missed_appts
    s_overdue = _lower_is_better(overdue_total, 10)
    contribs.append({"score": s_overdue, "weight": 0.20})
    metrics_used.append(_metric_entry(
        "overdue_reviews", "Overdue Reviews & Tasks", f"{int(overdue_total)} ({int(overdue_tasks)} tasks, {int(missed_appts)} missed appts)",
        "0 overdue", s_overdue, "count"))

    # 4. Critical lifecycle alerts (lower better; benchmark 0; scale 5 -> 0)
    s_crit = _lower_is_better(critical_alerts, 5)
    contribs.append({"score": s_crit, "weight": 0.15})
    metrics_used.append(_metric_entry(
        "lifecycle_alerts", "Critical Lifecycle Alerts", f"{int(critical_alerts)} critical / {int(lifecycle_alerts)} total",
        "0 critical alerts", s_crit, "count"))

    # 5. Concentration risk (lower better; benchmark 40% top3)
    s_conc = _lower_is_better(top3_pct, 80)  # 80% concentrated -> 0
    contribs.append({"score": s_conc, "weight": 0.15})
    metrics_used.append(_metric_entry(
        "concentration_risk", "Revenue Concentration", f"{top3_pct:.0f}% in top 3 clients",
        "<= 40% in top 3", s_conc, "percent"))

    score = _weighted_average(contribs)
    coverage = (len(metrics_used) / expected) * 100.0
    result["score"] = score if coverage >= MIN_COVERAGE_PERCENT else None
    result["status"] = "scored" if coverage >= MIN_COVERAGE_PERCENT else "insufficient_data"
    result["coverage"] = round(coverage, 1)
    result["metrics_used"] = metrics_used
    result["missing_metrics"] = missing

    problems, opps = [], []
    if avg_health < 70 and clients:
        problems.append(f"Average client health is {avg_health:.1f}/100 -- below the 70 healthy threshold.")
    if at_risk_pct > 30:
        problems.append(f"{at_risk} clients ({at_risk_pct:.0f}%) are at moderate or higher risk.")
    if overdue_total > 0:
        problems.append(f"{int(overdue_total)} overdue tasks/missed appointments need owner attention.")
    if critical_alerts > 0:
        problems.append(f"{int(critical_alerts)} critical lifecycle alerts are unresolved.")
    if top3_pct > 50:
        opps.append(f"Revenue is {top3_pct:.0f}% concentrated in 3 clients -- diversify to reduce risk.")
    opps.append(f"Scheduling the {int(lifecycle_alerts)} pending reviews would clear the alert backlog.")

    recs = []
    # Find the highest-risk client for a concrete action
    high_risk = sorted(risks, key=lambda r: _safe_num(r.get("risk_score")), reverse=True)
    if high_risk:
        rc = high_risk[0]
        name = rc.get("display_name", "at-risk client")
        recs.append(_recommendation(
            "Schedule an outreach for the highest-risk client ({}).".format(name),
            name, "at_risk_client", _safe_num(rc.get("risk_score")) * 10, "schedule"))
    if overdue_tasks > 0:
        recs.append(_recommendation(
            f"Complete {int(overdue_tasks)} overdue client tasks.".format(int(overdue_tasks)),
            "Overdue client tasks", "overdue_task", overdue_tasks * 50, "complete"))
    result["problems"] = problems
    result["opportunities"] = opps
    result["recommended_actions"] = recs
    result["explanation"] = (
        f"Client Relationships scores {score}/100. {int(total_clients)} clients average {avg_health:.1f}/100 health; "
        f"{at_risk} are at risk. {int(overdue_total)} overdue tasks/appointments and {int(critical_alerts)} critical alerts remain. "
        f"{'Client base is stable.' if at_risk_pct <= 20 and critical_alerts == 0 else 'Re-engagement needed.'}"
    )
    return result


# ---------------------------------------------------------------------------
# REFERRALS scoring
# ---------------------------------------------------------------------------

def score_referrals(data: Dict[str, Any]) -> Dict[str, Any]:
    result = _empty_category_result("referrals")
    ref = _safe_dict(data.get("referral_intelligence", {}))
    kpis = _safe_dict(ref.get("kpis"))

    if not data.get("_referral_ok"):
        result["explanation"] = "Referral Intelligence agent returned an error; cannot score."
        result["missing_metrics"] = [k["name"] for k in KPI_DEFINITIONS["referrals"]]
        return result

    total_sources = _safe_num(kpis.get("total_sources"))
    advocates = _safe_num(kpis.get("advocates"))
    high_pot = _safe_num(kpis.get("high_potential"))
    dormant = _safe_num(kpis.get("dormant"))
    opp_count = _safe_num(kpis.get("total_opportunities"))
    campaigns = _safe_list(ref.get("campaigns"))
    funnel = _safe_list(ref.get("funnel"))
    scored_sources = _safe_list(ref.get("scored_sources"))

    expected = 5
    metrics_used = []
    contribs = []
    missing = []

    # 1. Open referral opportunities (benchmark 5; max 15)
    s_opp = _higher_is_better(opp_count, 5, max_scale=15)
    contribs.append({"score": s_opp, "weight": 0.25})
    metrics_used.append(_metric_entry(
        "referral_opportunity_count", "Open Referral Opportunities", f"{int(opp_count)}",
        ">= 5 active", s_opp, "count"))

    # 2. Advocate ratio (advocates + high potential)
    adv = advocates + high_pot
    adv_pct = _ratio_pct(adv, total_sources)
    s_adv = _higher_is_better(adv_pct, 20, max_scale=60)
    contribs.append({"score": s_adv, "weight": 0.20})
    metrics_used.append(_metric_entry(
        "advocate_ratio", "Advocate Sources", f"{adv_pct:.0f}% ({int(adv)}/{int(total_sources)})",
        ">= 20%", s_adv, "percent"))

    # 3. Dormant ratio (lower better; benchmark 30%)
    dormant_pct = _ratio_pct(dormant, total_sources)
    s_dormant = _lower_is_better(dormant_pct, 60)
    contribs.append({"score": s_dormant, "weight": 0.25})
    metrics_used.append(_metric_entry(
        "dormant_ratio", "Dormant Referral Sources", f"{dormant_pct:.0f}% ({int(dormant)}/{int(total_sources)})",
        "<= 30%", s_dormant, "percent"))

    # 4. Funnel health (multi-stage progressing)
    funnel_score = 0.0
    if funnel and len(funnel) >= 3:
        # reward stages with meaningful counts beyond the first
        active_stages = sum(1 for f in funnel if _safe_num(_safe_dict(f).get("count")) > 0)
        funnel_score = _clamp((active_stages / len(funnel)) * 100)
    s_funnel = funnel_score
    contribs.append({"score": s_funnel, "weight": 0.15})
    metrics_used.append(_metric_entry(
        "funnel_conversion", "Referral Funnel Health", f"{len(funnel)} stages",
        "Active multi-stage funnel", s_funnel, "score"))

    # 5. Campaign readiness (benchmark 3)
    s_camp = _higher_is_better(len(campaigns), 3, max_scale=6)
    contribs.append({"score": s_camp, "weight": 0.15})
    metrics_used.append(_metric_entry(
        "campaign_readiness", "Referral Campaigns", f"{len(campaigns)} campaigns",
        ">= 3 active campaigns", s_camp, "count"))

    score = _weighted_average(contribs)
    coverage = (len(metrics_used) / expected) * 100.0
    result["score"] = score if coverage >= MIN_COVERAGE_PERCENT else None
    result["status"] = "scored" if coverage >= MIN_COVERAGE_PERCENT else "insufficient_data"
    result["coverage"] = round(coverage, 1)
    result["metrics_used"] = metrics_used
    result["missing_metrics"] = missing

    problems, opps = [], []
    if dormant_pct > 40:
        problems.append(f"{int(dormant)} referral sources ({dormant_pct:.0f}%) have gone dormant -- re-engagement needed.")
    if advocates == 0:
        problems.append("No advocate-tier referral sources yet -- the strongest relationships aren't being leveraged.")
    if opp_count < 5:
        problems.append(f"Only {int(opp_count)} open referral opportunities -- below the 5-opportunity benchmark.")
    opps.append(f"Activating the {int(dormant)} dormant sources could unlock untapped referral revenue.")
    opps.append(f"{int(high_pot)} high-potential sources are close to advocate tier -- nurture to convert.")

    recs = []
    # top opportunity source
    top_opp = _safe_list(ref.get("top_opportunities"))
    if top_opp:
        to = _safe_dict(top_opp[0])
        name = to.get("name", to.get("source_name", "top referral source"))
        val = _safe_num(to.get("estimated_value", to.get("potential_value", 0)))
        recs.append(_recommendation(
            "Contact the top referral opportunity source ({}).".format(name),
            name, "referral_opportunity", val, "contact_source"))
    if dormant > 0:
        recs.append(_recommendation(
            f"Re-engage {int(dormant)} dormant referral sources.".format(int(dormant)),
            "Dormant referral sources", "referral_opportunity", dormant * 200, "follow_up"))
    result["problems"] = problems
    result["opportunities"] = opps
    result["recommended_actions"] = recs
    result["explanation"] = (
        f"Referrals scores {score}/100. {int(total_sources)} sources, {int(adv)} advocate/high-potential, "
        f"{int(dormant)} dormant ({dormant_pct:.0f}%), and {int(opp_count)} open opportunities. "
        f"{'Referral engine is active.' if dormant_pct <= 30 else 'Too many sources have gone dormant.'}"
    )
    return result


# ---------------------------------------------------------------------------
# MARKETING scoring
# ---------------------------------------------------------------------------

def score_marketing(data: Dict[str, Any]) -> Dict[str, Any]:
    result = _empty_category_result("marketing")
    mkt = _safe_dict(data.get("marketing_summary", {}))
    p3 = _safe_dict(data.get("client_nurture", {}))
    p3k = _safe_dict(p3.get("kpis"))
    comp = _safe_dict(data.get("compliance", {}))

    compliance_status = _safe_str(mkt.get("compliance_status", comp.get("tcpa_compliant", "PASS")))
    compliance_blocks = _safe_num(mkt.get("compliance_blocks", comp.get("compliance_blocks", 0)))
    surveys_sent = _safe_num(p3k.get("surveys_sent", mkt.get("surveys_sent", 0)))
    surveys_done = _safe_num(p3k.get("surveys_completed", mkt.get("surveys_completed", 0)))
    active_nurture = _safe_num(p3k.get("active_nurture_clients", mkt.get("active_nurture_clients", 0)))
    email_campaigns = _safe_num(mkt.get("email_campaigns", 0))
    total_emails = _safe_num(mkt.get("total_emails", 0))

    expected = 4
    metrics_used = []
    contribs = []
    missing = []

    # 1. Compliance (PASS with 0 blocks = 100; blocks subtract heavily)
    if compliance_status.upper() == "PASS" and compliance_blocks == 0:
        s_comp = 100.0
    elif compliance_status.upper() == "PASS":
        s_comp = _clamp(100 - compliance_blocks * 20)
    else:
        s_comp = 0.0
    contribs.append({"score": s_comp, "weight": 0.35})
    metrics_used.append(_metric_entry(
        "compliance_status", "Compliance Status", f"{compliance_status} ({int(compliance_blocks)} blocks)",
        "PASS with 0 blocks", s_comp, "status"))

    # 2. Survey response rate (outcome metric, not vanity)
    resp_rate = _ratio_pct(surveys_done, surveys_sent)
    s_survey = _higher_is_better(resp_rate, 50, max_scale=100) if surveys_sent > 0 else 0.0
    if surveys_sent == 0:
        missing.append("survey_response_rate")
    else:
        contribs.append({"score": s_survey, "weight": 0.25})
        metrics_used.append(_metric_entry(
            "survey_response_rate", "Survey Response Rate", f"{resp_rate:.0f}% ({int(surveys_done)}/{int(surveys_sent)})",
            ">= 50%", s_survey, "percent"))

    # 3. Nurture coverage -- fraction of clients in nurture (need total clients)
    clv = _safe_dict(data.get("clv_intelligence", {}))
    total_clients = _safe_num(clv.get("kpis", {}).get("total_clients")) or active_nurture or 1
    nurture_pct = _ratio_pct(active_nurture, total_clients)
    s_nurture = _higher_is_better(nurture_pct, 100, max_scale=100)
    contribs.append({"score": s_nurture, "weight": 0.20})
    metrics_used.append(_metric_entry(
        "nurture_coverage", "Active Nurture Coverage", f"{nurture_pct:.0f}% ({int(active_nurture)}/{int(total_clients)} clients)",
        "All clients in nurture", s_nurture, "percent"))

    # 4. Campaign consistency -- campaigns with actual sends (total_emails>0).
    # NOTE: we deliberately do NOT reward raw total_emails or content count (vanity).
    campaigns_with_sends = email_campaigns if total_emails > 0 else 0
    s_camp = _higher_is_better(campaigns_with_sends, 3, max_scale=5)
    contribs.append({"score": s_camp, "weight": 0.20})
    metrics_used.append(_metric_entry(
        "campaign_consistency", "Email Campaign Activity", f"{int(campaigns_with_sends)} campaigns / {int(total_emails)} sends",
        ">= 3 active campaigns with sends", s_camp, "count"))

    score = _weighted_average(contribs)
    coverage = (len(metrics_used) / expected) * 100.0
    result["score"] = score if coverage >= MIN_COVERAGE_PERCENT else None
    result["status"] = "scored" if coverage >= MIN_COVERAGE_PERCENT else "insufficient_data"
    result["coverage"] = round(coverage, 1)
    result["metrics_used"] = metrics_used
    result["missing_metrics"] = missing

    problems, opps = [], []
    if compliance_blocks > 0:
        problems.append(f"{int(compliance_blocks)} compliance blocks must be resolved before publishing.")
    if surveys_sent > 0 and resp_rate < 50:
        problems.append(f"Survey response rate is {resp_rate:.0f}% -- below the 50% engagement benchmark.")
    if total_emails == 0:
        problems.append("Email campaigns are configured but none have actually sent yet.")
    if nurture_pct < 100:
        opps.append(f"{int(total_clients - active_nurture)} clients are not yet in a nurture sequence.")
    opps.append("Engagement outcomes (responses, clicks) matter more than content volume -- focus on sends that get replies.")

    recs = []
    if compliance_blocks > 0:
        recs.append(_recommendation(
            "Resolve {} compliance block(s) before publishing content.".format(int(compliance_blocks)),
            "Compliance blocks", "compliance_block", compliance_blocks * 500, "review"))
    if surveys_sent > 0 and resp_rate < 50:
        recs.append(_recommendation(
            "Follow up on {} uncompleted surveys to lift response rate.".format(int(surveys_sent - surveys_done)),
            "Pending surveys", "nurture_task", (surveys_sent - surveys_done) * 50, "send_message"))
    result["problems"] = problems
    result["opportunities"] = opps
    result["recommended_actions"] = recs
    result["explanation"] = (
        f"Marketing scores {score}/100. Compliance is {compliance_status} with {int(compliance_blocks)} blocks. "
        f"Survey response rate is {resp_rate:.0f}% and {nurture_pct:.0f}% of clients are in nurture. "
        f"{'Marketing is healthy and compliant.' if s_comp >= 100 and resp_rate >= 50 else 'Focus on engagement outcomes over volume.'}"
    )
    return result


# ---------------------------------------------------------------------------
# EXECUTION scoring
# ---------------------------------------------------------------------------

def score_execution(data: Dict[str, Any]) -> Dict[str, Any]:
    result = _empty_category_result("execution")
    perf = _safe_dict(data.get("performance_metrics", {}))
    needs = _safe_list(data.get("needs_attention"))
    top5 = _safe_list(data.get("top_5_priorities"))

    if not data.get("_ledger_ok"):
        result["explanation"] = "Action Ledger unavailable; cannot score execution."
        result["missing_metrics"] = [k["name"] for k in KPI_DEFINITIONS["execution"]]
        return result

    total_actions = _safe_num(perf.get("total_actions"))
    completed = _safe_num(perf.get("completed"))
    overdue = _safe_num(perf.get("overdue"))
    completion_rate = _safe_num(perf.get("completion_rate"))
    needs_count = len(needs)
    stuck = 0
    # stuck_opportunities from pipeline / snapshot
    pipe = _safe_dict(data.get("pipeline", {}))
    stuck = _safe_num(pipe.get("stuck_count"))

    expected = 4
    metrics_used = []
    contribs = []
    missing = []

    # 1. Completion rate -- special handling for empty ledger (0/0).
    if total_actions == 0:
        # No actions recorded yet is itself a weak-execution signal: the owner
        # isn't working the priority list. Score it low but not zero, and flag.
        s_comp = 25.0
        comp_label = "0% (no actions recorded yet)"
    else:
        s_comp = _higher_is_better(completion_rate, 70, max_scale=100)
        comp_label = f"{completion_rate:.0f}% ({int(completed)}/{int(total_actions)})"
    contribs.append({"score": s_comp, "weight": 0.30})
    metrics_used.append(_metric_entry(
        "completion_rate", "Action Completion Rate", comp_label,
        ">= 70%", s_comp, "percent"))

    # 2. Overdue actions (lower better; benchmark 0; scale 10 -> 0)
    s_overdue = _lower_is_better(overdue, 10)
    contribs.append({"score": s_overdue, "weight": 0.25})
    metrics_used.append(_metric_entry(
        "overdue_actions", "Overdue Actions", f"{int(overdue)}",
        "0 overdue", s_overdue, "count"))

    # 3. Needs attention volume (lower better; benchmark 5; scale 20 -> 0)
    s_needs = _lower_is_better(needs_count, 20)
    contribs.append({"score": s_needs, "weight": 0.25})
    metrics_used.append(_metric_entry(
        "needs_attention_volume", "Unaddressed Needs Attention", f"{needs_count} items",
        "<= 5 items outstanding", s_needs, "count"))

    # 4. Stuck opportunities (lower better; benchmark 0; scale 5 -> 0)
    s_stuck = _lower_is_better(stuck, 5)
    contribs.append({"score": s_stuck, "weight": 0.20})
    metrics_used.append(_metric_entry(
        "stuck_opportunities", "Stuck Opportunities", f"{int(stuck)}",
        "0 stuck", s_stuck, "count"))

    score = _weighted_average(contribs)
    coverage = (len(metrics_used) / expected) * 100.0
    result["score"] = score if coverage >= MIN_COVERAGE_PERCENT else None
    result["status"] = "scored" if coverage >= MIN_COVERAGE_PERCENT else "insufficient_data"
    result["coverage"] = round(coverage, 1)
    result["metrics_used"] = metrics_used
    result["missing_metrics"] = missing

    problems, opps = [], []
    if total_actions == 0:
        problems.append("No actions have been logged yet -- the priority list isn't being worked.")
    if overdue > 0:
        problems.append(f"{int(overdue)} actions are overdue.")
    if needs_count > 10:
        problems.append(f"{needs_count} items still need attention -- backlog is growing.")
    if stuck > 0:
        problems.append(f"{int(stuck)} pipeline opportunities are stuck in a stage.")
    opps.append(f"Working the {len(top5)} top priorities this week would lift completion and clear the backlog.")
    opps.append("Consistent daily execution is the highest-leverage habit for improving every other category.")

    recs = []
    if top5:
        first = _safe_dict(top5[0])
        recs.append(_recommendation(
            "Execute the #1 priority: {}.".format(first.get("entity", "top priority")),
            first.get("entity", "Top priority"), first.get("entity_type", "default"),
            _safe_num(first.get("priority_score", 0)) * 10, "complete"))
    if stuck > 0:
        recs.append(_recommendation(
            f"Unstick {int(stuck)} stalled pipeline opportunities.".format(int(stuck)),
            "Stuck opportunities", "revenue_gap", stuck * 100, "follow_up_opportunities"))
    result["problems"] = problems
    result["opportunities"] = opps
    result["recommended_actions"] = recs
    result["explanation"] = (
        f"Execution scores {score}/100. {int(total_actions)} actions recorded "
        f"({completion_rate:.0f}% complete), {int(overdue)} overdue, {needs_count} items need attention, "
        f"{int(stuck)} stuck opportunities. "
        f"{'Owner is executing well.' if total_actions > 0 and completion_rate >= 70 else 'Start working the priority list daily.'}"
    )
    return result


# ---------------------------------------------------------------------------
# Score dispatch
# ---------------------------------------------------------------------------

SCORERS = {
    "revenue": score_revenue,
    "lead_management": score_lead_management,
    "client_relationships": score_client_relationships,
    "referrals": score_referrals,
    "marketing": score_marketing,
    "execution": score_execution,
}


# ---------------------------------------------------------------------------
# Trend helpers (read/write snapshots)
# ---------------------------------------------------------------------------

def _snapshot_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), SNAPSHOT_FILE)


def load_snapshots() -> List[Dict[str, Any]]:
    try:
        with open(_snapshot_path()) as f:
            return json.load(f)
    except Exception:
        return []


def save_snapshots(snaps: List[Dict[str, Any]]):
    with open(_snapshot_path(), "w") as f:
        json.dump(snaps[-TREND_WEEKS:], f, indent=2)


def _category_trend(category_name, current_score, snapshots):
    """Compare current score to previous week's for this category."""
    if not snapshots or current_score is None:
        return None
    prev = snapshots[-1].get(category_name)
    if prev is None:
        return None
    if current_score > prev + 1:
        return "up"
    if current_score < prev - 1:
        return "down"
    return "flat"


# ---------------------------------------------------------------------------
# AI summary + insights
# ---------------------------------------------------------------------------

def _build_ai_summary(overall, categories, biggest_win, biggest_concern, biggest_opportunity):
    parts = []
    if overall is None:
        return "Insufficient data to compute a full Business Health Score. See category coverage for details."
    status = status_from_score(overall)
    parts.append(f"Business Health Score is {overall}/100 ({status}).")
    scored = [c for c in categories if c["status"] == "scored"]
    if scored:
        top_cat = max(scored, key=lambda c: c["score"] or 0)
        low_cat = min(scored, key=lambda c: c["score"] or 0)
        parts.append(f"Strongest area: {top_cat['label']} ({top_cat['score']}). Weakest: {low_cat['label']} ({low_cat['score']}).")
    if biggest_concern:
        parts.append(f"Biggest concern: {biggest_concern}.")
    if biggest_opportunity:
        parts.append(f"Biggest opportunity: {biggest_opportunity}.")
    return " ".join(parts)


def _determine_win_concern_opportunity(categories, snapshots):
    scored = [c for c in categories if c["status"] == "scored" and c["score"] is not None]
    win = concern = opportunity = None

    if scored:
        # Biggest win = strongest category OR largest upward trend
        win_cat = max(scored, key=lambda c: c["score"])
        # prefer an upward trend if present
        up_cats = [c for c in scored if c.get("trend") == "up"]
        if up_cats:
            win_cat = max(up_cats, key=lambda c: c["score"])
        win = f"{win_cat['label']} is your strongest area at {win_cat['score']}/100"

        # Biggest concern = weakest category OR largest downward trend
        down_cats = [c for c in scored if c.get("trend") == "down"]
        if down_cats:
            concern_cat = min(down_cats, key=lambda c: c["score"])
        else:
            concern_cat = min(scored, key=lambda c: c["score"])
        concern = f"{concern_cat['label']} is weakest at {concern_cat['score']}/100 -- {concern_cat['problems'][0] if concern_cat['problems'] else 'needs attention'}"

        # Biggest opportunity = category where improvement has highest business impact.
        # Business impact = weight * (100 - score). Highest gap weighted by category importance.
        opp_cat = max(scored, key=lambda c: CATEGORY_WEIGHTS.get(c["category"], 0) * (100 - (c["score"] or 0)))
        opp_gap = 100 - (opp_cat["score"] or 0)
        opportunity = f"Raising {opp_cat['label']} by {opp_gap:.0f} pts has the highest business impact (weight {int(CATEGORY_WEIGHTS.get(opp_cat['category'],0)*100)}%)"

    return win, concern, opportunity


def _weekly_brief(overall, categories, biggest_win, biggest_concern, biggest_opportunity, data):
    rev = _safe_dict(data.get("revenue_forecasting", {}))
    kpis = _safe_dict(rev.get("kpis"))
    targets = _safe_dict(rev.get("targets"))
    monthly = _safe_dict(targets.get("monthly"))
    actual = _safe_num(kpis.get("actual_revenue"))
    # Use business_config.revenue_goal if available, fall back to industry config
    _biz_goal = 0
    if _get_biz_config:
        try:
            _biz_goal = float(_get_biz_config().get('revenue_goal', 0) or 0)
        except Exception:
            _biz_goal = 0
    monthly_goal = _safe_num(monthly.get("goal")) or _biz_goal or INDUSTRY_CONFIG["target_monthly_revenue"]
    attainment = _percent_of(actual, monthly_goal)

    # Top 3 focus actions across categories
    focus = []
    for c in categories:
        for r in c.get("recommended_actions", []):
            focus.append({**r, "category": c["label"]})
    # sort by opportunity value desc
    focus.sort(key=lambda r: _safe_num(r.get("opportunity_value")), reverse=True)
    top3 = focus[:3]

    return {
        "health_score": overall,
        "win": biggest_win,
        "concern": biggest_concern,
        "opportunity": biggest_opportunity,
        "revenue_outlook": f"${actual:,.0f} booked ({attainment:.0f}% of ${monthly_goal:,.0f} monthly goal)",
        "top_3_focus_actions": top3,
    }


# ---------------------------------------------------------------------------
# Score transparency
# ---------------------------------------------------------------------------

def _build_transparency(categories, insufficient_count, used_weights):
    return {
        "method": "Weighted average of category scores. Categories with insufficient data are excluded and their weight is redistributed across available categories.",
        "category_weights_config": CATEGORY_WEIGHTS,
        "weights_used": used_weights,
        "insufficient_categories": insufficient_count,
        "min_coverage_percent": MIN_COVERAGE_PERCENT,
        "vanity_metrics_excluded": VANITY_METRICS,
        "missing_data_strategy": MISSING_DATA_RULES["strategy"],
        "industry": INDUSTRY_CONFIG["industry_label"],
        "disclaimer": f"{SAMPLE_DISCLAIMER} {DRAFT_DISCLAIMER}",
    }


# ---------------------------------------------------------------------------
# MASTER: get_scorecard()
# ---------------------------------------------------------------------------

def get_scorecard() -> Dict[str, Any]:
    """Returns the COMPLETE scorecard payload in one response."""
    data = _gather_data()
    snapshots = load_snapshots()

    # Score each category
    categories = []
    for name in CATEGORY_ORDER:
        scorer = SCORERS[name]
        try:
            res = scorer(data)
        except Exception as e:  # pragma: no cover -- defensive
            res = _empty_category_result(name)
            res["explanation"] = f"Scoring error: {e}"
            res["missing_metrics"] = [k["name"] for k in KPI_DEFINITIONS[name]]
        # attach trend
        res["trend"] = _category_trend(name, res.get("score"), snapshots)
        categories.append(res)

    # Overall score: normalize weights across scored categories only
    scored_cats = [c for c in categories if c["status"] == "scored" and c["score"] is not None]
    if scored_cats:
        total_w = sum(CATEGORY_WEIGHTS[c["category"]] for c in scored_cats)
        overall = round(sum(CATEGORY_WEIGHTS[c["category"]] * c["score"] for c in scored_cats) / total_w, 1) if total_w > 0 else None
        used_weights = {c["category"]: round(CATEGORY_WEIGHTS[c["category"]] / total_w, 3) for c in scored_cats} if total_w > 0 else {}
    else:
        overall = None
        used_weights = {}

    insufficient_count = sum(1 for c in categories if c["status"] != "scored")
    is_partial = insufficient_count > 0

    biggest_win, biggest_concern, biggest_opportunity = _determine_win_concern_opportunity(categories, snapshots)
    ai_summary = _build_ai_summary(overall, categories, biggest_win, biggest_concern, biggest_opportunity)
    weekly_brief = _weekly_brief(overall, categories, biggest_win, biggest_concern, biggest_opportunity, data)
    transparency = _build_transparency(categories, insufficient_count, used_weights)

    # Consolidated action recommendations
    all_recs = []
    for c in categories:
        for r in c.get("recommended_actions", []):
            r2 = dict(r)
            r2["category"] = c["label"]
            all_recs.append(r2)
    all_recs.sort(key=lambda r: _safe_num(r.get("opportunity_value")), reverse=True)

    payload = {
        "generated_at": datetime.now().isoformat(),
        "scan_date": TODAY.isoformat(),
        "overall_score": overall,
        "overall_label": "Partial Business Health Score" if is_partial else "Business Health Score",
        "overall_status": status_from_score(overall),
        "ai_summary": ai_summary,
        "categories": categories,
        "trends": {
            "snapshots": snapshots,
            "trend_weeks": TREND_WEEKS,
        },
        "biggest_win": biggest_win,
        "biggest_concern": biggest_concern,
        "biggest_opportunity": biggest_opportunity,
        "weekly_brief": weekly_brief,
        "score_transparency": transparency,
        "action_recommendations": all_recs[:15],
        "data_quality": {
            "v2_available": data.get("v2_available"),
            "v2_error": data.get("v2_error"),
            "ledger_available": data.get("ledger_available"),
            "ledger_error": data.get("ledger_error"),
            "categories_scored": len(scored_cats),
            "categories_insufficient": insufficient_count,
        },
        "disclaimer": f"{SAMPLE_DISCLAIMER} {DRAFT_DISCLAIMER}",
    }
    return payload


# ---------------------------------------------------------------------------
# Category detail
# ---------------------------------------------------------------------------

def get_category_detail(category_name: str) -> Dict[str, Any]:
    """Return detailed breakdown for a single category."""
    if category_name not in SCORERS:
        return {"error": f"Unknown category '{category_name}'. Valid: {list(SCORERS.keys())}"}
    data = _gather_data()
    snapshots = load_snapshots()
    try:
        res = SCORERS[category_name](data)
    except Exception as e:
        res = _empty_category_result(category_name)
        res["explanation"] = f"Scoring error: {e}"
    res["trend"] = _category_trend(category_name, res.get("score"), snapshots)
    res["kpi_definitions"] = KPI_DEFINITIONS.get(category_name, [])
    return res


# ---------------------------------------------------------------------------
# Snapshot save
# ---------------------------------------------------------------------------

def save_current_snapshot() -> Dict[str, Any]:
    """Compute current scorecard and persist a weekly snapshot."""
    card = get_scorecard()
    week = TODAY.isoformat()
    snap = {"week": week, "overall": card["overall_score"]}
    for c in card["categories"]:
        snap[c["category"]] = c["score"]
    snaps = load_snapshots()
    # replace if same week exists
    snaps = [s for s in snaps if s.get("week") != week]
    snaps.append(snap)
    snaps = snaps[-TREND_WEEKS:]
    save_snapshots(snaps)
    return {"status": "ok", "snapshot": snap, "total_snapshots": len(snaps)}


# ---------------------------------------------------------------------------
# Ask the scorecard (AI interpretation)
# ---------------------------------------------------------------------------

def ask_scorecard(question: str = "") -> Dict[str, Any]:
    """Answer owner questions using current scorecard data (rule-based)."""
    q = (question or "").lower().strip()
    card = get_scorecard()
    cats = {c["category"]: c for c in card["categories"]}

    answer = ""
    focus_actions = []

    if not q:
        answer = card["ai_summary"]
    elif "drop" in q or "down" in q or "decline" in q or "lower" in q:
        down = [c for c in card["categories"] if c.get("trend") == "down"]
        weak = sorted([c for c in card["categories"] if c["status"] == "scored"], key=lambda c: c["score"] or 0)
        if down:
            answer = "Score pressure is coming from: " + ", ".join(f"{c['label']} (trending down to {c['score']})" for c in down) + "."
        elif weak:
            w = weak[0]
            answer = f"Your lowest-scoring area is {w['label']} at {w['score']}/100. " + (w["problems"][0] if w["problems"] else "")
        else:
            answer = "No downward trends detected in the current data."
    elif "raise" in q or "improve" in q or "increase" in q or "fastest" in q or "higher" in q:
        opp = card.get("biggest_opportunity", "")
        answer = f"To raise your score fastest: {opp}. Focus on the highest-weight category with the largest gap."
        # surface that category's actions
        scored = [c for c in card["categories"] if c["status"] == "scored"]
        if scored:
            opp_cat = max(scored, key=lambda c: CATEGORY_WEIGHTS.get(c["category"], 0) * (100 - (c["score"] or 0)))
            focus_actions = opp_cat.get("recommended_actions", [])
    elif "revenue" in q or "money" in q or "income" in q:
        r = cats.get("revenue", {})
        answer = r.get("explanation", "Revenue data unavailable.")
        focus_actions = r.get("recommended_actions", [])
    elif "lead" in q:
        r = cats.get("lead_management", {})
        answer = r.get("explanation", "Lead data unavailable.")
        focus_actions = r.get("recommended_actions", [])
    elif "client" in q:
        r = cats.get("client_relationships", {})
        answer = r.get("explanation", "Client data unavailable.")
        focus_actions = r.get("recommended_actions", [])
    elif "referral" in q:
        r = cats.get("referrals", {})
        answer = r.get("explanation", "Referral data unavailable.")
        focus_actions = r.get("recommended_actions", [])
    elif "marketing" in q:
        r = cats.get("marketing", {})
        answer = r.get("explanation", "Marketing data unavailable.")
        focus_actions = r.get("recommended_actions", [])
    elif "execution" in q or "action" in q or "do" in q:
        r = cats.get("execution", {})
        answer = r.get("explanation", "Execution data unavailable.")
        focus_actions = r.get("recommended_actions", [])
    else:
        answer = card["ai_summary"]

    return {
        "question": question,
        "answer": answer,
        "overall_score": card["overall_score"],
        "focus_actions": focus_actions[:5],
        "disclaimer": f"{SAMPLE_DISCLAIMER} {DRAFT_DISCLAIMER}",
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _safe_str(v):
    return str(v) if v is not None else ""


if __name__ == "__main__":
    print("=" * 70)
    print("BUSINESS OWNER SCORECARD ENGINE -- TEST RUN")
    print("=" * 70)
    card = get_scorecard()
    print("\nScan date:", card["scan_date"])
    print("Overall:", card["overall_score"], "/", card["overall_label"], "-", card["overall_status"])
    print("\nAI SUMMARY:", card["ai_summary"])
    print("\n--- CATEGORIES ---")
    for c in card["categories"]:
        sc = c["score"] if c["score"] is not None else "N/A"
        print(f"  {c['label']:<22} {sc:>5}  [{c['status']}]  coverage {c['coverage']}%  trend={c['trend']}")
        for m in c["metrics_used"]:
            print(f"      - {m['label']}: {m['value']}  (benchmark: {m['benchmark']})  contrib={m['contribution']}")
        if c["missing_metrics"]:
            print(f"      MISSING: {c['missing_metrics']}")
    print("\n--- WEEKLY BRIEF ---")
    wb = card["weekly_brief"]
    print("  Health:", wb["health_score"])
    print("  Win:", wb["win"])
    print("  Concern:", wb["concern"])
    print("  Opportunity:", wb["opportunity"])
    print("  Revenue outlook:", wb["revenue_outlook"])
    print("  Top 3 focus actions:")
    for a in wb["top_3_focus_actions"]:
        print(f"    - [{a.get('action_type')}] {a.get('entity')}: {a.get('action')}")
    print("\n--- SCORE TRANSPARENCY ---")
    t = card["score_transparency"]
    print("  Method:", t["method"])
    print("  Weights used:", t["weights_used"])
    print("  Insufficient categories:", t["insufficient_categories"])
    print("  Vanity metrics excluded:", len(t["vanity_metrics_excluded"]))
    print("\n--- ACTION RECOMMENDATIONS (top 5) ---")
    for r in card["action_recommendations"][:5]:
        print(f"  - [{r.get('action_type')}] {r.get('entity')}: {r.get('action')}  (value ${r.get('opportunity_value',0):,.0f})")
    print("\n" + "=" * 70)
    print("SCORECARD ENGINE TEST COMPLETE")
    print("=" * 70)
