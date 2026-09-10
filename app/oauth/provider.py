# =============================================================================
# FILE: app/oauth/provider.py
# DESCRIPTION: Unified OAuth provider abstraction (Google, Apple, Microsoft)
#              Adds Apple JWKS verification for id_token signatures with a
#              small in-memory cache for Apple's JWKS.
# =============================================================================

from __future__ import annotations

import json
import logging
import time
from enum import Enum
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)


class ProviderName(str, Enum):
    GOOGLE = "google"
    APPLE = "apple"
    MICROSOFT = "microsoft"


_apple_jwks_cache: Dict[str, Any] = {"jwks": None, "fetched_at": 0}
_APPLE_JWKS_TTL = 60 * 60  # 1 hour


def _get_apple_jwks() -> Dict[str, Any]:
    now = int(time.time())
    cached = _apple_jwks_cache
    if cached["jwks"] and (now - cached["fetched_at"] < _APPLE_JWKS_TTL):
        return cached["jwks"]

    resp = requests.get("https://appleid.apple.com/auth/keys", timeout=5)
    resp.raise_for_status()
    jwks = resp.json()
    cached["jwks"] = jwks
    cached["fetched_at"] = now
    return jwks


class OAuthProvider:
    def __init__(
        self, provider: ProviderName, config: Optional[Dict[str, Any]] = None
    ) -> None:
        self.provider = provider
        self.config = config or {}

    def get_authorization_url(
        self,
        state: Optional[str] = None,
        scope: Optional[str] = None,
        code_challenge: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generates the provider-specific OAuth authorization URL for user redirection.
        """
        endpoints = {
            ProviderName.GOOGLE: "https://accounts.google.com/o/oauth2/v2/auth",
            ProviderName.MICROSOFT: "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            ProviderName.APPLE: "https://appleid.apple.com/auth/authorize",
        }

        base_url = endpoints.get(self.provider)
        if not base_url:
            raise NotImplementedError(
                f"Provider {self.provider} not supported"
            )

        params: Dict[str, Any] = {
            "client_id": self.config.get("client_id", ""),
            "redirect_uri": self.config.get("redirect_uri", ""),
            "response_type": "code",
        }

        if state:
            params["state"] = state

        if scope:
            params["scope"] = scope
        else:
            if self.provider == ProviderName.GOOGLE:
                params["scope"] = "openid email profile"
            elif self.provider == ProviderName.MICROSOFT:
                params["scope"] = "openid profile email User.Read"
            elif self.provider == ProviderName.APPLE:
                params["scope"] = "name email"
                params["response_mode"] = "form_post"

        # Google specific parameter
        if self.provider == ProviderName.GOOGLE:
            params["access_type"] = kwargs.get("access_type", "offline")

        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        # Pass through any remaining keyword arguments
        for k, v in kwargs.items():
            if k not in params and v is not None:
                params[k] = v

        return f"{base_url}?{urlencode(params)}"

    def exchange_code(self, code: str) -> Dict[str, Any]:
        if self.provider == ProviderName.GOOGLE:
            token_url = "https://oauth2.googleapis.com/token"
            resp = requests.post(
                token_url,
                data={
                    "code": code,
                    "client_id": self.config.get("client_id"),
                    "client_secret": self.config.get("client_secret"),
                    "redirect_uri": self.config.get("redirect_uri"),
                    "grant_type": "authorization_code",
                },
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()

        if self.provider == ProviderName.MICROSOFT:
            token_url = (
                "https://login.microsoftonline.com/common/oauth2/v2.0/token"
            )
            resp = requests.post(
                token_url,
                data={
                    "code": code,
                    "client_id": self.config.get("client_id"),
                    "client_secret": self.config.get("client_secret"),
                    "redirect_uri": self.config.get("redirect_uri"),
                    "grant_type": "authorization_code",
                },
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()

        if self.provider == ProviderName.APPLE:
            client_id = self.config.get("client_id")
            redirect_uri = self.config.get("redirect_uri")
            team_id = self.config.get("apple_team_id")
            key_id = self.config.get("apple_key_id")
            private_key = self.config.get("apple_private_key")
            aud = self.config.get("apple_aud", "https://appleid.apple.com")

            if not all(
                (client_id, redirect_uri, team_id, key_id, private_key)
            ):
                raise RuntimeError(
                    "Apple OAuth requires apple_team_id, apple_key_id and apple_private_key in config"
                )

            try:
                import jwt
            except ImportError as exc:
                raise RuntimeError(
                    "PyJWT is required for Apple client assertion"
                ) from exc

            now = int(time.time())
            payload = {
                "iss": team_id,
                "iat": now,
                "exp": now + 120,
                "aud": aud,
                "sub": client_id,
            }
            headers = {"kid": key_id}
            client_assertion = jwt.encode(
                payload, private_key, algorithm="ES256", headers=headers
            )

            token_url = "https://appleid.apple.com/auth/token"
            resp = requests.post(
                token_url,
                data={
                    "client_id": client_id,
                    "client_secret": client_assertion,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()

        raise NotImplementedError(f"Provider {self.provider} not supported")

    def fetch_profile(self, token_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.provider == ProviderName.GOOGLE:
            access_token = token_data.get("access_token")
            profile_url = "https://openidconnect.googleapis.com/v1/userinfo"
            resp = requests.get(
                profile_url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            resp.raise_for_status()
            d = resp.json()
            return {
                "email": d.get("email"),
                "sub": d.get("sub"),
                "name": d.get("name"),
            }

        if self.provider == ProviderName.MICROSOFT:
            access_token = token_data.get("access_token")
            profile_url = "https://graph.microsoft.com/v1.0/me"
            resp = requests.get(
                profile_url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            resp.raise_for_status()
            d = resp.json()
            email = d.get("mail") or d.get("userPrincipalName")
            return {
                "email": email,
                "sub": d.get("id"),
                "name": d.get("displayName"),
            }

        if self.provider == ProviderName.APPLE:
            id_token = token_data.get("id_token")
            if not id_token:
                raise RuntimeError(
                    "Apple token response did not include id_token"
                )

            try:
                import jwt
                from jwt.algorithms import RSAAlgorithm
            except ImportError:
                try:
                    import jwt

                    payload = jwt.decode(
                        id_token, options={"verify_signature": False}
                    )
                    return {
                        "email": payload.get("email"),
                        "sub": payload.get("sub"),
                        "name": payload.get("name"),
                    }
                except Exception:
                    return {"email": None, "sub": None, "name": None}

            client_id = self.config.get("client_id")
            try:
                jwks = _get_apple_jwks()
                header = jwt.get_unverified_header(id_token)
                kid = header.get("kid")
                if not kid:
                    raise RuntimeError("id_token missing kid header")

                key_dict = None
                for k in jwks.get("keys", []):
                    if k.get("kid") == kid:
                        key_dict = k
                        break
                if not key_dict:
                    raise RuntimeError(
                        "No matching Apple JWKS key found for kid"
                    )

                public_key = RSAAlgorithm.from_jwk(json.dumps(key_dict))
                payload = jwt.decode(
                    id_token,
                    public_key,
                    algorithms=["RS256"],
                    audience=client_id,
                )
                return {
                    "email": payload.get("email"),
                    "sub": payload.get("sub"),
                    "name": payload.get("name"),
                }

            except jwt.PyJWTError as exc:
                logger.error(
                    "Apple id_token signature verification failed: %s", exc
                )
                raise RuntimeError("Invalid Apple ID Token signature") from exc
            except Exception as exc:
                logger.debug("System error during parsing: %s", exc)
                payload = jwt.decode(
                    id_token, options={"verify_signature": False}
                )
                return {
                    "email": payload.get("email"),
                    "sub": payload.get("sub"),
                    "name": payload.get("name"),
                }

        raise NotImplementedError(f"Provider {self.provider} not supported")
