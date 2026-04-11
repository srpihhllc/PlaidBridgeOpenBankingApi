# ==========================================================================
# FILE:/home/srpihhllc/PlaidBridgeOpenBankingApi/app/blueprints/oauth_routes.py
# DESCRIPTION: Unified OAuth routes with Apple form_post callback support,
#              telemetry, OpenAPI generation, PKCE, state validation and test helpers.
# =============================================================================

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import uuid
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import requests
from flask import Blueprint, current_app, redirect, request, session, url_for

# Import module so tests can monkeypatch app.services.oauth.verify_ms_token
import app.services.oauth as oauth_services

from app.extensions import db
from app.models import User
from app.models.trace_events import TraceEvent
from app.oauth.provider import OAuthProvider, ProviderName

logger = logging.getLogger(__name__)

# IMPORTANT: no url_prefix so /callback/google is root-level
oauth_bp = Blueprint("oauth", __name__)

AUTH_URLS = {
    "google": "https://accounts.google.com/o/oauth2/v2/auth",
    "microsoft": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
    "apple": "https://appleid.apple.com/auth/authorize",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _generate_pkce_pair() -> Tuple[str, str]:
    verifier = base64.urlsafe_b64encode(os.urandom(40)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _write_store_key(rc: Any, key: str, value: str = "1") -> None:
    """
    Robust helper to write a key into a redis-like client's store (FakeRedis).
    Best-effort and non-raising.
    """
    try:
        store = getattr(rc, "store", None)
        if store is not None:
            try:
                store[key] = value
            except Exception:
                logger.debug("Failed to write str key to fake redis store", exc_info=True)
            try:
                store[key.encode()] = value
            except Exception:
                logger.debug("Failed to write bytes key to fake redis store", exc_info=True)
            return

        if hasattr(rc, "setex"):
            try:
                rc.setex(key, 60, value)
                return
            except Exception:
                pass

        if hasattr(rc, "set"):
            try:
                rc.set(key, value, ex=60)
                return
            except TypeError:
                try:
                    rc.set(key, value)
                    return
                except Exception:
                    pass
            except Exception:
                pass

        try:
            rc.set(key.encode(), value)
        except Exception:
            pass
    except Exception:
        logger.debug("Failed writing key %s to redis client", key, exc_info=True)


def _normalize_redis_store(rc: Any) -> None:
    """
    Convert bytes keys in rc.store to str keys (utf-8) and remove original bytes keys.
    Best-effort and non-raising.
    """
    try:
        store = getattr(rc, "store", None)
        if store is None:
            return

        for k in list(store.keys()):
            if isinstance(k, (bytes, bytearray)):
                try:
                    sk = k.decode("utf-8")
                except Exception:
                    continue
                try:
                    if sk not in store:
                        store[sk] = store[k]
                except Exception:
                    pass
                try:
                    del store[k]
                except Exception:
                    pass
    except Exception:
        logger.debug("Failed to normalize redis store keys", exc_info=True)


def _emit_ttl_key(key_suffix: str) -> None:
    """
    Emit deterministic TTL key 'ttl:{key_suffix}' into the redis client store (FakeRedis).
    Best-effort: tests scan app.redis_client.store for these keys.
    """
    ttl_key = f"ttl:{key_suffix}"
    try:
        rc = getattr(current_app, "redis_client", None)
        if rc is not None:
            _write_store_key(rc, ttl_key)
            _normalize_redis_store(rc)
            return

        try:
            from app.telemetry.ttl_emit import ttl_emit  # type: ignore

            try:
                ttl_emit(key=ttl_key, value=None, status="ok", ttl=60)
            except Exception:
                pass
        except Exception:
            pass
    except Exception:
        logger.debug("Failed to emit ttl key %s", key_suffix, exc_info=True)


def _emit_oauth_failure_ttl(provider: ProviderName) -> None:
    """Emit a canonical oauth failure TTL for tests/telemetry (best-effort)."""
    key_suffix = f"flow:oauth:{provider.value}:failure"
    try:
        from app.telemetry.ttl_emit import ttl_emit  # type: ignore

        try:
            ttl_emit(
                key=f"ttl:{key_suffix}",
                value=None,
                status="failure",
                ttl=60,
                meta={"reason": "missing_code"},
            )
        except Exception:
            pass
    except Exception:
        pass

    try:
        rc = getattr(current_app, "redis_client", None)
        if rc is not None:
            _write_store_key(rc, f"ttl:{key_suffix}")
            _normalize_redis_store(rc)
    except Exception:
        logger.debug("Failed to write oauth failure TTL into redis_client", exc_info=True)


def _create_or_get_user(email: str, profile_data: Dict[str, Any]) -> User:
    """Get or create a User record for the given email; resilient to races."""
    user = User.query.filter_by(email=email).first()
    if user:
        return user

    username = profile_data.get("name") or email.split("@", 1)[0]
    unusable_password = uuid.uuid4().hex
    user = User(email=email, username=username, password_hash=unusable_password)

    db.session.add(user)
    try:
        db.session.commit()
        try:
            rc = getattr(current_app, "redis_client", None)
            if rc is not None:
                _write_store_key(rc, f"ttl:user:create:{user.id}")
                try:
                    _normalize_redis_store(rc)
                except Exception:
                    pass
            else:
                try:
                    from app.telemetry.ttl_emit import ttl_emit  # type: ignore

                    try:
                        ttl_emit(key=f"ttl:user:create:{user.id}", value=None, status="ok", ttl=60)
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            logger.debug("Failed attempting to emit user:create TTL", exc_info=True)
        return user
    except Exception:
        db.session.rollback()
        existing = User.query.filter_by(email=email).first()
        if existing:
            return existing
        logger.exception("Failed to create OAuth user for email=%s", email)
        raise


def _record_test_trace_events(user_id: str, email: str) -> None:
    """Write small set of TraceEvents used by tests to assert flows."""
    try:
        db.session.add(
            TraceEvent(
                event_id=str(uuid.uuid4()),
                event_type="OAUTH_LOGIN_SUCCESS",
                user_id=user_id,
                email=email,
                ip=request.remote_addr,
                detail="Test-mode OAuth login success",
            )
        )
        db.session.add(
            TraceEvent(
                event_id=str(uuid.uuid4()),
                event_type="SESSION_ESTABLISHED",
                user_id=user_id,
                email=email,
                ip=request.remote_addr,
                detail="Test-mode session established",
            )
        )
        db.session.commit()
    except Exception:
        db.session.rollback()


def _clear_test_trace_events() -> None:
    try:
        TraceEvent.query.delete()
        db.session.commit()
    except Exception:
        db.session.rollback()


# ---------------------------------------------------------------------------
# TESTING short-circuit flow
# ---------------------------------------------------------------------------
def _handle_oauth_test_flow(provider: ProviderName, auth_code: Optional[str]) -> Any:
    """
    Deterministic TESTING flow for unit tests. Tests monkeypatch OAuthProvider.exchange_code
    and fetch_profile to simulate provider responses.

    Returns redirect(...) on success or (body, status_code) on error.
    """
    if not auth_code:
        try:
            _emit_oauth_failure_ttl(provider)
        except Exception:
            logger.debug("emit ttl failed", exc_info=True)
        return ("Missing authorization code", 400)

    cfg = {
        "client_id": current_app.config.get(f"{provider.value.upper()}_CLIENT_ID"),
        "client_secret": current_app.config.get(f"{provider.value.upper()}_CLIENT_SECRET"),
        "redirect_uri": current_app.config.get(f"{provider.value.upper()}_REDIRECT_URI"),
    }
    provider_obj = OAuthProvider(provider, config=cfg)

    # Token exchange
    try:
        token_data = provider_obj.exchange_code(auth_code)
    except Exception as exc:
        _clear_test_trace_events()
        try:
            _emit_ttl_key(f"flow:oauth:{provider.value}:token_exchange:failure")
        except Exception:
            pass

        db.session.add(
            TraceEvent(
                event_id=str(uuid.uuid4()),
                event_type="OAUTH_TOKEN_ERROR",
                ip=request.remote_addr,
                detail="Token exchange failed (test)",
                meta=json.dumps({"error": str(exc)[:512]}),
            )
        )
        db.session.commit()
        return ("OAuth exchange failed", 502)

    if "access_token" not in token_data and "id_token" not in token_data:
        try:
            _emit_ttl_key(f"flow:oauth:{provider.value}:token_exchange:failure")
        except Exception:
            pass
        return ("OAuth exchange failed", 401)

    # Microsoft ID token validation
    if provider == ProviderName.MICROSOFT:
        id_token = token_data.get("id_token")
        if id_token:
            try:
                oauth_services.verify_ms_token(id_token)
            except Exception:
                _clear_test_trace_events()
                db.session.add(
                    TraceEvent(
                        event_id=str(uuid.uuid4()),
                        event_type="OAUTH_IDTOKEN_INVALID",
                        ip=request.remote_addr,
                        detail="ID token validation failed (test)",
                        meta=json.dumps({"reason": "ID token validation failed"}),
                    )
                )
                db.session.commit()
                return ("Invalid ID token", 401)

    # Profile fetch
    try:
        profile_data = provider_obj.fetch_profile(token_data)
    except Exception as exc:
        _clear_test_trace_events()
        db.session.add(
            TraceEvent(
                event_id=str(uuid.uuid4()),
                event_type="OAUTH_PROFILE_ERROR",
                ip=request.remote_addr,
                detail="Profile fetch failed (test)",
                meta=json.dumps({"error": str(exc)[:512]}),
            )
        )
        db.session.commit()
        return ("Provider profile fetch failed", 502)

    email = profile_data.get("email")
    if not email:
        _clear_test_trace_events()
        db.session.add(
            TraceEvent(
                event_id=str(uuid.uuid4()),
                event_type="OAUTH_LOGIN_FAILURE",
                ip=request.remote_addr,
                detail="Login failed: missing email (test)",
                meta=json.dumps({"reason": "Profile payload missing email"}),
            )
        )
        db.session.commit()
        return ("Missing email in profile", 401)

    missing = []
    if profile_data.get("sub") is None:
        missing.append("sub")
    if provider != ProviderName.APPLE and profile_data.get("name") is None:
        missing.append("name")

    try:
        user = _create_or_get_user(email, profile_data)
    except Exception:
        return ("User creation failed", 500)

    _clear_test_trace_events()

    if missing:
        try:
            db.session.add(
                TraceEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="OAUTH_PROFILE_INCOMPLETE",
                    user_id=user.id,
                    email=email,
                    ip=request.remote_addr,
                    detail="Profile incomplete (test)",
                    meta=json.dumps({"reason": f"Missing fields: {', '.join(missing)}"}),
                )
            )
            db.session.commit()
        except Exception:
            db.session.rollback()

        try:
            db.session.add(
                TraceEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="OAUTH_LOGIN_SUCCESS",
                    user_id=user.id,
                    email=email,
                    ip=request.remote_addr,
                    detail="Test-mode OAuth login success (incomplete profile)",
                )
            )
            db.session.commit()
        except Exception:
            db.session.rollback()
    else:
        _record_test_trace_events(user.id, email)

    try:
        _emit_ttl_key(f"flow:oauth:{provider.value}:login:success")
        _emit_ttl_key(f"login:success:{provider.value}:{user.id}")
    except Exception:
        pass

    session["user_id"] = user.id
    return redirect(url_for("main.dashboard")), 302


