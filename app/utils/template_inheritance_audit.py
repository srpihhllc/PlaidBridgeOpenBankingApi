# =============================================================================
# FILE: app/utils/template_inheritance_audit.py
# DESCRIPTION: Cockpit-grade template inheritance audit with path-aware domain resolution.
# =============================================================================

import json
import logging
import re

from flask import current_app

from app.telemetry.ttl_emit import emit_schema_trace

_logger = logging.getLogger(__name__)

EXTENDS_RE = re.compile(r'{%\s*extends\s*[\'"]([^\'"]+)[\'"]\s*%}')


def audit_template_inheritance(redis_client) -> dict:
    """
    Scans all template directories known to Flask and builds an inheritance graph.
    Uses both Jinja namespacing and physical file paths to detect:
      - missing parent templates
      - circular inheritance
      - cross-domain inheritance drift
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
        # 1. Ask Jinja for the exact, namespaced template map
        # ---------------------------------------------------------------------
        template_map: dict[str, str] = {}  # child_name → exact text source
        file_map: dict[str, str] = {}  # child_name → absolute physical path
        env = current_app.jinja_env

        for t_name in env.list_templates():
            if t_name.endswith((".html", ".jinja2")):
                try:
                    # get_source returns (source_code, absolute_filename, uptodate_function)
                    source, filename, _ = env.loader.get_source(env, t_name)
                    template_map[t_name] = source
                    if filename:
                        file_map[t_name] = filename
                except Exception as e:
                    _logger.warning(
                        "⚠️ Could not read template %s: %s", t_name, e
                    )
                    summary["errors"] += 1
                    continue

        # ---------------------------------------------------------------------
        # 2. Build inheritance graph
        # ---------------------------------------------------------------------
        parent_map: dict[str, str] = {}  # child → parent

        for rel, text in template_map.items():
            summary["templates_scanned"] += 1

            match = EXTENDS_RE.search(text)
            if match:
                parent = match.group(1)
                parent_map[rel] = parent
                summary["inheritance_links"] += 1

        # ---------------------------------------------------------------------
        # Detect missing parents
        # ---------------------------------------------------------------------
        missing_parents = {
            child: parent
            for child, parent in parent_map.items()
            if parent not in template_map
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
        def domain_of(t_name: str) -> str:
            # 1. Check logical Jinja namespace first (e.g., "admin/admin.html")
            if t_name.startswith("admin/"):
                return "admin"
            if t_name.startswith("sub/"):
                return "subscriber"
            if t_name.startswith("cockpit/"):
                return "cockpit"

            # 2. Fallback: Check absolute physical path on disk
            # (Handles flat structures in blueprint template folders)
            filepath = file_map.get(t_name, "").replace("\\", "/")
            if "/admin" in filepath:
                return "admin"
            if "/sub" in filepath or "/subscriber" in filepath:
                return "subscriber"
            if "/cockpit" in filepath:
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
        # Emit telemetry & Log results
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

        if missing_parents:
            _logger.error(
                "🚨 Missing parent templates:\n%s",
                json.dumps(missing_parents, indent=2),
            )
        if cycles:
            _logger.error(
                "🚨 Circular inheritance detected:\n%s",
                json.dumps(cycles, indent=2),
            )
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
