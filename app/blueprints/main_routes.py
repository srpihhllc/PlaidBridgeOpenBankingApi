# =============================================================================
# FILE: app/blueprints/main_routes.py
# DESCRIPTION: Public landing, auth, subscriber dashboard, and ignition routes.
#              Bulletproof URL endpoints, safe telemetry, and explicit errors.
# =============================================================================

import hmac
import os

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    render_template_string,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user
from jinja2 import TemplateNotFound
from sqlalchemy.exc import OperationalError
from werkzeug.security import check_password_hash

from app.extensions import csrf
from app.models.user import User
from app.security.founder import is_founder
from app.services.ignition_service import enable_operator_mode
from app.utils.redis_utils import get_redis_client


main_bp = Blueprint(
    "main",
    __name__,
    template_folder="../templates",
)


# -------------------------------------------------------------------------
# Direct Fallback / Redirect Route for Un-Prefixed Tile Calls
# -------------------------------------------------------------------------

@main_bp.route("/tiles/<path:tile_path>", methods=["GET", "POST"])
def redirect_unprefixed_tiles(tile_path: str):
    """
    Redirects direct calls to /tiles/... to the admin tiles namespace /admin/tiles/...
    """
    admin_tile_url = f"/admin/tiles/{tile_path}"
    if request.query_string:
        admin_tile_url += f"?{request.query_string.decode('utf-8')}"
    return redirect(admin_tile_url, code=307)


# -------------------------------------------------------------------------
# Ignition session configuration
# -------------------------------------------------------------------------

IGNITION_SESSION_KEY = "finbrain_ignition_authenticated"
IGNITION_STAGE_KEY = "finbrain_ignition_stage"
IGNITION_STAGE_VALUE = "operator_authenticated"
IGNITION_USER_ID_KEY = "ignition_user_id"
IGNITION_NEXT_ENDPOINT = "sub_ui.sub_index"

IGNITION_EXEMPT_ENDPOINTS = frozenset(
    {
        "subscriber.update_profile",
    }
)


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def is_creator(user) -> bool:
    """
    Backward-compatible founder alias.
    """
    return is_founder(user)


def _get_redis_client():
    """Return the configured Redis client when available."""
    return (
        getattr(current_app, "redis_client", None)
        or get_redis_client()
    )


def safe_get_redis_ttl(key: str) -> int:
    """Return a positive Redis TTL, or zero when unavailable."""
    redis_client = _get_redis_client()

    if not redis_client:
        return 0

    try:
        ttl_value = redis_client.ttl(key)

        if isinstance(ttl_value, bytes):
            ttl_value = ttl_value.decode(
                "utf-8",
                errors="replace",
            )

        ttl = int(ttl_value)
        return ttl if ttl > 0 else 0

    except Exception:
        current_app.logger.debug(
            "Redis TTL read failed for key %r",
            key,
            exc_info=True,
        )
        return 0


def emit_narrative_trace(
    key_prefix: str,
    detail: str,
    status: str,
    value: str = "",
) -> None:
    """Emit short-lived diagnostic telemetry without breaking requests."""
    redis_client = _get_redis_client()

    if not redis_client:
        current_app.logger.debug(
            "Redis unavailable; skipping telemetry for %r",
            key_prefix,
        )
        return

    try:
        redis_client.setex(
            f"{key_prefix}:{detail}",
            300,
            f"{status} | {value}",
        )

    except Exception as exc:
        current_app.logger.debug(
            "Redis telemetry emit failed for %s: %s",
            key_prefix,
            exc,
            exc_info=True,
        )


def _render_login():
    return render_template(
        "auth/login.html",
        app=current_app,
    )


def mark_ignition_complete(user) -> None:
    """Store successful ignition state in the signed Flask session."""
    session.permanent = True
    session[IGNITION_SESSION_KEY] = True
    session[IGNITION_STAGE_KEY] = IGNITION_STAGE_VALUE
    session[IGNITION_USER_ID_KEY] = getattr(user, "id", None)

    current_app.logger.info(
        "Ignition session established for user_id=%s",
        getattr(user, "id", "unknown"),
    )


def ignition_is_complete() -> bool:
    """Return whether the current session completed ignition."""
    current_user_id = getattr(current_user, "id", None)
    ignition_user_id = session.get(IGNITION_USER_ID_KEY)

    return (
        getattr(current_user, "is_authenticated", False)
        and session.get(IGNITION_SESSION_KEY) is True
        and session.get(IGNITION_STAGE_KEY) == IGNITION_STAGE_VALUE
        and ignition_user_id is not None
        and str(ignition_user_id) == str(current_user_id)
    )


def clear_ignition_state() -> None:
    """Remove ignition state from the current session."""
    session.pop(IGNITION_SESSION_KEY, None)
    session.pop(IGNITION_STAGE_KEY, None)
    session.pop(IGNITION_USER_ID_KEY, None)


