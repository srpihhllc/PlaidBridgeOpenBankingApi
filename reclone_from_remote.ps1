# reclone_from_remote.ps1
# Run from the parent directory of your repo clone (i.e., one level above PlaidBridgeOpenBankingApi_repo_clone)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$localDir = "PlaidBridgeOpenBankingApi_repo_clone"
$repoUrl = "https://github.com/srpihhllc/PlaidBridgeOpenBankingApi.git"
$branch = "fix/single-create-app-shim"  # change if you pushed a different branch

# 0) Optional: stash or backup important local changes
Write-Host "If you have local changes you want to keep, create a backup now. Sleeping 5s..."
Start-Sleep -Seconds 5

# 1) Remove local repo directory (careful)
if (Test-Path $localDir) {
    Write-Host "Removing local repo directory $localDir ..."
    # Move it instead of immediate delete for safety (rename)
    $bakDir = "${localDir}_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Write-Host "Renaming to backup: $bakDir"
    Rename-Item -Path $localDir -NewName $bakDir
} else {
    Write-Host "Local directory $localDir not found. Continuing to clone."
}

# 2) Clone fresh copy of the repo and check out the branch
Write-Host "Cloning $repoUrl ..."
git clone $repoUrl $localDir

Set-Location $localDir

# 3) Checkout branch (create local tracking if necessary)
try {
    git fetch origin
    git checkout $branch
} catch {
    Write-Host "Branch $branch not found on origin. Listing remote branches:"
    git branch -r
    throw
}

# 4) Verify files are present
Write-Host "Verifying app/__init__.py and app/flask_app.py exist in fresh clone..."
if (Test-Path app\__init__.py) { Write-Host "app/__init__.py exists." } else { Write-Host "app/__init__.py missing." }
if (Test-Path app\flask_app.py) { Write-Host "app/flask_app.py exists." } else { Write-Host "app/flask_app.py missing." }

# 5) Create new venv and install minimal deps (optional)
Write-Host "Creating a fresh venv in the repo..."
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
Write-Host "Done. Inspect files locally and run tests as needed."
