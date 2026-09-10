# =============================================================================
# FILE: app/utils/template_block_audit.py
# =============================================================================

import json
import logging
import re

from flask import current_app

from app.telemetry.ttl_emit import emit_schema_trace

_logger = logging.getLogger(__name__)

BLOCK_RE = re.compile(r"{%\s*block\s+([a-zA-Z0-9_]+)\s*%}")
REQUIRED_BLOCKS = {"head", "styles", "scripts", "navbar", "content", "body"}


def domain_of(t_name: str) -> str:
    if t_name.startswith("admin/"):
        return "admin"
    if t_name.startswith("sub/"):
        return "subscriber"
    if t_name.startswith("cockpit/"):
        return "cockpit"
    return "global"


def audit_template_blocks(redis_client) -> dict:
    summary = {
        "templates_scanned": 0,
        "block_definitions": 0,
        "missing_required_blocks": 0,
        "cross_domain_block_violations": 0,
        "errors": 0,
    }

    try:
        env = current_app.jinja_env
        block_map: dict[str, set[str]] = {}

        # 1. Scan templates using Jinja's native registry
        for t_name in env.list_templates():
            if not t_name.endswith((".html", ".jinja2")):
                continue

            summary["templates_scanned"] += 1
            try:
                source, _, _ = env.loader.get_source(env, t_name)
                blocks = set(BLOCK_RE.findall(source))
                block_map[t_name] = blocks
                summary["block_definitions"] += len(blocks)
            except Exception as e:
                _logger.warning("⚠️ Could not read template %s: %s", t_name, e)
                summary["errors"] += 1
                continue

        # 2. Detect missing required blocks
        missing_required = {
            tmpl: sorted(list(REQUIRED_BLOCKS - blocks))
            for tmpl, blocks in block_map.items()
            if domain_of(tmpl) in ("subscriber", "admin", "cockpit")
            and (REQUIRED_BLOCKS - blocks)
        }
        summary["missing_required_blocks"] = len(missing_required)

        # 3. Detect cross-domain block drift
        cross_domain = {}
        for tmpl, blocks in block_map.items():
            d = domain_of(tmpl)
            if d == "subscriber" and "navbar" in blocks and "admin" in tmpl:
                cross_domain[tmpl] = (
                    "subscriber template defining admin navbar"
                )
            if d == "admin" and "navbar" in blocks and "sub" in tmpl:
                cross_domain[tmpl] = (
                    "admin template defining subscriber navbar"
                )

        summary["cross_domain_block_violations"] = len(cross_domain)

        # 4. Telemetry
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

        if missing_required:
            _logger.error(
                "🚨 Missing required blocks:\n%s",
                json.dumps(missing_required, indent=2),
            )
        if cross_domain:
            _logger.error(
                "🚨 Cross-domain block drift:\n%s",
                json.dumps(cross_domain, indent=2),
            )

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
