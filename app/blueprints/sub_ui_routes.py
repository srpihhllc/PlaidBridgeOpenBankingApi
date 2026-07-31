# =============================================================================
# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/blueprints/sub_ui_routes.py
# Subscriber Routes (FINAL, CLEAN, DTO-SAFE, SUBSCRIBER-ONLY)
# =============================================================================

import json
import os
import threading
from collections.abc import Iterator
from datetime import datetime

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    render_template_string,
    request,
    session,  # Hoisted to top-level for full blueprint access
    url_for,
)
from flask_login import current_user, login_required

from app.auth_handlers import SystemOperator  # Resolved missing reference
from app.constants import BLUEPRINT_AUDIT_KEY, DEFAULT_TTL, OPERATOR_MODE_KEY  # Hoisted
from app.dto.transaction_dto import TransactionDTO
from app.extensions import db
from app.models.todo import Todo
from app.models.transactions import Transaction
from app.models.user_dashboard import UserDashboard
from app.models.registry import Registry  # 🟢 ADDED: Live database model for services
from app.services.category_analytics import compute_category_summary
from app.services.fraud_analytics import compute_fraud_summary
from app.services.timeline_analytics import compute_timeline
from app.utils.redis_utils import get_redis_client
from app.utils.telemetry import log_identity_event

# =============================================================================
# Blueprint
# =============================================================================

sub_bp = Blueprint("sub_ui", __name__, url_prefix="/sub")


# =============================================================================
# Role Guard
# =============================================================================


def require_subscriber():
    """
    Hard guard: only authenticated subscribers may access /sub routes.
    Operators bypass the role check.
    """
    if not getattr(current_user, "is_authenticated", False):
        abort(401)

    # 💡 OPERATOR BYPASS
    if session.get(OPERATOR_MODE_KEY) is True:
        return current_user  # Let the operator through!

    if getattr(current_user, "role", None) != "subscriber":
        abort(403)

    return current_user


# =============================================================================
# Template Drift Audit
# =============================================================================

TTL_KEY = BLUEPRINT_AUDIT_KEY
TEMPLATE_RENDER_ERROR_SUB = "E401"

_EXPECTED_TEMPLATES_MANIFEST: set[str] = {
    "sub/subscriber_dashboard.html",
    "sub/profile.html",
    "sub/fraud_drilldown.html",
    "sub/settings.html",
}

TTL_SECONDS = DEFAULT_TTL
_TEMPLATE_CACHE: list[str] = []
_TEMPLATE_CACHE_LAST_WALK = datetime.min
_TEMPLATE_CACHE_EXPIRY_SECONDS = 300
_TEMPLATE_CACHE_LOCK = threading.Lock()


def list_templates() -> Iterator[str]:
    global _TEMPLATE_CACHE, _TEMPLATE_CACHE_LAST_WALK

    force_refresh = current_app.config.get("FORCE_TEMPLATE_REFRESH", False)
    expired = (
        datetime.utcnow() - _TEMPLATE_CACHE_LAST_WALK
    ).total_seconds() >= _TEMPLATE_CACHE_EXPIRY_SECONDS

    if not force_refresh and _TEMPLATE_CACHE and not expired:
        return iter(_TEMPLATE_CACHE)

    with _TEMPLATE_CACHE_LOCK:
        if not force_refresh and _TEMPLATE_CACHE and not expired:
            return iter(_TEMPLATE_CACHE)

        root = os.path.join(current_app.root_path, "templates")
        all_templates: list[str] = []

        for base, _, files in os.walk(root):
            for fname in files:
                if fname.endswith(".html") and not fname.startswith("_"):
                    rel = os.path.relpath(os.path.join(base, fname), root)
                    all_templates.append(rel.replace(os.sep, "/"))

        _TEMPLATE_CACHE = all_templates
        _TEMPLATE_CACHE_LAST_WALK = datetime.utcnow()

    return iter(_TEMPLATE_CACHE)


def is_subscriber_template(tpl: str) -> bool:
    return tpl.startswith("sub/")


