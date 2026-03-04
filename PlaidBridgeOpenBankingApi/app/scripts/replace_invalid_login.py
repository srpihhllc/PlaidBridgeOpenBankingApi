#!/usr/bin/env python3
"""
Safe edit: replace the redirect after the "Invalid email or password." flash
with returning the rendered login template.

Creates a timestamped backup: PlaidBridgeOpenBankingApi/app/blueprints/auth_routes.py.fixbak.<ts>
"""
import re
import shutil
from pathlib import Path
from datetime import datetime

FILE = Path("PlaidBridgeOpenBankingApi/app/blueprints/auth_routes.py")
if not FILE.exists():
    raise SystemExit(f"File not found: {FILE}")

ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
bak = FILE.with_name(FILE.name + f".fixbak.{ts}")
shutil.copy2(FILE, bak)
print(f"Backup written to: {bak}")

s = FILE.read_text(encoding="utf-8", errors="replace")

pattern = re.compile(
    r'(flash\(\s*["\']Invalid email or password\.\s*["\']\s*,\s*["\']danger["\']\s*\)\s*)'
    r'return\s+redirect\s*\(\s*url_for\s*\(\s*["\']auth\.login["\']\s*\)\s*\)\s*;?',
    re.S,
)
if pattern.search(s):
    s2 = pattern.sub(r'\1return render_template("auth/login.html")', s, count=1)
    FILE.write_text(s2, encoding="utf-8")
    print("Replacement applied.")
else:
    print("Pattern not found — no change made (maybe already replaced).")

# Print a small context window for manual verification
lines = FILE.read_text(encoding="utf-8").splitlines()
start = max(0, 372 - 1)
end = min(len(lines), 404)
print("\n---- context (lines 372-404) ----")
for i in range(start, end):
    print(f"{i+1:4d}: {lines[i]}")
print("---- end context ----")
