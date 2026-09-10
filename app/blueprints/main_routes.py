# =============================================================================
# FILE: app/blueprints/main_routes.py
# DESCRIPTION: Public landing, auth, and subscriber dashboard routes.
# Bulletproof URL endpoints, safe telemetry, and explicit error handling.
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
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user
from jinja2 import TemplateNotFound
from sqlalchemy.exc import OperationalError
from werkzeug.security import check_password_hash

from app.auth_handlers import SystemOperator
from app.constants import OPERATOR_MODE_KEY
from app.extensions import csrf
from app.models.user import User
from app.utils.redis_utils import get_redis_client

main_bp = Blueprint("main", __name__, template_folder="../templates")


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def is_creator(user) -> bool:
    creator_email = os.getenv("CREATOR_EMAIL")
    creator_username = os.getenv("CREATOR_USERNAME")

    if not user:
        return False

    return (
        getattr(user, "email", None) == creator_email
        or getattr(user, "username", None) == creator_username
    )


def safe_get_redis_ttl(key: str) -> int:
    redis_client = (
        getattr(current_app, "redis_client", None) or get_redis_client()
    )
    if not redis_client:
        return 0
    try:
        ttl_val = redis_client.ttl(key)
        if isinstance(ttl_val, bytes):
            ttl_val = ttl_val.decode()
        val = int(ttl_val)
        return val if val > 0 else 0
    except Exception:
        current_app.logger.debug(
            "Redis TTL read failed for key '%s'", key, exc_info=True
        )
        return 0


def emit_narrative_trace(
    key_prefix: str, detail: str, status: str, value: str = ""
):
    redis_client = (
        getattr(current_app, "redis_client", None) or get_redis_client()
    )
    if not redis_client:
        current_app.logger.debug(
            "Redis unavailable — skipping telemetry for '%s'", key_prefix
        )
        return
    try:
        key = f"{key_prefix}:{detail}"
        redis_client.setex(key, 300, f"{status} | {value}")
    except Exception as exc:
        current_app.logger.debug(
            "Redis telemetry emit failed for %s: %s",
            key_prefix,
            exc,
            exc_info=True,
        )


# -------------------------------------------------------------------------
# Static / Favicon
# -------------------------------------------------------------------------
@main_bp.route("/favicon.ico")
def favicon():
    static_folder = current_app.static_folder or os.path.join(
        current_app.root_path, "static"
    )
    favicon_path = os.path.join(static_folder, "favicon.ico")
    if os.path.exists(favicon_path):
        return send_from_directory(static_folder, "favicon.ico")
    return ("", 204)


