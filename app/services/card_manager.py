# =============================================================================
# FILE: app/services/card_manager.py
# DESCRIPTION: Card management service for Treasury Prime sandbox.
#              Provides suspend/unfreeze helpers with explicit typing.
# =============================================================================

from __future__ import annotations

import logging
import os
from typing import Final

import requests
from requests import RequestException, Response

logger = logging.getLogger(__name__)

API_BASE: Final[str] = "https://api.sandbox.treasuryprime.com/cards"
API_KEY_ENV: Final[str] = "TREASURY_PRIME_SANDBOX_API_KEY"
REQUEST_TIMEOUT: Final[int] = 15


def _auth_headers() -> dict[str, str]:
    """Return authorization headers for Treasury Prime API."""
    api_key = os.getenv(API_KEY_ENV)
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def suspend_card(card_id: str) -> bool:
    """Suspend a card in Treasury Prime sandbox."""
    url = f"{API_BASE}/{card_id}/suspend"
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
    """Unfreeze (unsuspend) a card in Treasury Prime sandbox."""
    url = f"{API_BASE}/{card_id}/unsuspend"
    headers = _auth_headers()

    try:
        res: Response = requests.post(
            url, headers=headers, timeout=REQUEST_TIMEOUT
        )
        return res.status_code == 200
    except RequestException as e:
        logger.error(f"Network error unfreezing card {card_id}: {e}")
        return False


__all__ = ["suspend_card", "unfreeze_card"]
