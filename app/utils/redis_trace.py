# app/utils/redis_trace.py


def emit_ttl_trace(key: str, value: str):
    print(f"[TTL TRACE] {key} → {value}")
