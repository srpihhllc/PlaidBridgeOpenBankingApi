# =============================================================================
# FILE: app/constants/telemetry_keys.py
# DESCRIPTION: Centralized constants for Redis/Cockpit health telemetry.
# =============================================================================

# --- TTL Durations (in seconds) ---
# Time-to-live for a successful Redis ping pulse (30 minutes)
REDIS_PING_TTL = 1_800
# Time-to-live for a Redis failure pulse (15 minutes)
REDIS_FAIL_TTL = 900
# Time-to-live for a successful queue flush pulse (30 minutes)
REDIS_QUEUE_FLUSH_TTL = 1_800

# --- Telemetry Key Names ---
# General status key (success/error)
REDIS_PING_KEY = "ttl:boot:redis_ping"
# Boolean success marker
REDIS_PING_SUCCESS_KEY = "ttl:boot:redis_ping_success"
# Timestamp of last success
REDIS_PING_SUCCESS_TS_KEY = "ttl:boot:redis_ping_success_timestamp"
# Marker indicating the internal queue was successfully cleared
REDIS_QUEUE_FLUSH_KEY = "ttl:boot:redis_queue_flushed"

# --- Metrics Configuration Placeholders ---
# The actual REDIS_CONNECT_FAILURES_COUNTER object lives in app.metrics.
# =============================================================================
