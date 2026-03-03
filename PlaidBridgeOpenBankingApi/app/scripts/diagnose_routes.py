#!/usr/bin/env python3
"""
Lightweight route wiring diagnostic.

- Creates the Flask app using the 'testing' config.
- Iterates app.url_map rules.
- Skips rules with path variables (those require parameters).
- Skips static endpoints.
- Issues GET requests (no follow) to each simple route and records status/location.
- Outputs CSV to stdout: endpoint,rule,methods,status,location,notes

Run from repo root with PYTHONPATH set so the nested package imports correctly.
"""
from app import create_app
from urllib.parse import urljoin
import sys
import json
import traceback

def main():
    app = create_app("testing")
    app.testing = True

    results = []
    with app.test_client() as client:
        for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
            # Skip static files and flask internal endpoints
            if rule.endpoint.startswith("static"):
                continue

            # Skip rules with path variables (e.g. /user/<id>)
            if rule.arguments:
                results.append({
                    "endpoint": rule.endpoint,
                    "rule": rule.rule,
                    "methods": sorted(list(rule.methods)),
                    "status": "SKIPPED-VARIABLES",
                    "location": "",
                    "notes": "requires path parameters (skipped)"
                })
                continue

            # Try only safe methods: GET (avoid POST, DELETE, etc.)
            if "GET" not in rule.methods:
                results.append({
                    "endpoint": rule.endpoint,
                    "rule": rule.rule,
                    "methods": sorted(list(rule.methods)),
                    "status": "SKIPPED-NONGET",
                    "location": "",
                    "notes": "no GET method"
                })
                continue

            try:
                resp = client.get(rule.rule, follow_redirects=False)
                status = resp.status_code
                loc = resp.headers.get("Location", "")
                notes = ""
                # If it's a redirect back to auth.login or /auth/login, flag it
                if loc and ("auth/login" in loc or loc.endswith("/auth/login") or "auth.login" in loc):
                    notes = "redirects-to-login"
                # If 500, capture first part of body
                if status >= 500:
                    snippet = resp.get_data(as_text=True)[:400].replace("\n", "\\n")
                    notes = (notes + " ERROR_BODY: " + snippet).strip()
                results.append({
                    "endpoint": rule.endpoint,
                    "rule": rule.rule,
                    "methods": sorted(list(rule.methods)),
                    "status": status,
                    "location": loc,
                    "notes": notes,
                })
            except Exception as e:
                tb = traceback.format_exc().splitlines()[-1]
                results.append({
                    "endpoint": rule.endpoint,
                    "rule": rule.rule,
                    "methods": sorted(list(rule.methods)),
                    "status": "EXCEPTION",
                    "location": "",
                    "notes": str(tb),
                })

    # Print CSV header then JSON for easy parsing if needed
    print("endpoint,rule,methods,status,location,notes")
    for r in results:
        methods = "|".join(r["methods"])
        # escape commas in notes/location
        loc = r["location"].replace(",", "%2C")
        notes = r["notes"].replace(",", "%2C")
        print(f'{r["endpoint"]},{r["rule"]},{methods},{r["status"]},{loc},{notes}')

    # Also dump JSON to stderr for richer info
    print(file=sys.stderr)
    print(json.dumps(results, indent=2), file=sys.stderr)

if __name__ == "__main__":
    main()