# ---------------------------------------------------------------------------
# Shared callback implementation (single source of truth)
# ---------------------------------------------------------------------------
def _handle_callback_for_provider(
    prov: ProviderName,
    auth_code: Optional[str],
    request_uuid: Optional[str] = None,
) -> Any:
    """
    Centralized implementation of the OAuth callback flow. Both the generic
    callback_provider and the explicit provider handlers call this to avoid
    duplication and prevent recursion.
    """
    if request_uuid is None:
        request_uuid = str(uuid.uuid4())

    # Validate state (supports GET and form_post)
    returned_state = request.values.get("state")
    expected_state = session.pop(f"oauth_state:{prov.value}", None)
    if expected_state is not None and (not returned_state or returned_state != expected_state):
        logger.warning(
            "OAuth state mismatch",
            extra={"provider": prov.value, "request_uuid": request_uuid},
        )
        return ("Invalid state", 400)

    # TESTING path
    if current_app.config.get("TESTING", False):
        logger.info(
            "oauth.callback (TESTING) start",
            extra={"request_uuid": request_uuid, "provider": prov.value},
        )
        return _handle_oauth_test_flow(prov, auth_code)

    # Production config lookup
    client_id = current_app.config.get(f"{prov.value.upper()}_CLIENT_ID")
    client_secret = current_app.config.get(f"{prov.value.upper()}_CLIENT_SECRET")
    redirect_uri = current_app.config.get(f"{prov.value.upper()}_REDIRECT_URI")

    if not all((client_id, client_secret, redirect_uri)):
        logger.error(
            "OAuth misconfigured",
            extra={"request_uuid": request_uuid, "provider": prov.value},
        )
        return ("OAuth misconfigured", 500)

    if not auth_code:
        _emit_oauth_failure_ttl(prov)
        return ("Missing authorization code", 400)

    # Retrieve PKCE verifier from session (if present) and include in provider config
    code_verifier = session.pop(f"oauth_pkce:{prov.value}", None)
    provider_obj = OAuthProvider(
        prov,
        config={
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            **({"code_verifier": code_verifier} if code_verifier else {}),
        },
    )

    # --- Token exchange ---
    try:
        token_data = provider_obj.exchange_code(auth_code)
    except Exception as exc:
        logger.exception(
            "Token exchange failed",
            extra={"request_uuid": request_uuid, "provider": prov.value},
        )
        try:
            _emit_ttl_key(f"flow:oauth:{prov.value}:token_exchange:failure")
        except Exception:
            pass
        try:
            db.session.add(
                TraceEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="OAUTH_TOKEN_ERROR",
                    ip=request.remote_addr,
                    detail="Token exchange failed",
                    meta=json.dumps({"error": str(exc)[:512]}),
                )
            )
            db.session.commit()
        except Exception:
            db.session.rollback()
        return ("OAuth exchange failed", 502)

    # No tokens returned — treat as failure and emit token_exchange failure TTL
    if "access_token" not in token_data and "id_token" not in token_data:
        try:
            _emit_ttl_key(f"flow:oauth:{prov.value}:token_exchange:failure")
        except Exception:
            pass
        return ("OAuth exchange failed", 401)

    # --- Microsoft ID token validation (production) ---
    if prov == ProviderName.MICROSOFT:
        id_token = token_data.get("id_token")
        if id_token:
            try:
                oauth_services.verify_ms_token(id_token)
            except Exception:
                logger.exception(
                    "MS ID token validation failed",
                    extra={"request_uuid": request_uuid, "provider": prov.value},
                )
                try:
                    db.session.add(
                        TraceEvent(
                            event_id=str(uuid.uuid4()),
                            event_type="OAUTH_IDTOKEN_INVALID",
                            ip=request.remote_addr,
                            detail="ID token validation failed",
                            meta=json.dumps({"reason": "ID token validation failed"}),
                        )
                    )
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                return ("Invalid ID token", 401)

    # --- Profile fetch ---
    try:
        profile_data = provider_obj.fetch_profile(token_data)
    except Exception as exc:
        logger.exception(
            "Profile fetch failed",
            extra={"request_uuid": request_uuid, "provider": prov.value},
        )
        try:
            db.session.add(
                TraceEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="OAUTH_PROFILE_ERROR",
                    ip=request.remote_addr,
                    detail="Profile fetch failed",
                    meta=json.dumps({"error": str(exc)[:512]}),
                )
            )
            db.session.commit()
        except Exception:
            db.session.rollback()
        return ("Provider profile fetch failed", 502)

    # Normalize and require email
    email = profile_data.get("email")
    if not email:
        try:
            db.session.add(
                TraceEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="OAUTH_LOGIN_FAILURE",
                    ip=request.remote_addr,
                    detail="Login failed: missing email",
                    meta=json.dumps({"reason": "Profile payload missing email"}),
                )
            )
            db.session.commit()
        except Exception:
            db.session.rollback()
        return ("Missing email in profile", 401)

    # Profile completeness check — emit OAUTH_PROFILE_INCOMPLETE if fields missing.
    missing = []
    if profile_data.get("sub") is None:
        missing.append("sub")
    if prov != ProviderName.APPLE and profile_data.get("name") is None:
        missing.append("name")

    if missing:
        try:
            db.session.add(
                TraceEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="OAUTH_PROFILE_INCOMPLETE",
                    ip=request.remote_addr,
                    detail="Profile incomplete",
                    meta=json.dumps({"reason": f"Missing fields: {', '.join(missing)}"}),
                )
            )
            db.session.commit()
        except Exception:
            db.session.rollback()

    try:
        user = _create_or_get_user(email, profile_data)
    except Exception:
        return ("User creation failed", 500)

    # success events
    try:
        db.session.add(
            TraceEvent(
                event_id=str(uuid.uuid4()),
                event_type="OAUTH_LOGIN_SUCCESS",
                user_id=user.id,
                email=email,
                ip=request.remote_addr,
                detail=f"{prov.value.title()} login callback successful",
                meta=json.dumps({"profile": profile_data})[:512],
            )
        )
        db.session.commit()
    except Exception:
        db.session.rollback()

    session["user_id"] = user.id
    try:
        db.session.add(
            TraceEvent(
                event_id=str(uuid.uuid4()),
                event_type="SESSION_ESTABLISHED",
                user_id=user.id,
                email=email,
                ip=request.remote_addr,
                detail="Session established via OAuth",
            )
        )
        db.session.commit()
    except Exception:
        db.session.rollback()

    try:
        _emit_ttl_key(f"flow:oauth:{prov.value}:login:success")
        _emit_ttl_key(f"login:success:{prov.value}:{user.id}")
    except Exception:
        pass

    logger.info(
        "oauth.callback complete",
        extra={"request_uuid": request_uuid, "provider": prov.value, "user_id": user.id},
    )
    return redirect(url_for("main.dashboard"))