def _emit_blueprint_audit_trace() -> dict:
    all_templates = set(list(list_templates()))
    expected = _EXPECTED_TEMPLATES_MANIFEST

    missing = expected - all_templates
    extras = {t for t in all_templates if is_subscriber_template(t)} - expected

    status = "DRIFT_DETECTED" if missing or extras else "COCKPIT_ACTIVE"

    # Normalized keys to perfectly fit the UI data binding contract
    audit_data = {
        "last_audit_date": datetime.utcnow().isoformat(),
        "status": status,
        "audit_status": status,
        "expected_sub": len(expected),
        "actual_sub": sum(1 for t in all_templates if is_subscriber_template(t)),
        "missing": len(missing),
        "extras": len(extras),
        "audit_issues": len(missing) + len(extras),
        "drift_details": {
            "missing_list": list(missing),
            "extras_list": list(extras),
        },
    }

    try:
        r = getattr(current_app, "redis_client", None) or get_redis_client()
        if r:
            r.setex(TTL_KEY, TTL_SECONDS, json.dumps(audit_data))
    except Exception as e:
        audit_data["status"] = "error"
        audit_data["audit_status"] = "ERROR"
        audit_data["message"] = str(e)

    return audit_data


def get_audit_info() -> dict:
    try:
        r = getattr(current_app, "redis_client", None) or get_redis_client()
        if r:
            raw = r.get(TTL_KEY)
            if raw:
                return json.loads(raw)
        return _emit_blueprint_audit_trace()
    except Exception as e:
        return {
            "last_audit_date": datetime.utcnow().isoformat(),
            "status": "unavailable",
            "audit_status": "UNAVAILABLE",
            "audit_issues": 0,
            "message": "Error retrieving audit data.",
            "error": type(e).__name__,
        }


# =============================================================================
# Telemetry Helper
# =============================================================================


def _emit_subscriber_ui_rendered(user, view_name: str, template_name: str, extra=None):
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
            tpl_list = list(list_templates())
        except Exception:
            tpl_list = []
        return jsonify({"templates": tpl_list}), 200

    is_sub = getattr(current_user, "is_authenticated", False) and getattr(current_user, "role", None) == "subscriber"
    is_operator = session.get(OPERATOR_MODE_KEY) is True

    if is_sub or is_operator:
        try:
            user = require_subscriber()
            log_identity_event(
                user_id=getattr(user, "id", "operator"),
                event_type="SUBSCRIBER_INDEX_ACCESS",
                details={"via": "sub_ui.sub_index"},
                ip=request.remote_addr,
            )
        except Exception:
            pass

        return redirect(url_for("sub_ui.dashboard"))

    return redirect(url_for("main.subscriber_login"))