# -------------------------------------------------------------------------
# Static / Favicon
# -------------------------------------------------------------------------

@main_bp.route("/favicon.ico")
def favicon():
    """Serve favicon.ico when present."""
    static_folder = current_app.static_folder or os.path.join(
        current_app.root_path,
        "static",
    )

    favicon_path = os.path.join(
        static_folder,
        "favicon.ico",
    )

    if os.path.isfile(favicon_path):
        return send_from_directory(
            static_folder,
            "favicon.ico",
        )

    return "", 204


# -------------------------------------------------------------------------
# Public landing
# -------------------------------------------------------------------------

@main_bp.route("/", endpoint="home")
def home():
    redis_ttl = safe_get_redis_ttl("boot:render:home_view")

    try:
        auth_ok = bool(
            getattr(current_user, "is_authenticated", False)
        )

        if auth_ok:
            current_app.logger.info(
                "Authenticated visitor: %s",
                getattr(current_user, "id", "unknown"),
            )

    except Exception:
        auth_ok = False
        current_app.logger.debug(
            "current_user probe failed; serving anonymously",
            exc_info=True,
        )

    try:
        emit_narrative_trace(
            "boot:render",
            "home_view",
            "ok",
            "rendered:index.html",
        )

        return render_template(
            "index.html",
            app=current_app,
            redis_ttl=redis_ttl,
            auth_ok=auth_ok,
        )

    except TemplateNotFound:
        current_app.logger.error(
            "Template index.html not found",
            exc_info=True,
        )

        emit_narrative_trace(
            "boot:render",
            "home_view",
            "template_not_found",
        )

        return (
            render_template_string(
                "<h1>Welcome (fallback, TemplateNotFound)</h1>"
            ),
            200,
        )

    except OperationalError as exc:
        current_app.logger.exception(
            "DB operational error while rendering home: %s",
            exc,
        )

        emit_narrative_trace(
            "boot:render",
            "home_view",
            "db_error_fallback",
            str(exc),
        )

        return (
            render_template_string(
                "<h1>Welcome (Database Error Fallback)</h1>"
            ),
            503,
        )

    except Exception as exc:
        current_app.logger.exception(
            "Generic error rendering home: %s",
            exc,
        )

        emit_narrative_trace(
            "boot:render",
            "home_view",
            "generic_error_fallback",
            str(exc),
        )

        return (
            render_template_string(
                "<h1>Welcome (Internal Error Fallback)</h1>"
            ),
            500,
        )


# -------------------------------------------------------------------------
# Dispute form and PDF upload
# -------------------------------------------------------------------------

@main_bp.route("/dispute-form", methods=["GET"])
def dispute_form():
    emit_narrative_trace(
        "boot:render",
        "dispute_form",
        "ok",
        "rendered:letters/dispute_form.html",
    )

    return render_template(
        "letters/dispute_form.html",
    )


@main_bp.route("/upload-pdf", methods=["POST"])
def upload_pdf():
    uploaded_file = request.files.get("file")

    if uploaded_file is None:
        return b"No file part", 400

    if not uploaded_file.filename:
        return b"No file part", 400

    if not uploaded_file.filename.lower().endswith(".pdf"):
        return b"Invalid file format", 400

    return b"OK", 200


# -------------------------------------------------------------------------
# Auth flows
# -------------------------------------------------------------------------

def handle_login_post(source: str):
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    try:
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(
            user.password_hash,
            password,
        ):
            login_user(user)

            emit_narrative_trace(
                "login",
                f"user_id:{user.id}",
                "ok",
                f"via:{source}",
            )

            flash(
                f"Welcome back, {user.email}!",
                "success",
            )

            return redirect(
                url_for("sub_ui.dashboard"),
            )

        flash(
            "Invalid credentials.",
            "danger",
        )

        emit_narrative_trace(
            "login",
            f"email:{email}",
            "error",
            "invalid_credentials",
        )

    except Exception:
        current_app.logger.exception(
            "Login error for email=%s",
            email,
        )

        flash(
            "Login error. Please try again.",
            "danger",
        )

    return _render_login()


@main_bp.route(
    "/login",
    methods=["GET", "POST"],
    endpoint="subscriber_login",
)
def login():
    if request.method == "POST":
        return handle_login_post("login")

    return _render_login()


@main_bp.route(
    "/get_started",
    methods=["GET", "POST"],
    endpoint="subscriber_entry",
)
def get_started():
    if request.method == "POST":
        return handle_login_post("get_started")

    return _render_login()


@main_bp.route(
    "/register_subscriber",
    methods=["GET", "POST"],
)
def register_subscriber_redirect():
    return redirect(
        url_for("auth.register_subscriber"),
        code=302,
    )


@main_bp.route(
    "/logout",
    endpoint="logout",
)
@login_required
def logout_alias():
    return redirect(
        url_for("auth.logout"),
    )


