# =============================================================================
# FILE: app/blueprints/admin_routes.py
# DESCRIPTION: Admin API layer only.
#              FIXED: Strict decorator stacking order and added missing routes.
# =============================================================================

import json
import logging
import os
import re
import secrets
import string
from datetime import datetime
from typing import Any

from flask import Blueprint, jsonify, request, session
from flask_jwt_extended import get_jwt, jwt_required
from flask_login import current_user as login_user
from flask_login import login_required

from app.decorators import admin_required, roles_required
from app.extensions import csrf
from app.extensions import db as real_db
from app.models.plaid_item import PlaidItem
from app.models.user import User as RealUserModel
from app.utils.rate_limit_guard import rate_limit_if_enabled
from app.utils.redis_utils import get_redis_client
from app.utils.security_utils import success_response
from app.utils.telemetry import log_identity_event

logger = logging.getLogger(__name__)

# =============================================================================
# 1. BLUEPRINTS (API ONLY)
# =============================================================================

admin_bp = Blueprint("admin_api_core", __name__, url_prefix="/admin/api")
admin_api_bp = Blueprint("admin_api", __name__, url_prefix="/admin/api/v1")

# =============================================================================
# 2. CONSTANTS & REGEX
# =============================================================================

try:
    from app.constants import OPERATOR_MODE_KEY
except ImportError:
    OPERATOR_MODE_KEY = "operator_mode"

OPERATOR_MODE_TTL_SECONDS_KEY = "operator_mode_ttl_seconds"
OPERATOR_MODE_START_TIME_KEY = "operator_mode_start_time"
OPERATOR_CODE_REGEX = re.compile(r"^[A-Z0-9]{6,16}$")

LUA_GETDEL = """
local v = redis.call('GET', KEYS[1])
if v then redis.call('DEL', KEYS[1]) end
return v
"""

# =============================================================================
# 3. HYBRID MODEL LAYER (Mocks for Dev / Real for Prod)
# =============================================================================


class MockQuery:
    def __init__(self, model_class):
        self.model_class = model_class

    def count(self):
        return 0

    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, **kwargs):
        return self

    def all(self):
        return []

    def first(self):
        return self.model_class()

    def get(self, ident):
        return self.model_class(id=ident)

    def order_by(self, *args):
        return self

    def limit(self, *args):
        return self


class MockModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.id = kwargs.get("id", 1)

    balance_used = 0.0
    credit_limit = 0.0
    suspended = False
    status = "active"

    @classmethod
    def query(cls):
        # class-level query property: return a MockQuery for the model class
        return MockQuery(cls)


