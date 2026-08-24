"""
Demo Business Data Generator for Command Center V2.

Generates realistic demo data for 5 different business types and 4 scenarios.
Each demo business gets a complete dataset that powers all existing features.
"""

import sqlite3
import json
import os
import uuid
import random
from datetime import datetime, timedelta, date

random.seed(42)

DB_PATH = "data.db"

# ============================================================
# DEMO BUSINESS DEFINITIONS
# ============================================================

DEMO_BUSINESSES = {
    "roofing": {
        "id": "roofing",
        "name": "[SAMPLE] Rocky Mountain Roofing",
        "industry": "Roofing & Exterior",
        "years_in_business": 12,
        "team_size": 18,
        "revenue_goal": 85000,
        "current_revenue": 52000,
        "avg_transaction_value": 8500,
        "primary_objective": "Grow residential re-roofing revenue",
        "services": [
            ("Residential Re-Roof", 8500, "roofing"),
            ("Storm Damage Repair", 4200, "repair"),
            ("Roof Inspection", 350, "inspection"),
            ("Gutter Installation", 1800, "gutter"),
            ("Skylight Installation", 2200, "skylight"),
            ("Commercial Roofing", 25000, "commercial"),
        ],
        "lead_sources": ["Google Ads", "Facebook Ads", "Referral", "Angi", "HomeAdvisor", "Organic Search"],
        "first_names": ["Robert", "Jennifer", "Michael", "Linda", "David", "Susan", "James", "Patricia", "John", "Mary", "Richard", "Elizabeth", "Thomas", "Barbara", "Charles", "Susan", "Daniel", "Jessica", "Matthew", "Amanda"],
        "last_names": ["Anderson", "Martinez", "Thompson", "Garcia", "Wilson", "Johnson", "Williams", "Brown", "Davis", "Miller", "Taylor", "Clark", "Lewis", "Walker", "Hall", "Young", "King", "Wright", "Lopez", "Hill"],
        "story": {
            "strength": "Strong referral program drives 40% of new business",
            "weakness": "Lead follow-up process is slow -- 5 leads untouched for 48+ hours",
            "opportunity": "Storm season approaching -- pipeline is building",
            "risk": "Revenue target missed by 6% last month"
        }
    },
    "hvac": {
        "id": "hvac",
        "name": "[SAMPLE] Front Range HVAC",
        "industry": "HVAC & Mechanical",
        "years_in_business": 8,
        "team_size": 24,
        "revenue_goal": 120000,
        "current_revenue": 78000,
        "avg_transaction_value": 6200,
        "primary_objective": "Expand seasonal maintenance contracts",
        "services": [
            ("AC Installation", 6200, "installation"),
            ("Furnace Replacement", 5800, "installation"),
            ("Emergency Repair", 850, "repair"),
            ("Maintenance Contract", 480, "maintenance"),
            ("Duct Cleaning", 650, "service"),
            ("Heat Pump Installation", 9500, "installation"),
        ],
        "lead_sources": ["Google Ads", "Referral", "HomeAdvisor", "Facebook Ads", "Organic Search", "Angi"],
        "first_names": ["Christopher", "Ashley", "Andrew", "Brittany", "Justin", "Samantha", "Ryan", "Lauren", "Tyler", "Nicole", "Brandon", "Megan", "Dustin", "Rachel", "Kevin", "Stephanie", "Brian", "Emily", "Jason", "Sarah"],
        "last_names": ["Carter", "Reed", "Bailey", "Cooper", "Murphy", "Rivera", "Cook", "Bell", "Morris", "Sanders", "Price", "Bennett", "Wood", "Ross", "Coleman", "Jenkins", "Perry", "Powell", "Long", "Hughes"],
        "story": {
            "strength": "Growing fast -- 35% revenue increase year over year",
            "weakness": "Capacity bottleneck during summer peak demand",
            "opportunity": "Emergency repair value is high -- capitalize on demand",
            "risk": "Maintenance contract renewal rate slipping"
        }
    },
    "landscaping": {
        "id": "landscaping",
        "name": "[SAMPLE] Evergreen Landscaping",
        "industry": "Landscaping & Lawn Care",
        "years_in_business": 15,
        "team_size": 32,
        "revenue_goal": 65000,
        "current_revenue": 41000,
        "avg_transaction_value": 3200,
        "primary_objective": "Increase recurring maintenance revenue",
        "services": [
            ("Landscape Design", 4500, "design"),
            ("Lawn Maintenance", 180, "maintenance"),
            ("Hardscape Installation", 7500, "hardscape"),
            ("Tree Service", 1200, "tree"),
            ("Irrigation System", 2800, "irrigation"),
            ("Seasonal Cleanup", 650, "cleanup"),
        ],
        "lead_sources": ["Referral", "Google Ads", "Facebook Ads", "Organic Search", "Angi", "Yard Signs"],
        "first_names": ["Austin", "Hailey", "Logan", "Kaitlyn", "Caleb", "Sydney", "Connor", "Morgan", "Ethan", "Olivia", "Nathan", "Savannah", "Dylan", "Brooke", "Hunter", "Kayla", "Mason", "Allison", "Owen", "Grace"],
        "last_names": ["Bryant", "Dunn", "Walsh", "Foster", "Soto", "Vasquez", "Manning", "Holt", "Brennan", "Frost", "Page", "Bates", "Chase", "Delgado", "English", "Finley", "Gallagher", "Harmon", "Ibarra", "Jacobson"],
        "story": {
            "strength": "Strong repeat customers -- 70% retention rate",
            "weakness": "Seasonal revenue swings create cash flow gaps",
            "opportunity": "Upsell hardscape installations to existing maintenance clients",
            "risk": "Competing on price -- margins are thin"
        }
    },
    "marketing": {
        "id": "marketing",
        "name": "[SAMPLE] Summit Growth Marketing",
        "industry": "Marketing Agency",
        "years_in_business": 5,
        "team_size": 12,
        "revenue_goal": 75000,
        "current_revenue": 58000,
        "avg_transaction_value": 4500,
        "primary_objective": "Increase retainer client base",
        "services": [
            ("SEO Retainer", 3500, "retainer"),
            ("PPC Management", 2500, "retainer"),
            ("Content Marketing", 2800, "retainer"),
            ("Social Media Management", 2000, "retainer"),
            ("Website Redesign", 12000, "project"),
            ("Marketing Audit", 1800, "project"),
        ],
        "lead_sources": ["LinkedIn", "Referral", "Organic Search", "Google Ads", "Content Marketing", "Speaking Events"],
        "first_names": ["Alex", "Jordan", "Casey", "Riley", "Quinn", "Avery", "Drew", "Reese", "Sage", "Finley", "Blake", "Cameron", "Dakota", "Emerson", "Frankie", "Greer", "Harlow", "Indigo", "Jules", "Kendall"],
        "last_names": ["Sterling", "Mercer", "Holloway", "Preston", "Ashford", "Bancroft", "Carrington", "Delacroix", "Easton", "Fairchild", "Garrison", "Harrington", "Ingram", "Kensington", "Lockhart", "Montgomery", "Prescott", "Sinclair", "Templeton", "Vance"],
        "story": {
            "strength": "Strong pipeline -- 12 active opportunities",
            "weakness": "Conversion rate slipping -- 15% drop in close rate",
            "opportunity": "Retainer clients have high lifetime value",
            "risk": "Two large retainer clients up for renewal this quarter"
        }
    },
    "consulting": {
        "id": "consulting",
        "name": "[SAMPLE] Peak Advisory Consulting",
        "industry": "Business Consulting",
        "years_in_business": 7,
        "team_size": 6,
        "revenue_goal": 50000,
        "current_revenue": 38000,
        "avg_transaction_value": 12000,
        "primary_objective": "Expand strategic advisory engagements",
        "services": [
            ("Strategic Planning", 15000, "advisory"),
            ("Operations Audit", 8000, "audit"),
            ("Financial Review", 6500, "review"),
            ("Growth Strategy", 12000, "strategy"),
            ("Executive Coaching", 3500, "coaching"),
            ("Market Analysis", 7500, "analysis"),
        ],
        "lead_sources": ["Referral", "LinkedIn", "Speaking Events", "Organic Search", "Content Marketing", "Past Client"],
        "first_names": ["Victoria", "Benjamin", "Claire", "Nicholas", "Adelaide", "Harrison", "Eleanor", "Sebastian", "Caroline", "Theodore", "Genevieve", "Augustus", "Penelope", "Maxwell", "Charlotte", "Nathaniel", "Vivian", "Oliver", "Abigail", "Henry"],
        "last_names": ["Ashworth", "Beaumont", "Carrington", "Devereux", "Eastwick", "Fairbourne", "Greystone", "Hawkridge", "Iverson", "Kingsley", "Lockwood", "Marchetti", "Northrop", "Pemberton", "Radcliffe", "Stoneham", "Thackeray", "Underhill", "Wakefield", "Yarrow"],
        "story": {
            "strength": "High customer value -- avg engagement is $12,000",
            "weakness": "Long sales cycle -- 90 days average from lead to close",
            "opportunity": "Strong referral network -- 60% of new business from referrals",
            "risk": "Follow-up discipline needed -- 3 leads untouched for 2 weeks"
        }
    }
}

