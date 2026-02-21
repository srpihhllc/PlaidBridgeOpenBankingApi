# app/utils/boot_trace.py

from app.utils.redis_trace import emit_ttl_trace


def run_boot_trace():
    emit_ttl_trace("startup::db.auth", "connected")
    emit_ttl_trace("startup::blueprint.vault", "registered")
    emit_ttl_trace("startup::session.redis", "live")
    emit_ttl_trace("startup::pulse.monitor", "booting")
