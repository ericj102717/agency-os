#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

# Diagnostic: check what's available
echo "=== Environment Diagnostic ==="
echo "Node: $(node --version 2>&1)"
echo "NPM: $(npm --version 2>&1)"
echo "Python: $(python --version 2>&1 || echo 'NOT FOUND')"
echo "Python3: $(python3 --version 2>&1 || echo 'NOT FOUND')"
echo "Pip: $(pip --version 2>&1 || echo 'NOT FOUND')"
echo "Pip3: $(pip3 --version 2>&1 || echo 'NOT FOUND')"
echo "Which python: $(which python 2>&1 || echo 'NOT FOUND')"
echo "Which python3: $(which python3 2>&1 || echo 'NOT FOUND')"
echo "PATH: $PATH"
echo "=== Files ==="
ls -la dist/index.cjs 2>&1
ls -la backend/server.py 2>&1
echo "=== Starting Express with diagnostic info ==="

NODE_ENV=production \
  AGENCY_API_KEY="diag-test-key" \
  AGENCY_WRITE_KEY="nMHKbJCRkpTgHyqEy0acrakD1hDWOe3p6yd6QKEOxLU" \
  node dist/index.cjs