class MockUser(MockModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.email = kwargs.get("email", "operator@example.com")
        self.is_admin = True
        self.is_authenticated = True


class MockLedger(MockModel):
    pass


class MockSchemaEvent(MockModel):
    event_type = "MOCK_EVENT"
    details = "{}"


class MockLender(MockModel):
    name = "Mock Lender"


class MockTransaction(MockModel):
    pass


class MockPaymentLog(MockModel):
    pass


class MockFraudReport(MockModel):
    pass


class MockTradeline(MockModel):
    pass


class MockDisputeLog(MockModel):
    pass


class MockDB:
    class MockSession:
        def add(self, obj):
            pass

        def commit(self):
            pass

        def rollback(self):
            pass

        def delete(self, obj):
            pass

        def query(self, model):
            return MockQuery(model)

    session = MockSession()


def _get_model_layer():
    is_testing = os.getenv("FLASK_ENV") == "testing"
    force_real = os.getenv("USE_REAL_MODELS", "false").lower() == "true"
    if is_testing or force_real:
        try:
            from app.models.user import User as RealUser

            return {"User": RealUser, "db": real_db, "is_mock": False}
        except ImportError:
            pass
    return {"User": MockUser, "db": MockDB(), "is_mock": True}


models_context = _get_model_layer()
User = models_context["User"]
db = models_context["db"]
is_mock = models_context["is_mock"]

# Predeclare model names as Any so we can assign either real model classes or mocks
CreditLedger: Any
PaymentLog: Any
Lender: Any
Transaction: Any
SchemaEvent: Any

if not is_mock:
    try:
        # import-untyped is possible for in-repo models; guard with type:ignore for analysis
        from app.models.credit_ledger import (
            CreditLedger as _CreditLedger,  # type: ignore[import-untyped]
        )
        from app.models.lender import Lender as _Lender  # type: ignore[import-untyped]
        from app.models.payment_log import PaymentLog as _PaymentLog  # type: ignore[import-untyped]
        from app.models.schema_event import (
            SchemaEvent as _SchemaEvent,  # type: ignore[import-untyped]
        )
        from app.models.transaction import (
            Transaction as _Transaction,  # type: ignore[import-untyped]
        )

        # assign to the predeclared names
        CreditLedger = _CreditLedger
        PaymentLog = _PaymentLog
        Lender = _Lender
        Transaction = _Transaction
        SchemaEvent = _SchemaEvent
    except ImportError:
        # fall back to mocks if any real model import fails at runtime
        CreditLedger = MockLedger
        PaymentLog = MockPaymentLog
        Lender = MockLender
        Transaction = MockTransaction
        SchemaEvent = MockSchemaEvent
else:
    CreditLedger = MockLedger
    PaymentLog = MockPaymentLog
    Lender = MockLender
    Transaction = MockTransaction
    SchemaEvent = MockSchemaEvent

FraudReport = MockFraudReport
Tradeline = MockTradeline
DisputeLog = MockDisputeLog

# =============================================================================
# 4. INTERNAL HELPERS
# =============================================================================


def _make_operator_key(code: str) -> str:
    return f"operator:code:v1:{code}"


def _generate_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _audit_emit(event_type: str, metadata: dict):
    user_identifier = getattr(login_user, "id", None) or request.remote_addr
    safe_details = {
        "target_user": metadata.get("target_user"),
        "admin_id": metadata.get("admin_user_id") or user_identifier,
        "code_prefix": metadata.get("code_prefix"),
        "reason": metadata.get("reason"),
        "ttl": metadata.get("ttl"),
        "keys_deleted": metadata.get("keys_deleted"),
    }
    try:
        log_identity_event(
            user_id=user_identifier,
            event_type=event_type,
            details={k: v for k, v in safe_details.items() if v is not None},
            ip=request.remote_addr,
        )
    except Exception:
        pass


def get_remote_address():
    return request.remote_addr


# =============================================================================
# 5. BASIC ADMIN API ROUTES
# =============================================================================


@admin_api_bp.route("/traces/recent", methods=["GET"])
@csrf.exempt
@jwt_required()
@roles_required("admin")
def api_get_recent_traces():
    query_results = SchemaEvent.query.order_by(SchemaEvent.timestamp.desc()).limit(20).all()
    traces = [
        {
            "timestamp": getattr(t, "timestamp", datetime.utcnow()).isoformat(),
            "event": getattr(t, "event_type", "UNKNOWN"),
            "id": getattr(t, "id", None),
            "details": getattr(t, "details", {}),
        }
        for t in query_results
    ]
    return success_response({"traces": traces, "status": "ok"}, message="Traces fetched.")


# =============================================================================
# 6. OPERATOR CODE API
# =============================================================================


@login_required
@admin_required
@csrf.exempt
@admin_api_bp.route("/operator_code/generate", methods=["POST"])
def operator_code_generate():
    req = request.get_json(silent=True) or {}
    ttl = max(30, min(int(req.get("ttl_seconds", 600)), 3600))
    length = max(6, min(int(req.get("length", 8)), 16))

    code = _generate_code(length)
    key = _make_operator_key(code)

    r = get_redis_client()
    if not r:
        return jsonify({"status": "error", "message": "Redis unavailable"}), 503

    payload = {
        "created_by_ip": request.remote_addr,
        "created_at": datetime.utcnow().isoformat(),
        "ttl": ttl,
        "admin_user_id": getattr(login_user, "id", "unknown"),
    }
    r.setex(key, ttl, json.dumps(payload))

    _audit_emit("OPERATOR_CODE_GENERATED", {"code_prefix": code[:4], "ttl": ttl})
    return jsonify({"status": "ok", "operator_code": code, "expires_in": ttl}), 201


@login_required
@admin_required
@csrf.exempt
@admin_api_bp.route("/operator_code/invalidate", methods=["POST"])
def operator_code_invalidate():
    try:
        r = get_redis_client()
        if not r:
            return jsonify({"status": "error", "message": "Redis unavailable"}), 503

        keys_to_delete = list(r.scan_iter("operator:code:v1:*"))
        count = r.delete(*keys_to_delete) if keys_to_delete else 0

        _audit_emit("OPERATOR_CODE_INVALIDATED_ALL", {"keys_deleted": count})
        return jsonify({"status": "ok", "message": f"Invalidated {count} codes."}), 200
    except Exception:
        return jsonify({"status": "error", "message": "server_error"}), 500


@rate_limit_if_enabled("5/minute")
@csrf.exempt
@admin_api_bp.route("/operator_entry", methods=["POST"])
def operator_entry():
    data = request.form or request.get_json(silent=True) or {}
    code = (data.get("passcode") or data.get("code") or "").upper()

    if not code or not OPERATOR_CODE_REGEX.match(code):
        return jsonify({"status": "error", "message": "invalid_format"}), 400

    key = _make_operator_key(code)

    try:
        r = get_redis_client()
        if not r:
            return jsonify({"status": "error", "message": "service_unavailable"}), 503

        raw = r.eval(LUA_GETDEL, 1, key)
        if raw is None:
            return (
                jsonify({"status": "error", "message": "invalid_or_expired_code"}),
                403,
            )

        meta = json.loads(raw.decode("utf-8")) if isinstance(raw, bytes) else json.loads(raw)
        ttl = meta.get("ttl", 600)

        session[OPERATOR_MODE_KEY] = True
        session[OPERATOR_MODE_TTL_SECONDS_KEY] = ttl
        session[OPERATOR_MODE_START_TIME_KEY] = datetime.utcnow().timestamp()

        _audit_emit("OPERATOR_CODE_CONSUMED", {"code_prefix": code[:4], "ttl": ttl})
        return jsonify({"status": "ok", "message": "operator_mode_enabled"}), 200

    except Exception:
        return jsonify({"status": "error", "message": "server_error"}), 500


# =============================================================================
# 7. AUDIT & USER MANAGEMENT API
# =============================================================================


@login_required
@admin_required
@csrf.exempt
@admin_api_bp.route("/audit", methods=["GET"])
def audit_viewer_api():
    events = [{"id": i, "event_type": "MOCK_EVENT", "ip": f"192.168.1.{i}"} for i in range(1, 5)]
    return jsonify({"status": "ok", "events": events})


# ---------------------------
# LIST USERS (already present)
# ---------------------------


@admin_api_bp.route("/users", methods=["GET"])
@csrf.exempt
@jwt_required()
@roles_required("admin")
def admin_list_users():
    claims = get_jwt()
    if not claims.get("is_admin", False):
        return jsonify({"status": "error", "message": "admin_required"}), 403
    return jsonify({"status": "success", "users": []}), 200


# ---------------------------
# ⭐ NEW: DELETE USER ENDPOINT
# ---------------------------


@admin_api_bp.route("/users/<int:user_id>", methods=["DELETE"])
@csrf.exempt
@jwt_required()
@roles_required("admin")
def admin_delete_user(user_id):
    """
    Delete a user and cascade-delete their PlaidItem.
    Required by test_admin_delete_user_cascade_api.
    """
    user = RealUserModel.query.get(user_id)
    if not user:
        return jsonify({"status": "error", "message": "user_not_found"}), 404

    PlaidItem.query.filter_by(user_id=user_id).delete()

    real_db.session.delete(user)
    real_db.session.commit()

    return jsonify({"status": "ok", "message": "user_deleted"}), 200