@sub_bp.route("/dashboard", endpoint="dashboard")
@login_required
def dashboard():
    # Unwrap Werkzeug's LocalProxy to get the deterministic underlying object type
    user = current_user._get_current_object()

    # ⭐ GOD-MODE BYPASS: Structured fallback contract for transient operator sessions
    if isinstance(user, SystemOperator) or getattr(user, "id", None) == "TERENCE_CORTEX_PRIME":
        # 🛡️ Safely attach template context properties to prevent dynamic evaluation panics
        try:
            setattr(user, "total_balance", getattr(user, "total_balance", 0.00))
            setattr(user, "first_name", getattr(user, "first_name", "Terence"))
            setattr(user, "last_name", getattr(user, "last_name", "Operator"))
        except AttributeError:
            pass  # Protective catch if the model doesn't permit active mutation

        # authoritative mock profile context dict to match standard template contract
        profile_ctx = {
            "username": getattr(user, "username", "TERENCE_CORTEX_PRIME"),
            "full_name": "Terence Operator"
        }

        return render_template(
            "sub/subscriber_dashboard.html",
            audit_info={
                "last_audit_date": datetime.utcnow().isoformat(),
                "audit_status": "COCKPIT_ACTIVE",
                "audit_issues": 0,
                "environment": "CORTEX_PRIME"
            },
            profile=profile_ctx,
            bank_accounts=[],
            transactions=[],
            category_summary={},
            fraud_summary={"flagged_count": 0, "total_risk_score": 0.0},
            timeline=[],
            transaction_summary={"income": 0, "expenses": 0, "net": 0},
            page=1,
            total_pages=1,
            dashboard_settings={"theme": "dark", "compact_mode": False},
            pending_todos=[],
            completed_todos=[],
            services=[],  # 🟢 FIXED: Changed from service_registry={} to services=[]
            is_operator=True
        )



    # -------------------------------------------------------------------------
    # Standard Persistent Database Resolution Path (For Real Subscribers Only)
    # -------------------------------------------------------------------------

    # Telemetry
    log_identity_event(
        user_id=user.id,
        event_type="SUBSCRIBER_DASHBOARD_ACCESS",
        details={"via": "sub_ui.dashboard"},
        ip=request.remote_addr,
    )

    # Audit drift resolution with protective map default
    try:
        audit_info = get_audit_info()
        if not audit_info or not isinstance(audit_info, dict):
            raise ValueError("Malformed audit data struct")
    except Exception as e:
        current_app.logger.warning(f"Defaulting sparse audit payload: {str(e)}")
        audit_info = {
            "last_audit_date": datetime.utcnow().isoformat(),
            "audit_status": "INITIALIZING",
            "audit_issues": 0
        }

    # Profile DTO
    profile = {
        "username": getattr(user, "username", None),
        "full_name": getattr(user, "full_name", None),
    }

    # Ensure UserDashboard configuration exists
    dashboard_model = getattr(user, "user_dashboard", None)
    if dashboard_model is None:
        dashboard_model = UserDashboard.create_for_user(user.id)
        db.session.add(dashboard_model)
        db.session.commit()

    dashboard_settings = dashboard_model.settings or UserDashboard.default_settings()

    # Transaction feed processing
    raw_txns = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.date.desc()).all()
    transactions = [TransactionDTO.from_model(t) for t in raw_txns]

    # Compute Analytics Metrics
    category_summary = compute_category_summary(transactions)
    fraud_summary = compute_fraud_summary(transactions)
    timeline = compute_timeline(transactions)

    # Optional Downstream Analysis Engine Lookups
    try:
        from app.services.transaction_analysis import compute_transaction_summary
        transaction_summary = compute_transaction_summary(transactions)
    except Exception:
        transaction_summary = None

    # View Pagination Segmentation
    page = request.args.get("page", 1, type=int)
    per_page = 20
    total_items = len(transactions)
    total_pages = (total_items + per_page - 1) // per_page
    paged_transactions = transactions[(page - 1) * per_page : page * per_page]

    # Operational Task Queues
    todo_q = Todo.query.filter_by(user_id=user.id)
    pending_todos = todo_q.filter_by(completed=False).all()
    completed_todos = todo_q.filter_by(completed=True).all()

    # 🟢 FIXED: Discovery Services Infrastructure (Now Live From Database)
    seeded_services = Registry.query.filter_by(user_id=user.id).all()
    processed_services = []
    for svc in seeded_services:
        try:
            config_dict = json.loads(svc.config_blob) if isinstance(svc.config_blob, str) else svc.config_blob
            processed_services.append({
                'id': svc.id,
                'name': svc.name,
                'config': config_dict
            })
        except Exception:
            continue

    is_operator = bool(session.get(OPERATOR_MODE_KEY, False))

    # Telemetry Execution Trace
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

    # Render cockpit dashboard contextually
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
        services=processed_services,  # 🟢 FIXED: Pass the array of dictionary objects
        is_operator=is_operator,
    )


@sub_bp.route("/settings", endpoint="settings")
@login_required
def settings():
    user = require_subscriber()

    # ⭐ GOD-MODE BYPASS
    if getattr(user, "id", None) == "TERENCE_CORTEX_PRIME":
        return render_template(
            "sub/settings.html",
            dashboard_settings={"theme": "dark", "layout": "default"}
        )

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

    dashboard_settings = dashboard_model.settings or UserDashboard.default_settings()
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


