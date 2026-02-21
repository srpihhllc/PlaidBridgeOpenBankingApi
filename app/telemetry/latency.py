# app/telemetry/latency.py
# Compatibility shim so older imports remain valid while implementation lives in app.utils
# Re-export both emit_latency_trace and ttl_emit so tests can monkeypatch them.
from app.utils.latency import emit_latency_trace  # implementation moved to app/utils
from app.utils.ttl_emit import ttl_emit  # re-export the ttl_emit shim/impl used at runtime

__all__ = ["emit_latency_trace", "ttl_emit"]
