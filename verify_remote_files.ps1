# Replace branch name if different
$branch="fix/single-create-app-shim"
git fetch origin $branch
Write-Host "Remote branches:"
git branch -r | Select-String $branch -Context 0,0

# Show remote file content (safe read-only)
Write-Host "Remote app/__init__.py head (if present):"
try { git show origin/$branch:app/__init__.py | Select-Object -First 40 } catch { Write-Host "Not found or not accessible." }

Write-Host "Remote app/flask_app.py head (if present):"
try { git show origin/$branch:app/flask_app.py | Select-Object -First 40 } catch { Write-Host "Not found or not accessible." }