# -------------------------------------------------------------------------
# Subscriber dashboards
# -------------------------------------------------------------------------

@main_bp.route("/welcome_back")
@login_required
def welcome_back():
    user_email = getattr(current_user, "email", "")

    ttl = safe_get_redis_ttl(
        f"subscriber_registered:{user_email}",
    )

    return render_template(
        "welcome_back.html",
        bank_name=getattr(
            current_user,
            "bank_name",
            "Default Bank",
        ),
        routing_number=getattr(
            current_user,
            "routing_number",
            "000000000",
        ),
        account_ending=getattr(
            current_user,
            "account_ending",
            "0000",
        ),
        ttl=ttl,
        ttl_badge="active" if ttl > 0 else "expired",
    )


@main_bp.route(
    "/subscriber/dashboard",
    endpoint="subscriber_dashboard",
)
@login_required
def subscriber_dashboard():
    return redirect(
        url_for("sub_ui.dashboard"),
    )


@main_bp.route(
    "/dashboard",
    endpoint="dashboard",
)
@login_required
def dashboard_redirect():
    return redirect(
        url_for("sub_ui.dashboard"),
    )

# -------------------------------------------------------------------------
# Special entry / ignition
# -------------------------------------------------------------------------

@main_bp.route("/terence_entry", methods=["GET"])
def terence_entry():
    if ignition_is_complete():
        current_app.logger.info(
            "Ignition already complete; continuing to %s",
            IGNITION_NEXT_ENDPOINT,
        )
        return redirect(url_for(IGNITION_NEXT_ENDPOINT))

    return render_template("terence_entry.html", app=current_app)


@main_bp.route(
    "/ignite-cortex",
    methods=["GET", "POST"],
    endpoint="ignite_cortex",
)
@csrf.exempt
def ignite_cortex():
    """
    Validate ROOT_IGNITION_CODE, log in the creator user, enable operator
    mode, persist ignition state, and redirect.
    """
    if request.method == "GET":
        return redirect(url_for("main.terence_entry"))

    passcode = request.form.get("passcode", "").strip()
    expected_passcode = os.getenv("ROOT_IGNITION_CODE", "").strip()

    current_app.logger.info(
        "Ignition POST received: passcode_present=%s, "
        "entered_length=%d, configured=%s, configured_length=%d",
        bool(passcode),
        len(passcode),
        bool(expected_passcode),
        len(expected_passcode),
    )

    if not expected_passcode:
        current_app.logger.error("ROOT_IGNITION_CODE is not configured")
        flash("Ignition is temporarily unavailable.", "danger")
        return redirect(url_for("main.terence_entry"))

    if not hmac.compare_digest(passcode, expected_passcode):
        current_app.logger.warning("Ignition rejected: passphrase mismatch")
        flash("Invalid ignition code.", "danger")
        return redirect(url_for("main.terence_entry"))

    current_app.logger.info("Ignition passphrase accepted")

    creator_email = (
        os.getenv("CREATOR_EMAIL", "terence@cortex.prime")
        .strip()
        .lower()
    )

    try:
        user = User.query.filter_by(email=creator_email).first()
    except Exception:
        current_app.logger.exception("Ignition user lookup failed")
        flash("Unable to load the operator profile.", "danger")
        return redirect(url_for("main.terence_entry"))

    if user is None:
        current_app.logger.error("Ignition creator user was not found")
        flash("Operator profile is not configured.", "danger")
        return redirect(url_for("main.terence_entry"))

    user_id = getattr(user, "id", "unknown")

    try:
        login_user(user, remember=True)

        current_app.logger.info(
            "Ignition login succeeded for user_id=%s",
            user_id,
        )

        enable_operator_mode(actor=user)

        current_app.logger.info(
            "Operator mode enabled for user_id=%s",
            user_id,
        )

        mark_ignition_complete(user)

    except Exception:
        current_app.logger.exception(
            "Passcode ignition failed for user_id=%s",
            user_id,
        )
        clear_ignition_state()
        flash("Unable to enable operator mode.", "danger")
        return redirect(url_for("main.terence_entry"))

    flash("Cortex ignition successful.", "success")

    target_url = url_for(IGNITION_NEXT_ENDPOINT)
    current_app.logger.info(
        "Ignition complete; redirecting to %s",
        target_url,
    )
    return redirect(target_url)


@main_bp.before_app_request
def enforce_ignition_sequence():
    if not request.path.startswith("/sub"):
        return None

    if not getattr(current_user, "is_authenticated", False):
        return None

    if request.endpoint in IGNITION_EXEMPT_ENDPOINTS:
        return None

    if ignition_is_complete():
        return None

    current_app.logger.warning(
        "Authenticated user reached subscriber area without "
        "ignition state: endpoint=%s path=%s method=%s",
        request.endpoint,
        request.path,
        request.method,
    )
    return redirect(url_for("main.terence_entry"))