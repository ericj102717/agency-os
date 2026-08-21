"""
Calendar OAuth Module — Google Calendar + Microsoft Outlook
Handles OAuth 2.0 flows, token storage, and event syncing.
"""
import json
import time
import urllib.parse
import urllib.request
import urllib.parse
import urllib.error

def _http_post(url, data, timeout=15):
    """POST form data and return JSON response."""
    encoded = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=encoded, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            import json as _json
            return _json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        import json as _json
        body = e.read().decode() if e.fp else '{}'
        try:
            return _json.loads(body)
        except Exception:
            return {'error': body or str(e)}

def _http_get(url, headers=None, params=None, timeout=20):
    """GET URL and return JSON response."""
    if params:
        url = url + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method='GET')
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            import json as _json
            return _json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        import json as _json
        body = e.read().decode() if e.fp else '{}'
        try:
            return _json.loads(body)
        except Exception:
            return {'error': body or str(e)}
import db
from db import get_conn

# ---------------------------------------------------------------------------
# Config (from env vars, set in start-published.sh)
# ---------------------------------------------------------------------------

import os

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
MICROSOFT_CLIENT_ID = os.environ.get("MICROSOFT_CLIENT_ID", "")
MICROSOFT_CLIENT_SECRET = os.environ.get("MICROSOFT_CLIENT_SECRET", "")
OAUTH_REDIRECT_BASE = os.environ.get("OAUTH_REDIRECT_BASE", "")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

MICROSOFT_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
MICROSOFT_GRAPH_API = "https://graph.microsoft.com/v1.0"
MICROSOFT_SCOPES = ["Calendars.Read", "User.Read", "offline_access"]
MICROSOFT_USERINFO_URL = "https://graph.microsoft.com/v1.0/me"


