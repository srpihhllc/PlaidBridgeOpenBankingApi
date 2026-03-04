#!/usr/bin/env bash
# Applies the jinja_env global change, commits templates, runs audits/tests,
# and captures remaining missing endpoints.
#
# Usage (from repo root, Git Bash / POSIX):
#   chmod +x tools/apply_and_check.sh
#   ./tools/apply_and_check.sh
#
# Safe: creates a .bak copy of the app factory before editing, and writes
# missing_after_fix.json for inspection. It will not push automatically unless
# you confirm (uncomment the PUSH step).

set -euo pipefail

REPO_ROOT="$(pwd)"
APP_INIT="PlaidBridgeOpenBankingApi/app/__init__.py"
BACKUP="${APP_INIT}.bak"

echo "Repository root: ${REPO_ROOT}"
echo "Target file: ${APP_INIT}"

if [ ! -f "${APP_INIT}" ]; then
  echo "ERROR: expected file not found: ${APP_INIT}"
  exit 1
fi

# 1) Backup the original file
echo "Backing up ${APP_INIT} -> ${BACKUP}"
cp -p "${APP_INIT}" "${BACKUP}"

# 2) Insert the jinja_env global line (idempotent: only inserts once)
python - <<'PY'
from pathlib import Path
p = Path("PlaidBridgeOpenBankingApi/app/__init__.py")
s = p.read_text()
needle = "\n    return flask_app\n"
insert = (
    '\n    # Expose the Flask app instance to Jinja globals (silences template_audit warning).\n'
    '    # Harmless: only adds a reference in the template globals for audit & templates that\n'
    '    # expect `app` to exist in Jinja globals.\n'
    '    flask_app.jinja_env.globals["app"] = flask_app\n'
)
if insert.strip() in s:
    print("Already inserted: jinja_env global present -> nothing to change.")
else:
    if needle in s:
        s = s.replace(needle, insert + needle, 1)
        p.write_text(s)
        print("Inserted jinja_env global line.")
    else:
        print("ERROR: could not find expected return location in PlaidBridgeOpenBankingApi/app/__init__.py")
        raise SystemExit(2)
PY

# 3) Show the diff for review
echo "---- git diff (unstaged) ----"
git --no-pager diff -- PlaidBridgeOpenBankingApi/app/__init__.py || true
echo "----------------------------"

# 4) Stage changes (templates + factory). We assume you've already applied template fixes.
# Use -u to stage modified tracked files and the app factory change.
git add -u

echo
echo "Files staged for commit:"
git --no-pager status --porcelain

# 5) Commit
read -p "Commit staged changes now? [y/N] " yn
if [[ "${yn}" =~ ^[Yy] ]]; then
  git commit -m "chore: align template endpoints; expose Flask app in jinja_env.globals for audit"
  echo "Committed changes locally."
else
  echo "Skipped commit. You can inspect changes and commit manually."
fi

# 6) Optional: push (commented by default)
# read -p "Push branch chore/add-nav-audit-run to origin now? [y/N] " pushyn
# if [[ "${pushyn}" =~ ^[Yy] ]]; then
#   git push origin chore/add-nav-audit-run
# fi

# 7) Run the template + orchestration audit and capture missing endpoints
export PYTHONPATH="${REPO_ROOT}/PlaidBridgeOpenBankingApi"
export FLASK_ENV=development
export SQLALCHEMY_DATABASE_URI="sqlite:///./dev-db.sqlite"

echo
echo "Running audits (this may take a few seconds)..."
python - <<'PY' | sed -n '/🚨 Missing endpoints:/,$p' > missing_after_fix.json
# run audit script and print the part from the missing endpoints JSON onward
import sys, subprocess, json
# We call the audit as a module so it uses your project PYTHONPATH.
subprocess.run([sys.executable, "-m", "app.scripts.audit"])
PY

echo "Audit run complete. Remaining missing endpoints (if any) saved to missing_after_fix.json"
if [ -s missing_after_fix.json ]; then
  echo "missing_after_fix.json is not empty — please inspect or paste here for triage."
  echo "Preview:"
  sed -n '1,200p' missing_after_fix.json || true
else
  echo "missing_after_fix.json is empty — no missing endpoints reported by the audit."
fi

# 8) Run tests (pytest preferred, fallback to unittest)
echo
echo "Running tests..."
if command -v pytest >/dev/null 2>&1; then
  pytest -q || true
else
  python -m unittest discover -v || true
fi

# 9) Lint check (if tools are installed). Non-fatal.
echo
echo "Running optional lint/format checks (non-fatal)..."
if command -v black >/dev/null 2>&1; then
  black --check . || echo "black detected issues (run 'black .' to autoformat)"
fi
if command -v flake8 >/dev/null 2>&1; then
  flake8 . || echo "flake8 detected issues"
fi

echo
echo "DONE. Next recommended steps:"
echo "  - Inspect missing_after_fix.json (if non-empty) and paste it here for triage."
echo "  - If commit was skipped earlier, commit and push the branch, then open a PR."
echo "  - After PR/CI green, follow merge/deploy runbook (migrations, staging smoke tests)."
