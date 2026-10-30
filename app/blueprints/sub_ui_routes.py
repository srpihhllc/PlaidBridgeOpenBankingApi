# =============================================================================
# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/blueprints/sub_ui_routes.py
# Subscriber Routes (FINAL, CLEAN, DTO-SAFE, SUBSCRIBER-ONLY)
# =============================================================================

import json
import os
import threading
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any, cast

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    render_template_string,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from app.constants import (
    BLUEPRINT_AUDIT_KEY,
    DEFAULT_TTL,
    OPERATOR_MODE_KEY,
)
from app.decorators.access import has_permission, is_creator
from app.dto.transaction_dto import TransactionDTO
from app.extensions import db
from app.models.registry import Registry
from app.models.todo import Todo
from app.models.transactions import Transaction
from app.models.user_dashboard import UserDashboard
from app.services.category_analytics import compute_category_summary
from app.services.fraud_analytics import compute_fraud_summary
from app.services.timeline_analytics import compute_timeline
from app.utils.redis_utils import get_redis_client
from app.utils.telemetry import log_identity_event

sub_bp = Blueprint("sub_ui", __name__, url_prefix="/sub")


# =============================================================================
# Access Control
# =============================================================================

def require_subscriber() -> Any:
    """Strictly deny lenders; allow creators/owners and authorized subscribers."""
    if not getattr(current_user, "is_authenticated", False):
        abort(401)

    role = getattr(current_user, "role", None)

    # 1. Absolute lender denial
    if role == "lender":
        current_app.logger.warning(
            "ACCESS DENIED: Standard lender role attempted subscriber UI access"
        )
        abort(403)

    # 2. Creator / owner / admin super-user check
    if is_creator(current_user) or role in ("creator", "owner", "admin"):
        return current_user

    # 3. Operator mode / operational access
    operator_mode = session.get(OPERATOR_MODE_KEY) is True
    operational_access = has_permission(current_user, "read_operational_data")

    if operator_mode or operational_access:
        return current_user

    # 4. Standard subscriber check
    if role != "subscriber":
        current_app.logger.warning(
            "ACCESS CHECK: operator_mode=%r role=%r operational_access=%r",
            operator_mode,
            role,
            operational_access,
        )
        abort(403)

    return current_user


# =============================================================================
# Dashboard Telemetry & Missing API Routes
# =============================================================================

@sub_bp.route("/api/subscriber/token-pulse", methods=["GET"])
@login_required
def subscriber_token_pulse():
    """Return access token telemetry for the dashboard card."""
    user = require_subscriber()
    return jsonify({
        "status": "active",
        "ttl_seconds": 3600,
        "user_id": getattr(user, "id", None),
        "username": getattr(user, "username", "subscriber"),
    }), 200


@sub_bp.route("/api/subscriber/vault-activity", methods=["GET"])
@login_required
def subscriber_vault_activity():
    """Return recent vault activity data for the dashboard card."""
    require_subscriber()
    return jsonify({
        "status": "ok",
        "activity": [],
        "total_events": 0,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }), 200


@sub_bp.route("/api/trace/<key>", methods=["GET"])
@login_required
def get_trace_overlay(key: str):
    """Serve trace diagnostic data for trace_overlay.js mounts."""
    require_subscriber()
    return jsonify({
        "key": key,
        "label": f"Trace ({key})",
        "remaining_seconds": 300,
        "fresh": "True",
    }), 200


# =============================================================================
# Template Audit
# =============================================================================

TTL_KEY = BLUEPRINT_AUDIT_KEY
TTL_SECONDS = DEFAULT_TTL

_EXPECTED_TEMPLATES_MANIFEST: set[str] = {
    "sub/subscriber_dashboard.html",
    "sub/profile.html",
    "sub/fraud_drilldown.html",
    "sub/settings.html",
    "sub/vault_dashboard.html",
}

_TEMPLATE_CACHE: list[str] = []
_TEMPLATE_CACHE_LAST_WALK = datetime.min.replace(tzinfo=timezone.utc)
_TEMPLATE_CACHE_EXPIRY_SECONDS = 300
_TEMPLATE_CACHE_LOCK = threading.Lock()


