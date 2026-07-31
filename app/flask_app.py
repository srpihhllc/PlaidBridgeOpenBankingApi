# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/flask_app.py

"""
Thin compatibility shim routing to the canonical application factory.
All domain service imports and fallback overrides have been decoupled
to protect the application boot sequence from circular dependencies.
"""

from __future__ import annotations
import os
from typing import Any
from app import create_app as create_package_app

# Global instantiation variable reserved strictly for legacy callers
# explicitly opting in via the environment flag.
app: Any | None = None

if os.getenv("EXPORT_LEGACY_APP", "0") == "1":
    app = create_package_app()
    app.config.setdefault("ENABLE_SERVICE_WORKER", os.getenv("ENABLE_SERVICE_WORKER", "1").lower() in ("1", "true", "yes"))

def get_app() -> Any:
    """
    Authoritative factory pass-through wrapper for legacy entry points.
    """
    global app
    if app is not None:
        return app

    flask_app = create_package_app()
    flask_app.config.setdefault("ENABLE_SERVICE_WORKER", os.getenv("ENABLE_SERVICE_WORKER", "1").lower() in ("1", "true", "yes"))
    return flask_app

__all__ = ["get_app", "app"]