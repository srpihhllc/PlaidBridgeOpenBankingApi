import os

from cockpit_trace import trace_log, ttl_emitter


def probe_env_vars():
    required_keys = ["DB_PASSWORD", "REDIS_URL", "SECRET_KEY"]
    missing = [k for k in required_keys if not os.getenv(k)]
    if missing:
        ttl_emitter("boot:env_vars", status="red", ts=True)
        trace_log("boot:env_vars", f"❌ Missing env keys: {missing}", level="error")
    else:
        ttl_emitter("boot:env_vars", status="green", ts=True)
        trace_log("boot:env_vars", "✅ All required env vars present", level="info")
