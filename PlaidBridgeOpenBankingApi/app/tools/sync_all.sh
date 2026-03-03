#!/usr/bin/env bash
set -euo pipefail

BRANCH="chore/add-nav-audit-run"
TS="$(date +%Y%m%d%H%M%S)"
ARCHIVE_DIR="backups/tmpl_backups_${TS}"

echo "Archiving *.bak files to $ARCHIVE_DIR ..."
mkdir -p "$ARCHIVE_DIR"
# Move all .bak files into the archive while preserving paths
find . -type f -name '*.bak' -print0 | while IFS= read -r -d '' f; do
  dest="$ARCHIVE_DIR/$(dirname "$f")"
  mkdir -p "$dest"
  mv -- "$f" "$ARCHIVE_DIR/$f" || true
  echo "archived: $f -> $ARCHIVE_DIR/$f"
done

echo
# Ignore .bak going forward (if not already ignored)
if [ ! -f .gitignore ] || ! grep -qxF '*.bak' .gitignore; then
  echo '*.bak' >> .gitignore
  git add .gitignore
  echo "Added '*.bak' to .gitignore and staged it."
fi

# Ensure we're on the intended branch and up-to-date with remote
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH" || true

# Stage all changes (including new files like PR_DESCRIPTION.md, missing_after_fix.json, tools/)
echo "Staging all changes..."
git add -A

# Commit (if there are staged changes)
if ! git diff --cached --quiet; then
  git commit -m "chore(sync): commit workspace changes; archive .bak backups to ${ARCHIVE_DIR}"
  echo "Committed staged changes."
else
  echo "No staged changes to commit."
fi

# Push branch
echo "Pushing branch ${BRANCH} to origin..."
git push origin "$BRANCH"

# Show short verification
echo
echo "=== recent commits ==="
git --no-pager log --oneline -n 8
echo
echo "=== git status (porcelain) ==="
git status --porcelain
echo
echo "Backups archived under: $ARCHIVE_DIR"
echo "If you need to restore a .bak file, it's in that directory with its original path preserved."
