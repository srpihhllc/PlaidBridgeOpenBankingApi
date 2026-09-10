# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/utils/__init__.py

# Backwards-compat package surface for `from app.utils import ...`.
# Export stable helpers from submodules so legacy imports continue to work.
#
# We also re-export export_csv at package root so tests that call:
#   from app.utils import export_csv
# resolve to the updated implementation in csv_utils.

from __future__ import annotations

import importlib
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ——— Primary, resilient export_csv wrapper ———
def _resolve_export_csv() -> Callable[..., Any]:
    """
    Import the authoritative export_csv implementation.

    Preference order:
      1) app.utils.csv_utils.export_csv
      2) app.utils.csv.export_csv
      3) provide a clear ImportError-raising stub
    """
    candidates = ("app.utils.csv_utils", "app.utils.csv", "app.utils_legacy")
    for mod_name in candidates:
        try:
            mod = importlib.import_module(mod_name)
            if hasattr(mod, "export_csv"):
                return getattr(mod, "export_csv")
        except Exception:
            logger.debug(
                "Could not import %s (when resolving export_csv)",
                mod_name,
                exc_info=True,
            )

    # fallback stub
    def _missing(*args: Any, **kwargs: Any) -> Any:  # pragma: no cover
        raise ImportError(
            "export_csv is not available from csv_utils or csv modules"
        )

    return _missing


def export_csv(*args: Any, **kwargs: Any) -> Any:
    """
    Robust, compatibility wrapper for export_csv.

    - Calls the underlying implementation directly.
    - If the underlying implementation raises TypeError because it doesn't accept
      the 'output_path' keyword (older signature), and 'output_path' exists in kwargs,
      retry by passing output_path as the second positional argument.
    """
    impl = _resolve_export_csv()

    # Fast path: try calling exactly as requested
    try:
        return impl(*args, **kwargs)
    except TypeError as e:
        # If caller passed output_path but impl doesn't accept it, retry with positional
        if "output_path" in kwargs:
            output_val = kwargs.pop("output_path")
            try:
                return impl(*args, output_val, **kwargs)
            except TypeError:
                # restore and re-raise original error for clarity
                kwargs["output_path"] = output_val
                raise e
        # If TypeError for another reason, re-raise
        raise


# Re-export other utilities as before (best-effort imports)
try:
    from .csv_utils import export_csv as _csv_utils_export  # type: ignore
except Exception:
    _csv_utils_export = None  # not used; wrapper above resolves at runtime

# Keep previous public exports (only a subset shown here; extend as needed)
try:
    from .comms import notify_authorities  # type: ignore
except Exception:

    def notify_authorities(
        *a: Any, **kw: Any
    ) -> Any:  # pragma: no cover - fallback
        raise ImportError("notify_authorities not available")


try:
    from .loan_utils import analyze_loan_agreement  # type: ignore
except Exception:

    def analyze_loan_agreement(
        *a: Any, **kw: Any
    ) -> Any:  # pragma: no cover - fallback
        raise ImportError("analyze_loan_agreement not available")


try:
    from .time_utils import time_since  # type: ignore
except Exception:

    def time_since(*a: Any, **kw: Any) -> Any:  # pragma: no cover - fallback
        raise ImportError("time_since not available")


__all__ = [
    "export_csv",
    "notify_authorities",
    "analyze_loan_agreement",
    "time_since",
]
