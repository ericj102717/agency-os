#!/usr/bin/env python3
"""
Generate a realistic test dataset for a Medicare & Life Insurance agency CRM system
and insert it via the API at http://127.0.0.1:8022.

All person/place names are prefixed with [SAMPLE] so they are clearly test data.

Entities created (in dependency order):
  8. Business Config          -> /api/business/config
  6. Lead Sources (6)         -> /api/lead-sources
  7. Sales Stages (6)         -> /api/sales-stages
  5. Services (8)             -> /api/services
  1. Contacts (25)            -> /api/contacts
  2. Opportunities (10)      -> /api/opportunities   (reference contacts)
  4. Revenue Records (15)     -> /api/revenue          (reference client contacts)
  3. Referral Sources (5)     -> /api/referral-sources
  9. Actions (10)             -> /api/actions
 10. Business Memories (5)    -> /api/memory

At the end a summary is printed and every entity is verified by re-reading
the GET endpoints.
"""

import json
import random
from datetime import date, datetime, timedelta

import requests

BASE = "http://127.0.0.1:8022"
TIMEOUT = 30
SESSION = requests.Session()

# Deterministic-ish but realistic
random.seed(20260817)

# Track created record IDs so we can reference them later.
created = {
    "contacts": [],          # list of dicts {contact_id, contact_type, first/last}
    "client_contacts": [],   # subset that are clients (for revenue)
    "lead_contacts": [],     # subset that are leads (for opportunities)
    "opportunities": [],
    "revenue": [],
    "referral_sources": [],
    "services": [],
    "lead_sources": [],
    "sales_stages": [],
    "actions": [],
    "memory": [],
    "config": None,
}
errors = []


def post(endpoint, payload):
    """POST JSON and return parsed response. Records errors."""
    url = f"{BASE}{endpoint}"
    try:
        resp = SESSION.post(url, json=payload, timeout=TIMEOUT)
    except requests.RequestException as e:
        errors.append(f"POST {endpoint}: connection error {e}")
        return None
    try:
        data = resp.json()
    except ValueError:
        data = {"raw": resp.text}
    if resp.status_code >= 400:
        errors.append(f"POST {endpoint}: HTTP {resp.status_code} -> {data}")
    return data


def get(endpoint):
    url = f"{BASE}{endpoint}"
    try:
        resp = SESSION.get(url, timeout=TIMEOUT)
        return resp.json()
    except Exception as e:
        errors.append(f"GET {endpoint}: {e}")
        return None


def ok(resp):
    if resp is None:
        return False
    if isinstance(resp, dict):
        return resp.get("status") == "ok" or "id" in resp or "contact_id" in resp or "opp_id" in resp or "record_id" in resp or "source_id" in resp or "memory_id" in resp or "action_id" in resp or "business_name" in resp
    return True


# ---------------------------------------------------------------------------
# Reference data pools
# ---------------------------------------------------------------------------
FIRST_NAMES = [
    "Margaret", "Robert", "Patricia", "James", "Barbara", "William", "Dorothy",
    "Richard", "Helen", "Thomas", "Sandra", "Charles", "Linda", "Joseph",
    "Carol", "Christopher", "Ruth", "Daniel", "Sharon", "Matthew", "Donna",
    "Anthony", "Michelle", "Mark", "Laura", "Steven", "Karen", "Paul",
    "Nancy", "Kenneth", "Betty", "George",
]
LAST_NAMES = [
    "Anderson", "Thompson", "Rodriguez", "Mitchell", "Walker", "Hall",
    "Allen", "Young", "King", "Wright", "Lopez", "Hill", "Scott", "Green",
    "Adams", "Baker", "Nelson", "Carter", "Roberts", "Turner", "Phillips",
    "Campbell", "Parker", "Evans", "Edwards", "Collins", "Stewart", "Morris",
]
CO_CITIES_ZIP = [
    ("Denver", "80202"), ("Colorado Springs", "80903"), ("Aurora", "80010"),
    ("Fort Collins", "80524"), ("Lakewood", "80226"), ("Pueblo", "81003"),
    ("Boulder", "80302"), ("Longmont", "80501"), ("Grand Junction", "81501"),
    ("Greeley", "80631"), ("Westminster", "80030"), ("Arvada", "80002"),
]
LEAD_SOURCES = ["Google Ads", "Facebook", "Referral", "Organic", "LinkedIn", "Partner Referral"]
PIPELINE_STAGES_LEADS = ["new", "contacted", "qualified", "closed_won", "closed_lost"]
MEDICARE_STATUSES = ["Eligible", "Enrolled", "Not Eligible", "Turning 65"]
PRODUCT_TYPES = [
    "Medicare Advantage", "Medicare Supplement", "Life Insurance",
    "Dental Vision Hearing", "Final Expense",
]
PRODUCT_TYPES_FULL = PRODUCT_TYPES + ["Long-Term Care", "Annuities", "ACA Plans"]

