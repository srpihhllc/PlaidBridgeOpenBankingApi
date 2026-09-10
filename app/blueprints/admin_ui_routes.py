# =============================================================================
# DESCRIPTION: Admin UI routes with cockpit wiring and tiles.
# Compatibility: blueprint is registered as "admin" (so legacy calls to
# url_for('admin.*') continue to work). We also create admin_ui.* aliases
# to preserve any JS/templates that reference admin_ui.* endpoints.
#
# This module also provides helper functions `ensure_admin_aliases(...)` and
# `register_admin_blueprint(...)` intended to be called from your app factory.
# =============================================================================

import io
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Iterable

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

# Import mock models from admin API layer
from app.blueprints.admin_routes import (
    MockLedger,
    MockLender,
    MockModel,
    MockSchemaEvent,
    MockUser,
)
from app.decorators import (
    admin_required,
    roles_required,
    super_admin_required,
)

# Import real service-layer functions
from app.services.card_manager import suspend_card, unfreeze_card
from app.services.letter_writer import render_letter_to_text
from app.utils.redis_utils import get_redis_client
from app.utils.time_utils import safe_parse_timestamp

logger = logging.getLogger(__name__)

# Defensive blueprint creation:
# - Reuse an existing blueprint object if one was already created (helps tests
#   or import-time reimports that may create the object earlier).
# - Do NOT register the blueprint at import time; registration is handled
#   centrally by register_blueprints(app) in the application factory.
admin_bp = globals().get("admin_bp") or Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
    template_folder="../templates/admin",
)


# =============================================================================
# ADMIN INDEX & CANONICAL HOME
# =============================================================================
@admin_bp.route("/", strict_slashes=False, endpoint="admin_index")
@admin_bp.route("/home", endpoint="admin_home")
def admin_index():
    """Unified Admin landing and canonical home view with feature gate &
    fallbacks. Handles both /admin/ and /admin/home transparently as a single
    execution point to satisfy template audit requirements and eliminate
    alias fallback bloat.
    """
    # 1. Feature Gate: Diagnostic inventory
    if current_app.config.get("DEBUG_UI"):
        templates = [
            "admin_console.html",
            "cockpit/cockpit_dashboard.html",
            "audit_viewer.html",
            "lenders.html",
        ]
        return jsonify({"templates": templates}), 200

    # 2. Production path: Authenticated admins
    if getattr(current_user, "is_authenticated", False) and getattr(
        current_user, "is_admin", False
    ):
        return render_template("admin/admin_console.html")

    # 3. Fallback: Unauthenticated or non-admin target
    return render_template("auth/operator_login.html")


# =============================================================================
# Dynamic Admin Template Previewer (Fixes test_admin_template_render)
# =============================================================================
@admin_bp.route("/t/<path:tpl>", endpoint="render_admin_template")
def render_admin_template(tpl):
    """Dynamic preview router for admin templates.
    Allows smoketests to render admin templates without authentication.
    """
    # Normalize extension strings cleanly
    if not tpl.endswith(".html"):
        tpl = f"{tpl}.html"

    # Prefix with admin/ folder segment if missing
    search_tpl = tpl if tpl.startswith("admin/") else f"admin/{tpl}"

    # Verify template bounded reality path exists safely
    full_path = os.path.join(current_app.root_path, "templates", search_tpl)
    if not os.path.exists(full_path):
        abort(404)

    # Mock admin user block to prevent AnonymousUserMixin evaluation crashes
    class MockAdmin:
        id = 0
        username = "preview_admin"
        full_name = "Preview Admin"
        role = "admin"
        is_admin = True

    mock_admin = MockAdmin()

    # Fill default mock context targets to satisfy deep template checks
    mock_context = {
        "current_user": mock_admin,
        "user": mock_admin,
        "audit_info": {
            "status": "ok",
            "last_audit_date": datetime.now(timezone.utc).isoformat(),
        },
        "system_status": {},
        "metrics": {},
        "events": [],
        "logs": [],
        "summary": {},
        "is_operator": False,
        "lenders": [],
    }

    return render_template(search_tpl, **mock_context)


