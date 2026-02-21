# =============================================================================
# FILE: scripts/grep_template_audit.py
# DESCRIPTION: Scans all route files for render_template() calls and cross-checks
#              against the templates/ directory to detect missing or mismatched templates.
# =============================================================================

import os
import re

ROUTES_DIRS = [
    "app/blueprints",
    "app/routes",
    "app/cockpit/routes",
]
TEMPLATES_DIR = "app/templates"


def collect_templates():
    templates = set()
    for root, _, files in os.walk(TEMPLATES_DIR):
        for f in files:
            if f.endswith((".html", ".jinja2")):
                rel_path = os.path.relpath(os.path.join(root, f), TEMPLATES_DIR)
                templates.add(rel_path.replace("\\", "/"))
    return templates


def grep_routes():
    render_calls = []
    for base in ROUTES_DIRS:
        for root, _, files in os.walk(base):
            for f in files:
                if not f.endswith(".py"):
                    continue
                path = os.path.join(root, f)
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    text = fh.read()
                for match in re.findall(r'render_template\(\s*[\'"]([^\'"]+)[\'"]', text):
                    render_calls.append((path, match))
    return render_calls


def main():
    templates = collect_templates()
    calls = grep_routes()

    print("=== ROUTE → TEMPLATE AUDIT ===")
    for path, tpl in calls:
        status = "OK" if tpl in templates else "MISSING"
        print(f"{path} → {tpl} [{status}]")


if __name__ == "__main__":
    main()
