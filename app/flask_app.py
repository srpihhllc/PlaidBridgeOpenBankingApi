# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/flask_app.py

"""
Thin shim so legacy/top-level tests can do:
    from flask_app import app, parse_pdf, export_csv, compute_new_balance, …
This module avoids importing a module-level Flask instance named `app`
unless EXPORT_LEGACY_APP=1 is set in the environment.
"""

import os
from collections.abc import Callable
from typing import Any

from app.services.balance import account_balance, compute_new_balance, update_account_balance
from app.services.csv_utils import export_csv, import_csv, save_statements_as_csv
from app.services.discrepancy import correct_discrepancies
from app.services.pdf_parser import parse_pdf

# -------------------------------------------------------------------------
# Application factory import (typed for mypy)
# -------------------------------------------------------------------------
create_package_app: Callable[..., Any] | None
try:
    from app import create_app as create_package_app
except Exception:
    create_package_app = None

# -------------------------------------------------------------------------
# PDF generator import — tolerate missing symbol for mypy
# -------------------------------------------------------------------------
try:
    from app.services.pdf_generator import generate_pdf_from_csv
except Exception:
    # Provide a typed placeholder so mypy and runtime both remain stable
    def generate_pdf_from_csv(*args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "generate_pdf_from_csv is not implemented in app.services.pdf_generator"
        )


# -------------------------------------------------------------------------
# Helper: parse boolean-ish env var
# -------------------------------------------------------------------------
def _env_flag_true(name: str, default: str = "1") -> bool:
    """
    Return True if environment variable `name` is set to a true value.
    Accepts "1", "true", "yes" (case-insensitive). Otherwise False.
    """
    val = os.getenv(name, default)
    return str(val).lower() in ("1", "true", "yes")


# -------------------------------------------------------------------------
# Optional legacy module-level Flask instance
# -------------------------------------------------------------------------
_module_app: Any | None = None

if os.getenv("EXPORT_LEGACY_APP", "0") == "1":
    if create_package_app is None:
        raise RuntimeError("create_app not importable; cannot construct legacy module app.")
    _module_app = create_package_app()
    # Ensure there is a deterministic default for ENABLE_SERVICE_WORKER.
    # Use environment variable ENABLE_SERVICE_WORKER (1/0 or true/false) if present,
    # otherwise default to True for backwards compatibility.
    _module_app.config.setdefault(
        "ENABLE_SERVICE_WORKER", _env_flag_true("ENABLE_SERVICE_WORKER", default="1")
    )
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
    "generate_pdf_from_csv",
    "compute_new_balance",
    "update_account_balance",
    "account_balance",
    "get_app",
]


# -------------------------------------------------------------------------
# Factory accessor
# -------------------------------------------------------------------------
def get_app():
    """
    Return an application instance. If EXPORT_LEGACY_APP was set, returns the
    legacy module app. Otherwise returns a fresh app from the package factory.

    This function also ensures the application config contains a sensible
    default for ENABLE_SERVICE_WORKER, controlled by the environment variable
    ENABLE_SERVICE_WORKER (accepted values: 1/0/true/false/yes/no). If the env
    var is not present, ENABLE_SERVICE_WORKER defaults to True.
    """
    if _module_app is not None:
        return _module_app
    if create_package_app is None:
        raise RuntimeError("Application factory is not importable")

    app = create_package_app()

    # Ensure the flag exists and is deterministic for templates that read it.
    app.config.setdefault(
        "ENABLE_SERVICE_WORKER", _env_flag_true("ENABLE_SERVICE_WORKER", default="1")
    )

    return app