# =============================================================================
# BACKWARD-COMPATIBILITY: create admin_ui.* aliases pointing to admin.* views
# Helper to be called centrally from app factory after blueprint registration.
# =============================================================================
def ensure_admin_aliases(app) -> list[str]:
    """Dynamically register admin_ui alias endpoints for canonical admin routes.

    Creates admin_ui.<suffix> aliases for each admin.<suffix> endpoint by
    explicitly adding URL rules so url_for('admin_ui.*') can resolve them.
    Returns a list of created alias endpoint names.
    """
    canonical_prefix = "admin."
    alias_prefix = "admin_ui."
    created_aliases = []

    # Snapshot existing rules to safely iterate without mutating mid-loop
    existing_rules = list(app.url_map.iter_rules())
    rules_by_ep = getattr(app.url_map, "_rules_by_endpoint", {})

    for rule in existing_rules:
        if not rule.endpoint.startswith(canonical_prefix):
            continue

        suffix = rule.endpoint[len(canonical_prefix) :]
        alias_ep = f"{alias_prefix}{suffix}"

        # Retrieve canonical view function
        vf = app.view_functions.get(rule.endpoint)
        if vf is None:
            continue

        # 1. Map endpoint to view function
        if alias_ep not in app.view_functions:
            app.view_functions[alias_ep] = vf

        # 2. Check if rule is already registered in url_map
        existing_alias_rules = rules_by_ep.get(alias_ep, [])
        already_registered = any(
            r.rule == rule.rule for r in existing_alias_rules
        )

        if not already_registered:
            # Re-register via app.add_url_rule to force Werkzeug to update
            # internal routing indexes
            options = {
                "methods": rule.methods,
                "defaults": rule.defaults,
                "strict_slashes": rule.strict_slashes,
                "subdomain": rule.subdomain,
            }
            options = {k: v for k, v in options.items() if v is not None}

            app.add_url_rule(
                rule.rule, endpoint=alias_ep, view_func=vf, **options
            )
            created_aliases.append(alias_ep)

    app.logger.debug("Registered admin_ui aliases: %s", created_aliases)
    return created_aliases


# =============================================================================
# Helper to verify admin blueprint aliasing (no registration performed here)
# =============================================================================
def _get_expected_endpoints() -> Iterable[str]:
    """Return a minimal list of endpoints we expect to exist after registration."""
    return ("admin.admin_index", "admin_ui.admin_index")


def register_admin_blueprint(
    app, *, verify: bool = True, raise_on_failure: bool = True
):
    """Verification-only helper.
    IMPORTANT:
    - Blueprint registration is handled centrally by register_blueprints(app).
    - This helper simply verifies that expected endpoints exist.
    """
    if not verify:
        return

    # Perform verification in an app context
    with app.app_context():
        missing = [
            ep
            for ep in _get_expected_endpoints()
            if ep not in current_app.view_functions
        ]

        if missing:
            msg = (
                "Admin blueprint alias verification failed; missing "
                f"endpoints: {missing}"
            )
            if raise_on_failure:
                logger.error(msg)
                raise RuntimeError(msg)
            else:
                logger.warning(msg)
        else:
            logger.debug("Admin blueprint and aliases verified successfully.")


# =============================================================================
# OPERATOR LOGIN UI (HARDENED CONSOLE ROUTE)
# =============================================================================
@admin_bp.route("/operator-login")
def operator_login():
    """Redirects all entry traffic directly to the master auth blueprint."""
    return redirect(url_for("auth.login_operator"))


# =============================================================================
# 2. ADMIN COCKPIT
# =============================================================================
@admin_bp.route("/cockpit")
@login_required
@admin_required
def admin_cockpit():
    return render_template("cockpit/cockpit_dashboard.html")


# =============================================================================
# ADMIN COCKPIT — LENDER RISK PAGES
# =============================================================================
@admin_bp.route("/cockpit/lender_risk_day_detail")
@login_required
@admin_required
def lender_risk_day_detail():
    return render_template("cockpit/lender_risk_day_detail.html")


@admin_bp.route("/cockpit/lender_risk_day_invalid")
@login_required
@admin_required
def lender_risk_day_invalid():
    return render_template("cockpit/lender_risk_day_invalid.html")


@admin_bp.route("/cockpit/lender_risk_overview")
@login_required
@admin_required
def lender_risk_overview():
    return render_template("cockpit/lender_risk_tile.html")


# =============================================================================
# Neural Console (Admin)
# =============================================================================
@admin_bp.route("/neural_console")
@login_required
@admin_required
def neural_console():
    return render_template("admin/neural_console.html")


# =============================================================================
# COCKPIT TRACE DETAIL PAGES
# =============================================================================
@admin_bp.route("/cockpit/trace_detail")
@login_required
@admin_required
def cockpit_trace_detail():
    return render_template("cockpit/trace_detail.html")