# ============================================================
# SCENARIO DEFINITIONS
# ============================================================

SCENARIOS = {
    "balanced": {
        "id": "balanced",
        "name": "Steady Operations",
        "description": "A balanced business with typical operations",
        "lead_volume": "normal",
        "conversion_rate": 0.25,
        "revenue_trend": "stable",
        "referral_strength": "moderate",
        "follow_up_delay": 1,
        "pipeline_health": "normal",
    },
    "growing_fast": {
        "id": "growing_fast",
        "name": "Growing Fast",
        "description": "Strong leads, increasing revenue, capacity challenges",
        "lead_volume": "high",
        "conversion_rate": 0.32,
        "revenue_trend": "increasing",
        "referral_strength": "strong",
        "follow_up_delay": 2,
        "pipeline_health": "strong",
    },
    "revenue_decline": {
        "id": "revenue_decline",
        "name": "Revenue Decline",
        "description": "Lead volume falling, conversion dropping",
        "lead_volume": "low",
        "conversion_rate": 0.15,
        "revenue_trend": "decreasing",
        "referral_strength": "weak",
        "follow_up_delay": 4,
        "pipeline_health": "weak",
    },
    "referral_machine": {
        "id": "referral_machine",
        "name": "Referral Machine",
        "description": "Strong customer retention, high referral activity",
        "lead_volume": "moderate",
        "conversion_rate": 0.38,
        "revenue_trend": "stable",
        "referral_strength": "very_strong",
        "follow_up_delay": 1,
        "pipeline_health": "normal",
    },
    "operational_bottleneck": {
        "id": "operational_bottleneck",
        "name": "Operational Bottleneck",
        "description": "Strong demand but limited capacity to deliver",
        "lead_volume": "high",
        "conversion_rate": 0.30,
        "revenue_trend": "stable",
        "referral_strength": "moderate",
        "follow_up_delay": 3,
        "pipeline_health": "strong",
    }
}