def _redirect_base(request):
    """Derive the public redirect base URL from env or request headers."""
    if OAUTH_REDIRECT_BASE:
        return OAUTH_REDIRECT_BASE.rstrip("/")
    # Fallback: derive from request headers
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    if host:
        scheme = "https" if "pplx.app" in host or "perplexity.ai" in host else "http"
        return f"{scheme}://{host}"
    return "http://localhost:5000"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def init_db():
    """Create calendar_connections table if not exists."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS calendar_connections (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                email TEXT,
                access_token TEXT,
                refresh_token TEXT,
                token_expires_at TIMESTAMP,
                calendar_id TEXT,
                connected_at TIMESTAMP DEFAULT (datetime('now')),
                last_synced_at TIMESTAMP,
                metadata_json TEXT
            )
        """)
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_cal_conn_biz_provider
            ON calendar_connections(business_id, provider)
        """)
        conn.commit()
        print("[calendar_oauth] table ready")
    finally:
        db.return_conn(conn)


# ---------------------------------------------------------------------------
# OAuth Start — build authorization URL
# ---------------------------------------------------------------------------

def get_auth_url(provider: str, request) -> str:
    """Return the OAuth authorization URL for the given provider."""
    base = _redirect_base(request)
    redirect_uri = f"{base}/api/calendar/oauth/{provider}/callback"
    state = f"{provider}_{int(time.time())}"

    if provider == "google":
        if not GOOGLE_CLIENT_ID:
            raise ValueError("Google OAuth not configured. Set GOOGLE_CLIENT_ID env var.")
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(GOOGLE_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

    elif provider == "outlook":
        if not MICROSOFT_CLIENT_ID:
            raise ValueError("Microsoft OAuth not configured. Set MICROSOFT_CLIENT_ID env var.")
        params = {
            "client_id": MICROSOFT_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(MICROSOFT_SCOPES),
            "response_mode": "query",
            "state": state,
        }
        return f"{MICROSOFT_AUTH_URL}?{urllib.parse.urlencode(params)}"

    raise ValueError(f"Unknown provider: {provider}")


# ---------------------------------------------------------------------------
# OAuth Callback — exchange code for tokens
# ---------------------------------------------------------------------------

def exchange_code(provider: str, code: str, request) -> dict:
    """Exchange authorization code for access + refresh tokens."""
    base = _redirect_base(request)
    redirect_uri = f"{base}/api/calendar/oauth/{provider}/callback"

    if provider == "google":
        data = {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        tokens = _http_post(GOOGLE_TOKEN_URL, data)
        if "error" in tokens:
            raise ValueError(f"Google token error: {tokens.get('error_description', tokens['error'])}")

        # Get user email
        email = ""
        if "access_token" in tokens:
            ui = _http_get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"})
            if "email" in ui:
                email = ui.get("email", "")

        return {
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "expires_in": tokens.get("expires_in", 3600),
            "email": email,
        }

    elif provider == "outlook":
        data = {
            "client_id": MICROSOFT_CLIENT_ID,
            "client_secret": MICROSOFT_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "scope": " ".join(MICROSOFT_SCOPES),
        }
        tokens = _http_post(MICROSOFT_TOKEN_URL, data)
        if "error" in tokens:
            raise ValueError(f"Microsoft token error: {tokens.get('error_description', tokens['error'])}")

        # Get user email
        email = ""
        if "access_token" in tokens:
            ui = _http_get(MICROSOFT_USERINFO_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"})
            if "mail" in ui or "userPrincipalName" in ui:
                email = ui.get("mail") or ui.get("userPrincipalName", "")

        return {
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "expires_in": tokens.get("expires_in", 3600),
            "email": email,
        }

    raise ValueError(f"Unknown provider: {provider}")


# ---------------------------------------------------------------------------
# Token Storage
# ---------------------------------------------------------------------------

def store_connection(business_id: str, provider: str, tokens: dict) -> dict:
    """Store or update a calendar connection in the database."""
    import uuid
    conn = get_conn()
    try:
        cur = conn.cursor()
        expires_in = tokens.get('expires_in', 3600)

        cur.execute("""
            INSERT INTO calendar_connections (id, business_id, provider, email, access_token, refresh_token, token_expires_at, connected_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now', '+' || ? || ' seconds'), datetime('now'))
            ON CONFLICT(business_id, provider)
            DO UPDATE SET
                email = EXCLUDED.email,
                access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token,
                token_expires_at = EXCLUDED.token_expires_at,
                connected_at = datetime('now')
            RETURNING id, email, connected_at
        """, (
            str(uuid.uuid4()),
            business_id,
            provider,
            tokens.get("email", ""),
            tokens["access_token"],
            tokens.get("refresh_token", ""),
            str(expires_in),
        ))
        row = cur.fetchone()
        conn.commit()
        return {"id": row[0], "email": row[1], "provider": provider}
    finally:
        db.return_conn(conn)


def get_connection(business_id: str, provider: str):
    """Get a calendar connection (or None)."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, provider, email, access_token, refresh_token,
                   token_expires_at, connected_at, last_synced_at
            FROM calendar_connections
            WHERE business_id = ? AND provider = ?
        """, (business_id, provider))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "provider": row[1],
            "email": row[2],
            "access_token": row[3],
            "refresh_token": row[4],
            "token_expires_at": row[5].isoformat() if row[5] else None,
            "connected_at": row[6].isoformat() if row[6] else None,
            "last_synced_at": row[7].isoformat() if row[7] else None,
        }
    finally:
        db.return_conn(conn)


def get_all_connections(business_id: str) -> list:
    """Get all calendar connections for a business."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, provider, email, connected_at, last_synced_at
            FROM calendar_connections
            WHERE business_id = ?
            ORDER BY connected_at DESC
        """, (business_id,))
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "provider": r[1],
                "email": r[2],
                "connected_at": r[3].isoformat() if r[3] else None,
                "last_synced_at": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ]
    finally:
        db.return_conn(conn)


def delete_connection(business_id: str, provider: str) -> bool:
    """Delete a calendar connection."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM calendar_connections
            WHERE business_id = ? AND provider = ?
        """, (business_id, provider))
        conn.commit()
        return cur.rowcount > 0
    finally:
        db.return_conn(conn)


def update_sync_time(business_id: str, provider: str):
    """Update last_synced_at for a connection."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE calendar_connections SET last_synced_at = datetime('now')
            WHERE business_id = ? AND provider = ?
        """, (business_id, provider))
        conn.commit()
    finally:
        db.return_conn(conn)


# ---------------------------------------------------------------------------
# Token Refresh
# ---------------------------------------------------------------------------

def refresh_token_if_needed(business_id: str, provider: str) -> str:
    """Refresh the access token if expired. Returns the current valid access token."""
    conn_data = get_connection(business_id, provider)
    if not conn_data:
        raise ValueError(f"No {provider} connection found")

    # Check if token is still valid (with 5 min buffer)
    expires_at = conn_data.get("token_expires_at")
    if expires_at:
        from datetime import datetime, timezone
        exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if exp > now:
            return conn_data["access_token"]

    refresh_tok = conn_data.get("refresh_token")
    if not refresh_tok:
        raise ValueError(f"No refresh token for {provider}")

    if provider == "google":
        data = {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_tok,
            "grant_type": "refresh_token",
        }
        tokens = _http_post(GOOGLE_TOKEN_URL, data)
        if "access_token" not in tokens:
            raise ValueError(f"Google refresh failed: {tokens.get('error_description', tokens.get('error', 'unknown'))}")

        new_access = tokens["access_token"]
        expires_in = tokens.get("expires_in", 3600)

        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("""
                UPDATE calendar_connections
                SET access_token = ?, token_expires_at = datetime('now', '+' || ? || ' seconds')
                WHERE business_id = ? AND provider = ?
            """, (new_access, str(expires_in), business_id, provider))
            conn.commit()
        finally:
            db.return_conn(conn)
        return new_access

    elif provider == "outlook":
        data = {
            "client_id": MICROSOFT_CLIENT_ID,
            "client_secret": MICROSOFT_CLIENT_SECRET,
            "refresh_token": refresh_tok,
            "grant_type": "refresh_token",
            "scope": " ".join(MICROSOFT_SCOPES),
        }
        tokens = _http_post(MICROSOFT_TOKEN_URL, data)
        if "access_token" not in tokens:
            raise ValueError(f"Microsoft refresh failed: {tokens.get('error_description', tokens.get('error', 'unknown'))}")

        new_access = tokens["access_token"]
        expires_in = tokens.get("expires_in", 3600)
        new_refresh = tokens.get("refresh_token", refresh_tok)

        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("""
                UPDATE calendar_connections
                SET access_token = ?, refresh_token = ?, token_expires_at = datetime('now', '+' || ? || ' seconds')
                WHERE business_id = ? AND provider = ?
            """, (new_access, new_refresh, str(expires_in), business_id, provider))
            conn.commit()
        finally:
            db.return_conn(conn)
        return new_access

    raise ValueError(f"Unknown provider: {provider}")


# ---------------------------------------------------------------------------
# Event Sync
# ---------------------------------------------------------------------------

def sync_google_events(business_id: str) -> dict:
    """Fetch upcoming events from Google Calendar and upsert into mission_calendar_events."""
    import comm_store

    access_token = refresh_token_if_needed(business_id, "google")

    # Fetch events for the next 90 days
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=90)).isoformat()

    data = _http_get(
        f"{GOOGLE_CALENDAR_API}/calendars/primary/events",
        headers={"Authorization": f"Bearer {access_token}"},
        params={
            "timeMin": time_min,
            "timeMax": time_max,
            "maxResults": 50,
            "singleEvents": True,
            "orderBy": "startTime",
        },
    )
    if "error" in data:
        raise ValueError(f"Google Calendar API error: {data['error']}")
    events = data.get("items", [])

    synced = 0
    for ev in events:
        start = ev.get("start", {})
        end = ev.get("end", {})

        # Skip all-day events without times for now (or handle them)
        start_str = start.get("dateTime") or start.get("date")
        end_str = end.get("dateTime") or end.get("date")
        if not start_str:
            continue

        all_day = "date" in start and "dateTime" not in start
        title = ev.get("summary", "Untitled Event")
        location = ev.get("location", "")
        description = ev.get("description", "")
        external_id = ev.get("id", "")

        # Check if we already have this event (by external_id in metadata)
        existing = _find_by_external_id(business_id, external_id)
        if existing:
            # Update
            comm_store.update_calendar_event(existing["id"], {
                "title": title,
                "description": description,
                "location": location,
                "start_at": start_str,
                "end_at": end_str,
                "all_day": all_day,
                "status": "synced",
            })
        else:
            # Create
            comm_store.create_calendar_event(
                business_id=business_id,
                contact_name=None,
                title=title,
                description=description,
                location=location,
                event_type=_infer_event_type(title),
                start_at=start_str,
                end_at=end_str,
                all_day=all_day,
                metadata={"external_id": external_id, "provider": "google", "html_link": ev.get("htmlLink", "")},
            )
        synced += 1

    update_sync_time(business_id, "google")
    return {"provider": "google", "synced": synced, "total_found": len(events)}


def sync_outlook_events(business_id: str) -> dict:
    """Fetch upcoming events from Microsoft Outlook and upsert into mission_calendar_events."""
    import comm_store

    access_token = refresh_token_if_needed(business_id, "outlook")

    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    time_min = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    time_max = (now + timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")

    data = _http_get(
        f"{MICROSOFT_GRAPH_API}/me/calendarview",
        headers={"Authorization": f"Bearer {access_token}"},
        params={
            "startDateTime": time_min,
            "endDateTime": time_max,
            "$top": 50,
            "$select": "id,subject,bodyPreview,location,start,end,isAllDay,webLink",
        },
    )
    if "error" in data:
        raise ValueError(f"Microsoft Graph API error: {data['error']}")
    events = data.get("value", [])

    synced = 0
    for ev in events:
        start_obj = ev.get("start", {})
        end_obj = ev.get("end", {})
        start_str = start_obj.get("dateTime")
        end_str = end_obj.get("dateTime")
        if not start_str:
            continue

        all_day = ev.get("isAllDay", False)
        title = ev.get("subject", "Untitled Event")
        location_obj = ev.get("location", {})
        location = location_obj.get("displayName", "") if location_obj else ""
        description = ev.get("bodyPreview", "")
        external_id = ev.get("id", "")

        # Add timezone offset if missing (Microsoft returns naive datetime)
        if all_day:
            start_str = f"{start_str}T00:00:00"
            end_str = f"{end_str}T00:00:00"

        existing = _find_by_external_id(business_id, external_id)
        if existing:
            comm_store.update_calendar_event(existing["id"], {
                "title": title,
                "description": description,
                "location": location,
                "start_at": start_str,
                "end_at": end_str,
                "all_day": all_day,
                "status": "synced",
            })
        else:
            comm_store.create_calendar_event(
                business_id=business_id,
                contact_name=None,
                title=title,
                description=description,
                location=location,
                event_type=_infer_event_type(title),
                start_at=start_str,
                end_at=end_str,
                all_day=all_day,
                metadata={"external_id": external_id, "provider": "outlook", "web_link": ev.get("webLink", "")},
            )
        synced += 1

    update_sync_time(business_id, "outlook")
    return {"provider": "outlook", "synced": synced, "total_found": len(events)}


def _find_by_external_id(business_id: str, external_id: str):
    """Find a calendar event by its external_id in metadata_json."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id FROM mission_calendar_events
            WHERE business_id = ? AND metadata_json LIKE ?
        """, (business_id, f'%{external_id}%'))
        row = cur.fetchone()
        if row:
            return {"id": row[0]}
        return None
    finally:
        db.return_conn(conn)


def _infer_event_type(title: str) -> str:
    """Guess event type from title."""
    title_lower = title.lower()
    if "estimate" in title_lower:
        return "estimate"
    if "follow" in title_lower or "follow-up" in title_lower:
        return "follow_up"
    if "call" in title_lower:
        return "call"
    if "meeting" in title_lower or "consult" in title_lower:
        return "meeting"
    return "appointment"


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def get_status(business_id: str) -> dict:
    """Get connection status for all providers."""
    connections = get_all_connections(business_id)
    conn_map = {c["provider"]: c for c in connections}

    return {
        "google": {
            "configured": bool(GOOGLE_CLIENT_ID),
            "connected": "google" in conn_map,
            "email": conn_map.get("google", {}).get("email", ""),
            "connected_at": conn_map.get("google", {}).get("connected_at", ""),
            "last_synced_at": conn_map.get("google", {}).get("last_synced_at", ""),
        },
        "outlook": {
            "configured": bool(MICROSOFT_CLIENT_ID),
            "connected": "outlook" in conn_map,
            "email": conn_map.get("outlook", {}).get("email", ""),
            "connected_at": conn_map.get("outlook", {}).get("connected_at", ""),
            "last_synced_at": conn_map.get("outlook", {}).get("last_synced_at", ""),
        },
    }