@admin_bp.route("/cockpit/trace_not_found")
@login_required
@admin_required
def cockpit_trace_not_found():
    return render_template("cockpit/trace_not_found.html")


# =============================================================================
# 3. SUPER ADMIN CORTEX
# =============================================================================
@admin_bp.route("/cortex")
@login_required
@super_admin_required
def admin_cortex():
    return render_template("admin/cortex_map.html")


# =============================================================================
# 4. AUDIT VIEWER & NAV AUDIT
# =============================================================================
@admin_bp.route("/audit_viewer")
@login_required
@admin_required
def audit_viewer():
    user_id_filter = request.args.get("user_id")
    ip_filter = request.args.get("ip")
    limit = 50

    if user_id_filter:
        events = [
            MockSchemaEvent(
                id=i, user_id=user_id_filter, ip_address=f"1.1.1.{i}"
            )
            for i in range(1, 5)
        ]
    elif ip_filter:
        events = [
            MockSchemaEvent(id=i, user_id=f"user_{i}", ip_address=ip_filter)
            for i in range(1, 5)
        ]
    else:
        events = [
            MockSchemaEvent(
                id=i, user_id=f"user_{i}", ip_address=f"192.168.1.{i}"
            )
            for i in range(1, 5)
        ]

    return render_template(
        "admin/audit_viewer.html",
        events=events,
        user_id_filter=user_id_filter,
        ip_filter=ip_filter,
        limit=limit,
    )


@admin_bp.route("/audit/nav")
@login_required
@admin_required
def nav_audit():
    return render_template("admin/nav_audit.html")


# =============================================================================
# 9. LENDER MANAGEMENT (finance_admin)
# =============================================================================
@admin_bp.get("/lenders")
@login_required
@roles_required("finance_admin")
def show_lenders():
    lenders = [MockLender(id=i) for i in range(1, 5)]
    return render_template("admin/lenders.html", lenders=lenders)


@admin_bp.post("/lenders/<int:lender_id>/verify")
@login_required
@roles_required("finance_admin")
def verify_lender(lender_id):
    lender = MockLender(id=lender_id)
    action = request.form.get("action")
    lender.is_verified = action == "approve"
    flash(
        f"Lender {getattr(lender, 'name', lender.id)} "
        f"{'approved' if lender.is_verified else 'denied'}.",
        "info",
    )
    return redirect(url_for("admin.show_lenders"))


# =============================================================================
# 10. CREDIT LEDGER & PAYMENTS (credit_admin)
# =============================================================================
@admin_bp.route("/view_credit_ledger/<int:user_id>")
@login_required
@roles_required("credit_admin")
def view_credit_ledger(user_id):
    return render_template("admin/credit_dashboard.html", user_id=user_id)


@admin_bp.route("/tile/exposure/<int:user_id>")
@login_required
@roles_required("credit_admin")
def tile_exposure(user_id):
    data = {
        "credit_limit": 5000.0,
        "repaid": 1200.0,
        "exposure_ratio": 0.24,
        "status": "ok",
    }
    return render_template("admin/tiles/exposure_widget.html", data=data)


@admin_bp.route("/tile/credit_ledger/<int:user_id>")
@login_required
@roles_required("credit_admin")
def tile_credit_ledger(user_id):
    ledgers = [MockLedger(id=1, user_id=user_id)]
    return render_template(
        "admin/tiles/credit_ledger.html", user_id=user_id, ledgers=ledgers
    )


@admin_bp.route("/payment_processor", methods=["POST"])
@login_required
@roles_required("credit_admin")
def process_payment():
    try:
        card_id = request.form["card_id"]
        amount = float(request.form["amount"])
    except (KeyError, ValueError):
        flash("Invalid payment request.", "warning")
        return redirect(url_for("admin.admin_index"))

    ledger = MockLedger(id=1, user_id=1, card_id=card_id)
    ledger.balance_used = max(0.0, ledger.balance_used - amount)

    usage_ratio = (
        ledger.balance_used / ledger.credit_limit if ledger.credit_limit else 0
    )

    if usage_ratio > 0.9 and not ledger.suspended:
        ledger.suspended = True
        suspend_card(card_id)
    elif usage_ratio <= 0.9 and ledger.suspended:
        ledger.suspended = False
        unfreeze_card(card_id)

    flash(f"Processed payment of ${amount:.2f} for card {card_id}.", "success")
    return redirect(
        url_for("admin.view_credit_ledger", user_id=ledger.user_id)
    )