# ============================================================
# DATA GENERATION HELPERS
# ============================================================

def gen_id(prefix):
    """Generate a unique ID with date prefix."""
    today = date.today().strftime("%Y%m%d")
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"{prefix}-{today}-{short_uuid}"

def gen_date(days_ago):
    """Generate a date string N days ago."""
    d = date.today() - timedelta(days=days_ago)
    return d.isoformat()

def gen_phone():
    """Generate a phone number."""
    return f"({random.randint(200,999)}) {random.randint(200,999)}-{random.randint(1000,9999)}"

def gen_email(first, last):
    """Generate an email."""
    domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"]
    return f"{first.lower()}.{last.lower().replace(' ','')}@{random.choice(domains)}"

def gen_revenue_history(base_monthly, trend, months=12):
    """Generate monthly revenue with realistic fluctuations."""
    records = []
    trend_factor = {"increasing": 1.05, "decreasing": 0.95, "stable": 1.0}[trend]
    
    for i in range(months, 0, -1):
        # Add seasonal variation
        month_num = (date.today().month - i) % 12 + 1
        seasonal = 1.0
        if month_num in [11, 12, 1, 2]:  # Winter dip for most businesses
            seasonal = 0.8
        elif month_num in [5, 6, 7, 8]:  # Summer peak
            seasonal = 1.15
        
        # Calculate amount
        base = base_monthly * (trend_factor ** (months - i)) * seasonal
        amount = base * random.uniform(0.85, 1.15)
        amount = round(amount, 2)
        
        records.append({
            "amount": amount,
            "date": gen_date(i * 30 + random.randint(1, 28)),
            "days_ago": i * 30 + random.randint(1, 28),
        })
    
    return records

def gen_contacts(business, scenario, count=35):
    """Generate contacts -- mix of leads and clients."""
    contacts = []
    used_names = set()
    
    # Determine distribution based on scenario
    lead_ratio = {"high": 0.6, "moderate": 0.45, "normal": 0.5, "low": 0.35}[scenario["lead_volume"]]
    num_leads = int(count * lead_ratio)
    num_clients = count - num_leads
    
    # Generate leads
    lead_stages = ["new", "contacted", "qualified", "new", "contacted", "qualified"]
    for i in range(num_leads):
        first = random.choice(business["first_names"])
        last = random.choice(business["last_names"])
        name_key = f"{first}{last}"
        while name_key in used_names:
            first = random.choice(business["first_names"])
            last = random.choice(business["last_names"])
            name_key = f"{first}{last}"
        used_names.add(name_key)
        
        source = random.choice(business["lead_sources"])
        stage = random.choice(lead_stages)
        days_ago = random.randint(1, 45)
        
        contacts.append({
            "contact_id": gen_id("CNT"),
            "first_name": f"[SAMPLE] {first}",
            "last_name": last,
            "email": gen_email(first, last),
            "phone": gen_phone(),
            "contact_type": "lead",
            "lead_source": source,
            "pipeline_stage": stage,
            "medicare_status": "",
            "email_consent": random.choice([0, 1]),
            "sms_consent": random.choice([0, 1]),
            "call_consent": random.choice([0, 1]),
            "last_activity": gen_date(days_ago),
            "client_since": None,
            "zip_code": str(random.randint(80100, 81600)),
            "state": "CO",
            "tags": "",
            "notes": "",
            "is_sample": 1,
            "days_ago": days_ago,
            "stage": stage,
        })
    
    # Generate clients
    for i in range(num_clients):
        first = random.choice(business["first_names"])
        last = random.choice(business["last_names"])
        name_key = f"{first}{last}"
        while name_key in used_names:
            first = random.choice(business["first_names"])
            last = random.choice(business["last_names"])
            name_key = f"{first}{last}"
        used_names.add(name_key)
        
        source = random.choice(business["lead_sources"])
        client_days = random.randint(60, 730)
        
        contacts.append({
            "contact_id": gen_id("CNT"),
            "first_name": f"[SAMPLE] {first}",
            "last_name": last,
            "email": gen_email(first, last),
            "phone": gen_phone(),
            "contact_type": "client",
            "lead_source": source,
            "pipeline_stage": "closed_won",
            "medicare_status": "",
            "email_consent": 1,
            "sms_consent": random.choice([0, 1]),
            "call_consent": 1,
            "last_activity": gen_date(random.randint(1, 60)),
            "client_since": gen_date(client_days),
            "zip_code": str(random.randint(80100, 81600)),
            "state": "CO",
            "tags": random.choice(["vip", "repeat", "referral_source", ""]),
            "notes": "",
            "is_sample": 1,
            "days_ago": client_days,
            "stage": "closed_won",
        })
    
    return contacts

