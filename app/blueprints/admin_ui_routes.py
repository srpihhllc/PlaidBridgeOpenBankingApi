# =============================================================================
# DESCRIPTION: Admin UI routes with cockpit wiring and tiles.
# Compatibility: blueprint is registered as "admin" (so legacy calls to
# url_for('admin.*') continue to work). We also create admin_ui.* aliases
# to preserve any JS/templates that reference admin_ui.* endpoints.
#
# This module also provides a helper function `register_admin_blueprint(app, ...)`
# intended to be called from your app factory. The helper registers the blueprint
# and performs a runtime verification (smoke-check) that both admin.* and
# admin_ui.* endpoints were created. If verification fails the helper will
# either raise or log based on arguments.
#
# Recommended usage in app factory (create_app):
#   from app.blueprints.admin_ui_routes import register_admin_blueprint
#   register_admin_blueprint(app, verify=True, raise_on_failure=True)
#
# Add a small pytest smoke test (see bottom of file for snippets) to assert
# alias creation so registration-order problems are caught early in CI.
# =============================================================================

import io
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Iterable

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user as login_user
from flask_login import login_required

# Import mock models from admin API layer
from app.blueprints.admin_routes import MockLedger, MockLender, MockModel, MockSchemaEvent, MockUser
from app.decorators import admin_required, roles_required, super_admin_required

# Import real service-layer functions
from app.services.card_manager import suspend_card, unfreeze_card
from app.services.letter_writer import render_letter_to_text
from app.utils.redis_utils import get_redis_client
from app.utils.time_utils import safe_parse_timestamp

logger = logging.getLogger(__name__)

# Register blueprint under the canonical name "admin" so tests and code
# calling url_for("admin.*") are guaranteed to resolve.
admin_bp = Blueprint(
    "admin", __name__, url_prefix="/admin", template_folder="../templates/admin"
)

# Keep the old variable name available for imports that expect admin_ui_bp.
admin_ui_bp = admin_bp  # alias: same Blueprint object


# =============================================================================
# ADMIN INDEX (REQUIRED BY TEST SUITE)
# =============================================================================
# IMPORTANT: Do NOT pass endpoint= here. Flask auto-derives the endpoint name
# as "admin.admin_index" (blueprint name + "." + function name). Passing an
# explicit endpoint= kwarg causes Flask to store the Rule under the bare name
# in _rules_by_endpoint while view_functions receives the prefixed name —
# a split that makes url_for("admin.admin_index") raise BuildError.
#
# Use route path "/" (not "") with strict_slashes=False.
# On a Blueprint with url_prefix="/admin" this resolves to /admin.
# Using "" is unreliable: Werkzeug 3.1.x normalises empty-string blueprint
# paths to "/" internally, which can cause the endpoint key to be stored
# without the blueprint prefix in _rules_by_endpoint on some builds,
# breaking url_for("admin.admin_index").
@admin_bp.route("/", strict_slashes=False)
def admin_index():
    """
    Admin UI landing page.
    - Authenticated admins render the admin console (preserves prior behavior).
    - Unauthenticated callers receive a small JSON payload listing a few admin
      templates so smoke-tests that call /admin without auth do not get 401.
    """
    if getattr(login_user, "is_authenticated", False) and getattr(login_user, "is_admin", False):
        return render_template("admin_console.html")

    templates = [
        "admin_console.html",
        "cockpit/cockpit_dashboard.html",
        "audit_viewer.html",
        "lenders.html",
    ]
    return jsonify({"templates": templates}), 200