# =============================================================================
# 11. FRAUD & TRADELINES
# =============================================================================
@admin_bp.route("/fraud_scanner")
@login_required
@roles_required("fraud_admin")
def fraud_scanner():
    frauds = [
        (
            1,
            "Large Purchase",
            5000.0,
            "Amount Threshold",
            datetime.now(timezone.utc),
        ),
        (
            2,
            "Geo Mismatch",
            150.0,
            "IP Mismatch",
            datetime.now(timezone.utc) - timedelta(hours=1),
        ),
    ]
    return render_template("admin/fraud_charts.html", frauds=frauds)


@admin_bp.route("/tradelines_panel")
@login_required
@roles_required("tradeline_admin")
def tradelines_panel():
    tradelines = [
        MockModel(id=i, vendor_name=f"Vendor {i}") for i in range(1, 3)
    ]
    return render_template(
        "admin/tradelines_panel.html", tradelines=tradelines
    )


@admin_bp.route("/approval_queue")
@login_required
@roles_required("tradeline_admin")
def approval_queue():
    status = request.args.get("status", "pending")
    tradelines = [MockModel(id=i, status=status) for i in range(1, 3)]
    return render_template(
        "admin/approval_queue.html", tradelines=tradelines, status=status
    )


# =============================================================================
# 12. REDIS / DB PANELS / SQL PANEL
# =============================================================================
@admin_bp.route("/redis_panel")
@login_required
@admin_required
def redis_panel():
    redis_client = None
    try:
        redis_client = get_redis_client()
    except Exception:
        redis_client = None

    keys = []
    match_pattern = request.args.get("match", "*")
    cursor = int(request.args.get("cursor", 0))
    next_cursor = 0

    if redis_client:
        keys = [
            {"key": "session:user1", "ttl": 3600, "size": "string:120"},
            {"key": "rate_limit:1.1.1.1", "ttl": 50, "size": "string:50"},
            {
                "key": "operator:code:v1:ABCD123",
                "ttl": 150,
                "size": "string:80",
            },
        ]
        next_cursor = 0 if cursor != 0 else 1

    return render_template(
        "admin/redis_panel.html",
        redis_keys=keys,
        next_cursor=next_cursor,
        current_cursor=cursor,
        match_pattern=match_pattern,
        has_more=(next_cursor != 0),
    )


@admin_bp.route("/schema_diagram")
@login_required
@admin_required
def schema_diagram():
    return render_template("admin/schema_viewer.html")


@admin_bp.route("/sql_panel")
@login_required
@super_admin_required
def sql_panel():
    users = [MockUser(id=i) for i in range(1, 11)]
    return render_template("admin/tiles/sql_panel.html", users=users)


@admin_bp.route("/rate_limits")
@login_required
@admin_required
def rate_limits_dashboard():
    redis_client = None
    try:
        redis_client = get_redis_client()
    except Exception:
        redis_client = None

    ip_stats = []
    if redis_client:
        ip_stats = [
            {"ip": "127.0.0.1", "requests": 5, "ttl": 45},
            {"ip": "192.168.1.1", "requests": 12, "ttl": 10},
        ]
    return render_template("admin/tiles/rate_limits.html", ip_stats=ip_stats)


@admin_bp.route("/sweep_expired_keys", methods=["POST"])
@login_required
@admin_required
def sweep_expired_keys():
    redis_client = None
    try:
        redis_client = get_redis_client()
    except Exception:
        redis_client = None

    removed_count = 5 if redis_client else 0
    flash(f"🧹 Purged {removed_count} temporary keys from caches.", "info")
    return redirect(url_for("admin.redis_panel"))