def gen_opportunities(contacts, business, scenario, count=15):
    """Generate opportunities for leads."""
    opps = []
    leads = [c for c in contacts if c["contact_type"] == "lead"]
    
    stages = ["new", "contacted", "qualified", "application_submitted", "closed_won", "closed_lost"]
    stage_weights = [0.20, 0.25, 0.20, 0.10, 0.15, 0.10]
    
    # Adjust for scenario conversion rate
    if scenario["conversion_rate"] > 0.30:
        stage_weights = [0.15, 0.20, 0.15, 0.10, 0.25, 0.15]
    elif scenario["conversion_rate"] < 0.20:
        stage_weights = [0.25, 0.25, 0.20, 0.05, 0.10, 0.15]
    
    for i in range(min(count, len(leads))):
        contact = leads[i]
        service = random.choice(business["services"])
        stage = random.choices(stages, weights=stage_weights)[0]
        value = service[1] * random.uniform(0.8, 1.2)
        days_ago = random.randint(1, 60)
        
        opps.append({
            "opp_id": gen_id("OPP"),
            "contact_id": contact["contact_id"],
            "product_type": service[0],
            "stage": stage,
            "entered_stage": gen_date(days_ago),
            "expected_close": gen_date(random.randint(-5, 30)) if stage not in ["closed_won", "closed_lost"] else None,
            "estimated_value": round(value, 2),
            "created_date": gen_date(days_ago),
            "is_sample": 1,
        })
    
    return opps

def gen_revenue(contacts, business, scenario, count=18):
    """Generate revenue records for clients. Ensures current month has data."""
    records = []
    clients = [c for c in contacts if c["contact_type"] == "client"]
    revenue_history = gen_revenue_history(
        business["current_revenue"] / 12,
        scenario["revenue_trend"],
        months=12
    )
    
    for i, rev in enumerate(revenue_history):
        client = random.choice(clients)
        service = random.choice(business["services"])
        
        records.append({
            "record_id": gen_id("REV"),
            "contact_id": client["contact_id"],
            "product_type": service[0],
            "amount": rev["amount"],
            "revenue_date": rev["date"],
            "revenue_category": "service",
            "payment_status": "received",
            "source": client["lead_source"],
            "is_sample": 1,
        })
    
    # Ensure current month has revenue records (3-5 records)
    today = date.today()
    current_month_revenue = [r for r in records if r["revenue_date"].startswith(today.strftime("%Y-%m"))]
    needed = max(0, 4 - len(current_month_revenue))
    for i in range(needed):
        client = random.choice(clients)
        service = random.choice(business["services"])
        day = random.randint(1, min(today.day, 28))
        rev_date = today.replace(day=day).isoformat()
        amount = (business["current_revenue"] / 12) * random.uniform(0.15, 0.4)
        
        records.append({
            "record_id": gen_id("REV"),
            "contact_id": client["contact_id"],
            "product_type": service[0],
            "amount": round(amount, 2),
            "revenue_date": rev_date,
            "revenue_category": "service",
            "payment_status": "received",
            "source": client["lead_source"],
            "is_sample": 1,
        })
    
    return records

def gen_referral_sources(contacts, business, scenario, count=6):
    """Generate referral sources from clients."""
    sources = []
    clients = [c for c in contacts if c["contact_type"] == "client"]
    
    strength_map = {"very_strong": 85, "strong": 75, "moderate": 60, "weak": 40}
    base_strength = strength_map.get(scenario["referral_strength"], 50)
    
    for i in range(min(count, len(clients))):
        client = clients[i]
        referrals_gen = random.randint(3, 18) if base_strength > 60 else random.randint(0, 5)
        referrals_conv = int(referrals_gen * scenario["conversion_rate"])
        revenue = referrals_conv * business["avg_transaction_value"] * random.uniform(0.7, 1.3)
        
        sources.append({
            "source_id": gen_id("REF"),
            "source_name": client["first_name"] + " " + client["last_name"],  # Already has [SAMPLE] prefix from contact name
            "source_type": "client",
            "contact_info": client["email"],
            "relationship_strength": base_strength + random.randint(-10, 10),
            "referrals_generated": referrals_gen,
            "referrals_converted": referrals_conv,
            "conversion_rate": referrals_conv / referrals_gen if referrals_gen > 0 else 0,
            "total_revenue_generated": round(revenue, 2),
            "last_referral_date": gen_date(random.randint(1, 45)),
            "status": "active",
            "is_sample": 1,
        })
    
    return sources

