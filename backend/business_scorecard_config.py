#!/usr/bin/env python3
"""
Business Owner Scorecard Configuration
=======================================
Centralized configuration for the Medicare/Life Insurance agency
Business Owner Scorecard scoring engine.

Everything here is configurable so the same engine can be retargeted to
other industries (roofing, HVAC, real estate, etc.) by swapping
INDUSTRY_CONFIG and re-weighting categories.

All data is SAMPLE. All recommendations are DRAFT -- owner approval required.
"""

from datetime import date
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TODAY = date(2026, 8, 16)
DRAFT_DISCLAIMER = "DRAFT -- owner approval required."
SAMPLE_PREFIX = "[SAMPLE]"
SAMPLE_DISCLAIMER = "All data marked [SAMPLE]."

# ---------------------------------------------------------------------------
# Category weights (must sum to 1.0)
# ---------------------------------------------------------------------------
CATEGORY_WEIGHTS: Dict[str, float] = {
    "revenue": 0.25,
    "lead_management": 0.20,
    "client_relationships": 0.20,
    "referrals": 0.15,
    "marketing": 0.10,
    "execution": 0.10,
}

# Ordered list (used for stable display + iteration)
CATEGORY_ORDER: List[str] = [
    "revenue",
    "lead_management",
    "client_relationships",
    "referrals",
    "marketing",
    "execution",
]

# Human-friendly display labels
CATEGORY_LABELS: Dict[str, str] = {
    "revenue": "Revenue",
    "lead_management": "Lead Management",
    "client_relationships": "Client Relationships",
    "referrals": "Referrals",
    "marketing": "Marketing",
    "execution": "Execution",
}

# Which AI agent owns each category (for transparency / data source map)
CATEGORY_AGENT: Dict[str, str] = {
    "revenue": "Revenue Forecasting + CRM Management",
    "lead_management": "Lead Scoring + Lead Follow-Up",
    "client_relationships": "CLV Intelligence + CRM Management",
    "referrals": "Referral Intelligence",
    "marketing": "Marketing Content + Client Nurture",
    "execution": "Action Ledger + Priority Engine",
}

# ---------------------------------------------------------------------------
# Score thresholds (overall + per-category)
# ---------------------------------------------------------------------------
SCORE_THRESHOLDS: Dict[str, int] = {
    "excellent": 85,
    "good": 70,
    "fair": 50,
    "poor": 30,
}

# Minimum data coverage required to score a category (below this -> insufficient_data)
MIN_COVERAGE_PERCENT = 50.0


def status_from_score(score: Any) -> str:
    """Map a numeric score to a qualitative status label."""
    if score is None:
        return "insufficient_data"
    if score >= SCORE_THRESHOLDS["excellent"]:
        return "excellent"
    if score >= SCORE_THRESHOLDS["good"]:
        return "good"
    if score >= SCORE_THRESHOLDS["fair"]:
        return "fair"
    if score >= SCORE_THRESHOLDS["poor"]:
        return "poor"
    return "critical"


# ---------------------------------------------------------------------------
# Industry configuration -- Medicare / Life Insurance (Colorado agency)
# ---------------------------------------------------------------------------
INDUSTRY_CONFIG: Dict[str, Any] = {
    "industry_key": "medicare_life_insurance",
    "industry_label": "Medicare / Life Insurance",
    "region": "Colorado, USA",
    # Commission economics (sample planning assumptions)
    "avg_commission_per_medicare_policy": 350,   # first-year MA commission range
    "avg_commission_per_life_policy": 800,       # term/whole-life first-year
    "blended_avg_revenue_per_sale": 500,         # matches revenue_gap analysis input
    "historical_close_rate": 0.14,               # lead-to-sale conversion (small sample)
    "target_monthly_revenue": 25000,
    "target_quarterly_revenue": 75000,
    "target_annual_revenue": 300000,
    # Seasonality -- Annual Enrollment Period drives Medicare volume
    "aep_start": "October 15",
    "aep_end": "December 7",
    "oep_start": "January 1",
    "oep_end": "March 31",
    "peak_season_label": "AEP (Oct 15 - Dec 7)",
    # Regulatory compliance expectations
    "compliance_frameworks": [
        "TCPA", "CAN-SPAM", "CMS 42 CFR 422.2268",
        "C.R.S. 10-3-1104 (CO anti-rebating)", "FTC Endorsement Guides",
    ],
    # Cadence expectations
    "expected_client_review_cadence_days": 90,
    "expected_lead_followup_hours": 24,
    "expected_referral_contact_cadence_days": 90,
    "dormant_threshold_days": 180,
    # Vocabulary mapping (industry term -> plain English used in scorecard)
    "terminology": {
        "lead": "Prospect / Lead",
        "prospect": "Prospect",
        "client": "Policyholder / Client",
        "closed_won": "Enrolled / Policy issued",
        "consultation": "Benefits review / appointment",
        "pipeline": "Open opportunities",
        "AEP": "Annual Enrollment Period (Oct 15 - Dec 7)",
        "OEP": "Open Enrollment Period (Jan 1 - Mar 31)",
        "MA": "Medicare Advantage",
        "Part D": "Medicare prescription drug coverage",
        "CLV": "Client Lifetime Value",
        "commission": "Agent commission",
        "carrier": "Insurance carrier",
        "NBS": "New Business Submitted",
    },
}

