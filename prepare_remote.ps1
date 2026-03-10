# prepare_remote.ps1
# Run from repo root with .venv currently active (or not) - PowerShell

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# 0) Print current branch and status for review
Write-Host "Current branch:" (git branch --show-current)
git status --porcelain -u | Select-String -Pattern "app|.venv" -Context 0,0

# 1) Create and switch to a working branch for the change
$branch = "fix/single-create-app-shim"
git checkout -b $branch

# 2) Ensure .venv is in .gitignore
if (-not (Select-String -Path .gitignore -Pattern "^\Q.venv\E" -SimpleMatch -Quiet)) {
  Add-Content .gitignore "`n# Local virtualenv`n.venv`n"
  Write-Host ".venv appended to .gitignore"
} else {
  Write-Host ".venv already present in .gitignore"
}

# 3) Stop tracking .venv (remove from git index, keep files locally)
Write-Host "Removing .venv from index (will not delete local files)..."
git rm -r --cached .venv -q || Write-Host "No tracked .venv or already removed from index."

# 4) Stage the files we want on the branch (explicit, to avoid staging .venv)
Write-Host "Staging .gitignore and app files..."
git add .gitignore
# Stage canonical factory and shim (if present)
if (Test-Path app\__init__.py) { git add app\__init__.py } else { Write-Host "Warning: app\__init__.py not present in working tree" }
if (Test-Path app\flask_app.py) { git add app\flask_app.py } else { Write-Host "Warning: app\flask_app.py not present in working tree" }

# Stage models if modified (you intentionally changed many model files)
git add app\models\*.py

# 5) Show what will be committed
Write-Host "Files staged for commit:"
git status --porcelain | Select-String -Pattern "^[AMRD]"

# 6) Commit
git commit -m "chore(app): canonical create_app in app.__init__; add thin flask_app shim; stop tracking .venv"

# 7) Push branch to origin and set upstream
Write-Host "Pushing branch to origin..."
git push -u origin $branch

# 8) Verify remote branch and file contents exist
Write-Host "Fetching origin and verifying remote branch..."
git fetch origin --prune
# Show remote branch list containing our branch
git branch -r | Select-String $branch -Quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "Remote branch origin/$branch exists."
    Write-Host "Show remote app/__init__.py (if present):"
    try {
        git show origin/$branch:app/__init__.py | Select-String -Pattern "create_app" -Context 0,3
    } catch {
        Write-Host "app/__init__.py not found on origin/$branch"
    }
} else {
    Write-Host "origin/$branch not found in remote branches - check push errors above."
}

Write-Host "prepare_remote.ps1 finished."