def gen_actions(contacts, opportunities, business, scenario, count=8):
    """Generate actionable items."""
    actions = []
    leads = [c for c in contacts if c["contact_type"] == "lead"]
    
    action_types = [
        ("follow_up", "Follow up with lead", "Contact this lead within 24 hours to maximize conversion probability."),
        ("estimate", "Send estimate", "Prepare and send a detailed estimate to this prospect."),
        ("check_in", "Client check-in", "Reach out to this client for a satisfaction check-in."),
        ("referral_request", "Request referral", "This satisfied client is a strong referral candidate."),
        ("renewal", "Renewal reminder", "Service contract renewal is approaching."),
    ]
    
    for i in range(count):
        contact = random.choice(leads) if leads else random.choice(contacts)
        action_type, title_prefix, desc = random.choice(action_types)
        priority = random.randint(1, 5)
        days_ago = random.randint(0, 10)
        
        actions.append({
            "action_id": gen_id("ACT"),
            "entity_type": "contact",
            "entity_id": contact["contact_id"],
            "entity_name": contact["first_name"] + " " + contact["last_name"],
            "action_type": action_type,
            "title": f"{title_prefix}: {contact['first_name']} {contact['last_name']}",
            "description": desc,
            "priority": priority,
            "due_date": gen_date(-random.randint(0, 7)),
            "status": "pending",
            "completed_date": None,
            "expected_value": business["avg_transaction_value"] * random.uniform(0.5, 1.5),
            "actual_outcome": "",
            "recommendation_id": "",
            "source_module": "demo",
            "is_sample": 1,
        })
    
    return actions

def gen_recommendations(contacts, opportunities, business, scenario, count=6):
    """Generate realistic AI recommendations tied to demo data."""
    recs = []
    leads = [c for c in contacts if c["contact_type"] == "lead"]
    clients = [c for c in contacts if c["contact_type"] == "client"]
    
    # Follow-up opportunity
    uncontacted = [l for l in leads if l["stage"] in ["new", "contacted"]]
    if uncontacted:
        top_lead = uncontacted[0]
        recs.append({
            "rec_id": gen_id("REC"),
            "entity_type": "contact",
            "entity_id": top_lead["contact_id"],
            "rec_type": "follow_up",
            "title": f"Follow up with {len(uncontacted)} uncontacted leads",
            "description": f"{len(uncontacted)} leads have not been contacted in 48+ hours. Each day of delay reduces conversion probability by 15%.",
            "priority": 2,
            "expected_impact": f"Estimated opportunity value: ${len(uncontacted) * business['avg_transaction_value'] * 0.3:,.0f}",
            "ignore_consequence": "Leads will go cold and conversion probability will drop significantly.",
            "next_step": f"Contact {top_lead['first_name']} {top_lead['last_name']} first -- highest estimated value.",
            "explanation_data": json.dumps({"factors": ["Lead age > 48 hours", "High estimated value", "Industry avg conversion drops 15% per day"]}),
            "status": "active",
        })
    
    # Referral opportunity
    referral_candidates = [c for c in clients if c.get("tags") in ["vip", "referral_source", "repeat"]]
    if referral_candidates:
        recs.append({
            "rec_id": gen_id("REC"),
            "entity_type": "contact",
            "entity_id": referral_candidates[0]["contact_id"],
            "rec_type": "referral_request",
            "title": f"{len(referral_candidates)} satisfied clients are likely referral candidates",
            "description": f"Based on customer value and relationship strength, {len(referral_candidates)} clients show high referral potential.",
            "priority": 3,
            "expected_impact": f"Potential referral value: ${len(referral_candidates) * business['avg_transaction_value'] * scenario['conversion_rate']:,.0f}",
            "ignore_consequence": "Referral opportunities will be missed. Competitors may build relationships with these contacts.",
            "next_step": f"Reach out to {referral_candidates[0]['first_name']} {referral_candidates[0]['last_name']} -- strongest relationship.",
            "explanation_data": json.dumps({"factors": ["High customer satisfaction", "Strong relationship strength", "Industry referral rate 40%"]}),
            "status": "active",
        })
    
    # Revenue gap
    gap = business["revenue_goal"] - business["current_revenue"]
    gap_pct = (gap / business["revenue_goal"]) * 100 if business["revenue_goal"] > 0 else 0
    recs.append({
        "rec_id": gen_id("REC"),
        "entity_type": "business",
        "entity_id": "global",
        "rec_type": "revenue_gap",
        "title": f"Revenue is {gap_pct:.0f}% below monthly target",
        "description": f"Current revenue is ${business['current_revenue']:,.0f} against a goal of ${business['revenue_goal']:,.0f}. Gap: ${gap:,.0f}.",
        "priority": 2,
        "expected_impact": f"Closing {len([o for o in opportunities if o['stage'] not in ['closed_won', 'closed_lost']])} open opportunities could recover ${sum(o['estimated_value'] for o in opportunities if o['stage'] not in ['closed_won', 'closed_lost']):,.0f}.",
        "ignore_consequence": "Revenue gap will widen. Consider re-engaging dormant opportunities.",
        "next_step": "Focus on closing in-progress deals first -- they have the shortest path to revenue.",
        "explanation_data": json.dumps({"factors": ["Monthly target not met", "Open pipeline value available", "Historical close rate"]}),
        "status": "active",
    })
    
    # Pipeline opportunity
    active_opps = [o for o in opportunities if o["stage"] in ["qualified", "application_submitted"]]
    if active_opps:
        top_opp = max(active_opps, key=lambda o: o["estimated_value"])
        contact = next((c for c in contacts if c["contact_id"] == top_opp["contact_id"]), None)
        recs.append({
            "rec_id": gen_id("REC"),
            "entity_type": "opportunity",
            "entity_id": top_opp["opp_id"],
            "rec_type": "pipeline",
            "title": f"High-value opportunity ready to close: ${top_opp['estimated_value']:,.0f}",
            "description": f"{top_opp['product_type']} opportunity for {contact['first_name'] if contact else 'client'} {contact['last_name'] if contact else ''} is in {top_opp['stage']} stage.",
            "priority": 1,
            "expected_impact": f"Closing this deal adds ${top_opp['estimated_value']:,.0f} to revenue.",
            "ignore_consequence": "Competitor may win this deal. Delay reduces close probability.",
            "next_step": "Schedule a follow-up meeting to finalize terms.",
            "explanation_data": json.dumps({"factors": ["High estimated value", "Advanced pipeline stage", "Short close timeline"]}),
            "status": "active",
        })
    
    # Customer retention
    dormant_clients = [c for c in clients if c.get("days_ago", 0) > 180]
    if dormant_clients:
        recs.append({
            "rec_id": gen_id("REC"),
            "entity_type": "contact",
            "entity_id": dormant_clients[0]["contact_id"],
            "rec_type": "retention",
            "title": f"{len(dormant_clients)} clients haven't been contacted in 6+ months",
            "description": "These clients may be at risk of churning. A simple check-in call can re-engage them.",
            "priority": 3,
            "expected_impact": f"Retained client value: ${business['avg_transaction_value'] * len(dormant_clients):,.0f}",
            "ignore_consequence": "Clients may switch to competitors. Lost customers cost 5x more to replace.",
            "next_step": f"Call {dormant_clients[0]['first_name']} {dormant_clients[0]['last_name']} first.",
            "explanation_data": json.dumps({"factors": ["No contact > 180 days", "High lifetime value", "Churn risk increasing"]}),
            "status": "active",
        })
    
    # Marketing optimization
    recs.append({
        "rec_id": gen_id("REC"),
        "entity_type": "business",
        "entity_id": "global",
        "rec_type": "marketing",
        "title": "Optimize lead source mix for better ROI",
        "description": "Referral leads convert at 3x the rate of paid ads. Consider increasing referral outreach.",
        "priority": 4,
        "expected_impact": "Shifting 20% of ad spend to referral incentives could improve conversion by 8%.",
        "ignore_consequence": "Continued reliance on low-converting sources wastes budget.",
        "next_step": "Launch a referral incentive program for top clients.",
        "explanation_data": json.dumps({"factors": ["Referral conversion 3x higher than ads", "Cost per acquisition rising", "Referral ROI strongest"]}),
        "status": "active",
    })
    
    return recs[:count]

