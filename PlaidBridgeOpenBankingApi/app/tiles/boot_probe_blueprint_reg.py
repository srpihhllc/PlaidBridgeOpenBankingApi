import traceback

from cockpit_trace import trace_log, ttl_emitter
from flask import Blueprint


def probe_blueprint_reg():
    try:
        # Example import — update as needed
        from app.routes.borrower import borrower_bp

        assert isinstance(borrower_bp, Blueprint)
        ttl_emitter("boot:blueprint_reg", status="green", ts=True)
        trace_log(
            "boot:blueprint_reg",
            "✅ Blueprint 'borrower_bp' imported and valid",
            level="info",
        )
    except Exception:
        ttl_emitter("boot:blueprint_reg", status="red", ts=True)
        trace_log(
            "boot:blueprint_reg",
            f"❌ Blueprint import error:\n{traceback.format_exc()}",
            level="error",
        )
