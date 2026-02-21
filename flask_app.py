# Top-level shim for legacy imports (project root)
#
# This file proxies to app/flask_app.py so statements like:
#   from flask_app import get_app
# continue to work for tests and external tooling.
#
# If you previously had a minimal hello-world app here, it's safe to
# move that code into app/flask_app.py (or keep this shim and set
# EXPORT_LEGACY_APP=1 to create a legacy `app` instance).

import os
from typing import Any

try:
    # Import the public surface from the package-level shim.
    from app.flask_app import (
        account_balance,
        compute_new_balance,
        correct_discrepancies,
        export_csv,
        generate_pdf_from_csv,
        get_app,
        import_csv,
        parse_pdf,
        save_statements_as_csv,
        update_account_balance,
    )
except Exception as _err:  # pragma: no cover - surface import problems clearly
    raise ImportError(
        "Failed to import package shim from app.flask_app. "
        "Ensure the package `app` is importable and app/flask_app.py is present."
    ) from _err

# If callers expect a legacy module-level `app` object, create it when requested.
_module_app: Any | None = None
if os.getenv("EXPORT_LEGACY_APP", "0") == "1":
    _module_app = get_app()
    app = _module_app  # legacy symbol

# Re-export the public API surface
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