NOTES_TEMPLATES = [
    "Interested in reviewing Medicare Advantage options for upcoming AEP.",
    "Referred by existing client; scheduling initial consultation.",
    "Requested comparison between Plan G and Plan N supplements.",
    "Spouse recently enrolled; considering life insurance policy.",
    "Needs dental/vision/hearing coverage to complement Original Medicare.",
    "Looking into final expense policy to cover end-of-life costs.",
    "Turning 65 in a few months; needs initial Medicare enrollment guidance.",
    "Previously declined; follow up for next enrollment period.",
    "Returning call from website inquiry; high intent.",
    "Client since previous AEP; annual review due.",
]

TAGS_POOL = ["AEP", "high-priority", "warm-lead", "rural", "bilingual",
             "senior", "spouse-coverage", "renewal", "cross-sell", "referral"]


def rand_phone():
    return f"({random.randint(303, 720)}) {random.randint(200, 999)}-{random.randint(1000, 9999)}"


def rand_email(first, last, i):
    doms = ["gmail.com", "outlook.com", "yahoo.com", "icloud.com", "hotmail.com"]
    return f"{first.lower()}.{last.lower()}{i}@{random.choice(doms)}"


def rand_tags():
    return ", ".join(random.sample(TAGS_POOL, k=random.randint(1, 3)))


# ---------------------------------------------------------------------------
# 8. Business Config
# ---------------------------------------------------------------------------
def create_business_config():
    payload = {
        "business_name": "[SAMPLE] Rocky Mountain Medicare Solutions",
        "industry": "Medicare & Life Insurance",
        "revenue_goal": 50000,
        "goal_period": "monthly",
        "avg_transaction_value": 850,
        "current_revenue": 12000,
        "setup_complete": 1,
        "setup_completed_at": datetime.now().isoformat(),
    }
    resp = post("/api/business/config", payload)
    created["config"] = resp
    print(f"  business/config -> {resp}")


# ---------------------------------------------------------------------------
# 6. Lead Sources
# ---------------------------------------------------------------------------
def create_lead_sources():
    items = [
        ("Google Ads", "Paid search advertising via Google Ads campaigns"),
        ("Facebook Ads", "Social media advertising on Facebook/Meta platforms"),
        ("Referral", "Referrals from existing clients and word of mouth"),
        ("Organic Search", "Visitors from organic search engine results"),
        ("LinkedIn", "LinkedIn organic and outreach sourced leads"),
        ("Partner Referral", "Referrals from partner agents, CPAs, and advisors"),
    ]
    for i, (name, desc) in enumerate(items):
        resp = post("/api/lead-sources", {"name": name, "description": desc})
        if resp and "error" not in resp:
            created["lead_sources"].append(resp)
        else:
            errors.append(f"lead-source {name}: {resp}")


