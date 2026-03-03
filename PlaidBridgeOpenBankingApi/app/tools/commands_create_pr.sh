#!/usr/bin/env bash
# Run from repo root (Git Bash). This script stages, commits, pushes, and opens a PR
# using the GitHub CLI. If you don't have gh installed, see the alternative instructions below.
#
# Review changes before running. This will not run automatically unless you execute it.

set -euo pipefail

BRANCH="chore/add-nav-audit-run"
REMOTE="origin"
PR_TITLE="chore: align template endpoints and expose Flask app in Jinja globals"
PR_BODY_FILE="PR_DESCRIPTION.md"  # file content above

# 1) Ensure branch exists and is checked out
git checkout "${BRANCH}"

# 2) Stage tracked changes (we assume templates and __init__.py are modified)
git add -u

# 3) Commit (edit message if desired)
git commit -m "chore: align template endpoints; expose Flask app in jinja_env.globals for audit"

# 4) Push the branch
git push "${REMOTE}" "${BRANCH}"

# 5) Create the PR with GitHub CLI (interactive)
#    If you want to create it non-interactively, ensure GH CLI is authenticated and use --body-file
if command -v gh >/dev/null 2>&1; then
  gh pr create --base main --head "${BRANCH}" --title "${PR_TITLE}" --body-file "${PR_BODY_FILE}"
else
  echo "gh not found. Create a PR manually on GitHub from branch ${BRANCH} into main and use the PR description from ${PR_BODY_FILE}"
fi

echo "PR creation step complete (or pending manual creation)."
