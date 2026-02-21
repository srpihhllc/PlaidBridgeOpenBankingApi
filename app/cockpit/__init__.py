# =============================================================================
# FILE: app/cockpit/__init__.py
# DESCRIPTION: Registers cockpit blueprints with fault-tolerant logging
#              and cockpit‑grade TTL pulses.
# =============================================================================

import logging

from app.constants.telemetry_keys import REDIS_FAIL_TTL, REDIS_QUEUE_FLUSH_TTL
from app.telemetry.ttl_emit import safe_emit, ttl_emit
from app.utils.redis_utils import get_redis_client

logger = logging.getLogger(__name__)

# Wrap ttl_emit so it never raises through safe_import
ttl_emit = safe_emit(ttl_emit)


def _emit_cockpit_pulse(ttl_key: str, status: str, ttl: int):
    """
    Emit one cockpit pulse under key `ttl:boot:cockpit:{ttl_key}`.
    Falls back to queuing if Redis is down.
    """
    try:
        client = get_redis_client()
        ttl_emit(key=f"ttl:boot:cockpit:{ttl_key}", status=status, client=client, ttl=ttl)
    except Exception as exc:
        # client=None will queue the emit
        ttl_emit(key=f"ttl:boot:cockpit:{ttl_key}", status=status, client=None, ttl=ttl)
        logger.debug(f"Cockpit pulse queued [{ttl_key}]: {status} ({exc})")


def safe_import(module_path: str, attr_name: str, ttl_key: str):
    """
    Attempt to import `attr_name` from `module_path` without blowing up.
    Emits one TTL pulse (1800s on success; 900s on error).
    """
    try:
        module = __import__(module_path, fromlist=[attr_name])
        bp = getattr(module, attr_name)
        _emit_cockpit_pulse(ttl_key, "success", REDIS_QUEUE_FLUSH_TTL)
        return bp

    except Exception as e:
        logger.error(f"❌ Failed to import {module_path}.{attr_name}: {e}")
        _emit_cockpit_pulse(ttl_key, f"error:{str(e)[:64]}", REDIS_FAIL_TTL)
        return None


# Safe imports — missing tiles won’t crash the package
# Point directly at telemetry_dashboard.py where cockpit_bp is defined
cockpit_bp = safe_import("app.cockpit.routes.telemetry_dashboard", "cockpit_bp", "cockpit_bp")

trace_bp = safe_import("app.admin.cockpit.trace.event_id", "trace_bp", "trace_bp")
fk_inspector_bp = safe_import(
    "app.cockpit.tiles.fk_constraint_inspector", "fk_inspector_bp", "fk_inspector_bp"
)
drilldown_bp = safe_import("app.cockpit.routes.drilldown", "drilldown_bp", "drilldown_bp")


def register_cockpit_tiles(app):
    """Registers the Flask blueprints for the cockpit's tiles."""
    for name, bp in [
        ("cockpit_bp", cockpit_bp),
        ("trace_bp", trace_bp),
        ("fk_inspector_bp", fk_inspector_bp),
        ("drilldown_bp", drilldown_bp),
    ]:
        if bp:
            try:
                # Guard against duplicate registration
                if bp.name in app.blueprints:
                    app.logger.warning(f"⚠️ Skipping duplicate cockpit tile: {name}")
                    continue
                app.register_blueprint(bp)
                app.logger.info(f"✅ Registered cockpit tile: {name}")
            except Exception as e:
                app.logger.error(f"❌ Failed to register cockpit tile '{name}': {e}")
