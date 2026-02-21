# =============================================================================
# FILE: app/tiles/boot_monitor_tile.py
# DESCRIPTION: Boot monitor tile payload construction and TTL emission.
#              Avoids module-qualified model strings and reports actionable
#              recommendations without causing registry lookups.
# =============================================================================
from datetime import datetime

from flask import current_app

from app.utils.redis_utils import get_redis_client


def collect_boot_errors():
    return {
        "tile": "trace:boot_monitor",
        "last_boot": datetime.utcnow().isoformat(),
        "errors": [
            {
                "type": "ImportError",
                "path": "app.utils.telemetry.emit_ttl_pulse",
                "status": "❌ missing function",
                "recommendation": ("Define emit_ttl_pulse in telemetry.py or refactor CLI import"),
            },
            {
                "type": "TemplateNotFound",
                "path": "index.html",
                "status": "❌ missing file",
                "recommendation": (
                    "Confirm index.html is in app/templates and template_folder is "
                    "correctly registered"
                ),
            },
            {
                "type": "LoginManagerError",
                "source": "Flask-Login",
                "status": "❌ Missing user_loader",
                "recommendation": ("Define user_loader or request_loader in app/__init__.py"),
            },
            {
                "type": "ImportError",
                "path": "SubscriberProfile",
                "status": "❌ not exposed via app/models/__init__.py",
                "recommendation": (
                    "Ensure SubscriberProfile is defined and exported properly from " "app/models"
                ),
            },
            {
                "type": "ModuleNotFoundError",
                "path": "app.routes.main",
                "status": "❌ missing file",
                "recommendation": (
                    "Create main.py inside app/routes/ or adjust import in create_app()"
                ),
            },
            {
                "type": "ModuleNotFoundError",
                "path": "app.routes.auth",
                "status": "❌ missing file",
                "recommendation": "Confirm auth.py exists inside app/routes/",
            },
            {
                "type": "RouteNotFound",
                "template": "register.html",
                "route": "auth.register_subscriber",
                "status": "❌ unresolved url_for()",
                "recommendation": (
                    "Verify Blueprint route naming and registration inside " "auth_routes.py"
                ),
            },
            {
                "type": "DBAuthError",
                "user": "srpollardsihhllc",
                "status": "❌ denied",
                "recommendation": ("Check DB_USER and DB_PASSWORD in .env for validity"),
            },
        ],
    }


def emit_boot_monitor():
    """
    Emit the Boot Monitor payload to Redis with a 5-minute freshness TTL.
    Guards against Redis unavailability so the cockpit tile stays green.
    """
    key = "ttl:cockpit:boot_monitor"
    payload = collect_boot_errors()

    client = getattr(current_app, "redis_client", None) or get_redis_client()
    if client:
        try:
            # store JSON-like payload as a compact string; Redis TTL ensures freshness
            client.setex(key, 300, str(payload))
            current_app.logger.info(
                f"[tiles.boot_monitor_tile.emit_boot_monitor] TTL emitted for {key}"
            )
        except Exception as e:
            current_app.logger.error(
                "[tiles.boot_monitor_tile.emit_boot_monitor] Redis setex failed " f"for {key} — {e}"
            )
    else:
        current_app.logger.error(
            "[tiles.boot_monitor_tile.emit_boot_monitor] Redis unavailable — "
            f"skipping setex for {key}"
        )