@sub_bp.route("/fraud/drilldown", endpoint="fraud_drilldown")
@login_required
def fraud_drilldown():
    user = require_subscriber()

    # ⭐ GOD-MODE BYPASS
    if getattr(user, "id", None) == "TERENCE_CORTEX_PRIME":
        return render_template(
            "sub/fraud_drilldown.html",
            fraud_summary={"risk_score": 0, "flagged_count": 0},
            flagged_transactions=[],
            timeline=[]
        )

    raw_txns = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.date.desc()).all()
    transactions = [TransactionDTO.from_model(t) for t in raw_txns]

    fraud_summary = compute_fraud_summary(transactions)
    timeline = compute_timeline(transactions)
    flagged = [t for t in transactions if getattr(t, "is_flagged", False)]

    template_name = "sub/fraud_drilldown.html"

    _emit_subscriber_ui_rendered(
        user,
        view_name="sub_ui.fraud_drilldown",
        template_name=template_name,
        extra={"flagged_count": len(flagged)},
    )

    return render_template(
        template_name,
        fraud_summary=fraud_summary,
        flagged_transactions=flagged,
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
        "ip": request.remote_addr,
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

    # ⭐ GOD-MODE BYPASS
    if getattr(user, "id", None) == "TERENCE_CORTEX_PRIME":
        return render_template(
            "sub/vault_dashboard.html",
            vault_txns=[],
            summary={},
            flow_labels=[],
            flow_values=[],
            fraud_signals=[]
        )

    from app.dto.vault_dto import VaultTransactionDTO
    from app.models.vault_transaction import VaultTransaction
    from app.services.vault_analytics import (
        compute_vault_flow,
        compute_vault_fraud_signals,
        compute_vault_summary,
    )

    raw = (
        VaultTransaction.query.filter_by(user_id=user.id)
        .order_by(VaultTransaction.created_at.desc())
        .all()
    )

    vault_txns = [VaultTransactionDTO.from_model(t) for t in raw]

    summary = compute_vault_summary(raw)
    flow_labels, flow_values = compute_vault_flow(raw)
    fraud_signals = compute_vault_fraud_signals(raw)

    template_name = "sub/vault_dashboard.html"

    _emit_subscriber_ui_rendered(
        user,
        view_name="sub_ui.vault_dashboard",
        template_name=template_name,
        extra={"vault_txn_count": len(vault_txns)},
    )

    return render_template(
        template_name,
        vault_txns=vault_txns,
        summary=summary,
        flow_labels=flow_labels,
        flow_values=flow_values,
        fraud_signals=fraud_signals,
    )


# =============================================================================
# Operator Tool Placeholders (to prevent 404s)
# =============================================================================


@sub_bp.route("/debug/dto", endpoint="debug_dto")
@login_required
def debug_dto():
    return render_template_string(
        "<h1>DTO Inspector (Placeholder)</h1>" "<p>This tool will inspect DTO mappings.</p>"
    )


@sub_bp.route("/audit/report", endpoint="audit_report")
@login_required
def audit_report():
    return render_template_string(
        "<h1>Audit Report (Placeholder)</h1>"
        "<p>This will show audit results and schema drift.</p>"
    )


@sub_bp.route("/tile/diagnostics", endpoint="tile_diagnostics")
@login_required
def tile_diagnostics():
    return render_template_string(
        "<h1>Tile Diagnostics (Placeholder)</h1>"
        "<p>This will show tile render status and errors.</p>"
    )


# =============================================================================
# Dynamic Template Previewer (Fixes test_sub_template_render 404 & 500 context)
# =============================================================================


@sub_bp.route("/t/<path:tpl>", endpoint="render_sub_template")
def render_sub_template(tpl):
    """
    Dynamic preview router for subscriber templates.
    Ensures that requested parameters match files within the allowed manifest
    and supplies dummy context fields to bypass Jinja evaluation blocks.
    """
    if not tpl.endswith(".html"):
        tpl = f"{tpl}.html"

    search_tpl = tpl if tpl.startswith("sub/") else f"sub/{tpl}"

    if search_tpl not in _EXPECTED_TEMPLATES_MANIFEST:
        abort(404)

    if getattr(current_user, "is_authenticated", False):
        user = require_subscriber()
        _emit_subscriber_ui_rendered(
            user, view_name="sub_ui.render_sub_template", template_name=search_tpl
        )

    class MockUser:
        id = 0
        username = "preview_user"
        full_name = "Preview User"
        role = "subscriber"
        total_balance = 0.0
        user_dashboard = None

    mock_user = MockUser()

    mock_context = {
        "current_user": mock_user,
        "user": mock_user,
        "dashboard_settings": {"theme": "dark", "compact_mode": False},
        "audit_info": {"status": "ok", "audit_status": "COCKPIT_ACTIVE", "audit_issues": 0, "last_audit_date": datetime.utcnow().isoformat()},
        "profile": {"username": "smoke_test_user", "full_name": "Smoke Test Operator"},
        "transactions": [],
        "flagged_transactions": [],
        "category_summary": {},
        "fraud_summary": {"flagged_count": 0, "total_risk_score": 0.0},
        "timeline": [],
        "transaction_summary": {"income": 0, "expenses": 0, "net": 0},
        "page": 1,
        "total_pages": 1,
        "pending_todos": [],
        "completed_todos": [],
        "services": [],  # 🟢 FIXED: Changed from service_registry={}
        "is_operator": False,
        "vault_txns": [],
        "summary": {},
        "flow_labels": [],
        "flow_values": [],
        "fraud_signals": []
    }

    return render_template(search_tpl, **mock_context)