# Run from repo root in PowerShell (with admin/ExecutionPolicy bypass if needed)
# This script:
#  - backs up old .venv (rename)
#  - stops tracking .venv in git
#  - creates a new venv folder named @srpihhllc-PlaidBridgeOpenBankingApi
#  - activates it and installs requirements.txt if present

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# 1) Deactivate any active venv (PowerShell)
if (Get-Command "deactivate" -ErrorAction SilentlyContinue) {
    try { deactivate } catch {}
}

# 2) Backup existing .venv (if present)
$oldVenv = ".venv"
if (Test-Path $oldVenv) {
    $timestamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
    $backupName = ".venv_backup_$timestamp"
    Write-Host "Renaming existing .venv -> $backupName (backup)..."
    Rename-Item -Path $oldVenv -NewName $backupName -Force
} else {
    Write-Host "No .venv directory found. Continuing."
}

# 3) Stop tracking .venv in git (if it was tracked)
if (git ls-files --error-unmatch .venv -q 2>$null) {
    Write-Host ".venv is tracked by git; removing from index (keeps files locally) ..."
    git rm -r --cached .venv
    git commit -m "chore: stop tracking local .venv" || Write-Host "No commit made (nothing staged)"
} else {
    Write-Host ".venv not tracked by git."
}

# 4) Choose new venv folder name (no slashes): use @srpihhllc-PlaidBridgeOpenBankingApi
$newVenv = "@srpihhllc-PlaidBridgeOpenBankingApi"
Write-Host "New venv folder will be: $newVenv"

# 5) Add new venv folder to .gitignore if not present
$ignoreLine = "$newVenv/"
if (-not (Test-Path .gitignore)) { New-Item -Path .gitignore -ItemType File -Force | Out-Null }
if (-not (Select-String -Path .gitignore -Pattern ([regex]::Escape($newVenv)) -Quiet)) {
    Add-Content -Path .gitignore -Value "`n# Local virtualenv for repo`n$ignoreLine"
    git add .gitignore
    git commit -m "chore: ignore local venv $newVenv" || Write-Host "No commit created for .gitignore (maybe no changes)"
} else {
    Write-Host ".gitignore already contains an entry for $newVenv"
}

# 6) Create the new venv
Write-Host "Creating new venv in folder: $newVenv ..."
python -m venv $newVenv

# 7) Activate the new venv (PowerShell)
Write-Host "Activating the new venv..."
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& ".\$newVenv\Scripts\Activate.ps1"

# 8) Upgrade pip and install requirements if present
Write-Host "Upgrading pip and installing requirements (if requirements.txt exists)..."
python -m pip install --upgrade pip setuptools wheel
if (Test-Path "requirements.txt") {
    Write-Host "requirements.txt found — installing..."
    pip install -r requirements.txt
} else {
    Write-Host "No requirements.txt found — installing minimal tooling (ruff, pytest, alembic)..."
    pip install ruff pytest alembic
}

# 9) Show verification and how the prompt will appear
Write-Host ""
Write-Host "== Verification =="
Write-Host "Python: " (Get-Command python).Source
Write-Host "Pip:    " (Get-Command pip).Source
Write-Host "Virtual env path: $env:VIRTUAL_ENV"
Write-Host "Your shell prompt should now include: ($newVenv) at the front."

# Print top lines of activation script (optional) to show prompt function
Write-Host "`nActivation prompt info (first 40 lines of Activate.ps1):"
Get-Content ".\$newVenv\Scripts\Activate.ps1" -TotalCount 40 | Out-Host

Write-Host "`nDone. To activate later: .\$newVenv\Scripts\Activate.ps1"
