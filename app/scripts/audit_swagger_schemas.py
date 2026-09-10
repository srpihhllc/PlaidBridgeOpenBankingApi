# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/scripts/audit_swagger_schemas.py

import os
import re

APP_DIR = "app"
VIOLATIONS = []

# Pattern matches any dictionary parameter entry with "in": "body" or 'in': 'body'
BODY_PARAM_PATTERN = re.compile(r'[\'"]in[\'"]\s*:\s*[\'"]body[\'"]')
SCHEMA_PATTERN = re.compile(r'[\'"]schema[\'"]\s*:')

for root, _, files in os.walk(APP_DIR):
    for file in files:
        if file.endswith((".py", ".yaml", ".yml")):
            filepath = os.path.join(root, file)
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()

            body_count_in_block = 0
            has_schema = False

            for line_idx, line in enumerate(lines, 1):
                if BODY_PARAM_PATTERN.search(line):
                    if not SCHEMA_PATTERN.search(line):
                        VIOLATIONS.append((filepath, line_idx, line.strip()))

if VIOLATIONS:
    print(
        f" Found {len(VIOLATIONS)} potential Swagger 2.0 schema violations:\n"
    )
    for file, line_num, text in VIOLATIONS:
        print(f"  {file}:{line_num} -> {text}")
else:
    print(
        " No legacy `in: body` parameter violations found across blueprint definitions."
    )
