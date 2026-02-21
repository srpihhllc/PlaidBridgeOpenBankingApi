# =============================================================================
# FILE: app/utils/template_inheritance_audit.py
# DESCRIPTION: Cockpit-grade template inheritance audit for detecting:
#              - wrong base templates
#              - cross-domain inheritance drift
#              - missing parent templates
#              - circular inheritance
#              - subscriber/admin/cockpit boundary violations
# =============================================================================

import json
import logging
import os
import re

from flask import current_app

from app.telemetry.ttl_emit import emit_schema_trace

_logger = logging.getLogger(__name__)

EXTENDS_RE = re.compile(r'{%\s*extends\s*[\'"]([^\'"]+)[\'"]\s*%}')


def audit_template_inheritance(redis_client) -> dict:
    """
    Scans all template directories known to Flask and builds an inheritance graph.
    Detects:
      - missing parent templates
      - circular inheritance
      - cross-domain inheritance drift (admin → subscriber, etc.)
      - templates extending nonexistent files
    """

    summary = {
        "templates_scanned": 0,
        "inheritance_links": 0,
        "missing_parents": 0,
        "cross_domain_violations": 0,
        "circular_inheritance": 0,
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
        # Build a map of all templates
        # ---------------------------------------------------------------------
        template_map: dict[str, str] = {}  # name → absolute path

        for tdir in template_dirs:
            for root, _, files in os.walk(tdir):
                for fname in files:
                    if fname.endswith((".html", ".jinja2")):
                        rel = os.path.relpath(os.path.join(root, fname), tdir)
                        template_map[rel.replace("\\", "/")] = os.path.join(root, fname)

        # ---------------------------------------------------------------------
        # Build inheritance graph
        # ---------------------------------------------------------------------
        parent_map: dict[str, str] = {}  # child → parent

        for rel, abs_path in template_map.items():
            summary["templates_scanned"] += 1

            try:
                with open(abs_path, encoding="utf-8", errors="ignore") as fh:
                    text = fh.read()
            except Exception as e:
                _logger.warning("⚠️ Could not read template %s: %s", abs_path, e)
                summary["errors"] += 1
                continue

            match = EXTENDS_RE.search(text)
            if match:
                parent = match.group(1)
                parent_map[rel] = parent
                summary["inheritance_links"] += 1

        # ---------------------------------------------------------------------
        # Detect missing parents
        # ---------------------------------------------------------------------
        missing_parents = {
            child: parent for child, parent in parent_map.items() if parent not in template_map
        }

        summary["missing_parents"] = len(missing_parents)

        # ---------------------------------------------------------------------
        # Detect circular inheritance
        # ---------------------------------------------------------------------
        def detect_cycle(start: str) -> bool:
            seen = set()
            cur = start
            while cur in parent_map:
                if cur in seen:
                    return True
                seen.add(cur)
                cur = parent_map[cur]
            return False

        cycles = [t for t in parent_map if detect_cycle(t)]
        summary["circular_inheritance"] = len(cycles)

        # ---------------------------------------------------------------------
        # Detect cross-domain inheritance drift
        # ---------------------------------------------------------------------
        def domain_of(path: str) -> str:
            if path.startswith("admin/"):
                return "admin"
            if path.startswith("sub/"):
                return "subscriber"
            if path.startswith("cockpit/"):
                return "cockpit"
            return "global"

        cross_domain = {}

        for child, parent in parent_map.items():
            d_child = domain_of(child)
            d_parent = domain_of(parent)

            if d_child != d_parent and d_parent != "global":
                cross_domain[child] = parent

        summary["cross_domain_violations"] = len(cross_domain)

        # ---------------------------------------------------------------------
        # Emit telemetry
        # ---------------------------------------------------------------------
        emit_schema_trace(
            domain="cli",
            event="template_inheritance",
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
        if missing_parents:
            _logger.error(
                "🚨 Missing parent templates:\n%s",
                json.dumps(missing_parents, indent=2),
            )

        if cycles:
            _logger.error("🚨 Circular inheritance detected:\n%s", json.dumps(cycles, indent=2))

        if cross_domain:
            _logger.error(
                "🚨 Cross-domain inheritance drift:\n%s",
                json.dumps(cross_domain, indent=2),
            )

    except Exception as e:
        _logger.exception("Template inheritance audit failed: %s", e)
        summary["errors"] += 1

        emit_schema_trace(
            domain="cli",
            event="template_inheritance",
            detail="audit_fail",
            value="error",
            status="error",
            ttl=300,
            client=redis_client,
        )

    return summary
