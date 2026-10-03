# =============================================================================
# FILE: app/blueprints/admin_routes.py
# DESCRIPTION: Admin API layer only.
#              FIXED: Removed duplicate blueprint decorators causing route collisions.
# =============================================================================

import json
import logging
import os
import re
import secrets
import string
from datetime import datetime, timezone
from typing import Any

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    request,
    session,
    url_for,
)
from flask_jwt_extended import get_jwt, jwt_required
from flask_login import current_user, login_required

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
# 1. BLUEPRINTS (API ONLY - NO ADMIN_API_CORE)
# =============================================================================

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

CreditLedger: Any
PaymentLog: Any
Lender: Any
Transaction: Any
SchemaEvent: Any

if not is_mock:
    try:
        from app.models.credit_ledger import CreditLedger as _CreditLedger  # type: ignore[import-untyped]
        from app.models.lender import Lender as _Lender  # type: ignore[import-untyped]
        from app.models.payment_log import PaymentLog as _PaymentLog  # type: ignore[import-untyped]
        from app.models.schema_event import SchemaEvent as _SchemaEvent  # type: ignore[import-untyped]
        from app.models.transaction import Transaction as _Transaction  # type: ignore[import-untyped]

        CreditLedger = _CreditLedger
        PaymentLog = _PaymentLog
        Lender = _Lender
        Transaction = _Transaction
        SchemaEvent = _SchemaEvent
    except ImportError:
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
    user_identifier = (
        getattr(current_user, "id", 0) if current_user.is_authenticated else 0
    )

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
            event_type=event_type,
            user_id=user_identifier,
            details={k: v for k, v in safe_details.items() if v is not None},
            ip=request.remote_addr,
        )
    except Exception as e:
        logger.warning(f"Audit emit failed: {e}")


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
    query_results = (
        SchemaEvent.query.order_by(SchemaEvent.timestamp.desc())
        .limit(20)
        .all()
    )
    traces = [
        {
            "timestamp": getattr(
                t, "timestamp", datetime.now(timezone.utc)
            ).isoformat(),
            "event": getattr(t, "event_type", "UNKNOWN"),
            "id": getattr(t, "id", None),
            "details": getattr(t, "details", {}),
        }
        for t in query_results
    ]
    return success_response(
        {"traces": traces, "status": "ok"}, message="Traces fetched."
    )


# =============================================================================
# 6. OPERATOR CODE API
# =============================================================================


@admin_api_bp.route("/operator_code/generate", methods=["POST"])
@csrf.exempt
@login_required
@admin_required
def operator_code_generate():
    req = request.get_json(silent=True) or {}
    ttl = max(30, min(int(req.get("ttl_seconds", 600)), 3600))
    length = max(6, min(int(req.get("length", 8)), 16))

    code = _generate_code(length)
    key = _make_operator_key(code)

    r = get_redis_client()
    if not r:
        return jsonify(
            {"status": "error", "message": "Redis unavailable"}
        ), 503

    payload = {
        "created_by_ip": request.remote_addr,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ttl": ttl,
        "admin_user_id": getattr(current_user, "id", "unknown"),
    }
    r.setex(key, ttl, json.dumps(payload))

    _audit_emit(
        "OPERATOR_CODE_GENERATED", {"code_prefix": code[:4], "ttl": ttl}
    )
    return jsonify(
        {"status": "ok", "operator_code": code, "expires_in": ttl}
    ), 201


@admin_api_bp.route("/operator_code/invalidate", methods=["POST"])
@csrf.exempt
@login_required
@admin_required
def operator_code_invalidate():