#!/usr/bin/env python3
"""
Safe edit: replace the redirect after the "Invalid email or password." flash
with returning the rendered login template.

Creates a timestamped backup:
  PlaidBridgeOpenBankingApi/app/blueprints/auth_routes.py.fixbak.<ts>
"""
import re
import shutil
from pathlib import Path
from datetime import datetime

FILE = Path("PlaidBridgeOpenBankingApi/app/blueprints/auth_routes.py")
if not FILE.exists():
    raise SystemExit(f"File not found: {FILE}")

# Backup
ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
bak = FILE.with_name(FILE.name + f".fixbak.{ts}")
shutil.copy2(FILE, bak)
print("Backup written to:", bak)

text = FILE.read_text(encoding="utf-8", errors="replace")

# Find start of login_view definition
m_def = re.search(r'(^\s*def\s+login_view\s*\(\s*\)\s*:\s*)', text, flags=re.M)
if not m_def:
    raise SystemExit("Could not locate login_view() definition")

start_idx = m_def.start()

# Heuristic: find the next top-level @auth_bp.route or next "def " at column 0 after the start to mark end
rest = text[start_idx:]
m_next = re.search(r'\n\s*@auth_bp\.route\(|\n^def\s+', rest, flags=re.M)
if m_next:
    end_idx = start_idx + m_next.start()
else:
    end_idx = len(text)

func_block = text[start_idx:end_idx]

# Replace only the redirect immediately after the specific flash inside this function
new_block, nsubs = re.subn(
    r'(flash\(\s*["\']Invalid email or password\.\s*["\']\s*,\s*["\']danger["\']\s*\)\s*)'
    r'return\s+redirect\s*\(\s*url_for\s*\(\s*["\']auth\.login["\']\s*\)\s*\)\s*;?',
    r'\1return render_template("auth/login.html")',
    func_block,
    count=1,
    flags=re.S,
)

if nsubs:
    new_text = text[:start_idx] + new_block + text[end_idx:]
    FILE.write_text(new_text, encoding="utf-8")
    print(f"Replaced {nsubs} redirect(s) inside login_view().")
else:
    print("No matching redirect found inside login_view() (maybe already replaced).")

# Print a small context window for manual verification
lines = FILE.read_text(encoding="utf-8").splitlines()
start_line = max(1, text[:start_idx].count("\n") + 1)
end_line = start_line + new_block.count("\n")
print("\n---- context (login_view) ----")
for i in range(start_line - 1, min(end_line + 2, len(lines))):
    print(f"{i+1:4d}: {lines[i]}")
print("---- end context ----")
