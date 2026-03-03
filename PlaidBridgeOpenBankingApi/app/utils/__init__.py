# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/utils/__init__.py

# 1) Backup original and write new file
FILE=PlaidBridgeOpenBankingApi/app/utils/__init__.py
test -f "$FILE" || { echo "$FILE not found"; exit 1; }
cp -v "$FILE" "$FILE.bak.$(date +%s)"

cat > "$FILE" <<'PY'
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

# ---------------------------------------------------------------------------
# Ensure audit runner modules are available via `app.utils` package attribute
# (so code that does `from app.utils import nav_audit` continues to work).
# We import them dynamically and expose module objects; failures are logged so
# the package still imports even if some audit modules are missing.
# ---------------------------------------------------------------------------
try:
    # Import audit submodules as module objects and expose them on the package.
    # We prefer absolute import strings to avoid relative import quirks during
    # partial refactors or when modules are moved.
    nav_audit = importlib.import_module("app.utils.nav_audit")
    route_audit = importlib.import_module("app.utils.route_audit")
    template_audit = importlib.import_module("app.utils.template_audit")
    relationship_audit = importlib.import_module("app.utils.relationship_audit")
    redis_utils = importlib.import_module("app.utils.redis_utils")

    # Extend __all__ so `from app.utils import nav_audit` works.
    __all__ += [
        "nav_audit",
        "route_audit",
        "template_audit",
        "relationship_audit",
        "redis_utils",
    ]
except Exception as _exc:  # pragma: no cover - import-time defensive logging
    logger.warning("app.utils: could not import audit submodules: %s", _exc)
PY

# 2) Verify import surface
export PYTHONPATH="$PWD/PlaidBridgeOpenBankingApi"
python - <<'PY'
import importlib
m = importlib.import_module("app.utils")
print("app.utils __file__:", getattr(m, "__file__", None))
print("nav_audit present:", hasattr(m, "nav_audit"))
try:
    na = importlib.import_module("app.utils.nav_audit")
    print("nav_audit module file:", getattr(na, "__file__", None), "has run?:", hasattr(na, "run"))
except Exception as e:
    print("nav_audit direct import failed:", e)
PY

# 3) Run audits and route diagnostic + focused test
python -m app.scripts.audit | tee audit_output_after_init_fix.txt
python scripts/diagnose_routes.py > route_diagnostic.csv 2> route_diagnostic.json
head -n 200 route_diagnostic.csv
pytest -q app/tests/test_auth_routes.py::test_login_invalid_credentials -q | tee test_login_invalid_credentials.txt

# 4) Commit & push with your message (only if you're happy with the changes)
git add PlaidBridgeOpenBankingApi/app/utils/__init__.py
git commit -m "Add dynamic import for audit submodules in utils" -m "Dynamically import audit submodules and expose them in the app.utils package. Log warnings if any submodules fail to import."
git push origin chore/add-nav-audit-run

 
