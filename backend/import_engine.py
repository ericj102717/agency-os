#!/usr/bin/env python3
"""
Import Engine
=============
Field definitions, auto-mapping, validation, duplicate detection,
and chunked commit for the Data Import Wizard.

DRAFT -- owner approval required.
"""

import json
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import data_store

DRAFT_DISCLAIMER = "DRAFT -- owner approval required."

# ---------------------------------------------------------------------------
# Import Schemas — canonical field definitions for each data type
# ---------------------------------------------------------------------------

IMPORT_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "contacts": {
        "label": "Contacts (Leads, Clients, Prospects)",
        "table": "contacts",
        "required": ["first_name", "contact_type"],
        "recommended": ["last_name", "email", "phone", "lead_source", "pipeline_stage", "medicare_status"],
        "fields": {
            "contact_id":      {"label": "Contact ID", "aliases": ["contact id", "contactid", "id", "customer id", "customerid"]},
            "first_name":      {"label": "First Name", "aliases": ["first name", "firstname", "fname", "given name", "givenname"]},
            "last_name":       {"label": "Last Name", "aliases": ["last name", "lastname", "lname", "surname", "family name"]},
            "email":           {"label": "Email", "aliases": ["email", "email address", "emailaddress", "e-mail"]},
            "phone":           {"label": "Phone", "aliases": ["phone", "phone number", "phonenumber", "mobile", "cell", "cell phone", "telephone"]},
            "date_of_birth":   {"label": "Date of Birth", "aliases": ["date of birth", "dob", "birthday", "birth date"]},
            "contact_type":    {"label": "Contact Type", "aliases": ["contact type", "contacttype", "type", "record type", "recordtype"], "type": "enum", "options": ["lead", "prospect", "client"]},
            "lead_source":     {"label": "Lead Source", "aliases": ["lead source", "leadsource", "source", "referral source"]},
            "pipeline_stage":  {"label": "Pipeline Stage", "aliases": ["pipeline stage", "pipelinestage", "stage", "status"], "type": "enum", "options": ["new", "contacted", "qualified", "consultation_scheduled", "application_started", "closed_won", "closed_lost"]},
            "medicare_status": {"label": "Medicare Status", "aliases": ["medicare status", "medicarestatus", "medicare", "eligibility"], "type": "enum", "options": ["approaching_65", "eligible", "enrolled_A", "enrolled_B", "enrolled_AB", "enrolled_MA", "enrolled_part_d", "enrolled_supplement", "not_eligible"]},
            "email_consent":   {"label": "Email Consent", "aliases": ["email consent", "emailconsent", "email opt in", "email_opt_in", "can email"], "type": "boolean"},
            "sms_consent":     {"label": "SMS Consent", "aliases": ["sms consent", "smsconsent", "sms opt in", "sms_opt_in", "text consent", "can text"], "type": "boolean"},
            "call_consent":    {"label": "Call Consent", "aliases": ["call consent", "callconsent", "call opt in", "call_opt_in", "can call", "tcpa consent"], "type": "boolean"},
            "last_activity":   {"label": "Last Activity Date", "aliases": ["last activity", "lastactivity", "last contact", "lastcontactdate", "last touch"]},
            "client_since":    {"label": "Client Since", "aliases": ["client since", "clientsince", "start date", "onboarding date"]},
            "zip_code":        {"label": "Zip Code", "aliases": ["zip", "zip code", "zipcode", "postal code", "postalcode", "zip code"]},
            "state":           {"label": "State", "aliases": ["state", "st"]},
            "tags":            {"label": "Tags", "aliases": ["tags", "label", "labels", "segment"]},
        },
    },
    "opportunities": {
        "label": "Opportunities (Pipeline Deals)",
        "table": "opportunities",
        "required": ["product_type"],
        "recommended": ["contact_id", "stage", "estimated_value", "expected_close"],
        "fields": {
            "opp_id":          {"label": "Opportunity ID", "aliases": ["opp id", "oppid", "opportunity id", "opportunityid", "deal id", "dealid"]},
            "contact_id":      {"label": "Contact ID", "aliases": ["contact id", "contactid", "customer id", "customerid"]},
            "product_type":    {"label": "Product Type", "aliases": ["product type", "producttype", "product", "plan type", "plantype"], "type": "enum", "options": ["medicare_advantage", "medigap", "medicare_part_d", "life_term", "life_whole", "life_universal", "annuity", "other"]},
            "stage":           {"label": "Stage", "aliases": ["stage", "pipeline stage", "pipelinestage", "status"], "type": "enum", "options": ["new", "contacted", "qualified", "consultation_scheduled", "application_started", "closed_won", "closed_lost"]},
            "entered_stage":   {"label": "Entered Stage Date", "aliases": ["entered stage", "enteredstage", "stage date"]},
            "expected_close":  {"label": "Expected Close Date", "aliases": ["expected close", "expectedclose", "close date", "closedate", "expected close date"]},
            "estimated_value": {"label": "Estimated Value", "aliases": ["estimated value", "estimatedvalue", "value", "amount", "deal value", "commission"], "type": "number"},
            "created_date":    {"label": "Created Date", "aliases": ["created date", "createddate", "created", "start date"]},
        },
    },
    "revenue": {
        "label": "Revenue Records",
        "table": "revenue_records",
        "required": ["amount"],
        "recommended": ["contact_id", "product_type", "revenue_date"],
        "fields": {
            "record_id":         {"label": "Record ID", "aliases": ["record id", "recordid", "transaction id", "transactionid"]},
            "contact_id":         {"label": "Contact ID", "aliases": ["contact id", "contactid", "customer id", "customerid"]},
            "product_type":       {"label": "Product Type", "aliases": ["product type", "producttype", "product", "plan type"]},
            "amount":             {"label": "Amount", "aliases": ["amount", "revenue", "commission", "payment", "value", "price"], "type": "number"},
            "revenue_date":       {"label": "Revenue Date", "aliases": ["revenue date", "revenuedate", "date", "payment date", "paymentdate"]},
            "revenue_category":   {"label": "Category", "aliases": ["category", "revenue category", "revenuecategory", "type"], "type": "enum", "options": ["commission", "renewal", "bonus", "override", "referral_fee", "other"]},
            "payment_status":     {"label": "Payment Status", "aliases": ["payment status", "paymentstatus", "status"], "type": "enum", "options": ["received", "pending", "delayed", "cancelled"]},
            "source":             {"label": "Source", "aliases": ["source", "carrier", "company", "payer"]},
        },
    },
    "referrals": {
        "label": "Referral Sources",
        "table": "referral_sources",
        "required": ["source_name"],
        "recommended": ["source_type", "relationship_strength", "referrals_generated"],
        "fields": {
            "source_id":              {"label": "Source ID", "aliases": ["source id", "sourceid", "referral id", "referralid"]},
            "source_name":            {"label": "Source Name", "aliases": ["source name", "sourcename", "name", "partner name", "partnername", "referral source"]},
            "source_type":            {"label": "Source Type", "aliases": ["source type", "sourcetype", "type"], "type": "enum", "options": ["client", "agent", "partner", "organization", "event", "online"]},
            "contact_info":           {"label": "Contact Info", "aliases": ["contact info", "contactinfo", "email", "phone", "contact"]},
            "relationship_strength":  {"label": "Relationship Strength (0-100)", "aliases": ["relationship strength", "relationshipstrength", "strength", "relationship score"], "type": "number"},
            "referrals_generated":     {"label": "Referrals Generated", "aliases": ["referrals generated", "referralsgenerated", "total referrals", "referrals sent"], "type": "number"},
            "referrals_converted":     {"label": "Referrals Converted", "aliases": ["referrals converted", "referralsconverted", "conversions", "converted"], "type": "number"},
            "conversion_rate":         {"label": "Conversion Rate", "aliases": ["conversion rate", "conversionrate", "close rate"], "type": "number"},
            "total_revenue_generated": {"label": "Total Revenue Generated", "aliases": ["total revenue", "totalrevenue", "revenue generated", "revenuegenerated"], "type": "number"},
            "last_referral_date":      {"label": "Last Referral Date", "aliases": ["last referral date", "lastreferraldate", "last referral"]},
            "status":                  {"label": "Status", "aliases": ["status", "active status"], "type": "enum", "options": ["active", "inactive", "dormant"]},
        },
    },
}

