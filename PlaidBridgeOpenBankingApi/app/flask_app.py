# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/flask_app.py

"""
Legacy shim for backwards compatibility.
"""

import os
from collections.abc import Callable
from typing import Any

# Absolute imports into the real package
from PlaidBridgeOpenBankingApi.app.services.balance import (
    account_balance,
    compute_new_balance,
    update_account_balance,
)
from PlaidBridgeOpenBankingApi.app.services.csv_utils import (
    export_csv,
    import_csv,
    save_statements_as_csv,
)
from PlaidBridgeOpenBankingApi.app.services.discrepancy import correct_discrepancies
from PlaidBridgeOpenBankingApi.app.services.pdf_parser import parse_pdf

# Application factory import
create_package_app: Callable[..., Any] | None
try:
    from PlaidBridgeOpenBankingApi.app import create_app as create_package_app
except Exception:
    create_package_app = None

# PDF generator import
try:
    from PlaidBridgeOpenBankingApi.app.services.pdf_generator import generate_pdf_from_csv
except Exception:
    def generate_pdf_from_csv(*args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError(
            "generate_pdf_from_csv is not implemented in PlaidBridgeOpenBankingApi.app.services.pdf_generator"
        )


def _env_flag_true(name: str, default: str = "1") -> bool:
    val = os.getenv(name, default)
    return str(val).lower() in ("1", "true", "yes")


_module_app: Any | None = None

if os.getenv("EXPORT_LEGACY_APP", "0") == "1":
    if create_package_app is None:
        raise RuntimeError("create_app not importable; cannot construct legacy module app.")
    _module_app = create_package_app()
    _module_app.config.setdefault(
        "ENABLE_SERVICE_WORKER", _env_flag_true("ENABLE_SERVICE_WORKER", default="1")
    )
    app = _module_app


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


def get_app():
    if _module_app is not None:
        return _module_app
    if create_package_app is None:
        raise RuntimeError("Application factory is not importable")

    app = create_package_app()
    app.config.setdefault(
        "ENABLE_SERVICE_WORKER", _env_flag_true("ENABLE_SERVICE_WORKER", default="1")
    )
    return app
