# =============================================================================
# FILE: app/utils/cli_decorators.py
# DESCRIPTION: Safe execution wrappers for CLI commands. Defers imports to
#              optimize boot times and isolates test environments.
# =============================================================================

from __future__ import annotations

import os
from functools import wraps
from typing import Any, Callable


def cli_safe(
    imports: Callable[[], dict[str, Any]] | None = None,
    use_test_mode_env: str | None = None,
) -> Callable[[Callable[..., int]], Callable[..., int]]:
    """
    Cockpit-grade decorator for CLI entrypoints.

    Capabilities:
      - Defers heavy imports until execution time, speeding up CLI boot logic.
      - Safely isolates modules to support Pytest monkeypatching.
      - Injects execution mode ('prod' or 'test') via environment variables.

    Args:
        imports: A callable returning a dictionary of deferred imports.
        use_test_mode_env: The environment variable key to check for test mode.

    Note:
        The wrapped function MUST accept `_cli_mode` (str | None) and 
        `_imports` (dict[str, Any]) as keyword arguments.
    """

    def decorator(fn: Callable[..., int]) -> Callable[..., int]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> int:
            # 1. Resolve Execution Mode
            mode: str | None = None
            if use_test_mode_env:
                mode = os.getenv(use_test_mode_env, "prod")

            # 2. Execute Deferred Imports
            imported: dict[str, Any] = {}
            if imports is not None:
                imported = imports()

            # 3. Inject Runtime Context and Execute
            return fn(*args, _cli_mode=mode, _imports=imported, **kwargs)

        return wrapper

    return decorator