# Alternate industry presets (for future retargeting -- not active)
INDUSTRY_PRESETS: Dict[str, Dict[str, Any]] = {
    "roofing": {
        "industry_key": "roofing",
        "industry_label": "Residential Roofing",
        "blended_avg_revenue_per_sale": 8500,
        "historical_close_rate": 0.25,
        "target_annual_revenue": 1200000,
        "peak_season_label": "Storm season (Apr - Sep)",
    },
    "hvac": {
        "industry_key": "hvac",
        "industry_label": "Residential HVAC",
        "blended_avg_revenue_per_sale": 6500,
        "historical_close_rate": 0.30,
        "target_annual_revenue": 900000,
        "peak_season_label": "Summer (Jun - Aug) + Winter peaks",
    },
}

# ---------------------------------------------------------------------------
# KPI definitions per category
# ---------------------------------------------------------------------------
# Each KPI: name, source_fn (logical name of data source), benchmark,
# direction ('higher' or 'lower' is better), weight (within category),
# unit, and a human description. The engine resolves source_fn to actual
# data via the data-gathering layer in business_scorecard_engine.py.

KPI_DEFINITIONS: Dict[str, List[Dict[str, Any]]] = {
    "revenue": [
        {
            "name": "revenue_attainment",
            "label": "Revenue vs Monthly Goal",
            "source_fn": "revenue_forecasting",
            "benchmark": ">= 100% of monthly goal",
            "direction": "higher",
            "weight": 0.30,
            "unit": "percent_of_goal",
            "description": "Actual revenue achieved as a share of the monthly goal.",
        },
        {
            "name": "pipeline_coverage",
            "label": "Pipeline Coverage",
            "source_fn": "revenue_forecasting + pipeline",
            "benchmark": ">= 3.0x weighted pipeline vs remaining gap",
            "direction": "higher",
            "weight": 0.20,
            "unit": "ratio",
            "description": "Weighted pipeline strength relative to the open revenue gap.",
        },
        {
            "name": "close_rate",
            "label": "Close Rate",
            "source_fn": "pipeline",
            "benchmark": ">= 30% (industry small-sample)",
            "direction": "higher",
            "weight": 0.20,
            "unit": "percent",
            "description": "Share of opportunities that close won.",
        },
        {
            "name": "revenue_at_risk_ratio",
            "label": "Revenue at Risk",
            "source_fn": "revenue_forecasting",
            "benchmark": "<= 10% of active pipeline",
            "direction": "lower",
            "weight": 0.15,
            "unit": "ratio",
            "description": "Revenue flagged at risk relative to active pipeline value.",
        },
        {
            "name": "forecast_strength",
            "label": "30-Day Forecast Strength",
            "source_fn": "revenue_forecasting",
            "benchmark": ">= 100% of monthly goal covered",
            "direction": "higher",
            "weight": 0.15,
            "unit": "percent_of_goal",
            "description": "Forecast + committed revenue coverage of the monthly goal.",
        },
    ],
    "lead_management": [
        {
            "name": "avg_lead_score",
            "label": "Average Lead Score",
            "source_fn": "lead_scoring",
            "benchmark": ">= 60 (warm+)",
            "direction": "higher",
            "weight": 0.25,
            "unit": "score",
            "description": "Mean quality score across all open leads.",
        },
        {
            "name": "hot_warm_ratio",
            "label": "Hot + Warm Leads",
            "source_fn": "lead_scoring",
            "benchmark": ">= 30% of leads",
            "direction": "higher",
            "weight": 0.20,
            "unit": "percent",
            "description": "Share of leads scoring warm or hot (actionable).",
        },
        {
            "name": "decay_alert_ratio",
            "label": "Leads Going Cold",
            "source_fn": "lead_scoring",
            "benchmark": "<= 15% of leads at risk",
            "direction": "lower",
            "weight": 0.25,
            "unit": "percent",
            "description": "Leads flagged as decaying / at risk of going cold.",
        },
        {
            "name": "stage_conversion",
            "label": "Stage-to-Stage Conversion",
            "source_fn": "pipeline",
            "benchmark": ">= 80% per stage",
            "direction": "higher",
            "weight": 0.15,
            "unit": "percent",
            "description": "Average progression rate across early pipeline stages.",
        },
        {
            "name": "follow_up_velocity",
            "label": "Daily Call List Coverage",
            "source_fn": "lead_scoring",
            "benchmark": "Daily call list populated",
            "direction": "higher",
            "weight": 0.15,
            "unit": "count",
            "description": "Whether a prioritized daily call list exists and is populated.",
        },
    ],
    "client_relationships": [
        {
            "name": "avg_client_health",
            "label": "Average Client Health Score",
            "source_fn": "clv_intelligence",
            "benchmark": ">= 70",
            "direction": "higher",
            "weight": 0.25,
            "unit": "score",
            "description": "Mean CLV/relationship health score across clients.",
        },
        {
            "name": "at_risk_clients",
            "label": "At-Risk Clients",
            "source_fn": "clv_intelligence",
            "benchmark": "<= 20% of clients at moderate+ risk",
            "direction": "lower",
            "weight": 0.25,
            "unit": "percent",
            "description": "Share of clients flagged moderate or high risk.",
        },
        {
            "name": "overdue_reviews",
            "label": "Overdue Reviews & Tasks",
            "source_fn": "crm_management",
            "benchmark": "0 overdue",
            "direction": "lower",
            "weight": 0.20,
            "unit": "count",
            "description": "Overdue tasks and missed appointments for clients.",
        },
        {
            "name": "lifecycle_alerts",
            "label": "Critical Lifecycle Alerts",
            "source_fn": "crm_management",
            "benchmark": "0 critical alerts",
            "direction": "lower",
            "weight": 0.15,
            "unit": "count",
            "description": "Critical client lifecycle alerts (anniversaries, reviews, lapses).",
        },
        {
            "name": "concentration_risk",
            "label": "Revenue Concentration",
            "source_fn": "clv_intelligence",
            "benchmark": "<= 40% in top 3 clients",
            "direction": "lower",
            "weight": 0.15,
            "unit": "percent",
            "description": "Revenue concentrated in the top 3 clients (diversification risk).",
        },
    ],
    "referrals": [
        {
            "name": "referral_opportunity_count",
            "label": "Open Referral Opportunities",
            "source_fn": "referral_intelligence",
            "benchmark": ">= 5 active opportunities",
            "direction": "higher",
            "weight": 0.25,
            "unit": "count",
            "description": "Number of actionable referral opportunities identified.",
        },
        {
            "name": "advocate_ratio",
            "label": "Advocate Sources",
            "source_fn": "referral_intelligence",
            "benchmark": ">= 1 advocate (or high-potential) per 5 sources",
            "direction": "higher",
            "weight": 0.20,
            "unit": "percent",
            "description": "Share of referral sources that are advocates or high-potential.",
        },
        {
            "name": "dormant_ratio",
            "label": "Dormant Referral Sources",
            "source_fn": "referral_intelligence",
            "benchmark": "<= 30% dormant",
            "direction": "lower",
            "weight": 0.25,
            "unit": "percent",
            "description": "Share of referral sources that have gone dormant.",
        },
        {
            "name": "funnel_conversion",
            "label": "Referral Funnel Health",
            "source_fn": "referral_intelligence",
            "benchmark": "Active multi-stage funnel",
            "direction": "higher",
            "weight": 0.15,
            "unit": "score",
            "description": "Whether the referral funnel is populated and progressing.",
        },
        {
            "name": "campaign_readiness",
            "label": "Referral Campaigns",
            "source_fn": "referral_intelligence",
            "benchmark": ">= 3 active campaigns",
            "direction": "higher",
            "weight": 0.15,
            "unit": "count",
            "description": "Number of active referral campaigns ready to run.",
        },
    ],
    "marketing": [
        {
            "name": "compliance_status",
            "label": "Compliance Status",
            "source_fn": "marketing + compliance",
            "benchmark": "PASS with 0 blocks",
            "direction": "higher",
            "weight": 0.35,
            "unit": "status",
            "description": "Regulatory compliance across content and campaigns.",
        },
        {
            "name": "survey_response_rate",
            "label": "Survey Response Rate",
            "source_fn": "client_nurture",
            "benchmark": ">= 50%",
            "direction": "higher",
            "weight": 0.25,
            "unit": "percent",
            "description": "Share of sent surveys that were completed (engagement outcome).",
        },
        {
            "name": "nurture_coverage",
            "label": "Active Nurture Coverage",
            "source_fn": "client_nurture",
            "benchmark": "All clients in nurture",
            "direction": "higher",
            "weight": 0.20,
            "unit": "percent",
            "description": "Share of clients actively in a nurture sequence.",
        },
        {
            "name": "campaign_consistency",
            "label": "Email Campaign Activity",
            "source_fn": "marketing",
            "benchmark": ">= 3 active campaigns with sends",
            "direction": "higher",
            "weight": 0.20,
            "unit": "count",
            "description": "Active email campaigns that have actually sent (not just configured).",
        },
    ],
    "execution": [
        {
            "name": "completion_rate",
            "label": "Action Completion Rate",
            "source_fn": "action_ledger",
            "benchmark": ">= 70%",
            "direction": "higher",
            "weight": 0.30,
            "unit": "percent",
            "description": "Share of recorded actions the owner has completed.",
        },
        {
            "name": "overdue_actions",
            "label": "Overdue Actions",
            "source_fn": "action_ledger",
            "benchmark": "0 overdue",
            "direction": "lower",
            "weight": 0.25,
            "unit": "count",
            "description": "Actions past their due date still open.",
        },
        {
            "name": "needs_attention_volume",
            "label": "Unaddressed Needs Attention",
            "source_fn": "priority_engine",
            "benchmark": "<= 5 items outstanding",
            "direction": "lower",
            "weight": 0.25,
            "unit": "count",
            "description": "Number of priority items still needing the owner's attention.",
        },
        {
            "name": "stuck_opportunities",
            "label": "Stuck Opportunities",
            "source_fn": "priority_engine",
            "benchmark": "0 stuck",
            "direction": "lower",
            "weight": 0.20,
            "unit": "count",
            "description": "Pipeline opportunities stalled in a stage too long.",
        },
    ],
}