def list_templates() -> Iterator[str]:
    """Return cached HTML template paths."""
    global _TEMPLATE_CACHE
    global _TEMPLATE_CACHE_LAST_WALK

    force_refresh = current_app.config.get("FORCE_TEMPLATE_REFRESH", False)
    expired = (
        datetime.now(timezone.utc) - _TEMPLATE_CACHE_LAST_WALK
    ).total_seconds() >= _TEMPLATE_CACHE_EXPIRY_SECONDS

    if _TEMPLATE_CACHE and not force_refresh and not expired:
        return iter(_TEMPLATE_CACHE)

    with _TEMPLATE_CACHE_LOCK:
        if _TEMPLATE_CACHE and not force_refresh and not expired:
            return iter(_TEMPLATE_CACHE)

        template_root = os.path.join(current_app.root_path, "templates")
        templates: list[str] = []

        for base, _, files in os.walk(template_root):
            for filename in files:
                if not filename.endswith(".html") or filename.startswith("_"):
                    continue

                absolute_path = os.path.join(base, filename)
                relative_path = os.path.relpath(absolute_path, template_root)
                templates.append(relative_path.replace(os.sep, "/"))

        _TEMPLATE_CACHE = templates
        _TEMPLATE_CACHE_LAST_WALK = datetime.now(timezone.utc)

    return iter(_TEMPLATE_CACHE)


def is_subscriber_template(template_name: str) -> bool:
    return template_name.startswith("sub/")


def _emit_blueprint_audit_trace() -> dict[str, Any]:
    all_templates = set(list_templates())
    expected = _EXPECTED_TEMPLATES_MANIFEST

    missing = expected - all_templates
    extras = {
        template
        for template in all_templates
        if is_subscriber_template(template)
    } - expected

    status = "DRIFT_DETECTED" if missing or extras else "COCKPIT_ACTIVE"

    audit_data: dict[str, Any] = {
        "last_audit_date": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "audit_status": status,
        "expected_sub": len(expected),
        "actual_sub": sum(
            1 for template in all_templates if is_subscriber_template(template)
        ),
        "missing": len(missing),
        "extras": len(extras),
        "audit_issues": len(missing) + len(extras),
        "drift_details": {
            "missing_list": sorted(missing),
            "extras_list": sorted(extras),
        },
    }

    try:
        redis_client = (
            getattr(current_app, "redis_client", None) or get_redis_client()
        )

        if redis_client:
            redis_client.setex(TTL_KEY, TTL_SECONDS, json.dumps(audit_data))
    except Exception as exc:
        audit_data["status"] = "error"
        audit_data["audit_status"] = "ERROR"
        audit_data["message"] = str(exc)

    return audit_data


def get_audit_info() -> dict[str, Any]:
    try:
        redis_client = (
            getattr(current_app, "redis_client", None) or get_redis_client()
        )

        if redis_client:
            raw_data = redis_client.get(TTL_KEY)

            if raw_data:
                if isinstance(raw_data, bytes):
                    raw_data = raw_data.decode("utf-8")

                parsed_data: Any = json.loads(raw_data)
                if isinstance(parsed_data, dict):
                    return cast(dict[str, Any], parsed_data)

                raise ValueError("Stored audit data must be a JSON object.")

        return _emit_blueprint_audit_trace()

    except Exception as exc:
        return {
            "last_audit_date": datetime.now(timezone.utc).isoformat(),
            "status": "unavailable",
            "audit_status": "UNAVAILABLE",
            "audit_issues": 0,
            "message": "Error retrieving audit data.",
            "error": type(exc).__name__,
        }


# =============================================================================
# Telemetry
# =============================================================================

def _emit_subscriber_ui_rendered(
    user,
    view_name: str,
    template_name: str,
    extra: dict | None = None,
):
    details = {
        "view": view_name,
        "template": template_name,
        "path": request.path,
    }

    if extra:
        details.update(extra)

    log_identity_event(
        user_id=user.id,
        event_type="SUBSCRIBER_UI_RENDERED",
        details=details,
        ip=request.remote_addr,
    )


# =============================================================================
# Subscriber Routes
# =============================================================================