def gen_business_memory(business, scenario, count=4):
    """Generate business memory entries."""
    customer_goal = int(business["revenue_goal"] / business["avg_transaction_value"] * 0.6)
    memories = [
        ("business", "global", business["name"], f"Revenue goal: ${business['revenue_goal']:,}/month. Current: ${business['current_revenue']:,}. Customer goal: {customer_goal} new customers/month. Team: {business['team_size']} people. Years in business: {business['years_in_business']}.", "context", 90),
        ("business", "global", business["name"], f"Industry: {business['industry']}. Primary objective: {business['primary_objective']}. Average transaction value: ${business['avg_transaction_value']:,}.", "context", 85),
        ("scenario", "global", scenario["name"], f"Active scenario: {scenario['description']}. Conversion rate target: {scenario['conversion_rate']:.0%}. Lead volume: {scenario['lead_volume']}.", "context", 80),
        ("story", "global", business["name"], f"Key strength: {business['story']['strength']}. Key weakness: {business['story']['weakness']}. Opportunity: {business['story']['opportunity']}. Risk: {business['story']['risk']}.", "insight", 75),
    ]
    
    results = []
    for entity_type, entity_id, entity_name, text, category, score in memories[:count]:
        results.append({
            "memory_id": gen_id("MEM"),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_name": entity_name,
            "memory_text": text,
            "memory_category": category,
            "relevance_score": score,
        })
    
    return results

def gen_lead_sources(business):
    """Generate lead source records."""
    sources = []
    for i, name in enumerate(business["lead_sources"]):
        sources.append({
            "name": f"[SAMPLE] {name}",
            "description": f"{name} lead source",
            "is_active": 1,
            "sort_order": i,
        })
    return sources

