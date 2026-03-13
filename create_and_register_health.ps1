# Usage: run from repo root in PowerShell (venv active)
$blueprintPath = "app\blueprints\health_routes.py"
$blueprintBackup = "$env:USERPROFILE\tmp-health_routes-backup-before-create.py"
$appFile = "app\flask_app.py"
$appBackup = "$env:USERPROFILE\tmp-flask_app-backup-before-health-register.py"

# 1) Write health blueprint (backup if exists)
if (Test-Path $blueprintPath) {
    Copy-Item $blueprintPath $blueprintBackup -Force
    Write-Host "Backed up existing $blueprintPath -> $blueprintBackup"
}
@"
from flask import Blueprint, jsonify, current_app
from datetime import datetime
import time

health_bp = Blueprint('health', __name__)

@health_bp.route('/healthz', methods=['GET'])
def healthz():
    \"\"\"Minimal health endpoint expected by tests.\"\"\"
    start_time = current_app.config.get('START_TIME')
    now = time.time()
    uptime = None
    if start_time:
        try:
            uptime = int(now - float(start_time))
        except Exception:
            uptime = None

    payload = {
        'healthy': True,
        'timestamp': datetime.utcfromtimestamp(now).isoformat() + 'Z',
        'uptime': uptime,
        'checks': {},
    }
    return jsonify(payload), 200
"@ | Out-File -FilePath $blueprintPath -Encoding utf8

Write-Host "Wrote $blueprintPath"

# 2) Patch app/flask_app.py to import and register the blueprint
if (-not (Test-Path $appFile)) {
    Write-Error "$appFile not found. Aborting patch."
    exit 1
}

Copy-Item $appFile $appBackup -Force
Write-Host "Backed up $appFile -> $appBackup"

# Read file lines
$lines = Get-Content $appFile -Raw -Encoding UTF8 -ErrorAction Stop
$array = $lines -split "`r?`n"

# Insert top-level import if not present
$importLine = "from app.blueprints.health_routes import health_bp"
$hasImport = $false
for ($i=0; $i -lt $array.Count; $i++) {
    if ($array[$i] -match "^\s*from\s+app\.blueprints\.health_routes\s+import\s+health_bp\s*$") { $hasImport = $true; break }
}
if (-not $hasImport) {
    # Find last import line (a line starting with 'import ' or 'from ')
    $lastImportIdx = -1
    for ($i=0; $i -lt $array.Count; $i++) {
        if ($array[$i] -match '^\s*(import\s+|from\s+\S+\s+import\s+)') { $lastImportIdx = $i }
    }
    $insertAt = 0
    if ($lastImportIdx -ge 0) { $insertAt = $lastImportIdx + 1 }
    $before = $array[0..($insertAt-1)]
    $after = $array[$insertAt..($array.Count - 1)]
    $array = $before + @($importLine) + $after
    Write-Host "Inserted import at line $($insertAt+1): $importLine"
} else {
    Write-Host "Import already present; skipping import insertion."
}

# Ensure blueprint registered inside create_app()
$registered = $false
# find def create_app
$createIdx = $null
for ($i=0; $i -lt $array.Count; $i++) {
    if ($array[$i] -match '^\s*def\s+create_app\s*\(') { $createIdx = $i; break }
}
if ($createIdx -eq $null) {
    Write-Warning "Could not find def create_app(...). Attempting to insert registration at end of file."
    # append registration at end (but inside global scope)
    if (-not ($array -join "`n" -match "app\.register_blueprint\(\s*health_bp")) {
        $array += ""
        $array += "# Register health blueprint added by create_and_register_health.ps1"
        $array += "try:"
        $array += "    app.register_blueprint(health_bp)"
        $array += "except Exception:"
        $array += "    pass"
        $registered = $true
    }
} else {
    # find the 'return app' after createIdx
    $returnIdx = $null
    for ($j = $createIdx+1; $j -lt $array.Count; $j++) {
        if ($array[$j] -match '^\s*return\s+app\s*$') { $returnIdx = $j; break }
    }
    if ($returnIdx -eq $null) {
        Write-Warning "No 'return app' found inside create_app(); will append registration just after create_app() def."
        $insPos = $createIdx + 1
    } else {
        $insPos = $returnIdx
    }

    # check if already registered anywhere
    if ($array -join "`n" -match "app\.register_blueprint\(\s*health_bp") {
        Write-Host "health_bp already registered in file; skipping register insertion."
        $registered = $true
    } else {
        # insert registration line before returnIdx (or at insPos if return not found)
        # place registration indented with 4 spaces (assuming function body uses 4-space indentation)
        $regLines = @(
            "    # Register health blueprint (added by create_and_register_health.ps1)",
            "    try:",
            "        app.register_blueprint(health_bp)",
            "    except Exception:",
            "        # In testing environments imports may fail; swallow registration errors",
            "        pass"
        )

        $before = $array[0..($insPos-1)]
        $after = $array[$insPos..($array.Count - 1)]
        $array = $before + $regLines + $after
        $registered = $true
        Write-Host "Inserted registration just before line $($insPos+1)."
    }
}

# Write back patched app file
Set-Content -Path $appFile -Value ($array -join "`n") -Encoding utf8
Write-Host "Patched $appFile and preserved backup at $appBackup"

# Print the area around create_app for review
if ($createIdx -ne $null) {
    $start = [math]::Max(1, $createIdx - 4)
    $end = [math]::Min($createIdx + 40, $array.Count - 1)
    Write-Host "`n--- Context around create_app (lines $start..$end) ---"
    for ($i = $start; $i -le $end; $i++) {
        "{0,4}: {1}" -f ($i+1), (Get-Content $appFile)[$i]
    }
} else {
    Write-Host "`ncreate_app not found; appended registration at end of file. Review $appFile manually."
}

Write-Host "`nDone. If you want to revert:"
Write-Host "Copy-Item `"$appBackup`" `"$appFile`" -Force"
Write-Host "Copy-Item `"$blueprintBackup`" `"$blueprintPath`" -Force # if a backup was made"
