#!/usr/bin/env python3
"""
Dump a formatted table of all routes owned by the `oauth` blueprint.

Usage:
    python scripts/dump_oauth_routes.py

This imports create_app() from app, instantiates an app, and prints a table
of routes whose endpoint starts with "oauth." (i.e. owned by the oauth blueprint).

It prints:
    - Rule (URL pattern)
    - Methods (GET/POST/...)
    - Endpoint (Flask endpoint name)
    - Defaults (if any)
    - Arguments (variable parts in the rule)
"""
from __future__ import annotations

import sys
from typing import Iterable, List, Tuple

try:
    # Import app factory
    from app import create_app
except Exception as exc:  # pragma: no cover - helpful error message
    print("Failed to import create_app() from app: %s" % exc, file=sys.stderr)
    raise

def collect_oauth_rules(flask_app) -> List[Tuple[str, str, str, str, str]]:
    rows = []
    for rule in sorted(flask_app.url_map.iter_rules(), key=lambda r: (r.rule, sorted(r.methods or []))):
        endpoint = rule.endpoint or ""
        if not endpoint.startswith("oauth."):
            continue
        methods = ",".join(sorted(m for m in (rule.methods or set()) if m not in ("HEAD", "OPTIONS")))
        defaults = repr(rule.defaults) if rule.defaults else ""
        arguments = ",".join(sorted(rule.arguments)) if rule.arguments else ""
        rows.append((rule.rule, methods, endpoint, defaults, arguments))
    return rows

def format_table(rows: Iterable[Tuple[str, str, str, str, str]]) -> str:
    headers = ("Rule", "Methods", "Endpoint", "Defaults", "Arguments")
    col_widths = [max(len(h), 0) for h in headers]
    data = [headers] + list(rows)
    # compute widths
    for row in data:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    sep = "  "
    lines = []
    # header
    header_line = sep.join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    lines.append(header_line)
    lines.append(sep.join("-" * col_widths[i] for i in range(len(headers))))
    # rows
    for row in rows:
        lines.append(sep.join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)))
    return "\n".join(lines)

def main():
    app = create_app()
    with app.app_context():
        rows = collect_oauth_rules(app)
        if not rows:
            print("No routes found for oauth blueprint (endpoints starting with 'oauth.').")
            # Provide a hint: list blueprint keys
            print("\nBlueprints registered on the app:", sorted(app.blueprints.keys()))
            return
        table = format_table(rows)
        print("\nOAuth blueprint route map:\n")
        print(table)
        print("\nTotal oauth routes:", len(rows))

if __name__ == "__main__":
    main()