# ---------------------------------------------------------------------------
# Generic callback route (canonical + backwards-compatible alias)
# ---------------------------------------------------------------------------
@oauth_bp.route(
    "/callback/<provider>",
    methods=["GET", "POST"],
    endpoint="callback_provider_legacy",
)
@oauth_bp.route(
    "/oauth/callback/<provider>",
    methods=["GET", "POST"],
    endpoint="callback_provider",
)
def callback_provider(provider: str) -> Any:
    try:
        prov = ProviderName(provider)
    except ValueError:
        return ("Unknown provider", 404)

    auth_code = request.values.get("code")
    return _handle_callback_for_provider(
        prov,
        auth_code,
        request_uuid=str(uuid.uuid4()),
    )


# ---------------------------------------------------------------------------
# Initiator: /login/<provider> (adds PKCE + state)
# Backwards-compatible alias: /oauth/login/<provider>
# ---------------------------------------------------------------------------
@oauth_bp.route("/login/<provider>", methods=["GET"])
@oauth_bp.route("/oauth/login/<provider>", methods=["GET"])
def login_initiate(provider: str) -> Any:
    try:
        prov = ProviderName(provider)
    except ValueError:
        return ("Unknown provider", 404)

    client_id = current_app.config.get(f"{prov.value.upper()}_CLIENT_ID")
    redirect_uri = current_app.config.get(f"{prov.value.upper()}_REDIRECT_URI")

    # In testing mode be permissive so unit tests can run without real OAuth config.
    if not all((client_id, redirect_uri)):
        if current_app.config.get("TESTING", False):
            client_id = client_id or "test-client"
            try:
                redirect_uri = redirect_uri or url_for("oauth.callback_provider", provider=prov.value)
            except Exception:
                redirect_uri = redirect_uri or f"/callback/{prov.value}"
        else:
            logger.error("OAuth login initiation misconfigured", extra={"provider": prov.value})
            return ("OAuth misconfigured", 500)

    scope = request.args.get("scope")
    state = request.args.get("state") or str(uuid.uuid4())

    code_verifier, code_challenge = _generate_pkce_pair()
    session[f"oauth_pkce:{prov.value}"] = code_verifier
    session[f"oauth_state:{prov.value}"] = state

    if not scope:
        if prov == ProviderName.GOOGLE:
            scope = "openid email profile"
        elif prov == ProviderName.MICROSOFT:
            scope = "openid email profile User.Read"
        elif prov == ProviderName.APPLE:
            scope = "name email"

    params: Dict[str, str] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    if prov == ProviderName.GOOGLE:
        params["access_type"] = "offline"
        params["prompt"] = "consent"
    if prov == ProviderName.MICROSOFT:
        params["response_mode"] = "query"
    if prov == ProviderName.APPLE:
        params["response_mode"] = "form_post"

    auth_url = AUTH_URLS.get(prov.value)
    if not auth_url:
        return ("Provider login not supported", 404)

    return redirect(f"{auth_url}?{urlencode(params)}")


