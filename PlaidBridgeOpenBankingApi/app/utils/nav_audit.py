# app/utils/nav_audit.py

"""
Template navigation auditor.

Scans navbar.html and all templates for url_for() endpoint references,
then reports which endpoints are missing from the Flask app registry.

Designed for operator clarity, safe logging, and mypy correctness.
"""

import os
import re
from typing import Any

from flask import current_app

# Matches url_for('blueprint.endpoint') or url_for("blueprint.endpoint")
URL_FOR_REGEX = re.compile(r"url_for\(\s*['\"]([\w\.]+)['\"]")


def _extract_endpoints_from_html(html: str) -> set[str]:
    """Return all url_for() endpoint references found in a template."""
    return set(URL_FOR_REGEX.findall(html))


def _read_file(path: str) -> str:
    """Read a UTF‑8 file safely."""
    with open(path, encoding="utf-8") as f:
        return f.read()


def audit_navbar(app) -> dict[str, Any]:
    """
    Audit the navbar.html file for referenced endpoints and report which
    ones are missing from the Flask app's view registry.
    """
    template_folder = app.template_folder
    navbar_path = os.path.join(template_folder, "navbar.html")

    result: dict[str, Any] = {
        "file": navbar_path,
        "endpoints_in_nav": [],
        "missing_endpoints": [],
    }

    html = _read_file(navbar_path)
    endpoints = sorted(_extract_endpoints_from_html(html))
    result["endpoints_in_nav"] = endpoints

    missing = [ep for ep in endpoints if ep not in app.view_functions]
    result["missing_endpoints"] = sorted(missing)

    return result


def audit_templates(app) -> dict[str, Any]:
    """
    Recursively scan all templates for url_for() endpoint references.
    Returns a structured report of referenced endpoints and missing ones.
    """
    template_root = app.template_folder
    all_eps: set[str] = set()

    for root, _dirs, files in os.walk(template_root):
        for fn in files:
            if not fn.endswith(".html"):
                continue

            full_path = os.path.join(root, fn)

            try:
                html = _read_file(full_path)
                all_eps |= _extract_endpoints_from_html(html)

            except Exception as e:
                # Non‑fatal: log and continue
                current_app.logger.debug(f"Template scan skipped {full_path}: {e}")

    missing = sorted(ep for ep in all_eps if ep not in app.view_functions)

    return {
        "scanned_templates": template_root,
        "referenced_endpoints": sorted(all_eps),
        "missing_endpoints": missing,
    }


def run():
    """
    Compatibility wrapper so scripts/audit.py can call nav_audit.run().
    Creates a temporary app using the project's factory and runs the
    template/navigation audit inside an application context, printing JSON.
    """
    from app import create_app
    import json

    app = create_app()
    with app.app_context():
        report = audit_templates(app)
        print(json.dumps(report, indent=2))
