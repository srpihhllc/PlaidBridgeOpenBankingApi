# name=template_url_check.py
import re
from pathlib import Path
import sys
from typing import Set

# Run this script from the repository root (project directory that contains app/)
ROOT = Path.cwd()
TPL_GLOB = "app/templates/**/*.html"

pattern = re.compile(r"url_for\(\s*['\"]([^'\"]+)['\"]")
tpl_paths = list(ROOT.glob(TPL_GLOB))

def collect_used_endpoints(tpl_paths) -> Set[str]:
    used = set()
    for p in tpl_paths:
        try:
            txt = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in pattern.finditer(txt):
            used.add(m.group(1))
    return used

def main():
    used = collect_used_endpoints(tpl_paths)
    if not tpl_paths:
        print("No templates found under", TPL_GLOB)
        sys.exit(1)

    print(f"Found {len(tpl_paths)} template files, extracted {len(used)} distinct url_for(...) endpoints from templates.\n")

    # Import app and create application to inspect registered endpoints.
    # Creating the Flask app may print logs; that's expected.
    try:
        from app import create_app
    except Exception as e:
        print("Failed to import app.create_app():", e)
        sys.exit(2)

    # Prefer explicit development env so logging/fallback behavior is sane
    app = create_app(env_name="development")

    existing = set(app.view_functions.keys())

    missing = sorted([u for u in used if u not in existing])

    print("Number of endpoints referenced in templates:", len(used))
    print("Number of endpoints registered on Flask app:", len(existing))

    if missing:
        print("\nMissing endpoints referenced in templates (these url_for targets are not registered):")
        for m in missing:
            print(" -", m)
        print("\nRecommendation: For each missing endpoint, either fix the template to use an existing endpoint, or ensure the blueprint that registers it is imported/registered by create_app().")
        sys.exit(3)
    else:
        print("\nNo missing endpoints found. All template url_for(...) targets are present in the running app.")
        sys.exit(0)

if __name__ == "__main__":
    main()