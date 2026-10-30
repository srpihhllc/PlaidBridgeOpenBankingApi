
"""Backwards-compatible exports for ``from app.utils import ...``."""



from __future__ import annotations



import importlib

import logging

from datetime import datetime

from typing import Any, Callable, cast



logger = logging.getLogger(__name__)





def _resolve_export_csv() -> Callable[..., Any]:

    """Resolve the authoritative CSV export implementation."""

    candidates = ("app.utils.csv_utils", "app.utils.csv", "app.utils_legacy")



    for mod_name in candidates:

        try:

            mod = importlib.import_module(mod_name)

            if hasattr(mod, "export_csv"):

                return cast(Callable[..., Any], getattr(mod, "export_csv"))

        except Exception:

            logger.debug(

                "Could not import %s when resolving export_csv",

                mod_name,

                exc_info=True,

            )



    def _missing(*args: Any, **kwargs: Any) -> Any:

        raise ImportError(

            "export_csv is not available from csv_utils or csv modules"

        )



    return _missing





def export_csv(*args: Any, **kwargs: Any) -> Any:

    """Call the CSV exporter, supporting older ``output_path`` signatures."""

    impl = _resolve_export_csv()



    try:

        return impl(*args, **kwargs)

    except TypeError as error:

        if "output_path" not in kwargs:

            raise



        output_val = kwargs.pop("output_path")

        try:

            return impl(*args, output_val, **kwargs)

        except TypeError:

            kwargs["output_path"] = output_val

            raise error





try:

    from .comms import notify_authorities

except ImportError:



    def notify_authorities(report: Any) -> Any:

        raise ImportError("notify_authorities not available")





try:

    from .loan_utils import analyze_loan_agreement

except ImportError:



    def analyze_loan_agreement(text: Any) -> Any:

        raise ImportError("analyze_loan_agreement not available")





try:

    from .time_utils import time_since

except ImportError:



    def time_since(ts: datetime) -> str:

        raise ImportError("time_since not available")





__all__ = [

    "export_csv",

    "notify_authorities",

    "analyze_loan_agreement",

    "time_since",

]