# ---------------------------------------------------------------------------
# 7. Sales Stages
# ---------------------------------------------------------------------------
def create_sales_stages():
    items = [
        ("new", "New", 0, 0, False, False),
        ("contacted", "Contacted", 20, 1, False, False),
        ("qualified", "Qualified", 40, 2, False, False),
        ("application_submitted", "Application Submitted", 70, 3, False, False),
        ("closed_won", "Closed Won", 100, 4, True, True),
        ("closed_lost", "Closed Lost", 0, 5, True, False),
    ]
    for name, label, prob, order, is_closed, is_won in items:
        resp = post("/api/sales-stages", {
            "name": name, "label": label, "probability": prob,
            "sort_order": order, "is_closed": is_closed, "is_won": is_won,
        })
        if resp and "error" not in resp:
            created["sales_stages"].append(resp)
        else:
            errors.append(f"sales-stage {name}: {resp}")


# ---------------------------------------------------------------------------
# 5. Services
# ---------------------------------------------------------------------------
def create_services():
    items = [
        ("Medicare Advantage", "Part C plans combining hospital, medical, and often drug coverage with extra benefits.", 0),
        ("Medicare Supplement", "Medigap policies (Plans A-N) covering Medicare out-of-pocket costs.", 0),
        ("Life Insurance", "Term and whole life coverage for final expenses and legacy planning.", 0),
        ("Final Expense", "Burial and final expense whole-life policies with simplified underwriting.", 0),
        ("Dental Vision Hearing", "Standalone DVH coverage complementing Medicare.", 0),
        ("Long-Term Care", "Long-term care insurance for nursing, home health, and assisted living.", 0),
        ("Annuities", "Fixed and indexed annuities for retirement income planning.", 0),
        ("ACA Plans", "Affordable Care Act marketplace health plans.", 0),
    ]
    prices = [1850, 1620, 2400, 850, 640, 3000, 2200, 950]
    for i, ((name, desc, _), price) in enumerate(zip(items, prices)):
        resp = post("/api/services", {"name": name, "description": desc, "avg_price": price})
        if resp and "id" in resp:
            created["services"].append(resp)
        else:
            errors.append(f"service {name}: {resp}")


