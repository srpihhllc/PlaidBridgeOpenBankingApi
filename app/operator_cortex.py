# =============================================================================
# FILE: app/operator_cortex.py
# DESCRIPTION: Operator Cortex subsystem for runtime God-Mode stabilization.
# =============================================================================

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class OperatorCortex:
    def __init__(self, app: Optional[Any] = None) -> None:
        """
        Initialize OperatorCortex.

        Args:
            app: Optional Flask application instance.
        """
        self.app = app
        # Default state matching CLI expectations
        self.is_enabled: bool = False

        if app is not None:
            self.init_app(app)

    def init_app(self, app: Any) -> None:
        """
        Bind OperatorCortex to the Flask application instance.

        Args:
            app: Flask application instance.
        """
        self.app = app

        # Safely bind to Flask extensions dictionary
        if not hasattr(app, "extensions") or not isinstance(
            app.extensions, dict
        ):
            app.extensions = {}

        app.extensions["operator_cortex"] = self

        # Optionally pull initial config if set in Flask app
        self.is_enabled = bool(
            app.config.get("OPERATOR_CORTEX_ENABLED", self.is_enabled)
        )

        if hasattr(app, "logger"):
            app.logger.info("🧠 OperatorCortex initialized successfully.")
        else:
            logger.info("🧠 OperatorCortex initialized successfully.")

    def status(self) -> dict:
        """Return the detailed status of the subsystem."""
        return {
            "status": "ok",
            "enabled": self.is_enabled,
            "message": "Operator Cortex subsystem placeholder",
        }

    def enable(self) -> None:
        """Enable God-Mode stabilization."""
        self.is_enabled = True

    def disable(self) -> None:
        """Disable God-Mode stabilization."""
        self.is_enabled = False


if __name__ == "__main__":
    cortex_instance = OperatorCortex()
    print("🧠 Testing OperatorCortex directly...")
    print(f"Initial Status: {cortex_instance.status()}")

    cortex_instance.enable()
    print(f"After Enable:   {cortex_instance.status()}")

    cortex_instance.disable()
    print(f"After Disable:  {cortex_instance.status()}")
