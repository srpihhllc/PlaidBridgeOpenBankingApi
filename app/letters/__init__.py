"""
Letters module for dispute orchestration.

Handles rendering, dispatch, and audit of legal correspondence
to all credit reporting agencies and investigative targets.
"""

from .bureaus import BUREAUS
from .dispatcher import dispatch_letter
from .render_engine import render_letter

__all__ = ["BUREAUS", "dispatch_letter", "render_letter"]