# ---------------------------------------------------------------------------
# 1. Contacts (15 leads + 10 clients)
# ---------------------------------------------------------------------------
def create_contacts():
    today = date.today()

    # --- 15 leads ---
    lead_configs = [
        # (pipeline_stage, medicare_status, lead_source)
        ("new", "Turning 65", "Google Ads"),
        ("new", "Eligible", "Facebook"),
        ("new", "Not Eligible", "Organic"),
        ("contacted", "Eligible", "LinkedIn"),
        ("contacted", "Turning 65", "Google Ads"),
        ("contacted", "Enrolled", "Referral"),
        ("qualified", "Eligible", "Partner Referral"),
        ("qualified", "Turning 65", "Google Ads"),
        ("qualified", "Enrolled", "Facebook"),
        ("qualified", "Eligible", "Organic"),
        ("closed_won", "Enrolled", "Referral"),
        ("closed_won", "Enrolled", "Partner Referral"),
        ("closed_lost", "Not Eligible", "Facebook"),
        ("closed_lost", "Eligible", "LinkedIn"),
        ("closed_lost", "Not Eligible", "Google Ads"),
    ]
    used_emails = set()
    for i, (stage, med_status, source) in enumerate(lead_configs):
        first = f"[SAMPLE] {random.choice(FIRST_NAMES)}"
        last = random.choice(LAST_NAMES)
        email = rand_email(first.replace("[SAMPLE] ", "sample"), last, i)
        # ensure uniqueness
        while email in used_emails:
            email = rand_email(first.replace("[SAMPLE] ", "sample"), last, i)
        used_emails.add(email)
        city, zc = random.choice(CO_CITIES_ZIP)
        payload = {
            "first_name": first,
            "last_name": last,
            "email": email,
            "phone": rand_phone(),
            "contact_type": "lead",
            "lead_source": source,
            "pipeline_stage": stage,
            "medicare_status": med_status,
            "email_consent": random.choice([True, False]),
            "sms_consent": random.choice([True, False]),
            "call_consent": random.choice([True, False]),
            "zip_code": zc,
            "state": "CO",
            "tags": rand_tags(),
            "notes": random.choice(NOTES_TEMPLATES),
            "last_activity": (today - timedelta(days=random.randint(1, 60))).isoformat(),
        }
        resp = post("/api/contacts", payload)
        if resp and resp.get("contact_id"):
            rec = {"contact_id": resp["contact_id"], "contact_type": "lead",
                   "first_name": first, "last_name": last, "pipeline_stage": stage}
            created["contacts"].append(rec)
            created["lead_contacts"].append(rec)
        else:
            errors.append(f"contact lead {first} {last}: {resp}")

    # --- 10 clients ---
    client_configs = [
        ("Medicare Advantage", "Google Ads"),
        ("Medicare Supplement", "Referral"),
        ("Life Insurance", "Partner Referral"),
        ("Dental Vision Hearing", "Organic"),
        ("Final Expense", "Facebook"),
        ("Medicare Advantage", "Partner Referral"),
        ("Medicare Supplement", "Referral"),
        ("Life Insurance", "LinkedIn"),
        ("Final Expense", "Google Ads"),
        ("Medicare Advantage", "Organic"),
    ]
    client_since_dates = [
        "2024-01-15", "2024-03-22", "2024-06-10", "2024-09-05", "2024-11-18",
        "2025-02-14", "2025-05-30", "2025-08-12", "2026-01-20", "2026-04-03",
    ]
    for i, ((product, source), since) in enumerate(zip(client_configs, client_since_dates)):
        first = f"[SAMPLE] {random.choice(FIRST_NAMES)}"
        last = random.choice(LAST_NAMES)
        email = rand_email(first.replace("[SAMPLE] ", "sample"), last, 100 + i)
        while email in used_emails:
            email = rand_email(first.replace("[SAMPLE] ", "sample"), last, 100 + i)
        used_emails.add(email)
        city, zc = random.choice(CO_CITIES_ZIP)
        payload = {
            "first_name": first,
            "last_name": last,
            "email": email,
            "phone": rand_phone(),
            "contact_type": "client",
            "lead_source": source,
            "pipeline_stage": "closed_won",
            "medicare_status": "Enrolled",
            "email_consent": True,
            "sms_consent": random.choice([True, False]),
            "call_consent": True,
            "zip_code": zc,
            "state": "CO",
            "tags": f"client, {product.lower().replace(' ', '-')}, renewal",
            "notes": f"Enrolled in {product}. Annual review around client anniversary. "
                     f"Original source: {source}.",
            "client_since": since,
            "last_activity": (today - timedelta(days=random.randint(1, 30))).isoformat(),
        }
        resp = post("/api/contacts", payload)
        if resp and resp.get("contact_id"):
            rec = {"contact_id": resp["contact_id"], "contact_type": "client",
                   "first_name": first, "last_name": last, "product": product}
            created["contacts"].append(rec)
            created["client_contacts"].append(rec)
        else:
            errors.append(f"contact client {first} {last}: {resp}")


