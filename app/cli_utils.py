
from __future__ import annotations



from functools import wraps

from typing import Callable, Any

import os





def cli_safe(imports: Callable[[], dict[str, Any]] | None = None,

             use_test_mode_env: str | None = None):

    """

    Decorator for CLI entrypoints:

      - defers imports until call time

      - plays nice with pytest monkeypatch

      - supports test/prod mode via env var

    """



    def decorator(fn: Callable[..., int]):

        @wraps(fn)

        def wrapper(*args: Any, **kwargs: Any) -> int:

            mode = None

            if use_test_mode_env:

                mode = os.getenv(use_test_mode_env, "prod")



            imported: dict[str, Any] = {}

            if imports is not None:

                imported = imports()



            return fn(*args, _cli_mode=mode, _imports=imported, **kwargs)



        return wrapper



    return decorator