# -------------------------------------------------------------------------
# Public landing
# -------------------------------------------------------------------------
@main_bp.route("/", endpoint="home")
def home():
    redis_ttl = safe_get_redis_ttl("boot:render:home_view")

    auth_ok = False
    try:
        auth_ok = bool(getattr(current_user, "is_authenticated", False))
        if auth_ok:
            current_app.logger.info(
                "Authenticated visitor: %s",
                getattr(current_user, "id", "unknown"),
            )
    except Exception:
        current_app.logger.debug(
            "current_user probe failed; serving anonymously", exc_info=True
        )

    try:
        emit_narrative_trace(
            "boot:render", "home_view", "ok", "rendered:index.html"
        )
        return render_template(
            "index.html",
            app=current_app,
            redis_ttl=redis_ttl,
            auth_ok=auth_ok,
        )

    except TemplateNotFound:
        current_app.logger.error(
            "Template index.html not found", exc_info=True
        )
        emit_narrative_trace(
            "boot:render", "home_view", "template_not_found", ""
        )
        return (
            render_template_string(
                "<html><body><h1>Welcome (fallback, TemplateNotFound)</h1></body></html>"
            ),
            200,
        )

    except OperationalError as e:
        current_app.logger.exception(
            "DB operational error while rendering home: %s", e
        )
        emit_narrative_trace(
            "boot:render", "home_view", "db_error_fallback", str(e)
        )
        return (
            render_template_string(
                "<html><body><h1>Welcome (Database Error Fallback)</h1></body></html>"
            ),
            503,
        )

    except Exception as e:
        current_app.logger.exception("Generic error rendering home: %s", e)
        emit_narrative_trace(
            "boot:render", "home_view", "generic_error_fallback", str(e)
        )
        return (
            render_template_string(
                "<html><body><h1>Welcome (Internal Error Fallback)</h1></body></html>"
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
    return render_template("letters/dispute_form.html")


@main_bp.route("/upload-pdf", methods=["POST"])
def upload_pdf():
    if "file" not in request.files:
        return b"No file part", 400

    file = request.files["file"]
    if file.filename == "":
        return b"No file part", 400

    if not file.filename.lower().endswith(".pdf"):
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
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            emit_narrative_trace(
                "login", f"user_id:{user.id}", "ok", f"via:{source}"
            )
            flash(f"Welcome back, {user.email}!", "success")
            return redirect(url_for("sub_ui.dashboard"))
        else:
            flash("Invalid credentials.", "danger")
            emit_narrative_trace(
                "login", f"email:{email}", "error", "invalid_credentials"
            )
    except Exception:
        current_app.logger.exception("Login error for email=%s", email)
        flash("Login error. Please try again.", "danger")
    return render_template("auth/login.html", app=current_app)


@main_bp.route("/login", methods=["GET", "POST"], endpoint="subscriber_login")
def login():
    if request.method == "POST":
        return handle_login_post("login")
    return render_template("auth/login.html", app=current_app)


@main_bp.route(
    "/get_started", methods=["GET", "POST"], endpoint="subscriber_entry"
)
def get_started():
    if request.method == "POST":
        return handle_login_post("get_started")
    return render_template("auth/login.html", app=current_app)


@main_bp.route("/register_subscriber", methods=["GET", "POST"])
def register_subscriber_redirect():
    return redirect(url_for("auth.register_subscriber"), code=302)


@main_bp.route("/logout", endpoint="logout")
@login_required
def logout_alias():
    return redirect(url_for("auth.logout"))


# -------------------------------------------------------------------------
# Subscriber dashboards
# -------------------------------------------------------------------------
@main_bp.route("/welcome_back")
@login_required
def welcome_back():
    user_email = getattr(current_user, "email", "")
    ttl = safe_get_redis_ttl(f"subscriber_registered:{user_email}")
    ttl_badge = "active" if ttl > 0 else "expired"

    return render_template(
        "welcome_back.html",
        bank_name=getattr(current_user, "bank_name", "Default Bank"),
        routing_number=getattr(current_user, "routing_number", "000000000"),
        account_ending=getattr(current_user, "account_ending", "0000"),
        ttl=ttl,
        ttl_badge=ttl_badge,
    )


@main_bp.route("/subscriber/dashboard", endpoint="subscriber_dashboard")
@login_required
def subscriber_dashboard():
    return redirect(url_for("sub_ui.dashboard"))


@main_bp.route("/dashboard", endpoint="dashboard")
@login_required
def dashboard_redirect():
    return redirect(url_for("sub_ui.dashboard"))


# -------------------------------------------------------------------------
# Special entry / ignition
# -------------------------------------------------------------------------
@main_bp.route("/terence_entry")
def terence_entry():
    return render_template("terence_entry.html", app=current_app)


@main_bp.route("/ignite-cortex", methods=["GET", "POST"])
@csrf.exempt
def ignite_cortex():
    if request.method == "GET":
        # Serves entry page or requires explicit authentication
        return redirect(url_for("main.terence_entry"))

    if current_user.is_authenticated and is_creator(current_user):
        session[OPERATOR_MODE_KEY] = True
        flash("Creator ignition successful.", "success")
        return redirect(url_for("sub_ui.sub_index"))

    passcode = request.form.get("passcode", "").strip()
    expected = os.getenv("ROOT_IGNITION_CODE")

    if not expected or passcode != expected:
        flash("Invalid ignition code.", "danger")
        return redirect(url_for("main.terence_entry"))

    creator_email = os.getenv("CREATOR_EMAIL") or "terence@cortex.prime"
    user = User.query.filter_by(email=creator_email).first()

    if not user:
        current_app.logger.error(
            "Ignition aborted: Creator user record for %s missing from database.",
            creator_email,
        )
        return (
            "Critical Error: Creator user profile not found in database.",
            500,
        )

    login_user(SystemOperator("TERENCE_CORTEX_PRIME"))

    session[OPERATOR_MODE_KEY] = True
    session["user_email"] = creator_email
    session["username"] = os.getenv("CREATOR_USERNAME") or "OPERATOR_ADMIN"
    session["is_creator"] = True
    session["role"] = "subscriber"

    flash("Cortex ignition successful.", "success")
    return redirect(url_for("sub_ui.sub_index"))