# ---------------------------------------------------------------------------
# 2. Opportunities (10)
# ---------------------------------------------------------------------------
def create_opportunities():
    today = date.today()
    # mix: some closed_won, some closed_lost, most active
    opp_configs = [
        ("Medicare Advantage", "new", "Eligible"),
        ("Medicare Supplement", "contacted", "Eligible"),
        ("Life Insurance", "qualified", "Turning 65"),
        ("Dental Vision Hearing", "application_submitted", "Enrolled"),
        ("Final Expense", "qualified", "Eligible"),
        ("Medicare Advantage", "closed_won", "Enrolled"),
        ("Medicare Supplement", "closed_won", "Enrolled"),
        ("Life Insurance", "closed_lost", "Not Eligible"),
        ("Medicare Advantage", "contacted", "Turning 65"),
        ("Final Expense", "application_submitted", "Turning 65"),
    ]
    # Use leads mostly; for closed_won use a client contact
    for i, (product, stage, med_status) in enumerate(opp_configs):
        if stage in ("closed_won",) and created["client_contacts"]:
            contact = created["client_contacts"][i % len(created["client_contacts"])]
        elif stage == "closed_lost" and created["lead_contacts"]:
            contact = created["lead_contacts"][i % len(created["lead_contacts"])]
        elif created["lead_contacts"]:
            contact = created["lead_contacts"][i % len(created["lead_contacts"])]
        else:
            contact = created["contacts"][i % len(created["contacts"])]
        # expected_close: future dates for active, past for closed
        if stage in ("closed_won", "closed_lost"):
            expected_close = (today - timedelta(days=random.randint(5, 90))).isoformat()
            est_value = random.choice([200, 450, 800, 1200, 2500, 3000])
        else:
            expected_close = (today + timedelta(days=random.randint(10, 120))).isoformat()
            est_value = random.randint(200, 3000)
        created_date = (today - timedelta(days=random.randint(5, 150))).isoformat()
        payload = {
            "contact_id": contact["contact_id"],
            "product_type": product,
            "stage": stage,
            "expected_close": expected_close,
            "estimated_value": est_value,
            "created_date": created_date,
            "stage_history": json.dumps([
                {"stage": "new", "date": created_date, "note": "Opportunity created"}
            ]),
        }
        resp = post("/api/opportunities", payload)
        if resp and resp.get("opp_id"):
            created["opportunities"].append({"opp_id": resp["opp_id"], "stage": stage,
                                             "product_type": product,
                                             "contact_id": contact["contact_id"]})
        else:
            errors.append(f"opportunity {product}/{stage}: {resp}")


# ---------------------------------------------------------------------------
# 4. Revenue Records (15) -- reference client contacts, spread across 2026
# ---------------------------------------------------------------------------
def create_revenue():
    clients = created["client_contacts"]
    if not clients:
        errors.append("revenue: no client contacts available to reference")
        return
    rev_categories = ["commission", "renewal", "bonus"]
    payment_statuses = ["paid", "pending"]
    sources = ["Carrier Direct", "AARP/UnitedHealthcare", "Mutual of Omaha",
               "Humana", "Anthem Blue Cross", "Brokerage Channel"]
    products_for_rev = [c.get("product", random.choice(PRODUCT_TYPES)) for c in clients]
    for i in range(15):
        client = clients[i % len(clients)]
        product = products_for_rev[i % len(products_for_rev)] or random.choice(PRODUCT_TYPES)
        # spread across 2026: Jan - Aug
        month = (i % 8) + 1
        day = random.randint(1, 28)
        rev_date = f"2026-{month:02d}-{day:02d}"
        amount = random.randint(100, 3000)
        payload = {
            "contact_id": client["contact_id"],
            "product_type": product,
            "amount": amount,
            "revenue_date": rev_date,
            "revenue_category": random.choice(rev_categories),
            "payment_status": random.choice(payment_statuses),
            "source": random.choice(sources),
        }
        resp = post("/api/revenue", payload)
        if resp and resp.get("record_id"):
            created["revenue"].append({"record_id": resp["record_id"], "amount": amount,
                                       "product": product, "date": rev_date})
        else:
            errors.append(f"revenue {product}/{rev_date}: {resp}")


