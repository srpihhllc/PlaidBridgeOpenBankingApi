# app/models/timeline.py
# Compatibility shim so callers can import from app.models.timeline

from app.models.timeline_event import TimelineEvent  # noqa: F401

__all__ = ["TimelineEvent"]
