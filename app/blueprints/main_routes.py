# =============================================================================
# FILE: app/blueprints/main_routes.py
# DESCRIPTION: Public landing, auth, subscriber dashboard, and ignition routes.
#              Bulletproof URL endpoints, safe telemetry, and explicit errors.
# =============================================================================

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
    url_for,
)
from flask_login import current_user, login_required, login_user
from jinja2 import TemplateNotFound
from sqlalchemy.exc import OperationalError
from werkzeug.security import check_password_hash

from app.decorators.access import has_permission
from app.extensions import csrf
from app.models.user import User
from app.services.ignition_service import enable_operator_mode
from app.utils.redis_utils import get_redis_client


main_bp = Blueprint(
    "main",
    __name__,
    template_folder="../templates",
)


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def is_creator(user) -> bool:
    """Return whether the user matches a configured creator identity."""
    if not user:
        return False

    creator_email = os.getenv("CREATOR_EMAIL")
    creator_username = os.getenv("CREATOR_USERNAME")

    return any(
        (
            creator_email
            and getattr(user, "email", None) == creator_email,
            creator_username
            and getattr(user, "username", None) == creator_username,
            getattr(user, "role", None) == "creator",
        )
    )


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


def _render_login() :
    return render_template(
        "auth/login.html",
        app=current_app,
    )


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
    favicon_path = os.path.join(static_folder, "favicon.ico")

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
                "<html><body>"
                "<h1>Welcome (fallback, TemplateNotFound)</h1>"
                "</body></html>"
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
                "<html><body>"
                "<h1>Welcome (Database Error Fallback)</h1>"
                "</body></html>"
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
                "<html><body>"
                "<h1>Welcome (Internal Error Fallback)</h1>"
                "</body></html>"
            ),
            500,
        )


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
@main_bp.route("/terence_entry")
def terence_entry():
    return render_template(
        "terence_entry.html",
        app=current_app,
    )


@main_bp.route(
    "/ignite-cortex",
    methods=["GET", "POST"],
)
@csrf.exempt
def ignite_cortex():
    if request.method == "GET":
        return redirect(
            url_for("main.terence_entry"),
        )

    if getattr(current_user, "is_authenticated", False):
        has_operator_access = (
            is_creator(current_user)
            or has_permission(
                current_user,
                "read_operational_data",
            )
        )

        if has_operator_access:
            try:
                enable_operator_mode(current_user)

            except Exception:
                current_app.logger.exception(
                    "Authenticated operator ignition failed for user_id=%s",
                    getattr(current_user, "id", "unknown"),
                )
                flash(
                    "Unable to enable operator mode.",
                    "danger",
                )
                return redirect(
                    url_for("main.terence_entry"),
                )

            flash(
                "Creator ignition successful.",
                "success",
            )

            return redirect(
                url_for("sub_ui.sub_index"),
            )

    passcode = request.form.get(
        "passcode",
        "",
    ).strip()
    expected_passcode = os.getenv("ROOT_IGNITION_CODE")

    if not expected_passcode or passcode != expected_passcode:
        flash(
            "Invalid ignition code.",
            "danger",
        )
        return redirect(
            url_for("main.terence_entry"),
        )

    creator_email = (
        os.getenv("CREATOR_EMAIL")
        or "terence@cortex.prime"
    )

    try:
        user = User.query.filter_by(
            email=creator_email,
        ).first()

    except Exception:
        current_app.logger.exception(
            "Ignition user lookup failed for %s",
            creator_email,
        )
        return (
            "Critical Error: Unable to load creator user profile.",
            503,
        )

    if not user:
        current_app.logger.error(
            "Ignition aborted: creator user record for %s "
            "is missing from the database.",
            creator_email,
        )
        return (
            "Critical Error: Creator user profile not found in database.",
            500,
        )

    try:
        login_user(user)
        enable_operator_mode(user)

    except Exception:
        current_app.logger.exception(
            "Passcode ignition failed for user_id=%s",
            getattr(user, "id", "unknown"),
        )
        flash(
            "Unable to enable operator mode.",
            "danger",
        )
        return redirect(
            url_for("main.terence_entry"),
        )

    flash(
        "Cortex ignition successful.",
        "success",
    )

    return redirect(
        url_for("sub_ui.sub_index"),
    )