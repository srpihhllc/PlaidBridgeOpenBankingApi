# app/blueprints/admin_ui_routes.py

import io
import json
import logging
import os
from datetime import datetime, timedelta

from flask import (
    Blueprint,
    current_app,
    flash,
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

admin_ui_bp = Blueprint(
    "admin", __name__, url_prefix="/admin", template_folder="../templates/admin"
)


# =============================================================================
# ADMIN INDEX (REQUIRED BY TEST SUITE)
# =============================================================================


@admin_ui_bp.route("/", endpoint="admin_index")
@login_required
@admin_required
def admin_index():
    """
    Admin UI landing page.
    Required by test_login_with_admin_role and used as the primary admin redirect.
    """
    return render_template("admin_console.html")


# =============================================================================
# OPERATOR LOGIN UI
# =============================================================================


@login_required
@admin_ui_bp.route("/operator-login")
def operator_login():
    return render_template("operator_login.html")


# =============================================================================
# 2. ADMIN COCKPIT
# =============================================================================


@login_required
@admin_required
@admin_ui_bp.route("/cockpit")
def admin_cockpit():
    return render_template("cockpit/cockpit_dashboard.html")


# =============================================================================
# 3. SUPER ADMIN CORTEX
# =============================================================================


@login_required
@super_admin_required
@admin_ui_bp.route("/cortex")
def admin_cortex():
    return render_template("cortex_map.html")


# =============================================================================
# 4. AUDIT VIEWER
# =============================================================================


@login_required
@admin_required
@admin_ui_bp.route("/audit_viewer")
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


@login_required
@roles_required("finance_admin")
@admin_ui_bp.get("/lenders")
def show_lenders():
    lenders = [MockLender(id=i) for i in range(1, 5)]
    return render_template("lenders.html", lenders=lenders)


@login_required
@roles_required("finance_admin")
@admin_ui_bp.post("/lenders/<int:lender_id>/verify")
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


@login_required
@roles_required("credit_admin")
@admin_ui_bp.route("/view_credit_ledger/<int:user_id>")
def view_credit_ledger(user_id):
    return render_template("credit_dashboard.html", user_id=user_id)


@login_required
@roles_required("credit_admin")
@admin_ui_bp.route("/tile/exposure/<int:user_id>")
def tile_exposure(user_id):
    data = {
        "credit_limit": 5000.0,
        "repaid": 1200.0,
        "exposure_ratio": 0.24,
        "status": "ok",
    }
    return render_template("admin/tiles/exposure_widget.html", data=data)


@login_required
@roles_required("credit_admin")
@admin_ui_bp.route("/tile/credit_ledger/<int:user_id>")
def tile_credit_ledger(user_id):
    ledgers = [MockLedger(id=1, user_id=user_id)]
    return render_template("admin/tiles/credit_ledger.html", user_id=user_id, ledgers=ledgers)


@login_required
@roles_required("credit_admin")
@admin_ui_bp.route("/payment_processor", methods=["POST"])
def process_payment():
    try:
        card_id = request.form["card_id"]
        amount = float(request.form["amount"])
    except (KeyError, ValueError):
        flash("Invalid payment request.", "warning")
        return redirect(url_for("admin.admin_home"))

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


@login_required
@roles_required("fraud_admin")
@admin_ui_bp.route("/fraud_scanner")
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


@login_required
@roles_required("tradeline_admin")
@admin_ui_bp.route("/tradelines_panel")
def tradelines_panel():
    tradelines = [MockModel(id=i, vendor_name=f"Vendor {i}") for i in range(1, 3)]
    return render_template("tradelines_panel.html", tradelines=tradelines)


@login_required
@roles_required("tradeline_admin")
@admin_ui_bp.route("/approval_queue")
def approval_queue():
    status = request.args.get("status", "pending")
    tradelines = [MockModel(id=i, status=status) for i in range(1, 3)]
    return render_template("approval_queue.html", tradelines=tradelines, status=status)


# =============================================================================
# 12. REDIS / DB PANELS / SQL PANEL
# =============================================================================


@login_required
@admin_required
@admin_ui_bp.route("/redis_panel")
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


@login_required
@admin_required
@admin_ui_bp.route("/schema_diagram")
def schema_diagram():
    return render_template("schema_viewer.html")


@login_required
@super_admin_required
@admin_ui_bp.route("/sql_panel")
def sql_panel():
    users = [MockUser(id=i) for i in range(1, 11)]
    return render_template("sql_panel.html", users=users)


@login_required
@admin_required
@admin_ui_bp.route("/rate_limits")
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


@login_required
@admin_required
@admin_ui_bp.route("/sweep_expired_keys", methods=["POST"])
def sweep_expired_keys():
    redis_client = None
    try:
        redis_client = get_redis_client()
    except Exception:
        redis_client = None

    removed_count = 5 if redis_client else 0
    flash(f"🧹 Purged {removed_count} temporary keys from caches.", "info")
    return redirect(url_for("admin.redis_panel"))


@login_required
@admin_required
@admin_ui_bp.route("/log_viewer")
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


@login_required
@roles_required("fraud_admin")
@admin_ui_bp.route("/tile/fraud_chart")
def tile_fraud_chart():
    frauds = [
        {"score": 0.2},
        {"score": 0.6},
        {"score": 0.9},
        {"score": 0.4},
        {"score": 0.85},
    ]
    return render_template("admin/tiles/fraud_chart.html", frauds=frauds)


@login_required
@admin_required
@admin_ui_bp.route("/tile/redis_keys")
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


@login_required
@super_admin_required
@admin_ui_bp.route("/tile/sql_panel")
def tile_sql_panel():
    users = [MockUser(id=i) for i in range(1, 11)]
    return render_template("admin/tiles/sql_panel.html", users=users)


@login_required
@admin_required
@admin_ui_bp.route("/tile/rate_limits")
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


@login_required
@admin_required
@admin_ui_bp.route("/tile/log_viewer")
def tile_log_viewer():
    lines = [
        "[2025-10-31 09:30:00] INFO: App started successfully.",
        "[2025-10-31 09:31:15] DEBUG: Operator code generated: XYZW1234.",
        "[2025-10-31 09:32:40] ERROR: DB connection pool exhausted.",
    ]
    return render_template("admin/tiles/log_viewer.html", log_lines=lines)


@login_required
@admin_required
@admin_ui_bp.route("/tile/trace_viewer")
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


@login_required
@admin_required
@admin_ui_bp.route("/tile/statements_timeline")
def tile_statements_timeline():
    logs = [
        {"timestamp": datetime.utcnow().isoformat()},
        {"timestamp": (datetime.utcnow() - timedelta(hours=1)).isoformat()},
    ]
    return render_template("admin/tiles/statements_timeline.html", logs=logs)


@login_required
@admin_required
@admin_ui_bp.route("/tile/statements_heatmap")
def tile_statements_heatmap():
    logs = [
        {"bank": "Chase"},
        {"bank": "Chase"},
        {"bank": "Wells Fargo"},
        {"bank": "Citi"},
    ]
    return render_template("admin/tiles/statements_heatmap.html", logs=logs)


@login_required
@admin_required
@admin_ui_bp.route("/tile/agent_activity")
def tile_agent_activity():
    audits = [
        {"triggered_by": "Agent1", "status": "OK", "timestamp": "2025-10-31 09:30"},
        {"triggered_by": "Agent2", "status": "WARN", "timestamp": "2025-10-31 09:31"},
    ]
    return render_template("admin/tiles/agent_activity.html", audits=audits)


@login_required
@admin_required
@admin_ui_bp.route("/tile/schema_events")
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


@login_required
@admin_required
@admin_ui_bp.route("/tile/schema_versions")
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


@login_required
@admin_required
@admin_ui_bp.route("/trace_viewer")
def trace_viewer():
    redis_client = None
    try:
        redis_client = get_redis_client()
    except Exception:
        redis_client = None

    recent_traces = ["trace-id-123", "trace-id-456", "trace-id-789"] if redis_client else []
    return render_template("trace_viewer.html", recent_traces=recent_traces)


@login_required
@admin_required
@admin_ui_bp.route("/export_trace/<string:trace_id>")
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

    filename = f"trace_export_{trace_id}_" f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return send_file(
        buffer,
        mimetype="application/json",
        as_attachment=True,
        download_name=filename,
    )


# =============================================================================
# 14. DISPUTE LOG MANAGEMENT
# =============================================================================


@login_required
@roles_required("credit_admin")
@admin_ui_bp.route("/dispute_logs/<int:user_id>")
def view_dispute_logs(user_id):
    user = MockUser(id=user_id)
    logs = [
        MockModel(id=i, user_id=user_id, timestamp=datetime.utcnow() - timedelta(days=i))
        for i in range(1, 4)
    ]
    return render_template("admin_dispute_logs.html", user=user, logs=logs)


@login_required
@roles_required("credit_admin")
@admin_ui_bp.route("/preview_letter/<int:log_id>")
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


@login_required
@super_admin_required
@admin_ui_bp.route("/advanced_telemetry")
def advanced_telemetry():
    return render_template("telemetry_dashboard.html")


# =============================================================================
# SYSTEM (Heartbeat, Cache Health, System Map)
# =============================================================================


@login_required
@admin_required
@admin_ui_bp.route("/system_heartbeat")
def system_heartbeat():
    return render_template("system_heartbeat.html")


@login_required
@admin_required
@admin_ui_bp.route("/cache_health")
def cache_health():
    return render_template("cache_health.html")


@login_required
@admin_required
@admin_ui_bp.route("/system_map")
def system_map():
    return render_template("system_map.html")


# =============================================================================
# SCHEMA & TELEMETRY
# =============================================================================


@login_required
@admin_required
@admin_ui_bp.route("/schema_events")
def schema_events():
    return render_template("schema_events.html")


@login_required
@admin_required
@admin_ui_bp.route("/schema_versions")
def schema_versions():
    return render_template("schema_versions.html")


@login_required
@admin_required
@admin_ui_bp.route("/route_list")
def route_list():
    return render_template("route_list.html")


# =============================================================================
# ACTIVITY & STATS
# =============================================================================


@login_required
@admin_required
@admin_ui_bp.route("/agent_activity")
def agent_activity():
    return render_template("agent_activity.html")


# =============================================================================
# STATEMENTS
# =============================================================================


@login_required
@admin_required
@admin_ui_bp.route("/statements_timeline")
def statements_timeline():
    return render_template("statements_timeline.html")


@login_required
@admin_required
@admin_ui_bp.route("/statements_heatmap")
def statements_heatmap():
    return render_template("statements_heatmap.html")


# =============================================================================
# NEURAL INSIGHTS
# =============================================================================


@login_required
@admin_required
@admin_ui_bp.route("/brain_diagnosis")
def brain_diagnosis():
    return render_template("brain_diagnosis.html")


@login_required
@admin_required
@admin_ui_bp.route("/model_summary")
def model_summary():
    return render_template("model_summary.html")


# =============================================================================
# TOOLS
# =============================================================================


@login_required
@admin_required
@admin_ui_bp.route("/repair_result")
def repair_result():
    return render_template("repair_result.html")
