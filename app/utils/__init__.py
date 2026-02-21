# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/utils/__init__.py

# Backwards-compat package surface for `from app.utils import ...`.
# Export small, stable helpers from the package submodules so legacy
# imports continue to work while implementations are being reorganized.

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable
from typing import Any, cast

logger = logging.getLogger(__name__)

# Prefer relative imports inside the package for things already moved.
# Use a try/except so import-time failures fall back to dynamic resolution.
try:
    from .comms import notify_authorities
    from .loan_utils import analyze_loan_agreement
    from .time_utils import time_since
except Exception:
    # If package submodules are reorganized in a way that breaks relative imports
    # at import time, fall back to importlib to avoid static mypy attribute checks.
    _mod = importlib.import_module("app.utils.comms")
    notify_authorities = cast(Any, _mod.notify_authorities)
    _mod = importlib.import_module("app.utils.loan_utils")
    analyze_loan_agreement = cast(Any, _mod.analyze_loan_agreement)
    _mod = importlib.import_module("app.utils.time_utils")
    time_since = cast(Any, _mod.time_since)

# Helper type for exported callables we re-export from legacy/modern modules.
Func = Callable[..., Any]

# List of utility symbol names we want to export from either the new `app.utils`
# module or fall back to the legacy single-file module `app.utils_legacy`.
_LEGACY_FALLBACK_MODULE = "app.utils_legacy"
_SYMBOLS = [
    "create_bank_statement",
    "detect_fraudulent_transaction",
    "execute_smart_contract",
    "get_pythonanywhere_cpu_quota",
    "merge_pdfs",
]

# Try dynamic resolution to avoid static mypy complaining when the modern
# package-level `app.utils.utils` doesn't expose the symbols (during refactor).
_utils_mod = None
try:
    _utils_mod = importlib.import_module("app.utils.utils")
except Exception:
    _utils_mod = None

# Resolve each symbol: prefer _utils_mod if it exposes the name, otherwise
# import from the legacy module. We cast assigned symbols to Any to avoid
# static assignment-type complaints from mypy while keeping runtime behavior.
for _name in _SYMBOLS:
    try:
        if _utils_mod is not None and hasattr(_utils_mod, _name):
            globals()[_name] = cast(Any, getattr(_utils_mod, _name))
        else:
            legacy_mod = importlib.import_module(_LEGACY_FALLBACK_MODULE)
            globals()[_name] = cast(Any, getattr(legacy_mod, _name))
    except Exception as _exc:  # pragma: no cover - defensive fallback
        # If both modern and legacy fail, provide a safe placeholder that raises
        # a clear ImportError at call time. Capture values into defaults so the
        # produced callable doesn't reference a transient exception variable.
        _exc_msg = str(_exc)

        def _make_missing(name: str, exc_msg: str):
            def _missing(*args: Any, **kwargs: Any) -> Any:
                raise ImportError(f"Required utility '{name}' is not available: {exc_msg}")

            return _missing

        globals()[_name] = cast(Any, _make_missing(_name, _exc_msg))
        logger.warning("Utility %s not found in utils or legacy module: %s", _name, _exc_msg)

# Export stable public surface
__all__ = [
    "analyze_loan_agreement",
    "notify_authorities",
    "time_since",
] + _SYMBOLS