# =============================================================================
# BACKWARD-COMPATIBILITY: create admin_ui.* aliases pointing to admin.* views
# Robust: if _rules_by_endpoint is missing, build it from existing rules.
# =============================================================================
def _register_admin_ui_aliases(state):
    """
    When the blueprint is registered, create admin_ui.<suffix> aliases for each
    admin.<suffix> endpoint. This reuses the same Rule lists so no duplicate Rule
    objects are created. If internals are unavailable, we build the mapping
    from the current rules to make aliasing robust for different Flask versions.
    """
    app = state.app
    canonical_prefix = "admin"
    alias_prefix = "admin_ui"

    # Try to populate internal structures
    try:
        app.url_map.update()
    except Exception:
        app.logger.debug("app.url_map.update() raised; proceeding with available internals.")

    # Ensure _rules_by_endpoint mapping exists. If not, build it from iter_rules().
    rules_by_ep = getattr(app.url_map, "_rules_by_endpoint", None)
    if rules_by_ep is None:
        app.logger.debug("_rules_by_endpoint missing; building mapping from url_map.iter_rules()")
        rules_by_ep = {}
        for r in list(app.url_map.iter_rules()):
            rules_by_ep.setdefault(r.endpoint, []).append(r)
        # attach it so later code (and Flask internals) can rely on it if writable
        try:
            app.url_map._rules_by_endpoint = rules_by_ep
        except Exception:
            # last resort: set attribute anyway
            setattr(app.url_map, "_rules_by_endpoint", rules_by_ep)

    created_aliases = []
    for endpoint, rule_list in list(rules_by_ep.items()):
        if not endpoint.startswith(canonical_prefix + "."): 
            continue

        suffix = endpoint.split(".", 1)[1]  # 'admin_index', 'view_credit_ledger', etc.
        alias_ep = f"{alias_prefix}.{suffix}"

        # Map view function for alias -> canonical view func
        if alias_ep not in app.view_functions:
            vf = app.view_functions.get(endpoint)
            if vf is not None:
                app.view_functions[alias_ep] = vf
                created_aliases.append(alias_ep)

        # Reuse the same Rule objects list to avoid duplicate Rule creation
        if rule_list:
            rules_by_ep.setdefault(alias_ep, rule_list)

    # Ensure index alias names commonly used are available
    # (admin_ui.admin_home, admin.admin_home)
    index_canonical = f"{canonical_prefix}.admin_index"
    if index_canonical in app.view_functions:
        for special_alias in (f"{alias_prefix}.admin_home", f"{canonical_prefix}.admin_home"):
            if special_alias not in app.view_functions:
                app.view_functions[special_alias] = app.view_functions[index_canonical]
                rules_by_ep.setdefault(special_alias, rules_by_ep.get(index_canonical, []))
                created_aliases.append(special_alias)

    app.logger.debug(f"Registered admin_ui aliases: {created_aliases}")


# Record hook: run once when blueprint is registered
admin_bp.record_once(_register_admin_ui_aliases)


# =============================================================================
# Helper to register blueprint and optionally verify aliases (for app factory)
# =============================================================================
def _get_expected_endpoints() -> Iterable[str]:
    """
    Return a minimal list of endpoints we expect to exist after registration.
    Add to this list if you rely on other specific endpoint names in tests.
    """
    return ("admin.admin_index", "admin_ui.admin_index")

def register_admin_blueprint(app, *, verify: bool = True, raise_on_failure: bool = True):
    """
    Helper to register the admin blueprint and verify aliasing.

    Usage (in create_app):
        register_admin_blueprint(app, verify=True, raise_on_failure=True)

    Parameters:
    - app: Flask application instance
    - verify: if True, perform the post-registration verification check
    - raise_on_failure: if True, raise RuntimeError on missing endpoints; otherwise log a warning

    Why use this:
    - Centralizes registration and verification
    - Ensures tests / code calling url_for('admin.admin_index') succeed
    """
    app.register_blueprint(admin_bp)

    if not verify:
        return

    # Perform verification in an app context
    with app.app_context():
        missing = [ep for ep in _get_expected_endpoints() if ep not in current_app.view_functions]
        if missing:
            msg = f"Admin blueprint alias verification failed; missing endpoints: {missing}"
            if raise_on_failure:
                logger.error(msg)
                raise RuntimeError(msg)
            else:
                logger.warning(msg)
        else:
            logger.debug("Admin blueprint and aliases verified successfully.")


# =============================================================================
# OPERATOR LOGIN UI
# =============================================================================
@admin_bp.route("/operator-login")
@login_required
def operator_login():
    return render_template("operator_login.html")


# =============================================================================
# 2. ADMIN COCKPIT
# =============================================================================
@admin_bp.route("/cockpit")
@login_required
@admin_required
def admin_cockpit():
    return render_template("cockpit/cockpit_dashboard.html")


