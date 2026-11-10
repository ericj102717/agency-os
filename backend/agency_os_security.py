"""Authenticated, tenant-scoped API surface for Operiq Agency OS.

This module is deliberately additive: legacy endpoints keep their existing behavior,
while all /api/agency-os routes require a valid Supabase access token and an active
agency membership. The service database connection is always paired with explicit
agency predicates; never trust agency_id or user_id supplied by a browser as identity.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix="/api/agency-os", tags=["Agency OS secure tenant API"])


class ContactCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(default="", max_length=120)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    organization_name: str | None = Field(default=None, max_length=200)
    preferred_contact_method: str | None = None
    source: str | None = Field(default=None, max_length=120)

    @field_validator("first_name")
    @classmethod
    def first_name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("first_name cannot be blank")
        return value

    @field_validator("preferred_contact_method")
    @classmethod
    def valid_contact_method(cls, value: str | None) -> str | None:
        allowed = {"email", "phone", "sms", "mail", "none"}
        if value is not None and value not in allowed:
            raise ValueError("Invalid preferred_contact_method")
        return value


def _auth_config() -> tuple[str, str]:
    base_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    anon_key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not base_url or not anon_key:
        raise HTTPException(status_code=503, detail="Supabase authentication is not configured")
    return base_url, anon_key


def verify_supabase_access_token(authorization: str | None) -> dict[str, str]:
    """Validate bearer token with Supabase Auth; never decode an unverified JWT."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer access token required")
    token = authorization[7:].strip()
    if not token or len(token) > 8192:
        raise HTTPException(status_code=401, detail="Invalid access token")
    base_url, anon_key = _auth_config()
    request = urllib.request.Request(
        f"{base_url}/auth/v1/user",
        headers={"Authorization": f"Bearer {token}", "apikey": anon_key, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 401, 403):
            raise HTTPException(status_code=401, detail="Invalid or expired access token") from exc
        raise HTTPException(status_code=503, detail="Authentication provider unavailable") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Authentication provider unavailable") from exc

    user_id = payload.get("id")
    if not isinstance(user_id, str):
        raise HTTPException(status_code=401, detail="Authentication provider returned no user identity")
    try:
        UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid user identity") from exc
    return {"id": user_id, "email": str(payload.get("email") or "")}


def current_user(authorization: str | None = Header(default=None, alias="Authorization")) -> dict[str, str]:
    return verify_supabase_access_token(authorization)


def _database_connection():
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise HTTPException(status_code=503, detail="Agency OS PostgreSQL database is not configured")
    try:
        return psycopg2.connect(database_url, connect_timeout=8, cursor_factory=RealDictCursor)
    except psycopg2.Error as exc:
        raise HTTPException(status_code=503, detail="Agency OS database unavailable") from exc


def require_agency_membership(agency_id: UUID, user: dict[str, str], *, write: bool = False) -> dict[str, Any]:
    """Resolve membership from the database; never accept role/tenant claims from request data."""
    connection = _database_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """select m.agency_id, m.user_id, m.role, m.status, w.name as agency_name
                       from public.agency_memberships m
                       join public.agency_workspaces w on w.id = m.agency_id
                       where m.agency_id = %s and m.user_id = %s and m.status = 'active'
                         and w.status = 'active'""",
                    (str(agency_id), user["id"]),
                )
                membership = cursor.fetchone()
        if not membership:
            raise HTTPException(status_code=404, detail="Agency not found")
        if write and membership["role"] == "read_only":
            raise HTTPException(status_code=403, detail="Read-only membership cannot modify agency data")
        return dict(membership)
    finally:
        connection.close()


def _agency_access(agency_id: UUID, user: dict[str, str] = Depends(current_user)) -> dict[str, Any]:
    return require_agency_membership(agency_id, user)


@router.get("/me/agencies")
def list_my_agencies(user: dict[str, str] = Depends(current_user)):
    """List only active workspaces for the authenticated user."""
    connection = _database_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """select w.id, w.name, w.slug, w.industry, w.timezone, w.currency_code,
                              m.role, m.status
                       from public.agency_memberships m
                       join public.agency_workspaces w on w.id = m.agency_id
                       where m.user_id = %s and m.status = 'active' and w.status = 'active'
                       order by w.name""",
                    (user["id"],),
                )
                agencies = [dict(row) for row in cursor.fetchall()]
        return {"agencies": agencies}
    finally:
        connection.close()


@router.get("/{agency_id}/contacts")
def list_contacts(agency_id: UUID, membership: dict[str, Any] = Depends(_agency_access)):
    connection = _database_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """select id, first_name, last_name, display_name, email, phone,
                              organization_name, lifecycle_status, source, created_at, updated_at
                       from public.agency_contacts
                       where agency_id = %s
                       order by created_at desc
                       limit 250""",
                    (str(membership["agency_id"]),),
                )
                contacts = [dict(row) for row in cursor.fetchall()]
        return {"contacts": contacts, "agency_id": str(membership["agency_id"])}
    finally:
        connection.close()


@router.post("/{agency_id}/contacts", status_code=201)
def create_contact(
    agency_id: UUID,
    payload: ContactCreate,
    user: dict[str, str] = Depends(current_user),
):
    membership = require_agency_membership(agency_id, user, write=True)
    connection = _database_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """insert into public.agency_contacts
                       (agency_id, first_name, last_name, email, phone, organization_name,
                        preferred_contact_method, source, created_by)
                       values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                       returning id, agency_id, first_name, last_name, display_name, email,
                                 phone, organization_name, lifecycle_status, source, created_at""",
                    (str(membership["agency_id"]), payload.first_name, payload.last_name,
                     payload.email, payload.phone, payload.organization_name,
                     payload.preferred_contact_method, payload.source, user["id"]),
                )
                contact = dict(cursor.fetchone())
                cursor.execute(
                    """insert into public.agency_audit_events
                       (agency_id, actor_user_id, event_type, entity_type, entity_id, after_data)
                       values (%s, %s, 'contact.created', 'contact', %s, %s::jsonb)""",
                    (str(membership["agency_id"]), user["id"], str(contact["id"]),
                     json.dumps({"first_name": contact["first_name"], "last_name": contact["last_name"]})),
                )
        return {"contact": contact}
    except psycopg2.Error as exc:
        raise HTTPException(status_code=400, detail="Unable to create contact") from exc
    finally:
        connection.close()