# ---------------------------------------------------------------------------
# 3. Referral Sources / Partners (5)
# ---------------------------------------------------------------------------
def create_referral_sources():
    items = [
        # (name, source_type, strength, generated, converted, status)
        ("[SAMPLE] Janet Reyes", "Insurance Agent", 92, 18, 7, "active"),
        ("[SAMPLE] Front Range Financial Group", "Financial Advisor", 78, 12, 5, "active"),
        ("[SAMPLE] Mountain View CPA Firm", "CPA", 85, 9, 4, "active"),
        ("[SAMPLE] David Pruitt Law", "Attorney", 55, 3, 0, "dormant"),
        ("[SAMPLE] Summit Health Partners", "Healthcare Provider", 70, 1, 0, "new"),
    ]
    today = date.today()
    for name, stype, strength, gen, conv, status in items:
        conv_rate = round((conv / gen * 100), 1) if gen else 0.0
        total_rev = random.randint(0, 15000)
        last_ref = (today - timedelta(days=random.randint(5, 120))).isoformat()
        payload = {
            "source_name": name,
            "source_type": stype,
            "contact_info": f"partner@{name.replace('[SAMPLE] ', '').replace(' ', '').lower()}.com",
            "relationship_strength": strength,
            "referrals_generated": gen,
            "referrals_converted": conv,
            "conversion_rate": conv_rate,
            "total_revenue_generated": total_rev,
            "last_referral_date": last_ref,
            "status": status,
        }
        resp = post("/api/referral-sources", payload)
        if resp and resp.get("source_id"):
            created["referral_sources"].append({"source_id": resp["source_id"],
                                                 "source_name": name, "status": status})
        else:
            errors.append(f"referral-source {name}: {resp}")


# ---------------------------------------------------------------------------
# 9. Actions (10)
# ---------------------------------------------------------------------------
def create_actions():
    today = date.today()
    action_configs = [
        # (action_type, title, priority, status, expected_value)
        ("call", "Follow-up call with [SAMPLE] lead about Medicare Advantage", 2, "pending", 1850),
        ("email", "Send enrollment guide to [SAMPLE] Turning 65 prospect", 3, "pending", 0),
        ("meeting", "Schedule AEP consultation with [SAMPLE] couple", 1, "pending", 2400),
        ("document", "Request beneficiary info for [SAMPLE] life insurance app", 4, "pending", 0),
        ("call", "Confirm [SAMPLE] client appointment for Plan G review", 2, "pending", 1620),
        ("email", "Send renewal options to [SAMPLE] existing client", 5, "completed", 850),
        ("meeting", "Quarterly review with [SAMPLE] referral partner agent", 6, "completed", 0),
        ("call", "Re-engage [SAMPLE] dormant lead from Q1", 7, "pending", 1200),
        ("document", "Collect signed application from [SAMPLE] Final Expense lead", 3, "pending", 850),
        ("email", "Thank-you note + referral request to [SAMPLE] new client", 8, "completed", 0),
    ]
    for i, (atype, title, priority, status, exp_val) in enumerate(action_configs):
        due_offset = random.randint(1, 21)
        due_date = (today + timedelta(days=due_offset)).isoformat()
        if status == "completed":
            due_date = (today - timedelta(days=random.randint(1, 10))).isoformat()
        # attach to a contact if available
        if created["contacts"]:
            contact = created["contacts"][i % len(created["contacts"])]
            entity_type = "contact"
            entity_id = contact["contact_id"]
            entity_name = f"{contact['first_name']} {contact['last_name']}"
        else:
            entity_type = entity_id = entity_name = ""
        payload = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_name": entity_name,
            "action_type": atype,
            "title": title,
            "description": f"Action item #{i+1}: {title}. "
                           f"Priority {priority}/10. "
                           f"Type: {atype}. "
                           f"Expected value ${exp_val}.",
            "priority": priority,
            "due_date": due_date,
            "status": status,
            "expected_value": exp_val,
            "source_module": "command_center",
        }
        resp = post("/api/actions", payload)
        if resp and resp.get("action_id"):
            created["actions"].append({"action_id": resp["action_id"], "status": status,
                                       "action_type": atype})
        else:
            errors.append(f"action {title}: {resp}")