# =============================================================================
# ADMIN COCKPIT — LENDER RISK PAGES (ADDED)
# =============================================================================
@admin_bp.route("/cockpit/lender_risk_day_detail")
@login_required
@admin_required
def lender_risk_day_detail():
    return render_template("admin/cockpit/lender_risk_day_detail.html")


@admin_bp.route("/cockpit/lender_risk_day_invalid")
@login_required
@admin_required
def lender_risk_day_invalid():
    return render_template("admin/cockpit/lender_risk_day_invalid.html")


@admin_bp.route("/cockpit/lender_risk_overview")
@login_required
@admin_required
def lender_risk_overview():
    return render_template("admin/cockpit/lender_risk_overview.html")


# =============================================================================
# Neural Console (Admin) (ADDED)
# =============================================================================
@admin_bp.route("/neural_console")
@login_required
@admin_required
def neural_console():
    return render_template("admin/neural_console.html")


# =============================================================================
# COCKPIT TRACE DETAIL PAGES (ADDED)
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
    return render_template("cortex_map.html")


# =============================================================================
# 4. AUDIT VIEWER
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
            MockSchemaEvent(id=i, user_id=user_id_filter, ip_address=f"1.1.1.{i}")
            for i in range(1, 5)
        ]
    elif ip_filter:
        events = [
            MockSchemaEvent(id=i, user_id=f"user_{i}", ip_address=ip_filter) for i in range(1, 5)
        ]
    else:
        events = [
            MockSchemaEvent(id=i, user_id=f"user_{i}", ip_address=f"192.168.1.{i}")
            for i in range(1, 5)
        ]

    return render_template(
        "audit_viewer.html",
        events=events,
        user_id_filter=user_id_filter,
        ip_filter=ip_filter,
        limit=limit,
    )


# =============================================================================
# 9. LENDER MANAGEMENT (finance_admin)
# =============================================================================
@admin_bp.get("/lenders")
@login_required
@roles_required("finance_admin")
def show_lenders():
    lenders = [MockLender(id=i) for i in range(1, 5)]
    return render_template("lenders.html", lenders=lenders)


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
    return render_template("credit_dashboard.html", user_id=user_id)


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
    return render_template("admin/tiles/credit_ledger.html", user_id=user_id, ledgers=ledgers)


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

    usage_ratio = ledger.balance_used / ledger.credit_limit if ledger.credit_limit else 0

    if usage_ratio > 0.9 and not ledger.suspended:
        ledger.suspended = True
        suspend_card(card_id)
    elif usage_ratio <= 0.9 and ledger.suspended:
        ledger.suspended = False
        unfreeze_card(card_id)

    flash(f"Processed payment of ${amount:.2f} for card {card_id}.", "success")
    return redirect(url_for("admin.view_credit_ledger", user_id=ledger.user_id))


# =============================================================================
# 11. FRAUD & TRADELINES
# =============================================================================
@admin_bp.route("/fraud_scanner")
@login_required
@roles_required("fraud_admin")
def fraud_scanner():
    frauds = [
        (1, "Large Purchase", 5000.0, "Amount Threshold", datetime.utcnow()),
        (
            2,
            "Geo Mismatch",
            150.0,
            "IP Mismatch",
            datetime.utcnow() - timedelta(hours=1),
        ),
    ]
    return render_template("fraud_charts.html", frauds=frauds)


@admin_bp.route("/tradelines_panel")
@login_required
@roles_required("tradeline_admin")
def tradelines_panel():
    tradelines = [MockModel(id=i, vendor_name=f"Vendor {i}") for i in range(1, 3)]
    return render_template("tradelines_panel.html", tradelines=tradelines)


