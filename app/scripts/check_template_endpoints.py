#!/usr/bin/env python3
"""
Check template url_for endpoints against app.view_functions.
Outputs missing endpoints and the templates that reference them.
"""
import re
import sys
from pathlib import Path
from flask import Flask
from app import create_app

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app" / "templates"
PAT = re.compile(r"url_for\(\s*['\"]([^'\"]+)['\"]")

def find_template_endpoints():
    refs = {}
    for tpl in TEMPLATES.rglob("*.html"):
        text = tpl.read_text(encoding="utf-8", errors="ignore")
        for m in PAT.findall(text):
            refs.setdefault(m, set()).add(str(tpl.relative_to(TEMPLATES)))
    return refs

def main():
    app = create_app(env_name="development")
    existing = set(app.view_functions.keys())
    refs = find_template_endpoints()
    missing = {ep: files for ep, files in refs.items() if ep not in existing}
    if not missing:
        print("All template url_for endpoints exist.")
        return 0
    print("Missing endpoints referenced by templates:")
    for ep, files in sorted(missing.items()):
        print(f"\n- {ep}")
        for f in sorted(files):
            print(f"    {f}")
    return 1

if __name__ == "__main__":
    sys.exit(main())
