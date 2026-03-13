# Backup file first
$src = "app\blueprints\auth_routes.py"
$bak = "$env:USERPROFILE\tmp-auth_routes-normalize-backup.py"
Copy-Item $src $bak -Force
Write-Host "Backup saved to $bak"

# Load file
$lines = Get-Content $src -Raw -Encoding UTF8 -ErrorAction Stop
$array = $lines -split "`r?`n"

# Find top-level clusters: lines that start at column 0 with @, def or class
$topIndices = @()
for ($i = 0; $i -lt $array.Count; $i++) {
    if ($array[$i] -match '^[^ \t](@|def\s+|class\s+)') {
        $topIndices += $i
    }
}
if ($topIndices.Count -eq 0) {
    Write-Host "No top-level def/class/@ lines found. Aborting."
    exit 0
}
# Add EOF sentinel
$topIndices += $array.Count

$changed = @()

# For each cluster, find the def line (skip pure decorator-only clusters)
for ($t = 0; $t -lt $topIndices.Count - 1; $t++) {
    $clusterStart = $topIndices[$t]
    $clusterEnd = $topIndices[$t+1] - 1

    # find the first def within the cluster (if any)
    $defIdx = $null
    for ($j = $clusterStart; $j -le $clusterEnd; $j++) {
        if ($array[$j] -match '^\s*def\s+') { $defIdx = $j; break }
    }
    if ($defIdx -eq $null) { continue }

    # body runs from defIdx+1 .. clusterEnd
    for ($k = $defIdx + 1; $k -le $clusterEnd; $k++) {
        $ln = $array[$k]
        if ($ln.Trim().Length -gt 0 -and $ln -notmatch '^[ \t]') {
            # Prepend 4 spaces to lines that are inside the function but at column 0
            $array[$k] = '    ' + $ln
            $changed += $k
        }
    }
}

if ($changed.Count -eq 0) {
    Write-Host "No in-function lines at column 0 detected; no changes made."
    exit 0
}

# Write back file
Set-Content -Path $src -Value ($array -join "`n") -Encoding UTF8
Write-Host "Applied conservative normalization. Lines changed: $($changed.Count)"

# Print a few contexts around the first changed lines for review
$sample = $changed | Select-Object -Unique | Select-Object -First 6
foreach ($idx in $sample) {
    $start = [math]::Max(1, $idx - 3)
    $end = [math]::Min($idx + 3, $array.Count - 1)
    Write-Host "`n--- Context around line $($idx+1) ---"
    for ($i = $start; $i -le $end; $i++) {
        "{0,4}: {1}" -f ($i+1), (Get-Content $src)[$i]
    }
}

# Quick syntax check
Write-Host "`nRunning: python -m py_compile $src"
python -m py_compile $src
if ($LASTEXITCODE -eq 0) {
    Write-Host "py_compile: OK"
} else {
    Write-Host "py_compile: FAILED"
    Write-Host "If it failed, paste the py_compile output and the printed contexts above and I'll refine the fix."
}

Write-Host "`nIf you want to revert, run:"
Write-Host "Copy-Item `"$bak`" $src -Force; Write-Host 'Restored backup.'"