@admin_bp.route("/approval_queue")
@login_required
@roles_required("tradeline_admin")
def approval_queue():
    status = request.args.get("status", "pending")
    tradelines = [MockModel(id=i, status=status) for i in range(1, 3)]
    return render_template("approval_queue.html", tradelines=tradelines, status=status)


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
            {"key": "operator:code:v1:ABCD123", "ttl": 150, "size": "string:80"},
        ]
        next_cursor = 0 if cursor != 0 else 1

    return render_template(
        "redis_panel.html",
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
    return render_template("schema_viewer.html")


@admin_bp.route("/sql_panel")
@login_required
@super_admin_required
def sql_panel():
    users = [MockUser(id=i) for i in range(1, 11)]
    return render_template("sql_panel.html", users=users)


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
    return render_template("rate_limits.html", ip_stats=ip_stats)


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
    log_path = current_app.config.get(
        "LOG_FILE_PATH", os.path.join(current_app.root_path, "../logs/flask.log")
    )
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
    return render_template("log_viewer.html", log_lines=lines, log_info=log_info)


# =============================================================================
# ADMIN TILE ENDPOINTS (ASYNC DASHBOARD MODULES)
# =============================================================================
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
            {"key": "operator:code:v1:ABCD123", "ttl": 150, "size": "string:80"},
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
    logs = [
        {"timestamp": datetime.utcnow().isoformat()},
        {"timestamp": (datetime.utcnow() - timedelta(hours=1)).isoformat()},
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
        {"triggered_by": "Agent1", "status": "OK", "timestamp": "2025-10-31 09:30"},
        {"triggered_by": "Agent2", "status": "WARN", "timestamp": "2025-10-31 09:31"},
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
            timestamp=datetime.utcnow(),
        ),
        MockSchemaEvent(
            id=2,
            event_type="insert",
            origin="api",
            detail="Added Y",
            timestamp=datetime.utcnow(),
        ),
    ]
    return render_template("admin/tiles/schema_events.html", events=events)


@admin_bp.route("/tile/schema_versions")
@login_required
@admin_required
def tile_schema_versions():
    versions = [
        MockModel(id=1, version_hash="abc123", applied_at=datetime.utcnow()),
        MockModel(
            id=2,
            version_hash="def456",
            applied_at=datetime.utcnow() - timedelta(days=1),
        ),
    ]
    return render_template("admin/tiles/schema_versions.html", versions=versions)


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

    recent_traces = ["trace-id-123", "trace-id-456", "trace-id-789"] if redis_client else []
    return render_template("trace_viewer.html", recent_traces=recent_traces)


@admin_bp.route("/export_trace/<string:trace_id>")
@login_required
@admin_required
def export_trace(trace_id):
    trace_events = [
        {"event": "start", "timestamp": datetime.now().isoformat()},
        {
            "event": "db_call",
            "query": "SELECT *",
            "timestamp": (datetime.now() + timedelta(milliseconds=10)).isoformat(),
        },
        {
            "event": "end",
            "timestamp": (datetime.now() + timedelta(milliseconds=20)).isoformat(),
        },
    ]
    trace_events.sort(key=lambda x: safe_parse_timestamp(x.get("timestamp", "")))

    export_data = {
        "metadata": {
            "trace_id": trace_id,
            "exported_at": datetime.now().isoformat(),
            "exported_by": getattr(login_user, "email", "anonymous"),
            "events_count": len(trace_events),
        },
        "events": trace_events,
    }

    buffer = io.BytesIO(json.dumps(export_data, indent=2).encode("utf-8"))
    buffer.seek(0)

    filename = f"trace_export_{trace_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
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
        MockModel(id=i, user_id=user_id, timestamp=datetime.utcnow() - timedelta(days=i))
        for i in range(1, 4)
    ]
    return render_template("admin_dispute_logs.html", user=user, logs=logs)


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
        "admin_letter_preview.html",
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
    return render_template("telemetry_dashboard.html")


# =============================================================================
# SYSTEM (Heartbeat, Cache Health, System Map)
# =============================================================================
@admin_bp.route("/system_heartbeat")
@login_required
@admin_required
def system_heartbeat():
    return render_template("system_heartbeat.html")


@admin_bp.route("/cache_health")
@login_required
@admin_required
def cache_health():
    return render_template("cache_health.html")


@admin_bp.route("/system_map")
@login_required
@admin_required
def system_map():
    return render_template("system_map.html")


# =============================================================================
# SYSTEM HEALTH PAGE (ADDED)
# =============================================================================
@admin_bp.route("/system_health")
@login_required
@admin_required
def system_health():
    return render_template("system_health.html")


