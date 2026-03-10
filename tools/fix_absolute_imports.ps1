# tools/fix_absolute_imports.ps1
# Run from repository root. Creates .bak backups before editing files.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Write-Host "Scanning for parent-relative imports of app.extensions.db..."

# Patterns to replace:
$pattern1 = 'from\s+\.\.\s*extensions\s+import\s+db'
$pattern2 = 'from\s+\.\.\s*extensions\s+import\s+(.+)'

# Search python files under app/ for the pattern
Get-ChildItem -Path .\app -Recurse -Include *.py -File |
    ForEach-Object {
        $path = $_.FullName
        $text = Get-Content -Raw -Path $path
        if ($text -match $pattern1 -or $text -match $pattern2) {
            Copy-Item -Path $path -Destination "$path.bak" -Force
            $new = $text -replace $pattern1, 'from app.extensions import db'
            # handles "from ..extensions import something, db" -> map db only; if more complex, leave manual
            $new = $new -replace "from\s+\.\.\s*extensions\s+import\s+(.+)", 'from app.extensions import $1'
            Set-Content -Path $path -Value $new -Force
            Write-Host "Patched: $path (backup: $($path).bak)"
        }
    }

Write-Host "Done. Search for remaining relative imports manually if any."
