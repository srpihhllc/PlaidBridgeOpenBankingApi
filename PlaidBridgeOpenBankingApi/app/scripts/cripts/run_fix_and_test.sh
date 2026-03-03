#!/usr/bin/env bash
set -euo pipefail

# Run from repo root. Use Git Bash / PowerShell / CMD (bash required for this script).
PY_SCRIPT="scripts/replace_invalid_login.py"

if [ ! -f "$PY_SCRIPT" ]; then
  echo "Missing $PY_SCRIPT — create it first (see scripts/replace_invalid_login.py)"
  exit 1
fi

echo "1) Applying safe edit..."
python "$PY_SCRIPT"

echo
echo "2) Running the single failing test..."
export PYTHONPATH="$PWD/PlaidBridgeOpenBankingApi"
export PYTHONIOENCODING=utf-8

# Run test — if it fails this script exits with non-zero
pytest -q app/tests/test_auth_routes.py::test_login_invalid_credentials -q

echo
echo "3) Test passed — preparing commit."

# If an index.lock is present, stop and instruct user to remove it manually to avoid clobbering
if [ -f .git/index.lock ]; then
  echo "ERROR: .git/index.lock exists. Make sure no other git is running and remove it:"
  echo "  rm -f .git/index.lock"
  exit 2
fi

git add PlaidBridgeOpenBankingApi/app/blueprints/auth_routes.py
git commit -m "fix(auth): re-render login form on invalid credentials (return 200 instead of redirect)" || true
git push origin chore/add-nav-audit-run || true

echo "Done. If the commit was pushed, the branch has the fix."