@sub_bp.route("/", strict_slashes=False)
def sub_index():
    if current_app.config.get("DEBUG_UI"):
        try:
            templates = list(list_templates())
        except Exception:
            templates = []

        return jsonify({"templates": templates}), 200

    authenticated = getattr(
        current_user,
        "is_authenticated",
        False,
    )
    is_subscriber = (
        authenticated
        and getattr(current_user, "role", None) == "subscriber"
    )
    is_operator = session.get(OPERATOR_MODE_KEY) is True

    if is_subscriber or is_operator:
        user = require_subscriber()

        log_identity_event(
            user_id=getattr(user, "id", "operator"),
            event_type="SUBSCRIBER_INDEX_ACCESS",
            details={"via": "sub_ui.sub_index"},
            ip=request.remote_addr,
        )

        return redirect(url_for("sub_ui.dashboard"))

    return redirect(url_for("main.subscriber_login"))


@sub_bp.route("/dashboard", endpoint="dashboard")
@login_required
def dashboard():
    user = require_subscriber()
    is_operator = bool(session.get(OPERATOR_MODE_KEY, False))

    log_identity_event(
        user_id=user.id,
        event_type="SUBSCRIBER_DASHBOARD_ACCESS",
        details={"via": "sub_ui.dashboard"},
        ip=request.remote_addr,
    )

    try:
        audit_info = get_audit_info()

        if not isinstance(audit_info, dict):
            raise ValueError("Malformed audit data")

    except Exception as exc:
        current_app.logger.warning(
            "Using fallback audit payload: %s",
            exc,
        )
        audit_info = {
            "last_audit_date": datetime.now(
                timezone.utc
            ).isoformat(),
            "audit_status": "INITIALIZING",
            "audit_issues": 0,
        }

    profile = {
        "username": getattr(user, "username", None),
        "full_name": getattr(user, "full_name", None),
    }

    dashboard_model = getattr(user, "user_dashboard", None)

    if dashboard_model is None:
        dashboard_model = UserDashboard.create_for_user(user.id)
        db.session.add(dashboard_model)
        db.session.commit()

    dashboard_settings = (
        dashboard_model.settings
        or UserDashboard.default_settings()
    )

    raw_transactions = (
        Transaction.query
        .filter_by(user_id=user.id)
        .order_by(Transaction.date.desc())
        .all()
    )
    transactions = [
        TransactionDTO.from_model(transaction)
        for transaction in raw_transactions
    ]

    category_summary = compute_category_summary(transactions)
    fraud_summary = compute_fraud_summary(transactions)
    timeline = compute_timeline(transactions)

    try:
        from app.services.transaction_analysis import (
            compute_transaction_summary,
        )

        transaction_summary = compute_transaction_summary(
            transactions,
        )
    except Exception:
        transaction_summary = None

    page = max(
        request.args.get("page", 1, type=int),
        1,
    )
    per_page = 20
    total_items = len(transactions)
    total_pages = max(
        (total_items + per_page - 1) // per_page,
        1,
    )

    start_index = (page - 1) * per_page
    end_index = page * per_page
    paged_transactions = transactions[start_index:end_index]

    todo_query = Todo.query.filter_by(user_id=user.id)
    pending_todos = todo_query.filter_by(
        completed=False,
    ).all()
    completed_todos = todo_query.filter_by(
        completed=True,
    ).all()

    if is_operator:
        seeded_services = Registry.query.all()
    else:
        seeded_services = Registry.query.filter_by(
            user_id=user.id,
        ).all()

    processed_services = []

    for service in seeded_services:
        try:
            if isinstance(service.config_blob, str):
                config = json.loads(service.config_blob)
            else:
                config = service.config_blob

            processed_services.append(
                {
                    "id": service.id,
                    "name": service.name,
                    "config": config,
                }
            )
        except Exception:
            continue

    template_name = "sub/subscriber_dashboard.html"

    _emit_subscriber_ui_rendered(
        user,
        view_name="sub_ui.dashboard",
        template_name=template_name,
        extra={
            "transaction_count": len(transactions),
            "pending_todos": len(pending_todos),
            "completed_todos": len(completed_todos),
        },
    )

    return render_template(
        template_name,
        audit_info=audit_info,
        profile=profile,
        transactions=paged_transactions,
        category_summary=category_summary,
        fraud_summary=fraud_summary,
        timeline=timeline,
        transaction_summary=transaction_summary,
        page=page,
        total_pages=total_pages,
        dashboard_settings=dashboard_settings,
        pending_todos=pending_todos,
        completed_todos=completed_todos,
        service_registry=processed_services,
        is_operator=is_operator,
    )


