# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/flask_app.py

"""
Thin shim for legacy/top-level imports.

This module provides a small compatibility layer for callers that import
from `flask_app` (legacy tests/scripts). It delegates to the canonical
factory in `app` and avoids duplicating create_app.
"""

from __future__ import annotations
import os
from collections.abc import Callable
from typing import Any

# Keep service imports tolerant — they may import heavy modules; use try/except.
try:
    from app.services.balance import account_balance, compute_new_balance, update_account_balance
    from app.services.csv_utils import export_csv, import_csv, save_statements_as_csv
    from app.services.discrepancy import correct_discrepancies
    from app.services.pdf_parser import parse_pdf
except Exception:
    # Provide fallbacks/placeholders if services are unavailable at import time
    def account_balance(*args, **kwargs):
        raise NotImplementedError("account_balance unavailable during import")

    def compute_new_balance(*args, **kwargs):
        raise NotImplementedError("compute_new_balance unavailable during import")

    def update_account_balance(*args, **kwargs):
        raise NotImplementedError("update_account_balance unavailable during import")

    def export_csv(*args, **kwargs):
        raise NotImplementedError("export_csv unavailable during import")

    def import_csv(*args, **kwargs):
        raise NotImplementedError("import_csv unavailable during import")

    def save_statements_as_csv(*args, **kwargs):
        raise NotImplementedError("save_statements_as_csv unavailable during import")

    def correct_discrepancies(*args, **kwargs):
        raise NotImplementedError("correct_discrepancies unavailable during import")

    def parse_pdf(*args, **kwargs):
        raise NotImplementedError("parse_pdf unavailable during import")


# -------------------------------------------------------------------------
# Try to import the canonical package factory from app.
# Do not raise during import — callers will see an error only when they try to use it.
# -------------------------------------------------------------------------
create_package_app: Callable[..., Any] | None
try:
    from app import create_app as create_package_app  # canonical factory
except Exception:
    create_package_app = None

# -------------------------------------------------------------------------
# Optional legacy module-level Flask instance
# -------------------------------------------------------------------------
_module_app: Any | None = None

if os.getenv("EXPORT_LEGACY_APP", "0") == "1":
    if create_package_app is None:
        raise RuntimeError("create_app not importable; cannot construct legacy module app.")
    _module_app = create_package_app()
    # Ensure deterministic default for ENABLE_SERVICE_WORKER.
    _module_app.config.setdefault("ENABLE_SERVICE_WORKER", os.getenv("ENABLE_SERVICE_WORKER", "1").lower() in ("1","true","yes"))
    app = _module_app  # legacy symbol for callers that import `app` directly

# -------------------------------------------------------------------------
# Public API surface
# -------------------------------------------------------------------------
__all__ = [
    "parse_pdf",
    "correct_discrepancies",
    "export_csv",
    "import_csv",
    "save_statements_as_csv",
    "compute_new_balance",
    "update_account_balance",
    "account_balance",
    "get_app",
]

# -------------------------------------------------------------------------
# Factory accessor
# -------------------------------------------------------------------------
def get_app() -> Any:
    """
    Return an application instance. If EXPORT_LEGACY_APP was set, returns the
    legacy module app. Otherwise returns a fresh app from the package factory.
    """
    if _module_app is not None:
        return _module_app
    if create_package_app is None:
        raise RuntimeError("Application factory is not importable")
    app = create_package_app()
    app.config.setdefault("ENABLE_SERVICE_WORKER", os.getenv("ENABLE_SERVICE_WORKER", "1").lower() in ("1","true","yes"))
    return app
