# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/utils/__init__.py

# =============================================================================
# utils package initializer (hardened + correct for PlaidBridgeOpenBankingApi)
# =============================================================================

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable
from typing import Any, cast

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Primary stable helpers (prefer relative imports)
# -----------------------------------------------------------------------------
try:
    from .comms import notify_authorities
    from .loan_utils import analyze_loan_agreement
    from .time_utils import time_since
except Exception:
    # Absolute fallback imports using the correct package root
    _mod = importlib.import_module(
        "PlaidBridgeOpenBankingApi.app.utils.comms"
    )
    notify_authorities = cast(Any, _mod.notify_authorities)

    _mod = importlib.import_module(
        "PlaidBridgeOpenBankingApi.app.utils.loan_utils"
    )
    analyze_loan_agreement = cast(Any, _mod.analyze_loan_agreement)

    _mod = importlib.import_module(
        "PlaidBridgeOpenBankingApi.app.utils.time_utils"
    )
    time_since = cast(Any, _mod.time_since)

Func = Callable[..., Any]

# -----------------------------------------------------------------------------
# Legacy fallback module (corrected to real package root)
# -----------------------------------------------------------------------------
_LEGACY_FALLBACK_MODULE = (
    "PlaidBridgeOpenBankingApi.app.utils_legacy"
)

_SYMBOLS = [
    "create_bank_statement",
    "detect_fraudulent_transaction",
    "execute_smart_contract",
    "get_pythonanywhere_cpu_quota",
    "merge_pdfs",
]

# -----------------------------------------------------------------------------
# Try modern utils module first, fallback to legacy
# -----------------------------------------------------------------------------
_utils_mod = None
try:
    _utils_mod = importlib.import_module(
        "PlaidBridgeOpenBankingApi.app.utils.utils"
    )
except Exception:
    _utils_mod = None

for _name in _SYMBOLS:
    try:
        if _utils_mod is not None and hasattr(_utils_mod, _name):
            globals()[_name] = cast(
                Any, getattr(_utils_mod, _name)
            )
        else:
            legacy_mod = importlib.import_module(
                _LEGACY_FALLBACK_MODULE
            )
            globals()[_name] = cast(
                Any, getattr(legacy_mod, _name)
            )
    except Exception as _exc:
        _exc_msg = str(_exc)

        def _make_missing(name: str, exc_msg: str):
            def _missing(*args: Any, **kwargs: Any) -> Any:
                raise ImportError(
                    f"Required utility '{name}' is not available: {exc_msg}"
                )
            return _missing

        globals()[_name] = cast(
            Any, _make_missing(_name, _exc_msg)
        )
        logger.warning(
            "Utility %s not found: %s", _name, _exc_msg
        )

# -----------------------------------------------------------------------------
# Public API surface
# -----------------------------------------------------------------------------
__all__ = [
    "analyze_loan_agreement",
    "notify_authorities",
    "time_since",
] + _SYMBOLS


   



 