# ---------------------------------------------------------------------------
# 10. Business Memories (5)
# ---------------------------------------------------------------------------
def create_memories():
    client_a = created["client_contacts"][0] if created["client_contacts"] else {}
    client_b = created["client_contacts"][1] if len(created["client_contacts"]) > 1 else {}
    ref_a = created["referral_sources"][0] if created["referral_sources"] else {}
    ref_b = created["referral_sources"][1] if len(created["referral_sources"]) > 1 else {}
    lead_a = created["lead_contacts"][0] if created["lead_contacts"] else {}

    items = [
        {
            "entity_type": "contact",
            "entity_id": client_a.get("contact_id", ""),
            "entity_name": f"{client_a.get('first_name','')} {client_a.get('last_name','')}".strip(),
            "memory_text": f"Client prefers afternoon phone calls (after 1pm MT). "
                           f"Allergic to long email chains; keep correspondence brief. "
                           f"Enrolled in {client_a.get('product','Medicare Advantage')}.",
            "memory_category": "client_preference",
            "relevance_score": 85,
        },
        {
            "entity_type": "referral_source",
            "entity_id": ref_a.get("source_id", ""),
            "entity_name": ref_a.get("source_name", ""),
            "memory_text": "Strong referral partner (Insurance Agent). Consistently sends "
                           "5-8 warm leads per quarter. Reward with quarterly lunch and "
                           "co-marketing support. Best contact: email mornings.",
            "memory_category": "partner_relationship",
            "relevance_score": 90,
        },
        {
            "entity_type": "contact",
            "entity_id": client_b.get("contact_id", ""),
            "entity_name": f"{client_b.get('first_name','')} {client_b.get('last_name','')}".strip(),
            "memory_text": f"Client requested SMS reminders only (no marketing emails). "
                           f"Spouse also a prospect for life insurance cross-sell. "
                           f"Renewal month is April.",
            "memory_category": "client_preference",
            "relevance_score": 80,
        },
        {
            "entity_type": "referral_source",
            "entity_id": ref_b.get("source_id", ""),
            "entity_name": ref_b.get("source_name", ""),
            "memory_text": "Financial Advisor partner. Refers affluent clients needing "
                           "Medicare Supplement + annuity bundling. Has gone dormant "
                           "recently; schedule re-engagement meeting Q3.",
            "memory_category": "partner_relationship",
            "relevance_score": 70,
        },
        {
            "entity_type": "contact",
            "entity_id": lead_a.get("contact_id", ""),
            "entity_name": f"{lead_a.get('first_name','')} {lead_a.get('last_name','')}".strip(),
            "memory_text": "Lead is Turning 65 this year. High intent for Medicare "
                           "Advantage during AEP. Budget-conscious; recommend $0 premium "
                           "plans with dental benefits. Follow up weekly.",
            "memory_category": "sales_note",
            "relevance_score": 88,
        },
    ]
    for payload in items:
        resp = post("/api/memory", payload)
        if resp and resp.get("memory_id"):
            created["memory"].append({"memory_id": resp["memory_id"],
                                      "entity_type": payload["entity_type"]})
        else:
            errors.append(f"memory: {resp}")


