# =============================================================================
# FILE: app/utils/template_audit.py
# DESCRIPTION: Cockpit-grade template wiring audit using Jinja native discovery.
#              Tracks granular drift details and emits Redis telemetry.
# =============================================================================

import json
import logging
import re
from typing import Any, Dict

import redis
from flask import current_app

from app.telemetry.ttl_emit import emit_schema_trace

_logger = logging.getLogger(__name__)

# Refined regex: ignores Jinja comments {# ... #} and standard comments #
URL_FOR_RE = re.compile(r"(?<!{#)(?<!#)\burl_for\(\s*[\"']([^\"']+)[\"']")


def run_template_audit(redis_client: redis.Redis = None) -> Dict[str, Any]:
    """
    Audits template-route alignment by scanning the active Jinja environment.
    Emits schema-based TTL traces for cockpit dashboard monitoring and returns
    granular drift details for debugging.
    """
    summary: Dict[str, Any] = {
        "templates_scanned": 0,
        "endpoints_found": 0,
        "missing_endpoints": 0,
        "errors": 0,
        "drift_details": [],
    }

    # -------------------------------------------------------------------------
    # 1. Jinja Context Validation
    # -------------------------------------------------------------------------
    env = getattr(current_app, "jinja_env", None)
    if env is None or not hasattr(env, "globals"):
        _logger.warning("🧩 Jinja environment missing or invalid.")
        summary["errors"] += 1
        if redis_client:
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
        return summary

    # -------------------------------------------------------------------------
    # 2. Endpoint Link Audit (Jinja Native)
    # -------------------------------------------------------------------------
    # Extract all valid endpoints registered in the Flask app
    valid_endpoints = {
        rule.endpoint for rule in current_app.url_map.iter_rules()
    }
    missing_dict: dict[str, set[str]] = {}

    # Scan exactly what Jinja sees (handles Blueprints and Global folders)
    for t_name in env.list_templates():
        if not t_name.endswith((".html", ".htm", ".jinja2")):
            continue

        summary["templates_scanned"] += 1

        try:
            # Resolve source via the registered loader
            source, _, _ = env.loader.get_source(env, t_name)
        except Exception as e:
            _logger.warning("⚠️ Could not read template %s: %s", t_name, e)
            summary["errors"] += 1
            continue

        # Identify dangling url_for references
        for ep in URL_FOR_RE.findall(source):
            # Static files are handled implicitly, ignore them
            if ep == "static":
                continue

            summary["endpoints_found"] += 1
            if ep not in valid_endpoints:
                missing_dict.setdefault(t_name, set()).add(ep)
                summary["drift_details"].append(
                    {"template": t_name, "broken_endpoint": ep}
                )

    # -------------------------------------------------------------------------
    # 3. Telemetry & Reporting
    # -------------------------------------------------------------------------
    if missing_dict:
        if redis_client:
            emit_schema_trace(
                domain="cli",
                event="template_audit",
                detail="missing_endpoints",
                value="error",
                status="error",
                ttl=300,
                client=redis_client,
            )
        serializable_missing = {
            k: sorted(list(v)) for k, v in missing_dict.items()
        }
        _logger.error(
            "🚨 Missing endpoints:\n%s",
            json.dumps(serializable_missing, indent=2),
        )
        summary["missing_endpoints"] = sum(
            len(v) for v in missing_dict.values()
        )
    else:
        if redis_client:
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

    # -------------------------------------------------------------------------
    # 4. Persistence to Aggregation
    # -------------------------------------------------------------------------
    if redis_client:
        try:
            agg = "template_audit:aggregate"
            for key in [
                "templates_scanned",
                "endpoints_found",
                "missing_endpoints",
                "errors",
            ]:
                redis_client.hincrby(agg, key, summary[key])

            # Strip drift_details from the meta payload to prevent Redis bloat
            meta_summary = {
                k: v for k, v in summary.items() if k != "drift_details"
            }
            emit_schema_trace(
                domain="cli",
                event="template_audit",
                detail="summary",
                value="success",
                status="ok",
                ttl=600,
                client=redis_client,
                meta=meta_summary,
            )
        except Exception as agg_err:
            _logger.warning(
                "⚠️ Could not update Redis aggregation: %s", agg_err
            )

    return summary


# -----------------------------------------------------------------------------
# 5. Backward Compatibility Export
# -----------------------------------------------------------------------------
# Maps legacy imports referencing audit_template_wiring directly to the unified runner
audit_template_wiring = run_template_audit
