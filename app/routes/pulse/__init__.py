# app/routes/pulse/__init__.py
"""Pulse routes package initialization."""

from app.routes.pulse.access_token import bp as pulse_access_token_bp

__all__ = ["pulse_access_token_bp"]