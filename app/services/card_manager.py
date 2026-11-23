# =============================================================================

# FILE: app/services/card_manager.py

# DESCRIPTION: Card management service for Treasury Prime (sandbox & production).

#              Provides unified config resolution and suspend/unfreeze helpers.

# =============================================================================



from __future__ import annotations



import logging

import os

from typing import Final



import requests

from requests import RequestException, Response



logger = logging.getLogger(__name__)



SANDBOX_DEFAULT_URL: Final[str] = "https://api.sandbox.treasuryprime.com"

PROD_DEFAULT_URL: Final[str] = "https://api.treasuryprime.com"

REQUEST_TIMEOUT: Final[int] = 15





def get_treasury_prime_config() -> tuple[str, str]:

    """Resolve (base_url, api_key) from TREASURY_PRIME_ENV (sandbox|production)."""

    env = os.getenv("TREASURY_PRIME_ENV", "sandbox").strip().lower()

    if env == "production":

        base_url = os.getenv("TREASURY_PRIME_PRODUCTION_API_URL", PROD_DEFAULT_URL).rstrip("/")

        api_key = os.getenv("TREASURY_PRIME_PRODUCTION_API_KEY") or os.getenv("TREASURY_PRIME_API_KEY", "")

    else:

        base_url = os.getenv("TREASURY_PRIME_SANDBOX_API_URL", SANDBOX_DEFAULT_URL).rstrip("/")

        api_key = os.getenv("TREASURY_PRIME_SANDBOX_API_KEY") or os.getenv("TREASURY_PRIME_API_KEY", "")

    return base_url, api_key





def _auth_headers() -> dict[str, str]:

    """Return authorization headers for Treasury Prime API."""

    _, api_key = get_treasury_prime_config()

    return {"Authorization": f"Bearer {api_key}"} if api_key else {}





def suspend_card(card_id: str) -> bool:

    """Suspend a card in Treasury Prime."""

    base_url, _ = get_treasury_prime_config()

    url = f"{base_url}/cards/{card_id}/suspend"

    headers = _auth_headers()



    try:

        res: Response = requests.post(

            url, headers=headers, timeout=REQUEST_TIMEOUT

        )

        return res.status_code == 200

    except RequestException as e:

        logger.error(f"Network error suspending card {card_id}: {e}")

        return False





def unfreeze_card(card_id: str) -> bool:

    """Unfreeze (unsuspend) a card in Treasury Prime."""

    base_url, _ = get_treasury_prime_config()

    url = f"{base_url}/cards/{card_id}/unsuspend"

    headers = _auth_headers()



    try:

        res: Response = requests.post(

            url, headers=headers, timeout=REQUEST_TIMEOUT

        )

        return res.status_code == 200

    except RequestException as e:

        logger.error(f"Network error unfreezing card {card_id}: {e}")

        return False





__all__ = ["get_treasury_prime_config", "suspend_card", "unfreeze_card"]

