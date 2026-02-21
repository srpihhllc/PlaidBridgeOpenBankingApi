# app/utils/blueprint_utils.py

from flask import Flask

from app.telemetry.ttl_emit import trace_log, ttl_emit


def register_with_trace(app: Flask, bp, name: str, trace_key: str = None):
    """
    Register a blueprint with TTL and trace logging.

    Args:
        app (Flask): Flask app instance
        bp (Blueprint): Blueprint to register
        name (str): Human-readable name for logging
        trace_key (str): Optional trace_log key
    """
    try:
        app.register_blueprint(bp)
        app.logger.info(f"✅ {name} blueprint registered.")

        ttl_emit(
            key=f"ttl:blueprint:{name}",
            value=None,
            status="success",
            ttl=300,
        )

        if trace_key:
            trace_log(trace_key, f"{name} blueprint registered.")

    except Exception as e:
        app.logger.warning(f"⚠️ {name} blueprint failed to register: {e}")

        ttl_emit(
            key=f"ttl:blueprint:{name}",
            value=None,
            status="error",
            ttl=300,
        )

        if trace_key:
            trace_log(f"{trace_key}_error", f"{name} blueprint failed: {e}")