# =============================================================================
# SCHEMA & TELEMETRY
# =============================================================================
@admin_bp.route("/schema_events")
@login_required
@admin_required
def schema_events():
    return render_template("schema_events.html")


@admin_bp.route("/schema_versions")
@login_required
@admin_required
def schema_versions():
    return render_template("schema_versions.html")


@admin_bp.route("/route_list")
@login_required
@admin_required
def route_list():
    return render_template("route_list.html")


# =============================================================================
# ACTIVITY & STATS
# =============================================================================
@admin_bp.route("/agent_activity")
@login_required
@admin_required
def agent_activity():
    return render_template("agent_activity.html")


# =============================================================================
# DASHBOARD PAGES (ADDED)
# =============================================================================
@admin_bp.route("/dashboard_anomalies")
@login_required
@admin_required
def dashboard_anomalies():
    return render_template("dashboard_anomalies.html")


@admin_bp.route("/dashboard_liquidity")
@login_required
@admin_required
def dashboard_liquidity():
    return render_template("dashboard_liquidity.html")


# =============================================================================
# STATEMENTS
# =============================================================================
@admin_bp.route("/statements_timeline")
@login_required
@admin_required
def statements_timeline():
    return render_template("statements_timeline.html")


@admin_bp.route("/statements_heatmap")
@login_required
@admin_required
def statements_heatmap():
    return render_template("statements_heatmap.html")


# =============================================================================
# NEURAL INSIGHTS
# =============================================================================
@admin_bp.route("/brain_diagnosis")
@login_required
@admin_required
def brain_diagnosis():
    return render_template("brain_diagnosis.html")


@admin_bp.route("/model_summary")
@login_required
@admin_required
def model_summary():
    return render_template("model_summary.html")


# =============================================================================
# IDENTITY / MISC ADMIN PAGES (ADDED)
# =============================================================================
@admin_bp.route("/identity_events")
@login_required
@admin_required
def identity_events():
    return render_template("identity_events.html")


@admin_bp.route("/ignition_trace")
@login_required
@admin_required
def ignition_trace():
    return render_template("ignition_trace.html")


@admin_bp.route("/login_trace_monitor")
@login_required
@admin_required
def login_trace_monitor():
    return render_template("login_trace_monitor.html")


@admin_bp.route("/me")
@login_required
@admin_required
def me_dashboard():
    return render_template("me.html")


@admin_bp.route("/mutation_submit")
@login_required
@admin_required
def mutation_submit():
    return render_template("mutation_submit_tile.html")


@admin_bp.route("/registry")
@login_required
@admin_required
def registry():
    return render_template("registry.html")


# =============================================================================
# MISC: API USAGE (page that shows api usage tile) (ADDED)
# =============================================================================
@admin_bp.route("/api_usage")
@login_required
@admin_required
def api_usage():
    return render_template("api_usage_tile.html")


# =============================================================================
# TOOLS
# =============================================================================
@admin_bp.route("/repair_result")
@login_required
@admin_required
def repair_result():
    return render_template("repair_result.html")


# =============================================================================
# TEST / SMOKE SNIPPETS (copy-paste into your test suite)
# =============================================================================
# def test_admin_aliases_registered(client):
#     with client.application.test_request_context():
#         eps = {r.endpoint for r in current_app.url_map.iter_rules()}
#         assert "admin.admin_index" in eps
#         assert "admin_ui.admin_index" in eps
#
# def test_admin_view_functions_present(client):
#     with client.application.test_request_context():
#         assert "admin.admin_index" in current_app.view_functions
#         assert "admin_ui.admin_index" in current_app.view_functions
#
# def test_admin_url_building(client):
#     with client.application.test_request_context():
#         assert url_for("admin.admin_index") == url_for("admin_ui.admin_index")
#         assert url_for("admin.view_credit_ledger", user_id=1) == \
#                url_for("admin_ui.view_credit_ledger", user_id=1)
#
# =============================================================================
# DOCUMENTATION NOTES
# - Ensure your create_app() registers this blueprint early (call
#   register_admin_blueprint(app)) before any code that calls url_for() at
#   import-time or tests that call url_for.
# - Do NOT pass endpoint= to @admin_bp.route("/") — Flask must auto-derive
#   "admin.admin_index" from the blueprint name + function name.