# ---------------------------------------------------------------------------
# Verification via GET
# ---------------------------------------------------------------------------
def verify():
    print("\n" + "=" * 70)
    print("VERIFICATION (GET endpoints)")
    print("=" * 70)
    checks = [
        ("Business Config", "/api/business/config", lambda d: bool(isinstance(d, dict) and d.get("business_name", "").startswith("[SAMPLE]"))),
        ("Services", "/api/services", lambda d: isinstance(d, list) and len(d) >= 8),
        ("Lead Sources", "/api/lead-sources", lambda d: isinstance(d, list) and len(d) >= 6),
        ("Sales Stages", "/api/sales-stages", lambda d: isinstance(d, list) and len(d) >= 6),
        ("Contacts", "/api/contacts", lambda d: isinstance(d, list) and len(d) >= 25),
        ("Opportunities", "/api/opportunities", lambda d: isinstance(d, list) and len(d) >= 10),
        ("Revenue Records", "/api/revenue", lambda d: isinstance(d, list) and len(d) >= 15),
        ("Referral Sources", "/api/referral-sources", lambda d: isinstance(d, list) and len(d) >= 5),
        ("Actions", "/api/actions", lambda d: isinstance(d, list) and len(d) >= 10),
        ("Business Memory", "/api/memory", lambda d: isinstance(d, list) and len(d) >= 5),
    ]
    all_ok = True
    for label, ep, check in checks:
        data = get(ep)
        count = len(data) if isinstance(data, list) else 1
        passed = check(data)
        all_ok = all_ok and passed
        print(f"  {'PASS' if passed else 'FAIL':4} | {label:18} | GET {ep:24} | count={count}")
    return all_ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("GENERATING TEST DATASET -> http://127.0.0.1:8022")
    print("All person/place names prefixed with [SAMPLE]")
    print("=" * 70)

    print("\n[8] Business Config...")
    create_business_config()

    print("[6] Lead Sources...")
    create_lead_sources()

    print("[7] Sales Stages...")
    create_sales_stages()

    print("[5] Services...")
    create_services()

    print("[1] Contacts (25 = 15 leads + 10 clients)...")
    create_contacts()

    print("[2] Opportunities (10)...")
    create_opportunities()

    print("[4] Revenue Records (15)...")
    create_revenue()

    print("[3] Referral Sources (5)...")
    create_referral_sources()

    print("[9] Actions (10)...")
    create_actions()

    print("[10] Business Memories (5)...")
    create_memories()

    # Summary
    print("\n" + "=" * 70)
    print("CREATION SUMMARY")
    print("=" * 70)
    print(f"  Business Config      : {'OK' if created['config'] else 'FAILED'}")
    print(f"  Lead Sources         : {len(created['lead_sources'])} created")
    print(f"  Sales Stages         : {len(created['sales_stages'])} created")
    print(f"  Services             : {len(created['services'])} created")
    print(f"  Contacts             : {len(created['contacts'])} created "
          f"({len(created['lead_contacts'])} leads + {len(created['client_contacts'])} clients)")
    print(f"  Opportunities        : {len(created['opportunities'])} created")
    print(f"  Revenue Records      : {len(created['revenue'])} created")
    print(f"  Referral Sources     : {len(created['referral_sources'])} created")
    print(f"  Actions              : {len(created['actions'])} created")
    print(f"  Business Memories    : {len(created['memory'])} created")

    if errors:
        print("\n" + "-" * 70)
        print(f"ERRORS/WARNINGS ({len(errors)}):")
        print("-" * 70)
        for e in errors:
            print(f"  - {e}")
    else:
        print("\nNo errors. All records created cleanly.")

    # Verify
    verify_ok = verify()

    # Save a JSON record of what was created
    summary = {
        "generated_at": datetime.now().isoformat(),
        "base_url": BASE,
        "counts": {
            "business_config": 1 if created["config"] else 0,
            "lead_sources": len(created["lead_sources"]),
            "sales_stages": len(created["sales_stages"]),
            "services": len(created["services"]),
            "contacts": len(created["contacts"]),
            "leads": len(created["lead_contacts"]),
            "clients": len(created["client_contacts"]),
            "opportunities": len(created["opportunities"]),
            "revenue_records": len(created["revenue"]),
            "referral_sources": len(created["referral_sources"]),
            "actions": len(created["actions"]),
            "memories": len(created["memory"]),
        },
        "ids": created,
        "errors": errors,
        "verification_passed": verify_ok,
    }
    out_path = "/home/user/workspace/command-center/test_data_summary.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nSummary JSON saved to: {out_path}")

    print("\n" + "=" * 70)
    print(f"DONE. Verification: {'ALL PASSED' if verify_ok else 'SEE FAILURES ABOVE'}")
    print("=" * 70)


if __name__ == "__main__":
    main()