@sub_bp.route(
    "/update-profile",
    methods=["POST"],
    endpoint="update_profile",
)
@login_required
def update_profile():
    user = require_subscriber()

    user.primary_phone = request.form.get(
        "primary_phone",
        "",
    ).strip()
    user.business_phone = request.form.get(
        "business_phone",
        "",
    ).strip()
    user.first_name = request.form.get(
        "first_name",
        "",
    ).strip()
    user.last_name = request.form.get(
        "last_name",
        "",
    ).strip()

    db.session.commit()

    return redirect(url_for("sub_ui.settings"))


@sub_bp.route("/settings", endpoint="settings")
@login_required
def settings():
    user = require_subscriber()

    log_identity_event(
        user_id=user.id,
        event_type="SUBSCRIBER_SETTINGS_ACCESS",
        details={},
        ip=request.remote_addr,
    )

    dashboard_model = getattr(user, "user_dashboard", None)

    if dashboard_model is None:
        dashboard_model = UserDashboard.create_for_user(user.id)
        db.session.add(dashboard_model)
        db.session.commit()

    dashboard_settings = (
        dashboard_model.settings
        or UserDashboard.default_settings()
    )
    template_name = "sub/settings.html"

    _emit_subscriber_ui_rendered(
        user,
        view_name="sub_ui.settings",
        template_name=template_name,
    )

    return render_template(
        template_name,
        dashboard_settings=dashboard_settings,
    )


@sub_bp.route(
    "/fraud/drilldown",
    endpoint="fraud_drilldown",
)
@login_required
def fraud_drilldown():
    user = require_subscriber()

    raw_transactions = (
        Transaction.query
        .filter_by(user_id=user.id)
        .order_by(Transaction.date.desc())
        .all()
    )
    transactions = [
        TransactionDTO.from_model(transaction)
        for transaction in raw_transactions
    ]

    fraud_summary = compute_fraud_summary(transactions)
    timeline = compute_timeline(transactions)
    flagged_transactions = [
        transaction
        for transaction in transactions
        if getattr(transaction, "is_flagged", False)
    ]

    template_name = "sub/fraud_drilldown.html"

    _emit_subscriber_ui_rendered(
        user,
        view_name="sub_ui.fraud_drilldown",
        template_name=template_name,
        extra={
            "flagged_count": len(flagged_transactions),
        },
    )

    return render_template(
        template_name,
        fraud_summary=fraud_summary,
        flagged_transactions=flagged_transactions,
        timeline=timeline,
    )


@sub_bp.route("/audit_trace", methods=["GET"])
@login_required
def audit_trace():
    user = require_subscriber()

    payload = {
        "user_id": user.id,
        "role": user.role,
        "path": request.path,
        "endpoint": request.endpoint,
    }

    log_identity_event(
        user_id=user.id,
        event_type="SUBSCRIBER_AUDIT_TRACE_VIEWED",
        details=payload,
        ip=request.remote_addr,
    )

    return jsonify(payload), 200


@sub_bp.route("/navbar_probe", methods=["GET"])
@login_required
def navbar_probe():
    user = require_subscriber()

    details = {
        "path": request.path,
        "endpoint": request.endpoint,
        "role": user.role,
    }

    log_identity_event(
        user_id=user.id,
        event_type="SUBSCRIBER_NAVBAR_RENDERED",
        details=details,
        ip=request.remote_addr,
    )

    return jsonify({"ok": True}), 200


