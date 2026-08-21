#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

echo "=== STARTUP LOG ==="
echo "PWD: $(pwd)"
echo "Node: $(node --version 2>&1 || echo 'not found')"
echo "Python: $(python --version 2>&1 || echo 'not found')"
echo "Python3: $(python3 --version 2>&1 || echo 'not found')"

# Ensure python is available
if command -v python >/dev/null 2>&1; then
  PY=python
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  echo "ERROR: No python found"; exit 1
fi

# Generate a random API key for this session (backend auth, never exposed to client)
export AGENCY_API_KEY=${AGENCY_API_KEY:-$($PY -c "import secrets; print(secrets.token_hex(32))")}

# Write key for mutations — uses a stable default so the user can save changes
# without checking server logs. Override with AGENCY_WRITE_KEY env var if needed.
export AGENCY_WRITE_KEY=${AGENCY_WRITE_KEY:-"nMHKbJCRkpTgHyqEy0acrakD1hDWOe3p6yd6QKEOxLU"}

echo "========================================"
echo "Agency OS Command Center"
echo "========================================"
echo "Write key for mutations: $AGENCY_WRITE_KEY"
echo "(Enter this key in the app when prompted to save changes)"
echo "========================================"

# --- Supabase/Postgres connection ---
SUPABASE_PROJECT="jpeavskedjffubzojdmu"

if [ -n "${CUSTOM_CRED_DB_JPEAVSKEDJFFUBZOJDMU_SUPABASE_CO_TOKEN:-}" ]; then
  DB_PASS="$CUSTOM_CRED_DB_JPEAVSKEDJFFUBZOJDMU_SUPABASE_CO_TOKEN"
  export DATABASE_URL="postgresql://postgres.${SUPABASE_PROJECT}:${DB_PASS}@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
  echo "DATABASE_URL set from credential env var (Supabase pooler)"
elif [ -n "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL already set in environment"
else
  echo "No DATABASE_URL or Supabase credential found — using SQLite fallback"
fi

# Install Python dependencies (E2B sandbox may not have them)
echo "Installing Python dependencies..."
pip install -r backend/requirements.txt 2>&1 || pip3 install -r backend/requirements.txt 2>&1 || {
  echo "ERROR: Failed to install Python dependencies"; exit 1;
}

# Install psycopg2 if using Postgres
if [ -n "${DATABASE_URL:-}" ]; then
  pip install psycopg2-binary -q 2>/dev/null || true

  echo "Initializing Postgres schema..."
  (cd backend && $PY -c "import db; db.init_db()" 2>&1 || echo "Schema init warning (may be expected)")

  echo "Checking for data migration..."
  (cd backend && $PY migrate_to_postgres.py 2>&1 || echo "Migration skipped")
fi

# Verify dist/index.cjs exists
echo "Checking dist/index.cjs..."
ls -la dist/index.cjs || { echo "ERROR: dist/index.cjs not found"; exit 1; }

# Verify backend/server.py exists
echo "Checking backend/server.py..."
ls -la backend/server.py || { echo "ERROR: backend/server.py not found"; exit 1; }

# Start FastAPI backend on port 8088 with logging
echo "Starting FastAPI on port 8088..."
(cd backend && PORT=8088 HOST=127.0.0.1 AGENCY_API_KEY="$AGENCY_API_KEY" ${DATABASE_URL:+DATABASE_URL="$DATABASE_URL"} $PY server.py) > /tmp/fastapi.log 2>&1 &
FASTAPI_PID=$!

trap 'kill $FASTAPI_PID 2>/dev/null || true' EXIT

# Wait for FastAPI to be ready
FASTAPI_READY=0
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:8088/api/summary?x_api_key=$AGENCY_API_KEY" >/dev/null 2>&1; then
    FASTAPI_READY=1
    echo "FastAPI ready"
    break
  fi
  sleep 1
done

if [ "$FASTAPI_READY" != "1" ]; then
  echo "=== FASTAPI FAILED TO START ==="
  echo "=== FastAPI logs: ==="
  cat /tmp/fastapi.log 2>&1 || true
  echo "=== Processes: ==="
  ps aux 2>&1 || true
  echo "=== Continuing to Express anyway (API will be broken) ==="
fi

# Start Express server (serves static + proxies /api/* to FastAPI)
# AGENCY_WRITE_KEY is passed so Express can validate client-supplied write keys
echo "Starting Express on port 5000..."
NODE_ENV=production \
  AGENCY_API_KEY="$AGENCY_API_KEY" \
  AGENCY_WRITE_KEY="$AGENCY_WRITE_KEY" \
  ${DATABASE_URL:+DATABASE_URL="$DATABASE_URL"} \
  node dist/index.cjs
