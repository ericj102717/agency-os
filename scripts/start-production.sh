#!/usr/bin/env bash
# Production start script for the FastAPI backend.
# Used by Render, Railway, or any container host.
set -euo pipefail

cd "$(dirname "$0")/.."

# Install Python dependencies
pip install --no-cache-dir -r backend/requirements.txt

# Install psycopg2 if using Postgres
if [ -n "${DATABASE_URL:-}" ]; then
  pip install psycopg2-binary -q 2>/dev/null || true

  echo "Initializing Postgres schema..."
  (cd backend && python3 -c "import db; db.init_db()" 2>&1 || echo "Schema init warning")

  echo "Running data migration if needed..."
  (cd backend && python3 scripts/migrate_to_postgres.py 2>&1 || echo "Migration skipped")
fi

# Start the FastAPI server
# PORT is provided by the host (Render defaults to 10000)
# ALLOWED_ORIGINS should be set to the frontend URL (comma-separated)
exec python3 backend/server.py