# ---------------------------------------------------------------------------
# Missing-data handling rules
# ---------------------------------------------------------------------------
MISSING_DATA_RULES: Dict[str, Any] = {
    # When a metric cannot be resolved, record it in missing_metrics and
    # exclude it from the weighted score (re-normalize remaining weights).
    "strategy": "exclude_and_renormalize",
    # Coverage is computed as: (resolved KPIs / expected KPIs) * 100
    # If coverage < MIN_COVERAGE_PERCENT -> status='insufficient_data', score=None
    "min_coverage_percent": MIN_COVERAGE_PERCENT,
    # When the ENTIRE category data source fails (agent error), mark all
    # KPIs as missing and set category to insufficient_data.
    "on_agent_error": "insufficient_data",
}

# ---------------------------------------------------------------------------
# Vanity-metric guardrail
# ---------------------------------------------------------------------------
# These metrics are NEVER counted as positive contributors on their own --
# they only matter when paired with an outcome metric. The engine explicitly
# does not reward raw counts without outcomes.
VANITY_METRICS: List[str] = [
    "content_pieces",          # count alone, no engagement outcome
    "calendar_entries",         # scheduled count alone
    "touchpoints_scheduled",   # scheduled count alone (vs delivered)
    "total_emails",             # sent count alone (vs opened/clicked)
    "drip_emails",              # configured count alone
    "total_actions",            # raw count (vs completion rate)
    "missing_tags",             # CRM hygiene, not a business outcome
    "unused_tags",
    "missing_fields",
    "duplicate_contacts",
]

# ---------------------------------------------------------------------------
# Trend window
# ---------------------------------------------------------------------------
TREND_WEEKS = 8          # how many weeks of snapshots to retain
SNAPSHOT_FILE = "scorecard_snapshots.json"


def get_config_summary() -> Dict[str, Any]:
    """Return a flat summary of the active configuration (for transparency)."""
    return {
        "industry": INDUSTRY_CONFIG["industry_label"],
        "region": INDUSTRY_CONFIG["region"],
        "category_weights": CATEGORY_WEIGHTS,
        "score_thresholds": SCORE_THRESHOLDS,
        "min_coverage_percent": MIN_COVERAGE_PERCENT,
        "missing_data_strategy": MISSING_DATA_RULES["strategy"],
        "vanity_metrics_excluded": VANITY_METRICS,
        "trend_weeks": TREND_WEEKS,
        "today": TODAY.isoformat(),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(get_config_summary(), indent=2))