def gen_services(business):
    """Generate service records."""
    services = []
    for i, (name, price, category) in enumerate(business["services"]):
        services.append({
            "name": f"[SAMPLE] {name}",
            "description": f"{name} service",
            "avg_price": price,
            "category": category,
            "is_active": 1,
            "sort_order": i,
        })
    return services

# ============================================================
# DATABASE MATERIALIZATION
# ============================================================

def clear_demo_data(conn):
    """Clear all demo/sample data from the database."""
    c = conn.cursor()
    
    # Tables with is_sample column - delete all (demo data has is_sample=1)
    sample_tables = ["contacts", "opportunities", "revenue_records", "referral_sources"]
    for table in sample_tables:
        c.execute(f"DELETE FROM {table}")
    
    # Tables without is_sample - delete all (regenerated each demo)
    other_tables = ["actions", "recommendations", "recommendation_feedback", "business_memory",
                     "services", "lead_sources"]
    for table in other_tables:
        c.execute(f"DELETE FROM {table}")
    
    # Reset auto-increment sequences (SQLite only — Postgres uses SERIAL, no need)
    try:
        c.execute("DELETE FROM sqlite_sequence WHERE name IN ('contacts','opportunities','revenue_records','referral_sources','actions','recommendations','recommendation_feedback','business_memory','services','lead_sources')")
    except Exception:
        pass  # sqlite_sequence doesn't exist in Postgres
    
    conn.commit()

def has_real_user_data(conn):
    """Check if any non-sample user data exists in the database."""
    c = conn.cursor()
    # Check contacts for non-sample records
    c.execute("SELECT COUNT(*) AS cnt FROM contacts WHERE is_sample = 0 AND first_name NOT LIKE '%[SAMPLE]%'")
    row = c.fetchone()
    if row:
        cnt = row["cnt"] if isinstance(row, dict) else row[0]
        if cnt and cnt > 0:
            return True
    # Check revenue for non-sample records
    c.execute("SELECT COUNT(*) AS cnt FROM revenue_records WHERE is_sample = 0")
    row = c.fetchone()
    if row:
        cnt = row["cnt"] if isinstance(row, dict) else row[0]
        if cnt and cnt > 0:
            return True
    return False