# ---------------------------------------------------------------------------
# Auto-mapping: match CSV headers to canonical fields
# ---------------------------------------------------------------------------

def auto_map_headers(headers: List[str], data_type: str) -> Dict[str, str]:
    """Map CSV column headers to canonical field names.
    Returns {csv_header: canonical_field}."""
    schema = IMPORT_SCHEMAS.get(data_type, {})
    field_defs = schema.get("fields", {})
    mapping = {}

    # Build lookup: lowercase alias -> canonical field
    alias_lookup = {}
    for canonical, fdef in field_defs.items():
        alias_lookup[canonical.lower()] = canonical
        for alias in fdef.get("aliases", []):
            alias_lookup[alias.lower()] = canonical

    for header in headers:
        if not header:
            mapping[header] = ""
            continue
        header_lower = header.strip().lower().replace("_", " ").replace("-", " ")
        # Try exact match
        if header_lower in alias_lookup:
            mapping[header] = alias_lookup[header_lower]
            continue
        # Try without spaces
        header_nospace = header_lower.replace(" ", "")
        for alias, canonical in alias_lookup.items():
            if alias.replace(" ", "") == header_nospace:
                mapping[header] = canonical
                break
        else:
            # Try partial match
            for alias, canonical in alias_lookup.items():
                if alias in header_lower or header_lower in alias:
                    mapping[header] = canonical
                    break
            else:
                mapping[header] = ""  # unmapped

    return mapping

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def parse_boolean(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    s = str(val).strip().lower()
    return s in ("true", "yes", "y", "1", "t", "checked", "opted in", "opt_in", "consented")

def parse_number(val: Any) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace("$", "").replace(",", "").replace("%", "")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0

def validate_row(row: Dict[str, Any], data_type: str, row_number: int) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    """Validate and normalize a single row.
    Returns (normalized_row, issues_list)."""
    schema = IMPORT_SCHEMAS.get(data_type, {})
    field_defs = schema.get("fields", {})
    required = schema.get("required", [])
    issues = []
    normalized = {}

    for canonical, value in row.items():
        fdef = field_defs.get(canonical, {})
        ftype = fdef.get("type", "string")

        if value is None or str(value).strip() == "":
            normalized[canonical] = ""
            continue

        if ftype == "boolean":
            normalized[canonical] = parse_boolean(value)
        elif ftype == "number":
            num = parse_number(value)
            normalized[canonical] = num
            if num == 0 and str(value).strip() not in ("0", "0.0", "$0", "$0.00", ""):
                issues.append({"row": row_number, "field": canonical, "type": "warning",
                               "message": f"Could not parse number: '{value}' -- defaulted to 0"})
        elif ftype == "enum":
            val_lower = str(value).strip().lower().replace(" ", "_").replace("-", "_")
            options = fdef.get("options", [])
            # Case-insensitive match
            matched = None
            for opt in options:
                if opt.lower() == val_lower:
                    matched = opt
                    break
            if matched:
                normalized[canonical] = matched
            else:
                # Try partial match
                for opt in options:
                    if opt.lower() in val_lower or val_lower in opt.lower():
                        matched = opt
                        break
                if matched:
                    normalized[canonical] = matched
                else:
                    normalized[canonical] = str(value).strip()
                    issues.append({"row": row_number, "field": canonical, "type": "warning",
                                   "message": f"Unknown value '{value}' for {fdef.get('label', canonical)}. Valid: {', '.join(options[:5])}"})
        else:
            normalized[canonical] = str(value).strip()

    # Check required fields
    for req in required:
        val = normalized.get(req, "")
        if not val or (isinstance(val, str) and not val.strip()):
            fdef = field_defs.get(req, {})
            issues.append({"row": row_number, "field": req, "type": "error",
                           "message": f"Required field missing: {fdef.get('label', req)}"})

    # TCPA compliance: warn about missing consent
    if data_type == "contacts":
        for consent_field in ["email_consent", "sms_consent", "call_consent"]:
            if consent_field not in row or row.get(consent_field, "") == "":
                fdef = field_defs.get(consent_field, {})
                issues.append({"row": row_number, "field": consent_field, "type": "warning",
                               "message": f"Missing {fdef.get('label', consent_field)} -- defaulted to false. TCPA requires explicit consent for outreach."})
                normalized[consent_field] = False

    return normalized, issues

# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def check_duplicate(row: Dict[str, Any], data_type: str) -> Optional[Dict[str, Any]]:
    """Check if a row duplicates existing data."""
    if data_type == "contacts":
        return data_store.check_contact_duplicate(row)
    elif data_type == "opportunities":
        return data_store.check_opp_duplicate(row)
    # Revenue and referrals: check by ID
    elif data_type == "revenue":
        record_id = row.get("record_id", "")
        if record_id:
            conn = data_store.get_conn()
            existing = conn.execute("SELECT * FROM revenue_records WHERE record_id = ?", (record_id,)).fetchone()
            return dict(existing) if existing else None
    elif data_type == "referrals":
        source_id = row.get("source_id", "")
        if source_id:
            conn = data_store.get_conn()
            existing = conn.execute("SELECT * FROM referral_sources WHERE source_id = ?", (source_id,)).fetchone()
            return dict(existing) if existing else None
    return None

# ---------------------------------------------------------------------------
# Preview: validate all rows without committing
# ---------------------------------------------------------------------------

def preview_import(rows: List[Dict[str, Any]], data_type: str, field_mapping: Dict[str, str]) -> Dict[str, Any]:
    """Validate rows and return a preview summary.
    rows: list of {csv_header: value} dicts
    field_mapping: {csv_header: canonical_field}
    """
    # Remap rows using field mapping
    remapped_rows = []
    for row in rows:
        remapped = {}
        for csv_header, value in row.items():
            canonical = field_mapping.get(csv_header, "")
            if canonical:
                remapped[canonical] = value
        remapped_rows.append(remapped)

    valid_rows = []
    invalid_rows = []
    duplicate_rows = []
    all_issues = []
    warnings = []

    for i, row in enumerate(remapped_rows):
        row_number = i + 2  # +2 because row 1 is header
        normalized, issues = validate_row(row, data_type, row_number)

        has_error = any(iss["type"] == "error" for iss in issues)
        has_warning = any(iss["type"] == "warning" for iss in issues)

        if has_error:
            invalid_rows.append({"row": row_number, "data": row, "issues": issues})
        else:
            # Check for duplicates
            dup = check_duplicate(normalized, data_type)
            if dup:
                duplicate_rows.append({"row": row_number, "data": normalized, "existing": dup})
            else:
                valid_rows.append(normalized)

        all_issues.extend(issues)
        if has_warning:
            warnings.extend([iss for iss in issues if iss["type"] == "warning"])

    return {
        "data_type": data_type,
        "total_rows": len(rows),
        "valid_rows": len(valid_rows),
        "invalid_rows": len(invalid_rows),
        "duplicate_rows": len(duplicate_rows),
        "warning_count": len(warnings),
        "issues": all_issues[:50],
        "preview_valid": valid_rows[:5],
        "preview_invalid": invalid_rows[:5],
        "preview_duplicates": duplicate_rows[:5],
    }

# ---------------------------------------------------------------------------
# Commit: insert validated rows in chunks
# ---------------------------------------------------------------------------

def commit_chunk(rows: List[Dict[str, Any]], data_type: str, batch_id: str, is_sample: bool = False) -> Dict[str, Any]:
    """Commit a chunk of validated rows to the database."""
    inserted = 0
    errors = 0
    duplicates = 0

    for row in rows:
        if data_type == "contacts":
            ok, err = data_store.insert_contact(row, batch_id, is_sample)
        elif data_type == "opportunities":
            ok, err = data_store.insert_opportunity(row, batch_id, is_sample)
        elif data_type == "revenue":
            ok, err = data_store.insert_revenue(row, batch_id, is_sample)
        elif data_type == "referrals":
            ok, err = data_store.insert_referral_source(row, batch_id, is_sample)
        else:
            ok, err = False, "Unknown data type"

        if ok:
            inserted += 1
        elif err and "Duplicate" in str(err):
            duplicates += 1
        else:
            errors += 1
            data_store.add_issue(batch_id, 0, "", "error", f"Insert failed: {err}", json.dumps(row, default=str))

    return {
        "batch_id": batch_id,
        "chunk_size": len(rows),
        "inserted": inserted,
        "duplicates": duplicates,
        "errors": errors,
    }

def start_batch(data_type: str, filename: str, total_rows: int, field_mapping: Dict[str, str]) -> str:
    """Create an import batch and return the batch_id."""
    batch_id = f"imp-{uuid.uuid4().hex[:12]}"
    data_store.create_batch(batch_id, data_type, filename, total_rows, field_mapping)
    return batch_id

def complete_batch(batch_id: str):
    """Mark a batch as completed."""
    data_store.update_batch(batch_id, status="completed")

def get_batch_status(batch_id: str) -> Optional[Dict[str, Any]]:
    """Get the status of an import batch."""
    batch = data_store.get_batch(batch_id)
    if not batch:
        return None
    issues = data_store.get_issues(batch_id, limit=20)
    batch["recent_issues"] = issues
    return batch