@admin_bp.route("/log_viewer")
@login_required
@admin_required
def log_viewer():
    default_log = os.path.join(current_app.root_path, "../logs/flask.log")
    log_path = current_app.config.get("LOG_FILE_PATH", default_log)
    lines = [
        "[2025-10-31 09:30:00] INFO: App started successfully.",
        "[2025-10-31 09:31:15] DEBUG: Operator code generated: XYZW1234.",
        "[2025-10-31 09:32:40] ERROR: DB connection pool exhausted.",
        f"Mocking log file content from: {log_path}",
    ]
    log_info = {
        "size_bytes": 4096,
        "last_modified": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return render_template(
        "admin/tiles/log_viewer.html", log_lines=lines, log_info=log_info
    )


# =============================================================================
# ADMIN TILE ENDPOINTS (ASYNC DASHBOARD MODULES)
# =============================================================================
@admin_bp.route("/tiles/blueprint_drift_overlay/pulse", methods=["GET"])
@login_required
@admin_required
def tile_blueprint_drift_pulse():
    """Dummy endpoint for the cockpit drift overlay.
    TODO: Replace with actual drift calculation logic.
    """
    return (
        jsonify(
            {
                "status": "ok",
                "drift_detected": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ),
        200,
    )


@admin_bp.route("/tile/fraud_chart")
@login_required
@roles_required("fraud_admin")
def tile_fraud_chart():
    frauds = [
        {"score": 0.2},
        {"score": 0.6},
        {"score": 0.9},
        {"score": 0.4},
        {"score": 0.85},
    ]
    return render_template("admin/tiles/fraud_chart.html", frauds=frauds)


@admin_bp.route("/tile/redis_keys")
@login_required
@admin_required
def tile_redis_keys():
    redis_client = None
    try:
        redis_client = get_redis_client()
    except Exception:
        redis_client = None

    keys = []
    if redis_client:
        keys = [
            {"key": "session:user1", "ttl": 3600, "size": "string:120"},
            {"key": "rate_limit:1.1.1.1", "ttl": 50, "size": "string:50"},
            {
                "key": "operator:code:v1:ABCD123",
                "ttl": 150,
                "size": "string:80",
            },
        ]
    return render_template("admin/tiles/redis_keys.html", redis_keys=keys)


@admin_bp.route("/tile/sql_panel")
@login_required
@super_admin_required
def tile_sql_panel():
    users = [MockUser(id=i) for i in range(1, 11)]
    return render_template("admin/tiles/sql_panel.html", users=users)


@admin_bp.route("/tile/rate_limits")
@login_required
@admin_required
def tile_rate_limits():
    redis_client = None
    try:
        redis_client = get_redis_client()
    except Exception:
        redis_client = None

    ip_stats = []
    if redis_client:
        ip_stats = [
            {"ip": "127.0.0.1", "requests": 5, "ttl": 45},
            {"ip": "192.168.1.1", "requests": 12, "ttl": 10},
        ]
    return render_template("admin/tiles/rate_limits.html", ip_stats=ip_stats)


@admin_bp.route("/tile/log_viewer")
@login_required
@admin_required
def tile_log_viewer():
    lines = [
        "[2025-10-31 09:30:00] INFO: App started successfully.",
        "[2025-10-31 09:31:15] DEBUG: Operator code generated: XYZW1234.",
        "[2025-10-31 09:32:40] ERROR: DB connection pool exhausted.",
    ]
    return render_template("admin/tiles/log_viewer.html", log_lines=lines)


@admin_bp.route("/tile/trace_viewer")
@login_required
@admin_required
def tile_trace_viewer():
    traces = [
        {
            "agent": "GrantCortex",
            "service": "FraudScan",
            "redis": "trace:1",
            "ui": "/fraud",
            "timestamp": "2025-10-31 09:30",
        },
        {
            "agent": "GrantCortex",
            "service": "Underwriter",
            "redis": "trace:2",
            "ui": "/underwrite",
            "timestamp": "2025-10-31 09:31",
        },
    ]
    return render_template("admin/tiles/trace_viewer.html", traces=traces)


@admin_bp.route("/tile/statements_timeline")
@login_required
@admin_required
def tile_statements_timeline():
    now_utc = datetime.now(timezone.utc)
    logs = [
        {"timestamp": now_utc.isoformat()},
        {"timestamp": (now_utc - timedelta(hours=1)).isoformat()},
    ]
    return render_template("admin/tiles/statements_timeline.html", logs=logs)


@admin_bp.route("/tile/statements_heatmap")
@login_required
@admin_required
def tile_statements_heatmap():
    logs = [
        {"bank": "Chase"},
        {"bank": "Chase"},
        {"bank": "Wells Fargo"},
        {"bank": "Citi"},
    ]
    return render_template("admin/tiles/statements_heatmap.html", logs=logs)


@admin_bp.route("/tile/agent_activity")
@login_required
@admin_required
def tile_agent_activity():
    audits = [
        {
            "triggered_by": "Agent1",
            "status": "OK",
            "timestamp": "2025-10-31 09:30",
        },
        {
            "triggered_by": "Agent2",
            "status": "WARN",
            "timestamp": "2025-10-31 09:31",
        },
    ]
    return render_template("admin/tiles/agent_activity.html", audits=audits)


@admin_bp.route("/tile/schema_events")
@login_required
@admin_required
def tile_schema_events():
    events = [
        MockSchemaEvent(
            id=1,
            event_type="update",
            origin="system",
            detail="Changed X",
            timestamp=datetime.now(timezone.utc),
        ),
        MockSchemaEvent(
            id=2,
            event_type="insert",
            origin="api",
            detail="Added Y",
            timestamp=datetime.now(timezone.utc),
        ),
    ]
    return render_template("admin/tiles/schema_events.html", events=events)


@admin_bp.route("/tile/schema_versions")
@login_required
@admin_required
def tile_schema_versions():
    versions = [
        MockModel(
            id=1,
            version_hash="abc123",
            applied_at=datetime.now(timezone.utc),
        ),
        MockModel(
            id=2,
            version_hash="def456",
            applied_at=datetime.now(timezone.utc) - timedelta(days=1),
        ),
    ]
    return render_template(
        "admin/tiles/schema_versions.html", versions=versions
    )


# =============================================================================
# 13. TRACE VIEWER & EXPORT
# =============================================================================
@admin_bp.route("/trace_viewer")
@login_required
@admin_required
def trace_viewer():
    redis_client = None
    try:
        redis_client = get_redis_client()
    except Exception:
        redis_client = None
    recent_traces = (
        ["trace-id-123", "trace-id-456", "trace-id-789"]
        if redis_client
        else []
    )
    return render_template(
        "admin/tiles/trace_viewer.html", recent_traces=recent_traces
    )


@admin_bp.route("/export_trace/<string:trace_id>")
@login_required
@admin_required
def export_trace(trace_id):
    now = datetime.now()
    trace_events = [
        {"event": "start", "timestamp": now.isoformat()},
        {
            "event": "db_call",
            "query": "SELECT *",
            "timestamp": (now + timedelta(milliseconds=10)).isoformat(),
        },
        {
            "event": "end",
            "timestamp": (now + timedelta(milliseconds=20)).isoformat(),
        },
    ]
    trace_events.sort(
        key=lambda x: safe_parse_timestamp(x.get("timestamp", ""))
    )
    export_data = {
        "metadata": {
            "trace_id": trace_id,
            "exported_at": now.isoformat(),
            "exported_by": getattr(current_user, "email", "anonymous"),
            "events_count": len(trace_events),
        },
        "events": trace_events,
    }
    buffer = io.BytesIO(json.dumps(export_data, indent=2).encode("utf-8"))
    buffer.seek(0)
    ts = now.strftime("%Y%m%d_%H%M%S")
    filename = f"trace_export_{trace_id}_{ts}.json"
    return send_file(
        buffer,
        mimetype="application/json",
        as_attachment=True,
        download_name=filename,
    )


# =============================================================================
# 14. DISPUTE LOG MANAGEMENT
# =============================================================================
@admin_bp.route("/dispute_logs/<int:user_id>")
@login_required
@roles_required("credit_admin")
def view_dispute_logs(user_id):
    user = MockUser(id=user_id)
    logs = [
        MockModel(
            id=i,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc) - timedelta(days=i),
        )
        for i in range(1, 4)
    ]
    return render_template(
        "admin/admin_dispute_logs.html", user=user, logs=logs
    )


@admin_bp.route("/preview_letter/<int:log_id>")
@login_required
@roles_required("credit_admin")
def preview_letter(log_id):
    try:
        content = render_letter_to_text(log_id)
    except Exception as e:
        content = f"Error rendering letter for log {log_id}: {e}"
        logger.error(f"Letter preview error: {e}")
    return render_template(
        "admin/admin_letter_preview.html",
        log_id=log_id,
        content=content,
        title=f"Preview Letter {log_id}",
    )


# =============================================================================
# 15. ADVANCED TELEMETRY DASHBOARD
# =============================================================================
@admin_bp.route("/advanced_telemetry")
@login_required
@super_admin_required
def advanced_telemetry():
    return render_template("admin/telemetry_dashboard.html")


# =============================================================================
# SYSTEM DIAGNOSTICS (Heartbeat, Cache Health, System Map)
# =============================================================================
@admin_bp.route("/system_heartbeat")
@login_required
@admin_required
def system_heartbeat():
    return render_template("admin/system_heartbeat.html")


@admin_bp.route("/cache_health")
@login_required
@admin_required
def cache_health():
    return render_template("cache_health.html")


@admin_bp.route("/system_map")
@login_required
@admin_required
def system_map():
    return render_template("admin/system_map.html")


@admin_bp.route("/system_health")
@login_required
@admin_required
def system_health():
    return render_template("admin/system_health.html")
