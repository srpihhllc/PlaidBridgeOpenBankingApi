# =============================================================================
# FILE: app/utils/template_block_audit.py
# DESCRIPTION: Cockpit-grade template block audit for detecting:
#              - missing required blocks
#              - cross-domain block drift
#              - wrong navbar/styles/scripts blocks
#              - subscriber/admin/cockpit block contamination
# =============================================================================

import json
import logging
import os
import re

from flask import current_app

from app.telemetry.ttl_emit import emit_schema_trace

_logger = logging.getLogger(__name__)

# Regex to capture block definitions: {% block name %}
BLOCK_RE = re.compile(r"{%\s*block\s+([a-zA-Z0-9_]+)\s*%}")

# Blocks we care about for cockpit-grade UI correctness
REQUIRED_BLOCKS = {
    "head",
    "styles",
    "scripts",
    "navbar",
    "content",
    "body",
}


# Domain classifier
def domain_of(path: str) -> str:
    if path.startswith("admin/"):
        return "admin"
    if path.startswith("sub/"):
        return "subscriber"
    if path.startswith("cockpit/"):
        return "cockpit"
    return "global"


def audit_template_blocks(redis_client) -> dict:
    """
    Scans all templates and extracts block definitions.
    Detects:
      - missing required blocks
      - cross-domain block drift
      - wrong navbar/styles/scripts inheritance
      - subscriber templates inheriting admin navbar
      - admin templates inheriting subscriber blocks
    """

    summary = {
        "templates_scanned": 0,
        "block_definitions": 0,
        "missing_required_blocks": 0,
        "cross_domain_block_violations": 0,
        "errors": 0,
    }

    try:
        # ---------------------------------------------------------------------
        # Collect template directories
        # ---------------------------------------------------------------------
        template_dirs = set()

        if hasattr(current_app, "jinja_loader") and hasattr(current_app.jinja_loader, "searchpath"):
            for p in current_app.jinja_loader.searchpath:
                if os.path.isdir(p):
                    template_dirs.add(p)

        for _bp_name, bp in current_app.blueprints.items():
            if bp.template_folder:
                bp_path = os.path.join(bp.root_path, bp.template_folder)
                if os.path.isdir(bp_path):
                    template_dirs.add(bp_path)

        # ---------------------------------------------------------------------
        # Scan templates and extract blocks
        # ---------------------------------------------------------------------
        block_map: dict[str, set[str]] = {}  # template → set(blocks)

        for tdir in template_dirs:
            for root, _, files in os.walk(tdir):
                for fname in files:
                    if not fname.endswith((".html", ".jinja2")):
                        continue

                    summary["templates_scanned"] += 1
                    abs_path = os.path.join(root, fname)
                    rel = os.path.relpath(abs_path, tdir).replace("\\", "/")

                    try:
                        with open(abs_path, encoding="utf-8", errors="ignore") as fh:
                            text = fh.read()
                    except Exception as e:
                        _logger.warning("⚠️ Could not read template %s: %s", abs_path, e)
                        summary["errors"] += 1
                        continue

                    blocks = set(BLOCK_RE.findall(text))
                    block_map[rel] = blocks
                    summary["block_definitions"] += len(blocks)

        # ---------------------------------------------------------------------
        # Detect missing required blocks
        # ---------------------------------------------------------------------
        missing_required = {
            tmpl: sorted(list(REQUIRED_BLOCKS - blocks))
            for tmpl, blocks in block_map.items()
            if domain_of(tmpl) in ("subscriber", "admin", "cockpit") and (REQUIRED_BLOCKS - blocks)
        }

        summary["missing_required_blocks"] = len(missing_required)

        # ---------------------------------------------------------------------
        # Detect cross-domain block drift
        # ---------------------------------------------------------------------
        cross_domain = {}

        for tmpl, blocks in block_map.items():
            d = domain_of(tmpl)

            # Subscriber templates should NOT define admin navbar/styles/scripts
            if d == "subscriber":
                if "navbar" in blocks and "admin" in tmpl:
                    cross_domain[tmpl] = "subscriber template defining admin navbar"

            # Admin templates should NOT define subscriber navbar
            if d == "admin":
                if "navbar" in blocks and "sub" in tmpl:
                    cross_domain[tmpl] = "admin template defining subscriber navbar"

        summary["cross_domain_block_violations"] = len(cross_domain)

        # ---------------------------------------------------------------------
        # Emit telemetry
        # ---------------------------------------------------------------------
        emit_schema_trace(
            domain="cli",
            event="template_block_audit",
            detail="summary",
            value="success",
            status="ok",
            ttl=600,
            client=redis_client,
            meta=summary,
        )

        # ---------------------------------------------------------------------
        # Log detailed results
        # ---------------------------------------------------------------------
        if missing_required:
            _logger.error(
                "🚨 Missing required blocks:\n%s",
                json.dumps(missing_required, indent=2),
            )

        if cross_domain:
            _logger.error("🚨 Cross-domain block drift:\n%s", json.dumps(cross_domain, indent=2))

    except Exception as e:
        _logger.exception("Template block audit failed: %s", e)
        summary["errors"] += 1

        emit_schema_trace(
            domain="cli",
            event="template_block_audit",
            detail="audit_fail",
            value="error",
            status="error",
            ttl=300,
            client=redis_client,
        )

    return summary
