# app/services/card_manager.py

"""
Card management service for Treasury Prime sandbox.

Provides suspend/unfreeze helpers with explicit typing and
mypy‑friendly request handling.
"""

import os
from typing import Final

import requests
from requests import Response

API_BASE: Final[str] = "https://api.sandbox.treasuryprime.com/cards"
API_KEY_ENV: Final[str] = "TREASURY_PRIME_SANDBOX_API_KEY"


def _auth_headers() -> dict[str, str]:
    """Return authorization headers for Treasury Prime API."""
    api_key = os.getenv(API_KEY_ENV)
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def suspend_card(card_id: str) -> bool:
    """Suspend a card in Treasury Prime sandbox."""
    url = f"{API_BASE}/{card_id}/suspend"
    headers = _auth_headers()

    res: Response = requests.post(url, headers=headers)
    return res.status_code == 200


def unfreeze_card(card_id: str) -> bool:
    """Unfreeze (unsuspend) a card in Treasury Prime sandbox."""
    url = f"{API_BASE}/{card_id}/unsuspend"
    headers = _auth_headers()

    res: Response = requests.post(url, headers=headers)
    return res.status_code == 200
