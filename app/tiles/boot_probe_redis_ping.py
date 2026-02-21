# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tiles/boot_probe_redis_ping.py

from cockpit_trace import trace_log, ttl_emitter

from app.utils.redis_utils import get_redis_client  # ✅ centralised, SSL‑safe client


def probe_redis_ping():
    """
    Probe Redis connectivity at boot and emit cockpit telemetry.
    Falls back gracefully if Redis is unavailable.
    """
    r = get_redis_client()
    if not r:
        ttl_emitter("boot:redis_ping", status="red", ts=True)
        trace_log("boot:redis_ping", "❌ Redis unavailable", level="error")
        return

    try:
        pong = r.ping()
        ttl_emitter("boot:redis_ping", status="green" if pong else "red", ts=True)
        trace_log("boot:redis_ping", f"✅ Redis ping: {pong}", level="info")
    except Exception as e:
        ttl_emitter("boot:redis_ping", status="red", ts=True)
        trace_log("boot:redis_ping", f"❌ Redis ping failed: {e}", level="error")