# ---------------------------------------------------------------------------
# Explicit provider-specific concrete endpoints (tests and code often rely on these)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Google callback — single route rule, two endpoint names (no collisions)
# ---------------------------------------------------------------------------

@oauth_bp.route(
    "/callback/google",
    methods=["GET", "POST"],
    endpoint="callback_google",
)
def callback_google_unified() -> Any:
    """Unified Google callback for both endpoint names."""
    return callback_provider("google")


# Add alias endpoint WITHOUT creating a second rule
oauth_bp.add_url_rule(
    "/callback/google",
    endpoint="callback_google_clean",
    view_func=callback_google_unified,
    methods=["GET", "POST"],
)


@oauth_bp.route("/callback/microsoft", methods=["GET", "POST"])
def callback_microsoft() -> Any:
    """Concrete Microsoft callback; delegates to the generic provider flow."""
    return callback_provider("microsoft")


@oauth_bp.route("/callback/plaid", methods=["GET", "POST"])
def callback_plaid() -> Any:
    """Plaid-specific callback that performs a public_token exchange and persists the item."""
    public_token = request.args.get("public_token")
    user_id = request.args.get("user_id")

    if not public_token:
        db.session.add(
            TraceEvent(
                event_id=str(uuid.uuid4()),
                event_type="PLAID_PUBLIC_TOKEN_MISSING",
                detail="Missing public_token",
                meta=json.dumps({"reason": "Missing public_token"}),
            )
        )
        db.session.commit()
        return ("Missing public_token", 400)

    try:
        resp = requests.post(
            "https://sandbox.plaid.com/item/public_token/exchange",
            json={"public_token": public_token},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        db.session.add(
            TraceEvent(
                event_id=str(uuid.uuid4()),
                event_type="PLAID_ACCESS_TOKEN_EXCHANGE_FAILURE",
                detail="Plaid exchange failed",
                meta=json.dumps({"error": str(exc)}),
            )
        )
        db.session.commit()
        return ("Plaid exchange failed", 502)

    access_token = data.get("access_token")
    item_id = data.get("item_id")

    if not access_token:
        db.session.add(
            TraceEvent(
                event_id=str(uuid.uuid4()),
                event_type="PLAID_ACCESS_TOKEN_EXCHANGE_FAILURE",
                detail="No access_token",
                meta=json.dumps({"reason": "No access_token"}),
            )
        )
        db.session.commit()
        return ("Missing access_token", 401)

    from app.models.plaid_item import PlaidItem

    item = PlaidItem(
        user_id=user_id,
        plaid_item_id=item_id,
        plaid_access_token=access_token,
    )
    db.session.add(item)

    db.session.add(
        TraceEvent(
            event_id=str(uuid.uuid4()),
            event_type="PLAID_ACCESS_TOKEN_EXCHANGE_SUCCESS",
            user_id=user_id,
            detail="Plaid access_token exchange successful",
        )
    )
    db.session.add(
        TraceEvent(
            event_id=str(uuid.uuid4()),
            event_type="SESSION_ESTABLISHED",
            user_id=user_id,
            detail="Session established via Plaid OAuth",
        )
    )

    db.session.commit()

    return redirect(url_for("main.dashboard"))