@sub_bp.route("/vaults", endpoint="vault_dashboard")
@login_required
def vault_dashboard():
    user = require_subscriber()

    from app.dto.vault_dto import VaultTransactionDTO
    from app.models.vault_transaction import VaultTransaction
    from app.services.vault_analytics import (
        compute_vault_flow,
        compute_vault_fraud_signals,
        compute_vault_summary,
    )

    raw_transactions = (
        VaultTransaction.query
        .filter_by(user_id=user.id)
        .order_by(VaultTransaction.created_at.desc())
        .all()
    )

    vault_transactions = [
        VaultTransactionDTO.from_model(transaction)
        for transaction in raw_transactions
    ]

    summary = compute_vault_summary(raw_transactions)
    flow_labels, flow_values = compute_vault_flow(
        raw_transactions,
    )
    fraud_signals = compute_vault_fraud_signals(
        raw_transactions,
    )

    template_name = "sub/vault_dashboard.html"

    _emit_subscriber_ui_rendered(
        user,
        view_name="sub_ui.vault_dashboard",
        template_name=template_name,
        extra={
            "vault_txn_count": len(vault_transactions),
        },
    )

    return render_template(
        template_name,
        vault_txns=vault_transactions,
        summary=summary,
        flow_labels=flow_labels,
        flow_values=flow_values,
        fraud_signals=fraud_signals,
    )


# =============================================================================
# Operator and Diagnostic Placeholders
# =============================================================================

@sub_bp.route("/debug/dto", endpoint="debug_dto")
@login_required
def debug_dto():
    require_subscriber()

    return render_template_string(
        """
        <h1>DTO Inspector</h1>
        <p>This tool will inspect DTO mappings.</p>
        """
    )


@sub_bp.route("/audit/report", endpoint="audit_report")
@login_required
def audit_report():
    require_subscriber()

    return render_template_string(
        """
        <h1>Audit Report</h1>
        <p>This will show audit results and schema drift.</p>
        """
    )


@sub_bp.route(
    "/tile/diagnostics",
    endpoint="tile_diagnostics",
)
@login_required
def tile_diagnostics():
    require_subscriber()

    return render_template_string(
        """
        <h1>Tile Diagnostics</h1>
        <p>This will show tile render status and errors.</p>
        """
    )


# =============================================================================
# Dynamic Template Previewer
# =============================================================================

@sub_bp.route(
    "/t/<path:tpl>",
    endpoint="render_sub_template",
)
@login_required
def render_sub_template(tpl: str):
    user = require_subscriber()

    if not tpl.endswith(".html"):
        tpl = f"{tpl}.html"

    template_name = (
        tpl if tpl.startswith("sub/") else f"sub/{tpl}"
    )

    if template_name not in _EXPECTED_TEMPLATES_MANIFEST:
        abort(404)

    _emit_subscriber_ui_rendered(
        user,
        view_name="sub_ui.render_sub_template",
        template_name=template_name,
        extra={"preview": True},
    )

    class MockUser:
        id = 0
        username = "preview_user"
        full_name = "Preview User"
        email = "preview@example.com"
        is_active = True
        role = "subscriber"
        total_balance = 0.0
        user_dashboard = None

    mock_user = MockUser()

    mock_context = {
        "current_user": mock_user,
        "user": mock_user,
        "dashboard_settings": {
            "theme": "dark",
            "compact_mode": False,
        },
        "audit_info": {
            "status": "ok",
            "audit_status": "COCKPIT_ACTIVE",
            "audit_issues": 0,
            "last_audit_date": datetime.now(
                timezone.utc,
            ).isoformat(),
        },
        "profile": {
            "username": "smoke_test_user",
            "full_name": "Smoke Test Operator",
        },
        "transactions": [],
        "flagged_transactions": [],
        "category_summary": {},
        "fraud_summary": {
            "flagged_count": 0,
            "total_risk_score": 0.0,
        },
        "timeline": [],
        "transaction_summary": {
            "income": 0,
            "expenses": 0,
            "net": 0,
        },
        "page": 1,
        "total_pages": 1,
        "pending_todos": [],
        "completed_todos": [],
        "service_registry": [],
        "is_operator": False,
        "vault_txns": [],
        "summary": {},
        "flow_labels": [],
        "flow_values": [],
        "fraud_signals": [],
    }

    return render_template(
        template_name,
        **mock_context,
    )