def materialize_demo(business_id, scenario_id="balanced"):
    """Materialize a demo business + scenario into the database."""
    business = DEMO_BUSINESSES[business_id]
    scenario = SCENARIOS[scenario_id]
    
    # Use raw psycopg2 connection directly (bypass wrapper to avoid recursion)
    import psycopg2
    from psycopg2 import extras as pg_extras
    DATABASE_URL = os.environ.get("DATABASE_URL", "")
    if not DATABASE_URL:
        # SQLite fallback
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL")
        is_pg = False
    else:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=pg_extras.RealDictCursor)
        is_pg = True
    
    def _exec(sql, params=None):
        """Execute SQL with auto-translation for Postgres."""
        if is_pg:
            sql = sql.replace("?", "%s")
            sql = sql.replace("INSERT OR IGNORE INTO", "INSERT INTO")
            sql = sql.replace("INSERT OR REPLACE INTO", "INSERT INTO")
            sql = sql.replace("datetime('now')", "NOW()")
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur
    
    # Check for real user data - block if found
    if has_real_user_data(conn):
        conn.close()
        raise ValueError("Cannot activate demo mode: real user data exists. Clear your data first.")
    
    # Clear existing data
    clear_demo_data(conn)
    
    # Update business config
    _exec("""
        UPDATE business_config SET
            business_name = ?,
            industry = ?,
            primary_objective = ?,
            revenue_goal = ?,
            goal_period = 'monthly',
            avg_transaction_value = ?,
            current_revenue = ?,
            setup_complete = 1,
            setup_completed_at = datetime('now'),
            updated_at = datetime('now')
        WHERE id = 1
    """, (
        business["name"],
        business["industry"],
        business["primary_objective"],
        business["revenue_goal"],
        business["avg_transaction_value"],
        business["current_revenue"],
    ))
    
    # Generate data
    contacts = gen_contacts(business, scenario)
    opportunities = gen_opportunities(contacts, business, scenario)
    revenue = gen_revenue(contacts, business, scenario)
    referrals = gen_referral_sources(contacts, business, scenario)
    actions = gen_actions(contacts, opportunities, business, scenario)
    recommendations = gen_recommendations(contacts, opportunities, business, scenario)
    memories = gen_business_memory(business, scenario)
    lead_sources = gen_lead_sources(business)
    services = gen_services(business)
    
    # Insert contacts
    for c in contacts:
        _exec("""
            INSERT INTO contacts (contact_id, first_name, last_name, email, phone, contact_type,
                lead_source, pipeline_stage, medicare_status, email_consent, sms_consent, call_consent,
                last_activity, client_since, zip_code, state, tags, notes, is_sample)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            c["contact_id"], c["first_name"], c["last_name"], c["email"], c["phone"],
            c["contact_type"], c["lead_source"], c["pipeline_stage"], c["medicare_status"],
            c["email_consent"], c["sms_consent"], c["call_consent"],
            c["last_activity"], c["client_since"], c["zip_code"], c["state"], c["tags"], c["notes"]
        ))
    
    # Insert opportunities
    for o in opportunities:
        _exec("""
            INSERT INTO opportunities (opp_id, contact_id, product_type, stage, entered_stage,
                expected_close, estimated_value, created_date, is_sample)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            o["opp_id"], o["contact_id"], o["product_type"], o["stage"],
            o["entered_stage"], o["expected_close"], o["estimated_value"], o["created_date"]
        ))
    
    # Insert revenue records
    for r in revenue:
        _exec("""
            INSERT INTO revenue_records (record_id, contact_id, product_type, amount,
                revenue_date, revenue_category, payment_status, source, is_sample)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            r["record_id"], r["contact_id"], r["product_type"], r["amount"],
            r["revenue_date"], r["revenue_category"], r["payment_status"], r["source"]
        ))
    
    # Insert referral sources
    for r in referrals:
        _exec("""
            INSERT INTO referral_sources (source_id, source_name, source_type, contact_info,
                relationship_strength, referrals_generated, referrals_converted, conversion_rate,
                total_revenue_generated, last_referral_date, status, is_sample)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            r["source_id"], r["source_name"], r["source_type"], r["contact_info"],
            r["relationship_strength"], r["referrals_generated"], r["referrals_converted"],
            r["conversion_rate"], r["total_revenue_generated"], r["last_referral_date"], r["status"]
        ))
    
    # Insert actions
    for a in actions:
        _exec("""
            INSERT INTO actions (action_id, entity_type, entity_id, entity_name, action_type,
                title, description, priority, due_date, status, completed_date, expected_value,
                actual_outcome, recommendation_id, source_module)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            a["action_id"], a["entity_type"], a["entity_id"], a["entity_name"],
            a["action_type"], a["title"], a["description"], a["priority"],
            a["due_date"], a["status"], a["completed_date"], a["expected_value"],
            a["actual_outcome"], a["recommendation_id"], a["source_module"]
        ))
    
    # Insert recommendations
    for r in recommendations:
        _exec("""
            INSERT INTO recommendations (rec_id, entity_type, entity_id, rec_type, title,
                description, priority, expected_impact, ignore_consequence, next_step,
                explanation_data, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r["rec_id"], r["entity_type"], r["entity_id"], r["rec_type"],
            r["title"], r["description"], r["priority"], r["expected_impact"],
            r["ignore_consequence"], r["next_step"], r["explanation_data"], r["status"]
        ))
    
    # Insert business memory
    for m in memories:
        _exec("""
            INSERT INTO business_memory (memory_id, entity_type, entity_id, entity_name,
                memory_text, memory_category, relevance_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            m["memory_id"], m["entity_type"], m["entity_id"], m["entity_name"],
            m["memory_text"], m["memory_category"], m["relevance_score"]
        ))
    
    # Insert lead sources
    for ls in lead_sources:
        _exec("""
            INSERT OR IGNORE INTO lead_sources (name, description, is_active, sort_order)
            VALUES (?, ?, ?, ?)
        """, (ls["name"], ls["description"], ls["is_active"], ls["sort_order"]))
    
    # Insert services
    for s in services:
        _exec("""
            INSERT OR IGNORE INTO services (name, description, avg_price, category, is_active, sort_order)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (s["name"], s["description"], s["avg_price"], s["category"], s["is_active"], s["sort_order"]))
    
    conn.commit()
    
    # Set demo state
    if is_pg:
        _exec("""
            INSERT INTO demo_state (business_id, scenario_id, state_json)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (business_id, scenario_id, '{}'))
    else:
        _exec("""
            INSERT OR REPLACE INTO demo_state (id, is_demo_mode, business_id, scenario_id, updated_at)
            VALUES (1, 1, ?, ?, datetime('now'))
        """, (business_id, scenario_id))
    conn.commit()
    conn.close()
    
    # Return summary
    return {
        "business_id": business_id,
        "business_name": business["name"],
        "scenario_id": scenario_id,
        "scenario_name": scenario["name"],
        "contacts": len(contacts),
        "opportunities": len(opportunities),
        "revenue_records": len(revenue),
        "referral_sources": len(referrals),
        "actions": len(actions),
        "recommendations": len(recommendations),
        "business_memory": len(memories),
        "lead_sources": len(lead_sources),
        "services": len(services),
    }

def get_demo_list():
    """Return list of available demo businesses."""
    return [
        {"id": b["id"], "name": b["name"], "industry": b["industry"],
         "team_size": b["team_size"], "revenue_goal": b["revenue_goal"],
         "story": b["story"]}
        for b in DEMO_BUSINESSES.values()
    ]

def get_scenario_list():
    """Return list of available scenarios."""
    return [
        {"id": s["id"], "name": s["name"], "description": s["description"]}
        for s in SCENARIOS.values()
    ]

if __name__ == "__main__":
    # Test: materialize roofing business
    result = materialize_demo("roofing", "balanced")
    print("Demo materialized:")
    for k, v in result.items():
        print(f"  {k}: {v}")
