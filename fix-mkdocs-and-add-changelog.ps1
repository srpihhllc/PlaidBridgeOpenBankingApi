# Safe PowerShell script to fix mkdocs nav (remove leading "docs/") and ensure CHANGELOG.md exists.
# Run from repository root in PowerShell (where mkdocs.yml is located).
#
# What it does:
#  - Back up mkdocs.yml to $env:USERPROFILE\tmp-mkdocs-yml-backup.yml
#  - Remove "docs/" prefixes from nav file paths (only when followed by .md/.yaml/.yml)
#  - Create a minimal root CHANGELOG.md if missing
#  - Run mkdocs build --strict (if mkdocs is installed in this environment)
#
# Usage (PowerShell): 
#   .\fix-mkdocs-and-add-changelog.ps1

$mk = "mkdocs.yml"
$backup = "$env:USERPROFILE\tmp-mkdocs-yml-backup.yml"

if (-not (Test-Path $mk)) {
    Write-Error "mkdocs.yml not found in current directory. cd to repo root and retry."
    exit 1
}

Write-Host "Backing up $mk -> $backup"
Copy-Item $mk $backup -Force

# Load and normalize nav entries: remove 'docs/' only when followed by a filename with extension .md/.yaml/.yml
$text = Get-Content $mk -Raw

# This replacement is conservative: it only targets occurrences like docs/01-name.md or docs/10-openapi.yaml
$fixed = $text -replace 'docs\/([A-Za-z0-9_\-\/]+?\.(?:md|yaml|yml))', '$1'

if ($fixed -ne $text) {
    Write-Host "Updating mkdocs.yml: removing leading 'docs/' from nav file paths"
    $fixed | Set-Content -Path $mk -Encoding UTF8
    Write-Host "mkdocs.yml updated (backup at $backup)"
} else {
    Write-Host "No 'docs/' prefixes found to normalize in mkdocs.yml"
}

# Ensure top-level CHANGELOG.md exists (create placeholder only if missing)
if (-not (Test-Path "CHANGELOG.md")) {
    Write-Host "Creating placeholder CHANGELOG.md at repo root"
    @"
# Changelog

This CHANGELOG.md is a minimal placeholder created to satisfy MkDocs strict navigation and CI checks.
Replace with your project's real changelog content.

## Unreleased

- placeholder: added CHANGELOG.md so mkdocs strict build passes
"@ | Set-Content -Path "CHANGELOG.md" -Encoding UTF8
} else {
    Write-Host "CHANGELOG.md already exists at repo root"
}

# (Optional) ensure CONTRIBUTING.md exists - create minimal only if missing
if (-not (Test-Path "CONTRIBUTING.md")) {
    Write-Host "Creating placeholder CONTRIBUTING.md at repo root"
    @"
# Contributing

This is a placeholder CONTRIBUTING.md. Replace with contribution guidelines for the project.
"@ | Set-Content -Path "CONTRIBUTING.md" -Encoding UTF8
} else {
    Write-Host "CONTRIBUTING.md already exists at repo root"
}

# Run mkdocs build --strict if mkdocs is available in the PATH
# If mkdocs is not available in this environment, skip this step and run it in CI or your MkDocs virtualenv.
try {
    Write-Host "Running: mkdocs build --strict"
    $proc = Start-Process -FilePath "mkdocs" -ArgumentList "build --strict" -NoNewWindow -Wait -PassThru -ErrorAction Stop
    if ($proc.ExitCode -eq 0) {
        Write-Host "mkdocs build --strict: OK"
    } else {
        Write-Host "mkdocs build --strict returned exit code $($proc.ExitCode)"
        exit $proc.ExitCode
    }
} catch {
    Write-Warning "Failed to run 'mkdocs' here (mkdocs may not be installed in this shell)."
    Write-Host "Please run 'mkdocs build --strict' in your docs environment (CI runner or virtualenv)."
}

Write-Host "Done."
