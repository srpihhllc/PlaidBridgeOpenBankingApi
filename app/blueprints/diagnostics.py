# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/blueprints/diagnostics.py

import os
import time
from functools import wraps

from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from flask import Blueprint, current_app, jsonify, render_template
from flask_login import login_required
from sqlalchemy import text

from app.config import get_config
from app.decorators import admin_required
from app.models import Transaction, User, db
from app.utils.redis_utils import get_redis_client

diagnostics_bp = Blueprint("diagnostics", __name__, url_prefix="/diagnostics")

# =============================================================================
# COCKPIT-GRADE UTILITIES
# =============================================================================


def cli_safe_auth(f):
    """
    🛡️ Cockpit-Grade Bypass Decorator
    If DIAGNOSTICS_CLI_MODE is True (set by CLI), we skip Flask-Login/Admin checks.
    Otherwise, we enforce full production security for web requests.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_app.config.get("DIAGNOSTICS_CLI_MODE"):
            return f(*args, **kwargs)

        @login_required
        @admin_required
        def wrapper():
            return f(*args, **kwargs)

        return wrapper()

    return decorated_function


# =============================================================================
# DIAGNOSTIC ROUTES
# =============================================================================


@diagnostics_bp.route("/console")
@login_required
@admin_required
def neural_console():
    """Renders the central admin cockpit UI."""
    return render_template("admin/neural_console.html")


@diagnostics_bp.route("/full")
@cli_safe_auth
def get_full_diagnostics():
    """
    The Unified /full Endpoint.
    Consolidates Performance, Integrity, Configuration, and Statistics.
    """
    config_obj = get_config()
    start_total = time.time()

    # Threshold for 'Degraded' state detection
    LATENCY_THRESHOLD_MS = 200

    # 1. Database Performance & Connectivity
    db_connected = False
    db_message = "Handshake successful"
    db_latency_ms = 0
    try:
        start_db = time.time()
        db.session.execute(text("SELECT 1"))
        db_latency_ms = round((time.time() - start_db) * 1000, 2)
        db_connected = True
    except Exception as e:
        db_message = str(e)

    # 2. Redis Performance & Connectivity
    redis_ok = False
    redis_msg = "Handshake successful"
    redis_latency_ms = 0
    try:
        redis_client = get_redis_client()
        start_redis = time.time()
        if redis_client.ping():
            redis_latency_ms = round((time.time() - start_redis) * 1000, 2)
            redis_ok = True
    except Exception as e:
        redis_msg = str(e)

    # 3. Migration Integrity (The Fixed Snippet)
    current_head = "Unknown"
    current_db_rev = "Unknown"
    try:
        # ⭐ Force look for alembic.ini in the current working directory (Project Root)
        project_root = os.getcwd()
        alembic_ini_path = os.path.join(project_root, "alembic.ini")

        if os.path.exists(alembic_ini_path):
            alembic_cfg = AlembicConfig(alembic_ini_path)
            script = ScriptDirectory.from_config(alembic_cfg)
            current_head = script.get_current_head()

            with db.engine.connect() as conn:
                context = MigrationContext.configure(conn)
                current_db_rev = context.get_current_revision()
        else:
            current_head = f"alembic.ini not found at {project_root}"
            current_db_rev = "N/A"
    except Exception as e:
        current_head = f"Error: {str(e)}"
        current_db_rev = "Error"

    # Normalize revisions
    invalid_states = [None, "Unknown", "Error", "N/A"]
    normalized_head = str(current_head).strip()
    normalized_db = str(current_db_rev).strip()
    migration_synced = normalized_head not in invalid_states and normalized_head == normalized_db

    # 4. Model Statistics
    try:
        db_stats = {
            "total_users": User.query.count(),
            "unapproved_users": User.query.filter_by(is_approved=False).count(),
            "orphaned_transactions": Transaction.query.filter_by(user_id=None).count(),
        }
    except Exception:
        db_stats = {"error": "Stats unavailable"}

    # 5. Cache Stats
    try:
        redis = get_redis_client()
        keys = redis.keys("*")
        cache_stats = {
            "total_keys": len(keys),
            "volatile_alerts": sum(
                1
                for k in keys
                if redis.ttl(k) == -1 and k.decode().startswith(("mfa", "rate", "session"))
            ),
        }
    except Exception:
        cache_stats = {"error": "Cache stats unavailable"}

    return (
        jsonify(
            {
                "meta": {
                    "timestamp": time.time(),
                    "generation_ms": round((time.time() - start_total) * 1000, 2),
                    "app_version": current_app.config.get("APP_VERSION", "1.0.0"),
                    "env": current_app.config.get("ENV", "production"),
                    "maintenance_mode": current_app.config.get("MAINTENANCE_MODE", False),
                },
                "infra": {
                    "database": {
                        "online": db_connected,
                        "latency_ms": db_latency_ms,
                        "degraded": (
                            db_latency_ms > LATENCY_THRESHOLD_MS if db_connected else False
                        ),
                        "message": db_message,
                    },
                    "redis": {
                        "online": redis_ok,
                        "latency_ms": redis_latency_ms,
                        "degraded": (
                            redis_latency_ms > LATENCY_THRESHOLD_MS if redis_ok else False
                        ),
                        "message": redis_msg,
                    },
                },
                "integrity": {
                    "alembic_head": normalized_head,
                    "db_revision": normalized_db,
                    "synced": migration_synced,
                },
                "stats": {"db": db_stats, "cache": cache_stats},
                "config_summary": config_obj.summarize(),
            }
        ),
        200,
    )


# --- Standard UI Routes ---


@diagnostics_bp.route("/routes")
@login_required
@admin_required
def route_list():
    """Returns a visual map of all registered application routes."""
    routes = [
        {
            "endpoint": r.endpoint,
            "methods": list(r.methods - {"HEAD", "OPTIONS"}),
            "url": str(r),
        }
        for r in current_app.url_map.iter_rules()
    ]
    routes.sort(key=lambda r: r["url"])
    return render_template("admin/route_list.html", routes=routes)


@diagnostics_bp.route("/db_health")
@login_required
@admin_required
def db_health():
    """Renders a detailed health check for the database."""
    return render_template(
        "admin/db_health.html",
        total_users=User.query.count(),
        orphaned_tx=Transaction.query.filter_by(user_id=None).all(),
    )
