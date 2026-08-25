#!/usr/bin/env bash
# Start Express immediately, then bootstrap FastAPI in the background.
# Express returns 502 for API calls until FastAPI is ready (~10-15s).

cd "$(dirname "$0")/.."

# Ensure python is available
if command -v python >/dev/null 2>&1; then
  PY=python
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  echo "ERROR: No python found"; exit 1
fi

# Generate API keys
export AGENCY_API_KEY=${AGENCY_API_KEY:-$($PY -c "import secrets; print(secrets.token_hex(32))")}
export AGENCY_WRITE_KEY=${AGENCY_WRITE_KEY:-"nMHKbJCRkpTgHyqEy0acrakD1hDWOe3p6yd6QKEOxLU"}

# Set DATABASE_URL (Supabase pooler)
SUPABASE_PROJECT="jpeavskedjffubzojdmu"
SUPABASE_PASS="Uo7HUK00Eaju4YJ7"
export DATABASE_URL="postgresql://postgres.${SUPABASE_PROJECT}:${SUPABASE_PASS}@aws-0-us-west-2.pooler.supabase.com:6543/postgres"

# Bootstrap FastAPI in the background
bootstrap_fastapi() {
  # Install deps only if needed
  $PY -c "import fastapi" 2>/dev/null || {
    echo "[bootstrap] Installing Python deps..."
    pip install -r backend/requirements.txt 2>&1 || pip3 install -r backend/requirements.txt 2>&1 || true
  }
  $PY -c "import psycopg2" 2>/dev/null || pip install psycopg2-binary -q 2>/dev/null || true

  # Init schema
  echo "[bootstrap] Initializing schema..."
  (cd backend && $PY -c "import db; db.init_db()" 2>&1 || echo "[bootstrap] Schema init warning")

  # Start FastAPI
  echo "[bootstrap] Starting FastAPI on port 8088..."
  (cd backend && PORT=8088 HOST=127.0.0.1 AGENCY_API_KEY="$AGENCY_API_KEY" DATABASE_URL="$DATABASE_URL" $PY server.py) > /tmp/fastapi.log 2>&1 &
  FASTAPI_PID=$!
  echo "[bootstrap] FastAPI PID: $FASTAPI_PID"

  # Wait for readiness (up to 60s)
  for i in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:8088/health" >/dev/null 2>&1; then
      echo "[bootstrap] FastAPI ready"
      break
    fi
    sleep 1
  done
}

# Start FastAPI bootstrap in background
bootstrap_fastapi &

# Start Express server immediately (port 5000)
echo "Starting Express on port 5000..."
NODE_ENV=production \
  AGENCY_API_KEY="$AGENCY_API_KEY" \
  AGENCY_WRITE_KEY="$AGENCY_WRITE_KEY" \
  DATABASE_URL="$DATABASE_URL" \
  node dist/index.cjs
