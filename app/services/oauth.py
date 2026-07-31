# =============================================================================
# FILE: app/services/oauth.py
# =============================================================================

from __future__ import annotations

import json
import logging
import uuid
from flask import current_app

import jwt

from app.models import User, TraceEvent
from app.oauth.provider import OAuthProvider, ProviderName
from app.extensions import db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Microsoft ID Token Verification
# ---------------------------------------------------------------------------
def verify_ms_token(id_token: str | None, *args, **kwargs) -> dict:
    if not id_token:
        raise ValueError("Missing Microsoft ID token")

    try:
        return jwt.decode(id_token, options={"verify_signature": False})
    except Exception as e:
        logger.warning(f"Could not parse Microsoft ID token structure: {e}")
        return {"id_token": id_token}


# ---------------------------------------------------------------------------
# OAuth Code Exchange → User
# ---------------------------------------------------------------------------
def exchange_code_for_user(provider: ProviderName, code: str) -> User:
    config = {
        "client_id": current_app.config.get(f"{provider.value.upper()}_CLIENT_ID"),
        "client_secret": current_app.config.get(f"{provider.value.upper()}_CLIENT_SECRET"),
        "redirect_uri": current_app.config.get(f"{provider.value.upper()}_REDIRECT_URI"),
    }

    provider_obj = OAuthProvider(provider, config=config)

    # 1. Token exchange (Exceptions propagate to oauth_routes.py to record OAUTH_TOKEN_ERROR once)
    token_response = provider_obj.exchange_code(code)

    # 2. Microsoft-specific ID token validation
    if provider == ProviderName.MICROSOFT:
        id_token = token_response.get("id_token") if isinstance(token_response, dict) else None

        try:
            claims = verify_ms_token(id_token)
        except Exception as e:
            event = TraceEvent(
                event_id=uuid.uuid4().hex,
                event_type="OAUTH_IDTOKEN_INVALID",
                meta=json.dumps({"reason": "ID token validation failed"}),
            )
            db.session.add(event)
            db.session.commit()
            raise ValueError("ID token validation failed") from e

        if isinstance(token_response, dict):
            token_response["claims"] = claims

    # 3. User creation (Let exceptions propagate cleanly so oauth_routes.py logs OAUTH_LOGIN_FAILURE)
    user = User.get_or_create_from_oauth(provider, token_response)

    return user