# =============================================================================
# FILE: app/routes/oauth_routes.py
# DESCRIPTION: Google OAuth callback routes with cockpit-grade telemetry.
# =============================================================================

import uuid

import requests
from flask import Blueprint, current_app, redirect, request, session, url_for

from app.extensions import db
from app.models import User
from app.models.trace_events import TraceEvent
from app.telemetry.ttl_emit import ttl_emit  # Import the TTL emitter

# NOTE: The imports for google.auth are intentionally removed from the top-level.
# This prevents Alembic from trying to import them when loading the app's metadata,
# which avoids a ModuleNotFoundError if they are not installed in the migration environment.

oauth_bp = Blueprint("oauth", __name__)


@oauth_bp.route("/callback/google")
def callback_google():
    """
    Handles the Google OAuth 2.0 callback.

    This function now includes cockpit-grade TTL telemetry to provide real-time
    visibility into the authentication flow, including successes and failures
    at each critical stage.
    """
    # Initialize a unique ID for this request to correlate all telemetry traces.
    request_uuid = str(uuid.uuid4())
    redis_client = getattr(current_app, "redis_client", None)

    # Lazy imports: These will only be executed when this route is called at runtime.
    import google.auth.transport.requests
    import google.oauth2.id_token

    auth_code = request.args.get("code")

    # ------------------
    # 1. Initial State Check & Telemetry
    # ------------------
    if not auth_code:
        # Emit telemetry for a missing auth code
        if redis_client:
            ttl_emit(
                key=f"ttl:flow:oauth:google:failure:{request_uuid}",
                msg="reason:no_code",
                r=redis_client,
                ttl=60,
            )
        return "Missing authorization code", 400

    # 🔑 Centralized config values
    client_id = current_app.config["GOOGLE_CLIENT_ID"]
    client_secret = current_app.config["GOOGLE_CLIENT_SECRET"]
    redirect_uri = current_app.config["GOOGLE_REDIRECT_URI"]

    # ------------------
    # 2. Exchange code for access token
    # ------------------
    try:
        # Emit telemetry for the start of the token exchange
        if redis_client:
            ttl_emit(
                key=f"ttl:flow:oauth:google:token_exchange:start:{request_uuid}",
                msg="status:attempt",
                r=redis_client,
                ttl=60,
            )

        token_res = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": auth_code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        token_res.raise_for_status()
        token_data = token_res.json()

        # Emit telemetry for a successful token exchange
        if redis_client:
            ttl_emit(
                key=f"ttl:flow:oauth:google:token_exchange:success:{request_uuid}",
                msg="status:ok",
                r=redis_client,
                ttl=60,
            )

    except Exception as e:
        # Emit telemetry for token exchange failure
        if redis_client:
            ttl_emit(
                key=f"ttl:flow:oauth:google:token_exchange:failure:{request_uuid}",
                msg=f"reason:{str(e)[:64]}",
                r=redis_client,
                ttl=60,
            )
        # Log to DB for historical audit
        db.session.add(
            TraceEvent(
                event_type="OAUTH_TOKEN_ERROR",
                ip=request.remote_addr,
                detail="Token exchange failed",
                meta=str(e)[:512],
            )
        )
        db.session.commit()
        return "OAuth exchange failed", 502

    if "access_token" not in token_data:
        # Emit telemetry for a missing access token
        if redis_client:
            ttl_emit(
                key=f"ttl:flow:oauth:google:token_exchange:failure:{request_uuid}",
                msg="reason:no_access_token",
                r=redis_client,
                ttl=60,
            )
        return "OAuth exchange failed", 401

    access_token = token_data["access_token"]

    # ------------------
    # 3. Optional: Validate ID token
    # ------------------
    id_token_str = token_data.get("id_token")
    if id_token_str:
        try:
            request_adapter = google.auth.transport.requests.Request()
            google.oauth2.id_token.verify_oauth2_token(id_token_str, request_adapter, client_id)
            # id_info contains 'sub', 'email', etc.
        except Exception as e:
            # Emit telemetry for ID token validation failure
            if redis_client:
                ttl_emit(
                    key=f"ttl:flow:oauth:google:id_token_validation:failure:{request_uuid}",
                    msg=f"reason:{str(e)[:64]}",
                    r=redis_client,
                    ttl=60,
                )
            return "Invalid ID token", 401

    # ------------------
    # 4. Fetch user profile from Google
    # ------------------
    try:
        profile_res = requests.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        profile_res.raise_for_status()
        profile_data = profile_res.json()
    except Exception as e:
        # Emit telemetry for profile fetch failure
        if redis_client:
            ttl_emit(
                key=f"ttl:flow:oauth:google:profile_fetch:failure:{request_uuid}",
                msg=f"reason:{str(e)[:64]}",
                r=redis_client,
                ttl=60,
            )
        # Log to DB for historical audit
        db.session.add(
            TraceEvent(
                event_type="OAUTH_PROFILE_ERROR",
                ip=request.remote_addr,
                detail="Profile fetch failed",
                meta=str(e)[:512],
            )
        )
        db.session.commit()
        return "Google profile fetch failed", 502

    email = profile_data.get("email")
    if not email:
        # Emit telemetry for missing email
        if redis_client:
            ttl_emit(
                key=f"ttl:flow:oauth:google:login:failure:{request_uuid}",
                msg="reason:no_email",
                r=redis_client,
                ttl=60,
            )
        return "Missing email in profile", 401

    # ------------------
    # 5. Authenticate or create user
    # ------------------
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email)
        db.session.add(user)
        db.session.commit()
        # Emit telemetry for a new user creation
        if redis_client:
            ttl_emit(
                key=f"ttl:flow:oauth:google:user:create:{request_uuid}",
                msg=f"user_id:{user.id}",
                r=redis_client,
                ttl=300,
            )

    # 6. Final success telemetry
    # Emit a long-lived TTL for successful login
    if redis_client:
        ttl_emit(
            key=f"ttl:flow:oauth:google:login:success:{request_uuid}",
            msg=f"user_id:{user.id}",
            r=redis_client,
            ttl=300,
        )

    # Log to DB for historical audit
    db.session.add(
        TraceEvent(
            event_type="OAUTH_LOGIN_SUCCESS",
            email=email,
            ip=request.remote_addr,
            detail="Google login callback successful",
            meta=str(profile_data)[:512],
        )
    )
    db.session.commit()

    # 7. Establish session
    session["user_id"] = user.id
    db.session.add(
        TraceEvent(
            event_type="SESSION_ESTABLISHED",
            email=email,
            ip=request.remote_addr,
            detail="Flask session created for user",
        )
    )
    db.session.commit()

    return redirect(url_for("main.dashboard"))
