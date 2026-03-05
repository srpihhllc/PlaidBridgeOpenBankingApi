# =============================================================================
# FILE: app/utils/template_audit.py
# DESCRIPTION: Cockpit-grade template wiring audit for route-template alignment,
#              endpoint validity, and Jinja context checks with schema-based TTL
#              telemetry for cockpit dashboards.
# =============================================================================

import json
import logging
import os
import re
from typing import Any

import redis
from flask import current_app

from app.telemetry.ttl_emit import emit_schema_trace

_logger = logging.getLogger(__name__)

URL_FOR_RE = re.compile(r"url_for\(\s*[\"']([^\"']+)[\"']")


def audit_template_wiring(redis_client: redis.Redis) -> dict[str, int]:
    """
    Audit template context, route-template alignment, and endpoint validity.
    Scans ALL template directories known to Flask (including blueprint folders),
    emits schema-based TTL traces, and returns a structured summary.
    """

    summary: dict[str, int] = {
        "templates_scanned": 0,
        "endpoints_found": 0,
        "missing_endpoints": 0,
        "errors": 0,
    }

    try:
        # ---------------------------------------------------------------------
        # Jinja Context Check
        # ---------------------------------------------------------------------
        env: Any = getattr(current_app, "jinja_env", None)
        if env is None or not hasattr(env, "globals"):
            emit_schema_trace(
                domain="cli",
                event="template_audit",
                detail="missing_app_context",
                value="error",
                status="error",
                ttl=300,
                client=redis_client,
                meta={"reason": "missing_app_context"},
            )
            _logger.warning("🧩 Jinja environment missing or has no 'globals'.")
            summary["errors"] += 1
            jinja_globals: dict[str, Any] = {}
        else:
            jinja_globals = env.globals  # type: ignore[assignment]
            if "app" not in jinja_globals:
                emit_schema_trace(
                    domain="cli",
                    event="template_audit",
                    detail="missing_app_context",
                    value="error",
                    status="error",
                    ttl=300,
                    client=redis_client,
                    meta={"reason": "missing_app_context"},
                )
                _logger.warning("🧩 Jinja context missing 'app'.")
                summary["errors"] += 1
            else:
                emit_schema_trace(
                    domain="cli",
                    event="template_audit",
                    detail="missing_app_context",
                    value="success",
                    status="ok",
                    ttl=300,
                    client=redis_client,
                )

        # ---------------------------------------------------------------------
        # Collect ALL template directories Flask knows about
        # ---------------------------------------------------------------------
        template_dirs: set[str] = set()

        # 1. Global template folder (app/templates)
        if hasattr(current_app, "jinja_loader") and hasattr(current_app.jinja_loader, "searchpath"):
            for p in current_app.jinja_loader.searchpath:
                if os.path.isdir(p):
                    template_dirs.add(p)

        # 2. Blueprint template folders
        for _, bp in current_app.blueprints.items():
            if bp.template_folder:
                bp_path = os.path.join(bp.root_path, bp.template_folder)
                if os.path.isdir(bp_path):
                    template_dirs.add(bp_path)

        if not template_dirs:
            _logger.warning("⚠️ No template directories found via Flask loader.")
            summary["errors"] += 1

        # ---------------------------------------------------------------------
        # Endpoint Link Audit
        # ---------------------------------------------------------------------
        endpoints = {rule.endpoint for rule in current_app.url_map.iter_rules()}
        missing: dict[str, set[str]] = {}

        for tdir in template_dirs:
            for root, _, files in os.walk(tdir):
                for fname in files:
                    if not fname.endswith((".html", ".jinja2")):
                        continue

                    summary["templates_scanned"] += 1
                    path = os.path.join(root, fname)

                    try:
                        with open(path, encoding="utf-8", errors="ignore") as fh:
                            text = fh.read()
                    except Exception as read_err:
                        _logger.warning("⚠️ Could not read template %s: %s", path, read_err)
                        summary["errors"] += 1
                        continue

                    for ep in URL_FOR_RE.findall(text):
                        summary["endpoints_found"] += 1
                        if ep not in endpoints:
                            missing.setdefault(path, set()).add(ep)

        # ---------------------------------------------------------------------
        # Missing Endpoint Telemetry
        # ---------------------------------------------------------------------
        if missing:
            emit_schema_trace(
                domain="cli",
                event="template_audit",
                detail="missing_endpoints",
                value="error",
                status="error",
                ttl=300,
                client=redis_client,
            )

            serializable_missing = {k: sorted(list(v)) for k, v in missing.items()}
            _logger.error(
                "🚨 Missing endpoints:\n%s",
                json.dumps(serializable_missing, indent=2),
            )
            summary["missing_endpoints"] = sum(len(v) for v in missing.values())
        else:
            emit_schema_trace(
                domain="cli",
                event="template_audit",
                detail="missing_endpoints",
                value="success",
                status="ok",
                ttl=300,
                client=redis_client,
            )
            _logger.info("✅ All template endpoints are valid.")

    except Exception as e:
        _logger.exception("Template wiring audit failed: %s", e)
        emit_schema_trace(
            domain="cli",
            event="template_audit",
            detail="audit_fail",
            value="error",
            status="error",
            ttl=300,
            client=redis_client,
        )
        summary["errors"] += 1

    # -------------------------------------------------------------------------
    # Aggregation Telemetry
    # -------------------------------------------------------------------------
    try:
        redis_client.hincrby(
            "template_audit:aggregate",
            "templates_scanned",
            summary["templates_scanned"],
        )
        redis_client.hincrby(
            "template_audit:aggregate",
            "endpoints_found",
            summary["endpoints_found"],
        )
        redis_client.hincrby(
            "template_audit:aggregate",
            "missing_endpoints",
            summary["missing_endpoints"],
        )
        redis_client.hincrby(
            "template_audit:aggregate",
            "errors",
            summary["errors"],
        )

        emit_schema_trace(
            domain="cli",
            event="template_audit",
            detail="summary",
            value="success",
            status="ok",
            ttl=600,
            client=redis_client,
            meta=summary,
        )

    except Exception as agg_err:
        _logger.warning("⚠️ Could not update Redis aggregation: %s", agg_err)

    return summary


def run():
    """
    Compatibility wrapper so scripts/audit.py can call template_audit.run().
    Runs audit_template_wiring() within the current application context,
    using a no-op Redis stub when no real client is available.
    """
    from app.utils.redis_utils import get_redis_client

    redis_client = get_redis_client()
    summary = audit_template_wiring(redis_client)
    _logger.info("Template audit summary: %s", summary)
