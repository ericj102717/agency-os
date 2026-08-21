#!/usr/bin/env bash
# Production start script for the FastAPI backend.
# Used by Render, Railway, or any container host.
set -euo pipefail

# Install Python dependencies
pip install --no-cache-dir -r backend/requirements.txt

# Start the FastAPI server
# PORT is provided by the host (Render/Railway default to 10000)
# ALLOWED_ORIGINS should be set to the frontend URL (comma-separated)
exec python3 backend/server.py
